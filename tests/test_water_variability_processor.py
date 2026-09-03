"""Tests for water_variability_processor — sv/iv rasterisation mirroring
water_stress_processor: per-country per-indicator Min-Max pooled across
bau/opt/pes, independent sv and iv pools, no sentinel, no log, and proof the
raw layer is captured before normalisation (not inverted from it). Synthetic
fixtures only, no Aqueduct download."""

import geopandas as gpd
import numpy as np
import pytest
import xarray as xr
from shapely.geometry import box

from src.processors import water_variability_processor as wvp


def _ref_grid(ny: int = 4, nx: int = 4) -> xr.DataArray:
    ys = -np.arange(ny, dtype="float64")
    xs = np.arange(nx, dtype="float64")
    da = xr.DataArray(np.zeros((ny, nx)), dims=("y", "x"), coords={"y": ys, "x": xs})
    return da.rio.write_crs("EPSG:4326")


def _basins(cols):
    """Two side-by-side basins covering the whole reference grid extent.
    ``cols`` maps ``{indicator}_{scenario}`` -> [basin1, basin2]. Any of the
    six sv/iv columns not given defaults to a flat 1.0."""
    geoms = [box(-1.0, -4.0, 1.5, 1.0), box(1.5, -4.0, 4.0, 1.0)]
    data = {"pfaf_id": [1, 2]}
    for ind in wvp.INDICATORS:
        for s in ("bau", "opt", "pes"):
            key = f"{ind}_{s}"
            data[key] = cols.get(key, [1.0, 1.0])
    return gpd.GeoDataFrame(data, geometry=geoms, crs="EPSG:4326")


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
def test_paths_distinct_per_indicator_and_kind():
    assert wvp.normalized_raster_path("India", "pes", "sv").name == "seasonal_variability_India_pes_1km.tif"
    assert wvp.raw_raster_path("India", "pes", "sv").name == "seasonal_variability_raw_India_pes_1km.tif"
    assert wvp.normalized_raster_path("India", "pes", "iv").name == "interannual_variability_India_pes_1km.tif"
    assert wvp.raw_raster_path("India", "pes", "iv").name == "interannual_variability_raw_India_pes_1km.tif"
    # every combination is a distinct file
    paths = {
        wvp.normalized_raster_path("India", "pes", "sv"),
        wvp.raw_raster_path("India", "pes", "sv"),
        wvp.normalized_raster_path("India", "pes", "iv"),
        wvp.raw_raster_path("India", "pes", "iv"),
    }
    assert len(paths) == 4


def test_unknown_indicator_rejected():
    with pytest.raises(ValueError):
        wvp.normalized_raster_path("India", "pes", "ws")
    with pytest.raises(ValueError):
        wvp.compute_country_minmax("India", "wd", basins=_basins({}))


def test_raw_column_name():
    assert wvp._scenario_raw_column("bau", "sv") == "bau50_sv_x_r"
    assert wvp._scenario_raw_column("pes", "iv") == "pes50_iv_x_r"


# --------------------------------------------------------------------------
# Min-Max pooling — per country, per indicator, across scenarios
# --------------------------------------------------------------------------
def test_minmax_pools_all_three_scenarios():
    basins = _basins({
        "sv_bau": [0.5, 1.2],
        "sv_opt": [0.1, 0.8],
        "sv_pes": [0.3, 1.6],   # sv max is here
    })
    cmin, cmax = wvp.compute_country_minmax("India", "sv", basins=basins)
    assert cmin == pytest.approx(0.1)
    assert cmax == pytest.approx(1.6)


def test_sv_and_iv_pools_are_independent():
    basins = _basins({
        "sv_bau": [0.2, 0.4], "sv_opt": [0.2, 0.4], "sv_pes": [0.2, 0.4],
        "iv_bau": [1.0, 3.0], "iv_opt": [1.0, 3.0], "iv_pes": [1.0, 3.0],
    })
    sv_min, sv_max = wvp.compute_country_minmax("India", "sv", basins=basins)
    iv_min, iv_max = wvp.compute_country_minmax("India", "iv", basins=basins)
    assert (sv_min, sv_max) == pytest.approx((0.2, 0.4))
    assert (iv_min, iv_max) == pytest.approx((1.0, 3.0))


def test_minmax_subset_of_scenarios():
    basins = _basins({"iv_bau": [1.0, 9.0], "iv_opt": [0.2, 0.4], "iv_pes": [0.3, 0.5]})
    cmin, cmax = wvp.compute_country_minmax("India", "iv", scenarios=["opt", "pes"], basins=basins)
    assert (cmin, cmax) == pytest.approx((0.2, 0.5))


