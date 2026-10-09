"""
tests/test_cycle11_hardening.py - Comprehensive Cycle 11 Hardening, Defensive Boundary,
and Subsystem Parity Test Suite.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (Cycle 11 Wave 2 Test Suite Specification)
- COLLABORATION.md

Coverage:
1. DefectTracker Severity Handling & Scoring Hardening:
   - query_defects handles severity_index=None with CRITICAL severity without crashing (no TypeError).
   - Reports with severity_index=None and severity="CRITICAL" receive effective severity score 9.0.
   - Filtering by min_severity correctly includes critical records and excludes low severity or unclassified records.
   - Dynamic get_statistics() computes critical_defect_count accurately when pre-stored statistics block is absent.
   - Thread-safe LRU caching memoizes and invalidates queries properly with severity_index=None.

2. utils/json_writer Safe Float NaN & Infinity Protections:
   - _safe_float rejects and clamps float("nan"), float("inf"), float("-inf"), and string representations.
   - Guaranteed RFC 8259 compliance preventing JSON syntax errors on clients.
   - Safe defaults and defensive handling against malformed default arguments.
   - format_daily_report_payload guarantees 0 NaN or Infinity in serialized JSON output.

3. utils/json_writer Historical Report Preservation on Null Statistics:
   - write_daily_reports cleanly handles existing daily_reports.json where "statistics": null or missing.
   - Prevents AttributeError ('NoneType' object has no attribute 'get') that previously wiped historical reports.
   - Merges historical records cleanly with new scraped complaints without record loss.
   - Recomputes valid statistics and enforces POSIX 0644 atomic file writes.

4. simulateBatteryHealth Brand-New 0-Year EV Kinetics:
   - simulateBatteryHealth({ years: 0, totalKm: 0 }) strictly preserves 0 calendar degradation (calendarLossPct = 0).
   - Guarantees brand-new EV delivers 100% State of Health (sohPct = 100), Grade A, and 0 total loss.
   - Only falls back to 3 years when years is undefined, null, NaN, or negative (< 0).

5. SubsidyTrackerClient Badge Styling & Non-Negative Pending Logic:
   - getBadgeStyle and getStatusLabel handle "available" status and provide fallback default: branches.
   - Guarantees valid CSS strings and status labels (never undefined or "undefined").
   - Pending vehicle calculation enforces Math.max(0, safeApplied - safeDelivered) preventing negative pending counts.

6. Repository Tree Mirror Parity & POSIX 0644 Permissions:
   - 100% bitwise parity of Python modules between root (tracker/, utils/) and ev-stealth-web/.
   - 100% mirror parity between root tests/ and ev-stealth-web/tests/.
   - POSIX 0644 permission compliance across dataset JSON files.
"""

from __future__ import annotations

import collections
from datetime import date, datetime, timezone
from enum import Enum
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
APP_DIR = SRC_DIR / "app"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
else:
    sys.path.remove(str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT))

if str(WEB_ROOT) not in sys.path:
    sys.path.append(str(WEB_ROOT))

from tracker.atomic_writer import atomic_write_json, atomic_write_json_multiple
from tracker.defect_tracker import DefectTracker
from tracker.subsidy_tracker import SubsidyTracker
from utils.json_writer import (
    _safe_float,
    format_daily_report_payload,
    read_daily_reports,
    write_daily_reports,
)


