"""
Diagnostic-only measurement for open verification items V2, V3/V4 and V6.

Standalone: run from the project root with
``.venv\\Scripts\\python -m analysis.verification_diagnostics`` (or
``python analysis/verification_diagnostics.py``). It reads only files already
produced by Stage 1/2 (the EM-DAT country CSVs and the validated-plant
tables) and queries the CDS catalogue for metadata only — no data download,
no index code, no ``age_factor`` / ``event_factor`` implementation. Same
pattern as ``analysis/normalization_diagnostics.py``.

Three outputs land next to this file, one per verification item:

* ``analysis/emdat_coverage_diagnostics.md`` — V2: how many climate-relevant
  EM-DAT events per country, and how many carry a usable administrative
  location (free-text ``Location``, structured ``Admin Units`` at adm1/adm2,
  ``GADM Admin Units``, point ``Latitude``/``Longitude``).
* ``analysis/gcm_catalog_check.md`` — V3/V4: for each candidate second GCM,
  whether the CDS ``projections-cmip6`` catalogue offers daily ``tasmax``
  for ssp1_2_6 + ssp3_7_0 + ssp5_8_5 together, over 2041-2070.
* ``analysis/naes_denominator_coverage.md`` — V6: the share of declared
  power-plant capacity that has both a coordinate and a commissioning year
  (the base the SCI/NAES can actually score).

The script measures and stops. It draws no conclusion about which admin
level, which GCM or which V6 treatment to adopt.
"""

from __future__ import annotations

import ast
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import (  # noqa: E402
    ASSETS_PROCESSED,
    CDS_API_KEY,
    CDS_API_URL,
    CLIMATE_RAW,
    CMIP6_SOURCE_ID_CDS,
    COUNTRIES,
    VALIDATION_RAW,
)
from src.downloaders.emdat_downloader import DISASTER_TYPES  # noqa: E402

HERE = Path(__file__).resolve().parent
EMDAT_MD = HERE / "emdat_coverage_diagnostics.md"
GCM_MD = HERE / "gcm_catalog_check.md"
NAES_MD = HERE / "naes_denominator_coverage.md"

# CDS ``projections-cmip6`` catalogue query (metadata only).
CDS_DATASET = "projections-cmip6"
CDS_TASMAX_VARIABLE = "daily_maximum_near_surface_air_temperature"
# Priority order given by the V4 task.
CANDIDATE_MODELS = ["ipsl_cm6a_lr", "miroc6", "mpi_esm1_2_lr", "cnrm_cm6_1"]
# The three scenarios that must be available *together* (ssp370 added in
# parity with the existing two if a second GCM is adopted).
REQUIRED_EXPERIMENTS = {
    "ssp1_2_6": "ssp126",
    "ssp3_7_0": "ssp370",
    "ssp5_8_5": "ssp585",
}
TARGET_YEARS = set(range(2041, 2071))


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------
def _md_table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    return "\n".join(out)


def _pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}%" if d else "n/a"


# --------------------------------------------------------------------------
# Task 1 / V2 — EM-DAT coverage and geocoding
# --------------------------------------------------------------------------
def _admin_unit_levels(cell: object) -> set[str]:
    """Which administrative tiers a structured ``Admin Units`` cell names.
    Returns a subset of {'adm1', 'adm2'} (EM-DAT only carries those two), or
    {'UNPARSEABLE'} when the JSON/list literal will not parse."""
    if cell is None or (isinstance(cell, float) and np.isnan(cell)):
        return set()
    text = str(cell).strip()
    if not text or text.lower() == "nan":
        return set()
    try:
        records = json.loads(text)
    except Exception:  # noqa: BLE001
        try:
            records = ast.literal_eval(text)
        except Exception:  # noqa: BLE001
            return {"UNPARSEABLE"}
    levels: set[str] = set()
    for rec in records:
        for field in rec:
            if field.startswith("adm1"):
                levels.add("adm1")
            elif field.startswith("adm2"):
                levels.add("adm2")
    return levels


