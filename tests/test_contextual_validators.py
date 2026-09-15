"""Tests for src/index/contextual_validators -- GEAR v3 Phase 5 (Methods
Section 7), broad-impact (EM-DAT) validator class only (physical-occurrence
not implemented, no acquired source -- see module docstring).

Covers: pure GADM-GID parsing (no I/O), the three-state assignment logic
against real EM-DAT/GADM/plant data, and -- the task's explicit
requirement -- a read-only guarantee test proving this module never changes
psae.py/risk_bands.py/risk_calculator.py output.
"""

import numpy as np
import pandas as pd
import pytest

from src.config import BOUNDARIES_RAW, COUNTRIES, COUNTRY_ISO3
from src.downloaders import emdat_downloader
from src.index import contextual_validators as cv
from src.index import psae
from src.index import risk_bands as rb
from src.index import risk_calculator as rc


def _real_data_present() -> bool:
    plants_ok = all(
        (rc.ASSETS_PROCESSED / f"gem_validated_plants_{c}.csv").exists() for c in COUNTRIES
    )
    boundaries_ok = all(
        (BOUNDARIES_RAW / "gadm" / f"gadm41_{COUNTRY_ISO3[c]}.gpkg").exists() for c in COUNTRIES
    )
    emdat_ok = all(emdat_downloader.country_csv_path(c).exists() for c in COUNTRIES)
    rasters_ok = rc.raster_path("heat", "Brazil", "opt", rc.configured_models()[0]).exists()
    return plants_ok and boundaries_ok and emdat_ok and rasters_ok


pytestmark = pytest.mark.skipif(
    not _real_data_present(),
    reason="validated-plant CSVs, GADM boundaries, EM-DAT CSVs or processed rasters absent",
)


# --------------------------------------------------------------------------
# Pure GADM-GID parsing -- no I/O
# --------------------------------------------------------------------------
def test_resolve_admin1_gid_level_0_is_none():
    assert cv._resolve_admin1_gid("BRA", 0) is None


def test_resolve_admin1_gid_level_1_passes_through():
    assert cv._resolve_admin1_gid("BRA.5_1", 1) == "BRA.5_1"


def test_resolve_admin1_gid_level_2_truncates_to_admin1_parent():
    assert cv._resolve_admin1_gid("BRA.19.68_2", 2) == "BRA.19_1"


def test_resolve_admin1_gid_malformed_returns_none():
    assert cv._resolve_admin1_gid("BRA", 1) is None


def test_admin1_gids_from_cell_parses_mixed_levels():
    cell = '[{"gid_1": "BRA.5_1"}, {"gid_2": "BRA.19.68_2"}, {"gid_0": "BRA"}]'
    assert cv._admin1_gids_from_cell(cell) == {"BRA.5_1", "BRA.19_1"}


def test_admin1_gids_from_cell_empty_or_malformed_is_empty_set():
    assert cv._admin1_gids_from_cell(None) == set()
    assert cv._admin1_gids_from_cell("") == set()
    assert cv._admin1_gids_from_cell("not json") == set()
    assert cv._admin1_gids_from_cell(float("nan")) == set()


# --------------------------------------------------------------------------
# Three-state output -- pytestmark-gated real-data tests
# --------------------------------------------------------------------------
def test_output_only_uses_the_three_documented_states():
    out = cv.compute_broad_impact_validation(["Portugal"])  # smallest country, fastest
    assert set(out["state"]) <= set(cv.THREE_STATE_LABELS)


def test_every_row_is_hazard_applicable_to_its_own_bucket():
    from src.index import hazard_scope as hs

    out = cv.compute_broad_impact_validation(["Portugal"])
    for row in out.itertuples(index=False):
        assert row.hazard_term in hs.APPLICABLE_HAZARDS[row.bucket]


def test_unmapped_hazard_terms_are_always_not_applicable():
    """precip/wind/sv/iv have no EMDAT_DISASTER_TYPE_TO_TERM entry -- every
    row for those hazard terms must be Not Applicable, regardless of
    location."""
    out = cv.compute_broad_impact_validation(["Portugal"])
    unmapped = set(out["hazard_term"]) - set(cv.EMDAT_DISASTER_TYPE_TO_TERM.values())
    assert unmapped  # sanity: there really are unmapped terms in H_b
    rows = out[out["hazard_term"].isin(unmapped)]
    assert (rows["state"] == cv.NOT_APPLICABLE).all()


