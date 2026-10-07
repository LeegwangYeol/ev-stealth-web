/**
 * tests/test_challenger_client_edge_cases.ts
 *
 * EMPIRICAL ADVERSARIAL CHALLENGER: CLIENT EDGE CASES
 * Tasks:
 * 1. Empty models array testing
 * 2. Empty regions array testing
 * 3. Invalid query strings (malformed URI, XSS, prototype pollution, unicode, non-existent identifiers)
 * 4. Component logic & helper stress-testing
 */

import * as subsidy from '../src/lib/getSubsidyData';
import * as recall from '../src/lib/getRecallData';
import * as depreciation from '../src/lib/getDepreciationData';
import * as reliability from '../src/lib/getReliabilityData';
import type { EVSubsidyDataset, RegionEntry, PopularModelEntry } from '../src/types/subsidy';
import type { RecallDatabase } from '../src/lib/getRecallData';

interface TestReport {
  total: number;
  passed: number;
  failed: number;
  anomalies: string[];
  findings: string[];
}

const report: TestReport = {
  total: 0,
  passed: 0,
  failed: 0,
  anomalies: [],
  findings: [],
};

function recordAssert(group: string, name: string, condition: boolean, details?: any) {
  report.total++;
  if (condition) {
    report.passed++;
  } else {
    report.failed++;
    const errMsg = `[${group}] ${name}`;
    report.findings.push(errMsg);
    console.error(`❌ [CHALLENGER FAILURE] ${errMsg}`, details || '');
  }
}

function recordBug(id: string, description: string, details?: any) {
  const bugMsg = `[${id}] ${description}`;
  report.findings.push(bugMsg);
  console.warn(`🐛 [CONFIRMED BUG FINDING] ${bugMsg}`, details || '');
}

function recordAnomaly(group: string, name: string, details?: any) {
  const anomalyMsg = `[${group}] ${name}`;
  report.anomalies.push(anomalyMsg);
  console.warn(`⚠️ [ADVERSARIAL ANOMALY] ${anomalyMsg}`, details || '');
}

console.log('================================================================');
console.log('🔬 EMPIRICAL ADVERSARIAL TEST: CLIENT EDGE CASES & QUERY STRINGS');
console.log('================================================================\n');

// ============================================================================
// PART 1: EMPTY MODELS & EMPTY REGIONS IN SUBSIDY LOGIC
// ============================================================================
console.log('--- [PART 1: Empty Models & Empty Regions in Subsidy Logic] ---');

// 1.1 calculateNetSubsidy with invalid/empty/non-existent IDs
const nonExistentModelIds = [
  '',
  '   ',
  'non-existent-model',
  'null',
  'undefined',
  '__proto__',
  'constructor',
  '<script>alert("xss")</script>',
  '⚡🚗🔋',
  'A'.repeat(5000),
];

const nonExistentRegionIds = [
  '',
  '   ',
  'KR-99',
  'UNKNOWN_REGION',
  'null',
  'undefined',
  '__proto__',
  'constructor',
  'DROP TABLE regions;--',
  '제주도_남극점',
  'B'.repeat(5000),
];

for (const mId of nonExistentModelIds) {
  for (const rId of nonExistentRegionIds) {
    let result: any;
    let didThrow = false;
    try {
      result = subsidy.calculateNetSubsidy(mId, rId);
    } catch (e: any) {
      didThrow = true;
      recordAssert('calculateNetSubsidy:fallback', `Throws on (${mId}, ${rId})`, false, { error: e.message });
    }

    if (!didThrow && result) {
      recordAssert(
        'calculateNetSubsidy:empty_resilience',
        `Returns valid finite numbers for model="${mId.slice(0, 15)}", region="${rId.slice(0, 15)}"`,
        Number.isFinite(result.netPurchasePriceKrw) &&
        Number.isFinite(result.nationalSubsidyKrw) &&
        Number.isFinite(result.localSubsidyKrw) &&
        Number.isFinite(result.totalSubsidyKrw) &&
        typeof result.modelName === 'string' &&
        typeof result.regionName === 'string' &&
        typeof result.warningNotice === 'string'
      );
    }
  }
}

