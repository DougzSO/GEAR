"""Tests for src/index/psae -- GEAR v3 Equation 2, PSAE_i.

Covers: Equation 2's arithmetic (count of RiskBand_i,h >= High over H_b),
complete-case handling for missing/NaN RiskBand_i,h (docs/DECISIONS.md,
"Phase 4 (PSAE) input mapping; missing/NaN RiskBand handling in the PSAE
denominator: CLOSED, complete-case"), the four H_b sizes (hydro=5,
thermal=3, wind=1, solar=3), Section 6's classification cut points
(1.0/0.5/0.0), and the cross-bucket comparability guard (work plan Phase
4.2).

Pure-function tests against a hand-built fake RiskBandTable -- no raster or
CSV I/O, no dependency on real processed data.
"""

import numpy as np
import pandas as pd
import pytest

from src.index import hazard_scope as hs
from src.index import psae
from src.index import risk_bands as rb


def _fake_risk_band_table(rows: list[dict], model: str = "gfdl_esm4") -> rb.RiskBandTable:
    """A minimal RiskBandTable.frame -- only the columns compute_psae
    actually reads. Each row dict needs: plant_uid, country, plant_name,
    bucket, water_scenario, heat_scenario, hazard_term, risk_band."""
    frame = pd.DataFrame(rows)
    frame["model"] = model
    return rb.RiskBandTable(frame=frame, percentile_cuts={}, model=model)


def _rows_for_bucket(bucket: str, plant_uid: str, bands: dict, water_scenario: str = "opt") -> list[dict]:
    """One row per hazard in bucket's H_b, band taken from `bands[hazard]`
    (None if the hazard key is absent -- simulates a missing RiskBand)."""
    h_b = hs.APPLICABLE_HAZARDS[bucket]
    return [
        {
            "plant_uid": plant_uid, "country": "Testland", "plant_name": "p",
            "bucket": bucket, "water_scenario": water_scenario,
            "heat_scenario": "ssp126", "hazard_term": h,
            "risk_band": bands.get(h),
        }
        for h in h_b
    ]


# --------------------------------------------------------------------------
# H_b sizes -- the four bucket cases named in the task
# --------------------------------------------------------------------------
def test_h_b_sizes_match_the_four_named_cases():
    assert len(hs.APPLICABLE_HAZARDS["hydro"]) == 5
    assert len(hs.APPLICABLE_HAZARDS["thermal"]) == 3
    assert len(hs.APPLICABLE_HAZARDS["wind"]) == 1
    assert len(hs.APPLICABLE_HAZARDS["solar"]) == 3


@pytest.mark.parametrize("bucket", ["hydro", "thermal", "wind", "solar"])
def test_compute_psae_all_extreme_saturates_to_1(bucket):
    """Every hazard in H_b classified Extreme -> PSAE = 1.0 -> EXTREME,
    for all four bucket sizes."""
    h_b = hs.APPLICABLE_HAZARDS[bucket]
    rows = _rows_for_bucket(bucket, "P-1", {h: "Extreme" for h in h_b})
    result = psae.compute_psae(_fake_risk_band_table(rows))
    row = result.frame.iloc[0]
    assert row["h_b_size"] == len(h_b)
    assert row["n_high_or_above"] == len(h_b)
    assert row["psae"] == pytest.approx(1.0)
    assert row["psae_label"] == "EXTREME"
    assert bool(row["psae_complete"]) is True
    assert row["missing_hazards"] == ()


@pytest.mark.parametrize("bucket", ["hydro", "thermal", "wind", "solar"])
def test_compute_psae_all_low_is_0(bucket):
    """Every hazard in H_b classified Low -> PSAE = 0.0 -> LOW, for all
    four bucket sizes."""
    h_b = hs.APPLICABLE_HAZARDS[bucket]
    rows = _rows_for_bucket(bucket, "P-1", {h: "Low" for h in h_b})
    result = psae.compute_psae(_fake_risk_band_table(rows))
    row = result.frame.iloc[0]
    assert row["n_high_or_above"] == 0
    assert row["psae"] == pytest.approx(0.0)
    assert row["psae_label"] == "LOW"
    assert bool(row["psae_complete"]) is True


