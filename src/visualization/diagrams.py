"""
Figure 1 -- conceptual architecture diagram of the GEAR/CCRS pipeline.

Unlike every other module in ``src/visualization`` (which plots real data),
this one draws a static flowchart: inputs -> processing -> output, three
layers, no data dependency. Built directly in matplotlib (``FancyBboxPatch``
boxes, ``FancyArrowPatch`` arrows) rather than an external diagramming tool,
so it stays inside the same reproducible pipeline as every other figure and
shares ``_common``'s font scale, dpi and PNG+PDF save convention.

--------------------------------------------------------------------------
Orientation: left-to-right (Douglas's 2026-09-05 request, justified here)
--------------------------------------------------------------------------
Left-to-right over top-to-bottom because (a) it reads as a pipeline in the
conventional input -> transform -> output direction without relying on an
arrow-direction legend, and (b) it produces a wide/landscape figure,
consistent with every combined multi-country map in this project (three
country panels side by side) and better suited to a full page-width insert
in the manuscript than a tall, narrow, top-to-bottom chart would be.

--------------------------------------------------------------------------
Notation -- confirmed against analysis/climate_risk_score_spec.md before
drawing, not invented for this figure
--------------------------------------------------------------------------
- ``Hazard_i,s`` (Section 2/3): the weighted-sum hazard term, three additive
  components since the SPEI integration -- ``w_water[bucket]*water_sub +
  w_heat[bucket]*Tlog(heat) + w_drought[bucket]*Tlog(spei_freq)``.
- ``age_factor_i`` (Section 6): plain-text subscript notation, exactly as
  used in ``src/index/age_factor.py`` and the spec -- there is no separate
  Greek symbol anywhere in the codebase for this term, so none is invented
  here (the spec/docstrings never write ``alpha(t_i)``).
- ``EventMultiplier_i`` / ``EventMultiplier_c`` (Section 7): country-level
  multiplier, ``EventMultiplier_c = 1 + k*(rate_c/rate_max)``.
- ``CCRS_i,s`` (Section 2): ``Hazard_i,s x age_factor_i x EventMultiplier_i``,
  purely multiplicative, one value per plant x scenario (x GCM).
- ``WaterRiskBand`` / ``HeatRiskBand`` (Section 8): computed on the raw
  normalized water/heat components directly (``S_water``,
  ``extreme_heat_days``), independent of ``age_factor``/``EventMultiplier``
  and NOT derived from the final ``CCRS_i,s`` -- the single combined-CCRS
  band was tried and dropped (Section 8.0). The diagram draws this as a
  separate branch off ``Normalization``, not off ``CCRS_i,s``, to avoid
  misrepresenting a closed methodological decision.

--------------------------------------------------------------------------
Two judgment calls made for completeness, not explicitly listed in Douglas's
box-by-box content spec -- flagged rather than silently added
--------------------------------------------------------------------------
- **EM-DAT disaster records** is drawn as a fourth Input box. Douglas's
  content list names only GEM/GADM/climate hazards under "Inputs", but
  ``EventMultiplier_c`` (an explicitly requested Processing box) cannot be
  drawn with an incoming arrow from nothing -- EM-DAT is its only data
  source (``src/index/event_multiplier.py``). Omitting the box would make
  the diagram inaccurate about where that term comes from.
- **GADM boundaries** is connected with two arrows: into ``Normalization``
  (administrative/country delineation used throughout the pipeline) and,
  dashed, into ``Risk Bands`` (the bands are ultimately reported per
  admin-1 unit on the maps). Neither connection is a numeric input to the
  ``Hazard``/``CCRS`` formulas themselves -- GADM does not enter any
  equation -- so both arrows are drawn in a lighter, dashed style to
  visually distinguish "administrative context" from the numeric data flow
  (CMIP6/Aqueduct/EM-DAT -> formulas).
> Point to validate: confirm both choices read as intended, or say what to
> change before this is committed.
"""

from __future__ import annotations

import textwrap

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from src.config import OUTPUT_DIAGRAMS
from src.visualization._common import fs, save_figure

LAYER_BG = {
    "input": "#eaf0f7",
    "processing": "#f7f1e6",
    "output": "#eaf5ec",
}
BOX_FACECOLOR = "#ffffff"
BOX_EDGECOLOR = "#333333"
ARROW_COLOR = "#333333"
CONTEXT_ARROW_COLOR = "#999999"
LAYER_LABEL_COLOR = "#555555"