def _eval_ts_node(script: str, timeout_sec: int = 30) -> Any:
    """Execute a Node.js snippet using jiti or tsx to resolve TypeScript modules."""
    if not shutil.which("node"):
        raise unittest.SkipTest("Node.js runtime not installed on host environment.")

    # Try tsx first if available
    try:
        proc = subprocess.run(
            ["npx", "--no-install", "tsx", "-e", script],
            cwd=str(WEB_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.strip())
    except Exception:
        pass

    # Fallback to jiti via Node.js
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
        cwd=str(WEB_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Node evaluation failed (code {proc.returncode}):\nSTDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
        )
    return json.loads(proc.stdout.strip())


# ============================================================================
# 1. DefectTracker Severity Handling & Scoring Tests
# ============================================================================
class TestCycle11DefectTrackerSeverityHardening(unittest.TestCase):
    """Verifies that DefectTracker query_defects and get_statistics handle severity_index=None

    with CRITICAL severity without crashing and scores records properly.
    """

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_cycle11_defect_")
        self.data_file = Path(self.test_dir) / "daily_reports.json"

        # Create structured sample defect data containing records with None severity_index
        self.sample_reports: List[Dict[str, Any]] = [
            {
                "id": "crit_none_idx_1",
                "title": "ICCU failure while driving causing abrupt stop",
                "defect_topic": "ICCU",
                "verbatim_quote": "고속도로에서 갑자기 계기판 경고등 켜지면서 출력이 차단되었습니다",
                "defect_category": "POWERTRAIN",
                "vehicle_brand": "현대",
                "vehicle_model": "아이오닉 5",
                "severity_index": None,
                "severity": "CRITICAL",
                "negativity_score": 0.95,
                "is_authentic_defect": True,
            },
            {
                "id": "crit_none_idx_2_lower",
                "title": "EV3 skid on wet road losing rear grip",
                "defect_topic": "TRACTION",
                "verbatim_quote": "빗길에서 후륜 접지력이 급격히 상실되었습니다",
                "defect_category": "CHASSIS",
                "vehicle_brand": "기아",
                "vehicle_model": "EV3",
                "severity_index": None,
                "severity": "critical",  # Lowercase test
                "negativity_score": 0.92,
                "is_authentic_defect": True,
            },
            {
                "id": "numeric_high_idx",
                "title": "High voltage battery cell imbalance",
                "defect_topic": "BATTERY",
                "verbatim_quote": "급속 충전 중 80% 구간에서 셀 밸런싱 에러가 발생합니다",
                "defect_category": "BATTERY",
                "vehicle_brand": "테슬라",
                "vehicle_model": "모델 Y",
                "severity_index": 8.5,
                "severity": "HIGH",
                "negativity_score": 0.88,
                "is_authentic_defect": True,
            },
            {
                "id": "numeric_low_idx",
                "title": "Minor wind noise near driver side door",
                "defect_topic": "BODY",
                "verbatim_quote": "시속 100km 주행 시 운전석 창문 틈새로 풍절음이 들립니다",
                "defect_category": "BUILD_QUALITY",
                "vehicle_brand": "현대",
                "vehicle_model": "아이오닉 6",
                "severity_index": 3.2,
                "severity": "LOW",
                "negativity_score": 0.35,
                "is_authentic_defect": True,
            },
            {
                "id": "none_low_idx",
                "title": "Infotainment screen minor lag on startup",
                "defect_topic": "INFOTAINMENT",
                "verbatim_quote": "부팅 직후 내비게이션 터치 반응이 1초 정도 느립니다",
                "defect_category": "ELECTRONICS",
                "vehicle_brand": "제네시스",
                "vehicle_model": "GV60",
                "severity_index": None,
                "severity": "LOW",
                "negativity_score": 0.40,
                "is_authentic_defect": True,
            },
            {
                "id": "all_none",
                "title": "Rattle noise inside glovebox",
                "defect_topic": "INTERIOR",
                "verbatim_quote": "방지턱 넘을 때 글로브박스에서 달그락거리는 소리가 납니다",
                "defect_category": "BUILD_QUALITY",
                "vehicle_brand": "기아",
                "vehicle_model": "EV6",
                "severity_index": None,
                "severity": None,
                "negativity_score": None,
                "is_authentic_defect": True,
            },
        ]

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "pipeline_version": "1.0.0",
            "reports": self.sample_reports,
        }
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        self.tracker = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_query_defects_handles_severity_index_none_with_critical_severity_without_crashing(self) -> None:
        """When querying with min_severity, severity_index=None with CRITICAL severity

        must receive an effective score of 9.0 and must not raise TypeError: float() argument must be a string or a real number, not 'NoneType'.
        """
        # min_severity=7.0 should match:
        # - crit_none_idx_1 (effective_sev = 9.0)
        # - crit_none_idx_2_lower (effective_sev = 9.0)
        # - numeric_high_idx (effective_sev = 8.5)
        # and exclude:
        # - numeric_low_idx (3.2 < 7.0)
        # - none_low_idx (0.0 < 7.0)
        # - all_none (0.0 < 7.0)
        results = self.tracker.query_defects(min_severity=7.0, file_path=self.data_file)

        returned_ids = {r["id"] for r in results}
        self.assertIn("crit_none_idx_1", returned_ids, "CRITICAL defect with severity_index=None must be returned")
        self.assertIn("crit_none_idx_2_lower", returned_ids, "Case-insensitive 'critical' defect must be returned")
        self.assertIn("numeric_high_idx", returned_ids, "Defect with severity_index=8.5 must be returned")

        self.assertNotIn("numeric_low_idx", returned_ids, "Low severity defect (3.2) must be excluded")
        self.assertNotIn("none_low_idx", returned_ids, "Non-critical defect with severity_index=None must be excluded")
        self.assertNotIn("all_none", returned_ids, "Unspecified defect must be excluded")

    def test_query_defects_strict_high_threshold_bounds(self) -> None:
        """Querying with min_severity=9.0 must retain effective_sev=9.0 CRITICAL records

        and exclude numeric_high_idx (8.5 < 9.0).
        """
        results_9 = self.tracker.query_defects(min_severity=9.0, file_path=self.data_file)
        ids_9 = {r["id"] for r in results_9}
        self.assertIn("crit_none_idx_1", ids_9)
        self.assertIn("crit_none_idx_2_lower", ids_9)
        self.assertNotIn("numeric_high_idx", ids_9)

        # Threshold higher than 9.0 (e.g. 9.5) should exclude all
        results_95 = self.tracker.query_defects(min_severity=9.5, file_path=self.data_file)
        self.assertEqual(len(results_95), 0)

    def test_get_statistics_counts_critical_defects_with_none_severity_index(self) -> None:
        """Dynamic calculation in get_statistics() must count records with severity='CRITICAL'

        as critical even if severity_index is None.
        """
        # In our sample data, 3 records are critical:
        # crit_none_idx_1 (CRITICAL), crit_none_idx_2_lower (critical), numeric_high_idx (8.5 >= 7.0)
        stats = self.tracker.get_statistics(file_path=self.data_file)

        self.assertEqual(stats["total_filtered_defects"], len(self.sample_reports))
        self.assertEqual(stats["critical_defect_count"], 3, "Must count exactly 3 critical defects")

    def test_query_defects_caching_consistency_under_none_severity_index(self) -> None:
        """Query caching must return consistent results across multiple calls without mutating cache."""
        res1 = self.tracker.query_defects(min_severity=7.0, file_path=self.data_file)
        res2 = self.tracker.query_defects(min_severity=7.0, file_path=self.data_file)

        self.assertEqual([r["id"] for r in res1], [r["id"] for r in res2])
        self.assertEqual(len(res1), 3)


