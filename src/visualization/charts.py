"""
CCRS non-geospatial figures.

Categories: 5 (WaterRiskBand x HeatRiskBand combined-risk capacity bars,
rewritten from a heatmap -- B3), 6 (CCRS distribution by bucket, all three
scenarios -- B5), 7 (age_factor by bucket, secondary), 8 (capacity by risk
band, secondary), 9 (removed -- see below), 11 (Top-N CCRS breakdown by
bucket, rewritten -- B4), plus C4 (relative contribution of each Hazard
term by country).

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
new ``plot_hazard_term_contribution_distribution`` (per-plant box+strip,
unweighted vs. capacity-weighted) showed that Brazil's aggregate bar was
masking a real divergence between the typical plant and the typical
installed capacity -- a failure mode a single mean bar cannot surface.
Neither function is deleted; both are demoted, not removed.

--------------------------------------------------------------------------
2026-09-05 -- visual-review round, based on real-data PNGs
--------------------------------------------------------------------------
- FIG 4 fused into one figure (``plot_ccrs_rank_stability``) -- the
  rank-probability bar-chart prototype is discarded, the density-overlay
  prototype is kept and now carries the pairwise order-stability evidence
  as an on-panel annotation instead of a second chart (see the comment
  above ``plot_ccrs_rank_stability``).
- C4's per-plant distribution figure drops the violin chart type entirely
  -- box+strip for every country, with the STRIP (never the box's own
  quantiles) visually subsampled above ``STRIP_MAX_POINTS`` (see the
  comment above that constant).

--------------------------------------------------------------------------
2026-09-05 follow-up -- final removals + Figure 3 rebuilt from scratch
--------------------------------------------------------------------------
Two prior FIG 3 designs (a bucket-paneled single figure, then a
scenario-paneled family of 3 files per risk-band axis -- both reviewed
against real data in the prior round) are DELETED outright, not relocated:
``plot_capacity_vulnerability_by_bucket_water``/``_heat`` and their shared
``_capacity_vulnerability_scenario_figure`` renderer no longer exist, and
neither do their output PNG/PDF files. They are superseded by a
differently-scoped figure, ``plot_figure3_capacity_vulnerability_
profiles`` -- three panels (national risk-band capacity shares, CCRS
distribution by technology, age-vs-age_factor scatter), not a bucket x
risk-band cut. See that function's own module comment for the full design.

``plot_national_ccrs_with_ci`` is likewise DELETED (not moved again) --
Douglas's decision after reviewing the fused FIG 4: it no longer adds
anything the rank-stability figure doesn't already cover.

``plot_ccrs_rank_density``/``plot_ccrs_rank_probability`` (the FIG 4
prototypes, already fused/discarded in the previous round) had leftover
PNG/PDF files on disk from before that round's rename -- removed here as a
cleanup; no code changed for this part, since neither function has existed
since the fuse into ``plot_ccrs_rank_stability``.

``emdat_validation.plot_emdat_spatial_validation`` moves to
``combined/secondary/`` -- still a useful exploratory figure, just no
longer a manuscript-figure candidate (see that module's own comment).

--------------------------------------------------------------------------
2026-09-05 article-figure-numbering round -- Figure 3 composite discarded,
replaced by the article's actual Figure 2/6/7
--------------------------------------------------------------------------
``plot_figure3_capacity_vulnerability_profiles`` (the 2x2 composite from
the immediately prior round) was purely intermediate -- it no longer
exists. Its panels are split across the article's real figure numbering:

- Panel A (band exposure, water+heat sub-blocks) -> Figure 2
  (``plot_figure2_capacity_exposure_by_band``), unchanged data/design
  except no "historical baseline" column (never implemented -- no such
  dataset exists in this pipeline, confirmed again this round).
- Panels B + C -> Figure 6
  (``plot_figure6_technology_age_vulnerability_pes``). Panel A is box+strip
  per technology bucket (2026-09-06; was a KDE violin); Panel B is the
  age vs age_factor scatter with marker area proportional to capacity.
  Panel B has no scenario dimension to restrict in the first place
  (age_factor does not vary by water_scenario) -- by design.

``plot_ccrs_rank_stability`` (the fused, all-3-scenarios Monte Carlo
figure) moves to ``combined/secondary/`` -- the article's headline Monte
Carlo figure is now ``plot_figure7_montecarlo_stability_pes``, PES only, a
single density panel with the ranking stability as an inset annotation
(2026-09-06 fuse; was two panels).

``plot_hazard_term_contribution_distribution`` moves to
``combined/secondary/`` -- not cited in the current Results draft, kept as
a Supplementary candidate (logic/data untouched). Same treatment applied
in ``maps.py`` to ``plot_worst_case_risk_band_map`` and ``plot_ccrs_
scenario_delta_map``'s combined view.

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

from src.config import AQUEDUCT_SCENARIO_FOR_CMIP6, COUNTRIES, OUTPUT_MAPS
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
# 2026-09-05 article-figure-numbering round -- the 2x2 composite built in
# the prior round (``plot_figure3_capacity_vulnerability_profiles``) was
# purely intermediate and no longer exists as such. Its three panels are
# split into the article's actual Figure 2 (band exposure) and Figure 6
# (technology exposure + age scatter, both restricted to PES) below.
# --------------------------------------------------------------------------


def _bucket_identity_legend_handles() -> list[mlines.Line2D]:
    return [
        mlines.Line2D([0], [0], marker="o", color="w", markerfacecolor=color, markeredgecolor="none",
                      markersize=9, label=bucket.capitalize())
        for bucket, color in BUCKET_COLORS.items()
    ]


# --------------------------------------------------------------------------
# FIGURE 2 -- national capacity exposure by risk band, water + heat,
# opt/bau/pes only (article figure numbering round, 2026-09-05)
#
# Extracted from the prior composite's Panel A -- SAME data/aggregation as
# ``plot_capacity_by_risk_band`` (category 8, secondary): national
# (country x scenario), no bucket cut, ``vdata.load_water_band_shares``/
# ``load_heat_band_shares`` directly. This is a deliberate near-duplicate,
# not an oversight -- category 8 is the existing internal/methods
# reference figure, kept as-is in secondary/ (Douglas did not ask for it to
# be touched this round); Figure 2 is the same content promoted to the
# article's own primary output with the article's own numbering/filename.
# If this redundancy (two files, same numbers) is not wanted going forward,
# that is Douglas's call -- flagged, not resolved unilaterally here.
#
# No "historical baseline" column: no such dataset exists anywhere in this
# pipeline (WaterRiskBand/HeatRiskBand are computed only from the three
# future scenario projections; neither ARCHITECTURE.md nor INVENTORY.md
# name a separate current/present-day raster) -- confirmed again this
# round, per Douglas's explicit instruction to drop that column from scope
# rather than fabricate it.
#
# --------------------------------------------------------------------------
# 2026-09-06 fine-tuning round -- legend and x-axis
# --------------------------------------------------------------------------
# - TWO independent legends, one per panel: the water panel's 5 native
#   WaterRiskBand levels and the heat panel's 4 native HeatRiskBand levels
#   are different colour schemes on the same ordinal-severity ramp; a single
#   merged legend forced the reader to disambiguate "Water: High" from
#   "Heat: HIGH" by prefix. Each panel now carries only its own scheme,
#   placed directly under that panel.
# - X-axis grouped by country: three bars (opt/bau/pes, in that
#   optimistic->pessimistic order, NOT alphabetical) per country, with a gap
#   between country blocks and the country name as a bold label centred
#   under its block -- instead of nine flat "Brazil / opt", "Brazil / bau"
#   ... ticks with no visual hierarchy. The heat panel's ``heat_scenario``
#   (ssp126/370/585) is relabelled to the same opt/bau/pes axis via
#   ``AQUEDUCT_SCENARIO_FOR_CMIP6`` so both panels share one scenario axis.
# --------------------------------------------------------------------------
FIGURE2_SCENARIO_ORDER = ("opt", "bau", "pes")


def _band_swatch_handles(band_colors: dict) -> list[mlines.Line2D]:
    return [
        mlines.Line2D([0], [0], marker="s", color="w", markerfacecolor=color,
                      markeredgecolor="#888888", markeredgewidth=0.5, markersize=10, label=str(label))
        for label, color in band_colors.items()
    ]


def _draw_grouped_band_exposure_panel(ax, shares: pd.DataFrame, countries: list[str],
                                       band_order: tuple, band_colors: dict, title: str) -> None:
    """One stacked bar per (country, scenario). Bars are laid out in
    per-country blocks (opt/bau/pes, with a one-slot gap between blocks);
    the scenario is the per-bar x-tick, the country a bold label centred
    under the block. ``shares`` must carry a normalised ``scenario`` column
    (opt/bau/pes) plus ``country``/``band``/``capacity_share``."""
    block = len(FIGURE2_SCENARIO_ORDER) + 1
    positions, bar_labels, block_centers = [], [], []
    for ci, _country in enumerate(countries):
        start = ci * block
        for si, scenario in enumerate(FIGURE2_SCENARIO_ORDER):
            positions.append(start + si)
            bar_labels.append(scenario)
        block_centers.append(start + (len(FIGURE2_SCENARIO_ORDER) - 1) / 2)

    bottom = np.zeros(len(positions))
    for band in band_order:
        heights = []
        for country in countries:
            for scenario in FIGURE2_SCENARIO_ORDER:
                cell = shares[(shares["country"] == country) & (shares["scenario"] == scenario)
                              & (shares["band"] == band)]
                heights.append(float(cell["capacity_share"].iloc[0]) if len(cell) else 0.0)
        heights = np.asarray(heights)
        ax.bar(positions, heights, bottom=bottom, width=0.8,
               color=band_colors.get(band, "#cccccc"), label=str(band))
        bottom += heights

    ax.set_xticks(positions)
    ax.set_xticklabels(bar_labels, fontsize=fs(8))
    ax.set_xlim(-0.8, positions[-1] + 0.8)
    ax.set_ylim(0, 1.05)
    for center, country in zip(block_centers, countries):
        ax.text(center, -0.11, country, transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontweight="bold", fontsize=fs(10))
    ax.set_title(title, fontweight="bold", fontsize=fs(11))
    ax.set_ylabel("Share of national computable capacity", fontsize=fs(9.5))


def plot_figure2_capacity_exposure_by_band(
    countries: list[str] | None = None,
    water_shares: pd.DataFrame | None = None, heat_shares: pd.DataFrame | None = None,
    gcm: str = PRIMARY_GCM,
) -> pathlib.Path:
    countries = countries or COUNTRIES
    water_shares = water_shares if water_shares is not None else vdata.load_water_band_shares()
    heat_shares = heat_shares if heat_shares is not None else vdata.load_heat_band_shares()

    heat_to_scenario = {h: w for h, w in AQUEDUCT_SCENARIO_FOR_CMIP6.items()}
    water = water_shares[water_shares["country"].isin(countries)].copy()
    water["scenario"] = water["water_scenario"]
    heat = heat_shares[(heat_shares["gcm"] == gcm) & heat_shares["country"].isin(countries)].copy()
    heat["scenario"] = heat["heat_scenario"].map(heat_to_scenario)
    present = [c for c in countries if c in set(water["country"]) | set(heat["country"])]

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    _draw_grouped_band_exposure_panel(
        axes[0], water, present, WATER_RISK_BANDS + ("NO_BAND",),
        {**WATER_BAND_COLORS, "NO_BAND": "#e0e0e0"}, "a -- WaterRiskBand (fixed WRI Aqueduct 4.0 cuts)",
    )
    _draw_grouped_band_exposure_panel(
        axes[1], heat, present, HEAT_RISK_BANDS + ("NO_BAND",),
        {**HEAT_BAND_COLORS, "NO_BAND": "#e0e0e0"}, f"b -- HeatRiskBand ({gcm}, sample-relative cuts)",
    )
    axes[0].legend(handles=_band_swatch_handles({**WATER_BAND_COLORS, "NO_BAND": "#e0e0e0"}),
                    loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, fontsize=fs(7.5),
                    frameon=False, title="WaterRiskBand", title_fontsize=fs(8.5))
    axes[1].legend(handles=_band_swatch_handles({**HEAT_BAND_COLORS, "NO_BAND": "#e0e0e0"}),
                    loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, fontsize=fs(7.5),
                    frameon=False, title="HeatRiskBand", title_fontsize=fs(8.5))

    fig.tight_layout()
    out_path = save_figure(fig, OUT_DIR / "combined" / "figure2_capacity_exposure_by_band.png")
    logger.info("Figure 2 saved to %s", out_path)
    return out_path


# --------------------------------------------------------------------------
# FIGURE 6 -- CCRS by technology (box+strip) + age vs age_factor scatter,
# PES only (article figure numbering round, 2026-09-05; panels reworked
# 2026-09-06)
#
# Extracted from the prior composite's Panels B/C, both restricted to PES.
#
# Panel A: box + strip per technology bucket, pooled across countries -- the
# SAME idiom as ``plot_hazard_term_contribution_distribution`` (box
# quantiles from the full per-plant sample; the strip a fixed reproducible
# subsample above ``STRIP_MAX_POINTS`` so it stays legible at any volume;
# the true n and, when subsampled, the shown count reported per bucket).
# The 2026-09-06 round replaced the KDE violin used here before -- Douglas
# prefers box+strip, and it removes the "implies a smooth continuous
# distribution the sample may not support" concern the violin carried.
#
# Panel B: kept as a scatter (NOT collapsed to an aggregate bar). Marker
# AREA is proportional to plant ``capacity_mw`` (sqrt scale, the project's
# bubble convention) so the installed capacity riding the ageing curve is
# visible, not just the plant count; alpha is low for the dense
# common-age/common-bucket overplotting. A small text box reports each
# country's capacity-weighted mean operational age. Panel B has NO scenario
# dependence to restrict in the first place: ``age_factor`` is a per-plant,
# scenario-invariant quantity (it does not vary by water_scenario -- only
# Hazard and EventMultiplier do), so "under PES" does not change what
# Panel B plots. This is correct-by-design, not a pending fix.
# --------------------------------------------------------------------------
def _draw_technology_exposure_panel(ax, final: pd.DataFrame, gcm: str, scenario: str = "pes") -> None:
    col = f"ccrs_{gcm}"
    sub = final[(final["water_scenario"] == scenario) & final["computable"]]
    rng = np.random.default_rng(0)
    labels = []
    for i, bucket in enumerate(BUCKETS):
        values = sub.loc[sub["bucket"] == bucket, col].dropna().to_numpy()
        if len(values) == 0:
            labels.append(f"{bucket.capitalize()}\n(n=0)")
            continue
        n_shown = _draw_box_and_strip(ax, i, values, None, BUCKET_COLORS[bucket], rng)
        note = f"n={len(values):,}"
        if n_shown < len(values):
            note += f"\n({n_shown:,} shown)"
        labels.append(f"{bucket.capitalize()}\n{note}")
    ax.set_xticks(range(len(BUCKETS)))
    ax.set_xticklabels(labels, fontsize=fs(8))
    ax.set_ylabel(f"CCRS ({gcm}, {scenario.upper()})", fontsize=fs(9.5))
    ax.set_title(f"a -- Technology exposure ({scenario.upper()})", fontweight="bold", fontsize=fs(11))


def _draw_age_amplification_scatter(ax, age_factors: pd.DataFrame) -> None:
    """Per-plant operational age vs age_factor, coloured by bucket, marker
    area proportional to ``capacity_mw`` (sqrt scale). No scenario filter --
    ``age_factor`` does not vary by water_scenario (see the module comment
    above); this is by design, not an omission."""
    known = age_factors[age_factors["age"].notna() & age_factors["capacity_mw"].notna()]
    cap_max = float(known["capacity_mw"].clip(lower=0).max()) if len(known) else 0.0
    for bucket in BUCKETS:
        s = known[known["bucket"] == bucket]
        if len(s) == 0:
            continue
        if cap_max > 0:
            sizes = 5 + 55 * np.sqrt(s["capacity_mw"].clip(lower=0) / cap_max)
        else:
            sizes = 12
        ax.scatter(s["age"], s["age_factor"], s=sizes, alpha=0.22,
                   color=BUCKET_COLORS[bucket], edgecolors="none")
    ax.axhline(1.0, color="black", linewidth=0.6, linestyle=":")
    ax.set_xlabel("Operational age (years) -- marker area proportional to plant capacity", fontsize=fs(9))
    ax.set_ylabel("age_factor ( >= 1 )", fontsize=fs(9.5))
    ax.set_title("b -- Age-driven risk amplification", fontweight="bold", fontsize=fs(11))

    wm = []
    for country in COUNTRIES:
        c = known[known["country"] == country]
        w = c["capacity_mw"].clip(lower=0)
        if len(c) and w.sum() > 0:
            wm.append(f"{country} {float(np.average(c['age'], weights=w)):.0f} yr")
    if wm:
        ax.text(0.03, 0.97, "Capacity-weighted mean age\n" + "\n".join(wm),
                transform=ax.transAxes, ha="left", va="top", fontsize=fs(7.5),
                bbox=dict(facecolor="white", alpha=0.8, edgecolor="#999999", linewidth=0.5,
                          boxstyle="round,pad=0.3"))


def plot_figure6_technology_age_vulnerability_pes(
    countries: list[str] | None = None,
    final: pd.DataFrame | None = None, age_factors: pd.DataFrame | None = None,
    gcm: str = PRIMARY_GCM,
) -> pathlib.Path:
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    age_factors = age_factors if age_factors is not None else vdata.load_age_factors()
    final = final[final["country"].isin(countries)]
    age_factors = age_factors[age_factors["country"].isin(countries)]

    fig, axes = plt.subplots(1, 2, figsize=(14, 6.5))
    _draw_technology_exposure_panel(axes[0], final, gcm, scenario="pes")
    _draw_age_amplification_scatter(axes[1], age_factors)
    handles = _bucket_identity_legend_handles()
    axes[1].legend(handles=handles, fontsize=fs(8), loc="upper left", bbox_to_anchor=(1.02, 1.0),
                    ncol=1, borderaxespad=0, title="Technology", title_fontsize=fs(8.5))

    fig.tight_layout()
    out_path = save_figure(fig, OUT_DIR / "combined" / f"figure6_technology_age_vulnerability_pes_{gcm}.png")
    logger.info("Figure 6 saved to %s", out_path)
    return out_path


# --------------------------------------------------------------------------
# FIG 4 -- ordinal rank stability under Monte Carlo uncertainty
# (Douglas's 2026-09-05 request: the point+CI figure above does not show
# whether a country's apparent ranking advantage (e.g. India > Portugal)
# holds per-draw, or only on average)
#
# --------------------------------------------------------------------------
# 2026-09-05 follow-up review -- fused into ONE figure, prototype (b) dropped
# --------------------------------------------------------------------------
# Both prototypes were generated and reviewed against real data.
# ``plot_ccrs_rank_probability`` (the grouped 0-100% rank bars) was judged
# not useful -- discarded, not kept as a secondary variant, since it added a
# second figure that communicated nothing the density overlay didn't already
# show more directly. ``plot_ccrs_rank_density`` (the density overlay) was
# judged to have real potential but suffered legend/text overlapping the
# density curves. Fix: the two are fused into ONE figure
# (``plot_ccrs_rank_stability``) -- the density overlay is kept as the
# visual evidence of separation, and the exact stability evidence the
# discarded bar chart was trying to show ("India > Portugal in X% of
# draws") is now a small text annotation printed directly on each density
# panel (``monte_carlo.pairwise_order_stability``), rather than a second bar
# chart repeating the same 0-100% axis. This keeps the redesign's original
# goal -- show whether a ranking holds per-draw, not just on average --
# without the panel that added no new information.
#
# Overlap fix: the per-panel annotation is placed at the top-left in axes
# fraction coordinates with an opaque-ish white background box (so it never
# visually merges with a density curve underneath it, wherever the curves
# happen to peak), and the country-color legend moved OUT of the axes
# (``fig.legend`` below the panels, matching the "legend never overlaps the
# plot" convention already used by the map figures via
# ``_common.legend_below_artists``) instead of ``ax.legend(loc="upper
# right")``, which is exactly where it used to collide with the rightmost
# density curve.
#
# Density overlay, not a literal offset ridge plot: with exactly 3
# countries, an offset/joyplot-style stack (built for telling apart many
# overlapping categories) adds a vertical-offset dimension that carries no
# information here and makes reading the actual overlap/separation between
# 3 curves harder, not easier -- a shared-axis overlay with alpha-fill shows
# the same separation/overlap directly.
#
# --------------------------------------------------------------------------
# 2026-09-05 follow-up review -- caption text, N unchanged
# --------------------------------------------------------------------------
# N=1,000 iterations is a closed decision (ARCHITECTURE.md Sec. 8) and is
# NOT reopened here -- ``FIGURE7_CAPTION`` below is text only. It lives in
# the manuscript's own figure-caption text, not printed on the figure
# itself: this project's convention is no figure prints its own
# multi-sentence caption. An earlier version of this caption named "a"/"b"
# panels; the 2026-09-06 fuse removed that split, and the caption below now
# describes the single density panel with its ranking inset. The fused
# 3-scenario ``plot_ccrs_rank_stability`` is unrelated to this caption and
# has none of its own (it moved to secondary/, a Supplementary candidate).
#
# 2026-09-05 follow-up: the caption previously claimed the distributions
# "capture structural uncertainties between global circulation models
# (GFDL-ESM4 and MIROC6)". That was factually wrong for this figure: both
# ``plot_ccrs_rank_stability`` and ``plot_figure7_montecarlo_stability_pes``
# call ``monte_carlo.run_country_scenario_draws`` with its default ``model``
# (``risk_bands.PRIMARY_GCM`` = GFDL-ESM4 ONLY) -- MIROC6 is never drawn
# from here; only the three approved parameter groups (thermal water/heat/
# drought ratio, age_factor retention rates, EventMultiplier k) are
# perturbed, all within GFDL-ESM4. The MIROC6-vs-GFDL-ESM4 comparison lived
# in the now-deleted ``plot_national_ccrs_with_ci``'s secondary-GCM marker,
# not here. Douglas's decision: drop the GCM-comparison claim, state the
# figure for what it is -- parametric uncertainty under GFDL-ESM4 (the
# primary model) on SSP5-8.5.
#
# 2026-09-06: Figure 7 fused to ONE panel (see the comment above the
# function) -- the caption no longer has an "a"/"b" split; the ranking
# evidence is now an inset annotation on the single density panel.
# --------------------------------------------------------------------------
FIGURE7_CAPTION = (
    "Probability density functions of the aggregate Climate Change Risk Score (CCRS) for "
    "Brazil, Portugal, and India generated through 1,000 Monte Carlo iterations. The "
    "distributions capture parametric uncertainty in the framework's bounding assumptions "
    "(the thermal water/heat/drought weighting ratio, the age-factor retention rates, and the "
    "EventMultiplier constant) under GFDL-ESM4, the framework's primary climate model, on the "
    "high-emission SSP5-8.5 trajectory. The inset reports the ordinal risk ranking held across "
    "the Monte Carlo draws. Despite stochastic parameter variation and the expected widening of "
    "probability density under extreme warming, the relative infrastructural risk divergence -- "
    "wherein India's compounded multi-hazard exposure systematically outpaces Portugal's "
    "localized thermal risk -- remains structurally robust."
)


def _pairwise_dominant_direction(pairwise: pd.DataFrame, scenario: str) -> list[str]:
    """One line per UNORDERED country pair (not two, which would just be
    complementary percentages of each other) -- the direction with
    probability >= 50% is the one printed, e.g. "India > Portugal: 100%"."""
    sub = pairwise[pairwise["water_scenario"] == scenario]
    seen: set[frozenset] = set()
    lines = []
    for row in sub.itertuples(index=False):
        pair = frozenset((row.country_a, row.country_b))
        if pair in seen:
            continue
        seen.add(pair)
        reverse = sub[(sub["country_a"] == row.country_b) & (sub["country_b"] == row.country_a)]
        pct_b_greater_a = float(reverse["pct_a_greater_b"].iloc[0]) if len(reverse) else 1.0 - row.pct_a_greater_b
        if row.pct_a_greater_b >= pct_b_greater_a:
            lines.append(f"{row.country_a} > {row.country_b}: {row.pct_a_greater_b:.0%}")
        else:
            lines.append(f"{row.country_b} > {row.country_a}: {pct_b_greater_a:.0%}")
    return lines


def plot_ccrs_rank_stability(
    countries: list[str] | None = None, draws: pd.DataFrame | None = None,
    pre: "mc._Precomputed | None" = None,
) -> pathlib.Path:
    """FIG 4 (fused), all 3 scenarios -- one panel per water_scenario,
    overlaid CCRS density curves (one per country, ``COUNTRY_COLORS``) with
    a dashed vertical line at each country's median, PLUS a small text
    annotation giving the exact % of Monte Carlo draws in which each
    pairwise ordering holds (``monte_carlo.pairwise_order_stability``) --
    see the module comment above for why this replaces the two separate
    prototypes (density + rank-probability bars) generated in the first
    redesign round.

    2026-09-05 article-figure-numbering round: this 3-scenario version is
    no longer the article's headline Monte Carlo figure -- that is now
    ``plot_figure7_montecarlo_stability_pes`` (PES only, 2 panels: density
    + a genuine separate ranking-stability panel). This function is KEPT,
    unchanged in logic, saved to ``combined/secondary/`` as a Supplementary
    candidate ("all 3 scenarios at once" reference), not deleted."""
    from scipy import stats as sp_stats

    countries = countries or COUNTRIES
    if draws is None:
        pre = pre or mc._Precomputed()
        draws = mc.run_country_scenario_draws(pre=pre)
    pairwise = mc.pairwise_order_stability(draws)

    scenarios = ("opt", "bau", "pes")
    fig, axes = plt.subplots(1, len(scenarios), figsize=(5.8 * len(scenarios), 5.8), sharey=True)
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

        lines = _pairwise_dominant_direction(pairwise, scenario)
        if lines:
            ax.text(0.03, 0.97, "\n".join(lines), transform=ax.transAxes, ha="left", va="top",
                    fontsize=fs(7.5),
                    bbox=dict(facecolor="white", alpha=0.85, edgecolor="#999999", linewidth=0.5,
                              boxstyle="round,pad=0.3"))
    axes[0].set_ylabel("Density (Monte Carlo draws)", fontsize=fs(10))

    handles = [mlines.Line2D([0], [0], color=COUNTRY_COLORS[c], linewidth=2.5, label=c) for c in countries]
    fig.legend(handles=handles, fontsize=fs(9), loc="lower center", ncol=len(countries), frameon=False,
               bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    out_path = save_figure(fig, SECONDARY_DIR / f"ccrs_rank_stability_{PRIMARY_GCM}.png")
    logger.info("CCRS rank stability, all scenarios (secondary) saved to %s", out_path)
    return out_path


# --------------------------------------------------------------------------
# FIGURE 7 -- Monte Carlo CCRS density + ordinal ranking stability, PES only
# (article figure numbering round, 2026-09-05; fused to one panel 2026-09-06)
#
# ONE panel: overlaid CCRS density curves for the three countries under PES,
# with the ranking-stability evidence as a small inset text box ("India >
# Brazil > Portugal in 100% of draws"), not a second bar panel. This matches
# the decision already taken for ``plot_ccrs_rank_stability`` (the fused
# 3-scenario Supplementary figure above): the rank-probability bar chart
# repeats, on a 0-100% axis, what the density separation and one line of
# text already say. N=1,000 Monte Carlo iterations is unchanged
# (ARCHITECTURE.md Sec. 8, not reopened) -- same ``run_country_scenario_
# draws`` output, sliced to PES.
#
# X-axis (2026-09-06): Brazil (~0.33) and Portugal (~0.30) sit close
# together far below India (~0.85); on a plain linear axis autoscaled to
# [min, max] they overlap in the leftmost sliver. ``xscale="log"`` gives the
# low end proportionally more width and separates the two -- kept as the
# default. ``xscale="linear"`` (autozoomed to the real data range, no fixed
# 0.2-1.0) is available for comparison; the density SHAPE is preserved
# either way (this is not the point+CI form, which was already rejected).
# --------------------------------------------------------------------------
def _figure7_ranking_lines(ranked: pd.DataFrame, scenario: str = "pes") -> list[str]:
    """Full best-to-worst orderings and their share of Monte Carlo draws
    (``monte_carlo.full_ranking_distribution``), most frequent first, for
    one scenario -- e.g. ``["India > Brazil > Portugal: 100%"]``."""
    dist = mc.full_ranking_distribution(ranked)
    dist = dist[dist["water_scenario"] == scenario].sort_values("probability", ascending=False)
    return [f"{row.ordering}: {row.probability:.0%}" for row in dist.itertuples(index=False)]


def plot_figure7_montecarlo_stability_pes(
    countries: list[str] | None = None, draws: pd.DataFrame | None = None,
    pre: "mc._Precomputed | None" = None, xscale: str = "log",
) -> pathlib.Path:
    from scipy import stats as sp_stats

    countries = countries or COUNTRIES
    if draws is None:
        pre = pre or mc._Precomputed()
        draws = mc.run_country_scenario_draws(pre=pre)
    pes_draws = draws[draws["water_scenario"] == "pes"]
    ranked = mc.rank_per_draw(pes_draws)

    fig, ax = plt.subplots(figsize=(9.5, 5.8))
    values_by_country = {}
    for country in countries:
        v = pes_draws.loc[pes_draws["country"] == country, "ccrs"].dropna().to_numpy()
        if len(v) >= 2 and np.ptp(v) > 0:
            values_by_country[country] = v

    lo = min((v.min() for v in values_by_country.values()), default=0.0)
    hi = max((v.max() for v in values_by_country.values()), default=1.0)
    if xscale == "log" and lo > 0 and hi > lo:
        grid = np.geomspace(lo, hi, 500)
        ax.set_xscale("log")
    else:
        margin = 0.02 * (hi - lo) if hi > lo else 0.05
        grid = np.linspace(lo, hi, 500)
        ax.set_xlim(lo - margin, hi + margin)

    for country, v in values_by_country.items():
        density = sp_stats.gaussian_kde(v)(grid)
        ax.plot(grid, density, color=COUNTRY_COLORS[country], linewidth=1.8)
        ax.fill_between(grid, density, color=COUNTRY_COLORS[country], alpha=0.25)
        ax.axvline(float(np.median(v)), color=COUNTRY_COLORS[country], linestyle="--", linewidth=1.0)

    lines = _figure7_ranking_lines(ranked, "pes")
    if lines:
        ax.text(0.97, 0.97, "Ordinal ranking (share of draws)\n" + "\n".join(lines),
                transform=ax.transAxes, ha="right", va="top", fontsize=fs(8),
                bbox=dict(facecolor="white", alpha=0.9, edgecolor="#999999", linewidth=0.5,
                          boxstyle="round,pad=0.35"))

    ax.set_title("CCRS density and ranking stability (SSP5-8.5/PES)", fontweight="bold", fontsize=fs(11))
    ax.set_xlabel(f"CCRS ({PRIMARY_GCM}, capacity-weighted mean per draw)", fontsize=fs(9.5))
    ax.set_ylabel("Density (Monte Carlo draws)", fontsize=fs(10))
    # Legend below the panel, not inside it -- on a log x-axis the Brazil/
    # Portugal peaks sit hard against the left edge, exactly where an
    # in-axes upper-left legend would land (same convention as
    # ``plot_ccrs_rank_stability``).
    handles = [mlines.Line2D([0], [0], color=COUNTRY_COLORS[c], linewidth=2.5, label=c)
               for c in values_by_country]
    fig.legend(handles=handles, fontsize=fs(9), loc="lower center", ncol=len(handles),
               frameon=False, bbox_to_anchor=(0.5, -0.02))

    fig.tight_layout(rect=(0, 0.05, 1, 1))
    out_path = save_figure(fig, OUT_DIR / "combined" / f"figure7_montecarlo_stability_pes_{PRIMARY_GCM}.png")
    logger.info("Figure 7 saved to %s", out_path)
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
# 2026-09-05 review -- box+strip for EVERY country, violin dropped entirely
# --------------------------------------------------------------------------
# Douglas found box+strip (previously used only for Portugal, ~438 unique
# plants) more useful to read than violin (previously used for Brazil/India,
# ~5,150 / ~4,580 unique plants) and asked whether box+strip is viable at
# that larger volume too, rather than keeping two different chart types.
# Investigated: a full, unthinned strip at Brazil/India's volume (~15,000
# points per panel-row across 3 terms) would be a solid smear -- individual
# points stop being distinguishable well before that count, and overplotting
# would misrepresent density (a region with 50 overlapping points looks the
# same as one with 5,000). The chosen fix is NOT a different chart type --
# box+strip is kept for every country -- but the STRIP is visually
# subsampled above ``STRIP_MAX_POINTS`` points (a fixed, reproducible random
# sample, seeded per call): this keeps the strip legible (individual points
# stay visible, small and semi-transparent) at any volume without a second
# chart type to reason about per country. Critically, the BOX statistics
# (median/quartiles/whiskers, weighted or not) are always computed from the
# FULL per-plant data, never from the visual subsample -- subsampling only
# ever affects which points are drawn as a strip, never the reported
# quantiles. The panel title reports the true n and, when subsampled, how
# many points are actually plotted, so the reduction is never silent.
# --------------------------------------------------------------------------
# Weighting: BOTH unweighted and capacity-weighted views, stacked as rows
# --------------------------------------------------------------------------
# This is the same question that motivated the redesign in the first place
# (a few large plants can dominate the aggregate) -- so both views are shown
# rather than picking one. Row 1 (unweighted): every plant counts equally,
# answers "is this term dominant across most of the FLEET". Row 2
# (capacity-weighted): each plant's contribution to the box is weighted by
# ``capacity_mw`` (a weighted-quantile box), answers "is this term dominant
# across most of the installed CAPACITY". The weighted row also scales each
# strip point's marker size by its own capacity -- the same "where is the
# capacity actually concentrated" question, visible directly on the
# individual plants rather than only in the box's shape.
# --------------------------------------------------------------------------
STRIP_MAX_POINTS = 600
_HAZARD_TERM_COLS = (("water_share", "water"), ("heat_share", "heat"), ("drought_share", "drought"))


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


def _draw_box_and_strip(ax, x: float, values: np.ndarray, weights: np.ndarray | None, color: str,
                         rng: np.random.Generator, width: float = 0.5,
                         max_strip_points: int = STRIP_MAX_POINTS) -> int:
    """Draws the box from the FULL ``values``/``weights`` (never from the
    subsample below), then a strip of at most ``max_strip_points`` points --
    a fixed random sample when there are more than that many, so the strip
    stays legible at any plant count without changing what the box itself
    reports. Returns the number of points actually plotted (== ``len(values)``
    when no subsampling happened), for the caller to report on the panel."""
    stats = _box_stats(values, weights)
    bp = ax.bxp([stats], positions=[x], widths=width, patch_artist=True, showfliers=False)
    for patch in bp["boxes"]:
        patch.set_facecolor(color)
        patch.set_alpha(0.5)

    n = len(values)
    if n > max_strip_points:
        idx = rng.choice(n, size=max_strip_points, replace=False)
    else:
        idx = np.arange(n)
    strip_values = values[idx]
    jitter = rng.uniform(-width / 4, width / 4, size=len(idx))
    if weights is not None:
        sizes = 4 + 46 * (weights[idx] / weights.max())
        alpha = 0.5
    else:
        sizes = 6
        alpha = 0.35 if n <= max_strip_points else 0.25
    ax.scatter(x + jitter, strip_values, s=sizes, color=color, alpha=alpha, edgecolors="none", zorder=3)
    return len(idx)


def plot_hazard_term_contribution_distribution(
    countries: list[str] | None = None, per_plant: pd.DataFrame | None = None, gcm: str = PRIMARY_GCM,
) -> pathlib.Path:
    """Redesigned C4: 2 rows (unweighted / capacity-weighted) x one panel
    per country, each panel showing all 3 Hazard terms' per-plant share
    distribution side by side -- box+strip for every country (see the
    module comment above for why violin was dropped and how the strip is
    subsampled at high plant counts). Uses
    ``tables.hazard_term_contribution_per_plant`` -- the per-plant frame
    ``hazard_term_contribution_table``'s bar-chart numbers already
    aggregate away; that table/bar-chart pair is untouched by this addition.

    2026-09-05 article-figure-numbering round: not cited in the current
    Results draft -- moved to ``combined/secondary/`` (Supplementary
    candidate, not deleted; logic/data untouched)."""
    from src.visualization import tables as vtables

    countries = countries or COUNTRIES
    per_plant = (per_plant if per_plant is not None
                 else vtables.hazard_term_contribution_per_plant(gcm=gcm, countries=countries))
    rng = np.random.default_rng(0)

    fig, axes = plt.subplots(2, len(countries), figsize=(4.6 * len(countries), 9), sharey=True)
    axes = np.atleast_2d(axes)

    for col, country in enumerate(countries):
        sub = per_plant[per_plant["country"] == country]
        for row, weighted in enumerate((False, True)):
            ax = axes[row, col]
            weights_all = sub["capacity_mw"].to_numpy("float64") if weighted else None
            n_plotted = 0
            for i, (term_col, label) in enumerate(_HAZARD_TERM_COLS):
                values = sub[term_col].to_numpy("float64")
                color = HAZARD_TERM_COLORS[term_col]
                n_plotted = _draw_box_and_strip(ax, i, values, weights_all, color, rng)
            ax.set_xticks(range(len(_HAZARD_TERM_COLS)))
            ax.set_xticklabels([label for _, label in _HAZARD_TERM_COLS], fontsize=fs(9))
            ax.set_ylim(-0.02, 1.02)
            weight_label = "capacity-weighted" if weighted else "unweighted"
            if row == 0:
                # Two lines, not one -- a single long line ("Brazil (n=15,446
                # plant-scenario rows, 600 pts/term shown)") was found (real-
                # data sample) to overflow into the neighbouring panel's
                # title at this font scale, since 3 panels share one row.
                # Splitting the country name (bold) from the row-count/
                # subsample detail (smaller, not bold) keeps each line's own
                # pixel width well inside one panel.
                subsample_note = f", {n_plotted:,} pts/term shown" if n_plotted < len(sub) else ""
                ax.set_title(f"{country}\n(n={len(sub):,} rows{subsample_note})",
                              fontsize=fs(9.5), fontweight="bold")
            ax.set_xlabel(weight_label, fontsize=fs(8.5))
        axes[0, col].set_xlabel("")

    for row in range(2):
        axes[row, 0].set_ylabel("Share of Hazard", fontsize=fs(10))

    fig.tight_layout()
    out_path = save_figure(fig, SECONDARY_DIR / f"hazard_term_contribution_distribution_{gcm}.png")
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
