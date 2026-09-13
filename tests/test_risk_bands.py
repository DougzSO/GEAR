"""Tests for src/index/risk_bands -- Phase 3.2, GEAR v3 work plan.

Replaces the retired CCRS-era test_risk_bands.py (WaterRiskBand/HeatRiskBand
against the deleted ccrs_calculator), exactly as tests/test_risk_calculator.py
replaced the retired ccrs_calculator tests in Phase 1.

Covers: pure band arithmetic (percentile_band_cuts, _bandize) with no I/O;
one Tier 1 hazard (Water Stress, absolute cutoffs) and one Tier 3 hazard
(Drought, percentile cutoffs) end to end via classify_hazard; the binary
Wind-bucket scheme; that a (hazard, bucket) combination outside
hazard_scope.APPLICABLE_HAZARDS always raises HazardNotApplicableError,
never a silent default band; and the THRESHOLD_REGISTRY <-> H_b consistency
guard.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.index import hazard_scope as hs
from src.index import risk_bands as rb


# --------------------------------------------------------------------------
# percentile_band_cuts -- pure function, no I/O
# --------------------------------------------------------------------------
def test_percentile_band_cuts_drops_lowest_as_diagnostic():
    values = np.arange(1, 101, dtype="float64")  # 1..100
    info = rb.percentile_band_cuts(values, (50.0, 75.0, 90.0, 95.0))
    assert info["diagnostic_percentile"] == 50.0
    assert info["band_percentiles"] == (75.0, 90.0, 95.0)
    assert len(info["band_cuts"]) == 3
    # np.percentile(1..100, 75) == 75.25
    assert info["band_cuts"][0] == pytest.approx(75.25, abs=0.5)
    assert info["n"] == 100


def test_percentile_band_cuts_ignores_nan():
    values = np.array([np.nan, *range(1, 101)], dtype="float64")
    info = rb.percentile_band_cuts(values, (50.0, 75.0, 90.0, 95.0))
    assert info["n"] == 100


def test_percentile_band_cuts_raises_on_all_nan():
    with pytest.raises(ValueError, match="no finite values"):
        rb.percentile_band_cuts(np.array([np.nan, np.nan]))


# --------------------------------------------------------------------------
# _bandize -- pure function, no I/O
# --------------------------------------------------------------------------
def test_bandize_four_band_left_closed():
    cuts = (10.0, 20.0, 30.0)
    values = np.array([-5.0, 10.0, 15.0, 20.0, 29.999, 30.0, 100.0])
    bands = rb._bandize(values, cuts, rb.BAND_LABELS)
    assert list(bands) == ["Low", "Medium", "Medium", "High", "High", "Extreme", "Extreme"]


def test_bandize_binary_wind_scheme():
    values = np.array([0.0, 24.9, 25.0, 40.0])
    bands = rb._bandize(values, (25.0,), rb.WIND_BUCKET_BAND_LABELS)
    assert list(bands) == ["Low", "Low", "Extreme", "Extreme"]


def test_bandize_nan_is_none():
    bands = rb._bandize(np.array([np.nan, 5.0]), (10.0, 20.0, 30.0), rb.BAND_LABELS)
    assert bands[0] is None
    assert bands[1] == "Low"


def test_bandize_rejects_mismatched_cuts_and_labels():
    with pytest.raises(ValueError, match="cannot bound"):
        rb._bandize(np.array([1.0]), (10.0, 20.0), rb.BAND_LABELS)  # 2 cuts, 4 labels


# --------------------------------------------------------------------------
# classify_hazard -- Tier 1 (absolute), Water Stress
# --------------------------------------------------------------------------
def test_water_stress_tier1_absolute_cuts():
    values = np.array([0.05, 0.1, 0.25, 0.4, 0.6, 0.8, 0.95])
    result = rb.classify_hazard("ws", "hydro", values)
    assert result.spec.tier == 1
    assert result.spec.kind == "absolute"
    assert list(result.bands) == ["Low", "Medium", "Medium", "High", "High", "Extreme", "Extreme"]
    assert result.cuts_used == rb.WATER_STRESS_TIER1_CUTS
    assert result.percentile_info is None


def test_water_stress_applies_to_both_hydro_and_thermal():
    values = np.array([0.5])
    for bucket in ("hydro", "thermal"):
        result = rb.classify_hazard("ws", bucket, values)
        assert result.spec.tier == 1
        assert result.bands[0] == "High"


# --------------------------------------------------------------------------
# classify_hazard -- Tier 3 (percentile), Drought/SPEI
# --------------------------------------------------------------------------
def test_drought_spei_tier3_percentile():
    pooled = np.arange(1, 101, dtype="float64")
    raw = np.array([1.0, 76.0, 91.0, 96.0])  # below P75, in Medium, in High, in Extreme
    result = rb.classify_hazard("spei", "hydro", raw, pooled_values=pooled)
    assert result.spec.tier == 3
    assert result.spec.kind == "percentile"
    assert list(result.bands) == ["Low", "Medium", "High", "Extreme"]
    assert result.percentile_info["diagnostic_percentile"] == 50.0


def test_drought_spei_requires_pooled_values():
    with pytest.raises(ValueError, match="pooled_values is required"):
        rb.classify_hazard("spei", "hydro", np.array([1.0]))


# --------------------------------------------------------------------------
# Extreme Wind -- Tier 1 binary (Wind bucket) vs Tier 3 percentile (Solar)
# --------------------------------------------------------------------------
def test_extreme_wind_wind_bucket_is_binary():
    values = np.array([10.0, 24.9, 25.0, 30.0])
    result = rb.classify_hazard("wind", "wind", values)
    assert result.spec.tier == 1
    assert result.spec.labels == rb.WIND_BUCKET_BAND_LABELS
    assert list(result.bands) == ["Low", "Low", "Extreme", "Extreme"]


def test_extreme_wind_solar_bucket_is_percentile():
    pooled = np.arange(1, 101, dtype="float64")
    raw = np.array([1.0, 91.0, 96.0, 99.5])
    result = rb.classify_hazard("wind", "solar", raw, pooled_values=pooled)
    assert result.spec.tier == 3
    assert result.spec.percentiles == rb.WIND_SOLAR_TIER3_PERCENTILES
    assert result.percentile_info["diagnostic_percentile"] == 75.0
    assert list(result.bands) == ["Low", "Medium", "High", "Extreme"]


# --------------------------------------------------------------------------
# Extreme Heat -- Solar is a FINAL Tier 3 fallback (closed 2026-09-12 by a
# bounded literature search, not provisional), same cuts as Thermal
# --------------------------------------------------------------------------
def test_extreme_heat_solar_is_final_not_provisional_and_uses_thermal_style_cuts():
    thermal_spec = rb.THRESHOLD_REGISTRY[("heat", "thermal")]
    solar_spec = rb.THRESHOLD_REGISTRY[("heat", "solar")]
    assert thermal_spec.provisional is False
    assert solar_spec.provisional is False
    assert solar_spec.percentiles == thermal_spec.percentiles == rb.GENERIC_TIER3_PERCENTILES


# --------------------------------------------------------------------------
# sv/iv -- Tier 3, Hydro only (not Thermal)
# --------------------------------------------------------------------------
def test_sv_iv_are_hydro_only_tier3():
    for term in ("sv", "iv"):
        assert ("hydro", term) or True  # documentation anchor
        spec = rb.THRESHOLD_REGISTRY[(term, "hydro")]
        assert spec.tier == 3
        assert spec.percentiles == rb.GENERIC_TIER3_PERCENTILES
        assert (term, "thermal") not in rb.THRESHOLD_REGISTRY


# --------------------------------------------------------------------------
# Inapplicable hazard/bucket combinations -- must raise, never silently band
# --------------------------------------------------------------------------
@pytest.mark.parametrize("hazard,bucket", [
    ("spei", "thermal"),   # Drought is Hydro-only
    ("spei", "wind"),
    ("spei", "solar"),
    ("ws", "wind"),        # Water Stress has no water-independent bucket
    ("ws", "solar"),
    ("wind", "hydro"),     # Extreme Wind never applies to a water bucket
    ("wind", "thermal"),
    ("sv", "thermal"),     # sv/iv are Hydro-only (not Thermal, Phase 3.1)
    ("iv", "wind"),
    ("heat", "hydro"),     # Extreme Heat never applies to Hydro
    ("not_a_hazard", "hydro"),
])
def test_inapplicable_combination_raises_not_a_silent_band(hazard, bucket):
    with pytest.raises(rb.HazardNotApplicableError):
        rb.classify_hazard(hazard, bucket, np.array([1.0]), pooled_values=np.array([1.0, 2.0, 3.0]))


def test_every_h_b_combination_is_classifiable():
    """The converse: every combination hazard_scope DOES mark applicable
    must have a THRESHOLD_REGISTRY entry (enforced at import time too; this
    re-checks it as a normal test, not only a load-time assertion)."""
    for bucket, hazards in hs.APPLICABLE_HAZARDS.items():
        for hazard in hazards:
            assert (hazard, bucket) in rb.THRESHOLD_REGISTRY


# --------------------------------------------------------------------------
# compute_risk_bands -- pipeline-level, monkeypatched sampling (no raster I/O)
# --------------------------------------------------------------------------
def _fake_plants(bucket: str, n: int = 6) -> pd.DataFrame:
    return pd.DataFrame({
        rb.PLANT_UID: [f"p{bucket}{i}" for i in range(n)],
        "country": "Testland", "plant_name": [f"plant{i}" for i in range(n)],
        "lon": 0.0, "lat": 0.0, "capacity_mw": 10.0, "commissioning_year": 2000.0,
        "bucket": bucket, "fuel_type": "x", "mixed_fuel_type": False,
        "fuel_types_found": "x",
    })


def test_compute_risk_bands_only_classifies_applicable_combinations(monkeypatch):
    """End-to-end pipeline check with fully monkeypatched sampling: no
    (hazard, bucket) row appears in the output frame unless
    hazard_scope.APPLICABLE_HAZARDS marks it applicable."""
    rng = np.random.default_rng(0)

    def fake_sample_hazard_terms(model=rb.PRIMARY_GCM):
        parts = []
        for bucket in hs.APPLICABLE_HAZARDS:
            plants = _fake_plants(bucket)
            for water_scen in ("opt", "bau", "pes"):
                part = plants.copy()
                part["water_scenario"] = water_scen
                part["heat_scenario"] = "ssp126"
                for term in ("ws", "sv", "iv", "heat", "spei", "precip", "wind"):
                    part[term] = rng.uniform(0.0, 50.0, size=len(part))
                parts.append(part)
        return pd.concat(parts, ignore_index=True)

    monkeypatch.setattr(rb, "sample_hazard_terms", fake_sample_hazard_terms)
    result = rb.compute_risk_bands()

    present = set(zip(result.frame["hazard_term"], result.frame["bucket"]))
    assert present == set(rb.THRESHOLD_REGISTRY)
    assert result.frame["risk_band"].notna().all()
    assert set(result.frame["risk_band"].unique()) <= set(rb.BAND_LABELS) | set(rb.WIND_BUCKET_BAND_LABELS)


def test_compute_risk_bands_rejects_unconfigured_model():
    with pytest.raises(ValueError, match="not a configured GCM"):
        rb.compute_risk_bands(model="not_a_real_gcm")
