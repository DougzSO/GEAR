"""Tests for cds_precipitation_downloader — variable+model-tagged paths, the
pr/tas request shape, reuse (not duplication) of the tasmax common-grid
helpers, raw-series validation, the QA period-mean unit conversion, and
credential handling. No CDS access."""

import numpy as np
import pandas as pd
import pytest
import rioxarray  # noqa: F401  (registers the .rio accessor)
import xarray as xr

from src import config
from src.downloaders import cds_precipitation_downloader as cdp
from src.downloaders import cds_tasmax_downloader as cds


def _synth_ds(short_name: str, n_days: int, start: str = "2041-01-01", value: float = 1.0):
    """A synthetic daily CMIP6-style dataset (time, lat, lon), EPSG:4326."""
    times = pd.date_range(start, periods=n_days, freq="D")
    lat = np.array([10.0, 9.0])
    lon = np.array([0.0, 1.0])
    data = np.full((n_days, 2, 2), value, dtype="float32")
    return xr.Dataset(
        {short_name: (("time", "lat", "lon"), data)},
        coords={"time": times, "lat": lat, "lon": lon},
    )


def test_output_paths_are_model_and_variable_tagged():
    assert cdp.raw_dir("Brazil", "gfdl_esm4", "ssp126", "pr").as_posix().endswith(
        "raw/climate/cds_spei/Brazil/gfdl_esm4/ssp126/pr"
    )
    assert (
        cdp.native_raster_path("India", "miroc6", "ssp585", "tas").name
        == "air_temperature_mean_India_miroc6_ssp585_native.tif"
    )
    assert (
        cdp.resampled_raster_path("India", "miroc6", "ssp585", "pr").name
        == "precipitation_mean_India_miroc6_ssp585_1km.tif"
    )


def test_spei_variables_default_is_pr_and_tas():
    assert cdp.spei_variables() == {
        "pr": "precipitation",
        "tas": "near_surface_air_temperature",
    }


def test_spei_variables_raises_when_empty(monkeypatch):
    monkeypatch.setattr(cdp, "CMIP6_SPEI_VARIABLES", {})
    with pytest.raises(ValueError):
        cdp.spei_variables()


def test_grid_helpers_are_the_tasmax_ones_not_copies():
    # The common corrected 1 km grid must have ONE definition shared with the
    # heat layer, not a divergent copy.
    assert cdp._resample_to_1km is cds._resample_to_1km
    assert cdp._country_area is cds._country_area
    assert cdp.configured_models is cds.configured_models


def test_build_request_carries_variable_model_experiment_and_area(monkeypatch):
    # _country_area -> _climate_bounds -> get_country_bounds / fallback all
    # live in the tasmax module.
    monkeypatch.setattr(cds, "get_country_bounds", lambda c: (-74.0, -34.0, -28.0, 5.0))
    monkeypatch.setattr(cds, "COUNTRY_BBOX_FALLBACK", {"Brazil": (-73.0, -33.0, -29.0, 4.0)})
    req = cdp._build_request("Brazil", "some_model", "ssp370", "precipitation")
    assert req["variable"] == "precipitation"
    assert req["model"] == "some_model"
    assert req["experiment"] == "ssp3_7_0"
    assert req["temporal_resolution"] == "daily"
    assert req["area"] == [5.0, -74.0, -34.0, -28.0]  # N, W, S, E
    assert req["year"][0] == "2041" and req["year"][-1] == "2070"


def test_period_mean_converts_pr_flux_to_mm_per_day_and_marks_qa_only(monkeypatch):
    monkeypatch.setattr(cdp, "_open_series", lambda files: _synth_ds("pr", 40, value=1e-4))
    da = cdp._period_mean(["x.nc"], "pr", "gfdl_esm4")
    # 1e-4 kg m-2 s-1 * 86400 s/day = 8.64 mm/day
    assert np.allclose(da.values, 8.64, rtol=1e-4)
    assert da.attrs["units"] == "mm_per_day"
    assert da.attrs["model"] == "gfdl_esm4"
    assert "NOT an SPEI input" in da.attrs["note"]


def test_period_mean_converts_tas_kelvin_to_celsius(monkeypatch):
    monkeypatch.setattr(cdp, "_open_series", lambda files: _synth_ds("tas", 40, value=300.0))
    da = cdp._period_mean(["x.nc"], "tas", "miroc6")
    assert np.allclose(da.values, 300.0 - 273.15)
    assert da.attrs["units"] == "degC"


