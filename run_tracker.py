#!/usr/bin/env python3
"""Run Tracker: Scheduled Tasks CLI Entrypoint for Nationwide EV Subsidy Tracking.

Autonomous background tracker that monitors, calculates, and publishes
South Korea EV subsidy depletion rates, regional quotas, and alert thresholds.

Usage:
    python3 run_tracker.py --sync-web --verbose
    python3 run_tracker.py --dry-run
    python3 run_tracker.py --output /path/to/custom.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import List, Optional, Set, Union

# Ensure repository root and tracker package are on sys.path
_CURRENT_DIR = Path(__file__).resolve().parent
_POSSIBLE_ROOTS = [
    _CURRENT_DIR,
    _CURRENT_DIR.parent,
    _CURRENT_DIR / "ev-stealth-web",
    _CURRENT_DIR.parent / "ev-stealth-web",
]
for root_path in _POSSIBLE_ROOTS:
    if root_path.exists() and str(root_path) not in sys.path:
        sys.path.insert(0, str(root_path))

from tracker.subsidy_models import SubsidyPayload
from tracker.subsidy_tracker import SubsidyTracker

logger = logging.getLogger("run_tracker")


def _resolve_default_paths():
    """Adaptively resolve primary and web targets depending on execution directory."""
    if (_CURRENT_DIR / "src" / "data").exists():
        # Executing from within ev-stealth-web/
        primary_output = _CURRENT_DIR / "src" / "data" / "ev_subsidy_data.json"
        web_output = _CURRENT_DIR / "src" / "data" / "ev_subsidy_data.json"
        mirror_primary = _CURRENT_DIR / "src" / "data" / "subsidy_depletion_data.json"
        mirror_web = _CURRENT_DIR / "src" / "data" / "subsidy_depletion_data.json"
        external_sync_targets: List[Path] = []
        if (_CURRENT_DIR.parent / "data").exists():
            external_sync_targets.append(_CURRENT_DIR.parent / "data" / "ev_subsidy_data.json")
            external_sync_targets.append(_CURRENT_DIR.parent / "data" / "subsidy_depletion_data.json")
        return primary_output, web_output, mirror_primary, mirror_web, external_sync_targets
    else:
        # Executing from project root /Users/a7890/src/my-e-car/
        primary_output = _CURRENT_DIR / "data" / "ev_subsidy_data.json"
        web_output = _CURRENT_DIR / "ev-stealth-web" / "src" / "data" / "ev_subsidy_data.json"
        mirror_primary = _CURRENT_DIR / "data" / "subsidy_depletion_data.json"
        mirror_web = _CURRENT_DIR / "ev-stealth-web" / "src" / "data" / "subsidy_depletion_data.json"
        return primary_output, web_output, mirror_primary, mirror_web, []


(
    DEFAULT_PRIMARY_OUTPUT,
    DEFAULT_WEB_OUTPUT,
    MIRROR_PRIMARY_OUTPUT,
    MIRROR_WEB_OUTPUT,
    EXTERNAL_SYNC_TARGETS,
) = _resolve_default_paths()


def validate_defect_reports_file(file_path: Union[str, Path]) -> bool:
    """Validate that target file contains valid JSON syntax and expected schema ('reports' list key)."""
    p = Path(file_path)
    try:
        if not p.is_file() or p.stat().st_size == 0:
            return False
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False
        if "reports" not in data or not isinstance(data["reports"], list):
            return False
        if not all(isinstance(r, dict) for r in data["reports"]):
            return False
        return True
    except Exception as exc:
        logger.warning("Defect report schema validation failed for %s: %s", p, exc)
        return False


def sync_defect_reports(
    web_dir: Optional[Path] = None,
    dry_run: bool = False,
    run_crawler: bool = False,
) -> List[str]:
    """Synchronize defect reports (daily_reports.json) between root data/ and web src/data/.

    Ensures both locations are bitwise synchronized and crash-durably mirrored.
    Validates source file JSON syntax and schema ('reports' key) before performing
    atomic file replacement based on st_mtime. Never propagates corrupt files.
    If run_crawler is True, executes the crawler pipeline before synchronizing.
    """
    logger.info("Synchronizing defect reports (daily_reports.json)...")
    if dry_run:
        logger.info("[DRY-RUN] Defect reports synchronization skipped file persistence.")
        return []

    # Resolve web and root paths
    if web_dir:
        web_reports_path = Path(web_dir) / "daily_reports.json"
    elif (_CURRENT_DIR / "src" / "data").exists():
        web_reports_path = _CURRENT_DIR / "src" / "data" / "daily_reports.json"
    else:
        web_reports_path = _CURRENT_DIR / "ev-stealth-web" / "src" / "data" / "daily_reports.json"

    if (_CURRENT_DIR / "data").exists():
        root_reports_path = _CURRENT_DIR / "data" / "daily_reports.json"
    else:
        root_reports_path = _CURRENT_DIR.parent / "data" / "daily_reports.json"

    written_paths: List[str] = []

    if run_crawler:
        try:
            from run_scraper import ScraperPipeline
            pipeline = ScraperPipeline()
            res = pipeline.run(
                sources="all",
                limit=10,
                sync_web=True,
                web_dir=web_dir,
                dry_run=dry_run,
            )
            written_paths.extend(res.get("written_paths", []))
            return written_paths
        except Exception as exc:
            logger.warning(
                "Crawler execution in sync_defect_reports encountered: %s. Falling back to mirror synchronization.",
                exc,
            )

    root_exists = root_reports_path.exists()
    web_exists = web_reports_path.exists()

    source_path: Optional[Path] = None
    target_paths: List[Path] = []

    if root_exists and web_exists:
        try:
            root_stat = root_reports_path.stat()
            web_stat = web_reports_path.stat()
            if root_stat.st_mtime >= web_stat.st_mtime:
                primary, secondary = root_reports_path, web_reports_path
            else:
                primary, secondary = web_reports_path, root_reports_path
        except Exception:
            primary, secondary = root_reports_path, web_reports_path

        # Validate candidate source: do not propagate corrupt files
        if validate_defect_reports_file(primary):
            source_path = primary
            target_paths = [secondary]
        elif validate_defect_reports_file(secondary):
            logger.warning(
                "Primary source %s failed defect reports schema validation. Falling back to valid secondary %s.",
                primary,
                secondary,
            )
            source_path = secondary
            target_paths = [primary]
        else:
            logger.error(
                "Both candidate defect report files (%s, %s) are corrupt or invalid. Aborting sync to prevent corruption propagation.",
                primary,
                secondary,
            )
            return []
    elif root_exists and not web_exists:
        if validate_defect_reports_file(root_reports_path):
            source_path = root_reports_path
            target_paths = [web_reports_path]
        else:
            logger.error("Root defect reports file %s is corrupt or invalid. Aborting sync.", root_reports_path)
            return []
    elif web_exists and not root_exists:
        if validate_defect_reports_file(web_reports_path):
            source_path = web_reports_path
            target_paths = [root_reports_path]
        else:
            logger.error("Web defect reports file %s is corrupt or invalid. Aborting sync.", web_reports_path)
            return []

    if source_path and target_paths and validate_defect_reports_file(source_path):
        for tgt in target_paths:
            temp_name = None
            try:
                tgt.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile("wb", dir=str(tgt.parent), delete=False, prefix=".tmp_sync_") as tf:
                    temp_name = tf.name
                    with open(source_path, "rb") as sf:
                        shutil.copyfileobj(sf, tf)
                    tf.flush()
                    os.fsync(tf.fileno())
                os.replace(temp_name, tgt)
                written_paths.append(str(tgt))
                logger.info("  ✓ Successfully synchronized defect reports: %s -> %s", source_path, tgt)
            except Exception as e:
                logger.warning("Failed to synchronize defect report to %s: %s", tgt, e)
            finally:
                if temp_name and os.path.exists(temp_name):
                    os.unlink(temp_name)

    return written_paths


def setup_logging(verbose: bool = False) -> None:
    """Configure structured logging."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_arguments(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse CLI flags and parameters."""
    parser = argparse.ArgumentParser(
        description="Autonomous Nationwide EV Subsidy Depletion Tracker"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=DEFAULT_PRIMARY_OUTPUT,
        help="Primary output path for the generated subsidy JSON dataset.",
    )
    parser.add_argument(
        "--sync-web",
        action="store_true",
        help="Synchronize output files directly into ev-stealth-web/src/data/.",
    )
    web_dir_env = os.getenv("EV_TRACKER_WEB_DIR")
    parser.add_argument(
        "--web-dir",
        type=Path,
        default=Path(web_dir_env) if web_dir_env else None,
        help="Custom web directory to sync data files into (overrides default ev-stealth-web/src/data/ or EV_TRACKER_WEB_DIR).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable detailed debug logging.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate metrics and output executive summary without saving to disk.",
    )
    parser.add_argument(
        "--mock-network",
        action="store_true",
        help="Simulate remote network failure to force resilient baseline fallback.",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default=os.getenv("EV_SUBSIDY_API_ENDPOINT"),
        help="Custom URL for remote subsidy API/scraper endpoint.",
    )
    parser.add_argument(
        "--validate-cache",
        dest="validate_cache",
        action="store_true",
        default=True,
        help="Validate cached payload structure and integrity (default: True).",
    )
    parser.add_argument(
        "--no-validate-cache",
        dest="validate_cache",
        action="store_false",
        help="Disable cache schema and region validation.",
    )
    parser.add_argument(
        "--quarantine-corrupted",
        dest="quarantine_corrupted",
        action="store_true",
        default=True,
        help="Quarantine corrupted cache files if encountered (default: True).",
    )
    parser.add_argument(
        "--no-quarantine-corrupted",
        dest="quarantine_corrupted",
        action="store_false",
        help="Disable automatic quarantine of corrupted cache files.",
    )
    parser.add_argument(
        "--sync-defects",
        dest="sync_defects",
        action="store_true",
        default=None,
        help="Synchronize defect reports alongside subsidy data.",
    )
    parser.add_argument(
        "--no-sync-defects",
        dest="sync_defects",
        action="store_false",
        help="Disable defect reports synchronization.",
    )
    return parser.parse_args(args)


