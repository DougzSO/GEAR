"""
Generic plotting infrastructure shared by every CCRS figure -- boundary /
disputed-territory handling, dynamic per-country figsize, the
capacity-proportional marker-size convention, footer/legend positioning, and
the save (PNG+PDF, dpi=200) helper.

Reused directly from ``energy_risk_assessment/src/visualization/maps.py``
(old repo): the boundary/disputed-territory helpers
(``_load_admin1_boundaries``, ``_country_has_disputed_admin1``,
``_draw_country_boundary``, ``_footer_with_gadm_disclaimer``), the dynamic
figsize helpers (``_aspect_ratio_width``, ``_multi_panel_figsize``,
``_single_panel_figsize``), the marker-size convention (``_marker_sizes``,
sqrt-of-capacity), the style constants (``dpi=200``, ``bbox_inches="tight"``,
PNG+PDF saved together), and the footer-positioning helpers
(``_tight_bottom_fraction``, ``_footer_below_artist``,
``_footer_below_panels``, ``_legend_below_artists``). Only the plumbing that
depends on the old schema (``ADM_ADM_1`` boundary layer itself, GADM GID
convention, ``COUNTRIES``/``COUNTRY_ISO3``/``MAINLAND_ONLY_COUNTRIES``) was
re-pointed at ``GEAR_framework``'s own ``src.config``/
``src.downloaders.boundaries_downloader`` -- the logic is otherwise
unchanged, since both repos already share the exact same GADM 4.1 data and
the same disputed-territory finding (India's ``Z``-prefixed admin-1 GIDs:
Jammu & Kashmir, parts of Himachal Pradesh/Uttarakhand/Arunachal Pradesh).

--------------------------------------------------------------------------
Palette decision (reported per task, applied module-wide)
--------------------------------------------------------------------------
The old repo used ``RdBu_r`` for the one diverging map (scenario delta) and
``YlOrRd``/``PuBu``/``YlGnBu`` for sequential ones -- defensible but not
perceptually uniform. This module keeps ``RdBu_r`` for the diverging case
(already appropriate: a true zero-centered delta) and switches every
sequential/ordinal use (risk-band severity, capacity-share heatmaps, the
Top-N breakdown heatmap) to **viridis** -- perceptually uniform, monotonic
in lightness, colorblind-safe, and the de facto standard for sequential data
in scientific publication. Categorical/nominal data (technology bucket
identity: hydro/thermal/wind/solar, a NAME not an ORDER) is not a case
"perceptually uniform" applies to -- it keeps a fixed qualitative palette
(``BUCKET_COLORS``), analogous to the old repo's ``FUEL_BUCKET_COLORS`` but
with 4 buckets instead of 5 (the new schema folds every thermal fuel -- coal
included -- into one ``thermal`` bucket; there is no separate ``coal``
category to color).
"""

from __future__ import annotations

import pathlib
import textwrap

import geopandas as gpd
import matplotlib
import matplotlib.lines as mlines
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import BOUNDARIES_RAW, COUNTRIES, COUNTRY_ISO3, MAINLAND_ONLY_COUNTRIES
from src.downloaders.boundaries_downloader import get_country_bounds, get_country_geometry
from src.index.ccrs_calculator import BUCKETS

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------
SEQUENTIAL_CMAP = "viridis"
DIVERGING_CMAP = "RdBu_r"

# Categorical, nominal -- technology bucket identity (4 buckets: the new
# CCRS schema has no standalone "coal" category, unlike the old repo's
# 5-bucket FUEL_BUCKET_COLORS).
BUCKET_COLORS = {
    "hydro": "#1f77b4",
    "thermal": "#4d4d4d",
    "wind": "#17becf",
    "solar": "#ff9f1c",
}
assert set(BUCKET_COLORS) == set(BUCKETS)

NOT_COMPUTABLE_COLOR = "#7f7f7f"
NOT_COMPUTABLE_MARKER = "x"

# Ordinal band severity colors -- sampled from SEQUENTIAL_CMAP at evenly
# spaced points, one color per band label, low-to-high severity order.
WATER_BAND_ORDER = ("Low", "Low-Medium", "Medium-High", "High", "Extremely-High")
HEAT_BAND_ORDER = ("LOW", "MEDIUM", "HIGH", "EXTREME")


