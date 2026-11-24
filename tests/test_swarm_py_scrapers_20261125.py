"""Targeted regression tests for scrapers/ edge-case & security hardening (2026-11-25)."""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scrapers.blind_scraper import BlindScraper
from scrapers.bobaedream_scraper import BobaedreamScraper
from scrapers.cafe_forum_miner import CafeForumMiner
from scrapers.common_utils import (
    ComplaintRecord,
    SafeHttpClient,
    extract_defect_topic,
    extract_slang_terms,
    get_random_headers,
    is_allowed_domain_url,
    is_safe_url,
    load_complaints_json,
    polite_delay,
    safe_non_negative_int,
    save_complaints_json,
)
from scrapers.dcinside_scraper import DCInsideScraper


class TestCommonUtilsEdgeCasesAndSecurity(unittest.TestCase):
    """Verify edge-case safety, JSON compliance, and header/URL sanitization in common_utils."""

    def test_polite_delay_and_sleep_polite_non_finite_and_negative_bounds(self) -> None:
        with patch("scrapers.common_utils.time.sleep") as mock_sleep:
            polite_delay(None, None)  # type: ignore[arg-type]
            polite_delay(float("nan"), float("inf"))
            polite_delay(-5.0, -0.0)
            polite_delay(True, False)  # type: ignore[arg-type]
            mock_sleep.assert_not_called()

            polite_delay(0.05, 0.01)  # swapped order must still work
            mock_sleep.assert_called_once()

        for cls in (BlindScraper, BobaedreamScraper, CafeForumMiner, DCInsideScraper):
            scraper = cls(client=SafeHttpClient(min_delay=0.0, max_delay=0.0))
            scraper.min_delay = -1.0
            scraper.max_delay = float("inf")
            with patch("scrapers.common_utils.time.sleep") as mock_sleep:
                scraper.sleep_polite()
                mock_sleep.assert_not_called()
            scraper.close(force=True)

    def test_clock_skew_negative_elapsed_does_not_inflate_jitter_sleep(self) -> None:
        client = SafeHttpClient(min_delay=0.1, max_delay=0.2, enable_cache=False)
        client.last_request_time = time.time() + 1000.0  # simulated future clock skew
        with patch("scrapers.common_utils.time.sleep") as mock_sleep:
            client._sleep_with_jitter()
            mock_sleep.assert_called_once()
            slept = mock_sleep.call_args[0][0]
            self.assertLessEqual(slept, 0.2)
            self.assertGreaterEqual(slept, 0.1)
        client.close()

    def test_header_crlf_sanitization_in_headers_and_client(self) -> None:
        headers = get_random_headers(referer="https://example.com/\r\nX-Evil: 1\x00")
        self.assertNotIn("\r", headers["Referer"])
        self.assertNotIn("\n", headers["Referer"])
        self.assertNotIn("\x00", headers["Referer"])

        recorded_headers = {}

        class MockOpener:
            def open(self, req, timeout=15.0):
                recorded_headers.update(dict(req.header_items()))
                resp = MagicMock()
                resp.getcode.return_value = 200
                resp.headers = {"Content-Type": "text/html; charset=utf-8"}
                resp.read.side_effect = [b"ok", b""]
                return resp

        client = SafeHttpClient(min_delay=0.0, max_delay=0.0, enable_cache=False, opener=MockOpener())
        status, _, _ = client.request(
            "https://example.com/test",
            headers={"X-Custom": "val\r\nInjected: bad\x00", "X-Skip": None},  # type: ignore[dict-item]
        )
        self.assertEqual(status, 200)
        self.assertEqual(recorded_headers.get("X-custom"), "valInjected: bad")
        self.assertNotIn("X-skip", recorded_headers)
        client.close()

    def test_is_safe_url_invalid_port_rejected_even_with_allow_private_ips(self) -> None:
        safe, reason = is_safe_url("http://127.0.0.1:99999/api", allow_private_ips=True)
        self.assertFalse(safe)
        self.assertIn("Invalid port", reason)

    def test_save_and_load_complaints_json_sanitizes_nan_inf_and_invalid_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, "out.json")
            payload = [
                {
                    "id": "T1",
                    "score": float("nan"),
                    "inf": float("inf"),
                    "neg_zero": -0.0,
                    "nested": {"x": float("-inf")},
                }
            ]
            save_complaints_json(payload, out_path)
            with open(out_path, "r", encoding="utf-8") as f:
                raw_text = f.read()
            self.assertNotIn("NaN", raw_text)
            self.assertNotIn("Infinity", raw_text)
            loaded = load_complaints_json(out_path)
            self.assertEqual(len(loaded), 1)
            self.assertIsNone(loaded[0]["score"])
            self.assertIsNone(loaded[0]["inf"])
            self.assertFalse(math.copysign(1.0, loaded[0]["neg_zero"]) < 0)
            self.assertIsNone(loaded[0]["nested"]["x"])

        # Null byte / non-string paths must return [] instead of raising ValueError/TypeError
        self.assertEqual(load_complaints_json("bad\x00path.json"), [])
        self.assertEqual(load_complaints_json(12345), [])  # type: ignore[arg-type]

    def test_extract_slang_extract_defect_topic_and_validate_edge_cases(self) -> None:
        # Empty slang key must not match every string; non-string text must not crash
        self.assertEqual(extract_slang_terms("일반 문장", {"": {}, "황천길": {}}), [])
        self.assertEqual(extract_slang_terms(None, {"황천길": {}}), [])  # type: ignore[arg-type]
        self.assertEqual(extract_slang_terms("테스트", 123), [])  # type: ignore[arg-type]
        self.assertIsInstance(extract_defect_topic("parking", None), str)  # type: ignore[arg-type]

        rec = ComplaintRecord(
            id="ID1",
            platform="blind",
            board_name="블라인드",
            post_url="https://www.teamblind.com/kr/post/1",
            post_title="제목",
            target_vehicle="BYD Atto 3",
            category="parking",
            defect_topic="주차",
            raw_quote=12345,  # type: ignore[arg-type]
        )
        valid, errors = rec.validate()
        self.assertFalse(valid)
        self.assertTrue(any("raw_quote" in e for e in errors))

    def test_safe_non_negative_int_and_domain_check_and_surrogate_cache_key(self) -> None:
        self.assertEqual(safe_non_negative_int("1,234"), 1234)
        self.assertEqual(safe_non_negative_int(True), 0)
        self.assertEqual(safe_non_negative_int(float("nan")), 0)
        self.assertEqual(safe_non_negative_int(float("inf")), 0)
        self.assertEqual(safe_non_negative_int(-5), 0)

        self.assertTrue(is_allowed_domain_url("https://www.bobaedream.co.kr/view?No=1", ("bobaedream.co.kr",)))
        self.assertFalse(is_allowed_domain_url("https://evil-bobaedream.co.kr/view?No=1", ("bobaedream.co.kr",)))

        client = SafeHttpClient(min_delay=0.0, max_delay=0.0, enable_cache=False)
        key = client._cache_key("https://example.com/\ud800")
        self.assertEqual(len(key), 64)
        client.close()


