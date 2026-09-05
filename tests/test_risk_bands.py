"""Tests for src/index/risk_bands -- WaterRiskBand and HeatRiskBand.

Covers: the fixed absolute WaterRiskBand cuts (one case per cut + one value
per band), the p25/p75/p95 HeatRiskBand cuts on a known synthetic sample,
that HeatRiskBand uses GFDL-ESM4 alone (not MIROC6, not a blend), that
plant_uid is the identity key, and that no function returns a single number
combining the two bands. Monkeypatched tests need no data on disk.
"""

import numpy as np
import pandas as pd
import pytest

from src.index import risk_bands as rb
from src.index import ccrs_calculator as ccrs


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _fake_terms(rows):
    """Build a frame shaped like ccrs.sample_terms(): one row per
    (plant, water_scenario) with raw ws/sv/iv/heat."""
    base = {
        "country": "Testland", "plant_name": "p", "lat": 0.0, "lon": 0.0,
        "capacity_mw": 10.0, "commissioning_year": 2000.0, "bucket": "thermal",
        "water_scenario": "opt", "heat_scenario": "ssp126",
        "ws": 0.0, "sv": 0.0, "iv": 0.0, "heat": 0.0,
    }
    return pd.DataFrame([{**base, **r} for r in rows])


# --------------------------------------------------------------------------
# 1. WaterRiskBand -- absolute cuts
# --------------------------------------------------------------------------
def test_water_band_cuts_are_the_fixed_published_constants():
    assert rb.WATER_BAND_CUTS == (0.208, 0.415, 0.667, 1.0)
    assert rb.WATER_RISK_BANDS == (
        "Low", "Low-Medium", "Medium-High", "High", "Extremely-High")


def test_water_band_one_value_per_band():
    got = list(rb.water_risk_band([0.10, 0.30, 0.50, 0.80, 1.50]))
    assert got == ["Low", "Low-Medium", "Medium-High", "High", "Extremely-High"]


def test_water_band_values_exactly_on_each_cut_go_to_the_higher_band():
    # left-closed: a value == cut belongs to the band above the cut
    got = list(rb.water_risk_band([0.208, 0.415, 0.667, 1.0]))
    assert got == ["Low-Medium", "Medium-High", "High", "Extremely-High"]
    # just below each cut stays in the lower band
    eps = 1e-9
    got_below = list(rb.water_risk_band([0.208 - eps, 0.415 - eps, 0.667 - eps, 1.0 - eps]))
    assert got_below == ["Low", "Low-Medium", "Medium-High", "High"]


def test_water_band_nan_is_unbanded_and_result_is_gcm_pool_independent():
    out = rb.water_risk_band([np.nan, 0.5])
    assert out[0] is None and out[1] == "Medium-High"


def test_s_water_uses_raw_within_water_weights():
    # S_water = 0.4164*ws + 0.2505*sv + 0.3331*iv on RAW values
    w = ccrs.WITHIN_WATER_WEIGHTS
    val = rb.s_water([1.0], [2.0], [3.0])[0]
    assert val == pytest.approx(w["ws"] * 1 + w["sv"] * 2 + w["iv"] * 3)


# --------------------------------------------------------------------------
# 2. HeatRiskBand -- p25/p75/p95 on a known sample
# --------------------------------------------------------------------------
def test_heat_percentile_cuts_on_known_sample():
    sample = np.arange(0, 101)               # 0..100 inclusive
    cuts = rb.heat_percentile_cuts(sample)
    assert cuts == {
        25: np.percentile(sample, 25),
        75: np.percentile(sample, 75),
        95: np.percentile(sample, 95),
    }
    assert (cuts[25], cuts[75], cuts[95]) == (25.0, 75.0, 95.0)


def test_heat_band_classification_against_computed_cuts():
    cuts = {25: 25.0, 75: 75.0, 95: 95.0}
    got = list(rb.heat_risk_band([10.0, 25.0, 50.0, 75.0, 90.0, 95.0, 120.0], cuts))
    #                               LOW  MED*  MED   HIGH*  HIGH  EXT*   EXT     (* = exactly on cut -> higher band)
    assert got == ["LOW", "MEDIUM", "MEDIUM", "HIGH", "HIGH", "EXTREME", "EXTREME"]