def _ordinal_band_colors(labels: tuple[str, ...]) -> dict[str, str]:
    cmap = matplotlib.colormaps[SEQUENTIAL_CMAP]
    return {label: cmap(i / max(1, len(labels) - 1)) for i, label in enumerate(labels)}


WATER_BAND_COLORS = _ordinal_band_colors(WATER_BAND_ORDER)
HEAT_BAND_COLORS = _ordinal_band_colors(HEAT_BAND_ORDER)

# --------------------------------------------------------------------------
# Style constants
# --------------------------------------------------------------------------
MAP_DPI = 200
MIN_MARKER_SIZE = 6
MAX_MARKER_SIZE = 240
BBOX_MARGIN_DEG = 1.0
NATIONAL_FACECOLOR = "#f5f5f0"
ADMIN1_LINE_COLOR = "#999999"
ADMIN1_LINE_WIDTH = 0.35

# --------------------------------------------------------------------------
# Fonts -- every figure text (axis labels, legends, annotations, footers) is
# 20% larger than the pre-review baseline (Douglas's review round,
# 2026-09-04). ``fs()`` scales any literal fontsize passed explicitly at a
# call site; ``plt.rcParams`` below raises the *default* sizes matplotlib
# applies where no explicit fontsize is passed (axis tick labels, unlabelled
# ax.set_xlabel/ax.set_ylabel calls).
# --------------------------------------------------------------------------
FONT_SCALE = 1.2


def fs(base: float) -> float:
    return round(base * FONT_SCALE, 1)


plt.rcParams.update({
    "font.size": fs(10),
    "axes.titlesize": fs(11),
    "axes.labelsize": fs(10),
    "xtick.labelsize": fs(9),
    "ytick.labelsize": fs(9),
    "legend.fontsize": fs(9),
    "figure.titlesize": fs(13),
})

TITLE_FONTWEIGHT = "bold"
DISPUTED_GID_PREFIX = "Z"
DISPUTED_LINE_COLOR = "#bbbbbb"
DISPUTED_LINE_STYLE = "--"
GADM_DISCLAIMER_TEXT = (
    "Administrative boundaries per GADM 4.1; boundary representation does not imply endorsement."
)


def marker_sizes(capacity_mw: pd.Series) -> np.ndarray:
    """sqrt-of-capacity marker area -- the standard bubble-map convention,
    avoids exaggerating large plants (linear radius scaling would)."""
    capacity = capacity_mw.fillna(0).clip(lower=0)
    if len(capacity) == 0 or capacity.max() <= 0:
        return np.full(len(capacity), MIN_MARKER_SIZE)
    scaled = np.sqrt(capacity / capacity.max())
    return (MIN_MARKER_SIZE + scaled * (MAX_MARKER_SIZE - MIN_MARKER_SIZE)).to_numpy()


def bucket_legend_handles():
    return [
        mlines.Line2D([0], [0], marker="o", color="w", markerfacecolor=color,
                      markeredgecolor="none", markersize=9, label=bucket)
        for bucket, color in BUCKET_COLORS.items()
    ]


def panel_title(ax, text: str, n_power_plants: int, n_excluded: int | None = None) -> None:
    """Bold text above a map panel -- ``Power Plants=N`` (never ``n=N``), plus
    ``excluded=M`` when the panel distinguishes computable-base membership.
    No figure in this module prints a title (``fig.suptitle``/figure-level
    caption text is a footer, see ``figure_caption_footer``) -- this is the
    per-panel label only (Douglas's 2026-09-04 review)."""
    label = f"{text} (Power Plants={n_power_plants:,}"
    if n_excluded is not None:
        label += f", excluded={n_excluded:,}"
    label += ")"
    ax.set_title(label, fontweight=TITLE_FONTWEIGHT, fontsize=fs(10))


