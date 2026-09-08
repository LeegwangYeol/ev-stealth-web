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
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

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
for root_path in POSSIBLE_ROOTS:
    if root_path.exists() and str(root_path) not in sys.path:
        sys.path.insert(0, str(root_path))

# Dynamic imports with fallback aliases
from crawlers.bobaedream import BobaeDreamCrawler
from crawlers.dcinside import DCInsideCrawler
from models.complaint import ComplaintRecord, RawPost
from utils.http_client import SafeHttpClient
from utils.json_writer import (
    DEFAULT_OUTPUT_PATH,
    format_daily_report_payload,
    read_daily_reports,
    write_daily_reports,
)

try:
    from filters.defect_filter import ContextualDefectFilter as DefectFilter
except ImportError:
    from filters.defect_filter import DefectFilter  # type: ignore

logger = logging.getLogger("ScraperRunner")


def _resolve_web_reports_path() -> Path:
    candidates = [
        CURRENT_DIR / "ev-stealth-web" / "src" / "data" / "daily_reports.json",
        CURRENT_DIR / "src" / "data" / "daily_reports.json",
        CURRENT_DIR.parent / "ev-stealth-web" / "src" / "data" / "daily_reports.json",
        CURRENT_DIR.parent / "src" / "my-e-car" / "ev-stealth-web" / "src" / "data" / "daily_reports.json",
    ]
    for c in candidates:
        if c.parent.exists():
            return c
    return candidates[0]


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
        target_boards = ["national"]

        for board in target_boards:
            try:
                logger.info(f"Crawling BobaeDream board '{board}' (limit={limit})...")
                board_posts = self.bobae_crawler.crawl_board(board, pages=1, limit=limit)
                posts.extend(board_posts)
                if len(posts) >= limit:
                    break
            except Exception as e:
                logger.warning(f"Error while crawling BobaeDream board '{board}': {e}")

        # If board crawl returned few or no posts, fallback to EV keyword search
        if len(posts) < limit:
            remaining = limit - len(posts)
            try:
                logger.info(f"Searching BobaeDream for '전기차' (remaining limit={remaining})...")
                search_posts = self.bobae_crawler.crawl_posts_by_keyword("전기차", boards=["national"], limit=remaining)
                posts.extend(search_posts)
            except Exception as e:
                logger.warning(f"Error while searching BobaeDream: {e}")

        return posts[:limit]

    def harvest_dcinside(self, limit: int) -> List[Dict[str, Any]]:
        """Harvest recent EV discussions from DCInside galleries."""
        posts: List[Dict[str, Any]] = []
        target_galleries = ["car_new1"]

        for gall in target_galleries:
            try:
                logger.info(f"Crawling DCInside gallery '{gall}' (limit={limit})...")
                gall_posts = self.dc_crawler.crawl_gallery(gall, pages=1, limit=limit)
                posts.extend(gall_posts)
                if len(posts) >= limit:
                    break
            except Exception as e:
                logger.warning(f"Error while crawling DCInside gallery '{gall}': {e}")

        # Fallback to EV search if gallery listings yielded fewer posts
        if len(posts) < limit:
            remaining = limit - len(posts)
            try:
                logger.info(f"Searching DCInside for '전기차' (remaining limit={remaining})...")
                search_posts = self.dc_crawler.crawl_posts_by_keyword("전기차", galleries=["car_new1"], limit=remaining)
                posts.extend(search_posts)
            except Exception as e:
                logger.warning(f"Error while searching DCInside: {e}")

        return posts[:limit]

    def harvest(self, source_choice: str, limit: int) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """Harvest raw post dictionaries based on selected source mode."""
        valid_sources = {"all", "bobaedream", "dcinside"}
        selected_source = source_choice.lower().strip() if source_choice else "all"
        if selected_source not in valid_sources:
            logger.warning(f"Unknown source '{source_choice}', falling back to 'all'")
            selected_source = "all"

        raw_posts: List[Dict[str, Any]] = []
        stats: Dict[str, int] = {"bobaedream": 0, "dcinside": 0}

        if selected_source in ("all", "bobaedream"):
            try:
                bobae_posts = self.harvest_bobaedream(limit=limit)
                raw_posts.extend(bobae_posts)
                stats["bobaedream"] = len(bobae_posts)
            except Exception as e:
                logger.warning(f"BobaeDream crawler encountered an unhandled error: {e}")

        if selected_source in ("all", "dcinside"):
            try:
                dc_posts = self.harvest_dcinside(limit=limit)
                raw_posts.extend(dc_posts)
                stats["dcinside"] = len(dc_posts)
            except Exception as e:
                logger.warning(f"DCInside crawler encountered an unhandled error: {e}")

        return raw_posts, stats

    def filter_defects(self, raw_post_dicts: Iterable[Dict[str, Any]]) -> List[ComplaintRecord]:
        """Classify raw post dictionaries through 4-stage DefectFilter."""
        defects: List[ComplaintRecord] = []
        for p_dict in raw_post_dicts:
            try:
                raw_post = RawPost.from_dict(p_dict)
                complaint = self.defect_filter.process_post(raw_post)
                if complaint.is_authentic_defect:
                    defects.append(complaint)
            except Exception as e:
                logger.warning(f"Failed to process post {p_dict.get('post_id', 'unknown')}: {e}")
        return defects

    def run(
        self,
        sources: str = "all",
        limit: int = 20,
        output_path: Optional[str] = None,
        sync_web: bool = False,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        """Execute end-to-end harvest, filter, and report publishing pipeline."""
        configure_logging(verbose)
        clamped_limit = max(1, limit)

        logger.info(
            f"Starting scraper pipeline: sources={sources}, limit={clamped_limit}, "
            f"sync_web={sync_web}, dry_run={dry_run}"
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
            target_paths.append(os.path.abspath(WEB_DATA_DAILY_REPORTS_PATH))
        if not target_paths:
            target_paths.append(os.path.abspath(DEFAULT_OUTPUT_PATH))

        # Deduplicate paths while preserving order
        unique_paths: List[str] = []
        for path_str in target_paths:
            if path_str not in unique_paths:
                unique_paths.append(path_str)

        # 4. Handle persistence or dry-run
        results_summary: Dict[str, Any] = {
            "total_scraped": total_scraped,
            "total_filtered_defects": len(defect_complaints),
            "harvest_stats": harvest_stats,
            "target_paths": unique_paths,
            "dry_run": dry_run,
            "written_paths": [],
            "preserved_paths": [],
        }

        if dry_run:
            logger.info(
                f"[DRY-RUN] Processed {total_scraped} raw posts; "
                f"{len(defect_complaints)} authentic defects identified. "
                f"Skipping disk write for targets: {unique_paths}."
            )
            return results_summary

        # Normal write mode with graceful degradation
        for out_path in unique_paths:
            try:
                if len(defect_complaints) > 0:
                    written_path = write_daily_reports(
                        complaints=defect_complaints,
                        output_path=out_path,
                        total_scraped=total_scraped,
                    )
                    results_summary["written_paths"].append(written_path)
                    logger.info(f"Successfully published daily reports to: {written_path}")
                else:
                    # Graceful degradation: preserve existing data if file exists and scrape is empty
                    if os.path.exists(out_path):
                        logger.warning(
                            f"Scrape produced 0 authentic defects. Preserving existing reports at {out_path}."
                        )
                        results_summary["preserved_paths"].append(out_path)
                    else:
                        logger.warning(
                            f"Scrape produced 0 authentic defects and {out_path} does not exist. "
                            f"Initializing empty daily reports payload."
                        )
                        written_path = write_daily_reports(
                            complaints=[],
                            output_path=out_path,
                            total_scraped=total_scraped,
                        )
                        results_summary["written_paths"].append(written_path)
            except Exception as e:
                logger.error(f"Failed to write daily reports to {out_path}: {e}")
                raise

        return results_summary


def main(argv: Optional[List[str]] = None) -> int:
    """CLI runner main entrypoint returning standard process exit codes."""
    parser = create_parser()
    args = parser.parse_args(argv)

    # Determine desired output path
    output_dest = args.output or args.output_path

    try:
        pipeline = ScraperPipeline()
        summary = pipeline.run(
            sources=args.sources,
            limit=args.limit,
            output_path=output_dest,
            sync_web=args.sync_web,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
        if summary.get("total_scraped", 0) == 0:
            logger.error("Scraping failure: 0 posts harvested across all sources (network outage or blocked).")
            return 1
        return 0
    except KeyboardInterrupt:
        logger.warning("Scraper runner cancelled by user.")
        return 1
    except SystemExit as se:
        return se.code if isinstance(se.code, int) else 1
    except Exception as exc:
        logger.error(f"Fatal error during scraper execution: {exc}", exc_info=args.verbose)
        return 1


if __name__ == "__main__":
    sys.exit(main())
