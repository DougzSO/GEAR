"""
CCRS non-geospatial figures.

Categories: 5 (WaterRiskBand x HeatRiskBand combined-risk capacity bars,
rewritten from a heatmap -- B3), 6 (CCRS distribution by bucket, all three
scenarios -- B5), 7 (age_factor by bucket, secondary), 8 (capacity by risk
band, secondary), 9 (removed -- see below), 11 (Top-N CCRS breakdown by
bucket, rewritten -- B4), plus two new categories from Douglas's 2026-09-04
review: C1 (national aggregate CCRS with Monte Carlo CI) and C4 (relative
contribution of each Hazard term by country).

--------------------------------------------------------------------------
B5 -- figures moved to combined/secondary/, one removed
--------------------------------------------------------------------------
``age_factor_by_bucket``, ``capacity_by_risk_band`` and
``ccrs_distribution_by_bucket`` are kept (they carry real methodological/
result content -- a retention-curve sanity check, the headline capacity-share
result, and the per-bucket score distribution) but relocated to
``combined/secondary/`` per Douglas's review, separated from the primary
figures. ``ccrs_distribution_by_bucket`` is now generated for all three water
scenarios (previously bau only).

``plot_event_multiplier_by_country`` (category 9) is **removed**, not just
relocated: it drew 3 bars for 3 numbers (``EventMultiplier_c`` per country).
Three numbers are read faster and more precisely from a table than from a
bar chart with two annotation lines squeezed above each bar -- see
``src/visualization/tables.py``'s ``event_multiplier_table``, which carries
the exact same numbers.

--------------------------------------------------------------------------
Reused / adapted techniques
--------------------------------------------------------------------------
The per-column-normalized-for-color / real-value-annotated matrix technique
of the old repo's ``maps._draw_sci_component_heatmap_panel`` is still used by
category 11's Top-N breakdown; category 5's former contingency heatmap
(``_draw_matrix_panel``) was replaced by a stacked bar chart per Douglas's
review and no longer uses it. The overlaid-step-histogram small-multiple
technique of ``sensitivity_analysis.plot_resilience_norm_distribution_by_
bucket`` still backs category 6.
"""

from __future__ import annotations

import logging
import pathlib

import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import COUNTRIES, OUTPUT_MAPS
from src.index import monte_carlo as mc
from src.index.ccrs_calculator import BUCKETS, PLANT_UID
from src.index.risk_bands import HEAT_RISK_BANDS, PRIMARY_GCM, WATER_RISK_BANDS
from src.visualization import data as vdata
from src.visualization._common import (
    BUCKET_COLORS,
    HEAT_BAND_COLORS,
    HEAT_BAND_ORDER,
    SEQUENTIAL_CMAP,
    WATER_BAND_COLORS,
    WATER_BAND_ORDER,
    fs,
    save_figure,
)

logger = logging.getLogger(__name__)

OUT_DIR = OUTPUT_MAPS  # primary figures from this module are saved alongside the maps
SECONDARY_DIR = OUTPUT_MAPS / "combined" / "secondary"  # B5

SCENARIO_COLORS = {"opt": "#2ca02c", "bau": "#1f77b4", "pes": "#d62728"}
HAZARD_TERM_COLORS = {"water_share": "#1f77b4", "heat_share": "#d62728", "drought_share": "#8c564b"}


def _draw_matrix_panel(ax, cell_values: np.ndarray, row_labels, col_labels, title: str,
                        annotate_fmt: str = "{:,.0f}") -> None:
    """Per-column-normalized-for-color, real-value-annotated matrix -- reused
    technique from the old repo's ``_draw_sci_component_heatmap_panel``.
    Still used by category 11 only (category 5 no longer uses it, B3)."""
    col_min = cell_values.min(axis=0)
    col_max = cell_values.max(axis=0)
    col_range = np.where(col_max > col_min, col_max - col_min, 1.0)
    normalized = (cell_values - col_min) / col_range

    ax.imshow(normalized, aspect="auto", cmap=SEQUENTIAL_CMAP, vmin=0, vmax=1)
    for i in range(cell_values.shape[0]):
        for j in range(cell_values.shape[1]):
            ax.text(j, i, annotate_fmt.format(cell_values[i, j]), ha="center", va="center",
                     fontsize=fs(9), color="white" if normalized[i, j] > 0.5 else "black")
    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, fontsize=fs(9))
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=fs(9))
    ax.set_title(title, fontweight="bold", fontsize=fs(11))


