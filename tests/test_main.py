"""
Wiring tests for the pipeline orchestrator (``src/main.py``).

These do NOT exercise the real computation -- every heavy internal function
is replaced with a spy that records its calls and returns a light synthetic
stand-in. The point is the orchestration contract:

* each dependency step (T1 per GCM, T2, T3, T4 per GCM, T5) runs exactly once;
* ``monte_carlo._Precomputed`` is built exactly once;
* the one ``_Precomputed`` instance and the one per-draw frame are passed *by
  reference* to every Monte Carlo consumer (the rank-stability figures, the
  C5 magnitude table, and the C1/C2 national summary), never recomputed.

Spies sit on the internal functions, never on the module CLIs.
"""

from __future__ import annotations

import pandas as pd
import pytest

from src import main
from src.index import ccrs_calculator as ccrs


class Spy:
    def __init__(self, name: str, ret=None):
        self.name = name
        self.calls: list[tuple[tuple, dict]] = []
        self._ret = ret

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if callable(self._ret):
            return self._ret(*args, **kwargs)
        return self._ret

    @property
    def n(self) -> int:
        return len(self.calls)


class FakePre:
    """Stand-in for monte_carlo._Precomputed -- identity is all that matters."""


class FakeBand:
    """Stand-in for risk_bands.BandTable (only ``.frame`` is read here)."""
    frame = pd.DataFrame({"plant_uid": ["A"], "water_scenario": ["opt"]})


def _hazard_df():
    return pd.DataFrame({
        "plant_uid": ["A", "B"], "country": ["Brazil", "India"],
        "water_scenario": ["opt", "opt"], "commissioning_year": [2000.0, None],
    })


def _final_df():
    return pd.DataFrame({
        "plant_uid": ["A", "B"], "country": ["Brazil", "India"],
        "water_scenario": ["opt", "opt"], "commissioning_year": [2000.0, None],
        "ccrs_gfdl_esm4": [0.3, 0.9],
    })


def _draws_df():
    return pd.DataFrame({
        "draw_id": [0, 1, 0, 1],
        "country": ["Brazil", "Brazil", "India", "India"],
        "water_scenario": ["opt", "opt", "opt", "opt"],
        "ccrs": [0.10, 0.20, 0.50, 0.60],
    })