def figure_caption_footer(fig, artists, caption: str, countries: list[str] | None = None) -> None:
    """Figure-level context (what the old code put in ``fig.suptitle``) is
    printed as a footer instead -- no figure carries a printed title
    (Douglas's 2026-09-04 review). Appends the GADM disclaimer, if any of
    ``countries`` has disputed admin-1 territory, onto the same footer line
    rather than a second one."""
    text = caption
    if countries:
        disclaimer = footer_with_gadm_disclaimer("", countries)
        if disclaimer:
            text = f"{text} — {disclaimer}" if text else disclaimer
    footer_below_panels(fig, artists, text)


def figure_caption_footer_single(fig, ax, caption: str, countries: list[str] | None = None) -> None:
    """Single-panel equivalent of ``figure_caption_footer``."""
    text = caption
    if countries:
        disclaimer = footer_with_gadm_disclaimer("", countries)
        if disclaimer:
            text = f"{text} — {disclaimer}" if text else disclaimer
    footer_below_artist(fig, ax, text)


def not_computable_legend_handle():
    return mlines.Line2D([0], [0], marker=NOT_COMPUTABLE_MARKER, color=NOT_COMPUTABLE_COLOR,
                          linestyle="None", markersize=8, markeredgewidth=1.5,
                          label="Excluded from the V6 computable base (no commissioning_year)")


# --------------------------------------------------------------------------
# Boundary / disputed-territory handling (reused pattern)
# --------------------------------------------------------------------------
_admin1_cache: dict[str, gpd.GeoDataFrame] = {}


def load_admin1_boundaries(country: str) -> gpd.GeoDataFrame:
    """``ADM_ADM_1`` layer of the GADM 4.1 geopackage already downloaded by
    ``boundaries_downloader.py``. Portugal (``MAINLAND_ONLY_COUNTRIES``) is
    clipped to the mainland geometry already used for the national boundary
    -- the Azores/Madeira districts are never drawn."""
    if country in _admin1_cache:
        return _admin1_cache[country]

    iso3 = COUNTRY_ISO3[country]
    gpkg_path = BOUNDARIES_RAW / "gadm" / f"gadm41_{iso3}.gpkg"
    if not gpkg_path.exists():
        raise FileNotFoundError(
            f"{gpkg_path} does not exist -- run "
            f"boundaries_downloader.download_country_boundary('{country}') first."
        )
    gdf = gpd.read_file(gpkg_path, layer="ADM_ADM_1")

    if country in MAINLAND_ONLY_COUNTRIES:
        mainland = gpd.GeoSeries([get_country_geometry(country)], crs="EPSG:4326")
        gdf = gpd.clip(gdf, mainland)

    _admin1_cache[country] = gdf
    return gdf


def country_has_disputed_admin1(country: str) -> bool:
    """True if ``country`` has at least one ``Z``-prefixed ``GID_1`` polygon
    (disputed territory in GADM's convention) -- only India, in this study."""
    admin1 = load_admin1_boundaries(country)
    return admin1["GID_1"].str.startswith(DISPUTED_GID_PREFIX).any()


def footer_with_gadm_disclaimer(text: str, countries: list[str]) -> str:
    """Appends ``GADM_DISCLAIMER_TEXT`` once (not per country/panel) if any
    of ``countries`` has disputed admin-1 territory. Empty ``text`` returns
    just the disclaimer, with no stray separator."""
    if not any(country_has_disputed_admin1(c) for c in countries):
        return text
    return f"{text} — {GADM_DISCLAIMER_TEXT}" if text else GADM_DISCLAIMER_TEXT


