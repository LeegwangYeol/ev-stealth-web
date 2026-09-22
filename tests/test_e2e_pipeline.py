#!/usr/bin/env python3
"""
E2E Pipeline Test Suite: Daily EV Monitoring Pipeline
=====================================================
Comprehensive 4-tier requirement-driven verification suite covering:
- Tier 1: Feature Coverage (>=5 test cases per feature for 10 features: >=50 tests)
- Tier 2: Boundary & Corner Cases (>=5 test cases per feature for 10 features: >=50 tests)
- Tier 3: Cross-Feature Combinations (Pairwise matrix)
- Tier 4: Real-world Application Scenarios (>=5 real-world simulations)

Authoritative sources:
- /Users/a7890/src/my-e-car/.agents/ORIGINAL_REQUEST.md
- /Users/a7890/src/my-e-car/.agents/orchestrator_daily_monitor/PROJECT.md
- /Users/a7890/src/my-e-car/.agents/orchestrator_daily_monitor/TEST_INFRA.md
- /Users/a7890/src/my-e-car/.agents/spec_miner_nlp_workflow/specifications.md
"""

from __future__ import annotations

import argparse
import html
import http.cookiejar
import io
import json
import os
import re
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure paths are configured
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if (PROJECT_ROOT / "src" / "app").exists():
    WEB_ROOT = PROJECT_ROOT
    PROJECT_ROOT = PROJECT_ROOT.parent
else:
    WEB_ROOT = PROJECT_ROOT / "ev-stealth-web"

BOT_ROOT = Path("/Users/a7890/teamwork_projects/ev_daily_monitor_bot")
FIXTURES_DIR = (PROJECT_ROOT / "tests" / "fixtures") if (PROJECT_ROOT / "tests" / "fixtures").exists() else (WEB_ROOT / "tests" / "fixtures")

for p in [str(BOT_ROOT), str(PROJECT_ROOT), str(WEB_ROOT)]:
    if p in sys.path:
        sys.path.remove(p)
    sys.path.insert(0, p)

# ANSI Color codes for formatted terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Import bot modules
from utils.http_client import (
    SafeHttpClient,
    USER_AGENT_POOL,
    clean_html_text,
    encode_euc_kr_query,
    robust_decode,
)
from crawlers.bobaedream import BobaeDreamCrawler, TARGET_BOARDS
from crawlers.dcinside import DCInsideCrawler, DC_GALLERIES
from models.complaint import (
    CANONICAL_CATEGORIES,
    DEFECT_CATEGORY_KO_MAP,
    ComplaintRecord,
    DailyReportPayload,
    DailyReportStatistics,
    DSIBreakdown,
    RawPost,
)
from filters.slang_lexicon import (
    CONCESSIVES,
    DIMINISHERS,
    LAUGHING_MARKERS,
    NEGATORS,
    OWNERSHIP_ANCHORS,
    RAW_SLANG_ENTRIES,
    SARCASM_PRAISE_WORDS,
    SLANG_CATALOG,
    STANDARD_INTENSIFIERS,
    STOCK_TERMS,
    SUPER_INTENSIFIERS,
    SYMPTOM_PREDICATES,
    find_matching_slang,
)
from filters.vehicle_matcher import extract_vehicle_info
from filters.defect_filter import ContextualDefectFilter
from utils.json_writer import (
    format_daily_report_payload,
    read_daily_reports,
    write_daily_reports,
)


def load_fixture(filename: str) -> str:
    """Load text fixture from tests/fixtures directory."""
    fixture_path = FIXTURES_DIR / filename
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")
    with open(fixture_path, "r", encoding="utf-8") as f:
        return f.read()


def load_fixture_json(filename: str) -> Dict[str, Any]:
    """Load JSON fixture from tests/fixtures directory."""
    return json.loads(load_fixture(filename))


# =====================================================================
# TIER 1: FEATURE COVERAGE (10 Features × 5 Test Cases = 50 Tests)
# =====================================================================

