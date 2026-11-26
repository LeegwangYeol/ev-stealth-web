"""Targeted regression tests for scrapers/ audit fixes (2026-11-27)."""

from __future__ import annotations

import json
import os
import sys
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scrapers.blind_scraper import BlindScraper
from scrapers.bobaedream_scraper import BobaedreamScraper
from scrapers.cafe_forum_miner import CafeForumMiner
from scrapers.common_utils import (
    SafeHttpClient,
    clean_html_text,
    encode_euc_kr_query,
    extract_balanced_tag_content,
    extract_meta_content,
    is_allowed_domain_url,
    strip_non_body_html,
)
from scrapers.dcinside_scraper import DCInsideScraper


class TestCommonUtilsAuditFixes(unittest.TestCase):
    """Verify domain allowlist, single-pass HTML stripping, quote-aware tags, and EUC-KR encoding."""

    def test_is_allowed_domain_url_rejects_userinfo_backslash_control_and_bad_port(self) -> None:
        self.assertTrue(is_allowed_domain_url("https://www.teamblind.com/kr/post/1", ("teamblind.com",)))
        self.assertFalse(is_allowed_domain_url("https://evil.com\\@www.teamblind.com/kr/post/1", ("teamblind.com",)))
        self.assertFalse(is_allowed_domain_url("https://user:pass@www.teamblind.com/kr/post/1", ("teamblind.com",)))
        self.assertFalse(is_allowed_domain_url("https://www.teamblind.com\n/kr/post/1", ("teamblind.com",)))
        self.assertFalse(is_allowed_domain_url("https://www.teamblind.com:99999/kr/post/1", ("teamblind.com",)))
        self.assertFalse(is_allowed_domain_url("https://evil.com/", ("",)))

    def test_single_pass_comment_and_script_stripping_prevents_cross_deletion(self) -> None:
        html_doc = (
            "<html><head>"
            "<script>var s = '<!-- </head>';</script>"
            '<meta charset="euc-kr">'
            '<meta property="og:title" content="실제 메타 제목">'
            "</head><body>"
            "<p>실제 본문 내용</p>"
            "<!-- trailing comment -->"
            "</body></html>"
        )
        self.assertEqual(SafeHttpClient._detect_encoding("text/html", html_doc.encode("ascii", "ignore")), "euc-kr")
        self.assertEqual(extract_meta_content(html_doc, "og:title"), "실제 메타 제목")
        stripped = strip_non_body_html(html_doc)
        self.assertIn("실제 본문 내용", stripped)
        self.assertNotIn("og:title", stripped)
        self.assertEqual(clean_html_text(html_doc), "실제 본문 내용")

    def test_clean_html_text_handles_gt_in_quoted_attributes_and_preserves_math(self) -> None:
        raw = '<div title="a > b"><img src="x.png" alt="1 > 2">실제 본문 < 3000 그리고 > 200</div>'
        self.assertEqual(clean_html_text(raw), "실제 본문 < 3000 그리고 > 200")

    def test_extract_balanced_tag_content_self_closing_returns_empty(self) -> None:
        html_doc = '<div class="bodyCont" /><div class="other">바깥</div>'
        self.assertEqual(
            extract_balanced_tag_content(
                html_doc,
                r'<div\b[^>]*\bclass=["\'][^"\']*\bbodyCont\b[^"\']*["\'][^>]*>',
                tag_name="div",
            ),
            "",
        )

    def test_encode_euc_kr_query_encodes_slashes_in_keys_and_values(self) -> None:
        encoded = encode_euc_kr_query({"keyword": "A/S 후기", "a/b": "1/2"})
        self.assertIn(b"keyword=A%2FS", encoded)
        self.assertIn(b"a%2Fb=1%2F2", encoded)