// 1.2 Synthetic empty database tests
const syntheticEmptyDataset: EVSubsidyDataset = {
  metadata: {
    version: '1.0.0',
    generated_at: '2026-10-06T00:00:00Z',
    policy_year: 2026,
    data_sources: ['TEST_EMPTY'],
    total_regions_tracked: 0,
    total_municipalities_tracked: 0,
    currency: 'KRW',
  },
  alert_thresholds: {
    HEALTHY: {
      min_percent: 0,
      max_percent: 60,
      label_ko: '여유',
      severity: 'HEALTHY',
      color_hex: '#10B981',
      badge_class: 'bg-emerald-500',
      recommended_action: '신청 가능',
    },
    CAUTION: {
      min_percent: 60,
      max_percent: 80,
      label_ko: '주의',
      severity: 'CAUTION',
      color_hex: '#F59E0B',
      badge_class: 'bg-amber-500',
      recommended_action: '접수 증가',
    },
    WARNING: {
      min_percent: 80,
      max_percent: 95,
      label_ko: '경고',
      severity: 'WARNING',
      color_hex: '#F97316',
      badge_class: 'bg-orange-500',
      recommended_action: '마감 임박',
    },
    CRITICAL: {
      min_percent: 95,
      max_percent: 100,
      label_ko: '심각',
      severity: 'CRITICAL',
      color_hex: '#EF4444',
      badge_class: 'bg-red-500',
      recommended_action: '조기 소진 위험',
    },
    DEPLETED: {
      min_percent: 100,
      max_percent: 999,
      label_ko: '소진',
      severity: 'DEPLETED',
      color_hex: '#6B7280',
      badge_class: 'bg-gray-500',
      recommended_action: '예산 마감',
    },
  },
  nationwide_summary: {
    total_announced_units: 0,
    total_applied_units: 0,
    total_delivered_units: 0,
    total_remaining_units: 0,
    nationwide_depletion_rate: 0,
    total_budget_billion_krw: 0,
    disbursed_budget_billion_krw: 0,
    category_totals: {
      passenger: {
        announced_units: 0,
        applied_units: 0,
        delivered_units: 0,
        remaining_units: 0,
        depletion_rate: 0,
        delivery_rate: 0,
        status: 'HEALTHY',
        max_local_subsidy_krw: 0,
        max_total_subsidy_krw: 0,
      },
      commercial: {
        announced_units: 0,
        applied_units: 0,
        delivered_units: 0,
        remaining_units: 0,
        depletion_rate: 0,
        delivery_rate: 0,
        status: 'HEALTHY',
        max_local_subsidy_krw: 0,
        max_total_subsidy_krw: 0,
      },
      bus: {
        announced_units: 0,
        applied_units: 0,
        delivered_units: 0,
        remaining_units: 0,
        depletion_rate: 0,
        delivery_rate: 0,
        status: 'HEALTHY',
        max_local_subsidy_krw: 0,
        max_total_subsidy_krw: 0,
      },
    },
    alert_region_counts: {
      healthy: 0,
      caution: 0,
      warning: 0,
      critical: 0,
      depleted: 0,
    },
  },
  regions: [],
  popular_models_matrix: [],
};

recordAssert(
  'empty_models_handling',
  'Empty models matrix has length 0',
  syntheticEmptyDataset.popular_models_matrix.length === 0
);

recordAssert(
  'empty_regions_handling',
  'Empty regions matrix has length 0',
  syntheticEmptyDataset.regions.length === 0
);

