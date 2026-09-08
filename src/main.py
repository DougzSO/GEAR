"""
GEAR pipeline orchestrator -- one entry point that runs the whole chain in
dependency order without recomputing anything two steps share.

    python -m src.main [flags]

Runs, in order:

    EM-DAT inspection  -> verify the per-country EM-DAT event CSVs T3 needs
    Climate processors -> only if the processed rasters are missing or stale
    T1  ccrs_calculator.compute_hazard        (per GCM, once)
    T2  age_factor.compute_age_factors        (independent of T3)
    T3  event_multiplier.compute_event_multipliers
    T4  risk_bands.compute_bands              (per GCM, once)
    T5  ccrs_report.assemble_ccrs + attach_risk_bands + capacity-share tables
    Monte Carlo   -> one shared monte_carlo._Precomputed, reused everywhere
    Tables        -> src/visualization/tables.py's CSV outputs
    Figures       -> every src/visualization figure (maps, charts, Figure 1)
    EM-DAT spatial validation -> src/index/emdat_validation + its box/strip figure

Why an orchestrator, not seven ``python -m`` calls: each module's ``main()``
recomputes its own inputs. Called separately, ``age_factor`` / ``event_
multiplier`` / ``risk_bands`` run ~4 times over, and ``monte_carlo._Precomputed``
(the expensive per-raster Hazard + band rebuild) is built three times -- once
in ``monte_carlo.main()``, once in ``tables.main()``, once inside the
rank-stability figure. This module computes each dependency exactly once and
threads the in-memory objects through every consumer via the optional
``*=None`` parameters those functions already expose (plus three small
injection hooks added for this: ``ccrs_calculator.compute_hazard_by_gcm(
frames_by_model=...)``, ``monte_carlo._Precomputed(hazard_by_model=...,
band_tables=...)``, ``tables.hazard_term_contribution_per_plant(hazard=...)``).

Every module keeps its own ``main()`` for isolated runs / debugging -- this
orchestrator calls the internal functions directly, never the CLIs, so there
is no redundant disk I/O between steps.

Scope flags (``--countries`` / ``--scenarios``) narrow only the *figure and
table* generation loops -- the index layer (T1-T5) and Monte Carlo always run
full-scope, because the sample-relative HeatRiskBand cuts, the global term
bounds and ``EventMultiplier``'s ``rate_max`` are only correct over all three
countries and all three scenarios.
"""

from __future__ import annotations

import argparse
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src import config
from src.config import COUNTRIES, OUTPUT_TABLES
from src.downloaders.cds_tasmax_downloader import configured_models, resampled_raster_path
from src.index import age_factor as agef
from src.index import ccrs_calculator as ccrs
from src.index import ccrs_report
from src.index import emdat_validation as emv
from src.index import event_multiplier as evm
from src.index import monte_carlo as mc
from src.index import risk_bands
from src.index.ccrs_calculator import WATER_SCENARIOS
from src.processors import heat_stress_processor as heatp
from src.processors import spei_processor as speip
from src.processors import water_stress_processor as wsp
from src.processors import water_variability_processor as wvp
from src.processors._common import _find_aqueduct_csv
from src.visualization import charts, diagrams, maps
from src.visualization import emdat_validation as emv_viz
from src.visualization import tables as vtables

logger = logging.getLogger("src.main")


