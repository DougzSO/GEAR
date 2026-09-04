"""Tests for src/index/ccrs_calculator -- the CCRS Hazard term.

Covers: the closed per-bucket water/heat weights and how they are applied
(one case per bucket), the frozen global-bounds regression lock, the
GFDL-ESM4 / MIROC6 separation (separate fields, never blended), the exclusion
of ``wd`` from every calculation, and the per-GCM merge having no cross-join
duplication (stable ``plant_uid``).

Pure-function and monkeypatched tests run without touching disk. Tests that
read the processed rasters or the validated-plant CSVs are skipped (never
silently passed) when those inputs are absent.
"""

import random

import numpy as np
import pandas as pd
import pytest

from src.index import ccrs_calculator as cc


# --------------------------------------------------------------------------
# Weights — closed values
# --------------------------------------------------------------------------
def test_within_water_weights_match_published_spec():
    w = cc.WITHIN_WATER_WEIGHTS
    assert set(w) == {"ws", "sv", "iv"}          # no wd
    assert w["ws"] == pytest.approx(0.4164, abs=5e-5)
    assert w["sv"] == pytest.approx(0.2505, abs=5e-5)
    assert w["iv"] == pytest.approx(0.3331, abs=5e-5)
    assert sum(w.values()) == pytest.approx(1.0)


def test_bucket_weights_are_the_closed_matrix():
    assert cc.BUCKET_WEIGHTS == {
        "hydro":   {"water": 1.00, "heat": 0.00},
        "thermal": {"water": 0.75, "heat": 0.25},
        "wind":    {"water": 0.00, "heat": 1.00},
        "solar":   {"water": 0.00, "heat": 1.00},
    }
    for w in cc.BUCKET_WEIGHTS.values():
        assert w["water"] + w["heat"] == pytest.approx(1.0)


# --------------------------------------------------------------------------
# Transforms
# --------------------------------------------------------------------------
def test_tlin_is_linear_minmax():
    out = cc.transform_term("sv", np.array([0.0, 1.0, 2.0]), 0.0, 2.0)
    np.testing.assert_allclose(out, [0.0, 0.5, 1.0])


def test_tlog_is_log1p_then_minmax():
    raw = np.array([0.0, 3.0])
    out = cc.transform_term("ws", raw, 0.0, 3.0)
    # midpoint in log space, not linear space
    mid = cc.transform_term("ws", np.array([np.expm1(np.log1p(3.0) / 2)]), 0.0, 3.0)
    assert out[0] == pytest.approx(0.0)
    assert out[1] == pytest.approx(1.0)
    assert mid[0] == pytest.approx(0.5, abs=1e-6)


def test_transform_clips_out_of_range_and_handles_degenerate():
    np.testing.assert_allclose(
        cc.transform_term("iv", np.array([-1.0, 5.0]), 0.0, 2.0), [0.0, 1.0]
    )
    np.testing.assert_allclose(
        cc.transform_term("sv", np.array([1.0, 2.0]), 3.0, 3.0), [0.0, 0.0]
    )


# --------------------------------------------------------------------------
# 1. One case per bucket — weights applied correctly
# --------------------------------------------------------------------------
def test_hazard_per_bucket_weight_application():
    # transformed inputs, hand-picked
    water_sub_val = np.full(4, 0.40)
    t_heat = np.full(4, 0.80)
    buckets = np.array(["hydro", "thermal", "wind", "solar"], dtype=object)

    haz = cc.hazard(buckets, water_sub_val, t_heat)

    assert haz[0] == pytest.approx(1.00 * 0.40 + 0.00 * 0.80)   # hydro  -> 0.40
    assert haz[1] == pytest.approx(0.75 * 0.40 + 0.25 * 0.80)   # thermal-> 0.50
    assert haz[2] == pytest.approx(0.00 * 0.40 + 1.00 * 0.80)   # wind   -> 0.80
    assert haz[3] == pytest.approx(0.00 * 0.40 + 1.00 * 0.80)   # solar  -> 0.80


def test_wind_solar_hazard_is_heat_only_even_when_water_is_nan():
    haz = cc.hazard(
        np.array(["wind", "solar"], dtype=object),
        np.array([np.nan, np.nan]),      # entire water side missing
        np.array([0.3, 0.6]),
    )
    np.testing.assert_allclose(haz, [0.3, 0.6])


def test_hydro_hazard_is_water_only_even_when_heat_is_nan():
    haz = cc.hazard(
        np.array(["hydro"], dtype=object),
        np.array([0.42]),
        np.array([np.nan]),              # heat missing, weight 0 -> ignored
    )
    assert haz[0] == pytest.approx(0.42)