def _stacked_bar(ax, shares: pd.DataFrame, group_cols: list[str], band_col: str,
                  band_order, band_colors: dict, value_col: str = "capacity_share",
                  ylim: tuple[float, float] | None = (0, 1.05)) -> None:
    groups = shares[group_cols].drop_duplicates().sort_values(group_cols)
    x_labels = [" / ".join(str(v) for v in row) for row in groups.itertuples(index=False)]
    x = np.arange(len(groups))
    bottom = np.zeros(len(groups))
    for band in band_order:
        heights = []
        for _, row in groups.iterrows():
            mask = np.all([shares[c] == row[c] for c in group_cols], axis=0)
            cell = shares[mask & (shares[band_col] == band)]
            heights.append(float(cell[value_col].iloc[0]) if len(cell) else 0.0)
        heights = np.array(heights)
        ax.bar(x, heights, bottom=bottom, color=band_colors.get(band, "#cccccc"), label=str(band))
        bottom += heights
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=fs(8))
    if ylim is not None:
        ax.set_ylim(*ylim)


# --------------------------------------------------------------------------
# Category 5 -- WaterRiskBand x HeatRiskBand combined-risk capacity bars
# (B3 rewrite: replaces the contingency heatmap with a stacked bar chart in
# the same visual language as capacity_by_risk_band -- bar color = risk
# level, bar height = capacity)
# --------------------------------------------------------------------------
WATER_RANK = {b: i for i, b in enumerate(WATER_BAND_ORDER)}
HEAT_RANK = {b: i for i, b in enumerate(HEAT_BAND_ORDER)}


def _combined_risk_level(water_band: pd.Series, heat_band: pd.Series) -> pd.Series:
    """One combined-severity label per row: the higher of the two bands'
    normalized rank (0..1), re-bucketed into the same four labels as
    HeatRiskBand (``LOW``/``MEDIUM``/``HIGH``/``EXTREME``) -- a defensible
    simplification, reported per Douglas's review, that lets 5 WaterRiskBand
    x 4 HeatRiskBand = 20 combinations collapse into 4 legible bar segments
    instead of a 20-color legend nobody could read. Rows with no band on
    either side (``NaN``) become ``"NO_BAND"``, consistent with
    ``ccrs_report.band_capacity_shares``'s convention."""
    w_norm = water_band.map(WATER_RANK) / (len(WATER_BAND_ORDER) - 1)
    h_norm = heat_band.map(HEAT_RANK) / (len(HEAT_BAND_ORDER) - 1)
    combined = np.maximum(w_norm, h_norm)
    labels = pd.cut(combined, bins=[-0.01, 0.25, 0.5, 0.75, 1.01], labels=HEAT_BAND_ORDER)
    return labels.astype(object).where(labels.notna(), None)


