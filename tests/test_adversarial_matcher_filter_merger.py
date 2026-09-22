#!/usr/bin/env python3
"""
Adversarial Stress Test Suite: Vehicle Matcher, Defect Filter, and JSON Writer Merger
====================================================================================
Tests the robustness, edge cases, and crash resilience of:
1. Vehicle Matcher (filters/vehicle_matcher.py):
   - BMW M3 vs Tesla Model 3 collisions
   - English word "my" vs Tesla Model Y
   - Weatherstrip "도어 씰" vs BYD Seal
   - Mixed casing, typos, complex sentences, verbal suffix blind spots
2. Defect Filter (filters/defect_filter.py):
   - Authentic rhetorical question defect complaints
   - Prospective buyer inquiries and advice seeking (~나요?, ~가요?, 살까요, 궁금)
   - News, financial spam, and flame wars
3. JSON Writer & Historical Merging (utils/json_writer.py):
   - In-batch duplicate IDs and duplicate URLs
   - Merge with existing files and ID deduplication
   - Empty lists handling
   - Malformed entries (None, non-numeric strings, None defect_category)
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from filters.defect_filter import ContextualDefectFilter
from filters.vehicle_matcher import (
    BRAND_BYD,
    BRAND_HYUNDAI,
    BRAND_KIA,
    BRAND_OTHER,
    BRAND_TESLA,
    extract_vehicle_info,
)
from models.complaint import ComplaintRecord, RawPost
from utils.json_writer import (
    format_daily_report_payload,
    read_daily_reports,
    write_daily_reports,
)


class TestVehicleMatcherEdgeCases(unittest.TestCase):
    """Adversarial stress tests for vehicle brand and model extraction."""

    def test_01_bmw_m3_vs_tesla_model3_standard(self):
        """Verify standard BMW M3 and Tesla Model 3 distinctions."""
        # Standard BMW M3
        b1, m1 = extract_vehicle_info("BMW M3 엔진오일 누유 결함")
        self.assertEqual(b1, BRAND_OTHER)
        self.assertEqual(m1, "BMW M3")

        b2, m2 = extract_vehicle_info("비엠 M3 서스펜션 잡소리")
        self.assertEqual(b2, BRAND_OTHER)
        self.assertEqual(m2, "BMW M3")

        # Standard Tesla Model 3
        b3, m3 = extract_vehicle_info("테슬라 모델3 하이랜드 단차 심각")
        self.assertEqual(b3, BRAND_TESLA)
        self.assertEqual(m3, "Model 3 Highland")

        b4, m4 = extract_vehicle_info("테슬라 M3 롱레인지 출고 후기")
        self.assertEqual(b4, BRAND_TESLA)
        self.assertEqual(m4, "Model 3")

    def test_02_bmw_m3_competition_collision_exposure(self):
        """Remediated: 'm3 컴페티션' without preceding 'bmw' keyword is correctly classified as BMW M3."""
        brand, model = extract_vehicle_info("M3 컴페티션 차주인데 승차감 너무 딱딱함")
        self.assertEqual(brand, BRAND_OTHER)
        self.assertEqual(model, "BMW M3")

    def test_03_bmw_m3_spacing_and_particle_variations(self):
        """Test multi-space padding and grammatical particles preceding M3."""
        # Double space "BMW  M3"
        b1, m1 = extract_vehicle_info("BMW  M3 트랙 주행기")
        # "bmw의 m3"
        b2, m2 = extract_vehicle_info("bmw의 m3 결함 문의")
        # "비엠더블유  m3"
        b3, m3 = extract_vehicle_info("비엠더블유  m3 브레이크 소음")

        self.assertEqual(b1, BRAND_OTHER)
        self.assertEqual(m1, "BMW M3")
        self.assertEqual(b2, BRAND_OTHER)
        self.assertEqual(m2, "BMW M3")
        self.assertEqual(b3, BRAND_OTHER)
        self.assertEqual(m3, "BMW M3")

    def test_04_english_word_my_vs_model_y(self):
        """Verify English word 'my' does not falsely trigger Tesla Model Y."""
        english_phrases = [
            "my car battery is dead",
            "In my opinion this is bad",
            "my phone is connected",
            "my problem is solved",
            "my battery is dead",
            "my motor is broken",
            "my car is broken",
            "This is my new car",
            "my project is done",
            "my post on the forum",
            "my way or highway",
            "Oh my god!",
            "my dear friend",
            "my friend bought an EV",
        ]
        for phrase in english_phrases:
            brand, model = extract_vehicle_info(phrase)
            self.assertNotEqual(
                (brand, model),
                (BRAND_TESLA, "Model Y"),
                f"False positive Model Y match on English phrase: '{phrase}'",
            )

        # Legitimate Model Y variants MUST match
        valid_my = [
            ("테슬라 my rwd 출고했습니다", (BRAND_TESLA, "Model Y")),
            ("MY는 승차감 어떤가요?", (BRAND_TESLA, "Model Y")),
            ("MY가 고장났습니다", (BRAND_TESLA, "Model Y")),
            ("MY 오너 분들 계신가요", (BRAND_TESLA, "Model Y")),
            ("MY RWD 단차 심함", (BRAND_TESLA, "Model Y")),
            ("MY 롱레인지 주행거리", (BRAND_TESLA, "Model Y")),
            ("MY 주니퍼 언제 나오나요?", (BRAND_TESLA, "Model Y Juniper")),
            ("모델Y 주니퍼 시승기", (BRAND_TESLA, "Model Y Juniper")),
        ]
        for phrase, expected in valid_my:
            actual = extract_vehicle_info(phrase)
            self.assertEqual(actual, expected, f"Failed on valid Model Y: '{phrase}'")

    def test_05_weatherstrip_seal_vs_byd_seal(self):
        """Verify generic automotive weatherstrips ('도어 씰', etc.) do not trigger BYD Seal."""
        weatherstrip_phrases = [
            "도어 씰 불량으로 트렁크 누수 발생",
            "도어씰 들뜸으로 풍절음 심함",
            "트렁크 씰 들뜸으로 소음 심함",
            "트렁크씰 방수 불량",
            "웨더스트립 씰 교체 비용 문의",
            "고무 씰 찢어짐 결함",
            "고무씰 패킹 교환",
            "오일 씰 누유 심각",
            "오일씰 교환 공임비",
            "윈도우 씰 고무 패킹 불량",
            "윈도우씰 잡소리",
            "유리 씰 방수 결함",
            "유리씰 탈착",
            "모터 씰 누유",
            "방수 씰 부품 교체",
            "방수씰 틈새 누수",
            "엔진 씰 누유",
            "문짝 씰 들뜸",
            "실리콘 씰 코킹 작업",
        ]
        for phrase in weatherstrip_phrases:
            brand, model = extract_vehicle_info(phrase)
            self.assertNotEqual(
                (brand, model),
                (BRAND_BYD, "씰"),
                f"False positive BYD Seal match on weatherstrip phrase: '{phrase}'",
            )

        # Legitimate BYD Seal matches MUST match
        valid_byd_seal = [
            ("BYD 씰 신차 출고 후기", (BRAND_BYD, "씰")),
            ("비야디 씰 주행거리 테스트", (BRAND_BYD, "씰")),
            ("씰 EV 주행거리 및 전비 테스트", (BRAND_BYD, "씰")),
            ("씰 세단 승차감 어떤가요", (BRAND_BYD, "씰")),
            ("BYD Seal 사전계약 완료", (BRAND_BYD, "씰")),
            ("비야디의 신차 씰 전기차 시승기", (BRAND_BYD, "씰")),
            ("BYD 씰 도어 씰 불량으로 물 샘", (BRAND_BYD, "씰")),
            ("비야디 신차 씰 결함 터짐", (BRAND_BYD, "씰")),
            ("BYD의 씰 전기차 결함", (BRAND_BYD, "씰")),
        ]
        for phrase, expected in valid_byd_seal:
            actual = extract_vehicle_info(phrase)
            self.assertEqual(actual, expected, f"Failed on valid BYD Seal: '{phrase}'")

    def test_06_casing_typos_and_complex_sentences(self):
        """Stress-test casing variations, common spacing typos, and complex sentences."""
        test_cases = [
            # Casing
            ("bmw m3 결함", (BRAND_OTHER, "BMW M3")),
            ("BMW M3 결함", (BRAND_OTHER, "BMW M3")),
            ("bMw M3 결함", (BRAND_OTHER, "BMW M3")),
            ("teSLa moDeL 3 출고", (BRAND_TESLA, "Model 3")),
            ("TESLA MODEL Y 시승", (BRAND_TESLA, "Model Y")),
            ("byd SEAL 사전계약", (BRAND_BYD, "씰")),
            ("BYD seal 시승기", (BRAND_BYD, "씰")),
            ("iOnIq 5 단차", (BRAND_HYUNDAI, "아이오닉5")),
            ("Ev6 Gt 가속감", (BRAND_KIA, "EV6 GT")),
            ("atTO 3 충전", (BRAND_BYD, "Atto 3")),
            ("dOLpHiN 전비", (BRAND_BYD, "돌핀")),
            ("SeaLiOn 7 리뷰", (BRAND_BYD, "시라이언")),

            # Spacing & Typos
            ("아이오닉 5 N 시승", (BRAND_HYUNDAI, "아이오닉5 N")),
            ("아이오닉5N 결함", (BRAND_HYUNDAI, "아이오닉5 N")),
            ("아이오닉 5n", (BRAND_HYUNDAI, "아이오닉5 N")),
            ("ioniq 5 n", (BRAND_HYUNDAI, "아이오닉5 N")),
            ("아토3 출고", (BRAND_BYD, "Atto 3")),
            ("atto 3", (BRAND_BYD, "Atto 3")),
            ("atto3", (BRAND_BYD, "Atto 3")),
            ("캐스퍼ev 방전", (BRAND_HYUNDAI, "캐스퍼 일렉트릭")),
            ("코나ev 화재", (BRAND_HYUNDAI, "코나 EV")),
            ("포터ev 모터", (BRAND_HYUNDAI, "포터 EV")),
            ("봉고ev 인버터", (BRAND_KIA, "봉고 EV")),
            ("레이ev 배터리", (BRAND_KIA, "레이 EV")),
            ("폴스타2 단차", (BRAND_OTHER, "폴스타 2")),
            ("샤오미 su7 브레이크", (BRAND_OTHER, "샤오미 SU7")),
            ("su7 트랙 주행", (BRAND_OTHER, "샤오미 SU7")),
            ("루시드 에어 고장", (BRAND_OTHER, "Lucid Air")),
            ("리비안 r1t 서스펜션", (BRAND_OTHER, "Rivian")),
            ("타이칸 충전 불가", (BRAND_OTHER, "타이칸")),
            ("이 트론 전비", (BRAND_OTHER, "Audi e-tron")),
            ("사이버트럭 와이퍼", (BRAND_TESLA, "Cybertruck")),

            # Complex multi-model sentences
            ("아이오닉5 vs EV6 비교", (BRAND_HYUNDAI, "아이오닉5")),
            ("도어 씰 방수 고무에서 잡소리 나는데 이거 모델3 결함인가요?", (BRAND_TESLA, "Model 3")),
        ]
        for text, expected in test_cases:
            actual = extract_vehicle_info(text)
            self.assertEqual(actual, expected, f"Failed on: '{text}'")

    def test_07_verbal_suffix_lookahead_blindspot(self):
        """VULNERABILITY TEST: Verbal endings like '입니다', '했습니다' fail trailing lookahead.

        Root cause:
        r'(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)' in Model Y and BYD Seal
        rules requires either specific nominal particles or non-Hangul.
        Copulas and verbal endings (입니다, 했습니다) start with Hangul not in the particle set,
        causing legitimate owner statements to be discarded into ('Other', '전기차').
        """
        blindspot_cases = [
            ("MY 오너입니다", (BRAND_TESLA, "Model Y")),
            ("MY 차주입니다", (BRAND_TESLA, "Model Y")),
            ("MY 출고했습니다", (BRAND_TESLA, "Model Y")),
            ("씰 오너입니다", (BRAND_BYD, "씰")),
            ("씰 출고했습니다", (BRAND_BYD, "씰")),
            ("씰 시승했습니다", (BRAND_BYD, "씰")),
        ]
        for phrase, expected in blindspot_cases:
            actual = extract_vehicle_info(phrase)
            self.assertEqual(
                actual,
                expected,
                f"Expected correct match for '{phrase}'",
            )


class TestDefectFilterRobustness(unittest.TestCase):
    """Stress tests for defect filter: rhetorical defect complaints vs spam/inquiries."""

    def setUp(self):
        self.filter = ContextualDefectFilter()

    def test_01_rhetorical_question_defect_complaints(self):
        """Verify authentic defect complaints phrased as questions pass as defects."""
        rhetorical_complaints = [
            ("iccu_q", "내 차 출고 3일만에 고속도로에서 100km 달리다 갑자기 퍽 소리나고 멈췄는데 이거 ICCU 결함인가요?", "BATTERY_CHARGING"),
            ("trunk_water_q", "내 차 테슬라 모델Y 비 오는 날 트렁크 바닥에 물이 흥건하게 고이는데 원래 이런가요?", "BUILD_QUALITY"),
            ("battery_smoke_q", "내 차 급속충전 중 배터리 온도 급상승하고 연기 나는데 이거 배터리 화재 위험인가요?", "BATTERY_CHARGING"),
            ("steering_noise_q", "출고 3일차 내 차 핸들에서 뚝뚝 소리 나고 떨리는데 이거 불량 아닌가요?", "DRIVING_POWERTRAIN"),
            ("windshield_leak_q", "내 차 비 오는 날 달리는데 앞유리에 물 새는데 이거 단차 문제인가요?", "BUILD_QUALITY"),
            ("charging_pop_q", "내 차 완속 충전 꽂았더니 펑 소리 나면서 충전 중단 에러 뜨는데 충전기 문제인가요?", "BATTERY_CHARGING"),
            ("blackout_q", "내 차 주행 중에 화면 블랙아웃되고 네비 먹통 됐는데 다들 이런 증상 겪으셨나요?", "SOFTWARE_ELECTRONICS"),
            ("wind_noise_gap_q", "내 차 문짝 단차 심해서 풍절음 심한데 원래 이런가요?", "BUILD_QUALITY"),
        ]

        for pid, text, expected_cat in rhetorical_complaints:
            post = RawPost(
                platform="dcinside",
                post_id=pid,
                url=f"https://example.com/{pid}",
                title=text[:25],
                content=text,
                comments=[],
            )
            rec = self.filter.process_post(post)
            self.assertTrue(
                rec.is_authentic_defect,
                f"Rhetorical defect '{pid}' was incorrectly rejected: {rec.filter_reason}",
            )
            self.assertEqual(
                rec.defect_category,
                expected_cat,
                f"Defect '{pid}' category mismatch: got {rec.defect_category}, expected {expected_cat}",
            )
            self.assertLess(rec.sentiment_polarity, 0.0)
            self.assertGreater(rec.negativity_score, 0.5)

    def test_02_prospective_buyer_inquiries_and_spam_rejected(self):
        """Verify prospective buyer inquiries, advice requests, and spam are filtered out."""
        spam_and_inquiries = [
            ("buyer_1", "전기차 살까요 말까요? 모델Y 승차감 어떤가요? 궁금합니다."),
            ("buyer_2", "아이오닉5 vs EV6 고민중인데 어떤 차 살까요?"),
            ("buyer_3", "테슬라 모델3 하이랜드 승차감 어떤가요?"),
            ("buyer_4", "겨울철 전비 많이 떨어지나요? 구매 전 궁금합니다."),
            ("buyer_anchor_1", "내 차 살 때 테슬라랑 현대차 중에 뭐가 더 나을까요?"),
            ("buyer_anchor_2", "내 차로 EV6 살까 고민 중인데 충전 편한가요?"),
            ("stock_spam", "테슬라 주가 전망 어떤가요? 주식 살까요 말까요? 영업이익 궁금"),
            ("news_spam", "[속보] 현대차 아이오닉9 미국 공장 본격 양산 개시. 연합뉴스 기자."),
            ("flaming", "흉기충들 개슬람들 모여서 물고 빨고 난리났네 ㅋㅋㅋ"),
            ("sales_rep", "현대차 대리점 영맨 추천해주세요. 할인 조건 좋은 곳 있나요?"),
            ("subsidy_q", "전기차 보조금 얼마나 나오나요? 신청 방법 궁금합니다."),
            ("prospective_defect_q", "ICCU 고장 문제 진짜인가요? 살까 말까 고민중인데 무섭네요."),
            ("prospective_gap_q", "전기차 사려는데 단차 결함 심한가요?"),
            ("ad_spam", "중고차 최고가 매입! 테슬라 현대 전기차 삽니다. 010-1234-5678"),
            ("happy_delivery", "내 차 오늘 드디어 인도받았습니다! 출고 인증샷 올립니다. 너무 좋네요!"),
        ]

        for pid, text in spam_and_inquiries:
            post = RawPost(
                platform="dcinside",
                post_id=pid,
                url=f"https://example.com/{pid}",
                title=text[:25],
                content=text,
                comments=[],
            )
            rec = self.filter.process_post(post)
            self.assertFalse(
                rec.is_authentic_defect,
                f"Spam/Inquiry '{pid}' leaked as an authentic defect! Filter reason: {rec.filter_reason}",
            )


class TestJsonWriterHistoricalMerging(unittest.TestCase):
    """Stress tests historical report merging in utils/json_writer.py."""

    def test_01_in_batch_duplicate_ids_and_urls_exposure(self):
        """VULNERABILITY TEST: In-batch duplicate IDs are NOT deduplicated.

        Root cause: write_daily_reports lines 154-162 iterates through new_reports
        and adds nid/nurl to seen_ids/seen_urls, but DOES NOT check whether
        nid or nurl is ALREADY in seen_ids/seen_urls before appending nr!
        """
        with tempfile.TemporaryDirectory() as td:
            out_file = os.path.join(td, "test_dups.json")
            batch_with_duplicates = [
                {"id": "rep_dup", "url": "https://example.com/1", "title": "첫번째 결함"},
                {"id": "rep_dup", "url": "https://example.com/1_dup", "title": "중복 ID 결함"},
                {"id": "rep_unique", "url": "https://example.com/2", "title": "고유 결함"},
            ]

            write_daily_reports(batch_with_duplicates, output_path=out_file)
            result = read_daily_reports(out_file)

            # Check that duplicate IDs were deduplicated
            report_ids = [r["id"] for r in result["reports"]]
            self.assertEqual(len(report_ids), 2)
            self.assertEqual(len(set(report_ids)), 2)

    def test_02_merge_with_existing_file_deduplication(self):
        """Verify cross-batch merging and updating of existing reports."""
        with tempfile.TemporaryDirectory() as td:
            out_file = os.path.join(td, "daily_reports.json")

            initial_batch = [
                {"id": "id_1", "url": "https://example.com/1", "title": "결함 1", "negativity_score": 0.8},
                {"id": "id_2", "url": "https://example.com/2", "title": "결함 2", "negativity_score": 0.7},
            ]
            write_daily_reports(initial_batch, output_path=out_file, total_scraped=20)
            data1 = read_daily_reports(out_file)
            self.assertEqual(len(data1["reports"]), 2)
            self.assertEqual(data1["statistics"]["total_scraped"], 20)

            # Second batch: updates id_1, adds id_3
            second_batch = [
                {"id": "id_1", "url": "https://example.com/1", "title": "결함 1 업데이트", "negativity_score": 0.95},
                {"id": "id_3", "url": "https://example.com/3", "title": "신규 결함 3", "negativity_score": 0.85},
            ]
            write_daily_reports(second_batch, output_path=out_file, total_scraped=15, merge_existing=True)
            data2 = read_daily_reports(out_file)

            self.assertEqual(len(data2["reports"]), 3)
            self.assertEqual(data2["statistics"]["total_scraped"], 35)

            id1_entry = next(r for r in data2["reports"] if r["id"] == "id_1")
            self.assertEqual(id1_entry["title"], "결함 1 업데이트")
            self.assertEqual(id1_entry["negativity_score"], 0.95)

    def test_03_empty_lists_handling(self):
        """Verify behavior when empty lists are provided."""
        with tempfile.TemporaryDirectory() as td:
            out_file = os.path.join(td, "empty_test.json")

            # 1. Writing empty list to new file
            write_daily_reports([], output_path=out_file)
            data1 = read_daily_reports(out_file)
            self.assertEqual(len(data1["reports"]), 0)
            self.assertEqual(data1["statistics"]["total_scraped"], 0)
            self.assertEqual(data1["statistics"]["total_filtered_defects"], 0)
            self.assertEqual(data1["statistics"]["avg_negativity_score"], 0.0)

            # 2. Add some items
            items = [{"id": "id_1", "url": "https://example.com/1", "title": "결함 1"}]
            write_daily_reports(items, output_path=out_file, total_scraped=10)

            # 3. Merging empty list preserves existing data
            write_daily_reports([], output_path=out_file, total_scraped=0, merge_existing=True)
            data2 = read_daily_reports(out_file)
            self.assertEqual(len(data2["reports"]), 1)
            self.assertEqual(data2["statistics"]["total_scraped"], 10)

            # 4. Overwriting with merge_existing=False clears existing data
            write_daily_reports([], output_path=out_file, total_scraped=0, merge_existing=False)
            data3 = read_daily_reports(out_file)
            self.assertEqual(len(data3["reports"]), 0)

    def test_04_malformed_entries_crash_exposure(self):
        """VULNERABILITY TEST: Malformed dict entries trigger unhandled TypeError/ValueError crashes.

        Root cause:
        In utils/json_writer.py line 76:
            neg_score = float(record_dict.get("negativity_score", ...))
        and line 77:
            float(record_dict.get("severity_index", 0.0))
        When 'negativity_score' or 'severity_index' is None, float(None) raises TypeError.
        When non-numeric string like 'not_a_number' is passed, float(...) raises ValueError.
        """
        # Case A: negativity_score is None
        bad_entry_none = {"id": "bad_none", "negativity_score": None}
        payload_none = format_daily_report_payload([bad_entry_none])
        self.assertEqual(len(payload_none.reports), 1)

        # Case B: negativity_score is non-numeric string
        bad_entry_str = {"id": "bad_str", "negativity_score": "not_a_number"}
        payload_str = format_daily_report_payload([bad_entry_str])
        self.assertEqual(len(payload_str.reports), 1)

        # Case C: severity_index is None
        bad_entry_sev = {"id": "bad_sev", "severity_index": None}
        payload_sev = format_daily_report_payload([bad_entry_sev])
        self.assertEqual(len(payload_sev.reports), 1)

    def test_05_non_dict_elements_handling(self):
        """Verify that non-dict / non-ComplaintRecord items are safely skipped."""
        mixed_items = [
            None,
            "random string",
            12345,
            {"id": "valid_1", "url": "https://example.com/1", "title": "정상 결함"},
            [],
        ]
        payload = format_daily_report_payload(mixed_items)
        self.assertEqual(len(payload.reports), 1)
        self.assertEqual(payload.reports[0]["id"], "valid_1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
