"""
EM-DAT disaster events — acquisition of the open EM-DAT Archive snapshot.

ACQUISITION ONLY. This module downloads the Archive, filters it to the study
countries and the climate-relevant disaster types, and produces descriptive
counts and geocoding-coverage tables. It does NOT geocode events, and it does
NOT cross-check them against risk hotspots — that belongs to the not-yet-built
index/validation layer.

Source: EM-DAT Archive on the UCLouvain Dataverse (DOI 10.14428/DVN/I0LTPH,
Delforge et al.). Chosen over the aggregated HDX "Country Profiles" (no
``Location`` field) and over the authenticated ``public.emdat.be`` portal
(requires a login). The Archive is a flat one-row-per-event table, open, no
registration, citable by DOI, covering 1900-2024. It is a snapshot (taken
2026-04-30 by the EM-DAT team), so 2025+ events are absent.

Geographic granularity is heterogeneous per event: the free-text ``Location``
field ranges from a single district to dozens of municipalities to vague
directional descriptors, and a fraction is empty; a separate ``GADM Admin
Units`` field carries structured GID codes (polygon-level) for only some
events; a still smaller fraction carries a point-level ``Latitude`` /
``Longitude`` centroid. The coverage report measures all three separately —
GADM-unit coverage and lat/lon coverage are two distinct figures, not one
metric measured twice. Any use of these fields downstream must respect that
heterogeneity — this module only measures it.
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

from src.config import (
    COUNTRIES,
    COUNTRY_ISO3,
    EMDAT_ARCHIVE_PERSISTENT_ID,
    EMDAT_DATAVERSE_API_BASE,
    OUTPUT_INSPECTION,
    VALIDATION_RAW,
)

logger = logging.getLogger(__name__)

# Exact values confirmed against the Archive's "Disaster Type" column.
DISASTER_TYPES = ["Drought", "Extreme temperature", "Flood", "Storm"]

# The file id changes with every published version of the Archive; only the
# filename keyword is stable.
TARGET_FILENAME_KEYWORD = "emdat_archive"
RAW_ARCHIVE_FILENAME = "_emdat_archive_raw.xlsx"

REQUIRED_COLUMNS = ["ISO", "Country", "Disaster Type", "Location", "Start Year"]
# Structured geocoding field, present for only a fraction of events.
GADM_ADMIN_COLUMN = "GADM Admin Units"
# Point-level geocoding: a single event centroid. Distinct from GADM_ADMIN_COLUMN
# (a polygon-level administrative unit) — a much smaller fraction of events
# carries it. This is the figure ARCHITECTURE.md Section 7.2 cites.
LATLON_COLUMNS = ("Latitude", "Longitude")


class DataverseUnavailableError(RuntimeError):
    """Raised when the UCLouvain Dataverse API times out or refuses the
    connection after retries — an actionable message rather than a bare
    ``requests`` traceback."""


def archive_path() -> Path:
    return VALIDATION_RAW / RAW_ARCHIVE_FILENAME


def country_csv_path(country: str) -> Path:
    return VALIDATION_RAW / f"emdat_{country}.csv"


def _retry(func, max_tries: int = 3, base_sleep: float = 2.0, label: str = "operation"):
    for attempt in range(max_tries):
        try:
            return func()
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            if attempt == max_tries - 1:
                raise DataverseUnavailableError(
                    f"{label}: timeout / connection error after {max_tries} tries. "
                    f"Likely Dataverse instability or a local network block, not a "
                    f"script bug. Original error: {exc}"
                ) from exc
            wait = base_sleep * (2 ** attempt) + random.uniform(0, 1)
            logger.warning("%s failed (try %d/%d): %s", label, attempt + 1, max_tries, exc)
            time.sleep(wait)


def discover_archive_file(timeout: int = 30) -> dict:
    """Locate the ``.xlsx`` table inside the Archive dataset without
    hardcoding its file id. Raises ``RuntimeError`` if the dataset structure
    has changed and the expected file cannot be found unambiguously."""

    def _lookup() -> dict:
        response = requests.get(
            f"{EMDAT_DATAVERSE_API_BASE}/datasets/:persistentId",
            params={"persistentId": EMDAT_ARCHIVE_PERSISTENT_ID},
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json()

    data = _retry(_lookup, label="Dataverse dataset lookup (EM-DAT Archive)")
    if data.get("status") != "OK":
        raise RuntimeError(f"Dataverse returned an unexpected status: {data}")

    files = data.get("data", {}).get("latestVersion", {}).get("files", [])
    candidates = [
        f
        for f in files
        if TARGET_FILENAME_KEYWORD in (f.get("dataFile", {}).get("filename", "") or "").lower()
        and f["dataFile"]["filename"].lower().endswith(".xlsx")
    ]
    if len(candidates) != 1:
        available = [f.get("dataFile", {}).get("filename") for f in files]
        raise RuntimeError(
            f"Expected exactly one .xlsx named like '{TARGET_FILENAME_KEYWORD}' in "
            f"{EMDAT_ARCHIVE_PERSISTENT_ID}, found {len(candidates)}. "
            f"Available files: {available}."
        )

    data_file = candidates[0]["dataFile"]
    return {
        "file_id": data_file["id"],
        "filename": data_file["filename"],
        "filesize": data_file.get("filesize"),
        "restricted": candidates[0].get("restricted", False),
    }


def _validate_xlsx(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        header = pd.read_excel(path, nrows=0).columns.tolist()
    except Exception as exc:  # noqa: BLE001
        logger.error("EM-DAT Archive at %s could not be read: %s", path, exc)
        return False
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        logger.error("EM-DAT Archive at %s missing expected columns: %s", path, missing)
        return False
    return True


def download_emdat_archive(overwrite: bool = False, timeout: int = 180) -> dict:
    """Download the full EM-DAT Archive table once (cached). Returns an honest
    status dict — never silent success if the download or schema check
    fails."""
    VALIDATION_RAW.mkdir(parents=True, exist_ok=True)
    out_file = archive_path()

    if out_file.exists() and not overwrite and _validate_xlsx(out_file):
        logger.info("EM-DAT Archive cached and valid, skipping: %s", out_file)
        return {"success": True, "path": str(out_file), "reason": "cached_valid"}

    try:
        file_info = discover_archive_file(timeout=min(timeout, 30))
    except (RuntimeError, DataverseUnavailableError) as exc:
        logger.error("Failed to locate the EM-DAT Archive file: %s", exc)
        return {"success": False, "path": None, "reason": f"discovery_error: {exc}"}

    if file_info["restricted"]:
        return {
            "success": False,
            "path": None,
            "reason": "file_restricted — the Archive file now requires authentication.",
        }

    logger.info(
        "EM-DAT Archive located: %s (%s bytes, file_id=%s)",
        file_info["filename"], f"{file_info['filesize']:,}", file_info["file_id"],
    )

    def _fetch() -> bytes:
        response = requests.get(
            f"{EMDAT_DATAVERSE_API_BASE}/access/datafile/{file_info['file_id']}",
            timeout=timeout,
        )
        response.raise_for_status()
        return response.content

    try:
        content = _retry(_fetch, label="Download EM-DAT Archive")
    except DataverseUnavailableError as exc:
        logger.error(str(exc))
        return {"success": False, "path": None, "reason": f"download_timeout: {exc}"}
    except Exception as exc:  # noqa: BLE001
        logger.error("EM-DAT Archive download failed: %s", exc)
        return {"success": False, "path": None, "reason": f"download_error: {exc}"}

    out_file.write_bytes(content)
    if not _validate_xlsx(out_file):
        return {"success": False, "path": str(out_file), "reason": "validation_failed"}

    logger.info("EM-DAT Archive downloaded and validated: %s (%s bytes)", out_file, f"{len(content):,}")
    return {
        "success": True,
        "path": str(out_file),
        "reason": "downloaded",
        "source_filename": file_info["filename"],
    }


def filter_and_split_by_country(
    archive_file: Path,
    countries: list[str] | None = None,
    disaster_types: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Filter the Archive by ISO code and disaster type, and write one CSV per
    country to ``data/raw/validation/emdat_{country}.csv``."""
    countries = countries or COUNTRIES
    disaster_types = disaster_types or DISASTER_TYPES

    df = pd.read_excel(archive_file)
    isos = {country: COUNTRY_ISO3[country] for country in countries}

    VALIDATION_RAW.mkdir(parents=True, exist_ok=True)
    result: dict[str, pd.DataFrame] = {}
    for country, iso in isos.items():
        sub = df[(df["ISO"] == iso) & (df["Disaster Type"].isin(disaster_types))].copy()
        out_path = country_csv_path(country)
        sub.to_csv(out_path, index=False)
        result[country] = sub
        logger.info("EM-DAT/%s: %d event(s) -> %s", country, len(sub), out_path)

    return result