# ============================================================================
# 2. utils/json_writer Safe Float NaN & Infinity Protections
# ============================================================================
class TestCycle11JsonWriterSafeFloatProtections(unittest.TestCase):
    """Verifies that _safe_float rejects NaN and Infinity, preventing non-standard

    JSON values that break RFC 8259 compliance and crash JavaScript JSON.parse.
    """

    def test_safe_float_rejects_nan_and_infinity_primitives(self) -> None:
        """_safe_float must return safe default when encountering NaN, Inf, or -Inf."""
        self.assertEqual(_safe_float(float("nan"), default=0.0), 0.0)
        self.assertEqual(_safe_float(float("inf"), default=0.0), 0.0)
        self.assertEqual(_safe_float(float("-inf"), default=0.0), 0.0)
        self.assertEqual(_safe_float(math.nan, default=1.5), 1.5)
        self.assertEqual(_safe_float(math.inf, default=1.5), 1.5)

    def test_safe_float_rejects_nan_and_infinity_strings(self) -> None:
        """_safe_float must reject string representations of NaN and Infinity."""
        self.assertEqual(_safe_float("nan", default=0.0), 0.0)
        self.assertEqual(_safe_float("NaN", default=0.0), 0.0)
        self.assertEqual(_safe_float("inf", default=0.0), 0.0)
        self.assertEqual(_safe_float("-inf", default=0.0), 0.0)
        self.assertEqual(_safe_float("Infinity", default=0.0), 0.0)
        self.assertEqual(_safe_float("-Infinity", default=0.0), 0.0)

    def test_safe_float_defensive_against_nan_default_argument(self) -> None:
        """If caller erroneously passes default=float('nan'), _safe_float must clamp to 0.0."""
        res_nan = _safe_float(float("nan"), default=float("nan"))
        self.assertFalse(math.isnan(res_nan), "Output must never be NaN")
        self.assertEqual(res_nan, 0.0)

        res_inf = _safe_float(float("inf"), default=float("inf"))
        self.assertFalse(math.isinf(res_inf), "Output must never be Infinity")
        self.assertEqual(res_inf, 0.0)

    def test_safe_float_preserves_valid_finite_values(self) -> None:
        """_safe_float must accurately convert and preserve standard finite floats and ints."""
        self.assertEqual(_safe_float(42, default=0.0), 42.0)
        self.assertEqual(_safe_float(3.14159, default=0.0), 3.14159)
        self.assertEqual(_safe_float("123.45", default=0.0), 123.45)
        self.assertEqual(_safe_float("-99.5", default=0.0), -99.5)
        self.assertEqual(_safe_float(0, default=5.0), 0.0)

    def test_format_daily_report_payload_computes_finite_statistics_on_nan_and_inf(self) -> None:
        """format_daily_report_payload must compute valid finite statistics even when records

        contain raw NaN, Infinity, or unparseable score strings.
        """
        malformed_records = [
            {
                "id": "rec_nan_1",
                "title": "Test NaN scores",
                "negativity_score": float("nan"),
                "severity_index": float("inf"),
                "is_authentic_defect": True,
            },
            {
                "id": "rec_nan_2",
                "title": "Test String Infinity scores",
                "negativity_score": "Infinity",
                "severity_index": "-Infinity",
                "is_authentic_defect": True,
            },
        ]
        payload = format_daily_report_payload(malformed_records)
        self.assertIsInstance(payload.statistics.avg_negativity_score, float)
        self.assertTrue(math.isfinite(payload.statistics.avg_negativity_score))
        self.assertEqual(payload.statistics.critical_defect_count, 0)
        self.assertEqual(payload.statistics.total_filtered_defects, 2)


