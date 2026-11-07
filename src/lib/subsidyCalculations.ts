/**
 * Pure calculation utilities, type definitions, and mathematical models for South Korea EV Subsidies.
 * Based on Ministry of Environment (환경부) & Korea Environment Corporation (KECO) 2026 Guidelines.
 *
 * This module has ZERO dependencies on heavy JSON data files, enabling client bundles
 * to remain lean without bundling redundant static data payloads.
 */

import type {
  AlertSeverity,
  AlertThresholdConfig,
  CategoryMetrics,
  RegionEntry,
  PopularModelEntry,
  EVSubsidyDataset,
  SubsidyCalculationResult,
  SubsidyCalculatorOptions,
  MunicipalityMetrics,
} from '../types/subsidy.ts';

export type {
  AlertSeverity,
  AlertThresholdConfig,
  CategoryMetrics,
  RegionEntry,
  PopularModelEntry,
  EVSubsidyDataset,
  SubsidyCalculationResult,
  SubsidyCalculatorOptions,
  MunicipalityMetrics,
};

// ==========================================
// 1. FROZEN DEFAULT FALLBACK CONSTANTS (Zero-GC)
// ==========================================

export const DEFAULT_SUBSIDY_THRESHOLDS: Readonly<Record<AlertSeverity, Readonly<AlertThresholdConfig>>> = Object.freeze({
  HEALTHY: Object.freeze({
    min_percent: 0.0,
    max_percent: 59.9,
    label_ko: '원활 (신청 여유)',
    severity: 'HEALTHY' as AlertSeverity,
    color_hex: '#10B981',
    badge_class: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    recommended_action: '보조금 잔여량이 충분하여 신청 접수 후 통상 1~2주 내 교부 결정됩니다.',
  }),
  CAUTION: Object.freeze({
    min_percent: 60.0,
    max_percent: 79.9,
    label_ko: '주의 (소진 가속)',
    severity: 'CAUTION' as AlertSeverity,
    color_hex: '#F59E0B',
    badge_class: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    recommended_action: '출고 예정 시기가 1~2개월 이내인 경우 조속한 서류 접수를 권장합니다.',
  }),
  WARNING: Object.freeze({
    min_percent: 80.0,
    max_percent: 94.9,
    label_ko: '경고 (마감 임박)',
    severity: 'WARNING' as AlertSeverity,
    color_hex: '#F97316',
    badge_class: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    recommended_action: '잔여 예산 소진이 임박했습니다. 즉시 출고 가능한 실재고 매칭이 필요합니다.',
  }),
  CRITICAL: Object.freeze({
    min_percent: 95.0,
    max_percent: 99.9,
    label_ko: '위험 (잔여 극소)',
    severity: 'CRITICAL' as AlertSeverity,
    color_hex: '#EF4444',
    badge_class: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    recommended_action: '선착순 마감 직전입니다. 담당 지자체 문의 및 추경 예산 편성 여부를 확인하세요.',
  }),
  DEPLETED: Object.freeze({
    min_percent: 100.0,
    max_percent: 999.0,
    label_ko: '마감 (접수 종료)',
    severity: 'DEPLETED' as AlertSeverity,
    color_hex: '#6B7280',
    badge_class: 'bg-slate-800 text-slate-200 border-slate-600',
    recommended_action: '2026년 공고 예산이 전액 소진되었습니다. 취소분 대기 접수 또는 차년도 사업을 준비하세요.',
  }),
});

export const DEFAULT_NATIONWIDE_SUMMARY = Object.freeze({
  total_announced_units: 0,
  total_applied_units: 0,
  total_delivered_units: 0,
  total_remaining_units: 0,
  nationwide_depletion_rate: 0,
  total_budget_billion_krw: 0,
  disbursed_budget_billion_krw: 0,
  category_totals: Object.freeze({
    passenger: Object.freeze({
      announced_units: 0,
      applied_units: 0,
      delivered_units: 0,
      remaining_units: 0,
      depletion_rate: 0,
      delivery_rate: 0,
      status: 'HEALTHY' as AlertSeverity,
    }),
    commercial: Object.freeze({
      announced_units: 0,
      applied_units: 0,
      delivered_units: 0,
      remaining_units: 0,
      depletion_rate: 0,
      delivery_rate: 0,
      status: 'HEALTHY' as AlertSeverity,
    }),
    bus: Object.freeze({
      announced_units: 0,
      applied_units: 0,
      delivered_units: 0,
      remaining_units: 0,
      depletion_rate: 0,
      delivery_rate: 0,
      status: 'HEALTHY' as AlertSeverity,
    }),
  }),
  alert_region_counts: Object.freeze({
    healthy: 0,
    caution: 0,
    warning: 0,
    critical: 0,
    depleted: 0,
  }),
});

export const DEFAULT_FALLBACK_DATASET: EVSubsidyDataset = Object.freeze({
  metadata: Object.freeze({
    version: '1.0.0',
    generated_at: '2026-01-01T00:00:00.000Z',
    policy_year: 2026,
    data_sources: Object.freeze([
      '환경부 무공해차 통합누리집 (ev.or.kr)',
      '한국환경공단 (KECO) CleanSys',
      '17개 광역시도 무공해차 보급 촉진 고시공고',
    ]) as unknown as string[],
    total_regions_tracked: 17,
    total_municipalities_tracked: 73,
    currency: 'KRW',
  }),
  alert_thresholds: DEFAULT_SUBSIDY_THRESHOLDS as unknown as Record<AlertSeverity, AlertThresholdConfig>,
  nationwide_summary: DEFAULT_NATIONWIDE_SUMMARY as unknown as EVSubsidyDataset['nationwide_summary'],
  regions: Object.freeze([]) as unknown as RegionEntry[],
  popular_models_matrix: Object.freeze([]) as unknown as PopularModelEntry[],
}) as unknown as EVSubsidyDataset;

// ==========================================
// 2. CANONICAL REGION ALIAS MAP
// ==========================================

