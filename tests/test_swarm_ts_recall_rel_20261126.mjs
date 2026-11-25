import assert from 'node:assert/strict';
import * as recallCalc from '../src/lib/recallCalculations.ts';
import * as getRecall from '../src/lib/getRecallData.ts';
import * as relCalc from '../src/lib/reliabilityCalculations.ts';
import * as getRel from '../src/lib/getReliabilityData.ts';

// 1. parseRecallDate handles single-digit hours consistently across dot/slash/dash and English month formats
for (const mod of [recallCalc, getRecall]) {
  const d1 = mod.parseRecallDate('2024.03.18 9:15:30');
  const d2 = mod.parseRecallDate('2024/03/18 9:15:30');
  const d3 = mod.parseRecallDate('2024-03-18 9:15:30');
  const d4 = mod.parseRecallDate('Mar 18, 2024 9:15:30');
  const d5 = mod.parseRecallDate('18 Mar 2024 9:15:30');
  const d6 = mod.parseRecallDate('2024 Mar 18 9:15:30');

  for (const d of [d1, d2, d3, d4, d5, d6]) {
    assert.ok(d instanceof Date);
    assert.equal(d.toISOString(), '2024-03-18T09:15:30.000Z');
  }

  assert.equal(mod.parseRecallDate('2024.03.18 24:15:30'), null);
  assert.equal(mod.parseRecallDate('2024.02.30 9:15:30'), null);
  assert.equal(mod.parseRecallDate('Mar 18, 2024 25:15:30'), null);
}

// 2. 4-letter ASCII brand tokens ('Audi', 'Ford', 'MINI') must not falsely match substring collisions ('Saudi', 'Oxford', 'Gemini')
{
  const customRecallDb = {
    metadata: recallCalc.DEFAULT_RECALL_METADATA,
    vin_prefixes: [],
    battery_profiles: [
      {
        model_id: 'saudi-ev-1',
        brand: 'Saudi EV',
        model_name: 'Ceer Sedan',
        years: '2024 ~ 2026',
        cell_supplier: 'CATL',
        cell_chemistry: 'LFP',
        fire_incident_status: 'VERIFIED_SAFE',
        recommended_soc_limit: 100,
        underground_parking_advisory: '정상',
        bms_safety_features: 'BMS',
      },
      {
        model_id: 'audi-q4-etron',
        brand: 'Audi Korea',
        model_name: 'Q4 e-tron',
        years: '2023 ~ 2026',
        cell_supplier: 'LG에너지솔루션',
        cell_chemistry: 'NCM',
        fire_incident_status: 'VERIFIED_SAFE',
        recommended_soc_limit: 80,
        underground_parking_advisory: '정상',
        bms_safety_features: 'BMS',
      },
    ],
    recalls: [
      {
        id: 'RC-SAUDI-CEER',
        campaign_no: 'MOLIT-2025-0001',
        agency: 'MOLIT',
        agency_ko: '국토교통부',
        brand: 'Saudi EV',
        target_model: 'Ceer Sedan',
        target_model_years: '2024 ~ 2026',
        production_date_range: '2024.01.01 ~ 2025.01.01',
        affected_kdm_units: 10,
        defect_title: '테스트 결함',
        risk_level: 'SOFTWARE_REGULATION',
        risk_level_ko: '소프트웨어/규정',
        defect_detail: '테스트',
        remedy_type: 'OTA_WIRELESS',
        remedy_type_ko: '무선(OTA) 업데이트',
        remedy_action: '업데이트',
        consumer_emergency_guide: '없음',
        service_center_contact: '080-000-0000',
        official_link: 'https://www.car.go.kr',
        status: 'ACTIVE',
      },
    ],
  };

  for (const mod of [recallCalc, getRecall]) {
    const audiCheck = mod.checkRecallsByModel('Audi', 'Ceer Sedan', 2025, customRecallDb);
    assert.equal(audiCheck.valid, true);
    assert.equal(audiCheck.recalls.length, 0, 'Audi query must not match Saudi EV recall');
    assert.equal(audiCheck.batteryProfile, undefined, 'Audi query must not match Saudi EV battery profile');

    const audiModels = mod.getModelsForBrand('Audi', customRecallDb);
    assert.ok(audiModels.includes('Q4 e-tron'));
    assert.ok(!audiModels.includes('Ceer Sedan'), 'Audi must not include Saudi EV models');
  }

  const customRelDb = {
    metadata: { version: '1.0.0' },
    repair_cost_matrix: [],
    brands: [
      {
        id: 'saudi-ev',
        name_ko: '사우디 EV',
        name_en: 'Saudi EV',
        country: 'SA',
        overall_dsi: 40,
        total_reports: 10,
        critical_issue_rate: 0,
        category_distribution: {},
        models: [],
      },
      {
        id: 'audi-ev',
        name_ko: '아우디 코리아',
        name_en: 'Audi Korea',
        country: 'DE',
        overall_dsi: 45,
        total_reports: 20,
        critical_issue_rate: 5,
        category_distribution: {},
        models: [],
      },
    ],
  };

  assert.equal(relCalc.resolveBrandReliability('audi', customRelDb)?.id, 'audi-ev');
  assert.equal(relCalc.getBrandReliabilityById('audi', customRelDb)?.id, 'audi-ev');
  assert.equal(getRel.resolveBrandReliability('audi', customRelDb)?.id, 'audi-ev');
  assert.equal(getRel.getBrandReliabilityById('audi', customRelDb)?.id, 'audi-ev');
  assert.equal(
    relCalc.resolveBrandReliability('ford', {
      ...customRelDb,
      brands: [
        {
          id: 'oxford',
          name_ko: '옥스포드',
          name_en: 'Oxford Mobility',
          country: 'UK',
          overall_dsi: 30,
          total_reports: 5,
          critical_issue_rate: 0,
          category_distribution: {},
          models: [],
        },
      ],
    }),
    undefined
  );
}

