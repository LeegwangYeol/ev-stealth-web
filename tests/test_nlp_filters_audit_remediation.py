#!/usr/bin/env python3
"""
Comprehensive Audit & Hardening Verification Test Suite for EV NLP Filters:
- filters/defect_classifier.py
- filters/spam_filter.py
- filters/slang_filter.py
- filters/slang_lexicon.py
- filters/vehicle_matcher.py

Verifies:
1. Slang dictionary coverage for EV automotive terms and false positive prevention.
2. Defect classification precision/recall and severity scoring thresholds.
3. RegEx performance and catastrophic backtracking vulnerabilities.
"""

from __future__ import annotations

from pathlib import Path
import sys
import time
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from filters.defect_classifier import DefectClassifier
from filters.slang_filter import SlangFilter
from filters.slang_lexicon import (
    RAW_SLANG_ENTRIES,
    SLANG_CATALOG,
    SYMPTOM_PREDICATES,
    find_matching_slang,
)
from filters.spam_filter import SpamFilter
from filters.vehicle_matcher import extract_vehicle_info
from models.complaint import ComplaintRecord, RawPost


class TestSlangDictionaryFalsePositiveRemediation(unittest.TestCase):
    """Test 1: Slang dictionary coverage for EV automotive terms and false positive prevention."""

    def setUp(self) -> None:
        self.clf = DefectClassifier()
        self.filter = SlangFilter()

    def test_door_seal_weatherstrip_not_tagged_as_byd_seal_slang(self) -> None:
        """Rubber weatherstrip door seals must never be falsely tagged as BYD Seal slang."""
        false_positive_cases = [
            "아이오닉5 도어 씰 고무 몰딩 들뜸 현상",
            "웨더스트립 씰 틈새로 풍절음 들어옵니다",
            "트렁크 고무 씰 유격으로 누수 발생",
            "방수 씰링 작업 완료했습니다",
        ]
        for text in false_positive_cases:
            matches = find_matching_slang(text)
            matched_terms = [m.term for m in matches]
            self.assertNotIn("씰", matched_terms, f"Falsely matched BYD Seal slang on door seal: {text}")

    def test_authentic_byd_seal_slang_matched(self) -> None:
        """Genuine mentions of BYD Seal vehicle must be accurately matched."""
        authentic_seal_cases = [
            "비야디 씰 시승해봤는데 주행감은 생각보다 탄탄하네요.",
            "BYD 씰 신차 출고했습니다",
            "씰 EV 가속감 장난 아니네요",
            "비야디 씰 세단 사전계약 넣었습니다",
        ]
        for text in authentic_seal_cases:
            matches = find_matching_slang(text)
            matched_terms = [m.term for m in matches]
            self.assertIn("씰", matched_terms, f"Failed to match BYD Seal on vehicle text: {text}")

    def test_rice_cooker_appliance_not_tagged_as_motor_noise_slang(self) -> None:
        """Kitchen electric rice cookers in camping/V2L context must not trigger motor noise defect slang."""
        camping_cases = [
            "차박 가서 전기밥솥 썼는데 V2L 좋네요",
            "캠핑 가서 쿠쿠 밥솥으로 밥 지어 먹었습니다",
            "압력 밥솥 올려놓고 V2L 전원 꽂음",
        ]
        for text in camping_cases:
            matches = find_matching_slang(text)
            matched_terms = [m.term for m in matches]
            self.assertNotIn("밥솥", matched_terms, f"Falsely matched motor noise slang on kitchen appliance: {text}")

    def test_authentic_motor_whining_rice_cooker_noise_matched(self) -> None:
        """High-frequency inverter/motor noise sounding like a rice cooker must match slang."""
        noise_cases = [
            "엑셀 밟을 때마다 모터에서 밥솥 취사소리 삐익 나는데 센터선 정상이래.",
            "가속 페달 밟으면 밥솥소리 너무 심해서 귀가 아픔.",
            "모터에서 고주파 밥솥 소리 심하게 올라옵니다",
        ]
        for text in noise_cases:
            matches = find_matching_slang(text)
            matched_terms = [m.term for m in matches]
            self.assertTrue(
                any(t in ("밥솥", "밥솥소리") for t in matched_terms),
                f"Failed to match motor noise slang: {text}",
            )

    def test_new_critical_ev_slang_terms_coverage(self) -> None:
        """Newly added EV community defect terms must be present in catalog and matched."""
        new_terms = [
            "DSM 블랙아웃",
            "디지털 사이드미러 먹통",
            "충전 튕김",
            "충전 끊김",
            "절연 저항 이상",
            "원페달 먹통",
        ]
        for term in new_terms:
            self.assertIn(term, SLANG_CATALOG, f"Missing {term} in SLANG_CATALOG")
            entry = SLANG_CATALOG[term]
            self.assertGreater(len(entry.meaning), 0)
            self.assertGreater(entry.severity_weight, 0)
            self.assertLess(entry.default_polarity, 0.0)

        # Functional matching test
        sample = "폭우에 디지털 사이드미러 먹통 돼서 갓길 섰고 완속 물렸더니 충전 튕김 발생"
        matches = find_matching_slang(sample)
        matched_terms = [m.term for m in matches]
        self.assertIn("디지털 사이드미러 먹통", matched_terms)
        self.assertIn("충전 튕김", matched_terms)

    def test_benign_turn_signal_operation_not_classified_as_defect(self) -> None:
        """Standard turn signal operation ('깜빡이 켜고') must not be classified as a defect."""
        benign_cases = [
            "내 차 신차 출고 후 깜빡이 켜고 고속도로 주행했습니다.",
            "이브이6 깜빡이 켜고 주행했습니다",
            "차선 변경할 때 깜빡이 켜는 습관이 중요합니다",
            "아이오닉5 깜빡이 켜고 합류 도로 진입 완료",
        ]
        for text in benign_cases:
            rec = self.clf.classify(text)
            self.assertFalse(rec.is_authentic_defect, f"Benign turn signal operation falsely passed: {text}")

    def test_authentic_turn_signal_malfunction_classified_as_defect(self) -> None:
        """Stalkless turn signal or turn signal sound cutout must classify as authentic defect."""
        malfunction_cases = [
            "우리 집 테쪽이 모델와이 MCU 꺼지더니 깜빡이 소리도 안 남",
            "하이랜드 버튼식 깜빡이 회전교차로에서 누르다 핸들 꼬임",
            "주행 중 깜빡이 먹통 돼서 차선 변경 못 하고 갓길에 세웠습니다.",
        ]
        for text in malfunction_cases:
            rec = self.clf.classify(text)
            self.assertTrue(rec.is_authentic_defect, f"Turn signal defect failed gate: {text}")
            self.assertEqual(rec.filter_reason, "PASSED: Authentic EV defect complaint")

    def test_benign_v2l_feature_praise_not_classified_as_defect(self) -> None:
        """Praise for V2L feature ('V2L 신세계', 'V2L 편하고 대만족') must not be classified as a defect."""
        praise_cases = [
            "내 차 아이오닉5 V2L 꽂아서 커피포트 끓여 마셨는데 신세계네요.",
            "아이오닉5 출고하고 V2L 써봤는데 진짜 편하고 대만족입니다.",
            "내 차 아이오닉5 타는데 V2L로 커피 머신 돌려 마시니 좋습니다.",
        ]
        for text in praise_cases:
            rec = self.clf.classify(text)
            self.assertFalse(rec.is_authentic_defect, f"Benign V2L praise falsely passed: {text}")

    def test_authentic_v2l_failure_classified_as_defect(self) -> None:
        """V2L overload, error, or discharge shutoff must classify as authentic defect."""
        failure_cases = [
            "내 차 아이오닉5 캠핑 가서 V2L 꽂았는데 과열 경고 뜨고 전원 차단됨.",
            "고속도로 휴게소에서 V2L 오류 에러 코드 점등되며 안 됨.",
        ]
        for text in failure_cases:
            rec = self.clf.classify(text)
            self.assertTrue(rec.is_authentic_defect, f"V2L failure failed gate: {text}")
            self.assertEqual(rec.defect_category, "BATTERY_CHARGING")


