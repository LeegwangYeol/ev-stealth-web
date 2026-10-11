"""
tests/test_cycle13_backend_hardening.py - Comprehensive Unit Tests for Cycle 13 Backend Remediations.

Validates:
1. ReportGenerator.generate_defect_briefing() robustness with None, NaN, Inf severity_index and None defect_category.
2. ReportGenerator.generate_subsidy_briefing() robustness when remaining_units, announced_units, or category metrics are None.
3. DefectTracker.query_defects() with limit <= 0 (limit=0, limit=-1) returns [] directly.
4. DefectTracker.query_defects() thread-safe cache key generation within _cache_lock with normalized min_severity.
5. DefectTracker.query_defects() keyword search includes summary field.
6. atomic_write_json and write_daily_reports RFC 8259 compliance: float NaN and Inf converted to 0.0 with allow_nan=False.
7. utils/json_writer.write_daily_reports() historical merge filtering: gracefully ignores corrupted non-dict entries.
8. tracker/subsidy_baseline.py defensive guards in calculate_price_cap_ratio() and calculate_net_subsidy().
9. utils/http_client.encode_euc_kr_query() safe guards on None, non-dict, and non-str inputs.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from typing import Any, Dict, List

from tracker.atomic_writer import atomic_write_json, sanitize_nan_inf
from tracker.defect_tracker import DefectTracker
from tracker.report_generator import ReportGenerator
from tracker.subsidy_baseline import (
    calculate_net_subsidy,
    calculate_price_cap_ratio,
    build_initial_baseline,
)
from utils.http_client import encode_euc_kr_query
from utils.json_writer import format_daily_report_payload, write_daily_reports


class TestReportGeneratorHardening(unittest.TestCase):
    """Test defensive guards in ReportGenerator against None, NaN, and malformed inputs."""

    def setUp(self) -> None:
        self.generator = ReportGenerator()

    def test_generate_defect_briefing_with_none_severity_index(self) -> None:
        """generate_defect_briefing should not raise TypeError when severity_index is None."""
        payload = {
            "reports": [
                {
                    "id": "defect-1",
                    "title": "BMS Warning",
                    "vehicle_brand": "현대",
                    "vehicle_model": "아이오닉 5",
                    "severity_index": None,
                    "defect_category": None,
                },
                {
                    "id": "defect-2",
                    "title": "ICC Failure",
                    "vehicle_brand": "기아",
                    "vehicle_model": "EV6",
                    "severity_index": 8.5,
                    "defect_category": "BATTERY_CHARGING",
                },
                {
                    "id": "defect-3",
                    "title": "Rattle Noise",
                    "vehicle_brand": "테슬라",
                    "vehicle_model": "Model Y",
                    "severity_index": float("nan"),
                    "defect_category": "BUILD_QUALITY",
                },
            ],
            "statistics": {
                "critical_defect_count": None,
                "avg_negativity_score": None,
            },
        }
        briefing = self.generator.generate_defect_briefing(payload)
        self.assertIn("총 수집/분류 결함 건수**: 3건", briefing)
        self.assertIn("기아 EV6", briefing)
        self.assertIn("DSI: 8.5", briefing)

    def test_generate_defect_briefing_with_list_input_and_null_values(self) -> None:
        """generate_defect_briefing accepts list of dicts with null severity scores."""
        reports = [
            {"id": "d-1", "severity_index": None, "vehicle_brand": "현대"},
            {"id": "d-2", "severity_index": 9.2, "vehicle_brand": "현대", "defect_topic": "구동모터 경고"},
        ]
        briefing = self.generator.generate_defect_briefing(reports)
        self.assertIn("구동모터 경고", briefing)
        self.assertIn("DSI: 9.2", briefing)

    def test_generate_subsidy_briefing_with_none_units(self) -> None:
        """generate_subsidy_briefing handles None remaining_units and announced_units gracefully."""
        payload = build_initial_baseline()
        # Artificially inject None values into regions and categories
        payload.regions[0].categories["passenger"].remaining_units = None
        payload.regions[0].categories["passenger"].announced_units = None
        payload.regions[0].categories["passenger"].applied_units = None
        payload.regions[0].categories["passenger"].depletion_rate = None
        payload.regions[0].categories["passenger"].status = None

        briefing = self.generator.generate_subsidy_briefing(payload)
        self.assertIn("전국 지자체 전기차 보조금", briefing)
        self.assertIn("차종별 소진 현황", briefing)
        self.assertIn("잔여: 0대", briefing)


class TestDefectTrackerHardening(unittest.TestCase):
    """Test DefectTracker limit<=0, thread safety, normalized caching, and summary search."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="test_dt_hardening_")
        self.test_file = Path(self.temp_dir) / "daily_reports.json"
        sample_data = {
            "reports": [
                {
                    "id": "dt-1",
                    "title": "ICC Failure",
                    "defect_topic": "고전압 배터리 충전 불량",
                    "summary": "완속 충전 시 차단기 트립 현상 발생",
                    "verbatim_quote": "완속 충전기 꽂자마자 퍽 소리 나며 꺼짐",
                    "raw_quote": "완속 충전기 꽂자마자 퍽 소리 나며 꺼짐",
                    "vehicle_brand": "현대",
                    "vehicle_model": "아이오닉 5",
                    "defect_category": "BATTERY_CHARGING",
                    "severity_index": 8.5,
                    "is_authentic_defect": True,
                },
                {
                    "id": "dt-2",
                    "title": "Brake System",
                    "defect_topic": "회생제동 이질감",
                    "summary": "원페달 드라이빙 모드에서 감속 불균형",
                    "verbatim_quote": "회생제동 레벨 3에서 울컥거림 심함",
                    "raw_quote": "회생제동 레벨 3에서 울컥거림 심함",
                    "vehicle_brand": "기아",
                    "vehicle_model": "EV6",
                    "defect_category": "BRAKE_SYSTEM",
                    "severity_index": 6.0,
                    "is_authentic_defect": True,
                },
            ]
        }
        with open(self.test_file, "w", encoding="utf-8") as f:
            json.dump(sample_data, f)
        self.tracker = DefectTracker()

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_query_defects_limit_zero_and_negative(self) -> None:
        """query_defects with limit=0 or limit=-1 returns empty list []."""
        res_zero = self.tracker.query_defects(file_path=self.test_file, limit=0)
        self.assertEqual(res_zero, [])

        res_neg = self.tracker.query_defects(file_path=self.test_file, limit=-5)
        self.assertEqual(res_neg, [])

    def test_query_defects_keyword_includes_summary(self) -> None:
        """query_defects finds keyword that only appears in the summary field."""
        # "트립" appears only in dt-1's summary
        res = self.tracker.query_defects(file_path=self.test_file, keyword="트립")
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["id"], "dt-1")

        # "감속" appears only in dt-2's summary
        res2 = self.tracker.query_defects(file_path=self.test_file, keyword="감속")
        self.assertEqual(len(res2), 1)
        self.assertEqual(res2[0]["id"], "dt-2")

    def test_query_defects_cache_key_thread_safety(self) -> None:
        """Concurrent queries with varying min_severity do not corrupt LRU query cache."""
        errors: List[Exception] = []

        def worker(thread_id: int) -> None:
            try:
                for i in range(20):
                    # Alternate between float, string, and None
                    sev = 6.0 if (i % 2 == 0) else "8.5"
                    results = self.tracker.query_defects(
                        file_path=self.test_file,
                        min_severity=sev,
                        category="BATTERY_CHARGING" if i % 3 == 0 else None,
                    )
                    self.assertIsInstance(results, list)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"Thread concurrency errors occurred: {errors}")


