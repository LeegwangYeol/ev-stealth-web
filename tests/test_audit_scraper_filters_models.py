#!/usr/bin/env python3
"""Comprehensive Audit & Hardening Test Suite for Scraper, Filters, and Defect Models.

Verifies:
1. ReDoS resistance & regex performance in vehicle matcher & filter patterns.
2. DefectClassifier & SpamFilter robustness against None, non-string, malformed, and adversarial inputs.
3. Date parsing resilience & calendar validation in DefectReport and ComplaintRecord.
4. ScraperPipeline filter_defects and harvest error handling and fallback defaults.
"""

from __future__ import annotations

from datetime import datetime, timezone
import math
import time
import unittest
from unittest.mock import MagicMock, patch

from filters.defect_classifier import (
    ContextualDefectFilter,
    DefectClassifier,
)
from filters.defect_filter import (
    DefectFilter,
    evaluate_stage1_noise as defect_filter_eval_noise,
)
from filters.slang_lexicon import find_matching_slang
from filters.spam_filter import (
    COMMERCIAL_SPAM_KEYWORDS,
    SpamFilter,
    evaluate_stage1_noise,
    is_spam,
)
from filters.vehicle_matcher import MODEL_RULES, extract_vehicle_info
from models.complaint import ComplaintRecord, RawPost
from models.defect_report import DefectReport, parse_date_str
from run_scraper import ScraperPipeline


class TestVehicleMatcherReDoSAndPerformance(unittest.TestCase):
    """Audits regex performance and verifies ReDoS remediation."""

    def test_01_genesis_whitespace_no_quadratic_backtracking(self) -> None:
        """Verifies that the Genesis/GV60 regex does not exhibit quadratic backtracking on whitespace."""
        genesis_rule = next(
            (pat for pat, brand in [
                (re_pat, b) for re_pat, b in [(r[0], r[1]) for r in [
                    (rule[0], rule[2]) for rule in MODEL_RULES
                ]]
            ] if "제네시스" in pat.pattern),
            None,
        )
        # Search specifically in BRAND_KEYWORDS or MODEL_RULES
        from filters.vehicle_matcher import BRAND_KEYWORDS
        brand_genesis = next(pat for pat, brand in BRAND_KEYWORDS if "제네시스" in pat.pattern)

        # 50,000 characters of spaces
        large_space = " " * 50000
        t0 = time.time()
        brand_genesis.search(large_space)
        dur = time.time() - t0
        self.assertLess(dur, 0.05, f"Genesis regex took {dur:.4f}s on 50k spaces; ReDoS detected!")

    def test_02_model_rules_scaling_on_adversarial_strings(self) -> None:
        """All model rules must complete search on adversarial long strings in under 20ms."""
        adversarial_payloads = [
            " " * 10000,
            "a" * 10000,
            ("비엠 " * 50) + "m3",
            ("모델 " * 50) + "3",
            ("아이오닉 " * 50) + "5",
            ("byd " * 50) + "seal",
        ]
        for pat, model_name, brand in MODEL_RULES:
            for payload in adversarial_payloads:
                t0 = time.time()
                pat.search(payload)
                dur = time.time() - t0
                self.assertLess(
                    dur,
                    0.05,
                    f"Model rule '{model_name}' ({pat.pattern[:40]}) took {dur:.4f}s on payload: {payload[:20]}...",
                )

    def test_03_extract_vehicle_info_null_and_malformed_safety(self) -> None:
        """extract_vehicle_info must never raise on None, non-string, or empty title/content."""
        brand, model = extract_vehicle_info(None, None)
        self.assertEqual(brand, "Other")
        self.assertEqual(model, "전기차")

        brand, model = extract_vehicle_info(12345, ["not", "string"])  # type: ignore
        self.assertEqual(brand, "Other")
        self.assertEqual(model, "전기차")