def test_thermal_hazard_propagates_nan_on_a_weighted_side():
    haz = cc.hazard(
        np.array(["thermal", "thermal"], dtype=object),
        np.array([0.4, np.nan]),
        np.array([np.nan, 0.5]),
    )
    assert np.isnan(haz).all()           # both sides weighted > 0 for thermal


def test_compute_hazard_end_to_end_per_bucket(monkeypatch):
    """compute_hazard: raw sample -> transform with given bounds -> weighted
    Hazard, one plant per bucket."""
    fake = pd.DataFrame({
        cc.PLANT_UID: ["T-00000", "T-00001", "T-00002", "T-00003", "T-00004"],
        "country": "Testland",
        "plant_name": ["h", "t", "w", "s", "nobucket"],
        "lon": 0.0, "lat": 0.0,
        "capacity_mw": [10.0, 20.0, 30.0, 40.0, 50.0],
        "commissioning_year": [2000.0, 2000.0, 2000.0, np.nan, 2000.0],
        "bucket": ["hydro", "thermal", "wind", "solar", pd.NA],
        "water_scenario": "opt", "heat_scenario": "ssp126",
        "ws": [1.0, 1.0, 1.0, 1.0, 1.0],
        "sv": [0.5, 0.5, 0.5, 0.5, 0.5],
        "iv": [0.5, 0.5, 0.5, 0.5, 0.5],
        "heat": [4.0, 4.0, 4.0, 4.0, 4.0],
    })
    monkeypatch.setattr(cc, "sample_terms", lambda model: fake.copy())
    bounds = {
        "ws": (0.0, 1.0), "sv": (0.0, 1.0), "iv": (0.0, 1.0),
        "heat": {"gfdl_esm4": (0.0, 4.0)},
    }
    out = cc.compute_hazard("gfdl_esm4", bounds=bounds)

    assert list(out["bucket"]) == ["hydro", "thermal", "wind", "solar"]  # NA dropped
    t_ws = np.clip(np.log1p(1.0) / np.log1p(1.0), 0, 1)   # 1.0
    t_heat = np.clip(np.log1p(4.0) / np.log1p(4.0), 0, 1)  # 1.0
    w_sub = 0.4164 * t_ws + 0.2505 * 0.5 + 0.3331 * 0.5
    by_bucket = dict(zip(out["bucket"], out["hazard"]))
    assert by_bucket["hydro"] == pytest.approx(w_sub, abs=1e-4)
    assert by_bucket["thermal"] == pytest.approx(0.75 * w_sub + 0.25 * t_heat, abs=1e-4)
    assert by_bucket["wind"] == pytest.approx(t_heat, abs=1e-4)
    assert by_bucket["solar"] == pytest.approx(t_heat, abs=1e-4)


# --------------------------------------------------------------------------
# 2. Frozen global-bounds regression lock
# --------------------------------------------------------------------------
def test_frozen_bounds_structure():
    fb = cc.FROZEN_BOUNDS
    assert set(fb) == {"ws", "sv", "iv", "heat"}
    for t in ("ws", "sv", "iv"):
        lo, hi = fb[t]
        assert lo <= hi
    assert set(fb["heat"]) == set(cc.configured_models())


def _rasters_present() -> bool:
    try:
        p = cc.raster_path("heat", "Brazil", "opt", cc.configured_models()[0])
        q = cc.raster_path("ws", "Brazil", "opt", cc.configured_models()[0])
        return p.exists() and q.exists()
    except Exception:
        return False


@pytest.mark.skipif(not _rasters_present(), reason="processed rasters absent — cannot recompute bounds")
def test_frozen_bounds_match_recomputed_from_data():
    """REGRESSION LOCK. Recomputes the global Min-Max bounds from the rasters
    on disk and compares them to FROZEN_BOUNDS.

    A failure here is NOT resolved by copying the recomputed numbers into
    FROZEN_BOUNDS. It means the data snapshot moved (a raster was
    reprocessed, a country or scenario was added/removed). Investigate the
    cause first; only then update FROZEN_BOUNDS + BOUNDS_DATA_SNAPSHOT
    deliberately, recording the before/after numbers in the commit. Never let
    the test recompute and accept silently.
    """
    live = cc.compute_global_bounds()
    assert cc._bounds_close(live, cc.FROZEN_BOUNDS), (
        f"global bounds drifted from the frozen snapshot {cc.BOUNDS_DATA_SNAPSHOT}.\n"
        f"  frozen:     {cc.FROZEN_BOUNDS}\n"
        f"  recomputed: {live}\n"
        "Manual review required — see this test's docstring."
    )


