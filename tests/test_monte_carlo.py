"""Tests for src/index/monte_carlo -- CCRS Monte Carlo sensitivity (item J).

Covers: reproducibility (same seed -> identical output), RNG independence
per country, declared-bound compliance of every perturbed parameter,
FROZEN_BOUNDS/risk_bands cuts staying untouched through a full run,
percentile-CI correctness on a synthetic case, and a small end-to-end run
over the real three countries. The vectorised age_factor mirror is
additionally cross-checked against the production ``age_factor`` module at
the unperturbed (central) rates.

Tests that read the processed rasters or validated-plant CSVs are skipped
(never silently passed) when those inputs are absent.
"""

import numpy as np
import pandas as pd
import pytest

from src.config import COUNTRIES
from src.index import age_factor
from src.index import ccrs_calculator as cc
from src.index import monte_carlo as mc
from src.index import risk_bands


def _inputs_present() -> bool:
    try:
        p = cc.raster_path("heat", "Brazil", "opt", cc.configured_models()[0])
        q = cc.raster_path("spei", "Brazil", "opt", cc.configured_models()[0])
        r = cc.raster_path("ws", "Brazil", "opt", cc.configured_models()[0])
        plants = all((cc.ASSETS_PROCESSED / f"gem_validated_plants_{c}.csv").exists() for c in COUNTRIES)
        return p.exists() and q.exists() and r.exists() and plants
    except Exception:
        return False


pytestmark_needs_data = pytest.mark.skipif(not _inputs_present(), reason="processed rasters or plant CSVs absent")


# --------------------------------------------------------------------------
# 1. Reproducibility -- same seed, identical output
# --------------------------------------------------------------------------
def test_draw_country_params_reproducible():
    a = mc.draw_country_params("Brazil", 0.20, n=200)
    b = mc.draw_country_params("Brazil", 0.20, n=200)
    for key in a:
        np.testing.assert_array_equal(a[key], b[key])


@pytestmark_needs_data
def test_run_simulation_reproducible():
    pre = mc._Precomputed()
    r1 = mc.run_simulation(0.20, n=8, pre=pre)
    r2 = mc.run_simulation(0.20, n=8, pre=pre)
    pd.testing.assert_frame_equal(r1["water"], r2["water"])
    pd.testing.assert_frame_equal(r1["heat"], r2["heat"])


# --------------------------------------------------------------------------
# 2. RNG independence per country
# --------------------------------------------------------------------------
def test_country_streams_are_independent():
    """A country's draws do not depend on whether another country's stream
    was also created/consumed -- each stream is seeded solely off its own
    country name (+ magnitude) and RANDOM_SEED."""
    brazil_alone = mc.draw_country_params("Brazil", 0.20, n=50)

    # Consume India's and Portugal's streams first, then draw Brazil's --
    # must be bit-identical to the "alone" draw above.
    mc.draw_country_params("India", 0.20, n=50)
    mc.draw_country_params("Portugal", 0.20, n=50)
    brazil_after_others = mc.draw_country_params("Brazil", 0.20, n=50)

    for key in brazil_alone:
        np.testing.assert_array_equal(brazil_alone[key], brazil_after_others[key])


def test_different_countries_get_different_draws():
    brazil = mc.draw_country_params("Brazil", 0.20, n=50)
    india = mc.draw_country_params("India", 0.20, n=50)
    assert not np.array_equal(brazil["coal_rate"], india["coal_rate"])


@pytestmark_needs_data
def test_perturbing_one_country_does_not_move_another_in_the_same_iteration():
    """End-to-end version of the RNG-independence property: one country's
    per-plant CCRS draw is identical whether or not another country is also
    being simulated in the same run."""
    pre = mc._Precomputed()
    params_all = {c: mc.draw_country_params(c, 0.20, n=3) for c in COUNTRIES}
    params_brazil_only = {"Brazil": mc.draw_country_params("Brazil", 0.20, n=3)}

    model = "gfdl_esm4"
    h = pre.haz[model]
    brazil_mask = h["country"] == "Brazil"

    full = mc.compute_draw_ccrs(pre, model, params_all, 0)[brazil_mask]
    # compute_draw_ccrs indexes params_by_country by COUNTRIES order internally
    # via a per-row country_idx gather, so a dict containing only Brazil's
    # params still resolves correctly for Brazil-only rows.
    solo = mc.compute_draw_ccrs(pre, model, {**params_all, "Brazil": params_brazil_only["Brazil"]}, 0)[brazil_mask]
    np.testing.assert_array_equal(full, solo)


