import assert from 'node:assert/strict';
import * as depCalc from '../src/lib/depreciationCalculations.ts';
import * as depData from '../src/lib/getDepreciationData.ts';
import * as relCalc from '../src/lib/reliabilityCalculations.ts';
import * as getRel from '../src/lib/getReliabilityData.ts';

// 1. Depreciation Arrhenius, clamp, and overflow math parity across both engines
for (const mod of [depCalc, depData]) {
  // Clamp edge cases: NaN, +/-Infinity, -0, inverted bounds
  assert.equal(Object.is(mod.clamp(-0, -10, 10), 0), true);
  assert.equal(mod.clamp(Infinity, 5, 99), 99);
  assert.equal(mod.clamp(-Infinity, 5, 99), 5);
  assert.equal(mod.clamp(NaN, 5, 99), 5);
  assert.equal(mod.clamp(50, 99, 5), 50);
  assert.equal(mod.clamp(120, 99, 5), 99);

  // Arrhenius extreme chemistry parameters must stay finite and bounded
  const extremeBat = mod.simulateBatteryHealth(
    {
      chemistry: 'NCA',
      years: Infinity,
      totalKm: Infinity,
      ambientTempC: 85,
      storageSoc: 1.0,
      dcfcRatio: 1.0,
      packCapacityKwh: 10,
      vehicleEfficiencyKmPerKwh: 0.5,
    },
    {
      NCA: {
        calendar_arrhenius_ea_j_mol: 1e9,
        soc_stress_coefficient_beta: 1e6,
        calendar_baseline_annual_loss_pct: 100,
        calendar_time_exponent_z: 100,
        dcfc_acceleration_multiplier_max: 1e9,
        cyclic_exponent_w: 100,
        cycle_life_to_80_soh: 10,
      },
    }
  );
  assert.ok(Number.isFinite(extremeBat.sohPct));
  assert.equal(extremeBat.sohPct, 0);
  assert.equal(extremeBat.calendarLossPct, 100);
  assert.equal(extremeBat.cyclicLossPct, 100);
  assert.equal(extremeBat.totalLossPct, 100);
  assert.equal(extremeBat.grade, 'CRITICAL');

  // 0 years & 0 km with 0-exponent custom chemistry must still yield 100% SoH (no 0^0=1 leak)
  const zeroBat = mod.simulateBatteryHealth(
    { chemistry: 'LFP', years: 0, totalKm: 0 },
    { LFP: { calendar_time_exponent_z: 0, cyclic_exponent_w: 0 } }
  );
  assert.equal(zeroBat.sohPct, 100);
  assert.equal(zeroBat.calendarLossPct, 0);
  assert.equal(zeroBat.cyclicLossPct, 0);

  // Arrhenius temperature monotonicity (higher temp => >= calendar loss)
  const cold = mod.simulateBatteryHealth({ chemistry: 'NCM_811', years: 5, totalKm: 50000, ambientTempC: -20 });
  const warm = mod.simulateBatteryHealth({ chemistry: 'NCM_811', years: 5, totalKm: 50000, ambientTempC: 45 });
  assert.ok(warm.calendarLossPct > cold.calendarLossPct);

  // Depreciation & TCO extreme inputs remain finite and bounded
  const depOverflow = mod.calculateDepreciation({
    years: Infinity,
    mileageKm: Infinity,
    customPurchasePriceKrw: 1e15,
  });
  assert.equal(depOverflow.years, 100);
  assert.equal(depOverflow.mileageKm, 10_000_000);
  assert.equal(depOverflow.basePurchasePriceKrw, 10_000_000_000);
  assert.equal(depOverflow.adjustedResidualPct, 5.0);
  assert.ok(Number.isFinite(depOverflow.estimatedResidualPriceKrw));
  assert.ok(Number.isFinite(depOverflow.depreciationAmountKrw));

  const tcoOverflow = mod.calculateTcoComparison(Infinity, Infinity, 0.01, 0.5, 1e9, {
    fuel_tariffs: { ev_slow_charging_krw_per_kwh: 1e20, ice_gasoline_krw_per_liter: 1e20 },
    tax_parameters: {
      education_tax_multiplier: 1e10,
      ice_displacement_tiers: [{ max_cc: null, rate_per_cc_krw: 1e20, name: 'extreme' }],
    },
  });
  assert.ok(Number.isFinite(tcoOverflow.totalCumulativeSavingsKrw));
  assert.equal(tcoOverflow.years, 30);
}

