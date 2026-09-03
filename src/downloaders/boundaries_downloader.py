"""
National boundaries — GADM 4.1, administrative level 0, as GeoPackage.

GADM level 0 is used (not Natural Earth 1:110m) because the boundary is
consumed to clip ~1 km rasters and to bound climate API queries: a coarse
outline would leak or clip whole grid cells.

For countries in ``MAINLAND_ONLY_COUNTRIES`` the level-0 geometry is a
MultiPolygon that includes overseas archipelagos (for Portugal this inflates
the bounding box from ~5x4 to ~25x12 degrees). The mainland filter keeps only
the largest polygon by area. This is a heuristic — it happens to be correct
for every country in scope — and should be checked visually at least once.

Functions return ``None`` (with an ERROR log) or raise explicitly on failure;
they never fail silently, so the orchestrator can treat a step as genuinely
failed rather than as masked success.
"""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import MultiPolygon

from src.config import (
    BOUNDARIES_RAW,
    COUNTRY_ISO3,
    GADM_BASE_URL,
    MAINLAND_ONLY_COUNTRIES,
)

logger = logging.getLogger(__name__)

GADM_LAYER = "ADM_ADM_0"


def boundary_path(country: str) -> Path:
    """Output path for a country's GADM GeoPackage."""
    iso3 = COUNTRY_ISO3[country]
    return BOUNDARIES_RAW / "gadm" / f"gadm41_{iso3}.gpkg"


def download_country_boundary(country: str, overwrite: bool = False) -> Path | None:
    """Download the GADM 4.1 level-0 GeoPackage for one country.

    Returns the file path, or ``None`` if the download or post-download
    validation fails (always with an ERROR log).
    """
    if country not in COUNTRY_ISO3:
        logger.error("No ISO3 configured for country: %s", country)
        return None

    iso3 = COUNTRY_ISO3[country]
    out_file = boundary_path(country)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if out_file.exists() and not overwrite:
        logger.info("GADM boundary already present for %s, skipping: %s", country, out_file)
        return out_file

    url = f"{GADM_BASE_URL}/gadm41_{iso3}.gpkg"
    logger.info("Downloading GADM boundary for %s: %s", country, url)

    try:
        response = requests.get(url, timeout=180, stream=True)
        response.raise_for_status()
        with open(out_file, "wb") as handle:
            for chunk in response.iter_content(chunk_size=8192):
                handle.write(chunk)
    except Exception as exc:  # noqa: BLE001 - reported, not masked
        logger.error("Failed to download GADM boundary for %s: %s", country, exc)
        return None

    try:
        gdf = gpd.read_file(out_file, layer=GADM_LAYER)
        if gdf.empty:
            logger.error("GADM boundary for %s downloaded empty.", country)
            return None
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "GADM boundary for %s downloaded but could not be read "
            "(corrupt file or renamed layer): %s",
            country,
            exc,
        )
        return None

    logger.info("GADM boundary validated for %s: %s", country, out_file)
    return out_file


def _apply_mainland_filter(country: str, geometry):
    """Keep only the largest polygon by area for mainland-only countries."""
    if country not in MAINLAND_ONLY_COUNTRIES:
        return geometry
    if not isinstance(geometry, MultiPolygon):
        return geometry

    parts = list(geometry.geoms)
    largest = max(parts, key=lambda poly: poly.area)
    logger.info(
        "%s: original geometry had %d parts (likely islands / archipelagos); "
        "keeping only the largest by area. Confirm visually before trusting.",
        country,
        len(parts),
    )
    return largest


def get_country_geometry(country: str):
    """Return the (shapely) geometry for a country from the downloaded GADM
    file. Raises ``FileNotFoundError`` if the boundary has not been downloaded
    yet — never returns ``None`` silently."""
    gpkg_path = boundary_path(country)
    if not gpkg_path.exists():
        raise FileNotFoundError(
            f"GADM boundary not found for {country}. "
            f"Run download_country_boundary('{country}') first."
        )
    gdf = gpd.read_file(gpkg_path, layer=GADM_LAYER)
    return _apply_mainland_filter(country, gdf.geometry.iloc[0])


def get_country_bounds(country: str) -> tuple[float, float, float, float]:
    """Return the real ``(xmin, ymin, xmax, ymax)`` from the GADM geometry,
    after the mainland filter. Used by the climate downloaders instead of the
    approximate fallback box."""
    return get_country_geometry(country).bounds


def download_all_boundaries(countries, overwrite: bool = False) -> dict:
    """Download boundaries for every country and return a per-country status
    report the orchestrator can act on."""
    status = {}
    for country in countries:
        path = download_country_boundary(country, overwrite=overwrite)
        status[country] = {
            "success": path is not None,
            "path": str(path) if path else None,
        }
    return status
