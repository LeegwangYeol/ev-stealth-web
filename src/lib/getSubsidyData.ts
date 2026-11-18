import rawData from '../data/ev_subsidy_data.json' with { type: 'json' };
import type {
  EVSubsidyDataset,
  PopularModelEntry,
  RegionEntry,
  CategoryMetrics,
  AlertThresholdConfig,
  SubsidyCalculationResult,
  SubsidyCalculatorOptions,
  SubsidyCategoryKey,
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

const ALERT_SEVERITIES: readonly AlertSeverity[] = [
  'HEALTHY',
  'CAUTION',
  'WARNING',
  'CRITICAL',
  'DEPLETED',
];

const CATEGORY_KEYS: readonly SubsidyCategoryKey[] = ['passenger', 'commercial', 'bus'];

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}

function safeNonNegNum(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : fallback;
}

function safeNonEmptyStr(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.trim().length > 0 ? value : fallback;
}

function normalizeCategoryMetricsObj(raw: unknown, fb: CategoryMetrics): CategoryMetrics {
  if (!isPlainRecord(raw)) {
    return fb;
  }
  const announced = safeNonNegNum(raw.announced_units, fb.announced_units);
  const applied = safeNonNegNum(raw.applied_units, fb.applied_units);
  const delivered = safeNonNegNum(raw.delivered_units, fb.delivered_units);
  const remaining = safeNonNegNum(raw.remaining_units, calculateRemainingUnits(applied, announced));
  const depletionRate = safeNonNegNum(raw.depletion_rate, calculateDepletionRate(applied, announced));
  const deliveryRate = safeNonNegNum(raw.delivery_rate, calculateDeliveryRate(delivered, announced));
  const status = resolveAlertSeverity(raw.status, depletionRate);

  return {
    announced_units: announced,
    applied_units: applied,
    delivered_units: delivered,
    remaining_units: remaining,
    depletion_rate: depletionRate,
    delivery_rate: deliveryRate,
    status,
    ...(typeof raw.max_local_subsidy_krw === 'number' && Number.isFinite(raw.max_local_subsidy_krw) && raw.max_local_subsidy_krw >= 0
      ? { max_local_subsidy_krw: raw.max_local_subsidy_krw }
      : fb.max_local_subsidy_krw !== undefined
      ? { max_local_subsidy_krw: fb.max_local_subsidy_krw }
      : {}),
    ...(typeof raw.max_total_subsidy_krw === 'number' && Number.isFinite(raw.max_total_subsidy_krw) && raw.max_total_subsidy_krw >= 0
      ? { max_total_subsidy_krw: raw.max_total_subsidy_krw }
      : fb.max_total_subsidy_krw !== undefined
      ? { max_total_subsidy_krw: fb.max_total_subsidy_krw }
      : {}),
    ...(typeof raw.total_budget_krw === 'number' && Number.isFinite(raw.total_budget_krw) && raw.total_budget_krw >= 0
      ? { total_budget_krw: raw.total_budget_krw }
      : {}),
    ...(typeof raw.remaining_budget_krw === 'number' && Number.isFinite(raw.remaining_budget_krw) && raw.remaining_budget_krw >= 0
      ? { remaining_budget_krw: raw.remaining_budget_krw }
      : {}),
  };
}

/**
 * Validates and deeply normalizes an untrusted or partially corrupted EV subsidy dataset
 * so missing nested fields, non-object array entries, or NaN/Infinity values never crash consumers.
 */