class TestScrapersDomainIsolationAndMetadataParsing(unittest.TestCase):
    """Verify off-domain link rejection, metadata isolation, and dangerous URL scheme checks."""

    def test_blind_rejects_off_domain_slug_and_normalizes_nan_counts(self) -> None:
        scraper = BlindScraper(client=SafeHttpClient(min_delay=0.0, max_delay=0.0))
        feed_html = """
        <script id="__NEXT_DATA__" type="application/json">
        {"props":{"pageProps":{"articles":[
          {"id":"1","title":"피싱 링크","slug":"https://evil.com/phish"},
          {"id":"2","title":"프로토콜 상대 피싱","slug":"//evil.com/phish"},
          {"id":"3","title":"정상 글","slug":"atto3-review"}
        ]}}}
        </script>
        """
        items = scraper.parse_topic_feed(feed_html)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["post_id"], "3")
        self.assertTrue(items[0]["url"].startswith("https://www.teamblind.com/"))

        detail_html = """
        <script id="__NEXT_DATA__" type="application/json">
        {"props":{"pageProps":{"article":{"title":"아토3 후기","body":"본문입니다.","view_count":NaN,"like_count":"1,050"}}}}
        </script>
        """
        detail = scraper.parse_post_detail(detail_html, "https://www.teamblind.com/kr/post/3")
        self.assertEqual(detail["view_count"], 0)
        self.assertEqual(detail["upvote_count"], 1050)
        scraper.close(force=True)

    def test_bobaedream_rejects_off_domain_links_and_title_count_collisions(self) -> None:
        scraper = BobaedreamScraper(client=SafeHttpClient(min_delay=0.0, max_delay=0.0))
        list_html = """
        <a href="https://evil.com/view?code=electric&No=1">악성 외부 링크 제목</a>
        <a href="/view?code=electric&No=2">정상 보배드림 게시글</a>
        """
        items = scraper.parse_board_list(list_html, "electric")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["post_no"], "2")

        search_html = """
        <dl>
          <dt><a href="https://evil.com/view?code=electric&No=9">악성 검색 링크</a></dt>
          <dt><a href="https://www.bobaedream.co.kr/view?code=electric&No=10">정상 검색 링크</a></dt>
        </dl>
        """
        s_items = scraper.parse_search_results(search_html)
        self.assertEqual(len(s_items), 1)
        self.assertEqual(s_items[0]["post_no"], "10")

        detail_html = """
        <html><body>
          <strong class="title">조회 9999 추천 8888 아토3 시승기</strong>
          <span class="countGroup">2026.11.25 04:00 | 조회 <em>42</em> | 추천 <span>7</span></span>
          <!-- <div class="bodyCont">주석 가짜 본문</div> -->
          <div class="bodyCont">실제 본문 내용입니다.</div>
        </body></html>
        """
        detail = scraper.parse_post_detail(detail_html, "https://www.bobaedream.co.kr/view?code=electric&No=10")
        self.assertEqual(detail["view_count"], 42)
        self.assertEqual(detail["upvote_count"], 7)
        self.assertEqual(detail["body"], "실제 본문 내용입니다.")
        scraper.close(force=True)

    def test_dcinside_rejects_off_domain_links_dedups_and_ignores_commented_body(self) -> None:
        scraper = DCInsideScraper(client=SafeHttpClient(min_delay=0.0, max_delay=0.0))
        list_html = """
        <table>
          <tr data-no="101" class="ub-content"><td class="gall_tit"><a href="https://evil.com/board/view/?id=ev&no=101">외부 피싱</a></td></tr>
          <tr data-no="102" class="ub-content"><td class="gall_tit"><a href="/mgallery/board/view/?id=ev&no=102">정상 글 1</a></td></tr>
          <tr data-no="102" class="ub-content"><td class="gall_tit"><a href="/mgallery/board/view/?id=ev&no=102">중복 글 1</a></td></tr>
        </table>
        """
        items = scraper.parse_gallery_list(list_html, "ev")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["post_id"], "102")

        detail_html = """
        <html><body>
          <!-- <div class="writing_view_box">주석 본문</div> -->
          <div class="writing_view_box">진짜 본문 내용입니다.</div>
        </body></html>
        """
        detail = scraper.parse_post_detail(detail_html, "https://gall.dcinside.com/mgallery/board/view/?id=ev&no=102", "ev", "102")
        self.assertEqual(detail["body"], "진짜 본문 내용입니다.")
        scraper.close(force=True)

    def test_cafe_forum_miner_rejects_javascript_post_url_and_surrogate_safe_id(self) -> None:
        miner = CafeForumMiner(client=SafeHttpClient(min_delay=0.0, max_delay=0.0))
        bad_rec = miner.normalize_record({
            "platform": "naver_cafe",
            "post_url": "javascript:alert(1)",
            "raw_quote": "충전 중 튕김 현상이 반복적으로 발생하고 있습니다.",
            "category": "charging",
        })
        self.assertIsNone(bad_rec)

        surrogate_rec = miner.normalize_record({
            "platform": "naver_cafe",
            "post_url": "https://cafe.naver.com/ev/1",
            "raw_quote": "충전 중 튕김 현상이 발생합니다 \ud800",
            "category": "charging",
        })
        self.assertIsNotNone(surrogate_rec)
        self.assertTrue(surrogate_rec.id.startswith("CASE_CHAR_"))
        miner.close(force=True)


if __name__ == "__main__":
    unittest.main()
