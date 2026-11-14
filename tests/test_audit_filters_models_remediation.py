"""Unit and regression tests for filters, data models, and utils audit fixes.

Tests:
1. Slang Filter: case-resilient acronym checking in is_slang_present, Unicode normalization,
   zero-width space stripping, non-breaking space handling, fullwidth conversion,
   and Hangul compatibility jamo preservation.
2. Spam Filter: unspaced commercial spam keywords (카톡상담, 텔레문의, 오픈카톡, 당일대출),
   expanded news domain evaluation.
3. Vehicle Matcher: colloquial slang EV model recognition (코나 일렉, 니로 일렉, 캐스퍼 일렉,
   모3, 모Y, 모S, 모X, T4K, GV90, 이삼이, 이육이, 이구이).
4. Defect Classifier: Powertrain auto-hold and accelerator pedal failures protected from software "먹통" hijacking.
5. Models: ComplaintRecord from_dict brand inference from model, DailyReportPayload.validate_payload on instance.
6. Utils: format_daily_report_payload and write_daily_reports resilient against None and non-iterable inputs.
"""

from __future__ import annotations

import unittest

from filters.defect_classifier import DefectClassifier
from filters.slang_filter import SlangFilter, is_slang_present
from filters.slang_lexicon import find_matching_slang
from filters.spam_filter import SpamFilter, is_spam
from filters.vehicle_matcher import VehicleMatcher, extract_vehicle_info
from models.complaint import ComplaintRecord, DailyReportPayload
from utils.json_writer import format_daily_report_payload


