/**
 * Pure calculation utilities, type definitions, and mathematical models for South Korea EV Subsidies.
 * Based on Ministry of Environment (환경부) & Korea Environment Corporation (KECO) 2026 Guidelines.
 *
 * This module has ZERO dependencies on heavy JSON data files, enabling client bundles
 * to remain lean without bundling redundant static data payloads.
 */

import {
  AlertSeverity,
  AlertThresholdConfig,
  CategoryMetrics,
  RegionEntry,
  PopularModelEntry,
  EVSubsidyDataset,
  SubsidyCalculationResult,
  SubsidyCalculatorOptions,
  MunicipalityMetrics,
} from '../types/subsidy';

export type {
  AlertSeverity,
  AlertThresholdConfig,
  CategoryMetrics,
  RegionEntry,
  PopularModelEntry,
  EVSubsidyDataset,
  SubsidyCalculationResult,
  SubsidyCalculatorOptions,
  MunicipalityMetrics,
};

// ==========================================
// 1. FROZEN DEFAULT FALLBACK CONSTANTS (Zero-GC)
// ==========================================

export const DEFAULT_SUBSIDY_THRESHOLDS: Readonly<Record<AlertSeverity, Readonly<AlertThresholdConfig>>> = Object.freeze({
  HEALTHY: Object.freeze({
    min_percent: 0.0,
    max_percent: 59.9,
    label_ko: '원활 (신청 여유)',
    severity: 'HEALTHY' as AlertSeverity,
    color_hex: '#10B981',
    badge_class: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    recommended_action: '보조금 잔여량이 충분하여 신청 접수 후 통상 1~2주 내 교부 결정됩니다.',
  }),
  CAUTION: Object.freeze({
    min_percent: 60.0,
    max_percent: 79.9,
    label_ko: '주의 (소진 가속)',
    severity: 'CAUTION' as AlertSeverity,
    color_hex: '#F59E0B',
    badge_class: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    recommended_action: '출고 예정 시기가 1~2개월 이내인 경우 조속한 서류 접수를 권장합니다.',
  }),
  WARNING: Object.freeze({
    min_percent: 80.0,
    max_percent: 94.9,
    label_ko: '경고 (마감 임박)',
    severity: 'WARNING' as AlertSeverity,
    color_hex: '#F97316',
    badge_class: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    recommended_action: '잔여 예산 소진이 임박했습니다. 즉시 출고 가능한 실재고 매칭이 필요합니다.',
  }),
  CRITICAL: Object.freeze({
    min_percent: 95.0,
    max_percent: 99.9,
    label_ko: '위험 (잔여 극소)',
    severity: 'CRITICAL' as AlertSeverity,
    color_hex: '#EF4444',
    badge_class: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    recommended_action: '선착순 마감 직전입니다. 담당 지자체 문의 및 추경 예산 편성 여부를 확인하세요.',
  }),
  DEPLETED: Object.freeze({
    min_percent: 100.0,
    max_percent: 999.0,
    label_ko: '마감 (접수 종료)',
    severity: 'DEPLETED' as AlertSeverity,
    color_hex: '#6B7280',
    badge_class: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
    recommended_action: '2026년 공고 예산이 전액 소진되었습니다. 취소분 대기 접수 또는 차년도 사업을 준비하세요.',
  }),
});

export const DEFAULT_NATIONWIDE_SUMMARY = Object.freeze({
  total_announced_units: 0,
  total_applied_units: 0,
  total_delivered_units: 0,
  total_remaining_units: 0,
  nationwide_depletion_rate: 0,
  total_budget_billion_krw: 0,
  disbursed_budget_billion_krw: 0,
  category_totals: Object.freeze({
    passenger: Object.freeze({
      announced_units: 0,
      applied_units: 0,
      delivered_units: 0,
      remaining_units: 0,
      depletion_rate: 0,
      delivery_rate: 0,
      status: 'HEALTHY' as AlertSeverity,
    }),
    commercial: Object.freeze({
      announced_units: 0,
      applied_units: 0,
      delivered_units: 0,
      remaining_units: 0,
      depletion_rate: 0,
      delivery_rate: 0,
      status: 'HEALTHY' as AlertSeverity,
    }),
    bus: Object.freeze({
      announced_units: 0,
      applied_units: 0,
      delivered_units: 0,
      remaining_units: 0,
      depletion_rate: 0,
      delivery_rate: 0,
      status: 'HEALTHY' as AlertSeverity,
    }),
  }),
  alert_region_counts: Object.freeze({
    healthy: 0,
    caution: 0,
    warning: 0,
    critical: 0,
    depleted: 0,
  }),
});

