"""Tests for src/index/event_multiplier -- the country-level EventMultiplier_c.

Covers all three countries against the (recomputed, full-precision) fixture,
the >=1 / rate_max invariants, and the country-keyed multiplicative
application: no row duplication or drop introduced by the join (the T1/T2
plant_uid-stability lesson, applied to a country-level join instead of a
plant_uid-level one).
"""

import numpy as np
import pandas as pd
import pytest
from pandas.errors import MergeError

from src.index import event_multiplier as em
from src.downloaders import emdat_downloader


# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------
def test_constants_match_the_spec():
    assert em.EVENT_MULTIPLIER_K == 0.5
    assert em.EMDAT_ARCHIVE_SPAN_YEARS == 124


# --------------------------------------------------------------------------
# regression fixture -- all three countries
# --------------------------------------------------------------------------
# Fixture logged in docs/DECISIONS.md / climate_risk_score_spec.md Section 7
# (3-decimal roundings): Brazil 1.192, Portugal 1.031, India 1.500.
# Recomputed full precision (this module, N_events 239/38/622, span 124):
# Brazil 1.192122, Portugal 1.030547, India 1.500000 -- diffs 0.000122 /
# 0.000453 / 0.000000, all << 0.01, so the recomputed values are accepted.
_FIXTURE_N_EVENTS = {"Brazil": 239, "Portugal": 38, "India": 622}
_FIXTURE_EVENT_MULTIPLIER = {"Brazil": 1.192122, "Portugal": 1.030547, "India": 1.500000}


def _fake_event_counts(monkeypatch):
    fake = pd.DataFrame([{"country": c, "n_events": n} for c, n in _FIXTURE_N_EVENTS.items()])
    monkeypatch.setattr(em, "load_event_counts", lambda countries=None: fake.copy())


def test_compute_event_multipliers_matches_the_regression_fixture(monkeypatch):
    _fake_event_counts(monkeypatch)
    out = em.compute_event_multipliers(list(_FIXTURE_N_EVENTS)).set_index("country")
    for country, expected in _FIXTURE_EVENT_MULTIPLIER.items():
        assert out.loc[country, "event_multiplier"] == pytest.approx(expected, abs=1e-4)
        # also within the 0.01 Step 2 acceptance band of the published 3-decimal fixture
        published = {"Brazil": 1.192, "Portugal": 1.031, "India": 1.500}[country]
        assert abs(out.loc[country, "event_multiplier"] - published) <= 0.01


def test_rate_max_is_the_highest_rate_country_and_gets_1_plus_k(monkeypatch):
    _fake_event_counts(monkeypatch)
    out = em.compute_event_multipliers(list(_FIXTURE_N_EVENTS)).set_index("country")
    assert out["rate"].idxmax() == "India"
    assert out.loc["India", "event_multiplier"] == pytest.approx(1.0 + em.EVENT_MULTIPLIER_K)


def test_event_multiplier_is_always_ge_1(monkeypatch):
    _fake_event_counts(monkeypatch)
    out = em.compute_event_multipliers(list(_FIXTURE_N_EVENTS))
    assert (out["event_multiplier"] >= 1.0).all()


def test_rate_is_n_events_over_the_archive_span(monkeypatch):
    _fake_event_counts(monkeypatch)
    out = em.compute_event_multipliers(list(_FIXTURE_N_EVENTS)).set_index("country")
    for country, n in _FIXTURE_N_EVENTS.items():
        assert out.loc[country, "rate"] == pytest.approx(n / 124)


# --------------------------------------------------------------------------
# application: country join, multiplicative, plant_uid-safe
# --------------------------------------------------------------------------
def _synthetic_hazard():
    return pd.DataFrame({
        "plant_uid": ["BRA-1", "BRA-1", "BRA-2", "PRT-1", "IND-1", "IND-2"],
        "country": ["Brazil", "Brazil", "Brazil", "Portugal", "India", "India"],
        "water_scenario": ["opt", "pes", "opt", "opt", "opt", "opt"],
        "hazard_gfdl_esm4": [0.10, 0.20, 0.30, 0.40, 0.50, 0.60],
        "hazard_miroc6": [0.15, 0.25, 0.35, 0.45, 0.55, 0.65],
    })


def _synthetic_multipliers():
    return pd.DataFrame({
        "country": ["Brazil", "Portugal", "India"],
        "n_events": [239, 38, 622],
        "rate": [239 / 124, 38 / 124, 622 / 124],
        "event_multiplier": [1.192122, 1.030547, 1.5],
    })


