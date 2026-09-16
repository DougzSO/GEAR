"""
RESULTS_DRAFT.md Section 4.2 -- hazard-removal OAT summary table (capacity-
fraction shift per removal, by country and bucket). No persisted CSV exists
for this analysis (docs/DECISIONS.md only carries the narrative numbers) --
this module calls the real, tracked
``src.index.scenario_discovery.hazard_removal_oat()`` directly against real
production data (cheap, no Monte Carlo) rather than treating this item as
data-less.
"""

from __future__ import annotations

import matplotlib.pyplot as plt

from src.index import scenario_discovery as sd
from src.reporting.results_draft import common as c

ITEM, SLUG = 8, "hazard_removal_oat"


def run() -> list[c.ManifestEntry]:
    d = c.item_dir(ITEM, SLUG)
    table = sd.hazard_removal_oat()

    out_csv = d / "hazard_removal_oat.csv"
    table.to_csv(out_csv, index=False)

    high = table[table["psae_label"] == "HIGH"].copy()
    high["shift_pp"] = high["shift"] * 100
    high["group"] = high["bucket"] + " / " + high["removed_hazard"] + " / " + high["country"]
    high = high.sort_values("shift_pp", key=lambda s: s.abs(), ascending=True)

    fig, ax = plt.subplots(figsize=(9, max(5, 0.28 * len(high))))
    colors = ["#e63946" if v > 0 else "#2a9d8f" for v in high["shift_pp"]]
    ax.barh(high["group"], high["shift_pp"], color=colors)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Shift in PSAE=HIGH capacity fraction (percentage points, removal - baseline)")
    ax.set_title("Hazard-removal OAT -- capacity-fraction shift into PSAE=HIGH per removed hazard")
    ax.tick_params(axis="y", labelsize=7)
    fig.tight_layout()
    out_png = d / "hazard_removal_oat.png"
    fig.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close(fig)

    max_shift = high["shift_pp"].abs().max()
    return [c.ManifestEntry(
        item=ITEM, section="4.2 Hazard-removal OAT",
        caption="Change in PSAE band capacity share when each applicable hazard is individually "
                "removed from its bucket's H_b, by country.",
        source="src.index.scenario_discovery.hazard_removal_oat() (recomputed live; no persisted "
               "CSV in data/outputs/tables/ prior to this run)",
        files=[str(out_csv.relative_to(d.parent.parent)), str(out_png.relative_to(d.parent.parent))],
        status="generated (recomputed from source module, no persisted CSV)",
        notes=f"{len(table)} rows; largest observed |shift| in HIGH band: {max_shift:.1f} pp.",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
