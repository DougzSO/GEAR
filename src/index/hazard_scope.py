"""
Per-bucket applicable-hazard sets -- ``H_b`` (``docs/rework/
GEAR_v3_methodology_nature_format.md`` Section 3; ``docs/rework/
GEAR_v3_work_plan.md`` Phase 3.1).

Single source of truth, per the standing modularity rule: Phase 3.2
(``RiskBand_{i,h}`` threshold classification) and Phase 4 (PSAE aggregation,
Equation 2) both read ``APPLICABLE_HAZARDS`` from here rather than each
re-deriving or hardcoding its own copy of which hazard terms apply to which
bucket. This module does not compute ``Risk_{i,h}`` itself and does not
change ``src/index/risk_calculator.py``'s Equation 1 -- it only encodes which
hazard terms are *consumed* per bucket.

--------------------------------------------------------------------------
Result, not a fresh judgment call
--------------------------------------------------------------------------
Every entry below reflects an already-closed decision, not a choice made in
this module: Section 3's H_b table (mechanistic-relevance rationale) plus
Phase 2.5's empirical correlation-gate outcome (``src/index/
correlation_gate.py``, ``docs/DECISIONS.md`` "GEAR v3 Phase 2.5: correlation
gate implemented and run"), plus author-confirmed decisions this module
closes out (below).

* **Hydro** -- ``ws`` (Water Stress), ``spei`` (Drought), ``precip``
  (Extreme Precipitation, gated and passed), plus ``sv``/``iv`` (water
  seasonal/interannual variability). ``sv``/``iv`` were carried since Phase 1
  as independent, gate-confirmed-non-redundant candidates whose H_b
  membership was explicitly left open (``risk_calculator.py`` module
  docstring; ``docs/DECISIONS.md`` "GEAR v3 Phase 2.5: correlation gate
  implemented and run", "sv/iv... still-open decision"). Author-confirmed
  (2026-09-12): both ``sv`` and ``iv`` are added to Hydro's H_b -- Hydro
  inflow/hydraulic-head is sensitive to both seasonal and multi-year water
  variability, not only mean Water Stress; both passed the gate against
  Water Stress and against each other, and Criterion 3's tie-breaker
  (Section 5) never fired on real data, so there was no gate-forced reason
  to keep only one.
* **Thermal** -- ``ws``, ``heat`` (Extreme Heat), ``precip`` (gated and
  passed). ``sv``/``iv`` are explicitly NOT extended to Thermal
  (author-confirmed, 2026-09-12), even though both were gated as candidates
  in Thermal too (``correlation_gate.WATER_BUCKETS``) and passed there as
  well: Phase 0 confirmed no cooling-technology field (once-through/
  recirculating/dry/hybrid) exists in the ingested GEM data, so there is no
  per-plant basis to justify a water-*variability* sensitivity mechanism
  for Thermal specifically -- extending sv/iv there would assume a
  mechanism the available data cannot support, contradicting the
  already-closed Thermal-homogeneity decision (``docs/LIMITATIONS.md``,
  "2026-09-11 -- GEM cooling-technology field absent: Thermal bucket
  treated as homogeneous"). Drought/SPEI is excluded from Thermal by the
  original Section 3 mechanistic rationale (the drought mechanism is
  already captured via Water Stress for a thermal plant; SPEI's
  hydraulic-head mechanism is Hydro-specific).
* **Wind** -- ``wind`` (Extreme Wind, IEC turbine cut-out mechanism) only.
  Not a correlation-gate candidate (Section 3.1: a dedicated per-bucket
  hazard by original design).
* **Solar** -- ``heat`` (PV efficiency-loss mechanism), ``precip``
  (substation-flooding mechanism, gated and passed), ``wind`` (tracker
  structural-uplift mechanism, ERA5 gust percentile, Tier 3 final per
  Section 3.1). No water-dependency mechanism (Section 3), so neither
  ``ws`` nor ``spei``/``sv``/``iv``.

See ``docs/DECISIONS.md``, "GEAR v3 Phase 3.1: hazard_scope.py reconciliation
after parallel-session conflict" for the Hydro-vs-Thermal sv/iv distinction
above being restated after a since-corrected conflicting edit.

--------------------------------------------------------------------------
Wildfire and SLR -- absent by design, not an oversight
--------------------------------------------------------------------------
Neither hazard has a term in ``HAZARD_LABELS`` below or appears in any
bucket's applicable set. This is a closed scope decision, not a gap:

* Wildfire (FWI/EFFIS) is deferred for a genuine data-availability gap
  (Methods Section 10.1; ``docs/LIMITATIONS.md``, "2026-09-11 -- Wildfire
  (FWI/EFFIS) deferred, not implemented"). If reinstated, Section 10.1
  already names its applicable buckets (Thermal, Solar) -- that
  reinstatement is out of scope for this module.
* Sea-level rise is excluded from the hazard set entirely (Methods Section
  10; ``docs/LIMITATIONS.md``, "2026-09-03 -- Sea-level rise (SLR) excluded
  from the hazard set").

Standalone: none -- this module has no CLI. It is imported by downstream
Phase 3.2/4 modules and by ``tests/test_hazard_scope.py``.
"""

