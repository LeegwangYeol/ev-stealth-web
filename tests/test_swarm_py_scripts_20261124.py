"""Regression tests for scripts/*.py fixes (2026-11-24 audit)."""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
import sys
import tempfile
import unittest

WEB_ROOT = Path(__file__).resolve().parent.parent
if str(WEB_ROOT) not in sys.path:
    sys.path.insert(0, str(WEB_ROOT))

from scripts import build_casebook
from scripts import compile_database
from scripts import cross_aggregator
from scripts import domain_tokenizer
from scripts import mine_community_data
from scripts import statistical_ranker
from scripts import sync_defect_reports as sync_mod
from scripts import validate_data


def _valid_subsidy_payload() -> dict:
    return {
        "metadata": {
            "version": "1.0",
            "generated_at": "2026-01-01",
            "policy_year": 2026,
            "currency": "KRW",
        },
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


class TestScriptsAudit20261124(unittest.TestCase):
    def test_validate_database_rejects_bool_and_nan_ids(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            slang = p / "slang.json"
            slang.write_text(json.dumps({f"term_{i}": {"category": "test"} for i in range(12)}), encoding="utf-8")

            bad_id_rec = {
                "id": True,
                "platform": "bobaedream",
                "board_name": "국산차",
                "post_url": "https://example.com/1",
                "post_title": "title",
                "target_vehicle": "Ioniq 5",
                "category": "charging",
                "defect_topic": "topic",
                "raw_quote": "quote text here",
                "slang_terms": ["ICCU"],
                "severity": "critical_safety",
                "collected_at": "2026-01-01T00:00:00Z",
            }
            comp = p / "complaints.json"
            comp.write_text(json.dumps([bad_id_rec]), encoding="utf-8")

            ok, errs, _ = validate_data.validate_database(str(comp), str(slang), min_per_category=1, min_total=1)
            self.assertFalse(ok)
            self.assertTrue(any("Invalid id type 'bool'" in e for e in errs))

    def test_validate_subsidy_rejects_false_iso_and_nonlist_collections(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub.json"
            payload = _valid_subsidy_payload()
            payload["regions"][0]["iso_code"] = False
            payload["regions"][0]["region_id"] = "KR-00"
            payload["regions"][1]["municipalities"] = "corrupt"
            payload["popular_models_matrix"] = {"not": "a_list"}

            p.write_text(json.dumps(payload), encoding="utf-8")
            ok, errs, _ = validate_data.validate_subsidy_data(p)
            self.assertFalse(ok)
            self.assertTrue(any("Invalid iso_code/region_id type 'bool'" in e for e in errs))
            self.assertTrue(any("'municipalities' must be a list" in e for e in errs))
            self.assertTrue(any("'popular_models_matrix' must be a list" in e for e in errs))

    def test_validate_subsidy_rejects_duplicate_or_empty_popular_model_ids(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sub.json"
            payload = _valid_subsidy_payload()
            payload["popular_models_matrix"] = [
                {
                    "model_id": "m1",
                    "name_ko": "모델1",
                    "base_price_krw": 50_000_000,
                    "price_subsidy_ratio": 1.0,
                    "national_subsidy_krw": 5_000_000,
                },
                {
                    "model_id": "m1",
                    "name_ko": "   ",
                    "base_price_krw": 50_000_000,
                    "price_subsidy_ratio": 1.0,
                    "national_subsidy_krw": 5_000_000,
                },
            ]
            p.write_text(json.dumps(payload), encoding="utf-8")
            ok, errs, _ = validate_data.validate_subsidy_data(p)
            self.assertFalse(ok)
            self.assertTrue(any("duplicate model_id 'm1'" in e for e in errs))
            self.assertTrue(any("invalid or empty name_ko" in e for e in errs))

    def test_validate_daily_reports_rejects_empty_or_nonstring_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "daily_reports.json"
            payload = {
                "generated_at": "2026-11-24T00:00:00Z",
                "pipeline_version": "1.0.0",
                "statistics": {
                    "total_scraped": 1,
                    "total_filtered_defects": 1,
                    "avg_negativity_score": 0.8,
                    "critical_defect_count": 0,
                },
                "reports": [
                    {
                        "id": "rep-1",
                        "source": "   ",
                        "url": 12345,
                        "title": "Valid Title",
                        "date": "2026-11-24",
                        "vehicle_model": "EV6",
                        "defect_category": "BATTERY_CHARGING",
                        "defect_category_ko": "배터리/충전",
                        "summary": "Summary",
                        "verbatim_quote": "Quote",
                        "sentiment_score": 0.8,
                        "severity": "HIGH",
                    }
                ],
            }
            p.write_text(json.dumps(payload), encoding="utf-8")
            ok, errs, _ = validate_data.validate_daily_reports(p)
            self.assertFalse(ok)
            self.assertTrue(any("Field 'source' must be a non-empty string" in e for e in errs))
            self.assertTrue(any("Field 'url' must be a string" in e for e in errs))

    def test_validate_data_parity_rejects_path_traversal_target_files(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            d1 = base / "root"
            d2 = base / "web"
            d1.mkdir()
            d2.mkdir()
            ok, errs, _ = validate_data.validate_data_parity(
                d1, d2, target_files=["../secret.json", "sub/file.json", ".."]
            )
            self.assertFalse(ok)
            self.assertEqual(len(errs), 3)
            self.assertTrue(all("Unsafe target filename rejected" in e for e in errs))

    def test_sync_defect_reports_url_case_merge_sanitization_and_validate_path_guard(self) -> None:
        self.assertEqual(
            sync_mod.normalize_url_for_key("HTTPS://WWW.Bobaedream.co.kr/view?No=1#top"),
            "Bobaedream.co.kr/view?No=1",
        )
        self.assertFalse(sync_mod.validate_reports_file(None))  # type: ignore[arg-type]

        merged = sync_mod.merge_report_records(
            {
                "negativity_score": float("nan"),
                "sentiment_score": float("inf"),
                "dsi_breakdown": {"safety": float("nan"), "functional": 8.0},
            },
            {
                "date": "2026-11-24",
                "dsi_breakdown": {"economic": 7.5},
            },
        )
        self.assertEqual(merged["date"], "2026-11-24")
        self.assertNotIn("negativity_score", merged)
        self.assertNotIn("sentiment_score", merged)
        self.assertEqual(merged["dsi_breakdown"], {"functional": 8.0, "economic": 7.5})

        serialized = json.dumps(merged, allow_nan=False)
        self.assertIn("2026-11-24", serialized)

    def test_build_casebook_accepts_str_paths_and_sanitizes_markdown_cells_and_urls(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)
            data_p = p / "complaints.json"
            slang_p = p / "slang.json"
            out_p = p / "CASEBOOK.md"

            data_p.write_text(
                json.dumps(
                    [
                        {
                            "id": "C|1",
                            "platform": "dcinside",
                            "board_name": "전기차|갤",
                            "post_url": "javascript:alert(1)",
                            "post_title": "Title\nBreak",
                            "target_vehicle": "Model|Y",
                            "category": "parking",
                            "defect_topic": "Topic|1",
                            "raw_quote": "Quote",
                            "slang_terms": ["ICCU|폭탄"],
                            "severity": "critical_safety",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            slang_p.write_text(
                json.dumps({"term|a": {"category": "c|1", "meaning": "m\n1", "context": "ctx|1", "example": "ex|1"}}),
                encoding="utf-8",
            )

            build_casebook.build_casebook(str(data_p), str(slang_p), str(out_p))  # type: ignore[arg-type]
            md = out_p.read_text(encoding="utf-8")
            self.assertNotIn("javascript:alert(1)", md)
            self.assertIn("[링크 바로가기](#)", md)
            self.assertIn("term\\|a", md)
            self.assertIn("C\\|1", md)

    def test_domain_tokenizer_logs_corrupt_slang_and_guards_trie_inputs(self) -> None:
        trie = domain_tokenizer.AutomotiveTrie()
        trie.insert("ICCU", domain_category="tech", severity_weight=float("nan"))
        match = trie.search_longest_prefix("ICCU", 0)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match[2], 1.0)
        self.assertIsNone(trie.search_longest_prefix("ICCU", True))  # type: ignore[arg-type]
        self.assertIsNone(trie.search_longest_prefix("ICCU", 1.5))  # type: ignore[arg-type]
        self.assertIsNone(trie.search_longest_prefix("ICCU", 99))

        with tempfile.TemporaryDirectory() as td:
            bad_slang = Path(td) / "slang.json"
            bad_slang.write_text("{corrupt", encoding="utf-8")
            with self.assertLogs(domain_tokenizer.__name__, level=logging.WARNING) as cm:
                tok = domain_tokenizer.DomainTokenizer(str(bad_slang))
            self.assertGreater(tok.trie.term_count, 0)
            self.assertTrue(any("Failed to load slang dictionary" in m for m in cm.output))

    def test_statistical_ranker_compute_tfidf_rejects_non_string_and_unhashable(self) -> None:
        ranker = statistical_ranker.StatisticalRanker([])
        self.assertEqual(ranker.compute_tfidf(None), 0.0)  # type: ignore[arg-type]
        self.assertEqual(ranker.compute_tfidf(["unhashable"]), 0.0)  # type: ignore[arg-type]
        self.assertEqual(ranker.compute_tfidf(""), 0.0)

    def test_cross_aggregator_chi_square_rejects_jagged_and_temporal_uses_date_fallback(self) -> None:
        chi2, dof, pval = cross_aggregator.CrossAggregator.compute_chi_square([[1, 2], [3, 4, 5]])
        self.assertEqual((chi2, dof, pval), (0.0, 0, 1.0))

        agg = cross_aggregator.CrossAggregator()
        temporal = agg.aggregate_by_temporal_trend(
            [{"date": "20240815", "sentiment_tier": "NEGATIVE", "dsi_score": 8.0}]
        )
        self.assertEqual(temporal["2024"]["total_cases"], 1)

    def test_mine_community_data_clamps_bad_delays_and_non_dict_slang(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            slang_list = Path(td) / "slang_list.json"
            slang_list.write_text('["not", "a", "dict"]', encoding="utf-8")
            orch = mine_community_data.CommunityDataMiningOrchestrator(
                min_delay=-5.0,
                max_delay=-10.0,
                slang_path=str(slang_list),
                output_path=str(Path(td) / "out.json"),
            )
            self.assertEqual(orch.min_delay, 0.0)
            self.assertEqual(orch.max_delay, 0.0)
            self.assertEqual(orch.slang_dict, {})

    def test_compile_database_does_not_shadow_root_entrypoints_in_sys_path(self) -> None:
        scripts_dir = str(WEB_ROOT / "scripts")
        self.assertTrue(hasattr(compile_database, "compile_database"))
        if scripts_dir in sys.path and str(WEB_ROOT) in sys.path:
            self.assertLess(sys.path.index(str(WEB_ROOT)), sys.path.index(scripts_dir))


if __name__ == "__main__":
    unittest.main()