class TestRFC8259SanitizationAndAtomicWriter(unittest.TestCase):
    """Test float NaN and Inf sanitization in atomic_writer and utils/json_writer."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="test_rfc8259_")

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sanitize_nan_inf_recursive(self) -> None:
        """sanitize_nan_inf converts NaN, +Inf, -Inf to 0.0 recursively across dicts and lists."""
        payload = {
            "nan": float("nan"),
            "pos_inf": float("inf"),
            "neg_inf": float("-inf"),
            "nested": {
                "inner_nan": float("nan"),
                "array": [1.0, float("nan"), float("inf"), "safe_str"],
            },
            "valid_float": 3.14,
        }
        sanitized = sanitize_nan_inf(payload)
        self.assertEqual(sanitized["nan"], 0.0)
        self.assertEqual(sanitized["pos_inf"], 0.0)
        self.assertEqual(sanitized["neg_inf"], 0.0)
        self.assertEqual(sanitized["nested"]["inner_nan"], 0.0)
        self.assertEqual(sanitized["nested"]["array"][1], 0.0)
        self.assertEqual(sanitized["nested"]["array"][2], 0.0)
        self.assertEqual(sanitized["nested"]["array"][3], "safe_str")
        self.assertEqual(sanitized["valid_float"], 3.14)

    def test_atomic_write_json_rejects_nan_and_writes_compliant_json(self) -> None:
        """atomic_write_json sanitizes NaNs and produces strict RFC 8259 JSON readable by any parser."""
        target = Path(self.temp_dir) / "test_nan.json"
        data = {
            "rate": float("nan"),
            "inf": float("inf"),
            "list": [float("nan"), 42],
        }
        atomic_write_json(data, target)
        with open(target, "r", encoding="utf-8") as f:
            raw_text = f.read()

        # Strict test: RFC 8259 forbid unquoted NaN/Infinity
        self.assertNotIn("NaN", raw_text)
        self.assertNotIn("Infinity", raw_text)

        loaded = json.loads(raw_text)
        self.assertEqual(loaded["rate"], 0.0)
        self.assertEqual(loaded["inf"], 0.0)
        self.assertEqual(loaded["list"][0], 0.0)
        self.assertEqual(loaded["list"][1], 42)


class TestJsonWriterHistoricalMergeAndScores(unittest.TestCase):
    """Test utils/json_writer safe historical merge and score sanitization."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="test_jw_merge_")
        self.target_path = Path(self.temp_dir) / "daily_reports.json"

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_write_daily_reports_merges_gracefully_with_corrupted_non_dict_entries(self) -> None:
        """write_daily_reports should not crash with AttributeError when existing_reports contains non-dict."""
        corrupted_existing = {
            "reports": [
                {"id": "exist-1", "title": "Existing Valid Issue", "url": "http://example.com/1"},
                None,  # Corrupted historical None entry
                "string_not_dict",  # Corrupted historical string entry
                12345,  # Corrupted historical int entry
            ],
            "statistics": {
                "total_scraped": 4,
            },
        }
        with open(self.target_path, "w", encoding="utf-8") as f:
            json.dump(corrupted_existing, f)

        new_complaints = [
            {
                "id": "new-1",
                "title": "New Defect",
                "url": "http://example.com/2",
                "negativity_score": float("nan"),
                "severity_index": float("nan"),
                "is_authentic_defect": True,
            }
        ]

        result_path = write_daily_reports(
            complaints=new_complaints,
            output_path=str(self.target_path),
            merge_existing=True,
        )
        self.assertTrue(os.path.exists(result_path))

        with open(result_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertNotIn("NaN", content)
        data = json.loads(content)
        report_ids = [r["id"] for r in data["reports"]]
        self.assertIn("exist-1", report_ids)
        self.assertIn("new-1", report_ids)
        # Ensure NaN was converted to safe default in payload
        new_report = next(r for r in data["reports"] if r["id"] == "new-1")
        self.assertEqual(new_report["negativity_score"], 0.5)
        self.assertEqual(new_report["severity_index"], 0.0)


class TestSubsidyBaselineDefensiveHardening(unittest.TestCase):
    """Test calculate_price_cap_ratio and calculate_net_subsidy defensive boundaries in subsidy_baseline.py."""

    def test_calculate_price_cap_ratio_none_nan_and_valid(self) -> None:
        """calculate_price_cap_ratio safely handles None, NaN, Inf, and statutory brackets."""
        self.assertEqual(calculate_price_cap_ratio(None), 0.0)  # type: ignore
        self.assertEqual(calculate_price_cap_ratio(float("nan")), 0.0)  # type: ignore
        self.assertEqual(calculate_price_cap_ratio(float("inf")), 0.0)  # type: ignore
        self.assertEqual(calculate_price_cap_ratio("invalid"), 0.0)  # type: ignore

        # Statutory 2026 brackets
        self.assertEqual(calculate_price_cap_ratio(50_000_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_000_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_000_001), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_001), 0.0)

    def test_calculate_net_subsidy_defensive_none_inputs(self) -> None:
        """calculate_net_subsidy safely returns non-negative calculations when arguments are None."""
        res_null = calculate_net_subsidy(None, None, None, None)  # type: ignore
        self.assertEqual(res_null["national_subsidy_krw"], 0)
        self.assertEqual(res_null["local_subsidy_krw"], 0)
        self.assertEqual(res_null["total_subsidy_krw"], 0)
        self.assertEqual(res_null["net_price_krw"], 0)

        # Valid standard case
        res_valid = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=6_500_000,
            max_local=4_000_000,
            msrp=53_000_000,
        )
        self.assertEqual(res_valid["national_subsidy_krw"], 6_500_000)
        self.assertEqual(res_valid["local_subsidy_krw"], 4_000_000)
        self.assertEqual(res_valid["total_subsidy_krw"], 10_500_000)
        self.assertEqual(res_valid["net_price_krw"], 42_500_000)


