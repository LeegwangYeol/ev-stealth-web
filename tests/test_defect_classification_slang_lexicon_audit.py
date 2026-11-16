"""Comprehensive Verification Test Suite for Defect Classification, Slang Lexicon & Filters Audit.

Verifies:
1. Commercial spam regex refinement & false positive prevention on owner contact narratives
2. Telegram community defect discussions not falsely flagged as commercial spam
3. Rhetorical negation and hearsay contrastive defect reports properly categorized as authentic defects
4. Brand pejoratives/nicknames excluded from negated defect lists
5. Highlander, Juniper, MS software, and MX player boundary robustness
6. Kia Soul EV and imported/alternative brand keyword additions
"""

import unittest

from filters.defect_classifier import DefectClassifier
from filters.slang_lexicon import find_matching_slang
from filters.spam_filter import SpamFilter
from filters.vehicle_matcher import BRAND_KIA, BRAND_OTHER, BRAND_TESLA, extract_vehicle_info


class TestDefectClassificationAndSlangAudit(unittest.TestCase):
    def setUp(self) -> None:
        self.classifier = DefectClassifier()
        self.spam_filter = SpamFilter()

    # -----------------------------------------------------------------
    # 1. Commercial Spam & Phone Number Narrative Tests
    # -----------------------------------------------------------------
    def test_owner_phone_narratives_not_flagged_as_commercial_spam(self) -> None:
        """First-person narratives mentioning phone contacts must not be flagged as spam."""
        safe_owner_narratives = [
            "고속도로에서 배터리 경고등 켜져서 견인차 불렀는데 010-1234-5678로 연락했습니다.",
            "서비스센터 어드바이저 010-1234-5678로 문자 보냈더니 답장이 없네요.",
            "단차 수리 관련해서 담당자 010-9876-5432로 문의했더니 정상이랍니다.",
        ]
        for text in safe_owner_narratives:
            is_spam, reason = self.spam_filter.evaluate_stage1_noise(text)
            self.assertFalse(is_spam, f"Falsely flagged owner narrative as spam: {text} (Reason: {reason})")

    def test_actual_commercial_phone_solicitations_flagged_as_spam(self) -> None:
        """Explicit commercial solicitations with phone numbers must be detected as spam."""
        spam_solicitations = [
            "장기렌트 즉시출고 최저가 010-1234-5678로 문의주세요",
            "신차 패키지 특가 상담처: 010-1234-5678",
            "오토리스 최저가 비교 010-9876-5432 로 문자바랍니다",
        ]
        for text in spam_solicitations:
            is_spam, reason = self.spam_filter.evaluate_stage1_noise(text)
            self.assertTrue(is_spam, f"Failed to detect phone solicitation spam: {text}")

    def test_telegram_community_discussions_not_flagged_as_commercial_spam(self) -> None:
        """Discussions mentioning telegram groups for defect/recall info must be retained."""
        legit_telegram_posts = [
            "단차 결함 때문에 텔레그램 방에서 집단 소송 준비 중입니다.",
            "텔레그램 차주 모임에서 ICCU 리콜 소식 들었습니다.",
        ]
        for text in legit_telegram_posts:
            is_spam, reason = self.spam_filter.evaluate_stage1_noise(text)
            self.assertFalse(is_spam, f"Falsely flagged telegram community post as spam: {text} (Reason: {reason})")

    # -----------------------------------------------------------------
    # 2. Rhetorical Negation & Hearsay Contrastive Defect Handling
    # -----------------------------------------------------------------
    def test_rhetorical_negations_classified_as_authentic_defects(self) -> None:
        """Rhetorical reversals ('없기는 개뿔', '없기는커녕') must qualify as authentic defects."""
        rhetorical_posts = [
            "내 차 아이오닉5 출고했는데 단차 없기는 개뿔 진짜 심해요",
            "내 차 EV6 출고했는데 잡소리 없기는커녕 귀신소리 오지네요",
            "신차 인수했는데 도장 불량 없기는 무슨 범퍼에 기스 개판입니다",
        ]
        for text in rhetorical_posts:
            record = self.classifier.classify(text)
            self.assertTrue(
                record.is_authentic_defect,
                f"Rhetorical defect post failed classification: {text} (Reason: {record.filter_reason}, Polarity: {record.sentiment_polarity})",
            )
            self.assertLess(record.sentiment_polarity, 0.0)

    def test_hearsay_contrastive_defects_classified_as_authentic(self) -> None:
        """Hearsay contrastive reports ('없다더니', '안 난다더니') must qualify as authentic defects."""
        hearsay_posts = [
            "내 차 EV6 출고했는데 잡소리 없다더니 고속도로 올리자마자 찌걱찌걱 난리남",
            "내 차 아이오닉6 잡소리 안 난다더니 주행 중 고주파음 미치겠네요",
            "내 차 단차 없다고 들었는데 실제로 보니 엄청 심함",
        ]
        for text in hearsay_posts:
            record = self.classifier.classify(text)
            self.assertTrue(
                record.is_authentic_defect,
                f"Hearsay defect post failed classification: {text} (Reason: {record.filter_reason}, Polarity: {record.sentiment_polarity})",
            )
            self.assertLess(record.sentiment_polarity, 0.0)

    # -----------------------------------------------------------------
    # 3. Brand Pejorative & Nickname Negation Protection
    # -----------------------------------------------------------------
    def test_brand_pejoratives_not_treated_as_negated_defects(self) -> None:
        """Statements negating brand pejoratives must not produce negated defect tags."""
        pejorative_phrases = [
            "여기는 현기충 없어서 좋네요",
            "커뮤니티에 테슬람 없어서 클린함",
            "매장에 비야디 씰 없어서 다른 차 봤습니다",
        ]
        for text in pejorative_phrases:
            res = self.classifier.evaluate_stage3_scoping(text)
            self.assertEqual(
                res["negated_defects"],
                [],
                f"Brand pejorative or model falsely included in negated_defects: {text} -> {res['negated_defects']}",
            )

    # -----------------------------------------------------------------
    # 4. Vehicle Matcher Robustness & Ambiguity Resolution
    # -----------------------------------------------------------------
    def test_highlander_and_juniper_boundary_precision(self) -> None:
        """Toyota Highlander and Juniper router must not match Tesla models."""
        # Non-Tesla false positive suppression
        brand, model = extract_vehicle_info("Toyota Highlander hybrid defect")
        self.assertEqual(brand, BRAND_OTHER)
        self.assertNotEqual(model, "Model 3 Highland")

        brand, model = extract_vehicle_info("Juniper Networks router defect")
        self.assertEqual(brand, BRAND_OTHER)
        self.assertNotEqual(model, "Model Y Juniper")

        # True Tesla models match accurately
        brand, model = extract_vehicle_info("테슬라 하이랜드 출고 후 단차 점검")
        self.assertEqual(brand, BRAND_TESLA)
        self.assertEqual(model, "Model 3 Highland")

        brand, model = extract_vehicle_info("Tesla Model Y Juniper reservation")
        self.assertEqual(brand, BRAND_TESLA)
        self.assertEqual(model, "Model Y Juniper")

    def test_ms_and_mx_service_boundary_precision(self) -> None:
        """Microsoft software and MX DNS/media terms must not match Tesla Model S/X."""
        b1, m1 = extract_vehicle_info("MS 워드 문서 열기 오류")
        self.assertEqual(b1, BRAND_OTHER)
        self.assertNotEqual(m1, "Model S")

        b2, m2 = extract_vehicle_info("MX 레코드 설정 오류")
        self.assertEqual(b2, BRAND_OTHER)
        self.assertNotEqual(m2, "Model X")

        # True Tesla models match accurately
        b3, m3 = extract_vehicle_info("MS 롱레인지 승차감 비교")
        self.assertEqual(b3, BRAND_TESLA)
        self.assertEqual(m3, "Model S")

        b4, m4 = extract_vehicle_info("MX 플래드 출고했습니다")
        self.assertEqual(b4, BRAND_TESLA)
        self.assertEqual(m4, "Model X")

    def test_kia_soul_ev_and_imported_brand_matching(self) -> None:
        """Kia Soul EV and imported brands like Renault must match canonically."""
        b_soul, m_soul = extract_vehicle_info("기아 쏘울 EV 배터리 교체 완료")
        self.assertEqual(b_soul, BRAND_KIA)
        self.assertEqual(m_soul, "쏘울 EV")

        b_renault, _ = extract_vehicle_info("르노 전기차 배터리 고장")
        self.assertEqual(b_renault, BRAND_OTHER)


if __name__ == "__main__":
    unittest.main()
