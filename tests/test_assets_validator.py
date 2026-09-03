"""Tests for assets_validator — status filter, plant aggregation, fuel
bucketing, and mainland-only exclusion. Synthetic fixtures only, no GEM
download."""

import numpy as np
import pandas as pd
import pytest

from src.downloaders import assets_validator as av


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
def _gem_rows():
    """One row per generating unit, GEM column names."""
    return pd.DataFrame(
        {
            "Plant / Project name": [
                "Alpha", "Alpha",          # two units, same plant -> aggregate
                "Beta",                    # planned
                "Gamma",                   # retired -> excluded from both
                "Delta",                   # Portugal mainland
                "Ilha", "Ilha",            # Portugal island -> mainland exclusion
                "Itaqui power station", "Itaqui power station",  # divergent fuel -> mixed
            ],
            "Latitude": [-10.0, -10.00005, -12.0, -13.0, 39.5, 32.7, 32.7, 20.0, 20.00005],
            "Longitude": [-40.0, -40.00005, -41.0, -42.0, -8.0, -16.9, -16.9, 78.0, 78.00005],
            "Capacity (MW)": [100.0, 50.0, 200.0, 10.0, 30.0, 5.0, 5.0, 60.0, 40.0],
            "Type": [
                "coal", "coal",
                "wind",
                "hydropower",
                "utility-scale solar",
                "oil/gas", "oil/gas",
                "coal", "oil/gas",
            ],
            "Start year": [1990, 2005, 2020, 1970, 2015, 2000, 2001, 1995, 2010],
            "Country/area": [
                "Brazil", "Brazil", "Brazil", "Brazil",
                "Portugal", "Portugal", "Portugal", "India", "India",
            ],
            "Status": [
                "operating", "operating", "construction", "retired",
                "operating", "operating", "operating", "operating", "operating",
            ],
        }
    )


# --------------------------------------------------------------------------
# Status filter
# --------------------------------------------------------------------------
def test_split_by_status_separates_operating_planned_other():
    operating, planned, summary = av.split_by_status(av._apply_mapping(_gem_rows()))
    assert summary["n_operating"] == 7
    assert summary["n_planned"] == 1        # "construction"
    assert summary["n_other_excluded_from_both"] == 1  # "retired"
    assert set(planned["plant_name"]) == {"Beta"}
    assert "Gamma" not in set(operating["plant_name"])


# --------------------------------------------------------------------------
# Plant aggregation
# --------------------------------------------------------------------------
def test_aggregate_sums_capacity_and_takes_oldest_year():
    df = av._apply_mapping(_gem_rows())
    operating, _, _ = av.split_by_status(df)
    agg = av.aggregate_by_plant(operating)

    alpha = agg[agg["plant_name"] == "Alpha"].iloc[0]
    assert alpha["capacity_mw"] == 150.0
    assert alpha["commissioning_year"] == 1990   # min across units
    assert alpha["n_units"] == 2
    assert not alpha["mixed_fuel_type"]


def test_aggregate_flags_divergent_fuel_as_mixed():
    df = av._apply_mapping(_gem_rows())
    operating, _, _ = av.split_by_status(df)
    agg = av.aggregate_by_plant(operating)

    mix = agg[agg["plant_name"] == "Itaqui power station"].iloc[0]
    assert bool(mix["mixed_fuel_type"]) is True
    assert pd.isna(mix["fuel_type"])
    assert mix["fuel_types_found"] == "coal;oil/gas"


def test_aggregate_capacity_all_missing_stays_nan():
    df = pd.DataFrame(
        {
            "country": ["Brazil", "Brazil"],
            "plant_name": ["X", "X"],
            "lat": [1.0, 1.0],
            "lon": [2.0, 2.0],
            "capacity_mw": [np.nan, np.nan],
            "fuel_type": ["coal", "coal"],
            "commissioning_year": [2000, 2001],
        }
    )
    agg = av.aggregate_by_plant(df)
    assert np.isnan(agg.iloc[0]["capacity_mw"])


