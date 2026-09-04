"""
CCRS geospatial maps -- categories 1 (overview), 2 (scenario delta),
3 (WaterRiskBand), 4 (HeatRiskBand), 10 (computable-base completeness).

Every category is exposed as one function with a ``combined: bool`` switch
(default ``False``, per-country -- one figure per country, dict keyed by
country) rather than a separate pair of functions per category (the old
repo's ``plot_X_map`` / ``plot_X_map_per_country`` split) -- same output
shapes, less duplicated plumbing. ``combined=True`` produces one figure for
every requested country.

Reused directly from the old repo's ``maps.py`` (see ``_common.py``'s
docstring for the full list): boundary/disputed-territory drawing, dynamic
per-country figsize, the sqrt-of-capacity marker-size convention, dpi=200
PNG+PDF saving, footer/legend positioning. The panel-drawing logic itself is
new -- adapted to the CCRS schema (``plant_uid``, ``ccrs_{gcm}``, 4 buckets,
``risk_bands.py``'s two independent bands) rather than the old SCI schema.

--------------------------------------------------------------------------
Douglas's 2026-09-04 review round -- what changed
--------------------------------------------------------------------------
- No figure prints a title (``fig.suptitle``) any more -- the equivalent
  context is folded into the figure footer (``_common.figure_caption_footer``).
  Per-panel labels ("Brazil (n=1,234)") stay, but bold and reading
  ``Power Plants=N`` instead of ``n=N`` (``_common.panel_title``).
- Categories 1, 3, 10 (overview / WaterRiskBand / computable-base) are now
  generated for all three water scenarios in one figure -- scenario is a
  panel dimension, not a separate file per scenario (B2). ``combined=True``
  arranges countries (rows) x scenarios (columns) in one grid; ``combined=
  False`` gives one figure per country with its three scenarios side by
  side.
- Category 4 (HeatRiskBand) is generated once per heat scenario, GFDL-ESM4
  only, three country panels side by side -- the old two-GCM-row layout (one
  figure, ssp370 only) is gone; see ``src/visualization/tables.py`` for the
  GFDL/MIROC6 comparison this replaces (B1).
"""

from __future__ import annotations

import logging
import pathlib

import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import COUNTRIES, OUTPUT_MAPS
from src.index.ccrs_calculator import WATER_SCENARIOS, WATER_TO_HEAT
from src.index.risk_bands import PRIMARY_GCM
from src.visualization import data as vdata
from src.visualization._common import (
    BUCKET_COLORS,
    DIVERGING_CMAP,
    HEAT_BAND_COLORS,
    NOT_COMPUTABLE_COLOR,
    NOT_COMPUTABLE_MARKER,
    WATER_BAND_COLORS,
    aspect_ratio_width,
    bucket_legend_handles,
    country_bbox_aspect,
    draw_country_boundary,
    figure_caption_footer,
    figure_caption_footer_single,
    fs,
    legend_below_artists,
    marker_sizes,
    not_computable_legend_handle,
    panel_title,
    save_figure,
)

logger = logging.getLogger(__name__)


def _scenario_rows(final: pd.DataFrame, water_scenario: str) -> pd.DataFrame:
    return final[final["water_scenario"] == water_scenario]


def _country_frame(final: pd.DataFrame, country: str, water_scenario: str) -> pd.DataFrame:
    return _scenario_rows(final, water_scenario).loc[lambda d: d["country"] == country]


# --------------------------------------------------------------------------
# Figsize for a (country, scenario) panel grid -- see module docstring:
# a fixed column width per scenario, row height driven by the country's real
# bbox aspect (only the country -- not the scenario -- affects aspect).
# --------------------------------------------------------------------------
def _country_scenario_figsize(country: str, n_scenarios: int, base_height: float = 7.0) -> tuple[float, float]:
    width_each = aspect_ratio_width(country, base_height)
    return (width_each * n_scenarios, base_height)


def _combined_grid_figsize(countries: list[str], n_scenarios: int,
                            col_width: float = 5.0) -> tuple[tuple[float, float], list[float]]:
    heights = [max(3.0, min(col_width / country_bbox_aspect(c), 10.0)) for c in countries]
    return (col_width * n_scenarios, sum(heights)), heights


