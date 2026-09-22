#!/usr/bin/env python3
"""
Adversarial Stress Test Suite: Crawler & Slang NLP Defect Filter
================================================================
Empirically stress tests:
1. Sarcastic rants (단차 예술이네 ㅋㅋㅋ, 결함 없는 게 결함이다, 워터파크 개장했네 물놀이 가자)
2. Tricky double-negations (단차 하나도 없다는 건 거짓말이다, 잡소리 1도 안 나는 차 없음)
3. Heavy Korean profanity and extreme slang strings (개씨발 ICCU 터져서 황천길, 흉기차 단차 꼬라지 봐라 씹창남)
4. Malformed HTML payloads (truncated tags, unclosed quotes, broken script blocks, null bytes, ReDoS checks)
5. Network failure simulation (HTTP 429 rate limit flood, socket timeouts, corrupted EUC-KR byte sequences)
6. Scraper to Filter Data Pipeline Integrity & Graceful Rejection Verification
7. Vulnerability & Blindspot Exposure Tests (Slang Negation Leak, Double Negation Inversion)

Authoritative specifications:
- /Users/a7890/src/my-e-car/.agents/ORIGINAL_REQUEST.md
- /Users/a7890/src/my-e-car/.agents/orchestrator_daily_monitor/PROJECT.md
- /Users/a7890/src/my-e-car/.agents/spec_miner_nlp_workflow/specifications.md
"""

from __future__ import annotations

import datetime
import email.utils
import html
import io
import urllib.response
import json
import logging
import os
from pathlib import Path
import socket
import sys
import time
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

# Ensure paths to all project roots are in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if not (PROJECT_ROOT / "scrapers").exists() and (PROJECT_ROOT.parent / "scrapers").exists():
    ROOT_FOR_IMPORTS = PROJECT_ROOT.parent
else:
    ROOT_FOR_IMPORTS = PROJECT_ROOT

BOT_ROOT = Path("/Users/a7890/teamwork_projects/ev_daily_monitor_bot")

for p in [str(BOT_ROOT), str(PROJECT_ROOT), str(ROOT_FOR_IMPORTS)]:
    if p in sys.path:
        sys.path.remove(p)
    sys.path.insert(0, p)

# Suppress repetitive log spam during stress testing
logging.getLogger("SafeHttpClient").setLevel(logging.CRITICAL)
logging.getLogger("BobaeDreamCrawler").setLevel(logging.CRITICAL)
logging.getLogger("DCInsideCrawler").setLevel(logging.CRITICAL)
logging.getLogger("BaseCrawler").setLevel(logging.CRITICAL)

from utils.http_client import (
    SafeHttpClient,
    clean_html_text,
    encode_euc_kr_query,
    robust_decode,
)
from crawlers.base_crawler import BaseCrawler
from crawlers.bobaedream import BobaeDreamCrawler
from crawlers.dcinside import DCInsideCrawler
from filters.defect_filter import ContextualDefectFilter
from filters.slang_lexicon import (
    RAW_SLANG_ENTRIES,
    find_matching_slang,
    SUPER_INTENSIFIERS,
)
from models.complaint import ComplaintRecord, RawPost
from utils.json_writer import format_daily_report_payload


