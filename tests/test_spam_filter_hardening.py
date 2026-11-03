#!/usr/bin/env python3
"""Comprehensive Hardening Test Suite for SpamFilter Stage 1.

Audits:
1. Regex patterns for promotional ads, commercial spam, dealer links, affiliate codes, scam promotions.
2. Filtering out speculative financial or unrelated political discussions.
3. Preventing false positives on genuine owner complaints that include price or dealer names.
4. Input validation (None, non-string, extremely long text strings, null bytes).
"""

from __future__ import annotations

from pathlib import Path
import sys
import time
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from filters.spam_filter import (
    AFFILIATE_REGEXES,
    COMMERCIAL_SPAM_KEYWORDS,
    COMMERCIAL_SPAM_REGEXES,
    CONTACT_SPAM_REGEXES,
    DEALER_PROMO_REGEXES,
    FINANCIAL_SPECULATION_TERMS,
    POLITICAL_TERMS,
    SCAM_PROMO_REGEXES,
    SpamFilter,
    evaluate_stage1_noise,
    is_spam,
    sanitize_input,
)


class TestSpamFilterPromotionalAndScamPatterns(unittest.TestCase):
    """Test 1: Regex patterns for ads, commercial spam, dealer links, affiliate codes, scams."""

    def setUp(self) -> None:
        self.filter = SpamFilter()

    def test_affiliate_and_referral_codes(self) -> None:
        """Referral codes, coupon discounts, affiliate links must be filtered."""
        affiliate_samples = [
            "테슬라 모델Y 구매 시 리퍼럴 코드 ts.la/myreferral123 입력하시면 66만원 할인 혜택",
            "아이오닉6 구매할 때 추천인 코드 입력하고 포인트 받으세요. 추천인 코드: EV2026KING",
            "쿠팡 자동차용품 특가 링크 link.coupang.com/a/b12345 확인해보세요.",
            "신차 구매 프로모션 코드: PROMO-9988 입력 시 50만원 캐시백",
            "Use my Tesla referral code to get 1000 supercharging credits ts.la/abc",
            "알리익스프레스 EV 악세사리 coupa.ng/abcdef 할인 링크 공유합니다.",
        ]
        for text in affiliate_samples:
            is_disc, reason = self.filter.evaluate_stage1_noise(text)
            self.assertTrue(is_disc, f"Affiliate promo not discarded: {text}")
            self.assertIn("Commercial", reason)

    def test_dealer_promotional_broker_ads(self) -> None:
        """Long-term rent/lease brokers, tinting packages, dealer cash payback ads must be filtered."""
        dealer_samples = [
            "신차 장기렌트 특가 즉시출고! 최저가 견적비교 상담문의 환영",
            "전기차 즉시출고 초특가 할인 이벤트 선착순 리스 견적 신청",
            "신차패키지 썬팅 틴팅 블랙박스 공동구매 특가 시공 이벤트 문의",
            "딜러 특별 지원 현금 페이백 최대 지원 서비스 증정 010-1234-5678로 문의",
            "전국 최저가 견적비교 무료 시승 신청 예약 open.kakao.com/car123",
        ]
        for text in dealer_samples:
            is_disc, reason = self.filter.evaluate_stage1_noise(text)
            self.assertTrue(is_disc, f"Dealer ad not discarded: {text}")
            self.assertIn("Commercial", reason)

    def test_contact_solicitations_and_direct_channels(self) -> None:
        """Open KakaoTalk, Telegram, Line IDs, and phone solicitations must be filtered."""
        contact_samples = [
            "전기차 시승 및 보조금 문의 open.kakao.com/me/evdealers",
            "신차 견적 상담 카카오 플러스친구 pf.kakao.com/_deal123",
            "비공개 특가 정보 텔레그램 t.me/ev_secret_room 입장",
            "상담 문의 카톡 ID: carmaster77 주세요",
            "특가 리스 차량 문의 010-9876-5432로 연락 부탁드립니다.",
            "단독 할인 링크 bit.ly/ev_special_discount 클릭",
        ]
        for text in contact_samples:
            is_disc, reason = self.filter.evaluate_stage1_noise(text)
            self.assertTrue(is_disc, f"Contact solicitation not discarded: {text}")
            self.assertIn("Commercial", reason)

    def test_scam_promotions_gambling_loans(self) -> None:
        """Crypto/stock reading rooms, gambling, adult, and illegal loan cashing must be filtered."""
        scam_samples = [
            "주식 리딩방 무료체험 VIP 추천주 원금 보장 수익률 100% 달성",
            "코인 리딩방 단톡방 수익률 극대화 프로젝트 무료 입장",
            "바카라 사설토토 파워볼 안전놀이터 꽁머니 첫충 매충 이벤트",
            "소액결제 현금화 정보이용료 카드깡 5분 입금 비상금 마련",
            "무직자 당일 대출 승인 저신용자 급전 당일지급 상담",
            "출장안마 24시 조건만남 예약 문의",
        ]
        for text in scam_samples:
            is_disc, reason = self.filter.evaluate_stage1_noise(text)
            self.assertTrue(is_disc, f"Scam/illicit promo not discarded: {text}")
            self.assertIn("Commercial", reason)


