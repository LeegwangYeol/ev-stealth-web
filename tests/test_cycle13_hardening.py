"""
tests/test_cycle13_hardening.py - Comprehensive Cycle 13 Hardening, Defensive Boundary,
Accessibility, Performance, and Mirror Parity Test Suite.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (Cycle 13 Wave 2 Test Suite Specification)
- Wave 1 Explorer Handoff Reports:
  - sync13_explorer_backend_w1/handoff.md
  - sync13_explorer_frontend_w1/handoff.md
  - sync13_explorer_a11y_w1/handoff.md
  - sync13_explorer_perf_w1/handoff.md
  - sync13_explorer_parity_w1/handoff.md
- COLLABORATION.md

Coverage:
1. Backend Hardening:
   - ReportGenerator.generate_defect_briefing None safety & NaN/Inf handling.
   - ReportGenerator.generate_subsidy_briefing None string formatting safety.
   - DefectTracker.query_defects limit <= 0 early return [].
   - DefectTracker cache lock thread safety and normalized cache keys.
   - DefectTracker summary field keyword search recall.
   - atomic_writer & json_writer recursive float NaN / Infinity sanitation to 0.0 (RFC 8259).
   - utils/json_writer.write_daily_reports non-dict merge safety.
   - subsidy_baseline calculate_price_cap_ratio and calculate_net_subsidy None/invalid safety.
   - utils/http_client encode_euc_kr_query None and non-string guard.

2. Frontend Logic & Boundary Hardening:
   - simulateBatteryHealth out-of-bounds battery replacement costs fallback.
   - calculateKPIs zero-filtered records non-synthetic fallback ('해당 없음 (0건)', 0.0, 0%).
   - isYearMatchForCampaign comma/semicolon-delimited disjoint year segments parsing.

3. Accessibility & Performance Invariants:
   - Heading monotonicity across all 12 App Router pages (no skipped heading levels).
   - Layout font preloading (preload: false on geistMono) and force-static declarations.
   - WCAG 2.1 AA landmark regions, aria-describedby warning linkages, and accessible table text.

4. Repository Parity:
   - 100% bitwise parity between root tests/ and ev-stealth-web/tests/ with 0o644 permissions.
   - 100% triple mirror parity across data/ JSON datasets.
"""

from __future__ import annotations

import concurrent.futures
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Union

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

from tracker.atomic_writer import atomic_write_json, sanitize_nan_inf
from tracker.defect_tracker import DefectTracker
from tracker.report_generator import ReportGenerator, _metric_val
from tracker.subsidy_baseline import (
    build_initial_baseline,
    calculate_price_cap_ratio,
    calculate_net_subsidy,
)
from utils.http_client import encode_euc_kr_query
from utils.json_writer import (
    _safe_float,
    format_daily_report_payload,
    read_daily_reports,
    write_daily_reports,
)


