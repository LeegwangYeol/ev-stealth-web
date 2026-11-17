import rawData from '../data/ev_subsidy_data.json' with { type: 'json' };
import type {
  EVSubsidyDataset,
  PopularModelEntry,
  RegionEntry,
  SubsidyCalculationResult,
  SubsidyCalculatorOptions,
  AlertSeverity,
} from '../types/subsidy.ts';
import {
  calculateDepletionRate,
  calculateDeliveryRate,
  calculateRemainingUnits,
  calculateWaitlistUnits,
  isDepletionOverExhausted,
  calculatePendingDeliveries,
  calculateDepletionVelocity,
  predictExhaustionDays,
  predictExhaustionDate,
  parseSubsidyNumber,
  parseModelSubsidy,
  parseCategoryMetrics,
  resolveAlertSeverity,
  getRegionByIdFromList,
  getModelByIdFromList,
  DEFAULT_NATIONWIDE_SUMMARY,
  safeCompareNumbers,
  compareRegions,
  sortRegions,
  rankRegionsByDepletion,
  compareModels,
  sortModels,
  getPriceSubsidyRatio,
  calculateNetSubsidyPure,
  calculateSubsidyStatistics,
  formatCurrencyKrw,
  formatManwon,
  formatBillionKrw,
  formatDepletionRate,
  getDepletionBadgeStyle,
  REGION_ALIAS_MAP,
  METROPOLITAN_CITIES,
  PROVINCES,
  METROPOLITAN_CITY_CODES,
  PROVINCE_CODES,
  classifyRegionGroup,
  isMetropolitanCity,
  isProvince,
  groupRegionsByType,
  type DepletionRateOptions,
  type ParseSubsidyNumberOptions,
  type ParsedModelSubsidy,
  type ParsedCategoryMetrics,
  type RegionSortOption,
  type ModelSortOption,
  type RankedRegionEntry,
  type HistoricalTrajectoryPoint,
  type RegionalGroup,
  type RegionalGroupSummary,
} from './subsidyCalculations.ts';

export {
  calculateDepletionRate,
  calculateDeliveryRate,
  calculateRemainingUnits,
  calculateWaitlistUnits,
  isDepletionOverExhausted,
  calculatePendingDeliveries,
  calculateDepletionVelocity,
  predictExhaustionDays,
  predictExhaustionDate,
  parseSubsidyNumber,
  parseModelSubsidy,
  parseCategoryMetrics,
  safeCompareNumbers,
  compareRegions,
  sortRegions,
  rankRegionsByDepletion,
  compareModels,
  sortModels,
  getPriceSubsidyRatio,
  calculateNetSubsidyPure,
  calculateSubsidyStatistics,
  formatCurrencyKrw,
  formatManwon,
  formatBillionKrw,
  formatDepletionRate,
  getDepletionBadgeStyle,
  REGION_ALIAS_MAP,
  METROPOLITAN_CITIES,
  PROVINCES,
  METROPOLITAN_CITY_CODES,
  PROVINCE_CODES,
  classifyRegionGroup,
  isMetropolitanCity,
  isProvince,
  groupRegionsByType,
  type DepletionRateOptions,
  type ParseSubsidyNumberOptions,
  type ParsedModelSubsidy,
  type ParsedCategoryMetrics,
  type RegionSortOption,
  type ModelSortOption,
  type RankedRegionEntry,
  type HistoricalTrajectoryPoint,
  type RegionalGroup,
  type RegionalGroupSummary,
};

