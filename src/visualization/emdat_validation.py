"""
Box/strip plot for the EM-DAT x Hazard spatial overlay validation (C6).

Draws ``src.index.emdat_validation.run_validation()``'s ``"polygons"``
table: the admin-1 zonal hazard value split by whether that polygon had a
geocoded EM-DAT event, with the Mann-Whitney U p-value and group sizes
annotated ON the panel. Never a single combined score across countries/
types. The statistical logic (Mann-Whitney U, skip rule at
``emdat_validation.MIN_GROUP_SIZE``) is untouched by this module -- see
``src/index/emdat_validation.py``, not here.

Coverage/proxy caveats are printed in the figure's own footer, not only in
``src.index.emdat_validation``'s docstring -- Douglas's explicit
requirement (2026-09-04) that the limitations travel with the figure
itself.

--------------------------------------------------------------------------
2026-09-05 redesign -- diagnosis: layout, not chart type
--------------------------------------------------------------------------
The original version put one panel per TESTED (country, disaster_type) pair
side by side in a single row (7 panels on the real data) -- cramped, and,
more importantly, gave a highly significant result (India, p=5e-7) the same
visual weight as a null one (Brazil, p=0.87). Box+strip itself is not the
problem: every group here is 3-32 admin-1 polygons, never enough for a
density/ridge overlay (the FIG 4 technique) to be honestly supported --
applying that technique here would repeat exactly the "implies smoothness
the sample can't support" failure Douglas flagged for Portugal in the C4
redesign, at an even smaller N. So box+strip is kept, and the fix is
layout + visual emphasis:

- A fixed grid -- disaster_type (rows, ``emdat_validation.
  DISASTER_TYPE_TO_TERM`` order) x country (columns) -- instead of one row
  per TESTED pair only. Every (country, disaster_type) combination gets a
  same-sized cell, tested or not, so the figure's shape does not change
  with how many pairs happened to be testable.
- Statistically significant cells (p < ``ALPHA`` = 0.05) get a light gold
  background tint and a bold border -- found, not assumed, to be the
  visual emphasis Douglas asked for; non-significant cells stay plain white
  and slightly more transparent, read as "checked, nothing found" rather
  than competing for attention with the significant result.
- p-value AND group sizes stay annotated directly on the panel (already
  true before this redesign, kept, now at a larger, more legible size since
  panels are bigger).
- Skipped pairs (Portugal, Extreme temperature/Drought: every admin-1 unit
  had >= 1 event, no control group) are NOT left blank or text-only --
  whichever group actually has finite data (here, the "with event" side)
  is still drawn as its own single box+strip, so real data is never hidden
  just because the comparison could not run. The skip reason is printed on
  the panel in place of a p-value, and the cell gets a grey hatched
  background so it reads as "not a statistical test" at a glance, still
  inside the same grid as every valid-result cell (does not break the
  layout of the countries with a valid result -- Douglas's explicit test
  requirement).
"""

from __future__ import annotations

import logging
import pathlib
import textwrap

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import COUNTRIES, OUTPUT_MAPS
from src.index import emdat_validation as ev
from src.visualization._common import figure_caption_footer, fs, save_figure

logger = logging.getLogger(__name__)

OUT_DIR = OUTPUT_MAPS

CAPTION = (
    "EXPLORATORY, diagnostic only -- does not feed back into Hazard/CCRS. "
    "Compares only the ~50-53% of EM-DAT events with a structured GADM "
    "Admin Units reference (point-level Lat/Lon covers just 5.3-12.1%, "
    "Portugal 2 events) -- a real sample-selection gap, not a random "
    "subsample. Flood is compared against the water STRESS raster "
    "(scarcity), the closest available term, not excess water. Storm has "
    "no matching Hazard term and is not tested. Gold background = "
    "statistically significant (p<0.05); grey hatching = skipped, no "
    "control group available (shown with its one available group, not "
    "blank). See src/index/emdat_validation.py for the full method and "
    "caveats."
)

_GROUP_COLORS = {"no event": "#cccccc", ">=1 event": "#d62728"}
ALPHA = 0.05
_SIGNIFICANT_FACECOLOR = "#fff3cd"
_SIGNIFICANT_EDGECOLOR = "#b8860b"
_SKIPPED_FACECOLOR = "#f2f2f2"


def _draw_groups(ax, series_label_color: list[tuple[pd.Series, str, str]]) -> None:
    """Draws one box+strip per ``(series, label, color)`` triple actually
    provided -- callers pass only the groups that exist (never a ``None``
    placeholder), so ``boxplot``'s label/data count always match."""
    entries = [(s.dropna(), lbl, c) for s, lbl, c in series_label_color]
    if not entries:
        return
    positions = list(range(1, len(entries) + 1))
    groups = [e[0] for e in entries]
    labels = [e[1] for e in entries]
    colors = [e[2] for e in entries]
    bp = ax.boxplot(groups, positions=positions, tick_labels=labels, patch_artist=True,
                     widths=0.5, showfliers=False)
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)

    rng = np.random.default_rng(0)
    for pos, g, color in zip(positions, groups, colors):
        jitter = rng.normal(0, 0.05, size=len(g))
        ax.scatter(np.full(len(g), pos) + jitter, g, s=16, color="black", alpha=0.6, zorder=3)