def plot_water_heat_combined_risk_bars(
    countries: list[str] | None = None, gcm: str = PRIMARY_GCM, bands: dict | None = None,
) -> dict[str, pathlib.Path]:
    """Category 5 -- per country, one figure: x-axis = water_scenario,
    stacked bars = share of V6-computable-base capacity at each combined
    WaterRiskBand/HeatRiskBand severity level. Complemented by
    ``src/visualization/tables.py``'s ``water_heat_contingency_capacity_table``
    (the full, non-collapsed numbers, in ``data/outputs/tables/``)."""
    from src.index import ccrs_report as cr

    countries = countries or COUNTRIES
    bands = bands if bands is not None else vdata.load_band_tables()
    frame = bands[gcm].frame.copy()
    frame["combined_risk"] = _combined_risk_level(frame["water_risk_band"], frame["heat_risk_band"])

    paths = {}
    for country in countries:
        sub = frame[frame["country"] == country]
        shares = cr.band_capacity_shares(sub, "combined_risk", HEAT_BAND_ORDER, ["water_scenario"])
        fig, ax = plt.subplots(figsize=(6, 6))
        _stacked_bar(ax, shares, ["water_scenario"], "band", HEAT_BAND_ORDER + ("NO_BAND",),
                     {**HEAT_BAND_COLORS, "NO_BAND": "#e0e0e0"})
        ax.set_ylabel("Capacity share", fontsize=fs(10))
        ax.set_xlabel("water_scenario", fontsize=fs(10))
        ax.legend(fontsize=fs(8), loc="upper right", ncol=2, title="Combined WaterRiskBand/HeatRiskBand severity",
                  title_fontsize=fs(8))
        fig.tight_layout()
        out_path = save_figure(fig, OUT_DIR / country / f"water_heat_combined_risk_bars_{gcm}.png")
        paths[country] = out_path
        logger.info("water_heat_combined_risk_bars (%s) saved to %s", country, out_path)
    return paths


# --------------------------------------------------------------------------
# Category 6 -- CCRS distribution by fuel_type_bucket (B5: all 3 scenarios)
# --------------------------------------------------------------------------
def plot_ccrs_distribution_by_bucket(
    countries: list[str] | None = None, gcm: str = PRIMARY_GCM, water_scenario: str = "bau",
    final: pd.DataFrame | None = None,
) -> pathlib.Path:
    """Small multiple (1 panel/country), overlaid step-histograms per
    bucket. Saved to ``combined/secondary/`` (B5). Call once per
    water_scenario to cover all three (B5 extends this from bau-only)."""
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    col = f"ccrs_{gcm}"
    sub = final[(final["water_scenario"] == water_scenario) & final["computable"]]

    fig, axes = plt.subplots(1, len(countries), figsize=(6 * len(countries), 5), sharex=True)
    axes = np.atleast_1d(axes)
    lo, hi = sub[col].min(), sub[col].max()
    bins = np.linspace(lo, hi, 21) if hi > lo else 21

    for ax, country in zip(axes, countries):
        country_df = sub[sub["country"] == country]
        for bucket in BUCKETS:
            values = country_df.loc[country_df["bucket"] == bucket, col]
            if len(values) == 0:
                continue
            ax.hist(values, bins=bins, histtype="step", linewidth=2.0,
                    color=BUCKET_COLORS[bucket], label=f"{bucket} (n={len(values):,})", density=True)
        ax.set_title(country, fontweight="bold", fontsize=fs(13))
        ax.set_xlabel(f"{col} ({water_scenario})", fontsize=fs(10))
        ax.legend(fontsize=fs(8), loc="upper right")
    axes[0].set_ylabel("Density", fontsize=fs(10))

    fig.tight_layout()
    out_path = save_figure(fig, SECONDARY_DIR / f"ccrs_distribution_by_bucket_{gcm}_{water_scenario}.png")
    logger.info("CCRS distribution by bucket (%s) saved to %s", water_scenario, out_path)
    return out_path


# --------------------------------------------------------------------------
# Category 7 -- age_factor by bucket/technology (B5: secondary)
# --------------------------------------------------------------------------
def plot_age_factor_by_bucket(
    countries: list[str] | None = None, age_factors: pd.DataFrame | None = None,
) -> pathlib.Path:
    """Box plot of ``age_factor`` per bucket x country. Saved to
    ``combined/secondary/`` (B5)."""
    countries = countries or COUNTRIES
    af = age_factors if age_factors is not None else vdata.load_age_factors()

    fig, ax = plt.subplots(figsize=(2.2 * len(countries) * len(BUCKETS) / 2 + 4, 6))
    positions = []
    box_data = []
    labels = []
    colors = []
    pos = 0
    group_gap = 1
    for country in countries:
        for bucket in BUCKETS:
            values = af.loc[(af["country"] == country) & (af["bucket"] == bucket), "age_factor"]
            if len(values) == 0:
                continue
            pos += 1
            positions.append(pos)
            box_data.append(values.to_numpy())
            neutral_frac = (
                af.loc[(af["country"] == country) & (af["bucket"] == bucket),
                       "age_factor_neutralized_missing_year"].mean()
            )
            labels.append(f"{bucket}\n{country}\n({neutral_frac:.0%} neutral)")
            colors.append(BUCKET_COLORS[bucket])
        pos += group_gap

    bp = ax.boxplot(box_data, positions=positions, patch_artist=True, widths=0.6, showfliers=False)
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_xticks(positions)
    ax.set_xticklabels(labels, fontsize=fs(7))
    ax.set_ylabel("age_factor (>= 1, 2050 horizon)", fontsize=fs(10))
    ax.axhline(1.0, color="black", linewidth=0.6, linestyle=":")
    fig.tight_layout()
    out_path = save_figure(fig, SECONDARY_DIR / "age_factor_by_bucket.png")
    logger.info("age_factor by bucket saved to %s", out_path)
    return out_path


