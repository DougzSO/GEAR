"""
GEAR v3 Phase 5 -- contextual validator layer (``docs/rework/
GEAR_v3_methodology_nature_format.md`` Section 7; ``docs/rework/
GEAR_v3_work_plan.md`` Phase 5).

Two validator classes (Section 7.1/7.2), deliberately not conflated, each
reporting the SAME three-state output per applicable hazard per asset
(Section 7.3): ``Corroborated`` / ``No Record`` / ``Not Applicable``, post-
2000 only. **No validator state modifies PSAE, RiskBand, or Risk_i,h under
any circumstance** (Section 7.3, verbatim) -- this module is a read-only
overlay: it imports ``risk_calculator.load_plants`` and ``hazard_scope.
APPLICABLE_HAZARDS`` to know which (asset, hazard) pairs to report on, and
never calls, imports, or mutates anything in ``psae.py``/``risk_bands.py``/
``risk_calculator.py`` beyond that read. See
``tests/test_contextual_validators.py``'s explicit before/after equality
tests for the read-only guarantee.

--------------------------------------------------------------------------
Data-source availability -- checked before writing any acquisition code,
per the standing "never acquire new data without author confirmation" rule
--------------------------------------------------------------------------
* **Broad-impact (Section 7.2, EM-DAT)**: already acquired and on disk for
  all three countries (``src/downloaders/emdat_downloader.py``,
  ``data/raw/validation/emdat_{country}.csv``) -- CCRS-era work, reusable.
  **Implemented in this module.**
* **Physical-occurrence (Section 7.1, IBTrACS/FIRMS/landslide/lightning)**:
  grep-confirmed **zero** acquisition code or data anywhere in this project
  (``grep -rl "IBTrACS\\|ibtracs" --include=*.py`` and the FIRMS equivalent
  both return nothing under ``src/``; the substring hits in
  ``tests/test_extreme_wind_processor.py``/``tests/test_visualization.py``
  are false positives -- "con**firms**"). Per this task's explicit
  instruction: **not acquired here.** This module is therefore a
  **PARTIAL implementation of Phase 5** -- the broad-impact class only, the
  two-class taxonomy left structurally ready (``ValidatorClass``,
  ``THREE_STATE_LABELS``) for a physical-occurrence class to be added once
  an author decides which source to acquire and how. Labelled as partial,
  not closed, per this project's own partial-closure convention -- see
  ``docs/DECISIONS.md``.

--------------------------------------------------------------------------
Not the retired src/index/emdat_validation.py, reused where it still fits
--------------------------------------------------------------------------
The retired module (CCRS-era, currently broken by Phase 1's deletion of
``ccrs_calculator``) is a polygon-level Mann-Whitney diagnostic ("do
hazard-raster values differ between admin-1 polygons with vs. without a
geocoded EM-DAT event"), not a per-asset three-state validator -- a
genuinely different design, not reusable as-is, exactly as this task's
brief states. Its ``GADM Admin Units`` JSON-parsing logic (admin-1 GID
resolution) and its documented coverage caveats ARE reused here (not
importable -- the retired module cannot be imported at all, broken
dependency), reproduced below rather than duplicated blind: EM-DAT's own
point Latitude/Longitude covers only 5.3-12.1% of events across the three
countries (Portugal: 2 events) -- unusable for a per-asset radius search.
The structured ``GADM Admin Units`` field covers 50.3-52.6% -- enough for
an admin-1-polygon overlay, the granularity used here (Section 7.3 says
"location/radius"; admin-1-polygon containment is this project's own
established, data-quality-driven operationalization of that phrase, not a
literal fixed-radius search, since EM-DAT's own point coordinates are
mostly absent). The ~47-50% of events with no structured geocoding at all
are silently excluded from every validator state below -- the SAME
real, non-random coverage gap the retired module already documented
(better-documented/urban disasters plausibly over-represented in the
geocoded half). Every "No Record" state below answers "no GEOCODED event
was found", not "no event ever occurred" -- narrower, stated here once
rather than re-litigated per state.

--------------------------------------------------------------------------
Disaster-type -> hazard-term mapping -- inherited UNCHANGED, an open item
flagged, not silently extended
--------------------------------------------------------------------------
``EMDAT_DISASTER_TYPE_TO_TERM`` below is the retired module's own mapping,
verbatim (approved by Douglas, 2026-09-04): ``Extreme temperature -> heat``,
``Drought -> spei``, ``Flood -> ws`` (an explicitly acknowledged poor
match -- water STRESS, not excess water -- kept only because no better term
existed in the CCRS-era hazard set), ``Storm`` excluded (no wind hazard
term existed yet). v3 now has both ``precip`` (Extreme Precipitation, a
plausibly much better "Flood" proxy) and ``wind`` (a real "Storm" target)
that did not exist when this mapping was approved. **Not extended here**:
re-deriving a disaster-type/hazard-term mapping is a methodology judgment
call this task's brief did not ask for and Section 7 does not specify --
flagged as an open item in ``docs/DECISIONS.md`` for author confirmation,
not decided by this module.

Standalone: ``python -m src.index.contextual_validators`` writes
``data/outputs/tables/contextual_validators.csv``.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd

from src.config import BOUNDARIES_RAW, COUNTRIES, COUNTRY_ISO3, MAINLAND_ONLY_COUNTRIES, OUTPUT_TABLES
from src.downloaders import emdat_downloader
from src.downloaders.boundaries_downloader import get_country_geometry
from src.index import hazard_scope as hs
from src.index import risk_calculator as rc

logger = logging.getLogger(__name__)

PLANT_UID = rc.PLANT_UID

# --------------------------------------------------------------------------
# Three-state output (Section 7.3) -- exactly these three tokens, shared by
# every validator class.
# --------------------------------------------------------------------------
CORROBORATED = "Corroborated"
NO_RECORD = "No Record"
NOT_APPLICABLE = "Not Applicable"
THREE_STATE_LABELS = (CORROBORATED, NO_RECORD, NOT_APPLICABLE)

# Section 7.3: "Historical window: post-2000 only for all sources."
VALIDATION_WINDOW_START_YEAR = 2000

# The two classes (Section 7.1/7.2) -- named here so a future
# physical-occurrence implementation registers under the same taxonomy
# rather than inventing a parallel one.
VALIDATOR_CLASS_PHYSICAL_OCCURRENCE = "physical_occurrence"
VALIDATOR_CLASS_BROAD_IMPACT = "broad_impact"

OUTPUT_COLUMNS = [
    PLANT_UID, "country", "plant_name", "bucket", "validator_class",
    "source", "hazard_term", "state", "n_geocoded_events", "gid_1",
]

# --------------------------------------------------------------------------
# Broad-impact (EM-DAT) disaster-type -> GEAR hazard-term mapping -- see
# module docstring, "inherited UNCHANGED, an open item flagged".
# --------------------------------------------------------------------------
EMDAT_DISASTER_TYPE_TO_TERM = {
    "Extreme temperature": "heat",
    "Drought": "spei",
    "Flood": "ws",
}
_TERM_TO_EMDAT_DISASTER_TYPE = {v: k for k, v in EMDAT_DISASTER_TYPE_TO_TERM.items()}

_GID_KEY_RE = re.compile(r"^gid_(\d+)$")


# --------------------------------------------------------------------------
# Admin-1 boundaries + GADM GID parsing -- reproduced from the retired
# (unimportable) src/index/emdat_validation.py, see module docstring.
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


def load_geocoded_emdat_events(country: str) -> pd.DataFrame:
    """One row per (``disaster_type``, admin-1 ``gid_1``, ``start_year``) an
    EM-DAT event resolves to, restricted to disaster types this module has a
    hazard-term mapping for. Multiple admin-1 GIDs per event (a multi-
    province event) each get their own row; events with no ``GADM Admin
    Units`` entry, or a type this module has no term mapping for, are
    absent -- the coverage gap the module docstring documents, not a bug.
    ``start_year`` is kept unfiltered here (post-2000 is applied by the
    caller) so this function stays a pure "what does EM-DAT's geocoding
    say" read."""
    path = emdat_downloader.country_csv_path(country)
    df = pd.read_csv(path)
    df = df[df["Disaster Type"].isin(EMDAT_DISASTER_TYPE_TO_TERM)]
    rows = []
    for disaster_type, gadm_cell, start_year in zip(
        df["Disaster Type"], df["GADM Admin Units"], df["Start Year"],
    ):
        for gid in _admin1_gids_from_cell(gadm_cell):
            rows.append({
                "disaster_type": disaster_type,
                "hazard_term": EMDAT_DISASTER_TYPE_TO_TERM[disaster_type],
                "gid_1": gid,
                "start_year": start_year,
            })
    return pd.DataFrame(rows, columns=["disaster_type", "hazard_term", "gid_1", "start_year"])