def test_validate_raw_series_certifies_a_full_window(monkeypatch):
    monkeypatch.setattr(cdp, "_open_series", lambda files: _synth_ds("pr", 365 * 30, value=2.0))
    r = cdp.validate_raw_series(["x.nc"], "pr")
    assert r["variable"] == "pr"
    assert r["n_timesteps"] == 365 * 30
    assert r["covers_window"] is True
    assert r["plausible_daily_length"] is True
    assert r["finite_fraction_first_step"] == 1.0
    assert r["valid"] is True


def test_validate_raw_series_flags_a_truncated_series(monkeypatch):
    monkeypatch.setattr(cdp, "_open_series", lambda files: _synth_ds("pr", 500, value=2.0))
    r = cdp.validate_raw_series(["x.nc"], "pr")
    assert r["covers_window"] is False
    assert r["plausible_daily_length"] is False
    assert r["valid"] is False


def test_get_client_raises_without_api_key(monkeypatch):
    monkeypatch.setattr(config, "CDS_API_KEY", None)
    with pytest.raises(config.MissingCredentialError):
        cdp._get_client()


def test_download_raw_reports_failure_not_silent(monkeypatch, tmp_path):
    monkeypatch.setattr(cdp, "CLIMATE_RAW", tmp_path)

    def _boom():
        raise RuntimeError("cds down")

    monkeypatch.setattr(cdp, "_get_client", _boom)
    monkeypatch.setattr(cdp, "_build_request", lambda *a: {"stub": True})
    status = cdp._download_raw("Brazil", "gfdl_esm4", "ssp126", "pr", overwrite=True)
    assert status["success"] is False
    assert "cds_error" in status["reason"]


def test_process_iterates_both_variables_and_reports_validation(monkeypatch, tmp_path):
    monkeypatch.setattr(cdp, "CLIMATE_PROCESSED", tmp_path)
    monkeypatch.setattr(
        cdp,
        "_download_raw",
        lambda c, m, s, sn, o: {
            "success": True, "reason": "cached", "seconds": 0.0,
            "path": "d", "files": ["a.nc"],
        },
    )
    monkeypatch.setattr(
        cdp,
        "validate_raw_series",
        lambda files, sn: {"variable": sn, "valid": True, "n_timesteps": 10950},
    )
    # pre-create the 1 km rasters so the QA period-mean compute is skipped
    for sn in cdp.spei_variables():
        cdp.resampled_raster_path("Brazil", "gfdl_esm4", "ssp126", sn).touch()

    out = cdp.process_country_model_scenario("Brazil", "gfdl_esm4", "ssp126")
    assert out["success"] is True
    assert set(out["variables"]) == {"pr", "tas"}
    assert out["variables"]["pr"]["validation"]["valid"] is True
    assert out["variables"]["tas"]["resampled_path"].endswith(
        "air_temperature_mean_Brazil_gfdl_esm4_ssp126_1km.tif"
    )


def test_process_propagates_a_download_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(cdp, "CLIMATE_PROCESSED", tmp_path)
    monkeypatch.setattr(
        cdp,
        "_download_raw",
        lambda c, m, s, sn, o: {"success": sn == "tas", "reason": "cds_error: x", "path": None}
        if sn == "pr"
        else {"success": True, "reason": "cached", "seconds": 0.0, "path": "d", "files": ["a.nc"]},
    )
    monkeypatch.setattr(cdp, "validate_raw_series", lambda files, sn: {"valid": True})
    for sn in cdp.spei_variables():
        cdp.resampled_raster_path("India", "miroc6", "ssp370", sn).touch()

    out = cdp.process_country_model_scenario("India", "miroc6", "ssp370")
    assert out["success"] is False
    assert out["variables"]["pr"]["success"] is False


def test_download_all_iterates_every_model_and_scenario(monkeypatch):
    monkeypatch.setattr(cdp, "configured_models", lambda: ["m1", "m2"])
    monkeypatch.setattr(cdp, "CMIP6_SCENARIOS", ["ssp126", "ssp585", "ssp370"])
    seen = []
    monkeypatch.setattr(
        cdp,
        "process_country_model_scenario",
        lambda country, model, scenario, overwrite: seen.append((country, model, scenario))
        or {"success": True},
    )
    cdp.download_all_cds_precipitation(["Brazil"])
    assert seen == [
        ("Brazil", "m1", "ssp126"), ("Brazil", "m1", "ssp585"), ("Brazil", "m1", "ssp370"),
        ("Brazil", "m2", "ssp126"), ("Brazil", "m2", "ssp585"), ("Brazil", "m2", "ssp370"),
    ]
