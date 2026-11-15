/**
 * Pure calculation utilities, type definitions, and styling helpers for EV Reliability Analytics.
 * This module has ZERO dependencies on heavy JSON data files, enabling client bundles
 * to remain lean without duplicating data payloads.
 */

// ==========================================
// 1. DOMAIN ENUMS & INTERFACES (from @/types/reliability)
// ==========================================

import type {
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
  TrajectoryVerdict,
  PeriodicDefectInput,
  QuarterlyDefectBreakdown,
  MonthlyDefectBreakdown,
  ModelYearTrajectory,
} from '../types/reliability.ts';

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
  TrajectoryVerdict,
  PeriodicDefectInput,
  QuarterlyDefectBreakdown,
  MonthlyDefectBreakdown,
  ModelYearTrajectory,
};

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

  let parsed: number | null = null;
  if (typeof rawScore === 'number' && Number.isFinite(rawScore)) {
    parsed = rawScore;
  } else if (typeof rawScore === 'string') {
    const trimmed = rawScore.trim();
    if (trimmed !== '') {
      const num = Number(trimmed);
      if (Number.isFinite(num)) {
        parsed = num;
      }
    }
  }

  if (parsed === null) {
    return safeFallback;
  }

  const clamped = Math.max(0, Math.min(100, parsed));
  return Math.round(clamped * 10) / 10 + 0;
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
            addCount(cat, (val as { count?: unknown }).count);
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

  const rawMetaTotal = meta?.total_records_analyzed ?? meta?.total_analyzed_posts;
  let totalAnalyzedPosts =
    typeof rawMetaTotal === 'number' && Number.isFinite(rawMetaTotal) && rawMetaTotal > 0
      ? Math.floor(rawMetaTotal)
      : 0;

  // Single-brand or missing metadata fallback: sum across brand reports
  if (totalAnalyzedPosts === 0 && brands.length > 0) {
    for (const b of brands) {
      if (b && typeof b.total_reports === 'number' && Number.isFinite(b.total_reports) && b.total_reports > 0) {
        totalAnalyzedPosts += Math.floor(b.total_reports);
      }
    }
  }

  const trackedBrandsCount = brands.length;
  let trackedModelsCount = 0;
  for (const b of brands) {
    if (b && Array.isArray(b.models)) {
      trackedModelsCount += b.models.length;
    }
  }

  // Calculate industry / dataset average DSI
  let industryAvgDsi = 0;
  if (typeof meta?.avg_industry_dsi === 'number' && Number.isFinite(meta.avg_industry_dsi) && meta.avg_industry_dsi > 0) {
    industryAvgDsi = normalizeReliabilityScore(meta.avg_industry_dsi, 0);
  } else if (brands.length > 0) {
    // Dynamic calculation for single-brand or partial datasets
    let weightedDsiSum = 0;
    let totalDsiWeight = 0;
    let simpleDsiSum = 0;
    let validDsiCount = 0;

    for (const b of brands) {
      if (!b) continue;
      const bDsi = normalizeReliabilityScore(b.overall_dsi, 0);
      const bReports = typeof b.total_reports === 'number' && Number.isFinite(b.total_reports) && b.total_reports > 0
        ? b.total_reports
        : 0;

      if (bDsi > 0) {
        simpleDsiSum += bDsi;
        validDsiCount++;
        if (bReports > 0) {
          weightedDsiSum += bDsi * bReports;
          totalDsiWeight += bReports;
        }
      }
    }

    if (totalDsiWeight > 0) {
      industryAvgDsi = Math.round((weightedDsiSum / totalDsiWeight) * 10) / 10;
    } else if (validDsiCount > 0) {
      industryAvgDsi = Math.round((simpleDsiSum / validDsiCount) * 10) / 10;
    }
  }

  // Determine top defect category via safe aggregation
  const aggregated = aggregateCategoryComplaintCounts(brands);
  let topDefectCategory = 'BATTERY_CHARGING';
  let maxCount = 0;

  for (const [catKey, val] of Object.entries(aggregated)) {
    if (val.count > maxCount) {
      maxCount = val.count;
      topDefectCategory = catKey;
    }
  }

  if (maxCount === 0 && Object.keys(aggregated).length === 0) {
    topDefectCategory = 'NONE';
  }

  return {
    totalAnalyzedPosts,
    trackedBrandsCount,
    trackedModelsCount,
    industryAvgDsi,
    topDefectCategory,
    totalRecordsAnalyzed: totalAnalyzedPosts,
    brandsCount: trackedBrandsCount,
    modelsCount: trackedModelsCount,
    avgIndustryDsi: industryAvgDsi,
  };
}

