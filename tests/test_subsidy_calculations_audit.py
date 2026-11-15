"""
tests/test_subsidy_calculations_audit.py - Deep Audit & Regression Test Suite
for ev-stealth-web/src/lib/subsidyCalculations.ts and getSubsidyData.ts.

Audit Scope:
1. Division by zero in depletion rate calculations when totalQuota === 0 or appliedCount is invalid.
2. NaN or Infinity handling in sorting and ranking logic.
3. Edge cases in parsing subsidy numbers (만원 units, commas, missing properties).
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from typing import Any, Dict

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


def _eval_ts_node(script: str, timeout_sec: int = 30) -> Any:
    """Execute a Node.js snippet using tsx in WEB_ROOT."""
    if not shutil.which("node"):
        raise unittest.SkipTest("Node.js runtime not installed on host environment.")

    proc = subprocess.run(
        ["npx", "--no-install", "tsx", "-e", script],
        cwd=str(WEB_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"TSX execution failed (code {proc.returncode}):\n{proc.stderr}\nScript was:\n{script}")

    stdout = proc.stdout.strip()
    if not stdout:
        return None
    return json.loads(stdout)


class TestSubsidyDepletionZeroDivision(unittest.TestCase):
    """Verifies that calculateDepletionRate, calculateDeliveryRate, and calculateRemainingUnits

    never throw division-by-zero or return NaN/Infinity under zero or invalid inputs.
    """

    def test_01_depletion_rate_zero_and_invalid_quota(self) -> None:
        """calculateDepletionRate returns 0.0 when totalQuota is 0, negative, null, NaN, or Infinity."""
        script = """
        import { calculateDepletionRate, calculateDeliveryRate, calculateRemainingUnits } from './src/lib/subsidyCalculations';
        import { calculateDepletionRate as getDepRate } from './src/lib/getSubsidyData';

        console.log(JSON.stringify({
            quota_zero: calculateDepletionRate(100, 0),
            quota_negative: calculateDepletionRate(100, -50),
            quota_null: calculateDepletionRate(100, null),
            quota_undefined: calculateDepletionRate(100, undefined),
            quota_nan: calculateDepletionRate(100, NaN),
            quota_infinity: calculateDepletionRate(100, Infinity),
            re_exported_quota_zero: getDepRate(50, 0),
            delivery_zero: calculateDeliveryRate(50, 0),
            remaining_zero: calculateRemainingUnits(50, 0),
        }));
        """
        res = _eval_ts_node(script)
        self.assertEqual(res["quota_zero"], 0.0)
        self.assertEqual(res["quota_negative"], 0.0)
        self.assertEqual(res["quota_null"], 0.0)
        self.assertEqual(res["quota_undefined"], 0.0)
        self.assertEqual(res["quota_nan"], 0.0)
        self.assertEqual(res["quota_infinity"], 0.0)
        self.assertEqual(res["re_exported_quota_zero"], 0.0)
        self.assertEqual(res["delivery_zero"], 0.0)
        self.assertEqual(res["remaining_zero"], 0)

    def test_02_depletion_rate_invalid_applied_count(self) -> None:
        """calculateDepletionRate handles invalid appliedCount (null, undefined, negative, NaN, Infinity)."""
        script = """
        import { calculateDepletionRate } from './src/lib/subsidyCalculations';

        console.log(JSON.stringify({
            applied_null: calculateDepletionRate(null, 1000),
            applied_undefined: calculateDepletionRate(undefined, 1000),
            applied_negative: calculateDepletionRate(-100, 1000),
            applied_nan: calculateDepletionRate(NaN, 1000),
            applied_infinity: calculateDepletionRate(Infinity, 1000),
            valid_normal: calculateDepletionRate(894, 1000),
            valid_oversubscribed: calculateDepletionRate(1100, 1000),
            valid_clamped: calculateDepletionRate(1100, 1000, { clamp100: true }),
        }));
        """
        res = _eval_ts_node(script)
        self.assertEqual(res["applied_null"], 0.0)
        self.assertEqual(res["applied_undefined"], 0.0)
        self.assertEqual(res["applied_negative"], 0.0)
        self.assertEqual(res["applied_nan"], 0.0)
        self.assertEqual(res["applied_infinity"], 0.0)
        self.assertEqual(res["valid_normal"], 89.4)
        self.assertEqual(res["valid_oversubscribed"], 110.0)
        self.assertEqual(res["valid_clamped"], 100.0)

    def test_03_get_category_depletion_zero_announced(self) -> None:
        """getCategoryDepletion in getSubsidyData handles zero or missing announced units gracefully."""
        script = """
        import { getCategoryDepletion } from './src/lib/getSubsidyData';

        const zeroRegion = {
            region_id: 'KR-ZERO',
            iso_code: 'KR-99',
            name_ko: '제로지역',
            name_en: 'Zero Region',
            tier: 'province',
            overall_depletion_rate: 0,
            overall_status: 'HEALTHY',
            residency_requirement_days: 30,
            supplementary_budget_added: false,
            categories: {
                passenger: {
                    announced_units: 0,
                    applied_units: 10,
                    delivered_units: 5,
                    remaining_units: 0,
                    depletion_rate: 0,
                    delivery_rate: 0,
                    status: 'HEALTHY',
                },
                commercial: { announced_units: 0, applied_units: 0, delivered_units: 0, remaining_units: 0, depletion_rate: 0, delivery_rate: 0, status: 'HEALTHY' },
                bus: { announced_units: 0, applied_units: 0, delivered_units: 0, remaining_units: 0, depletion_rate: 0, delivery_rate: 0, status: 'HEALTHY' },
            },
            notes: 'Zero test'
        };

        const dep = getCategoryDepletion(zeroRegion, 'passenger');
        console.log(JSON.stringify(dep));
        """
        res = _eval_ts_node(script)
        self.assertEqual(res["announcedUnits"], 0)
        self.assertEqual(res["depletionRate"], 0.0)
        self.assertEqual(res["formattedAnnounced"], "0")
        self.assertEqual(res["remainingUnits"], 0)

    def test_04_calculate_subsidy_statistics_zero_dataset(self) -> None:
        """calculateSubsidyStatistics protects against zero budget and announced counts."""
        script = """
        import { calculateSubsidyStatistics } from './src/lib/subsidyCalculations';

        const emptyDataset = {
            nationwide_summary: {
                total_announced_units: 0,
                total_applied_units: 0,
                total_delivered_units: 0,
                total_remaining_units: 0,
                nationwide_depletion_rate: 0,
                total_budget_billion_krw: 0,
                disbursed_budget_billion_krw: 0,
            },
            regions: []
        };

        const stats = calculateSubsidyStatistics(emptyDataset);
        console.log(JSON.stringify({
            depletionRate: stats.nationalDepletionRate,
            deliveryRate: stats.deliveryRate,
            budgetExecutionRate: stats.budgetExecutionRatePct,
            criticalCount: stats.criticalRegionsCount
        }));
        """
        res = _eval_ts_node(script)
        self.assertEqual(res["depletionRate"], 0.0)
        self.assertEqual(res["deliveryRate"], 0.0)
        self.assertEqual(res["budgetExecutionRate"], 0.0)
        self.assertEqual(res["criticalCount"], 0)


class TestSubsidySortingAndRankingNaNInfinity(unittest.TestCase):
    """Verifies that sorting and ranking logic gracefully handles NaN, Infinity, and -Infinity."""

    def test_05_safe_compare_numbers_contract(self) -> None:
        """safeCompareNumbers guarantees deterministic ordering and NEVER produces NaN."""
        script = """
        import { safeCompareNumbers } from './src/lib/subsidyCalculations';

        console.log(JSON.stringify({
            normal_asc: safeCompareNumbers(10, 20, 'asc') < 0,
            normal_desc: safeCompareNumbers(10, 20, 'desc') > 0,
            equal: safeCompareNumbers(10, 10, 'asc') === 0,
            nan_first: safeCompareNumbers(NaN, 10, 'asc') > 0,
            nan_second: safeCompareNumbers(10, NaN, 'asc') < 0,
            nan_both: safeCompareNumbers(NaN, NaN, 'asc') === 0,
            inf_both: safeCompareNumbers(Infinity, Infinity, 'asc') === 0,
            inf_subtraction_safe: !Number.isNaN(safeCompareNumbers(Infinity, Infinity, 'desc')),
            inf_gt_finite: safeCompareNumbers(Infinity, 1000, 'desc') < 0,
            neginf_lt_finite: safeCompareNumbers(-Infinity, 1000, 'asc') < 0,
            null_handled: safeCompareNumbers(null, 50, 'asc') > 0,
            undefined_handled: safeCompareNumbers(undefined, 50, 'asc') > 0,
        }));
        """
        res = _eval_ts_node(script)
        for key, val in res.items():
            self.assertTrue(val, f"Condition failed: {key}")

    def test_06_sort_regions_with_nan_and_infinity_rates(self) -> None:
        """sortRegions does not crash, freeze, or return NaN when depletion_rate contains NaN or Infinity."""
        script = """
        import { sortRegions, rankRegionsByDepletion } from './src/lib/subsidyCalculations';

        const adversarialRegions = [
            {
                region_id: 'R-NAN',
                name_ko: 'NaN지역',
                categories: { passenger: { depletion_rate: NaN, remaining_units: 10, max_local_subsidy_krw: 1000000 } }
            },
            {
                region_id: 'R-INF',
                name_ko: '무한지역',
                categories: { passenger: { depletion_rate: Infinity, remaining_units: 0, max_local_subsidy_krw: 2000000 } }
            },
            {
                region_id: 'R-HIGH',
                name_ko: '높은지역',
                categories: { passenger: { depletion_rate: 98.5, remaining_units: 50, max_local_subsidy_krw: 1500000 } }
            },
            {
                region_id: 'R-LOW',
                name_ko: '낮은지역',
                categories: { passenger: { depletion_rate: 45.0, remaining_units: 500, max_local_subsidy_krw: 3000000 } }
            },
            {
                region_id: 'R-NULL',
                name_ko: '결측지역',
                categories: { passenger: null }
            }
        ];

        const sortedDesc = sortRegions(adversarialRegions, 'DEPLETION_DESC', 'passenger');
        const sortedIds = sortedDesc.map(r => r.region_id);
        const ranked = rankRegionsByDepletion(adversarialRegions, 'passenger');

        console.log(JSON.stringify({
            sortedIds,
            rank1: ranked[0].regionId,
            rank1Rate: ranked[0].depletionRate,
            rankCount: ranked.length
        }));
        """
        res = _eval_ts_node(script)
        self.assertEqual(res["rankCount"], 5)
        # Infinity is highest in descending order, followed by 98.5, 45.0, then NaN and null at the bottom
        self.assertEqual(res["sortedIds"][0], "R-INF")
        self.assertEqual(res["sortedIds"][1], "R-HIGH")
        self.assertEqual(res["sortedIds"][2], "R-LOW")
        self.assertIn(res["sortedIds"][3], ["R-NAN", "R-NULL"])
        self.assertIn(res["sortedIds"][4], ["R-NAN", "R-NULL"])

    def test_07_sort_models_with_invalid_attributes(self) -> None:
        """sortModels safely sorts vehicles even if base_price_krw or national_subsidy_krw is NaN/Infinity."""
        script = """
        import { sortModels } from './src/lib/subsidyCalculations';

        const dummyModels = [
            { model_id: 'M-INF', name_ko: '슈퍼카', base_price_krw: Infinity, national_subsidy_krw: 0, rated_range_km: 500 },
            { model_id: 'M-CHEAP', name_ko: '가성비차', base_price_krw: 30000000, national_subsidy_krw: 6500000, rated_range_km: 350 },
            { model_id: 'M-NAN', name_ko: '에러차', base_price_krw: NaN, national_subsidy_krw: NaN, rated_range_km: 0 },
            { model_id: 'M-MID', name_ko: '중형차', base_price_krw: 52000000, national_subsidy_krw: 5000000, rated_range_km: 450 },
        ];

        const sortedPriceAsc = sortModels(dummyModels, 'PRICE_ASC').map(m => m.model_id);
        const sortedSubsidyDesc = sortModels(dummyModels, 'SUBSIDY_DESC').map(m => m.model_id);

        console.log(JSON.stringify({ sortedPriceAsc, sortedSubsidyDesc }));
        """
        res = _eval_ts_node(script)
        # Price ASC: 30M, 52M, then Infinity / NaN
        self.assertEqual(res["sortedPriceAsc"][0], "M-CHEAP")
        self.assertEqual(res["sortedPriceAsc"][1], "M-MID")
        # Subsidy DESC: 6.5M, 5.0M, then 0 / NaN
        self.assertEqual(res["sortedSubsidyDesc"][0], "M-CHEAP")
        self.assertEqual(res["sortedSubsidyDesc"][1], "M-MID")


class TestSubsidyNumberParsingAndMissingProperties(unittest.TestCase):
    """Verifies parseSubsidyNumber, parseModelSubsidy, and parseCategoryMetrics handling

    of Korean denominations (만원, 억원), thousands commas, and missing properties.
    """

    def test_08_parse_manwon_units(self) -> None:
        """parseSubsidyNumber accurately converts '만원', '만 원', '만' strings to KRW."""
        script = """
        import { parseSubsidyNumber } from './src/lib/subsidyCalculations';

        console.log(JSON.stringify({
            p1: parseSubsidyNumber('650만원'),
            p2: parseSubsidyNumber('650만 원'),
            p3: parseSubsidyNumber('650만'),
            p4: parseSubsidyNumber('5,500만원'),
            p5: parseSubsidyNumber('5500.5만원'),
            p6: parseSubsidyNumber(' 150 만원 '),
        }));
        """
        res = _eval_ts_node(script)
        self.assertEqual(res["p1"], 6_500_000)
        self.assertEqual(res["p2"], 6_500_000)
        self.assertEqual(res["p3"], 6_500_000)
        self.assertEqual(res["p4"], 55_000_000)
        self.assertEqual(res["p5"], 55_005_000)
        self.assertEqual(res["p6"], 1_500_000)

    def test_09_parse_eok_and_compound_units(self) -> None:
        """parseSubsidyNumber parses '억', '억원', '천만원' and compound Korean values."""
        script = """
        import { parseSubsidyNumber } from './src/lib/subsidyCalculations';

        console.log(JSON.stringify({
            e1: parseSubsidyNumber('2.1억'),
            e2: parseSubsidyNumber('2.1억원'),
            e3: parseSubsidyNumber('1억 2000만원'),
            e4: parseSubsidyNumber('1억 5,000만 원'),
            e5: parseSubsidyNumber('5천만원'),
            e6: parseSubsidyNumber('5천원'),
        }));
        """
        res = _eval_ts_node(script)
        self.assertEqual(res["e1"], 210_000_000)
        self.assertEqual(res["e2"], 210_000_000)
        self.assertEqual(res["e3"], 120_000_000)
        self.assertEqual(res["e4"], 150_000_000)
        self.assertEqual(res["e5"], 50_000_000)
        self.assertEqual(res["e6"], 5_000)

    def test_10_parse_commas_and_currency_symbols(self) -> None:
        """parseSubsidyNumber strips commas, '원', 'KRW', '₩' seamlessly."""
        script = """
        import { parseSubsidyNumber } from './src/lib/subsidyCalculations';

        console.log(JSON.stringify({
            c1: parseSubsidyNumber('6,500,000'),
            c2: parseSubsidyNumber('6,500,000원'),
            c3: parseSubsidyNumber(' 6,500,000 KRW '),
            c4: parseSubsidyNumber('₩54,000,000'),
            c5: parseSubsidyNumber('54000000'),
            c6: parseSubsidyNumber(54000000),
        }));
        """
        res = _eval_ts_node(script)
        self.assertEqual(res["c1"], 6_500_000)
        self.assertEqual(res["c2"], 6_500_000)
        self.assertEqual(res["c3"], 6_500_000)
        self.assertEqual(res["c4"], 54_000_000)
        self.assertEqual(res["c5"], 54_000_000)
        self.assertEqual(res["c6"], 54_000_000)

    def test_11_parse_missing_properties_and_defaults(self) -> None:
        """parseModelSubsidy and parseCategoryMetrics fill defaults when properties are missing."""
        script = """
        import { parseModelSubsidy, parseCategoryMetrics, parseSubsidyNumber } from './src/lib/subsidyCalculations';

        const emptyModel = parseModelSubsidy({});
        const nullModel = parseModelSubsidy(null);
        const emptyCat = parseCategoryMetrics({});

        console.log(JSON.stringify({
            emptyModel_price: emptyModel.basePriceKrw,
            emptyModel_subsidy: emptyModel.nationalSubsidyKrw,
            emptyModel_ratio: emptyModel.priceSubsidyRatio,
            nullModel_price: nullModel.basePriceKrw,
            emptyCat_announced: emptyCat.announcedUnits,
            emptyCat_remaining: emptyCat.remainingUnits,
            emptyCat_rate: emptyCat.depletionRate,
            emptyCat_status: emptyCat.status,
            unparseable_string: parseSubsidyNumber('보조금 없음', { defaultKrw: 0 }),
            null_input: parseSubsidyNumber(null, { defaultKrw: 1234 }),
        }));
        """
        res = _eval_ts_node(script)
        self.assertEqual(res["emptyModel_price"], 54_100_000)
        self.assertEqual(res["emptyModel_subsidy"], 0)
        self.assertEqual(res["emptyModel_ratio"], 1.0)
        self.assertEqual(res["nullModel_price"], 54_100_000)
        self.assertEqual(res["emptyCat_announced"], 0)
        self.assertEqual(res["emptyCat_remaining"], 0)
        self.assertEqual(res["emptyCat_rate"], 0.0)
        self.assertEqual(res["emptyCat_status"], "HEALTHY")
        self.assertEqual(res["unparseable_string"], 0)
        self.assertEqual(res["null_input"], 1234)

    def test_12_lookup_functions_missing_property_resilience(self) -> None:
        """getRegionById and getModelById do not throw when array items lack region_id / model_id."""
        script = """
        import { getRegionByIdFromList, getModelByIdFromList } from './src/lib/subsidyCalculations';
        import { getRegionById, getModelById } from './src/lib/getSubsidyData';

        const malformedRegions = [
            null,
            {},
            { name_ko: 123 },
            { region_id: 'KR-11', name_ko: '서울특별시' }
        ];

        const malformedModels = [
            null,
            {},
            { name_ko: null },
            { model_id: 'ioniq-5-2026', name_ko: '현대 아이오닉 5' }
        ];

        const r1 = getRegionByIdFromList(malformedRegions, 'KR-11');
        const r2 = getRegionByIdFromList(malformedRegions, 'unknown');
        const m1 = getModelByIdFromList(malformedModels, 'ioniq-5-2026');
        const m2 = getModelByIdFromList(malformedModels, 'unknown');

        console.log(JSON.stringify({
            r1_found: r1?.region_id === 'KR-11',
            r2_none: r2 === undefined,
            m1_found: m1?.model_id === 'ioniq-5-2026',
            m2_none: m2 === undefined,
            liveRegion_found: Boolean(getRegionById('서울')),
            liveModel_found: Boolean(getModelById('ioniq-5-2026')),
        }));
        """
        res = _eval_ts_node(script)
        self.assertTrue(res["r1_found"])
        self.assertTrue(res["r2_none"])
        self.assertTrue(res["m1_found"])
        self.assertTrue(res["m2_none"])
        self.assertTrue(res["liveRegion_found"])
        self.assertTrue(res["liveModel_found"])

    def test_13_calculate_net_subsidy_with_string_manwon_msrp(self) -> None:
        """calculateNetSubsidy accepts custom MSRP formatted as '5500만원' or '55,000,000'."""
        script = """
        import { calculateNetSubsidy } from './src/lib/getSubsidyData';
        import { calculateNetSubsidyPure } from './src/lib/subsidyCalculations';

        const res1 = calculateNetSubsidy('ioniq-5-2026', 'KR-11', '5500만원');
        const res2 = calculateNetSubsidy('ioniq-5-2026', 'KR-11', '55,000,000원');

        console.log(JSON.stringify({
            msrp1: res1.msrpKrw,
            msrp2: res2.msrpKrw,
            ratio1: res1.priceSubsidyRatio,
            ratio2: res2.priceSubsidyRatio,
            same: res1.msrpKrw === res2.msrpKrw
        }));
        """
        res = _eval_ts_node(script)
        self.assertEqual(res["msrp1"], 55_000_000)
        self.assertEqual(res["msrp2"], 55_000_000)
        self.assertEqual(res["ratio1"], 1.0)
        self.assertEqual(res["ratio2"], 1.0)
        self.assertTrue(res["same"])

    def test_14_waitlist_and_pending_deliveries(self) -> None:
        """calculateWaitlistUnits, isDepletionOverExhausted, and calculatePendingDeliveries calculations."""
        script = """
        import {
            calculateWaitlistUnits,
            isDepletionOverExhausted,
            calculatePendingDeliveries,
        } from './src/lib/subsidyCalculations';

        console.log(JSON.stringify({
            // Waitlist calculations
            waitlist_normal: calculateWaitlistUnits(80, 100),
            waitlist_exact: calculateWaitlistUnits(100, 100),
            waitlist_over: calculateWaitlistUnits(125, 100),
            waitlist_zero_quota: calculateWaitlistUnits(50, 0),
            waitlist_null: calculateWaitlistUnits(null, 100),
            waitlist_nan: calculateWaitlistUnits(NaN, 100),

            // Over-exhaustion detection (> 100.0%)
            over_normal: isDepletionOverExhausted(89.4),
            over_exact: isDepletionOverExhausted(100.0),
            over_exceeded: isDepletionOverExhausted(100.1),
            over_null: isDepletionOverExhausted(null),
            over_nan: isDepletionOverExhausted(NaN),

            // Pending deliveries (applied - delivered)
            pending_normal: calculatePendingDeliveries(100, 70),
            pending_delivered_exceeds: calculatePendingDeliveries(50, 60),
            pending_null: calculatePendingDeliveries(null, 50),
            pending_zero: calculatePendingDeliveries(0, 0),
        }));
        """
        res = _eval_ts_node(script)
        self.assertEqual(res["waitlist_normal"], 0)
        self.assertEqual(res["waitlist_exact"], 0)
        self.assertEqual(res["waitlist_over"], 25)
        self.assertEqual(res["waitlist_zero_quota"], 0)
        self.assertEqual(res["waitlist_null"], 0)
        self.assertEqual(res["waitlist_nan"], 0)

        self.assertFalse(res["over_normal"])
        self.assertFalse(res["over_exact"])
        self.assertTrue(res["over_exceeded"])
        self.assertFalse(res["over_null"])
        self.assertFalse(res["over_nan"])

        self.assertEqual(res["pending_normal"], 30)
        self.assertEqual(res["pending_delivered_exceeds"], 0)
        self.assertEqual(res["pending_null"], 0)
        self.assertEqual(res["pending_zero"], 0)

    def test_15_velocity_and_exhaustion_predictions(self) -> None:
        """calculateDepletionVelocity, predictExhaustionDays, and predictExhaustionDate zero division & bounds."""
        script = """
        import {
            calculateDepletionVelocity,
            predictExhaustionDays,
            predictExhaustionDate,
        } from './src/lib/subsidyCalculations';

        console.log(JSON.stringify({
            // Velocity
            vel_normal: calculateDepletionVelocity(0, 300, 30),
            vel_zero_days: calculateDepletionVelocity(0, 300, 0),
            vel_neg_days: calculateDepletionVelocity(0, 300, -10),
            vel_null: calculateDepletionVelocity(null, 300, 30),
            vel_nan: calculateDepletionVelocity(NaN, 300, 30),
            vel_start_gt_end: calculateDepletionVelocity(500, 300, 30),

            // Exhaustion Days
            days_normal: predictExhaustionDays(100, 10),
            days_fractional: predictExhaustionDays(95, 10),
            days_zero_rem: predictExhaustionDays(0, 10),
            days_neg_rem: predictExhaustionDays(-20, 10),
            days_zero_vel: predictExhaustionDays(100, 0),
            days_neg_vel: predictExhaustionDays(100, -5),
            days_null: predictExhaustionDays(null, 10),

            // Exhaustion Date
            date_normal: predictExhaustionDate(100, 10, '2026-03-01'),
            date_zero_vel: predictExhaustionDate(100, 0, '2026-03-01'),
        }));
        """
        res = _eval_ts_node(script)
        self.assertEqual(res["vel_normal"], 10.0)
        self.assertEqual(res["vel_zero_days"], 0.0)
        self.assertEqual(res["vel_neg_days"], 0.0)
        self.assertEqual(res["vel_null"], 0.0)
        self.assertEqual(res["vel_nan"], 0.0)
        self.assertEqual(res["vel_start_gt_end"], 0.0)

        self.assertEqual(res["days_normal"], 10)
        self.assertEqual(res["days_fractional"], 10)
        self.assertEqual(res["days_zero_rem"], 0)
        self.assertEqual(res["days_neg_rem"], 0)
        self.assertIsNone(res["days_zero_vel"])
        self.assertIsNone(res["days_neg_vel"])
        self.assertIsNone(res["days_null"])

        self.assertEqual(res["date_normal"], "2026-03-11")
        self.assertIsNone(res["date_zero_vel"])

    def test_16_regional_grouping_classification(self) -> None:
        """classifyRegionGroup, isMetropolitanCity, isProvince, and groupRegionsByType."""
        script = """
        import {
            classifyRegionGroup,
            isMetropolitanCity,
            isProvince,
            groupRegionsByType,
        } from './src/lib/subsidyCalculations';

        const sampleRegions = [
            { region_id: 'KR-11', name_ko: '서울특별시', tier: 'special_city' },
            { region_id: 'KR-41', name_ko: '경기도', tier: 'province' },
            { region_id: 'KR-36', name_ko: '세종특별자치시', tier: 'special_self_governing_city' },
            { region_id: 'KR-49', name_ko: '제주특별자치도', tier: 'special_self_governing_province' },
        ];

        const grouped = groupRegionsByType(sampleRegions);

        console.log(JSON.stringify({
            seoul_grp: classifyRegionGroup('KR-11'),
            seoul_is_metro: isMetropolitanCity('서울'),
            seoul_is_prov: isProvince('서울'),
            gyeonggi_grp: classifyRegionGroup('KR-41'),
            gyeonggi_is_metro: isMetropolitanCity('경기'),
            gyeonggi_is_prov: isProvince('경기'),
            metro_count: grouped.metropolitan_cities.length,
            prov_count: grouped.provinces.length,
            null_grp: classifyRegionGroup(null),
        }));
        """
        res = _eval_ts_node(script)
        self.assertEqual(res["seoul_grp"], "metropolitan_cities")
        self.assertTrue(res["seoul_is_metro"])
        self.assertFalse(res["seoul_is_prov"])
        self.assertEqual(res["gyeonggi_grp"], "provinces")
        self.assertFalse(res["gyeonggi_is_metro"])
        self.assertTrue(res["gyeonggi_is_prov"])
        self.assertEqual(res["metro_count"], 2)
        self.assertEqual(res["prov_count"], 2)
        self.assertEqual(res["null_grp"], "other")

    def test_17_safe_compare_numbers_nan_vs_infinities(self) -> None:
        """safeCompareNumbers guarantees NaN is sorted to the end even when compared to Infinity/-Infinity."""
        script = """
        import { safeCompareNumbers } from './src/lib/subsidyCalculations';

        console.log(JSON.stringify({
            inf_vs_nan_asc: safeCompareNumbers(Infinity, NaN, 'asc') < 0,
            nan_vs_inf_asc: safeCompareNumbers(NaN, Infinity, 'asc') > 0,
            inf_vs_nan_desc: safeCompareNumbers(Infinity, NaN, 'desc') < 0,
            nan_vs_inf_desc: safeCompareNumbers(NaN, Infinity, 'desc') > 0,
            neginf_vs_nan_asc: safeCompareNumbers(-Infinity, NaN, 'asc') < 0,
            nan_vs_neginf_asc: safeCompareNumbers(NaN, -Infinity, 'asc') > 0,
        }));
        """
        res = _eval_ts_node(script)
        for key, val in res.items():
            self.assertTrue(val, f"Assertion failed: {key}")

    def test_18_bidirectional_model_sort_and_tie_breaking(self) -> None:
        """compareModels supports SUBSIDY_ASC, RANGE_ASC, NAME_DESC and handles ranking ties gracefully."""
        script = """
        import { sortModels, rankRegionsByDepletion } from './src/lib/subsidyCalculations';

        const models = [
            { model_id: 'M-A', name_ko: '가 모델', national_subsidy_krw: 6500000, rated_range_km: 500, base_price_krw: 50000000 },
            { model_id: 'M-B', name_ko: '나 모델', national_subsidy_krw: 3000000, rated_range_km: 300, base_price_krw: 40000000 },
        ];

        const sortedSubsidyAsc = sortModels(models, 'SUBSIDY_ASC').map(m => m.model_id);
        const sortedRangeAsc = sortModels(models, 'RANGE_ASC').map(m => m.model_id);
        const sortedNameDesc = sortModels(models, 'NAME_DESC').map(m => m.model_id);

        // Ties in ranking
        const tiedRegions = [
            { region_id: 'R-1', name_ko: '지역A', categories: { passenger: { depletion_rate: 85.0 } } },
            { region_id: 'R-2', name_ko: '지역B', categories: { passenger: { depletion_rate: 85.0 } } },
            { region_id: 'R-3', name_ko: '지역C', categories: { passenger: { depletion_rate: 70.0 } } },
        ];

        const ranked = rankRegionsByDepletion(tiedRegions, 'passenger');

        console.log(JSON.stringify({
            subAscFirst: sortedSubsidyAsc[0],
            rangeAscFirst: sortedRangeAsc[0],
            nameDescFirst: sortedNameDesc[0],
            rank1: ranked[0].rank,
            rank2: ranked[1].rank,
            rank3: ranked[2].rank,
        }));
        """
        res = _eval_ts_node(script)
        self.assertEqual(res["subAscFirst"], "M-B")
        self.assertEqual(res["rangeAscFirst"], "M-B")
        self.assertEqual(res["nameDescFirst"], "M-B")
        # Standard competition ranking: ties receive same rank, next rank skips
        self.assertEqual(res["rank1"], 1)
        self.assertEqual(res["rank2"], 1)
        self.assertEqual(res["rank3"], 3)


if __name__ == "__main__":
    unittest.main()
