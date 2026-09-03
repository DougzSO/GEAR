"""Tests for heat_stress_processor — per-country Min-Max with scenarios
(ssp126/ssp585) AND models pooled jointly into one domain, passthrough of the
raw layer, NaN preservation, multi-model iteration, and the fail-loud grid
guard that protects the joint pool once a second GCM is added (V4). Synthetic
fixtures only, no CDS data."""

import numpy as np
import pytest
import xarray as xr

from src.processors import heat_stress_processor as hsp
from src.processors.heat_stress_processor import GridMismatchError


def _grid(values: np.ndarray, res: float = 1.0, x0: float = 0.0) -> xr.DataArray:
    ny, nx = values.shape
    ys = -np.arange(ny, dtype="float64") * res
    xs = x0 + np.arange(nx, dtype="float64") * res
    da = xr.DataArray(
        values.astype("float64"), dims=("y", "x"), coords={"y": ys, "x": xs}
    )
    return da.rio.write_crs("EPSG:4326")


def _patch_rasters(monkeypatch, data: dict):
    """``data`` maps (model, scenario) -> np.ndarray; installs a fake
    ``_load_heat_raster`` and a matching ``configured_models``."""
    monkeypatch.setattr(
        hsp, "_load_heat_raster", lambda c, m, s: _grid(data[(m, s)])
    )
    models = sorted({m for m, _ in data})
    monkeypatch.setattr(hsp, "configured_models", lambda: models)


# --------------------------------------------------------------------------
# Paths / passthrough
# --------------------------------------------------------------------------
def test_raw_path_is_the_downloader_output():
    from src.downloaders.cds_tasmax_downloader import resampled_raster_path

    p = hsp.raw_raster_path("Brazil", "gfdl_esm4", "ssp585")
    assert p == resampled_raster_path("Brazil", "gfdl_esm4", "ssp585")
    assert p.name == "extreme_heat_days_Brazil_gfdl_esm4_ssp585_1km.tif"


def test_normalized_path_is_model_tagged():
    assert (
        hsp.normalized_raster_path("India", "gfdl_esm4", "ssp126").name
        == "heat_stress_India_gfdl_esm4_ssp126_1km.tif"
    )


def test_process_report_marks_raw_as_passthrough(monkeypatch, tmp_path):
    monkeypatch.setattr(hsp, "CLIMATE_PROCESSED", tmp_path)
    days = np.array([[0.0, 20.0, 60.0], [10.0, np.nan, 172.0]])
    monkeypatch.setattr(hsp, "_load_heat_raster", lambda c, m, s: _grid(days))

    rep = hsp.process_country_model_scenario(
        "India", "gfdl_esm4", "ssp585", 0.0, 172.0, overwrite=True
    )
    assert rep["success"] is True
    assert rep["raw_kind"] == "passthrough_existing"
    assert rep["raw_units"] == "days_per_year_with_tasmax_gt_40C"
    assert rep["raw_path"].endswith("extreme_heat_days_India_gfdl_esm4_ssp585_1km.tif")
    # normalised raster actually written; raw layer NOT written by this module
    assert (tmp_path / "heat_stress_India_gfdl_esm4_ssp585_1km.tif").exists()
    assert not (tmp_path / "extreme_heat_days_India_gfdl_esm4_ssp585_1km.tif").exists()


# --------------------------------------------------------------------------
# Min-Max pooling — scenarios and models jointly
# --------------------------------------------------------------------------
def test_minmax_pools_both_scenarios(monkeypatch):
    _patch_rasters(monkeypatch, {
        ("gfdl_esm4", "ssp126"): np.array([[0.0, 10.0], [40.0, np.nan]]),
        ("gfdl_esm4", "ssp585"): np.array([[5.0, 20.0], [80.0, 173.0]]),  # max here
    })
    cmin, cmax = hsp.compute_country_minmax("India")
    assert cmin == pytest.approx(0.0)
    assert cmax == pytest.approx(173.0)


def test_minmax_pools_jointly_across_two_models(monkeypatch):
    # second synthetic model even though CMIP6_SOURCE_ID_CDS holds only one:
    # the joint domain must span BOTH models' extremes.
    _patch_rasters(monkeypatch, {
        ("m_cool", "ssp126"): np.array([[0.0, 5.0]]),
        ("m_cool", "ssp585"): np.array([[2.0, 8.0]]),
        ("m_hot", "ssp126"): np.array([[50.0, 90.0]]),
        ("m_hot", "ssp585"): np.array([[60.0, 200.0]]),   # joint max
    })
    cmin, cmax = hsp.compute_country_minmax("India")
    assert cmin == pytest.approx(0.0)     # from m_cool
    assert cmax == pytest.approx(200.0)   # from m_hot
    # a per-model domain would have given (0, 8) or (50, 200) — never (0, 200)


