"""
CCRS non-geospatial figures -- categories 5 (WaterRiskBand x HeatRiskBand
contingency heatmap), 6 (CCRS distribution by bucket), 7 (age_factor by
bucket), 8 (capacity by risk band, stacked bars), 9 (EventMultiplier by
country), 11 (Top-N CCRS breakdown heatmap, bonus category).

Reused from the old repo (adapted, see ``_common.py``'s module docstring
for the palette decision): the per-column-normalized-for-color /
real-value-annotated matrix technique of
``maps._draw_sci_component_heatmap_panel`` (category 5's contingency matrix
and category 11's Top-N breakdown both use it, ``YlOrRd`` -> ``viridis``),
and the overlaid-step-histogram small-multiple technique of
``sensitivity_analysis.plot_resilience_norm_distribution_by_bucket``
(category 6, ``resilience_norm`` swapped for ``ccrs_{gcm}``). Categories 7,
8, 9 have no direct precedent in the old repo (new figure types for the new
schema) but reuse the shared bucket palette and dpi=200/PNG+PDF style.
"""

from __future__ import annotations

import logging
import pathlib

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import COUNTRIES, OUTPUT_MAPS
from src.index.ccrs_calculator import BUCKETS
from src.index.risk_bands import HEAT_RISK_BANDS, PRIMARY_GCM, WATER_RISK_BANDS
from src.index import risk_bands as rb
from src.visualization import data as vdata
from src.visualization._common import BUCKET_COLORS, SEQUENTIAL_CMAP, save_figure

logger = logging.getLogger(__name__)

OUT_DIR = OUTPUT_MAPS  # figures from this module are saved alongside the maps


# --------------------------------------------------------------------------
# Category 5 -- WaterRiskBand x HeatRiskBand contingency heatmap
# --------------------------------------------------------------------------
def _draw_matrix_panel(ax, cell_values: np.ndarray, row_labels, col_labels, title: str,
                        annotate_fmt: str = "{:,.0f}") -> None:
    """Per-column-normalized-for-color, real-value-annotated matrix --
    reused technique from the old repo's
    ``_draw_sci_component_heatmap_panel``."""
    col_min = cell_values.min(axis=0)
    col_max = cell_values.max(axis=0)
    col_range = np.where(col_max > col_min, col_max - col_min, 1.0)
    normalized = (cell_values - col_min) / col_range

    ax.imshow(normalized, aspect="auto", cmap=SEQUENTIAL_CMAP, vmin=0, vmax=1)
    for i in range(cell_values.shape[0]):
        for j in range(cell_values.shape[1]):
            ax.text(j, i, annotate_fmt.format(cell_values[i, j]), ha="center", va="center",
                     fontsize=9, color="white" if normalized[i, j] > 0.5 else "black")
    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, fontsize=9)
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=9)
    ax.set_title(title, fontsize=11)


def plot_contingency_heatmap(
    countries: list[str] | None = None, gcm: str = PRIMARY_GCM,
    bands: dict | None = None, combined: bool = False,
) -> dict[str, pathlib.Path]:
    countries = countries or COUNTRIES
    bands = bands if bands is not None else vdata.load_band_tables()
    frame = bands[gcm].frame
    stem = f"water_heat_contingency_{gcm}"

    if combined:
        tab = rb.contingency_table(frame, "capacity_mw")
        fig, ax = plt.subplots(figsize=(8, 6))
        _draw_matrix_panel(ax, tab.to_numpy(), WATER_RISK_BANDS, HEAT_RISK_BANDS,
                            "All countries pooled", annotate_fmt="{:,.0f} MW")
        ax.set_xlabel("HeatRiskBand")
        ax.set_ylabel("WaterRiskBand")
        fig.suptitle(f"WaterRiskBand x HeatRiskBand capacity contingency ({gcm})")
        out_path = save_figure(fig, OUT_DIR / "combined" / f"{stem}.png")
        logger.info("%s (combined) saved to %s", stem, out_path)
        return {"combined": out_path}

    paths = {}
    for country in countries:
        tab = rb.contingency_table(frame[frame["country"] == country], "capacity_mw")
        fig, ax = plt.subplots(figsize=(8, 6))
        _draw_matrix_panel(ax, tab.to_numpy(), WATER_RISK_BANDS, HEAT_RISK_BANDS,
                            country, annotate_fmt="{:,.0f} MW")
        ax.set_xlabel("HeatRiskBand")
        ax.set_ylabel("WaterRiskBand")
        fig.suptitle(f"WaterRiskBand x HeatRiskBand capacity contingency ({gcm}) -- {country}")
        out_path = save_figure(fig, OUT_DIR / country / f"{stem}.png")
        paths[country] = out_path
        logger.info("%s (%s) saved to %s", stem, country, out_path)
    return paths


