"""Tests for cds_tasmax_downloader — model-tagged path construction, multi
source_id iteration, request shape, and credential handling. No CDS access."""

import pytest

from src import config
from src.downloaders import cds_tasmax_downloader as cds


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
    seen = []
    monkeypatch.setattr(
        cds,
        "process_country_model_scenario",
        lambda country, model, scenario, overwrite: seen.append((country, model, scenario))
        or {"success": True},
    )
    cds.download_all_cds_tasmax(["Brazil"])
    assert seen == [
        ("Brazil", "m1", "ssp126"), ("Brazil", "m1", "ssp585"),
        ("Brazil", "m2", "ssp126"), ("Brazil", "m2", "ssp585"),
    ]