// Robust typed fallback in case raw JSON is missing or malformed
const fallbackDataset: EVSubsidyDataset = {
  metadata: {
    version: '1.0.0',
    generated_at: new Date().toISOString(),
    policy_year: 2026,
    data_sources: [
      '환경부 무공해차 통합누리집 (ev.or.kr)',
      '한국환경공단 (KECO) CleanSys',
      '17개 광역시도 무공해차 보급 촉진 고시공고',
    ],
    total_regions_tracked: 17,
    total_municipalities_tracked: 73,
    currency: 'KRW',
  },
  alert_thresholds: {
    HEALTHY: {
      min_percent: 0.0,
      max_percent: 59.9,
      label_ko: '원활 (신청 여유)',
      severity: 'HEALTHY',
      color_hex: '#10B981',
      badge_class: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
      recommended_action: '보조금 잔여량이 충분하여 신청 접수 후 통상 1~2주 내 교부 결정됩니다.',
    },
    CAUTION: {
      min_percent: 60.0,
      max_percent: 79.9,
      label_ko: '주의 (소진 가속)',
      severity: 'CAUTION',
      color_hex: '#F59E0B',
      badge_class: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      recommended_action: '출고 예정 시기가 1~2개월 이내인 경우 조속한 서류 접수를 권장합니다.',
    },
    WARNING: {
      min_percent: 80.0,
      max_percent: 94.9,
      label_ko: '경고 (마감 임박)',
      severity: 'WARNING',
      color_hex: '#F97316',
      badge_class: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
      recommended_action: '잔여 예산 소진이 임박했습니다. 즉시 출고 가능한 실재고 매칭이 필요합니다.',
    },
    CRITICAL: {
      min_percent: 95.0,
      max_percent: 99.9,
      label_ko: '위험 (잔여 극소)',
      severity: 'CRITICAL',
      color_hex: '#EF4444',
      badge_class: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
      recommended_action: '선착순 마감 직전입니다. 담당 지자체 문의 및 추경 예산 편성 여부를 확인하세요.',
    },
    DEPLETED: {
      min_percent: 100.0,
      max_percent: 999.0,
      label_ko: '마감 (접수 종료)',
      severity: 'DEPLETED',
      color_hex: '#6B7280',
      badge_class: 'bg-slate-800 text-slate-200 border-slate-600',
      recommended_action: '2026년 공고 예산이 전액 소진되었습니다. 취소분 대기 접수 또는 차년도 사업을 준비하세요.',
    },
  },
  nationwide_summary: {
    total_announced_units: 148510,
    total_applied_units: 132766,
    total_delivered_units: 122515,
    total_remaining_units: 15744,
    nationwide_depletion_rate: 89.4,
    total_budget_billion_krw: 2105.1,
    disbursed_budget_billion_krw: 1893.4,
    category_totals: {
      passenger: {
        announced_units: 110400,
        applied_units: 97035,
        delivered_units: 88960,
        remaining_units: 13365,
        depletion_rate: 87.9,
        delivery_rate: 80.6,
        status: 'WARNING',
        max_local_subsidy_krw: 3500000,
        max_total_subsidy_krw: 10000000,
      },
      commercial: {
        announced_units: 34800,
        applied_units: 32754,
        delivered_units: 30780,
        remaining_units: 2046,
        depletion_rate: 94.1,
        delivery_rate: 88.4,
        status: 'WARNING',
        max_local_subsidy_krw: 6000000,
        max_total_subsidy_krw: 16500000,
      },
      bus: {
        announced_units: 3310,
        applied_units: 2977,
        delivered_units: 2775,
        remaining_units: 333,
        depletion_rate: 89.9,
        delivery_rate: 83.8,
        status: 'WARNING',
        max_local_subsidy_krw: 35000000,
        max_total_subsidy_krw: 105000000,
      },
    },
    alert_region_counts: {
      healthy: 0,
      caution: 1,
      warning: 12,
      critical: 4,
      depleted: 0,
    },
  },
  regions: [],
  popular_models_matrix: [],
};

/**
 * Returns the strongly-typed EV Subsidy Database.
 */
export function getSubsidyDatabase(): EVSubsidyDataset {
  try {
    if (rawData && typeof rawData === 'object' && Array.isArray((rawData as Record<string, unknown>).regions)) {
      const typed = rawData as unknown as Partial<EVSubsidyDataset>;
      return {
        metadata: typed.metadata && typeof typed.metadata === 'object' ? typed.metadata : fallbackDataset.metadata,
        alert_thresholds:
          typed.alert_thresholds && typeof typed.alert_thresholds === 'object'
            ? typed.alert_thresholds
            : fallbackDataset.alert_thresholds,
        nationwide_summary:
          typed.nationwide_summary && typeof typed.nationwide_summary === 'object'
            ? typed.nationwide_summary
            : fallbackDataset.nationwide_summary,
        regions: Array.isArray(typed.regions) ? typed.regions : fallbackDataset.regions,
        popular_models_matrix: Array.isArray(typed.popular_models_matrix)
          ? typed.popular_models_matrix
          : fallbackDataset.popular_models_matrix,
        ...(Array.isArray(typed.historical_depletion_trajectory)
          ? { historical_depletion_trajectory: typed.historical_depletion_trajectory }
          : {}),
      };
    }
    return fallbackDataset;
  } catch (err) {
    console.error('Failed to load subsidy database, using fallback:', err);
    return fallbackDataset;
  }
}

/**
 * Returns all regions tracked in the database.
 */
export function getAllRegions(): RegionEntry[] {
  const db = getSubsidyDatabase();
  return Array.isArray(db?.regions) ? db.regions : [];
}

/**
 * Finds a specific region by region_id, iso_code, Korean name, or colloquial alias.
 * Guards against null elements and missing string properties.
 */
export function getRegionById(regionId: string): RegionEntry | undefined {
  return getRegionByIdFromList(getAllRegions(), regionId);
}

/**
 * Returns all popular vehicle models in the matrix.
 */
