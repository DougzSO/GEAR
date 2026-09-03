"""
Global rivers — Natural Earth 10m physical/rivers_lake_centerlines.

Same source and same download-once, share-across-countries pattern as
``coastline_downloader``. Originally used to tell run-of-river hydro plants
(close to the coast only because they sit near a large river mouth) apart
from genuinely coastal assets. SLR is outside the active hazard scope
(ARCHITECTURE.md Section 3), so no processor currently consumes this layer;
it is acquired and kept as a reference boundary layer.
"""

from __future__ import annotations

import logging
import zipfile
from pathlib import Path

import requests

from src.config import BOUNDARIES_RAW

logger = logging.getLogger(__name__)

RIVERS_URL = (
    "https://naciscdn.org/naturalearth/10m/physical/"
    "ne_10m_rivers_lake_centerlines.zip"
)
_OUT_DIR = BOUNDARIES_RAW / "natural_earth_rivers"
_SHP_NAME = "ne_10m_rivers_lake_centerlines.shp"


def rivers_path() -> Path:
    """Path to the extracted rivers shapefile."""
    return _OUT_DIR / _SHP_NAME


def download_rivers(overwrite: bool = False) -> Path:
    """Download and extract the global rivers layer once. Returns the
    ``.shp`` path. Raises ``FileNotFoundError`` if extraction does not
    produce the expected file — never fails silently."""
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    shp_path = rivers_path()

    if shp_path.exists() and not overwrite:
        logger.info("Natural Earth rivers already present, skipping: %s", shp_path)
        return shp_path

    zip_path = _OUT_DIR / "ne_10m_rivers_lake_centerlines.zip"
    logger.info("Downloading Natural Earth 10m rivers: %s", RIVERS_URL)
    response = requests.get(RIVERS_URL, timeout=120)
    response.raise_for_status()
    zip_path.write_bytes(response.content)

    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(_OUT_DIR)

    if not shp_path.exists():
        raise FileNotFoundError(
            f"Extracting {zip_path} did not produce {shp_path} — the shapefile "
            f"name inside the archive may have changed."
        )

    logger.info("Natural Earth rivers ready: %s", shp_path)
    return shp_path
