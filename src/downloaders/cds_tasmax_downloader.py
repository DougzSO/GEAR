"""
Extreme heat — daily ``tasmax`` from the Copernicus CDS ``projections-cmip6``
dataset, reduced to an annual count of days with ``tasmax`` above a threshold.

Why daily CMIP6 output: the indicator is "number of days per year with
tasmax > 40 C", which needs a real daily series. The trade-off is the native
GCM resolution (~1 degree, ~100 km), far coarser than the 1 km target of the
rest of the pipeline.

Spatial resampling, not downscaling: the per-cell day count is resampled to
``RESOLUTION_TARGET_DEG`` by nearest neighbour. This creates no new
information — one ~100 km cell becomes ~100 identical 1 km cells. Nearest
neighbour is deliberate over bilinear/cubic: there is no bias correction
here, and a higher-order interpolator would fake spatial precision the data
does not have. The "1 km" of this layer is nominal, for stacking with the
other hazards; state this in the manuscript methods.

Multiple GCMs: ``config.CMIP6_SOURCE_ID_CDS`` is a list. ARCHITECTURE.md
Section 4 makes a second GCM a mandatory sensitivity check, so every function
here iterates over the configured models and writes model-tagged outputs. The
second model is pending verification item V4; with one model configured the
behaviour is identical to the single-model pipeline, only the file names
carry the model id.

CDS request contract: the parameter names below (variable, model, experiment)
were taken from the public ``projections-cmip6`` process schema. If the API
has changed, the error from the first real run names the valid values — adjust
the constants here.
"""

from __future__ import annotations

import json
import logging
import time
import math
import zipfile
from pathlib import Path

import xarray as xr
from rasterio.enums import Resampling
from rasterio.transform import from_origin

from src.config import (
    CDS_API_URL,
    CLIMATE_PROCESSED,
    CLIMATE_RAW,
    CMIP6_FUTURE_PERIOD,
    CMIP6_SCENARIO_TO_CDS_EXPERIMENT,
    CMIP6_SCENARIOS,
    CMIP6_SOURCE_ID_CDS,
    COUNTRY_BBOX_FALLBACK,
    CRS_TARGET,
    EXTREME_HEAT_THRESHOLD_C,
    RESOLUTION_TARGET_DEG,
    require_cds_api_key,
)
from src.downloaders.boundaries_downloader import get_country_bounds

logger = logging.getLogger(__name__)

CDS_DATASET = "projections-cmip6"
CDS_VARIABLE = "daily_maximum_near_surface_air_temperature"
HEAT_THRESHOLD_K = EXTREME_HEAT_THRESHOLD_C + 273.15

_START, _END = CMIP6_FUTURE_PERIOD
N_YEARS = int(_END[:4]) - int(_START[:4]) + 1


def configured_models() -> list[str]:
    """The CDS ``model`` ids to process. Empty is a configuration error."""
    models = [m for m in CMIP6_SOURCE_ID_CDS if m]
    if not models:
        raise ValueError(
            "config.CMIP6_SOURCE_ID_CDS is empty. Populate at least one CDS "
            "model id (e.g. 'gfdl_esm4')."
        )
    return models


def raw_dir(country: str, model: str, scenario: str) -> Path:
    return CLIMATE_RAW / "cds_tasmax" / country / model / scenario


def native_raster_path(country: str, model: str, scenario: str) -> Path:
    return CLIMATE_PROCESSED / f"extreme_heat_days_{country}_{model}_{scenario}_native.tif"


def resampled_raster_path(country: str, model: str, scenario: str) -> Path:
    return CLIMATE_PROCESSED / f"extreme_heat_days_{country}_{model}_{scenario}_1km.tif"


def _get_client():
    import cdsapi

    return cdsapi.Client(url=CDS_API_URL, key=require_cds_api_key())


def _climate_bounds(country: str) -> tuple[float, float, float, float]:
    """Effective ``(xmin, ymin, xmax, ymax)`` for the heat download: the
    per-coordinate union of the GADM level-0 bounds and
    ``config.COUNTRY_BBOX_FALLBACK[country]``. The union covers in-scope
    territory GADM under-represents (northern J&K / Ladakh, western Kutch) and
    gives the ~1 deg GCM grid room to snap outward rather than clipping a
    border cell. Used for both the CDS request area and the post-resample
    clip box, so the two always agree."""
    gxmin, gymin, gxmax, gymax = get_country_bounds(country)
    fxmin, fymin, fxmax, fymax = COUNTRY_BBOX_FALLBACK[country]
    return (min(gxmin, fxmin), min(gymin, fymin), max(gxmax, fxmax), max(gymax, fymax))


