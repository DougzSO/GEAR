"""
Climate acquisition orchestrator.

Runs the climate-layer downloaders — boundaries, CDS tasmax (extreme heat),
Aqueduct (water stress) — and writes an explicit per-step, per-country
report. It never prints "completed successfully" without checking whether a
step actually failed or was skipped: a skipped Aqueduct step (no
``GEE_PROJECT_ID``) is reported as skipped, not as success.

The process exit code reflects whether any step failed for real.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime

from src.config import COUNTRIES, LOG_DIR
from src.downloaders.aqueduct_downloader import download_all_aqueduct
from src.downloaders.boundaries_downloader import download_all_boundaries
from src.downloaders.cds_tasmax_downloader import download_all_cds_tasmax

logger = logging.getLogger(__name__)

ALL_STEPS = ["boundaries", "cds_tasmax", "aqueduct"]


def _iter_leaf_status(node):
    """Yield every leaf status dict from an arbitrarily nested
    ``country -> ... -> {"success": bool}`` report."""
    if isinstance(node, dict):
        if "success" in node:
            yield node
        else:
            for value in node.values():
                yield from _iter_leaf_status(value)


def _summarize(report: dict, label: str) -> dict:
    total = success = 0
    for status in _iter_leaf_status(report):
        total += 1
        success += int(bool(status["success"]))
    return {"label": label, "total": total, "success": success, "failed": total - success}


def _skipped(report: dict) -> bool:
    """True only if every leaf was skipped for a non-failure reason
    (e.g. Aqueduct with no GEE project)."""
    leaves = list(_iter_leaf_status(report))
    return bool(leaves) and all(
        not s["success"] and s.get("reason") == "gee_not_configured" for s in leaves
    )


def run_climate_pipeline(
    steps: list[str] | None = None, overwrite: bool = False
) -> dict:
    """Run the requested acquisition steps and return a full report. ``steps``
    can be a subset, e.g. ``["boundaries", "aqueduct"]``."""
    steps = steps or ALL_STEPS
    unknown = [s for s in steps if s not in ALL_STEPS]
    if unknown:
        raise ValueError(f"Unknown step(s): {unknown}. Valid: {ALL_STEPS}")

    report: dict = {"timestamp": datetime.now().isoformat(), "steps": {}}

    if "boundaries" in steps:
        logger.info("=== Step: boundaries (GADM) ===")
        result = download_all_boundaries(COUNTRIES, overwrite=overwrite)
        report["steps"]["boundaries"] = result
        summary = _summarize(result, "boundaries")
        logger.info("Boundaries: %d/%d countries OK", summary["success"], summary["total"])
        if summary["failed"]:
            logger.error("Boundaries incomplete — downstream steps may fail for those countries.")

    if "cds_tasmax" in steps:
        logger.info("=== Step: CDS tasmax (extreme heat) ===")
        result = download_all_cds_tasmax(COUNTRIES, overwrite=overwrite)
        report["steps"]["cds_tasmax"] = result
        summary = _summarize(result, "cds_tasmax")
        logger.info("CDS tasmax: %d/%d country x model x scenario OK", summary["success"], summary["total"])

    if "aqueduct" in steps:
        logger.info("=== Step: Aqueduct (water stress, GEE) ===")
        result = download_all_aqueduct(COUNTRIES, overwrite=overwrite)
        report["steps"]["aqueduct"] = result
        summary = _summarize(result, "aqueduct")
        if _skipped(result):
            logger.warning("Aqueduct: SKIPPED for all countries (GEE_PROJECT_ID not set).")
        else:
            logger.info("Aqueduct: %d/%d countries OK", summary["success"], summary["total"])

    any_failure = False
    for step_name, step_report in report["steps"].items():
        if step_name == "aqueduct" and _skipped(step_report):
            continue  # skipped by design, not a failure
        any_failure = any_failure or _summarize(step_report, step_name)["failed"] > 0

    report["overall_success"] = not any_failure

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    report_path = LOG_DIR / f"climate_pipeline_report_{datetime.now():%Y%m%d_%H%M%S}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))
    logger.info(
        "Climate pipeline finished %s. Report: %s",
        "with failures" if any_failure else "with no recorded failures",
        report_path,
    )
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    result = run_climate_pipeline()
    sys.exit(0 if result["overall_success"] else 1)