# --------------------------------------------------------------------------
# Shared bubble-map panel -- categories 1 and 10
# --------------------------------------------------------------------------
def _draw_bubble_panel(ax, country: str, frame_country: pd.DataFrame, ring_col: str | None,
                        ring_quantile: float = 0.8, alpha: float = 0.6) -> dict:
    """Bucket-colored bubble map, size ~ capacity. Plants outside the V6
    computable base (no ``commissioning_year``) are NEVER omitted -- drawn
    as a distinct grey ``x`` marker, same convention for every category that
    uses this panel (item 1's overview ring and item 10's completeness map
    both go through here). Does not set the panel title -- the caller does,
    via ``_common.panel_title``, since the label text differs by category
    and (post B2) by scenario."""
    draw_country_boundary(ax, country)
    computable = frame_country[frame_country["computable"]]
    not_computable = frame_country[~frame_country["computable"]]

    if ring_col and len(computable):
        cut = computable[ring_col].quantile(ring_quantile)
        high = (computable[ring_col] >= cut).to_numpy()
    else:
        high = np.zeros(len(computable), dtype=bool)

    sizes = marker_sizes(computable["capacity_mw"])
    colors = computable["bucket"].map(BUCKET_COLORS).fillna("#000000")
    edgecolors = np.where(high, "#d62728", "none")
    linewidths = np.where(high, 1.3, 0.0)
    ax.scatter(computable["lon"], computable["lat"], s=sizes, c=colors,
               edgecolors=edgecolors, linewidths=linewidths, alpha=alpha, zorder=3)

    if len(not_computable):
        ax.scatter(not_computable["lon"], not_computable["lat"], s=16,
                   c=NOT_COMPUTABLE_COLOR, marker=NOT_COMPUTABLE_MARKER, linewidths=1.2, zorder=4)

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    return {"n_computable": len(computable), "n_excluded": len(not_computable)}


def _ring_legend_handle(ring_quantile: float, label: str) -> mlines.Line2D:
    return mlines.Line2D([0], [0], marker="o", color="w", markerfacecolor="white",
                          markeredgecolor="#d62728", markeredgewidth=1.3, markersize=9,
                          label=f"Top {round((1 - ring_quantile) * 100)}% {label} (in-country)")


def _render_scenario_bubble_figure(
    countries: list[str], final: pd.DataFrame, ring_col: str | None, ring_label: str,
    caption: str, out_stem: str, combined: bool,
    water_scenarios: tuple[str, ...] = WATER_SCENARIOS, ring_quantile: float = 0.8,
) -> dict[str, pathlib.Path]:
    """Categories 1 (overview) and 10 (computable-base) -- one figure per
    country with all ``water_scenarios`` as side-by-side panels
    (``combined=False``), or one grid figure, countries (rows) x scenarios
    (columns) (``combined=True``). See module docstring, B2."""
    handles = bucket_legend_handles() + (
        [_ring_legend_handle(ring_quantile, ring_label)] if ring_col else []
    ) + [not_computable_legend_handle()]

    if combined:
        figsize, heights = _combined_grid_figsize(countries, len(water_scenarios))
        fig, axes = plt.subplots(len(countries), len(water_scenarios), figsize=figsize,
                                  gridspec_kw={"height_ratios": heights}, constrained_layout=True)
        axes = np.atleast_2d(axes)
        for row, country in enumerate(countries):
            for col, ws in enumerate(water_scenarios):
                frame = _country_frame(final, country, ws)
                stats = _draw_bubble_panel(axes[row, col], country, frame, ring_col, ring_quantile)
                panel_title(axes[row, col], ws, stats["n_computable"], stats["n_excluded"])
                if col == 0:
                    axes[row, col].set_ylabel(f"{country}\nLatitude")
        legend_below_artists(fig, axes.ravel().tolist(), handles, ncol=len(handles), fontsize=fs(10), frameon=False)
        figure_caption_footer(fig, axes.ravel().tolist(), caption, countries)
        out_path = save_figure(fig, OUTPUT_MAPS / "combined" / f"{out_stem}.png")
        logger.info("%s (combined) saved to %s", out_stem, out_path)
        return {"combined": out_path}

    paths: dict[str, pathlib.Path] = {}
    for country in countries:
        figsize = _country_scenario_figsize(country, len(water_scenarios))
        fig, axes = plt.subplots(1, len(water_scenarios), figsize=figsize, constrained_layout=True)
        axes = np.atleast_1d(axes)
        for ax, ws in zip(axes, water_scenarios):
            frame = _country_frame(final, country, ws)
            stats = _draw_bubble_panel(ax, country, frame, ring_col, ring_quantile)
            panel_title(ax, ws, stats["n_computable"], stats["n_excluded"])
        fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.02),
                   ncol=2, fontsize=fs(8), frameon=False)
        figure_caption_footer(fig, list(axes), f"{caption} -- {country}", [country])
        out_path = save_figure(fig, OUTPUT_MAPS / country / f"{out_stem}.png")
        paths[country] = out_path
        logger.info("%s (%s) saved to %s", out_stem, country, out_path)
    return paths


