#!/usr/bin/env python3
"""Targeted regression tests for 2026-11-26 utils/*.py, scripts/*.py, run_scraper.py, and run_tracker.py audit."""

from __future__ import annotations

import contextlib
from decimal import Decimal
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

WEB_ROOT = Path(__file__).resolve().parent.parent
if str(WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_ROOT))

import run_scraper
import run_tracker
from scripts import build_casebook
from scripts import cross_aggregator
from scripts import domain_tokenizer
from scripts import sync_defect_reports as sync_mod
from utils.http_client import SafeHttpClient
from utils.json_writer import _safe_float, format_daily_report_payload, read_daily_reports


def _assert_positive_zero(test_case: unittest.TestCase, val: float) -> None:
    if val == 0.0:
        test_case.assertFalse(math.copysign(1.0, val) < 0.0, f"Expected +0.0, got {val!r}")


class TestUtilsAndRunners20261126(unittest.TestCase):
    """Regression tests for HTTP header/method validation, json_writer type guards, and runner CLI safety."""

    def test_http_client_rejects_non_string_method_and_invalid_header_names(self) -> None:
        captured_headers = {}

        class CapturingOpener:
            def open(self, req, timeout=15.0):
                captured_headers.update(dict(req.header_items()))
                resp = MagicMock()
                resp.getcode.return_value = 200
                resp.headers = {}
                resp.read.side_effect = [b"ok", b""]
                return resp

        mock_opener = MagicMock()
        client = SafeHttpClient(enable_jitter=False, enable_cache=False, max_retries=2, opener=mock_opener)
        for bad_method in (123, True, ["GET"]):
            res = client.request("https://example.com/test", method=bad_method)  # type: ignore[arg-type]
            self.assertEqual(res, (0, "", b""))
        mock_opener.open.assert_not_called()

        cap_client = SafeHttpClient(
            enable_jitter=False,
            enable_cache=False,
            default_headers={"Bad Header": "drop", "X-Default": "ok\x07\x1f"},
            opener=CapturingOpener(),
        )
        status, _, _ = cap_client.get(
            "https://example.com/test",
            headers={
                "Invalid Name": "value",
                "Bad:Name": "value",
                "X-Clean": "abc\r\n\x00\x0bdef",
            },
        )
        self.assertEqual(status, 200)
        hdr_keys_lower = {k.lower() for k in captured_headers}
        self.assertNotIn("bad header", hdr_keys_lower)
        self.assertNotIn("invalid name", hdr_keys_lower)
        self.assertNotIn("bad:name", hdr_keys_lower)
        self.assertEqual(captured_headers["X-default"], "ok")
        self.assertEqual(captured_headers["X-clean"], "abcdef")

    def test_json_writer_handles_non_pathlike_and_decimal(self) -> None:
        self.assertEqual(read_daily_reports(123), {"reports": [], "statistics": {}})  # type: ignore[arg-type]
        self.assertEqual(read_daily_reports(object()), {"reports": [], "statistics": {}})  # type: ignore[arg-type]
        self.assertEqual(_safe_float(Decimal("0.75")), 0.75)
        self.assertEqual(_safe_float("bad", default=Decimal("NaN")), 0.0)
        payload = format_daily_report_payload([{"id": "d1", "dsi_breakdown": {"safety": Decimal("4.5")}}])
        self.assertEqual(payload.reports[0]["dsi_breakdown"]["safety"], 4.5)

    def test_runners_main_system_exit_none_and_bool_and_whitespace_cache_dir(self) -> None:
        with patch.object(run_scraper, "create_parser") as mock_cp:
            mock_cp.return_value.parse_args.side_effect = SystemExit(None)
            self.assertEqual(run_scraper.main([]), 0)
            mock_cp.return_value.parse_args.side_effect = SystemExit(True)
            self.assertEqual(run_scraper.main([]), 1)

        with patch.object(run_tracker, "parse_arguments", side_effect=SystemExit(None)):
            self.assertEqual(run_tracker.main([]), 0)
        with patch.object(run_tracker, "parse_arguments", side_effect=SystemExit(True)):
            self.assertEqual(run_tracker.main([]), 1)

        with run_scraper.ScraperPipeline(enable_cache=False, cache_fallback=False, cache_dir="   ") as pipeline:
            self.assertIsNone(pipeline._custom_cache_dir)