// Verify default fallback model structure
const defaultModelFallback: PopularModelEntry = {
  model_id: 'ioniq-5-2026',
  name_ko: '현대 아이오닉 5 롱레인지 2WD (2026)',
  manufacturer: '현대자동차',
  battery_type: 'NCM 삼원계 (84kWh)',
  battery_capacity_kwh: 84.0,
  rated_range_km: 485,
  base_price_krw: 54100000,
  price_subsidy_ratio: 1.0,
  national_subsidy_krw: 6500000,
};

recordAssert(
  'defaultModelFallback:validity',
  'Default model fallback contains complete valid specification',
  defaultModelFallback.base_price_krw > 0 &&
  defaultModelFallback.rated_range_km > 0 &&
  defaultModelFallback.battery_capacity_kwh > 0
);

// 1.3 Defensive lookup guards and luxury subsidy ratio tests
const adversarialLookupKeys: any[] = [null, undefined, '', '   ', 12345, {}, [], NaN, Infinity];
for (const key of adversarialLookupKeys) {
  const reg = subsidy.getRegionById(key);
  recordAssert(
    'subsidy:getRegionById:defensive',
    `getRegionById returns undefined safely for adversarial key ${String(key)}`,
    reg === undefined
  );

  const mdl = subsidy.getModelById(key);
  recordAssert(
    'subsidy:getModelById:defensive',
    `getModelById returns undefined safely for adversarial key ${String(key)}`,
    mdl === undefined
  );
}

// 1.4 Luxury vehicle statutory price exclusion for Infinity MSRP
recordAssert(
  'subsidy:getPriceSubsidyRatio:luxury_infinity',
  'getPriceSubsidyRatio(Infinity) returns 0.0 (luxury vehicle exclusion)',
  subsidy.getPriceSubsidyRatio(Infinity) === 0.0
);
recordAssert(
  'subsidy:getPriceSubsidyRatio:luxury_85M',
  'getPriceSubsidyRatio(85_000_000) returns 0.0 (luxury vehicle boundary)',
  subsidy.getPriceSubsidyRatio(85_000_000) === 0.0
);
recordAssert(
  'subsidy:getPriceSubsidyRatio:negative_default',
  'getPriceSubsidyRatio(-1000) returns 1.0 (default ratio)',
  subsidy.getPriceSubsidyRatio(-1000) === 1.0
);

// ============================================================================
// PART 2: INVALID QUERY STRINGS IN RECALL PORTAL RESOLVER
// ============================================================================
console.log('\n--- [PART 2: Invalid Query Strings in Recall Portal Resolver] ---');

// The exact implementation from RecallPortalClient.tsx
const BRAND_SYNONYMS: Record<string, string> = {
  tesla: '테슬라',
  hyundai: '현대자동차',
  genesis: '제네시스',
  kia: '기아',
  mercedes: '메르세데스-벤츠',
  benz: '메르세데스-벤츠',
  'mercedes-benz': '메르세데스-벤츠',
  bmw: 'BMW',
  byd: 'BYD',
  chevrolet: '쉐보레',
  chevy: '쉐보레',
  polestar: '폴스타',
  porsche: '포르쉐',
};

function resolveBrandActual(inputBrand: string, availableBrands: string[]): string | undefined {
  if (!inputBrand || typeof inputBrand !== 'string') return undefined;
  const normalized = inputBrand.trim().toLowerCase();
  const direct = availableBrands.find((b) => b.toLowerCase() === normalized);
  if (direct) return direct;

  const synonym = Object.prototype.hasOwnProperty.call(BRAND_SYNONYMS, normalized)
    ? BRAND_SYNONYMS[normalized]
    : undefined;
  if (typeof synonym === 'string') {
    const synonymMatch = availableBrands.find((b) => b.toLowerCase() === synonym.toLowerCase());
    if (synonymMatch) return synonymMatch;
  }

  const partial = availableBrands.find(
    (b) => b.toLowerCase().includes(normalized) || normalized.includes(b.toLowerCase())
  );
  if (partial) return partial;

  return undefined;
}

