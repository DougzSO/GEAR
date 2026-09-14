"""
Extreme Wind hazard layer -- GEAR v3 Phase 2.3
(``docs/rework/GEAR_v3_work_plan.md``).

ERA5 hourly 10 m instantaneous gust (``era5_wind_downloader``), reduced to a
single raw physical raster and normalized on the same unified grid
infrastructure as every other hazard (native ERA5 grid -> nearest-neighbour
resample to the country's fixed 1 km grid via
``cds_tasmax_downloader._resample_to_1km`` -> per-country Min-Max, identical
shared ``GridMismatchError`` guard). See ``era5_wind_downloader`` for why
ERA5 (not CMIP6) and the flagged baseline-period caveat.

--------------------------------------------------------------------------
Two downstream consumers, one raw layer, threshold logic as a parameter
--------------------------------------------------------------------------
Per the v3 methodology (Section 3.1/4) and the Phase 0.4 closure
(``docs/DECISIONS.md``, "Solar Extreme Wind: ERA5 gust percentile is final,
not contingency"), Extreme Wind feeds two buckets with two different, non-
convergent threshold methods on the *same* physical quantity:

- **Wind bucket, Tier 1**: turbine cut-out design speed, a single fixed IEC
  design-class constant (~25 m/s), independent of site or sample.
- **Solar bucket, Tier 3**: percentiles (P75/P90/P95/P99) of the ERA5 gust
  distribution itself -- final, not a placeholder pending a Tier 1 value (no
  defensible absolute structural threshold exists for solar trackers, per
  Phase 0.4).

This module therefore computes ONE raw indicator raster (never two
copy-pasted processors for the two buckets) and exposes the threshold logic
as a parameter: ``WIND_BUCKET_THRESHOLD_SPEC`` / ``SOLAR_BUCKET_THRESHOLD_SPEC``
are named constants passed into the single dispatcher ``classify_extreme_wind``,
which branches on ``threshold_spec["kind"]`` rather than existing as two
separate functions. RiskBand assembly proper (binning a plant's Hazard value
into a labelled band) is Phase 3.2 work, not implemented here; what this
module provides is the raw+normalized raster and the reusable, parametrized
classification arithmetic Phase 3.2 will call.

--------------------------------------------------------------------------
Raw indicator: mean annual maximum gust (m/s), not an exceedance-day count
--------------------------------------------------------------------------
Unlike Extreme Heat/Precipitation (whose raw indicator already bakes in a
threshold -- "days/year exceeding X"), Extreme Wind's two consumers apply
their threshold logic AFTER the raw layer exists and need it in the same
physical unit (m/s) the IEC constant is expressed in. The raw indicator is
therefore the per-pixel MEAN ANNUAL MAXIMUM instantaneous 10 m gust over the
baseline period -- the standard extreme-value characteristic-gust metric in
wind engineering (mean of each calendar year's single peak gust, not a
same-unit days-count). Both consumers' thresholds are applied to this raster
(or its pooled per-country distribution for Solar's percentiles) downstream,
never inside this module's raw-layer computation.

--------------------------------------------------------------------------
Correlation gate: NOT a candidate (confirmed against the methodology draft)
--------------------------------------------------------------------------
Extreme Wind is not run through the Phase 2.5 correlation gate. Methods
Section 2 states explicitly: "Extreme Wind is not part of a single shared
hazard core; it is assigned per bucket per the mechanistic rationale in
Section 3" -- and Section 5's gate is scoped by name to Extreme Precipitation
only (Wildfire's own candidacy was separately deferred for a data-
availability reason unrelated to wind; see ``docs/DECISIONS.md``, "GEAR v3
Phase 2.2: Wildfire deferred"). Extreme Wind is a dedicated hazard for the
Wind/Solar buckets, gated only by the bucket-specific threshold in Section 4,
never by inter-hazard correlation. This module is therefore NOT wired into
any Phase 2.5 gate list.

--------------------------------------------------------------------------
Wired into risk_calculator -- Phase 3 integration closed, 2026-09-14
--------------------------------------------------------------------------
This processor produces the raster layer (+ the standalone classification
utility). ``wind`` is wired into ``src/index/risk_calculator.py``'s
``HAZARD_TERMS``/``Risk_i,h`` computation (``docs/DECISIONS.md``, "GEAR v3
wind Risk_i,h integration: empirical transform result,
PENDING_RISK_I_H_HAZARDS closed"): its empirically-measured pooled skew
(+0.622, right-skewed, ``|skew| > 0.5``) classified it into ``LOG_TERMS``
(``Tlog``/log1p), by the same ``normality_check`` procedure that classified
``precip`` into ``LIN_TERMS`` -- the rule is shared, the outcome is not.
Per-bucket applicable-hazard table membership (H_b) was already closed
earlier (``src/index/hazard_scope.py``, ``WIND_APPLICABLE_BUCKETS``) and is
unaffected by this Risk_i,h wiring. ``WIND_TEMPORAL_WINDOW`` mirrors the
shape of ``src.index.risk_calculator.HAZARD_TEMPORAL_WINDOW`` (same schema
keys, asserted at import time) and IS that module's ``"wind"`` entry
directly (imported there, not copied), matching the pattern already used
for ``extreme_precipitation_processor.PRECIP_TEMPORAL_WINDOW``.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import rioxarray  # noqa: F401 - registers the .rio accessor
import xarray as xr

from src.config import CLIMATE_PROCESSED, COUNTRIES, CRS_TARGET
from src.downloaders import era5_wind_downloader
from src.downloaders.cds_tasmax_downloader import _normalize_longitude, _resample_to_1km
from src.downloaders.era5_wind_downloader import (
    BASELINE_YEARS,
    ERA5_WIND_BASELINE_PERIOD,
    _pick_var,
    open_gust_dataset,
)
from src.downloaders.era5_wind_downloader import raw_dir as era5_raw_dir
from src.processors._common import GridMismatchError  # noqa: F401 - re-exported for callers/tests

logger = logging.getLogger(__name__)

RAW_UNITS = "mean_annual_max_10m_gust_ms"

# --------------------------------------------------------------------------
# Temporal-window constant -- explicit named constant per the standing rule,
# same schema as src.index.risk_calculator.HAZARD_TEMPORAL_WINDOW, NOT
# merged into that dict (see module docstring, "Not yet wired").
#
# WIND_TEMPORAL_WINDOW_IS_PROJECTED = False is deliberately outside the
# schema-matched dict: it is a genuine asymmetry versus every other hazard
# (all of which ARE mid-century projections), not something the shared
# schema has a field for. Flagged in docs/DECISIONS.md as an open item --
# the methodology draft names ERA5 as the source but does not itself specify
# or reconcile this temporal mismatch.
# --------------------------------------------------------------------------
WIND_TEMPORAL_WINDOW = {
    "source": "era5_single_levels_reanalysis",
    "horizon_year": None,
    "window": f"{ERA5_WIND_BASELINE_PERIOD[0][:4]}-{ERA5_WIND_BASELINE_PERIOD[1][:4]}",
    "is_explicit_30yr_window": True,
    "note": "ERA5 HISTORICAL reanalysis baseline (WMO 30-yr climate normal), "
            "NOT a CMIP6-style mid-century projection like every other v3 "
            "hazard -- there is no SSP/GCM axis and no 2050 horizon here. "
            "The specific baseline period is an engineering default pending "
            "author confirmation (docs/DECISIONS.md).",
}
WIND_TEMPORAL_WINDOW_IS_PROJECTED = False

# The expected-keys literal below is intentionally not imported from
# risk_calculator: that module imports THIS one (WIND_TEMPORAL_WINDOW is
# risk_calculator.HAZARD_TEMPORAL_WINDOW's "wind" entry, directly, not a
# copy -- see risk_calculator.py), so importing back would recreate the
# circular dependency the wiring change removed. Mirrors
# extreme_precipitation_processor.PRECIP_TEMPORAL_WINDOW's identical fix.
_TEMPORAL_WINDOW_SCHEMA_KEYS = frozenset({
    "source", "horizon_year", "window", "is_explicit_30yr_window", "note",
})
assert set(WIND_TEMPORAL_WINDOW) == _TEMPORAL_WINDOW_SCHEMA_KEYS, (
    "WIND_TEMPORAL_WINDOW must use the identical schema as every "
    "risk_calculator.HAZARD_TEMPORAL_WINDOW entry -- extend the pattern, "
    "don't diverge from it."
)

# --------------------------------------------------------------------------
# Threshold logic as a parameter -- one dispatcher, two named specs, never
# two copy-pasted processors. See module docstring.
# --------------------------------------------------------------------------
IEC_TURBINE_CUTOUT_SPEED_MS = 25.0  # ~90 km/h, IEC turbine design standard

WIND_BUCKET_THRESHOLD_SPEC = {
    "kind": "tier1_fixed_speed",
    "value_ms": IEC_TURBINE_CUTOUT_SPEED_MS,
    "tier": 1,
    "source": "IEC turbine cut-out design standard (~25 m/s), site-independent",
}

SOLAR_GUST_PERCENTILES = (75.0, 90.0, 95.0, 99.0)

SOLAR_BUCKET_THRESHOLD_SPEC = {
    "kind": "tier3_percentile",
    "percentiles": SOLAR_GUST_PERCENTILES,
    "tier": 3,
    "source": "ERA5 gust percentile method, final per Phase 0.4 closure "
               "(docs/DECISIONS.md) -- not a placeholder pending a Tier 1 value.",
}


def classify_extreme_wind(values: np.ndarray, threshold_spec: dict) -> dict:
    """Single dispatcher for both buckets' threshold logic, branching on
    ``threshold_spec["kind"]`` -- this is the "parameter, not two
    copy-pasted processors" mechanism. ``values`` is any array of raw
    mean-annual-max gust speeds (m/s), typically the pooled per-country raw
    raster or a per-plant sample. NaN is excluded from every statistic, never
    silently treated as 0.

    This does not itself produce a RiskBand label -- Phase 3.2 assembles
    that from whichever result dict this returns.
    """
    finite = np.asarray(values, dtype="float64")
    finite = finite[~np.isnan(finite)]
    kind = threshold_spec["kind"]

    if kind == "tier1_fixed_speed":
        cutoff = float(threshold_spec["value_ms"])
        exceeds = finite >= cutoff
        return {
            "kind": kind,
            "threshold_ms": cutoff,
            "fraction_exceeding": float(exceeds.mean()) if finite.size else float("nan"),
            "n_valid": int(finite.size),
        }

    if kind == "tier3_percentile":
        pcts = threshold_spec["percentiles"]
        cuts = {float(p): float(np.percentile(finite, p)) for p in pcts} if finite.size else {
            float(p): float("nan") for p in pcts
        }
        return {"kind": kind, "percentile_cuts_ms": cuts, "n_valid": int(finite.size)}

    raise ValueError(f"Unknown threshold_spec kind: {kind!r}")


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
def native_raster_path(country: str) -> Path:
    return CLIMATE_PROCESSED / f"extreme_wind_gust_raw_{country}_native.tif"


def raw_raster_path(country: str) -> Path:
    """Path to the raw physical Extreme Wind layer (mean annual maximum 10 m
    gust, m/s), on the 1 km grid. No model/scenario axis -- ERA5 is a single
    reanalysis product, unlike the CMIP6-driven hazards."""
    return CLIMATE_PROCESSED / f"extreme_wind_gust_raw_{country}_1km.tif"


def normalized_raster_path(country: str) -> Path:
    return CLIMATE_PROCESSED / f"extreme_wind_gust_{country}_1km.tif"


# --------------------------------------------------------------------------
# Per-year processing -- download, reduce, delete (disk-footprint fix,
# 2026-09-12; see era5_wind_downloader module docstring, "Disk footprint").
# --------------------------------------------------------------------------
def annual_max_path(country: str, year: int) -> Path:
    """Tiny per-year cache: one 2D (lat, lon) field, the per-pixel maximum
    gust within that single year -- a few MB at most, vs. the ~0.5-1 GB raw
    hourly file it is derived from and immediately replaces."""
    return era5_raw_dir(country, year) / "annual_max.nc"


def _normalize_dims(obj):
    """CDS/cfgrib return ``latitude``/``longitude`` dim names; the rest of
    this module (and ``_normalize_longitude``, ``_resample_to_1km``,
    ``.rio``) uses ``lat``/``lon``, matching every other processor. Renames
    only if present -- a no-op on the synthetic ``(time, lat, lon)``
    fixtures this module's tests use, which are already named ``lat``/
    ``lon``. Works on a ``Dataset`` or a ``DataArray`` alike (``.rename``
    has the same dict-based signature on both)."""
    rename = {d: d[:3] for d in ("latitude", "longitude") if d in obj.dims}
    return obj.rename(rename) if rename else obj


def compute_annual_max_for_year(gust_da: xr.DataArray) -> xr.DataArray:
    """Per-pixel maximum gust within one year's hourly series -- the
    single-year building block ``compute_mean_annual_max_gust`` uses
    internally per calendar year, exposed separately so the per-year
    process-then-delete flow (``ensure_year_annual_max``) can reduce one
    year's file in isolation, without ever loading another year into memory.

    Reduces over every temporal dimension present: ``time``, and ``step``
    for ECMWF forecast-type GRIB responses, where the valid hour is
    ``time + step`` rather than a single flat time axis (this is the actual
    shape of a real CDS ``instantaneous_10m_wind_gust`` response opened via
    cfgrib -- confirmed against the recovered Brazil 1991-2008 files, GEAR
    v3 Phase 3.2 follow-up). The synthetic ``(time, lat, lon)``-only
    fixtures in this module's tests have no ``step`` dimension; ``dim``
    simply omits it in that case, so this is one reduction rule for both
    shapes, not a special case for real data.
    """
    reduce_dims = [d for d in ("time", "step") if d in gust_da.dims]
    return gust_da.max(dim=reduce_dims, skipna=True)


def ensure_year_annual_max(country: str, year: int, overwrite: bool = False) -> dict:
    """Download (if needed) one year's raw ERA5 gust file, reduce it to that
    year's per-pixel maximum, cache the tiny result at ``annual_max_path``,
    and delete the raw hourly payload -- this is the per-year unit the
    disk-footprint fix is built from. ``ensure_all_years_annual_max`` calls
    this once per baseline year instead of ``era5_wind_downloader.
    download_country_baseline``'s keep-everything approach.

    Idempotent: if ``annual_max_path`` already exists and ``overwrite`` is
    ``False``, returns immediately without re-downloading or re-deleting
    anything (there is nothing left to delete -- the raw file for a
    completed year no longer exists by construction).
    """
    out_path = annual_max_path(country, year)
    if out_path.exists() and not overwrite:
        return {"success": True, "path": str(out_path), "reason": "cached"}

    dl_status = era5_wind_downloader._download_raw_year(country, year, overwrite)
    if not dl_status["success"]:
        return {"success": False, "path": None, "reason": dl_status["reason"]}

    raw_files = [Path(f) for f in dl_status["files"]]
    try:
        ds = open_gust_dataset(raw_files)
        ds = _normalize_dims(ds)  # latitude/longitude -> lat/lon BEFORE _normalize_longitude,
        ds = _normalize_longitude(ds)  # which requires ds["lon"] to already exist
        var = _pick_var(ds)
        da = ds[var]
        annual_max = compute_annual_max_for_year(da).astype("float32")
        annual_max.name = "extreme_wind_gust_annual_max"
        annual_max = annual_max.load()  # materialize before closing the source file
        ds.close()

        if set(annual_max.dims) != {"lat", "lon"}:
            # Observed once on real data (Brazil 2012): a degenerate
            # single-scalar reduction instead of the expected 2D grid --
            # root cause not fully identified (the source raw file was
            # already deleted by the time this was noticed, per this
            # function's own design, so it could not be inspected after
            # the fact). Never silently accept a malformed reduction as
            # "processed": raise here so the raw file is NOT deleted and
            # the year is reported as a failure, available for a retry
            # with the raw file still on disk to diagnose if it recurs.
            raise ValueError(
                f"expected a 2D (lat, lon) reduction, got dims={annual_max.dims} "
                f"shape={annual_max.shape} -- refusing to cache or delete the raw file."
            )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "ERA5 gust %s/%d: failed to reduce raw file(s) %s: %s: %s",
            country, year, raw_files, type(exc).__name__, exc,
        )
        return {"success": False, "path": None, "reason": f"reduce_failed: {type(exc).__name__}: {exc}"}

    annual_max.to_netcdf(out_path)

    # The whole point: delete the raw payload now that the tiny reduced
    # artifact is safely on disk. Never delete before the write above
    # succeeds. Includes cfgrib's .idx sidecar (a per-file index cache it
    # writes next to a GRIB source, negligible size but still raw-adjacent
    # debris with no purpose once the source is gone).
    for f in raw_files:
        f.unlink(missing_ok=True)
        for idx in f.parent.glob(f"{f.name}*.idx"):
            idx.unlink(missing_ok=True)
    marker = era5_raw_dir(country, year) / ".downloaded"
    marker.unlink(missing_ok=True)  # annual_max_path's own existence is now the cache signal

    logger.info("ERA5 gust %s/%d: reduced to annual max and raw file deleted.", country, year)
    return {"success": True, "path": str(out_path), "reason": "processed"}


def ensure_all_years_annual_max(country: str, overwrite: bool = False) -> dict:
    """``ensure_year_annual_max`` for every ``BASELINE_YEARS`` entry. Report
    is ``{year: status}``; a failure on one year does not stop the others
    (same convention as the retired ``download_country_baseline``)."""
    return {year: ensure_year_annual_max(country, year, overwrite) for year in BASELINE_YEARS}


# --------------------------------------------------------------------------
# Concurrent acceleration -- the CDS queue, not local CPU/network, is the
# bottleneck for this backlog (confirmed empirically: Portugal and India
# progressed independently and concurrently as two separate OS processes
# with no conflict, GEAR v3 Phase 3.2 follow-up). Threads (not processes)
# are appropriate: cdsapi's client.retrieve() is a blocking network call,
# so the workers spend almost all their time waiting on I/O, not competing
# for CPU. Safe to run concurrently because every (country, year) pair
# already writes to and deletes a fully distinct path -- checked, not
# assumed: raw_dir(country, year) is parametrized by both country AND
# year (never a fixed/shared filename reused across iterations), so is
# annual_max_path, the ``.downloaded`` marker, and cfgrib's per-source
# ``.idx`` sidecar. No two (country, year) tasks ever touch the same file.
# --------------------------------------------------------------------------
_RATE_LIMIT_MARKERS = ("rate limit", "too many requests", "429", "concurrent", "quota", "throttl")


def ensure_years_concurrent(
    country_years: list[tuple[str, int]], max_workers: int = 3, overwrite: bool = False,
) -> dict:
    """Concurrent variant of ``ensure_year_annual_max`` for accelerating a
    CDS-queue-bound multi-year/multi-country backlog. Runs up to
    ``max_workers`` ``(country, year)`` downloads at once (default/cap 3,
    per the author's instruction); each is fully independent (see module
    note above on distinct paths).

    Backs off rather than retrying aggressively if a CDS response looks
    like a rate-limit/too-many-concurrent-requests error: the in-flight
    concurrency target is halved (floor 1, never fully serial-only unless
    forced there) the first time a failure's reason string matches
    ``_RATE_LIMIT_MARKERS`` (a best-effort substring check -- CDS's exact
    wording for this is not guaranteed, so this is a heuristic, not a
    guaranteed detector). A backed-off year is reported as a normal
    failure in the returned dict, same as any other failure -- it is NOT
    automatically retried within this call; retrying is a separate,
    explicit follow-up call, never a tight loop here.

    Returns ``{(country, year): status}``.
    """
    if max_workers < 1:
        raise ValueError(f"max_workers must be >= 1, got {max_workers}")

    import concurrent.futures

    results: dict[tuple[str, int], dict] = {}
    pending = list(country_years)
    target_workers = max_workers

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures: dict[concurrent.futures.Future, tuple[str, int]] = {}

        def _submit_next() -> None:
            if pending and len(futures) < target_workers:
                country, year = pending.pop(0)
                fut = executor.submit(ensure_year_annual_max, country, year, overwrite)
                futures[fut] = (country, year)

        for _ in range(min(target_workers, len(pending))):
            _submit_next()

        while futures:
            done, _ = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
            for fut in done:
                country_year = futures.pop(fut)
                result = fut.result()
                results[country_year] = result

                if not result["success"]:
                    reason = str(result.get("reason", "")).lower()
                    if any(marker in reason for marker in _RATE_LIMIT_MARKERS) and target_workers > 1:
                        target_workers -= 1
                        logger.warning(
                            "CDS response for %s looks like a rate-limit/concurrent-request "
                            "error (reason: %s) -- backing off, concurrency reduced to %d.",
                            country_year, result["reason"], target_workers,
                        )

                _submit_next()

    return results


# --------------------------------------------------------------------------
# Raw indicator: mean annual maximum gust
# --------------------------------------------------------------------------
def compute_mean_annual_max_gust(gust_da: xr.DataArray) -> xr.DataArray:
    """Per pixel: each calendar year's maximum instantaneous gust, then the
    mean of those annual maxima across the baseline period -- the standard
    characteristic extreme-gust metric. Returns a 2D ``(lat, lon)``
    ``DataArray`` on the native grid of ``gust_da``.

    Deliberately not a days-exceeding-threshold count (contrast with
    ``extreme_precipitation_processor.compute_extreme_precip_days``): the
    threshold comparison is deferred to the two downstream consumers (see
    ``classify_extreme_wind``), so the raw layer must stay in the same
    physical unit (m/s) both thresholds are expressed in.

    Takes a single multi-year-concatenated ``gust_da`` (this module's own
    tests exercise it this way, with synthetic data); the production path
    (``_compute_native``) instead builds the equivalent mean directly from
    the per-year ``annual_max_path`` cache and does not call this function,
    since the whole point of the disk-footprint fix is to never hold more
    than one year's hourly data in memory/on disk at once.
    """
    time_index = gust_da["time"].to_index()
    years = np.asarray(time_index.year)
    unique_years = np.unique(years)

    annual_maxima = []
    for year in unique_years:
        year_slice = gust_da.isel(time=np.where(years == year)[0])
        annual_maxima.append(compute_annual_max_for_year(year_slice))

    stacked = xr.concat(annual_maxima, dim="year")
    mean_max = stacked.mean(dim="year", skipna=True).astype("float32")
    mean_max.name = "extreme_wind_gust_raw"
    mean_max.attrs.update(
        method="Mean of each calendar year's maximum instantaneous 10 m gust "
               "over the baseline period (characteristic extreme-gust metric)",
        units=RAW_UNITS,
        n_years=int(len(unique_years)),
        period=f"{ERA5_WIND_BASELINE_PERIOD[0]}/{ERA5_WIND_BASELINE_PERIOD[1]}",
        note=(
            "Threshold-agnostic raw layer -- neither the Wind-bucket Tier 1 "
            "IEC cut-out constant nor the Solar-bucket Tier 3 gust "
            "percentiles are applied here (see WIND_BUCKET_THRESHOLD_SPEC / "
            "SOLAR_BUCKET_THRESHOLD_SPEC / classify_extreme_wind). Not yet "
            "wired into src/index/risk_calculator.py's Risk_i,h -- pending "
            "Phase 3.1. Extreme Wind is NOT a Phase 2.5 correlation-gate "
            "candidate (see module docstring)."
        ),
    )
    return mean_max


def _compute_native(country: str) -> xr.DataArray:
    """Builds the native mean-annual-max-gust raster from the per-year
    ``annual_max_path`` cache -- never bulk-loads every year's raw hourly
    file at once. ``ensure_raw_raster`` guarantees every year is cached
    (downloaded, reduced, raw file deleted) before this runs."""
    missing = [y for y in BASELINE_YEARS if not annual_max_path(country, y).exists()]
    if missing:
        raise FileNotFoundError(
            f"annual_max cache missing for {country}, year(s) {missing} -- "
            f"run ensure_all_years_annual_max({country!r}) first."
        )

    yearly = [xr.open_dataarray(annual_max_path(country, y)) for y in BASELINE_YEARS]
    # Drop every coord except lat/lon (GRIB sources attach scalar coords
    # such as `number`/`surface` that carry no information here but can
    # make xr.concat's default coords="different" check needlessly picky
    # across 30 independently-written files) -- keep only what the raster
    # actually needs.
    yearly = [da.reset_coords(drop=True) if set(da.coords) - {"lat", "lon"} else da for da in yearly]
    stacked = xr.concat(yearly, dim="year", coords="minimal", compat="override")
    mean_max = stacked.mean(dim="year", skipna=True).astype("float32")
    for da in yearly:
        da.close()

    mean_max.name = "extreme_wind_gust_raw"
    mean_max.attrs.update(
        country=country,
        method="Mean of each calendar year's maximum instantaneous 10 m gust "
               "over the baseline period (characteristic extreme-gust metric); "
               "each year downloaded, reduced, and its raw file deleted one "
               "at a time (disk-footprint fix, 2026-09-12) rather than all "
               "years held on disk simultaneously.",
        units=RAW_UNITS,
        n_years=int(len(BASELINE_YEARS)),
        period=f"{ERA5_WIND_BASELINE_PERIOD[0]}/{ERA5_WIND_BASELINE_PERIOD[1]}",
        note=(
            "Threshold-agnostic raw layer -- neither the Wind-bucket Tier 1 "
            "IEC cut-out constant nor the Solar-bucket Tier 3 gust "
            "percentiles are applied here (see WIND_BUCKET_THRESHOLD_SPEC / "
            "SOLAR_BUCKET_THRESHOLD_SPEC / classify_extreme_wind). Not yet "
            "wired into src/index/risk_calculator.py's Risk_i,h -- pending "
            "Phase 3.1. Extreme Wind is NOT a Phase 2.5 correlation-gate "
            "candidate (see module docstring)."
        ),
    )
    return mean_max


# --------------------------------------------------------------------------
# Raw layer -- compute once, cache to disk
# --------------------------------------------------------------------------
def ensure_raw_raster(country: str, overwrite: bool = False) -> dict:
    """Ensure every baseline year is downloaded+reduced+deleted (``ensure_
    all_years_annual_max``, one year on disk at a time), then compute and
    write the native + 1 km raw Extreme Wind raster for one country from
    that per-year cache. Idempotent."""
    CLIMATE_PROCESSED.mkdir(parents=True, exist_ok=True)
    native_path = native_raster_path(country)
    raw_path = raw_raster_path(country)

    if raw_path.exists() and not overwrite:
        logger.info("%s: extreme-wind raw raster cached, skipping.", country)
        return {"success": True, "path": str(raw_path), "reason": "cached"}

    year_reports = ensure_all_years_annual_max(country, overwrite=overwrite)
    failed_years = {y: r for y, r in year_reports.items() if not r["success"]}
    if failed_years:
        logger.error("%s: %d year(s) failed to download/reduce: %s", country, len(failed_years), failed_years)
        return {"success": False, "path": None, "reason": f"missing_years: {failed_years}"}

    try:
        native = _compute_native(country)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return {"success": False, "path": None, "reason": f"missing_dependency: {exc}"}

    native = native.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    native = native.rio.write_crs(CRS_TARGET)
    native.rio.to_raster(native_path)

    resampled = _resample_to_1km(native, country)
    resampled.rio.to_raster(raw_path)
    logger.info(
        "%s: native %s %s, raw 1km %s %s",
        country, native_path.name, tuple(native.shape), raw_path.name, tuple(resampled.shape),
    )
    return {
        "success": True, "path": str(raw_path), "reason": "processed",
        "native_path": str(native_path), "shape": list(resampled.shape),
    }


# --------------------------------------------------------------------------
# Min-Max normalisation (per-country, single product -- no model/scenario pool)
# --------------------------------------------------------------------------
def _load_raw_raster(country: str) -> xr.DataArray:
    path = raw_raster_path(country)
    if not path.exists():
        raise FileNotFoundError(
            f"Extreme-wind raw raster not found: {path}. Run ensure_raw_raster "
            f"(or process_all_countries) first."
        )
    da = rioxarray.open_rasterio(path)
    return da.isel(band=0) if "band" in da.dims else da


def compute_country_minmax(country: str, da: xr.DataArray | None = None) -> tuple[float, float]:
    """Per-country Min-Max domain over the single ERA5 raster -- no
    model/scenario pooling axis exists for this hazard, unlike the
    CMIP6-driven layers."""
    if da is None:
        da = _load_raw_raster(country)
    values = np.asarray(da.values, dtype="float64").ravel()
    finite = values[~np.isnan(values)]
    country_min, country_max = float(finite.min()), float(finite.max())
    logger.info(
        "%s: normalisation domain (single ERA5 product, per country): "
        "min=%.6g max=%.6g (n=%d).",
        country, country_min, country_max, len(finite),
    )
    return country_min, country_max


def normalize_country(
    country: str, country_min: float, country_max: float, da: xr.DataArray | None = None,
) -> xr.DataArray:
    """Per-country Min-Max normalisation against the shared country domain.
    NaN at the source raster's edges propagates, never becomes 0."""
    if da is None:
        da = _load_raw_raster(country)
    values = da.values.astype("float64")

    span = country_max - country_min
    if span <= 0:
        normalized = np.where(np.isnan(values), np.nan, 0.0).astype("float32")
    else:
        normalized = np.clip((values - country_min) / span, 0.0, 1.0).astype("float32")

    out = xr.DataArray(
        normalized, dims=da.dims, coords=da.coords, name="extreme_wind_normalized",
    ).rio.write_crs(da.rio.crs)
    out.attrs.update(
        source="ERA5 reanalysis-era5-single-levels, instantaneous_10m_wind_gust, "
               "mean annual maximum, 1 km grid",
        normalization="per-country Min-Max (single ERA5 product, no "
                      "model/scenario pooling axis)",
        country=country,
        country_min=country_min,
        country_max=country_max,
        note="0 = least extreme-wind-prone cell observed in this country; "
             "1 = most. Not comparable in absolute terms across countries. "
             "NaN = outside the country boundary (preserved from source). "
             "This normalized layer is a within-country diagnostic only -- "
             "the Wind/Solar bucket threshold logic (Tier 1 IEC cut-out / "
             "Tier 3 gust percentile) is applied to the RAW layer, never to "
             "this normalized one.",
    )
    return out