# --------------------------------------------------------------------------
# Fuel bucketing
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "fuel, expected",
    [
        ("hydropower", "hydro"),
        ("wind", "wind"),
        ("utility-scale solar", "solar"),
        ("coal", "thermal"),
        ("oil/gas", "thermal"),
        ("nuclear", "thermal"),
        ("bioenergy", "thermal"),
        ("geothermal", "thermal"),
    ],
)
def test_fuel_bucket_maps_all_thermal_together(fuel, expected):
    df = pd.DataFrame(
        [{"plant_name": "P", "fuel_type": fuel, "mixed_fuel_type": False, "fuel_types_found": fuel}]
    )
    assert av.add_fuel_bucket(df).iloc[0]["fuel_type_bucket"] == expected


def test_fuel_bucket_only_four_categories():
    assert sorted(set(av.FUEL_TYPE_TO_BUCKET.values())) == ["hydro", "solar", "thermal", "wind"]


def test_fuel_bucket_unmapped_fuel_raises():
    df = pd.DataFrame(
        [{"plant_name": "P", "fuel_type": "fusion", "mixed_fuel_type": False, "fuel_types_found": "fusion"}]
    )
    with pytest.raises(ValueError):
        av.add_fuel_bucket(df)


def test_fuel_bucket_mixed_plant_uses_override():
    df = pd.DataFrame(
        [{"plant_name": "Itaqui power station", "fuel_type": None,
          "mixed_fuel_type": True, "fuel_types_found": "coal;oil/gas"}]
    )
    assert av.add_fuel_bucket(df).iloc[0]["fuel_type_bucket"] == "thermal"


def test_fuel_bucket_unlisted_mixed_plant_raises():
    df = pd.DataFrame(
        [{"plant_name": "Unknown mixed", "fuel_type": None,
          "mixed_fuel_type": True, "fuel_types_found": "coal;oil/gas"}]
    )
    with pytest.raises(ValueError):
        av.add_fuel_bucket(df)


# --------------------------------------------------------------------------
# Mainland-only exclusion (end-to-end validate())
# --------------------------------------------------------------------------
@pytest.fixture
def _wired(monkeypatch, tmp_path):
    monkeypatch.setattr(av, "ASSETS_PROCESSED", tmp_path)
    bounds = {
        "Brazil": (-74.0, -34.0, -28.0, 6.0),
        "Portugal": (-9.5, 36.9, -6.2, 42.2),   # mainland only — excludes Madeira (~ -16.9, 32.7)
        "India": (68.0, 6.5, 97.5, 35.5),
    }
    monkeypatch.setattr(av, "get_country_bounds", lambda c: bounds[c])
    return tmp_path


def test_validate_excludes_island_plants_for_portugal(_wired, tmp_path):
    csv = tmp_path / "gem.csv"
    _gem_rows().to_csv(csv, index=False)

    report = av.validate(csv)

    pt = report["countries"]["Portugal"]
    assert pt["n_excluded_mainland_only"] == 1          # "Ilha" aggregated to one plant
    assert (tmp_path / "gem_excluded_azores_madeira.csv").exists()

    validated_pt = pd.read_csv(tmp_path / "gem_validated_plants_Portugal.csv")
    assert "Ilha" not in set(validated_pt["plant_name"])
    assert "Delta" in set(validated_pt["plant_name"])


def test_validate_reports_but_keeps_out_of_bbox_for_non_mainland(_wired, tmp_path):
    csv = tmp_path / "gem.csv"
    rows = _gem_rows()
    # push the India plant outside the India bbox
    rows.loc[rows["Country/area"] == "India", "Longitude"] = 120.0
    rows.to_csv(csv, index=False)

    report = av.validate(csv)
    india = report["countries"]["India"]
    assert india["n_out_of_country_bbox"] == 1
    assert india["n_excluded_mainland_only"] == 0
    validated_in = pd.read_csv(tmp_path / "gem_validated_plants_India.csv")
    assert "Itaqui power station" in set(validated_in["plant_name"])  # kept despite out of bbox


def test_validate_status_summary_counts(_wired, tmp_path):
    csv = tmp_path / "gem.csv"
    _gem_rows().to_csv(csv, index=False)
    report = av.validate(csv)
    assert report["status_summary"]["n_operating"] == 7
    assert report["status_summary"]["n_planned"] == 1
    assert report["fuel_buckets"] == ["hydro", "solar", "thermal", "wind"]
