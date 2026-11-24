#!/usr/bin/env python3
"""Targeted regression tests for 2026-11-25 utils/*.py, run_tracker.py, and run_scraper.py audit."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock

import run_scraper
import run_tracker
from utils.http_client import SafeHttpClient, clean_html_text
from utils.json_writer import _safe_float, format_daily_report_payload


class TestHttpClientHardening20261125(unittest.TestCase):
    """Regression tests for ReDoS prevention, HTTP method validation, backoff caps, and headers."""

    def test_clean_html_text_no_redos_on_unclosed_comments_or_tags(self) -> None:
        """Unclosed '<!--' or '<' sequences must complete in linear time without quadratic backtracking."""
        payload_comments = "<!--" * 20000 + " hello"
        payload_tags = "<" * 20000 + " world"

        t0 = time.monotonic()
        res_comments = clean_html_text(payload_comments)
        elapsed_comments = time.monotonic() - t0

        t1 = time.monotonic()
        res_tags = clean_html_text(payload_tags)
        elapsed_tags = time.monotonic() - t1

        self.assertLess(elapsed_comments, 0.5)
        self.assertLess(elapsed_tags, 0.5)
        self.assertIn("hello", res_comments)
        self.assertIn("world", res_tags)

        # Valid closed comments/tags still stripped properly even when followed by unclosed markers
        mixed = "<!-- hidden --><p>visible</p><!--" + "<!--" * 5000
        self.assertEqual(clean_html_text(mixed), "visible\n" + "<!--" * 5001)

    def test_request_rejects_crlf_and_invalid_http_methods(self) -> None:
        """HTTP methods containing CRLF, whitespace, or non-token characters must be rejected immediately."""
        mock_opener = MagicMock()
        client = SafeHttpClient(enable_jitter=False, enable_cache=False, max_retries=3, opener=mock_opener)

        for bad_method in ("GET\r\nX-Injected: evil", "POST / HTTP/1.1", "GET\x00", "123"):
            status, text, raw = client.request("https://example.com/api", method=bad_method)
            self.assertEqual((status, text, raw), (0, "", b""))
        mock_opener.open.assert_not_called()

    def test_request_deduplicates_case_insensitive_referer_header(self) -> None:
        """Explicit referer arg replaces lowercase referer from default_headers without duplicating."""
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
            default_headers={"referer": "https://old.example.com/"},
            opener=CapturingOpener(),
        )
        status, _, _ = client.get("https://example.com/page", referer="https://new.example.com/")
        self.assertEqual(status, 200)
        referer_keys = [k for k in captured_headers if k.lower() == "referer"]
        self.assertEqual(len(referer_keys), 1)
        self.assertEqual(captured_headers[referer_keys[0]], "https://new.example.com/")

    def test_calc_backoff_caps_huge_and_non_finite_retry_after_without_jitter(self) -> None:
        """_calc_backoff must cap huge retry_after and ignore NaN/Inf/bool even when enable_jitter=False."""
        client = SafeHttpClient(enable_jitter=False, enable_cache=False, max_backoff=30.0)

        self.assertEqual(client._calc_backoff(1, retry_after=12.5), 12.5)
        self.assertEqual(client._calc_backoff(1, retry_after=999999.0), 60.0)

        b_inf = client._calc_backoff(1, retry_after=float("inf"))
        b_nan = client._calc_backoff(1, retry_after=float("nan"))
        b_bool = client._calc_backoff(1, retry_after=True)  # type: ignore[arg-type]
        for b in (b_inf, b_nan, b_bool):
            self.assertTrue(math.isfinite(b))
            self.assertLessEqual(b, client.max_backoff)

    def test_parse_retry_after_case_insensitive_ratelimit_reset(self) -> None:
        """_parse_retry_after handles mixed-case X-Ratelimit-Reset on plain dict headers."""
        client = SafeHttpClient(enable_jitter=False, enable_cache=False)

        class DummyHE:
            headers = {"X-Ratelimit-Reset": str(time.time() + 10.0)}

        parsed = client._parse_retry_after(DummyHE())  # type: ignore[arg-type]
        self.assertIsNotNone(parsed)
        self.assertGreater(parsed, 0.0)
        self.assertLessEqual(parsed, 60.0)

    def test_set_cached_response_handles_none_raw_bytes(self) -> None:
        """set_cached_response accepts None raw_bytes without raising TypeError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            client = SafeHttpClient(cache_dir=tmp_dir, enable_jitter=False)
            client.set_cached_response("https://example.com/none-raw", 200, "hello", None)  # type: ignore[arg-type]
            cached = client.get_cached_response("https://example.com/none-raw")
            self.assertIsNotNone(cached)
            self.assertEqual(cached[0], 200)
            self.assertEqual(cached[1], "hello")


class TestJsonWriterAndRunners20261125(unittest.TestCase):
    """Regression tests for -0.0 JSON normalization and runner Path/None handling."""

    def test_safe_float_and_payload_normalize_negative_zero(self) -> None:
        """_safe_float and format_daily_report_payload normalize -0.0 to positive +0.0."""
        self.assertFalse(math.copysign(1.0, _safe_float(-0.0)) < 0)
        self.assertFalse(math.copysign(1.0, _safe_float("-0.0")) < 0)
        self.assertFalse(math.copysign(1.0, _safe_float("invalid", default=-0.0)) < 0)

        payload = format_daily_report_payload(
            [{"id": "r1", "negativity_score": -0.0, "severity_index": -0.0}]
        )
        serialized = json.dumps(payload.to_dict())
        self.assertNotIn("-0.0", serialized)

    def test_run_scraper_accepts_path_object_output_path(self) -> None:
        """ScraperPipeline.run accepts pathlib.Path for output_path without AttributeError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_path = Path(tmp_dir) / "daily_reports.json"
            with run_scraper.ScraperPipeline(enable_cache=False, cache_fallback=False) as pipeline:
                pipeline.harvest = MagicMock(return_value=([], {"bobaedream": 0, "dcinside": 0}))
                summary = pipeline.run(output_path=out_path, dry_run=True)  # type: ignore[arg-type]
            self.assertEqual(summary["target_paths"], [os.path.abspath(str(out_path))])

    def test_run_tracker_validate_defect_reports_handles_none_and_whitespace_dirs(self) -> None:
        """validate_defect_reports_file returns False on None; sync_defect_reports strips dir whitespace."""
        self.assertFalse(run_tracker.validate_defect_reports_file(None))  # type: ignore[arg-type]
        self.assertFalse(run_tracker.validate_defect_reports_file(""))

        with tempfile.TemporaryDirectory() as tmp_dir:
            root_d = Path(tmp_dir) / "root_d"
            web_d = Path(tmp_dir) / "web_d"
            root_d.mkdir()
            web_d.mkdir()
            (root_d / "daily_reports.json").write_text(
                json.dumps({"reports": [{"id": "1"}]}),
                encoding="utf-8",
            )
            written = run_tracker.sync_defect_reports(
                web_dir=f"  {web_d}  ",  # type: ignore[arg-type]
                root_dir=f"  {root_d}  ",
            )
            self.assertTrue((web_d / "daily_reports.json").is_file())
            self.assertTrue(any(Path(p) == web_d / "daily_reports.json" for p in written))


if __name__ == "__main__":
    unittest.main()