def test_every_model_scenario_shares_one_country_domain(monkeypatch, tmp_path):
    monkeypatch.setattr(hsp, "CLIMATE_PROCESSED", tmp_path)
    _patch_rasters(monkeypatch, {
        ("m_cool", "ssp126"): np.array([[0.0, 5.0]]),
        ("m_cool", "ssp585"): np.array([[2.0, 8.0]]),
        ("m_hot", "ssp126"): np.array([[50.0, 90.0]]),
        ("m_hot", "ssp585"): np.array([[60.0, 200.0]]),
    })
    report = hsp.process_all_countries(countries=["India"])
    india = report["countries"]["India"]
    assert india["country_min"] == pytest.approx(0.0)
    assert india["country_max"] == pytest.approx(200.0)
    # m_cool's hottest cell (8) normalises against the joint max (200), not 8
    cool = hsp.normalize_scenario("India", "m_cool", "ssp585", 0.0, 200.0).values
    assert float(np.nanmax(cool)) == pytest.approx(8.0 / 200.0)


# --------------------------------------------------------------------------
# Grid guard — fail loud, never silent
# --------------------------------------------------------------------------
def test_grid_mismatch_shape_between_models_fails_loud(monkeypatch):
    monkeypatch.setattr(hsp, "configured_models", lambda: ["m_a", "m_b"])

    def fake_load(country, model, scenario):
        shape = (2, 2) if model == "m_a" else (2, 3)
        return _grid(np.ones(shape))

    monkeypatch.setattr(hsp, "_load_heat_raster", fake_load)
    with pytest.raises(GridMismatchError, match="shape"):
        hsp.compute_country_minmax("India")


def test_grid_mismatch_resolution_between_models_fails_loud(monkeypatch):
    monkeypatch.setattr(hsp, "configured_models", lambda: ["m_a", "m_b"])

    def fake_load(country, model, scenario):
        res = 1.0 if model == "m_a" else 2.0
        return _grid(np.ones((2, 2)), res=res)

    monkeypatch.setattr(hsp, "_load_heat_raster", fake_load)
    with pytest.raises(GridMismatchError, match="transform"):
        hsp.compute_country_minmax("India")


def test_grid_mismatch_crs_between_models_fails_loud(monkeypatch):
    monkeypatch.setattr(hsp, "configured_models", lambda: ["m_a", "m_b"])

    def fake_load(country, model, scenario):
        da = _grid(np.ones((2, 2)))
        return da if model == "m_a" else da.rio.write_crs("EPSG:3857")

    monkeypatch.setattr(hsp, "_load_heat_raster", fake_load)
    with pytest.raises(GridMismatchError, match="CRS"):
        hsp.compute_country_minmax("India")


def test_matching_grids_pass_the_guard(monkeypatch):
    _patch_rasters(monkeypatch, {
        ("m_a", "ssp126"): np.zeros((3, 3)),
        ("m_a", "ssp585"): np.ones((3, 3)),
        ("m_b", "ssp126"): np.full((3, 3), 2.0),
        ("m_b", "ssp585"): np.full((3, 3), 3.0),
    })
    cmin, cmax = hsp.compute_country_minmax("India")
    assert (cmin, cmax) == pytest.approx((0.0, 3.0))


# --------------------------------------------------------------------------
# Normalisation behaviour
# --------------------------------------------------------------------------
def test_normalize_matches_minmax_formula_and_preserves_nan(monkeypatch):
    days = np.array([[0.0, 10.0, 40.0], [np.nan, 20.0, 80.0]])
    monkeypatch.setattr(hsp, "_load_heat_raster", lambda c, m, s: _grid(days))
    out = hsp.normalize_scenario("India", "gfdl_esm4", "ssp585", 0.0, 80.0).values

    expected = np.clip((days - 0.0) / (80.0 - 0.0), 0.0, 1.0)
    np.testing.assert_allclose(out[~np.isnan(days)], expected[~np.isnan(days)], atol=1e-6)
    assert np.isnan(out[1, 0])
    assert str(out.dtype) == "float32"


def test_normalize_clips_outside_country_domain(monkeypatch):
    days = np.array([[-5.0, 100.0]])
    monkeypatch.setattr(hsp, "_load_heat_raster", lambda c, m, s: _grid(days))
    out = hsp.normalize_scenario("Portugal", "gfdl_esm4", "ssp126", 0.0, 50.0)
    np.testing.assert_array_equal(out.values, np.array([[0.0, 1.0]], dtype="float32"))


# --------------------------------------------------------------------------
# Multi-model iteration
# --------------------------------------------------------------------------
def test_process_all_countries_iterates_every_model(monkeypatch, tmp_path):
    monkeypatch.setattr(hsp, "CLIMATE_PROCESSED", tmp_path)
    monkeypatch.setattr(hsp, "configured_models", lambda: ["m1", "m2"])
    monkeypatch.setattr(hsp, "_load_heat_raster", lambda c, m, s: _grid(np.array([[0.0, 50.0]])))

    report = hsp.process_all_countries(countries=["Brazil"])
    assert set(report["countries"]["Brazil"]["models"]) == {"m1", "m2"}
    for model in ("m1", "m2"):
        scen = report["countries"]["Brazil"]["models"][model]["scenarios"]
        assert set(scen) == {"ssp126", "ssp585"}
        assert all(s["success"] for s in scen.values())
    assert (tmp_path / "heat_stress_Brazil_m1_ssp126_1km.tif").exists()
    assert (tmp_path / "heat_stress_Brazil_m2_ssp585_1km.tif").exists()
