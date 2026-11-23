"""Targeted audit & regression tests for scrapers/ hardening (2026-11-24)."""

from __future__ import annotations

import io
import os
import socket
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scrapers.blind_scraper import BlindScraper
from scrapers.bobaedream_scraper import BobaedreamScraper
from scrapers.cafe_forum_miner import CafeForumMiner
from scrapers.common_utils import (
    CircuitBreaker,
    CircuitBreakerState,
    ResilientHTTPSConnection,
    SafeHttpClient,
    _create_safe_connection,
    bounded_cache_set,
    clean_html_text,
    extract_balanced_tag_content,
    extract_meta_content,
    is_safe_url,
    robust_decode,
)
from scrapers.dcinside_scraper import DCInsideScraper


class TestScrapersSSRFAndTunnelHardening(unittest.TestCase):
    """Verify SSRF, tunnel port policy, and scoped IPv6 hardening."""

    def test_resilient_https_tunnel_enforces_allowed_ports_and_zero_port(self) -> None:
        conn_zero = ResilientHTTPSConnection("93.184.215.14", 443, allow_private_ips=False)
        conn_zero.set_tunnel("93.184.215.14", 0)
        with patch("scrapers.common_utils._create_safe_connection") as mock_conn:
            with self.assertRaises(OSError) as ctx:
                conn_zero.connect()
            self.assertIn("SSRF blocked", str(ctx.exception))
            mock_conn.assert_not_called()

        conn_port = ResilientHTTPSConnection(
            "93.184.215.14",
            443,
            allow_private_ips=False,
            allowed_ports={8443},
        )
        conn_port.set_tunnel("93.184.215.14", 443)
        with patch("scrapers.common_utils._create_safe_connection") as mock_conn:
            with self.assertRaises(OSError) as ctx2:
                conn_port.connect()
            self.assertIn("Disallowed port 443", str(ctx2.exception))
            mock_conn.assert_not_called()

    def test_scoped_ipv6_sockaddr_blocked_in_is_safe_url_and_create_connection(self) -> None:
        scoped_addr = [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:4700:4700::1111", 443, 0, 2))]
        with patch("scrapers.common_utils.socket.getaddrinfo", return_value=scoped_addr):
            safe, reason = is_safe_url("https://example.com/")
            self.assertFalse(safe)
            self.assertIn("scoped IPv6", reason)

            with self.assertRaises(OSError) as ctx:
                _create_safe_connection(("example.com", 443), timeout=1.0, allow_private_ips=False)
            self.assertIn("scoped IPv6", str(ctx.exception))


class TestSafeHttpClientAndCircuitBreakerHardening(unittest.TestCase):
    """Verify SafeHttpClient streaming, POST cache isolation, header lookup, and CircuitBreaker bounds."""

    def test_single_read_fallback_does_not_loop(self) -> None:
        class NoArgResp:
            def __init__(self) -> None:
                self.read_calls = 0
                self.headers = {"Content-Type": "text/html; charset=utf-8"}

            def getcode(self) -> int:
                return 200

            def read(self) -> bytes:
                self.read_calls += 1
                return b"<html>short body</html>"

            def close(self) -> None:
                pass

        resp = NoArgResp()
        mock_opener = MagicMock()
        mock_opener.open.return_value = resp
        client = SafeHttpClient(min_delay=0.0, max_delay=0.0, enable_cache=False, opener=mock_opener)
        status, text, raw = client.request("https://example.com/single-read")
        self.assertEqual(status, 200)
        self.assertEqual(text, "<html>short body</html>")
        self.assertEqual(raw, b"<html>short body</html>")
        self.assertEqual(resp.read_calls, 1)
        client.close()

    def test_post_requests_do_not_cache_or_read_get_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            client = SafeHttpClient(
                min_delay=0.0,
                max_delay=0.0,
                max_retries=1,
                enable_cache=True,
                cache_fallback=True,
                cache_dir=tmpdir,
            )
            url = "https://www.bobaedream.co.kr/search"
            mock_opener = MagicMock()

            resp_post = MagicMock()
            resp_post.getcode.return_value = 200
            resp_post.read.side_effect = [b"POST RESULT", b""]
            resp_post.headers = {"Content-Type": "text/html; charset=utf-8"}
            mock_opener.open.return_value = resp_post
            client.opener = mock_opener

            status, text, _ = client.request(url, method="POST", data={"keyword": "BYD"})
            self.assertEqual(status, 200)
            self.assertEqual(text, "POST RESULT")
            self.assertIsNone(client.get_cached_response(url))

            # Populate GET cache, then fail a POST -> POST must not return GET cache
            client.set_cached_response(url, 200, "GET CACHED", b"GET CACHED")
            mock_opener.open.side_effect = OSError("network down")
            status2, text2, _ = client.request(url, method="POST", data={"keyword": "Tesla"})
            self.assertEqual(status2, 0)
            self.assertEqual(text2, "")
            self.assertFalse(client.last_response_from_cache)
            client.close()

    def test_http_error_case_insensitive_content_type_decoding(self) -> None:
        euckr_body = "잘못된 요청입니다".encode("euc-kr")
        err = urllib.error.HTTPError(
            url="https://example.com/err",
            code=400,
            msg="Bad Request",
            hdrs={"content-type": "text/html; charset=euc-kr"},  # type: ignore[arg-type]
            fp=io.BytesIO(euckr_body),
        )
        mock_opener = MagicMock()
        mock_opener.open.side_effect = err
        client = SafeHttpClient(min_delay=0.0, max_delay=0.0, max_retries=1, enable_cache=False, opener=mock_opener)
        status, text, _ = client.request("https://example.com/err")
        self.assertEqual(status, 400)
        self.assertEqual(text, "잘못된 요청입니다")
        client.close()

    def test_circuit_breaker_max_hosts_and_idna_normalization(self) -> None:
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=30.0, max_hosts=3)
        cb.record_failure("https://a.example.com/1")
        cb.record_failure("https://b.example.com/1")
        cb.record_failure("https://c.example.com/1")
        cb.record_failure("https://d.example.com/1")
        self.assertLessEqual(len(cb._hosts), 3)

        cb_idna = CircuitBreaker(failure_threshold=1, cooldown_seconds=30.0)
        cb_idna.record_failure("http://１２７.０.０.１/admin")
        self.assertEqual(cb_idna.get_state("127.0.0.1"), CircuitBreakerState.OPEN)

    def test_bounded_cache_set_zero_and_oversized_eviction(self) -> None:
        zero_cache = {}
        bounded_cache_set(zero_cache, "k", "v", max_size=0)
        self.assertEqual(zero_cache, {})

        pre_filled = {"a": 1, "b": 2, "c": 3, "d": 4}
        bounded_cache_set(pre_filled, "e", 5, max_size=2)
        self.assertEqual(len(pre_filled), 2)
        self.assertIn("e", pre_filled)


