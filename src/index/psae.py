"""
GEAR v3 Phase 4 -- PSAE_i (Physical Hazard Screening Index) aggregation
(``docs/rework/GEAR_v3_methodology_nature_format.md`` Section 6, Equation 2;
``docs/rework/GEAR_v3_work_plan.md`` Phase 4).

For plant i in bucket b with applicable hazard set ``H_b``::

    PSAE_i = ( sum over h in H_b of 1[RiskBand_i,h >= High] ) / |H_b|   (2)

This module consumes ``risk_bands.RiskBandTable.frame`` (Phase 3.2, already
closed for every hazard including ``wind``) -- it never recomputes
``RiskBand_{i,h}`` itself, and never touches ``risk_calculator.py``'s
``Risk_{i,h}``/``transform_term`` (Equation 1, a different, unrelated
quantity -- confirmed independent of PSAE in ``docs/DECISIONS.md``, the
Phase 3.3 entry's correction). ``H_b`` itself is read from
``hazard_scope.APPLICABLE_HAZARDS`` (Phase 3.1, closed), never re-derived
here.

--------------------------------------------------------------------------
Complete-case for missing/NaN RiskBand_i,h (author-closed, not invented
here)
--------------------------------------------------------------------------
``docs/DECISIONS.md``, "Phase 4 (PSAE) input mapping; missing/NaN RiskBand
handling in the PSAE denominator: CLOSED, complete-case" (2026-09-14): if
ANY hazard ``h`` in a plant's bucket's ``H_b`` has a missing/``None``
``risk_band`` for that plant/water_scenario, ``psae`` for that row is
``NaN`` -- never computed over a shrunk ``|H_b|`` (rejected option (a),
would make the denominator silently plant-dependent and break the
within-bucket comparability Section 9 relies on) and never silently
treated as "not High" (rejected option (c), would bias PSAE toward LOW
exactly where data coverage is worst). ``|H_b|`` (``h_b_size`` below) is
always the bucket's full nominal count from ``hazard_scope.
APPLICABLE_HAZARDS``, never shrunk per plant.

Every plant/water_scenario row is still emitted -- never silently dropped
because one hazard is missing. Two explicit fields carry the distinction a
bare ``NaN`` cannot: ``psae_complete`` (``False`` whenever any hazard was
missing) and ``missing_hazards`` (the exact hazard term(s) responsible).
``build_summary`` below reports a per-bucket, per-country coverage summary
(count/fraction of ``psae_complete=False`` rows) as a required part of this
module's report output, not an optional extra -- an output with undefined
``psae`` rows and no visible coverage summary would still be hiding the
scale of the gap from a reader.

--------------------------------------------------------------------------
Classification -- Section 6, both schemes are the SAME cut function
--------------------------------------------------------------------------
Cut points (Tier 3, author-declared, no literature precedent, stated as
such in Section 6): ``PSAE = 1.0`` -> EXTREME, ``0.5 <= PSAE < 1.0`` ->
HIGH, ``0.0 < PSAE < 0.5`` -> MEDIUM, ``PSAE = 0.0`` -> LOW.

Wind's compressed scheme (``|H_b| = 1``, Section 6: "Wind maps to {LOW,
EXTREME}") is not a second cut function -- with a single hazard, ``psae``
can only ever be exactly ``0.0`` or exactly ``1.0``, and the same four-cut
function above already maps those to LOW and EXTREME respectively. No
bucket-specific branch exists in ``classify_psae_fraction``; the
compression is a consequence of ``|H_b| = 1``'s restricted range, "derived
from the same cutoffs without introducing a new one" (Section 6, verbatim).

--------------------------------------------------------------------------
Comparability guard (work plan Phase 4.2)
--------------------------------------------------------------------------
Section 9: "PSAE is valid only within the same technology bucket... not
valid across buckets, because |H_b| differs by bucket and the index is a
within-bucket saturation fraction, not an absolute severity scale."
``assert_single_bucket``/``CrossBucketPSAEComparisonError`` is the
enforcement point work plan Phase 4.2 requires: any shared ranking/plotting
function over PSAE must call it (``rank_within_bucket`` below is the one
such function this module provides) rather than silently producing a
cross-bucket comparison. Phase 7 (visualization/reporting) is not built
yet -- this guard exists so that whenever it is, a cross-bucket PSAE plot
fails loudly instead of shipping silently.

Standalone: ``python -m src.index.psae`` from the project root. Reads
``data/outputs/tables/risk_bands.csv`` if present, else recomputes
``risk_bands.compute_risk_bands()``; writes
``data/outputs/tables/psae.csv`` and ``data/outputs/tables/psae_report.md``.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd
from numba import njit

from src.config import OUTPUT_TABLES
from src.index import hazard_scope as hs
from src.index import risk_bands as rb

logger = logging.getLogger(__name__)

PLANT_UID = rb.PLANT_UID

# RiskBand_{i,h} >= High -- the exact string tokens risk_bands.BAND_LABELS/
# WIND_BUCKET_BAND_LABELS both draw from (risk_bands.py:165-166); no
# per-bucket label-mapping decision needed, see module docstring.
HIGH_OR_ABOVE = frozenset({"High", "Extreme"})

# Section 6 classification labels, in ascending severity order.
PSAE_LABELS = ("LOW", "MEDIUM", "HIGH", "EXTREME")


class CrossBucketPSAEComparisonError(ValueError):
    """Raised when code attempts to rank/plot/compare PSAE values across
    more than one technology bucket on a single scale (Methods Section 9;
    work plan Phase 4.2). Never silently produced -- a caller must filter
    to one bucket first."""


def classify_psae_fraction(psae: float | None) -> str | None:
    """Section 6 classification of a single ``psae`` fraction. ``None``/
    ``NaN`` -> ``None`` (a complete-case-undefined plant gets no label --
    never silently classified as LOW or any other band).

    Scalar reference implementation -- kept as the public API
    (``tests/test_psae.py`` exercises it directly) and as the definition
    ``_classify_psae_codes_batch`` below is cross-checked against
    (``tests/test_psae.py::test_classify_psae_codes_batch_matches_scalar_...``).
    ``compute_psae`` itself calls the batch/Numba path, not this function,
    for its per-row classification (2026-09-15 perf fix, see
    ``compute_psae``'s docstring)."""
    if psae is None or (isinstance(psae, float) and np.isnan(psae)):
        return None
    if psae >= 1.0:
        return "EXTREME"
    if psae >= 0.5:
        return "HIGH"
    if psae > 0.0:
        return "MEDIUM"
    return "LOW"


# --------------------------------------------------------------------------
# Vectorised/Numba batch classification (2026-09-15 perf fix) -- see
# compute_psae's docstring for the measured hotspot this replaces. Integer
# codes, not strings: numba's nopython mode cannot return a Python
# str-or-None array directly, so the JIT kernel emits int8 codes
# (-1 = undefined/NaN, 0..3 = PSAE_LABELS index) and the tiny string lookup
# happens in plain, vectorised numpy just outside the kernel.
# --------------------------------------------------------------------------
@njit(cache=True)
def _classify_psae_codes_kernel(psae_values: np.ndarray) -> np.ndarray:
    n = psae_values.shape[0]
    codes = np.empty(n, dtype=np.int8)
    for i in range(n):
        v = psae_values[i]
        if np.isnan(v):
            codes[i] = -1
        elif v >= 1.0:
            codes[i] = 3
        elif v >= 0.5:
            codes[i] = 2
        elif v > 0.0:
            codes[i] = 1
        else:
            codes[i] = 0
    return codes


_PSAE_LABEL_LOOKUP = np.array(PSAE_LABELS, dtype=object)  # PSAE_LABELS defined above, module top


def classify_psae_fraction_batch(psae_values: np.ndarray) -> np.ndarray:
    """Vectorised/Numba-compiled equivalent of calling ``classify_psae_fraction``
    once per element of ``psae_values`` -- identical per-element semantics
    (NaN -> ``None``, same four cut points), an object array of ``str |
    None`` out, same shape as ``psae_values`` in."""
    psae_values = np.asarray(psae_values, dtype="float64")
    codes = _classify_psae_codes_kernel(psae_values)
    labels = np.empty(psae_values.shape[0], dtype=object)
    defined = codes >= 0
    labels[defined] = _PSAE_LABEL_LOOKUP[codes[defined]]
    labels[~defined] = None
    return labels


# --------------------------------------------------------------------------
# Aggregation
# --------------------------------------------------------------------------
PSAE_OUTPUT_COLUMNS = [
    PLANT_UID, "country", "plant_name", "bucket", "water_scenario",
    "heat_scenario", "model", "h_b_size", "n_high_or_above", "psae",
    "psae_label", "psae_complete", "missing_hazards",
]


class PSAETable(NamedTuple):
    frame: pd.DataFrame
    model: str


def compute_psae(risk_band_result: rb.RiskBandTable) -> PSAETable:
    """``PSAE_i`` (Equation 2) for every plant x water_scenario, grouped by
    the plant's own bucket, from an already-computed ``RiskBandTable.frame``
    -- never recomputes ``RiskBand_{i,h}`` itself (Phase 3.2's job).

    Complete-case for missing/NaN ``RiskBand_{i,h}`` -- see module
    docstring. Every plant/water_scenario row is emitted; a row with any
    missing hazard in its bucket's ``H_b`` gets ``psae=NaN``,
    ``psae_complete=False``, and ``missing_hazards`` naming exactly which
    hazard(s) were unavailable, never a silently dropped row and never a
    band computed over a shrunk denominator.

    --------------------------------------------------------------------
    Vectorised (2026-09-14 performance rewrite) -- no per-group Python loop
    --------------------------------------------------------------------
    Profiled before rewriting (``docs/DECISIONS.md``, "GEAR v3 psae.py
    performance fix"): the prior implementation's ~7.9s/call cost was NOT
    redundant computation or slow Python arithmetic -- ``cProfile`` on real
    production data (88,116 rows, 32,424 plant x water_scenario groups)
    showed ~95% of cumulative time inside pandas' OWN per-group machinery
    (``DataFrame._ixs``, ``fast_xs``, ``groupby.ops.__iter__``/``_chop``) --
    the cost of materialising 32,424 separate group sub-``DataFrame``s and
    indexing into them with ``.iloc``/``.iat``, not the four lines of actual
    per-group logic. The fix is therefore structural, not micro-
    optimisation: ``frame.pivot(...)`` once (one hazard-term column per
    hazard, one row per plant x water_scenario), then one boolean-matrix
    pass PER BUCKET (4 buckets, not 32,424 groups) using ``.isna()``/
    ``.isin()`` over the whole bucket's rows at once. The only remaining
    Python-level per-row work (assembling ``missing_hazards``) runs over
    plain numpy arrays, not pandas group objects -- this is what actually
    eliminates the cost, not fewer lines of code.

    --------------------------------------------------------------------
    ``psae_label`` classification (2026-09-15 perf fix) -- Numba, not a
    per-row Python loop
    --------------------------------------------------------------------
    Profiled again after the 2026-09-14 rewrite above (``docs/DECISIONS.md``,
    "GEAR v3 Phase 6 perf"): ``cProfile`` over 50 real Sobol-jitter draws
    showed ``classify_psae_fraction`` itself (called once per row, ~3.2M
    calls total) at ~11.4% of total draw time -- the one remaining pure-
    Python, non-vectorised hotspot the profile surfaced (everything else at
    or above it is pandas/numpy C-level machinery). ``psae_label`` is now
    assembled via ``classify_psae_fraction_batch`` (a Numba ``@njit``
    kernel over the whole bucket's ``psae_value`` array at once) instead of
    a ``for i in range(n): classify_psae_fraction(...)`` loop.
    ``missing_hazards`` still needs its own per-row loop (tuple assembly,
    not classification) and is unchanged.

    Correctness is unchanged: ``tests/test_psae.py`` (unmodified
    expectations, plus a new cross-check that the batch/Numba path matches
    ``classify_psae_fraction`` element-for-element) and
    ``tests/test_sensitivity_recompute.py`` (real-data, numeric-identity
    checks against this function specifically) both pass against this
    rewrite -- see ``docs/DECISIONS.md`` for the real-data verification
    this rewrite was checked against before being trusted.
    """
    frame = risk_band_result.frame
    id_cols = [PLANT_UID, "country", "plant_name", "bucket", "water_scenario",
               "heat_scenario", "model"]
    key_cols = [PLANT_UID, "water_scenario"]

    meta = (
        frame[id_cols]
        .drop_duplicates(subset=key_cols)
        .set_index(key_cols, drop=False)
    )
    wide = frame.pivot(index=key_cols, columns="hazard_term", values="risk_band")

    parts: list[pd.DataFrame] = []
    for bucket, h_b in hs.APPLICABLE_HAZARDS.items():
        bucket_keys = meta.index[meta["bucket"] == bucket]
        if len(bucket_keys) == 0:
            continue
        h_b_size = len(h_b)
        cols = list(h_b)
        # reindex columns too: a hazard in H_b that never appears anywhere
        # in `frame` (not even as a None/NaN row) becomes an all-NaN column
        # here rather than a silent KeyError or a dropped dimension.
        sub = wide.reindex(index=bucket_keys, columns=cols)

        is_missing = sub.isna().to_numpy()
        is_high = sub.isin(HIGH_OR_ABOVE).to_numpy()
        missing_count = is_missing.sum(axis=1)
        n_high = is_high.sum(axis=1)
        complete = missing_count == 0

        psae_value = np.where(complete, n_high / h_b_size, np.nan)
        n = len(bucket_keys)
        # psae_value is already NaN on every incomplete row (the np.where
        # above), so classify_psae_fraction_batch's own NaN handling makes
        # the `if complete[i] else None` branch the per-row loop used to
        # need unnecessary -- batch-classify the whole column at once.
        psae_label = classify_psae_fraction_batch(psae_value)
        # np.array([tuple(...), ...], dtype=object) would silently broadcast
        # into a 2-D array when every tuple has the same length (e.g. every
        # row complete -> every missing_hazards entry is the SAME-length
        # empty tuple `()`) -- a real numpy footgun, not a hypothetical.
        # Pre-allocated 1-D object arrays, filled by index, sidestep it.
        hazard_names = np.array(cols, dtype=object)
        missing_hazards = np.empty(n, dtype=object)
        for i in range(n):
            missing_hazards[i] = tuple(hazard_names[is_missing[i]]) if missing_count[i] else ()

        part = meta.loc[bucket_keys, id_cols].reset_index(drop=True)
        part["h_b_size"] = h_b_size
        part["n_high_or_above"] = np.where(complete, n_high, np.nan)
        part["psae"] = psae_value
        part["psae_label"] = psae_label
        part["psae_complete"] = complete
        part["missing_hazards"] = missing_hazards
        parts.append(part[PSAE_OUTPUT_COLUMNS])

    out = (
        pd.concat(parts, ignore_index=True) if parts
        else pd.DataFrame(columns=PSAE_OUTPUT_COLUMNS)
    )
    dup = int(out.duplicated(key_cols).sum())
    if dup:
        raise RuntimeError(f"compute_psae produced {dup} duplicate {key_cols} rows.")
    return PSAETable(frame=out, model=risk_band_result.model)


# --------------------------------------------------------------------------
# Comparability guard (work plan Phase 4.2)
# --------------------------------------------------------------------------
def assert_single_bucket(frame: pd.DataFrame, context: str = "") -> None:
    """Raises ``CrossBucketPSAEComparisonError`` if ``frame`` spans more
    than one ``bucket``. Call this before ranking, plotting, or otherwise
    comparing PSAE values on one shared scale -- never silently produce a
    cross-bucket comparison (Methods Section 9; work plan Phase 4.2)."""
    buckets = sorted(frame["bucket"].dropna().unique())
    if len(buckets) > 1:
        raise CrossBucketPSAEComparisonError(
            f"{context + ': ' if context else ''}PSAE is only comparable "
            f"within the same technology bucket (Methods Section 9) -- got "
            f"{buckets}. Filter to one bucket before ranking, plotting, or "
            f"comparing PSAE values on a single scale."
        )


def rank_within_bucket(psae_result: PSAETable, bucket: str, ascending: bool = False) -> pd.DataFrame:
    """PSAE-based ranking, scoped to exactly one bucket -- the only
    cross-plant PSAE comparison Methods Section 9 allows. Filters to
    ``bucket`` first, then calls ``assert_single_bucket`` as a second,
    explicit guard so a caller cannot silently rank across buckets even by
    passing an already-wrong bucket filter upstream."""
    sub = psae_result.frame[psae_result.frame["bucket"] == bucket].copy()
    assert_single_bucket(sub, context=f"rank_within_bucket({bucket!r})")
    return sub.sort_values("psae", ascending=ascending, na_position="last")


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
def build_summary(result: PSAETable) -> str:
    frame = result.frame
    lines: list[str] = ["# GEAR v3 PSAE_i -- summary\n"]

    lines.append("## H_b size per bucket\n")
    sizes = {b: len(h) for b, h in hs.APPLICABLE_HAZARDS.items()}
    lines.append(pd.Series(sizes, name="h_b_size").to_string() + "\n")

    lines.append(
        "## Coverage -- plants with psae_complete=False (missing >=1 hazard "
        "in H_b), per bucket x country\n"
    )
    coverage = (
        frame.assign(incomplete=~frame["psae_complete"])
        .groupby(["bucket", "country"])["incomplete"]
        .agg(["sum", "count"])
        .rename(columns={"sum": "incomplete_rows", "count": "total_rows"})
    )
    coverage["incomplete_fraction"] = (
        coverage["incomplete_rows"] / coverage["total_rows"]
    )
    lines.append(coverage.to_string() + "\n")

    lines.append("## PSAE label distribution per bucket (complete rows only)\n")
    complete = frame[frame["psae_complete"]]
    for bucket in sorted(hs.APPLICABLE_HAZARDS):
        sub = complete[complete["bucket"] == bucket]
        if sub.empty:
            lines.append(f"### {bucket}: no complete-case rows\n")
            continue
        dist = sub["psae_label"].value_counts().reindex(PSAE_LABELS, fill_value=0)
        lines.append(f"### {bucket} (H_b size {len(hs.APPLICABLE_HAZARDS[bucket])})\n")
        lines.append(dist.to_string() + "\n")

    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=rb.PRIMARY_GCM)
    parser.add_argument("--out-dir", type=Path, default=OUTPUT_TABLES)
    args = parser.parse_args()

    risk_band_result = rb.compute_risk_bands(args.model)
    result = compute_psae(risk_band_result)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = args.out_dir / "psae.csv"
    result.frame.to_csv(csv_path, index=False)

    report = build_summary(result)
    report_path = args.out_dir / "psae_report.md"
    report_path.write_text(report, encoding="utf-8")

    logger.info("wrote %s (%d rows)", csv_path, len(result.frame))
    logger.info("wrote %s", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