# --------------------------------------------------------------------------
# Category 6 -- CCRS distribution by fuel_type_bucket
# --------------------------------------------------------------------------
def plot_ccrs_distribution_by_bucket(
    countries: list[str] | None = None, gcm: str = PRIMARY_GCM, water_scenario: str = "bau",
    final: pd.DataFrame | None = None,
) -> pathlib.Path:
    """Small multiple (1 panel/country), overlaid step-histograms per
    bucket -- reused pattern from
    ``plot_resilience_norm_distribution_by_bucket``, ``resilience_norm``
    swapped for ``ccrs_{gcm}``. Combined only (small multiple already
    covers every country in one figure)."""
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
        ax.set_title(country, fontsize=13)
        ax.set_xlabel(f"{col} ({water_scenario})", fontsize=10)
        ax.legend(fontsize=8, loc="upper right")
    axes[0].set_ylabel("Density", fontsize=10)

    fig.suptitle(f"CCRS distribution by technology bucket ({gcm}, {water_scenario})", fontsize=13)
    fig.tight_layout()
    out_path = save_figure(fig, OUT_DIR / "combined" / f"ccrs_distribution_by_bucket_{gcm}_{water_scenario}.png")
    logger.info("CCRS distribution by bucket saved to %s", out_path)
    return out_path


# --------------------------------------------------------------------------
# Category 7 -- age_factor by bucket/technology
# --------------------------------------------------------------------------
def plot_age_factor_by_bucket(
    countries: list[str] | None = None, age_factors: pd.DataFrame | None = None,
) -> pathlib.Path:
    """Box plot of ``age_factor`` per bucket x country, with the
    missing-``commissioning_year`` (neutralized) share annotated per box --
    new figure, no direct old-repo precedent (the old ``age`` sub-factor was
    never shown standalone, only inside a product). Reuses the bucket color
    palette. Combined only."""
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
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("age_factor (>= 1, 2050 horizon)")
    ax.axhline(1.0, color="black", linewidth=0.6, linestyle=":")
    fig.suptitle("age_factor distribution by technology bucket and country")
    fig.tight_layout()
    out_path = save_figure(fig, OUT_DIR / "combined" / "age_factor_by_bucket.png")
    logger.info("age_factor by bucket saved to %s", out_path)
    return out_path


# --------------------------------------------------------------------------
# Category 8 -- per-country capacity share by risk band
# --------------------------------------------------------------------------
def _stacked_bar(ax, shares: pd.DataFrame, group_cols: list[str], band_col: str,
                  band_order, band_colors: dict) -> None:
    groups = shares[group_cols].drop_duplicates()
    groups = groups.sort_values(group_cols)
    x_labels = [" / ".join(str(v) for v in row) for row in groups.itertuples(index=False)]
    x = np.arange(len(groups))
    bottom = np.zeros(len(groups))
    for band in band_order:
        heights = []
        for _, row in groups.iterrows():
            mask = np.all([shares[c] == row[c] for c in group_cols], axis=0)
            cell = shares[mask & (shares[band_col] == band)]
            heights.append(float(cell["capacity_share"].iloc[0]) if len(cell) else 0.0)
        heights = np.array(heights)
        ax.bar(x, heights, bottom=bottom, color=band_colors.get(band, "#cccccc"), label=str(band))
        bottom += heights
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Capacity share")
    ax.set_ylim(0, 1.05)


