import rawData from '../data/ev_subsidy_data.json';
import {
  EVSubsidyDataset,
  PopularModelEntry,
  RegionEntry,
  SubsidyCalculationResult,
  SubsidyCalculatorOptions,
  AlertSeverity,
} from '../types/subsidy';

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
      badge_class: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
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
    if (rawData && typeof rawData === 'object' && 'regions' in rawData) {
      return rawData as unknown as EVSubsidyDataset;
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
  return db.regions || [];
}

/**
 * Finds a specific region by region_id, iso_code, or Korean name.
 */
export function getRegionById(regionId: string): RegionEntry | undefined {
  const regions = getAllRegions();
  const normalized = regionId.trim().toLowerCase();
  return regions.find(
    (r) =>
      r.region_id.toLowerCase() === normalized ||
      r.iso_code.toLowerCase() === normalized ||
      r.name_ko.toLowerCase() === normalized ||
      r.name_en.toLowerCase() === normalized
  );
}

/**
 * Returns all popular vehicle models in the matrix.
 */
export function getAllModels(): PopularModelEntry[] {
  const db = getSubsidyDatabase();
  return db.popular_models_matrix || [];
}

/**
 * Finds a vehicle model by model_id or Korean name.
 */
export function getModelById(modelId: string): PopularModelEntry | undefined {
  const models = getAllModels();
  const normalized = modelId.trim().toLowerCase();
  return models.find(
    (m) =>
      m.model_id.toLowerCase() === normalized ||
      m.name_ko.toLowerCase().includes(normalized)
  );
}

/**
 * Calculates national subsidy multiplier based on 2026 MOE statutory price caps:
 * - MSRP < 55,000,000 KRW: 1.0 (100% eligibility)
 * - 55,000,000 <= MSRP < 85,000,000 KRW: 0.5 (50% eligibility)
 * - MSRP >= 85,000,000 KRW: 0.0 (0% luxury vehicle exclusion)
 */
export function getPriceSubsidyRatio(msrpKrw: number): number {
  if (!Number.isFinite(msrpKrw) || msrpKrw < 0) {
    return 1.0;
  }
  if (msrpKrw >= 85_000_000) {
    return 0.0;
  }
  if (msrpKrw >= 55_000_000) {
    return 0.5;
  }
  return 1.0;
}

/**
 * Calculates the comprehensive net subsidy and out-of-pocket purchase price
 * for a chosen vehicle model in a designated administrative region.
 */
