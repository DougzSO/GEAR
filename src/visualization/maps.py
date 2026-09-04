"""
CCRS geospatial maps -- categories 1 (overview), 2 (scenario delta),
3 (WaterRiskBand), 4 (HeatRiskBand), 10 (computable-base completeness).

Every category is exposed as one function with a ``combined: bool`` switch
(default ``False``, per-country -- one figure per country, dict keyed by
country) rather than a separate pair of functions per category (the old
repo's ``plot_X_map`` / ``plot_X_map_per_country`` split) -- same output
shapes, less duplicated plumbing. ``combined=True`` produces one
side-by-side figure for every requested country, dict with a single
``"combined"`` key.

Reused directly from the old repo's ``maps.py`` (see ``_common.py``'s
docstring for the full list): boundary/disputed-territory drawing, dynamic
per-country figsize, the sqrt-of-capacity marker-size convention, dpi=200
PNG+PDF saving, footer/legend positioning. The panel-drawing logic itself is
new -- adapted to the CCRS schema (``plant_uid``, ``ccrs_{gcm}``, 4 buckets,
``risk_bands.py``'s two independent bands) rather than the old SCI schema.
"""

from __future__ import annotations

import logging
import pathlib

import matplotlib.lines as mlines
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import COUNTRIES, OUTPUT_MAPS
from src.index.ccrs_calculator import WATER_TO_HEAT
from src.index.risk_bands import PRIMARY_GCM
from src.visualization import data as vdata
from src.visualization._common import (
    BUCKET_COLORS,
    DIVERGING_CMAP,
    HEAT_BAND_COLORS,
    NOT_COMPUTABLE_COLOR,
    NOT_COMPUTABLE_MARKER,
    bucket_legend_handles,
    draw_country_boundary,
    footer_below_panels,
    footer_with_gadm_disclaimer,
    legend_below_artists,
    marker_sizes,
    multi_panel_figsize,
    not_computable_legend_handle,
    save_figure,
    single_panel_figsize,
)
from src.visualization._common import WATER_BAND_COLORS

logger = logging.getLogger(__name__)


def _scenario_rows(final: pd.DataFrame, water_scenario: str) -> pd.DataFrame:
    return final[final["water_scenario"] == water_scenario]


def _country_frame(final: pd.DataFrame, country: str, water_scenario: str) -> pd.DataFrame:
    return _scenario_rows(final, water_scenario).loc[lambda d: d["country"] == country]


# --------------------------------------------------------------------------
# Shared bubble-map panel -- categories 1 and 10
# --------------------------------------------------------------------------
def _draw_bubble_panel(ax, country: str, frame_country: pd.DataFrame, ring_col: str | None,
                        ring_quantile: float = 0.8, alpha: float = 0.6) -> dict:
    """Bucket-colored bubble map, size ~ capacity. Plants outside the V6
    computable base (no ``commissioning_year``) are NEVER omitted -- drawn
    as a distinct grey ``x`` marker, same convention for every category that
    uses this panel (item 1's overview ring and item 10's completeness map
    both go through here)."""
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

    ax.set_title(f"{country} (n={len(computable):,}, excluded={len(not_computable):,})")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    return {"n_computable": len(computable), "n_excluded": len(not_computable)}


def _ring_legend_handle(ring_quantile: float, label: str) -> mlines.Line2D:
    return mlines.Line2D([0], [0], marker="o", color="w", markerfacecolor="white",
                          markeredgecolor="#d62728", markeredgewidth=1.3, markersize=9,
                          label=f"Top {round((1 - ring_quantile) * 100)}% {label} (in-country)")


