#!/usr/bin/env python3
"""
Swarm Audit Test Suite for crawlers/*.py (2026-11-23).
Covers SSRF/URL normalization, LRU cache & memory bounds, HTML/comment/author parsing,
timestamp normalization, and error recovery across BaseCrawler, BobaeDreamCrawler, and DCInsideCrawler.
"""

from __future__ import annotations

import datetime
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.base_crawler import MAX_POST_CACHE_SIZE, BaseCrawler, _normalize_pages
from crawlers.bobaedream import (
    BobaeDreamCrawler,
    _normalize_iso_timestamp as bd_ts,
    extract_container_content as bd_extract,
)
from crawlers.dcinside import (
    DCInsideCrawler,
    _normalize_iso_timestamp as dc_ts,
    extract_container_content as dc_extract,
)
from utils.http_client import SafeHttpClient


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


class TestSwarmCrawlerHardening20261123(unittest.TestCase):
    """Verify SSRF, URL normalization, LRU cache bounds, parsing, timestamps, and recovery."""

    def test_normalize_fetch_url_urljoin_and_authority_guards(self):
        crawler = _DummyCrawler(base_url="https://www.bobaedream.co.kr/list?code=national")
        # Root-relative path resolves cleanly against origin rather than appending onto /list
        resolved = crawler._normalize_fetch_url("/view?code=national&No=123")
        self.assertEqual(resolved, "https://www.bobaedream.co.kr/view?code=national&No=123")

        # Unsafe authorities, bad ports, spaces in host, and control chars are rejected
        for bad in [
            "https://user:pass@www.bobaedream.co.kr/view?No=1",
            "https://www.bobaedream.co.kr\\@evil.com/view",
            "https://www.bobaedream.co.kr:99999/view",
            "https://www.bobaedream.co.kr /view",
            "https://www.bobaedream.co.kr/view\nInjected: 1",
            "javascript:alert(1)",
        ]:
            self.assertIsNone(crawler._normalize_fetch_url(bad), f"Expected None for {bad!r}")

    def test_lru_post_cache_eviction_and_mutation_isolation(self):
        crawler = _DummyCrawler(enable_cache=True, cache_fallback=True)
        # Fill cache up to capacity
        for i in range(MAX_POST_CACHE_SIZE):
            crawler._store_cached_post(f"https://example.com/post/{i}", {"id": i, "tags": ["a"]})

        # Touch post/0 via get_cached_post so post/1 becomes LRU
        hit = crawler.get_cached_post("https://example.com/post/0")
        self.assertIsNotNone(hit)
        hit["tags"].append("mutated")  # Mutate caller copy

        # Cache entry must remain unmutated
        hit_again = crawler.get_cached_post("https://example.com/post/0")
        self.assertEqual(hit_again["tags"], ["a"])

        # Adding one more item evicts post/1 (the least recently used), not post/0
        crawler._store_cached_post("https://example.com/post/new", {"id": "new"})
        self.assertEqual(len(crawler._post_cache), MAX_POST_CACHE_SIZE)
        self.assertIsNotNone(crawler.get_cached_post("https://example.com/post/0"))
        self.assertIsNone(crawler.get_cached_post("https://example.com/post/1"))

    def test_normalize_pages_bounds_extreme_values(self):
        self.assertEqual(_normalize_pages(10**9), 1000)
        self.assertEqual(_normalize_pages(float("inf")), 1)
        self.assertEqual(_normalize_pages(-5), 1)
        self.assertEqual(_normalize_pages(True), 1)

    def test_extract_container_content_ignores_data_class_attribute(self):
        html_bd = '<div data-class="bodyCont">wrong</div><div class="bodyCont">right</div>'
        self.assertEqual(bd_extract(html_bd, "div", "bodyCont"), "right")

        html_dc = '<div myclass="write_div">wrong</div><div class="write_div">right</div>'
        self.assertEqual(dc_extract(html_dc, "div", "write_div"), "right")

    def test_bobaedream_nested_comment_memo_and_notice_filter(self):
        crawler = BobaeDreamCrawler(client=MagicMock(spec=SafeHttpClient))
        comment_html = (
            '<div class="comment_memo"><div class="inner">중첩</div>첫 번째 댓글 본문</div>'
            '<div class="comment_memo">두 번째 댓글</div>'
        )
        comments = crawler.parse_comments_html(comment_html)
        self.assertEqual(len(comments), 2)
        self.assertIn("첫 번째 댓글 본문", comments[0])

        list_html = """
        <a href = "/view?code=ev-club&No=101">필독서 추천 전기차 정비 가이드</a>
        <a href="/view?code=ev-club&No=102">[필독] 게시판 이용 수칙</a>
        <a href="/view?code=ev-club&No=103">공지: 서버 점검 안내</a>
        """
        items = crawler.parse_list_page(list_html, "ev-club")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["post_id"], "101")
        self.assertEqual(items[0]["board_code"], "ev-club")

    def test_bobaedream_detail_attribute_order_and_bytes_fetch(self):
        mock_client = MagicMock(spec=SafeHttpClient)
        html_bytes = (
            '<html><body>'
            '<strong data-id="1" class="post title">배터리 결함 점검 후기</strong>'
            '<span data-nick="x" class="member author">테슬라오너</span>'
            '<div class="bodyCont">충전 중 오류 코드가 발생했습니다.</div>'
            '</body></html>'
        ).encode("utf-8")
        mock_client.get.return_value = (200, html_bytes, html_bytes)
        crawler = BobaeDreamCrawler(client=mock_client)
        post = crawler.fetch_post("https://www.bobaedream.co.kr/view?code=ev-club&No=77")
        self.assertIsNotNone(post)
        self.assertEqual(post["title"], "배터리 결함 점검 후기")
        self.assertEqual(post["author"], "테슬라오너")
        self.assertEqual(post["board_code"], "ev-club")

    def test_dcinside_div_gall_writer_and_js_anchor_skip(self):
        mock_client = MagicMock(spec=SafeHttpClient)
        crawler = DCInsideCrawler(client=mock_client)

        list_html = """
        <table>
          <tr class="ub-content us-post" data-no="555">
            <td class="gall_tit">
              <a href="javascript:view_alert(555)">스크랩</a>
              <a href="/mgallery/board/view/?id=ev-club&no=555">실제 게시글 제목</a>
            </td>
            <td class="gall_date" title="2026-09-08 10:11:21">10:11</td>
          </tr>
        </table>
        """
        items = crawler.parse_gallery_list(list_html, "ev-club")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "실제 게시글 제목")

        detail_html = """
        <html><body>
          <span class="title_subject">모바일/신형 레이아웃 제목</span>
          <div class="gall_writer ub-writer"><span class="nickname">차주A</span><span class="ip">(112.154)</span></div>
          <td class="gall_date">2026.09.08 오후 02:15</td>
          <div class="gallview-contents">본문 내용입니다.</div>
          <div class="comment_box"><span class="ip">(99.99)</span></div>
        </body></html>
        """
        detail = crawler.parse_post_detail(detail_html, "https://gall.dcinside.com/mgallery/board/view/?id=ev-club&no=555")
        self.assertEqual(detail["author"], "차주A (112.154)")
        self.assertEqual(detail["gallery_id"], "ev-club")
        self.assertEqual(detail["created_at"], "2026-09-08T14:15:00+00:00")

    def test_dcinside_no_mobile_fallback_for_non_dc_host(self):
        mock_client = MagicMock(spec=SafeHttpClient)
        mock_client.get.return_value = (404, "Not Found", b"")
        crawler = DCInsideCrawler(client=mock_client)
        res = crawler.fetch_post("https://example.com/post/12345")
        self.assertIsNone(res)
        self.assertEqual(mock_client.get.call_count, 1)

    def test_timestamp_meridiem_ip_guard_and_year_rollover(self):
        # AM/PM in full and 2-digit year timestamps
        self.assertEqual(bd_ts("2026.09.08 오후 02:15"), "2026-09-08T14:15:00+00:00")
        self.assertEqual(bd_ts("26.09.08 (화) 오후 02:15"), "2026-09-08T14:15:00+00:00")
        self.assertEqual(dc_ts("2026년 9월 8일 (화) 오후 02:15"), "2026-09-08T14:15:00+00:00")
        self.assertEqual(dc_ts("2026.09.08 (Wed) 14:15"), "2026-09-08T14:15:00+00:00")
        self.assertIn("T15:20:00", dc_ts("오후 03:20"))
        self.assertIn("T", dc_ts("그저께"))

        # IP address string must not be parsed as 2068-01-01
        ip_ts = bd_ts("192.168.1.1")
        self.assertFalse(ip_ts.startswith("2068-"), f"IP misparsed as date: {ip_ts}")

        # Year rollover when crawling in February for a December post
        class _FakeDateTime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 2, 1, 10, 0, 0, tzinfo=tz)

        with patch("crawlers.bobaedream.datetime.datetime", _FakeDateTime), \
             patch("crawlers.dcinside.datetime.datetime", _FakeDateTime):
            self.assertEqual(bd_ts("12.25 14:00"), "2025-12-25T14:00:00+00:00")
            self.assertEqual(dc_ts("12.25 14:00"), "2025-12-25T14:00:00+00:00")


if __name__ == "__main__":
    unittest.main()
