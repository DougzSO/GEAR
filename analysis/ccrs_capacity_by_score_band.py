"""
Diagnostic-only: installed capacity (MW) by technology, country, scenario and
**CCRS-score band**, for both configured GCMs.

Unlike ``analysis/ccrs_final_summary.py`` (a frozen pre-index-layer artifact),
this script runs the **production** assembly: it calls
``src.visualization.data.load_ccrs_final()``, which recomputes
``CCRS_{i,s} = Hazard_{i,s} * age_factor_i * EventMultiplier_c`` live from
``src/index/*`` (never a cached CSV), attaches the two production risk bands,
and flags the V6 computable base. Only the extra step here is binning the
numeric ``ccrs_{gcm}`` score.

--------------------------------------------------------------------------
Why this is a diagnostic, not a manuscript output
--------------------------------------------------------------------------
``analysis/climate_risk_score_spec.md`` Section 8.3 records that a single
discrete band on the whole ``CCRS_{i,s}`` score was tried
(``analysis/ccrs_band_classification.py`` / ``_v2.py``) and **rejected** in
favour of the two independently-cut bands (``WaterRiskBand`` +
``HeatRiskBand``), because one combined band forces the whole classification
onto the weaker of the two axes. This table deliberately applies that
rejected classification -- it is a score-distribution view for internal
reading, and must not be cited as the study's risk classification unless
Section 8.3 is revised.

--------------------------------------------------------------------------
Band cuts -- country-balanced p25 / p75 / p95
--------------------------------------------------------------------------
The production CCRS score scale differs sharply between countries (India's
higher hazards and its EventMultiplier of 1.5 push it far above Brazil and
Portugal). A single pooled percentile would land every cut inside India's
distribution and collapse Brazil/Portugal into "Low". So the cuts are the
**mean of the three per-country p25/p75/p95** (one vote per country, all
three scenarios pooled), the same country-balanced convention as
``analysis/ccrs_band_classification_v2.py``. Cuts are computed **per GCM**
(the ``ccrs_gfdl_esm4`` and ``ccrs_miroc6`` scales are not comparable).

    Low  < p25  <=  Medium  < p75  <=  High  < p95  <=  Extreme

--------------------------------------------------------------------------
Scenarios
--------------------------------------------------------------------------
The three paired water/heat trajectories the pipeline ran:
``opt`` = SSP1-2.6, ``bau`` = SSP3-7.0, ``pes`` = SSP5-8.5.

Standalone: ``python -m analysis.ccrs_capacity_by_score_band`` from the
project root. Writes ``analysis/ccrs_capacity_by_score_band.md``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from src.visualization import data  # noqa: E402

HERE = Path(__file__).resolve().parent
MD_OUT = HERE / "ccrs_capacity_by_score_band.md"

GCMS = ["gfdl_esm4", "miroc6"]
BANDS = ["Low", "Medium", "High", "Extreme"]
SCEN_LABEL = {"opt": "SSP1-2.6", "bau": "SSP3-7.0", "pes": "SSP5-8.5"}
SCEN_ORDER = ["opt", "bau", "pes"]
COUNTRY_ORDER = ["Brazil", "Portugal", "India"]
BUCKET_ORDER = ["hydro", "thermal", "wind", "solar"]
BUCKET_LABEL = {"hydro": "Hydro", "thermal": "Thermal", "wind": "Wind", "solar": "Solar"}
PCTLS = [25, 75, 95]


def _md_table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |",
           "| " + " | ".join("---" for _ in header) + " |"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def country_balanced_cuts(frame: pd.DataFrame, col: str) -> dict[int, float]:
    """Mean of the three per-country p25/p75/p95 of ``col`` (one vote per
    country, all scenarios pooled)."""
    per_country = {
        c: {p: float(np.percentile(g[col].dropna(), p)) for p in PCTLS}
        for c, g in frame.groupby("country")
    }
    return {p: float(np.mean([per_country[c][p] for c in COUNTRY_ORDER])) for p in PCTLS}


def assign_band(score: pd.Series, cuts: dict[int, float]) -> pd.Series:
    return pd.cut(
        score, bins=[-np.inf, cuts[25], cuts[75], cuts[95], np.inf], labels=BANDS,
    )


def _mw(frame: pd.DataFrame) -> str:
    return f"{float(frame['capacity_mw'].sum()):,.0f}"


def build_gcm_section(df: pd.DataFrame, gcm: str) -> str:
    col = f"ccrs_{gcm}"
    sub = df[df[col].notna()].copy()
    cuts = country_balanced_cuts(sub, col)
    sub["band"] = assign_band(sub[col], cuts)

    lines = [
        f"## {gcm} — capacity (MW) by technology and CCRS-score band\n",
        f"Country-balanced cuts on `{col}`: "
        f"**Low** < {cuts[25]:.3f} · **Medium** {cuts[25]:.3f}–{cuts[75]:.3f} · "
        f"**High** {cuts[75]:.3f}–{cuts[95]:.3f} · **Extreme** ≥ {cuts[95]:.3f}\n",
    ]

    rows = []
    for country in COUNTRY_ORDER:
        for scen in SCEN_ORDER:
            for bucket in BUCKET_ORDER:
                s = sub[(sub["country"] == country)
                        & (sub["water_scenario"] == scen)
                        & (sub["bucket"] == bucket)]
                if s.empty:
                    continue
                by_band = s.groupby("band", observed=False)["capacity_mw"].sum()
                rows.append(
                    [country, f"{scen} ({SCEN_LABEL[scen]})", BUCKET_LABEL[bucket]]
                    + [f"{by_band.get(b, 0.0):,.0f}" for b in BANDS]
                    + [_mw(s)]
                )
    lines.append(_md_table(
        ["Country", "Scenario", "Technology"] + BANDS + ["Total"], rows))

    lines.append("\n### All technologies pooled\n")
    rows = []
    for country in COUNTRY_ORDER:
        for scen in SCEN_ORDER:
            s = sub[(sub["country"] == country) & (sub["water_scenario"] == scen)]
            by_band = s.groupby("band", observed=False)["capacity_mw"].sum()
            rows.append(
                [country, f"{scen} ({SCEN_LABEL[scen]})"]
                + [f"{by_band.get(b, 0.0):,.0f}" for b in BANDS]
                + [_mw(s)]
            )
    lines.append(_md_table(["Country", "Scenario"] + BANDS + ["Total"], rows))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    df = data.load_ccrs_final()
    df = df[df["water_scenario"].isin(SCEN_ORDER)].copy()

    n_nan = {g: int(df[f"ccrs_{g}"].isna().sum()) for g in GCMS}

    lines = ["# CCRS score bands — installed capacity by technology\n"]
    lines.append(
        "**Diagnostic only.** Capacity (MW) of each technology falling in each "
        "band of the numeric CCRS score, per country and scenario, for both "
        "GCMs. Regenerated live from `src/index/*` via "
        "`src.visualization.data.load_ccrs_final()` (never a cached CSV).\n"
    )
    lines.append(
        "> ⚠️ `analysis/climate_risk_score_spec.md` Section 8.3 records that a "
        "single band on the whole CCRS score was **tried and rejected** in "
        "favour of the two independent bands (WaterRiskBand + HeatRiskBand). "
        "This table applies the rejected classification — use it as an "
        "internal score-distribution view, not a manuscript methodology "
        "output, unless Section 8.3 is revised.\n"
    )
    lines.append(
        "Bands: country-balanced percentiles of the score — the mean of the "
        "three per-country p25/p75/p95 (one vote per country, all scenarios "
        "pooled), computed separately per GCM (same convention as "
        "`analysis/ccrs_band_classification_v2.py`). Scenarios are the paired "
        "water/heat trajectories: `opt` = SSP1-2.6, `bau` = SSP3-7.0, "
        "`pes` = SSP5-8.5. Plants with an undefined CCRS "
        f"(GFDL-ESM4 {n_nan['gfdl_esm4']}, MIROC6 {n_nan['miroc6']} of "
        f"{len(df):,} plant-scenario rows — thermal cells outside any "
        "Aqueduct basin) are excluded, so per-GCM totals differ by < 0.1%. "
        "MW rounded to whole numbers.\n"
    )

    for gcm in GCMS:
        lines.append(build_gcm_section(df, gcm))

    MD_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {MD_OUT.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
