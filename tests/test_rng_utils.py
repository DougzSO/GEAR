"""Tests for src/index/rng_utils.py -- GEAR v3 Phase 6's per-country-scenario
RNG stream utility. No raster/plant data needed (pure function), unlike
tests/test_sensitivity_recompute.py's real-data suite."""

import numpy as np

from src.index.rng_utils import phase6_rng


def test_phase6_rng_is_deterministic():
    a = phase6_rng("Brazil", "bau", "general_mc").random(10)
    b = phase6_rng("Brazil", "bau", "general_mc").random(10)
    np.testing.assert_array_equal(a, b)


def test_phase6_rng_independent_across_country():
    a = phase6_rng("Brazil", "bau", "general_mc").random(50)
    b = phase6_rng("Portugal", "bau", "general_mc").random(50)
    assert not np.array_equal(a, b)


def test_phase6_rng_independent_across_scenario():
    a = phase6_rng("Brazil", "bau", "general_mc").random(50)
    b = phase6_rng("Brazil", "opt", "general_mc").random(50)
    assert not np.array_equal(a, b)


def test_phase6_rng_independent_across_purpose():
    a = phase6_rng("Brazil", "bau", "general_mc").random(50)
    b = phase6_rng("Brazil", "bau", "sobol").random(50)
    assert not np.array_equal(a, b)


def test_phase6_rng_returns_generator():
    rng = phase6_rng("India", "pes", "general_mc")
    assert isinstance(rng, np.random.Generator)


def test_phase6_rng_covers_every_country_scenario_pair_without_collision():
    """The 9 (country, scenario) streams general_mc.py actually drives (3
    countries x 3 AQUEDUCT_SCENARIOS) must be pairwise distinct -- a
    collision here would silently correlate two scenario draws that are
    supposed to be independent."""
    from src.config import COUNTRIES, AQUEDUCT_SCENARIOS

    draws = {
        (c, s): phase6_rng(c, s, "general_mc").random(20)
        for c in COUNTRIES for s in AQUEDUCT_SCENARIOS
    }
    keys = list(draws)
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            assert not np.array_equal(draws[keys[i]], draws[keys[j]]), (
                f"collision between streams {keys[i]} and {keys[j]}"
            )
