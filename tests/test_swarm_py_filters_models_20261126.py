"""Swarm audit regression tests for filters/*.py and models/*.py (2026-11-26)."""

from __future__ import annotations

import json
import time
import unittest

from filters.defect_classifier import DefectClassifier, sanitize_text
from filters.slang_lexicon import find_matching_slang
from filters.spam_filter import (
    _BOUNDED_FINANCIAL_REGEXES,
    SpamFilter,
    sanitize_input,
)
from filters.vehicle_matcher import (
    BRAND_OTHER,
    BRAND_TESLA,
    _sanitize_matcher_text,
    extract_vehicle_info,
)
from models.complaint import (
    ComplaintRecord,
    DSIBreakdown,
    sanitize_string,
    validate_report_entry,
)


class TestSwarmPyFiltersModels20261126(unittest.TestCase):
    def setUp(self) -> None:
        self.clf = DefectClassifier()
        self.sf = SpamFilter()

    def test_juga_financial_regex_no_redos_on_50k_hangul(self) -> None:
        """_BOUNDED_FINANCIAL_REGEXES['주가'] must run in linear time on 50k Hangul chars."""
        pat = _BOUNDED_FINANCIAL_REGEXES["주가"]
        payload = "가" * 50_000

        t0 = time.perf_counter()
        self.assertIsNone(pat.search(payload))
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.assertLess(elapsed_ms, 250.0, f"ReDoS latency regression: {elapsed_ms:.2f}ms")

        self.assertIsNotNone(pat.search("현대차주가"))
        self.assertIsNotNone(pat.search("테슬라 주가 폭락"))
        self.assertIsNone(pat.search("원 차주가 불만 제기"))
        self.assertIsNone(pat.search("가차주가"))

    def test_boolean_true_and_false_rejected_consistently_by_all_sanitizers(self) -> None:
        """All filter and model sanitizers must return empty results for bool True/False."""
        self.assertEqual(sanitize_text(True), "")
        self.assertEqual(sanitize_text(False), "")
        self.assertEqual(sanitize_input(True), "")
        self.assertEqual(sanitize_input(False), "")
        self.assertEqual(sanitize_string(True), "")
        self.assertEqual(sanitize_string(False), "")
        self.assertEqual(_sanitize_matcher_text(True, 1000), "")
        self.assertEqual(_sanitize_matcher_text(False, 1000), "")
        self.assertEqual(find_matching_slang(True), [])
        self.assertEqual(find_matching_slang(False), [])

    def test_chulgojang_ieumsae_and_hajamaja_not_falsely_treated_as_defects(self) -> None:
        """'출고장'/'입고장' ('고장'), '이음새' ('이음'), and '출고하자마자' ('하자') avoid false positives."""
        # Prospective inquiry mentioning 출고장 or 이음새 should be filtered as Stage 1 inquiry
        self.assertTrue(self.sf.is_spam("아이오닉5 아산 출고장 위치 어디인가요?"))
        self.assertTrue(self.sf.is_spam("고속도로 이음새 넘을 때 승차감이 어떤가요?"))

        # Stage 2 must not treat 출고장/이음새 as operational defect symptoms
        is_owner_chulgo, _ = self.clf.evaluate_stage2_ownership("아산 출고장에서 내 차 인수했는데 양품입니다")
        self.assertFalse(is_owner_chulgo)
        is_owner_ieum, _ = self.clf.evaluate_stage2_ownership("고속도로 이음새 지나가는데 내 차 승차감 좋네요")
        self.assertFalse(is_owner_ieum)

        # Stage 3 polarity must not score '출고장' as '고장' or '출고하자마자' as '하자'
        s3_chulgo = self.clf.evaluate_stage3_scoping("신차 출고장에서 인수했는데 양품이고 만족합니다")
        self.assertNotIn("고장", s3_chulgo["matched_terms"])
        self.assertGreater(s3_chulgo["polarity"], 0.6)

        s3_haja = self.clf.evaluate_stage3_scoping("신차 출고하자마자 주행했는데 너무 조용하고 만족합니다")
        self.assertNotIn("하자", s3_haja["matched_terms"])
        self.assertGreater(s3_haja["polarity"], 0.6)

    def test_bulga_and_operational_mot_do_not_invert_authentic_defects(self) -> None:
        """'시동/제동/충전 불가' and '문 못 열고/충전기 못 빼고' must not negate defects."""
        authentic_cases = [
            "내 차 ICCU 고장으로 시동 불가 상태이고 견인 기다립니다",
            "내 차 브레이크 결함으로 제동 불가 상황이라 식겁했습니다",
            "내 차 도어캐치 실종으로 차 문을 못 열고 출근 포기했습니다",
            "내 차 충전건 고착이라 충전기 못 빼고 1시간 갇혔습니다",
        ]
        for text in authentic_cases:
            s3 = self.clf.evaluate_stage3_scoping(text)
            self.assertEqual(
                s3["negated_defects"],
                [],
                f"Authentic malfunction falsely negated in '{text}': {s3}",
            )
            rec = self.clf.classify(text)
            self.assertTrue(rec.is_authentic_defect, f"Failed defect gate for '{text}': {rec.filter_reason}")
            self.assertLess(rec.sentiment_polarity, -0.3)

        # Perception negation with '못' still negates perceived noise/defects
        praise = self.clf.evaluate_stage3_scoping("내 차 1년 탔는데 잡소리 못 느꼈어요 조용합니다")
        self.assertIn("잡소리", praise["negated_defects"])
        self.assertGreater(praise["polarity"], 0.0)

    def test_vehicle_matcher_unspaced_model_y_and_false_positive_guards(self) -> None:
        """Unspaced '모델Y단차'/'모델Y출고' match Model Y without matching 'model year'/'모델 와이퍼'."""
        self.assertEqual(extract_vehicle_info("모델Y단차 심해서 인수거부"), (BRAND_TESLA, "Model Y"))
        self.assertEqual(extract_vehicle_info("모델Y출고 후 주행기"), (BRAND_TESLA, "Model Y"))
        self.assertEqual(extract_vehicle_info("모델Y롱레인지 충전 문제"), (BRAND_TESLA, "Model Y"))

        self.assertEqual(extract_vehicle_info("2026 model year specs"), (BRAND_OTHER, "전기차"))
        self.assertEqual(extract_vehicle_info("구형 모델 와이퍼 교체 방법"), (BRAND_OTHER, "전기차"))

    def test_complaint_record_dict_dsi_breakdown_and_strict_bool_category(self) -> None:
        """ComplaintRecord normalizes dict dsi_breakdown; strict validation rejects bool category."""
        rec = ComplaintRecord(
            id="dsi-dict-1",
            source="clien",
            url="",
            title="브레이크 결함",
            author="",
            created_at="2026-11-26",
            vehicle_brand="Hyundai",
            vehicle_model="아이오닉5",
            defect_category="DRIVING_POWERTRAIN",
            summary="요약",
            verbatim_quote="브레이크가 안 들어서 위험했습니다",
            dsi_breakdown={"safety": 9.2, "functional": float("nan")},  # type: ignore[arg-type]
        )
        self.assertIsInstance(rec.dsi_breakdown, DSIBreakdown)
        admin = rec.to_admin_report_dict()
        self.assertEqual(admin["dsi_breakdown"]["safety"], 9.2)
        self.assertEqual(admin["dsi_breakdown"]["functional"], 0.0)
        self.assertEqual(rec["dsi_breakdown"]["safety"], 9.2)
        json.dumps(admin, allow_nan=False)

        ok_false, _ = validate_report_entry(
            {"id": "1", "title": "제목", "defect_category": False}, strict=True
        )
        self.assertFalse(ok_false)
        ok_true, _ = validate_report_entry(
            {"id": "1", "title": "제목", "defect_category": True}, strict=True
        )
        self.assertFalse(ok_true)


if __name__ == "__main__":
    unittest.main()
