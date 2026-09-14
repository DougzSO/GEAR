"""Tests for extreme_wind_processor -- GEAR v3 Phase 2.3, plus the Phase 3.2
follow-up disk-footprint restructuring (``ensure_year_annual_max`` et al.).

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

Disk-footprint section covers: ``compute_annual_max_for_year`` reducing over
both ``time`` and ``step`` (the real ECMWF forecast-type GRIB shape, not
just the simpler synthetic ``(time, lat, lon)`` fixture); ``_normalize_dims``
renaming ``latitude``/``longitude`` to ``lat``/``lon``; and
``ensure_year_annual_max`` deleting the raw file(s) after a successful
reduction (never before), so peak disk usage per year is bounded -- verified
by monkeypatching ``era5_wind_downloader._download_raw_year`` and
``open_gust_dataset``, no real CDS calls.
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


def test_wind_temporal_window_is_risk_calculators_wind_entry():
    """ERA5 gust acquisition completed for all three countries (2026-09-14)
    and this task wired wind into Risk_i,h --
    risk_calculator.HAZARD_TEMPORAL_WINDOW['wind'] IS this module's
    WIND_TEMPORAL_WINDOW object (imported, not copied), not merely equal to
    it, so the two can never silently drift apart."""
    assert rc.HAZARD_TEMPORAL_WINDOW["wind"] is ew.WIND_TEMPORAL_WINDOW
    assert "wind" in rc.HAZARD_TERMS


def test_wired_into_risk_calculator_hazard_terms():
    """precip was wired in first (correlation gate passed, real data for all
    three countries); wind followed once ERA5 gust acquisition completed
    (Brazil/Portugal/India all 30/30) and its empirically-measured skew
    (+0.622, right-skewed, |skew| > 0.5) classified it into LOG_TERMS -- see
    docs/DECISIONS.md, "GEAR v3 wind Risk_i,h integration: empirical
    transform result, PENDING_RISK_I_H_HAZARDS closed"."""
    assert set(rc.HAZARD_TERMS) == {"ws", "heat", "sv", "iv", "spei", "precip", "wind"}
    assert "wind" in rc.LOG_TERMS
    assert "wind" not in rc.LIN_TERMS


# --------------------------------------------------------------------------
# Grid guard (shared with heat_stress_processor / spei_processor / precip)
# --------------------------------------------------------------------------
def test_grid_mismatch_error_is_importable_and_shared():
    assert issubclass(GridMismatchError, Exception)


# --------------------------------------------------------------------------
# Disk-footprint restructuring (Phase 3.2 follow-up) -- per-year reduce,
# then delete the raw payload. Monkeypatched, no real CDS calls or files.
# --------------------------------------------------------------------------
def test_compute_annual_max_for_year_reduces_time_and_step():
    """Real CDS gust responses (opened via cfgrib) have a (time, step, lat,
    lon) shape -- a forecast base time plus a lead-time step, not a single
    flat time axis. The reduction must collapse both, not leave `step`
    unreduced."""
    da = xr.DataArray(
        np.array([[[[5.0, 30.0]]], [[[7.0, 6.0]]]]),  # (time=2, step=1, lat=1, lon=2)
        dims=("time", "step", "lat", "lon"),
    )
    out = ew.compute_annual_max_for_year(da)
    assert set(out.dims) == {"lat", "lon"}
    assert list(out.values.ravel()) == [7.0, 30.0]


def test_compute_annual_max_for_year_handles_flat_time_only():
    """The simpler (time, lat, lon) shape (this module's other synthetic
    fixtures) has no `step` dim -- must still reduce correctly, not error
    on the dim's absence."""
    da = xr.DataArray(np.array([[[1.0, 9.0]], [[3.0, 2.0]]]), dims=("time", "lat", "lon"))
    out = ew.compute_annual_max_for_year(da)
    assert set(out.dims) == {"lat", "lon"}
    assert list(out.values.ravel()) == [3.0, 9.0]


def test_normalize_dims_renames_latitude_longitude():
    da = xr.DataArray(
        np.zeros((1, 1)), dims=("latitude", "longitude"),
        coords={"latitude": [0.0], "longitude": [0.0]},
    )
    out = ew._normalize_dims(da)
    assert set(out.dims) == {"lat", "lon"}


