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
  type DepletionRateOptions,
  type ParseSubsidyNumberOptions,
  type ParsedModelSubsidy,
  type ParsedCategoryMetrics,
  type RegionSortOption,
  type ModelSortOption,
  type RankedRegionEntry,
} from './subsidyCalculations.ts';

export {
  calculateDepletionRate,
  calculateDeliveryRate,
  calculateRemainingUnits,
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
  type DepletionRateOptions,
  type ParseSubsidyNumberOptions,
  type ParsedModelSubsidy,
  type ParsedCategoryMetrics,
  type RegionSortOption,
  type ModelSortOption,
  type RankedRegionEntry,
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
        metadata: typed.metadata || fallbackDataset.metadata,
        alert_thresholds: typed.alert_thresholds || fallbackDataset.alert_thresholds,
        nationwide_summary: typed.nationwide_summary || fallbackDataset.nationwide_summary,
        regions: Array.isArray(typed.regions) ? typed.regions : fallbackDataset.regions,
        popular_models_matrix: Array.isArray(typed.popular_models_matrix)
          ? typed.popular_models_matrix
          : fallbackDataset.popular_models_matrix,
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
  if (!regionId || typeof regionId !== 'string') return undefined;
  const regions = getAllRegions();
  const normalized = regionId.trim().toLowerCase();
  if (!normalized) return undefined;

  const validRegions = regions.filter((r): r is RegionEntry => Boolean(r && typeof r === 'object'));

  // 1. Direct alias resolution
  const rawAlias = Object.prototype.hasOwnProperty.call(REGION_ALIAS_MAP, normalized)
    ? REGION_ALIAS_MAP[normalized]
    : Object.prototype.hasOwnProperty.call(REGION_ALIAS_MAP, regionId.trim())
    ? REGION_ALIAS_MAP[regionId.trim()]
    : undefined;
  const aliasedId = typeof rawAlias === 'string' ? rawAlias.toLowerCase() : undefined;
  if (aliasedId) {
    const matched = validRegions.find(
      (r) =>
        (typeof r.region_id === 'string' && r.region_id.toLowerCase() === aliasedId) ||
        (typeof r.iso_code === 'string' && r.iso_code.toLowerCase() === aliasedId)
    );
    if (matched) return matched;
  }

  // 2. Direct exact match on ID, ISO code, or localized names
  const exact = validRegions.find(
    (r) =>
      (typeof r.region_id === 'string' && r.region_id.toLowerCase() === normalized) ||
      (typeof r.iso_code === 'string' && r.iso_code.toLowerCase() === normalized) ||
      (typeof r.name_ko === 'string' && r.name_ko.toLowerCase() === normalized) ||
      (typeof r.name_en === 'string' && r.name_en.toLowerCase() === normalized)
  );
  if (exact) return exact;

  // 3. 2-letter provincial abbreviation / stripped administrative suffix match
  const stripped = normalized.replace(/(특별시|광역시|특별자치시|특별자치도|도)$/, '');
  if (stripped) {
    const rawStrippedAlias = Object.prototype.hasOwnProperty.call(REGION_ALIAS_MAP, stripped)
      ? REGION_ALIAS_MAP[stripped]
      : undefined;
    const strippedAliasedId = typeof rawStrippedAlias === 'string' ? rawStrippedAlias.toLowerCase() : undefined;
    if (strippedAliasedId) {
      const matched = validRegions.find(
        (r) =>
          (typeof r.region_id === 'string' && r.region_id.toLowerCase() === strippedAliasedId) ||
          (typeof r.iso_code === 'string' && r.iso_code.toLowerCase() === strippedAliasedId)
      );
      if (matched) return matched;
    }

    return validRegions.find((r) => {
      if (!r.name_ko || typeof r.name_ko !== 'string') return false;
      const rStripped = r.name_ko.toLowerCase().replace(/(특별시|광역시|특별자치시|특별자치도|도)$/, '');
      return (
        rStripped === stripped ||
        r.name_ko.toLowerCase().includes(stripped) ||
        stripped.includes(rStripped)
      );
    });
  }

  return undefined;
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
  if (!modelId || typeof modelId !== 'string') return undefined;
  const models = getAllModels();
  const normalized = modelId.trim().toLowerCase();
  if (!normalized) return undefined;

  const validModels = models.filter((m): m is PopularModelEntry => Boolean(m && typeof m === 'object'));

  // 1. Exact or substring match on raw string
  const directMatch = validModels.find(
    (m) =>
      (typeof m.model_id === 'string' && m.model_id.toLowerCase() === normalized) ||
      (typeof m.name_ko === 'string' && m.name_ko.toLowerCase() === normalized) ||
      (typeof m.name_ko === 'string' && m.name_ko.toLowerCase().includes(normalized))
  );
  if (directMatch) return directMatch;

  // 2. Normalize by stripping whitespace, hyphens, and punctuation
  const cleanQuery = normalized.replace(/[\s\-_]+/g, '');
  if (!cleanQuery) return undefined;

  return validModels.find((m) => {
    const cleanId = (typeof m.model_id === 'string' ? m.model_id : '').toLowerCase().replace(/[\s\-_]+/g, '');
    const cleanKo = (typeof m.name_ko === 'string' ? m.name_ko : '').toLowerCase().replace(/[\s\-_]+/g, '');
    return (cleanId && cleanId.includes(cleanQuery)) || (cleanKo && cleanKo.includes(cleanQuery));
  });
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
  const defaultModel: PopularModelEntry = models[0] || {
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
  const defaultRegion: RegionEntry = regions.find(r => r.region_id === 'KR-11') || regions[0] || {
    region_id: 'KR-11',
    name_ko: '서울특별시',
    residency_requirement_days: 30,
    announced_date: '2026-02-15',
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
    if ('categories' in regionOrId && regionOrId.categories) {
      region = regionOrId as RegionEntry;
    } else if ('region_id' in regionOrId && typeof regionOrId.region_id === 'string') {
      region = getRegionById(regionOrId.region_id);
    }
  }

  const category = region?.categories?.[categoryKey];
  const announced = parseSubsidyNumber(category?.announced_units, { defaultKrw: 0 });
  const applied = parseSubsidyNumber(category?.applied_units, { defaultKrw: 0 });
  const remaining = typeof category?.remaining_units === 'number' && Number.isFinite(category.remaining_units) && category.remaining_units >= 0
    ? category.remaining_units
    : calculateRemainingUnits(applied, announced);
  const rate = typeof category?.depletion_rate === 'number' && Number.isFinite(category.depletion_rate) && category.depletion_rate >= 0
    ? category.depletion_rate
    : calculateDepletionRate(applied, announced);
  const status: AlertSeverity = category?.status || (rate >= 100.0 ? 'DEPLETED' : rate >= 95.0 ? 'CRITICAL' : rate >= 80.0 ? 'WARNING' : rate >= 60.0 ? 'CAUTION' : 'HEALTHY');

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

