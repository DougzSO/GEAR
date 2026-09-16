"""
RESULTS_DRAFT.md Section 5 -- PSAE secondary/screening map, one map per
(bucket, SSP scenario), colored by PSAE category, with contextual-validator
overlay (physical-occurrence/IBTrACS and broad-impact/EM-DAT, visually
distinct symbology per Methods Section 7's two-class taxonomy). Explicitly
labeled a screening index, not asset risk magnitude (see item05 for Risk_i,h
maps). Source: psae.csv + risk_by_hazard.csv (lat/lon) + contextual_validators.csv.

Layout (2026-09-16 rework, matching item04's country-column convention):
never more than 3 maps per figure, never a country x scenario grid.
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


def _plot(bucket: str, scen: str, sub_bucket, corrob: dict, cap_max: float, out_path) -> None:
    sub = sub_bucket[(sub_bucket["water_scenario"] == scen) & (sub_bucket["psae_complete"])]
    countries = [co for co in c.COUNTRIES if (sub["country"] == co).any()]
    fig, axes = c.make_country_row_figure(countries)

    for ax, country in zip(axes, countries):
        c.draw_country_boundary(ax, country)
        cell = sub[sub["country"] == country]
        for label in c.PSAE_LABELS:
            lc = cell[cell["psae_label"] == label]
            if lc.empty:
                continue
            ax.scatter(lc["lon"], lc["lat"], marker="o", color=c.PSAE_COLOR[label],
                       s=c.marker_sizes(lc["capacity_mw"], capacity_max=cap_max),
                       edgecolor="black", linewidth=0.2, alpha=c.MARKER_ALPHA, zorder=3)
        phys = cell[cell["plant_uid"].isin(corrob.get("physical_occurrence", set()))]
        broad = cell[cell["plant_uid"].isin(corrob.get("broad_impact", set()))]
        # broad-impact (EM-DAT) corroboration is a country/region-level disaster record, so it
        # is genuinely near-universal within an affected country (up to ~78% of solar plants,
        # 2026-09-16 data) -- no marker size alone keeps that legible, so this overlay stays
        # small, thin, and translucent rather than competing with the PSAE-colored base circles.
        if len(phys):
            ax.scatter(phys["lon"], phys["lat"], marker="*", facecolor="none",
                       edgecolor="black", s=19.2, linewidth=0.5, alpha=0.55, zorder=4)
        if len(broad):
            ax.scatter(broad["lon"], broad["lat"], marker="^", facecolor="none",
                       edgecolor="blue", s=12, linewidth=0.4, alpha=0.4, zorder=4)
        c.panel_title(ax, country, len(cell))

    label_handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=c.PSAE_COLOR[l],
                                 markeredgecolor="black", markersize=8.4, label=l) for l in c.PSAE_LABELS]
    val_handles = [
        plt.Line2D([0], [0], marker="*", color="w", markerfacecolor="none", markeredgecolor="black",
                   markersize=9.6, label="Physical-occurrence corroborated (IBTrACS)"),
        plt.Line2D([0], [0], marker="^", color="w", markerfacecolor="none", markeredgecolor="blue",
                   markersize=8.4, label="Broad-impact corroborated (EM-DAT)"),
    ]
    c.legend_below_axes(fig, axes, label_handles + val_handles,
                         ncol=len(label_handles) + len(val_handles))
    fig.suptitle(f"PSAE -- {c.BUCKET_LABEL[bucket]} ({c.SSP_LABEL[scen]})", fontsize=14.4, fontweight="bold")
    fig.canvas.draw()
    for ax in axes:
        c.add_compass_rose(ax, redraw=False)
    c.save_figure(fig, out_path)


def run() -> list[c.ManifestEntry]:
    inv = c.load_inventory()
    psae = c.load_psae(capacity=inv.set_index("plant_uid")["capacity_mw"])
    coords = c.load_coords()
    validators = c.load_contextual_validators()
    psae = psae.merge(coords, left_on="plant_uid", right_index=True, how="left")
    cap_max = psae["capacity_mw"].max()

    files = []
    for bucket in c.BUCKET_ORDER:
        sub_bucket = psae[psae["bucket"] == bucket]
        if sub_bucket.empty:
            continue
        corrob = _corroborated_plants(validators, bucket)
        for scen in c.SSP_ORDER:
            if not (sub_bucket["water_scenario"] == scen).any():
                continue
            out_png = c.maps_dir(scen) / f"psae_screening_map_{bucket}_{scen}.png"
            _plot(bucket, scen, sub_bucket, corrob, cap_max, out_png)
            files.append(str(out_png.relative_to(c.output_root())))

    return [c.ManifestEntry(
        item=ITEM, section="5. PSAE screening map",
        caption="Geographic distribution of PSAE_i screening classifications, one figure per (bucket, "
                "SSP scenario), 3 country panels each, physical-occurrence and broad-impact validator "
                "overlay, explicitly secondary/screening-only.",
        source="data/outputs/tables/psae.csv + risk_by_hazard.csv (lat/lon) + "
               "contextual_validators.csv",
        files=files, status="generated",
        notes=f"{len(files)} files (1 per bucket x SSP scenario combination) -- 2026-09-16 rework, "
              f"max 3 maps/figure.",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