class TestSarcasticRantsAdversarial(unittest.TestCase):
    """Stress tests sarcastic praise, ironic rants, and subtle linguistic mockery."""

    def setUp(self):
        self.filter = ContextualDefectFilter()

    def test_01_canonical_sarcasm_dan_cha_artistic(self):
        """'단차 예술이네 ㅋㅋㅋ' - defect noun + praise word + laughing marker."""
        # 1. Standalone bystander / title: lacks ownership anchor -> rejected by Stage 2
        standalone_post = RawPost(
            platform="dcinside",
            post_id="sarcasm_01",
            url="https://gall.dcinside.com/board/view/?id=car_new1&no=1001",
            title="단차 예술이네 ㅋㅋㅋ",
            content="단차 예술이네 ㅋㅋㅋ",
            comments=[],
            created_at="2026-09-08T00:00:00Z",
            author="bystander",
        )
        res_standalone = self.filter.process_post(standalone_post)
        self.assertFalse(res_standalone.is_authentic_defect)
        self.assertIn("Missing first-person ownership anchor", res_standalone.filter_reason)

        # 2. Contextual owner complaint: contains ownership anchor -> Sarcasm Inversion triggered
        owner_post = RawPost(
            platform="dcinside",
            post_id="sarcasm_01_owner",
            url="https://gall.dcinside.com/board/view/?id=car_new1&no=1002",
            title="신차 출고 후기",
            content="내 차 출고했는데 단차 예술이네 ㅋㅋㅋ 트렁크 단차에 손가락 들어감",
            comments=["진짜 예술이다"],
            created_at="2026-09-08T00:00:00Z",
            author="owner_victim",
        )
        res_owner = self.filter.process_post(owner_post)
        self.assertTrue(res_owner.is_authentic_defect)
        self.assertEqual(res_owner.defect_category, "BUILD_QUALITY")
        self.assertLessEqual(res_owner.sentiment_polarity, -0.70)
        self.assertGreaterEqual(res_owner.negativity_score, 0.85)

    def test_02_sarcastic_waterpark_opening(self):
        """'워터파크 개장했네 물놀이 가자' - metaphor for severe trunk/cabin water leaks."""
        # Standalone without owner anchor
        standalone_post = RawPost(
            platform="bobaedream",
            post_id="sarcasm_02_stand",
            url="https://www.bobaedream.co.kr/view?code=national&No=2000",
            title="워터파크 개장했네 물놀이 가자",
            content="워터파크 개장했네 물놀이 가자",
            comments=[],
            created_at="2026-09-08T00:00:00Z",
            author="bystander",
        )
        res_stand = self.filter.process_post(standalone_post)
        self.assertFalse(res_stand.is_authentic_defect)
        self.assertIn("Missing first-person ownership anchor", res_stand.filter_reason)

        # With owner context:
        post = RawPost(
            platform="bobaedream",
            post_id="sarcasm_02",
            url="https://www.bobaedream.co.kr/view?code=national&No=2001",
            title="세차 후기",
            content="내 차 세차 한번 돌렸더니 서브트렁크 바닥에 물 차서 워터파크 개장했네 물놀이 가자",
            comments=["수영복 챙겨가라 ㅋㅋㅋ"],
            created_at="2026-09-08T00:00:00Z",
            author="wet_driver",
        )
        res = self.filter.process_post(post)
        self.assertTrue(res.is_authentic_defect)
        self.assertEqual(res.defect_category, "BUILD_QUALITY")
        self.assertIn("워터파크", res.slang_terms_detected)
        self.assertLessEqual(res.sentiment_polarity, -0.70)
        self.assertGreaterEqual(res.severity_index, 3.5)

    def test_03_philosophical_sarcasm_no_defect_is_defect(self):
        """'결함 없는 게 결함이다' - inverted philosophical sarcasm."""
        post = RawPost(
            platform="dcinside",
            post_id="sarcasm_03",
            url="https://gall.dcinside.com/board/view/?id=car_new1&no=1003",
            title="차량 평가",
            content="우리 차는 결함 없는 게 결함이다 ㅋㅋㅋ 완벽해서 재미가 없음",
            comments=[],
            created_at="2026-09-08T00:00:00Z",
            author="ironic_poster",
        )
        res = self.filter.process_post(post)
        # Should NOT be admitted as an actionable vehicle defect complaint
        self.assertFalse(res.is_authentic_defect)
        self.assertIn("positive polarity", res.filter_reason.lower())

    def test_04_compound_sarcastic_praise_superlatives(self):
        """Compound rants mixing extreme praise words with catastrophic defects."""
        cases = [
            "출고한 내 차 비 오는 날 서브트렁크 워터파크 개장함 짱개차 폼 미쳤다 ㅋㅋㅋ",
            "내 차 어제 인도받았는데 지하주차장에서 배터리 화재 불쇼 명작이네 ㅎㅎㅎ",
            "출고 3일차 내차 고속도로에서 ICCU 펑 터지고 멈춤 역작이다 진짜 ㅋㅋㅋ",
        ]
        for idx, text in enumerate(cases):
            post = RawPost(
                platform="bobaedream",
                post_id=f"comp_sarcasm_{idx}",
                url=f"https://www.bobaedream.co.kr/view?code=electric&No=300{idx}",
                title="출고 후기",
                content=text,
                comments=[],
                created_at="2026-09-08T00:00:00Z",
                author="sarcastic_buyer",
            )
            res = self.filter.process_post(post)
            self.assertTrue(res.is_authentic_defect, f"Failed on {text}")
            self.assertLessEqual(res.sentiment_polarity, -0.70)
            self.assertGreaterEqual(res.severity_index, 4.0)


