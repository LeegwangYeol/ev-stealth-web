#!/usr/bin/env python3
"""
Comprehensive Audit & Hardening Test Suite: Vehicle Matcher, Slang Lexicon & Ambiguity Resolution
================================================================================================
Exhaustively verifies:
1. Domestic EV model matching:
   - Hyundai: Ioniq 5/6/9/7/5N/6N, generic Ioniq, Kona EV, Casper Electric, Porter EV, ST1
   - Genesis: GV60, GV70 EV, G80 EV, Genesis EV
   - Kia: EV3/EV6/EV9/EV2/EV4/EV5/EV6 GT/EV9 GT, Niro EV, Ray EV, Bongo EV
   - KGM: Torres EVX
2. Imported EV model matching:
   - Tesla: Model 3/Y/S/X/Cybertruck/Model 2, Highland, Juniper
   - BYD: Atto 3, Seal, Dolphin, Sealion, Han, Tang
   - Mercedes: EQE, EQS, EQ Series
   - BMW: i4, iX3, iX, i Series
   - Polestar: Polestar 2, Polestar 4, Polestar 3/5
3. Korean slang & colloquialisms:
   - '메기', '깜빡이', '버튼식 깜빡이', '깜빡이 버튼', '테쪽이', '삼식이', '이븨', '이브이',
     '아이오닉', '모델와이', '비야디', '씰', '사트', '벤츠 화재'
4. Ambiguity resolution:
   - Comparison headlines ('EV6 vs 아이오닉5' vs '아이오닉5 vs EV6')
   - Ownership anchor priority ('EV6 차주인데 아이오닉5 시승')
   - Subsumption resolution ('아이오닉5 N' vs '아이오닉5', 'EV6 GT' vs 'EV6', 'Model 3 Highland' vs 'Model 3')
   - Title priority over body content
"""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from filters.slang_lexicon import (
    OWNERSHIP_ANCHORS,
    RAW_SLANG_ENTRIES,
    SLANG_CATALOG,
    SYMPTOM_PREDICATES,
    find_matching_slang,
)
from filters.vehicle_matcher import (
    BRAND_BYD,
    BRAND_HYUNDAI,
    BRAND_KIA,
    BRAND_OTHER,
    BRAND_TESLA,
    VehicleMatcher,
    extract_vehicle_info,
)


