"""Tests for src/index/sobol_sensitivity.py -- GEAR v3 Phase 6.2's SALib
Sobol driver. Real-data tests (anything calling ``sensitivity_recompute.
precompute``/``run_sobol_draws_parallel``) are skipped when processed
rasters are absent, mirroring tests/test_sensitivity_recompute.py's own
skip condition -- not duplicated logic, same convention."""

import numpy as np
import pytest

from src.index import risk_bands as rb
from src.index import risk_calculator as rc
from src.index import sensitivity_recompute as sr
from src.index import sobol_sensitivity as ss


def _rasters_present() -> bool:
    try:
        p = rc.raster_path("heat", "Brazil", "opt", rc.configured_models()[0])
        q = rc.raster_path("ws", "Brazil", "opt", rc.configured_models()[0])
        return p.exists() and q.exists()
    except Exception:
        return False


# --------------------------------------------------------------------------
# Pure-function tests -- no I/O, always run
# --------------------------------------------------------------------------
def test_problem_has_thirteen_dimensions():
    assert ss.PROBLEM["num_vars"] == 13
    assert len(ss.PROBLEM["names"]) == 13
    assert len(ss.PROBLEM["bounds"]) == 13


def test_problem_bounds_match_the_closed_d13_table():
    expected = dict(zip(ss.PARAM_NAMES, ss.PARAM_BOUNDS))
    assert expected["coal_decay_rate"] == [0.0019, 0.0044]
    assert expected["wind_relative_rate"] == [0.0030, 0.0050]
    assert expected["hydro_retention_rate"] == [0.0050, 0.0060]
    assert expected["solar_retention_rate"] == [0.0056, 0.0084]
    assert expected["coal_overhaul_cycle_years"] == [4.0, 6.0]
    assert expected["coal_overhaul_recovery"] == [0.56, 0.84]
    assert expected["upper_tail_padding_fraction"] == [0.04, 0.06]
    for hazard in ("spei", "precip", "heat", "sv", "iv", "wind"):
        assert expected[f"{hazard}_percentile_shift"] == [-5.0, 5.0]


def test_hazard_name_to_keys_matches_threshold_registry_percentile_entries():
    percentile_keys = {k for k, spec in rb.THRESHOLD_REGISTRY.items() if spec.kind == "percentile"}
    covered = {k for keys in ss._HAZARD_NAME_TO_KEYS.values() for k in keys}
    assert percentile_keys == covered


def test_precip_shift_applies_identically_to_all_three_buckets():
    row = np.zeros(13)
    row[ss.PARAM_NAMES.index("precip_percentile_shift")] = 3.0
    _, percentile_overrides, _ = ss.row_to_params(row)
    base = rb.THRESHOLD_REGISTRY[("precip", "hydro")].percentiles
    expected = tuple(p + 3.0 for p in base)
    for bucket in ("hydro", "thermal", "solar"):
        assert percentile_overrides[("precip", bucket)] == expected


def test_heat_shift_applies_identically_to_both_buckets():
    row = np.zeros(13)
    row[ss.PARAM_NAMES.index("heat_percentile_shift")] = -2.0
    _, percentile_overrides, _ = ss.row_to_params(row)
    base = rb.THRESHOLD_REGISTRY[("heat", "thermal")].percentiles
    expected = tuple(max(p - 2.0, 0.0) for p in base)
    assert percentile_overrides[("heat", "thermal")] == expected
    assert percentile_overrides[("heat", "solar")] == expected


def test_wind_shift_clips_near_the_ceiling():
    """wind's top base percentile is 99.0 -- a +5 shift must clip to +0.5
    (ceiling 99.5), never push the top cut to 104."""
    row = np.zeros(13)
    row[ss.PARAM_NAMES.index("wind_percentile_shift")] = 5.0
    _, percentile_overrides, _ = ss.row_to_params(row)
    shifted = percentile_overrides[("wind", "solar")]
    assert max(shifted) <= ss.WIND_PERCENTILE_CEILING + 1e-9
    base = rb.THRESHOLD_REGISTRY[("wind", "solar")].percentiles
    assert max(base) == 99.0
    assert max(shifted) == pytest.approx(99.5)


def test_wind_negative_shift_not_clipped():
    row = np.zeros(13)
    row[ss.PARAM_NAMES.index("wind_percentile_shift")] = -5.0
    _, percentile_overrides, _ = ss.row_to_params(row)
    base = rb.THRESHOLD_REGISTRY[("wind", "solar")].percentiles
    expected = tuple(p - 5.0 for p in base)
    assert percentile_overrides[("wind", "solar")] == expected


def test_row_to_params_zero_row_reproduces_nominal_rates():
    row = np.zeros(13)
    row[ss.PARAM_NAMES.index("coal_decay_rate")] = 0.0025
    row[ss.PARAM_NAMES.index("wind_relative_rate")] = 0.004
    row[ss.PARAM_NAMES.index("hydro_retention_rate")] = 0.0055
    row[ss.PARAM_NAMES.index("solar_retention_rate")] = 0.007
    row[ss.PARAM_NAMES.index("coal_overhaul_cycle_years")] = 5.0
    row[ss.PARAM_NAMES.index("coal_overhaul_recovery")] = 0.70
    row[ss.PARAM_NAMES.index("upper_tail_padding_fraction")] = 0.05
    rate_overrides, percentile_overrides, padding = ss.row_to_params(row)
    assert rate_overrides["coal_decay_rate"] == pytest.approx(0.0025)
    assert padding == pytest.approx(0.05)
    for key, spec in rb.THRESHOLD_REGISTRY.items():
        if spec.kind == "percentile":
            assert percentile_overrides[key] == spec.percentiles


def test_sample_problem_evaluation_count_matches_calc_second_order_false_formula():
    n0 = 4
    rows = ss.sample_problem(n0, calc_second_order=False, seed=1)
    assert rows.shape == (n0 * (13 + 2), 13)


def test_nanaverage_skips_nan_rows():
    values = np.array([1.0, np.nan, 3.0])
    weights = np.array([1.0, 5.0, 1.0])
    assert ss._nanaverage(values, weights) == pytest.approx(2.0)


def test_nanaverage_all_nan_returns_nan():
    values = np.array([np.nan, np.nan])
    weights = np.array([1.0, 1.0])
    assert np.isnan(ss._nanaverage(values, weights))


# --------------------------------------------------------------------------
# Real-data, small-scale end-to-end test
# --------------------------------------------------------------------------
@pytest.mark.skipif(not _rasters_present(), reason="processed rasters absent -- cannot precompute")
def test_run_validation_small_scale_produces_bounded_indices():
    pre = sr.precompute()
    res = ss.run_validation(2, pre=pre, n_workers=2, seed=1)
    assert res["n_evals"] == 2 * (13 + 2)
    assert np.isfinite(res["Y_risk"]).all()
    assert np.isfinite(res["Y_psae"]).all() or np.isnan(res["Y_psae"]).any() is False
    # S1/ST are bounded on [0, 1] in theory; small-N bootstrap noise can push
    # a value slightly outside that range, so this asserts they are at least
    # not wildly outside it, not a strict [0, 1] clip.
    for sob in (res["sobol_risk"], res["sobol_psae"]):
        assert np.all(np.abs(sob["S1"]) < 3.0)
        assert np.all(np.abs(sob["ST"]) < 3.0)
