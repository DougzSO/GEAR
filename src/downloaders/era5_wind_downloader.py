"""
Extreme Wind hazard input -- hourly ERA5 10 m instantaneous wind gust, from
the Copernicus CDS ``reanalysis-era5-single-levels`` dataset. GEAR v3 Phase
2.3 (``docs/rework/GEAR_v3_work_plan.md``).

--------------------------------------------------------------------------
Why ERA5, not CMIP6, and what that changes
--------------------------------------------------------------------------
Every other v3 hazard layer (heat, precipitation, SPEI) is a CMIP6 daily
projection for the explicit 2041-2070 window (``config.CMIP6_FUTURE_PERIOD``).
No CMIP6 GCM in this pipeline's configured set outputs a usable daily gust
variable, and the v3 methodology (``docs/rework/GEAR_v3_methodology_nature_
format.md`` Section 2/4) specifies ERA5 gust/sustained speed as the Extreme
Wind data source, not a CMIP6 projection. ERA5 is a **historical reanalysis**
(observationally constrained, 1940-present), not a future-scenario product --
there is no SSP axis, no GCM axis, and no 2050 horizon here.

**Flagged, not silently resolved**: this makes Extreme Wind's temporal basis
genuinely different from every other hazard's, not just differently labelled
-- see ``extreme_wind_processor.WIND_TEMPORAL_WINDOW`` and
``WIND_TEMPORAL_WINDOW_IS_PROJECTED = False`` for the explicit flag, and
``docs/DECISIONS.md`` ("GEAR v3 Phase 2.3: Extreme Wind processor") for the
open item this raises: the methodology draft names ERA5 as the source but
does not specify a baseline averaging period. ``ERA5_WIND_BASELINE_PERIOD``
below (1991-2020, the current WMO 30-yr climate normal) is an engineering
default, not a Phase-0-verified decision -- pending the author's confirmation
like the other open/provisional entries in ``docs/DECISIONS.md``.

--------------------------------------------------------------------------
Variable and request shape
--------------------------------------------------------------------------
``instantaneous_10m_wind_gust`` (ERA5 short name ``i10fg``) is the CDS token
for hourly instantaneous 10 m gust -- the same physical quantity the v3
methodology's Tier 1 (Wind, IEC cut-out) and Tier 3 (Solar, gust percentile)
rows both reference. There is no daily/annual pre-aggregated gust product on
the CDS catalogue; hourly instantaneous values must be downloaded and reduced
to an annual statistic downstream (``extreme_wind_processor``). Requests are
built one calendar year at a time (unlike the CMIP6 downloaders' single
30-year request) -- an ERA5 hourly request for a 30-year window in one call
is impractically large; per-year requests are the standard CDS usage pattern
for high-frequency ERA5 fields and let a partial download resume cleanly.

``_country_area``/``_climate_bounds`` are imported from
``cds_tasmax_downloader``, not re-implemented, so the wind bounding box is
the exact same per-country box the rest of the pipeline already uses.

--------------------------------------------------------------------------
Response format -- GRIB in practice, not guaranteed NetCDF (fixed 2026-09-12)
--------------------------------------------------------------------------
``reanalysis-era5-single-levels`` does not always return a real zip archive
of NetCDF files for this variable -- in practice the response for
``instantaneous_10m_wind_gust`` is a raw GRIB message. ``_download_raw_year``
detects this by magic bytes (``_is_grib``) and saves it with the correct
``.grib`` extension; it previously (bug, fixed this date) fell back to
writing the same raw bytes into a file literally named ``gust_hourly.nc``
whenever ``zipfile.ZipFile`` raised ``BadZipFile`` -- silently mislabeling a
GRIB payload as NetCDF. This was caught only because 18 already-downloaded
Brazil years (1991-2008) turned out to be unreadable by every plain-NetCDF
reader once cfgrib was installed and cross-checked against them (magic
bytes = ``GRIB``, not any NetCDF signature). ``open_gust_dataset`` opens
either format correctly by inspecting the actual file extension it was
saved under, never by assuming NetCDF. See ``docs/DECISIONS.md``, "GEAR v3
Phase 3.2 follow-up: ERA5 GRIB mislabeling bug fixed, 18 Brazil years
recovered".

--------------------------------------------------------------------------
Disk footprint -- process-then-delete per year (fixed 2026-09-12)
--------------------------------------------------------------------------
This module's own bulk functions (``download_country_baseline``/
``download_all_era5_wind``) keep every year's raw hourly file on disk at
once (~0.5-1 GB/year x 30 years/country) -- this is what filled the disk
mid-run in practice. They are kept for manual/debugging use only; the
production path is ``src.processors.extreme_wind_processor.
ensure_all_years_annual_max``, which downloads one year via
``_download_raw_year``, reduces it to that year's tiny per-pixel maximum
immediately, and deletes the raw file before starting the next year --
capping peak disk use at roughly one year's raw download regardless of
baseline length. See that function's docstring and ``docs/DECISIONS.md``,
"GEAR v3 Phase 3.2 follow-up: ERA5 download disk-footprint restructuring".
"""