def plot_capacity_by_risk_band(
    water_shares: pd.DataFrame | None = None, heat_shares: pd.DataFrame | None = None,
) -> pathlib.Path:
    """Stacked bar, % V6-computable-base capacity per WaterRiskBand (left)
    and HeatRiskBand (right, GFDL-ESM4 primary only -- MIROC6 is its own
    row in ``heat_shares``, plotted separately if requested), country x
    scenario. New figure -- the natural headline-result chart, no old-repo
    precedent in this exact form. Combined only."""
    from src.visualization._common import WATER_BAND_COLORS, HEAT_BAND_COLORS

    water_shares = water_shares if water_shares is not None else vdata.load_water_band_shares()
    heat_shares = heat_shares if heat_shares is not None else vdata.load_heat_band_shares()
    heat_primary = heat_shares[heat_shares["gcm"] == PRIMARY_GCM]

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    _stacked_bar(axes[0], water_shares, ["country", "water_scenario"], "band",
                 WATER_RISK_BANDS + ("NO_BAND",),
                 {**WATER_BAND_COLORS, "NO_BAND": "#e0e0e0"})
    axes[0].set_title("WaterRiskBand")
    axes[0].legend(fontsize=7, loc="upper right", ncol=2)

    _stacked_bar(axes[1], heat_primary, ["country", "heat_scenario"], "band",
                 HEAT_RISK_BANDS + ("NO_BAND",),
                 {**HEAT_BAND_COLORS, "NO_BAND": "#e0e0e0"})
    axes[1].set_title(f"HeatRiskBand ({PRIMARY_GCM}, primary)")
    axes[1].legend(fontsize=7, loc="upper right", ncol=2)

    fig.suptitle("V6-computable-base capacity share by risk band, country x scenario")
    fig.tight_layout()
    out_path = save_figure(fig, OUT_DIR / "combined" / "capacity_by_risk_band.png")
    logger.info("Capacity by risk band saved to %s", out_path)
    return out_path


# --------------------------------------------------------------------------
# Category 9 -- EventMultiplier by country
# --------------------------------------------------------------------------
def plot_event_multiplier_by_country(
    countries: list[str] | None = None, event_multipliers: pd.DataFrame | None = None,
) -> pathlib.Path:
    """Trivial 3-bar chart, ``EventMultiplier_c`` per country with
    ``N_events``/``rate`` annotated -- no precedent needed. Combined only."""
    countries = countries or COUNTRIES
    em = event_multipliers if event_multipliers is not None else vdata.load_event_multipliers()
    em = em.set_index("country").reindex(countries).reset_index()

    fig, ax = plt.subplots(figsize=(5, 4))
    bars = ax.bar(em["country"], em["event_multiplier"], color="#4d4d4d")
    for bar, (_, row) in zip(bars, em.iterrows()):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                f"N={row['n_events']:.0f}\nrate={row['rate']:.3f}/yr", ha="center", va="bottom", fontsize=8)
    ax.axhline(1.0, color="black", linewidth=0.6, linestyle=":")
    ax.set_ylabel("EventMultiplier_c")
    fig.suptitle("EventMultiplier by country (EM-DAT event frequency)")
    fig.tight_layout()
    out_path = save_figure(fig, OUT_DIR / "combined" / "event_multiplier_by_country.png")
    logger.info("EventMultiplier by country saved to %s", out_path)
    return out_path


# --------------------------------------------------------------------------
# Category 11 (bonus) -- Top-N CCRS breakdown heatmap
# --------------------------------------------------------------------------
def plot_top_n_ccrs_breakdown(
    gcm: str = PRIMARY_GCM, n: int = 10, final: pd.DataFrame | None = None,
) -> pathlib.Path:
    """Rows = Top-N plants by ``ccrs_{gcm}``, columns = the three
    multiplicative factors (``hazard_{gcm}``, ``age_factor``,
    ``event_multiplier``) -- same rendering technique as category 5
    (``_draw_matrix_panel``), same per-column-normalized-for-color /
    real-value-in-cell convention. Answers "why is this plant ranked where
    it is", which no other category covers. Combined only."""
    final = final if final is not None else vdata.load_ccrs_final()
    top = vdata.top_n_by_ccrs(final, gcm=gcm, n=n)
    cols = [f"hazard_{gcm}", "age_factor", "event_multiplier"]

    fig, ax = plt.subplots(figsize=(8, 0.55 * len(top) + 2))
    _draw_matrix_panel(ax, top[cols].to_numpy(),
                        [f"{name[:28]} ({country}, {bucket})"
                         for name, country, bucket in zip(top["plant_name"], top["country"], top["bucket"])],
                        ["Hazard", "age_factor", "EventMultiplier"],
                        f"Top-{n} plants by CCRS ({gcm}) -- factor breakdown", annotate_fmt="{:.3f}")
    fig.tight_layout()
    out_path = save_figure(fig, OUT_DIR / "combined" / f"top{n}_ccrs_breakdown_{gcm}.png")
    logger.info("Top-%d CCRS breakdown heatmap saved to %s", n, out_path)
    return out_path
