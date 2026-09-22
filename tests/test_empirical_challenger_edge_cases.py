#!/usr/bin/env python3
"""
Empirical Adversarial Edge Cases & Stress Test Suite
===================================================
Author: challenger_api_edge_cases (Empirical Challenger)

Rigorous empirical challenge and stress test harness covering:
1. Corrupted, malformed, empty, and huge HTML payloads into BaseCrawler,
   BobaeDreamCrawler.parse_post_detail(), and DCInsideCrawler.parse_post_detail().
2. Extreme text payloads with Korean automotive slang, special Unicode emojis
   (astral plane, ZWJ, RTL overrides, null bytes, NFD Hangul), and massive repetitive
   strings into ContextualDefectFilter and VehicleMatcher (verifying ReDoS resilience
   and crash-free operation).
3. HTTP 429 response simulation with RFC 9110 HTTP-date and delay-seconds Retry-After
   headers, verifying backoff calculation, clamping, and zero ResourceWarnings.
4. Atomic writing of daily_reports.json under simulated disk flush failures, ENOSPC,
   KeyboardInterrupt, and concurrent read/write race condition verification.
5. Empirical Vulnerability Findings: Unhandled exceptions exposed under specific edge cases:
   - Out-of-range timestamps in HTML (ValueError: month/hour out of range)
   - None inputs to VehicleMatcher and DefectFilter (TypeError)
   - IEEE 754 NaN float leakage producing non-standard JSON breaking JavaScript parsers
"""

from __future__ import annotations

import datetime
import email.utils
import errno
import html
import io
import json
import logging
import math
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import urllib.request
import warnings

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
ROOT_FOR_IMPORTS = PROJECT_ROOT.parent if (PROJECT_ROOT.parent / "crawlers").exists() else PROJECT_ROOT
if str(ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(ROOT_FOR_IMPORTS))

from crawlers.base_crawler import BaseCrawler
from crawlers.bobaedream import BobaeDreamCrawler
from crawlers.dcinside import DCInsideCrawler
from filters.defect_filter import ContextualDefectFilter
from filters.vehicle_matcher import (
    BRAND_BYD,
    BRAND_HYUNDAI,
    BRAND_KIA,
    BRAND_OTHER,
    BRAND_TESLA,
    extract_vehicle_info,
)
from models.complaint import ComplaintRecord, RawPost
from utils.http_client import SafeHttpClient, clean_html_text, robust_decode
from utils.json_writer import (
    DEFAULT_OUTPUT_PATH,
    format_daily_report_payload,
    read_daily_reports,
    write_daily_reports,
)


