"""
GEAR v3 pipeline orchestrator -- one entry point for the index + reporting
layer (correlation_gate -> risk_calculator -> risk_bands -> psae ->
contextual_validators -> [sobol/general_mc, opt-in] -> results_draft), with a
SHA-256 manifest so a step aborts instead of silently running on stale
upstream output.

    python -m src.orchestrator [--only STEP [STEP ...]] [--run-sobol] [--run-general-mc]

Design decisions this module makes explicit (see docs/memory/05-decisoes-tecnicas.md
for the full writeup):

* No ``params/config.yaml``. ``src/config.py`` is already this repo's one
  mandatory shared config (``CLAUDE.md`` Sec. 12) -- a parallel YAML file
  nothing else reads would just be a second, driftable source of truth.
  This module hashes ``src/config.py`` itself for the "did config change"
  check.
* Every step runs IN-PROCESS (calls the module's own function directly),
  never ``subprocess.run("python -m ...")``. ``src/main.py``'s docstring
  documents at length why per-step CLI invocation is wasteful (each CLI
  recomputes its own inputs); ``src/reporting/results_draft/run_all.py``
  already proves the in-process pattern works end to end for this
  pipeline's own reporting layer. Re-adding subprocess-per-step here would
  reintroduce the exact problem that was already fixed once.
* Steps F (Sobol) and G (general-MC) are opt-in (``--run-sobol`` /
  ``--run-general-mc``), never run by default. The CLOSED Phase 6 results
  already on disk (``phase6_sobol_full_n1024.json`` at N0=1024 took 7,237s;
  ``phase6_general_mc_convergence.json``'s doubling sequence took 11,902s)
  make "run every time" impractical, and this module's own by-stratum/
  by-GCM extensions (``sobol_sensitivity.run_validation_stratified``,
  ``general_mc.run_convergence_by_gcm``) are EXPERIMENTAL, not part of the
  methodology closed in docs/DECISIONS.md -- see those functions'
  docstrings. Default ``--n0``/``--ns`` here are small smoke-test values,
  not a replacement for the closed full-scale run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from src import config
from src.index import contextual_validators, correlation_gate, psae as psae_mod
from src.index import risk_bands, risk_calculator
from src.reporting.results_draft import common as rd_common
from src.reporting.results_draft import run_all as results_draft_run_all

logger = logging.getLogger("src.orchestrator")

CONFIG_FILE = Path(__file__).resolve().with_name("config.py")
MANIFEST_PATH = config.OUTPUT_DIR / "pipeline_manifest.json"
OUTPUT_TABLES = config.OUTPUT_TABLES
CLIMATE_PROCESSED = config.CLIMATE_PROCESSED


# --------------------------------------------------------------------------
# Hashing
# --------------------------------------------------------------------------
def hash_file(path: Path) -> str:
    """SHA-256 hex digest of one file's bytes."""
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def hash_directory_listing(directory: Path, pattern: str = "*.tif") -> str:
    """SHA-256 of the sorted (relative path, size, mtime_ns) listing of every
    file matching ``pattern`` under ``directory`` -- a staleness fingerprint
    for a whole raster tree without reading gigabytes of raster bytes into
    this hash (``hash_file`` is for single small/medium files; the climate
    raster tree is not one)."""
    directory = Path(directory)
    if not directory.exists():
        return hashlib.sha256(b"<missing>").hexdigest()
    entries = []
    for p in sorted(directory.rglob(pattern)):
        st = p.stat()
        entries.append(f"{p.relative_to(directory).as_posix()}:{st.st_size}:{st.st_mtime_ns}")
    h = hashlib.sha256()
    h.update("\n".join(entries).encode("utf-8"))
    return h.hexdigest()


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if isinstance(obj, dict):
        return {str(k): v for k, v in obj.items()}
    if isinstance(obj, (set, tuple)):
        return list(obj)
    return str(obj)


def _write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------
def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {"runs": [], "current_hashes": {}}


def save_manifest(manifest: dict) -> None:
    _write_json(manifest, MANIFEST_PATH)


def git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=config.BASE_DIR,
            capture_output=True, text=True, check=True, timeout=10,
        )
        return out.stdout.strip()
    except Exception:
        return None