from __future__ import annotations

import json
import logging
import time
import zipfile
from pathlib import Path

import xarray as xr

from src.config import CDS_API_URL, CLIMATE_RAW, require_cds_api_key
from src.downloaders.cds_tasmax_downloader import _country_area

logger = logging.getLogger(__name__)

CDS_DATASET = "reanalysis-era5-single-levels"
CDS_VARIABLE = "instantaneous_10m_wind_gust"

# WMO 30-yr climate normal, current cycle. NOT a Phase-0-verified constant --
# the methodology draft names ERA5 as the source but does not specify a
# baseline period. Flagged in docs/DECISIONS.md, pending author confirmation.
ERA5_WIND_BASELINE_PERIOD = ("1991-01-01", "2020-12-31")
_START, _END = ERA5_WIND_BASELINE_PERIOD
BASELINE_YEARS = list(range(int(_START[:4]), int(_END[:4]) + 1))
N_YEARS = len(BASELINE_YEARS)

_ALL_MONTHS = [f"{m:02d}" for m in range(1, 13)]
_ALL_DAYS = [f"{d:02d}" for d in range(1, 32)]
_ALL_HOURS = [f"{h:02d}:00" for h in range(24)]


def raw_dir(country: str, year: int) -> Path:
    return CLIMATE_RAW / "era5_wind" / country / str(year)


def _is_grib(path: Path) -> bool:
    """First 4 bytes of a real GRIB message are the literal ASCII ``GRIB``
    (edition 1 and 2 alike). Used to positively identify a CDS response that
    is not a valid zip, instead of assuming it must be NetCDF."""
    with open(path, "rb") as f:
        return f.read(4) == b"GRIB"


def _get_client():
    import cdsapi

    return cdsapi.Client(url=CDS_API_URL, key=require_cds_api_key())


def _build_request(country: str, year: int) -> dict:
    """One calendar year, every month/day/hour -- CDS silently ignores
    invalid dates (e.g. Feb 30) for this dataset, so requesting all 31 days
    for every month is safe and avoids a per-month day-count table."""
    return {
        "product_type": "reanalysis",
        "variable": CDS_VARIABLE,
        "year": [str(year)],
        "month": _ALL_MONTHS,
        "day": _ALL_DAYS,
        "time": _ALL_HOURS,
        "area": _country_area(country),
    }


def _download_raw_year(country: str, year: int, overwrite: bool) -> dict:
    """Download one country/year of hourly ERA5 gust. Returns a structured
    status dict; the raw ``cdsapi`` exception never propagates."""
    out_dir = raw_dir(country, year)
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / "gust_hourly.zip"
    marker = out_dir / ".downloaded"

    if marker.exists() and not overwrite:
        data_files = sorted(out_dir.glob("*.nc")) + sorted(out_dir.glob("*.grib"))
        if data_files:
            logger.info("ERA5 gust cached for %s/%d, skipping.", country, year)
            return {
                "success": True, "path": str(out_dir), "reason": "cached",
                "seconds": 0.0, "files": [str(f) for f in data_files],
            }

    request = _build_request(country, year)
    logger.info("CDS ERA5 gust request for %s/%d: %s", country, year, json.dumps(request))

    start = time.monotonic()
    try:
        client = _get_client()
        client.retrieve(CDS_DATASET, request, str(zip_path))
    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - start
        logger.error(
            "CDS ERA5 gust request failed for %s/%d after %.0fs: %s: %s",
            country, year, elapsed, type(exc).__name__, exc,
        )
        return {
            "success": False, "path": None,
            "reason": f"cds_error: {type(exc).__name__}: {exc}", "seconds": elapsed,
        }
    elapsed = time.monotonic() - start

    try:
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(out_dir)
        zip_path.unlink()
        data_files = sorted(out_dir.glob("*.nc"))
        if not data_files:
            logger.error(
                "CDS ERA5 gust %s/%d: zip extracted but no .nc member in %s",
                country, year, out_dir,
            )
            return {"success": False, "path": str(out_dir), "reason": "no_nc_after_extract", "seconds": elapsed}
    except zipfile.BadZipFile:
        # The CDS response was not actually a zip. Previously this silently
        # copied the raw bytes into a file named "gust_hourly.nc" -- if the
        # payload was GRIB (as it is for this dataset/variable in practice),
        # that mislabeled a GRIB file as NetCDF, and every reader downstream
        # either misread it silently or failed opaquely. Fixed: identify the
        # actual format by magic bytes and name it correctly, or fail loud.
        if _is_grib(zip_path):
            grib_path = out_dir / "gust_hourly.grib"
            zip_path.rename(grib_path)
            data_files = [grib_path]
            logger.info(
                "CDS ERA5 gust %s/%d: response was raw GRIB, not a zip -- "
                "saved as %s (not mislabeled .nc).",
                country, year, grib_path.name,
            )
        else:
            magic = zip_path.read_bytes()[:4]
            logger.error(
                "CDS ERA5 gust %s/%d: response is neither a valid zip nor "
                "GRIB (first 4 bytes: %r) -- unknown format, not saved as "
                "any extension.", country, year, magic,
            )
            return {
                "success": False, "path": str(out_dir),
                "reason": f"unknown_response_format: magic={magic!r}", "seconds": elapsed,
            }

    marker.write_text(f"downloaded in {elapsed:.0f}s: {[f.name for f in data_files]}")
    logger.info("CDS ERA5 gust %s/%d: OK in %.0fs", country, year, elapsed)
    return {
        "success": True, "path": str(out_dir), "reason": "downloaded",
        "seconds": elapsed, "files": [str(f) for f in data_files],
    }