export function getAllModels(): PopularModelEntry[] {
  const db = getSubsidyDatabase();
  return Array.isArray(db?.popular_models_matrix) ? db.popular_models_matrix : [];
}

/**
 * Finds a vehicle model by model_id or Korean name, supporting whitespace- and hyphen-normalized queries.
 * Guards against null elements and missing string properties.
 */
export function getModelById(modelId: string): PopularModelEntry | undefined {
  return getModelByIdFromList(getAllModels(), modelId);
}


/**
 * Calculates the comprehensive net subsidy and out-of-pocket purchase price
 * for a chosen vehicle model in a designated administrative region.
 * Automatically resolves model and region IDs and delegates to pure calculation engine.
 */
export function calculateNetSubsidy(
  modelId: string,
  regionId: string,
  customMsrp?: number | string | null,
  options?: SubsidyCalculatorOptions
): SubsidyCalculationResult {
  const models = getAllModels();
  const regions = getAllRegions();
  const defaultModel: PopularModelEntry = models.find((m): m is PopularModelEntry => Boolean(m && typeof m === 'object')) || {
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
  const defaultRegion: RegionEntry =
    regions.find((r): r is RegionEntry => Boolean(r && typeof r === 'object' && r.region_id === 'KR-11')) ||
    regions.find((r): r is RegionEntry => Boolean(r && typeof r === 'object')) || {
      region_id: 'KR-11',
      iso_code: 'KR-11',
      name_ko: '서울특별시',
      name_en: 'Seoul',
      tier: 'special_city',
      overall_depletion_rate: 0,
      overall_status: 'HEALTHY',
      residency_requirement_days: 30,
      supplementary_budget_added: false,
      categories: DEFAULT_NATIONWIDE_SUMMARY.category_totals,
    };

  const model = getModelById(modelId) || defaultModel;
  const region = getRegionById(regionId) || defaultRegion;
  return calculateNetSubsidyPure(model, region, customMsrp, options);
}

/**
 * Safely retrieves category depletion metrics for a given region or category object,
 * guarding all numerical values and toLocaleString calls against null/undefined.
 */
export function getCategoryDepletion(
  regionOrId?: RegionEntry | string | null,
  categoryKey: 'passenger' | 'commercial' | 'bus' = 'passenger'
): {
  announcedUnits: number;
  appliedUnits: number;
  remainingUnits: number;
  depletionRate: number;
  status: AlertSeverity;
  formattedRemaining: string;
  formattedAnnounced: string;
  formattedApplied: string;
} {
  let region: RegionEntry | undefined;
  if (typeof regionOrId === 'string') {
    region = getRegionById(regionOrId);
  } else if (regionOrId && typeof regionOrId === 'object') {
    if ('categories' in regionOrId && regionOrId.categories && typeof regionOrId.categories === 'object') {
      region = regionOrId as RegionEntry;
    } else if ('region_id' in regionOrId && typeof regionOrId.region_id === 'string') {
      region = getRegionById(regionOrId.region_id);
    }
  }

  const category = region?.categories?.[categoryKey];
  const rawAnnounced = category?.announced_units;
  const rawApplied = category?.applied_units;
  const announced = typeof rawAnnounced === 'number' && !Number.isFinite(rawAnnounced)
    ? 0
    : parseSubsidyNumber(rawAnnounced, { defaultKrw: 0 });
  const applied = typeof rawApplied === 'number' && !Number.isFinite(rawApplied)
    ? 0
    : parseSubsidyNumber(rawApplied, { defaultKrw: 0 });
  const remaining = typeof category?.remaining_units === 'number' && Number.isFinite(category.remaining_units) && category.remaining_units >= 0
    ? category.remaining_units
    : calculateRemainingUnits(applied, announced);
  const rate = typeof category?.depletion_rate === 'number' && Number.isFinite(category.depletion_rate) && category.depletion_rate >= 0
    ? category.depletion_rate
    : calculateDepletionRate(applied, announced);
  const status: AlertSeverity = resolveAlertSeverity(category?.status, rate);

  const safeAnnounced = Number.isFinite(announced) ? announced : 0;
  const safeApplied = Number.isFinite(applied) ? applied : 0;
  const safeRemaining = Number.isFinite(remaining) ? remaining : 0;
  const safeRate = Number.isFinite(rate) ? rate : 0.0;

  return {
    announcedUnits: safeAnnounced,
    appliedUnits: safeApplied,
    remainingUnits: safeRemaining,
    depletionRate: safeRate,
    status,
    formattedRemaining: safeRemaining.toLocaleString(),
    formattedAnnounced: safeAnnounced.toLocaleString(),
    formattedApplied: safeApplied.toLocaleString(),
  };
}

