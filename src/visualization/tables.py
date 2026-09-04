"""
CCRS summary tables -- new in Douglas's 2026-09-04 review round.

Every function here returns an in-memory ``pandas.DataFrame`` (never reads a
cached CSV, same rule as ``src/visualization/data.py``) and, for the
CLI/report entry point, is also written to ``data/outputs/tables/``. These
tables complement (or, in one case, replace) a figure:

- ``heat_band_gcm_comparison_table`` -- replaces the GFDL/MIROC6 comparison
  the old two-GCM-row HeatRiskBand map used to carry (B1).
- ``water_heat_contingency_capacity_table`` -- complements the
  WaterRiskBand x HeatRiskBand stacked-bar chart (B3) with the underlying
  numbers.
- ``national_ccrs_summary_table`` -- complements the national CCRS + Monte
  Carlo CI figure (C1) with the numbers behind it (C2).
- ``hazard_weight_provenance_table`` -- consolidates every weight used in the
  Hazard formula with its documented provenance (C3). Provenance strings are
  taken verbatim from ``docs/DECISIONS.md`` -- never invented here.
- ``monte_carlo_parameter_summary_table`` -- per (country, water_scenario,
  perturbation magnitude), point estimate + Monte Carlo CI (C5), replacing
  any figure-shaped Monte Carlo output.
- ``event_multiplier_table`` -- replaces ``plot_event_multiplier_by_country``
  (removed, B5): three numbers per country are better read as a table row
  than as a 3-bar chart -- see ``charts.py`` module docstring for the removal
  note.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import pandas as pd

from src.config import COUNTRIES, OUTPUT_TABLES
from src.index import monte_carlo as mc
from src.index import ccrs_calculator as ccrs
from src.index.ccrs_calculator import BUCKET_WEIGHTS, WATER_TO_HEAT, _PUBLISHED_WITHIN_WATER
from src.index.risk_bands import PRIMARY_GCM
from src.visualization import data as vdata

logger = logging.getLogger(__name__)

HIGH_HEAT_BANDS = ("HIGH", "EXTREME")

# --------------------------------------------------------------------------
# C6 -- EM-DAT spatial overlay validation: investigated, NOT implemented.
# See the task report for the full proposed design; this constant is the
# recorded finding, kept next to the other table functions so a reader
# grepping this module for "C6" finds the status instead of a silent gap.
# --------------------------------------------------------------------------
C6_INVESTIGATION_NOTE = (
    "C6 (EM-DAT x hazard spatial overlay validation) is not implemented -- "
    "exploratory only, per Douglas's 2026-09-04 review. Feasibility check "
    "against data/outputs/inspection/emdat_coverage.csv (src/downloaders/"
    "emdat_downloader.py's coverage_report): point-level Latitude/Longitude "
    "coverage is 5.3-12.1% of events (Brazil 12.1%, Portugal 5.3% -- only 2 "
    "events, India 10.5%), too sparse for a point-level overlay. The "
    "structured 'GADM Admin Units' field covers 50.3-52.6% of events across "
    "all three countries -- enough for an admin-1-polygon-level overlay, "
    "not a point-level one. Proposed design (not built): assign each "
    "geocoded event to its GADM admin-1 polygon(s), aggregate the relevant "
    "Hazard term (water_sub for Flood/Drought, T_heat for Extreme "
    "temperature, T_spei for Drought) over the plants/raster cells inside "
    "that polygon, and compare the hazard distribution of polygons with a "
    "recorded event against polygons without one -- a Mann-Whitney U test "
    "(non-parametric, appropriate given the small per-country N and skewed "
    "hazard values) per country x disaster-type pair, shown as a box/strip "
    "plot with the test statistic and p-value annotated, not a single "
    "combined score. Caveats to carry into any future approval: ~50% "
    "non-coverage is a real sample-selection gap (not random -- better-"
    "documented/urban disasters likely over-represented in the geocoded "
    "half), Portugal's N=38 events limits any per-type split, a 'GADM Admin "
    "Units' entry may itself span multiple polygons or admin levels "
    "(unverified column-format detail), and a positive association would "
    "still not prove causation given three countries and multiple disaster "
    "types being compared. Awaiting Douglas's sign-off before any of this "
    "is coded."
)

# [2026-09-04, addendum] appended to the note itself (not just this comment)
# so a reader of C6_INVESTIGATION_NOTE alone still sees the outcome: Douglas
# approved the design above after reading this finding, and it is now
# implemented as src/index/emdat_validation.py (data/statistics) and
# src/visualization/emdat_validation.py (the box/strip plot). The coverage/
# proxy caveats above still apply verbatim -- they are also printed on the
# figure itself (emdat_validation.CAPTION), not only recorded here. One
# detail not anticipated in this note: the "GADM Admin Units" field mixes
# admin-1 and admin-2 (and occasionally admin-0) granularity per event, not
# a single level -- see emdat_validation's docstring for how that is
# resolved.
C6_INVESTIGATION_NOTE += (
    " [2026-09-04 addendum] Approved after this finding was reported -- now "
    "implemented as src/index/emdat_validation.py (data/statistics) and "
    "src/visualization/emdat_validation.py (the box/strip plot). The "
    "coverage/proxy caveats above still apply verbatim -- they are also "
    "printed on the figure itself (emdat_validation.CAPTION), not only "
    "recorded here. One detail not anticipated above: the 'GADM Admin "
    "Units' field mixes admin-1 and admin-2 (and occasionally admin-0) "
    "granularity per event, not a single level -- see emdat_validation's "
    "docstring for how that is resolved."
)


# --------------------------------------------------------------------------
# B1 -- GFDL vs MIROC6 comparison (replaces the second map panel)
# --------------------------------------------------------------------------
def heat_band_gcm_comparison_table(
    bands: dict | None = None, water_scenario: str = "bau", countries: list[str] | None = None,
) -> pd.DataFrame:
    """One row per country: % of V6-computable-base capacity in HIGH or
    EXTREME HeatRiskBand, GFDL-ESM4 vs MIROC6, and their difference. The
    metric a reader actually wants from the two-panel map this replaces --
    "does the sensitivity GCM disagree enough with the primary one to
    matter" -- stated as one number instead of requiring a visual
    side-by-side comparison of two maps."""
    countries = countries or COUNTRIES
    bands = bands if bands is not None else vdata.load_band_tables()
    heat_scenario = WATER_TO_HEAT[water_scenario]
    shares = vdata.load_heat_band_shares(bands)
    shares = shares[shares["heat_scenario"] == heat_scenario]

    rows = []
    for country in countries:
        sub = shares[shares["country"] == country]
        high = {}
        for gcm in ("gfdl_esm4", "miroc6"):
            g = sub[(sub["gcm"] == gcm) & (sub["band"].isin(HIGH_HEAT_BANDS))]
            high[gcm] = float(g["capacity_share"].sum())
        rows.append({
            "country": country, "heat_scenario": heat_scenario,
            "share_high_or_extreme_gfdl_esm4": high["gfdl_esm4"],
            "share_high_or_extreme_miroc6": high["miroc6"],
            "difference_miroc6_minus_gfdl": high["miroc6"] - high["gfdl_esm4"],
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# B3 -- WaterRiskBand x HeatRiskBand contingency, in capacity_mw
# --------------------------------------------------------------------------
def water_heat_contingency_capacity_table(
    bands: dict | None = None, gcm: str = PRIMARY_GCM, countries: list[str] | None = None,
) -> pd.DataFrame:
    """Long-format capacity (MW) per (country, water_scenario, WaterRiskBand,
    HeatRiskBand) combination, V6 computable base only -- the numbers behind
    the B3 stacked-bar chart."""
    from src.index import ccrs_report as cr

    countries = countries or COUNTRIES
    bands = bands if bands is not None else vdata.load_band_tables()
    frame = bands[gcm].frame
    frame = frame[frame["country"].isin(countries)]
    base = ccrs.computable_base(frame)

    rows = []
    group_cols = ["country", "water_scenario", "water_risk_band", "heat_risk_band"]
    for keys, g in base.groupby(group_cols, dropna=False):
        row = dict(zip(group_cols, keys))
        row["capacity_mw"] = cr.capacity_sum(g)
        rows.append(row)
    return pd.DataFrame(rows).sort_values(group_cols).reset_index(drop=True)


# --------------------------------------------------------------------------
# C2 -- national aggregate CCRS summary (point + CI + rank)
# --------------------------------------------------------------------------
def national_ccrs_summary_table(ci_frame: pd.DataFrame, gcm: str = PRIMARY_GCM) -> pd.DataFrame:
    """``ci_frame`` is ``monte_carlo.run_country_scenario_simulation``'s
    output (one row per country x water_scenario: ``point_estimate``,
    ``p2.5``, ``p50``, ``p97.5``). Adds a within-scenario rank (1 = highest
    CCRS) and the GCM label -- the numbers behind the C1 figure."""
    out = ci_frame.copy()
    out["gcm"] = gcm
    out["rank_within_scenario"] = (
        out.groupby("water_scenario")["point_estimate"].rank(ascending=False, method="min").astype(int)
    )
    cols = ["country", "water_scenario", "gcm", "point_estimate", "p2.5", "p50.0", "p97.5", "rank_within_scenario"]
    return out[cols].sort_values(["water_scenario", "rank_within_scenario"]).reset_index(drop=True)


# --------------------------------------------------------------------------
# C3 -- weight provenance, consolidated
# --------------------------------------------------------------------------
def hazard_weight_provenance_table() -> pd.DataFrame:
    """Every weight in the Hazard formula, with the provenance documented in
    ``docs/DECISIONS.md`` -- verbatim classification, not invented here:

    - The within-``water_sub`` weights (ws/sv/iv, 0.4164/0.2505/0.3331) are a
      **closed, derived** quantity: WRI Aqueduct 4.0 category step widths
      (``docs/DECISIONS.md`` "SPEI drought term added to Hazard", Reason
      section; ``analysis/climate_risk_score_spec.md`` Section 8.1).
    - The per-bucket (w_water, w_heat, w_drought) weights are an **explicit
      judgment call, not a calibration** -- Douglas's qualitative guidance,
      2026-09-04, no published water/heat/drought importance ratio exists for
      these technologies (``docs/DECISIONS.md``, same entry, "Per-bucket
      weights" section).
    """
    rows = []
    for term, weight in _PUBLISHED_WITHIN_WATER.items():
        rows.append({
            "weight": f"within-water_sub: {term}", "bucket": "n/a (applies inside every bucket's water_sub)",
            "value": weight,
            "provenance": "Closed, derived -- WRI Aqueduct 4.0 category step widths (w_k proportional to 1/tau_k)",
        })
    for bucket, w in BUCKET_WEIGHTS.items():
        for component, value in w.items():
            rows.append({
                "weight": f"bucket weight: w_{component}", "bucket": bucket, "value": value,
                "provenance": (
                    "Explicit judgment call (Douglas, 2026-09-04) -- not a calibration, no "
                    "published water/heat/drought importance ratio exists for this technology"
                ),
            })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# C4 -- relative contribution of each Hazard term, by country
# --------------------------------------------------------------------------
def hazard_term_contribution_table(
    gcm: str = PRIMARY_GCM, countries: list[str] | None = None,
) -> pd.DataFrame:
    """Capacity-weighted mean contribution of water/heat/drought to
    ``Hazard_{i,s}``, per country (and water_scenario) -- the numbers behind
    the C4 figure. Contribution is each term's weighted, transformed value
    (``w_water*water_sub``, ``w_heat*T_heat``, ``w_drought*T_spei``) as a
    share of their sum (``= Hazard``, by construction of ``ccrs_calculator.
    hazard``), capacity-weighted-averaged over the V6 computable base."""
    countries = countries or COUNTRIES
    hz = ccrs.compute_hazard(gcm)
    hz = hz[hz["country"].isin(countries)]
    base = ccrs.computable_base(hz)

    w_water = base["bucket"].map(lambda b: BUCKET_WEIGHTS[b]["water"])
    w_heat = base["bucket"].map(lambda b: BUCKET_WEIGHTS[b]["heat"])
    w_drought = base["bucket"].map(lambda b: BUCKET_WEIGHTS[b]["drought"])

    water_contrib = w_water * base["water_sub"]
    heat_contrib = w_heat * base["T_heat"]
    drought_contrib = w_drought * base["T_spei"]
    total = water_contrib + heat_contrib + drought_contrib

    frame = pd.DataFrame({
        "country": base["country"], "water_scenario": base["water_scenario"],
        "capacity_mw": base["capacity_mw"],
        "water_share": (water_contrib / total).where(total > 0),
        "heat_share": (heat_contrib / total).where(total > 0),
        "drought_share": (drought_contrib / total).where(total > 0),
    }).dropna(subset=["water_share", "heat_share", "drought_share"])

    def _wmean(g: pd.DataFrame) -> pd.Series:
        w = g["capacity_mw"]
        return pd.Series({
            "water_share": (g["water_share"] * w).sum() / w.sum(),
            "heat_share": (g["heat_share"] * w).sum() / w.sum(),
            "drought_share": (g["drought_share"] * w).sum() / w.sum(),
        })

    return frame.groupby(["country", "water_scenario"]).apply(_wmean, include_groups=False).reset_index()


# --------------------------------------------------------------------------
# C5 -- Monte Carlo tables (country x scenario x perturbation magnitude)
# --------------------------------------------------------------------------
def monte_carlo_parameter_summary_table(
    magnitudes: tuple[float, ...] = mc.MAGNITUDES, n: int = mc.N_ITERATIONS,
    pre: "mc._Precomputed | None" = None, model: str = PRIMARY_GCM,
) -> pd.DataFrame:
    """Point estimate + CI per (country, water_scenario, magnitude), one row
    per group per magnitude -- the un-pooled counterpart of
    ``monte_carlo.run_country_scenario_simulation`` (which pools every
    magnitude into one envelope for the C1 figure). This table keeps the
    three perturbation magnitudes as separate rows, since a table can carry
    that extra dimension without becoming unreadable the way a single figure
    would."""
    pre = pre or mc._Precomputed()
    frames = []
    for magnitude in magnitudes:
        ci = mc.run_country_scenario_simulation(magnitudes=(magnitude,), n=n, pre=pre, model=model)
        ci["magnitude"] = magnitude
        frames.append(ci)
    out = pd.concat(frames, ignore_index=True)
    out["gcm"] = model
    return out[["country", "water_scenario", "gcm", "magnitude", "point_estimate", "p2.5", "p50.0", "p97.5"]]


# --------------------------------------------------------------------------
# B5 (removal note) -- EventMultiplier as a table, not a 3-bar chart
# --------------------------------------------------------------------------
def event_multiplier_table(event_multipliers: pd.DataFrame | None = None) -> pd.DataFrame:
    em = event_multipliers if event_multipliers is not None else vdata.load_event_multipliers()
    return em[["country", "n_events", "rate", "event_multiplier"]].sort_values("country").reset_index(drop=True)


# --------------------------------------------------------------------------
# CLI -- writes every table to data/outputs/tables/
# --------------------------------------------------------------------------
def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=OUTPUT_TABLES)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    heat_band_gcm_comparison_table().to_csv(args.out_dir / "heat_band_gcm_comparison.csv", index=False)
    water_heat_contingency_capacity_table().to_csv(args.out_dir / "water_heat_contingency_capacity.csv", index=False)
    hazard_weight_provenance_table().to_csv(args.out_dir / "hazard_weight_provenance.csv", index=False)
    hazard_term_contribution_table().to_csv(args.out_dir / "hazard_term_contribution.csv", index=False)
    event_multiplier_table().to_csv(args.out_dir / "event_multiplier.csv", index=False)

    pre = mc._Precomputed()
    ci = mc.run_country_scenario_simulation(pre=pre)
    national_ccrs_summary_table(ci).to_csv(args.out_dir / "national_ccrs_summary.csv", index=False)
    monte_carlo_parameter_summary_table(pre=pre).to_csv(args.out_dir / "monte_carlo_national_summary.csv", index=False)

    logger.info("wrote all visualization summary tables to %s", args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
