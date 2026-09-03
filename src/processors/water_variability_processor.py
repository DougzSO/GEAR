"""
Water variability — turn the WRI Aqueduct 4.0 basin CSV into two rasters per
country/scenario for each of two indicators: a per-country Min-Max normalised
layer (0-1) and the raw physical layer.

Indicators (both from the SAME ``aqueduct_{year}.csv`` the water-stress
processor reads — different columns):

* ``sv`` — seasonal variability: the ``{scenario}50_sv_x_r`` column,
  variation in blue-water supply *between months of a year*.
* ``iv`` — interannual variability: the ``{scenario}50_iv_x_r`` column,
  variation in blue-water supply *between years*.

Both raw values are dimensionless variability coefficients (std / mean of
supply). Observed ranges over the three study countries: ``sv`` ~0.06-1.6,
``iv`` ~0.14-3.1.

**No log transform, no sentinel.** This module does plain linear per-country
Min-Max, exactly like ``water_stress_processor``. Unlike ``ws``/``wd``,
``sv``/``iv`` carry no WRI ``9999`` sentinel (they are coefficients, not
consumption/availability ratios), so the sentinel-substitution machinery is
absent here. The ``log1p`` option discussed for ``ws``/heat in
``analysis/climate_risk_score_spec.md`` is NOT applied: ``sv``/``iv`` are
near-symmetric to mildly skewed (``analysis/aqueduct_indicator_correlation.md``
task 4), so a log would over-correct. Any log/other transform for the unified
score is applied downstream, never in this processor.

Normalisation domain: Min-Max PER COUNTRY, PER INDICATOR, pooling the three
Aqueduct scenarios (bau, opt, pes) of that country together, never across
countries and never across indicators. ``sv`` and ``iv`` get independent
``(min, max)`` pools. "1.0" means "the most variable basin observed in THIS
country for THIS indicator, in any scenario" — not comparable in absolute
terms between countries. Same convention as the water-stress and heat layers.

Output grid: reuses the exact grid (transform/shape/CRS) of an already
processed ``extreme_heat_days_{country}_{model}_{scenario}_1km.tif``, so every
hazard layer aligns pixel for pixel. Requires the heat layer processed first.

Pixels outside every basin polygon stay NaN, never 0.

This module produces the raster layers only. It does not extract per-plant
values or combine hazards — that belongs to the not-yet-built index layer.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rioxarray  # noqa: F401 - registers the .rio accessor
import xarray as xr
from rasterio.features import rasterize
from shapely.geometry import shape as shapely_shape

from src.config import (
    AQUEDUCT_SCENARIOS,
    AQUEDUCT_TO_SSP_LABEL,
    CLIMATE_PROCESSED,
    CLIMATE_RAW,
    COUNTRIES,
    CRS_TARGET,
    YEAR_TARGET,
)
from src.downloaders.cds_tasmax_downloader import configured_models, resampled_raster_path

logger = logging.getLogger(__name__)

# "50" = the 2050 horizon. Aqueduct 4.0 future_annual only has 2030/2050/2080
# ("30"/"50"/"80"); "50" is the one that matches YEAR_TARGET and the heat layer.
AQUEDUCT_YEAR_SUFFIX = "50"
assert YEAR_TARGET == 2050, (
    "AQUEDUCT_YEAR_SUFFIX='50' is pinned to YEAR_TARGET=2050 (the only Aqueduct "
    "4.0 horizon for that target). If YEAR_TARGET changes, update this too."
)

RAW_COLUMN_SUFFIX = "x_r"

# The two variability indicators handled here.
INDICATORS = ("sv", "iv")
INDICATOR_FILE_NAME = {"sv": "seasonal_variability", "iv": "interannual_variability"}
INDICATOR_LABEL = {"sv": "seasonal variability", "iv": "interannual variability"}

RAW_UNITS = "variability_coefficient_dimensionless"

# sv/iv are coefficients of variation; there is no WRI 9999 sentinel for them.
# A value this large would be physically absurd and almost certainly a parsing
# or source error — fail loud rather than silently poisoning the Min-Max pool.
SANITY_CEILING = 50.0


def _check_indicator(indicator: str) -> str:
    if indicator not in INDICATORS:
        raise ValueError(f"indicator must be one of {INDICATORS}, got {indicator!r}")
    return indicator


def normalized_raster_path(country: str, scenario: str, indicator: str) -> Path:
    _check_indicator(indicator)
    name = INDICATOR_FILE_NAME[indicator]
    return CLIMATE_PROCESSED / f"{name}_{country}_{scenario}_1km.tif"


def raw_raster_path(country: str, scenario: str, indicator: str) -> Path:
    """Path to the raw physical layer (dimensionless variability coefficient),
    on the same grid as the normalised layer. Uniform interface with
    ``water_stress_processor.raw_raster_path`` / ``heat_stress_processor``."""
    _check_indicator(indicator)
    name = INDICATOR_FILE_NAME[indicator]
    return CLIMATE_PROCESSED / f"{name}_raw_{country}_{scenario}_1km.tif"


def _scenario_raw_column(scenario: str, indicator: str) -> str:
    return f"{scenario}{AQUEDUCT_YEAR_SUFFIX}_{indicator}_{RAW_COLUMN_SUFFIX}"


def _find_aqueduct_csv(country: str) -> Path:
    """Locate the consolidated Aqueduct CSV (``aqueduct_{year}.csv``, one file
    holding every scenario/indicator column). Raises ``FileNotFoundError`` if
    absent."""
    csv_path = CLIMATE_RAW / "aqueduct" / country / f"aqueduct_{YEAR_TARGET}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"No Aqueduct CSV for {country} at {csv_path}. Run the Aqueduct "
            f"downloader first."
        )
    return csv_path


def load_aqueduct_basins(country: str) -> gpd.GeoDataFrame:
    """Load the Aqueduct basin CSV (geometry in the ``.geo`` GeoJSON column)
    and return a GeoDataFrame with ``pfaf_id``, geometry, and the raw sv/iv
    columns for each scenario in ``AQUEDUCT_SCENARIOS``, renamed to
    ``{indicator}_{scenario}`` (e.g. ``sv_bau``, ``iv_pes``). Basins with no
    geometry, or no value at all across every sv/iv column, are dropped with
    an explicit count."""
    csv_path = _find_aqueduct_csv(country)
    df = pd.read_csv(csv_path)

    raw_cols = {
        (ind, s): _scenario_raw_column(s, ind)
        for ind in INDICATORS
        for s in AQUEDUCT_SCENARIOS
    }
    missing = [c for c in raw_cols.values() if c not in df.columns]
    if missing:
        raise ValueError(
            f"{csv_path} is missing expected columns {missing}. "
            f"Available (sample): {list(df.columns)[:20]}"
        )

    n_total = len(df)
    geom = df[".geo"].apply(
        lambda g: shapely_shape(json.loads(g)) if pd.notna(g) else None
    )
    numeric = df[list(raw_cols.values())].apply(pd.to_numeric, errors="coerce")
    numeric.columns = [f"{ind}_{s}" for (ind, s) in raw_cols]

    arr = numeric.to_numpy()
    if np.isfinite(arr).any():
        over = float(np.nanmax(np.abs(arr)))
        if over > SANITY_CEILING:
            raise ValueError(
                f"{csv_path}: a sv/iv value of {over:g} exceeds the sanity ceiling "
                f"{SANITY_CEILING}. sv/iv are coefficients of variation (~0-3 in "
                f"the study data) and carry no WRI sentinel — this is a source or "
                f"parsing error, not a real value."
            )

    all_na = numeric.isna().all(axis=1)
    n_no_geom = int(geom.isna().sum())
    n_no_data = int((all_na & geom.notna()).sum())

    keep = geom.notna().to_numpy() & ~all_na.to_numpy()
    out = numeric.loc[keep].reset_index(drop=True)
    out.insert(0, "pfaf_id", df.loc[keep, "pfaf_id"].to_numpy())
    logger.info(
        "%s: %d/%d valid basins (%d without geometry, %d without any sv/iv value).",
        country, int(keep.sum()), n_total, n_no_geom, n_no_data,
    )
    return gpd.GeoDataFrame(out, geometry=geom[keep].to_numpy(), crs=CRS_TARGET)


def compute_country_minmax(
    country: str,
    indicator: str,
    scenarios: list[str] | None = None,
    basins: gpd.GeoDataFrame | None = None,
) -> tuple[float, float]:
    """Per-country, per-indicator Min-Max domain: the country's scenarios of
    ONE indicator pooled together, never across countries and never across
    indicators."""
    _check_indicator(indicator)
    scenarios = scenarios or AQUEDUCT_SCENARIOS
    if basins is None:
        basins = load_aqueduct_basins(country)

    pooled = [
        pd.to_numeric(basins[f"{indicator}_{scenario}"], errors="coerce").dropna()
        for scenario in scenarios
    ]
    combined = pd.concat(pooled, ignore_index=True)
    country_min, country_max = float(combined.min()), float(combined.max())
    logger.info(
        "%s/%s: normalisation domain (scenarios %s pooled, per country): "
        "min=%.6g max=%.6g (n=%d).",
        country, indicator, scenarios, country_min, country_max, len(combined),
    )
    return country_min, country_max


def _load_reference_grid(country: str, model: str | None = None) -> xr.DataArray:
    """Load the grid (transform/shape/CRS) of an already processed heat
    raster; variability is rasterised onto exactly this grid, identical to the
    water-stress and heat layers. The 1 km grid depends only on the country
    bounds and target resolution, so it is model/scenario independent — the
    first configured model / ssp126 is used arbitrarily."""
    model = model or configured_models()[0]
    ref_path = resampled_raster_path(country, model, "ssp126")
    if not ref_path.exists():
        raise FileNotFoundError(
            f"Reference grid not found: {ref_path}. Process the extreme-heat "
            f"layer first (its grid is reused here)."
        )
    da = rioxarray.open_rasterio(ref_path)
    return da.isel(band=0) if "band" in da.dims else da


def rasterize_scenario(
    country: str,
    scenario: str,
    indicator: str,
    country_min: float,
    country_max: float,
    basins: gpd.GeoDataFrame | None = None,
    model: str | None = None,
) -> tuple[xr.DataArray, xr.DataArray]:
    """Rasterise the raw ``indicator`` values of ``scenario`` onto the
    reference grid and apply per-country Min-Max normalisation. Pixels outside
    every basin stay NaN.

    Returns ``(normalized, raw)`` on the same grid. ``raw`` is the rasterised
    physical value captured before the normalisation line — not the Min-Max
    inverted afterwards.
    """
    _check_indicator(indicator)
    if basins is None:
        basins = load_aqueduct_basins(country)

    ref = _load_reference_grid(country, model)
    transform = ref.rio.transform()
    out_shape = ref.shape

    values = pd.to_numeric(basins[f"{indicator}_{scenario}"], errors="coerce")
    valid = values.notna()
    shapes = list(zip(basins.geometry[valid], values[valid]))

    raw_raster = rasterize(
        shapes=shapes,
        out_shape=out_shape,
        transform=transform,
        fill=np.nan,
        dtype="float64",
    )

    span = country_max - country_min
    if span <= 0:
        normalized = np.where(np.isnan(raw_raster), np.nan, 0.0).astype("float32")
    else:
        normalized = np.clip(
            (raw_raster - country_min) / span, 0.0, 1.0
        ).astype("float32")

    common_attrs = {
        "source": (
            f"WRI Aqueduct 4.0 future_annual, indicator {indicator} "
            f"({INDICATOR_LABEL[indicator]}), raw coefficient"
        ),
        "aqueduct_indicator": indicator,
        "aqueduct_scenario": scenario,
        "aqueduct_scenario_ssp": AQUEDUCT_TO_SSP_LABEL.get(scenario, "unknown"),
        "year_horizon": YEAR_TARGET,
        "country": country,
    }

    da_raw = xr.DataArray(
        raw_raster.astype("float32"), dims=("y", "x"),
        coords={"y": ref["y"], "x": ref["x"]},
        name=f"{INDICATOR_FILE_NAME[indicator]}_raw",
    ).rio.write_crs(CRS_TARGET)
    da_raw.attrs.update(
        **common_attrs,
        units=RAW_UNITS,
        normalization="none — raw variability coefficient, captured before "
                      "Min-Max; comparable in absolute terms between countries",
        note=f"Dimensionless {INDICATOR_LABEL[indicator]} coefficient per basin "
             f"(std / mean of blue-water supply). No WRI sentinel applies. "
             f"NaN = outside any mapped basin.",
    )

    da_norm = xr.DataArray(
        normalized, dims=("y", "x"),
        coords={"y": ref["y"], "x": ref["x"]},
        name=f"{INDICATOR_FILE_NAME[indicator]}_normalized",
    ).rio.write_crs(CRS_TARGET)
    da_norm.attrs.update(
        **common_attrs,
        normalization="per-country, per-indicator Min-Max (this country's "
                      "scenarios pooled, not across countries or indicators)",
        country_min=country_min,
        country_max=country_max,
        note=f"0 = least variable basin observed in this country for "
             f"{INDICATOR_LABEL[indicator]} (any scenario); 1 = most variable. "
             f"Not comparable in absolute terms across countries. "
             f"NaN = outside any mapped basin.",
    )
    return da_norm, da_raw


def process_country_scenario(
    country: str,
    scenario: str,
    indicator: str,
    country_min: float,
    country_max: float,
    basins: gpd.GeoDataFrame | None = None,
    overwrite: bool = False,
    model: str | None = None,
) -> dict:
    """Rasterise, normalise and write both layers for one
    country/scenario/indicator. Each raster is only (re)written when it was
    not already cached."""
    _check_indicator(indicator)
    CLIMATE_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = normalized_raster_path(country, scenario, indicator)
    raw_path = raw_raster_path(country, scenario, indicator)

    norm_cached = out_path.exists() and not overwrite
    raw_cached = raw_path.exists() and not overwrite
    if norm_cached and raw_cached:
        logger.info(
            "%s/%s/%s: water variability already processed, skipping.",
            country, scenario, indicator,
        )
        return {
            "success": True, "path": str(out_path), "reason": "cached",
            "raw_path": str(raw_path), "raw_units": RAW_UNITS, "raw_kind": "computed",
        }

    try:
        da_norm, da_raw = rasterize_scenario(
            country, scenario, indicator, country_min, country_max,
            basins=basins, model=model,
        )
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return {"success": False, "path": None, "reason": f"missing_dependency: {exc}"}

    if not norm_cached:
        da_norm.rio.to_raster(out_path)
    if not raw_cached:
        da_raw.rio.to_raster(raw_path)

    valid = da_norm.values[~np.isnan(da_norm.values)]
    if len(valid):
        raw_valid = da_raw.values[~np.isnan(da_raw.values)]
        logger.info(
            "%s/%s/%s: saved %s - %s, %d valid px, mean=%.3f (raw %s..%s)",
            country, scenario, indicator, out_path.name, da_norm.shape, len(valid),
            float(valid.mean()), f"{float(raw_valid.min()):.3g}",
            f"{float(raw_valid.max()):.3g}",
        )
    else:
        logger.warning(
            "%s/%s/%s: saved %s but 0 valid pixels (all NaN).",
            country, scenario, indicator, out_path.name,
        )

    return {
        "success": True, "path": str(out_path), "reason": "processed",
        "shape": list(da_norm.shape), "raw_path": str(raw_path),
        "raw_units": RAW_UNITS, "raw_kind": "computed",
    }


def process_all_countries(
    countries: list[str] | None = None,
    scenarios: list[str] | None = None,
    indicators: list[str] | None = None,
    overwrite: bool = False,
) -> dict:
    countries = countries or COUNTRIES
    scenarios = scenarios or AQUEDUCT_SCENARIOS
    indicators = indicators or list(INDICATORS)
    for indicator in indicators:
        _check_indicator(indicator)

    report = {"normalization_domain": "per_country_per_indicator", "countries": {}}
    for country in countries:
        basins = load_aqueduct_basins(country)
        report["countries"][country] = {}
        for indicator in indicators:
            country_min, country_max = compute_country_minmax(
                country, indicator, scenarios, basins=basins
            )
            entry = {
                "country_min": country_min,
                "country_max": country_max,
                "scenarios": {},
            }
            for scenario in scenarios:
                entry["scenarios"][scenario] = process_country_scenario(
                    country, scenario, indicator, country_min, country_max,
                    basins=basins, overwrite=overwrite,
                )
            report["countries"][country][indicator] = entry
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--countries", nargs="+", default=None)
    parser.add_argument("--scenarios", nargs="+", default=None, choices=AQUEDUCT_SCENARIOS)
    parser.add_argument("--indicators", nargs="+", default=None, choices=list(INDICATORS))
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    result = process_all_countries(
        countries=args.countries,
        scenarios=args.scenarios,
        indicators=args.indicators,
        overwrite=args.overwrite,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    ok = all(
        s["success"]
        for c in result["countries"].values()
        for ind in c.values()
        for s in ind["scenarios"].values()
    )
    sys.exit(0 if ok else 1)