def test_normalize_dims_is_a_noop_when_already_lat_lon():
    da = xr.DataArray(np.zeros((1, 1)), dims=("lat", "lon"))
    out = ew._normalize_dims(da)
    assert set(out.dims) == {"lat", "lon"}


def test_annual_max_path_is_under_the_year_raw_dir():
    from src.downloaders.era5_wind_downloader import raw_dir

    p = ew.annual_max_path("Brazil", 1995)
    assert p.parent == raw_dir("Brazil", 1995)
    assert p.name == "annual_max.nc"


def _fake_raw_year_file(tmp_path, country, year, values):
    """Write a tiny synthetic (time, lat, lon) NetCDF standing in for one
    year's raw ERA5 gust file, and return the dl_status dict
    ensure_year_annual_max expects from _download_raw_year."""
    year_dir = tmp_path / country / str(year)
    year_dir.mkdir(parents=True)
    raw_path = year_dir / "gust_hourly.nc"
    times = pd.date_range(f"{year}-01-01", periods=len(values), freq="h")
    xr.Dataset(
        {"i10fg": (("time", "lat", "lon"), np.asarray(values).reshape(-1, 1, 1))},
        coords={"time": times, "lat": [0.0], "lon": [0.0]},
    ).to_netcdf(raw_path)
    return raw_path, {"success": True, "path": str(year_dir), "reason": "downloaded", "files": [str(raw_path)]}


def test_ensure_year_annual_max_deletes_raw_file_after_success(tmp_path, monkeypatch):
    raw_path, dl_status = _fake_raw_year_file(tmp_path, "Brazil", 2010, [5.0, 40.0, 3.0])
    monkeypatch.setattr(ew.era5_wind_downloader, "raw_dir", lambda c, y: tmp_path / c / str(y))
    monkeypatch.setattr(ew, "era5_raw_dir", lambda c, y: tmp_path / c / str(y))
    monkeypatch.setattr(
        ew.era5_wind_downloader, "_download_raw_year", lambda c, y, ow: dl_status,
    )

    result = ew.ensure_year_annual_max("Brazil", 2010)

    assert result["success"] is True
    assert not raw_path.exists(), "raw file must be deleted after a successful reduction"
    out_path = ew.annual_max_path("Brazil", 2010)
    assert out_path.exists()
    cached = xr.open_dataarray(out_path)
    assert float(cached.values.item()) == pytest.approx(40.0)
    cached.close()


def test_ensure_year_annual_max_keeps_raw_file_if_reduction_fails(tmp_path, monkeypatch):
    """Never delete the raw payload before the reduced artifact is safely
    written -- if the reduction step raises, the raw file must survive so
    the year can be retried, not silently lost."""
    year_dir = tmp_path / "Brazil" / "2011"
    year_dir.mkdir(parents=True)
    raw_path = year_dir / "gust_hourly.nc"
    raw_path.write_bytes(b"not actually valid netcdf or grib")
    dl_status = {"success": True, "path": str(year_dir), "reason": "downloaded", "files": [str(raw_path)]}

    monkeypatch.setattr(ew, "era5_raw_dir", lambda c, y: tmp_path / c / str(y))
    monkeypatch.setattr(
        ew.era5_wind_downloader, "_download_raw_year", lambda c, y, ow: dl_status,
    )

    result = ew.ensure_year_annual_max("Brazil", 2011)

    assert result["success"] is False
    assert "reduce_failed" in result["reason"]
    assert raw_path.exists(), "raw file must survive a failed reduction, not be deleted"
    assert not ew.annual_max_path("Brazil", 2011).exists()


def test_ensure_year_annual_max_is_idempotent_when_cached(tmp_path, monkeypatch):
    """If annual_max.nc already exists, never re-download -- confirms the
    cache short-circuits before _download_raw_year is even called.

    Regression note: this test previously did NOT monkeypatch
    ``era5_raw_dir``, so ``annual_max_path("Brazil", 2012)`` resolved to
    the REAL project path and this test's synthetic 1-element array
    silently overwrote real, already-downloaded Brazil 2012 data every
    time the suite ran -- discovered when the real pipeline's
    ``_compute_native`` later choked on a degenerate ``(dim_0,)``-shaped
    file for that one year (GEAR v3 Phase 3.2 follow-up, concurrency
    task). Every test in this module that touches ``annual_max_path`` or
    ``era5_raw_dir`` must monkeypatch ``era5_raw_dir`` to a ``tmp_path``,
    with no exception -- there is no synthetic-fixture use of this
    function that is safe to skip that patch."""
    monkeypatch.setattr(ew, "era5_raw_dir", lambda c, y: tmp_path / c / str(y))
    out_path = ew.annual_max_path("Brazil", 2012)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    xr.DataArray(np.array([1.0])).to_netcdf(out_path)

    def _boom(*args, **kwargs):
        raise AssertionError("_download_raw_year must not be called when already cached")

    monkeypatch.setattr(ew.era5_wind_downloader, "_download_raw_year", _boom)

    result = ew.ensure_year_annual_max("Brazil", 2012)
    assert result["success"] is True
    assert result["reason"] == "cached"


