"""Tests for src/index/general_mc.py -- GEAR v3 Phase 6.1's 9-stream
per-country-scenario general Monte Carlo driver. Real-data tests skip when
processed rasters are absent, same convention as
tests/test_sensitivity_recompute.py."""

import numpy as np
import pytest

from src.config import AQUEDUCT_SCENARIOS, COUNTRIES
from src.index import general_mc as gm
from src.index import risk_calculator as rc
from src.index import sensitivity_recompute as sr


def _rasters_present() -> bool:
    try:
        p = rc.raster_path("heat", "Brazil", "opt", rc.configured_models()[0])
        q = rc.raster_path("ws", "Brazil", "opt", rc.configured_models()[0])
        return p.exists() and q.exists()
    except Exception:
        return False


def test_streams_are_the_nine_country_scenario_pairs():
    assert len(gm.STREAMS) == 9
    assert set(gm.STREAMS) == {(c, s) for c in COUNTRIES for s in AQUEDUCT_SCENARIOS}


def test_draw_row_stays_within_param_bounds():
    from src.index import rng_utils
    from src.index import sobol_sensitivity as ss

    rng = rng_utils.phase6_rng("Brazil", "bau", "test")
    for _ in range(200):
        row = gm._draw_row(rng)
        for value, (lo, hi) in zip(row, ss.PARAM_BOUNDS):
            assert lo <= value <= hi


def test_draw_row_deterministic_per_stream():
    from src.index import rng_utils

    a = gm._draw_row(rng_utils.phase6_rng("India", "pes", "general_mc"))
    b = gm._draw_row(rng_utils.phase6_rng("India", "pes", "general_mc"))
    np.testing.assert_array_equal(a, b)


@pytest.mark.skipif(not _rasters_present(), reason="processed rasters absent -- cannot precompute")
def test_run_n_small_scale_covers_every_stream():
    pre = sr.precompute()
    res = gm.run_n(2, pre=pre, n_workers=2)
    assert res["n_total_draws"] == 9 * 2
    assert set(res["stream_stats"]) == set(gm.STREAMS)
    for stats in res["stream_stats"].values():
        assert stats["n"] == 2
        assert np.isfinite(stats["risk_mean"])
        assert stats["risk_ci"][0] <= stats["risk_mean"] <= stats["risk_ci"][1]


@pytest.mark.skipif(not _rasters_present(), reason="processed rasters absent -- cannot precompute")
def test_run_convergence_records_relative_change_on_second_step():
    pre = sr.precompute()
    steps = gm.run_convergence([2, 3], pre=pre, n_workers=2)
    assert len(steps) == 2
    for stats in steps[1]["stream_stats"].values():
        assert "risk_mean_relchange_vs_prev" in stats
        assert "psae_ci_halfwidth_relchange_vs_prev" in stats
