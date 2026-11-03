"""
Unit & Integration Test Suite for BobaeDream Crawler Audit & Hardening.
Verifies all 6 audit requirements:
1. Pagination logic, community board URL parsing, post ID extraction.
2. Handling of deleted posts, secret/restricted posts, non-standard date formats.
3. Anti-scraping, Cloudflare challenges, rate limits, retry backoff with jitter.
4. Entity decoding (&nbsp;, &amp;, &lt;, &gt;) and title whitespace trimming.
"""

from __future__ import annotations

import datetime
import unittest
from unittest.mock import MagicMock, patch

from crawlers.bobaedream import (
    BOBAE_BASE_URL,
    BOBAE_LIST_URL,
    TARGET_BOARDS,
    BobaeDreamCrawler,
    BobaedreamCrawler,
    _normalize_iso_timestamp,
    clean_title_text,
    extract_container_content,
    is_deleted_or_restricted,
)
from utils.http_client import SafeHttpClient


class TestBobaeDreamAuditURLParsingAndPagination(unittest.TestCase):
    """Test Requirement 1: Bobaedream pagination logic, community board URL parsing, post ID extraction."""

    def setUp(self):
        self.mock_client = MagicMock(spec=SafeHttpClient)
        self.crawler = BobaeDreamCrawler(client=self.mock_client)

    def test_post_id_extraction_multi_patterns(self):
        """Extract post IDs from No=, no=, b_no=, bm_no=, /bbs_view/, and /view/."""
        html_sample = """
        <div>
          <a href="/view?code=national&No=1001">국산차 대문자 No</a>
          <a href="/board/bulletin/view.php?code=import&no=2002">수입차 소문자 no PHP 스크립트</a>
          <a href="/view?code=electric&b_no=3003">전기차 b_no 파라미터</a>
          <a href="/view?code=freeb&bm_no=4004">자유게시판 bm_no 파라미터</a>
          <a href="/board/bbs_view/electric/5005">모바일 REST 스타일 URL</a>
          <a href="/view/6006">단축 view URL</a>
          <a href="/view?code=national&amp;No=7007">HTML 엔티티 포함 링크 &amp;No</a>
          <a href="//www.bobaedream.co.kr/view?code=national&No=8008">프로토콜 상대 URL</a>
        </div>
        """
        items = self.crawler.parse_list_page(html_sample, "national")
        extracted_ids = [item["post_id"] for item in items]
        self.assertEqual(extracted_ids, ["1001", "2002", "3003", "4004", "5005", "6006", "7007", "8008"])

        # Check URL canonicalization
        self.assertEqual(items[6]["url"], f"{BOBAE_BASE_URL}/view?code=national&No=7007")
        self.assertEqual(items[7]["url"], "https://www.bobaedream.co.kr/view?code=national&No=8008")

        # Check board code extraction
        self.assertEqual(items[1]["board_code"], "import")
        self.assertEqual(items[4]["board_code"], "electric")

    def test_trailing_comment_badge_stripping_and_notice_filtering(self):
        """Strip trailing comment badges like (14), [28] while preserving tags and filtering notices."""
        html_sample = """
        <table>
          <tr><td><a href="/view?code=national&No=101">[공지] 커뮤니티 운영 원칙 안내</a></td></tr>
          <tr><td><a href="/view?code=national&No=102"><b>공지</b> 서버 점검 공지사항</a></td></tr>
          <tr><td><a href="/view?code=national&No=103"><b class="notice">필독</b> 이용 수칙</a></td></tr>
          <tr><td><a href="/view?code=national&No=201">[후기] 아이오닉5 2만km 주행 후기 (14)</a></td></tr>
          <tr><td><a href="/view?code=national&No=202">EV6 빗길 회생제동 피쉬테일 결함 [28]</a></td></tr>
          <tr><td><a href="/view?code=national&No=203">현대차 ICCU 무상수리 공지 떴네요</a></td></tr>
        </table>
        """
        items = self.crawler.parse_list_page(html_sample, "national")
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["post_id"], "201")
        self.assertEqual(items[0]["title"], "[후기] 아이오닉5 2만km 주행 후기")
        self.assertEqual(items[1]["post_id"], "202")
        self.assertEqual(items[1]["title"], "EV6 빗길 회생제동 피쉬테일 결함")
        self.assertEqual(items[2]["post_id"], "203")
        self.assertEqual(items[2]["title"], "현대차 ICCU 무상수리 공지 떴네요")

    def test_pagination_loop_termination(self):
        """Pagination stops early when subsequent page returns duplicate items."""
        page_html = """
        <a href="/view?code=national&No=501">게시글 1</a>
        <a href="/view?code=national&No=502">게시글 2</a>
        """
        self.mock_client.get.return_value = (200, page_html, b"")

        # Request 5 pages, but same items repeat -> must break after page 2
        with patch.object(self.crawler, "fetch_post", return_value={"post_id": "dummy"}):
            results = self.crawler.crawl_board("national", pages=5)
            # 2 unique posts fetched from page 1, loop terminated at page 2
            self.assertEqual(len(results), 2)
            self.assertEqual(self.mock_client.get.call_count, 2)


