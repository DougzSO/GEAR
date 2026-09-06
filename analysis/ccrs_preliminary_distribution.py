"""
Diagnostic-only: the shape of a provisional Hazard score with EQUAL weights.

Not production code, not a decision. It combines the four CCRS hazard terms
(`ws`, `heat`, `sv`, `iv`) at plant level with `w = 0.25` each, using the
transforms proposed in `analysis/climate_risk_score_spec.md` — `log1p` then
Min-Max for `ws`/`heat`, plain Min-Max for `sv`/`iv` — and **global** Min-Max
bounds (all countries and all scenarios pooled, no per-country
normalisation). `age_factor` and `EventMultiplier` are deliberately omitted:
this isolates the pure Hazard term so its distribution can be inspected
before band cutoffs are proposed.

Standalone: `python -m analysis.ccrs_preliminary_distribution` from the
project root. Reads the processed raw rasters (`water_stress_raw_*`,
`extreme_heat_days_*`, `seasonal_variability_raw_*`,
`interannual_variability_raw_*`) and `gem_validated_plants_{country}.csv`.
Writes `analysis/ccrs_preliminary_distribution.md`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import rowcol

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import (  # noqa: E402
    AQUEDUCT_SCENARIO_FOR_CMIP6,
    ASSETS_PROCESSED,
    CLIMATE_PROCESSED,
    COUNTRIES,
)
from src.downloaders.cds_tasmax_downloader import configured_models  # noqa: E402

HERE = Path(__file__).resolve().parent
MD_OUT = HERE / "ccrs_preliminary_distribution.md"

MODELS = configured_models()
PCTL = [1, 5, 25, 50, 75, 95, 99]
WEIGHTS = {"ws": 0.25, "heat": 0.25, "sv": 0.25, "iv": 0.25}
LOG_TERMS = {"ws", "heat"}          # log1p then Min-Max
LIN_TERMS = {"sv", "iv"}            # plain Min-Max

# heat scenario <-> water scenario (SSP identity), from config
WATER_TO_HEAT = {ws: hs for hs, ws in AQUEDUCT_SCENARIO_FOR_CMIP6.items()}
WATER_SCENARIOS = ["opt", "bau", "pes"]


def skewness(a: np.ndarray) -> float:
    a = np.asarray(a, "float64")
    a = a[~np.isnan(a)]
    if a.size < 3 or a.std() == 0:
        return float("nan")
    return float(np.mean(((a - a.mean()) / a.std()) ** 3))


def pctl_row(a: np.ndarray) -> dict:
    a = np.asarray(a, "float64")
    a = a[~np.isnan(a)]
    if a.size == 0:
        return {"n": 0, **{f"p{p}": float("nan") for p in PCTL}, "max": float("nan"), "skew": float("nan")}
    qs = np.percentile(a, PCTL)
    return {"n": int(a.size), **{f"p{p}": float(q) for p, q in zip(PCTL, qs)},
            "max": float(a.max()), "skew": skewness(a)}


def sample_points(path: Path, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    with rasterio.open(path) as src:
        band = src.read(1).astype("float64")
        nod = src.nodata
        if nod is not None and not np.isnan(nod):
            band[band == nod] = np.nan
        rows, cols = rowcol(src.transform, lons, lats)
        rows, cols = np.asarray(rows), np.asarray(cols)
        h, w = band.shape
        inside = (rows >= 0) & (rows < h) & (cols >= 0) & (cols < w)
        out = np.full(lons.shape, np.nan)
        out[inside] = band[rows[inside], cols[inside]]
    return out


def raster(term: str, country: str, water_scen: str, model: str) -> Path:
    if term == "ws":
        return CLIMATE_PROCESSED / f"water_stress_raw_{country}_{water_scen}_1km.tif"
    if term == "sv":
        return CLIMATE_PROCESSED / f"seasonal_variability_raw_{country}_{water_scen}_1km.tif"
    if term == "iv":
        return CLIMATE_PROCESSED / f"interannual_variability_raw_{country}_{water_scen}_1km.tif"
    if term == "heat":
        return CLIMATE_PROCESSED / f"extreme_heat_days_{country}_{model}_{WATER_TO_HEAT[water_scen]}_1km.tif"
    raise ValueError(term)


def extract(model: str) -> pd.DataFrame:
    """One row per (plant, water scenario). Raw term values + a 'matched'
    flag (all four terms finite)."""
    recs = []
    for country in COUNTRIES:
        plants = pd.read_csv(ASSETS_PROCESSED / f"gem_validated_plants_{country}.csv")
        lons = plants["lon"].to_numpy("float64")
        lats = plants["lat"].to_numpy("float64")
        for ws_scen in WATER_SCENARIOS:
            part = pd.DataFrame({
                "country": np.repeat(country, len(plants)),
                "water_scenario": ws_scen,
            })
            for term in ("ws", "heat", "sv", "iv"):
                part[term] = sample_points(raster(term, country, ws_scen, model), lons, lats)
            recs.append(part)
    df = pd.concat(recs, ignore_index=True)
    df["matched"] = df[["ws", "heat", "sv", "iv"]].notna().all(axis=1)
    return df


def transform_term(term: str, raw: np.ndarray, lo: float, hi: float) -> np.ndarray:
    if term in LOG_TERMS:
        x, a, b = np.log1p(raw), np.log1p(lo), np.log1p(hi)
    else:
        x, a, b = raw, lo, hi
    if b <= a:
        return np.zeros_like(x)
    return np.clip((x - a) / (b - a), 0.0, 1.0)


def fmt(v, s="{:.4g}"):
    return "—" if v is None or (isinstance(v, float) and np.isnan(v)) else s.format(v)


def md_table(headers, rows):
    return "\n".join([
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
        *["| " + " | ".join(r) + " |" for r in rows],
    ])


def build_model_section(model: str, df: pd.DataFrame) -> tuple[str, dict]:
    m = df[df["matched"]].copy()
    # global Min-Max bounds: pooled over ALL countries and ALL scenarios
    bounds = {t: (float(m[t].min()), float(m[t].max())) for t in ("ws", "heat", "sv", "iv")}
    for t in ("ws", "heat", "sv", "iv"):
        lo, hi = bounds[t]
        m[f"T_{t}"] = transform_term(t, m[t].to_numpy(), lo, hi)
    m["hazard"] = sum(WEIGHTS[t] * m[f"T_{t}"] for t in ("ws", "heat", "sv", "iv"))

    out = [f"## Heat GCM: `{model}`\n"]
    out.append(f"Matched plant×scenario rows: {len(m)} "
               f"(of {len(df)}; unmatched = plant outside a basin or the heat raster).\n")

    # global bounds table
    br = []
    for t in ("ws", "heat", "sv", "iv"):
        lo, hi = bounds[t]
        tr = "log1p → Min-Max" if t in LOG_TERMS else "Min-Max"
        br.append([t, tr, fmt(lo), fmt(hi)])
    out.append("### Global per-term bounds (pooled, all countries × all scenarios)\n")
    out.append(md_table(["term", "transform", "raw min", "raw max"], br))

    # per-term transformed distribution
    out.append("\n### Transformed term distributions (0–1), pooled\n")
    tr_rows = []
    for t in ("ws", "heat", "sv", "iv"):
        pr = pctl_row(m[f"T_{t}"].to_numpy())
        tr_rows.append([t] + [fmt(pr[k]) for k in ("p1", "p5", "p25", "p50", "p75", "p95", "p99", "max")]
                       + [fmt(pr["skew"], "{:.3f}")])
    out.append(md_table(["term", "p1", "p5", "p25", "p50", "p75", "p95", "p99", "max", "skew"], tr_rows))

    # hazard score distribution, per country + pooled
    out.append("\n### Hazard score (Σ 0.25·term), equal weights — NO age_factor, NO EventMultiplier\n")
    hz_rows = []
    summary = {}
    for country in COUNTRIES + ["**pooled**"]:
        sub = m if country == "**pooled**" else m[m["country"] == country]
        pr = pctl_row(sub["hazard"].to_numpy())
        summary[country.strip("*")] = pr
        hz_rows.append([country, str(pr["n"])]
                       + [fmt(pr[k]) for k in ("p1", "p5", "p25", "p50", "p75", "p95", "p99", "max")]
                       + [fmt(pr["skew"], "{:.3f}")])
    out.append(md_table(
        ["country", "n", "p1", "p5", "p25", "p50", "p75", "p95", "p99", "max", "skew"], hz_rows))

    # scenario breakdown of the pooled score
    out.append("\n### Pooled Hazard score by scenario\n")
    sc_rows = []
    for ws_scen in WATER_SCENARIOS:
        sub = m[m["water_scenario"] == ws_scen]
        pr = pctl_row(sub["hazard"].to_numpy())
        sc_rows.append([f"{ws_scen} / {WATER_TO_HEAT[ws_scen]}", str(pr["n"])]
                       + [fmt(pr[k]) for k in ("p25", "p50", "p75", "p95", "p99", "max")]
                       + [fmt(pr["skew"], "{:.3f}")])
    out.append(md_table(
        ["scenario (water / heat)", "n", "p25", "p50", "p75", "p95", "p99", "max", "skew"], sc_rows))
    out.append("")
    return "\n".join(out), summary


def main() -> int:
    lines = ["# Preliminary CCRS Hazard-term distribution — equal weights\n"]
    lines.append(
        "Diagnostic only. **Provisional `w = 0.25` for every term**, purely to "
        "see the shape — not a weight decision. `age_factor` and "
        "`EventMultiplier` are excluded (pure Hazard term). Transforms per "
        "`analysis/climate_risk_score_spec.md`: `log1p`→Min-Max for `ws`/`heat`, "
        "plain Min-Max for `sv`/`iv`. **Min-Max bounds are global** — pooled "
        "over all three countries and all three scenarios (matched plants), "
        "no per-country normalisation.\n"
    )
    lines.append(
        "- Plant→raster: nearest-pixel sample of the processed raw rasters.\n"
        "- Scenario pairing (SSP identity): "
        + ", ".join(f"{w} ↔ {WATER_TO_HEAT[w]}" for w in WATER_SCENARIOS) + ".\n"
        "- Two heat GCMs reported separately — `heat` is the one term whose "
        "GCM choice is still open, and MIROC6's day-counts run ~10–100× GFDL, "
        "so the Hazard shape depends on it.\n"
    )
    for model in MODELS:
        section, _ = build_model_section(model, extract(model))
        lines.append(section)
    lines.append("---\n")
    lines.append(
        "No band cutoffs proposed here. The point of the table is the shape "
        "(skew, percentile spacing) and the country ordering under a global "
        "scale, as input to the EXTREME/HIGH/MEDIUM/LOW cutoff discussion "
        "(spec Section 10 item B)."
    )
    MD_OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {MD_OUT.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
