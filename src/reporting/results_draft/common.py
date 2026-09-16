"""
Shared constants, real-data loaders, and the manifest writer for every
``results_draft`` item module. No item module re-derives a scenario label,
band order, or hazard/bucket mapping independently of this file -- see
``docs/rework/GEAR_v3_RESULTS_DRAFT.md`` item-to-source mapping (2026-09-15
mapping pass) for why each constant/loader here is the correct real-data
source, not an approximation.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import BOUNDARIES_RAW, COUNTRIES, COUNTRY_ISO3, MAINLAND_ONLY_COUNTRIES, OUTPUT_RESULTS_DRAFT, OUTPUT_TABLES
from src.downloaders.boundaries_downloader import get_country_bounds, get_country_geometry

# --------------------------------------------------------------------------
# Scenario / band / hazard vocabulary -- src/config.py AQUEDUCT_SCENARIO_LABELS
# is the source of truth for the opt/bau/pes <-> SSP label mapping; repeated
# here as a plain dict (not re-imported) because config.py's dict is keyed the
# other direction (SSP-string -> aqueduct-label) for the processor layer.
# --------------------------------------------------------------------------
SSP_ORDER = ["opt", "bau", "pes"]  # SSP1-2.6 -> SSP3-7.0 -> SSP5-8.5, RESULTS_DRAFT's own axis order
SSP_LABEL = {"opt": "SSP1-2.6", "bau": "SSP3-7.0", "pes": "SSP5-8.5"}
SSP_SLUG = {"opt": "ssp126", "bau": "ssp370", "pes": "ssp585"}  # maps/ subfolder names
BAND_ORDER = ["Low", "Medium", "High", "Extreme"]
PSAE_LABELS = ["LOW", "MEDIUM", "HIGH", "EXTREME"]

HAZARD_LABEL = {
    "ws": "Water Stress", "spei": "Drought (SPEI)", "precip": "Extreme Precipitation",
    "sv": "Water Seasonal Variability", "iv": "Water Interannual Variability",
    "heat": "Extreme Heat", "wind": "Extreme Wind",
}
BUCKET_HAZARDS = {
    "hydro": ["ws", "spei", "precip", "sv", "iv"],
    "thermal": ["ws", "heat", "precip"],
    "wind": ["wind"],
    "solar": ["heat", "precip", "wind"],
}
BUCKET_LABEL = {"hydro": "Hydro", "thermal": "Thermal", "wind": "Wind", "solar": "Solar"}
BUCKET_ORDER = ["hydro", "thermal", "solar", "wind"]
BUCKET_MARKER = {"hydro": "o", "thermal": "s", "solar": "^", "wind": "D"}

SEQUENTIAL_CMAP = "viridis"  # matches src.visualization._common's own palette choice


def _ordinal_band_colors(labels: list[str]) -> dict[str, str]:
    """Sample SEQUENTIAL_CMAP at evenly spaced points, low-to-high severity --
    identical convention to src.visualization._common._ordinal_band_colors
    (docs/_audit/2026-09-15_phase7_legacy_maps_audit.md Section 3: the legacy
    pipeline used a perceptually-uniform sequential palette for every ordinal
    band, never a hand-picked qualitative one)."""
    import matplotlib
    cmap = matplotlib.colormaps[SEQUENTIAL_CMAP]
    return {label: cmap(i / max(1, len(labels) - 1)) for i, label in enumerate(labels)}


BAND_COLOR = _ordinal_band_colors(BAND_ORDER)  # Low/Medium/High/Extreme, viridis-ordinal
PSAE_COLOR = _ordinal_band_colors(PSAE_LABELS)  # LOW/MEDIUM/HIGH/EXTREME, viridis-ordinal

TABLES = OUTPUT_TABLES  # data/outputs/tables -- real, already-computed production CSVs/JSON


# --------------------------------------------------------------------------
# Real-data loaders. Every function reads a file already listed in the
# 2026-09-15 output-folder audit (docs/_audit/2026-09-15_output_folder_audit_prestep.md)
# -- no synthetic/example data anywhere in this package.
# --------------------------------------------------------------------------
def load_inventory() -> pd.DataFrame:
    """One row per plant_uid -- capacity_mw, country, bucket, age_factor.
    Source: ccrs_age_factors.csv (T2 output, already deduplicated per plant)."""
    df = pd.read_csv(TABLES / "ccrs_age_factors.csv")
    assert df["plant_uid"].is_unique, "ccrs_age_factors.csv is expected one-row-per-plant"
    return df


def load_coords() -> pd.DataFrame:
    """plant_uid -> lat/lon, deduplicated from risk_by_hazard.csv (one row per
    plant x water_scenario x hazard_term; lat/lon is constant per plant)."""
    df = pd.read_csv(TABLES / "risk_by_hazard.csv", usecols=["plant_uid", "lat", "lon"])
    return df.drop_duplicates("plant_uid").set_index("plant_uid")[["lat", "lon"]]


def load_risk_bands(capacity: pd.Series | None = None) -> pd.DataFrame:
    """Per plant x water_scenario x hazard_term RiskBand_i,h. Source:
    risk_bands.csv (T4, primary GCM GFDL-ESM4, 88,116 rows). ``capacity``
    (plant_uid -> capacity_mw, from load_inventory()) is merged in if given --
    risk_bands.csv itself carries no capacity_mw column."""
    df = pd.read_csv(TABLES / "risk_bands.csv")
    if capacity is not None:
        df["capacity_mw"] = df["plant_uid"].map(capacity)
    return df


def load_psae(capacity: pd.Series | None = None) -> pd.DataFrame:
    """Per plant x water_scenario PSAE_i, grouped by bucket. Source: psae.csv
    (``python -m src.index.psae``, Phase 4, Eq. 2) -- not persisted by
    src/main.py's pipeline run; regenerated once for this package via
    ``python -m src.index.psae`` before any item module here reads it (see
    docs/DECISIONS.md, "GEAR v3 results_draft: psae.csv materialized")."""
    path = TABLES / "psae.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist -- run `python -m src.index.psae` first "
            f"(src/main.py's pipeline does not persist this file)."
        )
    df = pd.read_csv(path)
    if capacity is not None:
        df["capacity_mw"] = df["plant_uid"].map(capacity)
    return df


def load_risk_by_hazard() -> pd.DataFrame:
    """Per plant x water_scenario x hazard_term Risk_i,h (Eq. 1). Source:
    risk_by_hazard.csv (already carries capacity_mw, lat/lon, age_factor)."""
    return pd.read_csv(TABLES / "risk_by_hazard.csv")


def load_correlation_gate() -> pd.DataFrame:
    return pd.read_csv(TABLES / "correlation_gate.csv")


def load_contextual_validators() -> pd.DataFrame:
    return pd.read_csv(TABLES / "contextual_validators.csv")


def load_normalization_origin() -> pd.DataFrame:
    return pd.read_csv(TABLES / "normalization_origin_table.csv")


def load_sobol() -> dict:
    with open(TABLES / "phase6_sobol_full_n1024.json") as f:
        return json.load(f)


def load_general_mc_convergence() -> dict:
    with open(TABLES / "phase6_general_mc_convergence.json") as f:
        return json.load(f)


# --------------------------------------------------------------------------
# Map plotting helpers -- ADM0+ADM1 boundary, disputed-territory dashed
# treatment, compass rose, capacity-weighted markers, panel titles.
#
# Reconstructed from src/visualization/_common.py's own logic (draw_country_
# boundary, load_admin1_boundaries, country_has_disputed_admin1, add_compass_
# rose, panel_title -- docs/_audit/2026-09-15_phase7_legacy_maps_audit.md
# Section 2), NOT by importing that module: as of 2026-09-15, _common.py (and
# everything importing it -- src/main.py, monte_carlo.py, emdat_validation.py,
# charts.py, data.py, maps.py, tables.py) raises ``ModuleNotFoundError: No
# module named 'src.index.ccrs_calculator'`` (renamed to risk_calculator.py,
# 8 real import statements never updated -- pre-existing, out of this
# package's scope to fix). The specific functions reused below never touched
# ccrs_calculator in the first place -- confirmed by reading _common.py
# directly -- so reimplementing them here (same geometry, same GADM layer,
# same disputed-GID convention) carries zero risk of diverging from what a
# fixed _common.py would draw.
#
# Disclaimer decision (author-confirmed, 2026-09-06, see maps.py's own
# "Correction 2" docstring and the audit above): the dashed disputed-
# territory outline stays; the GADM text disclaimer in the figure footer
# does NOT come back. No footer/disclaimer function exists in this module by
# design -- not an oversight.
# --------------------------------------------------------------------------
_admin1_cache: dict[str, gpd.GeoDataFrame] = {}
MAP_MARGIN_DEG = 1.0
DISPUTED_GID_PREFIX = "Z"
DISPUTED_LINE_COLOR = "#bbbbbb"
DISPUTED_LINE_STYLE = "--"
ADMIN1_LINE_COLOR = "#999999"
ADMIN1_LINE_WIDTH = 0.35
NATIONAL_FACECOLOR = "#f5f5f0"


def load_admin1_boundaries(country: str) -> gpd.GeoDataFrame:
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
    admin1 = load_admin1_boundaries(country)
    return admin1["GID_1"].str.startswith(DISPUTED_GID_PREFIX).any()


def draw_country_boundary(ax, country: str) -> None:
    """ADM0 national outline + ADM1 state boundaries; disputed ADM1 polygons
    (India: Jammu & Kashmir, parts of Himachal Pradesh/Uttarakhand/Arunachal
    Pradesh -- GID_1 prefixed "Z") get the SAME fill as the rest of the
    country (never left empty) with a dashed grey outline, visually distinct
    from ordinary state borders. Applied uniformly to every country, every
    call -- not a per-figure special case for India; India simply has
    disputed admin-1 territory and every other study country does not."""
    geom = get_country_geometry(country)
    gpd.GeoSeries([geom], crs="EPSG:4326").plot(
        ax=ax, facecolor=NATIONAL_FACECOLOR, edgecolor="black", linewidth=0.6, zorder=1
    )
    admin1 = load_admin1_boundaries(country)
    is_disputed = admin1["GID_1"].str.startswith(DISPUTED_GID_PREFIX)
    disputed, normal = admin1[is_disputed], admin1[~is_disputed]
    if len(disputed):
        disputed.plot(ax=ax, facecolor=NATIONAL_FACECOLOR, edgecolor="none", zorder=1.2)
        disputed.boundary.plot(ax=ax, color=DISPUTED_LINE_COLOR, linewidth=ADMIN1_LINE_WIDTH,
                                linestyle=DISPUTED_LINE_STYLE, zorder=1.6)
    normal.boundary.plot(ax=ax, color=ADMIN1_LINE_COLOR, linewidth=ADMIN1_LINE_WIDTH, zorder=1.5)

    xmin, ymin, xmax, ymax = get_country_bounds(country)
    ax.set_xlim(xmin - MAP_MARGIN_DEG, xmax + MAP_MARGIN_DEG)
    ax.set_ylim(ymin - MAP_MARGIN_DEG, ymax + MAP_MARGIN_DEG)
    ax.set_aspect("equal")
    ax.set_xlabel("Longitude", fontsize=9.6)  # MAP_TEXT_SCALE (1.2x) applied throughout this module
    ax.set_ylabel("Latitude", fontsize=9.6)
    ax.tick_params(labelsize=7.2)


MAP_TEXT_SCALE = 1.2  # 2026-09-16: all map text/markers 20% larger than the previous pass, proportions
                       # kept -- every fontsize/markersize constant below is the old value x 1.2.


def panel_title(ax, text: str, n_power_plants: int, fontsize: float = 10.8) -> None:
    """Bold "<text> (Power Plants=N)" -- "Power Plants=N", never "n=N", per
    Douglas's 2026-09-04 review (docs/_audit/2026-09-15_phase7_legacy_maps_audit.md
    Section 3, matching src.visualization._common.panel_title's own convention)."""
    ax.set_title(f"{text} (Power Plants={n_power_plants:,})", fontweight="bold", fontsize=fontsize)


