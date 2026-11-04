import rawTrendsData from '../data/ev_reliability_trends.json' with { type: 'json' };

// ==========================================
// 1. DOMAIN ENUMS & INTERFACES (from @/types/reliability)
// ==========================================

export type {
  DefectCategoryKey,
  ModelYearVerdict,
  YearEvaluation,
  ModelReliability,
  BrandReliability,
  DefectCategoryMetadata,
  RepairCostMatrixItem,
  ReliabilityTrendsDatabase,
  EnrichedModelItem,
  ReliabilityKPIs,
} from '@/types/reliability';

import type {
  DefectCategoryKey,
  ModelYearVerdict,
  YearEvaluation,
  ModelReliability,
  BrandReliability,
  ReliabilityTrendsDatabase,
  EnrichedModelItem,
  ReliabilityKPIs,
} from '@/types/reliability';

export type TrendDirection = 'UP' | 'DOWN' | 'STABLE';

export interface TrendCalculationResult {
  direction: TrendDirection;
  percentageChange: number;
  absoluteChange: number;
  formattedChange: string;
  isIncrease: boolean;
  isDecrease: boolean;
  isStable: boolean;
}

export interface CategoryComplaintItem {
  category: DefectCategoryKey | string;
  count: number;
  percentage: number;
}

// ==========================================
// 2. RELIABILITY SCORE NORMALIZATION & CALCULATION HELPERS
// ==========================================

/**
 * Normalizes a raw reliability or DSI score to the strictly bounded [0, 100] interval.
 * - Non-numeric or non-finite inputs (NaN, null, undefined, Infinity, -Infinity) fall back safely to fallback (default: 0).
 * - Negative values are clamped to 0.
 * - Values exceeding 100 are clamped to 100.
 * - Rounds to 1 decimal place.
 */
export function normalizeReliabilityScore(rawScore: unknown, fallback: number = 0): number {
  const safeFallback =
    typeof fallback === 'number' && Number.isFinite(fallback)
      ? Math.max(0, Math.min(100, Math.round(fallback * 10) / 10))
      : 0;

  if (typeof rawScore !== 'number' || !Number.isFinite(rawScore)) {
    return safeFallback;
  }

  const clamped = Math.max(0, Math.min(100, rawScore));
  return Math.round(clamped * 10) / 10;
}

/**
 * Safely aggregates category complaint counts across raw records, brand distributions,
 * or category counts arrays.
 *
 * Edge cases handled:
 * - Duplicate categories: Case-insensitive and trimmed category normalization (e.g. 'battery_charging' and 'BATTERY_CHARGING' are merged)
 * - Accumulates duplicate entries properly without dropping counts or duplicate keys
 * - Undefined, null, NaN, or negative counts: Coerced safely to 0
 * - Zero total count: Percentages default to 0.0 without division by zero (NaN%)
 * - Null/undefined inputs or malformed items: Defensive fallback to empty record {}
 */
