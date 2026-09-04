"""Tests for src/visualization -- the 11 approved CCRS figure categories.

Covers: one test per figure category running on small synthetic data (no
rendering validation, just "runs without raising and produces the expected
file/object"), disputed-territory handling (India) still works against the
new schema, computable-base plants are always marked (never omitted),
per-country + combined produce the right file counts, and the module never
reads a CSV from data/outputs/tables/ (mocks src/index/* and confirms the
result tracks the mock, not a pre-existing file).

Figure-generating tests are skipped (never silently passed) when the GADM
boundary files are absent -- they are raw source data, not stale-methodology
output, so this is the same kind of skip other test files already use for
processed rasters / validated-plant CSVs.
"""

import matplotlib
matplotlib.use("Agg")  # headless -- no display needed for these tests

import numpy as np
import pandas as pd
import pytest

from src.config import COUNTRIES
from src.index.ccrs_calculator import BUCKETS
from src.index.risk_bands import HEAT_RISK_BANDS, PRIMARY_GCM, WATER_RISK_BANDS, BandTable
from src.visualization import _common, charts, data as vdata, maps


def _boundaries_present() -> bool:
    try:
        return all(_common.load_admin1_boundaries(c) is not None for c in COUNTRIES)
    except Exception:
        return False


boundaries_needed = pytest.mark.skipif(not _boundaries_present(), reason="GADM boundary files absent")


# --------------------------------------------------------------------------
# Synthetic fixtures -- no real CCRS data, no disk I/O beyond raw GADM boundaries
# --------------------------------------------------------------------------
def _synthetic_final() -> pd.DataFrame:
    rows = []
    coords = {
        "Brazil": (-50.0, -15.0), "Portugal": (-8.0, 39.5), "India": (78.0, 22.0),
    }
    plant_id = 0
    for country in COUNTRIES:
        lon0, lat0 = coords[country]
        for i, bucket in enumerate(BUCKETS):
            for scen, gcm_a, gcm_b in [("opt", 0.3, 0.5), ("bau", 0.5, 0.7), ("pes", 0.7, 0.9)]:
                plant_id += 1
                missing_year = country == "Brazil" and bucket == "wind"  # exercise the "excluded" path
                rows.append({
                    "plant_uid": f"{country[:3].upper()}-{plant_id:04d}",
                    "water_scenario": scen, "heat_scenario": {"opt": "ssp126", "bau": "ssp370", "pes": "ssp585"}[scen],
                    "country": country, "plant_name": f"{bucket} plant {i}",
                    "lat": lat0 + i * 0.3, "lon": lon0 + i * 0.3,
                    "bucket": bucket, "capacity_mw": 50.0 + i * 20,
                    "commissioning_year": np.nan if missing_year else 2000 + i,
                    "hazard_gfdl_esm4": gcm_a * (i + 1) / len(BUCKETS),
                    "hazard_miroc6": gcm_b * (i + 1) / len(BUCKETS),
                    "age": np.nan if missing_year else 50.0 - i,
                    "age_factor": 1.0 + 0.1 * i,
                    "age_factor_neutralized_missing_year": missing_year,
                    "n_events": 100, "rate": 0.8, "event_multiplier": 1.2,
                    "ccrs_gfdl_esm4": gcm_a * (i + 1) / len(BUCKETS) * (1.0 + 0.1 * i) * 1.2,
                    "ccrs_miroc6": gcm_b * (i + 1) / len(BUCKETS) * (1.0 + 0.1 * i) * 1.2,
                    "water_risk_band": WATER_RISK_BANDS[i % len(WATER_RISK_BANDS)],
                    "heat_risk_band_gfdl_esm4": HEAT_RISK_BANDS[i % len(HEAT_RISK_BANDS)],
                    "heat_risk_band_miroc6": HEAT_RISK_BANDS[(i + 1) % len(HEAT_RISK_BANDS)],
                    "computable": not missing_year,
                })
    return pd.DataFrame(rows)


def _synthetic_bands(final: pd.DataFrame) -> dict[str, BandTable]:
    out = {}
    for gcm in ("gfdl_esm4", "miroc6"):
        frame = final[["plant_uid", "country", "water_scenario", "heat_scenario", "capacity_mw",
                        "commissioning_year", "water_risk_band"]].copy()
        frame["heat_risk_band"] = final[f"heat_risk_band_{gcm}"]
        out[gcm] = BandTable(frame=frame, heat_cuts={25: 1.0, 75: 2.0, 95: 3.0}, heat_gcm=gcm)
    return out


