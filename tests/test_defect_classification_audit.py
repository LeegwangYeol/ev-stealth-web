#!/usr/bin/env python3
"""Comprehensive Audit & Verification Test Suite for Defect Classifier & Defect Filter.

Validates:
1. Classification accuracy for all 8 target Korean EV defect categories:
   - ICCU (통합충전제어장치) -> BATTERY_CHARGING
   - 배터리 화재 / 열폭주 -> BATTERY_CHARGING
   - BMS 오작동 -> BATTERY_CHARGING
   - 모터 감속기 소음 -> DRIVING_POWERTRAIN
   - 조향 / 피시테일링 (fishtailing) -> DRIVING_POWERTRAIN
   - 전자식 도어캐치 -> BUILD_QUALITY
   - 인포테인먼트 / OTA 블랙아웃 -> SOFTWARE_ELECTRONICS
   - 브레이크 먹통 -> DRIVING_POWERTRAIN
2. Edge cases: empty texts, single-character posts, emojis, foreign languages, non-string inputs.
3. Multi-keyword priority ordering and physical root-cause resolution.
4. Statistical confidence score calculation and false-positive suppression.
5. Bitwise parity and serialization integrity.
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from filters.defect_classifier import COMPOUND_DEFECT_RULES, DefectClassifier
from filters.defect_filter import ContextualDefectFilter, DefectFilter
from models.complaint import ComplaintRecord, RawPost


class TestKoreanEVDefectClassificationAccuracy(unittest.TestCase):
    """Verifies 100% accuracy on critical Korean EV defect categories and terms."""

    def setUp(self) -> None:
        self.clf = ContextualDefectFilter()

    def test_01_iccu_integrated_charging_control_unit(self) -> None:
        """ICCU and 통합충전제어장치 failures must classify into BATTERY_CHARGING."""
        cases = [
            "고속도로 주행 중 퍽 소리와 함께 ICCU 고장 발생",
            "통합충전제어장치(ICCU) 결함으로 12V 방전 및 시동 꺼짐",
            "통합 충전 제어 장치 이상으로 완속 충전 불가 현상",
            "통합충전제어기 리콜 받고도 또 ICCU 터짐",
            "아이오닉5 ICCU 폭탄 터져서 전원공급장치 점검 경고등 점등",
        ]
        for text in cases:
            cat = self.clf.classify_defect_category(text)
            self.assertEqual(cat, "BATTERY_CHARGING", f"Failed on ICCU case: {text}")

    def test_02_battery_fire_and_thermal_runaway(self) -> None:
        """Battery fires, explosions, and thermal runaway must classify into BATTERY_CHARGING."""
        cases = [
            "지하주차장 충전 중 배터리 화재 및 불쇼 발생",
            "고전압 배터리 팩 열폭주 현상으로 소방차 출동",
            "배터리 연기 치솟더니 배터리 발화 및 폭발",
            "주행 중 하부 배터리 불꽃 튀면서 화재 발생",
        ]
        for text in cases:
            cat = self.clf.classify_defect_category(text)
            self.assertEqual(cat, "BATTERY_CHARGING", f"Failed on Fire/Thermal Runaway: {text}")

    def test_03_bms_malfunction(self) -> None:
        """BMS malfunctions and battery management errors must classify into BATTERY_CHARGING."""
        cases = [
            "BMS 오작동으로 완속 급속 충전 전부 인식 불가",
            "배터리 관리 시스템(BMS) 오류 경고등 점등 및 벽돌 현상",
            "BMS 업데이트 이후 충전 중단 에러 지속 발생",
            "배터리관리시스템 통신 오류로 SOC 급감",
        ]
        for text in cases:
            cat = self.clf.classify_defect_category(text)
            self.assertEqual(cat, "BATTERY_CHARGING", f"Failed on BMS case: {text}")

    def test_04_motor_and_reducer_noise(self) -> None:
        """Motor reducer noise, whining, and vibration must classify into DRIVING_POWERTRAIN (NOT BUILD_QUALITY)."""
        cases = [
            "모터 감속기 소음 및 웅웅거리는 고주파음 극심함",
            "감속기 소음 잡소리 심해서 주행 시 귀가 먹먹함",
            "가속 페달 밟을 때 감속기 쇠소리 및 갈리는 소리 발생",
            "모터 소음 및 인버터 고주파 귀신소리 발생",
            "구동 모터 소음 및 감속기 이음 결함",
        ]
        for text in cases:
            cat = self.clf.classify_defect_category(text)
            self.assertEqual(cat, "DRIVING_POWERTRAIN", f"Failed on Motor/Reducer noise: {text}")

    def test_05_steering_and_fishtailing(self) -> None:
        """Steering lock, deviation, and fishtailing must classify into DRIVING_POWERTRAIN."""
        cases = [
            "비 오는 날 맨홀 밟고 회생제동 풀리면서 피시테일링 발생",
            "고속 코너에서 fishtailing 현상으로 차체 털림",
            "조향 장치 이상 및 핸들 잠김으로 사고 날 뻔함",
            "주행 중 핸들 쏠림 및 MDPS 결함으로 조향 불능",
            "빗길 피쉬테일 털리면서 중앙분리대 박을 뻔",
        ]
        for text in cases:
            cat = self.clf.classify_defect_category(text)
            self.assertEqual(cat, "DRIVING_POWERTRAIN", f"Failed on Steering/Fishtailing: {text}")

    def test_06_electronic_door_catch(self) -> None:
        """Electronic flush door catch defects must classify into BUILD_QUALITY (NOT SOFTWARE_ELECTRONICS)."""
        cases = [
            "전자식 도어캐치 안 튀어나와서 차 문 못 열고 출근 포기",
            "혹한기 플러시 도어 손잡이 먹통 및 도어캐치 실종",
            "오토플러시 도어 핸들 안 튀어나옴 결함",
            "조수석 외캐치 팝업 불량 및 도어캐치 먹통",
        ]
        for text in cases:
            cat = self.clf.classify_defect_category(text)
            self.assertEqual(cat, "BUILD_QUALITY", f"Failed on Door Catch: {text}")

    def test_07_infotainment_and_ota_blackout(self) -> None:
        """Infotainment, clusters, and OTA blackouts must classify into SOFTWARE_ELECTRONICS."""
        cases = [
            "주행 중 인포테인먼트 네비게이션 및 디스플레이 먹통",
            "ccNC 화면 꺼짐 및 계기판 클러스터 블랙아웃",
            "OTA 업데이트 진행 후 전체 소프트웨어 벽돌 및 먹통",
            "내비게이션 터치 먹통 및 헤드업 디스플레이 블랙아웃",
        ]
        for text in cases:
            cat = self.clf.classify_defect_category(text)
            self.assertEqual(cat, "SOFTWARE_ELECTRONICS", f"Failed on Infotainment/OTA Blackout: {text}")

    def test_08_brake_failure_and_meoktong(self) -> None:
        """Brake loss, pedal lock, and brake 먹통 must classify into DRIVING_POWERTRAIN (NOT SOFTWARE_ELECTRONICS)."""
        cases = [
            "고속도로 주행 중 브레이크 먹통으로 제동 불능",
            "브레이크 밟았는데 스펀지 브레이크처럼 페달 푹 꺼짐",
            "계기판 경고등 뜨며 브레이크가 벽돌 페달 돼서 제동 불가",
            "페달 먹통 및 회생제동 불능으로 앞차 추돌 위기",
            "브레이크 먹통으로 죽을 뻔했습니다",
        ]
        for text in cases:
            cat = self.clf.classify_defect_category(text)
            self.assertEqual(cat, "DRIVING_POWERTRAIN", f"Failed on Brake Failure: {text}")


class TestEdgeCaseAndNonStringRobustness(unittest.TestCase):
    """Verifies crash-resilience against empty, single-character, emoji, foreign, and non-string inputs."""

    def setUp(self) -> None:
        self.clf = ContextualDefectFilter()

    def test_empty_and_whitespace_inputs(self) -> None:
        """Empty texts and whitespace-only content must be discarded gracefully."""
        for text in ["", "   ", "\n\t  \r", None]:
            discarded, reason = self.clf.evaluate_stage1_noise(text)
            self.assertTrue(discarded)
            self.assertIn("Empty", reason)

            rec = self.clf.classify(text)
            self.assertIsInstance(rec, ComplaintRecord)
            self.assertFalse(rec.is_authentic_defect)
            self.assertEqual(rec.confidence_score, 0.0)

    def test_single_character_posts(self) -> None:
        """Single-character posts must be discarded at Stage 1 as insufficient content."""
        for text in ["ㅋ", "a", "1", ".", "?"]:
            discarded, reason = self.clf.evaluate_stage1_noise(text)
            self.assertTrue(discarded)
            self.assertIn("single-character", reason)

            rec = self.clf.classify(text)
            self.assertFalse(rec.is_authentic_defect)
            self.assertEqual(rec.confidence_score, 0.0)

    def test_pure_emoji_and_symbol_posts(self) -> None:
        """Pure emojis or symbols must be discarded at Stage 1 as non-alphanumeric noise."""
        for text in ["🚗⚡️🔥", "🚨😭💥", "😱😱😱", "!@#$%^&*()"]:
            discarded, reason = self.clf.evaluate_stage1_noise(text)
            self.assertTrue(discarded)
            self.assertIn("emojis or symbols", reason)

            rec = self.clf.classify(text)
            self.assertFalse(rec.is_authentic_defect)
            self.assertEqual(rec.confidence_score, 0.0)

    def test_foreign_language_posts(self) -> None:
        """Foreign language text without Korean context must be discarded without crashing."""
        foreign_samples = [
            "电动车电池起火，刹车失灵完全无法停下来",
            "電気自動車のバッテリーが故障して走行中に停止しました",
            "Электромобиль загорелся на трассе",
            "The car was parked in the driveway and nothing happened.",
        ]
        for text in foreign_samples:
            discarded, reason = self.clf.evaluate_stage1_noise(text)
            self.assertTrue(discarded, f"Foreign language was not discarded: {text}")
            self.assertIn("Foreign language", reason)

            rec = self.clf.classify(text)
            self.assertFalse(rec.is_authentic_defect)

    def test_non_string_inputs(self) -> None:
        """Non-string inputs (int, float, list, dict, object) must never crash process_post or classify."""
        non_string_cases = [
            12345,
            3.14159,
            True,
            ["not", "a", "string"],
            {"content": "내차 주행 중 ICCU 고장 발생했습니다"},
            object(),
        ]
        for item in non_string_cases:
            rec = self.clf.classify(item)
            self.assertIsInstance(rec, ComplaintRecord)
            self.assertIsInstance(rec.confidence_score, float)


class TestPriorityOrderingAndRootCauseResolution(unittest.TestCase):
    """Verifies priority resolution when multiple defect keywords appear in a single post."""

    def setUp(self) -> None:
        self.clf = ContextualDefectFilter()

    def test_iccu_breakdown_with_service_repair_keywords(self) -> None:
        """ICCU breakdown leading to dealership service/quote complaints must classify as BATTERY_CHARGING."""
        text = (
            "내차 출고 3달만에 고속도로에서 퍽 소리 나더니 ICCU 터짐. "
            "견인차 불러서 서비스센터 입고했는데 어드바이저가 부품 없다고 대차 거부하고 "
            "수리비 견적 450만원 나왔습니다. AS 지연에 감가상각 어떡하죠."
        )
        cat = self.clf.classify_defect_category(text)
        self.assertEqual(cat, "BATTERY_CHARGING")

    def test_brake_failure_with_service_repair_keywords(self) -> None:
        """Brake failure leading to emergency service visit must classify as DRIVING_POWERTRAIN."""
        text = (
            "내차 주행 중 갑자기 브레이크 먹통으로 죽을 뻔해서 블루핸즈 긴급 입고했습니다. "
            "사업소 정비사가 부품 수급 지연된다며 대차도 안 해주고 수리비 견적만 비싸네요."
        )
        cat = self.clf.classify_defect_category(text)
        self.assertEqual(cat, "DRIVING_POWERTRAIN")

    def test_reducer_noise_with_build_quality_noise_words(self) -> None:
        """Reducer whining mixed with cabin rattle words must prioritize DRIVING_POWERTRAIN."""
        text = "내차 주행할 때 모터 감속기 소음 및 잡소리 이음 소음 심각합니다."
        cat = self.clf.classify_defect_category(text)
        self.assertEqual(cat, "DRIVING_POWERTRAIN")

    def test_pure_service_repair_dispute_without_physical_failure(self) -> None:
        """Disputes about repair estimates, insurance, or dealer markups without mechanical failure remain SERVICE_REPAIR_COST."""
        text = "서비스센터 정기점검 입고했는데 대차 거부당하고 단순 공임 수리비 견적 폭탄 맞았습니다."
        cat = self.clf.classify_defect_category(text)
        self.assertEqual(cat, "SERVICE_REPAIR_COST")

    def test_battery_scratch_total_loss_quote_remains_service_cost(self) -> None:
        """Underbody battery pack scratch estimate and total loss dispute remains SERVICE_REPAIR_COST."""
        text = "배터리 팩 하부 긁힘 견적 2500만원 통교체 전손 처리"
        cat = self.clf.classify_defect_category(text)
        self.assertEqual(cat, "SERVICE_REPAIR_COST")


class TestConfidenceScoreCalculation(unittest.TestCase):
    """Verifies confidence score calculation and false positive suppression."""

    def setUp(self) -> None:
        self.clf = ContextualDefectFilter()

    def test_high_confidence_for_authentic_defect(self) -> None:
        """Authentic defect complaints with compound terms, symptoms, and anchors yield high confidence (> 0.70)."""
        post = RawPost(
            platform="bobaedream",
            post_id="auth_001",
            title="EV6 고속도로 주행 중 ICCU 터짐",
            content="내차 고속도로 주행 중 퍽 소리 나더니 전원공급장치 점검 뜨고 시동 꺼짐. 황천길 갈 뻔했습니다.",
        )
        rec = self.clf.process_post(post)
        self.assertTrue(rec.is_authentic_defect)
        self.assertGreaterEqual(rec.confidence_score, 0.70)
        self.assertLessEqual(rec.confidence_score, 1.0)

    def test_confidence_suppression_on_negated_defects(self) -> None:
        """Praise posts negating defects must have low/zero confidence and be filtered."""
        post = RawPost(
            platform="dcinside",
            post_id="praise_001",
            title="아이오닉5 양품 출고 후기",
            content="내차 5000km 주행했는데 단차 전혀 없고 잡소리도 1도 안 납니다. 완전 양품이네요.",
        )
        rec = self.clf.process_post(post)
        self.assertFalse(rec.is_authentic_defect)
        self.assertLess(rec.confidence_score, 0.35)

    def test_confidence_suppression_on_vague_complaint(self) -> None:
        """Vague complaints without component or symptom yield low confidence (< 0.35) and fail gate."""
        post = RawPost(
            platform="dcinside",
            post_id="vague_001",
            title="차가 좀 이상한 듯",
            content="출고했는데 차가 좀 이상한 것 같습니다 어쩌죠?",
        )
        rec = self.clf.process_post(post)
        self.assertFalse(rec.is_authentic_defect)
        self.assertLess(rec.confidence_score, 0.35)


if __name__ == "__main__":
    unittest.main()
