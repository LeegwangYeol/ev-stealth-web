#!/usr/bin/env python3
"""
Master CLI Entrypoint & Daily Scraper Pipeline Runner.

Orchestrates Korean EV community crawlers (BobaeDream, DCInside),
contextual defect filtering, and daily structured JSON report synchronization
to Next.js admin reporting dashboard.

Authoritative specifications:
- /Users/a7890/src/my-e-car/.agents/orchestrator_daily_monitor/PROJECT.md § Interface Contracts
- /Users/a7890/src/my-e-car/.agents/spec_miner_nlp_workflow/specifications.md § 3
"""

from __future__ import annotations

import argparse
import datetime
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import sys
import tempfile
import threading
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union

# Ensure bot and project roots are present in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
POSSIBLE_ROOTS = [
    CURRENT_DIR,
    CURRENT_DIR.parent,
    CURRENT_DIR / "ev-stealth-web",
    CURRENT_DIR.parent / "ev-stealth-web",
    CURRENT_DIR.parent / "ev_daily_monitor_bot",
    CURRENT_DIR.parent / "my-e-car",
]
for root_path in reversed(POSSIBLE_ROOTS):
    if root_path.exists():
        if str(root_path) in sys.path:
            sys.path.remove(str(root_path))
        sys.path.insert(0, str(root_path))

# Dynamic imports with fallback aliases
from crawlers.bobaedream import BobaeDreamCrawler
from crawlers.dcinside import DCInsideCrawler
from models.complaint import ComplaintRecord, RawPost
try:
    from models.defect_report import DefectReport
except ImportError:
    DefectReport = ComplaintRecord  # type: ignore

from utils.http_client import SafeHttpClient
from utils.json_writer import (
    DEFAULT_OUTPUT_PATH,
    format_daily_report_payload,
    read_daily_reports,
    write_daily_reports,
)

try:
    from filters.defect_classifier import DefectClassifier as DefectFilter
except ImportError:
    try:
        from filters.defect_filter import ContextualDefectFilter as DefectFilter
    except ImportError:
        from filters.defect_filter import DefectFilter  # type: ignore

logger = logging.getLogger("ScraperRunner")

_SHUTDOWN_REQUESTED = False


def _signal_handler(signum: int, frame: Any) -> None:
    """Handle termination signals by setting shutdown flag and raising exception for graceful unwind."""
    global _SHUTDOWN_REQUESTED
    _SHUTDOWN_REQUESTED = True
    sig_name = signal.Signals(signum).name if hasattr(signal, "Signals") else f"signal {signum}"
    logger.warning(f"Received termination {sig_name}. Halting scraper pipeline gracefully...")
    if signum == signal.SIGINT:
        raise KeyboardInterrupt(f"Scraper runner interrupted by {sig_name}")
    else:
        raise SystemExit(128 + signum)


def setup_signal_handlers() -> None:
    """Register graceful termination signal handlers for SIGINT and SIGTERM."""
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, _signal_handler)
            except (ValueError, OSError, AttributeError):
                pass


def _find_repo_root() -> Path:
    """Locate canonical repository root directory resilient to symlinks and nested execution."""
    candidates = [
        CURRENT_DIR,
        CURRENT_DIR.parent,
        CURRENT_DIR.parent.parent,
        Path.cwd(),
        Path.cwd().parent,
    ]
    for c in candidates:
        if (c / "data").is_dir() and (
            (c / "ev-stealth-web").is_dir()
            or (c / "run_scraper.py").is_file()
            or (c / "run_tracker.py").is_file()
        ):
            return c.resolve()
    if CURRENT_DIR.name == "ev-stealth-web":
        return CURRENT_DIR.parent.resolve()
    return CURRENT_DIR.resolve()


REPO_ROOT = _find_repo_root()


