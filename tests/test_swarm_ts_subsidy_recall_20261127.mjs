import assert from 'node:assert/strict';
import * as subsidyCalc from '../src/lib/subsidyCalculations.ts';
import * as getSubsidy from '../src/lib/getSubsidyData.ts';
import * as recallCalc from '../src/lib/recallCalculations.ts';
import * as getRecall from '../src/lib/getRecallData.ts';

// 1. Subsidy UTC date parsing, rollover rejection, and TZ abbreviation handling
{
  const invalidDates = [
    '2026-02-30 12:00:00 GMT (UTC)',
    '2026-02-30 12:00:00 +09:00 (KST)',
    '2026-04-31 00:00:00 UTC (UTC)',
    '2026-02-30 12:00:00 EST',
    '2026-04-31 12:00:00 PST',
    '2026-02-30 12:00:00 GMT+0900 (Korean Standard Time)',
    '02/30/2026 12:00:00 GMT',
    'Feb 30 12:00:00 2026 EST',
    '2026-02-29',
  ];
  for (const raw of invalidDates) {
    assert.equal(
      subsidyCalc.predictExhaustionDate(0, 1, raw),
      null,
      `Expected null for rolled-over/invalid date: ${raw}`
    );
  }

  assert.equal(subsidyCalc.predictExhaustionDate(0, 1, 'Mar 1, 2026 20:00:00 EST'), '2026-03-02');
  assert.equal(subsidyCalc.predictExhaustionDate(0, 1, 'Mar 1, 2026 20:00:00 PST'), '2026-03-02');
  assert.equal(subsidyCalc.predictExhaustionDate(0, 1, '2026-03-01 20:00:00 EST'), '2026-03-02');
  assert.equal(subsidyCalc.predictExhaustionDate(0, 1, '2026-03-01T12:00:00Z (UTC)'), '2026-03-01');
  assert.equal(subsidyCalc.predictExhaustionDate(0, 1, '2026-03-01T00:30:00+09:00'), '2026-02-28');
}

// 2. Recall UTC date parsing, rollover rejection, and TZ bounds (both modules)
for (const mod of [recallCalc, getRecall]) {
  const invalidRecallDates = [
    'Feb 30 12:00:00 2024 GMT',
    '30 Feb 12:00:00 2024 UTC',
    'Mar 18, 2024 12:00:00 +25:00',
    '2024-02-30 12:00:00 EST',
    '2024.02.30 12:00:00 GMT',
    '2024-02-30T12:00:00-05:00 (EST)',
  ];
  for (const raw of invalidRecallDates) {
    assert.equal(mod.parseRecallDate(raw), null, `Expected null for invalid recall date: ${raw}`);
  }

  assert.equal(
    mod.parseRecallDate('Mar 18, 2024 20:00:00 EST')?.toISOString(),
    '2024-03-19T01:00:00.000Z'
  );
  assert.equal(
    mod.parseRecallDate('2024-03-18 20:00:00 EST')?.toISOString(),
    '2024-03-19T01:00:00.000Z'
  );
}

// 3. Overflow saturation in aggregateRecallsByManufacturer & calculateRecallKPIs
for (const mod of [recallCalc, getRecall]) {
  const campaigns = [
    {
      id: 'R-SMALL',
      campaign_no: 'C-1',
      agency: 'MOLIT',
      agency_ko: '국토교통부',
      brand: '현대자동차',
      target_model: '아이오닉 5',
      target_model_years: '2024',
      production_date_range: '2024.01.01 ~ 2024.12.31',
      affected_kdm_units: 1e307,
      defect_title: '테스트1',
      risk_level: 'FIRE_HAZARD',
      risk_level_ko: '화재 위험',
      defect_detail: '테스트',
      remedy_type: 'OTA_WIRELESS',
      remedy_type_ko: 'OTA',
      remedy_action: '조치',
      consumer_emergency_guide: '없음',
      service_center_contact: '080-000-0000',
      official_link: 'https://www.car.go.kr',
      status: 'ACTIVE',
    },
    {
      id: 'R-LARGE',
      campaign_no: 'C-2',
      agency: 'MOLIT',
      agency_ko: '국토교통부',
      brand: '현대자동차',
      target_model: '아이오닉 5',
      target_model_years: '2024',
      production_date_range: '2024.01.01 ~ 2024.12.31',
      affected_kdm_units: 1.7e308,
      defect_title: '테스트2',
      risk_level: 'FIRE_HAZARD',
      risk_level_ko: '화재 위험',
      defect_detail: '테스트',
      remedy_type: 'OTA_WIRELESS',
      remedy_type_ko: 'OTA',
      remedy_action: '조치',
      consumer_emergency_guide: '없음',
      service_center_contact: '080-000-0000',
      official_link: 'https://www.car.go.kr',
      status: 'RESOLVED',
    },
  ];

  const agg = mod.aggregateRecallsByManufacturer(campaigns);
  assert.equal(agg['현대자동차'].affectedUnits, Number.MAX_VALUE);
  assert.ok(Number.isFinite(agg['현대자동차'].affectedUnits));

  const kpis = mod.calculateRecallKPIs({
    metadata: recallCalc.DEFAULT_RECALL_METADATA,
    vin_prefixes: [],
    battery_profiles: [],
    recalls: campaigns,
  });
  assert.equal(kpis.totalAffectedVehiclesKdm, Number.MAX_VALUE);
  assert.ok(Number.isFinite(kpis.totalAffectedVehiclesKdm));
}