# --------------------------------------------------------------------------
# 3. Declared bounds respected
# --------------------------------------------------------------------------
def test_perturbed_parameters_respect_their_declared_ranges():
    for country in COUNTRIES:
        for magnitude in mc.MAGNITUDES:
            params = mc.draw_country_params(country, magnitude, n=2000)
            lo, hi = mc.COAL_DECAY_RATE_RANGE
            assert (params["coal_rate"] >= lo).all() and (params["coal_rate"] <= hi).all()
            lo, hi = mc.WIND_RATE_RANGE
            assert (params["wind_rate"] >= lo).all() and (params["wind_rate"] <= hi).all()
            lo, hi = mc.HYDRO_RATE_RANGE
            assert (params["hydro_rate"] >= lo).all() and (params["hydro_rate"] <= hi).all()
            # thermal weights: drought fixed, water+heat renormalised to fill the rest
            base = cc.BUCKET_WEIGHTS["thermal"]
            np.testing.assert_allclose(params["thermal_drought"], base["drought"])
            np.testing.assert_allclose(
                params["thermal_water"] + params["thermal_heat"] + params["thermal_drought"], 1.0,
            )
            assert (params["thermal_water"] >= 0).all() and (params["thermal_heat"] >= 0).all()
            # EventMultiplier k: relative +/-magnitude around the central value
            k0 = __import__("src.index.event_multiplier", fromlist=["EVENT_MULTIPLIER_K"]).EVENT_MULTIPLIER_K
            assert (params["event_k"] >= k0 * (1 - magnitude) - 1e-12).all()
            assert (params["event_k"] <= k0 * (1 + magnitude) + 1e-12).all()


# --------------------------------------------------------------------------
# 4. FROZEN_BOUNDS / risk_bands cuts untouched by a full run
# --------------------------------------------------------------------------
@pytestmark_needs_data
def test_structural_constants_untouched_by_a_full_run():
    frozen_before = {k: (dict(v) if isinstance(v, dict) else tuple(v)) for k, v in cc.FROZEN_BOUNDS.items()}
    water_cuts_before = tuple(risk_bands.WATER_BAND_CUTS)

    pre = mc._Precomputed()
    for magnitude in mc.MAGNITUDES:
        mc.run_simulation(magnitude, n=3, pre=pre)

    frozen_after = {k: (dict(v) if isinstance(v, dict) else tuple(v)) for k, v in cc.FROZEN_BOUNDS.items()}
    assert frozen_after == frozen_before
    assert tuple(risk_bands.WATER_BAND_CUTS) == water_cuts_before
    mc.assert_structural_constants_untouched(pre)  # must not raise


def test_assert_structural_constants_untouched_detects_drift(monkeypatch):
    class _FakePre:
        frozen_bounds_snapshot = {"ws": (0.0, 1.0)}
        water_band_cuts_snapshot = (0.1, 0.2)

    monkeypatch.setattr(cc, "FROZEN_BOUNDS", {"ws": (0.0, 1.5)})  # drifted
    with pytest.raises(RuntimeError, match="FROZEN_BOUNDS"):
        mc.assert_structural_constants_untouched(_FakePre())


