#!/usr/bin/env python3
"""
Swarm Audit Regression Test Suite for crawlers/*.py (2026-11-26).
Verifies fixes for:
- Linear-time O(N) _mask_comments_and_scripts on unclosed <!-- / <script> / <style> tags
- Linear-time list parsing in BobaeDreamCrawler.parse_list_page and DCInsideCrawler.parse_gallery_list
  on thousands of unclosed <a> / <tr> tags
- BobaeDream fallback anchor parameter boundary and entity-unescaping
- DCInside data-href shadowing guard, entity-encoded javascript: skip, and external host filter
- HTML comment masking in is_deleted_or_restricted (avoiding comment false positives/negatives)
- Tag-matched and nested title/date extraction in parse_post_detail (BobaeDream & DCInside)
- Post-urljoin control-character validation in BaseCrawler._normalize_fetch_url and LSP fetch_ajax_comments
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.base_crawler import BaseCrawler, _mask_comments_and_scripts
from crawlers.bobaedream import (
    BobaeDreamCrawler,
    is_deleted_or_restricted as bd_blocked,
)
from crawlers.dcinside import (
    DCInsideCrawler,
    is_deleted_or_restricted as dc_blocked,
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


class TestSwarmCrawlerHardening20261126(unittest.TestCase):
    """Regression tests for 2026-11-26 crawlers/ audit fixes."""

    def test_mask_comments_and_scripts_linear_time_unclosed_tags(self):
        t0 = time.monotonic()
        res_comment = _mask_comments_and_scripts("<!--" * 15000)
        res_script = _mask_comments_and_scripts("<script>" * 15000)
        res_style = _mask_comments_and_scripts("<style>" * 15000)
        elapsed = time.monotonic() - t0

        self.assertEqual(len(res_comment), len("<!--" * 15000))
        self.assertEqual(len(res_script), len("<script>" * 15000))
        self.assertEqual(len(res_style), len("<style>" * 15000))
        self.assertLess(elapsed, 0.5)

        # Valid blocks still masked while preserving string length and outer text
        sample = '<!-- fake --><div class="x">ok</div><script>var a = "<!--";</script>'
        masked = _mask_comments_and_scripts(sample)
        self.assertEqual(len(masked), len(sample))
        self.assertIn('<div class="x">ok</div>', masked)
        self.assertNotIn("fake", masked)
        self.assertNotIn("var a", masked)

    def test_list_parsers_linear_time_on_unclosed_tags(self):
        bd = BobaeDreamCrawler(client=MagicMock(spec=SafeHttpClient))
        dc = DCInsideCrawler(client=MagicMock(spec=SafeHttpClient))

        t0 = time.monotonic()
        bd_items = bd.parse_list_page('<a href="/view?No=1">' * 8000, "national")
        dc_tr_items = dc.parse_gallery_list('<tr class="ub-content" data-no="1">' * 8000, "car_new1")
        dc_a_items = dc.parse_gallery_list('<a href="/board/view/?id=car_new1&no=1">' * 8000, "car_new1")
        elapsed = time.monotonic() - t0

        self.assertEqual(bd_items, [])
        self.assertEqual(dc_tr_items, [])
        self.assertEqual(dc_a_items, [])
        self.assertLess(elapsed, 0.5)

    def test_bobaedream_fallback_anchor_param_boundaries_and_entities(self):
        bd = BobaeDreamCrawler(client=MagicMock(spec=SafeHttpClient))
        html_sample = """
        <a href="/board/view.html?postno=999&amp;code=national">가짜 파라미터</a>
        <a href="/board/view.html?No=1234&amp;code=electric#reply">전기차 정상 제목</a>
        """
        items = bd.parse_list_page(html_sample, "national")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["post_id"], "1234")
        self.assertEqual(items[0]["board_code"], "electric")
        self.assertEqual(items[0]["title"], "전기차 정상 제목")

    def test_dcinside_list_data_href_and_external_alt_anchor_guards(self):
        dc = DCInsideCrawler(client=MagicMock(spec=SafeHttpClient))
        # Row with data-href before href and entity-encoded javascript anchor
        html_rows = """
        <table>
          <tr class="ub-content us-post" data-no="501">
            <td class="gall_tit">
              <a href="&#x6a;avascript:alert(1)">스크랩</a>
              <a data-href="javascript:void(0)" href="/board/view/?id=car_new1&no=501">실제 게시글 제목</a>
            </td>
          </tr>
        </table>
        """
        items = dc.parse_gallery_list(html_rows, "car_new1")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["post_id"], "501")
        self.assertEqual(items[0]["title"], "실제 게시글 제목")

        # Fallback anchor parser must reject external hosts and unsafe authorities
        html_alt = """
        <a href="https://evil.com/board/car_new1/9999">외부 악성 링크</a>
        <a href="https://user@gall.dcinside.com/board/car_new1/8888">유저인포 링크</a>
        <a href="https://gall.dcinside.com/board/view/?id=car_new1&amp;no=7777">정상 DC 링크</a>
        """
        alt_items = dc.parse_gallery_list(html_alt, "car_new1")
        self.assertEqual([it["post_id"] for it in alt_items], ["7777"])

    def test_is_deleted_or_restricted_ignores_html_comments(self):
        # Short valid post with commented-out deleted marker must NOT be treated as deleted
        bd_short_valid = '<html><body><!-- 삭제된 게시물입니다 --><div class="bodyCont">짧은 정상 글</div></body></html>'
        self.assertEqual(bd_blocked(bd_short_valid), (False, ""))

        dc_short_valid = '<html><body><!-- 삭제된 게시물입니다 --><div class="write_div">짧은 정상 글</div></body></html>'
        self.assertEqual(dc_blocked(dc_short_valid), (False, ""))

        # Commented-out dummy large body must NOT mask a real blocked/deleted message
        bd_commented_body = (
            '<html><body>'
            '<!-- <div class="bodyCont">' + ('가' * 80) + '</div> -->'
            '<div>서비스 점검 중입니다.</div>'
            '</body></html>'
        )
        self.assertEqual(bd_blocked(bd_commented_body), (True, "service_maintenance"))

        # Script alert() deleted markers must still be detected
        self.assertEqual(bd_blocked("<script>alert('삭제된 게시물입니다.');</script>"), (True, "deleted_post"))
        self.assertEqual(dc_blocked("<script>alert('삭제된 게시물입니다.');</script>"), (True, "deleted_post"))

    def test_detail_parsers_nested_and_mismatched_title_and_date_tags(self):
        dc = DCInsideCrawler(client=MagicMock(spec=SafeHttpClient))
        dc_html = """
        <html><body>
          <h3 class="title_subject"><span class="badge">[일반]</span> 아이오닉5 ICCU 후기</h3>
          <td class="gall_date"><span>작성일</span> 2026.09.08 14:20</td>
          <div class="write_div">본문 내용입니다.</div>
        </body></html>
        """
        dc_det = dc.parse_post_detail(dc_html, "https://gall.dcinside.com/board/view/?id=car_new1&no=10")
        self.assertEqual(dc_det["title"], "[일반] 아이오닉5 ICCU 후기")
        self.assertEqual(dc_det["created_at"], "2026-09-08T14:20:00+00:00")

        dc_nested_span_html = """
        <html><body>
          <span class="title_subject"><span class="badge">[후기]</span> 중첩 스팬 제목</span>
          <div class="write_div">본문입니다.</div>
        </body></html>
        """
        dc_det2 = dc.parse_post_detail(dc_nested_span_html, "https://gall.dcinside.com/board/view/?id=car_new1&no=11")
        self.assertEqual(dc_det2["title"], "[후기] 중첩 스팬 제목")

        bd = BobaeDreamCrawler(client=MagicMock(spec=SafeHttpClient))
        bd_html = """
        <html><body>
          <strong class="title">보배드림 제목</strong>
          <span myclass="date">1999.01.01</span>
          <td class="date"><span>등록일</span> 2026.09.08 15:30</td>
          <!-- <div id="print_area">주석 처리된 가짜 본문</div> -->
          <div class="bodyCont">실제 본문</div>
        </body></html>
        """
        bd_det = bd.parse_post_detail(bd_html, "https://www.bobaedream.co.kr/view?code=national&No=20")
        self.assertEqual(bd_det["created_at"], "2026-09-08T15:30:00+00:00")
        self.assertEqual(bd_det["content"], "실제 본문")

    def test_normalize_fetch_url_post_urljoin_ctrl_check_and_lsp_ajax(self):
        crawler = _DummyCrawler(base_url="https://www.bobaedream.co.kr")
        # Dirty base_url containing CRLF or NUL must not survive urljoin
        self.assertIsNone(
            crawler._normalize_fetch_url("view?No=1", base_url="https://www.bobaedream.co.kr/\r\nX-Injected: 1/sub/")
        )
        self.assertIsNone(
            crawler._normalize_fetch_url("view?No=1", base_url="https://www.bobaedream.co.kr/\x00sub/")
        )
        self.assertIsNone(crawler._normalize_fetch_url("https://@www.bobaedream.co.kr/view?No=1"))

        # BobaeDreamCrawler.fetch_ajax_comments works without positional referer (LSP)
        mock_client = MagicMock(spec=SafeHttpClient)
        mock_client.get.return_value = (200, '<dd class="comment">테스트 댓글입니다</dd>', b"")
        bd = BobaeDreamCrawler(client=mock_client)
        comments = bd.fetch_ajax_comments("/board_renew/bulletin/comment_list.php?No=1")
        self.assertEqual(comments, ["테스트 댓글입니다"])

    def test_dcinside_gall_num_notice_linear_time_on_malformed_td(self):
        dc = DCInsideCrawler(client=MagicMock(spec=SafeHttpClient))
        # Malformed unclosed spans/tags inside gall_num td must not cause ReDoS backtracking
        evil_td = '<tr class="ub-content" data-no="999"><td class="gall_num">' + ("<span>" * 5000) + '공지</td></tr>'
        t0 = time.monotonic()
        items = dc.parse_gallery_list(evil_td, "car_new1")
        elapsed = time.monotonic() - t0
        self.assertEqual(items, [])
        self.assertLess(elapsed, 0.5)

        # Normal numeric gall_num without data-no still extracts post_no, and nested notice span is skipped
        normal_html = """
        <table>
          <tr class="ub-content">
            <td class="gall_num"><b>공지</b></td>
            <td class="gall_tit"><a href="/board/view/?id=car_new1&no=1">공지글</a></td>
          </tr>
          <tr class="ub-content">
            <td class="gall_num">12345</td>
            <td class="gall_tit"><a href="/board/view/?id=car_new1&no=12345">정상글</a></td>
          </tr>
        </table>
        """
        parsed = dc.parse_gallery_list(normal_html, "car_new1")
        self.assertEqual([it["post_id"] for it in parsed], ["12345"])


if __name__ == "__main__":
    unittest.main()
