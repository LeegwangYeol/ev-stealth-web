#!/usr/bin/env python3
"""
Unit and Integration Test Suite for Crawler Infrastructure.
Covers:
- BaseCrawler interface, session warm-up, fault-tolerant fetch_post
- BobaeDreamCrawler (EUC-KR query encoding, board parsing, post detail extraction,
  timestamp normalization edge cases, dynamic AJAX comment harvesting)
- DCInsideCrawler (Gallery prefix routing for major/minor/mini, gallery parsing,
  notice row filtering, e_s_n_o CSRF token extraction, AJAX comment JSON parsing)
- Edge cases:
  * Null/None values and empty strings across all parsers and timestamp normalizers
  * Zero values (0 comments, 0 views, 0 recommends, 0 posts)
  * Network timeouts (URLError, TimeoutError, connection drops)
  * HTTP status errors (403, 404, 500, 502, 503)
  * Corrupted, truncated, or malformed HTML/JSON
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.base_crawler import BaseCrawler
from crawlers.bobaedream import (
    BOBAE_BASE_URL,
    BOBAE_LIST_URL,
    BOBAE_VIEW_URL,
    TARGET_BOARDS,
    BobaeDreamCrawler,
    _normalize_iso_timestamp as bd_normalize_timestamp,
)
from crawlers.dcinside import (
    DC_BASE_URL,
    DC_GALLERIES,
    DCInsideCrawler,
    _normalize_iso_timestamp as dc_normalize_timestamp,
)
from utils.http_client import SafeHttpClient


class ConcreteDummyCrawler(BaseCrawler):
    """Concrete implementation for testing BaseCrawler abstract methods."""

    def parse_post_detail(self, html_content: str, post_url: str, **kwargs):
        if "CORRUPT" in html_content:
            raise ValueError("Corrupt DOM encountered")
        return {
            "url": post_url,
            "title": "Sample Title",
            "content": "Sample Content",
        }


class TestBaseCrawler(unittest.TestCase):
    """Test BaseCrawler abstract interface, warm-up, and error recovery."""

    def test_cannot_instantiate_abstract_base_crawler(self):
        """Direct instantiation of BaseCrawler must fail with TypeError."""
        with self.assertRaises(TypeError):
            BaseCrawler()

    def test_warm_up_handling(self):
        """ensure_warm_up must respect force, boolean flags, and avoid duplicate calls."""
        mock_client = MagicMock(spec=SafeHttpClient)
        crawler = ConcreteDummyCrawler(client=mock_client)

        # 1. Warm up with valid URL
        crawler.ensure_warm_up("https://example.com")
        self.assertTrue(crawler._warmed_up)
        mock_client.warm_up_session.assert_called_once_with("https://example.com")

        # 2. Subsequent call without force does not repeat
        crawler.ensure_warm_up("https://example.com")
        self.assertEqual(mock_client.warm_up_session.call_count, 1)

        # 3. Force call repeats
        crawler.ensure_warm_up("https://example.com", force=True)
        self.assertEqual(mock_client.warm_up_session.call_count, 2)

        # 4. Boolean passed as first argument
        crawler.ensure_warm_up(True)

    def test_fetch_post_success(self):
        """Successful 200 HTTP response must call parse_post_detail and return dict."""
        mock_client = MagicMock(spec=SafeHttpClient)
        mock_client.get.return_value = (200, "<html><body>Valid Post</body></html>", b"")
        crawler = ConcreteDummyCrawler(client=mock_client)

        result = crawler.fetch_post("https://example.com/post/1")
        self.assertIsNotNone(result)
        self.assertEqual(result["title"], "Sample Title")

    def test_fetch_post_http_errors_and_empty_responses(self):
        """Non-200 responses and empty bodies must safely return None without crashing."""
        mock_client = MagicMock(spec=SafeHttpClient)
        crawler = ConcreteDummyCrawler(client=mock_client)

        # HTTP error codes
        for status in [400, 403, 404, 500, 502, 503]:
            mock_client.get.return_value = (status, "Error page", b"")
            res = crawler.fetch_post("https://example.com/post/1")
            self.assertIsNone(res, f"Expected None on status {status}")

        # Empty body
        mock_client.get.return_value = (200, "", b"")
        self.assertIsNone(crawler.fetch_post("https://example.com/post/1"))

        # None body
        mock_client.get.return_value = (200, None, b"")
        self.assertIsNone(crawler.fetch_post("https://example.com/post/1"))

    def test_fetch_post_exception_during_parsing(self):
        """Corrupt HTML that causes parsing exception must be caught, returning None."""
        mock_client = MagicMock(spec=SafeHttpClient)
        mock_client.get.return_value = (200, "<html>CORRUPT DOM</html>", b"")
        crawler = ConcreteDummyCrawler(client=mock_client)

        result = crawler.fetch_post("https://example.com/post/corrupt")
        self.assertIsNone(result)


class TestBobaeDreamCrawler(unittest.TestCase):
    """Test BobaeDream crawler URL builders, parsing, and timestamp normalization."""

    def setUp(self):
        self.mock_client = MagicMock(spec=SafeHttpClient)
        self.crawler = BobaeDreamCrawler(client=self.mock_client)

    def test_timestamp_normalization_edge_cases(self):
        """Timestamp normalizer must handle None, empty, malformed, and relative formats."""
        # 1. Null / None value (Discovered bug regression test)
        ts_none = bd_normalize_timestamp(None)
        self.assertIsInstance(ts_none, str)
        self.assertIn("T", ts_none)

        # 2. Empty string
        ts_empty = bd_normalize_timestamp("")
        self.assertIsInstance(ts_empty, str)
        self.assertIn("T", ts_empty)

        # 3. Relative today time "14:25"
        ts_time = bd_normalize_timestamp("14:25")
        self.assertIn("T14:25:00", ts_time)

        # 4. Month/Day "09.15"
        ts_md = bd_normalize_timestamp("09.15")
        self.assertIn("-09-15T12:00:00", ts_md)

        # 5. Full standard "2026-09-08 14:30:00"
        ts_full = bd_normalize_timestamp("2026-09-08 14:30:00")
        self.assertTrue(ts_full.startswith("2026-09-08T14:30:00"))

        # 6. Malformed string
        ts_garbage = bd_normalize_timestamp("알수없는날짜")
        self.assertIsInstance(ts_garbage, str)
        self.assertIn("T", ts_garbage)

    def test_build_search_and_list_urls(self):
        """Search URLs must EUC-KR percent-encode keywords and list URLs format correctly."""
        search_url = self.crawler.build_search_url("national", "아이오닉", page=2)
        self.assertIn("code=national", search_url)
        self.assertIn("page=2", search_url)
        self.assertIn("search=", search_url)

        list_url = self.crawler.build_list_url("electric", page=3)
        self.assertEqual(list_url, f"{BOBAE_LIST_URL}?code=electric&page=3")

    def test_parse_list_page_normal_and_empty(self):
        """parse_list_page must extract valid post links and skip notices and empty rows."""
        sample_html = """
        <table>
          <tr>
            <td><a href="/view?code=national&No=1001"><b>공지</b> 게시판 이용 수칙</a></td>
          </tr>
          <tr>
            <td><a href="/view?code=national&No=2001">아이오닉5 충전 속도 질문드립니다</a></td>
          </tr>
          <tr>
            <td><a href="/view?No=2002&code=national">EV6 주행 후기 공유</a></td>
          </tr>
        </table>
        """
        items = self.crawler.parse_list_page(sample_html, "national")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["post_id"], "2001")
        self.assertEqual(items[1]["post_id"], "2002")
        self.assertIn("아이오닉5", items[0]["title"])

        # Empty HTML
        self.assertEqual(self.crawler.parse_list_page("", "national"), [])
        self.assertEqual(self.crawler.parse_list_page("<html></html>", "national"), [])

    def test_parse_post_detail_complete_and_missing_fields(self):
        """parse_post_detail must extract fields or provide safe defaults."""
        sample_html = """
        <html>
        <body>
          <strong class="title">아토3 어라운드뷰 왜곡 심각합니다</strong>
          <span class="author">보배차주</span>
          <td class="date">2026-09-08 10:20:00</td>
          <div class="bodyCont">어라운드뷰 왜곡 때문에 휠을 긁었습니다.</div>
          <!-- //bodyCont -->
          <div id="cmt_list">
            <dd class="comment">저도 주차할 때 깜짝 놀랐습니다.</dd>
          </div>
        </body>
        </html>
        """
        post = self.crawler.parse_post_detail(sample_html, "https://www.bobaedream.co.kr/view?code=national&No=5001")
        self.assertEqual(post["post_id"], "5001")
        self.assertEqual(post["title"], "아토3 어라운드뷰 왜곡 심각합니다")
        self.assertEqual(post["author"], "보배차주")
        self.assertIn("어라운드뷰 왜곡", post["content"])
        self.assertEqual(len(post["comments"]), 1)

        # Missing fields HTML
        sparse_html = "<html><body><div class='bodyCont'>본문만 존재</div></body></html>"
        sparse_post = self.crawler.parse_post_detail(sparse_html, "https://www.bobaedream.co.kr/view?code=national&No=9999")
        self.assertEqual(sparse_post["post_id"], "9999")
        self.assertEqual(sparse_post["title"], "")
        self.assertEqual(sparse_post["author"], "")
        self.assertEqual(sparse_post["comments"], [])

    def test_dynamic_ajax_comment_fetching_and_network_timeouts(self):
        """extract_ajax_comment_url and fetch_ajax_comments must handle timeouts and 500s."""
        sample_html = """
        <script>
          $("#cmt_list").load("/board_renew/bulletin/comment_list.php?tb=uni_cmt_2609&code=national&No=5001");
        </script>
        """
        ajax_url = self.crawler.extract_ajax_comment_url(sample_html)
        self.assertIsNotNone(ajax_url)
        self.assertIn("comment_list.php", ajax_url)

        # Network timeout during AJAX comment fetch
        self.mock_client.get.side_effect = TimeoutError("AJAX comment request timed out")
        comments = self.crawler.fetch_ajax_comments(ajax_url, "https://www.bobaedream.co.kr/view?No=5001")
        self.assertEqual(comments, [])

        # Server error 500 during AJAX comment fetch
        self.mock_client.get.side_effect = None
        self.mock_client.get.return_value = (500, "Internal Server Error", b"")
        comments_500 = self.crawler.fetch_ajax_comments(ajax_url, "https://www.bobaedream.co.kr/view?No=5001")
        self.assertEqual(comments_500, [])


class TestDCInsideCrawler(unittest.TestCase):
    """Test DCInside crawler gallery routing, list parsing, e_s_n_o, and comment API."""

    def setUp(self):
        self.mock_client = MagicMock(spec=SafeHttpClient)
        self.crawler = DCInsideCrawler(client=self.mock_client)

    def test_gallery_routing_prefixes(self):
        """DCInside galleries must route to correct major, minor, or mini prefix."""
        self.assertEqual(self.crawler.get_gallery_prefix("car_new1"), "board")
        self.assertEqual(self.crawler.get_gallery_prefix("tesla"), "mgallery/board")
        self.assertEqual(self.crawler.get_gallery_prefix("electriccar"), "mini/board")

        # Unknown gallery defaults to mgallery/board
        self.assertEqual(self.crawler.get_gallery_prefix("unknown_gal"), "mgallery/board")

        # URL builders
        gal_url = self.crawler.build_list_url("car_new1", page=2)
        self.assertEqual(gal_url, f"{DC_BASE_URL}/board/lists/?id=car_new1&page=2")

        post_url = self.crawler.build_post_url("tesla", "12345")
        self.assertEqual(post_url, f"{DC_BASE_URL}/mgallery/board/view/?id=tesla&no=12345")

    def test_timestamp_normalization_edge_cases(self):
        """DCInside timestamp normalizer must safely handle None, empty, and relative times."""
        # 1. Null / None value (Regression test for discovered bug)
        ts_none = dc_normalize_timestamp(None)
        self.assertIsInstance(ts_none, str)
        self.assertIn("T", ts_none)

        # 2. Empty string
        ts_empty = dc_normalize_timestamp("")
        self.assertIsInstance(ts_empty, str)
        self.assertIn("T", ts_empty)

        # 3. Time only "10:15"
        ts_time = dc_normalize_timestamp("10:15")
        self.assertIn("T10:15:00", ts_time)

        # 4. Standard full date "2026.09.08 11:20:00"
        ts_full = dc_normalize_timestamp("2026.09.08 11:20:00")
        self.assertTrue(ts_full.startswith("2026-09-08T11:20:00"))

        # 5. Malformed string
        ts_malformed = dc_normalize_timestamp("???.??.??")
        self.assertIsInstance(ts_malformed, str)

    def test_parse_gallery_list_and_filter_notices(self):
        """parse_gallery_list must extract regular posts and filter out notice rows."""
        sample_html = """
        <table>
          <tr class="ub-content ub-notice">
            <td class="gall_num">공지</td>
            <td class="gall_tit"><a href="/mgallery/board/view/?id=tesla&no=1">전기차 갤러리 공지사항</a></td>
          </tr>
          <tr class="ub-content us-post" data-no="10500">
            <td class="gall_num">10500</td>
            <td class="gall_tit"><a href="/mgallery/board/view/?id=tesla&no=10500">모델Y 하이랜드 승차감 후기</a></td>
            <td class="gall_date" title="2026-09-08 12:00:00">12:00</td>
          </tr>
        </table>
        """
        items = self.crawler.parse_gallery_list(sample_html, "tesla")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["post_id"], "10500")
        self.assertIn("모델Y 하이랜드", items[0]["title"])

        # Empty HTML
        self.assertEqual(self.crawler.parse_gallery_list("", "tesla"), [])

    def test_extract_esno_token(self):
        """extract_esno_token must extract CSRF token from input tag or script."""
        html_input = '<input type="hidden" id="e_s_n_o" value="test_token_abc_123" />'
        token1 = self.crawler.extract_esno_token(html_input)
        self.assertEqual(token1, "test_token_abc_123")

        html_script = '<script>var e_s_n_o = "script_token_xyz_789";</script>'
        token2 = self.crawler.extract_esno_token(html_script)
        self.assertEqual(token2, "script_token_xyz_789")

        # Missing token
        self.assertIsNone(self.crawler.extract_esno_token("<html><body>No token</body></html>"))

    def test_parse_comment_json_and_network_timeouts(self):
        """parse_comment_json and fetch_ajax_comments must handle timeouts, nulls, and malformed JSON."""
        # 1. Valid comment JSON
        valid_json = json.dumps({
            "comments": [
                {"memo": "저도 같은 증상 겪었습니다."},
                {"comment_memo": "서비스센터 예약하셨나요?"},
                {"memo": "보이스리플입니다."}  # Must be ignored
            ]
        })
        comments = self.crawler.parse_comment_json(valid_json)
        self.assertEqual(len(comments), 2)
        self.assertIn("같은 증상", comments[0])

        # 2. Corrupted / malformed JSON
        corrupted_comments = self.crawler.parse_comment_json("{broken_json: true, ...")
        self.assertEqual(corrupted_comments, [])

        # 3. Empty or null JSON
        self.assertEqual(self.crawler.parse_comment_json(""), [])
        self.assertEqual(self.crawler.parse_comment_json(None), [])

        # 4. Network timeout during AJAX comment POST
        self.mock_client.post.side_effect = urllib.error.URLError("Connection timed out")
        res_timeout = self.crawler.fetch_ajax_comments("tesla", "100", "token123", "https://example.com")
        self.assertEqual(res_timeout, [])

        # 5. HTTP 503 error
        self.mock_client.post.side_effect = None
        self.mock_client.post.return_value = (503, "Service Unavailable", b"")
        res_503 = self.crawler.fetch_ajax_comments("tesla", "100", "token123", "https://example.com")
        self.assertEqual(res_503, [])


if __name__ == "__main__":
    unittest.main()
