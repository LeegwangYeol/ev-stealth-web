"""tests/test_adversarial_pipeline.py - Adversarial & Stress Testing Suite for Python Tracker Pipeline.

Empirically validates:
1. Concurrency & Collision:
   - High-concurrency parallel process writes to shared output file.
   - Concurrent reader verification to prove zero uncommitted/half-written reads.
   - Temp file cleanup verification (no leaked .tmp_subsidy_* files).
2. Corrupted Cache Recovery:
   - Malformed/truncated JSON.
   - Invalid non-UTF-8 binary bytes.
   - Mismatched schema/structure.
   - 0-byte empty file and null bytes.
3. Mathematical Limits & Edge Cases:
   - Division-by-zero defense when announced_units == 0 across categories and nationwide summary.
   - Over-subscription clamping when applied_units > announced_units (>100% depletion, remaining units clamped to 0).
   - Boundary threshold classifications for 5-tier alert engine.
4. CLI Extremes:
   - Unknown and malformed CLI flags (exit code 2).
   - Non-existent deep nested output directories (auto-creation).
   - Read-only output target error handling and cleanup.
   - --dry-run vs persistent run guarantees.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tracker.atomic_writer import atomic_write_json
from tracker.subsidy_baseline import build_initial_baseline
from tracker.subsidy_models import (
    AlertSeverity,
    CategoryMetrics,
    RegionRecord,
    SubsidyPayload,
)
from tracker.subsidy_tracker import SubsidyTracker


class TestConcurrencyAndCollision(unittest.TestCase):
    """Stress tests for concurrent process executions and atomic file swaps."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_file = Path(self.temp_dir.name) / "concurrent_subsidy.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_concurrent_process_writes_atomic_safety(self):
        """Run 16 concurrent processes executing run_tracker.py targeting the exact same file."""
        num_workers = 16
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "run_tracker.py"),
            "--output",
            str(self.output_file),
            "--verbose",
        ]

        # Launch concurrent subprocesses simultaneously
        processes: List[subprocess.Popen] = []
        for _ in range(num_workers):
            p = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            processes.append(p)

        # Wait for all processes to complete and collect exit codes and logs
        exit_codes = []
        stderr_outputs = []
        for p in processes:
            stdout, stderr = p.communicate(timeout=30)
            exit_codes.append(p.returncode)
            if p.returncode != 0:
                stderr_outputs.append(stderr)

        self.assertEqual(
            exit_codes,
            [0] * num_workers,
            f"Some concurrent processes failed! Errors:\n" + "\n---\n".join(stderr_outputs),
        )

        # File must exist, be non-empty, and contain 100% valid parseable JSON
        self.assertTrue(self.output_file.exists())
        self.assertGreater(self.output_file.stat().st_size, 1000)

        with open(self.output_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("metadata", data)
        self.assertIn("regions", data)
        self.assertEqual(len(data["regions"]), 17)

        # Ensure no dangling temporary files were leaked in the directory
        temp_files = list(Path(self.temp_dir.name).glob(".tmp_subsidy_*"))
        self.assertEqual(
            len(temp_files),
            0,
            f"Orphaned temporary files found in output directory: {temp_files}",
        )

    def test_concurrent_readers_during_intense_writes(self):
        """Simultaneously write from multiple workers while a reader thread repeatedly reads."""
        write_count = 10
        read_errors: List[str] = []
        successful_reads = [0]
        stop_readers = False

        # First write an initial valid file
        atomic_write_json(build_initial_baseline(), self.output_file)

        def reader_worker():
            while not stop_readers:
                try:
                    if self.output_file.exists():
                        with open(self.output_file, "r", encoding="utf-8") as f:
                            content = f.read()
                            if content:  # If file opened and read
                                parsed = json.loads(content)
                                if "regions" not in parsed:
                                    read_errors.append("Missing regions key in read file")
                                else:
                                    successful_reads[0] += 1
                except json.JSONDecodeError as exc:
                    read_errors.append(f"JSONDecodeError observed during read: {exc}")
                except Exception as exc:
                    read_errors.append(f"Unexpected reader exception: {exc}")
                time.sleep(0.002)

        reader_thread = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        reader_future = reader_thread.submit(reader_worker)

        # Run multiple processes rewriting the file rapidly
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "run_tracker.py"),
            "--output",
            str(self.output_file),
        ]

        procs = []
        for _ in range(write_count):
            procs.append(subprocess.Popen(cmd, cwd=str(PROJECT_ROOT)))

        for p in procs:
            p.wait(timeout=20)
            self.assertEqual(p.returncode, 0)

        stop_readers = True
        reader_future.result(timeout=5)
        reader_thread.shutdown()

        self.assertGreater(successful_reads[0], 10, "Expected at least 10 successful reads")
        self.assertEqual(
            read_errors,
            [],
            f"Atomic write violation! Readers encountered corrupted/partial state: {read_errors}",
        )