export const REGION_ALIAS_MAP: Readonly<Record<string, string>> = Object.freeze({
  // Special City / Metropolitan Cities
  '서울': 'KR-11',
  '서울특별시': 'KR-11',
  'seoul': 'KR-11',
  '부산': 'KR-26',
  '부산광역시': 'KR-26',
  'busan': 'KR-26',
  '대구': 'KR-27',
  '대구광역시': 'KR-27',
  'daegu': 'KR-27',
  '인천': 'KR-28',
  '인천광역시': 'KR-28',
  'incheon': 'KR-28',
  '광주': 'KR-29',
  '광주광역시': 'KR-29',
  'gwangju': 'KR-29',
  '대전': 'KR-30',
  '대전광역시': 'KR-30',
  'daejeon': 'KR-30',
  '울산': 'KR-31',
  '울산광역시': 'KR-31',
  'ulsan': 'KR-31',
  // Special Self-Governing City (CleanSys KR-36 and ISO KR-50)
  '세종': 'KR-36',
  '세종특별자치시': 'KR-36',
  'sejong': 'KR-36',
  'kr-50': 'KR-36',
  'kr-36': 'KR-36',
  // Provinces
  '경기': 'KR-41',
  '경기도': 'KR-41',
  'gyeonggi': 'KR-41',
  '강원': 'KR-42',
  '강원도': 'KR-42',
  '강원특별자치도': 'KR-42',
  'gangwon': 'KR-42',
  '충북': 'KR-43',
  '충청북도': 'KR-43',
  'chungbuk': 'KR-43',
  '충남': 'KR-44',
  '충청남도': 'KR-44',
  'chungnam': 'KR-44',
  '전북': 'KR-45',
  '전라북도': 'KR-45',
  '전북특별자치도': 'KR-45',
  'jeonbuk': 'KR-45',
  '전남': 'KR-46',
  '전라남도': 'KR-46',
  'jeonnam': 'KR-46',
  '경북': 'KR-47',
  '경상북도': 'KR-47',
  'gyeongbuk': 'KR-47',
  '경남': 'KR-48',
  '경상남도': 'KR-48',
  'gyeongnam': 'KR-48',
  '제주': 'KR-49',
  '제주도': 'KR-49',
  '제주특별자치도': 'KR-49',
  'jeju': 'KR-49',
});

// ==========================================
// 3. STATUTORY PRICE-CAP FORMULA
// ==========================================

/**
 * Calculates national subsidy multiplier based on 2026 MOE statutory price caps:
 * - MSRP <= 55,000,000 KRW: 1.0 (100% eligibility)
 * - 55,000,000 < MSRP <= 85,000,000 KRW: 0.5 (50% eligibility)
 * - MSRP > 85,000,000 KRW or invalid/negative: 0.0 (luxury vehicle exclusion)
 */
export function getPriceSubsidyRatio(msrpKrw: number): number {
  if (!Number.isFinite(msrpKrw) || msrpKrw <= 0 || msrpKrw === Infinity) {
    return 0.0;
  }
  if (msrpKrw <= 55_000_000) {
    return 1.0;
  }
  if (msrpKrw <= 85_000_000) {
    return 0.5;
  }
  return 0.0;
}

// ==========================================
// 4. PURE LIST LOOKUP FUNCTIONS
// ==========================================

/**
 * Pure region resolver from a supplied array of regions.
 * Matches by region_id, iso_code, Korean name, English name, canonical alias,
 * or stripped administrative suffix.
 * Defensively guards against missing properties or non-string attributes.
 */
export function getRegionByIdFromList(
  regions: readonly RegionEntry[] | undefined,
  regionId: string
): RegionEntry | undefined {
  if (!regionId || typeof regionId !== 'string' || !Array.isArray(regions)) return undefined;
  const normalized = regionId.trim().toLowerCase();
  if (!normalized) return undefined;

  const validRegions = regions.filter((r): r is RegionEntry => Boolean(r && typeof r === 'object'));

  // 1. Direct alias resolution
  const rawAlias = Object.prototype.hasOwnProperty.call(REGION_ALIAS_MAP, normalized)
    ? REGION_ALIAS_MAP[normalized]
    : Object.prototype.hasOwnProperty.call(REGION_ALIAS_MAP, regionId.trim())
    ? REGION_ALIAS_MAP[regionId.trim()]
    : undefined;
  const aliasedId = typeof rawAlias === 'string' ? rawAlias.toLowerCase() : undefined;
  if (aliasedId) {
    const matched = validRegions.find(
      (r) =>
        (typeof r.region_id === 'string' && r.region_id.toLowerCase() === aliasedId) ||
        (typeof r.iso_code === 'string' && r.iso_code.toLowerCase() === aliasedId)
    );
    if (matched) return matched;
  }

  // 2. Direct exact match on ID, ISO code, or localized names
  const exact = validRegions.find(
    (r) =>
      (typeof r.region_id === 'string' && r.region_id.toLowerCase() === normalized) ||
      (typeof r.iso_code === 'string' && r.iso_code.toLowerCase() === normalized) ||
      (typeof r.name_ko === 'string' && r.name_ko.toLowerCase() === normalized) ||
      (typeof r.name_en === 'string' && r.name_en.toLowerCase() === normalized)
  );
  if (exact) return exact;

  // 3. 2-letter provincial abbreviation / stripped administrative suffix match
  const stripped = normalized.replace(/(특별시|광역시|특별자치시|특별자치도|도)$/, '');
  if (stripped) {
    const rawStrippedAlias = Object.prototype.hasOwnProperty.call(REGION_ALIAS_MAP, stripped)
      ? REGION_ALIAS_MAP[stripped]
      : undefined;
    const strippedAliasedId = typeof rawStrippedAlias === 'string' ? rawStrippedAlias.toLowerCase() : undefined;
    if (strippedAliasedId) {
      const matched = validRegions.find(
        (r) =>
          (typeof r.region_id === 'string' && r.region_id.toLowerCase() === strippedAliasedId) ||
          (typeof r.iso_code === 'string' && r.iso_code.toLowerCase() === strippedAliasedId)
      );
      if (matched) return matched;
    }

    return validRegions.find((r) => {
      if (!r.name_ko || typeof r.name_ko !== 'string') return false;
      const rStripped = r.name_ko.toLowerCase().replace(/(특별시|광역시|특별자치시|특별자치도|도)$/, '');
      return (
        rStripped === stripped ||
        r.name_ko.toLowerCase().includes(stripped) ||
        stripped.includes(rStripped)
      );
    });
  }

  return undefined;
}

/**
 * Pure model resolver from a supplied array of popular models.
 * Supports whitespace-, hyphen-, and punctuation-normalized queries.
 * Defensively guards against missing properties or non-string attributes.
 */
export function getModelByIdFromList(
  models: readonly PopularModelEntry[] | undefined,
  modelId: string
): PopularModelEntry | undefined {
  if (!modelId || typeof modelId !== 'string' || !Array.isArray(models)) return undefined;
  const normalized = modelId.trim().toLowerCase();
  if (!normalized) return undefined;

  const validModels = models.filter((m): m is PopularModelEntry => Boolean(m && typeof m === 'object'));

  // 1. Exact or substring match on raw string
  const directMatch = validModels.find(
    (m) =>
      (typeof m.model_id === 'string' && m.model_id.toLowerCase() === normalized) ||
      (typeof m.name_ko === 'string' && m.name_ko.toLowerCase() === normalized) ||
      (typeof m.name_ko === 'string' && m.name_ko.toLowerCase().includes(normalized))
  );
  if (directMatch) return directMatch;

  // 2. Normalize by stripping whitespace, hyphens, and punctuation
  const cleanQuery = normalized.replace(/[\s\-_]+/g, '');
  if (!cleanQuery) return undefined;

  return validModels.find((m) => {
    const cleanId = (typeof m.model_id === 'string' ? m.model_id : '').toLowerCase().replace(/[\s\-_]+/g, '');
    const cleanKo = (typeof m.name_ko === 'string' ? m.name_ko : '').toLowerCase().replace(/[\s\-_]+/g, '');
    return (cleanId && cleanId.includes(cleanQuery)) || (cleanKo && cleanKo.includes(cleanQuery));
  });
}