def task1_emdat_coverage() -> str:
    lines: list[str] = []
    lines.append("# V2 — EM-DAT coverage and administrative geocoding")
    lines.append("")
    lines.append(
        "Source files: `data/raw/validation/emdat_{country}.csv`, written by "
        "`src/downloaders/emdat_downloader.py` at Stage 1. Descriptive only."
    )
    lines.append("")
    lines.append(
        "**Inclusion criteria actually applied by the downloader.** "
        "`filter_and_split_by_country` filters the EM-DAT Archive on two "
        "conditions only: `ISO` equals the country code, and `Disaster Type` "
        "is one of "
        + ", ".join(f"`{t}`" for t in DISASTER_TYPES)
        + ". It applies **no** &ge;10-deaths / &ge;100-affected / declared-"
        "emergency threshold of its own — that quadruple criterion is "
        "EM-DAT's own database-entry rule, already satisfied by every row in "
        "the Archive. The “eligible events” count below is therefore "
        "the full type-filtered row count. The severity-signal breakdown that "
        "follows is reported separately, and is lower than the row count "
        "mainly because pre-1990 events often carry no recorded deaths or "
        "affected figure."
    )
    lines.append("")

    # ---- eligible-event counts -------------------------------------------
    count_rows = []
    frames: dict[str, pd.DataFrame] = {}
    for country in COUNTRIES:
        df = pd.read_csv(VALIDATION_RAW / f"emdat_{country}.csv")
        frames[country] = df
        by_type = df["Disaster Type"].value_counts()
        count_rows.append([
            country,
            len(df),
            f"{int(df['Start Year'].min())}–{int(df['Start Year'].max())}",
            int(by_type.get("Drought", 0)),
            int(by_type.get("Extreme temperature", 0)),
            int(by_type.get("Flood", 0)),
            int(by_type.get("Storm", 0)),
        ])
    lines.append("## 1. Eligible events (type-filtered row count)")
    lines.append("")
    lines.append(_md_table(
        ["country", "eligible events", "year span",
         "Drought", "Extreme temp.", "Flood", "Storm"],
        count_rows,
    ))
    lines.append("")

    # ---- severity-signal breakdown -------------------------------------
    sev_rows = []
    for country in COUNTRIES:
        df = frames[country]
        n = len(df)
        deaths = pd.to_numeric(df["Total Deaths"], errors="coerce")
        affected = pd.to_numeric(df["Total Affected"], errors="coerce")
        decl = df["Declaration"].astype(str).str.strip().str.lower() == "yes"
        appeal = df["Appeal"].astype(str).str.strip().str.lower() == "yes"
        ofda = df["OFDA/BHA Response"].astype(str).str.strip().str.lower() == "yes"
        any_signal = (deaths >= 10) | (affected >= 100) | decl | appeal | ofda
        sev_rows.append([
            country, n,
            int((deaths >= 10).sum()),
            int((affected >= 100).sum()),
            int(decl.sum()),
            int(ofda.sum()),
            f"{int(any_signal.sum())} ({_pct(int(any_signal.sum()), n)})",
        ])
    lines.append("## 2. Severity signal present in the columns we hold")
    lines.append("")
    lines.append(_md_table(
        ["country", "events", "deaths ≥ 10", "affected ≥ 100",
         "Declaration = Yes", "OFDA/BHA = Yes", "≥ 1 signal"],
        sev_rows,
    ))
    lines.append("")
    lines.append(
        "`Appeal = Yes` is 0 in all three countries, so it is omitted from "
        "the table."
    )
    lines.append("")

    # ---- geocoding coverage -------------------------------------------
    geo_rows = []
    for country in COUNTRIES:
        df = frames[country]
        n = len(df)
        loc = df["Location"].astype(str).str.strip()
        loc_ok = int(((df["Location"].notna()) & (loc != "") & (loc.str.lower() != "nan")).sum())
        gadm_ok = int(df["GADM Admin Units"].notna().sum())
        latlon_ok = int((df["Latitude"].notna() & df["Longitude"].notna()).sum())
        geo_rows.append([
            country, n,
            f"{loc_ok} ({_pct(loc_ok, n)})",
            f"{gadm_ok} ({_pct(gadm_ok, n)})",
            f"{latlon_ok} ({_pct(latlon_ok, n)})",
        ])
    lines.append("## 3. Usable location fields (country level and below)")
    lines.append("")
    lines.append(_md_table(
        ["country", "events", "free-text `Location`",
         "`GADM Admin Units`", "point `Latitude`/`Longitude`"],
        geo_rows,
    ))
    lines.append("")
    lines.append(
        "`Location` is free text (“Bahia state”, “Northeastern "
        "states”, comma-separated municipality lists, vague directional "
        "descriptors); “parseable” here means only non-empty. "
        "`GADM Admin Units` carries structured GID codes; `Latitude`/"
        "`Longitude` is a single event centroid."
    )
    lines.append("")

    # ---- finer-than-country admin level -----------------------------
    adm_rows = []
    for country in COUNTRIES:
        df = frames[country]
        n = len(df)
        levels = df["Admin Units"].apply(_admin_unit_levels)
        nonnull = int(df["Admin Units"].notna().sum())
        adm1 = int(levels.apply(lambda s: "adm1" in s).sum())
        adm2 = int(levels.apply(lambda s: "adm2" in s).sum())
        unparseable = int(levels.apply(lambda s: "UNPARSEABLE" in s).sum())
        adm_rows.append([
            country, n,
            f"{nonnull} ({_pct(nonnull, n)})",
            f"{adm1} ({_pct(adm1, n)})",
            f"{adm2} ({_pct(adm2, n)})",
            unparseable,
        ])
    lines.append("## 4. Structured `Admin Units` by administrative tier")
    lines.append("")
    lines.append(
        "EM-DAT's `Admin Units` field is a JSON list of `{adm1_code, "
        "adm1_name}` (state / UF / region) and/or `{adm2_code, adm2_name}` "
        "(municipality / district) records. An event can name both tiers. "
        "Counts below are events carrying at least one record at that tier."
    )
    lines.append("")
    lines.append(_md_table(
        ["country", "events", "`Admin Units` non-null",
         "has adm1 (state)", "has adm2 (district)", "unparseable"],
        adm_rows,
    ))
    lines.append("")
    lines.append(
        "`GADM Admin Units` (structured GID, previous table) tracks "
        "`Admin Units` almost one-for-one — the small gaps are events "
        "whose EM-DAT admin name did not migrate to a GADM GID."
    )
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Task 2 / V3 + V4 — CDS catalogue availability for a second GCM
# --------------------------------------------------------------------------
def _cds_constraints(selection: dict, tries: int = 4) -> dict:
    """POST a partial selection to the ``projections-cmip6`` constraints
    endpoint and return the dict of still-valid values per field. Metadata
    only — this never retrieves data. Retries the transient 5xx the CDS
    gateway occasionally returns."""
    last: Exception | None = None
    for attempt in range(tries):
        resp = requests.post(
            f"{CDS_API_URL}/retrieve/v1/processes/{CDS_DATASET}/constraints",
            headers={"PRIVATE-TOKEN": CDS_API_KEY, "Content-Type": "application/json"},
            json={"inputs": selection},
            timeout=60,
        )
        if resp.status_code < 500:
            resp.raise_for_status()
            return resp.json()
        last = requests.HTTPError(f"{resp.status_code} {resp.reason}")
        time.sleep(2 * (attempt + 1))
    raise last  # type: ignore[misc]