class TestScriptsAudit20261126(unittest.TestCase):
    """Regression tests for scripts/*.py Markdown link safety, -0.0 normalization, and CLI/input guards."""

    def test_build_casebook_prevents_markdown_link_injection_and_handles_missing_file_in_main(self) -> None:
        safe_url = build_casebook._sanitize_md_url("https://example.com/a[b]c\\d")
        self.assertNotIn("[", safe_url)
        self.assertNotIn("]", safe_url)
        self.assertNotIn("\\", safe_url)
        self.assertIn("%5B", safe_url)
        self.assertIn("%5D", safe_url)

        section = build_casebook.build_case_studies_section(
            "parking",
            "Parking",
            [
                {
                    "id": "1",
                    "platform": "dcinside",
                    "board_name": "board",
                    "post_url": "https://example.com/evil](https://phish.example)",
                    "post_title": "Title",
                    "target_vehicle": "EV6",
                    "category": "parking",
                    "defect_topic": "Topic",
                    "raw_quote": "Quote",
                }
            ],
        )
        self.assertIn("\\](https://phish.example)", section)

        with tempfile.TemporaryDirectory() as td:
            missing_data = Path(td) / "missing.json"
            old_argv = sys.argv
            buf = io.StringIO()
            try:
                sys.argv = ["build_casebook.py", "--data-path", str(missing_data)]
                with contextlib.redirect_stdout(buf):
                    with self.assertRaises(SystemExit) as cm:
                        build_casebook.main()
                self.assertEqual(cm.exception.code, 1)
                self.assertIn("[ERROR] Failed to build casebook", buf.getvalue())
            finally:
                sys.argv = old_argv

    def test_sync_defect_reports_tiny_negative_rounding_and_cli_help(self) -> None:
        norm = sync_mod.normalize_report_item(
            {
                "id": "rep-neg-tiny",
                "source": "bobaedream",
                "title": "Test",
                "dsi_breakdown": {"safety": -0.001},
            }
        )
        _assert_positive_zero(self, norm["dsi_breakdown"]["safety"])

        stats = sync_mod.compute_report_statistics([{"negativity_score": -0.0001}])
        _assert_positive_zero(self, stats["avg_negativity_score"])

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = sync_mod.main(["--help"])
        self.assertEqual(rc, 0)
        self.assertIn("Autonomous Defect Reports Synchronization", buf.getvalue())

    def test_cross_aggregator_strips_whitespace_platform_and_category(self) -> None:
        agg = cross_aggregator.CrossAggregator()
        records = [
            {
                "platform": "  dcinside  ",
                "category": "   ",
                "target_vehicle": "BYD Atto 3",
                "sentiment_tier": "NEGATIVE",
                "dsi_score": 7.0,
            }
        ]
        cont = agg.build_contingency_tables(records)
        # dcinside is index 1, NEGATIVE is index 2
        self.assertEqual(cont["platform_sentiment"]["matrix"][1][2], 1)

        brands = agg.aggregate_by_brand(records)
        self.assertEqual(brands["BYD_Chinese"]["category_breakdown"]["parking"], 1)

        vehs = agg.aggregate_by_vehicle_model(records)
        self.assertEqual(vehs["BYD Atto 3"]["category_breakdown"]["parking"], 1)

    def test_domain_tokenizer_ignores_non_pathlike_slang_dict_path(self) -> None:
        tok = domain_tokenizer.DomainTokenizer(slang_dict_path=123)  # type: ignore[arg-type]
        self.assertGreater(tok.trie.term_count, 0)


if __name__ == "__main__":
    unittest.main()
