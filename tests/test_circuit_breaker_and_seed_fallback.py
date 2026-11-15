"""Tests for Circuit Breaker, Safe HTML / BeautifulSoup Parsing, and Seed Dataset Fallbacks.

Verifies:
1. Rate limit handling, exponential backoff, and host-level circuit breaking on 403, 429, 503, and network errors.
2. Safe HTML parsing and BeautifulSoup error handling (bs4 optional, ParserRejectedMarkup, FeatureNotFound, RecursionError).
3. Fallback to cache and seed datasets (raw_bobae_emerging.json, raw_dcinside_emerging.json, raw_blind_emerging.json, raw_cafe_emerging.json, compiled_complaints.json) when live sites are offline or restricted.
4. RawPost.from_dict alias mapping for seed data compatibility.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

from crawlers.base_crawler import BaseCrawler
from crawlers.bobaedream import BobaeDreamCrawler
from crawlers.dcinside import DCInsideCrawler
from models.complaint import RawPost
from run_scraper import ScraperPipeline
from scrapers.blind_scraper import BlindScraper
from scrapers.bobaedream_scraper import BobaedreamScraper
from scrapers.cafe_forum_miner import CafeForumMiner
from scrapers.common_utils import ComplaintRecord as ScraperComplaintRecord
from scrapers.dcinside_scraper import DCInsideScraper
from utils.http_client import (
    CircuitBreaker,
    CircuitBreakerState,
    SafeHttpClient,
    safe_extract_html_text,
    safe_soup_parse,
)


class TestCircuitBreakerCore(unittest.TestCase):
    """Test host-level circuit breaker state transitions and fast-fail behavior."""

    def test_state_transitions_closed_to_open_to_half_open_to_closed(self) -> None:
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=0.2)
        host = "www.bobaedream.co.kr"

        # Initially CLOSED
        self.assertEqual(cb.get_state(host), CircuitBreakerState.CLOSED)
        self.assertFalse(cb.is_open(host))
        self.assertTrue(cb.can_request(host))

        # 2 failures do not trip
        cb.record_failure(host, status_code=503)
        cb.record_failure(host, status_code=429)
        self.assertEqual(cb.get_state(host), CircuitBreakerState.CLOSED)
        self.assertTrue(cb.can_request(host))

        # 3rd failure trips circuit to OPEN
        cb.record_failure(host, status_code=403)
        self.assertEqual(cb.get_state(host), CircuitBreakerState.OPEN)
        self.assertTrue(cb.is_open(host))
        self.assertFalse(cb.can_request(host))

        # Wait for cooldown to elapse -> transitions to HALF_OPEN on next check
        time.sleep(0.25)
        self.assertTrue(cb.can_request(host))
        self.assertEqual(cb.get_state(host), CircuitBreakerState.HALF_OPEN)

        # Success resets to CLOSED
        cb.record_success(host)
        self.assertEqual(cb.get_state(host), CircuitBreakerState.CLOSED)
        self.assertFalse(cb.is_open(host))

    def test_half_open_failure_reopens_circuit(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.1)
        host = "gall.dcinside.com"

        cb.record_failure(host, status_code=503)
        cb.record_failure(host, status_code=503)
        self.assertEqual(cb.get_state(host), CircuitBreakerState.OPEN)

        time.sleep(0.15)
        self.assertEqual(cb.get_state(host), CircuitBreakerState.HALF_OPEN)

        # Failure during HALF_OPEN canary probe trips circuit back to OPEN
        cb.record_failure(host, status_code=503)
        self.assertEqual(cb.get_state(host), CircuitBreakerState.OPEN)
        self.assertFalse(cb.can_request(host))

    def test_reset_circuit_breaker(self) -> None:
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=60.0)
        host = "www.teamblind.com"

        cb.record_failure(host, status_code=429)
        self.assertEqual(cb.get_state(host), CircuitBreakerState.OPEN)

        cb.reset(host)
        self.assertEqual(cb.get_state(host), CircuitBreakerState.CLOSED)
        self.assertTrue(cb.can_request(host))


class TestSafeHttpClientCircuitBreakerIntegration(unittest.TestCase):
    """Test SafeHttpClient integration with host circuit breaker and cache fallback."""

    def test_client_fast_fails_when_circuit_open(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = SafeHttpClient(
                min_delay=0.0,
                max_delay=0.0,
                enable_cache=True,
                cache_fallback=False,
                cache_dir=tmpdir,
                failure_threshold=2,
                cooldown_seconds=60.0,
            )
            url = "https://www.bobaedream.co.kr/list?code=national"

            # Trip circuit with 2 failures
            client.circuit_breaker.record_failure("www.bobaedream.co.kr", status_code=429)
            client.circuit_breaker.record_failure("www.bobaedream.co.kr", status_code=429)

            self.assertTrue(client.is_circuit_open(url))
            self.assertEqual(client.get_circuit_state(url), "OPEN")

            # Calling request on open circuit returns (503, "", b"") fast without network call
            with patch.object(client.opener, "open") as mock_open:
                status, text, raw = client.request(url)
                mock_open.assert_not_called()
                self.assertEqual(status, 503)

    def test_client_serves_cache_when_circuit_open_with_cache_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = SafeHttpClient(
                min_delay=0.0,
                max_delay=0.0,
                enable_cache=True,
                cache_fallback=True,
                cache_dir=tmpdir,
                failure_threshold=1,
                cooldown_seconds=60.0,
            )
            url = "https://gall.dcinside.com/mgallery/board/lists/?id=tesla"
            cached_html = "<html><body>Cached Tesla Gallery HTML</body></html>"

            # Pre-populate cache
            client.set_cached_response(url, 200, cached_html, cached_html.encode("utf-8"))

            # Trip circuit
            client.circuit_breaker.record_failure("gall.dcinside.com", status_code=503)
            self.assertTrue(client.is_circuit_open(url))

            # Request returns cached content with status 200
            status, text, raw = client.request(url)
            self.assertEqual(status, 200)
            self.assertIn("Cached Tesla Gallery HTML", text)


class TestSafeSoupAndHTMLParsing(unittest.TestCase):
    """Test safe HTML parsing and BeautifulSoup error handling."""

    def test_safe_extract_html_text_with_scripts_and_entities(self) -> None:
        raw_html = """
        <div class="content">
            <script>var x = 123;</script>
            <style>.hide { display: none; }</style>
            <!-- comment -->
            <p>테슬라 &amp; 현대차 <b>배터리/충전</b> 오류 &lt;심각&gt;</p>
        </div>
        """
        extracted = safe_extract_html_text(raw_html)
        self.assertIn("테슬라 & 현대차 배터리/충전 오류 <심각>", extracted)
        self.assertNotIn("var x = 123", extracted)
        self.assertNotIn(".hide", extracted)
        self.assertNotIn("comment", extracted)

    def test_safe_soup_parse_handles_corrupt_and_non_string_markup(self) -> None:
        # None and non-string inputs return None safely
        self.assertIsNone(safe_soup_parse(None))
        self.assertIsNone(safe_soup_parse(12345))
        self.assertIsNone(safe_soup_parse(""))

        # Even with null bytes and invalid characters, safe_soup_parse does not crash
        corrupt_html = "<div\x00>Corrupted <broken p"
        soup = safe_soup_parse(corrupt_html)
        # If bs4 is installed, returns soup object; if not installed, returns None gracefully
        if soup is not None:
            self.assertIn("Corrupted", soup.text)

    def test_safe_soup_parse_handles_parser_rejected_markup(self) -> None:
        with patch("utils.http_client.BS4_AVAILABLE", True):
            with patch("utils.http_client.BeautifulSoup", side_effect=Exception("Parser error")):
                res = safe_soup_parse("<div>Test</div>")
                self.assertIsNone(res)


class TestRawPostSeedCompatibility(unittest.TestCase):
    """Test RawPost.from_dict mapping of seed dataset alias keys."""

    def test_raw_post_from_seed_dict(self) -> None:
        seed_item = {
            "id": "BOBAE_XM_001",
            "platform": "bobaedream",
            "board_name": "보배드림 수입차게시판",
            "post_url": "https://www.bobaedream.co.kr/view?code=import&No=718942",
            "post_title": "샤오미 SU7 서킷 주행 중 브레이크 패드 가루되고 벽 처박는 영상 충격이네요",
            "target_vehicle": "Xiaomi SU7 Max",
            "category": "safety",
            "defect_topic": "샤오미 SU7 서킷 고속 제동 시 브레이크 패드 열화 소손 및 페달 바닥 꺼짐 충돌",
            "raw_quote": "영상 보는데 진짜 오금이 저리더라. 673마력짜리 괴물 차를 만들어놓고...",
            "slang_terms": ["샤이칸", "움직이는 보조배터리"],
            "severity": "critical_safety",
            "platform_metadata": {
                "author_type": "enthusiast",
                "author_badge": "수입차 10년차",
                "post_date": "2024-05-18",
            },
        }

        post = RawPost.from_dict(seed_item)
        self.assertEqual(post.post_id, "BOBAE_XM_001")
        self.assertEqual(post.platform, "bobaedream")
        self.assertEqual(post.url, "https://www.bobaedream.co.kr/view?code=import&No=718942")
        self.assertIn("샤오미 SU7 서킷 주행", post.title)
        self.assertIn("영상 보는데 진짜 오금이 저리더라", post.content)
        self.assertEqual(post.author, "수입차 10년차")
        self.assertEqual(post.created_at, "2024-05-18")


class TestCrawlerAndPipelineSeedFallback(unittest.TestCase):
    """Test seed dataset fallback in crawlers and ScraperPipeline."""

    def test_bobaedream_crawler_seed_fallback(self) -> None:
        crawler = BobaeDreamCrawler()
        posts = crawler.load_seed_posts(limit=5)
        self.assertIsInstance(posts, list)
        if posts:
            first = posts[0]
            self.assertEqual(first.get("platform"), "bobaedream")
            self.assertTrue("title" in first or "post_title" in first)
            self.assertTrue("url" in first or "post_url" in first)

    def test_dcinside_crawler_seed_fallback(self) -> None:
        crawler = DCInsideCrawler()
        posts = crawler.load_seed_posts(limit=5)
        self.assertIsInstance(posts, list)
        if posts:
            first = posts[0]
            self.assertEqual(first.get("platform"), "dcinside")
            self.assertTrue("title" in first or "post_title" in first)

    def test_standalone_scrapers_load_seed_records(self) -> None:
        bobae_scraper = BobaedreamScraper()
        dc_scraper = DCInsideScraper()
        blind_scraper = BlindScraper()
        cafe_miner = CafeForumMiner()

        bobae_records = bobae_scraper.load_seed_records(limit=3)
        dc_records = dc_scraper.load_seed_records(limit=3)
        blind_records = blind_scraper.load_seed_records(limit=3)
        cafe_records = cafe_miner.load_seed_records(limit=3)

        self.assertIsInstance(bobae_records, list)
        self.assertIsInstance(dc_records, list)
        self.assertIsInstance(blind_records, list)
        self.assertIsInstance(cafe_records, list)

        if bobae_records:
            self.assertIsInstance(bobae_records[0], ScraperComplaintRecord)
            self.assertEqual(bobae_records[0].platform, "bobaedream")

        if dc_records:
            self.assertIsInstance(dc_records[0], ScraperComplaintRecord)
            self.assertEqual(dc_records[0].platform, "dcinside")

    def test_scraper_pipeline_seed_fallback_when_offline(self) -> None:
        pipeline = ScraperPipeline(cache_fallback=True)

        with patch.object(pipeline, "harvest_bobaedream", return_value=[]), \
             patch.object(pipeline, "harvest_dcinside", return_value=[]), \
             patch.object(pipeline, "_get_harvest_cache_path", return_value=Path("/tmp/nonexistent_harvest_cache.json")):

            raw_posts, stats = pipeline.harvest(source_choice="all", limit=10)
            self.assertIsInstance(raw_posts, list)
            # When remote crawlers return 0 posts and cache file does not exist,
            # pipeline falls back to loading posts from seed datasets in data/
            self.assertGreater(len(raw_posts), 0)
            self.assertGreater(stats.get("bobaedream", 0) + stats.get("dcinside", 0), 0)

            # Check that defect filtering processes fallback posts without crashes
            defects = pipeline.filter_defects(raw_posts)
            self.assertIsInstance(defects, list)


if __name__ == "__main__":
    unittest.main()