def test_bounds_close_detects_drift():
    base = {"ws": (0.0, 1.0), "sv": (0.0, 1.0), "iv": (0.0, 1.0),
            "heat": {"gfdl_esm4": (0.0, 10.0), "miroc6": (0.0, 20.0)}}
    assert cc._bounds_close(base, dict(base))
    drifted = {**base, "heat": {"gfdl_esm4": (0.0, 10.5), "miroc6": (0.0, 20.0)}}
    assert not cc._bounds_close(base, drifted)
    assert not cc._bounds_close(base, {**base, "ws": (0.0, 1.01)})


# --------------------------------------------------------------------------
# 3. GFDL-ESM4 vs MIROC6 -- separate fields, never blended
# --------------------------------------------------------------------------
def _fake_hazard_frame(val, *, dup_names=False):
    """Two plants with the SAME name and (when dup_names) identical
    capacity/commissioning year, but distinct plant_uid -- the exact shape
    that used to cross-join in the per-GCM merge."""
    name = "same plant" if dup_names else None
    return pd.DataFrame({
        cc.PLANT_UID: ["A-00000", "A-00001"],
        "country": ["A", "A"],
        "plant_name": [name or "p1", name or "p2"],
        "lat": [1.0, 2.0], "lon": [3.0, 4.0],
        "water_scenario": ["opt", "opt"], "heat_scenario": ["ssp126", "ssp126"],
        "bucket": ["wind", "solar"],
        "capacity_mw": [1.0, 1.0] if dup_names else [1.0, 2.0],
        "commissioning_year": [2001.0, 2001.0] if dup_names else [2001.0, 2002.0],
        "hazard": [val, val],
    })


def test_compute_hazard_by_gcm_keeps_models_in_separate_columns(monkeypatch):
    monkeypatch.setattr(
        cc, "compute_hazard",
        lambda model, bounds=None: _fake_hazard_frame({"gfdl_esm4": 0.10, "miroc6": 0.90}[model]),
    )
    wide = cc.compute_hazard_by_gcm(models=["gfdl_esm4", "miroc6"])

    assert "hazard_gfdl_esm4" in wide.columns
    assert "hazard_miroc6" in wide.columns
    assert "hazard" not in wide.columns                      # no blended column
    np.testing.assert_allclose(wide["hazard_gfdl_esm4"], [0.10, 0.10])
    np.testing.assert_allclose(wide["hazard_miroc6"], [0.90, 0.90])
    # the two GCMs are never averaged: no column equals their mean
    blend = (wide["hazard_gfdl_esm4"] + wide["hazard_miroc6"]) / 2
    assert not any(np.allclose(wide[c], blend) for c in wide.columns if c.startswith("hazard_"))


def test_compute_hazard_by_gcm_has_no_cross_join_duplication(monkeypatch):
    """Two GEM records sharing name + capacity + commissioning year (distinct
    only by plant_uid / coordinate) must NOT cross-join in the per-GCM merge.
    Before the plant_uid key this produced 2x2 = 4 rows instead of 2."""
    monkeypatch.setattr(
        cc, "compute_hazard",
        lambda model, bounds=None: _fake_hazard_frame(
            {"gfdl_esm4": 0.10, "miroc6": 0.90}[model], dup_names=True),
    )
    wide = cc.compute_hazard_by_gcm(models=["gfdl_esm4", "miroc6"])

    assert len(wide) == 2                                    # one row per plant_uid, not 4
    assert wide[cc.PLANT_UID].tolist() == ["A-00000", "A-00001"]
    assert wide.duplicated(cc.GCM_MERGE_KEY).sum() == 0


def test_compute_hazard_by_gcm_raises_on_residual_duplication(monkeypatch):
    """The guard inside compute_hazard_by_gcm fires if a merge ever
    cross-joins again (e.g. plant_uid stops being unique)."""
    dupe = _fake_hazard_frame(0.5, dup_names=True)
    dupe[cc.PLANT_UID] = "A-00000"                            # break uid uniqueness
    monkeypatch.setattr(cc, "compute_hazard", lambda model, bounds=None: dupe.copy())
    with pytest.raises(RuntimeError, match="cross-join"):
        cc.compute_hazard_by_gcm(models=["gfdl_esm4", "miroc6"])


