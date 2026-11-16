"""Audit and Verification Test Suite for Tracker and Scraper Entrypoints.

Verifies:
- run_tracker.py: CLI argument parsing, dry-run mode, format options, mock network fallback, web sync.
- run_scraper.py: CLI argument parsing, dry-run mode, target-date parsing, timeout sanitization, mirror replication on 0 defects.
- tracker/subsidy_tracker.py: Comma-separated string parsing in _safe_int_metric, zero-division prevention, collect_and_save parity.
- utils/json_writer.py: _safe_float comma-separated string parsing.
- Parity auto-healing resilience.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import run_scraper
import run_tracker
from tracker.subsidy_models import SubsidyPayload
from tracker.subsidy_tracker import (
    SubsidyTracker,
    _safe_int_metric,
    calculate_depletion_rate,
    calculate_depletion_velocity,
    predict_exhaustion_days,
)
from utils.json_writer import _safe_float


class TestRunTrackerCLIAndEntrypoint(unittest.TestCase):
    """Test suite verifying run_tracker.py CLI arguments, dry-run mode, and fallback resilience."""

    def test_parse_arguments_defaults(self):
        """Verify default CLI arguments when no options are provided."""
        args = run_tracker.parse_arguments([])
        self.assertFalse(args.dry_run)
        self.assertFalse(args.sync_web)
        self.assertFalse(args.mock_network)
        self.assertFalse(args.verbose)
        self.assertTrue(args.validate_cache)
        self.assertTrue(args.quarantine_corrupted)
        self.assertEqual(args.format, "text")
        self.assertIsNotNone(args.output)
        self.assertTrue(str(args.output).endswith("ev_subsidy_data.json"))

    def test_parse_arguments_custom_flags(self):
        """Verify all CLI argument flags are properly parsed and normalized."""
        args = run_tracker.parse_arguments([
            "--dry-run",
            "--sync-web",
            "--mock-network",
            "--verbose",
            "-f", "json",
            "--output", "/tmp/custom_subsidies.json",
            "--web-dir", "/tmp/custom_web_dir",
            "--no-validate-cache",
            "--no-quarantine-corrupted",
            "--sync-defects",
        ])
        self.assertTrue(args.dry_run)
        self.assertTrue(args.sync_web)
        self.assertTrue(args.mock_network)
        self.assertTrue(args.verbose)
        self.assertEqual(args.format, "json")
        self.assertEqual(str(args.output), "/tmp/custom_subsidies.json")
        self.assertEqual(str(args.web_dir), "/tmp/custom_web_dir")
        self.assertFalse(args.validate_cache)
        self.assertFalse(args.quarantine_corrupted)
        self.assertTrue(args.sync_defects)

    def test_output_path_directory_sanitization(self):
        """Passing a directory or trailing slash path should resolve to ev_subsidy_data.json inside it."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            args = run_tracker.parse_arguments(["--output", tmp_dir])
            self.assertEqual(args.output, Path(tmp_dir) / "ev_subsidy_data.json")

    def test_dry_run_executes_without_writing_to_disk(self):
        """In dry-run mode, main() returns 0 and leaves nonexistent output path uncreated."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            custom_out = Path(tmp_dir) / "should_not_exist.json"
            exit_code = run_tracker.main([
                "--dry-run",
                "--output", str(custom_out),
                "--format", "json",
            ])
            self.assertEqual(exit_code, 0)
            self.assertFalse(custom_out.exists(), "Dry-run mode must never write output files to disk")

    def test_resilient_baseline_fallback_on_network_failure(self):
        """With --mock-network, main() succeeds using resilient baseline fallback."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "fallback_output.json"
            exit_code = run_tracker.main([
                "--dry-run",
                "--mock-network",
                "--output", str(out_file),
                "--format", "summary",
            ])
            self.assertEqual(exit_code, 0)

    def test_auto_heal_mirrored_parity_prefers_rich_defect_reports(self):
        """auto_heal_mirrored_parity should prioritize files with authentic defect reports over empty shells."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            data_dir = root / "data"
            web_data = root / "ev-stealth-web" / "src" / "data"
            data_dir.mkdir(parents=True)
            web_data.mkdir(parents=True)

            # Put authentic reports in data_dir (4 reports)
            rich_content = {
                "metadata": {"version": "1.0.0"},
                "reports": [
                    {"id": f"rep-{i}", "title": f"Defect {i}", "model": "아이오닉 5"}
                    for i in range(5)
                ],
                "statistics": {"total_defects": 5},
            }
            (data_dir / "daily_reports.json").write_text(json.dumps(rich_content, ensure_ascii=False))

            # Put empty reports shell in web_data with newer mtime
            empty_content = {"metadata": {"version": "1.0.0"}, "reports": []}
            empty_file = web_data / "daily_reports.json"
            empty_file.write_text(json.dumps(empty_content, ensure_ascii=False))
            # Set empty file mtime 100 seconds ahead
            os.utime(empty_file, (os.path.getatime(empty_file) + 100, os.path.getmtime(empty_file) + 100))

            repaired = run_tracker.auto_heal_mirrored_parity(repo_root=root)
            self.assertTrue(len(repaired) > 0)

            # Web data should now have the rich content replicated
            healed = json.loads(empty_file.read_text(encoding="utf-8-sig"))
            self.assertEqual(len(healed.get("reports", [])), 5, "Empty file must be healed with authentic reports")


class TestRunScraperCLIAndEntrypoint(unittest.TestCase):
    """Test suite verifying run_scraper.py CLI arguments, dry-run mode, and mirror replication."""

    def test_parse_arguments_defaults(self):
        """Verify default CLI arguments for run_scraper.py."""
        parser = run_scraper.create_parser()
        args = parser.parse_args([])
        self.assertEqual(args.sources, "all")
        self.assertEqual(args.limit, 20)
        self.assertIsNone(args.target_date)
        self.assertFalse(args.dry_run)
        self.assertFalse(args.sync_web)
        self.assertTrue(args.cache_fallback)

    def test_parse_target_date_formats(self):
        """Verify parsing of calendar and ISO target dates."""
        d1 = run_scraper.parse_target_date("2026-11-04")
        self.assertTrue(d1.startswith("2026-11-04"))

        d2 = run_scraper.parse_target_date("2026.11.04")
        self.assertTrue(d2.startswith("2026-11-04"))

        d3 = run_scraper.parse_target_date("2026/11/04")
        self.assertTrue(d3.startswith("2026-11-04"))

        d_iso = run_scraper.parse_target_date("2026-11-04T12:00:00Z")
        self.assertIn("2026-11-04", d_iso)

        with self.assertRaises(argparse.ArgumentTypeError):
            run_scraper.parse_target_date("invalid-date-format")

        with self.assertRaises(argparse.ArgumentTypeError):
            run_scraper.parse_target_date("2026-02-31")

    def test_scraper_pipeline_timeout_sanitization(self):
        """Verify pipeline handles None or invalid string timeouts without raising exceptions."""
        with run_scraper.ScraperPipeline(
            connect_timeout=None,
            read_timeout=-1.0,
        ) as pipeline:
            self.assertEqual(pipeline.connect_timeout, 5.0)
            self.assertEqual(pipeline.read_timeout, 15.0)

    def test_dry_run_executes_without_disk_write(self):
        """In dry-run mode, ScraperPipeline returns summary without writing target files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_out = Path(tmp_dir) / "daily_reports.json"
            with run_scraper.ScraperPipeline(cache_fallback=False) as pipeline:
                # Mock harvest to return 1 sample post
                pipeline.harvest = MagicMock(return_value=([
                    {"id": "p1", "title": "전기차 ICCU 고장 발생", "content": "주행 중 경고등 점등"}
                ], {"bobaedream": 1, "dcinside": 0}))

                res = pipeline.run(
                    sources="all",
                    limit=1,
                    output_path=str(test_out),
                    dry_run=True,
                )
                self.assertTrue(res["dry_run"])
                self.assertEqual(res["total_scraped"], 1)
                self.assertFalse(test_out.exists(), "Dry-run mode must never write files to disk")

    def test_zero_defects_replicates_authentic_mirror_to_invalid_target(self):
        """When scrape produces 0 defects, invalid or missing targets are healed from authentic mirror."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            authentic_file = root / "authentic_daily_reports.json"
            authentic_payload = {
                "metadata": {"version": "1.0.0"},
                "reports": [
                    {"id": "auth-1", "title": "BMS 통신 오류", "model": "EV6"}
                ],
                "statistics": {"total_defects": 1},
            }
            authentic_file.write_text(json.dumps(authentic_payload, ensure_ascii=False))

            # Corrupted / empty target
            corrupted_target = root / "corrupted_target.json"
            corrupted_target.write_text("NOT_VALID_JSON_CORRUPT")

            with run_scraper.ScraperPipeline(cache_fallback=False) as pipeline:
                pipeline.harvest = MagicMock(return_value=([], {"bobaedream": 0, "dcinside": 0}))

                # Temporarily patch candidate mirrors to include authentic_file
                with patch("run_scraper._resolve_web_reports_path", return_value=authentic_file):
                    res = pipeline.run(
                        sources="all",
                        limit=5,
                        output_path=str(corrupted_target),
                        dry_run=False,
                    )
                    written_resolved = [str(Path(wp).resolve()) for wp in res["written_paths"]]
                    self.assertIn(str(corrupted_target.resolve()), written_resolved)
                    # Verify target was healed with authentic contents
                    content = json.loads(corrupted_target.read_text(encoding="utf-8-sig"))
                    self.assertEqual(len(content["reports"]), 1)


class TestSubsidyTrackerHardeningAndEdgeCases(unittest.TestCase):
    """Test suite verifying SubsidyTracker edge case safety, comma parsing, and collect_and_save."""

    def test_safe_int_metric_handles_comma_strings(self):
        """_safe_int_metric must parse comma-formatted numeric strings without error."""
        self.assertEqual(_safe_int_metric("1,500"), 1500)
        self.assertEqual(_safe_int_metric("  2,345,678  "), 2345678)
        self.assertEqual(_safe_int_metric("100"), 100)
        self.assertEqual(_safe_int_metric(250), 250)
        self.assertEqual(_safe_int_metric(None, default=42), 42)
        self.assertEqual(_safe_int_metric("invalid", default=0), 0)
        self.assertEqual(_safe_int_metric(float("nan"), default=0), 0)
        self.assertEqual(_safe_int_metric(float("inf"), default=0), 0)

    def test_safe_float_handles_comma_strings(self):
        """_safe_float in json_writer must parse comma-formatted numeric strings without error."""
        self.assertEqual(_safe_float("1,234.56"), 1234.56)
        self.assertEqual(_safe_float("  99,999  "), 99999.0)
        self.assertEqual(_safe_float(None, default=0.0), 0.0)
        self.assertEqual(_safe_float("invalid", default=5.5), 5.5)

    def test_collect_and_save_dry_run_parity(self):
        """SubsidyTracker.collect_and_save(dry_run=True) should return SubsidyPayload without file writes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = Path(tmp_dir) / "test_subsidy.json"
            tracker = SubsidyTracker(cache_fallback_path=out_file)
            payload = tracker.collect_and_save(
                sync_web=False,
                output_path=out_file,
                dry_run=True,
                sync_defects=False,
            )
            self.assertIsInstance(payload, SubsidyPayload)
            self.assertFalse(out_file.exists(), "Dry-run mode in collect_and_save must not write files")

    def test_calculate_depletion_velocity_and_prediction_guards(self):
        """Verify prediction velocity and exhaustion days guard against divide-by-zero and negative values."""
        self.assertEqual(calculate_depletion_velocity(0, 100, 0), 0.0)
        self.assertEqual(calculate_depletion_velocity(0, 100, -5), 0.0)
        self.assertEqual(calculate_depletion_velocity("invalid", 100, 10), 0.0)
        self.assertEqual(calculate_depletion_velocity("0", "1,500", "30"), 50.0)

        self.assertIsNone(predict_exhaustion_days(100, 0.0))
        self.assertIsNone(predict_exhaustion_days(100, -10.0))
        self.assertEqual(predict_exhaustion_days(0, 50.0), 0)
        self.assertEqual(predict_exhaustion_days(-10, 50.0), 0)
        self.assertEqual(predict_exhaustion_days("1,000", "50"), 20)


if __name__ == "__main__":
    unittest.main()
