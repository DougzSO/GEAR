"""Tests for src/index/age_factor -- the >=1 CCRS age multiplier (final
convention: age_factor = 2 - clip(retention(age), 0, 1) in [1, 2]).

One test per fuel_type_bucket (including the neutral gas/oil-gas and
nuclear/bioenergy thermal cases), coal's assumed-overhaul sawtooth (decay
within a cycle, partial recovery at a cycle boundary, multiple cycles), the
wind CF_initial dead-code-path check, one mixed-fuel case, one
missing-commissioning_year case, plus the sign convention, the [1,2] clip,
the study-horizon constant, and the plant_uid-keyed multiplicative
application.
"""

import inspect

import numpy as np
import pandas as pd
import pytest

from src.index import age_factor as af
from src.index import ccrs_calculator as ccrs
from src.index.ccrs_calculator import PLANT_UID
from src import config


# --------------------------------------------------------------------------
# sign convention and constants
# --------------------------------------------------------------------------
def test_reference_year_is_the_study_horizon_constant():
    assert af.REFERENCE_YEAR == config.YEAR_TARGET == 2050


def test_two_minus_retention_maps_20pct_loss_to_1_2():
    # spec Section 6 example: 20% loss -> ~x1.2
    assert af._to_multiplier(0.80) == pytest.approx(1.20)
    assert af._to_multiplier(1.00) == pytest.approx(1.00)
    assert af._to_multiplier(0.50) == pytest.approx(1.50)


def test_age_factor_is_clipped_to_the_1_2_range():
    # a wildly old (implausible) plant -> retention < 0 -> clipped, af == 2.0
    assert af.age_factor("x", "hydro", 100_000) == pytest.approx(2.0)
    # a "future" plant (negative age) -> retention > 1 -> clipped, af == 1.0
    assert af.age_factor("x", "wind", -50) == pytest.approx(1.0)


def test_plant_age_uses_reference_year_and_passes_nan_through():
    assert af.plant_age(2000) == pytest.approx(2050 - 2000)
    assert np.isnan(af.plant_age(np.nan))
    assert np.isnan(af.plant_age(pd.NA))


# --------------------------------------------------------------------------
# one case per fuel_type_bucket
# --------------------------------------------------------------------------
def test_bucket_hydro():
    # retention = 1 - 0.0055*age (0.55%/yr, no 0.79 scaling) ; af = 2 - retention
    assert af.age_factor("H", "hydro", 40) == pytest.approx(1 + 0.0055 * 40)
    assert af.age_factor("H", "hydro", 0) == pytest.approx(1.0)


def test_bucket_wind_is_uniform_0_4_pct_per_year_for_every_plant():
    # 1 - 0.004*age applied uniformly, no CF_initial branch
    assert af.age_factor("W", "wind", 25) == pytest.approx(1 + 0.004 * 25)   # 1.10
    assert af.age_factor("W", "wind", 0) == pytest.approx(1.0)


def test_bucket_solar():
    # compound: af = 2 - (1-0.007)**age
    assert af.age_factor("S", "solar", 30) == pytest.approx(2 - (1 - 0.007) ** 30)
    assert af.age_factor("S", "solar", 0) == pytest.approx(1.0)


def test_bucket_thermal_gas_is_neutral():
    assert af.age_factor("G", "thermal", 40, fuel_type="oil/gas") == 1.0
    assert af.age_factor("G", "thermal", 120, fuel_type="oil/gas") == 1.0   # age-independent


def test_bucket_thermal_nuclear_and_bioenergy_are_neutral():
    assert af.age_factor("N", "thermal", 55, fuel_type="nuclear") == 1.0
    assert af.age_factor("B", "thermal", 55, fuel_type="bioenergy") == 1.0


def test_unknown_thermal_fuel_and_unknown_bucket_fail_loud():
    with pytest.raises(ValueError, match="no age curve"):
        af.age_factor("X", "thermal", 30, fuel_type="geothermal")
    with pytest.raises(ValueError, match="unknown fuel_type_bucket"):
        af.age_factor("X", "tidal", 30)
    with pytest.raises(ValueError, match="no fuel_type"):
        af.age_factor("X", "thermal", 30, fuel_type=pd.NA)


# --------------------------------------------------------------------------
# coal: assumed-overhaul sawtooth
# --------------------------------------------------------------------------
def test_coal_decays_within_a_cycle():
    # 3 yr into the first (open) 5-yr cycle -> plain 0.25 pp/yr decay so far
    r = af._coal_retention(3)
    assert r == pytest.approx(1 - 0.0025 * 3)
    assert af.age_factor("C", "thermal", 3, fuel_type="coal") == pytest.approx(2 - r)
    # decay is monotonic strictly inside a cycle
    assert af._coal_retention(4) < af._coal_retention(3) < af._coal_retention(0)


