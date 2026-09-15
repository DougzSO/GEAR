"""Tests for src/index/sensitivity_recompute -- GEAR v3 Phase 6's
partial-recomputation pipeline (raster caching + perturbed-chain recompute).

Covers, in order of what the task required:
1. Correctness FIRST: at nominal (unperturbed) parameter values, the cached/
   recompute path must reproduce the existing production functions
   (``age_factor.compute_age_factors``, ``risk_calculator.
   compute_risk_by_hazard``, ``risk_bands.compute_risk_bands``,
   ``psae.compute_psae``) numerically identically -- real data, not a fake.
2. Pure-function unit tests for the one necessary reimplementation
   (``retention_vector`` -- vectorised, cannot call the scalar
   ``age_factor.age_factor()`` per-parameter without a Python loop, see
   module docstring) against ``age_factor``'s own scalar retention curves,
   no I/O.

All real-data tests are skipped (never silently passed) when the processed
rasters / validated-plant CSVs are absent, mirroring
``tests/test_risk_calculator.py::_rasters_present`` and
``tests/test_age_factor.py::_plants_present``. ``precompute()`` is
expensive (~30-60s, dominated by raster I/O) -- shared across this module's
real-data tests via a module-scoped fixture, paid once, not once per test.
"""

import numpy as np
import pandas as pd
import pytest

from src.index import age_factor
from src.index import psae
from src.index import risk_bands as rb
from src.index import risk_calculator as rc
from src.index import sensitivity_recompute as sr


def _rasters_present() -> bool:
    try:
        p = rc.raster_path("heat", "Brazil", "opt", rc.configured_models()[0])
        q = rc.raster_path("ws", "Brazil", "opt", rc.configured_models()[0])
        return p.exists() and q.exists()
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _rasters_present(), reason="processed rasters absent -- cannot precompute"
)


@pytest.fixture(scope="module")
def pre() -> sr.PrecomputedInputs:
    return sr.precompute()


@pytest.fixture(scope="module")
def model() -> str:
    return rc.configured_models()[0]


# --------------------------------------------------------------------------
# Correctness FIRST (task requirement) -- nominal draw must match production
# --------------------------------------------------------------------------
def test_age_factor_vector_matches_production_at_nominal_rates(pre):
    """No overrides -> must reproduce age_factor.compute_age_factors()'s
    age_factor column exactly (both read the same underlying attributes;
    only the vectorisation differs)."""
    prod = age_factor.compute_age_factors()
    mine = sr.age_factor_vector(pre.attrs)
    assert list(pre.attrs[sr.PLANT_UID]) == list(prod[sr.PLANT_UID])
    np.testing.assert_allclose(mine, prod["age_factor"].to_numpy("float64"))


def test_recompute_risk_by_hazard_matches_production_at_nominal_values(pre, model):
    """No overrides -> must reproduce risk_calculator.compute_risk_by_hazard
    numerically identically -- Risk_i,h (Equation 1), the exact quantity the
    task requires verified before any speed claim."""
    prod = rc.compute_risk_by_hazard(model)
    mine = sr.recompute_risk_by_hazard(pre, model)

    key = [rc.PLANT_UID, "water_scenario", "hazard_term"]
    prod_s = prod.sort_values(key).reset_index(drop=True)
    mine_s = mine.sort_values(key).reset_index(drop=True)

    assert list(prod_s.columns) == list(mine_s.columns)
    assert len(prod_s) == len(mine_s)
    for col in ("hazard_i_h", "exposure_mw", "age_factor", "risk_i_h"):
        np.testing.assert_allclose(
            prod_s[col].to_numpy("float64"), mine_s[col].to_numpy("float64"),
            equal_nan=True,
        )