class TestSpamFilterFinancialAndPoliticalSpeculation(unittest.TestCase):
    """Test 2: Filtering out speculative financial or unrelated political discussions."""

    def setUp(self) -> None:
        self.filter = SpamFilter()

    def test_speculative_stock_and_equities_trading(self) -> None:
        """Speculative stock equities discussions without vehicle defects must be filtered."""
        stock_samples = [
            "테슬라 주가 나스닥 폭락 매수 기회인가요? 평단 낮추려 합니다.",
            "에코프로비엠 주가 목표주가 상향 현대차 실적 전망 리포트",
            "코스피 코스닥 시장 공매도 숏스퀴즈 테슬라 주식 전망",
            "어닝쇼크 실적발표 이후 목표주가 하향 매도 의견",
        ]
        for text in stock_samples:
            is_disc, reason = self.filter.evaluate_stage1_noise(text)
            self.assertTrue(is_disc, f"Stock speculation not discarded: {text}")
            self.assertIn("Financial", reason)
            self.assertIn("stock", reason.lower())

    def test_speculative_crypto_and_derivatives(self) -> None:
        """Speculative crypto/derivative trading discussions must be filtered."""
        crypto_samples = [
            "비트코인 이더리움 가상화폐 업비트 차트분석 골든크로스 발생",
            "바이낸스 코인 선물거래 숏포지션 레버리지 마진 청산맵 분석",
        ]
        for text in crypto_samples:
            is_disc, reason = self.filter.evaluate_stage1_noise(text)
            self.assertTrue(is_disc, f"Crypto speculation not discarded: {text}")
            self.assertIn("Financial", reason)

    def test_unrelated_partisan_political_discussions(self) -> None:
        """Partisan political conflicts and ideological flame wars must be filtered."""
        political_samples = [
            "윤석열 대통령 탄핵 민주당 국민의힘 총선 여야 갈등",
            "이재명 문재인 개딸 수박 좌빨 토착왜구 정치병자들 싸움",
            "한동훈 조국 총선 정권심판 정권교체 여론조사 지지율",
            "더불어민주당 개혁신당 야당 여당 국회의원 탄핵 청원",
        ]
        for text in political_samples:
            is_disc, reason = self.filter.evaluate_stage1_noise(text)
            self.assertTrue(is_disc, f"Political discussion not discarded: {text}")
            self.assertIn("political", reason.lower())

    def test_government_agency_defect_filing_not_misidentified_as_news(self) -> None:
        """Owner reports mentioning filing complaints with MOLIT/국토부 must NOT be discarded as news wires."""
        valid_filing = "내 차 ICCU 터져서 고속도로 멈춘 뒤 국토교통부에 결함 신고서 접수했습니다."
        is_disc, reason = self.filter.evaluate_stage1_noise(valid_filing)
        self.assertFalse(is_disc, f"Owner reporting to MOLIT falsely discarded as news: {reason}")

        valid_complaint = "블루핸즈에서 수리 거부당해서 국토부 민원 넣고 왔습니다."
        is_disc, reason = self.filter.evaluate_stage1_noise(valid_complaint)
        self.assertFalse(is_disc, f"Owner MOLIT complaint falsely discarded: {reason}")