# --------------------------------------------------------------------------
# Category 8 -- per-country capacity share by risk band (B5: secondary)
# --------------------------------------------------------------------------
def plot_capacity_by_risk_band(
    water_shares: pd.DataFrame | None = None, heat_shares: pd.DataFrame | None = None,
) -> pathlib.Path:
    """Stacked bar, % V6-computable-base capacity per WaterRiskBand (left)
    and HeatRiskBand (right, GFDL-ESM4 primary only), country x scenario.
    Saved to ``combined/secondary/`` (B5)."""
    water_shares = water_shares if water_shares is not None else vdata.load_water_band_shares()
    heat_shares = heat_shares if heat_shares is not None else vdata.load_heat_band_shares()
    heat_primary = heat_shares[heat_shares["gcm"] == PRIMARY_GCM]

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    _stacked_bar(axes[0], water_shares, ["country", "water_scenario"], "band",
                 WATER_RISK_BANDS + ("NO_BAND",),
                 {**WATER_BAND_COLORS, "NO_BAND": "#e0e0e0"})
    axes[0].set_title("WaterRiskBand", fontweight="bold", fontsize=fs(11))
    axes[0].set_ylabel("Capacity share", fontsize=fs(10))
    axes[0].legend(fontsize=fs(7), loc="upper right", ncol=2)

    _stacked_bar(axes[1], heat_primary, ["country", "heat_scenario"], "band",
                 HEAT_RISK_BANDS + ("NO_BAND",),
                 {**HEAT_BAND_COLORS, "NO_BAND": "#e0e0e0"})
    axes[1].set_title(f"HeatRiskBand ({PRIMARY_GCM}, primary)", fontweight="bold", fontsize=fs(11))
    axes[1].legend(fontsize=fs(7), loc="upper right", ncol=2)

    fig.tight_layout()
    out_path = save_figure(fig, SECONDARY_DIR / "capacity_by_risk_band.png")
    logger.info("Capacity by risk band saved to %s", out_path)
    return out_path


