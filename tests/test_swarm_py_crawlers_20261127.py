#!/usr/bin/env python3
"""
Swarm Audit Regression Test Suite for crawlers/*.py (2026-11-27).
Verifies fixes for:
- Linear-time O(N) _mask_comments_and_scripts on unclosed <script / <style tags without '>'
- Linear-time O(N) HTML parsing in extract_container_content, list parsers, comment parsers,
  e_s_n_o extraction, is_deleted_or_restricted, and parse_post_detail (BobaeDream & DCInside)
- DCInside parse_comment_json huge integer is_delete OverflowError guard
- DCInside parse_gallery_list non-HTTP scheme filtering and exact CSS token matching in gall_num
- Pagination loops (_crawl_list_pages / _crawl_gallery_pages) avoiding false-positive aborts on
  post titles containing maintenance/deleted phrases
- BobaeDream parse_post_detail title matching when heading text equals tag name (e.g. <h2>h2</h2>)
"""

from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from crawlers.base_crawler import _mask_comments_and_scripts
from crawlers.bobaedream import (
    BobaeDreamCrawler,
    extract_container_content as bd_extract,
    is_deleted_or_restricted as bd_blocked,
)
from crawlers.dcinside import (
    DCInsideCrawler,
    _extract_td_inner_by_class,
    extract_container_content as dc_extract,
    is_deleted_or_restricted as dc_blocked,
)
from utils.http_client import SafeHttpClient