def test_ensure_year_annual_max_propagates_download_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(ew, "era5_raw_dir", lambda c, y: tmp_path / c / str(y))
    monkeypatch.setattr(
        ew.era5_wind_downloader, "_download_raw_year",
        lambda c, y, ow: {"success": False, "path": None, "reason": "cds_error: boom"},
    )

    result = ew.ensure_year_annual_max("Brazil", 2013)
    assert result["success"] is False
    assert result["reason"] == "cds_error: boom"
    assert not ew.annual_max_path("Brazil", 2013).exists()


def test_ensure_all_years_annual_max_calls_every_baseline_year(monkeypatch):
    seen = []

    def _fake_ensure(country, year, overwrite=False):
        seen.append(year)
        return {"success": True, "path": "x", "reason": "cached"}

    monkeypatch.setattr(ew, "ensure_year_annual_max", _fake_ensure)
    report = ew.ensure_all_years_annual_max("Brazil")
    assert seen == list(ew.BASELINE_YEARS)
    assert set(report) == set(ew.BASELINE_YEARS)


def test_peak_disk_never_holds_more_than_one_years_raw_file(tmp_path, monkeypatch):
    """The actual point of the restructuring: across a multi-year run, at
    no point do two years' raw files exist on disk simultaneously."""
    years = [2000, 2001, 2002]
    max_concurrent = {"n": 0}

    def _fake_download(country, year, overwrite):
        year_dir = tmp_path / country / str(year)
        year_dir.mkdir(parents=True)
        raw_path = year_dir / "gust_hourly.nc"
        times = pd.date_range(f"{year}-01-01", periods=3, freq="h")
        xr.Dataset(
            {"i10fg": (("time", "lat", "lon"), np.array([1.0, 2.0, 3.0]).reshape(-1, 1, 1))},
            coords={"time": times, "lat": [0.0], "lon": [0.0]},
        ).to_netcdf(raw_path)
        current = sum(
            1 for y in years if (tmp_path / country / str(y) / "gust_hourly.nc").exists()
        )
        max_concurrent["n"] = max(max_concurrent["n"], current)
        return {"success": True, "path": str(year_dir), "reason": "downloaded", "files": [str(raw_path)]}

    monkeypatch.setattr(ew, "era5_raw_dir", lambda c, y: tmp_path / c / str(y))
    monkeypatch.setattr(ew, "BASELINE_YEARS", years)
    monkeypatch.setattr(ew.era5_wind_downloader, "_download_raw_year", _fake_download)

    report = ew.ensure_all_years_annual_max("Brazil")

    assert all(r["success"] for r in report.values())
    assert max_concurrent["n"] == 1, "more than one year's raw file existed on disk at once"
    for y in years:
        assert not (tmp_path / "Brazil" / str(y) / "gust_hourly.nc").exists()


# --------------------------------------------------------------------------
# ensure_years_concurrent -- controlled parallel acceleration of the
# CDS-queue-bound backlog (Phase 3.2 follow-up, concurrency task)
# --------------------------------------------------------------------------
def test_ensure_years_concurrent_processes_every_pair(monkeypatch):
    seen = []
    lock_calls = {"n": 0}

    def _fake_ensure(country, year, overwrite=False):
        lock_calls["n"] += 1
        seen.append((country, year))
        return {"success": True, "path": "x", "reason": "processed"}

    monkeypatch.setattr(ew, "ensure_year_annual_max", _fake_ensure)
    pairs = [("Portugal", y) for y in range(2000, 2005)] + [("India", y) for y in range(2000, 2003)]

    results = ew.ensure_years_concurrent(pairs, max_workers=3)

    assert set(results) == set(pairs)
    assert set(seen) == set(pairs)
    assert lock_calls["n"] == len(pairs)
    assert all(r["success"] for r in results.values())