class TestDefectClassificationPrecisionRecallAndThresholds(unittest.TestCase):
    """Test 2: Defect classification precision/recall and severity scoring thresholds."""

    def setUp(self) -> None:
        self.clf = DefectClassifier()

    def test_failed_repair_not_misidentified_as_negated_defect(self) -> None:
        """Complaints stating a defect was NOT fixed ('단차 안 잡혀서') must NOT be inverted to praise."""
        failed_repair_cases = [
            "사업소 갔는데 단차 안 잡혀서 미치겠네요",
            "블루핸즈 3번 입고했는데 하부 잡소리 안 잡힘 짜증납니다",
            "내 차 단차 때문에 화가 안 풀리네요",
            "서비스센터 들어갔지만 누수 안 고쳐짐 답답하네요",
        ]
        for text in failed_repair_cases:
            res = self.clf.evaluate_stage3_scoping(text)
            self.assertEqual(res["negated_defects"], [], f"Failed repair falsely treated as negated defect: {text}")
            self.assertLess(res["polarity"], 0.0, f"Polarity was not negative for failed repair: {text}")

    def test_true_negated_defects_correctly_inverted_to_praise(self) -> None:
        """Praise statements negating defects ('단차 전혀 없고 잡소리도 1도 안 납니다') must be positive."""
        praise_cases = [
            "내 차 아이오닉5 5000km 탔는데 단차 전혀 없고 잡소리도 1도 안 납니다.",
            "단차 없고 누수 없는 완전 양품 출고했습니다.",
        ]
        for text in praise_cases:
            rec = self.clf.classify(text)
            self.assertFalse(rec.is_authentic_defect)
            self.assertGreater(rec.sentiment_polarity, 0.0)

    def test_dsm_blackout_classification_and_dsi(self) -> None:
        """Digital Side Mirror blackout must classify to SOFTWARE_ELECTRONICS with high safety DSI."""
        text = "내 차 아이오닉5 고속도로 주행 중 디지털 사이드미러 먹통 DSM 블랙아웃 발생해서 식겁함"
        rec = self.clf.classify(text)
        self.assertTrue(rec.is_authentic_defect)
        self.assertEqual(rec.defect_category, "SOFTWARE_ELECTRONICS")
        self.assertGreaterEqual(rec.severity_index, 7.0)
        self.assertGreaterEqual(rec.dsi_breakdown.safety, 9.0)

    def test_charging_rejection_and_insulation_classification(self) -> None:
        """Charging interruption and insulation resistance must classify to BATTERY_CHARGING."""
        c1 = "내 차 EV6 급속 충전기 꽂았는데 5분 만에 충전 튕김 현상 발생해서 시동 안 걸림"
        r1 = self.clf.classify(c1)
        self.assertTrue(r1.is_authentic_defect)
        self.assertEqual(r1.defect_category, "BATTERY_CHARGING")

        c2 = "비 오는 날 주행 중 고전압 배터리 절연 저항 이상 경고등 뜨며 시동 꺼짐"
        r2 = self.clf.classify(c2)
        self.assertTrue(r2.is_authentic_defect)
        self.assertEqual(r2.defect_category, "BATTERY_CHARGING")

    def test_one_pedal_failure_classification(self) -> None:
        """One-pedal / i-Pedal deactivation must classify to DRIVING_POWERTRAIN."""
        text = "내 차 주행 중 원페달 먹통 돼서 감속 안 되고 앞차 박을 뻔했습니다"
        rec = self.clf.classify(text)
        self.assertTrue(rec.is_authentic_defect)
        self.assertEqual(rec.defect_category, "DRIVING_POWERTRAIN")