class TestCrawlerCorruptedHTMLPayloads(unittest.TestCase):
    """Adversarial stress tests feeding corrupted, broken, or empty HTML payloads

    into BaseCrawler, BobaeDreamCrawler, and DCInsideCrawler.
    """

    def setUp(self):
        logging.getLogger("SafeHttpClient").setLevel(logging.CRITICAL)
        logging.getLogger("BobaeDreamCrawler").setLevel(logging.CRITICAL)
        logging.getLogger("DCInsideCrawler").setLevel(logging.CRITICAL)
        logging.getLogger("BaseCrawler").setLevel(logging.CRITICAL)

        self.bobae = BobaeDreamCrawler()
        self.dc = DCInsideCrawler()

    def test_01_empty_and_whitespace_html_payloads(self):
        """Verify crawlers return valid schema dict without crashing on empty/whitespace HTML."""
        empty_inputs = ["", "   ", "\t\n\r  \n", "\u00a0\u200b\u3000"]
        for payload in empty_inputs:
            # BobaeDream
            res_b = self.bobae.parse_post_detail(
                payload, "https://www.bobaedream.co.kr/view?code=national&No=12345"
            )
            self.assertIsInstance(res_b, dict)
            self.assertEqual(res_b["platform"], "bobaedream")
            self.assertEqual(res_b["post_id"], "12345")
            self.assertEqual(res_b["title"], "")
            self.assertEqual(res_b["content"], "")
            self.assertEqual(res_b["comments"], [])
            self.assertTrue(len(res_b["created_at"]) > 0)

            # DCInside
            res_d = self.dc.parse_post_detail(
                payload, "https://gall.dcinside.com/board/view/?id=car_new1&no=67890"
            )
            self.assertIsInstance(res_d, dict)
            self.assertEqual(res_d["platform"], "dcinside")
            self.assertEqual(res_d["post_id"], "67890")
            self.assertEqual(res_d["title"], "")
            self.assertEqual(res_d["content"], "")
            self.assertEqual(res_d["comments"], [])
            self.assertTrue(len(res_d["created_at"]) > 0)

    def test_02_severely_malformed_and_truncated_tags(self):
        """Verify crawlers handle unclosed tags, broken quotes, and tag soup gracefully."""
        corrupted_payloads = [
            "<<<<html>>>><<<div class=\"bodyCont\">broken body without closure",
            "<strong class=\"title\">Unfinished title <div class=\"bodyCont\">Nested body without end",
            "<div class=\"write_div\"><script>alert('xss');</script><style>body{color:red}</style>Content</div>",
            "<a href=\"view?code=national&No=999\">Unclosed link in table",
            "<!-- Unclosed comment with bodyCont <div class=\"bodyCont\">text</div>",
            "<!DOCTYPE html><html><head><title>Test</title></head><body><div id=\"unrelated\">No target tags</div></body></html>",
            "<strong class=\"title\"><span class=\"nested\">Title with <b>heavy</b> tags</span></strong><div class=\"bodyCont\">Body with <img src=\"foo.jpg\" onerror=\"alert(1)\"></div>",
            "<tr class=\"ub-content\" data-no=\"123\"><td class=\"gall_tit\">No anchor tag here</td></tr>",
            "<input type=\"hidden\" id=\"e_s_n_o\" value=\"\">",
            "<input type=\"hidden\" name=\"e_s_n_o\" value=\"token_without_id_attr\">",
        ]

        for payload in corrupted_payloads:
            res_b = self.bobae.parse_post_detail(
                payload, "https://www.bobaedream.co.kr/view?code=national&No=11111"
            )
            self.assertIsInstance(res_b, dict)
            self.assertEqual(res_b["post_id"], "11111")
            self.assertIsInstance(res_b["comments"], list)

            res_d = self.dc.parse_post_detail(
                payload, "https://gall.dcinside.com/board/view/?id=car_new1&no=22222"
            )
            self.assertIsInstance(res_d, dict)
            self.assertEqual(res_d["post_id"], "22222")
            self.assertIsInstance(res_d["comments"], list)

    def test_03_deeply_nested_tags_and_regex_recursion(self):
        """Stress test deep nesting (5,000 unclosed tags) to verify no regex recursion limits or crashes."""
        deep_nesting = "<div>" * 5000 + "<strong class=\"title\">Deep Title</strong><div class=\"bodyCont\">Deep Body</div>" + "</div>" * 5000
        start = time.monotonic()
        res_b = self.bobae.parse_post_detail(
            deep_nesting, "https://www.bobaedream.co.kr/view?code=national&No=55555"
        )
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 2.0, f"Parsing deeply nested tags took too long: {elapsed:.2f}s")
        self.assertIn("Deep Title", res_b["title"])
        self.assertIn("Deep Body", res_b["content"])

    def test_04_binary_null_bytes_and_invalid_bytes(self):
        """Verify binary data, null bytes, and non-ASCII control characters do not raise exceptions."""
        binary_payload = "<html>\x00\x01\x02<strong class=\"title\">Title\x00With\x00Nulls</strong><div class=\"bodyCont\">Body\x00\x1fWith\x7fNulls</div></html>"
        res_b = self.bobae.parse_post_detail(
            binary_payload, "https://www.bobaedream.co.kr/view?code=national&No=77777"
        )
        self.assertIsInstance(res_b, dict)
        self.assertIn("Title", res_b["title"])
        self.assertIn("Body", res_b["content"])

    def test_05_base_crawler_fetch_post_safety_wrapper(self):
        """Verify BaseCrawler.fetch_post catches all exceptions from parse_post_detail and returns None."""
        class ExplodingCrawler(BaseCrawler):
            def parse_post_detail(self, html_content: str, post_url: str, **kwargs):
                raise ValueError("Simulated catastrophic DOM explosion!")

        mock_client = MagicMock(spec=SafeHttpClient)
        mock_client.get.return_value = (200, "<html>Boom</html>", b"<html>Boom</html>")
        mock_client.warm_up_session.return_value = True

        crawler = ExplodingCrawler(client=mock_client)
        result = crawler.fetch_post("https://example.com/exploding_post")
        self.assertIsNone(result, "fetch_post must return None when parse_post_detail raises exception")

    def test_06_corrupt_ajax_comments_handling(self):
        """Verify parsing comments from broken AJAX responses or invalid JSON handles gracefully."""
        broken_jsons = ["", "{", "null", "[]", "{\"comments\": \"not-a-list\"}", "{\"comments\": [\"string_instead_of_dict\", null, 123]}"]
        for bj in broken_jsons:
            comments = self.dc.parse_comment_json(bj)
            self.assertIsInstance(comments, list)

        broken_htmls = ["", "<dd>no class</dd>", "<dd class=\"comment\">", "<dd class=\"comment\"><a href=\"#\">신고</a></dd>"]
        for bh in broken_htmls:
            comments = self.bobae.parse_comments_html(bh)
            self.assertIsInstance(comments, list)


