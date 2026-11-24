import assert from 'node:assert/strict';
import {
  DEFAULT_SUBSIDY_THRESHOLDS,
  getRegionByIdFromList,
  getModelByIdFromList,
  parseSubsidyNumber,
  parseModelSubsidy,
  parseCategoryMetrics,
  calculateDepletionRate,
  compareRegions,
  compareModels,
  getDepletionBadgeStyle,
  classifyRegionGroup,
  predictExhaustionDate,
} from '../src/lib/subsidyCalculations.ts';
import {
  getRegionById,
  getModelById,
  calculateNetSubsidy,
  getCategoryDepletion,
} from '../src/lib/getSubsidyData.ts';

// 1. Unicode NFD vs NFC Hangul lookup, classification, and number parsing
{
  const seoulNfd = '서울'.normalize('NFD');
  const seoulFullNfd = '서울특별시'.normalize('NFD');
  const gyeonggiNfd = '경기도'.normalize('NFD');
  const modelNfd = '아이오닉 5'.normalize('NFD');
  const amountNfd = '1억 2,500만원'.normalize('NFD');

  const seoul = getRegionById(seoulNfd);
  assert.ok(seoul, 'getRegionById should resolve NFD Korean alias');
  assert.equal(seoul.region_id, 'KR-11');

  const seoulFull = getRegionById(seoulFullNfd);
  assert.ok(seoulFull, 'getRegionById should resolve NFD full Korean name');
  assert.equal(seoulFull.region_id, 'KR-11');

  const customList = [
    {
      region_id: 'custom-gg',
      iso_code: 'KR-99',
      name_ko: gyeonggiNfd,
      name_en: 'Gyeonggi',
      tier: 'province',
      overall_depletion_rate: 50,
      overall_status: 'HEALTHY',
      residency_requirement_days: 30,
      supplementary_budget_added: false,
      categories: {
        passenger: { announced_units: 100, applied_units: 50, delivered_units: 40, remaining_units: 50, depletion_rate: 50, delivery_rate: 40, status: 'HEALTHY' },
        commercial: { announced_units: 0, applied_units: 0, delivered_units: 0, remaining_units: 0, depletion_rate: 0, delivery_rate: 0, status: 'HEALTHY' },
        bus: { announced_units: 0, applied_units: 0, delivered_units: 0, remaining_units: 0, depletion_rate: 0, delivery_rate: 0, status: 'HEALTHY' },
      },
    },
  ];
  assert.equal(getRegionByIdFromList(customList, '경기')?.region_id, 'custom-gg');
  assert.equal(getRegionByIdFromList(customList, '경기'.normalize('NFD'))?.region_id, 'custom-gg');

  const model = getModelById(modelNfd);
  assert.ok(model, 'getModelById should resolve NFD Korean model query');
  assert.equal(model.model_id, 'ioniq-5-2026');

  const customModels = [
    {
      model_id: 'custom-ev',
      name_ko: '현대 아이오닉 5'.normalize('NFD'),
      manufacturer: '현대',
      battery_type: 'NCM',
      battery_capacity_kwh: 84,
      rated_range_km: 485,
      base_price_krw: 54_100_000,
      price_subsidy_ratio: 1.0,
      national_subsidy_krw: 6_500_000,
    },
  ];
  assert.equal(getModelByIdFromList(customModels, '아이오닉5')?.model_id, 'custom-ev');

  assert.equal(parseSubsidyNumber(amountNfd), 125_000_000);
  assert.equal(classifyRegionGroup(seoulNfd), 'metropolitan_cities');
  assert.equal(classifyRegionGroup(gyeonggiNfd), 'provinces');
}

// 2. Negative zero (-0) guard
{
  const parsedModel = parseModelSubsidy({ price_subsidy_ratio: -0 });
  assert.ok(Object.is(parsedModel.priceSubsidyRatio, 0), 'priceSubsidyRatio must not leak -0');

  const parsedCat = parseCategoryMetrics({
    announced_units: -0,
    applied_units: -0,
    delivered_units: -0,
    remaining_units: -0,
    depletion_rate: -0,
    delivery_rate: -0,
  });
  assert.ok(Object.is(parsedCat.announcedUnits, 0));
  assert.ok(Object.is(parsedCat.appliedUnits, 0));
  assert.ok(Object.is(parsedCat.remainingUnits, 0));
  assert.ok(Object.is(parsedCat.depletionRate, 0));
  assert.ok(Object.is(parsedCat.deliveryRate, 0));

  assert.ok(Object.is(calculateDepletionRate(-0, 100), 0));
  assert.ok(Object.is(parseSubsidyNumber(-0), 0));
}

// 3. Non-object truthy inputs in compareRegions and compareModels
{
  const seoul = getRegionById('KR-11');
  const ioniq = getModelById('ioniq-5-2026');
  assert.ok(seoul && ioniq);

  assert.equal(compareRegions('invalid', 'also-invalid'), 0);
  assert.equal(compareRegions('invalid', seoul), 1);
  assert.equal(compareRegions(seoul, []), -1);
  assert.equal(compareRegions('invalid', null), 0);

  assert.equal(compareModels('invalid', 123), 0);
  assert.equal(compareModels('invalid', ioniq), 1);
  assert.equal(compareModels(ioniq, []), -1);
  assert.equal(compareModels([], undefined), 0);
}

// 4. WCAG 2.1 AA/AAA opaque high-contrast badge classes
{
  const severities = ['HEALTHY', 'CAUTION', 'WARNING', 'CRITICAL', 'DEPLETED'];
  for (const sev of severities) {
    const cls = DEFAULT_SUBSIDY_THRESHOLDS[sev].badge_class;
    assert.ok(!cls.includes('/10'), `${sev} badge_class must use opaque surface instead of /10`);
    assert.ok(!cls.includes('text-emerald-400') && !cls.includes('text-amber-400'), `${sev} badge_class must use high-contrast text`);
    assert.ok(/\bbg-[a-z]+-950\b/.test(cls), `${sev} badge_class must use dark -950 opaque surface`);
  }

  for (const rate of [10, 65, 85, 96, 100, NaN, Infinity]) {
    const style = getDepletionBadgeStyle(rate);
    assert.ok(!style.badgeClass.includes('/10'), `getDepletionBadgeStyle(${rate}) must use opaque surface`);
    assert.ok(/\bbg-[a-z]+-950\b/.test(style.badgeClass), `getDepletionBadgeStyle(${rate}) must use -950 surface`);
  }
}

// 5. Additional edge-case sanity for date & data helpers
{
  assert.equal(predictExhaustionDate(5, 1, '2026-02-30'), null);
  assert.equal(predictExhaustionDate(1, 1, '2024-02-29'), '2024-03-01');
  const net = calculateNetSubsidy('ioniq-5-2026', 'KR-11', '6,000만원');
  assert.equal(net.priceSubsidyRatio, 0.5);
  assert.ok(Number.isFinite(net.netPurchasePriceKrw));
  const dep = getCategoryDepletion('KR-11', 'passenger');
  assert.ok(dep.announcedUnits >= 0 && Number.isFinite(dep.depletionRate));
}

console.log('ALL SWARM TS SUBSIDY REGRESSION TESTS PASSED!');