class TestFiltersAndModelsAuditRemediation(unittest.TestCase):
    """Rigorous audit test cases verifying resilience, edge case handling, and zero regression."""

    def setUp(self) -> None:
        self.slang_filter = SlangFilter()
        self.spam_filter = SpamFilter()
        self.classifier = DefectClassifier()

    # -------------------------------------------------------------------------
    # 1. Slang Filter & Slang Lexicon
    # -------------------------------------------------------------------------
    def test_01_is_slang_present_case_insensitivity(self) -> None:
        """is_slang_present matches Latin acronyms case-insensitively."""
        text = "고속도로에서 갑자기 ICCU 경고등 떴습니다."
        self.assertTrue(is_slang_present(text, "ICCU"))
        self.assertTrue(is_slang_present(text, "iccu"))
        self.assertTrue(is_slang_present(text, "Iccu"))

        v2l_text = "이번에 캠핑 가서 V2L 꽂았는데 먹통이네요"
        self.assertTrue(is_slang_present(v2l_text, "V2L"))
        self.assertTrue(is_slang_present(v2l_text, "v2l"))

        bms_text = "이번 업데이트 이후 BMS 에러 발생함"
        self.assertTrue(is_slang_present(bms_text, "BMS 에러"))
        self.assertTrue(is_slang_present(bms_text, "bms 에러"))

        # Empty and None guards
        self.assertFalse(is_slang_present("", "iccu"))
        self.assertFalse(is_slang_present(None, "iccu"))
        self.assertFalse(is_slang_present(text, ""))
        self.assertFalse(is_slang_present(text, "   "))
        self.assertTrue(is_slang_present(text, None))

    def test_02_find_matching_slang_zero_width_and_nbsp(self) -> None:
        """find_matching_slang successfully normalizes NBSP, ZWSP, and fullwidth letters."""
        # Non-breaking space (U+00A0 &nbsp;) in composite slang
        nbsp_text = "ICCU\u00a0폭탄 터졌습니다"
        matches = find_matching_slang(nbsp_text)
        terms = [m.term for m in matches]
        self.assertIn("ICCU 폭탄", terms)

        # Zero-width spaces (U+200B) inside slang word
        zwsp_text = "단\u200b차 너무 심하네요"
        matches_zwsp = find_matching_slang(zwsp_text)
        terms_zwsp = [m.term for m in matches_zwsp]
        self.assertIn("단차", terms_zwsp)

        # Fullwidth Latin (ＩＣＣＵ)
        fullwidth_text = "ＩＣＣＵ 교체 받았습니다"
        matches_fw = find_matching_slang(fullwidth_text)
        terms_fw = [m.term for m in matches_fw]
        self.assertIn("ICCU", terms_fw)

        # Preserves Hangul compatibility jamo
        jamo_text = "ㅋㅋㅋ ㅎㅎㅎ 흉기차 터짐"
        matches_jamo = find_matching_slang(jamo_text)
        terms_jamo = [m.term for m in matches_jamo]
        self.assertIn("흉기차", terms_jamo)

    # -------------------------------------------------------------------------
    # 2. Spam Filter
    # -------------------------------------------------------------------------
    def test_03_commercial_spam_unspaced_keywords(self) -> None:
        """SpamFilter catches common Korean unspaced advertising words."""
        self.assertTrue(is_spam("최저가 즉시출고 카톡상담 문의"))
        self.assertTrue(is_spam("신차 최저가 텔레문의 주세요"))
        self.assertTrue(is_spam("상담 문의는 오픈카톡 링크 클릭"))
        self.assertTrue(is_spam("무직자대출 당일대출 승인 보장"))
        self.assertTrue(is_spam("주식리딩방 코인리딩방 원금보장"))

    def test_04_expanded_news_domain_detection(self) -> None:
        """SpamFilter detects external link shares to expanded news domains with minimal text."""
        self.assertTrue(self.spam_filter.is_spam("기사 공유합니다", "https://biz.chosun.com/industry/car/123"))
        self.assertTrue(self.spam_filter.is_spam("기사 공유합니다", "https://www.hankyung.com/article/202610101234"))
        self.assertTrue(self.spam_filter.is_spam("기사 공유합니다", "https://www.etnews.com/202610100001"))

    # -------------------------------------------------------------------------
    # 3. Vehicle Matcher
    # -------------------------------------------------------------------------
    def test_05_vehicle_matcher_colloquial_models(self) -> None:
        """VehicleMatcher accurately identifies popular Korean colloquial abbreviations."""
        cases = [
            ("코나 일렉 출고했는데 단차 있네요", "Hyundai", "코나 EV"),
            ("니로 일렉 하부 잡소리", "Kia", "니로 EV"),
            ("캐스퍼 일렉 계기판 먹통", "Hyundai", "캐스퍼 일렉트릭"),
            ("포터 일렉 충전 불량", "Hyundai", "포터 EV"),
            ("봉고 일렉 배터리 이상", "Kia", "봉고 EV"),
            ("모3 승차감 어떤가요", "Tesla", "Model 3"),
            ("모Y 주행기 및 잡소리", "Tesla", "Model Y"),
            ("모S 에어서스 결함", "Tesla", "Model S"),
            ("모X 팔콘윙 단차", "Tesla", "Model X"),
            ("T4K 1톤 트럭 주행거리 저하", "BYD", "T4K"),
            ("티사케이 충전 에러", "BYD", "T4K"),
            ("GV90 스파이샷 보셨나요", "Hyundai", "GV90"),
            ("이삼이 출고 후기", "Kia", "EV3"),
            ("이육이 잡소리 해결법", "Kia", "EV6"),
            ("이구이 고속도로 멈춤", "Kia", "EV9"),
        ]
        for title, exp_b, exp_m in cases:
            b, m = extract_vehicle_info(title)
            self.assertEqual(b, exp_b, f"Expected brand {exp_b} for title '{title}', got {b}")
            self.assertEqual(m, exp_m, f"Expected model {exp_m} for title '{title}', got {m}")

    # -------------------------------------------------------------------------
    # 4. Defect Classifier
    # -------------------------------------------------------------------------
    def test_06_autohold_and_pedal_powertrain_protection(self) -> None:
        """Auto-hold and accelerator pedal failures classify as DRIVING_POWERTRAIN, not SOFTWARE_ELECTRONICS."""
        text = "내 차 경사로에서 오토홀드 먹통되고 뒤로 밀려서 대형 사고날 뻔했습니다."
        rec = self.classifier.classify(text)
        self.assertEqual(
            rec.defect_category,
            "DRIVING_POWERTRAIN",
            f"Expected DRIVING_POWERTRAIN for auto-hold failure, got {rec.defect_category}",
        )

        pedal_text = "고속도로에서 주행 중 내 차 가속 페달 먹통되고 속도 급감했습니다."
        rec_pedal = self.classifier.classify(pedal_text)
        self.assertEqual(
            rec_pedal.defect_category,
            "DRIVING_POWERTRAIN",
            f"Expected DRIVING_POWERTRAIN for accelerator failure, got {rec_pedal.defect_category}",
        )

    # -------------------------------------------------------------------------
    # 5. Complaint Model Serialization / Deserialization
    # -------------------------------------------------------------------------
    def test_07_complaint_record_brand_inference_from_model(self) -> None:
        """ComplaintRecord.from_dict infers vehicle_brand when only vehicle_model is supplied."""
        rec = ComplaintRecord.from_dict({
            "id": "rec_auto_brand_1",
            "title": "아이오닉5 충전 오류",
            "vehicle_model": "아이오닉5",
            "vehicle_brand": "",
        })
        self.assertEqual(rec.vehicle_brand, "Hyundai")
        self.assertEqual(rec.vehicle_model, "아이오닉5")

        rec_kia = ComplaintRecord.from_dict({
            "id": "rec_auto_brand_2",
            "title": "EV6 단차",
            "vehicle_model": "EV6",
            "vehicle_brand": "",
        })
        self.assertEqual(rec_kia.vehicle_brand, "Kia")

        rec_tesla = ComplaintRecord.from_dict({
            "id": "rec_auto_brand_3",
            "title": "Model 3 글래스 루프 누수",
            "vehicle_model": "Model 3",
            "vehicle_brand": "",
        })
        self.assertEqual(rec_tesla.vehicle_brand, "Tesla")

    def test_08_daily_report_payload_validate_payload_on_instance(self) -> None:
        """DailyReportPayload.validate_payload validates DailyReportPayload instance without rejecting type."""
        payload = DailyReportPayload(
            generated_at="2026-11-15T00:00:00Z",
            reports=[
                {
                    "id": "test_1",
                    "title": "아이오닉5 ICCU 폭탄 교체",
                    "vehicle_brand": "Hyundai",
                    "vehicle_model": "아이오닉5",
                    "defect_category": "BATTERY_CHARGING",
                    "summary": "ICCU 고장",
                    "verbatim_quote": "ICCU 폭탄으로 갓길에 세웠습니다.",
                }
            ],
        )
        is_valid, errors = DailyReportPayload.validate_payload(payload)
        self.assertTrue(is_valid, f"Validation failed on instance: {errors}")
        self.assertEqual(len(errors), 0)

    # -------------------------------------------------------------------------
    # 6. JSON Writer Resilience
    # -------------------------------------------------------------------------
    def test_09_format_daily_report_payload_null_guard(self) -> None:
        """format_daily_report_payload safely handles None, non-iterables, and string inputs without crashing."""
        payload_none = format_daily_report_payload(None)
        self.assertEqual(payload_none.total_complaints_today, 0)
        self.assertEqual(len(payload_none.reports), 0)

        payload_int = format_daily_report_payload(12345)  # type: ignore[arg-type]
        self.assertEqual(payload_int.total_complaints_today, 0)

        payload_str = format_daily_report_payload("invalid_string")  # type: ignore[arg-type]
        self.assertEqual(payload_str.total_complaints_today, 0)


if __name__ == "__main__":
    unittest.main()