def _render_bubble_figure(
    countries: list[str], frames_by_country: dict[str, pd.DataFrame], ring_col: str | None,
    ring_label: str, title: str, out_stem: str, combined: bool, ring_quantile: float = 0.8,
) -> dict[str, pathlib.Path]:
    handles = bucket_legend_handles() + (
        [_ring_legend_handle(ring_quantile, ring_label)] if ring_col else []
    ) + [not_computable_legend_handle()]

    if combined:
        figsize, widths = multi_panel_figsize(countries)
        fig, axes = plt.subplots(1, len(countries), figsize=figsize,
                                  gridspec_kw={"width_ratios": widths}, constrained_layout=True)
        axes = np.atleast_1d(axes)
        for ax, country in zip(axes, countries):
            _draw_bubble_panel(ax, country, frames_by_country[country], ring_col, ring_quantile)
        legend_below_artists(fig, list(axes), handles, ncol=len(handles), fontsize=10, frameon=False)
        disclaimer = footer_with_gadm_disclaimer("", countries)
        if disclaimer:
            footer_below_panels(fig, list(axes), disclaimer)
        fig.suptitle(title, y=1.02)
        out_path = save_figure(fig, OUTPUT_MAPS / "combined" / f"{out_stem}.png")
        logger.info("%s (combined) saved to %s", out_stem, out_path)
        return {"combined": out_path}

    paths: dict[str, pathlib.Path] = {}
    for country in countries:
        fig, ax = plt.subplots(figsize=single_panel_figsize(country))
        _draw_bubble_panel(ax, country, frames_by_country[country], ring_col, ring_quantile)
        fig.subplots_adjust(top=0.90, bottom=0.16, left=0.10, right=0.97)
        fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.06),
                   ncol=2, fontsize=8, frameon=False)
        fig.suptitle(f"{title} -- {country}", fontsize=13, y=0.985)
        disclaimer = footer_with_gadm_disclaimer("", [country])
        if disclaimer:
            fig.text(0.99, 0.005, disclaimer, ha="right", va="bottom", fontsize=8, style="italic")
        out_path = save_figure(fig, OUTPUT_MAPS / country / f"{out_stem}.png")
        paths[country] = out_path
        logger.info("%s (%s) saved to %s", out_stem, country, out_path)
    return paths