# --------------------------------------------------------------------------
# Category 1 -- CCRS overview map
# --------------------------------------------------------------------------
def plot_ccrs_overview_map(
    countries: list[str] | None = None, gcm: str = PRIMARY_GCM,
    final: pd.DataFrame | None = None, combined: bool = False,
    water_scenarios: tuple[str, ...] = WATER_SCENARIOS,
) -> dict[str, pathlib.Path]:
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    ring_col = f"ccrs_{gcm}"
    return _render_scenario_bubble_figure(
        countries, final, ring_col, "CCRS", f"CCRS overview ({gcm})",
        f"ccrs_overview_{gcm}", combined, water_scenarios,
    )


# --------------------------------------------------------------------------
# Category 2 -- CCRS scenario-delta map
# --------------------------------------------------------------------------
def _draw_delta_panel(ax, country: str, frame_country: pd.DataFrame, max_abs: float, alpha: float = 0.6):
    draw_country_boundary(ax, country)
    sizes = marker_sizes(frame_country["capacity_mw"])
    sc = ax.scatter(frame_country["lon"], frame_country["lat"], s=sizes, c=frame_country["delta"],
                     cmap=DIVERGING_CMAP, vmin=-max_abs, vmax=max_abs, alpha=alpha, zorder=3,
                     edgecolors="black", linewidths=0.4)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    return sc


def _compute_scenario_delta(final: pd.DataFrame, country: str, scenario_a: str, scenario_b: str,
                             gcm: str) -> pd.DataFrame:
    col = f"ccrs_{gcm}"
    a = final[(final["country"] == country) & (final["water_scenario"] == scenario_a) & final["computable"]]
    b = final[(final["country"] == country) & (final["water_scenario"] == scenario_b) & final["computable"]]
    merged = a[["plant_uid", "lat", "lon", "capacity_mw", col]].merge(
        b[["plant_uid", col]], on="plant_uid", suffixes=("_a", "_b"),
    )
    merged["delta"] = merged[f"{col}_b"] - merged[f"{col}_a"]
    return merged


def plot_ccrs_scenario_delta_map(
    countries: list[str] | None = None, scenario_a: str = "opt", scenario_b: str = "pes",
    gcm: str = PRIMARY_GCM, final: pd.DataFrame | None = None, combined: bool = False,
) -> dict[str, pathlib.Path]:
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    frames = {c: _compute_scenario_delta(final, c, scenario_a, scenario_b, gcm) for c in countries}
    max_abs = max((f["delta"].abs().max() for f in frames.values() if len(f)), default=1.0)
    caption = f"CCRS scenario delta ({gcm}, {scenario_b} minus {scenario_a})"
    stem = f"ccrs_scenario_delta_{gcm}_{scenario_a}_vs_{scenario_b}"

    if combined:
        widths = [aspect_ratio_width(c, 9.0) for c in countries]
        fig, axes = plt.subplots(1, len(countries), figsize=(sum(widths), 9.0),
                                  gridspec_kw={"width_ratios": widths}, constrained_layout=True)
        axes = np.atleast_1d(axes)
        sc = None
        for ax, country in zip(axes, countries):
            sc = _draw_delta_panel(ax, country, frames[country], max_abs)
            panel_title(ax, country, len(frames[country]))
        cbar = fig.colorbar(sc, ax=axes.tolist(), orientation="horizontal", pad=0.08, shrink=0.5, aspect=30)
        cbar.set_label(f"CCRS delta ({scenario_b} minus {scenario_a})", fontsize=fs(9))
        figure_caption_footer(fig, list(axes), caption, countries)
        out_path = save_figure(fig, OUTPUT_MAPS / "combined" / f"{stem}.png")
        logger.info("%s (combined) saved to %s", stem, out_path)
        return {"combined": out_path}

    paths = {}
    for country in countries:
        width = aspect_ratio_width(country, 7.0)
        fig, ax = plt.subplots(figsize=(width, 7.0))
        sc = _draw_delta_panel(ax, country, frames[country], max_abs)
        panel_title(ax, country, len(frames[country]))
        fig.subplots_adjust(top=0.88, bottom=0.20, left=0.10, right=0.97)
        cbar = fig.colorbar(sc, ax=ax, orientation="horizontal", pad=0.10, shrink=0.85, aspect=25)
        cbar.set_label(f"CCRS delta ({scenario_b} minus {scenario_a})", fontsize=fs(8))
        figure_caption_footer_single(fig, ax, f"{caption} -- {country}", [country])
        out_path = save_figure(fig, OUTPUT_MAPS / country / f"{stem}.png")
        paths[country] = out_path
        logger.info("%s (%s) saved to %s", stem, country, out_path)
    return paths