def download_country_baseline(country: str, overwrite: bool = False) -> dict:
    """Download every year of ``ERA5_WIND_BASELINE_PERIOD`` for one country,
    keeping every year's raw hourly file on disk simultaneously (up to
    ~28 GB/country). Report is ``{year: status}``; failures on individual
    years do not stop the others.

    **Not the production path any more.** This is the bulk-download
    pattern that filled the disk mid-run in practice (GEAR v3 Phase 3.2
    follow-up incident, ``docs/DECISIONS.md``) -- kept only for manual/
    debugging use (e.g. inspecting a raw file by hand) where a small
    number of years is downloaded deliberately, not the full baseline.
    The production entry point is ``src.processors.extreme_wind_processor.
    ensure_all_years_annual_max``, which downloads, reduces, and deletes
    one year at a time, capping peak disk use at roughly one year's raw
    download (~0.5 GB) regardless of the baseline length.
    """
    return {year: _download_raw_year(country, year, overwrite) for year in BASELINE_YEARS}


def download_all_era5_wind(countries, overwrite: bool = False) -> dict:
    """``download_country_baseline`` for every country -- see that
    function's docstring: not the production path, debugging use only."""
    return {country: download_country_baseline(country, overwrite) for country in countries}


def open_gust_dataset(data_files: list[Path]) -> xr.Dataset:
    """Open one year's raw gust file(s), selecting the ``cfgrib`` engine for
    a GRIB response and the default (NetCDF) engine otherwise -- replaces
    the old ``_open_series``, which always assumed NetCDF and could not
    open a GRIB response at all.

    Format is detected from the file's own magic bytes (``_is_grib``), not
    its extension: years downloaded before the mislabeling fix (18 Brazil
    years, 1991-2008) are real GRIB content sitting in a file still named
    ``gust_hourly.nc`` on disk (fixing the bug does not retroactively rename
    already-downloaded files) -- content-based detection opens those
    correctly with no separate migration step, and also correctly opens
    every newly-downloaded, correctly-named ``.grib`` file the fixed
    ``_download_raw_year`` now produces. CDS returns exactly one file per
    one-variable-one-year request in practice; ``open_mfdataset`` is used
    only if more than one ever appears, so a multi-file response is not
    silently mishandled."""
    engine = "cfgrib" if _is_grib(data_files[0]) else None
    if len(data_files) == 1:
        return xr.open_dataset(data_files[0], engine=engine) if engine else xr.open_dataset(data_files[0])
    kwargs = {"engine": engine} if engine else {}
    return xr.open_mfdataset([str(f) for f in data_files], combine="by_coords", **kwargs)


def _pick_var(ds: xr.Dataset) -> str:
    for candidate in ("i10fg", "fg10", "instantaneous_10m_wind_gust"):
        if candidate in ds.data_vars:
            return candidate
    return list(ds.data_vars)[0]


if __name__ == "__main__":
    import argparse
    import sys

    from src.config import COUNTRIES

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--country", required=True, choices=COUNTRIES)
    parser.add_argument("--year", type=int, default=None, help="single year; default = whole baseline period")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if args.year is not None:
        result = {args.year: _download_raw_year(args.country, args.year, args.overwrite)}
    else:
        result = download_country_baseline(args.country, args.overwrite)

    print(json.dumps(result, indent=2, default=str))
    sys.exit(0 if all(v["success"] for v in result.values()) else 1)