export function aggregateCategoryComplaintCounts(
  inputs?:
    | Array<{
        category?: string | DefectCategoryKey;
        category_key?: string;
        code?: string;
        defect_category?: string;
        count?: number | unknown;
        percentage?: number | unknown;
      } | null | undefined>
    | BrandReliability[]
    | ReliabilityTrendsDatabase
    | Record<string, { count?: number | unknown; percentage?: number | unknown } | number | unknown>
    | null
): Record<string, { count: number; percentage: number }> {
  if (!inputs) return {};

  const countMap = new Map<string, number>();

  const addCount = (rawKey: unknown, rawCount: unknown) => {
    if (!rawKey || typeof rawKey !== 'string') return;
    const key = rawKey.trim().toUpperCase();
    if (!key) return;

    let parsedCount = 0;
    if (typeof rawCount === 'number' && Number.isFinite(rawCount)) {
      parsedCount = Math.max(0, Math.floor(rawCount));
    } else if (typeof rawCount === 'string') {
      const num = Number(rawCount.trim());
      if (Number.isFinite(num)) {
        parsedCount = Math.max(0, Math.floor(num));
      }
    }

    countMap.set(key, (countMap.get(key) || 0) + parsedCount);
  };

  if (Array.isArray(inputs)) {
    for (const item of inputs) {
      if (!item || typeof item !== 'object') continue;

      // Case A: Item is a BrandReliability object with category_distribution
      if ('category_distribution' in item && item.category_distribution && typeof item.category_distribution === 'object') {
        const dist = item.category_distribution as Record<string, { count?: unknown } | number>;
        for (const [cat, val] of Object.entries(dist)) {
          if (val && typeof val === 'object' && 'count' in val) {
            addCount(cat, val.count);
          } else {
            addCount(cat, val);
          }
        }
        continue;
      }

      // Case B: Item is a category entry: { category / category_key / code / defect_category, count }
      const entry = item as Record<string, unknown>;
      const catKey =
        (typeof entry.category === 'string' && entry.category) ||
        (typeof entry.category_key === 'string' && entry.category_key) ||
        (typeof entry.code === 'string' && entry.code) ||
        (typeof entry.defect_category === 'string' && entry.defect_category) ||
        '';

      addCount(catKey, entry.count);
    }
  } else if (typeof inputs === 'object') {
    // Case C: inputs is a ReliabilityTrendsDatabase
    if ('brands' in inputs && Array.isArray((inputs as ReliabilityTrendsDatabase).brands)) {
      return aggregateCategoryComplaintCounts((inputs as ReliabilityTrendsDatabase).brands);
    }

    // Case D: inputs is a Record<string, { count?: unknown } | number>
    for (const [cat, val] of Object.entries(inputs)) {
      if (val && typeof val === 'object' && 'count' in val) {
        addCount(cat, (val as { count?: unknown }).count);
      } else {
        addCount(cat, val);
      }
    }
  }

  let totalCount = 0;
  for (const c of countMap.values()) {
    totalCount += c;
  }

  const result: Record<string, { count: number; percentage: number }> = {};
  for (const [key, count] of countMap.entries()) {
    const percentage = totalCount > 0 ? Math.round((count / totalCount) * 1000) / 10 : 0.0;
    result[key] = {
      count,
      percentage,
    };
  }

  return result;
}

/**
 * Returns a sorted array of aggregated category complaint items (highest count first).
 */
export function getAggregatedCategoryList(inputs?: unknown): CategoryComplaintItem[] {
  const record = aggregateCategoryComplaintCounts(inputs as Parameters<typeof aggregateCategoryComplaintCounts>[0]);
  return Object.entries(record)
    .map(([category, data]) => ({
      category,
      count: data.count,
      percentage: data.percentage,
    }))
    .sort((a, b) => b.count - a.count);
}

/**
 * Calculates trend direction and percentage change between current and previous periods.
 *
 * Edge cases handled:
 * - Division by zero (previous === 0):
 *   - If current > 0 and previous === 0: returns UP, +100.0% (finite growth, not Infinity)
 *   - If current === 0 and previous === 0: returns STABLE, 0.0% (not NaN from 0/0)
 *   - If current < 0 and previous === 0: returns DOWN, -100.0% (finite change, not -Infinity)
 * - Non-finite inputs (NaN, Infinity, -Infinity, null, undefined):
 *   - Safely coerced to 0, returning STABLE with 0.0% change
 * - Minor fluctuations within thresholdPct (default: 0.1%):
 *   - Classified as STABLE
 */
