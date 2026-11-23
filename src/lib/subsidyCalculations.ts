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
  RegionTier,
  PopularModelEntry,
  EVSubsidyDataset,
  SubsidyCalculationResult,
  SubsidyCalculatorOptions,
  SubsidyCategoryKey,
  MunicipalityMetrics,
  SubsidyStatistics,
  CriticalRegionInfo,
  CategoryBreakdownMetrics,
  RegionSortOption,
  ModelSortOption,
  RankedRegionEntry,
  HistoricalTrajectoryPoint,
  RegionalGroup,
  RegionalGroupSummary,
} from '../types/subsidy.ts';

export type {
  AlertSeverity,
  AlertThresholdConfig,
  CategoryMetrics,
  RegionEntry,
  RegionTier,
  PopularModelEntry,
  EVSubsidyDataset,
  SubsidyCalculationResult,
  SubsidyCalculatorOptions,
  SubsidyCategoryKey,
  MunicipalityMetrics,
  SubsidyStatistics,
  CriticalRegionInfo,
  CategoryBreakdownMetrics,
  RegionSortOption,
  ModelSortOption,
  RankedRegionEntry,
  HistoricalTrajectoryPoint,
  RegionalGroup,
  RegionalGroupSummary,
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

const REGION_SUFFIX_RE = /(특별시|광역시|특별자치시|특별자치도|도)$/;
const MODEL_CLEAN_RE = /[\s\-_]+/g;
const DATE_ONLY_RE = /^(\d{4})([-/.])(\d{1,2})\2(\d{1,2})(?:\s*(?:Z|UTC|GMT))?$/i;
const US_DATE_ONLY_RE = /^(\d{1,2})([-/.])(\d{1,2})\2(\d{4})(?:\s*(?:Z|UTC|GMT))?$/i;
const DATETIME_RE = /^(\d{4})([-/.])(\d{1,2})\2(\d{1,2})[Tt ](\d{1,2}):(\d{2})(?::(\d{2})(?:\.(\d+))?)?(?:\s*(?:(Z|UTC|GMT)|(?:UTC|GMT)?\s*([+-])(?:(\d{2})(\d{2})|(\d{1,2})(?::(\d{2}))?)))?$/i;
const EXPLICIT_TZ_RE = /(?:(?:GMT|UTC)\s*([+-])(?:(\d{2})(\d{2})|(\d{1,2})(?::(\d{2}))?)|([+-])(\d{2}):?(\d{2})|GMT|UTC|Z)(?:\s*\([^)]*\))?\s*$/i;
const SHORT_NUMERIC_ONLY_RE = /^[+-]?\d{1,3}$/;
const ISO_YEAR_MONTH_RE = /^\d{4}(?:-\d{2})?$/;
const NAMED_MONTH_DAY_RE = /\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b[^0-9]*(\d{1,2})\b|\b(\d{1,2})\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b/i;
const MONTH_NAME_TO_INDEX: Readonly<Record<string, number>> = {
  jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5,
  jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11,
};
const STRICT_NUMBER_RE = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;
const STRICT_UNIT_NUMBER_RE = /^(?:\d+(?:\.\d*)?|\.\d+)$/;
const LEADING_SIGN_RE = /^([+-])?\s*(.*)$/;
const EOK_RE = /([\d.,]+)\s*억/;
const CHEON_MAN_RE = /([\d.,]+)\s*천\s*만/;
const MAN_RE = /([\d.,]+)\s*만/;
const CHEON_RE = /([\d.,]+)\s*천(?!\s*만)/;
const COMMA_RE = /,/g;
const CURRENCY_STRIP_RE = /krw|[,원₩\s]/gi;

const KO_COLLATOR = new Intl.Collator('ko');
const DEFAULT_COLLATOR = new Intl.Collator();

interface RegionLookupIndex {
  length: number;
  first: RegionEntry | undefined;
  last: RegionEntry | undefined;
  idOrIsoMap: Map<string, RegionEntry>;
  exactAnyMap: Map<string, RegionEntry>;
  strippedKoMap: Map<string, RegionEntry>;
}

interface ModelLookupIndex {
  length: number;
  first: PopularModelEntry | undefined;
  last: PopularModelEntry | undefined;
  exactMap: Map<string, PopularModelEntry>;
  cleanExactMap: Map<string, PopularModelEntry>;
}

const REGION_LIST_INDEX_CACHE = new WeakMap<readonly RegionEntry[], RegionLookupIndex>();
const MODEL_LIST_INDEX_CACHE = new WeakMap<readonly PopularModelEntry[], ModelLookupIndex>();

function getRegionLookupIndex(regions: readonly RegionEntry[]): RegionLookupIndex {
  const len = regions.length;
  const first = len > 0 ? regions[0] : undefined;
  const last = len > 0 ? regions[len - 1] : undefined;
  const cached = REGION_LIST_INDEX_CACHE.get(regions);
  if (cached && cached.length === len && cached.first === first && cached.last === last) {
    return cached;
  }

  const idOrIsoMap = new Map<string, RegionEntry>();
  const exactAnyMap = new Map<string, RegionEntry>();
  const strippedKoMap = new Map<string, RegionEntry>();

  for (let i = 0; i < len; i++) {
    const r = regions[i];
    if (!r || typeof r !== 'object' || Array.isArray(r)) continue;
    const rid = typeof r.region_id === 'string' ? r.region_id.trim().toLowerCase() : '';
    const iso = typeof r.iso_code === 'string' ? r.iso_code.trim().toLowerCase() : '';
    const ko = typeof r.name_ko === 'string' ? r.name_ko.trim().toLowerCase() : '';
    const en = typeof r.name_en === 'string' ? r.name_en.trim().toLowerCase() : '';

    if (rid) {
      if (!idOrIsoMap.has(rid)) idOrIsoMap.set(rid, r);
      if (!exactAnyMap.has(rid)) exactAnyMap.set(rid, r);
    }
    if (iso) {
      if (!idOrIsoMap.has(iso)) idOrIsoMap.set(iso, r);
      if (!exactAnyMap.has(iso)) exactAnyMap.set(iso, r);
    }
    if (ko && !exactAnyMap.has(ko)) exactAnyMap.set(ko, r);
    if (en && !exactAnyMap.has(en)) exactAnyMap.set(en, r);
    if (ko) {
      const rStripped = ko.replace(REGION_SUFFIX_RE, '');
      if (rStripped && !strippedKoMap.has(rStripped)) {
        strippedKoMap.set(rStripped, r);
      }
    }
  }

  const index: RegionLookupIndex = {
    length: len,
    first,
    last,
    idOrIsoMap,
    exactAnyMap,
    strippedKoMap,
  };
  REGION_LIST_INDEX_CACHE.set(regions, index);
  return index;
}

function getModelLookupIndex(models: readonly PopularModelEntry[]): ModelLookupIndex {
  const len = models.length;
  const first = len > 0 ? models[0] : undefined;
  const last = len > 0 ? models[len - 1] : undefined;
  const cached = MODEL_LIST_INDEX_CACHE.get(models);
  if (cached && cached.length === len && cached.first === first && cached.last === last) {
    return cached;
  }

  const exactMap = new Map<string, PopularModelEntry>();
  const cleanExactMap = new Map<string, PopularModelEntry>();

  for (let i = 0; i < len; i++) {
    const m = models[i];
    if (!m || typeof m !== 'object' || Array.isArray(m)) continue;
    const idNorm = typeof m.model_id === 'string' ? m.model_id.trim().toLowerCase() : '';
    const koNorm = typeof m.name_ko === 'string' ? m.name_ko.trim().toLowerCase() : '';

    if (idNorm && !exactMap.has(idNorm)) exactMap.set(idNorm, m);
    if (koNorm && !exactMap.has(koNorm)) exactMap.set(koNorm, m);
    if (idNorm) {
      const cleanId = idNorm.replace(MODEL_CLEAN_RE, '');
      if (cleanId && !cleanExactMap.has(cleanId)) cleanExactMap.set(cleanId, m);
    }
    if (koNorm) {
      const cleanKo = koNorm.replace(MODEL_CLEAN_RE, '');
      if (cleanKo && !cleanExactMap.has(cleanKo)) cleanExactMap.set(cleanKo, m);
    }
  }

  const index: ModelLookupIndex = {
    length: len,
    first,
    last,
    exactMap,
    cleanExactMap,
  };
  MODEL_LIST_INDEX_CACHE.set(models, index);
  return index;
}

