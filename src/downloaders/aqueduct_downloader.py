"""
Water stress — WRI Aqueduct 4.0 ``future_annual``, via Google Earth Engine.

One Earth Engine call plus one HTTP download per country. The
``future_annual`` FeatureCollection is wide: one feature per basin with a
column for every scenario/horizon (``bau50_ws_x_r``, ``opt50_ws_x_r``,
``pes50_ws_x_r``, ...). There is no scenario filter to apply to the query, so
a single download covers all three scenarios in ``AQUEDUCT_SCENARIOS``.

If ``GEE_PROJECT_ID`` is not set, the whole step is reported as SKIPPED — not
silently passed and not raised. Earth Engine is the only credential in the
acquisition layer that is optional by design.

Post-download validation checks that the CSV exists, is non-empty, and holds
one raw water-stress column per scenario for the requested horizon.
"""

from __future__ import annotations

import logging
import random
import time
from pathlib import Path

import pandas as pd
import requests

from src.config import (
    AQUEDUCT_FC_ID,
    AQUEDUCT_SCENARIOS,
    AQUEDUCT_TO_SSP_LABEL,
    CLIMATE_RAW,
    GEE_PROJECT_ID,
    YEAR_TARGET,
)
from src.downloaders.boundaries_downloader import get_country_geometry

logger = logging.getLogger(__name__)

# "30"/"50"/"80" are the only horizons in Aqueduct 4.0 future_annual.
_YEAR_SUFFIX = {2030: "30", 2050: "50", 2080: "80"}

# The full-resolution GADM level-0 polygon for a large country (Brazil, India)
# exceeds Earth Engine's 10 MB request payload limit when sent as an inline
# geometry. It is simplified before the query. ~0.05 deg (~5 km) is far below
# the size of the hydrological basins being selected by intersection, so it
# does not change which basins are returned in practice; it must not be used
# for anything that needs the exact border.
GEOMETRY_SIMPLIFY_TOLERANCE_DEG = 0.05

_gee_ready: bool | None = None  # initialisation state, cached for this run


def output_path(country: str, year: int = YEAR_TARGET) -> Path:
    """CSV path for a country's Aqueduct download (no scenario suffix — the
    file holds every scenario column)."""
    return CLIMATE_RAW / "aqueduct" / country / f"aqueduct_{year}.csv"


def init_gee() -> bool:
    """Initialise Earth Engine once per run. Returns ``False`` (with a
    warning) if ``GEE_PROJECT_ID`` is not configured or init fails."""
    global _gee_ready
    if _gee_ready is not None:
        return _gee_ready

    if not GEE_PROJECT_ID:
        logger.warning(
            "GEE_PROJECT_ID not set in credentials.local. The Aqueduct step "
            "will be SKIPPED (reported explicitly, never as silent success)."
        )
        _gee_ready = False
        return False

    try:
        import ee

        ee.Initialize(project=GEE_PROJECT_ID)
        logger.info("Google Earth Engine initialised.")
        _gee_ready = True
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to initialise Earth Engine: %s", exc)
        _gee_ready = False

    return _gee_ready


def _retry(func, max_tries: int = 3, base_sleep: float = 2.0, label: str = "operation"):
    for attempt in range(max_tries):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001
            if attempt == max_tries - 1:
                raise
            wait = base_sleep * (2 ** attempt) + random.uniform(0, 1)
            logger.warning("%s failed (try %d/%d): %s", label, attempt + 1, max_tries, exc)
            time.sleep(wait)


def _validate_csv(path: Path, year: int = YEAR_TARGET) -> bool:
    """The CSV must exist, be non-empty, and hold one raw water-stress column
    per scenario for the requested horizon."""
    if not path.exists():
        return False
    try:
        df = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Aqueduct CSV at %s could not be read: %s", path, exc)
        return False

    if df.empty:
        logger.error("Aqueduct CSV at %s is empty.", path)
        return False

    suffix = _YEAR_SUFFIX[year]
    expected = [f"{scenario}{suffix}_ws_x_r" for scenario in AQUEDUCT_SCENARIOS]
    missing = [c for c in expected if c not in df.columns]
    if missing:
        logger.error("Aqueduct CSV at %s missing scenario columns %s", path, missing)
        return False
    return True


def download_aqueduct_gee(
    country: str, year: int = YEAR_TARGET, overwrite: bool = False
) -> dict:
    """Download Aqueduct future indicators for one country/year. Returns a
    status dict: ``{"success", "path", "reason"}``."""
    if year not in _YEAR_SUFFIX:
        raise ValueError(f"year must be one of {sorted(_YEAR_SUFFIX)}")

    out_file = output_path(country, year)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if out_file.exists() and not overwrite:
        if _validate_csv(out_file, year=year):
            logger.info("Aqueduct %s/%s cached and valid, skipping.", country, year)
            return {"success": True, "path": str(out_file), "reason": "cached_valid"}
        logger.warning("Aqueduct %s/%s exists but is invalid, re-downloading.", country, year)
        overwrite = True

    if not init_gee():
        return {"success": False, "path": None, "reason": "gee_not_configured"}

    import ee

    try:
        polygon = get_country_geometry(country).simplify(
            GEOMETRY_SIMPLIFY_TOLERANCE_DEG
        )
        geom = ee.Geometry(polygon.__geo_interface__)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return {"success": False, "path": None, "reason": "boundary_missing"}

    try:
        fc = ee.FeatureCollection(AQUEDUCT_FC_ID).filterBounds(geom)
        n_features = fc.size().getInfo()
        if n_features == 0:
            logger.error("No Aqueduct features intersect %s", country)
            return {"success": False, "path": None, "reason": "no_features"}
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to load Aqueduct FeatureCollection for %s: %s", country, exc)
        return {"success": False, "path": None, "reason": f"gee_error: {exc}"}

    try:
        def _download() -> bytes:
            url = fc.getDownloadURL(filetype="CSV")
            response = requests.get(url, timeout=180)
            response.raise_for_status()
            return response.content

        content = _retry(_download, label=f"Aqueduct {country} {year}")
        out_file.write_bytes(content)
    except Exception as exc:  # noqa: BLE001
        logger.error("Aqueduct download failed for %s/%s: %s", country, year, exc)
        return {"success": False, "path": None, "reason": f"download_error: {exc}"}

    if not _validate_csv(out_file, year=year):
        return {"success": False, "path": str(out_file), "reason": "validation_failed"}

    labels = ", ".join(f"{s}={AQUEDUCT_TO_SSP_LABEL[s]}" for s in AQUEDUCT_SCENARIOS)
    logger.info("Aqueduct OK: %s (%s) -> %s", country, labels, out_file)
    return {"success": True, "path": str(out_file), "reason": "downloaded"}


def download_all_aqueduct(countries, overwrite: bool = False) -> dict:
    """Download for every country and return a per-country status report."""
    return {
        country: download_aqueduct_gee(country, overwrite=overwrite)
        for country in countries
    }