COMPASS_ROSE_SIZE_IN = 0.36  # fixed physical size, matching the legacy src.visualization._common
                              # convention -- NOT a fraction of each panel's own size. A rose sized
                              # relative to its own panel looks the same regardless of how big the
                              # panel actually is; a fixed physical size is what makes it look
                              # correctly small once panels grow (2026-09-16 regression: a
                              # panel-relative rose became oversized when panels were undersized,
                              # masking the real problem -- panels are now restored to the legacy
                              # base_height=8in, single-file column layout, see make_country_row_figure).
COMPASS_ROSE_MARGIN = 0.035  # axes-fraction padding kept clear from every edge, incl. the "N" label
COMPASS_ROSE_COLORS = ("black", "white")
COMPASS_ROSE_POINTS = 8


def add_compass_rose(ax, size_in: float = COMPASS_ROSE_SIZE_IN,
                      margin: float = COMPASS_ROSE_MARGIN, redraw: bool = True) -> None:
    """8-point star, upper right, fixed physical size (legacy-matching).
    Position is solved from its own radius so the full glyph -- including
    the "N" label above the north tip -- always lands inside
    [margin, 1-margin] on both axes; combined with ``clip_on=True`` this
    guarantees it never spills past the axis limits, and a translucent
    white backing disc keeps it legible over whatever map data happens to
    sit in that corner (both improvements over the legacy version, which
    relied on ``clip_on=False`` and no backing).

    Call LAST, after any shared legend/colorbar has already been added --
    see the identical caveat in src.visualization._common.add_compass_rose's
    own docstring (reading ax.get_window_extent() before the figure's final
    layout settles produces an inconsistent size across panels).
    ``redraw=False`` skips the per-call ``fig.canvas.draw()`` -- safe when
    the caller already drew the canvas once before looping over many panels
    (the rose itself never changes any axes' bbox), avoiding an O(n^2)
    redraw cost on multi-panel grids."""
    import matplotlib.patches as mpatches
    fig = ax.figure
    if redraw:
        fig.canvas.draw()
    bbox = ax.get_window_extent()
    dpi = fig.dpi
    ax_w_in, ax_h_in = bbox.width / dpi, bbox.height / dpi
    r_tip_x = (size_in / 2) / ax_w_in if ax_w_in > 0 else size_in / 2
    r_tip_y = (size_in / 2) / ax_h_in if ax_h_in > 0 else size_in / 2
    r_notch_x, r_notch_y = r_tip_x * 0.32, r_tip_y * 0.32
    label_y_extent = r_tip_y * 0.45 + 0.05  # room for the "N" text above the north tip
    cx = 1 - margin - r_tip_x
    cy = 1 - margin - r_tip_y - label_y_extent
    trans = ax.transAxes

    def _point(angle_deg, rx, ry):
        rad = np.radians(angle_deg)
        return (cx + rx * np.sin(rad), cy + ry * np.cos(rad))

    backing = mpatches.Ellipse((cx, cy), width=2 * r_tip_x * 1.35, height=2 * r_tip_y * 1.35,
                                facecolor="white", edgecolor="none", alpha=0.72,
                                transform=trans, zorder=9, clip_on=True)
    ax.add_patch(backing)

    step = 360 / COMPASS_ROSE_POINTS
    for i in range(COMPASS_ROSE_POINTS):
        angle = i * step
        left_notch = _point(angle - step / 2, r_notch_x, r_notch_y)
        tip = _point(angle, r_tip_x, r_tip_y)
        right_notch = _point(angle + step / 2, r_notch_x, r_notch_y)
        kite = mpatches.Polygon(
            [(cx, cy), left_notch, tip, right_notch], closed=True,
            facecolor=COMPASS_ROSE_COLORS[i % 2], edgecolor="black", linewidth=0.4,
            transform=trans, zorder=10, clip_on=True,
        )
        ax.add_patch(kite)
    n_tip_x, n_tip_y = _point(0, r_tip_x, r_tip_y)
    ax.text(n_tip_x, n_tip_y + r_tip_y * 0.45, "N", transform=trans, ha="center", va="bottom",
            fontsize=7.2, fontweight="bold", zorder=11, clip_on=True)


