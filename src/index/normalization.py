"""
GEAR v3 normalization module -- FROZEN_BOUNDS computation, the per-hazard
normality/skewness check that selects a Min-Max transform (``docs/rework/
GEAR_v3_methodology_nature_format.md`` Section 4.2), and the structured
bounds origin table (Section 4.3).

Phase 2.4 of ``docs/rework/GEAR_v3_work_plan.md``. Isolated module per the
standing modularity rule -- imports the already-verified sampling/plant-
loading infrastructure from ``src.index.risk_calculator`` (``load_plants``,
``sample_raster``, ``raster_path``, the water-scenario/GCM pairing, the
five terms and ``FROZEN_BOUNDS`` that module already computes) rather than
reimplementing it. This module does **not** modify ``risk_calculator.py``
and does not feed its recommendation back into ``risk_calculator.
HAZARD_TERMS`` or ``FROZEN_BOUNDS`` -- it produces an independent
recommendation (selected transform + bounds + origin table) per hazard
candidate. Phase 3.3 (``docs/rework/GEAR_v3_work_plan.md``) applied that
recommendation to ``risk_calculator.py``'s ``LOG_TERMS`` transform on
2026-09-14 (``docs/DECISIONS.md``, "Phase 3.3 scope over `wind`: closed"):
``risk_calculator.transform_term``'s ``Tlog`` branch now reproduces this
module's ``transform_neg_log_minmax`` mechanism directly (not imported --
this module imports ``risk_calculator``, so the reverse import would be
circular), for every current ``LOG_TERMS`` member (``ws``, ``heat``,
``wind``). ``spei`` was also ``LOG_TERMS`` on 2026-09-14 but was
reclassified to ``LIN_TERMS`` in a later same-day correction (an inherited,
never-re-evaluated CCRS default; the published article's own Table S3
reports its transform as direct Min-Max -- see ``docs/DECISIONS.md``, "GEAR
v3: spei reclassified from LOG_TERMS to LIN_TERMS (Phase 3.3 correction)").
``FROZEN_BOUNDS`` itself (raw, pre-transform min/max) is unaffected -- only
the transform formula applied to those bounds changed.

--------------------------------------------------------------------------
Candidate hazard set -- run uniformly, no special-casing
--------------------------------------------------------------------------
Every candidate below goes through the identical normality-check ->
transform-selection procedure. None is hardcoded to a particular transform
in advance, including the two terms with a documented prior assumption:

* ``sv``/``iv`` (water seasonal/interannual variability) were assigned a
  linear (direct Min-Max) transform in the retired ``ccrs_calculator.py``
  and carried over unchanged into ``risk_calculator.LIN_TERMS`` -- that was
  never the output of a normality check, just an inherited default. This
  module re-evaluates them like any other candidate.
* ``heat`` (Extreme Heat) carries a known tail-compression complaint
  (Phase 3.3, ``docs/rework/GEAR_v3_work_plan.md``) -- it is checked by the
  same procedure as every other term, not special-cased to force a
  particular transform ahead of the check.

``NORMALIZATION_CANDIDATE_TERMS`` is ``risk_calculator.HAZARD_TERMS`` in
full -- as of 2026-09-14 that already includes ``precip`` and ``wind``
(both wired into ``risk_calculator.py``; see ``docs/DECISIONS.md``, "GEAR
v3 wind Risk_i,h integration: empirical transform result,
PENDING_RISK_I_H_HAZARDS closed"), so ``NEW_CANDIDATE_TERMS`` is now empty
-- kept as a named, empty tuple rather than deleted, so a future hazard
processor added ahead of its own ``risk_calculator`` wiring still has an
obvious place to register as a normalization candidate before it is
production-wired (the exact role ``precip``/``wind`` served here earlier).
Extreme Wind's raw gust layer only is what is normalized here -- the
Wind-bucket IEC cut-out vs. Solar-bucket percentile threshold split from
Phase 2.3 is a Phase 3.2 classification concern, irrelevant to normalizing
the raw distribution. Wildfire is excluded -- deferred, not part of the
hazard set (``docs/DECISIONS.md``, "GEAR v3 Phase 2.2: Wildfire deferred").

--------------------------------------------------------------------------
Transform selection (Section 4.2) -- confirmed redesign, 2026-09-11
--------------------------------------------------------------------------
Three transform candidates are considered per hazard. Selection is a
per-hazard normality/skewness check on that hazard's pooled distribution
(plant x water-scenario samples, countries and scenarios pooled -- the same
pool ``risk_calculator.compute_global_bounds`` already uses for its five
terms):

* ``direct_minmax`` -- approximately-normal variables:
  ``(x - lo) / (hi - lo)``.
* ``neg_log_minmax`` -- ``f(x) = -ln(1 - x)`` applied to a preliminary
  Min-Max scaling of the raw value (padded so the pooled maximum never
  reaches the ``x = 1`` singularity), then Min-Maxed a second time onto
  ``[0, 1]``. Selected for skewed variables. **Confirmed to replace
  ``log1p_minmax`` (below) as the skewed-variable transform, uniformly, not
  only for Extreme Heat**: log1p compresses the upper tail of a
  right-skewed hazard (large values are pushed close together near 1.0,
  exactly where a physically extreme plant should be most separated from a
  moderate one); ``-ln(1-x)`` does the opposite -- it expands the upper
  tail, since ``-ln(1-x) -> infinity`` as ``x -> 1``. This is the mechanism
  Phase 3.3 applies to Extreme Heat's tail-compression complaint, arrived
  at here by the same uniform check applied to every candidate.
* ``log1p_minmax`` -- **retired**, not selectable. Kept as
  ``transform_log1p_minmax`` only so the origin table can show what the
  pre-redesign ``FROZEN_BOUNDS`` in ``risk_calculator.py`` used for
  ``ws``/``heat``/``spei``, as an explicit before/after record.
  ``select_transform`` never returns it.

The normality/skewness check itself (``normality_check``) uses the
Fisher-Pearson skewness statistic (``scipy.stats.skew``) as the DECIDING
criterion, with Shapiro-Wilk (``scipy.stats.shapiro``) computed and
reported alongside as a diagnostic only. This is a deliberate choice, not
an oversight: at the sample sizes here (thousands of plant x scenario
rows), Shapiro-Wilk rejects exact normality for almost any real
geophysical sample, including mildly skewed ones, so it is not informative
as a binary gate; skewness magnitude, thresholded at the standard
``|skew| <= 0.5`` "fairly symmetrical" convention (Bulmer, 1979,
*Principles of Statistics*, Dover ed. 1979, Section 4.5), is the decisive
signal. Tier: author-declared engineering threshold, not a literature
value specific to hydrometeorological hazard variables -- flagged the same
way other engineering defaults in this project are (e.g. ``age_factor``'s
assumed coal-overhaul cycle, ``ERA5_WIND_BASELINE_PERIOD``).

--------------------------------------------------------------------------
Standalone
--------------------------------------------------------------------------
``python -m src.index.normalization`` from the project root. Reads the
processed raw rasters and ``gem_validated_plants_{country}.csv`` (via
``risk_calculator.load_plants``); writes
``data/outputs/tables/normalization_origin_table.csv``.
"""