# --------------------------------------------------------------------------
# Category 1 -- CCRS overview map
# --------------------------------------------------------------------------
def plot_ccrs_overview_map(
    countries: list[str] | None = None, gcm: str = PRIMARY_GCM, water_scenario: str = "bau",
    final: pd.DataFrame | None = None, combined: bool = False,
) -> dict[str, pathlib.Path]:
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    ring_col = f"ccrs_{gcm}"
    frames = {c: _country_frame(final, c, water_scenario) for c in countries}
    return _render_bubble_figure(
        countries, frames, ring_col, "CCRS", f"CCRS overview ({gcm}, {water_scenario})",
        f"ccrs_overview_{gcm}_{water_scenario}", combined,
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
    ax.set_title(f"{country} (n={len(frame_country):,})")
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
    title = f"CCRS scenario delta ({gcm}, {scenario_b} minus {scenario_a})"
    stem = f"ccrs_scenario_delta_{gcm}_{scenario_a}_vs_{scenario_b}"

    if combined:
        figsize, widths = multi_panel_figsize(countries)
        fig, axes = plt.subplots(1, len(countries), figsize=figsize,
                                  gridspec_kw={"width_ratios": widths}, constrained_layout=True)
        axes = np.atleast_1d(axes)
        sc = None
        for ax, country in zip(axes, countries):
            sc = _draw_delta_panel(ax, country, frames[country], max_abs)
        cbar = fig.colorbar(sc, ax=axes.tolist(), orientation="horizontal", pad=0.08, shrink=0.5, aspect=30)
        cbar.set_label(f"CCRS delta ({scenario_b} minus {scenario_a})")
        fig.suptitle(title, y=1.05)
        out_path = save_figure(fig, OUTPUT_MAPS / "combined" / f"{stem}.png")
        logger.info("%s (combined) saved to %s", stem, out_path)
        return {"combined": out_path}

    paths = {}
    for country in countries:
        fig, ax = plt.subplots(figsize=single_panel_figsize(country, top=0.88, bottom=0.20))
        sc = _draw_delta_panel(ax, country, frames[country], max_abs)
        fig.subplots_adjust(top=0.88, bottom=0.20, left=0.10, right=0.97)
        cbar = fig.colorbar(sc, ax=ax, orientation="horizontal", pad=0.10, shrink=0.85, aspect=25)
        cbar.set_label(f"CCRS delta ({scenario_b} minus {scenario_a})", fontsize=8)
        fig.suptitle(f"{title} -- {country}", fontsize=11, y=0.985)
        out_path = save_figure(fig, OUTPUT_MAPS / country / f"{stem}.png")
        paths[country] = out_path
        logger.info("%s (%s) saved to %s", stem, country, out_path)
    return paths


# --------------------------------------------------------------------------
# Categories 3/4 -- WaterRiskBand / HeatRiskBand categorical maps
# --------------------------------------------------------------------------
def _draw_band_panel(ax, country: str, frame_country: pd.DataFrame, band_col: str,
                      band_colors: dict, alpha: float = 0.7):
    draw_country_boundary(ax, country)
    banded = frame_country.dropna(subset=[band_col])
    sizes = marker_sizes(banded["capacity_mw"])
    colors = banded[band_col].map(band_colors).fillna("#cccccc")
    ax.scatter(banded["lon"], banded["lat"], s=sizes, c=list(colors), alpha=alpha,
               edgecolors="black", linewidths=0.3, zorder=3)
    ax.set_title(f"{country} (n={len(banded):,})")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")


def _band_legend_handles(band_colors: dict) -> list[mlines.Line2D]:
    return [
        mlines.Line2D([0], [0], marker="o", color="w", markerfacecolor=color,
                      markeredgecolor="black", markeredgewidth=0.3, markersize=9, label=str(label))
        for label, color in band_colors.items()
    ]


def plot_water_risk_band_map(
    countries: list[str] | None = None, water_scenario: str = "bau",
    final: pd.DataFrame | None = None, combined: bool = False,
) -> dict[str, pathlib.Path]:
    """Category 3 -- WaterRiskBand is GCM-independent (risk_bands.py); no
    ``gcm`` parameter."""
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    frames = {c: _country_frame(final, c, water_scenario) for c in countries}
    handles = _band_legend_handles(WATER_BAND_COLORS)
    title = f"WaterRiskBand ({water_scenario})"
    stem = f"water_risk_band_{water_scenario}"

    if combined:
        figsize, widths = multi_panel_figsize(countries)
        fig, axes = plt.subplots(1, len(countries), figsize=figsize,
                                  gridspec_kw={"width_ratios": widths}, constrained_layout=True)
        axes = np.atleast_1d(axes)
        for ax, country in zip(axes, countries):
            _draw_band_panel(ax, country, frames[country], "water_risk_band", WATER_BAND_COLORS)
        legend_below_artists(fig, list(axes), handles, ncol=len(handles), fontsize=9, frameon=False)
        fig.suptitle(title, y=1.03)
        out_path = save_figure(fig, OUTPUT_MAPS / "combined" / f"{stem}.png")
        logger.info("%s (combined) saved to %s", stem, out_path)
        return {"combined": out_path}

    paths = {}
    for country in countries:
        fig, ax = plt.subplots(figsize=single_panel_figsize(country))
        _draw_band_panel(ax, country, frames[country], "water_risk_band", WATER_BAND_COLORS)
        fig.subplots_adjust(top=0.90, bottom=0.18, left=0.10, right=0.97)
        fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.07),
                   ncol=3, fontsize=8, frameon=False)
        fig.suptitle(f"{title} -- {country}", fontsize=13, y=0.985)
        out_path = save_figure(fig, OUTPUT_MAPS / country / f"{stem}.png")
        paths[country] = out_path
        logger.info("%s (%s) saved to %s", stem, country, out_path)
    return paths


