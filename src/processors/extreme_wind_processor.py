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
Not yet wired into risk_calculator -- Phase 3, not this phase
--------------------------------------------------------------------------
This processor produces the raster layer (+ the standalone classification
utility) only. It is NOT wired into ``src/index/risk_calculator.py``'s
``HAZARD_TERMS``/``Risk_i,h`` computation, and it is NOT added to any
bucket's applicable-hazard table -- both are Phase 3.1 decisions.
``WIND_TEMPORAL_WINDOW`` mirrors the shape of
``src.index.risk_calculator.HAZARD_TEMPORAL_WINDOW`` (same schema keys,
asserted at import time) but is a standalone constant, not merged into that
dict, matching the pattern already used for
``extreme_precipitation_processor.PRECIP_TEMPORAL_WINDOW``.
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
from src.downloaders.cds_tasmax_downloader import _normalize_longitude, _resample_to_1km
from src.downloaders.era5_wind_downloader import (
    BASELINE_YEARS,
    ERA5_WIND_BASELINE_PERIOD,
    _open_series,
    _pick_var,
)
from src.downloaders.era5_wind_downloader import raw_dir as era5_raw_dir
from src.index.risk_calculator import HAZARD_TEMPORAL_WINDOW as _CORE_HAZARD_TEMPORAL_WINDOW
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
_CORE_SCHEMA_KEYS = set(next(iter(_CORE_HAZARD_TEMPORAL_WINDOW.values())))
assert set(WIND_TEMPORAL_WINDOW) == _CORE_SCHEMA_KEYS, (
    "WIND_TEMPORAL_WINDOW must use the identical schema as "
    "risk_calculator.HAZARD_TEMPORAL_WINDOW entries -- extend the pattern, "
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
# Reading the raw hourly series
# --------------------------------------------------------------------------
def _load_hourly_gust(country: str, years: list[int] | None = None) -> xr.DataArray:
    """Open every configured baseline year's hourly gust series for
    ``country`` and concatenate along time. Raises ``FileNotFoundError`` if
    any year is missing -- this module never triggers a download itself."""
    years = years or BASELINE_YEARS
    all_files: list[Path] = []
    missing: list[int] = []
    for year in years:
        nc_dir = era5_raw_dir(country, year)
        nc_files = sorted(nc_dir.glob("*.nc"))
        if not nc_files:
            missing.append(year)
        all_files.extend(nc_files)

    if missing:
        raise FileNotFoundError(
            f"No raw ERA5 gust .nc files for {country}, year(s) {missing} under "
            f"{era5_raw_dir(country, missing[0]).parent}. Run "
            f"era5_wind_downloader.download_country_baseline first."
        )

    ds = _normalize_longitude(_open_series(all_files))
    var = _pick_var(ds)
    return ds[var]


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
    """
    time_index = gust_da["time"].to_index()
    years = np.asarray(time_index.year)
    unique_years = np.unique(years)

    annual_maxima = []
    for year in unique_years:
        year_slice = gust_da.isel(time=np.where(years == year)[0])
        annual_maxima.append(year_slice.max(dim="time", skipna=True))

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
    gust_da = _load_hourly_gust(country)
    da = compute_mean_annual_max_gust(gust_da)
    da.attrs.update(country=country)
    return da


# --------------------------------------------------------------------------
# Raw layer -- compute once, cache to disk
# --------------------------------------------------------------------------
def ensure_raw_raster(country: str, overwrite: bool = False) -> dict:
    """Compute (if not cached) and write the native + 1 km raw Extreme Wind
    raster for one country. Idempotent."""
    CLIMATE_PROCESSED.mkdir(parents=True, exist_ok=True)
    native_path = native_raster_path(country)
    raw_path = raw_raster_path(country)

    if raw_path.exists() and not overwrite:
        logger.info("%s: extreme-wind raw raster cached, skipping.", country)
        return {"success": True, "path": str(raw_path), "reason": "cached"}

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