export function calculateTrendDirection(
  current: number | unknown,
  previous: number | unknown,
  thresholdPct: number = 0.1
): TrendCalculationResult {
  const safeCurrent = typeof current === 'number' && Number.isFinite(current) ? current : 0;
  const safePrevious = typeof previous === 'number' && Number.isFinite(previous) ? previous : 0;
  const safeThreshold =
    typeof thresholdPct === 'number' && Number.isFinite(thresholdPct)
      ? Math.max(0, thresholdPct)
      : 0.1;

  const absoluteChange = Math.round((safeCurrent - safePrevious) * 100) / 100;

  // Edge case: previous period is 0 (prevents division by zero, Infinity, and NaN)
  if (safePrevious === 0) {
    if (safeCurrent > 0) {
      return {
        direction: 'UP',
        percentageChange: 100,
        absoluteChange,
        formattedChange: '+100.0%',
        isIncrease: true,
        isDecrease: false,
        isStable: false,
      };
    }
    if (safeCurrent < 0) {
      return {
        direction: 'DOWN',
        percentageChange: -100,
        absoluteChange,
        formattedChange: '-100.0%',
        isIncrease: false,
        isDecrease: true,
        isStable: false,
      };
    }
    return {
      direction: 'STABLE',
      percentageChange: 0,
      absoluteChange: 0,
      formattedChange: '0.0%',
      isIncrease: false,
      isDecrease: false,
      isStable: true,
    };
  }

  // Normal calculation: ((current - previous) / Math.abs(safePrevious)) * 100
  const rawPctChange = ((safeCurrent - safePrevious) / Math.abs(safePrevious)) * 100;
  const pctChange = Number.isFinite(rawPctChange) ? Math.round(rawPctChange * 10) / 10 : 0;

  if (Math.abs(pctChange) <= safeThreshold) {
    return {
      direction: 'STABLE',
      percentageChange: 0,
      absoluteChange,
      formattedChange: '0.0%',
      isIncrease: false,
      isDecrease: false,
      isStable: true,
    };
  }

  if (pctChange > 0) {
    return {
      direction: 'UP',
      percentageChange: pctChange,
      absoluteChange,
      formattedChange: `+${pctChange.toFixed(1)}%`,
      isIncrease: true,
      isDecrease: false,
      isStable: false,
    };
  }

  return {
    direction: 'DOWN',
    percentageChange: pctChange,
    absoluteChange,
    formattedChange: `${pctChange.toFixed(1)}%`,
    isIncrease: false,
    isDecrease: true,
    isStable: false,
  };
}

/**
 * Calculates high-level KPI summary statistics from a ReliabilityTrendsDatabase.
 * Aggregates post counts, models count, industry average DSI, and determines
 * the top defect category using safe category complaint aggregation.
 */
export function calculateReliabilityKPIs(data?: ReliabilityTrendsDatabase | null): ReliabilityKPIs {
  const brands = Array.isArray(data?.brands) ? data.brands : [];
  const meta = data?.metadata;

  const totalAnalyzedPosts = Number.isFinite(meta?.total_records_analyzed)
    ? Math.max(0, meta!.total_records_analyzed!)
    : (Number.isFinite(meta?.total_analyzed_posts) ? Math.max(0, meta!.total_analyzed_posts!) : 0);

  const trackedBrandsCount = brands.length;
  let trackedModelsCount = 0;
  for (const b of brands) {
    if (Array.isArray(b?.models)) {
      trackedModelsCount += b.models.length;
    }
  }

  const industryAvgDsi = normalizeReliabilityScore(meta?.avg_industry_dsi, 0);

  // Determine top defect category via safe aggregation
  const aggregated = aggregateCategoryComplaintCounts(brands);
  let topDefectCategory = 'BATTERY_CHARGING';
  let maxCount = -1;

  for (const [catKey, val] of Object.entries(aggregated)) {
    if (val.count > maxCount) {
      maxCount = val.count;
      topDefectCategory = catKey;
    }
  }

  return {
    totalAnalyzedPosts,
    trackedBrandsCount,
    trackedModelsCount,
    industryAvgDsi,
    topDefectCategory,
  };
}

// ==========================================
// 3. MASTER DATA LOADER & DOMAIN RETRIEVAL
// ==========================================

/**
 * Fallback baseline in case JSON parsing encounters any anomaly.
 */
