"""Tests for extreme_wind_processor -- GEAR v3 Phase 2.3.

Covers: the mean-annual-max-gust raw indicator arithmetic, the parametrized
threshold dispatcher (classify_extreme_wind) for both the Wind-bucket Tier 1
IEC constant and the Solar-bucket Tier 3 percentile method, the
WIND_TEMPORAL_WINDOW schema match against
src.index.risk_calculator.HAZARD_TEMPORAL_WINDOW plus its historical-vs-
projected flag, that this hazard is NOT wired into risk_calculator's
HAZARD_TERMS/Risk_i,h yet, and the raster read/normalise/cache pattern shared
with the other processors. Synthetic fixtures only, no CDS data (real-data
checks are skipped, never silently passed, when the raw gust series is
absent).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.index import risk_calculator as rc
from src.processors import extreme_wind_processor as ew
from src.processors.extreme_wind_processor import GridMismatchError


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _hourly_gust(n_years: int, values_per_year: list[np.ndarray], start_year: int = 2000) -> xr.DataArray:
    """Synthetic hourly (time, lat, lon) gust series, one pixel. Each element
    of ``values_per_year`` is the hourly series for that calendar year
    (length = hours in year); years are Jan 1 00:00 onward, non-leap."""
    frames = []
    for i, year_vals in enumerate(values_per_year[:n_years]):
        times = pd.date_range(f"{start_year + i}-01-01", periods=len(year_vals), freq="h")
        frames.append((times, year_vals))
    all_times = np.concatenate([t.values for t, _ in frames])
    all_vals = np.concatenate([v for _, v in frames])
    return xr.DataArray(
        all_vals.reshape(-1, 1, 1), dims=("time", "lat", "lon"),
        coords={"time": all_times, "lat": np.asarray([0.0]), "lon": np.asarray([0.0])},
    )


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
def test_paths_have_no_model_or_scenario_axis():
    assert ew.raw_raster_path("Brazil").name == "extreme_wind_gust_raw_Brazil_1km.tif"
    assert ew.normalized_raster_path("India").name == "extreme_wind_gust_India_1km.tif"
    assert ew.native_raster_path("Portugal").name == "extreme_wind_gust_raw_Portugal_native.tif"


# --------------------------------------------------------------------------
# Raw indicator: mean annual maximum gust
# --------------------------------------------------------------------------
def test_mean_annual_max_gust_averages_yearly_peaks():
    """Year 1 peaks at 20 m/s, year 2 peaks at 30 m/s -> mean annual max
    == 25 m/s, the mean of the two peaks, not any other statistic."""
    year1 = np.full(24 * 10, 5.0)
    year1[100] = 20.0
    year2 = np.full(24 * 10, 5.0)
    year2[50] = 30.0
    gust_da = _hourly_gust(2, [year1, year2])

    out = ew.compute_mean_annual_max_gust(gust_da)
    assert float(out.values[0, 0]) == pytest.approx(25.0, abs=1e-6)


def test_raw_layer_units_and_note_are_threshold_agnostic():
    year1 = np.full(24 * 5, 5.0)
    gust_da = _hourly_gust(1, [year1])
    out = ew.compute_mean_annual_max_gust(gust_da)
    assert out.attrs["units"] == ew.RAW_UNITS
    assert "threshold-agnostic" in out.attrs["note"].lower()
    assert "not yet wired" in out.attrs["note"].lower() or "not wired" in out.attrs["note"].lower()


# --------------------------------------------------------------------------
# Threshold logic as a parameter -- one dispatcher, not two processors
# --------------------------------------------------------------------------
def test_wind_bucket_tier1_fixed_speed_dispatch():
    values = np.array([10.0, 20.0, 25.0, 26.0, 30.0, np.nan])
    result = ew.classify_extreme_wind(values, ew.WIND_BUCKET_THRESHOLD_SPEC)
    assert result["kind"] == "tier1_fixed_speed"
    assert result["threshold_ms"] == ew.IEC_TURBINE_CUTOUT_SPEED_MS
    # 3 of 5 finite values (25, 26, 30) are >= 25.0
    assert result["n_valid"] == 5
    assert result["fraction_exceeding"] == pytest.approx(3 / 5)


def test_solar_bucket_tier3_percentile_dispatch():
    values = np.arange(1, 101, dtype="float64")  # 1..100
    result = ew.classify_extreme_wind(values, ew.SOLAR_BUCKET_THRESHOLD_SPEC)
    assert result["kind"] == "tier3_percentile"
    assert set(result["percentile_cuts_ms"]) == set(ew.SOLAR_GUST_PERCENTILES)
    assert result["percentile_cuts_ms"][95.0] == pytest.approx(np.percentile(values, 95.0))


def test_classify_extreme_wind_rejects_unknown_kind():
    with pytest.raises(ValueError):
        ew.classify_extreme_wind(np.array([1.0, 2.0]), {"kind": "bogus"})


def test_threshold_specs_are_named_constants_not_hardcoded_twice():
    """Both bucket specs carry their own tier and source provenance and are
    distinct objects -- the dispatch is data-driven, not a fork of logic."""
    assert ew.WIND_BUCKET_THRESHOLD_SPEC["tier"] == 1
    assert ew.SOLAR_BUCKET_THRESHOLD_SPEC["tier"] == 3
    assert ew.WIND_BUCKET_THRESHOLD_SPEC["kind"] != ew.SOLAR_BUCKET_THRESHOLD_SPEC["kind"]


def test_nan_never_counted_as_a_valid_observation():
    result_t1 = ew.classify_extreme_wind(np.array([np.nan, np.nan]), ew.WIND_BUCKET_THRESHOLD_SPEC)
    assert result_t1["n_valid"] == 0
    assert np.isnan(result_t1["fraction_exceeding"])

    result_t3 = ew.classify_extreme_wind(np.array([np.nan, np.nan]), ew.SOLAR_BUCKET_THRESHOLD_SPEC)
    assert result_t3["n_valid"] == 0
    assert all(np.isnan(v) for v in result_t3["percentile_cuts_ms"].values())


# --------------------------------------------------------------------------
# Temporal-window constant -- extends the Phase 1 pattern, flags the
# historical-vs-projected asymmetry explicitly
# --------------------------------------------------------------------------
def test_wind_temporal_window_matches_core_schema():
    core_keys = set(next(iter(rc.HAZARD_TEMPORAL_WINDOW.values())))
    assert set(ew.WIND_TEMPORAL_WINDOW) == core_keys


def test_wind_temporal_window_flags_historical_not_projected():
    assert ew.WIND_TEMPORAL_WINDOW_IS_PROJECTED is False
    assert ew.WIND_TEMPORAL_WINDOW["horizon_year"] is None
    assert "1991" in ew.WIND_TEMPORAL_WINDOW["window"]
    assert "reanalysis" in ew.WIND_TEMPORAL_WINDOW["note"].lower()


def test_wind_not_merged_into_the_core_hazard_temporal_window_dict():
    assert "wind" not in rc.HAZARD_TEMPORAL_WINDOW
    assert "wind" not in rc.HAZARD_TERMS


def test_not_wired_into_risk_calculator_hazard_terms_yet():
    assert set(rc.HAZARD_TERMS) == {"ws", "heat", "sv", "iv", "spei"}


# --------------------------------------------------------------------------
# Grid guard (shared with heat_stress_processor / spei_processor / precip)
# --------------------------------------------------------------------------
def test_grid_mismatch_error_is_importable_and_shared():
    assert issubclass(GridMismatchError, Exception)


# --------------------------------------------------------------------------
# Real data sanity (skipped if the raw ERA5 gust series is absent)
# --------------------------------------------------------------------------
def _gust_present() -> bool:
    try:
        from src.downloaders.era5_wind_downloader import BASELINE_YEARS, raw_dir
        p = raw_dir("Brazil", BASELINE_YEARS[0])
        return p.exists() and any(p.glob("*.nc"))
    except Exception:
        return False


@pytest.mark.skipif(not _gust_present(), reason="raw ERA5 gust series absent")
def test_real_data_ensure_raw_raster():
    result = ew.ensure_raw_raster("Brazil")
    assert result["success"]
    assert result["reason"] in ("processed", "cached")