def _resolve_web_reports_path(custom_web_dir: Optional[Union[str, Path]] = None) -> Path:
    if custom_web_dir:
        raw_web = str(custom_web_dir).strip()
        if raw_web and raw_web != ".":
            return Path(raw_web) / "daily_reports.json"
    env_dir = (
        os.getenv("EV_SCRAPER_WEB_DIR")
        or os.getenv("EV_TRACKER_WEB_DIR")
        or os.getenv("EV_WEB_DIR")
        or ""
    ).strip()
    if env_dir and env_dir != ".":
        return Path(env_dir) / "daily_reports.json"
    candidates = [
        REPO_ROOT / "ev-stealth-web" / "src" / "data" / "daily_reports.json",
        REPO_ROOT / "src" / "data" / "daily_reports.json",
        CURRENT_DIR / "ev-stealth-web" / "src" / "data" / "daily_reports.json",
        CURRENT_DIR / "src" / "data" / "daily_reports.json",
        CURRENT_DIR.parent / "ev-stealth-web" / "src" / "data" / "daily_reports.json",
        CURRENT_DIR.parent / "src" / "my-e-car" / "ev-stealth-web" / "src" / "data" / "daily_reports.json",
    ]
    for c in candidates:
        if c.parent.exists():
            return c.resolve()
    return candidates[0].resolve()


def _resolve_public_reports_path(custom_web_dir: Optional[Union[str, Path]] = None) -> Path:
    """Resolve repository public data/daily_reports.json path for Triple Mirror Parity."""
    candidates = [
        REPO_ROOT / "ev-stealth-web" / "public" / "data" / "daily_reports.json",
        REPO_ROOT / "public" / "data" / "daily_reports.json",
        CURRENT_DIR / "ev-stealth-web" / "public" / "data" / "daily_reports.json",
        CURRENT_DIR / "public" / "data" / "daily_reports.json",
        CURRENT_DIR.parent / "ev-stealth-web" / "public" / "data" / "daily_reports.json",
        CURRENT_DIR.parent / "src" / "my-e-car" / "ev-stealth-web" / "public" / "data" / "daily_reports.json",
    ]
    if custom_web_dir:
        raw_web = str(custom_web_dir).strip()
        if raw_web and raw_web != ".":
            custom_public = Path(raw_web).parent / "public" / "data" / "daily_reports.json"
            candidates.insert(0, custom_public)
            custom_public_2 = Path(raw_web).parent.parent / "public" / "data" / "daily_reports.json"
            candidates.insert(1, custom_public_2)
    for c in candidates:
        if c.parent.exists():
            return c.resolve()
    return candidates[0].resolve()


def _resolve_root_reports_path() -> Path:
    """Resolve repository root data/daily_reports.json path."""
    candidates = [
        REPO_ROOT / "data" / "daily_reports.json",
        CURRENT_DIR / "data" / "daily_reports.json",
        CURRENT_DIR.parent / "data" / "daily_reports.json",
        CURRENT_DIR.parent.parent / "data" / "daily_reports.json",
    ]
    for c in candidates:
        if c.parent.exists():
            return c.resolve()
    return candidates[0].resolve()