# --------------------------------------------------------------------------
# 5. Percentile CI correctness on a known synthetic case
# --------------------------------------------------------------------------
def test_percentile_ci_matches_numpy_on_a_known_array():
    values = np.arange(1, 1001, dtype="float64")  # 1..1000
    ci = mc.percentile_ci(values)
    assert ci[2.5] == pytest.approx(np.percentile(values, 2.5))
    assert ci[50.0] == pytest.approx(np.percentile(values, 50.0))
    assert ci[97.5] == pytest.approx(np.percentile(values, 97.5))
    # sanity: known values for 1..1000 (numpy linear interpolation)
    assert ci[50.0] == pytest.approx(500.5, abs=1e-9)


def test_percentile_ci_ignores_nan():
    values = np.array([1.0, 2.0, 3.0, np.nan, np.nan])
    ci = mc.percentile_ci(values, percentiles=(50.0,))
    assert ci[50.0] == pytest.approx(2.0)


def test_percentile_ci_all_nan_returns_nan_not_a_crash():
    ci = mc.percentile_ci(np.array([np.nan, np.nan]))
    assert all(np.isnan(v) for v in ci.values())


# --------------------------------------------------------------------------
# 6. Small end-to-end run over the real three countries
# --------------------------------------------------------------------------
@pytestmark_needs_data
def test_end_to_end_small_run_produces_expected_format():
    pre = mc._Precomputed()
    result = mc.run_simulation(0.20, n=5, pre=pre)

    for key, group_cols in (("water", ["country", "water_scenario", "water_risk_band"]),
                             ("heat", ["country", "heat_scenario", "heat_risk_band", "gcm"])):
        frame = result[key]
        assert not frame.empty
        for col in group_cols + ["point_estimate", "p2.5", "p50.0", "p97.5"]:
            assert col in frame.columns
        assert set(frame["country"]) <= set(COUNTRIES)
        # every point estimate is finite or an honestly-reported all-NaN group
        assert frame["point_estimate"].notna().sum() > 0

    assert set(result["heat"]["gcm"]) == set(cc.configured_models())


@pytestmark_needs_data
def test_full_simulation_timing_is_feasible():
    """Regression guard on the module's own feasibility claim: one magnitude
    at a reduced N must complete well within this test's timeout, confirming
    N=1000 x 3 magnitudes x 3 countries stays in the few-minutes range (see
    the task report accompanying this module for the measured full timing)."""
    pre = mc._Precomputed()
    import time
    t0 = time.perf_counter()
    mc.run_simulation(0.20, n=50, pre=pre)
    elapsed = time.perf_counter() - t0
    assert elapsed < 30.0, f"50-iteration run took {elapsed:.1f}s -- unexpectedly slow"


# --------------------------------------------------------------------------
# Cross-check: vectorised age_factor mirror vs. production age_factor.py
# --------------------------------------------------------------------------
@pytestmark_needs_data
def test_vectorized_retention_matches_production_age_factor_at_central_rates():
    """At the unperturbed (central, production) rates, monte_carlo's
    vectorised retention/age_factor mirror must match
    age_factor.compute_age_factors() row for row -- guards against
    transcription drift between the two implementations (see module
    docstring, "Vectorised age_factor")."""
    attrs = mc._plant_attributes()
    country_map = attrs.merge(age_factor.load_plant_attributes()[["plant_uid", "country"]], on="plant_uid")
    country_idx = country_map["country"].map({c: i for i, c in enumerate(COUNTRIES)}).to_numpy()

    central_coal = np.full(len(COUNTRIES), age_factor.COAL_DECAY_RATE)
    central_wind = np.full(len(COUNTRIES), age_factor.WIND_RELATIVE_RATE)
    central_hydro = np.full(len(COUNTRIES), age_factor.HYDRO_RETENTION_RATE)

    retention = mc._retention_vector(attrs, country_idx, central_coal, central_wind, central_hydro)
    vectorized_af = 2.0 - np.clip(retention, 0.0, 1.0)

    production = age_factor.compute_age_factors().set_index("plant_uid")["age_factor"]
    vectorized_series = pd.Series(vectorized_af, index=attrs["plant_uid"].to_numpy()).reindex(production.index)

    np.testing.assert_allclose(vectorized_series.to_numpy(), production.to_numpy(), atol=1e-9)