class TestDomesticEVModelMatching(unittest.TestCase):
    """Test recognition of all Korean domestic EV models."""

    def test_hyundai_ioniq_family(self):
        cases = [
            ("아이오닉 5 출고했습니다", BRAND_HYUNDAI, "아이오닉5"),
            ("아이오닉5 배터리 완충", BRAND_HYUNDAI, "아이오닉5"),
            ("더 뉴 아이오닉 5 롱레인지", BRAND_HYUNDAI, "아이오닉5"),
            ("아이오닉 5 N 서킷 주행", BRAND_HYUNDAI, "아이오닉5 N"),
            ("아이오닉5N 랩타임", BRAND_HYUNDAI, "아이오닉5 N"),
            ("아이오닉 6 시승기", BRAND_HYUNDAI, "아이오닉6"),
            ("아이오닉6 고속 전비", BRAND_HYUNDAI, "아이오닉6"),
            ("아이오닉 6 N 공개", BRAND_HYUNDAI, "아이오닉6 N"),
            ("아이오닉 메기 디자인", BRAND_HYUNDAI, "아이오닉6"),
            ("조선 메기 승차감", BRAND_HYUNDAI, "아이오닉6"),
            ("아이오닉 9 대형 전기 SUV", BRAND_HYUNDAI, "아이오닉9"),
            ("아이오닉9 사전예약", BRAND_HYUNDAI, "아이오닉9"),
            ("아이오닉 7 콘셉트카", BRAND_HYUNDAI, "아이오닉7"),
            ("아이오닉 일렉트릭 중고", BRAND_HYUNDAI, "아이오닉"),
            ("아이오닉 전기차 충전 문제", BRAND_HYUNDAI, "아이오닉"),
            ("아이오닉 타고 여행 다녀옴", BRAND_HYUNDAI, "아이오닉"),
        ]
        for title, expected_b, expected_m in cases:
            brand, model = extract_vehicle_info(title)
            self.assertEqual(brand, expected_b, f"Brand mismatch for {title}")
            self.assertEqual(model, expected_m, f"Model mismatch for {title}")

    def test_hyundai_other_ev_models(self):
        cases = [
            ("디 올 뉴 코나 일렉트릭", BRAND_HYUNDAI, "코나 EV"),
            ("코나 EV 배터리 리콜", BRAND_HYUNDAI, "코나 EV"),
            ("캐스퍼 일렉트릭 사전계약", BRAND_HYUNDAI, "캐스퍼 일렉트릭"),
            ("캐스퍼 EV 출퇴근용", BRAND_HYUNDAI, "캐스퍼 일렉트릭"),
            ("캐스퍼 일렉트릭 크로스", BRAND_HYUNDAI, "캐스퍼 일렉트릭"),
            ("포터 일렉트릭 주행거리", BRAND_HYUNDAI, "포터 EV"),
            ("포터 EV 화물 운송", BRAND_HYUNDAI, "포터 EV"),
            ("현대 ST1 특장차 출고", BRAND_HYUNDAI, "ST1"),
        ]
        for title, expected_b, expected_m in cases:
            brand, model = extract_vehicle_info(title)
            self.assertEqual(brand, expected_b, f"Brand mismatch for {title}")
            self.assertEqual(model, expected_m, f"Model mismatch for {title}")

    def test_genesis_electrified_models(self):
        cases = [
            ("제네시스 GV60 페이스리프트", BRAND_HYUNDAI, "GV60"),
            ("일렉트리파이드 GV60 충전 속도", BRAND_HYUNDAI, "GV60"),
            ("제네시스 GV70 전동화 모델", BRAND_HYUNDAI, "GV70 EV"),
            ("GV70 EV 주행거리 테스트", BRAND_HYUNDAI, "GV70 EV"),
            ("일렉트리파이드 GV70 시승기", BRAND_HYUNDAI, "GV70 EV"),
            ("GV70e 보조금 현황", BRAND_HYUNDAI, "GV70 EV"),
            ("제네시스 G80 전동화 모델", BRAND_HYUNDAI, "G80 EV"),
            ("G80 EV 승차감 비교", BRAND_HYUNDAI, "G80 EV"),
            ("일렉트리파이드 G80 리무진", BRAND_HYUNDAI, "G80 EV"),
            ("G80e 출고 후기", BRAND_HYUNDAI, "G80 EV"),
            ("제네시스 전기차 전용 충전소", BRAND_HYUNDAI, "제네시스 EV"),
        ]
        for title, expected_b, expected_m in cases:
            brand, model = extract_vehicle_info(title)
            self.assertEqual(brand, expected_b, f"Brand mismatch for {title}")
            self.assertEqual(model, expected_m, f"Model mismatch for {title}")

    def test_kia_ev_family_and_colloquialisms(self):
        cases = [
            ("기아 EV3 롱레인지 출고", BRAND_KIA, "EV3"),
            ("EV3 어스 트림 옵션", BRAND_KIA, "EV3"),
            ("이븨3 실구매가 얼마인가요", BRAND_KIA, "EV3"),
            ("이브이3 주행거리 전비", BRAND_KIA, "EV3"),
            ("더 뉴 EV6 롱레인지", BRAND_KIA, "EV6"),
            ("이븨6 페이스리프트 단차", BRAND_KIA, "EV6"),
            ("이브이6 충전 중단 에러", BRAND_KIA, "EV6"),
            ("EV6 GT 제로백 테스트", BRAND_KIA, "EV6 GT"),
            ("이븨6 GT 가속력 미쳤네요", BRAND_KIA, "EV6 GT"),
            ("기아 EV9 6인승 시승", BRAND_KIA, "EV9"),
            ("이븨9 에어 서스펜션", BRAND_KIA, "EV9"),
            ("이브이9 고속도로 주행", BRAND_KIA, "EV9"),
            ("EV9 GT 라인 출고", BRAND_KIA, "EV9 GT"),
            ("EV4 세단 스파이샷", BRAND_KIA, "EV4"),
            ("이븨4 출시일", BRAND_KIA, "EV4"),
            ("EV5 중국 출시 후기", BRAND_KIA, "EV5"),
            ("이븨5 국내 도입", BRAND_KIA, "EV5"),
            ("EV2 소형 전기차 예상도", BRAND_KIA, "EV2"),
            ("니로 EV 주행거리", BRAND_KIA, "니로 EV"),
            ("레이 EV 도심 주행용", BRAND_KIA, "레이 EV"),
            ("봉고 EV 전기 트럭", BRAND_KIA, "봉고 EV"),
        ]
        for title, expected_b, expected_m in cases:
            brand, model = extract_vehicle_info(title)
            self.assertEqual(brand, expected_b, f"Brand mismatch for {title}")
            self.assertEqual(model, expected_m, f"Model mismatch for {title}")

    def test_torres_evx_kgm(self):
        cases = [
            ("토레스 EVX 오너 분들 계신가요", BRAND_OTHER, "토레스 EVX"),
            ("토레스 evx 보조금 신청 완료", BRAND_OTHER, "토레스 EVX"),
            ("토레스 전기차 겨울철 주행거리", BRAND_OTHER, "토레스 EVX"),
            ("torres evx 충전 속도 테스트", BRAND_OTHER, "토레스 EVX"),
            ("KGM 토레스 EVX 출고했습니다", BRAND_OTHER, "토레스 EVX"),
        ]
        for title, expected_b, expected_m in cases:
            brand, model = extract_vehicle_info(title)
            self.assertEqual(brand, expected_b, f"Brand mismatch for {title}")
            self.assertEqual(model, expected_m, f"Model mismatch for {title}")


