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
 * Parses a number or non-empty numeric string into a finite number, or returns null.
 * Rejects empty/whitespace strings, NaN, Infinity, booleans, and objects.
 */
export function parseFiniteNumber(val: unknown): number | null {
  if (typeof val === 'number') {
    if (!Number.isFinite(val)) return null;
    return val === 0 ? 0 : val;
  }
  if (typeof val === 'string') {
    const trimmed = val.trim();
    if (trimmed === '') return null;
    const num = Number(trimmed);
    if (!Number.isFinite(num)) return null;
    return num === 0 ? 0 : num;
  }
  return null;
}

function safeRound(value: number, factor: number): number {
  if (!Number.isFinite(value)) return 0;
  const scaled = value * factor;
  if (!Number.isFinite(scaled)) return value + 0;
  return Math.round(scaled) / factor + 0;
}

interface ScaledTotal {
  total: number;
  maxVal: number;
  scaledTotal: number;
}

function buildScaledTotal(values: Iterable<number>): ScaledTotal {
  let total = 0;
  let maxVal = 0;
  let scaledTotal = 0;
  for (const v of values) {
    total += v;
    if (v > 0) {
      if (v > maxVal) {
        if (maxVal > 0) {
          scaledTotal *= maxVal / v;
        }
        maxVal = v;
      }
      scaledTotal += v / maxVal;
    }
  }
  return { total, maxVal, scaledTotal };
}

function calcSharePct(part: number, st: ScaledTotal): number {
  const rawPct = Number.isFinite(st.total)
    ? (st.total > 0 ? (part / st.total) * 100 : 0)
    : (st.scaledTotal > 0 && st.maxVal > 0 ? ((part / st.maxVal) / st.scaledTotal) * 100 : 0);
  return Number.isFinite(rawPct) ? Math.round(rawPct * 10) / 10 + 0 : 0.0;
}

const VALID_CATEGORY_KEYS: ReadonlySet<DefectCategoryKey> = new Set<DefectCategoryKey>([
  'BATTERY_CHARGING',
  'DRIVING_POWERTRAIN',
  'SOFTWARE_ELECTRONICS',
  'BUILD_QUALITY',
  'SERVICE_REPAIR_COST',
  'COLD_WEATHER',
]);

export function sanitizeVerdict(val: unknown): ModelYearVerdict {
  if (typeof val === 'string') {
    const upper = val.trim().toUpperCase();
    if (upper === 'BUY_SAFE' || upper === 'CAUTION' || upper === 'AVOID') {
      return upper;
    }
  }
  return 'CAUTION';
}

export function sanitizeGrade(val: unknown): OverallReliabilityGrade {
  if (typeof val === 'string') {
    const upper = val.trim().toUpperCase();
    if (
      upper === 'A+' ||
      upper === 'A' ||
      upper === 'B' ||
      upper === 'C' ||
      upper === 'D' ||
      upper === 'F'
    ) {
      return upper;
    }
  }
  return 'C';
}

export function sanitizeCategoryKey(
  val: unknown,
  fallback: DefectCategoryKey = 'BATTERY_CHARGING'
): DefectCategoryKey {
  if (typeof val === 'string') {
    const upper = val.trim().toUpperCase() as DefectCategoryKey;
    if (VALID_CATEGORY_KEYS.has(upper)) {
      return upper;
    }
  }
  return fallback;
}

