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
  parseFiniteNumber,
  sanitizeVerdict,
  sanitizeGrade,
  sanitizeCategoryKey,
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
  isPlainRecord,
  copySafeOwnFields,
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

const DEFAULT_FALLBACK_CATEGORIES: DefectCategoryMetadata[] = [
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
];

function createDefaultFallbackDatabase(): ReliabilityTrendsDatabase {
  return {
    metadata: {
      version: '1.0.0',
      updated_at: '2026-09-16T12:00:00Z',
      total_records_analyzed: 1280,
      brands_count: 0,
      models_count: 0,
      avg_industry_dsi: 64.2,
    },
    categories: DEFAULT_FALLBACK_CATEGORIES.map((c) => ({ ...c })),
    repair_cost_matrix: [],
    brands: [],
  };
}

let cachedTrendsDatabase: ReliabilityTrendsDatabase | null = null;

function ensureTrendsDatabaseLoaded(): ReliabilityTrendsDatabase {
  if (cachedTrendsDatabase) {
    return cachedTrendsDatabase;
  }
  const loaded = getReliabilityTrendsData();
  return cachedTrendsDatabase ?? loaded;
}

/**
 * Safely loads the master EV Reliability & Defect Trends database.
 * Strictly guarantees non-null, valid array/object shapes with defensive fallbacks
 * and bounds all DSI scores between [0, 100]. Caches normalized payload for reuse.
 */
