"""
RESULTS_DRAFT.md Section 4.1 -- Sobol S1/ST bar chart, two panels (Risk_i,h,
PSAE_i), all thirteen parameters. Source: phase6_sobol_full_n1024.json
(closed, real, N0=1024, 15,360 evaluations, per docs/DECISIONS.md "GEAR v3
Phase 6 closure").
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.index.sobol_sensitivity import PARAM_NAMES
from src.reporting.results_draft import common as c

ITEM, SLUG = 7, "sobol_sensitivity"


def _panel(ax, block: dict, title: str) -> None:
    s1, s1c, st, stc = np.array(block["S1"]), np.array(block["S1_conf"]), np.array(block["ST"]), np.array(block["ST_conf"])
    order = np.argsort(-st)
    names = [PARAM_NAMES[i] for i in order]
    y = np.arange(len(names))
    ax.barh(y - 0.18, s1[order], height=0.34, xerr=s1c[order], label="S1", color="#264653")
    ax.barh(y + 0.18, st[order], height=0.34, xerr=st[order] * 0 + stc[order], label="ST", color="#e76f51")
    ax.set_yticks(y)
    ax.set_yticklabels(names, fontsize=8)
    ax.invert_yaxis()
    ax.set_xlabel("Sobol index")
    ax.set_title(title, fontsize=10)
    ax.legend(fontsize=8)


def run() -> list[c.ManifestEntry]:
    sobol = c.load_sobol()

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    _panel(axes[0], sobol["sobol_risk"], "Risk_i,h (capacity-weighted pooled mean)")
    _panel(axes[1], sobol["sobol_psae"], "PSAE_i (mean, psae_complete-masked)")
    fig.suptitle(f"Sobol/SALib global sensitivity, D=13, N0={sobol['n0']:,} "
                 f"({sobol['n_evals']:,} evaluations, PSAE coverage "
                 f"{100*sobol['psae_coverage_fraction']:.2f}%)", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out_png = c.other_dir() / "sobol_sensitivity.png"
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close(fig)

    rows = []
    for output_name, block in (("risk", sobol["sobol_risk"]), ("psae", sobol["sobol_psae"])):
        for i, name in enumerate(PARAM_NAMES):
            rows.append({
                "output": output_name, "parameter": name,
                "S1": block["S1"][i], "S1_conf": block["S1_conf"][i],
                "ST": block["ST"][i], "ST_conf": block["ST_conf"][i],
            })
    table = pd.DataFrame(rows)
    out_csv = c.tables_dir() / "sobol_sensitivity.csv"
    table.to_csv(out_csv, index=False)

    return [c.ManifestEntry(
        item=ITEM, section="4.1 Sobol sensitivity",
        caption="First-order (S1) and total-order (ST) Sobol indices for all 13 continuous "
                "parameters, Risk_i,h and PSAE_i panels, showing the two-chain architectural "
                "independence.",
        source="data/outputs/tables/phase6_sobol_full_n1024.json",
        files=[str(out_png.relative_to(c.output_root())), str(out_csv.relative_to(c.output_root()))],
        status="generated",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
