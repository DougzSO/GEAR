"""
RESULTS_DRAFT.md Section 3.2 -- Top-N asset risk ranking table per hazard, per
country (Risk_i,h, MW, RiskBand, age_factor). Rankings are hazard-specific,
never compared across the hazard panels in this table set. Source:
risk_by_hazard.csv (Risk_i,h, capacity, age_factor) joined to risk_bands.csv
(RiskBand_i,h label).
"""

from __future__ import annotations

import pandas as pd

from src.reporting.results_draft import common as c

ITEM, SLUG = 6, "risk_topn_table"
TOP_N = 10
ALL_HAZARDS = ["ws", "spei", "precip", "sv", "iv", "heat", "wind"]


def run() -> list[c.ManifestEntry]:
    rbh = c.load_risk_by_hazard()
    rb = c.load_risk_bands()[["plant_uid", "water_scenario", "hazard_term", "risk_band"]]

    merged = rbh.merge(rb, on=["plant_uid", "water_scenario", "hazard_term"], how="left")

    rows = []
    for country in c.COUNTRIES:
        for hazard in ALL_HAZARDS:
            for scen in c.SSP_ORDER:
                sub = merged[(merged["country"] == country) & (merged["hazard_term"] == hazard) &
                             (merged["water_scenario"] == scen)]
                sub = sub.dropna(subset=["risk_i_h"]).sort_values("risk_i_h", ascending=False).head(TOP_N)
                for rank, r in enumerate(sub.itertuples(index=False), 1):
                    rows.append({
                        "country": country, "hazard": hazard, "hazard_label": c.HAZARD_LABEL[hazard],
                        "scenario": scen, "ssp": c.SSP_LABEL[scen], "rank": rank,
                        "plant_uid": r.plant_uid, "plant_name": r.plant_name, "bucket": r.bucket,
                        "capacity_mw": r.capacity_mw, "age_factor": r.age_factor,
                        "hazard_i_h": r.hazard_i_h, "risk_i_h": r.risk_i_h, "risk_band": r.risk_band,
                    })
    table = pd.DataFrame(rows)
    out_csv = c.tables_dir() / "risk_topn_table.csv"
    table.to_csv(out_csv, index=False)

    return [c.ManifestEntry(
        item=ITEM, section="3.2 Top-N asset ranking",
        caption=f"Top-{TOP_N} highest-Risk_i,h assets per hazard, per country, per SSP scenario "
                f"(capacity, age_factor, Hazard_i,h, Risk_i,h, RiskBand). Hazard-specific, not "
                f"cross-hazard comparable.",
        source="data/outputs/tables/risk_by_hazard.csv + risk_bands.csv",
        files=[str(out_csv.relative_to(c.output_root()))], status="generated",
        notes=f"{len(table)} rows ({len(c.COUNTRIES)} countries x {len(ALL_HAZARDS)} hazards x "
              f"3 scenarios x up to {TOP_N}).",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
