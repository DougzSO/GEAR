"""Tests for src/index/ccrs_calculator — the CCRS Hazard term.

Covers: the closed per-bucket water/heat weights and how they are applied
(one case per bucket), the frozen global-bounds regression lock, the
GFDL-ESM4 / MIROC6 separation (separate fields, never blended), and the
exclusion of ``wd`` from every calculation.

Pure-function and monkeypatched tests run without touching disk. The
frozen-bounds regression test reads the processed rasters and is skipped
(never silently passed) when they are absent.
"""

import numpy as np
import pandas as pd
import pytest

from src.index import ccrs_calculator as cc


# --------------------------------------------------------------------------
# Weights — closed values
# --------------------------------------------------------------------------
def test_within_water_weights_match_published_spec():
    w = cc.WITHIN_WATER_WEIGHTS
    assert set(w) == {"ws", "sv", "iv"}          # no wd
    assert w["ws"] == pytest.approx(0.4164, abs=5e-5)
    assert w["sv"] == pytest.approx(0.2505, abs=5e-5)
    assert w["iv"] == pytest.approx(0.3331, abs=5e-5)
    assert sum(w.values()) == pytest.approx(1.0)


def test_bucket_weights_are_the_closed_matrix():
    assert cc.BUCKET_WEIGHTS == {
        "hydro":   {"water": 1.00, "heat": 0.00},
        "thermal": {"water": 0.75, "heat": 0.25},
        "wind":    {"water": 0.00, "heat": 1.00},
        "solar":   {"water": 0.00, "heat": 1.00},
    }
    for w in cc.BUCKET_WEIGHTS.values():
        assert w["water"] + w["heat"] == pytest.approx(1.0)


# --------------------------------------------------------------------------
# Transforms
# --------------------------------------------------------------------------
def test_tlin_is_linear_minmax():
    out = cc.transform_term("sv", np.array([0.0, 1.0, 2.0]), 0.0, 2.0)
    np.testing.assert_allclose(out, [0.0, 0.5, 1.0])


def test_tlog_is_log1p_then_minmax():
    raw = np.array([0.0, 3.0])
    out = cc.transform_term("ws", raw, 0.0, 3.0)
    # midpoint in log space, not linear space
    mid = cc.transform_term("ws", np.array([np.expm1(np.log1p(3.0) / 2)]), 0.0, 3.0)
    assert out[0] == pytest.approx(0.0)
    assert out[1] == pytest.approx(1.0)
    assert mid[0] == pytest.approx(0.5, abs=1e-6)


def test_transform_clips_out_of_range_and_handles_degenerate():
    np.testing.assert_allclose(
        cc.transform_term("iv", np.array([-1.0, 5.0]), 0.0, 2.0), [0.0, 1.0]
    )
    np.testing.assert_allclose(
        cc.transform_term("sv", np.array([1.0, 2.0]), 3.0, 3.0), [0.0, 0.0]
    )


# --------------------------------------------------------------------------
# 1. One case per bucket — weights applied correctly
# --------------------------------------------------------------------------
def test_hazard_per_bucket_weight_application():
    # transformed inputs, hand-picked
    water_sub_val = np.full(4, 0.40)
    t_heat = np.full(4, 0.80)
    buckets = np.array(["hydro", "thermal", "wind", "solar"], dtype=object)

    haz = cc.hazard(buckets, water_sub_val, t_heat)

    assert haz[0] == pytest.approx(1.00 * 0.40 + 0.00 * 0.80)   # hydro  -> 0.40
    assert haz[1] == pytest.approx(0.75 * 0.40 + 0.25 * 0.80)   # thermal-> 0.50
    assert haz[2] == pytest.approx(0.00 * 0.40 + 1.00 * 0.80)   # wind   -> 0.80
    assert haz[3] == pytest.approx(0.00 * 0.40 + 1.00 * 0.80)   # solar  -> 0.80


def test_wind_solar_hazard_is_heat_only_even_when_water_is_nan():
    haz = cc.hazard(
        np.array(["wind", "solar"], dtype=object),
        np.array([np.nan, np.nan]),      # entire water side missing
        np.array([0.3, 0.6]),
    )
    np.testing.assert_allclose(haz, [0.3, 0.6])


def test_hydro_hazard_is_water_only_even_when_heat_is_nan():
    haz = cc.hazard(
        np.array(["hydro"], dtype=object),
        np.array([0.42]),
        np.array([np.nan]),              # heat missing, weight 0 -> ignored
    )
    assert haz[0] == pytest.approx(0.42)


def test_thermal_hazard_propagates_nan_on_a_weighted_side():
    haz = cc.hazard(
        np.array(["thermal", "thermal"], dtype=object),
        np.array([0.4, np.nan]),
        np.array([np.nan, 0.5]),
    )
    assert np.isnan(haz).all()           # both sides weighted > 0 for thermal


