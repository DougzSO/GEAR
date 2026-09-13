"""Tests for src/index/hazard_scope -- Phase 3.1, GEAR v3 work plan.

Covers the H_b table's structural invariants (Methods Section 3): every
bucket has a defined, non-empty applicable set; Wildfire/SLR are absent
everywhere; Extreme Wind ('wind') appears only in the Wind and Solar
buckets; sv/iv appear only in Hydro; and the table's keys exactly match
risk_calculator.BUCKETS. Pure-function/data tests only -- no raster or
plant-CSV I/O.
"""

from __future__ import annotations

import pytest

from src.index import hazard_scope as hs
from src.index import risk_calculator as rc


def test_keys_match_risk_calculator_buckets():
    assert set(hs.APPLICABLE_HAZARDS) == set(rc.BUCKETS)


def test_every_bucket_has_a_non_empty_h_b():
    for bucket in rc.BUCKETS:
        assert len(hs.applicable_hazards(bucket)) > 0


def test_wildfire_and_slr_absent_from_every_bucket():
    for bucket, hazards in hs.APPLICABLE_HAZARDS.items():
        assert "wildfire" not in hazards, bucket
        assert "slr" not in hazards, bucket


def test_extreme_wind_only_in_wind_and_solar():
    for bucket, hazards in hs.APPLICABLE_HAZARDS.items():
        if "wind" in hazards:
            assert bucket in {"wind", "solar"}, bucket
    assert "wind" in hs.applicable_hazards("wind")
    assert "wind" in hs.applicable_hazards("solar")
    assert "wind" not in hs.applicable_hazards("hydro")
    assert "wind" not in hs.applicable_hazards("thermal")


def test_sv_iv_only_in_hydro():
    for bucket, hazards in hs.APPLICABLE_HAZARDS.items():
        if bucket == "hydro":
            continue
        assert "sv" not in hazards, bucket
        assert "iv" not in hazards, bucket
    assert "sv" in hs.applicable_hazards("hydro")
    assert "iv" in hs.applicable_hazards("hydro")


def test_hydro_h_b_matches_methods_section_3():
    assert set(hs.applicable_hazards("hydro")) == {"ws", "spei", "precip", "sv", "iv"}


def test_thermal_h_b_matches_methods_section_3():
    assert set(hs.applicable_hazards("thermal")) == {"ws", "heat", "precip"}


def test_wind_h_b_matches_methods_section_3():
    assert set(hs.applicable_hazards("wind")) == {"wind"}


def test_solar_h_b_matches_methods_section_3():
    assert set(hs.applicable_hazards("solar")) == {"heat", "precip", "wind"}


def test_applicable_hazards_raises_on_unknown_bucket():
    with pytest.raises(KeyError):
        hs.applicable_hazards("not_a_bucket")


def test_every_hazard_term_has_a_label():
    for hazards in hs.APPLICABLE_HAZARDS.values():
        for h in hazards:
            assert h in hs.HAZARD_LABELS, h


# --------------------------------------------------------------------------
# Standing regression guard -- the precip/wind integration gap.
#
# precip and wind both had a closed processor and a closed RiskBand
# classification (Phase 3.2) well before either was wired into
# risk_calculator.HAZARD_TERMS/FROZEN_BOUNDS -- Risk_i,h (Equation 1) was
# silently absent for both until a dedicated task closed it for precip
# (docs/DECISIONS.md, "GEAR v3 Risk_i,h integration gap: precip wired in,
# wind still blocked on ERA5 acquisition"). This test is the guard that
# stops that specific failure mode from recurring silently for some future
# hazard: every hazard named in a bucket's H_b must be traceable to either
# a real HAZARD_TERMS/FROZEN_BOUNDS entry or an explicit, reasoned exception
# in hazard_scope.PENDING_RISK_I_H_HAZARDS -- never simply missing from
# both with no record of why.
# --------------------------------------------------------------------------
def test_every_h_b_member_has_a_risk_i_h_entry_or_a_documented_exception():
    all_h_b_members = {h for hazards in hs.APPLICABLE_HAZARDS.values() for h in hazards}
    computable = set(rc.HAZARD_TERMS)
    pending = set(hs.PENDING_RISK_I_H_HAZARDS)

    unaccounted = all_h_b_members - computable - pending
    assert not unaccounted, (
        f"{unaccounted} appear in some bucket's H_b but have neither a "
        f"risk_calculator.HAZARD_TERMS entry nor a documented exception in "
        f"hazard_scope.PENDING_RISK_I_H_HAZARDS -- this is exactly the "
        f"precip/wind integration gap recurring for a new hazard. Either "
        f"wire it into HAZARD_TERMS/FROZEN_BOUNDS or add a reasoned entry "
        f"to PENDING_RISK_I_H_HAZARDS."
    )
    # every FROZEN_BOUNDS-backed term also needs a reason to STOP being
    # pending -- an entry cannot be in both sets at once.
    assert not (computable & pending), (
        f"{computable & pending} are in both HAZARD_TERMS and "
        f"PENDING_RISK_I_H_HAZARDS -- remove the stale pending entry now "
        f"that the hazard is wired in."
    )


def test_pending_risk_i_h_hazards_are_reasoned_not_bare():
    for hazard, reason in hs.PENDING_RISK_I_H_HAZARDS.items():
        assert isinstance(reason, str) and len(reason) > 20, (
            f"PENDING_RISK_I_H_HAZARDS[{hazard!r}] must carry an actual "
            f"reason, not a bare placeholder."
        )
