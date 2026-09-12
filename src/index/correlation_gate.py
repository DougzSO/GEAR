"""
GEAR v3 Phase 2.5: the correlation gate (``docs/rework/
GEAR_v3_methodology_nature_format.md`` Section 5; ``docs/rework/
GEAR_v3_work_plan.md`` Phase 2.5).

Isolated module per the standing modularity rule -- imports the
already-verified plant-loading/raster-sampling infrastructure from
``src.index.risk_calculator`` (``load_plants``, ``sample_raster``,
``raster_path``, ``WATER_TO_HEAT``) and the grid-consistency guard from
``src.processors._common`` (``assert_consistent_grid``) rather than
reimplementing either. Does **not** modify ``risk_calculator.py`` or
``normalization.py``, and does not consume ``normalization.py``'s output:
per the author's explicit confirmation, this gate runs on RAW, pre-
normalization, pre-transform hazard values -- the same raw rasters
``risk_calculator.sample_raster`` reads before ``transform_term``/
``apply_transform`` is ever applied.

--------------------------------------------------------------------------
Candidate pairs -- exactly six, no others
--------------------------------------------------------------------------
Five gated pairs (``|r| >= 0.80`` excludes one variable from a bucket's
applicable set) and one report-only pair (Water Stress vs Drought, mandatory
for Hydro by design, never excluded regardless of ``r``):

    precip vs ws      (gated)
    precip vs spei     (gated)
    sv vs ws           (gated)
    iv vs ws           (gated)
    sv vs iv           (gated)
    ws vs spei         (report-only -- no exclusion logic wired to this pair
                        under any circumstance; see ``REPORT_ONLY_PAIRS``)

Extreme Wind and Wildfire are never part of this gate: Extreme Wind by
original design (a dedicated per-bucket hazard, never a correlation
candidate, Methods Section 3.1); Wildfire because it is deferred from the
hazard checklist entirely (``docs/DECISIONS.md``, "GEAR v3 Phase 2.2:
Wildfire deferred").

--------------------------------------------------------------------------
Per-bucket scope, restricted to mechanistically applicable buckets
--------------------------------------------------------------------------
A pair is only evaluated for a technology bucket if BOTH members are (or
would be, for sv/iv) mechanistically relevant to that bucket's H_b table
(Methods Section 3): Hydro and Thermal are the only buckets with a water
mechanism (Wind and Solar are declared "no water dependency" in Section
3's own exclusion rationale), so every ws/sv/iv-involving pair is Hydro/
Thermal only. Drought applies only to Hydro -- Thermal's water mechanism is
fully captured by Water Stress per Section 3's own exclusion rationale
("Drought mechanism already captured via Water Stress") -- so ``precip`` vs
``spei`` and ``ws`` vs ``spei`` are Hydro-only. Evaluating e.g. ``precip``
vs ``spei`` inside the Wind bucket would produce a number with no
mechanistic referent (neither hazard is ever a Wind candidate), so it is
not computed, not silently zero-filled.

--------------------------------------------------------------------------
Spatial harmonization -- reuses the existing per-country 1 km grid, no new
regridding step
--------------------------------------------------------------------------
Methods Section 5 requires harmonizing both layers to a common spatial
support before computing ``r``. This project's raster-processing layer
already guarantees that: every candidate raster (``ws``/``sv``/``iv`` via
``water_stress_processor``/``water_variability_processor``, ``spei`` via
``spei_processor``, ``precip`` via ``extreme_precipitation_processor``) is
resampled onto, or rasterised directly onto, the SAME per-country 1 km
reference grid (the grid of an already-processed extreme-heat raster --
``src/processors/_common.py``'s ``_load_reference_grid``/
``_resample_to_1km``), so every candidate layer is already pixel-for-pixel
co-registered by construction, not merely "close enough" in resolution.

This module therefore does not build a new regridder or a zonal/basin
aggregation step. Instead it (a) reuses ``src/processors/_common.py``'s
existing ``assert_consistent_grid`` guard -- the same one
``heat_stress_processor``/``spei_processor`` already use to certify a
pooled Min-Max domain -- to verify, programmatically and loudly, that the
two rasters in a given pair share one grid for that country before any
value is read; then (b) samples both rasters via ``risk_calculator.
sample_raster``'s existing nearest-pixel extraction at the exact same
plant coordinate set. Because both layers sit on the identical grid, this
point extraction reads the same grid cell across layers for every plant --
a genuinely harmonized common support, not an independent "nearest pixel
in each raster's own resolution" approximation. This is the "aggregated to
a common spatial support" step Section 5 requires; it is a verification of
an already-true invariant, not new regridding, and is why no new
regrid/zonal utility was written for this module.

--------------------------------------------------------------------------
Pearson vs Spearman
--------------------------------------------------------------------------
Pearson's r is the primary, reported statistic (Methods Section 5 states
the gate criterion as ``|r| < 0.80`` without specifying rank vs linear;
Pearson is used because every candidate pair here is a continuous
physical-quantity comparison -- e.g. a wet-day-exceedance count against a
consumption/availability ratio -- with no ordinal-only variable, so a
linear correlation is the more informative default and the one directly
comparable to the ``-0.85``/``0.80`` style cutoffs used in this
methodology's prior drafts). Spearman's rho is always computed alongside,
never only on request, so a rank-based reading is available for every row
without a second pass.

A pair is NOT forced to Pearson uniformly if the pooled scatter argues
against it: ``flag_nonlinearity`` compares ``|rho| - |r|`` against
``NONLINEARITY_FLAG_THRESHOLD``. When the gap exceeds that threshold (rank
correlation materially stronger than linear correlation -- the classic
signature of a monotonic-but-curved relationship, e.g. the negative,
saturating Precipitation/Drought relationship Section 5 already expects a
sign for), Spearman's rho, not Pearson's r, is used as the operative
gate-decision statistic for that specific (pair, bucket, country, gcm)
cell -- flagged as such in the output (``nonlinearity_flagged``,
``decision_r_method``), not silently substituted. This is an automated
proxy for "visibly non-linear on inspection" (Tier 3, author-declared
threshold, no literature precedent for this specific cutoff) -- it does
not replace an eventual manual scatter-plot check before the article's
final supplementary figure, and is stated as a proxy, not equivalent to
one.

--------------------------------------------------------------------------
Country pooling
--------------------------------------------------------------------------
Per Methods Section 5 (this task's explicit instruction): ``r`` is computed
PER COUNTRY separately (Brazil, Portugal, India each get their own row),
never pooled across countries for the gate decision itself. A pooled/
global value is also computed and reported for reference only, alongside,
never substituted for the per-country values in the gate verdict.

Within a country, the sample pools the three water/heat-scenario pairings
(opt/bau/pes) as additional observations per plant -- the same pooling
convention ``risk_calculator.compute_global_bounds`` already uses for its
per-term bounds -- rather than gating separately per scenario, which
Section 5 does not call for and which would fragment an already
country-and-bucket-restricted sample into groups too small for a stable
correlation estimate.

--------------------------------------------------------------------------
GCM axis
--------------------------------------------------------------------------
``spei`` and ``precip`` are GCM-dependent (GFDL-ESM4 / MIROC6); ``ws``/
``sv``/``iv`` have no GCM axis (Aqueduct rasters are GCM-independent by
construction, ``risk_calculator`` module docstring). Consistent with this
project's standing rule that GFDL-ESM4 and MIROC6 are never pooled or
blended (``ARCHITECTURE.md`` Section 5.4), a pair with at least one
GCM-dependent member is reported PER GCM, never averaged across GCMs;
``precip`` vs ``spei`` (both GCM-dependent) is paired same-GCM only,
never cross-GCM. Flat-flat pairs (``sv``/``iv``/``ws`` mutually) have no
GCM axis and are reported once, with ``gcm = "not_gcm_dependent"`` (not the
string ``"n/a"`` -- that is one of pandas' default ``read_csv`` NA
sentinels and would silently round-trip back to a real ``NaN`` on reload,
indistinguishable from a data problem).

--------------------------------------------------------------------------
Standalone
--------------------------------------------------------------------------
``python -m src.index.correlation_gate`` from the project root. Reads the
processed raw rasters and ``gem_validated_plants_{country}.csv``; writes
``data/outputs/tables/correlation_gate.csv`` (one row per pair x bucket x
country x gcm), a reusable artifact for Phase 7's figures.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import rioxarray  # noqa: F401 - registers the .rio accessor
from scipy import stats as sp_stats

from src.config import COUNTRIES, OUTPUT_TABLES
from src.downloaders.cds_tasmax_downloader import configured_models
from src.index import risk_calculator as rc
from src.processors._common import assert_consistent_grid
from src.processors.extreme_precipitation_processor import raw_raster_path as precip_raw_path

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Gate threshold and terms
# --------------------------------------------------------------------------
GATE_THRESHOLD = 0.80  # |r| >= this excludes -- Methods Section 5

GATE_TERMS = ("ws", "sv", "iv", "spei", "precip")
GCM_DEPENDENT_GATE_TERMS = frozenset({"spei", "precip"})
FLAT_GATE_TERMS = frozenset({"ws", "sv", "iv"})
assert GCM_DEPENDENT_GATE_TERMS | FLAT_GATE_TERMS == set(GATE_TERMS)

TERM_LABELS = {
    "ws": "Water Stress",
    "sv": "Seasonal Variability",
    "iv": "Interannual Variability",
    "spei": "Drought (SPEI)",
    "precip": "Extreme Precipitation",
}

# Buckets with a water mechanism at all (Section 3: Wind/Solar are "no water
# dependency"). Every candidate pair below is restricted to a subset of
# this set -- see module docstring, "Per-bucket scope".
WATER_BUCKETS = ("hydro", "thermal")


@dataclass(frozen=True)
class CandidatePair:
    term_a: str
    term_b: str
    gated: bool
    buckets: tuple[str, ...]
    label: str


CANDIDATE_PAIRS: tuple[CandidatePair, ...] = (
    CandidatePair("precip", "ws", gated=True, buckets=WATER_BUCKETS,
                  label="Extreme Precipitation vs Water Stress"),
    CandidatePair("precip", "spei", gated=True, buckets=("hydro",),
                  label="Extreme Precipitation vs Drought (SPEI)"),
    CandidatePair("sv", "ws", gated=True, buckets=WATER_BUCKETS,
                  label="Seasonal Variability vs Water Stress"),
    CandidatePair("iv", "ws", gated=True, buckets=WATER_BUCKETS,
                  label="Interannual Variability vs Water Stress"),
    CandidatePair("sv", "iv", gated=True, buckets=WATER_BUCKETS,
                  label="Seasonal vs Interannual Variability"),
    CandidatePair("ws", "spei", gated=False, buckets=("hydro",),
                  label="Water Stress vs Drought (SPEI) -- report-only, "
                        "mandatory pair, never excluded"),
)
REPORT_ONLY_PAIRS = tuple(p for p in CANDIDATE_PAIRS if not p.gated)
GATED_PAIRS = tuple(p for p in CANDIDATE_PAIRS if p.gated)


def _pair_is_gcm_dependent(pair: CandidatePair) -> bool:
    return pair.term_a in GCM_DEPENDENT_GATE_TERMS or pair.term_b in GCM_DEPENDENT_GATE_TERMS


# --------------------------------------------------------------------------
# Pre-registered tie-breaker hierarchy (Methods Section 5, fixed before this
# gate was run -- docs/DECISIONS.md, "GEAR v3 Phase 2.5: pre-registered
# correlation-gate tie-breaker rule"). Encoded here as data, not re-derived
# ad hoc per pair.
# --------------------------------------------------------------------------
# Criterion 1 -- mechanistic primacy, per bucket. Only populated where
# Methods Section 2 (per-hazard Mechanism column) or Section 3 (per-bucket
# exclusion rationale) states a direct, textual basis; ``None`` means
# "ambiguous by the text as written" and the pair falls through to
# Criterion 2, not to an invented ranking.
#   - precip vs ws: ws's stated mechanism (Section 2) is "Thermal
#     cooling-water availability" -- inapplicable to Hydro (Section 3:
#     "Not thermally cooled"), so precip (spillway overtopping/powerhouse
#     flooding, Section 3) is primary in Hydro. In Thermal, cooling-water
#     availability IS the bucket's defining mechanism (Section 2), so ws is
#     primary there.
#   - precip vs spei: per this project's own Criterion-1 framing example
#     (docs/DECISIONS.md), Drought is more directly tied to Hydro's
#     headloss/inflow failure mode than Extreme Precipitation's
#     overtopping/flooding mechanism -- spei is primary in Hydro.
#   - sv/iv vs ws, and sv vs iv: no differentiated mechanism is stated
#     anywhere in Sections 2/3 for sv or iv specifically (both are "the
#     same Aqueduct product as ws", risk_calculator module docstring) --
#     ambiguous, falls through.
MECHANISTIC_PRIMACY: dict[tuple[str, str], dict[str, str | None]] = {
    ("precip", "ws"): {"hydro": "precip", "thermal": "ws"},
    ("precip", "spei"): {"hydro": "spei"},
    ("sv", "ws"): {"hydro": None, "thermal": None},
    ("iv", "ws"): {"hydro": None, "thermal": None},
    ("sv", "iv"): {"hydro": None, "thermal": None},
}

# Criterion 2 -- data-tier confidence (Section 4). ``ws`` has a cited Tier 1
# threshold (WRI Aqueduct category cutoffs); ``spei``/``precip`` have a
# declared Tier 3 fallback (no defensible Tier 1 found, Section 4); ``sv``/
# ``iv`` have no Section 4 entry at all (outside Section 2's checklist,
# Phase 3 pending) and are treated as tier-undefined/lowest confidence by
# default, consistent with Section 4's "no untagged threshold is permitted"
# framing read conservatively (absence of a tier is not treated as Tier 1).
DATA_TIER_RANK = {"ws": 1, "spei": 3, "precip": 3, "sv": 4, "iv": 4}  # lower wins


def _criterion_2_winner(term_a: str, term_b: str) -> str | None:
    ra, rb = DATA_TIER_RANK[term_a], DATA_TIER_RANK[term_b]
    if ra == rb:
        return None
    return term_a if ra < rb else term_b


# Criterion 3 -- sv/iv specific (convergent Tier 2 evidence: PNNL-33212 +
# companion FAQ, Colorado River Hoover/Glen Canyon case; Moghaddasi, Gavahi,
# Moftakhari & Moradkhani 2024, Environmental Research Letters 19(8)). iv
# retained over sv if this exact pair fails the gate. See
# docs/DECISIONS.md, "GEAR v3 Phase 2.5: pre-registered correlation-gate
# tie-breaker rule" for the full citation and the explicit convergent-not-
# definitive qualification.
SV_IV_CRITERION_3_WINNER = "iv"


def resolve_tie_breaker(term_a: str, term_b: str, bucket: str) -> tuple[str, int]:
    """Which term is retained, and which criterion (1/2/3) decided it, for
    ``term_a``/``term_b`` failing the gate in ``bucket``. Raises
    ``ValueError`` if no criterion resolves it (should not happen for any
    pair in ``GATED_PAIRS`` -- Criterion 2 is total over ``DATA_TIER_RANK``
    except when both terms share a rank, and Criterion 3 is the declared
    backstop for the one pair, sv/iv, where that occurs)."""
    key = (term_a, term_b) if (term_a, term_b) in MECHANISTIC_PRIMACY else (term_b, term_a)
    primacy = MECHANISTIC_PRIMACY.get(key, {})
    winner = primacy.get(bucket)
    if winner is not None:
        return winner, 1

    winner = _criterion_2_winner(term_a, term_b)
    if winner is not None:
        return winner, 2

    if {term_a, term_b} == {"sv", "iv"}:
        return SV_IV_CRITERION_3_WINNER, 3

    raise ValueError(
        f"no tie-breaker criterion resolves ({term_a}, {term_b}) in bucket "
        f"{bucket!r} -- this pair/bucket combination is missing from "
        f"MECHANISTIC_PRIMACY, DATA_TIER_RANK ties, and is not sv/iv."
    )


# --------------------------------------------------------------------------
# Sampling -- reuses risk_calculator's plant loading and raster sampling.
# --------------------------------------------------------------------------
def _term_raster_path(term: str, country: str, water_scenario: str, model: str) -> Path:
    if term == "precip":
        return precip_raw_path(country, model, rc.WATER_TO_HEAT[water_scenario])
    return rc.raster_path(term, country, water_scenario, model)


def _sample_raster_or_nan(path: Path, lons: np.ndarray, lats: np.ndarray, context: str) -> np.ndarray:
    """``rc.sample_raster``, but a missing raster file returns all-NaN (with
    a logged warning) instead of crashing the whole gate run. A genuine data
    gap (e.g. Extreme Precipitation not yet processed for a country) must
    surface as ``n`` too small / ``data_unavailable`` in the gate's output,
    not abort every other pair/country/bucket that IS computable."""
    if not path.exists():
        logger.warning("missing raster for %s: %s -- treating as all-NaN", context, path)
        return np.full(np.shape(lons), np.nan, dtype="float64")
    return rc.sample_raster(path, lons, lats)


def sample_gate_terms(models: list[str] | None = None) -> pd.DataFrame:
    """One row per (plant, water scenario), every ``GATE_TERMS`` raw value.
    Flat terms (``ws``/``sv``/``iv``) get one column; GCM-dependent terms
    (``spei``/``precip``) get one column per model, ``{term}__{model}``.
    A term/country combination with no processed raster on disk yet (see
    ``_sample_raster_or_nan``) comes back as all-NaN, not a crash."""
    models = models or configured_models()
    parts = []
    for country in COUNTRIES:
        plants = rc.load_plants(country)
        lons = plants["lon"].to_numpy("float64")
        lats = plants["lat"].to_numpy("float64")
        for water_scen in rc.WATER_SCENARIOS:
            part = plants.copy()
            part["water_scenario"] = water_scen
            part["heat_scenario"] = rc.WATER_TO_HEAT[water_scen]
            for term in FLAT_GATE_TERMS:
                part[term] = _sample_raster_or_nan(
                    _term_raster_path(term, country, water_scen, models[0]), lons, lats,
                    f"{term}/{country}/{water_scen}",
                )
            for term in GCM_DEPENDENT_GATE_TERMS:
                for model in models:
                    part[f"{term}__{model}"] = _sample_raster_or_nan(
                        _term_raster_path(term, country, water_scen, model), lons, lats,
                        f"{term}/{country}/{water_scen}/{model}",
                    )
            parts.append(part)
    return pd.concat(parts, ignore_index=True)


def _term_column(term: str, model: str | None) -> str:
    return f"{term}__{model}" if term in GCM_DEPENDENT_GATE_TERMS else term


# --------------------------------------------------------------------------
# Spatial harmonization guard (verification, not new regridding -- see
# module docstring).
# --------------------------------------------------------------------------
def verify_harmonized_grid(term_a: str, term_b: str, country: str, model: str) -> bool:
    """Assert both rasters share one grid for ``country`` before any value
    is read from them. Raises ``src.processors._common.GridMismatchError``
    (loud, never silent) on an actual mismatch. One representative scenario
    is sufficient: the 1 km grid depends only on country bounds/resolution,
    identical across every scenario of that country (``_common.py``'s
    ``_load_reference_grid`` docstring). Returns ``False`` (skips the
    check, does not raise) if either raster is not yet on disk -- a data
    gap, not a grid mismatch; the correlation itself will separately come
    back as ``n`` too small / ``data_unavailable``."""
    scen = rc.WATER_SCENARIOS[0]
    path_a = _term_raster_path(term_a, country, scen, model)
    path_b = _term_raster_path(term_b, country, scen, model)
    if not path_a.exists() or not path_b.exists():
        return False
    da_a = rioxarray.open_rasterio(path_a)
    da_b = rioxarray.open_rasterio(path_b)
    da_a = da_a.isel(band=0) if "band" in da_a.dims else da_a
    da_b = da_b.isel(band=0) if "band" in da_b.dims else da_b
    assert_consistent_grid(country, {(term_a, "a"): da_a, (term_b, "b"): da_b})
    return True


# --------------------------------------------------------------------------
# Correlation
# --------------------------------------------------------------------------
NONLINEARITY_FLAG_THRESHOLD = 0.10  # Tier 3, author-declared -- see module docstring


def compute_pair_correlation(x: np.ndarray, y: np.ndarray) -> dict:
    """Pearson's r and Spearman's rho over the finite-in-both pairs of
    ``x``/``y``. Returns ``n`` = 0 and NaN statistics if fewer than 3 finite
    pairs remain (never raises -- callers report ``n`` and skip/flag
    downstream)."""
    x = np.asarray(x, "float64")
    y = np.asarray(y, "float64")
    mask = np.isfinite(x) & np.isfinite(y)
    n = int(mask.sum())
    if n < 3:
        return {"n": n, "pearson_r": np.nan, "spearman_rho": np.nan}
    pearson_r = float(sp_stats.pearsonr(x[mask], y[mask])[0])
    spearman_rho = float(sp_stats.spearmanr(x[mask], y[mask])[0])
    return {"n": n, "pearson_r": pearson_r, "spearman_rho": spearman_rho}


def flag_nonlinearity(pearson_r: float, spearman_rho: float) -> bool:
    """``True`` if rank correlation is materially stronger than linear
    correlation (see module docstring, "Pearson vs Spearman") -- an
    automated proxy for a visibly non-linear/monotonic-curved scatter."""
    if np.isnan(pearson_r) or np.isnan(spearman_rho):
        return False
    return (abs(spearman_rho) - abs(pearson_r)) > NONLINEARITY_FLAG_THRESHOLD


# --------------------------------------------------------------------------
# Gate: one row per (pair, bucket, country, gcm)
# --------------------------------------------------------------------------
GATE_OUTPUT_COLUMNS = [
    "pair_label", "term_a", "term_b", "gated", "bucket", "country", "gcm",
    "n", "pearson_r", "spearman_rho", "nonlinearity_flagged", "decision_r_method",
    "decision_r", "gate_verdict", "retained_term", "excluded_term", "criterion",
]


def _models_for_pair(pair: CandidatePair, models: list[str]) -> list[str | None]:
    return list(models) if _pair_is_gcm_dependent(pair) else [None]


def run_gate(models: list[str] | None = None) -> pd.DataFrame:
    """The full correlation gate: every ``CANDIDATE_PAIRS`` entry, every
    applicable bucket, every country, every relevant GCM. Returns the long
    table described in ``GATE_OUTPUT_COLUMNS`` -- one row per (pair, bucket,
    country, gcm), plus a ``country == "pooled"`` reference-only row per
    (pair, bucket, gcm), never used in the gate verdict for any per-country
    row."""
    models = models or configured_models()
    df = sample_gate_terms(models)

    rows: list[dict] = []
    for pair in CANDIDATE_PAIRS:
        for bucket in pair.buckets:
            for model in _models_for_pair(pair, models):
                col_a = _term_column(pair.term_a, model)
                col_b = _term_column(pair.term_b, model)

                bucket_df = df[df["bucket"] == bucket]
                country_frames = {c: bucket_df[bucket_df["country"] == c] for c in COUNTRIES}
                country_frames["pooled"] = bucket_df

                for country, frame in country_frames.items():
                    if model is not None and country != "pooled":
                        verify_harmonized_grid(pair.term_a, pair.term_b, country, model)
                    stats = compute_pair_correlation(
                        frame[col_a].to_numpy("float64"), frame[col_b].to_numpy("float64"),
                    )
                    nonlinear = flag_nonlinearity(stats["pearson_r"], stats["spearman_rho"])
                    decision_method = "spearman" if nonlinear else "pearson"
                    decision_r = (
                        stats["spearman_rho"] if nonlinear else stats["pearson_r"]
                    )

                    verdict = None
                    retained = excluded = criterion = None
                    if country != "pooled":
                        if not pair.gated:
                            verdict = "report_only"
                        elif np.isnan(decision_r):
                            verdict = "insufficient_data"
                        elif abs(decision_r) >= GATE_THRESHOLD:
                            verdict = "fail"
                            retained, criterion = resolve_tie_breaker(
                                pair.term_a, pair.term_b, bucket
                            )
                            excluded = pair.term_b if retained == pair.term_a else pair.term_a
                        else:
                            verdict = "pass"

                    rows.append({
                        "pair_label": pair.label, "term_a": pair.term_a, "term_b": pair.term_b,
                        "gated": pair.gated, "bucket": bucket, "country": country,
                        "gcm": model or "not_gcm_dependent",
                        "n": stats["n"], "pearson_r": stats["pearson_r"],
                        "spearman_rho": stats["spearman_rho"],
                        "nonlinearity_flagged": nonlinear, "decision_r_method": decision_method,
                        "decision_r": decision_r, "gate_verdict": verdict,
                        "retained_term": retained, "excluded_term": excluded,
                        "criterion": criterion,
                    })

    return pd.DataFrame.from_records(rows, columns=GATE_OUTPUT_COLUMNS)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUTPUT_TABLES / "correlation_gate.csv")
    args = parser.parse_args()

    table = run_gate()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(args.out, index=False)
    logger.info("wrote %s (%d rows)", args.out, len(table))

    for _, row in table[table["country"] != "pooled"].iterrows():
        logger.info(
            "%s | %s | %s [%s]: n=%d r=%.3f (%s) -> %s%s",
            row["pair_label"], row["bucket"], row["country"], row["gcm"],
            row["n"], row["decision_r"], row["decision_r_method"], row["gate_verdict"],
            f" (retain {row['retained_term']}, criterion {row['criterion']})"
            if row["gate_verdict"] == "fail" else "",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