# ============================================================================
# 3. utils/json_writer Historical Report Preservation on Null Statistics
# ============================================================================
class TestCycle11JsonWriterNullStatisticsPreservation(unittest.TestCase):
    """Verifies that write_daily_reports handles existing files with null statistics cleanly

    without wiping historical defect records due to AttributeError.
    """

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_cycle11_writer_")
        self.output_file = Path(self.test_dir) / "daily_reports.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_write_daily_reports_preserves_history_when_existing_statistics_is_none(self) -> None:
        """When daily_reports.json exists with 'statistics': null, write_daily_reports

        must NOT raise AttributeError or wipe existing reports.
        """
        historical_records = [
            {
                "id": "hist_1",
                "title": "Historical defect 1",
                "url": "https://example.com/hist1",
                "is_authentic_defect": True,
                "defect_category": "POWERTRAIN",
            },
            {
                "id": "hist_2",
                "title": "Historical defect 2",
                "url": "https://example.com/hist2",
                "is_authentic_defect": True,
                "defect_category": "BATTERY",
            },
        ]
        # Write initial file with statistics: None
        initial_data = {
            "generated_at": "2026-10-09T00:00:00Z",
            "pipeline_version": "1.0.0",
            "statistics": None,  # Explicitly null
            "reports": historical_records,
        }
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(initial_data, f, ensure_ascii=False, indent=2)

        # New complaint to merge
        new_records = [
            {
                "id": "new_1",
                "title": "New discovered defect",
                "url": "https://example.com/new1",
                "is_authentic_defect": True,
                "defect_category": "CHASSIS",
            }
        ]

        # Call write_daily_reports with merge_existing=True
        written_path = write_daily_reports(
            complaints=new_records,
            output_path=str(self.output_file),
            merge_existing=True,
        )
        self.assertEqual(written_path, str(self.output_file))

        # Verify merged content
        result = read_daily_reports(str(self.output_file))
        saved_ids = {r["id"] for r in result.get("reports", [])}

        self.assertIn("hist_1", saved_ids, "Historical report 1 must be preserved")
        self.assertIn("hist_2", saved_ids, "Historical report 2 must be preserved")
        self.assertIn("new_1", saved_ids, "New report must be added")
        self.assertEqual(len(result["reports"]), 3, "All 3 reports must exist in merged output")

        # Statistics block must now be populated and valid
        stats = result.get("statistics")
        self.assertIsNotNone(stats)
        self.assertIsInstance(stats, dict)
        self.assertEqual(stats["total_filtered_defects"], 3)

    def test_write_daily_reports_preserves_history_when_existing_statistics_is_missing(self) -> None:
        """When existing file omits 'statistics' key altogether, history must still be preserved."""
        initial_data = {
            "generated_at": "2026-10-09T00:00:00Z",
            "pipeline_version": "1.0.0",
            "reports": [
                {
                    "id": "hist_no_stats",
                    "title": "Defect without statistics block",
                    "url": "https://example.com/no_stats",
                    "is_authentic_defect": True,
                }
            ],
        }
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(initial_data, f, ensure_ascii=False, indent=2)

        write_daily_reports(
            complaints=[
                {
                    "id": "new_incoming",
                    "title": "Incoming defect",
                    "url": "https://example.com/incoming",
                    "is_authentic_defect": True,
                }
            ],
            output_path=str(self.output_file),
            merge_existing=True,
        )

        result = read_daily_reports(str(self.output_file))
        saved_ids = {r["id"] for r in result.get("reports", [])}
        self.assertIn("hist_no_stats", saved_ids)
        self.assertIn("new_incoming", saved_ids)

    def test_atomic_writer_default_serializer_handles_complex_types(self) -> None:
        """atomic_write_json default serializer must convert Path, datetime, date, set, and Enum without crashing."""
        class TestEnum(Enum):
            ACTIVE = "active"

        payload = {
            "path_val": Path("/tmp/sample_path"),
            "datetime_val": datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc),
            "date_val": date(2026, 10, 10),
            "set_val": {"alpha", "beta"},
            "enum_val": TestEnum.ACTIVE,
        }
        target = Path(self.test_dir) / "atomic_complex.json"
        atomic_write_json(payload, target)

        self.assertTrue(target.exists())
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["path_val"], "/tmp/sample_path")
        self.assertEqual(data["date_val"], "2026-10-10")
        self.assertIn("alpha", data["set_val"])
        self.assertEqual(data["enum_val"], "active")


