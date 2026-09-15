"""
GEAR v3 Phase 6.1 -- general Monte Carlo uncertainty-propagation driver,
separate from Sobol's own ``N_0`` convergence (``sobol_sensitivity.py``).
Implements ``docs/rework/PHASE6_DESIGN.md`` Section 4.1's doubling-sequence
convergence procedure (``N = 1000, 2000, 4000, 8000, 16000``), using
``rng_utils.phase6_rng``'s per-country-scenario granularity -- the ONE
Phase 6 driver that utility actually attaches to (see ``rng_utils.py``'s
docstring and ``sobol_sensitivity.py``'s, which explains why SALib's own
sampler has no attachment point for it).

--------------------------------------------------------------------------
The 9x cost multiplier -- what per-country-scenario RNG actually requires,
worked through concretely, not resolved here
--------------------------------------------------------------------------
Every one of this project's 13 continuous parameters (``sobol_sensitivity.
PARAM_NAMES``) is genuinely GLOBAL -- ``retention_vector``/
``recompute_risk_bands`` apply one sampled parameter vector identically
across every country and water_scenario within a single evaluation. There
is no way to draw "Brazil/bau's own independent parameter vector" and
"Brazil/opt's own independent parameter vector" and get two DIFFERENT
global parameter vectors cheaply recomputed together -- the chain
(``age_factor`` -> ``RiskBand``/``PSAE``) has to be recomputed in full for
each stream's own draw. Delivering genuine per-country-scenario
independence (the reason this granularity was chosen at all -- avoiding
spurious cross-scenario correlation) therefore means, for each of the 9
``(country, water_scenario)`` streams, independently:

    1. draw one parameter vector from that stream's own ``phase6_rng``,
    2. run ONE FULL recompute (``recompute_draw_all_models``, every
       country, every scenario, both GCMs -- there is no cheaper partial
       recompute that only touches one country/scenario, since the
       upstream chain does not vary by country/scenario except through
       which ROWS happen to belong to that country/scenario),
    3. filter the recomputed output down to just that stream's own
       ``(country, water_scenario)`` rows before recording the statistic.

9 independent full recomputes per draw index, not 1 -- a genuine 9x
multiplier on top of whatever ``N`` the doubling sequence reaches, on top
of Sobol's already-measured ~0.40-0.45s/draw cost. This module implements
exactly that (see ``run_stream``/``run_convergence`` below) because it is
the only construction that actually delivers "per-country-scenario RNG, to
avoid spurious cross-scenario correlation" -- but the resulting cost is an
OPEN DECISION POINT for the author, not resolved by this module: at
``N=8000`` (the design's own minimum target before declaring convergence
plausible), this is ``9 * 8000 = 72,000`` full recomputes, ~72,000 * ~0.45s
~= 9 hours even at the measured 4-worker parallel throughput -- multiple
times the Sobol full-scale run's own already-flagged ~1-2 day cost. This
module deliberately runs only small ``N`` (see ``docs/DECISIONS.md``'s new
entry and this session's report) -- ``N>=8000`` is NOT executed here.

--------------------------------------------------------------------------
Draw distribution
--------------------------------------------------------------------------
Reuses ``sobol_sensitivity.PARAM_NAMES``/``PARAM_BOUNDS`` (the closed D=13
problem) as the parameter space a general-MC draw samples UNIFORMLY from,
via that stream's own ``phase6_rng`` generator (``rng.uniform(lo, hi)`` per
dimension) -- the same ±20%-default / literature-range bounds Sobol uses,
consistent with ``docs/DECISIONS.md``'s "uniform, default distribution"
closure (item 1) for every Tier-3 parameter with no better-sourced prior.
Not a new parameter set -- the same D=13 problem, drawn from directly
rather than through SALib's Saltelli design.

Standalone: no CLI. ``run_convergence`` is the entry point.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import time

import numpy as np
import pandas as pd

from src.config import AQUEDUCT_SCENARIOS, COUNTRIES
from src.index import psae
from src.index import risk_calculator as rc
from src.index import rng_utils
from src.index import sensitivity_recompute as sr
from src.index import sobol_sensitivity as ss

logger = logging.getLogger(__name__)

STREAMS: tuple[tuple[str, str], ...] = tuple(
    (country, scenario) for country in COUNTRIES for scenario in AQUEDUCT_SCENARIOS
)
assert len(STREAMS) == 9


def _draw_row(rng: np.random.Generator) -> np.ndarray:
    """One uniform draw over ``sobol_sensitivity.PROBLEM``'s D=13 box, from
    ``rng`` -- the stream's own ``phase6_rng`` generator."""
    lo = np.array([b[0] for b in ss.PARAM_BOUNDS], dtype="float64")
    hi = np.array([b[1] for b in ss.PARAM_BOUNDS], dtype="float64")
    return lo + rng.random(len(ss.PARAM_NAMES)) * (hi - lo)


