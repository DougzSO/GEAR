"""Tests for src/index/risk_calculator -- GEAR v3 Equation 1, Risk_i,h.

Covers: Equation 1's arithmetic, the Exposure type-level guard (log10
display transform rejected by risk_i_h), the per-hazard temporal-window
constants, the retained transform/bounds infrastructure (unchanged from the
retired ccrs_calculator.py -- Phase 1 does not touch normalization
methodology), and that the retired CCRS weighted-sum-across-hazards
computation and EventMultiplier are gone from this module specifically.

Pure-function and monkeypatched tests run without touching disk. Tests that
read the processed rasters or the validated-plant CSVs are skipped (never
silently passed) when those inputs are absent.
"""

import inspect

import numpy as np
import pandas as pd
import pytest

from src.index import risk_calculator as rc


# --------------------------------------------------------------------------
# Equation 1: Risk_i,h = Hazard_i,h * Exposure_i(MW) * Vulnerability_i
# --------------------------------------------------------------------------
def test_risk_i_h_is_the_plain_product():
    hazard_i_h = np.array([0.0, 0.5, 1.0])
    exposure_mw = rc.exposure_capacity_mw([100.0, 200.0, 50.0])
    vulnerability = np.array([1.0, 1.2, 1.75])
    out = rc.risk_i_h(hazard_i_h, exposure_mw, vulnerability)
    np.testing.assert_allclose(out, [0.0, 0.5 * 200.0 * 1.2, 1.0 * 50.0 * 1.75])


def test_risk_i_h_never_combines_hazards_by_construction():
    """risk_i_h takes one hazard's Hazard_i,h array at a time -- there is no
    signature that accepts more than one hazard term, so a caller cannot
    accidentally sum across hazards inside this function."""
    sig = inspect.signature(rc.risk_i_h)
    assert list(sig.parameters) == ["hazard_i_h", "exposure_mw", "vulnerability"]


def test_risk_i_h_rejects_the_log10_display_exposure_by_type():
    hazard_i_h = np.array([0.5])
    vulnerability = np.array([1.0])
    log_exposure = rc.exposure_log10_display([999.0])
    with pytest.raises(TypeError, match="log10"):
        rc.risk_i_h(hazard_i_h, log_exposure, vulnerability)


def test_exposure_capacity_mw_is_raw_not_logged():
    out = rc.exposure_capacity_mw([0.0, 9.0, 99.0])
    np.testing.assert_allclose(out, [0.0, 9.0, 99.0])
    assert not isinstance(out, rc.ExposureLog10Display)


def test_exposure_log10_display_is_log10_of_mw_plus_1_and_is_tagged():
    out = rc.exposure_log10_display([0.0, 9.0, 99.0])
    np.testing.assert_allclose(out, np.log10(np.array([1.0, 10.0, 100.0])))
    assert isinstance(out, rc.ExposureLog10Display)


# --------------------------------------------------------------------------
# CCRS retirement -- no weighted-sum-across-hazards, no EventMultiplier
# --------------------------------------------------------------------------
def test_no_bucket_weighted_sum_across_hazards_remains():
    """The retired ccrs_calculator.py combined every hazard term into one
    Hazard_i,s via BUCKET_WEIGHTS / water_sub / hazard(). None of that
    combination logic exists in the v3 core."""
    for name in ("BUCKET_WEIGHTS", "WITHIN_WATER_WEIGHTS", "WRI_TOP_THRESHOLD",
                 "water_sub", "hazard", "compute_hazard", "compute_hazard_by_gcm"):
        assert not hasattr(rc, name), f"retired CCRS symbol {name!r} still present"


def test_event_multiplier_not_imported_by_the_core():
    """EventMultiplier may still be *mentioned* in this module's docstring
    (explaining its retirement) but must never be imported or called."""
    assert not hasattr(rc, "event_multiplier")
    assert not hasattr(rc, "EventMultiplier")
    import_lines = [l for l in inspect.getsource(rc).splitlines()
                     if l.strip().startswith(("import ", "from "))]
    assert not any("event_multiplier" in l for l in import_lines)


def test_ccrs_calculator_and_ccrs_report_modules_no_longer_exist():
    with pytest.raises(ModuleNotFoundError):
        __import__("src.index.ccrs_calculator")
    with pytest.raises(ModuleNotFoundError):
        __import__("src.index.ccrs_report")


# --------------------------------------------------------------------------
# Temporal-window assumption -- explicit per-hazard constant
# --------------------------------------------------------------------------
def test_every_hazard_term_declares_a_temporal_window():
    assert set(rc.HAZARD_TEMPORAL_WINDOW) == set(rc.HAZARD_TERMS)
    for term, meta in rc.HAZARD_TEMPORAL_WINDOW.items():
        assert meta["horizon_year"] == 2050
        assert isinstance(meta["is_explicit_30yr_window"], bool)


def test_heat_and_spei_are_the_explicit_30yr_cmip6_window():
    assert rc.HAZARD_TEMPORAL_WINDOW["heat"]["window"] == "2041-2070"
    assert rc.HAZARD_TEMPORAL_WINDOW["heat"]["is_explicit_30yr_window"] is True
    assert rc.HAZARD_TEMPORAL_WINDOW["spei"]["window"] == "2041-2070"
    assert rc.HAZARD_TEMPORAL_WINDOW["spei"]["is_explicit_30yr_window"] is True


def test_water_terms_are_the_aqueduct_point_estimate_not_a_30yr_window():
    for term in ("ws", "sv", "iv"):
        assert rc.HAZARD_TEMPORAL_WINDOW[term]["window"] == "point_estimate_2050"
        assert rc.HAZARD_TEMPORAL_WINDOW[term]["is_explicit_30yr_window"] is False