def test_recompute_risk_bands_matches_production_at_nominal_values(pre, model):
    """No overrides -> must reproduce risk_bands.compute_risk_bands
    numerically identically -- RiskBand_i,h, same percentile cuts, same
    band labels."""
    prod = rb.compute_risk_bands(model)
    mine = sr.recompute_risk_bands(pre, model)

    key = [rb.PLANT_UID, "water_scenario", "hazard_term", "bucket"]
    prod_f = prod.frame.sort_values(key).reset_index(drop=True)
    mine_f = mine.frame.sort_values(key).reset_index(drop=True)

    assert len(prod_f) == len(mine_f)
    np.testing.assert_allclose(
        prod_f["raw_value"].to_numpy("float64"), mine_f["raw_value"].to_numpy("float64"),
        equal_nan=True,
    )
    prod_bands = prod_f["risk_band"].astype(object).where(prod_f["risk_band"].notna(), None)
    mine_bands = mine_f["risk_band"].astype(object).where(mine_f["risk_band"].notna(), None)
    assert (prod_bands.to_numpy() == mine_bands.to_numpy()).all()

    assert set(prod.percentile_cuts) == set(mine.percentile_cuts)
    for k, prod_info in prod.percentile_cuts.items():
        mine_info = mine.percentile_cuts[k]
        assert prod_info["band_cuts"] == mine_info["band_cuts"]
        assert prod_info["all_cuts"] == mine_info["all_cuts"]


def test_recompute_draw_psae_matches_production_at_nominal_values(pre, model):
    """The full draw's PSAE table (fed through the unmodified
    psae.compute_psae) must match production psae.compute_psae(risk_bands.
    compute_risk_bands(model)) numerically identically."""
    prod_bands = rb.compute_risk_bands(model)
    prod_psae = psae.compute_psae(prod_bands)

    draw = sr.recompute_draw(pre, model)

    key = [psae.PLANT_UID, "water_scenario"]
    pp = prod_psae.frame.sort_values(key).reset_index(drop=True)
    mp = draw.psae.frame.sort_values(key).reset_index(drop=True)

    np.testing.assert_allclose(
        pp["psae"].to_numpy("float64"), mp["psae"].to_numpy("float64"), equal_nan=True,
    )
    pp_label = pp["psae_label"].astype(object).where(pp["psae_label"].notna(), None)
    mp_label = mp["psae_label"].astype(object).where(mp["psae_label"].notna(), None)
    assert (pp_label.to_numpy() == mp_label.to_numpy()).all()
    assert (pp["psae_complete"].to_numpy() == mp["psae_complete"].to_numpy()).all()


def test_recompute_draw_with_perturbed_params_changes_output(pre, model):
    """Sanity that perturbation actually moves the two chains -- a pipeline
    that silently ignored its override arguments would still pass the
    nominal-match tests above."""
    nominal = sr.recompute_draw(pre, model)

    big_rate_overrides = {
        "coal_decay_rate": age_factor.COAL_DECAY_RATE * 3.0,
        "wind_relative_rate": age_factor.WIND_RELATIVE_RATE * 3.0,
        "hydro_retention_rate": age_factor.HYDRO_RETENTION_RATE * 3.0,
        "solar_retention_rate": age_factor.SOLAR_RETENTION_RATE * 3.0,
    }
    perturbed = sr.recompute_draw(pre, model, rate_overrides=big_rate_overrides)
    assert not np.allclose(
        nominal.risk_by_hazard["risk_i_h"].to_numpy("float64"),
        perturbed.risk_by_hazard["risk_i_h"].to_numpy("float64"),
        equal_nan=True,
    )

    shifted = {
        key: tuple(min(max(p + 10.0, 0.0), 100.0) for p in spec.percentiles)
        for key, spec in rb.THRESHOLD_REGISTRY.items() if spec.kind == "percentile"
    }
    perturbed_bands = sr.recompute_risk_bands(pre, model, percentile_overrides=shifted)
    same_key = [rb.PLANT_UID, "water_scenario", "hazard_term", "bucket"]
    a = nominal.risk_bands.frame.sort_values(same_key).reset_index(drop=True)
    b = perturbed_bands.frame.sort_values(same_key).reset_index(drop=True)
    a_bands = a["risk_band"].astype(object).where(a["risk_band"].notna(), None)
    b_bands = b["risk_band"].astype(object).where(b["risk_band"].notna(), None)
    assert not (a_bands.to_numpy() == b_bands.to_numpy()).all()