parse_args = parse_arguments


def main() -> int:
    """Main CLI entrypoint execution loop."""
    args = parse_arguments()
    setup_logging(args.verbose)

    logger.info("Initializing Autonomous EV Subsidy Tracker...")
    logger.info("Configuration: dry_run=%s, sync_web=%s, output=%s", args.dry_run, args.sync_web, args.output)

    try:
        tracker = SubsidyTracker(
            endpoint_url=args.endpoint,
            timeout_seconds=5.0,
            cache_fallback_path=args.output,
            validate_cache=args.validate_cache,
            quarantine_corrupted=getattr(args, "quarantine_corrupted", True),
        )

        payload, fallback_used = tracker.execute_tracking_cycle(
            mock_network_failure=args.mock_network,
            validate_cache=args.validate_cache,
            quarantine_corrupted=getattr(args, "quarantine_corrupted", True),
        )

        if not payload or not getattr(payload, "regions", None) or len(payload.regions) < 17:
            logger.warning(
                "Cache payload incomplete (%d regions). Safe baseline fallback guaranteed.",
                len(payload.regions) if (payload and getattr(payload, "regions", None)) else 0,
            )
            from tracker.subsidy_baseline import build_initial_baseline
            payload = build_initial_baseline()
            fallback_used = True

        if not args.dry_run:
            destinations: List[Path] = [args.output]

            # If writing to default primary output or when syncing with standard filename, also create mirror subsidy_depletion_data.json
            if args.output.resolve() == DEFAULT_PRIMARY_OUTPUT.resolve():
                destinations.append(MIRROR_PRIMARY_OUTPUT)
            elif args.output.name == "ev_subsidy_data.json":
                destinations.append(args.output.parent / "subsidy_depletion_data.json")
            elif args.output.name == "subsidy_depletion_data.json":
                destinations.append(args.output.parent / "ev_subsidy_data.json")

            if args.sync_web:
                if args.web_dir:
                    web_dir = Path(args.web_dir)
                    destinations.append(web_dir / "ev_subsidy_data.json")
                    destinations.append(web_dir / "subsidy_depletion_data.json")
                else:
                    destinations.append(DEFAULT_WEB_OUTPUT)
                    destinations.append(MIRROR_WEB_OUTPUT)
                    destinations.extend(EXTERNAL_SYNC_TARGETS)

            # Deduplicate destinations while preserving order
            unique_destinations: List[Path] = []
            seen_paths: Set[str] = set()
            for dst in destinations:
                resolved_str = str(dst.resolve()) if dst.exists() else str(dst.absolute())
                if resolved_str not in seen_paths:
                    seen_paths.add(resolved_str)
                    unique_destinations.append(dst)

            logger.info("Saving subsidy datasets to %d target path(s)...", len(unique_destinations))
            written_paths = tracker.save_payload(payload, unique_destinations)
            for wp in written_paths:
                logger.info("  ✓ Successfully written: %s", wp)

            # Synchronize defect reports alongside subsidy data when syncing web
            if args.sync_web or (args.sync_defects is True):
                if getattr(args, "sync_defects", None) is not False:
                    sync_defect_reports(
                        web_dir=args.web_dir,
                        dry_run=False,
                        run_crawler=bool(args.sync_defects is True),
                    )
        else:
            logger.info("Dry-run requested: skipping file persistence.")
            if args.sync_web or (args.sync_defects is True):
                sync_defect_reports(web_dir=args.web_dir, dry_run=True, run_crawler=False)

        # Print executive summary briefing to stdout
        briefing = tracker.generate_briefing(payload, fallback_used=fallback_used)
        print("\n" + briefing + "\n")

        logger.info("Subsidy tracking pipeline finished successfully.")
        return 0

    except Exception as exc:
        logger.exception("Fatal error in subsidy tracker pipeline: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