def process_country(country: str, overwrite: bool = False) -> dict:
    """Ensure the raw raster, then normalise and write the Extreme Wind
    layer for one country."""
    raw_status = ensure_raw_raster(country, overwrite=overwrite)
    if not raw_status["success"]:
        return {"success": False, "raw": raw_status}

    CLIMATE_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = normalized_raster_path(country)
    raw_meta = {"raw_path": raw_status["path"], "raw_kind": "computed", "raw_units": RAW_UNITS}

    if out_path.exists() and not overwrite:
        logger.info("%s: extreme wind already processed, skipping.", country)
        return {"success": True, "path": str(out_path), "reason": "cached", **raw_meta}

    da = _load_raw_raster(country)
    country_min, country_max = compute_country_minmax(country, da=da)
    da_norm = normalize_country(country, country_min, country_max, da=da)
    da_norm.rio.to_raster(out_path)

    valid = da_norm.values[~np.isnan(da_norm.values)]
    if len(valid):
        logger.info(
            "%s: saved %s - %s, %d valid px, mean=%.3f (raw: %s)",
            country, out_path.name, da_norm.shape, len(valid), float(valid.mean()), raw_status["path"],
        )
    else:
        logger.warning("%s: saved %s but 0 valid pixels (all NaN).", country, out_path.name)

    return {
        "success": True, "path": str(out_path), "reason": "processed",
        "shape": list(da_norm.shape),
        "country_min": country_min, "country_max": country_max,
        **raw_meta,
    }


def process_all_countries(countries: list[str] | None = None, overwrite: bool = False) -> dict:
    countries = countries or COUNTRIES
    report = {"normalization_domain": "per_country_single_era5_product", "countries": {}}
    for country in countries:
        report["countries"][country] = process_country(country, overwrite=overwrite)
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--countries", nargs="+", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    result = process_all_countries(countries=args.countries, overwrite=args.overwrite)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    ok = all(c.get("success", False) for c in result["countries"].values())
    sys.exit(0 if ok else 1)