def test_heat_percentile_cuts_ignores_nan():
    cuts = rb.heat_percentile_cuts([np.nan, 0.0, 50.0, 100.0, np.nan])
    assert cuts == rb.heat_percentile_cuts([0.0, 50.0, 100.0])


# --------------------------------------------------------------------------
# 3. HeatRiskBand uses GFDL-ESM4 alone -- not MIROC6, not a blend
# --------------------------------------------------------------------------
def test_primary_gcm_is_gfdl_and_is_first_configured():
    assert rb.PRIMARY_GCM == "gfdl_esm4"
    assert rb.PRIMARY_GCM == ccrs.configured_models()[0]


def test_compute_bands_heat_side_is_gfdl_only(monkeypatch):
    calls = []

    def fake_sample_terms(model):
        calls.append(model)
        # heat is wildly different per GCM; gfdl small, miroc6 large
        heat = {"gfdl_esm4": 1.0, "miroc6": 500.0}[model]
        return _fake_terms([
            {"plant_uid": "T-1", "ws": 0.1, "sv": 0.1, "iv": 0.1, "heat": heat},
            {"plant_uid": "T-2", "ws": 0.1, "sv": 0.1, "iv": 0.1, "heat": heat * 2},
            {"plant_uid": "T-3", "ws": 0.1, "sv": 0.1, "iv": 0.1, "heat": heat * 3},
        ])

    monkeypatch.setattr(ccrs, "sample_terms", fake_sample_terms)

    result = rb.compute_bands()                      # default -> primary GCM
    assert calls == ["gfdl_esm4"]                    # sampled once, gfdl only
    assert result.heat_gcm == "gfdl_esm4"
    # heat_days column is the gfdl values (1, 2, 3), never miroc6 (500, ...)
    assert sorted(result.frame["heat_days"]) == [1.0, 2.0, 3.0]
    # cuts are percentiles of the gfdl sample, not miroc6, not a pooled mix
    assert result.heat_cuts == rb.heat_percentile_cuts([1.0, 2.0, 3.0])
    assert max(result.heat_cuts.values()) < 10       # nowhere near the miroc6 scale


def test_compute_bands_miroc6_uses_its_own_percentiles_not_a_blend(monkeypatch):
    def fake_sample_terms(model):
        heat = {"gfdl_esm4": 1.0, "miroc6": 500.0}[model]
        return _fake_terms([
            {"plant_uid": "T-1", "heat": heat},
            {"plant_uid": "T-2", "heat": heat * 2},
        ])

    monkeypatch.setattr(ccrs, "sample_terms", fake_sample_terms)
    result = rb.compute_bands("miroc6")
    assert result.heat_gcm == "miroc6"
    assert result.heat_cuts == rb.heat_percentile_cuts([500.0, 1000.0])
    # not the gfdl cuts, not the mean of the two
    assert result.heat_cuts != rb.heat_percentile_cuts([1.0, 2.0])


# --------------------------------------------------------------------------
# 4. plant_uid is the identity key
# --------------------------------------------------------------------------
def test_bands_keyed_by_plant_uid_not_plant_name(monkeypatch):
    def fake_sample_terms(model):
        return _fake_terms([
            # same plant_name, distinct plant_uid, different water inputs
            {"plant_uid": "BRA-aaaa", "plant_name": "Shared Name",
             "ws": 0.05, "sv": 0.05, "iv": 0.05, "heat": 1.0},   # low S_water
            {"plant_uid": "BRA-bbbb", "plant_name": "Shared Name",
             "ws": 1.5, "sv": 1.5, "iv": 1.5, "heat": 1.0},      # high S_water
        ])

    monkeypatch.setattr(ccrs, "sample_terms", fake_sample_terms)
    frame = rb.compute_bands().frame

    assert rb.PLANT_UID in frame.columns
    assert len(frame) == 2
    by_uid = dict(zip(frame[rb.PLANT_UID], frame["water_risk_band"]))
    assert by_uid["BRA-aaaa"] == "Low"
    assert by_uid["BRA-bbbb"] == "Extremely-High"
    # the shared name did not collapse or cross the two records
    assert frame["plant_name"].tolist() == ["Shared Name", "Shared Name"]


