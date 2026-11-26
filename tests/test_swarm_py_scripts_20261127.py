"""Regression tests for scripts/*.py fixes (2026-11-27 audit)."""

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

from scripts import cross_aggregator
from scripts import domain_tokenizer
from scripts import statistical_ranker
from scripts import sync_defect_reports as sync_mod
from scripts import validate_data


def _assert_positive_zero(test_case: unittest.TestCase, val: float) -> None:
    if val == 0.0:
        test_case.assertFalse(math.copysign(1.0, val) < 0.0, f"Expected +0.0, got {val!r}")


class TestScriptsAudit20261127(unittest.TestCase):
    def test_cross_aggregator_normalizes_negative_zero_tiers_and_whitespace_timestamps(self) -> None:
        agg = cross_aggregator.CrossAggregator()
        records = [
            {
                "platform": "  bobaedream ",
                "target_vehicle": "Tesla Model Y",
                "category": "  PARKING  ",
                "sentiment_tier": "  negative  ",
                "dsi_score": -0.001,
                "polarity_score": -0.5,
                "collected_at": "   ",
                "date": "2024-08-15",
                "raw_quote": "주차 문제",
            }
        ]

        brands = agg.aggregate_by_brand(records)
        _assert_positive_zero(self, brands["Tesla"]["mean_dsi"])
        self.assertEqual(brands["Tesla"]["sentiment_counts"]["NEGATIVE"], 1)
        self.assertEqual(brands["Tesla"]["sentiment_pct"]["NEGATIVE"], 100.0)

        platforms = agg.aggregate_by_platform(records)
        _assert_positive_zero(self, platforms["bobaedream"]["mean_dsi"])
        self.assertEqual(platforms["bobaedream"]["sentiment_counts"]["NEGATIVE"], 1)

        vehicles = agg.aggregate_by_vehicle_model(records)
        _assert_positive_zero(self, vehicles["Tesla Model Y"]["mean_dsi"])

        temporal = agg.aggregate_by_temporal_trend(records)
        self.assertEqual(temporal["2024"]["total_cases"], 1)
        _assert_positive_zero(self, temporal["2024"]["mean_dsi"])
        self.assertEqual(temporal["2024"]["sentiment_breakdown"]["NEGATIVE"], 1)

        cont = agg.build_contingency_tables(records)
        # bobaedream=0, NEGATIVE=2; parking=0, Passenger EV=0; Tesla=0
        self.assertEqual(cont["platform_sentiment"]["matrix"][0][2], 1)
        self.assertEqual(cont["category_segment"]["matrix"][0][0], 1)
        self.assertEqual(cont["brand_category"]["matrix"][0][0], 1)
        self.assertEqual(cont["brand_sentiment"]["matrix"][0][2], 1)

    def test_sync_defect_reports_rejects_nonscalar_ids_infinity_strings_and_discovers_web_mirrors(self) -> None:
        for bad_id in (["a"], {"k": "v"}, "Infinity", "-Infinity", "+inf"):
            self.assertIsNone(sync_mod.get_report_primary_id({"id": bad_id}))
            norm = sync_mod.normalize_report_item({"id": bad_id, "source": "dcinside", "title": "test"})
            self.assertTrue(norm["id"].startswith("defect_"))

        top_cats = sync_mod.compute_top_categories(
            [{"defect_category": "   ", "category": "COLD_WEATHER"}]
        )
        self.assertEqual(top_cats[0]["category"], "COLD_WEATHER")

        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            root_d = base / "data"
            web_root = base / "ev-stealth-web"
            web_src = web_root / "src" / "data"
            web_pub = web_root / "public" / "data"
            web_data = web_root / "data"
            for d in (root_d, web_src, web_pub, web_data):
                d.mkdir(parents=True)

            _, _, add_from_web_root = sync_mod.get_default_known_paths(root_dir=root_d, web_dir=web_root)
            add_resolved = {p.resolve() for p in add_from_web_root}
            self.assertIn((web_pub / "daily_reports.json").resolve(), add_resolved)
            self.assertIn((web_data / "daily_reports.json").resolve(), add_resolved)

            _, _, add_from_src_data = sync_mod.get_default_known_paths(root_dir=root_d, web_dir=web_src)
            add_src_resolved = {p.resolve() for p in add_from_src_data}
            self.assertIn((web_pub / "daily_reports.json").resolve(), add_src_resolved)
            self.assertIn((web_data / "daily_reports.json").resolve(), add_src_resolved)

    def test_validate_data_normalizes_neg_zero_rate_and_avoids_duplicate_flat_public_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data_dir = root / "data"
            src_data = root / "src" / "data"
            pub_data = root / "public" / "data"
            for d in (data_dir, src_data, pub_data):
                d.mkdir(parents=True)

            sub_payload = {
                "metadata": {"version": "1.0", "generated_at": "2026-01-01", "policy_year": 2026, "currency": "KRW"},
                "alert_thresholds": {
                    t: {"min_percent": 0.0, "max_percent": 100.0, "severity": t}
                    for t in ("HEALTHY", "CAUTION", "WARNING", "CRITICAL", "DEPLETED")
                },
                "nationwide_summary": {
                    "total_announced_units": 0,
                    "total_applied_units": 0,
                    "total_remaining_units": 0,
                    "nationwide_depletion_rate": -0.0,
                },
                "regions": [
                    {
                        "iso_code": f"KR-{i:02d}",
                        "name_ko": f"지역{i}",
                        "categories": {
                            c: {
                                "announced_units": 0,
                                "applied_units": 0,
                                "remaining_units": 0,
                                "depletion_rate": 0.0,
                                "status": "HEALTHY",
                            }
                            for c in ("passenger", "commercial", "bus")
                        },
                    }
                    for i in range(17)
                ],
            }
            sub_path = data_dir / "ev_subsidy_data.json"
            sub_path.write_text(json.dumps(sub_payload), encoding="utf-8")
            ok, errs, stats = validate_data.validate_subsidy_data(sub_path)
            self.assertTrue(ok, errs)
            _assert_positive_zero(self, stats["nationwide_depletion_rate"])

            _, _, all_stats = validate_data.validate_all_datasets(project_root=root, sync_web=False, dry_run=True)
            dirs = all_stats["parity"]["directories"]
            pub_entries = [d for d in dirs if str(pub_data) in d]
            self.assertEqual(len(pub_entries), 1)

    def test_statistical_ranker_strips_brand_and_normalizes_neg_zero_dsi(self) -> None:
        class TinyNegSentiment:
            def classify(self, text: str, tokens=None):
                return type(
                    "Res",
                    (),
                    {
                        "polarity_score": 0.0,
                        "tier_label": "NEUTRAL",
                        "dsi_score": -0.001,
                        "dsi_breakdown": {},
                        "detected_complaints": [],
                    },
                )()

        records = [
            {
                "target_vehicle": "Tesla Model Y",
                "post_title": "정신병 와이퍼 문제",
                "defect_topic": "정신병 와이퍼",
                "raw_quote": "테슬라 모델 Y 정신병 와이퍼 마른 유리 긁힘",
            },
            {
                "target_vehicle": "Hyundai Ioniq 5",
                "post_title": "ICCU 터짐",
                "defect_topic": "ICCU",
                "raw_quote": "아이오닉 5 ICCU 폭탄 셧다운",
            },
        ]
        ranker = statistical_ranker.StatisticalRanker(records, sentiment_engine=TinyNegSentiment())

        top = ranker.compute_top_keywords(top_n=5)
        for row in top:
            _assert_positive_zero(self, row["mean_dsi"])
            _assert_positive_zero(self, row["ccs_score"])

        brand_res = ranker.compute_brand_top_keywords(brand="  tesla  ", top_n=5)
        self.assertGreater(len(brand_res), 0)
        self.assertFalse(any("ICCU" in row["keyword"] for row in brand_res))
        for row in brand_res:
            _assert_positive_zero(self, row["mean_dsi"])

    def test_domain_tokenizer_ignores_directory_slang_dict_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tok = domain_tokenizer.DomainTokenizer(slang_dict_path=td)
            self.assertGreater(tok.trie.term_count, 0)


if __name__ == "__main__":
    unittest.main()
