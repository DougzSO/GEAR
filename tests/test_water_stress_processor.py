"""Tests for water_stress_processor — Min-Max pooling across bau/opt/pes,
WRI sentinel (9999) substitution in both the raw and normalised outputs, and
proof that the raw layer is captured before normalisation (not inverted from
it). Synthetic fixtures only, no Aqueduct download."""

import geopandas as gpd
import numpy as np
import pytest
import xarray as xr
from shapely.geometry import box

from src.processors import water_stress_processor as wsp
from src.processors.water_stress_processor import RAW_SENTINEL_VALUE


def _ref_grid(ny: int = 4, nx: int = 4) -> xr.DataArray:
    ys = -np.arange(ny, dtype="float64")
    xs = np.arange(nx, dtype="float64")
    da = xr.DataArray(np.zeros((ny, nx)), dims=("y", "x"), coords={"y": ys, "x": xs})
    return da.rio.write_crs("EPSG:4326")


def _basins(values_per_scenario):
    """Two side-by-side basins covering the whole reference grid extent.
    ``values_per_scenario`` is a dict scenario -> [basin1, basin2]."""
    geoms = [box(-1.0, -4.0, 1.5, 1.0), box(1.5, -4.0, 4.0, 1.0)]
    data = {"pfaf_id": [1, 2]}
    data.update(values_per_scenario)
    return gpd.GeoDataFrame(data, geometry=geoms, crs="EPSG:4326")


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
def test_raw_and_normalized_paths_are_distinct():
    assert wsp.raw_raster_path("India", "pes").name == "water_stress_raw_India_pes_1km.tif"
    assert wsp.normalized_raster_path("India", "pes").name == "water_stress_India_pes_1km.tif"
    assert wsp.raw_raster_path("India", "pes") != wsp.normalized_raster_path("India", "pes")


# --------------------------------------------------------------------------
# Min-Max pooling across scenarios
# --------------------------------------------------------------------------
def test_minmax_pools_all_three_scenarios():
    basins = _basins({
        "bau": [0.5, 2.0],
        "opt": [0.1, 1.0],
        "pes": [0.3, 3.0],   # global max is here
    })
    cmin, cmax = wsp.compute_country_minmax("India", basins=basins)
    assert cmin == pytest.approx(0.1)
    assert cmax == pytest.approx(3.0)


def test_minmax_excludes_sentinel_from_pool():
    basins = _basins({
        "bau": [0.5, RAW_SENTINEL_VALUE],
        "opt": [0.1, 1.0],
        "pes": [0.3, 2.0],
    })
    cmin, cmax = wsp.compute_country_minmax("India", basins=basins)
    assert cmax == pytest.approx(2.0)          # 9999 not counted
    assert cmin == pytest.approx(0.1)


def test_minmax_subset_of_scenarios():
    basins = _basins({"bau": [1.0, 9.0], "opt": [0.2, 0.4], "pes": [0.3, 0.5]})
    cmin, cmax = wsp.compute_country_minmax("India", scenarios=["opt", "pes"], basins=basins)
    assert (cmin, cmax) == pytest.approx((0.2, 0.5))


# --------------------------------------------------------------------------
# rasterize_scenario — sentinel substitution, both outputs
# --------------------------------------------------------------------------
def _rasterize(monkeypatch, values, cmin, cmax):
    monkeypatch.setattr(wsp, "_load_reference_grid", lambda c, m=None: _ref_grid())
    basins = _basins({"bau": values, "opt": values, "pes": values})
    return wsp.rasterize_scenario("India", "bau", cmin, cmax, basins=basins)


def test_normalized_is_minmax_of_raw(monkeypatch):
    norm, raw = _rasterize(monkeypatch, [0.5, 1.5], 0.0, 2.0)
    mask = ~np.isnan(raw.values)
    expected = np.clip((raw.values[mask] - 0.0) / (2.0 - 0.0), 0.0, 1.0)
    np.testing.assert_allclose(norm.values[mask], expected, atol=1e-6)


def test_raw_keeps_physical_scale_above_one(monkeypatch):
    _, raw = _rasterize(monkeypatch, [0.5, 1.8], 0.0, 2.0)
    assert float(np.nanmax(raw.values)) > 1.0


def test_raw_is_not_inverted_minmax(monkeypatch):
    _, raw_a = _rasterize(monkeypatch, [0.5, 1.5], 0.0, 2.0)
    _, raw_b = _rasterize(monkeypatch, [0.5, 1.5], -10.0, 999.0)
    np.testing.assert_array_equal(
        np.nan_to_num(raw_a.values, nan=-1), np.nan_to_num(raw_b.values, nan=-1)
    )


def test_sentinel_becomes_country_max_in_both_outputs(monkeypatch):
    # basin 2 = WRI sentinel -> country_max (2.0) in raw, 1.0 in normalised
    norm, raw = _rasterize(monkeypatch, [0.5, RAW_SENTINEL_VALUE], 0.0, 2.0)
    raw_vals = np.unique(raw.values[~np.isnan(raw.values)])
    assert RAW_SENTINEL_VALUE not in raw_vals
    assert 2.0 in raw_vals
    assert float(np.nanmax(norm.values)) == pytest.approx(1.0)
    assert raw.attrs["n_sentinel_clipped_to_max"] == 1


def test_pixels_outside_basins_stay_nan(monkeypatch):
    monkeypatch.setattr(wsp, "_load_reference_grid", lambda c, m=None: _ref_grid(nx=8))
    # basins only cover x in [-1, 4]; x = 5,6,7 columns fall outside
    basins = _basins({"bau": [0.5, 1.0], "opt": [0.5, 1.0], "pes": [0.5, 1.0]})
    _, raw = wsp.rasterize_scenario("India", "bau", 0.0, 1.0, basins=basins)
    assert np.isnan(raw.values[:, -1]).all()


def test_raw_units_attribute(monkeypatch):
    _, raw = _rasterize(monkeypatch, [0.5, 1.5], 0.0, 2.0)
    assert raw.attrs["units"] == "consumption_to_availability_ratio"
    assert "none" in raw.attrs["normalization"].lower()