@pytest.mark.skipif(not _rasters_present(), reason="processed rasters absent")
def test_real_gcm_columns_differ_and_are_not_a_blend():
    wide = cc.compute_hazard_by_gcm()
    both = wide.dropna(subset=["hazard_gfdl_esm4", "hazard_miroc6"])
    assert (both["hazard_gfdl_esm4"] != both["hazard_miroc6"]).any()
    # MIROC6 runs hotter for wind/solar (heat-only buckets) -- sanity that the
    # columns are genuinely per-model, not a shared value
    ws = both[both["bucket"].isin(["wind", "solar"])]
    assert ws["hazard_miroc6"].mean() > ws["hazard_gfdl_esm4"].mean()


# --------------------------------------------------------------------------
# 3b. plant_uid -- derived from record content, stable, unique
# --------------------------------------------------------------------------
def _plants_present() -> bool:
    return all(
        (cc.ASSETS_PROCESSED / f"gem_validated_plants_{c}.csv").exists()
        for c in cc.COUNTRIES
    )


def _row(name, lat, lon, cap, year, bucket, fuel):
    return {
        "country": "Brazil", "plant_name": name, "lat": lat, "lon": lon,
        "capacity_mw": cap, "fuel_type": fuel, "mixed_fuel_type": False,
        "fuel_types_found": fuel, "commissioning_year": year, "n_units": 1,
        "fuel_type_bucket": bucket,
    }


_FIXTURE_ROWS = [
    _row("Alpha wind farm", "-1.1000", "-2.2000", 10.0, 2000.0, "wind", "wind"),
    _row("Beta solar project", "-3.3000", "-4.4000", 20.0, 2001.0, "solar", "utility-scale solar"),
    # same name as row 0, different coordinate -> a distinct GEM record
    _row("Alpha wind farm", "-1.5000", "-2.9000", 10.0, 2000.0, "wind", "wind"),
    _row("Gamma hydroelectric plant", "-5.5000", "-6.6000", 30.0, 2002.0, "hydro", "hydropower"),
    _row("Delta power station", "-7.7000", "-8.8000", 40.0, 2003.0, "thermal", "oil/gas"),
]


def _write_plants_csv(path, rows):
    pd.DataFrame(rows).to_csv(path, index=False)


def _uid_by_record(df):
    """Map keyed by the identifying triple -> plant_uid."""
    return {
        (str(n), float(la), float(lo)): u
        for n, la, lo, u in zip(df["plant_name"], df["lat"], df["lon"], df[cc.PLANT_UID])
    }


def test_derive_plant_uid_is_deterministic_and_content_addressed():
    a = cc._derive_plant_uid("BRA", "Alpha wind farm", "-1.1000", "-2.2000")
    b = cc._derive_plant_uid("BRA", "Alpha wind farm", "-1.1000", "-2.2000")
    assert a == b and a.startswith("BRA-")
    # any identifying field changing changes the uid
    assert cc._derive_plant_uid("BRA", "Alpha wind farm", "-1.1000", "-2.2001") != a
    assert cc._derive_plant_uid("BRA", "Alpha wind FARM", "-1.1000", "-2.2000") != a


def test_plant_uid_is_stable_under_row_reordering(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, "ASSETS_PROCESSED", tmp_path)
    path = tmp_path / "gem_validated_plants_Brazil.csv"

    _write_plants_csv(path, _FIXTURE_ROWS)
    before = _uid_by_record(cc.load_plants("Brazil"))

    _write_plants_csv(path, list(reversed(_FIXTURE_ROWS)))
    after_reversed = _uid_by_record(cc.load_plants("Brazil"))

    shuffled = list(_FIXTURE_ROWS)
    random.Random(123).shuffle(shuffled)
    _write_plants_csv(path, shuffled)
    after_shuffled = _uid_by_record(cc.load_plants("Brazil"))

    assert before == after_reversed == after_shuffled
    assert len(before) == len(_FIXTURE_ROWS)          # incl. both "Alpha wind farm" records


def test_plant_uid_is_stable_when_a_middle_row_is_removed(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, "ASSETS_PROCESSED", tmp_path)
    path = tmp_path / "gem_validated_plants_Brazil.csv"

    _write_plants_csv(path, _FIXTURE_ROWS)
    before = _uid_by_record(cc.load_plants("Brazil"))

    trimmed = _FIXTURE_ROWS[:2] + _FIXTURE_ROWS[3:]   # drop row index 2 (an "Alpha" record)
    _write_plants_csv(path, trimmed)
    after = _uid_by_record(cc.load_plants("Brazil"))

    # every surviving record keeps the exact uid it had before
    for key, uid in after.items():
        assert before[key] == uid
    assert len(after) == len(before) - 1