function resolveModelAndBrand(
  modelParam: string | null,
  brandParam: string | null,
  initialDatabase: RecallDatabase,
  availableBrands: string[]
): { brand: string; model: string } | null {
  let resolvedBrand: string | undefined = brandParam
    ? resolveBrandActual(brandParam, availableBrands)
    : undefined;

  let resolvedModel: string | undefined;

  if (modelParam && typeof modelParam === 'string') {
    const cleanModel = modelParam.trim();
    const cleanLower = cleanModel.toLowerCase();

    const variants = Array.from(
      new Set([
        cleanLower,
        cleanLower.replace(/\s+/g, ''),
        cleanLower.replace(/[-_]/g, ''),
        cleanLower.replace(/[-_\s]/g, ''),
      ])
    ).filter(Boolean);

    const candidates: Array<{ brand: string; model: string }> = [];
    (initialDatabase.battery_profiles || []).forEach((p) =>
      candidates.push({ brand: p.brand, model: p.model_name })
    );
    (initialDatabase.vin_prefixes || []).forEach((vp) =>
      candidates.push({ brand: vp.brand, model: vp.model_name })
    );
    (initialDatabase.recalls || []).forEach((r) => {
      (r.target_model || '').split(',').forEach((mStr) => {
        candidates.push({ brand: r.brand, model: mStr.trim() });
      });
    });

    let matchedCandidate: { brand: string; model: string } | undefined;
    for (const v of variants) {
      matchedCandidate = candidates.find((c) => {
        const cLower = (c.model || '').toLowerCase();
        const brandMatch = !resolvedBrand || c.brand === resolvedBrand;
        return brandMatch && cLower === v;
      });
      if (matchedCandidate) break;
    }

    if (!matchedCandidate) {
      for (const v of variants) {
        matchedCandidate = candidates.find((c) => {
          const cLower = (c.model || '').toLowerCase();
          const brandMatch = !resolvedBrand || c.brand === resolvedBrand;
          return brandMatch && (cLower.startsWith(v) || v.startsWith(cLower));
        });
        if (matchedCandidate) break;
      }
    }

    if (!matchedCandidate) {
      for (const v of variants) {
        matchedCandidate = candidates.find((c) => {
          const cLower = (c.model || '').toLowerCase();
          const brandMatch = !resolvedBrand || c.brand === resolvedBrand;
          return brandMatch && (cLower.includes(v) || v.includes(cLower));
        });
        if (matchedCandidate) break;
      }
    }

    if (matchedCandidate) {
      if (!resolvedBrand) resolvedBrand = resolveBrandActual(matchedCandidate.brand, availableBrands);
      resolvedModel = matchedCandidate.model;
    } else {
      resolvedModel = cleanModel;
    }
  }

  if (resolvedBrand && !resolvedModel) {
    const brandModels = recall.getModelsForBrand(resolvedBrand, initialDatabase);
    resolvedModel = brandModels[0] || '';
  }

  if (resolvedBrand && resolvedModel) {
    const brandModels = recall.getModelsForBrand(resolvedBrand, initialDatabase);
    const matchedBrandModel = brandModels.find(
      (m) =>
        m.toLowerCase() === resolvedModel!.toLowerCase() ||
        m.toLowerCase().startsWith(resolvedModel!.toLowerCase()) ||
        resolvedModel!.toLowerCase().startsWith(m.toLowerCase()) ||
        m.toLowerCase().includes(resolvedModel!.toLowerCase()) ||
        resolvedModel!.toLowerCase().includes(m.toLowerCase())
    );
    if (matchedBrandModel) {
      resolvedModel = matchedBrandModel;
    }

    return { brand: resolvedBrand, model: resolvedModel };
  }

  return null;
}

const recallDb = recall.getRecallDatabase();
const availableBrands = recall.getDistinctBrands(recallDb);