@pytest.fixture
def spies(monkeypatch, tmp_path):
    reg: dict[str, Spy] = {}

    def patch(target_mod, attr, ret=None):
        s = Spy(attr, ret)
        monkeypatch.setattr(target_mod, attr, s)
        reg[attr] = s
        return s

    # never let a default out_dir / figure dir point at the real data/outputs/
    monkeypatch.setattr(main, "OUTPUT_TABLES", tmp_path)
    monkeypatch.setattr(main.maps, "OUTPUT_MAPS", tmp_path)

    # --- steps that must not touch disk / network ---
    patch(main, "emdat_inspection", pd.DataFrame({"country": ["Brazil"], "n_events": [1]}))
    patch(main, "processed_rasters_stale", [])          # -> processors skipped
    patch(main, "run_processors", None)
    patch(main, "_write_csv", None)
    monkeypatch.setattr(main.Path, "write_text", lambda self, *a, **k: None)

    # --- T1 / T2 / T3 / T4 / T5 internals ---
    patch(main.ccrs, "compute_hazard", lambda m, **k: _hazard_df())
    patch(main.ccrs, "compute_hazard_by_gcm", lambda **k: _hazard_df())
    patch(main.agef, "compute_age_factors", pd.DataFrame({"plant_uid": ["A", "B"]}))
    patch(main.agef, "build_summary", "")
    patch(main.evm, "compute_event_multipliers", pd.DataFrame({"country": ["Brazil"]}))
    patch(main.risk_bands, "compute_bands", lambda m: FakeBand())
    patch(main.risk_bands, "build_summary", "")
    patch(main.ccrs_report, "assemble_ccrs", lambda *a, **k: _final_df())
    patch(main.ccrs_report, "attach_risk_bands", lambda *a, **k: _final_df())
    patch(main.ccrs_report, "compute_water_band_shares", pd.DataFrame())
    patch(main.ccrs_report, "compute_heat_band_shares", pd.DataFrame())
    patch(main.ccrs_report, "build_summary", "")

    # --- Monte Carlo: one _Precomputed, shared ---
    the_pre = FakePre()
    patch(main.mc, "_Precomputed", lambda **k: the_pre)
    reg["_the_pre"] = the_pre  # type: ignore[assignment]
    patch(main.mc, "run_simulation", {"water": pd.DataFrame(), "heat": pd.DataFrame()})
    patch(main.mc, "assert_structural_constants_untouched", None)
    the_draws = _draws_df()
    patch(main.mc, "run_country_scenario_draws", the_draws)
    reg["_the_draws"] = the_draws  # type: ignore[assignment]

    # --- consumers of the shared Monte Carlo objects ---
    patch(main.charts, "plot_ccrs_rank_stability", None)
    patch(main.charts, "plot_figure7_montecarlo_stability_pes", None)
    patch(main.vtables, "monte_carlo_parameter_summary_table", pd.DataFrame())
    patch(main.vtables, "national_ccrs_summary_table", pd.DataFrame())

    # --- every other figure / table function: harmless no-op spies ---
    for mod, names in {
        main.diagrams: ["plot_pipeline_overview"],
        main.maps: [
            "plot_figure5_ccrs_overview", "plot_water_risk_band_map", "plot_computable_base_map",
            "plot_heat_risk_band_map", "plot_worst_case_risk_band_map",
            "plot_ccrs_asset_level_pes_map", "plot_ccrs_scenario_delta_map",
        ],
        main.charts: [
            "plot_figure2_capacity_exposure_by_band", "plot_capacity_by_risk_band",
            "plot_age_factor_by_bucket", "plot_water_heat_combined_risk_bars",
            "plot_top_n_ccrs_breakdown_by_bucket", "plot_ccrs_distribution_by_bucket",
            "plot_figure6_technology_age_vulnerability_pes",
            "plot_hazard_term_contribution_distribution", "plot_hazard_term_contribution",
        ],
        main.vtables: [
            "heat_band_gcm_comparison_table", "water_heat_contingency_capacity_table",
            "hazard_weight_provenance_table", "hazard_term_contribution_per_plant",
            "hazard_term_contribution_table", "event_multiplier_table",
        ],
        main.emv: ["run_validation"],
        main.emv_viz: ["plot_emdat_spatial_validation"],
    }.items():
        for nm in names:
            patch(mod, nm, pd.DataFrame() if nm.endswith("table") else None)

    # run_validation must return the dict shape the writer/plotter expect
    reg["run_validation"]._ret = {"summary": pd.DataFrame(), "polygons": pd.DataFrame()}
    reg["hazard_term_contribution_per_plant"]._ret = pd.DataFrame()
    reg["hazard_term_contribution_table"]._ret = pd.DataFrame()
    return reg


def test_each_dependency_step_runs_exactly_once(spies):
    main.run_pipeline(skip_processors=True)

    n_models = len(ccrs.configured_models())
    assert spies["compute_hazard"].n == n_models          # T1, once per GCM
    assert spies["compute_hazard_by_gcm"].n == 1
    assert spies["compute_age_factors"].n == 1            # T2
    assert spies["compute_event_multipliers"].n == 1      # T3
    assert spies["compute_bands"].n == n_models           # T4, once per GCM
    assert spies["assemble_ccrs"].n == 1                  # T5
    assert spies["attach_risk_bands"].n == 1


