#!/usr/bin/env python3
"""
Swarm Audit Regression Test Suite for crawlers/*.py (2026-11-24).
Verifies fixes for:
- LRU post cache capacity preservation on existing-key updates
- Referer control-char / null-byte sanitization
- OverflowError-safe timeout handling & CircuitBreaker attribute fallback
- BobaeDream seed fallback alias (raw_bobae_emerging.json)
- URL canonicalization whitespace/authority guards & page bounds
- CSS class token boundary & single-pass comment/script masking in extract_container_content
- WAF/maintenance false-positive protection on large article bodies
- Leap-year 02.29 rollover across non-leap years
- List parser comment/script masking, DCInside mixed data-no rows, icon-only anchors, and gall_date attribute order
- Empty leading title/author fallbacks and nested tag static comment extraction
"""

from __future__ import annotations

import datetime
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.base_crawler import (
    MAX_POST_CACHE_SIZE,
    BaseCrawler,
    _sanitize_referer,
)
from crawlers.bobaedream import (
    BobaeDreamCrawler,
    _canonicalize_bobaedream_href,
    _normalize_iso_timestamp as bd_ts,
    extract_container_content as bd_extract,
    is_deleted_or_restricted as bd_blocked,
)
from crawlers.dcinside import (
    DCInsideCrawler,
    _normalize_iso_timestamp as dc_ts,
    extract_container_content as dc_extract,
    is_deleted_or_restricted as dc_blocked,
)
from utils.http_client import CircuitBreaker, SafeHttpClient


class _DummyCrawler(BaseCrawler):
    def parse_post_detail(self, html_content: str, post_url: str, **kwargs):
        return {
            "platform": "dummy",
            "post_id": "1",
            "url": post_url,
            "title": "Dummy Title",
            "content": html_content,
            "comments": [],
        }