def _worker_general_mc_draw(task: tuple[str, str, np.ndarray]) -> dict:
    """One (country, scenario, drawn_row) task -- one FULL recompute (every
    country/scenario/GCM, see module docstring for why it cannot be
    narrower), filtered down to just this task's own (country, scenario)
    rows before returning. Executed inside a worker process (same
    ``sensitivity_recompute._init_worker``-shared ``pre`` pattern as
    ``sobol_sensitivity``'s worker)."""
    country, scenario, row = task
    rate_overrides, percentile_overrides, padding_fraction = ss.row_to_params(row)
    pre = sr._worker_pre
    models = sr._worker_models

    original_pad = rc.TLOG_UPPER_TAIL_PADDING_FRACTION
    rc.TLOG_UPPER_TAIL_PADDING_FRACTION = padding_fraction
    try:
        risk_frames, psae_frames = [], []
        for model in models:
            risk_df = sr.recompute_risk_by_hazard(
                pre, model, bounds=dict(rc.FROZEN_BOUNDS), rate_overrides=rate_overrides,
            )
            risk_frames.append(risk_df)
            band_table = sr.recompute_risk_bands(pre, model, percentile_overrides=percentile_overrides)
            psae_frames.append(psae.compute_psae(band_table).frame)
    finally:
        rc.TLOG_UPPER_TAIL_PADDING_FRACTION = original_pad

    risk_all = pd.concat(risk_frames, ignore_index=True)
    psae_all = pd.concat(psae_frames, ignore_index=True)

    risk_sub = risk_all[(risk_all["country"] == country) & (risk_all["water_scenario"] == scenario)]
    psae_sub = psae_all[(psae_all["country"] == country) & (psae_all["water_scenario"] == scenario)]

    return {
        "country": country,
        "scenario": scenario,
        "risk_mean": float(ss._nanaverage(
            risk_sub["risk_i_h"].to_numpy("float64"), risk_sub["capacity_mw"].to_numpy("float64"),
        )),
        "psae_mean": float(psae_sub["psae"].mean(skipna=True)),
        "psae_n_complete": int(psae_sub["psae_complete"].sum()),
        "psae_n_total": int(len(psae_sub)),
    }


def run_stream_draws_parallel(
    pre: sr.PrecomputedInputs,
    tasks: list[tuple[str, str, np.ndarray]],
    *,
    models: list[str] | None = None,
    n_workers: int | None = None,
) -> list[dict]:
    n_workers = n_workers or mp.cpu_count()
    models = models or rc.configured_models()
    for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ.setdefault(var, "1")
    ctx = mp.get_context()
    with ctx.Pool(processes=n_workers, initializer=sr._init_worker, initargs=(pre, models)) as pool:
        return pool.map(_worker_general_mc_draw, tasks)


def _percentile_ci(values: np.ndarray) -> tuple[float, float]:
    return float(np.nanpercentile(values, 2.5)), float(np.nanpercentile(values, 97.5))


