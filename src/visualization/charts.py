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
2026-09-05 -- C4 reclassified secondary, replaced by a per-plant redesign
--------------------------------------------------------------------------
``plot_hazard_term_contribution`` (the capacity-weighted-mean bar chart) and
``tables.hazard_term_contribution_table`` (its numbers) move to
``combined/secondary/`` -- see the module comment directly above
``plot_hazard_term_contribution`` for the full reasoning. In one line: the
new ``plot_hazard_term_contribution_distribution`` (per-plant violin/
box+strip, unweighted vs. capacity-weighted) showed that Brazil's aggregate
bar was masking a real divergence between the typical plant and the typical
installed capacity -- a failure mode a single mean bar cannot surface.
Neither function is deleted; both are demoted, not removed.

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

# No qualitative palette for COUNTRY identity existed anywhere in this module
# before FIG 4's redesign (unlike SCENARIO_COLORS/BUCKET_COLORS/*_BAND_COLORS,
# all already established) -- picked here, deliberately avoiding hexes
# already used by those other qualitative dimensions in this same module
# (blue/green/red/gray/cyan/orange), so a reader is never misled into
# associating a country color with a scenario or bucket color in a different
# figure. Flagged as a new small palette decision, not silently invented.
COUNTRY_COLORS = {"Brazil": "#9467bd", "Portugal": "#8c564b", "India": "#e377c2"}


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
# FIG 3 -- systemic capacity vulnerability by technology bucket x scenario
# (Douglas's 2026-09-05 request -- promoted from secondary to a primary
# manuscript figure)
#
# "Parte da lógica já existe em capacity_by_risk_band ... falta o corte por
# bucket tecnológico" -- this is a direct, minimal extension of category 8's
# HeatRiskBand panel: ``ccrs_report.band_capacity_shares`` already accepts
# an arbitrary ``group_cols`` list, and ``bucket`` is already a column on
# every ``BandTable.frame`` (carried from T1 through risk_bands.py) -- no
# change to ccrs_report.py or risk_bands.py was needed, just a new call site
# with ``"bucket"`` added to the grouping, and ``_stacked_bar`` (already
# generic over group_cols) reused as-is.
#
# --------------------------------------------------------------------------
# Layout choice: (a) one panel per bucket, not (b) one merged figure
# --------------------------------------------------------------------------
# Option (b) would need a legend distinguishing every (bucket, band)
# combination that appears in a single stacked segment -- up to 4 buckets x
# 5 bands (4 HeatRiskBand levels + NO_BAND) = 20 combinations, on top of 9
# country x scenario x-groups already on one axis. That is not legible.
# Option (a) keeps each panel to ONE stacking dimension (band, at most 5
# colors) and moves bucket to the panel facet -- the same small-multiple
# principle already used by category 6 (``plot_ccrs_distribution_by_bucket``)
# and category 11 (Top-N breakdown), so it is also visually consistent with
# the other bucket-faceted figures in this module.
#
# --------------------------------------------------------------------------
# Risk-band axis: BOTH WaterRiskBand and HeatRiskBand, as two sister figures
# (Douglas's 2026-09-05 follow-up, replacing the HeatRiskBand-only version)
# --------------------------------------------------------------------------
# The HeatRiskBand-only version was a judgment call flagged for confirmation
# -- rejected: showing only the sample-relative axis would silently inherit
# HeatRiskBand's cross-run non-comparability (the same limitation already
# documented for the worst-case map, T4) without making that visible on the
# figure itself. Putting WaterRiskBand (stable, absolute WRI cuts) and
# HeatRiskBand (this run's own p25/p75/p95) side by side as two DIFFERENTLY
# LABELLED figures makes that asymmetry obvious from the figure identity
# alone (FIG 3a vs. FIG 3b), not just from a caption a reader might skip.
#
# --------------------------------------------------------------------------
# Two sister figures (3a, 3b), not one 8-panel figure -- legibility choice
# --------------------------------------------------------------------------
# The already-generated 4-panel HeatRiskBand-only version needed
# ~4.6in/panel x 4 = ~18in width to keep 9 country x scenario x-groups
# readable per panel. Doubling to 8 panels in one image would need ~37in
# width -- either an impractically large single image, or shrinking every
# panel to fit a normal page/column width, which directly undoes the
# legibility this small-multiple layout was chosen for in the first place.
# Two same-sized sister figures (FIG 3a: WaterRiskBand x 4 buckets, FIG 3b:
# HeatRiskBand x 4 buckets) keep each figure at the exact panel size already
# validated, placed side by side on the manuscript page (a page-layout
# decision, not something this code needs to force into one file) --
# achieving the same "obvious side-by-side asymmetry" Douglas asked for
# without the width/legibility tradeoff of a single 8-panel image.
#
# --------------------------------------------------------------------------
# Denominator convention (unchanged from the first version)
# --------------------------------------------------------------------------
# ``capacity_share`` in each (bucket, country, water_scenario) cell is a
# percentage of THAT BUCKET's own V6-computable-base capacity in that
# country/scenario -- e.g. "42% of Brazil's thermal capacity is
# HIGH/EXTREME under pes", not "42% of Brazil's total cross-technology
# capacity". This is the standard ``band_capacity_shares`` convention
# (same function, just with ``bucket`` in ``group_cols`` instead of held
# fixed), and it is the only denominator that makes "vulnerability of THIS
# technology" a legible statement -- a technology with little capacity in a
# country would otherwise round to ~0% under a whole-country denominator
# regardless of how exposed its own fleet is.
# --------------------------------------------------------------------------
def _capacity_vulnerability_by_bucket_figure(
    shares: pd.DataFrame, band_order: tuple, band_colors: dict, legend_title: str, out_path: pathlib.Path,
) -> pathlib.Path:
    """Shared 4-panel (one per bucket) renderer for FIG 3a/3b -- the two
    figures differ only in which band column/palette/legend title they
    were built with, not in panel layout."""
    fig, axes = plt.subplots(1, len(BUCKETS), figsize=(4.6 * len(BUCKETS), 6), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, bucket in zip(axes, BUCKETS):
        bucket_shares = shares[shares["bucket"] == bucket]
        _stacked_bar(ax, bucket_shares, ["country", "water_scenario"], "band",
                     band_order, band_colors)
        # bucket identity uses the project's fixed qualitative bucket palette
        # (BUCKET_COLORS, reused from maps.py/charts.py, no new color) --
        # the stacking dimension itself (the risk band) stays on its own
        # existing WATER_BAND_COLORS/HEAT_BAND_COLORS.
        ax.set_title(bucket, fontweight="bold", fontsize=fs(11), color=BUCKET_COLORS[bucket])
    axes[0].set_ylabel("Share of this bucket's own computable capacity", fontsize=fs(10))
    axes[-1].legend(fontsize=fs(7), loc="upper right", ncol=1,
                     title=legend_title, title_fontsize=fs(7))
    fig.tight_layout()
    out = save_figure(fig, out_path)
    logger.info("Capacity vulnerability by bucket saved to %s", out)
    return out


def plot_capacity_vulnerability_by_bucket_water(
    countries: list[str] | None = None, bands: dict | None = None,
) -> pathlib.Path:
    """FIG 3a -- one panel per technology bucket, WaterRiskBand-stacked
    bars, country x water_scenario on the x-axis. WaterRiskBand does not
    depend on GCM (risk_bands.py), so this figure has no ``gcm`` parameter,
    same convention as ``maps.plot_water_risk_band_map``. Promoted out of
    ``combined/secondary/`` -- saved directly under ``OUT_DIR``."""
    from src.index import ccrs_report as cr

    countries = countries or COUNTRIES
    bands = bands if bands is not None else vdata.load_band_tables()
    frame = bands[PRIMARY_GCM].frame  # water_risk_band is GCM-independent; any BandTable carries the same values
    shares = cr.band_capacity_shares(
        frame, "water_risk_band", WATER_RISK_BANDS, ["bucket", "country", "water_scenario"],
    )
    shares = shares[shares["country"].isin(countries)]
    return _capacity_vulnerability_by_bucket_figure(
        shares, WATER_RISK_BANDS + ("NO_BAND",), {**WATER_BAND_COLORS, "NO_BAND": "#e0e0e0"},
        "WaterRiskBand", OUT_DIR / "combined" / "capacity_vulnerability_by_bucket_water.png",
    )


def plot_capacity_vulnerability_by_bucket_heat(
    countries: list[str] | None = None, gcm: str = PRIMARY_GCM, bands: dict | None = None,
) -> pathlib.Path:
    """FIG 3b -- one panel per technology bucket, HeatRiskBand-stacked bars
    (GFDL-ESM4 primary), country x water_scenario on the x-axis. Same
    denominator/promotion/style convention as FIG 3a (WaterRiskBand) --
    see the module comment above for why these are two sister figures
    rather than one 8-panel image, and why BOTH axes are shown rather than
    heat alone."""
    from src.index import ccrs_report as cr

    countries = countries or COUNTRIES
    bands = bands if bands is not None else vdata.load_band_tables()
    frame = bands[gcm].frame
    shares = cr.band_capacity_shares(
        frame, "heat_risk_band", HEAT_RISK_BANDS, ["bucket", "country", "water_scenario"],
    )
    shares = shares[shares["country"].isin(countries)]
    return _capacity_vulnerability_by_bucket_figure(
        shares, HEAT_RISK_BANDS + ("NO_BAND",), {**HEAT_BAND_COLORS, "NO_BAND": "#e0e0e0"},
        f"HeatRiskBand ({gcm})", OUT_DIR / "combined" / f"capacity_vulnerability_by_bucket_heat_{gcm}.png",
    )


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
# FIG 4 redesign -- ordinal rank stability under Monte Carlo uncertainty
# (Douglas's 2026-09-05 request: the point+CI figure above does not show
# whether a country's apparent ranking advantage (e.g. India > Portugal)
# holds per-draw, or only on average)
#
# Two prototypes generated per the brief's explicit invitation to produce
# both when in doubt -- (a) density overlay and (b) rank-probability bars.
# Both are built from ``monte_carlo.run_country_scenario_draws`` (the newly
# retained per-draw data, see that function's docstring for the "no added
# simulation cost" confirmation) and share ``COUNTRY_COLORS`` (new, see
# above) for country identity across both prototypes.
#
# (a) is a density OVERLAY, not a literal offset ridge plot: with exactly 3
# countries, an offset/joyplot-style stack (built for telling apart many
# overlapping categories) adds a vertical-offset dimension that carries no
# information here and makes reading the actual overlap/separation between
# 3 curves harder, not easier -- a shared-axis overlay with alpha-fill shows
# the same separation/overlap directly. Point (a) in the brief itself names
# "ridge plot / density overlay" as one option, not two, so this is a choice
# within the option, not a substitution for it.
# --------------------------------------------------------------------------
def plot_ccrs_rank_density(
    countries: list[str] | None = None, draws: pd.DataFrame | None = None,
    pre: "mc._Precomputed | None" = None,
) -> pathlib.Path:
    """FIG 4 prototype (a) -- one panel per water_scenario, overlaid CCRS
    density curves (one per country, ``COUNTRY_COLORS``), a dashed vertical
    line at each country's median. Visual separation between two countries'
    curves is the same "systematic, not just on-average" evidence a
    non-overlapping CI shows, but directly at the distribution level rather
    than collapsed to a point + interval."""
    from scipy import stats as sp_stats

    countries = countries or COUNTRIES
    if draws is None:
        pre = pre or mc._Precomputed()
        draws = mc.run_country_scenario_draws(pre=pre)

    scenarios = ("opt", "bau", "pes")
    fig, axes = plt.subplots(1, len(scenarios), figsize=(5.5 * len(scenarios), 5.5), sharey=True)
    axes = np.atleast_1d(axes)
    lo, hi = draws["ccrs"].min(), draws["ccrs"].max()
    grid = np.linspace(lo, hi, 400) if hi > lo else np.array([lo])

    for ax, scenario in zip(axes, scenarios):
        for country in countries:
            values = draws.loc[(draws["country"] == country) & (draws["water_scenario"] == scenario), "ccrs"]
            values = values.dropna().to_numpy()
            if len(values) < 2 or np.ptp(values) == 0:
                continue
            density = sp_stats.gaussian_kde(values)(grid)
            ax.plot(grid, density, color=COUNTRY_COLORS[country], linewidth=1.8)
            ax.fill_between(grid, density, color=COUNTRY_COLORS[country], alpha=0.25)
            ax.axvline(np.median(values), color=COUNTRY_COLORS[country], linestyle="--", linewidth=1.0)
        ax.set_title(scenario, fontweight="bold", fontsize=fs(11))
        ax.set_xlabel(f"CCRS ({PRIMARY_GCM}, capacity-weighted mean per draw)", fontsize=fs(9))
    axes[0].set_ylabel("Density (Monte Carlo draws)", fontsize=fs(10))

    handles = [mlines.Line2D([0], [0], color=COUNTRY_COLORS[c], linewidth=2.5, label=c) for c in countries]
    axes[-1].legend(handles=handles, fontsize=fs(9), loc="upper right", frameon=False)
    fig.tight_layout()
    out_path = save_figure(fig, OUT_DIR / "combined" / f"ccrs_rank_density_{PRIMARY_GCM}.png")
    logger.info("CCRS rank density (FIG 4 prototype a) saved to %s", out_path)
    return out_path


def plot_ccrs_rank_probability(
    countries: list[str] | None = None, draws: pd.DataFrame | None = None,
    pre: "mc._Precomputed | None" = None,
) -> pathlib.Path:
    """FIG 4 prototype (b) -- one panel per water_scenario, grouped bars:
    for each country, % of Monte Carlo draws in which it placed 1st/2nd/3rd
    by CCRS (1st = highest CCRS = most at-risk). Directly answers "does
    India outrank Portugal in (near-)every draw, or only on average" with a
    single bar height, rather than requiring the reader to compare two
    distributions' overlap by eye (prototype (a))."""
    countries = countries or COUNTRIES
    if draws is None:
        pre = pre or mc._Precomputed()
        draws = mc.run_country_scenario_draws(pre=pre)
    ranked = mc.rank_per_draw(draws)
    table = mc.rank_probability_table(ranked)

    scenarios = ("opt", "bau", "pes")
    ranks = sorted(ranked["rank"].unique())
    fig, axes = plt.subplots(1, len(scenarios), figsize=(4.5 * len(scenarios), 5.5), sharey=True)
    axes = np.atleast_1d(axes)
    width = 0.8 / len(countries)

    for ax, scenario in zip(axes, scenarios):
        sub = table[table["water_scenario"] == scenario]
        x = np.arange(len(ranks))
        for i, country in enumerate(countries):
            heights = [
                float(sub.loc[(sub["country"] == country) & (sub["rank"] == r), "probability"].iloc[0])
                if len(sub.loc[(sub["country"] == country) & (sub["rank"] == r)]) else 0.0
                for r in ranks
            ]
            ax.bar(x + (i - (len(countries) - 1) / 2) * width, heights, width=width,
                   color=COUNTRY_COLORS[country], label=country)
        ax.set_xticks(x)
        ax.set_xticklabels([f"rank {r}\n(1=highest risk)" if r == ranks[0] else f"rank {r}" for r in ranks],
                            fontsize=fs(8))
        ax.set_title(scenario, fontweight="bold", fontsize=fs(11))
        ax.set_ylim(0, 1.05)
    axes[0].set_ylabel("Share of Monte Carlo draws", fontsize=fs(10))
    axes[-1].legend(fontsize=fs(9), loc="upper right", frameon=False)
    fig.tight_layout()
    out_path = save_figure(fig, OUT_DIR / "combined" / f"ccrs_rank_probability_{PRIMARY_GCM}.png")
    logger.info("CCRS rank probability (FIG 4 prototype b) saved to %s", out_path)
    return out_path


# --------------------------------------------------------------------------
# C4 redesign -- per-plant distribution of each Hazard term's share, by
# country (Douglas's 2026-09-05 request). The original bar chart
# (``plot_hazard_term_contribution``, kept below UNCHANGED, not removed --
# Douglas has not authorized retiring it yet) compresses ~5,000-15,000
# plants per country into one capacity-weighted mean bar per term, which
# cannot show whether a term's apparent dominance (e.g. "water dominates in
# Brazil") holds across most plants or is pulled by a handful of large/
# atypical ones -- exactly the failure mode Douglas flagged.
#
# --------------------------------------------------------------------------
# Chart type per country: violin OR box+strip, chosen by sample size, not by
# country name
# --------------------------------------------------------------------------
# Real plant-scenario row counts (V6 computable base, 3 water_scenarios
# pooled per plant): Brazil 15,446, India 13,734, Portugal 1,314 -- roughly
# 5,150 / 4,580 / 438 UNIQUE plants once divided by the 3 pooled scenarios.
# A KDE-based violin implies a smooth, continuously-supported distribution --
# defensible at Brazil/India's volume, but at Portugal's ~438 unique plants
# a violin would visually claim smoothness the sample cannot support
# (Douglas's own concern, stated in the brief). The decision is thresholded
# on the ESTIMATED UNIQUE PLANT COUNT (``VIOLIN_MIN_PLANTS`` = 1,000; row
# count / number of distinct water_scenario values present), not the raw
# pooled row count -- thresholding on rows directly would have put Portugal
# (1,314 rows) on the wrong side of a naive 1,000-row cutoff despite having
# only a third that many actual plants. Not a hardcoded country name either,
# so if a future country/dataset changes size, the chart type follows the
# data. Below the threshold: a box (weighted or unweighted quantiles) plus a
# strip of the actual per-plant points -- exactly Douglas's "box/strip para
# Portugal" suggestion.
#
# --------------------------------------------------------------------------
# Weighting: BOTH unweighted and capacity-weighted views, stacked as rows
# --------------------------------------------------------------------------
# This is the same question that motivated the redesign in the first place
# (a few large plants can dominate the aggregate) -- so both views are shown
# rather than picking one. Row 1 (unweighted): every plant counts equally,
# answers "is this term dominant across most of the FLEET". Row 2
# (capacity-weighted): each plant's contribution to the shown density/box is
# weighted by ``capacity_mw`` (``scipy.stats.gaussian_kde``'s native
# ``weights`` argument for the violin; a weighted-quantile box for the
# small-N countries), answers "is this term dominant across most of the
# installed CAPACITY". For the box+strip countries, the weighted row also
# scales each strip point's marker size by its own capacity -- the same
# "where is the capacity actually concentrated" question, visible directly
# on the individual plants rather than only in the box's shape.
# --------------------------------------------------------------------------
VIOLIN_MIN_PLANTS = 1000
_HAZARD_TERM_COLS = (("water_share", "water"), ("heat_share", "heat"), ("drought_share", "drought"))


def _estimated_unique_plants(sub: pd.DataFrame) -> float:
    """Row count / number of distinct ``water_scenario`` values present --
    an estimate of unique plants behind a pooled-scenario frame (each plant
    contributes one row per scenario). Used only to pick violin vs. box+strip
    (``VIOLIN_MIN_PLANTS``), never as a displayed statistic."""
    n_scenarios = sub["water_scenario"].nunique() or 1
    return len(sub) / n_scenarios


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    order = np.argsort(values)
    values, weights = values[order], weights[order]
    cum = np.cumsum(weights) - 0.5 * weights
    cum /= weights.sum()
    return float(np.interp(q, cum, values))


def _box_stats(values: np.ndarray, weights: np.ndarray | None) -> dict:
    if weights is None:
        q1, med, q3 = np.percentile(values, [25, 50, 75])
    else:
        q1, med, q3 = (_weighted_quantile(values, weights, q) for q in (0.25, 0.5, 0.75))
    iqr = q3 - q1
    lo_fence, hi_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inside = values[(values >= lo_fence) & (values <= hi_fence)]
    whislo = float(inside.min()) if len(inside) else float(q1)
    whishi = float(inside.max()) if len(inside) else float(q3)
    return {"med": float(med), "q1": float(q1), "q3": float(q3),
            "whislo": whislo, "whishi": whishi, "fliers": []}


def _draw_violin(ax, x: float, values: np.ndarray, weights: np.ndarray | None, color: str, width: float = 0.7) -> None:
    from scipy import stats as sp_stats

    if len(values) < 2 or np.ptp(values) == 0:
        return
    kde = sp_stats.gaussian_kde(values, weights=weights)
    grid = np.linspace(values.min(), values.max(), 200)
    density = kde(grid)
    density = density / density.max() * (width / 2)
    ax.fill_betweenx(grid, x - density, x + density, color=color, alpha=0.6, linewidth=0.6, edgecolor="black")


def _draw_box_and_strip(ax, x: float, values: np.ndarray, weights: np.ndarray | None, color: str,
                         rng: np.random.Generator, width: float = 0.5) -> None:
    stats = _box_stats(values, weights)
    bp = ax.bxp([stats], positions=[x], widths=width, patch_artist=True, showfliers=False)
    for patch in bp["boxes"]:
        patch.set_facecolor(color)
        patch.set_alpha(0.5)
    jitter = rng.uniform(-width / 4, width / 4, size=len(values))
    if weights is not None:
        sizes = 4 + 46 * (weights / weights.max())
    else:
        sizes = 6
    ax.scatter(x + jitter, values, s=sizes, color=color, alpha=0.4, edgecolors="none", zorder=3)


def plot_hazard_term_contribution_distribution(
    countries: list[str] | None = None, per_plant: pd.DataFrame | None = None, gcm: str = PRIMARY_GCM,
) -> pathlib.Path:
    """Redesigned C4: 2 rows (unweighted / capacity-weighted) x one panel
    per country, each panel showing all 3 Hazard terms' per-plant share
    distribution side by side (violin above ``VIOLIN_MIN_ROWS`` plant-
    scenario rows, box+strip below it -- see the module comment above).
    Uses ``tables.hazard_term_contribution_per_plant`` -- the per-plant
    frame ``hazard_term_contribution_table``'s bar-chart numbers already
    aggregate away; that table/bar-chart pair is untouched by this addition."""
    from src.visualization import tables as vtables

    countries = countries or COUNTRIES
    per_plant = (per_plant if per_plant is not None
                 else vtables.hazard_term_contribution_per_plant(gcm=gcm, countries=countries))
    rng = np.random.default_rng(0)

    fig, axes = plt.subplots(2, len(countries), figsize=(4.6 * len(countries), 9), sharey=True)
    axes = np.atleast_2d(axes)

    for col, country in enumerate(countries):
        sub = per_plant[per_plant["country"] == country]
        use_violin = _estimated_unique_plants(sub) >= VIOLIN_MIN_PLANTS
        for row, weighted in enumerate((False, True)):
            ax = axes[row, col]
            weights_all = sub["capacity_mw"].to_numpy("float64") if weighted else None
            for i, (term_col, label) in enumerate(_HAZARD_TERM_COLS):
                values = sub[term_col].to_numpy("float64")
                color = HAZARD_TERM_COLORS[term_col]
                if use_violin:
                    _draw_violin(ax, i, values, weights_all, color)
                else:
                    _draw_box_and_strip(ax, i, values, weights_all, color, rng)
            ax.set_xticks(range(len(_HAZARD_TERM_COLS)))
            ax.set_xticklabels([label for _, label in _HAZARD_TERM_COLS], fontsize=fs(9))
            ax.set_ylim(-0.02, 1.02)
            style = "violin" if use_violin else "box+strip"
            weight_label = "capacity-weighted" if weighted else "unweighted"
            if row == 0:
                ax.set_title(f"{country} (n={len(sub):,} plant-scenario rows, {style})",
                              fontsize=fs(9.5), fontweight="bold")
            ax.set_xlabel(weight_label, fontsize=fs(8.5))
        axes[0, col].set_xlabel("")

    for row in range(2):
        axes[row, 0].set_ylabel("Share of Hazard", fontsize=fs(10))

    fig.tight_layout()
    out_path = save_figure(fig, OUT_DIR / "combined" / f"hazard_term_contribution_distribution_{gcm}.png")
    logger.info("Hazard term contribution distribution saved to %s", out_path)
    return out_path


# --------------------------------------------------------------------------
# C4 (reclassified secondary, 2026-09-05) -- relative contribution of
# water/heat/drought to Hazard, by country
#
# Demoted from primary to ``combined/secondary/`` -- this single
# capacity-weighted-mean bar per (country, water_scenario) is no longer a
# manuscript-figure candidate now that ``plot_hazard_term_contribution_
# distribution`` (the per-plant redesign, same task round) has demonstrated
# what it hides: the typical PLANT and the typical CAPACITY can disagree,
# and one aggregate bar cannot show that they do. Concretely, on the real
# data, Brazil's *unweighted* per-plant distribution has heat/drought
# dominating most individual plants (water_share concentrated near 0), but
# once weighted by capacity, water rises substantially and drought becomes
# even MORE extreme -- i.e. the single bar this function draws is shaped
# disproportionately by a handful of large-capacity plants, not
# representative of the median plant, and gives no visual indication that
# this is happening. Kept here, not deleted -- still a valid, correct
# capacity-weighted mean, useful as a quick single-number reference -- but
# the distribution figure is the one to cite for the actual water/heat/
# drought-dominance claim.
# --------------------------------------------------------------------------
def plot_hazard_term_contribution(
    countries: list[str] | None = None, contribution: pd.DataFrame | None = None, gcm: str = PRIMARY_GCM,
) -> pathlib.Path:
    """The structural argument for why Brazil/Portugal/India differ: the
    share of ``Hazard_{i,s}`` coming from water_sub, heat and drought,
    capacity-weighted, per country x water_scenario. Uses
    ``src/visualization/tables.py``'s ``hazard_term_contribution_table``.

    Secondary, not a manuscript-figure candidate -- see the module comment
    immediately above for why (superseded by ``plot_hazard_term_contribution_
    distribution``'s per-plant redesign, which surfaced a real
    unweighted-vs-capacity-weighted divergence this single bar cannot show)."""
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
    out_path = save_figure(fig, SECONDARY_DIR / f"hazard_term_contribution_{gcm}.png")
    logger.info("Hazard term contribution (secondary) saved to %s", out_path)
    return out_path
