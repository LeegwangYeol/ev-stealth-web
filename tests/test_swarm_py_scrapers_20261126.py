"""Targeted regression tests for scrapers/ audit fixes (2026-11-26)."""

from __future__ import annotations

import os
import socket
import sys
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scrapers.blind_scraper import BlindScraper
from scrapers.bobaedream_scraper import BobaedreamScraper
from scrapers.cafe_forum_miner import CafeForumMiner
from scrapers.common_utils import (
    CircuitBreakerState,
    SafeHttpClient,
    _create_safe_connection,
    robust_decode,
)
from scrapers.dcinside_scraper import DCInsideScraper


class TestCharsetAndHttpClientHardening(unittest.TestCase):
    """Verify encoding detection/decoding, stale cache flag reset, and socket cleanup."""

    def test_detect_encoding_ignores_html_comments_before_meta_charset(self) -> None:
        raw = b'<!-- <meta charset="utf-8"> --><meta charset="euc-kr"><p>\xc0\xfc\xb1\xe2\xc2\xf7</p>'
        self.assertEqual(SafeHttpClient._detect_encoding("text/html", raw), "euc-kr")

    def test_robust_decode_truncated_utf8_does_not_mojibake_to_cp949(self) -> None:
        truncated = "가".encode("utf-8")[:-1]  # b"\xea\xb0" which is also valid CP949 '媛'
        decoded = robust_decode(truncated, declared_encoding="utf-8")
        self.assertEqual(decoded, "\ufffd")
        self.assertNotEqual(decoded, "媛")

        # Valid CP949 even with wrong utf-8 declaration must still fall back to cp949
        cp949_bytes = "전기차 급속 충전".encode("cp949")
        self.assertEqual(robust_decode(cp949_bytes, declared_encoding="utf-8"), "전기차 급속 충전")

    def test_last_response_from_cache_reset_on_open_circuit_and_ssrf_block(self) -> None:
        client = SafeHttpClient(
            min_delay=0.0,
            max_delay=0.0,
            failure_threshold=1,
            circuit_cooldown=60.0,
            enable_cache=True,
            cache_fallback=True,
        )
        cached_url = "https://www.bobaedream.co.kr/view?code=electric&No=1"
        client.set_cached_response(cached_url, 200, "cached body", b"cached body")
        client.circuit_breaker.record_failure(cached_url, status_code=503)

        # First call returns cached response while circuit is open
        status1, text1, _ = client.request(cached_url)
        self.assertEqual(status1, 200)
        self.assertEqual(text1, "cached body")
        self.assertTrue(client.last_response_from_cache)

        # Second call to an uncached URL on the same open host must reset flag to False
        uncached_url = "https://www.bobaedream.co.kr/view?code=electric&No=2"
        status2, text2, _ = client.request(uncached_url)
        self.assertEqual(status2, 503)
        self.assertEqual(text2, "")
        self.assertFalse(client.last_response_from_cache)

        # Third call hits cache again, then SSRF-blocked call must reset flag to False
        client.request(cached_url)
        self.assertTrue(client.last_response_from_cache)
        status3, _, _ = client.request("http://127.0.0.1/admin")
        self.assertEqual(status3, 0)
        self.assertFalse(client.last_response_from_cache)
        client.close()

    def test_create_safe_connection_closes_socket_on_non_oserror(self) -> None:
        mock_sock = MagicMock()
        mock_sock.settimeout.side_effect = ValueError("bad timeout")
        addr_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 443))]
        with patch("scrapers.common_utils.socket.getaddrinfo", return_value=addr_info), patch(
            "scrapers.common_utils.socket.socket", return_value=mock_sock
        ):
            with self.assertRaises(ValueError):
                _create_safe_connection(("example.com", 443), timeout=1.0, allow_private_ips=False)
        mock_sock.close.assert_called_once()


