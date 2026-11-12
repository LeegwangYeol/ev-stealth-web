#!/usr/bin/env python3
"""
Dedicated Resilience Verification Suite for Scrapers, Crawlers, and Master Pipeline.
Validates:
1. Explicit connect and read network timeouts across SafeHttpClient, BaseCrawler, and ScraperPipeline.
2. Exponential backoff and retry mechanisms on transient network errors (URLError, timeouts, 5xx).
3. Fallback to cached data when remote endpoints are unreachable or return 5xx errors.
4. CafeForumMiner runtime safety (no missing imports, polite delay with jitter).
"""

from __future__ import annotations

import http.cookiejar
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.base_crawler import BaseCrawler
from crawlers.bobaedream import BobaeDreamCrawler
from crawlers.dcinside import DCInsideCrawler
from run_scraper import ScraperPipeline
from scrapers.blind_scraper import BlindScraper
from scrapers.bobaedream_scraper import BobaedreamScraper
from scrapers.cafe_forum_miner import CafeForumMiner
from scrapers.common_utils import SafeHttpClient as CommonSafeHttpClient
from scrapers.dcinside_scraper import DCInsideScraper
from utils.http_client import SafeHttpClient


class TestExplicitTimeouts(unittest.TestCase):
    """Test explicit connect and read timeout configurations across all layers."""

    def test_safe_http_client_tuple_timeouts(self):
        """SafeHttpClient accepts tuple (connect_timeout, read_timeout)."""
        client = SafeHttpClient(timeout=(3.5, 12.0), enable_jitter=False)
        self.assertEqual(client.connect_timeout, 3.5)
        self.assertEqual(client.read_timeout, 12.0)

    def test_safe_http_client_explicit_keyword_timeouts(self):
        """SafeHttpClient accepts separate connect_timeout and read_timeout keywords."""
        client = SafeHttpClient(connect_timeout=4.0, read_timeout=20.0, enable_jitter=False)
        self.assertEqual(client.connect_timeout, 4.0)
        self.assertEqual(client.read_timeout, 20.0)

    def test_common_utils_safe_http_client_timeouts(self):
        """scrapers.common_utils.SafeHttpClient supports connect_timeout and read_timeout properties."""
        client = CommonSafeHttpClient(timeout=(2.5, 8.0))
        self.assertEqual(client.connect_timeout, 2.5)
        self.assertEqual(client.read_timeout, 8.0)

    def test_base_crawler_explicit_timeouts(self):
        """BaseCrawler exposes and propagates connect and read timeouts."""
        crawler = BobaeDreamCrawler(timeout=(4.0, 16.0))
        self.assertEqual(crawler.connect_timeout, 4.0)
        self.assertEqual(crawler.read_timeout, 16.0)
        self.assertEqual(crawler.client.connect_timeout, 4.0)
        self.assertEqual(crawler.client.read_timeout, 16.0)

    def test_dcinside_crawler_explicit_timeouts(self):
        """DCInsideCrawler inherits and propagates connect and read timeouts."""
        crawler = DCInsideCrawler(connect_timeout=3.0, read_timeout=14.0)
        self.assertEqual(crawler.connect_timeout, 3.0)
        self.assertEqual(crawler.read_timeout, 14.0)

    def test_scraper_pipeline_explicit_timeouts(self):
        """ScraperPipeline configures explicit connect and read timeouts on crawlers and HTTP client."""
        pipeline = ScraperPipeline(connect_timeout=2.0, read_timeout=10.0)
        self.assertEqual(pipeline.connect_timeout, 2.0)
        self.assertEqual(pipeline.read_timeout, 10.0)
        self.assertEqual(pipeline.client.connect_timeout, 2.0)
        self.assertEqual(pipeline.client.read_timeout, 10.0)
        self.assertEqual(pipeline.bobae_crawler.connect_timeout, 2.0)
        self.assertEqual(pipeline.bobae_crawler.read_timeout, 10.0)
        self.assertEqual(pipeline.dc_crawler.connect_timeout, 2.0)
        self.assertEqual(pipeline.dc_crawler.read_timeout, 10.0)
        pipeline.close()

    def test_request_per_call_timeout_override(self):
        """Per-request timeout tuple or keywords override instance default timeouts."""
        class MockRecordingOpener:
            def __init__(self):
                self.recorded_timeout = None
            def open(self, req, timeout=15.0):
                self.recorded_timeout = timeout
                mock_resp = MagicMock()
                mock_resp.getcode.return_value = 200
                mock_resp.read.return_value = b"<html>OK</html>"
                mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
                return mock_resp

        opener = MockRecordingOpener()
        client = SafeHttpClient(timeout=(5.0, 15.0), enable_jitter=False, opener=opener)
        status, text, raw = client.request("https://example.com/test", timeout=(2.0, 7.5))
        self.assertEqual(status, 200)
        self.assertEqual(opener.recorded_timeout, 7.5)