class TestSwarmCrawlerHardening20261127(unittest.TestCase):
    """Regression tests for 2026-11-27 crawlers/ audit fixes."""

    def test_redos_linear_time_on_malformed_and_unclosed_tags(self):
        bd = BobaeDreamCrawler(client=MagicMock(spec=SafeHttpClient))
        dc = DCInsideCrawler(client=MagicMock(spec=SafeHttpClient))

        t0 = time.monotonic()
        self.assertEqual(_mask_comments_and_scripts("<script " * 15000), "<script " * 15000)
        self.assertEqual(_mask_comments_and_scripts("<style " * 15000), "<style " * 15000)

        self.assertEqual(bd_extract("<div " * 10000, "div", "bodyCont"), "")
        self.assertEqual(bd_extract("<div " * 10000 + ">", "div", "bodyCont"), "")
        self.assertEqual(
            bd_extract('<div class="bodyCont">' + "<div " * 10000, "div", "bodyCont"),
            "<div " * 10000,
        )
        self.assertEqual(dc_extract("<div " * 10000, "div", "write_div"), "")
        self.assertEqual(
            dc_extract('<div class="write_div">' + "<div " * 10000, "div", "write_div"),
            "<div " * 10000,
        )

        self.assertEqual(bd.parse_list_page("<a " * 10000 + "</a>", "national"), [])
        self.assertEqual(bd.parse_list_page("<a >" * 10000 + "</a>", "national"), [])
        self.assertEqual(bd.parse_comments_html("<dd " * 10000 + ">"), [])
        self.assertEqual(bd_blocked("<div " * 10000)[0], False)
        bd.parse_post_detail(
            "<strong " * 10000 + ">",
            "https://www.bobaedream.co.kr/view?code=national&No=1",
        )

        self.assertEqual(dc.parse_gallery_list("<tr " * 10000 + "</tr>", "car_new1"), [])
        self.assertEqual(dc.parse_gallery_list("<tr>" * 10000 + "</tr>", "car_new1"), [])
        self.assertEqual(dc.parse_gallery_list("<a " * 10000 + "</a>", "car_new1"), [])
        self.assertIsNone(dc.extract_esno_token("<input " * 10000 + "e_s_n_o"))
        self.assertEqual(dc_blocked("<div " * 10000)[0], False)
        dc.parse_post_detail(
            "<span " * 10000 + ">",
            "https://gall.dcinside.com/board/view/?id=car_new1&no=1",
        )
        elapsed = time.monotonic() - t0
        self.assertLess(elapsed, 0.75)

    def test_dcinside_parse_comment_json_huge_int_is_delete_no_overflow(self):
        dc = DCInsideCrawler(client=MagicMock(spec=SafeHttpClient))
        huge_int = "9" * 500
        payload = (
            '{"comments": ['
            '{"memo": "삭제될 댓글입니다", "is_delete": ' + huge_int + '},'
            '{"memo": "정상 댓글입니다", "is_delete": 0}'
            "]}"
        )
        comments = dc.parse_comment_json(payload)
        self.assertEqual(comments, ["정상 댓글입니다"])

        # Also verify standard JSON bool/string/float is_delete
        payload2 = json.dumps({
            "comments": [
                {"memo": "생존 댓글", "is_delete": False},
                {"memo": "삭제 댓글", "is_delete": "Y"},
            ]
        })
        self.assertEqual(dc.parse_comment_json(payload2), ["생존 댓글"])

    def test_dcinside_gallery_list_scheme_and_gall_num_token_guards(self):
        dc = DCInsideCrawler(client=MagicMock(spec=SafeHttpClient))

        # Exact class token matching in _extract_td_inner_by_class
        row = '<td class="gall_num_hidden">999</td><td class="gall_num">1234</td>'
        self.assertEqual(_extract_td_inner_by_class(row, "gall_num"), "1234")

        # Fallback anchor list must ignore non-http schemes even if path contains /board/
        html_alt = """
        <a href="data:text/html,/board/car_new1/9999">데이터 스킴 링크</a>
        <a href="vbscript:msgbox('/board/car_new1/8888')">VB스크립트 링크</a>
        <a href="java&#x09;script:/board/car_new1/7777">제어문자 스킴 링크</a>
        <a href="https://gall.dcinside.com/board/car_new1/5555">정상 게시글 제목</a>
        """
        items = dc.parse_gallery_list(html_alt, "car_new1")
        self.assertEqual([it["post_id"] for it in items], ["5555"])

    def test_list_pagination_does_not_abort_on_post_title_maintenance_phrase(self):
        bd_client = MagicMock(spec=SafeHttpClient)
        bd_list_html = """
        <html><body>
          <table>
            <tr><td><a href="/view?code=electric&No=301">블루링크 서비스 점검 중 오류 해결 후기</a></td></tr>
          </table>
        </body></html>
        """
        bd_post_html = """
        <html><body>
          <strong class="title">블루링크 서비스 점검 중 오류 해결 후기</strong>
          <div class="bodyCont">블루링크 앱 연결이 안 될 때 캐시를 초기화하고 재로그인하니 정상적으로 차량 제어 및 충전 상태 조회가 되었습니다.</div>
        </body></html>
        """
        bd_client.warm_up_session.return_value = True
        bd_client.get.side_effect = [
            (200, bd_list_html, bd_list_html.encode("utf-8")),
            (200, bd_post_html, bd_post_html.encode("utf-8")),
        ]
        bd = BobaeDreamCrawler(client=bd_client)
        bd_posts = bd.crawl_board("electric", pages=1, limit=5)
        self.assertEqual(len(bd_posts), 1)
        self.assertEqual(bd_posts[0]["post_id"], "301")

        dc_client = MagicMock(spec=SafeHttpClient)
        dc_list_html = """
        <html><body>
          <table>
            <tr class="ub-content us-post" data-no="401">
              <td class="gall_tit"><a href="/board/view/?id=car_new1&no=401">서비스 점검 중 앱 먹통 문의</a></td>
              <td class="gall_date" title="2026-11-27 03:00:00">03:00</td>
            </tr>
          </table>
        </body></html>
        """
        dc_post_html = """
        <html><body>
          <span class="title_subject">서비스 점검 중 앱 먹통 문의</span>
          <div class="write_div">오전에 원격 공조 실행하려는데 접속이 지연되다가 다시 시도하니 정상 작동하고 있습니다. 다른 분들도 참고하세요.</div>
        </body></html>
        """
        dc_client.warm_up_session.return_value = True
        dc_client.get.side_effect = [
            (200, dc_list_html, dc_list_html.encode("utf-8")),
            (200, dc_post_html, dc_post_html.encode("utf-8")),
        ]
        dc = DCInsideCrawler(client=dc_client)
        dc_posts = dc.crawl_gallery("car_new1", pages=1, limit=5)
        self.assertEqual(len(dc_posts), 1)
        self.assertEqual(dc_posts[0]["post_id"], "401")

    def test_bobaedream_title_matching_tag_name(self):
        bd = BobaeDreamCrawler(client=MagicMock(spec=SafeHttpClient))
        html_doc = """
        <html><body>
          <h2 class="title">h2</h2>
          <div class="bodyCont">수소차 h2 모델 시승기 본문입니다.</div>
        </body></html>
        """
        detail = bd.parse_post_detail(html_doc, "https://www.bobaedream.co.kr/view?code=national&No=99")
        self.assertEqual(detail["title"], "h2")


if __name__ == "__main__":
    unittest.main()