# --------------------------------------------------------------------------
# Pure-function unit tests -- retention_vector against age_factor's own
# scalar curves, no I/O.
# --------------------------------------------------------------------------
def _attrs(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def test_retention_vector_hydro_matches_scalar():
    attrs = _attrs([{"age": 10.0, "bucket": "hydro", "fuel_type": "", "mixed_fuel_type": False, "fuel_types_found": ""}])
    out = sr.retention_vector(attrs)
    assert out[0] == pytest.approx(age_factor._hydro_retention(10.0))


def test_retention_vector_wind_matches_scalar():
    attrs = _attrs([{"age": 7.0, "bucket": "wind", "fuel_type": "", "mixed_fuel_type": False, "fuel_types_found": ""}])
    out = sr.retention_vector(attrs)
    assert out[0] == pytest.approx(age_factor._wind_retention(7.0))


def test_retention_vector_solar_matches_scalar():
    attrs = _attrs([{"age": 12.0, "bucket": "solar", "fuel_type": "", "mixed_fuel_type": False, "fuel_types_found": ""}])
    out = sr.retention_vector(attrs)
    assert out[0] == pytest.approx(age_factor._solar_retention(12.0))


def test_retention_vector_coal_matches_scalar_across_several_ages():
    for age in (0.0, 1.0, 4.9, 5.0, 5.1, 12.3, 23.0):
        attrs = _attrs([{"age": age, "bucket": "thermal", "fuel_type": "coal", "mixed_fuel_type": False, "fuel_types_found": ""}])
        out = sr.retention_vector(attrs)
        assert out[0] == pytest.approx(age_factor._coal_retention(age)), f"age={age}"


def test_retention_vector_coal_with_perturbed_rate_matches_scalar_with_same_rate(monkeypatch):
    """A perturbed decay_rate fed to retention_vector must match the scalar
    _coal_retention computed under the SAME rate (monkeypatched module
    constant) -- proves the perturbation actually reaches the sawtooth
    formula, not just the linear/compound curves."""
    perturbed_rate = age_factor.COAL_DECAY_RATE * 1.7
    for age in (0.0, 3.0, 5.0, 8.5, 21.0):
        attrs = _attrs([{"age": age, "bucket": "thermal", "fuel_type": "coal", "mixed_fuel_type": False, "fuel_types_found": ""}])
        out = sr.retention_vector(attrs, coal_decay_rate=perturbed_rate)
        monkeypatch.setattr(age_factor, "COAL_DECAY_RATE", perturbed_rate)
        expected = age_factor._coal_retention(age)
        monkeypatch.undo()
        assert out[0] == pytest.approx(expected), f"age={age}"


def test_retention_vector_neutral_thermal_fuels_are_one():
    for fuel in sorted(age_factor.NEUTRAL_THERMAL_FUELS):
        attrs = _attrs([{"age": 30.0, "bucket": "thermal", "fuel_type": fuel, "mixed_fuel_type": False, "fuel_types_found": ""}])
        out = sr.retention_vector(attrs)
        assert out[0] == 1.0


def test_retention_vector_mixed_fuel_is_the_average():
    attrs = _attrs([{
        "age": 10.0, "bucket": "thermal", "fuel_type": "", "mixed_fuel_type": True,
        "fuel_types_found": "coal;oil/gas",
    }])
    out = sr.retention_vector(attrs)
    expected = np.mean([age_factor._coal_retention(10.0), 1.0])
    assert out[0] == pytest.approx(expected)


def test_retention_vector_nan_age_is_neutral():
    attrs = _attrs([{"age": float("nan"), "bucket": "hydro", "fuel_type": "", "mixed_fuel_type": False, "fuel_types_found": ""}])
    out = sr.retention_vector(attrs)
    assert out[0] == 1.0
    af = sr.age_factor_vector(attrs)
    assert af[0] == age_factor.NEUTRAL_AGE_FACTOR


def test_retention_vector_unknown_bucket_raises():
    attrs = _attrs([{"age": 5.0, "bucket": "nuclear-ish-typo", "fuel_type": "", "mixed_fuel_type": False, "fuel_types_found": ""}])
    with pytest.raises(ValueError, match="unknown fuel_type_bucket"):
        sr.retention_vector(attrs)


def test_retention_vector_unknown_thermal_fuel_raises():
    attrs = _attrs([{"age": 5.0, "bucket": "thermal", "fuel_type": "typo-fuel", "mixed_fuel_type": False, "fuel_types_found": ""}])
    with pytest.raises(ValueError, match="unknown thermal fuel_type"):
        sr.retention_vector(attrs)


def test_age_factor_vector_is_two_minus_clipped_retention():
    attrs = _attrs([{"age": 10.0, "bucket": "hydro", "fuel_type": "", "mixed_fuel_type": False, "fuel_types_found": ""}])
    retention = sr.retention_vector(attrs)
    af = sr.age_factor_vector(attrs)
    np.testing.assert_allclose(af, 2.0 - np.clip(retention, 0.0, 1.0))
