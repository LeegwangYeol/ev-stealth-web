"""Swarm audit regression tests for filters/*.py and models/*.py (2026-11-25)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import math
import unittest

from filters.defect_classifier import DefectClassifier
from filters.slang_filter import is_slang_present
from filters.vehicle_matcher import BRAND_TESLA, extract_vehicle_info
from models.complaint import (
    ComplaintRecord,
    DSIBreakdown,
    DailyReportPayload,
    DailyReportStatistics,
    _safe_clamp,
    _safe_float,
    _safe_round,
    parse_date_str,
    validate_report_entry,
)


class TestSwarmPyFiltersModels20261125(unittest.TestCase):
    def setUp(self) -> None:
        self.clf = DefectClassifier()

    def test_negative_zero_normalized_to_positive_zero(self) -> None:
        """_safe_float, _safe_round, _safe_clamp, and ComplaintRecord must never emit -0.0."""
        self.assertEqual(math.copysign(1.0, _safe_float("-0.0")), 1.0)
        self.assertEqual(math.copysign(1.0, _safe_round(-0.000001, 4)), 1.0)
        self.assertEqual(math.copysign(1.0, _safe_clamp(-0.0, 0.0, 1.0)), 1.0)

        rec = ComplaintRecord(
            id="neg0",
            source="clien",
            url="",
            title="테스트",
            author="",
            created_at="2026-11-25",
            vehicle_brand="Hyundai",
            vehicle_model="아이오닉5",
            defect_category="BATTERY_CHARGING",
            summary="",
            verbatim_quote="테스트 인용문",
            sentiment_polarity=-0.000001,
            negativity_score=-0.000001,
            severity_index=-0.0001,
            confidence_score=-0.000001,
        )
        d = rec.to_dict()
        for key in ("sentiment_polarity", "negativity_score", "severity_index", "confidence_score"):
            self.assertEqual(math.copysign(1.0, d[key]), 1.0)
        self.assertNotIn("-0.0", json.dumps(d))

    def test_complaint_record_slang_terms_non_iterable_and_bytes_resilience(self) -> None:
        """ComplaintRecord handles scalar, bool, bytes, and invisible-char slang_terms_detected safely."""
        for bad_slang, expected in [
            (123, []),
            (True, []),
            (False, []),
            ({"a": 1}, []),
            (b"ICCU,\xeb\x8b\xa8\xec\xb0\xa8", ["ICCU", "단차"]),
            (["", "\x00\u200b", None, False, "ICCU"], ["ICCU"]),
        ]:
            rec = ComplaintRecord(
                id="s1",
                source="clien",
                url="",
                title="제목",
                author="",
                created_at="",
                vehicle_brand="Hyundai",
                vehicle_model="아이오닉5",
                defect_category="BATTERY_CHARGING",
                summary="",
                verbatim_quote="인용",
                slang_terms_detected=bad_slang,  # type: ignore[arg-type]
            )
            self.assertEqual(rec.slang_terms_detected, expected)

    def test_daily_report_payload_nan_inf_and_none_fields_json_safe(self) -> None:
        """DailyReportPayload.to_dict() produces RFC 8259 compliant JSON even with NaN/Inf/None inputs."""
        payload = DailyReportPayload.from_dict(
            {
                "generated_at": "2026-11-25T00:00:00Z",
                "reports": [
                    {
                        "id": "r1",
                        "title": "ICCU 고장",
                        "severity_index": float("nan"),
                        "negativity_score": float("inf"),
                        "sentiment_polarity": -0.0,
                        "extra": [1.0, float("nan"), b"test"],
                    }
                ],
                "top_defect_categories": [{"category": "BATTERY_CHARGING", "avg": float("nan")}],
            }
        )
        serialized = json.dumps(payload.to_dict(), allow_nan=False)
        parsed = json.loads(serialized)
        self.assertEqual(parsed["reports"][0]["severity_index"], 0.0)
        self.assertEqual(parsed["reports"][0]["negativity_score"], 0.0)
        self.assertEqual(parsed["reports"][0]["extra"], [1.0, 0.0, "test"])

        direct = DailyReportPayload(
            generated_at="2026-11-25T00:00:00Z",
            statistics=None,  # type: ignore[arg-type]
            reports=None,  # type: ignore[arg-type]
            total_complaints_today=float("nan"),  # type: ignore[arg-type]
            top_defect_categories=None,  # type: ignore[arg-type]
            quarantined_reports=None,  # type: ignore[arg-type]
        )
        direct_dict = direct.to_dict()
        self.assertEqual(direct_dict["total_complaints_today"], 0)
        self.assertEqual(direct_dict["reports"], [])
        json.dumps(direct_dict, allow_nan=False)

    def test_validate_report_entry_rejects_invisible_only_id_or_content(self) -> None:
        """Entries whose id or text consists solely of null bytes / BiDi / ZWSP chars must fail validation."""
        ok_id, _ = validate_report_entry({"id": "\x00\u200b\u202e", "title": "실제 제목"})
        self.assertFalse(ok_id)
        ok_txt, _ = validate_report_entry({"id": "valid-1", "title": "\x00\u200b\u202e"})
        self.assertFalse(ok_txt)

    def test_parse_date_str_trailing_digit_boundary_and_relative_days_ago(self) -> None:
        """_RE_DATE_2 must not match 4-digit suffixes like 26.10.2500; N일 전 resolves accurately."""
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%d")

        self.assertEqual(parse_date_str("26.10.2500"), today_utc)
        self.assertEqual(parse_date_str("26.10.25"), "2026-10-25")
        self.assertEqual(parse_date_str("3일 전"), three_days_ago)
        self.assertEqual(parse_date_str("3일전"), three_days_ago)

    def test_classifier_bytes_input_and_false_negation_guards(self) -> None:
        """classify/process_post decode UTF-8/CP949 bytes; '이음새' and '이상 없음' must not invert real defects."""
        utf8_post = "내 차 아이오닉5 ICCU 폭탄 터져서 고속도로에서 멈춤 ㅠㅠ".encode("utf-8")
        rec_utf8 = self.clf.classify(utf8_post)
        self.assertTrue(rec_utf8.is_authentic_defect)
        self.assertEqual(rec_utf8.defect_category, "BATTERY_CHARGING")

        cp949_post = "내 차 아이오닉5 주행 중 ICCU 경고등 뜨고 멈춤".encode("cp949")
        rec_cp949 = self.clf.process_post(cp949_post)
        self.assertTrue(rec_cp949.is_authentic_defect)

        # '이음새' (expansion joint) must not be detected as negated '이음' (abnormal noise)
        joint_res = self.clf.evaluate_stage3_scoping("고가도로 이음새 지나갔고 단차는 없고 이상도 없어요")
        self.assertNotIn("이음", joint_res["negated_defects"])

        # Negated generic '이상' must not invert safety-critical '절연 저항 이상'
        insul_res = self.clf.evaluate_stage3_scoping("내 차 세차 후 절연 저항 이상 경고등 떴는데 타이어는 이상 없음")
        self.assertLess(insul_res["polarity"], -0.5)

    def test_slang_filter_and_vehicle_matcher_edge_cases(self) -> None:
        """is_slang_present handles bytes/fullwidth/bool; Model Y 주니퍼 resolves to Model Y Juniper."""
        self.assertFalse(is_slang_present("ICCU 터짐", True))  # type: ignore[arg-type]
        self.assertTrue(is_slang_present("ICCU 터짐", b"iccu"))  # type: ignore[arg-type]
        self.assertTrue(is_slang_present("ICCU 터짐", "ＩＣＣＵ"))

        self.assertEqual(extract_vehicle_info("Model Y 주니퍼 단차"), (BRAND_TESLA, "Model Y Juniper"))
        self.assertEqual(extract_vehicle_info("모델 Y juniper 출고"), (BRAND_TESLA, "Model Y Juniper"))


if __name__ == "__main__":
    unittest.main()