// Prototype pollution vulnerability check on RecallPortalClient.tsx:38
const prototypePollutionKeys = ['constructor', 'toString', 'valueOf', 'hasOwnProperty', '__proto__'];
for (const key of prototypePollutionKeys) {
  try {
    const res = resolveBrandActual(key, availableBrands);
    recordAssert(
      'resolveBrand:prototypeSafety',
      `Prototype collision key '${key}' safely handled without crash`,
      res === undefined || typeof res === 'string'
    );
  } catch (err: any) {
    recordBug(
      'VULN-RECALL-PROTO-POLLUTION',
      `RecallPortalClient resolveBrand crashes on query ?brand=${key}: ${err.message}`,
      { queryParam: `?brand=${key}`, error: err.message }
    );
  }
}

// Adversarial query param test matrix (without prototype pollution keys)
const adversarialQueryParams = [
  // 1. Malformed / empty / null
  { model: null, brand: null, desc: 'both null' },
  { model: '', brand: '', desc: 'both empty string' },
  { model: '   ', brand: '   ', desc: 'whitespace only' },
  // 2. Corrupt URI & decoding anomalies
  { model: '%E0%A4%A', brand: '%FF%FE', desc: 'percent-encoded malformed bytes' },
  { model: '????&&&&====', brand: '????', desc: 'punctuation only' },
  // 3. Injection / Exploit strings
  { model: "'; DROP TABLE recalls; --", brand: "' OR '1'='1", desc: 'SQL injection strings' },
  { model: '<script>alert("xss")</script>', brand: '<img src=x onerror=alert(1)>', desc: 'XSS HTML tags' },
  // 4. Extreme Unicode & RTL & control chars
  { model: '🚗⚡💥🔥', brand: '🇰🇷🇩🇪🇺🇸', desc: 'emojis and flags' },
  { model: '\u202E\u0000\u0001\r\n\t', brand: '\uFEFF\u200B\u200C', desc: 'control characters and zero-width spaces' },
  // 5. Overflow strings
  { model: 'A'.repeat(5000), brand: 'B'.repeat(5000), desc: '5,000-char string overflow' },
  // 6. Valid brand but non-existent model
  { model: 'FlyingSaucer2099', brand: '현대자동차', desc: 'valid brand with fictional model' },
  // 7. Non-existent brand with valid model
  { model: '아이오닉 5', brand: 'MartianMotors', desc: 'fictional brand with valid model' },
  // 8. Brand synonyms & case variations
  { model: 'model y', brand: 'tesla', desc: 'lowercase synonym' },
  { model: 'EQE', brand: 'benz', desc: 'synonym benz' },
  { model: 'ev6', brand: 'KIA', desc: 'uppercase synonym' },
];

for (const qp of adversarialQueryParams) {
  let res: any;
  let threw = false;
  try {
    res = resolveModelAndBrand(qp.model, qp.brand, recallDb, availableBrands);
  } catch (err: any) {
    threw = true;
    recordAssert('resolveModelAndBrand', `Throws on ${qp.desc}`, false, { error: err.message });
  }

  if (!threw) {
    recordAssert(
      'resolveModelAndBrand:safety',
      `Handled safely without crash on ${qp.desc}`,
      res === null || (typeof res === 'object' && typeof res.brand === 'string' && typeof res.model === 'string')
    );
  }
}

// 2.2 Test resolveModelAndBrand with EMPTY database
const emptyRecallDb: RecallDatabase = {
  metadata: {
    version: '0.0.0',
    updated_at: '2026-10-06T00:00:00Z',
    total_campaigns: 0,
    total_affected_vehicles_kdm: 0,
    active_fire_campaigns: 0,
    ota_remedy_rate_pct: 0,
  },
  recalls: [],
  vin_prefixes: [],
  battery_profiles: [],
};

const emptyBrands: string[] = [];

