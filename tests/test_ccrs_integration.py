"""Integration tests across T1 (ccrs_calculator) + T2 (age_factor) + T3
(event_multiplier), and a regression check against the pre-existing
``analysis/ccrs_final_summary.py`` diagnostic.

--------------------------------------------------------------------------
Correction to the task's premise (investigated before writing any test)
--------------------------------------------------------------------------
The task frames the ~39.2% India figure in ``analysis/ccrs_final_summary.py``
as "the pure Hazard term (T1 alone)". **That is not what the figure is.**
Reading the script (``main()``, the ``hi_hi`` computation in section 4):

    hi_hi = sub.loc[sub.wband.isin(["High", "Extremely-High"])
                    & sub.hband.isin(["HIGH", "EXTREME"]), "capacity_mw"].sum()

``wband``/``hband`` are ``WaterRiskBand``/``HeatRiskBand`` -- discrete bands
cut directly from the RAW ``ws``/``sv``/``iv`` and ``heat_days`` values
(``analysis/water_risk_band_classification.py`` + this script's
``heat_band_frame``), using the same weight derivation and the same absolute
cuts that later became ``src/index/risk_bands.py`` (T4). This is a **T4-level
WaterRiskBand x HeatRiskBand compound capacity share**, not T1's
bucket-weighted numeric ``Hazard_i,s`` score at all -- T1's Hazard formula
(``w_water*water_sub + w_heat*Tlog(heat)``) never appears anywhere in this
calculation. It is also, by construction, independent of ``age_factor`` and
``EventMultiplier`` (T2/T3): bands are never redefined by those multipliers
-- CCRS deliberately keeps WaterRiskBand/HeatRiskBand categorical and
separate from the continuous numeric score (spec Section 8.3, ARCHITECTURE.md
Section 5.2). So there is no way to "extend" the 39.2% figure to include
age_factor/EventMultiplier the way the task's part (a) implies for a
band-style metric -- that structural fact is itself a finding, not a gap in
this test file.

Given that, the tests below do two separate, honestly-labelled things:

(a) **New reference for the actual T1 x T2 x T3 product** (the numeric
    ``CCRS_i,s``, not a band share): the V6-computable-base
    capacity-weighted mean ``CCRS_i,s`` per country, per GCM, pooled over the
    3 water scenarios (``_capacity_weighted_ccrs_means``), frozen as
    ``NEW_REFERENCE_CCRS_MEAN`` with a tight regression lock (same convention
    as ``ccrs_calculator.FROZEN_BOUNDS`` / the ``event_multiplier`` fixture --
    recompute from data, compare, fail on drift, no silent update).
(b) **The actual same-metric comparison against the old 39.2%**: the
    WaterRiskBand x HeatRiskBand compound capacity share for India under
    GFDL-ESM4, recomputed from the current, committed ``risk_bands.py`` (T4)
    production code, at ±0.5 pp -- this is what the task's part (b) asks for,
    correctly targeted at the metric the old figure actually is.

--------------------------------------------------------------------------
Cross-join bug: did the old 39.2% predate the fix?
--------------------------------------------------------------------------
No -- and not because of timing, but because of how it was computed.
``analysis/ccrs_band_classification.extract_with_capacity`` (which
``water_risk_band_classification.water_band_frame`` calls) builds its output
by reading ``gem_validated_plants_{country}.csv`` **once** and sampling
rasters directly against each row's own ``lon``/``lat``, in that row's
original position -- there is no ``.merge``/``.join`` call anywhere in it
(confirmed by source inspection,
``test_old_diagnostic_extraction_never_merges_on_an_ambiguous_key``). T1's
cross-join bug was specifically a side-by-side **merge** of two
separately-computed per-GCM frames on the ambiguous key
``(country, plant_name, capacity_mw, commissioning_year)``
(``ccrs_calculator.compute_hazard_by_gcm``, fixed in commit f6e50bb). The old
diagnostic never performs that merge (or any merge), so it is structurally
unaffected by that bug regardless of when it ran.

For completeness: the raster and CSV files it read (checked by file mtime)
were all written *before* ``analysis/ccrs_final_summary.py`` last ran
(2026-09-03 evening) and have not been touched since, so it also ran on the
same data snapshot T1-T5 use today -- no data drift to account for either.
Both facts (no merge, no data drift) are why the ~0.03 pp residual difference
found in part (b) is attributable to a genuine, minor, and separately
identified methodological difference (below), not the cross-join bug and not
stale data.

--------------------------------------------------------------------------
Where the small residual difference comes from (term-by-term)
--------------------------------------------------------------------------
The old diagnostic computes HeatRiskBand percentile cuts (p25/p75/p95) over
the **water-matched** pool only (rows where ws/sv/iv/heat are all finite --
``water_band_frame``'s ``m = df[df["matched"]]``). ``risk_bands.py`` (T4)
computes them over **every row with a finite heat value**, regardless of
whether the water terms are finite (``ccrs.sample_terms`` gives ~54 more
India rows this way -- outside any Aqueduct basin but inside a heat raster
cell). This shifts the p75 cut by 0.17 days/yr (31.1667 -> 31.0) and the
compound share by ~0.03-0.11 pp depending on the capacity denominator
convention used -- see the numbers in
``test_hazard_band_compound_share_for_india_vs_old_diagnostic_value``. This
is well inside the ±0.5 pp tolerance; it is reported here as the identified
cause, not dismissed.
"""

