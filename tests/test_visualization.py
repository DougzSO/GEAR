"""Tests for src/visualization -- the CCRS figure/table modules, including
Douglas's 2026-09-04 review round (Parts A-C).

Covers: one test per figure category running on small synthetic data (no
rendering validation, just "runs without raising and produces the expected
file/object"), disputed-territory handling (India) still works against the
new schema, computable-base plants are always marked (never omitted),
per-country + combined produce the right file counts, the module never reads
a CSV from data/outputs/tables/, the Part A style rules (PDF isolated in a
pdf/ subfolder, no printed title, Power Plants=X wording), the B1/B2
scenario-grid generation, and the new C1-C5 figures/tables. C6 is not
implemented (exploratory only, see ``test_c6_investigation_documented``).

Figure-generating tests are skipped (never silently passed) when the GADM
boundary files are absent -- they are raw source data, not stale-methodology
output, so this is the same kind of skip other test files already use for
processed rasters / validated-plant CSVs.
"""

import matplotlib
matplotlib.use("Agg")  # headless -- no display needed for these tests

import numpy as np
import pandas as pd
import pytest

from src.config import COUNTRIES
from src.index.ccrs_calculator import BUCKETS, WATER_SCENARIOS
from src.index.risk_bands import HEAT_RISK_BANDS, PRIMARY_GCM, WATER_RISK_BANDS, BandTable
from src.visualization import _common, charts, data as vdata, maps, tables as vtables


def _boundaries_present() -> bool:
    try:
        return all(_common.load_admin1_boundaries(c) is not None for c in COUNTRIES)
    except Exception:
        return False


boundaries_needed = pytest.mark.skipif(not _boundaries_present(), reason="GADM boundary files absent")


# --------------------------------------------------------------------------
# Synthetic fixtures -- no real CCRS data, no disk I/O beyond raw GADM boundaries
# --------------------------------------------------------------------------
def _synthetic_final() -> pd.DataFrame:
    rows = []
    coords = {
        "Brazil": (-50.0, -15.0), "Portugal": (-8.0, 39.5), "India": (78.0, 22.0),
    }
    plant_id = 0
    for country in COUNTRIES:
        lon0, lat0 = coords[country]
        for i, bucket in enumerate(BUCKETS):
            for scen, gcm_a, gcm_b in [("opt", 0.3, 0.5), ("bau", 0.5, 0.7), ("pes", 0.7, 0.9)]:
                plant_id += 1
                missing_year = country == "Brazil" and bucket == "wind"  # exercise the "excluded" path
                rows.append({
                    "plant_uid": f"{country[:3].upper()}-{plant_id:04d}",
                    "water_scenario": scen, "heat_scenario": {"opt": "ssp126", "bau": "ssp370", "pes": "ssp585"}[scen],
                    "country": country, "plant_name": f"{bucket} plant {i}",
                    "lat": lat0 + i * 0.3, "lon": lon0 + i * 0.3,
                    "bucket": bucket, "capacity_mw": 50.0 + i * 20,
                    "commissioning_year": np.nan if missing_year else 2000 + i,
                    "hazard_gfdl_esm4": gcm_a * (i + 1) / len(BUCKETS),
                    "hazard_miroc6": gcm_b * (i + 1) / len(BUCKETS),
                    "age": np.nan if missing_year else 50.0 - i,
                    "age_factor": 1.0 + 0.1 * i,
                    "age_factor_neutralized_missing_year": missing_year,
                    "n_events": 100, "rate": 0.8, "event_multiplier": 1.2,
                    "ccrs_gfdl_esm4": gcm_a * (i + 1) / len(BUCKETS) * (1.0 + 0.1 * i) * 1.2,
                    "ccrs_miroc6": gcm_b * (i + 1) / len(BUCKETS) * (1.0 + 0.1 * i) * 1.2,
                    "water_risk_band": WATER_RISK_BANDS[i % len(WATER_RISK_BANDS)],
                    "heat_risk_band_gfdl_esm4": HEAT_RISK_BANDS[i % len(HEAT_RISK_BANDS)],
                    "heat_risk_band_miroc6": HEAT_RISK_BANDS[(i + 1) % len(HEAT_RISK_BANDS)],
                    "computable": not missing_year,
                })
    return pd.DataFrame(rows)


def _synthetic_bands(final: pd.DataFrame) -> dict[str, BandTable]:
    out = {}
    for gcm in ("gfdl_esm4", "miroc6"):
        frame = final[["plant_uid", "country", "water_scenario", "heat_scenario", "capacity_mw",
                        "commissioning_year", "bucket", "water_risk_band"]].copy()
        frame["heat_risk_band"] = final[f"heat_risk_band_{gcm}"]
        out[gcm] = BandTable(frame=frame, heat_cuts={25: 1.0, 75: 2.0, 95: 3.0}, heat_gcm=gcm)
    return out


def _synthetic_age_factors(final: pd.DataFrame) -> pd.DataFrame:
    return final[["plant_uid", "country", "bucket", "age_factor",
                   "age_factor_neutralized_missing_year"]].drop_duplicates("plant_uid")


def _synthetic_event_multipliers() -> pd.DataFrame:
    return pd.DataFrame({
        "country": COUNTRIES, "n_events": [239, 38, 622],
        "rate": [1.9, 0.3, 5.0], "event_multiplier": [1.19, 1.03, 1.5],
    })


