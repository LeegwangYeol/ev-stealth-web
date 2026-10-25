"""Unit test suite locking in all Cycle 18 Backend Remediations.

Validates:
1. Type hint introspection for defect_filter and subsidy_baseline.
2. Non-positive MSRP guard in calculate_price_cap_ratio.
3. Standard mapping protocol KeyError on CategoryMetrics and MunicipalityMetrics.
4. Native mapping protocol on ComplaintRecord and DailyReportPayload.
5. DailyReportStatistics.to_dict() None and NaN resilience with _safe_round.
6. Korean dotted and 2-digit year date parsing in _extract_record_date and ComplaintRecord.date_str.
7. RawPost.from_dict None comments and attribute coercion resilience.
8. ContextualDefectFilter.process_post filtering non-string comment items.
9. Crawler case-insensitive regex for post ID extraction in BobaeDream and DCInside.
10. Symlink deduplication in sync_defect_reports using Path.resolve().
11. Atomic writer empty target_path guard and Decimal serialization.
12. Slang lexicon None text guard and robust_decode str handling.
"""

from decimal import Decimal
import os
from pathlib import Path
import tempfile
import typing
import unittest

from crawlers.bobaedream import BobaeDreamCrawler
from crawlers.dcinside import DCInsideCrawler
from filters.defect_filter import ContextualDefectFilter
from filters.slang_lexicon import find_matching_slang
from models.complaint import (
    ComplaintRecord,
    DailyReportPayload,
    DailyReportStatistics,
    RawPost,
)
from run_tracker import sync_defect_reports as run_tracker_sync_defect_reports
from tracker.atomic_writer import _json_default, atomic_write_json
from tracker.defect_tracker import DefectTracker
from tracker.subsidy_baseline import (
    build_initial_baseline,
    calculate_price_cap_ratio as baseline_calc_price_cap,
)
from tracker.subsidy_models import CategoryMetrics, MunicipalityMetrics
from tracker.subsidy_tracker import calculate_price_cap_ratio as tracker_calc_price_cap
from utils.http_client import robust_decode
from utils.json_writer import _extract_record_date


