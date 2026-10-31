"""
tests/test_backend_cycle23_remediation.py - Exhaustive boundary and adversarial
unit test suite locking in all Cycle 23 Backend Remediations, Vehicle Matcher patterns,
ComplaintRecord transformations, and Frontend Calculation Contracts.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (Cycle 23 Backend Remediation Specification)
- COLLABORATION.md

Classes & Coverage (24 tests across 4 test classes):
1. TestRawPostAndDSIBreakdownMappingProtocols (9 tests: 01-09)
   - test_01_raw_post_subscript_access_all_keys: Subscript access for all 8 attributes.
   - test_02_raw_post_missing_key_raises_keyerror: Missing key subscript access raises KeyError.
   - test_03_raw_post_contains_and_get_fallbacks: 'in' operator and get() with custom defaults.
   - test_04_raw_post_dict_conversion_and_iteration: dict(raw_post) and iter(raw_post) key preservation.
   - test_05_dsi_breakdown_subscript_access_and_bounds: Subscript access for all 5 pillars.
   - test_06_dsi_breakdown_missing_key_raises_keyerror: Missing pillar raises KeyError.
   - test_07_dsi_breakdown_dict_unpacking_and_iteration: **dsi unpacking and list(iter()).
   - test_08_daily_report_statistics_mapping_protocol: DailyReportStatistics mapping protocol.
   - test_09_daily_report_payload_mapping_protocol: DailyReportPayload mapping protocol.

2. TestExpandedVehicleMatcherCycle23 (6 tests: 10-15)
   - test_10_cadillac_lyriq_adversarial_patterns: All casing, spacing, and Korean particles for Cadillac Lyriq.
   - test_11_english_brand_names_adversarial_casing: All English brands under BRAND_OTHER with varied cases.
   - test_12_kia_ev2_particles_and_spelling: Kia EV2 with all Korean particles and casing.
   - test_13_byd_sealion_dual_spelling_and_particles: BYD 시라이언 / 씨라이언 (including 07 / 7).
   - test_14_volkswagen_id4_and_idbuzz_adversarial: Volkswagen ID.4, id4, ID.Buzz, ID 버즈.
   - test_15_non_vehicle_negative_adversarial_inputs: Non-vehicle text never false-triggers major EV brands.

3. TestComplaintRecordFromDictTransformations (5 tests: 16-20)
   - test_16_from_dict_model_brand_map_new_tokens: ev2, sealion, 시라이언, id.4, id4, id.buzz, lyriq, 리릭.
   - test_17_from_dict_brand_map_english_brands: audi, porsche, volvo, chevrolet, cadillac, volkswagen, bmw, polestar.
   - test_18_from_dict_alias_resolution_and_date_normalization: id/post_id, platform/source, date/created_at normalizations.
   - test_19_from_dict_malformed_types_and_defaults: None, {}, empty lists, non-string fallbacks.
   - test_20_from_dict_nested_dsi_breakdown_and_to_admin_report_dict: Nested DSI parsing and serialization roundtrip.

4. TestFrontendContractsBoundaryAndAdversarial (4 tests: 21-24)
   - test_21_depreciation_cap_10b_krw_and_bounds_in_both_sources: 10B KRW cap in both TS files via static & Node execution.
   - test_22_dsi_severity_level_exhaustive_node_boundary_matrix: Exhaustive Node evaluation of getDsiSeverityLevel.
   - test_23_pdi_checklist_heading_h2_id_and_print_classes: PDI checklist h2 id="pdi-cat-..." and print classes.
   - test_24_subsidy_tracker_nan_and_inf_guards: calculate_price_cap_ratio and calculate_net_subsidy bounds.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional
import unittest


def _find_repo_root() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent.parent.parent,
        Path.cwd(),
        Path.cwd().parent,
    ]
    for p in candidates:
        if (p / "ev-stealth-web").is_dir() and (p / "data").is_dir():
            return p
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _find_repo_root()
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
else:
    sys.path.remove(str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT))

if str(WEB_ROOT) not in sys.path:
    sys.path.append(str(WEB_ROOT))

from filters.vehicle_matcher import (
    extract_vehicle_info,
    BRAND_HYUNDAI,
    BRAND_KIA,
    BRAND_OTHER,
    BRAND_TESLA,
    BRAND_BYD,
)
from models.complaint import (
    ComplaintRecord,
    DailyReportPayload,
    DailyReportStatistics,
    DSIBreakdown,
    RawPost,
)
from tracker.subsidy_tracker import calculate_price_cap_ratio, calculate_net_subsidy


# ===========================================================================
# Class 1: TestRawPostAndDSIBreakdownMappingProtocols
# ===========================================================================
class TestRawPostAndDSIBreakdownMappingProtocols(unittest.TestCase):
    """Rigorous verification of RawPost, DSIBreakdown, and Report mapping protocols."""

    def setUp(self) -> None:
        self.post = RawPost(
            platform="bobaedream",
            post_id="bd_98765",
            url="https://www.bobaedream.co.kr/view?code=electric&No=98765",
            title="캐딜락 리릭 주행 질감 솔직 후기",
            content="핸들 조향감이 묵직하고 고속 안정성이 탁월합니다.",
            comments=["리릭 실물 깡패죠", "주행거리 얼마 나오나요?"],
            created_at="2026-10-31 15:30:00",
            author="미국차매니아",
        )
        self.dsi = DSIBreakdown(
            safety=8.8,
            functional=8.0,
            economic=6.5,
            social=5.0,
            convenience=4.5,
        )

    def test_01_raw_post_subscript_access_all_keys(self) -> None:
        """RawPost allows dict-like subscript access for all 8 standard fields."""
        self.assertEqual(self.post["platform"], "bobaedream")
        self.assertEqual(self.post["post_id"], "bd_98765")
        self.assertEqual(self.post["url"], "https://www.bobaedream.co.kr/view?code=electric&No=98765")
        self.assertEqual(self.post["title"], "캐딜락 리릭 주행 질감 솔직 후기")
        self.assertEqual(self.post["content"], "핸들 조향감이 묵직하고 고속 안정성이 탁월합니다.")
        self.assertEqual(len(self.post["comments"]), 2)
        self.assertEqual(self.post["created_at"], "2026-10-31 15:30:00")
        self.assertEqual(self.post["author"], "미국차매니아")

    def test_02_raw_post_missing_key_raises_keyerror(self) -> None:
        """Subscript access for non-existent field raises KeyError."""
        with self.assertRaises(KeyError):
            _ = self.post["non_existent_attribute"]

    def test_03_raw_post_contains_and_get_fallbacks(self) -> None:
        """'in' operator and get() fallback work identically to standard dict."""
        self.assertIn("title", self.post)
        self.assertIn("post_id", self.post)
        self.assertNotIn("battery_supplier", self.post)

        self.assertEqual(self.post.get("title"), "캐딜락 리릭 주행 질감 솔직 후기")
        self.assertIsNone(self.post.get("unknown_key"))
        self.assertEqual(self.post.get("unknown_key", "default_val"), "default_val")

    def test_04_raw_post_dict_conversion_and_iteration(self) -> None:
        """dict(raw_post) and iter(raw_post) preserve all keys and values."""
        d = dict(self.post)
        self.assertIsInstance(d, dict)
        self.assertEqual(len(d), 8)
        self.assertEqual(d["title"], self.post.title)
        self.assertEqual(
            list(self.post),
            ["platform", "post_id", "url", "title", "content", "comments", "created_at", "author"],
        )

    def test_05_dsi_breakdown_subscript_access_and_bounds(self) -> None:
        """DSIBreakdown supports subscript access for all 5 pillars with exact values."""
        self.assertEqual(self.dsi["safety"], 8.8)
        self.assertEqual(self.dsi["functional"], 8.0)
        self.assertEqual(self.dsi["economic"], 6.5)
        self.assertEqual(self.dsi["social"], 5.0)
        self.assertEqual(self.dsi["convenience"], 4.5)

    def test_06_dsi_breakdown_missing_key_raises_keyerror(self) -> None:
        """Non-existent pillar subscript raises KeyError."""
        with self.assertRaises(KeyError):
            _ = self.dsi["environmental"]

    def test_07_dsi_breakdown_dict_unpacking_and_iteration(self) -> None:
        """**dsi unpacking and list(iter(dsi)) yield all 5 pillar names."""
        unpacked = {**dict(self.dsi)}
        self.assertEqual(len(unpacked), 5)
        self.assertIn("safety", unpacked)
        self.assertEqual(list(self.dsi), ["safety", "functional", "economic", "social", "convenience"])

    def test_08_daily_report_statistics_mapping_protocol(self) -> None:
        """DailyReportStatistics supports subscripting, contains, get, and dict unpacking."""
        stats = DailyReportStatistics(
            total_scraped=350,
            total_filtered_defects=42,
            avg_negativity_score=0.89,
            critical_defect_count=7,
        )
        self.assertEqual(stats["total_scraped"], 350)
        self.assertEqual(stats.get("critical_defect_count"), 7)
        self.assertIn("avg_negativity_score", stats)
        d = dict(stats)
        self.assertEqual(d["total_filtered_defects"], 42)

    def test_09_daily_report_payload_mapping_protocol(self) -> None:
        """DailyReportPayload supports subscripting, get, and dict conversion."""
        payload = DailyReportPayload(
            generated_at="2026-10-31T09:00:00Z",
            pipeline_version="2.3.0",
        )
        self.assertEqual(payload["pipeline_version"], "2.3.0")
        self.assertEqual(payload.get("generated_at"), "2026-10-31T09:00:00Z")
        d = dict(payload)
        self.assertEqual(d["pipeline_version"], "2.3.0")


# ===========================================================================
# Class 2: TestExpandedVehicleMatcherCycle23
# ===========================================================================
class TestExpandedVehicleMatcherCycle23(unittest.TestCase):
    """Boundary and adversarial verification of vehicle brand and model matching."""

    def test_10_cadillac_lyriq_adversarial_patterns(self) -> None:
        """Cadillac Lyriq recognized across Korean/English variants, casing, and Korean postpositional particles."""
        adversarial_cases = [
            ("캐딜락 리릭 2026년형 승차감 후기", BRAND_OTHER, "Cadillac Lyriq"),
            ("cadillac lyriq 급속충전 테스트", BRAND_OTHER, "Cadillac Lyriq"),
            ("CADILLAC LYRIQ Sport AWD 출고", BRAND_OTHER, "Cadillac Lyriq"),
            ("리릭 핸들 단차 및 유격 문의", BRAND_OTHER, "Cadillac Lyriq"),
            ("리릭도 환경부 보조금 지급 대상인가요?", BRAND_OTHER, "Cadillac Lyriq"),
            ("리릭을 살까 말까 고민중", BRAND_OTHER, "Cadillac Lyriq"),
            ("리릭으로 패밀리카 결정했습니다", BRAND_OTHER, "Cadillac Lyriq"),
            ("리릭은 디자인이 정말 미래지향적이네요", BRAND_OTHER, "Cadillac Lyriq"),
            ("리릭이 도로에서 존재감 넘치네요", BRAND_OTHER, "Cadillac Lyriq"),
            ("리릭에 충전기 꽂아두고 퇴근", BRAND_OTHER, "Cadillac Lyriq"),
            ("리릭 승차감 및 주행 성능 후기", BRAND_OTHER, "Cadillac Lyriq"),
            ("리릭만 충전 속도가 느린 건가요", BRAND_OTHER, "Cadillac Lyriq"),
            ("캐딜락리릭 사전계약 가격표", BRAND_OTHER, "Cadillac Lyriq"),
        ]
        for text, exp_b, exp_m in adversarial_cases:
            b, m = extract_vehicle_info(text)
            self.assertEqual(b, exp_b, f"Brand mismatch for: '{text}' (got {b})")
            self.assertEqual(m, exp_m, f"Model mismatch for: '{text}' (got {m})")

    def test_11_english_brand_names_adversarial_casing(self) -> None:
        """Bare and contextual English brand names mapped to BRAND_OTHER regardless of case."""
        cases = [
            ("audi", BRAND_OTHER),
            ("AUDI", BRAND_OTHER),
            ("Audi", BRAND_OTHER),
            ("porsche", BRAND_OTHER),
            ("PORSCHE", BRAND_OTHER),
            ("Porsche", BRAND_OTHER),
            ("volvo", BRAND_OTHER),
            ("VOLVO", BRAND_OTHER),
            ("Volvo", BRAND_OTHER),
            ("chevrolet", BRAND_OTHER),
            ("CHEVROLET", BRAND_OTHER),
            ("chevy", BRAND_OTHER),
            ("cadillac", BRAND_OTHER),
            ("CADILLAC", BRAND_OTHER),
            ("Cadillac", BRAND_OTHER),
            ("bmw", BRAND_OTHER),
            ("BMW", BRAND_OTHER),
            ("mercedes", BRAND_OTHER),
            ("mercedes-benz", BRAND_OTHER),
            ("volkswagen", BRAND_OTHER),
            ("VOLKSWAGEN", BRAND_OTHER),
            ("vw", BRAND_OTHER),
            ("VW", BRAND_OTHER),
            ("polestar", BRAND_OTHER),
            ("POLESTAR", BRAND_OTHER),
            ("rivian", BRAND_OTHER),
            ("RIVIAN", BRAND_OTHER),
            ("lucid", BRAND_OTHER),
            ("LUCID", BRAND_OTHER),
            ("xiaomi", BRAND_OTHER),
            ("XIAOMI", BRAND_OTHER),
            ("audi 서비스센터 예약", BRAND_OTHER),
            ("porsche 충전 인프라", BRAND_OTHER),
            ("volvo 배터리 화재 보상", BRAND_OTHER),
            ("chevrolet 보증 기간 안내", BRAND_OTHER),
            ("cadillac 딜러사 문의", BRAND_OTHER),
        ]
        for text, exp_b in cases:
            b, _ = extract_vehicle_info(text)
            self.assertEqual(b, exp_b, f"Expected brand {exp_b} for text '{text}', got {b}")

    def test_12_kia_ev2_particles_and_spelling(self) -> None:
        """Kia EV2 recognized across casing and Korean particles."""
        cases = [
            ("기아 EV2는 언제 사전계약 받나요?", BRAND_KIA, "EV2"),
            ("EV2가 소형 전기차 시장 평정할 듯", BRAND_KIA, "EV2"),
            ("기아의 EV2로 결정했습니다", BRAND_KIA, "EV2"),
            ("ev2를 사야 할지 캐스퍼를 사야 할지 고민", BRAND_KIA, "EV2"),
            ("EV2도 V2L 지원하나요?", BRAND_KIA, "EV2"),
            ("EV2만 나오면 바로 계약금 넣습니다", BRAND_KIA, "EV2"),
            ("EV2의 실내 공간 크기", BRAND_KIA, "EV2"),
            ("기아 ev2 실물 스파이샷", BRAND_KIA, "EV2"),
        ]
        for text, exp_b, exp_m in cases:
            b, m = extract_vehicle_info(text)
            self.assertEqual(b, exp_b, f"Brand mismatch for: '{text}'")
            self.assertEqual(m, exp_m, f"Model mismatch for: '{text}'")

    def test_13_byd_sealion_dual_spelling_and_particles(self) -> None:
        """BYD Sealion recognized with both 시라이언 and 씨라이언 spellings and suffixes."""
        cases = [
            ("비야디 시라이언 7 주행 후기", BRAND_BYD, "시라이언"),
            ("BYD 씨라이언 07 가격 공개", BRAND_BYD, "시라이언"),
            ("씨라이언7도 보조금 전액 수령 가능한가요?", BRAND_BYD, "시라이언"),
            ("sealion 7 모터 출력", BRAND_BYD, "시라이언"),
            ("sealion07 실내 인테리어", BRAND_BYD, "시라이언"),
            ("씨라이언은 승차감이 어떤가요?", BRAND_BYD, "시라이언"),
            ("시라이언과 타사 차량 비교", BRAND_BYD, "시라이언"),
            ("sealion 배터리 스펙", BRAND_BYD, "시라이언"),
        ]
        for text, exp_b, exp_m in cases:
            b, m = extract_vehicle_info(text)
            self.assertEqual(b, exp_b, f"Brand mismatch for: '{text}'")
            self.assertEqual(m, exp_m, f"Model mismatch for: '{text}'")

    def test_14_volkswagen_id4_and_idbuzz_adversarial(self) -> None:
        """Volkswagen ID.4 and ID.Buzz recognized across spelling variants."""
        cases = [
            ("폭스바겐 ID.4 소프트웨어 업데이트", BRAND_OTHER, "Volkswagen ID.4"),
            ("id4 충전구 열림 버튼 불량", BRAND_OTHER, "Volkswagen ID.4"),
            ("ID.4 Pro 트림 출고 대기", BRAND_OTHER, "Volkswagen ID.4"),
            ("폭스바겐 id.4 겨울철 전비", BRAND_OTHER, "Volkswagen ID.4"),
            ("폭스바겐 ID 버즈 국내 출시 가격", BRAND_OTHER, "Volkswagen ID.Buzz"),
            ("id.buzz 롱휠베이스 사전예약", BRAND_OTHER, "Volkswagen ID.Buzz"),
            ("id 버즈 차박 공간", BRAND_OTHER, "Volkswagen ID.Buzz"),
            ("ID.Buzz 패밀리카로 최고", BRAND_OTHER, "Volkswagen ID.Buzz"),
        ]
        for text, exp_b, exp_m in cases:
            b, m = extract_vehicle_info(text)
            self.assertEqual(b, exp_b, f"Brand mismatch for: '{text}'")
            self.assertEqual(m, exp_m, f"Model mismatch for: '{text}'")

    def test_15_non_vehicle_negative_adversarial_inputs(self) -> None:
        """Noise text does not falsely trigger Hyundai, Kia, Tesla, or BYD."""
        noise_cases = [
            "오늘 서울 날씨 참 좋네요 산책이나 갈까요",
            "국내 주식 시장 코스피 3000포인트 돌파",
            "하이엔드 오디오 앰프 스피커 세팅 추천",
            "체스 토너먼트 결승전 관전 후기",
            "자전거 전용 도로 라이딩 코스 추천",
        ]
        for text in noise_cases:
            b, _ = extract_vehicle_info(text)
            self.assertNotIn(
                b,
                [BRAND_HYUNDAI, BRAND_KIA, BRAND_TESLA, BRAND_BYD],
                f"False positive vehicle detection for noise text: '{text}' -> {b}",
            )


# ===========================================================================
# Class 3: TestComplaintRecordFromDictTransformations
# ===========================================================================
class TestComplaintRecordFromDictTransformations(unittest.TestCase):
    """Detailed boundary and adversarial testing for ComplaintRecord.from_dict."""

    def test_16_from_dict_model_brand_map_new_tokens(self) -> None:
        """ComplaintRecord.from_dict recognizes new tokens in model_brand_map."""
        tokens = [
            ("ev2", "Kia"),
            ("ev2 gt", "Kia"),
            ("sealion", "BYD"),
            ("sealion 7", "BYD"),
            ("시라이언", "BYD"),
            ("시라이언 7", "BYD"),
            ("id.4", "Volkswagen"),
            ("id.4 pro", "Volkswagen"),
            ("id4", "Volkswagen"),
            ("id4 pro", "Volkswagen"),
            ("id.buzz", "Volkswagen"),
            ("id버즈", "Volkswagen"),
            ("lyriq", "Cadillac"),
            ("lyriq sport", "Cadillac"),
            ("리릭", "Cadillac"),
            ("리릭 스포츠", "Cadillac"),
        ]
        for token, exp_brand in tokens:
            rec = ComplaintRecord.from_dict({
                "id": f"rec_{token.replace(' ', '_').replace('.', '_')}",
                "target_vehicle": token,
                "title": f"{token} 결함 리포트",
            })
            self.assertEqual(
                rec.vehicle_brand,
                exp_brand,
                f"Target vehicle '{token}' resolved to brand '{rec.vehicle_brand}', expected '{exp_brand}'",
            )
            self.assertEqual(rec.vehicle_model, token)

    def test_17_from_dict_brand_map_english_brands(self) -> None:
        """ComplaintRecord.from_dict parses English brand names from target_vehicle."""
        brand_cases = [
            ("audi e-tron", "Audi", "e-tron"),
            ("porsche taycan", "Porsche", "taycan"),
            ("volvo ex30", "Volvo", "ex30"),
            ("chevrolet bolt", "Chevrolet", "bolt"),
            ("cadillac lyriq", "Cadillac", "lyriq"),
            ("volkswagen id.4", "Volkswagen", "id.4"),
            ("bmw i4", "BMW", "i4"),
            ("polestar 2", "Polestar", "2"),
        ]
        for target_veh, exp_b, exp_m in brand_cases:
            rec = ComplaintRecord.from_dict({
                "id": f"rec_{exp_b}_{exp_m}",
                "target_vehicle": target_veh,
                "title": f"{target_veh} 점검 리포트",
            })
            self.assertEqual(rec.vehicle_brand, exp_b)
            self.assertEqual(rec.vehicle_model, exp_m)

    def test_18_from_dict_alias_resolution_and_date_normalization(self) -> None:
        """Aliases (post_id/id, platform/source, date/created_at) and dates normalize properly."""
        data = {
            "post_id": "dc_custom_100",
            "platform": "dcinside",
            "post_url": "https://gall.dcinside.com/view/custom_100",
            "post_title": "리릭 충전 중 셧다운",
            "author": "리릭초보",
            "date": "20261031",
            "target_vehicle": "cadillac lyriq",
            "defect_category": "BATTERY_CHARGING",
            "summary": "급속 충전 중 정차",
            "raw_quote": "충전기 꽂고 10분 뒤 꺼짐",
        }
        rec = ComplaintRecord.from_dict(data)
        self.assertEqual(rec.id, "dc_custom_100")
        self.assertEqual(rec.source, "dcinside")
        self.assertEqual(rec.url, "https://gall.dcinside.com/view/custom_100")
        self.assertEqual(rec.title, "리릭 충전 중 셧다운")
        self.assertEqual(rec.created_at, "20261031")
        self.assertEqual(rec.date_str, "2026-10-31")
        self.assertEqual(rec.vehicle_brand, "Cadillac")
        self.assertEqual(rec.vehicle_model, "lyriq")

    def test_19_from_dict_malformed_types_and_defaults(self) -> None:
        """Handles None, {}, missing keys, and malformed types safely without crashing."""
        rec_none = ComplaintRecord.from_dict(None)
        self.assertEqual(rec_none.id, "")
        self.assertEqual(rec_none.source, "unknown")

        rec_empty = ComplaintRecord.from_dict({})
        self.assertEqual(rec_empty.id, "")
        self.assertEqual(rec_empty.source, "unknown")

        rec_types = ComplaintRecord.from_dict({
            "id": 12345,
            "title": 99999,
            "slang_terms_detected": None,
            "negativity_score": "0.85",
            "severity_index": "88.5",
        })
        self.assertEqual(rec_types.id, "12345")
        self.assertEqual(rec_types.title, "99999")
        self.assertEqual(rec_types.slang_terms_detected, [])
        self.assertEqual(rec_types.negativity_score, 0.85)
        self.assertEqual(rec_types.severity_index, 88.5)

    def test_20_from_dict_nested_dsi_breakdown_and_to_admin_report_dict(self) -> None:
        """Nested DSIBreakdown parses properly and round-trips via to_admin_report_dict."""
        data = {
            "id": "rec_dsi_01",
            "title": "리릭 완충 시 오류",
            "target_vehicle": "cadillac lyriq",
            "dsi_breakdown": {
                "safety": 9.5,
                "functional": 8.0,
                "economic": 7.5,
                "social": 6.0,
                "convenience": 5.0,
            },
        }
        rec = ComplaintRecord.from_dict(data)
        self.assertIsNotNone(rec.dsi_breakdown)
        self.assertEqual(rec.dsi_breakdown["safety"], 9.5)
        self.assertEqual(rec.dsi_breakdown["convenience"], 5.0)

        admin_dict = rec.to_admin_report_dict()
        self.assertIn("dsi_breakdown", admin_dict)
        self.assertEqual(admin_dict["dsi_breakdown"]["safety"], 9.5)
        self.assertEqual(admin_dict["target_vehicle"], "Cadillac lyriq")


# ===========================================================================
# Class 4: TestFrontendContractsBoundaryAndAdversarial
# ===========================================================================
class TestFrontendContractsBoundaryAndAdversarial(unittest.TestCase):
    """Detailed boundary and adversarial validation of Frontend Calculation Contracts."""

    def test_21_depreciation_cap_10b_krw_and_bounds_in_both_sources(self) -> None:
        """10 Billion KRW cap enforced in both depreciationCalculations.ts and getDepreciationData.ts."""
        cmd = [
            "node",
            "--no-warnings",
            "--experimental-strip-types",
            "-e",
            """