class TestScrapersDedupAndCommentIsolation(unittest.TestCase):
    """Verify comment/script isolation and canonical post-ID deduplication across scrapers."""

    def test_blind_next_data_comment_skip_feed_dedup_and_dom_isolation(self) -> None:
        scraper = BlindScraper(client=SafeHttpClient(min_delay=0.0, max_delay=0.0))

        fake_next = {"props": {"pageProps": {"articles": [{"id": "1", "title": "가짜", "slug": "fake"}]}}}
        real_next = {
            "props": {
                "pageProps": {
                    "articles": [
                        {"id": "10", "title": "아토3 후기 <!-- 내부주석 -->", "slug": "atto3-10"},
                        {"id": "10", "title": "아토3 후기 중복", "slug": "atto3-10"},
                    ]
                }
            }
        }
        feed_html = (
            f'<!-- <script id="__NEXT_DATA__">{json.dumps(fake_next)}</script> -->'
            f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(real_next)}</script>'
        )
        items = scraper.parse_topic_feed(feed_html, topic_name="자동차")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["post_id"], "10")
        self.assertEqual(items[0]["title"], "아토3 후기")
        self.assertEqual(items[0]["url"], "https://www.teamblind.com/kr/post/atto3-10")

        # DOM fallback ignores commented/script links
        dom_feed = (
            '<!-- <a href="/kr/post/fake-99">가짜 링크</a> -->'
            '<script>var x = \'<a href="/kr/post/real-77">가짜 스크립트</a>\';</script>'
            '<a href="/kr/post/real-77">진짜 블라인드 게시글</a>'
        )
        dom_items = scraper.parse_topic_feed(dom_feed)
        self.assertEqual(len(dom_items), 1)
        self.assertEqual(dom_items[0]["title"], "진짜 블라인드 게시글")

        # Nested author-info div and commented comment-item isolation
        detail_html = """
        <html><body>
          <h1 class="article-title">테스트 제목</h1>
          <div class="author-info"><div class="avatar">img</div><span>현대자동차</span></div>
          <div class="article-content">테스트 본문 내용입니다.</div>
          <!-- <div class="comment-item">주석 속 가짜 댓글입니다.</div><!-- //comment-item -->
          <div class="comment-item"><div class="inner">진짜 댓글 내용입니다.</div></div>
        </body></html>
        """
        detail = scraper.parse_post_detail(detail_html, "https://www.teamblind.com/kr/post/real-77")
        self.assertEqual(detail["company"], "현대자동차")
        self.assertEqual(detail["comments"], ["진짜 댓글 내용입니다."])

        # Long badge + short comment text (<5 chars) must be skipped rather than producing invalid record
        recs = scraper.extract_complaint_records({
            "url": "https://www.teamblind.com/kr/post/real-77",
            "title": "아토3 충전",
            "body": "짧음",
            "comments": ["[매우긴회사이름입니다] 충전"],
        })
        self.assertEqual(recs, [])
        scraper.close(force=True)

    def test_bobaedream_list_comment_isolation_cross_page_dedup_and_date_before_count_group(self) -> None:
        mock_client = MagicMock()
        page1 = '<dl><dt><a href="/view?code=electric&No=50&bm=1">보배드림 전기차 충전 후기</a></dt></dl>'
        page2 = '<dl><dt><a href="/view?code=electric&No=50&bm=2">보배드림 전기차 충전 후기</a></dt></dl>'
        mock_client.request.side_effect = [(200, page1, b""), (200, page2, b"")]
        scraper = BobaedreamScraper(client=mock_client)

        search_items = scraper.search("BYD", max_pages=2)
        self.assertEqual(len(search_items), 1)
        self.assertEqual(search_items[0]["post_no"], "50")

        board_html = (
            '<!-- <a href="/view?code=electric&No=77">주석 가짜 글</a> -->'
            '<a href="/view?code=electric&No=77">실제 보배드림 글</a>'
        )
        board_items = scraper.parse_board_list(board_html, "electric")
        self.assertEqual(len(board_items), 1)
        self.assertEqual(board_items[0]["title"], "실제 보배드림 글")

        # <span class="date"> before <span class="countGroup"> must not fall back to title counts
        detail_html = """
        <html><body>
          <strong class="title">조회 9999 추천 8888 실제 제목</strong>
          <span class="date">2026.11.27 04:10</span>
          <span class="countGroup">조회 <em>45</em> | 추천 <span>3</span></span>
          <div class="bodyCont"></div>
          <!-- <div class="bodyCont">주석 가짜 본문</div><!-- //bodyCont -->
        </body></html>
        """
        detail = scraper.parse_post_detail(detail_html, "https://www.bobaedream.co.kr/view?code=electric&No=77")
        self.assertEqual(detail["published_at"], "2026-11-27 04:10")
        self.assertEqual(detail["view_count"], 45)
        self.assertEqual(detail["upvote_count"], 3)
        self.assertEqual(detail["body"], "")
        scraper.close(force=True)

    def test_dcinside_list_and_body_ignore_commented_blocks(self) -> None:
        scraper = DCInsideScraper(client=SafeHttpClient(min_delay=0.0, max_delay=0.0))
        list_html = """
        <table>
          <!-- <tr data-no="201" class="ub-content"><td class="gall_tit"><a href="/mgallery/board/view/?id=ev&no=201">주석 가짜 글</a></td></tr> -->
          <tr data-no="201" class="ub-content"><td class="gall_tit"><a href="/mgallery/board/view/?id=ev&no=201">실제 디시 글</a></td></tr>
        </table>
        """
        items = scraper.parse_gallery_list(list_html, "ev")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "실제 디시 글")

        detail_html = """
        <html><body>
          <span class="title_subject">빈 본문 글</span>
          <div class="writing_view_box"></div>
          <!-- <div class="writing_view_box">주석 속 가짜 본문</div><!-- //writing_view_box -->
        </body></html>
        """
        detail = scraper.parse_post_detail(detail_html, "https://gall.dcinside.com/mgallery/board/view/?id=ev&no=201", "ev", "201")
        self.assertEqual(detail["body"], "")
        scraper.close(force=True)

    def test_cafe_forum_miner_ignores_comments_and_dedups_by_canonical_id(self) -> None:
        mock_client = MagicMock()
        pomppu_p1 = (
            '<!-- <a href="/zboard/view.php?id=car&no=300">주석 가짜 뽐뿌</a> -->'
            '<a href="/zboard/view.php?id=car&no=300&page=1">뽐뿌 전기차 충전 후기</a>'
            '<a href="/zboard/view.php?id=car&no=300&divpage=2">뽐뿌 전기차 충전 후기</a>'
        )
        pomppu_p2 = '<a href="/zboard/view.php?id=car&no=300&page=2">뽐뿌 전기차 충전 후기</a>'
        clien_p1 = (
            '<!-- <a class="list_subject" href="/service/board/cm_car/400">주석 가짜 클리앙</a> -->'
            '<a class="list_subject" href="/service/board/cm_car/400?od=T31&po=0">클리앙 아이오닉5 후기</a>'
            '<a class="list_subject" href="/service/board/cm_car/400?od=T31&po=0#comment">클리앙 아이오닉5 후기</a>'
        )
        clien_p2 = '<a class="list_subject" href="/service/board/cm_car/400?od=T31&po=1">클리앙 아이오닉5 후기</a>'
        mock_client.request.side_effect = [
            (200, pomppu_p1, b""),
            (200, pomppu_p2, b""),
            (200, clien_p1, b""),
            (200, clien_p2, b""),
        ]

        miner = CafeForumMiner(client=mock_client)
        p_items = miner.mine_pomppu("아토3", max_pages=2)
        self.assertEqual(len(p_items), 1)
        self.assertEqual(p_items[0]["post_no"], "300")

        c_items = miner.mine_clien("아이오닉5", max_pages=2)
        self.assertEqual(len(c_items), 1)
        self.assertEqual(c_items[0]["post_id"], "400")
        miner.close(force=True)


if __name__ == "__main__":
    unittest.main()
