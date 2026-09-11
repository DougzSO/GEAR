"""Tests for src/index/event_multiplier -- the country-level EventMultiplier_c.

Covers all three countries against the (recomputed, full-precision) fixture
and the >=1 / rate_max invariants -- the module's own logic, independent of
any Hazard application.

The former "apply to Hazard" tests (multiplying a Hazard CSV by
EventMultiplier, country-join safety) are removed: GEAR v3 Phase 1 retires
EventMultiplier from the Risk/Hazard core entirely (docs/DECISIONS.md,
"GEAR v3 rework Phase 1"; docs/rework/GEAR_v3_work_plan.md Phase 1.4).
EventMultiplier is no longer applied to any Hazard/Risk table anywhere in
the pipeline; this module is kept importable, unused, as a Phase 5
contextual-validator candidate.
"""

import pandas as pd
import pytest

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