import { calculateDepreciation as c1 } from './ev-stealth-web/src/lib/depreciationCalculations.ts';
import { calculateDepreciation as c2 } from './ev-stealth-web/src/lib/getDepreciationData.ts';

const extremeHigh = 999_999_999_999;
const exactly10B = 10_000_000_000;
const over10B = 10_000_000_001;
const negativePrice = -50_000_000;

const r1_high = c1({ years: 1, customPurchasePriceKrw: extremeHigh });
const r2_high = c2({ years: 1, customPurchasePriceKrw: extremeHigh });

const r1_exact = c1({ years: 1, customPurchasePriceKrw: exactly10B });
const r2_exact = c2({ years: 1, customPurchasePriceKrw: exactly10B });

const r1_over = c1({ years: 1, customPurchasePriceKrw: over10B });
const r2_over = c2({ years: 1, customPurchasePriceKrw: over10B });

const r1_neg = c1({ years: 1, customPurchasePriceKrw: negativePrice });
const r2_neg = c2({ years: 1, customPurchasePriceKrw: negativePrice });

console.log(JSON.stringify({
  high: [r1_high.basePurchasePriceKrw, r2_high.basePurchasePriceKrw],
  exact: [r1_exact.basePurchasePriceKrw, r2_exact.basePurchasePriceKrw],
  over: [r1_over.basePurchasePriceKrw, r2_over.basePurchasePriceKrw],
  neg: [r1_neg.basePurchasePriceKrw > 0, r2_neg.basePurchasePriceKrw > 0]
}));
""",
        ]
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, check=True)
        res = json.loads(proc.stdout)

        self.assertEqual(res["high"], [10_000_000_000, 10_000_000_000])
        self.assertEqual(res["exact"], [10_000_000_000, 10_000_000_000])
        self.assertEqual(res["over"], [10_000_000_000, 10_000_000_000])
        self.assertEqual(res["neg"], [True, True])

    def test_22_dsi_severity_level_exhaustive_node_boundary_matrix(self) -> None:
        """Exhaustive boundary testing of getDsiSeverityLevel in both TS modules."""
        cmd = [
            "node",
            "--no-warnings",
            "--experimental-strip-types",
            "-e",
            """