/**
 * Pure region resolver from a supplied array of regions.
 * Matches by region_id, iso_code, Korean name, English name, canonical alias,
 * or stripped administrative suffix.
 * Uses a WeakMap-cached index for O(1) exact and alias lookups while preserving
 * exact fallback semantics for partial substring queries.
 */
export function getRegionByIdFromList(
  regions: readonly RegionEntry[] | undefined,
  regionId: string
): RegionEntry | undefined {
  if (!regionId || typeof regionId !== 'string' || !Array.isArray(regions)) return undefined;
  const trimmed = regionId.trim();
  const normalized = trimmed.toLowerCase();
  if (!normalized) return undefined;

  const index = getRegionLookupIndex(regions);

  // 1. Direct alias resolution (O(1))
  const rawAlias = Object.prototype.hasOwnProperty.call(REGION_ALIAS_MAP, normalized)
    ? REGION_ALIAS_MAP[normalized]
    : Object.prototype.hasOwnProperty.call(REGION_ALIAS_MAP, trimmed)
    ? REGION_ALIAS_MAP[trimmed]
    : undefined;
  const aliasedId = typeof rawAlias === 'string' ? rawAlias.toLowerCase() : undefined;
  if (aliasedId) {
    const aliasedMatch = index.idOrIsoMap.get(aliasedId);
    if (aliasedMatch) return aliasedMatch;
  }

  // 2. Direct exact match on ID, ISO code, or localized names (O(1))
  const exactMatch = index.exactAnyMap.get(normalized);
  if (exactMatch) return exactMatch;

  // 3. 2-letter provincial abbreviation / stripped administrative suffix match
  const stripped = normalized.replace(REGION_SUFFIX_RE, '');
  if (stripped) {
    const rawStrippedAlias = Object.prototype.hasOwnProperty.call(REGION_ALIAS_MAP, stripped)
      ? REGION_ALIAS_MAP[stripped]
      : undefined;
    const strippedAliasedId = typeof rawStrippedAlias === 'string' ? rawStrippedAlias.toLowerCase() : undefined;
    if (strippedAliasedId) {
      const strippedAliasMatch = index.idOrIsoMap.get(strippedAliasedId);
      if (strippedAliasMatch) return strippedAliasMatch;
    }

    if (stripped.length < 2) {
      return index.strippedKoMap.get(stripped);
    }

    for (let i = 0; i < regions.length; i++) {
      const r = regions[i];
      if (!r || typeof r !== 'object' || Array.isArray(r)) continue;
      if (!r.name_ko || typeof r.name_ko !== 'string') continue;
      const lowerKo = r.name_ko.trim().toLowerCase();
      const rStripped = lowerKo.replace(REGION_SUFFIX_RE, '');
      if (
        (rStripped && rStripped === stripped) ||
        lowerKo.includes(stripped) ||
        (rStripped && stripped.includes(rStripped))
      ) {
        return r;
      }
    }
  }

  return undefined;
}

/**
 * Pure model resolver from a supplied array of popular models.
 * Supports whitespace-, hyphen-, and punctuation-normalized queries.
 * Uses a WeakMap-cached index for O(1) exact and normalized-ID lookups.
 */