export function normalizeSubsidyDataset(data: unknown): EVSubsidyDataset {
  if (!isPlainRecord(data) || !Array.isArray(data.regions)) {
    return fallbackDataset;
  }

  const rawMeta = isPlainRecord(data.metadata) ? data.metadata : {};
  const fbMeta = fallbackDataset.metadata;
  const metadata: EVSubsidyDataset['metadata'] = {
    version: safeNonEmptyStr(rawMeta.version, fbMeta.version),
    generated_at: safeNonEmptyStr(rawMeta.generated_at, fbMeta.generated_at),
    policy_year:
      typeof rawMeta.policy_year === 'number' && Number.isFinite(rawMeta.policy_year) && rawMeta.policy_year >= 2020
        ? Math.floor(rawMeta.policy_year)
        : fbMeta.policy_year,
    data_sources: Array.isArray(rawMeta.data_sources)
      ? rawMeta.data_sources.filter((s): s is string => typeof s === 'string' && s.trim().length > 0)
      : fbMeta.data_sources,
    total_regions_tracked: safeNonNegNum(rawMeta.total_regions_tracked, fbMeta.total_regions_tracked),
    total_municipalities_tracked: safeNonNegNum(
      rawMeta.total_municipalities_tracked,
      fbMeta.total_municipalities_tracked
    ),
    currency: safeNonEmptyStr(rawMeta.currency, fbMeta.currency),
  };
  if (metadata.data_sources.length === 0) {
    metadata.data_sources = fbMeta.data_sources;
  }

  const rawThresholds = isPlainRecord(data.alert_thresholds) ? data.alert_thresholds : {};
  const alertThresholds = {} as Record<AlertSeverity, AlertThresholdConfig>;
  for (const sev of ALERT_SEVERITIES) {
    const fbCfg = fallbackDataset.alert_thresholds[sev];
    const rawCfg = Object.prototype.hasOwnProperty.call(rawThresholds, sev) && isPlainRecord(rawThresholds[sev])
      ? (rawThresholds[sev] as Record<string, unknown>)
      : {};
    alertThresholds[sev] = {
      min_percent: typeof rawCfg.min_percent === 'number' && Number.isFinite(rawCfg.min_percent) ? rawCfg.min_percent : fbCfg.min_percent,
      max_percent: typeof rawCfg.max_percent === 'number' && Number.isFinite(rawCfg.max_percent) ? rawCfg.max_percent : fbCfg.max_percent,
      label_ko: safeNonEmptyStr(rawCfg.label_ko, fbCfg.label_ko),
      severity: sev,
      color_hex: safeNonEmptyStr(rawCfg.color_hex, fbCfg.color_hex),
      badge_class: safeNonEmptyStr(rawCfg.badge_class, fbCfg.badge_class),
      recommended_action: safeNonEmptyStr(rawCfg.recommended_action, fbCfg.recommended_action),
    };
  }

  const rawSummary = isPlainRecord(data.nationwide_summary) ? data.nationwide_summary : {};
  const fbSummary = fallbackDataset.nationwide_summary;
  const rawCatTotals = isPlainRecord(rawSummary.category_totals) ? rawSummary.category_totals : {};
  const rawAlertCounts = isPlainRecord(rawSummary.alert_region_counts) ? rawSummary.alert_region_counts : {};

  const nationwideSummary: EVSubsidyDataset['nationwide_summary'] = {
    total_announced_units: safeNonNegNum(rawSummary.total_announced_units, fbSummary.total_announced_units),
    total_applied_units: safeNonNegNum(rawSummary.total_applied_units, fbSummary.total_applied_units),
    total_delivered_units: safeNonNegNum(rawSummary.total_delivered_units, fbSummary.total_delivered_units),
    total_remaining_units: safeNonNegNum(rawSummary.total_remaining_units, fbSummary.total_remaining_units),
    nationwide_depletion_rate: safeNonNegNum(
      rawSummary.nationwide_depletion_rate,
      fbSummary.nationwide_depletion_rate
    ),
    total_budget_billion_krw: safeNonNegNum(
      rawSummary.total_budget_billion_krw,
      fbSummary.total_budget_billion_krw
    ),
    disbursed_budget_billion_krw: safeNonNegNum(
      rawSummary.disbursed_budget_billion_krw,
      fbSummary.disbursed_budget_billion_krw
    ),
    ...(typeof rawSummary.total_budget_krw === 'number' && Number.isFinite(rawSummary.total_budget_krw) && rawSummary.total_budget_krw >= 0
      ? { total_budget_krw: rawSummary.total_budget_krw }
      : {}),
    ...(typeof rawSummary.disbursed_budget_krw === 'number' && Number.isFinite(rawSummary.disbursed_budget_krw) && rawSummary.disbursed_budget_krw >= 0
      ? { disbursed_budget_krw: rawSummary.disbursed_budget_krw }
      : {}),
    category_totals: {
      passenger: normalizeCategoryMetricsObj(rawCatTotals.passenger, fbSummary.category_totals.passenger),
      commercial: normalizeCategoryMetricsObj(rawCatTotals.commercial, fbSummary.category_totals.commercial),
      bus: normalizeCategoryMetricsObj(rawCatTotals.bus, fbSummary.category_totals.bus),
    },
    alert_region_counts: {
      healthy: safeNonNegNum(rawAlertCounts.healthy, fbSummary.alert_region_counts.healthy),
      caution: safeNonNegNum(rawAlertCounts.caution, fbSummary.alert_region_counts.caution),
      warning: safeNonNegNum(rawAlertCounts.warning, fbSummary.alert_region_counts.warning),
      critical: safeNonNegNum(rawAlertCounts.critical, fbSummary.alert_region_counts.critical),
      depleted: safeNonNegNum(rawAlertCounts.depleted, fbSummary.alert_region_counts.depleted),
    },
  };

  const regions: RegionEntry[] = data.regions.filter((r): r is RegionEntry => isPlainRecord(r));
  const popularModels: PopularModelEntry[] = Array.isArray(data.popular_models_matrix)
    ? data.popular_models_matrix.filter((m): m is PopularModelEntry => isPlainRecord(m))
    : fallbackDataset.popular_models_matrix;

  const trajectory: HistoricalTrajectoryPoint[] | undefined = Array.isArray(data.historical_depletion_trajectory)
    ? data.historical_depletion_trajectory
        .filter((pt): pt is Record<string, unknown> => isPlainRecord(pt))
        .map((pt) => ({
          date: safeNonEmptyStr(pt.date, metadata.generated_at.slice(0, 10)),
          passenger_rate: safeNonNegNum(pt.passenger_rate, 0),
          commercial_rate: safeNonNegNum(pt.commercial_rate, 0),
          overall_rate: safeNonNegNum(pt.overall_rate, 0),
        }))
    : undefined;

  return {
    metadata,
    alert_thresholds: alertThresholds,
    nationwide_summary: nationwideSummary,
    regions,
    popular_models_matrix: popularModels,
    ...(trajectory ? { historical_depletion_trajectory: trajectory } : {}),
  };
}