class TestImportedEVModelMatching(unittest.TestCase):
    """Test recognition of imported EV models (Tesla, BYD, Mercedes, BMW, Polestar)."""

    def test_tesla_family_and_colloquialisms(self):
        cases = [
            ("테슬라 모델3 하이랜드 단차 점검", BRAND_TESLA, "Model 3 Highland"),
            ("모델 3 하이랜드 승차감", BRAND_TESLA, "Model 3 Highland"),
            ("M3 하이랜드 휠 얼라인먼트", BRAND_TESLA, "Model 3 Highland"),
            ("하이랜드 RWD 출고했습니다", BRAND_TESLA, "Model 3 Highland"),
            ("테슬라 모델3 롱레인지", BRAND_TESLA, "Model 3"),
            ("모델쓰리 단차 검수", BRAND_TESLA, "Model 3"),
            ("모델스리 시승해봤습니다", BRAND_TESLA, "Model 3"),
            ("삼식이 하이랜드 나오기 전 구형", BRAND_TESLA, "Model 3"),
            ("삼식이 출고 인증합니다", BRAND_TESLA, "Model 3"),
            ("테슬라 삼식이 단차 괜찮네요", BRAND_TESLA, "Model 3"),
            ("테슬라 메기 타다가 기변", BRAND_TESLA, "Model 3"),
            ("메기3 승차감 튜닝", BRAND_TESLA, "Model 3"),
            ("모델 Y 주니퍼 스파이샷", BRAND_TESLA, "Model Y Juniper"),
            ("모델와이 주니퍼 출시 언제", BRAND_TESLA, "Model Y Juniper"),
            ("MY 주니퍼 대기 중", BRAND_TESLA, "Model Y Juniper"),
            ("테슬라 모델와이 출고 후기", BRAND_TESLA, "Model Y"),
            ("모델와이 RWD 승차감 어떤가요", BRAND_TESLA, "Model Y"),
            ("모델Y 롱레인지 전비", BRAND_TESLA, "Model Y"),
            ("테슬라 모델S 플래드", BRAND_TESLA, "Model S"),
            ("모델에스 승차감 비교", BRAND_TESLA, "Model S"),
            ("테슬라 모델X 팔콘윙 단차", BRAND_TESLA, "Model X"),
            ("모델엑스 출고 대기", BRAND_TESLA, "Model X"),
            ("사이버트럭 스테인리스 단차", BRAND_TESLA, "Cybertruck"),
            ("테슬라 사트 한국 인도", BRAND_TESLA, "Cybertruck"),
            ("사트 출고했습니다", BRAND_TESLA, "Cybertruck"),
            ("싸트 차주 모임", BRAND_TESLA, "Cybertruck"),
            ("모델 2 반값 테슬라 루머", BRAND_TESLA, "Model 2"),
        ]
        for title, expected_b, expected_m in cases:
            brand, model = extract_vehicle_info(title)
            self.assertEqual(brand, expected_b, f"Brand mismatch for {title}")
            self.assertEqual(model, expected_m, f"Model mismatch for {title}")

    def test_byd_family_and_colloquialisms(self):
        cases = [
            ("BYD 아토 3 사전계약", BRAND_BYD, "Atto 3"),
            ("아토3 충전 속도 어때요", BRAND_BYD, "Atto 3"),
            ("비야디 돌핀 도심형 전기차", BRAND_BYD, "돌핀"),
            ("BYD dolphin 주행거리", BRAND_BYD, "돌핀"),
            ("비야디 씰 국내 출시 가격", BRAND_BYD, "씰"),
            ("BYD 씰 신차 출고", BRAND_BYD, "씰"),
            ("씰 EV 가속감 장난 아니네요", BRAND_BYD, "씰"),
            ("씰 세단 승차감 리뷰", BRAND_BYD, "씰"),
            ("시라이언 07 SUV", BRAND_BYD, "시라이언"),
            ("씨라이언 7 전비", BRAND_BYD, "시라이언"),
            ("비야디 한 플래그십", BRAND_BYD, "한"),
            ("BYD 탕 7인승", BRAND_BYD, "탕"),
        ]
        for title, expected_b, expected_m in cases:
            brand, model = extract_vehicle_info(title)
            self.assertEqual(brand, expected_b, f"Brand mismatch for {title}")
            self.assertEqual(model, expected_m, f"Model mismatch for {title}")

    def test_mercedes_ev_models(self):
        cases = [
            ("벤츠 EQE 350+ 화재 배터리", BRAND_OTHER, "EQE"),
            ("메르세데스 EQE 출고 후기", BRAND_OTHER, "EQE"),
            ("EQE SUV 승차감", BRAND_OTHER, "EQE"),
            ("벤츠 EQS 450+ 럭셔리 세단", BRAND_OTHER, "EQS"),
            ("EQS 580 하이퍼스크린", BRAND_OTHER, "EQS"),
            ("EQA 250 주행거리", BRAND_OTHER, "EQ Series"),
            ("EQB 패밀리 전기차", BRAND_OTHER, "EQ Series"),
        ]
        for title, expected_b, expected_m in cases:
            brand, model = extract_vehicle_info(title)
            self.assertEqual(brand, expected_b, f"Brand mismatch for {title}")
            self.assertEqual(model, expected_m, f"Model mismatch for {title}")

    def test_bmw_ev_models(self):
        cases = [
            ("BMW i4 eDrive40 출고", BRAND_OTHER, "BMW i4"),
            ("비엠 i4 M50 출력", BRAND_OTHER, "BMW i4"),
            ("BMW iX3 LCI 단차 점검", BRAND_OTHER, "BMW iX3"),
            ("비엠 ix3 승차감", BRAND_OTHER, "BMW iX3"),
            ("BMW iX xDrive50 럭셔리", BRAND_OTHER, "BMW iX"),
            ("비엠 ix 40 시승기", BRAND_OTHER, "BMW iX"),
            ("iX는 전기차 끝판왕이네요", BRAND_OTHER, "BMW iX"),
            ("ix 차주 분들 충전 질문", BRAND_OTHER, "BMW iX"),
            ("BMW i7 플래그십", BRAND_OTHER, "BMW i Series"),
            ("BMW i5 전기 세단", BRAND_OTHER, "BMW i Series"),
        ]
        for title, expected_b, expected_m in cases:
            brand, model = extract_vehicle_info(title)
            self.assertEqual(brand, expected_b, f"Brand mismatch for {title}")
            self.assertEqual(model, expected_m, f"Model mismatch for {title}")

    def test_polestar_models(self):
        cases = [
            ("폴스타 2 롱레인지 듀얼모터", BRAND_OTHER, "폴스타 2"),
            ("폴스타2 하부 잡소리", BRAND_OTHER, "폴스타 2"),
            ("폴스타 4 쿠페형 SUV 출고", BRAND_OTHER, "폴스타 4"),
            ("폴스타4 리어윈도우 리스", BRAND_OTHER, "폴스타 4"),
            ("폴스타 3 대형 SUV", BRAND_OTHER, "폴스타 3"),
            ("폴스타는 어떤 브랜드인가요", BRAND_OTHER, "폴스타"),
        ]
        for title, expected_b, expected_m in cases:
            brand, model = extract_vehicle_info(title)
            self.assertEqual(brand, expected_b, f"Brand mismatch for {title}")
            self.assertEqual(model, expected_m, f"Model mismatch for {title}")