export function getReliabilityTrendsData(): ReliabilityTrendsDatabase {
  if (cachedTrendsDatabase) {
    return cachedTrendsDatabase;
  }
  try {
    if (!isPlainRecord(rawTrendsData)) {
      return createDefaultFallbackDatabase();
    }

    const data = rawTrendsData as unknown as ReliabilityTrendsDatabase;

    const brands: BrandReliability[] = Array.isArray(data.brands)
      ? data.brands
          .filter((b): b is BrandReliability => isPlainRecord(b))
          .map((b) => {
            const safeBrandId = typeof b.id === 'string' ? b.id : '';
            const rawReports = parseFiniteNumber(b.total_reports);
            const rawCritical = parseFiniteNumber(b.critical_issue_rate);
            return {
              ...copySafeOwnFields(b),
              id: safeBrandId,
              name_ko: typeof b.name_ko === 'string' ? b.name_ko : '',
              name_en: typeof b.name_en === 'string' ? b.name_en : '',
              country: typeof b.country === 'string' ? b.country : '',
              overall_dsi: normalizeReliabilityScore(b.overall_dsi, 50.0),
              total_reports: rawReports !== null ? Math.max(0, Math.floor(rawReports)) : 0,
              critical_issue_rate:
                rawCritical !== null ? Math.max(0, Math.min(100, rawCritical)) : 0,
              category_distribution: aggregateCategoryComplaintCounts(
                b.category_distribution && typeof b.category_distribution === 'object'
                  ? b.category_distribution
                  : {}
              ) as Record<DefectCategoryKey, { count: number; percentage: number }>,
              models: Array.isArray(b.models)
                ? b.models
                    .filter((m): m is ModelReliability => isPlainRecord(m))
                    .map((m) => {
                      const modelBrandId = typeof m.brand_id === 'string' ? m.brand_id.trim() : '';
                      return {
                        ...copySafeOwnFields(m),
                        id: typeof m.id === 'string' ? m.id : '',
                        name: typeof m.name === 'string' ? m.name : '',
                        segment: typeof m.segment === 'string' ? m.segment : '',
                        brand_id: modelBrandId ? modelBrandId : safeBrandId,
                        overall_grade: sanitizeGrade(m.overall_grade),
                        avg_dsi: normalizeReliabilityScore(m.avg_dsi, 50.0),
                        top_category: sanitizeCategoryKey(m.top_category),
                        year_evaluations: Array.isArray(m.year_evaluations)
                          ? m.year_evaluations
                              .filter((y): y is YearEvaluation => isPlainRecord(y))
                              .map((y) => {
                                const parsedYear = parseFiniteNumber(y.year);
                                const parsedIncident = parseFiniteNumber(y.incident_rate);
                                return {
                                  ...copySafeOwnFields(y),
                                  year: parsedYear !== null ? Math.floor(parsedYear) + 0 : 0,
                                  verdict: sanitizeVerdict(y.verdict),
                                  dsi_score: normalizeReliabilityScore(y.dsi_score, 50.0),
                                  incident_rate:
                                    parsedIncident !== null
                                      ? Math.max(0, Math.min(100, parsedIncident)) + 0
                                      : 0,
                                  primary_defect:
                                    typeof y.primary_defect === 'string' ? y.primary_defect : '',
                                  estimated_repair_cost:
                                    typeof y.estimated_repair_cost === 'string'
                                      ? y.estimated_repair_cost
                                      : '',
                                  chronic_symptoms: Array.isArray(y.chronic_symptoms)
                                    ? y.chronic_symptoms.filter(
                                        (s): s is string => typeof s === 'string'
                                      )
                                    : [],
                                  raw_quote: typeof y.raw_quote === 'string' ? y.raw_quote : '',
                                };
                              })
                          : [],
                      };
                    })
                : [],
            };
          })
      : [];

    const rawMetaObj = isPlainRecord(data.metadata)
      ? (data.metadata as ReliabilityTrendsDatabase['metadata'])
      : undefined;
    const rawTotal =
      parseFiniteNumber(rawMetaObj?.total_records_analyzed) ??
      parseFiniteNumber(
        (rawMetaObj as unknown as Record<string, unknown> | undefined)?.total_analyzed_posts
      );
    const brandReportsSum = brands.reduce((acc, b) => {
      const next = acc + b.total_reports;
      return Number.isFinite(next) ? next : Number.MAX_VALUE;
    }, 0);
    const total_records_analyzed =
      rawTotal !== null && rawTotal >= 0
        ? Math.floor(rawTotal)
        : brandReportsSum > 0
          ? brandReportsSum
          : 1280;

    const rawAvgDsi = parseFiniteNumber(rawMetaObj?.avg_industry_dsi);
    let avg_industry_dsi = 64.2;
    if (rawAvgDsi !== null) {
      avg_industry_dsi = normalizeReliabilityScore(rawAvgDsi, 64.2);
    } else if (brands.length > 0) {
      const computedKpis = calculateReliabilityKPIsPure({
        metadata: { version: '1.0.0' },
        repair_cost_matrix: [],
        brands,
      });
      avg_industry_dsi = computedKpis.industryAvgDsi;
    }

    const updatedAt =
      (typeof rawMetaObj?.updated_at === 'string' && rawMetaObj.updated_at.trim()) ||
      (typeof rawMetaObj?.last_updated === 'string' && rawMetaObj.last_updated.trim()) ||
      '2026-09-16T12:00:00Z';

    const metadata = {
      version:
        typeof rawMetaObj?.version === 'string' && rawMetaObj.version.trim()
          ? rawMetaObj.version
          : '1.0.0',
      updated_at: updatedAt,
      total_records_analyzed,
      brands_count: brands.length,
      models_count: brands.reduce((acc, b) => acc + b.models.length, 0),
      avg_industry_dsi,
    };

    const rawCategories = Array.isArray(data.categories)
      ? data.categories
      : Array.isArray(data.defect_categories)
        ? data.defect_categories
        : [];
    const validCategories = rawCategories
      .filter(
        (c): c is DefectCategoryMetadata =>
          isPlainRecord(c) && typeof c.code === 'string' && c.code.trim().length > 0
      )
      .map((c) => {
        const share = parseFiniteNumber(c.industry_share_pct);
        return {
          ...copySafeOwnFields(c),
          code: sanitizeCategoryKey(c.code),
          label_ko: typeof c.label_ko === 'string' ? c.label_ko : '',
          description: typeof c.description === 'string' ? c.description : '',
          icon_name: typeof c.icon_name === 'string' ? c.icon_name : 'AlertCircle',
          industry_share_pct: share !== null ? Math.max(0, Math.min(100, share)) : 0,
          avg_repair_cost_range:
            typeof c.avg_repair_cost_range === 'string' ? c.avg_repair_cost_range : '',
        };
      });
    const categories =
      validCategories.length > 0
        ? validCategories
        : DEFAULT_FALLBACK_CATEGORIES.map((c) => ({ ...c }));

    const repair_cost_matrix = Array.isArray(data.repair_cost_matrix)
      ? data.repair_cost_matrix
          .filter(
            (r): r is RepairCostMatrixItem =>
              isPlainRecord(r) && typeof r.component_name === 'string'
          )
          .map((r) => ({
            ...copySafeOwnFields(r),
            affected_systems: typeof r.affected_systems === 'string' ? r.affected_systems : '',
            avg_cost_krw: typeof r.avg_cost_krw === 'string' ? r.avg_cost_krw : '',
            standard_warranty: typeof r.standard_warranty === 'string' ? r.standard_warranty : '',
            high_risk_models: Array.isArray(r.high_risk_models)
              ? r.high_risk_models.filter((m): m is string => typeof m === 'string')
              : undefined,
            representative_models: Array.isArray(r.representative_models)
              ? r.representative_models.filter((m): m is string => typeof m === 'string')
              : undefined,
          }))
      : [];

    cachedTrendsDatabase = {
      metadata,
      categories,
      repair_cost_matrix,
      brands,
    };
    return cachedTrendsDatabase;
  } catch (error) {
    console.error('[getReliabilityTrendsData] Failed to load trends data safely:', error);
    return createDefaultFallbackDatabase();
  }
}

