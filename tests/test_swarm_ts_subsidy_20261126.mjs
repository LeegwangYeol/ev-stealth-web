import assert from 'node:assert/strict';
import {
  DEFAULT_SUBSIDY_THRESHOLDS,
  getRegionByIdFromList,
  getModelByIdFromList,
  sortModels,
  compareModels,
  sortRegions,
  rankRegionsByDepletion,
  parseModelSubsidy,
  calculateNetSubsidyPure,
  calculateDepletionRate,
  calculateRemainingUnits,
  getDepletionBadgeStyle,
  getBadgeStyle,
} from '../src/lib/subsidyCalculations.ts';
import {
  normalizeSubsidyDataset,
  getCategoryDepletion,
} from '../src/lib/getSubsidyData.ts';

// 1. NET_PRICE_ASC / NET_PRICE_DESC and RANGE_ASC negative/-0 sorting
{
  const models = [
    {
      model_id: 'low-msrp-no-sub',
      name_ko: '모델A',
      manufacturer: 'A',
      battery_type: 'LFP',
      battery_capacity_kwh: 60,
      rated_range_km: 400,
      base_price_krw: 48_000_000,
      price_subsidy_ratio: 1.0,
      national_subsidy_krw: 0,
    },
    {
      model_id: 'mid-msrp-full-sub',
      name_ko: '모델B',
      manufacturer: 'B',
      battery_type: 'NCM',
      battery_capacity_kwh: 84,
      rated_range_km: 485,
      base_price_krw: 50_000_000,
      price_subsidy_ratio: 1.0,
      national_subsidy_krw: 6_500_000,
    },
  ];

  // By MSRP, model A (48M) < model B (50M)
  assert.deepEqual(
    sortModels(models, 'PRICE_ASC').map((m) => m.model_id),
    ['low-msrp-no-sub', 'mid-msrp-full-sub']
  );

  // By net price after national subsidy, model B (43.5M) < model A (48M)
  assert.deepEqual(
    sortModels(models, 'NET_PRICE_ASC').map((m) => m.model_id),
    ['mid-msrp-full-sub', 'low-msrp-no-sub']
  );
  assert.deepEqual(
    sortModels(models, 'NET_PRICE_DESC').map((m) => m.model_id),
    ['low-msrp-no-sub', 'mid-msrp-full-sub']
  );

  // Negative / -0 rated_range_km clamped to 0 in RANGE_ASC
  const rangeModels = [
    { ...models[0], model_id: 'm-neg', rated_range_km: -50 },
    { ...models[1], model_id: 'm-pos', rated_range_km: 100 },
    { ...models[0], model_id: 'm-neg-zero', rated_range_km: -0 },
  ];
  assert.equal(compareModels(rangeModels[0], rangeModels[2], 'RANGE_ASC'), -1);
  assert.deepEqual(
    sortModels(rangeModels, 'RANGE_DESC').map((m) => m.model_id),
    ['m-pos', 'm-neg', 'm-neg-zero']
  );
}

// 2. WeakMap lookup cache invalidation on in-place middle-element mutation
{
  const makeRegion = (id, name) => ({
    region_id: id,
    iso_code: id,
    name_ko: name,
    name_en: id,
    tier: 'province',
    overall_depletion_rate: 10,
    overall_status: 'HEALTHY',
    residency_requirement_days: 30,
    supplementary_budget_added: false,
    categories: {
      passenger: { announced_units: 100, applied_units: 10, delivered_units: 5, remaining_units: 90, depletion_rate: 10, delivery_rate: 5, status: 'HEALTHY' },
      commercial: { announced_units: 0, applied_units: 0, delivered_units: 0, remaining_units: 0, depletion_rate: 0, delivery_rate: 0, status: 'HEALTHY' },
      bus: { announced_units: 0, applied_units: 0, delivered_units: 0, remaining_units: 0, depletion_rate: 0, delivery_rate: 0, status: 'HEALTHY' },
    },
  });

  const regions = [
    makeRegion('KR-11', '서울특별시'),
    makeRegion('KR-26', '부산광역시'),
    makeRegion('KR-41', '경기도'),
  ];
  assert.equal(getRegionByIdFromList(regions, 'KR-26')?.name_ko, '부산광역시');

  // Mutate middle element while preserving length, first, and last
  regions[1] = makeRegion('KR-30', '대전광역시');
  assert.equal(getRegionByIdFromList(regions, 'KR-30')?.name_ko, '대전광역시');
  assert.equal(getRegionByIdFromList(regions, 'KR-26'), undefined);

  const models = [
    { model_id: 'm1', name_ko: '아이오닉 5' },
    { model_id: 'm2', name_ko: 'EV6' },
    { model_id: 'm3', name_ko: '코나' },
  ];
  assert.equal(getModelByIdFromList(models, 'm2')?.name_ko, 'EV6');
  models[1] = { model_id: 'm4', name_ko: '레이 EV' };
  assert.equal(getModelByIdFromList(models, 'm4')?.name_ko, '레이 EV');
  assert.equal(getModelByIdFromList(models, 'm2'), undefined);
}