class TestCharsetAndHtmlHelpersHardening(unittest.TestCase):
    """Verify UTF-8 BOM fallback, balanced tag extraction, meta tags, and math text preservation."""

    def test_robust_decode_utf8_bom_with_corrupt_byte_preserves_utf8(self) -> None:
        raw = b"\xef\xbb\xbf" + "전기차 배터리".encode("utf-8") + b"\xff" + " 테스트".encode("utf-8")
        decoded = robust_decode(raw)
        self.assertIn("전기차 배터리", decoded)
        self.assertIn("테스트", decoded)
        self.assertIn("\ufffd", decoded)

    def test_extract_balanced_tag_content_ignores_comments_and_scripts(self) -> None:
        html_doc = """
        <div class="bodyCont">
          <!-- <div>fake open inside comment -->
          <script>var html = "<div>unclosed</div><div>";</script>
          <div class="inner">실제 본문</div>
        </div>
        <div>바깥 영역</div>
        """
        inner = extract_balanced_tag_content(
            html_doc,
            r'<div\b[^>]*\bclass=["\'][^"\']*\bbodyCont\b[^"\']*["\'][^>]*>',
            tag_name="div",
        )
        self.assertIn("실제 본문", inner)
        self.assertNotIn("바깥 영역", inner)

    def test_extract_meta_content_handles_comments_and_gt_in_quotes(self) -> None:
        html_doc = """
        <html><head>
          <!-- <meta property="og:title" content="주석 제목"> -->
          <meta property="og:title" content="BYD > 테슬라 비교">
        </head></html>
        """
        self.assertEqual(extract_meta_content(html_doc, "og:title"), "BYD > 테슬라 비교")

    def test_clean_html_text_preserves_comparison_operators(self) -> None:
        raw = "<p>가격 < 3000만원 이고 출력 > 200마력 입니다</p>"
        self.assertEqual(clean_html_text(raw), "가격 < 3000만원 이고 출력 > 200마력 입니다")


