"""
Central configuration for the GEAR acquisition/processing layer.

Every downloader and processor imports from this module; none runs without it
(see docs/INVENTORY.md, "Dependência compartilhada obrigatória"). It defines:

* the directory layout under ``data/``;
* the fixed model parameters (countries, target grid, CRS, scenario lists);
* the data-source endpoints and snapshot identifiers;
* credential loading from ``credentials.local`` plus ``require_*()`` helpers
  that fail with an actionable message when a required secret is absent.

Secrets are never hardcoded. ``credentials.local`` (git-ignored) is the only
file read for credentials; it is loaded once, at import time, via
``python-dotenv``.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS_FILE = BASE_DIR / "credentials.local"
load_dotenv(CREDENTIALS_FILE)

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = DATA_DIR / "outputs"

CLIMATE_RAW = RAW_DIR / "climate"
ASSETS_RAW = RAW_DIR / "assets"
BOUNDARIES_RAW = RAW_DIR / "boundaries"
VALIDATION_RAW = RAW_DIR / "validation"

CLIMATE_PROCESSED = PROCESSED_DIR / "climate"
ASSETS_PROCESSED = PROCESSED_DIR / "assets"

OUTPUT_MAPS = OUTPUT_DIR / "maps"
OUTPUT_TABLES = OUTPUT_DIR / "tables"
OUTPUT_INSPECTION = OUTPUT_DIR / "inspection"

LOG_DIR = BASE_DIR / "logs"

# --------------------------------------------------------------------------
# Credentials (read from credentials.local, never hardcoded)
# --------------------------------------------------------------------------
GEE_PROJECT_ID = os.getenv("GEE_PROJECT_ID")
CDS_API_KEY = os.getenv("CDS_API_KEY")
CDS_API_URL = os.getenv("CDS_API_URL", "https://cds.climate.copernicus.eu/api")

# Reserved — no active downloader uses these. EARTHDATA_* would only be needed
# for NASA Earthdata access; EMDAT_PORTAL_* only for the authenticated
# public.emdat.be portal. The active EM-DAT path uses the open UCLouvain
# Dataverse and needs no credential.
EARTHDATA_USERNAME = os.getenv("EARTHDATA_USERNAME")
EARTHDATA_PASSWORD = os.getenv("EARTHDATA_PASSWORD")
EMDAT_PORTAL_EMAIL = os.getenv("EMDAT_PORTAL_EMAIL")
EMDAT_PORTAL_PASSWORD = os.getenv("EMDAT_PORTAL_PASSWORD")


class MissingCredentialError(RuntimeError):
    """Raised when a required credential is absent from ``credentials.local``.

    Downloaders that genuinely need a secret (CDS, and the reserved paths)
    raise this instead of letting an opaque third-party exception surface.
    The Aqueduct downloader is the deliberate exception: it *skips* its step
    when ``GEE_PROJECT_ID`` is missing rather than raising.
    """


def _require(value: str | None, var_name: str, example_line: str) -> str:
    if not value:
        raise MissingCredentialError(
            f"Credential '{var_name}' is missing or empty. Add the following "
            f"line to '{CREDENTIALS_FILE}':\n    {example_line}"
        )
    return value


def require_gee_project_id() -> str:
    return _require(GEE_PROJECT_ID, "GEE_PROJECT_ID", "GEE_PROJECT_ID=your-gee-project")


def require_cds_api_key() -> str:
    return _require(CDS_API_KEY, "CDS_API_KEY", "CDS_API_KEY=your-cds-api-key")


def require_earthdata_credentials() -> tuple[str, str]:
    """Reserved — no active downloader calls this."""
    return (
        _require(EARTHDATA_USERNAME, "EARTHDATA_USERNAME", "EARTHDATA_USERNAME=your-user"),
        _require(EARTHDATA_PASSWORD, "EARTHDATA_PASSWORD", "EARTHDATA_PASSWORD=your-pass"),
    )


def require_emdat_portal_credentials() -> tuple[str, str]:
    """Reserved — the active EM-DAT downloader uses the open Dataverse and
    does not call this. Kept so that a future authenticated public.emdat.be
    path fails with the same ``MissingCredentialError`` as every other
    source."""
    return (
        _require(EMDAT_PORTAL_EMAIL, "EMDAT_PORTAL_EMAIL", "EMDAT_PORTAL_EMAIL=your-email"),
        _require(EMDAT_PORTAL_PASSWORD, "EMDAT_PORTAL_PASSWORD", "EMDAT_PORTAL_PASSWORD=your-pass"),
    )


# --------------------------------------------------------------------------
# Model parameters
# --------------------------------------------------------------------------
COUNTRIES = ["Brazil", "Portugal", "India"]

COUNTRY_ISO3 = {
    "Brazil": "BRA",
    "Portugal": "PRT",
    "India": "IND",
}

# Countries whose overseas territories are outside the study scope. Portugal
# excludes the Azores and Madeira archipelagos. Read by the boundaries
# downloader (largest-polygon filter) and the assets validator (physical
# exclusion of island plants).
MAINLAND_ONLY_COUNTRIES = {"Portugal"}

# Minimum climate-download coverage box per country (xmin, ymin, xmax, ymax),
# decimal degrees. The extreme-heat downloader requests, and clips to, the
# per-coordinate UNION of this box and the GADM level-0 bounds
# (cds_tasmax_downloader._climate_bounds). It exists because two effects pull
# the GADM bbox in below the study's real footprint:
#   * GADM 4.1 level-0 India stops at ~33.26 N / ~68.19 E — it omits most of
#     Indian-administered Jammu & Kashmir and Ladakh, and the far west of
#     Kutch, which hold in-scope operating plants (Chenab/Jhelum hydro,
#     thermal near Kutch).
#   * the CMIP6 GCM native grid (~1 deg lat, ~1.25 deg lon) snaps the
#     requested area inward by up to one cell, eroding e.g. the northern
#     border of mainland Portugal (plants at ~42.08 N were dropped at the
#     42.0 cell edge).
# These boxes are mainland / in-scope territory only. They must NOT re-include
# the Azores or Madeira — that exclusion is MAINLAND_ONLY_COUNTRIES plus the
# largest-polygon filter in boundaries_downloader, and is intentional. Brazil's
# box matches its GADM bounds, so the union is a no-op there.
COUNTRY_BBOX_FALLBACK = {
    "Brazil": (-73.99, -33.75, -28.84, 5.27),
    "Portugal": (-9.75, 36.75, -6.00, 43.00),
    "India": (67.50, 6.50, 97.50, 37.50),
}

CRS_TARGET = "EPSG:4326"
RESOLUTION_TARGET_DEG = 0.008333  # ~1 km nominal

YEAR_TARGET = 2050

# --------------------------------------------------------------------------
# Scenario mapping
# --------------------------------------------------------------------------
# Aqueduct 4.0 future_annual ships one column per scenario per basin, using
# WRI's native short labels. The SSP-RCP identities below are from WRI's
# official data dictionary (github.com/wri/Aqueduct40) and the Technical
# Note (Kuzma et al. 2023, DOI 10.46830/writn.23.00061):
#   opt = SSP1-RCP2.6   bau = SSP3-RCP7.0   pes = SSP5-RCP8.5
# "opt" and "pes" are the *same* SSP-RCP scenarios as the CMIP6 heat layer,
# only labelled differently because they come from a different pipeline.
# "bau" (SSP3-7.0) has no counterpart in the active heat scenarios.
AQUEDUCT_SCENARIOS = ["bau", "opt", "pes"]

AQUEDUCT_TO_SSP_LABEL = {
    "opt": "SSP1-2.6",
    "bau": "SSP3-7.0",
    "pes": "SSP5-8.5",
}

# Emission scenarios used by the extreme-heat layer (Copernicus CDS / CMIP6).
CMIP6_SCENARIOS = ["ssp126", "ssp585"]

# Value required by the CDS "experiment" parameter for each scenario above.
CMIP6_SCENARIO_TO_CDS_EXPERIMENT = {
    "ssp126": "ssp1_2_6",
    "ssp585": "ssp5_8_5",
}

# Scenario-identity pairing between the water (Aqueduct) and heat (CMIP6)
# layers, used downstream to combine hazards. "bau" is left out — no CMIP6
# counterpart in the active scenario set.
AQUEDUCT_SCENARIO_FOR_CMIP6 = {
    "ssp126": "opt",
    "ssp585": "pes",
}

# --------------------------------------------------------------------------
# CMIP6 GCM configuration
# --------------------------------------------------------------------------
# List, not a scalar: ARCHITECTURE.md Section 4 makes a second GCM a
# mandatory sensitivity check. The downloader and processors iterate over
# this list for both ssp126 and ssp585. Only GFDL-ESM4 is populated now; the
# second entry is pending post-data verification item V4 (model choice and
# country coverage).
CMIP6_SOURCE_ID_CDS = [
    "gfdl_esm4",
    # <pending V4: second GCM, e.g. a model with a structurally different
    #  convection / hydrological-cycle parameterisation than GFDL-ESM4>
]

CMIP6_FUTURE_PERIOD = ("2041-01-01", "2070-12-31")  # the "2050" window
EXTREME_HEAT_THRESHOLD_C = 40  # a "day of extreme heat" has tasmax above this

RANDOM_SEED = 42  # stochastic sampling — used only by the not-yet-rebuilt layer

# --------------------------------------------------------------------------
# Data sources
# --------------------------------------------------------------------------
# GADM 4.1 national boundaries (level 0), GeoPackage.
GADM_BASE_URL = "https://geodata.ucdavis.edu/gadm/gadm4.1/gpkg"

# WRI Aqueduct 4.0 water risk, future annual, via Google Earth Engine.
AQUEDUCT_FC_ID = "WRI/Aqueduct_Water_Risk/V4/future_annual"

# EM-DAT Archive on the UCLouvain Dataverse (Delforge et al.), open, citable
# by DOI, snapshot dated 2026-04-30 by the EM-DAT team.
EMDAT_ARCHIVE_PERSISTENT_ID = "doi:10.14428/DVN/I0LTPH"
EMDAT_DATAVERSE_API_BASE = "https://dataverse.uclouvain.be/api"

# Complementary national asset registries. The downloaders that consume these
# (ANEEL for Brazil, DGEG for Portugal) are NOT part of this rebuild; the
# endpoints are retained so the constants exist if that decision is revisited.
ANEEL_CKAN_BASE_URL = "https://dadosabertos.aneel.gov.br/api/3/action"
DGOVPT_API_BASE_URL = "https://dados.gov.pt/api/1"
