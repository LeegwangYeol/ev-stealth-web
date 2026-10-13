"""Tests verifying the architectural remediations from critic_architecture_1 findings."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import run_tracker
from tracker.defect_tracker import DefectTracker


class TestCriticRemediationCycle15(unittest.TestCase):
    """Verifies that all 4 critic findings have been remediated cleanly."""

    def setUp(self) -> None:
        p = Path(__file__).resolve()
        while p.parent != p:
            if (p / "run_tracker.py").exists() and (p / "ev-stealth-web").exists():
                self.repo_root = p
                break
            p = p.parent
        else:
            self.repo_root = Path(__file__).resolve().parent.parent

    def test_test_mirror_parity_wcag_a11y(self) -> None:
        """tests/test_frontend_a11y_wcag.py and ev-stealth-web/tests/test_frontend_a11y_wcag.py are bit-for-bit identical."""
        root_test = self.repo_root / "tests" / "test_frontend_a11y_wcag.py"
        web_test = self.repo_root / "ev-stealth-web" / "tests" / "test_frontend_a11y_wcag.py"

        self.assertTrue(root_test.exists(), f"{root_test} must exist")
        self.assertTrue(web_test.exists(), f"{web_test} must exist")

        root_bytes = root_test.read_bytes()
        web_bytes = web_test.read_bytes()

        self.assertEqual(
            len(root_bytes),
            len(web_bytes),
            f"Byte length mismatch between root ({len(root_bytes)}) and web ({len(web_bytes)})",
        )
        self.assertEqual(root_bytes, web_bytes, "Content mismatch between root and web WCAG test suites")

    def test_run_tracker_defect_mirror_sync_on_zero_crawler_results(self) -> None:
        """run_tracker.sync_defect_reports does not short-circuit when crawler yields 0 defects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            root_data_dir = tmp_root / "data"
            web_data_dir = tmp_root / "ev-stealth-web" / "src" / "data"
            public_data_dir = tmp_root / "ev-stealth-web" / "public" / "data"
            root_data_dir.mkdir(parents=True)
            web_data_dir.mkdir(parents=True)
            public_data_dir.mkdir(parents=True)

            source_file = root_data_dir / "daily_reports.json"
            valid_payload = {
                "generated_at": "2026-10-14T05:00:00Z",
                "reports": [{"id": "DEF-100", "title": "Test Complaint"}],
                "statistics": {"total": 1},
            }
            with open(source_file, "w", encoding="utf-8") as f:
                json.dump(valid_payload, f)

            # Mock ScraperPipeline to return empty written_paths (0 new defects found)
            mock_pipeline = mock.MagicMock()
            mock_pipeline.run.return_value = {
                "total_scraped": 20,
                "total_filtered_defects": 0,
                "written_paths": [],
                "preserved_paths": [str(source_file)],
            }

            with mock.patch.object(run_tracker, "_CURRENT_DIR", tmp_root):
                with mock.patch("run_scraper.ScraperPipeline", return_value=mock_pipeline):
                    written = run_tracker.sync_defect_reports(
                        web_dir=web_data_dir,
                        run_crawler=True,
                        dry_run=False,
                    )

            # The sync must NOT short-circuit; it should replicate to both web and public mirrors
            web_file = web_data_dir / "daily_reports.json"
            public_file = public_data_dir / "daily_reports.json"
            self.assertTrue(web_file.exists(), "web_data_dir/daily_reports.json must exist after sync")
            self.assertTrue(public_file.exists(), "public_data_dir/daily_reports.json must exist after sync")
            with open(web_file, "r", encoding="utf-8") as wf:
                data_web = json.load(wf)
            with open(public_file, "r", encoding="utf-8") as pf:
                data_pub = json.load(pf)
            self.assertEqual(data_web["reports"][0]["id"], "DEF-100")
            self.assertEqual(data_pub["reports"][0]["id"], "DEF-100")
            self.assertIn(str(web_file), written)
            self.assertIn(str(public_file), written)

    def test_defect_tracker_oop_defect_mirror_sync_on_zero_crawler_results(self) -> None:
        """DefectTracker.sync_defect_reports does not short-circuit and replicates to all 3 mirrors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            root_data_dir = tmp_root / "data"
            web_data_dir = tmp_root / "web" / "src" / "data"
            public_data_dir = tmp_root / "web" / "public" / "data"

            root_data_dir.mkdir(parents=True)
            web_data_dir.mkdir(parents=True)
            public_data_dir.mkdir(parents=True)

            root_file = root_data_dir / "daily_reports.json"
            valid_payload = {
                "generated_at": "2026-10-14T05:00:00Z",
                "reports": [{"id": "DEF-200", "title": "OOP Test Complaint"}],
                "statistics": {"total": 1},
            }
            with open(root_file, "w", encoding="utf-8") as f:
                json.dump(valid_payload, f)

            mock_pipeline = mock.MagicMock()
            mock_pipeline.run.return_value = {
                "total_scraped": 15,
                "total_filtered_defects": 0,
                "written_paths": [],
                "preserved_paths": [],
            }

            tracker = DefectTracker(
                root_data_dir=root_data_dir,
                web_data_dir=web_data_dir,
                public_data_dir=public_data_dir,
                pipeline=mock_pipeline,
            )

            written = tracker.sync_defect_reports(
                web_dir=web_data_dir,
                run_crawler=True,
                dry_run=False,
            )

            web_file = web_data_dir / "daily_reports.json"
            public_file = public_data_dir / "daily_reports.json"

            self.assertTrue(web_file.exists(), "web_data_dir/daily_reports.json must exist")
            self.assertTrue(public_file.exists(), "public_data_dir/daily_reports.json must exist")

            with open(web_file, "r", encoding="utf-8") as wf:
                self.assertEqual(json.load(wf)["reports"][0]["id"], "DEF-200")
            with open(public_file, "r", encoding="utf-8") as pf:
                self.assertEqual(json.load(pf)["reports"][0]["id"], "DEF-200")

            self.assertIn(str(web_file), written)
            self.assertIn(str(public_file), written)

    def test_no_corrupt_quarantine_files_in_data_dir(self) -> None:
        """data/ directory contains zero stale .corrupt_ quarantine files."""
        data_dir = self.repo_root / "data"
        if data_dir.exists():
            corrupt_files = list(data_dir.glob("*.corrupt*"))
            self.assertEqual(
                corrupt_files,
                [],
                f"data/ contains stale quarantine files: {corrupt_files}",
            )

    def test_github_actions_workflow_runs_tracker_and_stages_mirrors(self) -> None:
        """daily-scraper.yml runs run_tracker.py --sync-web and stages all daily_reports.json mirrors."""
        workflow_path = self.repo_root / ".github" / "workflows" / "daily-scraper.yml"
        self.assertTrue(workflow_path.exists())
        content = workflow_path.read_text(encoding="utf-8")

        self.assertIn("python3 run_tracker.py --sync-web", content)
        self.assertIn("data/daily_reports.json", content)
        self.assertIn("ev-stealth-web/public/data/daily_reports.json", content)


if __name__ == "__main__":
    unittest.main()