class TestExtremeTextAndNLPStress(unittest.TestCase):
    """Adversarial stress tests for ContextualDefectFilter and VehicleMatcher

    with massive text repetitions (ReDoS audit), Unicode edge cases, and extreme Korean slang.
    """

    def setUp(self):
        self.filter = ContextualDefectFilter()

    def test_01_massive_repetitive_tokens_redos_audit(self):
        """Verify VehicleMatcher and DefectFilter do not suffer catastrophic backtracking on massive text."""
        heavy_text = ("bmw " * 5000) + "m3 " + ("현대 " * 5000) + "아이오닉 5 N " + ("ㅋㅋㅋㅋ " * 10000)
        start = time.monotonic()
        brand, model = extract_vehicle_info(heavy_text[:200], heavy_text)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 1.5, f"VehicleMatcher took {elapsed:.2f}s on heavy text (potential ReDoS)")
        self.assertIn(brand, [BRAND_HYUNDAI, BRAND_OTHER, BRAND_TESLA])

        massive_post = RawPost(
            platform="bobaedream",
            post_id="massive_01",
            url="https://www.bobaedream.co.kr/view?code=national&No=9999",
            title="내 아이오닉5 배터리 단차 고장 " + ("단차 " * 500),
            content="내 차 출고했는데 " + ("ICCU 폭탄 터짐 퍽 소리 나고 멈춤 " * 300) + ("ㅋㅋㅋㅋ " * 1000),
            comments=["댓글 " * 50] * 20,
            created_at="2026-09-08T12:00:00Z",
            author="heavy_user",
        )
        start = time.monotonic()
        record = self.filter.process_post(massive_post)
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 2.0, f"DefectFilter took {elapsed:.2f}s on massive post (potential ReDoS)")
        self.assertIsInstance(record, ComplaintRecord)
        self.assertTrue(record.is_authentic_defect)

    def test_02_special_unicode_and_astral_emojis(self):
        """Stress test with astral plane emojis, ZWJ sequences, RTL overrides, and null characters."""
        unicode_adversarial_strings = [
            "🚨💥🚗⚡️🔥 내 차 테슬라 모델Y 주행 중 퍽 소리 나고 멈춤 💀😱",
            "아이오닉5 \u200e\u200f\u202a\u202eRTL_OVERRIDE ICCU 터짐 황천길 갈 뻔",
            "내 차 캐스퍼 일렉트릭 👨‍👩‍👧‍👦 가족 태우고 가다가 동력 상실 발생 ⚡️",
            "내 EV6 \x00\x01\x02 배터리 방전 먹통 견인차 부름 ㅠㅠ",
            "내 차 테슬라 모델3 \u0300\u0301\u0302\u0303\u0304 결함 심각",
            "내 차\ufeff\u200b\u200c\u200d\u2060 BYD 아토3 배터리 불쇼 에디션",
        ]

        for text in unicode_adversarial_strings:
            brand, model = extract_vehicle_info(text)
            self.assertIn(brand, [BRAND_TESLA, BRAND_HYUNDAI, BRAND_KIA, BRAND_BYD, BRAND_OTHER])
            post = RawPost(
                platform="dcinside",
                post_id="unicode_test",
                url="https://gall.dcinside.com/board/view/?id=car_new1&no=123",
                title=text,
                content=text,
                comments=[],
                created_at="2026-09-08T12:00:00Z",
                author="unicode_tester",
            )
            record = self.filter.process_post(post)
            self.assertIsInstance(record, ComplaintRecord)

    def test_03_nfd_hangul_normalization_resilience(self):
        """Verify behavior on decomposed Hangul (NFD, common in macOS clipboard/filesystems)."""
        nfc_text = "내 아이오닉5 출고했는데 ICCU 터져서 황천길 갈 뻔"
        nfd_text = unicodedata.normalize("NFD", nfc_text)

        brand_nfd, model_nfd = extract_vehicle_info(nfd_text)
        self.assertIsInstance(brand_nfd, str)
        self.assertIsInstance(model_nfd, str)

        post_nfd = RawPost(
            platform="dcinside",
            post_id="nfd_test",
            url="https://gall.dcinside.com/board/view/?id=car_new1&no=124",
            title=nfd_text,
            content=nfd_text,
            comments=[],
            created_at="2026-09-08T12:00:00Z",
            author="nfd_tester",
        )
        record_nfd = self.filter.process_post(post_nfd)
        self.assertIsInstance(record_nfd, ComplaintRecord)

    def test_04_dense_unspaced_korean_slang(self):
        """Verify highly compressed Korean text without spaces is parsed without error."""
        dense_text = "내차아이오닉5iccu폭탄터짐황천길갈뻔핸들잠기고동력상실블루핸즈입고함"
        brand, model = extract_vehicle_info(dense_text)
        self.assertEqual(brand, BRAND_HYUNDAI)
        self.assertEqual(model, "아이오닉5")

        post = RawPost(
            platform="dcinside",
            post_id="dense_test",
            url="https://gall.dcinside.com/board/view/?id=car_new1&no=125",
            title=dense_text,
            content=dense_text,
            comments=[],
            created_at="2026-09-08T12:00:00Z",
            author="dense_tester",
        )
        record = self.filter.process_post(post)
        self.assertIsInstance(record, ComplaintRecord)
        self.assertTrue(record.is_authentic_defect)