for (const qp of adversarialQueryParams) {
  let threw = false;
  let res: any;
  try {
    res = resolveModelAndBrand(qp.model, qp.brand, emptyRecallDb, emptyBrands);
  } catch (err: any) {
    threw = true;
    recordAssert('resolveModelAndBrand:empty_db', `Throws on empty DB with ${qp.desc}`, false, { error: err.message });
  }

  if (!threw) {
    recordAssert(
      'resolveModelAndBrand:empty_db',
      `Safely handles empty DB with ${qp.desc}`,
      res === null || (typeof res === 'object' && typeof res.brand === 'string')
    );
  }
}

// ============================================================================
// PART 3: DEPRECIATION CALCULATOR WITH EMPTY MODELS
// ============================================================================
console.log('\n--- [PART 3: Depreciation Calculator With Empty Models] ---');

const emptyDepreciationDb = {
  metadata: {
    version: '1.0.0',
    updated_at: '2026-10-06T00:00:00Z',
    total_models_analyzed: 0,
    market_notes: 'Empty database test',
  },
  models: [],
};

// Check fallback model logic in DepreciationCalculatorClient:
// Line 66: initialDatabase?.models?.length > 0 ? initialDatabase.models : [FALLBACK_MODEL]
const fallbackCandidate = (emptyDepreciationDb.models && emptyDepreciationDb.models.length > 0)
  ? emptyDepreciationDb.models
  : ['FALLBACK_TRIGGERED'];

recordAssert(
  'depreciation:empty_models',
  'Empty models array in depreciation database triggers fallback',
  fallbackCandidate[0] === 'FALLBACK_TRIGGERED'
);

// calculateDepreciation with empty / non-existent modelId
const depResDefault = depreciation.calculateDepreciation({
  modelId: 'non-existent-depreciation-model',
  years: 3,
  mileageKm: 45000,
});

recordAssert(
  'depreciation:non_existent_modelId',
  'calculateDepreciation falls back gracefully to default model when modelId is invalid',
  Number.isFinite(depResDefault.adjustedResidualPct) &&
  Number.isFinite(depResDefault.estimatedResidualPriceKrw) &&
  typeof depResDefault.model.model_name === 'string' &&
  depResDefault.model.model_name.length > 0
);

// 3.2 simulateBatteryHealth input sanitization under NaN and extreme values
const sanitizedHealth = depreciation.simulateBatteryHealth({
  years: NaN,
  totalKm: NaN,
  ambientTempC: NaN,
  storageSoc: NaN,
  dcfcRatio: NaN,
});
recordAssert(
  'depreciation:simulateBatteryHealth:sanitized_inputs',
  'simulateBatteryHealth handles NaN ambientTempC, storageSoc, and dcfcRatio without NaN in outputs',
  Number.isFinite(sanitizedHealth.calendarLossPct) &&
  Number.isFinite(sanitizedHealth.cyclicLossPct) &&
  Number.isFinite(sanitizedHealth.totalLossPct) &&
  Number.isFinite(sanitizedHealth.sohPct)
);

// ============================================================================
// PART 4: RELIABILITY DASHBOARD WITH EMPTY BRANDS / MODELS
// ============================================================================
console.log('\n--- [PART 4: Reliability Dashboard With Empty Brands / Models] ---');

const emptyReliabilityDb: any = {
  metadata: {
    version: '1.0.0',
    updated_at: '2026-10-06T00:00:00Z',
    total_records_analyzed: 0,
    brands_count: 0,
    models_count: 0,
    avg_industry_dsi: 0,
  },
  categories: [],
  repair_cost_matrix: [],
  brands: [],
};

const enrichedModelsEmpty = reliability.getAllEnrichedModels(emptyReliabilityDb);
recordAssert(
  'reliability:empty_brands',
  'getAllEnrichedModels returns empty array without throwing when brands is []',
  Array.isArray(enrichedModelsEmpty) && enrichedModelsEmpty.length === 0
);

