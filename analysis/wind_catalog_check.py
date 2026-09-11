"""
Diagnostic-only CDS catalogue check for a CMIP6 sfcWind-based Extreme Wind
term, re-verifying the near_surface_wind_speed finding already recorded in
analysis/fwi_catalog_check.md (Phase 2.2 FWI investigation) for the two
configured GCMs (gfdl_esm4, miroc6) across the three active scenarios
(ssp126, ssp370, ssp585) over 2041-2070 -- specifically at daily resolution,
and against the exact grid/download pattern this pipeline already uses for
tasmax/pr (src/downloaders/cds_tasmax_downloader.py, CDS_VARIABLE =
"daily_maximum_near_surface_air_temperature").

Also checks whether a "daily maximum" sfcWind variant
(daily_maximum_near_surface_wind_speed / sfcWindmax) exists on the
catalogue, since the pipeline's own convention for tasmax is to use the
daily-MAXIMUM variant, not the daily-mean one, when both exist -- the prior
FWI check only queried near_surface_wind_speed (sfcWind, daily mean), which
is what the Canadian FWI System's noon-wind input needs, not what an
extreme-gust proxy would want.

Same method as analysis/spei_catalog_check.py / analysis/fwi_catalog_check.md:
POST projections-cmip6/constraints on the Copernicus CDS. Metadata endpoint
-- no data retrieved, nothing queued, no download.

Writes analysis/wind_catalog_check.md. No index/score/wind-processor code
touched.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import (  # noqa: E402
    CDS_API_KEY,
    CDS_API_URL,
    CMIP6_SCENARIO_TO_CDS_EXPERIMENT,
    CMIP6_SCENARIOS,
    CMIP6_SOURCE_ID_CDS,
    COUNTRIES,
)

HERE = Path(__file__).resolve().parent
OUT_MD = HERE / "wind_catalog_check.md"

CDS_DATASET = "projections-cmip6"

VARIABLES = {
    "near_surface_wind_speed": "sfcWind -- daily MEAN near-surface wind speed (already checked in the Phase 2.2 FWI investigation, re-verified here)",
    "daily_maximum_near_surface_wind_speed": "sfcWindmax -- daily MAXIMUM near-surface wind speed (this pipeline's established convention for tasmax: use the daily-max variant when it exists, not the daily-mean one)",
    "instantaneous_10m_wind_gust": "gust -- the ERA5 quantity already downloaded by era5_wind_downloader.py, checked here only to confirm it does NOT appear on the CMIP6 projections catalogue under this or any name",
}

MODELS = [m for m in CMIP6_SOURCE_ID_CDS if m]
SCENARIOS = list(CMIP6_SCENARIOS)
TARGET_YEARS = set(range(2041, 2071))


def _cds_constraints(selection: dict, tries: int = 4) -> dict:
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


def _md_table(headers: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]
    for r in rows:
        out.append("| " + " | ".join("" if c is None else str(c) for c in r) + " |")
    return "\n".join(out)


def _year_span(view: dict) -> tuple[str, bool, list[int]]:
    years = sorted(int(y) for y in view.get("year", []))
    if not years:
        return "-", False, []
    span = f"{years[0]}-{years[-1]}"
    missing = sorted(TARGET_YEARS - set(years))
    return span, not missing, missing


def main() -> int:
    lines: list[str] = []
    lines.append("# Extreme Wind (CMIP6 sfcWind) -- CDS catalogue re-check")
    lines.append("")
    lines.append(
        "Query: `POST projections-cmip6/constraints` on the Copernicus CDS "
        "(metadata only -- no data retrieved, nothing queued). Purpose: "
        "re-verify the `near_surface_wind_speed` finding already recorded in "
        "`analysis/fwi_catalog_check.md` specifically at daily resolution and "
        "against the exact grid/download pattern this pipeline uses for "
        "tasmax/pr, plus check whether a daily-MAXIMUM sfcWind variant "
        "exists (this pipeline's own convention for tasmax). No decision on "
        "Extreme Wind's data source here."
    )
    lines.append("")
    lines.append(
        f"- Models (`config.CMIP6_SOURCE_ID_CDS`): {', '.join(MODELS)}\n"
        f"- Scenarios (`config.CMIP6_SCENARIOS`): "
        f"{', '.join(f'{s} ({CMIP6_SCENARIO_TO_CDS_EXPERIMENT[s]})' for s in SCENARIOS)}\n"
        f"- Window: 2041-2070\n"
        f"- Countries ({', '.join(COUNTRIES)}): the `projections-cmip6` catalogue is "
        "global; the `area` subset is a retrieval parameter, not a catalogue "
        "constraint, so availability is identical for all three."
    )
    lines.append("")

    daily_vars = set(_cds_constraints({"temporal_resolution": "daily"}).get("variable", []))
    lines.append("## 0. Are the variables on the daily catalogue at all?")
    lines.append("")
    rows = []
    for var, desc in VARIABLES.items():
        rows.append([f"`{var}`", desc, "yes" if var in daily_vars else "**NO**"])
    lines.append(_md_table(["CDS variable", "meaning", "listed for temporal_resolution=daily"], rows))
    lines.append("")

    lines.append("## 1. Per variable x model -- all three active scenarios + 2041-2070")
    lines.append("")
    rows = []
    detail_rows = []
    for var, desc in VARIABLES.items():
        base = {"temporal_resolution": "daily", "variable": var}
        if var not in daily_vars:
            rows.append([f"`{var}`", "-", "n/a -- not on daily catalogue"])
            for model in MODELS:
                for s in SCENARIOS:
                    detail_rows.append([var, model, f"{s} ({CMIP6_SCENARIO_TO_CDS_EXPERIMENT[s]})",
                                        "n/a -- variable not on daily catalogue", "-", "-", "-"])
            continue
        var_models = set(_cds_constraints(base).get("model", []))
        for model in MODELS:
            if model not in var_models:
                rows.append([f"`{var}`", model, "**model not offered for this variable**"])
                for s in SCENARIOS:
                    detail_rows.append([var, model, f"{s} ({CMIP6_SCENARIO_TO_CDS_EXPERIMENT[s]})",
                                        "model unavailable", "-", "-", "-"])
                continue
            per_scen_ok = []
            for s in SCENARIOS:
                cds_exp = CMIP6_SCENARIO_TO_CDS_EXPERIMENT[s]
                view = _cds_constraints({**base, "model": model, "experiment": cds_exp})
                exps = set(view.get("experiment", []))
                if cds_exp not in exps and not view.get("year"):
                    detail_rows.append([var, model, f"{s} ({cds_exp})", "unavailable", "-", "-", "-"])
                    per_scen_ok.append(False)
                    continue
                span, covers, missing = _year_span(view)
                detail_rows.append([
                    var, model, f"{s} ({cds_exp})", "available", span,
                    "yes" if covers else "no",
                    "none" if not missing else f"{len(missing)} ({missing[0]}-{missing[-1]})",
                ])
                per_scen_ok.append(covers)
            ok_all = all(per_scen_ok)
            rows.append([f"`{var}`", model, "yes" if ok_all else "no -- see detail"])
    lines.append(_md_table(
        ["CDS variable", "model", "ssp126 + ssp370 + ssp585 all present, 2041-2070 covered"], rows))
    lines.append("")

    lines.append("## 2. Per variable x model x scenario detail")
    lines.append("")
    lines.append(_md_table(
        ["variable", "model", "scenario", "catalogue status", "year span offered",
         "covers 2041-2070", "years missing in window"], detail_rows))
    lines.append("")

    lines.append("## 3. Realisation member / grid")
    lines.append("")
    lines.append(
        "The `projections-cmip6` `constraints` endpoint does not expose the "
        "realization member (`r?i?p?f?`) or grid label -- fixed server-side, "
        "only visible in the NetCDF filename after a retrieval, same "
        "limitation already on record for tasmin/pr (`analysis/"
        "spei_catalog_check.md`). Whether `sfcWind`/`sfcWindmax` ship the "
        "same `r1i1p1f1` member as the already-downloaded tasmax series "
        "(gfdl_esm4 r1i1p1f1/gr1, miroc6 r1i1p1f1/gn) is NOT confirmed by "
        "this catalogue query and would need a real first download to check "
        "-- same open item already flagged for pr/tasmin/spei."
    )
    lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_MD.relative_to(HERE.parent)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