def _eval_ts_node(script: str, timeout_sec: int = 30) -> Any:
    """Execute a Node.js snippet using tsx or jiti to resolve TypeScript modules."""
    if not shutil.which("node"):
        raise unittest.SkipTest("Node.js runtime not installed on host environment.")

    # Try tsx first
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
        raise unittest.SkipTest(f"tsx and jiti not found at {jiti_path}")

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
# 1. Backend ReportGenerator Hardening Tests
# ============================================================================
class TestCycle13ReportGeneratorHardening(unittest.TestCase):
    """Verifies ReportGenerator defensive handling against None values,
    unsupported string formatting, and NaN/Infinity numeric tokens.
    """

    def setUp(self) -> None:
        self.generator = ReportGenerator()

    def test_generate_defect_briefing_none_and_invalid_severity_safety(self) -> None:
        """generate_defect_briefing must not crash when severity_index or defect fields are None, NaN, or Inf."""
        # 1. Record with explicit None values across all optional/computed fields
        reports_with_none = [
            {
                "id": "defect_none_1",
                "title": "ICCU 동력상실 경고등",
                "defect_topic": None,
                "summary": "고속도로 주행 중 전원 차단",
                "defect_category": None,
                "vehicle_brand": "현대",
                "vehicle_model": "아이오닉 5",
                "severity_index": None,
                "severity": "CRITICAL",
                "is_authentic_defect": True,
            },
            {
                "id": "defect_nan_2",
                "title": "배터리 충전 지연",
                "defect_topic": "충전",
                "defect_category": "BATTERY",
                "vehicle_brand": "기아",
                "vehicle_model": "EV6",
                "severity_index": float("nan"),
                "severity": "HIGH",
                "is_authentic_defect": True,
            },
            {
                "id": "defect_inf_3",
                "title": "OTA 업데이트 화면 먹통",
                "defect_topic": "OTA",
                "defect_category": "ELECTRONICS",
                "vehicle_brand": "테슬라",
                "vehicle_model": "모델 Y",
                "severity_index": float("inf"),
                "severity": "LOW",
                "is_authentic_defect": True,
            },
        ]

        payload = {
            "reports": reports_with_none,
            "statistics": {
                "critical_defect_count": None,
                "avg_negativity_score": None,
            },
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Must execute cleanly without TypeError: '>=' not supported between 'NoneType' and 'float'
        briefing = self.generator.generate_defect_briefing(payload)
        self.assertIsInstance(briefing, str)
        self.assertIn("대한민국 EV 실생활 결함 및 커뮤니티 동향 일일 브리핑", briefing)
        self.assertIn("UNKNOWN", briefing)  # None defect_category grouped cleanly as UNKNOWN
        self.assertIn("총 수집/분류 결함 건수", briefing)

        # 2. Test empty reports handling
        empty_briefing = self.generator.generate_defect_briefing({"reports": []})
        self.assertIn("수집된 결함 내역이 없습니다.", empty_briefing)
        self.assertIn("현재 긴급 심각도(DSI >= 7.0) 결함 사례 없음.", empty_briefing)

    def test_generate_subsidy_briefing_none_string_formatting_safety(self) -> None:
        """generate_subsidy_briefing must not crash when remaining_units or announced_units is None."""
        payload = build_initial_baseline()
        self.assertGreater(len(payload.regions), 0)

        # Corrupt the first region's passenger category remaining_units and announced_units to None
        target_region = payload.regions[0]
        target_region.overall_status = "CRITICAL"
        if "passenger" in target_region.categories:
            target_region.categories["passenger"].remaining_units = None
            target_region.categories["passenger"].announced_units = None
            target_region.categories["passenger"].applied_units = None

        # Corrupt the second region: categories is None
        if len(payload.regions) > 1:
            payload.regions[1].overall_status = "DEPLETED"
            payload.regions[1].categories = None  # type: ignore[assignment]

        # Must execute cleanly without TypeError: unsupported format string passed to NoneType.__format__
        briefing = self.generator.generate_subsidy_briefing(payload)
        self.assertIsInstance(briefing, str)
        self.assertIn("전국 전기차 보조금 소진 현황 일일 종합 브리핑", briefing)
        self.assertIn("잔여: 0대", briefing)  # Safe integer 0 fallback with comma formatting

    def test_metric_val_helper_robustness(self) -> None:
        """_metric_val helper must handle None objects, missing keys, and None values safely."""
        self.assertEqual(_metric_val(None, "remaining_units", 0), 0)
        self.assertEqual(_metric_val({}, "remaining_units", 0), 0)
        self.assertEqual(_metric_val({"remaining_units": None}, "remaining_units", 0), 0)
        self.assertEqual(_metric_val({"remaining_units": 42}, "remaining_units", 0), 42)


# ============================================================================
# 2. Backend DefectTracker Hardening Tests
# ============================================================================
class TestCycle13DefectTrackerHardening(unittest.TestCase):
    """Verifies DefectTracker fixes: limit <= 0 early return, summary keyword search,
    and thread-safe normalized cache locking.
    """

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_cycle13_defect_")
        self.data_file = Path(self.test_dir) / "daily_reports.json"

        self.sample_data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "reports": [
                {
                    "id": "def_sum_only",
                    "title": "주행 중 이상 진동 발생",
                    "defect_topic": "진동",
                    "summary": "특수고전압배터리셀불량인버터경고등발생",
                    "verbatim_quote": "차가 덜덜 떨립니다",
                    "raw_quote": "진동이 심해요",
                    "defect_category": "POWERTRAIN",
                    "vehicle_brand": "현대",
                    "vehicle_model": "아이오닉 5",
                    "severity": "CRITICAL",
                    "severity_index": 8.5,
                    "is_authentic_defect": True,
                },
                {
                    "id": "def_title_match",
                    "title": "ICCU 전원 차단 결함",
                    "defect_topic": "ICCU",
                    "summary": "주행 불가 상태",
                    "verbatim_quote": "속도가 줄어듭니다",
                    "raw_quote": "위험했습니다",
                    "defect_category": "POWERTRAIN",
                    "vehicle_brand": "기아",
                    "vehicle_model": "EV6",
                    "severity": "HIGH",
                    "severity_index": 7.0,
                    "is_authentic_defect": True,
                },
                {
                    "id": "def_low_severity",
                    "title": "도어 트림 단차",
                    "defect_topic": "단차",
                    "summary": "도어와 펜더 사이 간격 불일치",
                    "verbatim_quote": "단차가 좀 있네요",
                    "raw_quote": "마감 아쉬움",
                    "defect_category": "BUILD_QUALITY",
                    "vehicle_brand": "테슬라",
                    "vehicle_model": "모델 Y",
                    "severity": "LOW",
                    "severity_index": 2.0,
                    "is_authentic_defect": True,
                },
            ],
        }

        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.sample_data, f, ensure_ascii=False, indent=2)

        self.tracker = DefectTracker(root_data_dir=self.test_dir, web_data_dir=self.test_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_query_defects_limit_zero_and_negative(self) -> None:
        """query_defects with limit <= 0 must return an empty list [], not 1 record."""
        # limit = 0
        res_zero = self.tracker.query_defects(limit=0, file_path=self.data_file)
        self.assertEqual(res_zero, [], "limit=0 must return empty list []")

        # limit = -1
        res_neg = self.tracker.query_defects(limit=-1, file_path=self.data_file)
        self.assertEqual(res_neg, [], "limit=-1 must return empty list []")

        # string limit="0"
        res_str_zero = self.tracker.query_defects(limit="0", file_path=self.data_file)  # type: ignore[arg-type]
        self.assertEqual(res_str_zero, [], "limit='0' must return empty list []")

        # string limit="-5"
        res_str_neg = self.tracker.query_defects(limit="-5", file_path=self.data_file)  # type: ignore[arg-type]
        self.assertEqual(res_str_neg, [], "limit='-5' must return empty list []")

        # limit = 1 must return exactly 1 item
        res_one = self.tracker.query_defects(limit=1, file_path=self.data_file)
        self.assertEqual(len(res_one), 1)

        # limit = None must return all items
        res_all = self.tracker.query_defects(limit=None, file_path=self.data_file)
        self.assertEqual(len(res_all), 3)

    def test_query_defects_summary_keyword_search(self) -> None:
        """query_defects must match keywords present strictly in the summary field."""
        # Keyword present ONLY in summary
        kw = "특수고전압배터리셀불량인버터경고등발생"
        res = self.tracker.query_defects(keyword=kw, file_path=self.data_file)
        self.assertEqual(len(res), 1, "Keyword present strictly in summary must be matched")
        self.assertEqual(res[0]["id"], "def_sum_only")

        # Case-insensitive substring match
        res_sub = self.tracker.query_defects(keyword="인버터경고등", file_path=self.data_file)
        self.assertEqual(len(res_sub), 1)
        self.assertEqual(res_sub[0]["id"], "def_sum_only")

        # Non-matching keyword
        res_none = self.tracker.query_defects(keyword="존재하지않는결함키워드", file_path=self.data_file)
        self.assertEqual(res_none, [])

    def test_query_defects_cache_locking_and_normalization_under_concurrency(self) -> None:
        """Cache key computation must be thread-safe under concurrency and normalize min_severity."""
        # Query with float 8.0 vs string "8.0" should hit same normalized query cache
        res_float = self.tracker.query_defects(min_severity=8.0, file_path=self.data_file)
        res_str = self.tracker.query_defects(min_severity="8.0", file_path=self.data_file)
        self.assertEqual(len(res_float), len(res_str))
        self.assertEqual(res_float, res_str)

        # Concurrency stress test across 10 threads
        def worker(idx: int) -> int:
            if idx % 3 == 0:
                return len(self.tracker.query_defects(limit=0, file_path=self.data_file))
            elif idx % 3 == 1:
                return len(self.tracker.query_defects(min_severity=7.0, file_path=self.data_file))
            else:
                return len(self.tracker.load_reports(file_path=self.data_file))

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker, i) for i in range(24)]
            results = [f.result() for f in futures]

        self.assertEqual(len(results), 24)
        for i, val in enumerate(results):
            if i % 3 == 0:
                self.assertEqual(val, 0)
            elif i % 3 == 1:
                self.assertEqual(val, 2)
            else:
                self.assertEqual(val, 3)


