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
        nc_files = sorted(out_dir.glob("*.nc"))
        if nc_files:
            logger.info("ERA5 gust cached for %s/%d, skipping.", country, year)
            return {
                "success": True, "path": str(out_dir), "reason": "cached",
                "seconds": 0.0, "files": [str(f) for f in nc_files],
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
    except zipfile.BadZipFile:
        (out_dir / "gust_hourly.nc").write_bytes(zip_path.read_bytes())

    nc_files = sorted(out_dir.glob("*.nc"))
    if not nc_files:
        logger.error(
            "CDS ERA5 gust %s/%d: download finished but no .nc file in %s",
            country, year, out_dir,
        )
        return {"success": False, "path": str(out_dir), "reason": "no_nc_after_extract", "seconds": elapsed}

    marker.write_text(f"downloaded in {elapsed:.0f}s: {[f.name for f in nc_files]}")
    logger.info("CDS ERA5 gust %s/%d: OK in %.0fs", country, year, elapsed)
    return {
        "success": True, "path": str(out_dir), "reason": "downloaded",
        "seconds": elapsed, "files": [str(f) for f in nc_files],
    }


def download_country_baseline(country: str, overwrite: bool = False) -> dict:
    """Download every year of ``ERA5_WIND_BASELINE_PERIOD`` for one country.
    Report is ``{year: status}``; failures on individual years do not stop
    the others."""
    return {year: _download_raw_year(country, year, overwrite) for year in BASELINE_YEARS}


def download_all_era5_wind(countries, overwrite: bool = False) -> dict:
    """Process every configured country over the full baseline period.
    Report is nested ``country -> year -> status``."""
    return {country: download_country_baseline(country, overwrite) for country in countries}


def _open_series(nc_files: list[Path]) -> xr.Dataset:
    if len(nc_files) == 1:
        return xr.open_dataset(nc_files[0])
    return xr.open_mfdataset([str(f) for f in nc_files], combine="by_coords")


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