import inspect

import numpy as np
import pandas as pd
import pytest

from analysis import ccrs_band_classification
from analysis import ccrs_final_summary
from analysis import water_risk_band_classification as water_bands
from src.downloaders import emdat_downloader
from src.index import age_factor
from src.index import ccrs_calculator as ccrs
from src.index import ccrs_report as cr
from src.index import event_multiplier
from src.index import risk_bands
from src.index.ccrs_calculator import PLANT_UID

# --------------------------------------------------------------------------
# (a) new T1 x T2 x T3 reference: capacity-weighted mean CCRS_i,s per country
# --------------------------------------------------------------------------
REFERENCE_SNAPSHOT_DATE = "2026-09-04"  # re-frozen post-SPEI -- see the 2026-09-05 update note below

# V6-computable-base capacity-weighted mean CCRS_i,s per country, per GCM,
# pooled over the 3 water_scenarios. Frozen from the data snapshot above --
# see the module docstring. Update only after deliberate manual review, with
# the number diff recorded, same discipline as ccrs_calculator.FROZEN_BOUNDS.
#
# --------------------------------------------------------------------------
# 2026-09-05 update -- regenerated after the SPEI/drought Hazard term
# --------------------------------------------------------------------------
# The ORIGINAL snapshot below this comment (first frozen under the
# "2026-09-04" date, T6) was locked from ``cr.compute_ccrs()`` BEFORE commit
# ``fb6a775`` ("Integrate SPEI/drought term into Hazard as a new additive
# term", spec item F) landed. That commit changed the Hazard formula itself
# (``Hazard_i,s`` gained a third additive term, ``w_drought[bucket] *
# Tlog(spei_freq)``) -- the frozen mean was never a bug, it was simply
# computed against a two-term Hazard that no longer exists in the codebase.
# ``test_new_reference_ccrs_mean_matches_frozen_regression_snapshot`` caught
# exactly the drift it is designed to catch: every value roughly doubled
# (e.g. Brazil/GFDL-ESM4: 0.1276 -> 0.2821), which is the expected, correct
# effect of adding a real third hazard term to an unrenormalised weighted
# sum -- not a regression. Manually reviewed and confirmed against a live
# recompute of ``cr.compute_ccrs()`` (same ``_capacity_weighted_ccrs_means``
# methodology, unchanged) before updating the constant below:
#
#     old (pre-SPEI, frozen 2026-09-04)      new (post-SPEI, frozen 2026-09-05)
#     gfdl_esm4/Brazil:   0.1276146046   ->  0.2821133919
#     gfdl_esm4/Portugal: 0.1597086666   ->  0.2835049447
#     gfdl_esm4/India:    0.7373050560   ->  0.8036207700
#     miroc6/Brazil:      0.3358241992   ->  0.5493571696
#     miroc6/Portugal:    0.3467460666   ->  0.4348641055
#     miroc6/India:       0.8724441059   ->  0.9632593619
#
# Kept here rather than deleted so the history of *why* the constant moved
# stays traceable from the test file itself, not only from git blame.
NEW_REFERENCE_CCRS_MEAN = {
    "gfdl_esm4": {"Brazil": 0.2821133919, "Portugal": 0.2835049447, "India": 0.8036207700},
    "miroc6": {"Brazil": 0.5493571696, "Portugal": 0.4348641055, "India": 0.9632593619},
}

# (b) the actual same-metric comparison target: the published headline figure
# in analysis/ccrs_final_summary.md section 4 ("India/gfdl_esm4: **39.2%**").
OLD_INDIA_COMPOUND_SHARE_PCT = 39.2
COMPOUND_SHARE_TOLERANCE_PP = 0.5