export function getModelByIdFromList(
  models: readonly PopularModelEntry[] | undefined,
  modelId: string
): PopularModelEntry | undefined {
  if (!modelId || typeof modelId !== 'string' || !Array.isArray(models)) return undefined;
  const normalized = modelId.trim().toLowerCase();
  if (!normalized) return undefined;

  const index = getModelLookupIndex(models);

  // 1a. Exact match on model_id or name_ko (O(1))
  const exactMatch = index.exactMap.get(normalized);
  if (exactMatch) return exactMatch;

  // 1b. Substring match on name_ko
  for (let i = 0; i < models.length; i++) {
    const m = models[i];
    if (!m || typeof m !== 'object' || Array.isArray(m)) continue;
    if (typeof m.name_ko === 'string' && m.name_ko.toLowerCase().includes(normalized)) {
      return m;
    }
  }

  // 2. Normalize by stripping whitespace, hyphens, and punctuation (O(1) exact)
  const cleanQuery = normalized.replace(MODEL_CLEAN_RE, '');
  if (!cleanQuery) return undefined;

  const cleanExactMatch = index.cleanExactMap.get(cleanQuery);
  if (cleanExactMatch) return cleanExactMatch;

  for (let i = 0; i < models.length; i++) {
    const m = models[i];
    if (!m || typeof m !== 'object' || Array.isArray(m)) continue;
    const cleanId = typeof m.model_id === 'string'
      ? m.model_id.toLowerCase().replace(MODEL_CLEAN_RE, '')
      : '';
    const cleanKo = typeof m.name_ko === 'string'
      ? m.name_ko.toLowerCase().replace(MODEL_CLEAN_RE, '')
      : '';
    if ((cleanId && cleanId.includes(cleanQuery)) || (cleanKo && cleanKo.includes(cleanQuery))) {
      return m;
    }
  }

  return undefined;
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

  const numerator = appliedCount * 100;
  let rate = Number.isFinite(numerator)
    ? numerator / totalQuota
    : (appliedCount / totalQuota) * 100;
  if (rate === Infinity && options?.clamp100) {
    rate = 100.0;
  }
  if (!Number.isFinite(rate) || rate < 0) {
    return 0.0;
  }
  if (options?.clamp100 && rate > 100.0) {
    rate = 100.0;
  }

  const decimals =
    typeof options?.roundDecimals === 'number' &&
    Number.isFinite(options.roundDecimals) &&
    options.roundDecimals >= 0
      ? Math.min(10, Math.floor(options.roundDecimals))
      : 1;
  const factor = Math.pow(10, decimals);

  // Scale numerator before dividing by totalQuota when finite to avoid IEEE-754 truncation (e.g. 14.049999999999999)
  const scaledNumerator = appliedCount * 100 * factor;
  const scaled =
    options?.clamp100 && rate >= 100.0
      ? 100.0 * factor
      : Number.isFinite(scaledNumerator)
      ? scaledNumerator / totalQuota
      : rate * factor;
  const rounded = Number.isFinite(scaled) ? Math.round(scaled) / factor : rate;

  return Number.isFinite(rounded) && rounded > 0 ? rounded : 0.0;
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

/**
 * Calculates waitlisted / over-subscribed EV subsidy units beyond announced quota: max(0, applied - quota).
 */
export function calculateWaitlistUnits(
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
  if (
    appliedCount === null ||
    appliedCount === undefined ||
    !Number.isFinite(appliedCount) ||
    appliedCount <= 0
  ) {
    return 0;
  }
  const safeQuota = Math.floor(totalQuota);
  const safeApplied = Math.floor(appliedCount);
  return Math.max(0, safeApplied - safeQuota);
}

/**
 * Returns true if depletion rate strictly exceeds 100.0% (over-exhaustion / waitlisted status).
 */
export function isDepletionOverExhausted(depletionRate?: number | null): boolean {
  if (depletionRate === null || depletionRate === undefined || !Number.isFinite(depletionRate)) {
    return false;
  }
  return depletionRate > 100.0;
}

/**
 * Calculates pending vehicle deliveries (applied - delivered) clamped at zero.
 */
export function calculatePendingDeliveries(
  appliedCount?: number | null,
  deliveredCount?: number | null
): number {
  if (
    appliedCount === null ||
    appliedCount === undefined ||
    !Number.isFinite(appliedCount) ||
    appliedCount <= 0
  ) {
    return 0;
  }
  const safeApplied = Math.floor(appliedCount);
  const safeDelivered =
    deliveredCount !== null && deliveredCount !== undefined && Number.isFinite(deliveredCount)
      ? Math.max(0, Math.floor(deliveredCount))
      : 0;
  return Math.max(0, safeApplied - safeDelivered);
}

/**
 * Calculates daily subsidy application burn rate velocity (units/day) with zero-division protection.
 */
export function calculateDepletionVelocity(
  appliedStart: number | null | undefined,
  appliedEnd: number | null | undefined,
  days: number | null | undefined
): number {
  if (
    appliedStart === null ||
    appliedStart === undefined ||
    !Number.isFinite(appliedStart) ||
    appliedEnd === null ||
    appliedEnd === undefined ||
    !Number.isFinite(appliedEnd) ||
    days === null ||
    days === undefined ||
    !Number.isFinite(days) ||
    days <= 0
  ) {
    return 0.0;
  }
  const diff = Math.max(0, appliedEnd - appliedStart);
  const raw = Number.isFinite(diff * 100) ? (diff * 100) / days : (diff / days) * 100;
  const velocity = Number.isFinite(raw) ? Math.round(raw) / 100 : 0.0;
  return Number.isFinite(velocity) && velocity > 0 ? velocity : 0.0;
}

/**
 * Predicts number of calendar days until subsidy quota exhaustion based on daily velocity.
 * Returns 0 if remainingUnits <= 0, or null if velocity <= 0 or invalid.
 */
export function predictExhaustionDays(
  remainingUnits: number | null | undefined,
  dailyVelocity: number | null | undefined
): number | null {
  if (
    remainingUnits === null ||
    remainingUnits === undefined ||
    !Number.isFinite(remainingUnits) ||
    dailyVelocity === null ||
    dailyVelocity === undefined ||
    !Number.isFinite(dailyVelocity)
  ) {
    return null;
  }
  if (remainingUnits <= 0) return 0;
  if (dailyVelocity <= 0) return null;
  const days = Math.ceil(remainingUnits / dailyVelocity);
  return Number.isFinite(days) && days >= 0 ? (days === 0 ? 0 : days) : null;
}

function buildValidatedUtcDate(
  year: number,
  month: number,
  day: number,
  hour: number,
  minute: number,
  second: number,
  ms: number
): Date | null {
  if (
    !Number.isInteger(year) ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > 31 ||
    hour < 0 ||
    hour > 23 ||
    minute < 0 ||
    minute > 59 ||
    second < 0 ||
    second > 59 ||
    ms < 0 ||
    ms > 999
  ) {
    return null;
  }
  const dt = new Date(0);
  dt.setUTCFullYear(year, month - 1, day);
  dt.setUTCHours(hour, minute, second, ms);
  if (
    Number.isNaN(dt.getTime()) ||
    dt.getUTCFullYear() !== year ||
    dt.getUTCMonth() !== month - 1 ||
    dt.getUTCDate() !== day
  ) {
    return null;
  }
  return dt;
}

/**
 * Parses a Date or string strictly into a UTC Date, avoiding local-timezone shifts
 * on YYYY/MM/DD, YYYY.MM.DD, or timezone-less YYYY-MM-DD HH:mm:ss(.ffffff) inputs and
 * rejecting silent calendar rollovers (e.g., 2026-02-30 or 2026-02-30T12:00:00Z).
 */
function parseUtcStartDate(startDate?: Date | string | null): Date | null {
  if (startDate === undefined || startDate === null) {
    return new Date();
  }
  if (startDate instanceof Date) {
    return Number.isNaN(startDate.getTime()) ? null : new Date(startDate.getTime());
  }
  if (typeof startDate !== 'string') {
    return null;
  }
  const s = startDate.trim();
  if (!s) {
    return new Date();
  }

  // Date-only formats: YYYY-MM-DD, YYYY/MM/DD, YYYY.MM.DD
  const dateOnly = DATE_ONLY_RE.exec(s);
  if (dateOnly) {
    const year = Number(dateOnly[1]);
    const month = Number(dateOnly[3]);
    const day = Number(dateOnly[4]);
    return buildValidatedUtcDate(year, month, day, 0, 0, 0, 0);
  }

  // US date-only formats: MM-DD-YYYY, MM/DD/YYYY, MM.DD.YYYY
  const usDateOnly = US_DATE_ONLY_RE.exec(s);
  if (usDateOnly) {
    const month = Number(usDateOnly[1]);
    const day = Number(usDateOnly[3]);
    const year = Number(usDateOnly[4]);
    return buildValidatedUtcDate(year, month, day, 0, 0, 0, 0);
  }

  // Datetime formats (naive treated as UTC, or explicit Z / ±HH:MM / ±HHMM)
  const dtMatch = DATETIME_RE.exec(s);
  if (dtMatch) {
    const year = Number(dtMatch[1]);
    const month = Number(dtMatch[3]);
    const day = Number(dtMatch[4]);
    const hour = Number(dtMatch[5]);
    const minute = Number(dtMatch[6]);
    const second = dtMatch[7] ? Number(dtMatch[7]) : 0;
    const ms = dtMatch[8] ? Number(dtMatch[8].slice(0, 3).padEnd(3, '0')) : 0;

    let offsetMinutes = 0;
    if (dtMatch[10]) {
      const tzHour = Number(dtMatch[11] ?? dtMatch[13]);
      const tzMin = Number(dtMatch[12] ?? dtMatch[14] ?? 0);
      if (tzHour > 23 || tzMin > 59) {
        return null;
      }
      offsetMinutes = (dtMatch[10] === '+' ? 1 : -1) * (tzHour * 60 + tzMin);
    }

    const dt = buildValidatedUtcDate(year, month, day, hour, minute, second, ms);
    if (!dt) {
      return null;
    }
    if (offsetMinutes !== 0) {
      dt.setTime(dt.getTime() - offsetMinutes * 60_000);
      if (Number.isNaN(dt.getTime())) {
        return null;
      }
    }
    return dt;
  }

  if (SHORT_NUMERIC_ONLY_RE.test(s)) {
    return null;
  }

  const parsed = new Date(s);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  const tzMatch = EXPLICIT_TZ_RE.exec(s);
  const hasExplicitTz = Boolean(tzMatch);
  let offsetMinutes = 0;
  const tzSign = tzMatch?.[1] ?? tzMatch?.[6];
  if (tzMatch && tzSign) {
    const tzHour = Number(tzMatch[2] ?? tzMatch[4] ?? tzMatch[7]);
    const tzMin = Number(tzMatch[3] ?? tzMatch[5] ?? tzMatch[8] ?? 0);
    if (tzHour > 23 || tzMin > 59) {
      return null;
    }
    offsetMinutes = (tzSign === '+' ? 1 : -1) * (tzHour * 60 + tzMin);
  }

  const namedMatch = NAMED_MONTH_DAY_RE.exec(s);
  if (namedMatch) {
    const monthToken = (namedMatch[1] ?? namedMatch[4] ?? '').slice(0, 3).toLowerCase();
    const dayToken = Number(namedMatch[2] ?? namedMatch[3]);
    const expectedMonth = Object.prototype.hasOwnProperty.call(MONTH_NAME_TO_INDEX, monthToken)
      ? MONTH_NAME_TO_INDEX[monthToken]
      : undefined;
    if (expectedMonth !== undefined && Number.isInteger(dayToken)) {
      let actualMonth: number;
      let actualDay: number;
      if (hasExplicitTz) {
        const checkDt = offsetMinutes !== 0
          ? new Date(parsed.getTime() + offsetMinutes * 60_000)
          : parsed;
        actualMonth = checkDt.getUTCMonth();
        actualDay = checkDt.getUTCDate();
      } else {
        actualMonth = parsed.getMonth();
        actualDay = parsed.getDate();
      }
      if (actualMonth !== expectedMonth || actualDay !== dayToken) {
        return null;
      }
    }
  }

  if (!hasExplicitTz && !ISO_YEAR_MONTH_RE.test(s)) {
    return buildValidatedUtcDate(
      parsed.getFullYear(),
      parsed.getMonth() + 1,
      parsed.getDate(),
      parsed.getHours(),
      parsed.getMinutes(),
      parsed.getSeconds(),
      parsed.getMilliseconds()
    );
  }
  return parsed;
}

/**
 * Predicts estimated calendar date (YYYY-MM-DD in UTC) of subsidy exhaustion.
 */
export function predictExhaustionDate(
  remainingUnits: number | null | undefined,
  dailyVelocity: number | null | undefined,
  startDate?: Date | string | null
): string | null {
  const days = predictExhaustionDays(remainingUnits, dailyVelocity);
  if (days === null) return null;
  try {
    const baseDt = parseUtcStartDate(startDate);
    if (!baseDt) {
      return null;
    }
    baseDt.setUTCDate(baseDt.getUTCDate() + days);
    if (Number.isNaN(baseDt.getTime())) {
      return null;
    }
    const yr = baseDt.getUTCFullYear();
    if (!Number.isFinite(yr) || yr < 0 || yr > 9999) {
      return null;
    }
    const mo = String(baseDt.getUTCMonth() + 1).padStart(2, '0');
    const da = String(baseDt.getUTCDate()).padStart(2, '0');
    return `${String(yr).padStart(4, '0')}-${mo}-${da}`;
  } catch {
    return null;
  }
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
    ? (options.defaultKrw === 0 ? 0 : options.defaultKrw)
    : 0;
  const maxCap = typeof options?.maxKrw === 'number' && Number.isFinite(options.maxKrw) && options.maxKrw >= 0
    ? (options.maxKrw === 0 ? 0 : options.maxKrw)
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
      return allowNeg ? (maxCap === 0 ? 0 : -maxCap) : 0;
    }
    if (!Number.isFinite(input)) {
      return fallback;
    }
    if (!allowNeg && input <= 0) {
      return 0;
    }
    const rounded = Math.round(input);
    const clamped = allowNeg
      ? Math.max(-maxCap, Math.min(maxCap, rounded))
      : Math.min(maxCap, Math.max(0, rounded));
    return clamped === 0 ? 0 : clamped;
  }

  if (typeof input !== 'string') {
    return fallback;
  }

  const raw = input.trim();
  if (!raw) {
    return fallback;
  }

  const signMatch = LEADING_SIGN_RE.exec(raw);
  const sign = signMatch?.[1] ?? '';
  const clean = signMatch?.[2] ?? raw;
  if (!clean || /^[+-]/.test(clean)) {
    return fallback;
  }
  const isNeg = sign === '-';

  let total = 0;
  let matchedKoreanUnit = false;

  // 1. Match '억'
  const eokMatch = EOK_RE.exec(clean);
  if (eokMatch) {
    const numStr = eokMatch[1].replace(COMMA_RE, '');
    const val = STRICT_UNIT_NUMBER_RE.test(numStr) ? parseFloat(numStr) : NaN;
    if (Number.isFinite(val)) {
      total += val * 100_000_000;
      matchedKoreanUnit = true;
    }
  }

  // 2. Match '천만' (e.g. 5천만원)
  const cheonManMatch = CHEON_MAN_RE.exec(clean);
  if (cheonManMatch) {
    const numStr = cheonManMatch[1].replace(COMMA_RE, '');
    const val = STRICT_UNIT_NUMBER_RE.test(numStr) ? parseFloat(numStr) : NaN;
    if (Number.isFinite(val)) {
      total += val * 10_000_000;
      matchedKoreanUnit = true;
    }
  } else {
    // 3. Match '만' (e.g. 650만원, 5,500만 원, 650만)
    const manMatch = MAN_RE.exec(clean);
    if (manMatch) {
      const numStr = manMatch[1].replace(COMMA_RE, '');
      const val = STRICT_UNIT_NUMBER_RE.test(numStr) ? parseFloat(numStr) : NaN;
      if (Number.isFinite(val)) {
        total += val * 10_000;
        matchedKoreanUnit = true;
      }
    }
  }

  // 4. Match standalone '천' (not followed by '만', e.g. 5천원)
  const cheonMatch = CHEON_RE.exec(clean);
  if (cheonMatch) {
    const numStr = cheonMatch[1].replace(COMMA_RE, '');
    const val = STRICT_UNIT_NUMBER_RE.test(numStr) ? parseFloat(numStr) : NaN;
    if (Number.isFinite(val)) {
      total += val * 1_000;
      matchedKoreanUnit = true;
    }
  }

  // 5. If no Korean unit was matched, parse as standard raw number with commas/currency symbols
  if (!matchedKoreanUnit) {
    const stripped = clean.replace(CURRENCY_STRIP_RE, '');
    if ((sign !== '' && /^[+-]/.test(stripped)) || !STRICT_NUMBER_RE.test(stripped)) {
      return fallback;
    }
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

  if (!allowNeg && finalVal <= 0) {
    return 0;
  }

  const clamped = allowNeg
    ? Math.max(-maxCap, Math.min(maxCap, finalVal))
    : Math.min(maxCap, Math.max(0, finalVal));
  return clamped === 0 ? 0 : clamped;
}