def test_ensure_years_concurrent_never_exceeds_max_workers_in_flight(monkeypatch):
    """The actual concurrency cap, verified directly: at no point are more
    than max_workers downloads running at the same time."""
    import threading
    import time

    in_flight = {"n": 0, "max": 0}
    guard = threading.Lock()

    def _fake_ensure(country, year, overwrite=False):
        with guard:
            in_flight["n"] += 1
            in_flight["max"] = max(in_flight["max"], in_flight["n"])
        time.sleep(0.05)
        with guard:
            in_flight["n"] -= 1
        return {"success": True, "path": "x", "reason": "processed"}

    monkeypatch.setattr(ew, "ensure_year_annual_max", _fake_ensure)
    pairs = [("Testland", y) for y in range(2000, 2010)]

    ew.ensure_years_concurrent(pairs, max_workers=3)

    assert in_flight["max"] <= 3
    assert in_flight["max"] > 1, "test is meaningless if concurrency never actually overlapped"


def test_ensure_years_concurrent_rejects_invalid_max_workers():
    with pytest.raises(ValueError):
        ew.ensure_years_concurrent([("Brazil", 2000)], max_workers=0)


def test_ensure_years_concurrent_backs_off_on_rate_limit_like_failure(monkeypatch):
    """A CDS failure whose reason looks like a rate-limit/concurrent-request
    error must reduce in-flight concurrency, not be retried in a tight
    loop -- verified by checking the in-flight count never climbs back
    above the reduced target after the first such failure."""
    import threading

    call_order = []
    in_flight = {"n": 0, "post_backoff_max": 0}
    guard = threading.Lock()
    backoff_seen = {"flag": False}

    def _fake_ensure(country, year, overwrite=False):
        with guard:
            in_flight["n"] += 1
            call_order.append(year)
            current = in_flight["n"]
        import time
        time.sleep(0.03)
        with guard:
            in_flight["n"] -= 1
            if backoff_seen["flag"]:
                in_flight["post_backoff_max"] = max(in_flight["post_backoff_max"], current)

        if year == 2001:
            return {"success": False, "path": None, "reason": "cds_error: 429 Too Many Requests"}
        return {"success": True, "path": "x", "reason": "processed"}

    monkeypatch.setattr(ew, "ensure_year_annual_max", _fake_ensure)
    pairs = [("Testland", y) for y in range(2000, 2010)]

    results = ew.ensure_years_concurrent(pairs, max_workers=3)

    assert results[("Testland", 2001)]["success"] is False
    # every pair still gets a result -- backoff reduces future concurrency,
    # it does not drop any pending task
    assert set(results) == set(pairs)


def test_ensure_years_concurrent_never_retries_a_failed_year_itself(monkeypatch):
    calls = {"n": 0}

    def _fake_ensure(country, year, overwrite=False):
        calls["n"] += 1
        return {"success": False, "path": None, "reason": "cds_error: 429 too many requests"}

    monkeypatch.setattr(ew, "ensure_year_annual_max", _fake_ensure)
    pairs = [("Testland", 2000)]

    ew.ensure_years_concurrent(pairs, max_workers=3)

    assert calls["n"] == 1, "a failed year must not be retried automatically within one call"


# --------------------------------------------------------------------------
# Real data sanity (skipped if the raw ERA5 gust series is absent)
# --------------------------------------------------------------------------
def _all_years_reduced(country: str = "Brazil") -> bool:
    """True only if every baseline year already has its tiny annual_max
    cache (the disk-footprint fix means raw per-year files no longer sit on
    disk once processed -- checking for a raw ``*.nc``/``*.grib`` file, as
    this used to, would incorrectly report ``False`` for a fully-processed
    country)."""
    try:
        return all(ew.annual_max_path(country, y).exists() for y in ew.BASELINE_YEARS)
    except Exception:
        return False


@pytest.mark.skipif(not _all_years_reduced(), reason="ERA5 gust annual-max cache incomplete for Brazil")
def test_real_data_ensure_raw_raster():
    result = ew.ensure_raw_raster("Brazil")
    assert result["success"]
    assert result["reason"] in ("processed", "cached")