# --------------------------------------------------------------------------
# Category 3 -- WaterRiskBand categorical map
# --------------------------------------------------------------------------
def _draw_band_panel(ax, country: str, frame_country: pd.DataFrame, band_col: str,
                      band_colors: dict, alpha: float = 0.7) -> int:
    draw_country_boundary(ax, country)
    banded = frame_country.dropna(subset=[band_col])
    sizes = marker_sizes(banded["capacity_mw"])
    colors = banded[band_col].map(band_colors).fillna("#cccccc")
    ax.scatter(banded["lon"], banded["lat"], s=sizes, c=list(colors), alpha=alpha,
               edgecolors="black", linewidths=0.3, zorder=3)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    return len(banded)


def _band_legend_handles(band_colors: dict) -> list[mlines.Line2D]:
    return [
        mlines.Line2D([0], [0], marker="o", color="w", markerfacecolor=color,
                      markeredgecolor="black", markeredgewidth=0.3, markersize=9, label=str(label))
        for label, color in band_colors.items()
    ]


def plot_water_risk_band_map(
    countries: list[str] | None = None, final: pd.DataFrame | None = None, combined: bool = False,
    water_scenarios: tuple[str, ...] = WATER_SCENARIOS,
) -> dict[str, pathlib.Path]:
    """Category 3 -- WaterRiskBand is GCM-independent (risk_bands.py); no
    ``gcm`` parameter. Generated for all three water scenarios in one
    figure (B2) -- see ``_render_scenario_bubble_figure``'s grid layout,
    reused here with the band-panel drawer instead of the bubble drawer."""
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    handles = _band_legend_handles(WATER_BAND_COLORS)
    caption = "WaterRiskBand"
    stem = "water_risk_band"

    if combined:
        figsize, heights = _combined_grid_figsize(countries, len(water_scenarios))
        fig, axes = plt.subplots(len(countries), len(water_scenarios), figsize=figsize,
                                  gridspec_kw={"height_ratios": heights}, constrained_layout=True)
        axes = np.atleast_2d(axes)
        for row, country in enumerate(countries):
            for col, ws in enumerate(water_scenarios):
                frame = _country_frame(final, country, ws)
                n = _draw_band_panel(axes[row, col], country, frame, "water_risk_band", WATER_BAND_COLORS)
                panel_title(axes[row, col], ws, n)
                if col == 0:
                    axes[row, col].set_ylabel(f"{country}\nLatitude")
        legend_below_artists(fig, axes.ravel().tolist(), handles, ncol=len(handles), fontsize=fs(9), frameon=False)
        figure_caption_footer(fig, axes.ravel().tolist(), caption, countries)
        out_path = save_figure(fig, OUTPUT_MAPS / "combined" / f"{stem}.png")
        logger.info("%s (combined) saved to %s", stem, out_path)
        return {"combined": out_path}

    paths = {}
    for country in countries:
        figsize = _country_scenario_figsize(country, len(water_scenarios))
        fig, axes = plt.subplots(1, len(water_scenarios), figsize=figsize, constrained_layout=True)
        axes = np.atleast_1d(axes)
        for ax, ws in zip(axes, water_scenarios):
            frame = _country_frame(final, country, ws)
            n = _draw_band_panel(ax, country, frame, "water_risk_band", WATER_BAND_COLORS)
            panel_title(ax, ws, n)
        fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.02),
                   ncol=3, fontsize=fs(8), frameon=False)
        figure_caption_footer(fig, list(axes), f"{caption} -- {country}", [country])
        out_path = save_figure(fig, OUTPUT_MAPS / country / f"{stem}.png")
        paths[country] = out_path
        logger.info("%s (%s) saved to %s", stem, country, out_path)
    return paths