class TestScrapersAllowlistAndDomRobustness(unittest.TestCase):
    """Verify domain allowlists, deduplication order, and comment/nested DOM isolation."""

    def test_blind_fetch_detail_rejects_off_domain_and_feed_dedup_survives_empty_link(self) -> None:
        mock_client = MagicMock()
        scraper = BlindScraper(client=mock_client)
        self.assertEqual(scraper.fetch_post_detail("https://evil.com/kr/post/123"), {})
        self.assertEqual(scraper.fetch_post_detail("http://127.0.0.1/kr/post/123"), {})
        mock_client.request.assert_not_called()

        # Thumbnail/empty anchor before real title anchor must not poison seen_urls
        feed_html = """
        <div class="article-list-pre">
          <a href="/kr/post/atto3-123"><img src="thumb.png" /></a>
          <a href="/kr/post/atto3-123">BYD 아토3 충전 튕김 후기</a>
        </div>
        """
        items = scraper.parse_topic_feed(feed_html, topic_name="자동차")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "BYD 아토3 충전 튕김 후기")
        self.assertEqual(items[0]["url"], "https://www.teamblind.com/kr/post/atto3-123")

        # Commented-out title/company/comment must be ignored
        detail_html = """
        <html><body>
          <!-- <h1 class="article-title">가짜 제목</h1><span class="company">가짜회사</span> -->
          <h1 class="article-title">진짜 제목</h1>
          <span class="company">현대자동차</span>
          <div class="article-content">진짜 본문 내용입니다.</div>
          <!-- <p class="comment-text">가짜 댓글 내용입니다.</p> -->
          <p class="comment-text">진짜 댓글 내용입니다.</p>
        </body></html>
        """
        detail = scraper.parse_post_detail(detail_html, "https://www.teamblind.com/kr/post/atto3-123")
        self.assertEqual(detail["title"], "진짜 제목")
        self.assertEqual(detail["company"], "현대자동차")
        self.assertEqual(detail["comments"], ["진짜 댓글 내용입니다."])
        scraper.close(force=True)

    def test_bobaedream_fetch_detail_allowlist_list_dedup_and_nested_count_group(self) -> None:
        mock_client = MagicMock()
        scraper = BobaedreamScraper(client=mock_client)
        self.assertEqual(scraper.fetch_post_detail("https://evil.com/view?code=electric&No=1"), {})
        mock_client.request.assert_not_called()

        # Thumbnail link and off-domain link must not poison seen_nos for real post No=42
        list_html = """
        <a href="https://evil.com/view?code=electric&No=42">피싱 링크</a>
        <a href="/view?code=electric&No=42"><img src="icon.png" /></a>
        <a href="/view?code=electric&No=42">정상 보배드림 전기차 후기</a>
        """
        items = scraper.parse_board_list(list_html, "electric")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["post_no"], "42")
        self.assertEqual(items[0]["title"], "정상 보배드림 전기차 후기")

        # Nested <span> inside countGroup must not truncate before view/upvote counts
        detail_html = """
        <html><body>
          <!-- <strong class="title">주석 제목</strong> -->
          <strong class="title">조회 9999 추천 8888 실제 제목</strong>
          <span class="countGroup">
            <span class="date">2026.11.26 04:05</span> | 조회 <em>123</em> | 추천 <span>9</span>
          </span>
          <div class="bodyCont">보배드림 실제 본문입니다.</div>
          <!-- <dd class="comment">주석 속 가짜 댓글입니다.</dd> -->
          <dd class="comment">실제 작성된 댓글 내용입니다.</dd>
        </body></html>
        """
        detail = scraper.parse_post_detail(detail_html, "https://www.bobaedream.co.kr/view?code=electric&No=42")
        self.assertEqual(detail["title"], "조회 9999 추천 8888 실제 제목")
        self.assertEqual(detail["published_at"], "2026-11-26 04:05")
        self.assertEqual(detail["view_count"], 123)
        self.assertEqual(detail["upvote_count"], 9)
        self.assertEqual(detail["comments"], ["실제 작성된 댓글 내용입니다."])
        scraper.close(force=True)

    def test_dcinside_ignores_commented_and_script_metadata_and_encodes_slash_in_keyword(self) -> None:
        mock_client = MagicMock()
        mock_client.request.return_value = (200, "", b"")
        scraper = DCInsideScraper(client=mock_client)
        scraper.search_gallery("electriccar", "A/S", max_pages=1)
        called_url = mock_client.request.call_args[0][0]
        self.assertIn("s_keyword=A%2FS", called_url)

        detail_html = """
        <html><body>
          <!-- <span class="title_subject">주석 제목</span>
               <td class="gall_writer"><span class="nickname">가짜닉</span><span class="ip">(9.9)</span></td>
               <input type="hidden" id="e_s_n_o" value="fake_token" />
               <p class="usertxt">주석 속 가짜 댓글입니다.</p> -->
          <script>var tpl = '<span class="gall_count">조회 99999</span>';</script>
          <span class="title_subject">진짜 디시 제목</span>
          <td class="gall_writer"><span class="nickname">진짜닉</span></td>
          <span class="gall_count">조회 <em>55</em></span>
          <input type="hidden" id="e_s_n_o" value="real_token" />
          <div class="writing_view_box">디시 본문 내용입니다.</div>
          <p class="usertxt">진짜 디시 댓글입니다.</p>
        </body></html>
        """
        detail = scraper.parse_post_detail(
            detail_html,
            "https://gall.dcinside.com/mgallery/board/view/?id=electriccar&no=1",
            "electriccar",
            "1",
        )
        self.assertEqual(detail["title"], "진짜 디시 제목")
        self.assertEqual(detail["author_badge"], "진짜닉")
        self.assertEqual(detail["author_type"], "dc_fixed_nick")
        self.assertEqual(detail["view_count"], 55)
        self.assertEqual(detail["e_s_n_o"], "real_token")
        self.assertEqual(detail["comments"], ["진짜 디시 댓글입니다."])
        scraper.close(force=True)

    def test_cafe_forum_miner_rejects_malformed_schemed_and_userinfo_urls(self) -> None:
        miner = CafeForumMiner(client=SafeHttpClient(min_delay=0.0, max_delay=0.0))
        for bad_url in (
            "https:evil.com/post/1",
            "http://",
            "https://user:pass@cafe.naver.com/ev/1",
            "///evil.com/path",
        ):
            rec = miner.normalize_record({
                "platform": "naver_cafe",
                "post_url": bad_url,
                "raw_quote": "충전 중 튕김 현상이 반복적으로 발생하고 있습니다.",
                "category": "charging",
            })
            self.assertIsNone(rec, f"Expected None for malformed post_url={bad_url!r}")
        miner.close(force=True)


if __name__ == "__main__":
    unittest.main()