# ============================================================================
# 3. Backend Serialization, Baseline, & HTTP Client Hardening Tests
# ============================================================================
class TestCycle13SerializationBaselineAndHttpHardening(unittest.TestCase):
    """Verifies atomic_writer and json_writer NaN/Inf sanitization, non-dict merge safety,
    subsidy_baseline price cap ratio safety, and http_client EUC-KR encoding guard.
    """

    def setUp(self) -> None:
        self.test_dir = tempfile.mkdtemp(prefix="test_cycle13_serial_")

    def tearDown(self) -> None:
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_atomic_writer_and_json_writer_nan_inf_sanitization(self) -> None:
        """sanitize_nan_inf and atomic_write_json must sanitize float NaN and Inf to 0.0 (RFC 8259)."""
        payload = {
            "nan_val": float("nan"),
            "pos_inf": float("inf"),
            "neg_inf": float("-inf"),
            "nested_dict": {
                "inner_nan": float("nan"),
                "valid_float": 88.5,
            },
            "nested_list": [float("nan"), float("inf"), 42],
            "valid_int": 100,
        }

        # 1. Direct unit verification of sanitize_nan_inf
        sanitized = sanitize_nan_inf(payload)
        self.assertEqual(sanitized["nan_val"], 0.0)
        self.assertEqual(sanitized["pos_inf"], 0.0)
        self.assertEqual(sanitized["neg_inf"], 0.0)
        self.assertEqual(sanitized["nested_dict"]["inner_nan"], 0.0)
        self.assertEqual(sanitized["nested_dict"]["valid_float"], 88.5)
        self.assertEqual(sanitized["nested_list"], [0.0, 0.0, 42])

        # 2. Disk serialization via atomic_write_json with allow_nan=False
        target = Path(self.test_dir) / "test_nan.json"
        atomic_write_json(payload, target)
        self.assertTrue(target.exists())

        raw_text = target.read_text(encoding="utf-8")
        self.assertNotIn("NaN", raw_text)
        self.assertNotIn("Infinity", raw_text)

        loaded = json.loads(raw_text)
        self.assertEqual(loaded["nan_val"], 0.0)
        self.assertEqual(loaded["pos_inf"], 0.0)
        self.assertEqual(loaded["neg_inf"], 0.0)

    def test_write_daily_reports_non_dict_merge_safety(self) -> None:
        """write_daily_reports must gracefully filter out non-dict items in existing reports."""
        target = Path(self.test_dir) / "daily_reports.json"

        # Pre-seed daily_reports.json with corrupted non-dict entries
        corrupted_data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "reports": [
                None,  # Null entry
                "corrupted_string_item",  # String entry
                12345,  # Numeric entry
                {
                    "id": "valid_hist_1",
                    "title": "기존 유효 제보",
                    "url": "https://example.com/hist1",
                    "is_authentic_defect": True,
                },
            ],
            "statistics": {
                "total_scraped": 4,
            },
        }

        with open(target, "w", encoding="utf-8") as f:
            json.dump(corrupted_data, f, ensure_ascii=False)

        new_reports = [
            {
                "id": "new_report_1",
                "title": "신규 결함 제보",
                "url": "https://example.com/new1",
                "is_authentic_defect": True,
            }
        ]

        # Must execute cleanly without AttributeError: 'NoneType' object has no attribute 'get'
        write_daily_reports(new_reports, output_path=target, merge_existing=True)

        res_data = read_daily_reports(target)
        self.assertIsInstance(res_data, dict)
        reports = res_data.get("reports", [])
        self.assertEqual(len(reports), 2)
        report_ids = [r.get("id") for r in reports]
        self.assertIn("valid_hist_1", report_ids)
        self.assertIn("new_report_1", report_ids)

    def test_subsidy_baseline_price_cap_ratio_none_and_invalid_safety(self) -> None:
        """calculate_price_cap_ratio and calculate_net_subsidy in subsidy_baseline must handle None/invalid inputs."""
        # calculate_price_cap_ratio boundary inputs
        self.assertEqual(calculate_price_cap_ratio(None), 0.0)
        self.assertEqual(calculate_price_cap_ratio(float("nan")), 0.0)
        self.assertEqual(calculate_price_cap_ratio(float("inf")), 0.0)
        self.assertEqual(calculate_price_cap_ratio("invalid_msrp"), 0.0)  # type: ignore[arg-type]
        self.assertEqual(calculate_price_cap_ratio(50_000_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(70_000_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(90_000_000), 0.0)

        # calculate_net_subsidy boundary inputs
        res_none = calculate_net_subsidy(None, None, None, None)  # type: ignore[arg-type]
        self.assertIsInstance(res_none, dict)
        self.assertEqual(res_none["national_subsidy_krw"], 0)
        self.assertEqual(res_none["local_subsidy_krw"], 0)
        self.assertEqual(res_none["total_subsidy_krw"], 0)
        self.assertEqual(res_none["net_price_krw"], 0)

        # Partial None inputs with valid model national
        res_partial = calculate_net_subsidy(5_000_000, 6_500_000, 4_000_000, None)  # type: ignore[arg-type]
        self.assertGreaterEqual(res_partial["net_price_krw"], 0)

    def test_http_client_euc_kr_none_and_non_dict_guard(self) -> None:
        """encode_euc_kr_query must safely return empty string for None, non-string, and non-dict inputs."""
        self.assertEqual(encode_euc_kr_query(None), "")
        self.assertEqual(encode_euc_kr_query(""), "")
        self.assertEqual(encode_euc_kr_query(12345), "")  # type: ignore[arg-type]
        self.assertEqual(encode_euc_kr_query(["a", "b"]), "")  # type: ignore[arg-type]

        # Valid string
        encoded_str = encode_euc_kr_query("전기차")
        self.assertTrue(len(encoded_str) > 0)
        self.assertIn("%", encoded_str)

        # Valid dict
        encoded_dict = encode_euc_kr_query({"search": "결함"})
        self.assertTrue(encoded_dict.startswith("search="))


# ============================================================================
# 4. Frontend Logic & Boundary Hardening Tests
# ============================================================================
class TestCycle13FrontendLogicHardening(unittest.TestCase):
    """Verifies Next.js client component logic: battery replacement tier fallback,
    daily reports zero-filtered fallback, and disjoint recall year segment parsing.
    """

    def test_battery_replacement_tier_fallback(self) -> None:
        """simulateBatteryHealth must gracefully fallback across tiers without out-of-bounds errors."""
        script = """
        import { simulateBatteryHealth } from './src/lib/getDepreciationData';
        const resSmall = simulateBatteryHealth({ years: 3, totalKm: 45000, packCapacityKwh: 50 });
        const resLarge = simulateBatteryHealth({ years: 3, totalKm: 45000, packCapacityKwh: 100 });
        console.log(JSON.stringify({
            smallTier: resSmall.replacementCostEstimate.tierId,
            largeTier: resLarge.replacementCostEstimate.tierId,
            smallCost: resSmall.replacementCostEstimate.estimatedCostKrw,
            largeCost: resLarge.replacementCostEstimate.estimatedCostKrw,
        }));
        """
        output = _eval_ts_node(script)
        self.assertEqual(output["smallTier"], "TIER_50KWH")
        self.assertEqual(output["largeTier"], "TIER_100KWH")
        self.assertGreater(output["smallCost"], 0)
        self.assertGreater(output["largeCost"], 0)

    def test_daily_reports_zero_records_kpi_fallback(self) -> None:
        """calculateKPIs with empty report list must return non-synthetic zero-count fallbacks."""
        script = """
        import { calculateKPIs } from './src/lib/getDailyReports';
        const kpis = calculateKPIs([]);
        console.log(JSON.stringify(kpis));
        """
        output = _eval_ts_node(script)
        self.assertEqual(output["total_filtered_defects"], 0)
        self.assertEqual(output["avg_negativity_score"], 0.0)
        self.assertEqual(output["top_model"], "해당 없음 (0건)")
        self.assertEqual(output["top_platform"], "해당 없음 (0%)")

    def test_recall_data_comma_delimited_segment_parsing(self) -> None:
        """isYearMatchForCampaign must correctly parse comma/semicolon-delimited disjoint year segments."""
        script = """
        import { isYearMatchForCampaign } from './src/lib/getRecallData';
        console.log(JSON.stringify({
            disjointMid: isYearMatchForCampaign(2021, "2018, 2024"),
            disjointStart: isYearMatchForCampaign(2018, "2018, 2024"),
            disjointEnd: isYearMatchForCampaign(2024, "2018, 2024"),
            rangeMid: isYearMatchForCampaign(2023, "2019, 2022~2024"),
            rangeExcluded: isYearMatchForCampaign(2020, "2019, 2022~2024"),
            rangeSingle: isYearMatchForCampaign(2019, "2019, 2022~2024"),
            semicolonDelim: isYearMatchForCampaign(2025, "2020; 2025"),
        }));
        """
        output = _eval_ts_node(script)
        # Disjoint "2018, 2024": 2021 should NOT match, 2018 and 2024 MUST match
        self.assertFalse(output["disjointMid"], "2021 should not match disjoint campaign '2018, 2024'")
        self.assertTrue(output["disjointStart"], "2018 should match disjoint campaign '2018, 2024'")
        self.assertTrue(output["disjointEnd"], "2024 should match disjoint campaign '2018, 2024'")

        # Range segment "2019, 2022~2024": 2023 matches, 2020 does not match, 2019 matches
        self.assertTrue(output["rangeMid"], "2023 should match '2019, 2022~2024'")
        self.assertFalse(output["rangeExcluded"], "2020 should not match '2019, 2022~2024'")
        self.assertTrue(output["rangeSingle"], "2019 should match '2019, 2022~2024'")

        # Semicolon delimiter "2020; 2025"
        self.assertTrue(output["semicolonDelim"], "2025 should match '2020; 2025'")


# ============================================================================
# 5. Accessibility & Performance Invariants Tests
# ============================================================================
class TestCycle13AccessibilityAndPerformanceInvariants(unittest.TestCase):
    """Verifies heading monotonicity across all 12 App Router pages, font preload: false,
    and WCAG 2.1 AA landmark regions.
    """

    def test_heading_monotonicity_across_all_12_pages(self) -> None:
        """Every App Router page and its client component must maintain monotonic heading hierarchy (step <= 1)."""
        page_routes = [
            APP_DIR / "page.tsx",
            APP_DIR / "2026-latest" / "page.tsx",
            APP_DIR / "byd" / "page.tsx",
            APP_DIR / "depreciation-calculator" / "page.tsx",
            APP_DIR / "global-brands" / "page.tsx",
            APP_DIR / "hyundai-kia" / "page.tsx",
            APP_DIR / "pdi-checklist" / "page.tsx",
            APP_DIR / "recall-portal" / "page.tsx",
            APP_DIR / "reliability-analytics" / "page.tsx",
            APP_DIR / "secret-admin-reports" / "page.tsx",
            APP_DIR / "subsidy-tracker" / "page.tsx",
            APP_DIR / "tesla" / "page.tsx",
        ]

        heading_re = re.compile(r"<h([1-6])[\s>]")

        for p in page_routes:
            self.assertTrue(p.exists(), f"Route file {p} must exist")
            content = p.read_text(encoding="utf-8")

            # Also include co-located client components if imported
            client_files = list(p.parent.glob("*Client.tsx"))
            combined_content = content
            for cf in client_files:
                combined_content += "\n" + cf.read_text(encoding="utf-8")

            matches = [int(m.group(1)) for m in heading_re.finditer(combined_content)]
            self.assertGreater(len(matches), 0, f"Page {p.parent.name} must have at least one heading")
            self.assertEqual(matches[0], 1, f"First heading in {p.parent.name} must be h1, got h{matches[0]}")

            # Verify no skipped heading levels (e.g. h1 -> h3 or h2 -> h4)
            current_level = matches[0]
            for lvl in matches[1:]:
                step = lvl - current_level
                self.assertLessEqual(
                    step,
                    1,
                    f"Heading skipped levels in {p.parent.name}: h{current_level} followed directly by h{lvl}",
                )
                current_level = lvl

    def test_layout_font_preload_and_force_static_declarations(self) -> None:
        """layout.tsx must configure preload: false on geistMono, and all 12 pages must declare force-static."""
        layout_file = APP_DIR / "layout.tsx"
        self.assertTrue(layout_file.exists())
        layout_text = layout_file.read_text(encoding="utf-8")

        # GeistMono preload: false
        self.assertIn("preload: false", layout_text, "geistMono in layout.tsx must have preload: false")

        # All 12 pages declare force-static
        page_routes = [
            APP_DIR / "page.tsx",
            APP_DIR / "2026-latest" / "page.tsx",
            APP_DIR / "byd" / "page.tsx",
            APP_DIR / "depreciation-calculator" / "page.tsx",
            APP_DIR / "global-brands" / "page.tsx",
            APP_DIR / "hyundai-kia" / "page.tsx",
            APP_DIR / "pdi-checklist" / "page.tsx",
            APP_DIR / "recall-portal" / "page.tsx",
            APP_DIR / "reliability-analytics" / "page.tsx",
            APP_DIR / "secret-admin-reports" / "page.tsx",
            APP_DIR / "subsidy-tracker" / "page.tsx",
            APP_DIR / "tesla" / "page.tsx",
        ]
        for p in page_routes:
            text = p.read_text(encoding="utf-8")
            self.assertTrue(
                "export const dynamic = 'force-static';" in text
                or 'export const dynamic = "force-static";' in text,
                f"Page {p} must declare force-static",
            )

    def test_wcag21aa_landmark_and_semantic_improvements(self) -> None:
        """Verify WCAG 2.1 AA improvements: hub aria-label, footer label, PDI warning linkage, and accessible table."""
        # 1. Page.tsx hub navigation section aria-label
        page_content = (APP_DIR / "page.tsx").read_text(encoding="utf-8")
        self.assertIn('aria-label="서비스 주요 진입점 바로가기 그리드"', page_content)

        # 2. SiteFooter or layout footer label
        footer_file = SRC_DIR / "components" / "layout" / "SiteFooter.tsx"
        self.assertTrue(footer_file.exists())
        footer_content = footer_file.read_text(encoding="utf-8")
        self.assertIn('aria-label="법적 고지 및 데이터 출처"', footer_content)
        self.assertIn('role="contentinfo"', footer_content)

        # 3. PDI Checklist aria-describedby warning connection
        pdi_content = (APP_DIR / "pdi-checklist" / "PdiChecklistClient.tsx").read_text(encoding="utf-8")
        self.assertIn("aria-describedby", pdi_content)
        self.assertIn("pdi-warning-", pdi_content)

        # 4. AdminDashboard screen reader table does not hide title with aria-hidden
        admin_content = (APP_DIR / "secret-admin-reports" / "AdminDashboardClient.tsx").read_text(encoding="utf-8")
        self.assertIn("<span>{report.title}</span>", admin_content)


# ============================================================================
# 6. Mirror Parity & POSIX Permissions Tests
# ============================================================================
class TestCycle13MirrorParity(unittest.TestCase):
    """Verifies 100% cryptographic SHA-256 bitwise parity and 0o644 permissions
    for test suites and dataset files.
    """

    def test_test_suite_mirror_parity_and_permissions(self) -> None:
        """tests/test_cycle13_hardening.py and ev-stealth-web/tests/test_cycle13_hardening.py must be bitwise identical."""
        root_test = PROJECT_ROOT / "tests" / "test_cycle13_hardening.py"
        web_test = WEB_ROOT / "tests" / "test_cycle13_hardening.py"

        self.assertTrue(root_test.exists(), f"{root_test} must exist")
        self.assertTrue(web_test.exists(), f"{web_test} must exist")

        root_bytes = root_test.read_bytes()
        web_bytes = web_test.read_bytes()

        root_sha = hashlib.sha256(root_bytes).hexdigest()
        web_sha = hashlib.sha256(web_bytes).hexdigest()

        self.assertEqual(
            root_sha,
            web_sha,
            f"Test suite files must have 100% bitwise parity. Root: {root_sha}, Web: {web_sha}",
        )

        # Check POSIX 0o644 permissions
        root_mode = oct(stat.S_IMODE(root_test.stat().st_mode))
        web_mode = oct(stat.S_IMODE(web_test.stat().st_mode))
        self.assertEqual(root_mode, "0o644", f"Root test permissions must be 0o644, got {root_mode}")
        self.assertEqual(web_mode, "0o644", f"Web test permissions must be 0o644, got {web_mode}")

    def test_dataset_triple_parity_and_permissions(self) -> None:
        """All 4 core datasets must maintain 100% SHA-256 parity across root, src, and public directories."""
        datasets = [
            "ev_subsidy_data.json",
            "subsidy_depletion_data.json",
            "daily_reports.json",
            "models_subsidy_matrix.json",
        ]

        dir_root = PROJECT_ROOT / "data"
        dir_src = WEB_ROOT / "src" / "data"
        dir_pub = WEB_ROOT / "public" / "data"

        for ds in datasets:
            p_root = dir_root / ds
            p_src = dir_src / ds
            p_pub = dir_pub / ds

            self.assertTrue(p_root.exists(), f"Root dataset {p_root} must exist")
            self.assertTrue(p_src.exists(), f"Web src dataset {p_src} must exist")
            self.assertTrue(p_pub.exists(), f"Public dataset {p_pub} must exist")

            sha_root = hashlib.sha256(p_root.read_bytes()).hexdigest()
            sha_src = hashlib.sha256(p_src.read_bytes()).hexdigest()
            sha_pub = hashlib.sha256(p_pub.read_bytes()).hexdigest()

            self.assertEqual(
                sha_root,
                sha_src,
                f"Dataset parity mismatch between root and src for {ds}",
            )
            self.assertEqual(
                sha_root,
                sha_pub,
                f"Dataset parity mismatch between root and public for {ds}",
            )


if __name__ == "__main__":
    unittest.main()
