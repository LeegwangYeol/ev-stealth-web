#!/usr/bin/env python3
"""
Unit and Integration Test Suite for Defect Filters, Vehicle Matcher, and Slang Lexicon.
Covers:
- Stage 1: Noise & Exclusion Filter (News, stock spam, prospective buyer queries, flame wars)
- Stage 2: Ownership Anchor & Operational Symptom Verification
- Stage 3: Negation, Concessive Scoping, and Sarcasm Resolution
- Stage 4: 5-Pillar Taxonomy Classification & Actionability
- DSI (Defect Severity Index), Polarity, and Negativity scoring engines
- Edge cases: Null values, empty strings, zero values, boundary values, extreme lengths
- Vehicle Matcher brand & model extraction with ambiguity resolution
- Slang Lexicon term matching and edge cases
"""

from __future__ import annotations

import os
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from filters.defect_filter import (
    CATEGORY_KEYWORD_MAP,
    NEGATIVE_LEXICON,
    POSITIVE_LEXICON,
    ContextualDefectFilter,
)
from filters.slang_lexicon import (
    CONCESSIVES,
    DIMINISHERS,
    LAUGHING_MARKERS,
    NEGATORS,
    NEWS_PATTERNS,
    OWNERSHIP_ANCHORS,
    RAW_SLANG_ENTRIES,
    SARCASM_PRAISE_WORDS,
    SLANG_CATALOG,
    STANDARD_INTENSIFIERS,
    STOCK_TERMS,
    SUPER_INTENSIFIERS,
    SYMPTOM_PREDICATES,
    SlangEntry,
    find_matching_slang,
)
from filters.vehicle_matcher import (
    BRAND_BYD,
    BRAND_HYUNDAI,
    BRAND_KIA,
    BRAND_OTHER,
    BRAND_TESLA,
    VALID_BRANDS,
    VehicleMatcher,
    extract_vehicle_info,
)
from models.complaint import (
    CANONICAL_CATEGORIES,
    ComplaintRecord,
    DSIBreakdown,
    RawPost,
)