# --------------------------------------------------------------------------
# Progress / timing log
# --------------------------------------------------------------------------
@dataclass
class StepTimer:
    steps: list[tuple[str, float, str]] = field(default_factory=list)
    _t0: float = field(default_factory=time.perf_counter)

    def _elapsed(self) -> str:
        s = int(time.perf_counter() - self._t0)
        return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"

    @contextmanager
    def step(self, label: str):
        logger.info("[%s] %s ...", self._elapsed(), label)
        t = time.perf_counter()
        outcome = "done"
        try:
            yield
        finally:
            dt = time.perf_counter() - t
            self.steps.append((label, dt, outcome))
            logger.info("[%s] %s -- %s in %.1fs", self._elapsed(), label, outcome, dt)

    def skipped(self, label: str, why: str) -> None:
        self.steps.append((label, 0.0, f"skipped ({why})"))
        logger.info("[%s] %s -- skipped (%s)", self._elapsed(), label, why)

    def summary(self) -> str:
        total = sum(dt for _, dt, _ in self.steps)
        width = max((len(lbl) for lbl, _, _ in self.steps), default=0)
        lines = ["", "=" * (width + 26), f"Pipeline finished in {self._elapsed()} ({total:.0f}s of work)"]
        for label, dt, outcome in self.steps:
            note = "" if outcome == "done" else f"  [{outcome}]"
            lines.append(f"  {label:<{width}}  {dt:8.1f}s{note}")
        lines.append("=" * (width + 26))
        return "\n".join(lines)


# --------------------------------------------------------------------------
# Processor staleness -- run the climate processors only if a processed
# raster is missing or older than an input it derives from
# --------------------------------------------------------------------------
def _aqueduct_csv_or_none(country: str) -> Path | None:
    try:
        return _find_aqueduct_csv(country)
    except FileNotFoundError:
        return None


def processed_rasters_stale(models: list[str]) -> list[str]:
    """Reasons the processed climate rasters need regenerating -- an empty
    list means they are all present and newer than their inputs. Always
    checks the full country/scenario matrix (a partial ``--scenarios`` run is
    for figure iteration, not a reason to treat the processor layer as
    complete)."""
    cmip6 = list(config.CMIP6_SCENARIOS)
    aqueduct = list(config.AQUEDUCT_SCENARIOS)
    checks: list[tuple[str, Path | None, Path]] = []

    for country in COUNTRIES:
        for model in models:
            for scen in cmip6:
                heat_in = resampled_raster_path(country, model, scen)
                checks.append((f"heat {country}/{model}/{scen}", heat_in,
                               heatp.normalized_raster_path(country, model, scen)))
                checks.append((f"spei-raw {country}/{model}/{scen}", None,
                               speip.raw_raster_path(country, model, scen)))
                checks.append((f"spei {country}/{model}/{scen}", None,
                               speip.normalized_raster_path(country, model, scen)))
        aq = _aqueduct_csv_or_none(country)
        for scen in aqueduct:
            checks.append((f"water-stress {country}/{scen}", aq,
                           wsp.normalized_raster_path(country, scen)))
            for indicator in wvp.INDICATORS:
                checks.append((f"water-var {country}/{scen}/{indicator}", aq,
                               wvp.normalized_raster_path(country, scen, indicator)))

    reasons: list[str] = []
    for label, src, out in checks:
        if not out.exists():
            reasons.append(f"{label}: {out.name} missing")
        elif src is not None and src.exists() and src.stat().st_mtime > out.stat().st_mtime:
            reasons.append(f"{label}: input {src.name} is newer than {out.name}")
    return reasons


def run_processors(force: bool) -> None:
    """heat first (its 1 km grid is the reference every other layer stacks
    onto), then the two Aqueduct layers, then SPEI. Each processor already
    skips a raster whose output exists unless ``overwrite``."""
    heatp.process_all_countries(overwrite=force)
    wsp.process_all_countries(overwrite=force)
    wvp.process_all_countries(overwrite=force)
    speip.process_all_countries(overwrite=force)


# --------------------------------------------------------------------------
# EM-DAT inspection -- what T3 (EventMultiplier) consumes
# --------------------------------------------------------------------------
def emdat_inspection() -> pd.DataFrame:
    from src.downloaders import emdat_downloader

    missing = [c for c in COUNTRIES if not emdat_downloader.country_csv_path(c).exists()]
    if missing:
        raise FileNotFoundError(
            f"EM-DAT country CSV(s) missing for {missing}. Run "
            f"`python -m src.downloaders.emdat_downloader` first "
            f"(the orchestrator does not trigger network downloads)."
        )
    counts = evm.load_event_counts(list(COUNTRIES))
    for r in counts.itertuples(index=False):
        logger.info("EM-DAT %s: %d climate-relevant events", r.country, r.n_events)
    return counts