from __future__ import annotations

from src.index import risk_calculator as rc

# --------------------------------------------------------------------------
# Hazard term labels for the two terms risk_calculator.py does not yet name
# (precip/wind are Phase 2.1/2.3 processors, not yet wired into
# risk_calculator.HAZARD_TERMS -- Phase 3.2/4 territory, not this module's).
# Combined with rc.HAZARD_LABELS at the bottom of this section for one
# lookup covering every term used anywhere in APPLICABLE_HAZARDS.
# --------------------------------------------------------------------------
_EXTRA_HAZARD_LABELS: dict[str, str] = {
    "precip": "Extreme Precipitation",
    "wind": "Extreme Wind",
}

HAZARD_LABELS: dict[str, str] = {**rc.HAZARD_LABELS, **_EXTRA_HAZARD_LABELS}

# --------------------------------------------------------------------------
# H_b -- the per-bucket applicable-hazard set (Methods Section 3 table).
# Keys are exactly risk_calculator.BUCKETS; see module docstring above for
# the mechanistic rationale and gate-outcome citation behind every entry.
# --------------------------------------------------------------------------
APPLICABLE_HAZARDS: dict[str, tuple[str, ...]] = {
    "hydro": ("ws", "spei", "precip", "sv", "iv"),
    "thermal": ("ws", "heat", "precip"),
    "wind": ("wind",),
    "solar": ("heat", "precip", "wind"),
}

# Hazards explicitly out of scope everywhere -- named here so a reader (or a
# test) does not have to infer their absence from a diff against Section 2's
# checklist. See module docstring, "Wildfire and SLR" above.
DEFERRED_OR_EXCLUDED_HAZARDS: tuple[str, ...] = ("wildfire", "slr")

# Extreme Wind's closed per-bucket scope (Section 3.1): the turbine
# cut-out mechanism (Wind) and the tracker structural-uplift mechanism
# (Solar) are its only two consumers -- never a water-bucket hazard.
WIND_APPLICABLE_BUCKETS: frozenset[str] = frozenset({"wind", "solar"})

# --------------------------------------------------------------------------
# H_b members with no Risk_i,h entry yet -- an explicit, named exception set,
# not a silent gap. This is the standing guard against the precip/wind
# integration gap recurring for a future hazard: every hazard named in
# APPLICABLE_HAZARDS must be either a key in risk_calculator.HAZARD_TERMS
# (computable, real Risk_i,h) OR listed here with a reason -- never simply
# absent from both with no record of why (tests/test_hazard_scope.py enforces
# this exhaustively). Removing an entry here requires it to have gained a
# real HAZARD_TERMS entry in the same change, never the other way around.
# --------------------------------------------------------------------------
PENDING_RISK_I_H_HAZARDS: dict[str, str] = {
    "wind": (
        "RiskBand classification exists (src/index/risk_bands.py, Phase 3.2) "
        "but Risk_i,h does not: ERA5 gust acquisition is incomplete (Brazil "
        "30/30 years cached, Portugal 12/30, India 2/30; no country has a "
        "processed extreme_wind_gust_raw_*.tif). See docs/DECISIONS.md, "
        "'GEAR v3 Risk_i,h integration gap: precip wired in, wind still "
        "blocked on ERA5 acquisition'."
    ),
}


def applicable_hazards(bucket: str) -> tuple[str, ...]:
    """``H_b`` for one bucket. Raises ``KeyError`` on an unknown bucket --
    no silent empty-set fallback for a typo'd or retired bucket name."""
    return APPLICABLE_HAZARDS[bucket]


def _validate() -> None:
    """Fail-high structural guard, run at import time (project convention,
    ``CLAUDE.md`` Section 8: fail loud rather than silently produce a
    malformed H_b table). Not a substitute for ``tests/test_hazard_scope.py``
    -- this only guards against an accidental future edit breaking the
    invariants those tests pin down explicitly."""
    if set(APPLICABLE_HAZARDS) != set(rc.BUCKETS):
        raise AssertionError(
            f"APPLICABLE_HAZARDS keys {sorted(APPLICABLE_HAZARDS)} must "
            f"exactly match risk_calculator.BUCKETS {sorted(rc.BUCKETS)}"
        )
    for bucket, hazards in APPLICABLE_HAZARDS.items():
        if not hazards:
            raise AssertionError(f"bucket {bucket!r} has an empty H_b")
        for h in hazards:
            if h in DEFERRED_OR_EXCLUDED_HAZARDS:
                raise AssertionError(
                    f"{h!r} is deferred/excluded and must not appear in "
                    f"bucket {bucket!r}'s H_b"
                )
    for bucket in rc.BUCKETS:
        if bucket not in WIND_APPLICABLE_BUCKETS and "wind" in APPLICABLE_HAZARDS[bucket]:
            raise AssertionError(
                f"'wind' is only applicable to {sorted(WIND_APPLICABLE_BUCKETS)}, "
                f"found in bucket {bucket!r}"
            )


_validate()