export function calculateNetSubsidy(
  modelId: string,
  regionId: string,
  customMsrp?: number,
  options?: SubsidyCalculatorOptions
): SubsidyCalculationResult {
  const models = getAllModels();
  const regions = getAllRegions();

  // 1. Resolve vehicle model
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

  const model = getModelById(modelId) || defaultModel;

  // 2. Resolve region
  const defaultRegion: RegionEntry = regions[0] || {
    region_id: 'KR-11',
    iso_code: 'KR-11',
    name_ko: '서울특별시',
    name_en: 'Seoul',
    tier: 'special_city',
    overall_depletion_rate: 87.8,
    overall_status: 'WARNING',
    residency_requirement_days: 30,
    supplementary_budget_added: false,
    categories: {
      passenger: {
        announced_units: 11500,
        applied_units: 9890,
        delivered_units: 8900,
        remaining_units: 1610,
        depletion_rate: 86.0,
        delivery_rate: 77.4,
        status: 'WARNING',
        max_local_subsidy_krw: 1500000,
        max_total_subsidy_krw: 8000000,
      },
      commercial: {
        announced_units: 2800,
        applied_units: 2660,
        delivered_units: 2450,
        remaining_units: 140,
        depletion_rate: 95.0,
        delivery_rate: 87.5,
        status: 'CRITICAL',
        max_local_subsidy_krw: 4000000,
        max_total_subsidy_krw: 14500000,
      },
      bus: {
        announced_units: 450,
        applied_units: 396,
        delivered_units: 360,
        remaining_units: 54,
        depletion_rate: 88.0,
        delivery_rate: 80.0,
        status: 'WARNING',
        max_local_subsidy_krw: 35000000,
        max_total_subsidy_krw: 105000000,
      },
    },
    notes: '서울시 보조금 잔여 소진 임박',
  };

  const region = getRegionById(regionId) || defaultRegion;

  // 3. Resolve MSRP and price cap ratio
  const activeMsrp = customMsrp && customMsrp > 0 ? customMsrp : model.base_price_krw;
  const ratio = getPriceSubsidyRatio(activeMsrp);

  let priceCapTierText = '100% 전액 지원 (5,500만 원 미만)';
  if (ratio === 0.5) {
    priceCapTierText = '50% 감액 지원 (5,500만~8,500만 원 구간)';
  } else if (ratio === 0.0) {
    priceCapTierText = '보조금 지급 대상 제외 (8,500만 원 이상)';
  }

  // 4. Calculate National Subsidy
  let nationalSubsidyKrw = 0;
  if (ratio > 0) {
    if (customMsrp && customMsrp > 0) {
      // Re-evaluate model un-scaled baseline
      const baseRatio = model.price_subsidy_ratio > 0 ? model.price_subsidy_ratio : 1.0;
      const unscaledNational = Math.round(model.national_subsidy_krw / baseRatio);
      nationalSubsidyKrw = Math.min(6_500_000, Math.round(unscaledNational * ratio));
    } else {
      nationalSubsidyKrw = model.national_subsidy_krw;
    }
  }

  // 5. Additional Grants / Subsidies
  let additionalGrantsKrw = 0;
  if (nationalSubsidyKrw > 0 && options) {
    if (options.isYouthFirstTimeBuyer) {
      // Youth 1st time buyer: +20% national subsidy
      additionalGrantsKrw += Math.round(nationalSubsidyKrw * 0.2);
    }
    if (options.isSmallBusinessOrTaxi) {
      // Small business / taxi: +30% national subsidy
      additionalGrantsKrw += Math.round(nationalSubsidyKrw * 0.3);
    }
    if (options.isMultiChildFamily) {
      // Multi-child family: +10% national subsidy
      additionalGrantsKrw += Math.round(nationalSubsidyKrw * 0.1);
    }
    if (options.isOldDieselScrappage) {
      // Scrappage bonus: flat 1,000,000 KRW
      additionalGrantsKrw += 1_000_000;
    }
  }

  // 6. Calculate Local Municipal Matching Subsidy
  // Formula: S_local = S_local_max * (S_nat / 6,500,000)
  const maxLocal = region.categories.passenger.max_local_subsidy_krw;
  let localSubsidyKrw = 0;
  if (nationalSubsidyKrw > 0) {
    localSubsidyKrw = Math.round(maxLocal * (nationalSubsidyKrw / 6_500_000));
    // Round to nearest 10,000 KRW
    localSubsidyKrw = Math.round(localSubsidyKrw / 10_000) * 10_000;
  }

  // 7. Calculate Combined Total & Out-of-pocket Net Price
  const totalSubsidyKrw = nationalSubsidyKrw + localSubsidyKrw + additionalGrantsKrw;
  const netPurchasePriceKrw = Math.max(0, activeMsrp - totalSubsidyKrw);

  // 8. Depletion Risk & Warning Analysis
  const depletionRate = region.categories.passenger.depletion_rate;
  const isHighDepletionRisk = depletionRate >= 80.0;
  const depletionStatus: AlertSeverity = region.categories.passenger.status;

  let warningNotice: string | undefined;
  if (depletionRate >= 95.0) {
    warningNotice = `🚨 ${region.name_ko}의 승용 보조금 소진율이 ${depletionRate}%로 선착순 마감 직전입니다! 즉시 출고 가능 실재고 매칭이 필요합니다.`;
  } else if (depletionRate >= 80.0) {
    warningNotice = `⚠️ ${region.name_ko}의 승용 보조금 소진율이 ${depletionRate}%에 달해 조기 마감 위험이 높습니다.`;
  } else {
    warningNotice = `✅ ${region.name_ko}의 보조금 잔여량이 비교적 여유롭습니다 (${region.categories.passenger.remaining_units.toLocaleString()}대 잔여).`;
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
