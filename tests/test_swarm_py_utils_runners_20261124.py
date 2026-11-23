#!/usr/bin/env python3
"""Targeted regression tests for 2026-11-24 utils/*.py, run_tracker.py, and run_scraper.py audit."""

from __future__ import annotations

import datetime
import http.client
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import urllib.request

import run_scraper
import run_tracker
from utils.http_client import (
    CircuitBreaker,
    ResilientHTTPSConnection,
    SafeHttpClient,
    SafeRedirectHandler,
    is_safe_url,
)
from utils.json_writer import (
    format_daily_report_payload,
    read_daily_reports,
)


class TestHttpClientSecurityHardening20261124(unittest.TestCase):
    """Tests for IDNA SSRF, proxy tunnel port checks, redirect downgrade, headers, and cache safety."""

    def test_is_safe_url_blocks_unicode_idna_ssrf_bypasses(self) -> None:
        """Fullwidth / Unicode IDNA representations of localhost or 127.0.0.1 must be blocked."""
        bypass_urls = [
            "http://ｌｏｃａｌｈｏｓｔ/admin",
            "http://１２７．０．０．１/secrets",
            "http://127.0.0.1\u3002/status",
            "http://app.\uff4c\uff4f\uff43\uff41\uff4c\uff48\uff4f\uff53\uff54/",
        ]
        for bad_url in bypass_urls:
            safe, reason = is_safe_url(bad_url)
            self.assertFalse(safe, f"Unicode IDNA SSRF URL should be blocked: {bad_url}")
            self.assertIn("SSRF blocked", reason)

        # Valid public IDN domain should still be allowed when DNS is offline/unresolvable
        with patch("utils.http_client.socket.getaddrinfo", side_effect=OSError("offline")):
            safe_idn, _ = is_safe_url("https://한국어.example.com/news")
            self.assertTrue(safe_idn)

    def test_https_tunnel_validates_tunnel_port_and_ipv6(self) -> None:
        """ResilientHTTPSConnection must block CONNECT tunnels to disallowed ports or unsafe IPv6 hosts."""
        conn_bad_port = ResilientHTTPSConnection(
            "proxy.example.com",
            443,
            allow_private_ips=False,
        )
        conn_bad_port.set_tunnel("public.example.com", 6379)
        with self.assertRaises(OSError) as ctx_port:
            conn_bad_port.connect()
        self.assertIn("SSRF blocked", str(ctx_port.exception))
        self.assertIn("6379", str(ctx_port.exception))

        conn_bad_v6 = ResilientHTTPSConnection(
            "proxy.example.com",
            443,
            allow_private_ips=False,
        )
        conn_bad_v6.set_tunnel("::1", 443)
        with self.assertRaises(OSError) as ctx_v6:
            conn_bad_v6.connect()
        self.assertIn("SSRF blocked", str(ctx_v6.exception))

    def test_connect_time_ssrf_error_aborts_immediately_without_retry_or_cache(self) -> None:
        """Connect-time SSRF OSError/URLError must abort on attempt 1 without retrying or returning cache."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            client = SafeHttpClient(
                max_retries=3,
                enable_jitter=False,
                enable_cache=True,
                cache_fallback=True,
                cache_dir=tmp_dir,
            )
            url = "https://rebind.example.com/secret"
            client.set_cached_response(url, 200, "cached-body", b"cached-body")

            mock_opener = MagicMock()
            mock_opener.open.side_effect = urllib.error.URLError(
                OSError("SSRF blocked: Domain 'rebind.example.com' resolved to unsafe IP 127.0.0.1")
            )
            client.opener = mock_opener

            with patch("utils.http_client.socket.getaddrinfo", side_effect=OSError("offline")):
                status, text, raw = client.get(url)

            self.assertEqual(status, 0)
            self.assertEqual(text, "")
            self.assertEqual(raw, b"")
            self.assertEqual(mock_opener.open.call_count, 1)

    def test_redirect_handler_strips_referer_on_https_downgrade(self) -> None:
        """HTTPS -> HTTP redirects must strip Referer header to avoid leaking HTTPS URLs."""
        handler = SafeRedirectHandler(allow_private_ips=False)
        req = urllib.request.Request(
            "https://example.com/private?token=secret",
            headers={"Referer": "https://example.com/origin", "User-Agent": "TestUA"},
        )
        new_req = handler.redirect_request(
            req, None, 302, "Found", {}, "http://example.com/public"
        )
        self.assertIsNotNone(new_req)
        hdr_keys_lower = {k.lower() for k in new_req.headers}
        unredir_keys_lower = {k.lower() for k in getattr(new_req, "unredirected_hdrs", {})}
        self.assertNotIn("referer", hdr_keys_lower)
        self.assertNotIn("referer", unredir_keys_lower)

    def test_incomplete_read_salvage_does_not_poison_cache(self) -> None:
        """Final-attempt IncompleteRead returns salvaged partial bytes but must not write to cache."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            resp_mock = MagicMock()
            resp_mock.getcode.return_value = 200
            resp_mock.headers = {"Content-Type": "text/html; charset=utf-8"}
            resp_mock.read.side_effect = http.client.IncompleteRead(b"<html>partial", 100)

            mock_opener = MagicMock()
            mock_opener.open.return_value = resp_mock

            client = SafeHttpClient(
                max_retries=1,
                enable_jitter=False,
                enable_cache=True,
                cache_dir=tmp_dir,
                opener=mock_opener,
            )
            url = "https://example.com/truncated"
            status, text, raw = client.get(url)
            self.assertEqual(status, 200)
            self.assertEqual(text, "<html>partial")
            self.assertEqual(raw, b"<html>partial")
            self.assertIsNone(client.get_cached_response(url))

    def test_request_sanitizes_crlf_and_none_headers(self) -> None:
        """Header values containing CRLF/null bytes are stripped and None headers are skipped."""
        captured_headers = {}

        class CapturingOpener:
            def open(self, req, timeout=15.0):
                captured_headers.update(dict(req.header_items()))
                resp = MagicMock()
                resp.getcode.return_value = 200
                resp.headers = {}
                resp.read.side_effect = [b"ok", b""]
                return resp

        client = SafeHttpClient(
            enable_jitter=False,
            enable_cache=False,
            opener=CapturingOpener(),
        )
        status, _, _ = client.get(
            "https://example.com/headers",
            referer="https://example.com/\r\nX-Injected: evil",
            headers={
                "X-Test": "val\r\nInjected: 1\x00",
                "X-Empty": None,  # type: ignore[dict-item]
            },
        )
        self.assertEqual(status, 200)
        self.assertNotIn("X-empty", captured_headers)
        self.assertEqual(captured_headers["X-test"], "valInjected: 1")
        self.assertNotIn("\r", captured_headers["Referer"])
        self.assertNotIn("\n", captured_headers["Referer"])

    def test_circuit_breaker_bare_ipv6_and_bool_retry_after(self) -> None:
        """CircuitBreaker handles bare IPv6 literals and ignores bool retry_after."""
        cb = CircuitBreaker(failure_threshold=1, cooldown_seconds=0.05)
        self.assertEqual(cb._extract_host("::1"), "::1")
        cb.record_failure("::1", status_code=503, retry_after=True)  # type: ignore[arg-type]
        self.assertTrue(cb.is_open("::1"))