import { getDsiSeverityLevel as f1 } from './ev-stealth-web/src/lib/reliabilityCalculations.ts';
import { getDsiSeverityLevel as f2 } from './ev-stealth-web/src/lib/getReliabilityData.ts';

const boundaryCases = [
  NaN,
  -100.0,
  -0.01,
  0,
  0.0,
  34.99,
  35.0,
  59.99,
  60.0,
  79.99,
  80.0,
  99.9,
  100.0,
  Infinity,
  -Infinity
];

console.log(JSON.stringify({
  f1: boundaryCases.map(f1),
  f2: boundaryCases.map(f2)
}));
""",
        ]
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True, check=True)
        res = json.loads(proc.stdout)

        f1_list = res["f1"]
        f2_list = res["f2"]
        self.assertEqual(len(f1_list), len(f2_list))

        expected_levels = [
            "LOW",       # NaN
            "LOW",       # -100.0
            "LOW",       # -0.01
            "LOW",       # 0
            "LOW",       # 0.0
            "LOW",       # 34.99
            "MODERATE",  # 35.0
            "MODERATE",  # 59.99
            "HIGH",      # 60.0
            "HIGH",      # 79.99
            "CRITICAL",  # 80.0
            "CRITICAL",  # 99.9
            "CRITICAL",  # 100.0
            "LOW",       # Infinity
            "LOW",       # -Infinity
        ]

        for i, exp in enumerate(expected_levels):
            self.assertEqual(f1_list[i]["level"], exp, f"f1 mismatch at index {i}")
            self.assertEqual(f2_list[i]["level"], exp, f"f2 mismatch at index {i}")
            self.assertTrue(len(f1_list[i]["label"]) > 0)
            self.assertTrue(len(f1_list[i]["colorClass"]) > 0)

    def test_23_pdi_checklist_heading_h2_id_and_print_classes(self) -> None:
        """PDI checklist heading h2 id='pdi-cat-...' and print classes present in PdiChecklistClient.tsx."""
        client_file = WEB_ROOT / "src" / "app" / "pdi-checklist" / "PdiChecklistClient.tsx"
        self.assertTrue(client_file.is_file(), f"Missing file: {client_file}")
        content = client_file.read_text(encoding="utf-8")

        # Heading id template literal check
        self.assertTrue(
            bool(re.search(r'<h2[^>]*id=\{`pdi-cat-\$\{category\}`\}', content)),
            "Missing dynamic id={`pdi-cat-${category}`} on category h2 headings",
        )

        # Print classes
        self.assertIn("print:bg-slate-100", content)
        self.assertIn("print:border-gray-300", content)
        self.assertIn("print:shadow-none", content)
        self.assertIn("print:break-inside-avoid", content)
        self.assertIn("print:hidden", content)
        self.assertIn("print:py-2", content)
        self.assertIn("print:hover:bg-transparent", content)
        self.assertIn("print:accent-blue-600", content)
        self.assertIn("print:text-black", content)

    def test_24_subsidy_tracker_nan_and_inf_guards(self) -> None:
        """calculate_price_cap_ratio and calculate_net_subsidy guard against float('nan') and float('inf')."""
        self.assertEqual(calculate_price_cap_ratio(float("nan")), 0.0)  # type: ignore
        self.assertEqual(calculate_price_cap_ratio(float("inf")), 0.0)  # type: ignore
        self.assertEqual(calculate_price_cap_ratio(-10_000_000), 0.0)

        res = calculate_net_subsidy(
            model_national=float("nan"),  # type: ignore
            max_national=float("inf"),  # type: ignore
            max_local=1500000,
            msrp=54000000,
        )
        self.assertIsInstance(res, dict)
        self.assertEqual(res["total_subsidy_krw"], 0)


if __name__ == "__main__":
    unittest.main()
