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
CMIP6 model and both scenarios (ssp126, ssp585) of that country jointly into
one domain. Never pooled across countries. "1.0" means "the hottest cell
observed in THIS country, in any model, in any scenario" — not comparable in
absolute terms between countries. Outputs stay model-tagged
(``heat_stress_{country}_{model}_{scenario}_1km.tif``) but share the single
country domain.

An earlier revision made the domain per-model. That is reverted: joint
pooling is the design originally specified for this layer. Whether to switch
back to per-model normalisation once a real second GCM exists is an open
question tied to verification item V4 (ARCHITECTURE.md Section 4), not
resolved here.

Grid guard: joint pooling and a shared normalisation domain are only valid
if every pooled raster sits on the same grid. Before pooling,
``_assert_consistent_grid`` raises ``GridMismatchError`` (never a silent
pass) if the model rasters disagree on shape, resolution/transform or CRS.
With one model configured this is a no-op; it exists so that adding the
second GCM under V4 fails loudly instead of misaligning the stack.

Multiple GCMs: this module iterates over every model in
``cds_tasmax_downloader.configured_models()``.

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

logger = logging.getLogger(__name__)

RAW_UNITS = "days_per_year_with_tasmax_gt_40C"

# Absolute tolerance on the six affine-transform coefficients when comparing
# grids. The 1 km grid is derived by nearest-neighbour resampling from a fixed
# country bounding box, so matching model rasters are bit-identical; this only
# guards against a genuinely different grid slipping in.
_TRANSFORM_ATOL = 1e-9


class GridMismatchError(ValueError):
    """Raised when the model rasters that would be pooled into one Min-Max
    domain are not on the same grid (shape, resolution/transform or CRS).
    Joint per-country pooling and a shared normalisation domain are invalid
    on mismatched grids, and the normalised stack would be silently
    misaligned. Fail loud instead."""


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


def _grid_signature(da: xr.DataArray) -> tuple:
    """(shape, transform coefficients, CRS) — everything that defines the
    grid a raster sits on."""
    transform = tuple(float(v) for v in tuple(da.rio.transform())[:6])
    return tuple(da.shape), transform, str(da.rio.crs)


def _assert_consistent_grid(
    country: str, rasters: dict[tuple[str, str], xr.DataArray]
) -> None:
    """Fail loudly if the rasters to be pooled disagree on grid shape,
    resolution/transform or CRS. No-op for a single raster."""
    items = list(rasters.items())
    ref_key, ref_da = items[0]
    ref_shape, ref_transform, ref_crs = _grid_signature(ref_da)

    problems: list[str] = []
    for key, da in items[1:]:
        shape, transform, crs = _grid_signature(da)
        if shape != ref_shape:
            problems.append(f"{key} shape {shape} != {ref_shape} {ref_key}")
        elif not np.allclose(transform, ref_transform, rtol=0.0, atol=_TRANSFORM_ATOL):
            problems.append(
                f"{key} transform {transform} != {ref_transform} {ref_key}"
            )
        if crs != ref_crs:
            problems.append(f"{key} CRS {crs} != {ref_crs} {ref_key}")

    if problems:
        raise GridMismatchError(
            f"{country}: heat rasters to be pooled into one Min-Max domain are "
            f"on inconsistent grids — joint pooling is invalid until this is "
            f"fixed:\n  " + "\n  ".join(problems)
        )


def _load_country_rasters(
    country: str,
    models: list[str] | None = None,
    scenarios: list[str] | None = None,
) -> dict[tuple[str, str], xr.DataArray]:
    """Open every ``(model, scenario)`` raster for ``country`` and assert they
    share one grid before any of them is used."""
    models = models or configured_models()
    scenarios = scenarios or CMIP6_SCENARIOS

    rasters = {
        (model, scenario): _load_heat_raster(country, model, scenario)
        for model in models
        for scenario in scenarios
    }
    _assert_consistent_grid(country, rasters)
    return rasters


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
