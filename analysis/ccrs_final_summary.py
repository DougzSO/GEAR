"""
DEPRECATED / diagnostic-only -- frozen historical artifact, not production.

This script predates the CCRS index layer (``src/index/``, T1-T6, all
committed) and uses a methodology that diverges from it: its HeatRiskBand
percentile cuts (p25/p75/p95) are computed over the "matched" pool only --
rows where ``ws``/``sv``/``iv`` **and** ``heat`` are all finite -- whereas
``src/index/risk_bands.py`` (the production classifier) cuts over every row
with a finite ``heat`` value, independent of the water terms, by design
(WaterRiskBand and HeatRiskBand are separate, never co-dependent columns --
spec Section 8.3). This was confirmed in T6
(``tests/test_ccrs_integration.py``) as a small, permanent, expected residual
(~0.05 pp, India/GFDL-ESM4 compound share: 39.2551% here vs 39.2000%
production) -- documented, not a bug, and not something either side will be
changed to close. Full account: ``docs/memory/05-decisoes-tecnicas.md``,
item 17 ("``analysis/ccrs_final_summary.py`` x ``src/index/risk_bands.py``
never match exactly -- HeatRiskBand percentile-cut pool differs").

**Source of truth for production numbers: ``src/index/ccrs_report.py``**
(the final CCRS assembly and per-country capacity-share report), backed by
``src/index/risk_bands.py`` (WaterRiskBand/HeatRiskBand) and
``src/index/ccrs_calculator.py`` (the Hazard term). Do not cite this script's
numbers as the study's result -- use ``ccrs_report.py``'s output instead.

Kept, not deleted: this diagnostic has standalone historical value (it is
also the frozen baseline ``tests/test_ccrs_integration.py`` regression-checks
production against, via its ``heat_band_frame`` function -- see that test
module before changing or removing anything here). Not recomputed, not
extended, not aligned to the production pool.

--------------------------------------------------------------------------
Original docstring (unchanged below)
--------------------------------------------------------------------------
Consolidated CCRS diagnostic summary — assembles the pieces already computed:

* CCRS numeric score distribution (transcribed from
  ``analysis/ccrs_preliminary_distribution.md`` — NOT recomputed).
* WaterRiskBand: absolute WRI-anchored bands on ws+sv+iv
  (``analysis/water_risk_band_classification.py``).
* HeatRiskBand: sample-relative percentile bands on the heat term alone
  (heat pooled p25/p75/p95 per GCM, GFDL-ESM4 primary).
* Joint reading: WaterRiskBand x HeatRiskBand crossed by country — the one
  view none of the earlier reports showed.
* Items still open after this band-structure close.

Diagnostic only. No production code, no weight change to the combined score.

Standalone: ``python -m analysis.ccrs_final_summary`` from the project root.
Writes ``analysis/ccrs_final_summary.md``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import ASSETS_PROCESSED, COUNTRIES  # noqa: E402
from analysis.ccrs_preliminary_distribution import MODELS, WATER_SCENARIOS  # noqa: E402
from analysis.ccrs_band_classification import _pct, md_table  # noqa: E402
from analysis.water_risk_band_classification import (  # noqa: E402
    WATER_BANDS,
    band_cuts,
    derive_weights,
    water_band_frame,
)

HERE = Path(__file__).resolve().parent
MD_OUT = HERE / "ccrs_final_summary.md"

HEAT_BANDS = ["LOW", "MEDIUM", "HIGH", "EXTREME"]
PRIMARY_GCM = "gfdl_esm4"

# CCRS numeric Hazard-score distribution, equal weights, transcribed verbatim
# from analysis/ccrs_preliminary_distribution.md (do not recompute here).
CCRS_NUMERIC = {
    "gfdl_esm4": {
        "Brazil":   dict(n=15759, p1=0.04123, p5=0.05149, p25=0.08617, p50=0.1312, p75=0.1788, p95=0.292,  p99=0.3586, mx=0.4256, sk=0.972),
        "Portugal": dict(n=1347,  p1=0.1150,  p5=0.1223,  p25=0.1495,  p50=0.1969, p75=0.2186, p95=0.3136, p99=0.3331, mx=0.3331, sk=0.779),
        "India":    dict(n=15195, p1=0.1081,  p5=0.1351,  p25=0.2584,  p50=0.4070, p75=0.5615, p95=0.6914, p99=0.7592, mx=0.8691, sk=-0.002),
        "pooled":   dict(n=32301, p1=0.04774, p5=0.05960, p25=0.1278,  p50=0.2009, p75=0.3862, p95=0.6470, p99=0.7374, mx=0.8691, sk=0.870),
    },
    "miroc6": {
        "Brazil":   dict(n=15723, p1=0.04468, p5=0.07221, p25=0.1668, p50=0.2502, p75=0.3195, p95=0.3923, p99=0.4690, mx=0.5037, sk=-0.132),
        "Portugal": dict(n=1245,  p1=0.1411,  p5=0.1447,  p25=0.1867, p50=0.2599, p75=0.3095, p95=0.3536, p99=0.4047, mx=0.4309, sk=-0.036),
        "India":    dict(n=15195, p1=0.1214,  p5=0.2834,  p25=0.3665, p50=0.4516, p75=0.6027, p95=0.7250, p99=0.7892, mx=0.8824, sk=0.150),
        "pooled":   dict(n=32163, p1=0.05136, p5=0.08358, p25=0.2355, p50=0.3333, p75=0.4447, p95=0.6884, p99=0.7670, mx=0.8824, sk=0.500),
    },
}


def heat_band_frame(model: str, m: pd.DataFrame) -> tuple[pd.DataFrame, dict[int, float]]:
    """Add a HeatRiskBand to the (already water-banded, matched) frame using
    the pooled p25/p75/p95 of that GCM's own heat term (days/yr > 40 C).
    Percentile cuts are rank-invariant, so cutting raw days == cutting the
    transformed term."""
    heat = m["heat"].to_numpy("float64")
    cuts = {p: float(np.percentile(heat, p)) for p in (25, 75, 95)}
    edges = [-np.inf, cuts[25], cuts[75], cuts[95], np.inf]
    hb = np.full(len(m), "", dtype=object)
    for i, band in enumerate(HEAT_BANDS):
        sel = (heat >= edges[i]) & (heat < edges[i + 1])
        hb[sel] = band
    m = m.copy()
    m["hband"] = hb
    return m, cuts


def cap_by_band(sub: pd.DataFrame, col: str, bands: list[str]) -> list[str]:
    denom = float(sub["capacity_mw"].fillna(0).sum())
    out = []
    for b in bands:
        mw = float(sub.loc[sub[col] == b, "capacity_mw"].fillna(0).sum())
        out.append(f"{_pct(mw, denom)}")
    return out


def coverage_table(frames: dict[str, pd.DataFrame]) -> str:
    """declared vs matched installed capacity per country x GCM. The cross-tabs
    normalise to matched capacity (all four terms finite), not declared."""
    rows = []
    for model in MODELS:
        f = frames[model]
        for country in COUNTRIES:
            full = pd.read_csv(ASSETS_PROCESSED / f"gem_validated_plants_{country}.csv")
            declared = pd.to_numeric(full["capacity_mw"], errors="coerce").fillna(0).sum()
            # match set is constant across scenarios; take one as representative
            sub = f[(f.country == country) & (f.water_scenario == WATER_SCENARIOS[0])]
            matched = sub["capacity_mw"].fillna(0).sum()
            rows.append([
                model, country, f"{declared:,.0f}", f"{matched:,.0f}",
                f"{declared - matched:,.0f}", f"{100 * matched / declared:.1f}%",
            ])
    return md_table(
        ["GCM", "country", "declared MW", "matched MW", "excluded MW", "matched %"], rows)


def cross_table(sub: pd.DataFrame) -> str:
    denom = float(sub["capacity_mw"].fillna(0).sum())
    rows = []
    for wb in WATER_BANDS:
        cells = []
        for hb in HEAT_BANDS:
            mw = float(sub.loc[(sub["wband"] == wb) & (sub["hband"] == hb),
                               "capacity_mw"].fillna(0).sum())
            cells.append(_pct(mw, denom))
        rows.append([f"water {wb}"] + cells)
    return md_table(["", *[f"heat {h}" for h in HEAT_BANDS]], rows)


def main() -> int:
    weights = derive_weights()
    wcuts = band_cuts(weights)

    L: list[str] = ["# CCRS — consolidated diagnostic summary\n"]
    L.append(
        "Diagnostic only, no production code. Equal provisional weights "
        "(`w = 0.25` on each of ws/heat/sv/iv) for the numeric score; "
        "`age_factor` and `EventMultiplier` not yet applied. The discrete "
        "classification is now **two separate bands**, not one band on the "
        "combined score:\n\n"
        "- **WaterRiskBand** (ws + sv + iv) — **absolute** cuts from WRI "
        "Aqueduct 4.0 categories (`analysis/water_risk_band_classification.md`, "
        "`analysis/absolute_threshold_research.md`).\n"
        "- **HeatRiskBand** (`extreme_heat_days` alone) — **sample-relative** "
        "percentile cuts, GFDL-ESM4 primary, with a declared limitation "
        "(no absolute annual-frequency threshold exists for this indicator).\n"
    )

    # ---- 1. CCRS numeric ----
    L.append("\n## 1. CCRS numeric score (unchanged) — descriptive\n")
    L.append(
        "Single continuous weighted sum, used for overall ranking and the "
        "per-plant map. Transcribed from `analysis/ccrs_preliminary_distribution.md` "
        "(not recomputed).\n"
    )
    for model in MODELS:
        L.append(f"\n**Heat GCM `{model}`**\n")
        rows = []
        for c in ["Brazil", "Portugal", "India", "pooled"]:
            d = CCRS_NUMERIC[model][c]
            rows.append([c, str(d["n"])] + [f"{d[k]:.3f}" for k in
                        ("p1", "p5", "p25", "p50", "p75", "p95", "p99", "mx", "sk")])
        L.append(md_table(
            ["country", "n", "p1", "p5", "p25", "p50", "p75", "p95", "p99", "max", "skew"], rows))

    # ---- 2. WaterRiskBand ----
    L.append("\n## 2. WaterRiskBand — absolute WRI-anchored bands\n")
    L.append(
        f"`S_water = {weights['ws']:.4f}·ws_raw + {weights['sv']:.4f}·sv_raw "
        f"+ {weights['iv']:.4f}·iv_raw`; cuts "
        f"{wcuts[0]:.3f} / {wcuts[1]:.3f} / {wcuts[2]:.3f} / {wcuts[3]:.3f} "
        f"(derivation in `water_risk_band_classification.md`). % of installed "
        f"capacity per band, per country x scenario. GCM-independent by "
        f"construction; the plant set differs slightly between GCM columns "
        f"(MIROC6 drops coastal plants). Portugal loses 34 plants / 804 MW "
        f"(3.7% of declared capacity) under MIROC6, driven by the ~1.4-degree "
        f"native grid resolution issue documented in DECISIONS.md's V4 update "
        f"entry — the largest cross-country coverage divergence in this "
        f"report, though it does not change Portugal's compound-risk figures "
        f"(both remain 0.0%).\n"
    )
    frames = {}
    for model in MODELS:
        m = water_band_frame(model, weights, wcuts)
        frames[model], _ = heat_band_frame(model, m)
    for model in MODELS:
        L.append(f"\n**{model} plant set**\n")
        rows = []
        for country in COUNTRIES:
            for sc in WATER_SCENARIOS:
                sub = frames[model][(frames[model].country == country)
                                    & (frames[model].water_scenario == sc)]
                rows.append([country, sc] + cap_by_band(sub, "wband", WATER_BANDS))
        L.append(md_table(["country", "scenario"] + WATER_BANDS, rows))

    # ---- 3. HeatRiskBand ----
    L.append("\n## 3. HeatRiskBand — sample-relative percentile bands\n")
    for model in MODELS:
        _, hcuts = heat_band_frame(model, frames[model])
        L.append(
            f"\n**{model}** — pooled p25/p75/p95 of `extreme_heat_days` = "
            f"**{hcuts[25]:.2f} / {hcuts[75]:.1f} / {hcuts[95]:.1f} days/yr > 40 °C**. "
            f"By construction the pooled split is 25 / 50 / 20 / 5 %.\n"
        )
        rows = []
        for country in COUNTRIES:
            for sc in WATER_SCENARIOS:
                sub = frames[model][(frames[model].country == country)
                                    & (frames[model].water_scenario == sc)]
                rows.append([country, sc] + cap_by_band(sub, "hband", HEAT_BANDS))
        L.append(md_table(["country", "scenario"] + HEAT_BANDS, rows))
    L.append(
        "\n_Note: under GFDL-ESM4 the pooled p25 is ~0.03 days/yr — 24 % of "
        "plants have exactly zero 40 °C days in the 2041–2070 mean — so the "
        "GFDL LOW band is effectively \"no extreme heat\". Under MIROC6 the "
        "same percentile is ~18 days/yr._\n"
    )
    L.append(
        "\n> **Declared limitation (HeatRiskBand).** No published absolute "
        "threshold classifies the annual frequency of days above 40 °C into "
        "risk categories. Published schemes classify single-day intensity "
        "(WBGT, ISO 7243) or the presence/absence of a temperature threshold "
        "(World Bank CKP), not cumulative annual frequency. Heat-mortality "
        "epidemiology deliberately avoids absolute cuts because they do not "
        "carry across different baseline climates — the same physical value "
        "(e.g. 35 °C) is a very different risk in different climates. "
        "HeatRiskBand therefore uses cuts relative to this study's sample "
        "(pooled percentiles) and is sensitive to the GCM used (~10–100× "
        "difference between GFDL-ESM4 and MIROC6 in the underlying absolute "
        "values, though the classification itself is recomputed per "
        "percentile). This is a declared limitation, not an implementation "
        "flaw — it is the available state of the art for this kind of "
        "indicator.\n"
    )

    # ---- 4. Joint reading ----
    L.append("\n## 4. Joint reading — WaterRiskBand × HeatRiskBand by country\n")
    L.append(
        "% of a country's **matched** installed capacity in each (water band, "
        "heat band) cell, three scenarios pooled. **Matched** = plants with a "
        "finite value in all four terms (ws, sv, iv, heat); each country's row "
        "is normalised to its own matched capacity, **not** to total declared "
        "capacity. This crossing is not visible in any of the single-band "
        "reports.\n"
    )
    L.append("\n### Capacity coverage — declared vs. matched\n")
    L.append(
        "Plants drop out when they fall outside an Aqueduct basin (ws/sv/iv, "
        "GCM-independent) or outside the heat raster (heat, GCM-dependent). "
        "The excluded share is the difference between each country's declared "
        "installed capacity and the denominator used in the cross-tabs below.\n"
    )
    L.append(coverage_table(frames))
    L.append(
        "\nUnder GFDL-ESM4 the matched/declared distinction is immaterial "
        "(99.6–99.9% everywhere). Under MIROC6 it is immaterial for Brazil "
        "(99.4%) and India (99.7%) but material for Portugal (96.3% — 34 "
        "plants / 804 MW excluded by the coarse native grid, per §2). "
        "Portugal's compound-risk cells are 0.0% regardless, so no headline "
        "number changes.\n"
    )
    for model in MODELS:
        L.append(f"\n### {model}\n")
        for country in COUNTRIES:
            sub = frames[model][frames[model].country == country]
            L.append(f"\n**{country}** (capacity pooled over 3 scenarios)\n")
            L.append(cross_table(sub))
            hi_hi = sub.loc[sub.wband.isin(["High", "Extremely-High"])
                            & sub.hband.isin(["HIGH", "EXTREME"]), "capacity_mw"].fillna(0).sum()
            ext_ext = sub.loc[(sub.wband == "Extremely-High")
                              & (sub.hband == "EXTREME"), "capacity_mw"].fillna(0).sum()
            denom = sub["capacity_mw"].fillna(0).sum()
            L.append(
                f"\n_{country}/{model}: **{_pct(hi_hi, denom)}** of capacity is "
                f"(water High or Extremely-High) AND (heat HIGH or EXTREME) at "
                f"once; **{_pct(ext_ext, denom)}** is water Extremely-High AND "
                f"heat EXTREME simultaneously._\n"
            )

    # ---- 5. Still open ----
    L.append("\n## 5. Still open after this close\n")
    L.append(
        "- **Weight of `heat` inside the combined numeric CCRS.** The numeric "
        "score still uses provisional equal weights (0.25 each). The "
        "magnitude-derived weight vector (spec §5/§6, same status as the "
        "original weight matrix / V5) is not set.\n"
        "- **`EventMultiplier` functional form `f()`.** Country-level EM-DAT "
        "frequency (V2, closed); linear vs stepped vs capped, raw count vs "
        "exposure-normalised vs rate — not decided (spec §10 item C).\n"
        "- **`age_factor` not implemented in code.** V1 fuel-specific curves "
        "are decided but unwritten; the ≥1 multiplier mapping (spec §10 item "
        "D) is not fixed.\n"
        "- **SPEI / drought term not implemented.** Method settled if added "
        "(SPEI + Thornthwaite PET, one method across both GCMs; spec §3), but "
        "no term, transform or weight exists.\n"
    )

    MD_OUT.write_text("\n".join(L), encoding="utf-8")
    print(f"wrote {MD_OUT.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