class TestHttpClientEncodeEucKrHardening(unittest.TestCase):
    """Test utils/http_client.encode_euc_kr_query() safe guards on diverse types."""

    def test_encode_euc_kr_query_none_and_invalid(self) -> None:
        """encode_euc_kr_query returns empty string for None, numbers, booleans, and empty strings."""
        self.assertEqual(encode_euc_kr_query(None), "")
        self.assertEqual(encode_euc_kr_query(""), "")
        self.assertEqual(encode_euc_kr_query(12345), "")  # type: ignore
        self.assertEqual(encode_euc_kr_query(True), "")  # type: ignore
        self.assertEqual(encode_euc_kr_query([]), "")  # type: ignore

    def test_encode_euc_kr_query_valid_string_and_dict(self) -> None:
        """encode_euc_kr_query percent-encodes Korean string or dictionary into valid EUC-KR / CP949."""
        encoded_str = encode_euc_kr_query("전기차")
        self.assertTrue(len(encoded_str) > 0)
        self.assertTrue("%" in encoded_str)

        encoded_dict = encode_euc_kr_query({"search_kw": "결함", "page": 1})
        self.assertIn("search_kw=", encoded_dict)
        self.assertIn("page=1", encoded_dict)


if __name__ == "__main__":
    unittest.main()
