/**
 * South Korea EV Subsidy Domain Type Definitions
 * Based on Ministry of Environment (환경부) & Korea Environment Corporation (KECO) 2026 Guidelines.
 */

export type AlertSeverity = 'HEALTHY' | 'CAUTION' | 'WARNING' | 'CRITICAL' | 'DEPLETED';

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
  max_local_subsidy_krw: number;
  max_total_subsidy_krw: number;
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
}

export interface RegionEntry {
  region_id: string;
  iso_code: string;
  name_ko: string;
  name_en: string;
  tier: 'special_city' | 'metropolitan_city' | 'special_self_governing_city' | 'province' | 'special_self_governing_province' | string;
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
  notes: string;
}

export interface PopularModelEntry {
  model_id: string;
  name_ko: string;
  manufacturer: string;
  battery_type: string;
  battery_capacity_kwh: number;
  rated_range_km: number;
  base_price_krw: number;
  price_subsidy_ratio: number;
  national_subsidy_krw: number;
  regional_subsidy_samples?: Record<
    string,
    {
      total_subsidy_krw: number;
      net_price_krw: number;
    }
  >;
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
  historical_depletion_trajectory?: Array<{
    date: string;
    passenger_rate: number;
    commercial_rate: number;
    overall_rate: number;
  }>;
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
  customMsrp?: number;
  isYouthFirstTimeBuyer?: boolean; // +20% national subsidy
  isSmallBusinessOrTaxi?: boolean; // +30% national subsidy
  isMultiChildFamily?: boolean; // +10% national subsidy
  isOldDieselScrappage?: boolean; // +1,000,000 KRW flat incentive
}