def coverage_report(filtered_by_country: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Per-country event count and geocoding coverage: how many events carry a
    free-text ``Location``, how many carry a structured ``GADM Admin Units``
    polygon reference, and how many carry a point-level ``Latitude`` /
    ``Longitude`` centroid. The last two are distinct coverage figures, not
    the same metric measured twice. Descriptive only — no conclusions drawn
    here."""
    lat_col, lon_col = LATLON_COLUMNS
    rows = []
    for country, sub in filtered_by_country.items():
        n = len(sub)
        has_location = int(sub["Location"].notna().sum()) if n else 0
        has_gadm = (
            int(sub[GADM_ADMIN_COLUMN].notna().sum())
            if n and GADM_ADMIN_COLUMN in sub.columns
            else 0
        )
        has_latlon = (
            int((sub[lat_col].notna() & sub[lon_col].notna()).sum())
            if n and lat_col in sub.columns and lon_col in sub.columns
            else 0
        )
        rows.append(
            {
                "country": country,
                "n_events": n,
                "n_with_location_text": has_location,
                "pct_with_location_text": round(100 * has_location / n, 1) if n else 0.0,
                "n_with_gadm_admin_units": has_gadm,
                "pct_with_gadm_admin_units": round(100 * has_gadm / n, 1) if n else 0.0,
                "n_with_latlon": has_latlon,
                "pct_with_latlon": round(100 * has_latlon / n, 1) if n else 0.0,
            }
        )
    result = pd.DataFrame(rows)

    OUTPUT_INSPECTION.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_INSPECTION / "emdat_coverage.csv", index=False)
    return result


def event_counts(filtered_by_country: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Event count per country / disaster type / start year. Descriptive
    only."""
    frames = []
    for country, sub in filtered_by_country.items():
        if sub.empty:
            continue
        counts = (
            sub.groupby(["Disaster Type", "Start Year"]).size().reset_index(name="n_events")
        )
        counts.insert(0, "country", country)
        frames.append(counts)

    result = (
        pd.concat(frames, ignore_index=True)
        if frames
        else pd.DataFrame(columns=["country", "Disaster Type", "Start Year", "n_events"])
    )
    result = result.sort_values(["country", "Disaster Type", "Start Year"]).reset_index(drop=True)

    OUTPUT_INSPECTION.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT_INSPECTION / "emdat_event_counts.csv", index=False)
    return result