def test_compute_hazard_end_to_end_per_bucket(monkeypatch):
    """compute_hazard: raw sample -> transform with given bounds -> weighted
    Hazard, one plant per bucket."""
    fake = pd.DataFrame({
        "country": "Testland",
        "plant_name": ["h", "t", "w", "s", "nobucket"],
        "lon": 0.0, "lat": 0.0,
        "capacity_mw": [10.0, 20.0, 30.0, 40.0, 50.0],
        "commissioning_year": [2000.0, 2000.0, 2000.0, np.nan, 2000.0],
        "bucket": ["hydro", "thermal", "wind", "solar", pd.NA],
        "water_scenario": "opt", "heat_scenario": "ssp126",
        "ws": [1.0, 1.0, 1.0, 1.0, 1.0],
        "sv": [0.5, 0.5, 0.5, 0.5, 0.5],
        "iv": [0.5, 0.5, 0.5, 0.5, 0.5],
        "heat": [4.0, 4.0, 4.0, 4.0, 4.0],
    })
    monkeypatch.setattr(cc, "sample_terms", lambda model: fake.copy())
    bounds = {
        "ws": (0.0, 1.0), "sv": (0.0, 1.0), "iv": (0.0, 1.0),
        "heat": {"gfdl_esm4": (0.0, 4.0)},
    }
    out = cc.compute_hazard("gfdl_esm4", bounds=bounds)

    assert list(out["bucket"]) == ["hydro", "thermal", "wind", "solar"]  # NA dropped
    t_ws = np.clip(np.log1p(1.0) / np.log1p(1.0), 0, 1)   # 1.0
    t_heat = np.clip(np.log1p(4.0) / np.log1p(4.0), 0, 1)  # 1.0
    w_sub = 0.4164 * t_ws + 0.2505 * 0.5 + 0.3331 * 0.5
    by_bucket = dict(zip(out["bucket"], out["hazard"]))
    assert by_bucket["hydro"] == pytest.approx(w_sub, abs=1e-4)
    assert by_bucket["thermal"] == pytest.approx(0.75 * w_sub + 0.25 * t_heat, abs=1e-4)
    assert by_bucket["wind"] == pytest.approx(t_heat, abs=1e-4)
    assert by_bucket["solar"] == pytest.approx(t_heat, abs=1e-4)


# --------------------------------------------------------------------------
# 2. Frozen global-bounds regression lock
# --------------------------------------------------------------------------
def test_frozen_bounds_structure():
    fb = cc.FROZEN_BOUNDS
    assert set(fb) == {"ws", "sv", "iv", "heat"}
    for t in ("ws", "sv", "iv"):
        lo, hi = fb[t]
        assert lo <= hi
    assert set(fb["heat"]) == set(cc.configured_models())


def _rasters_present() -> bool:
    try:
        p = cc.raster_path("heat", "Brazil", "opt", cc.configured_models()[0])
        q = cc.raster_path("ws", "Brazil", "opt", cc.configured_models()[0])
        return p.exists() and q.exists()
    except Exception:
        return False


@pytest.mark.skipif(not _rasters_present(), reason="processed rasters absent — cannot recompute bounds")
def test_frozen_bounds_match_recomputed_from_data():
    """REGRESSION LOCK. Recomputes the global Min-Max bounds from the rasters
    on disk and compares them to FROZEN_BOUNDS.

    A failure here is NOT resolved by copying the recomputed numbers into
    FROZEN_BOUNDS. It means the data snapshot moved (a raster was
    reprocessed, a country or scenario was added/removed). Investigate the
    cause first; only then update FROZEN_BOUNDS + BOUNDS_DATA_SNAPSHOT
    deliberately, recording the before/after numbers in the commit. Never let
    the test recompute and accept silently.
    """
    live = cc.compute_global_bounds()
    assert cc._bounds_close(live, cc.FROZEN_BOUNDS), (
        f"global bounds drifted from the frozen snapshot {cc.BOUNDS_DATA_SNAPSHOT}.\n"
        f"  frozen:     {cc.FROZEN_BOUNDS}\n"
        f"  recomputed: {live}\n"
        "Manual review required — see this test's docstring."
    )


def test_bounds_close_detects_drift():
    base = {"ws": (0.0, 1.0), "sv": (0.0, 1.0), "iv": (0.0, 1.0),
            "heat": {"gfdl_esm4": (0.0, 10.0), "miroc6": (0.0, 20.0)}}
    assert cc._bounds_close(base, dict(base))
    drifted = {**base, "heat": {"gfdl_esm4": (0.0, 10.5), "miroc6": (0.0, 20.0)}}
    assert not cc._bounds_close(base, drifted)
    assert not cc._bounds_close(base, {**base, "ws": (0.0, 1.01)})


