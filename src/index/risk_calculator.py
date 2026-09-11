"""
GEAR v3 core equation -- ``Risk_{i,h}``, per plant, per hazard, per scenario
and GCM (``docs/rework/GEAR_v3_methodology_nature_format.md`` Section 1,
Equation 1; ``docs/rework/GEAR_v3_work_plan.md`` Phase 1).

    Risk_{i,h} = Hazard_{i,h} * Exposure_i * Vulnerability_i             (1)

This module replaces ``src/index/ccrs_calculator.py`` (retired, see
``docs/DECISIONS.md``). The prior architecture combined every hazard term
into one weighted-sum ``Hazard_{i,s}`` per plant (the CCRS core) and then
multiplied it by ``age_factor`` and ``EventMultiplier``. Both changes below
are decisions, not omissions:

* **No weighted sum across hazards.** ``Risk_{i,h}`` is computed and kept
  **per hazard** -- there is no combined "Hazard" value for a plant, and
  nothing in this module sums or blends ``Risk_{i,h}`` across different
  hazards ``h``. The v3 methodology treats that as a stated fallacy
  (Section 9, Overview): a plant's wind risk and drought risk are never
  added into one number here.
* **No ``EventMultiplier``.** Retired from this core entirely (Phase 1.4) --
  not imported, not called, not referenced. Its future as a Phase 5
  contextual validator (physical-occurrence / broad-impact corroboration,
  never re-entering the score) is out of scope for this module.

--------------------------------------------------------------------------
Exposure -- two forms, only one of them a Risk input
--------------------------------------------------------------------------
``Exposure_i`` is installed capacity, reported in two explicit forms
(Methods Section 1), never conflated:

* ``exposure_capacity_mw`` -- **Systemic Capacity at Risk**, raw MW. The
  only form ``risk_i_h`` accepts. Used in every comparability-relevant
  calculation.
* ``exposure_log10_display`` -- **Intrinsic Asset Risk**, ``log10(MW + 1)``,
  a map/legend display transform only, so a handful of very large plants do
  not visually dominate a map and mask physically severe risk at smaller
  assets. Tier 3, author-declared, no literature precedent.

The guard is enforced at the type level, not just by convention:
``exposure_log10_display`` returns an ``ExposureLog10Display``-tagged array
(a distinct ``np.ndarray`` subclass); ``risk_i_h`` raises ``TypeError`` if
handed one. A caller cannot accidentally feed the display transform into a
scoring/ranking calculation without an explicit, loud failure.

--------------------------------------------------------------------------
Vulnerability
--------------------------------------------------------------------------
``Vulnerability_i`` is ``age_factor_i`` (unchanged, ``src/index/
age_factor.py``, spec item D / ``docs/DECISIONS.md`` 2026-09-04 final): the
``>= 1`` ``2 - retention(age)`` capacity/efficiency-retention multiplier.
Not redefined here -- this module imports and applies it, never recomputes
it.

--------------------------------------------------------------------------
Hazard terms currently computable, and an open methodology question
--------------------------------------------------------------------------
The v3 methodology's six-hazard core checklist (Section 2) lists exactly:
Water Stress, Extreme Heat, Drought, Extreme Precipitation, Wildfire, Extreme
Wind. Of these, only three have raw data acquired and processed as of Phase
1: Water Stress (``ws``), Extreme Heat (``heat``), Drought (``spei``).
Extreme Precipitation, Wildfire and Extreme Wind are Phase 2 acquisition
work, not yet available, and are therefore not computed here.

**Flagged, not silently resolved**: the pre-v3 codebase also computed two
further Aqueduct indicators, seasonal variability (``sv``) and interannual
variability (``iv``), combined with ``ws`` into a composite ``water_sub``
term. The v3 methodology's Section 2 checklist names only "Water Stress" as
a hazard -- it does not list ``sv``/``iv`` as separate hazards, and gives no
instruction to fold them into Water Stress either. Rather than silently
carrying the old composite forward (which would smuggle a pre-v3 assumption
into the Equation 1 restructuring) or silently dropping ``sv``/``iv``
(losing a signal that might still be wanted), this module computes
``Risk_{i,h}`` for ``sv`` and ``iv`` as their own, independent, clearly
labelled hazard terms -- exactly like every other term -- using their
existing per-term ``FROZEN_BOUNDS``. Their inclusion in, exclusion from, or
any other treatment in the FINAL applicable-hazard set per bucket is a
Phase 3 decision (Section 3, per-bucket ``H_b`` tables), not decided here.
Until Phase 3 resolves this, ``sv``/``iv`` rows exist in this module's
output but are not implied to be part of the "Water Stress" hazard the
methodology names.

--------------------------------------------------------------------------
Temporal-window assumption per hazard -- explicit, not buried in prose
--------------------------------------------------------------------------
Per the standing modularity rule (work plan), every hazard's temporal-window
assumption is an explicit, readable constant (``HAZARD_TEMPORAL_WINDOW``
below), not left to be inferred from a processor's docstring. This encodes
Methods Section 1.1's finding: ``ws``/``sv``/``iv`` are Aqueduct
``future_annual`` (a period-representative ~2050 point estimate, not a
30-year window); ``heat``/``spei`` are the explicit CMIP6 2041-2070 window,
represented by 2050. Both are treated as targeting the same nominal
mid-century horizon (a stated, literature-consistent approximation, not a
flaw), but the two are not an identical averaging window -- declared here in
code, so a future audit of data-window alignment does not require reading
every processor line by line.

--------------------------------------------------------------------------
Transforms, bounds, plant identity, GCM handling -- unchanged from the
retired ``ccrs_calculator.py``
--------------------------------------------------------------------------
The per-term normalization (``Tlog``/``Tlin``, ``FROZEN_BOUNDS``, the
frozen-bounds regression guard), the ``plant_uid`` content-hash identity, and
the GFDL-ESM4-primary / MIROC6-sensitivity-panel GCM rule are methodology
that Phase 1 does not revisit -- carried over verbatim. This module is
deliberately kept import-light and free of any correlation-gate or
threshold-tier logic: Phase 2.4 (normalization as its own isolated module)
and Phase 2.5 (the correlation gate as its own class) are separate,
not-yet-done phases that will import from here, not be folded into it.

Standalone: ``python -m src.index.risk_calculator`` from the project root.
Reads the processed raw rasters and ``gem_validated_plants_{country}.csv``;
writes ``data/outputs/tables/risk_by_hazard.csv``.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol

from src.config import (
    AQUEDUCT_SCENARIO_FOR_CMIP6,
    ASSETS_PROCESSED,
    COUNTRIES,
    COUNTRY_ISO3,
    OUTPUT_TABLES,
)
from src.downloaders.cds_tasmax_downloader import configured_models
from src.processors.heat_stress_processor import raw_raster_path as heat_raw_path
from src.processors.spei_processor import raw_raster_path as spei_raw_path
from src.processors.water_stress_processor import raw_raster_path as ws_raw_path
from src.processors.water_variability_processor import raw_raster_path as var_raw_path

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Terms and transforms
# --------------------------------------------------------------------------
# NOT the final v3 applicable-hazard set -- see the module docstring section
# "Hazard terms currently computable". Extreme Precipitation / Wildfire /
# Extreme Wind are absent (Phase 2, not yet acquired); sv/iv are present but
# flagged pending Phase 3.
HAZARD_TERMS = ("ws", "heat", "sv", "iv", "spei")
LOG_TERMS = frozenset({"ws", "heat", "spei"})   # log1p -> Min-Max
LIN_TERMS = frozenset({"sv", "iv"})             # linear Min-Max
# Terms whose global bound is per-GCM (magnitudes are not model-comparable);
# every other term's bound is a single flat pair pooling all GCMs.
GCM_DEPENDENT_TERMS = frozenset({"heat", "spei"})
FLAT_BOUND_TERMS = tuple(t for t in HAZARD_TERMS if t not in GCM_DEPENDENT_TERMS)

# ``wd`` (water depletion) is left out: rank-redundant with ``ws``
# (Spearman 0.98-0.998, analysis/aqueduct_indicator_correlation.md). This
# finding predates v3 and is unaffected by the Phase 1 restructuring.
EXCLUDED_INDICATORS = ("wd",)

# Human-readable hazard label per term, and whether the term is one of the
# v3 methodology's six named core hazards (Section 2) or a carried-over,
# not-yet-decided indicator (see module docstring).
HAZARD_LABELS = {
    "ws": "Water Stress",
    "heat": "Extreme Heat",
    "spei": "Drought",
    "sv": "Water Seasonal Variability (not a v3 Section 2 hazard -- Phase 3 pending)",
    "iv": "Water Interannual Variability (not a v3 Section 2 hazard -- Phase 3 pending)",
}
V3_CORE_HAZARD_TERMS = frozenset({"ws", "heat", "spei"})

# --------------------------------------------------------------------------
# Temporal-window assumption per hazard term -- explicit, named, not buried
# in a docstring (standing modularity rule; Methods Section 1.1).
# --------------------------------------------------------------------------
HAZARD_TEMPORAL_WINDOW: dict[str, dict[str, object]] = {
    "ws": {
        "source": "aqueduct_future_annual",
        "horizon_year": 2050,
        "window": "point_estimate_2050",
        "is_explicit_30yr_window": False,
        "note": "WRI Aqueduct 4.0 future_annual, horizon 50 -- a "
                "period-representative ~2050 point estimate, not an "
                "explicit 30-yr averaging window.",
    },
    "sv": {
        "source": "aqueduct_future_annual", "horizon_year": 2050,
        "window": "point_estimate_2050", "is_explicit_30yr_window": False,
        "note": "same Aqueduct product as ws.",
    },
    "iv": {
        "source": "aqueduct_future_annual", "horizon_year": 2050,
        "window": "point_estimate_2050", "is_explicit_30yr_window": False,
        "note": "same Aqueduct product as ws.",
    },
    "heat": {
        "source": "cmip6_tasmax", "horizon_year": 2050,
        "window": "2041-2070", "is_explicit_30yr_window": True,
        "note": "explicit 30-yr CMIP6 window, represented by its "
                "mid-point 2050.",
    },
    "spei": {
        "source": "cmip6_pr_tas_thornthwaite", "horizon_year": 2050,
        "window": "2041-2070", "is_explicit_30yr_window": True,
        "note": "same explicit CMIP6 30-yr window as heat.",
    },
}
assert set(HAZARD_TEMPORAL_WINDOW) == set(HAZARD_TERMS), (
    "HAZARD_TEMPORAL_WINDOW must declare a temporal-window entry for every "
    "hazard term in HAZARD_TERMS -- no term may rely on an implicit window."
)

# Aqueduct scenarios (water side) and the paired CMIP6 scenario (heat side),
# by the SSP identity in config.AQUEDUCT_SCENARIO_FOR_CMIP6.
WATER_SCENARIOS = ("opt", "bau", "pes")
WATER_TO_HEAT = {ws: hs for hs, ws in AQUEDUCT_SCENARIO_FOR_CMIP6.items()}

# Technology buckets this module scores. Applicable-hazard subsets per
# bucket (H_b, Methods Section 3) are Phase 3 -- not decided here; every
# bucket gets every computable hazard term for now.
BUCKETS = ("hydro", "thermal", "wind", "solar")

# Stable per-plant identifier and the merge key it anchors.
PLANT_UID = "plant_uid"
# Raw CSV text tokens hashed into plant_uid -- attributes of the record, never
# its position in the file. Verified unique across all three countries.
_UID_FIELDS = ("plant_name", "lat", "lon")
_UID_DIGEST_BYTES = 6   # 48-bit hash; collision-checked at load time

# --------------------------------------------------------------------------
# Frozen global bounds (unchanged from the retired ccrs_calculator.py --
# per-term, not the retired composite water_sub. spec item G, closed).
#
# Do NOT edit by hand without explicit manual review: the regression test in
# tests/test_risk_calculator.py recomputes and compares, and fails on drift.
# Format: RAW bounds (pre-log1p) (min, max). Tlog applies log1p to both the
# data and the bound.
#   - ws/sv/iv: one pair per term (water rasters are GCM-independent).
#   - heat/spei: one pair per GCM each (MIROC6 ~10-100x GFDL for heat; never
#     in the same pool).
# --------------------------------------------------------------------------
BOUNDS_DATA_SNAPSHOT = "2026-09-04"
FROZEN_BOUNDS: dict[str, object] = {
    "ws": (3.3699998880365456e-07, 29.883182525634766),
    "sv": (0.060949064791202545, 1.6313080787658691),
    "iv": (0.1379709094762802, 2.4342257976531982),
    "heat": {
        "gfdl_esm4": (0.0, 159.89999389648438),
        "miroc6": (0.0, 274.20001220703125),
    },
    "spei": {
        "gfdl_esm4": (1.4441261291503906, 4.022922515869141),
        "miroc6": (1.2722063064575195, 4.160458564758301),
    },
}


class BoundsRegressionError(RuntimeError):
    """The recomputed global bounds diverged from ``FROZEN_BOUNDS``.

    Not to be silenced. If the data on disk changed on purpose (a new country,
    a new scenario, a raster reprocessed), update ``FROZEN_BOUNDS`` and
    ``BOUNDS_DATA_SNAPSHOT`` **deliberately**, with the number diff recorded in
    the commit -- never let the test recompute and accept silently.
    """


# --------------------------------------------------------------------------
# Rasters and sampling
# --------------------------------------------------------------------------
def raster_path(term: str, country: str, water_scenario: str, model: str) -> Path:
    """Path to the processed RAW raster for a term/country/scenario(/GCM).

    ``model`` is only used by ``heat``/``spei``; the water rasters ignore it.
    """
    if term == "ws":
        return ws_raw_path(country, water_scenario)
    if term == "sv":
        return var_raw_path(country, water_scenario, "sv")
    if term == "iv":
        return var_raw_path(country, water_scenario, "iv")
    if term == "heat":
        return heat_raw_path(country, model, WATER_TO_HEAT[water_scenario])
    if term == "spei":
        return spei_raw_path(country, model, WATER_TO_HEAT[water_scenario])
    raise ValueError(
        f"unknown term {term!r} (expected one of {HAZARD_TERMS}; "
        f"{EXCLUDED_INDICATORS} is excluded from GEAR by design)"
    )


def sample_raster(path: Path, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    """Nearest-pixel sample of the raster at each (lon, lat). Points outside
    the grid or on nodata come back as NaN."""
    with rasterio.open(path) as src:
        band = src.read(1).astype("float64")
        nod = src.nodata
        if nod is not None and not np.isnan(nod):
            band[band == nod] = np.nan
        rows, cols = rowcol(src.transform, np.asarray(lons), np.asarray(lats))
        rows, cols = np.asarray(rows), np.asarray(cols)
        h, w = band.shape
        inside = (rows >= 0) & (rows < h) & (cols >= 0) & (cols < w)
        out = np.full(np.shape(lons), np.nan, dtype="float64")
        out[inside] = band[rows[inside], cols[inside]]
    return out


def _derive_plant_uid(iso3: str, name: str, lat_token: str, lon_token: str) -> str:
    """``{ISO3}-blake2s(plant_name | lat | lon)`` over the raw CSV text tokens.

    Deterministic (blake2s, not Python's salted ``hash``), so the same record
    yields the same uid on every run, in any row order.
    """
    payload = "\x1f".join((name, lat_token, lon_token)).encode("utf-8")
    return f"{iso3}-{hashlib.blake2s(payload, digest_size=_UID_DIGEST_BYTES).hexdigest()}"


def load_plants(country: str) -> pd.DataFrame:
    """Validated plants for the country: ``plant_uid``, ``plant_name``,
    ``lon``/``lat``, ``capacity_mw``, ``commissioning_year``, ``bucket``
    (from ``fuel_type_bucket``), and the fuel identity columns ``fuel_type`` /
    ``mixed_fuel_type`` / ``fuel_types_found`` (needed by
    ``src/index/age_factor.py`` to pick the per-fuel age curve inside the
    ``thermal`` bucket). Every plant has a coordinate (V6).

    ``plant_uid`` -- there is **no native GEM identifier** in
    ``gem_validated_plants_{country}.csv``; it is a deterministic content
    hash of ``(plant_name, lat, lon)`` text tokens. See
    ``docs/memory/05-decisoes-tecnicas.md`` item 12 for the full rationale
    (unchanged from the retired ``ccrs_calculator.py``).
    """
    path = ASSETS_PROCESSED / f"gem_validated_plants_{country}.csv"
    # lat/lon/name read as raw text so the hash is byte-stable; numeric copies
    # of lat/lon are re-parsed below for raster sampling.
    df = pd.read_csv(path, dtype={f: "string" for f in _UID_FIELDS})
    iso3 = COUNTRY_ISO3[country]

    tokens = df[list(_UID_FIELDS)].fillna("")
    uid = [
        _derive_plant_uid(iso3, name, lat, lon)
        for name, lat, lon in zip(tokens["plant_name"], tokens["lat"], tokens["lon"])
    ]
    if len(set(uid)) != len(uid):
        raise ValueError(
            f"plant_uid hash collision in {path.name}: two records hash to the "
            f"same id. Increase _UID_DIGEST_BYTES or add a field to _UID_FIELDS."
        )

    return pd.DataFrame({
        PLANT_UID: uid,
        "country": country,
        "plant_name": df["plant_name"].astype("string"),
        "lon": pd.to_numeric(df["lon"], errors="coerce").astype("float64"),
        "lat": pd.to_numeric(df["lat"], errors="coerce").astype("float64"),
        "capacity_mw": pd.to_numeric(df["capacity_mw"], errors="coerce"),
        "commissioning_year": pd.to_numeric(df["commissioning_year"], errors="coerce"),
        "bucket": df["fuel_type_bucket"].astype("string"),
        "fuel_type": df["fuel_type"].astype("string"),
        "mixed_fuel_type": df["mixed_fuel_type"].fillna(False).astype(bool),
        "fuel_types_found": df["fuel_types_found"].astype("string"),
    })


def sample_terms(model: str) -> pd.DataFrame:
    """One row per (plant, water scenario) with every hazard term's RAW value
    sampled for ``model`` on the heat/drought side. Carries ``plant_uid``."""
    parts = []
    for country in COUNTRIES:
        plants = load_plants(country)
        lons = plants["lon"].to_numpy("float64")
        lats = plants["lat"].to_numpy("float64")
        for water_scen in WATER_SCENARIOS:
            part = plants.copy()
            part["water_scenario"] = water_scen
            part["heat_scenario"] = WATER_TO_HEAT[water_scen]
            for term in HAZARD_TERMS:
                part[term] = sample_raster(
                    raster_path(term, country, water_scen, model), lons, lats
                )
            parts.append(part)
    return pd.concat(parts, ignore_index=True)


# --------------------------------------------------------------------------
# Transforms and bounds
# --------------------------------------------------------------------------
def transform_term(term: str, raw: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """``Tlog`` for ws/heat/spei, ``Tlin`` for sv/iv -- this IS ``Hazard_{i,h}``
    for the term: a per-hazard [0, 1] normalization, never combined with any
    other term's transformed value. ``lo``/``hi`` are RAW bounds; for
    ``Tlog`` the log1p is applied to both data and bound before the Min-Max.
    Degenerate domain (``hi <= lo``) -> zeros."""
    raw = np.asarray(raw, "float64")
    if term in LOG_TERMS:
        x, a, b = np.log1p(raw), np.log1p(lo), np.log1p(hi)
    elif term in LIN_TERMS:
        x, a, b = raw, float(lo), float(hi)
    else:
        raise ValueError(f"unknown term {term!r}")
    if b <= a:
        return np.zeros_like(x)
    return np.clip((x - a) / (b - a), 0.0, 1.0)


def compute_global_bounds(models: list[str] | None = None) -> dict[str, object]:
    """Recompute the global bounds from the rasters on disk.

    Over the rows with a known technology bucket, countries and scenarios
    pooled -- identical procedure to the retired ``ccrs_calculator.py``'s
    per-term bounds (Phase 1 does not touch normalization methodology, only
    how the transformed terms are combined downstream).
    """
    models = models or configured_models()
    frames = {m: sample_terms(m) for m in models}
    frames = {m: f[f["bucket"].isin(BUCKETS)] for m, f in frames.items()}

    def _minmax(frame: pd.DataFrame, term: str) -> tuple[float, float]:
        col = frame.loc[frame[term].notna(), term].to_numpy("float64")
        return float(col.min()), float(col.max())

    water = frames[models[0]]
    out: dict[str, object] = {t: _minmax(water, t) for t in FLAT_BOUND_TERMS}
    for t in GCM_DEPENDENT_TERMS:
        out[t] = {m: _minmax(f, t) for m, f in frames.items()}
    return out


def _bounds_close(a: dict[str, object], b: dict[str, object], atol: float = 1e-4) -> bool:
    if set(a) != set(b):
        return False
    for term in FLAT_BOUND_TERMS:
        if not np.allclose(a[term], b[term], atol=atol, rtol=0):
            return False
    for term in GCM_DEPENDENT_TERMS:
        by_gcm_a, by_gcm_b = a[term], b[term]
        if set(by_gcm_a) != set(by_gcm_b):
            return False
        if not all(
            np.allclose(by_gcm_a[m], by_gcm_b[m], atol=atol, rtol=0) for m in by_gcm_a
        ):
            return False
    return True


def assert_frozen_bounds_current(models: list[str] | None = None) -> dict[str, object]:
    """Recompute and compare against ``FROZEN_BOUNDS``; raise
    ``BoundsRegressionError`` on drift. Returns the recomputed bounds."""
    live = compute_global_bounds(models)
    if not _bounds_close(live, FROZEN_BOUNDS):
        raise BoundsRegressionError(
            "recomputed bounds diverge from FROZEN_BOUNDS "
            f"(snapshot {BOUNDS_DATA_SNAPSHOT}).\n  frozen:     {FROZEN_BOUNDS}\n"
            f"  recomputed: {live}\n"
            "Manual review required before updating the constant."
        )
    return live


def _term_bounds(term: str, model: str, bounds: dict[str, object]) -> tuple[float, float]:
    if term in GCM_DEPENDENT_TERMS:
        return tuple(bounds[term][model])  # type: ignore[index]
    return tuple(bounds[term])  # type: ignore[return-value]


# --------------------------------------------------------------------------
# Exposure (Methods Section 1) -- two forms, only one is a Risk input.
# --------------------------------------------------------------------------
class ExposureLog10Display(np.ndarray):
    """Marker type for ``log10(capacity_mw + 1)``, the VISUALIZATION-ONLY
    Exposure display transform (Intrinsic Asset Risk, Methods Section 1).

    A distinct ``np.ndarray`` subclass so that ``risk_i_h`` can reject it at
    the type level -- see ``exposure_log10_display`` and ``risk_i_h``.
    """


def exposure_capacity_mw(capacity_mw) -> np.ndarray:
    """Systemic Capacity at Risk -- raw installed capacity in MW. The only
    Exposure form ``risk_i_h`` accepts."""
    return np.asarray(capacity_mw, dtype="float64")


def exposure_log10_display(capacity_mw) -> ExposureLog10Display:
    """Intrinsic Asset Risk -- ``log10(MW + 1)``. A map/legend DISPLAY
    transform only (Methods Section 1): keeps a handful of very large plants
    from visually dominating a map and masking physically severe risk at
    smaller assets. Never a second metric, never an input to any
    comparability, ranking or scoring calculation -- ``risk_i_h`` raises
    ``TypeError`` if handed this array instead of raw MW. Tier 3,
    author-declared log base/offset, no literature precedent."""
    arr = np.log10(np.asarray(capacity_mw, dtype="float64") + 1.0)
    return arr.view(ExposureLog10Display)


# --------------------------------------------------------------------------
# Equation 1 -- Risk_i,h = Hazard_i,h * Exposure_i * Vulnerability_i
# --------------------------------------------------------------------------
def risk_i_h(
    hazard_i_h: np.ndarray,
    exposure_mw: np.ndarray,
    vulnerability: np.ndarray,
) -> np.ndarray:
    """Equation 1 (Methods Section 1): ``Risk_{i,h} = Hazard_{i,h} *
    Exposure_i * Vulnerability_i``, for one hazard ``h`` at a time. Never
    combined or summed with another hazard's ``Risk_{i,h}`` -- that
    combination does not exist anywhere in this module or its callers
    (Section 9 comparability rule).

    ``exposure_mw`` must be raw MW (``exposure_capacity_mw`` output), never
    the ``log10(MW+1)`` display transform (``exposure_log10_display``
    output) -- enforced at the type level, not just by convention.
    """
    if isinstance(exposure_mw, ExposureLog10Display):
        raise TypeError(
            "risk_i_h() received an ExposureLog10Display array (the "
            "log10(MW+1) VISUALIZATION-ONLY transform) where raw MW "
            "(Systemic Capacity at Risk, exposure_capacity_mw) is required. "
            "This transform must never enter a scoring/ranking calculation "
            "-- Methods Section 1."
        )
    hazard_i_h = np.asarray(hazard_i_h, "float64")
    exposure_mw = np.asarray(exposure_mw, "float64")
    vulnerability = np.asarray(vulnerability, "float64")
    return hazard_i_h * exposure_mw * vulnerability


def compute_risk_by_hazard(
    model: str,
    bounds: dict[str, object] | None = None,
    age_factors: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """``Risk_{i,h}`` for every computable hazard term, one row per (plant,
    water scenario, hazard term), for one GCM.

    Long format on purpose: a ``hazard_term`` column, not one column per
    hazard, so that summing or plotting across hazards requires an explicit,
    visible groupby/filter decision rather than an accidental row-wise sum
    across columns.

    Columns: identity (``plant_uid``, ``country``, ``plant_name``, ``lat``,
    ``lon``, ``bucket``), ``capacity_mw``, ``commissioning_year``,
    ``water_scenario``, ``heat_scenario``, ``model``, ``hazard_term``,
    ``hazard_i_h`` (Equation 1's Hazard term, [0, 1]), ``exposure_mw``,
    ``age_factor`` (Vulnerability), ``risk_i_h`` (Equation 1's output).
    """
    from src.index import age_factor  # local import: age_factor imports this
    # module for load_plants/PLANT_UID, so a module-level import here would
    # be circular.

    bounds = bounds or FROZEN_BOUNDS
    df = sample_terms(model)
    df = df[df["bucket"].isin(BUCKETS)].reset_index(drop=True)

    af = age_factors if age_factors is not None else age_factor.compute_age_factors()
    af_small = af[[PLANT_UID, "age_factor"]]
    merged = df.merge(af_small, on=PLANT_UID, how="left", validate="many_to_one")
    missing = int(merged["age_factor"].isna().sum())
    if missing:
        raise ValueError(
            f"{missing} rows have no age_factor after the join to load_plants "
            f"-- the age_factor table is stale relative to the current "
            f"gem_validated_plants_*.csv. Regenerate it first."
        )

    exposure_mw = exposure_capacity_mw(merged["capacity_mw"].to_numpy("float64"))

    parts = []
    for term in HAZARD_TERMS:
        lo, hi = _term_bounds(term, model, bounds)
        h_i_h = transform_term(term, merged[term].to_numpy("float64"), lo, hi)
        vulnerability = merged["age_factor"].to_numpy("float64")
        risk = risk_i_h(h_i_h, exposure_mw, vulnerability)

        part = merged[[PLANT_UID, "country", "plant_name", "lat", "lon",
                        "water_scenario", "heat_scenario", "bucket",
                        "capacity_mw", "commissioning_year"]].copy()
        part["model"] = model
        part["hazard_term"] = term
        part["hazard_i_h"] = h_i_h
        part["exposure_mw"] = exposure_mw
        part["age_factor"] = vulnerability
        part["risk_i_h"] = risk
        parts.append(part)

    out = pd.concat(parts, ignore_index=True)
    key = [PLANT_UID, "water_scenario", "hazard_term"]
    dup = int(out.duplicated(key).sum())
    if dup:
        raise RuntimeError(
            f"compute_risk_by_hazard produced {dup} duplicate {key} rows."
        )
    return out


def compute_risk(models: list[str] | None = None, bounds: dict[str, object] | None = None,
                  age_factors: pd.DataFrame | None = None) -> pd.DataFrame:
    """``Risk_{i,h}`` stacked across every configured GCM (long format, a
    ``model`` column) -- GFDL-ESM4 and MIROC6 rows sit side by side, never
    averaged or blended (``ARCHITECTURE.md`` Section 5.4's GCM rule, carried
    over unchanged)."""
    from src.index import age_factor  # local import: see compute_risk_by_hazard

    models = models or configured_models()
    af = age_factors if age_factors is not None else age_factor.compute_age_factors()
    return pd.concat(
        [compute_risk_by_hazard(m, bounds=bounds, age_factors=af) for m in models],
        ignore_index=True,
    )


# --------------------------------------------------------------------------
# Computable base (V6) -- for any future capacity roll-up
# --------------------------------------------------------------------------
def computable_base(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to the V6 computable base: valid coordinate (every plant has
    one) + ``commissioning_year`` present. Any capacity sum starts here,
    never from ``capacity_mw`` over the whole fleet."""
    return df[df["commissioning_year"].notna()]


def capacity_sum(df: pd.DataFrame) -> float:
    """Sum ``capacity_mw`` over ``df`` -- only valid if ``df`` is already
    limited to the V6 computable base (every row has a ``commissioning_year``).
    Fails loud (``AssertionError``) if a row without ``commissioning_year``
    reaches here -- callers must pass ``computable_base(df)`` in first."""
    assert df["commissioning_year"].notna().all(), (
        "capacity_sum: received rows with a missing commissioning_year -- "
        "capacity must be summed over computable_base(df), never over the "
        "raw fleet or capacity_mw directly."
    )
    return float(df["capacity_mw"].sum())


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-bounds", action="store_true",
        help="recompute the global bounds and compare against FROZEN_BOUNDS; writes nothing",
    )
    parser.add_argument("--out", type=Path, default=OUTPUT_TABLES / "risk_by_hazard.csv")
    args = parser.parse_args()

    if args.check_bounds:
        try:
            live = assert_frozen_bounds_current()
        except BoundsRegressionError as exc:
            logger.error(str(exc))
            return 1
        logger.info("frozen bounds match the data (%s): %s", BOUNDS_DATA_SNAPSHOT, live)
        return 0

    long_df = compute_risk()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    long_df.to_csv(args.out, index=False)
    logger.info("wrote %s (%d plant x scenario x hazard_term rows)", args.out, len(long_df))

    for term in HAZARD_TERMS:
        s = long_df.loc[long_df["hazard_term"] == term, "risk_i_h"].dropna()
        logger.info("risk_i_h[%s] (%s): n=%d, p50=%.4f, p95=%.4f, max=%.4f",
                    term, HAZARD_LABELS[term], len(s), s.median(), s.quantile(0.95), s.max())
    base = computable_base(long_df)
    logger.info("computable base (commissioning_year present): %d / %d rows",
                len(base), len(long_df))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
