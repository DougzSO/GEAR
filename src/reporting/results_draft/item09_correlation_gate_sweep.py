"""
RESULTS_DRAFT.md Section 4.2 -- correlation-gate threshold sweep, flip count
vs. threshold (0.60-0.90). No persisted CSV exists for this analysis; calls
the real, tracked ``src.index.scenario_discovery.correlation_gate_sweep()``
directly (post-processes the already-computed correlation_gate.csv decision_r
column, never recomputes Pearson/Spearman).
"""

from __future__ import annotations

import matplotlib.pyplot as plt

from src.index import scenario_discovery as sd
from src.reporting.results_draft import common as c

ITEM, SLUG = 9, "correlation_gate_sweep"


def run() -> list[c.ManifestEntry]:
    table = sd.correlation_gate_sweep()

    out_csv = c.tables_dir() / "correlation_gate_sweep.csv"
    table.to_csv(out_csv, index=False)

    flips = table.groupby("threshold")["flipped_vs_baseline"].sum().reindex(sd.SWEPT_THRESHOLDS, fill_value=0)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar([str(t) for t in flips.index], flips.values, color="#264653")
    ax.axvline(list(flips.index).index(0.80), color="#e63946", linestyle="--",
               label="production baseline (0.80)")
    ax.set_xlabel("Swept |r| exclusion threshold")
    ax.set_ylabel("N cells flipped vs. 0.80 baseline")
    ax.set_title("Correlation-gate threshold sweep -- flip count vs. threshold")
    ax.legend()
    fig.tight_layout()
    out_png = c.other_dir() / "correlation_gate_sweep.png"
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return [c.ManifestEntry(
        item=ITEM, section="4.2 Correlation-gate threshold sweep",
        caption="Number of correlation-gate cells that would flip pass/fail under seven "
                "alternative |r| thresholds (0.60-0.90), relative to the production 0.80 baseline.",
        source="src.index.scenario_discovery.correlation_gate_sweep() (recomputed live from "
               "correlation_gate.csv's real decision_r column; no persisted sweep CSV prior to "
               "this run)",
        files=[str(out_csv.relative_to(c.output_root())), str(out_png.relative_to(c.output_root()))],
        status="generated (recomputed from source module, no persisted CSV)",
        notes=f"flips at 0.80 baseline: {int(flips.get(0.80, 0))} (expected 0).",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
