"""Tests for cds_tasmax_downloader — model-tagged path construction, multi
source_id iteration, request shape, the common cross-model 1 km grid, and
credential handling. No CDS access."""

import numpy as np
import pytest
import rioxarray  # noqa: F401  (registers the .rio accessor)
import xarray as xr

from src import config
from src.downloaders import cds_tasmax_downloader as cds


def _native_grid(res_lat, res_lon, x0, y0, nx, ny):
    """A synthetic GCM-native ``extreme_heat_days`` array (lat, lon) in
    EPSG:4326, north-up."""
    lon = x0 + np.arange(nx) * res_lon
    lat = y0 - np.arange(ny) * res_lat
    da = xr.DataArray(
        np.arange(ny * nx, dtype="float32").reshape(ny, nx),
        dims=("lat", "lon"),
        coords={"lat": lat, "lon": lon},
    )
    da = da.rio.set_spatial_dims(x_dim="lon", y_dim="lat")
    return da.rio.write_crs("EPSG:4326")


def test_output_paths_are_model_tagged():
    assert cds.raw_dir("Brazil", "gfdl_esm4", "ssp126").as_posix().endswith(
        "raw/climate/cds_tasmax/Brazil/gfdl_esm4/ssp126"
    )
    assert (
        cds.native_raster_path("India", "gfdl_esm4", "ssp585").name
        == "extreme_heat_days_India_gfdl_esm4_ssp585_native.tif"
    )
    assert (
        cds.resampled_raster_path("India", "gfdl_esm4", "ssp585").name
        == "extreme_heat_days_India_gfdl_esm4_ssp585_1km.tif"
    )


def test_configured_models_filters_pending_slot(monkeypatch):
    monkeypatch.setattr(config, "CMIP6_SOURCE_ID_CDS", ["gfdl_esm4", ""])
    monkeypatch.setattr(cds, "CMIP6_SOURCE_ID_CDS", ["gfdl_esm4", ""])
    assert cds.configured_models() == ["gfdl_esm4"]


def test_configured_models_raises_when_empty(monkeypatch):
    monkeypatch.setattr(cds, "CMIP6_SOURCE_ID_CDS", [])
    with pytest.raises(ValueError):
        cds.configured_models()


def test_build_request_carries_model_experiment_and_area(monkeypatch):
    monkeypatch.setattr(cds, "get_country_bounds", lambda c: (-74.0, -34.0, -28.0, 5.0))
    # floor box fully inside the geometry bounds -> union == geometry bounds
    monkeypatch.setattr(cds, "COUNTRY_BBOX_FALLBACK", {"Brazil": (-73.0, -33.0, -29.0, 4.0)})
    req = cds._build_request("Brazil", "some_model", "ssp585")
    assert req["model"] == "some_model"
    assert req["experiment"] == "ssp5_8_5"
    assert req["area"] == [5.0, -74.0, -34.0, -28.0]  # N, W, S, E
    assert req["year"][0] == "2041" and req["year"][-1] == "2070"


def test_climate_bounds_unions_gadm_and_floor(monkeypatch):
    monkeypatch.setattr(cds, "get_country_bounds", lambda c: (68.2, 6.8, 97.2, 33.3))
    monkeypatch.setattr(cds, "COUNTRY_BBOX_FALLBACK", {"India": (67.5, 6.5, 97.5, 37.5)})
    # each coordinate takes the wider of the two sources
    assert cds._climate_bounds("India") == (67.5, 6.5, 97.5, 37.5)

    monkeypatch.setattr(cds, "get_country_bounds", lambda c: (67.0, 5.0, 98.0, 38.0))
    assert cds._climate_bounds("India") == (67.0, 5.0, 98.0, 38.0)


