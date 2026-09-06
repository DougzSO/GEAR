"""
Diagnostic-only: classify plants into an **absolute** WaterRiskBand
(ws + sv + iv combined) using WRI Aqueduct 4.0 category thresholds — no
sample percentiles.

Not production code. The combined CCRS numeric score is unchanged and lives
elsewhere; this only cuts the water part of it into
Low / Low-Medium / Medium-High / High / Extremely-High and rolls the result
up to installed capacity.

Construction (audited in full in ``analysis/climate_risk_score_spec.md``
Section 8):

    S_water_i = w_ws * ws_raw_i + w_sv * sv_raw_i + w_iv * iv_raw_i

with weights inversely proportional to each indicator's average WRI category
width (top threshold / 4), so that traversing one average WRI category of any
indicator adds the same amount to S_water. Band cuts are the value of S_water
when all three indicators sit exactly on the same WRI category boundary.

Standalone: ``python -m analysis.water_risk_band_classification`` from the
project root. Writes ``analysis/water_risk_band_classification.md``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import COUNTRIES  # noqa: E402
from analysis.ccrs_preliminary_distribution import (  # noqa: E402
    MODELS,
    WATER_SCENARIOS,
    WATER_TO_HEAT,
)
from analysis.ccrs_band_classification import (  # noqa: E402
    DOMINANCE_THRESHOLD,
    _pct,
    extract_with_capacity,
    md_table,
)

HERE = Path(__file__).resolve().parent
MD_OUT = HERE / "water_risk_band_classification.md"

WATER_BANDS = ["Low", "Low-Medium", "Medium-High", "High", "Extremely-High"]

# WRI Aqueduct 4.0 category boundaries in raw units (from the downloaded
# aqueduct_*.csv `_l` label vocabulary; see analysis/absolute_threshold_research.md).
#   ws : withdrawal-to-availability ratio
#   sv : within-year coefficient of variation of blue-water supply
#   iv : between-year coefficient of variation of blue-water supply
WRI_BOUNDARIES = {
    "ws": [0.10, 0.20, 0.40, 0.80],
    "sv": [0.33, 0.66, 1.00, 1.33],
    "iv": [0.25, 0.50, 0.75, 1.00],
}
INDICATORS = ("ws", "sv", "iv")


def derive_weights() -> dict[str, float]:
    """w_k proportional to 1 / (average WRI category width) = 1 / (tau_k / 4)
    = 4 / tau_k, where tau_k is the High -> Extremely-High threshold. The
    factor 4 cancels in normalisation, so w_k proportional to 1 / tau_k."""
    tau = {k: WRI_BOUNDARIES[k][-1] for k in INDICATORS}
    inv = {k: 1.0 / tau[k] for k in INDICATORS}
    total = sum(inv.values())
    return {k: inv[k] / total for k in INDICATORS}


def band_cuts(weights: dict[str, float]) -> list[float]:
    """S_water at each joint WRI boundary: all three indicators sitting
    exactly on their Nth category boundary at once."""
    cuts = []
    for n in range(4):
        s = sum(weights[k] * WRI_BOUNDARIES[k][n] for k in INDICATORS)
        cuts.append(s)
    return cuts


def s_water(m: pd.DataFrame, weights: dict[str, float]) -> np.ndarray:
    return sum(weights[k] * m[k].to_numpy("float64") for k in INDICATORS)


def classify(score: np.ndarray, cuts: list[float]) -> np.ndarray:
    edges = [-np.inf, *cuts, np.inf]
    out = np.full(score.shape, "", dtype=object)
    for i, band in enumerate(WATER_BANDS):
        out[(score >= edges[i]) & (score < edges[i + 1])] = band
    return out


def _cell(sub: pd.DataFrame, band: str, denom_n: int, denom_mw: float, cap: bool) -> str:
    if cap:
        mw = float(sub.loc[sub["wband"] == band, "capacity_mw"].fillna(0).sum())
        return f"{_pct(mw, denom_mw)} ({mw:,.0f} MW)"
    n = int((sub["wband"] == band).sum())
    return f"{_pct(n, denom_n)} ({n})"


def water_band_frame(model: str, weights: dict[str, float], cuts: list[float]) -> pd.DataFrame:
    """Matched (ws, sv, iv, heat) plant x scenario rows with S_water and its
    band. Matched includes heat so this frame can be crossed with the heat
    band on an identical plant set."""
    df = extract_with_capacity(model)
    m = df[df["matched"]].copy()
    m["s_water"] = s_water(m, weights)
    m["wband"] = classify(m["s_water"].to_numpy(), cuts)
    m.attrs["n_total"] = len(df)
    return m


def build_section(model: str, m: pd.DataFrame) -> tuple[str, list[str]]:
    out = [f"## Heat GCM plant set: `{model}`\n"]
    out.append(
        f"WaterRiskBand does not depend on the GCM; the only difference "
        f"between GCM sections is which plants are in the matched set "
        f"(MIROC6 drops the western-Portugal / coastal-Brazil strip). "
        f"Matched rows {len(m)} / {m.attrs['n_total']}.\n"
    )

    out.append("### Plants by WaterRiskBand — % (count)\n")
    rows = []
    for country in COUNTRIES:
        for ws_scen in WATER_SCENARIOS:
            sub = m[(m["country"] == country) & (m["water_scenario"] == ws_scen)]
            rows.append([country, f"{ws_scen}/{WATER_TO_HEAT[ws_scen]}", str(len(sub))]
                        + [_cell(sub, b, len(sub), 0, cap=False) for b in WATER_BANDS])
    out.append(md_table(["country", "scenario", "n plants"] + WATER_BANDS, rows))

    out.append("\n### Installed capacity by WaterRiskBand — % (MW)\n")
    rows = []
    flags: list[str] = []
    for country in COUNTRIES:
        for ws_scen in WATER_SCENARIOS:
            sub = m[(m["country"] == country) & (m["water_scenario"] == ws_scen)]
            denom_mw = float(sub["capacity_mw"].fillna(0).sum())
            rows.append([country, f"{ws_scen}/{WATER_TO_HEAT[ws_scen]}", f"{denom_mw:,.0f}"]
                        + [_cell(sub, b, len(sub), denom_mw, cap=True) for b in WATER_BANDS])
            for b in WATER_BANDS:
                share = (sub.loc[sub["wband"] == b, "capacity_mw"].fillna(0).sum() / denom_mw
                         if denom_mw else 0.0)
                if share > DOMINANCE_THRESHOLD:
                    flags.append(
                        f"- **{model} set / {country} / {ws_scen}**: {share*100:.1f}% "
                        f"of installed capacity in **{b}** alone."
                    )
    out.append(md_table(["country", "scenario", "total MW"] + WATER_BANDS, rows))
    out.append("")
    return "\n".join(out), flags


def weight_report(weights: dict[str, float], cuts: list[float]) -> str:
    tau = {k: WRI_BOUNDARIES[k][-1] for k in INDICATORS}
    lines = ["## Weight derivation (auditable)\n"]
    lines.append(
        "Each indicator's four finite WRI categories span raw 0 to its "
        "High->Extremely-High threshold `tau`. Average category width "
        "`delta_k = tau_k / 4`. Weight `w_k` proportional to `1 / delta_k` "
        "(= `4 / tau_k`; the 4 cancels, so `w_k` proportional to `1 / tau_k`), "
        "normalised to sum 1.\n"
    )
    rows = []
    inv_total = sum(1.0 / tau[k] for k in INDICATORS)
    for k in INDICATORS:
        rows.append([
            k, f"{tau[k]:.2f}", f"{tau[k] / 4:.4f}",
            f"{1.0 / tau[k]:.5f}", f"{(1.0 / tau[k]) / inv_total:.4f}",
        ])
    lines.append(md_table(
        ["indicator", "tau (top threshold)", "avg category width tau/4",
         "1 / tau", "weight w_k"], rows))
    lines.append(
        f"\n`S_water_i = {weights['ws']:.4f}*ws_raw + {weights['sv']:.4f}*sv_raw "
        f"+ {weights['iv']:.4f}*iv_raw`\n"
    )
    lines.append(
        "Because `w_k * tau_k = 1/3` for every k, each indicator contributes "
        "exactly one third of the top cut and the High->Extremely-High cut "
        "lands at 1.0.\n"
    )
    lines.append("### Absolute band cuts on S_water\n")
    brows = []
    labels = ["Low / Low-Medium", "Low-Medium / Medium-High",
              "Medium-High / High", "High / Extremely-High"]
    for n, lab in enumerate(labels):
        parts = " + ".join(f"{weights[k]:.4f}*{WRI_BOUNDARIES[k][n]:g}" for k in INDICATORS)
        brows.append([lab,
                      ", ".join(f"{k}={WRI_BOUNDARIES[k][n]:g}" for k in INDICATORS),
                      f"{parts} = **{cuts[n]:.4f}**"])
    lines.append(md_table(["boundary", "all three indicators at", "S_water"], brows))
    lines.append(
        f"\nWaterRiskBand: **Low** < {cuts[0]:.3f} · **Low-Medium** "
        f"{cuts[0]:.3f}-{cuts[1]:.3f} · **Medium-High** {cuts[1]:.3f}-{cuts[2]:.3f} "
        f"· **High** {cuts[2]:.3f}-{cuts[3]:.3f} · **Extremely-High** >= {cuts[3]:.3f}\n"
    )
    return "\n".join(lines)


def main() -> int:
    weights = derive_weights()
    cuts = band_cuts(weights)

    lines = ["# WaterRiskBand classification — absolute (WRI Aqueduct 4.0) cuts\n"]
    lines.append(
        "Diagnostic only, no production code. `ws` + `sv` + `iv` combined "
        "with weights derived from the WRI category step widths, cut at "
        "**absolute** thresholds anchored in WRI Aqueduct 4.0 (ws tracing to "
        "Raskin et al. 1997, SEI; sv/iv to WRI's own operational CV cutoffs — "
        "published but weaker, see `analysis/absolute_threshold_research.md`). "
        "No sample percentiles. Sentinel-substituted `ws_raw` (WRI 9999 -> "
        "country max) is used as-is; those basins are Extremely-High by "
        "definition.\n"
    )
    lines.append(weight_report(weights, cuts))

    all_flags: list[str] = []
    for model in MODELS:
        section, flags = build_section(model, water_band_frame(model, weights, cuts))
        lines.append(section)
        all_flags.extend(flags)

    lines.append("---\n")
    lines.append("## Dominance flags (> 50% of installed capacity in one band)\n")
    lines.append("\n".join(all_flags) if all_flags else "_None._")
    MD_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {MD_OUT.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
