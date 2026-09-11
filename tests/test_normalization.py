"""Tests for src/index/normalization -- Phase 2.4, GEAR v3 work plan.

Covers: the normality/skewness check's decisive skewness criterion (Shapiro-
Wilk reported but not deciding), transform selection never returning the
retired ``log1p_minmax``, the arithmetic and boundary behaviour of
``transform_neg_log_minmax`` (monotonic, bounded, no singularity at the
pooled maximum), the candidate term set including the Phase 2.1/2.3
additions and the Wildfire exclusion, and the origin table's schema and
per-row transform-selection consistency.

Pure-function tests only -- no raster or plant-CSV I/O, so these run
without any processed data on disk.
"""

import numpy as np
import pandas as pd

from src.index import normalization as norm
from src.index import risk_calculator as rc


# --------------------------------------------------------------------------
# Candidate term set
# --------------------------------------------------------------------------
def test_candidate_terms_include_2_1_and_2_3_additions():
    assert "precip" in norm.NORMALIZATION_CANDIDATE_TERMS
    assert "wind" in norm.NORMALIZATION_CANDIDATE_TERMS


def test_candidate_terms_include_sv_iv_as_independent_terms():
    assert "sv" in norm.NORMALIZATION_CANDIDATE_TERMS
    assert "iv" in norm.NORMALIZATION_CANDIDATE_TERMS


def test_wildfire_is_not_a_candidate():
    assert not any("fire" in t.lower() or "wildfire" in t.lower()
                   for t in norm.NORMALIZATION_CANDIDATE_TERMS)
    assert not any("wildfire" in label.lower() for label in norm.HAZARD_LABELS.values())


def test_wind_is_flat_not_gcm_dependent():
    assert "wind" in norm.FLAT_BOUND_TERMS
    assert "wind" not in norm.GCM_DEPENDENT_TERMS


def test_precip_is_gcm_dependent_like_heat_and_spei():
    assert "precip" in norm.GCM_DEPENDENT_TERMS


def test_every_candidate_has_an_origin_source_and_label():
    for term in norm.NORMALIZATION_CANDIDATE_TERMS:
        assert term in norm.ORIGIN_SOURCE
        assert term in norm.HAZARD_LABELS


# --------------------------------------------------------------------------
# Normality/skewness check
# --------------------------------------------------------------------------
def test_symmetric_sample_is_not_flagged_skewed():
    rng = np.random.default_rng(1)
    sample = rng.normal(loc=10.0, scale=2.0, size=2000)
    check = norm.normality_check(sample)
    assert abs(check["skewness"]) <= norm.SKEWNESS_NORMAL_THRESHOLD
    assert check["is_skewed"] is False


def test_right_skewed_sample_is_flagged_skewed():
    rng = np.random.default_rng(2)
    sample = rng.exponential(scale=5.0, size=2000)
    check = norm.normality_check(sample)
    assert check["skewness"] > norm.SKEWNESS_NORMAL_THRESHOLD
    assert check["is_skewed"] is True


def test_shapiro_is_reported_but_does_not_override_the_skew_verdict():
    """A large, mildly-skewed sample can have skew <= 0.5 (not flagged) even
    though Shapiro-Wilk rejects exact normality at this sample size -- the
    verdict must still follow skewness, not shapiro_p."""
    rng = np.random.default_rng(3)
    sample = rng.normal(loc=0.0, scale=1.0, size=4000) ** 2  # chi2(1)-like, mildly reshaped
    check = norm.normality_check(sample)
    assert check["shapiro_p"] is not None
    assert check["is_skewed"] == (abs(check["skewness"]) > norm.SKEWNESS_NORMAL_THRESHOLD)


def test_shapiro_subsamples_above_the_ceiling_deterministically():
    rng = np.random.default_rng(4)
    sample = rng.normal(size=norm.SHAPIRO_MAX_N + 500)
    check_a = norm.normality_check(sample)
    check_b = norm.normality_check(sample)
    assert check_a["shapiro_subsampled"] is True
    assert check_a["shapiro_stat"] == check_b["shapiro_stat"]  # deterministic seed


def test_select_transform_never_returns_retired_log1p():
    normal_check = {"is_skewed": False}
    skewed_check = {"is_skewed": True}
    assert norm.select_transform(normal_check) != "log1p_minmax"
    assert norm.select_transform(skewed_check) != "log1p_minmax"
    assert norm.select_transform(normal_check) == "direct_minmax"
    assert norm.select_transform(skewed_check) == "neg_log_minmax"


# --------------------------------------------------------------------------
# Transforms
# --------------------------------------------------------------------------
def test_direct_minmax_matches_risk_calculator_convention():
    raw = np.array([0.0, 5.0, 10.0])
    out = norm.transform_direct_minmax(raw, lo=0.0, hi=10.0)
    np.testing.assert_allclose(out, [0.0, 0.5, 1.0])