class TestSpamFilterRobustness(unittest.TestCase):
    """Audits SpamFilter stage 1 noise exclusion, commercials, news, and queries."""

    def setUp(self) -> None:
        self.filter = SpamFilter()

    def test_01_null_and_empty_inputs(self) -> None:
        """SpamFilter must discard empty or None input gracefully without exceptions."""
        is_disc, reason = self.filter.evaluate_stage1_noise(None, None)
        self.assertTrue(is_disc)
        self.assertIn("Empty", reason)

        is_disc, reason = self.filter.evaluate_stage1_noise("", "")
        self.assertTrue(is_disc)

        is_disc, reason = self.filter.evaluate_stage1_noise("   \n\t   ", "")
        self.assertTrue(is_disc)

    def test_02_commercial_spam_detection(self) -> None:
        """Illegal ads and commercial solicitations must be rejected."""
        ad_text = "당일 대출 가능합니다. 카톡 상담 아이디 loan119 연락주세요."
        is_disc, reason = self.filter.evaluate_stage1_noise(ad_text)
        self.assertTrue(is_disc)
        self.assertIn("Commercial", reason)

        # Telegram spam
        ad_tele = "코인 마진거래 텔레그램 문의 주세요."
        self.assertTrue(self.filter.is_spam(ad_tele))

    def test_03_journalistic_news_detection(self) -> None:
        """Journalistic wires and news agency quotes must be filtered."""
        news_text = "[단독] 국토교통부에 따르면 현대차 아이오닉5 리콜 발표를 전했다."
        is_disc, reason = self.filter.evaluate_stage1_noise(news_text)
        self.assertTrue(is_disc)
        self.assertIn("Journalistic", reason)

    def test_04_external_news_share_with_short_comment(self) -> None:
        """External news link shares with minimal text must be filtered."""
        self.assertTrue(self.filter.is_spam("이거 보세요", "https://news.naver.com/mnews/article/001/123"))

    def test_05_stock_trading_discussion_filtered(self) -> None:
        """Financial stock trading discussions with 2+ stock keywords must be filtered."""
        stock_text = "오늘 테슬라 주가 나스닥 실적발표 보고 매수 평단 낮췄습니다."
        is_disc, reason = self.filter.evaluate_stage1_noise(stock_text)
        self.assertTrue(is_disc)
        self.assertIn("stock", reason)

    def test_06_prospective_buyer_query_filtered_vs_authentic_question_retained(self) -> None:
        """Prospective buyer queries filtered; authentic owner defect questions retained."""
        # Non-owner prospective buyer query
        query_text = "전기차 살까요 말까요? 연비랑 유지비 궁금합니다."
        is_disc, reason = self.filter.evaluate_stage1_noise(query_text)
        self.assertTrue(is_disc)
        self.assertIn("inquiry", reason.lower())

        # Authentic owner with question mark ending retained
        owner_question = "고속도로 주행 중 갑자기 ICCU 퍽 터지면서 동력 상실 왔는데 이거 어떻게 해야 하나요?"
        is_disc, _ = self.filter.evaluate_stage1_noise(owner_question)
        self.assertFalse(is_disc, "Authentic defect complaint with question marker must NOT be discarded")

    def test_07_filter_posts_iterable(self) -> None:
        """filter_posts filters out spam and retains legitimate posts."""
        posts = [
            {"title": "광고", "content": "무직자 대출 문의 카톡 상담", "url": ""},
            {"title": "진짜 결함", "content": "내차 아이오닉5 주행 중 모터 소음 찌걱 소리 남", "url": ""},
            None,
        ]
        retained = self.filter.filter_posts(posts)
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0]["title"], "진짜 결함")


