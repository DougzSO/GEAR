"""
RESULTS_DRAFT.md Section 1 -- correlation-gate matrix (closed, real numbers).
Source: data/outputs/tables/correlation_gate.csv (src/index/correlation_gate.py
output), 56 rows = 48 gated cells (5 pairs x 3 countries x GCM-dependent axis)
+ 8 mandatory non-gated Water Stress vs. Drought reference rows.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from src.reporting.results_draft import common as c

ITEM, SLUG = 1, "correlation_gate"
GATE_THRESHOLD = 0.80


def run() -> list[c.ManifestEntry]:
    df = c.load_correlation_gate()

    export_cols = [
        "pair_label", "term_a", "term_b", "gated", "bucket", "country", "gcm", "n",
        "pearson_r", "spearman_rho", "nonlinearity_flagged", "decision_r_method",
        "decision_r", "gate_verdict", "retained_term", "excluded_term", "criterion",
    ]
    out_csv = c.tables_dir() / "correlation_gate_matrix.csv"
    df[export_cols].to_csv(out_csv, index=False)

    df = df.copy()
    df["row_label"] = df["pair_label"].str.slice(0, 42) + " | " + df["country"] + " | " + df["gcm"]
    df = df.sort_values(["gated", "pair_label", "country", "gcm"], ascending=[False, True, True, True])

    fig, ax = plt.subplots(figsize=(9, max(6, 0.22 * len(df))))
    # Explicit pass/fail selection, not `gated & (verdict != "pass")": that
    # comparison treats a NaN verdict as "!= pass" too, which silently
    # painted the 12 "pooled" rows (gated=True by pair definition, but never
    # assigned a real per-country verdict -- see correlation_gate.run_gate,
    # `if country != "pooled": verdict = ...`) red as if they had failed the
    # gate, when in fact zero real per-country gated cells fail.
    colors = np.select(
        [df["gate_verdict"] == "pass", df["gate_verdict"] == "fail"],
        ["#2a9d8f", "#e63946"],
        default="#8d99ae",
    )
    y = np.arange(len(df))
    ax.barh(y, df["decision_r"].abs(), color=colors)
    ax.axvline(GATE_THRESHOLD, color="black", linestyle="--", linewidth=1, label=f"exclusion threshold |r|={GATE_THRESHOLD}")
    ax.set_yticks(y)
    ax.set_yticklabels(df["row_label"], fontsize=6)
    ax.set_xlabel("|decision statistic| (Pearson r, or Spearman rho where nonlinearity-flagged)")
    ax.set_title("Correlation-gate matrix -- |decision_r| per pair x country x GCM (gated pairs) "
                  "and the mandatory Water Stress vs. Drought reference rows (grey, not gated)")
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    out_png = c.other_dir() / "correlation_gate_matrix.png"
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close(fig)

    n_flip = int((df["gate_verdict"] == "fail").sum())
    n_pass = int((df["gate_verdict"] == "pass").sum())
    n_report_only = int((df["gate_verdict"] == "report_only").sum())
    n_not_gated = int(df["gate_verdict"].isna().sum())
    return [c.ManifestEntry(
        item=ITEM, section="1. Correlation gate",
        caption="Full pairwise correlation-gate matrix (Pearson r, Spearman rho, n, decision-method "
                "flag, pass/fail) for the five gated pairs x three countries x GCM, plus the "
                "mandatory Water Stress/Drought reference row.",
        source="data/outputs/tables/correlation_gate.csv",
        files=[str(out_csv.relative_to(c.output_root())), str(out_png.relative_to(c.output_root()))],
        status="generated",
        notes=f"{len(df)} rows exported; {n_flip} gated cells failed the |r|<0.80 threshold "
              f"(expected 0, per docs/DECISIONS.md closure) -- {n_pass} pass, {n_report_only} "
              f"report_only, {n_not_gated} not gated (pooled reference rows, no per-country verdict).",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