class TestSpamFilterPreventFalsePositivesOnGenuineComplaints(unittest.TestCase):
    """Test 3: Preventing false positives on genuine complaints with price or dealer names."""

    def setUp(self) -> None:
        self.filter = SpamFilter()

    def test_genuine_complaints_mentioning_dealers_or_agents(self) -> None:
        """Owner complaints quoting salespeople or dealers must NOT be treated as commercial spam."""
        dealer_complaints = [
            "성수 하이테크센터 딜러가 출고 전에는 단차 다 잡아준다더니 출고 후 연락 두절됐습니다.",
            "일산 서비스센터 지점장과 딜러가 모터 고주파 소음 정상이라고 우겨서 대판 싸우고 왔네요.",
            "영업사원 카마스터가 ICCU 결함 없다고 거짓말해서 계약했는데 고속도로에서 멈췄습니다.",
            "대리점 직원이 신차 인수장에서 도장 불량과 단차를 인수거부 못하게 강요합니다.",
            "분당 블루핸즈 정비사랑 센터장이 배터리 방전 문제로 발뺌해서 화가 납니다.",
        ]
        for text in dealer_complaints:
            is_disc, reason = self.filter.evaluate_stage1_noise(text)
            self.assertFalse(is_disc, f"Authentic complaint with dealer mention falsely discarded: {reason} | Text: {text}")

    def test_genuine_complaints_mentioning_repair_prices_and_depreciation(self) -> None:
        """Owner complaints with repair costs, quotes, and depreciation loss must NOT be discarded."""
        cost_complaints = [
            "배터리 팩 하부 긁힘으로 서비스센터 수리 견적 2,500만원 통교체 견적서 청구받았습니다.",
            "차값 7,000만원짜리 차가 출고 3개월 만에 감가상각 2천만원 손해보고 똥값 됐네요.",
            "블루핸즈에서 인버터 교체비용 800만원 부르는데 보험 처리 자차 전손 가야 할지 고민입니다.",
            "단차 도장 불량으로 인수거부하려니 딜러가 50만원 할인해줄 테니 그냥 타라고 합니다.",
            "수리비 폭탄 맞고 배터리 교체비 3000만원 청구서 받아서 너무 억울합니다.",
        ]
        for text in cost_complaints:
            is_disc, reason = self.filter.evaluate_stage1_noise(text)
            self.assertFalse(is_disc, f"Authentic complaint with price/quote falsely discarded: {reason} | Text: {text}")

    def test_genuine_owner_questions_with_dealer_or_price(self) -> None:
        """Authentic owner questions about repairs or dealer interactions ending in '?' must be kept."""
        question_samples = [
            "성수 하이테크센터에서 ICCU 수리비 500만원 견적 나왔는데 이거 무상보증 안 되나요?",
            "딜러가 트렁크 누수 물 새는 거 정상이라는데 사업소 다시 가야 하나요?",
            "내 차 주행 중 모터 소음 밥솥 소리 나는데 블루핸즈 입고해야 하나요?",
        ]
        for text in question_samples:
            is_disc, reason = self.filter.evaluate_stage1_noise(text)
            self.assertFalse(is_disc, f"Owner question with dealer/price falsely discarded: {reason} | Text: {text}")


