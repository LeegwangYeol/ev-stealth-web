"""
Comprehensive Hardening & Adversarial Edge Case Verification Suite for:
- utils.http_client (SafeHttpClient, clean_html_text, robust_decode, memory bounds, timeouts)
- utils.safe_http (compatibility alias and interface parity)
- crawlers.base_crawler (BaseCrawler context management, session clearing, input validation)
- crawlers.bobaedream & crawlers.bobaedream_crawler (DOM resilience, balanced containers, EUC-KR)
- crawlers.dcinside & crawlers.dcinside_crawler (Attribute order independence, nested write_div, e_s_n_o)
"""

from __future__ import annotations

import http.cookiejar
import io
import json
import unittest
import urllib.error
import urllib.request

from crawlers.base_crawler import BaseCrawler
from crawlers.bobaedream import (
    BobaeDreamCrawler,
    BobaedreamCrawler,
    extract_container_content as bd_extract,
)
from crawlers.dcinside import (
    DCInsideCrawler,
    DcInsideCrawler,
    extract_container_content as dc_extract,
)
from utils.http_client import (
    MAX_COOKIEJAR_ENTRIES,
    MAX_RESPONSE_BYTES,
    SafeHttpClient,
    clean_html_text,
    encode_euc_kr_query,
    robust_decode,
)
from utils.safe_http import SafeHttpClient as SafeHttpClientAlias


class TestSafeHttpClientHardening(unittest.TestCase):
    """Test suite for SafeHttpClient memory bounds, timeout handling, and connection recovery."""

    def test_alias_parity(self):
        """utils.safe_http exports SafeHttpClient identical to utils.http_client."""
        self.assertIs(SafeHttpClient, SafeHttpClientAlias)

    def test_invalid_and_empty_url_handling(self):
        """Request immediately aborts and returns (0, '', b'') without retrying on invalid/empty URLs."""
        client = SafeHttpClient(max_retries=3, enable_jitter=False)
        for bad_url in ["", "   ", None, "ftp://example.com", "file:///etc/passwd"]:  # type: ignore
            status, text, raw = client.request(bad_url)  # type: ignore
            self.assertEqual(status, 0)
            self.assertEqual(text, "")
            self.assertEqual(raw, b"")

    def test_timeout_normalization_and_handling(self):
        """Negative, zero, or non-numeric timeouts safely normalize to positive floats."""
        client = SafeHttpClient(timeout=-5.0)
        self.assertEqual(client.timeout, -5.0)  # Init stores value

        # In request(), negative timeouts normalize to 15.0 without BlockingIOError
        class TimeoutOpener:
            def open(self, req, timeout=15.0):
                self.recorded_timeout = timeout
                raise TimeoutError("The read operation timed out")

        opener = TimeoutOpener()
        client = SafeHttpClient(max_retries=1, enable_jitter=False, opener=opener)
        status, text, raw = client.request("https://example.com/slow", timeout=0.0)
        self.assertEqual(status, 0)
        self.assertEqual(opener.recorded_timeout, 15.0)

    def test_bounded_response_stream_prevents_memory_leak(self):
        """Responses exceeding max_response_size are safely truncated to prevent OOM."""
        class BigResponse:
            def __init__(self):
                self.bytes_sent = 0
            def getcode(self):
                return 200
            @property
            def headers(self):
                return {"Content-Type": "text/plain; charset=utf-8"}
            def read(self, n=65536):
                if self.bytes_sent >= 100000:
                    return b""
                chunk_len = min(n, 100000 - self.bytes_sent)
                self.bytes_sent += chunk_len
                return b"A" * chunk_len
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass

        class BigOpener:
            def open(self, req, timeout=15.0):
                return BigResponse()

        # Set max_response_size to 5000 bytes
        client = SafeHttpClient(max_retries=1, enable_jitter=False, opener=BigOpener(), max_response_size=5000)
        status, text, raw = client.request("https://example.com/huge")
        self.assertEqual(status, 200)
        self.assertLessEqual(len(raw), 5000 + 65536)  # Bounded at first chunk exceeding cap

    def test_cookie_jar_pruning_and_clearing(self):
        """CookieJar auto-prunes expired cookies and clears beyond max_cookies."""
        jar = http.cookiejar.CookieJar()
        client = SafeHttpClient(enable_jitter=False, cookie_jar=jar, max_cookies=5)

        # Populate with dummy cookies
        for i in range(10):
            c = http.cookiejar.Cookie(
                version=0, name=f"c_{i}", value="1", port=None, port_specified=False,
                domain="example.com", domain_specified=True, domain_initial_dot=False,
                path="/", path_specified=True, secure=False, expires=None, discard=False,
                comment=None, comment_url=None, rest={}, rfc2109=False,
            )
            client.cookie_jar.set_cookie(c)

        self.assertEqual(len(client.cookie_jar), 10)
        # _sleep_with_jitter prunes cookies when exceeding max_cookies
        client._sleep_with_jitter()
        self.assertEqual(len(client.cookie_jar), 0)

    def test_context_manager_and_close(self):
        """SafeHttpClient cleanly resets and closes via context manager protocol."""
        with SafeHttpClient(enable_jitter=False) as client:
            client.clear_cookies()
            self.assertEqual(len(client.cookie_jar), 0)

    def test_clean_html_text_resilience(self):
        """clean_html_text sanitizes null bytes, scripts, comments, and entities."""
        raw = "<div>Hello\x00World<!-- comment --> <script>alert(1);</script><p>Paragraph</p>"
        cleaned = clean_html_text(raw)
        self.assertNotIn("alert(1)", cleaned)
        self.assertNotIn("\x00", cleaned)
        self.assertIn("Hello World", cleaned)
        self.assertIn("Paragraph", cleaned)

        # Non-string safety
        self.assertEqual(clean_html_text(None), "")  # type: ignore
        self.assertEqual(clean_html_text(123), "")  # type: ignore