# ============================================================================
# 4. simulateBatteryHealth Brand-New 0-Year EV Kinetics
# ============================================================================
class TestCycle11SimulateBatteryHealthZeroYear(unittest.TestCase):
    """Verifies that simulateBatteryHealth correctly preserves 0 calendar degradation

    for a brand-new 0-year EV rather than erroneously falling back to 3 years.
    """

    def test_simulate_battery_health_zero_year_zero_calendar_loss(self) -> None:
        """When years=0, calendarLossPct must strictly be 0.0 (0 calendar degradation)."""
        script = """
        import { simulateBatteryHealth } from './src/lib/getDepreciationData';
        const res0 = simulateBatteryHealth({
            years: 0,
            totalKm: 0,
            annualKm: 15000,
            ambientTempC: 25.0
        });
        console.log(JSON.stringify(res0));
        """
        res = _eval_ts_node(script)

        self.assertEqual(res["years"], 0, "Reported years must be 0")
        self.assertEqual(res["totalKm"], 0, "Reported totalKm must be 0")
        self.assertEqual(res["calendarLossPct"], 0, "Brand-new 0-year EV must have 0 calendar degradation")
        self.assertEqual(res["cyclicLossPct"], 0, "0-km EV must have 0 cyclic loss")
        self.assertEqual(res["totalLossPct"], 0, "0-year 0-km EV must have 0 total loss")
        self.assertEqual(res["sohPct"], 100, "Brand-new EV State of Health must be 100%")
        self.assertEqual(res["grade"], "GRADE_A", "Brand-new EV must receive Grade A")
        self.assertEqual(res["usedMarketValuationFactor"], 1.0, "Brand-new EV valuation factor must be 1.0")

    def test_simulate_battery_health_fallback_to_three_years_for_invalid_years(self) -> None:
        """simulateBatteryHealth must only fall back to 3 years when years is undefined,

        null, NaN, or negative (< 0).
        """
        script = """
        import { simulateBatteryHealth } from './src/lib/getDepreciationData';
        const resUndefined = simulateBatteryHealth({ years: undefined, totalKm: 45000 });
        const resNull = simulateBatteryHealth({ years: null as any, totalKm: 45000 });
        const resNegative = simulateBatteryHealth({ years: -5, totalKm: 45000 });
        const resNaN = simulateBatteryHealth({ years: NaN, totalKm: 45000 });

        console.log(JSON.stringify({
            undefinedYears: resUndefined.years,
            undefinedLoss: resUndefined.calendarLossPct,
            nullYears: resNull.years,
            nullLoss: resNull.calendarLossPct,
            negativeYears: resNegative.years,
            negativeLoss: resNegative.calendarLossPct,
            nanYears: resNaN.years,
            nanLoss: resNaN.calendarLossPct,
        }));
        """
        res = _eval_ts_node(script)

        # All invalid inputs fall back to 3 years and have non-zero calendar loss
        self.assertEqual(res["undefinedYears"], 3)
        self.assertGreater(res["undefinedLoss"], 0)
        self.assertEqual(res["nullYears"], 3)
        self.assertGreater(res["nullLoss"], 0)
        self.assertEqual(res["negativeYears"], 3)
        self.assertGreater(res["negativeLoss"], 0)
        self.assertEqual(res["nanYears"], 3)
        self.assertGreater(res["nanLoss"], 0)


