"""
RESULTS_DRAFT.md Section 7 -- threshold tier-provenance table (hazard,
bucket, tier, basis, absolute vs. sample-relative), one row per hazard/bucket
combination in every H_b. Source: src.index.risk_bands.THRESHOLD_REGISTRY
(the same Python constant ccrs_risk_bands_report.md's "Consolidated
tier/threshold table" section already renders) -- exported here as a clean,
standalone CSV/table asset rather than only as report-embedded markdown.
"""

from __future__ import annotations

import pandas as pd

from src.index import hazard_scope as hs
from src.index import risk_bands as rb
from src.reporting.results_draft import common as c

ITEM, SLUG = 16, "threshold_tier_provenance"


def run() -> list[c.ManifestEntry]:
    rows = []
    for (hazard, bucket), spec in sorted(rb.THRESHOLD_REGISTRY.items()):
        rows.append({
            "hazard": hazard, "hazard_label": hs.HAZARD_LABELS[hazard], "bucket": bucket,
            "tier": spec.tier, "kind": spec.kind,
            "absolute_or_sample_relative": "absolute" if spec.kind in ("absolute", "binary") else "sample-relative",
            "cuts": spec.cuts, "percentiles": spec.percentiles,
            "labels": spec.labels, "provisional": spec.provisional, "basis": spec.note,
        })
    table = pd.DataFrame(rows)
    out_csv = c.tables_dir() / "threshold_tier_provenance.csv"
    table.to_csv(out_csv, index=False)

    return [c.ManifestEntry(
        item=ITEM, section="7. Threshold tier-provenance",
        caption="Evidence-tier provenance for every RiskBand classification threshold: tier "
                "(1=absolute, 3=sample-relative percentile) and basis, one row per hazard/bucket "
                "combination in every H_b.",
        source="src.index.risk_bands.THRESHOLD_REGISTRY (Python constant, also rendered in "
               "ccrs_risk_bands_report.md)",
        files=[str(out_csv.relative_to(c.output_root()))], status="generated",
        notes=f"{len(table)} rows (one per hazard/bucket combination in every H_b).",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