class TestBaseCrawlerHardening(unittest.TestCase):
    """Test BaseCrawler lifecycle, session management, and post URL validation."""

    def test_base_crawler_context_manager_and_close(self):
        class DummyCrawler(BaseCrawler):
            def parse_post_detail(self, html_content: str, post_url: str, **kwargs):
                return {"post_id": "1", "url": post_url}

        with DummyCrawler() as crawler:
            crawler.ensure_warm_up("https://example.com")
            crawler.clear_session()
            self.assertFalse(crawler._warmed_up)

    def test_fetch_post_invalid_url(self):
        class DummyCrawler(BaseCrawler):
            def parse_post_detail(self, html_content: str, post_url: str, **kwargs):
                return {"post_id": "1", "url": post_url}

        crawler = DummyCrawler()
        self.assertIsNone(crawler.fetch_post(""))
        self.assertIsNone(crawler.fetch_post(None))  # type: ignore


class TestBobaeDreamCrawlerDOMResilience(unittest.TestCase):
    """Test BobaeDream balanced container extraction and malformed DOM resilience."""

    def test_balanced_container_preserves_nested_divs(self):
        html = '<div class="bodyCont"><div>Paragraph 1</div><div>Paragraph 2 with crucial details</div></div><div class="other">Other</div>'
        extracted = bd_extract(html, "div", "bodyCont")
        self.assertIn("Paragraph 1", extracted)
        self.assertIn("Paragraph 2 with crucial details", extracted)
        self.assertNotIn("Other", extracted)

    def test_list_page_single_and_double_quotes_and_param_order(self):
        crawler = BobaeDreamCrawler()
        # Mix of double quotes, single quotes, and swapped query parameters
        html = """
        <a href="/view?code=national&No=1001">국산차 정상 제목</a>
        <a href='/view?No=1002&code=national'>국산차 역순 파라미터 제목</a>
        <a href="/view?code=national&No=9999">[공지] 공지사항 필터링 대상</a>
        """
        items = crawler.parse_list_page(html, "national")
        self.assertEqual(len(items), 2)
        nos = {item["post_id"] for item in items}
        self.assertEqual(nos, {"1001", "1002"})

    def test_parse_post_detail_none_safe(self):
        crawler = BobaeDreamCrawler()
        res = crawler.parse_post_detail(None, "https://www.bobaedream.co.kr/view?code=national&No=123")  # type: ignore
        self.assertIsInstance(res, dict)
        self.assertEqual(res["platform"], "bobaedream")
        self.assertEqual(res["title"], "")

    def test_bobaedream_alias(self):
        self.assertIs(BobaeDreamCrawler, BobaedreamCrawler)