class TestContextualDefectFilterStages(unittest.TestCase):
    """Test individual filtering stages in ContextualDefectFilter."""

    def setUp(self):
        self.filter = ContextualDefectFilter()

    def test_stage1_journalistic_patterns(self):
        """Journalistic news articles must be discarded in Stage 1."""
        news_samples = [
            "기자회견에서 현대차 관계자는 신형 아이오닉에 대해 보도했다.",
            "[단독] 환경부 전기차 보조금 개편안 확정 발표",
            "뉴스 속보: 테슬라 모델Y 화재 발생 조사 착수 (연합뉴스)",
            "기사 본문: 배터리 결함 관련 정부 대책 회의 열려. 취재 = 홍길동 기자",
        ]
        for sample in news_samples:
            discarded, reason = self.filter.evaluate_stage1_noise(sample)
            self.assertTrue(discarded, f"Expected news to be discarded: {sample}")
            self.assertIn("Journalistic", reason)

    def test_stage1_financial_stock_spam(self):
        """Stock discussions and financial spam must be discarded in Stage 1."""
        stock_samples = [
            "에코프로비엠 주가 목표주가 상향, 현대차 실적 전망 리포트",
            "테슬라 나스닥 폭락 주가 하락 매수 기회인가요?",
        ]
        for sample in stock_samples:
            discarded, reason = self.filter.evaluate_stage1_noise(sample)
            self.assertTrue(discarded, f"Expected stock discussion to be discarded: {sample}")
            self.assertIn("Financial", reason)

    def test_stage1_prospective_buyer_inquiry_vs_rhetorical_defect(self):
        """Prospective buyer inquiries are discarded, but genuine defect rhetorical questions are kept."""
        # Prospective buyer advice seeking -> Discard
        inquiry_samples = [
            "아이오닉5 vs EV6 둘 중에 뭐 살까요?",
            "테슬라 모델Y 승차감 어떤가요?",
            "전기차 보조금 올해 얼마 나오나요?",
            "아토3 살만한 차인지 궁금합니다.",
        ]
        for sample in inquiry_samples:
            discarded, reason = self.filter.evaluate_stage1_noise(sample)
            self.assertTrue(discarded, f"Expected prospective inquiry to be discarded: {sample}")

        # Genuine defect rhetorical question -> Kept (not discarded)
        defect_rhetorical = [
            "고속도로 주행 중 ICCU 터져서 멈췄는데 이거 결함 맞나요?",
            "비 오는 날 트렁크 물 새서 워터파크 됐는데 정상인가요?",
            "출고 3일 만에 배터리 경고등 뜨고 방전됐는데 사업소 가야 하나요?",
        ]
        for sample in defect_rhetorical:
            discarded, reason = self.filter.evaluate_stage1_noise(sample)
            self.assertFalse(discarded, f"Authentic defect complaint was incorrectly discarded: {sample}")

    def test_stage1_flame_wars_and_curses(self):
        """Malicious brand flaming curses must be discarded."""
        flame_samples = [
            "테슬람들 배터리 불타죽어라 ㅋㅋㅋ",
            "흉기차 개돼지들 타죽어 봐야 정신 차리지",
            "짱깨차 망해라 ㅉㅉ",
        ]
        for sample in flame_samples:
            discarded, reason = self.filter.evaluate_stage1_noise(sample)
            self.assertTrue(discarded, f"Expected flame curse to be discarded: {sample}")

    def test_stage2_ownership_verification(self):
        """Stage 2 must verify authentic owner anchors or symptom experiences."""
        # Authentic owner statements -> Pass Stage 2
        owner_samples = [
            "내 차 어제 출고받아서 비 맞았는데 테일램프 누수 발생해서 습기 찼습니다.",
            "아이오닉5 차주인데 주행 중 덜컹거리며 경고등 떴습니다.",
            "지난주 인도받고 지하주차장 오르막 롤백 결함 겪어서 사업소 예약했습니다.",
        ]
        for sample in owner_samples:
            is_owner, reason = self.filter.evaluate_stage2_ownership(sample)
            self.assertTrue(is_owner, f"Authentic owner was rejected: {sample} (reason: {reason})")

        # Third-party speculation without anchor -> Discard in Stage 2
        non_owner = "지나가는 사람인데 저 차는 디자인이 별로인 것 같습니다."
        is_owner, reason = self.filter.evaluate_stage2_ownership(non_owner)
        self.assertFalse(is_owner, "Non-owner speculation passed Stage 2")

    def test_stage3_negation_and_concessive_resolution(self):
        """Stage 3 must handle negation (안 고장남) and detect sarcasm."""
        # Negated defect -> Polarity shifted positive
        negated = "배터리 충전 전혀 문제 없고 결함 아닙니다 양품이네요."
        analysis = self.filter.evaluate_stage3_scoping(negated)
        self.assertGreaterEqual(analysis["polarity"], 0.0)

        # Sarcastic praise
        sarcastic = "단차 누수로 비 새는데 현대차 기술력 대단하다 대만족 ㅋㅋㅋ"
        analysis_sarcastic = self.filter.evaluate_stage3_scoping(sarcastic)
        self.assertTrue(analysis_sarcastic["is_sarcastic"])

    def test_stage4_5_pillar_taxonomy(self):
        """Stage 4 must correctly categorize complaints into 5 canonical pillars."""
        test_cases = [
            ("고속도로 주행 중 ICCU 고장으로 12V 배터리 방전 발생", "BATTERY_CHARGING"),
            ("빗길 맨홀 지나갈 때 회생제동 풀리면서 피쉬테일 털림", "DRIVING_POWERTRAIN"),
            ("트렁크 웨더스트립 조립 불량으로 비 오는 날 누수", "BUILD_QUALITY"),
            ("내비게이션 터치 먹통 되고 클러스터 계기판 블랙아웃", "SOFTWARE_ELECTRONICS"),
            ("배터리 팩 하부 긁힘 견적 2500만원 통교체 전손 처리", "SERVICE_REPAIR_COST"),
        ]
        for text, expected_category in test_cases:
            cat = self.filter.classify_defect_category(text)
            self.assertEqual(cat, expected_category, f"Mismatch for: {text}")


class TestContextualDefectFilterScoringAndEdgeCases(unittest.TestCase):
    """Test scoring engines, zero values, null values, and extreme inputs."""

    def setUp(self):
        self.filter = ContextualDefectFilter()

    def test_null_and_empty_inputs_to_process_post(self):
        """Empty or None posts must return safe, non-crashing ComplaintRecord."""
        empty_post = RawPost(post_id="EMPTY_01", title="", content="", comments=[])
        rec = self.filter.process_post(empty_post)
        self.assertIsInstance(rec, ComplaintRecord)
        self.assertEqual(rec.sentiment_polarity, 0.0)
        self.assertEqual(rec.negativity_score, 0.5)
        self.assertEqual(rec.severity_index, 0.0)
        self.assertFalse(rec.is_authentic_defect)

        # None inputs in dict
        none_dict = {
            "post_id": "NONE_01",
            "title": None,
            "content": None,
            "comments": None,
            "url": None,
            "author": None,
        }
        rec_none = self.filter.process_post(none_dict)
        self.assertIsInstance(rec_none, ComplaintRecord)
        self.assertEqual(rec_none.severity_index, 0.0)

    def test_dsi_score_range_and_breakdown(self):
        """DSI score must strictly stay within [0.0, 10.0] and return valid breakdown."""
        critical_text = "주행 중 배터리 화재 열폭주 발생 전손 사망 위험"
        dsi, breakdown = self.filter.compute_dsi(critical_text, "BATTERY_CHARGING")
        self.assertGreaterEqual(dsi, 7.0)
        self.assertLessEqual(dsi, 10.0)
        self.assertIsInstance(breakdown, DSIBreakdown)
        self.assertGreaterEqual(breakdown.safety, 7.0)
        self.assertLessEqual(breakdown.safety, 10.0)

        # Minor cosmetic issue
        minor_text = "조수석 도어 단차 살짝 벌어짐 마감 아쉬움"
        dsi_minor, b_minor = self.filter.compute_dsi(minor_text, "BUILD_QUALITY")
        self.assertGreaterEqual(dsi_minor, 0.0)
        self.assertLessEqual(dsi_minor, 10.0)

    def test_extreme_input_length(self):
        """Filter must handle extremely large inputs (50,000+ chars) without recursion or memory crash."""
        large_body = "내 차 배터리 충전 중 ICCU 터짐. " * 3000
        post = RawPost(post_id="HUGE_01", title="대형 글 테스트", content=large_body)
        rec = self.filter.process_post(post)
        self.assertIsInstance(rec, ComplaintRecord)
        self.assertTrue(rec.is_authentic_defect)
        self.assertEqual(rec.defect_category, "BATTERY_CHARGING")