def run_emdat_pipeline(
    countries: list[str] | None = None,
    disaster_types: list[str] | None = None,
    overwrite: bool = False,
) -> dict:
    """Download + filter/split + descriptive counts and coverage. Honest per
    step: if the download fails, nothing downstream is attempted."""
    report = {"download": download_emdat_archive(overwrite=overwrite)}
    if not report["download"]["success"]:
        report["overall_success"] = False
        return report

    countries = countries or COUNTRIES
    disaster_types = disaster_types or DISASTER_TYPES

    try:
        filtered = filter_and_split_by_country(
            archive_path(), countries, disaster_types
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to filter/split the EM-DAT Archive: %s", exc)
        report["filter_and_split"] = {"error": str(exc)}
        report["overall_success"] = False
        return report

    counts = event_counts(filtered)
    coverage = coverage_report(filtered)
    report["filter_and_split"] = {
        country: {"n_events": len(sub), "path": str(country_csv_path(country))}
        for country, sub in filtered.items()
    }
    report["event_counts"] = {
        "path": str(OUTPUT_INSPECTION / "emdat_event_counts.csv"),
        "total_events": int(counts["n_events"].sum()) if not counts.empty else 0,
    }
    report["coverage"] = coverage.to_dict(orient="records")
    report["overall_success"] = True
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--countries", nargs="+", default=None)
    parser.add_argument("--disaster-types", nargs="+", default=None)
    args = parser.parse_args()

    result = run_emdat_pipeline(
        countries=args.countries,
        disaster_types=args.disaster_types,
        overwrite=args.overwrite,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    sys.exit(0 if result.get("overall_success") else 1)
