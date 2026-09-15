"""
GEAR v3 Phase 6.3 -- scenario discovery / one-at-a-time (discrete/structural
parameters), per ``docs/rework/PHASE6_DESIGN.md`` Section 2. Kept
structurally and in its output SEPARATE from Sobol (``sobol_sensitivity.py``,
Phase 6.2) -- never folded together, per this session's explicit task
requirement. All three sub-analyses below run on already-computed or cheap
inputs (no Monte Carlo, no partial-recomputation harness needed) and are
run for real at full scale, not just validated small.

--------------------------------------------------------------------------
2.1 Hazard inclusion/exclusion OAT -- mechanism, verified by direct read
--------------------------------------------------------------------------
``psae.compute_psae`` does NOT derive its per-bucket ``H_b`` from which
hazard columns/rows happen to be present in the ``RiskBandTable.frame`` it
is given -- it reads ``hazard_scope.APPLICABLE_HAZARDS`` directly, once per
call (``for bucket, h_b in hs.APPLICABLE_HAZARDS.items(): ... h_b_size =
len(h_b) ... sub = wide.reindex(index=bucket_keys, columns=list(h_b))``).
Dropping a hazard's ROWS from ``frame`` before calling ``compute_psae``
therefore does not shrink ``|H_b|`` the way Section 2.1 wants -- it would
make ``compute_psae`` see every plant in that bucket as missing that one
hazard (``psae_complete=False`` for the entire bucket, every ``psae`` NaN),
not the "denominator shrinks by one, still computable" scenario a hazard
*removal* OAT wants to test. The correct lever is ``APPLICABLE_HAZARDS``
itself: temporarily override the one bucket's tuple to drop the target
hazard (``_hazard_removed`` context manager below), then call the real,
untouched ``psae.compute_psae`` -- ``h_b_size``/``cols``/the boolean-matrix
pass all follow from the (temporarily) smaller ``H_b`` automatically, no
``psae.py`` logic reimplemented. Restored in a ``finally`` block; this
module runs single-threaded/serially (cheap, no need for the
``multiprocessing`` harness Phase 6.2 needs), so the mutate-then-restore
window never overlaps a concurrent read of the same global.

--------------------------------------------------------------------------
2.3 Correlation-gate threshold sweep -- decision logic only, not r/rho
--------------------------------------------------------------------------
Post-processes the already-computed ``data/outputs/tables/correlation_gate.csv``
(``decision_r`` per gated pair/bucket/country/gcm cell) at a swept set of
thresholds, re-running only ``correlation_gate.py``'s pass/fail comparison
(``abs(decision_r) >= threshold``) and, for a flip, its real
``resolve_tie_breaker`` -- never recomputes Pearson/Spearman.

--------------------------------------------------------------------------
2.2 PSAE cut-point OAT
--------------------------------------------------------------------------
Re-classifies the same underlying ``psae`` fractions from the real, closed
baseline (``psae.compute_psae``) at shifted 0.5 boundaries (0.4, 0.6),
using ``psae.classify_psae_fraction``'s own cut logic, adapted (not
reimplemented from scratch -- the four-way branch is the same shape, the
literal ``0.5`` is the one thing this module needs to vary, which the
production function does not expose as a parameter). Inherently coarse per
``PHASE6_DESIGN.md`` Section 2.2: with ``|H_b|`` in {1, 3}, the achievable
``psae`` values are ``{0, 1/|H_b|, ..., 1}``, so most shifts land inside the
same bucket as the 0.5 baseline and only some create a different discrete
classification outcome.

Standalone: no CLI. ``run_all`` is the entry point.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

import numpy as np
import pandas as pd

from src.config import COUNTRIES, OUTPUT_TABLES
from src.index import correlation_gate as cg
from src.index import hazard_scope as hs
from src.index import psae
from src.index import risk_bands as rb
from src.index import risk_calculator as rc

logger = logging.getLogger(__name__)

PSAE_LABELS = psae.PSAE_LABELS  # ("LOW", "MEDIUM", "HIGH", "EXTREME")


# --------------------------------------------------------------------------
# 2.1 Hazard inclusion/exclusion OAT
# --------------------------------------------------------------------------
MEANINGFUL_REMOVALS: dict[str, tuple[str, ...]] = {
    bucket: hazards
    for bucket, hazards in hs.APPLICABLE_HAZARDS.items()
    if len(hazards) > 1  # Wind (|H_b|=1) excluded -- would empty H_b, structural error
}


@contextmanager
def _hazard_removed(bucket: str, hazard: str):
    """Temporarily overrides ``hazard_scope.APPLICABLE_HAZARDS[bucket]`` to
    drop ``hazard`` -- see module docstring for why this, not row-dropping,
    is the mechanism that actually shrinks PSAE's ``|H_b|`` denominator."""
    original = hs.APPLICABLE_HAZARDS[bucket]
    assert hazard in original, f"{hazard!r} not in APPLICABLE_HAZARDS[{bucket!r}] = {original!r}"
    reduced = tuple(h for h in original if h != hazard)
    hs.APPLICABLE_HAZARDS[bucket] = reduced
    try:
        yield reduced
    finally:
        hs.APPLICABLE_HAZARDS[bucket] = original


