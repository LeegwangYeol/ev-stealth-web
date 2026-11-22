#!/usr/bin/env python3
"""Targeted regression tests for utils/*.py, run_tracker.py, and run_scraper.py."""

from __future__ import annotations

from datetime import datetime
import http.cookiejar
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock
import urllib.request

import run_scraper
import run_tracker
from utils.http_client import (
    CircuitBreaker,
    SafeHttpClient,
    SafeRedirectHandler,
    is_safe_url,
)
from utils.json_writer import (
    _extract_record_date,
    read_daily_reports,
    write_daily_reports,
)


class TestUtilsHttpClientHardening(unittest.TestCase):
    """Tests for SSRF, redirect credential stripping, cache bounds, and client edge cases."""

    def test_is_safe_url_enforces_allowed_ports_for_implicit_default_ports(self) -> None:
        """Implicit ports 80/443 must be checked against custom allowed_ports."""
        safe, reason = is_safe_url("https://example.com/api", allowed_ports={8443})
        self.assertFalse(safe)
        self.assertIn("Disallowed port 443", reason)

        safe_http, reason_http = is_safe_url("http://example.com/api", allowed_ports={8080})
        self.assertFalse(safe_http)
        self.assertIn("Disallowed port 80", reason_http)

        safe_ok, _ = is_safe_url("https://example.com:8443/api", allowed_ports={8443})
        self.assertTrue(safe_ok)

    def test_safe_redirect_handler_strips_sensitive_headers_cross_origin(self) -> None:
        """Cross-origin redirects strip Authorization, Proxy-Authorization, and Cookie headers."""
        handler = SafeRedirectHandler(allow_private_ips=False)
        req = urllib.request.Request(
            "https://example.com/start",
            headers={
                "Authorization": "Bearer secret",
                "Proxy-Authorization": "Basic abc",
                "Cookie": "sid=123",
                "User-Agent": "CustomUA",
            },
        )
        new_req = handler.redirect_request(
            req, None, 302, "Found", {}, "https://other.example.org/dest"
        )
        self.assertIsNotNone(new_req)
        hdr_keys_lower = {k.lower() for k in new_req.headers}
        unredir_keys_lower = {k.lower() for k in getattr(new_req, "unredirected_hdrs", {})}
        for sensitive in ("authorization", "proxy-authorization", "cookie"):
            self.assertNotIn(sensitive, hdr_keys_lower)
            self.assertNotIn(sensitive, unredir_keys_lower)
        self.assertEqual(new_req.get_header("User-agent"), "CustomUA")

    def test_safe_redirect_handler_keeps_headers_same_origin(self) -> None:
        """Same-origin redirects preserve Authorization and Cookie headers."""
        handler = SafeRedirectHandler(allow_private_ips=False)
        req = urllib.request.Request(
            "https://example.com/start",
            headers={"Authorization": "Bearer secret", "Cookie": "sid=123"},
        )
        new_req = handler.redirect_request(
            req, None, 302, "Found", {}, "https://example.com/next"
        )
        self.assertIsNotNone(new_req)
        self.assertEqual(new_req.get_header("Authorization"), "Bearer secret")
        self.assertEqual(new_req.get_header("Cookie"), "sid=123")

    def test_memory_cache_bounded_on_disk_load_and_write(self) -> None:
        """In-memory cache remains bounded at 500 entries even when loading >500 items from disk."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            client = SafeHttpClient(cache_dir=tmp_dir, enable_jitter=False)
            for i in range(520):
                client.set_cached_response(f"https://example.com/p/{i}", 200, f"body-{i}", f"body-{i}".encode())
            self.assertLessEqual(len(client._memory_cache), 500)

            client2 = SafeHttpClient(cache_dir=tmp_dir, enable_jitter=False)
            for i in range(520):
                res = client2.get_cached_response(f"https://example.com/p/{i}")
                self.assertIsNotNone(res)
            self.assertLessEqual(len(client2._memory_cache), 500)

    def test_post_dict_respects_lowercase_content_type_header(self) -> None:
        """POST with dict data must not duplicate Content-Type when lowercase content-type is given."""
        client = SafeHttpClient(enable_jitter=False, enable_cache=False)
        captured_headers = {}

        class MockOpener:
            def open(self, req, timeout=15.0):
                captured_headers.update(dict(req.header_items()))
                resp = MagicMock()
                resp.getcode.return_value = 200
                resp.headers = {}
                resp.read.side_effect = [b"ok", b""]
                return resp

        client.opener = MockOpener()
        status, _, _ = client.post(
            "https://example.com/submit",
            data={"a": "1"},
            headers={"content-type": "application/json"},
        )
        self.assertEqual(status, 200)
        ct_keys = [k for k in captured_headers if k.lower() == "content-type"]
        self.assertEqual(len(ct_keys), 1)
        self.assertEqual(captured_headers[ct_keys[0]], "application/json")

    def test_none_status_code_and_large_backoff_do_not_crash(self) -> None:
        """None status_code in HALF_OPEN and large attempt numbers in _calc_backoff are handled safely."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.01)
        cb.record_failure("https://example.com.", status_code=503)
        self.assertEqual(cb._extract_host("https://example.com./test"), "example.com")

        client = SafeHttpClient(enable_jitter=False, enable_cache=False)
        self.assertLessEqual(client._calc_backoff(5000), client.max_backoff)

        class NoneStatusOpener:
            def open(self, req, timeout=15.0):
                resp = MagicMock()
                resp.getcode.return_value = None
                resp.headers = {}
                resp.read.side_effect = [b"ok", b""]
                return resp

        client.opener = NoneStatusOpener()
        status, text, _ = client.get("https://example.com/none-status")
        self.assertIsNone(status)
        self.assertEqual(text, "ok")

    def test_clear_cookies_syncs_processor_on_replacement(self) -> None:
        """If cookie_jar lacks clear(), replacement jar is synced onto HTTPCookieProcessor."""
        client = SafeHttpClient(enable_jitter=False)
        client.cookie_jar = object()  # type: ignore[assignment]
        client.clear_cookies()
        self.assertIsInstance(client.cookie_jar, http.cookiejar.CookieJar)
        processors = [
            h for h in client.opener.handlers if isinstance(h, urllib.request.HTTPCookieProcessor)
        ]
        self.assertTrue(all(p.cookiejar is client.cookie_jar for p in processors))