// 3. Overflow-safe scaled percentages & moving averages for extreme 1e308 complaint counts
{
  const agg = relCalc.aggregateCategoryComplaintCounts([
    { category: 'BATTERY_CHARGING', count: 1e308 },
    { category: 'DRIVING_POWERTRAIN', count: 1e308 },
  ]);
  assert.equal(agg.BATTERY_CHARGING.percentage, 50);
  assert.equal(agg.DRIVING_POWERTRAIN.percentage, 50);

  const quarterly = relCalc.aggregateQuarterlyDefectBreakdown([
    { date: '2024-01-15', category: 'BATTERY_CHARGING', count: 1e308, dsiScore: 60 },
    { date: '2024-04-15', category: 'DRIVING_POWERTRAIN', count: 1e308, dsiScore: 40 },
    { date: '2024-07-15', category: 'SOFTWARE_ELECTRONICS', count: 1e308, dsiScore: 50 },
  ]);
  assert.equal(quarterly.length, 3);
  assert.equal(quarterly[0].percentage, 33.3);
  assert.equal(quarterly[1].percentage, 33.3);
  assert.equal(quarterly[2].percentage, 33.3);
  assert.equal(quarterly[2].movingAverage3Q, 1e308);

  const monthly = relCalc.aggregateMonthlyDefectBreakdown([
    { date: '2024-01-15', category: 'BATTERY_CHARGING', count: 1e308 },
    { date: '2024-02-15', category: 'DRIVING_POWERTRAIN', count: 1e308 },
  ]);
  assert.equal(monthly.length, 2);
  assert.equal(monthly[0].percentage, 50);
  assert.equal(monthly[1].percentage, 50);
  assert.equal(monthly[1].movingAverage3M, 1e308);
}

console.log('✅ All ts-lib-calc-recall 20261126 regression checks passed!');