def _country_area(country: str) -> list[float]:
    """``[N, W, S, E]`` — the order the CDS ``area`` parameter expects."""
    xmin, ymin, xmax, ymax = _climate_bounds(country)
    return [ymax, xmin, ymin, xmax]


def _build_request(country: str, model: str, scenario: str) -> dict:
    """Build the CDS retrieve request for one country/model/scenario, one
    request covering the whole 30-year window."""
    start_year, end_year = int(_START[:4]), int(_END[:4])
    return {
        "temporal_resolution": "daily",
        "experiment": CMIP6_SCENARIO_TO_CDS_EXPERIMENT[scenario],
        "variable": CDS_VARIABLE,
        "model": model,
        "year": [str(y) for y in range(start_year, end_year + 1)],
        "month": [f"{m:02d}" for m in range(1, 13)],
        "area": _country_area(country),
    }


def _download_raw(country: str, model: str, scenario: str, overwrite: bool) -> dict:
    """Download the raw daily package for one country/model/scenario. Returns
    a structured status dict; the raw ``cdsapi`` exception never propagates."""
    out_dir = raw_dir(country, model, scenario)
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / "tasmax_daily.zip"
    marker = out_dir / ".downloaded"

    if marker.exists() and not overwrite:
        nc_files = sorted(out_dir.glob("*.nc"))
        if nc_files:
            logger.info("CDS tasmax cached for %s/%s/%s, skipping.", country, model, scenario)
            return {
                "success": True,
                "path": str(out_dir),
                "reason": "cached",
                "seconds": 0.0,
                "files": [str(f) for f in nc_files],
            }

    request = _build_request(country, model, scenario)
    logger.info(
        "CDS request for %s/%s/%s: %s", country, model, scenario, json.dumps(request)
    )

    start = time.monotonic()
    try:
        client = _get_client()
        client.retrieve(CDS_DATASET, request, str(zip_path))
    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - start
        logger.error(
            "CDS request failed for %s/%s/%s after %.0fs: %s: %s",
            country, model, scenario, elapsed, type(exc).__name__, exc,
        )
        return {
            "success": False,
            "path": None,
            "reason": f"cds_error: {type(exc).__name__}: {exc}",
            "seconds": elapsed,
        }
    elapsed = time.monotonic() - start

    try:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(out_dir)
    except zipfile.BadZipFile:
        # Depending on the delivery format the CDS may return a bare netCDF.
        (out_dir / "tasmax_daily.nc").write_bytes(zip_path.read_bytes())

    nc_files = sorted(out_dir.glob("*.nc"))
    if not nc_files:
        logger.error(
            "CDS %s/%s/%s: download finished but no .nc file in %s",
            country, model, scenario, out_dir,
        )
        return {"success": False, "path": str(out_dir), "reason": "no_nc_after_extract", "seconds": elapsed}

    marker.write_text(f"downloaded in {elapsed:.0f}s: {[f.name for f in nc_files]}")
    logger.info("CDS %s/%s/%s: OK in %.0fs", country, model, scenario, elapsed)
    return {
        "success": True,
        "path": str(out_dir),
        "reason": "downloaded",
        "seconds": elapsed,
        "files": [str(f) for f in nc_files],
    }


def _open_tasmax(nc_files: list[Path]) -> xr.Dataset:
    if len(nc_files) == 1:
        return xr.open_dataset(nc_files[0])
    return xr.open_mfdataset([str(f) for f in nc_files], combine="by_coords")


def _normalize_longitude(ds: xr.Dataset) -> xr.Dataset:
    """CMIP6/ESGF output often uses longitude 0-360; the rest of the pipeline
    uses -180/180. Without this, bbox clipping misses everything for
    Brazil/Portugal (negative longitudes)."""
    if float(ds["lon"].max()) > 180:
        ds = ds.assign_coords(lon=(((ds["lon"] + 180) % 360) - 180)).sortby("lon")
    return ds


def _compute_extreme_heat_days(nc_files: list[Path], model: str) -> xr.DataArray:
    """Mean number of days per year with ``tasmax`` above the threshold over
    the 2041-2070 window: total exceedance days divided by ``N_YEARS``.
    Returns a 2D (lat, lon) array at the GCM's native resolution."""
    ds = _open_tasmax(nc_files)
    ds = _normalize_longitude(ds)

    var_name = "tasmax" if "tasmax" in ds.data_vars else list(ds.data_vars)[0]
    tasmax = ds[var_name]

    exceed_days = (tasmax > HEAT_THRESHOLD_K).sum(dim="time")
    days_per_year = (exceed_days / N_YEARS).astype("float32")
    days_per_year.name = "extreme_heat_days_per_year"
    days_per_year.attrs.update(
        threshold_c=EXTREME_HEAT_THRESHOLD_C,
        period=f"{_START}/{_END}",
        n_years=N_YEARS,
        source="CDS projections-cmip6, daily_maximum_near_surface_air_temperature",
        model=model,
        note=(
            "Indicator = total days above threshold over the period / N_YEARS. "
            "Native GCM resolution (~1 degree), not resampled at this step."
        ),
    )
    ds.close()
    return days_per_year