class TestHttp429AndRFC9110Backoff(unittest.TestCase):
    """Adversarial testing of HTTP 429 Retry-After header parsing (RFC 9110),

    exponential backoff calculations, and ResourceWarning verification.
    """

    def setUp(self):
        logging.getLogger("SafeHttpClient").setLevel(logging.CRITICAL)
        self.client_no_jitter = SafeHttpClient(enable_jitter=False)
        self.client_with_jitter = SafeHttpClient(enable_jitter=True)

    def _create_mock_http_error(self, code: int, headers_dict: Dict[str, str]) -> urllib.error.HTTPError:
        headers_msg = email.message_from_string(
            "\n".join(f"{k}: {v}" for k, v in headers_dict.items()) + "\n\n"
        )
        fp = io.BytesIO(b"Too Many Requests")
        return urllib.error.HTTPError(
            url="https://example.com/test",
            code=code,
            msg="Too Many Requests",
            hdrs=headers_msg,
            fp=fp,
        )

    def test_01_retry_after_delay_seconds(self):
        """Verify numeric delay-seconds in Retry-After header are correctly parsed."""
        he_int = self._create_mock_http_error(429, {"Retry-After": "120"})
        parsed = self.client_no_jitter._parse_retry_after(he_int)
        he_int.close()
        self.assertEqual(parsed, 120.0)

        he_float = self._create_mock_http_error(429, {"Retry-After": "15.5"})
        parsed = self.client_no_jitter._parse_retry_after(he_float)
        he_float.close()
        self.assertEqual(parsed, 15.5)

        he_zero = self._create_mock_http_error(429, {"Retry-After": "0"})
        parsed = self.client_no_jitter._parse_retry_after(he_zero)
        he_zero.close()
        self.assertEqual(parsed, 0.0)

        he_neg = self._create_mock_http_error(429, {"Retry-After": "-10"})
        parsed = self.client_no_jitter._parse_retry_after(he_neg)
        he_neg.close()
        self.assertIsNone(parsed)

    def test_02_retry_after_rfc9110_http_date(self):
        """Verify RFC 9110 IMF-fixdate format is parsed to delta seconds."""
        now = datetime.datetime.now(datetime.timezone.utc)
        future_dt = now + datetime.timedelta(seconds=45)
        imf_fixdate = email.utils.format_datetime(future_dt)

        he_date = self._create_mock_http_error(429, {"Retry-After": imf_fixdate})
        parsed = self.client_no_jitter._parse_retry_after(he_date)
        he_date.close()

        self.assertIsNotNone(parsed)
        self.assertAlmostEqual(parsed, 45.0, delta=3.0)

        past_dt = now - datetime.timedelta(seconds=100)
        past_fixdate = email.utils.format_datetime(past_dt)
        he_past = self._create_mock_http_error(429, {"Retry-After": past_fixdate})
        parsed_past = self.client_no_jitter._parse_retry_after(he_past)
        he_past.close()

        self.assertIsNotNone(parsed_past)
        self.assertEqual(parsed_past, 0.0)

    def test_03_retry_after_malformed_headers(self):
        """Verify garbage/corrupted Retry-After headers fall back gracefully to None."""
        malformed_values = [
            "",
            "   ",
            "Wed, Invalid Month 2026 99:99:99 GMT",
            "not-a-number-or-date",
            "999999999999999999999999999999999999999999999999999999",
            ";;;",
            "\x00\x01\x02",
        ]
        for val in malformed_values:
            he = self._create_mock_http_error(429, {"Retry-After": val})
            parsed = self.client_no_jitter._parse_retry_after(he)
            he.close()
            if val in ["", "   ", "Wed, Invalid Month 2026 99:99:99 GMT", "not-a-number-or-date", ";;;", "\x00\x01\x02"]:
                self.assertIsNone(parsed, f"Malformed value '{val}' should parse to None")

    def test_04_calc_backoff_bounding_and_jitter(self):
        """Verify exponential backoff calculation and cap bounds."""
        b1 = self.client_no_jitter._calc_backoff(1)
        self.assertEqual(b1, 2.0)
        b2 = self.client_no_jitter._calc_backoff(2)
        self.assertEqual(b2, 4.0)
        b3 = self.client_no_jitter._calc_backoff(3)
        self.assertEqual(b3, 8.0)

        b_ra = self.client_no_jitter._calc_backoff(1, retry_after=12.5)
        self.assertEqual(b_ra, 12.5)

        b_ra_huge = self.client_with_jitter._calc_backoff(1, retry_after=3600.0)
        self.assertEqual(b_ra_huge, 60.0)

    def test_05_http429_request_retry_loop_and_resource_warnings(self):
        """Simulate HTTP 429 response loop and verify zero ResourceWarnings."""
        with warnings.catch_warnings(record=True) as recorded_warnings:
            warnings.simplefilter("always", ResourceWarning)

            mock_opener = MagicMock()
            def mock_open_side_effect(req, timeout):
                raise self._create_mock_http_error(429, {"Retry-After": "0.01"})

            mock_opener.open.side_effect = mock_open_side_effect

            client = SafeHttpClient(
                max_retries=2,
                enable_jitter=False,
                opener=mock_opener,
            )

            logging.getLogger("SafeHttpClient").setLevel(logging.CRITICAL)

            status, text, raw = client.request("https://example.com/test_429")
            self.assertEqual(status, 429)

            res_warnings = [w for w in recorded_warnings if issubclass(w.category, ResourceWarning)]
            self.assertEqual(
                len(res_warnings),
                0,
                f"Expected 0 ResourceWarnings, but got: {[str(w.message) for w in res_warnings]}",
            )


