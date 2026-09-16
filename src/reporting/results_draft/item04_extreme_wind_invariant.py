"""
RESULTS_DRAFT.md Section 3.1 -- Extreme Wind, scenario-invariant structural
exposure. Single-column display (not three near-duplicate SSP columns), by
country and bucket (Wind, Solar). Asserts (fail-loud, not silently
tolerated) that risk_band and risk_i_h for hazard=wind are identical across
all three water_scenario values before rendering -- this figure's entire
premise is that invariance, so it must never render a false claim of it.

Consolidation (2026-09-15 rework): since this hazard has no scenario axis at
all, there is nothing to split by scenario -- the three prior per-country
files collapse into **one figure**, countries as subplots (matching the
legacy maps.py "_render_country_row_figure" convention, docs/_audit/
2026-09-15_phase7_legacy_maps_audit.md Section 4).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from src.reporting.results_draft import common as c

ITEM, SLUG = 4, "extreme_wind_invariant"
OLD_FILENAMES_SUPERSEDED = [f"extreme_wind_invariant_{country.lower()}.png" for country in c.COUNTRIES]


def _assert_static(rb_wind: pd.DataFrame, rbh_wind: pd.DataFrame) -> None:
    band_pivot = rb_wind.pivot(index="plant_uid", columns="water_scenario", values="risk_band")
    n_varies_band = int((band_pivot.nunique(axis=1, dropna=True) > 1).sum())
    if n_varies_band:
        raise AssertionError(
            f"Extreme Wind RiskBand varies across water_scenario for {n_varies_band} plants -- "
            f"the SSP-invariance premise of this figure does not hold on this data, refusing to "
            f"render a false claim of static exposure."
        )
    risk_pivot = rbh_wind.pivot_table(index="plant_uid", columns="water_scenario", values="risk_i_h")
    max_spread = (risk_pivot.max(axis=1) - risk_pivot.min(axis=1)).max()
    if max_spread is not None and max_spread > 1e-9:
        raise AssertionError(
            f"Extreme Wind Risk_i,h varies across water_scenario (max spread {max_spread}) -- "
            f"refusing to render a false claim of static exposure."
        )


def run() -> list[c.ManifestEntry]:
    d = c.item_dir(ITEM, SLUG)
    rb = c.load_risk_bands()
    rbh = c.load_risk_by_hazard()
    coords = c.load_coords()

    rb_wind = rb[rb["hazard_term"] == "wind"]
    rbh_wind = rbh[rbh["hazard_term"] == "wind"]
    _assert_static(rb_wind, rbh_wind)

    single = rb_wind.drop_duplicates("plant_uid")[["plant_uid", "country", "bucket", "risk_band"]]
    single = single.merge(
        rbh_wind.drop_duplicates("plant_uid")[["plant_uid", "risk_i_h", "capacity_mw", "age_factor"]],
        on="plant_uid", how="left",
    ).merge(coords, left_on="plant_uid", right_index=True, how="left")

    out_csv = d / "extreme_wind_invariant.csv"
    single.to_csv(out_csv, index=False)

    countries_present = [co for co in c.COUNTRIES if (single["country"] == co).any()]
    widths = [c.aspect_ratio_width(co, 5.5) for co in countries_present]
    fig, axes = plt.subplots(1, len(countries_present), squeeze=False,
                              figsize=(sum(widths), 5.5))
    for ax, country in zip(axes[0], countries_present):
        sub = single[single["country"] == country]
        c.draw_country_boundary(ax, country)
        for bucket in sub["bucket"].unique():
            bsub = sub[sub["bucket"] == bucket]
            for band in c.WIND_BAND_ORDER:
                cell = bsub[bsub["risk_band"] == band]
                if cell.empty:
                    continue
                ax.scatter(cell["lon"], cell["lat"], marker=c.BUCKET_MARKER[bucket],
                           color=c.WIND_BAND_COLOR[band], s=c.marker_sizes(cell["capacity_mw"]),
                           edgecolor="black", linewidth=0.3, zorder=3)
        c.panel_title(ax, country, sub.shape[0])

    buckets_present = sorted(single["bucket"].unique())
    handles = [plt.Line2D([0], [0], marker="o", color="w", markerfacecolor=c.WIND_BAND_COLOR[b],
                           markeredgecolor="black", markersize=8, label=b) for b in c.WIND_BAND_ORDER]
    handles += [plt.Line2D([0], [0], marker=m, color="w", markerfacecolor="grey",
                            markeredgecolor="black", markersize=8, label=c.BUCKET_LABEL[bk])
                for bk, m in c.BUCKET_MARKER.items() if bk in buckets_present]
    fig.legend(handles=handles, loc="lower center", ncol=len(handles), fontsize=8, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Extreme Wind Risk_i,h/RiskBand (ERA5, scenario-invariant, single column; "
                 "Wind + Solar buckets)", fontsize=11)
    fig.tight_layout(rect=[0, 0.04, 1, 0.94])
    fig.canvas.draw()
    for ax in axes[0]:
        c.add_compass_rose(ax, redraw=False)
    out_png = d / "extreme_wind_invariant_map_by_country.png"
    c.save_figure(fig, out_png)

    files = [str(out_csv.relative_to(d.parent.parent)), str(out_png.relative_to(d.parent.parent))]

    return [c.ManifestEntry(
        item=ITEM, section="3.1 Extreme Wind (SSP-invariant)",
        caption="Extreme Wind's Risk_i,h/RiskBand/PSAE contribution shown as a single value per "
                "plant (ERA5, 1991-2020), not three near-duplicate SSP columns.",
        source="data/outputs/tables/risk_bands.csv + risk_by_hazard.csv",
        files=files, status="generated",
        notes=f"Static-ness asserted programmatically (fail-loud) before rendering, not assumed. "
              f"Consolidated 2026-09-15: 1 file (countries as subplots) -- supersedes 3 per-country "
              f"files from the prior layout: {', '.join(OLD_FILENAMES_SUPERSEDED)}.",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