def test_target_grid_depends_only_on_bounds_and_resolution(monkeypatch):
    monkeypatch.setattr(cds, "get_country_bounds", lambda c: (-9.5, 37.0, -6.2, 42.15))
    monkeypatch.setattr(cds, "COUNTRY_BBOX_FALLBACK", {"Portugal": (-9.75, 36.75, -6.0, 43.0)})
    transform, width, height = cds._target_grid("Portugal")
    res = config.RESOLUTION_TARGET_DEG
    # union bounds = (-9.75, 36.75, -6.0, 43.0)
    assert width == cds.math.ceil((-6.0 - -9.75) / res)
    assert height == cds.math.ceil((43.0 - 36.75) / res)
    assert (transform.a, transform.e) == (res, -res)
    assert (transform.c, transform.f) == (-9.75, 43.0)  # top-left origin


def test_resample_gives_identical_grid_for_different_native_resolutions(monkeypatch):
    # gfdl_esm4 is ~1.25x1 deg, miroc6 ~1.4x1.4 deg, with different native
    # origins. After _resample_to_1km both must land on the SAME grid.
    monkeypatch.setattr(cds, "get_country_bounds", lambda c: (-9.5, 37.0, -6.2, 42.15))
    monkeypatch.setattr(cds, "COUNTRY_BBOX_FALLBACK", {"Portugal": (-9.75, 36.75, -6.0, 43.0)})

    like_gfdl = _native_grid(1.0, 1.25, x0=-10.0, y0=43.0, nx=5, ny=7)
    like_miroc6 = _native_grid(1.40076, 1.40625, x0=-9.140625, y0=43.4237, nx=4, ny=6)

    a = cds._resample_to_1km(like_gfdl, "Portugal")
    b = cds._resample_to_1km(like_miroc6, "Portugal")

    assert a.rio.shape == b.rio.shape
    assert a.rio.transform() == b.rio.transform()
    assert a.rio.crs == b.rio.crs
    # and that grid is exactly _target_grid's
    transform, width, height = cds._target_grid("Portugal")
    assert a.rio.shape == (height, width)
    assert a.rio.transform() == transform


def test_country_area_uses_the_unioned_northern_extent(monkeypatch):
    monkeypatch.setattr(cds, "get_country_bounds", lambda c: (68.2, 6.8, 97.2, 33.3))
    monkeypatch.setattr(cds, "COUNTRY_BBOX_FALLBACK", {"India": (67.5, 6.5, 97.5, 37.5)})
    # N, W, S, E — northern extent comes from the floor box, not GADM's 33.3
    assert cds._country_area("India") == [37.5, 67.5, 6.5, 97.5]


def test_get_client_raises_without_api_key(monkeypatch):
    monkeypatch.setattr(config, "CDS_API_KEY", None)
    with pytest.raises(config.MissingCredentialError):
        cds._get_client()


def test_download_raw_reports_failure_not_silent(monkeypatch, tmp_path):
    monkeypatch.setattr(cds, "CLIMATE_RAW", tmp_path)

    def _boom():
        raise RuntimeError("cds down")

    monkeypatch.setattr(cds, "_get_client", _boom)
    monkeypatch.setattr(cds, "_build_request", lambda *a: {"stub": True})
    status = cds._download_raw("Brazil", "gfdl_esm4", "ssp126", overwrite=True)
    assert status["success"] is False
    assert "cds_error" in status["reason"]


def test_download_all_iterates_every_model_and_scenario(monkeypatch):
    monkeypatch.setattr(cds, "configured_models", lambda: ["m1", "m2"])
    monkeypatch.setattr(cds, "CMIP6_SCENARIOS", ["ssp126", "ssp585", "ssp370"])
    seen = []
    monkeypatch.setattr(
        cds,
        "process_country_model_scenario",
        lambda country, model, scenario, overwrite: seen.append((country, model, scenario))
        or {"success": True},
    )
    cds.download_all_cds_tasmax(["Brazil"])
    assert seen == [
        ("Brazil", "m1", "ssp126"), ("Brazil", "m1", "ssp585"), ("Brazil", "m1", "ssp370"),
        ("Brazil", "m2", "ssp126"), ("Brazil", "m2", "ssp585"), ("Brazil", "m2", "ssp370"),
    ]