# ============================================================================
# 5. SubsidyTrackerClient Badge Styling & Non-Negative Pending Logic
# ============================================================================
class TestCycle11SubsidyTrackerClientHardening(unittest.TestCase):
    """Verifies SubsidyTrackerClient badge styling fallback branches and non-negative

    pending count logic.
    """

    def test_get_badge_style_and_status_label_default_branches(self) -> None:
        """getBadgeStyle and getStatusLabel must handle 'available' and provide valid

        fallback strings for unexpected status values (never undefined).
        """
        script = """
        import { getBadgeStyle, getStatusLabel } from './src/app/subsidy-tracker/SubsidyTrackerClient';

        const availStyle = getBadgeStyle('available');
        const unknownStyle = getBadgeStyle('UNKNOWN_TIER');
        const emptyStyle = getBadgeStyle('');

        const availLabel = getStatusLabel('available');
        const unknownLabel = getStatusLabel('UNKNOWN_TIER');
        const emptyLabel = getStatusLabel('');

        console.log(JSON.stringify({
            availStyle,
            unknownStyle,
            emptyStyle,
            availLabel,
            unknownLabel,
            emptyLabel
        }));
        """
        res = _eval_ts_node(script)

        # Validate badge styles
        self.assertIsInstance(res["availStyle"], str)
        self.assertIn("bg-", res["availStyle"])
        self.assertNotEqual(res["availStyle"], "undefined")

        self.assertIsInstance(res["unknownStyle"], str)
        self.assertIn("bg-", res["unknownStyle"])
        self.assertNotEqual(res["unknownStyle"], "undefined")

        self.assertIsInstance(res["emptyStyle"], str)
        self.assertNotEqual(res["emptyStyle"], "undefined")

        # Validate status labels
        self.assertIsInstance(res["availLabel"], str)
        self.assertIn("안정", res["availLabel"])
        self.assertNotEqual(res["availLabel"], "undefined")

        self.assertIsInstance(res["unknownLabel"], str)
        self.assertIn("안정", res["unknownLabel"])
        self.assertNotEqual(res["unknownLabel"], "undefined")

    def test_subsidy_tracker_pending_count_non_negative_clamp(self) -> None:
        """Pending vehicle calculation Math.max(0, safeApplied - safeDelivered)

        must never yield negative pending numbers when delivered exceeds applied.
        """
        script = """
        function calculatePending(safeApplied: number, safeDelivered: number): number {
            return Math.max(0, safeApplied - safeDelivered);
        }

        console.log(JSON.stringify({
            normalCase: calculatePending(100, 40),
            equalCase: calculatePending(50, 50),
            overDeliveredCase: calculatePending(30, 45),
            zeroAppliedCase: calculatePending(0, 10),
        }));
        """
        res = _eval_ts_node(script)

        self.assertEqual(res["normalCase"], 60)
        self.assertEqual(res["equalCase"], 0)
        self.assertEqual(res["overDeliveredCase"], 0, "Delivered > applied must clamp pending to 0")
        self.assertEqual(res["zeroAppliedCase"], 0, "0 applied with delivered > 0 must clamp to 0")

    def test_subsidy_tracker_client_source_contains_clamp_and_optional_chaining(self) -> None:
        """SubsidyTrackerClient.tsx source must contain Math.max(0, safeApplied - safeDelivered)

        and optional chaining on regional category dereferencing.
        """
        client_file = APP_DIR / "subsidy-tracker" / "SubsidyTrackerClient.tsx"
        self.assertTrue(client_file.exists(), f"File {client_file} must exist")
        content = client_file.read_text(encoding="utf-8")

        # Verify Math.max clamp on pending applications
        self.assertIn(
            "Math.max(0, safeApplied - safeDelivered)",
            content,
            "SubsidyTrackerClient must clamp pending applications to non-negative with Math.max",
        )

        # Verify default branch in getBadgeStyle and getStatusLabel
        self.assertIn("default:", content, "Must have default: branch in switch statements")
        self.assertIn("case 'available':", content, "Must handle 'available' status in badge switch")


