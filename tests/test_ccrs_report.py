"""Tests for src/index/ccrs_report -- the final CCRS assembly (T1 x T2 x T3)
and the T4-band capacity-share / contingency report.

1. Hand-calculated multiplicative chain (Hazard x age_factor x EventMultiplier).
2. Capacity aggregation uses the V6 computable base, never capacity_mw
   directly -- the assert fails loud if it does not.
3. % capacity by band sums to 1.0 within every (country, scenario[, gcm])
   group, including a NO_BAND row for unbanded plants.
4. WaterRiskBand x HeatRiskBand contingency is reused from risk_bands.py
   (T4), never a single combined score.
5. The report contains the HeatRiskBand warning, the wind fallback note, and
   the missing-commissioning_year fraction.
6. End-to-end on real data: no plant_uid row is duplicated or dropped
   relative to the 10,808-plant x scenario expectation.
"""

import inspect

import numpy as np
import pandas as pd
import pytest

from src.index import age_factor
from src.index import ccrs_calculator as ccrs
from src.index import ccrs_report as cr
from src.index import risk_bands
from src.index.ccrs_calculator import PLANT_UID


# --------------------------------------------------------------------------
# 1. multiplicative chain, hand-calculated
# --------------------------------------------------------------------------
def test_compute_ccrs_multiplies_hazard_age_factor_and_event_multiplier(tmp_path):
    hazard = pd.DataFrame({
        PLANT_UID: ["BRA-1", "IND-1"],
        "country": ["Brazil", "India"],
        "water_scenario": ["opt", "opt"],
        "hazard_gfdl_esm4": [0.20, 0.40],
        "hazard_miroc6": [0.10, 0.50],
    })
    hz_csv = tmp_path / "ccrs_hazard.csv"
    hazard.to_csv(hz_csv, index=False)

    af = pd.DataFrame({
        PLANT_UID: ["BRA-1", "IND-1"],
        "age": [30.0, 40.0],
        "age_factor": [1.10, 1.20],
        "age_factor_neutralized_missing_year": [False, False],
    })
    em = pd.DataFrame({
        "country": ["Brazil", "India"],
        "n_events": [239, 622],
        "rate": [239 / 124, 622 / 124],
        "event_multiplier": [1.192122, 1.5],
    })

    out = cr.compute_ccrs(hz_csv, age_factors=af, event_multipliers=em)
    row = out.set_index(PLANT_UID)

    # 0.20 * 1.10 * 1.192122 -- hand-calculated
    assert row.loc["BRA-1", "ccrs_gfdl_esm4"] == pytest.approx(0.20 * 1.10 * 1.192122)
    assert row.loc["BRA-1", "ccrs_miroc6"] == pytest.approx(0.10 * 1.10 * 1.192122)
    # 0.40 * 1.20 * 1.5 = 0.72 exactly
    assert row.loc["IND-1", "ccrs_gfdl_esm4"] == pytest.approx(0.72)
    assert row.loc["IND-1", "ccrs_miroc6"] == pytest.approx(0.50 * 1.20 * 1.5)
    # original Hazard columns untouched
    np.testing.assert_allclose(out["hazard_gfdl_esm4"], hazard["hazard_gfdl_esm4"])


def test_compute_ccrs_rejects_a_country_missing_from_event_multipliers(tmp_path):
    hazard = pd.DataFrame({
        PLANT_UID: ["BRA-1"], "country": ["Brazil"], "water_scenario": ["opt"],
        "hazard_gfdl_esm4": [0.2], "hazard_miroc6": [0.1],
    })
    hz_csv = tmp_path / "ccrs_hazard.csv"
    hazard.to_csv(hz_csv, index=False)
    af = pd.DataFrame({
        PLANT_UID: ["BRA-1"], "age": [10.0], "age_factor": [1.0],
        "age_factor_neutralized_missing_year": [False],
    })
    em = pd.DataFrame({
        "country": ["India"], "n_events": [622], "rate": [622 / 124],
        "event_multiplier": [1.5],
    })
    with pytest.raises(ValueError, match="Brazil"):
        cr.compute_ccrs(hz_csv, age_factors=af, event_multipliers=em)