def draw_country_boundary(ax, country: str) -> None:
    """National boundary + admin-1 reference lines. Disputed admin-1
    polygons (India) are filled the SAME color as the rest of the country
    (never left unfilled -- would visually read as "excluded") with a
    dashed grey outline, visually distinct from ordinary state borders."""
    geom = get_country_geometry(country)
    gpd.GeoSeries([geom], crs="EPSG:4326").plot(
        ax=ax, facecolor=NATIONAL_FACECOLOR, edgecolor="black", linewidth=0.6, zorder=1
    )
    admin1 = load_admin1_boundaries(country)
    is_disputed = admin1["GID_1"].str.startswith(DISPUTED_GID_PREFIX)
    disputed, normal = admin1[is_disputed], admin1[~is_disputed]

    if len(disputed):
        disputed.plot(ax=ax, facecolor=NATIONAL_FACECOLOR, edgecolor="none", zorder=1.2)
        disputed.boundary.plot(
            ax=ax, color=DISPUTED_LINE_COLOR, linewidth=ADMIN1_LINE_WIDTH,
            linestyle=DISPUTED_LINE_STYLE, zorder=1.6,
        )
    normal.boundary.plot(ax=ax, color=ADMIN1_LINE_COLOR, linewidth=ADMIN1_LINE_WIDTH, zorder=1.5)

    xmin, ymin, xmax, ymax = get_country_bounds(country)
    ax.set_xlim(xmin - BBOX_MARGIN_DEG, xmax + BBOX_MARGIN_DEG)
    ax.set_ylim(ymin - BBOX_MARGIN_DEG, ymax + BBOX_MARGIN_DEG)
    ax.set_aspect("equal")


COMPASS_ROSE_SIZE = 0.11          # axes-fraction diameter -- small, proportional to the panel
COMPASS_ROSE_XY = (0.90, 0.88)    # axes-fraction center -- upper right of each map panel
COMPASS_ROSE_COLORS = ("black", "white")


def add_compass_rose(ax, xy: tuple[float, float] = COMPASS_ROSE_XY, size: float = COMPASS_ROSE_SIZE) -> None:
    """Small 4-point compass-rose star (N/E/S/W kite quadrilaterals,
    alternating black/white fill) in the upper-right corner of ``ax``, in
    axes-fraction coordinates so it always sits in the same visual corner
    regardless of the panel's data extent. A full compass-rose shape, not a
    single directional arrow (Douglas's 2026-09-05 review); only the ``N``
    point is labelled -- S/E/W are left unlabelled to avoid clutter at this
    size, the rose shape itself already reads as "north-up" orientation
    without needing every label. Called once per geographic map panel
    (every country panel gets its own, not one for the whole figure)."""
    cx, cy = xy
    r_tip = size / 2
    r_notch = r_tip * 0.32
    trans = ax.transAxes

    def _point(angle_deg: float, r: float) -> tuple[float, float]:
        rad = np.radians(angle_deg)
        return (cx + r * np.sin(rad), cy + r * np.cos(rad))

    cardinal_angles = (0, 90, 180, 270)  # N, E, S, W -- 0 = up, clockwise
    for i, angle in enumerate(cardinal_angles):
        left_notch = _point(angle - 45, r_notch)
        tip = _point(angle, r_tip)
        right_notch = _point(angle + 45, r_notch)
        kite = mpatches.Polygon(
            [(cx, cy), left_notch, tip, right_notch], closed=True,
            facecolor=COMPASS_ROSE_COLORS[i % 2], edgecolor="black", linewidth=0.5,
            transform=trans, zorder=10, clip_on=False,
        )
        ax.add_patch(kite)

    n_tip_x, n_tip_y = _point(0, r_tip)
    ax.text(n_tip_x, n_tip_y + r_tip * 0.35, "N", transform=trans, ha="center", va="bottom",
            fontsize=fs(7), fontweight="bold", zorder=11, clip_on=False)


# --------------------------------------------------------------------------
# Dynamic per-country figsize (reused pattern)
# --------------------------------------------------------------------------
def country_bbox_aspect(country: str) -> float:
    xmin, ymin, xmax, ymax = get_country_bounds(country)
    width_deg = (xmax - xmin) + 2 * BBOX_MARGIN_DEG
    height_deg = (ymax - ymin) + 2 * BBOX_MARGIN_DEG
    return width_deg / height_deg


def aspect_ratio_width(country: str, base_height: float,
                        min_width: float = 4.0, max_width: float = 14.0) -> float:
    """Panel width proportional to the country's real lon/lat bbox aspect
    ratio at a fixed ``base_height`` -- avoids the letterboxing a single
    fixed width per country produces for a country far from square (India
    wide, Portugal tall/narrow)."""
    aspect = country_bbox_aspect(country)
    return max(min_width, min(base_height * aspect, max_width))