class TestSpamFilterAndRegExPerformance(unittest.TestCase):
    """Test 3: RegEx performance, ReDoS immunity, and spam filter precision."""

    def setUp(self) -> None:
        self.spam = SpamFilter()
        self.clf = DefectClassifier()

    def test_reservation_holders_waiting_not_discarded_as_journalistic(self) -> None:
        """Community members using '대기자' (reservation holders) must NOT be discarded as journalists."""
        community_samples = [
            "출고 대기자 분들 단차 불량 많나요?",
            "AS 수리 대기자 많은가요?",
            "신차 입고 대기자 모임입니다",
            "보조금 신청 대기자 인데 출고 일정 안내 받았습니다",
        ]
        for text in community_samples:
            is_disc, reason = self.spam.evaluate_stage1_noise(text)
            self.assertNotIn("Journalistic", reason, f"Community user falsely discarded as news: {reason} | Text: {text}")

    def test_owner_recall_announcement_discussion_not_discarded_as_news(self) -> None:
        """Owner reports discussing recall announcements with defect symptoms must NOT be discarded as news."""
        recall_samples = [
            "내 차 아이오닉5 몰고 있는데 이번에 ICCU 터져서 리콜 발표 보고 왔습니다.",
            "고속도로에서 시동 꺼진 뒤 리콜 발표 소식 접하고 블루핸즈 방문 예약했습니다.",
        ]
        for text in recall_samples:
            is_disc, reason = self.spam.evaluate_stage1_noise(text)
            self.assertFalse(is_disc, f"Owner recall complaint falsely discarded: {reason} | Text: {text}")

    def test_as_substring_in_english_words_does_not_falsely_bypass_flaming_filter(self) -> None:
        """English words containing 'as' (e.g. 'casper', 'crash', 'glass') must NOT trigger 'as' service keyword."""
        # A flaming post with English 'crash' without actual EV component should be filtered
        flaming_post = "개슬라 crash ㅋㅋㅋ 타죽어라 망해라"
        is_disc, reason = self.spam.evaluate_stage1_noise(flaming_post)
        self.assertTrue(is_disc, f"Brand flaming with 'crash' was not filtered: {reason}")

    def test_vehicle_matcher_sweep_line_subsumption_speed(self) -> None:
        """Adversarial repetitive vehicle text (2,000 matches) resolves cleanly in < 100ms."""
        adversarial_text = "아이오닉 5 " * 2000
        start = time.perf_counter()
        brand, model = extract_vehicle_info("전기차 후기", adversarial_text)
        elapsed = time.perf_counter() - start

        self.assertEqual(brand, "Hyundai")
        self.assertEqual(model, "아이오닉5")
        self.assertLess(elapsed, 0.10, f"Vehicle matcher subsumption too slow: {elapsed:.4f}s")


if __name__ == "__main__":
    unittest.main()
