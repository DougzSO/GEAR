"""
Box/strip plot for the EM-DAT x Hazard spatial overlay validation (C6).

Draws ``src.index.emdat_validation.run_validation()``'s ``"polygons"``
table: one panel per (country, disaster_type) pair that was actually tested
(``skip_reason`` is null), the admin-1 zonal hazard value split by whether
that polygon had a geocoded EM-DAT event, with the Mann-Whitney U p-value
and group sizes annotated ON the panel. Never a single combined score
across countries/types.

Coverage/proxy caveats are printed in the figure's own footer, not only in
``src.index.emdat_validation``'s docstring -- Douglas's explicit
requirement (2026-09-04) that the limitations travel with the figure
itself.
"""

from __future__ import annotations

import logging
import pathlib

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
    "no matching Hazard term and is not tested. See "
    "src/index/emdat_validation.py for the full method and caveats."
)

_GROUP_COLORS = {"no event": "#cccccc", ">=1 event": "#d62728"}


def _panel(ax, country: str, disaster_type: str, term: str, polygons: pd.DataFrame,
           p_value: float, n_without: int, n_with: int) -> None:
    groups = [
        polygons.loc[~polygons["has_event"], "hazard_value"].dropna(),
        polygons.loc[polygons["has_event"], "hazard_value"].dropna(),
    ]
    labels = list(_GROUP_COLORS)
    bp = ax.boxplot(groups, tick_labels=labels, patch_artist=True, widths=0.5, showfliers=False)
    for patch, label in zip(bp["boxes"], labels):
        patch.set_facecolor(_GROUP_COLORS[label])
        patch.set_alpha(0.6)

    rng = np.random.default_rng(0)
    for i, g in enumerate(groups, start=1):
        jitter = rng.normal(0, 0.05, size=len(g))
        ax.scatter(np.full(len(g), i) + jitter, g, s=14, color="black", alpha=0.6, zorder=3)

    ax.set_title(f"{country}\n{disaster_type} -> {term}", fontweight="bold", fontsize=fs(9))
    p_text = f"Mann-Whitney U p={p_value:.3f}" if not np.isnan(p_value) else "p=n/a"
    ax.set_xlabel(f"{p_text} (n={n_without} / {n_with})", fontsize=fs(8))
    ax.set_ylabel(f"{term} raw raster, admin-1 zonal mean", fontsize=fs(8))


def plot_emdat_spatial_validation(
    countries: list[str] | None = None, result: dict[str, pd.DataFrame] | None = None,
) -> pathlib.Path:
    countries = countries or COUNTRIES
    result = result if result is not None else ev.run_validation(countries=countries)
    summary, polygons = result["summary"], result["polygons"]
    tested = summary[summary["skip_reason"].isna()].reset_index(drop=True)
    skipped = summary[summary["skip_reason"].notna()]

    n_panels = max(len(tested), 1)
    fig, axes = plt.subplots(1, n_panels, figsize=(4.2 * n_panels, 5.5), constrained_layout=True)
    axes = np.atleast_1d(axes)

    if len(tested) == 0:
        axes[0].text(
            0.5, 0.5,
            "No (country, disaster_type) pair had enough geocoded\nevents to test -- see the "
            "summary table for reasons.",
            ha="center", va="center", fontsize=fs(10), wrap=True, transform=axes[0].transAxes,
        )
        axes[0].axis("off")
    else:
        for ax, row in zip(axes, tested.itertuples(index=False)):
            sub = polygons[(polygons["country"] == row.country) & (polygons["disaster_type"] == row.disaster_type)]
            _panel(ax, row.country, row.disaster_type, row.term, sub,
                   row.p_value, row.n_finite_without_event, row.n_finite_with_event)

    caption = CAPTION
    if len(skipped):
        caption += " Skipped: " + "; ".join(
            f"{r.country}/{r.disaster_type} ({r.skip_reason})" for r in skipped.itertuples(index=False)
        )
    figure_caption_footer(fig, list(axes), caption)
    out_path = save_figure(fig, OUT_DIR / "combined" / "emdat_spatial_validation.png")
    logger.info("EM-DAT spatial validation saved to %s", out_path)
    return out_path