// 2. Reliability chronic symptom normalization (case & whitespace) and verdict/grade sanitization
{
  assert.equal(relCalc.sanitizeVerdict(' buy_safe '), 'BUY_SAFE');
  assert.equal(relCalc.sanitizeVerdict('avoid'), 'AVOID');
  assert.equal(relCalc.sanitizeVerdict('unknown'), 'CAUTION');
  assert.equal(relCalc.sanitizeGrade(' a+ '), 'A+');
  assert.equal(relCalc.sanitizeGrade('b'), 'B');
  assert.equal(relCalc.sanitizeGrade('Z'), 'C');

  const traj = relCalc.calculateModelYearDefectTrajectory([
    {
      year: 2021,
      verdict: 'avoid',
      dsi_score: 80,
      incident_rate: 30,
      primary_defect: 'ICCU',
      estimated_repair_cost: '500만',
      chronic_symptoms: ['ICCU   Failure', '12V 방전', ' 12v  방전 '],
      raw_quote: '',
    },
    {
      year: 2022,
      verdict: ' buy_safe ',
      dsi_score: 30,
      incident_rate: 10,
      primary_defect: 'None',
      estimated_repair_cost: '100만',
      chronic_symptoms: [' iccu failure '],
      raw_quote: '',
    },
  ]);

  assert.deepEqual(traj.chronicCategories, ['ICCU Failure']);
  assert.equal(traj.yearOverYearProgression[0].verdict, 'AVOID');
  assert.equal(traj.yearOverYearProgression[1].verdict, 'BUY_SAFE');
}

// 3. Prototype-key safety across reliability aggregation, lookup, and enrichment
{
  const maliciousRecord = JSON.parse(
    '{"__proto__": {"polluted": true, "count": 999}, "constructor": {"count": 500}, "prototype": 300, "BATTERY_CHARGING": {"count": 10}}'
  );
  const agg = relCalc.aggregateCategoryComplaintCounts(maliciousRecord);
  assert.deepEqual(Object.keys(agg), ['BATTERY_CHARGING']);
  assert.equal(agg.BATTERY_CHARGING.count, 10);
  assert.equal(({}).polluted, undefined);

  const maliciousDb = JSON.parse(`{
    "metadata": { "version": "1.0.0" },
    "repair_cost_matrix": [],
    "brands": [{
      "id": "hyundai",
      "name_ko": "현대자동차",
      "name_en": "Hyundai",
      "country": "KR",
      "overall_dsi": 55,
      "total_reports": 10,
      "critical_issue_rate": 5,
      "category_distribution": {},
      "models": [{
        "__proto__": { "polluted": true },
        "constructor": "bad",
        "id": "ioniq5",
        "name": "아이오닉 5",
        "segment": "CUV",
        "brand_id": "   ",
        "overall_grade": " b ",
        "avg_dsi": 55,
        "top_category": "battery_charging",
        "year_evaluations": [{
          "__proto__": { "polluted": true },
          "year": 2023,
          "verdict": " buy_safe ",
          "dsi_score": 40,
          "incident_rate": 10,
          "primary_defect": "None",
          "estimated_repair_cost": "100만",
          "chronic_symptoms": ["ICCU"],
          "raw_quote": ""
        }]
      }]
    }]
  }`);

  const enriched = relCalc.getAllEnrichedModels(maliciousDb);
  assert.equal(enriched.length, 1);
  assert.equal(enriched[0].brand_id, 'hyundai');
  assert.equal(enriched[0].overall_grade, 'B');
  assert.equal(enriched[0].year_evaluations[0].verdict, 'BUY_SAFE');
  assert.equal(Object.prototype.hasOwnProperty.call(enriched[0], '__proto__'), false);
  assert.equal(Object.prototype.hasOwnProperty.call(enriched[0], 'constructor'), false);
  assert.equal(Object.prototype.hasOwnProperty.call(enriched[0].year_evaluations[0], '__proto__'), false);

  assert.equal(relCalc.resolveBrandReliability('__proto__', maliciousDb), undefined);
  assert.equal(relCalc.resolveBrandReliability('constructor', maliciousDb), undefined);
  assert.equal(relCalc.getBrandReliabilityById('__proto__', maliciousDb), undefined);
  assert.equal(relCalc.getBrandReliabilityById('toString', maliciousDb), undefined);

  const periodicProto = relCalc.aggregateQuarterlyDefectBreakdown([
    { date: '2024-01-15', category: '__proto__', count: 5 },
    { date: '2024-02-15', category: 'constructor', count: 3 },
  ]);
  assert.equal(periodicProto[0].topCategory, 'UNKNOWN');
  assert.equal(periodicProto[0].categoryDistribution.UNKNOWN.count, 8);
}

