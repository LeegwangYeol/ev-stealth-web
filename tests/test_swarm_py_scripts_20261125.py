"""Regression tests for scripts/*.py fixes (2026-11-25 audit)."""

from __future__ import annotations

import contextlib
import io
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

WEB_ROOT = Path(__file__).resolve().parent.parent
if str(WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_ROOT))

from scripts import build_casebook
from scripts import cross_aggregator
from scripts import generate_report
from scripts import sentiment_engine
from scripts import statistical_ranker
from scripts import sync_defect_reports as sync_mod
from scripts import validate_data


def _assert_positive_zero(test_case: unittest.TestCase, val: float) -> None:
    if val == 0.0:
        test_case.assertFalse(math.copysign(1.0, val) < 0.0, f"Expected +0.0, got {val!r}")


class TestScriptsAudit20261125(unittest.TestCase):
    def test_sync_defect_reports_whitespace_fallbacks_and_negative_zero(self) -> None:
        item = {
            "id": "rep-ws-1",
            "source": "   ",
            "platform": "bobaedream",
            "url": "   ",
            "post_url": "https://www.bobaedream.co.kr/view?No=10",
            "title": "   ",
            "post_title": "실제 제목",
            "date": "   ",
            "created_at": "2026-11-25T01:02:03Z",
            "vehicle_model": "   ",
            "target_vehicle": "Ioniq 5",
            "verbatim_quote": "   ",
            "raw_quote": "실제 인용문",
            "sentiment_score": -0.0,
            "sentiment_polarity": -0.0,
            "negativity_score": -0.0,
            "severity_index": -0.0,
            "sentiment_tier": "   ",
            "dsi_breakdown": {"safety": -0.0, "functional": 2.0},
        }
        norm = sync_mod.normalize_report_item(item)
        self.assertEqual(norm["source"], "bobaedream")
        self.assertEqual(norm["platform"], "bobaedream")
        self.assertEqual(norm["url"], "https://www.bobaedream.co.kr/view?No=10")
        self.assertEqual(norm["title"], "실제 제목")
        self.assertEqual(norm["post_title"], "실제 제목")
        self.assertEqual(norm["date"], "2026-11-25")
        self.assertEqual(norm["vehicle_model"], "Ioniq 5")
        self.assertEqual(norm["verbatim_quote"], "실제 인용문")
        self.assertEqual(norm["sentiment_tier"], "POSITIVE")

        _assert_positive_zero(self, norm["sentiment_score"])
        _assert_positive_zero(self, norm["sentiment_polarity"])
        _assert_positive_zero(self, norm["negativity_score"])
        _assert_positive_zero(self, norm["severity_index"])
        _assert_positive_zero(self, norm["dsi_breakdown"]["safety"])
        self.assertNotIn("-0.0", json.dumps(norm, allow_nan=False))

        merged = sync_mod.merge_report_records(
            {"date": "2026-11-24", "negativity_score": -0.0},
            {"date": "   ", "created_at": "2026-11-25T00:00:00Z", "negativity_score": -0.0},
        )
        self.assertEqual(merged["date"], "2026-11-24")
        _assert_positive_zero(self, merged["negativity_score"])
        _assert_positive_zero(self, merged["sentiment_score"])

        stats = sync_mod.compute_report_statistics([{"platform": "   ", "source": "dcinside", "vehicle_model": "EV6"}])
        self.assertEqual(stats["top_platform"], "dcinside")

    def test_build_casebook_sanitizes_urls_none_fields_multiline_quotes_and_platform_table(self) -> None:
        safe_url = build_casebook._sanitize_md_url("https://example.com/a|b<c>\n\r?q=(1)")
        self.assertNotIn("\n", safe_url)
        self.assertNotIn("\r", safe_url)
        self.assertNotIn("|", safe_url)
        self.assertNotIn("<", safe_url)
        self.assertIn("%7C", safe_url)

        cases = [
            {
                "id": None,
                "platform": "dc|inside\nbreak",
                "board_name": None,
                "post_url": "https://example.com/post?a=1|2",
                "post_title": "Title\nInjectedHeading",
                "target_vehicle": None,
                "category": "parking",
                "defect_topic": None,
                "raw_quote": "Line 1\n## Not a heading",
                "slang_terms": ["tag`backtick"],
                "severity": None,
            }
        ]
        section = build_casebook.build_case_studies_section("parking", "Parking", cases)
        self.assertNotIn('> "None"', section)
        self.assertIn('> "Line 1\n> ## Not a heading"', section)
        self.assertNotIn("Title\nInjectedHeading", section)
        self.assertIn("`tag'backtick`", section)

        idx_md = build_casebook.build_source_index_section(cases)
        self.assertIn("`dc\\|inside break`", idx_md)

    def test_generate_report_escapes_platform_table_and_handles_missing_slang(self) -> None:
        tok = generate_report.DomainTokenizer()
        sent = generate_report.SentimentEngine(tok)
        records = [
            {
                "platform": "dc|inside\nbad",
                "post_title": "ICCU 결함",
                "defect_topic": "충전",
                "raw_quote": "ICCU 폭탄 발생",
                "target_vehicle": "Ioniq 5",
                "category": "charging",
            }
        ]
        ranker = generate_report.StatisticalRanker(records, tok, sent)
        agg = generate_report.CrossAggregator(tok, sent)
        report_md = generate_report.generate_statistical_report_content(records, ranker, agg)
        self.assertIn("dc\\|inside bad", report_md)

        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            inp = p / "complaints.json"
            inp.write_text(json.dumps(records), encoding="utf-8")
            missing_slang = p / "missing_slang.json"
            out_rep = p / "STATISTICAL_REPORT.md"
            out_cb = p / "CASEBOOK.md"

            old_argv = sys.argv
            buf = io.StringIO()
            try:
                sys.argv = [
                    "generate_report.py",
                    "--input", str(inp),
                    "--slang", str(missing_slang),
                    "--output", str(out_rep),
                    "--casebook", str(out_cb),
                ]
                with contextlib.redirect_stdout(buf):
                    with self.assertRaises(SystemExit) as cm:
                        generate_report.main()
                self.assertEqual(cm.exception.code, 1)
                self.assertIn("Failed to build casebook", buf.getvalue())
            finally:
                sys.argv = old_argv

    def test_sentiment_engine_normalizes_negative_zero(self) -> None:
        eng = sentiment_engine.SentimentEngine()
        res = eng.classify("안 테스트")
        _assert_positive_zero(self, res.polarity_score)
        _assert_positive_zero(self, res.dsi_score)
        for v in res.dsi_breakdown.values():
            _assert_positive_zero(self, v)

    def test_statistical_ranker_large_n_ngram_pmi_no_underflow_or_inf(self) -> None:
        long_quote = " ".join(["아이오닉", "배터리", "충전", "오류"] * 40)
        ranker = statistical_ranker.StatisticalRanker(
            [{"post_title": "테스트", "defect_topic": "충전", "raw_quote": long_quote}]
        )
        grams = ranker.extract_ngrams(n=100, min_freq=1, top_k=5)
        self.assertGreater(len(grams), 0)
        for _, _, pmi in grams:
            self.assertTrue(math.isfinite(pmi))
            _assert_positive_zero(self, pmi)

    def test_cross_aggregator_whitespace_and_negative_zero(self) -> None:
        _assert_positive_zero(self, cross_aggregator._safe_finite_float(-0.0, 1.0))
        chi2, _, _ = cross_aggregator.CrossAggregator.compute_chi_square([[1, 1], [1, 1]])
        _assert_positive_zero(self, chi2)

        agg = cross_aggregator.CrossAggregator()
        plat_stats = agg.aggregate_by_platform([{"platform": "   ", "raw_quote": "test"}])
        self.assertIn("unknown", plat_stats)
        self.assertNotIn("   ", plat_stats)

        veh_stats = agg.aggregate_by_vehicle_model([{"target_vehicle": "   ", "raw_quote": "test"}])
        self.assertIn("Unknown EV", veh_stats)
        self.assertNotIn("   ", veh_stats)

    def test_validate_data_parity_rejects_backslash_and_null_byte_and_main_exit_none(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            d1 = base / "root"
            d2 = base / "web"
            d1.mkdir()
            d2.mkdir()
            ok, errs, _ = validate_data.validate_data_parity(
                d1, d2, target_files=["..\\secret.json", "bad\x00name.json"]
            )
            self.assertFalse(ok)
            self.assertEqual(len(errs), 2)

        with mock.patch.object(validate_data, "parse_arguments", side_effect=SystemExit()):
            self.assertEqual(validate_data.main([]), 0)
        with mock.patch.object(validate_data, "parse_arguments", side_effect=SystemExit(True)):
            self.assertEqual(validate_data.main([]), 1)

    def test_scripts_run_tracker_does_not_self_recurse_and_exits_cleanly(self) -> None:
        src = (WEB_ROOT / "scripts" / "run_tracker.py").read_text(encoding="utf-8")
        self.assertNotIn('CURRENT_DIR / "run_tracker.py"', src)
        self.assertIn("CURRENT_FILE", src)

        res = subprocess.run(
            [sys.executable, str(WEB_ROOT / "scripts" / "run_tracker.py"), "--help"],
            capture_output=True,
            text=True,
            cwd=str(WEB_ROOT),
        )
        self.assertEqual(res.returncode, 0)

        res_sc = subprocess.run(
            [sys.executable, str(WEB_ROOT / "scripts" / "run_scraper.py"), "--help"],
            capture_output=True,
            text=True,
            cwd=str(WEB_ROOT),
        )
        self.assertEqual(res_sc.returncode, 0)


if __name__ == "__main__":
    unittest.main()