class TestJsonWriterAndRunnersHardening20261124(unittest.TestCase):
    """Tests for json_writer, run_scraper, and run_tracker hardening."""

    def test_read_daily_reports_handles_null_byte_path_safely(self) -> None:
        """read_daily_reports returns empty payload rather than crashing on null-byte paths."""
        res = read_daily_reports("bad\x00path.json", quarantine_corrupted=False)
        self.assertEqual(res, {"reports": [], "statistics": {}})

    def test_format_daily_report_payload_normalizes_blank_generated_at(self) -> None:
        """Blank generated_at defaults to a non-empty UTC ISO-8601 timestamp."""
        payload = format_daily_report_payload([], generated_at="   ")
        self.assertTrue(payload.generated_at)
        self.assertIn("T", payload.generated_at)

    def test_run_scraper_save_harvest_cache_sanitizes_nan_and_datetime(self) -> None:
        """_save_harvest_cache sanitizes NaN/Inf/datetime values without failing JSON serialization."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            pipeline = run_scraper.ScraperPipeline(
                bobae_crawler=MagicMock(),
                dc_crawler=MagicMock(),
                defect_filter=MagicMock(),
                enable_cache=True,
                cache_dir=tmp_dir,
            )
            posts = [
                {
                    "id": "p1",
                    "score": float("nan"),
                    "inf_val": float("inf"),
                    "created_at": datetime.datetime(2026, 11, 24, 1, 0, tzinfo=datetime.timezone.utc),
                }
            ]
            pipeline._save_harvest_cache(posts)
            loaded = pipeline._load_harvest_cache()
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["id"], "p1")
            self.assertEqual(loaded[0]["score"], 0.0)
            self.assertEqual(loaded[0]["inf_val"], 0.0)
            self.assertTrue(str(loaded[0]["created_at"]).startswith("2026-11-24"))

    def test_run_scraper_atomic_copy_file_rejects_directory_target(self) -> None:
        """_atomic_copy_file raises IsADirectoryError when dest_path is an existing directory."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            src = Path(tmp_dir) / "src.json"
            src.write_text('{"reports": []}', encoding="utf-8")
            dest_dir = Path(tmp_dir) / "existing_dir"
            dest_dir.mkdir()
            with self.assertRaises(IsADirectoryError):
                run_scraper._atomic_copy_file(src, dest_dir)

    def test_run_scraper_zero_defects_prefers_rich_mirror_over_empty_shell(self) -> None:
        """When 0 defects are scraped, an invalid target must be healed from a populated mirror, not an empty one."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            empty_mirror = root / "empty_mirror.json"
            empty_mirror.write_text(json.dumps({"reports": []}), encoding="utf-8")

            rich_mirror = root / "rich_mirror.json"
            rich_mirror.write_text(
                json.dumps({"reports": [{"id": "r1", "title": "ICCU fault"}]}),
                encoding="utf-8",
            )

            corrupt_target = root / "corrupt_target.json"
            corrupt_target.write_text("{corrupt", encoding="utf-8")

            with run_scraper.ScraperPipeline(cache_fallback=False) as pipeline:
                pipeline.harvest = MagicMock(return_value=([], {"bobaedream": 0, "dcinside": 0}))
                with patch("run_scraper._resolve_web_reports_path", return_value=empty_mirror), \
                     patch("run_scraper._resolve_root_reports_path", return_value=rich_mirror), \
                     patch("run_scraper._resolve_public_reports_path", return_value=empty_mirror):
                    pipeline.run(output_path=str(corrupt_target), dry_run=False)

            healed = json.loads(corrupt_target.read_text(encoding="utf-8"))
            self.assertEqual(len(healed["reports"]), 1)
            self.assertEqual(healed["reports"][0]["id"], "r1")

    def test_run_tracker_json_format_sanitizes_nan_and_closes_crawler(self) -> None:
        """run_tracker --format json sanitizes NaN floats and sync_defect_reports closes ScraperPipeline."""
        mock_payload = MagicMock()
        mock_payload.regions = [MagicMock()] * 17
        mock_payload.to_dict.return_value = {
            "nationwide_summary": {"depletion_rate": float("nan")},
            "regions": [],
        }

        buf = io.StringIO()
        with patch.object(run_tracker.SubsidyTracker, "execute_tracking_cycle", return_value=(mock_payload, False)), \
             patch("sys.stdout", buf):
            exit_code = run_tracker.main(["--dry-run", "--format", "json"])

        self.assertEqual(exit_code, 0)
        parsed = json.loads(buf.getvalue())
        self.assertEqual(parsed["nationwide_summary"]["depletion_rate"], 0.0)

        with tempfile.TemporaryDirectory() as tmp_dir:
            root_d = Path(tmp_dir) / "root_data"
            web_d = Path(tmp_dir) / "web_data"
            root_d.mkdir()
            web_d.mkdir()
            (root_d / "daily_reports.json").write_text('{"reports": []}', encoding="utf-8")

            mock_pipeline = MagicMock()
            mock_pipeline.__enter__.return_value = mock_pipeline
            mock_pipeline.run.return_value = {"written_paths": []}
            with patch("run_scraper.ScraperPipeline", return_value=mock_pipeline):
                run_tracker.sync_defect_reports(
                    web_dir=web_d,
                    root_dir=root_d,
                    run_crawler=True,
                )
            mock_pipeline.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
