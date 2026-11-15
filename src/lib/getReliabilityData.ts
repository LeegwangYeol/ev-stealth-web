import rawTrendsData from '../data/ev_reliability_trends.json' with { type: 'json' };

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
// 2. RE-EXPORT CORE CALCULATION ENGINES
// ==========================================

import {
  normalizeReliabilityScore,
  aggregateCategoryComplaintCounts,
  getAggregatedCategoryList,
  calculateTrendDirection,
  calculateReliabilityKPIs as calculateReliabilityKPIsPure,
  getAllEnrichedModels as getAllEnrichedModelsPure,
  getVerdictBadgeInfo,
  getDsiSeverityLevel as getDsiSeverityLevelPure,
  getGradeBadgeStyle,
  getModelReliabilityById as getModelReliabilityByIdPure,
  getDefectsForModel as getDefectsForModelPure,
  getBrandReliabilityById as getBrandReliabilityByIdPure,
  DEFAULT_CATEGORY_SEVERITY_WEIGHTS,
  DEFAULT_STEALTH_SCORE_WEIGHTS,
  calculateReliabilityConfidence,
  normalizeDefectFrequency,
  calculateWeightedDefectFrequency,
  deriveGradeFromStealthScore,
  deriveVerdictFromStealthScore,
  calculateStealthScore as calculateStealthScorePure,
  getModelYearEvaluation as getModelYearEvaluationPure,
  resolveBrandReliability as resolveBrandReliabilityPure,
  getSafeDefaultBrandReliability,
  getBrandWithFallback as getBrandWithFallbackPure,
  getSafeDefaultModelReliability,
  aggregateQuarterlyDefectBreakdown,
  aggregateMonthlyDefectBreakdown,
  calculateModelYearDefectTrajectory,
  aggregateDefectTrendsByPeriod,
} from './reliabilityCalculations.ts';

export function getDsiSeverityLevel(dsi: number) {
  const safeDsi = Number.isFinite(dsi) ? Math.max(0, dsi) : 0;
  return getDsiSeverityLevelPure(safeDsi);
}

export {
  normalizeReliabilityScore,
  aggregateCategoryComplaintCounts,
  getAggregatedCategoryList,
  calculateTrendDirection,
  getVerdictBadgeInfo,
  getGradeBadgeStyle,
  DEFAULT_CATEGORY_SEVERITY_WEIGHTS,
  DEFAULT_STEALTH_SCORE_WEIGHTS,
  calculateReliabilityConfidence,
  normalizeDefectFrequency,
  calculateWeightedDefectFrequency,
  deriveGradeFromStealthScore,
  deriveVerdictFromStealthScore,
  getSafeDefaultBrandReliability,
  getSafeDefaultModelReliability,
  aggregateQuarterlyDefectBreakdown,
  aggregateMonthlyDefectBreakdown,
  calculateModelYearDefectTrajectory,
  aggregateDefectTrendsByPeriod,
};

// ==========================================
// 3. MASTER DATA LOADER & DATA-DEPENDENT WRAPPERS
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
 * Uses master trends database if data parameter is omitted.
 */
export function getAllEnrichedModels(data?: ReliabilityTrendsDatabase): EnrichedModelItem[] {
  return getAllEnrichedModelsPure(data || getReliabilityTrendsData());
}

/**
 * Calculates high-level KPI summary statistics from a ReliabilityTrendsDatabase.
 * Uses master trends database if data parameter is omitted.
 */
export function calculateReliabilityKPIs(data?: ReliabilityTrendsDatabase | null): ReliabilityKPIs {
  return calculateReliabilityKPIsPure(data || getReliabilityTrendsData());
}

/**
 * Finds a specific model by ID from the reliability trends dataset.
 * Uses master trends database if data parameter is omitted.
 */
export function getModelReliabilityById(
  modelId: string,
  data?: ReliabilityTrendsDatabase
): EnrichedModelItem | undefined {
  return getModelReliabilityByIdPure(modelId, data || getReliabilityTrendsData());
}

/**
 * Returns all year evaluations / defect records for a specific model.
 * Uses master trends database if data parameter is omitted.
 */
export function getDefectsForModel(
  modelId: string,
  data?: ReliabilityTrendsDatabase
): YearEvaluation[] {
  return getDefectsForModelPure(modelId, data || getReliabilityTrendsData());
}

/**
 * Finds a specific brand by ID or name from the reliability dataset.
 * Uses master trends database if data parameter is omitted.
 */
export function getBrandReliabilityById(
  brandId: string,
  data?: ReliabilityTrendsDatabase
): BrandReliability | undefined {
  return getBrandReliabilityByIdPure(brandId, data || getReliabilityTrendsData());
}

/**
 * Returns a specific year evaluation for a model.
 * Uses master trends database if data parameter is omitted.
 */
export function getModelYearEvaluation(
  modelId: string,
  year: number | string,
  data?: ReliabilityTrendsDatabase
): YearEvaluation | undefined {
  return getModelYearEvaluationPure(modelId, year, data || getReliabilityTrendsData());
}

/**
 * Safe fuzzy brand resolver that matches ID, Korean name, English name, or standard alias.
 * Uses master trends database if data parameter is omitted.
 */
export function resolveBrandReliability(
  brandQuery: string,
  data?: ReliabilityTrendsDatabase
): BrandReliability | undefined {
  return resolveBrandReliabilityPure(brandQuery, data || getReliabilityTrendsData());
}

/**
 * Returns a requested brand or safe default fallback if the brand is unknown.
 * Uses master trends database if data parameter is omitted.
 */
export function getBrandWithFallback(
  brandId: string,
  fallback?: BrandReliability,
  data?: ReliabilityTrendsDatabase
): BrandReliability {
  return getBrandWithFallbackPure(brandId, fallback, data || getReliabilityTrendsData());
}

/**
 * Evaluates the Stealth Reliability Composite Score using multi-factor weighting.
 * Defaults baselineIndustryDsi to master database average if omitted.
 */
export function calculateStealthScore(input?: StealthScoreInput | null): StealthScoreResult {
  let baseline = input?.baselineIndustryDsi;
  if (baseline === undefined || baseline === null) {
    try {
      const db = getReliabilityTrendsData();
      baseline = db?.metadata?.avg_industry_dsi ?? 50.0;
    } catch {
      baseline = 50.0;
    }
  }
  return calculateStealthScorePure({
    ...input,
    baselineIndustryDsi: baseline,
  });
}