const VALID_ALERT_SEVERITIES: ReadonlySet<AlertSeverity> = new Set([
  'HEALTHY',
  'CAUTION',
  'WARNING',
  'CRITICAL',
  'DEPLETED',
]);

const VALID_CATEGORY_KEYS: ReadonlySet<SubsidyCategoryKey> = new Set([
  'passenger',
  'commercial',
  'bus',
]);

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}

function getSafeCategory(
  categories: unknown,
  categoryKey: SubsidyCategoryKey
): CategoryMetrics | undefined {
  if (!isPlainObject(categories) || !VALID_CATEGORY_KEYS.has(categoryKey)) {
    return undefined;
  }
  if (!Object.prototype.hasOwnProperty.call(categories, categoryKey)) {
    return undefined;
  }
  const cat = categories[categoryKey];
  return isPlainObject(cat) ? (cat as unknown as CategoryMetrics) : undefined;
}

function safeString(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function safeNonEmptyString(value: unknown, fallback: string): string {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : fallback;
}

function safeFiniteNonNeg(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value) && value >= 0) {
    return value === 0 ? 0 : value;
  }
  return undefined;
}

function round1Safe(value: number): number {
  if (!Number.isFinite(value)) return value;
  const scaled = value * 10;
  const rounded = Number.isFinite(scaled) ? Math.round(scaled) / 10 : value;
  return rounded === 0 ? 0 : rounded;
}

function parseFiniteNonNegNumber(value: unknown): number {
  if (typeof value === 'number' && !Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, parseSubsidyNumber(value, { defaultKrw: 0 }));
}

/**
 * Resolves a validated AlertSeverity from an untrusted status field or depletion rate fallback.
 */
