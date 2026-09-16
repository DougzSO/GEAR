"""
RESULTS_DRAFT.md Section 3.2 -- Risk_i,h intra-hazard comparison figure,
capacity-weighted asset markers colored/sized by Risk_i,h. Never blended
across hazards (Methods Section 9) -- one figure per (hazard, SSP scenario)
combination, 3 country panels side by side, one color scale per hazard
(shared across that hazard's 3 scenario figures for comparability). Source:
risk_by_hazard.csv (already carries capacity_mw, lat/lon, age_factor).

Layout (2026-09-16 rework, matching item04's country-column convention):
never more than 3 maps per figure, never a country x scenario grid.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

from src.reporting.results_draft import common as c

ITEM, SLUG = 5, "risk_intra_hazard_map"
ALL_HAZARDS = ["ws", "spei", "precip", "sv", "iv", "heat", "wind"]


def _plot(hazard: str, scen: str, sub_hazard, norm: Normalize, cap_max: float, out_path) -> None:
    cmap = c.SEQUENTIAL_CMAP
    sub = sub_hazard[sub_hazard["water_scenario"] == scen]
    countries = [co for co in c.COUNTRIES if (sub["country"] == co).any()]
    # constrained_layout (via make_country_row_figure) is colorbar-aware -- fig.colorbar(ax=list)
    # here just works, unlike tight_layout which explicitly does not understand colorbar axes
    # and previously needed a hand-built GridSpec column to avoid overlapping the last panel.
    fig, axes = c.make_country_row_figure(countries)

    for ax, country in zip(axes, countries):
        c.draw_country_boundary(ax, country)
        cell = sub[sub["country"] == country]
        for bucket in cell["bucket"].unique():
            bsub = cell[cell["bucket"] == bucket]
            ax.scatter(bsub["lon"], bsub["lat"], marker=c.BUCKET_MARKER[bucket],
                       c=bsub["risk_i_h"], cmap=cmap, norm=norm,
                       s=c.marker_sizes(bsub["capacity_mw"], capacity_max=cap_max),
                       edgecolor="black", linewidth=0.2, alpha=c.MARKER_ALPHA, zorder=3)
        c.panel_title(ax, country, len(cell))

    sm = ScalarMappable(norm=norm, cmap=cmap)
    cbar = fig.colorbar(sm, ax=axes, shrink=0.8, label=f"Risk_i,h ({c.HAZARD_LABEL[hazard]})")
    cbar.ax.yaxis.label.set_fontsize(9.6)
    cbar.ax.tick_params(labelsize=7.2)
    bucket_handles = [plt.Line2D([0], [0], marker=m, color="w", markerfacecolor="grey",
                                  markeredgecolor="black", markersize=8.4, label=c.BUCKET_LABEL[bk])
                      for bk, m in c.BUCKET_MARKER.items() if bk in sub_hazard["bucket"].unique()]
    c.legend_below_axes(fig, axes, bucket_handles, ncol=len(bucket_handles))
    fig.suptitle(f"Risk_i,h -- {c.HAZARD_LABEL[hazard]} ({c.SSP_LABEL[scen]})", fontsize=14.4, fontweight="bold")
    # compass rose LAST, after colorbar/legend have already shrunk the axes.
    fig.canvas.draw()
    for ax in axes:
        c.add_compass_rose(ax, redraw=False)
    c.save_figure(fig, out_path)


def run() -> list[c.ManifestEntry]:
    rbh = c.load_risk_by_hazard()
    cap_max = rbh["capacity_mw"].max()

    files = []
    for hazard in ALL_HAZARDS:
        sub_hazard = rbh[rbh["hazard_term"] == hazard].dropna(subset=["risk_i_h"])
        if sub_hazard.empty:
            continue
        # one color scale per hazard, shared across its 3 scenario figures
        norm = Normalize(vmin=float(sub_hazard["risk_i_h"].min()), vmax=float(sub_hazard["risk_i_h"].max()))
        for scen in c.SSP_ORDER:
            if not (sub_hazard["water_scenario"] == scen).any():
                continue
            out_png = c.maps_dir(scen) / f"risk_intra_hazard_map_{hazard}_{scen}.png"
            _plot(hazard, scen, sub_hazard, norm, cap_max, out_png)
            files.append(str(out_png.relative_to(c.output_root())))

    return [c.ManifestEntry(
        item=ITEM, section="3.2 Risk_i,h intra-hazard map",
        caption="Asset-level Risk_i,h, capacity-weighted marker size, color = Risk_i,h (one scale per "
                "hazard), one figure per (hazard, SSP scenario), 3 country panels each; never a "
                "cross-hazard sum.",
        source="data/outputs/tables/risk_by_hazard.csv",
        files=files, status="generated",
        notes=f"{len(files)} files (1 per hazard x SSP scenario combination) -- 2026-09-16 rework, "
              f"max 3 maps/figure.",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
