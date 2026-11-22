"""Swarm audit regression tests for filters/*.py and models/*.py (2026-11-23)."""

from __future__ import annotations

import math
import time
import unicodedata
import unittest

from filters.defect_classifier import DefectClassifier
from filters.slang_lexicon import find_matching_slang
from filters.spam_filter import SpamFilter, matches_category_keyword
from filters.vehicle_matcher import BRAND_BYD, BRAND_OTHER, extract_vehicle_info
from models.complaint import (
    ComplaintRecord,
    DailyReportStatistics,
    parse_date_str,
    sanitize_string,
    validate_report_entry,
)


class TestSwarmFiltersAndModelsAudit(unittest.TestCase):
    def setUp(self) -> None:
        self.clf = DefectClassifier()
        self.spam = SpamFilter()

    def test_jeonson_and_tcam_false_positives_suppressed(self) -> None:
        """Substrings like 안전손잡이, 충전손실, 완속충전손실, 멀티캠 must not trigger 전손/티캠."""
        fp_texts = [
            "운전석 안전손잡이 단차 있고 잡소리 심해요",
            "완속 충전손실 너무 심하네요",
            "블랙박스 멀티캠 장착 후기입니다",
        ]
        for text in fp_texts:
            terms = [e.term for e in find_matching_slang(text)]
            self.assertNotIn("전손", terms, f"False positive 전손 in: {text}")
            self.assertNotIn("티캠", terms, f"False positive 티캠 in: {text}")

        self.assertFalse(matches_category_keyword("SERVICE_REPAIR_COST", "전손", "안전손잡이 흔들림"))
        self.assertFalse(matches_category_keyword("SERVICE_REPAIR_COST", "전손", "충전손실 심함"))
        self.assertFalse(matches_category_keyword("SOFTWARE_ELECTRONICS", "티캠", "멀티캠 화질"))
        self.assertTrue(matches_category_keyword("SERVICE_REPAIR_COST", "전손", "하부 긁혀서 전손 판정"))
        self.assertTrue(matches_category_keyword("SOFTWARE_ELECTRONICS", "티캠", "티캠 먹통됨"))

        # Classify safety: 안전손잡이 단차 should be BUILD_QUALITY, not SERVICE_REPAIR_COST
        cat = self.clf.classify_defect_category("내 차 안전손잡이 단차 벌어지고 찌걱찌걱 잡소리 남")
        self.assertEqual(cat, "BUILD_QUALITY")

        # Polarity should not falsely score 안전손잡이 as 전손 (-0.90)
        res = self.clf.evaluate_stage3_scoping("안전손잡이 만족하고 잘 쓰고 있어요")
        self.assertGreater(res["polarity"], 0.0)
        self.assertNotIn("전손", res["matched_terms"])

    def test_megi_and_dolphin_false_positives_suppressed(self) -> None:
        """헤메기 / 메기탕 must not match 메기 slang, 엔돌핀 must not match BYD 돌핀."""
        self.assertNotIn("메기", [e.term for e in find_matching_slang("서비스센터 찾느라 헤메기만 했네요")])
        self.assertNotIn("메기", [e.term for e in find_matching_slang("점심에 메기매운탕 먹음")])
        self.assertIn("메기", [e.term for e in find_matching_slang("아이오닉 메기 디자인 적응 안됨")])

        brand, model = extract_vehicle_info("드라이브하니 엔돌핀이 뿜뿜 도네요")
        self.assertNotEqual(brand, BRAND_BYD)
        self.assertNotEqual(model, "돌핀")

        b2, m2 = extract_vehicle_info("BYD 돌핀 출고 후기")
        self.assertEqual((b2, m2), (BRAND_BYD, "돌핀"))

    def test_bounded_ascii_acronyms_in_slang_and_compounds(self) -> None:
        """ICCU, V2L, DSM, BMS, AS must respect ASCII alphanumeric boundaries."""
        self.assertNotIn("ICCU", [e.term for e in find_matching_slang("siccu test")])
        self.assertIn("ICCU", [e.term for e in find_matching_slang("ICCU폭탄 터짐")])
        self.assertFalse(matches_category_keyword("SERVICE_REPAIR_COST", "as", "1as test"))
        self.assertTrue(matches_category_keyword("SERVICE_REPAIR_COST", "as", "AS센터 입고"))
        # "dsm" inside "bdsm" or "oldsmobile" must not hijack to SOFTWARE_ELECTRONICS
        cat = self.clf.classify_defect_category("올드스모빌 oldsmobile 도어 단차 심함")
        self.assertEqual(cat, "BUILD_QUALITY")

    def test_eopsi_adverbs_do_not_falsely_negate_defects(self) -> None:
        """Adverbs like 끊임없이, 수없이, 끝없이, 어김없이, 전조 없이, 예고 없이 must NOT negate defects."""
        persistent_defect_texts = [
            "내 차 방지턱 넘을 때마다 잡소리 끊임없이 나요.",
            "내 차 주행 중 경고등이 수없이 뜨네요.",
            "내 차 비만 오면 어김없이 누수 생깁니다.",
            "내 차 주행 중 전조 없이 동력 상실로 갓길에 멈춤.",
            "내 차 주행 중 예고 없이 브레이크 먹통 돼서 죽을 뻔.",
        ]
        for text in persistent_defect_texts:
            stage3 = self.clf.evaluate_stage3_scoping(text)
            self.assertEqual(
                stage3["negated_defects"],
                [],
                f"Falsely negated defect in: {text} -> {stage3}",
            )
            self.assertLess(stage3["polarity"], 0.0, f"Polarity should stay negative for: {text}")

        # Real negation must still negate
        real_neg = self.clf.evaluate_stage3_scoping("내 차 단차 전혀 없고 잡소리 없이 조용합니다.")
        self.assertGreater(real_neg["polarity"], 0.0)
        self.assertTrue(len(real_neg["negated_defects"]) >= 1)

    def test_negated_defect_with_praise_and_laugh_not_sarcasm(self) -> None:
        """Explicitly negated defect + genuine praise + ㅋㅋㅋ must not trigger sarcasm inversion."""
        praise = "내 차 출고했는데 단차 전혀 없고 마감 완벽하네요 ㅋㅋㅋ"
        res = self.clf.evaluate_stage3_scoping(praise)
        self.assertFalse(res["is_sarcastic"])
        self.assertGreater(res["polarity"], 0.0)

        # Actual sarcasm without negation still triggers sarcasm inversion
        sarcastic = "단차 누수로 비 새는데 현대차 기술력 대단하다 대만족 ㅋㅋㅋ"
        res_sarc = self.clf.evaluate_stage3_scoping(sarcastic)
        self.assertTrue(res_sarc["is_sarcastic"])
        self.assertLess(res_sarc["polarity"], -0.5)

    def test_concessive_expansion_cap_performance(self) -> None:
        """Adversarial repeated concessives must be bounded and finish quickly."""
        evil = "내 차 " + ("하지만 " * 3000) + "단차 심함"
        start = time.perf_counter()
        res = self.clf.evaluate_stage3_scoping(evil)
        elapsed = time.perf_counter() - start
        self.assertLess(elapsed, 0.25)
        self.assertIn("polarity", res)

    def test_spam_filter_explicit_empty_lists_respected(self) -> None:
        """Passing empty lists to SpamFilter must disable those rule sets rather than falling back."""
        sf = SpamFilter(
            news_regexes=[],
            stock_terms=[],
            commercial_spam_terms=[],
            commercial_spam_regexes=[],
            political_terms=[],
        )
        self.assertEqual(sf.news_regexes, [])
        self.assertEqual(sf.financial_terms, [])
        self.assertFalse(sf.is_spam("카톡 상담 오픈채팅 주식 매수 매도 윤석열 이재명 [속보]"))

    def test_models_cp949_bytes_and_nfd_unicode_and_dates(self) -> None:
        """Verify CP949 byte decoding, NFD category validation/brand inference, and date digit boundaries."""
        cp949_bytes = "고장 심각".encode("cp949")
        self.assertEqual(sanitize_string(cp949_bytes), "고장 심각")

        # NFD Hangul category in strict validation
        nfd_cat = unicodedata.normalize("NFD", "배터리")
        ok, err = validate_report_entry({"id": "1", "title": "테스트", "defect_category": nfd_cat}, strict=True)
        self.assertTrue(ok, err)

        # NFD Hangul target_vehicle / vehicle_model inference
        nfd_model = unicodedata.normalize("NFD", "아이오닉5")
        rec = ComplaintRecord.from_dict({"id": "2", "title": "충전 오류", "vehicle_model": nfd_model})
        self.assertEqual(rec.vehicle_brand, "Hyundai")

        # Embedded 6-digit prefix before YYYY-MM-DD must not match YYYY as trailing 4 digits
        today = parse_date_str(None)
        self.assertEqual(parse_date_str("ID122026-10-28"), today)
        self.assertEqual(parse_date_str("2026-10-28"), "2026-10-28")

        # DailyReportStatistics.from_dict sanitizes NaN even on existing instance
        bad_stats = DailyReportStatistics(total_scraped=-5, avg_negativity_score=math.nan)
        clean_stats = DailyReportStatistics.from_dict(bad_stats)
        self.assertEqual(clean_stats.total_scraped, 0)
        self.assertEqual(clean_stats.avg_negativity_score, 0.0)


if __name__ == "__main__":
    unittest.main()