def aspect_ratio_width(country: str, base_height: float, min_width: float = 4.0, max_width: float = 14.0) -> float:
    xmin, ymin, xmax, ymax = get_country_bounds(country)
    width_deg = (xmax - xmin) + 2 * MAP_MARGIN_DEG
    height_deg = (ymax - ymin) + 2 * MAP_MARGIN_DEG
    return max(min_width, min(base_height * width_deg / height_deg, max_width))


ROW_FIGURE_BASE_HEIGHT = 8.0  # matches the legacy src.visualization.maps._render_country_row_figure
                               # base_height -- the 2026-09-16 rework's own 5.0in undersized every
                               # 3-panel map relative to that reference, leaving excess whitespace.


def make_country_row_figure(countries: list[str], base_height: float = ROW_FIGURE_BASE_HEIGHT):
    """1 row x len(countries) columns, panel widths proportional to each
    country's own lon/lat aspect ratio (``aspect_ratio_width``), maps filling
    as much of the figure as possible. ``constrained_layout=True`` (not
    ``tight_layout``/manual ``subplots_adjust``) -- the same choice the
    legacy row-figure helper made, and the only one of the three that
    correctly reserves space for both a colorbar and a suptitle without
    per-caller tuning. Returns (fig, axes) with axes as a flat list."""
    widths = [aspect_ratio_width(country, base_height) for country in countries]
    fig, axes = plt.subplots(1, len(countries), figsize=(sum(widths), base_height),
                              gridspec_kw={"width_ratios": widths}, constrained_layout=True)
    axes = np.atleast_1d(axes).ravel().tolist()
    return fig, axes