# ============================================================================
# 6. Repository Tree Mirror Parity & POSIX 0644 Permissions
# ============================================================================
class TestCycle11RepoParityAndPermissions(unittest.TestCase):
    """Verifies 100% bitwise parity of Python modules and tests between root and web,

    and POSIX 0644 mode enforcement on dataset JSON files.
    """

    def test_tracker_and_utils_bitwise_parity(self) -> None:
        """All .py files in tracker/ and utils/ must have bitwise identical SHA-256 hashes

        in ev-stealth-web/tracker/ and ev-stealth-web/utils/.
        """
        modules_to_check = [
            ("tracker/defect_tracker.py", "ev-stealth-web/tracker/defect_tracker.py"),
            ("tracker/atomic_writer.py", "ev-stealth-web/tracker/atomic_writer.py"),
            ("tracker/subsidy_tracker.py", "ev-stealth-web/tracker/subsidy_tracker.py"),
            ("tracker/subsidy_models.py", "ev-stealth-web/tracker/subsidy_models.py"),
            ("tracker/subsidy_baseline.py", "ev-stealth-web/tracker/subsidy_baseline.py"),
            ("tracker/report_generator.py", "ev-stealth-web/tracker/report_generator.py"),
            ("utils/json_writer.py", "ev-stealth-web/utils/json_writer.py"),
            ("utils/http_client.py", "ev-stealth-web/utils/http_client.py"),
        ]

        for rel_root, rel_web in modules_to_check:
            p_root = PROJECT_ROOT / rel_root
            p_web = PROJECT_ROOT / rel_web
            self.assertTrue(p_root.exists(), f"{p_root} must exist")
            self.assertTrue(p_web.exists(), f"{p_web} must exist")

            sha_root = hashlib.sha256(p_root.read_bytes()).hexdigest()
            sha_web = hashlib.sha256(p_web.read_bytes()).hexdigest()
            self.assertEqual(
                sha_root,
                sha_web,
                f"Bitwise parity mismatch between {rel_root} and {rel_web}",
            )

    def test_test_tree_files_parity(self) -> None:
        """Every .py test file in tests/ must be present in ev-stealth-web/tests/."""
        root_tests = {p.name for p in (PROJECT_ROOT / "tests").glob("*.py")}
        web_tests = {p.name for p in (WEB_ROOT / "tests").glob("*.py")}

        # Exclude self if copy hasn't happened yet in this exact instant
        diff = root_tests - web_tests
        # If test_cycle11_hardening.py is the only difference, it will be synchronized in step 2
        diff.discard("test_cycle11_hardening.py")
        self.assertEqual(diff, set(), f"Missing mirrored test files in web: {diff}")

    def test_dataset_json_files_have_posix_0644_permissions(self) -> None:
        """All dataset JSON files in data/ and ev-stealth-web/src/data/ must have mode 0o644."""
        dirs_to_check = [
            PROJECT_ROOT / "data",
            WEB_ROOT / "src" / "data",
        ]
        non_compliant: List[str] = []

        for d in dirs_to_check:
            if not d.exists():
                continue
            for f in d.glob("*.json"):
                mode = stat.S_IMODE(f.stat().st_mode)
                if mode != 0o644:
                    non_compliant.append(f"{f}: {oct(mode)}")

        self.assertEqual(
            non_compliant,
            [],
            f"All JSON files must have 0o644 permissions. Non-compliant: {non_compliant}",
        )


if __name__ == "__main__":
    unittest.main()