def _capacity_by_plant() -> pd.Series:
    """``plant_uid`` -> ``capacity_mw``, every country pooled -- PSAE's
    output carries no capacity column (``psae.PSAE_OUTPUT_COLUMNS``), so
    capacity-weighted distributions need it merged in from the plant table
    ``risk_bands``/``risk_calculator`` both load from."""
    parts = [rc.load_plants(c)[[rc.PLANT_UID, "capacity_mw"]] for c in COUNTRIES]
    cap = pd.concat(parts, ignore_index=True)
    dup = int(cap.duplicated(rc.PLANT_UID).sum())
    if dup:
        raise RuntimeError(f"_capacity_by_plant: {dup} duplicate plant_uid across countries.")
    return cap.set_index(rc.PLANT_UID)["capacity_mw"]


def _capacity_label_distribution(psae_frame: pd.DataFrame, cap: pd.Series) -> pd.DataFrame:
    """Fraction of CAPACITY (not plant count) in each PSAE label, per
    bucket x country, complete-case rows only (psae_complete=False ->
    excluded from the numerator AND denominator here -- this is a
    distribution over classified capacity, not a coverage statistic;
    ``build_summary``-style coverage is reported separately, see
    ``hazard_removal_report``)."""
    complete = psae_frame[psae_frame["psae_complete"]].copy()
    complete["capacity_mw"] = complete[rc.PLANT_UID].map(cap)
    if complete["capacity_mw"].isna().any():
        missing = int(complete["capacity_mw"].isna().sum())
        raise RuntimeError(f"_capacity_label_distribution: {missing} rows have no capacity_mw match.")

    out = []
    for (bucket, country), sub in complete.groupby(["bucket", "country"]):
        total = sub["capacity_mw"].sum()
        for label in PSAE_LABELS:
            frac = sub.loc[sub["psae_label"] == label, "capacity_mw"].sum() / total if total else float("nan")
            out.append({"bucket": bucket, "country": country, "psae_label": label, "capacity_fraction": frac})
    return pd.DataFrame(out)


def hazard_removal_oat(model: str = rb.PRIMARY_GCM) -> pd.DataFrame:
    """Section 2.1, full run (not validation-scale -- cheap). One row per
    (bucket, removed_hazard, country, psae_label): baseline capacity
    fraction, removal capacity fraction, and the shift. Baseline and every
    removal are computed against the SAME real ``RiskBandTable`` (one
    ``compute_risk_bands`` call, reused -- only ``APPLICABLE_HAZARDS`` is
    perturbed per removal, not the underlying raw hazard sampling)."""
    band_table = rb.compute_risk_bands(model)
    cap = _capacity_by_plant()

    baseline_psae = psae.compute_psae(band_table).frame
    baseline_dist = _capacity_label_distribution(baseline_psae, cap)
    baseline_dist = baseline_dist.rename(columns={"capacity_fraction": "baseline_fraction"})

    rows = []
    for bucket, hazards in MEANINGFUL_REMOVALS.items():
        for hazard in hazards:
            with _hazard_removed(bucket, hazard) as reduced_h_b:
                removal_psae = psae.compute_psae(band_table).frame
                removal_psae = removal_psae[removal_psae["bucket"] == bucket]
                removal_dist = _capacity_label_distribution(removal_psae, cap)
                removal_dist = removal_dist.rename(columns={"capacity_fraction": "removal_fraction"})

            merged = baseline_dist[baseline_dist["bucket"] == bucket].merge(
                removal_dist, on=["bucket", "country", "psae_label"], how="left",
            )
            merged["removed_hazard"] = hazard
            merged["h_b_baseline_size"] = len(hazards)
            merged["h_b_removal_size"] = len(reduced_h_b)
            merged["shift"] = merged["removal_fraction"] - merged["baseline_fraction"]
            rows.append(merged)

    return pd.concat(rows, ignore_index=True)[[
        "bucket", "removed_hazard", "country", "psae_label",
        "h_b_baseline_size", "h_b_removal_size",
        "baseline_fraction", "removal_fraction", "shift",
    ]]


# --------------------------------------------------------------------------
# 2.3 Correlation-gate threshold sweep
# --------------------------------------------------------------------------
SWEPT_THRESHOLDS: tuple[float, ...] = (0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90)


