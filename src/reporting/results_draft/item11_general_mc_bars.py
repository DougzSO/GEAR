"""
RESULTS_DRAFT.md Section 4.3 -- cross-country, cross-scenario risk_mean/
psae_mean bar chart with 95% CI error bars, N=800 (the converged step).
Source: phase6_general_mc_convergence.json, ``converged_n`` step.
"""

from __future__ import annotations

import ast

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.reporting.results_draft import common as c

ITEM, SLUG = 11, "general_mc_bars"


def run() -> list[c.ManifestEntry]:
    gmc = c.load_general_mc_convergence()
    converged_n = gmc["converged_n"]
    step = next(s for s in gmc["steps"] if s["n"] == converged_n)

    rows = []
    for key, v in step["stream_stats"].items():
        country, scenario = ast.literal_eval(key)
        rows.append({
            "country": country, "scenario": scenario, "ssp": c.SSP_LABEL[scenario],
            "risk_mean": v["risk_mean"], "risk_ci_lo": v["risk_ci"][0], "risk_ci_hi": v["risk_ci"][1],
            "psae_mean": v["psae_mean"], "psae_ci_lo": v["psae_ci"][0], "psae_ci_hi": v["psae_ci"][1],
        })
    table = pd.DataFrame(rows)
    out_csv = c.tables_dir() / "general_mc_bars.csv"
    table.to_csv(out_csv, index=False)

    groups = [(co, sc) for co in c.COUNTRIES for sc in c.SSP_ORDER]
    x = np.arange(len(groups))
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for ax, mean_col, lo_col, hi_col, title in (
        (axes[0], "risk_mean", "risk_ci_lo", "risk_ci_hi", "risk_mean (capacity-weighted, pooled)"),
        (axes[1], "psae_mean", "psae_ci_lo", "psae_ci_hi", "psae_mean"),
    ):
        vals, lo, hi = [], [], []
        for co, sc in groups:
            r = table[(table["country"] == co) & (table["scenario"] == sc)].iloc[0]
            vals.append(r[mean_col]); lo.append(r[mean_col] - r[lo_col]); hi.append(r[hi_col] - r[mean_col])
        ax.bar(x, vals, yerr=[lo, hi], capsize=3, color="#264653")
        ax.set_xticks(x)
        ax.set_xticklabels([f"{co}\n{c.SSP_LABEL[sc]}" for co, sc in groups], fontsize=7)
        ax.set_title(title, fontsize=10)
    fig.suptitle(f"General Monte Carlo point estimates with 95% CI, N={converged_n} per stream", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    out_png = c.other_dir() / "general_mc_bars.png"
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return [c.ManifestEntry(
        item=ITEM, section="4.3 General-MC bar chart",
        caption=f"Mean Risk_i,h and mean PSAE_i with 95% CI, N={converged_n}-per-stream, for nine "
                f"country x water-scenario combinations.",
        source="data/outputs/tables/phase6_general_mc_convergence.json (converged_n step)",
        files=[str(out_csv.relative_to(c.output_root())), str(out_png.relative_to(c.output_root()))],
        status="generated",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