def _add_headroom(ax, frac: float = 0.28) -> None:
    """Expands the y-axis top limit after the data is drawn, so the
    p-value/N (or skip-reason) annotation text at the top of the panel
    never overlaps the highest data point or the box/strip itself."""
    lo, hi = ax.get_ylim()
    span = hi - lo
    if span > 0:
        ax.set_ylim(lo, hi + frac * span)


def _panel_tested(ax, country: str, disaster_type: str, term: str, polygons: pd.DataFrame,
                   p_value: float, n_without: int, n_with: int) -> None:
    without = polygons.loc[~polygons["has_event"], "hazard_value"]
    with_ = polygons.loc[polygons["has_event"], "hazard_value"]
    colors = list(_GROUP_COLORS.values())
    _draw_groups(ax, [(without, "no event", colors[0]), (with_, ">=1 event", colors[1])])
    _add_headroom(ax)

    significant = not np.isnan(p_value) and p_value < ALPHA
    if significant:
        ax.set_facecolor(_SIGNIFICANT_FACECOLOR)
        for spine in ax.spines.values():
            spine.set_edgecolor(_SIGNIFICANT_EDGECOLOR)
            spine.set_linewidth(2.2)

    marker = " *" if significant else ""
    ax.set_title(f"{country} / {disaster_type}{marker}", fontweight="bold", fontsize=fs(10))
    p_text = f"Mann-Whitney U p={p_value:.3g}" if not np.isnan(p_value) else "p=n/a"
    ax.text(0.5, 0.93, f"{p_text}\n(n={n_without} / {n_with})", transform=ax.transAxes,
            ha="center", va="top", fontsize=fs(9), fontweight="bold" if significant else "normal")
    ax.set_ylabel(f"{term}, admin-1 zonal mean", fontsize=fs(8.5))


def _panel_skipped(ax, country: str, disaster_type: str, term: str, polygons: pd.DataFrame,
                    skip_reason: str) -> None:
    without = polygons.loc[~polygons["has_event"], "hazard_value"] if len(polygons) else pd.Series(dtype="float64")
    with_ = polygons.loc[polygons["has_event"], "hazard_value"] if len(polygons) else pd.Series(dtype="float64")
    has_without, has_with = without.notna().any(), with_.notna().any()

    ax.set_facecolor(_SKIPPED_FACECOLOR)
    for spine in ax.spines.values():
        spine.set_edgecolor("#999999")
        spine.set_linestyle((0, (4, 2)))

    if has_without or has_with:
        colors = list(_GROUP_COLORS.values())
        entries = []
        if has_without:
            entries.append((without, "no event", colors[0]))
        if has_with:
            entries.append((with_, ">=1 event", colors[1]))
        _draw_groups(ax, entries)
        for bar in ax.patches:
            bar.set_hatch("///")
    else:
        ax.set_xticks([])
        ax.set_yticks([])

    ax.set_title(f"{country} / {disaster_type}", fontweight="bold", fontsize=fs(10), color="#555555")
    wrapped_reason = "\n".join(textwrap.wrap(skip_reason, width=30))
    ax.text(0.5, 0.93, f"not tested:\n{wrapped_reason}", transform=ax.transAxes, ha="center", va="top",
            fontsize=fs(7), color="#555555")
    ax.set_ylabel(f"{term}, admin-1 zonal mean", fontsize=fs(8.5))
    if has_without or has_with:
        _add_headroom(ax, frac=0.55)
    else:
        ax.set_ylim(0, 1)


def plot_emdat_spatial_validation(
    countries: list[str] | None = None, result: dict[str, pd.DataFrame] | None = None,
) -> pathlib.Path:
    """Fixed ``disaster_type`` (rows) x ``country`` (columns) grid -- see the
    module docstring's "2026-09-05 redesign" section for the full
    reasoning. Every cell is drawn, tested or skipped, so the figure's
    shape never depends on how many pairs happened to be testable this
    run."""
    countries = countries or COUNTRIES
    result = result if result is not None else ev.run_validation(countries=countries)
    summary, polygons = result["summary"], result["polygons"]
    disaster_types = list(ev.DISASTER_TYPE_TO_TERM)

    fig, axes = plt.subplots(len(disaster_types), len(countries),
                              figsize=(4.6 * len(countries), 4.4 * len(disaster_types)),
                              constrained_layout=True)
    axes = np.atleast_2d(axes)

    for r, disaster_type in enumerate(disaster_types):
        for c, country in enumerate(countries):
            ax = axes[r, c]
            row_match = summary[(summary["country"] == country) & (summary["disaster_type"] == disaster_type)]
            if len(row_match) == 0:
                ax.text(0.5, 0.5, "no data for\nthis pair", ha="center", va="center",
                        transform=ax.transAxes, fontsize=fs(9), color="#999999")
                ax.set_xticks([])
                ax.set_yticks([])
                continue
            row = row_match.iloc[0]
            sub = polygons[(polygons["country"] == country) & (polygons["disaster_type"] == disaster_type)]
            if row["skip_reason"] is None:
                _panel_tested(ax, country, disaster_type, row["term"], sub,
                               row["p_value"], row["n_finite_without_event"], row["n_finite_with_event"])
            else:
                _panel_skipped(ax, country, disaster_type, row["term"], sub, row["skip_reason"])

    figure_caption_footer(fig, list(axes.ravel()), CAPTION)
    out_path = save_figure(fig, OUT_DIR / "combined" / "emdat_spatial_validation.png")
    logger.info("EM-DAT spatial validation saved to %s", out_path)
    return out_path
