"""
RESULTS_DRAFT.md Section 7 -- FROZEN_BOUNDS origin table (variable, bounds,
origin, tier, skewness, Shapiro-Wilk, transform), one row per hazard with a
processed raster. Source: normalization_origin_table.csv (src/index/
normalization.py output) -- copied through with renamed, article-ready
columns, no values recomputed or altered.
"""

from __future__ import annotations

from src.reporting.results_draft import common as c

ITEM, SLUG = 15, "normalization_provenance"


def run() -> list[c.ManifestEntry]:
    table = c.load_normalization_origin()

    out_csv = c.tables_dir() / "normalization_provenance.csv"
    table.to_csv(out_csv, index=False)

    return [c.ManifestEntry(
        item=ITEM, section="7. FROZEN_BOUNDS provenance",
        caption="Provenance table for every Min-Max normalization bound (FROZEN_BOUNDS): pooled "
                "sample min/max, tier, Fisher-Pearson skewness, Shapiro-Wilk diagnostic, transform.",
        source="data/outputs/tables/normalization_origin_table.csv",
        files=[str(out_csv.relative_to(c.output_root()))], status="generated",
        notes=f"{len(table)} rows (one per hazard/GCM origin combination).",
    )]


if __name__ == "__main__":
    for e in run():
        print(e)
