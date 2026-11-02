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
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import List, Optional, Set, Tuple, Union

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
    """Adaptively resolve primary and web targets depending on execution directory with bidirectional auto-sync."""
    if (_CURRENT_DIR / "data").exists() and (_CURRENT_DIR / "ev-stealth-web" / "src" / "data").exists():
        # Executing from project root /Users/a7890/src/my-e-car/
        primary_output = _CURRENT_DIR / "data" / "ev_subsidy_data.json"
        web_output = _CURRENT_DIR / "ev-stealth-web" / "src" / "data" / "ev_subsidy_data.json"
        mirror_primary = _CURRENT_DIR / "data" / "subsidy_depletion_data.json"
        mirror_web = _CURRENT_DIR / "ev-stealth-web" / "src" / "data" / "subsidy_depletion_data.json"
        external_sync_targets = [web_output, mirror_web]
        if (_CURRENT_DIR / "ev-stealth-web" / "public" / "data").exists():
            external_sync_targets.extend([
                _CURRENT_DIR / "ev-stealth-web" / "public" / "data" / "ev_subsidy_data.json",
                _CURRENT_DIR / "ev-stealth-web" / "public" / "data" / "subsidy_depletion_data.json",
            ])
        if (_CURRENT_DIR / "public" / "data").exists():
            external_sync_targets.extend([
                _CURRENT_DIR / "public" / "data" / "ev_subsidy_data.json",
                _CURRENT_DIR / "public" / "data" / "subsidy_depletion_data.json",
            ])
        return primary_output, web_output, mirror_primary, mirror_web, external_sync_targets
    elif (_CURRENT_DIR / "src" / "data").exists():
        # Executing from within ev-stealth-web/
        primary_output = _CURRENT_DIR / "src" / "data" / "ev_subsidy_data.json"
        web_output = _CURRENT_DIR / "src" / "data" / "ev_subsidy_data.json"
        mirror_primary = _CURRENT_DIR / "src" / "data" / "subsidy_depletion_data.json"
        mirror_web = _CURRENT_DIR / "src" / "data" / "subsidy_depletion_data.json"
        external_sync_targets: List[Path] = []
        if (_CURRENT_DIR.parent / "data").exists():
            external_sync_targets.append(_CURRENT_DIR.parent / "data" / "ev_subsidy_data.json")
            external_sync_targets.append(_CURRENT_DIR.parent / "data" / "subsidy_depletion_data.json")
        if (_CURRENT_DIR / "public" / "data").exists():
            external_sync_targets.append(_CURRENT_DIR / "public" / "data" / "ev_subsidy_data.json")
            external_sync_targets.append(_CURRENT_DIR / "public" / "data" / "subsidy_depletion_data.json")
        return primary_output, web_output, mirror_primary, mirror_web, external_sync_targets
    else:
        # Executing from project root or fallback
        primary_output = _CURRENT_DIR / "data" / "ev_subsidy_data.json"
        web_output = _CURRENT_DIR / "ev-stealth-web" / "src" / "data" / "ev_subsidy_data.json"
        mirror_primary = _CURRENT_DIR / "data" / "subsidy_depletion_data.json"
        mirror_web = _CURRENT_DIR / "ev-stealth-web" / "src" / "data" / "subsidy_depletion_data.json"
        external_sync_targets = []
        if (_CURRENT_DIR / "ev-stealth-web" / "src" / "data").exists():
            external_sync_targets.extend([web_output, mirror_web])
        elif (_CURRENT_DIR.parent / "data").exists():
            external_sync_targets.extend([
                _CURRENT_DIR.parent / "data" / "ev_subsidy_data.json",
                _CURRENT_DIR.parent / "data" / "subsidy_depletion_data.json",
            ])
        if (_CURRENT_DIR / "ev-stealth-web" / "public" / "data").exists():
            external_sync_targets.extend([
                _CURRENT_DIR / "ev-stealth-web" / "public" / "data" / "ev_subsidy_data.json",
                _CURRENT_DIR / "ev-stealth-web" / "public" / "data" / "subsidy_depletion_data.json",
            ])
        elif (_CURRENT_DIR.parent / "ev-stealth-web" / "public" / "data").exists():
            external_sync_targets.extend([
                _CURRENT_DIR.parent / "ev-stealth-web" / "public" / "data" / "ev_subsidy_data.json",
                _CURRENT_DIR.parent / "ev-stealth-web" / "public" / "data" / "subsidy_depletion_data.json",
            ])
        if (_CURRENT_DIR / "public" / "data").exists():
            external_sync_targets.extend([
                _CURRENT_DIR / "public" / "data" / "ev_subsidy_data.json",
                _CURRENT_DIR / "public" / "data" / "subsidy_depletion_data.json",
            ])
        return primary_output, web_output, mirror_primary, mirror_web, external_sync_targets