// 4. Date edge cases in periodic breakdowns (Korean trailing-dot year-month, +HH offsets, invalid rollover)
{
  const monthly = relCalc.aggregateMonthlyDefectBreakdown([
    { date: '2024. 3.', category: 'BATTERY_CHARGING', count: 4 },
    { date: '2024.03.', category: 'BATTERY_CHARGING', count: 6 },
    { date: '2024. 4', category: 'DRIVING_POWERTRAIN', count: 5 },
    { date: '2024-01-01T00:30:00+09', category: 'COLD_WEATHER', count: 7 },
    { date: '2023-02-29', category: 'BUILD_QUALITY', count: 99 },
    { date: '2024-02-30', category: 'BUILD_QUALITY', count: 99 },
    { date: '2024. 13.', category: 'BUILD_QUALITY', count: 99 },
    { date: '2024-03-18T24:00:00Z', category: 'BUILD_QUALITY', count: 99 },
  ]);

  assert.deepEqual(
    monthly.map((m) => [m.periodKey, m.totalComplaints]),
    [
      ['2023-12', 7],
      ['2024-03', 10],
      ['2024-04', 5],
    ]
  );

  const quarterly = relCalc.aggregateQuarterlyDefectBreakdown([
    { date: '2024. 3.', category: 'BATTERY_CHARGING', count: 4 },
    { date: '2024-01-01T00:30:00+09', category: 'COLD_WEATHER', count: 7 },
    { date: '2024년 2분기', category: 'DRIVING_POWERTRAIN', count: 5 },
  ]);

  assert.deepEqual(
    quarterly.map((q) => [q.periodKey, q.totalComplaints]),
    [
      ['2023-Q4', 7],
      ['2024-Q1', 4],
      ['2024-Q2', 5],
    ]
  );
}

// 5. Data loading normalization sanity on master datasets
{
  const depDb = depData.getDepreciationDatabase();
  assert.ok(depDb.models.length >= 15);
  assert.ok(depData.getAllBrands().length >= 8);
  assert.ok(depData.getClawbackSchedule().length >= 6);

  const relDb = getRel.getReliabilityTrendsData();
  assert.ok(relDb.brands.length >= 9);
  assert.ok(relDb.categories && relDb.categories.length >= 6);
  for (const brand of relDb.brands) {
    assert.ok(brand.overall_dsi >= 0 && brand.overall_dsi <= 100);
    for (const model of brand.models) {
      assert.ok(model.brand_id.trim().length > 0);
      assert.ok(model.avg_dsi >= 0 && model.avg_dsi <= 100);
    }
  }
}

console.log('✅ All ts-lib-dep-rel 20261127 regression checks passed!');