def test_apply_to_hazard_multiplies_by_country_never_sums(tmp_path):
    hazard = _synthetic_hazard()
    hz_csv = tmp_path / "ccrs_hazard.csv"
    hazard.to_csv(hz_csv, index=False)

    out = em.apply_to_hazard(hz_csv, multipliers=_synthetic_multipliers())

    br = out[out["country"] == "Brazil"]
    np.testing.assert_allclose(br["hazard_gfdl_esm4_x_event"], br["hazard_gfdl_esm4"] * 1.192122)
    np.testing.assert_allclose(br["hazard_miroc6_x_event"], br["hazard_miroc6"] * 1.192122)
    ind = out[out["country"] == "India"]
    np.testing.assert_allclose(ind["hazard_gfdl_esm4_x_event"], ind["hazard_gfdl_esm4"] * 1.5)
    # original Hazard columns untouched (multiplicative side column, no overwrite)
    np.testing.assert_allclose(out["hazard_gfdl_esm4"], hazard["hazard_gfdl_esm4"])


def test_apply_to_hazard_country_join_does_not_duplicate_or_drop_plant_uid_rows(tmp_path):
    hazard = _synthetic_hazard()
    hz_csv = tmp_path / "ccrs_hazard.csv"
    hazard.to_csv(hz_csv, index=False)

    out = em.apply_to_hazard(hz_csv, multipliers=_synthetic_multipliers())

    assert len(out) == len(hazard)
    # every plant_uid row (including the repeated BRA-1 scenario rows) survives
    # exactly as many times as it appeared in the input -- country join fans
    # out on nothing, since the multiplier table is one row per country.
    pd.testing.assert_series_equal(
        out["plant_uid"].value_counts().sort_index(),
        hazard["plant_uid"].value_counts().sort_index(),
    )
    assert out["plant_uid"].tolist() == hazard["plant_uid"].tolist()


def test_apply_to_hazard_rejects_a_country_missing_from_the_multiplier_table(tmp_path):
    hazard = _synthetic_hazard()
    hz_csv = tmp_path / "ccrs_hazard.csv"
    hazard.to_csv(hz_csv, index=False)

    multipliers = _synthetic_multipliers()
    multipliers = multipliers[multipliers["country"] != "India"]   # drop India on purpose
    with pytest.raises(ValueError, match="India"):
        em.apply_to_hazard(hz_csv, multipliers=multipliers)


def test_apply_to_hazard_rejects_a_duplicated_country_in_the_multiplier_table(tmp_path):
    hazard = _synthetic_hazard()
    hz_csv = tmp_path / "ccrs_hazard.csv"
    hazard.to_csv(hz_csv, index=False)

    multipliers = pd.concat([_synthetic_multipliers(), _synthetic_multipliers().iloc[[0]]],
                            ignore_index=True)   # Brazil appears twice
    # merge(..., validate="many_to_one") refuses a non-unique right side before
    # any row could silently fan out -- this is the cross-join guard.
    with pytest.raises(MergeError):
        em.apply_to_hazard(hz_csv, multipliers=multipliers)


# --------------------------------------------------------------------------
# real data sanity (skipped if the EM-DAT country CSVs are absent)
# --------------------------------------------------------------------------
def _emdat_present() -> bool:
    return all(emdat_downloader.country_csv_path(c).exists() for c in ("Brazil", "Portugal", "India"))


@pytest.mark.skipif(not _emdat_present(), reason="emdat_{country}.csv absent")
def test_real_data_n_events_match_the_published_counts():
    counts = em.load_event_counts(["Brazil", "Portugal", "India"]).set_index("country")["n_events"]
    assert counts["Brazil"] == 239
    assert counts["Portugal"] == 38
    assert counts["India"] == 622


@pytest.mark.skipif(not _emdat_present(), reason="emdat_{country}.csv absent")
def test_real_data_event_multipliers_match_the_regression_fixture():
    out = em.compute_event_multipliers(["Brazil", "Portugal", "India"]).set_index("country")
    for country, published in {"Brazil": 1.192, "Portugal": 1.031, "India": 1.500}.items():
        assert abs(out.loc[country, "event_multiplier"] - published) <= 0.01


def _hazard_csv_present() -> bool:
    return em.HAZARD_CSV.exists()


@pytest.mark.skipif(not _hazard_csv_present(), reason="ccrs_hazard.csv absent")
def test_real_data_apply_to_hazard_preserves_row_count_and_plant_uid_multiset():
    hz = pd.read_csv(em.HAZARD_CSV)
    out = em.apply_to_hazard()
    assert len(out) == len(hz)
    pd.testing.assert_series_equal(
        out["plant_uid"].value_counts().sort_index(),
        hz["plant_uid"].value_counts().sort_index(),
    )
    assert (out["event_multiplier"] >= 1.0).all()