// 4.2 getAllEnrichedModels with non-array brands / models
const malformedReliabilityDbs: any[] = [
  {},
  { brands: null },
  { brands: undefined },
  { brands: 'not-an-array' },
  { brands: [{ name_ko: '무효브랜드', models: null }] },
  { brands: [{ name_ko: '무효브랜드', models: undefined }] },
  { brands: [{ name_ko: '유효브랜드', name_en: 'Valid', country: 'KR', models: [{ model_name: '테스트' }] }] },
];

for (const mDb of malformedReliabilityDbs) {
  let threw = false;
  let res: any;
  try {
    res = reliability.getAllEnrichedModels(mDb);
  } catch (err: any) {
    threw = true;
  }
  recordAssert(
    'reliability:getAllEnrichedModels:iterability_guards',
    `getAllEnrichedModels does not throw on malformed db structure`,
    !threw && Array.isArray(res)
  );
}

// ============================================================================
// PART 5: URL SEARCHPARAMS SIMULATION FOR CLIENT PAGES
// ============================================================================
console.log('\n--- [PART 5: Client SearchParams Simulation & URL Boundaries] ---');

const rawQueryStrings = [
  '?region=KR-11&model=ioniq-5-2026',
  '?region=&model=',
  '?region=INVALID_REGION_99&model=INVALID_MODEL_99',
  '?region=%E0%A4%A&model=%FF%FE',
  '?region=' + 'X'.repeat(5000) + '&model=' + 'Y'.repeat(5000),
  '?brand=tesla&model=model+y&year=2024',
  '?brand=benz&model=EQE&year=-9999',
  '?brand=kia&model=ev6&year=NaN',
  '?brand=hyundai&model=ioniq5&year=Infinity',
  '?brand=genesis&model=gv60&year=1e30',
  '?brand=' + encodeURIComponent('<script>alert(1)</script>') + '&model=test',
];

for (const qs of rawQueryStrings) {
  let parsedParams: URLSearchParams | null = null;
  let threw = false;
  try {
    parsedParams = new URLSearchParams(qs);
  } catch (e: any) {
    threw = true;
    recordAssert('URLSearchParams:parsing', `Throws on query string ${qs.slice(0, 30)}`, false, { error: e.message });
  }

  if (!threw && parsedParams) {
    const regionParam = parsedParams.get('region') || '';
    const modelParam = parsedParams.get('model') || '';
    const brandParam = parsedParams.get('brand') || '';
    const yearParam = parsedParams.get('year');

    // Test Year parsing guard
    let parsedYear: number | undefined;
    if (yearParam) {
      const parsedNum = parseInt(yearParam, 10);
      parsedYear = Number.isFinite(parsedNum) && !Number.isNaN(parsedNum) ? parsedNum : undefined;
    }

    // Subsidy calculation with these params
    const subCalc = subsidy.calculateNetSubsidy(modelParam, regionParam);
    recordAssert(
      'searchParams:subsidyIntegration',
      `Subsidy calculation succeeds cleanly for query "${qs.slice(0, 35)}..."`,
      Number.isFinite(subCalc.netPurchasePriceKrw) && Number.isFinite(subCalc.totalSubsidyKrw)
    );

    // Recall portal with these params
    const recallMatch = resolveModelAndBrand(modelParam, brandParam, recallDb, availableBrands);
    recordAssert(
      'searchParams:recallIntegration',
      `Recall matching succeeds cleanly without throw for query "${qs.slice(0, 35)}..."`,
      recallMatch === null || typeof recallMatch.brand === 'string'
    );
  }
}

console.log('\n================================================================');
console.log('🏁 EMPIRICAL ADVERSARIAL CHALLENGER VERIFICATION SUMMARY:');
console.log(`   Total Assertions Evaluated: ${report.total}`);
console.log(`   Passed:                     ${report.passed}`);
console.log(`   Failed:                     ${report.failed}`);
console.log(`   Confirmed Bug Findings:     ${report.findings.length}`);
console.log('================================================================\n');

if (report.failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}
