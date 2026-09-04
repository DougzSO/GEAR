"""
CCRS risk bands -- ``WaterRiskBand`` and ``HeatRiskBand``, per plant.

The CCRS classifies each plant with **two independent discrete bands**
(``docs/ARCHITECTURE.md`` Section 5.2, ``analysis/climate_risk_score_spec.md``
Section 8). They are never merged into one score: the water side rests on
externally-published absolute thresholds and the heat side does not, so a
single combined band would inherit the weaker basis (spec Section 8.3). This
module produces the two as **separate columns** plus an optional auxiliary
``WaterRiskBand x HeatRiskBand`` contingency table -- nothing here returns a
single number that mixes them.

Depends only on ``src/index/ccrs_calculator.py`` (T1) for the plant sample,
the raw term values, the within-water weights and ``plant_uid``.

--------------------------------------------------------------------------
WaterRiskBand -- absolute, WRI Aqueduct 4.0 anchored
--------------------------------------------------------------------------
    S_water = 0.4164 * ws_raw + 0.2505 * sv_raw + 0.3331 * iv_raw

over the RAW (sentinel-substituted) Aqueduct layers -- NOT the transformed
terms. ``(0.4164, 0.2505, 0.3331)`` are ``ccrs_calculator.WITHIN_WATER_WEIGHTS``
(``w_k`` proportional to ``1/tau_k``, the WRI High->Extremely-High thresholds).

**``S_water`` here is NOT ``ccrs_calculator``'s ``water_sub``.** They share the
same three weights but operate on different scales for different purposes:
``water_sub`` = ``0.4164*Tlog(ws) + 0.2505*Tlin(sv) + 0.3331*Tlin(iv)`` over the
globally Min-Max-normalised terms, in ``[0, 1]``, feeding the numeric Hazard
*score*; ``S_water`` here = ``0.4164*ws_raw + 0.2505*sv_raw + 0.3331*iv_raw``
over untransformed physical values (can exceed 1), so that the cuts can be
anchored to the absolute WRI Aqueduct 4.0 category boundaries -- a
*classification*, not a score. Same weights, different scale, different job.

    cut          S_water   band boundary
    -----------  --------  ------------------------------
    0.208        Low            -> Low-Medium
    0.415        Low-Medium     -> Medium-High
    0.667        Medium-High    -> High
    1.0          High           -> Extremely-High

Each cut is the value of ``S_water`` when ``ws``/``sv``/``iv`` all sit exactly
on the same WRI category boundary (spec Section 8.1). The published top cut is
0.999385, rounded to 1.0 in ``ARCHITECTURE.md`` Section 5.2 and used as 1.0
here. Cuts are **left-closed**: a value exactly on a cut goes to the higher
band. **These cuts are fixed constants** -- they do not depend on any data
pool, country or GCM, so WaterRiskBand is stable across runs.

--------------------------------------------------------------------------
HeatRiskBand -- sample-relative percentile cuts
--------------------------------------------------------------------------
``extreme_heat_days`` (mean days/yr with tasmax > 40 C) classified on its own
at the **pooled p25 / p75 / p95** of this study's plant sample under the
**primary GCM, GFDL-ESM4** -- every ``(plant_uid, scenario)`` row with a
finite GFDL-ESM4 heat value, all three countries and all three scenarios
pooled into one sample. GFDL-ESM4 and MIROC6 are **never pooled together**
(``docs/DECISIONS.md`` "[2026-09-04] CCRS global Min-Max bounds ...", and
``ARCHITECTURE.md`` Section 5.4). ``compute_bands`` accepts another configured
GCM for the sensitivity panel; it then uses that GCM's **own** pooled
percentiles, never a blend.

    LOW  <  p25  <=  MEDIUM  <  p75  <=  HIGH  <  p95  <=  EXTREME

**HeatRiskBand is not comparable across runs** whose scenario/GCM pool
differs from the current data snapshot -- the cuts move with the sample.
``HEAT_BAND_WARNING`` states this and is emitted verbatim in every report the
module writes (``build_summary``), not only in code comments.

--------------------------------------------------------------------------
Capacity
--------------------------------------------------------------------------
Any capacity share in the summary is over the **V6 computable base**
(``ccrs_calculator.computable_base`` -- coordinates + ``commissioning_year``),
per ``ARCHITECTURE.md`` Section 5.5. Capacity never enters a band cut.

Standalone: ``python -m src.index.risk_bands`` from the project root. Writes
``data/outputs/tables/ccrs_risk_bands.csv`` and
``data/outputs/tables/ccrs_risk_bands_report.md``.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pandas as pd

# T1 is this module's only project dependency. Names re-exported from
# ccrs_calculator (PLANT_UID, WATER_SCENARIOS, WITHIN_WATER_WEIGHTS,
# configured_models, computable_base, sample_terms, OUTPUT_TABLES) are reached
# through it on purpose, so the dependency graph stays "risk_bands -> T1" only.
from src.index import ccrs_calculator as ccrs

logger = logging.getLogger(__name__)

PLANT_UID = ccrs.PLANT_UID

# --------------------------------------------------------------------------
# WaterRiskBand -- fixed absolute cuts (spec Section 8.1 / ARCHITECTURE 5.2)
# --------------------------------------------------------------------------
WATER_RISK_BANDS = ("Low", "Low-Medium", "Medium-High", "High", "Extremely-High")
WATER_BAND_CUTS = (0.208, 0.415, 0.667, 1.0)   # published: 0.208 / 0.415 / 0.667 / 0.999~=1.0
assert len(WATER_BAND_CUTS) == len(WATER_RISK_BANDS) - 1
assert list(WATER_BAND_CUTS) == sorted(WATER_BAND_CUTS)

# --------------------------------------------------------------------------
# HeatRiskBand -- sample-relative percentile cuts (spec Section 8.2)
# --------------------------------------------------------------------------
HEAT_RISK_BANDS = ("LOW", "MEDIUM", "HIGH", "EXTREME")
HEAT_BAND_PERCENTILES = (25, 75, 95)
# GFDL-ESM4 is the primary GCM for every cited CCRS figure; it is the first
# configured model. Fail loud if the config order ever changes.
PRIMARY_GCM = "gfdl_esm4"
assert PRIMARY_GCM == ccrs.configured_models()[0], (
    f"PRIMARY_GCM={PRIMARY_GCM!r} is no longer configured_models()[0]="
    f"{ccrs.configured_models()[0]!r}"
)

HEAT_BAND_WARNING = (
    "HeatRiskBand is sample-relative and is NOT comparable across runs. Its "
    "cuts are the p25/p75/p95 of extreme_heat_days over this study's plant "
    "sample under the primary GCM (gfdl_esm4), with all three scenarios "
    "pooled; any run whose scenario or GCM pool differs from the current data "
    "snapshot produces different cuts and a non-comparable classification. "
    "GFDL-ESM4 and MIROC6 are never pooled together. WaterRiskBand is the "
    "opposite: it uses fixed absolute WRI Aqueduct 4.0 cuts "
    "(0.208 / 0.415 / 0.667 / 1.0) that depend on neither the data pool nor "
    "the GCM, and IS stable across runs."
)

# Column layout of the per-plant band table.
_OUTPUT_COLUMNS = [
    PLANT_UID, "country", "plant_name", "water_scenario", "heat_scenario",
    "bucket", "capacity_mw", "commissioning_year",
    "ws_raw", "sv_raw", "iv_raw", "s_water", "water_risk_band",
    "heat_days", "heat_risk_band",
]


class BandTable(NamedTuple):
    """Return of ``compute_bands``: the per-plant band frame plus the heat
    percentile cuts actually used and the GCM they came from."""

    frame: pd.DataFrame
    heat_cuts: dict[int, float]
    heat_gcm: str


# --------------------------------------------------------------------------
# Pure band logic
# --------------------------------------------------------------------------
def s_water(ws_raw, sv_raw, iv_raw) -> np.ndarray:
    """``0.4164 * ws_raw + 0.2505 * sv_raw + 0.3331 * iv_raw`` over the RAW
    (untransformed, sentinel-substituted) Aqueduct values. NaN if any input is
    NaN.

    Not the same as ``ccrs_calculator.water_sub``: same three weights, but that
    one acts on the globally Min-Max-normalised ``Tlog``/``Tlin`` terms in
    ``[0, 1]`` for the Hazard score, whereas this acts on the physical values
    so the band cuts stay anchored to the absolute WRI category boundaries.
    """
    w = ccrs.WITHIN_WATER_WEIGHTS
    return (w["ws"] * np.asarray(ws_raw, "float64")
            + w["sv"] * np.asarray(sv_raw, "float64")
            + w["iv"] * np.asarray(iv_raw, "float64"))


def _bandize(values: np.ndarray, cuts, labels) -> np.ndarray:
    """Left-closed banding: label i covers ``[edges[i], edges[i+1])``. NaN
    values get ``None`` (no band)."""
    v = np.asarray(values, "float64")
    edges = [-np.inf, *cuts, np.inf]
    out = np.full(v.shape, None, dtype=object)
    for i, label in enumerate(labels):
        out[(v >= edges[i]) & (v < edges[i + 1])] = label
    out[np.isnan(v)] = None
    return out


def water_risk_band(s_water_values) -> np.ndarray:
    """Classify ``S_water`` into ``WATER_RISK_BANDS`` at the fixed absolute
    cuts ``WATER_BAND_CUTS``. GCM- and data-pool-independent."""
    return _bandize(s_water_values, WATER_BAND_CUTS, WATER_RISK_BANDS)


def heat_percentile_cuts(heat_days) -> dict[int, float]:
    """``{25: p25, 75: p75, 95: p95}`` of the finite ``heat_days`` sample
    (``numpy`` linear interpolation, matching the analysis diagnostics)."""
    h = np.asarray(heat_days, "float64")
    h = h[~np.isnan(h)]
    if h.size == 0:
        raise ValueError("heat_percentile_cuts: no finite heat_days values")
    return {p: float(np.percentile(h, p)) for p in HEAT_BAND_PERCENTILES}


def heat_risk_band(heat_days, cuts: dict[int, float]) -> np.ndarray:
    """Classify ``heat_days`` into ``HEAT_RISK_BANDS`` at the given
    ``{25,75,95}`` cuts (from ``heat_percentile_cuts``)."""
    ordered = [cuts[p] for p in HEAT_BAND_PERCENTILES]
    return _bandize(heat_days, ordered, HEAT_RISK_BANDS)


# --------------------------------------------------------------------------
# Per-plant band table
# --------------------------------------------------------------------------
def compute_bands(heat_gcm: str = PRIMARY_GCM) -> BandTable:
    """One row per ``(plant_uid, water_scenario)`` with both bands as separate
    columns.

    ``heat_gcm`` selects the GCM for the heat side (default: the primary GCM,
    ``gfdl_esm4``). The heat percentile cuts are that one GCM's own pooled
    p25/p75/p95 -- passing ``"miroc6"`` gives the sensitivity-panel bands, not
    a blend. ``water_risk_band`` never depends on ``heat_gcm``.
    """
    if heat_gcm not in ccrs.configured_models():
        raise ValueError(
            f"heat_gcm={heat_gcm!r} is not a configured GCM "
            f"({ccrs.configured_models()})"
        )

    df = ccrs.sample_terms(heat_gcm).rename(columns={
        "ws": "ws_raw", "sv": "sv_raw", "iv": "iv_raw", "heat": "heat_days",
    })
    df["s_water"] = s_water(df["ws_raw"], df["sv_raw"], df["iv_raw"])
    df["water_risk_band"] = water_risk_band(df["s_water"])

    cuts = heat_percentile_cuts(df["heat_days"])
    df["heat_risk_band"] = heat_risk_band(df["heat_days"], cuts)

    frame = df[_OUTPUT_COLUMNS].copy()
    return BandTable(frame=frame, heat_cuts=cuts, heat_gcm=heat_gcm)


def contingency_table(frame: pd.DataFrame, value: str = "count") -> pd.DataFrame:
    """Auxiliary ``WaterRiskBand`` (rows) x ``HeatRiskBand`` (columns) cross
    view. ``value``: ``"count"`` (plant_uid x scenario rows) or
    ``"capacity_mw"`` (summed installed capacity, computable base).

    This is a cross-tabulation, never a merge -- there is no cell that is a
    single combined score.
    """
    sub = frame.dropna(subset=["water_risk_band", "heat_risk_band"])
    if value == "count":
        tab = pd.crosstab(sub["water_risk_band"], sub["heat_risk_band"])
    elif value == "capacity_mw":
        base = ccrs.computable_base(sub)
        tab = base.pivot_table(
            index="water_risk_band", columns="heat_risk_band",
            values="capacity_mw", aggfunc="sum", fill_value=0.0,
        )
    else:
        raise ValueError(f"value must be 'count' or 'capacity_mw', got {value!r}")
    return tab.reindex(index=WATER_RISK_BANDS, columns=HEAT_RISK_BANDS, fill_value=0)


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
def _band_distribution(frame: pd.DataFrame, band_col: str, bands) -> pd.DataFrame:
    banded = frame.dropna(subset=[band_col])
    base = ccrs.computable_base(banded)
    cap_total = float(base["capacity_mw"].sum())
    rows = []
    for b in bands:
        n = int((banded[band_col] == b).sum())
        cap = float(base.loc[base[band_col] == b, "capacity_mw"].sum())
        rows.append({
            "band": b,
            "rows": n,
            "row_share": n / len(banded) if len(banded) else 0.0,
            "capacity_mw": cap,
            "capacity_share": cap / cap_total if cap_total else 0.0,
        })
    return pd.DataFrame(rows)


def build_summary(result: BandTable) -> str:
    """Human-readable report. Emits ``HEAT_BAND_WARNING`` verbatim and the
    "never merged into one score" statement."""
    frame, cuts, gcm = result
    lines: list[str] = []
    lines.append("# CCRS risk bands -- summary\n")

    lines.append("## Comparability warning\n")
    lines.append(HEAT_BAND_WARNING + "\n")
    if gcm != PRIMARY_GCM:
        lines.append(
            f"_This run used `{gcm}` for the heat side -- the MIROC6 "
            f"sensitivity panel, on its own pooled percentiles. Not the cited "
            f"figure._\n"
        )

    lines.append("## The two bands are never merged\n")
    lines.append(
        "WaterRiskBand and HeatRiskBand are reported as two separate columns "
        "(and, below, as an auxiliary cross-tabulation). No value in this "
        "report combines them into a single risk number or ordinal score "
        "(spec Section 8.4/8.5).\n"
    )

    lines.append("## WaterRiskBand -- absolute WRI Aqueduct 4.0 cuts (fixed)\n")
    lines.append(
        "`S_water = 0.4164*ws_raw + 0.2505*sv_raw + 0.3331*iv_raw`; cuts "
        "0.208 / 0.415 / 0.667 / 1.0 (left-closed). Independent of data pool "
        "and GCM; stable across runs.\n"
    )
    lines.append(_band_distribution(frame, "water_risk_band", WATER_RISK_BANDS)
                 .to_string(index=False) + "\n")

    lines.append(f"## HeatRiskBand -- sample-relative percentile cuts ({gcm})\n")
    lines.append(
        f"`extreme_heat_days` pooled p25/p75/p95 = "
        f"{cuts[25]:.4g} / {cuts[75]:.4g} / {cuts[95]:.4g} days/yr > 40 C "
        f"(all countries, 3 scenarios pooled). By construction the pooled "
        f"split is ~25 / 50 / 20 / 5 %.\n"
    )
    lines.append(_band_distribution(frame, "heat_risk_band", HEAT_RISK_BANDS)
                 .to_string(index=False) + "\n")

    lines.append("## Auxiliary cross view -- WaterRiskBand x HeatRiskBand (row counts)\n")
    lines.append(contingency_table(frame, "count").to_string() + "\n")
    lines.append(
        "\nCross-tabulation only. Capacity in each cell "
        "(`contingency_table(frame, 'capacity_mw')`) is an auxiliary output "
        "too; the two bands are still never summed into one number.\n"
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--heat-gcm", default=PRIMARY_GCM, choices=ccrs.configured_models(),
        help="GCM for the heat side (default: the primary GCM, gfdl_esm4)",
    )
    parser.add_argument("--out-dir", type=Path, default=ccrs.OUTPUT_TABLES)
    args = parser.parse_args()

    result = compute_bands(args.heat_gcm)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = args.out_dir / "ccrs_risk_bands.csv"
    result.frame.to_csv(csv_path, index=False)

    report = build_summary(result)
    report_path = args.out_dir / "ccrs_risk_bands_report.md"
    report_path.write_text(report, encoding="utf-8")

    logger.info("wrote %s (%d plant x scenario rows)", csv_path, len(result.frame))
    logger.info("wrote %s", report_path)
    logger.info("heat cuts (%s): p25=%.4g p75=%.4g p95=%.4g",
                result.heat_gcm, result.heat_cuts[25], result.heat_cuts[75],
                result.heat_cuts[95])
    logger.warning("%s", HEAT_BAND_WARNING)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