class TestAmbiguityResolutionEngine(unittest.TestCase):
    """Test resolution when multiple vehicle names or generic terms appear."""

    def test_comparison_headline_order(self):
        """In comparison headlines without ownership cues, the leftmost vehicle wins."""
        b1, m1 = extract_vehicle_info("EV6 vs 아이오닉5 전비 비교")
        self.assertEqual((b1, m1), (BRAND_KIA, "EV6"))

        b2, m2 = extract_vehicle_info("아이오닉5 vs EV6 비교 시승")
        self.assertEqual((b2, m2), (BRAND_HYUNDAI, "아이오닉5"))

        b3, m3 = extract_vehicle_info("모델3 vs 폴스타2 고민 중입니다")
        self.assertEqual((b3, m3), (BRAND_TESLA, "Model 3"))

        b4, m4 = extract_vehicle_info("폴스타2 vs 모델3 비교해주세요")
        self.assertEqual((b4, m4), (BRAND_OTHER, "폴스타 2"))

    def test_ownership_anchor_priority(self):
        """An explicit ownership anchor attached to a vehicle trumps earlier generic mentions."""
        # EV6 owner mentions Ioniq 5 in passing
        b1, m1 = extract_vehicle_info("아이오닉5 보다가 결국 EV6 차주 됐습니다")
        self.assertEqual((b1, m1), (BRAND_KIA, "EV6"))

        b2, m2 = extract_vehicle_info("EV6 차주인데 아이오닉5랑 비교해봤어요")
        self.assertEqual((b2, m2), (BRAND_KIA, "EV6"))

        # Ioniq 5 owner mentions EV6
        b3, m3 = extract_vehicle_info("아이오닉5 차주인데 EV6보다 만족합니다")
        self.assertEqual((b3, m3), (BRAND_HYUNDAI, "아이오닉5"))

        # Delivery statement priority
        b4, m4 = extract_vehicle_info("모델Y 고민하다가 폴스타4 출고했습니다")
        self.assertEqual((b4, m4), (BRAND_OTHER, "폴스타 4"))

    def test_defect_affinity_priority(self):
        """Vehicle directly associated with defect keywords receives priority."""
        b1, m1 = extract_vehicle_info("아이오닉5 타는데 지인 EV6 결함 보니 심각하네요")
        self.assertEqual((b1, m1), (BRAND_HYUNDAI, "아이오닉5"))

        b2, m2 = extract_vehicle_info("전기차 비교하다가 EV6 결함 터져서 고생 중입니다")
        self.assertEqual((b2, m2), (BRAND_KIA, "EV6"))

    def test_subsumption_resolution(self):
        """Parent/composite model rules supersede sub-model names cleanly."""
        # Ioniq 5 N supersedes Ioniq 5
        b1, m1 = extract_vehicle_info("아이오닉 5 N 트랙 주행 결함")
        self.assertEqual((b1, m1), (BRAND_HYUNDAI, "아이오닉5 N"))

        # EV6 GT supersedes EV6
        b2, m2 = extract_vehicle_info("EV6 GT 모터 과열 경고등")
        self.assertEqual((b2, m2), (BRAND_KIA, "EV6 GT"))

        # Model 3 Highland supersedes Model 3
        b3, m3 = extract_vehicle_info("모델3 하이랜드 단차 지옥")
        self.assertEqual((b3, m3), (BRAND_TESLA, "Model 3 Highland"))

        # Model Y Juniper supersedes Model Y
        b4, m4 = extract_vehicle_info("모델Y 주니퍼 배터리 스펙")
        self.assertEqual((b4, m4), (BRAND_TESLA, "Model Y Juniper"))

    def test_title_priority_over_content(self):
        """A specific model in the title takes absolute priority over models in content."""
        title = "기아 EV6 하부 배터리팩 찍힘으로 사업소 입고"
        content = "전에 타던 아이오닉5는 멀쩡했는데 이번 EV6는 배터리 커버가 너무 얇네요. 테슬라 모델3 타는 친구도 놀람."
        brand, model = extract_vehicle_info(title, content)
        self.assertEqual((brand, model), (BRAND_KIA, "EV6"))

    def test_content_fallback_when_title_generic(self):
        """When title is generic ('전기차 결함'), model is extracted from content."""
        title = "전기차 급속 충전 질문드립니다"
        content = "내 차 아이오닉5 롱레인지인데 100kW 충전기에서 40kW밖에 안 나오네요."
        brand, model = extract_vehicle_info(title, content)
        self.assertEqual((brand, model), (BRAND_HYUNDAI, "아이오닉5"))


