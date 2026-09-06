"""
Infrastructure shared by more than one climate processor -- consolidated
here so the duplicated copies cannot drift apart.

Two independent pieces:

* **Aqueduct input + reference grid** (``_find_aqueduct_csv``,
  ``_load_reference_grid``) -- used by both ``water_stress_processor`` and
  ``water_variability_processor``, which read the same
  ``aqueduct_{year}.csv`` and rasterise onto the same 1 km grid (the grid of
  an already-processed extreme-heat raster).
* **Grid-consistency guard** (``GridMismatchError``, ``grid_signature``,
  ``assert_consistent_grid``, ``load_country_rasters``) -- used by both
  ``heat_stress_processor`` and ``spei_processor``, the two GCM/scenario-
  indexed layers that pool every ``(model, scenario)`` raster into one
  per-country Min-Max domain. Joint pooling is only valid if every pooled
  raster sits on the same grid; the guard fails loud (never a silent pass)
  when they disagree on shape, resolution/transform or CRS. It caught, and
  forced the fix of, a real grid-offset bug between GFDL-ESM4 and MIROC6
  (``docs/DECISIONS.md``, V4).

``load_country_rasters`` takes the per-raster loader as a callable argument
because heat and SPEI open different files (the downloader's existing heat
raster vs. the SPEI raw raster this processor computes).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rioxarray  # noqa: F401 - registers the .rio accessor
import xarray as xr

from src.config import CLIMATE_RAW, YEAR_TARGET
from src.downloaders.cds_tasmax_downloader import configured_models, resampled_raster_path

# Absolute tolerance on the six affine-transform coefficients when comparing
# grids. The 1 km grid is derived by nearest-neighbour resampling from a fixed
# country bounding box, so matching model rasters are bit-identical; this only
# guards against a genuinely different grid slipping in.
_TRANSFORM_ATOL = 1e-9


# --------------------------------------------------------------------------
# Aqueduct input + reference grid (water_stress / water_variability)
# --------------------------------------------------------------------------
def _find_aqueduct_csv(country: str) -> Path:
    """Locate the consolidated Aqueduct CSV (``aqueduct_{year}.csv``, one file
    holding every scenario/indicator column). Raises ``FileNotFoundError`` if
    absent."""
    csv_path = CLIMATE_RAW / "aqueduct" / country / f"aqueduct_{YEAR_TARGET}.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"No Aqueduct CSV for {country} at {csv_path}. Run the Aqueduct "
            f"downloader first."
        )
    return csv_path


def _load_reference_grid(country: str, model: str | None = None) -> xr.DataArray:
    """Load the grid (transform/shape/CRS) of an already processed heat
    raster; the Aqueduct layer is rasterised onto exactly this grid, so every
    hazard layer aligns pixel for pixel. The 1 km grid depends only on the
    country bounds and target resolution, so it is identical across models and
    scenarios -- the first configured model / ssp126 is used arbitrarily."""
    model = model or configured_models()[0]
    ref_path = resampled_raster_path(country, model, "ssp126")
    if not ref_path.exists():
        raise FileNotFoundError(
            f"Reference grid not found: {ref_path}. Process the extreme-heat "
            f"layer first (its grid is reused here)."
        )
    da = rioxarray.open_rasterio(ref_path)
    return da.isel(band=0) if "band" in da.dims else da


# --------------------------------------------------------------------------
# Grid-consistency guard (heat_stress / spei)
# --------------------------------------------------------------------------
class GridMismatchError(ValueError):
    """Raised when the model/scenario rasters that would be pooled into one
    Min-Max domain are not on the same grid (shape, resolution/transform or
    CRS). Joint per-country pooling and a shared normalisation domain are
    invalid on mismatched grids, and the normalised stack would be silently
    misaligned. Fail loud instead."""


def grid_signature(da: xr.DataArray) -> tuple:
    """(shape, transform coefficients, CRS) -- everything that defines the
    grid a raster sits on."""
    transform = tuple(float(v) for v in tuple(da.rio.transform())[:6])
    return tuple(da.shape), transform, str(da.rio.crs)


def assert_consistent_grid(
    country: str, rasters: dict[tuple[str, str], xr.DataArray]
) -> None:
    """Fail loudly if the rasters to be pooled disagree on grid shape,
    resolution/transform or CRS. No-op for a single raster."""
    items = list(rasters.items())
    ref_key, ref_da = items[0]
    ref_shape, ref_transform, ref_crs = grid_signature(ref_da)

    problems: list[str] = []
    for key, da in items[1:]:
        shape, transform, crs = grid_signature(da)
        if shape != ref_shape:
            problems.append(f"{key} shape {shape} != {ref_shape} {ref_key}")
        elif not np.allclose(transform, ref_transform, rtol=0.0, atol=_TRANSFORM_ATOL):
            problems.append(f"{key} transform {transform} != {ref_transform} {ref_key}")
        if crs != ref_crs:
            problems.append(f"{key} CRS {crs} != {ref_crs} {ref_key}")

    if problems:
        raise GridMismatchError(
            f"{country}: rasters to be pooled into one Min-Max domain are on "
            f"inconsistent grids -- joint pooling is invalid until this is "
            f"fixed:\n  " + "\n  ".join(problems)
        )


def load_country_rasters(
    country: str,
    load_one,
    models: list[str],
    scenarios: list[str],
) -> dict[tuple[str, str], xr.DataArray]:
    """Open every ``(model, scenario)`` raster for ``country`` via
    ``load_one(country, model, scenario)`` and assert they share one grid
    before any of them is used."""
    rasters = {
        (model, scenario): load_one(country, model, scenario)
        for model in models
        for scenario in scenarios
    }
    assert_consistent_grid(country, rasters)
    return rasters
