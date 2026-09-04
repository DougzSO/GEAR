"""
EM-DAT x Hazard spatial overlay validation (C6, exploratory/diagnostic).

Approved by Douglas (2026-09-04) after a feasibility report (see
``src/visualization/tables.py``'s ``C6_INVESTIGATION_NOTE`` for the
pre-approval version of this finding). This module does **not** feed back
into ``Hazard``/``CCRS`` -- it is a one-way diagnostic cross-check of
whether the Hazard raster fields agree, spatially, with where EM-DAT
recorded a climate disaster, at admin-1 polygon granularity: the only
granularity EM-DAT's structured geocoding ("GADM Admin Units") supports at
usable coverage.

--------------------------------------------------------------------------
Coverage -- read before trusting any p-value this module produces
--------------------------------------------------------------------------
Per ``data/outputs/inspection/emdat_coverage.csv``
(``src/downloaders/emdat_downloader.py``'s ``coverage_report``): point-level
Latitude/Longitude covers only 5.3-12.1% of events (Portugal: 2 events) --
unusable for a point overlay. The structured "GADM Admin Units" field covers
50.3-52.6% of events across all three countries -- enough for an
admin-1-polygon-level overlay, the granularity used here. The other
~47-50% of events (no structured geocoding at all) are silently excluded
from every group in this module -- a REAL sample-selection gap, not a
random subsample (better-documented/urban disasters are plausibly
over-represented in the geocoded half). Every p-value produced here answers
"do the GEOCODED events line up with the hazard field", never "do ALL
EM-DAT events line up" -- a narrower claim, repeated on every figure this
module's companion (``src/visualization/emdat_validation.py``) produces,
not just in this docstring.

--------------------------------------------------------------------------
"GADM Admin Units" field -- mixed granularity, resolved to admin-1
--------------------------------------------------------------------------
The field is a JSON array of ``{"gid_<level>": "...", ...}`` objects. Level
varies per event: some give an admin-1 GID directly (level 1, e.g.
``"BRA.5_1"``), most give admin-2 / municipality (level 2, e.g.
``"BRA.19.68_2"``), a few give only admin-0 / country (level 0, too coarse
to place on a specific polygon -- dropped). ``_resolve_admin1_gid``
truncates any level >= 1 GID to its admin-1 parent (the first two
dot-separated segments), so every event lands on the same admin-1 grid the
CCRS boundary layer uses (``GID_1`` in the GADM 4.1 ``ADM_ADM_1`` layer).
This mixed-granularity format was **not** anticipated in the pre-approval
feasibility report (which assumed one granularity) -- discovered while
implementing this module, documented here rather than silently handled.

--------------------------------------------------------------------------
Disaster-type -> Hazard-term mapping -- best available proxy, not a
physical match, reported as a caveat, not fixed here
--------------------------------------------------------------------------
    Extreme temperature -> heat   (T_heat's underlying raw raster)
    Drought              -> spei  (spei_freq's underlying raw raster)
    Flood                -> ws    (water STRESS raster -- scarcity, not
                                    excess water; the only water-side raster
                                    this system has. Kept because there is
                                    no flood/excess-water term in the CCRS,
                                    not because it is a good match.)
    Storm                -> EXCLUDED: no wind/storm hazard term exists in
                                    the CCRS to compare against.

--------------------------------------------------------------------------
Method
--------------------------------------------------------------------------
For each (country, disaster_type) pair above (Storm excluded): every
admin-1 polygon's zonal MEAN of the mapped term's raw raster
(``rasterio.mask``, nodata-safe; GFDL-ESM4, ``water_scenario="bau"`` -- one
reference field, since this is a diagnostic check, not a scenario-resolved
CCRS result), split into two groups -- polygons with >= 1 geocoded event of
that type, polygons with none -- compared with a two-sided Mann-Whitney U
test (non-parametric: admin-1 counts per country are all under 40 here, and
the hazard field is not assumed normal). A pair is **skipped, not silently
dropped** (``skip_reason`` recorded) when either group has fewer than
``MIN_GROUP_SIZE`` polygons with a finite raster value.

Standalone: ``python -m src.index.emdat_validation`` writes
``data/outputs/tables/emdat_spatial_validation.csv`` (the summary) and
``data/outputs/tables/emdat_spatial_validation_polygons.csv`` (the raw
per-polygon values the summary and the figure are both built from).
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
from scipy import stats

from src.config import BOUNDARIES_RAW, COUNTRIES, COUNTRY_ISO3, MAINLAND_ONLY_COUNTRIES, OUTPUT_TABLES
from src.downloaders import emdat_downloader
from src.downloaders.boundaries_downloader import get_country_geometry
from src.index import ccrs_calculator as ccrs
from src.index.risk_bands import PRIMARY_GCM

logger = logging.getLogger(__name__)

DISASTER_TYPE_TO_TERM = {
    "Extreme temperature": "heat",
    "Drought": "spei",
    "Flood": "ws",
}
EXCLUDED_DISASTER_TYPES = ("Storm",)  # no matching Hazard term, see module docstring
REFERENCE_WATER_SCENARIO = "bau"
MIN_GROUP_SIZE = 3

_GID_KEY_RE = re.compile(r"^gid_(\d+)$")


# --------------------------------------------------------------------------
# Admin-1 boundaries -- a minimal, index-layer-only loader (does not import
# src/visualization, to keep the index layer independent of it; mirrors
# _common.load_admin1_boundaries's mainland-clipping logic only, since this
# module needs geometries + GID_1, not the disputed-territory drawing).
# --------------------------------------------------------------------------
def _load_admin1_boundaries(country: str) -> gpd.GeoDataFrame:
    iso3 = COUNTRY_ISO3[country]
    gpkg_path = BOUNDARIES_RAW / "gadm" / f"gadm41_{iso3}.gpkg"
    if not gpkg_path.exists():
        raise FileNotFoundError(
            f"{gpkg_path} does not exist -- run "
            f"boundaries_downloader.download_country_boundary('{country}') first."
        )
    gdf = gpd.read_file(gpkg_path, layer="ADM_ADM_1")
    if country in MAINLAND_ONLY_COUNTRIES:
        mainland = gpd.GeoSeries([get_country_geometry(country)], crs="EPSG:4326")
        gdf = gpd.clip(gdf, mainland)
    return gdf


# --------------------------------------------------------------------------
# "GADM Admin Units" parsing
# --------------------------------------------------------------------------
def _resolve_admin1_gid(gid_value: str, level: int) -> str | None:
    """Truncate a level-N GID to its admin-1 parent. ``level == 0``
    (country-only) cannot be placed on a specific admin-1 polygon and
    returns ``None``."""
    if level == 0:
        return None
    parts = str(gid_value).split(".")
    if len(parts) < 2:
        return None
    country_code = parts[0]
    admin1_num = parts[1].split("_")[0] if level == 1 else parts[1]
    return f"{country_code}.{admin1_num}_1"


def _admin1_gids_from_cell(cell) -> set[str]:
    if not isinstance(cell, str) or not cell.strip():
        return set()
    try:
        entries = json.loads(cell)
    except (TypeError, ValueError):
        return set()
    gids: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for key, value in entry.items():
            m = _GID_KEY_RE.match(key)
            if not m:
                continue
            gid = _resolve_admin1_gid(value, int(m.group(1)))
            if gid:
                gids.add(gid)
    return gids


def load_geocoded_events(country: str) -> pd.DataFrame:
    """One row per (``disaster_type``, admin-1 ``gid_1``) a country's EM-DAT
    events resolve to. Storm is excluded (no matching term); events with no
    "GADM Admin Units" entry at all are silently absent -- that omission
    IS the coverage gap this module's docstring documents, not a bug."""
    path = emdat_downloader.country_csv_path(country)
    df = pd.read_csv(path)
    df = df[df["Disaster Type"].isin(DISASTER_TYPE_TO_TERM)]
    rows = []
    for disaster_type, gadm_cell in zip(df["Disaster Type"], df["GADM Admin Units"]):
        for gid in _admin1_gids_from_cell(gadm_cell):
            rows.append({"disaster_type": disaster_type, "gid_1": gid})
    return pd.DataFrame(rows, columns=["disaster_type", "gid_1"]).drop_duplicates()