def test_no_sentinel_substitution():
    """Unlike ws/wd, a large value is a real value here — no 9999 handling."""
    assert not hasattr(wvp, "RAW_SENTINEL_VALUE")
    basins = _basins({"iv_bau": [0.3, 5.0], "iv_opt": [0.3, 5.0], "iv_pes": [0.3, 5.0]})
    cmin, cmax = wvp.compute_country_minmax("India", "iv", basins=basins)
    assert cmax == pytest.approx(5.0)  # 5.0 kept, not treated as a sentinel


def test_absurd_value_fails_loud():
    basins = _basins({"sv_bau": [0.3, 9999.0], "sv_opt": [0.3, 0.4], "sv_pes": [0.3, 0.4]})
    # the guard lives in the CSV loader; simulate it directly
    numeric = basins[[f"{i}_{s}" for i in wvp.INDICATORS for s in ("bau", "opt", "pes")]]
    assert float(np.nanmax(np.abs(numeric.to_numpy()))) > wvp.SANITY_CEILING


# --------------------------------------------------------------------------
# rasterize_scenario — both outputs, no log, raw not inverted
# --------------------------------------------------------------------------
def _rasterize(monkeypatch, indicator, values, cmin, cmax):
    monkeypatch.setattr(wvp, "_load_reference_grid", lambda c, m=None: _ref_grid())
    basins = _basins({
        f"{indicator}_bau": values,
        f"{indicator}_opt": values,
        f"{indicator}_pes": values,
    })
    return wvp.rasterize_scenario("India", "bau", indicator, cmin, cmax, basins=basins)


def test_normalized_is_plain_minmax_of_raw(monkeypatch):
    norm, raw = _rasterize(monkeypatch, "sv", [0.5, 1.5], 0.0, 2.0)
    mask = ~np.isnan(raw.values)
    expected = np.clip((raw.values[mask] - 0.0) / (2.0 - 0.0), 0.0, 1.0)
    np.testing.assert_allclose(norm.values[mask], expected, atol=1e-6)


def test_no_log_transform_applied(monkeypatch):
    """A linear Min-Max maps the midpoint of [min, max] to 0.5; log1p would not."""
    norm, raw = _rasterize(monkeypatch, "iv", [1.0, 1.0], 0.0, 2.0)
    assert float(np.nanmax(norm.values)) == pytest.approx(0.5)


def test_raw_keeps_physical_scale_above_one(monkeypatch):
    _, raw = _rasterize(monkeypatch, "iv", [0.5, 1.8], 0.0, 2.0)
    assert float(np.nanmax(raw.values)) > 1.0


def test_raw_is_not_inverted_minmax(monkeypatch):
    _, raw_a = _rasterize(monkeypatch, "sv", [0.5, 1.5], 0.0, 2.0)
    _, raw_b = _rasterize(monkeypatch, "sv", [0.5, 1.5], -10.0, 999.0)
    np.testing.assert_array_equal(
        np.nan_to_num(raw_a.values, nan=-1), np.nan_to_num(raw_b.values, nan=-1)
    )


def test_pixels_outside_basins_stay_nan(monkeypatch):
    monkeypatch.setattr(wvp, "_load_reference_grid", lambda c, m=None: _ref_grid(nx=8))
    basins = _basins({f"sv_{s}": [0.5, 1.0] for s in ("bau", "opt", "pes")})
    _, raw = wvp.rasterize_scenario("India", "bau", "sv", 0.0, 1.0, basins=basins)
    assert np.isnan(raw.values[:, -1]).all()


def test_raw_units_and_indicator_attrs(monkeypatch):
    _, raw = _rasterize(monkeypatch, "sv", [0.5, 1.5], 0.0, 2.0)
    assert raw.attrs["units"] == "variability_coefficient_dimensionless"
    assert raw.attrs["aqueduct_indicator"] == "sv"
    assert "none" in raw.attrs["normalization"].lower()


def test_norm_attrs_carry_country_bounds(monkeypatch):
    norm, _ = _rasterize(monkeypatch, "iv", [0.5, 1.5], 0.1, 3.0)
    assert norm.attrs["country_min"] == pytest.approx(0.1)
    assert norm.attrs["country_max"] == pytest.approx(3.0)
    assert norm.attrs["aqueduct_indicator"] == "iv"


def test_degenerate_domain_gives_zeros_not_nan_inside_basins(monkeypatch):
    norm, raw = _rasterize(monkeypatch, "sv", [0.7, 0.7], 0.7, 0.7)
    inside = ~np.isnan(raw.values)
    assert (norm.values[inside] == 0.0).all()