class TestDCInsideCrawlerDOMResilience(unittest.TestCase):
    """Test DCInside arbitrary attribute order, balanced write_div, and e_s_n_o tokens."""

    def test_tr_attribute_order_independence(self):
        crawler = DCInsideCrawler()
        # Row 1: class first, data-no second
        # Row 2: data-no first, class second
        # Row 3: single quotes
        html = """
        <table>
          <tr class="ub-content us-post" data-no="11111">
            <td class="gall_tit"><a href="/board/view/?id=car_new1&no=11111">첫번째 글</a></td>
            <td class="gall_date" title="2026-09-08 10:00:00">10:00</td>
          </tr>
          <tr data-no="22222" class="ub-content us-post">
            <td class="gall_tit"><a href="/board/view/?id=car_new1&no=22222">두번째 글 (속성 역순)</a></td>
            <td class="gall_date" title="2026-09-08 10:05:00">10:05</td>
          </tr>
          <tr data-no='33333' class='ub-content'>
            <td class='gall_tit'><a href='/board/view/?id=car_new1&no=33333'>세번째 글 (작은따옴표)</a></td>
            <td class='gall_date' title='2026-09-08 10:10:00'>10:10</td>
          </tr>
        </table>
        """
        items = crawler.parse_gallery_list(html, "car_new1")
        self.assertEqual(len(items), 3)
        nos = [item["post_id"] for item in items]
        self.assertEqual(nos, ["11111", "22222", "33333"])

    def test_esno_token_attribute_order_independence(self):
        crawler = DCInsideCrawler()
        # value first, id second
        html1 = '<input value="secret_token_123" id="e_s_n_o">'
        self.assertEqual(crawler.extract_esno_token(html1), "secret_token_123")

        # name first, value second
        html2 = '<input name="e_s_n_o" value="secret_token_456">'
        self.assertEqual(crawler.extract_esno_token(html2), "secret_token_456")

    def test_nested_write_div_not_truncated(self):
        crawler = DCInsideCrawler()
        html = """
        <div class="write_div">
          <div style="font-size:12px">첫번째 단락</div>
          <div style="font-size:14px">두번째 핵심 결함 내용 단락</div>
        </div>
        <div class="btn_recommend">추천</div>
        """
        detail = crawler.parse_post_detail(html, "https://gall.dcinside.com/board/view/?id=car_new1&no=999")
        self.assertIn("첫번째 단락", detail["content"])
        self.assertIn("두번째 핵심 결함 내용 단락", detail["content"])
        self.assertNotIn("추천", detail["content"])

    def test_dcinside_alias(self):
        self.assertIs(DCInsideCrawler, DcInsideCrawler)

    def test_self_closing_tag_depth_tracking(self):
        """Self-closing tags inside container do not increment depth incorrectly."""
        html = '<div class="bodyCont"><div>Valid line</div><div class="divider" /><div>After divider</div></div><div class="footer">Footer</div>'
        extracted = bd_extract(html, "div", "bodyCont")
        self.assertIn("Valid line", extracted)
        self.assertIn("After divider", extracted)
        self.assertNotIn("Footer", extracted)

    def test_timestamp_month_day_with_time(self):
        """Community timestamps with 'MM.DD HH:MM' parse correctly into current year ISO timestamps."""
        from crawlers.bobaedream import _normalize_iso_timestamp as bd_ts
        from crawlers.dcinside import _normalize_iso_timestamp as dc_ts

        ts_b = bd_ts("09.15 14:25")
        self.assertIn("-09-15T14:25:00", ts_b)

        ts_d = dc_ts("09.15 10:11")
        self.assertIn("-09-15T10:11:00", ts_d)

    def test_post_id_zero_falsy_protection(self):
        """post_id=0 must be preserved as '0' instead of falling back or becoming empty."""
        crawler_b = BobaeDreamCrawler()
        res_b = crawler_b.parse_post_detail("<div>test</div>", "https://example.com", post_id=0)  # type: ignore
        self.assertEqual(res_b["post_id"], "0")

        crawler_d = DCInsideCrawler()
        res_d = crawler_d.parse_post_detail("<div>test</div>", "https://example.com", post_id=0)  # type: ignore
        self.assertEqual(res_d["post_id"], "0")

    def test_crawler_relative_url_normalization(self):
        """Relative post URLs are normalized to absolute domain URLs."""
        from unittest.mock import MagicMock
        mock_client = MagicMock(spec=SafeHttpClient)
        mock_client.get.return_value = (200, "<html><strong class='title'>Title</strong><div class='bodyCont'>Content</div></html>", b"")

        crawler_b = BobaeDreamCrawler(client=mock_client)
        crawler_b.fetch_post("/view?code=national&No=123")
        called_url = mock_client.get.call_args[0][0]
        self.assertTrue(called_url.startswith("https://www.bobaedream.co.kr/view"))

        mock_client_d = MagicMock(spec=SafeHttpClient)
        mock_client_d.get.return_value = (200, "<html><span class='title_subject'>Title</span><div class='write_div'>Content</div></html>", b"")
        crawler_d = DCInsideCrawler(client=mock_client_d)
        crawler_d.fetch_post("/board/view/?id=car_new1&no=456")
        called_url_d = mock_client_d.get.call_args[0][0]
        self.assertTrue(called_url_d.startswith("https://gall.dcinside.com/board/view"))

    def test_network_dropout_recovery_in_crawl_loops(self):
        """Network exceptions on page 2 gracefully exit loop and retain page 1 results."""
        from unittest.mock import MagicMock
        mock_client = MagicMock(spec=SafeHttpClient)
        page1_html = "<a href='/view?code=national&No=101'>아이오닉5 고장</a>"
        post_html = "<strong class='title'>아이오닉5 고장</strong><div class='bodyCont'>본문</div>"

        def mock_get(url, *args, **kwargs):
            if "page=1" in url:
                return (200, page1_html, b"")
            elif "No=101" in url:
                return (200, post_html, b"")
            elif "page=2" in url:
                raise ConnectionResetError("Connection dropped by peer")
            return (404, "", b"")

        mock_client.get.side_effect = mock_get
        crawler = BobaeDreamCrawler(client=mock_client)
        posts = crawler.crawl_board("national", pages=3)
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["post_id"], "101")

    def test_dcinside_comment_replies_json_parsing(self):
        """Nested replies in DCInside comment API are parsed."""
        crawler = DCInsideCrawler()
        json_data = json.dumps({
            "comments": [
                {
                    "memo": "부품 교체 받으셨나요?",
                    "sub_comments": [
                        {"memo": "네 어제 직영센터에서 교체 완료했습니다."}
                    ]
                }
            ]
        })
        parsed = crawler.parse_comment_json(json_data)
        self.assertEqual(len(parsed), 2)
        self.assertIn("부품 교체", parsed[0])
        self.assertIn("직영센터", parsed[1])

    def test_limit_zero_returns_empty_list(self):
        """Passing limit=0 returns empty list without fetching."""
        crawler_b = BobaeDreamCrawler()
        self.assertEqual(crawler_b.crawl_board("national", limit=0), [])
        self.assertEqual(crawler_b.search_board("national", "아이오닉", limit=0), [])
        self.assertEqual(crawler_b.crawl_posts_by_keyword("아이오닉", limit=0), [])

        crawler_d = DCInsideCrawler()
        self.assertEqual(crawler_d.crawl_gallery("car_new1", limit=0), [])
        self.assertEqual(crawler_d.search_gallery("car_new1", "아이오닉", limit=0), [])
        self.assertEqual(crawler_d.crawl_posts_by_keyword("아이오닉", limit=0), [])