// ==========================================
// 4.1 PURE DEPLETION & DELIVERY RATE CALCULATIONS
// ==========================================

export interface DepletionRateOptions {
  clamp100?: boolean;
  roundDecimals?: number;
}

/**
 * Calculates EV subsidy depletion rate as percentage with zero-division guard and negative clamping.
 *
 * Formula: (appliedCount / totalQuota) * 100
 *
 * Division by Zero & Validation Protection:
 * - When totalQuota === 0, <= 0, or is not a finite number, returns 0.0.
 * - When appliedCount is invalid (null, undefined, negative, or not finite), returns 0.0.
 * - When clamp100 is true, clamps result to 100.0%.
 * - Rounds to specified decimal places (default: 1 decimal, e.g. 89.4%).
 */
export function calculateDepletionRate(
  appliedCount?: number | null,
  totalQuota?: number | null,
  options?: DepletionRateOptions
): number {
  if (
    totalQuota === null ||
    totalQuota === undefined ||
    !Number.isFinite(totalQuota) ||
    totalQuota <= 0
  ) {
    return 0.0;
  }
  if (
    appliedCount === null ||
    appliedCount === undefined ||
    !Number.isFinite(appliedCount) ||
    appliedCount <= 0
  ) {
    return 0.0;
  }

  let rate = (appliedCount / totalQuota) * 100;
  if (options?.clamp100) {
    rate = Math.min(100.0, rate);
  }

  const decimals = typeof options?.roundDecimals === 'number' && Number.isFinite(options.roundDecimals) && options.roundDecimals >= 0
    ? Math.floor(options.roundDecimals)
    : 1;
  const factor = Math.pow(10, decimals);
  const rounded = Math.round(rate * factor) / factor;

  return Number.isFinite(rounded) && rounded >= 0 ? rounded : 0.0;
}

/**
 * Calculates EV delivery rate percentage against announced quota: (delivered / quota) * 100.
 */
export function calculateDeliveryRate(
  deliveredCount?: number | null,
  totalQuota?: number | null,
  options?: DepletionRateOptions
): number {
  return calculateDepletionRate(deliveredCount, totalQuota, options);
}

/**
 * Calculates remaining available subsidy units (quota - applied) clamped at 0.
 */
export function calculateRemainingUnits(
  appliedCount?: number | null,
  totalQuota?: number | null
): number {
  if (
    totalQuota === null ||
    totalQuota === undefined ||
    !Number.isFinite(totalQuota) ||
    totalQuota <= 0
  ) {
    return 0;
  }
  const safeQuota = Math.floor(totalQuota);
  if (
    appliedCount === null ||
    appliedCount === undefined ||
    !Number.isFinite(appliedCount) ||
    appliedCount <= 0
  ) {
    return Math.max(0, safeQuota);
  }
  const safeApplied = Math.floor(appliedCount);
  return Math.max(0, safeQuota - safeApplied);
}

// ==========================================
// 4.2 NUMBER PARSING & MISSING PROPERTIES GUARDS
// ==========================================

export interface ParseSubsidyNumberOptions {
  allowNegative?: boolean;
  maxKrw?: number;
  defaultKrw?: number;
}

/**
 * Robust Korean currency and subsidy number parser.
 * Handles:
 * - Direct numbers, NaN, Infinity, -Infinity.
 * - Thousands commas: "6,500,000", "55,000,000원".
 * - Korean units:
 *   - "만원", "만 원", "만" (x10,000): "650만원" -> 6,500,000, "5,500만" -> 55,000,000.
 *   - "억원", "억 원", "억" (x100,000,000): "2.1억" -> 210,000,000.
 *   - Compound: "1억 2,000만 원" -> 120,000,000.
 *   - "천만원" (x10,000,000): "5천만원" -> 50,000,000.
 *   - "천원" (x1,000): "5천원" -> 5,000.
 * - Whitespace, currency symbols ("₩", "KRW", "원").
 * - Missing properties / null / undefined / unparseable text -> defaultKrw (default: 0).
 * - Caps at maxKrw (default: 10,000,000,000 KRW).
 */
export function parseSubsidyNumber(
  input: unknown,
  options?: ParseSubsidyNumberOptions
): number {
  const fallback = typeof options?.defaultKrw === 'number' && Number.isFinite(options.defaultKrw)
    ? options.defaultKrw
    : 0;
  const maxCap = typeof options?.maxKrw === 'number' && Number.isFinite(options.maxKrw)
    ? options.maxKrw
    : 10_000_000_000;
  const allowNeg = Boolean(options?.allowNegative);

  if (input === null || input === undefined) {
    return fallback;
  }

  if (typeof input === 'number') {
    if (Number.isNaN(input)) {
      return fallback;
    }
    if (input === Infinity) {
      return maxCap;
    }
    if (input === -Infinity) {
      return allowNeg ? -maxCap : 0;
    }
    if (!Number.isFinite(input)) {
      return fallback;
    }
    if (!allowNeg && input < 0) {
      return 0;
    }
    return Math.min(maxCap, Math.round(input));
  }

  if (typeof input !== 'string') {
    return fallback;
  }

  const raw = input.trim();
  if (!raw) {
    return fallback;
  }

  const isNeg = /^\s*-/.test(raw);
  const clean = raw.replace(/^[+\-\s]+/, '');

  let total = 0;
  let matchedKoreanUnit = false;

  // 1. Match '억'
  const eokMatch = clean.match(/([\d.,]+)\s*억/);
  if (eokMatch) {
    const val = parseFloat(eokMatch[1].replace(/,/g, ''));
    if (Number.isFinite(val)) {
      total += val * 100_000_000;
      matchedKoreanUnit = true;
    }
  }

  // 2. Match '천만' (e.g. 5천만원)
  const cheonManMatch = clean.match(/([\d.,]+)\s*천\s*만/);
  if (cheonManMatch) {
    const val = parseFloat(cheonManMatch[1].replace(/,/g, ''));
    if (Number.isFinite(val)) {
      total += val * 10_000_000;
      matchedKoreanUnit = true;
    }
  } else {
    // 3. Match '만' (e.g. 650만원, 5,500만 원, 650만)
    const manMatch = clean.match(/([\d.,]+)\s*만/);
    if (manMatch) {
      const val = parseFloat(manMatch[1].replace(/,/g, ''));
      if (Number.isFinite(val)) {
        total += val * 10_000;
        matchedKoreanUnit = true;
      }
    }
  }

  // 4. Match standalone '천' (not followed by '만', e.g. 5천원)
  const cheonMatch = clean.match(/([\d.,]+)\s*천(?!\s*만)/);
  if (cheonMatch) {
    const val = parseFloat(cheonMatch[1].replace(/,/g, ''));
    if (Number.isFinite(val)) {
      total += val * 1_000;
      matchedKoreanUnit = true;
    }
  }

  // 5. If no Korean unit was matched, parse as standard raw number with commas/currency symbols
  if (!matchedKoreanUnit) {
    const stripped = clean.replace(/[,원₩\sKRWkrw]/g, '');
    const val = parseFloat(stripped);
    if (Number.isFinite(val)) {
      total = val;
    } else {
      return fallback;
    }
  }

  let finalVal = Math.round(total);
  if (isNeg) {
    finalVal = -finalVal;
  }

  if (!allowNeg && finalVal < 0) {
    return 0;
  }

  return Math.min(maxCap, finalVal);
}

