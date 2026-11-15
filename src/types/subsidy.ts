/**
 * South Korea EV Subsidy Domain Type Definitions
 * Based on Ministry of Environment (환경부) & Korea Environment Corporation (KECO) 2026 Guidelines.
 */

declare global {
  interface NumberConstructor {
    isFinite(number: unknown): number is number;
  }
}

export type AlertSeverity = 'HEALTHY' | 'CAUTION' | 'WARNING' | 'CRITICAL' | 'DEPLETED';

export type RegionTier =
  | 'special_city'
  | 'metropolitan_city'
  | 'special_self_governing_city'
  | 'province'
  | 'special_self_governing_province';

export type RegionSortOption =
  | 'DEPLETION_DESC'
  | 'DEPLETION_ASC'
  | 'REMAINING_ASC'
  | 'REMAINING_DESC'
  | 'LOCAL_SUBSIDY_DESC'
  | 'LOCAL_SUBSIDY_ASC'
  | 'NAME_ASC'
  | 'NAME_DESC'
  | 'depletion_desc'
  | 'depletion_asc'
  | 'remaining_asc'
  | 'remaining_desc'
  | 'local_subsidy_asc'
  | 'local_subsidy_desc'
  | 'name_asc'
  | 'name_desc';

export type ModelSortOption =
  | 'PRICE_ASC'
  | 'PRICE_DESC'
  | 'NET_PRICE_ASC'
  | 'NET_PRICE_DESC'
  | 'SUBSIDY_ASC'
  | 'SUBSIDY_DESC'
  | 'RANGE_ASC'
  | 'RANGE_DESC'
  | 'NAME_ASC'
  | 'NAME_DESC'
  | 'price_asc'
  | 'price_desc'
  | 'net_price_asc'
  | 'net_price_desc'
  | 'subsidy_asc'
  | 'subsidy_desc'
  | 'range_asc'
  | 'range_desc'
  | 'name_asc'
  | 'name_desc';

export interface AlertThresholdConfig {
  min_percent: number;
  max_percent: number;
  label_ko: string;
  severity: AlertSeverity;
  color_hex: string;
  badge_class: string;
  recommended_action: string;
}

export interface CategoryMetrics {
  announced_units: number;
  applied_units: number;
  delivered_units: number;
  remaining_units: number;
  depletion_rate: number;
  delivery_rate: number;
  status: AlertSeverity;
  max_local_subsidy_krw?: number;
  max_total_subsidy_krw?: number;
  total_budget_krw?: number;
  remaining_budget_krw?: number;
}

export interface MunicipalityMetrics {
  name_ko: string;
  announced_units: number;
  applied_units: number;
  remaining_units: number;
  depletion_rate: number;
  status: AlertSeverity;
  local_subsidy_krw: number;
  muni_id?: string;
  name_en?: string;
  category?: string;
  delivered_units?: number;
  total_subsidy_krw?: number;
}

export interface RegionEntry {
  region_id: string;
  iso_code: string;
  code?: string;
  name_ko: string;
  name_en: string;
  tier: RegionTier;
  overall_depletion_rate: number;
  overall_status: AlertSeverity;
  residency_requirement_days: number;
  supplementary_budget_added: boolean;
  categories: {
    passenger: CategoryMetrics;
    commercial: CategoryMetrics;
    bus: CategoryMetrics;
  };
  municipalities?: MunicipalityMetrics[];
  notes?: string;
  last_updated?: string;
}

export interface PopularModelEntry {
  model_id: string;
  name_ko: string;
  manufacturer: string;
  manufacturer_ko?: string;
  battery_type: string;
  battery_capacity_kwh: number;
  rated_range_km: number;
  base_price_krw: number;
  price_subsidy_ratio: number;
  national_subsidy_krw: number;
  regional_subsidy_samples?: Record<
    string,
    {
      local_subsidy_krw?: number;
      total_subsidy_krw: number;
      net_price_krw: number;
    }
  >;
}

export interface HistoricalTrajectoryPoint {
  date: string;
  passenger_rate: number;
  commercial_rate: number;
  overall_rate: number;
}