# --------------------------------------------------------------------------
# Derive the national CI frame from the per-draw frame -- avoids a second
# full run_country_scenario_simulation over the same draws
# --------------------------------------------------------------------------
def ci_from_draws(draws: pd.DataFrame) -> pd.DataFrame:
    """Reproduce ``monte_carlo.run_country_scenario_simulation``'s output
    (columns ``country, water_scenario, point_estimate, p2.5, p50.0,
    p97.5``) from ``run_country_scenario_draws``'s per-draw frame -- the two
    build the identical ``(n_draws, n_groups)`` matrix, so the percentiles of
    the raw ``ccrs`` column per (country, water_scenario) group match
    ``_draws_to_ci_frame`` exactly. Keeps the C1/C2 consumer on the same
    Monte Carlo object as the figures instead of re-simulating."""
    rows = []
    for (country, scenario), g in draws.groupby(["country", "water_scenario"], sort=True):
        v = g["ccrs"].to_numpy("float64")
        v = v[~pd.isna(v)]
        ci = mc.percentile_ci(v)
        rows.append({
            "country": country, "water_scenario": scenario,
            "point_estimate": ci[50.0],
            "p2.5": ci[2.5], "p50.0": ci[50.0], "p97.5": ci[97.5],
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# Output helpers
# --------------------------------------------------------------------------
def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)
    logger.info("wrote %s (%d rows)", path.name, len(frame))


# --------------------------------------------------------------------------
# The pipeline
# --------------------------------------------------------------------------
def run_pipeline(
    countries: list[str] | None = None,
    water_scenarios: list[str] | None = None,
    *,
    skip_processors: bool = False,
    force_processors: bool = False,
    skip_montecarlo: bool = False,
    skip_tables: bool = False,
    skip_figures: bool = False,
    out_dir: Path | None = None,
    mc_iterations: int | None = None,
) -> dict:
    """Run the whole pipeline. Returns a dict of the key in-memory objects
    (for tests / notebooks). ``countries`` / ``water_scenarios`` restrict the
    figure and table loops only."""
    fig_countries = list(countries or COUNTRIES)
    fig_scenarios = list(water_scenarios or WATER_SCENARIOS)
    models = list(configured_models())
    out_dir = Path(out_dir) if out_dir is not None else OUTPUT_TABLES
    n_iter = mc_iterations or mc.N_ITERATIONS
    timer = StepTimer()
    result: dict = {}

    with timer.step("EM-DAT inspection"):
        result["emdat_counts"] = emdat_inspection()

    if skip_processors:
        timer.skipped("Climate processors", "--skip-processors")
    else:
        reasons = [] if force_processors else processed_rasters_stale(models)
        if force_processors or reasons:
            with timer.step("Climate processors"):
                if reasons:
                    logger.info("regenerating: %d stale/missing (e.g. %s)", len(reasons), reasons[0])
                run_processors(force=force_processors)
        else:
            timer.skipped("Climate processors", "processed rasters current")

    with timer.step("T1 -- Hazard (ccrs_calculator)"):
        hazard_by_model = {m: ccrs.compute_hazard(m) for m in models}
        hazard_wide = ccrs.compute_hazard_by_gcm(models=models, frames_by_model=hazard_by_model)
        result["hazard_by_model"] = hazard_by_model
        _write_csv(hazard_wide, out_dir / "ccrs_hazard.csv")

    with timer.step("T2 -- age_factor"):
        age_factors = agef.compute_age_factors()
        result["age_factors"] = age_factors
        _write_csv(age_factors, out_dir / "ccrs_age_factors.csv")
        (out_dir / "age_factor_report.md").write_text(agef.build_summary(age_factors), encoding="utf-8")

    with timer.step("T3 -- EventMultiplier"):
        event_multipliers = evm.compute_event_multipliers(list(COUNTRIES))
        result["event_multipliers"] = event_multipliers
        _write_csv(event_multipliers, out_dir / "ccrs_event_multipliers.csv")

    with timer.step("T4 -- risk bands"):
        band_tables = {m: risk_bands.compute_bands(m) for m in models}
        result["band_tables"] = band_tables
        for m, bt in band_tables.items():
            suffix = "" if m == risk_bands.PRIMARY_GCM else f"_{m}"
            _write_csv(bt.frame, out_dir / f"ccrs_risk_bands{suffix}.csv")
        (out_dir / "ccrs_risk_bands_report.md").write_text(
            risk_bands.build_summary(band_tables[risk_bands.PRIMARY_GCM]), encoding="utf-8")

    with timer.step("T5 -- CCRS assembly + report"):
        ccrs_df = ccrs_report.assemble_ccrs(hazard_wide, age_factors, event_multipliers)
        final = ccrs_report.attach_risk_bands(ccrs_df, band_tables)
        water_shares = ccrs_report.compute_water_band_shares(band_tables)
        heat_shares = ccrs_report.compute_heat_band_shares(band_tables)
        report_md = ccrs_report.build_summary(age_factors, water_shares, heat_shares, band_tables, final)
        _write_csv(final, out_dir / "ccrs_final.csv")   # same columns as ccrs_report.main()
        # the visualization layer's frame carries the extra V6 flag (matches
        # data.load_ccrs_final); it is not written to the CSV.
        final["computable"] = final["commissioning_year"].notna()
        result.update(final=final, water_shares=water_shares, heat_shares=heat_shares)
        _write_csv(water_shares, out_dir / "ccrs_water_band_capacity_shares.csv")
        _write_csv(heat_shares, out_dir / "ccrs_heat_band_capacity_shares.csv")
        (out_dir / "ccrs_report.md").write_text(report_md, encoding="utf-8")

    pre = draws = ci = None
    if skip_montecarlo:
        timer.skipped("Monte Carlo", "--skip-montecarlo")
    else:
        with timer.step("Monte Carlo"):
            pre = mc._Precomputed(hazard_by_model=hazard_by_model, band_tables=band_tables)
            water_frames, heat_frames = [], []
            for magnitude in mc.MAGNITUDES:
                res = mc.run_simulation(magnitude, n=n_iter, pre=pre)
                res["water"]["magnitude"] = magnitude
                res["heat"]["magnitude"] = magnitude
                water_frames.append(res["water"])
                heat_frames.append(res["heat"])
            mc.assert_structural_constants_untouched(pre)
            _write_csv(pd.concat(water_frames, ignore_index=True), out_dir / "monte_carlo_water_band.csv")
            _write_csv(pd.concat(heat_frames, ignore_index=True), out_dir / "monte_carlo_heat_band.csv")
            draws = mc.run_country_scenario_draws(n=n_iter, pre=pre)
            ci = ci_from_draws(draws)
        result.update(mc_pre=pre, mc_draws=draws, mc_ci=ci)

    if skip_tables:
        timer.skipped("Tables", "--skip-tables")
    else:
        with timer.step("Tables"):
            _generate_tables(out_dir, band_tables, event_multipliers, hazard_by_model,
                             pre, ci, fig_countries)

    # EM-DAT spatial validation -- produces both CSV outputs (a data product,
    # gated with the tables) and a box/strip figure (gated with the figures);
    # run_validation is computed once and shared between the two.
    if skip_tables and skip_figures:
        timer.skipped("EM-DAT spatial validation", "--skip-tables and --skip-figures")
    else:
        with timer.step("EM-DAT spatial validation"):
            emv_result = emv.run_validation(fig_countries)
            result["emv_result"] = emv_result
            if not skip_tables:
                _write_csv(emv_result["summary"], out_dir / "emdat_spatial_validation.csv")
                _write_csv(emv_result["polygons"], out_dir / "emdat_spatial_validation_polygons.csv")
            if not skip_figures:
                emv_viz.plot_emdat_spatial_validation(fig_countries, result=emv_result)

    if skip_figures:
        timer.skipped("Figures", "--skip-figures")
    else:
        with timer.step("Figures"):
            _generate_figures(final, band_tables, age_factors, water_shares, heat_shares,
                              hazard_by_model, draws, pre, fig_countries, fig_scenarios, models)

    print(timer.summary())
    result["timer"] = timer
    return result


# --------------------------------------------------------------------------
# Tables -- mirrors src/visualization/tables.py's main(), on shared objects
# --------------------------------------------------------------------------
def _generate_tables(out_dir, band_tables, event_multipliers, hazard_by_model,
                     pre, ci, countries) -> None:
    _write_csv(vtables.heat_band_gcm_comparison_table(band_tables),
               out_dir / "heat_band_gcm_comparison.csv")
    _write_csv(vtables.water_heat_contingency_capacity_table(band_tables),
               out_dir / "water_heat_contingency_capacity.csv")
    _write_csv(vtables.hazard_weight_provenance_table(),
               out_dir / "hazard_weight_provenance.csv")
    per_plant = vtables.hazard_term_contribution_per_plant(
        risk_bands.PRIMARY_GCM, countries, hazard=hazard_by_model[risk_bands.PRIMARY_GCM])
    _write_csv(vtables.hazard_term_contribution_table(per_plant=per_plant),
               out_dir / "hazard_term_contribution.csv")
    _write_csv(vtables.event_multiplier_table(event_multipliers),
               out_dir / "event_multiplier.csv")

    if pre is not None and ci is not None:
        _write_csv(vtables.national_ccrs_summary_table(ci),
                   out_dir / "national_ccrs_summary.csv")
        _write_csv(vtables.monte_carlo_parameter_summary_table(pre=pre),
                   out_dir / "monte_carlo_national_summary.csv")
    else:
        logger.info("Monte Carlo skipped -- national_ccrs_summary / monte_carlo_national_summary not written")


# --------------------------------------------------------------------------
# Figures -- every visualization function, on shared in-memory objects
# --------------------------------------------------------------------------
def _generate_figures(final, band_tables, age_factors, water_shares, heat_shares,
                      hazard_by_model, draws, pre, countries, scenarios, models) -> None:
    # Figure 1 -- pipeline schematic, no data dependency
    diagrams.plot_pipeline_overview()

    # Maps -- one figure per water scenario. Every map category is primary-GCM
    # only (the GFDL/MIROC6 heat comparison is a table, not a second map --
    # see plot_heat_risk_band_map's docstring).
    for scen in scenarios:
        maps.plot_figure5_ccrs_overview(countries, water_scenario=scen, final=final)
        maps.plot_water_risk_band_map(countries, water_scenario=scen, final=final)
        maps.plot_computable_base_map(countries, water_scenario=scen, final=final)
        maps.plot_heat_risk_band_map(countries, water_scenario=scen, final=final)
        maps.plot_worst_case_risk_band_map(countries, water_scenario=scen, final=final)
    # Asset-level continuous-color PES map -- Supplementary candidate, writes
    # to combined/secondary/ itself (2026-09-07: overview took the Figure 5 slot).
    maps.plot_ccrs_asset_level_pes_map(countries, final=final)
    maps.plot_ccrs_scenario_delta_map(countries, final=final, combined=False)
    maps.plot_ccrs_scenario_delta_map(countries, final=final, combined=True)

    # Charts
    charts.plot_figure2_capacity_exposure_by_band(countries, water_shares, heat_shares)
    charts.plot_capacity_by_risk_band(water_shares, heat_shares)
    charts.plot_age_factor_by_bucket(countries, age_factors)
    for m in models:
        charts.plot_water_heat_combined_risk_bars(countries, gcm=m, bands=band_tables)
        charts.plot_top_n_ccrs_breakdown_by_bucket(countries, gcm=m, final=final)
    for scen in scenarios:
        charts.plot_ccrs_distribution_by_bucket(countries, water_scenario=scen, final=final)
    # Figure 6 -- PES is the article figure; opt/bau are secondary variants.
    for scen in dict.fromkeys(["pes", *scenarios]):
        charts.plot_figure6_technology_age_vulnerability_pes(
            countries, final=final, age_factors=age_factors, scenario=scen)

    # C4 -- one per-plant contribution frame, feeds both C4 figures
    per_plant = vtables.hazard_term_contribution_per_plant(
        risk_bands.PRIMARY_GCM, countries, hazard=hazard_by_model[risk_bands.PRIMARY_GCM])
    contribution = vtables.hazard_term_contribution_table(per_plant=per_plant)
    charts.plot_hazard_term_contribution_distribution(countries, per_plant=per_plant)
    charts.plot_hazard_term_contribution(countries, contribution=contribution)

    # Figure 7 + its secondary PES-only piece -- both consume the SAME draws
    # object (and the same pre), never rebuilding _Precomputed. Skipped
    # entirely when Monte Carlo did not run (--skip-montecarlo).
    if draws is not None:
        charts.plot_ccrs_rank_stability(countries, draws=draws, pre=pre)
        charts.plot_figure7_montecarlo_stability_pes(countries, draws=draws, pre=pre)
    else:
        logger.info("Monte Carlo skipped -- Figure 7 (rank stability) not generated")

    _copy_named_article_figures(scenarios)


# Figures 3 and 4 are byte-identical copies of the PES water/heat risk-band
# maps under the manuscript's figure numbering -- there is deliberately no
# plot function that writes those names (docs/memory/05-decisoes-tecnicas.md).
# The orchestrator makes the copies so "generate every figure" needs no
# follow-up shell step.
def _copy_named_article_figures(scenarios) -> None:
    if "pes" not in scenarios:
        return
    combined = maps.OUTPUT_MAPS / "combined"
    renames = [
        ("water_risk_band_pes", "figure3_water_risk_band_pes"),
        ("heat_risk_band_ssp585", "figure4_heat_risk_band_pes"),
    ]
    for src_stem, dst_stem in renames:
        for sub, ext in (("", ".png"), ("pdf", ".pdf")):
            src = combined / sub / f"{src_stem}{ext}"
            dst = combined / sub / f"{dst_stem}{ext}"
            if src.exists():
                dst.write_bytes(src.read_bytes())
                logger.info("copied %s -> %s", src.name, dst.name)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m src.main", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--skip-processors", action="store_true",
                   help="never run the climate processors (assume the rasters are current)")
    p.add_argument("--force-processors", action="store_true",
                   help="re-run every processor with overwrite=True, ignoring the staleness check")
    p.add_argument("--skip-montecarlo", action="store_true",
                   help="skip Monte Carlo (and the figures/tables that need it) -- for fast map iteration")
    p.add_argument("--skip-tables", action="store_true", help="skip the summary-table CSVs")
    p.add_argument("--skip-figures", action="store_true", help="skip figure generation")
    p.add_argument("--countries", nargs="+", metavar="NAME", default=None,
                   help="restrict FIGURE/TABLE output to these countries (index + Monte Carlo stay full-scope)")
    p.add_argument("--scenarios", nargs="+", metavar="SCEN", default=None,
                   choices=list(WATER_SCENARIOS),
                   help="restrict FIGURE output to these water scenarios (index + Monte Carlo stay full-scope)")
    p.add_argument("--mc-iterations", type=int, default=None,
                   help=f"Monte Carlo iterations per magnitude (default {mc.N_ITERATIONS}; lower = faster dev runs)")
    p.add_argument("--out-dir", type=Path, default=OUTPUT_TABLES, help="where the CSV/report outputs go")
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    args = build_parser().parse_args(argv)
    if args.skip_processors and args.force_processors:
        raise SystemExit("--skip-processors and --force-processors are mutually exclusive")
    run_pipeline(
        countries=args.countries,
        water_scenarios=args.scenarios,
        skip_processors=args.skip_processors,
        force_processors=args.force_processors,
        skip_montecarlo=args.skip_montecarlo,
        skip_tables=args.skip_tables,
        skip_figures=args.skip_figures,
        out_dir=args.out_dir,
        mc_iterations=args.mc_iterations,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