# --------------------------------------------------------------------------
# 2. capacity: V6 computable base only, asserted
# --------------------------------------------------------------------------
def test_capacity_sum_requires_the_computable_base():
    df = pd.DataFrame({"capacity_mw": [10.0, 20.0], "commissioning_year": [2000.0, np.nan]})
    with pytest.raises(AssertionError, match="computable_base"):
        cr.capacity_sum(df)


def test_capacity_sum_matches_the_computable_base_total_excluding_missing_year():
    df = pd.DataFrame({"capacity_mw": [10.0, 20.0, 5.0], "commissioning_year": [2000.0, np.nan, 1995.0]})
    base = ccrs.computable_base(df)
    assert cr.capacity_sum(base) == pytest.approx(15.0)   # 10 + 5, the 20 MW NaN-year row excluded


# --------------------------------------------------------------------------
# 3. % capacity by band sums to 1.0, including NO_BAND
# --------------------------------------------------------------------------
def test_band_capacity_shares_sum_to_one_including_no_band():
    frame = pd.DataFrame({
        "country": ["Brazil", "Brazil", "Brazil", "Brazil", "India", "India"],
        "water_scenario": ["opt"] * 6,
        "capacity_mw": [10.0, 20.0, 30.0, 5.0, 100.0, 50.0],
        "commissioning_year": [2000.0] * 6,
        "test_band": ["Low", "High", None, "Low", "Extremely-High", "Extremely-High"],
    })
    bands = ["Low", "Low-Medium", "Medium-High", "High", "Extremely-High"]
    out = cr.band_capacity_shares(frame, "test_band", bands, ["country", "water_scenario"])

    totals = out.groupby(["country", "water_scenario"])["capacity_share"].sum()
    np.testing.assert_allclose(totals.to_numpy(), 1.0)

    # Brazil: 10+20+30+5=65 total, the 30 MW row has no band -> NO_BAND = 30/65
    br_no_band = out[(out["country"] == "Brazil") & (out["band"] == "NO_BAND")]
    assert br_no_band["capacity_share"].iloc[0] == pytest.approx(30 / 65)
    # India: fully banded, no NO_BAND capacity
    in_no_band = out[(out["country"] == "India") & (out["band"] == "NO_BAND")]
    assert in_no_band["capacity_share"].iloc[0] == pytest.approx(0.0)
    in_extreme = out[(out["country"] == "India") & (out["band"] == "Extremely-High")]
    assert in_extreme["capacity_share"].iloc[0] == pytest.approx(1.0)


def test_band_capacity_shares_excludes_rows_without_commissioning_year():
    # a plant missing commissioning_year must not enter any capacity total
    frame = pd.DataFrame({
        "country": ["Brazil", "Brazil"],
        "water_scenario": ["opt", "opt"],
        "capacity_mw": [10.0, 1000.0],
        "commissioning_year": [2000.0, np.nan],
        "test_band": ["Low", "Low"],
    })
    out = cr.band_capacity_shares(frame, "test_band", ["Low"], ["country", "water_scenario"])
    low = out[out["band"] == "Low"]
    assert low["capacity_mw"].iloc[0] == pytest.approx(10.0)   # the 1000 MW NaN-year row is excluded