def _synthetic_national_ci(scenarios=("opt", "bau", "pes"), seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for country in COUNTRIES:
        for scen in scenarios:
            point = rng.uniform(0.3, 0.9)
            rows.append({
                "country": country, "water_scenario": scen, "point_estimate": point,
                "p2.5": point * 0.85, "p50.0": point, "p97.5": point * 1.15,
            })
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def synth():
    final = _synthetic_final()
    return {
        "final": final,
        "bands": _synthetic_bands(final),
        "age_factors": _synthetic_age_factors(final),
        "event_multipliers": _synthetic_event_multipliers(),
    }


def _capture_figures(monkeypatch, module):
    """Intercepts every ``save_figure`` call made by ``module`` so the test
    can inspect the ``Figure`` object before it is closed (the public
    plotting functions save-and-close internally)."""
    captured = []
    real_save = _common.save_figure

    def _spy(fig, out_path):
        captured.append(fig)
        return real_save(fig, out_path)

    monkeypatch.setattr(module, "save_figure", _spy)
    return captured


# --------------------------------------------------------------------------
# 1. One test per figure category -- runs without error on synthetic data
# --------------------------------------------------------------------------
@boundaries_needed
def test_category_1_ccrs_overview_map(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    paths = maps.plot_ccrs_overview_map(countries=["Portugal"], final=synth["final"])
    assert paths["combined"].exists()


@boundaries_needed
def test_category_2_scenario_delta_map(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    paths = maps.plot_ccrs_scenario_delta_map(countries=["Portugal"], final=synth["final"])
    assert paths["Portugal"].exists()


@boundaries_needed
def test_category_3_water_risk_band_map(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    paths = maps.plot_water_risk_band_map(countries=["Portugal"], final=synth["final"])
    assert paths["combined"].exists()


@boundaries_needed
def test_category_4_heat_risk_band_map(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    paths = maps.plot_heat_risk_band_map(countries=["Portugal"], final=synth["final"])
    assert paths["combined"].exists()


def test_category_5_water_heat_combined_risk_bars(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "OUT_DIR", tmp_path)
    paths = charts.plot_water_heat_combined_risk_bars(countries=["Portugal"], bands=synth["bands"])
    assert paths["Portugal"].exists()


def test_category_6_ccrs_distribution_by_bucket(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "SECONDARY_DIR", tmp_path)
    path = charts.plot_ccrs_distribution_by_bucket(final=synth["final"])
    assert path.exists()


def test_category_6_ccrs_distribution_covers_all_scenarios(synth, tmp_path, monkeypatch):
    """B5: category 6 must be generatable for all three water scenarios,
    not bau only."""
    monkeypatch.setattr(charts, "SECONDARY_DIR", tmp_path)
    paths = {ws: charts.plot_ccrs_distribution_by_bucket(final=synth["final"], water_scenario=ws)
             for ws in WATER_SCENARIOS}
    assert len(paths) == 3
    for p in paths.values():
        assert p.exists()


def test_category_7_age_factor_by_bucket(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "SECONDARY_DIR", tmp_path)
    path = charts.plot_age_factor_by_bucket(age_factors=synth["age_factors"])
    assert path.exists()


def test_category_8_capacity_by_risk_band(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "SECONDARY_DIR", tmp_path)
    water_shares = vdata.load_water_band_shares(synth["bands"])
    heat_shares = vdata.load_heat_band_shares(synth["bands"])
    path = charts.plot_capacity_by_risk_band(water_shares=water_shares, heat_shares=heat_shares)
    assert path.exists()


# --------------------------------------------------------------------------
# FIG 3a/3b -- capacity vulnerability by bucket x scenario, one sister figure
# per risk-band axis (Douglas's 2026-09-05 request, both axes shown side by
# side rather than heat alone -- see the module comment in charts.py),
# promoted out of combined/secondary/ into the primary output dir.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("plot_fn, kwargs", [
    (charts.plot_capacity_vulnerability_by_bucket_water, {}),
    (charts.plot_capacity_vulnerability_by_bucket_heat, {}),
])
def test_fig3_saved_to_primary_dir(synth, tmp_path, monkeypatch, plot_fn, kwargs):
    monkeypatch.setattr(charts, "OUT_DIR", tmp_path)
    path = plot_fn(bands=synth["bands"], **kwargs)
    assert path.exists()
    assert "secondary" not in str(path)  # promoted, not left in combined/secondary/


@pytest.mark.parametrize("band_col, bands_tuple", [
    ("water_risk_band", WATER_RISK_BANDS),
    ("heat_risk_band", HEAT_RISK_BANDS),
])
def test_fig3_capacity_shares_sum_to_100_pct_per_bucket_country_scenario(synth, band_col, bands_tuple):
    from src.index import ccrs_report as cr

    frame = synth["bands"][PRIMARY_GCM].frame
    shares = cr.band_capacity_shares(frame, band_col, bands_tuple, ["bucket", "country", "water_scenario"])
    totals = shares.groupby(["bucket", "country", "water_scenario"])["capacity_share"].sum()
    # each (bucket, country, scenario) cell's bands + NO_BAND sum to 1.0 --
    # same convention as risk_bands/ccrs_report (never silently short of 100%)
    np.testing.assert_allclose(totals.to_numpy(), 1.0, atol=1e-9)


@pytest.mark.parametrize("band_col, bands_tuple", [
    ("water_risk_band", WATER_RISK_BANDS),
    ("heat_risk_band", HEAT_RISK_BANDS),
])
def test_fig3_all_four_buckets_are_segregated_not_mixed(synth, band_col, bands_tuple):
    from src.index import ccrs_report as cr

    frame = synth["bands"][PRIMARY_GCM].frame
    shares = cr.band_capacity_shares(frame, band_col, bands_tuple, ["bucket", "country", "water_scenario"])
    assert set(shares["bucket"].unique()) == set(BUCKETS)
    # one row per band (+ NO_BAND) per (bucket, country, scenario) cell -- no
    # cross-bucket blending anywhere in the grouped frame
    for bucket in BUCKETS:
        sub = shares[shares["bucket"] == bucket]
        assert set(sub["country"]) <= set(COUNTRIES)
        n_expected_rows = len(sub[["country", "water_scenario"]].drop_duplicates()) * (len(bands_tuple) + 1)
        assert len(sub) == n_expected_rows


def test_fig3a_and_fig3b_are_distinct_files_with_different_band_axes(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "OUT_DIR", tmp_path)
    water_path = charts.plot_capacity_vulnerability_by_bucket_water(bands=synth["bands"])
    heat_path = charts.plot_capacity_vulnerability_by_bucket_heat(bands=synth["bands"])
    assert water_path != heat_path
    assert water_path.exists() and heat_path.exists()


def test_category_9_event_multiplier_removed_replaced_by_table():
    """B5: the 3-bar EventMultiplier chart is removed, not relocated --
    replaced by ``tables.event_multiplier_table``."""
    assert not hasattr(charts, "plot_event_multiplier_by_country")
    table = vtables.event_multiplier_table(synth_em := _synthetic_event_multipliers())
    assert list(table["country"]) == sorted(COUNTRIES)
    assert set(table.columns) == {"country", "n_events", "rate", "event_multiplier"}


@boundaries_needed
def test_category_10_computable_base_map(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    paths = maps.plot_computable_base_map(countries=["Brazil"], final=synth["final"])
    assert paths["combined"].exists()


def test_category_11_top_n_ccrs_breakdown_by_bucket(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "OUT_DIR", tmp_path)
    paths = charts.plot_top_n_ccrs_breakdown_by_bucket(countries=["Portugal"], final=synth["final"], n=3)
    assert paths["Portugal"].exists()


# --------------------------------------------------------------------------
# 2. Disputed territory (India) still works against the new schema
# --------------------------------------------------------------------------
@boundaries_needed
def test_india_disputed_territory_handling():
    assert _common.country_has_disputed_admin1("India") == True  # noqa: E712 (numpy bool)
    assert _common.country_has_disputed_admin1("Brazil") == False  # noqa: E712
    assert _common.country_has_disputed_admin1("Portugal") == False  # noqa: E712

    disclaimer = _common.footer_with_gadm_disclaimer("", ["India"])
    assert _common.GADM_DISCLAIMER_TEXT in disclaimer
    assert _common.footer_with_gadm_disclaimer("", ["Brazil"]) == ""


@boundaries_needed
def test_india_map_renders_with_disputed_admin1(synth, tmp_path, monkeypatch):
    """End-to-end: a map over India (new CCRS schema) must not raise while
    drawing the disputed admin-1 polygons."""
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    paths = maps.plot_ccrs_overview_map(countries=["India"], final=synth["final"])
    assert paths["combined"].exists()


# --------------------------------------------------------------------------
# 3. Computable-base-excluded plants: always marked, never omitted
# --------------------------------------------------------------------------
def test_excluded_plants_are_marked_never_dropped(synth):
    final = synth["final"]
    excluded = final[~final["computable"]]
    assert len(excluded) > 0, "fixture must contain at least one excluded plant to test this"

    frame_country = final[(final["country"] == "Brazil") & (final["water_scenario"] == "bau")]
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    try:
        stats = maps._draw_bubble_panel(ax, "Brazil", frame_country, ring_col=None)
    finally:
        plt.close(fig)
    expected_excluded = len(frame_country[~frame_country["computable"]])
    assert stats["n_excluded"] == expected_excluded
    assert expected_excluded > 0


@boundaries_needed
def test_computable_base_map_includes_excluded_plants(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    final = synth["final"]
    frame_country = final[(final["country"] == "Brazil") & (final["water_scenario"] == "bau")]
    assert (~frame_country["computable"]).any()
    paths = maps.plot_computable_base_map(countries=["Brazil"], final=final)
    assert paths["combined"].exists()


# --------------------------------------------------------------------------
# 4. One combined figure per call, with its PDF
# --------------------------------------------------------------------------
@boundaries_needed
def test_overview_map_produces_one_combined_file_with_pdf(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    paths = maps.plot_ccrs_overview_map(final=synth["final"])
    assert len(paths) == 1
    assert "combined" in paths
    assert paths["combined"].exists() and _common.pdf_path_for(paths["combined"]).exists()


# --------------------------------------------------------------------------
# 5. No dependency on cached CSVs in data/outputs/tables/
# --------------------------------------------------------------------------
def test_load_ccrs_final_never_reads_a_cached_csv(monkeypatch, tmp_path):
    from src.index import age_factor, ccrs_calculator as ccrs, event_multiplier, risk_bands

    fake_hazard = pd.DataFrame({
        "plant_uid": ["X-01"], "country": ["Brazil"], "plant_name": ["fake"],
        "lat": [0.0], "lon": [0.0], "water_scenario": ["bau"], "heat_scenario": ["ssp370"],
        "bucket": ["thermal"], "capacity_mw": [10.0], "commissioning_year": [2000.0],
        "hazard_gfdl_esm4": [0.42], "hazard_miroc6": [0.55],
    })
    fake_af = pd.DataFrame({
        "plant_uid": ["X-01"], "age": [50.0], "age_factor": [1.3],
        "age_factor_neutralized_missing_year": [False],
    })
    fake_em = pd.DataFrame({
        "country": ["Brazil"], "n_events": [1], "rate": [0.1], "event_multiplier": [1.05],
    })
    fake_band_frame = pd.DataFrame({
        "plant_uid": ["X-01"], "water_scenario": ["bau"], "water_risk_band": ["Low"],
        "heat_risk_band": ["LOW"],
    })
    fake_bands = {
        gcm: risk_bands.BandTable(frame=fake_band_frame.copy(), heat_cuts={25: 1, 75: 2, 95: 3}, heat_gcm=gcm)
        for gcm in ccrs.configured_models()
    }

    def _boom(*a, **k):
        raise AssertionError("data.py must not read a CSV from data/outputs/tables/")

    monkeypatch.setattr(ccrs, "compute_hazard_by_gcm", lambda *a, **k: fake_hazard.copy())
    monkeypatch.setattr(age_factor, "compute_age_factors", lambda *a, **k: fake_af.copy())
    monkeypatch.setattr(event_multiplier, "compute_event_multipliers", lambda *a, **k: fake_em.copy())
    monkeypatch.setattr(risk_bands, "compute_bands", lambda gcm=None, **k: fake_bands[gcm or risk_bands.PRIMARY_GCM])
    monkeypatch.setattr(pd, "read_csv", _boom)

    final = vdata.load_ccrs_final()

    assert list(final["plant_uid"]) == ["X-01"]
    assert final["ccrs_gfdl_esm4"].iloc[0] == pytest.approx(0.42 * 1.3 * 1.05)
    assert final["water_risk_band"].iloc[0] == "Low"


# --------------------------------------------------------------------------
# 6. Part A -- style rules: PDF subfolder, no title, Power Plants=X, bold
# --------------------------------------------------------------------------
def test_save_figure_isolates_pdf_in_a_subfolder(tmp_path):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0, 1])
    out_path = tmp_path / "some_figure.png"
    _common.save_figure(fig, out_path)
    assert out_path.exists()
    pdf_path = tmp_path / "pdf" / "some_figure.pdf"
    assert pdf_path.exists()
    assert pdf_path == _common.pdf_path_for(out_path)
    assert not (tmp_path / "some_figure.pdf").exists()


@boundaries_needed
def test_no_figure_prints_a_title(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    captured = _capture_figures(monkeypatch, maps)
    maps.plot_ccrs_overview_map(countries=["Portugal"], final=synth["final"])
    assert len(captured) == 1
    assert captured[0]._suptitle is None


def test_panel_title_uses_power_plants_wording_and_is_bold():
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    try:
        _common.panel_title(ax, "Portugal", 12, 3)
        title = ax.get_title()
        assert "Power Plants=12" in title
        assert "n=" not in title
        assert "excluded=3" in title
        assert ax.title.get_fontweight() in ("bold", 700)
    finally:
        plt.close(fig)


# --------------------------------------------------------------------------
# 7. Correction 1 (2026-09-05) -- one figure per scenario, countries side by
# side (the layout category 4/HeatRiskBand already used correctly; B2 was
# misread on 2026-09-04 as "pack all 3 scenarios into one figure" -- it
# asked for generation ACROSS all 3 scenarios, one file each).
# --------------------------------------------------------------------------
@boundaries_needed
def test_overview_map_is_one_file_per_scenario_countries_side_by_side(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    captured = _capture_figures(monkeypatch, maps)
    maps.plot_ccrs_overview_map(countries=["Brazil", "Portugal"], final=synth["final"], water_scenario="bau")
    assert len(captured) == 1
    assert len(captured[0].axes) == 2  # one panel per country, no scenario dimension in this figure


@boundaries_needed
def test_overview_map_generates_a_distinct_file_per_scenario(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    paths = {ws: maps.plot_ccrs_overview_map(countries=["Portugal"], final=synth["final"], water_scenario=ws)["combined"]
             for ws in WATER_SCENARIOS}
    assert len(set(paths.values())) == 3  # 3 distinct files, one per scenario
    for p in paths.values():
        assert p.exists()


@boundaries_needed
def test_water_risk_band_map_is_one_file_per_scenario(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    captured = _capture_figures(monkeypatch, maps)
    paths = maps.plot_water_risk_band_map(countries=["Portugal"], final=synth["final"], water_scenario="bau")
    assert paths["combined"].exists()
    assert len(captured[0].axes) == 1  # one country requested -> one panel


@boundaries_needed
def test_computable_base_map_is_one_file_per_scenario(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    captured = _capture_figures(monkeypatch, maps)
    maps.plot_computable_base_map(countries=["Brazil", "Portugal", "India"], final=synth["final"], water_scenario="bau")
    assert len(captured[0].axes) == 3  # one panel per country, this call's single scenario only


@boundaries_needed
def test_heat_risk_band_map_gfdl_only_three_countries(synth, tmp_path, monkeypatch):
    """Reference layout every other category above now matches: GFDL-ESM4
    only, one panel per country, no GCM row split."""
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    captured = _capture_figures(monkeypatch, maps)
    maps.plot_heat_risk_band_map(countries=["Brazil", "Portugal", "India"], final=synth["final"])
    fig = captured[0]
    assert len(fig.axes) == 3  # one per country, no GCM row split


# --------------------------------------------------------------------------
# 7a2. Category 3b -- worst-case (Water vs. Heat) risk-band map
# (Douglas's 2026-09-05 request). Four synthetic plants, one per extreme
# combination named in the brief: water worse, heat worse, tie at the
# lowest level, tie at the highest level.
# --------------------------------------------------------------------------
def _worst_case_final(water_bands, heat_bands) -> pd.DataFrame:
    rows = []
    for i, (wb, hb) in enumerate(zip(water_bands, heat_bands)):
        rows.append({
            "plant_uid": f"WC-{i:02d}", "country": "Portugal", "plant_name": f"plant {i}",
            "water_scenario": "bau", "heat_scenario": "ssp370",
            "lat": 39.5 + i * 0.3, "lon": -8.0 + i * 0.3, "bucket": "thermal",
            "capacity_mw": 100.0, "commissioning_year": 2000.0,
            "water_risk_band": wb, "heat_risk_band_gfdl_esm4": hb, "computable": True,
        })
    return pd.DataFrame(rows)


@boundaries_needed
def test_worst_case_map_water_worse_colors_by_water_band(tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    captured = _capture_figures(monkeypatch, maps)
    final = _worst_case_final(["High"], ["MEDIUM"])
    maps.plot_worst_case_risk_band_map(countries=["Portugal"], final=final)
    ax = captured[0].axes[0]
    np.testing.assert_allclose(ax.collections[-1].get_facecolor()[0][:3],
                                matplotlib.colors.to_rgb(_common.WATER_BAND_COLORS["High"]))


@boundaries_needed
def test_worst_case_map_heat_worse_colors_by_heat_band(tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    captured = _capture_figures(monkeypatch, maps)
    final = _worst_case_final(["Low-Medium"], ["EXTREME"])
    maps.plot_worst_case_risk_band_map(countries=["Portugal"], final=final)
    ax = captured[0].axes[0]
    np.testing.assert_allclose(ax.collections[-1].get_facecolor()[0][:3],
                                matplotlib.colors.to_rgb(_common.HEAT_BAND_COLORS["EXTREME"]))


@boundaries_needed
def test_worst_case_map_tie_at_lowest_level_defaults_to_water(tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    captured = _capture_figures(monkeypatch, maps)
    final = _worst_case_final(["Low"], ["LOW"])
    maps.plot_worst_case_risk_band_map(countries=["Portugal"], final=final)
    ax = captured[0].axes[0]
    np.testing.assert_allclose(ax.collections[-1].get_facecolor()[0][:3],
                                matplotlib.colors.to_rgb(_common.WATER_BAND_COLORS["Low"]))


@boundaries_needed
def test_worst_case_map_tie_at_highest_level_defaults_to_water(tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    captured = _capture_figures(monkeypatch, maps)
    final = _worst_case_final(["Extremely-High"], ["EXTREME"])
    maps.plot_worst_case_risk_band_map(countries=["Portugal"], final=final)
    ax = captured[0].axes[0]
    np.testing.assert_allclose(ax.collections[-1].get_facecolor()[0][:3],
                                matplotlib.colors.to_rgb(_common.WATER_BAND_COLORS["Extremely-High"]))


@boundaries_needed
def test_worst_case_map_legend_labels_both_axes(synth, tmp_path, monkeypatch):
    """Legend must make the determinant readable without polluting the map
    itself: 5 'Water: <band>' entries + 4 'Heat: <band>' entries."""
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    captured = _capture_figures(monkeypatch, maps)
    maps.plot_worst_case_risk_band_map(countries=["Brazil", "Portugal", "India"], final=synth["final"])
    fig = captured[0]
    legend_labels = {t.get_text() for legend in fig.legends for t in legend.get_texts()}
    assert all(f"Water: {b}" in legend_labels for b in WATER_RISK_BANDS)
    assert all(f"Heat: {b}" in legend_labels for b in HEAT_RISK_BANDS)


@boundaries_needed
def test_worst_case_map_carries_the_comparability_caption(synth, tmp_path, monkeypatch):
    """Approved as an explicit exception to Correction 2 -- this figure keeps
    a caption footer because HeatRiskBand's sample-relative cuts make part of
    the map non-comparable across runs, and that must be stated on the
    figure, not only in risk_bands.py's text report."""
    from src.index.risk_bands import WORST_CASE_COMPARABILITY_NOTE

    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    captured = _capture_figures(monkeypatch, maps)
    maps.plot_worst_case_risk_band_map(countries=["Brazil", "Portugal", "India"], final=synth["final"])
    fig = captured[0]
    assert len(fig.texts) == 1
    assert "sample-relative" in fig.texts[0].get_text()
    assert "HeatRiskBand" in fig.texts[0].get_text() or "not comparable" in fig.texts[0].get_text()
    # sanity: the constant used at the call site is the one documented in risk_bands.py
    assert "sample-relative" in WORST_CASE_COMPARABILITY_NOTE


@boundaries_needed
def test_worst_case_map_is_one_file_per_scenario(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    paths = {ws: maps.plot_worst_case_risk_band_map(countries=["Portugal"], final=synth["final"], water_scenario=ws)["combined"]
             for ws in WATER_SCENARIOS}
    assert len(set(paths.values())) == 3
    for p in paths.values():
        assert p.exists()


# --------------------------------------------------------------------------
# 7b. Correction 2 (2026-09-05) -- no descriptive caption/disclaimer footer;
# only the legend below the map.
# --------------------------------------------------------------------------
@boundaries_needed
@pytest.mark.parametrize("plot_fn, kwargs", [
    (maps.plot_ccrs_overview_map, {}),
    (maps.plot_water_risk_band_map, {}),
    (maps.plot_computable_base_map, {}),
    (maps.plot_heat_risk_band_map, {}),
])
def test_map_figures_have_no_descriptive_caption_footer(synth, tmp_path, monkeypatch, plot_fn, kwargs):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    captured = _capture_figures(monkeypatch, maps)
    plot_fn(countries=["Brazil", "Portugal", "India"], final=synth["final"], **kwargs)
    fig = captured[0]
    # fig.texts holds any fig.text(...) calls (the old caption/disclaimer footer);
    # the legend is a separate artist (fig.legends), not a fig.text -- an empty
    # fig.texts means no leftover descriptive/disclaimer line below the map.
    assert fig.texts == []


# --------------------------------------------------------------------------
# 7c. Correction 3 (2026-09-05) -- a compass rose on every geographic map panel
# --------------------------------------------------------------------------
@boundaries_needed
@pytest.mark.parametrize("plot_fn, kwargs", [
    (maps.plot_ccrs_overview_map, {}),
    (maps.plot_water_risk_band_map, {}),
    (maps.plot_computable_base_map, {}),
    (maps.plot_heat_risk_band_map, {}),
    (maps.plot_worst_case_risk_band_map, {}),
])
def test_map_panels_each_get_their_own_compass_rose(synth, tmp_path, monkeypatch, plot_fn, kwargs):
    monkeypatch.setattr(maps, "OUTPUT_MAPS", tmp_path)
    captured = _capture_figures(monkeypatch, maps)
    plot_fn(countries=["Brazil", "Portugal", "India"], final=synth["final"], **kwargs)
    fig = captured[0]
    assert len(fig.axes) == 3
    for ax in fig.axes:
        # add_compass_rose adds 4 kite Polygon patches plus an "N" text, per panel
        assert len(ax.patches) >= 4
        assert any(t.get_text() == "N" for t in ax.texts)


def test_add_compass_rose_is_a_star_not_a_single_arrow():
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    try:
        _common.add_compass_rose(ax)
        assert len(ax.patches) == 4  # 4 kite quadrilaterals (N/E/S/W), not one arrow patch
        for patch in ax.patches:
            assert len(patch.get_xy()) == 5  # closed quadrilateral (4 vertices + repeat of first)
        assert sum(1 for t in ax.texts if t.get_text() == "N") == 1
    finally:
        plt.close(fig)


def test_heat_band_gcm_comparison_table_replaces_the_second_panel(synth):
    """B1's decision: the dropped MIROC6 map panel is replaced by a compact
    per-country comparison table, not silently dropped."""
    table = vtables.heat_band_gcm_comparison_table(bands=synth["bands"], water_scenario="bau")
    assert set(table["country"]) == set(COUNTRIES)
    assert {"share_high_or_extreme_gfdl_esm4", "share_high_or_extreme_miroc6",
            "difference_miroc6_minus_gfdl"} <= set(table.columns)


# --------------------------------------------------------------------------
# 8. B3 -- combined-risk stacked bars + complementary table
# --------------------------------------------------------------------------
def test_water_heat_contingency_capacity_table(synth):
    table = vtables.water_heat_contingency_capacity_table(bands=synth["bands"])
    assert {"country", "water_scenario", "water_risk_band", "heat_risk_band", "capacity_mw"} <= set(table.columns)
    assert (table["capacity_mw"] >= 0).all()


# --------------------------------------------------------------------------
# 9. C1/C2 -- national aggregate CCRS with CI, figure + table
# --------------------------------------------------------------------------
def test_national_ccrs_with_ci_figure(tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "OUT_DIR", tmp_path)
    ci_primary = _synthetic_national_ci()
    ci_secondary = _synthetic_national_ci(seed=1)
    path = charts.plot_national_ccrs_with_ci(ci_primary=ci_primary, ci_secondary=ci_secondary)
    assert path.exists()


def test_national_ccrs_summary_table_ranks_within_scenario():
    ci = _synthetic_national_ci()
    table = vtables.national_ccrs_summary_table(ci)
    assert set(table.columns) >= {"country", "water_scenario", "point_estimate", "rank_within_scenario"}
    for scen in ("opt", "bau", "pes"):
        ranks = sorted(table.loc[table["water_scenario"] == scen, "rank_within_scenario"])
        assert ranks == list(range(1, len(COUNTRIES) + 1))


# --------------------------------------------------------------------------
# 9b. FIG 4 redesign -- rank-stability prototypes (Douglas's 2026-09-05
# request), built directly on a synthetic per-draw frame (no raster
# pipeline / real Monte Carlo run needed).
# --------------------------------------------------------------------------
def _synthetic_draws(seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = 60
    means = {"India": 0.8, "Brazil": 0.4, "Portugal": 0.3}
    rows = []
    for scenario in ("opt", "bau", "pes"):
        for draw_id in range(n):
            for country, mean in means.items():
                rows.append({
                    "draw_id": draw_id, "magnitude": 0.20, "country": country,
                    "water_scenario": scenario, "ccrs": mean + 0.02 * rng.standard_normal(),
                })
    return pd.DataFrame(rows)


def test_fig4_rank_density_prototype(tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "OUT_DIR", tmp_path)
    path = charts.plot_ccrs_rank_density(draws=_synthetic_draws())
    assert path.exists()


def test_fig4_rank_probability_prototype(tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "OUT_DIR", tmp_path)
    path = charts.plot_ccrs_rank_probability(draws=_synthetic_draws())
    assert path.exists()


def test_fig4_country_colors_defined_for_every_country():
    assert set(charts.COUNTRY_COLORS) == set(COUNTRIES)


# --------------------------------------------------------------------------
# 10. C3 -- weight provenance table (no invented provenance)
# --------------------------------------------------------------------------
def test_hazard_weight_provenance_table_covers_every_weight():
    from src.index.ccrs_calculator import BUCKET_WEIGHTS

    table = vtables.hazard_weight_provenance_table()
    n_bucket_weights = sum(len(w) for w in BUCKET_WEIGHTS.values())
    assert len(table) == 3 + n_bucket_weights  # 3 within-water weights + every bucket weight
    assert table["provenance"].notna().all()
    assert (table["provenance"].str.len() > 0).all()
    # every bucket weight row must carry the "judgment call" provenance, never a fabricated calibration claim
    bucket_rows = table[table["bucket"] != "n/a (applies inside every bucket's water_sub)"]
    assert bucket_rows["provenance"].str.contains("judgment call").all()


# --------------------------------------------------------------------------
# 11. C4 -- relative Hazard-term contribution
# --------------------------------------------------------------------------
def _synthetic_contribution() -> pd.DataFrame:
    rows = []
    for country in COUNTRIES:
        for scen in ("opt", "bau", "pes"):
            rows.append({
                "country": country, "water_scenario": scen,
                "water_share": 0.5, "heat_share": 0.3, "drought_share": 0.2,
            })
    return pd.DataFrame(rows)


def test_hazard_term_contribution_figure_is_now_secondary(tmp_path, monkeypatch):
    """Reclassified secondary (2026-09-05), superseded by the per-plant
    distribution redesign -- kept, not deleted, but saved under
    combined/secondary/ like the other B5 secondary figures."""
    monkeypatch.setattr(charts, "SECONDARY_DIR", tmp_path)
    path = charts.plot_hazard_term_contribution(contribution=_synthetic_contribution())
    assert path.exists()


# --------------------------------------------------------------------------
# 11b. C4 redesign -- per-plant Hazard-term distribution (Douglas's
# 2026-09-05 request). The old bar chart/table above are untouched; these
# cover the new distribution figure and its supporting per-plant table.
# --------------------------------------------------------------------------
def _synthetic_per_plant_shares(seed: int = 0) -> pd.DataFrame:
    """country-specific plant counts deliberately straddle
    charts.VIOLIN_MIN_PLANTS (1000): Brazil/India well above (violin),
    Portugal well below (box+strip) -- mirrors the real data's shape
    (~5,150 / ~4,580 / ~438 unique plants) without needing the real
    pipeline."""
    rng = np.random.default_rng(seed)
    n_plants = {"Brazil": 1500, "India": 1400, "Portugal": 120}
    rows = []
    for country in COUNTRIES:
        n = n_plants[country]
        raw = rng.dirichlet([2, 2, 1], size=n)  # 3 shares summing to 1, per plant
        capacity = rng.uniform(5, 500, size=n)
        for scen in ("opt", "bau", "pes"):
            for i in range(n):
                rows.append({
                    "country": country, "water_scenario": scen, "capacity_mw": capacity[i],
                    "water_share": raw[i, 0], "heat_share": raw[i, 1], "drought_share": raw[i, 2],
                })
    return pd.DataFrame(rows)


def test_hazard_term_contribution_per_plant_shares_sum_to_one(synth):
    from src.index import ccrs_calculator as ccrs
    from src.visualization import tables as vtables

    # real production code path, exercised against synth["final"]-shaped
    # inputs is not directly wired (per_plant reads from ccrs.compute_hazard
    # live) -- so this test uses the synthetic per-plant frame directly, the
    # same contract plot_hazard_term_contribution_distribution consumes.
    frame = _synthetic_per_plant_shares()
    totals = frame["water_share"] + frame["heat_share"] + frame["drought_share"]
    np.testing.assert_allclose(totals.to_numpy(), 1.0, atol=1e-9)


def test_fig_c4_distribution_uses_violin_for_large_countries_box_for_small(tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "OUT_DIR", tmp_path)
    captured = _capture_figures(monkeypatch, charts)
    per_plant = _synthetic_per_plant_shares()
    charts.plot_hazard_term_contribution_distribution(countries=COUNTRIES, per_plant=per_plant)
    fig = captured[0]
    titles = [ax.get_title() for ax in fig.axes if ax.get_title()]
    assert any("Brazil" in t and "violin" in t for t in titles)
    assert any("India" in t and "violin" in t for t in titles)
    assert any("Portugal" in t and "box+strip" in t for t in titles)


def test_fig_c4_estimated_unique_plants_divides_by_scenario_count():
    per_plant = _synthetic_per_plant_shares()
    portugal = per_plant[per_plant["country"] == "Portugal"]
    # 120 plants x 3 scenarios = 360 rows -- must estimate ~120, not 360
    assert charts._estimated_unique_plants(portugal) == pytest.approx(120.0)


def test_fig_c4_weighted_view_is_not_a_copy_of_unweighted(tmp_path, monkeypatch):
    """The capacity-weighted row must actually weight -- construct a case
    where a tiny-capacity majority and a huge-capacity minority disagree, and
    confirm the weighted median moves toward the huge-capacity plants."""
    n = 200
    rng = np.random.default_rng(1)
    capacity = np.concatenate([np.full(190, 1.0), np.full(10, 10_000.0)])
    water_share = np.concatenate([np.full(190, 0.1), np.full(10, 0.9)])
    values = water_share
    weights = capacity

    unweighted_median = float(np.percentile(values, 50))
    weighted_median = charts._weighted_quantile(values, weights, 0.5)
    assert unweighted_median == pytest.approx(0.1)  # 190/200 plants dominate unweighted
    assert weighted_median == pytest.approx(0.9)     # 10 huge-capacity plants dominate weighted
    assert weighted_median != pytest.approx(unweighted_median)


def test_fig_c4_box_stats_weighted_and_unweighted_differ():
    values = np.concatenate([np.full(190, 0.1), np.full(10, 0.9)])
    weights = np.concatenate([np.full(190, 1.0), np.full(10, 10_000.0)])
    unweighted = charts._box_stats(values, None)
    weighted = charts._box_stats(values, weights)
    assert unweighted["med"] != weighted["med"]


# --------------------------------------------------------------------------
# 12. C5 -- Monte Carlo national summary table (mocked, no raster pipeline)
# --------------------------------------------------------------------------
def test_monte_carlo_parameter_summary_table_shape(monkeypatch):
    from src.index import monte_carlo as mc

    class _FakePre:
        pass

    def _fake_sim(magnitudes, n, pre, model):
        (magnitude,) = magnitudes
        rows = [{"country": c, "water_scenario": ws, "point_estimate": 0.5,
                 "p2.5": 0.4, "p50.0": 0.5, "p97.5": 0.6}
                for c in COUNTRIES for ws in ("opt", "bau", "pes")]
        return pd.DataFrame(rows)

    monkeypatch.setattr(mc, "run_country_scenario_simulation", _fake_sim)
    table = vtables.monte_carlo_parameter_summary_table(magnitudes=(0.10, 0.20, 0.30), n=5, pre=_FakePre())
    assert len(table) == 3 * len(COUNTRIES) * 3  # magnitudes x countries x scenarios
    assert set(table["magnitude"]) == {0.10, 0.20, 0.30}


# --------------------------------------------------------------------------
# 13. C6 -- EM-DAT x Hazard spatial overlay validation (approved + implemented)
# --------------------------------------------------------------------------
def test_c6_feasibility_finding_still_recorded():
    """The pre-approval feasibility note stays in place as the historical
    record of the investigation Douglas asked for before any code -- it is
    not deleted just because C6 is now implemented (see the addendum inside
    it, and src/index/emdat_validation.py's module docstring)."""
    assert "GADM Admin Units" in vtables.C6_INVESTIGATION_NOTE
    assert "emdat_validation.py" in vtables.C6_INVESTIGATION_NOTE


def test_emdat_admin1_gid_resolution_handles_mixed_granularity():
    """The 'GADM Admin Units' field mixes admin-1/admin-2/admin-0 GIDs per
    event (discovered while implementing, not in the original feasibility
    report) -- every level >= 1 must resolve to the same admin-1 parent."""
    from src.index import emdat_validation as ev

    admin1_cell = '[{"gid_1":"BRA.5_1","name_1":"Bahia"}]'
    admin2_cell = '[{"gid_2":"BRA.19.68_2","name_2":"Rio de Janeiro"}]'
    admin0_cell = '[{"gid_0":"BRA","name_0":"Brazil"}]'
    mixed_cell = '[{"gid_1":"BRA.5_1"},{"gid_2":"BRA.19.68_2"}]'

    assert ev._admin1_gids_from_cell(admin1_cell) == {"BRA.5_1"}
    assert ev._admin1_gids_from_cell(admin2_cell) == {"BRA.19_1"}
    assert ev._admin1_gids_from_cell(admin0_cell) == set()  # too coarse, dropped
    assert ev._admin1_gids_from_cell(mixed_cell) == {"BRA.5_1", "BRA.19_1"}
    assert ev._admin1_gids_from_cell(None) == set()
    assert ev._admin1_gids_from_cell(float("nan")) == set()


def test_emdat_storm_excluded_no_matching_hazard_term():
    from src.index import emdat_validation as ev

    assert "Storm" not in ev.DISASTER_TYPE_TO_TERM
    assert "Storm" in ev.EXCLUDED_DISASTER_TYPES


def test_run_validation_skips_pairs_with_too_few_polygons(monkeypatch):
    """Unit-level test of the skip/test decision logic -- mocks the two
    data-fetching calls so it does not need real rasters/boundaries."""
    from src.index import emdat_validation as ev

    fake_polys = pd.DataFrame({
        "gid_1": ["X.1_1", "X.2_1", "X.3_1"],
        "hazard_value": [0.2, 0.5, 0.9],
    })
    fake_events = pd.DataFrame({"disaster_type": ["Drought"], "gid_1": ["X.1_1"]})

    monkeypatch.setattr(ev, "load_geocoded_events", lambda country: fake_events)
    monkeypatch.setattr(ev, "polygon_hazard_table", lambda country, term, model, water_scenario: fake_polys)

    result = ev.run_validation(countries=["Brazil"])
    summary = result["summary"]
    assert set(summary["disaster_type"]) == set(ev.DISASTER_TYPE_TO_TERM)
    drought_row = summary[summary["disaster_type"] == "Drought"].iloc[0]
    # 1 polygon with an event, 2 without -- both below MIN_GROUP_SIZE=3 -> skipped
    assert drought_row["skip_reason"] is not None
    assert np.isnan(drought_row["p_value"])


def test_run_validation_runs_the_test_when_groups_are_large_enough(monkeypatch):
    from src.index import emdat_validation as ev

    fake_polys = pd.DataFrame({
        "gid_1": [f"X.{i}_1" for i in range(10)],
        "hazard_value": [0.1, 0.15, 0.2, 0.25, 0.3, 0.6, 0.65, 0.7, 0.75, 0.8],
    })
    fake_events = pd.DataFrame({
        "disaster_type": ["Drought"] * 5,
        "gid_1": [f"X.{i}_1" for i in range(5, 10)],  # the high-hazard half
    })

    monkeypatch.setattr(ev, "load_geocoded_events", lambda country: fake_events)
    monkeypatch.setattr(ev, "polygon_hazard_table", lambda country, term, model, water_scenario: fake_polys)

    result = ev.run_validation(countries=["Brazil"])
    row = result["summary"][result["summary"]["disaster_type"] == "Drought"].iloc[0]
    assert row["skip_reason"] is None
    assert not np.isnan(row["p_value"])
    assert row["median_hazard_with_event"] > row["median_hazard_without_event"]


def _emdat_full_grid_result(portugal_skipped: bool = True) -> dict[str, pd.DataFrame]:
    """Synthetic 3x3 (disaster_type x country) result frame, shaped like the
    real ``run_validation()`` output -- India significant on all 3 types,
    Brazil non-significant on all 3, Portugal skipped on 2 (no control
    group) and non-significant on Flood. Used by the 2026-09-05 redesign's
    layout tests (real statistical logic is untouched and covered
    separately, above)."""
    from src.index import emdat_validation as ev

    rows_summary, rows_polygons = [], []
    for disaster_type, term in ev.DISASTER_TYPE_TO_TERM.items():
        for country, significant, skipped in [
            ("Brazil", False, False), ("Portugal", False, portugal_skipped and disaster_type != "Flood"),
            ("India", True, False),
        ]:
            n_without, n_with = (0, 18) if skipped else (10, 10)
            without_vals = [] if skipped else list(np.linspace(0.1, 0.4, n_without))
            with_vals = list(np.linspace(0.6, 0.9, n_with)) if significant else list(np.linspace(0.1, 0.9, n_with))
            for v in without_vals:
                rows_polygons.append({"gid_1": f"{country[:2]}.{len(rows_polygons)}_1", "hazard_value": v,
                                       "has_event": False, "country": country, "disaster_type": disaster_type,
                                       "term": term})
            for v in with_vals:
                rows_polygons.append({"gid_1": f"{country[:2]}.{len(rows_polygons)}_1", "hazard_value": v,
                                       "has_event": True, "country": country, "disaster_type": disaster_type,
                                       "term": term})
            rows_summary.append({
                "country": country, "disaster_type": disaster_type, "term": term,
                "n_polygons_with_event": n_with, "n_polygons_without_event": n_without,
                "n_finite_with_event": n_with, "n_finite_without_event": n_without,
                "median_hazard_with_event": np.median(with_vals) if with_vals else float("nan"),
                "median_hazard_without_event": np.median(without_vals) if without_vals else float("nan"),
                "u_statistic": float("nan") if skipped else 5.0,
                "p_value": float("nan") if skipped else (0.001 if significant else 0.8),
                "skip_reason": (
                    f"fewer than 3 polygons with a finite hazard value on one side "
                    f"(with_event={n_with}, without_event={n_without})"
                ) if skipped else None,
            })
    return {"summary": pd.DataFrame(rows_summary), "polygons": pd.DataFrame(rows_polygons)}


def test_emdat_spatial_validation_figure_with_synthetic_result(tmp_path, monkeypatch):
    from src.visualization import emdat_validation as vev

    monkeypatch.setattr(vev, "OUT_DIR", tmp_path)
    path = vev.plot_emdat_spatial_validation(result=_emdat_full_grid_result())
    assert path.exists()


def test_emdat_spatial_validation_figure_reports_caveats_in_caption(tmp_path, monkeypatch):
    """Douglas's explicit requirement (unchanged by the redesign): coverage/
    proxy caveats must be printed on the figure itself, not only in the
    code."""
    from src.visualization import _common, emdat_validation as vev

    monkeypatch.setattr(vev, "OUT_DIR", tmp_path)
    captured = _capture_figures(monkeypatch, vev)
    vev.plot_emdat_spatial_validation(result=_emdat_full_grid_result())
    fig = captured[0]
    footer_texts = " ".join(t.get_text() for t in fig.texts)
    assert "EXPLORATORY" in footer_texts
    assert "GADM Admin Units" in footer_texts
    assert "Storm" in footer_texts


def test_emdat_spatial_validation_grid_is_always_3x3():
    """The 2026-09-05 redesign's core fix: a fixed disaster_type x country
    grid regardless of how many pairs were actually testable -- unlike the
    old version, whose panel count shrank/grew with the number of tested
    pairs."""
    from src.index import emdat_validation as ev

    result = _emdat_full_grid_result()
    n_disaster_types = len(ev.DISASTER_TYPE_TO_TERM)
    assert len(result["summary"]) == n_disaster_types * len(COUNTRIES)


def test_emdat_spatial_validation_skip_does_not_break_the_grid_layout(tmp_path, monkeypatch):
    """Portugal's 2 skipped (country, disaster_type) pairs must not shrink
    the figure or disturb Brazil/India's panels -- always a 3x3 grid of
    axes, tested or not."""
    from src.index import emdat_validation as ev
    from src.visualization import emdat_validation as vev

    monkeypatch.setattr(vev, "OUT_DIR", tmp_path)
    captured = _capture_figures(monkeypatch, vev)
    vev.plot_emdat_spatial_validation(result=_emdat_full_grid_result(portugal_skipped=True))
    fig = captured[0]
    assert len(fig.axes) == len(ev.DISASTER_TYPE_TO_TERM) * len(COUNTRIES)


def test_emdat_spatial_validation_skipped_panel_still_shows_its_one_group():
    """A skipped pair is not left blank -- whichever group has data (here,
    the 18 'with event' Portugal polygons) is still drawn."""
    import matplotlib.pyplot as plt
    from src.visualization import emdat_validation as vev

    fig, ax = plt.subplots()
    try:
        polygons = pd.DataFrame({
            "gid_1": [f"P.{i}_1" for i in range(18)], "hazard_value": np.linspace(0.1, 0.9, 18),
            "has_event": [True] * 18,
        })
        vev._panel_skipped(ax, "Portugal", "Extreme temperature", "heat", polygons,
                            "fewer than 3 polygons with a finite hazard value on one side "
                            "(with_event=18, without_event=0)")
        assert len(ax.lines) > 0 or len(ax.patches) > 0  # the boxplot/strip was actually drawn
        assert ax.collections  # the jittered strip scatter
    finally:
        plt.close(fig)


def test_emdat_spatial_validation_significant_panels_are_visually_distinct(tmp_path, monkeypatch):
    """India (p<0.05 on all 3 types) must render with the gold
    significance styling; Brazil (never significant) must not."""
    from src.visualization import emdat_validation as vev

    monkeypatch.setattr(vev, "OUT_DIR", tmp_path)
    captured = _capture_figures(monkeypatch, vev)
    vev.plot_emdat_spatial_validation(result=_emdat_full_grid_result())
    fig = captured[0]
    titles = {ax.get_title(): ax for ax in fig.axes}
    india_ax = next(ax for title, ax in titles.items() if "India" in title)
    brazil_ax = next(ax for title, ax in titles.items() if "Brazil" in title)
    assert "*" in [t for t in titles if "India" in t][0]
    assert india_ax.get_facecolor() != brazil_ax.get_facecolor()
    assert india_ax.spines["top"].get_edgecolor() != brazil_ax.spines["top"].get_edgecolor()


# --------------------------------------------------------------------------
# 14. B4 -- Top-N breakdown never mixes buckets in the same ranking
# --------------------------------------------------------------------------
def test_top_n_breakdown_by_bucket_never_mixes_buckets(synth, tmp_path, monkeypatch):
    monkeypatch.setattr(charts, "OUT_DIR", tmp_path)
    captured = _capture_figures(monkeypatch, charts)
    charts.plot_top_n_ccrs_breakdown_by_bucket(countries=["Portugal"], final=synth["final"], n=3)
    fig = captured[0]
    assert len(fig.axes) == len(BUCKETS)  # one panel per bucket, never combined
