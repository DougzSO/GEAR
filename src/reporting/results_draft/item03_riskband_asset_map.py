"""
RESULTS_DRAFT.md Section 2 -- per-hazard, per-scenario RiskBand asset map
(point symbology, technology-differentiated markers, colored by RiskBand).
Source: risk_bands.csv (T4) joined to per-plant lat/lon (risk_by_hazard.csv).

Layout (2026-09-16 rework, matching item04's country-column convention): one
figure per (SSP scenario, hazard) combination, 3 country panels side by
side -- never more than 3 maps per figure, never a country x scenario or
country x hazard grid. Hazards stay in separate figures with their own axis
(never summed/blended, Methods Section 9); every panel keeps the same
Low/Medium/High/Extreme legend, so no cross-hazard color-scale distortion is
introduced.

Extreme Wind is excluded here (its own single-figure, scenario-invariant
layout is item04, per the draft's explicit instruction not to repeat three
near-duplicate SSP figures for a scenario-invariant hazard).

Disputed-territory treatment (dashed ADM1 outline, no footer disclaimer,
2026-09-06 author decision) is applied uniformly via
``common.draw_country_boundary`` -- India panels are never a special case.
"""

from __future__ import annotations

import matplotlib.pyplot as plt

from src.reporting.results_draft import common as c

ITEM, SLUG = 3, "riskband_asset_map"
MAP_HAZARDS = ["ws", "spei", "precip", "sv", "iv", "heat"]  # wind handled by item04


def _plot(scen: str, hazard: str, merged, cap_max: float, out_path) -> None:
    sub = merged[(merged["water_scenario"] == scen) & (merged["hazard_term"] == hazard)]
    countries_present = [co for co in c.COUNTRIES if (sub["country"] == co).any()]
    fig, axes = c.make_country_row_figure(countries_present)

    for ax, country in zip(axes, countries_present):
        c.draw_country_boundary(ax, country)
        cell_country = sub[sub["country"] == country]
        n_plotted = 0
        for bucket in cell_country["bucket"].unique():
            bsub = cell_country[cell_country["bucket"] == bucket]
            for band in c.BAND_ORDER:
                cell = bsub[bsub["risk_band"] == band]
                if cell.empty:
                    continue
                n_plotted += len(cell)
                ax.scatter(cell["lon"], cell["lat"], marker=c.BUCKET_MARKER[bucket],
                           color=c.BAND_COLOR[band], s=c.marker_sizes(cell["capacity_mw"], capacity_max=cap_max),
                           edgecolor="black", linewidth=0.2, alpha=c.MARKER_ALPHA, zorder=3)
        c.panel_title(ax, country, n_plotted)

    buckets_present = sorted(sub["bucket"].unique())
    band_handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=col,
                                markeredgecolor="black", markersize=8.4, label=b)
                    for b, col in c.BAND_COLOR.items()]
    bucket_handles = [plt.Line2D([0], [0], marker=m, color="w", markerfacecolor="grey",
                                  markeredgecolor="black", markersize=8.4, label=c.BUCKET_LABEL[bk])
                      for bk, m in c.BUCKET_MARKER.items() if bk in buckets_present]
    c.legend_below_axes(fig, axes, band_handles + bucket_handles,
                         ncol=len(band_handles) + len(bucket_handles))
    fig.suptitle(f"{c.HAZARD_LABEL[hazard]} -- {c.SSP_LABEL[scen]}", fontsize=14.4, fontweight="bold")
    # compass rose LAST, after the shared legend has already shrunk the axes.
    fig.canvas.draw()
    for ax in axes:
        c.add_compass_rose(ax, redraw=False)
    c.save_figure(fig, out_path)


def run() -> list[c.ManifestEntry]:
    inv = c.load_inventory()
    rb = c.load_risk_bands(capacity=inv.set_index("plant_uid")["capacity_mw"])
    coords = c.load_coords()
    rb = rb.merge(coords, left_on="plant_uid", right_index=True, how="left")
    rb = rb[rb["hazard_term"].isin(MAP_HAZARDS)]
    cap_max = rb["capacity_mw"].max()

    files = []
    for scen in c.SSP_ORDER:
        for hazard in MAP_HAZARDS:
            if not ((rb["water_scenario"] == scen) & (rb["hazard_term"] == hazard)).any():
                continue
            out_png = c.maps_dir(scen) / f"riskband_map_{hazard}_{scen}.png"
            _plot(scen, hazard, rb, cap_max, out_png)
            files.append(str(out_png.relative_to(c.output_root())))

    return [c.ManifestEntry(
        item=ITEM, section="2. RiskBand asset map",
        caption="Geographic distribution of the fleet, marker shape = technology bucket, "
                "color = RiskBand_i,h, one figure per (SSP scenario, hazard), 3 country panels each.",
        source="data/outputs/tables/risk_bands.csv + risk_by_hazard.csv (lat/lon) + GADM boundaries "
               "(ADM0+ADM1, disputed-territory dashed outline)",
        files=files, status="generated",
        notes=f"{len(files)} files (1 per SSP scenario x hazard combination), each a "
              f"1x{len(c.COUNTRIES)} country-panel figure -- 2026-09-16 rework, max 3 maps/figure.",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