def run_n(
    n: int,
    *,
    pre: sr.PrecomputedInputs | None = None,
    n_workers: int | None = None,
    seed_note: str = "general_mc",
) -> dict:
    """One doubling-sequence step at sample size ``n`` PER STREAM -- ``9 *
    n`` total full recomputes (the 9x multiplier, see module docstring),
    real wall-clock timing. Returns, per (country, scenario) stream and
    pooled-overall: point estimate (mean), 95%% percentile CI
    (2.5/97.5, ``PHASE6_DESIGN.md`` Section 4.1's own convention), CI
    half-width, and Monte Carlo SE (``sample_std / sqrt(n)``) -- for BOTH
    output statistics (Risk_i,h, PSAE_i), psae_complete=False rows NaN-
    masked throughout (never dropped)."""
    if pre is None:
        pre = sr.precompute()

    tasks: list[tuple[str, str, np.ndarray]] = []
    for country, scenario in STREAMS:
        rng = rng_utils.phase6_rng(country, scenario, seed_note)
        for _ in range(n):
            tasks.append((country, scenario, _draw_row(rng)))

    t0 = time.perf_counter()
    results = run_stream_draws_parallel(pre, tasks, n_workers=n_workers)
    elapsed = time.perf_counter() - t0

    df = pd.DataFrame(results)
    stream_stats = {}
    for (country, scenario), sub in df.groupby(["country", "scenario"]):
        risk_vals = sub["risk_mean"].to_numpy("float64")
        psae_vals = sub["psae_mean"].to_numpy("float64")
        risk_lo, risk_hi = _percentile_ci(risk_vals)
        psae_lo, psae_hi = _percentile_ci(psae_vals)
        stream_stats[(country, scenario)] = {
            "n": len(sub),
            "risk_mean": float(np.nanmean(risk_vals)),
            "risk_ci": (risk_lo, risk_hi),
            "risk_ci_halfwidth": (risk_hi - risk_lo) / 2.0,
            "risk_se": float(np.nanstd(risk_vals, ddof=1) / np.sqrt(len(risk_vals))) if len(risk_vals) > 1 else float("nan"),
            "psae_mean": float(np.nanmean(psae_vals)),
            "psae_ci": (psae_lo, psae_hi),
            "psae_ci_halfwidth": (psae_hi - psae_lo) / 2.0,
            "psae_se": float(np.nanstd(psae_vals, ddof=1) / np.sqrt(len(psae_vals))) if len(psae_vals) > 1 else float("nan"),
            "psae_n_complete": int(sub["psae_n_complete"].sum()),
            "psae_n_total": int(sub["psae_n_total"].sum()),
        }

    return {
        "n": n,
        "n_total_draws": len(tasks),
        "elapsed_s": elapsed,
        "s_per_draw": elapsed / len(tasks),
        "stream_stats": stream_stats,
        "raw": df,
    }


def run_convergence(
    ns: list[int],
    *,
    pre: sr.PrecomputedInputs | None = None,
    n_workers: int | None = None,
) -> list[dict]:
    """The doubling sequence, run only at the ``ns`` given (this project's
    task explicitly caps real execution well below the design's full
    1000/2000/4000/8000/16000 sequence -- see this module's docstring and
    ``docs/DECISIONS.md``). Point-estimate and CI-half-width relative
    change vs. the previous step are computed per stream, per output, for
    whatever steps ARE run, so the (early, non-converged) trend is still
    visible."""
    if pre is None:
        pre = sr.precompute()
    steps = [run_n(n, pre=pre, n_workers=n_workers) for n in ns]

    for i in range(1, len(steps)):
        prev, cur = steps[i - 1], steps[i]
        for key in prev["stream_stats"]:
            p, c = prev["stream_stats"][key], cur["stream_stats"][key]
            for stat in ("risk_mean", "psae_mean"):
                base = p[stat]
                c[f"{stat}_relchange_vs_prev"] = (
                    abs(c[stat] - base) / abs(base) if base not in (0, None) and not np.isnan(base) else float("nan")
                )
            for stat in ("risk_ci_halfwidth", "psae_ci_halfwidth"):
                base = p[stat]
                c[f"{stat}_relchange_vs_prev"] = (
                    abs(c[stat] - base) / abs(base) if base not in (0, None) and not np.isnan(base) else float("nan")
                )
    return steps