// 4. Lookup complexity & longest-prefix-first / tie-breaking / mutation safety
for (const mod of [recallCalc, getRecall]) {
  const vinPrefixes = [];
  for (let i = 0; i < 2000; i++) {
    const code = String(i).padStart(4, '0');
    vinPrefixes.push({
      prefix: `KM8${code}`,
      wmi: 'KM8',
      brand: '현대자동차',
      model_name: `더미-${i}`,
      country: '대한민국',
      sample_full_vin: `KM8${code}R0000000000`.slice(0, 17),
      sample_description: 'dummy',
    });
  }
  // Longer prefix should win over shorter prefix, and first equal-length prefix should win
  vinPrefixes.push(
    {
      prefix: 'KM8ZZ',
      wmi: 'KM8',
      brand: '현대자동차',
      model_name: '짧은모델',
      country: '대한민국',
      sample_full_vin: 'KM8ZZ0000R0000000',
      sample_description: 'short',
    },
    {
      prefix: 'KM8ZZ123',
      wmi: 'KM8',
      brand: '현대자동차',
      model_name: '긴모델-첫번째',
      country: '대한민국',
      sample_full_vin: 'KM8ZZ1230R0000000',
      sample_description: 'long-first',
    },
    {
      prefix: 'KM8ZZ123',
      wmi: 'KM8',
      brand: '현대자동차',
      model_name: '긴모델-두번째',
      country: '대한민국',
      sample_full_vin: 'KM8ZZ1230R0000000',
      sample_description: 'long-second',
    }
  );

  const customDb = {
    metadata: recallCalc.DEFAULT_RECALL_METADATA,
    vin_prefixes: vinPrefixes,
    battery_profiles: [],
    recalls: [],
  };

  const t0 = performance.now();
  for (let i = 0; i < 200; i++) {
    const res = mod.decodeVinAndCheckRecalls('KM8ZZ1234R0000001', customDb);
    assert.equal(res.decodedModel, '긴모델-첫번째');
  }
  const elapsedMs = performance.now() - t0;
  assert.ok(elapsedMs < 1000, `Expected fast indexed prefix lookup, got ${elapsedMs}ms`);

  // Mutation invalidation check
  vinPrefixes[vinPrefixes.length - 2] = {
    prefix: 'KM8ZZ999',
    wmi: 'KM8',
    brand: '현대자동차',
    model_name: '변경모델',
    country: '대한민국',
    sample_full_vin: 'KM8ZZ9990R0000000',
    sample_description: 'mutated',
  };
  assert.equal(
    mod.decodeVinAndCheckRecalls('KM8ZZ1234R0000001', customDb).decodedModel,
    '긴모델-두번째'
  );
  assert.equal(
    mod.decodeVinAndCheckRecalls('KM8ZZ9994R0000001', customDb).decodedModel,
    '변경모델'
  );
}

// 5. Subsidy lookup performance + NFC normalization on code & manufacturer_ko
{
  const models = Object.freeze([
    Object.freeze({ model_id: 'ioniq-5', name_ko: '아이오닉 5' }),
    Object.freeze({ model_id: 'ev6-gt', name_ko: '기아 EV6 GT' }),
  ]);
  assert.equal(subsidyCalc.getModelByIdFromList(models, 'ioniq5')?.model_id, 'ioniq-5');
  assert.equal(subsidyCalc.getModelByIdFromList(models, 'EV6 GT')?.model_id, 'ev6-gt');

  const normalized = getSubsidy.normalizeSubsidyDataset({
    regions: [
      {
        region_id: 'KR-11',
        code: '서'.normalize('NFD'),
        name_ko: '서울특별시',
      },
      null,
      123,
    ],
    popular_models_matrix: [
      {
        model_id: 'm1',
        name_ko: '모델',
        manufacturer_ko: '현대'.normalize('NFD'),
      },
      'bad-entry',
    ],
  });
  assert.equal(normalized.regions.length, 1);
  assert.equal(normalized.regions[0].code, '서');
  assert.equal(normalized.popular_models_matrix.length, 1);
  assert.equal(normalized.popular_models_matrix[0].manufacturer_ko, '현대');
}

console.log('ALL SWARM TS SUBSIDY & RECALL 2026-11-27 REGRESSION TESTS PASSED!');