def check_dependencies(step_name: str, input_hashes: dict[str, str], manifest: dict) -> bool:
    """Compare ``input_hashes`` (path -> freshly computed hash) against
    ``manifest["current_hashes"]``. A path never recorded before (first run,
    or a brand-new input) is not a mismatch. Returns False (and logs an
    [ABORT] line per changed file) the moment any previously recorded hash
    disagrees with the current one."""
    ok = True
    for path_str, current in input_hashes.items():
        recorded = manifest["current_hashes"].get(path_str)
        if recorded is not None and recorded != current:
            print(f"[ABORT] {step_name}: input {path_str} changed (hash mismatch) "
                  f"since the upstream step that produced it last ran -- re-run "
                  f"that upstream step first.")
            ok = False
    return ok


# --------------------------------------------------------------------------
# Step definitions
# --------------------------------------------------------------------------
@dataclass
class StepResult:
    name: str
    status: str  # "success" | "failed" | "aborted" | "skipped"
    input_hashes: dict[str, str] = field(default_factory=dict)
    output_hashes: dict[str, str] = field(default_factory=dict)
    elapsed_s: float = 0.0
    detail: str = ""


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def _band_cuts_frame(result: risk_bands.RiskBandTable) -> pd.DataFrame:
    """Flatten ``RiskBandTable.percentile_cuts`` (Tier-3 (hazard, bucket) ->
    ``percentile_band_cuts()`` result) into a tabular ``band_cuts.csv`` --
    the same numbers already rendered as a prose string in
    ``risk_bands_report.md``, kept here as a NEW parseable table instead of
    a formatted-text column."""
    rows = []
    for (hazard, bucket), info in result.percentile_cuts.items():
        rows.append({
            "hazard_term": hazard, "bucket": bucket, "model": result.model,
            "diagnostic_percentile": info["diagnostic_percentile"],
            "diagnostic_value": info["diagnostic_value"],
            "band_cuts": ", ".join(f"{v:.6g}" for v in info["band_cuts"]),
            "n": info["n"],
        })
    return pd.DataFrame(rows)


def step_correlation_gate(_manifest: dict) -> tuple[pd.DataFrame, dict[str, Path]]:
    table = correlation_gate.run_gate()
    out = OUTPUT_TABLES / "correlation_gate.csv"
    _write_csv(table, out)
    return table, {"correlation_gate.csv": out}


def step_risk_calculator(_manifest: dict) -> tuple[pd.DataFrame, dict[str, Path]]:
    long_df = risk_calculator.compute_risk()
    out = OUTPUT_TABLES / "risk_by_hazard.csv"
    _write_csv(long_df, out)
    return long_df, {"risk_by_hazard.csv": out}


def step_risk_bands(_manifest: dict) -> tuple[risk_bands.RiskBandTable, dict[str, Path]]:
    result = risk_bands.compute_risk_bands(risk_bands.PRIMARY_GCM)
    bands_out = OUTPUT_TABLES / "risk_bands.csv"
    _write_csv(result.frame, bands_out)
    cuts_out = OUTPUT_TABLES / "band_cuts.csv"
    _write_csv(_band_cuts_frame(result), cuts_out)
    return result, {"risk_bands.csv": bands_out, "band_cuts.csv": cuts_out}


def step_psae(band_result: risk_bands.RiskBandTable) -> tuple[pd.DataFrame, dict[str, Path]]:
    result = psae_mod.compute_psae(band_result)
    out = OUTPUT_TABLES / "psae.csv"
    _write_csv(result.frame, out)
    return result.frame, {"psae.csv": out}


def step_contextual_validators(_manifest: dict) -> tuple[pd.DataFrame, dict[str, Path]]:
    result = contextual_validators.compute_contextual_validation()
    out = OUTPUT_TABLES / "contextual_validators.csv"
    _write_csv(result, out)
    return result, {"contextual_validators.csv": out}


def step_sobol_stratified(n0: int, n_workers: int | None) -> dict[str, Path]:
    from src.index import sobol_sensitivity as ss

    result = ss.run_validation_stratified(n0, n_workers=n_workers)
    out = OUTPUT_TABLES / "phase6_sobol_stratified.json"
    _write_json(result, out)
    return {"phase6_sobol_stratified.json": out}


def step_general_mc_by_gcm(ns: list[int], n_workers: int | None) -> dict[str, Path]:
    from src.index import general_mc as gmc

    steps = gmc.run_convergence_by_gcm(ns, n_workers=n_workers)
    payload = {"ns": ns, "steps": [
        {"n": s["n"], "n_total_draws": s["n_total_draws"], "models": s["models"],
         "elapsed_s": s["elapsed_s"], "s_per_draw": s["s_per_draw"],
         "stream_stats": {f"{c}|{sc}|{m}": v for (c, sc, m), v in s["stream_stats"].items()}}
        for s in steps
    ]}
    out = OUTPUT_TABLES / "phase6_general_mc_by_gcm.json"
    _write_json(payload, out)
    return {"phase6_general_mc_by_gcm.json": out}


