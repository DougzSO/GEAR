"""Script temporário: doubling sequence do Phase 6.1 (general-MC), N=100 ate
N=8000 por stream (9 streams, granularidade per-country-scenario, sem
reducao por custo -- decisao do autor). Para cedo se os dois criterios do
PHASE6_DESIGN.md Secao 4.1 forem atingidos e confirmados por mais um
dobramento; caso contrario roda ate N=8000 e reporta como nao convergido.
Nao faz parte do pipeline de producao -- artefato de execucao unica desta
tarefa, a ser removido depois que os numeros forem incorporados a
docs/DECISIONS.md."""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

from src.index import general_mc as gmc
from src.index import sensitivity_recompute as sr

POINT_TOL = 0.01
CI_TOL = 0.05
NS_SEQUENCE = [100, 200, 400, 800, 1600, 3200, 6400, 8000]


def _to_jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, float) and np.isnan(obj):
        return None
    return obj


def _criteria_met(prev_step: dict, cur_step: dict) -> bool:
    for key, cur in cur_step["stream_stats"].items():
        for stat in ("risk_mean_relchange_vs_prev", "psae_mean_relchange_vs_prev"):
            v = cur.get(stat)
            if v is None or np.isnan(v) or v >= POINT_TOL:
                return False
        for stat in ("risk_ci_halfwidth_relchange_vs_prev", "psae_ci_halfwidth_relchange_vs_prev"):
            v = cur.get(stat)
            if v is None or np.isnan(v) or v >= CI_TOL:
                return False
    return True


def main() -> None:
    t0 = time.perf_counter()
    print("precompute() starting...", flush=True)
    pre = sr.precompute()
    print(f"precompute() done in {time.perf_counter() - t0:.1f}s", flush=True)

    steps: list[dict] = []
    converged_at = None
    confirmed = False

    for i, n in enumerate(NS_SEQUENCE):
        t_step0 = time.perf_counter()
        step = gmc.run_n(n, pre=pre, n_workers=4, seed_note="general_mc")
        step_elapsed = time.perf_counter() - t_step0
        print(f"N={n}: {step['n_total_draws']} draws, {step_elapsed:.1f}s, "
              f"{step['s_per_draw']:.4f}s/draw", flush=True)

        if steps:
            prev = steps[-1]
            for key in prev["stream_stats"]:
                p, c = prev["stream_stats"][key], step["stream_stats"][key]
                for stat in ("risk_mean", "psae_mean"):
                    base = p[stat]
                    c[f"{stat}_relchange_vs_prev"] = (
                        abs(c[stat] - base) / abs(base)
                        if base not in (0, None) and not np.isnan(base) else float("nan")
                    )
                for stat in ("risk_ci_halfwidth", "psae_ci_halfwidth"):
                    base = p[stat]
                    c[f"{stat}_relchange_vs_prev"] = (
                        abs(c[stat] - base) / abs(base)
                        if base not in (0, None) and not np.isnan(base) else float("nan")
                    )

        steps.append(step)

        # Dump partial results after every step so a mid-run check is possible.
        partial = {"ns_run_so_far": [s["n"] for s in steps],
                   "steps": [{k: v for k, v in s.items() if k != "raw"} for s in steps]}
        with open("data/outputs/tables/phase6_general_mc_convergence.json", "w", encoding="utf-8") as f:
            json.dump(_to_jsonable(partial), f, indent=2)

        if len(steps) >= 2 and not confirmed:
            met = _criteria_met(steps[-2], steps[-1])
            print(f"  criteria met at N={n} vs N={steps[-2]['n']}: {met}", flush=True)
            if met and converged_at is None:
                converged_at = steps[-2]["n"]
            elif not met:
                converged_at = None

        if converged_at is not None and not confirmed:
            # need one more doubling to confirm -- that is the step we just ran
            if steps[-1]["n"] != converged_at:
                confirmed = True
                print(f"CONVERGED and CONFIRMED at N={converged_at} (confirmed by N={steps[-1]['n']})", flush=True)
                break

    else:
        pass

    final = {
        "ns_run": [s["n"] for s in steps],
        "converged": confirmed,
        "converged_n": converged_at if confirmed else None,
        "final_n_if_not_converged": steps[-1]["n"] if not confirmed else None,
        "steps": [{k: v for k, v in s.items() if k != "raw"} for s in steps],
    }
    with open("data/outputs/tables/phase6_general_mc_convergence.json", "w", encoding="utf-8") as f:
        json.dump(_to_jsonable(final), f, indent=2)

    print("DONE")
    print(f"converged={confirmed} converged_n={converged_at} ns_run={[s['n'] for s in steps]}")


if __name__ == "__main__":
    main()