def _reference_variant() -> str:
    """Variant label of the GCM already in use, read from a downloaded
    NetCDF filename if one exists (the CDS catalogue API does not expose the
    member)."""
    ref_model = next((m for m in CMIP6_SOURCE_ID_CDS if m), "gfdl_esm4")
    for nc in (CLIMATE_RAW / "cds_tasmax").rglob("*.nc"):
        parts = nc.stem.split("_")
        for p in parts:
            if p.startswith("r") and "i" in p and "p" in p and "f" in p:
                return f"{ref_model}: {p} (grid {parts[-2]}, from {nc.name})"
    return f"{ref_model}: no downloaded NetCDF found to read the member from"


def task2_gcm_catalog() -> str:
    lines: list[str] = []
    lines.append("# V3 + V4 — CDS catalogue check for a second GCM")
    lines.append("")
    lines.append(
        "Query: `POST projections-cmip6/constraints` on the Copernicus CDS "
        "(metadata endpoint — no data retrieved, nothing queued). For "
        "each candidate model the endpoint reports which `experiment` values "
        "and which `year` values remain valid once "
        "`temporal_resolution = daily` and "
        f"`variable = {CDS_TASMAX_VARIABLE}` are fixed."
    )
    lines.append("")
    lines.append(
        f"Reference model in use (`config.CMIP6_SOURCE_ID_CDS`): "
        f"**{_reference_variant()}**."
    )
    lines.append("")

    if not CDS_API_KEY:
        lines.append(
            "> **CDS_API_KEY absent from `credentials.local`.** The catalogue "
            "query could not run. Re-run this script with the key present."
        )
        lines.append("")
        return "\n".join(lines)

    try:
        base = {
            "temporal_resolution": "daily",
            "variable": CDS_TASMAX_VARIABLE,
        }
        daily_tasmax_models = set(_cds_constraints(base).get("model", []))
    except Exception as exc:  # noqa: BLE001
        lines.append(f"> **CDS query failed:** `{type(exc).__name__}: {exc}`")
        lines.append("")
        return "\n".join(lines)

    per_model_rows = []
    detail_rows = []
    for model in CANDIDATE_MODELS:
        has_var = model in daily_tasmax_models
        try:
            model_view = _cds_constraints({**base, "model": model})
        except Exception as exc:  # noqa: BLE001
            detail_rows.append([model, "query error", str(exc), "", ""])
            continue
        model_experiments = set(model_view.get("experiment", []))

        got_all = True
        for cds_exp, short in REQUIRED_EXPERIMENTS.items():
            if cds_exp not in model_experiments:
                detail_rows.append([model, f"{short} ({cds_exp})", "unavailable", "—", "—"])
                got_all = False
                continue
            try:
                exp_view = _cds_constraints({**base, "model": model, "experiment": cds_exp})
                years = {int(y) for y in exp_view.get("year", [])}
            except Exception as exc:  # noqa: BLE001
                detail_rows.append([model, f"{short} ({cds_exp})", f"year query error: {exc}", "", ""])
                got_all = False
                continue
            covers = TARGET_YEARS.issubset(years)
            got_all = got_all and covers
            span = f"{min(years)}–{max(years)}" if years else "—"
            detail_rows.append([
                model, f"{short} ({cds_exp})", "available", span,
                "yes" if covers else "no",
            ])

        per_model_rows.append([
            model,
            "yes" if has_var else "no",
            "yes" if (has_var and got_all) else "no",
            "not exposed by CDS catalogue API",
        ])

    lines.append("## 1. Per model — all three scenarios + 2041-2070 together")
    lines.append("")
    lines.append(_md_table(
        ["model (priority order)", "daily tasmax exists",
         "ssp126 + ssp370 + ssp585 all present, 2041-2070 covered",
         "variant / run"],
        per_model_rows,
    ))
    lines.append("")
    lines.append("## 2. Per model × scenario detail")
    lines.append("")
    lines.append(_md_table(
        ["model", "scenario", "catalogue status", "year span offered",
         "covers 2041-2070"],
        detail_rows,
    ))
    lines.append("")
    lines.append(
        "**Variant / run.** The CDS `projections-cmip6` catalogue and its "
        "`constraints` endpoint do not expose the realization member "
        "(`r?i?p?f?`) — it is fixed server-side and only visible in the "
        "NetCDF filename after a retrieval. `gfdl_esm4` returned "
        "`r1i1p1f1` / grid `gr1` (see reference line above). The member for "
        "each candidate above cannot be confirmed from the catalogue alone; "
        "it will be readable from the first real download and should be "
        "checked for `r1i1p1f1` parity at that point (CNRM-family models are "
        "the known exception — they commonly ship `r1i1p1f2`)."
    )
    lines.append("")

    # ---- Final V3 check: SSP3-7.0 for the reference GCM -----------------
    ref_model = next((m for m in CMIP6_SOURCE_ID_CDS if m), "gfdl_esm4")
    lines.append(f"## 3. Final V3 check — SSP3-7.0 for the reference GCM (`{ref_model}`)")
    lines.append("")
    lines.append(
        "ARCHITECTURE.md Section 9 (V3) adds SSP3-7.0 to the active scenario "
        "set only if the CDS catalogue offers it **for both** GCMs. MIROC6 "
        "is covered in the tables above; this is the check for "
        f"`{ref_model}`."
    )
    lines.append("")
    try:
        ref_view = _cds_constraints({**base, "model": ref_model})
        ref_has_ssp370 = "ssp3_7_0" in set(ref_view.get("experiment", []))
        if ref_has_ssp370:
            ref_years = {
                int(y) for y in _cds_constraints(
                    {**base, "model": ref_model, "experiment": "ssp3_7_0"}
                ).get("year", [])
            }
            covers = TARGET_YEARS.issubset(ref_years)
            span = f"{min(ref_years)}–{max(ref_years)}" if ref_years else "—"
            missing = sorted(TARGET_YEARS - ref_years)
        else:
            covers, span, missing = False, "—", sorted(TARGET_YEARS)
        lines.append(_md_table(
            ["model", "scenario", "catalogue status", "year span offered",
             "covers 2041-2070", "years missing in 2041-2070"],
            [[
                ref_model, "ssp370 (ssp3_7_0)",
                "available" if ref_has_ssp370 else "unavailable",
                span,
                "yes" if covers else "no",
                "none" if not missing else ", ".join(str(y) for y in missing),
            ]],
        ))
        lines.append("")
        verdict = (
            "SSP3-7.0 is available for the reference GCM over the full "
            "2041-2070 window — the V3 both-GCMs criterion is met."
            if ref_has_ssp370 and covers
            else "SSP3-7.0 is not available for the reference GCM over "
            "2041-2070 — the V3 both-GCMs criterion is not met."
        )
        lines.append(f"**Result:** {verdict}")
    except Exception as exc:  # noqa: BLE001
        lines.append(f"> **CDS query failed:** `{type(exc).__name__}: {exc}`")
    lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Task 3 / V6 — computable NAES denominator per country
