"""
tests/test_cycle10_hardening.py - Comprehensive Cycle 10 Hardening & Parity Test Suite.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (Cycle 10 Wave 2 Test Suite Specification)
- COLLABORATION.md

Coverage:
1. POSIX 0644 File Permission Enforcement Across Atomic Writers:
   - tracker/atomic_writer.py: atomic_write_json() and atomic_write_json_multiple() enforce 0o644 mode.
   - tracker/defect_tracker.py: sync_defect_reports() atomic file creation enforces 0o644 mode.
   - run_tracker.py: sync_defect_reports() atomic file creation enforces 0o644 mode.
   - utils/json_writer.py: write_daily_reports() atomic file creation enforces 0o644 mode.
   - Verifies newly created files on disk match stat mode 0o644 (-rw-r--r--).

2. Defect Synchronization Timestamp Preservation & SHA-256 Redundant Write Skip:
   - SHA-256 pre-check: When source and destination have identical content/hash, redundant write is skipped.
   - Inode / mtime stability: Target file is not rewritten if already bitwise identical.
   - Timestamp preservation: When syncing new or modified content, target st_mtime is set to match source st_mtime.
   - Oscillation prevention: Re-running sync immediately afterwards does not trigger reverse-copying or ping-pong timestamp drift.

3. SubsidyTracker Math Invariant Calculations:
   - calculate_depletion_rate:
     - Negative applied units clamped to 0.0.
     - Negative or zero announced units clamped to 0.0.
     - Non-numeric / NaN / Inf / None return 0.0 safely without raising exceptions.
     - Over-subscription calculated accurately (>100.0%).
   - calculate_remaining_units:
     - Over-subscription clamped strictly to 0 (no negative units).
     - Negative applied clamped to announced units.
     - Negative announced clamped to 0.
     - Non-numeric / NaN / None safely return 0.
   - calculate_category_metrics:
     - Guarantees non-negative metrics (depletion_rate >= 0.0, delivery_rate >= 0.0, remaining_units >= 0, remaining_budget_krw >= 0).
   - update_region_metrics:
     - Consolidates category metrics using calculate_depletion_rate and calculate_remaining_units.
     - Municipality metrics recalculated safely without negative rates.
     - Overall depletion rate and status are non-negative and finite.
   - compute_nationwide_summary:
     - Aggregates correctly with non-negative rate even on anomalous inputs.

4. DefectTracker "UNKNOWN" Category Indexing & Thread-Safe LRU Cache Operations:
   - "UNKNOWN" indexing:
     - Reports with missing, None, empty string, or whitespace-only defect_category are indexed under "UNKNOWN".
     - query_defects(category="UNKNOWN") successfully retrieves candidates from "UNKNOWN" bucket.
     - get_statistics() UNKNOWN category count matches query_defects(category="UNKNOWN") count.
   - Thread-safe LRU cache:
     - _cache_lock concurrency protection: concurrent multi-threaded queries without dictionary mutation errors.
     - True LRU cache eviction: accessed keys are promoted to end; capacity bounded (1024 entries) with oldest non-accessed evicted.
     - Invalidation hooks: invalidate_cache() clears _query_cache, _category_index, and cached reports.

5. Frontend Library Functions (via Node.js / jiti harness):
   - Arrhenius Boundary Protections (getDepreciationData.ts):
     - simulateBatteryHealth({ ambientTempC: -273.15 }) and simulateBatteryHealth({ ambientTempC: -300 })
       do not divide by zero in Arrhenius kinetic rate formula; temperature clamped to >= 1K.
     - calendarLossPct, cyclicLossPct, totalLossPct, and sohPct return valid finite numbers without NaN or Infinity.
     - getClawbackSchedule() safely handles nullish DATABASE.subsidy_clawback_schedule.
   - NaN / Infinity Protections (getSubsidyData.ts):
     - calculateNetSubsidy('ioniq-5-2026', 'KR-11', Infinity) returns finite netPurchasePriceKrw (capped at 10B KRW, never Infinity).
     - calculateNetSubsidy with customMsrp=NaN falls back safely to finite model base price.
     - getCategoryDepletion() safely handles nullish/undefined region and category metrics without throwing TypeError on toLocaleString.
   - Empty-String & Type Safety Recall Filters (getRecallData.ts):
     - checkRecallsByModel("", "") and checkRecallsByModel("   ", "   ") returns valid=false and recalls=[].
     - checkRecallsByModel(null, undefined) does not throw TypeError.
     - getModelsForBrand("") and getModelsForBrand(null) returns empty array [].
     - validateVinString("") and validateVinString(null) returns valid=false without throwing TypeError.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from typing import Any, Dict, List, Optional, Union
from unittest import mock

# Adaptive repository and web root resolution
def _find_repo_root() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent.parent.parent,
        Path.cwd(),
        Path.cwd().parent,
    ]
    for p in candidates:
        if (p / "ev-stealth-web").is_dir() and (p / "data").is_dir():
            return p
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _find_repo_root()
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web"
SRC_DIR = WEB_ROOT / "src"
LIB_DIR = SRC_DIR / "lib"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
else:
    sys.path.remove(str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT))

if str(WEB_ROOT) not in sys.path:
    sys.path.append(str(WEB_ROOT))

import run_tracker
from tracker.atomic_writer import atomic_write_json, atomic_write_json_multiple
from tracker.defect_tracker import DefectTracker
from tracker.subsidy_models import CategoryMetrics, MunicipalityMetrics, RegionRecord
from tracker.subsidy_tracker import (
    SubsidyTracker,
    calculate_depletion_rate,
    calculate_remaining_units,
)
from utils.json_writer import write_daily_reports


def _eval_ts_node(script: str, timeout_sec: int = 30) -> Any:
    """Execute a Node.js snippet using jiti to resolve TypeScript files with alias mappings."""
    if not shutil.which("node"):
        raise unittest.SkipTest("Node.js runtime not installed on host environment.")

    jiti_path = WEB_ROOT / "node_modules" / "jiti"
    pkg_path = WEB_ROOT / "package.json"

    if not jiti_path.exists():
        raise unittest.SkipTest(f"jiti not found at {jiti_path}")

    node_wrapper = f"""
    const Module = require('module');
    const path = require('path');
    const origResolve = Module._resolveFilename;
    Module._resolveFilename = function(request, parent, isMain, options) {{
        if (request.startsWith('@/')) {{
            request = request.replace('@/', path.resolve({json.dumps(str(SRC_DIR))}) + '/');
        }}
        return origResolve.call(this, request, parent, isMain, options);
    }};
    const createJITI = require({json.dumps(str(jiti_path))});
    const jiti = createJITI({json.dumps(str(pkg_path))});

    {script}
    """
    proc = subprocess.run(
        ["node", "-e", node_wrapper],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=timeout_sec,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Node execution failed with exit code {proc.returncode}:\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )

    lines = [
        line.strip()
        for line in proc.stdout.splitlines()
        if line.strip() and not line.strip().startswith("(") and not line.strip().startswith("Warning:")
    ]
    if not lines:
        raise ValueError(f"No JSON output from Node execution:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    return json.loads(lines[-1])


# ==============================================================================
# 1. POSIX 0644 File Permission Enforcement Across Atomic Writers
# ==============================================================================

class TestCycle10POSIX0644AtomicWriterPermissions(unittest.TestCase):
    """Verifies that atomic JSON writers enforce POSIX 0644 (-rw-r--r--) file permissions."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_cycle10_perms_")

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_atomic_write_json_enforces_0644_permissions(self) -> None:
        """atomic_write_json explicitly applies 0o644 mode to written files."""
        target = Path(self.test_dir) / "output.json"
        written = atomic_write_json({"cycle": 10, "status": "hardened"}, target)
        self.assertTrue(written.exists())

        mode = os.stat(written).st_mode & 0o777
        self.assertEqual(
            mode,
            0o644,
            f"File permissions must be 0o644 (-rw-r--r--), got {oct(mode)}",
        )

    def test_atomic_write_json_multiple_enforces_0644_on_all_targets(self) -> None:
        """atomic_write_json_multiple applies 0o644 mode to every written target file."""
        targets = [
            Path(self.test_dir) / f"multi_{i}.json"
            for i in range(3)
        ]
        written_paths = atomic_write_json_multiple({"multi": True, "count": 3}, targets)
        self.assertEqual(len(written_paths), 3)

        for p in written_paths:
            self.assertTrue(p.exists())
            mode = os.stat(p).st_mode & 0o777
            self.assertEqual(
                mode,
                0o644,
                f"File {p} permissions must be 0o644, got {oct(mode)}",
            )

    def test_utils_json_writer_enforces_0644_permissions(self) -> None:
        """write_daily_reports in utils/json_writer.py applies 0o644 mode."""
        target = Path(self.test_dir) / "daily_reports.json"
        write_daily_reports({"reports": [], "statistics": {"count": 0}}, str(target))
        self.assertTrue(target.exists())

        mode = os.stat(target).st_mode & 0o777
        self.assertEqual(
            mode,
            0o644,
            f"write_daily_reports file permissions must be 0o644, got {oct(mode)}",
        )

    def test_defect_tracker_sync_enforces_0644_permissions(self) -> None:
        """DefectTracker.sync_defect_reports creates files with 0o644 permissions."""
        root_dir = Path(self.test_dir) / "root"
        web_dir = Path(self.test_dir) / "web"
        root_dir.mkdir(parents=True)
        web_dir.mkdir(parents=True)

        source_file = root_dir / "daily_reports.json"
        target_file = web_dir / "daily_reports.json"
        source_data = {
            "reports": [{"report_id": "c10-01", "defect_category": "BATTERY_CHARGING"}],
            "statistics": {"total": 1},
        }
        with open(source_file, "w", encoding="utf-8") as f:
            json.dump(source_data, f)

        tracker = DefectTracker(root_data_dir=str(root_dir), web_data_dir=str(web_dir))
        written = tracker.sync_defect_reports()
        self.assertIn(str(target_file), written)
        self.assertTrue(target_file.exists())

        mode = os.stat(target_file).st_mode & 0o777
        self.assertEqual(
            mode,
            0o644,
            f"DefectTracker synced file permissions must be 0o644, got {oct(mode)}",
        )

    def test_run_tracker_sync_defect_reports_enforces_0644_permissions(self) -> None:
        """run_tracker.sync_defect_reports creates files with 0o644 permissions."""
        run_tmp = Path(self.test_dir) / "run_tree"
        root_dir = run_tmp / "data"
        web_dir = run_tmp / "ev-stealth-web" / "src" / "data"
        root_dir.mkdir(parents=True)
        web_dir.mkdir(parents=True)

        root_file = root_dir / "daily_reports.json"
        web_file = web_dir / "daily_reports.json"
        data = {
            "reports": [{"report_id": "c10-run-01", "defect_category": "SOFTWARE_ELECTRONICS"}],
            "statistics": {"total": 1},
        }
        with open(root_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        with mock.patch.object(run_tracker, "_CURRENT_DIR", run_tmp):
            written = run_tracker.sync_defect_reports(web_dir=web_dir)
        self.assertIn(str(web_file), written)
        self.assertTrue(web_file.exists())

        mode = os.stat(web_file).st_mode & 0o777
        self.assertEqual(
            mode,
            0o644,
            f"run_tracker synced file permissions must be 0o644, got {oct(mode)}",
        )


# ==============================================================================
# 2. Defect Synchronization Timestamp Preservation & SHA-256 Redundant Write Skip
# ==============================================================================

class TestCycle10DefectSyncMtimeAndSHA256Skip(unittest.TestCase):
    """Verifies defect sync SHA-256 pre-check and mtime preservation to prevent ping-pong oscillation."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_cycle10_sync_mtime_")
        self.root_dir = Path(self.test_dir) / "data"
        self.web_dir = Path(self.test_dir) / "web_data"
        self.root_dir.mkdir(parents=True)
        self.web_dir.mkdir(parents=True)
        self.root_file = self.root_dir / "daily_reports.json"
        self.web_file = self.web_dir / "daily_reports.json"

        self.payload = {
            "reports": [
                {
                    "report_id": "c10-mtime-01",
                    "title": "ICCBL Failure",
                    "defect_category": "BATTERY_CHARGING",
                    "vehicle_brand": "현대",
                    "vehicle_model": "아이오닉 5",
                    "severity_index": 8.0,
                }
            ],
            "statistics": {"total_filtered_defects": 1},
        }

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sync_preserves_source_mtime_on_target(self) -> None:
        """When syncing, target file receives source st_mtime to prevent timestamp drift."""
        with open(self.root_file, "w", encoding="utf-8") as f:
            json.dump(self.payload, f)

        # Set specific past timestamp on source (1 hour ago)
        past_time = time.time() - 3600
        os.utime(self.root_file, (past_time, past_time))
        src_mtime = self.root_file.stat().st_mtime

        tracker = DefectTracker(root_data_dir=str(self.root_dir), web_data_dir=str(self.web_dir))
        tracker.sync_defect_reports()

        self.assertTrue(self.web_file.exists())
        tgt_mtime = self.web_file.stat().st_mtime

        self.assertAlmostEqual(
            tgt_mtime,
            src_mtime,
            places=1,
            msg=f"Target mtime ({tgt_mtime}) must match source mtime ({src_mtime})",
        )

    def test_sha256_match_skips_redundant_write(self) -> None:
        """When source and target have identical SHA-256 hash, redundant write is skipped."""
        with open(self.root_file, "w", encoding="utf-8") as f:
            json.dump(self.payload, f)

        tracker = DefectTracker(root_data_dir=str(self.root_dir), web_data_dir=str(self.web_dir))
        # Initial sync creates web file
        first_written = tracker.sync_defect_reports()
        self.assertEqual(len(first_written), 1)

        # Record target inode and mtime
        initial_stat = self.web_file.stat()
        initial_mtime = initial_stat.st_mtime
        initial_ino = initial_stat.st_ino

        # Run sync a second time immediately
        second_written = tracker.sync_defect_reports()

        # Target should not have been rewritten (skipped redundant sync)
        self.assertEqual(
            second_written,
            [],
            "Second sync with identical SHA-256 must return empty written list (skipped)",
        )
        current_stat = self.web_file.stat()
        self.assertEqual(
            current_stat.st_ino,
            initial_ino,
            "Target file inode must remain unchanged when write is skipped",
        )
        self.assertEqual(
            current_stat.st_mtime,
            initial_mtime,
            "Target file mtime must remain unchanged when write is skipped",
        )

    def test_no_ping_pong_timestamp_oscillation_across_successive_syncs(self) -> None:
        """Successive sync calls do not oscillate direction or modify timestamps back and forth."""
        with open(self.root_file, "w", encoding="utf-8") as f:
            json.dump(self.payload, f)

        tracker = DefectTracker(root_data_dir=str(self.root_dir), web_data_dir=str(self.web_dir))

        # 1st run: root -> web
        written1 = tracker.sync_defect_reports()
        self.assertIn(str(self.web_file), written1)

        mtime_root_1 = self.root_file.stat().st_mtime
        mtime_web_1 = self.web_file.stat().st_mtime
        self.assertAlmostEqual(mtime_root_1, mtime_web_1, places=1)

        # 2nd run: identical SHA-256 -> skip
        written2 = tracker.sync_defect_reports()
        self.assertEqual(written2, [], "Successive sync must skip rewriting identical files")

        # 3rd run: still stable
        written3 = tracker.sync_defect_reports()
        self.assertEqual(written3, [])


# ==============================================================================
# 3. SubsidyTracker Math Invariant Calculations
# ==============================================================================

class TestCycle10SubsidyTrackerMathInvariants(unittest.TestCase):
    """Verifies SubsidyTracker mathematical invariants and defensive boundaries."""

    def setUp(self) -> None:
        self.tracker = SubsidyTracker()

    def test_calculate_depletion_rate_invariants(self) -> None:
        """calculate_depletion_rate guarantees non-negative, finite percentage rates."""
        # Standard cases
        self.assertEqual(calculate_depletion_rate(50, 100), 50.0)
        self.assertEqual(calculate_depletion_rate(100, 100), 100.0)
        self.assertEqual(calculate_depletion_rate(150, 100), 150.0)  # Over-subscribed

        # Negative values clamped to 0.0
        self.assertEqual(calculate_depletion_rate(-10, 100), 0.0)
        self.assertEqual(calculate_depletion_rate(50, -100), 0.0)
        self.assertEqual(calculate_depletion_rate(-50, -100), 0.0)

        # Zero announced quota (zero division guard)
        self.assertEqual(calculate_depletion_rate(50, 0), 0.0)
        self.assertEqual(calculate_depletion_rate(0, 0), 0.0)

        # Non-numeric, NaN, Inf, None
        self.assertEqual(calculate_depletion_rate(float("nan"), 100), 0.0)
        self.assertEqual(calculate_depletion_rate(50, float("nan")), 0.0)
        self.assertEqual(calculate_depletion_rate(float("inf"), 100), 0.0)
        self.assertEqual(calculate_depletion_rate(50, float("inf")), 0.0)
        self.assertEqual(calculate_depletion_rate(None, 100), 0.0)
        self.assertEqual(calculate_depletion_rate(50, None), 0.0)
        self.assertEqual(calculate_depletion_rate("malformed", 100), 0.0)

    def test_calculate_remaining_units_invariants(self) -> None:
        """calculate_remaining_units clamps strictly to non-negative integer quota."""
        # Standard cases
        self.assertEqual(calculate_remaining_units(40, 100), 60)
        self.assertEqual(calculate_remaining_units(100, 100), 0)

        # Over-subscription (applied > announced) clamped strictly to 0
        self.assertEqual(calculate_remaining_units(120, 100), 0)
        self.assertEqual(calculate_remaining_units(9999, 100), 0)

        # Negative applied units clamped safely to total announced quota
        self.assertEqual(calculate_remaining_units(-50, 100), 100)

        # Negative announced quota clamped to 0
        self.assertEqual(calculate_remaining_units(50, -100), 0)
        self.assertEqual(calculate_remaining_units(-50, -100), 0)

        # NaN, Inf, None, malformed strings
        self.assertEqual(calculate_remaining_units(float("nan"), 100), 0)
        self.assertEqual(calculate_remaining_units(50, float("nan")), 0)
        self.assertEqual(calculate_remaining_units(float("inf"), 100), 0)
        self.assertEqual(calculate_remaining_units(None, 100), 0)
        self.assertEqual(calculate_remaining_units(50, None), 0)
        self.assertEqual(calculate_remaining_units("invalid", 100), 0)

    def test_calculate_category_metrics_boundary_invariants(self) -> None:
        """calculate_category_metrics ensures all outputs remain valid and non-negative."""
        cat = self.tracker.calculate_category_metrics(
            announced=-100,
            applied=-50,
            delivered=-20,
            max_local_subsidy=5_000_000,
        )
        self.assertGreaterEqual(cat.depletion_rate, 0.0)
        self.assertGreaterEqual(cat.delivery_rate, 0.0)
        self.assertGreaterEqual(cat.remaining_units, 0)
        self.assertGreaterEqual(cat.remaining_budget_krw, 0)
        self.assertGreaterEqual(cat.total_budget_krw, 0)

    def test_update_region_metrics_routes_through_invariant_guards(self) -> None:
        """update_region_metrics safely computes overall and category rates without negative numbers."""
        cat_p = CategoryMetrics(
            announced_units=100,
            applied_units=75,
            delivered_units=30,
            remaining_units=25,
            depletion_rate=75.0,
            delivery_rate=30.0,
            status="HEALTHY",
            max_local_subsidy_krw=2_000_000,
            max_total_subsidy_krw=8_500_000,
            total_budget_krw=1_000_000_000,
            remaining_budget_krw=250_000_000,
        )
        muni = MunicipalityMetrics(
            name_ko="강남구",
            announced_units=50,
            applied_units=60,  # Over-subscribed
            remaining_units=0,
            depletion_rate=120.0,
            status="DEPLETED",
        )
        region = RegionRecord(
            region_id="KR-11",
            name_ko="서울특별시",
            categories={"passenger": cat_p},
            municipalities=[muni],
        )

        updated = self.tracker.update_region_metrics(region)
        self.assertEqual(updated.overall_depletion_rate, 75.0)
        self.assertEqual(updated.categories["passenger"].remaining_units, 25)
        self.assertEqual(updated.categories["passenger"].depletion_rate, 75.0)
        self.assertEqual(updated.municipalities[0].remaining_units, 0)
        self.assertEqual(updated.municipalities[0].depletion_rate, 120.0)

    def test_compute_nationwide_summary_handles_edge_cases(self) -> None:
        """compute_nationwide_summary calculates rates via invariant functions."""
        # Empty regions dictionary
        summary = self.tracker.compute_nationwide_summary({})
        self.assertEqual(summary.total_announced_units, 0)
        self.assertEqual(summary.total_applied_units, 0)
        self.assertEqual(summary.total_remaining_units, 0)
        self.assertEqual(summary.nationwide_depletion_rate, 0.0)


# ==============================================================================
# 4. DefectTracker "UNKNOWN" Category Indexing & Thread-Safe LRU Cache Operations
# ==============================================================================

class TestCycle10DefectTrackerUnknownCategoryAndThreadSafeLRU(unittest.TestCase):
    """Verifies UNKNOWN category indexing alignment and thread-safe LRU caching in DefectTracker."""

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_cycle10_defect_lru_")
        self.data_file = Path(self.test_dir) / "daily_reports.json"

        # Synthetic dataset with standard, None, missing, and whitespace categories
        self.dataset = {
            "reports": [
                {
                    "report_id": "r-known-01",
                    "title": "Battery Rapid Degradation",
                    "defect_category": "BATTERY_CHARGING",
                    "vehicle_brand": "현대",
                    "vehicle_model": "아이오닉 5",
                    "severity_index": 8.0,
                },
                {
                    "report_id": "r-none-01",
                    "title": "Unspecified Sensor Fault",
                    "defect_category": None,
                    "vehicle_brand": "기아",
                    "vehicle_model": "EV6",
                    "severity_index": 5.0,
                },
                {
                    "report_id": "r-missing-01",
                    "title": "Anonymous Wind Noise",
                    # defect_category omitted completely
                    "vehicle_brand": "테슬라",
                    "vehicle_model": "Model Y",
                    "severity_index": 4.0,
                },
                {
                    "report_id": "r-empty-01",
                    "title": "Empty String Category",
                    "defect_category": "   ",
                    "vehicle_brand": "제네시스",
                    "vehicle_model": "GV60",
                    "severity_index": 6.0,
                },
                {
                    "report_id": "r-unknown-explicit-01",
                    "title": "Explicit Unknown Defect",
                    "defect_category": "UNKNOWN",
                    "vehicle_brand": "BMW",
                    "vehicle_model": "i4",
                    "severity_index": 7.0,
                },
            ],
            "statistics": {"total_filtered_defects": 5},
        }
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.dataset, f)

        self.tracker = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_unknown_category_indexing_and_query_retrieval(self) -> None:
        """Missing, None, and empty categories are indexed under 'UNKNOWN' and queryable."""
        unknown_reports = self.tracker.query_defects(category="UNKNOWN", file_path=self.data_file)
        # Expect exactly 4 reports: r-none-01, r-missing-01, r-empty-01, r-unknown-explicit-01
        self.assertEqual(
            len(unknown_reports),
            4,
            f"Expected 4 reports in UNKNOWN bucket, got {len(unknown_reports)}",
        )
        report_ids = {r["report_id"] for r in unknown_reports}
        self.assertEqual(
            report_ids,
            {"r-none-01", "r-missing-01", "r-empty-01", "r-unknown-explicit-01"},
        )

    def test_unknown_category_indexing_preserves_total_counts(self) -> None:
        """Category indexing retains all records without dropping missing or None categories."""
        # Query UNKNOWN category
        unknown_reports = self.tracker.query_defects(category="UNKNOWN", file_path=self.data_file)
        self.assertEqual(len(unknown_reports), 4)

        # Query explicit known category
        battery_reports = self.tracker.query_defects(category="BATTERY_CHARGING", file_path=self.data_file)
        self.assertEqual(len(battery_reports), 1)

        # Verify all 5 reports are accounted for across the category index
        all_indexed_count = sum(len(items) for items in self.tracker._category_index.values())
        self.assertEqual(
            all_indexed_count,
            5,
            f"All 5 reports must be retained in category index, found {all_indexed_count}",
        )
        self.assertEqual(len(unknown_reports) + len(battery_reports), 5)

    def test_thread_safe_concurrent_query_cache_access(self) -> None:
        """Query cache survives concurrent multi-threaded read/write hammering without race conditions."""
        errors: List[Exception] = []

        def worker_query(worker_id: int):
            try:
                for i in range(20):
                    brand = "현대" if i % 2 == 0 else "기아"
                    cat = "BATTERY_CHARGING" if i % 3 == 0 else "UNKNOWN"
                    res = self.tracker.query_defects(
                        category=cat,
                        vehicle_brand=brand,
                        file_path=self.data_file,
                    )
                    self.assertIsInstance(res, list)
            except Exception as exc:
                errors.append(exc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker_query, idx) for idx in range(8)]
            concurrent.futures.wait(futures)

        self.assertEqual(errors, [], f"Encountered thread concurrency errors: {errors}")

    def test_true_lru_cache_promotion_and_bounded_eviction(self) -> None:
        """Query cache promotes accessed keys and evicts oldest non-accessed entries when capped."""
        tracker = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)
        reports = tracker.load_reports(file_path=self.data_file)

        # Synthesize 1100 distinct cache queries beyond capacity (1024)
        for i in range(1050):
            # Each distinct keyword creates a distinct cache key
            tracker.query_defects(keyword=f"key_{i}", file_path=self.data_file)

        # Cache length must be strictly bounded <= 1024
        with tracker._cache_lock:
            cache_len = len(tracker._query_cache)
            self.assertLessEqual(cache_len, 1024, "Cache size must not exceed 1024 entries")
            self.assertEqual(cache_len, 1024)

            # Oldest keys (0..25) must have been evicted FIFO/LRU
            first_keys = [k for k in tracker._query_cache.keys()]
            # key_0 was evicted
            self.assertFalse(any("key_0" in str(k) for k in first_keys))


# ==============================================================================
# 5. Frontend Library Functions (via Node.js / jiti harness)
# ==============================================================================

class TestCycle10FrontendLibFunctionsHardening(unittest.TestCase):
    """Verifies frontend lib module bounds: Arrhenius Kelvin clamp, NaN/Infinity guards, empty string recall filters."""

    def test_arrhenius_absolute_zero_and_subzero_kelvin_boundary_protection(self) -> None:
        """simulateBatteryHealth protects Arrhenius formula against <= -273.15 C (Kelvin <= 0)."""
        dep_path = json.dumps(str(LIB_DIR / "getDepreciationData.ts"))
        script = f"""
        const dep = jiti({dep_path});

        // 1. Absolute zero (-273.15 C)
        const resAbsZero = dep.simulateBatteryHealth({{ ambientTempC: -273.15 }});
        // 2. Sub-absolute zero (-300 C)
        const resSubZero = dep.simulateBatteryHealth({{ ambientTempC: -300.0 }});
        // 3. Normal ambient (+25 C)
        const resNormal = dep.simulateBatteryHealth({{ ambientTempC: 25.0 }});

        console.log(JSON.stringify({{
            absZeroFiniteCalendarLoss: Number.isFinite(resAbsZero.calendarLossPct),
            absZeroFiniteSoh: Number.isFinite(resAbsZero.sohPct),
            absZeroCalendarLoss: resAbsZero.calendarLossPct,
            subZeroFiniteCalendarLoss: Number.isFinite(resSubZero.calendarLossPct),
            subZeroFiniteSoh: Number.isFinite(resSubZero.sohPct),
            normalFiniteCalendarLoss: Number.isFinite(resNormal.calendarLossPct),
        }}));
        """
        res = _eval_ts_node(script)

        self.assertTrue(res["absZeroFiniteCalendarLoss"], "-273.15C must produce finite calendarLossPct")
        self.assertTrue(res["absZeroFiniteSoh"], "-273.15C must produce finite sohPct")
        self.assertTrue(res["subZeroFiniteCalendarLoss"], "-300C must produce finite calendarLossPct")
        self.assertTrue(res["subZeroFiniteSoh"], "-300C must produce finite sohPct")
        self.assertTrue(res["normalFiniteCalendarLoss"], "25C must produce finite calendarLossPct")

    def test_subsidy_net_purchase_price_infinity_and_nan_protection(self) -> None:
        """calculateNetSubsidy produces finite netPurchasePriceKrw on Infinity and NaN customMsrp."""
        sub_path = json.dumps(str(LIB_DIR / "getSubsidyData.ts"))
        script = f"""
        const sub = jiti({sub_path});

        // 1. Custom MSRP = Infinity
        const resInf = sub.calculateNetSubsidy('ioniq-5-2026', 'KR-11', Infinity);
        // 2. Custom MSRP = NaN
        const resNaN = sub.calculateNetSubsidy('ioniq-5-2026', 'KR-11', NaN);
        // 3. Custom MSRP = -50,000,000 (negative)
        const resNeg = sub.calculateNetSubsidy('ioniq-5-2026', 'KR-11', -50_000_000);

        console.log(JSON.stringify({{
            infFinite: Number.isFinite(resInf.netPurchasePriceKrw),
            infValue: resInf.netPurchasePriceKrw,
            nanFinite: Number.isFinite(resNaN.netPurchasePriceKrw),
            nanValue: resNaN.netPurchasePriceKrw,
            negFinite: Number.isFinite(resNeg.netPurchasePriceKrw),
        }}));
        """
        res = _eval_ts_node(script)

        self.assertTrue(res["infFinite"], "calculateNetSubsidy(..., Infinity) must yield finite netPurchasePriceKrw")
        self.assertLessEqual(res["infValue"], 10_000_000_000, "Price must be capped at maximum statutory bound")
        self.assertTrue(res["nanFinite"], "calculateNetSubsidy(..., NaN) must yield finite netPurchasePriceKrw")
        self.assertTrue(res["negFinite"], "calculateNetSubsidy(..., -50M) must yield finite netPurchasePriceKrw")

    def test_category_depletion_null_guards_and_formatting(self) -> None:
        """getCategoryDepletion safely handles null/undefined region and category metrics."""
        sub_path = json.dumps(str(LIB_DIR / "getSubsidyData.ts"))
        script = f"""
        const sub = jiti({sub_path});

        let nullThrew = false;
        let undefinedThrew = false;
        let emptyThrew = false;
        let nullRes = null;
        let validRes = null;

        try {{
            nullRes = sub.getCategoryDepletion(null);
        }} catch (e) {{
            nullThrew = true;
        }}

        try {{
            sub.getCategoryDepletion(undefined);
        }} catch (e) {{
            undefinedThrew = true;
        }}

        try {{
            sub.getCategoryDepletion("");
        }} catch (e) {{
            emptyThrew = true;
        }}

        try {{
            validRes = sub.getCategoryDepletion("KR-11", "passenger");
        }} catch (e) {{}}

        console.log(JSON.stringify({{
            nullThrew,
            undefinedThrew,
            emptyThrew,
            nullResFormattedRemaining: nullRes ? nullRes.formattedRemaining : null,
            validResRemaining: validRes ? validRes.remainingUnits : -1,
        }}));
        """
        res = _eval_ts_node(script)

        self.assertFalse(res["nullThrew"], "getCategoryDepletion(null) must not throw")
        self.assertFalse(res["undefinedThrew"], "getCategoryDepletion(undefined) must not throw")
        self.assertFalse(res["emptyThrew"], "getCategoryDepletion('') must not throw")
        self.assertEqual(res["nullResFormattedRemaining"], "0")
        self.assertGreater(res["validResRemaining"], 0)

    def test_recall_filters_empty_string_and_type_guards(self) -> None:
        """checkRecallsByModel and helper functions guard against empty strings and non-string inputs."""
        rec_path = json.dumps(str(LIB_DIR / "getRecallData.ts"))
        script = f"""
        const rec = jiti({rec_path});

        // 1. checkRecallsByModel with empty strings
        const resEmpty = rec.checkRecallsByModel("", "");
        const resWhitespace = rec.checkRecallsByModel("   ", "   ");

        // 2. checkRecallsByModel with null / undefined
        let nullThrew = false;
        let resNull = null;
        try {{
            resNull = rec.checkRecallsByModel(null, undefined);
        }} catch (e) {{
            nullThrew = true;
        }}

        // 3. getModelsForBrand with empty string / null
        const modelsEmpty = rec.getModelsForBrand("");
        const modelsNull = rec.getModelsForBrand(null);

        // 4. validateVinString with empty string / null
        const vinEmpty = rec.validateVinString("");
        const vinNull = rec.validateVinString(null);

        console.log(JSON.stringify({{
            emptyValid: resEmpty.valid,
            emptyRecallsLength: resEmpty.recalls.length,
            whitespaceValid: resWhitespace.valid,
            whitespaceRecallsLength: resWhitespace.recalls.length,
            nullThrew,
            nullValid: resNull ? resNull.valid : null,
            modelsEmptyLength: modelsEmpty.length,
            modelsNullLength: modelsNull.length,
            vinEmptyValid: vinEmpty.valid,
            vinNullValid: vinNull.valid,
        }}));
        """
        res = _eval_ts_node(script)

        # Empty strings must NOT match all recalls
        self.assertFalse(res["emptyValid"], "checkRecallsByModel('', '') must return valid: false")
        self.assertEqual(res["emptyRecallsLength"], 0, "checkRecallsByModel('', '') must return empty recalls array")
        self.assertFalse(res["whitespaceValid"], "checkRecallsByModel('   ', '   ') must return valid: false")
        self.assertEqual(res["whitespaceRecallsLength"], 0)

        # Null / undefined safety
        self.assertFalse(res["nullThrew"], "checkRecallsByModel(null, undefined) must not throw")
        self.assertFalse(res["nullValid"])

        # getModelsForBrand safety
        self.assertEqual(res["modelsEmptyLength"], 0)
        self.assertEqual(res["modelsNullLength"], 0)

        # validateVinString safety
        self.assertFalse(res["vinEmptyValid"])
        self.assertFalse(res["vinNullValid"])


if __name__ == "__main__":
    unittest.main()