# --------------------------------------------------------------------------
# Transforms (unchanged from the retired ccrs_calculator.py)
# --------------------------------------------------------------------------
def test_tlin_is_linear_minmax():
    out = rc.transform_term("sv", np.array([0.0, 1.0, 2.0]), 0.0, 2.0)
    np.testing.assert_allclose(out, [0.0, 0.5, 1.0])


def test_tlog_is_log1p_then_minmax():
    raw = np.array([0.0, 3.0])
    out = rc.transform_term("ws", raw, 0.0, 3.0)
    assert out[0] == pytest.approx(0.0)
    assert out[1] == pytest.approx(1.0)


def test_transform_clips_out_of_range_and_handles_degenerate():
    np.testing.assert_allclose(
        rc.transform_term("iv", np.array([-1.0, 5.0]), 0.0, 2.0), [0.0, 1.0]
    )
    np.testing.assert_allclose(
        rc.transform_term("sv", np.array([1.0, 2.0]), 3.0, 3.0), [0.0, 0.0]
    )


def test_frozen_bounds_structure_unchanged_from_retired_module():
    fb = rc.FROZEN_BOUNDS
    assert set(fb) == {"ws", "sv", "iv", "heat", "spei"}
    for t in ("ws", "sv", "iv"):
        lo, hi = fb[t]
        assert lo <= hi
    assert set(fb["heat"]) == set(rc.configured_models())
    assert set(fb["spei"]) == set(rc.configured_models())


def _rasters_present() -> bool:
    try:
        p = rc.raster_path("heat", "Brazil", "opt", rc.configured_models()[0])
        q = rc.raster_path("ws", "Brazil", "opt", rc.configured_models()[0])
        return p.exists() and q.exists()
    except Exception:
        return False


@pytest.mark.skipif(not _rasters_present(), reason="processed rasters absent -- cannot recompute bounds")
def test_frozen_bounds_match_recomputed_from_data():
    """REGRESSION LOCK, carried over unchanged from the retired module. A
    failure here means the data snapshot moved -- investigate before editing
    FROZEN_BOUNDS."""
    live = rc.compute_global_bounds()
    assert rc._bounds_close(live, rc.FROZEN_BOUNDS), (
        f"global bounds drifted from the frozen snapshot {rc.BOUNDS_DATA_SNAPSHOT}.\n"
        f"  frozen:     {rc.FROZEN_BOUNDS}\n  recomputed: {live}"
    )


# --------------------------------------------------------------------------
# compute_risk_by_hazard -- end to end with a fake sample, real age_factor join
# --------------------------------------------------------------------------
def test_compute_risk_by_hazard_end_to_end(monkeypatch):
    fake = pd.DataFrame({
        rc.PLANT_UID: ["T-00000"],
        "country": "Testland",
        "plant_name": ["p"],
        "lon": 0.0, "lat": 0.0,
        "capacity_mw": [100.0],
        "commissioning_year": [2000.0],
        "bucket": ["thermal"],
        "water_scenario": "opt", "heat_scenario": "ssp126",
        "ws": [1.0], "sv": [0.5], "iv": [0.5], "heat": [4.0], "spei": [1.0],
    })
    monkeypatch.setattr(rc, "sample_terms", lambda model: fake.copy())
    af = pd.DataFrame({rc.PLANT_UID: ["T-00000"], "age_factor": [1.2]})
    bounds = {
        "ws": (0.0, 1.0), "sv": (0.0, 1.0), "iv": (0.0, 1.0),
        "heat": {"gfdl_esm4": (0.0, 4.0)},
        "spei": {"gfdl_esm4": (0.0, 1.0)},
    }
    out = rc.compute_risk_by_hazard("gfdl_esm4", bounds=bounds, age_factors=af)

    assert set(out["hazard_term"]) == set(rc.HAZARD_TERMS)
    assert len(out) == len(rc.HAZARD_TERMS)   # one row per hazard term, one plant
    ws_row = out[out["hazard_term"] == "ws"].iloc[0]
    assert ws_row["hazard_i_h"] == pytest.approx(1.0)   # ws=1.0 saturates bound [0,1]
    assert ws_row["risk_i_h"] == pytest.approx(1.0 * 100.0 * 1.2)
    # never summed across hazard_term -- each row stands alone
    assert out["risk_i_h"].sum() != out.loc[out["hazard_term"] == "ws", "risk_i_h"].iloc[0]


def test_compute_risk_by_hazard_raises_on_stale_age_factor(monkeypatch):
    fake = pd.DataFrame({
        rc.PLANT_UID: ["T-00000"], "country": "Testland", "plant_name": ["p"],
        "lon": 0.0, "lat": 0.0, "capacity_mw": [100.0], "commissioning_year": [2000.0],
        "bucket": ["thermal"], "water_scenario": "opt", "heat_scenario": "ssp126",
        "ws": [1.0], "sv": [0.5], "iv": [0.5], "heat": [4.0], "spei": [1.0],
    })
    monkeypatch.setattr(rc, "sample_terms", lambda model: fake.copy())
    af_missing = pd.DataFrame({rc.PLANT_UID: ["OTHER-PLANT"], "age_factor": [1.0]})
    bounds = {
        "ws": (0.0, 1.0), "sv": (0.0, 1.0), "iv": (0.0, 1.0),
        "heat": {"gfdl_esm4": (0.0, 4.0)}, "spei": {"gfdl_esm4": (0.0, 1.0)},
    }
    with pytest.raises(ValueError, match="age_factor"):
        rc.compute_risk_by_hazard("gfdl_esm4", bounds=bounds, age_factors=af_missing)