// 3. Hangul NFD -> NFC normalization in dataset normalization & pure parsers
{
  const nfdRegionName = '서울특별시'.normalize('NFD');
  const nfdModelName = '현대 아이오닉 5'.normalize('NFD');
  const nfdSampleKey = '서울'.normalize('NFD');

  const normalized = normalizeSubsidyDataset({
    metadata: {
      data_sources: ['환경부'.normalize('NFD')],
    },
    regions: [
      {
        region_id: 'KR-11',
        name_ko: nfdRegionName,
        notes: '서울 공고'.normalize('NFD'),
        municipalities: [{ name_ko: '서울'.normalize('NFD'), announced_units: 100, applied_units: 50 }],
      },
    ],
    popular_models_matrix: [
      {
        model_id: 'ioniq-5-2026',
        name_ko: nfdModelName,
        manufacturer: '현대자동차'.normalize('NFD'),
        regional_subsidy_samples: {
          [nfdSampleKey]: { local_subsidy_krw: 1_500_000, total_subsidy_krw: 8_000_000, net_price_krw: 46_100_000 },
        },
      },
    ],
  });

  assert.equal(normalized.metadata.data_sources[0], '환경부');
  assert.equal(normalized.regions[0].name_ko, '서울특별시');
  assert.equal(normalized.regions[0].notes, '서울 공고');
  assert.equal(normalized.regions[0].municipalities[0].name_ko, '서울');
  assert.equal(normalized.popular_models_matrix[0].name_ko, '현대 아이오닉 5');
  assert.ok(Object.prototype.hasOwnProperty.call(normalized.popular_models_matrix[0].regional_subsidy_samples, '서울'));

  const parsedModel = parseModelSubsidy({ name_ko: nfdModelName });
  assert.equal(parsedModel.nameKo, '현대 아이오닉 5');

  const pureRes = calculateNetSubsidyPure(
    { name_ko: nfdModelName, base_price_krw: 50_000_000, national_subsidy_krw: 6_500_000 },
    { region_id: 'KR-11', name_ko: nfdRegionName }
  );
  assert.equal(pureRes.modelName, '현대 아이오닉 5');
  assert.equal(pureRes.regionName, '서울특별시');
}

// 4. Negative depletion_rate / remaining_units fallback vs Infinity and -0 in sorting/ranking
{
  const regions = [
    {
      region_id: 'R-NEG-RATE',
      name_ko: '음수비율',
      categories: {
        passenger: { announced_units: 100, applied_units: 80, depletion_rate: -10, remaining_units: -5 },
      },
    },
    {
      region_id: 'R-INF-RATE',
      name_ko: '무한비율',
      categories: {
        passenger: { announced_units: 100, applied_units: 100, depletion_rate: Infinity, remaining_units: 0 },
      },
    },
    {
      region_id: 'R-NEG-ZERO',
      name_ko: '음수제로',
      categories: {
        passenger: { announced_units: 100, applied_units: 0, depletion_rate: -0, remaining_units: -0 },
      },
    },
  ];

  const sorted = sortRegions(regions, 'DEPLETION_DESC', 'passenger');
  assert.deepEqual(
    sorted.map((r) => r.region_id),
    ['R-INF-RATE', 'R-NEG-RATE', 'R-NEG-ZERO']
  );

  const ranked = rankRegionsByDepletion(regions, 'passenger');
  assert.equal(ranked[0].regionId, 'R-INF-RATE');
  assert.equal(ranked[1].regionId, 'R-NEG-RATE');
  assert.equal(ranked[1].depletionRate, 80);
  assert.equal(ranked[1].remainingUnits, 20);
  assert.equal(ranked[2].regionId, 'R-NEG-ZERO');
  assert.ok(Object.is(ranked[2].depletionRate, 0));
  assert.ok(Object.is(ranked[2].remainingUnits, 0));

  assert.ok(Object.is(calculateDepletionRate(-0, -0), 0));
  assert.ok(Object.is(calculateRemainingUnits(-0, -0), 0));
  const dep = getCategoryDepletion(regions[2], 'passenger');
  assert.ok(Object.is(dep.depletionRate, 0));
  assert.ok(Object.is(dep.remainingUnits, 0));
}

// 5. Contrast badge class checks
{
  for (const sev of ['HEALTHY', 'CAUTION', 'WARNING', 'CRITICAL', 'DEPLETED']) {
    const cls = DEFAULT_SUBSIDY_THRESHOLDS[sev].badge_class;
    assert.ok(/\bbg-[a-z]+-950\b/.test(cls));
    assert.ok(/\btext-[a-z]+-(?:100|200)\b/.test(cls));
    assert.ok(getBadgeStyle(sev).includes(cls));
    assert.ok(/\bbg-[a-z]+-950\b/.test(getDepletionBadgeStyle(sev === 'DEPLETED' ? 100 : 50).badgeClass));
  }
}

console.log('ALL SWARM TS SUBSIDY 2026-11-26 REGRESSION TESTS PASSED!');