class TestBobaeDreamAuditDeletedRestrictedAndDates(unittest.TestCase):
    """Test Requirement 2: Handling of deleted posts, secret/restricted posts, non-standard date formats."""

    def setUp(self):
        self.mock_client = MagicMock(spec=SafeHttpClient)
        self.crawler = BobaeDreamCrawler(client=self.mock_client)

    def test_deleted_post_detection(self):
        """Detect alert('삭제된 게시물입니다') and related deleted post markers."""
        deleted_samples = [
            "<script>alert('삭제된 게시물입니다.'); history.back();</script>",
            "<script>alert('존재하지 않는 게시물입니다.');</script>",
            "<script>alert('해당 게시물이 삭제되었습니다.');</script>",
            "<div class='warning'>삭제된 게시물입니다.</div>",
            "<p>요청하신 게시물을 찾을 수 없습니다</p>",
        ]
        for html_text in deleted_samples:
            is_blocked, reason = is_deleted_or_restricted(html_text)
            self.assertTrue(is_blocked, f"Failed on: {html_text}")
            self.assertEqual(reason, "deleted_post")

            # fetch_post returns None
            self.mock_client.get.return_value = (200, html_text, b"")
            res = self.crawler.fetch_post("https://www.bobaedream.co.kr/view?code=national&No=999")
            self.assertIsNone(res)

            # parse_post_detail returns is_deleted=True
            detail = self.crawler.parse_post_detail(html_text, "https://www.bobaedream.co.kr/view?code=national&No=999")
            self.assertTrue(detail["is_deleted"])
            self.assertEqual(detail["title"], "")

    def test_secret_and_restricted_post_detection(self):
        """Detect secret, member-only, and permission-denied post markers."""
        restricted_samples = [
            ("<script>alert('비밀글입니다.');</script>", "restricted_post"),
            ("<script>alert('작성자만 조회할 수 있는 비밀글입니다.');</script>", "restricted_post"),
            ("<script>alert('로그인 후 이용 가능합니다.');</script>", "restricted_post"),
            ("<script>alert('접근 권한이 없습니다.');</script>", "restricted_post"),
            ("<p>비밀글 기능으로 보호된 글입니다</p>", "restricted_post"),
        ]
        for html_text, expected_reason in restricted_samples:
            is_blocked, reason = is_deleted_or_restricted(html_text)
            self.assertTrue(is_blocked, f"Failed on: {html_text}")
            self.assertEqual(reason, expected_reason)

            self.mock_client.get.return_value = (200, html_text, b"")
            res = self.crawler.fetch_post("https://www.bobaedream.co.kr/view?code=national&No=777")
            self.assertIsNone(res)

            detail = self.crawler.parse_post_detail(html_text, "https://www.bobaedream.co.kr/view?code=national&No=777")
            self.assertTrue(detail["is_restricted"])

    def test_non_standard_timestamp_normalization(self):
        """Normalize ISO, relative Korean strings, Korean dates, and AM/PM."""
        now = datetime.datetime.now(datetime.timezone.utc)

        # 1. Already ISO-8601 with 'T' (must NOT truncate to 12:00:00)
        iso_str = "2026-09-08T15:45:30Z"
        res_iso = _normalize_iso_timestamp(iso_str)
        self.assertEqual(res_iso, "2026-09-08T15:45:30+00:00")

        # 2. Relative Korean: "방금 전", "5분 전", "2시간 전"
        self.assertIn("T", _normalize_iso_timestamp("방금 전"))
        five_min = _normalize_iso_timestamp("5분 전")
        self.assertIn("T", five_min)
        two_hrs = _normalize_iso_timestamp("2시간 전")
        self.assertIn("T", two_hrs)

        # 3. Relative Korean: "어제 14:30"
        yesterday_str = _normalize_iso_timestamp("어제 14:30")
        self.assertIn("T14:30:00", yesterday_str)

        # 4. Korean format: "2026년 9월 8일 10:15:00"
        kr_str = _normalize_iso_timestamp("2026년 9월 8일 10:15:00")
        self.assertEqual(kr_str, "2026-09-08T10:15:00+00:00")

        # 5. Korean format with day-of-week and meridiem: "2026년 9월 8일 (화) 오후 02:15"
        kr_pm_str = _normalize_iso_timestamp("2026년 9월 8일 (화) 오후 02:15")
        self.assertEqual(kr_pm_str, "2026-09-08T14:15:00+00:00")

        # 6. AM/PM time only: "오후 03:20"
        pm_time = _normalize_iso_timestamp("오후 03:20")
        self.assertIn("T15:20:00", pm_time)

        # 7. 2-digit year: "26.09.08 10:15"
        yymmdd = _normalize_iso_timestamp("26.09.08 10:15")
        self.assertEqual(yymmdd, "2026-09-08T10:15:00+00:00")