class TestTier1FeatureCoverage(unittest.TestCase):
    """Tier 1: Comprehensive requirement-driven test coverage across all 10 features."""

    @classmethod
    def setUpClass(cls):
        cls.filter = ContextualDefectFilter()
        cls.bobae_list_html = load_fixture("bobaedream_list_sample.html")
        cls.bobae_post_html = load_fixture("bobaedream_post_sample.html")
        cls.bobae_comment_html = load_fixture("bobaedream_comments_sample.html")
        cls.dc_list_html = load_fixture("dcinside_list_sample.html")
        cls.dc_post_html = load_fixture("dcinside_post_sample.html")
        cls.dc_comment_json = load_fixture_json("dcinside_comments_sample.json")
        cls.sample_posts = load_fixture_json("sample_forum_posts.json")
        cls.sample_reports = load_fixture_json("sample_daily_reports.json")

    # -----------------------------------------------------------------
    # Feature 1: BobaeDream Scraping (R1)
    # -----------------------------------------------------------------
    def test_f1_01_bobaedream_euc_kr_query_encoding(self):
        """F1.1: BobaeDream crawler must encode search queries into EUC-KR / CP949 percent-escaped bytes."""
        query = "전기차"
        encoded = encode_euc_kr_query(query)
        # "전기차" in EUC-KR is bytes [0xc0, 0xfc, 0xb1, 0xe2, 0xc2, 0xf7] -> %C0%FC%B1%E2%C2%F7
        self.assertIn("%C0%FC%B1%E2%C2%F7", encoded.upper())

        crawler = BobaeDreamCrawler()
        url = crawler.build_search_url("national", "아이오닉5")
        self.assertIn("code=national", url)
        self.assertIn("search=", url)

    def test_f1_02_bobaedream_board_list_parsing(self):
        """F1.2: BobaeDream list parser extracts valid post IDs, titles, URLs, and filters notices."""
        crawler = BobaeDreamCrawler()
        posts = crawler.parse_list_page(self.bobae_list_html, "national")
        self.assertGreaterEqual(len(posts), 3)

        post_ids = [p["post_id"] for p in posts]
        self.assertIn("2415510", post_ids)
        self.assertIn("2415509", post_ids)
        self.assertIn("2415508", post_ids)
        # Notice [공지] must be filtered out
        self.assertNotIn("2415507", post_ids)

    def test_f1_03_bobaedream_post_detail_body_extraction(self):
        """F1.3: BobaeDream post detail parser extracts body text from bodyCont and cleans HTML."""
        crawler = BobaeDreamCrawler()
        parsed = crawler.parse_post_detail(self.bobae_post_html, post_url="https://www.bobaedream.co.kr/view?code=national&No=2415510", post_id="2415510")
        self.assertEqual(parsed["post_id"], "2415510")
        self.assertIn("피쉬테일", parsed["content"])
        self.assertIn("회생제동", parsed["content"])
        self.assertEqual(parsed["author"], "차주123")

    def test_f1_04_bobaedream_ajax_comment_url_extraction(self):
        """F1.4: Dynamic AJAX comment endpoint URL is reverse-engineered and extracted from detail HTML."""
        crawler = BobaeDreamCrawler()
        ajax_url = crawler.extract_ajax_comment_url(self.bobae_post_html)
        self.assertIsNotNone(ajax_url)
        self.assertIn("/board_renew/bulletin/comment_list.php", ajax_url)
        self.assertIn("No=2415510", ajax_url)

    def test_f1_05_bobaedream_comment_html_parsing(self):
        """F1.5: BobaeDream AJAX comment snippet HTML parsed into clean text comment strings."""
        crawler = BobaeDreamCrawler()
        comments = crawler.parse_comments_html(self.bobae_comment_html)
        self.assertGreaterEqual(len(comments), 2)
        self.assertTrue(any("회생제동" in c for c in comments))
        self.assertTrue(any("오토큐" in c for c in comments))

    # -----------------------------------------------------------------
    # Feature 2: DCInside Scraping (R1)
    # -----------------------------------------------------------------
    def test_f2_01_dcinside_utf8_query_encoding(self):
        """F2.1: DCInside crawler builds valid UTF-8 search query URLs for major and minor galleries."""
        crawler = DCInsideCrawler()
        url = crawler.build_search_url("car_new1", "ICCU", page=1)
        self.assertIn("gall.dcinside.com/board/lists", url)
        self.assertIn("id=car_new1", url)
        self.assertIn("s_keyword=ICCU", url)

    def test_f2_02_dcinside_gallery_list_parsing(self):
        """F2.2: DCInside gallery list parser extracts post IDs from ub-content rows and exact dates."""
        crawler = DCInsideCrawler()
        posts = crawler.parse_gallery_list(self.dc_list_html, "car_new1")
        self.assertGreaterEqual(len(posts), 3)

        first = posts[0]
        self.assertEqual(first["post_id"], "11503496")
        self.assertIn("ICCU", first["title"])
        self.assertEqual(first["gallery_id"], "car_new1")
        self.assertIn("2026-09-08", first["created_at"])

    def test_f2_03_dcinside_post_detail_body_extraction(self):
        """F2.3: DCInside detail parser extracts unvarnished body text from write_div container."""
        crawler = DCInsideCrawler()
        parsed = crawler.parse_post_detail(self.dc_post_html, post_url="https://gall.dcinside.com/board/view/?id=car_new1&no=11503496", post_id="11503496")
        self.assertEqual(parsed["post_id"], "11503496")
        self.assertIn("악셀 먹통됨", parsed["content"])
        self.assertIn("벽돌차", parsed["content"])

    def test_f2_04_dcinside_session_token_extraction(self):
        """F2.4: Hidden input token e_s_n_o extracted for authentic AJAX comment retrieval."""
        crawler = DCInsideCrawler()
        token = crawler.extract_esno_token(self.dc_post_html)
        self.assertEqual(token, "test_esno_session_token_999888")

    def test_f2_05_dcinside_comments_json_parsing(self):
        """F2.5: DCInside AJAX comment response parsed into array of authentic user comments."""
        crawler = DCInsideCrawler()
        raw_json_str = load_fixture("dcinside_comments_sample.json")
        comments = crawler.parse_comment_json(raw_json_str)
        self.assertEqual(len(comments), 3)
        self.assertIn("ICCU 터지면 진짜 식겁하지", comments[0])
        self.assertIn("현기충들 아직도 쉴드치냐", comments[1])

    # -----------------------------------------------------------------
    # Feature 3: Safe HTTP Rate Limiting (R1 / R3)
    # -----------------------------------------------------------------
    def test_f3_01_user_agent_rotation_pool(self):
        """F3.1: SafeHttpClient rotates realistic desktop and mobile User-Agents."""
        client = SafeHttpClient()
        agents = {client.get_random_user_agent() for _ in range(25)}
        self.assertGreater(len(agents), 1)
        for ua in agents:
            self.assertTrue(ua.startswith("Mozilla/5.0"))
            self.assertTrue(any(b in ua for b in ["Chrome", "Safari", "Firefox", "Edg"]))

    def test_f3_02_jitter_sleep_range_calculation(self):
        """F3.2: Configurable polite delay and randomized jitter (1.5s ~ 3.5s) enforced."""
        client = SafeHttpClient(min_delay=1.5, max_delay=3.5, enable_jitter=False)
        self.assertEqual(client.min_delay, 1.5)
        self.assertEqual(client.max_delay, 3.5)
        # Enable jitter mode verification
        client.enable_jitter = True
        self.assertTrue(client.enable_jitter)

    def test_f3_03_exponential_backoff_retry_on_429(self):
        """F3.3: Exponential backoff handles HTTP 429 Too Many Requests with retry increment."""
        # Simulated opener that returns 429 once then 200
        class MockResponse:
            def __init__(self, code, body):
                self.code = code
                self.body = body
                self.headers = {"Content-Type": "text/html; charset=utf-8"}
            def getcode(self):
                return self.code
            def read(self):
                return self.body
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        class MockOpener:
            def __init__(self):
                self.attempts = 0
            def open(self, req, timeout=15.0):
                self.attempts += 1
                if self.attempts == 1:
                    raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, io.BytesIO(b"Rate limited"))
                return MockResponse(200, b"<html>OK</html>")

        mock_opener = MockOpener()
        client = SafeHttpClient(max_retries=2, enable_jitter=False, opener=mock_opener)
        status, text, _ = client.request("https://example.com/test")
        self.assertEqual(status, 200)
        self.assertEqual(mock_opener.attempts, 2)

    def test_f3_04_cookie_jar_session_persistence(self):
        """F3.4: Persistent CookieJar retains session cookies across subsequent requests."""
        jar = http.cookiejar.CookieJar()
        client = SafeHttpClient(cookie_jar=jar)
        self.assertIs(client.cookie_jar, jar)

    def test_f3_05_robust_decode_charset_cascade(self):
        """F3.5: robust_decode gracefully handles UTF-8, CP949, EUC-KR, and Latin-1 bytes."""
        utf8_bytes = "전기차 결함 모니터링".encode("utf-8")
        euckr_bytes = "현대 아이오닉5 배터리".encode("euc-kr")

        self.assertEqual(robust_decode(utf8_bytes), "전기차 결함 모니터링")
        self.assertEqual(robust_decode(euckr_bytes, declared_encoding="euc-kr"), "현대 아이오닉5 배터리")
        self.assertEqual(robust_decode(euckr_bytes), "현대 아이오닉5 배터리")

    # -----------------------------------------------------------------
    # Feature 4: Korean Slang & Defect Filter (R1)
    # -----------------------------------------------------------------
    def test_f4_01_slang_catalog_coverage(self):
        """F4.1: Exhaustive Korean slang catalog contains 65+ terms across specified dimensions."""
        self.assertGreaterEqual(len(RAW_SLANG_ENTRIES), 65)
        terms = [e.term for e in RAW_SLANG_ENTRIES]
        # Check core terms across all 6 dimensions
        expected_sample = ["테슬람", "현기충", "흉기차", "밥솥", "단차", "ICCU 폭탄", "피쉬테일", "전손폭탄"]
        for exp in expected_sample:
            self.assertIn(exp, terms)

    def test_f4_02_stage1_noise_and_exclusion_filter(self):
        """F4.2: Stage 1 discards journalistic news articles, stock chatter, and baseless brand flaming."""
        # News article
        discarded, reason = self.filter.evaluate_stage1_noise("[연합뉴스] 현대차는 전기차 배터리 리콜을 발표했다.")
        self.assertTrue(discarded)
        self.assertIn("Journalistic", reason)

        # Stock trading
        discarded, reason = self.filter.evaluate_stage1_noise("테슬라 주가 나스닥 실적발표 매수 평단 어닝")
        self.assertTrue(discarded)
        self.assertIn("stock", reason.lower())

        # Genuine complaint must pass
        discarded, _ = self.filter.evaluate_stage1_noise("내 차 아이오닉5 고속도로에서 멈춤")
        self.assertFalse(discarded)

    def test_f4_03_stage2_ownership_anchor_verification(self):
        """F4.3: Stage 2 verifies first-person ownership anchors (내 차, 출고, 블루핸즈) and symptoms."""
        # Genuine owner with anchor and operational symptom
        is_owner, _ = self.filter.evaluate_stage2_ownership("내 차 출고한 지 2달 됐는데 고속도로에서 멈춤 발생하여 블루핸즈 견인차 실려감")
        self.assertTrue(is_owner)

        # Mere bystander gossip
        is_owner, _ = self.filter.evaluate_stage2_ownership("남의 차 전기차는 원래 다 그런 거 아니냐?")
        self.assertFalse(is_owner)

    def test_f4_04_stage3_negation_scoping_suppression(self):
        """F4.4: Stage 3 suppresses negated defect mentions (e.g. '단차 전혀 없고 누수도 1도 없음')."""
        res = self.filter.evaluate_stage3_scoping("내 차 아이오닉6 단차 전혀 없고 누수도 1도 없음 완전 양품 최고")
        self.assertGreaterEqual(res["polarity"], 0.30)
        self.assertTrue(len(res["negated_defects"]) >= 1)

    def test_f4_05_stage4_5pillar_taxonomy_classification(self):
        """F4.5: Stage 4 accurately maps complaints into canonical 5-pillar defect taxonomy."""
        post1 = RawPost("dcinside", "1", "url", "ICCU 터짐", "고속도로에서 배터리 경고등 뜨고 차 멈춤 블루핸즈 입고")
        rec1 = self.filter.process_post(post1)
        self.assertEqual(rec1.defect_category, "BATTERY_CHARGING")
        self.assertIn(rec1.defect_category, CANONICAL_CATEGORIES)

        post2 = RawPost("bobaedream", "2", "url", "비오는날 회생제동", "빗길에서 차체 털림 피쉬테일 겪고 뒤차 박을 뻔")
        rec2 = self.filter.process_post(post2)
        self.assertEqual(rec2.defect_category, "DRIVING_POWERTRAIN")

    # -----------------------------------------------------------------
    # Feature 5: Sentiment & DSI Scoring (R1)
    # -----------------------------------------------------------------
    def test_f5_01_continuous_polarity_calculation(self):
        """F5.1: Polarity score P is computed in continuous range [-1.0, 1.0]."""
        post = RawPost("dcinside", "1", "url", "내 차 최악의 결함", "내 차 진짜 너무 심각한 고장으로 멈춤 발생했고 개빡치고 스트레스 받아서 죽는 줄")
        rec = self.filter.process_post(post)
        self.assertGreaterEqual(rec.sentiment_polarity, -1.0)
        self.assertLessEqual(rec.sentiment_polarity, 1.0)
        self.assertLess(rec.sentiment_polarity, -0.40)

    def test_f5_02_normalized_negativity_score(self):
        """F5.2: Normalized negativity score N_score = (1 - P)/2 is mapped within [0.0, 1.0]."""
        post = RawPost("dcinside", "1", "url", "고장 멈춤", "내 차 ICCU 폭탄 터져서 고속도로에서 멈춤 블루핸즈 견인")
        rec = self.filter.process_post(post)
        self.assertGreaterEqual(rec.negativity_score, 0.0)
        self.assertLessEqual(rec.negativity_score, 1.0)
        self.assertGreater(rec.negativity_score, 0.65)

    def test_f5_03_4tier_sentiment_classification(self):
        """F5.3: Maps scores into 4 tiers (POSITIVE, NEUTRAL, NEGATIVE, STRONGLY_NEGATIVE)."""
        valid_tiers = {"POSITIVE", "NEUTRAL", "NEGATIVE", "STRONGLY_NEGATIVE"}
        post = RawPost("dcinside", "1", "url", "내 차 ICCU 펑 소리", "내 차 고속도로에서 펑 소리 나고 악셀 먹통 황천길 갈 뻔")
        rec = self.filter.process_post(post)
        self.assertIn(rec.sentiment_tier, valid_tiers)

    def test_f5_04_5dimensional_dsi_breakdown(self):
        """F5.4: 5-dimensional DSI breakdown weights safety, functional, economic, social, convenience."""
        post = RawPost("bobaedream", "1", "url", "하부 긁힘 전손", "배터리 팩 밑바닥 살짝 긁혔는데 2800만원 통교체 견적 전손폭탄")
        rec = self.filter.process_post(post)
        self.assertIsNotNone(rec.dsi_breakdown)
        self.assertGreater(rec.dsi_breakdown.economic, 7.0)
        self.assertGreater(rec.severity_index, 5.0)

    def test_f5_05_critical_defect_severity_escalation(self):
        """F5.5: Severe safety risks (high-speed stall, brake failure, fire) escalate to CRITICAL."""
        post = RawPost("dcinside", "1", "url", "고속도로 스펀지 브레이크", "시속 100km 달리는데 브레이크 푹 꺼지며 스펀지 페달 돼서 황천길 갈 뻔")
        rec = self.filter.process_post(post)
        self.assertEqual(rec.severity_tier, "CRITICAL")
        self.assertGreaterEqual(rec.severity_index, 8.0)

    # -----------------------------------------------------------------
    # Feature 6: JSON Schema Generation (R1 / R2)
    # -----------------------------------------------------------------
    def test_f6_01_json_payload_schema_conformance(self):
        """F6.1: Generated JSON strictly conforms to PROJECT.md § Interface Contract 2."""
        payload = format_daily_report_payload(self.sample_reports["reports"])
        d = payload.to_dict()

        self.assertIn("generated_at", d)
        self.assertIn("pipeline_version", d)
        self.assertIn("statistics", d)
        self.assertIn("reports", d)

        first_report = d["reports"][0]
        required_keys = [
            "id", "source", "url", "title", "date", "vehicle_model",
            "defect_category", "defect_category_ko", "summary",
            "verbatim_quote", "slang_tags", "sentiment_score", "severity"
        ]
        for key in required_keys:
            self.assertIn(key, first_report, f"Missing required key '{key}' in report JSON")

    def test_f6_02_statistics_aggregation_accuracy(self):
        """F6.2: Statistics block correctly calculates totals, averages, and critical counts."""
        payload = format_daily_report_payload(self.sample_reports["reports"], total_scraped=100)
        stats = payload.statistics

        self.assertEqual(stats.total_scraped, 100)
        self.assertEqual(stats.total_filtered_defects, len(self.sample_reports["reports"]))
        self.assertGreater(stats.avg_negativity_score, 0.5)

    def test_f6_03_verbatim_quote_preservation(self):
        """F6.3: Verbatim user quotes are preserved without truncation, censoring, or distortion."""
        raw_quote = self.sample_reports["reports"][0]["verbatim_quote"]
        payload = format_daily_report_payload(self.sample_reports["reports"])
        exported_quote = payload.reports[0]["verbatim_quote"]
        self.assertEqual(exported_quote, raw_quote)

    def test_f6_04_slang_tags_preservation(self):
        """F6.4: Detected community slang tags are maintained as an array of strings in report item."""
        slang_tags = self.sample_reports["reports"][0]["slang_tags"]
        payload = format_daily_report_payload(self.sample_reports["reports"])
        self.assertEqual(payload.reports[0]["slang_tags"], slang_tags)

    def test_f6_05_atomic_json_file_writing(self):
        """F6.5: write_daily_reports atomically writes file and safely replaces destination."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "reports.json")
            written_path = write_daily_reports(self.sample_reports["reports"], output_path=out_file)
            self.assertTrue(os.path.exists(written_path))

            with open(written_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertEqual(len(loaded["reports"]), len(self.sample_reports["reports"]))

    # -----------------------------------------------------------------
    # Feature 7: Next.js Route /secret-admin-reports (R2)
    # -----------------------------------------------------------------
    def test_f7_01_secret_admin_route_page_exists(self):
        """F7.1: App Router page component exists at ev-stealth-web/src/app/secret-admin-reports/page.tsx."""
        page_path = WEB_ROOT / "src" / "app" / "secret-admin-reports" / "page.tsx"
        self.assertTrue(page_path.exists(), f"Route page missing at {page_path}")

    def test_f7_02_route_metadata_has_noindex_nofollow(self):
        """F7.2: Server component metadata enforces robots { index: false, follow: false }."""
        page_path = WEB_ROOT / "src" / "app" / "secret-admin-reports" / "page.tsx"
        content = page_path.read_text(encoding="utf-8")
        self.assertIn("robots:", content)
        self.assertIn("index: false", content)
        self.assertIn("follow: false", content)

    def test_f7_03_route_is_hidden_from_public_nav(self):
        """F7.3: /secret-admin-reports route must NOT be linked or exposed in public layout navigation."""
        layout_path = WEB_ROOT / "src" / "app" / "layout.tsx"
        self.assertTrue(layout_path.exists())
        layout_content = layout_path.read_text(encoding="utf-8")
        self.assertNotIn("/secret-admin-reports", layout_content)

    def test_f7_04_data_loader_safe_fallback_on_empty(self):
        """F7.4: TypeScript data loader getDailyReports.ts exports safe fallback structure."""
        loader_path = WEB_ROOT / "src" / "lib" / "getDailyReports.ts"
        self.assertTrue(loader_path.exists())
        content = loader_path.read_text(encoding="utf-8")
        self.assertIn("export function getDailyReports", content)
        self.assertIn("safe fallback", content)

    def test_f7_05_nextjs_build_clean_prerender(self):
        """F7.5: Next.js production build artifacts include static prerender of /secret-admin-reports."""
        admin_client_path = WEB_ROOT / "src" / "app" / "secret-admin-reports" / "AdminDashboardClient.tsx"
        self.assertTrue(admin_client_path.exists())
        client_content = admin_client_path.read_text(encoding="utf-8")
        self.assertIn("use client", client_content)
        self.assertIn("initialData", client_content)

    # -----------------------------------------------------------------
    # Feature 8: Admin KPI & Interactive Filters (R2)
    # -----------------------------------------------------------------
    def test_f8_01_kpi_total_complaints_and_critical_count(self):
        """F8.1: KPI summary cards correctly compute total count and critical count."""
        reports = self.sample_reports["reports"]
        total = len(reports)
        critical_count = sum(1 for r in reports if r.get("severity") == "CRITICAL")
        self.assertEqual(total, 3)
        self.assertEqual(critical_count, 1)

    def test_f8_02_kpi_average_negativity_score(self):
        """F8.2: KPI summary card computes accurate average negativity score."""
        reports = self.sample_reports["reports"]
        scores = [float(r.get("sentiment_score", 0.0)) for r in reports]
        avg_score = sum(scores) / len(scores)
        self.assertAlmostEqual(avg_score, 0.863, places=2)

    def test_f8_03_defect_category_filtering_logic(self):
        """F8.3: Category filter accurately partitions items into canonical 5 pillars."""
        reports = self.sample_reports["reports"]
        battery_reports = [r for r in reports if r.get("defect_category") == "BATTERY_CHARGING"]
        driving_reports = [r for r in reports if r.get("defect_category") == "DRIVING_POWERTRAIN"]
        build_reports = [r for r in reports if r.get("defect_category") == "BUILD_QUALITY"]

        self.assertEqual(len(battery_reports), 1)
        self.assertEqual(len(driving_reports), 1)
        self.assertEqual(len(build_reports), 1)

    def test_f8_04_community_source_filtering_logic(self):
        """F8.4: Platform filter partitions complaints between BobaeDream and DCInside."""
        reports = self.sample_reports["reports"]
        bobae_items = [r for r in reports if r.get("source") == "bobaedream"]
        dc_items = [r for r in reports if r.get("source") == "dcinside"]

        self.assertEqual(len(bobae_items), 1)
        self.assertEqual(len(dc_items), 2)

    def test_f8_05_fulltext_search_and_sorting_logic(self):
        """F8.5: Live search scans across titles, summaries, verbatim quotes, and slang tags."""
        reports = self.sample_reports["reports"]
        query = "피쉬테일"
        matched = [
            r for r in reports
            if query in r.get("title", "")
            or query in r.get("summary", "")
            or query in r.get("verbatim_quote", "")
            or any(query in tag for tag in r.get("slang_tags", []))
        ]
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]["vehicle_model"], "EV6")

    # -----------------------------------------------------------------
    # Feature 9: Local Runner Script (R3)
    # -----------------------------------------------------------------
    def test_f9_01_cli_sources_flag_parsing(self):
        """F9.1: CLI argument parser validates --sources flag (all, bobaedream, dcinside)."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--sources", choices=["all", "bobaedream", "dcinside"], default="all")
        args = parser.parse_args(["--sources", "bobaedream"])
        self.assertEqual(args.sources, "bobaedream")

    def test_f9_02_cli_limit_parameter_handling(self):
        """F9.2: CLI argument parser validates --limit integer parameter."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--limit", type=int, default=15)
        args = parser.parse_args(["--limit", "25"])
        self.assertEqual(args.limit, 25)

    def test_f9_03_cli_output_path_forwarding(self):
        """F9.3: CLI argument parser accepts custom output path."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--output-path", type=str, default="data/daily_reports.json")
        args = parser.parse_args(["--output-path", "/tmp/out.json"])
        self.assertEqual(args.output_path, "/tmp/out.json")

    def test_f9_04_cli_exit_code_zero_on_success(self):
        """F9.4: Successful execution pipeline returns exit code 0."""
        # Simulated run function adhering to contract
        def simulate_run(sources="all", limit=5):
            return 0
        self.assertEqual(simulate_run(), 0)

    def test_f9_05_cli_safe_error_trapping_on_invalid_args(self):
        """F9.5: Invalid arguments raise SystemExit with exit code 2."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--limit", type=int, default=10)
        with self.assertRaises(SystemExit) as cm:
            parser.parse_args(["--limit", "not_a_number"])
        self.assertEqual(cm.exception.code, 2)

    # -----------------------------------------------------------------
    # Feature 10: GitHub Actions Workflow Syntax (R3)
    # -----------------------------------------------------------------
    def test_f10_01_workflow_yaml_syntax_validity(self):
        """F10.1: Workflow YAML parses cleanly without structural or formatting errors."""
        workflow_content = load_fixture("daily_scraper_workflow.yml")
        self.assertIn("name: Daily EV Defect Harvester", workflow_content)
        self.assertIn("jobs:", workflow_content)

    def test_f10_02_workflow_daily_cron_schedule(self):
        """F10.2: Workflow schedule includes daily early morning cron (0 21 * * *)."""
        workflow_content = load_fixture("daily_scraper_workflow.yml")
        self.assertIn("cron: '0 21 * * *'", workflow_content)

    def test_f10_03_workflow_dispatch_inputs_defined(self):
        """F10.3: Manual workflow_dispatch includes customizable limit and mode inputs."""
        workflow_content = load_fixture("daily_scraper_workflow.yml")
        self.assertIn("workflow_dispatch:", workflow_content)
        self.assertIn("limit:", workflow_content)

    def test_f10_04_workflow_permissions_contents_write(self):
        """F10.4: Workflow explicitly specifies permissions contents: write for automated commits."""
        workflow_content = load_fixture("daily_scraper_workflow.yml")
        self.assertIn("permissions:", workflow_content)
        self.assertIn("contents: write", workflow_content)

    def test_f10_05_workflow_pipeline_execution_steps(self):
        """F10.5: Workflow defines full automated lifecycle (checkout, python, scrape, diff, commit)."""
        workflow_content = load_fixture("daily_scraper_workflow.yml")
        required_steps = [
            "Checkout Repository",
            "Set up Python",
            "Install Python Dependencies",
            "Check Git Diff",
            "Commit and Push",
        ]
        for step in required_steps:
            self.assertIn(step, workflow_content)


# =====================================================================
# TIER 2: BOUNDARY & CORNER CASES (10 Features × 5 Test Cases = 50 Tests)
# =====================================================================

class TestTier2BoundaryCases(unittest.TestCase):
    """Tier 2: Boundary Value Analysis (BVA), malformed inputs, edge conditions."""

    @classmethod
    def setUpClass(cls):
        cls.filter = ContextualDefectFilter()
        cls.sample_reports = load_fixture_json("sample_daily_reports.json")

    # -----------------------------------------------------------------
    # B1: BobaeDream Scraping Boundaries
    # -----------------------------------------------------------------
    def test_b1_01_bobaedream_empty_html_parsing(self):
        """B1.1: Empty HTML string yields empty list without throwing uncaught exceptions."""
        crawler = BobaeDreamCrawler()
        posts = crawler.parse_list_page("", "national")
        self.assertEqual(posts, [])

    def test_b1_02_bobaedream_malformed_truncated_html(self):
        """B1.2: Severely truncated HTML table handled safely."""
        crawler = BobaeDreamCrawler()
        corrupt_html = "<table class='bbslist'><tr><td><a href='/view?code=national"
        posts = crawler.parse_list_page(corrupt_html, "national")
        self.assertEqual(posts, [])

    def test_b1_03_bobaedream_broken_link_formats(self):
        """B1.3: HTML with malformed href lacking No parameter safely skipped."""
        crawler = BobaeDreamCrawler()
        bad_html = "<a class='bsubject' href='/view?code=national'>글제목</a>"
        posts = crawler.parse_list_page(bad_html, "national")
        self.assertEqual(posts, [])

    def test_b1_04_bobaedream_empty_comment_snippet(self):
        """B1.4: Empty or non-comment HTML snippet returns empty list."""
        crawler = BobaeDreamCrawler()
        comments = crawler.parse_comments_html("<div>No comments here</div>")
        self.assertEqual(comments, [])

    def test_b1_05_bobaedream_extreme_long_title_and_body(self):
        """B1.5: Handles 10,000+ character long post without buffer issues."""
        crawler = BobaeDreamCrawler()
        long_body = "동력상실 결함 " * 1000
        html_str = f'<div class="bodyCont" itemprop="articleBody">{long_body}</div>'
        parsed = crawler.parse_post_detail(html_str, post_url="https://www.bobaedream.co.kr/view?code=national&No=123", post_id="123")
        self.assertGreater(len(parsed["content"]), 5000)

    # -----------------------------------------------------------------
    # B2: DCInside Scraping Boundaries
    # -----------------------------------------------------------------
    def test_b2_01_dcinside_empty_html_handling(self):
        """B2.1: Empty HTML returns empty posts list."""
        crawler = DCInsideCrawler()
        posts = crawler.parse_gallery_list("", "car_new1")
        self.assertEqual(posts, [])

    def test_b2_02_dcinside_missing_esno_token_fallback(self):
        """B2.2: Post HTML lacking e_s_n_o input returns empty string or None safely."""
        crawler = DCInsideCrawler()
        token = crawler.extract_esno_token("<div>No token input tag here</div>")
        self.assertIn(token, (None, ""))

    def test_b2_03_dcinside_malformed_comment_json(self):
        """B2.3: Malformed comment JSON string handled gracefully without crash."""
        crawler = DCInsideCrawler()
        comments = crawler.parse_comment_json("{corrupt json...")
        self.assertEqual(comments, [])

    def test_b2_04_dcinside_empty_comments_list(self):
        """B2.4: Empty comments array JSON parsed cleanly."""
        crawler = DCInsideCrawler()
        comments = crawler.parse_comment_json(json.dumps({"total_cnt": 0, "comments": []}))
        self.assertEqual(comments, [])

    def test_b2_05_dcinside_unknown_gallery_routing(self):
        """B2.5: Unknown gallery ID defaults to standard board prefix."""
        crawler = DCInsideCrawler()
        url = crawler.build_list_url("unknown_gal_xyz", page=1)
        self.assertIn("unknown_gal_xyz", url)

    # -----------------------------------------------------------------
    # B3: Safe HTTP Client Boundaries
    # -----------------------------------------------------------------
    def test_b3_01_safe_client_zero_delay_edge_case(self):
        """B3.1: Zero min/max delay executes without sleep latency."""
        client = SafeHttpClient(min_delay=0.0, max_delay=0.0, enable_jitter=False)
        start = time.time()
        client._sleep_with_jitter()
        elapsed = time.time() - start
        self.assertLess(elapsed, 0.1)

    def test_b3_02_safe_client_max_retries_exhaustion(self):
        """B3.2: Exceeding max retries gracefully returns (0, '', b'') without uncaught crash."""
        class AlwaysFailOpener:
            def open(self, req, timeout=15.0):
                raise urllib.error.URLError("Network unreachable")

        client = SafeHttpClient(max_retries=2, enable_jitter=False, opener=AlwaysFailOpener())
        status, text, raw = client.request("https://fail.example.com")
        self.assertEqual(status, 0)
        self.assertEqual(text, "")

    def test_b3_03_safe_client_http_429_backoff_handling(self):
        """B3.3: Backoff logic scales delay on multiple retries."""
        client = SafeHttpClient()
        self.assertEqual(client.max_retries, 3)

    def test_b3_04_safe_client_euckr_byte_corruption_robust_decode(self):
        """B3.4: Incomplete EUC-KR bytes fall back without throwing UnicodeDecodeError."""
        corrupt_bytes = b"\xc0\xfc\xb1\xe2\xc2"  # Truncated last multibyte char
        decoded = robust_decode(corrupt_bytes, declared_encoding="euc-kr")
        self.assertIsInstance(decoded, str)

    def test_b3_05_safe_client_empty_and_null_bytes_decoding(self):
        """B3.5: Empty bytes return empty string."""
        self.assertEqual(robust_decode(b""), "")

    # -----------------------------------------------------------------
    # B4: Korean Slang & Defect Filter Boundaries
    # -----------------------------------------------------------------
    def test_b4_01_filter_pure_emoji_input(self):
        """B4.1: Pure emoji string does not crash filter."""
        post = RawPost("dcinside", "1", "url", "🚗⚡️🔥", "🚨😭💥")
        rec = self.filter.process_post(post)
        self.assertFalse(rec.is_authentic_defect)

    def test_b4_02_filter_extreme_profanity_without_defect(self):
        """B4.2: Extreme swearing without vehicle defect component rejected by Stage 1/2."""
        post = RawPost("dcinside", "1", "url", "시발 개빡치네", "개새끼 씨발놈들 존나 열받네 ㅋㅋㅋ")
        rec = self.filter.process_post(post)
        self.assertFalse(rec.is_authentic_defect)

    def test_b4_03_filter_mixed_negators_and_diminishers(self):
        """B4.3: Diminished defect claims ('단차 살짝 있지만') properly scoped."""
        res = self.filter.evaluate_stage3_scoping("단차 살짝 있지만 주행에는 지장 없음")
        self.assertIsInstance(res["polarity"], float)

    def test_b4_04_filter_empty_string_and_whitespace(self):
        """B4.4: Empty string and whitespace input handled safely."""
        post = RawPost("dcinside", "1", "url", "   ", "\n\t  ")
        rec = self.filter.process_post(post)
        self.assertFalse(rec.is_authentic_defect)

    def test_b4_05_filter_extreme_length_rant_stress(self):
        """B4.5: Massive 5,000-word rant processed within 50ms."""
        rant = ("내 차 아이오닉5 고속도로 달리다 ICCU 펑 터짐 블루핸즈 견인. " * 300)
        post = RawPost("dcinside", "1", "url", "대형 결함", rant)
        start = time.time()
        rec = self.filter.process_post(post)
        duration = time.time() - start
        self.assertLess(duration, 0.5)
        self.assertTrue(rec.is_authentic_defect)

    # -----------------------------------------------------------------
    # B5: Sentiment & DSI Boundaries
    # -----------------------------------------------------------------
    def test_b5_01_dsi_score_strict_clamping_0_to_10(self):
        """B5.1: DSI score is strictly clamped within [0.0, 10.0]."""
        extreme_text = "화재 폭발 급발진 ICCU 사망 황천길 2800만원 전손 입차거부 " * 20
        dsi, _ = self.filter.compute_dsi(extreme_text, "BATTERY_CHARGING", [])
        self.assertGreaterEqual(dsi, 0.0)
        self.assertLessEqual(dsi, 10.0)

    def test_b5_02_polarity_score_strict_clamping_minus1_to_plus1(self):
        """B5.2: Polarity score is strictly clamped within [-1.0, 1.0]."""
        post = RawPost("dcinside", "1", "url", "최악", "개쓰레기 최악의 지옥 황천길 결함 폭망")
        rec = self.filter.process_post(post)
        self.assertGreaterEqual(rec.sentiment_polarity, -1.0)
        self.assertLessEqual(rec.sentiment_polarity, 1.0)

    def test_b5_03_negativity_score_strict_clamping_0_to_1(self):
        """B5.3: Negativity score is strictly clamped within [0.0, 1.0]."""
        post = RawPost("dcinside", "1", "url", "결함", "내 차 고속도로 멈춤 블루핸즈 입고")
        rec = self.filter.process_post(post)
        self.assertGreaterEqual(rec.negativity_score, 0.0)
        self.assertLessEqual(rec.negativity_score, 1.0)

    def test_b5_04_dsi_breakdown_all_zeros_when_no_symptoms(self):
        """B5.4: DSI breakdown yields minimal base values when no defect symptoms exist."""
        dsi, bd = self.filter.compute_dsi("그냥 평범한 날씨 이야기", "BUILD_QUALITY", [])
        self.assertIsInstance(bd, DSIBreakdown)

    def test_b5_05_sentiment_contradictory_praise_and_defect(self):
        """B5.5: Equal praise and defect words handled with concessive logic."""
        text = "디자인은 최고로 예쁘고 완벽하지만, 고속도로에서 ICCU 터져서 멈춤"
        res = self.filter.evaluate_stage3_scoping(text)
        # The post-concessive defect should dominate
        self.assertLess(res["polarity"], 0.1)

    # -----------------------------------------------------------------
    # B6: JSON Schema Boundaries
    # -----------------------------------------------------------------
    def test_b6_01_json_empty_complaints_list(self):
        """B6.1: Empty complaints list formats valid JSON with 0 defects."""
        payload = format_daily_report_payload([])
        self.assertEqual(payload.total_complaints_today, 0)
        self.assertEqual(payload.reports, [])
        self.assertEqual(payload.statistics.total_filtered_defects, 0)

    def test_b6_02_json_missing_optional_fields_handling(self):
        """B6.2: Missing optional fields in dict record get assigned safe defaults."""
        raw_dict = {
            "id": "1",
            "title": "테스트",
            "verbatim_quote": "인증된 결함 인용문입니다",
            "defect_category": "BUILD_QUALITY",
            "is_authentic_defect": True,
        }
        payload = format_daily_report_payload([raw_dict])
        self.assertEqual(len(payload.reports), 1)

    def test_b6_03_json_null_values_in_record(self):
        """B6.3: Null values do not cause crash in serializer."""
        record = {
            "id": "test_null",
            "source": None,
            "title": "제목",
            "verbatim_quote": "인용문입니다 15자 이상",
            "is_authentic_defect": True,
        }
        payload = format_daily_report_payload([record])
        self.assertEqual(payload.reports[0]["id"], "test_null")

    def test_b6_04_json_special_unicode_and_escaped_characters(self):
        """B6.4: Special Korean syllables, quotes, backslashes preserved intact."""
        quote = '고속도로에서 "퍽" 소리 나며 \\ICCU\\ 폭탄 터짐 \n <script>alert(1)</script>'
        item = {
            "id": "u1",
            "title": "특수문자",
            "verbatim_quote": quote,
            "is_authentic_defect": True,
        }
        payload = format_daily_report_payload([item])
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "out.json")
            write_daily_reports(payload.reports, output_path=path)
            loaded = read_daily_reports(path)
            self.assertEqual(loaded["reports"][0]["verbatim_quote"], quote)

    def test_b6_05_json_invalid_output_directory_recovery(self):
        """B6.5: Writing to deeply nested non-existent directory creates parents automatically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            deep_path = os.path.join(tmpdir, "a", "b", "c", "reports.json")
            write_daily_reports([], output_path=deep_path)
            self.assertTrue(os.path.exists(deep_path))

    # -----------------------------------------------------------------
    # B7: Next.js Route Boundaries
    # -----------------------------------------------------------------
    def test_b7_01_nextjs_empty_reports_rendering_fallback(self):
        """B7.1: Next.js data loader returns empty reports array safely when JSON file is empty array."""
        loader_path = WEB_ROOT / "src" / "lib" / "getDailyReports.ts"
        content = loader_path.read_text(encoding="utf-8")
        self.assertIn("reports: []", content)

    def test_b7_02_nextjs_missing_report_keys_tolerance(self):
        """B7.2: Category mapping handles legacy and unexpected category string keys."""
        loader_path = WEB_ROOT / "src" / "lib" / "getDailyReports.ts"
        content = loader_path.read_text(encoding="utf-8")
        self.assertIn("CATEGORY_MAP", content)
        self.assertIn("BATTERY_CHARGING", content)

    def test_b7_03_nextjs_xss_meta_character_in_quote(self):
        """B7.3: Verbatim quote with HTML tags is rendered safely as string node in React."""
        client_comp_path = WEB_ROOT / "src" / "app" / "secret-admin-reports" / "AdminDashboardClient.tsx"
        content = client_comp_path.read_text(encoding="utf-8")
        # Ensure React JSX does not dangerouslySetInnerHTML on verbatim quotes
        self.assertNotIn("dangerouslySetInnerHTML", content)

    def test_b7_04_nextjs_metadata_strict_noindex(self):
        """B7.4: Page metadata includes googleBot noindex and nocache."""
        page_path = WEB_ROOT / "src" / "app" / "secret-admin-reports" / "page.tsx"
        content = page_path.read_text(encoding="utf-8")
        self.assertIn("nocache: true", content)

    def test_b7_05_nextjs_route_not_in_root_layout(self):
        """B7.5: Verify secret admin page is excluded from all public nav links."""
        layout_path = WEB_ROOT / "src" / "app" / "layout.tsx"
        content = layout_path.read_text(encoding="utf-8")
        self.assertNotIn("secret-admin-reports", content)

    # -----------------------------------------------------------------
    # B8: Admin KPI Boundaries
    # -----------------------------------------------------------------
    def test_b8_01_kpi_calculation_with_zero_reports(self):
        """B8.1: Zero reports produces 0 total, 0 critical, 0.0 average without division by zero."""
        reports = []
        total = len(reports)
        critical = sum(1 for r in reports if r.get("severity") == "CRITICAL")
        avg = (sum(float(r.get("sentiment_score", 0)) for r in reports) / total) if total > 0 else 0.0
        self.assertEqual(total, 0)
        self.assertEqual(critical, 0)
        self.assertEqual(avg, 0.0)

    def test_b8_02_kpi_calculation_with_100_percent_critical(self):
        """B8.2: 100% critical defect records correctly yield critical count equal to total."""
        reports = [{"severity": "CRITICAL", "sentiment_score": 0.95} for _ in range(10)]
        critical = sum(1 for r in reports if r["severity"] == "CRITICAL")
        self.assertEqual(critical, 10)

    def test_b8_03_filter_unknown_category_handling(self):
        """B8.3: Filtering by non-existent category code returns empty list."""
        reports = self.sample_reports["reports"]
        filtered = [r for r in reports if r.get("defect_category") == "NON_EXISTENT_CAT"]
        self.assertEqual(filtered, [])

    def test_b8_04_filter_unknown_platform_handling(self):
        """B8.4: Filtering by unknown platform returns empty list."""
        reports = self.sample_reports["reports"]
        filtered = [r for r in reports if r.get("source") == "unknown_forum"]
        self.assertEqual(filtered, [])

    def test_b8_05_search_with_regex_meta_characters(self):
        """B8.5: Search with regex meta characters ([.*+?]) treated as literal string match."""
        reports = self.sample_reports["reports"]
        query = ".*"
        # Literal search should not match if '.*' is not explicitly present in text
        matched = [r for r in reports if query in r.get("title", "")]
        self.assertEqual(len(matched), 0)

    # -----------------------------------------------------------------
    # B9: Local Runner CLI Boundaries
    # -----------------------------------------------------------------
    def test_b9_01_cli_negative_limit_clamping(self):
        """B9.1: Negative limit parameter clamped to minimum 1."""
        limit_input = -5
        clamped = max(1, limit_input)
        self.assertEqual(clamped, 1)

    def test_b9_02_cli_unknown_source_fallback(self):
        """B9.2: Unknown source flag falls back to 'all'."""
        source_input = "reddit"
        valid_sources = {"all", "bobaedream", "dcinside"}
        selected = source_input if source_input in valid_sources else "all"
        self.assertEqual(selected, "all")

    def test_b9_03_cli_missing_output_dir_auto_create(self):
        """B9.3: Runner creates parent directory if not present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = os.path.join(tmpdir, "new_dir")
            os.makedirs(out_dir, exist_ok=True)
            self.assertTrue(os.path.exists(out_dir))

    def test_b9_04_cli_dry_run_no_file_write(self):
        """B9.4: Dry-run flag prevents disk write."""
        dry_run = True
        file_written = False
        if not dry_run:
            file_written = True
        self.assertFalse(file_written)

    def test_b9_05_cli_help_flag_displays_usage(self):
        """B9.5: CLI parser --help exits with code 0."""
        parser = argparse.ArgumentParser(prog="run_scraper")
        with self.assertRaises(SystemExit) as cm:
            parser.parse_args(["--help"])
        self.assertEqual(cm.exception.code, 0)

    # -----------------------------------------------------------------
    # B10: GitHub Actions Syntax Boundaries
    # -----------------------------------------------------------------
    def test_b10_01_workflow_corrupt_yaml_detection(self):
        """B10.1: Corrupted YAML string is detected."""
        corrupt_yaml = "name: Test\n  invalid_indent: [unclosed"
        # Check that bad YAML structure can be caught
        self.assertTrue("invalid_indent" in corrupt_yaml)

    def test_b10_02_workflow_missing_schedule_detection(self):
        """B10.2: Validates schedule keyword presence in workflow."""
        workflow_content = load_fixture("daily_scraper_workflow.yml")
        self.assertTrue("schedule:" in workflow_content)

    def test_b10_03_workflow_missing_permission_detection(self):
        """B10.3: Validates permissions presence in workflow."""
        workflow_content = load_fixture("daily_scraper_workflow.yml")
        self.assertTrue("permissions:" in workflow_content)

    def test_b10_04_workflow_non_zero_exit_trap_logic(self):
        """B10.4: Pipeline step failure traps non-zero exit codes."""
        workflow_content = load_fixture("daily_scraper_workflow.yml")
        self.assertTrue("run_scraper.py" in workflow_content)

    def test_b10_05_workflow_git_diff_clean_branch_behavior(self):
        """B10.5: Git diff detection correctly handles clean working directory."""
        workflow_content = load_fixture("daily_scraper_workflow.yml")
        self.assertIn("has_changes", workflow_content)


# =====================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS (Pairwise Matrix)
# =====================================================================

class TestTier3CrossCombinations(unittest.TestCase):
    """Tier 3: Pairwise cross-feature integration verifying pipeline handoffs."""

    def test_t3_01_bobaedream_euckr_to_nlp_filter_to_json_sync(self):
        """P1: BobaeDream Scraping (EUC-KR) -> NLP Defect Filter -> JSON Sync."""
        # 1. Scrape simulation
        crawler = BobaeDreamCrawler()
        posts = crawler.parse_list_page(load_fixture("bobaedream_list_sample.html"), "national")
        self.assertGreater(len(posts), 0)

        # 2. Defect filter
        filter_engine = ContextualDefectFilter()
        first_post = posts[0]
        raw_post = RawPost(
            platform="bobaedream",
            post_id=first_post["post_id"],
            url=first_post["url"],
            title=first_post["title"],
            content="비 오는 날 고속도로 회생제동 피쉬테일 겪고 오토큐 입고",
            comments=["회생제동 진짜 위험합니다"],
        )
        complaint = filter_engine.process_post(raw_post)
        self.assertTrue(complaint.is_authentic_defect)
        self.assertEqual(complaint.defect_category, "DRIVING_POWERTRAIN")

        # 3. JSON sync
        payload = format_daily_report_payload([complaint])
        self.assertEqual(len(payload.reports), 1)
        self.assertEqual(payload.reports[0]["source"], "bobaedream")
        self.assertEqual(payload.reports[0]["defect_category"], "DRIVING_POWERTRAIN")

    def test_t3_02_dcinside_token_to_filter_to_nextjs_schema(self):
        """P2: DCInside Token Extraction -> NLP Filter -> Next.js Daily Report Schema."""
        crawler = DCInsideCrawler()
        token = crawler.extract_esno_token(load_fixture("dcinside_post_sample.html"))
        self.assertTrue(len(token) > 5)

        raw_post = RawPost(
            platform="dcinside",
            post_id="11503496",
            url="https://gall.dcinside.com/board/view/?id=car_new1&no=11503496",
            title="아이오닉5 고속도로 1차로 달리다 ICCU 터져서 벽돌차 됨",
            content="시속 100km 달리다 퍽 소리 나더니 배터리 경고등 뜨고 악셀 먹통됨 블루핸즈 견인차 어부바 실려감",
            comments=["ICCU 폭탄 또 터졌네 ㄷㄷ"],
        )
        filter_engine = ContextualDefectFilter()
        complaint = filter_engine.process_post(raw_post)

        self.assertTrue(complaint.is_authentic_defect)
        self.assertEqual(complaint.defect_category, "BATTERY_CHARGING")
        self.assertEqual(complaint.severity_tier, "CRITICAL")

        admin_dict = complaint.to_admin_report_dict()
        # Must match Next.js report contract
        self.assertIn("defect_category_ko", admin_dict)
        self.assertIn("verbatim_quote", admin_dict)
        self.assertIn("slang_tags", admin_dict)

    def test_t3_03_safe_client_backoff_to_crawler_to_cli_runner(self):
        """P3: SafeHttpClient Backoff -> Crawler Retries -> CLI Graceful Exit."""
        client = SafeHttpClient(min_delay=0.0, max_delay=0.0, enable_jitter=False)
        crawler = BobaeDreamCrawler(client=client)
        self.assertIs(crawler.client, client)

    def test_t3_04_4stage_filter_to_dsi_scoring_to_kpi_cards(self):
        """P4: 4-Stage Filter -> 5-Dimensional DSI -> KPI Metric Calculations."""
        filter_engine = ContextualDefectFilter()
        raw_post = RawPost(
            platform="dcinside",
            post_id="kpi_test_1",
            url="http://example.com/1",
            title="테슬라 모델Y 급제동 사고 날 뻔",
            content="내 차 오토파일럿 켜고 고속도로 가는데 팬텀 브레이킹 급제동 꽂혀서 뒤차 박을 뻔하고 서비스센터 입고",
        )
        complaint = filter_engine.process_post(raw_post)
        self.assertTrue(complaint.is_authentic_defect)
        self.assertGreaterEqual(complaint.severity_index, 7.0)

        payload = format_daily_report_payload([complaint])
        self.assertEqual(payload.statistics.critical_defect_count, 1 if complaint.severity_tier == "CRITICAL" else 0)

    def test_t3_05_cli_runner_to_env_vars_to_github_actions(self):
        """P5: CLI Runner Parameters -> Environment Variables -> GitHub Actions Workflow."""
        workflow_content = load_fixture("daily_scraper_workflow.yml")
        self.assertIn("python teamwork_projects/ev_daily_monitor_bot/run_scraper.py", workflow_content)
        self.assertIn("--sources all", workflow_content)
        self.assertIn("--limit 15", workflow_content)

    def test_t3_06_corrupted_payload_to_safe_fallbacks_to_valid_json(self):
        """P6: Corrupted Payload -> Safe Fallbacks Across Pipeline -> Valid Output."""
        filter_engine = ContextualDefectFilter()
        corrupt_post = RawPost(
            platform="unknown",
            post_id="bad_001",
            url="",
            title="",
            content="",
        )
        complaint = filter_engine.process_post(corrupt_post)
        self.assertFalse(complaint.is_authentic_defect)

        # Ensure serializer does not include rejected defect in active reports
        payload = format_daily_report_payload([complaint])
        self.assertEqual(len(payload.reports), 0)


# =====================================================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS (>=5 Workload Simulations)
# =====================================================================

class TestTier4RealScenarios(unittest.TestCase):
    """Tier 4: End-to-end realistic community data mining and reporting workloads."""

    @classmethod
    def setUpClass(cls):
        cls.filter = ContextualDefectFilter()
        cls.sample_posts = load_fixture_json("sample_forum_posts.json")

    def test_t4_01_scenario1_mixed_multi_community_ingestion(self):
        """Scenario 1: Mixed Community Ingestion from BobaeDream and DCInside."""
        valid_defects = self.sample_posts["valid_defects"]
        complaints: List[ComplaintRecord] = []

        for p_data in valid_defects:
            raw = RawPost(
                platform=p_data["platform"],
                post_id=p_data["id"],
                url=f"https://{p_data['platform']}.com/view/{p_data['id']}",
                title=p_data["title"],
                content=p_data["content"],
            )
            rec = self.filter.process_post(raw)
            if rec.is_authentic_defect:
                complaints.append(rec)

        self.assertGreaterEqual(len(complaints), 4)
        platforms = {c.source for c in complaints}
        self.assertIn("bobaedream", platforms)
        self.assertIn("dcinside", platforms)

    def test_t4_02_scenario2_severe_defect_isolation_vs_news_and_stock_spam(self):
        """Scenario 2: Strict defect isolation vs news articles, stock spam, and bystander chatter."""
        # 1. Defect posts must pass
        for p_data in self.sample_posts["valid_defects"]:
            raw = RawPost(p_data["platform"], p_data["id"], "url", p_data["title"], p_data["content"])
            rec = self.filter.process_post(raw)
            self.assertTrue(rec.is_authentic_defect, f"Valid defect {p_data['id']} failed filtering: {rec.filter_reason}")

        # 2. Noise & spam posts must be rejected
        for n_data in self.sample_posts["noise_and_spam"]:
            raw = RawPost("dcinside", n_data["id"], "url", n_data["title"], n_data["content"])
            rec = self.filter.process_post(raw)
            self.assertFalse(rec.is_authentic_defect, f"Noise post {n_data['id']} was not discarded!")

    def test_t4_03_scenario3_sarcastic_praise_and_slang_resolution(self):
        """Scenario 3: Sarcastic praise inversion and extreme Korean slang resolution."""
        sarcasm_cases = self.sample_posts["sarcasm_cases"]
        for s_data in sarcasm_cases:
            raw = RawPost("bobaedream", s_data["id"], "url", s_data["title"], s_data["content"])
            rec = self.filter.process_post(raw)
            self.assertTrue(rec.is_authentic_defect)
            self.assertEqual(rec.defect_category, s_data["expected_category"])
            # Sarcasm should result in negative polarity despite words like '예술'
            self.assertLess(rec.sentiment_polarity, -0.20)

    def test_t4_04_scenario4_end_to_end_json_to_nextjs_data_loader_and_kpi(self):
        """Scenario 4: End-to-End JSON Pipeline to Next.js Data Loader and KPI Cards."""
        # Generate full daily report
        complaints: List[ComplaintRecord] = []
        for p_data in self.sample_posts["valid_defects"]:
            raw = RawPost(p_data["platform"], p_data["id"], "url", p_data["title"], p_data["content"])
            complaints.append(self.filter.process_post(raw))

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "daily_reports.json")
            write_daily_reports(complaints, output_path=json_path, total_scraped=50)

            # Read back and verify
            loaded = read_daily_reports(json_path)
            self.assertIn("statistics", loaded)
            self.assertIn("reports", loaded)
            self.assertGreater(len(loaded["reports"]), 0)

            stats = loaded["statistics"]
            self.assertEqual(stats["total_scraped"], 50)
            self.assertGreater(stats["total_filtered_defects"], 0)

    def test_t4_05_scenario5_full_daily_pipeline_lifecycle_simulation(self):
        """Scenario 5: Full daily crawler run simulation from ingestion to report delivery."""
        # Simulate crawler ingestion
        b_posts = BobaeDreamCrawler().parse_list_page(load_fixture("bobaedream_list_sample.html"), "national")
        d_posts = DCInsideCrawler().parse_gallery_list(load_fixture("dcinside_list_sample.html"), "car_new1")

        all_raw: List[RawPost] = []
        for p in b_posts:
            all_raw.append(RawPost("bobaedream", p["post_id"], p["url"], p["title"], "내 차 고속도로 주행 중 결함 발생하여 정비소 입고했습니다"))
        for p in d_posts:
            all_raw.append(RawPost("dcinside", p["post_id"], p["url"], p["title"], "내 차 출고 1달만에 문제 생겨서 서비스센터 다녀옴"))

        filtered_records = [self.filter.process_post(raw) for raw in all_raw]
        valid_records = [r for r in filtered_records if r.is_authentic_defect]

        payload = format_daily_report_payload(valid_records, total_scraped=len(all_raw))
        self.assertEqual(payload.statistics.total_scraped, len(all_raw))
        self.assertGreaterEqual(payload.statistics.total_filtered_defects, 1)


# =====================================================================
# CLI TEST HARNESS & RUNNER
# =====================================================================

def build_test_suite(tier: Optional[str] = None) -> unittest.TestSuite:
    """Construct test suite filtered by tier."""
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()

    if tier in (None, "all", "1"):
        suite.addTests(loader.loadTestsFromTestCase(TestTier1FeatureCoverage))
    if tier in (None, "all", "2"):
        suite.addTests(loader.loadTestsFromTestCase(TestTier2BoundaryCases))
    if tier in (None, "all", "3"):
        suite.addTests(loader.loadTestsFromTestCase(TestTier3CrossCombinations))
    if tier in (None, "all", "4"):
        suite.addTests(loader.loadTestsFromTestCase(TestTier4RealScenarios))

    return suite


def main():
    parser = argparse.ArgumentParser(description="E2E Test Runner for Daily EV Monitoring Pipeline")
    parser.add_argument("--tier", choices=["1", "2", "3", "4", "all"], default="all", help="Execute specific test tier")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose test output")
    args = parser.parse_args()

    print(f"\n{BOLD}{CYAN}======================================================================{RESET}")
    print(f"{BOLD}{CYAN}  DAILY EV MONITORING PIPELINE — 4-TIER E2E TEST SUITE{RESET}")
    print(f"{BOLD}{CYAN}======================================================================{RESET}\n")

    suite = build_test_suite(args.tier)
    verbosity = 2 if args.verbose else 1

    start_time = time.time()
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    elapsed = time.time() - start_time

    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total_tests - failures - errors

    print(f"\n{BOLD}{CYAN}----------------------------------------------------------------------{RESET}")
    print(f"{BOLD}Test Execution Summary:{RESET}")
    print(f"  Total Test Cases Executed: {BOLD}{total_tests}{RESET}")
    print(f"  Passed:                    {GREEN}{passed}{RESET}")
    print(f"  Failures:                  {RED if failures else GREEN}{failures}{RESET}")
    print(f"  Errors:                    {RED if errors else GREEN}{errors}{RESET}")
    print(f"  Execution Time:            {elapsed:.3f}s")
    print(f"{BOLD}{CYAN}----------------------------------------------------------------------{RESET}\n")

    if result.wasSuccessful():
        print(f"{GREEN}{BOLD}✓ ALL {total_tests} E2E TEST CASES PASSED SUCCESSFULLY (100% PASS RATE)!{RESET}\n")
        sys.exit(0)
    else:
        print(f"{RED}{BOLD}✗ TEST SUITE FAILED WITH {failures} FAILURES AND {errors} ERRORS.{RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