const DEFAULT_FALLBACK_DATABASE: ReliabilityTrendsDatabase = {
  metadata: {
    version: '1.0.0',
    updated_at: '2026-09-16T12:00:00Z',
    total_records_analyzed: 1280,
    brands_count: 9,
    models_count: 22,
    avg_industry_dsi: 64.2,
  },
  categories: [
    {
      code: 'BATTERY_CHARGING',
      label_ko: '배터리 & 고전압 충전',
      description: '고전압 배터리 셀 열화, 화재 리콜 위험, 급속/완속 충전 중단',
      icon_name: 'BatteryCharging',
      industry_share_pct: 38.4,
      avg_repair_cost_range: '2,500만 ~ 7,500만 원',
    },
    {
      code: 'DRIVING_POWERTRAIN',
      label_ko: '모터·감속기·ICCU 구동계',
      description: 'ICCU 폭파 및 주행 중 동력 상실, 감속기 기어 마모 소음',
      icon_name: 'Zap',
      industry_share_pct: 26.2,
      avg_repair_cost_range: '520만 ~ 1,450만 원',
    },
    {
      code: 'SOFTWARE_ELECTRONICS',
      label_ko: 'OTA·BMS·인포테인먼트',
      description: 'OTA 업데이트 벽돌 현상, BMS 오류로 인한 시동 불가',
      icon_name: 'Cpu',
      industry_share_pct: 14.8,
      avg_repair_cost_range: '150만 ~ 420만 원',
    },
    {
      code: 'BUILD_QUALITY',
      label_ko: '단차·도장·누수·조립 품질',
      description: '트렁크/도어 유격 단차, 우천 시 실내 누수, 테일램프 결로',
      icon_name: 'Wrench',
      industry_share_pct: 9.5,
      avg_repair_cost_range: '80만 ~ 350만 원',
    },
    {
      code: 'SERVICE_REPAIR_COST',
      label_ko: '보증 외 수리비 & 정비성',
      description: '부품 수급 지연, 경미한 하부 충격 시 배터리 전손 처리',
      icon_name: 'Coins',
      industry_share_pct: 6.1,
      avg_repair_cost_range: '200만 ~ 7,500만 원',
    },
    {
      code: 'COLD_WEATHER',
      label_ko: '혹한기 저온 결함 & 히트펌프',
      description: '영하 기온 시 히트펌프 옥토밸브 고착으로 난방 정지',
      icon_name: 'Snowflake',
      industry_share_pct: 5.0,
      avg_repair_cost_range: '320만 ~ 510만 원',
    },
  ],
  repair_cost_matrix: [],
  brands: [],
};

/**
 * Safely loads the master EV Reliability & Defect Trends database.
 * Strictly guarantees non-null, valid array/object shapes with defensive fallbacks
 * and bounds all DSI scores between [0, 100].
 */
export function getReliabilityTrendsData(): ReliabilityTrendsDatabase {
  try {
    if (!rawTrendsData) {
      return DEFAULT_FALLBACK_DATABASE;
    }

    const data = rawTrendsData as unknown as ReliabilityTrendsDatabase;

    const metadata = {
      version: data.metadata?.version || '1.0.0',
      updated_at: data.metadata?.updated_at || '2026-09-16T12:00:00Z',
      total_records_analyzed: Math.max(0, Number(data.metadata?.total_records_analyzed || 1280)),
      brands_count: Array.isArray(data.brands) ? data.brands.length : 9,
      models_count: Array.isArray(data.brands)
        ? data.brands.reduce((acc, b) => acc + (Array.isArray(b.models) ? b.models.length : 0), 0)
        : 22,
      avg_industry_dsi: normalizeReliabilityScore(data.metadata?.avg_industry_dsi, 64.2),
    };

    const categories = Array.isArray(data.categories) && data.categories.length > 0
      ? data.categories
      : DEFAULT_FALLBACK_DATABASE.categories;

    const repair_cost_matrix = Array.isArray(data.repair_cost_matrix)
      ? data.repair_cost_matrix
      : [];

    const brands = Array.isArray(data.brands)
      ? data.brands
          .filter((b): b is BrandReliability => Boolean(b && typeof b === 'object'))
          .map((b) => ({
            ...b,
            overall_dsi: normalizeReliabilityScore(b.overall_dsi, 50.0),
            total_reports: Math.max(0, Number.isFinite(b.total_reports) ? b.total_reports : 0),
            critical_issue_rate: Math.max(
              0,
              Math.min(100, Number.isFinite(b.critical_issue_rate) ? b.critical_issue_rate : 0)
            ),
            category_distribution: aggregateCategoryComplaintCounts(
              b.category_distribution && typeof b.category_distribution === 'object'
                ? b.category_distribution
                : {}
            ) as Record<DefectCategoryKey, { count: number; percentage: number }>,
            models: Array.isArray(b.models)
              ? b.models
                  .filter((m): m is ModelReliability => Boolean(m && typeof m === 'object'))
                  .map((m) => ({
                    ...m,
                    avg_dsi: normalizeReliabilityScore(m.avg_dsi, 50.0),
                    year_evaluations: Array.isArray(m.year_evaluations)
                      ? m.year_evaluations
                          .filter((y): y is YearEvaluation => Boolean(y && typeof y === 'object'))
                          .map((y) => ({
                            ...y,
                            dsi_score: normalizeReliabilityScore(y.dsi_score, 50.0),
                          }))
                      : [],
                  }))
              : [],
          }))
      : [];

    return {
      metadata,
      categories,
      repair_cost_matrix,
      brands,
    };
  } catch (error) {
    console.error('[getReliabilityTrendsData] Failed to load trends data safely:', error);
    return DEFAULT_FALLBACK_DATABASE;
  }
}