class TestExponentialBackoffAndRetries(unittest.TestCase):
    """Test exponential backoff scaling and retries on transient errors."""

    def test_exponential_backoff_calculation(self):
        """Backoff calculation increases exponentially with attempt count."""
        client = SafeHttpClient(backoff_factor=1.0, max_backoff=60.0, enable_jitter=False)
        self.assertEqual(client._calc_backoff(1), 2.0)
        self.assertEqual(client._calc_backoff(2), 4.0)
        self.assertEqual(client._calc_backoff(3), 8.0)
        self.assertEqual(client._calc_backoff(4), 16.0)

    def test_retry_after_header_honored(self):
        """HTTP 429 Retry-After header is honored when provided."""
        client = SafeHttpClient(enable_jitter=False)
        self.assertEqual(client._calc_backoff(1, retry_after=12.5), 12.5)

    @patch("time.sleep")
    def test_transient_503_error_retried(self, mock_sleep):
        """Transient HTTP 503 triggers retries before completion."""
        mock_opener = MagicMock()
        mock_fp = MagicMock()
        mock_fp.read.return_value = b"503 Service Unavailable"
        err_503 = urllib.error.HTTPError(
            url="https://example.com/api",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=mock_fp,
        )
        mock_opener.open.side_effect = err_503
        client = SafeHttpClient(max_retries=2, enable_jitter=False, opener=mock_opener, enable_cache=False)
        status, text, raw = client.get("https://example.com/api")
        self.assertEqual(status, 503)
        self.assertEqual(mock_opener.open.call_count, 2)
        self.assertTrue(mock_sleep.called)

    @patch("time.sleep")
    def test_socket_timeout_retried(self, mock_sleep):
        """Socket timeout exception triggers retries."""
        mock_opener = MagicMock()
        mock_opener.open.side_effect = socket.timeout("timed out")
        client = SafeHttpClient(max_retries=2, enable_jitter=False, opener=mock_opener, enable_cache=False)
        status, text, raw = client.get("https://example.com/slow")
        self.assertEqual(status, 0)
        self.assertEqual(mock_opener.open.call_count, 2)
        self.assertTrue(mock_sleep.called)