SINGLE_PANEL_LEFT = 0.10
SINGLE_PANEL_RIGHT = 0.97


def single_panel_figsize(country: str, base_height: float = 7.0,
                          top: float = 0.90, bottom: float = 0.16,
                          left: float = SINGLE_PANEL_LEFT, right: float = SINGLE_PANEL_RIGHT) -> tuple[float, float]:
    """Figsize for a 1-panel (per-country) figure. Accounts for the axes
    box occupying only ``(right-left)`` x ``(top-bottom)`` of the figure
    (title/labels/colorbar margins) -- ``top``/``bottom``/``left``/``right``
    must match what the caller passes to ``fig.subplots_adjust``, or the
    rendered axes box ends up a different aspect than intended and
    ``ax.set_aspect("equal")`` fills the gap with blank space."""
    aspect = country_bbox_aspect(country)
    axes_frac_ratio = (right - left) / (top - bottom)
    width = base_height * aspect / axes_frac_ratio
    width = max(5.5, min(width, 14.0))
    return (width, base_height)


def multi_panel_figsize(countries: list[str], base_height: float = 9.0) -> tuple[tuple[float, float], list[float]]:
    """Figsize + ``width_ratios`` for a combined (side-by-side) figure --
    each panel gets its own country's aspect-ratio width, not an equal
    fraction of one fixed total width."""
    widths = [aspect_ratio_width(c, base_height) for c in countries]
    return (sum(widths), base_height), widths


# --------------------------------------------------------------------------
# Footer / legend positioning (reused pattern)
# --------------------------------------------------------------------------
FOOTER_FONTSIZE = fs(8.5)
_FOOTER_CHAR_WIDTH_IN = 0.063


def _wrap_footer_text(fig, text: str, anchor_x: float = 0.99, margin_x: float = 0.02) -> str:
    fig_width_in = fig.get_size_inches()[0]
    avail_in = fig_width_in * (anchor_x - margin_x)
    max_chars = max(25, int(avail_in / _FOOTER_CHAR_WIDTH_IN))
    return textwrap.fill(text, width=max_chars)


def _footer_at(fig, y: float, text: str) -> None:
    fig.text(0.99, y, _wrap_footer_text(fig, text), ha="right", va="top",
              fontsize=FOOTER_FONTSIZE, style="italic", color="#444444")


def tight_bottom_fraction(fig, artist) -> float:
    """Minimum Y (figure fraction) of ``artist``'s rendered bbox -- forces a
    draw first (real layout, not an estimate). Works for both ``Axes`` and
    ``Legend``."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    get_bbox = getattr(artist, "get_tightbbox", None) or artist.get_window_extent
    bbox_px = get_bbox(renderer)
    return bbox_px.transformed(fig.transFigure.inverted()).y0


def footer_below_artist(fig, artist, text: str) -> None:
    y = tight_bottom_fraction(fig, artist) - 0.015
    _footer_at(fig, y, text)


def footer_below_panels(fig, artists, text: str) -> None:
    y = min(tight_bottom_fraction(fig, a) for a in artists) - 0.02
    _footer_at(fig, y, text)


def legend_below_artists(fig, artists, handles, margin: float = 0.015, **legend_kwargs):
    y = min(tight_bottom_fraction(fig, a) for a in artists) - margin
    return fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, y), **legend_kwargs)


# --------------------------------------------------------------------------
# Save (PNG in the output dir, PDF isolated in a "pdf/" subfolder -- Douglas's
# 2026-09-04 review: every output directory keeps PNGs alongside a /pdf/
# subfolder holding only the PDFs, instead of interleaving both formats)
# --------------------------------------------------------------------------
def pdf_path_for(out_path: pathlib.Path) -> pathlib.Path:
    return out_path.parent / "pdf" / out_path.with_suffix(".pdf").name


def save_figure(fig, out_path: pathlib.Path) -> pathlib.Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=MAP_DPI, bbox_inches="tight")
    pdf_path = pdf_path_for(out_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(pdf_path, bbox_inches="tight")
    plt.close(fig)
    return out_path