export function resolveAlertSeverity(rawStatus: unknown, depletionRate: number): AlertSeverity {
  const normalized = typeof rawStatus === 'string' ? rawStatus.trim().toUpperCase() : '';
  if (VALID_ALERT_SEVERITIES.has(normalized as AlertSeverity)) {
    return normalized as AlertSeverity;
  }
  const safeRate = Number.isFinite(depletionRate) || depletionRate === Infinity ? depletionRate : 0;
  if (safeRate >= 100.0) return 'DEPLETED';
  if (safeRate >= 95.0) return 'CRITICAL';
  if (safeRate >= 80.0) return 'WARNING';
  if (safeRate >= 60.0) return 'CAUTION';
  return 'HEALTHY';
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
  const m = isPlainObject(model) ? model : {};
  const modelId = safeNonEmptyString(m.model_id, safeNonEmptyString(m.id, 'unknown-model'));
  const nameKo = safeNonEmptyString(m.name_ko, safeNonEmptyString(m.name, '기본 모델'));
  const manufacturer = safeNonEmptyString(m.manufacturer, safeNonEmptyString(m.brand, '기타'));
  const rawPrice = parseSubsidyNumber(m.base_price_krw ?? m.basePriceKrw, { defaultKrw: 0 });
  const basePriceKrw = rawPrice > 0 ? rawPrice : 54_100_000;
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
  const c = isPlainObject(category) ? category : {};
  const announcedUnits = parseFiniteNonNegNumber(c.announced_units ?? c.announcedUnits);
  const appliedUnits = parseFiniteNonNegNumber(c.applied_units ?? c.appliedUnits);
  const deliveredUnits = parseFiniteNonNegNumber(c.delivered_units ?? c.deliveredUnits);

  const rawRemaining = c.remaining_units ?? c.remainingUnits;
  let remainingUnits: number;
  if (
    rawRemaining !== undefined &&
    rawRemaining !== null &&
    !(typeof rawRemaining === 'number' && !Number.isFinite(rawRemaining))
  ) {
    const parsedRemaining = parseSubsidyNumber(rawRemaining, { allowNegative: true, defaultKrw: -1 });
    remainingUnits = parsedRemaining >= 0
      ? parsedRemaining
      : calculateRemainingUnits(appliedUnits, announcedUnits);
  } else {
    remainingUnits = calculateRemainingUnits(appliedUnits, announcedUnits);
  }

  const rawRate = c.depletion_rate ?? c.depletionRate;
  const depletionRate = typeof rawRate === 'number' && Number.isFinite(rawRate) && rawRate >= 0
    ? round1Safe(rawRate)
    : calculateDepletionRate(appliedUnits, announcedUnits);

  const rawDelRate = c.delivery_rate ?? c.deliveryRate;
  const deliveryRate = typeof rawDelRate === 'number' && Number.isFinite(rawDelRate) && rawDelRate >= 0
    ? round1Safe(rawDelRate)
    : calculateDeliveryRate(deliveredUnits, announcedUnits);

  const maxLocalSubsidyKrw = parseFiniteNonNegNumber(c.max_local_subsidy_krw ?? c.maxLocalSubsidyKrw);
  const maxTotalSubsidyKrw = parseFiniteNonNegNumber(c.max_total_subsidy_krw ?? c.maxTotalSubsidyKrw);

  const status = resolveAlertSeverity(c.status, depletionRate);

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
  const isValidA = typeof a === 'number' && !Number.isNaN(a);
  const isValidB = typeof b === 'number' && !Number.isNaN(b);

  if (!isValidA && !isValidB) return 0;
  if (!isValidA) return 1; // Invalid values always sorted to the end
  if (!isValidB) return -1;

  if (a === b) return 0;

  const isFiniteA = Number.isFinite(a);
  const isFiniteB = Number.isFinite(b);

  if (isFiniteA && isFiniteB) {
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

  return 0;
}



function extractRegionSortMetric(
  region: RegionEntry,
  normalizedSort: string,
  categoryKey: SubsidyCategoryKey
): number {
  const cat = getSafeCategory(region.categories, categoryKey);
  switch (normalizedSort) {
    case 'DEPLETION_DESC':
    case 'DEPLETION_ASC':
      return typeof cat?.depletion_rate === 'number' && !Number.isNaN(cat.depletion_rate)
        ? Math.max(0, cat.depletion_rate)
        : calculateDepletionRate(cat?.applied_units, cat?.announced_units);
    case 'REMAINING_ASC':
    case 'REMAINING_DESC':
      return typeof cat?.remaining_units === 'number' && !Number.isNaN(cat.remaining_units)
        ? Math.max(0, cat.remaining_units)
        : calculateRemainingUnits(cat?.applied_units, cat?.announced_units);
    case 'LOCAL_SUBSIDY_DESC':
    case 'LOCAL_SUBSIDY_ASC':
      return parseSubsidyNumber(cat?.max_local_subsidy_krw, { defaultKrw: 0 });
    default:
      return 0;
  }
}

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

  const normalizedSort = typeof sortOption === 'string' && sortOption.trim()
    ? sortOption.trim().toUpperCase()
    : 'DEPLETION_DESC';

  let cmp = 0;
  switch (normalizedSort) {
    case 'DEPLETION_DESC':
    case 'REMAINING_DESC':
    case 'LOCAL_SUBSIDY_DESC': {
      const valA = extractRegionSortMetric(a, normalizedSort, categoryKey);
      const valB = extractRegionSortMetric(b, normalizedSort, categoryKey);
      cmp = safeCompareNumbers(valA, valB, 'desc');
      break;
    }
    case 'DEPLETION_ASC':
    case 'REMAINING_ASC':
    case 'LOCAL_SUBSIDY_ASC': {
      const valA = extractRegionSortMetric(a, normalizedSort, categoryKey);
      const valB = extractRegionSortMetric(b, normalizedSort, categoryKey);
      cmp = safeCompareNumbers(valA, valB, 'asc');
      break;
    }
    case 'NAME_ASC': {
      cmp = KO_COLLATOR.compare(safeString(a.name_ko), safeString(b.name_ko));
      break;
    }
    case 'NAME_DESC': {
      cmp = KO_COLLATOR.compare(safeString(b.name_ko), safeString(a.name_ko));
      break;
    }
    default:
      cmp = 0;
  }

  if (cmp !== 0) return cmp;
  // Deterministic tie-breaker by name then region_id
  const nameTie = KO_COLLATOR.compare(safeString(a.name_ko), safeString(b.name_ko));
  if (nameTie !== 0) return nameTie;
  return DEFAULT_COLLATOR.compare(safeString(a.region_id), safeString(b.region_id));
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
  const normalizedSort = typeof sortOption === 'string' && sortOption.trim()
    ? sortOption.trim().toUpperCase()
    : 'DEPLETION_DESC';

  const isNameAsc = normalizedSort === 'NAME_ASC';
  const isNameDesc = normalizedSort === 'NAME_DESC';
  const isDesc =
    normalizedSort === 'DEPLETION_DESC' ||
    normalizedSort === 'REMAINING_DESC' ||
    normalizedSort === 'LOCAL_SUBSIDY_DESC';
  const isNumericSort =
    isDesc ||
    normalizedSort === 'DEPLETION_ASC' ||
    normalizedSort === 'REMAINING_ASC' ||
    normalizedSort === 'LOCAL_SUBSIDY_ASC';

  const decorated: Array<{ item: T; metric: number; nameKo: string; regionId: string }> = [];
  for (let i = 0; i < regions.length; i++) {
    const r = regions[i];
    if (!isPlainObject(r)) continue;
    decorated.push({
      item: r as T,
      metric: isNumericSort ? extractRegionSortMetric(r as T, normalizedSort, categoryKey) : 0,
      nameKo: safeString(r.name_ko),
      regionId: safeString(r.region_id),
    });
  }

  if (decorated.length <= 1) {
    return decorated.map((d) => d.item);
  }

  const direction = isDesc ? 'desc' : 'asc';
  decorated.sort((a, b) => {
    let cmp = 0;
    if (isNumericSort) {
      cmp = safeCompareNumbers(a.metric, b.metric, direction);
    } else if (isNameAsc) {
      cmp = KO_COLLATOR.compare(a.nameKo, b.nameKo);
    } else if (isNameDesc) {
      cmp = KO_COLLATOR.compare(b.nameKo, a.nameKo);
    }
    if (cmp !== 0) return cmp;
    const nameTie = KO_COLLATOR.compare(a.nameKo, b.nameKo);
    if (nameTie !== 0) return nameTie;
    return DEFAULT_COLLATOR.compare(a.regionId, b.regionId);
  });

  const result = new Array<T>(decorated.length);
  for (let i = 0; i < decorated.length; i++) {
    result[i] = decorated[i].item;
  }
  return result;
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
    const cat = getSafeCategory(r.categories, categoryKey);
    const rawRate = typeof cat?.depletion_rate === 'number' && !Number.isNaN(cat.depletion_rate)
      ? Math.max(0, cat.depletion_rate)
      : calculateDepletionRate(cat?.applied_units, cat?.announced_units);
    const rate = round1Safe(rawRate);
    const rem = typeof cat?.remaining_units === 'number' && !Number.isNaN(cat.remaining_units)
      ? Math.max(0, cat.remaining_units)
      : calculateRemainingUnits(cat?.applied_units, cat?.announced_units);

    const status = resolveAlertSeverity(cat?.status, rate);

    if (i > 0) {
      const prev = ranked[i - 1];
      if (rate === prev.depletionRate) {
        currentRank = prev.rank;
      } else {
        currentRank = i + 1;
      }
    }

    ranked.push({
      ...r,
      rank: currentRank,
      regionId: safeString(r.region_id),
      nameKo: safeString(r.name_ko),
      depletionRate: rate,
      remainingUnits: rem,
      status,
      region: r,
    });
  }

  return ranked;
}