class TestVehicleMatcher(unittest.TestCase):
    """Test vehicle brand and model extraction logic with edge cases."""

    def test_canonical_brands_coverage(self):
        """Vehicle matcher must classify canonical EV brands."""
        test_cases = [
            ("현대 더 뉴 아이오닉 5 롱레인지 출고", BRAND_HYUNDAI, "아이오닉5"),
            ("기아 EV6 GT 라인 주행 후기", BRAND_KIA, "EV6"),
            ("테슬라 모델3 하이랜드 단차 점검", BRAND_TESLA, "Model 3 Highland"),
            ("BYD 아토3 급속 충전 속도", BRAND_BYD, "Atto 3"),
            ("포르쉐 타이칸 4S 배터리 교체", BRAND_OTHER, "타이칸"),
        ]
        for title, expected_brand, expected_model in test_cases:
            brand, model = extract_vehicle_info(title)
            self.assertEqual(brand, expected_brand, f"Brand mismatch for {title}")
            self.assertIn(expected_model, model, f"Model mismatch for {title}")

    def test_disambiguation_bmw_m3_vs_model_3(self):
        """BMW M3 must not be classified as Tesla Model 3."""
        bmw_cases = [
            "BMW M3 엔진오일 누유 문의",
            "M3 컴페티션 차주인데 승차감 너무 딱딱함",
            "비엠더블유 M3 코너링 성능",
        ]
        for title in bmw_cases:
            brand, model = extract_vehicle_info(title)
            self.assertEqual(brand, BRAND_OTHER, f"BMW M3 was misclassified as {brand}: {title}")
            self.assertEqual(model, "BMW M3")

    def test_disambiguation_english_my_vs_model_y(self):
        """English word 'my' must not trigger Tesla Model Y."""
        english_cases = [
            "This is my first electric car experience",
            "In my opinion charging speed is fine",
            "I love my daily commute",
        ]
        for text in english_cases:
            brand, model = extract_vehicle_info(text)
            self.assertNotEqual(model, "Model Y", f"English 'my' triggered Model Y for: {text}")

    def test_disambiguation_door_seal_vs_byd_seal(self):
        """Weatherstrip door seal must not trigger BYD Seal."""
        seal_cases = [
            "아이오닉5 도어 씰 고무 몰딩 들뜸 현상",
            "웨더스트립 씰 틈새로 풍절음 들어옵니다",
        ]
        for title in seal_cases:
            brand, model = extract_vehicle_info(title)
            self.assertNotEqual(model, "씰", f"Door seal triggered BYD Seal for: {title}")

    def test_null_and_empty_inputs_to_matcher(self):
        """None or empty inputs must return default fallback without crash."""
        b1, m1 = extract_vehicle_info("")
        self.assertEqual(b1, BRAND_OTHER)
        self.assertEqual(m1, "전기차")

        b2, m2 = extract_vehicle_info(None, None)
        self.assertEqual(b2, BRAND_OTHER)
        self.assertEqual(m2, "전기차")

        b3, m3 = VehicleMatcher.match("", "")
        self.assertEqual(b3, BRAND_OTHER)


class TestSlangLexicon(unittest.TestCase):
    """Test Korean automotive slang lexicon catalog and extraction."""

    def test_slang_catalog_entries(self):
        """Catalog must contain essential defect and component slang terms."""
        essential_terms = ["피쉬테일", "수막현상", "굼벵이 충전", "ICCU 폭탄", "황천길", "어라운드뷰 왜곡", "MCU 블랙아웃"]
        for term in essential_terms:
            self.assertIn(term, SLANG_CATALOG, f"Missing essential slang term: {term}")
            entry = SLANG_CATALOG[term]
            self.assertIsInstance(entry, SlangEntry)
            self.assertTrue(len(entry.meaning) > 0)

    def test_find_matching_slang_matches(self):
        """Matching slang terms must be accurately extracted from raw text."""
        sample = "순정 출고 타이어 빗길 수막현상으로 피쉬테일 털려서 황천길 갈 뻔"
        matches = find_matching_slang(sample)
        terms = [m.term for m in matches]
        self.assertIn("피쉬테일", terms)
        self.assertIn("수막현상", terms)
        self.assertIn("황천길", terms)

    def test_find_matching_slang_null_empty(self):
        """Empty or null strings must safely return empty lists."""
        self.assertEqual(find_matching_slang(""), [])
        self.assertEqual(find_matching_slang(None), [])


if __name__ == "__main__":
    unittest.main()