from __future__ import annotations

import argparse
import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from src.config import OUTPUT_TABLES
from src.downloaders.cds_tasmax_downloader import configured_models
from src.index import risk_calculator as rc
from src.processors.extreme_precipitation_processor import raw_raster_path as precip_raw_path
from src.processors.extreme_wind_processor import raw_raster_path as wind_raw_path

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Candidate terms -- all of risk_calculator.HAZARD_TERMS now (precip and
# wind are both wired in as of 2026-09-14; NEW_CANDIDATE_TERMS is therefore
# empty, kept as a named placeholder -- see module docstring). Wildfire is
# deliberately absent (deferred hazard, not part of this or any hazard set).
# --------------------------------------------------------------------------
NEW_CANDIDATE_TERMS: tuple[str, ...] = ()
NORMALIZATION_CANDIDATE_TERMS = tuple(rc.HAZARD_TERMS) + NEW_CANDIDATE_TERMS

# Terms whose distribution depends on the GCM (temperature/precipitation-
# derived, CMIP6-sourced): risk_calculator's existing heat/spei/precip.
# ``wind`` is ERA5 reanalysis, no GCM axis -- pooled once, like the flat
# Aqueduct terms (already reflected in rc.GCM_DEPENDENT_TERMS, no extra
# term to union in here anymore).
GCM_DEPENDENT_TERMS = frozenset(rc.GCM_DEPENDENT_TERMS)
FLAT_BOUND_TERMS = tuple(t for t in NORMALIZATION_CANDIDATE_TERMS if t not in GCM_DEPENDENT_TERMS)

HAZARD_LABELS = dict(rc.HAZARD_LABELS)
HAZARD_LABELS["precip"] = "Extreme Precipitation"
HAZARD_LABELS["wind"] = "Extreme Wind"

ORIGIN_SOURCE = {
    "ws": "WRI Aqueduct 4.0 future_annual -- water stress (consumption:availability ratio)",
    "sv": "WRI Aqueduct 4.0 future_annual -- seasonal variability",
    "iv": "WRI Aqueduct 4.0 future_annual -- interannual variability",
    "heat": "Copernicus CDS CMIP6 tasmax -- days/year with tasmax > 40C",
    "spei": "CMIP6 pr+tas (Thornthwaite PET) SPEI-12 -- months/year with SPEI <= -1.0",
    "precip": "CMIP6 pr -- days/year exceeding the pixel's own P95 wet-day amount",
    "wind": "ERA5 10 m instantaneous wind gust -- mean annual maximum (m/s)",
}
# Data tier for the BOUND itself (not the RiskBand threshold tier of Phase
# 3.2): every bound here is an empirical pooled sample min/max, never a
# literature constant, so all candidates share the same tier statement.
DATA_TIER = "empirical (pooled sample min/max, not a literature constant)"

# --------------------------------------------------------------------------
# Normality/skewness check
# --------------------------------------------------------------------------
SKEWNESS_NORMAL_THRESHOLD = 0.5  # Bulmer (1979) "fairly symmetrical" cutoff
SHAPIRO_MAX_N = 5000             # scipy.stats.shapiro's documented reliable ceiling
SHAPIRO_SUBSAMPLE_SEED = 20260911  # deterministic -- same subsample every run


def normality_check(sample: np.ndarray) -> dict:
    """Skewness (deciding) + Shapiro-Wilk (diagnostic only) on ``sample``.

    ``is_skewed`` is ``abs(skewness) > SKEWNESS_NORMAL_THRESHOLD`` -- the
    sole criterion ``select_transform`` reads. ``shapiro_stat``/
    ``shapiro_p`` are always computed and returned (subsampled
    deterministically above ``SHAPIRO_MAX_N``) so they appear in the origin
    table as a cross-check, but do not change the verdict -- see the module
    docstring for why.
    """
    sample = np.asarray(sample, "float64")
    sample = sample[~np.isnan(sample)]
    n = int(sample.size)
    if n < 3:
        raise ValueError(f"normality_check needs >= 3 finite values, got {n}")

    skewness = float(sp_stats.skew(sample))
    is_skewed = abs(skewness) > SKEWNESS_NORMAL_THRESHOLD

    subsampled = n > SHAPIRO_MAX_N
    shapiro_input = sample
    if subsampled:
        rng = np.random.default_rng(SHAPIRO_SUBSAMPLE_SEED)
        shapiro_input = rng.choice(sample, size=SHAPIRO_MAX_N, replace=False)
    shapiro_stat, shapiro_p = sp_stats.shapiro(shapiro_input)

    return {
        "n": n,
        "skewness": skewness,
        "is_skewed": is_skewed,
        "shapiro_stat": float(shapiro_stat),
        "shapiro_p": float(shapiro_p),
        "shapiro_subsampled": subsampled,
    }


def select_transform(check: dict) -> str:
    """``neg_log_minmax`` if skewed, else ``direct_minmax``. Never returns
    ``log1p_minmax`` (retired -- see module docstring)."""
    return "neg_log_minmax" if check["is_skewed"] else "direct_minmax"


# --------------------------------------------------------------------------
# Transforms
# --------------------------------------------------------------------------
UPPER_TAIL_PADDING_FRACTION = 0.05
# Author-declared engineering parameter (Tier 3, same transparency standard
# as the coal-overhaul cycle in age_factor.py): the preliminary Min-Max
# scaling for neg_log_minmax pads the raw upper bound by this fraction of
# the raw span so the pooled maximum lands strictly below the x=1
# singularity of -ln(1-x). Not derived from any cited source. 0.05 keeps
# the pooled max well inside the domain (padded x ~= 0.952) while keeping
# the transformed range compact (ln(1 + 1/0.05) = ln(21) ~= 3.045).


def transform_direct_minmax(raw: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """``(x - lo) / (hi - lo)``, clipped to ``[0, 1]``. Degenerate domain
    (``hi <= lo``) -> zeros, same convention as ``risk_calculator.
    transform_term``."""
    raw = np.asarray(raw, "float64")
    if hi <= lo:
        return np.zeros_like(raw)
    return np.clip((raw - lo) / (hi - lo), 0.0, 1.0)


def transform_log1p_minmax(raw: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Retired. ``log1p`` applied to both data and bound before Min-Max --
    ``risk_calculator.transform_term``'s ``LOG_TERMS`` branch, reproduced
    here only so the origin table can record the pre-redesign transform.
    Never returned by ``select_transform``."""
    raw = np.asarray(raw, "float64")
    x, a, b = np.log1p(raw), math.log1p(lo), math.log1p(hi)
    if b <= a:
        return np.zeros_like(x)
    return np.clip((x - a) / (b - a), 0.0, 1.0)


def transform_neg_log_minmax(
    raw: np.ndarray, lo: float, hi: float, pad: float = UPPER_TAIL_PADDING_FRACTION,
) -> np.ndarray:
    """``f(x) = -ln(1-x)`` on a padded preliminary Min-Max, then Min-Maxed
    again onto ``[0, 1]``.

    Step 1 (preliminary scale): ``x_scaled = (raw - lo) / (padded_hi - lo)``,
    ``padded_hi = hi + pad * (hi - lo)`` -- the padding keeps the pooled
    maximum's ``x_scaled`` strictly below 1 so step 2 never evaluates
    ``ln(0)``. Values are additionally clipped to ``[0, 1 - 1e-9]`` as a
    numerical guard for any out-of-pool value encountered later.

    Step 2 (expand + rescale): ``transformed = -ln(1 - x_scaled)``, then
    divided by its closed-form maximum ``ln(1 + 1/pad)`` (the value
    ``transformed`` takes at the pooled maximum, ``x_scaled = 1/(1+pad)`` --
    independent of ``lo``/``hi``, since the padding fraction is relative).
    Degenerate domain (``hi <= lo``) -> zeros.
    """
    raw = np.asarray(raw, "float64")
    span = hi - lo
    if span <= 0:
        return np.zeros_like(raw)
    padded_hi = hi + pad * span
    x_scaled = (raw - lo) / (padded_hi - lo)
    x_scaled = np.clip(x_scaled, 0.0, 1.0 - 1e-9)
    transformed = -np.log1p(-x_scaled)
    transformed_max = math.log1p(1.0 / pad)
    return np.clip(transformed / transformed_max, 0.0, 1.0)


TRANSFORMS = {
    "direct_minmax": transform_direct_minmax,
    "neg_log_minmax": transform_neg_log_minmax,
    "log1p_minmax": transform_log1p_minmax,
}


def apply_transform(kind: str, raw: np.ndarray, lo: float, hi: float) -> np.ndarray:
    try:
        fn = TRANSFORMS[kind]
    except KeyError:
        raise ValueError(f"unknown transform kind {kind!r} (expected one of {list(TRANSFORMS)})")
    return fn(raw, lo, hi)


# --------------------------------------------------------------------------
# Sampling -- reuses risk_calculator's plant loading and raster sampling;
# extends the row set with the two new candidate terms.
# --------------------------------------------------------------------------
def _candidate_raster_path(term: str, country: str, water_scenario: str, model: str) -> Path:
    if term in rc.HAZARD_TERMS:
        return rc.raster_path(term, country, water_scenario, model)
    if term == "precip":
        return precip_raw_path(country, model, rc.WATER_TO_HEAT[water_scenario])
    if term == "wind":
        return wind_raw_path(country)
    raise ValueError(f"unknown normalization candidate {term!r}")


def _sample_raster_or_nan(path: Path, lons, lats, context: str):
    """``rc.sample_raster``, but a missing raster returns all-NaN (logged)
    instead of crashing the whole recommendation run. Same pattern and same
    rationale as ``risk_bands._sample_raster_or_nan``: wind's ERA5 gust
    acquisition is incomplete (no country has a processed
    ``extreme_wind_gust_raw_*.tif`` yet), and a still-pending candidate
    should not make every other candidate's recommendation unrunnable."""
    if not path.exists():
        logger.warning("missing raster for %s: %s -- treating as all-NaN", context, path)
        return np.full(np.shape(lons), np.nan, dtype="float64")
    return rc.sample_raster(path, lons, lats)


def sample_candidate_terms(model: str) -> pd.DataFrame:
    """One row per (plant, water scenario) with every candidate term's RAW
    value sampled for ``model`` on the GCM-dependent terms. Same shape as
    ``risk_calculator.sample_terms``, extended with ``precip``/``wind``."""
    parts = []
    for country in rc.COUNTRIES:
        plants = rc.load_plants(country)
        lons = plants["lon"].to_numpy("float64")
        lats = plants["lat"].to_numpy("float64")
        wind_values = _sample_raster_or_nan(wind_raw_path(country), lons, lats, f"wind/{country}")
        for water_scen in rc.WATER_SCENARIOS:
            part = plants.copy()
            part["water_scenario"] = water_scen
            part["heat_scenario"] = rc.WATER_TO_HEAT[water_scen]
            for term in NORMALIZATION_CANDIDATE_TERMS:
                if term == "wind":
                    part[term] = wind_values
                else:
                    part[term] = rc.sample_raster(
                        _candidate_raster_path(term, country, water_scen, model), lons, lats
                    )
            parts.append(part)
    return pd.concat(parts, ignore_index=True)


# --------------------------------------------------------------------------
# Recommendation pipeline: bounds + normality check + transform, per term
# (per GCM where applicable), and the origin table.
# --------------------------------------------------------------------------
def _pool(frame: pd.DataFrame, term: str) -> np.ndarray:
    return frame.loc[frame[term].notna(), term].to_numpy("float64")


def _recommend_one(term: str, gcm_label: str, sample: np.ndarray) -> dict:
    lo, hi = float(sample.min()), float(sample.max())
    check = normality_check(sample)
    transform = select_transform(check)
    return {
        "term": term, "gcm": gcm_label, "bounds": (lo, hi),
        "check": check, "transform": transform,
    }


def compute_normalization_recommendations(models: list[str] | None = None) -> dict:
    """Bounds + normality check + selected transform for every candidate
    term (per GCM for the GCM-dependent ones). Returns
    ``{"recommendations": {term: {...} | {gcm: {...}}}, "origin_table": DataFrame}``.

    Pool membership mirrors ``risk_calculator.compute_global_bounds``: plant
    x water-scenario rows with a known ``fuel_type_bucket``, term value
    finite.
    """
    models = models or configured_models()
    frames = {m: sample_candidate_terms(m) for m in models}
    frames = {m: f[f["bucket"].isin(rc.BUCKETS)] for m, f in frames.items()}

    recommendations: dict[str, object] = {}
    rows = []

    for term in FLAT_BOUND_TERMS:
        sample = _pool(frames[models[0]], term)
        if sample.size < 3:
            logger.warning(
                "skipping %s: only %d finite pooled value(s) -- no processed "
                "raster for this candidate yet (see PENDING_RISK_I_H_HAZARDS-"
                "style gap, hazard_scope.py).", term, sample.size,
            )
            continue
        rec = _recommend_one(term, "pooled", sample)
        recommendations[term] = {"bounds": rec["bounds"], "check": rec["check"], "transform": rec["transform"]}
        rows.append(rec)

    for term in GCM_DEPENDENT_TERMS:
        per_gcm = {}
        for model, frame in frames.items():
            sample = _pool(frame, term)
            if sample.size < 3:
                logger.warning(
                    "skipping %s/%s: only %d finite pooled value(s) -- no "
                    "processed raster for this candidate yet.", term, model, sample.size,
                )
                continue
            rec = _recommend_one(term, model, sample)
            per_gcm[model] = {"bounds": rec["bounds"], "check": rec["check"], "transform": rec["transform"]}
            rows.append(rec)
        if per_gcm:
            recommendations[term] = per_gcm

    origin_table = build_origin_table(rows)
    return {"recommendations": recommendations, "origin_table": origin_table}


def build_origin_table(rows: list[dict]) -> pd.DataFrame:
    """Structured bounds origin table (Section 4.3): one row per hazard
    term (per GCM where the term is GCM-dependent) with variable, bounds,
    origin, tier, normality-check result and the transform applied. Never
    silently assumes a transform -- every row's ``transform_selected`` comes
    from ``select_transform``'s output for that row's own check."""
    records = []
    for row in rows:
        term = row["term"]
        check = row["check"]
        lo, hi = row["bounds"]
        records.append({
            "hazard_term": term,
            "hazard_label": HAZARD_LABELS[term],
            "gcm": row["gcm"],
            "origin_source": ORIGIN_SOURCE[term],
            "data_tier": DATA_TIER,
            "lower_bound_raw": lo,
            "upper_bound_raw": hi,
            "pool_n": check["n"],
            "skewness": check["skewness"],
            "shapiro_stat": check["shapiro_stat"],
            "shapiro_p": check["shapiro_p"],
            "shapiro_subsampled": check["shapiro_subsampled"],
            "is_skewed": check["is_skewed"],
            "transform_selected": row["transform"],
            "transform_note": (
                "replaces retired log1p_minmax" if row["transform"] == "neg_log_minmax"
                else "approximately normal, no transform beyond Min-Max"
            ),
        })
    return pd.DataFrame.from_records(records)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUTPUT_TABLES / "normalization_origin_table.csv")
    args = parser.parse_args()

    result = compute_normalization_recommendations()
    origin_table = result["origin_table"]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    origin_table.to_csv(args.out, index=False)
    logger.info("wrote %s (%d rows)", args.out, len(origin_table))

    for _, row in origin_table.iterrows():
        logger.info(
            "%s [%s]: skew=%.3f shapiro_p=%.4g -> %s",
            row["hazard_term"], row["gcm"], row["skewness"], row["shapiro_p"],
            row["transform_selected"],
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
