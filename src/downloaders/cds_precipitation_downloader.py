"""
Precipitation and daily-mean near-surface air temperature — daily ``pr`` and
``tas`` from the Copernicus CDS ``projections-cmip6`` dataset, for a future
SPEI (Standardised Precipitation-Evapotranspiration Index) drought term.

Mirrors ``cds_tasmax_downloader``: same dataset, same
2-GCM x 3-scenario x 3-country matrix, same 2041-2070 window, same common
per-country 1 km grid. ``_climate_bounds``, ``_country_area``,
``_normalize_longitude`` and ``_resample_to_1km`` are *imported* from that
module, not re-implemented, so the drought inputs stack cell-for-cell with
the heat layer and there is one definition of the corrected grid.

Why ``pr`` + ``tas`` and nothing else: the PET method for SPEI is
Thornthwaite (``analysis/climate_risk_score_spec.md`` Section 3), which needs
only precipitation and daily-mean temperature. Hargreaves
(``pr`` + ``tasmin`` + ``tasmax``) was rejected because daily ``tasmin`` is
absent from the CDS catalogue for ``gfdl_esm4`` / ``ssp3_7_0``
(``analysis/spei_catalog_check.md``).

What this step does and does NOT do: it downloads the raw daily series (the
NetCDF the future SPEI processor will read) and validates it, and it writes a
**period-mean climatology raster per variable as a QA/transparency artifact
only**. SPEI needs the full daily series, not the period mean, and is a
separate later task -- there is no ``spei_processor`` here.

CDS request contract: the ``variable`` tokens (``precipitation``,
``near_surface_air_temperature``) are from the public ``projections-cmip6``
process schema, same provenance as the tasmax downloader's. If the API has
changed, the error from the first real run names the valid values.
"""

from __future__ import annotations

import json
import logging
import time
import zipfile
from pathlib import Path

import numpy as np
import rioxarray  # noqa: F401  -- registers the .rio accessor used below
import xarray as xr

from src.config import (
    CLIMATE_PROCESSED,
    CLIMATE_RAW,
    CMIP6_FUTURE_PERIOD,
    CMIP6_SCENARIO_TO_CDS_EXPERIMENT,
    CMIP6_SCENARIOS,
    CMIP6_SPEI_VARIABLES,
    CRS_TARGET,
)
from src.downloaders.cds_tasmax_downloader import (
    _country_area,
    _get_client,
    _normalize_longitude,
    _resample_to_1km,
    configured_models,
)

logger = logging.getLogger(__name__)

CDS_DATASET = "projections-cmip6"

_START, _END = CMIP6_FUTURE_PERIOD
N_YEARS = int(_END[:4]) - int(_START[:4]) + 1

# Short name -> (multiplicative scale, additive offset, unit label) taking the
# native CMIP6 unit to a readable one for the QA period-mean raster:
#   pr : kg m-2 s-1 (precipitation flux) -> mm/day   (x 86400)
#   tas: K                               -> degC     (- 273.15)
_QA_UNIT = {
    "pr": (86400.0, 0.0, "mm_per_day"),
    "tas": (1.0, -273.15, "degC"),
}
# File stem for the QA period-mean raster per variable.
_QA_STEM = {"pr": "precipitation_mean", "tas": "air_temperature_mean"}


def spei_variables() -> dict[str, str]:
    """``{short_name: cds_variable}`` to download. Empty is a config error."""
    mapping = {k: v for k, v in CMIP6_SPEI_VARIABLES.items() if k and v}
    if not mapping:
        raise ValueError(
            "config.CMIP6_SPEI_VARIABLES is empty. Populate at least "
            "{'pr': 'precipitation', 'tas': 'near_surface_air_temperature'}."
        )
    return mapping


def raw_dir(country: str, model: str, scenario: str, short_name: str) -> Path:
    return CLIMATE_RAW / "cds_spei" / country / model / scenario / short_name


def native_raster_path(country: str, model: str, scenario: str, short_name: str) -> Path:
    return CLIMATE_PROCESSED / (
        f"{_QA_STEM[short_name]}_{country}_{model}_{scenario}_native.tif"
    )