function extractModelSortMetric(
  model: PopularModelEntry,
  normalizedSort: string
): number {
  switch (normalizedSort) {
    case 'PRICE_ASC':
    case 'NET_PRICE_ASC':
    case 'PRICE_DESC':
    case 'NET_PRICE_DESC':
      return parseSubsidyNumber(model.base_price_krw, { defaultKrw: 54_100_000 });
    case 'SUBSIDY_DESC':
    case 'SUBSIDY_ASC':
      return parseSubsidyNumber(model.national_subsidy_krw, { defaultKrw: 0 });
    case 'RANGE_DESC':
    case 'RANGE_ASC':
      return typeof model.rated_range_km === 'number' && Number.isFinite(model.rated_range_km)
        ? (model.rated_range_km === 0 ? 0 : model.rated_range_km)
        : 0;
    default:
      return 0;
  }
}

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

  const normalizedSort = typeof sortOption === 'string' && sortOption.trim()
    ? sortOption.trim().toUpperCase()
    : 'PRICE_ASC';

  let cmp = 0;
  switch (normalizedSort) {
    case 'PRICE_ASC':
    case 'NET_PRICE_ASC':
    case 'SUBSIDY_ASC':
    case 'RANGE_ASC': {
      const valA = extractModelSortMetric(a, normalizedSort);
      const valB = extractModelSortMetric(b, normalizedSort);
      cmp = safeCompareNumbers(valA, valB, 'asc');
      break;
    }
    case 'PRICE_DESC':
    case 'NET_PRICE_DESC':
    case 'SUBSIDY_DESC':
    case 'RANGE_DESC': {
      const valA = extractModelSortMetric(a, normalizedSort);
      const valB = extractModelSortMetric(b, normalizedSort);
      cmp = safeCompareNumbers(valA, valB, 'desc');
      break;
    }
    case 'NAME_ASC': {
      cmp = KO_COLLATOR.compare(safeString(a.name_ko), safeString(b.name_ko));
      break;
    }
    case 'NAME_DESC': {
      cmp = KO_COLLATOR.compare(safeString(b.name_ko), safeString(a.name_ko));
      break;
    }
    default:
      cmp = 0;
  }

  if (cmp !== 0) return cmp;
  return DEFAULT_COLLATOR.compare(safeString(a.model_id), safeString(b.model_id));
}

/**
 * Non-mutating pure function sorting vehicle models array with guaranteed NaN/Infinity safety.
 */
export function sortModels<T extends PopularModelEntry>(
  models: readonly T[] | null | undefined,
  sortOption: ModelSortOption = 'PRICE_ASC'
): T[] {
  if (!Array.isArray(models)) return [];
  const normalizedSort = typeof sortOption === 'string' && sortOption.trim()
    ? sortOption.trim().toUpperCase()
    : 'PRICE_ASC';

  const isNameAsc = normalizedSort === 'NAME_ASC';
  const isNameDesc = normalizedSort === 'NAME_DESC';
  const isDesc =
    normalizedSort === 'PRICE_DESC' ||
    normalizedSort === 'NET_PRICE_DESC' ||
    normalizedSort === 'SUBSIDY_DESC' ||
    normalizedSort === 'RANGE_DESC';
  const isNumericSort =
    isDesc ||
    normalizedSort === 'PRICE_ASC' ||
    normalizedSort === 'NET_PRICE_ASC' ||
    normalizedSort === 'SUBSIDY_ASC' ||
    normalizedSort === 'RANGE_ASC';

  const decorated: Array<{ item: T; metric: number; nameKo: string; modelId: string }> = [];
  for (let i = 0; i < models.length; i++) {
    const m = models[i];
    if (!isPlainObject(m)) continue;
    decorated.push({
      item: m as T,
      metric: isNumericSort ? extractModelSortMetric(m as T, normalizedSort) : 0,
      nameKo: safeString(m.name_ko),
      modelId: safeString(m.model_id),
    });
  }

  if (decorated.length <= 1) {
    return decorated.map((d) => d.item);
  }

  const direction = isDesc ? 'desc' : 'asc';
  decorated.sort((a, b) => {
    let cmp = 0;
    if (isNumericSort) {
      cmp = safeCompareNumbers(a.metric, b.metric, direction);
    } else if (isNameAsc) {
      cmp = KO_COLLATOR.compare(a.nameKo, b.nameKo);
    } else if (isNameDesc) {
      cmp = KO_COLLATOR.compare(b.nameKo, a.nameKo);
    }
    if (cmp !== 0) return cmp;
    return DEFAULT_COLLATOR.compare(a.modelId, b.modelId);
  });

  const result = new Array<T>(decorated.length);
  for (let i = 0; i < decorated.length; i++) {
    result[i] = decorated[i].item;
  }
  return result;
}

// ==========================================
// 5. PURE SUBSIDY CALCULATION ENGINE
// ==========================================

const DEFAULT_PURE_MODEL: PopularModelEntry = Object.freeze({
  model_id: 'unknown-model',
  name_ko: '기본 모델',
  manufacturer: '기타',
  battery_type: 'NCM 삼원계',
  battery_capacity_kwh: 84.0,
  rated_range_km: 485,
  base_price_krw: 54_100_000,
  national_subsidy_krw: 0,
  price_subsidy_ratio: 1.0,
});

const DEFAULT_PURE_REGION: RegionEntry = Object.freeze({
  region_id: 'unknown-region',
  iso_code: 'KR-00',
  name_ko: '전국 평균',
  name_en: 'Nationwide',
  tier: 'special_city',
  overall_depletion_rate: 0,
  overall_status: 'HEALTHY',
  residency_requirement_days: 30,
  supplementary_budget_added: false,
  categories: DEFAULT_NATIONWIDE_SUMMARY.category_totals,
}) as RegionEntry;

/**
 * Computes net subsidy, matching municipal grant, statutory price cap reduction,
 * and out-of-pocket net vehicle purchase price from model and region parameters.
 */