const FORBIDDEN_RECORD_KEYS = new Set([
  '__proto__',
  'constructor',
  'prototype',
  'tostring',
  'valueof',
  'hasownproperty',
  'isprototypeof',
  'propertyisenumerable',
  'tolocalestring',
  '__definegetter__',
  '__definesetter__',
  '__lookupgetter__',
  '__lookupsetter__',
]);

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
      ? Math.max(0, Math.min(100, Math.round(fallback * 10) / 10)) + 0
      : 0;

  const parsed = parseFiniteNumber(rawScore);
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
    if (!key || FORBIDDEN_RECORD_KEYS.has(key.toLowerCase())) return;

    const num = parseFiniteNumber(rawCount);
    const parsedCount = num !== null ? Math.max(0, Math.floor(num)) : 0;

    const prev = countMap.get(key) || 0;
    const next = prev + parsedCount;
    countMap.set(key, Number.isFinite(next) ? next : Number.MAX_VALUE);
  };

  if (Array.isArray(inputs)) {
    for (const item of inputs) {
      if (!item || typeof item !== 'object') continue;

      // Case A: Item is a BrandReliability object with category_distribution
      if ('category_distribution' in item && item.category_distribution && typeof item.category_distribution === 'object') {
        if (Array.isArray(item.category_distribution)) {
          const nested = aggregateCategoryComplaintCounts(
            item.category_distribution as Array<CategoryComplaintInputEntry | null | undefined>
          );
          for (const [cat, val] of Object.entries(nested)) {
            addCount(cat, val.count);
          }
        } else {
          const dist = item.category_distribution as Record<string, { count?: unknown } | number>;
          for (const [cat, val] of Object.entries(dist)) {
            if (val && typeof val === 'object' && 'count' in val) {
              addCount(cat, (val as { count?: unknown }).count);
            } else {
              addCount(cat, val);
            }
          }
        }
        continue;
      }

      // Case B: Item is a category entry: { category / category_key / code / defect_category, count }
      const entry = item as Record<string, unknown>;
      const catKey =
        (typeof entry.category === 'string' && entry.category.trim()) ||
        (typeof entry.category_key === 'string' && entry.category_key.trim()) ||
        (typeof entry.code === 'string' && entry.code.trim()) ||
        (typeof entry.defect_category === 'string' && entry.defect_category.trim()) ||
        '';

      addCount(catKey, entry.count);
    }
  } else if (typeof inputs === 'object') {
    // Case C: inputs is a ReliabilityTrendsDatabase
    if ('brands' in inputs) {
      return Array.isArray((inputs as ReliabilityTrendsDatabase).brands)
        ? aggregateCategoryComplaintCounts((inputs as ReliabilityTrendsDatabase).brands)
        : {};
    }

    // Case C2: inputs is a single BrandReliability object
    if ('category_distribution' in inputs) {
      const dist = (inputs as { category_distribution?: unknown }).category_distribution;
      return dist && typeof dist === 'object'
        ? aggregateCategoryComplaintCounts(
            dist as Parameters<typeof aggregateCategoryComplaintCounts>[0]
          )
        : {};
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

  const scaledTotal = buildScaledTotal(countMap.values());

  const result: Record<string, { count: number; percentage: number }> = {};
  for (const [key, count] of countMap.entries()) {
    result[key] = {
      count,
      percentage: calcSharePct(count, scaledTotal),
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
  const safeCurrent = parseFiniteNumber(current) ?? 0;
  const safePrevious = parseFiniteNumber(previous) ?? 0;
  const parsedThreshold = parseFiniteNumber(thresholdPct);
  const safeThreshold = parsedThreshold !== null ? Math.max(0, parsedThreshold) : 0.1;

  const rawAbsChange = safeCurrent - safePrevious;
  const scaledAbs = rawAbsChange * 100;
  const absoluteChange = Number.isFinite(scaledAbs)
    ? Math.round(scaledAbs) / 100 + 0
    : Number.isFinite(rawAbsChange)
      ? rawAbsChange + 0
      : rawAbsChange > 0
        ? Number.MAX_VALUE
        : rawAbsChange < 0
          ? -Number.MAX_VALUE
          : 0;

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
  const absPrev = Math.abs(safePrevious);
  let rawPctChange = ((safeCurrent - safePrevious) / absPrev) * 100;
  if (!Number.isFinite(rawPctChange)) {
    // Avoid spurious overflow in (safeCurrent - safePrevious) for extreme opposite-sign magnitudes
    const ratioPct = ((safeCurrent / absPrev) - Math.sign(safePrevious)) * 100;
    if (Number.isFinite(ratioPct)) {
      rawPctChange = ratioPct;
    }
  }
  const scaledPct = rawPctChange * 10;
  const pctChange = Number.isFinite(scaledPct)
    ? Math.round(scaledPct) / 10 + 0
    : Number.isFinite(rawPctChange)
      ? rawPctChange + 0
      : rawPctChange > 0
        ? 100
        : rawPctChange < 0
          ? -100
          : 0;

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
  const brands = Array.isArray(data?.brands)
    ? data.brands.filter((b): b is BrandReliability => Boolean(b && typeof b === 'object'))
    : [];
  const meta = data?.metadata;

  const rawMetaTotal =
    parseFiniteNumber(meta?.total_records_analyzed) ??
    parseFiniteNumber(meta?.total_analyzed_posts);
  let totalAnalyzedPosts =
    rawMetaTotal !== null && rawMetaTotal > 0 ? Math.floor(rawMetaTotal) : 0;

  // Single-brand or missing metadata fallback: sum across brand reports
  if (totalAnalyzedPosts === 0 && brands.length > 0) {
    for (const b of brands) {
      const bReports = parseFiniteNumber(b.total_reports);
      if (bReports !== null && bReports > 0) {
        const nextPosts = totalAnalyzedPosts + Math.floor(bReports);
        if (Number.isFinite(nextPosts)) {
          totalAnalyzedPosts = nextPosts;
        }
      }
    }
  }

  const trackedBrandsCount = brands.length;
  let trackedModelsCount = 0;
  for (const b of brands) {
    if (Array.isArray(b.models)) {
      trackedModelsCount += b.models.filter((m) => Boolean(m && typeof m === 'object')).length;
    }
  }

  // Calculate industry / dataset average DSI
  let industryAvgDsi = 0;
  const metaAvgDsi = parseFiniteNumber(meta?.avg_industry_dsi);
  if (metaAvgDsi !== null && metaAvgDsi > 0) {
    industryAvgDsi = normalizeReliabilityScore(metaAvgDsi, 0);
  } else if (brands.length > 0) {
    // Dynamic calculation for single-brand or partial datasets
    let weightedDsiSum = 0;
    let totalDsiWeight = 0;
    let simpleDsiSum = 0;
    let validDsiCount = 0;

    for (const b of brands) {
      const rawBrandDsi = parseFiniteNumber(b.overall_dsi);
      if (rawBrandDsi === null) continue;
      const bDsi = normalizeReliabilityScore(rawBrandDsi, 0);
      const rawReports = parseFiniteNumber(b.total_reports);
      const bReports = rawReports !== null && rawReports > 0 ? rawReports : 0;

      simpleDsiSum += bDsi;
      validDsiCount++;
      if (bReports > 0) {
        weightedDsiSum += bDsi * bReports;
        totalDsiWeight += bReports;
      }
    }

    if (totalDsiWeight > 0 && Number.isFinite(totalDsiWeight) && Number.isFinite(weightedDsiSum)) {
      industryAvgDsi = Math.round((weightedDsiSum / totalDsiWeight) * 10) / 10 + 0;
    } else if (validDsiCount > 0) {
      industryAvgDsi = Math.round((simpleDsiSum / validDsiCount) * 10) / 10 + 0;
    }
  }

  // Determine top defect category via safe aggregation
  const aggregated = aggregateCategoryComplaintCounts(brands);
  let topDefectCategory = 'NONE';
  let maxCount = 0;

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
    totalRecordsAnalyzed: totalAnalyzedPosts,
    brandsCount: trackedBrandsCount,
    modelsCount: trackedModelsCount,
    avgIndustryDsi: industryAvgDsi,
  };
}

// ==========================================
// 3. MODEL & BRAND RETRIEVAL UTILITIES
// ==========================================

export function isPlainRecord(val: unknown): val is Record<string, unknown> {
  return val !== null && typeof val === 'object' && !Array.isArray(val);
}

export function copySafeOwnFields<T extends object>(source: T): T {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(source)) {
    if (FORBIDDEN_RECORD_KEYS.has(k.toLowerCase())) continue;
    out[k] = v;
  }
  return out as T;
}

function enrichModelItem(brand: BrandReliability, model: ModelReliability): EnrichedModelItem {
  const safeBrandId = typeof brand.id === 'string' ? brand.id : '';
  const modelBrandId = typeof model.brand_id === 'string' ? model.brand_id.trim() : '';
  return {
    ...copySafeOwnFields(model),
    id: typeof model.id === 'string' ? model.id : '',
    name: typeof model.name === 'string' ? model.name : '',
    segment: typeof model.segment === 'string' ? model.segment : '',
    brand_id: modelBrandId ? modelBrandId : safeBrandId,
    overall_grade: sanitizeGrade(model.overall_grade),
    avg_dsi: normalizeReliabilityScore(model.avg_dsi, 0),
    top_category: sanitizeCategoryKey(model.top_category),
    year_evaluations: Array.isArray(model.year_evaluations)
      ? model.year_evaluations
          .filter((y): y is YearEvaluation => isPlainRecord(y))
          .map((y) => {
            const parsedYear = parseFiniteNumber(y.year);
            const parsedIncident = parseFiniteNumber(y.incident_rate);
            return {
              ...copySafeOwnFields(y),
              year: parsedYear !== null ? Math.floor(parsedYear) + 0 : 0,
              ...(typeof y.verdict === 'string' && y.verdict.trim()
                ? { verdict: sanitizeVerdict(y.verdict) }
                : {}),
              dsi_score: normalizeReliabilityScore(y.dsi_score, 0),
              incident_rate:
                parsedIncident !== null
                  ? Math.max(0, Math.min(100, parsedIncident)) + 0
                  : 0,
              primary_defect: typeof y.primary_defect === 'string' ? y.primary_defect : '',
              estimated_repair_cost:
                typeof y.estimated_repair_cost === 'string' ? y.estimated_repair_cost : '',
              chronic_symptoms: Array.isArray(y.chronic_symptoms)
                ? y.chronic_symptoms.filter((s): s is string => typeof s === 'string')
                : [],
              raw_quote: typeof y.raw_quote === 'string' ? y.raw_quote : '',
            };
          })
      : [],
    brand_name_ko: typeof brand.name_ko === 'string' ? brand.name_ko : '',
    brand_name_en: typeof brand.name_en === 'string' ? brand.name_en : '',
    brand_country: typeof brand.country === 'string' ? brand.country : '',
  };
}

/**
 * Returns a flattened array of all models enriched with brand information from a given database.
 * Pure function: operates directly on the provided data without importing raw JSON.
 */
export function getAllEnrichedModels(data?: ReliabilityTrendsDatabase | null): EnrichedModelItem[] {
  if (!data || !Array.isArray(data.brands)) return [];
  const result: EnrichedModelItem[] = [];
  const brands = data.brands;

  for (const brand of brands) {
    if (!brand || typeof brand !== 'object') continue;
    const models = Array.isArray(brand.models) ? brand.models : [];
    for (const model of models) {
      if (!model || typeof model !== 'object') continue;
      result.push(enrichModelItem(brand, model));
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
  data?: ReliabilityTrendsDatabase | null
): EnrichedModelItem | undefined {
  if (!modelId || typeof modelId !== 'string' || !data || !Array.isArray(data.brands)) return undefined;
  const normalized = modelId.trim().toLowerCase().replace(/[\s\-_]+/g, '');
  if (!normalized) return undefined;

  let exactNameMatch: { brand: BrandReliability; model: ModelReliability } | undefined;
  let partialMatch: { brand: BrandReliability; model: ModelReliability } | undefined;
  let bestPartialScore = -1;

  for (const brand of data.brands) {
    if (!brand || typeof brand !== 'object' || !Array.isArray(brand.models)) continue;
    for (const model of brand.models) {
      if (!model || typeof model !== 'object') continue;
      const mIdNorm = (typeof model.id === 'string' ? model.id : '').toLowerCase().replace(/[\s\-_]+/g, '');
      // Priority 1: Exact ID match
      if (mIdNorm === normalized) {
        return enrichModelItem(brand, model);
      }

      const mNameNorm = (typeof model.name === 'string' ? model.name : '').toLowerCase().replace(/[\s\-_]+/g, '');
      // Priority 2: Exact Name match
      if (!exactNameMatch && mNameNorm === normalized) {
        exactNameMatch = { brand, model };
        continue;
      }

      // Priority 3: Fallback substring match (require length >= 2, prefer longest overlap)
      if (normalized.length >= 2) {
        let score = -1;
        if (mIdNorm.length >= 2 && (mIdNorm.includes(normalized) || normalized.includes(mIdNorm))) {
          score = Math.min(mIdNorm.length, normalized.length) * 2 + 1;
        } else if (mNameNorm.length >= 2 && (mNameNorm.includes(normalized) || normalized.includes(mNameNorm))) {
          score = Math.min(mNameNorm.length, normalized.length) * 2;
        }
        if (score > bestPartialScore) {
          bestPartialScore = score;
          partialMatch = { brand, model };
        }
      }
    }
  }

  const chosen = exactNameMatch ?? partialMatch;
  return chosen ? enrichModelItem(chosen.brand, chosen.model) : undefined;
}

/**
 * Returns all year evaluations / defect records for a specific model,
 * ensuring the returned array is safe, non-null, and filtered of malformed entries.
 */
export function getDefectsForModel(
  modelId: string,
  data?: ReliabilityTrendsDatabase | null
): YearEvaluation[] {
  const model = getModelReliabilityById(modelId, data);
  if (!model || !Array.isArray(model.year_evaluations)) return [];
  return model.year_evaluations.filter((y: YearEvaluation) =>
    Boolean(y && typeof y === 'object' && typeof y.verdict === 'string' && y.verdict.trim())
  );
}

const SHORT_ASCII_BRAND_REGEX_CACHE = new Map<string, RegExp>();

function matchesBrandTokenOrSubstring(haystackLower: string, needleLower: string): boolean {
  if (haystackLower.length < 2 || needleLower.length < 2) return false;
  if (/^[a-z0-9]+$/.test(needleLower) && needleLower.length <= 4) {
    let re = SHORT_ASCII_BRAND_REGEX_CACHE.get(needleLower);
    if (!re) {
      re = new RegExp(`\\b${needleLower}\\b`);
      if (SHORT_ASCII_BRAND_REGEX_CACHE.size < 256) {
        SHORT_ASCII_BRAND_REGEX_CACHE.set(needleLower, re);
      }
    }
    return re.test(haystackLower);
  }
  return haystackLower.includes(needleLower);
}

/**
 * Finds a specific brand by ID or name from the reliability dataset.
 */
export function getBrandReliabilityById(
  brandId: string,
  data?: ReliabilityTrendsDatabase | null
): BrandReliability | undefined {
  if (!brandId || typeof brandId !== 'string') return undefined;
  const normalized = brandId.trim().toLowerCase();
  if (!normalized) return undefined;
  const brands = Array.isArray(data?.brands)
    ? data.brands.filter((b): b is BrandReliability => Boolean(b && typeof b === 'object'))
    : [];

  const exactId = brands.find(
    (b) => typeof b.id === 'string' && b.id.trim().toLowerCase() === normalized
  );
  if (exactId) return exactId;

  const exactName = brands.find(
    (b) =>
      (typeof b.name_ko === 'string' && b.name_ko.trim().toLowerCase() === normalized) ||
      (typeof b.name_en === 'string' && b.name_en.trim().toLowerCase() === normalized)
  );
  if (exactName) return exactName;

  if (normalized.length < 2) return undefined;
  return brands.find((b) => {
    const ko = typeof b.name_ko === 'string' ? b.name_ko.trim().toLowerCase() : '';
    const en = typeof b.name_en === 'string' ? b.name_en.trim().toLowerCase() : '';
    return (
      matchesBrandTokenOrSubstring(ko, normalized) ||
      matchesBrandTokenOrSubstring(en, normalized)
    );
  });
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
  const parsedComplaints = parseFiniteNumber(complaintCount);
  if (parsedComplaints === null || parsedComplaints <= 0) {
    return 0.0;
  }

  const safeComplaints = Math.max(0, Math.floor(parsedComplaints));
  if (safeComplaints === 0) return 0.0;

  const threshold =
    typeof minSampleThreshold === 'number' && Number.isFinite(minSampleThreshold) && minSampleThreshold > 0
      ? minSampleThreshold
      : 50;

  // Logarithmic asymptotic saturation
  const denom = Math.log(1 + threshold);
  const sampleConfidence =
    denom > 0 && Number.isFinite(denom)
      ? Math.min(1.0, Math.log(1 + safeComplaints) / denom)
      : 1.0;

  // Year coverage factor (if specified)
  let yearFactor = 1.0;
  if (yearsEvaluated !== undefined && yearsEvaluated !== null) {
    const rawYears = parseFiniteNumber(yearsEvaluated);
    const parsedYears = rawYears !== null ? Math.floor(rawYears) : null;

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
  const parsedComplaints = parseFiniteNumber(complaintCount);
  const safeComplaints = parsedComplaints !== null ? Math.max(0, parsedComplaints) : 0;

  const parsedVolume = parseFiniteNumber(fleetOrSalesVolume);
  const safeVolume = parsedVolume !== null ? Math.max(0, parsedVolume) : 0;

  if (safeComplaints === 0 || safeVolume === 0) {
    return 0.0;
  }

  const safeScale =
    typeof baselineScale === 'number' && Number.isFinite(baselineScale) && baselineScale > 0
      ? baselineScale
      : 1000;

  const frequency = (safeComplaints / safeVolume) * safeScale;
  return Number.isFinite(frequency) ? safeRound(frequency, 100) : 0.0;
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

  const weights = new Map<string, number>(Object.entries(DEFAULT_CATEGORY_SEVERITY_WEIGHTS));
  if (customWeights && typeof customWeights === 'object') {
    for (const [k, v] of Object.entries(customWeights)) {
      if (typeof k === 'string') {
        const trimmedKey = k.trim();
        if (!trimmedKey || FORBIDDEN_RECORD_KEYS.has(trimmedKey.toLowerCase())) continue;
        const parsedWeight = parseFiniteNumber(v);
        if (parsedWeight !== null && parsedWeight > 0) {
          weights.set(trimmedKey.toUpperCase(), parsedWeight);
        }
      }
    }
  }

  const weightedEntries: Array<{ count: number; weight: number }> = [];
  for (const [cat, data] of Object.entries(aggregated)) {
    const count = data.count || 0;
    if (count <= 0) continue;
    const nextTotal = totalComplaints + count;
    totalComplaints = Number.isFinite(nextTotal) ? nextTotal : Number.MAX_VALUE;
    const w = weights.get(cat);
    const weight = w !== undefined && Number.isFinite(w) && w > 0 ? w : 1.0;
    weightedSum += count * weight;
    weightedEntries.push({ count, weight });
  }

  if (totalComplaints === 0 || weightedEntries.length === 0) {
    return 0.0;
  }

  let volume = 0;
  let scale = 1000;
  const directVol = parseFiniteNumber(totalVolumeOrReports);
  if (directVol !== null) {
    volume = Math.max(0, directVol);
  } else if (totalVolumeOrReports && typeof totalVolumeOrReports === 'object') {
    const opts = totalVolumeOrReports as DefectFrequencyOptions;
    const parsedV =
      parseFiniteNumber(opts.fleetOrSalesVolume) ??
      parseFiniteNumber((opts as Record<string, unknown>).volume);
    if (parsedV !== null) {
      volume = Math.max(0, parsedV);
    }
    const parsedScale = parseFiniteNumber(opts.baselineScale);
    if (parsedScale !== null && parsedScale > 0) {
      scale = parsedScale;
    }
  }

  if (volume > 0) {
    let freq = (weightedSum / volume) * scale;
    if (!Number.isFinite(freq)) {
      let ratioSum = 0;
      for (const entry of weightedEntries) {
        ratioSum += (entry.count / volume) * entry.weight * scale;
      }
      freq = ratioSum;
    }
    return Number.isFinite(freq) ? safeRound(freq, 100) : 0.0;
  }

  // Fallback to average severity multiplier
  let avgMult = weightedSum / totalComplaints;
  if (!Number.isFinite(avgMult)) {
    let ratioSum = 0;
    for (const entry of weightedEntries) {
      ratioSum += (entry.count / totalComplaints) * entry.weight;
    }
    avgMult = ratioSum;
  }
  return Number.isFinite(avgMult) ? safeRound(avgMult, 100) : 0.0;
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
  const parsedIncident = parseFiniteNumber(input?.incidentRate);
  const safeIncidentRate = parsedIncident !== null ? Math.max(0, Math.min(100, parsedIncident)) : 0.0;
  const parsedCritical = parseFiniteNumber(input?.criticalIssueRate);
  const safeCriticalRate = parsedCritical !== null ? Math.max(0, Math.min(100, parsedCritical)) : 0.0;

  const parsedComplaints = parseFiniteNumber(input?.totalComplaints);
  const safeComplaints = parsedComplaints !== null ? Math.max(0, Math.floor(parsedComplaints)) : 0;

  const parsedYears = parseFiniteNumber(input?.yearsEvaluated);
  const safeYears = parsedYears !== null ? Math.max(0, Math.floor(parsedYears)) : undefined;

  // Weight validation and normalization
  let hasInvalidWeight = false;
  const rawWDsi = input?.weights?.dsiWeight;
  const rawWInc = input?.weights?.incidentWeight;
  const rawWCrit = input?.weights?.criticalWeight;

  if (input?.weights && typeof input.weights === 'object') {
    if (
      (rawWDsi !== undefined && (typeof rawWDsi !== 'number' || !Number.isFinite(rawWDsi) || rawWDsi < 0)) ||
      (rawWInc !== undefined && (typeof rawWInc !== 'number' || !Number.isFinite(rawWInc) || rawWInc < 0)) ||
      (rawWCrit !== undefined && (typeof rawWCrit !== 'number' || !Number.isFinite(rawWCrit) || rawWCrit < 0))
    ) {
      hasInvalidWeight = true;
    }
  }

  let wDsi = !hasInvalidWeight && typeof rawWDsi === 'number' && Number.isFinite(rawWDsi) && rawWDsi >= 0
    ? rawWDsi + 0
    : DEFAULT_STEALTH_SCORE_WEIGHTS.dsiWeight;
  let wInc = !hasInvalidWeight && typeof rawWInc === 'number' && Number.isFinite(rawWInc) && rawWInc >= 0
    ? rawWInc + 0
    : DEFAULT_STEALTH_SCORE_WEIGHTS.incidentWeight;
  let wCrit = !hasInvalidWeight && typeof rawWCrit === 'number' && Number.isFinite(rawWCrit) && rawWCrit >= 0
    ? rawWCrit + 0
    : DEFAULT_STEALTH_SCORE_WEIGHTS.criticalWeight;

  const totalWeight = wDsi + wInc + wCrit;
  if (totalWeight <= 0 || !Number.isFinite(totalWeight) || hasInvalidWeight) {
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
  const defectPenalty = Math.max(0, Math.min(100, Math.round(rawDefectPenalty * 10) / 10)) + 0;

  // Raw stealth score (100 - defect penalty)
  const rawStealthScore = Math.round((100 - defectPenalty) * 10) / 10 + 0;

  // Statistical confidence score [0.0, 1.0]
  const confidenceScore = calculateReliabilityConfidence(safeComplaints, safeYears);

  // Industry baseline stealth score (default industry avg DSI is 64.2 -> stealth 35.8; neutral baseline is 50.0)
  const rawBaseline = input?.baselineIndustryDsi;
  const baselineDsi = rawBaseline !== undefined && rawBaseline !== null
    ? normalizeReliabilityScore(rawBaseline, 50.0)
    : 50.0;
  const baselineStealth = Math.round((100 - baselineDsi) * 10) / 10 + 0;

  // Smoothed stealth score prevents 0-complaint or untested models from claiming 100% perfection
  const smoothedStealth = Math.max(
    0,
    Math.min(
      100,
      Math.round((confidenceScore * rawStealthScore + (1 - confidenceScore) * baselineStealth) * 10) / 10
    )
  ) + 0;

  // Volume-aware normalized defect frequency
  const rawVolume =
    parseFiniteNumber(input?.fleetOrSalesVolume) ??
    parseFiniteNumber(input?.fleetVolume) ??
    parseFiniteNumber(input?.salesVolume);
  const parsedScale = parseFiniteNumber(input?.baselineScale);
  const scale = parsedScale !== null && parsedScale > 0 ? parsedScale : 1000;
  const normalizedDefectFrequency = rawVolume !== null
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
  data?: ReliabilityTrendsDatabase | null
): YearEvaluation | undefined {
  if (!modelId || typeof modelId !== 'string') return undefined;
  const numYear = parseFiniteNumber(year);
  if (numYear === null) return undefined;

  const defects = getDefectsForModel(modelId, data);
  if (!defects || defects.length === 0) return undefined;

  const target = defects.find((y) => {
    if (!y) return false;
    const yNum = parseFiniteNumber(y.year);
    return yNum !== null && Math.floor(yNum) === Math.floor(numYear);
  });
  if (!target) return undefined;

  const parsedIncident = parseFiniteNumber(target.incident_rate);
  return {
    ...target,
    year: Math.floor(numYear) + 0,
    verdict: sanitizeVerdict(target.verdict),
    dsi_score: normalizeReliabilityScore(target.dsi_score, 50.0),
    incident_rate:
      parsedIncident !== null
        ? Math.max(0, Math.min(100, parsedIncident)) + 0
        : 0,
    chronic_symptoms: Array.isArray(target.chronic_symptoms)
      ? target.chronic_symptoms.filter((s): s is string => typeof s === 'string')
      : [],
    primary_defect: typeof target.primary_defect === 'string' ? target.primary_defect : '',
    estimated_repair_cost: typeof target.estimated_repair_cost === 'string' ? target.estimated_repair_cost : '',
    raw_quote: typeof target.raw_quote === 'string' ? target.raw_quote : '',
  };
}

const BRAND_ALIAS_TO_ID: Readonly<Record<string, string>> = Object.freeze({
  현대차: 'hyundai',
  현대자동차: 'hyundai',
  hyundaimotors: 'hyundai',
  기아차: 'kia',
  기아자동차: 'kia',
  kiamotors: 'kia',
  벤츠: 'mercedes-benz',
  메르세데스: 'mercedes-benz',
  mercedesbenz: 'mercedes-benz',
  비야디: 'byd',
  쉐보레: 'gm-chevrolet',
  chevy: 'gm-chevrolet',
  chevrolet: 'gm-chevrolet',
  한국지엠: 'gm-chevrolet',
});

/**
 * Safe fuzzy brand resolver that matches ID, Korean name, English name, or standard alias.
 * Returns undefined for unknown brands.
 */
export function resolveBrandReliability(
  brandQuery: string,
  data?: ReliabilityTrendsDatabase | null
): BrandReliability | undefined {
  if (!brandQuery || typeof brandQuery !== 'string') return undefined;
  const clean = brandQuery.trim().toLowerCase();
  if (!clean || clean === 'all') return undefined;

  const brands = Array.isArray(data?.brands)
    ? data.brands.filter((b): b is BrandReliability => Boolean(b && typeof b === 'object'))
    : [];
  if (brands.length === 0) return undefined;

  // Exact ID match
  const exact = brands.find((b) => typeof b.id === 'string' && b.id.trim().toLowerCase() === clean);
  if (exact) return exact;

  // Exact name match
  const nameExact = brands.find(
    (b) =>
      (typeof b.name_en === 'string' && b.name_en.trim().toLowerCase() === clean) ||
      (typeof b.name_ko === 'string' && b.name_ko.trim().toLowerCase() === clean)
  );
  if (nameExact) return nameExact;

  // Canonical alias match (handles e.g. '현대차', 'chevy', '기아차')
  const compactKey = clean.replace(/[\s\-_/()[\]+.,&]+/g, '');
  const mappedId = Object.prototype.hasOwnProperty.call(BRAND_ALIAS_TO_ID, compactKey)
    ? BRAND_ALIAS_TO_ID[compactKey]
    : undefined;
  if (mappedId) {
    const aliasMatch = brands.find((b) => typeof b.id === 'string' && b.id.trim().toLowerCase() === mappedId);
    if (aliasMatch) return aliasMatch;
  }

  // Substring match (require length >= 2 to prevent 1-char false positives, and word boundary for short ASCII tokens)
  if (clean.length < 2) return undefined;
  return brands.find((b) => {
    const en = typeof b.name_en === 'string' ? b.name_en.trim().toLowerCase() : '';
    const ko = typeof b.name_ko === 'string' ? b.name_ko.trim().toLowerCase() : '';
    return (
      matchesBrandTokenOrSubstring(en, clean) ||
      matchesBrandTokenOrSubstring(clean, en) ||
      matchesBrandTokenOrSubstring(ko, clean) ||
      matchesBrandTokenOrSubstring(clean, ko)
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
  data?: ReliabilityTrendsDatabase | null
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
  const safeBrandId = typeof brandId === 'string' && brandId.trim() ? brandId.trim().toLowerCase() : 'unknown';
  return {
    id: safeId,
    name: '미확인 차종',
    segment: '미분류',
    brand_id: safeBrandId,
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

interface PeriodAccumulator {
  year: number;
  subPeriod: number;
  totalComplaints: number;
  dsiWeightedSum: number;
  dsiCount: number;
  dsiUnweightedSum: number;
  dsiUnweightedCount: number;
  categoryCounts: Map<string, number>;
}

const STABLE_ZERO_TREND: TrendCalculationResult = {
  direction: 'STABLE',
  percentageChange: 0,
  absoluteChange: 0,
  formattedChange: '0.0%',
  isIncrease: false,
  isDecrease: false,
  isStable: true,
};

function parseValidDateString(dateVal: unknown): string | null {
  if (dateVal instanceof Date) {
    return Number.isNaN(dateVal.getTime()) ? null : dateVal.toISOString();
  }
  if (typeof dateVal === 'string') {
    const trimmed = dateVal.trim();
    return trimmed ? trimmed : null;
  }
  return null;
}

function isValidCalendarDate(year: number, month: number, day: number): boolean {
  if (year < 1990 || year > 2100 || month < 1 || month > 12 || day < 1 || day > 31) {
    return false;
  }
  const d = new Date(Date.UTC(year, month - 1, day));
  return (
    !Number.isNaN(d.getTime()) &&
    d.getUTCFullYear() === year &&
    d.getUTCMonth() === month - 1 &&
    d.getUTCDate() === day
  );
}

function parsePeriodicDate(
  dateVal: unknown
): { year: number; month?: number; quarter?: 1 | 2 | 3 | 4 } | null {
  if (dateVal instanceof Date) {
    if (Number.isNaN(dateVal.getTime())) return null;
    const parsedY = dateVal.getUTCFullYear();
    const parsedM = dateVal.getUTCMonth() + 1;
    if (parsedY < 1990 || parsedY > 2100) return null;
    return {
      year: parsedY,
      month: parsedM,
      quarter: Math.ceil(parsedM / 3) as 1 | 2 | 3 | 4,
    };
  }

  const dateStr = parseValidDateString(dateVal);
  if (!dateStr) return null;

  // 1. Quarter format: "2024-Q1", "2024 Q2", "2024년 1분기", "2024년 Q1"
  const qMatch =
    dateStr.match(/^(\d{4})(?:[-/. ]*|년\s*)Q([1-4])$/i) ||
    dateStr.match(/^(\d{4})\s*년?\s*([1-4])\s*분기$/);
  if (qMatch) {
    const parsedY = Number(qMatch[1]);
    if (parsedY >= 1990 && parsedY <= 2100) {
      return { year: parsedY, quarter: Number(qMatch[2]) as 1 | 2 | 3 | 4 };
    }
    return null;
  }

  // 2. Full or partial delimited date: YYYY-MM-DD, YYYY.MM.DD, YYYY/MM/DD, YYYY-MM, and ISO-8601 timestamps
  const fullMatch = dateStr.match(
    /^(\d{4})[-/. ](\d{1,2})(?:[-/. ](\d{1,2})(?:$|(?:T|\s+)(\d{1,2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(?:\s*(?:(Z)|([+-])(\d{2})(?::?(\d{2}))?))?))?$/i
  );
  if (fullMatch) {
    const parsedY = Number(fullMatch[1]);
    const parsedM = Number(fullMatch[2]);
    if (parsedY < 1990 || parsedY > 2100 || parsedM < 1 || parsedM > 12) return null;
    if (fullMatch[3] !== undefined) {
      const parsedD = Number(fullMatch[3]);
      if (!isValidCalendarDate(parsedY, parsedM, parsedD)) return null;

      if (fullMatch[4] !== undefined) {
        const hour = Number(fullMatch[4]);
        const minute = Number(fullMatch[5]);
        const second = fullMatch[6] !== undefined ? Number(fullMatch[6]) : 0;
        if (hour > 23 || minute > 59 || second > 59) return null;

        // Convert explicit-offset ISO timestamps (Z or ±HH:MM / ±HH) to UTC
        if (fullMatch[7] !== undefined || fullMatch[8] !== undefined) {
          let offsetMinutes = 0;
          if (fullMatch[8] !== undefined) {
            const tzHour = Number(fullMatch[9]);
            const tzMin = fullMatch[10] !== undefined ? Number(fullMatch[10]) : 0;
            if (tzHour > 23 || tzMin > 59) return null;
            const sign = fullMatch[8] === '-' ? -1 : 1;
            offsetMinutes = sign * (tzHour * 60 + tzMin);
          }
          const utcMs = Date.UTC(parsedY, parsedM - 1, parsedD, hour, minute, second) - offsetMinutes * 60_000;
          const utcDate = new Date(utcMs);
          const utcY = utcDate.getUTCFullYear();
          const utcM = utcDate.getUTCMonth() + 1;
          if (utcY < 1990 || utcY > 2100) return null;
          return {
            year: utcY,
            month: utcM,
            quarter: Math.ceil(utcM / 3) as 1 | 2 | 3 | 4,
          };
        }
      }
    }
    return {
      year: parsedY,
      month: parsedM,
      quarter: Math.ceil(parsedM / 3) as 1 | 2 | 3 | 4,
    };
  }

  // 2b. Korean spaced dot notation: "2024. 3. 18.", "2024. 03. 18", "2024. 3.", "2024.03."
  const spacedDotMatch = dateStr.match(/^(\d{4})\.\s*(\d{1,2})(?:\.\s*(\d{1,2}))?\.?$/);
  if (spacedDotMatch) {
    const parsedY = Number(spacedDotMatch[1]);
    const parsedM = Number(spacedDotMatch[2]);
    if (parsedY < 1990 || parsedY > 2100 || parsedM < 1 || parsedM > 12) return null;
    if (spacedDotMatch[3] !== undefined) {
      const parsedD = Number(spacedDotMatch[3]);
      if (!isValidCalendarDate(parsedY, parsedM, parsedD)) return null;
    }
    return {
      year: parsedY,
      month: parsedM,
      quarter: Math.ceil(parsedM / 3) as 1 | 2 | 3 | 4,
    };
  }

  // 3. Korean date: YYYY년 MM월 (DD일)
  const krMatch = dateStr.match(/^(\d{4})년\s*(\d{1,2})월(?:\s*(\d{1,2})일)?$/);
  if (krMatch) {
    const parsedY = Number(krMatch[1]);
    const parsedM = Number(krMatch[2]);
    if (parsedY < 1990 || parsedY > 2100 || parsedM < 1 || parsedM > 12) return null;
    if (krMatch[3] !== undefined) {
      const parsedD = Number(krMatch[3]);
      if (!isValidCalendarDate(parsedY, parsedM, parsedD)) return null;
    }
    return {
      year: parsedY,
      month: parsedM,
      quarter: Math.ceil(parsedM / 3) as 1 | 2 | 3 | 4,
    };
  }

  // 4. Compact YYYYMMDD
  const compactMatch = dateStr.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (compactMatch) {
    const parsedY = Number(compactMatch[1]);
    const parsedM = Number(compactMatch[2]);
    const parsedD = Number(compactMatch[3]);
    if (!isValidCalendarDate(parsedY, parsedM, parsedD)) return null;
    return {
      year: parsedY,
      month: parsedM,
      quarter: Math.ceil(parsedM / 3) as 1 | 2 | 3 | 4,
    };
  }

  return null;
}

function parsePeriodicMetrics(item: PeriodicDefectInput): {
  parsedCount: number;
  parsedDsi: number | null;
  catKey: string;
} {
  let parsedCount = 1;
  if (item.count !== undefined && item.count !== null) {
    const c = parseFiniteNumber(item.count);
    parsedCount = c !== null ? Math.max(0, Math.floor(c)) : 0;
  }

  const rawDsi = parseFiniteNumber(item.dsiScore);
  const parsedDsi = rawDsi !== null ? normalizeReliabilityScore(rawDsi, 50.0) : null;

  const trimmedCat =
    (typeof item.category === 'string' && item.category.trim()) ||
    (typeof item.defectCategory === 'string' && item.defectCategory.trim()) ||
    'UNKNOWN';
  const upperCat = trimmedCat.toUpperCase();
  const catKey = FORBIDDEN_RECORD_KEYS.has(upperCat.toLowerCase()) ? 'UNKNOWN' : upperCat;

  return { parsedCount, parsedDsi, catKey };
}

function accumulatePeriodEntry(
  groups: Map<string, PeriodAccumulator>,
  periodKey: string,
  year: number,
  subPeriod: number,
  metrics: { parsedCount: number; parsedDsi: number | null; catKey: string }
): void {
  if (!groups.has(periodKey)) {
    groups.set(periodKey, {
      year,
      subPeriod,
      totalComplaints: 0,
      dsiWeightedSum: 0,
      dsiCount: 0,
      dsiUnweightedSum: 0,
      dsiUnweightedCount: 0,
      categoryCounts: new Map(),
    });
  }

  const g = groups.get(periodKey)!;
  const nextTotal = g.totalComplaints + metrics.parsedCount;
  g.totalComplaints = Number.isFinite(nextTotal) ? nextTotal : Number.MAX_VALUE;

  if (metrics.parsedDsi !== null) {
    g.dsiUnweightedSum += metrics.parsedDsi;
    g.dsiUnweightedCount += 1;

    const weight = Math.max(1, metrics.parsedCount);
    const nextWeightedSum = g.dsiWeightedSum + metrics.parsedDsi * weight;
    const nextWeightCount = g.dsiCount + weight;
    if (Number.isFinite(nextWeightedSum) && Number.isFinite(nextWeightCount)) {
      g.dsiWeightedSum = nextWeightedSum;
      g.dsiCount = nextWeightCount;
    } else {
      g.dsiWeightedSum = Number.NaN;
    }
  }

  if (metrics.parsedCount > 0) {
    const prevCat = g.categoryCounts.get(metrics.catKey) || 0;
    const nextCat = prevCat + metrics.parsedCount;
    g.categoryCounts.set(metrics.catKey, Number.isFinite(nextCat) ? nextCat : Number.MAX_VALUE);
  }
}

function buildPeriodSummary(
  sortedKeys: string[],
  groups: Map<string, PeriodAccumulator>,
  index: number,
  grandTotalScaled: ScaledTotal
) {
  const key = sortedKeys[index];
  const g = groups.get(key)!;

  const percentage = calcSharePct(g.totalComplaints, grandTotalScaled);

  let avgDsi = 50.0;
  if (g.dsiCount > 0 && Number.isFinite(g.dsiWeightedSum) && Number.isFinite(g.dsiCount)) {
    const rawAvg = g.dsiWeightedSum / g.dsiCount;
    if (Number.isFinite(rawAvg)) {
      avgDsi = Math.round(rawAvg * 10) / 10 + 0;
    }
  } else if (g.dsiUnweightedCount > 0 && Number.isFinite(g.dsiUnweightedSum)) {
    const rawFallback = g.dsiUnweightedSum / g.dsiUnweightedCount;
    if (Number.isFinite(rawFallback)) {
      avgDsi = Math.round(rawFallback * 10) / 10 + 0;
    }
  }

  let topCategory: DefectCategoryKey | string = 'NONE';
  let maxCatCount = 0;
  const categoryDistribution: Record<string, { count: number; percentage: number }> = {};
  const catScaledTotal = buildScaledTotal(g.categoryCounts.values());

  for (const [cat, cnt] of g.categoryCounts.entries()) {
    categoryDistribution[cat] = {
      count: cnt,
      percentage: calcSharePct(cnt, catScaledTotal),
    };
    if (cnt > maxCatCount) {
      maxCatCount = cnt;
      topCategory = cat;
    }
  }

  const previousCount = index > 0 ? groups.get(sortedKeys[index - 1])!.totalComplaints : g.totalComplaints;
  const trendFromPrevious = index > 0
    ? calculateTrendDirection(g.totalComplaints, previousCount)
    : { ...STABLE_ZERO_TREND };

  const windowStart = Math.max(0, index - 2);
  const windowCount = index - windowStart + 1;
  let windowSum = 0;
  for (let w = windowStart; w <= index; w++) {
    windowSum += groups.get(sortedKeys[w])!.totalComplaints;
  }
  let rawMa: number;
  if (Number.isFinite(windowSum)) {
    rawMa = windowSum / windowCount;
  } else {
    let ratioSum = 0;
    for (let w = windowStart; w <= index; w++) {
      ratioSum += groups.get(sortedKeys[w])!.totalComplaints / windowCount;
    }
    rawMa = ratioSum;
  }
  const movingAverage3 = Number.isFinite(rawMa) ? safeRound(rawMa, 10) : 0;

  return {
    periodKey: key,
    year: g.year,
    subPeriod: g.subPeriod,
    totalComplaints: g.totalComplaints,
    percentage,
    avgDsi,
    topCategory,
    categoryDistribution,
    trendFromPrevious,
    movingAverage3,
  };
}

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

  const groups = new Map<string, PeriodAccumulator>();

  for (const item of inputs) {
    if (!item || typeof item !== 'object') continue;

    let year: number | null = null;
    let quarter: (1 | 2 | 3 | 4) | null = null;

    // 1. Direct year and quarter fields
    const directYear = parseFiniteNumber(item.year);
    if (directYear !== null && directYear >= 1990 && directYear <= 2100) {
      year = Math.floor(directYear);
    }

    if (item.quarter !== undefined && item.quarter !== null) {
      const qStr = String(item.quarter).trim().toUpperCase();
      const match = qStr.match(/^(?:Q)?([1-4])$/);
      if (match) {
        quarter = Number(match[1]) as 1 | 2 | 3 | 4;
      }
    }

    // 2. Month-based quarter derivation
    if (!quarter && item.month !== undefined && item.month !== null) {
      const m = parseFiniteNumber(item.month);
      if (m !== null && m >= 1 && m <= 12) {
        quarter = Math.ceil(Math.floor(m) / 3) as 1 | 2 | 3 | 4;
      }
    }

    // 3. Date string or Date object parsing
    if ((year === null || quarter === null) && item.date) {
      const parsedDate = parsePeriodicDate(item.date);
      if (parsedDate) {
        if (year === null) year = parsedDate.year;
        if (quarter === null && parsedDate.quarter) quarter = parsedDate.quarter;
      }
    }

    if (!year || !quarter) continue;

    const periodKey = `${year}-Q${quarter}`;
    accumulatePeriodEntry(
      groups,
      periodKey,
      year,
      quarter,
      parsePeriodicMetrics(item)
    );
  }

  // Sort chronologically by year and quarter (YYYY-QX lexicographical order matches chronological order)
  const sortedKeys = Array.from(groups.keys()).sort();
  const grandTotalScaled = buildScaledTotal(Array.from(groups.values(), (g) => g.totalComplaints));

  const results: QuarterlyDefectBreakdown[] = [];
  for (let i = 0; i < sortedKeys.length; i++) {
    const summary = buildPeriodSummary(sortedKeys, groups, i, grandTotalScaled);
    results.push({
      periodKey: summary.periodKey,
      year: summary.year,
      quarter: summary.subPeriod as 1 | 2 | 3 | 4,
      totalComplaints: summary.totalComplaints,
      percentage: summary.percentage,
      avgDsi: summary.avgDsi,
      topCategory: summary.topCategory,
      categoryDistribution: summary.categoryDistribution,
      trendFromPrevious: summary.trendFromPrevious,
      movingAverage3Q: summary.movingAverage3,
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

  const groups = new Map<string, PeriodAccumulator>();

  for (const item of inputs) {
    if (!item || typeof item !== 'object') continue;

    let year: number | null = null;
    let month: number | null = null;

    const directYear = parseFiniteNumber(item.year);
    if (directYear !== null && directYear >= 1990 && directYear <= 2100) {
      year = Math.floor(directYear);
    }

    const directMonth = parseFiniteNumber(item.month);
    if (directMonth !== null && directMonth >= 1 && directMonth <= 12) {
      month = Math.floor(directMonth);
    }

    if ((year === null || month === null) && item.date) {
      const parsedDate = parsePeriodicDate(item.date);
      if (parsedDate) {
        if (year === null) year = parsedDate.year;
        if (month === null && parsedDate.month) month = parsedDate.month;
      }
    }

    if (!year || !month) continue;

    const periodKey = `${year}-${String(month).padStart(2, '0')}`;
    accumulatePeriodEntry(
      groups,
      periodKey,
      year,
      month,
      parsePeriodicMetrics(item)
    );
  }

  const sortedKeys = Array.from(groups.keys()).sort();
  const grandTotalScaled = buildScaledTotal(Array.from(groups.values(), (g) => g.totalComplaints));
  const results: MonthlyDefectBreakdown[] = [];

  for (let i = 0; i < sortedKeys.length; i++) {
    const summary = buildPeriodSummary(sortedKeys, groups, i, grandTotalScaled);
    results.push({
      periodKey: summary.periodKey,
      year: summary.year,
      month: summary.subPeriod,
      monthLabel: `${summary.year}년 ${summary.subPeriod}월`,
      totalComplaints: summary.totalComplaints,
      percentage: summary.percentage,
      avgDsi: summary.avgDsi,
      topCategory: summary.topCategory,
      categoryDistribution: summary.categoryDistribution,
      trendFromPrevious: summary.trendFromPrevious,
      movingAverage3M: summary.movingAverage3,
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
    if (typeof model.id === 'string' && model.id.trim()) mId = model.id;
    if (typeof model.name === 'string' && model.name.trim()) mName = model.name;
    if ('brand_name_ko' in model && typeof model.brand_name_ko === 'string' && model.brand_name_ko.trim()) {
      bName = model.brand_name_ko;
    }
  }

  const evalByYear = new Map<number, YearEvaluation>();
  for (const e of evals) {
    if (!isPlainRecord(e)) continue;
    const parsedYear = parseFiniteNumber(e.year);
    if (parsedYear === null) continue;
    const yr = Math.floor(parsedYear) + 0;
    if (yr < 1900 || yr > 2100) continue;
    const parsedIncident = parseFiniteNumber(e.incident_rate);
    const currSymptoms = Array.isArray(e.chronic_symptoms)
      ? e.chronic_symptoms
          .filter((s): s is string => typeof s === 'string')
          .map((s) => s.trim().replace(/\s+/g, ' '))
          .filter(Boolean)
      : [];
    const existing = evalByYear.get(yr);
    const mergedSymptoms: string[] = [];
    const seenMerged = new Set<string>();
    for (const sym of [...(existing?.chronic_symptoms || []), ...currSymptoms]) {
      const key = sym.toLowerCase();
      if (!seenMerged.has(key)) {
        seenMerged.add(key);
        mergedSymptoms.push(sym);
      }
    }
    evalByYear.set(yr, {
      ...copySafeOwnFields(e),
      year: yr,
      dsi_score: normalizeReliabilityScore(e.dsi_score, 50.0),
      incident_rate: parsedIncident !== null ? Math.max(0, Math.min(100, parsedIncident)) + 0 : 0,
      chronic_symptoms: mergedSymptoms,
    });
  }
  const validEvals = Array.from(evalByYear.values()).sort((a, b) => a.year - b.year);

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
  const symptomDisplayNames = new Map<string, string>();
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
      const seenInYear = new Set<string>();
      for (const sym of curr.chronic_symptoms) {
        if (typeof sym === 'string') {
          const cleanSym = sym.trim().replace(/\s+/g, ' ');
          const normKey = cleanSym.toLowerCase();
          if (cleanSym && !seenInYear.has(normKey)) {
            seenInYear.add(normKey);
            if (!symptomDisplayNames.has(normKey)) {
              symptomDisplayNames.set(normKey, cleanSym);
            }
            chronicMap.set(normKey, (chronicMap.get(normKey) || 0) + 1);
          }
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

    const validVerdict: ModelYearVerdict = sanitizeVerdict(curr.verdict);

    progression.push({
      year: curr.year,
      dsi: curr.dsi_score,
      verdict: validVerdict,
      incidentRate: curr.incident_rate,
      primaryDefect: typeof curr.primary_defect === 'string' ? curr.primary_defect : '',
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
    .map(([normKey]) => symptomDisplayNames.get(normKey) ?? normKey);

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