# --------------------------------------------------------------------------
# 5. the two bands are never merged into one score
# --------------------------------------------------------------------------
def test_output_has_two_separate_band_columns_and_no_combined_column(monkeypatch):
    monkeypatch.setattr(ccrs, "sample_terms", lambda model: _fake_terms([
        {"plant_uid": "T-1", "ws": 0.3, "sv": 0.3, "iv": 0.3, "heat": 5.0},
        {"plant_uid": "T-2", "ws": 0.9, "sv": 0.9, "iv": 0.9, "heat": 50.0},
    ]))
    cols = set(rb.compute_bands().frame.columns)
    assert {"water_risk_band", "heat_risk_band"} <= cols
    forbidden = ("combined", "overall", "risk_band_combined", "ccrs_band",
                 "band_score", "merged_band", "total_band")
    assert not any(f in c for c in cols for f in forbidden)


def test_no_public_function_combines_the_two_bands():
    combining = [
        n for n in dir(rb)
        if callable(getattr(rb, n)) and not n.startswith("_")
        and any(k in n.lower() for k in ("combine", "merge", "overall", "blend"))
    ]
    assert combining == []


def test_band_label_sets_are_disjoint():
    # water bands are Title-case, heat bands UPPER -- they can never be
    # confused for one ordinal scale
    assert set(rb.WATER_RISK_BANDS).isdisjoint(rb.HEAT_RISK_BANDS)


def test_contingency_table_is_a_2d_crosstab_never_a_scalar(monkeypatch):
    monkeypatch.setattr(ccrs, "sample_terms", lambda model: _fake_terms([
        {"plant_uid": "T-1", "ws": 0.05, "sv": 0.05, "iv": 0.05, "heat": 1.0},
        {"plant_uid": "T-2", "ws": 1.5, "sv": 1.5, "iv": 1.5, "heat": 100.0},
        {"plant_uid": "T-3", "ws": 0.5, "sv": 0.5, "iv": 0.5, "heat": 20.0},
    ]))
    frame = rb.compute_bands().frame
    tab = rb.contingency_table(frame, "count")
    assert list(tab.index) == list(rb.WATER_RISK_BANDS)
    assert list(tab.columns) == list(rb.HEAT_RISK_BANDS)
    assert tab.to_numpy().sum() == len(frame.dropna(subset=["water_risk_band", "heat_risk_band"]))
    cap = rb.contingency_table(frame, "capacity_mw")
    assert cap.shape == (len(rb.WATER_RISK_BANDS), len(rb.HEAT_RISK_BANDS))
    with pytest.raises(ValueError):
        rb.contingency_table(frame, "combined_score")


# --------------------------------------------------------------------------
# report emits the comparability warning verbatim
# --------------------------------------------------------------------------
def test_build_summary_contains_the_heat_warning_verbatim(monkeypatch):
    monkeypatch.setattr(ccrs, "sample_terms", lambda model: _fake_terms([
        {"plant_uid": "T-1", "ws": 0.3, "sv": 0.3, "iv": 0.3, "heat": 5.0},
        {"plant_uid": "T-2", "ws": 0.9, "sv": 0.9, "iv": 0.9, "heat": 50.0},
    ]))
    text = rb.build_summary(rb.compute_bands())
    assert rb.HEAT_BAND_WARNING in text
    assert "not comparable across runs" in rb.HEAT_BAND_WARNING.lower()
    assert "never" in text.lower() and "merge" in text.lower()
    assert "stable across runs" in rb.HEAT_BAND_WARNING


# --------------------------------------------------------------------------
# real-data sanity (skipped if inputs absent)
# --------------------------------------------------------------------------
def _inputs_present() -> bool:
    try:
        return (ccrs.raster_path("heat", "Brazil", "opt", "gfdl_esm4").exists()
                and (ccrs.ASSETS_PROCESSED / "gem_validated_plants_Brazil.csv").exists())
    except Exception:
        return False