def _tight_bottom_fraction(fig, ax) -> float:
    fig.canvas.draw()
    bbox = ax.get_tightbbox(fig.canvas.get_renderer())
    return fig.transFigure.inverted().transform(bbox.min)[1]


def legend_below_axes(fig, axes: list, handles: list, ncol: int | None = None,
                       fontsize: float = 9.6, margin: float = 0.02):
    """Places a single figure-level legend just below the real (rendered)
    bottom edge of every panel, not a hand-tuned ``bbox_to_anchor`` guess --
    matches the legacy ``legend_below_artists`` convention. Safe to combine
    with ``constrained_layout``: the legend is added after layout has
    already settled the axes, and ``save_figure``'s ``bbox_inches="tight"``
    grows the saved canvas to include it, so no space needs to be
    pre-reserved for it in the figure itself."""
    y = min(_tight_bottom_fraction(fig, ax) for ax in axes) - margin
    return fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, y),
                       ncol=ncol or len(handles), fontsize=fontsize, frameon=False)


MARKER_ALPHA = 0.75  # dense country panels (up to ~10k plants) still need some transparency to keep
                      # the base map legible even at legacy-scale marker sizes and panel widths


def marker_sizes(capacity_mw: pd.Series, min_size: float = 6, max_size: float = 168,
                  capacity_max: float | None = None) -> np.ndarray:
    """Area-proportional marker size (sqrt-scaled capacity). ``capacity_max``
    should be the dataset-wide (whole-figure, not per-panel) max capacity so
    that markers stay comparable across the 3 country panels of the same
    figure -- a panel with only small plants must not get artificially
    inflated markers just because it lacks that figure's largest plant."""
    capacity = capacity_mw.fillna(0).clip(lower=0)
    cap_max = capacity_max if capacity_max is not None else capacity.max()
    if len(capacity) == 0 or cap_max is None or cap_max <= 0:
        return np.full(len(capacity), min_size)
    scaled = np.sqrt(capacity / cap_max)
    return (min_size + scaled * (max_size - min_size)).to_numpy()


