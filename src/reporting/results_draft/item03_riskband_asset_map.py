"""
RESULTS_DRAFT.md Section 2 -- per-hazard, per-country RiskBand asset map
(point symbology, technology-differentiated markers, colored by RiskBand).
Source: risk_bands.csv (T4) joined to per-plant lat/lon (risk_by_hazard.csv).

Consolidation (2026-09-15 rework, matching the legacy maps.py convention
documented in docs/_audit/2026-09-15_phase7_legacy_maps_audit.md Section 4):
**one figure per SSP scenario**, not per country x hazard. Each figure is a
grid of country (rows) x hazard (columns) panels -- 3 files total instead of
the previous 18 (one per country x hazard). Hazards stay in separate panels
with their own axis (never summed/blended, Methods Section 9); putting them
in columns of the same figure is a layout choice, not a combined score --
every panel keeps the same Low/Medium/High/Extreme legend, so no cross-
hazard color-scale distortion is introduced.

Extreme Wind is excluded here (its own single-column figure is item04, per
the draft's explicit instruction not to repeat three near-duplicate SSP
columns for a scenario-invariant hazard).

Disputed-territory treatment (dashed ADM1 outline, no footer disclaimer,
2026-09-06 author decision) is applied uniformly via
``common.draw_country_boundary`` -- India panels are never a special case.
"""

from __future__ import annotations

import matplotlib.pyplot as plt

from src.reporting.results_draft import common as c

ITEM, SLUG = 3, "riskband_asset_map"
MAP_HAZARDS = ["ws", "spei", "precip", "sv", "iv", "heat"]  # wind handled by item04
OLD_FILENAMES_SUPERSEDED = [
    f"riskband_map_{country.lower()}_{hazard}.png"
    for country in c.COUNTRIES for hazard in MAP_HAZARDS
]  # 18 files, one per (country, hazard) -- pre-2026-09-15-rework layout


def _panel(ax, country: str, hazard: str, sub, show_country: bool) -> None:
    c.draw_country_boundary(ax, country)
    n_plotted = 0
    for bucket in sub["bucket"].unique():
        bsub = sub[sub["bucket"] == bucket]
        for band in c.BAND_ORDER:
            cell = bsub[bsub["risk_band"] == band]
            if cell.empty:
                continue
            n_plotted += len(cell)
            ax.scatter(cell["lon"], cell["lat"], marker=c.BUCKET_MARKER[bucket],
                       color=c.BAND_COLOR[band], s=c.marker_sizes(cell["capacity_mw"]),
                       edgecolor="black", linewidth=0.2, zorder=3)
    # country printed once per row (y-axis label of the leftmost column),
    # never repeated in every panel's title -- the prior 2026-09-15 layout put
    # "Country -- Hazard" on every panel and the two overlapped in a 6-column
    # grid (titles wider than the narrow panels).
    if show_country:
        ax.set_ylabel(f"{country}\nLatitude", fontsize=8, fontweight="bold")
    c.panel_title(ax, c.HAZARD_LABEL[hazard], n_plotted, fontsize=7.5)


def _plot_scenario(scen: str, merged, out_path) -> None:
    countries_present = [co for co in c.COUNTRIES if (merged["country"] == co).any()]
    hazards_present = [h for h in MAP_HAZARDS if (merged["hazard_term"] == h).any()]
    n_rows, n_cols = len(countries_present), len(hazards_present)

    fig, axes = plt.subplots(n_rows, n_cols, squeeze=False, figsize=(3.6 * n_cols, 4.2 * n_rows))
    scen_df = merged[merged["water_scenario"] == scen]
    for ri, country in enumerate(countries_present):
        for ci, hazard in enumerate(hazards_present):
            sub = scen_df[(scen_df["country"] == country) & (scen_df["hazard_term"] == hazard)]
            _panel(axes[ri, ci], country, hazard, sub, show_country=(ci == 0))

    buckets_present = sorted(merged["bucket"].unique())
    band_handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=col,
                                markeredgecolor="black", markersize=7, label=b)
                    for b, col in c.BAND_COLOR.items()]
    bucket_handles = [plt.Line2D([0], [0], marker=m, color="w", markerfacecolor="grey",
                                  markeredgecolor="black", markersize=7, label=c.BUCKET_LABEL[bk])
                      for bk, m in c.BUCKET_MARKER.items() if bk in buckets_present]
    fig.legend(handles=band_handles + bucket_handles, loc="lower center",
               ncol=len(band_handles) + len(bucket_handles), fontsize=7, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle(f"RiskBand_i,h asset map -- {c.SSP_LABEL[scen]} "
                 f"(rows: country, columns: hazard -- never blended, same legend throughout)",
                 fontsize=11)
    fig.tight_layout(rect=[0, 0.03, 1, 0.96])
    # compass rose LAST, after the shared legend has already shrunk the axes.
    # One canvas.draw() for the whole grid (not one per panel) -- the rose
    # itself never changes any axes' bbox, so a single upfront draw is safe
    # and avoids O(n^2) redraw cost on this up-to-18-panel grid.
    fig.canvas.draw()
    for ax in axes.ravel():
        c.add_compass_rose(ax, redraw=False)
    c.save_figure(fig, out_path)


def run() -> list[c.ManifestEntry]:
    d = c.item_dir(ITEM, SLUG)
    inv = c.load_inventory()
    rb = c.load_risk_bands(capacity=inv.set_index("plant_uid")["capacity_mw"])
    coords = c.load_coords()
    rb = rb.merge(coords, left_on="plant_uid", right_index=True, how="left")
    rb = rb[rb["hazard_term"].isin(MAP_HAZARDS)]

    files = []
    for scen in c.SSP_ORDER:
        out_png = d / f"riskband_map_by_ssp_scenario_{scen}.png"
        _plot_scenario(scen, rb, out_png)
        files.append(str(out_png.relative_to(d.parent.parent)))

    return [c.ManifestEntry(
        item=ITEM, section="2. RiskBand asset map",
        caption="Geographic distribution of the fleet, marker shape = technology bucket, "
                "color = RiskBand_i,h, one figure per SSP scenario (country rows x hazard columns).",
        source="data/outputs/tables/risk_bands.csv + risk_by_hazard.csv (lat/lon) + GADM boundaries "
               "(ADM0+ADM1, disputed-territory dashed outline)",
        files=files, status="generated",
        notes=f"Consolidated 2026-09-15: 3 files (1/scenario), each a "
              f"{len(c.COUNTRIES)}x{len(MAP_HAZARDS)} country x hazard grid -- supersedes 18 "
              f"per-(country,hazard) files from the prior layout: {', '.join(OLD_FILENAMES_SUPERSEDED)}.",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
