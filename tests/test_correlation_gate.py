"""Tests for src/index/correlation_gate -- Phase 2.5, GEAR v3 work plan.

Covers: the spatial-harmonization guard (missing raster -> skipped, not a
crash; a genuine mismatch still raises loudly), the Pearson/Spearman
decision logic (nonlinearity flag, decision-method selection), the gate
verdict logic per pair (pass/fail/report-only/insufficient-data, and that
the report-only pair never gets a fail verdict regardless of ``r``), and
the tie-breaker dispatch (Criterion 1/2/3, including the sv/iv pair firing
Criterion 3 with iv retained).

Pure-function tests only where possible -- no raster or plant-CSV I/O
needed for gate-logic/tie-breaker tests. ``verify_harmonized_grid``'s
"missing raster" branch is also pure I/O-avoidance (checks ``Path.exists``
before ever opening a file).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.index import correlation_gate as cg
from src.processors._common import GridMismatchError


# --------------------------------------------------------------------------
# Candidate pairs / scope
# --------------------------------------------------------------------------
def test_exactly_six_candidate_pairs():
    assert len(cg.CANDIDATE_PAIRS) == 6


def test_exactly_one_report_only_pair_and_it_is_ws_vs_spei():
    assert len(cg.REPORT_ONLY_PAIRS) == 1
    pair = cg.REPORT_ONLY_PAIRS[0]
    assert {pair.term_a, pair.term_b} == {"ws", "spei"}


def test_five_gated_pairs():
    assert len(cg.GATED_PAIRS) == 5
    for pair in cg.GATED_PAIRS:
        assert pair.gated is True


def test_extreme_wind_and_wildfire_are_never_candidates():
    terms = {t for p in cg.CANDIDATE_PAIRS for t in (p.term_a, p.term_b)}
    assert "wind" not in terms
    assert not any("fire" in t.lower() for t in terms)


def test_precip_vs_spei_and_ws_vs_spei_are_hydro_only():
    for pair in cg.CANDIDATE_PAIRS:
        if {pair.term_a, pair.term_b} in ({"precip", "spei"}, {"ws", "spei"}):
            assert pair.buckets == ("hydro",)


def test_water_pairs_are_restricted_to_water_buckets():
    for pair in cg.CANDIDATE_PAIRS:
        assert set(pair.buckets) <= {"hydro", "thermal"}


# --------------------------------------------------------------------------
# Spatial harmonization guard
# --------------------------------------------------------------------------
def test_verify_harmonized_grid_skips_missing_rasters(monkeypatch, tmp_path):
    monkeypatch.setattr(
        cg, "_term_raster_path",
        lambda term, country, scen, model: tmp_path / f"{term}_{country}_{model}_does_not_exist.tif",
    )
    result = cg.verify_harmonized_grid("precip", "ws", "Portugal", "gfdl_esm4")
    assert result is False


def test_verify_harmonized_grid_raises_on_a_real_mismatch(monkeypatch, tmp_path):
    """A genuine grid mismatch (different shape) must still raise loudly --
    the missing-file skip must not swallow a real problem."""
    import rioxarray  # noqa: F401
    import xarray as xr
    import rasterio
    from rasterio.transform import from_origin

    def _write(path: Path, width: int, height: int) -> None:
        transform = from_origin(0.0, 0.0, 0.01, 0.01)
        with rasterio.open(
            path, "w", driver="GTiff", width=width, height=height, count=1,
            dtype="float32", crs="EPSG:4326", transform=transform,
        ) as dst:
            dst.write(np.zeros((height, width), dtype="float32"), 1)

    path_a = tmp_path / "a.tif"
    path_b = tmp_path / "b.tif"
    _write(path_a, 10, 10)
    _write(path_b, 20, 20)  # different shape -> mismatch

    monkeypatch.setattr(
        cg, "_term_raster_path",
        lambda term, country, scen, model: path_a if term == "precip" else path_b,
    )
    with pytest.raises(GridMismatchError):
        cg.verify_harmonized_grid("precip", "ws", "Brazil", "gfdl_esm4")


# --------------------------------------------------------------------------
# Pearson/Spearman decision logic
# --------------------------------------------------------------------------
def test_compute_pair_correlation_perfect_linear():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    y = 2.0 * x + 1.0
    stats = cg.compute_pair_correlation(x, y)
    assert stats["n"] == 5
    assert stats["pearson_r"] == pytest.approx(1.0)
    assert stats["spearman_rho"] == pytest.approx(1.0)


def test_compute_pair_correlation_drops_non_finite_pairs():
    x = np.array([1.0, 2.0, np.nan, 4.0, 5.0])
    y = np.array([1.0, 2.0, 3.0, np.nan, 5.0])
    stats = cg.compute_pair_correlation(x, y)
    assert stats["n"] == 3  # indices 0, 1, 4


def test_compute_pair_correlation_too_few_points_is_nan_not_an_error():
    stats = cg.compute_pair_correlation(np.array([1.0, 2.0]), np.array([1.0, 2.0]))
    assert stats["n"] == 2
    assert np.isnan(stats["pearson_r"])
    assert np.isnan(stats["spearman_rho"])


def test_flag_nonlinearity_true_when_rank_correlation_much_stronger():
    # A monotonic-but-curved relationship: weak linear r, strong rank rho.
    assert cg.flag_nonlinearity(pearson_r=0.40, spearman_rho=0.85) is True


def test_flag_nonlinearity_false_when_close():
    assert cg.flag_nonlinearity(pearson_r=0.75, spearman_rho=0.80) is False


def test_flag_nonlinearity_false_on_nan():
    assert cg.flag_nonlinearity(pearson_r=np.nan, spearman_rho=0.9) is False


# --------------------------------------------------------------------------
# Tie-breaker dispatch (Criteria 1/2/3)
# --------------------------------------------------------------------------
def test_criterion_1_precip_vs_ws_hydro_retains_precip():
    winner, criterion = cg.resolve_tie_breaker("precip", "ws", "hydro")
    assert winner == "precip"
    assert criterion == 1


def test_criterion_1_precip_vs_ws_thermal_retains_ws():
    winner, criterion = cg.resolve_tie_breaker("precip", "ws", "thermal")
    assert winner == "ws"
    assert criterion == 1


def test_criterion_1_precip_vs_spei_hydro_retains_spei():
    winner, criterion = cg.resolve_tie_breaker("precip", "spei", "hydro")
    assert winner == "spei"
    assert criterion == 1


def test_criterion_2_sv_vs_ws_retains_ws_on_data_tier():
    winner, criterion = cg.resolve_tie_breaker("sv", "ws", "hydro")
    assert winner == "ws"
    assert criterion == 2


def test_criterion_2_iv_vs_ws_retains_ws_on_data_tier():
    winner, criterion = cg.resolve_tie_breaker("iv", "ws", "thermal")
    assert winner == "ws"
    assert criterion == 2


def test_criterion_3_sv_vs_iv_retains_iv():
    winner, criterion = cg.resolve_tie_breaker("sv", "iv", "hydro")
    assert winner == "iv"
    assert criterion == 3
    assert winner == cg.SV_IV_CRITERION_3_WINNER


def test_tie_breaker_is_symmetric_in_argument_order():
    a, ca = cg.resolve_tie_breaker("sv", "iv", "thermal")
    b, cb = cg.resolve_tie_breaker("iv", "sv", "thermal")
    assert a == b == "iv"
    assert ca == cb == 3


# --------------------------------------------------------------------------
# Gate verdict logic (pure, via monkeypatched sampling)
# --------------------------------------------------------------------------
def _fake_frame(col_a: str, col_b: str, a_vals, b_vals, bucket="hydro", country="Brazil"):
    import pandas as pd
    return pd.DataFrame({
        "bucket": [bucket] * len(a_vals),
        "country": [country] * len(a_vals),
        col_a: a_vals,
        col_b: b_vals,
    })


def test_gate_fails_and_dispatches_tie_breaker_on_a_known_high_correlation_case(monkeypatch):
    """A synthetic sv/iv pair engineered to correlate above the gate
    threshold must fail the gate and retain iv via Criterion 3."""
    rng = np.random.default_rng(0)
    base = rng.normal(size=200)
    sv = base + rng.normal(scale=0.01, size=200)  # near-identical -> |r| >= 0.80
    iv = base + rng.normal(scale=0.01, size=200)

    frame = _fake_frame("sv", "iv", sv, iv)
    sv_iv_pair = next(p for p in cg.CANDIDATE_PAIRS if {p.term_a, p.term_b} == {"sv", "iv"})
    monkeypatch.setattr(cg, "CANDIDATE_PAIRS", (sv_iv_pair,))
    monkeypatch.setattr(cg, "sample_gate_terms", lambda models=None: frame)
    monkeypatch.setattr(cg, "COUNTRIES", ["Brazil"])
    monkeypatch.setattr(cg, "verify_harmonized_grid", lambda *a, **k: False)

    table = cg.run_gate(models=["gfdl_esm4"])
    row = table[(table["term_a"] == "sv") & (table["term_b"] == "iv")
                & (table["country"] == "Brazil") & (table["bucket"] == "hydro")].iloc[0]
    assert abs(row["decision_r"]) >= cg.GATE_THRESHOLD
    assert row["gate_verdict"] == "fail"
    assert row["retained_term"] == "iv"
    assert row["excluded_term"] == "sv"
    assert row["criterion"] == 3


def test_gate_passes_on_a_known_low_correlation_case(monkeypatch):
    rng = np.random.default_rng(1)
    sv = rng.normal(size=200)
    iv = rng.normal(size=200)  # independent -> |r| small

    frame = _fake_frame("sv", "iv", sv, iv)
    sv_iv_pair = next(p for p in cg.CANDIDATE_PAIRS if {p.term_a, p.term_b} == {"sv", "iv"})
    monkeypatch.setattr(cg, "CANDIDATE_PAIRS", (sv_iv_pair,))
    monkeypatch.setattr(cg, "sample_gate_terms", lambda models=None: frame)
    monkeypatch.setattr(cg, "COUNTRIES", ["Brazil"])
    monkeypatch.setattr(cg, "verify_harmonized_grid", lambda *a, **k: False)

    table = cg.run_gate(models=["gfdl_esm4"])
    row = table[(table["term_a"] == "sv") & (table["term_b"] == "iv")
                & (table["country"] == "Brazil") & (table["bucket"] == "hydro")].iloc[0]
    assert abs(row["decision_r"]) < cg.GATE_THRESHOLD
    assert row["gate_verdict"] == "pass"
    assert row["retained_term"] is None


def test_report_only_pair_never_fails_even_at_perfect_correlation(monkeypatch):
    x = np.linspace(0, 1, 50)
    frame = _fake_frame("ws", "spei__gfdl_esm4", x, x)  # perfectly correlated
    ws_spei_pair = next(p for p in cg.CANDIDATE_PAIRS if {p.term_a, p.term_b} == {"ws", "spei"})
    monkeypatch.setattr(cg, "CANDIDATE_PAIRS", (ws_spei_pair,))
    monkeypatch.setattr(cg, "sample_gate_terms", lambda models=None: frame)
    monkeypatch.setattr(cg, "COUNTRIES", ["Brazil"])
    monkeypatch.setattr(cg, "verify_harmonized_grid", lambda *a, **k: False)

    table = cg.run_gate(models=["gfdl_esm4"])
    row = table[(table["term_a"] == "ws") & (table["term_b"] == "spei")
                & (table["country"] == "Brazil")].iloc[0]
    assert abs(row["decision_r"]) >= cg.GATE_THRESHOLD  # would fail if it were gated
    assert row["gate_verdict"] == "report_only"
    assert row["retained_term"] is None
    assert row["excluded_term"] is None


def test_pooled_country_row_never_carries_a_gate_verdict(monkeypatch):
    rng = np.random.default_rng(2)
    sv = rng.normal(size=100)
    iv = rng.normal(size=100)
    frame = _fake_frame("sv", "iv", sv, iv)
    sv_iv_pair = next(p for p in cg.CANDIDATE_PAIRS if {p.term_a, p.term_b} == {"sv", "iv"})
    monkeypatch.setattr(cg, "CANDIDATE_PAIRS", (sv_iv_pair,))
    monkeypatch.setattr(cg, "sample_gate_terms", lambda models=None: frame)
    monkeypatch.setattr(cg, "COUNTRIES", ["Brazil"])
    monkeypatch.setattr(cg, "verify_harmonized_grid", lambda *a, **k: False)

    table = cg.run_gate(models=["gfdl_esm4"])
    pooled = table[table["country"] == "pooled"]
    assert len(pooled) > 0
    assert pooled["gate_verdict"].isna().all()


def test_missing_data_produces_insufficient_data_verdict_not_a_crash(monkeypatch):
    frame = _fake_frame("sv", "iv", [np.nan] * 10, [np.nan] * 10)
    sv_iv_pair = next(p for p in cg.CANDIDATE_PAIRS if {p.term_a, p.term_b} == {"sv", "iv"})
    monkeypatch.setattr(cg, "CANDIDATE_PAIRS", (sv_iv_pair,))
    monkeypatch.setattr(cg, "sample_gate_terms", lambda models=None: frame)
    monkeypatch.setattr(cg, "COUNTRIES", ["Brazil"])
    monkeypatch.setattr(cg, "verify_harmonized_grid", lambda *a, **k: False)

    table = cg.run_gate(models=["gfdl_esm4"])
    row = table[(table["term_a"] == "sv") & (table["term_b"] == "iv")
                & (table["country"] == "Brazil")].iloc[0]
    assert row["gate_verdict"] == "insufficient_data"


# --------------------------------------------------------------------------
# Real-data integration (skipped if the processed rasters/plant CSVs are
# absent -- never silently passed).
# --------------------------------------------------------------------------
def _real_data_present() -> bool:
    from src.config import ASSETS_PROCESSED
    return (ASSETS_PROCESSED / "gem_validated_plants_Brazil.csv").exists()


@pytest.mark.skipif(not _real_data_present(), reason="processed plant/raster data absent")
def test_run_gate_against_real_data_produces_the_documented_schema():
    table = cg.run_gate()
    assert list(table.columns) == cg.GATE_OUTPUT_COLUMNS
    assert len(table) > 0
    # Every gated, non-pooled row with finite data must have a definite verdict.
    concrete = table[(table["country"] != "pooled") & table["n"].gt(0)]
    assert concrete["gate_verdict"].isin(
        ["pass", "fail", "report_only", "insufficient_data"]
    ).all()