def _box(ax, cx: float, cy: float, w: float, h: float, text: str, wrap: int = 24) -> None:
    wrapped = "\n".join(textwrap.fill(line, wrap) if line else "" for line in text.split("\n"))
    ax.add_patch(FancyBboxPatch(
        (cx - w / 2, cy - h / 2), w, h,
        boxstyle="round,pad=0.12,rounding_size=0.18",
        facecolor=BOX_FACECOLOR, edgecolor=BOX_EDGECOLOR, linewidth=1.0, zorder=3,
    ))
    ax.text(cx, cy, wrapped, ha="center", va="center", fontsize=fs(8.5), zorder=4, linespacing=1.35)


def _layer_band(ax, x0: float, width: float, y0: float, height: float, color: str, label: str) -> None:
    ax.add_patch(FancyBboxPatch(
        (x0, y0), width, height, boxstyle="round,pad=0,rounding_size=0.3",
        facecolor=color, edgecolor="none", zorder=1,
    ))
    ax.text(x0 + width / 2, y0 + height - 0.55, label, ha="center", va="top",
            fontsize=fs(11), fontweight="bold", color=LAYER_LABEL_COLOR, zorder=2)


def _arrow(ax, p_from: tuple[float, float], p_to: tuple[float, float],
           dashed: bool = False, curve: float = 0.0) -> None:
    ax.add_patch(FancyArrowPatch(
        p_from, p_to, arrowstyle="-|>", mutation_scale=14,
        color=CONTEXT_ARROW_COLOR if dashed else ARROW_COLOR,
        linewidth=1.1, linestyle="--" if dashed else "-",
        connectionstyle=f"arc3,rad={curve}", zorder=2, shrinkA=2, shrinkB=2,
    ))


def _bent_arrow(ax, points: list[tuple[float, float]], dashed: bool = False) -> None:
    """Multi-segment routed connector -- straight ``Line2D`` legs through
    the empty corridors between box rows/columns, with a real arrowhead
    only on the final short leg. Used where a single bezier (``_arrow``)
    would bow through a box it must route around (e.g. an input feeding a
    box two rows below another one directly in the way)."""
    color = CONTEXT_ARROW_COLOR if dashed else ARROW_COLOR
    xs, ys = zip(*points[:-1])
    ax.plot(xs, ys, color=color, linewidth=1.1, linestyle="--" if dashed else "-", zorder=2)
    ax.add_patch(FancyArrowPatch(
        points[-2], points[-1], arrowstyle="-|>", mutation_scale=14, color=color,
        linewidth=1.1, linestyle="--" if dashed else "-", zorder=2, shrinkA=0, shrinkB=2,
    ))


