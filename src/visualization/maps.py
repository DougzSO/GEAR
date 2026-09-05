"""
CCRS geospatial maps -- categories 1 (overview), 2 (scenario delta),
3 (WaterRiskBand), 4 (HeatRiskBand), 10 (computable-base completeness).

Reused directly from the old repo's ``maps.py`` (see ``_common.py``'s
docstring for the full list): boundary/disputed-territory drawing, dynamic
per-country figsize, the sqrt-of-capacity marker-size convention, dpi=200
PNG+PDF saving, footer/legend positioning. The panel-drawing logic itself is
new -- adapted to the CCRS schema (``plant_uid``, ``ccrs_{gcm}``, 4 buckets,
``risk_bands.py``'s two independent bands) rather than the old SCI schema.

--------------------------------------------------------------------------
Douglas's 2026-09-04 review round -- what changed
--------------------------------------------------------------------------
No figure prints a title (``fig.suptitle``). Per-panel labels
("Brazil (Power Plants=1,234)") are bold, reading ``Power Plants=N`` instead
of ``n=N`` (``_common.panel_title``).

--------------------------------------------------------------------------
Douglas's 2026-09-05 review round -- corrections
--------------------------------------------------------------------------
- **Correction 1**: categories 1/3/10 (overview / WaterRiskBand /
  computable-base) had been misread from the 2026-09-04 brief as "pack all
  three water scenarios into one figure" (a country x scenario grid). The
  brief actually asked for generation ACROSS all three scenarios, one
  figure per scenario -- exactly the layout category 4 (HeatRiskBand)
  already used correctly. All four categories now share that same shape:
  one figure per call, one ``water_scenario`` argument, three country
  panels side by side, ``combined``-only (no per-country single-panel
  variant -- there is nothing to lay "side by side" with just one
  country). Call once per scenario to cover all three -- see
  ``src/config``/``ccrs_calculator.WATER_SCENARIOS`` for the three values.
- **Correction 2**: every figure-level caption/disclaimer footer
  (``_common.figure_caption_footer``) is removed from every map category --
  below each map there is now only the legend, nothing else. This
  includes the GADM boundary disclaimer that used to ride on the same
  footer line. *Point to validate*: the disclaimer was a deliberate
  data-provenance/compliance note for India's disputed admin-1 territory,
  not "descriptive context" in the sense Douglas's instruction targeted
  (scenario/GCM/category text) -- it is removed here because the
  instruction said "apenas a legenda" (only the legend) with no stated
  exception, but this should be confirmed rather than assumed permanent.
- **Correction 3**: every geographic map panel gets its own small compass
  rose (``_common.add_compass_rose``), upper right, not a single shared
  one for the whole figure. Category 2 (scenario delta) is included (a
  geographic map like the other four) even though it was not named in the
  B1-B3 2026-09-04 corrections.
"""

from __future__ import annotations

import logging
import pathlib
from typing import Callable

import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import COUNTRIES, OUTPUT_MAPS
from src.index.ccrs_calculator import WATER_TO_HEAT
from src.index.risk_bands import PRIMARY_GCM, WORST_CASE_COMPARABILITY_NOTE, worst_case_band
from src.visualization import data as vdata
from src.visualization._common import (
    BUCKET_COLORS,
    DIVERGING_CMAP,
    HEAT_BAND_COLORS,
    NOT_COMPUTABLE_COLOR,
    NOT_COMPUTABLE_MARKER,
    WATER_BAND_COLORS,
    add_compass_rose,
    aspect_ratio_width,
    bucket_legend_handles,
    draw_country_boundary,
    figure_caption_footer,
    fs,
    legend_below_artists,
    marker_sizes,
    not_computable_legend_handle,
    panel_title,
    save_figure,
)

logger = logging.getLogger(__name__)


def _country_frame(final: pd.DataFrame, country: str, water_scenario: str) -> pd.DataFrame:
    return final[(final["water_scenario"] == water_scenario) & (final["country"] == country)]


