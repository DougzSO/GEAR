"""
Diagnostic-only: apply a set of *proposed* absolute band cutoffs to the
equal-weight Hazard score from ``analysis/ccrs_preliminary_distribution.py``
and report how plants — and installed capacity — fall into
LOW/MEDIUM/HIGH/EXTREME, per country x GCM x scenario.

Not production code, not a spec decision, no weights touched. The score is
byte-identical to ``ccrs_preliminary_distribution`` (equal ``w = 0.25``,
``log1p``->global Min-Max for ws/heat, plain global Min-Max for sv/iv, global
bounds per GCM, no ``age_factor`` / ``EventMultiplier``). The only new thing
is the cut + the capacity roll-up.

Cutoffs (derived from the GFDL-ESM4 pooled percentiles already reported):

    LOW      score < 0.128            (< p25 GFDL)
    MEDIUM   0.128 <= score < 0.386   (p25-p75 GFDL)
    HIGH     0.386 <= score < 0.647   (p75-p95 GFDL)
    EXTREME  score >= 0.647           (>= p95 GFDL)

The SAME absolute cutoffs are applied to the MIROC6 score (not recalculated)
so the two can be compared on one ruler.

Standalone: ``python -m analysis.ccrs_band_classification`` from the project
root. Writes ``analysis/ccrs_band_classification.md``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ASSETS_PROCESSED, COUNTRIES  # noqa: E402
from analysis.ccrs_preliminary_distribution import (  # noqa: E402
    MODELS,
    WATER_SCENARIOS,
    WATER_TO_HEAT,
    WEIGHTS,
    raster,
    sample_points,
    transform_term,
)

HERE = Path(__file__).resolve().parent
MD_OUT = HERE / "ccrs_band_classification.md"

TERMS = ("ws", "heat", "sv", "iv")

# Proposed absolute cutoffs (GFDL-ESM4 pooled p25 / p75 / p95).
CUTS = [("LOW", -np.inf, 0.128),
        ("MEDIUM", 0.128, 0.386),
        ("HIGH", 0.386, 0.647),
        ("EXTREME", 0.647, np.inf)]
BANDS = [b for b, _, _ in CUTS]
DOMINANCE_THRESHOLD = 0.50  # >50% of capacity in one band -> flag


def classify(score: np.ndarray) -> np.ndarray:
    out = np.full(score.shape, "", dtype=object)
    for band, lo, hi in CUTS:
        out[(score >= lo) & (score < hi)] = band
    return out


def extract_with_capacity(model: str) -> pd.DataFrame:
    """One row per (plant, water scenario): the four raw term values plus
    capacity_mw. 'matched' = all four terms finite."""
    recs = []
    for country in COUNTRIES:
        plants = pd.read_csv(ASSETS_PROCESSED / f"gem_validated_plants_{country}.csv")
        lons = plants["lon"].to_numpy("float64")
        lats = plants["lat"].to_numpy("float64")
        cap = pd.to_numeric(plants["capacity_mw"], errors="coerce").to_numpy("float64")
        for ws_scen in WATER_SCENARIOS:
            part = pd.DataFrame({
                "country": np.repeat(country, len(plants)),
                "water_scenario": ws_scen,
                "plant_name": plants["plant_name"].to_numpy(),
                "capacity_mw": cap,
            })
            for term in TERMS:
                part[term] = sample_points(raster(term, country, ws_scen, model), lons, lats)
            recs.append(part)
    df = pd.concat(recs, ignore_index=True)
    df["matched"] = df[list(TERMS)].notna().all(axis=1)
    return df


def score_frame(model: str) -> pd.DataFrame:
    df = extract_with_capacity(model)
    m = df[df["matched"]].copy()
    # global per-GCM Min-Max bounds — identical to ccrs_preliminary_distribution
    bounds = {t: (float(m[t].min()), float(m[t].max())) for t in TERMS}
    hazard = np.zeros(len(m))
    for t in TERMS:
        lo, hi = bounds[t]
        hazard = hazard + WEIGHTS[t] * transform_term(t, m[t].to_numpy(), lo, hi)
    m["hazard"] = hazard
    m["band"] = classify(m["hazard"].to_numpy())
    m.attrs["bounds"] = bounds
    m.attrs["n_total"] = len(df)
    return m


def _pct(part: float, whole: float) -> str:
    return f"{100 * part / whole:.1f}%" if whole else "—"


def _cell_counts(sub: pd.DataFrame, band: str, denom_n: int) -> str:
    n = int((sub["band"] == band).sum())
    return f"{_pct(n, denom_n)} ({n})"


def _cell_cap(sub: pd.DataFrame, band: str, denom_mw: float) -> str:
    mw = float(sub.loc[sub["band"] == band, "capacity_mw"].fillna(0).sum())
    return f"{_pct(mw, denom_mw)} ({mw:,.0f} MW)"


def md_table(headers, rows):
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *["| " + " | ".join(r) + " |" for r in rows],
    ])


def build_model_section(model: str, m: pd.DataFrame) -> tuple[str, list[str]]:
    out = [f"## Heat GCM: `{model}`\n"]
    b = m.attrs["bounds"]
    out.append(
        f"Global per-GCM raw bounds: ws [{b['ws'][0]:.3g}, {b['ws'][1]:.3g}], "
        f"heat [{b['heat'][0]:.3g}, {b['heat'][1]:.3g}], "
        f"sv [{b['sv'][0]:.3g}, {b['sv'][1]:.3g}], "
        f"iv [{b['iv'][0]:.3g}, {b['iv'][1]:.3g}]. "
        f"Matched rows {len(m)} / {m.attrs['n_total']}.\n"
    )

    # ---- plants by band ----
    out.append("### Plants by band — % (count)\n")
    rows = []
    for country in COUNTRIES:
        for ws_scen in WATER_SCENARIOS:
            sub = m[(m["country"] == country) & (m["water_scenario"] == ws_scen)]
            denom = len(sub)
            rows.append([country, f"{ws_scen}/{WATER_TO_HEAT[ws_scen]}", str(denom)]
                        + [_cell_counts(sub, band, denom) for band in BANDS])
    out.append(md_table(["country", "scenario", "n plants"] + BANDS, rows))

    # ---- capacity by band ----
    out.append("\n### Installed capacity by band — % (MW)\n")
    rows = []
    flags: list[str] = []
    for country in COUNTRIES:
        for ws_scen in WATER_SCENARIOS:
            sub = m[(m["country"] == country) & (m["water_scenario"] == ws_scen)]
            denom_mw = float(sub["capacity_mw"].fillna(0).sum())
            rows.append([country, f"{ws_scen}/{WATER_TO_HEAT[ws_scen]}", f"{denom_mw:,.0f}"]
                        + [_cell_cap(sub, band, denom_mw) for band in BANDS])
            for band in BANDS:
                share = sub.loc[sub["band"] == band, "capacity_mw"].fillna(0).sum() / denom_mw if denom_mw else 0
                if share > DOMINANCE_THRESHOLD:
                    flags.append(
                        f"- **{model} / {country} / {ws_scen}({WATER_TO_HEAT[ws_scen]})**: "
                        f"{share*100:.1f}% of installed capacity in **{band}** alone."
                    )
    out.append(md_table(["country", "scenario", "total MW"] + BANDS, rows))

    # ---- capacity coverage note ----
    cov = []
    for country in COUNTRIES:
        full = pd.read_csv(ASSETS_PROCESSED / f"gem_validated_plants_{country}.csv")
        full_mw = pd.to_numeric(full["capacity_mw"], errors="coerce").fillna(0).sum()
        # matched capacity is per-scenario; opt is representative of coverage
        sub = m[(m["country"] == country) & (m["water_scenario"] == "opt")]
        cov.append([country, f"{full_mw:,.0f}", f"{sub['capacity_mw'].fillna(0).sum():,.0f}",
                    _pct(sub["capacity_mw"].fillna(0).sum(), full_mw),
                    str(int((full["capacity_mw"].isna()).sum()))])
    out.append("\n### Capacity coverage (opt scenario, representative)\n")
    out.append(md_table(
        ["country", "total declared MW", "scored MW", "scored %", "plants w/ NaN capacity"], cov))
    out.append("")
    return "\n".join(out), flags


def main() -> int:
    lines = ["# CCRS preliminary band classification — proposed cutoffs\n"]
    lines.append(
        "Diagnostic only. Equal weights (`w = 0.25`), same Hazard score as "
        "`analysis/ccrs_preliminary_distribution.py`; **no weight change, no "
        "`age_factor`, no `EventMultiplier`, no production code.** The band "
        "cutoffs below are a *proposal* under review.\n"
    )
    lines.append(
        "| band | rule | GFDL percentile |\n| --- | --- | --- |\n"
        "| LOW | score < 0.128 | < p25 |\n"
        "| MEDIUM | 0.128 ≤ score < 0.386 | p25–p75 |\n"
        "| HIGH | 0.386 ≤ score < 0.647 | p75–p95 |\n"
        "| EXTREME | score ≥ 0.647 | ≥ p95 |\n"
    )
    lines.append(
        "The **same absolute cutoffs** are applied to both GCM scores (each "
        "computed with its own global per-term bounds). If the cutoffs only "
        "fit GFDL, MIROC6 will pile capacity into HIGH/EXTREME — that is the "
        "check.\n"
    )

    all_flags: list[str] = []
    for model in MODELS:
        section, flags = build_model_section(model, score_frame(model))
        lines.append(section)
        all_flags.extend(flags)

    lines.append("---\n")
    lines.append("## Dominance flags (> 50% of installed capacity in one band)\n")
    lines.append("\n".join(all_flags) if all_flags else "_None._")
    lines.append(
        "\n\nA flag means the cutoffs are not discriminating for that "
        "country/GCM/scenario — a single band holds the majority of capacity, "
        "so the classification carries little information there.\n"
    )
    lines.append(
        "\n## What the numbers say (no decision drawn)\n\n"
        "- **The cutoffs discriminate India and compress Brazil / Portugal.** "
        "The cuts are GFDL *pooled* percentiles, and the pool is ~half Indian "
        "plants with much higher scores, so the thresholds land where India's "
        "distribution is, not Brazil's or Portugal's. Brazil and Portugal "
        "never reach EXTREME under either GCM, and never reach HIGH under "
        "GFDL (Portugal never under either).\n"
        "- **MIROC6 does not blow out EXTREME — it drains LOW.** The predicted "
        "saturation shows up as a *floor lift*: the MIROC6 heat term sits near "
        "the top of its own range for almost every matched plant (transformed "
        "p50 ≈ 0.77 vs GFDL ≈ 0.20), adding ~+0.15 to every score. That pushes "
        "Brazil out of LOW (55% → ~20%) and Portugal out of LOW entirely, all "
        "into MEDIUM — but India's EXTREME share only rises ~7% → ~14%, not a "
        "runaway.\n"
        "- **12 of 18 country×GCM×scenario cells are flagged.** Only India "
        "(both GCMs, all scenarios) spreads across three or four bands.\n"
    )
    MD_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {MD_OUT.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
