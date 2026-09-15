"""
IBTrACS tropical-cyclone best-track data -- acquisition of the NOAA NCEI
v04r01 basin CSV files (Knapp et al. 2010).

ACQUISITION ONLY. This module downloads one basin file per study country,
extracts the columns needed for a point/track-radius match, and writes one
CSV per country. It does NOT do the radius match against plant coordinates
-- that is ``src/index/contextual_validators.compute_physical_occurrence_
validation``.

Source: NOAA NCEI's public, no-credential CSV access
(``config.IBTRACS_BASE_URL``), one file per WMO basin, updated ~twice/year.
Chosen over the FIRMS/landslide/lightning candidates in Methods Section 7.1
-- see ``docs/DECISIONS.md``, "GEAR v3 Phase 5: physical-occurrence
validator (IBTrACS)" -- because it is the only Section-7.1 source with a
hazard-term slot this project's own hazard scope defines
(``hazard_scope.WIND_APPLICABLE_BUCKETS``).

Basin scope (``config.IBTRACS_BASIN_BY_COUNTRY``): one basin per country,
geographically exhaustive, not a simplification -- see the constant's own
comment in ``src/config.py``. Each basin file carries EVERY storm in that
basin regardless of which country (if any) it ultimately affected; this
module does not filter by country beyond selecting the right basin file,
because IBTrACS carries no per-track country attribution -- the country-level
relevance test is the radius match downstream, not this module.

Each basin CSV has two header rows (column names, then units) -- the units
row is skipped on read, exactly once, here. Wind speed is taken as the max
of ``WMO_WIND`` (each basin's designated official agency) and ``USA_WIND``
(ATCF/JTWC, frequently populated when the official agency is not, especially
for older or non-US-basin storms) -- neither column alone has usable
coverage across the whole record, mirroring IBTrACS's own multi-agency
design rather than picking one column arbitrarily.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
import time
from pathlib import Path

import pandas as pd
import requests

from src.config import COUNTRIES, IBTRACS_BASE_URL, IBTRACS_BASIN_BY_COUNTRY, VALIDATION_RAW

logger = logging.getLogger(__name__)

# Columns kept from the raw basin file -- everything else (per-agency
# secondary tracks, wind-radii quadrants, etc.) is out of scope for a
# track-center radius match.
REQUIRED_COLUMNS = ["SID", "SEASON", "BASIN", "NAME", "ISO_TIME", "LAT", "LON", "WMO_WIND", "USA_WIND"]

# Gale-force / tropical-storm-intensity threshold (kt), the same convention
# IBTrACS's own USA_R34 (34-kt wind radius) field name encodes. A track
# point below this is a tropical depression / extratropical remnant / genesis
# disturbance, not a point this validator treats as a qualifying wind event.
MIN_WIND_KT = 34


def basin_raw_path(basin: str) -> Path:
    return VALIDATION_RAW / f"_ibtracs_{basin}_raw.csv"


def country_csv_path(country: str) -> Path:
    return VALIDATION_RAW / f"ibtracs_{country}.csv"


def _retry(func, max_tries: int = 3, base_sleep: float = 2.0, label: str = "operation"):
    for attempt in range(max_tries):
        try:
            return func()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            if attempt == max_tries - 1:
                raise RuntimeError(
                    f"{label}: timeout / connection error after {max_tries} tries. "
                    f"Likely NOAA NCEI instability or a local network block, not a "
                    f"script bug. Original error: {exc}"
                ) from exc
            wait = base_sleep * (2 ** attempt) + random.uniform(0, 1)
            logger.warning("%s failed (try %d/%d): %s", label, attempt + 1, max_tries, exc)
            time.sleep(wait)


def _validate_basin_csv(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        header = pd.read_csv(path, nrows=0).columns.tolist()
    except Exception as exc:  # noqa: BLE001
        logger.error("IBTrACS basin file at %s could not be read: %s", path, exc)
        return False
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        logger.error("IBTrACS basin file at %s missing expected columns: %s", path, missing)
        return False
    return True


def download_basin(basin: str, overwrite: bool = False, timeout: int = 180) -> dict:
    """Download one basin's full-history CSV once (cached). Honest status
    dict, never silent success on a bad download or a schema mismatch."""
    VALIDATION_RAW.mkdir(parents=True, exist_ok=True)
    out_file = basin_raw_path(basin)

    if out_file.exists() and not overwrite and _validate_basin_csv(out_file):
        logger.info("IBTrACS basin %s cached and valid, skipping: %s", basin, out_file)
        return {"success": True, "path": str(out_file), "reason": "cached_valid"}

    url = f"{IBTRACS_BASE_URL}/ibtracs.{basin}.list.v04r01.csv"

    def _fetch() -> bytes:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content

    try:
        content = _retry(_fetch, label=f"Download IBTrACS basin {basin}")
    except RuntimeError as exc:
        logger.error(str(exc))
        return {"success": False, "path": None, "reason": f"download_error: {exc}"}
    except Exception as exc:  # noqa: BLE001
        logger.error("IBTrACS basin %s download failed: %s", basin, exc)
        return {"success": False, "path": None, "reason": f"download_error: {exc}"}

    out_file.write_bytes(content)
    if not _validate_basin_csv(out_file):
        return {"success": False, "path": str(out_file), "reason": "validation_failed"}

    logger.info("IBTrACS basin %s downloaded and validated: %s (%s bytes)", basin, out_file, f"{len(content):,}")
    return {"success": True, "path": str(out_file), "reason": "downloaded"}


def extract_track_points(basin_file: Path, country: str) -> pd.DataFrame:
    """Read one basin CSV (skipping its units row) and write the country's
    track-point CSV: ``SID``, ``SEASON`` (year, IBTrACS's own hemisphere-
    aware season label -- used instead of parsing ``ISO_TIME``'s calendar
    year, which would mis-assign Southern Hemisphere storms spanning
    December/January), ``NAME``, ``ISO_TIME``, ``LAT``, ``LON``, ``WIND_KT``
    (max of ``WMO_WIND``/``USA_WIND``). No radius or country-relevance
    filtering here -- see module docstring."""
    df = pd.read_csv(basin_file, skiprows=[1], low_memory=False)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise RuntimeError(f"{basin_file} missing expected columns: {missing}")

    df["LAT"] = pd.to_numeric(df["LAT"], errors="coerce")
    df["LON"] = pd.to_numeric(df["LON"], errors="coerce")
    df["WMO_WIND"] = pd.to_numeric(df["WMO_WIND"], errors="coerce")
    df["USA_WIND"] = pd.to_numeric(df["USA_WIND"], errors="coerce")
    df["SEASON"] = pd.to_numeric(df["SEASON"], errors="coerce")
    df["WIND_KT"] = df[["WMO_WIND", "USA_WIND"]].max(axis=1)

    out = df.loc[
        df["LAT"].notna() & df["LON"].notna(),
        ["SID", "SEASON", "NAME", "ISO_TIME", "LAT", "LON", "WIND_KT"],
    ].reset_index(drop=True)

    VALIDATION_RAW.mkdir(parents=True, exist_ok=True)
    out_path = country_csv_path(country)
    out.to_csv(out_path, index=False)
    logger.info("IBTrACS/%s: %d track point(s) -> %s", country, len(out), out_path)
    return out


def run_ibtracs_pipeline(countries: list[str] | None = None, overwrite: bool = False) -> dict:
    """Download each required basin once + extract each country's track
    points. Honest per step: if a basin download fails, that country's
    extraction is not attempted, and other countries proceed independently."""
    countries = countries or COUNTRIES
    basins_needed = {IBTRACS_BASIN_BY_COUNTRY[c] for c in countries}

    downloads = {basin: download_basin(basin, overwrite=overwrite) for basin in basins_needed}

    report: dict = {"download": downloads, "extract": {}}
    overall_success = True
    for country in countries:
        basin = IBTRACS_BASIN_BY_COUNTRY[country]
        if not downloads[basin]["success"]:
            report["extract"][country] = {"error": f"basin {basin} download failed"}
            overall_success = False
            continue
        try:
            points = extract_track_points(Path(downloads[basin]["path"]), country)
        except Exception as exc:  # noqa: BLE001
            logger.error("IBTrACS extraction failed for %s: %s", country, exc)
            report["extract"][country] = {"error": str(exc)}
            overall_success = False
            continue
        report["extract"][country] = {
            "n_track_points": len(points),
            "n_storms": int(points["SID"].nunique()) if len(points) else 0,
            "path": str(country_csv_path(country)),
        }

    report["overall_success"] = overall_success
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--countries", nargs="+", default=None)
    args = parser.parse_args()

    result = run_ibtracs_pipeline(countries=args.countries, overwrite=args.overwrite)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    sys.exit(0 if result.get("overall_success") else 1)