class TestSpamFilterInputValidationAndEdgeCases(unittest.TestCase):
    """Test 4: Input validation (None, non-string, extremely long text strings, null bytes)."""

    def setUp(self) -> None:
        self.filter = SpamFilter()

    def test_none_empty_and_whitespace_inputs(self) -> None:
        """None, empty, or whitespace-only inputs must be safely discarded."""
        empty_inputs = [None, "", "   ", "\t\t\n\n\r", "   \n\t   "]
        for inp in empty_inputs:
            is_disc, reason = self.filter.evaluate_stage1_noise(inp)
            self.assertTrue(is_disc)
            self.assertIn("Empty", reason)
            self.assertTrue(self.filter.is_spam(inp))

    def test_null_byte_sanitization(self) -> None:
        """Embedded null bytes (\\x00) must be sanitized without crashing or bypassing filters."""
        # Genuine complaint with null byte
        text_with_null = "내 차\x00 고속도로에서 배터리 ICCU 터짐\x00으로 멈춤"
        is_disc, _ = self.filter.evaluate_stage1_noise(text_with_null)
        self.assertFalse(is_disc, "Cleaned complaint with null byte was wrongly discarded")

        # Commercial spam disguised with null byte
        spam_with_null = "카톡\x00 상담 loan119 당일 대출"
        is_disc, reason = self.filter.evaluate_stage1_noise(spam_with_null)
        self.assertTrue(is_disc, "Spam with null byte was not caught")
        self.assertIn("Commercial", reason)

        # Journalistic news with null byte
        news_with_null = "[단독]\x00 국토교통부에 따르면 현대차 리콜 발표"
        is_disc, reason = self.filter.evaluate_stage1_noise(news_with_null)
        self.assertTrue(is_disc, "News with null byte was not caught")
        self.assertIn("Journalistic", reason)

    def test_non_string_types_coercion(self) -> None:
        """Numbers, bytearrays, dicts, custom objects must be safely coerced."""
        self.assertTrue(self.filter.is_spam(0))  # "0" -> purely numeric -> non-linguistic noise
        self.assertTrue(self.filter.is_spam(12345))

        # Bytes decoding
        bytes_complaint = "내 차 아이오닉5 배터리 누수 결함".encode("utf-8")
        is_disc, _ = self.filter.evaluate_stage1_noise(bytes_complaint)
        self.assertFalse(is_disc, "Valid bytes complaint was rejected")

        # Custom object
        class CustomPost:
            def __str__(self) -> str:
                return "내 차 ICCU 폭탄 터져서 고속도로 멈춤"

        is_disc, _ = self.filter.evaluate_stage1_noise(CustomPost())
        self.assertFalse(is_disc, "Custom object complaint was rejected")

    def test_extremely_long_strings_memory_and_redos_defense(self) -> None:
        """Adversarial long strings (500k+ chars) must be processed within 80ms without crashing."""
        # 500,000 character repeating string
        adversarial_long = ("대출 바카라 주가 나스닥 " * 25000)[:500000]
        t0 = time.time()
        is_disc, reason = self.filter.evaluate_stage1_noise(adversarial_long)
        dur = time.time() - t0

        self.assertTrue(is_disc)
        self.assertLess(dur, 0.08, f"Long string evaluation took {dur:.4f}s; potential ReDoS or memory leak!")

        # Long authentic complaint (40,000 chars)
        long_complaint = ("내 차 배터리 충전 중 ICCU 터짐 고장. " * 2000)[:40000]
        t0 = time.time()
        is_disc, _ = self.filter.evaluate_stage1_noise(long_complaint)
        dur = time.time() - t0
        self.assertFalse(is_disc, "Long authentic complaint was discarded")
        self.assertLess(dur, 0.08, f"Long complaint took {dur:.4f}s")

    def test_filter_posts_edge_cases(self) -> None:
        """filter_posts must safely handle None, non-iterables, malformed items, and retain authentic posts."""
        # None and non-iterable inputs
        self.assertEqual(self.filter.filter_posts(None), [])
        self.assertEqual(self.filter.filter_posts(12345), [])
        self.assertEqual(self.filter.filter_posts("not a list of posts"), [])

        # List with None and malformed dictionaries
        mixed_posts = [
            None,
            {"title": None, "content": None, "url": None},
            {"title": "광고", "content": "카톡 상담 대출 문의", "url": ""},
            {"title": "정상 결함", "content": "내 차 주행 중 ICCU 터져서 멈춤", "url": "https://cafe.naver.com/1"},
            {"corrupted": "no title or content"},
        ]
        retained = self.filter.filter_posts(mixed_posts)
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0]["title"], "정상 결함")


if __name__ == "__main__":
    unittest.main()