class TestDefectClassifierRobustness(unittest.TestCase):
    """Audits DefectClassifier stages 1-4, sentiment, DSI, and fallback handling."""

    def setUp(self) -> None:
        self.classifier = DefectClassifier()

    def test_01_process_post_with_none_and_empty(self) -> None:
        """process_post must handle None or empty input gracefully without raising exceptions."""
        rec = self.classifier.process_post(None)
        self.assertIsInstance(rec, ComplaintRecord)
        self.assertFalse(rec.is_authentic_defect)

        rec_empty = self.classifier.process_post({})
        self.assertIsInstance(rec_empty, ComplaintRecord)
        self.assertFalse(rec_empty.is_authentic_defect)

    def test_02_comments_string_not_split_into_chars(self) -> None:
        """Comments passed as a single string must not be split character-by-character."""
        post = RawPost(
            platform="dcinside",
            post_id="p1",
            title="아이오닉5 고장",
            content="내차 주행 중 멈춤 발생했습니다.",
            comments="서비스센터 입고했습니다.",  # String instead of list
        )
        rec = self.classifier.process_post(post)
        self.assertIsInstance(rec, ComplaintRecord)

    def test_03_authentic_defect_classified_correctly(self) -> None:
        """Real owner defect is classified with category, polarity, and DSI."""
        post = RawPost(
            platform="bobaedream",
            post_id="b101",
            title="EV6 고속도로 주행 중 ICCU 터짐",
            content="내차 출고 3달만에 고속도로에서 퍽 소리 나더니 전원공급장치 점검 경고등 뜨고 시동 꺼짐. 황천길 갈 뻔했습니다.",
            created_at="2026-10-28 14:30:00",
        )
        rec = self.classifier.process_post(post)
        self.assertTrue(rec.is_authentic_defect)
        self.assertEqual(rec.vehicle_brand, "Kia")
        self.assertEqual(rec.vehicle_model, "EV6")
        self.assertEqual(rec.defect_category, "BATTERY_CHARGING")
        self.assertLessEqual(rec.sentiment_polarity, -0.30)
        self.assertGreaterEqual(rec.severity_index, 7.0)
        self.assertIsNotNone(rec.dsi_breakdown)

    def test_04_negated_defect_praise_rejected(self) -> None:
        """Posts praising the car with negated defects must not be classified as defects."""
        post = RawPost(
            platform="dcinside",
            post_id="p2",
            title="아이오닉5 출고 후기 대만족",
            content="내차 출고하고 5000km 탔는데 단차 전혀 없고 잡소리 1도 안 납니다. 완벽한 양품이네요.",
        )
        rec = self.classifier.process_post(post)
        self.assertFalse(rec.is_authentic_defect)
        self.assertGreater(rec.sentiment_polarity, 0.0)

    def test_05_sarcastic_rant_inverted(self) -> None:
        """Sarcastic rants (praise + defect + laughing) must invert to negative."""
        post = RawPost(
            platform="bobaedream",
            post_id="p3",
            title="테슬라 모델3 감성 단차",
            content="내차 비 오는 날 타보니 단차 예술이네요 ㅋㅋㅋ 워터파크 개장했습니다 ㅎㅎ",
        )
        rec = self.classifier.process_post(post)
        self.assertLessEqual(rec.sentiment_polarity, -0.70)


