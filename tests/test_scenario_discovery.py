"""Tests for src/index/scenario_discovery.py -- GEAR v3 Phase 6.3's
scenario-discovery / OAT analyses. Real-data (risk_bands/psae) tests skip
when processed rasters are absent, same convention as
tests/test_sensitivity_recompute.py. The correlation-gate sweep only needs
the already-computed CSV, so it has its own, separate skip condition."""

from pathlib import Path

import pytest

from src.config import OUTPUT_TABLES
from src.index import hazard_scope as hs
from src.index import risk_calculator as rc
from src.index import scenario_discovery as sd


def _rasters_present() -> bool:
    try:
        p = rc.raster_path("heat", "Brazil", "opt", rc.configured_models()[0])
        q = rc.raster_path("ws", "Brazil", "opt", rc.configured_models()[0])
        return p.exists() and q.exists()
    except Exception:
        return False


def _correlation_gate_csv_present() -> bool:
    return (OUTPUT_TABLES / "correlation_gate.csv").exists()


# --------------------------------------------------------------------------
# Hazard-removal OAT mechanism -- pure, no I/O
# --------------------------------------------------------------------------
def test_meaningful_removals_excludes_wind_bucket():
    """Wind's H_b has exactly one hazard -- removing it would empty H_b,
    a structural error hazard_scope._validate() already guards, so it must
    not appear in MEANINGFUL_REMOVALS."""
    assert "wind" not in sd.MEANINGFUL_REMOVALS


def test_meaningful_removals_covers_hydro_thermal_solar_with_full_counts():
    assert set(sd.MEANINGFUL_REMOVALS) == {"hydro", "thermal", "solar"}
    assert len(sd.MEANINGFUL_REMOVALS["hydro"]) == 5
    assert len(sd.MEANINGFUL_REMOVALS["thermal"]) == 3
    assert len(sd.MEANINGFUL_REMOVALS["solar"]) == 3


def test_hazard_removed_context_manager_shrinks_and_restores_h_b():
    original = hs.APPLICABLE_HAZARDS["hydro"]
    with sd._hazard_removed("hydro", "spei") as reduced:
        assert "spei" not in reduced
        assert len(reduced) == len(original) - 1
        assert hs.APPLICABLE_HAZARDS["hydro"] == reduced
    assert hs.APPLICABLE_HAZARDS["hydro"] == original


def test_hazard_removed_restores_even_on_exception():
    original = hs.APPLICABLE_HAZARDS["thermal"]
    with pytest.raises(RuntimeError):
        with sd._hazard_removed("thermal", "heat"):
            raise RuntimeError("boom")
    assert hs.APPLICABLE_HAZARDS["thermal"] == original


# --------------------------------------------------------------------------
# PSAE cut-point classification -- pure, no I/O
# --------------------------------------------------------------------------
def test_classify_at_cut_matches_baseline_at_cut_point_five():
    from src.index import psae as psae_mod

    for value in (0.0, 0.2, 0.33, 0.5, 0.6, 0.66, 1.0, None, float("nan")):
        assert sd._classify_at_cut(value, 0.5) == psae_mod.classify_psae_fraction(value)


def test_classify_at_cut_shifted_boundary_changes_only_the_0_5_region():
    # a value of exactly 0.5 is HIGH at cut=0.4 baseline unaffected at the
    # degenerate 0.0/1.0 boundaries
    assert sd._classify_at_cut(0.0, 0.4) == "LOW"
    assert sd._classify_at_cut(1.0, 0.6) == "EXTREME"
    assert sd._classify_at_cut(0.4, 0.4) == "HIGH"   # at cut, HIGH begins
    assert sd._classify_at_cut(0.4, 0.5) == "MEDIUM"  # below the 0.5 baseline cut


# --------------------------------------------------------------------------
# Correlation-gate sweep -- needs only the already-computed CSV
# --------------------------------------------------------------------------
@pytest.mark.skipif(not _correlation_gate_csv_present(), reason="correlation_gate.csv not computed")
def test_correlation_gate_sweep_covers_every_swept_threshold():
    out = sd.correlation_gate_sweep()
    assert set(out["threshold"].unique()) == set(sd.SWEPT_THRESHOLDS)
    assert (out["verdict"].isin(["pass", "fail", "insufficient_data"])).all()


@pytest.mark.skipif(not _correlation_gate_csv_present(), reason="correlation_gate.csv not computed")
def test_correlation_gate_sweep_flip_has_a_resolved_tie_breaker():
    out = sd.correlation_gate_sweep()
    flips = out[out["verdict"] == "fail"]
    assert flips["retained_term"].notna().all()
    assert flips["criterion"].notna().all()


@pytest.mark.skipif(not _correlation_gate_csv_present(), reason="correlation_gate.csv not computed")
def test_correlation_gate_sweep_missing_csv_raises_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        sd.correlation_gate_sweep(csv_path=tmp_path / "does_not_exist.csv")


# --------------------------------------------------------------------------
# Real-data, full-scale (cheap) end-to-end
# --------------------------------------------------------------------------
@pytest.mark.skipif(not _rasters_present(), reason="processed rasters absent -- cannot compute risk bands")
def test_hazard_removal_oat_produces_twelve_removals_times_four_labels_times_three_countries():
    out = sd.hazard_removal_oat()
    n_removals = sum(len(v) for v in sd.MEANINGFUL_REMOVALS.values())
    assert n_removals == 11  # 5 + 3 + 3
    assert set(out["removed_hazard"].unique()) <= {
        h for hazards in sd.MEANINGFUL_REMOVALS.values() for h in hazards
    }
    assert set(out["psae_label"].unique()) == set(sd.PSAE_LABELS)
    # every (bucket, removed_hazard, country) triple has all four labels
    counts = out.groupby(["bucket", "removed_hazard", "country"]).size()
    assert (counts == 4).all()


@pytest.mark.skipif(not _rasters_present(), reason="processed rasters absent -- cannot compute risk bands")
def test_psae_cutpoint_oat_never_changes_the_degenerate_boundaries():
    out = sd.psae_cutpoint_oat()
    extreme_rows = out[out["psae_value"] == 1.0]
    low_rows = out[out["psae_value"] == 0.0]
    assert (extreme_rows["label_at_cut"] == "EXTREME").all()
    assert (low_rows["label_at_cut"] == "LOW").all()