@pytest.mark.skipif(not _inputs_present(), reason="processed rasters / plant CSVs absent")
def test_real_data_bands_and_pooled_heat_split():
    result = rb.compute_bands()
    frame = result.frame
    assert (frame[rb.PLANT_UID].value_counts() == len(ccrs.WATER_SCENARIOS)).all()
    assert set(frame["water_risk_band"].dropna()) <= set(rb.WATER_RISK_BANDS)
    assert set(frame["heat_risk_band"].dropna()) <= set(rb.HEAT_RISK_BANDS)
    # pooled heat split is ~25 / 50 / 20 / 5 by construction
    shares = frame["heat_risk_band"].value_counts(normalize=True)
    assert shares["LOW"] == pytest.approx(0.25, abs=0.03)
    assert shares["EXTREME"] == pytest.approx(0.05, abs=0.02)


# --------------------------------------------------------------------------
# 9. worst_case_band -- ordinal max across the two independent scales
# (Douglas's 2026-09-05 request), NOT a merge -- see the module comment
# above worst_case_band for the proposed rank mapping and tie-break.
# --------------------------------------------------------------------------
def test_worst_case_rank_tables_span_0_to_1_in_scale_order():
    assert [rb.WATER_BAND_RANK[b] for b in rb.WATER_RISK_BANDS] == [0.0, 0.25, 0.5, 0.75, 1.0]
    assert [rb.HEAT_BAND_RANK[b] for b in rb.HEAT_RISK_BANDS] == pytest.approx(
        [0.0, 1 / 3, 2 / 3, 1.0]
    )


def test_worst_case_band_water_worse():
    # water at "High" (0.75) outranks heat at "MEDIUM" (0.333)
    label, determinant = rb.worst_case_band("High", "MEDIUM")
    assert (label, determinant) == ("High", "water")


def test_worst_case_band_heat_worse():
    # heat at "EXTREME" (1.0) outranks water at "Low-Medium" (0.25)
    label, determinant = rb.worst_case_band("Low-Medium", "EXTREME")
    assert (label, determinant) == ("EXTREME", "heat")


def test_worst_case_band_tie_defaults_to_water():
    # both at the bottom of their own scale -- a rank tie (0.0 == 0.0)
    label, determinant = rb.worst_case_band("Low", "LOW")
    assert (label, determinant) == ("Low", "water")
    # both at the top of their own scale -- a rank tie (1.0 == 1.0)
    label, determinant = rb.worst_case_band("Extremely-High", "EXTREME")
    assert (label, determinant) == ("Extremely-High", "water")


def test_worst_case_band_both_lowest_is_the_tie_case_not_an_error():
    # explicit 4th case from the brief: both at their own lowest level
    label, determinant = rb.worst_case_band("Low", "LOW")
    assert label in rb.WATER_RISK_BANDS  # resolves to the water label on tie
    assert determinant == rb.WORST_CASE_TIE_BREAK


def test_worst_case_band_none_when_either_input_is_unbanded():
    assert rb.worst_case_band(None, "HIGH") == (None, None)
    assert rb.worst_case_band("High", None) == (None, None)


def test_worst_case_band_frame_adds_two_columns_not_a_score():
    frame = pd.DataFrame({
        "water_risk_band": ["Low", "High", "Extremely-High", None],
        "heat_risk_band": ["LOW", "MEDIUM", "EXTREME", "HIGH"],
    })
    out = rb.worst_case_band_frame(frame)
    # row 2 is a top-of-scale tie (Extremely-High == EXTREME, both rank 1.0) -> water wins
    assert list(out["worst_case_band"]) == ["Low", "High", "Extremely-High", None]
    assert list(out["worst_case_determinant"]) == ["water", "water", "water", None]
    assert not any(pd.api.types.is_numeric_dtype(out[c]) for c in ("worst_case_band", "worst_case_determinant"))
