"""
RESULTS_DRAFT.md Section 3.2 -- Risk_i,h intra-hazard comparison figure, one
panel per hazard, capacity-weighted asset markers colored/sized by Risk_i,h,
faceted by country and SSP scenario. Never blended across hazards (Methods
Section 9) -- one figure per hazard, one color scale per figure, never a
combined score. Source: risk_by_hazard.csv (already carries capacity_mw,
lat/lon, age_factor).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize

from src.reporting.results_draft import common as c

ITEM, SLUG = 5, "risk_intra_hazard_map"
ALL_HAZARDS = ["ws", "spei", "precip", "sv", "iv", "heat", "wind"]


def _plot(hazard: str, sub, out_path) -> None:
    countries = [co for co in c.COUNTRIES if (sub["country"] == co).any()]
    vmin, vmax = float(sub["risk_i_h"].min()), float(sub["risk_i_h"].max())
    norm = Normalize(vmin=vmin, vmax=vmax)
    cmap = c.SEQUENTIAL_CMAP

    fig, axes = plt.subplots(len(countries), 3, squeeze=False,
                              figsize=(3 * 4.2, 4.6 * len(countries)))
    for ri, country in enumerate(countries):
        for ci, scen in enumerate(c.SSP_ORDER):
            ax = axes[ri, ci]
            c.draw_country_boundary(ax, country)
            cell = sub[(sub["country"] == country) & (sub["water_scenario"] == scen)]
            for bucket in cell["bucket"].unique():
                bsub = cell[cell["bucket"] == bucket]
                ax.scatter(bsub["lon"], bsub["lat"], marker=c.BUCKET_MARKER[bucket],
                           c=bsub["risk_i_h"], cmap=cmap, norm=norm,
                           s=c.marker_sizes(bsub["capacity_mw"]),
                           edgecolor="black", linewidth=0.2, zorder=3)
            title = f"{country} -- {c.SSP_LABEL[scen]}" if ri == 0 or ci == 0 else c.SSP_LABEL[scen]
            c.panel_title(ax, title, len(cell))
    sm = ScalarMappable(norm=norm, cmap=cmap)
    fig.colorbar(sm, ax=axes.ravel().tolist(), shrink=0.6, label=f"Risk_i,h ({c.HAZARD_LABEL[hazard]})")
    bucket_handles = [plt.Line2D([0], [0], marker=m, color="w", markerfacecolor="grey",
                                  markeredgecolor="black", markersize=8, label=c.BUCKET_LABEL[bk])
                      for bk, m in c.BUCKET_MARKER.items() if bk in sub["bucket"].unique()]
    fig.legend(handles=bucket_handles, loc="lower center", ncol=len(bucket_handles), fontsize=8)
    fig.suptitle(f"Risk_i,h -- {c.HAZARD_LABEL[hazard]} (marker size = capacity MW; color = Risk_i,h; "
                 f"single hazard, never blended)", fontsize=11)
    # compass rose LAST, after colorbar/legend have already shrunk the axes --
    # see common.add_compass_rose's own docstring for why the order matters.
    fig.canvas.draw()
    for ax in axes.ravel():
        c.add_compass_rose(ax, redraw=False)
    c.save_figure(fig, out_path)


def run() -> list[c.ManifestEntry]:
    d = c.item_dir(ITEM, SLUG)
    rbh = c.load_risk_by_hazard()

    files = []
    for hazard in ALL_HAZARDS:
        sub = rbh[rbh["hazard_term"] == hazard].dropna(subset=["risk_i_h"])
        if sub.empty:
            continue
        out_png = d / f"risk_intra_hazard_map_{hazard}.png"
        _plot(hazard, sub, out_png)
        files.append(str(out_png.relative_to(d.parent.parent)))

    return [c.ManifestEntry(
        item=ITEM, section="3.2 Risk_i,h intra-hazard map",
        caption="Asset-level Risk_i,h for [hazard], capacity-weighted marker size, color = Risk_i,h, "
                "faceted by country and SSP scenario; never a cross-hazard sum.",
        source="data/outputs/tables/risk_by_hazard.csv",
        files=files, status="generated",
        notes=f"{len(files)} hazard panels (one figure per hazard, each with country x SSP subgrid).",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
