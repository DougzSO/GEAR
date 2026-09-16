"""
RESULTS_DRAFT.md Section 5 -- PSAE_i band distribution (EXTREME/HIGH/MEDIUM/
LOW, plant count and MW-share), one panel per bucket, faceted by country and
SSP scenario. Never combined on a shared color scale across buckets (Methods
Section 6.2 / 9) -- every panel below is drawn and read independently.
Source: psae.csv (``python -m src.index.psae``) + ccrs_age_factors.csv
(capacity_mw).
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from src.reporting.results_draft import common as c

ITEM, SLUG = 12, "psae_distribution"


def _build_table(inv: pd.DataFrame, psae: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for country in c.COUNTRIES:
        for bucket in c.BUCKET_ORDER:
            sub_b = psae[(psae["country"] == country) & (psae["bucket"] == bucket)]
            if sub_b.empty:
                continue
            for scen in c.SSP_ORDER:
                sub = sub_b[sub_b["water_scenario"] == scen]
                total_cap = sub["capacity_mw"].sum()
                complete = sub[sub["psae_complete"]]
                incomplete_cap = sub.loc[~sub["psae_complete"], "capacity_mw"].sum()
                for label in c.PSAE_LABELS:
                    lab_cap = complete.loc[complete["psae_label"] == label, "capacity_mw"].sum()
                    lab_n = int((complete["psae_label"] == label).sum())
                    rows.append({
                        "country": country, "bucket": bucket, "scenario": scen, "ssp": c.SSP_LABEL[scen],
                        "psae_label": label, "n_plants": lab_n, "capacity_mw": round(float(lab_cap), 3),
                        "pct_of_bucket_capacity": round(100 * lab_cap / total_cap, 3) if total_cap else None,
                    })
                rows.append({
                    "country": country, "bucket": bucket, "scenario": scen, "ssp": c.SSP_LABEL[scen],
                    "psae_label": "INCOMPLETE", "n_plants": int((~sub["psae_complete"]).sum()),
                    "capacity_mw": round(float(incomplete_cap), 3),
                    "pct_of_bucket_capacity": round(100 * incomplete_cap / total_cap, 3) if total_cap else None,
                })
    return pd.DataFrame(rows)


def _plot_bucket(bucket: str, table: pd.DataFrame, out_path) -> None:
    labels = c.PSAE_LABELS + ["INCOMPLETE"]
    colors = {**c.PSAE_COLOR, "INCOMPLETE": "#adb5bd"}
    sub_b = table[table["bucket"] == bucket]
    countries = [co for co in c.COUNTRIES if (sub_b["country"] == co).any()]

    fig, axes = plt.subplots(1, len(countries), figsize=(4 * len(countries), 4.5), squeeze=False)
    for ax, country in zip(axes[0], countries):
        sub = sub_b[sub_b["country"] == country]
        for si, scen in enumerate(c.SSP_ORDER):
            cell = sub[sub["scenario"] == scen]
            bottom = 0.0
            for label in labels:
                val = cell.loc[cell["psae_label"] == label, "pct_of_bucket_capacity"]
                v = float(val.iloc[0]) if len(val) and pd.notna(val.iloc[0]) else 0.0
                ax.bar(si, v, bottom=bottom, color=colors[label], width=0.6, edgecolor="white", linewidth=0.3)
                bottom += v
        ax.set_xticks(range(len(c.SSP_ORDER)))
        ax.set_xticklabels([c.SSP_LABEL[s].replace("SSP", "") for s in c.SSP_ORDER], fontsize=8)
        ax.set_ylim(0, 100)
        ax.set_title(country, fontsize=9)
        ax.set_ylabel("% bucket capacity")
    handles = [plt.Rectangle((0, 0), 1, 1, color=colors[l]) for l in labels]
    fig.legend(handles, labels, loc="lower center", ncol=len(labels), fontsize=8, bbox_to_anchor=(0.5, -0.03))
    fig.suptitle(f"PSAE_i distribution -- {c.BUCKET_LABEL[bucket]} (H_b size = {len(c.BUCKET_HAZARDS[bucket])}, "
                 f"{'compressed LOW/EXTREME scheme' if bucket == 'wind' else 'LOW/MEDIUM/HIGH/EXTREME'})",
                 fontsize=11)
    fig.tight_layout(rect=[0, 0.05, 1, 0.93])
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def run() -> list[c.ManifestEntry]:
    inv = c.load_inventory()
    psae = c.load_psae(capacity=inv.set_index("plant_uid")["capacity_mw"])

    table = _build_table(inv, psae)
    out_csv = c.tables_dir() / "psae_distribution.csv"
    table.to_csv(out_csv, index=False)

    files = [str(out_csv.relative_to(c.output_root()))]
    for bucket in c.BUCKET_ORDER:
        out_png = c.other_dir() / f"psae_distribution_{bucket}.png"
        _plot_bucket(bucket, table, out_png)
        files.append(str(out_png.relative_to(c.output_root())))

    coverage = psae.groupby(["bucket", "country"])["psae_complete"].agg(["sum", "count"])
    coverage["incomplete_fraction"] = 1 - coverage["sum"] / coverage["count"]
    out_cov = c.tables_dir() / "psae_coverage.csv"
    coverage.to_csv(out_cov)
    files.append(str(out_cov.relative_to(c.output_root())))

    return [c.ManifestEntry(
        item=ITEM, section="5. PSAE distribution",
        caption="Distribution of PSAE_i classifications, one panel per bucket (Hydro/Thermal/Solar "
                "4-band; Wind 2-band), by country and SSP scenario, with psae_complete coverage.",
        source="data/outputs/tables/psae.csv + ccrs_age_factors.csv",
        files=files, status="generated",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