class TestSwarmCrawlerHardening20261124(unittest.TestCase):
    """Regression tests for 2026-11-24 crawlers/ audit fixes."""

    def test_lru_cache_update_existing_key_preserves_capacity(self):
        crawler = _DummyCrawler(enable_cache=True, cache_fallback=True)
        for i in range(MAX_POST_CACHE_SIZE):
            crawler._store_cached_post(f"https://example.com/post/{i}", {"id": i})
        self.assertEqual(len(crawler._post_cache), MAX_POST_CACHE_SIZE)

        # Updating an existing key at full capacity must not evict another entry
        crawler._store_cached_post("https://example.com/post/0", {"id": 0, "updated": True})
        self.assertEqual(len(crawler._post_cache), MAX_POST_CACHE_SIZE)
        self.assertEqual(crawler.get_cached_post("https://example.com/post/0")["updated"], True)
        self.assertIsNotNone(crawler.get_cached_post("https://example.com/post/1"))

    def test_sanitize_referer_strips_control_chars_and_null(self):
        cleaned = _sanitize_referer("https://www.bobaedream.co.kr/list\r\nX-Injected: 1\x00\x0b\x7f")
        self.assertEqual(cleaned, "https://www.bobaedream.co.kr/listX-Injected: 1")
        self.assertIsNone(_sanitize_referer("\r\n\x00\x0b"))

    def test_huge_int_timeout_and_circuit_breaker_fallback(self):
        crawler = BobaeDreamCrawler(client=MagicMock(spec=SafeHttpClient), timeout=10**400)
        self.assertEqual(crawler.connect_timeout, 5.0)
        self.assertEqual(crawler.read_timeout, 15.0)

        class _MinimalClient:
            def __init__(self):
                self.circuit_breaker = CircuitBreaker(failure_threshold=1, cooldown_seconds=30.0)

        min_client = _MinimalClient()
        c = _DummyCrawler(client=min_client, base_url="https://www.bobaedream.co.kr")
        self.assertFalse(c.is_circuit_open())
        self.assertEqual(c.get_circuit_state(), "CLOSED")
        min_client.circuit_breaker.record_failure("www.bobaedream.co.kr", status_code=503)
        self.assertTrue(c.is_circuit_open())
        self.assertEqual(c.get_circuit_state(), "OPEN")

    def test_bobaedream_seed_fallback_loads_raw_bobae_emerging(self):
        crawler = BobaeDreamCrawler(client=MagicMock(spec=SafeHttpClient))
        posts = crawler.load_seed_posts(limit=2)
        self.assertGreater(len(posts), 0)
        self.assertEqual(posts[0].get("platform"), "bobaedream")
        self.assertTrue(posts[0].get("title"))
        self.assertTrue(posts[0].get("url"))

    def test_canonicalize_bobaedream_href_whitespace_and_host_guards(self):
        self.assertIsNone(_canonicalize_bobaedream_href("https://www.bobaedream.co.kr\u3000/view?No=1"))
        self.assertIsNone(_canonicalize_bobaedream_href("https://evil.com/view?No=1"))
        self.assertIsNone(_canonicalize_bobaedream_href("https://user@www.bobaedream.co.kr/view?No=1"))
        self.assertIsNone(_canonicalize_bobaedream_href("https://www.bobaedream.co.kr:8080/view?No=1"))
        self.assertEqual(
            _canonicalize_bobaedream_href("/view?code=national&No=123"),
            "https://www.bobaedream.co.kr/view?code=national&No=123",
        )

    def test_extract_container_content_css_boundary_and_script_comment_masking(self):
        # Hyphenated class names must not falsely match
        html_bd = (
            '<script>var marker = "<!--";</script>'
            '<div class="my-bodyCont">wrong</div>'
            '<div class="bodyCont-wrapper">also wrong</div>'
            '<div class="article bodyCont">실제 본문</div>'
        )
        self.assertEqual(bd_extract(html_bd, "div", "bodyCont"), "실제 본문")

        html_dc = (
            '<!-- <script> --><div class="write_div-inner">wrong</div>'
            '<div class="write_div main">DC 실제 본문</div>'
        )
        self.assertEqual(dc_extract(html_dc, "div", "write_div"), "DC 실제 본문")

    def test_is_deleted_or_restricted_respects_large_body_and_waf_titles(self):
        long_prose = "현대차 블루링크 앱에서 '서비스 점검 중' 및 '접근이 차단되었습니다' 오류가 반복 발생하여 서비스센터 입고 예정입니다."
        bd_html = f'<html><body><div class="bodyCont">{long_prose}</div></body></html>'
        self.assertEqual(bd_blocked(bd_html), (False, ""))

        dc_html = f'<html><body><div class="gallview-contents">{long_prose}</div></body></html>'
        self.assertEqual(dc_blocked(dc_html), (False, ""))

        # Actual maintenance or WAF blocks without article body are still blocked
        self.assertEqual(bd_blocked("<html><body>서비스 점검 중입니다.</body></html>")[0], True)
        self.assertEqual(dc_blocked("<html><title>403 Forbidden</title></html>")[0], True)
        self.assertEqual(
            bd_blocked(f'<html><title>Just a moment...</title><div class="bodyCont">{long_prose}</div></html>')[1],
            "cloudflare_challenge",
        )

    def test_leap_year_feb_29_rollover_in_non_leap_year(self):
        class _FakeDateTime2026(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 3, 1, 10, 0, 0, tzinfo=tz)

        with patch("crawlers.bobaedream.datetime.datetime", _FakeDateTime2026), \
             patch("crawlers.dcinside.datetime.datetime", _FakeDateTime2026):
            self.assertEqual(bd_ts("02.29 10:00"), "2024-02-29T10:00:00+00:00")
            self.assertEqual(dc_ts("02.29 10:00"), "2024-02-29T10:00:00+00:00")

    def test_list_parsers_ignore_html_comments_and_scripts(self):
        bd = BobaeDreamCrawler(client=MagicMock(spec=SafeHttpClient))
        bd_html = """
        <!-- <a href="/view?code=national&No=999">주석 처리된 가짜 글</a> -->
        <script>var tpl = '<a href="/view?code=national&No=888">스크립트 가짜 글</a>';</script>
        <a href="/view?code=national&No=101">진짜 게시글 제목</a>
        """
        bd_items = bd.parse_list_page(bd_html, "national")
        self.assertEqual([it["post_id"] for it in bd_items], ["101"])

        dc = DCInsideCrawler(client=MagicMock(spec=SafeHttpClient))
        dc_html = """
        <table>
          <!-- <tr class="ub-content" data-no="999"><td class="gall_tit"><a href="/board/view/?id=car_new1&no=999">주석 글</a></td></tr> -->
          <script>var row = '<tr class="ub-content" data-no="888"><td class="gall_tit"><a href="/board/view/?id=car_new1&no=888">스크립트 글</a></td></tr>';</script>
          <tr class="ub-content us-post" data-no="101">
            <td class="gall_tit"><a href="/board/view/?id=car_new1&no=101">DC 진짜 글</a></td>
          </tr>
        </table>
        """
        dc_items = dc.parse_gallery_list(dc_html, "car_new1")
        self.assertEqual([it["post_id"] for it in dc_items], ["101"])

    def test_dcinside_gallery_list_mixed_data_no_icon_anchor_and_date_attr_order(self):
        dc = DCInsideCrawler(client=MagicMock(spec=SafeHttpClient))
        html_sample = """
        <table>
          <tr class="ub-content us-post" data-no="201">
            <td class="gall_tit">
              <a href="/board/view/?id=car_new1&no=201"><em class="icon_img"></em></a>
              <a href="/board/view/?id=car_new1&no=201">아이콘 링크 뒤의 실제 제목</a>
            </td>
            <td title="2026-09-08 10:11:21" class="gall_date">10:11</td>
          </tr>
          <tr class="ub-content us-post">
            <td class="gall_num">202</td>
            <td class="gall_tit">
              <a href="/board/view/?id=car_new1&no=202">data-no 없는 행 제목</a>
            </td>
            <td class="gall_date" title="2026-09-08 11:22:33">11:22</td>
          </tr>
        </table>
        """
        items = dc.parse_gallery_list(html_sample, "car_new1")
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["post_id"], "201")
        self.assertEqual(items[0]["title"], "아이콘 링크 뒤의 실제 제목")
        self.assertEqual(items[0]["created_at"], "2026-09-08T10:11:21+00:00")
        self.assertEqual(items[1]["post_id"], "202")
        self.assertEqual(items[1]["title"], "data-no 없는 행 제목")

    def test_detail_parsers_empty_leading_tags_and_nested_static_comment(self):
        bd = BobaeDreamCrawler(client=MagicMock(spec=SafeHttpClient))
        bd_html = """
        <html>
          <head><meta property="og:title" content="OG 대체 제목"></head>
          <body>
            <strong class="title"></strong>
            <div class="bodyCont">본문 내용</div>
          </body>
        </html>
        """
        bd_detail = bd.parse_post_detail(bd_html, "https://www.bobaedream.co.kr/view?code=national&No=1")
        self.assertEqual(bd_detail["title"], "OG 대체 제목")

        dc = DCInsideCrawler(client=MagicMock(spec=SafeHttpClient))
        dc_html = """
        <html>
          <head>
            <meta content="DC OG 제목" property="og:title">
            <meta content="DC OG 본문 설명" property="og:description">
          </head>
          <body>
            <span class="title_subject"></span>
            <div class="gall_writer"><span class="nickname"></span><span data-nick="실제닉네임"></span></div>
            <div class="comment_list">
              <div class="usertxt"><span class="badge">베스트</span> 실제 댓글 본문입니다</div>
            </div>
          </body>
        </html>
        """
        dc_detail = dc.parse_post_detail(dc_html, "https://gall.dcinside.com/board/view/?id=car_new1&no=10")
        self.assertEqual(dc_detail["title"], "DC OG 제목")
        self.assertEqual(dc_detail["author"], "실제닉네임")
        self.assertEqual(dc_detail["content"], "DC OG 본문 설명")
        self.assertEqual(len(dc_detail["comments"]), 1)
        self.assertIn("실제 댓글 본문입니다", dc_detail["comments"][0])

    def test_url_page_bounds_jitter_nan_comment_and_empty_boards(self):
        bd = BobaeDreamCrawler(client=MagicMock(spec=SafeHttpClient))
        dc = DCInsideCrawler(client=MagicMock(spec=SafeHttpClient))

        self.assertIn("page=1", bd.build_list_url("national", page=True))
        self.assertIn("page=1", bd.build_search_url("national", "전기차", page=float("inf")))
        self.assertIn("page=100000", dc.build_list_url("car_new1", page=10**100))

        # Must not raise on bool or overflow floats
        bd.sleep_with_jitter(True, 1.0)
        bd.sleep_with_jitter(10**400, 1.0)

        # NaN is_delete in DCInside JSON comment must not be treated as truthy (deleted)
        payload = json.dumps({"comments": [{"memo": "정상 댓글입니다", "is_delete": float("nan")}]})
        self.assertEqual(dc.parse_comment_json(payload), ["정상 댓글입니다"])
        payload_del = json.dumps({"comments": [{"memo": "삭제될 댓글", "is_delete": 1}]})
        self.assertEqual(dc.parse_comment_json(payload_del), [])

        # Empty/whitespace board or gallery names must be skipped
        with patch.object(bd, "search_board", return_value=[]) as mock_bd_search:
            bd.crawl_posts_by_keyword("배터리", boards=["", "   ", "electric"])
            mock_bd_search.assert_called_once_with("electric", "배터리", pages=1, limit=None)

        with patch.object(dc, "search_gallery", return_value=[]) as mock_dc_search:
            dc.crawl_posts_by_keyword("배터리", galleries=["", "  ", "tesla"])
            mock_dc_search.assert_called_once_with("tesla", "배터리", pages=1, limit=None)


if __name__ == "__main__":
    unittest.main()
