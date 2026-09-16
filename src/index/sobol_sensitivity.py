"""
GEAR v3 Phase 6.2 -- SALib Sobol driver over the D=13 continuous-parameter
problem (``docs/rework/PHASE6_DESIGN.md`` Section 1, ``docs/DECISIONS.md``
"GEAR v3 Phase 6" entries, and the session's D=13 reconciliation -- see this
module's own docstring below for the reconciliation itself).

--------------------------------------------------------------------------
D=13, not the stale D=6 floor
--------------------------------------------------------------------------
``docs/DECISIONS.md``'s "Phase 6 (Sensitivity/uncertainty) input mapping"
entry (item 4c) left the RiskBand percentile-cut Sobol dimension grouping
open, noting it changes ``D`` "from 2 to 6 for that family alone" depending
on whether the grouping is one-per-percentile-family or one-per-hazard. The
author has since closed that (session decision, not re-derived here):
**one dimension per hazard NAME** (not per percentile-family group), which
resolves to exactly 6 dimensions for the percentile-cut family --
``spei``, ``precip``, ``heat``, ``sv``, ``iv`` (all
``risk_bands.GENERIC_TIER3_PERCENTILES``) and ``wind`` (the lone
``risk_bands.WIND_SOLAR_TIER3_PERCENTILES`` member, solar-bucket only for
percentile purposes -- ``wind/wind`` is Tier 1 binary, not percentile, and
carries no Sobol dimension). Combined with the 7 already-confirmed
continuous dimensions (3 literature-backed age_factor rates + 4 Tier-3
±20%-default parameters -- ``docs/DECISIONS.md`` items 1, 4a, 4b), that is
``7 + 6 = 13``, not the "D=6" floor an earlier note in this project's
history carried -- that note predates the later closures re-adding solar
retention and the coal-overhaul pair as Sobol candidates (both were
initially flagged, not yet closed, when D=6 was last written down) and
predates the per-hazard (not per-family) percentile grouping decision.
``PARAM_NAMES``/``PARAM_BOUNDS`` below are this reconciliation made
concrete; every bound was cross-checked directly against the current code
(``age_factor.py``, ``normalization.py``, ``risk_bands.py``) before being
written here -- see ``docs/DECISIONS.md``'s new Phase 6 D=13 entry for the
line-by-line verification.

--------------------------------------------------------------------------
The one parameter ``sensitivity_recompute.py`` cannot perturb through its
existing interface -- ``upper_tail_padding_fraction``
--------------------------------------------------------------------------
``risk_calculator.transform_term`` reads its tail-padding fraction from a
MODULE-LEVEL constant (``risk_calculator.TLOG_UPPER_TAIL_PADDING_FRACTION``,
deliberately kept independent of ``normalization.UPPER_TAIL_PADDING_FRACTION``
per that module's own comment, "reverse import would be circular" --
both are 0.05 at nominal), not a function parameter, and
``sensitivity_recompute.recompute_risk_by_hazard`` has no ``rate_overrides``/
``bounds`` plumbing that reaches it (unlike every other Section 1.1 rate,
which ``retention_vector`` accepts directly). Rather than modify
``sensitivity_recompute.py`` (out of scope -- its functions are already
tested and this module must only call it), this module perturbs the
padding fraction the same way the retired ``monte_carlo.py`` was rejected
for perturbing ``age_factor``'s rates: monkeypatch the module global for
the duration of exactly one draw's call, then restore it. Unlike the
``age_factor`` case, this is safe here: it is ONE scalar read inside ONE
synchronous, single-threaded call
(``recompute_risk_by_hazard``, no re-entrancy, no concurrent draws within
one worker process under ``multiprocessing.Pool``'s spawn model), always
restored in a ``finally`` block before the worker's next draw. The call is
also forced onto ``recompute_risk_by_hazard``'s live (non-cached) path by
passing a bounds dict that is a fresh shallow copy of ``rc.FROZEN_BOUNDS``
(``dict(rc.FROZEN_BOUNDS)``, never ``is rc.FROZEN_BOUNDS``) -- otherwise
``recompute_risk_by_hazard``'s ``Hazard_i,h`` cache (precomputed once at
the nominal padding value) would silently short-circuit the perturbation.
See ``_sobol_worker_run_draw`` below.

--------------------------------------------------------------------------
Why ``rng_utils.phase6_rng`` is NOT used here
--------------------------------------------------------------------------
SALib's own Sobol sampler (``SALib.sample.sobol.sample``) generates its own
low-discrepancy design matrix via its own ``seed`` argument -- it does not
draw from ``numpy.random.Generator`` at all, so there is nothing to plug
``phase6_rng`` into here. This is a genuine, deliberate asymmetry with
``general_mc.py`` (Phase 6.1), not an oversight -- see this module's
sibling module for where ``phase6_rng`` actually is used. Every one of
this module's 13 parameters is a genuinely global quantity (an age_factor
rate, a percentile shift) that applies identically across every country and
water_scenario within one Saltelli sample, by construction of
``retention_vector``/``recompute_risk_bands`` -- there is no
country/scenario-specific draw to key a stream to.

--------------------------------------------------------------------------
``calc_second_order`` and the evaluation-count formula -- a correction to
the budget already quoted upstream
--------------------------------------------------------------------------
The evaluation count ``N_0 * (2D + 2)`` quoted ahead of this module's
implementation assumes ``calc_second_order=True``. This module runs with
``calc_second_order=False`` per the task's own instruction ("do not compute
second-order indices... keep it False") -- but SALib's actual Saltelli
scheme under ``calc_second_order=False`` produces ``N_0 * (D + 2)``
evaluations, not ``N_0 * (2D + 2)`` (confirmed empirically in this module's
own dev: at ``D=13``, ``N_0=8``, ``calc_second_order=False`` yields exactly
120 rows == ``8 * 15`` == ``8 * (13 + 2)``, not 224). This roughly HALVES
the previously quoted full-scale budget (``N_0=1024`` -> ``1024 * 15 =
15,360`` evaluations, ~1.7 hours at 0.40s/draw, not ``1024 * 28 = 28,672``
/ ~3.2 hours) -- flagged here explicitly rather than silently carrying the
stale formula forward; see this session's ``docs/DECISIONS.md`` entry.

Standalone: no ``main()`` / CLI. ``run_validation`` below is the entry
point a caller (or a one-off script) uses to execute a real, small-scale
end-to-end run.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import time

import numpy as np
import pandas as pd
from SALib.analyze import sobol as salib_analyze
from SALib.sample import sobol as salib_sample

from src.index import psae
from src.index import risk_bands as rb
from src.index import risk_calculator as rc
from src.index import sensitivity_recompute as sr

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# The D=13 problem -- see module docstring for the reconciliation.
# --------------------------------------------------------------------------
PARAM_NAMES = [
    "coal_decay_rate",              # 1, literature (Sagaf 2020)
    "wind_relative_rate",           # 2, literature (Olauson et al. 2017)
    "hydro_retention_rate",         # 3, literature (Turner et al. 2024)
    "solar_retention_rate",         # 4, Tier 3, +-20% default
    "coal_overhaul_cycle_years",    # 5, Tier 3, +-20% default
    "coal_overhaul_recovery",       # 6, Tier 3, +-20% default
    "upper_tail_padding_fraction",  # 7, Tier 3, +-20% default
    "spei_percentile_shift",        # 8, Tier 3, rank-shift design
    "precip_percentile_shift",      # 9
    "heat_percentile_shift",        # 10
    "sv_percentile_shift",          # 11
    "iv_percentile_shift",          # 12
    "wind_percentile_shift",        # 13, asymmetric near-ceiling clip
]

PARAM_BOUNDS = [
    [0.0019, 0.0044],
    [0.0030, 0.0050],
    [0.0050, 0.0060],
    [0.0056, 0.0084],
    [4.0, 6.0],
    [0.56, 0.84],
    [0.04, 0.06],
    [-5.0, 5.0],
    [-5.0, 5.0],
    [-5.0, 5.0],
    [-5.0, 5.0],
    [-5.0, 5.0],
    [-5.0, 5.0],
]

PROBLEM: dict = {
    "num_vars": len(PARAM_NAMES),
    "names": PARAM_NAMES,
    "bounds": PARAM_BOUNDS,
}
assert len(PARAM_NAMES) == 13 == len(PARAM_BOUNDS)

# hazard NAME -> every (hazard, bucket) percentile_overrides key that shares
# it (decision 2, PHASE6_DESIGN.md's own grouping note -- precip/heat are
# pooled across their buckets' Tier 3 cuts, see risk_bands._PRECIP_NOTE and
# the heat/solar note).
_HAZARD_NAME_TO_KEYS: dict[str, tuple[tuple[str, str], ...]] = {
    "spei": (("spei", "hydro"),),
    "precip": (("precip", "hydro"), ("precip", "thermal"), ("precip", "solar")),
    "heat": (("heat", "thermal"), ("heat", "solar")),
    "sv": (("sv", "hydro"),),
    "iv": (("iv", "hydro"),),
    "wind": (("wind", "solar"),),
}
assert set(_HAZARD_NAME_TO_KEYS) == {"spei", "precip", "heat", "sv", "iv", "wind"}

# risk_bands.THRESHOLD_REGISTRY keys covered by percentile shifts above must
# be exactly the percentile-kind entries -- guards against a future
# THRESHOLD_REGISTRY edit silently leaving a (hazard, bucket) pair unshifted.
_PERCENTILE_KEYS = {
    k for k, spec in rb.THRESHOLD_REGISTRY.items() if spec.kind == "percentile"
}
_COVERED_KEYS = {k for keys in _HAZARD_NAME_TO_KEYS.values() for k in keys}
assert _PERCENTILE_KEYS == _COVERED_KEYS, (
    f"sobol_sensitivity._HAZARD_NAME_TO_KEYS out of sync with "
    f"risk_bands.THRESHOLD_REGISTRY's percentile-kind entries: "
    f"registry has {sorted(_PERCENTILE_KEYS)}, this module covers "
    f"{sorted(_COVERED_KEYS)}."
)

# Wind/solar's near-ceiling clip (decision 13, PHASE6_DESIGN.md Section 1.2):
# no shifted percentile may exceed this. WIND_SOLAR_TIER3_PERCENTILES tops
# out at P99 (rb.WIND_SOLAR_TIER3_PERCENTILES == (75.0, 90.0, 95.0, 99.0)),
# so a positive shift is capped at 0.5 pts; a negative shift needs no
# ceiling clip (the family's lowest member, P75, has ample room below).
WIND_PERCENTILE_CEILING = 99.5


def _wind_effective_shift(shift: float, base_percentiles: tuple[float, ...]) -> float:
    if shift <= 0.0:
        return shift
    room = WIND_PERCENTILE_CEILING - max(base_percentiles)
    return min(shift, room)


def row_to_params(row: np.ndarray) -> tuple[dict, dict, float]:
    """One Saltelli sample row (length 13, ``PARAM_NAMES`` order) ->
    ``(rate_overrides, percentile_overrides, padding_fraction)`` --
    the exact shapes ``sensitivity_recompute.recompute_risk_by_hazard``/
    ``recompute_risk_bands`` accept, plus the one parameter that goes
    through the monkeypatch path (see module docstring)."""
    vals = dict(zip(PARAM_NAMES, row))

    rate_overrides = {
        "coal_decay_rate": float(vals["coal_decay_rate"]),
        "wind_relative_rate": float(vals["wind_relative_rate"]),
        "hydro_retention_rate": float(vals["hydro_retention_rate"]),
        "solar_retention_rate": float(vals["solar_retention_rate"]),
        "coal_overhaul_cycle_years": float(vals["coal_overhaul_cycle_years"]),
        "coal_overhaul_recovery": float(vals["coal_overhaul_recovery"]),
    }

    percentile_overrides: dict[tuple[str, str], tuple[float, ...]] = {}
    for hazard_name, keys in _HAZARD_NAME_TO_KEYS.items():
        shift = float(vals[f"{hazard_name}_percentile_shift"])
        for key in keys:
            base = rb.THRESHOLD_REGISTRY[key].percentiles
            shift_eff = _wind_effective_shift(shift, base) if hazard_name == "wind" else shift
            percentile_overrides[key] = tuple(
                min(max(p + shift_eff, 0.0), 100.0) for p in base
            )

    padding_fraction = float(vals["upper_tail_padding_fraction"])
    return rate_overrides, percentile_overrides, padding_fraction


def sample_problem(n0: int, *, calc_second_order: bool = False, seed: int | None = None) -> np.ndarray:
    """SALib Saltelli sample over ``PROBLEM`` -- ``n0 * (D + 2)`` rows under
    ``calc_second_order=False`` (see module docstring's evaluation-count
    correction)."""
    return salib_sample.sample(PROBLEM, n0, calc_second_order=calc_second_order, seed=seed)


# --------------------------------------------------------------------------
# Parallel draw execution -- own worker (task requirement: do not reuse
# sensitivity_recompute._worker_run_draw, which is an explicitly-labeled
# throughput placeholder with a fixed jitter-only reduction). Reuses
# sensitivity_recompute._init_worker as the Pool initializer (same
# pre/models sharing pattern -- see that module's docstring), not
# reimplemented here.
# --------------------------------------------------------------------------
def _nanaverage(values: np.ndarray, weights: np.ndarray) -> float:
    """Capacity-weighted mean, skipping NaN ``values`` rows (and their
    weight) entirely -- ``risk_i_h`` carries real, production-confirmed NaN
    rows (sv/iv/ws data gaps at specific plant locations), and a plain
    ``np.average`` (no ``skipna`` support) would otherwise propagate a
    single NaN row into the whole summary statistic."""
    mask = ~np.isnan(values)
    if not mask.any():
        return float("nan")
    return float(np.average(values[mask], weights=weights[mask]))


def _sobol_worker_run_draw(row: np.ndarray) -> dict:
    """One Saltelli sample row, executed inside a worker process. Returns
    BOTH required output statistics (task requirement -- never just one):
    capacity-weighted mean Risk_i,h and mean PSAE_i (psae_complete=False
    rows NaN-masked per decision 3, never dropped), each at two
    granularities -- overall (pooled across countries and both GCMs) and
    per-country -- so a caller can choose which to feed into SALib's
    ``analyze`` without re-running draws. Overall is this module's primary,
    Sobol-analyzed statistic (see ``run_validation``); per-country is
    carried through as diagnostic detail only, not separately Sobol-analyzed
    at validation scale (report says so explicitly)."""
    rate_overrides, percentile_overrides, padding_fraction = row_to_params(row)
    pre = sr._worker_pre
    models = sr._worker_models

    original_pad = rc.TLOG_UPPER_TAIL_PADDING_FRACTION
    rc.TLOG_UPPER_TAIL_PADDING_FRACTION = padding_fraction
    try:
        risk_frames = []
        psae_frames = []
        for model in models:
            risk_df = sr.recompute_risk_by_hazard(
                pre, model,
                bounds=dict(rc.FROZEN_BOUNDS),  # fresh dict object -> forces the live (non-cached) path
                rate_overrides=rate_overrides,
            )
            risk_frames.append(risk_df)
            band_table = sr.recompute_risk_bands(pre, model, percentile_overrides=percentile_overrides)
            psae_frames.append(psae.compute_psae(band_table).frame)
    finally:
        rc.TLOG_UPPER_TAIL_PADDING_FRACTION = original_pad

    risk_all = pd.concat(risk_frames, ignore_index=True)
    psae_all = pd.concat(psae_frames, ignore_index=True)

    # risk_i_h carries real NaN rows (e.g. sv/iv/ws data gaps at some plant
    # locations -- confirmed against production data, not a Sobol-harness
    # artifact) -- a capacity-weighted mean must skip them rather than
    # propagate to a single NaN summary statistic (np.average does not
    # skipna). Weight is the row's own capacity_mw, unaffected by which
    # OTHER rows are missing.
    risk_overall = float(_nanaverage(
        risk_all["risk_i_h"].to_numpy("float64"),
        risk_all["capacity_mw"].to_numpy("float64"),
    ))
    risk_by_country = {
        str(c): float(_nanaverage(sub["risk_i_h"].to_numpy("float64"), sub["capacity_mw"].to_numpy("float64")))
        for c, sub in risk_all.groupby("country")
    }
    # (country, bucket) stratification -- additive, for run_validation_stratified
    # only (EXPERIMENTAL, see that function's docstring). risk_all/psae_all both
    # already carry a "bucket" column per row, so this is the same groupby
    # pattern as risk_by_country, one level finer, at no extra draw cost.
    risk_by_country_bucket = {
        f"{c}|{b}": float(_nanaverage(sub["risk_i_h"].to_numpy("float64"), sub["capacity_mw"].to_numpy("float64")))
        for (c, b), sub in risk_all.groupby(["country", "bucket"])
    }

    psae_overall = float(psae_all["psae"].mean(skipna=True))
    psae_by_country = {
        str(c): float(v) for c, v in psae_all.groupby("country")["psae"].mean().items()
    }
    psae_by_country_bucket = {
        f"{c}|{b}": float(v)
        for (c, b), v in psae_all.groupby(["country", "bucket"])["psae"].mean(skipna=True).items()
    }

    return {
        "risk_mean_overall": risk_overall,
        "risk_mean_by_country": risk_by_country,
        "risk_mean_by_country_bucket": risk_by_country_bucket,
        "psae_mean_overall": psae_overall,
        "psae_mean_by_country": psae_by_country,
        "psae_mean_by_country_bucket": psae_by_country_bucket,
        "psae_n_complete": int(psae_all["psae_complete"].sum()),
        "psae_n_total": int(len(psae_all)),
    }


def run_sobol_draws_parallel(
    pre: sr.PrecomputedInputs,
    rows: np.ndarray,
    *,
    models: list[str] | None = None,
    n_workers: int | None = None,
) -> list[dict]:
    """``rows`` (a Saltelli sample, ``sample_problem``'s output) ->
    one ``_sobol_worker_run_draw`` result per row, across a
    ``multiprocessing.Pool``. Mirrors
    ``sensitivity_recompute.run_draws_parallel``'s BLAS-thread-pinning and
    ``spawn``-safety handling exactly (see that function's docstring for the
    platform analysis) -- not duplicated reasoning, just the same pattern
    applied with this module's own worker function."""
    n_workers = n_workers or mp.cpu_count()
    models = models or rc.configured_models()
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ.setdefault(var, "1")
    ctx = mp.get_context()
    with ctx.Pool(processes=n_workers, initializer=sr._init_worker, initargs=(pre, models)) as pool:
        return pool.map(_sobol_worker_run_draw, [row for row in rows])


# --------------------------------------------------------------------------
# End-to-end validation run
# --------------------------------------------------------------------------
def run_validation(
    n0: int,
    *,
    pre: sr.PrecomputedInputs | None = None,
    n_workers: int | None = None,
    seed: int = 20260915,
) -> dict:
    """Sample -> parallel recompute -> SALib analyze, for both output
    statistics (Risk_i,h, PSAE_i), at ``n0``. Real wall-clock timing, no
    projection. ``pre`` may be passed in to reuse an already-built
    ``PrecomputedInputs`` (its raster read is the expensive, ~30-60s
    fixed cost this function does not want to pay twice across repeated
    calls at increasing ``n0``)."""
    if pre is None:
        pre = sr.precompute()

    t_sample0 = time.perf_counter()
    rows = sample_problem(n0, calc_second_order=False, seed=seed)
    t_sample = time.perf_counter() - t_sample0
    n_evals = rows.shape[0]
    expected = n0 * (len(PARAM_NAMES) + 2)
    assert n_evals == expected, f"unexpected evaluation count: got {n_evals}, expected {expected}"

    t_run0 = time.perf_counter()
    results = run_sobol_draws_parallel(pre, rows, n_workers=n_workers)
    t_run = time.perf_counter() - t_run0

    Y_risk = np.array([r["risk_mean_overall"] for r in results], dtype="float64")
    Y_psae = np.array([r["psae_mean_overall"] for r in results], dtype="float64")

    t_analyze0 = time.perf_counter()
    sobol_risk = salib_analyze.analyze(PROBLEM, Y_risk, calc_second_order=False, seed=seed)
    sobol_psae = salib_analyze.analyze(PROBLEM, Y_psae, calc_second_order=False, seed=seed)
    t_analyze = time.perf_counter() - t_analyze0

    total_complete = sum(r["psae_n_complete"] for r in results)
    total_rows = sum(r["psae_n_total"] for r in results)

    return {
        "n0": n0,
        "n_evals": n_evals,
        "n_workers": n_workers or mp.cpu_count(),
        "sample_s": t_sample,
        "run_s": t_run,
        "analyze_s": t_analyze,
        "total_s": t_sample + t_run + t_analyze,
        "s_per_draw": t_run / n_evals,
        "Y_risk": Y_risk,
        "Y_psae": Y_psae,
        "sobol_risk": sobol_risk,
        "sobol_psae": sobol_psae,
        "psae_coverage_fraction": total_complete / total_rows if total_rows else float("nan"),
        "psae_n_complete_total": total_complete,
        "psae_n_total": total_rows,
    }


# --------------------------------------------------------------------------
# Country x bucket stratified analysis -- EXPERIMENTAL
# --------------------------------------------------------------------------
def run_validation_stratified(
    n0: int,
    *,
    pre: sr.PrecomputedInputs | None = None,
    n_workers: int | None = None,
    seed: int = 20260915,
) -> dict:
    """Same sample/draws as ``run_validation`` (one Saltelli design, one pass
    of ``run_sobol_draws_parallel`` -- no extra evaluations), but additionally
    runs SALib ``analyze`` per (country, bucket) stratum using the per-draw
    breakdown ``_sobol_worker_run_draw`` already returns. ``analyze`` itself
    is a cheap post-processing step (seconds, not the draw cost), so this
    does not roughly double the run_validation wall-clock the way a second
    independent Sobol run would.

    A stratum is skipped (absent from the returned dicts) if any draw is
    missing it (e.g. a hazard not present at all for a bucket in a given
    country) -- SALib's ``analyze`` cannot handle NaN in its ``Y`` array, and
    silently imputing a value would fabricate a Sobol index for data that
    was never actually sampled.

    EXPERIMENTAL: this stratification (by hazard_scope bucket, one Sobol
    analysis per country) was not part of the closed Phase 6 methodology in
    ``docs/DECISIONS.md`` -- the closed run analyzes only the overall pooled
    statistic and reports per-country as diagnostic detail (see
    ``_sobol_worker_run_draw``'s docstring). Treat any interpretation of
    these per-stratum indices as provisional pending explicit author review;
    do not cite them as part of the closed Phase 6.2 result without that
    review.
    """
    if pre is None:
        pre = sr.precompute()

    rows = sample_problem(n0, calc_second_order=False, seed=seed)
    n_evals = rows.shape[0]
    expected = n0 * (len(PARAM_NAMES) + 2)
    assert n_evals == expected, f"unexpected evaluation count: got {n_evals}, expected {expected}"

    t0 = time.perf_counter()
    results = run_sobol_draws_parallel(pre, rows, n_workers=n_workers)
    elapsed = time.perf_counter() - t0

    strata = sorted({k for r in results for k in r["risk_mean_by_country_bucket"]})
    sobol_risk_by_stratum: dict[str, dict] = {}
    sobol_psae_by_stratum: dict[str, dict] = {}
    skipped_strata: list[str] = []
    for stratum in strata:
        y_risk = np.array([r["risk_mean_by_country_bucket"].get(stratum, np.nan) for r in results], dtype="float64")
        y_psae = np.array([r["psae_mean_by_country_bucket"].get(stratum, np.nan) for r in results], dtype="float64")
        if np.isnan(y_risk).any() or np.isnan(y_psae).any():
            skipped_strata.append(stratum)
            continue
        sobol_risk_by_stratum[stratum] = salib_analyze.analyze(PROBLEM, y_risk, calc_second_order=False, seed=seed)
        sobol_psae_by_stratum[stratum] = salib_analyze.analyze(PROBLEM, y_psae, calc_second_order=False, seed=seed)

    return {
        "n0": n0,
        "n_evals": n_evals,
        "n_workers": n_workers or mp.cpu_count(),
        "run_s": elapsed,
        "s_per_draw": elapsed / n_evals,
        "strata": strata,
        "skipped_strata": skipped_strata,
        "sobol_risk_by_stratum": sobol_risk_by_stratum,
        "sobol_psae_by_stratum": sobol_psae_by_stratum,
    }
