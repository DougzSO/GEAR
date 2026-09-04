"""Tests for spei_processor -- monthly aggregation from the raw daily
pr/tas series, the Thornthwaite PET formula, the day-length correction, the
rolling water-balance accumulation, the log-logistic PWM fit and SPEI
standardisation, the drought-frequency reduction, and the raster
read/normalise/cache pattern shared with heat_stress_processor. Synthetic
fixtures only, no CDS data."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import xarray as xr

from src.processors import spei_processor as sp
from src.processors.spei_processor import GridMismatchError


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _daily_series(n_days: int, values: np.ndarray, start: str = "2041-01-01") -> xr.DataArray:
    """A synthetic daily (time, lat, lon) DataArray. ``values`` broadcasts to
    (n_days, ny, nx)."""
    times = pd.date_range(start, periods=n_days, freq="D")
    values = np.broadcast_to(values, (n_days, *np.shape(values)[1:])) if np.ndim(values) > 1 else values
    return xr.DataArray(
        values, dims=("time", "lat", "lon"),
        coords={"time": times, "lat": np.asarray([0.0]), "lon": np.asarray([0.0, 10.0])},
    )


def _grid(values: np.ndarray) -> xr.DataArray:
    ny, nx = values.shape
    da = xr.DataArray(
        values.astype("float64"), dims=("y", "x"),
        coords={"y": -np.arange(ny, dtype="float64"), "x": np.arange(nx, dtype="float64")},
    )
    return da.rio.write_crs("EPSG:4326")


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
def test_paths_are_model_and_scenario_tagged():
    assert (
        sp.raw_raster_path("Brazil", "gfdl_esm4", "ssp585").name
        == "drought_stress_raw_Brazil_gfdl_esm4_ssp585_1km.tif"
    )
    assert (
        sp.normalized_raster_path("India", "miroc6", "ssp126").name
        == "drought_stress_India_miroc6_ssp126_1km.tif"
    )
    assert (
        sp.native_raster_path("Portugal", "gfdl_esm4", "ssp370").name
        == "drought_stress_raw_Portugal_gfdl_esm4_ssp370_native.tif"
    )


# --------------------------------------------------------------------------
# Monthly aggregation
# --------------------------------------------------------------------------
def test_monthly_aggregate_sums_precip_and_averages_temperature():
    # January (31 days) then February (28, non-leap 2041) at one pixel.
    pr = _daily_series(59, np.full((59, 1, 2), 1e-5))       # kg m-2 s-1
    tas = _daily_series(59, np.full((59, 1, 2), 293.15))    # 20 C

    pr_mm, tas_c, month_of, n_days, lat = sp._monthly_aggregate(pr, tas)
    assert list(month_of) == [1, 2]
    assert list(n_days) == [31, 28]
    # 1e-5 kg/m2/s * 86400 s/day * 31 days = 26.784 mm
    assert pr_mm[0, 0, 0] == pytest.approx(1e-5 * 86400 * 31)
    assert pr_mm[1, 0, 0] == pytest.approx(1e-5 * 86400 * 28)
    assert tas_c[0, 0, 0] == pytest.approx(20.0)
    assert lat.tolist() == [0.0]


def test_monthly_aggregate_rejects_shape_mismatch():
    pr = _daily_series(10, np.ones((10, 1, 2)))
    tas = xr.DataArray(
        np.ones((10, 1, 3)), dims=("time", "lat", "lon"),
        coords={"time": pr["time"], "lat": [0.0], "lon": [0.0, 5.0, 10.0]},
    )
    with pytest.raises(ValueError, match="shape mismatch"):
        sp._monthly_aggregate(pr, tas)


def test_monthly_aggregate_rejects_time_axis_mismatch():
    pr = _daily_series(10, np.ones((10, 1, 2)))
    tas = _daily_series(10, np.ones((10, 1, 2)), start="2041-02-01")
    with pytest.raises(ValueError, match="different time axes"):
        sp._monthly_aggregate(pr, tas)


# --------------------------------------------------------------------------
# Day length
# --------------------------------------------------------------------------
def test_day_length_at_equator_is_always_twelve_hours():
    out = sp._day_length_hours(np.array([0.0]), np.array([15.0, 196.0, 349.0]))
    np.testing.assert_allclose(out, 12.0, atol=1e-9)


def test_day_length_longer_in_local_summer_at_high_latitude():
    # Northern mid-latitude: day 172 (~June solstice) should be far longer
    # than day 355 (~December solstice).
    lat = np.array([45.0])
    summer = sp._day_length_hours(lat, np.array([172.0]))[0, 0]
    winter = sp._day_length_hours(lat, np.array([355.0]))[0, 0]
    assert summer > 14.0
    assert winter < 10.0


# --------------------------------------------------------------------------
# Thornthwaite PET
# --------------------------------------------------------------------------
def _reference_pet0(tas_c: np.ndarray, clim: np.ndarray) -> np.ndarray:
    """Independent re-implementation of the unadjusted (pre day-length) PET
    formula, straight from the module docstring, to check
    ``_thornthwaite_pet`` without re-using its own code."""
    heat_index = np.sum(np.clip(clim, 0.0, None) ** 1.514 / 5.0 ** 1.514)
    a = 6.75e-7 * heat_index ** 3 - 7.71e-5 * heat_index ** 2 + 1.792e-2 * heat_index + 0.49239
    return np.where(tas_c > 0.0, 16.0 * (10.0 * tas_c / heat_index) ** a, 0.0)


def test_thornthwaite_pet_matches_hand_formula_for_constant_temperature():
    # 24 months at 20 C, one pixel -- climatology is 20 C every calendar month.
    tas_c = np.full((24, 1, 1), 20.0)
    month_of = np.tile(np.arange(1, 13), 2)
    n_days = np.full(24, 30)
    lat = np.array([0.0])  # equator -> day-length factor exactly 1.0 (12/12 * NDM/30)

    pet = sp._thornthwaite_pet(tas_c, month_of, n_days, lat)
    expected0 = _reference_pet0(np.array(20.0), np.full(12, 20.0))
    assert pet[0, 0, 0] == pytest.approx(expected0, rel=1e-6)
    # NDM=30 and equatorial day length exactly cancels the correction factor.
    np.testing.assert_allclose(pet[:, 0, 0], expected0, rtol=1e-6)


def test_thornthwaite_pet_is_zero_for_non_positive_temperature():
    # 2 full years, one pixel: January stays below freezing every year, every
    # other month is a mild 15 C -- a full climatology, so the heat index is
    # well-defined (a partial climatology would leave most months NaN).
    month_of = np.tile(np.arange(1, 13), 2)
    n_days = np.full(24, 30)
    lat = np.array([50.0])
    tas_c = np.array([-5.0 if m == 1 else 15.0 for m in month_of]).reshape(24, 1, 1)

    pet = sp._thornthwaite_pet(tas_c, month_of, n_days, lat)
    jan_idx = np.where(month_of == 1)[0]
    jul_idx = np.where(month_of == 7)[0]
    assert np.all(pet[jan_idx, 0, 0] == 0.0)
    assert np.all(pet[jul_idx, 0, 0] > 0.0)


# --------------------------------------------------------------------------
# Rolling accumulation
# --------------------------------------------------------------------------
def test_rolling_accumulate_trailing_sum_and_ending_month():
    D = np.array([1.0, 2.0, 3.0, 4.0, 5.0]).reshape(5, 1, 1)
    month_of = np.array([1, 2, 3, 4, 5])
    D_accum, month_of_accum = sp._rolling_accumulate(D, month_of, scale=3)
    # windows: [1,2,3], [2,3,4], [3,4,5]
    np.testing.assert_allclose(D_accum[:, 0, 0], [6.0, 9.0, 12.0])
    np.testing.assert_array_equal(month_of_accum, [3, 4, 5])


def test_rolling_accumulate_rejects_too_short_series():
    D = np.zeros((2, 1, 1))
    with pytest.raises(ValueError, match="need at least"):
        sp._rolling_accumulate(D, np.array([1, 2]), scale=3)


# --------------------------------------------------------------------------
# Normal-quantile approximation
# --------------------------------------------------------------------------
def test_normal_quantile_is_zero_at_median_and_antisymmetric():
    assert sp._normal_quantile_from_cdf(np.array([0.5]))[0] == pytest.approx(0.0, abs=1e-6)
    lo = sp._normal_quantile_from_cdf(np.array([0.1]))[0]
    hi = sp._normal_quantile_from_cdf(np.array([0.9]))[0]
    assert lo < 0.0 < hi
    assert lo == pytest.approx(-hi, rel=1e-3)


# --------------------------------------------------------------------------
# Log-logistic fit + SPEI standardisation -- rank invariance
# --------------------------------------------------------------------------
def test_spei_preserves_rank_within_a_calendar_month():
    # One pixel, 6 "years" of all 12 calendar months (_fit_loglogistic always
    # fits every month); calendar month 6 is overwritten with a known,
    # clearly ordered sequence to check rank invariance on.
    n_years = 6
    month_of_accum = np.tile(np.arange(1, 13), n_years)
    rng = np.random.default_rng(1)
    D_accum = rng.normal(0.0, 5.0, size=(len(month_of_accum), 1, 1))

    idx6 = np.where(month_of_accum == 6)[0]
    known = np.array([-10.0, -2.0, 0.0, 1.0, 3.0, 8.0])
    D_accum[idx6, 0, 0] = known

    alpha, beta, gamma = sp._fit_loglogistic(D_accum, month_of_accum)
    spei = sp._spei_from_water_balance(D_accum, month_of_accum, alpha, beta, gamma)

    values = spei[idx6, 0, 0]
    assert np.all(np.diff(values) > 0)  # strictly increasing with D_accum
    # the driest year of the six should read as a below-median (negative) SPEI
    assert values[0] < 0.0
    assert values[-1] > 0.0


def test_fit_loglogistic_rejects_too_few_years():
    D_accum = np.zeros((2, 1, 1))
    with pytest.raises(ValueError, match="need >="):
        sp._fit_loglogistic(D_accum, np.array([6, 6]))


# --------------------------------------------------------------------------
# Drought frequency
# --------------------------------------------------------------------------
def test_drought_frequency_counts_months_at_or_below_threshold():
    spei = np.array([-2.0, -1.0, -0.5, 0.0, 1.0, 2.0]).reshape(6, 1, 1)
    freq = sp._drought_frequency(spei)
    # 2 of 6 months <= -1.0 -> 12 * 2/6 = 4.0 months/year
    assert freq[0, 0] == pytest.approx(4.0)


# --------------------------------------------------------------------------
# End-to-end: a drought-prone pixel reads a higher frequency than a stable one
# --------------------------------------------------------------------------
def test_compute_drought_frequency_flags_the_dry_pixel_more_than_the_stable_one():
    rng = np.random.default_rng(0)
    n_years = 8
    n_days = 365 * n_years
    times = pd.date_range("2041-01-01", periods=n_days, freq="D")
    month_index = times.month.values
    year_index = times.year.values

    # Pixel 0 ("stable"): mild seasonal cycle, small noise, no anomalies.
    # Pixel 1 ("dry"): same climate, but January of every other year gets a
    # severe precipitation deficit -- a repeated, detectable drought signal.
    base_temp = 293.15 + 5.0 * np.sin(2 * np.pi * (month_index - 1) / 12.0)
    base_precip = 3e-5 + 1e-5 * np.sin(2 * np.pi * (month_index - 4) / 12.0)

    tas_vals = np.stack([base_temp, base_temp], axis=-1)[:, None, :]  # (T, 1, 2)
    tas_vals = tas_vals + rng.normal(0, 0.2, size=tas_vals.shape)

    pr_stable = base_precip + rng.normal(0, 2e-6, size=base_precip.shape)
    pr_dry = base_precip.copy()
    drought_years = set(range(2041, 2041 + n_years, 2))
    dry_mask = (month_index == 1) & np.isin(year_index, list(drought_years))
    pr_dry = np.where(dry_mask, 1e-7, pr_dry) + rng.normal(0, 2e-6, size=pr_dry.shape)

    pr_vals = np.clip(np.stack([pr_stable, pr_dry], axis=-1)[:, None, :], 0.0, None)

    pr_da = xr.DataArray(
        pr_vals, dims=("time", "lat", "lon"),
        coords={"time": times, "lat": [10.0], "lon": [0.0, 10.0]},
    )
    tas_da = xr.DataArray(
        tas_vals, dims=("time", "lat", "lon"),
        coords={"time": times, "lat": [10.0], "lon": [0.0, 10.0]},
    )

    freq = sp.compute_drought_frequency(pr_da, tas_da, scale=3)
    stable_freq = float(freq.values[0, 0])
    dry_freq = float(freq.values[0, 1])

    assert np.isfinite(stable_freq) and np.isfinite(dry_freq)
    assert dry_freq > stable_freq
    assert freq.attrs["units"] == sp.RAW_UNITS
    assert "CCRS Hazard term" in freq.attrs["note"]


# --------------------------------------------------------------------------
# Raster read / grid guard / Min-Max normalisation (mirrors heat_stress_processor)
# --------------------------------------------------------------------------
def _patch_rasters(monkeypatch, data: dict):
    monkeypatch.setattr(sp, "_load_raw_raster", lambda c, m, s: _grid(data[(m, s)]))
    models = sorted({m for m, _ in data})
    scenarios = sorted({s for _, s in data})
    monkeypatch.setattr(sp, "configured_models", lambda: models)
    monkeypatch.setattr(sp, "CMIP6_SCENARIOS", scenarios)


def test_grid_mismatch_shape_fails_loud(monkeypatch):
    monkeypatch.setattr(sp, "configured_models", lambda: ["m_a", "m_b"])

    def fake_load(country, model, scenario):
        shape = (2, 2) if model == "m_a" else (2, 3)
        return _grid(np.ones(shape))

    monkeypatch.setattr(sp, "_load_raw_raster", fake_load)
    with pytest.raises(GridMismatchError, match="shape"):
        sp.compute_country_minmax("India")


def test_minmax_pools_models_and_scenarios_jointly(monkeypatch):
    _patch_rasters(monkeypatch, {
        ("gfdl_esm4", "ssp126"): np.array([[0.0, 1.0]]),
        ("gfdl_esm4", "ssp585"): np.array([[0.5, 4.0]]),
        ("miroc6", "ssp126"): np.array([[0.2, 2.0]]),
        ("miroc6", "ssp585"): np.array([[0.1, 6.0]]),  # joint max
    })
    cmin, cmax = sp.compute_country_minmax("India")
    assert cmin == pytest.approx(0.0)
    assert cmax == pytest.approx(6.0)


def test_normalize_matches_minmax_formula_and_preserves_nan(monkeypatch):
    freq = np.array([[0.0, 3.0, 6.0], [np.nan, 1.5, 12.0]])
    monkeypatch.setattr(sp, "_load_raw_raster", lambda c, m, s: _grid(freq))
    out = sp.normalize_scenario("India", "gfdl_esm4", "ssp585", 0.0, 12.0).values

    expected = np.clip(freq / 12.0, 0.0, 1.0)
    np.testing.assert_allclose(out[~np.isnan(freq)], expected[~np.isnan(freq)], atol=1e-6)
    assert np.isnan(out[1, 0])
    assert str(out.dtype) == "float32"


def test_ensure_raw_raster_computes_once_then_caches(monkeypatch, tmp_path):
    monkeypatch.setattr(sp, "CLIMATE_PROCESSED", tmp_path)
    calls = []

    def fake_native(country, model, scenario, scale=sp.SPEI_ACCUMULATION_MONTHS):
        calls.append((country, model, scenario))
        return xr.DataArray(
            np.array([[1.0, 2.0]]), dims=("lat", "lon"),
            coords={"lat": [10.0], "lon": [0.0, 10.0]},
        ).rio.write_crs("EPSG:4326")

    monkeypatch.setattr(sp, "_compute_native", fake_native)
    monkeypatch.setattr(sp, "_resample_to_1km", lambda da, country: da)

    first = sp.ensure_raw_raster("Brazil", "gfdl_esm4", "ssp126")
    assert first["success"] is True and first["reason"] == "processed"
    assert len(calls) == 1

    second = sp.ensure_raw_raster("Brazil", "gfdl_esm4", "ssp126")
    assert second["reason"] == "cached"
    assert len(calls) == 1  # not recomputed


def test_ensure_raw_raster_reports_missing_dependency(monkeypatch, tmp_path):
    monkeypatch.setattr(sp, "CLIMATE_PROCESSED", tmp_path)

    def boom(country, model, scenario, scale=sp.SPEI_ACCUMULATION_MONTHS):
        raise FileNotFoundError("no raw .nc files")

    monkeypatch.setattr(sp, "_compute_native", boom)
    result = sp.ensure_raw_raster("India", "miroc6", "ssp370")
    assert result["success"] is False
    assert "missing_dependency" in result["reason"]


def test_process_country_model_scenario_marks_raw_as_computed(monkeypatch, tmp_path):
    monkeypatch.setattr(sp, "CLIMATE_PROCESSED", tmp_path)
    freq = np.array([[0.0, 6.0]])
    monkeypatch.setattr(sp, "_load_raw_raster", lambda c, m, s: _grid(freq))

    rep = sp.process_country_model_scenario("India", "gfdl_esm4", "ssp585", 0.0, 6.0, overwrite=True)
    assert rep["success"] is True
    assert rep["raw_kind"] == "computed"
    assert rep["raw_units"] == sp.RAW_UNITS
    assert (tmp_path / "drought_stress_India_gfdl_esm4_ssp585_1km.tif").exists()


def test_process_all_countries_shares_one_domain_across_models(monkeypatch, tmp_path):
    monkeypatch.setattr(sp, "CLIMATE_PROCESSED", tmp_path)
    monkeypatch.setattr(sp, "configured_models", lambda: ["m1", "m2"])
    monkeypatch.setattr(sp, "CMIP6_SCENARIOS", ["ssp126", "ssp585"])
    monkeypatch.setattr(
        sp, "ensure_raw_raster",
        lambda country, model, scenario, scale=sp.SPEI_ACCUMULATION_MONTHS, overwrite=False:
            {"success": True, "path": "x", "reason": "processed"},
    )
    _patch_rasters(monkeypatch, {
        ("m1", "ssp126"): np.array([[0.0, 2.0]]),
        ("m1", "ssp585"): np.array([[1.0, 3.0]]),
        ("m2", "ssp126"): np.array([[0.5, 5.0]]),   # joint max
        ("m2", "ssp585"): np.array([[0.2, 4.0]]),
    })
    report = sp.process_all_countries(countries=["Brazil"])
    brazil = report["countries"]["Brazil"]
    assert brazil["country_min"] == pytest.approx(0.0)
    assert brazil["country_max"] == pytest.approx(5.0)
    assert set(brazil["models"]) == {"m1", "m2"}