export interface ParsedModelSubsidy {
  modelId: string;
  nameKo: string;
  manufacturer: string;
  basePriceKrw: number;
  nationalSubsidyKrw: number;
  priceSubsidyRatio: number;
}

/**
 * Safely parses model subsidy fields guarding against missing properties and malformed strings.
 */
export function parseModelSubsidy(model: unknown): ParsedModelSubsidy {
  const m = (model && typeof model === 'object') ? (model as Record<string, unknown>) : {};
  const modelId = typeof m.model_id === 'string' ? m.model_id : (typeof m.id === 'string' ? m.id : 'unknown-model');
  const nameKo = typeof m.name_ko === 'string' ? m.name_ko : (typeof m.name === 'string' ? m.name : '기본 모델');
  const manufacturer = typeof m.manufacturer === 'string' ? m.manufacturer : (typeof m.brand === 'string' ? m.brand : '기타');
  const basePriceKrw = parseSubsidyNumber(m.base_price_krw ?? m.basePriceKrw, { defaultKrw: 54_100_000 });
  const nationalSubsidyKrw = parseSubsidyNumber(m.national_subsidy_krw ?? m.nationalSubsidyKrw, { defaultKrw: 0 });

  const rawRatio = m.price_subsidy_ratio ?? m.priceSubsidyRatio;
  let priceSubsidyRatio = 1.0;
  if (typeof rawRatio === 'number' && Number.isFinite(rawRatio) && rawRatio >= 0) {
    priceSubsidyRatio = Math.min(1.0, rawRatio);
  } else {
    priceSubsidyRatio = getPriceSubsidyRatio(basePriceKrw);
  }

  return {
    modelId,
    nameKo,
    manufacturer,
    basePriceKrw,
    nationalSubsidyKrw,
    priceSubsidyRatio,
  };
}

export interface ParsedCategoryMetrics {
  announcedUnits: number;
  appliedUnits: number;
  deliveredUnits: number;
  remainingUnits: number;
  depletionRate: number;
  deliveryRate: number;
  status: AlertSeverity;
  maxLocalSubsidyKrw: number;
  maxTotalSubsidyKrw: number;
}

/**
 * Safely parses category metrics, guarding against missing properties, string values, and division by zero.
 */
export function parseCategoryMetrics(category: unknown): ParsedCategoryMetrics {
  const c = (category && typeof category === 'object') ? (category as Record<string, unknown>) : {};
  const announcedUnits = Math.max(0, parseSubsidyNumber(c.announced_units ?? c.announcedUnits, { defaultKrw: 0 }));
  const appliedUnits = Math.max(0, parseSubsidyNumber(c.applied_units ?? c.appliedUnits, { defaultKrw: 0 }));
  const deliveredUnits = Math.max(0, parseSubsidyNumber(c.delivered_units ?? c.deliveredUnits, { defaultKrw: 0 }));

  const rawRemaining = c.remaining_units ?? c.remainingUnits;
  const remainingUnits = typeof rawRemaining === 'number' && Number.isFinite(rawRemaining) && rawRemaining >= 0
    ? Math.floor(rawRemaining)
    : calculateRemainingUnits(appliedUnits, announcedUnits);

  const rawRate = c.depletion_rate ?? c.depletionRate;
  const depletionRate = typeof rawRate === 'number' && Number.isFinite(rawRate) && rawRate >= 0
    ? Math.round(rawRate * 10) / 10
    : calculateDepletionRate(appliedUnits, announcedUnits);

  const rawDelRate = c.delivery_rate ?? c.deliveryRate;
  const deliveryRate = typeof rawDelRate === 'number' && Number.isFinite(rawDelRate) && rawDelRate >= 0
    ? Math.round(rawDelRate * 10) / 10
    : calculateDeliveryRate(deliveredUnits, announcedUnits);

  const maxLocalSubsidyKrw = Math.max(0, parseSubsidyNumber(c.max_local_subsidy_krw ?? c.maxLocalSubsidyKrw, { defaultKrw: 0 }));
  const maxTotalSubsidyKrw = Math.max(0, parseSubsidyNumber(c.max_total_subsidy_krw ?? c.maxTotalSubsidyKrw, { defaultKrw: 0 }));

  let status: AlertSeverity = 'HEALTHY';
  if (typeof c.status === 'string' && ['HEALTHY', 'CAUTION', 'WARNING', 'CRITICAL', 'DEPLETED'].includes(c.status)) {
    status = c.status as AlertSeverity;
  } else {
    if (depletionRate >= 100.0) status = 'DEPLETED';
    else if (depletionRate >= 95.0) status = 'CRITICAL';
    else if (depletionRate >= 80.0) status = 'WARNING';
    else if (depletionRate >= 60.0) status = 'CAUTION';
    else status = 'HEALTHY';
  }

  return {
    announcedUnits,
    appliedUnits,
    deliveredUnits,
    remainingUnits,
    depletionRate,
    deliveryRate,
    status,
    maxLocalSubsidyKrw,
    maxTotalSubsidyKrw,
  };
}

// ==========================================
// 4.3 SAFE SORTING & RANKING UTILITIES (Zero-NaN / Zero-Infinity)
// ==========================================

/**
 * Universal safe number comparator for Array.prototype.sort.
 * Guarantees:
 * - NEVER produces NaN.
 * - Handles +Infinity and -Infinity deterministically without producing NaN on subtraction.
 * - Places NaN, null, and undefined deterministically at the end.
 * - Returns 0 for equal values (transitive and deterministic).
 */