def test_neg_log_minmax_endpoints_are_0_and_1():
    lo, hi = 2.0, 50.0
    out = norm.transform_neg_log_minmax(np.array([lo, hi]), lo=lo, hi=hi)
    np.testing.assert_allclose(out, [0.0, 1.0], atol=1e-8)


def test_neg_log_minmax_is_monotonically_increasing():
    lo, hi = 0.0, 100.0
    xs = np.linspace(lo, hi, 50)
    out = norm.transform_neg_log_minmax(xs, lo=lo, hi=hi)
    assert np.all(np.diff(out) >= 0)


def test_neg_log_minmax_stays_in_unit_interval_for_out_of_pool_values():
    lo, hi = 0.0, 10.0
    out = norm.transform_neg_log_minmax(np.array([-5.0, 15.0, 1e6]), lo=lo, hi=hi)
    assert np.all(out >= 0.0) and np.all(out <= 1.0)


def test_neg_log_minmax_expands_upper_tail_relative_to_log1p():
    """The whole point of the redesign: for a right-skewed domain, the top
    of the range should be MORE spread out under neg_log_minmax than under
    the retired log1p_minmax, not compressed further."""
    lo, hi = 0.0, 100.0
    upper = np.array([90.0, 95.0, 99.0, 100.0])
    neg_log = norm.transform_neg_log_minmax(upper, lo=lo, hi=hi)
    log1p = norm.transform_log1p_minmax(upper, lo=lo, hi=hi)
    neg_log_spread = neg_log[-1] - neg_log[0]
    log1p_spread = log1p[-1] - log1p[0]
    assert neg_log_spread > log1p_spread


def test_neg_log_minmax_degenerate_domain_is_zeros():
    out = norm.transform_neg_log_minmax(np.array([1.0, 2.0]), lo=5.0, hi=5.0)
    np.testing.assert_allclose(out, [0.0, 0.0])


def test_apply_transform_dispatches_by_name():
    raw = np.array([0.0, 7.0, 10.0])
    direct = norm.apply_transform("direct_minmax", raw, 0.0, 10.0)
    neg_log = norm.apply_transform("neg_log_minmax", raw, 0.0, 10.0)
    assert not np.allclose(direct, neg_log)


def test_apply_transform_rejects_unknown_kind():
    import pytest
    with pytest.raises(ValueError):
        norm.apply_transform("not_a_real_transform", np.array([1.0]), 0.0, 1.0)


# --------------------------------------------------------------------------
# Origin table
# --------------------------------------------------------------------------
def _fake_row(term: str, gcm: str, skewed: bool) -> dict:
    check = {
        "n": 100, "skewness": 1.2 if skewed else 0.1, "is_skewed": skewed,
        "shapiro_stat": 0.9, "shapiro_p": 0.01, "shapiro_subsampled": False,
    }
    return {
        "term": term, "gcm": gcm, "bounds": (0.0, 1.0), "check": check,
        "transform": norm.select_transform(check),
    }


def test_origin_table_schema_and_row_count():
    rows = [_fake_row("ws", "pooled", skewed=True), _fake_row("heat", "gfdl_esm4", skewed=False)]
    table = norm.build_origin_table(rows)
    assert len(table) == 2
    expected_cols = {
        "hazard_term", "hazard_label", "gcm", "origin_source", "data_tier",
        "lower_bound_raw", "upper_bound_raw", "pool_n", "skewness",
        "shapiro_stat", "shapiro_p", "shapiro_subsampled", "is_skewed",
        "transform_selected", "transform_note",
    }
    assert expected_cols == set(table.columns)


def test_origin_table_transform_selected_matches_is_skewed():
    rows = [_fake_row("precip", "gfdl_esm4", skewed=True), _fake_row("sv", "pooled", skewed=False)]
    table = norm.build_origin_table(rows)
    for _, row in table.iterrows():
        expected = "neg_log_minmax" if row["is_skewed"] else "direct_minmax"
        assert row["transform_selected"] == expected


def test_origin_table_never_records_the_retired_transform():
    rows = [_fake_row(t, "pooled", skewed=s) for t, s in
            [("ws", True), ("sv", False), ("iv", True), ("wind", False)]]
    table = norm.build_origin_table(rows)
    assert "log1p_minmax" not in set(table["transform_selected"])


# --------------------------------------------------------------------------
# risk_calculator infrastructure is unchanged (Phase 2.4 imports, not rebuilds)
# --------------------------------------------------------------------------
def test_risk_calculator_frozen_bounds_and_hazard_terms_untouched():
    assert rc.HAZARD_TERMS == ("ws", "heat", "sv", "iv", "spei")
    assert set(rc.FROZEN_BOUNDS) == set(rc.HAZARD_TERMS)
