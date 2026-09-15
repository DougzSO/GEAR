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

Also covers (bottom of file): a real-data regression test for the
2026-09-14 vectorised performance rewrite of ``compute_psae`` (``docs/
DECISIONS.md``, "GEAR v3 psae.py performance fix") against a small,
independent, deliberately slow per-group reference re-implementation of
the RETIRED (pre-rewrite) algorithm, kept ONLY in this test file -- never
reused in production code -- so a future change to ``compute_psae`` still
gets checked against real data, now that the original implementation no
longer exists in ``src/`` to diff against directly.
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
# classify_psae_fraction_batch (Numba, 2026-09-15 perf fix) -- must match
# the scalar reference element-for-element, not just look right.
# --------------------------------------------------------------------------
def test_classify_psae_fraction_batch_matches_scalar_reference():
    import numpy as np

    values = np.array([1.0, 0.999, 0.5, 0.4999, 2 / 3, 1 / 3, 0.0001, 0.0, float("nan")])
    expected = [psae.classify_psae_fraction(v) for v in values]
    actual = list(psae.classify_psae_fraction_batch(values))
    assert actual == expected


def test_classify_psae_fraction_batch_empty_input():
    import numpy as np

    out = psae.classify_psae_fraction_batch(np.array([], dtype="float64"))
    assert len(out) == 0


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


# --------------------------------------------------------------------------
# Real-data regression -- vectorised compute_psae vs. an independent,
# deliberately slow per-group reference (the RETIRED pre-2026-09-14
# algorithm, reproduced here only, never in src/). See module docstring.
# --------------------------------------------------------------------------
def _reference_compute_psae(risk_band_result: rb.RiskBandTable) -> pd.DataFrame:
    """Line-for-line the algorithm ``compute_psae`` used before the
    2026-09-14 vectorised rewrite -- a per-(plant_uid, water_scenario)
    Python groupby loop. Deliberately NOT imported from anywhere in
    ``src/`` (it no longer exists there) -- kept here, independently, as
    the real-data cross-check the rewrite was originally verified against."""
    frame = risk_band_result.frame
    id_cols = [psae.PLANT_UID, "country", "plant_name", "bucket", "water_scenario",
               "heat_scenario", "model"]
    rows: list[dict] = []
    for (_plant_uid, _water_scenario), group in frame.groupby(
        [psae.PLANT_UID, "water_scenario"], sort=False,
    ):
        bucket = group["bucket"].iat[0]
        h_b = hs.APPLICABLE_HAZARDS[bucket]
        h_b_size = len(h_b)
        by_hazard = dict(zip(group["hazard_term"], group["risk_band"]))
        missing = tuple(h for h in h_b if pd.isna(by_hazard.get(h)))
        meta = group.iloc[0]
        row = {c: meta[c] for c in id_cols}
        row["h_b_size"] = h_b_size
        if missing:
            row["n_high_or_above"] = np.nan
            row["psae"] = np.nan
            row["psae_label"] = None
            row["psae_complete"] = False
            row["missing_hazards"] = missing
        else:
            n_high = sum(1 for h in h_b if by_hazard[h] in psae.HIGH_OR_ABOVE)
            fraction = n_high / h_b_size
            row["n_high_or_above"] = n_high
            row["psae"] = fraction
            row["psae_label"] = psae.classify_psae_fraction(fraction)
            row["psae_complete"] = True
            row["missing_hazards"] = ()
        rows.append(row)
    return pd.DataFrame.from_records(rows)[psae.PSAE_OUTPUT_COLUMNS]


def _rasters_present() -> bool:
    from src.index import risk_calculator as rc
    try:
        return rc.raster_path("heat", "Brazil", "opt", rc.configured_models()[0]).exists()
    except Exception:
        return False


@pytest.mark.skipif(not _rasters_present(), reason="processed rasters absent")
def test_compute_psae_matches_reference_implementation_on_real_data():
    """The 2026-09-14 vectorised rewrite must match the retired per-group
    algorithm exactly on real production RiskBand output -- not just on
    the small hand-built fixtures above."""
    from src.index import risk_calculator as rc

    model = rc.configured_models()[0]
    band_table = rb.compute_risk_bands(model)

    expected = _reference_compute_psae(band_table)
    actual = psae.compute_psae(band_table).frame

    key = [psae.PLANT_UID, "water_scenario"]
    expected = expected.sort_values(key).reset_index(drop=True)
    actual = actual.sort_values(key).reset_index(drop=True)

    assert list(expected.columns) == list(actual.columns)
    assert len(expected) == len(actual)
    for col in ("h_b_size", "n_high_or_above", "psae"):
        np.testing.assert_allclose(
            expected[col].to_numpy("float64"), actual[col].to_numpy("float64"),
            equal_nan=True,
        )
    for col in ("country", "plant_name", "bucket", "water_scenario",
                "heat_scenario", "model", "psae_label"):
        e = expected[col].astype(object).where(expected[col].notna(), None)
        a = actual[col].astype(object).where(actual[col].notna(), None)
        assert (e.to_numpy() == a.to_numpy()).all(), f"column {col!r} diverged"
    assert (expected["psae_complete"].to_numpy() == actual["psae_complete"].to_numpy()).all()
    assert (
        expected["missing_hazards"].apply(tuple).to_numpy()
        == actual["missing_hazards"].apply(tuple).to_numpy()
    ).all()
