#!/usr/bin/env python3
"""
Unit and Integration Test Suite for Scraper Infrastructure and Network Resilience.
Re-exports and runs tests from test_scrapers.py and provides additional edge case coverage for:
- SafeHttpClient network timeouts, connection drops, socket leaks, exponential backoff
- Charset decoding resilience (CP949, EUC-KR, UTF-8 with BOM, Latin-1, None, empty)
- HTML sanitization and encoding edge cases
- CLI invocation of run_scraper.py
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import socket
import subprocess
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

# Import all test suites from test_scrapers.py for seamless interoperability
from tests.test_scrapers import (
    TestBlindScraper,
    TestBobaedreamScraper,
    TestCafeForumMiner,
    TestCommonUtils,
    TestCompiledDatabase,
    TestDCInsideScraper,
)
from scrapers.common_utils import polite_delay
from utils.http_client import (
    SafeHttpClient,
    USER_AGENT_POOL,
    clean_html_text,
    encode_euc_kr_query,
    robust_decode,
)


class TestSafeHttpClientNetworkResilience(unittest.TestCase):
    """Test SafeHttpClient network timeouts, retries, exponential backoff, and error codes."""

    def setUp(self):
        self.client = SafeHttpClient(min_delay=0.001, max_delay=0.002, max_retries=2, timeout=0.5)

    def test_user_agent_rotation(self):
        """User agent pool must provide valid modern browser user agents."""
        agents = {self.client.get_random_user_agent() for _ in range(50)}
        self.assertGreater(len(agents), 1)
        for ua in agents:
            self.assertIn("Mozilla", ua)

    @patch("urllib.request.build_opener")
    def test_network_timeout_handling(self, mock_build_opener):
        """SafeHttpClient must catch socket and urllib timeouts, retry, and return (0, '', b'')."""
        mock_opener = MagicMock()
        mock_opener.open.side_effect = urllib.error.URLError(socket.timeout("The read operation timed out"))
        self.client.opener = mock_opener

        status, text, raw = self.client.get("https://example.com/test-timeout")
        self.assertEqual(status, 0)
        self.assertEqual(text, "")
        self.assertEqual(raw, b"")
        self.assertEqual(mock_opener.open.call_count, 2)  # max_retries = 2

    @patch("urllib.request.build_opener")
    def test_http_500_502_503_retries(self, mock_build_opener):
        """Server errors (500, 502, 503) must trigger retries and close error handles."""
        mock_opener = MagicMock()
        mock_fp = MagicMock()
        mock_fp.read.return_value = b"502 Bad Gateway"
        http_err = urllib.error.HTTPError(
            url="https://example.com/api",
            code=502,
            msg="Bad Gateway",
            hdrs={},
            fp=mock_fp,
        )
        mock_opener.open.side_effect = http_err
        self.client.opener = mock_opener

        status, text, raw = self.client.get("https://example.com/api")
        self.assertEqual(status, 502)
        self.assertEqual(mock_opener.open.call_count, 2)
        # Verify close was called to prevent socket leaks
        self.assertTrue(mock_fp.close.called)

    @patch("urllib.request.build_opener")
    def test_http_404_not_found_no_retry(self, mock_build_opener):
        """Client error 404 must not retry and immediately return status 404."""
        mock_opener = MagicMock()
        mock_fp = MagicMock()
        mock_fp.read.return_value = b"Not Found"
        http_err = urllib.error.HTTPError(
            url="https://example.com/not-found",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=mock_fp,
        )
        mock_opener.open.side_effect = http_err
        self.client.opener = mock_opener

        status, text, raw = self.client.get("https://example.com/not-found")
        self.assertEqual(status, 404)
        self.assertEqual(mock_opener.open.call_count, 1)  # Only 1 attempt, no retry on 404

    def test_session_warm_up_failure_returns_false(self):
        """Warm-up session must catch connection errors and return False gracefully."""
        with patch.object(self.client, "request", side_effect=urllib.error.URLError("Connection refused")):
            success = self.client.warm_up_session("https://unreachable.invalid")
            self.assertFalse(success)


class TestEncodingAndSanitizationEdgeCases(unittest.TestCase):
    """Test encoding conversion, charset fallbacks, and HTML cleaning."""

    def test_robust_decode_various_encodings(self):
        """robust_decode must handle UTF-8, UTF-8 with BOM, CP949, EUC-KR, and Latin-1."""
        sample_ko = "현대 아이오닉5 전기차 급속 충전"

        # 1. UTF-8
        self.assertEqual(robust_decode(sample_ko.encode("utf-8")), sample_ko)

        # 2. UTF-8 with BOM
        bom_bytes = b"\xef\xbb\xbf" + sample_ko.encode("utf-8")
        self.assertIn("아이오닉5", robust_decode(bom_bytes))

        # 3. CP949 / EUC-KR
        cp949_bytes = sample_ko.encode("cp949")
        self.assertEqual(robust_decode(cp949_bytes), sample_ko)

        # 4. Latin-1 / ASCII
        ascii_text = "Tesla Model 3 Highland 2026"
        self.assertEqual(robust_decode(ascii_text.encode("latin-1")), ascii_text)

        # 5. Empty and None inputs
        self.assertEqual(robust_decode(b""), "")
        self.assertEqual(robust_decode(None), "")
        self.assertEqual(robust_decode("Already String"), "Already String")

    def test_clean_html_text_edge_cases(self):
        """clean_html_text must strip script, style, decode HTML entities, and handle nulls."""
        # Null and empty
        self.assertEqual(clean_html_text(""), "")
        self.assertEqual(clean_html_text(None), "")

        # XSS / script stripping
        dirty = "<p>정상 텍스트</p><script>alert('xss');</script><style>body {color: red;}</style>"
        cleaned = clean_html_text(dirty)
        self.assertEqual(cleaned, "정상 텍스트")
        self.assertNotIn("alert", cleaned)
        self.assertNotIn("color", cleaned)

        # HTML Entities
        entities = "&quot;아이오닉&quot; &amp; &lt;EV6&gt; &#39;테스트&#39;"
        cleaned_ent = clean_html_text(entities)
        self.assertEqual(cleaned_ent, '"아이오닉" & <EV6> \'테스트\'')

    def test_encode_euc_kr_query_edge_cases(self):
        """encode_euc_kr_query must safely percent-encode dictionaries or strings, and handle nulls."""
        self.assertEqual(encode_euc_kr_query(None), "")
        self.assertEqual(encode_euc_kr_query(""), "")
        self.assertEqual(encode_euc_kr_query({}), "")

        # String encoding
        str_enc = encode_euc_kr_query("전기차")
        self.assertTrue(str_enc.startswith("%"))

        # Dictionary encoding
        params = {"query": "전기차", "page": 1}
        dict_enc = encode_euc_kr_query(params)
        self.assertIn("query=", dict_enc)
        self.assertIn("page=1", dict_enc)

    def test_polite_delay_zero_and_negative(self):
        """polite_delay with 0 or negative seconds must return immediately."""
        start = time.time()
        polite_delay(0.0, 0.0)
        polite_delay(-1.0, -1.0)
        elapsed = time.time() - start
        self.assertLess(elapsed, 0.1)


class TestRunScraperPipeline(unittest.TestCase):
    """Test run_scraper.py pipeline execution and dry-run flag."""

    @patch("run_scraper.ScraperPipeline.harvest")
    def test_run_scraper_dry_run(self, mock_harvest):
        """Pipeline with dry_run=True must execute and return summary without writing to disk."""
        from run_scraper import ScraperPipeline

        mock_harvest.return_value = ([], {"bobaedream": 0, "dcinside": 0})
        runner = ScraperPipeline()
        res = runner.run(dry_run=True)
        self.assertTrue(res["dry_run"])
        self.assertEqual(res["total_scraped"], 0)
        self.assertEqual(res["written_paths"], [])


if __name__ == "__main__":
    unittest.main()