def resampled_raster_path(country: str, model: str, scenario: str, short_name: str) -> Path:
    return CLIMATE_PROCESSED / (
        f"{_QA_STEM[short_name]}_{country}_{model}_{scenario}_1km.tif"
    )


def _build_request(country: str, model: str, scenario: str, cds_variable: str) -> dict:
    """CDS retrieve request for one country/model/scenario/variable, one
    request covering the whole 30-year window."""
    start_year, end_year = int(_START[:4]), int(_END[:4])
    return {
        "temporal_resolution": "daily",
        "experiment": CMIP6_SCENARIO_TO_CDS_EXPERIMENT[scenario],
        "variable": cds_variable,
        "model": model,
        "year": [str(y) for y in range(start_year, end_year + 1)],
        "month": [f"{m:02d}" for m in range(1, 13)],
        "area": _country_area(country),
    }


def _download_raw(
    country: str, model: str, scenario: str, short_name: str, overwrite: bool
) -> dict:
    """Download the raw daily package for one country/model/scenario/variable.
    Returns a structured status dict; the raw ``cdsapi`` exception never
    propagates."""
    out_dir = raw_dir(country, model, scenario, short_name)
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{short_name}_daily.zip"
    marker = out_dir / ".downloaded"

    if marker.exists() and not overwrite:
        nc_files = sorted(out_dir.glob("*.nc"))
        if nc_files:
            logger.info(
                "CDS %s cached for %s/%s/%s, skipping.", short_name, country, model, scenario
            )
            return {
                "success": True,
                "path": str(out_dir),
                "reason": "cached",
                "seconds": 0.0,
                "files": [str(f) for f in nc_files],
            }

    request = _build_request(country, model, scenario, spei_variables()[short_name])
    logger.info(
        "CDS request for %s/%s/%s/%s: %s",
        country, model, scenario, short_name, json.dumps(request),
    )

    start = time.monotonic()
    try:
        client = _get_client()
        client.retrieve(CDS_DATASET, request, str(zip_path))
    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - start
        logger.error(
            "CDS request failed for %s/%s/%s/%s after %.0fs: %s: %s",
            country, model, scenario, short_name, elapsed, type(exc).__name__, exc,
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
        (out_dir / f"{short_name}_daily.nc").write_bytes(zip_path.read_bytes())

    nc_files = sorted(out_dir.glob("*.nc"))
    if not nc_files:
        logger.error(
            "CDS %s/%s/%s/%s: download finished but no .nc file in %s",
            country, model, scenario, short_name, out_dir,
        )
        return {
            "success": False,
            "path": str(out_dir),
            "reason": "no_nc_after_extract",
            "seconds": elapsed,
        }

    marker.write_text(f"downloaded in {elapsed:.0f}s: {[f.name for f in nc_files]}")
    logger.info("CDS %s/%s/%s/%s: OK in %.0fs", country, model, scenario, short_name, elapsed)
    return {
        "success": True,
        "path": str(out_dir),
        "reason": "downloaded",
        "seconds": elapsed,
        "files": [str(f) for f in nc_files],
    }


def _open_series(nc_files: list[Path]) -> xr.Dataset:
    if len(nc_files) == 1:
        return xr.open_dataset(nc_files[0])
    return xr.open_mfdataset([str(f) for f in nc_files], combine="by_coords")


def _pick_var(ds: xr.Dataset, short_name: str) -> str:
    return short_name if short_name in ds.data_vars else list(ds.data_vars)[0]


def validate_raw_series(nc_files: list[Path], short_name: str) -> dict:
    """Open the raw daily series and check it is what SPEI will need: the
    right variable, a daily time axis that spans 2041-2070, and real values.
    No SPEI computed -- this only certifies the download."""
    ds = _normalize_longitude(_open_series([Path(f) for f in nc_files]))
    var = _pick_var(ds, short_name)
    da = ds[var]

    times = da["time"]
    t0, t1 = str(times.min().values)[:10], str(times.max().values)[:10]
    n_steps = int(times.size)
    # ~daily over 30 years -> ~10950-10957 depending on calendar; be lenient.
    covers_window = (t0[:7] <= f"{_START[:4]}-01") and (t1[:7] >= f"{_END[:4]}-12")
    plausible_daily = n_steps >= 350 * N_YEARS

    first = da.isel(time=0)
    finite_fraction = float(np.isfinite(first).mean())

    ds.close()
    return {
        "variable": var,
        "n_timesteps": n_steps,
        "time_start": t0,
        "time_end": t1,
        "covers_window": bool(covers_window),
        "plausible_daily_length": bool(plausible_daily),
        "lat_range": [float(da["lat"].min()), float(da["lat"].max())],
        "lon_range": [float(da["lon"].min()), float(da["lon"].max())],
        "finite_fraction_first_step": finite_fraction,
        "valid": bool(covers_window and plausible_daily and finite_fraction > 0.0),
    }


def _period_mean(nc_files: list[Path], short_name: str, model: str) -> xr.DataArray:
    """Time-mean of the raw series over 2041-2070, unit-converted. QA artifact
    ONLY -- see module docstring; not an SPEI input."""
    ds = _normalize_longitude(_open_series([Path(f) for f in nc_files]))
    var = _pick_var(ds, short_name)
    scale, offset, unit = _QA_UNIT[short_name]

    mean = (ds[var].mean(dim="time") * scale + offset).astype("float32")
    mean.name = f"{short_name}_period_mean"
    mean.attrs.update(
        variable=short_name,
        units=unit,
        period=f"{_START}/{_END}",
        n_years=N_YEARS,
        source=f"CDS projections-cmip6, {spei_variables()[short_name]}",
        model=model,
        note=(
            "PERIOD MEAN over 2041-2070 for QA/transparency only. NOT an SPEI "
            "input: SPEI needs the full daily series in the raw NetCDF under "
            "data/raw/climate/cds_spei/."
        ),
    )
    ds.close()
    return mean


def process_country_model_scenario(
    country: str, model: str, scenario: str, overwrite: bool = False
) -> dict:
    """Download + validate the raw daily series and write the QA period-mean
    rasters (native + 1 km) for every SPEI variable, for one
    country/model/scenario."""
    CLIMATE_PROCESSED.mkdir(parents=True, exist_ok=True)
    per_var: dict = {}
    all_ok = True

    for short_name in spei_variables():
        status = _download_raw(country, model, scenario, short_name, overwrite)
        if not status["success"]:
            per_var[short_name] = status
            all_ok = False
            continue

        nc_files = [Path(f) for f in status["files"]]
        validation = validate_raw_series(nc_files, short_name)

        native_path = native_raster_path(country, model, scenario, short_name)
        resampled_path = resampled_raster_path(country, model, scenario, short_name)

        if resampled_path.exists() and not overwrite:
            logger.info(
                "QA mean already written for %s/%s/%s/%s, skipping compute.",
                country, model, scenario, short_name,
            )
        else:
            native = _period_mean(nc_files, short_name, model)
            native = native.rio.set_spatial_dims(x_dim="lon", y_dim="lat", inplace=False)
            native = native.rio.write_crs(CRS_TARGET)
            native.rio.to_raster(native_path)

            resampled = _resample_to_1km(native, country)
            resampled.rio.to_raster(resampled_path)
            logger.info(
                "%s/%s/%s/%s: native %s %s, 1km %s %s",
                country, model, scenario, short_name,
                native_path.name, tuple(native.shape),
                resampled_path.name, tuple(resampled.shape),
            )

        per_var[short_name] = {
            **status,
            "validation": validation,
            "native_path": str(native_path),
            "resampled_path": str(resampled_path),
        }
        all_ok = all_ok and validation["valid"]

    return {"success": all_ok, "country": country, "model": model,
            "scenario": scenario, "variables": per_var}


def download_all_cds_precipitation(countries, overwrite: bool = False) -> dict:
    """Process every country x model x scenario. Report is nested
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
