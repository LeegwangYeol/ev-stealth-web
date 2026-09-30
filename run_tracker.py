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
import logging
import os
from pathlib import Path
import sys
from typing import List, Set

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


def setup_logging(verbose: bool = False) -> None:
    """Configure structured logging."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_arguments() -> argparse.Namespace:
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
    return parser.parse_args()


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

        if not args.dry_run:
            destinations: List[Path] = [args.output]

            # If writing to default primary output, also create mirror subsidy_depletion_data.json
            if args.output == DEFAULT_PRIMARY_OUTPUT:
                destinations.append(MIRROR_PRIMARY_OUTPUT)

            if args.sync_web:
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
        else:
            logger.info("Dry-run requested: skipping file persistence.")

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
