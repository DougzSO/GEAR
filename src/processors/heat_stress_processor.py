"""
Extreme heat — turn the ``extreme_heat_days_{country}_{model}_{scenario}_1km``
rasters (mean days/year with tasmax > 40 C) into a per-country Min-Max
normalised layer (0-1). Analogous to ``water_stress_processor``.

Raw layer: for heat the raw physical value already exists on disk — the
``extreme_heat_days_*_1km.tif`` written by the downloader, on the exact grid
this module normalises. So the raw layer is a passthrough by reference, not a
recomputed or copied output. ``raw_raster_path`` points straight at that
file. Unit: days per year (0 to ~365; observed 0-173, India ssp585).

Normalisation domain: Min-Max computed PER COUNTRY, pooling every configured
CMIP6 model and every scenario in ``config.CMIP6_SCENARIOS`` (ssp126, ssp370,
ssp585) of that country jointly into one domain. Never pooled across
countries. "1.0" means "the hottest cell observed in THIS country, in any
model, in any scenario" — not comparable in absolute terms between countries.
Outputs stay model-tagged (``heat_stress_{country}_{model}_{scenario}_1km.tif``)
but share the single country domain. Joint (not per-model) pooling is the
design specified for this layer -- see ``docs/DECISIONS.md`` for the history.

Grid guard: joint pooling and a shared normalisation domain are only valid
if every pooled raster sits on the same grid. Before pooling, the shared
guard in ``src/processors/_common.py`` (``assert_consistent_grid``) raises
``GridMismatchError`` (never a silent pass) if the model/scenario rasters
disagree on shape, resolution/transform or CRS -- it caught, and forced the
fix of, a real grid-offset bug between GFDL-ESM4 and MIROC6
(``docs/DECISIONS.md``, V4). ``spei_processor`` uses the identical guard.

Multiple GCMs: this module iterates over every model in
``cds_tasmax_downloader.configured_models()`` (GFDL-ESM4 + MIROC6).

No sentinel value — a day count is a direct count, no source-specific code to
handle. NaN at the raster edges (outside the country boundary, inside the
download bbox) is preserved, never turned into 0.

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

from src.config import CLIMATE_PROCESSED, CMIP6_SCENARIOS, COUNTRIES
from src.downloaders.cds_tasmax_downloader import configured_models, resampled_raster_path
from src.processors._common import load_country_rasters
from src.processors._common import GridMismatchError  # noqa: F401 - re-exported for callers/tests

logger = logging.getLogger(__name__)

RAW_UNITS = "days_per_year_with_tasmax_gt_40C"

# The grid-consistency guard (GridMismatchError, the transform tolerance, the
# signature comparison) lives in src/processors/_common.py -- spei_processor
# shares the identical guard.


def normalized_raster_path(country: str, model: str, scenario: str) -> Path:
    return CLIMATE_PROCESSED / f"heat_stress_{country}_{model}_{scenario}_1km.tif"


def raw_raster_path(country: str, model: str, scenario: str) -> Path:
    """Path to the raw heat layer (days/year with tasmax > 40 C). This is NOT
    a new output of this module — it is the ``extreme_heat_days_*_1km.tif``
    the downloader already produced, on the same grid as the normalised
    raster. Passthrough by reference, no copy or recompute. Uniform interface
    with ``water_stress_processor.raw_raster_path``."""
    return resampled_raster_path(country, model, scenario)


def _load_heat_raster(country: str, model: str, scenario: str) -> xr.DataArray:
    path = raw_raster_path(country, model, scenario)
    if not path.exists():
        raise FileNotFoundError(
            f"Extreme-heat raster not found: {path}. Run the CDS tasmax "
            f"downloader first."
        )
    da = rioxarray.open_rasterio(path)
    return da.isel(band=0) if "band" in da.dims else da


def _load_country_rasters(
    country: str,
    models: list[str] | None = None,
    scenarios: list[str] | None = None,
) -> dict[tuple[str, str], xr.DataArray]:
    """Open every ``(model, scenario)`` heat raster for ``country`` and assert
    they share one grid before any of them is used (``_common``'s shared
    guard, identical to ``spei_processor``'s)."""
    return load_country_rasters(
        country, _load_heat_raster,
        models or configured_models(), scenarios or CMIP6_SCENARIOS,
    )


def compute_country_minmax(
    country: str,
    models: list[str] | None = None,
    scenarios: list[str] | None = None,
    rasters: dict[tuple[str, str], xr.DataArray] | None = None,
) -> tuple[float, float]:
    """Per-country Min-Max domain: every configured model and both scenarios
    of this country pooled jointly, never across countries. Grid consistency
    across the pooled rasters is asserted first."""
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
    country: str,
    model: str,
    scenario: str,
    country_min: float,
    country_max: float,
    da: xr.DataArray | None = None,
) -> xr.DataArray:
    """Per-country Min-Max normalisation of one heat raster against the shared
    country domain. NaN at the edges of the source raster propagates through
    the arithmetic and is never turned into 0."""
    if da is None:
        da = _load_heat_raster(country, model, scenario)
    values = da.values.astype("float64")

    normalized = np.clip(
        (values - country_min) / (country_max - country_min), 0.0, 1.0
    ).astype("float32")

    out = xr.DataArray(
        normalized, dims=da.dims, coords=da.coords, name="heat_stress_normalized"
    ).rio.write_crs(da.rio.crs)
    out.attrs.update(
        source="CDS daily tasmax (CMIP6), indicator days/year with tasmax > 40 C, 1 km grid",
        cmip6_model=model,
        cmip6_scenario=scenario,
        normalization="per-country Min-Max (this country's models and scenarios "
                      "pooled jointly, not across countries)",
        country=country,
        country_min=country_min,
        country_max=country_max,
        note="0 = coolest cell observed in this country (any model, any "
             "scenario); 1 = hottest. Not comparable in absolute terms across "
             "countries. NaN = outside the country boundary (preserved from source).",
    )
    return out


def process_country_model_scenario(
    country: str,
    model: str,
    scenario: str,
    country_min: float,
    country_max: float,
    da: xr.DataArray | None = None,
    overwrite: bool = False,
) -> dict:
    """Normalise and write the heat layer for one country/model/scenario
    against the shared country domain. The raw layer is the existing
    downloader output, referenced not rewritten."""
    CLIMATE_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = normalized_raster_path(country, model, scenario)
    raw_path = raw_raster_path(country, model, scenario)
    raw_meta = {
        "raw_path": str(raw_path),
        "raw_kind": "passthrough_existing",
        "raw_units": RAW_UNITS,
    }

    if out_path.exists() and not overwrite:
        logger.info("%s/%s/%s: heat stress already processed, skipping.", country, model, scenario)
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
        try:
            rasters = _load_country_rasters(country, models, scenarios)
        except FileNotFoundError as exc:
            logger.error(str(exc))
            report["countries"][country] = {"success": False, "reason": f"missing_dependency: {exc}"}
            continue

        country_min, country_max = compute_country_minmax(country, rasters=rasters)
        report["countries"][country] = {
            "country_min": country_min,
            "country_max": country_max,
            "models": {},
        }
        for model in models:
            report["countries"][country]["models"][model] = {"scenarios": {}}
            for scenario in scenarios:
                report["countries"][country]["models"][model]["scenarios"][scenario] = (
                    process_country_model_scenario(
                        country, model, scenario, country_min, country_max,
                        da=rasters[(model, scenario)], overwrite=overwrite,
                    )
                )
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
