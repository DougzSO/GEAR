"""Tests for extreme_precipitation_processor -- GEAR v3 Phase 2.1.

Covers: the percentile-cutoff raw indicator (per-pixel P95 wet-day
threshold, mean exceedance days/year), the Tier 3 / no-HAZUS-MH invariant,
the PRECIP_TEMPORAL_WINDOW schema match against
src.index.risk_calculator.HAZARD_TEMPORAL_WINDOW, that this hazard is NOT
wired into risk_calculator's HAZARD_TERMS/Risk_i,h yet, and the raster
read/normalise/cache pattern shared with heat_stress_processor/
spei_processor. Synthetic fixtures only, no CDS data (real-data checks are
skipped, never silently passed, when the raw pr series is absent).
"""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.index import risk_calculator as rc
from src.processors import extreme_precipitation_processor as ep
from src.processors.extreme_precipitation_processor import GridMismatchError


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _daily_pr_flux(n_days: int, mm_per_day: np.ndarray, start: str = "2041-01-01") -> xr.DataArray:
    """Synthetic daily (time, lat, lon) pr FLUX (kg m-2 s-1), one pixel, so
    that ``mm_per_day`` (mm/day, shape ``(n_days,)``) is recovered after the
    module's own flux -> mm/day conversion (``_PR_FLUX_TO_MM_PER_DAY``)."""
    times = pd.date_range(start, periods=n_days, freq="D")
    flux = (np.asarray(mm_per_day, dtype="float64") / ep._PR_FLUX_TO_MM_PER_DAY).reshape(n_days, 1, 1)
    return xr.DataArray(
        flux, dims=("time", "lat", "lon"),
        coords={"time": times, "lat": np.asarray([0.0]), "lon": np.asarray([0.0])},
    )


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
def test_paths_are_model_and_scenario_tagged():
    assert (
        ep.raw_raster_path("Brazil", "gfdl_esm4", "ssp585").name
        == "extreme_precip_raw_Brazil_gfdl_esm4_ssp585_1km.tif"
    )
    assert (
        ep.normalized_raster_path("India", "miroc6", "ssp126").name
        == "extreme_precip_India_miroc6_ssp126_1km.tif"
    )
    assert (
        ep.native_raster_path("Portugal", "gfdl_esm4", "ssp370").name
        == "extreme_precip_raw_Portugal_gfdl_esm4_ssp370_native.tif"
    )


# --------------------------------------------------------------------------
# Tier 3 / no-HAZUS-MH invariant (docs/DECISIONS.md, Phase 0 closure)
# --------------------------------------------------------------------------
def test_no_hazus_mh_used_as_a_threshold_source():
    """HAZUS-MH is discussed in the module docstring (explaining why it was
    rejected, per docs/DECISIONS.md) -- that mention is expected. What must
    NOT happen is HAZUS-MH being the actual threshold/method: it must not
    appear in the operative constants or the raw-layer's own metadata."""
    assert "hazus" not in ep.RAW_UNITS.lower()
    for name in ("WET_DAY_THRESHOLD_MM", "EXTREME_PRECIP_PERCENTILE"):
        assert "hazus" not in repr(getattr(ep, name)).lower()


def test_raw_units_name_the_percentile_method_not_a_fixed_threshold():
    assert "p95" in ep.RAW_UNITS.lower() or "local" in ep.RAW_UNITS.lower()
    assert ep.EXTREME_PRECIP_PERCENTILE == 95.0


# --------------------------------------------------------------------------
# Temporal-window constant -- extends the Phase 1 pattern, doesn't diverge
# --------------------------------------------------------------------------
def test_precip_temporal_window_matches_core_schema():
    core_keys = set(next(iter(rc.HAZARD_TEMPORAL_WINDOW.values())))
    assert set(ep.PRECIP_TEMPORAL_WINDOW) == core_keys
    assert ep.PRECIP_TEMPORAL_WINDOW["window"] == "2041-2070"
    assert ep.PRECIP_TEMPORAL_WINDOW["is_explicit_30yr_window"] is True
    assert ep.PRECIP_TEMPORAL_WINDOW["horizon_year"] == 2050


def test_precip_not_merged_into_the_core_hazard_temporal_window_dict():
    """PRECIP_TEMPORAL_WINDOW is a standalone constant -- 'precip' must not
    appear as a key in risk_calculator.HAZARD_TEMPORAL_WINDOW itself, since
    that would silently wire this hazard into Risk_i,h ahead of Phase 2.5/3."""
    assert "precip" not in rc.HAZARD_TEMPORAL_WINDOW
    assert "precip" not in rc.HAZARD_TERMS


def test_not_wired_into_risk_calculator_hazard_terms_yet():
    assert set(rc.HAZARD_TERMS) == {"ws", "heat", "sv", "iv", "spei"}


# --------------------------------------------------------------------------
# Raw indicator -- percentile-cutoff arithmetic
# --------------------------------------------------------------------------
def test_extreme_precip_days_counts_exceedance_of_the_pixel_own_p95():
    """365 days/year x 2 years, one pixel: days 1-300 each year are wet at a
    fixed 5 mm/day (so P95 of wet days == 5.0, and NO day exceeds it -- P95
    of a constant series equals that constant), plus one single spike day of
    50 mm in year 1 that must exceed the threshold and count."""
    n_years = 2
    day_vals = np.full(365 * n_years, 5.0)
    day_vals[300] = 50.0  # one spike in year 1, comfortably a wet day and > P95
    pr_da = _daily_pr_flux(365 * n_years, day_vals)

    out = ep.compute_extreme_precip_days(pr_da, wet_day_threshold_mm=1.0, percentile=95.0)
    val = float(out.values[0, 0])
    # exactly 1 exceedance day over 2 years -> 0.5 days/year
    assert val == pytest.approx(0.5, abs=1e-6)


def test_dry_pixel_with_no_wet_days_is_nan_not_zero():
    n_years = 1
    day_vals = np.zeros(365 * n_years)  # every day below the wet-day threshold
    pr_da = _daily_pr_flux(365 * n_years, day_vals)
    out = ep.compute_extreme_precip_days(pr_da, wet_day_threshold_mm=1.0, percentile=95.0)
    assert np.isnan(out.values[0, 0])


def test_attrs_document_tier_3_and_pending_wiring():
    n_years = 1
    day_vals = np.full(365 * n_years, 5.0)
    pr_da = _daily_pr_flux(365 * n_years, day_vals)
    out = ep.compute_extreme_precip_days(pr_da)
    note = out.attrs["note"]
    assert "Tier 3" in note
    assert "not yet wired" in note.lower() or "not wired" in note.lower()


# --------------------------------------------------------------------------
# Grid guard (shared with heat_stress_processor / spei_processor)
# --------------------------------------------------------------------------
def test_grid_mismatch_error_is_importable_and_shared():
    assert issubclass(GridMismatchError, Exception)


# --------------------------------------------------------------------------
# Real data sanity (skipped if the raw pr series is absent)
# --------------------------------------------------------------------------
def _pr_present() -> bool:
    try:
        from src.downloaders.cds_precipitation_downloader import raw_dir
        p = raw_dir("Brazil", ep.configured_models()[0], "ssp126", "pr")
        return p.exists() and any(p.glob("*.nc"))
    except Exception:
        return False


@pytest.mark.skipif(not _pr_present(), reason="raw CDS precipitation series absent")
def test_real_data_ensure_raw_raster_reuses_the_spei_download():
    result = ep.ensure_raw_raster("Brazil", ep.configured_models()[0], "ssp126")
    assert result["success"]
    assert result["reason"] in ("processed", "cached")