export type RegionalGroup = 'metropolitan_cities' | 'provinces' | 'other';

export interface RegionalGroupSummary {
  region_count: number;
  total_announced_units: number;
  total_applied_units: number;
  total_delivered_units: number;
  total_remaining_units: number;
  total_pending_deliveries: number;
  total_waitlist_units: number;
  depletion_rate: number;
  delivery_rate: number;
  status: AlertSeverity;
  regions: string[];
}

export interface EVSubsidyDataset {
  metadata: {
    version: string;
    generated_at: string;
    policy_year: number;
    data_sources: string[];
    total_regions_tracked: number;
    total_municipalities_tracked: number;
    currency: string;
  };
  alert_thresholds: Record<AlertSeverity, AlertThresholdConfig>;
  nationwide_summary: {
    total_announced_units: number;
    total_applied_units: number;
    total_delivered_units: number;
    total_remaining_units: number;
    nationwide_depletion_rate: number;
    total_budget_billion_krw: number;
    disbursed_budget_billion_krw: number;
    total_budget_krw?: number;
    disbursed_budget_krw?: number;
    category_totals: {
      passenger: CategoryMetrics;
      commercial: CategoryMetrics;
      bus: CategoryMetrics;
    };
    alert_region_counts: {
      healthy: number;
      caution: number;
      warning: number;
      critical: number;
      depleted: number;
    };
  };
  regions: RegionEntry[];
  popular_models_matrix: PopularModelEntry[];
  historical_depletion_trajectory?: HistoricalTrajectoryPoint[];
}

export interface SubsidyCalculationResult {
  modelId: string;
  modelName: string;
  manufacturer: string;
  batteryType: string;
  batteryCapacityKwh: number;
  ratedRangeKm: number;
  regionId: string;
  regionName: string;
  msrpKrw: number;
  priceSubsidyRatio: number; // 1.0, 0.5, or 0.0 based on 55M / 85M sliding price-cap rules
  nationalSubsidyKrw: number;
  localSubsidyKrw: number;
  additionalGrantsKrw: number;
  totalSubsidyKrw: number;
  netPurchasePriceKrw: number;
  isHighDepletionRisk: boolean; // >= 80%
  depletionRate: number;
  depletionStatus: AlertSeverity;
  residencyRequirementDays: number;
  warningNotice?: string;
  priceCapTierText: string;
}

export interface SubsidyCalculatorOptions {
  customMsrp?: number | string;
  isYouthFirstTimeBuyer?: boolean; // +20% national subsidy
  isSmallBusinessOrTaxi?: boolean; // +30% national subsidy
  isMultiChildFamily?: boolean; // +10% national subsidy
  isOldDieselScrappage?: boolean; // +1,000,000 KRW flat incentive
}

export interface RankedRegionEntry {
  rank: number;
  regionId: string;
  nameKo: string;
  depletionRate: number;
  remainingUnits: number;
  status: AlertSeverity;
  region: RegionEntry;
  // Shorthand backward-compatibility properties if accessed directly
  region_id?: string;
  name_ko?: string;
  overall_depletion_rate?: number;
  overall_status?: AlertSeverity;
}

export interface CriticalRegionInfo {
  regionId: string;
  nameKo: string;
  depletionRate: number;
  remainingUnits: number;
}

export interface CategoryBreakdownMetrics {
  announced: number;
  applied: number;
  remaining: number;
  rate: number;
}

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
  criticalRegions: CriticalRegionInfo[];
  warningRegionsCount: number;
  cautionRegionsCount: number;
  healthyRegionsCount: number;
  categoryBreakdown: {
    passenger: CategoryBreakdownMetrics;
    commercial: CategoryBreakdownMetrics;
    bus: CategoryBreakdownMetrics;
  };
  // Shorthand compatibility aliases
  announced?: number;
  applied?: number;
  delivered?: number;
  remaining?: number;
  depletionRate?: number;
  budgetTotal?: number;
  budgetDisbursed?: number;
  depletedRegionsCount?: number;
}

/**
 * Domain & Tracker Interoperability Aliases
 */
export type SubsidyPayload = EVSubsidyDataset;
export type SubsidyRegion = RegionEntry;