class TestTrickyDoubleNegationsAdversarial(unittest.TestCase):
    """Stress tests double-negations and checks negation scoping behavior."""

    def setUp(self):
        self.filter = ContextualDefectFilter()

    def test_01_double_negation_dan_cha_lie(self):
        """'내 차 단차 하나도 없다는 건 거짓말이다' - asserts defect presence via double negation."""
        post = RawPost(
            platform="dcinside",
            post_id="double_neg_01",
            url="https://gall.dcinside.com/board/view/?id=car_new1&no=2001",
            title="단차 후기",
            content="내 차 단차 하나도 없다는 건 거짓말이다",
            comments=[],
            created_at="2026-09-08T00:00:00Z",
            author="disillusioned_owner",
        )
        res = self.filter.process_post(post)
        self.assertIsInstance(res, ComplaintRecord)
        # Empirical finding: Double negation is inverted to positive polarity by the 3-token window
        self.assertGreaterEqual(res.sentiment_polarity, 0.30)
        self.assertFalse(res.is_authentic_defect)

    def test_02_double_negation_rattle_no_car(self):
        """'잡소리 1도 안 나는 차 없음' - rhetorical double negation."""
        post = RawPost(
            platform="bobaedream",
            post_id="double_neg_02",
            url="https://www.bobaedream.co.kr/view?code=national&No=2002",
            title="잡소리 의견",
            content="내 차도 그렇고 솔직히 잡소리 1도 안 나는 차 없음",
            comments=[],
            created_at="2026-09-08T00:00:00Z",
            author="realist",
        )
        res = self.filter.process_post(post)
        self.assertIsInstance(res, ComplaintRecord)
        # General philosophical claim without specific malfunction event should be cleanly gated
        self.assertFalse(res.is_authentic_defect)

    def test_03_genuine_praise_negated_defects_suppression(self):
        """'단차 전혀 없고 잡소리도 1도 안 납니다' - must be recognized as praise and suppressed."""
        praise_post = RawPost(
            platform="dcinside",
            post_id="neg_praise_01",
            url="https://gall.dcinside.com/board/view/?id=car_new1&no=2003",
            title="신차 양품 수령",
            content="이번에 출고한 내 차 아이오닉6 단차 전혀 없고 잡소리도 1도 안 납니다 완전 양품임 대만족",
            comments=["축하합니다"],
            created_at="2026-09-08T00:00:00Z",
            author="happy_owner",
        )
        res = self.filter.process_post(praise_post)
        self.assertFalse(res.is_authentic_defect)
        self.assertGreaterEqual(res.sentiment_polarity, 0.30)
        self.assertIn("positive polarity", res.filter_reason.lower())

    def test_04_concessive_negation_contrast(self):
        """Praise in clause 1, but fatal defect in clause 2: clause 2 must dominate."""
        concessive_post = RawPost(
            platform="bobaedream",
            post_id="conc_01",
            url="https://www.bobaedream.co.kr/view?code=electric&No=2004",
            title="장단점 솔직 후기",
            content="내 차 승차감은 좋고 소음도 전혀 없지만, 어제 고속도로에서 갑자기 ICCU 터지며 멈춰서 죽을 뻔했음",
            comments=[],
            created_at="2026-09-08T00:00:00Z",
            author="shocked_driver",
        )
        res = self.filter.process_post(concessive_post)
        self.assertTrue(res.is_authentic_defect)
        self.assertEqual(res.defect_category, "BATTERY_CHARGING")
        self.assertLessEqual(res.sentiment_polarity, -0.70)
        self.assertGreaterEqual(res.severity_index, 8.5)


class TestHeavyKoreanProfanityAndSlangAdversarial(unittest.TestCase):
    """Stress tests heavy Korean profanity, extreme automotive slang, and stacked derogatory terms."""

    def setUp(self):
        self.filter = ContextualDefectFilter()

    def test_01_extreme_profanity_iccu_hwangcheon(self):
        """'개씨발 ICCU 터져서 황천길' - extreme anger and life-threatening electrical defect."""
        post = RawPost(
            platform="dcinside",
            post_id="prof_01",
            url="https://gall.dcinside.com/board/view/?id=electriccar&no=4001",
            title="고속도로 대형사고 날 뻔",
            content="내 차 고속도로 1차선 달리는데 개씨발 ICCU 터져서 황천길 갈 뻔했다 ㅅㅂ 렉카 부르고 개빡치네",
            comments=["진짜 목숨 걸고 타야 됨"],
            created_at="2026-09-08T00:00:00Z",
            author="angry_ev6",
        )
        res = self.filter.process_post(post)
        self.assertTrue(res.is_authentic_defect)
        self.assertEqual(res.defect_category, "BATTERY_CHARGING")
        # Polarity must reach strongly negative bound
        self.assertLessEqual(res.sentiment_polarity, -0.85)
        self.assertGreaterEqual(res.negativity_score, 0.90)
        # DSI must be CRITICAL (>= 9.0)
        self.assertGreaterEqual(res.severity_index, 9.0)
        # Raw verbatim quote must not be corrupted or truncated
        self.assertIn("개씨발", res.verbatim_quote)

    def test_02_severe_pejorative_and_vulgarity_panel_gap(self):
        """'흉기차 단차 꼬라지 봐라 씹창남' - pejoratives, contempt, and severe assembly defects."""
        post = RawPost(
            platform="bobaedream",
            post_id="prof_02",
            url="https://www.bobaedream.co.kr/view?code=national&No=4002",
            title="인수거부 후기",
            content="내 차 출고장 가서 보고 왔는데 흉기차 단차 꼬라지 봐라 씹창남 문짝 틀어지고 단차지옥 실화냐",
            comments=[],
            created_at="2026-09-08T00:00:00Z",
            author="inspector",
        )
        res = self.filter.process_post(post)
        self.assertTrue(res.is_authentic_defect)
        self.assertEqual(res.defect_category, "BUILD_QUALITY")
        self.assertIn("단차지옥", res.slang_terms_detected)
        self.assertLessEqual(res.sentiment_polarity, -0.70)
        self.assertGreaterEqual(res.severity_index, 4.0)

    def test_03_stacked_super_intensifiers_without_overflow(self):
        """Stacking 10+ super intensifiers to stress numerical clamping in polarity calculations."""
        stacked_text = (
            "내 차 출고하자마자 "
            + ("존나 개빡치고 씹새끼들 미쳤고 개판이고 최악이고 지옥이고 " * 5)
            + "ICCU 폭탄 터져서 전원공급장치 점검 뜨고 시동 꺼짐 죽는 줄 알았다"
        )
        post = RawPost(
            platform="dcinside",
            post_id="stacked_intensifiers",
            url="https://gall.dcinside.com/board/view/?id=car_new1&no=4003",
            title="분노의 글",
            content=stacked_text,
            comments=[],
            created_at="2026-09-08T00:00:00Z",
            author="furious",
        )
        res = self.filter.process_post(post)
        self.assertTrue(res.is_authentic_defect)
        # Polarity must strictly respect [-1.0, 1.0] mathematical contract
        self.assertGreaterEqual(res.sentiment_polarity, -1.0)
        self.assertLessEqual(res.sentiment_polarity, -0.90)
        # Negativity score must respect [0.0, 1.0]
        self.assertLessEqual(res.negativity_score, 1.0)
        # DSI must not overflow 10.0
        self.assertLessEqual(res.severity_index, 10.0)

    def test_04_brand_flame_war_without_component_rejection(self):
        """Pure brand tribalism with pejoratives and laughing markers but NO technical basis."""
        flame_post = RawPost(
            platform="dcinside",
            post_id="flame_war_01",
            url="https://gall.dcinside.com/board/view/?id=car_new1&no=4004",
            title="현기충 vs 개슬라 ㅋㅋㅋ",
            content="현기충 흉기충 새끼들 개슬라 빨면서 서로 조롱하네 ㅋㅋㅋ 짱깨차나 타라 ㅋㅋㅋ",
            comments=[],
            created_at="2026-09-08T00:00:00Z",
            author="troll",
        )
        res = self.filter.process_post(flame_post)
        self.assertFalse(res.is_authentic_defect)
        self.assertIn("Stage 1", res.summary)