def test_monte_carlo_precomputed_built_once_and_shared(spies):
    main.run_pipeline(skip_processors=True)

    assert spies["_Precomputed"].n == 1, "the expensive Monte Carlo precompute must be built once"
    assert spies["run_country_scenario_draws"].n == 1, "the per-draw frame must be produced once"

    the_pre = spies["_the_pre"]

    # consumer 1: the rank-stability figures -- same pre AND same draws object
    rs_kwargs = spies["plot_ccrs_rank_stability"].calls[0][1]
    f7_kwargs = spies["plot_figure7_montecarlo_stability_pes"].calls[0][1]
    assert rs_kwargs["pre"] is the_pre
    assert f7_kwargs["pre"] is the_pre
    assert rs_kwargs["draws"] is f7_kwargs["draws"], "both figures must share one draws frame"
    assert rs_kwargs["draws"] is spies["_the_draws"]

    # consumer 2: the C5 magnitude table -- same pre, no re-simulation
    c5_kwargs = spies["monte_carlo_parameter_summary_table"].calls[0][1]
    assert c5_kwargs["pre"] is the_pre

    # consumer 3: the C1/C2 national summary -- fed the CI derived from the
    # SAME draws frame, never a second run_country_scenario_simulation
    (ci_arg,), _ = spies["national_ccrs_summary_table"].calls[0]
    assert list(ci_arg.columns) == ["country", "water_scenario", "point_estimate", "p2.5", "p50.0", "p97.5"]
    assert set(ci_arg["country"]) == {"Brazil", "India"}


def test_run_simulation_is_once_per_magnitude_not_more(spies):
    main.run_pipeline(skip_processors=True)
    assert spies["run_simulation"].n == len(main.mc.MAGNITUDES)


def test_figure_loops_have_the_right_cardinality(spies):
    """Scenario-swept maps run once per water scenario; the heat-band map is
    primary-GCM only (never once per GCM -- its filename carries no GCM, so a
    per-GCM loop would silently overwrite). GCM-suffixed charts run per GCM."""
    from src.index.ccrs_calculator import WATER_SCENARIOS

    main.run_pipeline(skip_processors=True)
    n_scen, n_models = len(WATER_SCENARIOS), len(ccrs.configured_models())

    assert spies["plot_water_risk_band_map"].n == n_scen
    assert spies["plot_heat_risk_band_map"].n == n_scen       # NOT n_scen * n_models
    assert spies["plot_computable_base_map"].n == n_scen
    assert spies["plot_top_n_ccrs_breakdown_by_bucket"].n == n_models
    assert spies["plot_ccrs_rank_stability"].n == 1


def test_skip_montecarlo_skips_every_monte_carlo_consumer(spies):
    main.run_pipeline(skip_processors=True, skip_montecarlo=True)

    assert spies["_Precomputed"].n == 0
    assert spies["run_country_scenario_draws"].n == 0
    assert spies["run_simulation"].n == 0
    assert spies["plot_ccrs_rank_stability"].n == 0
    assert spies["monte_carlo_parameter_summary_table"].n == 0
    assert spies["national_ccrs_summary_table"].n == 0
    # non-Monte-Carlo figures still run
    assert spies["plot_pipeline_overview"].n == 1
    assert spies["plot_water_risk_band_map"].n >= 1


def test_skip_flags_gate_their_phases(spies):
    main.run_pipeline(skip_processors=True, skip_tables=True, skip_figures=True)
    assert spies["assemble_ccrs"].n == 1              # index layer still runs
    assert spies["heat_band_gcm_comparison_table"].n == 0
    assert spies["plot_pipeline_overview"].n == 0
    assert spies["run_validation"].n == 0


def test_ci_from_draws_matches_monte_carlo_percentiles():
    """ci_from_draws must reproduce monte_carlo.percentile_ci group by group,
    so the C1/C2 consumer is numerically identical to a real
    run_country_scenario_simulation over the same draws."""
    draws = _draws_df()
    ci = main.ci_from_draws(draws)
    brazil = ci[ci["country"] == "Brazil"].iloc[0]
    ref = main.mc.percentile_ci([0.10, 0.20])
    assert brazil["p2.5"] == pytest.approx(ref[2.5])
    assert brazil["point_estimate"] == pytest.approx(ref[50.0])
    assert brazil["p97.5"] == pytest.approx(ref[97.5])