# --------------------------------------------------------------------------
# Plant -> admin-1 polygon spatial join
# --------------------------------------------------------------------------
def _plants_with_admin1(country: str) -> pd.DataFrame:
    """``risk_calculator.load_plants(country)`` plus a ``gid_1`` column
    (point-in-polygon join against the same admin-1 layer
    ``load_geocoded_emdat_events`` resolves events onto). ``gid_1`` is
    ``None`` for a plant whose point does not fall inside any admin-1
    polygon (e.g. a coordinate just outside a coastline simplification) --
    kept as an explicit ``None``, never silently dropped or guessed at."""
    plants = rc.load_plants(country)
    admin1 = _load_admin1_boundaries(country)[["GID_1", "geometry"]]
    points = gpd.GeoDataFrame(
        plants,
        geometry=gpd.points_from_xy(plants["lon"], plants["lat"]),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(points, admin1.to_crs("EPSG:4326"), how="left", predicate="within")
    joined = joined.drop(columns=["geometry", "index_right"], errors="ignore")
    joined = joined.rename(columns={"GID_1": "gid_1"})
    joined = joined.drop_duplicates(subset=[PLANT_UID], keep="first")
    return pd.DataFrame(joined)


# --------------------------------------------------------------------------
# Broad-impact (EM-DAT) validator -- Section 7.2
# --------------------------------------------------------------------------
def compute_broad_impact_validation(countries: list[str] | None = None) -> pd.DataFrame:
    """One row per (plant, hazard_term) for every hazard_term in that
    plant's bucket's ``hazard_scope.APPLICABLE_HAZARDS`` -- the three-state
    EM-DAT broad-impact output (Section 7.2/7.3). Read-only: reads
    ``risk_calculator.load_plants`` and ``hazard_scope.APPLICABLE_HAZARDS``,
    writes nothing back to either, never touches ``psae``/``risk_bands``.

    State assignment per (plant, hazard_term):
    - ``Not Applicable`` if ``hazard_term`` has no EM-DAT disaster-type
      mapping (``EMDAT_DISASTER_TYPE_TO_TERM`` -- this data source has no
      coverage for that hazard at all, not an asset-specific fact) OR the
      plant's point could not be placed in any admin-1 polygon (spatial
      join miss -- this source cannot be checked for that asset).
    - ``Corroborated`` if >=1 geocoded event of the mapped disaster type,
      ``start_year >= 2000``, resolves to the plant's ``gid_1``.
    - ``No Record`` otherwise (validator applicable, checked, nothing
      found).
    """
    countries = countries or COUNTRIES
    rows = []
    for country in countries:
        plants = _plants_with_admin1(country)
        events = load_geocoded_emdat_events(country)
        events = events[events["start_year"] >= VALIDATION_WINDOW_START_YEAR]
        # count of qualifying (post-2000, geocoded) events per (hazard_term, gid_1)
        counts = (
            events.groupby(["hazard_term", "gid_1"]).size()
            if not events.empty else pd.Series(dtype="int64")
        )

        for plant in plants.itertuples(index=False):
            bucket = plant.bucket
            applicable = hs.APPLICABLE_HAZARDS.get(bucket, ())
            gid_1 = getattr(plant, "gid_1", None)
            for hazard_term in applicable:
                mapped = hazard_term in _TERM_TO_EMDAT_DISASTER_TYPE
                if not mapped or pd.isna(gid_1) or gid_1 is None:
                    state = NOT_APPLICABLE
                    n_events = 0
                else:
                    n_events = int(counts.get((hazard_term, gid_1), 0))
                    state = CORROBORATED if n_events > 0 else NO_RECORD

                rows.append({
                    PLANT_UID: getattr(plant, PLANT_UID),
                    "country": country,
                    "plant_name": plant.plant_name,
                    "bucket": bucket,
                    "validator_class": VALIDATOR_CLASS_BROAD_IMPACT,
                    "source": "EM-DAT",
                    "hazard_term": hazard_term,
                    "state": state,
                    "n_geocoded_events": n_events,
                    "gid_1": gid_1 if (gid_1 is not None and not pd.isna(gid_1)) else None,
                })

    out = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    key = [PLANT_UID, "validator_class", "hazard_term"]
    dup = int(out.duplicated(key).sum())
    if dup:
        raise RuntimeError(f"compute_broad_impact_validation produced {dup} duplicate {key} rows.")
    return out


# --------------------------------------------------------------------------
# Physical-occurrence validator -- Section 7.1. NOT IMPLEMENTED: no source
# acquired (see module docstring). Named here as the explicit, honest stop
# point rather than silently absent.
# --------------------------------------------------------------------------
def compute_physical_occurrence_validation(countries: list[str] | None = None) -> pd.DataFrame:
    raise NotImplementedError(
        "Phase 5 physical-occurrence validator (Section 7.1: IBTrACS/FIRMS/"
        "landslide/lightning) has no acquired data source in this project "
        "(grep-confirmed) -- not implemented per the standing rule against "
        "acquiring new data without author confirmation. See "
        "docs/DECISIONS.md, 'GEAR v3 Phase 5: contextual validator layer "
        "(broad-impact only, partial)'."
    )


# --------------------------------------------------------------------------
# Combined entry point -- currently broad-impact only (see above).
# --------------------------------------------------------------------------
def compute_contextual_validation(countries: list[str] | None = None) -> pd.DataFrame:
    """Every implemented validator class, stacked. Physical-occurrence is
    absent (not implemented -- see module docstring), not silently
    represented as ``Not Applicable`` everywhere."""
    return compute_broad_impact_validation(countries)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=OUTPUT_TABLES)
    args = parser.parse_args()

    result = compute_contextual_validation()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / "contextual_validators.csv"
    result.to_csv(out_path, index=False)
    logger.info(
        "wrote %s (%d rows, broad_impact class only -- physical_occurrence "
        "not implemented, no acquired source)", out_path, len(result),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
