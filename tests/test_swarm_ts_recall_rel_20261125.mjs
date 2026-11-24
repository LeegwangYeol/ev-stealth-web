import assert from 'node:assert/strict';
import * as recallCalc from '../src/lib/recallCalculations.ts';
import * as getRecall from '../src/lib/getRecallData.ts';
import * as relCalc from '../src/lib/reliabilityCalculations.ts';
import * as getRel from '../src/lib/getReliabilityData.ts';

// 1. parseRecallDate preserves UTC HH:MM:SS on English month-name dates and rejects invalid time/rollover
for (const mod of [recallCalc, getRecall]) {
  const d1 = mod.parseRecallDate('Mar 18, 2024 09:15:30');
  const d2 = mod.parseRecallDate('18 Mar 2024 14:45:10');
  const d3 = mod.parseRecallDate('2024 Mar 18 23:59:59');
  assert.ok(d1 instanceof Date);
  assert.ok(d2 instanceof Date);
  assert.ok(d3 instanceof Date);
  assert.equal(d1.toISOString(), '2024-03-18T09:15:30.000Z');
  assert.equal(d2.toISOString(), '2024-03-18T14:45:10.000Z');
  assert.equal(d3.toISOString(), '2024-03-18T23:59:59.000Z');

  assert.equal(mod.parseRecallDate('Mar 18, 2024 24:00:00'), null);
  assert.equal(mod.parseRecallDate('18 Mar 2024 12:60:00'), null);
  assert.equal(mod.parseRecallDate('2024 Feb 30 10:00:00'), null);

  const sorted = mod.sortRecallsByDate(
    [
      { id: 'EARLY', recall_date: 'Mar 18, 2024 09:15:30' },
      { id: 'LATE', recall_date: 'Mar 18, 2024 14:45:10' },
    ],
    'desc'
  );
  assert.deepEqual(
    sorted.map((r) => r.id),
    ['LATE', 'EARLY']
  );
}

// 2. Short ASCII brand codes ('GM') must not falsely match 'KGM' in checkRecallsByModel or getModelsForBrand
{
  const customDb = {
    metadata: recallCalc.DEFAULT_RECALL_METADATA,
    vin_prefixes: [],
    battery_profiles: [
      {
        model_id: 'kgm-torres-evx',
        brand: 'KGM',
        model_name: '토레스 EVX',
        years: '2023 ~ 2025',
        cell_supplier: 'BYD',
        cell_chemistry: 'LFP',
        fire_incident_status: 'VERIFIED_SAFE',
        recommended_soc_limit: 100,
        underground_parking_advisory: '정상',
        bms_safety_features: 'BMS',
      },
      {
        model_id: 'gm-bolt-ev',
        brand: 'GM Korea',
        model_name: '볼트 EV',
        years: '2020 ~ 2023',
        cell_supplier: 'LG에너지솔루션',
        cell_chemistry: 'NCM',
        fire_incident_status: 'RECALLED_RESOLVED',
        recommended_soc_limit: 90,
        underground_parking_advisory: '리콜 완료',
        bms_safety_features: 'BMS',
      },
    ],
    recalls: [
      {
        id: 'RC-KGM-TORRES',
        campaign_no: 'MOLIT-2024-9999',
        agency: 'MOLIT',
        agency_ko: '국토교통부',
        brand: 'KGM',
        target_model: '토레스 EVX',
        target_model_years: '2023 ~ 2025',
        production_date_range: '2023.09.01 ~ 2024.06.01',
        affected_kdm_units: 100,
        defect_title: '테스트 결함',
        risk_level: 'SOFTWARE_REGULATION',
        risk_level_ko: '소프트웨어/규정',
        defect_detail: '테스트',
        remedy_type: 'SOFTWARE_UPDATE_SERVICE',
        remedy_type_ko: '센터 방문 SW',
        remedy_action: '업데이트',
        consumer_emergency_guide: '없음',
        service_center_contact: '080-000-0000',
        official_link: 'https://www.car.go.kr',
        status: 'ACTIVE',
      },
    ],
  };

  for (const mod of [recallCalc, getRecall]) {
    const gmCheck = mod.checkRecallsByModel('GM', '토레스 EVX', 2024, customDb);
    assert.equal(gmCheck.valid, true);
    assert.equal(gmCheck.recalls.length, 0, 'GM query must not match KGM recall');
    assert.equal(gmCheck.batteryProfile, undefined, 'GM query must not match KGM battery profile');

    const gmModels = mod.getModelsForBrand('GM', customDb);
    assert.ok(gmModels.includes('볼트 EV'), 'GM should still match GM Korea');
    assert.ok(!gmModels.includes('토레스 EVX'), 'GM must not include KGM models');

    const kgmModels = mod.getModelsForBrand('KGM', customDb);
    assert.ok(kgmModels.includes('토레스 EVX'));
    assert.ok(!kgmModels.includes('볼트 EV'));
  }
}

// 3. aggregateCategoryComplaintCounts must not leak non-category numeric fields when category_distribution/brands is null
{
  const nullDistBrand = {
    id: 'test-brand',
    name_ko: '테스트',
    name_en: 'Test',
    country: 'KR',
    overall_dsi: 75,
    total_reports: 120,
    critical_issue_rate: 15,
    category_distribution: null,
    models: [],
  };
  assert.deepEqual(relCalc.aggregateCategoryComplaintCounts(nullDistBrand), {});
  assert.deepEqual(getRel.aggregateCategoryComplaintCounts(nullDistBrand), {});

  const nullBrandsDb = {
    metadata: { version: '1.0.0', total_records_analyzed: 500, avg_industry_dsi: 60 },
    brands: null,
    repair_cost_matrix: [],
  };
  assert.deepEqual(relCalc.aggregateCategoryComplaintCounts(nullBrandsDb), {});
}

// 4. resolveBrandReliability & getBrandReliabilityById must not match 'gm' to 'KGM'
{
  const customTrends = {
    metadata: { version: '1.0.0' },
    repair_cost_matrix: [],
    brands: [
      {
        id: 'kg-mobility',
        name_ko: 'KG모빌리티',
        name_en: 'KGM',
        country: 'KR',
        overall_dsi: 40,
        total_reports: 10,
        critical_issue_rate: 5,
        category_distribution: {},
        models: [],
      },
      {
        id: 'gm-chevrolet',
        name_ko: 'GM 쉐보레',
        name_en: 'GM Chevrolet',
        country: 'US',
        overall_dsi: 55,
        total_reports: 20,
        critical_issue_rate: 10,
        category_distribution: {},
        models: [],
      },
    ],
  };

  assert.equal(relCalc.resolveBrandReliability('gm', customTrends)?.id, 'gm-chevrolet');
  assert.equal(relCalc.getBrandReliabilityById('gm', customTrends)?.id, 'gm-chevrolet');
  assert.equal(getRel.resolveBrandReliability('gm', customTrends)?.id, 'gm-chevrolet');
  assert.equal(getRel.getBrandReliabilityById('gm', customTrends)?.id, 'gm-chevrolet');
  assert.equal(relCalc.resolveBrandReliability('현대', {
    ...customTrends,
    brands: [
      {
        id: 'hyundai',
        name_ko: '현대자동차',
        name_en: 'Hyundai',
        country: 'KR',
        overall_dsi: 60,
        total_reports: 100,
        critical_issue_rate: 15,
        category_distribution: {},
        models: [],
      },
    ],
  })?.id, 'hyundai');
}

console.log('✅ All ts-lib-recall-rel regression checks passed!');
