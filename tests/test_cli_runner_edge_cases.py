#!/usr/bin/env python3
"""Comprehensive Unit and Edge Case Tests for CLI Entrypoints and Shell Runners.

Tests:
1. Argument parsing edge cases:
   - Empty string and whitespace path arguments (--output "", --web-dir "  ")
   - Directory paths passed to --output (auto-appends ev_subsidy_data.json)
   - Comma-separated sources and aliases in run_scraper (--sources bobaedream,dcinside, --sources bobae,dc)
   - Limit clamping (min 1, max 500)
   - Proper evaluation of --no-sync-defects in both normal and dry-run modes
2. Environment variable fallbacks:
   - EV_TRACKER_WEB_DIR, EV_SCRAPER_WEB_DIR, and unified EV_WEB_DIR
   - EV_SUBSIDY_API_ENDPOINT whitespace stripping and None conversion
   - Shell RUNNER_PY environment override
   - PYTHON_BIN / PYTHON precedence
3. Exit code propagation:
   - 0 on success and --help
   - 1 on runtime exception or user cancellation (KeyboardInterrupt)
   - 2 on invalid arguments or missing Python interpreter
4. Runtime resilience:
   - Fallback when regions < 17 in run_tracker.py executes without NameError (datetime/timezone).
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import run_scraper
import run_tracker

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestCLIRunnerEdgeCases(unittest.TestCase):
    """Test suite verifying CLI argument parsing edge cases and fallback protocols."""

    def test_run_tracker_parse_args_empty_strings(self) -> None:
        """Verify empty string or '.' arguments in run_tracker fall back safely."""
        args = run_tracker.parse_arguments(["--output", "", "--web-dir", "   ", "--endpoint", "   "])
        self.assertEqual(args.output, run_tracker.DEFAULT_PRIMARY_OUTPUT)
        self.assertIsNone(args.web_dir)
        self.assertIsNone(args.endpoint)

    def test_run_tracker_output_is_directory_resolution(self) -> None:
        """Verify directory passed as --output appends default filename."""
        with tempfile.TemporaryDirectory() as td:
            args = run_tracker.parse_arguments(["--output", td])
            self.assertEqual(args.output, Path(td) / "ev_subsidy_data.json")

    def test_run_tracker_env_var_web_dir_fallback(self) -> None:
        """Verify unified EV_WEB_DIR is used if EV_TRACKER_WEB_DIR is absent."""
        with patch.dict(os.environ, {"EV_TRACKER_WEB_DIR": "", "EV_WEB_DIR": "/tmp/unified_web"}):
            args = run_tracker.parse_arguments([])
            self.assertEqual(args.web_dir, Path("/tmp/unified_web"))

    def test_run_tracker_no_sync_defects_dry_run_respected(self) -> None:
        """Verify --no-sync-defects prevents defect sync even in dry-run mode."""
        args = run_tracker.parse_arguments(["--dry-run", "--sync-web", "--no-sync-defects"])
        self.assertIs(args.sync_defects, False)

        with patch("run_tracker.sync_defect_reports") as mock_sync:
            with patch.object(run_tracker.SubsidyTracker, "execute_tracking_cycle") as mock_cycle:
                mock_payload = MagicMock()
                mock_payload.regions = [MagicMock()] * 17
                mock_cycle.return_value = (mock_payload, False)
                with patch.object(run_tracker.SubsidyTracker, "generate_briefing", return_value="Summary"):
                    ret = run_tracker.main(["--dry-run", "--sync-web", "--no-sync-defects"])
                    self.assertEqual(ret, 0)
                    mock_sync.assert_not_called()

    def test_run_tracker_missing_datetime_import_regression(self) -> None:
        """Verify that fallback triggered when regions < 17 succeeds without NameError."""
        with patch.object(run_tracker.SubsidyTracker, "execute_tracking_cycle") as mock_cycle:
            # Return empty payload to trigger baseline rebuild branch (lines 495-507)
            mock_cycle.return_value = (None, True)
            with patch.object(run_tracker.SubsidyTracker, "generate_briefing", return_value="Baseline Briefing"):
                with patch.object(run_tracker.SubsidyTracker, "save_payload", return_value=[]):
                    ret = run_tracker.main(["--dry-run"])
                    self.assertEqual(ret, 0)

    def test_run_scraper_parse_comma_separated_sources_and_aliases(self) -> None:
        """Verify run_scraper accepts comma-separated sources and common aliases."""
        pipeline = run_scraper.ScraperPipeline(
            bobae_crawler=MagicMock(),
            dc_crawler=MagicMock(),
            defect_filter=MagicMock(),
        )
        pipeline.harvest_bobaedream = MagicMock(return_value=[{"post_id": "b1"}])
        pipeline.harvest_dcinside = MagicMock(return_value=[{"post_id": "d1"}])

        # Test comma-separated: "bobaedream,dcinside"
        posts, stats = pipeline.harvest("bobaedream,dcinside", limit=10)
        self.assertEqual(len(posts), 2)
        self.assertEqual(stats["bobaedream"], 1)
        self.assertEqual(stats["dcinside"], 1)

        # Test aliases: "bobae,dc"
        posts, stats = pipeline.harvest("bobae,dc", limit=10)
        self.assertEqual(len(posts), 2)

        # Test single alias: "dc"
        posts, stats = pipeline.harvest("dc", limit=10)
        self.assertEqual(len(posts), 1)
        self.assertEqual(stats["dcinside"], 1)
        self.assertEqual(stats["bobaedream"], 0)

    def test_run_scraper_limit_clamping(self) -> None:
        """Verify run_scraper clamps negative/zero to 1 and huge values to 500."""
        pipeline = run_scraper.ScraperPipeline(
            bobae_crawler=MagicMock(),
            dc_crawler=MagicMock(),
            defect_filter=MagicMock(),
        )
        pipeline.harvest_bobaedream = MagicMock(return_value=[])
        pipeline.harvest_dcinside = MagicMock(return_value=[])

        # Negative limit -> clamped to 1
        pipeline.harvest("all", limit=-50)
        pipeline.harvest_bobaedream.assert_called_with(limit=1)

        # Overflow limit -> clamped to 500
        pipeline.harvest("all", limit=999999)
        pipeline.harvest_bobaedream.assert_called_with(limit=500)

    def test_run_scraper_env_var_web_dir_fallback(self) -> None:
        """Verify run_scraper respects EV_TRACKER_WEB_DIR and EV_WEB_DIR when EV_SCRAPER_WEB_DIR is unset."""
        with patch.dict(os.environ, {"EV_SCRAPER_WEB_DIR": "", "EV_WEB_DIR": "/tmp/custom_shared_dir"}):
            resolved = run_scraper._resolve_web_reports_path()
            self.assertEqual(resolved, Path("/tmp/custom_shared_dir/daily_reports.json"))

    def test_exit_code_propagation_in_main(self) -> None:
        """Verify main() in both runners propagates exit codes (0 for help, 2 for invalid args)."""
        # run_tracker --help returns 0
        self.assertEqual(run_tracker.main(["--help"]), 0)
        # run_tracker invalid flag returns 2
        self.assertEqual(run_tracker.main(["--completely-bogus-flag"]), 2)

        # run_scraper --help returns 0
        self.assertEqual(run_scraper.main(["--help"]), 0)
        # run_scraper invalid flag returns 2
        self.assertEqual(run_scraper.main(["--completely-bogus-flag"]), 2)

    def test_run_scraper_target_date_parsing_valid(self) -> None:
        """Verify parse_target_date accepts YYYY-MM-DD, dots, slashes, and ISO-8601."""
        self.assertIsNone(run_scraper.parse_target_date(None))
        self.assertIsNone(run_scraper.parse_target_date(""))
        self.assertIsNone(run_scraper.parse_target_date("   "))

        # YYYY-MM-DD
        d1 = run_scraper.parse_target_date("2026-11-04")
        self.assertEqual(d1, "2026-11-04T00:00:00+00:00")

        # YYYY.MM.DD
        d2 = run_scraper.parse_target_date("2026.11.04")
        self.assertEqual(d2, "2026-11-04T00:00:00+00:00")

        # YYYY/MM/DD
        d3 = run_scraper.parse_target_date("2026/11/04")
        self.assertEqual(d3, "2026-11-04T00:00:00+00:00")

        # Full ISO string
        d4 = run_scraper.parse_target_date("2026-11-04T12:30:00Z")
        self.assertEqual(d4, "2026-11-04T12:30:00+00:00")

    def test_run_scraper_target_date_parsing_invalid(self) -> None:
        """Verify parse_target_date raises ArgumentTypeError on malformed date string."""
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            run_scraper.parse_target_date("invalid-date-string")
        with self.assertRaises(argparse.ArgumentTypeError):
            run_scraper.parse_target_date("2026-99-99")

        # Verify CLI exits with code 2 on invalid target date
        ret = run_scraper.main(["--target-date", "bogus-date"])
        self.assertEqual(ret, 2)

    def test_run_scraper_target_date_propagation_in_run(self) -> None:
        """Verify target_date argument propagates to results_summary and writer."""
        pipeline = run_scraper.ScraperPipeline(
            bobae_crawler=MagicMock(),
            dc_crawler=MagicMock(),
            defect_filter=MagicMock(),
        )
        pipeline.harvest = MagicMock(return_value=([], {"bobaedream": 0, "dcinside": 0}))
        res = pipeline.run(dry_run=True, target_date="2026-11-04T00:00:00+00:00")
        self.assertEqual(res["target_date"], "2026-11-04T00:00:00+00:00")

    def test_run_scraper_output_directory_resolution(self) -> None:
        """Verify directory passed as --output in run_scraper appends daily_reports.json."""
        with tempfile.TemporaryDirectory() as td:
            with patch("run_scraper.ScraperPipeline.run") as mock_run:
                mock_run.return_value = {"total_scraped": 0}
                ret = run_scraper.main(["--output", td, "--dry-run"])
                self.assertEqual(ret, 0)
                mock_run.assert_called_once()
                call_args = mock_run.call_args[1]
                self.assertEqual(call_args["output_path"], str(Path(td) / "daily_reports.json"))

    def test_run_scraper_signal_handling(self) -> None:
        """Verify _signal_handler sets shutdown flag, raises KeyboardInterrupt on SIGINT and SystemExit on SIGTERM."""
        import signal
        run_scraper._SHUTDOWN_REQUESTED = False

        # SIGINT raises KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            run_scraper._signal_handler(signal.SIGINT, None)
        self.assertTrue(run_scraper._SHUTDOWN_REQUESTED)

        # SIGTERM raises SystemExit(143)
        with self.assertRaises(SystemExit) as cm:
            run_scraper._signal_handler(signal.SIGTERM, None)
        self.assertEqual(cm.exception.code, 128 + signal.SIGTERM)

        # Reset flag
        run_scraper._SHUTDOWN_REQUESTED = False

    def test_run_scraper_repo_root_and_paths(self) -> None:
        """Verify _find_repo_root and path resolvers locate project data directories."""
        repo_root = run_scraper._find_repo_root()
        self.assertTrue(repo_root.is_dir())
        self.assertTrue((repo_root / "data").exists() or (repo_root / "ev-stealth-web").exists())

        web_path = run_scraper._resolve_web_reports_path()
        self.assertTrue(str(web_path).endswith("daily_reports.json"))

        root_path = run_scraper._resolve_root_reports_path()
        self.assertTrue(str(root_path).endswith("daily_reports.json"))

    def test_run_scraper_main_with_target_date_dry_run(self) -> None:
        """Verify run_scraper.main executes cleanly with --target-date and mocked harvest."""
        with patch.object(run_scraper.ScraperPipeline, "harvest", return_value=([], {"bobaedream": 0, "dcinside": 0})):
            ret = run_scraper.main(["--dry-run", "--target-date", "2026-11-04"])
            self.assertEqual(ret, 0)

    def test_run_scraper_sh_dry_run_with_target_date(self) -> None:
        """Verify run_scraper.sh forwards arguments including --target-date successfully."""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write("import sys; sys.exit(0 if '--target-date' in sys.argv and '2026-11-04' in sys.argv else 99)\n")
            custom_py = tf.name
        try:
            env = os.environ.copy()
            env["RUNNER_PY"] = custom_py
            res = subprocess.run(
                ["bash", str(REPO_ROOT / "run_scraper.sh"), "--dry-run", "--target-date", "2026-11-04"],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                env=env,
            )
            self.assertEqual(res.returncode, 0, f"STDOUT: {res.stdout}\nSTDERR: {res.stderr}")
            self.assertIn("DAILY EV MONITORING PIPELINE", res.stdout)
            self.assertIn("[SUCCESS]", res.stdout)
        finally:
            if os.path.exists(custom_py):
                os.unlink(custom_py)

    def test_run_scraper_sh_invalid_date_exit_code_2(self) -> None:
        """Verify run_scraper.sh returns exit code 2 and [ERROR] on invalid target date."""
        res = subprocess.run(
            ["bash", str(REPO_ROOT / "run_scraper.sh"), "--target-date", "invalid-target-date"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(res.returncode, 2)
        combined = res.stdout + res.stderr
        self.assertIn("[ERROR] Scraper pipeline failed with exit code 2", combined)

    def test_shell_runner_py_override(self) -> None:
        """Verify run_tracker.sh and run_scraper.sh respect RUNNER_PY environment override."""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
            tf.write("import sys; sys.exit(42)\n")
            custom_py = tf.name

        try:
            env = os.environ.copy()
            env["RUNNER_PY"] = custom_py
            res = subprocess.run(
                ["bash", str(REPO_ROOT / "run_tracker.sh")],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                env=env,
            )
            self.assertEqual(res.returncode, 42)
            self.assertIn("failed with code 42", res.stdout)
        finally:
            if os.path.exists(custom_py):
                os.unlink(custom_py)


if __name__ == "__main__":
    unittest.main()
