"""Regression tests for scripts/*.py fixes (2026-11-23 audit)."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

WEB_ROOT = Path(__file__).resolve().parent.parent
if str(WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_ROOT))

from scripts import build_casebook
from scripts import generate_report
from scripts import sync_defect_reports as sync_mod
from scripts import validate_data
from scripts.domain_tokenizer import AutomotiveTrie
from scripts.statistical_ranker import StatisticalRanker


class TestScriptsAudit20261123(unittest.TestCase):
    def test_validate_subsidy_rejects_whitespace_iso_code(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub.json"
            payload = {
                "metadata": {"version": "1.0", "generated_at": "2026-01-01", "policy_year": 2026, "currency": "KRW"},
                "alert_thresholds": {
                    t: {"min_percent": 0.0, "max_percent": 100.0, "severity": t}
                    for t in ("HEALTHY", "CAUTION", "WARNING", "CRITICAL", "DEPLETED")
                },
                "nationwide_summary": {
                    "total_announced_units": 100,
                    "total_applied_units": 10,
                    "total_remaining_units": 90,
                    "nationwide_depletion_rate": 10.0,
                },
                "regions": [
                    {
                        "iso_code": "   ",
                        "name_ko": "서울",
                        "categories": {
                            c: {
                                "announced_units": 10,
                                "applied_units": 1,
                                "remaining_units": 9,
                                "depletion_rate": 10.0,
                                "status": "HEALTHY",
                            }
                            for c in ("passenger", "commercial", "bus")
                        },
                    }
                ],
            }
            p.write_text(json.dumps(payload), encoding="utf-8")
            ok, errs, _ = validate_data.validate_subsidy_data(p)
            self.assertFalse(ok)
            self.assertTrue(any("Missing iso_code/region_id" in e for e in errs))

    def test_validate_data_cli_reports_mismatch_when_mirror_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data_dir = root / "data"
            web_src = root / "ev-stealth-web" / "src" / "data"
            web_pub = root / "ev-stealth-web" / "public" / "data"
            data_dir.mkdir(parents=True)
            web_src.mkdir(parents=True)
            web_pub.mkdir(parents=True)

            valid_sub = {
                "metadata": {"version": "1.0", "generated_at": "2026-01-01", "policy_year": 2026, "currency": "KRW"},
                "alert_thresholds": {
                    t: {"min_percent": 0.0, "max_percent": 100.0, "severity": t}
                    for t in ("HEALTHY", "CAUTION", "WARNING", "CRITICAL", "DEPLETED")
                },
                "nationwide_summary": {
                    "total_announced_units": 100,
                    "total_applied_units": 10,
                    "total_remaining_units": 90,
                    "nationwide_depletion_rate": 10.0,
                },
                "regions": [
                    {
                        "iso_code": f"KR-{i:02d}",
                        "name_ko": f"지역{i}",
                        "categories": {
                            c: {
                                "announced_units": 10,
                                "applied_units": 1,
                                "remaining_units": 9,
                                "depletion_rate": 10.0,
                                "status": "HEALTHY",
                            }
                            for c in ("passenger", "commercial", "bus")
                        },
                    }
                    for i in range(17)
                ],
            }
            sub_bytes = json.dumps(valid_sub).encode("utf-8")
            (data_dir / "ev_subsidy_data.json").write_bytes(sub_bytes)
            (web_src / "ev_subsidy_data.json").write_bytes(sub_bytes)
            # Omit web_pub/ev_subsidy_data.json intentionally

            import io
            from contextlib import redirect_stdout
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = validate_data.main(["--root", str(root), "--dry-run"])
            out = buf.getvalue()
            self.assertEqual(rc, 1)
            self.assertIn("ev_subsidy_data.json", out)
            self.assertNotIn("ev_subsidy_data.json        : PARITY OK", out)

    def test_sync_defect_reports_nan_and_bool_id_and_nan_scores(self) -> None:
        self.assertIsNone(sync_mod.get_report_primary_id({"id": True}))
        self.assertIsNone(sync_mod.get_report_primary_id({"id": float("nan")}))
        self.assertIsNone(sync_mod.get_report_primary_id({"id": "nan"}))

        norm = sync_mod.normalize_report_item({"id": float("nan"), "title": "t", "source": "dcinside"})
        self.assertTrue(norm["id"].startswith("defect_"))

        norm_bool = sync_mod.normalize_report_item({"id": True, "title": "t", "source": "dcinside"})
        self.assertTrue(norm_bool["id"].startswith("defect_"))

        merged = sync_mod.merge_report_records(
            {"negativity_score": float("nan"), "sentiment_score": 0.72},
            {"negativity_score": float("inf")},
        )
        self.assertTrue(math.isfinite(merged["negativity_score"]))
        self.assertAlmostEqual(merged["negativity_score"], 0.72, places=4)
        self.assertAlmostEqual(merged["sentiment_score"], 0.72, places=4)

    def test_sync_defect_reports_handles_nan_timeouts_and_caches_sources(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root_d = base / "data"
            web_d = base / "ev-stealth-web" / "src" / "data"
            root_d.mkdir(parents=True)
            web_d.mkdir(parents=True)

            payload = {
                "generated_at": "2026-11-23T00:00:00+00:00",
                "statistics": {"total_scraped": 1, "total_filtered_defects": 1, "avg_negativity_score": 0.8, "critical_defect_count": 1},
                "reports": [
                    {
                        "id": "r1",
                        "source": "bobaedream",
                        "date": "2026-11-23",
                        "title": "ICCU 셧다운",
                        "vehicle_model": "Ioniq 5",
                        "defect_category": "BATTERY_CHARGING",
                        "severity": "CRITICAL",
                        "sentiment_score": 0.8,
                        "slang_tags": ["ICCU"],
                    }
                ],
            }
            (root_d / "daily_reports.json").write_text(json.dumps(payload), encoding="utf-8")

            written = sync_mod.sync_defect_reports(
                root_dir=root_d,
                web_dir=web_d,
                lock_timeout=float("nan"),
                stale_timeout=-5.0,
            )
            self.assertIn(str(web_d / "daily_reports.json"), written)
            self.assertTrue((web_d / "daily_reports.json").is_file())

    def test_statistical_ranker_single_pass_tokenization_parity(self) -> None:
        records = [
            {
                "post_title": "ICCU 폭탄 고속도로 셧다운",
                "defect_topic": "충전 결함",
                "raw_quote": "고속도로 주행 중 ICCU 터짐으로 차가 멈췄습니다.",
            },
            {
                "post_title": "배트맨타이어 수막현상",
                "defect_topic": "우천 주행",
                "raw_quote": "빗길에서 배트맨타이어 때문에 피쉬테일 발생했습니다.",
            },
        ]
        ranker = StatisticalRanker(records)
        self.assertEqual(ranker.num_docs, 2)
        self.assertEqual(len(ranker.doc_dsi_scores), 2)
        top = ranker.compute_top_keywords(top_n=5)
        self.assertEqual(len(top), 5)
        self.assertTrue(all(math.isfinite(row["ccs_score"]) for row in top))

    def test_generate_report_rejects_nan_json_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            bad_json = Path(td) / "bad.json"
            bad_json.write_text('[{"post_title": "a", "score": NaN}]', encoding="utf-8")
            old_argv = sys.argv
            try:
                sys.argv = ["generate_report.py", "--input", str(bad_json)]
                with self.assertRaises(SystemExit) as cm:
                    generate_report.main()
                self.assertEqual(cm.exception.code, 1)
            finally:
                sys.argv = old_argv

    def test_build_casebook_rejects_nan_and_handles_unhashable_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            nan_file = Path(td) / "nan.json"
            nan_file.write_text('{"x": NaN}', encoding="utf-8")
            with self.assertRaises(ValueError):
                build_casebook.load_json_file(nan_file)

        md = build_casebook.build_source_index_section([
            {"id": "1", "platform": {"nested": 1}, "target_vehicle": ["EV6"], "category": "charging"}
        ])
        self.assertIn("EV6", md)

    def test_automotive_trie_non_string_guard(self) -> None:
        trie = AutomotiveTrie()
        trie.insert("ICCU", "tech_electrical", 2.5, "ICCU")
        self.assertIsNone(trie.search_longest_prefix(None, 0))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