let cachedDatabase: EVSubsidyDataset | null = null;

/**
 * Returns the strongly-typed EV Subsidy Database.
 */
export function getSubsidyDatabase(): EVSubsidyDataset {
  if (cachedDatabase) {
    return cachedDatabase;
  }
  try {
    cachedDatabase = normalizeSubsidyDataset(rawData);
    return cachedDatabase;
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

  const model = getModelByIdFromList(models, modelId) || defaultModel;
  const region = getRegionByIdFromList(regions, regionId) || defaultRegion;
  return calculateNetSubsidyPure(model, region, customMsrp, options);
}

/**
 * Safely retrieves category depletion metrics for a given region or category object,
 * guarding all numerical values and toLocaleString calls against null/undefined.
 */
export function getCategoryDepletion(
  regionOrId?: RegionEntry | string | null,
  categoryKey: SubsidyCategoryKey = 'passenger'
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
  } else if (isPlainRecord(regionOrId)) {
    if ('categories' in regionOrId && isPlainRecord(regionOrId.categories)) {
      region = regionOrId as unknown as RegionEntry;
    } else if ('region_id' in regionOrId && typeof regionOrId.region_id === 'string') {
      region = getRegionById(regionOrId.region_id);
    }
  }

  const rawCategories = region?.categories as unknown;
  const category =
    CATEGORY_KEYS.includes(categoryKey) &&
    isPlainRecord(rawCategories) &&
    Object.prototype.hasOwnProperty.call(rawCategories, categoryKey) &&
    isPlainRecord(rawCategories[categoryKey])
      ? (rawCategories[categoryKey] as unknown as CategoryMetrics)
      : undefined;
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