def correlation_gate_sweep(csv_path=None) -> pd.DataFrame:
    """Section 2.3 (+ 2.4's tie-breaker sub-finding folded in, per
    ``PHASE6_DESIGN.md`` Section 2.4's own instruction not to report it as
    an independent test). Re-applies ``abs(decision_r) >= threshold`` to the
    real, already-computed ``decision_r`` column at each swept threshold --
    never recomputes Pearson/Spearman. Reports every gated (pair, bucket,
    country, gcm) cell's verdict at every threshold, flags flips relative to
    the production 0.80 threshold, and calls the real
    ``correlation_gate.resolve_tie_breaker`` for the retained/excluded term
    on every cell that fails at ANY swept threshold (not just flips), so a
    reader can see the tie-breaker outcome wherever it would matter."""
    csv_path = csv_path or (OUTPUT_TABLES / "correlation_gate.csv")
    if not csv_path.exists():
        raise FileNotFoundError(
            f"correlation_gate_sweep: {csv_path} not found -- run "
            f"`python -m src.index.correlation_gate` first, or check "
            f"correlation_gate.py's own --out default if the path moved."
        )
    table = pd.read_csv(csv_path)
    gated = table[table["gated"] == True].copy()  # noqa: E712 -- pandas bool column, not `is True`

    rows = []
    for _, r in gated.iterrows():
        decision_r = r["decision_r"]
        for threshold in SWEPT_THRESHOLDS:
            if pd.isna(decision_r):
                verdict = "insufficient_data"
            elif abs(decision_r) >= threshold:
                verdict = "fail"
            else:
                verdict = "pass"

            retained = excluded = criterion = None
            if verdict == "fail":
                retained, criterion = cg.resolve_tie_breaker(r["term_a"], r["term_b"], r["bucket"])
                excluded = r["term_b"] if retained == r["term_a"] else r["term_a"]

            rows.append({
                "pair_label": r["pair_label"], "term_a": r["term_a"], "term_b": r["term_b"],
                "bucket": r["bucket"], "country": r["country"], "gcm": r["gcm"],
                "decision_r": decision_r, "threshold": threshold, "verdict": verdict,
                "retained_term": retained, "excluded_term": excluded, "criterion": criterion,
                "baseline_verdict": r["gate_verdict"],
            })

    out = pd.DataFrame(rows)
    out["flipped_vs_baseline"] = (
        (out["threshold"] != cg.GATE_THRESHOLD) & (out["verdict"] != out["baseline_verdict"])
    )
    return out


# --------------------------------------------------------------------------
# 2.2 PSAE cut-point OAT
# --------------------------------------------------------------------------
SHIFTED_CUTS: tuple[float, ...] = (0.4, 0.5, 0.6)  # 0.5 is the baseline, included for comparison


def _classify_at_cut(psae_value: float, cut: float) -> str | None:
    """Same four-way shape as ``psae.classify_psae_fraction`` -- the 1.0/0.0
    EXTREME/LOW boundaries are untouched (Section 2.2: degenerate, not
    meaningfully perturbable), only the internal MEDIUM/HIGH boundary
    (production ``0.5``, swept here) moves. Not a reimplementation of new
    logic, an adaptation exposing the one literal the production function
    does not parameterize."""
    if psae_value is None or (isinstance(psae_value, float) and np.isnan(psae_value)):
        return None
    if psae_value >= 1.0:
        return "EXTREME"
    if psae_value >= cut:
        return "HIGH"
    if psae_value > 0.0:
        return "MEDIUM"
    return "LOW"


def psae_cutpoint_oat(model: str = rb.PRIMARY_GCM) -> pd.DataFrame:
    """Section 2.2, full run against the real, closed baseline PSAE table.
    One row per (bucket, h_b_size, achievable psae value, shifted cut):
    the classification at that cut vs. the production (cut=0.5)
    classification, and whether it differs."""
    band_table = rb.compute_risk_bands(model)
    baseline = psae.compute_psae(band_table).frame
    complete = baseline[baseline["psae_complete"]]

    rows = []
    for h_b_size, sub in complete.groupby("h_b_size"):
        achievable = sorted(sub["psae"].unique())
        for value in achievable:
            for cut in SHIFTED_CUTS:
                label = _classify_at_cut(value, cut)
                baseline_label = _classify_at_cut(value, 0.5)
                rows.append({
                    "h_b_size": int(h_b_size), "psae_value": value, "cut": cut,
                    "label_at_cut": label, "baseline_label": baseline_label,
                    "differs_from_baseline": label != baseline_label,
                })
    return pd.DataFrame(rows).drop_duplicates(
        subset=["h_b_size", "psae_value", "cut"]
    ).sort_values(["h_b_size", "psae_value", "cut"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------
def run_all(model: str = rb.PRIMARY_GCM) -> dict[str, pd.DataFrame]:
    """All three sub-analyses, real, full-scale (cheap -- no Monte Carlo).
    Kept as three separate DataFrames in the return dict, never merged into
    one table, per this module's own "kept structurally separate" design."""
    return {
        "hazard_removal": hazard_removal_oat(model),
        "correlation_gate_sweep": correlation_gate_sweep(),
        "psae_cutpoint": psae_cutpoint_oat(model),
    }