def step_results_draft(_manifest: dict) -> dict[str, Path]:
    entries = results_draft_run_all.run()
    manifest_path = rd_common.write_manifest(entries)
    inventory_path = rd_common.write_figure_inventory(entries)
    n_generated = sum(1 for e in entries if e.status.startswith("generated"))
    logger.info("results_draft: %d/%d items generated", n_generated, len(entries))
    outputs = {"MANIFEST.md": manifest_path, "FIGURE_INVENTORY.md": inventory_path}
    for p in sorted((config.OUTPUT_RESULTS_DRAFT / "tables").rglob("*")):
        if p.is_file():
            outputs[f"results_draft/tables/{p.name}"] = p
    for p in sorted((config.OUTPUT_RESULTS_DRAFT / "maps").rglob("*")):
        if p.is_file():
            outputs[f"results_draft/maps/{p.relative_to(config.OUTPUT_RESULTS_DRAFT / 'maps')}"] = p
    for p in sorted((config.OUTPUT_RESULTS_DRAFT / "other").rglob("*")):
        if p.is_file():
            outputs[f"results_draft/other/{p.name}"] = p
    return outputs


# --------------------------------------------------------------------------
# Post-execution validations
# --------------------------------------------------------------------------
def validate_no_ccrs_prefix(written_paths: list[Path]) -> None:
    bad = [p for p in written_paths if p.name.startswith("ccrs_")]
    if bad:
        raise RuntimeError(
            f"[ABORT] orchestrator wrote {len(bad)} file(s) with a 'ccrs_' prefix "
            f"-- that legacy namespace belongs to the deleted CCRS layer, not v3: "
            f"{[str(p) for p in bad]}"
        )


def validate_risk_bands_wind_nonnull(frame: pd.DataFrame) -> None:
    wind_rows = frame[frame["hazard_term"] == "wind"]
    if wind_rows.empty:
        raise RuntimeError("[ABORT] risk_bands.csv has no 'wind' hazard_term rows at all.")
    if wind_rows["risk_band"].isna().all():
        raise RuntimeError(
            "[ABORT] risk_bands.csv: every 'wind' row has risk_band=NaN "
            "(100% NaN) -- Extreme Wind classification did not run."
        )