def save_figure(fig, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------
# Output tree + manifest -- 2026-09-16 flattened to 3 top-level folders:
#   results_draft/tables/          every CSV, no subfolders
#   results_draft/maps/ssp{126,370,585}/   every SSP-scenario-specific map
#   results_draft/maps/other/      maps with no scenario axis (e.g. the
#                                   Extreme Wind SSP-invariant map)
#   results_draft/other/           every generated figure that is neither a
#                                   table nor a country-panel map (bar
#                                   charts, heatmaps, convergence diagnostics)
# Confirmed 2026-09-16: no script outside this package references the old
# per-item ``NN_slug/`` paths (the numbered-subfolder scheme itself, and its
# predecessor ``item_dir()`` helper, are retired here), so this reorg does
# not break any external reader -- only this package's own auto-generated
# MANIFEST.md, which is rewritten every run.
# --------------------------------------------------------------------------
def tables_dir() -> Path:
    """Single flat home for every CSV table this package writes."""
    d = OUTPUT_RESULTS_DRAFT / "tables"
    d.mkdir(parents=True, exist_ok=True)
    return d


def maps_dir(scenario: str | None) -> Path:
    """``maps/ssp126|ssp370|ssp585`` for a scenario-specific map (pass the
    opt/bau/pes scenario code -- translated via ``SSP_SLUG``), or
    ``maps/other`` when ``scenario`` is None (a map with no scenario axis,
    e.g. the Extreme Wind SSP-invariant map)."""
    sub = SSP_SLUG[scenario] if scenario is not None else "other"
    d = OUTPUT_RESULTS_DRAFT / "maps" / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def other_dir() -> Path:
    """Every generated figure that is neither a table nor a country-panel
    map (bar charts, heatmaps, convergence diagnostics)."""
    d = OUTPUT_RESULTS_DRAFT / "other"
    d.mkdir(parents=True, exist_ok=True)
    return d


def output_root() -> Path:
    """``data/outputs`` -- the base every file's manifest-relative path is
    computed against, regardless of which of the 3 top-level folders above
    it actually lives in."""
    return OUTPUT_RESULTS_DRAFT.parent


@dataclass
class ManifestEntry:
    item: int
    section: str
    caption: str
    source: str
    files: list[str]
    status: str  # "generated" | "generated (recomputed from source module, no persisted CSV)" | "PENDING: <reason>"
    notes: str = ""


def write_manifest(entries: list[ManifestEntry], path: Path | None = None) -> Path:
    path = path or (OUTPUT_RESULTS_DRAFT / "MANIFEST.md")
    total_files = sum(len(e.files) for e in entries)
    lines = [
        "# results_draft/ manifest -- GEAR_v3_RESULTS_DRAFT.md figure/table generation\n",
        "Generated by `src/reporting/results_draft/run_all.py`. One row per numbered "
        "placeholder in `docs/rework/GEAR_v3_RESULTS_DRAFT.md` (16 total). `Status` "
        '"PENDING" means no committed/persisted data source exists for that item -- '
        "never a rounded or approximated substitute.\n",
        f"**Contagem total de arquivos gerados nesta execução: {total_files}.**\n",
        "| # | Seção | Legenda (resumo) | Fonte | Arquivos | Status |",
        "|---|---|---|---|---|---|",
    ]
    for e in sorted(entries, key=lambda x: x.item):
        files = "<br>".join(e.files) if e.files else "-"
        lines.append(f"| {e.item} | {e.section} | {e.caption} | {e.source} | {files} | {e.status} |")
    n_generated = sum(1 for e in entries if e.status.startswith("generated"))
    n_pending = sum(1 for e in entries if e.status.startswith("PENDING"))
    lines.append(f"\n**Total: {len(entries)} itens -- {n_generated} gerados, {n_pending} pendentes.**\n")

    notes_present = [e for e in entries if e.notes]
    if notes_present:
        lines.append("## Notas por item (consolidação, de-para de nomes, ressalvas)\n")
        for e in notes_present:
            lines.append(f"- **Item {e.item}** ({e.section}): {e.notes}")
        lines.append("")

    if n_pending:
        lines.append("## Pendentes (sem correspondência de dado real)\n")
        for e in entries:
            if e.status.startswith("PENDING"):
                lines.append(f"- **Item {e.item}** ({e.section}): {e.status}")
    OUTPUT_RESULTS_DRAFT.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# Per-file figure inventory -- descriptive, not a ranking (which figures
# matter most is a thesis-context judgment call this package cannot make).
# One row per PNG actually written (tables excluded -- this is a figure
# inventory), parsed from the item's own filename pattern where the
# filename encodes hazard/scenario/bucket, else falling back to the item's
# whole-item ManifestEntry caption for items that produce exactly one file.
# --------------------------------------------------------------------------
def _figure_row(item: int, filename: str, entry: "ManifestEntry") -> tuple[str, str] | None:
    module = {
        1: "item01_correlation_gate.py::run()", 2: "item02_riskband_distribution.py::_plot_country()",
        3: "item03_riskband_asset_map.py::_plot()", 4: "item04_extreme_wind_invariant.py::run()",
        5: "item05_risk_intra_hazard_map.py::_plot()", 7: "item07_sobol_sensitivity.py::run()",
        8: "item08_hazard_removal_oat.py::run()", 9: "item09_correlation_gate_sweep.py::run()",
        10: "item10_general_mc_convergence.py::run()", 11: "item11_general_mc_bars.py::run()",
        12: "item12_psae_distribution.py::_plot_bucket()", 13: "item13_psae_screening_map.py::_plot()",
        14: "item14_validator_overlay.py::run()",
    }.get(item)
    if module is None:  # table-only items (06, 15, 16) produce no figures
        return None
    how = f"{module} -- {entry.source}"

    if item == 2:
        m = re.match(r"riskband_distribution_(\w+)\.png", filename)
        country = m.group(1).capitalize() if m else filename
        return (f"RiskBand_i,h distribution (plant count and MW-share) by hazard x technology "
                f"bucket x SSP scenario, {country} only.", how)
    if item == 3:
        m = re.match(r"riskband_map_(\w+)_(\w+)\.png", filename)
        hazard, scen = (m.group(1), m.group(2)) if m else (filename, "")
        return (f"RiskBand_i,h asset map for {HAZARD_LABEL.get(hazard, hazard)}, "
                f"{SSP_LABEL.get(scen, scen)} -- 3 country panels (Brazil/Portugal/India), marker "
                f"shape = technology bucket, color = RiskBand (Low/Medium/High/Extreme).", how)
    if item == 5:
        m = re.match(r"risk_intra_hazard_map_(\w+)_(\w+)\.png", filename)
        hazard, scen = (m.group(1), m.group(2)) if m else (filename, "")
        return (f"Risk_i,h intra-hazard map for {HAZARD_LABEL.get(hazard, hazard)}, "
                f"{SSP_LABEL.get(scen, scen)} -- continuous viridis color scale by Risk_i,h, marker "
                f"size = capacity_mw, 3 country panels.", how)
    if item == 12:
        m = re.match(r"psae_distribution_(\w+)\.png", filename)
        bucket = m.group(1) if m else filename
        return (f"PSAE_i distribution (plant count and MW-share) for the "
                f"{BUCKET_LABEL.get(bucket, bucket)} bucket, faceted by country and SSP scenario.", how)
    if item == 13:
        m = re.match(r"psae_screening_map_(\w+)_(\w+)\.png", filename)
        bucket, scen = (m.group(1), m.group(2)) if m else (filename, "")
        return (f"PSAE_i screening map for the {BUCKET_LABEL.get(bucket, bucket)} bucket, "
                f"{SSP_LABEL.get(scen, scen)} -- color = PSAE category (Low/Medium/High/Extreme), "
                f"star/triangle overlay = validator corroboration (IBTrACS physical-occurrence / "
                f"EM-DAT broad-impact), 3 country panels.", how)
    return (entry.caption, how)  # single-file items: the item's own caption already describes it


def write_figure_inventory(entries: list[ManifestEntry], path: Path | None = None) -> Path:
    path = path or (OUTPUT_RESULTS_DRAFT / "FIGURE_INVENTORY.md")
    rows = []
    for e in sorted(entries, key=lambda x: x.item):
        for f in e.files:
            if not f.endswith(".png"):
                continue
            described = _figure_row(e.item, Path(f).name, e)
            if described is None:
                continue
            what, how = described
            rows.append((f.replace("\\", "/"), what, how))

    lines = [
        "# results_draft/ -- figure inventory\n",
        "Inventario descritivo de toda figura gerada por "
        "`src/reporting/results_draft/run_all.py`. Sem ranking de importancia -- isso depende "
        "do contexto da tese, que este gerador nao tem. Cada linha: caminho do arquivo "
        "(relativo a `data/outputs/`), o que a figura mostra, e como e gerada (modulo/funcao + "
        "fonte de dado).\n",
        f"**Total de figuras: {len(rows)}.**\n",
        "| Arquivo | O que mostra | Como e gerada |",
        "|---|---|---|",
    ]
    for f, what, how in rows:
        lines.append(f"| `{f}` | {what} | {how} |")
    OUTPUT_RESULTS_DRAFT.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