/**
 * Returns a flattened array of all models enriched with brand information.
 * Uses master trends database if data parameter is omitted.
 */
export function getAllEnrichedModels(data?: ReliabilityTrendsDatabase | null): EnrichedModelItem[] {
  return getAllEnrichedModelsPure(data === undefined ? ensureTrendsDatabaseLoaded() : data);
}

/**
 * Calculates high-level KPI summary statistics from a ReliabilityTrendsDatabase.
 * Uses master trends database if data parameter is omitted.
 */
export function calculateReliabilityKPIs(data?: ReliabilityTrendsDatabase | null): ReliabilityKPIs {
  return calculateReliabilityKPIsPure(data === undefined ? ensureTrendsDatabaseLoaded() : data);
}

/**
 * Finds a specific model by ID from the reliability trends dataset.
 * Uses master trends database if data parameter is omitted.
 */
export function getModelReliabilityById(
  modelId: string,
  data?: ReliabilityTrendsDatabase | null
): EnrichedModelItem | undefined {
  return getModelReliabilityByIdPure(modelId, data === undefined ? ensureTrendsDatabaseLoaded() : data);
}

/**
 * Returns all year evaluations / defect records for a specific model.
 * Uses master trends database if data parameter is omitted.
 */
export function getDefectsForModel(
  modelId: string,
  data?: ReliabilityTrendsDatabase | null
): YearEvaluation[] {
  return getDefectsForModelPure(modelId, data === undefined ? ensureTrendsDatabaseLoaded() : data);
}

/**
 * Finds a specific brand by ID or name from the reliability dataset.
 * Uses master trends database if data parameter is omitted.
 */
export function getBrandReliabilityById(
  brandId: string,
  data?: ReliabilityTrendsDatabase | null
): BrandReliability | undefined {
  return getBrandReliabilityByIdPure(brandId, data === undefined ? ensureTrendsDatabaseLoaded() : data);
}

/**
 * Returns a specific year evaluation for a model.
 * Uses master trends database if data parameter is omitted.
 */
export function getModelYearEvaluation(
  modelId: string,
  year: number | string,
  data?: ReliabilityTrendsDatabase | null
): YearEvaluation | undefined {
  return getModelYearEvaluationPure(modelId, year, data === undefined ? ensureTrendsDatabaseLoaded() : data);
}

/**
 * Safe fuzzy brand resolver that matches ID, Korean name, English name, or standard alias.
 * Uses master trends database if data parameter is omitted.
 */
export function resolveBrandReliability(
  brandQuery: string,
  data?: ReliabilityTrendsDatabase | null
): BrandReliability | undefined {
  return resolveBrandReliabilityPure(brandQuery, data === undefined ? ensureTrendsDatabaseLoaded() : data);
}

/**
 * Returns a requested brand or safe default fallback if the brand is unknown.
 * Uses master trends database if data parameter is omitted.
 */
export function getBrandWithFallback(
  brandId: string,
  fallback?: BrandReliability,
  data?: ReliabilityTrendsDatabase | null
): BrandReliability {
  return getBrandWithFallbackPure(brandId, fallback, data === undefined ? ensureTrendsDatabaseLoaded() : data);
}

/**
 * Evaluates the Stealth Reliability Composite Score using multi-factor weighting.
 * Defaults baselineIndustryDsi to master database average if omitted.
 */
export function calculateStealthScore(input?: StealthScoreInput | null): StealthScoreResult {
  const safeInput = input && typeof input === 'object' ? input : {};
  let baseline = safeInput.baselineIndustryDsi;
  if (baseline === undefined || baseline === null) {
    try {
      const db = ensureTrendsDatabaseLoaded();
      baseline = db?.metadata?.avg_industry_dsi ?? 50.0;
    } catch {
      baseline = 50.0;
    }
  }
  return calculateStealthScorePure({
    ...safeInput,
    baselineIndustryDsi: baseline,
  });
}