def test_coal_recovers_70pct_of_the_cycle_loss_at_the_cycle_boundary():
    just_before = af._coal_retention(5 - 1e-9)          # ~1 - 0.0125
    at_boundary = af._coal_retention(5)                 # 1 cycle closed, 0 yr into next
    cycle_loss = 0.0025 * af.COAL_OVERHAUL_CYCLE_YEARS   # 0.0125
    # retention steps UP at the boundary: 70% of that cycle's loss is recovered
    assert at_boundary > just_before
    assert at_boundary == pytest.approx(1 - (1 - af.COAL_OVERHAUL_RECOVERY) * cycle_loss)
    assert at_boundary == pytest.approx(1 - 0.00375)


def test_coal_multiple_cycles_accumulate_only_the_permanent_loss():
    # 2 full cycles (age 10): permanent loss = 2 * 30% * (0.25pp/yr * 5yr)
    r10 = af._coal_retention(10)
    assert r10 == pytest.approx(1 - 2 * 0.00375)
    # 8 full cycles + 0 yr into the 9th (age 40)
    r40 = af._coal_retention(40)
    assert r40 == pytest.approx(1 - 8 * 0.00375)
    assert af.age_factor("C", "thermal", 40, fuel_type="coal") == pytest.approx(2 - r40)
    # overhaul recovery keeps a mature plant far less degraded than pure decay
    assert r40 > 1 - 0.0025 * 40


# --------------------------------------------------------------------------
# wind CF_initial: dead code, not on the active path
# --------------------------------------------------------------------------
def test_wind_cf_initial_formula_exists_but_is_dead_code():
    # kept as an executable record of the formula ...
    assert af._wind_retention_from_cf_initial(20, 0.30) == pytest.approx(
        1 - 0.0015 * 20 / 0.30
    )
    # ... but age_factor no longer accepts a cf_initial argument at all
    assert "cf_initial" not in inspect.signature(af.age_factor).parameters
    # ... and nothing on the active call path references the dead function
    for fn in (af.age_factor, af._wind_retention, af.compute_age_factors,
               af._thermal_fuel_retention):
        assert "_wind_retention_from_cf_initial" not in inspect.getsource(fn)
    # the module defines it exactly once (the def itself) -- never called
    assert inspect.getsource(af).count("_wind_retention_from_cf_initial(") == 1


# --------------------------------------------------------------------------
# mixed fuel
# --------------------------------------------------------------------------
def test_mixed_fuel_is_the_simple_average_of_component_age_factors():
    age = 40
    coal = af.age_factor("m", "thermal", age, fuel_type="coal")
    # bioenergy;coal -> mean(1.0, coal_af)
    got = af.age_factor("m", "thermal", age, mixed_fuel_type=True,
                        fuel_types_found="bioenergy;coal")
    assert got == pytest.approx((1.0 + coal) / 2)
    # coal;oil/gas -> mean(coal_af, 1.0)
    assert af.age_factor("m", "thermal", age, mixed_fuel_type=True,
                         fuel_types_found="coal;oil/gas") == pytest.approx((coal + 1.0) / 2)
    # bioenergy;oil/gas -> both neutral -> 1.0
    assert af.age_factor("m", "thermal", age, mixed_fuel_type=True,
                         fuel_types_found="bioenergy;oil/gas") == pytest.approx(1.0)


def test_mixed_fuel_empty_components_fail_loud():
    with pytest.raises(ValueError, match="empty"):
        af.age_factor("m", "thermal", 30, mixed_fuel_type=True, fuel_types_found="")


# --------------------------------------------------------------------------
# missing commissioning_year
# --------------------------------------------------------------------------
def test_missing_commissioning_year_neutralises_age_factor():
    assert af.age_factor("z", "wind", np.nan) == 1.0
    assert af.age_factor("z", "hydro", pd.NA) == 1.0
    assert af.age_factor("z", "solar", None) == 1.0