class TestAtomicWritingAndInterruption(unittest.TestCase):
    """Adversarial stress testing of atomic daily_reports.json serialization."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.target_json = os.path.join(self.temp_dir.name, "daily_reports.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _generate_sample_complaints(self, count: int = 5) -> List[ComplaintRecord]:
        complaints = []
        for i in range(count):
            complaints.append(
                ComplaintRecord(
                    id=f"test_id_{i}",
                    source="bobaedream",
                    url=f"https://www.bobaedream.co.kr/view?code=national&No={i}",
                    title=f"아이오닉5 결함 테스트 {i}",
                    author=f"user_{i}",
                    created_at="2026-09-08T12:00:00Z",
                    vehicle_brand="Hyundai",
                    vehicle_model="아이오닉5",
                    defect_category="BATTERY_CHARGING",
                    summary=f"요약 {i}",
                    verbatim_quote=f"배터리 충전 불량 발생 {i}",
                    slang_terms_detected=["ICCU"],
                    sentiment_polarity=-0.8,
                    negativity_score=0.9,
                    severity_index=7.5,
                    is_authentic_defect=True,
                )
            )
        return complaints

    def test_01_atomic_write_success_and_valid_json(self):
        """Verify normal write creates valid, non-empty, formatted JSON file."""
        complaints = self._generate_sample_complaints(3)
        written_path = write_daily_reports(complaints, output_path=self.target_json)
        self.assertTrue(os.path.exists(written_path))

        data = read_daily_reports(written_path)
        self.assertIn("statistics", data)
        self.assertIn("reports", data)
        self.assertEqual(len(data["reports"]), 3)

    def test_02_simulated_disk_full_enospc_during_flush(self):
        """Verify ENOSPC leaves original file untouched and cleans temp file."""
        initial_complaints = self._generate_sample_complaints(2)
        write_daily_reports(initial_complaints, output_path=self.target_json)
        initial_data = read_daily_reports(self.target_json)

        with patch("os.fsync", side_effect=OSError(errno.ENOSPC, "No space left on device")):
            with self.assertRaises(OSError):
                write_daily_reports(self._generate_sample_complaints(10), output_path=self.target_json)

        self.assertTrue(os.path.exists(self.target_json))
        surviving_data = read_daily_reports(self.target_json)
        self.assertEqual(len(surviving_data["reports"]), 2)
        self.assertEqual(initial_data, surviving_data)

        remaining_files = os.listdir(self.temp_dir.name)
        self.assertEqual(remaining_files, ["daily_reports.json"])

    def test_03_simulated_keyboard_interrupt_during_serialization(self):
        """Verify KeyboardInterrupt during json.dump leaves original file untouched."""
        write_daily_reports(self._generate_sample_complaints(2), output_path=self.target_json)
        initial_data = read_daily_reports(self.target_json)

        with patch("json.dump", side_effect=KeyboardInterrupt("Simulated user interrupt")):
            with self.assertRaises(KeyboardInterrupt):
                write_daily_reports(self._generate_sample_complaints(10), output_path=self.target_json)

        surviving_data = read_daily_reports(self.target_json)
        self.assertEqual(len(surviving_data["reports"]), 2)
        self.assertEqual(initial_data, surviving_data)
        remaining_files = os.listdir(self.temp_dir.name)
        self.assertEqual(remaining_files, ["daily_reports.json"])

    def test_04_simulated_os_replace_failure(self):
        """Verify atomic replace failure leaves original file intact and removes temp file."""
        write_daily_reports(self._generate_sample_complaints(2), output_path=self.target_json)
        initial_data = read_daily_reports(self.target_json)

        with patch("os.replace", side_effect=PermissionError("Simulated permission error on rename")):
            with self.assertRaises(PermissionError):
                write_daily_reports(self._generate_sample_complaints(10), output_path=self.target_json)

        surviving_data = read_daily_reports(self.target_json)
        self.assertEqual(len(surviving_data["reports"]), 2)
        self.assertEqual(initial_data, surviving_data)
        remaining_files = os.listdir(self.temp_dir.name)
        self.assertEqual(remaining_files, ["daily_reports.json"])

    def test_05_concurrent_reader_never_reads_partial_json(self):
        """Verify that concurrent readers never encounter partially written or corrupted JSON."""
        write_daily_reports(self._generate_sample_complaints(2), output_path=self.target_json)

        stop_event = threading.Event()
        read_errors = []
        read_counts = [0]

        def reader_worker():
            while not stop_event.is_set():
                try:
                    data = read_daily_reports(self.target_json)
                    if "reports" not in data or not isinstance(data["reports"], list):
                        read_errors.append("Invalid structure")
                    read_counts[0] += 1
                except Exception as ex:
                    read_errors.append(f"Exception while reading: {ex}")
                time.sleep(0.001)

        reader_thread = threading.Thread(target=reader_worker)
        reader_thread.daemon = True
        reader_thread.start()

        for i in range(25):
            complaints = self._generate_sample_complaints(random.randint(1, 10))
            write_daily_reports(complaints, output_path=self.target_json, merge_existing=False)
            time.sleep(0.005)

        stop_event.set()
        reader_thread.join(timeout=2.0)

        self.assertEqual(len(read_errors), 0, f"Reader encountered corrupt reads: {read_errors}")
        self.assertGreater(read_counts[0], 10, "Reader should have performed multiple successful reads")

    def test_06_resilience_to_preexisting_corrupted_file(self):
        """Verify write_daily_reports recovers cleanly if the target file was previously truncated/corrupted."""
        with open(self.target_json, "w", encoding="utf-8") as f:
            f.write("{\"statistics\": {\"total_scraped\": 50, \"reports\": [{\"id\": \"incomplete")

        complaints = self._generate_sample_complaints(3)
        written_path = write_daily_reports(complaints, output_path=self.target_json, merge_existing=True)

        self.assertTrue(os.path.exists(written_path))
        data = read_daily_reports(written_path)
        self.assertEqual(len(data["reports"]), 3)
        self.assertEqual(data["statistics"]["total_filtered_defects"], 3)


class TestEmpiricalVulnerabilityFindings(unittest.TestCase):
    """Empirical demonstration and verification of latent bugs uncovered

    during edge-case stress testing.
    """

    def setUp(self):
        logging.getLogger("SafeHttpClient").setLevel(logging.CRITICAL)
        logging.getLogger("BobaeDreamCrawler").setLevel(logging.CRITICAL)
        logging.getLogger("DCInsideCrawler").setLevel(logging.CRITICAL)
        self.bobae = BobaeDreamCrawler()
        self.dc = DCInsideCrawler()
        self.filter = ContextualDefectFilter()

    def test_finding_01_crawler_date_normalization_unhandled_value_error(self):
        """EMPIRICAL FINDING 1: _normalize_iso_timestamp raises unhandled ValueError

        on out-of-range numerical dates/times (e.g. '99.99', '25:00', '2026-02-31').
        When an unhandled date appears in HTML, parse_post_detail crashes.
        """
        malformed_date_html = """
        <strong class="title">아이오닉5 고장</strong>
        <td class="date">99.99</td>
        <div class="bodyCont">배터리 ICCU 터짐</div>
        """
        with self.assertRaises(ValueError) as cm:
            self.bobae.parse_post_detail(malformed_date_html, "https://www.bobaedream.co.kr/view?code=national&No=123")
        self.assertIn("month must be in 1..12", str(cm.exception))

        malformed_list_html = """
        <table>
          <tr class="ub-content us-post" data-no="999">
            <td class="gall_tit ub-word"><a href="/board/view/?id=car_new1&no=999">제목</a></td>
            <td class="gall_date" title="2026-99-99 12:00:00">12:00</td>
          </tr>
        </table>
        """
        with self.assertRaises(ValueError) as cm2:
            self.dc.parse_gallery_list(malformed_list_html, "car_new1")
        self.assertIn("month must be in 1..12", str(cm2.exception))

    def test_finding_02_vehicle_matcher_type_error_on_none_title(self):
        """EMPIRICAL FINDING 2: VehicleMatcher.extract_vehicle_info crashes with TypeError

        when passed title=None because it calls pattern.search(title) without str() coercion.
        """
        with self.assertRaises(TypeError) as cm:
            extract_vehicle_info(None, "본문 내용")
        self.assertIn("expected string or bytes-like object", str(cm.exception))

    def test_finding_03_defect_filter_type_error_on_none_in_comments(self):
        """EMPIRICAL FINDING 3: ContextualDefectFilter.process_post crashes with TypeError

        when post.comments contains a None element (' '.join(post.comments) fails).
        """
        post_with_none_comment = RawPost(
            platform="dcinside",
            post_id="test_none",
            url="https://example.com/test",
            title="아이오닉5 고장",
            content="내 차 결함 발생",
            comments=[None],
            created_at="2026-09-08T00:00:00Z",
            author="tester",
        )
        with self.assertRaises(TypeError) as cm:
            self.filter.process_post(post_with_none_comment)
        self.assertIn("sequence item 0: expected str instance, NoneType found", str(cm.exception))

    def test_finding_04_json_writer_nan_inf_serialization_breaks_rfc8259(self):
        """EMPIRICAL FINDING 4: write_daily_reports produces literal NaN/Infinity tokens

        when complaint dicts contain float('nan') or float('inf'), creating invalid JSON
        that crashes Node.js / JavaScript JSON.parse().
        """
        with tempfile.TemporaryDirectory() as td:
            target_path = os.path.join(td, "daily_reports.json")
            record = {
                "id": "nan_test",
                "title": "테스트",
                "negativity_score": float("nan"),
                "severity_index": 7.5,
                "is_authentic_defect": True,
            }
            write_daily_reports([record], output_path=target_path, merge_existing=False)

            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read()

            self.assertIn("NaN", content)

            node_cmd = f"node -e 'JSON.parse(require(\"fs\").readFileSync(\"{target_path}\", \"utf8\"))'"
            proc = subprocess.run(node_cmd, shell=True, capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0, "Node.js JSON.parse should fail on NaN token")
            self.assertIn("SyntaxError", proc.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