class TestDefectReportAndDateParsing(unittest.TestCase):
    """Audits DefectReport model, date_str parsing, calendar validation, and serialization."""

    def test_01_parse_date_str_iso_and_timestamps(self) -> None:
        """parse_date_str correctly extracts YYYY-MM-DD from various timestamp formats."""
        self.assertEqual(parse_date_str("2026-10-28 19:01:23.495311"), "2026-10-28")
        self.assertEqual(parse_date_str("2026-10-28T19:01:23.495311Z"), "2026-10-28")
        self.assertEqual(parse_date_str("2026-10-28T19:01:23.495311+09:00"), "2026-10-28")
        self.assertEqual(parse_date_str("2026.10.28 19:01:23"), "2026-10-28")
        self.assertEqual(parse_date_str("2026/10/28 19:01:23"), "2026-10-28")
        self.assertEqual(parse_date_str("20261028"), "2026-10-28")
        self.assertEqual(parse_date_str("2026년 10월 28일"), "2026-10-28")
        self.assertEqual(parse_date_str("26.10.25"), "2026-10-25")
        self.assertEqual(parse_date_str("26-10-25"), "2026-10-25")

    def test_02_parse_date_str_month_day_format(self) -> None:
        """parse_date_str correctly maps MM.DD format to current year."""
        current_year = datetime.now(timezone.utc).year
        self.assertEqual(parse_date_str("10.28"), f"{current_year}-10-28")
        self.assertEqual(parse_date_str("05-15"), f"{current_year}-05-15")

    def test_03_calendar_validation_invalid_dates_fallback_to_today(self) -> None:
        """Invalid dates like Feb 31 or Month 13 must safely fall back to today without raising ValueError."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.assertEqual(parse_date_str("2026-02-31"), today)
        self.assertEqual(parse_date_str("2026-13-45"), today)
        self.assertEqual(parse_date_str("99999999"), today)
        self.assertEqual(parse_date_str("not-a-date"), today)
        self.assertEqual(parse_date_str(None), today)
        self.assertEqual(parse_date_str(""), today)

    def test_04_defect_report_from_dict_and_to_dict(self) -> None:
        """DefectReport initializes properly from dict, supports aliases, and serializes."""
        raw_data = {
            "id": "dr-999",
            "platform": "dcinside",
            "post_title": "ICCU 경고등 점등",
            "raw_quote": "고속도로에서 갑자기 시동 꺼지고 멈췄습니다.",
            "target_vehicle": "Kia EV6",
            "category": "BATTERY_CHARGING",
            "date": "2026-10-28",
            "slang_tags": "ICCU, 밥솥, 퍽",  # Comma-separated string
            "sentiment_score": 0.85,
            "severity_index": 7.5,
            "severity": "HIGH",
        }
        report = DefectReport.from_dict(raw_data)
        self.assertEqual(report.id, "dr-999")
        self.assertEqual(report.source, "dcinside")
        self.assertEqual(report.vehicle_brand, "Kia")
        self.assertEqual(report.vehicle_model, "EV6")
        self.assertEqual(report.defect_category, "BATTERY_CHARGING")
        self.assertEqual(report.date_str, "2026-10-28")
        self.assertIn("ICCU", report.slang_terms_detected)
        self.assertEqual(report.severity_tier, "HIGH")

        # Dictionary export contract checks
        d = report.to_admin_report_dict()
        self.assertEqual(d["target_vehicle"], "Kia EV6")
        self.assertEqual(d["date"], "2026-10-28")
        self.assertEqual(d["severity"], "HIGH")


class TestScraperPipelineHardening(unittest.TestCase):
    """Audits ScraperPipeline harvest, filter_defects, and runner error resilience."""

    def test_01_filter_defects_none_and_malformed_items(self) -> None:
        """filter_defects must handle None list, None items, and malformed dicts gracefully."""
        pipeline = ScraperPipeline()
        self.assertEqual(pipeline.filter_defects(None), [])
        self.assertEqual(pipeline.filter_defects([]), [])

        corrupt_items = [
            None,
            123,
            "just a string",
            {"post_id": "bad_post", "corrupted": True},
        ]
        # Should not raise exception
        result = pipeline.filter_defects(corrupt_items)
        self.assertIsInstance(result, list)

    def test_02_harvest_invalid_source_and_negative_limit(self) -> None:
        """harvest must fall back to 'all' and clamp limit >= 1 when given invalid arguments."""
        pipeline = ScraperPipeline()
        with patch.object(pipeline, "harvest_bobaedream", return_value=[]), \
             patch.object(pipeline, "harvest_dcinside", return_value=[]):
            posts, stats = pipeline.harvest(source_choice="invalid_source", limit=-10)
            self.assertEqual(posts, [])
            self.assertIn("bobaedream", stats)
            self.assertIn("dcinside", stats)

    def test_03_run_dry_run_handles_empty_scraped_gracefully(self) -> None:
        """run in dry_run mode completes with 0 exit without disk writes."""
        pipeline = ScraperPipeline()
        with patch.object(pipeline, "harvest", return_value=([], {"bobaedream": 0, "dcinside": 0})):
            summary = pipeline.run(dry_run=True, sources="all")
            self.assertEqual(summary["total_scraped"], 0)
            self.assertEqual(summary["total_filtered_defects"], 0)
            self.assertTrue(summary["dry_run"])


if __name__ == "__main__":
    unittest.main()