# --------------------------------------------------------------------------
# Category 4 -- HeatRiskBand categorical map (B1 rewrite)
# --------------------------------------------------------------------------
def plot_heat_risk_band_map(
    countries: list[str] | None = None, water_scenario: str = "bau",
    final: pd.DataFrame | None = None, gcm: str = PRIMARY_GCM,
) -> dict[str, pathlib.Path]:
    """Category 4 -- rewritten per Douglas's 2026-09-04 review (B1): one
    figure per heat scenario (call once per ``water_scenario``), GFDL-ESM4
    (primary) ONLY, three country panels side by side -- the previous
    ssp370-only, two-GCM-row layout wasted space and only ever covered one
    scenario. The GFDL-vs-MIROC6 comparison this drops is not lost: it is
    now a compact per-country table (``src/visualization/tables.py``,
    ``heat_band_gcm_comparison_table``) instead of a duplicated map -- see
    that module's docstring for why a table was chosen over a second map.

    Combined-only (three countries already share the one figure; a
    "per-country" variant would be a single-panel map with nothing to
    compare against, which the old repo never had a use for either)."""
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    heat_scenario = WATER_TO_HEAT[water_scenario]
    band_col = f"heat_risk_band_{gcm}"
    handles = _band_legend_handles(HEAT_BAND_COLORS)
    caption = f"HeatRiskBand ({heat_scenario}, {gcm} primary)"
    stem = f"heat_risk_band_{heat_scenario}"

    widths = [aspect_ratio_width(c, 8.0) for c in countries]
    fig, axes = plt.subplots(1, len(countries), figsize=(sum(widths), 8.0),
                              gridspec_kw={"width_ratios": widths}, constrained_layout=True)
    axes = np.atleast_1d(axes)
    for ax, country in zip(axes, countries):
        frame = _country_frame(final, country, water_scenario).copy()
        frame["_band"] = frame[band_col]
        n = _draw_band_panel(ax, country, frame, "_band", HEAT_BAND_COLORS)
        panel_title(ax, country, n)
    legend_below_artists(fig, list(axes), handles, ncol=len(handles), fontsize=fs(9), frameon=False)
    figure_caption_footer(fig, list(axes), caption, countries)
    out_path = save_figure(fig, OUTPUT_MAPS / "combined" / f"{stem}.png")
    logger.info("%s saved to %s", stem, out_path)
    return {"combined": out_path}


# --------------------------------------------------------------------------
# Category 10 -- data-completeness / computable-base map
# --------------------------------------------------------------------------
def plot_computable_base_map(
    countries: list[str] | None = None, final: pd.DataFrame | None = None, combined: bool = False,
    water_scenarios: tuple[str, ...] = WATER_SCENARIOS,
) -> dict[str, pathlib.Path]:
    """Plants excluded from the V6 computable base (missing
    ``commissioning_year`` -> neutral ``age_factor``) -- same
    "never omit, mark distinctly" convention as every other bubble map here
    (``_draw_bubble_panel``), just without the top-quantile ring (the point
    of this map is the grey ``x`` markers, not a risk ranking). Generated for
    all three water scenarios in one figure (B2) -- membership in the
    computable base does not vary by scenario, but the panel grid is kept
    consistent with categories 1/3 for layout uniformity and because Douglas's
    review asked for all three scenarios here too."""
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    return _render_scenario_bubble_figure(
        countries, final, None, "", "Data completeness -- V6 computable base",
        "computable_base", combined, water_scenarios,
    )
