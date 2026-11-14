import rawTrendsData from '../data/ev_reliability_trends.json' with { type: 'json' };

// ==========================================
// 1. DOMAIN ENUMS & INTERFACES (from @/types/reliability)
// ==========================================

export type {
  DefectCategoryKey,
  ModelYearVerdict,
  OverallReliabilityGrade,
  OutOfWarrantyRisk,
  TrendDirection,
  TrendCalculationResult,
  CategoryComplaintItem,
  CategoryComplaintInputEntry,
  YearEvaluation,
  ModelReliability,
  BrandReliability,
  DefectCategoryMetadata,
  RepairCostMatrixItem,
  ReliabilityTrendsDatabase,
  EnrichedModelItem,
  ReliabilityKPIs,
  StealthScoreWeights,
  StealthScoreInput,
  StealthScoreResult,
  DefectFrequencyOptions,
} from '../types/reliability.ts';

import type {
  DefectCategoryKey,
  ModelYearVerdict,
  OverallReliabilityGrade,
  TrendCalculationResult,
  CategoryComplaintItem,
  CategoryComplaintInputEntry,
  YearEvaluation,
  ModelReliability,
  BrandReliability,
  ReliabilityTrendsDatabase,
  EnrichedModelItem,
  ReliabilityKPIs,
  StealthScoreWeights,
  StealthScoreInput,
  StealthScoreResult,
} from '../types/reliability.ts';

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
    | Array<CategoryComplaintInputEntry | null | undefined>
    | BrandReliability[]
    | ReliabilityTrendsDatabase
    | Record<string, { count?: number | string | null; percentage?: number | string | null } | number | unknown>
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
    if (b && Array.isArray(b.models)) {
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

    const rawTotal = Number(data?.metadata?.total_records_analyzed ?? (data?.metadata as unknown as Record<string, unknown>)?.total_analyzed_posts);
    const total_records_analyzed = Number.isFinite(rawTotal) && rawTotal >= 0 ? Math.floor(rawTotal) : 1280;

    const metadata = {
      version: typeof data?.metadata?.version === 'string' ? data.metadata.version : '1.0.0',
      updated_at: typeof data?.metadata?.updated_at === 'string' ? data.metadata.updated_at : '2026-09-16T12:00:00Z',
      total_records_analyzed,
      brands_count: Array.isArray(data?.brands) ? data.brands.length : 9,
      models_count: Array.isArray(data?.brands)
        ? data.brands.reduce((acc, b) => acc + (b && Array.isArray(b.models) ? b.models.length : 0), 0)
        : 22,
      avg_industry_dsi: normalizeReliabilityScore(data?.metadata?.avg_industry_dsi, 64.2),
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

// ==========================================
// 4. STEALTH SCORE, DEFECT FREQUENCY & CONFIDENCE ALGORITHMS
// ==========================================

export const DEFAULT_CATEGORY_SEVERITY_WEIGHTS: Readonly<Record<DefectCategoryKey, number>> = Object.freeze({
  BATTERY_CHARGING: 2.5,
  DRIVING_POWERTRAIN: 2.0,
  COLD_WEATHER: 1.4,
  SERVICE_REPAIR_COST: 1.2,
  SOFTWARE_ELECTRONICS: 1.0,
  BUILD_QUALITY: 0.7,
});

export const DEFAULT_STEALTH_SCORE_WEIGHTS: Readonly<Required<StealthScoreWeights>> = Object.freeze({
  dsiWeight: 0.50,
  incidentWeight: 0.30,
  criticalWeight: 0.20,
});

/**
 * Calculates statistical confidence for reliability calculations based on complaint count
 * and multi-year tracking coverage.
 */
export function calculateReliabilityConfidence(
  complaintCount: unknown,
  yearsEvaluated?: unknown,
  minSampleThreshold: number = 50
): number {
  if (typeof complaintCount !== 'number' || !Number.isFinite(complaintCount) || complaintCount <= 0) {
    return 0.0;
  }

  const safeComplaints = Math.max(0, Math.floor(complaintCount));
  if (safeComplaints === 0) return 0.0;

  const threshold =
    typeof minSampleThreshold === 'number' && Number.isFinite(minSampleThreshold) && minSampleThreshold > 0
      ? minSampleThreshold
      : 50;

  const sampleConfidence = Math.min(
    1.0,
    Math.log(1 + safeComplaints) / Math.log(1 + threshold)
  );

  let yearFactor = 1.0;
  if (yearsEvaluated !== undefined && yearsEvaluated !== null) {
    if (typeof yearsEvaluated === 'number' && Number.isFinite(yearsEvaluated)) {
      const safeYears = Math.max(0, Math.floor(yearsEvaluated));
      if (safeYears === 0) yearFactor = 0.0;
      else if (safeYears === 1) yearFactor = 0.70;
      else if (safeYears === 2) yearFactor = 0.85;
      else yearFactor = 1.00;
    } else {
      yearFactor = 0.70;
    }
  }

  const combined = Math.max(0.0, Math.min(1.0, sampleConfidence * yearFactor));
  return Math.round(combined * 10000) / 10000;
}

/**
 * Normalizes defect complaint counts against vehicle sales, registrations, or fleet size.
 */
export function normalizeDefectFrequency(
  complaintCount: unknown,
  fleetOrSalesVolume: unknown,
  baselineScale: number = 1000
): number {
  const safeComplaints =
    typeof complaintCount === 'number' && Number.isFinite(complaintCount)
      ? Math.max(0, complaintCount)
      : 0;

  const safeVolume =
    typeof fleetOrSalesVolume === 'number' && Number.isFinite(fleetOrSalesVolume)
      ? Math.max(0, fleetOrSalesVolume)
      : 0;

  if (safeComplaints === 0 || safeVolume === 0) {
    return 0.0;
  }

  const safeScale =
    typeof baselineScale === 'number' && Number.isFinite(baselineScale) && baselineScale > 0
      ? baselineScale
      : 1000;

  const frequency = (safeComplaints / safeVolume) * safeScale;
  return Number.isFinite(frequency) ? Math.round(frequency * 100) / 100 : 0.0;
}

/**
 * Calculates a severity-weighted defect frequency across categories.
 */
export function calculateWeightedDefectFrequency(
  categoryInputs?: unknown,
  totalVolumeOrReports?: unknown,
  customWeights?: Record<string, number>
): number {
  const aggregated = aggregateCategoryComplaintCounts(
    categoryInputs as Parameters<typeof aggregateCategoryComplaintCounts>[0]
  );

  let totalComplaints = 0;
  let weightedSum = 0;

  const weights: Record<string, number> = {
    ...DEFAULT_CATEGORY_SEVERITY_WEIGHTS,
    ...(customWeights && typeof customWeights === 'object' ? customWeights : {}),
  };

  for (const [cat, data] of Object.entries(aggregated)) {
    const count = data.count || 0;
    if (count <= 0) continue;
    totalComplaints += count;
    const weight =
      typeof weights[cat] === 'number' && Number.isFinite(weights[cat]) && weights[cat] > 0
        ? weights[cat]
        : 1.0;
    weightedSum += count * weight;
  }

  if (totalComplaints === 0 || weightedSum === 0) {
    return 0.0;
  }

  const volume =
    typeof totalVolumeOrReports === 'number' && Number.isFinite(totalVolumeOrReports)
      ? Math.max(0, totalVolumeOrReports)
      : 0;

  if (volume > 0) {
    return Math.round((weightedSum / volume) * 100000) / 100;
  }

  return Math.round((weightedSum / totalComplaints) * 100) / 100;
}

/**
 * Derives an overall reliability grade (A+ through F) from a composite stealth score.
 */
export function deriveGradeFromStealthScore(score: unknown): OverallReliabilityGrade {
  const safeScore = normalizeReliabilityScore(score, 50.0);
  if (safeScore >= 90.0) return 'A+';
  if (safeScore >= 80.0) return 'A';
  if (safeScore >= 68.0) return 'B';
  if (safeScore >= 52.0) return 'C';
  if (safeScore >= 38.0) return 'D';
  return 'F';
}

/**
 * Derives a purchase recommendation verdict from a composite stealth score and confidence.
 */
export function deriveVerdictFromStealthScore(
  score: unknown,
  confidenceScore: number = 1.0
): ModelYearVerdict {
  const safeScore = normalizeReliabilityScore(score, 50.0);
  const safeConf =
    typeof confidenceScore === 'number' && Number.isFinite(confidenceScore)
      ? Math.max(0, Math.min(1, confidenceScore))
      : 1.0;

  if (safeConf < 0.25) {
    return 'CAUTION';
  }
  if (safeScore >= 70.0) return 'BUY_SAFE';
  if (safeScore < 50.0) return 'AVOID';
  return 'CAUTION';
}

/**
 * Evaluates the Stealth Reliability Composite Score using multi-factor weighting.
 * Defaults baselineIndustryDsi to current master trends dataset if omitted.
 */
export function calculateStealthScore(input?: StealthScoreInput | null): StealthScoreResult {
  const safeDsi = normalizeReliabilityScore(input?.dsi, 50.0);
  const safeIncidentRate =
    typeof input?.incidentRate === 'number' && Number.isFinite(input.incidentRate)
      ? Math.max(0, Math.min(100, input.incidentRate))
      : 0.0;
  const safeCriticalRate =
    typeof input?.criticalIssueRate === 'number' && Number.isFinite(input.criticalIssueRate)
      ? Math.max(0, Math.min(100, input.criticalIssueRate))
      : 0.0;

  const rawComplaints = input?.totalComplaints;
  const safeComplaints =
    typeof rawComplaints === 'number' && Number.isFinite(rawComplaints)
      ? Math.max(0, Math.floor(rawComplaints))
      : 0;

  const safeYears =
    typeof input?.yearsEvaluated === 'number' && Number.isFinite(input.yearsEvaluated)
      ? Math.max(0, Math.floor(input.yearsEvaluated))
      : undefined;

  // Weight validation and normalization
  let hasInvalidWeight = false;
  const rawWDsi = input?.weights?.dsiWeight;
  const rawWInc = input?.weights?.incidentWeight;
  const rawWCrit = input?.weights?.criticalWeight;

  if (input?.weights && typeof input.weights === 'object') {
    if (
      (rawWDsi !== undefined && (!Number.isFinite(rawWDsi) || (rawWDsi as number) < 0)) ||
      (rawWInc !== undefined && (!Number.isFinite(rawWInc) || (rawWInc as number) < 0)) ||
      (rawWCrit !== undefined && (!Number.isFinite(rawWCrit) || (rawWCrit as number) < 0))
    ) {
      hasInvalidWeight = true;
    }
  }

  let wDsi = !hasInvalidWeight && typeof rawWDsi === 'number' && Number.isFinite(rawWDsi) && rawWDsi >= 0
    ? rawWDsi
    : DEFAULT_STEALTH_SCORE_WEIGHTS.dsiWeight;
  let wInc = !hasInvalidWeight && typeof rawWInc === 'number' && Number.isFinite(rawWInc) && rawWInc >= 0
    ? rawWInc
    : DEFAULT_STEALTH_SCORE_WEIGHTS.incidentWeight;
  let wCrit = !hasInvalidWeight && typeof rawWCrit === 'number' && Number.isFinite(rawWCrit) && rawWCrit >= 0
    ? rawWCrit
    : DEFAULT_STEALTH_SCORE_WEIGHTS.criticalWeight;

  const totalWeight = wDsi + wInc + wCrit;
  if (totalWeight <= 0 || hasInvalidWeight) {
    wDsi = DEFAULT_STEALTH_SCORE_WEIGHTS.dsiWeight;
    wInc = DEFAULT_STEALTH_SCORE_WEIGHTS.incidentWeight;
    wCrit = DEFAULT_STEALTH_SCORE_WEIGHTS.criticalWeight;
  } else {
    wDsi /= totalWeight;
    wInc /= totalWeight;
    wCrit /= totalWeight;
  }

  const rawDefectPenalty = wDsi * safeDsi + wInc * safeIncidentRate + wCrit * safeCriticalRate;
  const defectPenalty = Math.max(0, Math.min(100, Math.round(rawDefectPenalty * 10) / 10));

  const rawStealthScore = Math.round((100 - defectPenalty) * 10) / 10;
  const confidenceScore = calculateReliabilityConfidence(safeComplaints, safeYears);

  let baselineIndustry = input?.baselineIndustryDsi;
  if (baselineIndustry === undefined || baselineIndustry === null) {
    try {
      const db = getReliabilityTrendsData();
      baselineIndustry = db?.metadata?.avg_industry_dsi ?? 64.2;
    } catch {
      baselineIndustry = 64.2;
    }
  }

  const baselineDsi = normalizeReliabilityScore(baselineIndustry, 64.2);
  const baselineStealth = Math.round((100 - baselineDsi) * 10) / 10;

  const smoothedStealth = Math.max(
    0,
    Math.min(
      100,
      Math.round((confidenceScore * rawStealthScore + (1 - confidenceScore) * baselineStealth) * 10) / 10
    )
  );

  const normalizedDefectFrequency = normalizeDefectFrequency(safeComplaints, 1000, 1000);
  const recommendedVerdict = deriveVerdictFromStealthScore(smoothedStealth, confidenceScore);
  const overallGrade = deriveGradeFromStealthScore(smoothedStealth);

  return {
    rawStealthScore,
    stealthScore: smoothedStealth,
    defectPenalty,
    confidenceScore,
    normalizedDefectFrequency,
    recommendedVerdict,
    overallGrade,
    isHighConfidence: confidenceScore >= 0.70,
  };
}

// ==========================================
// 5. BOUNDARY CONDITION HELPERS & SAFE DEFAULTS
// ==========================================

/**
 * Returns a specific year evaluation for a model, safely handling missing years,
 * unknown models, or non-numeric year inputs without throwing.
 */
export function getModelYearEvaluation(
  modelId: string,
  year: number | string,
  data?: ReliabilityTrendsDatabase
): YearEvaluation | undefined {
  if (!modelId || typeof modelId !== 'string') return undefined;
  const numYear = typeof year === 'number' ? year : Number(String(year || '').trim());
  if (!Number.isFinite(numYear)) return undefined;

  const defects = getDefectsForModel(modelId, data);
  if (!defects || defects.length === 0) return undefined;

  const target = defects.find((y) => y && Number.isFinite(y.year) && Math.floor(y.year) === Math.floor(numYear));
  if (!target) return undefined;

  return {
    ...target,
    year: Math.floor(target.year),
    dsi_score: normalizeReliabilityScore(target.dsi_score, 50.0),
    incident_rate:
      typeof target.incident_rate === 'number' && Number.isFinite(target.incident_rate)
        ? Math.max(0, Math.min(100, target.incident_rate))
        : 0,
    chronic_symptoms: Array.isArray(target.chronic_symptoms) ? target.chronic_symptoms : [],
    primary_defect: typeof target.primary_defect === 'string' ? target.primary_defect : '',
    estimated_repair_cost: typeof target.estimated_repair_cost === 'string' ? target.estimated_repair_cost : '',
    raw_quote: typeof target.raw_quote === 'string' ? target.raw_quote : '',
  };
}

/**
 * Safe fuzzy brand resolver that matches ID, Korean name, English name, or standard alias.
 */
export function resolveBrandReliability(
  brandQuery: string,
  data?: ReliabilityTrendsDatabase
): BrandReliability | undefined {
  if (!brandQuery || typeof brandQuery !== 'string') return undefined;
  const clean = brandQuery.trim().toLowerCase();
  if (!clean || clean === 'all') return undefined;

  const db = data || getReliabilityTrendsData();
  const brands = Array.isArray(db?.brands) ? db.brands : [];
  if (brands.length === 0) return undefined;

  const exact = brands.find((b) => b?.id?.toLowerCase() === clean);
  if (exact) return exact;

  const nameExact = brands.find(
    (b) => (b?.name_en || '').toLowerCase() === clean || (b?.name_ko || '').toLowerCase() === clean
  );
  if (nameExact) return nameExact;

  return brands.find((b) => {
    if (!b) return false;
    const en = (b.name_en || '').toLowerCase();
    const ko = (b.name_ko || '').toLowerCase();
    return (
      (en.length > 0 && (en.includes(clean) || clean.includes(en))) ||
      (ko.length > 0 && (ko.includes(clean) || clean.includes(ko)))
    );
  });
}

/**
 * Returns a robust fallback BrandReliability object for unknown or unlisted brands.
 */
export function getSafeDefaultBrandReliability(brandId: string = 'unknown'): BrandReliability {
  const safeId = typeof brandId === 'string' && brandId.trim() ? brandId.trim().toLowerCase() : 'unknown';
  return {
    id: safeId,
    name_ko: '미확인 브랜드',
    name_en: 'Unknown Brand',
    country: 'UNKNOWN',
    overall_dsi: 50.0,
    total_reports: 0,
    critical_issue_rate: 0.0,
    category_distribution: {
      BATTERY_CHARGING: { count: 0, percentage: 0.0 },
      DRIVING_POWERTRAIN: { count: 0, percentage: 0.0 },
      SOFTWARE_ELECTRONICS: { count: 0, percentage: 0.0 },
      BUILD_QUALITY: { count: 0, percentage: 0.0 },
      SERVICE_REPAIR_COST: { count: 0, percentage: 0.0 },
      COLD_WEATHER: { count: 0, percentage: 0.0 },
    },
    models: [],
  };
}

/**
 * Returns a requested brand or safe default fallback if the brand is unknown.
 */
export function getBrandWithFallback(
  brandId: string,
  fallback?: BrandReliability,
  data?: ReliabilityTrendsDatabase
): BrandReliability {
  const resolved = resolveBrandReliability(brandId, data) || getBrandReliabilityById(brandId, data);
  if (resolved) return resolved;
  return fallback || getSafeDefaultBrandReliability(brandId);
}

/**
 * Returns a robust fallback EnrichedModelItem object for unknown or unlisted models.
 */
export function getSafeDefaultModelReliability(
  modelId: string = 'unknown_model',
  brandId: string = 'unknown'
): EnrichedModelItem {
  const safeId = typeof modelId === 'string' && modelId.trim() ? modelId.trim().toLowerCase() : 'unknown_model';
  return {
    id: safeId,
    name: '미확인 차종',
    segment: '미분류',
    brand_id: brandId || 'unknown',
    overall_grade: 'C',
    avg_dsi: 50.0,
    top_category: 'BATTERY_CHARGING',
    year_evaluations: [],
    brand_name_ko: '미확인 브랜드',
    brand_name_en: 'Unknown Brand',
    brand_country: 'UNKNOWN',
  };
}
