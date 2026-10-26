"""
tests/test_backend_cycle19_remediation.py - Unit test suite locking in all Cycle 19 Backend Remediations.

Validates:
1. RawPost integer id=0 falsy coercion protection.
2. RawPost.from_dict source key fallback alongside platform.
3. ComplaintRecord severity_tier whitespace resilience (.strip()).
4. ComplaintRecord null slang_terms_detected defensive list fallback.
5. ComplaintRecord sentiment_tier polarity boundaries and NaN/Inf guards.
6. vehicle_matcher Hyundai Motor and Genesis brand recognition.
7. vehicle_matcher Casper EV and Kona Electric keyword symmetry.
8. vehicle_matcher model collision protection (BMW M3 vs Model 3, BYD Seal vs oil seal).
9. report_generator _safe_sev string severity tier mapping to numeric DSI scores.
10. crawlers 1-2 digit date parsing in BobaeDream and DCInside.
11. subsidy_tracker calculate_price_cap_ratio statutory boundaries.
12. subsidy_tracker calculate_net_subsidy over-cap ratio clamping and zero max_national division safety.
13. defect_filter rhetorical question owner complaint acceptance.
14. defect_filter sarcastic praise polarity inversion and authentic defect gate passage.
15. defect_filter negated defect praise positive polarity filtering.
16. atomic_writer sanitize_nan_inf fuzzing on deeply nested structures and Decimal serialization.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import json
import math
import os
from pathlib import Path
import tempfile
import unittest

from crawlers.bobaedream import BobaeDreamCrawler, _normalize_iso_timestamp as bd_ts
from crawlers.dcinside import DCInsideCrawler, _normalize_iso_timestamp as dc_ts
from filters.defect_filter import ContextualDefectFilter
from filters.vehicle_matcher import extract_vehicle_info
from models.complaint import ComplaintRecord, RawPost
from tracker.atomic_writer import _json_default, atomic_write_json, sanitize_nan_inf
from tracker.report_generator import ReportGenerator, _safe_sev
from tracker.subsidy_tracker import calculate_net_subsidy, calculate_price_cap_ratio


class TestBackendCycle19Remediation(unittest.TestCase):
    """Rigorous test cases locking in Cycle 19 backend hardening fixes."""

    # -----------------------------------------------------------------
    # Item 1: RawPost ID Falsy Coercion Guard
    # -----------------------------------------------------------------
    def test_01_raw_post_id_zero_falsy_protection(self) -> None:
        """RawPost must preserve integer id=0 as string '0' instead of empty string."""
        post1 = RawPost(id=0)
        self.assertEqual(post1.post_id, "0")
        self.assertEqual(post1.id, "0")

        post2 = RawPost(post_id=0)
        self.assertEqual(post2.post_id, "0")
        self.assertEqual(post2.id, "0")

        post3 = RawPost(id="0")
        self.assertEqual(post3.post_id, "0")

        post4 = RawPost(id=12345)
        self.assertEqual(post4.post_id, "12345")

    # -----------------------------------------------------------------
    # Item 2: RawPost.from_dict Source Key Fallback
    # -----------------------------------------------------------------
    def test_02_raw_post_from_dict_source_fallback(self) -> None:
        """RawPost.from_dict must support 'source' key alongside 'platform'."""
        p1 = RawPost.from_dict({"source": "dcinside", "id": "100"})
        self.assertEqual(p1.platform, "dcinside")
        self.assertEqual(p1.source, "dcinside")

        p2 = RawPost.from_dict({"platform": "bobaedream", "id": "200"})
        self.assertEqual(p2.platform, "bobaedream")

        p3 = RawPost.from_dict({"source": "custom_src", "platform": "fallback_plat"})
        self.assertEqual(p3.platform, "custom_src")

        p4 = RawPost.from_dict({})
        self.assertEqual(p4.platform, "unknown")

    # -----------------------------------------------------------------
    # Item 3: ComplaintRecord.severity_tier Whitespace Resilience
    # -----------------------------------------------------------------
    def test_03_complaint_record_severity_tier_whitespace_resilience(self) -> None:
        """ComplaintRecord.severity_tier must strip leading/trailing whitespace."""
        def _make_rec(sev: Any) -> ComplaintRecord:
            return ComplaintRecord(
                id="c1",
                source="dcinside",
                url="https://gall.dcinside.com/1",
                title="t",
                author="a",
                created_at="2026-10-26",
                vehicle_brand="Hyundai",
                vehicle_model="아이오닉5",
                defect_category="BATTERY_CHARGING",
                summary="s",
                verbatim_quote="v",
                severity=sev,
            )

        self.assertEqual(_make_rec(" critical ").severity_tier, "CRITICAL")
        self.assertEqual(_make_rec("warning\n").severity_tier, "WARNING")
        self.assertEqual(_make_rec("\tcaution\t").severity_tier, "CAUTION")
        self.assertEqual(_make_rec("info  ").severity_tier, "INFO")
        self.assertEqual(_make_rec("  LOW  ").severity_tier, "LOW")

    # -----------------------------------------------------------------
    # Item 4: ComplaintRecord Slang Terms Null Guard
    # -----------------------------------------------------------------
    def test_04_complaint_record_slang_terms_null_guard(self) -> None:
        """ComplaintRecord must return empty list [] when slang_terms_detected is None."""
        rec = ComplaintRecord(
            id="c2",
            source="bobaedream",
            url="https://bobaedream.co.kr/1",
            title="t",
            author="a",
            created_at="2026-10-26",
            vehicle_brand="Kia",
            vehicle_model="EV6",
            defect_category="DRIVING_POWERTRAIN",
            summary="s",
            verbatim_quote="v",
            slang_terms_detected=None,
        )
        self.assertEqual(rec.to_dict()["slang_terms_detected"], [])
        self.assertEqual(rec.to_admin_report_dict()["slang_tags"], [])
        self.assertEqual(rec.to_admin_report_dict()["slang_terms_detected"], [])

    # -----------------------------------------------------------------
    # Item 5: ComplaintRecord Sentiment Tier Boundaries
    # -----------------------------------------------------------------
    def test_05_complaint_record_sentiment_tier_boundaries(self) -> None:
        """ComplaintRecord.sentiment_tier must categorize polarity across statutory boundary transitions."""
        def _tier(pol: Any) -> str:
            return ComplaintRecord(
                id="c3",
                source="dcinside",
                url="http://example.com",
                title="t",
                author="a",
                created_at="2026-10-26",
                vehicle_brand="Tesla",
                vehicle_model="Model Y",
                defect_category="SOFTWARE_ELECTRONICS",
                summary="s",
                verbatim_quote="v",
                sentiment_polarity=pol,
            ).sentiment_tier

        self.assertEqual(_tier(0.30), "POSITIVE")
        self.assertEqual(_tier(0.29), "NEUTRAL")
        self.assertEqual(_tier(-0.29), "NEUTRAL")
        self.assertEqual(_tier(-0.30), "NEGATIVE")
        self.assertEqual(_tier(-0.69), "NEGATIVE")
        self.assertEqual(_tier(-0.70), "STRONGLY_NEGATIVE")
        self.assertEqual(_tier(None), "NEUTRAL")
        self.assertEqual(_tier(float("nan")), "NEUTRAL")
        self.assertEqual(_tier(float("inf")), "NEUTRAL")

    # -----------------------------------------------------------------
    # Item 6: Vehicle Matcher Hyundai Motor and Genesis
    # -----------------------------------------------------------------
    def test_06_vehicle_matcher_hyundai_motor_and_genesis(self) -> None:
        """vehicle_matcher must resolve '현대자동차' and Genesis models correctly."""
        b1, m1 = extract_vehicle_info("현대자동차 아이오닉 5 출고")
        self.assertEqual(b1, "Hyundai")
        self.assertEqual(m1, "아이오닉5")

        b2, m2 = extract_vehicle_info("제네시스 GV60 충전 불량")
        self.assertEqual(b2, "Hyundai")
        self.assertEqual(m2, "GV60")

        b3, m3 = extract_vehicle_info("제네시스 GV70 전동화 모델")
        self.assertEqual(b3, "Hyundai")
        self.assertEqual(m3, "GV70 EV")

        b4, m4 = extract_vehicle_info("제네시스 G80 전동화 모델")
        self.assertEqual(b4, "Hyundai")
        self.assertEqual(m4, "G80 EV")

        b5, m5 = extract_vehicle_info("제네시스 서비스센터 입고")
        self.assertEqual(b5, "Hyundai")

    # -----------------------------------------------------------------
    # Item 7: Vehicle Matcher Casper and Kona Symmetry
    # -----------------------------------------------------------------
    def test_07_vehicle_matcher_casper_and_kona_symmetry(self) -> None:
        """vehicle_matcher must match casper ev and kona electric bidirectionally."""
        b1, m1 = extract_vehicle_info("캐스퍼 ev 사전예약")
        self.assertEqual(b1, "Hyundai")
        self.assertEqual(m1, "캐스퍼 일렉트릭")

        b2, m2 = extract_vehicle_info("코나 electric 배터리 교체")
        self.assertEqual(b2, "Hyundai")
        self.assertEqual(m2, "코나 EV")

        b3, m3 = extract_vehicle_info("casper ev 출고 후기")
        self.assertEqual(b3, "Hyundai")
        self.assertEqual(m3, "캐스퍼 일렉트릭")

        b4, m4 = extract_vehicle_info("kona electric 주행거리")
        self.assertEqual(b4, "Hyundai")
        self.assertEqual(m4, "코나 EV")

    # -----------------------------------------------------------------
    # Item 8: Vehicle Matcher Collision Boundaries
    # -----------------------------------------------------------------
    def test_08_vehicle_matcher_collision_boundaries(self) -> None:
        """vehicle_matcher must avoid false-positive collisions across distinct vehicle and part names."""
        # BMW M3 must NOT match Tesla Model 3
        b1, m1 = extract_vehicle_info("BMW M3 컴페티션 배기음")
        self.assertEqual(b1, "Other")
        self.assertEqual(m1, "BMW M3")

        # BYD Seal vehicle must match
        b2, m2 = extract_vehicle_info("BYD 씰 신차 사전예약")
        self.assertEqual(b2, "BYD")
        self.assertEqual(m2, "씰")

        # Weatherstrip/door oil seal must NOT match BYD Seal
        b3, m3 = extract_vehicle_info("도어 오일 씰 누유 수리")
        self.assertEqual(b3, "Other")
        self.assertEqual(m3, "전기차")

    # -----------------------------------------------------------------
    # Item 9: Report Generator String Severity Tier Mapping
    # -----------------------------------------------------------------
    def test_09_report_generator_string_severity_tier_mapping(self) -> None:
        """_safe_sev must map string severity tiers to numeric DSI values for executive briefings."""
        self.assertEqual(_safe_sev({"severity": "CRITICAL"}), 10.0)
        self.assertEqual(_safe_sev({"severity": "WARNING"}), 7.0)
        self.assertEqual(_safe_sev({"severity": "CAUTION"}), 4.0)
        self.assertEqual(_safe_sev({"severity": "INFO"}), 1.0)
        self.assertEqual(_safe_sev({"severity": " critical "}), 10.0)

        rg = ReportGenerator()
        reports = [{
            "id": "rep_crit_1",
            "title": "전기차 ICCU 고장 발생",
            "severity": "CRITICAL",
            "defect_category": "BATTERY_CHARGING",
            "vehicle_brand": "Hyundai",
            "vehicle_model": "아이오닉5",
            "url": "https://example.com/iccu",
            "date": "2026-10-26",
            "summary": "주행 중 출력 제한",
            "verbatim_quote": "ICCU 터졌습니다",
        }]
        briefing = rg.generate_defect_briefing(reports)
        self.assertIn("## 🚨 긴급 주의 결함 사례", briefing)
        self.assertIn("전기차 ICCU 고장 발생", briefing)

    # -----------------------------------------------------------------
    # Item 10: Crawlers 1-2 Digit Date Parsing
    # -----------------------------------------------------------------
    def test_10_crawlers_one_to_two_digit_date_parsing(self) -> None:
        """BobaeDream and DCInside crawlers must parse 1 or 2 digit months and days."""
        self.assertTrue(bd_ts("2026.1.5").startswith("2026-01-05"))
        self.assertTrue(bd_ts("2026. 1. 5.").startswith("2026-01-05"))
        self.assertTrue(bd_ts("2026-1-5").startswith("2026-01-05"))
        self.assertTrue(bd_ts("2026.10.5").startswith("2026-10-05"))
        self.assertTrue(bd_ts("2026.1.25").startswith("2026-01-25"))

        self.assertTrue(dc_ts("2026.1.5").startswith("2026-01-05"))
        self.assertTrue(dc_ts("2026/1/5").startswith("2026-01-05"))
        self.assertTrue(dc_ts("2026-1-5").startswith("2026-01-05"))

    # -----------------------------------------------------------------
    # Item 11: Subsidy Tracker Exact Price Cap Boundaries
    # -----------------------------------------------------------------
    def test_11_subsidy_tracker_exact_price_cap_boundaries(self) -> None:
        """calculate_price_cap_ratio must strictly follow statutory threshold brackets."""
        self.assertEqual(calculate_price_cap_ratio(-10_000_000), 0.0)
        self.assertEqual(calculate_price_cap_ratio(0), 0.0)
        self.assertEqual(calculate_price_cap_ratio(30_000_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_000_000), 1.0)
        self.assertEqual(calculate_price_cap_ratio(55_000_001), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_000), 0.5)
        self.assertEqual(calculate_price_cap_ratio(85_000_001), 0.0)
        self.assertEqual(calculate_price_cap_ratio(100_000_000), 0.0)

    # -----------------------------------------------------------------
    # Item 12: Subsidy Tracker calculate_net_subsidy Edge Cases
    # -----------------------------------------------------------------
    def test_12_subsidy_tracker_calculate_net_subsidy_over_cap_and_zero_max(self) -> None:
        """calculate_net_subsidy must clamp ratio to 1.0 when over-cap and avoid zero division."""
        # Over-cap national subsidy: model_national (7M) > max_national (6.5M)
        res_over = calculate_net_subsidy(
            model_national=7_000_000,
            max_national=6_500_000,
            max_local=3_000_000,
            msrp=50_000_000,
        )
        self.assertEqual(res_over["local_subsidy_krw"], 3_000_000)
        self.assertEqual(res_over["total_subsidy_krw"], 10_000_000)
        self.assertEqual(res_over["net_price_krw"], 40_000_000)
        self.assertEqual(res_over["price_cap_ratio"], 1.0)

        # Zero max_national: avoids zero division
        res_zero = calculate_net_subsidy(
            model_national=6_500_000,
            max_national=0,
            max_local=3_000_000,
            msrp=50_000_000,
        )
        self.assertEqual(res_zero["local_subsidy_krw"], 0)
        self.assertEqual(res_zero["total_subsidy_krw"], 6_500_000)
        self.assertEqual(res_zero["price_cap_ratio"], 1.0)

    # -----------------------------------------------------------------
    # Item 13: Defect Filter Rhetorical Question Complaints
    # -----------------------------------------------------------------
    def test_13_defect_filter_rhetorical_question_owner_complaints(self) -> None:
        """ContextualDefectFilter must accept rhetorical question complaints from owners."""
        filter_inst = ContextualDefectFilter()
        post1 = RawPost(
            platform="dcinside",
            post_id="post_rq_1",
            url="https://gall.dcinside.com/1",
            title="아이오닉5 ICCU 퍽 터지는 소리 났는데 원래 이런가요?",
            content="고속도로에서 갑자기 멈췄습니다",
            created_at="2026-10-26",
            author="ioniq_owner",
        )
        res1 = filter_inst.process_post(post1)
        self.assertTrue(res1.is_authentic_defect)

        post2 = RawPost(
            platform="bobaedream",
            post_id="post_rq_2",
            url="https://bobaedream.co.kr/2",
            title="EV6 타다가 고속도로에서 멈췄는데 정상인가요?",
            content="주행 중 시동 꺼짐 발생했습니다",
            created_at="2026-10-26",
            author="ev6_owner",
        )
        res2 = filter_inst.process_post(post2)
        self.assertTrue(res2.is_authentic_defect)

    # -----------------------------------------------------------------
    # Item 14: Defect Filter Sarcastic Praise Inversion
    # -----------------------------------------------------------------
    def test_14_defect_filter_sarcastic_praise_inversion(self) -> None:
        """ContextualDefectFilter must invert sarcastic praise to negative polarity."""
        filter_inst = ContextualDefectFilter()
        post = RawPost(
            platform="bobaedream",
            post_id="post_sarcasm_1",
            url="https://bobaedream.co.kr/view?code=electric&No=3001",
            title="출고 후기",
            content="출고한 내 차 비 오는 날 서브트렁크 워터파크 개장함 짱개차 폼 미쳤다 ㅋㅋㅋ",
            created_at="2026-10-26",
            author="sarcastic_owner",
        )
        res = filter_inst.process_post(post)
        self.assertTrue(res.is_authentic_defect)
        self.assertLessEqual(res.sentiment_polarity, -0.70)
        self.assertGreaterEqual(res.severity_index, 4.0)

    # -----------------------------------------------------------------
    # Item 15: Defect Filter Negated Defect Praise Filtering
    # -----------------------------------------------------------------
    def test_15_defect_filter_negated_defect_praise_filtering(self) -> None:
        """ContextualDefectFilter must filter out praise that negates defects."""
        filter_inst = ContextualDefectFilter()
        post = RawPost(
            platform="bobaedream",
            post_id="post_praise_1",
            url="https://bobaedream.co.kr/view?code=national&No=4001",
            title="완전 양품 출고",
            content="단차 전혀 없고 잡소리도 1도 안 납니다 완전 양품이네요",
            created_at="2026-10-26",
            author="happy_owner",
        )
        res = filter_inst.process_post(post)
        self.assertFalse(res.is_authentic_defect)

    # -----------------------------------------------------------------
    # Item 16: Atomic Writer Fuzzing on Nested Structures
    # -----------------------------------------------------------------
    def test_16_atomic_writer_fuzz_nan_inf_nested_structures(self) -> None:
        """atomic_writer must sanitize nested NaN/Inf and serialize Decimal/Enum objects safely."""
        nested = {
            "list": [1.0, float("nan"), float("inf"), float("-inf")],
            "tuple": (2.0, float("nan")),
            "set": {3.0, float("inf")},
            "dict": {"nested_nan": float("nan")},
        }
        san = sanitize_nan_inf(nested)
        self.assertEqual(san["list"], [1.0, 0.0, 0.0, 0.0])
        self.assertEqual(san["tuple"], [2.0, 0.0])
        self.assertIn(0.0, san["set"])
        self.assertEqual(san["dict"]["nested_nan"], 0.0)

        # Decimal and Enum serialization in _json_default
        class TestSeverity(Enum):
            CRITICAL = "CRITICAL"

        self.assertEqual(_json_default(Decimal("1893.4")), 1893.4)
        self.assertEqual(_json_default(Decimal("NaN")), 0.0)
        self.assertEqual(_json_default(Decimal("Infinity")), 0.0)
        self.assertEqual(_json_default(TestSeverity.CRITICAL), "CRITICAL")
        self.assertEqual(_json_default(frozenset([1, 2])), [1, 2])
        self.assertEqual(_json_default(Path("/tmp/ev")), "/tmp/ev")

        # Atomic write to temporary file
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "test_nested.json"
            atomic_write_json(nested, target)
            self.assertTrue(target.exists())
            loaded = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(loaded["list"], [1.0, 0.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
