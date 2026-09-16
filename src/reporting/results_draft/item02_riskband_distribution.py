"""
RESULTS_DRAFT.md Section 2 -- per-hazard RiskBand_i,h distribution (count and
MW-share), faceted by country x bucket x SSP scenario. Hazards are never
summed (each hazard is its own bar group). Source: risk_bands.csv (T4) +
ccrs_age_factors.csv (capacity_mw, T2).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.reporting.results_draft import common as c

ITEM, SLUG = 2, "riskband_distribution"
BAND_COLORS = c.BAND_COLOR


def _build_table(inv: pd.DataFrame, rb: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for country in c.COUNTRIES:
        for bucket in c.BUCKET_ORDER:
            bucket_cap = inv.loc[(inv["country"] == country) & (inv["bucket"] == bucket), "capacity_mw"].sum()
            bucket_n = int(((inv["country"] == country) & (inv["bucket"] == bucket)).sum())
            if bucket_cap == 0:
                continue
            for hazard in c.BUCKET_HAZARDS[bucket]:
                sub_h = rb[(rb["country"] == country) & (rb["bucket"] == bucket) & (rb["hazard_term"] == hazard)]
                for scen in c.SSP_ORDER:
                    sub = sub_h[sub_h["water_scenario"] == scen]
                    n_missing = int(sub["risk_band"].isna().sum())
                    for band in c.BAND_ORDER:
                        band_cap = sub.loc[sub["risk_band"] == band, "capacity_mw"].sum()
                        band_n = int((sub["risk_band"] == band).sum())
                        rows.append({
                            "country": country, "bucket": bucket, "hazard": hazard,
                            "hazard_label": c.HAZARD_LABEL[hazard], "scenario": scen,
                            "ssp": c.SSP_LABEL[scen], "band": band,
                            "n_plants": band_n, "capacity_mw": round(float(band_cap), 3),
                            "pct_of_bucket_capacity": round(100 * band_cap / bucket_cap, 3),
                            "n_missing_band": n_missing, "bucket_total_capacity_mw": round(float(bucket_cap), 3),
                            "bucket_n_plants": bucket_n,
                        })
    return pd.DataFrame(rows)


def _plot_country(country: str, table: pd.DataFrame, out_path) -> None:
    buckets = [b for b in c.BUCKET_ORDER if (table["country"] == country).any() and
               ((table["country"] == country) & (table["bucket"] == b)).any()]
    max_hazards = max(len(c.BUCKET_HAZARDS[b]) for b in buckets)
    fig, axes = plt.subplots(len(buckets), 1, figsize=(3.2 * max_hazards, 3.2 * len(buckets)), squeeze=False)
    for i, bucket in enumerate(buckets):
        ax = axes[i, 0]
        hazards = c.BUCKET_HAZARDS[bucket]
        sub = table[(table["country"] == country) & (table["bucket"] == bucket)]
        x_labels = []
        x_pos = []
        pos = 0
        width = 0.25
        for hi, hazard in enumerate(hazards):
            for si, scen in enumerate(c.SSP_ORDER):
                cell = sub[(sub["hazard"] == hazard) & (sub["scenario"] == scen)]
                bottom = 0.0
                for band in c.BAND_ORDER:
                    val = cell.loc[cell["band"] == band, "pct_of_bucket_capacity"]
                    v = float(val.iloc[0]) if len(val) else 0.0
                    ax.bar(pos, v, width=width, bottom=bottom, color=BAND_COLORS[band],
                           edgecolor="white", linewidth=0.3)
                    bottom += v
                x_pos.append(pos)
                x_labels.append(c.SSP_LABEL[scen].replace("SSP", ""))
                pos += width
            pos += width * 0.8
        ax.set_xticks(x_pos)
        ax.set_xticklabels(x_labels, fontsize=6, rotation=0)
        ax.set_ylim(0, 100)
        ax.set_ylabel("% bucket capacity")
        ax.set_title(f"{c.BUCKET_LABEL[bucket]} -- hazards: {', '.join(c.HAZARD_LABEL[h] for h in hazards)}",
                     fontsize=8)
    handles = [plt.Rectangle((0, 0), 1, 1, color=col) for col in BAND_COLORS.values()]
    fig.legend(handles, list(BAND_COLORS.keys()), loc="lower center", ncol=4, fontsize=8,
               bbox_to_anchor=(0.5, -0.02 / max(1, len(buckets))))
    fig.suptitle(f"{country} -- RiskBand_i,h distribution by hazard x SSP scenario (bars grouped "
                 f"per hazard: SSP1-2.6/SSP3-7.0/SSP5-8.5)", fontsize=10)
    fig.tight_layout(rect=[0, 0.03, 1, 0.96])
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def run() -> list[c.ManifestEntry]:
    inv = c.load_inventory()
    rb = c.load_risk_bands(capacity=inv.set_index("plant_uid")["capacity_mw"])

    table = _build_table(inv, rb)
    out_csv = c.tables_dir() / "riskband_distribution.csv"
    table.to_csv(out_csv, index=False)

    files = [str(out_csv.relative_to(c.output_root()))]
    for country in c.COUNTRIES:
        out_png = c.other_dir() / f"riskband_distribution_{country.lower()}.png"
        _plot_country(country, table, out_png)
        files.append(str(out_png.relative_to(c.output_root())))

    return [c.ManifestEntry(
        item=ITEM, section="2. RiskBand distribution",
        caption="Distribution of RiskBand_i,h classifications (Low/Medium/High/Extreme) by hazard, "
                "technology bucket, country, and SSP scenario; plant count and MW-share.",
        source="data/outputs/tables/risk_bands.csv + ccrs_age_factors.csv",
        files=files, status="generated",
        notes=f"{len(table)} (country,bucket,hazard,scenario,band) rows.",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