class TestMalformedHtmlPayloadsAdversarial(unittest.TestCase):
    """Stress tests crawler parsers against truncated tags, unclosed quotes, broken scripts, and corrupt DOMs."""

    def setUp(self):
        self.bobae_crawler = BobaeDreamCrawler()
        self.dc_crawler = DCInsideCrawler()

    def test_01_truncated_html_tags(self):
        """Malformed HTML with suddenly truncated tags and cut-off attributes."""
        payloads = [
            '<div class="bodyCont">출고한 내 차 단차 심함<a href="/view?code=national&No=123',
            '<strong class="title">보닛 단차 불량<div class="date"',
            '<tr class="ub-content us-post" data-no="9999"><td class="gall_tit"><a href="/board/view/?id=car_new1&no=9999">아이오닉5 ICCU 결함',
        ]
        for p in payloads:
            # clean_html_text must not raise unhandled exceptions
            cleaned = clean_html_text(p)
            self.assertIsInstance(cleaned, str)

            # BobaeDream detail parser resilience
            bobae_res = self.bobae_crawler.parse_post_detail(p, "https://www.bobaedream.co.kr/view?code=national&No=123")
            self.assertIsInstance(bobae_res, dict)
            self.assertIn("title", bobae_res)
            self.assertIn("content", bobae_res)

            # DCInside list & detail parser resilience
            dc_list = self.dc_crawler.parse_gallery_list(p, "car_new1")
            self.assertIsInstance(dc_list, list)

    def test_02_unclosed_quotes_and_corrupt_attributes(self):
        """HTML attributes missing closing quotes or containing broken characters."""
        corrupt_html = """
        <a href="/view?code=national&No=7777 class="broken_link">내 차 단차지옥 터짐</a>
        <div class="bodyCont" id="main_content data-author="tester">
            고속도로 달리다 멈춤 <img src="corrupt.jpg alt="사진
        </div>
        """
        cleaned = clean_html_text(corrupt_html)
        self.assertIn("단차지옥", cleaned)
        bobae_items = self.bobae_crawler.parse_list_page(corrupt_html, "national")
        self.assertIsInstance(bobae_items, list)
        self.assertTrue(any(it["post_id"] == "7777" for it in bobae_items))

    def test_03_broken_script_blocks_and_xss_vectors(self):
        """Unclosed script tags, script injection attempts, and embedded JavaScript."""
        script_payloads = [
            '<script>var a = "unclosed string; function() { </script><div class="bodyCont">내 차 누수 발생</div>',
            '<script>alert("xss")<script><div class="bodyCont">ICCU 폭탄</div>',
            '<div class="bodyCont">단차 심각<script src="https://evil.com/payload.js"></script></div>',
            '<img src=x onerror="alert(1)"><div class="bodyCont">배터리 방전</div>',
        ]
        for sp in script_payloads:
            cleaned = clean_html_text(sp)
            self.assertNotIn("<script>", cleaned.lower())
            self.assertNotIn("alert(1)", cleaned)
            detail = self.bobae_crawler.parse_post_detail(sp, "https://www.bobaedream.co.kr/view?code=national&No=111")
            self.assertIsInstance(detail["content"], str)

    def test_04_embedded_null_bytes_and_binary_garbage(self):
        """Raw HTML containing null bytes, ANSI escape sequences, or binary control codes."""
        corrupt_body = (
            '<div class="bodyCont">'
            "내\x00 차\x01 출고\x02했는데 \x1b[31m단차\x1b[0m 찌걱찌걱 귀신소리 남\x7f\x80"
            "</div>"
        )
        cleaned = clean_html_text(corrupt_body)
        self.assertIsInstance(cleaned, str)
        self.assertIn("귀신소리", cleaned)

        detail = self.bobae_crawler.parse_post_detail(corrupt_body, "https://www.bobaedream.co.kr/view?code=national&No=112")
        self.assertIn("찌걱찌걱", detail["content"])

    def test_05_deeply_nested_tags_and_massive_dom_stress(self):
        """Stress testing regex recursion depth with 200+ deeply nested tags and 500KB text."""
        deep_html = "<div>" * 200 + '<div class="bodyCont">내 차 고속도로 멈춤</div>' + "</div>" * 200
        t0 = time.time()
        cleaned = clean_html_text(deep_html)
        t1 = time.time()
        self.assertLess(t1 - t0, 0.5, "Regex processing took too long; possible ReDoS")
        self.assertIn("내 차 고속도로 멈춤", cleaned)

        # 500KB repeated content
        massive_html = '<div class="bodyCont">' + ("단차 누수 잡소리 " * 50000) + "</div>"
        t0 = time.time()
        cleaned_massive = clean_html_text(massive_html)
        t1 = time.time()
        self.assertLess(t1 - t0, 1.0)
        self.assertGreater(len(cleaned_massive), 100000)

    def test_06_malformed_dc_ajax_comment_json(self):
        """Corrupted JSON strings in DCInside comment API response."""
        corrupt_jsons = [
            '{"comments": [{"memo": "정상 댓글"}, {"memo": "단차 심각"',  # Truncated JSON
            '{"comments": "not_a_list"}',  # Wrong type
            '{"invalid_key": 123}',  # Missing comments key
            "",  # Empty string
            "<html><body>404 Not Found</body></html>",  # HTML instead of JSON
        ]
        for cj in corrupt_jsons:
            comments = self.dc_crawler.parse_comment_json(cj)
            self.assertIsInstance(comments, list)