export function safeCompareNumbers(
  a: number | null | undefined,
  b: number | null | undefined,
  direction: 'asc' | 'desc' = 'asc'
): number {
  const isFiniteA = typeof a === 'number' && Number.isFinite(a);
  const isFiniteB = typeof b === 'number' && Number.isFinite(b);

  if (isFiniteA && isFiniteB) {
    if (a === b) return 0;
    return direction === 'asc' ? (a as number) - (b as number) : (b as number) - (a as number);
  }

  // Handle infinities
  const isInfA = a === Infinity;
  const isNegInfA = a === -Infinity;
  const isInfB = b === Infinity;
  const isNegInfB = b === -Infinity;

  if (isInfA && isInfB) return 0;
  if (isNegInfA && isNegInfB) return 0;

  if (isInfA) return direction === 'asc' ? 1 : -1;
  if (isInfB) return direction === 'asc' ? -1 : 1;
  if (isNegInfA) return direction === 'asc' ? -1 : 1;
  if (isNegInfB) return direction === 'asc' ? 1 : -1;

  // Both are invalid (NaN, null, undefined)
  if (!isFiniteA && !isFiniteB) return 0;

  // Invalid values pushed to the end
  return !isFiniteA ? 1 : -1;
}

export type RegionSortOption =
  | 'DEPLETION_DESC'
  | 'DEPLETION_ASC'
  | 'REMAINING_ASC'
  | 'REMAINING_DESC'
  | 'LOCAL_SUBSIDY_DESC'
  | 'LOCAL_SUBSIDY_ASC'
  | 'NAME_ASC'
  | 'NAME_DESC';

/**
 * Deterministic, NaN-safe region comparator.
 */
export function compareRegions(
  a: RegionEntry | null | undefined,
  b: RegionEntry | null | undefined,
  sortOption: RegionSortOption = 'DEPLETION_DESC',
  categoryKey: 'passenger' | 'commercial' | 'bus' = 'passenger'
): number {
  if (!a && !b) return 0;
  if (!a) return 1;
  if (!b) return -1;

  const catA = a.categories?.[categoryKey];
  const catB = b.categories?.[categoryKey];

  let cmp = 0;
  switch (sortOption) {
    case 'DEPLETION_DESC': {
      const rateA = typeof catA?.depletion_rate === 'number' && !Number.isNaN(catA.depletion_rate)
        ? catA.depletion_rate
        : calculateDepletionRate(catA?.applied_units, catA?.announced_units);
      const rateB = typeof catB?.depletion_rate === 'number' && !Number.isNaN(catB.depletion_rate)
        ? catB.depletion_rate
        : calculateDepletionRate(catB?.applied_units, catB?.announced_units);
      cmp = safeCompareNumbers(rateA, rateB, 'desc');
      break;
    }
    case 'DEPLETION_ASC': {
      const rateA = typeof catA?.depletion_rate === 'number' && !Number.isNaN(catA.depletion_rate)
        ? catA.depletion_rate
        : calculateDepletionRate(catA?.applied_units, catA?.announced_units);
      const rateB = typeof catB?.depletion_rate === 'number' && !Number.isNaN(catB.depletion_rate)
        ? catB.depletion_rate
        : calculateDepletionRate(catB?.applied_units, catB?.announced_units);
      cmp = safeCompareNumbers(rateA, rateB, 'asc');
      break;
    }
    case 'REMAINING_ASC': {
      const remA = typeof catA?.remaining_units === 'number' && !Number.isNaN(catA.remaining_units)
        ? catA.remaining_units
        : calculateRemainingUnits(catA?.applied_units, catA?.announced_units);
      const remB = typeof catB?.remaining_units === 'number' && !Number.isNaN(catB.remaining_units)
        ? catB.remaining_units
        : calculateRemainingUnits(catB?.applied_units, catB?.announced_units);
      cmp = safeCompareNumbers(remA, remB, 'asc');
      break;
    }
    case 'REMAINING_DESC': {
      const remA = typeof catA?.remaining_units === 'number' && !Number.isNaN(catA.remaining_units)
        ? catA.remaining_units
        : calculateRemainingUnits(catA?.applied_units, catA?.announced_units);
      const remB = typeof catB?.remaining_units === 'number' && !Number.isNaN(catB.remaining_units)
        ? catB.remaining_units
        : calculateRemainingUnits(catB?.applied_units, catB?.announced_units);
      cmp = safeCompareNumbers(remA, remB, 'desc');
      break;
    }
    case 'LOCAL_SUBSIDY_DESC': {
      const subA = parseSubsidyNumber(catA?.max_local_subsidy_krw, { defaultKrw: 0 });
      const subB = parseSubsidyNumber(catB?.max_local_subsidy_krw, { defaultKrw: 0 });
      cmp = safeCompareNumbers(subA, subB, 'desc');
      break;
    }
    case 'LOCAL_SUBSIDY_ASC': {
      const subA = parseSubsidyNumber(catA?.max_local_subsidy_krw, { defaultKrw: 0 });
      const subB = parseSubsidyNumber(catB?.max_local_subsidy_krw, { defaultKrw: 0 });
      cmp = safeCompareNumbers(subA, subB, 'asc');
      break;
    }
    case 'NAME_ASC': {
      cmp = (a.name_ko || '').localeCompare(b.name_ko || '', 'ko');
      break;
    }
    case 'NAME_DESC': {
      cmp = (b.name_ko || '').localeCompare(a.name_ko || '', 'ko');
      break;
    }
    default:
      cmp = 0;
  }

  if (cmp !== 0) return cmp;
  // Deterministic tie-breaker by name then region_id
  const nameTie = (a.name_ko || '').localeCompare(b.name_ko || '', 'ko');
  if (nameTie !== 0) return nameTie;
  return (a.region_id || '').localeCompare(b.region_id || '');
}

/**
 * Non-mutating pure function sorting regions array with guaranteed NaN/Infinity safety.
 */
export function sortRegions<T extends RegionEntry>(
  regions: readonly T[] | null | undefined,
  sortOption: RegionSortOption = 'DEPLETION_DESC',
  categoryKey: 'passenger' | 'commercial' | 'bus' = 'passenger'
): T[] {
  if (!Array.isArray(regions)) return [];
  const valid = regions.filter((r): r is T => Boolean(r && typeof r === 'object'));
  return [...valid].sort((a, b) => compareRegions(a, b, sortOption, categoryKey));
}

export interface RankedRegionEntry {
  rank: number;
  regionId: string;
  nameKo: string;
  depletionRate: number;
  remainingUnits: number;
  status: AlertSeverity;
  region: RegionEntry;
}

/**
 * Ranks regions by depletion rate descending (1-based standard competition ranking).
 * Handles ties identically and guards against NaN / Infinity.
 */