# --------------------------------------------------------------------------
# Category 11 -- Top-N CCRS breakdown, by bucket (B4 rewrite)
# --------------------------------------------------------------------------
def plot_top_n_ccrs_breakdown_by_bucket(
    countries: list[str] | None = None, gcm: str = PRIMARY_GCM, n: int = 5,
    final: pd.DataFrame | None = None,
) -> dict[str, pathlib.Path]:
    """Category 11, rewritten per Douglas's 2026-09-04 review (B4): per
    country, one small multiple with one horizontal-bar panel PER BUCKET
    (hydro/thermal/wind/solar never mixed in the same ranking), each
    showing its own top-``n`` plants by ``ccrs_{gcm}``.

    Chart-type choice, reported per the task: horizontal grouped bars
    (one panel per bucket) over the old single mixed-bucket heatmap,
    because (a) plant names are long text labels -- a horizontal bar's
    y-axis reads them without rotation, a heatmap's y-axis would not scale
    past ~15 rows before the labels overlap; (b) a bucket-per-panel small
    multiple makes "ranked #1 within its own technology" directly readable
    without a color-coded bucket column competing with the color-coded
    score column a mixed heatmap would need; (c) it stays legible at
    n=3/5/10 without resizing logic, since each panel's height already
    scales with n plants, not n x number of buckets."""
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    col = f"ccrs_{gcm}"
    computable = final[final["computable"]]

    paths = {}
    for country in countries:
        country_df = computable[computable["country"] == country]
        fig, axes = plt.subplots(1, len(BUCKETS), figsize=(4.2 * len(BUCKETS), 0.55 * n + 2.2))
        axes = np.atleast_1d(axes)
        for ax, bucket in zip(axes, BUCKETS):
            top = (
                country_df[country_df["bucket"] == bucket]
                .sort_values(col, ascending=False)
                .drop_duplicates(subset=[PLANT_UID])
                .head(n)
            )
            y = np.arange(len(top))[::-1]
            ax.barh(y, top[col], color=BUCKET_COLORS[bucket])
            ax.set_yticks(y)
            ax.set_yticklabels([str(name)[:22] for name in top["plant_name"]], fontsize=fs(8))
            ax.set_title(bucket, fontweight="bold", fontsize=fs(10))
            ax.set_xlabel(f"CCRS ({gcm})", fontsize=fs(9))
        fig.tight_layout()
        out_path = save_figure(fig, OUT_DIR / country / f"top{n}_ccrs_breakdown_by_bucket_{gcm}.png")
        paths[country] = out_path
        logger.info("Top-%d CCRS breakdown by bucket (%s) saved to %s", n, country, out_path)
    return paths


# --------------------------------------------------------------------------
# C1 -- national aggregate CCRS, with Monte Carlo CI
# --------------------------------------------------------------------------
def plot_national_ccrs_with_ci(
    countries: list[str] | None = None, ci_primary: pd.DataFrame | None = None,
    ci_secondary: pd.DataFrame | None = None, pre: "mc._Precomputed | None" = None,
    include_secondary_gcm: bool = True,
) -> pathlib.Path:
    """The central missing result Douglas flagged (C1): one CCRS score per
    country x water_scenario, with the Monte Carlo CI already implemented
    (``monte_carlo.run_country_scenario_simulation``, pooled across the
    three approved perturbation magnitudes -- see that function's
    docstring). Point + errorbar (2.5/50/97.5 percentile), GFDL-ESM4
    primary.

    GCM choice, reported per the task: MIROC6 is drawn in the SAME panel as
    a fainter, offset secondary marker (``include_secondary_gcm=True``,
    default) rather than a separate panel -- this is a compact, single
    headline result (unlike category 4's HeatRiskBand map, which is
    inherently spatial and benefits from a full second panel), and every
    other GCM-sensitivity comparison in this module (category 4's table,
    B1) already lives beside its primary figure rather than inside it, so a
    second full panel here would be redundant. Set
    ``include_secondary_gcm=False`` to drop it."""
    countries = countries or COUNTRIES
    if ci_primary is None:
        pre = pre or mc._Precomputed()
        ci_primary = mc.run_country_scenario_simulation(pre=pre, model=PRIMARY_GCM)
        if include_secondary_gcm and ci_secondary is None:
            ci_secondary = mc.run_country_scenario_simulation(pre=pre, model="miroc6")

    scenarios = ("opt", "bau", "pes")
    n_scenarios = len(scenarios)
    fig, ax = plt.subplots(figsize=(2.2 * len(countries) + 2, 6))
    x_base = np.arange(len(countries))
    span = 0.6
    offsets = {s: (i - (n_scenarios - 1) / 2) * (span / n_scenarios) for i, s in enumerate(scenarios)}

    for scenario in scenarios:
        sub = ci_primary[ci_primary["water_scenario"] == scenario].set_index("country").reindex(countries)
        x = x_base + offsets[scenario]
        y = sub["point_estimate"].to_numpy()
        lo = y - sub["p2.5"].to_numpy()
        hi = sub["p97.5"].to_numpy() - y
        ax.errorbar(x, y, yerr=[lo, hi], fmt="o", color=SCENARIO_COLORS[scenario],
                    markersize=7, capsize=4, elinewidth=1.4, zorder=3)
        if ci_secondary is not None:
            sub2 = ci_secondary[ci_secondary["water_scenario"] == scenario].set_index("country").reindex(countries)
            y2 = sub2["point_estimate"].to_numpy()
            lo2 = y2 - sub2["p2.5"].to_numpy()
            hi2 = sub2["p97.5"].to_numpy() - y2
            ax.errorbar(x + 0.02, y2, yerr=[lo2, hi2], fmt="D", color=SCENARIO_COLORS[scenario],
                        alpha=0.45, markersize=5, capsize=3, elinewidth=1.0, zorder=2)

    ax.set_xticks(x_base)
    ax.set_xticklabels(countries, fontsize=fs(10))
    ax.set_ylabel(f"CCRS ({PRIMARY_GCM}, capacity-weighted mean, Monte Carlo 95% CI)", fontsize=fs(10))

    scenario_handles = [mlines.Line2D([0], [0], marker="o", color=SCENARIO_COLORS[s], linestyle="None",
                                       markersize=8, label=s) for s in scenarios]
    gcm_handles = [mlines.Line2D([0], [0], marker="o", color="black", linestyle="None", markersize=7,
                                  label=f"{PRIMARY_GCM} (primary)")]
    if ci_secondary is not None:
        gcm_handles.append(mlines.Line2D([0], [0], marker="D", color="black", alpha=0.45, linestyle="None",
                                          markersize=6, label="miroc6 (sensitivity)"))
    ax.legend(handles=scenario_handles + gcm_handles, fontsize=fs(8), loc="upper left", ncol=2, frameon=False)

    fig.tight_layout()
    out_path = save_figure(fig, OUT_DIR / "combined" / f"national_ccrs_with_ci_{PRIMARY_GCM}.png")
    logger.info("National CCRS with Monte Carlo CI saved to %s", out_path)
    return out_path