def plot_pipeline_overview() -> "pathlib.Path":
    """Figure 1: conceptual 3-layer flowchart (inputs -> processing ->
    output) of the GEAR/CCRS pipeline. No printed title (project convention,
    ``_common.panel_title`` docstring) -- a caption goes in the manuscript
    text, not on the figure."""
    fig, ax = plt.subplots(figsize=(15, 8.5))
    ax.set_xlim(0, 30)
    ax.set_ylim(0, 18)
    ax.axis("off")

    _layer_band(ax, 0.3, 8.4, 0.3, 17.4, LAYER_BG["input"], "Inputs")
    _layer_band(ax, 9.2, 11.6, 0.3, 17.4, LAYER_BG["processing"], "Processing")
    _layer_band(ax, 21.3, 8.4, 0.3, 17.4, LAYER_BG["output"], "Output")

    box_w_in, box_w_proc, box_w_out = 7.2, 9.6, 7.2

    gem = (4.5, 15.5)
    gadm = (4.5, 11.5)
    climate = (4.5, 6.5)
    emdat = (4.5, 1.8)
    _box(ax, *gem, box_w_in, 2.3, "GEM Operating Assets\n(plant-level data, 3 countries)")
    _box(ax, *gadm, box_w_in, 2.3, "GADM Administrative Boundaries\n(admin-1 layers, disputed-territory handling)")
    _box(ax, *climate, box_w_in, 4.0,
         "Climate Hazard Data\nCopernicus CMIP6: tasmax, precipitation\n(GFDL-ESM4, MIROC6; 3 scenarios)\nAqueduct 4.0: water stress, seasonal/\ninterannual variability")
    _box(ax, *emdat, box_w_in, 2.3, "EM-DAT Disaster Records\n(country-level event frequency)")

    normalization = (15.0, 15.2)
    spei = (15.0, 11.8)
    hazard = (15.0, 8.4)
    age_factor = (15.0, 5.0)
    event_mult = (15.0, 1.8)
    _box(ax, *normalization, box_w_proc, 2.6,
         "Normalization\nFROZEN_BOUNDS global bounds\nTlog / Tlin transforms")
    _box(ax, *spei, box_w_proc, 2.6,
         "SPEI Drought Term\nThornthwaite PET; spei_freq\n(SPEI-12 <= -1.0)")
    _box(ax, *hazard, box_w_proc, 2.8,
         "Hazard_i,s\nw_water*water_sub + w_heat*Tlog(heat)\n+ w_drought*Tlog(spei_freq)", wrap=999)
    _box(ax, *age_factor, box_w_proc, 2.6,
         "age_factor_i\ntechnology-specific retention curve\n(>= 1 multiplier)")
    _box(ax, *event_mult, box_w_proc, 2.6,
         "EventMultiplier_i\nEventMultiplier_c = 1 + k*(rate_c/rate_max)\n(>= 1 multiplier, country-level)")

    ccrs = (25.4, 12.0)
    bands = (25.4, 5.0)
    _box(ax, *ccrs, box_w_out, 3.4, "CCRS_i,s\n= Hazard_i,s x age_factor_i\nx EventMultiplier_i")
    _box(ax, *bands, box_w_out, 3.4, "Risk Bands\nWaterRiskBand\nHeatRiskBand")

    _arrow(ax, (gem[0] + box_w_in / 2, gem[1] - 0.5), (age_factor[0] - box_w_proc / 2, age_factor[1] + 0.9), curve=-0.22)
    _arrow(ax, (climate[0] + box_w_in / 2, climate[1] + 1.3), (normalization[0] - box_w_proc / 2, normalization[1] - 0.3), curve=0.1)
    _arrow(ax, (climate[0] + box_w_in / 2, climate[1] - 0.3), (spei[0] - box_w_proc / 2, spei[1]), curve=0.03)
    _arrow(ax, (emdat[0] + box_w_in / 2, emdat[1]), (event_mult[0] - box_w_proc / 2, event_mult[1]), curve=-0.03)

    # GADM -> Risk Bands: routed through the empty horizontal corridor
    # between age_factor and EventMultiplier (the only row gap wide enough
    # to cross the whole processing column without cutting through a box).
    corridor_y = (age_factor[1] - 2.6 / 2 + event_mult[1] + 2.6 / 2) / 2
    _bent_arrow(ax, [
        (gadm[0] + box_w_in / 2, gadm[1] - 0.9),
        (gadm[0] + box_w_in / 2 + 0.6, corridor_y),
        (bands[0] - box_w_out / 2 - 0.6, corridor_y),
        (bands[0] - box_w_out / 2, bands[1] - 0.9),
    ], dashed=True)

    # Normalization / SPEI -> Hazard: routed through the empty vertical
    # corridors just outside the processing boxes' left/right edges, so
    # neither arrow cuts across the SPEI box sitting directly between
    # Normalization and Hazard.
    right_corridor_x = normalization[0] + box_w_proc / 2 + 0.15
    left_corridor_x = normalization[0] - box_w_proc / 2 - 0.15
    _bent_arrow(ax, [
        (normalization[0] + box_w_proc / 2, normalization[1] - 0.9),
        (right_corridor_x, normalization[1] - 0.9),
        (right_corridor_x, hazard[1] + 1.0),
        (hazard[0] + box_w_proc / 2 - 0.3, hazard[1] + 1.0),
    ])
    _bent_arrow(ax, [
        (spei[0] - box_w_proc / 2, spei[1] - 0.9),
        (left_corridor_x, spei[1] - 0.9),
        (left_corridor_x, hazard[1] + 1.0),
        (hazard[0] - box_w_proc / 2 + 0.3, hazard[1] + 1.0),
    ])

    _arrow(ax, (hazard[0] + box_w_proc / 2, hazard[1] + 0.3), (ccrs[0] - box_w_out / 2, ccrs[1] - 1.0), curve=-0.10)
    _arrow(ax, (age_factor[0] + box_w_proc / 2, age_factor[1] + 0.2), (ccrs[0] - box_w_out / 2, ccrs[1] - 1.5), curve=-0.20)
    _arrow(ax, (event_mult[0] + box_w_proc / 2, event_mult[1]), (ccrs[0] - box_w_out / 2, ccrs[1] - 1.65), curve=-0.30)

    _bent_arrow(ax, [
        (normalization[0] + box_w_proc / 2, normalization[1] - 1.1),
        (right_corridor_x + 0.5, normalization[1] - 1.1),
        (right_corridor_x + 0.5, bands[1] + 1.0),
        (bands[0] - box_w_out / 2, bands[1] + 1.0),
    ])

    fig.tight_layout()
    out_path = save_figure(fig, OUTPUT_DIAGRAMS / "figure1_pipeline_overview.png")
    return out_path


def main() -> int:
    path = plot_pipeline_overview()
    print(f"Saved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