export function rankRegionsByDepletion(
  regions: readonly RegionEntry[] | null | undefined,
  categoryKey: 'passenger' | 'commercial' | 'bus' = 'passenger'
): RankedRegionEntry[] {
  if (!Array.isArray(regions)) return [];
  const sorted = sortRegions(regions, 'DEPLETION_DESC', categoryKey);

  const ranked: RankedRegionEntry[] = [];
  let currentRank = 1;

  for (let i = 0; i < sorted.length; i++) {
    const r = sorted[i];
    const cat = r.categories?.[categoryKey];
    const rate = typeof cat?.depletion_rate === 'number' && !Number.isNaN(cat.depletion_rate)
      ? cat.depletion_rate
      : calculateDepletionRate(cat?.applied_units, cat?.announced_units);
    const rem = typeof cat?.remaining_units === 'number' && !Number.isNaN(cat.remaining_units)
      ? cat.remaining_units
      : calculateRemainingUnits(cat?.applied_units, cat?.announced_units);
    const status: AlertSeverity = cat?.status || (rate >= 100 ? 'DEPLETED' : rate >= 95 ? 'CRITICAL' : rate >= 80 ? 'WARNING' : rate >= 60 ? 'CAUTION' : 'HEALTHY');

    if (i > 0) {
      const prev = ranked[i - 1];
      if (rate === prev.depletionRate) {
        currentRank = prev.rank;
      } else {
        currentRank = i + 1;
      }
    }

    ranked.push({
      rank: currentRank,
      regionId: r.region_id || '',
      nameKo: r.name_ko || '',
      depletionRate: rate,
      remainingUnits: rem,
      status,
      region: r,
    });
  }

  return ranked;
}

export type ModelSortOption = 'PRICE_ASC' | 'PRICE_DESC' | 'SUBSIDY_DESC' | 'RANGE_DESC' | 'NAME_ASC';

/**
 * Deterministic, NaN-safe vehicle model comparator.
 */
export function compareModels(
  a: PopularModelEntry | null | undefined,
  b: PopularModelEntry | null | undefined,
  sortOption: ModelSortOption = 'PRICE_ASC'
): number {
  if (!a && !b) return 0;
  if (!a) return 1;
  if (!b) return -1;

  let cmp = 0;
  switch (sortOption) {
    case 'PRICE_ASC': {
      const priceA = parseSubsidyNumber(a.base_price_krw, { defaultKrw: 54_100_000 });
      const priceB = parseSubsidyNumber(b.base_price_krw, { defaultKrw: 54_100_000 });
      cmp = safeCompareNumbers(priceA, priceB, 'asc');
      break;
    }
    case 'PRICE_DESC': {
      const priceA = parseSubsidyNumber(a.base_price_krw, { defaultKrw: 54_100_000 });
      const priceB = parseSubsidyNumber(b.base_price_krw, { defaultKrw: 54_100_000 });
      cmp = safeCompareNumbers(priceA, priceB, 'desc');
      break;
    }
    case 'SUBSIDY_DESC': {
      const subA = parseSubsidyNumber(a.national_subsidy_krw, { defaultKrw: 0 });
      const subB = parseSubsidyNumber(b.national_subsidy_krw, { defaultKrw: 0 });
      cmp = safeCompareNumbers(subA, subB, 'desc');
      break;
    }
    case 'RANGE_DESC': {
      const rangeA = typeof a.rated_range_km === 'number' && Number.isFinite(a.rated_range_km) ? a.rated_range_km : 0;
      const rangeB = typeof b.rated_range_km === 'number' && Number.isFinite(b.rated_range_km) ? b.rated_range_km : 0;
      cmp = safeCompareNumbers(rangeA, rangeB, 'desc');
      break;
    }
    case 'NAME_ASC': {
      cmp = (a.name_ko || '').localeCompare(b.name_ko || '', 'ko');
      break;
    }
    default:
      cmp = 0;
  }

  if (cmp !== 0) return cmp;
  return (a.model_id || '').localeCompare(b.model_id || '');
}

/**
 * Non-mutating pure function sorting vehicle models array with guaranteed NaN/Infinity safety.
 */
export function sortModels<T extends PopularModelEntry>(
  models: readonly T[] | null | undefined,
  sortOption: ModelSortOption = 'PRICE_ASC'
): T[] {
  if (!Array.isArray(models)) return [];
  const valid = models.filter((m): m is T => Boolean(m && typeof m === 'object'));
  return [...valid].sort((a, b) => compareModels(a, b, sortOption));
}

// ==========================================
// 5. PURE SUBSIDY CALCULATION ENGINE
// ==========================================

/**
 * Computes net subsidy, matching municipal grant, statutory price cap reduction,
 * and out-of-pocket net vehicle purchase price from model and region parameters.
 */