# --------------------------------------------------------------------------
# Zonal hazard values per admin-1 polygon
# --------------------------------------------------------------------------
def _zonal_mean(raster_path: Path, geometry) -> float:
    with rasterio.open(raster_path) as src:
        try:
            out_image, _ = mask(src, [geometry], crop=True, nodata=np.nan, filled=True)
        except ValueError:
            return float("nan")  # polygon does not overlap the raster extent
        band = out_image[0].astype("float64")
        nod = src.nodata
        if nod is not None and not np.isnan(nod):
            band = np.where(band == nod, np.nan, band)
        finite = band[np.isfinite(band)]
        return float(finite.mean()) if finite.size else float("nan")


def polygon_hazard_table(
    country: str, term: str, model: str = PRIMARY_GCM, water_scenario: str = REFERENCE_WATER_SCENARIO,
) -> pd.DataFrame:
    """One row per admin-1 polygon: ``gid_1``, zonal-mean raw raster value of
    ``term`` (``ccrs_calculator.raster_path``, the same raster the CCRS
    Hazard term itself samples at plant points -- here aggregated over the
    whole polygon instead)."""
    admin1 = _load_admin1_boundaries(country)
    path = ccrs.raster_path(term, country, water_scenario, model)
    rows = [{"gid_1": gid, "hazard_value": _zonal_mean(path, geom)}
            for gid, geom in zip(admin1["GID_1"], admin1.geometry)]
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Mann-Whitney U comparison
# --------------------------------------------------------------------------
def run_validation(
    countries: list[str] | None = None, model: str = PRIMARY_GCM,
    water_scenario: str = REFERENCE_WATER_SCENARIO,
) -> dict[str, pd.DataFrame]:
    """Returns ``{"summary": DataFrame, "polygons": DataFrame}``.

    ``summary`` -- one row per (country, disaster_type): group sizes, median
    hazard value per group, the Mann-Whitney U statistic and two-sided
    p-value, or a non-null ``skip_reason`` if the pair could not be tested.

    ``polygons`` -- one row per (country, disaster_type, gid_1): the raw
    zonal hazard value and whether that polygon had >= 1 geocoded event of
    that type. This is what the box/strip plot
    (``src/visualization/emdat_validation.py``) draws; never a single
    combined score.
    """
    countries = countries or COUNTRIES
    summary_rows = []
    polygon_frames = []

    for country in countries:
        events = load_geocoded_events(country)
        for disaster_type, term in DISASTER_TYPE_TO_TERM.items():
            polys = polygon_hazard_table(country, term, model, water_scenario)
            event_gids = set(events.loc[events["disaster_type"] == disaster_type, "gid_1"])
            polys = polys.copy()
            polys["has_event"] = polys["gid_1"].isin(event_gids)
            polys["country"] = country
            polys["disaster_type"] = disaster_type
            polys["term"] = term
            polygon_frames.append(polys)

            with_event = polys.loc[polys["has_event"], "hazard_value"].dropna()
            without_event = polys.loc[~polys["has_event"], "hazard_value"].dropna()

            row = {
                "country": country, "disaster_type": disaster_type, "term": term,
                "n_polygons_with_event": int(polys["has_event"].sum()),
                "n_polygons_without_event": int((~polys["has_event"]).sum()),
                "n_finite_with_event": int(len(with_event)),
                "n_finite_without_event": int(len(without_event)),
                "median_hazard_with_event": float(with_event.median()) if len(with_event) else float("nan"),
                "median_hazard_without_event": float(without_event.median()) if len(without_event) else float("nan"),
                "u_statistic": float("nan"), "p_value": float("nan"), "skip_reason": None,
            }
            if len(with_event) < MIN_GROUP_SIZE or len(without_event) < MIN_GROUP_SIZE:
                row["skip_reason"] = (
                    f"fewer than {MIN_GROUP_SIZE} polygons with a finite hazard value on one side "
                    f"(with_event={len(with_event)}, without_event={len(without_event)})"
                )
            else:
                u_stat, p_value = stats.mannwhitneyu(with_event, without_event, alternative="two-sided")
                row["u_statistic"] = float(u_stat)
                row["p_value"] = float(p_value)
            summary_rows.append(row)

    polygons = pd.concat(polygon_frames, ignore_index=True) if polygon_frames else pd.DataFrame(
        columns=["gid_1", "hazard_value", "has_event", "country", "disaster_type", "term"]
    )
    return {"summary": pd.DataFrame(summary_rows), "polygons": polygons}


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=OUTPUT_TABLES)
    args = parser.parse_args()

    result = run_validation()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    result["summary"].to_csv(args.out_dir / "emdat_spatial_validation.csv", index=False)
    result["polygons"].to_csv(args.out_dir / "emdat_spatial_validation_polygons.csv", index=False)
    logger.info(
        "wrote emdat_spatial_validation.csv (%d rows) and "
        "emdat_spatial_validation_polygons.csv (%d rows) to %s",
        len(result["summary"]), len(result["polygons"]), args.out_dir,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