def test_compute_age_factors_flags_and_keeps_missing_year_rows(monkeypatch):
    fake = pd.DataFrame({
        PLANT_UID: ["A-1", "A-2", "A-3"],
        "country": "Testland",
        "plant_name": ["a", "b", "c"],
        "capacity_mw": [10.0, 20.0, 30.0],
        "commissioning_year": [2010.0, np.nan, 1990.0],
        "bucket": ["wind", "solar", "hydro"],
        "fuel_type": pd.array(["wind", "utility-scale solar", "hydropower"], dtype="string"),
        "mixed_fuel_type": [False, False, False],
        "fuel_types_found": pd.array(["wind", "utility-scale solar", "hydropower"], dtype="string"),
    })
    monkeypatch.setattr(af, "load_plant_attributes", lambda: fake.copy())
    out = af.compute_age_factors()

    assert len(out) == 3                                   # missing-year row kept
    row = out.set_index(PLANT_UID)
    assert row.loc["A-2", "age_factor_neutralized_missing_year"]
    assert row.loc["A-2", "age_factor"] == 1.0
    assert not row.loc["A-1", "age_factor_neutralized_missing_year"]
    assert row.loc["A-1", "age_factor"] == pytest.approx(1 + 0.004 * (2050 - 2010))


# --------------------------------------------------------------------------
# application: plant_uid key, multiplicative
# --------------------------------------------------------------------------
def test_apply_to_hazard_multiplies_per_plant_uid_never_sums(tmp_path):
    hazard = pd.DataFrame({
        PLANT_UID: ["A-1", "A-1", "B-2"],
        "water_scenario": ["opt", "pes", "opt"],
        "hazard_gfdl_esm4": [0.10, 0.20, 0.50],
        "hazard_miroc6": [0.40, 0.60, 0.80],
    })
    hz_csv = tmp_path / "ccrs_hazard.csv"
    hazard.to_csv(hz_csv, index=False)

    age_factors = pd.DataFrame({
        PLANT_UID: ["A-1", "B-2"],
        "age": [40.0, 20.0],
        "age_factor": [1.25, 2.0],
        "age_factor_neutralized_missing_year": [False, False],
    })

    out = af.apply_to_hazard(hz_csv, age_factors=age_factors)

    # A-1 rows both multiplied by 1.25, B-2 by 2.0 -- multiplication, not addition
    a1 = out[out[PLANT_UID] == "A-1"]
    np.testing.assert_allclose(a1["hazard_gfdl_esm4_aged"], [0.10 * 1.25, 0.20 * 1.25])
    np.testing.assert_allclose(a1["hazard_miroc6_aged"], [0.40 * 1.25, 0.60 * 1.25])
    b2 = out[out[PLANT_UID] == "B-2"]
    np.testing.assert_allclose(b2["hazard_gfdl_esm4_aged"], [0.50 * 2.0])
    # original columns untouched
    np.testing.assert_allclose(out["hazard_gfdl_esm4"], [0.10, 0.20, 0.50])


def test_apply_to_hazard_rejects_a_stale_hazard_csv(tmp_path):
    hazard = pd.DataFrame({
        PLANT_UID: ["OLD-999"],
        "hazard_gfdl_esm4": [0.1], "hazard_miroc6": [0.2],
    })
    hz_csv = tmp_path / "ccrs_hazard.csv"
    hazard.to_csv(hz_csv, index=False)
    age_factors = pd.DataFrame({
        PLANT_UID: ["A-1"], "age": [10.0], "age_factor": [1.0],
        "age_factor_neutralized_missing_year": [False],
    })
    with pytest.raises(ValueError, match="stale"):
        af.apply_to_hazard(hz_csv, age_factors=age_factors)


# --------------------------------------------------------------------------
# real data sanity (skipped if the validated CSVs are absent)
# --------------------------------------------------------------------------
def _plants_present() -> bool:
    return all(
        (ccrs.ASSETS_PROCESSED / f"gem_validated_plants_{c}.csv").exists()
        for c in ccrs.COUNTRIES
    )


@pytest.mark.skipif(not _plants_present(), reason="validated-plant CSVs absent")
def test_real_data_age_factors_are_all_ge_1_and_le_2():
    d = af.compute_age_factors()
    assert (d["age_factor"] >= 1.0).all()
    assert (d["age_factor"] <= 2.0).all()
    assert d[PLANT_UID].is_unique
    # neutral buckets/fuels really are exactly 1.0
    neutral = d[
        (d["bucket"] == "thermal")
        & d["fuel_type"].isin(["oil/gas", "nuclear", "bioenergy"])
        & ~d["age_factor_neutralized_missing_year"]
    ]
    assert (neutral["age_factor"] == 1.0).all()


@pytest.mark.skipif(not _plants_present(), reason="validated-plant CSVs absent")
def test_real_data_load_plants_carries_fuel_columns():
    p = ccrs.load_plants("Brazil")
    for col in ("fuel_type", "mixed_fuel_type", "fuel_types_found"):
        assert col in p.columns
    assert p["mixed_fuel_type"].dtype == bool