/**
 * Returns a flattened array of all models enriched with brand information.
 */
export function getAllEnrichedModels(data?: ReliabilityTrendsDatabase): EnrichedModelItem[] {
  const db = data || getReliabilityTrendsData();
  const result: EnrichedModelItem[] = [];
  const brands = Array.isArray(db?.brands) ? db.brands : [];

  for (const brand of brands) {
    if (!brand || typeof brand !== 'object') continue;
    const models = Array.isArray(brand.models) ? brand.models : [];
    for (const model of models) {
      if (!model || typeof model !== 'object') continue;
      result.push({
        ...model,
        avg_dsi: normalizeReliabilityScore(model.avg_dsi, 0),
        year_evaluations: Array.isArray(model.year_evaluations)
          ? model.year_evaluations
              .filter((y): y is YearEvaluation => Boolean(y && typeof y === 'object'))
              .map((y) => ({
                ...y,
                dsi_score: normalizeReliabilityScore(y.dsi_score, 0),
              }))
          : [],
        brand_name_ko: brand.name_ko || '',
        brand_name_en: brand.name_en || '',
        brand_country: brand.country || '',
      });
    }
  }

  return result;
}

/**
 * Returns badge styling and text for a given ModelYearVerdict.
 */
export function getVerdictBadgeInfo(verdict: ModelYearVerdict | string): {
  label: string;
  badgeClass: string;
  borderClass: string;
  bgClass: string;
  textClass: string;
  icon: string;
} {
  switch (verdict) {
    case 'AVOID':
      return {
        label: '🚫 구매 회피 (AVOID)',
        badgeClass: 'bg-rose-100 text-rose-800 border-rose-300',
        borderClass: 'border-rose-400',
        bgClass: 'bg-rose-500',
        textClass: 'text-rose-800',
        icon: '🚫',
      };
    case 'CAUTION':
      return {
        label: '⚠️ 주의 요망 (CAUTION)',
        badgeClass: 'bg-amber-100 text-amber-900 border-amber-300',
        borderClass: 'border-amber-400',
        bgClass: 'bg-amber-400',
        textClass: 'text-amber-900',
        icon: '⚠️',
      };
    case 'BUY_SAFE':
      return {
        label: '✅ 안심 추천 (BUY SAFE)',
        badgeClass: 'bg-emerald-100 text-emerald-800 border-emerald-300',
        borderClass: 'border-emerald-400',
        bgClass: 'bg-emerald-500',
        textClass: 'text-emerald-800',
        icon: '✅',
      };
    default:
      return {
        label: 'ℹ️ 정보 부족',
        badgeClass: 'bg-slate-100 text-slate-700 border-slate-300',
        borderClass: 'border-slate-300',
        bgClass: 'bg-slate-400',
        textClass: 'text-slate-700',
        icon: 'ℹ️',
      };
  }
}

/**
 * Returns severity description and color accents based on DSI score.
 */