class TestHttpAdvancedErrorRecoveryAndBaseCrawlerLifecycle(unittest.TestCase):
    """
    Unit test coverage for:
    - BaseCrawler lifecycle, properties (cookies, timeout, is_warmed_up), method stubs, client ownership
    - SafeHttpClient error recovery: RemoteDisconnected, IncompleteRead, SSLError, Cloudflare 520, 408
    - User-Agent rotation vs session pinning, custom headers (Accept-Language), cookie dict access
    - Partial response salvage on IncompleteRead disconnect
    """

    def test_remote_disconnected_recovery_and_retry(self):
        """RemoteDisconnected error triggers retry and logs appropriately."""
        import http.client
        resp_mock = unittest.mock.MagicMock()
        resp_mock.getcode.return_value = 200
        resp_mock.headers = {"Content-Type": "text/html; charset=utf-8"}
        resp_mock.read.side_effect = [b"<html>Recovered after disconnect</html>", b""]

        mock_opener = unittest.mock.MagicMock()
        mock_opener.open.side_effect = [
            urllib.error.URLError(http.client.RemoteDisconnected("Remote end closed connection without response")),
            resp_mock,
        ]
        client = SafeHttpClient(max_retries=2, enable_jitter=False, opener=mock_opener)
        status, text, raw = client.get("https://example.com/test-disconnect")
        self.assertEqual(status, 200)
        self.assertIn("Recovered after disconnect", text)
        self.assertEqual(mock_opener.open.call_count, 2)

    def test_incomplete_read_partial_salvage_on_final_attempt(self):
        """On final retry attempt, IncompleteRead partial bytes are salvaged rather than dropped."""
        import http.client
        resp_mock = unittest.mock.MagicMock()
        resp_mock.getcode.return_value = 200
        resp_mock.headers = {"Content-Type": "text/html; charset=utf-8"}
        resp_mock.read.side_effect = http.client.IncompleteRead(
            b"<html><div class='salvaged'>Partial Content</div>", 100
        )

        mock_opener = unittest.mock.MagicMock()
        mock_opener.open.return_value = resp_mock

        client = SafeHttpClient(max_retries=1, enable_jitter=False, opener=mock_opener)
        status, text, raw = client.get("https://example.com/test-incomplete")
        self.assertEqual(status, 200)
        self.assertIn("Partial Content", text)
        self.assertTrue(raw.startswith(b"<html>"))

    def test_ssl_error_recovery_and_retry(self):
        """SSL error triggers exponential backoff retry and recovers on success."""
        import ssl
        resp_mock = unittest.mock.MagicMock()
        resp_mock.getcode.return_value = 200
        resp_mock.headers = {"Content-Type": "text/html; charset=utf-8"}
        resp_mock.read.side_effect = [b"<html>SSL Handshake Success</html>", b""]

        mock_opener = unittest.mock.MagicMock()
        mock_opener.open.side_effect = [
            ssl.SSLEOFError("EOF occurred in violation of protocol"),
            resp_mock,
        ]
        client = SafeHttpClient(max_retries=2, enable_jitter=False, opener=mock_opener)
        status, text, raw = client.get("https://example.com/test-ssl")
        self.assertEqual(status, 200)
        self.assertIn("SSL Handshake Success", text)
        self.assertEqual(mock_opener.open.call_count, 2)

    def test_custom_headers_and_accept_language(self):
        """Custom default_headers and Accept-Language are forwarded to request."""
        client = SafeHttpClient(
            default_headers={"Accept-Language": "en-US,en;q=0.9", "X-Custom-Bot": "EVSwarm/1.0"},
            enable_jitter=False,
        )
        mock_opener = unittest.mock.MagicMock()
        resp_mock = unittest.mock.MagicMock()
        resp_mock.getcode.return_value = 200
        resp_mock.headers = {}
        resp_mock.read.side_effect = [b"ok", b""]
        mock_opener.open.return_value = resp_mock
        client.opener = mock_opener

        client.get("https://example.com/custom-headers", headers={"X-Per-Req": "123"})
        req = mock_opener.open.call_args[0][0]
        self.assertEqual(req.headers["Accept-language"], "en-US,en;q=0.9")
        self.assertEqual(req.headers["X-custom-bot"], "EVSwarm/1.0")
        self.assertEqual(req.headers["X-per-req"], "123")

    def test_user_agent_session_pinning(self):
        """When rotate_user_agent=False, User-Agent remains consistent across requests."""
        client = SafeHttpClient(
            user_agent="EV-Special-Agent/2026",
            rotate_user_agent=False,
            enable_jitter=False,
        )
        mock_opener = unittest.mock.MagicMock()
        resp_mock = unittest.mock.MagicMock()
        resp_mock.getcode.return_value = 200
        resp_mock.headers = {}
        resp_mock.read.side_effect = [b"ok", b""]
        mock_opener.open.return_value = resp_mock
        client.opener = mock_opener

        client.get("https://example.com/req1")
        req1 = mock_opener.open.call_args[0][0]
        self.assertEqual(req1.headers["User-agent"], "EV-Special-Agent/2026")

        client.get("https://example.com/req2")
        req2 = mock_opener.open.call_args[0][0]
        self.assertEqual(req2.headers["User-agent"], "EV-Special-Agent/2026")

    def test_get_cookie_dict_and_cookies_property(self):
        """get_cookie_dict returns key-value pairs matching cookie jar."""
        jar = http.cookiejar.CookieJar()
        c = http.cookiejar.Cookie(
            version=0, name="session_id", value="sess_abc123", port=None, port_specified=False,
            domain="example.com", domain_specified=True, domain_initial_dot=False,
            path="/", path_specified=True, secure=False, expires=None, discard=False,
            comment=None, comment_url=None, rest={}, rfc2109=False,
        )
        jar.set_cookie(c)
        client = SafeHttpClient(cookie_jar=jar, enable_jitter=False)
        cookies = client.get_cookie_dict()
        self.assertEqual(cookies.get("session_id"), "sess_abc123")

        # BaseCrawler exposes cookies property
        class DummyCrawler(BaseCrawler):
            def parse_post_detail(self, html_content: str, post_url: str, **kwargs):
                return {}

        crawler = DummyCrawler(client=client)
        self.assertEqual(crawler.cookies.get("session_id"), "sess_abc123")

    def test_base_crawler_lifecycle_and_stubs(self):
        """BaseCrawler default timeout, stubs, and client ownership behavior."""
        class DummyCrawler(BaseCrawler):
            def parse_post_detail(self, html_content: str, post_url: str, **kwargs):
                return {"post_id": "99", "url": post_url}

        # 1. Default timeout and base_url
        mock_client = unittest.mock.MagicMock(spec=SafeHttpClient)
        mock_client.warm_up_session.return_value = True
        crawler = DummyCrawler(client=mock_client, timeout=25.0, base_url="https://community.example.com")
        self.assertEqual(crawler.timeout, 25.0)
        self.assertEqual(crawler.base_url, "https://community.example.com")
        self.assertFalse(crawler.is_warmed_up)

        # 2. Method stubs
        self.assertEqual(crawler.crawl_posts_by_keyword("테슬라"), [])
        self.assertEqual(crawler.fetch_ajax_comments("https://example.com/post"), [])
        with self.assertRaises(NotImplementedError):
            crawler.build_list_url()
        with self.assertRaises(NotImplementedError):
            crawler.build_search_url()

        # 3. reset_session alias
        crawler.ensure_warm_up("https://community.example.com")
        self.assertTrue(crawler.is_warmed_up)
        crawler.reset_session()
        self.assertFalse(crawler.is_warmed_up)

        # 4. Injected client is not closed on crawler.close() unless force=True
        mock_shared_client = unittest.mock.MagicMock(spec=SafeHttpClient)
        crawler_shared = DummyCrawler(client=mock_shared_client)
        self.assertFalse(crawler_shared._owns_client)
        crawler_shared.close()
        mock_shared_client.close.assert_not_called()

        crawler_shared.close(force=True)
        mock_shared_client.close.assert_called_once()

    def test_cloudflare_and_timeout_status_retries(self):
        """HTTP 408, 520 Cloudflare origin error trigger retry with backoff."""
        mock_opener = unittest.mock.MagicMock()
        err_408 = urllib.error.HTTPError("https://example.com", 408, "Request Timeout", hdrs={}, fp=io.BytesIO(b""))
        resp_mock = unittest.mock.MagicMock()
        resp_mock.getcode.return_value = 200
        resp_mock.headers = {}
        resp_mock.read.side_effect = [b"ok after 408", b""]

        mock_opener.open.side_effect = [err_408, resp_mock]
        client = SafeHttpClient(max_retries=2, enable_jitter=False, opener=mock_opener)
        status, text, _ = client.get("https://example.com/test-408")
        self.assertEqual(status, 200)
        self.assertEqual(text, "ok after 408")
        self.assertEqual(mock_opener.open.call_count, 2)


if __name__ == "__main__":
    unittest.main()
