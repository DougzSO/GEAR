"""
RESULTS_DRAFT.md Section 5 -- PSAE secondary/screening map, one map per
bucket, colored by PSAE category, with contextual-validator overlay
(physical-occurrence/IBTrACS and broad-impact/EM-DAT, visually distinct
symbology per Methods Section 7's two-class taxonomy). Explicitly labeled a
screening index, not asset risk magnitude (see item05 for Risk_i,h maps).
Source: psae.csv + risk_by_hazard.csv (lat/lon) + contextual_validators.csv.
"""

from __future__ import annotations

import matplotlib.pyplot as plt

from src.reporting.results_draft import common as c

ITEM, SLUG = 13, "psae_screening_map"


def _corroborated_plants(validators, bucket: str) -> dict[str, set]:
    """plant_uid sets per validator_class, restricted to this bucket's H_b
    hazards and state == 'Corroborated' -- a bucket's map overlay only shows
    corroboration for hazards actually applicable to that bucket."""
    hazards = c.BUCKET_HAZARDS[bucket]
    sub = validators[(validators["bucket"] == bucket) & (validators["hazard_term"].isin(hazards)) &
                      (validators["state"] == "Corroborated")]
    return {vclass: set(g["plant_uid"]) for vclass, g in sub.groupby("validator_class")}


def _plot(bucket: str, sub, corrob: dict, out_path) -> None:
    countries = [co for co in c.COUNTRIES if (sub["country"] == co).any()]
    fig, axes = plt.subplots(len(countries), 3, squeeze=False, figsize=(3 * 4.2, 4.6 * len(countries)))
    for ri, country in enumerate(countries):
        for ci, scen in enumerate(c.SSP_ORDER):
            ax = axes[ri, ci]
            c.draw_country_boundary(ax, country)
            cell = sub[(sub["country"] == country) & (sub["water_scenario"] == scen) & (sub["psae_complete"])]
            for label in c.PSAE_LABELS:
                lc = cell[cell["psae_label"] == label]
                if lc.empty:
                    continue
                ax.scatter(lc["lon"], lc["lat"], marker="o", color=c.PSAE_COLOR[label],
                           s=c.marker_sizes(lc["capacity_mw"]),
                           edgecolor="black", linewidth=0.2, zorder=3)
            phys = cell[cell["plant_uid"].isin(corrob.get("physical_occurrence", set()))]
            broad = cell[cell["plant_uid"].isin(corrob.get("broad_impact", set()))]
            if len(phys):
                ax.scatter(phys["lon"], phys["lat"], marker="*", facecolor="none",
                           edgecolor="black", s=90, linewidth=0.8, zorder=4)
            if len(broad):
                ax.scatter(broad["lon"], broad["lat"], marker="^", facecolor="none",
                           edgecolor="blue", s=70, linewidth=0.8, zorder=4)
            title = f"{country} -- {c.SSP_LABEL[scen]}" if ri == 0 or ci == 0 else c.SSP_LABEL[scen]
            c.panel_title(ax, title, len(cell))
    label_handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=c.PSAE_COLOR[l],
                                 markeredgecolor="black", markersize=7, label=l) for l in c.PSAE_LABELS]
    val_handles = [
        plt.Line2D([0], [0], marker="*", color="w", markerfacecolor="none", markeredgecolor="black",
                   markersize=10, label="Physical-occurrence corroborated (IBTrACS)"),
        plt.Line2D([0], [0], marker="^", color="w", markerfacecolor="none", markeredgecolor="blue",
                   markersize=9, label="Broad-impact corroborated (EM-DAT)"),
    ]
    fig.legend(handles=label_handles + val_handles, loc="lower center",
               ncol=len(label_handles) + len(val_handles), fontsize=7, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle(f"PSAE_i screening map -- {c.BUCKET_LABEL[bucket]} (secondary/screening index, "
                 f"not asset risk magnitude; validator overlay shows corroboration only, absence of "
                 f"a marker is not 'no hazard occurred')", fontsize=10)
    fig.canvas.draw()
    for ax in axes.ravel():
        c.add_compass_rose(ax, redraw=False)
    c.save_figure(fig, out_path)


def run() -> list[c.ManifestEntry]:
    d = c.item_dir(ITEM, SLUG)
    inv = c.load_inventory()
    psae = c.load_psae(capacity=inv.set_index("plant_uid")["capacity_mw"])
    coords = c.load_coords()
    validators = c.load_contextual_validators()
    psae = psae.merge(coords, left_on="plant_uid", right_index=True, how="left")

    files = []
    for bucket in c.BUCKET_ORDER:
        sub = psae[psae["bucket"] == bucket]
        if sub.empty:
            continue
        corrob = _corroborated_plants(validators, bucket)
        out_png = d / f"psae_screening_map_{bucket}.png"
        _plot(bucket, sub, corrob, out_png)
        files.append(str(out_png.relative_to(d.parent.parent)))

    return [c.ManifestEntry(
        item=ITEM, section="5. PSAE screening map",
        caption="Geographic distribution of PSAE_i screening classifications per bucket, "
                "physical-occurrence and broad-impact validator overlay, explicitly secondary/"
                "screening-only.",
        source="data/outputs/tables/psae.csv + risk_by_hazard.csv (lat/lon) + "
               "contextual_validators.csv",
        files=files, status="generated",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