export function getDsiSeverityLevel(dsi: number): {
  level: 'CRITICAL' | 'HIGH' | 'MODERATE' | 'LOW';
  label: string;
  colorClass: string;
  barBgClass: string;
  textColor: string;
} {
  const safeDsi = Number.isFinite(dsi) ? Math.max(0, dsi) : 0;
  const boundedDsi = Math.min(100, safeDsi);

  if (boundedDsi >= 80) {
    return {
      level: 'CRITICAL',
      label: '치명적 위험 (Critical)',
      colorClass: 'text-rose-700',
      barBgClass: 'bg-rose-500',
      textColor: 'text-rose-700',
    };
  }
  if (boundedDsi >= 60) {
    return {
      level: 'HIGH',
      label: '높은 결함률 (High Risk)',
      colorClass: 'text-amber-800',
      barBgClass: 'bg-amber-500',
      textColor: 'text-amber-800',
    };
  }
  if (boundedDsi >= 35) {
    return {
      level: 'MODERATE',
      label: '주의 필요 (Moderate)',
      colorClass: 'text-yellow-900',
      barBgClass: 'bg-yellow-400',
      textColor: 'text-yellow-900',
    };
  }
  return {
    level: 'LOW',
    label: '안정적 내구성 (Safe & Reliable)',
    colorClass: 'text-emerald-800',
    barBgClass: 'bg-emerald-500',
    textColor: 'text-emerald-800',
  };
}

/**
 * Returns styling for the overall grade badge.
 */
export function getGradeBadgeStyle(grade: 'A+' | 'A' | 'B' | 'C' | 'D' | 'F' | string): {
  bg: string;
  text: string;
  border: string;
} {
  switch (grade) {
    case 'A+':
    case 'A':
      return { bg: 'bg-emerald-100', text: 'text-emerald-800', border: 'border-emerald-300' };
    case 'B':
      return { bg: 'bg-blue-100', text: 'text-blue-800', border: 'border-blue-300' };
    case 'C':
      return { bg: 'bg-amber-100', text: 'text-amber-900', border: 'border-amber-300' };
    case 'D':
      return { bg: 'bg-orange-100', text: 'text-orange-900', border: 'border-orange-300' };
    case 'F':
      return { bg: 'bg-rose-100', text: 'text-rose-900', border: 'border-rose-300' };
    default:
      return { bg: 'bg-slate-100', text: 'text-slate-800', border: 'border-slate-300' };
  }
}

/**
 * Finds a specific model by ID from the reliability trends dataset,
 * gracefully handling missing, null, or malformed defect records.
 */
export function getModelReliabilityById(
  modelId: string,
  data?: ReliabilityTrendsDatabase
): EnrichedModelItem | undefined {
  if (!modelId || typeof modelId !== 'string') return undefined;
  const normalized = modelId.trim().toLowerCase().replace(/[\s\-_]+/g, '');
  if (!normalized) return undefined;
  const allModels = getAllEnrichedModels(data);
  return allModels.find((m) => {
    const mIdNorm = (m?.id || '').toLowerCase().replace(/[\s\-_]+/g, '');
    const mNameNorm = (m?.name || '').toLowerCase().replace(/[\s\-_]+/g, '');
    return (
      (mIdNorm.length > 0 &&
        (mIdNorm === normalized || normalized.includes(mIdNorm) || mIdNorm.includes(normalized))) ||
      (mNameNorm.length > 0 &&
        (mNameNorm.includes(normalized) || normalized.includes(mNameNorm)))
    );
  });
}

/**
 * Returns all year evaluations / defect records for a specific model,
 * ensuring the returned array is safe, non-null, and filtered of malformed entries.
 */
export function getDefectsForModel(
  modelId: string,
  data?: ReliabilityTrendsDatabase
): YearEvaluation[] {
  const model = getModelReliabilityById(modelId, data);
  if (!model || !Array.isArray(model.year_evaluations)) return [];
  return model.year_evaluations.filter((y) => Boolean(y && typeof y === 'object' && y.verdict));
}

/**
 * Finds a specific brand by ID or name from the reliability dataset.
 */
export function getBrandReliabilityById(
  brandId: string,
  data?: ReliabilityTrendsDatabase
): BrandReliability | undefined {
  if (!brandId || typeof brandId !== 'string') return undefined;
  const normalized = brandId.trim().toLowerCase();
  if (!normalized) return undefined;
  const db = data || getReliabilityTrendsData();
  const brands = Array.isArray(db?.brands) ? db.brands : [];
  return brands.find(
    (b) =>
      Boolean(b && typeof b === 'object') &&
      ((b.id && b.id.toLowerCase() === normalized) ||
        (b.name_ko && b.name_ko.toLowerCase().includes(normalized)) ||
        (b.name_en && b.name_en.toLowerCase().includes(normalized)))
  );
}