// ==========================================
// 3. MODEL & BRAND RETRIEVAL UTILITIES
// ==========================================

/**
 * Returns a flattened array of all models enriched with brand information from a given database.
 * Pure function: operates directly on the provided data without importing raw JSON.
 */
export function getAllEnrichedModels(data?: ReliabilityTrendsDatabase): EnrichedModelItem[] {
  if (!data || !Array.isArray(data.brands)) return [];
  const result: EnrichedModelItem[] = [];
  const brands = data.brands;

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
 * Pure UI styling helper.
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
 * Pure UI calculation helper.
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
      barBgClass: 'bg-rose-600',
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
 * Pure UI styling helper.
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

  // Priority 1: Exact ID match
  const exactId = allModels.find((m) => {
    const mIdNorm = (m?.id || '').toLowerCase().replace(/[\s\-_]+/g, '');
    return mIdNorm === normalized;
  });
  if (exactId) return exactId;

  // Priority 2: Exact Name match
  const exactName = allModels.find((m) => {
    const mNameNorm = (m?.name || '').toLowerCase().replace(/[\s\-_]+/g, '');
    return mNameNorm === normalized;
  });
  if (exactName) return exactName;

  // Priority 3: Fallback substring match
  return allModels.find((m) => {
    const mIdNorm = (m?.id || '').toLowerCase().replace(/[\s\-_]+/g, '');
    const mNameNorm = (m?.name || '').toLowerCase().replace(/[\s\-_]+/g, '');
    return (
      (mIdNorm.length > 0 &&
        (mIdNorm.includes(normalized) || normalized.includes(mIdNorm))) ||
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
  return model.year_evaluations.filter((y: YearEvaluation) => Boolean(y && typeof y === 'object' && y.verdict));
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
  const brands = Array.isArray(data?.brands) ? data.brands : [];
  return brands.find(
    (b: BrandReliability) =>
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
 *
 * Mathematical properties:
 * - 0 complaints: strictly returns 0.0 (0% statistical confidence).
 * - Non-numeric, NaN, negative, null, or undefined complaints safely coerce to 0.0.
 * - Logarithmic saturation curve: ln(1 + n) / ln(1 + threshold) up to 1.0.
 * - Multiplied by year coverage factor (1 yr: 0.70, 2 yrs: 0.85, 3+ yrs: 1.00).
 * - Bounded strictly in [0.0, 1.0], rounded to 4 decimal places.
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

  // Logarithmic asymptotic saturation
  const sampleConfidence = Math.min(
    1.0,
    Math.log(1 + safeComplaints) / Math.log(1 + threshold)
  );

  // Year coverage factor (if specified)
  let yearFactor = 1.0;
  if (yearsEvaluated !== undefined && yearsEvaluated !== null) {
    let parsedYears: number | null = null;
    if (typeof yearsEvaluated === 'number' && Number.isFinite(yearsEvaluated)) {
      parsedYears = Math.floor(yearsEvaluated);
    } else if (typeof yearsEvaluated === 'string') {
      const num = Number(yearsEvaluated.trim());
      if (Number.isFinite(num)) parsedYears = Math.floor(num);
    }

    if (parsedYears !== null) {
      const safeYears = Math.max(0, parsedYears);
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
 *
 * Edge cases handled:
 * - 0 complaints: returns 0.0 without calculation errors.
 * - 0 or negative volume: returns 0.0 (prevents division by zero, NaN, or Infinity).
 * - Non-numeric or non-finite inputs: gracefully fall back to 0.0.
 * - Rounds to 2 decimal places.
 */
export function normalizeDefectFrequency(
  complaintCount: unknown,
  fleetOrSalesVolume: unknown,
  baselineScale: number = 1000
): number {
  let safeComplaints = 0;
  if (typeof complaintCount === 'number' && Number.isFinite(complaintCount)) {
    safeComplaints = Math.max(0, complaintCount);
  } else if (typeof complaintCount === 'string') {
    const num = Number(complaintCount.trim());
    if (Number.isFinite(num)) safeComplaints = Math.max(0, num);
  }

  let safeVolume = 0;
  if (typeof fleetOrSalesVolume === 'number' && Number.isFinite(fleetOrSalesVolume)) {
    safeVolume = Math.max(0, fleetOrSalesVolume);
  } else if (typeof fleetOrSalesVolume === 'string') {
    const num = Number(fleetOrSalesVolume.trim());
    if (Number.isFinite(num)) safeVolume = Math.max(0, num);
  }

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
 *
 * Weights critical categories (Battery, Powertrain) higher than cosmetic ones (Build Quality).
 * Safely handles empty input, zero complaints, and custom category weights.
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

  const weights: Record<string, number> = { ...DEFAULT_CATEGORY_SEVERITY_WEIGHTS };
  if (customWeights && typeof customWeights === 'object') {
    for (const [k, v] of Object.entries(customWeights)) {
      if (typeof k === 'string' && typeof v === 'number' && Number.isFinite(v) && v > 0) {
        weights[k.trim().toUpperCase() as DefectCategoryKey] = v;
      }
    }
  }

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

  let volume = 0;
  let scale = 1000;
  if (typeof totalVolumeOrReports === 'number' && Number.isFinite(totalVolumeOrReports)) {
    volume = Math.max(0, totalVolumeOrReports);
  } else if (typeof totalVolumeOrReports === 'string') {
    const num = Number(totalVolumeOrReports.trim());
    if (Number.isFinite(num)) volume = Math.max(0, num);
  } else if (totalVolumeOrReports && typeof totalVolumeOrReports === 'object') {
    const opts = totalVolumeOrReports as DefectFrequencyOptions;
    const rawV = opts.fleetOrSalesVolume ?? (opts as Record<string, unknown>).volume;
    if (typeof rawV === 'number' && Number.isFinite(rawV)) {
      volume = Math.max(0, rawV);
    } else if (typeof rawV === 'string') {
      const num = Number(rawV.trim());
      if (Number.isFinite(num)) volume = Math.max(0, num);
    }
    if (typeof opts.baselineScale === 'number' && Number.isFinite(opts.baselineScale) && opts.baselineScale > 0) {
      scale = opts.baselineScale;
    }
  }

  if (volume > 0) {
    return Math.round(((weightedSum / volume) * scale) * 100) / 100;
  }

  // Fallback to average severity multiplier
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
  if (safeScore >= 50.0) return 'C';
  if (safeScore >= 35.0) return 'D';
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
    return 'CAUTION'; // Insufficient statistical confidence defaults safely to CAUTION
  }
  if (safeScore >= 70.0) return 'BUY_SAFE';
  if (safeScore < 50.0) return 'AVOID';
  return 'CAUTION';
}

/**
 * Evaluates the Stealth Reliability Composite Score using multi-factor weighting:
 * - DSI (Defect Severity Index): default 50%
 * - Incident Rate (% vehicles affected): default 30%
 * - Critical Issue Rate (% safety-critical defects): default 20%
 *
 * Edge cases handled:
 * - 0 complaints: confidence is 0.0, smoothed score safely anchors to industry baseline without false 100% claims.
 * - Unknown brand or model: safe fallback defaults without crash.
 * - Non-finite or negative inputs: clamped defensively.
 * - Non-standard weights: automatically normalized to sum to 1.0.
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
  let safeComplaints = 0;
  if (typeof rawComplaints === 'number' && Number.isFinite(rawComplaints)) {
    safeComplaints = Math.max(0, Math.floor(rawComplaints));
  } else if (typeof rawComplaints === 'string') {
    const num = Number(rawComplaints.trim());
    if (Number.isFinite(num)) safeComplaints = Math.max(0, Math.floor(num));
  }

  const rawYears = input?.yearsEvaluated;
  let safeYears: number | undefined;
  if (typeof rawYears === 'number' && Number.isFinite(rawYears)) {
    safeYears = Math.max(0, Math.floor(rawYears));
  } else if (typeof rawYears === 'string') {
    const num = Number(rawYears.trim());
    if (Number.isFinite(num)) safeYears = Math.max(0, Math.floor(num));
  }

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

  // Raw defect penalty [0, 100]
  const rawDefectPenalty = wDsi * safeDsi + wInc * safeIncidentRate + wCrit * safeCriticalRate;
  const defectPenalty = Math.max(0, Math.min(100, Math.round(rawDefectPenalty * 10) / 10));

  // Raw stealth score (100 - defect penalty)
  const rawStealthScore = Math.round((100 - defectPenalty) * 10) / 10;

  // Statistical confidence score [0.0, 1.0]
  const confidenceScore = calculateReliabilityConfidence(safeComplaints, safeYears);

  // Industry baseline stealth score (default industry avg DSI is 64.2 -> stealth 35.8; neutral baseline is 50.0)
  const rawBaseline = input?.baselineIndustryDsi;
  const baselineDsi = rawBaseline !== undefined && rawBaseline !== null
    ? normalizeReliabilityScore(rawBaseline, 50.0)
    : 50.0;
  const baselineStealth = Math.round((100 - baselineDsi) * 10) / 10;

  // Smoothed stealth score prevents 0-complaint or untested models from claiming 100% perfection
  const smoothedStealth = Math.max(
    0,
    Math.min(
      100,
      Math.round((confidenceScore * rawStealthScore + (1 - confidenceScore) * baselineStealth) * 10) / 10
    )
  );

  // Volume-aware normalized defect frequency
  const rawVolume = input?.fleetOrSalesVolume ?? input?.fleetVolume ?? input?.salesVolume;
  const scale = typeof input?.baselineScale === 'number' && input.baselineScale > 0 ? input.baselineScale : 1000;
  const normalizedDefectFrequency = rawVolume !== undefined && rawVolume !== null
    ? normalizeDefectFrequency(safeComplaints, rawVolume, scale)
    : normalizeDefectFrequency(safeComplaints, 1000, 1000);

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
 * Returns undefined for unknown brands.
 */
export function resolveBrandReliability(
  brandQuery: string,
  data?: ReliabilityTrendsDatabase
): BrandReliability | undefined {
  if (!brandQuery || typeof brandQuery !== 'string') return undefined;
  const clean = brandQuery.trim().toLowerCase();
  if (!clean || clean === 'all') return undefined;

  const brands = Array.isArray(data?.brands) ? data.brands : [];
  if (brands.length === 0) return undefined;

  // Exact ID match
  const exact = brands.find((b) => b?.id?.toLowerCase() === clean);
  if (exact) return exact;

  // Exact name match
  const nameExact = brands.find(
    (b) => (b?.name_en || '').toLowerCase() === clean || (b?.name_ko || '').toLowerCase() === clean
  );
  if (nameExact) return nameExact;

  // Substring match
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

// ==========================================
// 6. DEFECT TREND AGGREGATION & PERIOD BREAKDOWN ALGORITHMS
// ==========================================

/**
 * Aggregates periodic defect inputs into quarterly breakdowns (Q1, Q2, Q3, Q4)
 * with chronologically ordered metrics, category distributions, QoQ growth trends,
 * and 3-quarter rolling moving averages.
 *
 * Edge cases handled:
 * - Empty/null/undefined inputs: returns empty array []
 * - 0 complaints in a quarter: safe 0% distribution without division by zero
 * - Single quarter dataset: STABLE 0.0% trend without previous period crash
 * - Missing DSI scores: defaults safely to neutral baseline 50.0
 * - Flexible period parsing: matches 'YYYY-QX', ISO date strings, or numeric { year, quarter/month }
 */
export function aggregateQuarterlyDefectBreakdown(
  inputs?: PeriodicDefectInput[] | null
): QuarterlyDefectBreakdown[] {
  if (!Array.isArray(inputs) || inputs.length === 0) return [];

  const groups = new Map<
    string,
    {
      year: number;
      quarter: 1 | 2 | 3 | 4;
      totalComplaints: number;
      dsiWeightedSum: number;
      dsiCount: number;
      categoryCounts: Map<string, number>;
    }
  >();

  let grandTotalComplaints = 0;

  for (const item of inputs) {
    if (!item || typeof item !== 'object') continue;

    let year: number | null = null;
    let quarter: (1 | 2 | 3 | 4) | null = null;

    // 1. Direct year and quarter fields
    if (item.year !== undefined && item.year !== null) {
      const y = Number(String(item.year).trim());
      if (Number.isFinite(y) && y >= 1990 && y <= 2100) year = Math.floor(y);
    }

    if (item.quarter !== undefined && item.quarter !== null) {
      const qStr = String(item.quarter).trim().toUpperCase();
      const match = qStr.match(/(?:Q|^)([1-4])/);
      if (match) {
        quarter = Number(match[1]) as 1 | 2 | 3 | 4;
      }
    }

    // 2. Month-based quarter derivation
    if (!quarter && item.month !== undefined && item.month !== null) {
      const m = Number(String(item.month).trim());
      if (Number.isFinite(m) && m >= 1 && m <= 12) {
        quarter = Math.ceil(m / 3) as 1 | 2 | 3 | 4;
      }
    }

    // 3. Date string or Date object parsing
    if ((!year || !quarter) && item.date) {
      const dateStr = item.date instanceof Date ? item.date.toISOString() : String(item.date).trim();
      const qMatch = dateStr.match(/^(\d{4})[-/. ]*Q([1-4])/i);
      if (qMatch) {
        year = Number(qMatch[1]);
        quarter = Number(qMatch[2]) as 1 | 2 | 3 | 4;
      } else {
        const dMatch = dateStr.match(/^(\d{4})[-/. ](\d{1,2})/);
        if (dMatch) {
          year = Number(dMatch[1]);
          const m = Number(dMatch[2]);
          if (m >= 1 && m <= 12) {
            quarter = Math.ceil(m / 3) as 1 | 2 | 3 | 4;
          }
        }
      }
    }

    if (!year || !quarter) continue;

    const periodKey = `${year}-Q${quarter}`;

    let parsedCount = 1;
    if (item.count !== undefined && item.count !== null) {
      const c = Number(String(item.count).trim());
      parsedCount = Number.isFinite(c) ? Math.max(0, Math.floor(c)) : 0;
    }

    let parsedDsi: number | null = null;
    if (item.dsiScore !== undefined && item.dsiScore !== null) {
      const d = Number(String(item.dsiScore).trim());
      if (Number.isFinite(d)) {
        parsedDsi = normalizeReliabilityScore(d, 50.0);
      }
    }

    const catKey = (
      (typeof item.category === 'string' && item.category) ||
      (typeof item.defectCategory === 'string' && item.defectCategory) ||
      'UNKNOWN'
    ).trim().toUpperCase();

    if (!groups.has(periodKey)) {
      groups.set(periodKey, {
        year,
        quarter,
        totalComplaints: 0,
        dsiWeightedSum: 0,
        dsiCount: 0,
        categoryCounts: new Map(),
      });
    }

    const g = groups.get(periodKey)!;
    g.totalComplaints += parsedCount;
    grandTotalComplaints += parsedCount;

    if (parsedDsi !== null) {
      g.dsiWeightedSum += parsedDsi * Math.max(1, parsedCount);
      g.dsiCount += Math.max(1, parsedCount);
    }

    if (parsedCount > 0) {
      g.categoryCounts.set(catKey, (g.categoryCounts.get(catKey) || 0) + parsedCount);
    }
  }

  // Sort chronologically by year and quarter
  const sortedKeys = Array.from(groups.keys()).sort((a, b) => {
    const [yA, qA] = a.split('-Q').map(Number);
    const [yB, qB] = b.split('-Q').map(Number);
    return yA !== yB ? yA - yB : qA - qB;
  });

  const results: QuarterlyDefectBreakdown[] = [];

  for (let i = 0; i < sortedKeys.length; i++) {
    const key = sortedKeys[i];
    const g = groups.get(key)!;

    const percentage = grandTotalComplaints > 0
      ? Math.round((g.totalComplaints / grandTotalComplaints) * 1000) / 10
      : 0.0;

    const avgDsi = g.dsiCount > 0
      ? Math.round((g.dsiWeightedSum / g.dsiCount) * 10) / 10
      : 50.0;

    let topCategory: DefectCategoryKey | string = 'BATTERY_CHARGING';
    let maxCatCount = 0;
    const categoryDistribution: Record<string, { count: number; percentage: number }> = {};

    for (const [cat, cnt] of g.categoryCounts.entries()) {
      categoryDistribution[cat] = {
        count: cnt,
        percentage: g.totalComplaints > 0 ? Math.round((cnt / g.totalComplaints) * 1000) / 10 : 0.0,
      };
      if (cnt > maxCatCount) {
        maxCatCount = cnt;
        topCategory = cat;
      }
    }

    if (maxCatCount === 0) {
      topCategory = 'NONE';
    }

    const previousCount = i > 0 ? groups.get(sortedKeys[i - 1])!.totalComplaints : g.totalComplaints;
    const trendFromPrevious = i > 0
      ? calculateTrendDirection(g.totalComplaints, previousCount)
      : {
          direction: 'STABLE' as const,
          percentageChange: 0,
          absoluteChange: 0,
          formattedChange: '0.0%',
          isIncrease: false,
          isDecrease: false,
          isStable: true,
        };

    // 3-quarter moving average
    const windowStart = Math.max(0, i - 2);
    let windowSum = 0;
    for (let w = windowStart; w <= i; w++) {
      windowSum += groups.get(sortedKeys[w])!.totalComplaints;
    }
    const movingAverage3Q = Math.round((windowSum / (i - windowStart + 1)) * 10) / 10;

    results.push({
      periodKey: key,
      year: g.year,
      quarter: g.quarter,
      totalComplaints: g.totalComplaints,
      percentage,
      avgDsi,
      topCategory,
      categoryDistribution,
      trendFromPrevious,
      movingAverage3Q,
    });
  }

  return results;
}

/**
 * Aggregates periodic defect inputs into monthly breakdowns (1 to 12)
 * with chronologically ordered metrics, category distributions, MoM growth trends,
 * and 3-month rolling moving averages.
 */
export function aggregateMonthlyDefectBreakdown(
  inputs?: PeriodicDefectInput[] | null
): MonthlyDefectBreakdown[] {
  if (!Array.isArray(inputs) || inputs.length === 0) return [];

  const groups = new Map<
    string,
    {
      year: number;
      month: number;
      totalComplaints: number;
      dsiWeightedSum: number;
      dsiCount: number;
      categoryCounts: Map<string, number>;
    }
  >();

  let grandTotalComplaints = 0;

  for (const item of inputs) {
    if (!item || typeof item !== 'object') continue;

    let year: number | null = null;
    let month: number | null = null;

    if (item.year !== undefined && item.year !== null) {
      const y = Number(String(item.year).trim());
      if (Number.isFinite(y) && y >= 1990 && y <= 2100) year = Math.floor(y);
    }

    if (item.month !== undefined && item.month !== null) {
      const m = Number(String(item.month).trim());
      if (Number.isFinite(m) && m >= 1 && m <= 12) month = Math.floor(m);
    }

    if ((!year || !month) && item.date) {
      const dateStr = item.date instanceof Date ? item.date.toISOString() : String(item.date).trim();
      const dMatch = dateStr.match(/^(\d{4})[-/. ](\d{1,2})/);
      if (dMatch) {
        year = Number(dMatch[1]);
        const m = Number(dMatch[2]);
        if (m >= 1 && m <= 12) month = m;
      }
    }

    if (!year || !month) continue;

    const periodKey = `${year}-${String(month).padStart(2, '0')}`;

    let parsedCount = 1;
    if (item.count !== undefined && item.count !== null) {
      const c = Number(String(item.count).trim());
      parsedCount = Number.isFinite(c) ? Math.max(0, Math.floor(c)) : 0;
    }

    let parsedDsi: number | null = null;
    if (item.dsiScore !== undefined && item.dsiScore !== null) {
      const d = Number(String(item.dsiScore).trim());
      if (Number.isFinite(d)) {
        parsedDsi = normalizeReliabilityScore(d, 50.0);
      }
    }

    const catKey = (
      (typeof item.category === 'string' && item.category) ||
      (typeof item.defectCategory === 'string' && item.defectCategory) ||
      'UNKNOWN'
    ).trim().toUpperCase();

    if (!groups.has(periodKey)) {
      groups.set(periodKey, {
        year,
        month,
        totalComplaints: 0,
        dsiWeightedSum: 0,
        dsiCount: 0,
        categoryCounts: new Map(),
      });
    }

    const g = groups.get(periodKey)!;
    g.totalComplaints += parsedCount;
    grandTotalComplaints += parsedCount;

    if (parsedDsi !== null) {
      g.dsiWeightedSum += parsedDsi * Math.max(1, parsedCount);
      g.dsiCount += Math.max(1, parsedCount);
    }

    if (parsedCount > 0) {
      g.categoryCounts.set(catKey, (g.categoryCounts.get(catKey) || 0) + parsedCount);
    }
  }

  const sortedKeys = Array.from(groups.keys()).sort();
  const results: MonthlyDefectBreakdown[] = [];

  for (let i = 0; i < sortedKeys.length; i++) {
    const key = sortedKeys[i];
    const g = groups.get(key)!;

    const percentage = grandTotalComplaints > 0
      ? Math.round((g.totalComplaints / grandTotalComplaints) * 1000) / 10
      : 0.0;

    const avgDsi = g.dsiCount > 0
      ? Math.round((g.dsiWeightedSum / g.dsiCount) * 10) / 10
      : 50.0;

    let topCategory: DefectCategoryKey | string = 'BATTERY_CHARGING';
    let maxCatCount = 0;
    const categoryDistribution: Record<string, { count: number; percentage: number }> = {};

    for (const [cat, cnt] of g.categoryCounts.entries()) {
      categoryDistribution[cat] = {
        count: cnt,
        percentage: g.totalComplaints > 0 ? Math.round((cnt / g.totalComplaints) * 1000) / 10 : 0.0,
      };
      if (cnt > maxCatCount) {
        maxCatCount = cnt;
        topCategory = cat;
      }
    }

    if (maxCatCount === 0) {
      topCategory = 'NONE';
    }

    const previousCount = i > 0 ? groups.get(sortedKeys[i - 1])!.totalComplaints : g.totalComplaints;
    const trendFromPrevious = i > 0
      ? calculateTrendDirection(g.totalComplaints, previousCount)
      : {
          direction: 'STABLE' as const,
          percentageChange: 0,
          absoluteChange: 0,
          formattedChange: '0.0%',
          isIncrease: false,
          isDecrease: false,
          isStable: true,
        };

    const windowStart = Math.max(0, i - 2);
    let windowSum = 0;
    for (let w = windowStart; w <= i; w++) {
      windowSum += groups.get(sortedKeys[w])!.totalComplaints;
    }
    const movingAverage3M = Math.round((windowSum / (i - windowStart + 1)) * 10) / 10;

    results.push({
      periodKey: key,
      year: g.year,
      month: g.month,
      monthLabel: `${g.year}년 ${g.month}월`,
      totalComplaints: g.totalComplaints,
      percentage,
      avgDsi,
      topCategory,
      categoryDistribution,
      trendFromPrevious,
      movingAverage3M,
    });
  }

  return results;
}

/**
 * Analyzes multi-year defect trajectories for a specific vehicle model, evaluating:
 * - DSI reduction/deterioration progression over consecutive model years
 * - Trajectory classification: RAPIDLY_IMPROVING, IMPROVING, STABLE, DEGRADING, CRITICALLY_DEGRADING
 * - Identification of chronic defect categories persisting across 2+ model years
 * - Safe vs. risk model year boundaries
 */
export function calculateModelYearDefectTrajectory(
  model: ModelReliability | EnrichedModelItem | YearEvaluation[] | null | undefined,
  modelMeta?: { id?: string; name?: string; brand?: string }
): ModelYearTrajectory {
  let evals: YearEvaluation[] = [];
  let mId = modelMeta?.id || 'unknown_model';
  let mName = modelMeta?.name || '미확인 차종';
  let bName = modelMeta?.brand || '';

  if (Array.isArray(model)) {
    evals = model;
  } else if (model && typeof model === 'object') {
    if (Array.isArray(model.year_evaluations)) {
      evals = model.year_evaluations;
    }
    if (model.id) mId = model.id;
    if (model.name) mName = model.name;
    if ('brand_name_ko' in model && model.brand_name_ko) bName = model.brand_name_ko;
  }

  const validEvals = evals
    .filter((e): e is YearEvaluation => Boolean(e && typeof e === 'object' && Number.isFinite(e.year)))
    .map((e) => ({
      ...e,
      year: Math.floor(e.year),
      dsi_score: normalizeReliabilityScore(e.dsi_score, 50.0),
      incident_rate: typeof e.incident_rate === 'number' && Number.isFinite(e.incident_rate)
        ? Math.max(0, Math.min(100, e.incident_rate))
        : 0,
    }))
    .sort((a, b) => a.year - b.year);

  if (validEvals.length === 0) {
    return {
      modelId: mId,
      modelName: mName,
      brandName: bName,
      trackedYears: [],
      initialDsi: 50.0,
      latestDsi: 50.0,
      overallDsiChange: {
        direction: 'STABLE',
        percentageChange: 0,
        absoluteChange: 0,
        formattedChange: '0.0%',
        isIncrease: false,
        isDecrease: false,
        isStable: true,
      },
      trajectoryVerdict: 'STABLE',
      peakRiskYear: null,
      peakRiskDsi: 50.0,
      safestYear: null,
      safestDsi: 50.0,
      chronicCategories: [],
      yearOverYearProgression: [],
    };
  }

  const initialDsi = validEvals[0].dsi_score;
  const latestDsi = validEvals[validEvals.length - 1].dsi_score;
  const overallDsiChange = calculateTrendDirection(latestDsi, initialDsi);

  let peakRiskYear = validEvals[0].year;
  let peakRiskDsi = validEvals[0].dsi_score;
  let safestYear = validEvals[0].year;
  let safestDsi = validEvals[0].dsi_score;

  const chronicMap = new Map<string, number>();
  const progression: ModelYearTrajectory['yearOverYearProgression'] = [];

  for (let i = 0; i < validEvals.length; i++) {
    const curr = validEvals[i];
    if (curr.dsi_score > peakRiskDsi) {
      peakRiskDsi = curr.dsi_score;
      peakRiskYear = curr.year;
    }
    if (curr.dsi_score < safestDsi) {
      safestDsi = curr.dsi_score;
      safestYear = curr.year;
    }

    if (Array.isArray(curr.chronic_symptoms)) {
      for (const sym of curr.chronic_symptoms) {
        if (typeof sym === 'string' && sym.trim()) {
          chronicMap.set(sym.trim(), (chronicMap.get(sym.trim()) || 0) + 1);
        }
      }
    }

    const prevDsi = i > 0 ? validEvals[i - 1].dsi_score : curr.dsi_score;
    const trendFromPreviousYear = i > 0
      ? calculateTrendDirection(curr.dsi_score, prevDsi)
      : {
          direction: 'STABLE' as const,
          percentageChange: 0,
          absoluteChange: 0,
          formattedChange: '0.0%',
          isIncrease: false,
          isDecrease: false,
          isStable: true,
        };

    progression.push({
      year: curr.year,
      dsi: curr.dsi_score,
      verdict: curr.verdict || 'CAUTION',
      incidentRate: curr.incident_rate,
      primaryDefect: curr.primary_defect || '',
      trendFromPreviousYear,
    });
  }

  // Trajectory classification based on DSI reduction/increase
  const dsiDelta = latestDsi - initialDsi; // negative = improvement
  let trajectoryVerdict: TrajectoryVerdict = 'STABLE';
  if (dsiDelta <= -30) {
    trajectoryVerdict = 'RAPIDLY_IMPROVING';
  } else if (dsiDelta <= -5) {
    trajectoryVerdict = 'IMPROVING';
  } else if (dsiDelta >= 20) {
    trajectoryVerdict = 'CRITICALLY_DEGRADING';
  } else if (dsiDelta >= 5) {
    trajectoryVerdict = 'DEGRADING';
  } else {
    trajectoryVerdict = 'STABLE';
  }

  // Chronic symptoms persisting in 2 or more model years
  const chronicCategories = Array.from(chronicMap.entries())
    .filter(([, count]) => count >= 2)
    .sort((a, b) => b[1] - a[1])
    .map(([sym]) => sym);

  return {
    modelId: mId,
    modelName: mName,
    brandName: bName,
    trackedYears: validEvals.map((e) => e.year),
    initialDsi,
    latestDsi,
    overallDsiChange,
    trajectoryVerdict,
    peakRiskYear,
    peakRiskDsi,
    safestYear,
    safestDsi,
    chronicCategories,
    yearOverYearProgression: progression,
  };
}

/**
 * Unified defect trend aggregator that supports both monthly and quarterly period breakdown.
 */
export function aggregateDefectTrendsByPeriod(
  inputs?: PeriodicDefectInput[] | null,
  periodType: 'MONTH' | 'QUARTER' = 'QUARTER'
): QuarterlyDefectBreakdown[] | MonthlyDefectBreakdown[] {
  if (periodType === 'MONTH') {
    return aggregateMonthlyDefectBreakdown(inputs);
  }
  return aggregateQuarterlyDefectBreakdown(inputs);
}
