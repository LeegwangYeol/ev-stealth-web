"""Targeted audit & regression tests for scrapers/ fixes (2026-11-23)."""

from __future__ import annotations

import json
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
    CircuitBreakerState,
    SafeHttpClient,
    classify_ev_text,
    clean_html_text,
    extract_meta_content,
    is_safe_url,
    normalize_scraper_url,
    robust_decode,
)
from scrapers.dcinside_scraper import DCInsideScraper


class TestScrapersSSRFHardening(unittest.TestCase):
    """Verify SSRF fixes in scrapers.common_utils."""

    def test_idna_fullwidth_and_homograph_blocked_offline(self) -> None:
        """Fullwidth / Unicode confusable loopback & metadata hosts must be blocked even if DNS fails."""
        with patch("scrapers.common_utils.socket.getaddrinfo", side_effect=socket.gaierror("offline")):
            for url in (
                "http://１２７.０.０.１/admin",
                "http://１６９.２５４.１６９.２５４/latest/meta-data/",
                "http://ⓛⓞⓒⓐⓛⓗⓞⓢⓣ/secret",
            ):
                safe, reason = is_safe_url(url)
                self.assertFalse(safe, f"Expected offline SSRF block for {url}, got reason={reason}")
                self.assertIn("SSRF blocked", reason)

    def test_whitespace_in_authority_blocked(self) -> None:
        """NBSP or space in URL authority must be rejected by is_safe_url and normalize_scraper_url."""
        safe, _ = is_safe_url("http://example.com\u00a0/admin")
        self.assertFalse(safe)
        self.assertIsNone(normalize_scraper_url("https://example.com\u00a0/post/1", "https://example.com"))
        self.assertIsNone(normalize_scraper_url("//example.com\u00a0/post/1", "https://example.com"))

    def test_allowed_ports_enforced_with_allow_private_ips(self) -> None:
        """Explicit allowed_ports must still be enforced (including implicit 80/443) when allow_private_ips=True."""
        safe_ok, _ = is_safe_url("http://127.0.0.1:8080/api", allow_private_ips=True, allowed_ports={8080})
        self.assertTrue(safe_ok)
        safe_bad, reason = is_safe_url("http://127.0.0.1:6379/", allow_private_ips=True, allowed_ports={8080})
        self.assertFalse(safe_bad)
        self.assertIn("Disallowed port", reason)
        safe_implicit_bad, reason_imp = is_safe_url("http://127.0.0.1/api", allow_private_ips=True, allowed_ports={8080})
        self.assertFalse(safe_implicit_bad)
        self.assertIn("Disallowed port 80", reason_imp)

    def test_safe_redirect_strips_sensitive_headers_cross_origin(self) -> None:
        """SafeRedirectHandler strips Authorization/Cookie headers on cross-origin redirects."""
        import io
        import urllib.request
        from scrapers.common_utils import SafeRedirectHandler

        handler = SafeRedirectHandler(allow_private_ips=False)
        req = urllib.request.Request(
            "https://example.com/start",
            headers={"Authorization": "Bearer secret", "Cookie": "sid=abc", "X-Trace": "keep"},
        )
        new_req = handler.redirect_request(
            req, io.BytesIO(b""), 302, "Found", {}, "https://other.example.org/next"
        )
        self.assertIsNotNone(new_req)
        self.assertFalse(new_req.has_header("Authorization"))
        self.assertFalse(new_req.has_header("Cookie"))
        self.assertEqual(new_req.get_header("X-trace"), "keep")

    def test_resilient_https_tunnel_host_ssrf_blocked(self) -> None:
        """ResilientHTTPSConnection.connect validates _tunnel_host via is_safe_url before connecting."""
        from scrapers.common_utils import ResilientHTTPSConnection

        conn = ResilientHTTPSConnection("93.184.215.14", 443, allow_private_ips=False)
        conn.set_tunnel("169.254.169.254", 443)
        with patch("scrapers.common_utils._create_safe_connection") as mock_create_conn:
            with self.assertRaises(OSError) as ctx:
                conn.connect()
            self.assertIn("SSRF blocked", str(ctx.exception))
            mock_create_conn.assert_not_called()