class TestUtilsJsonWriterHardening(unittest.TestCase):
    """Tests for json_writer directory guard, NaN quarantine, and date extraction."""

    def test_write_daily_reports_rejects_existing_directory(self) -> None:
        """write_daily_reports raises IsADirectoryError when output_path is a directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(IsADirectoryError):
                write_daily_reports([], output_path=tmp_dir)

    def test_read_daily_reports_rejects_and_quarantines_nan_json(self) -> None:
        """read_daily_reports rejects non-standard NaN JSON and quarantines when requested."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            p = Path(tmp_dir) / "daily_reports.json"
            p.write_text('{"reports": [{"id": "1", "negativity_score": NaN}]}', encoding="utf-8")

            res = read_daily_reports(str(p), quarantine_corrupted=False)
            self.assertEqual(res, {"reports": [], "statistics": {}})

            res_q = read_daily_reports(str(p), quarantine_corrupted=True)
            self.assertEqual(res_q, {"reports": [], "statistics": {}})
            self.assertFalse(p.exists())
            quarantined = list(Path(tmp_dir).glob("daily_reports.corrupt_*"))
            self.assertEqual(len(quarantined), 1)

    def test_extract_record_date_out_of_range_datetime_falls_through_cleanly(self) -> None:
        """Out-of-range datetime in 'date' falls back to valid 'created_at'."""
        rec = {"date": datetime(1800, 1, 1), "created_at": "2026-11-23"}
        self.assertEqual(_extract_record_date(rec), "2026-11-23")