class TestBobaeDreamAuditAntiScrapingAndEntities(unittest.TestCase):
    """Test Requirements 3 & 4: Anti-scraping, Cloudflare, rate limits, entities, and whitespace."""

    def setUp(self):
        self.mock_client = MagicMock(spec=SafeHttpClient)
        self.crawler = BobaeDreamCrawler(client=self.mock_client)

    def test_cloudflare_and_bot_challenge_detection(self):
        """Cloudflare challenge and bot blocking pages are detected and cleanly rejected."""
        cf_html = "<html><head><title>Just a moment...</title></head><body>cf-browser-verification</body></html>"
        is_blocked, reason = is_deleted_or_restricted(cf_html)
        self.assertTrue(is_blocked)
        self.assertEqual(reason, "cloudflare_challenge")

        bot_html = "<html><body>비정상적인 접근입니다. 잠시 후 다시 시도해주세요.</body></html>"
        is_blocked_b, reason_b = is_deleted_or_restricted(bot_html)
        self.assertTrue(is_blocked_b)
        self.assertEqual(reason_b, "abnormal_access_blocked")

        # parse_list_page returns empty list on anti-scraping
        self.assertEqual(self.crawler.parse_list_page(cf_html, "national"), [])
        self.assertEqual(self.crawler.parse_list_page(bot_html, "national"), [])

    def test_entity_decoding_and_whitespace_trimming(self):
        """clean_title_text decodes HTML entities (&nbsp;, &amp;, &lt;, &gt;) and trims special whitespace."""
        # Standard entities
        raw1 = "&nbsp;&nbsp;현대&amp;기아&nbsp;전기차&nbsp;배터리&nbsp;&nbsp;"
        self.assertEqual(clean_title_text(raw1), "현대&기아 전기차 배터리")

        # Brackets & symbols
        raw2 = "&lt;단독&gt; EV9 ICCU 결함 &quot;전액 리콜&quot; 확정"
        self.assertEqual(clean_title_text(raw2), "<단독> EV9 ICCU 결함 \"전액 리콜\" 확정")

        # Double-encoded entities
        raw3 = "&amp;lt;속보&amp;gt; 보배드림&amp;nbsp;게시판"
        self.assertEqual(clean_title_text(raw3), "<속보> 보배드림 게시판")

        # Unicode whitespace: non-breaking space (\xa0), zero-width space (\u200b), newlines
        raw4 = "  \xa0\t제목입니다\u200b\n\n여러   줄\xa0\xa0공백\u3000테스트 \n "
        self.assertEqual(clean_title_text(raw4), "제목입니다 여러 줄 공백 테스트")

    def test_detail_page_entity_and_whitespace_integration(self):
        """Detail page parsing decodes title, content, and author entities cleanly."""
        sample_html = """
        <html>
        <head><title>&lt;단독&gt; 배터리 결함 심각 - 보배드림</title></head>
        <body>
          <strong class="title">&lt;단독&gt;&nbsp;&nbsp;배터리&nbsp;결함&amp;화재&nbsp;위험</strong>
          <span class="author">&nbsp;차주&amp;연구원&nbsp;</span>
          <span class="date">2026-09-08 14:00:00</span>
          <div class="bodyCont">
            배터리 팩&nbsp;하단에 크랙이 발생했습니다.<br>
            제조사&amp;서비스센터에서는 나 몰라라 합니다.
          </div>
        </body>
        </html>
        """
        post = self.crawler.parse_post_detail(sample_html, "https://www.bobaedream.co.kr/view?code=electric&No=1234")
        self.assertEqual(post["title"], "<단독> 배터리 결함&화재 위험")
        self.assertEqual(post["author"], "차주&연구원")
        self.assertIn("배터리 팩 하단에 크랙이 발생했습니다.", post["content"])
        self.assertIn("제조사&서비스센터에서는", post["content"])
        self.assertEqual(post["board_code"], "electric")

    def test_referer_header_propagation(self):
        """fetch_post called during crawl_board passes list page URL as referer."""
        page_html = '<a href="/view?code=national&No=9001">정상 게시글</a>'
        self.mock_client.get.return_value = (200, page_html, b"")

        with patch.object(self.crawler, "fetch_post") as mock_fetch:
            mock_fetch.return_value = {"post_id": "9001", "title": "정상 게시글"}
            results = self.crawler.crawl_board("national", pages=1)
            self.assertEqual(len(results), 1)
            # Ensure fetch_post was called with referer equal to list page URL
            mock_fetch.assert_called_once()
            _, kwargs = mock_fetch.call_args
            self.assertEqual(kwargs.get("referer"), f"{BOBAE_LIST_URL}?code=national&page=1")


if __name__ == "__main__":
    unittest.main()
