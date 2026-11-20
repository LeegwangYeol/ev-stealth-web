import rawData from '../data/ev_subsidy_data.json' with { type: 'json' };
import type {
  EVSubsidyDataset,
  PopularModelEntry,
  RegionEntry,
  RegionTier,
  CategoryMetrics,
  MunicipalityMetrics,
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
  DEFAULT_SUBSIDY_THRESHOLDS,
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
const fallbackDataset: EVSubsidyDataset = Object.freeze({
  metadata: Object.freeze({
    version: '1.0.0',
    generated_at: new Date().toISOString(),
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
  alert_thresholds: DEFAULT_SUBSIDY_THRESHOLDS as Record<AlertSeverity, AlertThresholdConfig>,
  nationwide_summary: Object.freeze({
    total_announced_units: 148510,
    total_applied_units: 132766,
    total_delivered_units: 122515,
    total_remaining_units: 15744,
    nationwide_depletion_rate: 89.4,
    total_budget_billion_krw: 2105.1,
    disbursed_budget_billion_krw: 1893.4,
    category_totals: Object.freeze({
      passenger: Object.freeze({
        announced_units: 110400,
        applied_units: 97035,
        delivered_units: 88960,
        remaining_units: 13365,
        depletion_rate: 87.9,
        delivery_rate: 80.6,
        status: 'WARNING' as AlertSeverity,
        max_local_subsidy_krw: 3500000,
        max_total_subsidy_krw: 10000000,
      }),
      commercial: Object.freeze({
        announced_units: 34800,
        applied_units: 32754,
        delivered_units: 30780,
        remaining_units: 2046,
        depletion_rate: 94.1,
        delivery_rate: 88.4,
        status: 'WARNING' as AlertSeverity,
        max_local_subsidy_krw: 6000000,
        max_total_subsidy_krw: 16500000,
      }),
      bus: Object.freeze({
        announced_units: 3310,
        applied_units: 2977,
        delivered_units: 2775,
        remaining_units: 333,
        depletion_rate: 89.9,
        delivery_rate: 83.8,
        status: 'WARNING' as AlertSeverity,
        max_local_subsidy_krw: 35000000,
        max_total_subsidy_krw: 105000000,
      }),
    }),
    alert_region_counts: Object.freeze({
      healthy: 0,
      caution: 1,
      warning: 12,
      critical: 4,
      depleted: 0,
    }),
  }),
  regions: Object.freeze([]) as unknown as RegionEntry[],
  popular_models_matrix: Object.freeze([]) as unknown as PopularModelEntry[],
}) as EVSubsidyDataset;

const ALERT_SEVERITIES: readonly AlertSeverity[] = [
  'HEALTHY',
  'CAUTION',
  'WARNING',
  'CRITICAL',
  'DEPLETED',
];

const CATEGORY_KEYS: readonly SubsidyCategoryKey[] = ['passenger', 'commercial', 'bus'];

const VALID_REGION_TIERS: ReadonlySet<RegionTier> = new Set([
  'special_city',
  'metropolitan_city',
  'special_self_governing_city',
  'province',
  'special_self_governing_province',
]);

const FORBIDDEN_PROTO_KEYS: ReadonlySet<string> = new Set([
  '__proto__',
  'constructor',
  'prototype',
]);

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}

function safeNonNegNum(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
    ? (value === 0 ? 0 : value)
    : fallback;
}

function safeNonEmptyStr(value: unknown, fallback: string): string {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : fallback;
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

  const maxLocal = safeNonNegNum(raw.max_local_subsidy_krw, -1);
  const maxTotal = safeNonNegNum(raw.max_total_subsidy_krw, -1);
  const totalBudget = safeNonNegNum(raw.total_budget_krw, -1);
  const remainingBudget = safeNonNegNum(raw.remaining_budget_krw, -1);

  return {
    announced_units: announced,
    applied_units: applied,
    delivered_units: delivered,
    remaining_units: remaining,
    depletion_rate: depletionRate,
    delivery_rate: deliveryRate,
    status,
    ...(maxLocal >= 0
      ? { max_local_subsidy_krw: maxLocal }
      : fb.max_local_subsidy_krw !== undefined
      ? { max_local_subsidy_krw: fb.max_local_subsidy_krw }
      : {}),
    ...(maxTotal >= 0
      ? { max_total_subsidy_krw: maxTotal }
      : fb.max_total_subsidy_krw !== undefined
      ? { max_total_subsidy_krw: fb.max_total_subsidy_krw }
      : {}),
    ...(totalBudget >= 0 ? { total_budget_krw: totalBudget } : {}),
    ...(remainingBudget >= 0 ? { remaining_budget_krw: remainingBudget } : {}),
  };
}

function normalizeMunicipalityMetrics(raw: unknown): MunicipalityMetrics | null {
  if (!isPlainRecord(raw)) return null;
  const announced = safeNonNegNum(raw.announced_units, 0);
  const applied = safeNonNegNum(raw.applied_units, 0);
  const remaining = safeNonNegNum(raw.remaining_units, calculateRemainingUnits(applied, announced));
  const depletionRate = safeNonNegNum(raw.depletion_rate, calculateDepletionRate(applied, announced));
  const localSubsidy = safeNonNegNum(raw.local_subsidy_krw, 0);
  const delivered = safeNonNegNum(raw.delivered_units, -1);
  const totalSubsidy = safeNonNegNum(raw.total_subsidy_krw, -1);

  return {
    name_ko: safeNonEmptyStr(raw.name_ko, safeNonEmptyStr(raw.name_en, '미상 지자체')),
    announced_units: announced,
    applied_units: applied,
    remaining_units: remaining,
    depletion_rate: depletionRate,
    status: resolveAlertSeverity(raw.status, depletionRate),
    local_subsidy_krw: localSubsidy,
    ...(typeof raw.muni_id === 'string' && raw.muni_id.trim() ? { muni_id: raw.muni_id.trim() } : {}),
    ...(typeof raw.name_en === 'string' && raw.name_en.trim() ? { name_en: raw.name_en.trim() } : {}),
    ...(typeof raw.category === 'string' && raw.category.trim() ? { category: raw.category.trim() } : {}),
    ...(delivered >= 0 ? { delivered_units: delivered } : {}),
    ...(totalSubsidy >= 0 ? { total_subsidy_krw: totalSubsidy } : {}),
  };
}

function normalizeRegionEntry(raw: unknown): RegionEntry | null {
  if (!isPlainRecord(raw)) return null;
  const rawCats = isPlainRecord(raw.categories) ? raw.categories : {};
  const fbCats = DEFAULT_NATIONWIDE_SUMMARY.category_totals;
  const passenger = normalizeCategoryMetricsObj(rawCats.passenger, fbCats.passenger);
  const commercial = normalizeCategoryMetricsObj(rawCats.commercial, fbCats.commercial);
  const bus = normalizeCategoryMetricsObj(rawCats.bus, fbCats.bus);

  const overallRate = safeNonNegNum(raw.overall_depletion_rate, passenger.depletion_rate);
  const regionId = safeNonEmptyStr(raw.region_id, safeNonEmptyStr(raw.iso_code, 'unknown-region'));
  const isoCode = safeNonEmptyStr(raw.iso_code, regionId);
  const nameKo = safeNonEmptyStr(raw.name_ko, safeNonEmptyStr(raw.name_en, '미상 지역'));
  const nameEn = safeNonEmptyStr(raw.name_en, nameKo);
  const tier: RegionTier =
    typeof raw.tier === 'string' && VALID_REGION_TIERS.has(raw.tier as RegionTier)
      ? (raw.tier as RegionTier)
      : 'province';

  let municipalities: MunicipalityMetrics[] | undefined;
  if (Array.isArray(raw.municipalities)) {
    municipalities = [];
    for (let i = 0; i < raw.municipalities.length; i++) {
      const m = normalizeMunicipalityMetrics(raw.municipalities[i]);
      if (m) municipalities.push(m);
    }
  }

  return {
    region_id: regionId,
    iso_code: isoCode,
    ...(typeof raw.code === 'string' && raw.code.trim() ? { code: raw.code.trim() } : {}),
    name_ko: nameKo,
    name_en: nameEn,
    tier,
    overall_depletion_rate: overallRate,
    overall_status: resolveAlertSeverity(raw.overall_status, overallRate),
    residency_requirement_days: safeNonNegNum(raw.residency_requirement_days, 30),
    supplementary_budget_added: typeof raw.supplementary_budget_added === 'boolean' ? raw.supplementary_budget_added : false,
    categories: { passenger, commercial, bus },
    ...(municipalities ? { municipalities } : {}),
    ...(typeof raw.notes === 'string' ? { notes: raw.notes } : {}),
    ...(typeof raw.last_updated === 'string' && raw.last_updated.trim() ? { last_updated: raw.last_updated.trim() } : {}),
  };
}

function normalizePopularModelEntry(raw: unknown): PopularModelEntry | null {
  if (!isPlainRecord(raw)) return null;
  const rawNumPrice = safeNonNegNum(raw.base_price_krw, 0);
  const parsedPrice = rawNumPrice > 0
    ? rawNumPrice
    : parseSubsidyNumber(raw.base_price_krw, { defaultKrw: 0 });
  const basePrice = parsedPrice > 0 ? parsedPrice : 54_100_000;
  const rawRatio = raw.price_subsidy_ratio;
  const ratio =
    typeof rawRatio === 'number' && Number.isFinite(rawRatio) && rawRatio >= 0
      ? Math.min(1.0, rawRatio === 0 ? 0 : rawRatio)
      : getPriceSubsidyRatio(basePrice);

  let samples: PopularModelEntry['regional_subsidy_samples'];
  if (isPlainRecord(raw.regional_subsidy_samples)) {
    const cleanSamples: NonNullable<PopularModelEntry['regional_subsidy_samples']> = {};
    for (const key of Object.keys(raw.regional_subsidy_samples)) {
      if (FORBIDDEN_PROTO_KEYS.has(key)) continue;
      const sample = raw.regional_subsidy_samples[key];
      if (!isPlainRecord(sample)) continue;
      const localSub = safeNonNegNum(sample.local_subsidy_krw, -1);
      cleanSamples[key] = {
        ...(localSub >= 0 ? { local_subsidy_krw: localSub } : {}),
        total_subsidy_krw: safeNonNegNum(sample.total_subsidy_krw, 0),
        net_price_krw: safeNonNegNum(sample.net_price_krw, 0),
      };
    }
    samples = cleanSamples;
  }

  return {
    model_id: safeNonEmptyStr(raw.model_id, 'unknown-model'),
    name_ko: safeNonEmptyStr(raw.name_ko, '기본 모델'),
    manufacturer: safeNonEmptyStr(raw.manufacturer, '기타'),
    ...(typeof raw.manufacturer_ko === 'string' && raw.manufacturer_ko.trim()
      ? { manufacturer_ko: raw.manufacturer_ko.trim() }
      : {}),
    battery_type: safeNonEmptyStr(raw.battery_type, 'NCM 삼원계'),
    battery_capacity_kwh: safeNonNegNum(raw.battery_capacity_kwh, 0),
    rated_range_km: safeNonNegNum(raw.rated_range_km, 0),
    base_price_krw: basePrice,
    price_subsidy_ratio: ratio,
    national_subsidy_krw: safeNonNegNum(raw.national_subsidy_krw, 0),
    ...(samples ? { regional_subsidy_samples: samples } : {}),
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

  const regions: RegionEntry[] = [];
  for (let i = 0; i < data.regions.length; i++) {
    const normalizedRegion = normalizeRegionEntry(data.regions[i]);
    if (normalizedRegion) regions.push(normalizedRegion);
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
      ? rawMeta.data_sources
          .filter((s): s is string => typeof s === 'string' && s.trim().length > 0)
          .map((s) => s.trim())
      : [...fbMeta.data_sources],
    total_regions_tracked: safeNonNegNum(rawMeta.total_regions_tracked, regions.length),
    total_municipalities_tracked: safeNonNegNum(
      rawMeta.total_municipalities_tracked,
      0
    ),
    currency: safeNonEmptyStr(rawMeta.currency, fbMeta.currency),
  };
  if (metadata.data_sources.length === 0) {
    metadata.data_sources = [...fbMeta.data_sources];
  }

  const rawThresholds = isPlainRecord(data.alert_thresholds) ? data.alert_thresholds : {};
  const alertThresholds = {} as Record<AlertSeverity, AlertThresholdConfig>;
  for (const sev of ALERT_SEVERITIES) {
    const fbCfg = DEFAULT_SUBSIDY_THRESHOLDS[sev];
    const rawCfg = Object.prototype.hasOwnProperty.call(rawThresholds, sev) && isPlainRecord(rawThresholds[sev])
      ? (rawThresholds[sev] as Record<string, unknown>)
      : {};
    alertThresholds[sev] = {
      min_percent: typeof rawCfg.min_percent === 'number' && Number.isFinite(rawCfg.min_percent) ? (rawCfg.min_percent === 0 ? 0 : rawCfg.min_percent) : fbCfg.min_percent,
      max_percent: typeof rawCfg.max_percent === 'number' && Number.isFinite(rawCfg.max_percent) ? (rawCfg.max_percent === 0 ? 0 : rawCfg.max_percent) : fbCfg.max_percent,
      label_ko: safeNonEmptyStr(rawCfg.label_ko, fbCfg.label_ko),
      severity: sev,
      color_hex: safeNonEmptyStr(rawCfg.color_hex, fbCfg.color_hex),
      badge_class: safeNonEmptyStr(rawCfg.badge_class, fbCfg.badge_class),
      recommended_action: safeNonEmptyStr(rawCfg.recommended_action, fbCfg.recommended_action),
    };
  }

  const rawSummary = isPlainRecord(data.nationwide_summary) ? data.nationwide_summary : {};
  const zeroSummary = DEFAULT_NATIONWIDE_SUMMARY;
  const rawCatTotals = isPlainRecord(rawSummary.category_totals) ? rawSummary.category_totals : {};
  const rawAlertCounts = isPlainRecord(rawSummary.alert_region_counts) ? rawSummary.alert_region_counts : {};

  const totalBudgetKrw = safeNonNegNum(rawSummary.total_budget_krw, -1);
  const disbursedBudgetKrw = safeNonNegNum(rawSummary.disbursed_budget_krw, -1);
  const totalAnnouncedUnits = safeNonNegNum(rawSummary.total_announced_units, zeroSummary.total_announced_units);
  const totalAppliedUnits = safeNonNegNum(rawSummary.total_applied_units, zeroSummary.total_applied_units);
  const totalDeliveredUnits = safeNonNegNum(rawSummary.total_delivered_units, zeroSummary.total_delivered_units);

  const nationwideSummary: EVSubsidyDataset['nationwide_summary'] = {
    total_announced_units: totalAnnouncedUnits,
    total_applied_units: totalAppliedUnits,
    total_delivered_units: totalDeliveredUnits,
    total_remaining_units: safeNonNegNum(
      rawSummary.total_remaining_units,
      calculateRemainingUnits(totalAppliedUnits, totalAnnouncedUnits)
    ),
    nationwide_depletion_rate: safeNonNegNum(
      rawSummary.nationwide_depletion_rate,
      calculateDepletionRate(totalAppliedUnits, totalAnnouncedUnits)
    ),
    total_budget_billion_krw: safeNonNegNum(
      rawSummary.total_budget_billion_krw,
      zeroSummary.total_budget_billion_krw
    ),
    disbursed_budget_billion_krw: safeNonNegNum(
      rawSummary.disbursed_budget_billion_krw,
      zeroSummary.disbursed_budget_billion_krw
    ),
    ...(totalBudgetKrw >= 0 ? { total_budget_krw: totalBudgetKrw } : {}),
    ...(disbursedBudgetKrw >= 0 ? { disbursed_budget_krw: disbursedBudgetKrw } : {}),
    category_totals: {
      passenger: normalizeCategoryMetricsObj(rawCatTotals.passenger, zeroSummary.category_totals.passenger),
      commercial: normalizeCategoryMetricsObj(rawCatTotals.commercial, zeroSummary.category_totals.commercial),
      bus: normalizeCategoryMetricsObj(rawCatTotals.bus, zeroSummary.category_totals.bus),
    },
    alert_region_counts: {
      healthy: safeNonNegNum(rawAlertCounts.healthy, zeroSummary.alert_region_counts.healthy),
      caution: safeNonNegNum(rawAlertCounts.caution, zeroSummary.alert_region_counts.caution),
      warning: safeNonNegNum(rawAlertCounts.warning, zeroSummary.alert_region_counts.warning),
      critical: safeNonNegNum(rawAlertCounts.critical, zeroSummary.alert_region_counts.critical),
      depleted: safeNonNegNum(rawAlertCounts.depleted, zeroSummary.alert_region_counts.depleted),
    },
  };

  const popularModels: PopularModelEntry[] = [];
  if (Array.isArray(data.popular_models_matrix)) {
    for (let i = 0; i < data.popular_models_matrix.length; i++) {
      const normalizedModel = normalizePopularModelEntry(data.popular_models_matrix[i]);
      if (normalizedModel) popularModels.push(normalizedModel);
    }
  }

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


const DEFAULT_CALCULATOR_MODEL: PopularModelEntry = Object.freeze({
  model_id: 'ioniq-5-2026',
  name_ko: '현대 아이오닉 5 롱레인지 2WD (2026)',
  manufacturer: '현대자동차',
  battery_type: 'NCM 삼원계 (84kWh)',
  battery_capacity_kwh: 84.0,
  rated_range_km: 485,
  base_price_krw: 54100000,
  price_subsidy_ratio: 1.0,
  national_subsidy_krw: 6500000,
});

const DEFAULT_CALCULATOR_REGION: RegionEntry = Object.freeze({
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
}) as RegionEntry;

function resolveFallbackModel(models: readonly PopularModelEntry[]): PopularModelEntry {
  for (let i = 0; i < models.length; i++) {
    if (isPlainRecord(models[i])) return models[i];
  }
  return DEFAULT_CALCULATOR_MODEL;
}

function resolveFallbackRegion(regions: readonly RegionEntry[]): RegionEntry {
  let firstValid: RegionEntry | undefined;
  for (let i = 0; i < regions.length; i++) {
    const r = regions[i];
    if (!isPlainRecord(r)) continue;
    if (r.region_id === 'KR-11') return r;
    if (!firstValid) firstValid = r;
  }
  return firstValid || DEFAULT_CALCULATOR_REGION;
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
  const model = getModelByIdFromList(models, modelId) || resolveFallbackModel(models);
  const region = getRegionByIdFromList(regions, regionId) || resolveFallbackRegion(regions);
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

  const safeAnnounced = Number.isFinite(announced) && announced > 0 ? announced : 0;
  const safeApplied = Number.isFinite(applied) && applied > 0 ? applied : 0;
  const safeRemaining = Number.isFinite(remaining) && remaining > 0 ? remaining : 0;
  const safeRate = Number.isFinite(rate) && rate > 0 ? rate : 0.0;

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

