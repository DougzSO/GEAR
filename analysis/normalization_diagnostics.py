"""
Diagnostic-only analysis of the hazard values that actually reach the (not
yet built) index layer, and of candidate normalisation transforms.

Standalone: run from the project root with
``.venv\\Scripts\\python -m analysis.normalization_diagnostics`` (or
``python analysis/normalization_diagnostics.py``). It reads only the already
processed rasters and validated-plant tables; it writes nothing under
``src/`` and changes no pipeline behaviour. Two outputs land next to this
file:

* ``analysis/plant_level_hazard_values.csv`` — one row per plant x scenario
  x hazard, with the point-sampled raw value (empty when the plant falls
  outside the raster's valid extent). Reusable without recomputation.
* ``analysis/normalization_diagnostics.md`` — the full report (tasks 1-5).

Extraction method: point-sample of the processed 1 km rasters
(``water_stress_raw_*`` and ``extreme_heat_days_*``). Those rasters already
encode every methodological choice made so far (WRI sentinel -> country_max
substitution for water; the CDS download/resample extent for heat) and are
exactly what the index will consume. A plant is "matched" for a given
raster when its coordinate lands on a finite pixel; "no match" means NaN at
that pixel — either outside every Aqueduct basin (water) or outside the
country's heat-raster extent (heat).
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
    ASSETS_PROCESSED,
    AQUEDUCT_SCENARIOS,
    CLIMATE_PROCESSED,
    CMIP6_SCENARIOS,
    COUNTRIES,
)
from src.downloaders.cds_tasmax_downloader import configured_models  # noqa: E402

HERE = Path(__file__).resolve().parent
CSV_OUT = HERE / "plant_level_hazard_values.csv"
MD_OUT = HERE / "normalization_diagnostics.md"

PCTL_POINTS = [1, 5, 25, 50, 75, 95, 99]
MODELS = configured_models()

# Scenario-identity pairing between the two hazards (config.AQUEDUCT_SCENARIO_FOR_CMIP6):
# ssp126 <-> opt, ssp585 <-> pes. bau has no heat counterpart.
HEAT_TO_WATER_SCENARIO = {"ssp126": "opt", "ssp585": "pes"}


# --------------------------------------------------------------------------
# Small stats helpers (numpy only — scipy is not a project dependency)
# --------------------------------------------------------------------------
def skewness(a: np.ndarray) -> float:
    """Fisher-Pearson standardised moment coefficient (g1). NaN for n < 3 or
    zero variance."""
    a = np.asarray(a, dtype="float64")
    a = a[~np.isnan(a)]
    if a.size < 3:
        return float("nan")
    sd = a.std()
    if sd == 0:
        return float("nan")
    return float(np.mean(((a - a.mean()) / sd) ** 3))


def percentile_row(a: np.ndarray) -> dict:
    a = np.asarray(a, dtype="float64")
    a = a[~np.isnan(a)]
    row = {"n": int(a.size)}
    if a.size == 0:
        row.update({f"p{p}": float("nan") for p in PCTL_POINTS})
        row.update({"max": float("nan"), "skew": float("nan")})
        return row
    qs = np.percentile(a, PCTL_POINTS)
    row.update({f"p{p}": float(q) for p, q in zip(PCTL_POINTS, qs)})
    row["max"] = float(a.max())
    row["skew"] = skewness(a)
    return row


def pearson(x: np.ndarray, y: np.ndarray) -> float:
    m = ~(np.isnan(x) | np.isnan(y))
    if m.sum() < 3:
        return float("nan")
    x, y = x[m], y[m]
    if x.std() == 0 or y.std() == 0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    m = ~(np.isnan(x) | np.isnan(y))
    if m.sum() < 3:
        return float("nan")
    xr = pd.Series(x[m]).rank().to_numpy()
    yr = pd.Series(y[m]).rank().to_numpy()
    if xr.std() == 0 or yr.std() == 0:
        return float("nan")
    return float(np.corrcoef(xr, yr)[0, 1])


# --------------------------------------------------------------------------
# Raster point sampling
# --------------------------------------------------------------------------
def water_raster(country: str, scenario: str) -> Path:
    return CLIMATE_PROCESSED / f"water_stress_raw_{country}_{scenario}_1km.tif"


def heat_raster(country: str, model: str, scenario: str) -> Path:
    return CLIMATE_PROCESSED / f"extreme_heat_days_{country}_{model}_{scenario}_1km.tif"


def sample_points(raster_path: Path, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    """Nearest-pixel value at each (lon, lat). Returns NaN where the point is
    outside the raster or lands on a NaN / nodata pixel."""
    with rasterio.open(raster_path) as src:
        band = src.read(1).astype("float64")
        nodata = src.nodata
        if nodata is not None and not np.isnan(nodata):
            band[band == nodata] = np.nan
        rows, cols = rowcol(src.transform, lons, lats)
        rows = np.asarray(rows)
        cols = np.asarray(cols)
        h, w = band.shape
        inside = (rows >= 0) & (rows < h) & (cols >= 0) & (cols < w)
        out = np.full(lons.shape, np.nan, dtype="float64")
        out[inside] = band[rows[inside], cols[inside]]
    return out


# --------------------------------------------------------------------------
# Task 1 + 2 + CSV: plant-level extraction
# --------------------------------------------------------------------------
def load_plants(country: str) -> pd.DataFrame:
    df = pd.read_csv(ASSETS_PROCESSED / f"gem_validated_plants_{country}.csv")
    df = df.reset_index(drop=True)
    df["plant_uid"] = country + "::" + df.index.astype(str) + "::" + df["plant_name"].astype(str)
    return df


def extract_all() -> pd.DataFrame:
    records = []
    for country in COUNTRIES:
        plants = load_plants(country)
        lons = plants["lon"].to_numpy(dtype="float64")
        lats = plants["lat"].to_numpy(dtype="float64")

        base_cols = plants[
            ["plant_uid", "country", "plant_name", "lat", "lon",
             "capacity_mw", "commissioning_year", "fuel_type_bucket"]
        ]

        for scenario in AQUEDUCT_SCENARIOS:
            vals = sample_points(water_raster(country, scenario), lons, lats)
            part = base_cols.copy()
            part["hazard"] = "water_stress_raw"
            part["model"] = ""
            part["scenario"] = scenario
            part["value"] = vals
            part["matched"] = ~np.isnan(vals)
            records.append(part)

        for model in MODELS:
            for scenario in CMIP6_SCENARIOS:
                vals = sample_points(heat_raster(country, model, scenario), lons, lats)
                part = base_cols.copy()
                part["hazard"] = "extreme_heat_days"
                part["model"] = model
                part["scenario"] = scenario
                part["value"] = vals
                part["matched"] = ~np.isnan(vals)
                records.append(part)

    out = pd.concat(records, ignore_index=True)
    return out[
        ["country", "plant_name", "lat", "lon", "fuel_type_bucket", "capacity_mw",
         "commissioning_year", "hazard", "model", "scenario", "value", "matched", "plant_uid"]
    ]


# --------------------------------------------------------------------------
# Task 5: candidate transforms (0-1), descriptive only
# --------------------------------------------------------------------------
def t_linear_minmax(x: np.ndarray) -> np.ndarray:
    lo, hi = np.nanmin(x), np.nanmax(x)
    if hi == lo:
        return np.zeros_like(x)
    return (x - lo) / (hi - lo)


def t_log1p_minmax(x: np.ndarray) -> np.ndarray:
    y = np.log1p(x)
    lo, hi = np.nanmin(y), np.nanmax(y)
    if hi == lo:
        return np.zeros_like(y)
    return (y - lo) / (hi - lo)


def t_rank_quantile(x: np.ndarray) -> np.ndarray:
    r = pd.Series(x).rank(method="average").to_numpy()
    n = np.count_nonzero(~np.isnan(x))
    if n <= 1:
        return np.zeros_like(x)
    return (r - 1.0) / (n - 1.0)


def t_robust_clip(x: np.ndarray) -> np.ndarray:
    med = np.nanmedian(x)
    q1, q3 = np.nanpercentile(x, [25, 75])
    iqr = q3 - q1
    if iqr == 0:
        iqr = 1.0
    r = (x - med) / iqr
    lo, hi = np.nanpercentile(r, [1, 99])
    r = np.clip(r, lo, hi)
    if hi == lo:
        return np.zeros_like(r)
    return (r - lo) / (hi - lo)


TRANSFORMS = {
    "linear Min-Max (current)": t_linear_minmax,
    "log1p then Min-Max": t_log1p_minmax,
    "empirical rank / quantile": t_rank_quantile,
    "robust (median/IQR, clip p1/p99)": t_robust_clip,
}


def transform_shape_row(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype="float64")
    x = x[~np.isnan(x)]
    if x.size == 0:
        return {"p25": float("nan"), "p50": float("nan"), "p75": float("nan"), "skew": float("nan")}
    p25, p50, p75 = np.percentile(x, [25, 50, 75])
    return {"p25": float(p25), "p50": float(p50), "p75": float(p75), "skew": skewness(x)}


# --------------------------------------------------------------------------
# Markdown assembly
# --------------------------------------------------------------------------
def fmt(v: float, sig: str = "{:.4g}") -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return sig.format(v)


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    line = "| " + " | ".join(headers) + " |"
    sep = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    return "\n".join([line, sep, body])


def build_report(values: pd.DataFrame) -> str:
    out: list[str] = []
    out.append("# Normalisation diagnostics — plant-level hazard exposure\n")
    out.append(
        "Diagnostic only. No index / weighting / resilience logic. Generated by "
        "`analysis/normalization_diagnostics.py`; raw extraction in "
        "`analysis/plant_level_hazard_values.csv`.\n"
    )
    out.append(
        f"- Countries: {', '.join(COUNTRIES)}\n"
        f"- Water scenarios: {', '.join(AQUEDUCT_SCENARIOS)} (Aqueduct)\n"
        f"- Heat models x scenarios: {', '.join(MODELS)} x {', '.join(CMIP6_SCENARIOS)}\n"
        "- Extraction: nearest-pixel sample of the processed 1 km rasters "
        "(`water_stress_raw_*`, `extreme_heat_days_*`). 'No match' = NaN at the "
        "plant pixel (outside every basin, or outside the heat-raster extent).\n"
    )

    # ---------------------------------------------------------------- Task 1
    out.append("\n## 1. Plant-level extraction — match rates and distribution\n")
    out.append(
        "Per country / hazard / scenario: plants matched, plants with no match, "
        "and the percentile breakdown + skewness of the matched raw values. This "
        "is the distribution that feeds the index, distinct from the basin- / "
        "full-raster-level distributions in tasks 3.\n"
    )
    headers = ["country", "hazard", "model", "scenario", "n plants", "matched",
               "no match", "p1", "p5", "p25", "p50", "p75", "p95", "p99", "max", "skew"]
    rows = []
    for country in COUNTRIES:
        for hazard in ["water_stress_raw", "extreme_heat_days"]:
            sub_h = values[(values.country == country) & (values.hazard == hazard)]
            scen_keys = sorted(sub_h.groupby(["model", "scenario"]).groups.keys())
            for model, scenario in scen_keys:
                s = sub_h[(sub_h.model == model) & (sub_h.scenario == scenario)]
                n = len(s)
                matched = s[s.matched]
                pr = percentile_row(matched["value"].to_numpy())
                rows.append([
                    country, hazard, model or "—", scenario, str(n),
                    str(len(matched)), str(n - len(matched)),
                    fmt(pr["p1"]), fmt(pr["p5"]), fmt(pr["p25"]), fmt(pr["p50"]),
                    fmt(pr["p75"]), fmt(pr["p95"]), fmt(pr["p99"]), fmt(pr["max"]),
                    fmt(pr["skew"], "{:.3f}"),
                ])
    out.append(md_table(headers, rows))
    out.append(
        "\n_Observation (descriptive): the plant-level water distribution is "
        "shifted well above the basin-level one reported earlier (e.g. India "
        "plant p50 ~ 1.4-1.6 vs basin p50 ~ 0.58; Brazil plant p50 ~ 0.05 vs "
        "basin p50 ~ 0.0016) — plants concentrate in the more water-stressed "
        "basins. Heat is the same story against its own raster (task 3). No "
        "methodology conclusion drawn here._\n"
    )

    # ---------------------------------------------------------------- Task 2
    out.append("\n## 2. Plants with no match in at least one hazard\n")
    per_plant = (
        values.groupby(["plant_uid", "country", "plant_name", "fuel_type_bucket",
                         "capacity_mw", "lat", "lon", "hazard"])["matched"]
        .any()
        .unstack("hazard")
    )
    for hz in ["water_stress_raw", "extreme_heat_days"]:
        if hz not in per_plant.columns:
            per_plant[hz] = False
    unmatched = per_plant[~(per_plant["water_stress_raw"] & per_plant["extreme_heat_days"])]
    unmatched = unmatched.reset_index()

    out.append(
        f"A plant counts here when it matched **zero** scenarios of at least one "
        f"hazard. {len(unmatched)} plant(s). No decision on how to treat them — "
        f"enumeration only.\n"
    )
    if len(unmatched):
        by_country = unmatched.groupby("country").size().to_dict()
        out.append("Count by country: " + ", ".join(f"{k} {v}" for k, v in by_country.items()) + "\n")
        h2 = ["country", "plant_name", "fuel_bucket", "capacity_mw", "lat", "lon", "failed hazard(s)"]
        r2 = []
        for _, row in unmatched.sort_values(["country", "plant_name"]).iterrows():
            failed = []
            if not row["water_stress_raw"]:
                failed.append("water")
            if not row["extreme_heat_days"]:
                failed.append("heat")
            r2.append([
                row["country"], str(row["plant_name"]), str(row["fuel_type_bucket"]),
                fmt(row["capacity_mw"]), f"{row['lat']:.4f}", f"{row['lon']:.4f}",
                " + ".join(failed),
            ])
        out.append(md_table(h2, r2))
    else:
        out.append("_Every plant matched both hazards in at least one scenario._\n")

    # ---------------------------------------------------------------- Task 3
    out.append("\n## 3. Heat-stress distribution — plant level vs. full raster\n")
    out.append(
        "Percentiles + skewness of `extreme_heat_days` raw, per country / model / "
        "scenario, at plant level (matched plants, from task 1) and at full-raster "
        "level (every finite pixel). Parallels the water diagnostics already "
        "produced at basin level.\n"
    )
    h3 = ["country", "model", "scenario", "level", "n", "p1", "p5", "p25", "p50",
          "p75", "p95", "p99", "max", "skew"]
    r3 = []
    for country in COUNTRIES:
        for model in MODELS:
            for scenario in CMIP6_SCENARIOS:
                s = values[(values.country == country) & (values.hazard == "extreme_heat_days")
                           & (values.model == model) & (values.scenario == scenario) & values.matched]
                prp = percentile_row(s["value"].to_numpy())
                with rasterio.open(heat_raster(country, model, scenario)) as src:
                    band = src.read(1).astype("float64")
                    nod = src.nodata
                    if nod is not None and not np.isnan(nod):
                        band[band == nod] = np.nan
                prr = percentile_row(band.ravel())
                for level, pr in [("plant", prp), ("raster", prr)]:
                    r3.append([
                        country, model, scenario, level, str(pr["n"]),
                        fmt(pr["p1"]), fmt(pr["p5"]), fmt(pr["p25"]), fmt(pr["p50"]),
                        fmt(pr["p75"]), fmt(pr["p95"]), fmt(pr["p99"]), fmt(pr["max"]),
                        fmt(pr["skew"], "{:.3f}"),
                    ])
    out.append(md_table(h3, r3))
    out.append(
        "\nFor symmetry, the water raw distribution at **full-raster** level "
        "(processed `water_stress_raw_*`, every finite pixel, sentinel basins "
        "already substituted to country_max):\n"
    )
    h3w = ["country", "scenario", "n", "p1", "p5", "p25", "p50", "p75", "p95", "p99", "max", "skew"]
    r3w = []
    for country in COUNTRIES:
        for scenario in AQUEDUCT_SCENARIOS:
            with rasterio.open(water_raster(country, scenario)) as src:
                band = src.read(1).astype("float64")
                nod = src.nodata
                if nod is not None and not np.isnan(nod):
                    band[band == nod] = np.nan
            pr = percentile_row(band.ravel())
            r3w.append([
                country, scenario, str(pr["n"]), fmt(pr["p1"]), fmt(pr["p5"]),
                fmt(pr["p25"]), fmt(pr["p50"]), fmt(pr["p75"]), fmt(pr["p95"]),
                fmt(pr["p99"]), fmt(pr["max"]), fmt(pr["skew"], "{:.3f}"),
            ])
    out.append(md_table(h3w, r3w))

    # ---------------------------------------------------------------- Task 4
    out.append("\n## 4. Do the two hazards compound? (matched plants)\n")
    out.append(
        "Pearson and Spearman between `water_stress_raw` and `extreme_heat_days` "
        "raw, per country, on plants matched for both. Scenarios paired by SSP "
        "identity (ssp126 <-> opt, ssp585 <-> pes); the pooled row stacks both "
        "pairs.\n"
    )
    h4 = ["country", "pairing", "n plants", "Pearson r", "Spearman rho"]
    r4 = []
    corr_summary = {}
    for country in COUNTRIES:
        pooled_w, pooled_h = [], []
        for hs, ws in HEAT_TO_WATER_SCENARIO.items():
            w = values[(values.country == country) & (values.hazard == "water_stress_raw")
                       & (values.scenario == ws)].set_index("plant_uid")["value"]
            hh = values[(values.country == country) & (values.hazard == "extreme_heat_days")
                        & (values.scenario == hs) & (values.model == MODELS[0])].set_index("plant_uid")["value"]
            j = pd.concat([w.rename("w"), hh.rename("h")], axis=1).dropna()
            r4.append([
                country, f"{ws} / {hs}", str(len(j)),
                fmt(pearson(j["w"].to_numpy(), j["h"].to_numpy()), "{:.3f}"),
                fmt(spearman(j["w"].to_numpy(), j["h"].to_numpy()), "{:.3f}"),
            ])
            pooled_w.append(j["w"].to_numpy())
            pooled_h.append(j["h"].to_numpy())
        pw = np.concatenate(pooled_w) if pooled_w else np.array([])
        ph = np.concatenate(pooled_h) if pooled_h else np.array([])
        pr_, sr_ = pearson(pw, ph), spearman(pw, ph)
        corr_summary[country] = (pr_, sr_, len(pw))
        r4.append([country, "**pooled**", str(len(pw)),
                   fmt(pr_, "{:.3f}"), fmt(sr_, "{:.3f}")])
    out.append(md_table(h4, r4))
    verdict = []
    for country, (pr_, sr_, n) in corr_summary.items():
        if np.isnan(sr_):
            verdict.append(f"- **{country}**: not computable (n={n} or constant series).")
            continue
        mag = abs(sr_)
        direction = "compounding" if sr_ > 0 else "offsetting"
        if mag < 0.15:
            tag = "largely independent — being hit hard by one hazard says little about the other"
        elif mag < 0.4:
            tag = f"weakly {direction} — a mild tendency, not a strong one"
        elif mag < 0.7:
            tag = (f"moderately {direction} — "
                   + ("the same plants tend to face both" if sr_ > 0
                      else "plants high on one hazard tend to be lower on the other"))
        else:
            tag = f"strongly {direction}"
        verdict.append(f"- **{country}** (Spearman rho={sr_:.3f}, n={n}): {tag}.")
    out.append("\n".join(verdict) + "\n")

    # ---------------------------------------------------------------- Task 5
    out.append("\n## 5. Candidate transforms — shape comparison (plant level, per country)\n")
    out.append(
        "Plant-level matched values, all scenarios of a hazard pooled per country "
        "(water: bau+opt+pes; heat: ssp126+ssp585, first model). Each candidate "
        "maps to 0-1; the table shows p25/p50/p75 and skewness of the result so "
        "the shapes can be compared against the current linear Min-Max. "
        "Descriptive only — no winner picked, nothing implemented in `src/`.\n"
    )
    h5 = ["country", "hazard", "transform", "p25", "p50", "p75", "skew"]
    r5 = []
    for country in COUNTRIES:
        for hazard, scen_filter in [
            ("water_stress_raw", lambda v: v.hazard == "water_stress_raw"),
            ("extreme_heat_days", lambda v: (v.hazard == "extreme_heat_days") & (v.model == MODELS[0])),
        ]:
            s = values[(values.country == country) & scen_filter(values) & values.matched]
            x = s["value"].to_numpy(dtype="float64")
            x = x[~np.isnan(x)]
            if x.size == 0:
                r5.append([country, hazard, "(no matched plants)", "—", "—", "—", "—"])
                continue
            for name, fn in TRANSFORMS.items():
                shp = transform_shape_row(fn(x))
                r5.append([
                    country, hazard, name,
                    fmt(shp["p25"], "{:.3f}"), fmt(shp["p50"], "{:.3f}"),
                    fmt(shp["p75"], "{:.3f}"), fmt(shp["skew"], "{:.3f}"),
                ])
    out.append(md_table(h5, r5))
    out.append(
        "\n_Read: the rank/quantile transform is uniform by construction "
        "(skew ~ 0, quartiles ~ 0.25/0.5/0.75); log1p and robust-clip pull the "
        "mass off zero to differing degrees; linear Min-Max is the current "
        "baseline. Which distortion is acceptable is a methodology question "
        "deferred to the post-data revisit._\n"
    )

    out.append("\n---\n")
    out.append(
        f"Rasters read: `water_stress_raw_{{country}}_{{{','.join(AQUEDUCT_SCENARIOS)}}}_1km.tif`, "
        f"`extreme_heat_days_{{country}}_{{{','.join(MODELS)}}}_{{{','.join(CMIP6_SCENARIOS)}}}_1km.tif` "
        f"under `data/processed/climate/`. Plant tables: "
        f"`gem_validated_plants_{{country}}.csv` under `data/processed/assets/`.\n"
    )
    return "\n".join(out)


def main() -> int:
    values = extract_all()
    values.drop(columns=["plant_uid"]).to_csv(CSV_OUT, index=False)
    report = build_report(values)
    MD_OUT.write_text(report, encoding="utf-8")
    print(f"wrote {CSV_OUT.relative_to(HERE.parent)}  ({len(values)} rows)")
    print(f"wrote {MD_OUT.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
