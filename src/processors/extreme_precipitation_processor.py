"""
Extreme Precipitation hazard layer -- GEAR v3 Phase 2.1
(``docs/rework/GEAR_v3_work_plan.md``).

Reuses the daily ``pr`` series already downloaded by
``cds_precipitation_downloader`` for the SPEI drought term (no new download):
same 2-GCM x 3-scenario x 3-country matrix, same 2041-2070 window, same
common per-country 1 km grid. This module is the second consumer of that
``pr`` series -- ``spei_processor`` reads ``pr`` and ``tas`` together for
Thornthwaite PET; this module reads ``pr`` alone.

--------------------------------------------------------------------------
Tier -- Tier 3 only, HAZUS-MH is NOT a valid threshold source
--------------------------------------------------------------------------
Per the GEAR v3 Phase 0 closure (``docs/DECISIONS.md``, "Extreme
Precipitation downgraded Tier 1 -> Tier 3"): HAZUS-MH's depth-damage curves
are (a) continuous per-occupancy-type functions in feet from finished floor,
not categorical depth cutoffs, and (b) structurally incompatible with this
pipeline's `pr` input regardless -- there is no precipitation-to-inundation-
depth conversion step anywhere in this codebase. HAZUS-MH is therefore not
referenced anywhere in this module, its docstrings, or its outputs. This
hazard is Tier 3 only: a sample-relative percentile-cutoff method, the same
kind of method already used for Extreme Heat (``heat_stress_processor``'s
Tier 3 fallback, `docs/rework/GEAR_v3_methodology_nature_format.md` Section
4) and for Drought (``spei_processor``'s SPEI<=-1.0 frequency).

--------------------------------------------------------------------------
Raw indicator -- percentile-cutoff method (ETCCDI "very wet days" family)
--------------------------------------------------------------------------
Unlike Extreme Heat's raw indicator (a fixed physical threshold, tasmax >
40 C), there is no defensible fixed physical threshold for "extreme" daily
precipitation at Tier 3 (Phase 0 closure). The percentile-cutoff pattern is
applied one level earlier instead: the "extreme" threshold itself is
per-pixel and percentile-derived, not a fixed mm value --

1. A day is a WET_DAY if `pr >= WET_DAY_THRESHOLD_MM` (1 mm/day, the
   standard ETCCDI wet-day convention -- Zhang et al. 2011, "Indices for
   monitoring changes in extremes based on daily temperature and
   precipitation data", WIREs Climate Change 2(6):851-870).
2. Per pixel, `EXTREME_PRECIP_PERCENTILE` (P95) of that pixel's own wet-day
   amounts, over the full 2041-2070 window, is the pixel's local "very wet
   day" threshold -- the same ETCCDI R95p convention, computed per pixel so
   the threshold reflects each location's own rainfall regime (a semi-arid
   and a monsoon pixel do not share one fixed mm cutoff).
3. The raw hazard indicator is the mean days/year, over the window, with
   daily `pr` exceeding that pixel's own P95 threshold -- structurally the
   same "mean days/year exceeding a threshold" shape as Extreme Heat's
   `days_per_year_with_tasmax_gt_40C`, with the threshold itself
   percentile-derived rather than a fixed physical value.

This is the RAW physical indicator only. RiskBand-style classification
thresholds (Methods Section 4's separate P50/P75/P90/P95-of-the-INDICATOR
cutoffs, i.e. percentiles of this module's OUTPUT, not of daily pr) are
Phase 3 work, not implemented here.

--------------------------------------------------------------------------
Not yet an applicable hazard -- correlation-gate candidate (Phase 2.5)
--------------------------------------------------------------------------
This processor produces the raster layer only. It is NOT wired into
``src/index/risk_calculator.py``'s ``HAZARD_TERMS`` / `Risk_i,h` computation
in this task, and it is NOT added to any bucket's applicable-hazard table.
Methods Section 5 requires this hazard to pass the correlation gate (|r| <
0.80 against Water Stress and Drought, spatially harmonised first) before
Phase 3 decides its applicable-hazard-set membership. Wiring it into the
core now would pre-empt that gate.

``PRECIP_TEMPORAL_WINDOW`` mirrors the shape of
``src.index.risk_calculator.HAZARD_TEMPORAL_WINDOW`` (Phase 1) exactly (same
keys), imported and asserted against that schema rather than duplicated
freehand -- but it is a standalone constant in this module, not merged into
the core dict: merging would require adding "precip" to
``risk_calculator.HAZARD_TERMS`` too (an assert there enforces the two sets
match), which is exactly the premature-wiring this section says not to do.

--------------------------------------------------------------------------
Grid, normalisation, caching -- unchanged pattern
--------------------------------------------------------------------------
Computed on the native CMIP6 grid (mirrors ``spei_processor``), resampled by
nearest neighbour onto the country's fixed 1 km grid
(``cds_tasmax_downloader._resample_to_1km``), then Min-Max normalised per
country, pooling every configured model and scenario jointly -- identical
domain-pooling rule to ``heat_stress_processor``/``spei_processor``. The
grid-consistency guard (``GridMismatchError``,
``src/processors/_common.py``) is the same shared implementation.

This module produces the raster layer only. It does not extract per-plant
values or combine hazards.
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

from src.config import CLIMATE_PROCESSED, CMIP6_SCENARIOS, COUNTRIES, CRS_TARGET
from src.downloaders.cds_precipitation_downloader import _open_series, _pick_var
from src.downloaders.cds_precipitation_downloader import raw_dir as precip_raw_dir
from src.downloaders.cds_tasmax_downloader import (
    _normalize_longitude,
    _resample_to_1km,
    configured_models,
)
from src.index.risk_calculator import HAZARD_TEMPORAL_WINDOW as _CORE_HAZARD_TEMPORAL_WINDOW
from src.processors._common import load_country_rasters
from src.processors._common import GridMismatchError  # noqa: F401 - re-exported for callers/tests

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Tier 3 percentile-cutoff method -- see module docstring. Not a Tier 1
# constant: no cited engineering/damage threshold backs these numbers.
# --------------------------------------------------------------------------
WET_DAY_THRESHOLD_MM = 1.0        # ETCCDI wet-day convention (Zhang et al. 2011)
EXTREME_PRECIP_PERCENTILE = 95.0  # ETCCDI "very wet days" / R95p convention
RAW_UNITS = "days_per_year_with_pr_gt_local_p95_wet_day"

# Unit conversion for the raw CMIP6 pr flux (kg m-2 s-1 -> mm/day).
_PR_FLUX_TO_MM_PER_DAY = 86400.0

# Temporal-window assumption -- explicit named constant, same schema as
# src.index.risk_calculator.HAZARD_TEMPORAL_WINDOW (Phase 1 pattern), not
# merged into that dict (see module docstring, "Not yet an applicable
# hazard").
PRECIP_TEMPORAL_WINDOW = {
    "source": "cmip6_pr",
    "horizon_year": 2050,
    "window": "2041-2070",
    "is_explicit_30yr_window": True,
    "note": "Same explicit CMIP6 30-yr window as heat/spei -- pr is the same "
            "downloaded daily series spei_processor already consumes.",
}
_CORE_SCHEMA_KEYS = set(next(iter(_CORE_HAZARD_TEMPORAL_WINDOW.values())))
assert set(PRECIP_TEMPORAL_WINDOW) == _CORE_SCHEMA_KEYS, (
    "PRECIP_TEMPORAL_WINDOW must use the identical schema as "
    "risk_calculator.HAZARD_TEMPORAL_WINDOW entries -- extend the pattern, "
    "don't diverge from it."
)

# The grid-consistency guard (GridMismatchError + the transform tolerance +
# the signature comparison) is the shared implementation in
# src/processors/_common.py -- identical to heat_stress_processor's and
# spei_processor's.


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
def native_raster_path(country: str, model: str, scenario: str) -> Path:
    return CLIMATE_PROCESSED / f"extreme_precip_raw_{country}_{model}_{scenario}_native.tif"


def raw_raster_path(country: str, model: str, scenario: str) -> Path:
    """Path to the raw physical Extreme Precipitation layer (mean days/year
    with daily pr exceeding the pixel's own P95 wet-day threshold), on the
    1 km grid. Computed by this module, not a passthrough -- the indicator
    does not exist until this module computes it (same as
    ``spei_processor.raw_raster_path``, unlike ``heat_stress_processor``'s
    passthrough). Uniform interface with the other processors'
    ``raw_raster_path``."""
    return CLIMATE_PROCESSED / f"extreme_precip_raw_{country}_{model}_{scenario}_1km.tif"


def normalized_raster_path(country: str, model: str, scenario: str) -> Path:
    return CLIMATE_PROCESSED / f"extreme_precip_{country}_{model}_{scenario}_1km.tif"


# --------------------------------------------------------------------------
# Reading the raw daily series (pr only -- no tas needed here)
# --------------------------------------------------------------------------
def _load_daily_pr(country: str, model: str, scenario: str) -> xr.DataArray:
    """Open the raw daily ``pr`` series already downloaded by
    ``cds_precipitation_downloader`` for the SPEI term. Raises
    ``FileNotFoundError`` if it is not on disk yet -- this module never
    triggers a download itself."""
    nc_dir = precip_raw_dir(country, model, scenario, "pr")
    nc_files = sorted(nc_dir.glob("*.nc"))
    if not nc_files:
        raise FileNotFoundError(
            f"No raw pr .nc files for {country}/{model}/{scenario} under "
            f"{nc_dir}. Run the CDS precipitation downloader "
            f"(cds_precipitation_downloader.download_all_cds_precipitation) "
            f"first -- the same data spei_processor consumes."
        )
    ds = _normalize_longitude(_open_series(nc_files))
    var = _pick_var(ds, "pr")
    return ds[var]


# --------------------------------------------------------------------------
# Raw indicator: mean days/year with pr > per-pixel P95 wet-day threshold
# --------------------------------------------------------------------------
def compute_extreme_precip_days(
    pr_da: xr.DataArray,
    wet_day_threshold_mm: float = WET_DAY_THRESHOLD_MM,
    percentile: float = EXTREME_PRECIP_PERCENTILE,
) -> xr.DataArray:
    """Full pipeline: daily pr flux -> mm/day -> per-pixel wet-day P95
    threshold -> mean days/year exceeding it. Returns a 2D ``(lat, lon)``
    ``DataArray`` on the native grid of ``pr_da``.

    Per-pixel percentile is computed over every wet day in the whole window
    (not per calendar month, unlike SPEI's per-calendar-month fit) -- there
    is no seasonal-cycle removal step needed here, since the percentile
    itself is the pixel's own full-window distribution, already local.
    """
    pr_vals = np.asarray(pr_da.values, dtype="float64") * _PR_FLUX_TO_MM_PER_DAY  # (time, ny, nx)
    n_days_total = pr_vals.shape[0]
    time_index = pr_da["time"].to_index()
    n_years = float(len(np.unique(np.asarray(time_index.year))))

    wet_mask = pr_vals >= wet_day_threshold_mm
    wet_vals = np.where(wet_mask, pr_vals, np.nan)

    # Per-pixel P95 of wet-day amounts; a pixel with no wet days at all gets
    # NaN (propagates, never becomes a spurious 0 threshold).
    with np.errstate(invalid="ignore"):
        threshold = np.nanpercentile(wet_vals, percentile, axis=0)  # (ny, nx)

    exceeds = pr_vals > threshold[None, :, :]
    exceeds = np.where(np.isnan(threshold)[None, :, :], np.nan, exceeds.astype("float64"))

    days_per_year = np.nansum(exceeds, axis=0) / n_years
    # A pixel with an all-NaN threshold (no wet days in the whole window --
    # not observed in practice, but not assumed impossible) is NaN, not 0.
    days_per_year = np.where(np.isnan(threshold), np.nan, days_per_year)

    out = xr.DataArray(
        days_per_year.astype("float32"), dims=("lat", "lon"),
        coords={"lat": pr_da["lat"], "lon": pr_da["lon"]},
        name="extreme_precip_days_raw",
    )
    out.attrs.update(
        method=f"ETCCDI-style very-wet-days: per-pixel P{percentile:g} of "
               f"wet-day (pr >= {wet_day_threshold_mm:g} mm/day) amounts, "
               f"mean exceedance days/year over the window "
               f"(Zhang et al. 2011)",
        wet_day_threshold_mm=wet_day_threshold_mm,
        percentile=percentile,
        units=RAW_UNITS,
        n_days=int(n_days_total),
        n_years=n_years,
        note=(
            "Tier 3 only (docs/DECISIONS.md, 'Extreme Precipitation "
            "downgraded Tier 1 -> Tier 3') -- percentile-cutoff method, no "
            "HAZUS-MH or other absolute depth threshold used anywhere. Not "
            "yet wired into src/index/risk_calculator.py's Risk_i,h -- "
            "pending the Phase 2.5 correlation gate and Phase 3's "
            "applicable-hazard-set decision. See the module docstring."
        ),
    )
    return out


def _compute_native(country: str, model: str, scenario: str) -> xr.DataArray:
    pr_da = _load_daily_pr(country, model, scenario)
    da = compute_extreme_precip_days(pr_da)
    da.attrs.update(country=country, model=model, scenario=scenario)
    return da


# --------------------------------------------------------------------------
# Raw layer -- compute once, cache to disk
# --------------------------------------------------------------------------
def ensure_raw_raster(
    country: str, model: str, scenario: str, overwrite: bool = False,
) -> dict:
    """Compute (if not cached) and write the native + 1 km raw Extreme
    Precipitation raster for one country/model/scenario. Idempotent."""
    CLIMATE_PROCESSED.mkdir(parents=True, exist_ok=True)
    native_path = native_raster_path(country, model, scenario)
    raw_path = raw_raster_path(country, model, scenario)

    if raw_path.exists() and not overwrite:
        logger.info("%s/%s/%s: extreme-precip raw raster cached, skipping.", country, model, scenario)
        return {"success": True, "path": str(raw_path), "reason": "cached"}

    try:
        native = _compute_native(country, model, scenario)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return {"success": False, "path": None, "reason": f"missing_dependency: {exc}"}

    native = native.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    native = native.rio.write_crs(CRS_TARGET)
    native.rio.to_raster(native_path)

    resampled = _resample_to_1km(native, country)
    resampled.rio.to_raster(raw_path)
    logger.info(
        "%s/%s/%s: native %s %s, raw 1km %s %s",
        country, model, scenario,
        native_path.name, tuple(native.shape),
        raw_path.name, tuple(resampled.shape),
    )
    return {
        "success": True, "path": str(raw_path), "reason": "processed",
        "native_path": str(native_path), "shape": list(resampled.shape),
    }


# --------------------------------------------------------------------------
# Grid guard + Min-Max normalisation (mirrors heat_stress_processor / spei_processor)
# --------------------------------------------------------------------------
def _load_raw_raster(country: str, model: str, scenario: str) -> xr.DataArray:
    path = raw_raster_path(country, model, scenario)
    if not path.exists():
        raise FileNotFoundError(
            f"Extreme-precipitation raw raster not found: {path}. Run "
            f"ensure_raw_raster (or process_all_countries) first."
        )
    da = rioxarray.open_rasterio(path)
    return da.isel(band=0) if "band" in da.dims else da


def _load_country_rasters(
    country: str, models: list[str] | None = None, scenarios: list[str] | None = None,
) -> dict[tuple[str, str], xr.DataArray]:
    """Open every ``(model, scenario)`` Extreme Precipitation raw raster for
    ``country`` and assert they share one grid (``_common``'s shared guard,
    identical to ``heat_stress_processor``'s / ``spei_processor``'s)."""
    return load_country_rasters(
        country, _load_raw_raster,
        models or configured_models(), scenarios or CMIP6_SCENARIOS,
    )


def compute_country_minmax(
    country: str,
    models: list[str] | None = None,
    scenarios: list[str] | None = None,
    rasters: dict[tuple[str, str], xr.DataArray] | None = None,
) -> tuple[float, float]:
    """Per-country Min-Max domain: every configured model and scenario of
    this country pooled jointly, never across countries."""
    if rasters is None:
        rasters = _load_country_rasters(country, models, scenarios)

    pooled = []
    for da in rasters.values():
        values = np.asarray(da.values, dtype="float64").ravel()
        pooled.append(values[~np.isnan(values)])

    combined = np.concatenate(pooled)
    country_min, country_max = float(combined.min()), float(combined.max())
    logger.info(
        "%s: normalisation domain (models %s x scenarios %s pooled jointly, "
        "per country): min=%.6g max=%.6g (n=%d).",
        country, sorted({m for m, _ in rasters}), sorted({s for _, s in rasters}),
        country_min, country_max, len(combined),
    )
    return country_min, country_max


def normalize_scenario(
    country: str, model: str, scenario: str,
    country_min: float, country_max: float, da: xr.DataArray | None = None,
) -> xr.DataArray:
    """Per-country Min-Max normalisation of one Extreme Precipitation raster
    against the shared country domain. NaN at the source raster's edges
    propagates, never becomes 0."""
    if da is None:
        da = _load_raw_raster(country, model, scenario)
    values = da.values.astype("float64")

    span = country_max - country_min
    if span <= 0:
        normalized = np.where(np.isnan(values), np.nan, 0.0).astype("float32")
    else:
        normalized = np.clip((values - country_min) / span, 0.0, 1.0).astype("float32")

    out = xr.DataArray(
        normalized, dims=da.dims, coords=da.coords, name="extreme_precip_normalized",
    ).rio.write_crs(da.rio.crs)
    out.attrs.update(
        source="CDS daily pr (CMIP6), indicator days/year with pr > local P95 "
               "wet-day threshold, 1 km grid",
        cmip6_model=model,
        cmip6_scenario=scenario,
        normalization="per-country Min-Max (this country's models and scenarios "
                      "pooled jointly, not across countries)",
        country=country,
        country_min=country_min,
        country_max=country_max,
        note="0 = least extreme-precipitation-prone cell observed in this "
             "country (any model, any scenario); 1 = most. Not comparable in "
             "absolute terms across countries. NaN = outside the country "
             "boundary (preserved from source).",
    )
    return out


def process_country_model_scenario(
    country: str, model: str, scenario: str,
    country_min: float, country_max: float,
    da: xr.DataArray | None = None, overwrite: bool = False,
) -> dict:
    """Normalise and write the Extreme Precipitation layer for one
    country/model/scenario against the shared country domain. Assumes the
    raw raster is already on disk (``ensure_raw_raster``)."""
    CLIMATE_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = normalized_raster_path(country, model, scenario)
    raw_path = raw_raster_path(country, model, scenario)
    raw_meta = {"raw_path": str(raw_path), "raw_kind": "computed", "raw_units": RAW_UNITS}

    if out_path.exists() and not overwrite:
        logger.info("%s/%s/%s: extreme precipitation already processed, skipping.", country, model, scenario)
        return {"success": True, "path": str(out_path), "reason": "cached", **raw_meta}

    try:
        da_norm = normalize_scenario(country, model, scenario, country_min, country_max, da=da)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return {"success": False, "path": None, "reason": f"missing_dependency: {exc}"}

    da_norm.rio.to_raster(out_path)
    valid = da_norm.values[~np.isnan(da_norm.values)]
    if len(valid):
        logger.info(
            "%s/%s/%s: saved %s - %s, %d valid px, mean=%.3f (raw: %s)",
            country, model, scenario, out_path.name, da_norm.shape, len(valid),
            float(valid.mean()), raw_path.name,
        )
    else:
        logger.warning("%s/%s/%s: saved %s but 0 valid pixels (all NaN).", country, model, scenario, out_path.name)

    return {
        "success": True, "path": str(out_path), "reason": "processed",
        "shape": list(da_norm.shape), **raw_meta,
    }


def process_all_countries(
    countries: list[str] | None = None,
    scenarios: list[str] | None = None,
    models: list[str] | None = None,
    overwrite: bool = False,
) -> dict:
    countries = countries or COUNTRIES
    scenarios = scenarios or CMIP6_SCENARIOS
    models = models or configured_models()

    report = {"normalization_domain": "per_country_models_and_scenarios_pooled", "countries": {}}
    for country in countries:
        raw_status: dict = {}
        all_raw_ok = True
        for model in models:
            raw_status[model] = {}
            for scenario in scenarios:
                status = ensure_raw_raster(country, model, scenario, overwrite=overwrite)
                raw_status[model][scenario] = status
                all_raw_ok = all_raw_ok and status["success"]

        if not all_raw_ok:
            report["countries"][country] = {"success": False, "raw": raw_status}
            continue

        try:
            rasters = _load_country_rasters(country, models, scenarios)
        except FileNotFoundError as exc:
            logger.error(str(exc))
            report["countries"][country] = {"success": False, "reason": f"missing_dependency: {exc}"}
            continue

        country_min, country_max = compute_country_minmax(country, rasters=rasters)
        entry = {"country_min": country_min, "country_max": country_max, "models": {}}
        for model in models:
            entry["models"][model] = {"scenarios": {}}
            for scenario in scenarios:
                entry["models"][model]["scenarios"][scenario] = process_country_model_scenario(
                    country, model, scenario, country_min, country_max,
                    da=rasters[(model, scenario)], overwrite=overwrite,
                )
        report["countries"][country] = entry
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--countries", nargs="+", default=None)
    parser.add_argument("--scenarios", nargs="+", default=None, choices=CMIP6_SCENARIOS)
    parser.add_argument("--models", nargs="+", default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    result = process_all_countries(
        countries=args.countries, scenarios=args.scenarios,
        models=args.models, overwrite=args.overwrite,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    ok = all(
        c.get("success", True)
        and all(
            s["success"]
            for m in c.get("models", {}).values()
            for s in m["scenarios"].values()
        )
        for c in result["countries"].values()
    )
    sys.exit(0 if ok else 1)
