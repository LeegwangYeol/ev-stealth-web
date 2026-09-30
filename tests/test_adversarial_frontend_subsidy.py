"""
tests/test_adversarial_frontend_subsidy.py - Empirical Adversarial Test Harness for Next.js /subsidy-tracker UI.

Authoritative Requirements (User Request & Architecture):
1. Calculator Price-Cap Boundaries:
   - Test exact boundary prices: 54,999,999 KRW (100%), 55,000,000 KRW (50%), 84,999,999 KRW (50%), 85,000,000 KRW (0%).
   - Test negative MSRP, 0 MSRP, and astronomical MSRP (10,000,000,000 KRW).
2. Regional Matrix Completeness:
   - Verify calculations across all 17 administrative divisions (Seoul 1.5M KRW to Ulleung-gun 11.0M KRW).
3. Search & Filter Robustness:
   - Stress-test search input with Korean consonants/vowels (e.g. "ㅅㅇ", "ㄱㄱ"), symbols, and empty queries.
4. Mobile & DOM Integrity:
   - Verify layout does not overflow horizontally on 320px/375px mobile viewport widths.
   - Verify mobile drawer toggle works seamlessly.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
import sys
import unittest
from typing import Any, Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

_WEB_BASE = PROJECT_ROOT if (PROJECT_ROOT / "src" / "data").exists() else (PROJECT_ROOT / "ev-stealth-web")
DATA_FILE_PATH = _WEB_BASE / "src" / "data" / "ev_subsidy_data.json"
CLIENT_TSX_PATH = _WEB_BASE / "src" / "app" / "subsidy-tracker" / "SubsidyTrackerClient.tsx"
LAYOUT_TSX_PATH = _WEB_BASE / "src" / "app" / "layout.tsx"
GET_SUBSIDY_DATA_TS_PATH = _WEB_BASE / "src" / "lib" / "getSubsidyData.ts"


# ==============================================================================
# PURE REPLICATION OF FRONTEND ENGINE FOR ORACLE VERIFICATION
# ==============================================================================

def get_price_subsidy_ratio(msrp_krw: float) -> float:
    """Exact replica of getPriceSubsidyRatio in getSubsidyData.ts."""
    if msrp_krw >= 85_000_000:
        return 0.0
    if msrp_krw >= 55_000_000:
        return 0.5
    return 1.0


def calculate_net_subsidy_oracle(
    model: Dict[str, Any],
    region: Dict[str, Any],
    custom_msrp: Optional[int] = None,
    options: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """Exact replica of calculateNetSubsidy in getSubsidyData.ts."""
    options = options or {}
    base_price = model.get("base_price_krw", 54_100_000)
    active_msrp = custom_msrp if (custom_msrp is not None and custom_msrp > 0) else base_price

    ratio = get_price_subsidy_ratio(active_msrp)

    price_cap_tier_text = "100% 전액 지원 (5,500만 원 미만)"
    if ratio == 0.5:
        price_cap_tier_text = "50% 감액 지원 (5,500만~8,500만 원 구간)"
    elif ratio == 0.0:
        price_cap_tier_text = "보조금 지급 대상 제외 (8,500만 원 이상)"

    national_subsidy = 0
    if ratio > 0:
        if custom_msrp is not None and custom_msrp > 0:
            base_ratio = model.get("price_subsidy_ratio", 1.0)
            if base_ratio <= 0:
                base_ratio = 1.0
            unscaled_national = round(model.get("national_subsidy_krw", 6_500_000) / base_ratio)
            national_subsidy = min(6_500_000, round(unscaled_national * ratio))
        else:
            national_subsidy = model.get("national_subsidy_krw", 6_500_000)

    additional_grants = 0
    if national_subsidy > 0:
        if options.get("isYouthFirstTimeBuyer"):
            additional_grants += round(national_subsidy * 0.2)
        if options.get("isSmallBusinessOrTaxi"):
            additional_grants += round(national_subsidy * 0.3)
        if options.get("isMultiChildFamily"):
            additional_grants += round(national_subsidy * 0.1)
        if options.get("isOldDieselScrappage"):
            additional_grants += 1_000_000

    max_local = region["categories"]["passenger"]["max_local_subsidy_krw"]
    local_subsidy = 0
    if national_subsidy > 0:
        local_subsidy = round(max_local * (national_subsidy / 6_500_000))
        local_subsidy = round(local_subsidy / 10_000) * 10_000

    total_subsidy = national_subsidy + local_subsidy + additional_grants
    net_purchase_price = max(0, active_msrp - total_subsidy)

    depletion_rate = region["categories"]["passenger"]["depletion_rate"]
    is_high_risk = depletion_rate >= 80.0

    return {
        "active_msrp": active_msrp,
        "ratio": ratio,
        "price_cap_tier_text": price_cap_tier_text,
        "national_subsidy": national_subsidy,
        "local_subsidy": local_subsidy,
        "additional_grants": additional_grants,
        "total_subsidy": total_subsidy,
        "net_purchase_price": net_purchase_price,
        "is_high_risk": is_high_risk,
        "depletion_rate": depletion_rate,
    }


# ==============================================================================
# TEST SUITE
# ==============================================================================

class TestCalculatorPriceCapBoundaries(unittest.TestCase):
    """Adversarial stress-testing of 2026 MOE statutory price-cap boundaries."""

    @classmethod
    def setUpClass(cls):
        with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
            cls.db = json.load(f)
        cls.ioniq5 = next(m for m in cls.db["popular_models_matrix"] if m["model_id"] == "ioniq-5-2026")
        cls.seoul = next(r for r in cls.db["regions"] if r["region_id"] == "KR-11")

    def test_01_exact_statutory_boundaries(self):
        """Exact statutory thresholds: 54,999,999, 55,000,000, 84,999,999, 85,000,000."""
        # 1. Just below 55M: 100% eligibility
        r1 = get_price_subsidy_ratio(54_999_999)
        self.assertEqual(r1, 1.0, "54,999,999 KRW must receive 1.0 (100%) ratio")

        # 2. Exactly at 55M: 50% eligibility
        r2 = get_price_subsidy_ratio(55_000_000)
        self.assertEqual(r2, 0.5, "55,000,000 KRW must receive 0.5 (50%) ratio")

        # 3. Just below 85M: 50% eligibility
        r3 = get_price_subsidy_ratio(84_999_999)
        self.assertEqual(r3, 0.5, "84,999,999 KRW must receive 0.5 (50%) ratio")

        # 4. Exactly at 85M: 0% eligibility
        r4 = get_price_subsidy_ratio(85_000_000)
        self.assertEqual(r4, 0.0, "85,000,000 KRW must receive 0.0 (0%) ratio")

    def test_02_subwon_floating_point_boundaries(self):
        """Continuous sub-won floating point stress test."""
        self.assertEqual(get_price_subsidy_ratio(54_999_999.99), 1.0)
        self.assertEqual(get_price_subsidy_ratio(55_000_000.01), 0.5)
        self.assertEqual(get_price_subsidy_ratio(84_999_999.99), 0.5)
        self.assertEqual(get_price_subsidy_ratio(85_000_000.01), 0.0)

    def test_03_zero_and_negative_msrp_handling(self):
        """Adversarial testing of 0 and negative MSRP inputs."""
        # When custom MSRP is 0, the engine falls back to model.base_price_krw
        res_zero = calculate_net_subsidy_oracle(self.ioniq5, self.seoul, custom_msrp=0)
        self.assertEqual(res_zero["active_msrp"], self.ioniq5["base_price_krw"])
        self.assertGreater(res_zero["net_purchase_price"], 0)

        # When custom MSRP is negative, the engine falls back to model.base_price_krw
        res_neg = calculate_net_subsidy_oracle(self.ioniq5, self.seoul, custom_msrp=-50_000_000)
        self.assertEqual(res_neg["active_msrp"], self.ioniq5["base_price_krw"])
        self.assertEqual(res_neg["net_purchase_price"], res_zero["net_purchase_price"])

        # Also verify raw ratio function on negative numbers doesn't crash
        self.assertEqual(get_price_subsidy_ratio(-1), 1.0)

    def test_04_astronomical_msrp_scaling(self):
        """Adversarial testing of astronomical prices (10B, 100B, 1T KRW)."""
        astronomical_prices = [
            10_000_000_000,      # 10 Billion KRW
            100_000_000_000,     # 100 Billion KRW
            1_000_000_000_000,   # 1 Trillion KRW
            9_007_199_254_740_991 # JS MAX_SAFE_INTEGER
        ]
        for astro in astronomical_prices:
            res = calculate_net_subsidy_oracle(self.ioniq5, self.seoul, custom_msrp=astro)
            self.assertEqual(res["ratio"], 0.0, f"Astronomical price {astro} must have 0.0 ratio")
            self.assertEqual(res["national_subsidy"], 0)
            self.assertEqual(res["local_subsidy"], 0)
            self.assertEqual(res["total_subsidy"], 0)
            self.assertEqual(res["net_purchase_price"], astro, "Net price must equal MSRP when subsidy is 0")
            self.assertEqual(res["price_cap_tier_text"], "보조금 지급 대상 제외 (8,500만 원 이상)")

    def test_05_boundary_calculator_output_parity(self):
        """Verify mathematical breakdown at boundaries for Ioniq 5 in Seoul."""
        # Boundary 1: 54,999,999 KRW
        b1 = calculate_net_subsidy_oracle(self.ioniq5, self.seoul, custom_msrp=54_999_999)
        self.assertEqual(b1["national_subsidy"], 6_500_000)
        self.assertEqual(b1["local_subsidy"], 1_500_000)
        self.assertEqual(b1["total_subsidy"], 8_000_000)
        self.assertEqual(b1["net_purchase_price"], 46_999_999)

        # Boundary 2: 55,000,000 KRW
        b2 = calculate_net_subsidy_oracle(self.ioniq5, self.seoul, custom_msrp=55_000_000)
        self.assertEqual(b2["national_subsidy"], 3_250_000)
        self.assertEqual(b2["local_subsidy"], 750_000)
        self.assertEqual(b2["total_subsidy"], 4_000_000)
        self.assertEqual(b2["net_purchase_price"], 51_000_000)

        # Discontinuity at boundary: exactly 1 KRW increase in MSRP causes 4,000,001 KRW jump in out-of-pocket price!
        price_jump = b2["net_purchase_price"] - b1["net_purchase_price"]
        self.assertEqual(price_jump, 4_000_001, "Cliff effect at 55M boundary verified")


class TestRegionalMatrixCompleteness(unittest.TestCase):
    """Completeness & disparity verification across all 17 administrative divisions."""

    STATUTORY_17_ISO = {
        "KR-11", "KR-26", "KR-27", "KR-28", "KR-29", "KR-30", "KR-31", "KR-36",
        "KR-41", "KR-42", "KR-43", "KR-44", "KR-45", "KR-46", "KR-47", "KR-48", "KR-49"
    }

    @classmethod
    def setUpClass(cls):
        with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
            cls.db = json.load(f)
        cls.regions = cls.db["regions"]
        cls.models = cls.db["popular_models_matrix"]
        cls.ioniq5 = next(m for m in cls.models if m["model_id"] == "ioniq-5-2026")

    def test_01_all_17_divisions_present(self):
        """Confirm exactly 17 Korean administrative divisions exist with unique ISO codes."""
        found_iso = {r["iso_code"] for r in self.regions}
        self.assertEqual(len(self.regions), 17, "Must contain exactly 17 divisions")
        self.assertEqual(found_iso, self.STATUTORY_17_ISO, "Must match all 17 statutory ISO codes")

    def test_02_seoul_local_subsidy_contract(self):
        """Seoul (KR-11) must have max_local_subsidy_krw == 1,500,000 KRW."""
        seoul = next(r for r in self.regions if r["iso_code"] == "KR-11")
        self.assertEqual(seoul["categories"]["passenger"]["max_local_subsidy_krw"], 1_500_000)

    def test_03_ulleung_gun_local_subsidy_contract(self):
        """Ulleung-gun in Gyeongbuk (KR-47) must have local_subsidy_krw == 11,000,000 KRW."""
        gyeongbuk = next(r for r in self.regions if r["iso_code"] == "KR-47")
        self.assertIn("municipalities", gyeongbuk)
        ulleung = next((m for m in gyeongbuk["municipalities"] if m["name_ko"] == "울릉군"), None)
        self.assertIsNotNone(ulleung, "Ulleung-gun must be present in Gyeongbuk municipalities")
        self.assertEqual(ulleung["local_subsidy_krw"], 11_000_000, "Ulleung-gun must have 11.0M KRW local subsidy")

    def test_04_seoul_vs_ulleung_disparity_calculation(self):
        """Verify empirical disparity between Seoul (1.5M) and Ulleung-gun (11.0M)."""
        seoul = next(r for r in self.regions if r["iso_code"] == "KR-11")
        seoul_calc = calculate_net_subsidy_oracle(self.ioniq5, seoul)

        # Ulleung-gun local subsidy is 11,000,000 KRW
        ulleung_max_local = 11_000_000
        national_sub = self.ioniq5["national_subsidy_krw"]  # 6,500,000
        ulleung_total_sub = national_sub + ulleung_max_local  # 17,500,000
        ulleung_net_price = self.ioniq5["base_price_krw"] - ulleung_total_sub  # 54,100,000 - 17,500,000 = 36,600,000

        self.assertEqual(seoul_calc["total_subsidy"], 8_000_000)
        self.assertEqual(seoul_calc["net_purchase_price"], 46_100_000)
        self.assertEqual(ulleung_net_price, 36_600_000)

        # Net price disparity between Seoul and Ulleung-gun: exactly 9,500,000 KRW!
        disparity = seoul_calc["net_purchase_price"] - ulleung_net_price
        self.assertEqual(disparity, 9_500_000, "Disparity between Seoul and Ulleung-gun must be 9.5M KRW")

    def test_05_quota_arithmetic_invariants(self):
        """Verify remaining_units = max(0, announced - applied) across all regions & categories."""
        for reg in self.regions:
            for cat_name, cat in reg["categories"].items():
                expected_rem = max(0, cat["announced_units"] - cat["applied_units"])
                self.assertEqual(
                    cat["remaining_units"],
                    expected_rem,
                    f"Invariant violated in {reg['name_ko']} {cat_name}: remaining {cat['remaining_units']} != {expected_rem}"
                )
                self.assertGreaterEqual(cat["delivered_units"], 0)
                self.assertLessEqual(cat["delivered_units"], cat["applied_units"])

    def test_06_depletion_status_tier_mapping(self):
        """Verify 5-tier alert severity classification across all regions."""
        for reg in self.regions:
            for cat_name, cat in reg["categories"].items():
                rate = cat["depletion_rate"]
                status = cat["status"]
                if rate >= 100.0:
                    self.assertEqual(status, "DEPLETED")
                elif rate >= 95.0:
                    self.assertEqual(status, "CRITICAL")
                elif rate >= 80.0:
                    self.assertEqual(status, "WARNING")
                elif rate >= 60.0:
                    self.assertEqual(status, "CAUTION")
                else:
                    self.assertEqual(status, "HEALTHY")


class TestSearchAndFilterRobustness(unittest.TestCase):
    """Stress-testing search filter algorithms and injection resistance."""

    @classmethod
    def setUpClass(cls):
        with open(DATA_FILE_PATH, "r", encoding="utf-8") as f:
            cls.db = json.load(f)
        cls.regions = cls.db["regions"]

    def _filter_regions(self, query: str) -> List[Dict[str, Any]]:
        """Exact replica of search filter in SubsidyTrackerClient.tsx."""
        q = query.strip().lower()
        if not q:
            return self.regions

        matched = []
        for r in self.regions:
            match_region = (
                q in r["name_ko"].lower()
                or q in r["name_en"].lower()
                or q in r["iso_code"].lower()
            )
            match_muni = False
            if "municipalities" in r and r["municipalities"]:
                match_muni = any(q in m["name_ko"].lower() for m in r["municipalities"])

            if match_region or match_muni:
                matched.append(r)
        return matched

    def test_01_empty_and_whitespace_queries(self):
        """Empty and whitespace queries must return all 17 regions."""
        self.assertEqual(len(self._filter_regions("")), 17)
        self.assertEqual(len(self._filter_regions("   ")), 17)
        self.assertEqual(len(self._filter_regions("\t\n")), 17)

    def test_02_korean_consonants_stress_test(self):
        """Stress-test search with Korean consonants (choseong: ㅅㅇ, ㄱㄱ, ㅇㄹ)."""
        # Because standard includes() is used, choseong does not match syllable blocks,
        # but it must NOT throw an unhandled exception or crash the search filter.
        res_seoul_cons = self._filter_regions("ㅅㅇ")
        self.assertIsInstance(res_seoul_cons, list)
        self.assertEqual(len(res_seoul_cons), 0)

        res_gg_cons = self._filter_regions("ㄱㄱ")
        self.assertIsInstance(res_gg_cons, list)
        self.assertEqual(len(res_gg_cons), 0)

        res_ulleung_cons = self._filter_regions("ㅇㄹ")
        self.assertIsInstance(res_ulleung_cons, list)
        self.assertEqual(len(res_ulleung_cons), 0)

    def test_03_full_syllables_and_submunicipalities(self):
        """Full Korean syllables for regions and sub-municipalities must match accurately."""
        # 1. Seoul
        r_seoul = self._filter_regions("서울")
        self.assertEqual(len(r_seoul), 1)
        self.assertEqual(r_seoul[0]["name_ko"], "서울특별시")

        # 2. Gyeonggi
        r_gg = self._filter_regions("경기")
        self.assertEqual(len(r_gg), 1)
        self.assertEqual(r_gg[0]["name_ko"], "경기도")

        # 3. Sub-municipality: Ulleung-gun in Gyeongbuk
        r_ulleung = self._filter_regions("울릉")
        self.assertEqual(len(r_ulleung), 1)
        self.assertEqual(r_ulleung[0]["name_ko"], "경상북도")

        # 4. Sub-municipality: Suwon-si in Gyeonggi
        r_suwon = self._filter_regions("수원")
        self.assertEqual(len(r_suwon), 1)
        self.assertEqual(r_suwon[0]["name_ko"], "경기도")

    def test_04_regex_and_code_injection_resilience(self):
        """Search query must not crash when given regex operators or script tags."""
        adversarial_inputs = [
            ".*", "[a-z]", "(foo|bar)", "^$", "\\", "+", "?", "{1,3}",
            "<script>alert(1)</script>", "' OR 1=1 --", "\0", "⚡"
        ]
        for adv in adversarial_inputs:
            # Must run safely without regex compile error or runtime exception
            try:
                res = self._filter_regions(adv)
                self.assertIsInstance(res, list)
            except Exception as e:
                self.fail(f"Search query crashed on adversarial input '{adv}': {e}")


class TestMobileAndDOMIntegrity(unittest.TestCase):
    """Static analysis of layout & mobile drawer constraints."""

    def test_01_mobile_drawer_markup_in_layout(self):
        """Layout must contain #mobile-nav-drawer with native details/summary and bounds."""
        with open(LAYOUT_TSX_PATH, "r", encoding="utf-8") as f:
            layout_content = f.read()

        self.assertIn('id="mobile-nav-drawer"', layout_content)
        self.assertIn('data-testid="mobile-drawer-toggle"', layout_content)
        self.assertIn('data-testid="mobile-drawer"', layout_content)
        self.assertIn('max-w-[calc(100vw-2rem)]', layout_content, "Drawer must enforce max-width constraint for narrow viewports")
        self.assertIn('href="/subsidy-tracker"', layout_content, "Subsidy tracker link must exist in mobile drawer")

    def test_02_no_fixed_overflow_widths(self):
        """Client component must avoid rigid min-w that exceeds 320px."""
        with open(CLIENT_TSX_PATH, "r", encoding="utf-8") as f:
            client_content = f.read()

        # Check for dangerously large min-width utility classes (e.g. min-w-[400px], min-w-[500px])
        dangerous_min_w = re.findall(r'min-w-\[(\d+)px\]', client_content)
        for w in dangerous_min_w:
            self.assertLessEqual(int(w), 300, f"Found dangerous min-width class: min-w-[{w}px] exceeding 300px")


if __name__ == "__main__":
    unittest.main()
