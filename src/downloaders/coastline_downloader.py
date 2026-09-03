"""
Global coastline — Natural Earth 10m physical/coastline.

Downloaded once and shared across countries. A dedicated coastline layer is
used rather than a country's GADM polygon: the GADM outer ring mixes land
borders with the shore, so a distance-to-coast computed from it would measure
distance to a neighbouring country's border for inland plants near a frontier.

Resolution 10m (the finest Natural Earth publishes) is chosen because any
distance-to-coast threshold is on the order of tens of kilometres, which the
110m layer (~10 km positional error) could not support.

SLR is outside the active hazard scope (ARCHITECTURE.md Section 3), so no
processor currently consumes this layer; it is acquired and kept as a
reference boundary layer.
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import requests

from src.config import BOUNDARIES_RAW

logger = logging.getLogger(__name__)

COASTLINE_URL = "https://naciscdn.org/naturalearth/10m/physical/ne_10m_coastline.zip"
_OUT_DIR = BOUNDARIES_RAW / "natural_earth_coastline"
_SHP_NAME = "ne_10m_coastline.shp"


def coastline_path() -> Path:
    """Path to the extracted coastline shapefile."""
    return _OUT_DIR / _SHP_NAME


def download_coastline(overwrite: bool = False) -> Path:
    """Download and extract the global coastline once. Returns the ``.shp``
    path. Raises ``FileNotFoundError`` if extraction does not produce the
    expected file — never fails silently."""
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    shp_path = coastline_path()

    if shp_path.exists() and not overwrite:
        logger.info("Natural Earth coastline already present, skipping: %s", shp_path)
        return shp_path

    zip_path = _OUT_DIR / "ne_10m_coastline.zip"
    logger.info("Downloading Natural Earth 10m coastline: %s", COASTLINE_URL)
    response = requests.get(COASTLINE_URL, timeout=120)
    response.raise_for_status()
    zip_path.write_bytes(response.content)

    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(_OUT_DIR)

    if not shp_path.exists():
        raise FileNotFoundError(
            f"Extracting {zip_path} did not produce {shp_path} — the shapefile "
            f"name inside the archive may have changed."
        )

    logger.info("Natural Earth coastline ready: %s", shp_path)
    return shp_path