def validate_sobol_stratified(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    strata = payload.get("strata", [])
    if not strata:
        raise RuntimeError(f"[ABORT] {path}: no (country, bucket) strata present.")
    if not payload.get("sobol_risk_by_stratum"):
        raise RuntimeError(f"[ABORT] {path}: sobol_risk_by_stratum is empty.")


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------
STEP_ORDER = [
    "correlation_gate", "risk_calculator", "risk_bands", "psae",
    "contextual_validators", "sobol_sensitivity", "general_mc", "results_draft",
]


def run_pipeline(
    only: list[str] | None = None,
    *,
    run_sobol: bool = False,
    run_general_mc: bool = False,
    sobol_n0: int = 16,
    general_mc_ns: list[int] | None = None,
    n_workers: int | None = None,
) -> int:
    general_mc_ns = general_mc_ns or [50, 100]
    selected = only or STEP_ORDER
    manifest = load_manifest()
    run_record: dict = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "git_commit": git_commit(),
        "config_hash": hash_file(CONFIG_FILE),
        "steps": [],
    }
    written_paths: list[Path] = []
    band_result: risk_bands.RiskBandTable | None = None
    exit_code = 0

    for step in selected:
        if step not in STEP_ORDER:
            print(f"[ABORT] unknown step {step!r}; known steps: {STEP_ORDER}")
            return 1

        input_hashes = {"src/config.py": run_record["config_hash"]}
        if step == "correlation_gate":
            input_hashes["data/processed/climate"] = hash_directory_listing(CLIMATE_PROCESSED)
        elif step in ("risk_calculator", "risk_bands"):
            input_hashes["data/processed/climate"] = hash_directory_listing(CLIMATE_PROCESSED)
        elif step == "psae":
            bands_path = OUTPUT_TABLES / "risk_bands.csv"
            if bands_path.exists():
                input_hashes["data/outputs/tables/risk_bands.csv"] = hash_file(bands_path)
        elif step in ("sobol_sensitivity", "general_mc"):
            for name in ("psae.csv", "risk_by_hazard.csv"):
                p = OUTPUT_TABLES / name
                if p.exists():
                    input_hashes[f"data/outputs/tables/{name}"] = hash_file(p)
        elif step == "results_draft":
            p = OUTPUT_TABLES / "psae.csv"
            if p.exists():
                input_hashes["data/outputs/tables/psae.csv"] = hash_file(p)

        if not check_dependencies(step, input_hashes, manifest):
            run_record["steps"].append({"step": step, "status": "aborted"})
            exit_code = 1
            break

        t0 = time.perf_counter()
        try:
            outputs: dict[str, Path] = {}
            if step == "correlation_gate":
                _, outputs = step_correlation_gate(manifest)
            elif step == "risk_calculator":
                _, outputs = step_risk_calculator(manifest)
            elif step == "risk_bands":
                band_result, outputs = step_risk_bands(manifest)
                validate_risk_bands_wind_nonnull(band_result.frame)
            elif step == "psae":
                if band_result is None:
                    band_result = risk_bands.compute_risk_bands(risk_bands.PRIMARY_GCM)
                _, outputs = step_psae(band_result)
            elif step == "contextual_validators":
                _, outputs = step_contextual_validators(manifest)
            elif step == "sobol_sensitivity":
                if not run_sobol:
                    logger.info("sobol_sensitivity: skipped (pass --run-sobol to execute; "
                                "n0=%d is a smoke-test default, not the closed n0=1024 run)", sobol_n0)
                    run_record["steps"].append({"step": step, "status": "skipped"})
                    continue
                outputs = step_sobol_stratified(sobol_n0, n_workers)
                validate_sobol_stratified(outputs["phase6_sobol_stratified.json"])
            elif step == "general_mc":
                if not run_general_mc:
                    logger.info("general_mc: skipped (pass --run-general-mc to execute; "
                                "ns=%s is a smoke-test default, not the closed N=800/stream run)", general_mc_ns)
                    run_record["steps"].append({"step": step, "status": "skipped"})
                    continue
                outputs = step_general_mc_by_gcm(general_mc_ns, n_workers)
            elif step == "results_draft":
                outputs = step_results_draft(manifest)
        except Exception as exc:
            elapsed = time.perf_counter() - t0
            logger.exception("%s failed", step)
            run_record["steps"].append({
                "step": step, "status": "failed", "elapsed_s": elapsed, "error": str(exc),
            })
            exit_code = 1
            break

        elapsed = time.perf_counter() - t0
        output_hashes = {}
        for label, path in outputs.items():
            written_paths.append(path)
            key = f"data/outputs/{path.relative_to(config.OUTPUT_DIR).as_posix()}"
            h = hash_file(path) if path.stat().st_size < 200_000_000 else hash_directory_listing(path.parent)
            output_hashes[key] = h
            manifest["current_hashes"][key] = h
        for k, v in input_hashes.items():
            manifest["current_hashes"][k] = v

        logger.info("[%s] done in %.1fs (%d output file(s))", step, elapsed, len(outputs))
        run_record["steps"].append({
            "step": step, "status": "success", "elapsed_s": elapsed,
            "input_hashes": input_hashes, "output_hashes": output_hashes,
        })

    validate_no_ccrs_prefix(written_paths)

    manifest["runs"].append(run_record)
    save_manifest(manifest)
    return exit_code


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m src.orchestrator", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--only", nargs="+", metavar="STEP", choices=STEP_ORDER, default=None,
                   help="run only these steps (in STEP_ORDER order), e.g. --only risk_bands psae")
    p.add_argument("--run-sobol", action="store_true",
                   help="execute the stratified Sobol step (opt-in -- multi-hour at real n0)")
    p.add_argument("--run-general-mc", action="store_true",
                   help="execute the by-GCM general-MC step (opt-in -- multi-hour at real N)")
    p.add_argument("--sobol-n0", type=int, default=16,
                   help="Sobol n0 for --run-sobol (default 16, a smoke test -- the closed run used 1024)")
    p.add_argument("--general-mc-ns", type=int, nargs="+", default=[50, 100],
                   help="general-MC doubling sequence for --run-general-mc (default 50 100 -- the closed run reached 800/stream)")
    p.add_argument("--n-workers", type=int, default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    args = build_parser().parse_args(argv)
    return run_pipeline(
        only=args.only,
        run_sobol=args.run_sobol,
        run_general_mc=args.run_general_mc,
        sobol_n0=args.sobol_n0,
        general_mc_ns=args.general_mc_ns,
        n_workers=args.n_workers,
    )


if __name__ == "__main__":
    raise SystemExit(main())
