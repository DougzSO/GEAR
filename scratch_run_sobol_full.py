"""Script temporário: roda o Sobol/SALib completo em N_0=1024 e salva os
resultados reais (S1/ST por parâmetro, por estatística de saída) em JSON.
Não faz parte do pipeline de produção -- artefato de execução única desta
tarefa (Phase 6.2 full-scale run), a ser removido depois que os números
forem incorporados a docs/DECISIONS.md."""
from __future__ import annotations

import json
import time

import numpy as np

from src.index import sensitivity_recompute as sr
from src.index import sobol_sensitivity as ss


def _to_jsonable(obj):
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    return obj


def main() -> None:
    t0 = time.perf_counter()
    print("precompute() starting...", flush=True)
    pre = sr.precompute()
    print(f"precompute() done in {time.perf_counter() - t0:.1f}s", flush=True)

    result = ss.run_validation(1024, pre=pre, n_workers=4, seed=20260915)

    out = _to_jsonable(result)
    with open("data/outputs/tables/phase6_sobol_full_n1024.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print("DONE")
    print(f"n0={result['n0']} n_evals={result['n_evals']} total_s={result['total_s']:.1f} "
          f"s_per_draw={result['s_per_draw']:.4f} psae_coverage={result['psae_coverage_fraction']:.5f}")


if __name__ == "__main__":
    main()
