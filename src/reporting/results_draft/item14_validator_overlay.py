"""
RESULTS_DRAFT.md Section 6 -- validator overlay summary table (Corroborated /
No Record / Not Applicable counts, by validator type, hazard, country).
Source: contextual_validators.csv -- already the full production join (58,744
rows, both validator classes, all hazards/countries); the draft's own
"pending" status note for this item predates this file's materialization.
"""

from __future__ import annotations

import matplotlib.pyplot as plt

from src.reporting.results_draft import common as c

ITEM, SLUG = 14, "validator_overlay"
STATES = ["Corroborated", "No Record", "Not Applicable"]


def run() -> list[c.ManifestEntry]:
    d = c.item_dir(ITEM, SLUG)
    v = c.load_contextual_validators()

    table = (
        v.groupby(["validator_class", "country", "hazard_term", "state"])
        .size().reset_index(name="n_plants")
    )
    total = v.groupby(["validator_class", "country", "hazard_term"]).size().reset_index(name="total")
    table = table.merge(total, on=["validator_class", "country", "hazard_term"])
    table["fraction"] = table["n_plants"] / table["total"]
    table["hazard_label"] = table["hazard_term"].map(c.HAZARD_LABEL)
    out_csv = d / "validator_overlay_summary.csv"
    table.to_csv(out_csv, index=False)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for ax, vclass in zip(axes, ["physical_occurrence", "broad_impact"]):
        sub = table[table["validator_class"] == vclass]
        pivot = sub.pivot_table(index=["country", "hazard_label"], columns="state",
                                 values="n_plants", fill_value=0)
        pivot = pivot.reindex(columns=STATES, fill_value=0)
        pivot.plot(kind="barh", stacked=True, ax=ax,
                   color=["#2a9d8f", "#e9c46a", "#adb5bd"])
        ax.set_title(vclass, fontsize=10)
        ax.set_xlabel("N plants")
        ax.legend(fontsize=7)
    fig.suptitle("Contextual validator overlay -- Corroborated / No Record / Not Applicable, "
                 "by validator class, country, hazard", fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out_png = d / "validator_overlay_summary.png"
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close(fig)

    return [c.ManifestEntry(
        item=ITEM, section="6. Validator overlay",
        caption="Count/fraction of plants in Corroborated / No Record / Not Applicable, "
                "physical-occurrence (IBTrACS) and broad-impact (EM-DAT) validators, by country "
                "and hazard.",
        source="data/outputs/tables/contextual_validators.csv",
        files=[str(out_csv.relative_to(d.parent.parent)), str(out_png.relative_to(d.parent.parent))],
        status="generated",
        notes="Full production join already materialized (58,744 rows) -- contradicts the "
              "RESULTS_DRAFT.md text's 'not yet produced' status for this item.",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
