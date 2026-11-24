#!/usr/bin/env python3
"""
Swarm Audit Regression Test Suite for crawlers/*.py (2026-11-25).
Verifies fixes for:
- HTML-entity-encoded leading whitespace bypass in URL normalization
- Path traversal sanitization in BaseCrawler.load_seed_fallback
- Leap-year Feb 29 rollover when now is early in a leap year (e.g. 2024-01-15)
- BobaeDream "어제 오후 HH:MM" and Korean AM/PM timestamp parsing
- Linear-time (ReDoS-safe) fallback anchor parsing in BobaeDreamCrawler.parse_list_page
- Apostrophe/quote preservation in og:title, og:description, and data-nick attributes
- Balanced nested <div> extraction for content01, thum-txt, and DCInside static comments
"""

from __future__ import annotations

import datetime
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.base_crawler import BaseCrawler
from crawlers.bobaedream import (
    BobaeDreamCrawler,
    _normalize_iso_timestamp as bd_ts,
)
from crawlers.dcinside import (
    DCInsideCrawler,
    _normalize_iso_timestamp as dc_ts,
)
from utils.http_client import SafeHttpClient


class _DummyCrawler(BaseCrawler):
    def parse_post_detail(self, html_content: str, post_url: str, **kwargs):
        return {
            "platform": "dummy",
            "post_id": "1",
            "url": post_url,
            "title": "Dummy",
            "content": html_content,
            "comments": [],
        }


class TestSwarmCrawlerHardening20261125(unittest.TestCase):
    """Regression tests for 2026-11-25 crawlers/ audit fixes."""

    def test_normalize_fetch_url_strips_entity_leading_whitespace(self):
        crawler = _DummyCrawler(base_url="https://www.bobaedream.co.kr")
        self.assertIsNone(crawler._normalize_fetch_url("&#32;javascript:alert(1)"))
        self.assertEqual(
            crawler._normalize_fetch_url("&#32;/view?code=national&No=42"),
            "https://www.bobaedream.co.kr/view?code=national&No=42",
        )

    def test_load_seed_fallback_blocks_platform_path_traversal(self):
        crawler = _DummyCrawler()
        # Traversal string must not match a custom raw_<traversal>_emerging.json path
        # and must not crash; only valid compiled_complaints or filtered results return.
        res = crawler.load_seed_fallback(platform_name="../evil/../../secret", limit=5)
        self.assertIsInstance(res, list)
        self.assertEqual(res, [])

    def test_leap_year_feb29_rollover_from_early_leap_year(self):
        class _FakeLeapYearJan(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2024, 1, 15, 10, 0, 0, tzinfo=tz)

        with patch("crawlers.bobaedream.datetime.datetime", _FakeLeapYearJan), \
             patch("crawlers.dcinside.datetime.datetime", _FakeLeapYearJan):
            self.assertEqual(bd_ts("02.29 10:00"), "2020-02-29T10:00:00+00:00")
            self.assertEqual(dc_ts("02.29 10:00"), "2020-02-29T10:00:00+00:00")

    def test_bobaedream_yesterday_meridiem_and_kr_ampm_timestamps(self):
        ts_yesterday = bd_ts("어제 오후 02:30")
        self.assertIn("T14:30:00+00:00", ts_yesterday)
        ts_kr_pm = bd_ts("2026년 9월 8일 PM 02:15")
        self.assertEqual(ts_kr_pm, "2026-09-08T14:15:00+00:00")

    def test_bobaedream_parse_list_page_redos_resilience(self):
        bd = BobaeDreamCrawler(client=MagicMock(spec=SafeHttpClient))
        # Pathological input that would trigger O(N^4) backtracking in unguarded alt_pattern
        payload = '<a href="https://www.bobaedream.co.kr/' + ("viewNo=1" * 150) + '">제목</a>'
        t0 = time.monotonic()
        items = bd.parse_list_page(payload, "national")
        elapsed = time.monotonic() - t0
        self.assertEqual(items, [])
        self.assertLess(elapsed, 0.25)

    def test_og_meta_and_data_nick_preserve_mixed_quotes(self):
        bd = BobaeDreamCrawler(client=MagicMock(spec=SafeHttpClient))
        bd_html = """
        <html>
          <head><meta property="og:title" content="Bob's EV Battery Review"></head>
          <body><div class="content01"><div class="inner">중첩 박스</div>실제 본문 내용</div></body>
        </html>
        """
        bd_detail = bd.parse_post_detail(bd_html, "https://www.bobaedream.co.kr/view?code=electric&No=5")
        self.assertEqual(bd_detail["title"], "Bob's EV Battery Review")
        self.assertIn("실제 본문 내용", bd_detail["content"])

        dc = DCInsideCrawler(client=MagicMock(spec=SafeHttpClient))
        dc_html = """
        <html>
          <head>
            <meta property="og:title" content="Driver's ICCU Issue">
            <meta property='og:description' content='He said "recall now"'>
          </head>
          <body>
            <div class="gall_writer"><span data-nick="Kim'sGarage"></span></div>
            <div class="thum-txt"><div class="img-box">사진</div>모바일 중첩 본문 내용</div>
            <div class="comment_list">
              <div class="usertxt"><div class="quote">원댓글</div>중첩 div 실제 댓글 본문입니다</div>
            </div>
          </body>
        </html>
        """
        dc_detail = dc.parse_post_detail(dc_html, "https://gall.dcinside.com/board/view/?id=car_new1&no=77")
        self.assertEqual(dc_detail["title"], "Driver's ICCU Issue")
        self.assertEqual(dc_detail["author"], "Kim'sGarage")
        self.assertIn("모바일 중첩 본문 내용", dc_detail["content"])
        self.assertEqual(len(dc_detail["comments"]), 1)
        self.assertIn("중첩 div 실제 댓글 본문입니다", dc_detail["comments"][0])

        # Also check og:description fallback when thum-txt/write_div are absent
        dc_og_only = """
        <html>
          <head>
            <meta property="og:title" content="Driver's ICCU Issue">
            <meta property='og:description' content='He said "recall now"'>
          </head>
          <body></body>
        </html>
        """
        dc_og_detail = dc.parse_post_detail(dc_og_only, "https://gall.dcinside.com/board/view/?id=car_new1&no=78")
        self.assertEqual(dc_og_detail["content"], 'He said "recall now"')


if __name__ == "__main__":
    unittest.main()