export function calculateNetSubsidyPure(
  model: PopularModelEntry,
  region: RegionEntry,
  customMsrp?: number | string | null,
  options?: SubsidyCalculatorOptions
): SubsidyCalculationResult {
  const safeModel =
    model && typeof model === 'object'
      ? model
      : ({
          model_id: 'unknown-model',
          name_ko: '기본 모델',
          base_price_krw: 54_100_000,
          national_subsidy_krw: 0,
          price_subsidy_ratio: 1.0,
        } as PopularModelEntry);

  const safeRegion =
    region && typeof region === 'object'
      ? region
      : ({
          region_id: 'unknown-region',
          name_ko: '전국 평균',
          categories: { passenger: { max_local_subsidy_krw: 0, depletion_rate: 0, remaining_units: 0 } },
        } as unknown as RegionEntry);

  const passengerCategory = safeRegion.categories?.passenger;

  // 1. Resolve MSRP and statutory price-cap ratio
  const safeModelPrice = parseSubsidyNumber(safeModel?.base_price_krw, {
    defaultKrw: 54_100_000,
    maxKrw: 10_000_000_000,
  });

  let activeMsrp: number;
  if (customMsrp === Infinity) {
    activeMsrp = 10_000_000_000;
  } else if (customMsrp !== undefined && customMsrp !== null) {
    const parsed = parseSubsidyNumber(customMsrp, { maxKrw: 10_000_000_000 });
    activeMsrp = parsed > 0 ? parsed : safeModelPrice;
  } else {
    activeMsrp = safeModelPrice;
  }

  const ratio = getPriceSubsidyRatio(activeMsrp);

  let priceCapTierText = '100% 전액 지원 (5,500만 원 이하)';
  if (ratio === 0.5) {
    priceCapTierText = '50% 감액 지원 (5,500만~8,500만 원 구간)';
  } else if (ratio === 0.0) {
    priceCapTierText = '보조금 지급 대상 제외 (8,500만 원 초과)';
  }

  // 2. Calculate National Subsidy
  const validNationalSubsidy = parseSubsidyNumber(safeModel.national_subsidy_krw, { defaultKrw: 0 });
  let nationalSubsidyKrw = 0;
  if (ratio > 0) {
    const parsedCustom = customMsrp !== undefined && customMsrp !== null ? parseSubsidyNumber(customMsrp) : 0;
    if (parsedCustom > 0) {
      const baseRatio = Number.isFinite(safeModel.price_subsidy_ratio) && safeModel.price_subsidy_ratio > 0
        ? safeModel.price_subsidy_ratio
        : 1.0;
      const unscaledNational = Math.round(validNationalSubsidy / baseRatio);
      nationalSubsidyKrw = Math.min(6_500_000, Math.round(unscaledNational * ratio));
    } else {
      nationalSubsidyKrw = validNationalSubsidy;
    }
  }

  // 3. Additional Grants / Subsidies
  let additionalGrantsKrw = 0;
  if (nationalSubsidyKrw > 0 && options) {
    if (options.isYouthFirstTimeBuyer) {
      additionalGrantsKrw += Math.round(nationalSubsidyKrw * 0.2);
    }
    if (options.isSmallBusinessOrTaxi) {
      additionalGrantsKrw += Math.round(nationalSubsidyKrw * 0.3);
    }
    if (options.isMultiChildFamily) {
      additionalGrantsKrw += Math.round(nationalSubsidyKrw * 0.1);
    }
    if (options.isOldDieselScrappage) {
      additionalGrantsKrw += 1_000_000;
    }
  }

  // 4. Calculate Local Municipal Matching Subsidy
  // Formula: S_local = S_local_max * (S_nat / 6,500,000)
  const maxLocal = parseSubsidyNumber(passengerCategory?.max_local_subsidy_krw, { defaultKrw: 0 });
  let localSubsidyKrw = 0;
  if (nationalSubsidyKrw > 0 && maxLocal > 0) {
    const calculated = Math.round(maxLocal * (nationalSubsidyKrw / 6_500_000));
    localSubsidyKrw = Math.min(maxLocal, Math.round(calculated / 10_000) * 10_000);
  }

  // 5. Total & Net Out-of-pocket Purchase Price
  const totalSubsidyKrw = nationalSubsidyKrw + localSubsidyKrw + additionalGrantsKrw;
  const rawNetPrice = activeMsrp - totalSubsidyKrw;
  const netPurchasePriceKrw = Number.isFinite(rawNetPrice) ? Math.max(0, rawNetPrice) : 0;

  // 6. Depletion Risk & Warning Analysis
  const catAnnounced = parseSubsidyNumber(passengerCategory?.announced_units, { defaultKrw: 0 });
  const catApplied = parseSubsidyNumber(passengerCategory?.applied_units, { defaultKrw: 0 });

  const depletionRate = typeof passengerCategory?.depletion_rate === 'number' && Number.isFinite(passengerCategory.depletion_rate)
    ? passengerCategory.depletion_rate
    : calculateDepletionRate(catApplied, catAnnounced);

  const isHighDepletionRisk = depletionRate >= 80.0;
  const depletionStatus: AlertSeverity = passengerCategory?.status || (depletionRate >= 100 ? 'DEPLETED' : depletionRate >= 95 ? 'CRITICAL' : depletionRate >= 80 ? 'WARNING' : depletionRate >= 60 ? 'CAUTION' : 'HEALTHY');
  const remainingUnits = typeof passengerCategory?.remaining_units === 'number' && Number.isFinite(passengerCategory.remaining_units)
    ? passengerCategory.remaining_units
    : calculateRemainingUnits(catApplied, catAnnounced);

  let warningNotice: string | undefined;
  if (depletionRate >= 95.0) {
    warningNotice = `🚨 ${safeRegion.name_ko}의 승용 보조금 소진율이 ${depletionRate}%로 선착순 마감 직전입니다! 즉시 출고 가능 실재고 매칭이 필요합니다.`;
  } else if (depletionRate >= 80.0) {
    warningNotice = `⚠️ ${safeRegion.name_ko}의 승용 보조금 소진율이 ${depletionRate}%에 달해 조기 마감 위험이 높습니다.`;
  } else {
    warningNotice = `✅ ${safeRegion.name_ko}의 보조금 잔여량이 비교적 여유롭습니다 (${remainingUnits.toLocaleString()}대 잔여).`;
  }

  return {
    modelId: safeModel.model_id,
    modelName: safeModel.name_ko,
    manufacturer: safeModel.manufacturer,
    batteryType: safeModel.battery_type,
    batteryCapacityKwh: safeModel.battery_capacity_kwh,
    ratedRangeKm: safeModel.rated_range_km,
    regionId: safeRegion.region_id,
    regionName: safeRegion.name_ko,
    msrpKrw: activeMsrp,
    priceSubsidyRatio: ratio,
    nationalSubsidyKrw,
    localSubsidyKrw,
    additionalGrantsKrw,
    totalSubsidyKrw,
    netPurchasePriceKrw,
    isHighDepletionRisk,
    depletionRate,
    depletionStatus,
    residencyRequirementDays: safeRegion.residency_requirement_days,
    warningNotice,
    priceCapTierText,
  };
}

// ==========================================
// 6. STATISTICAL AGGREGATION UTILITIES
// ==========================================

export interface SubsidyStatistics {
  totalAnnouncedUnits: number;
  totalAppliedUnits: number;
  totalDeliveredUnits: number;
  totalRemainingUnits: number;
  nationalDepletionRate: number;
  deliveryRate: number;
  budgetTotalBillionKrw: number;
  budgetDisbursedBillionKrw: number;
  budgetExecutionRatePct: number;
  criticalRegionsCount: number;
  criticalRegions: Array<{ regionId: string; nameKo: string; depletionRate: number; remainingUnits: number }>;
  warningRegionsCount: number;
  cautionRegionsCount: number;
  healthyRegionsCount: number;
  categoryBreakdown: {
    passenger: { announced: number; applied: number; remaining: number; rate: number };
    commercial: { announced: number; applied: number; remaining: number; rate: number };
    bus: { announced: number; applied: number; remaining: number; rate: number };
  };
}

/**
 * Pure calculation of nationwide subsidy statistics from an EVSubsidyDataset.
 * Protects against division by zero and NaN/Infinity values.
 */