def test_compute_psae_complete_case_thermal_two_of_three_high():
    """Thermal, H_b=3 (ws, heat, precip): 2 High/Extreme, 1 Medium ->
    psae = 2/3, label HIGH (0.5 <= 2/3 < 1.0)."""
    rows = _rows_for_bucket("thermal", "P-1", {"ws": "High", "heat": "Extreme", "precip": "Medium"})
    result = psae.compute_psae(_fake_risk_band_table(rows))
    row = result.frame.iloc[0]
    assert row["h_b_size"] == 3
    assert row["n_high_or_above"] == 2
    assert row["psae"] == pytest.approx(2 / 3)
    assert row["psae_label"] == "HIGH"
    assert bool(row["psae_complete"]) is True
    assert row["missing_hazards"] == ()


# --------------------------------------------------------------------------
# Complete-case: missing/NaN RiskBand_i,h
# --------------------------------------------------------------------------
def test_compute_psae_missing_hazard_triggers_complete_case():
    """One of Thermal's 3 hazards has no RiskBand (None) -> psae is NaN,
    psae_complete is False, missing_hazards names exactly that hazard --
    never computed over a reduced H_b, never silently dropped as a row."""
    rows = _rows_for_bucket("thermal", "P-1", {"ws": "High", "heat": "Extreme"})  # precip missing
    result = psae.compute_psae(_fake_risk_band_table(rows))
    assert len(result.frame) == 1  # row is NOT dropped
    row = result.frame.iloc[0]
    assert row["h_b_size"] == 3          # denominator NOT shrunk to 2
    assert np.isnan(row["n_high_or_above"])
    assert np.isnan(row["psae"])
    assert row["psae_label"] is None
    assert bool(row["psae_complete"]) is False
    assert row["missing_hazards"] == ("precip",)


def test_nan_is_never_silently_treated_as_not_high():
    """Dedicated regression guard against rejected option (c)
    (treat-as-not-High): if the missing hazard were silently counted as
    'not High', a plant with 2 of 3 Thermal hazards Extreme and 1 missing
    would get psae = 2/3 (HIGH), identical to the fully-observed 2-of-3
    case. This test proves that does NOT happen -- the missing-hazard
    plant must come back NaN/undefined, not a finite 2/3."""
    complete_rows = _rows_for_bucket(
        "thermal", "P-complete", {"ws": "Extreme", "heat": "Extreme", "precip": "Low"},
    )
    incomplete_rows = _rows_for_bucket(
        "thermal", "P-incomplete", {"ws": "Extreme", "heat": "Extreme"},  # precip missing
    )
    result = psae.compute_psae(_fake_risk_band_table(complete_rows + incomplete_rows))
    by_plant = result.frame.set_index("plant_uid")

    complete_row = by_plant.loc["P-complete"]
    assert complete_row["psae"] == pytest.approx(2 / 3)
    assert complete_row["psae_label"] == "HIGH"

    incomplete_row = by_plant.loc["P-incomplete"]
    assert np.isnan(incomplete_row["psae"]), (
        "missing hazard was silently treated as 'not High' -- psae came back "
        f"finite ({incomplete_row['psae']!r}) instead of NaN"
    )
    assert incomplete_row["psae"] != pytest.approx(2 / 3), (
        "incomplete plant's psae accidentally matches the complete plant's "
        "2/3 -- the missing hazard was not excluded from the denominator "
        "the way option (c)/complete-case-violation would produce"
    )
    assert bool(incomplete_row["psae_complete"]) is False
    assert incomplete_row["psae_label"] is None