def _atomic_copy_file(src_path: Union[str, Path], dest_path: Union[str, Path]) -> str:
    """Atomically copy a file to dest_path using tempfile + os.replace."""
    dest = Path(dest_path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("wb", dir=str(dest.parent), delete=False, prefix=".tmp_sync_") as tf:
            temp_name = tf.name
            with open(src_path, "rb") as sf:
                shutil.copyfileobj(sf, tf)
            tf.flush()
            os.fsync(tf.fileno())
        try:
            os.chmod(temp_name, 0o644)
        except OSError:
            pass
        os.replace(temp_name, dest)
        return str(dest)
    finally:
        if temp_name and os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass


WEB_DATA_DAILY_REPORTS_PATH = str(_resolve_web_reports_path())


def configure_logging(verbose: bool = False) -> None:
    """Configure stdout logging with proper timestamps and levels."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )


def parse_target_date(date_str: Optional[str]) -> Optional[str]:
    """Parse and normalize target date CLI argument to ISO-8601 string.

    Accepts:
    - YYYY-MM-DD, YYYY.MM.DD, YYYY/MM/DD
    - Full ISO-8601 strings (e.g. 2026-11-04T00:00:00Z)
    Raises argparse.ArgumentTypeError on malformed date string.
    """
    if not date_str:
        return None
    val = str(date_str).strip()
    if not val:
        return None

    m_simple = re.match(r"^(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})$", val)
    if m_simple:
        y, m, d = int(m_simple.group(1)), int(m_simple.group(2)), int(m_simple.group(3))
        try:
            dt = datetime.datetime(y, m, d, 0, 0, 0, tzinfo=datetime.timezone.utc)
            return dt.isoformat()
        except ValueError as e:
            raise argparse.ArgumentTypeError(f"Invalid calendar date '{val}': {e}")

    clean_iso = val.replace("Z", "+00:00")
    try:
        dt = datetime.datetime.fromisoformat(clean_iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        return dt.isoformat()
    except Exception:
        raise argparse.ArgumentTypeError(
            f"Invalid target date '{val}'. Expected YYYY-MM-DD or ISO-8601 string."
        )


def create_parser() -> argparse.ArgumentParser:
    """Create CLI argument parser adhering to PROJECT.md and specifications.md."""
    parser = argparse.ArgumentParser(
        prog="run_scraper",
        description="Master CLI entrypoint for Daily EV Defect Scraper & NLP Classification Pipeline.",
    )
    parser.add_argument(
        "--sources",
        "--source",
        "-m",
        "--mode",
        dest="sources",
        default="all",
        help="Target community sources to harvest (all, bobaedream, dcinside).",
    )
    parser.add_argument(
        "--limit",
        "-l",
        type=int,
        default=20,
        help="Maximum posts to crawl per community board/gallery (default: 20, minimum: 1).",
    )
    parser.add_argument(
        "--target-date",
        "--date",
        dest="target_date",
        type=parse_target_date,
        default=None,
        help="Target publication or report date (YYYY-MM-DD or ISO-8601).",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Target file path for daily reports JSON.",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        dest="output_path",
        default=None,
        help="Alias for --output path.",
    )
    parser.add_argument(
        "--sync-web",
        "-s",
        action="store_true",
        default=False,
        help=f"Directly write daily report JSON to Next.js admin data directory ({WEB_DATA_DAILY_REPORTS_PATH}).",
    )
    web_dir_env = (
        os.getenv("EV_SCRAPER_WEB_DIR")
        or os.getenv("EV_TRACKER_WEB_DIR")
        or os.getenv("EV_WEB_DIR")
        or ""
    ).strip()
    parser.add_argument(
        "--web-dir",
        type=Path,
        default=Path(web_dir_env) if web_dir_env else None,
        help="Custom web directory to sync data files into (overrides default ev-stealth-web/src/data/ or EV_SCRAPER_WEB_DIR).",
    )
    parser.add_argument(
        "--dry-run",
        "-d",
        action="store_true",
        default=False,
        help="Execute crawling and classification in memory without writing reports to disk.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Enable detailed DEBUG logging.",
    )
    return parser


class ScraperPipeline:
    """Orchestrates community crawlers, NLP defect classification, and report publishing."""

    def __init__(
        self,
        bobae_crawler: Optional[BobaeDreamCrawler] = None,
        dc_crawler: Optional[DCInsideCrawler] = None,
        defect_filter: Optional[Any] = None,
        client: Optional[SafeHttpClient] = None,
    ):
        self.client = client or SafeHttpClient(min_delay=1.0, max_delay=2.5, enable_jitter=True)
        self.bobae_crawler = bobae_crawler or BobaeDreamCrawler(client=self.client)
        self.dc_crawler = dc_crawler or DCInsideCrawler(client=self.client)
        self.defect_filter = defect_filter or DefectFilter()

    def harvest_bobaedream(self, limit: int) -> List[Dict[str, Any]]:
        """Harvest recent EV discussions from BobaeDream boards."""
        posts: List[Dict[str, Any]] = []
        target_boards = ["national", "electric", "import"]

        for board in target_boards:
            if _SHUTDOWN_REQUESTED:
                logger.warning("Shutdown requested. Halting BobaeDream crawl.")
                break
            try:
                logger.info(f"Crawling BobaeDream board '{board}' (limit={limit})...")
                board_posts = self.bobae_crawler.crawl_board(board, pages=1, limit=limit)
                posts.extend(board_posts)
                if len(posts) >= limit:
                    break
            except Exception as e:
                logger.warning(f"Error while crawling BobaeDream board '{board}': {e}")

        # If board crawl returned few or no posts, fallback to EV keyword search
        if not _SHUTDOWN_REQUESTED and len(posts) < limit:
            remaining = limit - len(posts)
            try:
                logger.info(f"Searching BobaeDream for '전기차' (remaining limit={remaining})...")
                search_posts = self.bobae_crawler.crawl_posts_by_keyword("전기차", boards=["national", "electric", "import"], limit=remaining)
                posts.extend(search_posts)
            except Exception as e:
                logger.warning(f"Error while searching BobaeDream: {e}")

        return posts[:limit]

    def harvest_dcinside(self, limit: int) -> List[Dict[str, Any]]:
        """Harvest recent EV discussions from DCInside galleries."""
        posts: List[Dict[str, Any]] = []
        target_galleries = ["car_new1", "electriccar", "tesla", "ioniq", "byd"]

        for gall in target_galleries:
            if _SHUTDOWN_REQUESTED:
                logger.warning("Shutdown requested. Halting DCInside crawl.")
                break
            try:
                logger.info(f"Crawling DCInside gallery '{gall}' (limit={limit})...")
                gall_posts = self.dc_crawler.crawl_gallery(gall, pages=1, limit=limit)
                posts.extend(gall_posts)
                if len(posts) >= limit:
                    break
            except Exception as e:
                logger.warning(f"Error while crawling DCInside gallery '{gall}': {e}")

        # Fallback to EV search if gallery listings yielded fewer posts
        if not _SHUTDOWN_REQUESTED and len(posts) < limit:
            remaining = limit - len(posts)
            try:
                logger.info(f"Searching DCInside for '전기차' (remaining limit={remaining})...")
                search_posts = self.dc_crawler.crawl_posts_by_keyword("전기차", galleries=["car_new1", "electriccar", "tesla", "ioniq", "byd"], limit=remaining)
                posts.extend(search_posts)
            except Exception as e:
                logger.warning(f"Error while searching DCInside: {e}")

        return posts[:limit]

    def harvest(self, source_choice: Any, limit: Any = 20) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """Harvest raw post dictionaries based on selected source mode."""
        # Support comma-separated strings (e.g. "bobaedream,dcinside"), lists, aliases
        if isinstance(source_choice, (list, tuple, set)):
            raw_sources = [str(s).lower().strip() for s in source_choice]
        else:
            raw_sources = [s.strip().lower() for s in str(source_choice or "all").split(",") if s.strip()]

        selected_sources: Set[str] = set()
        for s in raw_sources:
            if s in ("all", "*"):
                selected_sources.update(["bobaedream", "dcinside"])
            elif s in ("bobaedream", "bobae", "b"):
                selected_sources.add("bobaedream")
            elif s in ("dcinside", "dc", "d"):
                selected_sources.add("dcinside")
            else:
                logger.warning(f"Unknown source '{s}', falling back to 'all'")
                selected_sources.update(["bobaedream", "dcinside"])

        try:
            clamped_limit = min(500, max(1, int(limit)))
        except (ValueError, TypeError):
            clamped_limit = 20

        raw_posts: List[Dict[str, Any]] = []
        stats: Dict[str, int] = {"bobaedream": 0, "dcinside": 0}

        if "bobaedream" in selected_sources:
            if _SHUTDOWN_REQUESTED:
                logger.warning("Shutdown requested. Skipping BobaeDream harvest.")
            else:
                try:
                    bobae_posts = self.harvest_bobaedream(limit=clamped_limit)
                    raw_posts.extend(bobae_posts)
                    stats["bobaedream"] = len(bobae_posts)
                except Exception as e:
                    logger.warning(f"BobaeDream crawler encountered an unhandled error: {e}")

        if "dcinside" in selected_sources:
            if _SHUTDOWN_REQUESTED:
                logger.warning("Shutdown requested. Skipping DCInside harvest.")
            else:
                try:
                    dc_posts = self.harvest_dcinside(limit=clamped_limit)
                    raw_posts.extend(dc_posts)
                    stats["dcinside"] = len(dc_posts)
                except Exception as e:
                    logger.warning(f"DCInside crawler encountered an unhandled error: {e}")

        return raw_posts, stats

    def filter_defects(self, raw_post_dicts: Optional[Iterable[Any]]) -> List[ComplaintRecord]:
        """Classify raw post dictionaries through 4-stage DefectFilter."""
        defects: List[ComplaintRecord] = []
        if not raw_post_dicts:
            return defects

        for p_dict in raw_post_dicts:
            if p_dict is None:
                continue
            try:
                raw_post = RawPost.from_dict(p_dict)
                complaint = self.defect_filter.process_post(raw_post)
                if complaint.is_authentic_defect:
                    defects.append(complaint)
            except Exception as e:
                post_id_val = "unknown"
                if isinstance(p_dict, dict):
                    post_id_val = str(p_dict.get("post_id") or p_dict.get("id") or "unknown")
                elif hasattr(p_dict, "post_id"):
                    post_id_val = str(getattr(p_dict, "post_id") or "unknown")
                elif hasattr(p_dict, "id"):
                    post_id_val = str(getattr(p_dict, "id") or "unknown")
                logger.warning(f"Failed to process post {post_id_val}: {e}")
        return defects

    def run(
        self,
        sources: str = "all",
        limit: int = 20,
        output_path: Optional[str] = None,
        sync_web: bool = False,
        dry_run: bool = False,
        verbose: bool = False,
        web_dir: Optional[Union[str, Path]] = None,
        target_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute end-to-end harvest, filter, and report publishing pipeline."""
        configure_logging(verbose)
        try:
            clamped_limit = max(1, int(limit))
        except (ValueError, TypeError):
            clamped_limit = 20

        logger.info(
            f"Starting scraper pipeline: sources={sources}, limit={clamped_limit}, "
            f"sync_web={sync_web}, dry_run={dry_run}, target_date={target_date}"
        )

        # 1. Harvest raw posts
        raw_posts, harvest_stats = self.harvest(source_choice=sources, limit=clamped_limit)
        total_scraped = len(raw_posts)
        logger.info(
            f"Harvest complete. Total scraped: {total_scraped} "
            f"(BobaeDream: {harvest_stats.get('bobaedream', 0)}, DCInside: {harvest_stats.get('dcinside', 0)})"
        )

        # 2. Filter & classify defect complaints
        defect_complaints = self.filter_defects(raw_posts)
        logger.info(
            f"NLP classification complete. Authentic defects identified: {len(defect_complaints)} / {total_scraped}"
        )

        # 3. Determine output file targets
        target_paths: List[str] = []
        custom_out = output_path.strip() if output_path and output_path.strip() else None

        if custom_out:
            target_paths.append(os.path.abspath(custom_out))
        if sync_web:
            resolved_web_path = _resolve_web_reports_path(web_dir)
            target_paths.append(os.path.abspath(str(resolved_web_path)))
            resolved_public_path = _resolve_public_reports_path(web_dir)
            target_paths.append(os.path.abspath(str(resolved_public_path)))
            resolved_root_path = _resolve_root_reports_path()
            target_paths.append(os.path.abspath(str(resolved_root_path)))
        if not target_paths:
            target_paths.append(os.path.abspath(DEFAULT_OUTPUT_PATH))

        # Deduplicate paths while preserving order
        unique_paths: List[str] = []
        for path_str in target_paths:
            if path_str not in unique_paths:
                unique_paths.append(path_str)

        # Normal write mode with graceful degradation and bitwise parity replication
        now_iso = target_date or datetime.datetime.now(datetime.timezone.utc).isoformat()

        # 4. Handle persistence or dry-run
        results_summary: Dict[str, Any] = {
            "total_scraped": total_scraped,
            "total_filtered_defects": len(defect_complaints),
            "harvest_stats": harvest_stats,
            "target_paths": unique_paths,
            "dry_run": dry_run,
            "written_paths": [],
            "preserved_paths": [],
            "target_date": now_iso,
        }

        if dry_run:
            logger.info(
                f"[DRY-RUN] Processed {total_scraped} raw posts; "
                f"{len(defect_complaints)} authentic defects identified. "
                f"Skipping disk write for targets: {unique_paths}."
            )
            return results_summary
        primary_written: Optional[str] = None

        # If scrape produced 0 defects, check if an existing authentic mirror file already exists
        existing_mirror: Optional[str] = None
        if len(defect_complaints) == 0:
            for p in unique_paths:
                if os.path.exists(p) and os.path.isfile(p) and os.path.getsize(p) > 0:
                    existing_mirror = p
                    break

        for out_path in unique_paths:
            try:
                if len(defect_complaints) > 0:
                    if primary_written is None:
                        written_path = write_daily_reports(
                            complaints=defect_complaints,
                            output_path=out_path,
                            total_scraped=total_scraped,
                            generated_at=now_iso,
                        )
                        primary_written = written_path
                    else:
                        _atomic_copy_file(primary_written, out_path)
                        written_path = out_path
                    results_summary["written_paths"].append(written_path)
                    logger.info(f"Successfully published daily reports to: {written_path}")
                else:
                    # Graceful degradation: preserve existing data if file exists and scrape is empty
                    if os.path.exists(out_path):
                        logger.warning(
                            f"Scrape produced 0 authentic defects. Preserving existing reports at {out_path}."
                        )
                        results_summary["preserved_paths"].append(out_path)
                    elif existing_mirror is not None:
                        # Replicate authentic content from the existing mirror instead of creating an empty payload
                        logger.warning(
                            f"Scrape produced 0 authentic defects and {out_path} does not exist. "
                            f"Replicating authentic contents from existing mirror at {existing_mirror}."
                        )
                        _atomic_copy_file(existing_mirror, out_path)
                        results_summary["written_paths"].append(out_path)
                    else:
                        logger.warning(
                            f"Scrape produced 0 authentic defects and {out_path} does not exist. "
                            f"Initializing empty daily reports payload."
                        )
                        if primary_written is None:
                            written_path = write_daily_reports(
                                complaints=[],
                                output_path=out_path,
                                total_scraped=total_scraped,
                                generated_at=now_iso,
                            )
                            primary_written = written_path
                        else:
                            _atomic_copy_file(primary_written, out_path)
                            written_path = out_path
                        results_summary["written_paths"].append(written_path)
            except Exception as e:
                logger.error(f"Failed to write daily reports to {out_path}: {e}")
                raise

        return results_summary


def main(argv: Optional[List[str]] = None) -> int:
    """CLI runner main entrypoint returning standard process exit codes."""
    verbose = False
    setup_signal_handlers()
    try:
        parser = create_parser()
        args = parser.parse_args(argv)
        verbose = args.verbose

        # Sanitize --web-dir
        if args.web_dir is not None:
            raw_web = str(args.web_dir).strip()
            args.web_dir = Path(raw_web) if raw_web and raw_web != "." else None

        # Determine desired output path and sanitize directory inputs
        raw_out = (args.output or args.output_path or "")
        output_dest = raw_out.strip() if isinstance(raw_out, str) and raw_out.strip() and raw_out.strip() != "." else None
        if output_dest:
            dest_p = Path(output_dest)
            if dest_p.is_dir():
                output_dest = str(dest_p / "daily_reports.json")

        pipeline = ScraperPipeline()
        summary = pipeline.run(
            sources=args.sources,
            limit=args.limit,
            output_path=output_dest,
            sync_web=args.sync_web,
            dry_run=args.dry_run,
            verbose=args.verbose,
            web_dir=args.web_dir,
            target_date=args.target_date,
        )
        if summary.get("total_scraped", 0) == 0:
            logger.warning("Scraping completed with 0 posts harvested across sources (network outage or empty boards). Exiting gracefully.")
            return 0
        return 0
    except KeyboardInterrupt:
        logger.warning("Scraper runner cancelled by user.")
        return 1
    except SystemExit as se:
        return se.code if isinstance(se.code, int) else 1
    except Exception as exc:
        logger.error(f"Fatal error during scraper execution: {exc}", exc_info=verbose)
        return 1


if __name__ == "__main__":
    sys.exit(main())