class TestRunnersEdgeCases(unittest.TestCase):
    """Tests for run_tracker.py and run_scraper.py CLI, path, and atomic copy fixes."""

    def test_run_tracker_trailing_slash_nonexistent_dir(self) -> None:
        """--output /path/to/new_dir/ preserves trailing slash and appends ev_subsidy_data.json."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            nonexistent_dir_str = os.path.join(tmp_dir, "new_sub_dir") + "/"
            args = run_tracker.parse_arguments(["--output", nonexistent_dir_str])
            self.assertEqual(args.output, Path(tmp_dir) / "new_sub_dir" / "ev_subsidy_data.json")

    def test_run_tracker_sync_defect_reports_empty_string_args(self) -> None:
        """Empty string web_dir/root_dir do not resolve to '.' in sync_defect_reports."""
        res = run_tracker.sync_defect_reports(web_dir="", root_dir="", dry_run=True)
        self.assertEqual(res, [])

    def test_run_scraper_empty_sources_defaults_to_all(self) -> None:
        """Empty source_choice falls back to all sources rather than scraping 0 sources."""
        pipeline = run_scraper.ScraperPipeline(
            bobae_crawler=MagicMock(),
            dc_crawler=MagicMock(),
            defect_filter=MagicMock(),
            enable_cache=False,
        )
        pipeline.harvest_bobaedream = MagicMock(return_value=[{"id": "b1"}])
        pipeline.harvest_dcinside = MagicMock(return_value=[{"id": "d1"}])
        posts, stats = pipeline.harvest("", limit=5)
        self.assertEqual(len(posts), 2)
        self.assertEqual(stats, {"bobaedream": 1, "dcinside": 1})

    def test_run_scraper_harvest_passes_remaining_limit(self) -> None:
        """harvest_bobaedream and harvest_dcinside request only remaining limit across boards/galleries."""
        bobae = MagicMock()
        bobae.crawl_board.side_effect = [[{"id": f"b{i}"} for i in range(7)], [{"id": "b7"}, {"id": "b8"}, {"id": "b9"}]]
        dc = MagicMock()
        dc.crawl_gallery.side_effect = [[{"id": f"d{i}"} for i in range(6)], [{"id": "d6"}, {"id": "d7"}, {"id": "d8"}, {"id": "d9"}]]

        pipeline = run_scraper.ScraperPipeline(
            bobae_crawler=bobae,
            dc_crawler=dc,
            defect_filter=MagicMock(),
            enable_cache=False,
        )
        b_posts = pipeline.harvest_bobaedream(limit=10)
        d_posts = pipeline.harvest_dcinside(limit=10)
        self.assertEqual(len(b_posts), 10)
        self.assertEqual(len(d_posts), 10)
        self.assertEqual(bobae.crawl_board.call_args_list[0].kwargs["limit"], 10)
        self.assertEqual(bobae.crawl_board.call_args_list[1].kwargs["limit"], 3)
        self.assertEqual(dc.crawl_gallery.call_args_list[0].kwargs["limit"], 10)
        self.assertEqual(dc.crawl_gallery.call_args_list[1].kwargs["limit"], 4)

    def test_run_scraper_atomic_copy_file_with_lock(self) -> None:
        """_atomic_copy_file copies content atomically under FileLock with 0o644 permissions."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            src = Path(tmp_dir) / "src.json"
            dst = Path(tmp_dir) / "dst.json"
            src.write_text('{"reports": []}', encoding="utf-8")
            out = run_scraper._atomic_copy_file(src, dst)
            self.assertEqual(Path(out), dst.resolve())
            self.assertEqual(dst.read_text(encoding="utf-8"), '{"reports": []}')
            self.assertEqual(dst.stat().st_mode & 0o777, 0o644)


if __name__ == "__main__":
    unittest.main()