# --------------------------------------------------------------------------
# C4 -- relative contribution of water/heat/drought to Hazard, by country
# --------------------------------------------------------------------------
def plot_hazard_term_contribution(
    countries: list[str] | None = None, contribution: pd.DataFrame | None = None, gcm: str = PRIMARY_GCM,
) -> pathlib.Path:
    """The structural argument for why Brazil/Portugal/India differ: the
    share of ``Hazard_{i,s}`` coming from water_sub, heat and drought,
    capacity-weighted, per country x water_scenario. Uses
    ``src/visualization/tables.py``'s ``hazard_term_contribution_table``."""
    from src.visualization import tables as vtables

    countries = countries or COUNTRIES
    contribution = contribution if contribution is not None else vtables.hazard_term_contribution_table(
        gcm=gcm, countries=countries,
    )
    scenarios = sorted(contribution["water_scenario"].unique())
    groups = contribution[["country", "water_scenario"]].drop_duplicates().sort_values(
        ["country", "water_scenario"]
    )
    x_labels = [f"{r.country} / {r.water_scenario}" for r in groups.itertuples(index=False)]
    x = np.arange(len(groups))

    fig, ax = plt.subplots(figsize=(1.4 * len(groups) + 3, 6))
    bottom = np.zeros(len(groups))
    for term_col, label in [("water_share", "water"), ("heat_share", "heat"), ("drought_share", "drought")]:
        heights = []
        for row in groups.itertuples(index=False):
            cell = contribution[(contribution["country"] == row.country)
                                 & (contribution["water_scenario"] == row.water_scenario)]
            heights.append(float(cell[term_col].iloc[0]) if len(cell) else 0.0)
        heights = np.array(heights)
        ax.bar(x, heights, bottom=bottom, color=HAZARD_TERM_COLORS[term_col], label=label)
        bottom += heights

    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=fs(8))
    ax.set_ylabel(f"Share of Hazard ({gcm})", fontsize=fs(10))
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=fs(9), loc="upper right", ncol=3)
    fig.tight_layout()
    out_path = save_figure(fig, OUT_DIR / "combined" / f"hazard_term_contribution_{gcm}.png")
    logger.info("Hazard term contribution saved to %s", out_path)
    return out_path
