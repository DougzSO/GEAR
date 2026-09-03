"""
Water stress — turn the WRI Aqueduct 4.0 basin CSV into two rasters per
country/scenario: a per-country Min-Max normalised layer (0-1) and the raw
physical layer (consumption-to-availability ratio).

Column: the continuous raw value ``{scenario}50_ws_x_r`` ("50" = the 2050
horizon; "_r" = raw ratio, not the WRI category ``_c``, label ``_l`` or the
WRI-normalised score ``_s``). The Min-Max normalisation here is ours, not a
reuse of WRI's.

WRI sentinel (RAW_SENTINEL_VALUE = 9999.0): a basin whose consumption exceeds
its available water is coded 9999 in the raw column. This is a real
"Extremely High" stress signal (WRI category 4, score 5.0), not missing data,
so those basins are NOT dropped from the dataset. But a literal 9999 in the
Min-Max pool would blow the maximum up and crush every real value (which top
out around ~30 for India) toward zero. Handling: 9999 is excluded from the
max calculation, then substituted with the real per-country max before
normalising — in BOTH outputs. In the normalised layer that is equivalent to
1.0; in the raw layer it means "the most extreme finite stress observed in
this country". Removing these basins would understate water stress precisely
where INVENTORY.md already flags the raw layer as least neutral between
countries (India).

Normalisation domain: Min-Max is computed PER COUNTRY, pooling the three
Aqueduct scenarios (bau, opt, pes) of that country together, never across
countries. "1.0" means "the most water-stressed basin observed in THIS
country, in any scenario" — not comparable in absolute terms between Brazil,
Portugal and India. The same convention is applied to the heat layer, so the
two stack consistently.

Output grid: reuses the exact grid (transform/shape/CRS) of an already
processed ``extreme_heat_days_{country}_{model}_{scenario}_1km.tif``, so the
two hazard layers align pixel for pixel. Requires the heat layer to have been
downloaded/processed first.

Pixels outside every basin polygon (ocean, gaps) stay NaN, never 0 — 0 would
mean "no water stress", which is not the same as "no basin mapped here".

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

WATER_STRESS_INDICATOR = "ws"
RAW_COLUMN_SUFFIX = "x_r"

RAW_UNITS = "consumption_to_availability_ratio"

# WRI's code for a non-finite consumption-to-availability ratio. Confirmed in
# the real India data: every 9999 row is WRI category 4 / score 5.0.
RAW_SENTINEL_VALUE = 9999.0


def normalized_raster_path(country: str, scenario: str) -> Path:
    return CLIMATE_PROCESSED / f"water_stress_{country}_{scenario}_1km.tif"


def raw_raster_path(country: str, scenario: str) -> Path:
    """Path to the raw physical layer (consumption-to-availability ratio),
    on the same grid as the normalised layer. Sentinel basins are clamped to
    the real per-country max. Uniform interface with
    ``heat_stress_processor.raw_raster_path``."""
    return CLIMATE_PROCESSED / f"water_stress_raw_{country}_{scenario}_1km.tif"


def _scenario_raw_column(scenario: str) -> str:
    return f"{scenario}{AQUEDUCT_YEAR_SUFFIX}_{WATER_STRESS_INDICATOR}_{RAW_COLUMN_SUFFIX}"


def _find_aqueduct_csv(country: str) -> Path:
    """Locate the consolidated Aqueduct CSV (``aqueduct_{year}.csv``, one file
    holding every scenario column). Raises ``FileNotFoundError`` if absent."""
    csv_path = CLIMATE_RAW / "aqueduct" / country / f"aqueduct_{YEAR_TARGET}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"No Aqueduct CSV for {country} at {csv_path}. Run the Aqueduct "
            f"downloader first."
        )
    return csv_path


def load_aqueduct_basins(country: str) -> gpd.GeoDataFrame:
    """Load the Aqueduct basin CSV (geometry in the ``.geo`` GeoJSON column)
    and return a GeoDataFrame with ``pfaf_id``, geometry, and the raw
    water-stress column for each scenario in ``AQUEDUCT_SCENARIOS`` (renamed
    to the bare scenario name). Basins with no geometry or no scenario value
    at all are dropped, with an explicit count."""
    csv_path = _find_aqueduct_csv(country)
    df = pd.read_csv(csv_path)

    raw_cols = {s: _scenario_raw_column(s) for s in AQUEDUCT_SCENARIOS}
    missing = [c for c in raw_cols.values() if c not in df.columns]
    if missing:
        raise ValueError(
            f"{csv_path} is missing expected columns {missing}. "
            f"Available (sample): {list(df.columns)[:20]}"
        )

    n_total = len(df)
    df["_geometry"] = df[".geo"].apply(
        lambda g: shapely_shape(json.loads(g)) if pd.notna(g) else None
    )
    all_na = df[list(raw_cols.values())].isna().all(axis=1)
    n_no_geom = int(df["_geometry"].isna().sum())
    n_no_data = int((all_na & df["_geometry"].notna()).sum())

    valid = df[df["_geometry"].notna() & ~all_na].copy()
    logger.info(
        "%s: %d/%d valid basins (%d without geometry, %d without any scenario value).",
        country, len(valid), n_total, n_no_geom, n_no_data,
    )

    return gpd.GeoDataFrame(
        valid[["pfaf_id"] + list(raw_cols.values())].rename(
            columns={v: k for k, v in raw_cols.items()}
        ),
        geometry=valid["_geometry"].values,
        crs=CRS_TARGET,
    )


def compute_country_minmax(
    country: str,
    scenarios: list[str] | None = None,
    basins: gpd.GeoDataFrame | None = None,
) -> tuple[float, float]:
    """Per-country Min-Max domain: the country's scenarios pooled together,
    never across countries. ``RAW_SENTINEL_VALUE`` is excluded from this
    calculation."""
    scenarios = scenarios or AQUEDUCT_SCENARIOS
    if basins is None:
        basins = load_aqueduct_basins(country)

    pooled = []
    for scenario in scenarios:
        values = pd.to_numeric(basins[scenario], errors="coerce").dropna()
        n_sentinel = int((values == RAW_SENTINEL_VALUE).sum())
        if n_sentinel:
            logger.info(
                "%s/%s: %d sentinel basin(s) (%s) excluded from the Min-Max pool.",
                country, scenario, n_sentinel, RAW_SENTINEL_VALUE,
            )
        pooled.append(values[values != RAW_SENTINEL_VALUE])

    combined = pd.concat(pooled, ignore_index=True)
    country_min, country_max = float(combined.min()), float(combined.max())
    logger.info(
        "%s: normalisation domain (scenarios %s pooled, per country, sentinel-free): "
        "min=%.6g max=%.6g (n=%d).",
        country, scenarios, country_min, country_max, len(combined),
    )
    return country_min, country_max


def _load_reference_grid(country: str, model: str | None = None) -> xr.DataArray:
    """Load the grid (transform/shape/CRS) of an already processed heat
    raster; water is rasterised onto exactly this grid. The 1 km grid depends
    only on the country bounds and target resolution, so it is identical
    across models and scenarios — the first configured model / ssp126 is used
    arbitrarily."""
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
    country_min: float,
    country_max: float,
    basins: gpd.GeoDataFrame | None = None,
    model: str | None = None,
) -> tuple[xr.DataArray, xr.DataArray]:
    """Rasterise the raw values of ``scenario`` onto the reference grid and
    apply per-country Min-Max normalisation. Sentinel basins are substituted
    with ``country_max`` before both outputs are formed. Pixels outside every
    basin stay NaN.

    Returns ``(normalized, raw)`` on the same grid. ``raw`` is the rasterised
    physical value captured before the normalisation line — not the Min-Max
    inverted afterwards.
    """
    if basins is None:
        basins = load_aqueduct_basins(country)

    ref = _load_reference_grid(country, model)
    transform = ref.rio.transform()
    out_shape = ref.shape

    values = pd.to_numeric(basins[scenario], errors="coerce")
    n_sentinel = int((values == RAW_SENTINEL_VALUE).sum())
    values_sub = values.where(values != RAW_SENTINEL_VALUE, country_max)

    valid = values_sub.notna()
    shapes = list(zip(basins.geometry[valid], values_sub[valid]))

    raw_raster = rasterize(
        shapes=shapes,
        out_shape=out_shape,
        transform=transform,
        fill=np.nan,
        dtype="float64",
    )

    normalized = np.clip(
        (raw_raster - country_min) / (country_max - country_min), 0.0, 1.0
    ).astype("float32")

    common_attrs = {
        "source": "WRI Aqueduct 4.0 future_annual, indicator ws (water stress), raw ratio",
        "aqueduct_scenario": scenario,
        "aqueduct_scenario_ssp": AQUEDUCT_TO_SSP_LABEL.get(scenario, "unknown"),
        "year_horizon": YEAR_TARGET,
        "country": country,
        "n_sentinel_clipped_to_max": n_sentinel,
    }

    da_raw = xr.DataArray(
        raw_raster.astype("float32"), dims=("y", "x"),
        coords={"y": ref["y"], "x": ref["x"]}, name="water_stress_raw",
    ).rio.write_crs(CRS_TARGET)
    da_raw.attrs.update(
        **common_attrs,
        units=RAW_UNITS,
        normalization="none — raw physical ratio, captured before Min-Max; "
                      "comparable in absolute terms between countries",
        note="Consumption-to-availability ratio per basin. Sentinel (WRI 9999) "
             "basins carry this country's real max. NaN = outside any mapped basin.",
    )

    da_norm = xr.DataArray(
        normalized, dims=("y", "x"),
        coords={"y": ref["y"], "x": ref["x"]}, name="water_stress_normalized",
    ).rio.write_crs(CRS_TARGET)
    da_norm.attrs.update(
        **common_attrs,
        normalization="per-country Min-Max (this country's scenarios pooled, "
                      "not across countries)",
        country_min=country_min,
        country_max=country_max,
        note="0 = least water-stressed basin observed in this country (any "
             "scenario); 1 = most stressed (sentinel basins clipped to the real "
             "country max). Not comparable in absolute terms across countries. "
             "NaN = outside any mapped basin.",
    )
    return da_norm, da_raw


def process_country_scenario(
    country: str,
    scenario: str,
    country_min: float,
    country_max: float,
    basins: gpd.GeoDataFrame | None = None,
    overwrite: bool = False,
    model: str | None = None,
) -> dict:
    """Rasterise, normalise and write both layers for one country/scenario.
    The normalised raster is only (re)written when it was not already
    cached — the raw layer likewise."""
    CLIMATE_PROCESSED.mkdir(parents=True, exist_ok=True)
    out_path = normalized_raster_path(country, scenario)
    raw_path = raw_raster_path(country, scenario)

    norm_cached = out_path.exists() and not overwrite
    raw_cached = raw_path.exists() and not overwrite
    if norm_cached and raw_cached:
        logger.info("%s/%s: water stress already processed, skipping.", country, scenario)
        return {
            "success": True, "path": str(out_path), "reason": "cached",
            "raw_path": str(raw_path), "raw_units": RAW_UNITS, "raw_kind": "computed",
        }

    try:
        da_norm, da_raw = rasterize_scenario(
            country, scenario, country_min, country_max, basins=basins, model=model
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
            "%s/%s: saved %s - %s, %d valid px, mean=%.3f (raw %s..%s %s)",
            country, scenario, out_path.name, da_norm.shape, len(valid), float(valid.mean()),
            f"{float(raw_valid.min()):.3g}", f"{float(raw_valid.max()):.3g}", RAW_UNITS,
        )
    else:
        logger.warning("%s/%s: saved %s but 0 valid pixels (all NaN).", country, scenario, out_path.name)

    return {
        "success": True, "path": str(out_path), "reason": "processed",
        "shape": list(da_norm.shape), "raw_path": str(raw_path),
        "raw_units": RAW_UNITS, "raw_kind": "computed",
    }


def process_all_countries(
    countries: list[str] | None = None,
    scenarios: list[str] | None = None,
    overwrite: bool = False,
) -> dict:
    countries = countries or COUNTRIES
    scenarios = scenarios or AQUEDUCT_SCENARIOS

    report = {"normalization_domain": "per_country", "countries": {}}
    for country in countries:
        basins = load_aqueduct_basins(country)
        country_min, country_max = compute_country_minmax(country, scenarios, basins=basins)
        report["countries"][country] = {
            "country_min": country_min,
            "country_max": country_max,
            "scenarios": {},
        }
        for scenario in scenarios:
            report["countries"][country]["scenarios"][scenario] = process_country_scenario(
                country, scenario, country_min, country_max, basins=basins, overwrite=overwrite
            )
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--countries", nargs="+", default=None)
    parser.add_argument("--scenarios", nargs="+", default=None, choices=AQUEDUCT_SCENARIOS)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    result = process_all_countries(
        countries=args.countries, scenarios=args.scenarios, overwrite=args.overwrite
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    ok = all(
        s["success"]
        for c in result["countries"].values()
        for s in c["scenarios"].values()
    )
    sys.exit(0 if ok else 1)