def _target_grid(country: str):
    """The single 1 km destination grid for a country — ``(transform, width,
    height)`` derived only from ``_climate_bounds(country)`` and
    ``RESOLUTION_TARGET_DEG``.

    Every GCM resamples onto exactly this transform and shape, whatever its
    native resolution. Deriving the output grid from each model's own native
    extent instead (an earlier design) left GFDL-ESM4 (~1.25x1 deg) and
    MIROC6 (~1.4x1.4 deg) on offset, differently-shaped 1 km rasters, which
    broke the per-country joint Min-Max pool downstream (its
    ``_assert_consistent_grid`` guard caught it)."""
    xmin, ymin, xmax, ymax = _climate_bounds(country)
    res = RESOLUTION_TARGET_DEG
    width = math.ceil((xmax - xmin) / res)
    height = math.ceil((ymax - ymin) / res)
    # Origin at the top-left corner (xmin, ymax); rows run north -> south.
    transform = from_origin(xmin, ymax, res, res)
    return transform, width, height


def _resample_to_1km(da: xr.DataArray, country: str) -> xr.DataArray:
    """Resample by nearest neighbour onto the country's common 1 km grid (see
    ``_target_grid``): identical transform, shape and CRS for every GCM, so
    the per-country joint Min-Max pool sees consistent grids. The extent
    matches ``_climate_bounds(country)`` — the same box used for the CDS
    request — so the raster is never clipped tighter than what was
    downloaded."""
    da = da.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    da = da.rio.write_crs(CRS_TARGET)

    transform, width, height = _target_grid(country)
    resampled = da.rio.reproject(
        CRS_TARGET,
        transform=transform,
        shape=(height, width),
        resampling=Resampling.nearest,
    )
    resampled.attrs["resampling_method"] = (
        f"nearest_neighbor — spatial resampling from ~1 degree to "
        f"{RESOLUTION_TARGET_DEG} degree onto a fixed per-country grid, "
        f"not a real increase in resolution"
    )
    return resampled


def process_country_model_scenario(
    country: str, model: str, scenario: str, overwrite: bool = False
) -> dict:
    """Download (if needed) + compute the indicator + resample to 1 km for one
    country/model/scenario. Writes both the native raster (QA/transparency)
    and the 1 km raster."""
    status = _download_raw(country, model, scenario, overwrite)
    if not status["success"]:
        return status

    CLIMATE_PROCESSED.mkdir(parents=True, exist_ok=True)
    native_path = native_raster_path(country, model, scenario)
    resampled_path = resampled_raster_path(country, model, scenario)

    if resampled_path.exists() and not overwrite:
        logger.info(
            "Indicator already processed for %s/%s/%s, skipping compute.",
            country, model, scenario,
        )
        return {**status, "native_path": str(native_path), "resampled_path": str(resampled_path)}

    nc_files = [Path(f) for f in status["files"]]

    native = _compute_extreme_heat_days(nc_files, model)
    native = native.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
    native = native.rio.write_crs(CRS_TARGET)
    native.rio.to_raster(native_path)

    resampled = _resample_to_1km(native, country)
    resampled.rio.to_raster(resampled_path)

    logger.info(
        "%s/%s/%s: native %s %s, 1km %s %s",
        country, model, scenario,
        native_path.name, tuple(native.shape),
        resampled_path.name, tuple(resampled.shape),
    )
    return {
        **status,
        "native_path": str(native_path),
        "resampled_path": str(resampled_path),
        "native_shape": list(native.shape),
        "resampled_shape": list(resampled.shape),
    }


def download_all_cds_tasmax(countries, overwrite: bool = False) -> dict:
    """Process every country x model x scenario. The report is nested
    ``country -> model -> scenario -> status``."""
    report: dict = {}
    for country in countries:
        report[country] = {}
        for model in configured_models():
            report[country][model] = {}
            for scenario in CMIP6_SCENARIOS:
                report[country][model][scenario] = process_country_model_scenario(
                    country, model, scenario, overwrite
                )
    return report


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--country", required=True)
    parser.add_argument("--scenario", required=True, choices=CMIP6_SCENARIOS)
    parser.add_argument("--model", default=None, help="CDS model id; default = first configured")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    chosen_model = args.model or configured_models()[0]
    result = process_country_model_scenario(
        args.country, chosen_model, args.scenario, args.overwrite
    )
    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if result["success"] else 1)