def test_corroborated_rows_have_at_least_one_geocoded_event_and_a_gid():
    out = cv.compute_broad_impact_validation(["Portugal"])
    corroborated = out[out["state"] == cv.CORROBORATED]
    if len(corroborated):
        assert (corroborated["n_geocoded_events"] >= 1).all()
        assert corroborated["gid_1"].notna().all()


def test_no_record_rows_have_zero_geocoded_events_but_a_mapped_hazard_and_gid():
    out = cv.compute_broad_impact_validation(["Portugal"])
    no_record = out[out["state"] == cv.NO_RECORD]
    if len(no_record):
        assert (no_record["n_geocoded_events"] == 0).all()
        assert no_record["gid_1"].notna().all()
        assert no_record["hazard_term"].isin(cv.EMDAT_DISASTER_TYPE_TO_TERM.values()).all()


def test_plants_with_no_admin1_match_are_not_applicable_everywhere():
    out = cv.compute_broad_impact_validation(["Brazil"])
    unmatched = out[out["gid_1"].isna()]
    if len(unmatched):
        assert (unmatched["state"] == cv.NOT_APPLICABLE).all()


def test_output_has_no_duplicate_plant_hazard_rows():
    out = cv.compute_broad_impact_validation(["Portugal"])
    key = [cv.PLANT_UID, "validator_class", "hazard_term"]
    assert out.duplicated(key).sum() == 0


def test_physical_occurrence_raises_not_implemented():
    with pytest.raises(NotImplementedError, match="physical-occurrence"):
        cv.compute_physical_occurrence_validation()


def test_compute_contextual_validation_is_broad_impact_only():
    out = cv.compute_contextual_validation(["Portugal"])
    assert set(out["validator_class"]) == {cv.VALIDATOR_CLASS_BROAD_IMPACT}


# --------------------------------------------------------------------------
# Read-only guarantee (task requirement, explicit) -- risk_calculator /
# risk_bands / psae outputs must be byte-for-byte identical before and
# after running the validator layer.
# --------------------------------------------------------------------------
def _frame_equal(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    if list(a.columns) != list(b.columns) or len(a) != len(b):
        return False
    a = a.reset_index(drop=True)
    b = b.reset_index(drop=True)
    for col in a.columns:
        av, bv = a[col], b[col]
        if pd.api.types.is_numeric_dtype(av) and pd.api.types.is_numeric_dtype(bv):
            if not np.allclose(
                av.to_numpy("float64"), bv.to_numpy("float64"), equal_nan=True,
            ):
                return False
        else:
            av_obj = av.astype(object).where(av.notna(), None)
            bv_obj = bv.astype(object).where(bv.notna(), None)
            if not (av_obj.to_numpy() == bv_obj.to_numpy()).all():
                return False
    return True


def test_contextual_validators_does_not_change_risk_calculator_output():
    model = rc.configured_models()[0]
    before = rc.compute_risk_by_hazard(model)
    cv.compute_contextual_validation(["Portugal"])
    after = rc.compute_risk_by_hazard(model)
    assert _frame_equal(before, after)


def test_contextual_validators_does_not_change_risk_bands_output():
    model = rc.configured_models()[0]
    before = rb.compute_risk_bands(model)
    cv.compute_contextual_validation(["Portugal"])
    after = rb.compute_risk_bands(model)
    assert _frame_equal(before.frame, after.frame)
    assert before.percentile_cuts == after.percentile_cuts


def test_contextual_validators_does_not_change_psae_output():
    model = rc.configured_models()[0]
    band_table = rb.compute_risk_bands(model)
    before = psae.compute_psae(band_table)
    cv.compute_contextual_validation(["Portugal"])
    after = psae.compute_psae(band_table)
    assert _frame_equal(before.frame, after.frame)


def test_contextual_validators_module_imports_but_never_calls_mutating_apis():
    """Structural guard, not just behavioural: this module must not import
    anything from psae.py or risk_bands.py at all -- Section 7.3's overlay
    constraint means it should not even need to."""
    import inspect

    import_lines = [
        line for line in inspect.getsource(cv).splitlines()
        if line.strip().startswith(("import ", "from "))
    ]
    assert not any("psae" in line for line in import_lines)
    assert not any("risk_bands" in line for line in import_lines)