class TestCorruptedCacheRecovery(unittest.TestCase):
    """Stress tests verifying resilient recovery from corrupt cache files."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_file = Path(self.temp_dir.name) / "ev_subsidy_data.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def _execute_runner_and_assert_recovery(self):
        """Helper to run run_tracker.py with cache_file as target and assert recovery."""
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "run_tracker.py"),
            "--output",
            str(self.cache_file),
            "--verbose",
        ]
        res = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(
            res.returncode,
            0,
            f"run_tracker.py exited with non-zero returncode {res.returncode}. Stderr:\n{res.stderr}",
        )

        # File must be overwritten with clean, valid JSON
        self.assertTrue(self.cache_file.exists())
        with open(self.cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("metadata", data)
        self.assertEqual(len(data["regions"]), 17)
        self.assertIn("Generating authoritative 2026 baseline", res.stderr + res.stdout)

    def test_truncated_malformed_json_recovery(self):
        """Malformed/truncated JSON in cache file must be safely overwritten."""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            f.write('{"metadata": {"version": "1.0.0", "incomplete_key": [1, 2, 3')

        self._execute_runner_and_assert_recovery()

    def test_invalid_utf8_binary_corruption_recovery(self):
        """File containing invalid UTF-8 byte sequences must not crash the pipeline."""
        with open(self.cache_file, "wb") as f:
            # Random non-UTF8 bytes
            f.write(b"\xff\xfe\x00\x12\x80\x99\xff\xee\xdd\xcc\xbb\xaa\x00\x00")

        self._execute_runner_and_assert_recovery()

    def test_zero_byte_empty_file_recovery(self):
        """Zero-byte 0-length file must not cause unhandled EOF errors."""
        self.cache_file.touch()
        self.assertEqual(self.cache_file.stat().st_size, 0)

        self._execute_runner_and_assert_recovery()

    def test_null_bytes_corruption_recovery(self):
        """File filled with null bytes must trigger graceful fallback."""
        with open(self.cache_file, "wb") as f:
            f.write(b"\x00" * 4096)

        self._execute_runner_and_assert_recovery()

    def test_non_dict_json_recovery(self):
        """Valid JSON that is a list or scalar instead of a dict must trigger graceful fallback."""
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump(["not", "a", "dict", 123], f)

        self._execute_runner_and_assert_recovery()

    def test_structural_schema_corruption_failure_mode(self):
        """Document and verify empirical vulnerability: syntactically valid JSON with malformed

        types (e.g. regions: 'not_a_list') bypasses from_dict and raises unhandled AttributeError
        in execute_tracking_cycle outside the try-except block, causing exit code 1.
        """
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump({"unrelated_field": "test", "numbers": [1, 2, 3], "regions": "not_a_list"}, f)

        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "run_tracker.py"),
            "--output",
            str(self.cache_file),
            "--verbose",
        ]
        res = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
        # Empirically captures that pipeline exits with 1 due to unhandled AttributeError
        self.assertEqual(res.returncode, 1)
        self.assertIn("AttributeError", res.stderr)
        self.assertIn("has no attribute 'categories'", res.stderr)

    def test_empty_regions_cache_degeneracy_vulnerability(self):
        """Document empirical vulnerability: cache with empty regions [] is accepted as valid,

        wiping out all 17 administrative regions instead of falling back to authoritative baseline.
        """
        with open(self.cache_file, "w", encoding="utf-8") as f:
            json.dump({"regions": []}, f)

        tracker = SubsidyTracker(cache_fallback_path=self.cache_file)
        payload, fallback_used = tracker.execute_tracking_cycle()
        # Vulnerability: len(payload.regions) becomes 0 instead of falling back to baseline (17 regions)
        self.assertEqual(len(payload.regions), 0)
        self.assertTrue(fallback_used)




class TestMathematicalLimitsAndEdgeCases(unittest.TestCase):
    """Stress tests for mathematical boundary conditions, division by zero, and over-subscription."""

    def setUp(self):
        self.tracker = SubsidyTracker()

    def test_zero_announced_units_division_by_zero_defense(self):
        """When announced units = 0, rates must safely evaluate to 0.0 with 0 remaining units."""
        # 1. Category level
        cat = self.tracker.calculate_category_metrics(
            announced=0,
            applied=0,
            delivered=0,
            max_local_subsidy=3_000_000,
        )
        self.assertEqual(cat.depletion_rate, 0.0)
        self.assertEqual(cat.delivery_rate, 0.0)
        self.assertEqual(cat.remaining_units, 0)
        self.assertEqual(cat.status, "HEALTHY")
        self.assertEqual(cat.total_budget_krw, 0)
        self.assertEqual(cat.remaining_budget_krw, 0)

        # 2. When announced = 0 but applied > 0 (anomaly case)
        cat_anomaly = self.tracker.calculate_category_metrics(
            announced=0,
            applied=50,
            delivered=10,
            max_local_subsidy=3_000_000,
        )
        self.assertEqual(cat_anomaly.depletion_rate, 0.0)
        self.assertEqual(cat_anomaly.delivery_rate, 0.0)
        self.assertEqual(cat_anomaly.remaining_units, 0)

    def test_nationwide_all_zero_announced_units(self):
        """If all regions have 0 announced units, nationwide aggregations must not raise ZeroDivisionError."""
        payload = build_initial_baseline()
        for r in payload.regions:
            for cat in r.categories.values():
                cat.announced_units = 0
                cat.applied_units = 0
                cat.delivered_units = 0
                cat.total_budget_krw = 0
                cat.remaining_budget_krw = 0
            self.tracker.update_region_metrics(r)

        summary = self.tracker.compute_nationwide_summary(payload.regions)
        self.assertEqual(summary.total_announced_units, 0)
        self.assertEqual(summary.total_applied_units, 0)
        self.assertEqual(summary.nationwide_depletion_rate, 0.0)
        self.assertEqual(summary.total_remaining_units, 0)

    def test_over_subscription_clamping(self):
        """When applied > announced (>100%), remaining units and budget must clamp to 0."""
        # Case: 1,000 announced, 1,850 applied (185% depletion rate)
        cat = self.tracker.calculate_category_metrics(
            announced=1000,
            applied=1850,
            delivered=900,
            max_local_subsidy=4_000_000,
        )
        self.assertEqual(cat.announced_units, 1000)
        self.assertEqual(cat.applied_units, 1850)
        self.assertEqual(cat.remaining_units, 0)  # Must be clamped, NEVER negative -850
        self.assertEqual(cat.depletion_rate, 185.0)
        self.assertEqual(cat.status, "DEPLETED")
        self.assertEqual(cat.remaining_budget_krw, 0)

    def test_alert_severity_threshold_boundaries(self):
        """Exhaustive boundary testing for 5-tier alert severity thresholds."""
        test_cases = [
            (0.0, AlertSeverity.HEALTHY),
            (59.9, AlertSeverity.HEALTHY),
            (60.0, AlertSeverity.CAUTION),
            (79.9, AlertSeverity.CAUTION),
            (80.0, AlertSeverity.WARNING),
            (94.9, AlertSeverity.WARNING),
            (95.0, AlertSeverity.CRITICAL),
            (99.9, AlertSeverity.CRITICAL),
            (100.0, AlertSeverity.DEPLETED),
            (100.01, AlertSeverity.DEPLETED),
            (500.0, AlertSeverity.DEPLETED),
        ]
        for rate, expected_severity in test_cases:
            with self.subTest(rate=rate):
                self.assertEqual(AlertSeverity.from_rate(rate), expected_severity)


class TestCLIExtremes(unittest.TestCase):
    """Stress tests for CLI options, non-existent directories, permissions, and dry-run."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_unknown_cli_flags_exit_code(self):
        """Unknown CLI flag must fail cleanly with argparse exit code 2."""
        res = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "run_tracker.py"), "--invalid-flag-12345"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 2)
        self.assertIn("unrecognized arguments", res.stderr)

    def test_missing_argument_value_exit_code(self):
        """Flag missing mandatory value must fail cleanly with exit code 2."""
        res = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "run_tracker.py"), "--output"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 2)
        self.assertIn("expected one argument", res.stderr)

    def test_non_existent_deep_nested_directory_auto_creation(self):
        """Providing output path with deeply nested non-existent directories must auto-create them."""
        deep_target = Path(self.temp_dir.name) / "level1" / "level2" / "level3" / "target.json"
        self.assertFalse(deep_target.parent.exists())

        res = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "run_tracker.py"),
                "--output",
                str(deep_target),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, f"Failed to auto-create dirs. Stderr: {res.stderr}")
        self.assertTrue(deep_target.exists())
        self.assertTrue(deep_target.parent.exists())

        with open(deep_target, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(len(data["regions"]), 17)

    def test_dry_run_guarantees_no_disk_write(self):
        """--dry-run must calculate metrics and output executive summary without touching disk."""
        target_path = Path(self.temp_dir.name) / "must_not_exist.json"

        res = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "run_tracker.py"),
                "--output",
                str(target_path),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertFalse(target_path.exists(), "Target file was created despite --dry-run flag!")
        # Executive summary must be present in stdout
        self.assertIn("전국 지자체 전기차 보조금 실시간 소진율 모니터링", res.stdout)
        self.assertIn("전국 평균 소진율", res.stdout)

    def test_dry_run_with_sync_web_precedence(self):
        """--dry-run must prevent --sync-web from writing files."""
        web_target = (PROJECT_ROOT / "src" / "data" / "ev_subsidy_data.json") if (PROJECT_ROOT / "src" / "data").exists() else (PROJECT_ROOT / "ev-stealth-web" / "src" / "data" / "ev_subsidy_data.json")
        target_path = Path(self.temp_dir.name) / "test_dry_sync.json"

        # Record mtime of web_target if exists
        prev_mtime = web_target.stat().st_mtime if web_target.exists() else None

        res = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "run_tracker.py"),
                "--output",
                str(target_path),
                "--sync-web",
                "--dry-run",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertFalse(target_path.exists())
        if prev_mtime is not None:
            self.assertEqual(web_target.stat().st_mtime, prev_mtime)

    def test_unwritable_directory_error_handling(self):
        """Targeting a directory without write permissions must raise error cleanly without orphan temp files."""
        read_only_dir = Path(self.temp_dir.name) / "readonly_dir"
        read_only_dir.mkdir(parents=True, exist_ok=True)
        # Set permissions to read-only (r-x r-x r-x = 0o555)
        os.chmod(read_only_dir, stat.S_IRUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP)

        target = read_only_dir / "cannot_write.json"

        try:
            res = subprocess.run(
                [
                    sys.executable,
                    str(PROJECT_ROOT / "run_tracker.py"),
                    "--output",
                    str(target),
                ],
                capture_output=True,
                text=True,
            )
            # Should exit with returncode 1 (fatal unhandled exception caught by main)
            self.assertEqual(res.returncode, 1)
            self.assertIn("Fatal error in subsidy tracker pipeline", res.stderr)
        finally:
            # Restore permissions so cleanup succeeds
            os.chmod(read_only_dir, stat.S_IRWXU)


if __name__ == "__main__":
    unittest.main()