def test_missing_hazard_row_is_not_dropped_from_output():
    """A plant with a missing hazard must still appear in the output table
    -- never silently omitted with no trace."""
    complete = _rows_for_bucket("wind", "P-ok", {"wind": "Extreme"})
    incomplete = _rows_for_bucket("wind", "P-missing", {})  # wind band missing
    result = psae.compute_psae(_fake_risk_band_table(complete + incomplete))
    assert set(result.frame["plant_uid"]) == {"P-ok", "P-missing"}
    missing_row = result.frame[result.frame["plant_uid"] == "P-missing"].iloc[0]
    assert bool(missing_row["psae_complete"]) is False
    assert missing_row["missing_hazards"] == ("wind",)


# --------------------------------------------------------------------------
# Wind's compressed scheme -- same cut function, restricted reachable range
# --------------------------------------------------------------------------
def test_wind_bucket_only_ever_produces_low_or_extreme():
    """|H_b|=1 for Wind -- psae in {0.0, 1.0} only, so the (unmodified,
    unbranched) Section 6 cut function can only ever emit LOW or EXTREME
    for this bucket, never MEDIUM/HIGH."""
    extreme_rows = _rows_for_bucket("wind", "P-extreme", {"wind": "Extreme"})
    low_rows = _rows_for_bucket("wind", "P-low", {"wind": "Low"})
    result = psae.compute_psae(_fake_risk_band_table(extreme_rows + low_rows))
    labels = set(result.frame["psae_label"])
    assert labels == {"EXTREME", "LOW"}
    assert "MEDIUM" not in labels and "HIGH" not in labels


# --------------------------------------------------------------------------
# Section 6 cut-point parity -- classify_psae_fraction
# --------------------------------------------------------------------------
@pytest.mark.parametrize("fraction,expected_label", [
    (1.0, "EXTREME"),
    (0.999, "HIGH"),
    (0.5, "HIGH"),
    (0.4999, "MEDIUM"),
    (2 / 3, "HIGH"),
    (1 / 3, "MEDIUM"),
    (0.0001, "MEDIUM"),
    (0.0, "LOW"),
])
def test_classify_psae_fraction_matches_section6_cuts(fraction, expected_label):
    assert psae.classify_psae_fraction(fraction) == expected_label


def test_classify_psae_fraction_nan_and_none_are_unclassified():
    assert psae.classify_psae_fraction(None) is None
    assert psae.classify_psae_fraction(float("nan")) is None


# --------------------------------------------------------------------------
# Comparability guard -- work plan Phase 4.2
# --------------------------------------------------------------------------
def test_assert_single_bucket_raises_on_mixed_buckets():
    frame = pd.DataFrame({"bucket": ["thermal", "wind"], "psae": [0.5, 1.0]})
    with pytest.raises(psae.CrossBucketPSAEComparisonError):
        psae.assert_single_bucket(frame)


def test_assert_single_bucket_passes_for_one_bucket():
    frame = pd.DataFrame({"bucket": ["thermal", "thermal"], "psae": [0.5, 1.0]})
    psae.assert_single_bucket(frame)  # must not raise


def test_rank_within_bucket_sorts_descending_by_default():
    rows = (
        _rows_for_bucket("wind", "P-low", {"wind": "Low"})
        + _rows_for_bucket("wind", "P-high", {"wind": "Extreme"})
    )
    result = psae.compute_psae(_fake_risk_band_table(rows))
    ranked = psae.rank_within_bucket(result, "wind")
    assert list(ranked["plant_uid"]) == ["P-high", "P-low"]


def test_compute_psae_never_produces_duplicate_plant_scenario_rows():
    rows = _rows_for_bucket("thermal", "P-1", {"ws": "Low", "heat": "Low", "precip": "Low"})
    result = psae.compute_psae(_fake_risk_band_table(rows))
    assert not result.frame.duplicated(["plant_uid", "water_scenario"]).any()