class TestCacheFallbackOnOutageAnd5xx(unittest.TestCase):
    """Test fallback to cached data when remote endpoints fail or return 5xx."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_cache_audit_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_utils_http_client_cache_fallback_on_unreachable(self):
        """utils.http_client.SafeHttpClient falls back to cached data on connection failure."""
        class MockDynamicOpener:
            def __init__(self):
                self.should_fail = False
            def open(self, req, timeout=15.0):
                if self.should_fail:
                    raise urllib.error.URLError("Network unreachable")
                mock_resp = MagicMock()
                mock_resp.getcode.return_value = 200
                mock_resp.read.side_effect = [b"<html>Authentic Post Body</html>", b""]
                mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
                return mock_resp

        opener = MockDynamicOpener()
        client = SafeHttpClient(
            max_retries=1,
            enable_jitter=False,
            opener=opener,
            cache_dir=self.temp_dir,
            enable_cache=True,
            cache_fallback=True,
        )

        test_url = "https://example.com/target-article"
        # 1. Successful fetch populates cache
        status, text, raw = client.get(test_url)
        self.assertEqual(status, 200)
        self.assertIn("Authentic Post Body", text)
        self.assertFalse(client.last_response_from_cache)

        # 2. Remote endpoint becomes completely unreachable
        opener.should_fail = True
        status, text, raw = client.get(test_url)
        self.assertEqual(status, 200)
        self.assertIn("Authentic Post Body", text)
        self.assertTrue(client.last_response_from_cache)

    def test_utils_http_client_cache_fallback_on_5xx(self):
        """utils.http_client.SafeHttpClient falls back to cached data on 502 Bad Gateway."""
        class MockOpener502:
            def __init__(self):
                self.return_502 = False
            def open(self, req, timeout=15.0):
                if self.return_502:
                    mock_fp = MagicMock()
                    mock_fp.read.return_value = b"502 Bad Gateway"
                    raise urllib.error.HTTPError(
                        url=req.full_url, code=502, msg="Bad Gateway", hdrs={}, fp=mock_fp
                    )
                mock_resp = MagicMock()
                mock_resp.getcode.return_value = 200
                mock_resp.read.side_effect = [b"<html>Healthy Server Content</html>", b""]
                mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
                return mock_resp

        opener = MockOpener502()
        client = SafeHttpClient(
            max_retries=1,
            enable_jitter=False,
            opener=opener,
            cache_dir=self.temp_dir,
            enable_cache=True,
            cache_fallback=True,
        )

        test_url = "https://example.com/target-502"
        # 1. Populate cache
        status, text, raw = client.get(test_url)
        self.assertEqual(status, 200)

        # 2. Server experiences 502 outage
        opener.return_502 = True
        status, text, raw = client.get(test_url)
        self.assertEqual(status, 200)
        self.assertIn("Healthy Server Content", text)
        self.assertTrue(client.last_response_from_cache)

    def test_common_utils_safe_http_client_cache_fallback(self):
        """scrapers.common_utils.SafeHttpClient falls back to cached data on outage."""
        class MockDynamicCommonOpener:
            def __init__(self):
                self.should_fail = False
            def open(self, req, timeout=15.0):
                if self.should_fail:
                    raise urllib.error.URLError("Connection refused")
                mock_resp = MagicMock()
                mock_resp.getcode.return_value = 200
                mock_resp.read.side_effect = [b"<div>Common Scraper Article</div>", b""]
                mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
                return mock_resp

        opener = MockDynamicCommonOpener()
        client = CommonSafeHttpClient(
            max_retries=1,
            min_delay=0.0,
            max_delay=0.0,
            opener=opener,
            cache_dir=self.temp_dir,
            enable_cache=True,
            cache_fallback=True,
        )

        url = "https://example.com/common-post"
        status, text = client.get(url)
        self.assertEqual(status, 200)
        self.assertIn("Common Scraper Article", text)

        opener.should_fail = True
        status, text = client.get(url)
        self.assertEqual(status, 200)
        self.assertIn("Common Scraper Article", text)

    def test_base_crawler_post_cache_fallback(self):
        """BaseCrawler returns cached parsed post detail when remote post is unreachable."""
        class DummyCrawler(BaseCrawler):
            def parse_post_detail(self, html_content: str, post_url: str, **kwargs):
                return {
                    "platform": "dummy",
                    "post_id": "999",
                    "url": post_url,
                    "title": "Cached Post Title",
                    "content": "Authentic Content",
                }

        crawler = DummyCrawler(enable_cache=True, cache_fallback=True)
        # Mock client to return success once, then fail
        mock_client = MagicMock()
        mock_client.get.side_effect = [
            (200, "<html>Success</html>"),
            (0, ""),  # Network failure on subsequent fetch
        ]
        crawler.client = mock_client

        # 1. Initial successful fetch
        post = crawler.fetch_post("https://example.com/post/999")
        self.assertIsNotNone(post)
        self.assertEqual(post["title"], "Cached Post Title")

        # 2. Subsequent fetch during network failure
        fallback_post = crawler.fetch_post("https://example.com/post/999")
        self.assertIsNotNone(fallback_post)
        self.assertEqual(fallback_post["title"], "Cached Post Title")

    def test_scraper_pipeline_harvest_cache_fallback(self):
        """ScraperPipeline falls back to cached harvest posts when remote sources return 0 items."""
        pipeline = ScraperPipeline(enable_cache=True, cache_fallback=True)
        dummy_harvest = [
            {
                "platform": "bobaedream",
                "post_id": "b1",
                "url": "https://example.com/b1",
                "title": "테슬라 모델Y 충전 오류",
                "content": "급속 충전 중 튕김 현상 발생",
            },
            {
                "platform": "dcinside",
                "post_id": "d1",
                "url": "https://example.com/d1",
                "title": "아이오닉5 ICCU 경고등",
                "content": "주행 중 퍽 소리와 함께 멈춤",
            },
        ]

        # 1. Simulate initial successful harvest and cache save
        pipeline._save_harvest_cache(dummy_harvest)

        # 2. Mock both crawlers to simulate total network outage / 5xx error
        pipeline.bobae_crawler.crawl_board = MagicMock(return_value=[])
        pipeline.bobae_crawler.crawl_posts_by_keyword = MagicMock(return_value=[])
        pipeline.dc_crawler.crawl_gallery = MagicMock(return_value=[])
        pipeline.dc_crawler.crawl_posts_by_keyword = MagicMock(return_value=[])

        posts, stats = pipeline.harvest(source_choice="all", limit=10)
        self.assertEqual(len(posts), 2)
        self.assertEqual(stats["bobaedream"], 1)
        self.assertEqual(stats["dcinside"], 1)
        pipeline.close()


class TestScraperRuntimeSafety(unittest.TestCase):
    """Test runtime safety and import integrity for scrapers."""

    def test_cafe_forum_miner_polite_sleep(self):
        """CafeForumMiner.sleep_polite executes cleanly without NameError."""
        miner = CafeForumMiner()
        miner.min_delay = 0.001
        miner.max_delay = 0.002
        start = time.time()
        miner.sleep_polite()
        dur = time.time() - start
        self.assertLess(dur, 0.1)

    def test_blind_scraper_polite_sleep(self):
        """BlindScraper.sleep_polite executes cleanly."""
        scraper = BlindScraper()
        scraper.min_delay = 0.001
        scraper.max_delay = 0.002
        start = time.time()
        scraper.sleep_polite()
        dur = time.time() - start
        self.assertLess(dur, 0.1)

    def test_bobaedream_scraper_polite_sleep(self):
        """BobaedreamScraper.sleep_polite executes cleanly."""
        scraper = BobaedreamScraper()
        scraper.min_delay = 0.001
        scraper.max_delay = 0.002
        start = time.time()
        scraper.sleep_polite()
        dur = time.time() - start
        self.assertLess(dur, 0.1)

    def test_dcinside_scraper_polite_sleep(self):
        """DCInsideScraper.sleep_polite executes cleanly."""
        scraper = DCInsideScraper()
        scraper.min_delay = 0.001
        scraper.max_delay = 0.002
        start = time.time()
        scraper.sleep_polite()
        dur = time.time() - start
        self.assertLess(dur, 0.1)


if __name__ == "__main__":
    unittest.main()