class TestWarmUpCircuitBreakerAndCacheSafety(unittest.TestCase):
    """Verify warm_up_session circuit breaker integration and SafeHttpClient resource bounds."""

    def test_warm_up_session_trips_and_reopens_circuit_breaker(self) -> None:
        """warm_up_session failures must trip circuit breaker and re-trip from HALF_OPEN."""
        client = SafeHttpClient(
            min_delay=0.0,
            max_delay=0.0,
            failure_threshold=1,
            circuit_cooldown=0.05,
            enable_cache=False,
        )
        mock_opener = MagicMock()
        mock_fp = MagicMock()
        err_403 = urllib.error.HTTPError(
            url="https://www.bobaedream.co.kr/",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=mock_fp,
        )
        mock_opener.open.side_effect = err_403
        client.opener = mock_opener

        self.assertFalse(client.warm_up_session("https://www.bobaedream.co.kr/"))
        self.assertEqual(client.get_circuit_state("www.bobaedream.co.kr"), CircuitBreakerState.OPEN)
        self.assertTrue(mock_fp.close.called)

        # Wait for HALF_OPEN and fail again -> must re-trip to OPEN, not remain HALF_OPEN
        import time
        time.sleep(0.08)
        mock_opener.open.side_effect = OSError("connection reset")
        self.assertFalse(client.warm_up_session("https://www.bobaedream.co.kr/"))
        self.assertEqual(client.get_circuit_state("www.bobaedream.co.kr"), CircuitBreakerState.OPEN)
        client.close()

    def test_invalid_bounds_and_lru_eviction(self) -> None:
        """Invalid max_response_size/max_cookies normalize safely and LRU cache stays bounded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            client = SafeHttpClient(
                max_response_size=None,  # type: ignore[arg-type]
                max_cookies=True,  # type: ignore[arg-type]
                cache_dir=tmpdir,
                enable_cache=True,
            )
            self.assertGreater(client.max_response_size, 0)
            self.assertGreater(client.max_cookies, 0)
            for i in range(520):
                client.set_cached_response(f"https://example.com/p/{i}", 200, f"body-{i}", b"body")
            self.assertLessEqual(len(client._memory_cache), 500)
            client.close()


class TestEncodingAndParserFixes(unittest.TestCase):
    """Verify encoding aliases, HTML cleaning, and scraper parser bug fixes."""

    def test_clean_html_text_preserves_inline_word_boundaries(self) -> None:
        """Tags like <pre> or <track> must not match <p> or <tr> in block newline regex."""
        raw = "<p>첫줄 <track kind='sub'>이어짐</p><pre>코드</pre>"
        cleaned = clean_html_text(raw)
        self.assertEqual(cleaned, "첫줄 이어짐\n코드")

    def test_robust_decode_korean_aliases(self) -> None:
        """cp-949 / ms-949 / ks_c_5601 / euckr aliases must decode cleanly."""
        sample = "전기차 급속 충전".encode("cp949")
        for alias in ("cp-949", "ms-949", "ks_c_5601", "euckr"):
            self.assertEqual(robust_decode(sample, alias), "전기차 급속 충전")

    def test_extract_meta_content_attribute_order(self) -> None:
        """extract_meta_content handles content before property and single quotes."""
        html_doc = "<meta content='테스트 &amp; 제목' property='og:title' />"
        self.assertEqual(extract_meta_content(html_doc, "og:title"), "테스트 & 제목")

    def test_blind_scraper_meta_order_and_topic_passthrough(self) -> None:
        """BlindScraper handles reversed og:title/og:description and topic_name passthrough."""
        scraper = BlindScraper(client=SafeHttpClient(min_delay=0.0, max_delay=0.0))
        feed_html = """
        <script id="__NEXT_DATA__" type="application/json">
        {"props":{"pageProps":{"articles":[{"id":"999","title":"BYD &amp; 아토3","slug":"atto3","author":{"companyName":"기아"}}]}}}
        </script>
        """
        items = scraper.parse_topic_feed(feed_html, topic_name="전기차")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "BYD & 아토3")
        self.assertEqual(items[0]["company"], "기아")
        self.assertEqual(items[0]["topic"], "전기차")

        detail_html = """
        <html><head>
          <meta content="블라인드 제목 테스트" property="og:title" />
          <meta content="블라인드 본문 설명 테스트입니다" property="og:description" />
        </head><body><span class='company'>현대차</span></body></html>
        """
        detail = scraper.parse_post_detail(detail_html, "https://www.teamblind.com/kr/post/1")
        self.assertEqual(detail["title"], "블라인드 제목 테스트")
        self.assertEqual(detail["body"], "블라인드 본문 설명 테스트입니다")
        self.assertEqual(detail["company"], "현대차")
        scraper.close(force=True)

    def test_bobaedream_ignores_head_dates_and_parses_wrapped_counts(self) -> None:
        """BobaedreamScraper ignores <head> dates, parses <em> wrapped counts, and anchors code=."""
        scraper = BobaedreamScraper(client=SafeHttpClient(min_delay=0.0, max_delay=0.0))
        search_html = """
        <dl>
          <dt><a href="/view?mycode=bad&code=electric&No=111">전기차 충전 후기</a></dt>
          <dt><a href="/view?code=electric&No=111">전기차 충전 후기</a></dt>
        </dl>
        """
        search_items = scraper.parse_search_results(search_html)
        self.assertEqual(len(search_items), 1)
        self.assertEqual(search_items[0]["board_code"], "electric")

        detail_html = """
        <html>
        <head><script>var buildDate = '2020-01-01';</script></head>
        <body>
          <strong class='title'>아토3 후기</strong>
          <span class="countGroup">2026.11.22 10:30 | 조회 <em>1,234</em> | 추천 <span>56</span></span>
          <div class="bodyCont">본문 내용이 충분히 길게 작성되었습니다.</div>
        </body></html>
        """
        detail = scraper.parse_post_detail(detail_html, "https://www.bobaedream.co.kr/view?code=electric&No=111")
        self.assertEqual(detail["published_at"], "2026-11-22 10:30")
        self.assertEqual(detail["view_count"], 1234)
        self.assertEqual(detail["upvote_count"], 56)
        scraper.close(force=True)

    def test_dcinside_div_gall_writer_and_head_date_isolation(self) -> None:
        """DCInsideScraper parses <div class='gall_writer'> and ignores <head> script dates."""
        scraper = DCInsideScraper(client=SafeHttpClient(min_delay=0.0, max_delay=0.0))
        detail_html = """
        <html>
        <head>
          <script>var ver = "2019.01.01";</script>
          <meta content="디시 제목 테스트" property="og:title" />
        </head>
        <body>
          <div class="gall_writer ub-writer"><span class="nickname"><em>전기차주</em></span><span class="ip">(1.2)</span></div>
          <span class="gall_date" title="2026-11-22 09:15:00">11.22</span>
          <div class="writing_view_box">실제 본문 내용입니다.</div>
          <p class="usertxt">[보이스리플] 음성댓글</p>
          <p class="usertxt">정상적인 댓글 내용입니다.</p>
        </body></html>
        """
        detail = scraper.parse_post_detail(
            detail_html, "https://gall.dcinside.com/mgallery/board/view/?id=electriccar&no=1", "electriccar", "1"
        )
        self.assertEqual(detail["title"], "디시 제목 테스트")
        self.assertEqual(detail["author_badge"], "전기차주 (1.2)")
        self.assertEqual(detail["published_at"], "2026-11-22 09:15:00")
        self.assertEqual(detail["comments"], ["정상적인 댓글 내용입니다."])
        scraper.close(force=True)

    def test_cafe_forum_miner_absolute_links_and_classify_parity(self) -> None:
        """CafeForumMiner parses absolute Pomppu/Clien links and classify_ev_text matches scrapers."""
        miner = CafeForumMiner(client=SafeHttpClient(min_delay=0.0, max_delay=0.0))
        pomppu_html = '<a href="https://www.ppomppu.co.kr/zboard/view.php?id=car&no=555">아토3 주차 센서 오작동</a>'
        clien_html = '<a class="list_subject" href="https://www.clien.net/service/board/cm_car/777">아이오닉5 ICCU 경고등</a>'
        self.assertEqual(len(miner.parse_pomppu_list(pomppu_html)), 1)
        self.assertEqual(len(miner.parse_clien_list(clien_html)), 1)

        veh, cat = classify_ev_text("아이오닉5 급속 충전 중 ICCU 경고등 튕김")
        self.assertEqual(veh, "Hyundai Ioniq 5")
        self.assertEqual(cat, "charging")
        miner.close(force=True)


if __name__ == "__main__":
    unittest.main()
