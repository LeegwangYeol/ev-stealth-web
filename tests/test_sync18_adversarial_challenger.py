#!/usr/bin/env python3
"""tests/test_sync18_adversarial_challenger.py - Cycle 18 Adversarial Edge Cases & Fuzzing Challenger Suite.

Authored by sync18_challenger_adversarial_w3 (Empirical Challenger, Wave 3).
Empirically stress-tests, fuzzes, and boundary-challenges the system against:
1. Malformed inputs & extreme numerical values (negative MSRPs, enormous numbers, NaN, Inf)
2. Adversarial fuzzing against crawlers, filters, and trackers
3. Date parser fuzzing (Korean dotted dates, 2-digit years, out-of-range timestamps)
4. Atomic writer concurrency, crash durability, serialization guarantees, and fault injection
5. Model mapping protocols, standard KeyError enforcement, and monkey-patch eradication
6. Cross-tier parity between Python backend calculators and TypeScript frontend helpers
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import datetime
from decimal import Decimal
from enum import Enum
import json
import logging
import math
import os
from pathlib import Path
import random
import re
import string
import sys
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional, Union
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
CURRENT_FILE_PARENT = Path(__file__).resolve().parent.parent
if CURRENT_FILE_PARENT.name == "ev-stealth-web":
    WEB_ROOT = CURRENT_FILE_PARENT
    PROJECT_ROOT = CURRENT_FILE_PARENT.parent
else:
    PROJECT_ROOT = CURRENT_FILE_PARENT
    WEB_ROOT = PROJECT_ROOT / "ev-stealth-web"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if WEB_ROOT.exists() and str(WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_ROOT))

# Backend modules under test
from crawlers.bobaedream import BobaeDreamCrawler
from crawlers.dcinside import DCInsideCrawler
from filters.defect_filter import ContextualDefectFilter
from filters.vehicle_matcher import extract_vehicle_info, VALID_BRANDS
from models.complaint import (
    ComplaintRecord,
    DailyReportPayload,
    DailyReportStatistics,
    DSIBreakdown,
    RawPost,
    _safe_round,
)
from tracker.atomic_writer import (
    _json_default,
    atomic_write_json,
    atomic_write_json_multiple,
    sanitize_nan_inf,
)
from tracker.subsidy_baseline import (
    calculate_price_cap_ratio as baseline_price_cap_ratio,
    calculate_net_subsidy as baseline_net_subsidy,
)
from tracker.subsidy_models import (
    AlertSeverity,
    CategoryMetrics,
    MunicipalityMetrics,
)
from tracker.subsidy_tracker import (
    calculate_depletion_rate,
    calculate_net_subsidy as tracker_net_subsidy,
    calculate_price_cap_ratio as tracker_price_cap_ratio,
    calculate_remaining_units,
    classify_alert_tier,
)
from utils.http_client import SafeHttpClient, clean_html_text
from utils.json_writer import (
    _extract_record_date,
    _safe_float,
    format_daily_report_payload,
    read_daily_reports,
    write_daily_reports,
)


class TestExtremeNumericalValuesAndMSRPPriceCaps(unittest.TestCase):
    """Part 1: Extreme numerical values, boundary MSRP price caps, and IEEE 754 specials."""

    def test_01_price_cap_ratio_boundary_and_negative_guards(self) -> None:
        """calculate_price_cap_ratio strictly returns 0.0 for <=0 MSRP, 1.0 for <=55M, 0.5 for <=85M, 0.0 for >85M."""
        test_cases = [
            (-1, 0.0),
            (-999_999_999, 0.0),
            (-1e20, 0.0),
            (0, 0.0),
            (1, 1.0),
            (54_999_999, 1.0),
            (55_000_000, 1.0),
            (55_000_001, 0.5),
            (84_999_999, 0.5),
            (85_000_000, 0.5),
            (85_000_001, 0.0),
            (100_000_000, 0.0),
            (10**18, 0.0),
            (None, 0.0),
            (float("nan"), 0.0),
            (float("inf"), 0.0),
            (float("-inf"), 0.0),
            ("invalid", 0.0),
            ([], 0.0),
        ]
        for val, expected in test_cases:
            with self.subTest(val=val, expected=expected):
                res_tracker = tracker_price_cap_ratio(val)  # type: ignore
                res_baseline = baseline_price_cap_ratio(val)  # type: ignore
                self.assertEqual(res_tracker, expected)
                self.assertEqual(res_baseline, expected)
                self.assertIsInstance(res_tracker, float)
                self.assertFalse(math.isnan(res_tracker))
                self.assertFalse(math.isinf(res_tracker))

    def test_02_calculate_net_subsidy_contract_and_non_negative_invariants(self) -> None:
        """calculate_net_subsidy guarantees price_cap_ratio key in return dict and non-negative net price."""
        extreme_msrps = [-100_000_000, 0, 30_000_000, 55_000_000, 70_000_000, 90_000_000, float("nan"), float("inf")]
        for msrp in extreme_msrps:
            with self.subTest(msrp=msrp):
                res_t = tracker_net_subsidy(
                    model_national=6_500_000,
                    max_national=6_500_000,
                    max_local=4_000_000,
                    msrp=msrp,  # type: ignore
                )
                res_b = baseline_net_subsidy(
                    model_national=6_500_000,
                    max_national=6_500_000,
                    max_local=4_000_000,
                    msrp=msrp,  # type: ignore
                )
                for res in (res_t, res_b):
                    self.assertIn("price_cap_ratio", res)
                    self.assertIn("national_subsidy_krw", res)
                    self.assertIn("local_subsidy_krw", res)
                    self.assertIn("total_subsidy_krw", res)
                    self.assertIn("net_price_krw", res)
                    self.assertGreaterEqual(res["net_price_krw"], 0)
                    self.assertGreaterEqual(res["total_subsidy_krw"], 0)
                    self.assertIn(res["price_cap_ratio"], [0.0, 0.5, 1.0])

    def test_03_calculate_depletion_rate_and_remaining_units_fuzzing(self) -> None:
        """Randomized fuzzing of calculate_depletion_rate and calculate_remaining_units."""
        rng = random.Random(42)
        for _ in range(500):
            applied = rng.choice([-1000, 0, rng.randint(1, 100_000), float("nan"), float("inf"), None])
            announced = rng.choice([-1000, 0, rng.randint(1, 100_000), float("nan"), float("inf"), None])
            rate = calculate_depletion_rate(applied, announced)  # type: ignore
            rem = calculate_remaining_units(applied, announced)  # type: ignore

            self.assertIsInstance(rate, float)
            self.assertIsInstance(rem, int)
            self.assertGreaterEqual(rate, 0.0)
            self.assertGreaterEqual(rem, 0)
            self.assertFalse(math.isnan(rate))
            self.assertFalse(math.isinf(rate))


class TestDateParserFuzzingAndResilience(unittest.TestCase):
    """Part 2: Date parsing, Korean dotted dates, 2-digit years, and boundary timestamp fuzzing."""

    def test_01_extract_record_date_korean_dotted_and_slash_formats(self) -> None:
        """_extract_record_date correctly standardizes Korean dotted, dashed, slashed, and spaced formats."""
        cases = [
            ({"date": "2026.10.25"}, "2026-10-25"),
            ({"date": "2026. 10. 25."}, "2026-10-25"),
            ({"created_at": "2026-10-25"}, "2026-10-25"),
            ({"created_at": "2026/10/25"}, "2026-10-25"),
            ({"timestamp": "2026. 1. 5."}, "2026-01-05"),
            ({"date": "26.10.25"}, "2026-10-25"),
            ({"date": "26-10-25"}, "2026-10-25"),
            ({"date": "26/10/25"}, "2026-10-25"),
            ({"created_at": "2026-10-25T14:30:00Z"}, "2026-10-25"),
            ({"date": ""}, ""),
            ({"date": None}, ""),
            ({}, ""),
            ({"date": "오늘 10:30"}, ""),
        ]
        for record, expected in cases:
            with self.subTest(record=record, expected=expected):
                res = _extract_record_date(record)
                self.assertEqual(res, expected)

    def test_02_complaint_record_date_str_property_resilience(self) -> None:
        """ComplaintRecord.date_str property extracts normalized date or defaults to today."""
        today_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

        cases = [
            ("2026. 10. 25.", "2026-10-25"),
            ("2026.10.25", "2026-10-25"),
            ("26.10.25", "2026-10-25"),
            ("2026-10-25", "2026-10-25"),
            ("", today_iso),
            (None, today_iso),
            ("invalid", today_iso),
        ]
        for input_date, expected in cases:
            with self.subTest(input_date=input_date, expected=expected):
                record = ComplaintRecord(
                    id="TEST_01",
                    source="bobaedream",
                    url="https://example.com/1",
                    title="아이오닉5 ICCU 결함",
                    author="차주1",
                    created_at=input_date,  # type: ignore
                    vehicle_brand="Hyundai",
                    vehicle_model="아이오닉5",
                    defect_category="BATTERY_CHARGING",
                    summary="ICCU 교체",
                    verbatim_quote="주행 중 경고등 점등되더니 멈췄습니다.",
                )
                self.assertEqual(record.date_str, expected)

    def test_03_format_daily_report_payload_target_date_filtering(self) -> None:
        """format_daily_report_payload accurately counts total_complaints_today against target generated_at."""
        target_date = "2026-10-25T12:00:00Z"
        complaints = [
            {"is_authentic_defect": True, "date": "2026.10.25", "negativity_score": 0.9, "id": "1"},
            {"is_authentic_defect": True, "created_at": "2026-10-25", "negativity_score": 0.8, "id": "2"},
            {"is_authentic_defect": True, "date": "2026-10-24", "negativity_score": 0.7, "id": "3"},  # Yesterday
            {"is_authentic_defect": True, "date": "", "negativity_score": 0.6, "id": "4"},  # Undated -> counts today
            {"is_authentic_defect": False, "date": "2026-10-25", "negativity_score": 0.5, "id": "5"},  # Non-defect
        ]
        payload = format_daily_report_payload(
            complaints=complaints,
            generated_at=target_date,
        )
        self.assertEqual(len(payload.reports), 4)  # 4 authentic defects
        # today matches: id=1, id=2 (2 records) + undated id=4 (1 record) = 3
        self.assertEqual(payload.total_complaints_today, 3)


class TestDefectFilterAndVehicleMatcherFuzzing(unittest.TestCase):
    """Part 3: DefectFilter, VehicleMatcher, and NLP text fuzzing with extreme inputs."""

    def setUp(self) -> None:
        logging.getLogger("ContextualDefectFilter").setLevel(logging.CRITICAL)
        self.filter = ContextualDefectFilter()

    def test_01_vehicle_matcher_fuzzing_with_adversarial_strings(self) -> None:
        """extract_vehicle_info survives null, non-str, massive strings, and Korean slang without crashing."""
        adversarial_inputs = [
            (None, None),
            ("", ""),
            (12345, 67890),
            (["아이오닉5"], {"content": "테슬라"}),
            ("A" * 50_000, "B" * 50_000),  # Massive strings
            ("\x00\x00\x00", "\x01\x02"),  # Null bytes
            ("아이오닉 5 N 충전 먹통", "신차 출고 후 바로 터짐"),
            ("테슬라 모델 Y RWD 주니퍼", "단차 누수 심각함"),
            ("BYD 아토 3 배터리 불량", "비야디 전기차 수리비"),
            ("타이칸 배터리 방전", "포르쉐 서비스센터 불만"),
            ("엔진오일 교체 후기", "그냥 일반 가솔린 세단"),  # Unrelated car
        ]
        for title, content in adversarial_inputs:
            with self.subTest(title=str(title)[:20]):
                brand, model = extract_vehicle_info(title, content)  # type: ignore
                self.assertIn(brand, VALID_BRANDS)
                self.assertIsInstance(model, str)
                self.assertTrue(len(model) > 0)

    def test_02_defect_filter_process_post_comments_polymorphism_and_none(self) -> None:
        """DefectFilter.process_post gracefully filters non-string comment items without TypeError."""
        post_with_bad_comments = RawPost(
            platform="bobaedream",
            post_id="POST_BAD_CMT",
            url="https://example.com/post/1",
            title="아이오닉5 출고 3일만에 주행 중 동력상실",
            content="제 차 아이오닉5 인데 어제 고속도로에서 갑자기 거북이 경고등 뜨고 멈췄습니다.",
            comments=[None, 12345, True, {"text": "bad"}, ["nested"], "정말 심각하네요 블루핸즈 가보세요"],  # type: ignore
        )
        record = self.filter.process_post(post_with_bad_comments)
        self.assertIsInstance(record, ComplaintRecord)
        self.assertEqual(record.vehicle_brand, "Hyundai")
        self.assertEqual(record.vehicle_model, "아이오닉5")
        self.assertTrue(record.is_authentic_defect)
        self.assertGreaterEqual(record.severity_index, 3.5)

    def test_03_defect_filter_massive_repetitive_text_redos_immunity(self) -> None:
        """DefectFilter processes huge 100k repetitive strings in under 1.0 second (ReDoS immunity)."""
        huge_text = ("아이오닉5 결함 고장 " * 5_000)
        start_time = time.perf_counter()
        is_owner, reason = self.filter.evaluate_stage2_ownership(huge_text)
        elapsed = time.perf_counter() - start_time
        self.assertLess(elapsed, 1.0, f"ReDoS suspected: processing took {elapsed:.2f}s")


class TestModelMappingProtocolAndKeyErrorStandardization(unittest.TestCase):
    """Part 4: Protocol compliance, standard KeyError enforcement, and monkey-patch removal."""

    def test_01_category_metrics_mapping_protocol(self) -> None:
        """CategoryMetrics raises KeyError on missing keys and implements __contains__ and .get()."""
        cm = CategoryMetrics(
            announced_units=100,
            applied_units=80,
            delivered_units=70,
            remaining_units=20,
            depletion_rate=80.0,
            delivery_rate=70.0,
            status="WARNING",
            max_local_subsidy_krw=4_000_000,
            max_total_subsidy_krw=10_500_000,
        )
        # Subscript access
        self.assertEqual(cm["announced_units"], 100)
        self.assertEqual(cm["depletion_rate"], 80.0)

        # KeyError on missing key
        with self.assertRaises(KeyError):
            _ = cm["non_existent_field"]

        # In operator
        self.assertIn("announced_units", cm)
        self.assertNotIn("non_existent_field", cm)

        # .get()
        self.assertEqual(cm.get("announced_units"), 100)
        self.assertEqual(cm.get("non_existent_field", "default_val"), "default_val")

    def test_02_municipality_metrics_mapping_protocol(self) -> None:
        """MunicipalityMetrics raises KeyError on missing keys and implements __contains__ and .get()."""
        mm = MunicipalityMetrics(
            name_ko="수원시",
            announced_units=500,
            applied_units=450,
            remaining_units=50,
            depletion_rate=90.0,
            status="CRITICAL",
        )
        self.assertEqual(mm["name_ko"], "수원시")
        with self.assertRaises(KeyError):
            _ = mm["invalid_attribute"]
        self.assertIn("name_ko", mm)
        self.assertNotIn("invalid_attribute", mm)
        self.assertEqual(mm.get("invalid_attribute", 42), 42)

    def test_03_complaint_record_and_daily_report_payload_mapping_protocol(self) -> None:
        """ComplaintRecord and DailyReportPayload support standard dictionary syntax and KeyError."""
        record = ComplaintRecord(
            id="CR_01",
            source="dcinside",
            url="https://gall.dcinside.com/1",
            title="EV6 단차 누수",
            author="익명",
            created_at="2026-10-25",
            vehicle_brand="Kia",
            vehicle_model="EV6",
            defect_category="BUILD_QUALITY",
            summary="트렁크 단차 누수",
            verbatim_quote="비오는 날 트렁크 열었더니 물이 고여있네요.",
        )
        self.assertEqual(record["id"], "CR_01")
        self.assertEqual(record["date"], "2026-10-25")
        self.assertEqual(record["raw_quote"], "비오는 날 트렁크 열었더니 물이 고여있네요.")
        with self.assertRaises(KeyError):
            _ = record["non_existent_key"]
        self.assertIn("date", record)
        self.assertNotIn("non_existent_key", record)
        self.assertIsNone(record.get("non_existent_key"))

        payload = DailyReportPayload(
            generated_at="2026-10-25T12:00:00Z",
            reports=[record.to_admin_report_dict()],
        )
        self.assertEqual(payload["generated_at"], "2026-10-25T12:00:00Z")
        self.assertEqual(len(payload["reports"]), 1)
        with self.assertRaises(KeyError):
            _ = payload["non_existent_payload_key"]
        self.assertIn("reports", payload)
        self.assertNotIn("non_existent_payload_key", payload)

    def test_04_daily_report_statistics_nan_inf_safety(self) -> None:
        """DailyReportStatistics.to_dict safely converts NaN and Inf to 0.0."""
        stats_nan = DailyReportStatistics(
            total_scraped=100,
            total_filtered_defects=5,
            avg_negativity_score=float("nan"),
            critical_defect_count=1,
        )
        d_nan = stats_nan.to_dict()
        self.assertEqual(d_nan["avg_negativity_score"], 0.0)

        stats_inf = DailyReportStatistics(
            total_scraped=100,
            total_filtered_defects=5,
            avg_negativity_score=float("inf"),
            critical_defect_count=1,
        )
        d_inf = stats_inf.to_dict()
        self.assertEqual(d_inf["avg_negativity_score"], 0.0)


class TestAtomicWriterDurabilityAndConcurrency(unittest.TestCase):
    """Part 5: Atomic writer fault injection, multi-threaded concurrency, and serialization guarantees."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.target_file = Path(self.temp_dir.name) / "test_atomic.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_01_atomic_write_json_decimal_path_datetime_serialization(self) -> None:
        """atomic_write_json serializes Decimal, Path, datetime, set, and Enum without error."""
        class TestTier(Enum):
            ALPHA = "alpha"

        data = {
            "decimal_val": Decimal("123.456"),
            "path_val": Path("/var/log/test"),
            "dt_val": datetime.datetime(2026, 10, 25, 12, 0, 0, tzinfo=datetime.timezone.utc),
            "date_val": datetime.date(2026, 10, 25),
            "set_val": {"apple", "banana"},
            "enum_val": TestTier.ALPHA,
            "nan_val": float("nan"),
            "inf_val": float("inf"),
        }
        written = atomic_write_json(data, self.target_file)
        self.assertTrue(written.exists())

        with open(written, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        self.assertEqual(loaded["decimal_val"], 123.456)
        self.assertEqual(loaded["path_val"], "/var/log/test")
        self.assertIn("2026-10-25", loaded["dt_val"])
        self.assertEqual(loaded["date_val"], "2026-10-25")
        self.assertEqual(set(loaded["set_val"]), {"apple", "banana"})
        self.assertEqual(loaded["enum_val"], "alpha")
        self.assertEqual(loaded["nan_val"], 0.0)
        self.assertEqual(loaded["inf_val"], 0.0)

    def test_02_atomic_write_json_empty_path_raises_value_error(self) -> None:
        """atomic_write_json raises ValueError on empty or whitespace-only target path."""
        with self.assertRaises(ValueError):
            atomic_write_json({"data": 1}, "")
        with self.assertRaises(ValueError):
            atomic_write_json({"data": 1}, "   ")

    def test_03_atomic_write_unserializable_object_leaves_target_intact(self) -> None:
        """atomic_write_json leaves existing file intact and removes temp file if serialization fails."""
        # Initial valid write
        atomic_write_json({"initial": "intact"}, self.target_file)
        self.assertTrue(self.target_file.exists())

        # Attempt to write unserializable object
        with self.assertRaises(TypeError):
            atomic_write_json({"bad": lambda x: x}, self.target_file)

        # Confirm target file still exists and contains initial data
        with open(self.target_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        self.assertEqual(loaded, {"initial": "intact"})

        # Confirm no temporary files are left behind
        temp_files = [p for p in Path(self.temp_dir.name).glob(".tmp_subsidy_*")]
        self.assertEqual(len(temp_files), 0)

    def test_04_multi_threaded_concurrent_atomic_writes(self) -> None:
        """10 threads concurrently writing to the same destination never corrupt JSON syntax."""
        errors: List[str] = []

        def worker(worker_id: int) -> None:
            for i in range(15):
                payload = {
                    "worker_id": worker_id,
                    "iteration": i,
                    "timestamp": time.time(),
                    "items": list(range(20)),
                }
                try:
                    atomic_write_json(payload, self.target_file)
                    # Verify readable
                    with open(self.target_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if not isinstance(data, dict) or "worker_id" not in data:
                            errors.append(f"Invalid read: {data}")
                except Exception as ex:
                    errors.append(f"Worker {worker_id} crashed: {ex}")
                time.sleep(0.002)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent atomic writes failed: {errors}")


class TestEmpiricalChallengerFindingsAndVulnerabilities(unittest.TestCase):
    """Part 6: Empirical documentation and verification of known vulnerabilities and edge cases."""

    def test_01_crawler_date_normalization_unhandled_value_error(self) -> None:
        """REMEDIATED: BobaeDreamCrawler and DCInsideCrawler safely handle
        out-of-range numerical dates/times (e.g. '99.99', '25:00', '2026-02-31')
        without raising unhandled ValueError, falling back gracefully to current ISO time.
        """
        bobae = BobaeDreamCrawler()
        dc = DCInsideCrawler()

        # Out-of-range month/day
        malformed_html = '<td class="date">99.99</td><strong class="title">제목</strong>'
        res_b = bobae.parse_post_detail(malformed_html, "https://www.bobaedream.co.kr/view?No=123")
        self.assertIn("created_at", res_b)
        self.assertIsInstance(res_b["created_at"], str)

        malformed_dc_list = (
            '<table><tr class="ub-content us-post" data-no="999">'
            '<td class="gall_tit ub-word"><a href="/board/view/?id=car_new1&no=999">제목</a></td>'
            '<td class="gall_date" title="2026-99-99 12:00:00">12:00</td>'
            '</tr></table>'
        )
        posts = dc.parse_gallery_list(malformed_dc_list, "car_new1")
        self.assertEqual(len(posts), 1)
        self.assertIsInstance(posts[0]["created_at"], str)

    def test_02_case_insensitivity_of_crawler_post_id_regex(self) -> None:
        """Post ID regex matching handles uppercase query parameters (NO=12345)."""
        bobae = BobaeDreamCrawler()
        res_upper = bobae.parse_post_detail(
            "<html><strong class='title'>제목</strong></html>",
            "https://www.bobaedream.co.kr/view?code=national&NO=998877",
        )
        self.assertEqual(res_upper["post_id"], "998877")

    def test_03_symlink_path_resolution_deduplication(self) -> None:
        """Path.resolve ensures identical physical files behind symlinks are not duplicated."""
        p1 = Path("/tmp")
        p2 = Path("/private/tmp")
        # On macOS, /tmp is a symlink to /private/tmp
        self.assertEqual(p1.resolve(), p2.resolve())

    def test_04_normalize_iso_timestamp_safe_fallback_on_malformed_values(self) -> None:
        """_normalize_iso_timestamp in both crawlers safely falls back on malformed times and dates."""
        from crawlers.bobaedream import _normalize_iso_timestamp as b_norm
        from crawlers.dcinside import _normalize_iso_timestamp as d_norm

        malformed_cases = [
            "99:99",
            "25:00",
            "12:99:99",
            "2026-02-31",
            "2026-99-99",
            "2026-00-00",
            "99.99",
            "13/32",
            "99/99/99",
            "invalid_date_str",
            "",
            "   ",
        ]
        for c in malformed_cases:
            with self.subTest(case=c):
                res_b = b_norm(c)
                res_d = d_norm(c)
                self.assertIsInstance(res_b, str)
                self.assertIsInstance(res_d, str)
                datetime.datetime.fromisoformat(res_b)
                datetime.datetime.fromisoformat(res_d)

    def test_05_ts_get_region_by_id_prototype_collision_guard(self) -> None:
        """TypeScript getRegionById safely returns undefined for Object.prototype property names."""
        import subprocess

        ts_test_script = (
            "import * as m from './src/lib/getSubsidyData';"
            "const props = ['constructor', 'toString', 'valueOf', '__proto__', '__defineGetter__'];"
            "const results = props.map(p => m.getRegionById(p));"
            "const safe = results.every(r => r === undefined);"
            "if (!safe) throw new Error('Unsafe prototype collision: ' + JSON.stringify(results));"
        )
        cmd = ["npx", "tsx", "-e", ts_test_script]
        proc = subprocess.run(cmd, cwd=str(WEB_ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"TypeScript prototype guard failed: {proc.stderr}")

    def test_06_ts_get_price_subsidy_ratio_parity_with_backend(self) -> None:
        """TypeScript getPriceSubsidyRatio exhibits 100% parity with Python calculate_price_cap_ratio on non-positive/invalid inputs."""
        import subprocess

        ts_test_script = (
            "import * as m from './src/lib/getSubsidyData';"
            "const cases = [-1, -50000000, 0, NaN, Infinity, -Infinity];"
            "const results = cases.map(c => m.getPriceSubsidyRatio(c));"
            "console.log(JSON.stringify(results));"
        )
        cmd = ["npx", "tsx", "-e", ts_test_script]
        proc = subprocess.run(cmd, cwd=str(WEB_ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"TypeScript parity run failed: {proc.stderr}")
        ts_results = json.loads(proc.stdout.strip())

        cases = [-1, -50000000, 0, float("nan"), float("inf"), float("-inf")]
        for val, ts_res in zip(cases, ts_results):
            py_res = tracker_price_cap_ratio(val)
            self.assertEqual(ts_res, 0.0, f"TypeScript ratio for {val} must be 0.0")
            self.assertEqual(py_res, 0.0, f"Python ratio for {val} must be 0.0")


if __name__ == "__main__":
    unittest.main()