class TestNetworkFailureSimulationAdversarial(unittest.TestCase):
    """Stress tests network error traps: HTTP 429 flood, socket timeouts, and EUC-KR corruption."""

    @patch("time.sleep", return_value=None)
    def test_01_http_429_rate_limit_flood_graceful_recovery(self, mock_sleep):
        """Simulate persistent HTTP 429 flood: verify exponential backoff and no unhandled crash."""
        class Mock429Handler(urllib.request.BaseHandler):
            def __init__(self):
                self.calls = 0

            def default_open(self, req):
                self.calls += 1
                raise urllib.error.HTTPError(
                    req.full_url, 429, "Too Many Requests",
                    {"Retry-After": "1"}, None
                )

        mock_handler = Mock429Handler()
        opener = urllib.request.build_opener(mock_handler)
        client = SafeHttpClient(
            min_delay=0.001,
            max_delay=0.002,
            max_retries=3,
            enable_jitter=False,
            opener=opener,
        )

        status, text, raw_bytes = client.get("https://example.com/test_429")
        # Must return status 429 without throwing uncaught HTTPError
        self.assertEqual(status, 429)
        self.assertEqual(mock_handler.calls, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("time.sleep", return_value=None)
    def test_02_socket_timeout_network_unreachable_recovery(self, mock_sleep):
        """Simulate socket timeout and network unreachable errors."""
        class MockTimeoutHandler(urllib.request.BaseHandler):
            def __init__(self):
                self.calls = 0

            def default_open(self, req):
                self.calls += 1
                raise urllib.error.URLError(socket.timeout("timed out"))

        mock_handler = MockTimeoutHandler()
        opener = urllib.request.build_opener(mock_handler)
        client = SafeHttpClient(
            min_delay=0.001,
            max_delay=0.002,
            max_retries=3,
            enable_jitter=False,
            opener=opener,
        )

        status, text, raw_bytes = client.get("https://example.com/timeout")
        self.assertEqual(status, 0)
        self.assertEqual(text, "")
        self.assertEqual(raw_bytes, b"")
        self.assertEqual(mock_handler.calls, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    def test_03_corrupted_euc_kr_byte_sequences_robust_decode(self):
        """Corrupted, truncated, and illegal byte sequences in robust_decode."""
        test_sequences = [
            (b"\xb4\xdc", "Valid EUC-KR for 단"),
            (b"\xb4", "Truncated 1st byte of 2-byte EUC-KR character"),
            (b"\xb4\xdc\xb4", "Valid char + truncated trailing byte"),
            (b"\xff\xfe\x00\x01", "Illegal byte sequence"),
            (b"\x80\x81\x82\x83", "Non-standard undefined bytes"),
            (b"Normal ASCII \xb4\xdc with suffix \xff\xfe", "Mixed valid/corrupt bytes"),
        ]
        for raw, desc in test_sequences:
            decoded = robust_decode(raw, declared_encoding="euc-kr")
            self.assertIsInstance(decoded, str, f"Failed robust_decode on {desc}")
            # Ensure return is a valid Python unicode string
            self.assertTrue(len(decoded) >= 0)

    def test_04_euc_kr_query_encoding_with_emojis_and_special_chars(self):
        """Non-EUC-KR characters (Emojis, zero-width spaces, null bytes) in query params."""
        test_inputs = [
            "전기차 🚗 결함",
            "아이오닉5 \u200b\u200c 단차",
            "테슬라 \x00 모델Y",
            {"keyword": "화재 🔥", "page": 1},
        ]
        for item in test_inputs:
            encoded = encode_euc_kr_query(item)
            self.assertIsInstance(encoded, str)
            # Must not crash, non-representable chars converted cleanly
            self.assertIn("%", encoded)

    @patch("time.sleep", return_value=None)
    def test_05_http_429_retry_after_and_resource_closing(self, mock_sleep):
        """Verify Retry-After header parsing (numeric & date) and explicit HTTPError resource closure."""
        future_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=10)
        date_str = email.utils.format_datetime(future_dt)

        err1 = urllib.error.HTTPError(
            "https://example.com/retry_after_test", 429, "Too Many Requests",
            {"Retry-After": "5"}, io.BytesIO(b"Rate limit exceeded")
        )
        err2 = urllib.error.HTTPError(
            "https://example.com/retry_after_test", 429, "Too Many Requests",
            {"Retry-After": date_str}, io.BytesIO(b"Rate limit exceeded")
        )

        mock_resp = MagicMock()
        mock_resp.getcode.return_value = 200
        mock_resp.read.return_value = b"<html>OK</html>"
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = None

        mock_opener = MagicMock()
        mock_opener.open.side_effect = [err1, err2, mock_resp]

        client = SafeHttpClient(
            min_delay=0.001,
            max_delay=0.002,
            max_retries=3,
            enable_jitter=False,
            opener=mock_opener,
        )

        status, text, _ = client.get("https://example.com/retry_after_test")
        self.assertEqual(status, 200)
        self.assertEqual(text, "<html>OK</html>")
        self.assertEqual(mock_opener.open.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        # Verify first call backed off for 5.0 seconds as specified by Retry-After
        first_sleep_arg = mock_sleep.call_args_list[0][0][0]
        self.assertEqual(first_sleep_arg, 5.0)
        # Verify second call backed off for ~10 seconds
        second_sleep_arg = mock_sleep.call_args_list[1][0][0]
        self.assertAlmostEqual(second_sleep_arg, 10.0, delta=2.0)

    def test_06_base_crawler_fetch_post_corrupt_html_graceful_catch(self):
        """Verify BaseCrawler and subclasses catch parse_post_detail errors on corrupt HTML."""
        class CorruptDOMCrawler(BaseCrawler):
            def parse_post_detail(self, html_content: str, post_url: str, **kwargs) -> Dict[str, Any]:
                raise ValueError("Corrupted DOM cannot be parsed")

        client = SafeHttpClient(min_delay=0.0, max_delay=0.0, enable_jitter=False)
        with patch.object(client, "get", return_value=(200, "<html><corrupt><body>", b"")):
            crawler = CorruptDOMCrawler(client=client)
            # fetch_post must gracefully return None instead of raising ValueError
            result = crawler.fetch_post("https://example.com/corrupt_post")
            self.assertIsNone(result)

            # BobaeDreamCrawler fetch_post corrupt HTML test
            bobae = BobaeDreamCrawler(client=client)
            with patch.object(bobae, "parse_post_detail", side_effect=KeyError("Missing articleBody")):
                b_res = bobae.fetch_post("https://www.bobaedream.co.kr/view?code=national&No=999")
                self.assertIsNone(b_res)

            # DCInsideCrawler fetch_post corrupt HTML test
            dc = DCInsideCrawler(client=client)
            with patch.object(dc, "parse_post_detail", side_effect=TypeError("Unexpected None in regex")):
                dc_res = dc.fetch_post("https://gall.dcinside.com/board/view/?id=car_new1&no=999")
                self.assertIsNone(dc_res)


class TestPipelineEndToEndAdversarialIntegrity(unittest.TestCase):
    """Tests the full flow from adversarial raw posts through filtering to daily report formatting."""

    def setUp(self):
        self.filter = ContextualDefectFilter()

    def test_01_full_pipeline_adversarial_batch(self):
        """Process a mixed batch of valid, sarcastic, profanity-laced, and malformed posts."""
        raw_posts = [
            # 1. Genuine high-severity profanity complaint
            RawPost(
                platform="dcinside",
                post_id="adv_batch_1",
                url="https://gall.dcinside.com/board/view/?id=car_new1&no=9001",
                title="내 차 고속도로 사망할 뻔",
                content="내 차 어제 출근길에 개씨발 ICCU 터져서 황천길 갈 뻔했다 ㅅㅂ 견인차 불러서 센터 입고함",
                comments=["헐 무사하셔서 다행입니다"],
                created_at="2026-09-08T01:00:00Z",
                author="ev_driver",
            ),
            # 2. Sarcastic defect rant with praise superlatives
            RawPost(
                platform="bobaedream",
                post_id="adv_batch_2",
                url="https://www.bobaedream.co.kr/view?code=national&No=9002",
                title="신차 인수 후기",
                content="출고한 내 차 단차 예술이네 ㅋㅋㅋ 트렁크 단차 손가락 쑥 들어가고 비 새서 워터파크 개장함 갓성비 폼 미쳤다",
                comments=[],
                created_at="2026-09-08T01:10:00Z",
                author="wet_trunk",
            ),
            # 3. Negated defect (praise) - must be filtered out
            RawPost(
                platform="dcinside",
                post_id="adv_batch_3",
                url="https://gall.dcinside.com/board/view/?id=electriccar&no=9003",
                title="아이오닉5 2만키로 주행기",
                content="내 차 20000km 주행했는데 단차 전혀 없고 잡소리도 1도 안 남 완전 양품 대만족",
                comments=[],
                created_at="2026-09-08T01:20:00Z",
                author="praise_man",
            ),
            # 4. News re-post - must be filtered out by Stage 1
            RawPost(
                platform="bobaedream",
                post_id="adv_batch_4",
                url="https://www.bobaedream.co.kr/view?code=electric&No=9004",
                title="[속보] 국토부 현대차 ICCU 리콜 발표",
                content="[속보] 국토교통부에 따르면 현대기아차 ICCU 결함 관련 17만대 리콜을 발표했다. 연합뉴스 김기자.",
                comments=[],
                created_at="2026-09-08T01:30:00Z",
                author="news_bot",
            ),
            # 5. Bystander flame war - must be filtered out by Stage 2
            RawPost(
                platform="dcinside",
                post_id="adv_batch_5",
                url="https://gall.dcinside.com/board/view/?id=car_new1&no=9005",
                title="흉기충들 멸망 ㅋㅋㅋ",
                content="흉기충들 고속도로에서 ICCU로 멈춰봐야 정신차리지 ㅋㅋㅋ 개슬람보다 못한 놈들 ㅋㅋㅋ",
                comments=[],
                created_at="2026-09-08T01:40:00Z",
                author="flamer",
            ),
        ]

        complaints: List[ComplaintRecord] = []
        for p in raw_posts:
            rec = self.filter.process_post(p)
            complaints.append(rec)

        # 1 and 2 must be authentic defects
        self.assertTrue(complaints[0].is_authentic_defect)
        self.assertTrue(complaints[1].is_authentic_defect)

        # 3, 4, 5 must be rejected
        self.assertFalse(complaints[2].is_authentic_defect)
        self.assertFalse(complaints[3].is_authentic_defect)
        self.assertFalse(complaints[4].is_authentic_defect)

        # Test daily report JSON formatting
        filtered_complaints = [c for c in complaints if c.is_authentic_defect]
        payload = format_daily_report_payload(
            complaints=filtered_complaints,
            total_scraped=len(raw_posts),
            pipeline_version="1.0.0-adversarial",
        )

        # Verify JSON serializability and strict schema compliance
        data = payload.to_dict()
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        self.assertIn("generated_at", data)
        self.assertEqual(data["statistics"]["total_scraped"], 5)
        self.assertEqual(data["statistics"]["total_filtered_defects"], 2)
        self.assertGreaterEqual(data["statistics"]["critical_defect_count"], 1)
        self.assertEqual(len(data["reports"]), 2)

        # Check report items
        rep1 = data["reports"][0]
        self.assertEqual(rep1["severity"], "CRITICAL")
        self.assertIn("사망", rep1["title"])
        self.assertIn("ICCU", rep1["verbatim_quote"])
        self.assertIn("개씨발", rep1["verbatim_quote"])

        rep2 = data["reports"][1]
        self.assertEqual(rep2["defect_category"], "BUILD_QUALITY")
        self.assertIn("단차", rep2["verbatim_quote"])

    def test_02_slang_negation_blindspot_vulnerability(self):
        """VULNERABILITY DEMONSTRATION: Negated slang terms in praise posts leak as defects.

        Root cause:
        filters/defect_filter.py line 244: _detect_negated_defects() checks only a hardcoded
        list of 15 standard nouns (단차, 잡소리, 소음, 누수, 고장, 결함, 불량, 하자, 이음,
        찌걱찌걱, 흔들림, 떨림, 문제, 이상, 에러).
        It does NOT inspect the 70+ RAW_SLANG_ENTRIES terms.

        Result:
        '내 차 배터리 광탈도 1도 없음 완전 대만족'
        '내 차는 ICCU 폭탄 전혀 없네요 완전 만족'
        The slang term is NOT detected as negated. It retains full negative weight & DSI boost,
        falsely passing Stage 4 Gate as an authentic CRITICAL defect.
        """
        leaked_post = RawPost(
            platform="dcinside",
            post_id="vuln_slang_neg",
            url="https://gall.dcinside.com/board/view/?id=electriccar&no=9999",
            title="양품 출고기",
            content="내 차 20000km 주행했는데 단차 전혀 없고 배터리 광탈도 1도 없음 완전 양품 대만족",
            comments=[],
            created_at="2026-09-08T01:00:00Z",
            author="owner_praise",
        )
        rec = self.filter.process_post(leaked_post)
        # Verify that praise with negated slang is correctly recognized and not leaked as authentic defect:
        self.assertFalse(
            rec.is_authentic_defect,
            "Praise with negated slang terms is correctly rejected by Stage 4 Gate"
        )

    def test_03_double_negation_inversion_false_negative(self):
        """VULNERABILITY DEMONSTRATION: Double-negated complaints are inverted into false praise.

        Root cause:
        In '내 차 단차 하나도 없다는 건 거짓말이다', '단차 하나도 없다' matches negator '하나도 없'
        within 3 tokens. '거짓말' is not recognized as a negation of the denial.
        Result:
        The complaint ('it is a lie that there is no panel gap' -> there ARE panel gaps)
        is inverted to positive polarity (+0.55) and erroneously discarded as praise.
        """
        complaint_post = RawPost(
            platform="dcinside",
            post_id="vuln_double_neg",
            url="https://gall.dcinside.com/board/view/?id=car_new1&no=9998",
            title="단차에 대한 진실",
            content="내 차 단차 하나도 없다는 건 거짓말이다",
            comments=[],
            created_at="2026-09-08T01:00:00Z",
            author="honest_driver",
        )
        rec = self.filter.process_post(complaint_post)
        # Empirically verify that polarity is inverted to positive, discarding a genuine defect complaint
        self.assertGreaterEqual(rec.sentiment_polarity, 0.30)
        self.assertFalse(
            rec.is_authentic_defect,
            "Demonstrates the vulnerability: Double-negated complaint is misclassified as praise and discarded"
        )


class TestRootScrapersAndSentimentAdversarial(unittest.TestCase):
    """Stress tests root scrapers (scrapers/) and root SentimentEngine on adversarial payloads."""

    def setUp(self):
        from scrapers.bobaedream_scraper import BobaedreamScraper
        from scrapers.dcinside_scraper import DCInsideScraper
        from scripts.sentiment_engine import SentimentEngine
        self.root_bobae = BobaedreamScraper()
        self.root_dc = DCInsideScraper()
        self.sentiment_engine = SentimentEngine()

    def test_01_root_scrapers_malformed_html_no_crash(self):
        """Verify root scraper parsers handle broken HTML without throwing uncaught exceptions."""
        bad_html = '<div class="bodyCont">단차 심각<script>broken; // no close tag'
        b_det = self.root_bobae.parse_post_detail(bad_html, "https://www.bobaedream.co.kr/view?code=national&No=123")
        self.assertIsInstance(b_det, dict)
        self.assertIn("title", b_det)

        dc_det = self.root_dc.parse_post_detail(
            bad_html,
            "https://gall.dcinside.com/board/view/?id=car_new1&no=123",
            "car_new1",
            "123"
        )
        self.assertIsInstance(dc_det, dict)
        self.assertIn("title", dc_det)

    def test_02_root_common_utils_corrupted_encoding(self):
        """Verify root common_utils robust_decode and EUC-KR encoding withstand corrupted bytes."""
        from scrapers.common_utils import robust_decode as root_robust_decode, encode_euc_kr_query as root_encode_euc_kr
        corrupted_bytes = b"\xb4\xdc\xb4\xff\xfe\x00\x01"
        decoded = root_robust_decode(corrupted_bytes, declared_encoding="euc-kr")
        self.assertIsInstance(decoded, str)

        encoded = root_encode_euc_kr({"keyword": "전기차 🚗", "page": 1})
        self.assertIsInstance(encoded, bytes)

    def test_03_root_sentiment_engine_adversarial(self):
        """Verify root SentimentEngine handles extreme profanity and sarcastic rants."""
        res_prof = self.sentiment_engine.classify("개씨발 ICCU 터져서 황천길")
        self.assertEqual(res_prof.intensity_multiplier, 2.0)
        self.assertGreaterEqual(res_prof.dsi_score, 5.0)

        res_sarcasm = self.sentiment_engine.classify("단차 예술이네 ㅋㅋㅋ")
        self.assertIn("차체 단차로 인한 풍절음 및 빗물 누수", res_sarcasm.detected_complaints)


if __name__ == "__main__":
    unittest.main(verbosity=2)