class TestSlangLexiconExpansion(unittest.TestCase):
    """Test newly added EV community slang terms and operational symptom predicates."""

    def test_required_community_terms_present(self):
        required_terms = [
            "메기",
            "깜빡이",
            "버튼식 깜빡이",
            "깜빡이 버튼",
            "테쪽이",
            "삼식이",
            "이븨",
            "이브이",
            "아이오닉",
            "모델와이",
            "비야디",
            "씰",
            "벤츠 화재",
        ]
        for term in required_terms:
            self.assertIn(term, SLANG_CATALOG, f"Missing required term in SLANG_CATALOG: {term}")
            entry = SLANG_CATALOG[term]
            self.assertTrue(len(entry.meaning) > 0)
            self.assertIsNotNone(entry.dimension)

    def test_find_matching_slang_with_new_terms(self):
        sample = "우리 집 테쪽이 모델와이 MCU 꺼지더니 깜빡이 소리도 안 남"
        matches = find_matching_slang(sample)
        matched_terms = [m.term for m in matches]
        self.assertIn("테쪽이", matched_terms)
        self.assertIn("모델와이", matched_terms)
        self.assertIn("깜빡이", matched_terms)

    def test_turn_signal_stalkless_defect_slang(self):
        sample = "하이랜드 버튼식 깜빡이 회전교차로에서 누르다 핸들 꼬임"
        matches = find_matching_slang(sample)
        matched_terms = [m.term for m in matches]
        self.assertIn("버튼식 깜빡이", matched_terms)

    def test_ownership_anchors_and_symptoms(self):
        self.assertIn("삼식이", OWNERSHIP_ANCHORS)
        self.assertIn("테쪽이", OWNERSHIP_ANCHORS)
        self.assertIn("이븨", OWNERSHIP_ANCHORS)
        self.assertIn("이브이", OWNERSHIP_ANCHORS)
        self.assertIn("깜빡이", SYMPTOM_PREDICATES)
        self.assertIn("소리 안 남", SYMPTOM_PREDICATES)
        self.assertIn("반응 없음", SYMPTOM_PREDICATES)


if __name__ == "__main__":
    unittest.main()