def _capacity_weighted_ccrs_means(ccrs_df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """V6-computable-base capacity-weighted mean CCRS_i,s per country, per
    GCM column present in ccrs_df, pooled over every water_scenario row."""
    base = ccrs.computable_base(ccrs_df)
    out: dict[str, dict[str, float]] = {}
    for hazard_col, ccrs_col in cr.CCRS_COLUMNS.items():
        if ccrs_col not in base.columns:
            continue
        gcm = hazard_col.removeprefix("hazard_")
        out[gcm] = {}
        for country in ccrs.COUNTRIES:
            sub = base.loc[base["country"] == country, [ccrs_col, "capacity_mw"]].dropna()
            out[gcm][country] = float(np.average(sub[ccrs_col], weights=sub["capacity_mw"]))
    return out


def _india_compound_band_share_gfdl(denominator: str = "matched") -> float:
    """% of India's capacity where WaterRiskBand in {High, Extremely-High}
    AND HeatRiskBand in {HIGH, EXTREME}, GFDL-ESM4, 3 scenarios pooled --
    computed from the current, committed src/index/risk_bands.py (T4).

    ``denominator``: "matched" reproduces the old diagnostic's convention
    (capacity summed only over rows with both bands present); "all" uses
    every India row's capacity_mw regardless of band membership.
    """
    bt = risk_bands.compute_bands("gfdl_esm4")
    sub = bt.frame[bt.frame["country"] == "India"]
    matched = sub.dropna(subset=["water_risk_band", "heat_risk_band"])
    hi_hi_cap = matched.loc[
        matched["water_risk_band"].isin(["High", "Extremely-High"])
        & matched["heat_risk_band"].isin(["HIGH", "EXTREME"]),
        "capacity_mw",
    ].sum()
    if denominator == "matched":
        denom = matched["capacity_mw"].sum()
    elif denominator == "all":
        denom = sub["capacity_mw"].sum()
    else:
        raise ValueError(f"denominator must be 'matched' or 'all', got {denominator!r}")
    return 100.0 * hi_hi_cap / denom


# --------------------------------------------------------------------------
# real-data guard
# --------------------------------------------------------------------------
def _real_data_present() -> bool:
    return (
        cr.HAZARD_CSV.exists()
        and all((ccrs.ASSETS_PROCESSED / f"gem_validated_plants_{c}.csv").exists() for c in ccrs.COUNTRIES)
        and all(emdat_downloader.country_csv_path(c).exists() for c in ("Brazil", "Portugal", "India"))
    )


_SKIP_REASON = "validated-plant CSVs, ccrs_hazard.csv or emdat_*.csv absent"


# --------------------------------------------------------------------------
# 1. regression lock on the new T1 x T2 x T3 reference number
# --------------------------------------------------------------------------
@pytest.mark.skipif(not _real_data_present(), reason=_SKIP_REASON)
def test_new_reference_ccrs_mean_matches_frozen_regression_snapshot():
    ccrs_df = cr.compute_ccrs()
    live = _capacity_weighted_ccrs_means(ccrs_df)

    mismatches = []
    for gcm, countries in NEW_REFERENCE_CCRS_MEAN.items():
        for country, frozen in countries.items():
            got = live[gcm][country]
            if abs(got - frozen) > 1e-6:
                mismatches.append(f"{gcm}/{country}: frozen={frozen:.10f} live={got:.10f}")
    assert not mismatches, (
        "NEW_REFERENCE_CCRS_MEAN (snapshot " + REFERENCE_SNAPSHOT_DATE + ") diverged from "
        "the recomputed capacity-weighted mean CCRS_i,s -- manual review required before "
        "updating the frozen constant:\n" + "\n".join(mismatches)
    )


@pytest.mark.skipif(not _real_data_present(), reason=_SKIP_REASON)
def test_new_reference_ccrs_mean_is_reported_with_its_snapshot_date():
    # the frozen reference is meaningless without a dated snapshot -- guard
    # against someone updating the numbers without updating the date.
    assert REFERENCE_SNAPSHOT_DATE
    import datetime
    datetime.date.fromisoformat(REFERENCE_SNAPSHOT_DATE)   # raises if malformed


# --------------------------------------------------------------------------
# 2. Hazard/band comparison against the old India figure, +/-0.5pp
# --------------------------------------------------------------------------
@pytest.mark.skipif(not _real_data_present(), reason=_SKIP_REASON)
def test_hazard_band_compound_share_for_india_vs_old_diagnostic_value():
    new_matched = _india_compound_band_share_gfdl("matched")
    new_all = _india_compound_band_share_gfdl("all")

    diff_matched = abs(new_matched - OLD_INDIA_COMPOUND_SHARE_PCT)
    diff_all = abs(new_all - OLD_INDIA_COMPOUND_SHARE_PCT)

    # Report both conventions regardless of outcome (assertion message is
    # the "report exactly where it diverges" artifact if this ever fails).
    report = (
        f"old (analysis/ccrs_final_summary.md, GFDL-ESM4) = {OLD_INDIA_COMPOUND_SHARE_PCT:.4f}%\n"
        f"new, matched-capacity denominator (old-style)   = {new_matched:.4f}%  (diff {diff_matched:.4f} pp)\n"
        f"new, all-capacity denominator                    = {new_all:.4f}%  (diff {diff_all:.4f} pp)\n"
        f"tolerance = +/-{COMPOUND_SHARE_TOLERANCE_PP} pp"
    )
    assert diff_matched <= COMPOUND_SHARE_TOLERANCE_PP, (
        "OUT OF TOLERANCE -- do not adjust the reference to force a match; "
        "investigate term by term (bounds, per-bucket weights, wd exclusion, "
        "cross-join) before accepting anything.\n" + report
    )
    # within tolerance: the old (pre-plant_uid) and new (post-cross-join-fix)
    # values are consistent within the declared margin -- see module docstring
    # for why the residual ~0.03-0.11 pp is a heat-percentile-pool difference,
    # not the cross-join bug (the old diagnostic never merges on the
    # ambiguous key at all -- see the next test).
    print(report)


@pytest.mark.skipif(not _real_data_present(), reason=_SKIP_REASON)
def test_old_diagnostic_value_is_reproducible_from_the_unchanged_source_data():
    """Confirms the 39.2% figure is faithfully reproducible from the data on
    disk today (no drift) -- re-running the exact old methodology gives
    39.2214%, matching the published rounded 39.2%."""
    weights = water_bands.derive_weights()
    cuts = water_bands.band_cuts(weights)
    m = water_bands.water_band_frame("gfdl_esm4", weights, cuts)
    m, _ = ccrs_final_summary.heat_band_frame("gfdl_esm4", m)

    sub = m[m["country"] == "India"]
    denom = sub["capacity_mw"].fillna(0).sum()
    hi_hi = sub.loc[
        sub["wband"].isin(["High", "Extremely-High"]) & sub["hband"].isin(["HIGH", "EXTREME"]),
        "capacity_mw",
    ].fillna(0).sum()
    reproduced = 100.0 * hi_hi / denom

    assert reproduced == pytest.approx(39.2214, abs=0.001)
    assert round(reproduced, 1) == pytest.approx(OLD_INDIA_COMPOUND_SHARE_PCT, abs=1e-9)


# --------------------------------------------------------------------------
# cross-join provenance of the old figure -- structural, not timing-based
# --------------------------------------------------------------------------
def test_old_diagnostic_extraction_never_merges_on_an_ambiguous_key():
    """analysis/ccrs_band_classification.extract_with_capacity (the sampling
    function under the old 39.2% figure, via water_risk_band_classification)
    builds its frame by reading each country's CSV once and sampling rasters
    positionally against that same read -- no .merge()/.join() call exists in
    it, so it cannot suffer the ambiguous-(country, plant_name, capacity_mw,
    commissioning_year)-key cross-join that T1's compute_hazard_by_gcm had
    before commit f6e50bb. This is a structural fact, independent of when the
    script last ran."""
    src = inspect.getsource(ccrs_band_classification.extract_with_capacity)
    assert ".merge(" not in src
    assert ".join(" not in src


# --------------------------------------------------------------------------
# 3. end-to-end: no plant_uid duplicated or dropped across T1 -> T2 -> T3
# --------------------------------------------------------------------------
@pytest.mark.skipif(not _real_data_present(), reason=_SKIP_REASON)
def test_no_duplicate_or_dropped_plant_uid_across_the_t1_t2_t3_chain():
    hz = pd.read_csv(cr.HAZARD_CSV)                              # T1
    af = age_factor.compute_age_factors()                        # T2
    em = event_multiplier.compute_event_multipliers()             # T3
    ccrs_df = cr.compute_ccrs(age_factors=af, event_multipliers=em)  # T1 x T2 x T3

    expected_plants = age_factor.load_plant_attributes()[PLANT_UID].nunique()

    # T1: one row per (plant_uid, water_scenario), no duplicate plant_uid set
    assert hz[PLANT_UID].nunique() == expected_plants
    assert not hz.duplicated([PLANT_UID, "water_scenario"]).any()

    # T2: one age_factor row per plant_uid, exactly the same set as T1
    assert af[PLANT_UID].nunique() == expected_plants
    assert not af[PLANT_UID].duplicated().any()
    assert set(af[PLANT_UID]) == set(hz[PLANT_UID])

    # T3: one row per country, and every country in T1's hazard table has one
    assert not em["country"].duplicated().any()
    assert set(hz["country"]) <= set(em["country"])

    # T1 x T2 x T3: row count preserved exactly, no plant_uid gained or lost
    assert len(ccrs_df) == len(hz)
    assert not ccrs_df.duplicated([PLANT_UID, "water_scenario"]).any()
    assert ccrs_df[PLANT_UID].nunique() == expected_plants
    assert set(ccrs_df[PLANT_UID]) == set(hz[PLANT_UID])