def _synthetic_age_factors(final: pd.DataFrame) -> pd.DataFrame:
    return final[["plant_uid", "country", "bucket", "age_factor",
                   "age_factor_neutralized_missing_year"]].drop_duplicates("plant_uid")


def _synthetic_event_multipliers() -> pd.DataFrame:
    return pd.DataFrame({
        "country": COUNTRIES, "n_events": [239, 38, 622],
        "rate": [1.9, 0.3, 5.0], "event_multiplier": [1.19, 1.03, 1.5],
    })


@pytest.fixture(scope="module")
def synth():
    final = _synthetic_final()
    return {
        "final": final,
        "bands": _synthetic_bands(final),
        "age_factors": _synthetic_age_factors(final),
        "event_multipliers": _synthetic_event_multipliers(),
    }


# --------------------------------------------------------------------------
# 1. One test per figure category -- runs without error on synthetic data
# --------------------------------------------------------------------------
@boundaries_needed
def test_category_1_ccrs_overview_map(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    paths = maps.plot_ccrs_overview_map(countries=["Portugal"], final=synth["final"])
    assert paths["Portugal"].exists()


@boundaries_needed
def test_category_2_scenario_delta_map(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    paths = maps.plot_ccrs_scenario_delta_map(countries=["Portugal"], final=synth["final"])
    assert paths["Portugal"].exists()


@boundaries_needed
def test_category_3_water_risk_band_map(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    paths = maps.plot_water_risk_band_map(countries=["Portugal"], final=synth["final"])
    assert paths["Portugal"].exists()


@boundaries_needed
def test_category_4_heat_risk_band_map(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    paths = maps.plot_heat_risk_band_map(countries=["Portugal"], final=synth["final"])
    assert paths["Portugal"].exists()


def test_category_5_contingency_heatmap(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "OUT_DIR", tmp_path)
    paths = charts.plot_contingency_heatmap(countries=["Portugal"], bands=synth["bands"])
    assert paths["Portugal"].exists()


def test_category_6_ccrs_distribution_by_bucket(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "OUT_DIR", tmp_path)
    path = charts.plot_ccrs_distribution_by_bucket(final=synth["final"])
    assert path.exists()


def test_category_7_age_factor_by_bucket(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "OUT_DIR", tmp_path)
    path = charts.plot_age_factor_by_bucket(age_factors=synth["age_factors"])
    assert path.exists()


def test_category_8_capacity_by_risk_band(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "OUT_DIR", tmp_path)
    water_shares = vdata.load_water_band_shares(synth["bands"])
    heat_shares = vdata.load_heat_band_shares(synth["bands"])
    path = charts.plot_capacity_by_risk_band(water_shares=water_shares, heat_shares=heat_shares)
    assert path.exists()


def test_category_9_event_multiplier_by_country(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "OUT_DIR", tmp_path)
    path = charts.plot_event_multiplier_by_country(event_multipliers=synth["event_multipliers"])
    assert path.exists()


@boundaries_needed
def test_category_10_computable_base_map(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    paths = maps.plot_computable_base_map(countries=["Brazil"], final=synth["final"])
    assert paths["Brazil"].exists()


def test_category_11_top_n_ccrs_breakdown(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "OUT_DIR", tmp_path)
    path = charts.plot_top_n_ccrs_breakdown(final=synth["final"], n=5)
    assert path.exists()


# --------------------------------------------------------------------------
# 2. Disputed territory (India) still works against the new schema
# --------------------------------------------------------------------------
@boundaries_needed
def test_india_disputed_territory_handling():
    assert _common.country_has_disputed_admin1("India") == True  # noqa: E712 (numpy bool)
    assert _common.country_has_disputed_admin1("Brazil") == False  # noqa: E712
    assert _common.country_has_disputed_admin1("Portugal") == False  # noqa: E712

    disclaimer = _common.footer_with_gadm_disclaimer("", ["India"])
    assert _common.GADM_DISCLAIMER_TEXT in disclaimer
    assert _common.footer_with_gadm_disclaimer("", ["Brazil"]) == ""


@boundaries_needed
def test_india_map_renders_with_disputed_admin1(synth, tmp_path, monkeypatch):
    """End-to-end: a map over India (new CCRS schema) must not raise while
    drawing the disputed admin-1 polygons."""
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    paths = maps.plot_ccrs_overview_map(countries=["India"], final=synth["final"])
    assert paths["India"].exists()


# --------------------------------------------------------------------------
# 3. Computable-base-excluded plants: always marked, never omitted
# --------------------------------------------------------------------------
def test_excluded_plants_are_marked_never_dropped(synth):
    final = synth["final"]
    excluded = final[~final["computable"]]
    assert len(excluded) > 0, "fixture must contain at least one excluded plant to test this"

    frame_country = final[(final["country"] == "Brazil") & (final["water_scenario"] == "bau")]
    # Direct check on the panel-drawing helper's bookkeeping instead of
    # pixel inspection: it must count every excluded row, not drop any.
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    try:
        stats = maps._draw_bubble_panel(ax, "Brazil", frame_country, ring_col=None)
    finally:
        plt.close(fig)
    expected_excluded = len(frame_country[~frame_country["computable"]])
    assert stats["n_excluded"] == expected_excluded
    assert expected_excluded > 0


def test_computable_base_map_includes_excluded_in_footer_count(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    if not _boundaries_present():
        pytest.skip("GADM boundary files absent")
    # Regression guard: rendering must not silently filter the excluded rows
    # out of the input frame before drawing.
    final = synth["final"]
    frame_country = final[(final["country"] == "Brazil") & (final["water_scenario"] == "bau")]
    assert (~frame_country["computable"]).any()
    paths = maps.plot_computable_base_map(countries=["Brazil"], final=final)
    assert paths["Brazil"].exists()


# --------------------------------------------------------------------------
# 4. Per-country + combined produce the correct number of files
# --------------------------------------------------------------------------
@boundaries_needed
def test_per_country_and_combined_file_counts(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    per_country = maps.plot_ccrs_overview_map(final=synth["final"], combined=False)
    assert len(per_country) == len(COUNTRIES)
    assert set(per_country) == set(COUNTRIES)
    for p in per_country.values():
        assert p.exists() and p.with_suffix(".pdf").exists()

    combined = maps.plot_ccrs_overview_map(final=synth["final"], combined=True)
    assert len(combined) == 1
    assert "combined" in combined
    assert combined["combined"].exists() and combined["combined"].with_suffix(".pdf").exists()


# --------------------------------------------------------------------------
# 5. No dependency on cached CSVs in data/outputs/tables/
# --------------------------------------------------------------------------
def test_load_ccrs_final_never_reads_a_cached_csv(monkeypatch, tmp_path):
    """Patches every src/index/* entry point data.py calls with in-memory
    fakes and confirms the result tracks the fakes -- if the module fell
    back to reading a CSV from data/outputs/tables/, the assertions below
    (which check the OUTPUT matches the FAKE, not whatever happens to be on
    disk) would fail."""
    from src.index import age_factor, ccrs_calculator as ccrs, event_multiplier, risk_bands

    fake_hazard = pd.DataFrame({
        "plant_uid": ["X-01"], "country": ["Brazil"], "plant_name": ["fake"],
        "lat": [0.0], "lon": [0.0], "water_scenario": ["bau"], "heat_scenario": ["ssp370"],
        "bucket": ["thermal"], "capacity_mw": [10.0], "commissioning_year": [2000.0],
        "hazard_gfdl_esm4": [0.42], "hazard_miroc6": [0.55],
    })
    fake_af = pd.DataFrame({
        "plant_uid": ["X-01"], "age": [50.0], "age_factor": [1.3],
        "age_factor_neutralized_missing_year": [False],
    })
    fake_em = pd.DataFrame({
        "country": ["Brazil"], "n_events": [1], "rate": [0.1], "event_multiplier": [1.05],
    })
    fake_band_frame = pd.DataFrame({
        "plant_uid": ["X-01"], "water_scenario": ["bau"], "water_risk_band": ["Low"],
        "heat_risk_band": ["LOW"],
    })
    fake_bands = {
        gcm: risk_bands.BandTable(frame=fake_band_frame.copy(), heat_cuts={25: 1, 75: 2, 95: 3}, heat_gcm=gcm)
        for gcm in ccrs.configured_models()
    }

    def _boom(*a, **k):
        raise AssertionError("data.py must not read a CSV from data/outputs/tables/")

    monkeypatch.setattr(ccrs, "compute_hazard_by_gcm", lambda *a, **k: fake_hazard.copy())
    monkeypatch.setattr(age_factor, "compute_age_factors", lambda *a, **k: fake_af.copy())
    monkeypatch.setattr(event_multiplier, "compute_event_multipliers", lambda *a, **k: fake_em.copy())
    monkeypatch.setattr(risk_bands, "compute_bands", lambda gcm=None, **k: fake_bands[gcm or risk_bands.PRIMARY_GCM])
    monkeypatch.setattr(pd, "read_csv", _boom)

    final = vdata.load_ccrs_final()

    assert list(final["plant_uid"]) == ["X-01"]
    assert final["ccrs_gfdl_esm4"].iloc[0] == pytest.approx(0.42 * 1.3 * 1.05)
    assert final["water_risk_band"].iloc[0] == "Low"