class TestBackendCycle18Remediation(unittest.TestCase):
    """Rigorous test cases for Cycle 18 backend hardening fixes."""

    # -----------------------------------------------------------------
    # Item 1: Type Hint Introspection
    # -----------------------------------------------------------------
    def test_typing_introspection_defect_filter_and_subsidy_baseline(self):
        """typing.get_type_hints must resolve Union and Optional without NameError."""
        filter_hints = typing.get_type_hints(ContextualDefectFilter.process_post)
        self.assertIn("post", filter_hints)
        self.assertIn("return", filter_hints)

        baseline_hints = typing.get_type_hints(build_initial_baseline)
        self.assertIn("regions", baseline_hints)
        self.assertIn("return", baseline_hints)

    # -----------------------------------------------------------------
    # Item 2: Price Cap Ratio Non-Positive MSRP Guard
    # -----------------------------------------------------------------
    def test_price_cap_ratio_non_positive_and_boundary_guards(self):
        """calculate_price_cap_ratio must return 0.0 for <= 0, None, NaN, and Inf."""
        for calc_fn in (baseline_calc_price_cap, tracker_calc_price_cap):
            # Non-positive values must yield 0.0 subsidy ratio
            self.assertEqual(calc_fn(-1), 0.0)
            self.assertEqual(calc_fn(-50_000_000), 0.0)
            self.assertEqual(calc_fn(0), 0.0)

            # Defensive null and non-numeric guards
            self.assertEqual(calc_fn(None), 0.0)  # type: ignore[arg-type]
            self.assertEqual(calc_fn("invalid"), 0.0)  # type: ignore[arg-type]
            self.assertEqual(calc_fn(float("nan")), 0.0)  # type: ignore[arg-type]
            self.assertEqual(calc_fn(float("inf")), 0.0)  # type: ignore[arg-type]

            # Statutory positive tiers
            self.assertEqual(calc_fn(30_000_000), 1.0)
            self.assertEqual(calc_fn(55_000_000), 1.0)
            self.assertEqual(calc_fn(55_000_001), 0.5)
            self.assertEqual(calc_fn(85_000_000), 0.5)
            self.assertEqual(calc_fn(85_000_001), 0.0)
            self.assertEqual(calc_fn(120_000_000), 0.0)

    # -----------------------------------------------------------------
    # Item 3: KeyError on Invalid Mapping Keys in Subsidy Models
    # -----------------------------------------------------------------
    def test_mapping_protocol_category_metrics_key_error(self):
        """CategoryMetrics.__getitem__ must raise KeyError on missing keys."""
        cat = CategoryMetrics.from_dict({
            "announced_units": 100,
            "applied_units": 50,
        })
        self.assertEqual(cat["announced_units"], 100)
        self.assertEqual(cat.get("announced_units"), 100)
        self.assertIn("announced_units", cat)
        self.assertNotIn("non_existent_key", cat)
        self.assertEqual(cat.get("non_existent_key", 42), 42)

        with self.assertRaises(KeyError):
            _ = cat["non_existent_key"]

    def test_mapping_protocol_municipality_metrics_key_error(self):
        """MunicipalityMetrics.__getitem__ must raise KeyError on missing keys."""
        muni = MunicipalityMetrics.from_dict({
            "name_ko": "수원시",
            "announced_units": 200,
        })
        self.assertEqual(muni["name_ko"], "수원시")
        self.assertEqual(muni.get("name_ko"), "수원시")
        self.assertIn("name_ko", muni)
        self.assertNotIn("invalid_metric", muni)
        self.assertIsNone(muni.get("invalid_metric"))

        with self.assertRaises(KeyError):
            _ = muni["invalid_metric"]

    # -----------------------------------------------------------------
    # Item 4 & 5: Native Mapping Protocol on Complaint Models
    # -----------------------------------------------------------------
    def test_mapping_protocol_complaint_record(self):
        """ComplaintRecord must support __getitem__, __contains__, and get()."""
        rec = ComplaintRecord(
            id="test_rec_1",
            source="dcinside",
            url="https://gall.dcinside.com/board/view/?id=car_new1&no=123",
            title="아이오닉5 ICCU 결함 발생",
            author="전기차차차",
            created_at="2026-10-25T12:00:00Z",
            vehicle_brand="현대",
            vehicle_model="아이오닉5",
            defect_category="battery",
            summary="주행 중 경고등 점등 및 출력 저하",
            verbatim_quote="ICCU 터져서 갓길에 세웠네요",
        )
        self.assertEqual(rec["title"], "아이오닉5 ICCU 결함 발생")
        self.assertEqual(rec["platform"], "dcinside")  # via admin report dict alias
        self.assertIn("title", rec)
        self.assertIn("target_vehicle", rec)  # via admin report dict alias
        self.assertNotIn("unknown_attr_xyz", rec)
        self.assertEqual(rec.get("title"), "아이오닉5 ICCU 결함 발생")
        self.assertEqual(rec.get("unknown_attr_xyz", "fallback"), "fallback")

        with self.assertRaises(KeyError):
            _ = rec["unknown_attr_xyz"]

    def test_mapping_protocol_daily_report_payload(self):
        """DailyReportPayload must support native mapping protocol without monkey patching."""
        payload = DailyReportPayload(
            generated_at="2026-10-25T19:00:00Z",
            total_complaints_today=15,
        )
        self.assertEqual(payload["generated_at"], "2026-10-25T19:00:00Z")
        self.assertEqual(payload["total_complaints_today"], 15)
        self.assertIn("statistics", payload)
        self.assertIn("reports", payload)
        self.assertNotIn("non_existent_field", payload)
        self.assertEqual(payload.get("total_complaints_today"), 15)
        self.assertEqual(payload.get("missing", 999), 999)

        with self.assertRaises(KeyError):
            _ = payload["non_existent_field"]

    # -----------------------------------------------------------------
    # Item 6: DailyReportStatistics.to_dict() None and NaN Handling
    # -----------------------------------------------------------------
    def test_daily_report_statistics_to_dict_safe_round(self):
        """DailyReportStatistics.to_dict() must handle None, NaN, and Inf safely."""
        # None negativity score
        stats_none = DailyReportStatistics(
            total_scraped=10,
            total_filtered_defects=5,
            avg_negativity_score=None,  # type: ignore[arg-type]
            critical_defect_count=1,
        )
        d_none = stats_none.to_dict()
        self.assertEqual(d_none["avg_negativity_score"], 0.0)

        # NaN negativity score
        stats_nan = DailyReportStatistics(
            avg_negativity_score=float("nan"),
        )
        d_nan = stats_nan.to_dict()
        self.assertEqual(d_nan["avg_negativity_score"], 0.0)

        # Inf negativity score
        stats_inf = DailyReportStatistics(
            avg_negativity_score=float("inf"),
        )
        d_inf = stats_inf.to_dict()
        self.assertEqual(d_inf["avg_negativity_score"], 0.0)

        # Valid score
        stats_valid = DailyReportStatistics(
            avg_negativity_score=0.8765,
        )
        d_valid = stats_valid.to_dict()
        self.assertEqual(d_valid["avg_negativity_score"], 0.88)

    # -----------------------------------------------------------------
    # Item 7: Date Parsing in _extract_record_date & ComplaintRecord
    # -----------------------------------------------------------------
    def test_json_writer_extract_record_date_korean_and_two_digit_years(self):
        """_extract_record_date must parse Korean dotted dates and 2-digit years."""
        self.assertEqual(_extract_record_date({"date": "2026.10.25"}), "2026-10-25")
        self.assertEqual(_extract_record_date({"date": "2026. 10. 25."}), "2026-10-25")
        self.assertEqual(_extract_record_date({"created_at": "2026/10/25"}), "2026-10-25")
        self.assertEqual(_extract_record_date({"created_at": "26.10.25"}), "2026-10-25")
        self.assertEqual(_extract_record_date({"timestamp": "26-10-25"}), "2026-10-25")
        self.assertEqual(_extract_record_date({"date": ""}), "")
        self.assertEqual(_extract_record_date({}), "")

    def test_complaint_record_date_str_two_digit_year(self):
        """ComplaintRecord.date_str must parse 2-digit year format."""
        rec = ComplaintRecord(
            id="rec_2digit",
            source="test",
            url="http://example.com",
            title="t",
            author="a",
            created_at="26.10.25",
            vehicle_brand="Kia",
            vehicle_model="EV9",
            defect_category="motor",
            summary="s",
            verbatim_quote="v",
        )
        self.assertEqual(rec.date_str, "2026-10-25")

    # -----------------------------------------------------------------
    # Item 8: RawPost.from_dict None Guards
    # -----------------------------------------------------------------
    def test_raw_post_from_dict_none_comments_and_none_attributes(self):
        """RawPost.from_dict must safely convert None fields without TypeError or literal 'None'."""
        post = RawPost.from_dict({
            "platform": None,
            "post_id": None,
            "url": None,
            "title": None,
            "content": None,
            "comments": None,
            "created_at": None,
            "author": None,
        })
        self.assertEqual(post.platform, "unknown")
        self.assertEqual(post.post_id, "")
        self.assertEqual(post.url, "")
        self.assertEqual(post.title, "")
        self.assertEqual(post.content, "")
        self.assertEqual(post.comments, [])
        self.assertEqual(post.created_at, "")
        self.assertEqual(post.author, "")

        # Also verify comments containing non-string or None items
        post_comments = RawPost.from_dict({
            "comments": ["좋아요", None, 12345],
        })
        self.assertEqual(post_comments.comments, ["좋아요", "12345"])

    # -----------------------------------------------------------------
    # Item 9: ContextualDefectFilter Comment Filtering
    # -----------------------------------------------------------------
    def test_process_post_filters_non_string_comments(self):
        """ContextualDefectFilter.process_post must filter out non-string items without TypeError."""
        defect_filter = ContextualDefectFilter()
        raw_post = RawPost(
            platform="dcinside",
            post_id="post_999",
            url="https://gall.dcinside.com/board/view/?id=car_new1&no=999",
            title="아이오닉5 배터리 결함 발생",
            content="주행 중 경고등 점등",
            comments=[None, 123, "서비스센터 접수함"],  # type: ignore[list-item]
            created_at="2026-10-25T10:00:00Z",
            author="차주1",
        )
        record = defect_filter.process_post(raw_post)
        self.assertIsNotNone(record.id)
        self.assertIn(record.vehicle_brand, ["현대", "Hyundai"])
        self.assertEqual(record.vehicle_model, "아이오닉5")

    # -----------------------------------------------------------------
    # Item 10: Crawlers Case-Insensitive Regex Post ID Extraction
    # -----------------------------------------------------------------
    def test_crawlers_case_insensitive_post_id_regex(self):
        """Crawlers must extract post IDs regardless of 'no=' or 'No=' case."""
        bc = BobaeDreamCrawler()
        dc = DCInsideCrawler()

        # BobaeDream URLs
        b1 = bc.parse_post_detail("<html></html>", "https://www.bobaedream.co.kr/view?code=national&No=111111")
        b2 = bc.parse_post_detail("<html></html>", "https://www.bobaedream.co.kr/view?code=national&no=222222")
        b3 = bc.parse_post_detail("<html></html>", "https://www.bobaedream.co.kr/view?code=national&NO=333333")
        self.assertEqual(b1["post_id"], "111111")
        self.assertEqual(b2["post_id"], "222222")
        self.assertEqual(b3["post_id"], "333333")

        # DCInside URLs
        d1 = dc.parse_post_detail("<html></html>", "https://gall.dcinside.com/board/view/?id=car_new1&no=444444")
        d2 = dc.parse_post_detail("<html></html>", "https://gall.dcinside.com/board/view/?id=car_new1&No=555555")
        d3 = dc.parse_post_detail("<html></html>", "https://gall.dcinside.com/board/view/?id=car_new1&NO=666666")
        self.assertEqual(d1["post_id"], "444444")
        self.assertEqual(d2["post_id"], "555555")
        self.assertEqual(d3["post_id"], "666666")

    # -----------------------------------------------------------------
    # Item 11: Symlink Deduplication in sync_defect_reports
    # -----------------------------------------------------------------
    def test_sync_defect_reports_symlink_deduplication(self):
        """sync_defect_reports must resolve symlinks so symlinked paths are not synced to themselves."""
        with tempfile.TemporaryDirectory() as td:
            base_dir = Path(td)
            real_src = base_dir / "real_dir"
            real_src.mkdir()
            symlink_src = base_dir / "symlink_dir"
            os.symlink(real_src, symlink_src, target_is_directory=True)

            source_file = real_src / "daily_reports.json"
            source_content = (
                '{"generated_at": "2026-10-25T19:00:00Z", "pipeline_version": "1.0.0", '
                '"statistics": {"total_scraped": 1, "total_filtered_defects": 1, '
                '"avg_negativity_score": 0.5, "critical_defect_count": 0}, "reports": []}'
            )
            source_file.write_text(source_content, encoding="utf-8")

            # In DefectTracker: real path and symlinked path point to same physical directory
            dt = DefectTracker(
                root_data_dir=real_src,
                web_data_dir=symlink_src,
                public_data_dir=None,
            )
            synced = dt.sync_defect_reports()
            # Because symlink_src points to real_src, Path.resolve() detects they are the same physical file
            self.assertEqual(synced, [])

    # -----------------------------------------------------------------
    # Item 12: Atomic Writer and Defensive Decimals
    # -----------------------------------------------------------------
    def test_atomic_writer_empty_target_path_and_decimal(self):
        """atomic_write_json must reject empty target_path and serialize Decimal objects."""
        with self.assertRaises(ValueError):
            atomic_write_json({"data": 1}, target_path="")

        with self.assertRaises(ValueError):
            atomic_write_json({"data": 1}, target_path="   ")

        # Decimal serialization
        self.assertEqual(_json_default(Decimal("123.45")), 123.45)
        self.assertEqual(_json_default(Decimal("NaN")), 0.0)
        self.assertEqual(_json_default(Decimal("Infinity")), 0.0)

    # -----------------------------------------------------------------
    # Item 13: Slang Lexicon & robust_decode Guards
    # -----------------------------------------------------------------
    def test_slang_lexicon_none_text_guard(self):
        """find_matching_slang must safely return [] when passed None or empty string."""
        self.assertEqual(find_matching_slang(None), [])  # type: ignore[arg-type]
        self.assertEqual(find_matching_slang(""), [])
        matches = find_matching_slang("ICCU 폭탄 터짐")
        self.assertTrue(any("ICCU" in m.term for m in matches))

    def test_robust_decode_handles_str_input(self):
        """robust_decode must handle string input directly without AttributeError."""
        self.assertEqual(robust_decode("already decoded string"), "already decoded string")
        self.assertEqual(robust_decode(b"hello utf-8"), "hello utf-8")
        self.assertEqual(robust_decode(b""), "")
        self.assertEqual(robust_decode(None), "")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main(verbosity=2)