# --------------------------------------------------------------------------
def task3_naes_denominator() -> str:
    lines: list[str] = []
    lines.append("# V6 — computable NAES/SCI denominator per country")
    lines.append("")
    lines.append(
        "Source files: `data/processed/assets/gem_validated_plants_{country}"
        ".csv` (Stage 1/2 output — GEM units already aggregated to "
        "plants, filtered to `Status == operating`). "
        "“Computable” = the plant has a usable coordinate **and** a "
        "`commissioning_year`, the two inputs a per-plant age/exposure score "
        "needs. Descriptive only."
    )
    lines.append("")

    rows = []
    fractions = {}
    for country in COUNTRIES:
        df = pd.read_csv(ASSETS_PROCESSED / f"gem_validated_plants_{country}.csv")
        n = len(df)
        lat = pd.to_numeric(df["lat"], errors="coerce")
        lon = pd.to_numeric(df["lon"], errors="coerce")
        coord_ok = (
            lat.notna() & lon.notna()
            & lat.between(-90, 90) & lon.between(-180, 180)
            & ~((lat == 0) & (lon == 0))
        )
        year_ok = pd.to_numeric(df["commissioning_year"], errors="coerce").notna()
        computable = coord_ok & year_ok

        total_cap = float(df["capacity_mw"].sum())
        comp_cap = float(df.loc[computable, "capacity_mw"].sum())
        frac = comp_cap / total_cap if total_cap else float("nan")
        fractions[country] = frac
        rows.append([
            country, n,
            f"{total_cap:,.1f}",
            int((~coord_ok).sum()),
            int((~year_ok).sum()),
            f"{df.loc[~year_ok, 'capacity_mw'].sum():,.1f}",
            int(computable.sum()),
            f"{comp_cap:,.1f}",
            f"{frac:.4f}",
        ])

    lines.append(_md_table(
        ["country", "plants", "total declared capacity_mw",
         "plants w/o coord", "plants w/o commissioning_year",
         "capacity_mw w/o year", "computable plants",
         "computable capacity_mw", "computable / total"],
        rows,
    ))
    lines.append("")

    hi = max(fractions, key=fractions.get)
    lo = min(fractions, key=fractions.get)
    spread = (fractions[hi] - fractions[lo]) * 100
    lines.append(
        f"Highest computable fraction: **{hi} {fractions[hi]:.4f}**. "
        f"Lowest: **{lo} {fractions[lo]:.4f}**. "
        f"Spread: **{spread:.2f} percentage points**."
    )
    lines.append("")
    lines.append(
        "Every plant in all three tables has a coordinate (`plants w/o "
        "coord` = 0); the only limiter on the denominator is a missing "
        "`commissioning_year`."
    )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    EMDAT_MD.write_text(task1_emdat_coverage(), encoding="utf-8")
    print(f"wrote {EMDAT_MD}")
    GCM_MD.write_text(task2_gcm_catalog(), encoding="utf-8")
    print(f"wrote {GCM_MD}")
    NAES_MD.write_text(task3_naes_denominator(), encoding="utf-8")
    print(f"wrote {NAES_MD}")


if __name__ == "__main__":
    main()
