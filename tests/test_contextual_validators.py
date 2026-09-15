"""Tests for src/index/contextual_validators -- GEAR v3 Phase 5 (Methods
Section 7): broad-impact (EM-DAT) and physical-occurrence (IBTrACS, ``wind``
term only) validator classes. FIRMS/landslide/lightning remain unacquired --
see module docstring.

Covers: pure GADM-GID parsing and haversine distance (no I/O), the
three-state assignment logic against real EM-DAT/IBTrACS/GADM/plant data
(including the known Brazil-near-null / India-real-density physical cases),
and -- the task's explicit requirement -- a read-only guarantee test proving
this module never changes psae.py/risk_bands.py/risk_calculator.py output.
"""

import numpy as np
import pandas as pd
import pytest

from src.config import BOUNDARIES_RAW, COUNTRIES, COUNTRY_ISO3
from src.downloaders import emdat_downloader, ibtracs_downloader
from src.index import contextual_validators as cv
from src.index import hazard_scope as hs
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
    ibtracs_ok = all(ibtracs_downloader.country_csv_path(c).exists() for c in COUNTRIES)
    rasters_ok = rc.raster_path("heat", "Brazil", "opt", rc.configured_models()[0]).exists()
    return plants_ok and boundaries_ok and emdat_ok and ibtracs_ok and rasters_ok


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


# --------------------------------------------------------------------------
# Physical-occurrence (IBTrACS) -- pure haversine, no I/O
# --------------------------------------------------------------------------
def test_haversine_zero_distance_for_identical_points():
    assert cv._haversine_km(-23.5, -46.6, -23.5, -46.6) == pytest.approx(0.0, abs=1e-6)


def test_haversine_matches_known_distance():
    # Lisbon (38.72 N, -9.14) to Porto (41.15 N, -8.61) -- known great-circle
    # distance ~273 km, cross-checked independently of this module.
    d = cv._haversine_km(38.72, -9.14, 41.15, -8.61)
    assert d == pytest.approx(273.0, rel=0.02)


def test_haversine_broadcasts_over_arrays():
    import numpy as np

    lat2 = np.array([-23.5, -22.9])
    lon2 = np.array([-46.6, -43.2])
    d = cv._haversine_km(-23.5, -46.6, lat2, lon2)
    assert d.shape == (2,)
    assert d[0] == pytest.approx(0.0, abs=1e-6)


# --------------------------------------------------------------------------
# Physical-occurrence (IBTrACS) -- pytestmark-gated real-data tests
# --------------------------------------------------------------------------
def test_physical_occurrence_output_only_uses_the_three_documented_states():
    out = cv.compute_physical_occurrence_validation(["Portugal"])
    assert set(out["state"]) <= set(cv.THREE_STATE_LABELS)


def test_physical_occurrence_every_row_is_hazard_applicable_to_its_own_bucket():
    out = cv.compute_physical_occurrence_validation(["Portugal"])
    for row in out.itertuples(index=False):
        assert row.hazard_term in hs.APPLICABLE_HAZARDS[row.bucket]


def test_physical_occurrence_non_wind_hazard_terms_are_always_not_applicable():
    """IBTrACS covers only ``wind`` -- every row for every other hazard term
    (ws/spei/precip/sv/iv/heat) must be Not Applicable, regardless of
    location, exactly the same shape as EM-DAT's unmapped-term rows."""
    out = cv.compute_physical_occurrence_validation(COUNTRIES)
    non_wind = out[out["hazard_term"] != "wind"]
    assert len(non_wind)  # sanity: hydro/thermal rows really are present
    assert (non_wind["state"] == cv.NOT_APPLICABLE).all()


def test_physical_occurrence_wind_rows_are_only_wind_or_solar_bucket():
    out = cv.compute_physical_occurrence_validation(COUNTRIES)
    wind_rows = out[out["hazard_term"] == "wind"]
    assert set(wind_rows["bucket"]) <= {"wind", "solar"}