def test_load_plants_raises_on_uid_collision(tmp_path, monkeypatch):
    monkeypatch.setattr(cc, "ASSETS_PROCESSED", tmp_path)
    path = tmp_path / "gem_validated_plants_Brazil.csv"
    dupe = _FIXTURE_ROWS[0]
    _write_plants_csv(path, [dupe, dict(dupe)])       # identical name+lat+lon twice
    with pytest.raises(ValueError, match="collision"):
        cc.load_plants("Brazil")


@pytest.mark.skipif(not _plants_present(), reason="validated-plant CSVs absent")
def test_load_plants_uid_unique_across_all_three_countries():
    for c in cc.COUNTRIES:
        p = cc.load_plants(c)
        assert p[cc.PLANT_UID].is_unique
        assert p[cc.PLANT_UID].str.fullmatch(cc.COUNTRY_ISO3[c] + r"-[0-9a-f]{12}").all()


@pytest.mark.skipif(
    not (_rasters_present() and _plants_present()), reason="rasters or plant CSVs absent"
)
def test_by_gcm_row_count_matches_unique_input_rows_and_dup_name_groups_stay_distinct():
    """Regression for the reported cross-join defect.

    (a) compute_hazard_by_gcm() must produce exactly one row per
        (individual plant x water_scenario), i.e. per plant_uid x scenario --
        counted by plant_uid, never by plant_name.
    (b) the (country, plant_name) groups that hold multiple GEM records must
        appear as that many distinct rows per scenario, neither collapsed nor
        duplicated.
    """
    plants = pd.concat([cc.load_plants(c) for c in cc.COUNTRIES], ignore_index=True)
    bucketed = plants[plants["bucket"].isin(cc.BUCKETS)]
    expected_rows = len(bucketed) * len(cc.WATER_SCENARIOS)

    wide = cc.compute_hazard_by_gcm()

    # (a)
    assert len(wide) == expected_rows
    assert wide.duplicated(cc.GCM_MERGE_KEY).sum() == 0
    assert wide[cc.PLANT_UID].nunique() == len(bucketed)

    # (b) -- the multi-record name groups
    grp = bucketed.groupby(["country", "plant_name"]).size()
    multi = grp[grp > 1]
    assert len(multi) > 0, "expected some multi-record (country, plant_name) groups"
    wide_grp = wide.groupby(["country", "plant_name"])
    for (country, name), n_records in multi.items():
        rows = wide_grp.get_group((country, name))
        assert len(rows) == n_records * len(cc.WATER_SCENARIOS)
        assert rows[cc.PLANT_UID].nunique() == n_records


# --------------------------------------------------------------------------
# 4. wd (water depletion) is excluded from every calculation
# --------------------------------------------------------------------------
def test_wd_is_not_a_hazard_term():
    assert "wd" not in cc.HAZARD_TERMS
    assert "wd" in cc.EXCLUDED_INDICATORS
    assert "wd" not in cc.WITHIN_WATER_WEIGHTS
    assert "wd" not in cc.WRI_TOP_THRESHOLD


def test_wd_has_no_raster_path_and_no_transform():
    with pytest.raises(ValueError):
        cc.raster_path("wd", "Brazil", "opt", cc.configured_models()[0])
    with pytest.raises(ValueError):
        cc.transform_term("wd", np.array([1.0]), 0.0, 2.0)


def test_wd_never_appears_in_sampled_or_scored_columns(monkeypatch):
    fake = pd.DataFrame({
        cc.PLANT_UID: ["T-00000"],
        "country": "T", "plant_name": ["a"], "lon": 0.0, "lat": 0.0,
        "capacity_mw": [1.0], "commissioning_year": [2000.0], "bucket": ["thermal"],
        "water_scenario": "opt", "heat_scenario": "ssp126",
        "ws": [1.0], "sv": [0.5], "iv": [0.5], "heat": [4.0],
    })
    monkeypatch.setattr(cc, "sample_terms", lambda model: fake.copy())
    out = cc.compute_hazard(
        "gfdl_esm4",
        bounds={"ws": (0.0, 1.0), "sv": (0.0, 1.0), "iv": (0.0, 1.0),
                "heat": {"gfdl_esm4": (0.0, 4.0)}},
    )
    assert not any("wd" in c for c in out.columns)


# --------------------------------------------------------------------------
# Capacity roll-up guard (V6)
# --------------------------------------------------------------------------
def test_computable_base_requires_commissioning_year():
    df = pd.DataFrame({
        "plant_name": ["a", "b", "c"],
        "commissioning_year": [2000.0, np.nan, 1990.0],
        "capacity_mw": [10.0, 20.0, 30.0],
    })
    base = cc.computable_base(df)
    assert list(base["plant_name"]) == ["a", "c"]