# --------------------------------------------------------------------------
# 4. contingency table reused from risk_bands (T4), never a single score
# --------------------------------------------------------------------------
def test_contingency_table_is_reused_from_risk_bands_and_is_never_a_single_score():
    frame = pd.DataFrame({
        "water_risk_band": ["Low", "High", "Extremely-High"],
        "heat_risk_band": ["LOW", "EXTREME", "EXTREME"],
    })
    tab = risk_bands.contingency_table(frame, "count")
    assert isinstance(tab, pd.DataFrame)
    assert tab.shape == (len(risk_bands.WATER_RISK_BANDS), len(risk_bands.HEAT_RISK_BANDS))
    assert tab.shape != (1, 1)   # never collapses to a single cell/score

    # ccrs_report.build_summary literally calls risk_bands.contingency_table
    # -- confirms reuse, not a duplicated reimplementation.
    src = inspect.getsource(cr.build_summary)
    assert "risk_bands.contingency_table" in src


# --------------------------------------------------------------------------
# 5. report contents
# --------------------------------------------------------------------------
def _minimal_band_table(gcm: str) -> risk_bands.BandTable:
    frame = pd.DataFrame({
        PLANT_UID: ["A-1", "B-2"],
        "country": ["Brazil", "India"],
        "water_scenario": ["opt", "opt"],
        "heat_scenario": ["ssp126", "ssp126"],
        "capacity_mw": [10.0, 20.0],
        "commissioning_year": [2000.0, 1990.0],
        "water_risk_band": ["Low", "High"],
        "heat_risk_band": ["LOW", "EXTREME"],
    })
    return risk_bands.BandTable(frame=frame, heat_cuts={25: 1.0, 75: 2.0, 95: 3.0}, heat_gcm=gcm)


def test_report_contains_the_warning_wind_note_and_missing_year_fraction():
    af = pd.DataFrame({
        "country": ["Brazil", "Portugal", "India"],
        "age_factor_neutralized_missing_year": [False, False, True],
    })
    band_tables = {"gfdl_esm4": _minimal_band_table("gfdl_esm4"),
                   "miroc6": _minimal_band_table("miroc6")}
    water_shares = cr.compute_water_band_shares(band_tables)
    heat_shares = cr.compute_heat_band_shares(band_tables)
    ccrs_final = pd.DataFrame({"ccrs_gfdl_esm4": [1.1, 1.3], "ccrs_miroc6": [1.0, 1.2]})

    report = cr.build_summary(af, water_shares, heat_shares, band_tables, ccrs_final)

    assert risk_bands.HEAT_BAND_WARNING in report
    assert "CF_initial" in report
    assert f"{age_factor.WIND_RELATIVE_RATE:.1%}" in report
    assert "commissioning_year" in report
    assert "India" in report   # the missing-year table names the country


# --------------------------------------------------------------------------
# 6. end-to-end on real data: no plant_uid duplicated or dropped
# --------------------------------------------------------------------------
def _real_data_present() -> bool:
    return cr.HAZARD_CSV.exists() and all(
        (ccrs.ASSETS_PROCESSED / f"gem_validated_plants_{c}.csv").exists()
        for c in ccrs.COUNTRIES
    )


@pytest.mark.skipif(not _real_data_present(), reason="ccrs_hazard.csv or validated-plant CSVs absent")
def test_real_data_ccrs_has_no_duplicate_or_missing_plant_uid():
    hz = pd.read_csv(cr.HAZARD_CSV)
    ccrs_df = cr.compute_ccrs()

    assert len(ccrs_df) == len(hz)
    assert not ccrs_df.duplicated([PLANT_UID, "water_scenario"]).any()

    expected_plants = age_factor.load_plant_attributes()[PLANT_UID].nunique()
    n_scenarios = ccrs_df["water_scenario"].nunique()
    assert ccrs_df[PLANT_UID].nunique() == expected_plants
    assert len(ccrs_df) == expected_plants * n_scenarios

    for col in cr.CCRS_COLUMNS.values():
        if col in ccrs_df.columns:
            finite = ccrs_df[col].dropna()
            # Hazard itself can be exactly 0 (a plant at the pooled Min-Max
            # floor, or a zero-weight side); age_factor/event_multiplier are
            # always >= 1, so CCRS can never go negative.
            assert (finite >= 0.0).all()