export function calculateSubsidyStatistics(dataset?: Partial<EVSubsidyDataset> | null): SubsidyStatistics {
  const summary = dataset?.nationwide_summary;
  const regions = Array.isArray(dataset?.regions) ? dataset.regions : [];

  const announced = parseSubsidyNumber(summary?.total_announced_units, { defaultKrw: 0 });
  const applied = parseSubsidyNumber(summary?.total_applied_units, { defaultKrw: 0 });
  const delivered = parseSubsidyNumber(summary?.total_delivered_units, { defaultKrw: 0 });
  const remaining = typeof summary?.total_remaining_units === 'number' && Number.isFinite(summary.total_remaining_units)
    ? summary.total_remaining_units
    : calculateRemainingUnits(applied, announced);

  const depletionRate = typeof summary?.nationwide_depletion_rate === 'number' && Number.isFinite(summary.nationwide_depletion_rate)
    ? summary.nationwide_depletion_rate
    : calculateDepletionRate(applied, announced);

  const deliveryRate = calculateDeliveryRate(delivered, announced);

  const budgetTotal = typeof summary?.total_budget_billion_krw === 'number' && Number.isFinite(summary.total_budget_billion_krw)
    ? Math.max(0, summary.total_budget_billion_krw)
    : 0;
  const budgetDisbursed = typeof summary?.disbursed_budget_billion_krw === 'number' && Number.isFinite(summary.disbursed_budget_billion_krw)
    ? Math.max(0, summary.disbursed_budget_billion_krw)
    : 0;
  const budgetExecutionRatePct = budgetTotal > 0 && budgetDisbursed >= 0
    ? Math.round((budgetDisbursed / budgetTotal) * 1000) / 10
    : 0;

  // Extract regions >= 95%
  const criticalList: Array<{ regionId: string; nameKo: string; depletionRate: number; remainingUnits: number }> = [];
  let criticalCount = 0;
  let warningCount = 0;
  let cautionCount = 0;
  let healthyCount = 0;

  for (const r of regions) {
    if (!r || typeof r !== 'object') continue;
    const rate = typeof r.overall_depletion_rate === 'number' && !Number.isNaN(r.overall_depletion_rate) ? r.overall_depletion_rate : 0;
    const rem = typeof r.categories?.passenger?.remaining_units === 'number' && !Number.isNaN(r.categories.passenger.remaining_units) ? r.categories.passenger.remaining_units : 0;
    if (rate >= 95.0) {
      criticalCount++;
      criticalList.push({
        regionId: r.region_id || '',
        nameKo: r.name_ko || '',
        depletionRate: rate,
        remainingUnits: rem,
      });
    } else if (rate >= 80.0) {
      warningCount++;
    } else if (rate >= 60.0) {
      cautionCount++;
    } else {
      healthyCount++;
    }
  }

  // Sort critical regions descending by depletion rate with full NaN/Infinity guard
  criticalList.sort((a, b) => {
    const cmp = safeCompareNumbers(b.depletionRate, a.depletionRate, 'asc');
    if (cmp !== 0) return cmp;
    return (a.nameKo || '').localeCompare(b.nameKo || '', 'ko');
  });

  const cat = summary?.category_totals;

  return {
    totalAnnouncedUnits: announced,
    totalAppliedUnits: applied,
    totalDeliveredUnits: delivered,
    totalRemainingUnits: remaining,
    nationalDepletionRate: depletionRate,
    deliveryRate,
    budgetTotalBillionKrw: budgetTotal,
    budgetDisbursedBillionKrw: budgetDisbursed,
    budgetExecutionRatePct,
    criticalRegionsCount: criticalCount,
    criticalRegions: criticalList,
    warningRegionsCount: warningCount,
    cautionRegionsCount: cautionCount,
    healthyRegionsCount: healthyCount,
    categoryBreakdown: {
      passenger: {
        announced: parseSubsidyNumber(cat?.passenger?.announced_units, { defaultKrw: 0 }),
        applied: parseSubsidyNumber(cat?.passenger?.applied_units, { defaultKrw: 0 }),
        remaining: typeof cat?.passenger?.remaining_units === 'number' && Number.isFinite(cat.passenger.remaining_units)
          ? cat.passenger.remaining_units
          : calculateRemainingUnits(cat?.passenger?.applied_units, cat?.passenger?.announced_units),
        rate: typeof cat?.passenger?.depletion_rate === 'number' && Number.isFinite(cat.passenger.depletion_rate)
          ? cat.passenger.depletion_rate
          : calculateDepletionRate(cat?.passenger?.applied_units, cat?.passenger?.announced_units),
      },
      commercial: {
        announced: parseSubsidyNumber(cat?.commercial?.announced_units, { defaultKrw: 0 }),
        applied: parseSubsidyNumber(cat?.commercial?.applied_units, { defaultKrw: 0 }),
        remaining: typeof cat?.commercial?.remaining_units === 'number' && Number.isFinite(cat.commercial.remaining_units)
          ? cat.commercial.remaining_units
          : calculateRemainingUnits(cat?.commercial?.applied_units, cat?.commercial?.announced_units),
        rate: typeof cat?.commercial?.depletion_rate === 'number' && Number.isFinite(cat.commercial.depletion_rate)
          ? cat.commercial.depletion_rate
          : calculateDepletionRate(cat?.commercial?.applied_units, cat?.commercial?.announced_units),
      },
      bus: {
        announced: parseSubsidyNumber(cat?.bus?.announced_units, { defaultKrw: 0 }),
        applied: parseSubsidyNumber(cat?.bus?.applied_units, { defaultKrw: 0 }),
        remaining: typeof cat?.bus?.remaining_units === 'number' && Number.isFinite(cat.bus.remaining_units)
          ? cat.bus.remaining_units
          : calculateRemainingUnits(cat?.bus?.applied_units, cat?.bus?.announced_units),
        rate: typeof cat?.bus?.depletion_rate === 'number' && Number.isFinite(cat.bus.depletion_rate)
          ? cat.bus.depletion_rate
          : calculateDepletionRate(cat?.bus?.applied_units, cat?.bus?.announced_units),
      },
    },
  };
}

// ==========================================
// 7. FORMATTING & PRESENTATION HELPERS
// ==========================================

export function formatCurrencyKrw(krw: number): string {
  if (!Number.isFinite(krw) || krw <= 0) return '0원';
  return `${Math.round(krw).toLocaleString()}원`;
}

export function formatManwon(krw: number): string {
  if (!Number.isFinite(krw) || krw <= 0) return '0만 원';
  const manwon = Math.round(krw / 10_000);
  return `${manwon.toLocaleString()}만 원`;
}

export function formatBillionKrw(billion: number): string {
  if (!Number.isFinite(billion) || billion <= 0) return '0억 원';
  return `${billion.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}억 원`;
}

export function formatDepletionRate(rate: number): string {
  if (!Number.isFinite(rate)) return '0.0%';
  const safeRate = Math.max(0, rate);
  return `${safeRate.toFixed(1)}%`;
}

export function getDepletionBadgeStyle(rate: number): {
  severity: AlertSeverity;
  colorHex: string;
  badgeClass: string;
  labelKo: string;
} {
  const safeRate = Number.isFinite(rate) ? rate : 0.0;
  if (safeRate >= 100.0) {
    return {
      severity: 'DEPLETED',
      colorHex: '#6B7280',
      badgeClass: 'bg-slate-800 text-slate-200 border-slate-600',
      labelKo: '마감 (접수 종료)',
    };
  }
  if (safeRate >= 95.0) {
    return {
      severity: 'CRITICAL',
      colorHex: '#EF4444',
      badgeClass: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
      labelKo: '위험 (잔여 극소)',
    };
  }
  if (safeRate >= 80.0) {
    return {
      severity: 'WARNING',
      colorHex: '#F97316',
      badgeClass: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
      labelKo: '경고 (마감 임박)',
    };
  }
  if (safeRate >= 60.0) {
    return {
      severity: 'CAUTION',
      colorHex: '#F59E0B',
      badgeClass: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      labelKo: '주의 (소진 가속)',
    };
  }
  return {
    severity: 'HEALTHY',
    colorHex: '#10B981',
    badgeClass: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    labelKo: '원활 (신청 여유)',
  };
}