export function calculateNetSubsidyPure(
  model?: PopularModelEntry | null,
  region?: RegionEntry | null,
  customMsrp?: number | string | null,
  options?: SubsidyCalculatorOptions
): SubsidyCalculationResult {
  const safeModel: PopularModelEntry = isPlainObject(model)
    ? (model as PopularModelEntry)
    : DEFAULT_PURE_MODEL;

  const safeRegion: RegionEntry = isPlainObject(region)
    ? (region as RegionEntry)
    : DEFAULT_PURE_REGION;

  const passengerCategory = getSafeCategory(safeRegion.categories, 'passenger');

  // 1. Resolve MSRP and statutory price-cap ratio
  const safeModelPrice = parseSubsidyNumber(safeModel?.base_price_krw, {
    defaultKrw: 54_100_000,
    maxKrw: 10_000_000_000,
  });

  const effectiveCustomMsrp =
    customMsrp !== undefined && customMsrp !== null ? customMsrp : options?.customMsrp;

  let activeMsrp: number;
  let parsedCustomMsrp = 0;
  if (effectiveCustomMsrp === Infinity) {
    activeMsrp = 10_000_000_000;
    parsedCustomMsrp = 10_000_000_000;
  } else if (effectiveCustomMsrp !== undefined && effectiveCustomMsrp !== null) {
    parsedCustomMsrp = parseSubsidyNumber(effectiveCustomMsrp, { maxKrw: 10_000_000_000 });
    activeMsrp = parsedCustomMsrp > 0 ? parsedCustomMsrp : (safeModelPrice > 0 ? safeModelPrice : 54_100_000);
  } else {
    activeMsrp = safeModelPrice > 0 ? safeModelPrice : 54_100_000;
  }

  const ratio = getPriceSubsidyRatio(activeMsrp);

  let priceCapTierText = '100% 전액 지원 (5,500만 원 이하)';
  if (ratio === 0.5) {
    priceCapTierText = '50% 감액 지원 (5,500만 원 초과 ~ 8,500만 원 이하)';
  } else if (ratio === 0.0) {
    priceCapTierText = '보조금 지급 대상 제외 (8,500만 원 초과)';
  }

  // 2. Calculate National Subsidy
  const validNationalSubsidy = parseFiniteNonNegNumber(safeModel.national_subsidy_krw);
  let nationalSubsidyKrw = 0;
  if (ratio > 0) {
    if (parsedCustomMsrp > 0) {
      const baseRatio = typeof safeModel.price_subsidy_ratio === 'number' && Number.isFinite(safeModel.price_subsidy_ratio) && safeModel.price_subsidy_ratio > 0
        ? safeModel.price_subsidy_ratio
        : 1.0;
      const unscaledNational = Math.round(validNationalSubsidy / baseRatio);
      nationalSubsidyKrw = Math.min(6_500_000, Math.max(0, Math.round(unscaledNational * ratio)));
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
  const maxLocal = parseFiniteNonNegNumber(passengerCategory?.max_local_subsidy_krw);
  let localSubsidyKrw = 0;
  if (nationalSubsidyKrw > 0 && maxLocal > 0) {
    const rawProduct = maxLocal * nationalSubsidyKrw;
    const calculated = Math.round(
      Number.isFinite(rawProduct)
        ? rawProduct / 6_500_000
        : maxLocal * (nationalSubsidyKrw / 6_500_000)
    );
    localSubsidyKrw = Math.min(maxLocal, Math.max(0, Math.round(calculated / 10_000) * 10_000));
  }

  // 5. Total & Net Out-of-pocket Purchase Price
  const totalSubsidyKrw = nationalSubsidyKrw + localSubsidyKrw + additionalGrantsKrw;
  const rawNetPrice = activeMsrp - totalSubsidyKrw;
  const netPurchasePriceKrw = Number.isFinite(rawNetPrice) ? Math.max(0, rawNetPrice) : 0;

  // 6. Depletion Risk & Warning Analysis
  const catAnnounced = parseFiniteNonNegNumber(passengerCategory?.announced_units);
  const catApplied = parseFiniteNonNegNumber(passengerCategory?.applied_units);

  const depletionRate =
    safeFiniteNonNeg(passengerCategory?.depletion_rate) ??
    calculateDepletionRate(catApplied, catAnnounced);

  const isHighDepletionRisk = depletionRate >= 80.0;
  const depletionStatus = resolveAlertSeverity(passengerCategory?.status, depletionRate);

  const remainingUnits =
    safeFiniteNonNeg(passengerCategory?.remaining_units) ??
    calculateRemainingUnits(catApplied, catAnnounced);

  const regionDisplayName = safeNonEmptyString(safeRegion.name_ko, '해당 지역');
  let warningNotice: string | undefined;
  const safeRemainingUnits = Number.isFinite(remainingUnits) ? remainingUnits : 0;

  if (catAnnounced <= 0) {
    warningNotice = `ℹ️ ${regionDisplayName}의 보조금 공고 정보가 아직 발표되지 않았거나 접수 준비 중입니다.`;
  } else if (depletionRate >= 100.0) {
    warningNotice = `🚨 ${regionDisplayName}의 2026년 공고 예산이 전액 소진(소진율 ${depletionRate.toFixed(1)}%)되어 접수가 마감되었습니다. 취소분 대기 또는 추경 편성을 확인하세요.`;
  } else if (depletionRate >= 95.0) {
    warningNotice = `🚨 ${regionDisplayName}의 승용 보조금 소진율이 ${depletionRate.toFixed(1)}%로 선착순 마감 직전입니다! 즉시 출고 가능 실재고 매칭이 필요합니다.`;
  } else if (depletionRate >= 80.0) {
    warningNotice = `⚠️ ${regionDisplayName}의 승용 보조금 소진율이 ${depletionRate.toFixed(1)}%에 달해 조기 마감 위험이 높습니다.`;
  } else {
    warningNotice = `✅ ${regionDisplayName}의 보조금 잔여량이 비교적 여유롭습니다 (${safeRemainingUnits.toLocaleString()}대 잔여).`;
  }

  return {
    modelId: safeNonEmptyString(safeModel.model_id, 'unknown-model'),
    modelName: safeNonEmptyString(safeModel.name_ko, '기본 모델'),
    manufacturer: safeNonEmptyString(safeModel.manufacturer, '기타'),
    batteryType: safeNonEmptyString(safeModel.battery_type, 'NCM 삼원계'),
    batteryCapacityKwh: safeFiniteNonNeg(safeModel.battery_capacity_kwh) ?? 0,
    ratedRangeKm: safeFiniteNonNeg(safeModel.rated_range_km) ?? 0,
    regionId: safeNonEmptyString(safeRegion.region_id, 'unknown-region'),
    regionName: regionDisplayName,
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
    residencyRequirementDays: safeFiniteNonNeg(safeRegion.residency_requirement_days) ?? 30,
    warningNotice,
    priceCapTierText,
  };
}

// ==========================================
// 6. STATISTICAL AGGREGATION UTILITIES
// ==========================================

function buildCategoryBreakdown(cat: CategoryMetrics | undefined): CategoryBreakdownMetrics {
  const announced = parseFiniteNonNegNumber(cat?.announced_units);
  const applied = parseFiniteNonNegNumber(cat?.applied_units);
  return {
    announced,
    applied,
    remaining: safeFiniteNonNeg(cat?.remaining_units) ?? calculateRemainingUnits(applied, announced),
    rate: safeFiniteNonNeg(cat?.depletion_rate) ?? calculateDepletionRate(applied, announced),
  };
}

/**
 * Pure calculation of nationwide subsidy statistics from an EVSubsidyDataset.
 * Protects against division by zero and NaN/Infinity values.
 */
export function calculateSubsidyStatistics(dataset?: Partial<EVSubsidyDataset> | null): SubsidyStatistics {
  const safeDataset = isPlainObject(dataset) ? (dataset as Partial<EVSubsidyDataset>) : undefined;
  const summary = isPlainObject(safeDataset?.nationwide_summary) ? safeDataset?.nationwide_summary : undefined;
  const regions = Array.isArray(safeDataset?.regions) ? safeDataset.regions : [];

  const announced = parseFiniteNonNegNumber(summary?.total_announced_units);
  const applied = parseFiniteNonNegNumber(summary?.total_applied_units);
  const delivered = parseFiniteNonNegNumber(summary?.total_delivered_units);
  const remaining =
    safeFiniteNonNeg(summary?.total_remaining_units) ??
    calculateRemainingUnits(applied, announced);

  const depletionRate =
    safeFiniteNonNeg(summary?.nationwide_depletion_rate) ??
    calculateDepletionRate(applied, announced);

  const deliveryRate = calculateDeliveryRate(delivered, announced);

  let budgetTotal = safeFiniteNonNeg(summary?.total_budget_billion_krw) ?? 0;
  if (budgetTotal === 0 && typeof summary?.total_budget_krw === 'number' && Number.isFinite(summary.total_budget_krw) && summary.total_budget_krw > 0) {
    budgetTotal = Math.round((summary.total_budget_krw / 1_000_000_000) * 10) / 10;
  }

  let budgetDisbursed = safeFiniteNonNeg(summary?.disbursed_budget_billion_krw) ?? 0;
  if (budgetDisbursed === 0 && typeof summary?.disbursed_budget_krw === 'number' && Number.isFinite(summary.disbursed_budget_krw) && summary.disbursed_budget_krw > 0) {
    budgetDisbursed = Math.round((summary.disbursed_budget_krw / 1_000_000_000) * 10) / 10;
  }

  const rawExecNumerator = budgetTotal > 0 && budgetDisbursed >= 0 ? budgetDisbursed * 1000 : 0;
  const rawExecRate = budgetTotal > 0 && budgetDisbursed >= 0
    ? (Number.isFinite(rawExecNumerator) ? rawExecNumerator / budgetTotal : (budgetDisbursed / budgetTotal) * 1000)
    : 0;
  const roundedExec = Number.isFinite(rawExecRate) ? Math.round(rawExecRate) / 10 : 0.0;
  const budgetExecutionRatePct = roundedExec > 0 ? roundedExec : 0.0;

  // Extract regions >= 95% and >= 100%
  const criticalList: Array<{ regionId: string; nameKo: string; depletionRate: number; remainingUnits: number }> = [];
  let depletedCount = 0;
  let criticalCount = 0;
  let warningCount = 0;
  let cautionCount = 0;
  let healthyCount = 0;

  if (regions.length > 0) {
    for (const r of regions) {
      if (!isPlainObject(r)) continue;
      const passengerCat = getSafeCategory(r.categories, 'passenger');
      const passengerApplied = parseFiniteNonNegNumber(passengerCat?.applied_units);
      const passengerAnnounced = parseFiniteNonNegNumber(passengerCat?.announced_units);
      const rate =
        safeFiniteNonNeg(r.overall_depletion_rate) ??
        calculateDepletionRate(passengerApplied, passengerAnnounced);
      const rem =
        safeFiniteNonNeg(passengerCat?.remaining_units) ??
        calculateRemainingUnits(passengerApplied, passengerAnnounced);

      if (rate >= 100.0) {
        depletedCount++;
        criticalCount++;
        criticalList.push({
          regionId: safeString(r.region_id),
          nameKo: safeString(r.name_ko),
          depletionRate: rate,
          remainingUnits: rem,
        });
      } else if (rate >= 95.0) {
        criticalCount++;
        criticalList.push({
          regionId: safeString(r.region_id),
          nameKo: safeString(r.name_ko),
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
  } else if (isPlainObject(summary?.alert_region_counts)) {
    depletedCount = parseFiniteNonNegNumber(summary.alert_region_counts.depleted);
    criticalCount = parseFiniteNonNegNumber(summary.alert_region_counts.critical) + depletedCount;
    warningCount = parseFiniteNonNegNumber(summary.alert_region_counts.warning);
    cautionCount = parseFiniteNonNegNumber(summary.alert_region_counts.caution);
    healthyCount = parseFiniteNonNegNumber(summary.alert_region_counts.healthy);
  }

  // Sort critical regions descending by depletion rate with full NaN/Infinity guard
  criticalList.sort((a, b) => {
    const cmp = safeCompareNumbers(a.depletionRate, b.depletionRate, 'desc');
    if (cmp !== 0) return cmp;
    return KO_COLLATOR.compare(safeString(a.nameKo), safeString(b.nameKo));
  });

  const cat = summary?.category_totals;
  const passengerCat = getSafeCategory(cat, 'passenger');
  const commercialCat = getSafeCategory(cat, 'commercial');
  const busCat = getSafeCategory(cat, 'bus');

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
      passenger: buildCategoryBreakdown(passengerCat),
      commercial: buildCategoryBreakdown(commercialCat),
      bus: buildCategoryBreakdown(busCat),
    },
    // Compatibility Shorthand Aliases
    announced,
    applied,
    delivered,
    remaining,
    depletionRate,
    budgetTotal,
    budgetDisbursed,
    depletedRegionsCount: depletedCount,
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

// ==========================================
// 8. REGIONAL GROUPING UTILITIES
// ==========================================

export const METROPOLITAN_CITIES = Object.freeze([
  '서울',
  '부산',
  '대구',
  '인천',
  '광주',
  '대전',
  '울산',
  '세종',
] as const);

export const PROVINCES = Object.freeze([
  '경기',
  '강원',
  '충북',
  '충남',
  '전북',
  '전남',
  '경북',
  '경남',
  '제주',
] as const);

export const METROPOLITAN_CITY_CODES = Object.freeze([
  'KR-11',
  'KR-26',
  'KR-27',
  'KR-28',
  'KR-29',
  'KR-30',
  'KR-31',
  'KR-36',
] as const);

export const PROVINCE_CODES = Object.freeze([
  'KR-41',
  'KR-42',
  'KR-43',
  'KR-44',
  'KR-45',
  'KR-46',
  'KR-47',
  'KR-48',
  'KR-49',
] as const);

const METROPOLITAN_CITY_CODE_SET: ReadonlySet<string> = new Set(METROPOLITAN_CITY_CODES);
const PROVINCE_CODE_SET: ReadonlySet<string> = new Set(PROVINCE_CODES);

function resolveRegionAliasCode(raw: string): string {
  const trimmed = raw.trim();
  const lower = trimmed.toLowerCase();
  if (Object.prototype.hasOwnProperty.call(REGION_ALIAS_MAP, lower)) {
    return REGION_ALIAS_MAP[lower].toUpperCase();
  }
  if (Object.prototype.hasOwnProperty.call(REGION_ALIAS_MAP, trimmed)) {
    return REGION_ALIAS_MAP[trimmed].toUpperCase();
  }
  return trimmed.toUpperCase();
}

export function classifyRegionGroup(
  region: RegionEntry | string | null | undefined
): RegionalGroup {
  if (!region) return 'other';

  if (typeof region === 'string') {
    const ident = region.trim();
    if (!ident) return 'other';
    const canonical = resolveRegionAliasCode(ident);
    if (METROPOLITAN_CITY_CODE_SET.has(canonical)) return 'metropolitan_cities';
    if (PROVINCE_CODE_SET.has(canonical)) return 'provinces';
    for (const city of METROPOLITAN_CITIES) {
      if (ident.startsWith(city)) return 'metropolitan_cities';
    }
    for (const prov of PROVINCES) {
      if (ident.startsWith(prov)) return 'provinces';
    }
    for (const city of METROPOLITAN_CITIES) {
      if (ident.includes(city)) return 'metropolitan_cities';
    }
    for (const prov of PROVINCES) {
      if (ident.includes(prov)) return 'provinces';
    }
    return 'other';
  }

  if (!isPlainObject(region)) return 'other';

  const rawCode =
    safeString(region.iso_code) ||
    safeString(region.region_id) ||
    safeString(region.code);
  const code = rawCode.trim() ? resolveRegionAliasCode(rawCode) : '';
  if (METROPOLITAN_CITY_CODE_SET.has(code)) return 'metropolitan_cities';
  if (PROVINCE_CODE_SET.has(code)) return 'provinces';

  const nameKo = safeString(region.name_ko).trim();
  for (const city of METROPOLITAN_CITIES) {
    if (nameKo.startsWith(city)) return 'metropolitan_cities';
  }
  for (const prov of PROVINCES) {
    if (nameKo.startsWith(prov)) return 'provinces';
  }
  for (const city of METROPOLITAN_CITIES) {
    if (nameKo.includes(city)) return 'metropolitan_cities';
  }
  for (const prov of PROVINCES) {
    if (nameKo.includes(prov)) return 'provinces';
  }

  if (
    region.tier === 'special_city' ||
    region.tier === 'metropolitan_city' ||
    region.tier === 'special_self_governing_city'
  ) {
    return 'metropolitan_cities';
  }
  if (
    region.tier === 'province' ||
    region.tier === 'special_self_governing_province'
  ) {
    return 'provinces';
  }

  return 'other';
}

export function isMetropolitanCity(
  region: RegionEntry | string | null | undefined
): boolean {
  return classifyRegionGroup(region) === 'metropolitan_cities';
}

export function isProvince(
  region: RegionEntry | string | null | undefined
): boolean {
  return classifyRegionGroup(region) === 'provinces';
}

export function groupRegionsByType<T extends RegionEntry>(
  regions: readonly T[] | null | undefined
): { metropolitan_cities: T[]; provinces: T[]; other: T[] } {
  const result: { metropolitan_cities: T[]; provinces: T[]; other: T[] } = {
    metropolitan_cities: [],
    provinces: [],
    other: [],
  };
  if (!Array.isArray(regions)) return result;

  for (const r of regions) {
    if (!isPlainObject(r)) continue;
    const grp = classifyRegionGroup(r as T);
    result[grp].push(r as T);
  }
  return result;
}

/**
 * Pure Helper: Badge styling with opaque solid backgrounds for compliant WCAG AA contrast (> 7:1)
 */
export const getBadgeStyle = (status?: AlertSeverity | string | null): string => {
  const normalized = typeof status === 'string' ? status.trim().toUpperCase() : '';
  switch (normalized) {
    case 'HEALTHY':
    case 'AVAILABLE':
      return 'bg-emerald-950 text-emerald-200 border-emerald-400';
    case 'CAUTION':
      return 'bg-amber-950 text-amber-200 border-amber-400';
    case 'WARNING':
      return 'bg-orange-950 text-orange-200 border-orange-400';
    case 'CRITICAL':
    case 'DANGER':
    case 'EMERGENCY':
      return 'bg-rose-950 text-rose-200 border-rose-400 animate-pulse motion-reduce:animate-none';
    case 'DEPLETED':
    case 'EXHAUSTED':
    case 'CLOSED':
    case 'END':
      return 'bg-slate-950 text-slate-100 border-slate-400';
    default:
      return 'bg-emerald-950 text-emerald-200 border-emerald-400';
  }
};

/**
 * Pure Helper: Status badge labels with accessible visual indicator
 */
export const getStatusLabel = (status?: AlertSeverity | string | null): string => {
  const normalized = typeof status === 'string' ? status.trim().toUpperCase() : '';
  switch (normalized) {
    case 'HEALTHY':
    case 'AVAILABLE':
      return '🟢 안정';
    case 'CAUTION':
      return '🟡 주의';
    case 'WARNING':
      return '🟠 경고';
    case 'CRITICAL':
    case 'DANGER':
    case 'EMERGENCY':
      return '🔴 마감임박';
    case 'DEPLETED':
    case 'EXHAUSTED':
    case 'CLOSED':
    case 'END':
      return '🔒 소진';
    default:
      return '🟢 안정';
  }
};