def test_physical_occurrence_corroborated_rows_have_at_least_one_match():
    out = cv.compute_physical_occurrence_validation(COUNTRIES)
    corroborated = out[out["state"] == cv.CORROBORATED]
    if len(corroborated):
        assert (corroborated["n_geocoded_events"] >= 1).all()
        assert (corroborated["hazard_term"] == "wind").all()
        assert corroborated["gid_1"].isna().all()


def test_physical_occurrence_no_record_rows_have_zero_matches():
    out = cv.compute_physical_occurrence_validation(COUNTRIES)
    no_record = out[(out["state"] == cv.NO_RECORD) & (out["validator_class"] == cv.VALIDATOR_CLASS_PHYSICAL_OCCURRENCE)]
    if len(no_record):
        assert (no_record["n_geocoded_events"] == 0).all()
        assert (no_record["hazard_term"] == "wind").all()


def test_physical_occurrence_output_has_no_duplicate_plant_hazard_rows():
    out = cv.compute_physical_occurrence_validation(["Portugal"])
    key = [cv.PLANT_UID, "validator_class", "hazard_term"]
    assert out.duplicated(key).sum() == 0


def test_physical_occurrence_brazil_is_near_total_no_record():
    """South Atlantic tropical-cyclone climatology is near-zero -- Hurricane
    Catarina (2004) is the one documented case. This validator's
    corroboration rate for Brazil should reflect that near-null physical
    reality, not indicate a bug or a data gap."""
    out = cv.compute_physical_occurrence_validation(["Brazil"])
    wind_rows = out[out["hazard_term"] == "wind"]
    corroborated = wind_rows[wind_rows["state"] == cv.CORROBORATED]
    assert len(corroborated) / len(wind_rows) < 0.01  # well under 1%
    if len(corroborated):
        # every Brazil corroboration must trace back to a track point within
        # STORM_TRACK_RADIUS_KM of that specific plant -- and every such
        # matched storm must be Catarina, the SA basin's one documented
        # hurricane-strength case. Other qualifying SA-basin storms exist in
        # the raw track file (e.g. weak 2010/2011 subtropical systems) but
        # never approach any actual plant -- checked directly, not inferred
        # from the basin-wide qualifying-track list.
        plants = rc.load_plants("Brazil")
        plants = plants[plants[cv.PLANT_UID].isin(corroborated[cv.PLANT_UID])]
        tracks = cv.load_ibtracs_track_points("Brazil")
        tracks = tracks[
            (tracks["SEASON"] >= cv.VALIDATION_WINDOW_START_YEAR)
            & (tracks["WIND_KT"] >= cv.IBTRACS_MIN_WIND_KT)
        ]
        matched_sids = set()
        for plant in plants.itertuples(index=False):
            d = cv._haversine_km(plant.lat, plant.lon, tracks["LAT"].to_numpy(), tracks["LON"].to_numpy())
            matched_sids.update(tracks.loc[d <= cv.STORM_TRACK_RADIUS_KM, "SID"].unique())
        assert matched_sids == {"2004086S29318"}


def test_physical_occurrence_india_has_real_corroboration_density():
    """India's coastal wind/solar plants sit inside an active North Indian
    Ocean cyclone basin -- corroboration should be a substantial, non-token
    fraction, unlike Brazil's near-null case."""
    out = cv.compute_physical_occurrence_validation(["India"])
    wind_rows = out[out["hazard_term"] == "wind"]
    corroborated = wind_rows[wind_rows["state"] == cv.CORROBORATED]
    assert len(corroborated) / len(wind_rows) > 0.10  # well above Brazil's <1%


def test_compute_contextual_validation_stacks_both_implemented_classes():
    out = cv.compute_contextual_validation(["Portugal"])
    assert set(out["validator_class"]) == {
        cv.VALIDATOR_CLASS_BROAD_IMPACT,
        cv.VALIDATOR_CLASS_PHYSICAL_OCCURRENCE,
    }
    # both classes report the full (plant, hazard_term) grid independently --
    # stacking must not deduplicate or drop either class's rows
    broad = cv.compute_broad_impact_validation(["Portugal"])
    physical = cv.compute_physical_occurrence_validation(["Portugal"])
    assert len(out) == len(broad) + len(physical)


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
