"""
RESULTS_DRAFT.md Section 4.3 -- general-MC convergence diagnostic
(point-estimate and CI half-width relative change vs. N, both outputs, all
nine streams). Source: phase6_general_mc_convergence.json (already carries
``*_relchange_vs_prev`` fields computed by
``src.index.general_mc.run_convergence``, not recomputed here).
"""

from __future__ import annotations

import ast

import matplotlib.pyplot as plt
import pandas as pd

from src.reporting.results_draft import common as c

ITEM, SLUG = 10, "general_mc_convergence"


def run() -> list[c.ManifestEntry]:
    gmc = c.load_general_mc_convergence()

    rows = []
    for step in gmc["steps"]:
        n = step["n"]
        for key, v in step["stream_stats"].items():
            country, scenario = ast.literal_eval(key)
            row = {"n": n, "country": country, "scenario": scenario, "ssp": c.SSP_LABEL[scenario]}
            row.update(v)
            rows.append(row)
    table = pd.DataFrame(rows)
    out_csv = c.tables_dir() / "general_mc_convergence.csv"
    table.to_csv(out_csv, index=False)

    fig, axes = plt.subplots(2, 2, figsize=(12, 9), sharex=True)
    stream_labels = [f"{co}/{sc}" for co in c.COUNTRIES for sc in c.SSP_ORDER]
    for ax, col, title in zip(
        axes.ravel(),
        ["risk_mean_relchange_vs_prev", "psae_mean_relchange_vs_prev",
         "risk_ci_halfwidth_relchange_vs_prev", "psae_ci_halfwidth_relchange_vs_prev"],
        ["risk_mean point-estimate relative change", "psae_mean point-estimate relative change",
         "risk_mean 95% CI half-width relative change", "psae_mean 95% CI half-width relative change"],
    ):
        for co in c.COUNTRIES:
            for sc in c.SSP_ORDER:
                sub = table[(table["country"] == co) & (table["scenario"] == sc)].sort_values("n")
                ax.plot(sub["n"], sub[col], marker="o", markersize=3, label=f"{co}/{c.SSP_LABEL[sc]}")
        ax.set_yscale("log")
        ax.set_xscale("log")
        ax.set_title(title, fontsize=9)
        ax.set_xlabel("N draws per stream")
        ax.axhline(0.01, color="grey", linestyle="--", linewidth=0.7)
    axes[0, 0].legend(fontsize=6, ncol=2)
    fig.suptitle(f"General Monte Carlo convergence -- converged={gmc['converged']} at "
                 f"N={gmc['converged_n']} (Ns tested: {gmc['ns_run']})", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out_png = c.other_dir() / "general_mc_convergence.png"
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return [c.ManifestEntry(
        item=ITEM, section="4.3 General-MC convergence",
        caption="Convergence of point-estimate and 95% CI half-width relative change vs. N "
                "(doubling sequence), risk_mean and psae_mean, all nine country x scenario streams.",
        source="data/outputs/tables/phase6_general_mc_convergence.json",
        files=[str(out_csv.relative_to(c.output_root())), str(out_png.relative_to(c.output_root()))],
        status="generated",
        notes=f"converged={gmc['converged']}, converged_n={gmc['converged_n']}.",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
