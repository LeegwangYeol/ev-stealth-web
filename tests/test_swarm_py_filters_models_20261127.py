"""Swarm audit regression tests for filters/*.py and models/*.py (2026-11-27)."""

from __future__ import annotations

import json
import math
import time
import unittest

from filters.defect_classifier import DefectClassifier
from filters.spam_filter import SpamFilter
from filters.vehicle_matcher import (
    BRAND_BYD,
    BRAND_OTHER,
    BRAND_TESLA,
    MODEL_RULES,
    extract_vehicle_info,
)
from models.complaint import (
    ComplaintRecord,
    DSIBreakdown,
    DailyReportPayload,
    RawPost,
    normalize_category,
    normalize_severity,
)
from models.defect_report import DefectReport


class TestSwarmPyFiltersModels20261127(unittest.TestCase):
    def setUp(self) -> None:
        self.clf = DefectClassifier()
        self.sf = SpamFilter()

    def test_vehicle_matcher_m3_latency_and_boundaries(self) -> None:
        """Model 3 pattern avoids redundant lookbehind passes; Atto 300 and 모델와이단차 behave accurately."""
        model3_pat = next(p for p, name, _ in MODEL_RULES if name == "Model 3")
        payload = "모" * 50_000
        t0 = time.perf_counter()
        self.assertIsNone(model3_pat.search(payload))
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.assertLess(elapsed_ms, 50.0, f"Model 3 regex latency regression: {elapsed_ms:.2f}ms")

        # Boundary guards for Atto 3 vs Atto 300
        self.assertEqual(extract_vehicle_info("BYD 아토3 출고 후기"), (BRAND_BYD, "Atto 3"))
        self.assertEqual(extract_vehicle_info("아토300 테스트 장비"), (BRAND_OTHER, "전기차"))

        # Unspaced 모델와이단차 resolves to Model Y while 모델 와이퍼 remains excluded
        self.assertEqual(extract_vehicle_info("모델와이단차 심해서 인수거부"), (BRAND_TESLA, "Model Y"))
        self.assertEqual(extract_vehicle_info("구형 모델 와이퍼 교체"), (BRAND_OTHER, "전기차"))

    def test_concessive_hande_boundary_does_not_invert_simhande(self) -> None:
        """'한데' inside '심한데'/'조용한데' must not trigger concessive reweighting."""
        text = "내 차 단차 심한데 승차감은 좋아요"
        s3 = self.clf.evaluate_stage3_scoping(text)
        self.assertLess(s3["polarity"], 0.0)

        strong_text = "내 차 단차랑 누수 심한데 승차감은 좋아요"
        s3_strong = self.clf.evaluate_stage3_scoping(strong_text)
        self.assertLess(s3_strong["polarity"], -0.3)

        rec = self.clf.classify(strong_text)
        self.assertTrue(rec.is_authentic_defect, f"Expected authentic defect, got: {rec.filter_reason}")
        self.assertEqual(rec.defect_category, "BUILD_QUALITY")

        # Standalone '한데' still splits concessive clauses properly
        s3_conc = self.clf.evaluate_stage3_scoping("승차감은 좋긴 한데 브레이크가 먹통입니다")
        self.assertLess(s3_conc["polarity"], -0.4)

    def test_spoken_operational_malfunction_predicates_pass_stage2(self) -> None:
        """Conjugated Korean operational malfunctions (안 들어요, 안 걸려요, 안 빠져요, 안 열려요) pass Stage 2."""
        authentic_cases = [
            ("내 차 브레이크가 안 들어요 서비스센터 가야하나요", "DRIVING_POWERTRAIN"),
            ("내 차 충전건이 안 빠져요 서비스센터 불렀습니다", "BATTERY_CHARGING"),
            ("내 차 도어캐치가 안 열려요 출근을 못 합니다", "BUILD_QUALITY"),
            ("내 차 오늘 아침부터 시동이 안 걸려요 12V 방전인가요", "BATTERY_CHARGING"),
        ]
        for text, expected_cat in authentic_cases:
            is_owner, reason = self.clf.evaluate_stage2_ownership(text)
            self.assertTrue(is_owner, f"Stage 2 rejected authentic defect '{text}': {reason}")
            rec = self.clf.classify(text)
            self.assertTrue(rec.is_authentic_defect, f"Gate rejected '{text}': {rec.filter_reason}")
            self.assertEqual(rec.defect_category, expected_cat)

        # Idioms like '마음에 안 들어요' must not become operational malfunction symptoms
        is_owner_idiom, _ = self.clf.evaluate_stage2_ownership("내 차 색상이 마음에 안 들어요")
        self.assertFalse(is_owner_idiom)

    def test_spam_filter_inquiry_kayo_suffix_filtered_when_no_defect_context(self) -> None:
        """General '~까요?' questions without defect/component context are discarded at Stage 1."""
        self.assertTrue(self.sf.is_spam("오늘 점심 뭐 먹을까요?"))
        self.assertTrue(self.sf.is_spam("아이오닉5 색상 어떤게 나을까요?"))
        # Authentic defect complaint ending in ~까요? is still protected
        self.assertFalse(self.sf.is_spam("내 차 ICCU 고장인데 서비스센터 가야 할까요?"))

    def test_models_sanitization_and_invariants(self) -> None:
        """normalize_category/normalize_severity handle fullwidth/bytes/null/bool; model invariants hold."""
        self.assertEqual(normalize_category("ＢＡＴＴＥＲＹ"), "BATTERY_CHARGING")
        self.assertEqual(normalize_category(b"BATTERY_CHARGING"), "BATTERY_CHARGING")
        self.assertEqual(normalize_category("BATTERY\x00"), "BATTERY_CHARGING")
        self.assertEqual(normalize_category(True), "BUILD_QUALITY")

        self.assertEqual(normalize_severity("ＨＩＧＨ"), "HIGH")
        self.assertEqual(normalize_severity(b"CRITICAL"), "CRITICAL")
        self.assertEqual(normalize_severity("high\x00"), "HIGH")
        self.assertEqual(normalize_severity(True, 8.5), "CRITICAL")

        # ComplaintRecord.from_dict sanitizes category before alias lookup and clears invisible-only severity
        rec_dirty = ComplaintRecord.from_dict(
            {
                "id": "r1",
                "title": "ICCU 결함",
                "defect_category": "배터리\x00",
                "severity": "\x00\u200b",
            }
        )
        self.assertEqual(rec_dirty.defect_category, "BATTERY_CHARGING")
        self.assertIsNone(rec_dirty.severity)

        # ComplaintRecord coerces is_authentic_defect to strict bool
        rec_none_auth = ComplaintRecord(
            id="r2",
            source="clien",
            url="",
            title="테스트",
            author="",
            created_at="2026-11-27",
            vehicle_brand="Hyundai",
            vehicle_model="아이오닉5",
            defect_category="BATTERY_CHARGING",
            summary="요약",
            verbatim_quote="인용",
            is_authentic_defect=None,  # type: ignore[arg-type]
        )
        self.assertIs(rec_none_auth.is_authentic_defect, True)
        rec_str_false = ComplaintRecord(
            id="r3",
            source="clien",
            url="",
            title="테스트",
            author="",
            created_at="2026-11-27",
            vehicle_brand="Hyundai",
            vehicle_model="아이오닉5",
            defect_category="BATTERY_CHARGING",
            summary="요약",
            verbatim_quote="인용",
            is_authentic_defect="false",  # type: ignore[arg-type]
        )
        self.assertIs(rec_str_false.is_authentic_defect, False)

        # DSIBreakdown sanitizes and clamps attributes directly in __post_init__
        dsi = DSIBreakdown(
            safety=float("nan"),
            functional=15.0,
            economic=-3.0,
            social=-0.0,
            convenience=True,  # type: ignore[arg-type]
        )
        self.assertEqual(dsi.safety, 0.0)
        self.assertEqual(dsi.functional, 10.0)
        self.assertEqual(dsi.economic, 0.0)
        self.assertEqual(math.copysign(1.0, dsi.social), 1.0)
        self.assertEqual(dsi.convenience, 0.0)
        json.dumps(dsi.to_dict(), allow_nan=False)

        # DefectReport.from_dict clones DSIBreakdown instead of aliasing mutable instance
        rec_with_dsi = ComplaintRecord(
            id="r4",
            source="clien",
            url="",
            title="제목",
            author="",
            created_at="2026-11-27",
            vehicle_brand="Hyundai",
            vehicle_model="아이오닉5",
            defect_category="BATTERY_CHARGING",
            summary="요약",
            verbatim_quote="인용",
            dsi_breakdown=DSIBreakdown(safety=8.0),
        )
        dr = DefectReport.from_dict(rec_with_dsi)
        self.assertIsNotNone(dr.dsi_breakdown)
        self.assertIsNot(dr.dsi_breakdown, rec_with_dsi.dsi_breakdown)

        # RawPost.from_dict accepts string comments consistently with RawPost.__init__
        rp = RawPost.from_dict({"title": "단차", "comments": "첫 댓글"})
        self.assertEqual(rp.comments, ["첫 댓글"])

        # DailyReportPayload.validate_payload rejects invisible-only generated_at
        ok_payload, errs = DailyReportPayload.validate_payload(
            {"generated_at": "\x00\u200b", "reports": []}
        )
        self.assertFalse(ok_payload)
        self.assertTrue(any("generated_at" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
