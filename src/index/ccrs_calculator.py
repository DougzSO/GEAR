"""
CCRS -- the ``Hazard_{i,s}`` term, per plant, scenario and GCM.

This module computes **only** the hazard term of the Climate Change Risk Score
(``docs/ARCHITECTURE.md`` Section 5.1, ``analysis/climate_risk_score_spec.md``
Section 2):

    Hazard_{i,s} = w_water[bucket] * water_sub_{i,s}
                 + w_heat[bucket]  * Tlog(heat_{i,s})
                 + w_drought[bucket] * Tlog(spei_freq_{i,s})

    water_sub_{i,s} = 0.4164 * Tlog(ws) + 0.2505 * Tlin(sv) + 0.3331 * Tlin(iv)

The full score ``CCRS_{i,s} = Hazard_{i,s} * age_factor_i * EventMultiplier_c``
is **not** assembled here: the ``age_factor`` multiplier mapping and its sign
convention are the spec's open item D (``ARCHITECTURE.md`` Section 10) -- see
``src/index/age_factor.py`` and ``docs/DECISIONS.md`` (2026-09-04).
``EventMultiplier_c`` has a closed form
(Section 7.2) but is also applied in the assembly step, outside this module.
The risk bands (WaterRiskBand / HeatRiskBand) are yet another step.

--------------------------------------------------------------------------
Drought (SPEI) term -- spec item F, CLOSED
--------------------------------------------------------------------------
``spei_freq`` is ``src/processors/spei_processor.py``'s raw drought-frequency
raster (months/year with SPEI-12 <= -1.0, Thornthwaite PET). It enters
``Hazard`` as a **new, independent third term**, not a complement folded into
``water_sub``: the existing ``water_sub`` weights (0.4164 / 0.2505 / 0.3331,
WRI Aqueduct category widths) are a closed, derived quantity (see
``WITHIN_WATER_WEIGHTS`` below) -- renormalising them to make room for SPEI
would replace a derived value with an arbitrary one for no documented reason.
Adding a third additive term at the bucket level, transformed and bounded the
same way as ``heat`` (``Tlog`` = ``MinMax(log1p(x))``, per-GCM bounds -- SPEI
depends on the GCM, like heat and unlike the Aqueduct water terms), preserves
``water_sub`` bit-for-bit while still letting drought exposure enter the
score. See ``docs/DECISIONS.md`` for the full record of this choice.

**This changes ``Hazard_{i,s}`` and therefore ``CCRS_{i,s}`` for every plant**
relative to every T1-T6 number computed before this integration: the bucket
weights below are new (a 3-way split replacing the 2-way ``w_water``/``w_heat``
matrix) and ``FROZEN_BOUNDS`` gained a new ``spei`` entry. Hazard/CCRS values
from before and after this change are **not directly comparable** -- see
``docs/DECISIONS.md`` "[2026-09-04] SPEI drought term added to Hazard".

--------------------------------------------------------------------------
The five hazard terms, and what they are NOT
--------------------------------------------------------------------------
``ws``, ``sv`` and ``iv`` are the **three WRI Aqueduct 4.0 water-risk
indicators**, not precipitation and not SPEI:

* ``ws``  -- water stress: withdrawal-to-availability ratio (Aqueduct column
  ``{scenario}50_ws_x_r``), rasterised by
  ``src/processors/water_stress_processor.py`` (the WRI 9999 sentinel is
  already substituted by the real ``country_max`` in the
  ``water_stress_raw_*`` raster).
* ``sv``  -- seasonal variability: within-year coefficient of variation of
  blue-water supply (Aqueduct column ``{scenario}50_sv_x_r``), rasterised by
  ``src/processors/water_variability_processor.py``
  (``seasonal_variability_raw_*`` raster).
* ``iv``  -- interannual variability: between-year coefficient of variation of
  the same supply (Aqueduct column ``{scenario}50_iv_x_r``), same processor
  (``interannual_variability_raw_*`` raster).

There is no precipitation/SPEI term in the current CCRS: a drought (SPEI) term
is the spec's open item F -- the ``pr``/``tas`` downloads already exist
(``cds_precipitation_downloader``) but no ``spei_processor`` has been written,
and ``sv``/``iv`` do **not** stand in for it (they measure variability of
supply, not a climatic water deficit).

* ``heat`` -- mean days/year with tasmax > 40 C (``extreme_heat_days_*``, a
  passthrough of ``cds_tasmax_downloader``), per GCM.
* ``spei`` -- ``spei_freq``, mean months/year with SPEI-12 <= -1.0
  (``drought_stress_raw_*``, computed by ``src/processors/spei_processor.py``
  from the raw ``pr``/``tas`` daily series), per GCM.

``wd`` (water depletion) is **excluded** from the calculation: the plant-level
Spearman ``ws x wd`` is 0.98-0.998 across the three countries
(``analysis/aqueduct_indicator_correlation.md``), so ``wd`` carries no rank
information independent of ``ws``. Keeping both would double-count the
water-stress level channel. ``ws`` is kept (the WRI headline indicator, already
in the pipeline); ``wd`` is dropped.

--------------------------------------------------------------------------
Transforms and bounds
--------------------------------------------------------------------------
* ``Tlog(x) = MinMax(log1p(x))`` -- applied to ``ws``, ``heat`` and ``spei``
  (severe right skew at plant level).
* ``Tlin(x) = MinMax(x)``        -- applied to ``sv`` and ``iv`` (near
  symmetric; log1p would over-correct and could invert their ordering).
* **Global bounds**: one ``(min, max)`` pair per term, pooling the 3 countries
  x 3 scenarios (never per-country, never per-scenario). This is the property
  that makes a CCRS of 0.4 mean the same exposure in Lisbon and in Chennai.
  - ``ws``/``sv``/``iv``: the water rasters do not depend on the GCM, so there
    is a single pair per term, pooling the plants that intersect a basin.
  - ``heat``/``spei``: one pair **per GCM** each. MIROC6 magnitudes run
    ~10-100x GFDL-ESM4 for heat; pooling both into one bound would be a
    cross-model blend. See "GCM" below, and ``docs/DECISIONS.md``
    "[2026-09-04] CCRS global Min-Max bounds" and
    "[2026-09-04] SPEI drought term added to Hazard" (the ``spei`` bound is a
    later, authorised *extension* of the same frozen constant, not a
    perturbation of the pre-existing ``ws``/``sv``/``iv``/``heat`` values,
    which are untouched).
* The bounds are **frozen** in ``FROZEN_BOUNDS`` (spec open item G: "a fixed,
  documented constant, not recomputed per run"). ``main`` and the default
  calculation use the frozen values; ``compute_global_bounds`` recomputes them
  from the data on disk. ``tests/test_ccrs_calculator.py`` compares the two
  and **fails** on drift -- updating ``FROZEN_BOUNDS`` requires explicit
  manual review.

--------------------------------------------------------------------------
Per technology-bucket weights (``ARCHITECTURE.md`` Section 5.3, closed;
3-way matrix since the SPEI integration -- spec item F)
--------------------------------------------------------------------------
    bucket    w_water  w_heat  w_drought
    hydro      0.55     0.00    0.45
    thermal    0.525    0.175   0.30
    wind       0.00     0.95    0.05
    solar      0.00     0.95    0.05

Each row sums to 1.0. This replaces the earlier 2-column ``w_water``/``w_heat``
matrix (``hydro`` 1.00/0.00, ``thermal`` 0.75/0.25, ``wind``/``solar``
0.00/1.00): every existing weight was rescaled to make room for
``w_drought``, not just the new column added on top -- see ``docs/DECISIONS.md``.

**Origin of these numbers -- explicit, same transparency standard as
``age_factor.py``'s assumed coal-overhaul cycle**: this is a direct
translation of a qualitative judgment (hydro and thermal plants that depend
on cooling/reservoir water are materially more exposed to prolonged drought
than to a single hot day; wind/solar have no physical water-dependence
mechanism but are not given an *absolute* zero, since a drought-driven
regional water/energy-system stress is not literally impossible for them
either). It is **not** a formal calibration (no AHP/pairwise comparison) and
**not** a literature-derived value -- there is no published water/heat/drought
importance ratio for any of these technologies. Revisit if a calibrated
alternative becomes available.

For ``wind``/``solar`` the whole water side -- ``ws``, ``sv`` AND ``iv`` --
zeroes together; the drought side is not zero. The within-water weights
``(0.4164, 0.2505, 0.3331)`` come from the WRI Aqueduct 4.0 category step
widths (``w_k proportional to 1/tau_k``, spec Section 8.1), not from the
Section 6.1 magnitude matrix, and are **unchanged** by the SPEI integration
(``water_sub`` is a closed sub-formula, never renormalised -- see "Drought
(SPEI) term" above).

--------------------------------------------------------------------------
GCM (``ARCHITECTURE.md`` Section 5.4)
--------------------------------------------------------------------------
GFDL-ESM4 is the primary value for every cited CCRS figure. MIROC6 is a
sensitivity panel, kept in a separate field/column -- **never** averaged or
50/50-blended with GFDL-ESM4. ``compute_hazard_by_gcm`` returns one
``hazard_{model}`` column per GCM side by side, never combined.

--------------------------------------------------------------------------
Plant identity
--------------------------------------------------------------------------
``(country, plant_name)`` is **not** unique: 429 name groups hold several
distinct GEM records (different coordinates, same name; 265 of them also share
``capacity_mw`` + ``commissioning_year``). ``load_plants`` therefore assigns a
stable ``plant_uid`` -- a deterministic content hash of the record's
``(plant_name, lat, lon)`` CSV text tokens, **not** a positional index (see
``load_plants`` for why there is no native GEM id and why the hash is on
content, not row position). It is carried through every frame and used as the
merge key in ``compute_hazard_by_gcm`` -- without it the per-GCM merge
cross-joins the ambiguous rows and inflates the output. See
``docs/DECISIONS.md`` and the regression tests
``test_compute_hazard_by_gcm_has_no_cross_join_duplication`` and
``test_plant_uid_is_stable_*``.

--------------------------------------------------------------------------
Capacity
--------------------------------------------------------------------------
Capacity enters neither ``Hazard_{i,s}`` nor ``CCRS_{i,s}`` -- only the
per-country roll-up (``ARCHITECTURE.md`` Section 5.5). This module does not
aggregate capacity; ``computable_base`` is here only so any future roll-up
uses the V6 computable base (valid coordinate + ``commissioning_year``), never
``capacity_mw`` directly.

Standalone: ``python -m src.index.ccrs_calculator`` from the project root.
Reads the processed raw rasters and ``gem_validated_plants_{country}.csv``;
writes ``data/outputs/tables/ccrs_hazard.csv``.
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
HAZARD_TERMS = ("ws", "heat", "sv", "iv", "spei")
LOG_TERMS = frozenset({"ws", "heat", "spei"})   # log1p -> Min-Max
LIN_TERMS = frozenset({"sv", "iv"})             # linear Min-Max
# Terms whose global bound is per-GCM (magnitudes are not model-comparable);
# every other term's bound is a single flat pair pooling all GCMs.
GCM_DEPENDENT_TERMS = frozenset({"heat", "spei"})
FLAT_BOUND_TERMS = tuple(t for t in HAZARD_TERMS if t not in GCM_DEPENDENT_TERMS)

# ``wd`` (water depletion) is left out: rank-redundant with ``ws``
# (Spearman 0.98-0.998, analysis/aqueduct_indicator_correlation.md).
EXCLUDED_INDICATORS = ("wd",)

# Aqueduct scenarios (water side) and the paired CMIP6 scenario (heat side),
# by the SSP identity in config.AQUEDUCT_SCENARIO_FOR_CMIP6.
WATER_SCENARIOS = ("opt", "bau", "pes")
WATER_TO_HEAT = {ws: hs for hs, ws in AQUEDUCT_SCENARIO_FOR_CMIP6.items()}

# Stable per-plant identifier and the merge key it anchors.
PLANT_UID = "plant_uid"
GCM_MERGE_KEY = [PLANT_UID, "water_scenario", "heat_scenario"]
# Raw CSV text tokens hashed into plant_uid -- attributes of the record, never
# its position in the file. Verified unique across all three countries.
_UID_FIELDS = ("plant_name", "lat", "lon")
_UID_DIGEST_BYTES = 6   # 48-bit hash; collision-checked at load time
# Descriptive columns carried once (from the first model's frame) into the
# per-GCM wide table.
_META_COLUMNS = [
    "country", "plant_name", "lat", "lon", "bucket",
    "capacity_mw", "commissioning_year",
]

# --------------------------------------------------------------------------
# water_sub within-water weights -- WRI Aqueduct 4.0 category widths
# (spec Section 8.1). w_k proportional to 1/tau_k, tau_k = the indicator's
# High -> Extremely-High threshold.
# --------------------------------------------------------------------------
WRI_TOP_THRESHOLD = {"ws": 0.80, "sv": 1.33, "iv": 1.00}


def _derive_within_water_weights() -> dict[str, float]:
    inv = {k: 1.0 / WRI_TOP_THRESHOLD[k] for k in ("ws", "sv", "iv")}
    total = sum(inv.values())
    return {k: inv[k] / total for k in ("ws", "sv", "iv")}


WITHIN_WATER_WEIGHTS = _derive_within_water_weights()

# Values published in spec Section 8.1 / ARCHITECTURE.md Section 5.1. The
# derivation above must reproduce them -- a guard against an accidental edit
# of WRI_TOP_THRESHOLD.
_PUBLISHED_WITHIN_WATER = {"ws": 0.4164, "sv": 0.2505, "iv": 0.3331}
assert all(
    abs(WITHIN_WATER_WEIGHTS[k] - _PUBLISHED_WITHIN_WATER[k]) < 5e-5
    for k in _PUBLISHED_WITHIN_WATER
), f"within-water weights {WITHIN_WATER_WEIGHTS} diverge from spec Section 8.1"

# --------------------------------------------------------------------------
# Per technology-bucket water/heat weights (ARCHITECTURE.md Section 5.3, closed).
# --------------------------------------------------------------------------
BUCKETS = ("hydro", "thermal", "wind", "solar")
# 3-way water/heat/drought split (spec item F, closed). A qualitative
# translation, not a formal calibration -- see the module docstring section
# "Per technology-bucket weights" for the origin and reasoning.
BUCKET_WEIGHTS = {
    "hydro":   {"water": 0.55,  "heat": 0.00,  "drought": 0.45},
    "thermal": {"water": 0.525, "heat": 0.175, "drought": 0.30},
    "wind":    {"water": 0.00,  "heat": 0.95,  "drought": 0.05},
    "solar":   {"water": 0.00,  "heat": 0.95,  "drought": 0.05},
}
assert all(
    abs(w["water"] + w["heat"] + w["drought"] - 1.0) < 1e-12
    for w in BUCKET_WEIGHTS.values()
), "w_water + w_heat + w_drought must sum to 1 per bucket"

# --------------------------------------------------------------------------
# Frozen global bounds (spec open item G).
#
# Derived from compute_global_bounds() over the data on disk at the snapshot
# below. Do NOT edit by hand without explicit manual review: the regression
# test in tests/test_ccrs_calculator.py recomputes and compares, and fails on
# drift. Format: RAW bounds (pre-log1p) (min, max). Tlog applies log1p to both
# the data and the bound.
#   - ws/sv/iv: one pair per term (water rasters are GCM-independent).
#   - heat/spei: one pair per GCM each (MIROC6 ~10-100x GFDL for heat; never
#     in the same pool).
#
# ``spei`` was added on the SAME snapshot date as an AUTHORISED EXTENSION
# (docs/DECISIONS.md "[2026-09-04] SPEI drought term added to Hazard"): the
# ws/sv/iv/heat values below are untouched (recomputed and confirmed
# byte-identical to the pre-SPEI snapshot before this edit), so this is not a
# redefinition of any existing bound -- only a new key added to the same
# frozen constant. It nonetheless means any Hazard/CCRS number computed after
# this point uses a materially different formula (new bucket weights, new
# additive term) and is not directly comparable to a pre-integration number.
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

    ``model`` is only used by ``heat``; the water rasters ignore it.
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
        f"{EXCLUDED_INDICATORS} is excluded from the CCRS by design)"
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
    ``gem_validated_plants_{country}.csv``. GEM's own unit and location IDs
    (``GEM unit/phase ID``, ``GEM location ID``) live only in
    ``gem_units_detail.csv`` at generating-unit grain and are **not** carried
    through the unit -> plant aggregation in
    ``src/downloaders/assets_validator.py`` (which keys plants on
    country + normalised name + coordinate rounded to ~100 m). ``plant_uid``
    is therefore a **deterministic content hash**:
    ``{ISO3}-blake2s(plant_name | lat | lon)`` computed over the raw CSV
    **text tokens** of those three fields -- attributes of the record, never
    its position or order in the file.

    * Stable across row reordering, row filtering / removal, and re-export, as
      long as the plant's name and coordinate strings are byte-identical.
    * A genuine edit to a plant's name or coordinates produces a **new** uid --
      correct, since it is then a different record.
    * ``(plant_name, lat, lon)`` is verified unique in all three countries'
      current snapshots; this function raises if the hash ever collides.
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
    """One row per (plant, water scenario) with the four RAW term values
    sampled for ``model`` on the heat side. Carries ``plant_uid``."""
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
    """``Tlog`` for ws/heat, ``Tlin`` for sv/iv. ``lo``/``hi`` are RAW bounds;
    for ``Tlog`` the log1p is applied to both data and bound before the
    Min-Max. Degenerate domain (``hi <= lo``) -> zeros."""
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
    pooled:

    * ``ws``/``sv``/``iv`` (``FLAT_BOUND_TERMS``): one ``(min, max)`` pair per
      term, over the plants whose term is finite (they intersect a basin).
      The water rasters are GCM-independent -- sampling with any configured
      GCM gives the same result; ``models[0]`` is used for convenience.
    * ``heat``/``spei`` (``GCM_DEPENDENT_TERMS``): one pair per GCM, over the
      plants whose value is finite for that GCM.

    Same structure as ``FROZEN_BOUNDS``.
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
# Hazard
# --------------------------------------------------------------------------
def water_sub(t_ws: np.ndarray, t_sv: np.ndarray, t_iv: np.ndarray) -> np.ndarray:
    """``0.4164 * Tlog(ws) + 0.2505 * Tlin(sv) + 0.3331 * Tlin(iv)`` -- over the
    already-transformed terms. NaN if any term is NaN."""
    w = WITHIN_WATER_WEIGHTS
    return w["ws"] * np.asarray(t_ws) + w["sv"] * np.asarray(t_sv) + w["iv"] * np.asarray(t_iv)


def hazard(
    bucket: np.ndarray,
    water_sub_val: np.ndarray,
    t_heat: np.ndarray,
    t_spei: np.ndarray,
) -> np.ndarray:
    """``w_water[bucket] * water_sub + w_heat[bucket] * Tlog(heat)
    + w_drought[bucket] * Tlog(spei_freq)``.

    A side with weight 0 is dropped before the multiplication, so a NaN
    ``water_sub`` does not contaminate ``wind``/``solar`` (nor a NaN ``heat``
    or ``spei`` contaminate ``hydro``, whose ``w_heat`` is 0). Where a side
    has weight > 0, a NaN propagates -- the plant has no hazard in that
    scenario, which is the correct behaviour.
    """
    bucket = np.asarray(bucket, dtype=object)
    w_water = np.array([BUCKET_WEIGHTS[b]["water"] if b in BUCKET_WEIGHTS else np.nan
                        for b in bucket], dtype="float64")
    w_heat = np.array([BUCKET_WEIGHTS[b]["heat"] if b in BUCKET_WEIGHTS else np.nan
                       for b in bucket], dtype="float64")
    w_drought = np.array([BUCKET_WEIGHTS[b]["drought"] if b in BUCKET_WEIGHTS else np.nan
                          for b in bucket], dtype="float64")
    water_sub_val = np.asarray(water_sub_val, "float64")
    t_heat = np.asarray(t_heat, "float64")
    t_spei = np.asarray(t_spei, "float64")

    # Multiply only where the weight is > 0: the zeroed side never touches a
    # NaN, and the weighted side propagates NaN normally.
    water_part = np.zeros(len(w_water), dtype="float64")
    heat_part = np.zeros(len(w_heat), dtype="float64")
    drought_part = np.zeros(len(w_drought), dtype="float64")
    mw = w_water > 0.0
    mh = w_heat > 0.0
    md = w_drought > 0.0
    water_part[mw] = w_water[mw] * water_sub_val[mw]
    heat_part[mh] = w_heat[mh] * t_heat[mh]
    drought_part[md] = w_drought[md] * t_spei[md]
    out = water_part + heat_part + drought_part
    # unknown bucket -> NaN (should not happen: the caller filters first)
    out[np.isnan(w_water) | np.isnan(w_heat) | np.isnan(w_drought)] = np.nan
    return out


def compute_hazard(model: str, bounds: dict[str, object] | None = None) -> pd.DataFrame:
    """``Hazard_{i,s}`` per plant x scenario for one GCM.

    One row per (plant, scenario) with a known bucket -- keyed by
    ``plant_uid``. Columns: identity + ``lat``/``lon``, ``bucket``,
    ``capacity_mw``, ``commissioning_year``, the five transformed terms
    ``T_*``, ``water_sub``, ``hazard``, ``model``. Uses ``FROZEN_BOUNDS`` by
    default.
    """
    bounds = bounds or FROZEN_BOUNDS
    df = sample_terms(model)
    df = df[df["bucket"].isin(BUCKETS)].reset_index(drop=True)

    tt = {}
    for term in HAZARD_TERMS:
        lo, hi = _term_bounds(term, model, bounds)
        tt[term] = transform_term(term, df[term].to_numpy("float64"), lo, hi)

    ws_sub = water_sub(tt["ws"], tt["sv"], tt["iv"])
    haz = hazard(df["bucket"].to_numpy(), ws_sub, tt["heat"], tt["spei"])

    out = df[[PLANT_UID, "country", "plant_name", "lat", "lon",
              "water_scenario", "heat_scenario", "bucket",
              "capacity_mw", "commissioning_year"]].copy()
    for term in HAZARD_TERMS:
        out[f"T_{term}"] = tt[term]
    out["water_sub"] = ws_sub
    out["hazard"] = haz
    out["model"] = model
    return out


def compute_hazard_by_gcm(
    models: list[str] | None = None, bounds: dict[str, object] | None = None
) -> pd.DataFrame:
    """Each GCM's ``Hazard`` side by side -- one ``hazard_{model}`` column per
    GCM, **never** combined. GFDL-ESM4 is the primary column; MIROC6 is a
    sensitivity panel (``ARCHITECTURE.md`` Section 5.4).

    The merge is on ``plant_uid`` + scenario (``GCM_MERGE_KEY``), so each
    individual GEM record stays distinct and no row is duplicated by a
    cross-join (see the module docstring, "Plant identity"). Every model
    yields the same key set, so the descriptive columns are taken once from
    the first model's frame.
    """
    models = models or configured_models()
    merged: pd.DataFrame | None = None
    for m in models:
        h = compute_hazard(m, bounds=bounds)
        col = f"hazard_{m}"
        h = h.rename(columns={"hazard": col})
        if merged is None:
            merged = h[GCM_MERGE_KEY + _META_COLUMNS + [col]].copy()
        else:
            merged = merged.merge(h[GCM_MERGE_KEY + [col]], on=GCM_MERGE_KEY, how="outer")

    dup = int(merged.duplicated(GCM_MERGE_KEY).sum())
    if dup:
        raise RuntimeError(
            f"compute_hazard_by_gcm produced {dup} duplicate {GCM_MERGE_KEY} rows "
            "-- the per-GCM merge cross-joined. This should be impossible with a "
            "stable plant_uid; investigate load_plants."
        )
    return merged


# --------------------------------------------------------------------------
# Computable base (V6) -- for any future capacity roll-up
# --------------------------------------------------------------------------
def computable_base(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to the V6 computable base: valid coordinate (every plant has
    one) + ``commissioning_year`` present. Any capacity sum in the per-country
    roll-up (``ARCHITECTURE.md`` Section 5.5) starts here, never from
    ``capacity_mw`` over the whole fleet."""
    return df[df["commissioning_year"].notna()]


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
    parser.add_argument("--out", type=Path, default=OUTPUT_TABLES / "ccrs_hazard.csv")
    args = parser.parse_args()

    if args.check_bounds:
        try:
            live = assert_frozen_bounds_current()
        except BoundsRegressionError as exc:
            logger.error(str(exc))
            return 1
        logger.info("frozen bounds match the data (%s): %s", BOUNDS_DATA_SNAPSHOT, live)
        return 0

    wide = compute_hazard_by_gcm()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    wide.to_csv(args.out, index=False)
    logger.info("wrote %s (%d plant x scenario rows)", args.out, len(wide))

    haz_cols = [c for c in wide.columns if c.startswith("hazard_")]
    for c in haz_cols:
        s = wide[c].dropna()
        logger.info("%s: n=%d, p50=%.4f, p95=%.4f, max=%.4f",
                    c, len(s), s.median(), s.quantile(0.95), s.max())
    base = computable_base(wide)
    logger.info("computable base (commissioning_year present): %d / %d rows",
                len(base), len(wide))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