class TestScraperDomParsersHardening(unittest.TestCase):
    """Verify Blind, Bobaedream, DCInside, and CafeForumMiner DOM parser fixes."""

    def test_blind_absolute_topic_links_and_multiline_comments(self) -> None:
        scraper = BlindScraper(client=SafeHttpClient(min_delay=0.0, max_delay=0.0))
        feed_html = '<a href="https://www.teamblind.com/kr/post/abc-123">BYD 아토3 후기</a>'
        items = scraper.parse_topic_feed(feed_html, topic_name="자동차")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], "https://www.teamblind.com/kr/post/abc-123")

        post_data = {
            "url": "https://www.teamblind.com/kr/post/abc-123",
            "title": "아토3 충전 질문",
            "body": "본문 길이가 짧음",
            "comments": ["[현대차] 첫줄 충전 튕김 발생\n둘째줄 상세 내용도 보존되어야 합니다."],
        }
        records = scraper.extract_complaint_records(post_data)
        self.assertEqual(len(records), 1)
        self.assertIn("둘째줄 상세 내용도 보존되어야 합니다.", records[0].raw_quote)
        scraper.close(force=True)

    def test_bobaedream_view_php_and_nested_body_isolation(self) -> None:
        scraper = BobaedreamScraper(client=SafeHttpClient(min_delay=0.0, max_delay=0.0))
        list_html = '<a href="/board/bulletin/view.php?code=electric&No=9001">아토3 충전 튕김 현상</a>'
        items = scraper.parse_board_list(list_html, "electric")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["post_no"], "9001")

        detail_html = """
        <html><body>
          <strong class="title">아토3 후기</strong>
          <div class="bodyCont"><div>진짜 본문</div></div>
          <div class="sidebar">사이드바 광고</div>
          <!-- //bodyCont -->
        </body></html>
        """
        detail = scraper.parse_post_detail(detail_html, "https://www.bobaedream.co.kr/view?code=electric&No=9001")
        self.assertEqual(detail["body"], "진짜 본문")
        self.assertNotIn("사이드바 광고", detail["body"])
        scraper.close(force=True)

    def test_dcinside_author_ip_isolation_wrapped_counts_and_del_yn_lowercase(self) -> None:
        scraper = DCInsideScraper(client=SafeHttpClient(min_delay=0.0, max_delay=0.0))
        detail_html = """
        <html><body>
          <span class="title_subject">고정닉 게시글</span>
          <td class="gall_writer"><span class="nickname">고정닉작성자</span></td>
          <span class="gall_count">조회 <em>4,321</em></span>
          <span class="gall_reply_num">추천 <span>77</span></span>
          <div class="writing_view_box"><div>본문 내용입니다.</div></div>
          <div class="cmt_nickbox"><span class="ip">(223.38)</span></div>
          <p class="usertxt">댓글 내용입니다.</p>
        </body></html>
        """
        detail = scraper.parse_post_detail(
            detail_html, "https://gall.dcinside.com/mgallery/board/view/?id=electriccar&no=10", "electriccar", "10"
        )
        self.assertEqual(detail["author_badge"], "고정닉작성자")
        self.assertEqual(detail["author_type"], "dc_fixed_nick")
        self.assertEqual(detail["view_count"], 4321)
        self.assertEqual(detail["upvote_count"], 77)
        self.assertEqual(detail["body"], "본문 내용입니다.")

        # Test lowercase del_yn filtering in AJAX comments
        mock_client = MagicMock()
        mock_client.request.return_value = (
            200,
            '{"comments":[{"memo":"삭제된 댓글입니다.","del_yn":"y"},{"memo":"유효한 댓글 내용입니다.","del_yn":"N"}]}',
            b"",
        )
        scraper_ajax = DCInsideScraper(client=mock_client)
        comments = scraper_ajax.fetch_comments_ajax("electriccar", "10", e_s_n_o="tok")
        self.assertEqual(comments, ["유효한 댓글 내용입니다."])
        scraper.close(force=True)

    def test_cafe_forum_miner_protocol_relative_pomppu_and_uppercase_clien(self) -> None:
        miner = CafeForumMiner(client=SafeHttpClient(min_delay=0.0, max_delay=0.0))
        pomppu_html = '<a href="//www.ppomppu.co.kr/zboard/view.php?id=car&no=777">아토3 급속충전 후기</a>'
        clien_html = '<a CLASS="list_subject" href="/service/board/cm_car/8888">아이오닉5 빗길 주행</a>'
        p_items = miner.parse_pomppu_list(pomppu_html)
        c_items = miner.parse_clien_list(clien_html)
        self.assertEqual(len(p_items), 1)
        self.assertEqual(p_items[0]["url"], "https://www.ppomppu.co.kr/zboard/view.php?id=car&no=777")
        self.assertEqual(len(c_items), 1)
        self.assertEqual(c_items[0]["url"], "https://www.clien.net/service/board/cm_car/8888")
        miner.close(force=True)


if __name__ == "__main__":
    unittest.main()