def plot_heat_risk_band_map(
    countries: list[str] | None = None, water_scenario: str = "bau",
    final: pd.DataFrame | None = None, combined: bool = False, gcms: tuple[str, str] = (PRIMARY_GCM, "miroc6"),
) -> dict[str, pathlib.Path]:
    """Category 4 -- one GFDL-ESM4 (primary) panel + one MIROC6 (sensitivity)
    panel, side by side, for every country -- no precedent in the old repo
    (its design had a single GCM). GFDL-ESM4/MIROC6 are never blended
    (ARCHITECTURE.md Section 5.4)."""
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    heat_scenario = WATER_TO_HEAT[water_scenario]
    handles = _band_legend_handles(HEAT_BAND_COLORS)
    title = f"HeatRiskBand ({heat_scenario}) -- GFDL-ESM4 primary, MIROC6 sensitivity panel"
    stem = f"heat_risk_band_{heat_scenario}"

    def frame_for(country, gcm):
        band_col = f"heat_risk_band_{gcm}"
        f = _country_frame(final, country, water_scenario).copy()
        f["_band"] = f[band_col]
        return f

    if combined:
        n_countries = len(countries)
        fig, axes = plt.subplots(2, n_countries, figsize=(5.5 * n_countries, 10), constrained_layout=True)
        axes = np.atleast_2d(axes)
        for row, gcm in enumerate(gcms):
            for col, country in enumerate(countries):
                f = frame_for(country, gcm)
                _draw_band_panel(axes[row, col], country, f, "_band", HEAT_BAND_COLORS)
                if col == 0:
                    axes[row, col].set_ylabel(f"{gcm}\nLatitude")
        legend_below_artists(fig, axes.ravel().tolist(), handles, ncol=len(handles), fontsize=9, frameon=False)
        fig.suptitle(title, y=1.03)
        out_path = save_figure(fig, OUTPUT_MAPS / "combined" / f"{stem}.png")
        logger.info("%s (combined) saved to %s", stem, out_path)
        return {"combined": out_path}

    paths = {}
    for country in countries:
        fig, axes = plt.subplots(1, 2, figsize=(11, 6.5))
        for ax, gcm in zip(axes, gcms):
            f = frame_for(country, gcm)
            _draw_band_panel(ax, country, f, "_band", HEAT_BAND_COLORS)
            ax.set_title(f"{gcm} ({'primary' if gcm == PRIMARY_GCM else 'sensitivity'})")
        fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.02),
                   ncol=len(handles), fontsize=8, frameon=False)
        fig.suptitle(f"{title.split(' -- ')[0]} -- {country}", fontsize=12, y=1.02)
        out_path = save_figure(fig, OUTPUT_MAPS / country / f"{stem}.png")
        paths[country] = out_path
        logger.info("%s (%s) saved to %s", stem, country, out_path)
    return paths


# --------------------------------------------------------------------------
# Category 10 -- data-completeness / computable-base map
# --------------------------------------------------------------------------
def plot_computable_base_map(
    countries: list[str] | None = None, water_scenario: str = "bau",
    final: pd.DataFrame | None = None, combined: bool = False,
) -> dict[str, pathlib.Path]:
    """Plants excluded from the V6 computable base (missing
    ``commissioning_year`` -> neutral ``age_factor``) -- same
    "never omit, mark distinctly" convention as every other bubble map here
    (``_draw_bubble_panel``), just without the top-quantile ring (the point
    of this map is the grey ``x`` markers, not a risk ranking)."""
    countries = countries or COUNTRIES
    final = final if final is not None else vdata.load_ccrs_final()
    frames = {c: _country_frame(final, c, water_scenario) for c in countries}
    return _render_bubble_figure(
        countries, frames, None, "", "Data completeness -- V6 computable base",
        f"computable_base_{water_scenario}", combined,
    )