(
    DEFAULT_PRIMARY_OUTPUT,
    DEFAULT_WEB_OUTPUT,
    MIRROR_PRIMARY_OUTPUT,
    MIRROR_WEB_OUTPUT,
    EXTERNAL_SYNC_TARGETS,
) = _resolve_default_paths()


def _is_project_data_dir(path: Path, cwd: Path) -> bool:
    """Check if the path points to the real project data directory."""
    try:
        resolved = path.resolve()
        for cand in [cwd / "data", cwd.parent / "data", cwd / "ev-stealth-web" / "src" / "data", cwd / "src" / "data"]:
            if cand.exists() and resolved == cand.resolve():
                return True
    except Exception:
        pass
    return False


def validate_defect_reports_file(file_path: Union[str, Path]) -> bool:
    """Validate that target file contains valid JSON syntax and expected schema ('reports' list key)."""
    from tracker.atomic_writer import is_corrupted_or_quarantined_filename

    p = Path(file_path)
    if is_corrupted_or_quarantined_filename(p):
        return False
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
    quarantine_corrupted: bool = True,
    root_dir: Optional[Union[str, Path]] = None,
) -> List[str]:
    """Synchronize defect reports (daily_reports.json) between root data/ and web src/data/.

    Ensures both locations are bitwise synchronized and crash-durably mirrored.
    Validates source file JSON syntax and schema ('reports' key) before performing
    atomic file replacement based on st_mtime. Never propagates corrupt files.
    Quarantines corrupted candidate/target files when quarantine_corrupted is True.
    Protected by FileLock to eliminate race conditions during concurrent multi-process synchronization.
    If run_crawler is True, executes the crawler pipeline before synchronizing.
    """
    from tracker.atomic_writer import (
        FileLock,
        is_corrupted_or_quarantined_filename,
        quarantine_corrupted_file,
    )

    logger.info("Synchronizing defect reports (daily_reports.json)...")
    if dry_run:
        logger.info("[DRY-RUN] Defect reports synchronization skipped file persistence.")
        return []

    # Resolve web, root, and public paths
    if web_dir:
        web_reports_path = Path(web_dir) / "daily_reports.json"
    elif (_CURRENT_DIR / "ev-stealth-web" / "src" / "data").exists():
        web_reports_path = _CURRENT_DIR / "ev-stealth-web" / "src" / "data" / "daily_reports.json"
    elif (_CURRENT_DIR / "src" / "data").exists():
        web_reports_path = _CURRENT_DIR / "src" / "data" / "daily_reports.json"
    else:
        web_reports_path = _CURRENT_DIR / "ev-stealth-web" / "src" / "data" / "daily_reports.json"

    if root_dir:
        root_reports_path = Path(root_dir) / "daily_reports.json"
    elif (_CURRENT_DIR / "data").exists():
        root_reports_path = _CURRENT_DIR / "data" / "daily_reports.json"
    else:
        root_reports_path = _CURRENT_DIR.parent / "data" / "daily_reports.json"

    public_reports_paths: List[Path] = []
    if web_dir and (Path(web_dir).parent / "public" / "data").exists():
        public_reports_paths.append(Path(web_dir).parent / "public" / "data" / "daily_reports.json")
    if web_dir and (Path(web_dir).parent.parent / "public" / "data").exists():
        public_reports_paths.append(Path(web_dir).parent.parent / "public" / "data" / "daily_reports.json")
    if root_dir and (Path(root_dir).parent / "public" / "data").exists():
        public_reports_paths.append(Path(root_dir).parent / "public" / "data" / "daily_reports.json")
    is_custom_run = (root_dir is not None) or (web_dir is not None and not _is_project_data_dir(Path(web_dir), _CURRENT_DIR))
    if not is_custom_run:
        if (_CURRENT_DIR / "ev-stealth-web" / "public" / "data").exists():
            public_reports_paths.append(_CURRENT_DIR / "ev-stealth-web" / "public" / "data" / "daily_reports.json")
        if (_CURRENT_DIR / "public" / "data").exists():
            public_reports_paths.append(_CURRENT_DIR / "public" / "data" / "daily_reports.json")
        if (_CURRENT_DIR.parent / "ev-stealth-web" / "public" / "data").exists():
            public_reports_paths.append(_CURRENT_DIR.parent / "ev-stealth-web" / "public" / "data" / "daily_reports.json")

    # Deduplicate public paths preserving order
    seen_pub = set()
    deduped_public: List[Path] = []
    for p in public_reports_paths:
        r_str = str(p.resolve()) if p.exists() else str(p.absolute())
        if r_str not in seen_pub:
            seen_pub.add(r_str)
            deduped_public.append(p)

    sync_lock_path = root_reports_path.parent / ".sync_defect_reports.lock"
    written_paths: List[str] = []

    with FileLock(sync_lock_path):
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
            except Exception as exc:
                logger.warning(
                    "Crawler execution in sync_defect_reports encountered: %s. Falling back to mirror synchronization.",
                    exc,
                )

        def _candidate_score(cand_path: Path) -> Tuple[int, int, float]:
            try:
                with open(cand_path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                r_list = d.get("reports", []) if isinstance(d, dict) else []
                num_reports = len(r_list)
                return (1 if num_reports >= 4 else 0, num_reports, cand_path.stat().st_mtime)
            except Exception:
                return (0, 0, 0.0)

        known_paths: List[Path] = [root_reports_path, web_reports_path] + deduped_public
        candidate_paths: List[Path] = [p for p in known_paths if p.exists()]
        try:
            candidate_paths.sort(key=_candidate_score, reverse=True)
        except Exception:
            pass

        source_path: Optional[Path] = None
        for cand in candidate_paths:
            if is_corrupted_or_quarantined_filename(cand):
                continue
            if validate_defect_reports_file(cand):
                source_path = cand
                break
            elif quarantine_corrupted:
                quarantine_corrupted_file(cand)

        if not source_path:
            logger.error(
                "No candidate defect report file is valid among %s. Aborting sync to prevent corruption propagation.",
                candidate_paths,
            )
            return []

        target_paths: List[Path] = []
        seen_target_abs: Set[str] = {str(Path(source_path).resolve())}
        for p in known_paths:
            resolved_p = str(Path(p).resolve())
            if resolved_p not in seen_target_abs and (p.parent.exists() or p.parent.parent.exists()):
                seen_target_abs.add(resolved_p)
                target_paths.append(p)

        if source_path and target_paths and validate_defect_reports_file(source_path):
            try:
                source_stat = source_path.stat()
                h_src = hashlib.sha256()
                with open(source_path, "rb") as sf:
                    while chunk := sf.read(65536):
                        h_src.update(chunk)
                source_hash = h_src.hexdigest()
            except Exception as e:
                logger.error("Failed to inspect source defect report %s: %s", source_path, e)
                return []

            for tgt in target_paths:
                if tgt.exists():
                    if is_corrupted_or_quarantined_filename(tgt):
                        continue
                    if not validate_defect_reports_file(tgt):
                        if quarantine_corrupted:
                            quarantine_corrupted_file(tgt)
                    else:
                        try:
                            h_tgt = hashlib.sha256()
                            with open(tgt, "rb") as tf_in:
                                while chunk := tf_in.read(65536):
                                    h_tgt.update(chunk)
                            if h_tgt.hexdigest() == source_hash:
                                try:
                                    tgt_stat = tgt.stat()
                                    if tgt_stat.st_mtime != source_stat.st_mtime:
                                        os.utime(tgt, (source_stat.st_atime, source_stat.st_mtime))
                                except OSError:
                                    pass
                                logger.debug("Skipping redundant defect report sync for %s (SHA-256 match)", tgt)
                                continue
                        except Exception as e:
                            logger.warning("Error verifying SHA-256 on target %s: %s", tgt, e)

                temp_name = None
                try:
                    tgt.parent.mkdir(parents=True, exist_ok=True)
                    with tempfile.NamedTemporaryFile("wb", dir=str(tgt.parent), delete=False, prefix=".tmp_sync_") as tf:
                        temp_name = tf.name
                        with open(source_path, "rb") as sf:
                            shutil.copyfileobj(sf, tf)
                        tf.flush()
                        os.fsync(tf.fileno())
                    try:
                        os.chmod(temp_name, 0o644)
                    except OSError:
                        pass
                    os.replace(temp_name, tgt)
                    # Preserve original source timestamp to prevent oscillation
                    try:
                        os.utime(tgt, (source_stat.st_atime, source_stat.st_mtime))
                    except OSError:
                        pass
                    # Directory fsync to commit new target file
                    try:
                        dir_fd = os.open(str(tgt.parent), os.O_RDONLY)
                        os.fsync(dir_fd)
                        os.close(dir_fd)
                    except OSError:
                        pass

                    written_paths.append(str(tgt))
                    logger.info("  ✓ Successfully synchronized defect reports: %s -> %s", source_path, tgt)
                except Exception as e:
                    logger.warning("Failed to synchronize defect report to %s: %s", tgt, e)
                finally:
                    if temp_name and os.path.exists(temp_name):
                        try:
                            os.unlink(temp_name)
                        except OSError:
                            pass

    deduped_written: List[str] = []
    for p_str in written_paths:
        if p_str not in deduped_written:
            deduped_written.append(p_str)

    return deduped_written


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
    web_dir_env = (os.getenv("EV_TRACKER_WEB_DIR") or os.getenv("EV_WEB_DIR") or "").strip()
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
    endpoint_env = (os.getenv("EV_SUBSIDY_API_ENDPOINT") or "").strip() or None
    parser.add_argument(
        "--endpoint",
        type=str,
        default=endpoint_env,
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
    parsed = parser.parse_args(args)

    # Sanitize and defend against empty string or bare directory output paths
    if parsed.output is not None:
        raw_out_str = str(parsed.output).strip()
        if not raw_out_str or raw_out_str == ".":
            parsed.output = DEFAULT_PRIMARY_OUTPUT
        elif parsed.output.is_dir():
            parsed.output = parsed.output / "ev_subsidy_data.json"
    else:
        parsed.output = DEFAULT_PRIMARY_OUTPUT

    # Sanitize custom web directory argument
    if parsed.web_dir is not None:
        raw_web_str = str(parsed.web_dir).strip()
        if not raw_web_str or raw_web_str == ".":
            parsed.web_dir = None
        else:
            parsed.web_dir = Path(raw_web_str)

    # Sanitize endpoint URL
    if parsed.endpoint is not None:
        raw_ep = parsed.endpoint.strip()
        parsed.endpoint = raw_ep if raw_ep else None

    return parsed


parse_args = parse_arguments


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint execution loop."""
    try:
        args = parse_arguments(argv)
        setup_logging(args.verbose)

        logger.info("Initializing Autonomous EV Subsidy Tracker...")
        logger.info("Configuration: dry_run=%s, sync_web=%s, output=%s", args.dry_run, args.sync_web, args.output)
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
            for idx, r in enumerate(payload.regions):
                payload.regions[idx] = tracker.update_region_metrics(r)
            payload.nationwide_summary = tracker.compute_nationwide_summary(payload.regions)
            payload.metadata.generated_at = datetime.now(timezone.utc).isoformat()
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

            # Check if bidirectional automatic synchronization applies:
            # If both root data/ and web src/data/ exist in the tree, and the output is targeting
            # the default or repository data directories, automatically synchronize to both locations
            # even if --sync-web was omitted.
            root_data_dir: Optional[Path] = None
            if (_CURRENT_DIR / "data").exists():
                root_data_dir = _CURRENT_DIR / "data"
            elif (_CURRENT_DIR.parent / "data").exists():
                root_data_dir = _CURRENT_DIR.parent / "data"

            web_data_dir: Optional[Path] = None
            if (_CURRENT_DIR / "ev-stealth-web" / "src" / "data").exists():
                web_data_dir = _CURRENT_DIR / "ev-stealth-web" / "src" / "data"
            elif (_CURRENT_DIR / "src" / "data").exists():
                web_data_dir = _CURRENT_DIR / "src" / "data"

            both_data_dirs_exist = (
                root_data_dir is not None
                and root_data_dir.is_dir()
                and web_data_dir is not None
                and web_data_dir.is_dir()
            )

            is_default_or_repo_target = False
            try:
                resolved_output = args.output.resolve()
                repo_target_dirs: List[Path] = []
                if root_data_dir and root_data_dir.exists():
                    repo_target_dirs.append(root_data_dir.resolve())
                if web_data_dir and web_data_dir.exists():
                    repo_target_dirs.append(web_data_dir.resolve())

                known_targets: Set[Path] = {
                    DEFAULT_PRIMARY_OUTPUT.resolve(),
                    DEFAULT_WEB_OUTPUT.resolve(),
                    MIRROR_PRIMARY_OUTPUT.resolve(),
                    MIRROR_WEB_OUTPUT.resolve(),
                }
                for ext in EXTERNAL_SYNC_TARGETS:
                    try:
                        known_targets.add(ext.resolve())
                    except Exception:
                        pass

                if resolved_output in known_targets:
                    is_default_or_repo_target = True
                elif resolved_output.parent in repo_target_dirs:
                    is_default_or_repo_target = True
            except Exception:
                is_default_or_repo_target = (args.output == DEFAULT_PRIMARY_OUTPUT)

            auto_bidirectional = both_data_dirs_exist and is_default_or_repo_target

            if args.sync_web or auto_bidirectional:
                if args.web_dir:
                    web_dir = Path(args.web_dir)
                    destinations.append(web_dir / "ev_subsidy_data.json")
                    destinations.append(web_dir / "subsidy_depletion_data.json")
                    destinations.append(DEFAULT_PRIMARY_OUTPUT)
                    destinations.append(MIRROR_PRIMARY_OUTPUT)
                    destinations.extend(EXTERNAL_SYNC_TARGETS)
                else:
                    destinations.append(DEFAULT_WEB_OUTPUT)
                    destinations.append(MIRROR_WEB_OUTPUT)
                    destinations.append(DEFAULT_PRIMARY_OUTPUT)
                    destinations.append(MIRROR_PRIMARY_OUTPUT)
                    destinations.extend(EXTERNAL_SYNC_TARGETS)

            # Deduplicate destinations while preserving order
            unique_destinations: List[Path] = []
            seen_paths: Set[str] = set()
            for dst in destinations:
                resolved_str = str(dst.resolve())
                if resolved_str not in seen_paths:
                    seen_paths.add(resolved_str)
                    unique_destinations.append(dst)

            from tracker.atomic_writer import FileLock

            subsidy_lock_path = args.output.parent / ".subsidy_sync.lock"
            with FileLock(subsidy_lock_path):
                logger.info("Saving subsidy datasets to %d target path(s)...", len(unique_destinations))
                written_paths = tracker.save_payload(payload, unique_destinations)
                for wp in written_paths:
                    logger.info("  ✓ Successfully written: %s", wp)

            # Synchronize defect reports alongside subsidy data when syncing web or auto-bidirectional
            if args.sync_web or auto_bidirectional or (args.sync_defects is True):
                if getattr(args, "sync_defects", None) is not False:
                    sync_defect_reports(
                        web_dir=args.web_dir,
                        dry_run=False,
                        run_crawler=bool(args.sync_defects is True),
                        quarantine_corrupted=getattr(args, "quarantine_corrupted", True),
                    )
        else:
            logger.info("Dry-run requested: skipping file persistence.")
            both_exist = (
                ((_CURRENT_DIR / "data").is_dir() or (_CURRENT_DIR.parent / "data").is_dir())
                and ((_CURRENT_DIR / "ev-stealth-web" / "src" / "data").is_dir() or (_CURRENT_DIR / "src" / "data").is_dir())
            )
            try:
                is_target = (args.output.resolve() == DEFAULT_PRIMARY_OUTPUT.resolve()) or (args.output == DEFAULT_PRIMARY_OUTPUT)
            except Exception:
                is_target = (args.output == DEFAULT_PRIMARY_OUTPUT)
            auto_bidirectional = both_exist and is_target
            if args.sync_web or auto_bidirectional or (args.sync_defects is True):
                if getattr(args, "sync_defects", None) is not False:
                    sync_defect_reports(
                        web_dir=args.web_dir,
                        dry_run=True,
                        run_crawler=False,
                        quarantine_corrupted=getattr(args, "quarantine_corrupted", True),
                    )

        # Print executive summary briefing to stdout
        briefing = tracker.generate_briefing(payload, fallback_used=fallback_used)
        print("\n" + briefing + "\n")

        logger.info("Subsidy tracking pipeline finished successfully.")
        return 0

    except KeyboardInterrupt:
        logger.warning("Subsidy tracker pipeline cancelled by user.")
        return 1
    except SystemExit as se:
        return se.code if isinstance(se.code, int) else 1
    except Exception as exc:
        logger.exception("Fatal error in subsidy tracker pipeline: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
