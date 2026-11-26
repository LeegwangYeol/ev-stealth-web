#!/usr/bin/env python3
"""Targeted regression tests for 2026-11-27 utils/*.py, run_scraper.py, and run_tracker.py audit."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

WEB_ROOT = Path(__file__).resolve().parent.parent
if str(WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_ROOT))

import run_scraper
import run_tracker
from utils.http_client import SafeHttpClient
from utils.json_writer import format_daily_report_payload


class TestHttpClientAndJsonWriter20261127(unittest.TestCase):
    """Regression tests for http_client cache_dir/URL whitespace guards and json_writer category alias."""

    def test_http_client_ignores_whitespace_cache_dir_and_whitespace_cache_urls(self) -> None:
        """Whitespace-only cache_dir falls back to default path; whitespace-only URLs are not cached."""
        client = SafeHttpClient(cache_dir="   ", enable_jitter=False, enable_cache=True)
        self.assertNotEqual(client.cache_dir.strip(), "")
        self.assertNotEqual(client.cache_dir, "   ")

        with tempfile.TemporaryDirectory() as td:
            c2 = SafeHttpClient(cache_dir=td, enable_jitter=False, enable_cache=True)
            c2.set_cached_response("   ", 200, "body", b"body")
            self.assertEqual(len(c2._memory_cache), 0)
            self.assertIsNone(c2.get_cached_response("   "))

    def test_json_writer_counts_category_alias_when_defect_category_missing(self) -> None:
        """format_daily_report_payload uses 'category' when 'defect_category' is absent."""
        payload = format_daily_report_payload(
            [
                {"id": "rep-1", "category": "BATTERY_CHARGING", "negativity_score": 0.8},
                {"id": "rep-2", "defect_category": "", "category": "DRIVING_POWERTRAIN", "negativity_score": 0.6},
            ]
        )
        cats = {item["category"]: item["count"] for item in payload.top_defect_categories}
        self.assertEqual(cats.get("BATTERY_CHARGING"), 1)
        self.assertEqual(cats.get("DRIVING_POWERTRAIN"), 1)
        self.assertNotIn("BUILD_QUALITY", cats)


class TestRunnerPathIsolation20261127(unittest.TestCase):
    """Regression tests for run_scraper and run_tracker CLI/env path isolation."""

    def test_run_scraper_env_web_dir_isolates_sync_web_targets(self) -> None:
        """ScraperPipeline.run(sync_web=True) respects EV_SCRAPER_WEB_DIR without leaking to repo paths."""
        with tempfile.TemporaryDirectory() as td:
            custom_web = Path(td) / "isolated_web"
            custom_web.mkdir()
            with patch.dict(os.environ, {"EV_SCRAPER_WEB_DIR": str(custom_web)}):
                with run_scraper.ScraperPipeline(enable_cache=False, cache_fallback=False) as pipeline:
                    pipeline.harvest = MagicMock(return_value=([], {"bobaedream": 0, "dcinside": 0}))
                    summary = pipeline.run(sync_web=True, dry_run=True)

            expected = os.path.abspath(str(custom_web / "daily_reports.json"))
            self.assertEqual(summary["target_paths"], [expected])

    def test_run_scraper_custom_subdir_does_not_leak_to_parent_public_data(self) -> None:
        """Custom --web-dir whose parent happens to have public/data must not leak to parent public/data."""
        with tempfile.TemporaryDirectory() as td:
            parent_pub = Path(td) / "public" / "data"
            parent_pub.mkdir(parents=True)
            custom_sub = Path(td) / "custom_sub"
            custom_sub.mkdir()
            with run_scraper.ScraperPipeline(enable_cache=False, cache_fallback=False) as pipeline:
                pipeline.harvest = MagicMock(return_value=([], {"bobaedream": 0, "dcinside": 0}))
                summary = pipeline.run(sync_web=True, web_dir=custom_sub, dry_run=True)

            self.assertEqual(
                summary["target_paths"],
                [os.path.abspath(str(custom_sub / "daily_reports.json"))],
            )

    def test_run_tracker_sync_defect_reports_root_only_isolates_crawler_and_web_path(self) -> None:
        """sync_defect_reports(root_dir=..., web_dir=None, run_crawler=True) stays isolated in root_dir."""
        with tempfile.TemporaryDirectory() as td:
            root_d = Path(td) / "isolated_root"
            root_d.mkdir()
            (root_d / "daily_reports.json").write_text(
                json.dumps({"reports": [{"id": "r1"}]}),
                encoding="utf-8",
            )

            mock_pipeline = MagicMock()
            mock_pipeline.__enter__.return_value = mock_pipeline
            mock_pipeline.run.return_value = {"written_paths": []}

            with patch("run_scraper.ScraperPipeline", return_value=mock_pipeline):
                written = run_tracker.sync_defect_reports(
                    web_dir=None,
                    root_dir=root_d,
                    run_crawler=True,
                )

            mock_pipeline.run.assert_called_once()
            call_kwargs = mock_pipeline.run.call_args.kwargs
            self.assertFalse(call_kwargs["sync_web"])
            self.assertIsNone(call_kwargs["web_dir"])
            self.assertEqual(Path(call_kwargs["output_path"]), root_d / "daily_reports.json")
            self.assertEqual(written, [])
            self.assertFalse((Path(run_tracker._CURRENT_DIR) / "daily_reports.json").exists())


if __name__ == "__main__":
    unittest.main()