export const DEFAULT_FALLBACK_DATASET: EVSubsidyDataset = Object.freeze({
  metadata: Object.freeze({
    version: '1.0.0',
    generated_at: '2026-01-01T00:00:00.000Z',
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
  alert_thresholds: DEFAULT_SUBSIDY_THRESHOLDS as unknown as Record<AlertSeverity, AlertThresholdConfig>,
  nationwide_summary: DEFAULT_NATIONWIDE_SUMMARY as unknown as EVSubsidyDataset['nationwide_summary'],
  regions: Object.freeze([]) as unknown as RegionEntry[],
  popular_models_matrix: Object.freeze([]) as unknown as PopularModelEntry[],
}) as unknown as EVSubsidyDataset;

// ==========================================
// 2. CANONICAL REGION ALIAS MAP
// ==========================================

export const REGION_ALIAS_MAP: Readonly<Record<string, string>> = Object.freeze({
  // Special City / Metropolitan Cities
  '서울': 'KR-11',
  '서울특별시': 'KR-11',
  'seoul': 'KR-11',
  '부산': 'KR-26',
  '부산광역시': 'KR-26',
  'busan': 'KR-26',
  '대구': 'KR-27',
  '대구광역시': 'KR-27',
  'daegu': 'KR-27',
  '인천': 'KR-28',
  '인천광역시': 'KR-28',
  'incheon': 'KR-28',
  '광주': 'KR-29',
  '광주광역시': 'KR-29',
  'gwangju': 'KR-29',
  '대전': 'KR-30',
  '대전광역시': 'KR-30',
  'daejeon': 'KR-30',
  '울산': 'KR-31',
  '울산광역시': 'KR-31',
  'ulsan': 'KR-31',
  // Special Self-Governing City (CleanSys KR-36 and ISO KR-50)
  '세종': 'KR-36',
  '세종특별자치시': 'KR-36',
  'sejong': 'KR-36',
  'kr-50': 'KR-36',
  'kr-36': 'KR-36',
  // Provinces
  '경기': 'KR-41',
  '경기도': 'KR-41',
  'gyeonggi': 'KR-41',
  '강원': 'KR-42',
  '강원도': 'KR-42',
  '강원특별자치도': 'KR-42',
  'gangwon': 'KR-42',
  '충북': 'KR-43',
  '충청북도': 'KR-43',
  'chungbuk': 'KR-43',
  '충남': 'KR-44',
  '충청남도': 'KR-44',
  'chungnam': 'KR-44',
  '전북': 'KR-45',
  '전라북도': 'KR-45',
  '전북특별자치도': 'KR-45',
  'jeonbuk': 'KR-45',
  '전남': 'KR-46',
  '전라남도': 'KR-46',
  'jeonnam': 'KR-46',
  '경북': 'KR-47',
  '경상북도': 'KR-47',
  'gyeongbuk': 'KR-47',
  '경남': 'KR-48',
  '경상남도': 'KR-48',
  'gyeongnam': 'KR-48',
  '제주': 'KR-49',
  '제주도': 'KR-49',
  '제주특별자치도': 'KR-49',
  'jeju': 'KR-49',
});

// ==========================================
// 3. STATUTORY PRICE-CAP FORMULA
// ==========================================

/**
 * Calculates national subsidy multiplier based on 2026 MOE statutory price caps:
 * - MSRP <= 55,000,000 KRW: 1.0 (100% eligibility)
 * - 55,000,000 < MSRP <= 85,000,000 KRW: 0.5 (50% eligibility)
 * - MSRP > 85,000,000 KRW or invalid/negative: 0.0 (luxury vehicle exclusion)
 */
export function getPriceSubsidyRatio(msrpKrw: number): number {
  if (!Number.isFinite(msrpKrw) || msrpKrw < 0 || msrpKrw === Infinity) {
    return 0.0;
  }
  if (msrpKrw <= 55_000_000) {
    return 1.0;
  }
  if (msrpKrw <= 85_000_000) {
    return 0.5;
  }
  return 0.0;
}

// ==========================================
// 4. PURE LIST LOOKUP FUNCTIONS
// ==========================================

/**
 * Pure region resolver from a supplied array of regions.
 * Matches by region_id, iso_code, Korean name, English name, canonical alias,
 * or stripped administrative suffix.
 */
export function getRegionByIdFromList(
  regions: readonly RegionEntry[] | undefined,
  regionId: string
): RegionEntry | undefined {
  if (!regionId || typeof regionId !== 'string' || !Array.isArray(regions)) return undefined;
  const normalized = regionId.trim().toLowerCase();
  if (!normalized) return undefined;

  // 1. Direct alias resolution
  const rawAlias = Object.prototype.hasOwnProperty.call(REGION_ALIAS_MAP, normalized)
    ? REGION_ALIAS_MAP[normalized]
    : Object.prototype.hasOwnProperty.call(REGION_ALIAS_MAP, regionId.trim())
    ? REGION_ALIAS_MAP[regionId.trim()]
    : undefined;
  const aliasedId = typeof rawAlias === 'string' ? rawAlias : undefined;
  if (aliasedId) {
    const matched = regions.find(
      (r) =>
        r.region_id.toLowerCase() === aliasedId.toLowerCase() ||
        r.iso_code.toLowerCase() === aliasedId.toLowerCase()
    );
    if (matched) return matched;
  }

  // 2. Direct exact match on ID, ISO code, or localized names
  const exact = regions.find(
    (r) =>
      r.region_id.toLowerCase() === normalized ||
      r.iso_code.toLowerCase() === normalized ||
      r.name_ko.toLowerCase() === normalized ||
      r.name_en.toLowerCase() === normalized
  );
  if (exact) return exact;

  // 3. 2-letter provincial abbreviation / stripped administrative suffix match
  const stripped = normalized.replace(/(특별시|광역시|특별자치시|특별자치도|도)$/, '');
  if (stripped) {
    const rawStrippedAlias = Object.prototype.hasOwnProperty.call(REGION_ALIAS_MAP, stripped)
      ? REGION_ALIAS_MAP[stripped]
      : undefined;
    const strippedAliasedId = typeof rawStrippedAlias === 'string' ? rawStrippedAlias : undefined;
    if (strippedAliasedId) {
      const matched = regions.find(
        (r) =>
          r.region_id.toLowerCase() === strippedAliasedId.toLowerCase() ||
          r.iso_code.toLowerCase() === strippedAliasedId.toLowerCase()
      );
      if (matched) return matched;
    }

    return regions.find((r) => {
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
 * Pure model resolver from a supplied array of popular models.
 * Supports whitespace-, hyphen-, and punctuation-normalized queries.
 */
export function getModelByIdFromList(
  models: readonly PopularModelEntry[] | undefined,
  modelId: string
): PopularModelEntry | undefined {
  if (!modelId || typeof modelId !== 'string' || !Array.isArray(models)) return undefined;
  const normalized = modelId.trim().toLowerCase();
  if (!normalized) return undefined;

  // 1. Exact or substring match on raw string
  const directMatch = models.find(
    (m) =>
      m.model_id.toLowerCase() === normalized ||
      m.name_ko.toLowerCase() === normalized ||
      m.name_ko.toLowerCase().includes(normalized)
  );
  if (directMatch) return directMatch;

  // 2. Normalize by stripping whitespace, hyphens, and punctuation
  const cleanQuery = normalized.replace(/[\s\-_]+/g, '');
  if (!cleanQuery) return undefined;

  return models.find((m) => {
    const cleanId = m.model_id.toLowerCase().replace(/[\s\-_]+/g, '');
    const cleanKo = m.name_ko.toLowerCase().replace(/[\s\-_]+/g, '');
    return cleanId.includes(cleanQuery) || cleanKo.includes(cleanQuery);
  });
}

// ==========================================
// 5. PURE SUBSIDY CALCULATION ENGINE
// ==========================================

/**
 * Computes net subsidy, matching municipal grant, statutory price cap reduction,
 * and out-of-pocket net vehicle purchase price from model and region parameters.
 */
export function calculateNetSubsidyPure(
  model: PopularModelEntry,
  region: RegionEntry,
  customMsrp?: number,
  options?: SubsidyCalculatorOptions
): SubsidyCalculationResult {
  const passengerCategory = region.categories?.passenger;

  // 1. Resolve MSRP and statutory price-cap ratio
  const safeModelPrice =
    Number.isFinite(model?.base_price_krw) && model.base_price_krw > 0
      ? Math.min(10_000_000_000, model.base_price_krw)
      : 54_100_000;

  let activeMsrp: number;
  if (customMsrp === Infinity) {
    activeMsrp = 10_000_000_000;
  } else if (customMsrp !== undefined && customMsrp !== null && Number.isFinite(customMsrp) && customMsrp > 0) {
    activeMsrp = Math.min(10_000_000_000, customMsrp);
  } else {
    activeMsrp = safeModelPrice;
  }

  const ratio = getPriceSubsidyRatio(activeMsrp);

  let priceCapTierText = '100% 전액 지원 (5,500만 원 이하)';
  if (ratio === 0.5) {
    priceCapTierText = '50% 감액 지원 (5,500만~8,500만 원 구간)';
  } else if (ratio === 0.0) {
    priceCapTierText = '보조금 지급 대상 제외 (8,500만 원 초과)';
  }

  // 2. Calculate National Subsidy
  const validNationalSubsidy = Number.isFinite(model.national_subsidy_krw)
    ? model.national_subsidy_krw
    : 0;
  let nationalSubsidyKrw = 0;
  if (ratio > 0) {
    if (customMsrp && customMsrp > 0 && Number.isFinite(customMsrp)) {
      const baseRatio = model.price_subsidy_ratio > 0 ? model.price_subsidy_ratio : 1.0;
      const unscaledNational = Math.round(validNationalSubsidy / baseRatio);
      nationalSubsidyKrw = Math.min(6_500_000, Math.round(unscaledNational * ratio));
    } else {
      nationalSubsidyKrw = validNationalSubsidy;
    }
  }

  // 3. Additional Grants / Subsidies
  let additionalGrantsKrw = 0;
  if (nationalSubsidyKrw > 0 && options) {
    if (options.isYouthFirstTimeBuyer) {
      additionalGrantsKrw += Math.round(nationalSubsidyKrw * 0.2);
    }
    if (options.isSmallBusinessOrTaxi) {
      additionalGrantsKrw += Math.round(nationalSubsidyKrw * 0.3);
    }
    if (options.isMultiChildFamily) {
      additionalGrantsKrw += Math.round(nationalSubsidyKrw * 0.1);
    }
    if (options.isOldDieselScrappage) {
      additionalGrantsKrw += 1_000_000;
    }
  }

  // 4. Calculate Local Municipal Matching Subsidy
  // Formula: S_local = S_local_max * (S_nat / 6,500,000)
  const maxLocal = Number.isFinite(passengerCategory?.max_local_subsidy_krw)
    ? passengerCategory!.max_local_subsidy_krw!
    : 0;
  let localSubsidyKrw = 0;
  if (nationalSubsidyKrw > 0 && maxLocal > 0) {
    const calculated = Math.round(maxLocal * (nationalSubsidyKrw / 6_500_000));
    localSubsidyKrw = Math.min(maxLocal, Math.round(calculated / 10_000) * 10_000);
  }

  // 5. Total & Net Out-of-pocket Purchase Price
  const totalSubsidyKrw = nationalSubsidyKrw + localSubsidyKrw + additionalGrantsKrw;
  const rawNetPrice = activeMsrp - totalSubsidyKrw;
  const netPurchasePriceKrw = Number.isFinite(rawNetPrice) ? Math.max(0, rawNetPrice) : 0;

  // 6. Depletion Risk & Warning Analysis
  const depletionRate = Number.isFinite(passengerCategory?.depletion_rate)
    ? passengerCategory!.depletion_rate
    : 0;
  const isHighDepletionRisk = depletionRate >= 80.0;
  const depletionStatus: AlertSeverity = passengerCategory?.status || 'HEALTHY';
  const remainingUnits = Number.isFinite(passengerCategory?.remaining_units)
    ? passengerCategory!.remaining_units
    : 0;

  let warningNotice: string | undefined;
  if (depletionRate >= 95.0) {
    warningNotice = `🚨 ${region.name_ko}의 승용 보조금 소진율이 ${depletionRate}%로 선착순 마감 직전입니다! 즉시 출고 가능 실재고 매칭이 필요합니다.`;
  } else if (depletionRate >= 80.0) {
    warningNotice = `⚠️ ${region.name_ko}의 승용 보조금 소진율이 ${depletionRate}%에 달해 조기 마감 위험이 높습니다.`;
  } else {
    warningNotice = `✅ ${region.name_ko}의 보조금 잔여량이 비교적 여유롭습니다 (${remainingUnits.toLocaleString()}대 잔여).`;
  }

  return {
    modelId: model.model_id,
    modelName: model.name_ko,
    manufacturer: model.manufacturer,
    batteryType: model.battery_type,
    batteryCapacityKwh: model.battery_capacity_kwh,
    ratedRangeKm: model.rated_range_km,
    regionId: region.region_id,
    regionName: region.name_ko,
    msrpKrw: activeMsrp,
    priceSubsidyRatio: ratio,
    nationalSubsidyKrw,
    localSubsidyKrw,
    additionalGrantsKrw,
    totalSubsidyKrw,
    netPurchasePriceKrw,
    isHighDepletionRisk,
    depletionRate,
    depletionStatus,
    residencyRequirementDays: region.residency_requirement_days,
    warningNotice,
    priceCapTierText,
  };
}

// ==========================================
// 6. STATISTICAL AGGREGATION UTILITIES
// ==========================================

export interface SubsidyStatistics {
  totalAnnouncedUnits: number;
  totalAppliedUnits: number;
  totalDeliveredUnits: number;
  totalRemainingUnits: number;
  nationalDepletionRate: number;
  deliveryRate: number;
  budgetTotalBillionKrw: number;
  budgetDisbursedBillionKrw: number;
  budgetExecutionRatePct: number;
  criticalRegionsCount: number;
  criticalRegions: Array<{ regionId: string; nameKo: string; depletionRate: number; remainingUnits: number }>;
  warningRegionsCount: number;
  cautionRegionsCount: number;
  healthyRegionsCount: number;
  categoryBreakdown: {
    passenger: { announced: number; applied: number; remaining: number; rate: number };
    commercial: { announced: number; applied: number; remaining: number; rate: number };
    bus: { announced: number; applied: number; remaining: number; rate: number };
  };
}

/**
 * Pure calculation of nationwide subsidy statistics from an EVSubsidyDataset.
 */
export function calculateSubsidyStatistics(dataset?: Partial<EVSubsidyDataset> | null): SubsidyStatistics {
  const summary = dataset?.nationwide_summary;
  const regions = Array.isArray(dataset?.regions) ? dataset!.regions : [];

  const announced = Number.isFinite(summary?.total_announced_units) ? summary!.total_announced_units : 0;
  const applied = Number.isFinite(summary?.total_applied_units) ? summary!.total_applied_units : 0;
  const delivered = Number.isFinite(summary?.total_delivered_units) ? summary!.total_delivered_units : 0;
  const remaining = Number.isFinite(summary?.total_remaining_units) ? summary!.total_remaining_units : 0;

  const depletionRate = announced > 0
    ? Number.isFinite(summary?.nationwide_depletion_rate)
      ? summary!.nationwide_depletion_rate
      : Math.round((applied / announced) * 1000) / 10
    : 0;

  const deliveryRate = announced > 0
    ? Math.round((delivered / announced) * 1000) / 10
    : 0;

  const budgetTotal = Number.isFinite(summary?.total_budget_billion_krw) ? summary!.total_budget_billion_krw : 0;
  const budgetDisbursed = Number.isFinite(summary?.disbursed_budget_billion_krw) ? summary!.disbursed_budget_billion_krw : 0;
  const budgetExecutionRatePct = budgetTotal > 0
    ? Math.round((budgetDisbursed / budgetTotal) * 1000) / 10
    : 0;

  // Extract regions >= 95%
  const criticalList: Array<{ regionId: string; nameKo: string; depletionRate: number; remainingUnits: number }> = [];
  let criticalCount = 0;
  let warningCount = 0;
  let cautionCount = 0;
  let healthyCount = 0;

  for (const r of regions) {
    const rate = Number.isFinite(r.overall_depletion_rate) ? r.overall_depletion_rate : 0;
    const rem = Number.isFinite(r.categories?.passenger?.remaining_units) ? r.categories.passenger.remaining_units : 0;
    if (rate >= 95.0) {
      criticalCount++;
      criticalList.push({
        regionId: r.region_id,
        nameKo: r.name_ko,
        depletionRate: rate,
        remainingUnits: rem,
      });
    } else if (rate >= 80.0) {
      warningCount++;
    } else if (rate >= 60.0) {
      cautionCount++;
    } else {
      healthyCount++;
    }
  }

  // Sort critical regions descending by depletion rate
  criticalList.sort((a, b) => b.depletionRate - a.depletionRate);

  const cat = summary?.category_totals;

  return {
    totalAnnouncedUnits: announced,
    totalAppliedUnits: applied,
    totalDeliveredUnits: delivered,
    totalRemainingUnits: remaining,
    nationalDepletionRate: depletionRate,
    deliveryRate,
    budgetTotalBillionKrw: budgetTotal,
    budgetDisbursedBillionKrw: budgetDisbursed,
    budgetExecutionRatePct,
    criticalRegionsCount: criticalCount,
    criticalRegions: criticalList,
    warningRegionsCount: warningCount,
    cautionRegionsCount: cautionCount,
    healthyRegionsCount: healthyCount,
    categoryBreakdown: {
      passenger: {
        announced: cat?.passenger?.announced_units ?? 0,
        applied: cat?.passenger?.applied_units ?? 0,
        remaining: cat?.passenger?.remaining_units ?? 0,
        rate: cat?.passenger?.depletion_rate ?? 0,
      },
      commercial: {
        announced: cat?.commercial?.announced_units ?? 0,
        applied: cat?.commercial?.applied_units ?? 0,
        remaining: cat?.commercial?.remaining_units ?? 0,
        rate: cat?.commercial?.depletion_rate ?? 0,
      },
      bus: {
        announced: cat?.bus?.announced_units ?? 0,
        applied: cat?.bus?.applied_units ?? 0,
        remaining: cat?.bus?.remaining_units ?? 0,
        rate: cat?.bus?.depletion_rate ?? 0,
      },
    },
  };
}

// ==========================================
// 7. FORMATTING & PRESENTATION HELPERS
// ==========================================

export function formatCurrencyKrw(krw: number): string {
  if (!Number.isFinite(krw) || krw <= 0) return '0원';
  return `${Math.round(krw).toLocaleString()}원`;
}

export function formatManwon(krw: number): string {
  if (!Number.isFinite(krw) || krw <= 0) return '0만 원';
  const manwon = Math.round(krw / 10_000);
  return `${manwon.toLocaleString()}만 원`;
}

export function formatBillionKrw(billion: number): string {
  if (!Number.isFinite(billion) || billion <= 0) return '0억 원';
  return `${billion.toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })}억 원`;
}

export function formatDepletionRate(rate: number): string {
  if (!Number.isFinite(rate)) return '0.0%';
  return `${rate.toFixed(1)}%`;
}

export function getDepletionBadgeStyle(rate: number): {
  severity: AlertSeverity;
  colorHex: string;
  badgeClass: string;
  labelKo: string;
} {
  if (rate >= 100.0) {
    return {
      severity: 'DEPLETED',
      colorHex: '#6B7280',
      badgeClass: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
      labelKo: '마감 (접수 종료)',
    };
  }
  if (rate >= 95.0) {
    return {
      severity: 'CRITICAL',
      colorHex: '#EF4444',
      badgeClass: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
      labelKo: '위험 (잔여 극소)',
    };
  }
  if (rate >= 80.0) {
    return {
      severity: 'WARNING',
      colorHex: '#F97316',
      badgeClass: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
      labelKo: '경고 (마감 임박)',
    };
  }
  if (rate >= 60.0) {
    return {
      severity: 'CAUTION',
      colorHex: '#F59E0B',
      badgeClass: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      labelKo: '주의 (소진 가속)',
    };
  }
  return {
    severity: 'HEALTHY',
    colorHex: '#10B981',
    badgeClass: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    labelKo: '원활 (신청 여유)',
  };
}