# --------------------------------------------------------------------------
# 3. GFDL-ESM4 vs MIROC6 — separate fields, never blended
# --------------------------------------------------------------------------
def test_compute_hazard_by_gcm_keeps_models_in_separate_columns(monkeypatch):
    key = ["country", "plant_name", "water_scenario", "heat_scenario", "bucket",
           "capacity_mw", "commissioning_year"]

    def fake_compute_hazard(model, bounds=None):
        val = {"gfdl_esm4": 0.10, "miroc6": 0.90}[model]
        base = pd.DataFrame({
            "country": ["A", "A"], "plant_name": ["p1", "p2"],
            "water_scenario": ["opt", "opt"], "heat_scenario": ["ssp126", "ssp126"],
            "bucket": ["wind", "solar"], "capacity_mw": [1.0, 2.0],
            "commissioning_year": [2001.0, 2002.0],
        })
        base["hazard"] = val
        return base

    monkeypatch.setattr(cc, "compute_hazard", fake_compute_hazard)
    wide = cc.compute_hazard_by_gcm(models=["gfdl_esm4", "miroc6"])

    assert "hazard_gfdl_esm4" in wide.columns
    assert "hazard_miroc6" in wide.columns
    assert "hazard" not in wide.columns                      # no blended column
    np.testing.assert_allclose(wide["hazard_gfdl_esm4"], [0.10, 0.10])
    np.testing.assert_allclose(wide["hazard_miroc6"], [0.90, 0.90])
    # the two GCMs are never averaged: no column equals their mean
    blend = (wide["hazard_gfdl_esm4"] + wide["hazard_miroc6"]) / 2
    assert not any(np.allclose(wide[c], blend) for c in wide.columns if c.startswith("hazard_"))


@pytest.mark.skipif(not _rasters_present(), reason="processed rasters absent")
def test_real_gcm_columns_differ_and_are_not_a_blend():
    wide = cc.compute_hazard_by_gcm()
    g, m = wide["hazard_gfdl_esm4"], wide["hazard_miroc6"]
    both = wide.dropna(subset=["hazard_gfdl_esm4", "hazard_miroc6"])
    assert (both["hazard_gfdl_esm4"] != both["hazard_miroc6"]).any()
    # MIROC6 runs hotter for wind/solar (heat-only buckets) — sanity that the
    # columns are genuinely per-model, not a shared value
    ws = both[both["bucket"].isin(["wind", "solar"])]
    assert ws["hazard_miroc6"].mean() > ws["hazard_gfdl_esm4"].mean()


# --------------------------------------------------------------------------
# 4. wd (water depletion) is excluded from every calculation
# --------------------------------------------------------------------------
def test_wd_is_not_a_hazard_term():
    assert "wd" not in cc.HAZARD_TERMS
    assert "wd" in cc.EXCLUDED_INDICATORS
    assert "wd" not in cc.WITHIN_WATER_WEIGHTS
    assert "wd" not in cc.WRI_TOP_THRESHOLD


def test_wd_has_no_raster_path_and_no_transform():
    with pytest.raises(ValueError):
        cc.raster_path("wd", "Brazil", "opt", cc.configured_models()[0])
    with pytest.raises(ValueError):
        cc.transform_term("wd", np.array([1.0]), 0.0, 2.0)


def test_wd_never_appears_in_sampled_or_scored_columns(monkeypatch):
    fake = pd.DataFrame({
        "country": "T", "plant_name": ["a"], "lon": 0.0, "lat": 0.0,
        "capacity_mw": [1.0], "commissioning_year": [2000.0], "bucket": ["thermal"],
        "water_scenario": "opt", "heat_scenario": "ssp126",
        "ws": [1.0], "sv": [0.5], "iv": [0.5], "heat": [4.0],
    })
    monkeypatch.setattr(cc, "sample_terms", lambda model: fake.copy())
    out = cc.compute_hazard(
        "gfdl_esm4",
        bounds={"ws": (0.0, 1.0), "sv": (0.0, 1.0), "iv": (0.0, 1.0),
                "heat": {"gfdl_esm4": (0.0, 4.0)}},
    )
    assert not any("wd" in c for c in out.columns)


# --------------------------------------------------------------------------
# Capacity roll-up guard (V6)
# --------------------------------------------------------------------------
def test_computable_base_requires_commissioning_year():
    df = pd.DataFrame({
        "plant_name": ["a", "b", "c"],
        "commissioning_year": [2000.0, np.nan, 1990.0],
        "capacity_mw": [10.0, 20.0, 30.0],
    })
    base = cc.computable_base(df)
    assert list(base["plant_name"]) == ["a", "c"]