# --------------------------------------------------------------------------
# Shared "countries side by side, one scenario" figure -- categories 1, 3, 10
# (and reused inline by 4/2, which have their own extra needs: a fixed GCM
# band column / a colorbar respectively)
# --------------------------------------------------------------------------
def _render_country_row_figure(
    countries: list[str], draw_and_title: Callable[[object, str], None],
    handles: list, out_path: pathlib.Path, base_height: float = 8.0,
    legend_ncol: int | None = None, legend_fontsize: float = 10.0,
) -> pathlib.Path:
    """One figure, ``countries`` side by side (one panel each), a shared
    legend below. ``draw_and_title(ax, country)`` draws the panel's content
    AND sets its (bold, "Power Plants=N") title -- the two differ per
    category, everything else (figsize, legend, compass rose placement via
    the panel-drawing helpers, saving) is common."""
    widths = [aspect_ratio_width(c, base_height) for c in countries]
    fig, axes = plt.subplots(1, len(countries), figsize=(sum(widths), base_height),
                              gridspec_kw={"width_ratios": widths}, constrained_layout=True)
    axes = np.atleast_1d(axes)
    for ax, country in zip(axes, countries):
        draw_and_title(ax, country)
    legend_below_artists(fig, list(axes), handles, ncol=legend_ncol or len(handles),
                          fontsize=fs(legend_fontsize), frameon=False)
    return save_figure(fig, out_path)


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
    via ``_common.panel_title``, since the label text differs by category."""
    draw_country_boundary(ax, country)
    add_compass_rose(ax)
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


# --------------------------------------------------------------------------
# Category 1 -- CCRS overview map
# --------------------------------------------------------------------------
def plot_ccrs_overview_map(
    countries: list[str] | None = None, gcm: str = PRIMARY_GCM, water_scenario: str = "bau",
    final: pd.DataFrame | None = None,
) -> dict[str, pathlib.Path]:
    """One figure per ``water_scenario`` (call once per scenario to cover
    all three), three country panels side by side -- same layout as
    category 4 (HeatRiskBand)."""
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    ring_col = f"ccrs_{gcm}"
    handles = bucket_legend_handles() + [_ring_legend_handle(0.8, "CCRS"), not_computable_legend_handle()]

    def draw_and_title(ax, country):
        frame = _country_frame(final, country, water_scenario)
        stats = _draw_bubble_panel(ax, country, frame, ring_col, ring_quantile=0.8)
        panel_title(ax, country, stats["n_computable"], stats["n_excluded"])

    stem = f"ccrs_overview_{gcm}_{water_scenario}"
    out_path = _render_country_row_figure(
        countries, draw_and_title, handles, OUTPUT_MAPS / "combined" / f"{stem}.png",
    )
    logger.info("%s saved to %s", stem, out_path)
    return {"combined": out_path}


# --------------------------------------------------------------------------
# Category 2 -- CCRS scenario-delta map
# --------------------------------------------------------------------------
def _draw_delta_panel(ax, country: str, frame_country: pd.DataFrame, max_abs: float, alpha: float = 0.6):
    draw_country_boundary(ax, country)
    add_compass_rose(ax)
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
    add_compass_rose(ax)
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
    countries: list[str] | None = None, water_scenario: str = "bau", final: pd.DataFrame | None = None,
) -> dict[str, pathlib.Path]:
    """Category 3 -- WaterRiskBand is GCM-independent (risk_bands.py); no
    ``gcm`` parameter. One figure per ``water_scenario`` (call once per
    scenario to cover all three), same layout as category 4."""
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    handles = _band_legend_handles(WATER_BAND_COLORS)

    def draw_and_title(ax, country):
        frame = _country_frame(final, country, water_scenario)
        n = _draw_band_panel(ax, country, frame, "water_risk_band", WATER_BAND_COLORS)
        panel_title(ax, country, n)

    stem = f"water_risk_band_{water_scenario}"
    out_path = _render_country_row_figure(
        countries, draw_and_title, handles, OUTPUT_MAPS / "combined" / f"{stem}.png", legend_fontsize=9,
    )
    logger.info("%s saved to %s", stem, out_path)
    return {"combined": out_path}


# --------------------------------------------------------------------------
# Category 4 -- HeatRiskBand categorical map
# --------------------------------------------------------------------------
def plot_heat_risk_band_map(
    countries: list[str] | None = None, water_scenario: str = "bau",
    final: pd.DataFrame | None = None, gcm: str = PRIMARY_GCM,
) -> dict[str, pathlib.Path]:
    """Category 4 -- one figure per heat scenario (call once per
    ``water_scenario``), GFDL-ESM4 (primary) ONLY, three country panels
    side by side -- the reference layout every other map category in this
    module now matches (Douglas's 2026-09-05 review, correction 1). The
    GFDL-vs-MIROC6 comparison is a compact per-country table
    (``src/visualization/tables.py``, ``heat_band_gcm_comparison_table``)
    instead of a duplicated map."""
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    heat_scenario = WATER_TO_HEAT[water_scenario]
    band_col = f"heat_risk_band_{gcm}"
    handles = _band_legend_handles(HEAT_BAND_COLORS)

    def draw_and_title(ax, country):
        frame = _country_frame(final, country, water_scenario).copy()
        frame["_band"] = frame[band_col]
        n = _draw_band_panel(ax, country, frame, "_band", HEAT_BAND_COLORS)
        panel_title(ax, country, n)

    stem = f"heat_risk_band_{heat_scenario}"
    out_path = _render_country_row_figure(
        countries, draw_and_title, handles, OUTPUT_MAPS / "combined" / f"{stem}.png", legend_fontsize=9,
    )
    logger.info("%s saved to %s", stem, out_path)
    return {"combined": out_path}


# --------------------------------------------------------------------------
# Category 3b -- worst-case (Water vs. Heat) risk-band map
#
# Douglas's 2026-09-05 request: color each plant by whichever of
# WaterRiskBand/HeatRiskBand ranks more severe (ordinal max, via
# ``risk_bands.worst_case_band`` -- see that module for the proposed
# 5-level/4-level rank mapping and the water-wins tie-break, both approved).
# This is NOT the "never combine the two bands into one score" rule being
# broken: no numeric fusion happens here, each plant keeps one of the two
# ALREADY-existing categorical labels (and that axis's own established
# color, ``WATER_BAND_COLORS``/``HEAT_BAND_COLORS`` -- no new color is
# invented), exactly ``max(a, b)`` over two ordinal categories, never an
# average or sum of the two ranks.
#
# Marker SHAPE (circle = water is the worse axis, triangle = heat is the
# worse axis) is the "which axis determined it" signal Douglas asked for --
# chosen over a text annotation per plant because a shape carries that
# information without adding any printed text to the map, and the legend
# handles already use the same two shapes, so the mapping is visible without
# a separate explanation.
#
# This is the ONE map category in this module that still prints a caption
# footer (``_common.figure_caption_footer``) below the legend -- every other
# category dropped it under Correction 2. Approved as an explicit exception:
# HeatRiskBand's cuts are this run's own sample-relative p25/p75/p95 (not
# comparable across a different scenario/GCM pool, see ``HEAT_BAND_WARNING``
# in risk_bands.py); a figure that looks like it maps two absolute exposure
# axes side by side is misleading without stating, on the figure itself,
# that only one of the two (water) is actually run-stable. The footer here
# carries ONLY ``risk_bands.WORST_CASE_COMPARABILITY_NOTE`` -- no GADM
# disputed-territory disclaimer is re-added (that removal is unrelated to
# this warning and stays as Correction 2 left it).
# --------------------------------------------------------------------------
def _draw_worst_case_panel(ax, country: str, frame_country: pd.DataFrame, heat_band_col: str,
                            alpha: float = 0.7) -> int:
    draw_country_boundary(ax, country)
    add_compass_rose(ax)
    sub = frame_country.dropna(subset=["water_risk_band", heat_band_col])
    pairs = [worst_case_band(w, h) for w, h in zip(sub["water_risk_band"], sub[heat_band_col])]
    determinant = np.array([p[1] for p in pairs], dtype=object)
    label = np.array([p[0] for p in pairs], dtype=object)
    sizes = marker_sizes(sub["capacity_mw"])
    lon = sub["lon"].to_numpy()
    lat = sub["lat"].to_numpy()

    for axis, marker, palette in (("water", "o", WATER_BAND_COLORS), ("heat", "^", HEAT_BAND_COLORS)):
        mask = determinant == axis
        if not mask.any():
            continue
        colors = [palette[lbl] for lbl in label[mask]]
        ax.scatter(lon[mask], lat[mask], s=np.asarray(sizes)[mask], c=colors, marker=marker,
                   alpha=alpha, edgecolors="black", linewidths=0.3, zorder=3)

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    return len(sub)


def _worst_case_legend_handles() -> list[mlines.Line2D]:
    water_handles = [
        mlines.Line2D([0], [0], marker="o", color="w", markerfacecolor=color, markeredgecolor="black",
                      markeredgewidth=0.3, markersize=9, label=f"Water: {label}")
        for label, color in WATER_BAND_COLORS.items()
    ]
    heat_handles = [
        mlines.Line2D([0], [0], marker="^", color="w", markerfacecolor=color, markeredgecolor="black",
                      markeredgewidth=0.3, markersize=9, label=f"Heat: {label}")
        for label, color in HEAT_BAND_COLORS.items()
    ]
    return water_handles + heat_handles


def plot_worst_case_risk_band_map(
    countries: list[str] | None = None, water_scenario: str = "bau",
    final: pd.DataFrame | None = None, gcm: str = PRIMARY_GCM, base_height: float = 8.0,
) -> dict[str, pathlib.Path]:
    """One figure per ``water_scenario`` (call once per scenario to cover all
    three), three country panels side by side -- same layout as every other
    category in this module. Unlike ``plot_water_risk_band_map``/
    ``plot_heat_risk_band_map`` (one axis each), each plant here is colored
    by whichever of the two bands is more severe (``risk_bands.
    worst_case_band``), marker shape showing which axis was the determinant.
    """
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    heat_band_col = f"heat_risk_band_{gcm}"
    handles = _worst_case_legend_handles()

    widths = [aspect_ratio_width(c, base_height) for c in countries]
    fig, axes = plt.subplots(1, len(countries), figsize=(sum(widths), base_height),
                              gridspec_kw={"width_ratios": widths}, constrained_layout=True)
    axes = np.atleast_1d(axes)
    for ax, country in zip(axes, countries):
        frame = _country_frame(final, country, water_scenario)
        n = _draw_worst_case_panel(ax, country, frame, heat_band_col)
        panel_title(ax, country, n)

    legend = legend_below_artists(fig, list(axes), handles, ncol=5, fontsize=fs(9), frameon=False)
    figure_caption_footer(fig, [*axes, legend], WORST_CASE_COMPARABILITY_NOTE)

    stem = f"worst_case_risk_band_{gcm}_{water_scenario}"
    out_path = save_figure(fig, OUTPUT_MAPS / "combined" / f"{stem}.png")
    logger.info("%s saved to %s", stem, out_path)
    return {"combined": out_path}


# --------------------------------------------------------------------------
# Category 10 -- data-completeness / computable-base map
# --------------------------------------------------------------------------
def plot_computable_base_map(
    countries: list[str] | None = None, water_scenario: str = "bau", final: pd.DataFrame | None = None,
) -> dict[str, pathlib.Path]:
    """Plants excluded from the V6 computable base (missing
    ``commissioning_year`` -> neutral ``age_factor``) -- same
    "never omit, mark distinctly" convention as every other bubble map here
    (``_draw_bubble_panel``), just without the top-quantile ring. One
    figure per ``water_scenario`` (call once per scenario to cover all
    three) -- membership in the computable base does not vary by scenario,
    but the layout is kept consistent with categories 1/3/4."""
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    handles = bucket_legend_handles() + [not_computable_legend_handle()]

    def draw_and_title(ax, country):
        frame = _country_frame(final, country, water_scenario)
        stats = _draw_bubble_panel(ax, country, frame, None)
        panel_title(ax, country, stats["n_computable"], stats["n_excluded"])

    stem = f"computable_base_{water_scenario}"
    out_path = _render_country_row_figure(
        countries, draw_and_title, handles, OUTPUT_MAPS / "combined" / f"{stem}.png",
    )
    logger.info("%s saved to %s", stem, out_path)
    return {"combined": out_path}
