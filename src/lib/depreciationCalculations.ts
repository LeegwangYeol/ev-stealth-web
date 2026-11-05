/**
 * Pure calculation utilities, type definitions, and mathematical models for EV Depreciation,
 * Battery Health (Arrhenius electrochemical kinetics), Subsidy Clawback, and Total Cost of Ownership (TCO).
 *
 * This module has ZERO dependencies on heavy JSON data files, enabling client bundles
 * to remain lean without bundling redundant static data payloads.
 */

// ==========================================
// 1. DOMAIN ENUMS & BASIC TYPES
// ==========================================

export type BatteryChemistryType = 'LFP' | 'NCM_622' | 'NCM_811' | 'NCMA' | 'NCA';
export type ResaleDefenseTier = 'S' | 'A' | 'A-' | 'B+' | 'B' | 'B-' | 'C+' | 'C' | 'D';
export type SoftwareOtaLevel = 'FULL_STACK' | 'ADVANCED_CCB' | 'INFOTAINMENT_ONLY' | 'BASIC';
export type BatteryRiskGrade = 'GRADE_A' | 'GRADE_B' | 'GRADE_C' | 'CRITICAL';
export type TransferType = 'intra' | 'inter' | 'export';
export type PriceBasis = 'msrp' | 'effective';

// ==========================================
// 2. DATABASE SCHEMA INTERFACES
// ==========================================

export interface DepreciationCurvePoint {
  residual_pct_msrp: number;
  depreciation_pct_msrp: number;
  residual_pct_effective: number;
  avg_used_price_krw: number;
  annual_drop_pct: number;
}

export interface DepreciationCurve {
  year_1: DepreciationCurvePoint;
  year_2: DepreciationCurvePoint;
  year_3: DepreciationCurvePoint;
  year_4: DepreciationCurvePoint;
  year_5: DepreciationCurvePoint;
  [key: string]: DepreciationCurvePoint;
}

export interface BatterySpecs {
  capacity_kwh: number;
  chemistry: string;
  cell_supplier: string;
  voltage_architecture: '400V' | '800V' | string;
}

export interface WarrantyInfo {
  years: number;
  km: number;
  guarantee_retention_pct: number;
}

export interface FactorWeights {
  warranty_cliff: number;
  chemistry_aging: number;
  architecture_800v: number;
  ota_maturity: number;
  net_factor_adjustment: number;
}

export interface EvModelDepreciation {
  id: string;
  brand_id: string;
  brand_name_en: string;
  brand_name_ko: string;
  model_name: string;
  segment: string;
  msrp_krw_baseline: number;
  avg_subsidy_krw: number;
  net_purchase_price_krw: number;
  battery_specs: BatterySpecs;
  warranty: WarrantyInfo;
  factor_weights: FactorWeights;
  software_ota_level: SoftwareOtaLevel;
  resale_defense_tier: ResaleDefenseTier;
  depreciation_curve: DepreciationCurve;
  key_pros_resale: string;
  key_cons_resale: string;
}

export interface BatteryReplacementTierCosts {
  new_pack_krw: number;
  new_pack_usd: number;
  reman_pack_krw: number | null;
  reman_pack_usd: number | null;
  labor_coolant_krw: number;
  labor_coolant_usd: number;
  total_new_installed_krw: number;
  total_new_installed_usd: number;
  total_reman_installed_krw: number | null;
  total_reman_installed_usd: number | null;
  cost_per_kwh_usd: number;
}

export interface BatteryReplacementTier {
  tier_id: string;
  segment_name: string;
  pack_size_kwh_nominal: number;
  pack_size_range: string;
  representative_models: string[];
  costs: BatteryReplacementTierCosts;
}

export interface BatteryChemistryProfile {
  id: BatteryChemistryType;
  name: string;
  cathode_structure: string;
  nominal_cell_voltage_v: number;
  voltage_cutoff_v: number;
  energy_density_wh_kg: number;
  cycle_life_to_80_soh: number;
  calendar_baseline_annual_loss_pct: number;
  calendar_arrhenius_ea_j_mol: number;
  soc_stress_coefficient_beta: number;
  calendar_time_exponent_z: number;
  cyclic_exponent_w: number;
  dod_exponent_u: number;
  dcfc_acceleration_multiplier_max: number;
  cold_charge_sensitivity_gamma: number;
  thermal_runaway_temp_c: number;
  ocv_profile_type: string;
  cell_balancing_requirement: string;
}

export interface AdjustmentFactors {
  warranty_cliff: {
    safe_period_multiplier: number;
    approaching_cliff_1_2_years_penalty: number;
    expired_warranty_penalty: number;
    description: string;
  };
  battery_chemistry: Record<
    string,
    {
      cycle_life_bonus_yr3_5: number;
      winter_seasonal_discount: number;
      fire_safety_reputation_bonus: number;
      description: string;
    }
  >;
  facelift_hardware?: {
    platform_800V_premium: number;
    platform_400V_penalty: number;
    major_facelift_compute_shift_penalty: number;
    description: string;
  };
  hardware_platform?: {
    architecture_800v_bonus: number;
    architecture_400v_penalty: number;
    description: string;
  };
  software_ota?: Record<string, number> | {
    full_stack_fota_bonus: number;
    legacy_infotainment_penalty: number;
    description: string;
  };
  mileage_sensitivity: {
    base_km_per_year?: number;
    baseline_annual_km?: number;
    penalty_per_10000km_excess: number;
    bonus_per_10000km_deficit: number;
    max_mileage_discount_cap?: number;
    description?: string;
  };
}

export interface ClawbackTier {
  min_months: number;
  max_months_exclusive: number | null;
  clawback_rate: number;
  label_ko: string;
}

export interface SubsidyTransferRule {
  scenario: string;
  clawback_local: boolean;
  clawback_national: boolean;
  description: string;
}

export interface SubsidyClawbackSchedule {
  mandatory_operation_months: number;
  legal_basis: string;
  tiers: ClawbackTier[];
  transfer_rules: Record<TransferType, SubsidyTransferRule>;
}

export interface IceDisplacementTier {
  max_cc: number | null;
  rate_per_cc_krw: number;
  name: string;
}

export interface TcoFuelTariffs {
  ev_slow_charging_krw_per_kwh: number;
  ev_fast_charging_krw_per_kwh: number;
  ice_gasoline_krw_per_liter: number;
  ice_diesel_krw_per_liter: number;
}

export interface TcoTaxParameters {
  ev_annual_tax_krw: number;
  ev_base_tax_krw: number;
  ev_education_tax_krw: number;
  ice_displacement_tiers: {
    max_cc: number | null;
    rate_per_cc_krw: number;
    name: string;
  }[];
  education_tax_multiplier: number;
  ice_age_discount_start_year: number;
  ice_age_discount_rate_per_year: number;
  ice_age_discount_max: number;
}

export interface TcoAuxiliaryBenefits {
  expressway_toll_discount_rate: number;
  annual_toll_savings_krw: number;
  public_parking_discount_rate: number;
  annual_parking_savings_krw: number;
  maintenance_annual_savings_krw: number;
}

export interface TcoEfficiencyBaselines {
  ev_efficiency_km_per_kwh: number;
  ice_gasoline_economy_km_per_liter: number;
  ice_diesel_economy_km_per_liter: number;
}

export interface TcoParameters {
  fuel_tariffs: TcoFuelTariffs;
  efficiency_baselines: TcoEfficiencyBaselines;
  tax_parameters: TcoTaxParameters;
  auxiliary_benefits: TcoAuxiliaryBenefits;
}

export interface DepreciationDatabase {
  metadata: {
    version: string;
    generated_at: string;
    total_models: number;
    brands_count: number;
    currency: string;
    baseline_annual_mileage_km: number;
    sources: string[];
  };
  market_context: {
    korean_market_status: string;
    cheongna_fire_impact_summary: string;
    subsidy_clawback_rules: string;
  };
  adjustment_factors: {
    warranty_cliff: {
      safe_period_multiplier: number;
      approaching_cliff_1_2_years_penalty: number;
      expired_warranty_penalty: number;
      description: string;
    };
    battery_chemistry: Record<string, {
      cycle_life_bonus_yr3_5: number;
      winter_seasonal_discount: number;
      fire_safety_reputation_bonus: number;
      description: string;
    }>;
    facelift_hardware?: {
      platform_800V_premium: number;
      platform_400V_penalty: number;
      major_facelift_compute_shift_penalty: number;
      description: string;
    };
    software_ota?: Record<string, number> | {
      full_stack_fota_bonus: number;
      legacy_infotainment_penalty: number;
      description: string;
    };
    mileage_sensitivity: {
      base_km_per_year?: number;
      baseline_annual_km?: number;
      penalty_per_10000km_excess: number;
      bonus_per_10000km_deficit: number;
      max_mileage_discount_cap?: number;
      description?: string;
    };
  };
  chemistries: Record<BatteryChemistryType, BatteryChemistryProfile>;
  battery_replacement_costs: BatteryReplacementTier[];
  subsidy_clawback_schedule: SubsidyClawbackSchedule;
  tco_parameters: TcoParameters;
  models: EvModelDepreciation[];
}

// ==========================================
// 3. CALCULATION INPUT & OUTPUT INTERFACES
// ==========================================

export interface DepreciationCalculationInput {
  modelId: string;
  years: number; // 0 to 10
  mileageKm?: number; // total odometer km
  winterSeason?: boolean;
  priceBasis?: PriceBasis;
  customPurchasePriceKrw?: number;
  model?: EvModelDepreciation;
}

export interface FactorAdjustmentsBreakdown {
  warrantyCliffPenalty: number;
  batteryChemistryBonus: number;
  architectureAdjustment: number;
  otaAdjustment: number;
  mileageAdjustment: number;
  winterAdjustment: number;
  totalAdjustmentPct: number;
}

export interface WarrantyStatus {
  isApproachingCliff: boolean;
  isExpired: boolean;
  remainingYears: number;
  remainingKm: number;
}

export interface DepreciationCalculationResult {
  model: EvModelDepreciation;
  years: number;
  mileageKm: number;
  priceBasis: PriceBasis;
  basePurchasePriceKrw: number;
  baselineResidualPct: number;
  adjustedResidualPct: number;
  estimatedResidualPriceKrw: number;
  depreciationAmountKrw: number;
  defenseTier: ResaleDefenseTier;
  factorAdjustments: FactorAdjustmentsBreakdown;
  warrantyStatus: WarrantyStatus;
  keyPros: string;
  keyCons: string;
}

export interface BatterySimulationInput {
  modelId?: string;
  model?: EvModelDepreciation;
  chemistry?: string;
  years?: number;
  totalKm?: number;
  annualKm?: number;
  dcfcRatio?: number; // 0.0 (100% slow) to 1.0 (100% DC fast)
  storageSoc?: number; // 0.2 to 1.0
  ambientTempC?: number; // Celsius (-20 to 45)
  packCapacityKwh?: number;
  vehicleEfficiencyKmPerKwh?: number;
}

export interface BatteryHealthResult {
  chemistry: BatteryChemistryType;
  chemistryName: string;
  years: number;
  totalKm: number;
  equivalentFullCycles: number;
  calendarLossPct: number;
  cyclicLossPct: number;
  totalLossPct: number;
  sohPct: number; // State of Health (100% to 0%)
  grade: BatteryRiskGrade;
  gradeLabel: string;
  badgeColor: string;
  failureRiskPct: number;
  winterRangeRetentionPct: number;
  usedMarketValuationFactor: number;
  usedMarketValuationText: string;
  actionRecommendation: string;
  replacementCostEstimate: {
    tierId: string;
    segmentName: string;
    newPackKrw: number;
    remanPackKrw: number | null;
    laborCoolantKrw: number;
    totalNewInstalledKrw: number;
    totalRemanInstalledKrw: number | null;
    estimatedCostKrw: number;
  };
}

export interface ClawbackResult {
  heldMonths: number;
  tierLabel: string;
  statutoryClawbackRate: number; // e.g. 0.70
  effectiveClawbackRate: number; // 0 if exempt, else statutory
  localSubsidyReceivedKrw: number;
  nationalSubsidyReceivedKrw: number;
  localClawbackKrw: number;
  nationalClawbackKrw: number;
  totalClawbackKrw: number;
  transferType: TransferType;
  isExempt: boolean;
  remainingMonthsOfObligation: number;
  explanation: string;
}

export interface TcoYearBreakdown {
  year: number;
  cumulativeKm: number;
  evElectricityCostKrw: number;
  iceFuelCostKrw: number;
  evAutomobileTaxKrw: number;
  iceAutomobileTaxKrw: number;
  tollSavingsKrw: number;
  parkingSavingsKrw: number;
  maintenanceSavingsKrw: number;
  annualNetSavingsKrw: number;
  cumulativeNetSavingsKrw: number;
}

export interface TcoResult {
  annualKm: number;
  years: number;
  totalKm: number;
  evEfficiencyKmPerKwh: number;
  iceFuelEconomyKmPerLiter: number;
  blendedElectricityTariffKrwPerKwh: number;
  gasolinePriceKrwPerLiter: number;
  evFuelCostPerKm: number;
  iceFuelCostPerKm: number;
  evTotalFuelCostKrw: number;
  iceTotalFuelCostKrw: number;
  fuelSavingsKrw: number;
  evTotalTaxKrw: number;
  iceTotalTaxKrw: number;
  taxSavingsKrw: number;
  tollSavingsKrw: number;
  parkingSavingsKrw: number;
  maintenanceSavingsKrw: number;
  totalAuxiliarySavingsKrw: number;
  totalCumulativeSavingsKrw: number;
  yearlyBreakdown: TcoYearBreakdown[];
}

// ==========================================
// 4. PURE DEFAULT CONSTANTS (ZERO JSON DEPENDENCY)
// ==========================================

export const DEFAULT_BASELINE_ANNUAL_MILEAGE_KM = 15000;

export const DEFAULT_ADJUSTMENT_FACTORS: AdjustmentFactors = {
  warranty_cliff: {
    safe_period_multiplier: 1.0,
    approaching_cliff_1_2_years_penalty: -0.06,
    expired_warranty_penalty: -0.14,
    description: '배터리 교체 비용으로 인해 보증 만료 2년 전부터 감가 가속, 만료 시 -14% 추가 급락',
  },
  battery_chemistry: {
    LFP: {
      cycle_life_bonus_yr3_5: 0.025,
      winter_seasonal_discount: -0.035,
      fire_safety_reputation_bonus: 0.03,
      description: '올리빈 구조의 높은 열적 안정성 및 수명(3,000사이클)으로 장기 잔존가치 우수하나 혹한기 충전 및 주행거리 저하',
    },
    NCM_622: {
      cycle_life_bonus_yr3_5: 0.0,
      winter_seasonal_discount: -0.015,
      fire_safety_reputation_bonus: 0.01,
      description: '균형 잡힌 중밀도 3원계 셀로 열화율이 완만하며 상대적으로 안정적인 방어율 유지',
    },
    NCM_811: {
      cycle_life_bonus_yr3_5: -0.01,
      winter_seasonal_discount: -0.01,
      fire_safety_reputation_bonus: 0.0,
      description: '고에너지밀도 하이니켈 셀로 저온 효율 우수하나 고충전율 및 급속충전에 따른 미세 크랙 위험',
    },
    NCMA: {
      cycle_life_bonus_yr3_5: 0.015,
      winter_seasonal_discount: -0.01,
      fire_safety_reputation_bonus: 0.015,
      description: '알루미늄 도핑 4원계 양극재로 하이니켈 안정성 강화 및 사이클 수명 개선',
    },
    NCA: {
      cycle_life_bonus_yr3_5: -0.015,
      winter_seasonal_discount: -0.01,
      fire_safety_reputation_bonus: -0.005,
      description: '원통형 고출력 특화 양극재로 초기 성능 우수하나 캘린더 열화 속도가 상대적으로 빠름',
    },
  },
  mileage_sensitivity: {
    baseline_annual_km: 15000,
    penalty_per_10000km_excess: -0.015,
    bonus_per_10000km_deficit: 0.01,
    max_mileage_discount_cap: -0.15,
    description: '연 15,000km 기준 10,000km 초과 시마다 -1.5% 감가 페널티, 미달 시 +1.0% 가산',
  },
  hardware_platform: {
    architecture_800v_bonus: 0.02,
    architecture_400v_penalty: 0.0,
    description: '800V 초고전압 시스템 탑재 시 18분 급속충전 경쟁력으로 잔존가치 +2% 방어',
  },
  software_ota: {
    full_stack_fota_bonus: 0.025,
    legacy_infotainment_penalty: -0.02,
    description: '구동계·BMS 풀스택 OTA 지원 모델은 감가 방어율 +2.5% 프리미엄',
  },
};

export const DEFAULT_CHEMISTRY_PROFILES: Record<BatteryChemistryType, BatteryChemistryProfile> = {
  LFP: {
    id: 'LFP',
    name: 'LFP (리튬인산철)',
    cathode_structure: 'Olivine LiFePO4',
    nominal_cell_voltage_v: 3.2,
    voltage_cutoff_v: 2.5,
    energy_density_wh_kg: 175,
    cycle_life_to_80_soh: 3000,
    calendar_baseline_annual_loss_pct: 0.9,
    calendar_arrhenius_ea_j_mol: 52000,
    soc_stress_coefficient_beta: 0.45,
    calendar_time_exponent_z: 0.5,
    cyclic_exponent_w: 0.52,
    dod_exponent_u: 1.15,
    dcfc_acceleration_multiplier_max: 1.35,
    cold_charge_sensitivity_gamma: 0.85,
    thermal_runaway_temp_c: 270,
    ocv_profile_type: 'FLAT_PLATEAU',
    cell_balancing_requirement: 'WEEKLY_100PCT_MANDATORY',
  },
  NCM_622: {
    id: 'NCM_622',
    name: 'NCM 622 (중밀도 3원계)',
    cathode_structure: 'Layered LiNi0.6Co0.2Mn0.2O2',
    nominal_cell_voltage_v: 3.65,
    voltage_cutoff_v: 2.75,
    energy_density_wh_kg: 240,
    cycle_life_to_80_soh: 1800,
    calendar_baseline_annual_loss_pct: 1.4,
    calendar_arrhenius_ea_j_mol: 60000,
    soc_stress_coefficient_beta: 0.85,
    calendar_time_exponent_z: 0.5,
    cyclic_exponent_w: 0.56,
    dod_exponent_u: 1.3,
    dcfc_acceleration_multiplier_max: 1.6,
    cold_charge_sensitivity_gamma: 0.45,
    thermal_runaway_temp_c: 215,
    ocv_profile_type: 'SLOPING',
    cell_balancing_requirement: 'NORMAL_BMS_ROUTINE',
  },
  NCM_811: {
    id: 'NCM_811',
    name: 'NCM 811 (하이니켈 3원계)',
    cathode_structure: 'Layered LiNi0.8Co0.1Mn0.1O2',
    nominal_cell_voltage_v: 3.7,
    voltage_cutoff_v: 2.8,
    energy_density_wh_kg: 275,
    cycle_life_to_80_soh: 1400,
    calendar_baseline_annual_loss_pct: 1.7,
    calendar_arrhenius_ea_j_mol: 65000,
    soc_stress_coefficient_beta: 1.05,
    calendar_time_exponent_z: 0.5,
    cyclic_exponent_w: 0.6,
    dod_exponent_u: 1.4,
    dcfc_acceleration_multiplier_max: 1.9,
    cold_charge_sensitivity_gamma: 0.35,
    thermal_runaway_temp_c: 195,
    ocv_profile_type: 'SLOPING',
    cell_balancing_requirement: 'NORMAL_BMS_ROUTINE',
  },
  NCMA: {
    id: 'NCMA',
    name: 'NCMA (알루미늄 도핑 4원계)',
    cathode_structure: 'Layered LiNi0.89Co0.05Mn0.05Al0.01O2',
    nominal_cell_voltage_v: 3.7,
    voltage_cutoff_v: 2.8,
    energy_density_wh_kg: 290,
    cycle_life_to_80_soh: 1600,
    calendar_baseline_annual_loss_pct: 1.3,
    calendar_arrhenius_ea_j_mol: 62000,
    soc_stress_coefficient_beta: 0.8,
    calendar_time_exponent_z: 0.5,
    cyclic_exponent_w: 0.58,
    dod_exponent_u: 1.35,
    dcfc_acceleration_multiplier_max: 1.7,
    cold_charge_sensitivity_gamma: 0.4,
    thermal_runaway_temp_c: 205,
    ocv_profile_type: 'SLOPING',
    cell_balancing_requirement: 'NORMAL_BMS_ROUTINE',
  },
  NCA: {
    id: 'NCA',
    name: 'NCA (니켈·코발트·알루미늄 원통형)',
    cathode_structure: 'Layered LiNi0.85Co0.12Al0.03O2',
    nominal_cell_voltage_v: 3.65,
    voltage_cutoff_v: 2.75,
    energy_density_wh_kg: 280,
    cycle_life_to_80_soh: 1300,
    calendar_baseline_annual_loss_pct: 1.6,
    calendar_arrhenius_ea_j_mol: 67000,
    soc_stress_coefficient_beta: 0.95,
    calendar_time_exponent_z: 0.5,
    cyclic_exponent_w: 0.62,
    dod_exponent_u: 1.45,
    dcfc_acceleration_multiplier_max: 2.0,
    cold_charge_sensitivity_gamma: 0.3,
    thermal_runaway_temp_c: 190,
    ocv_profile_type: 'SLOPING',
    cell_balancing_requirement: 'NORMAL_BMS_ROUTINE',
  },
};

export const DEFAULT_REPLACEMENT_TIERS: BatteryReplacementTier[] = [
  {
    tier_id: 'TIER_50KWH',
    segment_name: '소형/경형 (40~60kWh)',
    pack_size_kwh_nominal: 50,
    pack_size_range: '40~60 kWh',
    representative_models: ['CASPER_EV', 'RAY_EV', 'KONA_ELECTRIC'],
    costs: {
      new_pack_krw: 16500000,
      new_pack_usd: 12200,
      reman_pack_krw: 11500000,
      reman_pack_usd: 8500,
      labor_coolant_krw: 1200000,
      labor_coolant_usd: 890,
      total_new_installed_krw: 17700000,
      total_new_installed_usd: 13090,
      total_reman_installed_krw: 12700000,
      total_reman_installed_usd: 9390,
      cost_per_kwh_usd: 244,
    },
  },
  {
    tier_id: 'TIER_77KWH',
    segment_name: '준중형/중형 (65~84kWh)',
    pack_size_kwh_nominal: 77.4,
    pack_size_range: '65~84 kWh',
    representative_models: ['IONIQ_5', 'EV6', 'TESLA_MODEL_Y', 'TESLA_MODEL_3'],
    costs: {
      new_pack_krw: 24500000,
      new_pack_usd: 18100,
      reman_pack_krw: 16500000,
      reman_pack_usd: 12200,
      labor_coolant_krw: 1500000,
      labor_coolant_usd: 1110,
      total_new_installed_krw: 26000000,
      total_new_installed_usd: 19210,
      total_reman_installed_krw: 18000000,
      total_reman_installed_usd: 13310,
      cost_per_kwh_usd: 234,
    },
  },
  {
    tier_id: 'TIER_100KWH',
    segment_name: '대형/플래그십 (90~110kWh)',
    pack_size_kwh_nominal: 99.8,
    pack_size_range: '89~110 kWh',
    representative_models: ['EV9', 'GENESIS_GV70_ELECTRIFIED', 'BENZ_EQE_350', 'TAYCAN'],
    costs: {
      new_pack_krw: 38000000,
      new_pack_usd: 28100,
      reman_pack_krw: null,
      reman_pack_usd: null,
      labor_coolant_krw: 2200000,
      labor_coolant_usd: 1630,
      total_new_installed_krw: 40200000,
      total_new_installed_usd: 29730,
      total_reman_installed_krw: null,
      total_reman_installed_usd: null,
      cost_per_kwh_usd: 282,
    },
  },
];

export const DEFAULT_CLAWBACK_TIERS: ClawbackTier[] = [
  { min_months: 0, max_months_exclusive: 3, clawback_rate: 0.7, label_ko: '3개월 미만 (70% 회수)' },
  { min_months: 3, max_months_exclusive: 6, clawback_rate: 0.6, label_ko: '3개월 이상 6개월 미만 (60% 회수)' },
  { min_months: 6, max_months_exclusive: 12, clawback_rate: 0.5, label_ko: '6개월 이상 12개월 미만 (50% 회수)' },
  { min_months: 12, max_months_exclusive: 18, clawback_rate: 0.35, label_ko: '12개월 이상 18개월 미만 (35% 회수)' },
  { min_months: 18, max_months_exclusive: 24, clawback_rate: 0.2, label_ko: '18개월 이상 24개월 미만 (20% 회수)' },
  { min_months: 24, max_months_exclusive: null, clawback_rate: 0.0, label_ko: '24개월 이상 (의무종료 / 회수 없음)' },
];

export const DEFAULT_TCO_PARAMETERS: TcoParameters = {
  fuel_tariffs: {
    ev_slow_charging_krw_per_kwh: 260,
    ev_fast_charging_krw_per_kwh: 380,
    ice_gasoline_krw_per_liter: 1680,
    ice_diesel_krw_per_liter: 1540,
  },
  efficiency_baselines: {
    ev_efficiency_km_per_kwh: 5.2,
    ice_gasoline_economy_km_per_liter: 12.0,
    ice_diesel_economy_km_per_liter: 14.5,
  },
  tax_parameters: {
    ev_annual_tax_krw: 130000,
    ev_base_tax_krw: 100000,
    ev_education_tax_krw: 30000,
    ice_displacement_tiers: [
      { max_cc: 1000, rate_per_cc_krw: 80, name: '경차' },
      { max_cc: 1600, rate_per_cc_krw: 140, name: '소형' },
      { max_cc: null, rate_per_cc_krw: 200, name: '중대형' },
    ],
    education_tax_multiplier: 0.3,
    ice_age_discount_start_year: 3,
    ice_age_discount_rate_per_year: 0.05,
    ice_age_discount_max: 0.5,
  },
  auxiliary_benefits: {
    expressway_toll_discount_rate: 0.5,
    annual_toll_savings_krw: 280000,
    public_parking_discount_rate: 0.5,
    annual_parking_savings_krw: 190000,
    maintenance_annual_savings_krw: 450000,
  },
};

export const FALLBACK_MODEL: EvModelDepreciation = {
  id: 'ioniq-5-2026',
  brand_id: 'hyundai',
  brand_name_en: 'Hyundai',
  brand_name_ko: '현대자동차',
  model_name: '아이오닉 5 롱레인지 2WD (2026)',
  segment: '준중형 CUV',
  msrp_krw_baseline: 54100000,
  avg_subsidy_krw: 8000000,
  net_purchase_price_krw: 46100000,
  battery_specs: {
    capacity_kwh: 84.0,
    chemistry: 'NCMA',
    cell_supplier: 'SK온',
    voltage_architecture: '800V',
  },
  warranty: {
    years: 10,
    km: 200000,
    guarantee_retention_pct: 70,
  },
  factor_weights: {
    warranty_cliff: 1.0,
    chemistry_aging: 0.015,
    architecture_800v: 0.02,
    ota_maturity: 0.015,
    net_factor_adjustment: 0.05,
  },
  software_ota_level: 'ADVANCED_CCB',
  resale_defense_tier: 'A',
  depreciation_curve: {
    year_1: {
      residual_pct_msrp: 85.0,
      depreciation_pct_msrp: 15.0,
      residual_pct_effective: 92.0,
      avg_used_price_krw: 45985000,
      annual_drop_pct: 15.0,
    },
    year_2: {
      residual_pct_msrp: 75.0,
      depreciation_pct_msrp: 25.0,
      residual_pct_effective: 82.0,
      avg_used_price_krw: 40575000,
      annual_drop_pct: 10.0,
    },
    year_3: {
      residual_pct_msrp: 65.0,
      depreciation_pct_msrp: 35.0,
      residual_pct_effective: 71.0,
      avg_used_price_krw: 35165000,
      annual_drop_pct: 10.0,
    },
    year_4: {
      residual_pct_msrp: 55.0,
      depreciation_pct_msrp: 45.0,
      residual_pct_effective: 60.0,
      avg_used_price_krw: 29755000,
      annual_drop_pct: 10.0,
    },
    year_5: {
      residual_pct_msrp: 45.0,
      depreciation_pct_msrp: 55.0,
      residual_pct_effective: 49.0,
      avg_used_price_krw: 24345000,
      annual_drop_pct: 10.0,
    },
  },
  key_pros_resale: '800V 초급속 충전 및 넓은 실내 거주성',
  key_cons_resale: '부분변경에 따른 구형 시세 완만 조정',
};

// ==========================================
// 5. HELPER MATH UTILITIES
// ==========================================

export function clamp(val: number, min: number, max: number): number {
  const safeMin = Number.isFinite(min) ? min : 0;
  const safeMax = Number.isFinite(max) ? max : safeMin;
  const trueMin = Math.min(safeMin, safeMax);
  const trueMax = Math.max(safeMin, safeMax);
  if (!Number.isFinite(val)) return trueMin;
  return Math.min(Math.max(val, trueMin), trueMax);
}

export function normalizeChemistry(chem?: string | null): BatteryChemistryType {
  if (!chem || typeof chem !== 'string') return 'NCM_811';
  const upper = chem.toUpperCase();
  if (upper.includes('LFP')) return 'LFP';
  if (upper.includes('622')) return 'NCM_622';
  if (upper.includes('NCMA')) return 'NCMA';
  if (upper.includes('NCA')) return 'NCA';
  return 'NCM_811';
}

export function interpolateBaselineResidual(
  curve: DepreciationCurve,
  years: number,
  basis: PriceBasis
): number {
  const key = basis === 'effective' ? 'residual_pct_effective' : 'residual_pct_msrp';

  if (!Number.isFinite(years) || years <= 0) return 100.0;

  const getPoint = (val: unknown, fallback: number): number =>
    typeof val === 'number' && Number.isFinite(val) ? clamp(val, 0.0, 100.0) : fallback;

  const y1 = getPoint(curve?.year_1?.[key], 100.0);
  const y2 = getPoint(curve?.year_2?.[key], y1);
  const y3 = getPoint(curve?.year_3?.[key], y2);
  const y4 = getPoint(curve?.year_4?.[key], y3);
  const y5 = getPoint(curve?.year_5?.[key], y4 !== 100.0 ? y4 : 50.0);

  if (years <= 1.0) {
    return clamp(100.0 - years * (100.0 - y1), 0.0, 100.0);
  }
  if (years <= 2.0) {
    return clamp(y1 - (years - 1.0) * (y1 - y2), 0.0, 100.0);
  }
  if (years <= 3.0) {
    return clamp(y2 - (years - 2.0) * (y2 - y3), 0.0, 100.0);
  }
  if (years <= 4.0) {
    return clamp(y3 - (years - 3.0) * (y3 - y4), 0.0, 100.0);
  }
  if (years <= 5.0) {
    return clamp(y4 - (years - 4.0) * (y4 - y5), 0.0, 100.0);
  }

  // Beyond 5 years: extrapolate with compounding 8% drop per additional year
  const excessYears = years - 5.0;
  const extrapolated = y5 * Math.pow(0.92, excessYears);
  const safeExtrapolated = Number.isFinite(extrapolated) ? Math.max(10.0, extrapolated) : 10.0;
  return clamp(safeExtrapolated, 0.0, 100.0);
}

// ==========================================
// 6. CORE CALCULATION ENGINES
// ==========================================

export interface CalculateDepreciationOptions {
  model?: EvModelDepreciation;
  models?: EvModelDepreciation[];
  baselineAnnualMileageKm?: number;
  adjustmentFactors?: AdjustmentFactors;
}

/**
 * Calculates empirical depreciation and adjusted residual value for an EV.
 * Operates purely on provided model parameters without mandatory JSON dataset imports.
 */
export function calculateDepreciation(
  input: DepreciationCalculationInput,
  options?: CalculateDepreciationOptions
): DepreciationCalculationResult {
  const safeInput = input && typeof input === 'object' ? input : ({} as DepreciationCalculationInput);
  const rawYears = safeInput.years;
  const parsedYears = typeof rawYears === 'number' ? rawYears : Number(rawYears);
  const years = Number.isFinite(parsedYears) ? Math.max(0, parsedYears) : 0;

  const baselineAnnualMileageKm =
    options?.baselineAnnualMileageKm ?? DEFAULT_BASELINE_ANNUAL_MILEAGE_KM;
  const adjustmentFactors =
    options?.adjustmentFactors ?? DEFAULT_ADJUSTMENT_FACTORS;

  const rawMileage = safeInput.mileageKm;
  const parsedMileage = typeof rawMileage === 'number' ? rawMileage : Number(rawMileage);
  const defaultMileage = years * baselineAnnualMileageKm;
  const mileageKm = Number.isFinite(parsedMileage) ? Math.max(0, parsedMileage) : defaultMileage;

  const {
    modelId,
    winterSeason = false,
    priceBasis = 'msrp',
    customPurchasePriceKrw,
  } = safeInput;

  let model = safeInput.model || options?.model;
  if (!model && options?.models && modelId) {
    model = options.models.find(
      (m) => m.id.toLowerCase() === modelId.toLowerCase() || m.id === modelId
    );
  }
  if (!model) {
    model = FALLBACK_MODEL;
  }

  const baselineResidualPct = interpolateBaselineResidual(
    model.depreciation_curve,
    years,
    priceBasis
  );

  // 1. Mileage Adjustment
  const expectedMileage = years * baselineAnnualMileageKm;
  const deltaMileage = mileageKm - expectedMileage;
  let mileageAdjustment = 0;
  if (deltaMileage > 0) {
    const rawPenalty =
      (deltaMileage / 10000) *
      adjustmentFactors.mileage_sensitivity.penalty_per_10000km_excess;
    const maxDiscountCap =
      adjustmentFactors.mileage_sensitivity.max_mileage_discount_cap ?? -0.15;
    if (mileageKm >= 500000) {
      mileageAdjustment = rawPenalty;
    } else if (mileageKm > 300000) {
      const progress = (mileageKm - 300000) / 200000;
      mileageAdjustment = maxDiscountCap * (1 - progress) + rawPenalty * progress;
    } else {
      mileageAdjustment = Math.max(maxDiscountCap, rawPenalty);
    }
  } else {
    const bonusRate = adjustmentFactors.mileage_sensitivity.bonus_per_10000km_deficit;
    mileageAdjustment = Math.min(0.06, (Math.abs(deltaMileage) / 10000) * bonusRate);
  }

  // 2. Warranty Cliff
  const warrantyYears = model?.warranty?.years ?? 8;
  const warrantyKm = model?.warranty?.km ?? 160000;
  const remainingWarrantyYears = warrantyYears - years;
  const remainingWarrantyKm = warrantyKm - mileageKm;
  const isExpired = remainingWarrantyYears <= 0 || remainingWarrantyKm <= 0;
  const isApproachingCliff =
    !isExpired && (remainingWarrantyYears <= 2 || remainingWarrantyKm <= 25000);

  let warrantyCliffPenalty = 0;
  if (isExpired) {
    warrantyCliffPenalty = adjustmentFactors.warranty_cliff.expired_warranty_penalty;
  } else if (isApproachingCliff) {
    warrantyCliffPenalty =
      adjustmentFactors.warranty_cliff.approaching_cliff_1_2_years_penalty;
  }

  // 3. Chemistry Aging Adjustment
  const modelChemistry = model?.battery_specs?.chemistry ?? 'NCM_811';
  let batteryChemistryBonus = model?.factor_weights?.chemistry_aging ?? 0;
  if (modelChemistry.includes('LFP')) {
    // Smooth monotonic ramp from year 2.0 to 3.0 to ensure discrete chemistry bonuses never invert the depreciation curve
    const lfpBonusRamp = clamp(years - 2.0, 0.0, 1.0);
    batteryChemistryBonus += 0.01 * lfpBonusRamp;
  }

  // 4. Winter Season Adjustment
  let winterAdjustment = 0;
  if (winterSeason) {
    if (modelChemistry.includes('LFP')) {
      winterAdjustment = -0.035;
    } else {
      winterAdjustment = -0.015;
    }
  }

  // 5. Hardware Architecture & OTA
  const architectureAdjustment = model?.factor_weights?.architecture_800v ?? 0;
  const otaAdjustment = model?.factor_weights?.ota_maturity ?? 0;

  // Combine Total Adjustments
  const totalAdjustmentPct =
    (warrantyCliffPenalty +
      batteryChemistryBonus +
      architectureAdjustment +
      otaAdjustment +
      mileageAdjustment +
      winterAdjustment) *
    100;

  const adjustedResidualPct = clamp(
    Math.round((baselineResidualPct + totalAdjustmentPct) * 10) / 10,
    5.0,
    99.0
  );

  const parsedCustomPrice =
    typeof customPurchasePriceKrw === 'number'
      ? customPurchasePriceKrw
      : typeof customPurchasePriceKrw === 'string' && (customPurchasePriceKrw as string).trim() !== ''
      ? Number((customPurchasePriceKrw as string).trim())
      : NaN;

  const rawBasePurchasePrice =
    Number.isFinite(parsedCustomPrice) && parsedCustomPrice >= 0
      ? parsedCustomPrice
      : priceBasis === 'effective'
      ? (model?.net_purchase_price_krw ?? 48_000_000)
      : (model?.msrp_krw_baseline ?? 55_000_000);

  const basePurchasePriceKrw = Math.min(10_000_000_000, Math.max(0, rawBasePurchasePrice));

  const rawEstimatedResidual = Math.round(
    (basePurchasePriceKrw * adjustedResidualPct) / 100
  );
  const estimatedResidualPriceKrw = clamp(
    rawEstimatedResidual,
    0,
    basePurchasePriceKrw
  );
  const depreciationAmountKrw = clamp(
    basePurchasePriceKrw - estimatedResidualPriceKrw,
    0,
    basePurchasePriceKrw
  );

  return {
    model,
    years,
    mileageKm,
    priceBasis,
    basePurchasePriceKrw,
    baselineResidualPct: Math.round(baselineResidualPct * 10) / 10,
    adjustedResidualPct,
    estimatedResidualPriceKrw,
    depreciationAmountKrw,
    defenseTier: model?.resale_defense_tier ?? 'B',
    factorAdjustments: {
      warrantyCliffPenalty: Math.round(warrantyCliffPenalty * 1000) / 10,
      batteryChemistryBonus: Math.round(batteryChemistryBonus * 1000) / 10,
      architectureAdjustment: Math.round(architectureAdjustment * 1000) / 10,
      otaAdjustment: Math.round(otaAdjustment * 1000) / 10,
      mileageAdjustment: Math.round(mileageAdjustment * 1000) / 10,
      winterAdjustment: Math.round(winterAdjustment * 1000) / 10,
      totalAdjustmentPct: Math.round(totalAdjustmentPct * 10) / 10,
    },
    warrantyStatus: {
      isApproachingCliff,
      isExpired,
      remainingYears: Number.isFinite(remainingWarrantyYears)
        ? Math.max(0, Math.round(remainingWarrantyYears * 10) / 10)
        : 0,
      remainingKm: Number.isFinite(remainingWarrantyKm)
        ? Math.max(0, Math.round(remainingWarrantyKm))
        : 0,
    },
    keyPros: model?.key_pros_resale ?? '데이터 동기화 완료',
    keyCons: model?.key_cons_resale ?? '정기 점검 필요',
  };
}

/**
 * Simulates electrochemical State of Health (SoH) and degradation kinetics.
 * Combines Arrhenius calendar aging and cyclic fatigue with DC fast charging strain.
 */
export function simulateBatteryHealth(
  params: BatterySimulationInput,
  customChemistries?: Record<string, BatteryChemistryProfile>,
  customReplacementCosts?: BatteryReplacementTier[],
  options?: { models?: EvModelDepreciation[]; model?: EvModelDepreciation }
): BatteryHealthResult {
  const safeParams = params && typeof params === 'object' ? params : ({} as BatterySimulationInput);
  const {
    chemistry: chemInput,
    modelId,
    years: rawYears,
    totalKm: inputTotalKm,
    annualKm = 15000,
    dcfcRatio = 0.25,
    storageSoc = 0.5,
    ambientTempC = 25.0,
    vehicleEfficiencyKmPerKwh = 5.2,
  } = safeParams;

  const parsedYears = typeof rawYears === 'number' ? rawYears : Number(rawYears);
  const isInvalidYears =
    rawYears === undefined ||
    rawYears === null ||
    !Number.isFinite(parsedYears) ||
    parsedYears < 0;
  const safeYears = isInvalidYears ? 3 : clamp(parsedYears, 0, 100);

  let model: EvModelDepreciation | undefined = safeParams.model || options?.model;
  if (!model && options?.models && modelId) {
    model = options.models.find(
      (m) => m.id.toLowerCase() === modelId.toLowerCase() || m.id === modelId
    );
  }
  if (!model && modelId) {
    if (FALLBACK_MODEL.id.toLowerCase() === modelId.toLowerCase() || FALLBACK_MODEL.id === modelId) {
      model = FALLBACK_MODEL;
    }
  }

  const chemistryKey: BatteryChemistryType = normalizeChemistry(
    chemInput || model?.battery_specs?.chemistry || 'NCM_811'
  );

  const chemProfile =
    customChemistries?.[chemistryKey] ||
    DEFAULT_CHEMISTRY_PROFILES[chemistryKey] ||
    DEFAULT_CHEMISTRY_PROFILES.NCM_811;

  const parsedPackCapacity =
    typeof safeParams.packCapacityKwh === 'number'
      ? safeParams.packCapacityKwh
      : typeof safeParams.packCapacityKwh === 'string' && (safeParams.packCapacityKwh as string).trim() !== ''
      ? Number((safeParams.packCapacityKwh as string).trim())
      : (model?.battery_specs?.capacity_kwh ?? 77.4);
  const packCapacityKwh = Number.isFinite(parsedPackCapacity) && parsedPackCapacity > 0 ? parsedPackCapacity : 77.4;

  const parsedAnnualKm = typeof annualKm === 'number'
    ? annualKm
    : typeof annualKm === 'string' && (annualKm as string).trim() !== ''
    ? Number((annualKm as string).trim())
    : NaN;
  const safeAnnualKm = Number.isFinite(parsedAnnualKm) && parsedAnnualKm >= 0 ? parsedAnnualKm : 15000;

  const parsedInputTotalKm = typeof inputTotalKm === 'number'
    ? inputTotalKm
    : typeof inputTotalKm === 'string' && (inputTotalKm as string).trim() !== ''
    ? Number((inputTotalKm as string).trim())
    : NaN;
  const rawMileage = Number.isFinite(parsedInputTotalKm)
    ? parsedInputTotalKm
    : safeYears * safeAnnualKm;
  const safeMileage = clamp(rawMileage, 0, 10_000_000);

  // A. Calendar Aging via Arrhenius & SoC Kinetics
  const R_GAS = 8.314462;
  const T_REF_K = 298.15;
  const SOC_REF = 0.5;

  const parsedAmbientTemp = typeof ambientTempC === 'number'
    ? ambientTempC
    : typeof ambientTempC === 'string' && (ambientTempC as string).trim() !== ''
    ? Number((ambientTempC as string).trim())
    : NaN;
  const safeTempC = Number.isFinite(parsedAmbientTemp) ? clamp(parsedAmbientTemp, -60.0, 85.0) : 25.0;

  const parsedStorageSoc = typeof storageSoc === 'number'
    ? storageSoc
    : typeof storageSoc === 'string' && (storageSoc as string).trim() !== ''
    ? Number((storageSoc as string).trim())
    : NaN;
  const safeStorageSoc = Number.isFinite(parsedStorageSoc) ? clamp(parsedStorageSoc, 0.0, 1.0) : 0.5;

  const parsedDcfcRatio = typeof dcfcRatio === 'number'
    ? dcfcRatio
    : typeof dcfcRatio === 'string' && (dcfcRatio as string).trim() !== ''
    ? Number((dcfcRatio as string).trim())
    : NaN;
  const safeDcfcRatio = Number.isFinite(parsedDcfcRatio) ? clamp(parsedDcfcRatio, 0.0, 1.0) : 0.25;
  const tempK = Math.max(1.0, safeTempC + 273.15);

  const arrheniusEa = chemProfile.calendar_arrhenius_ea_j_mol ?? 60000;
  const arrheniusFactor = Math.exp(
    (-arrheniusEa / R_GAS) * (1.0 / tempK - 1.0 / T_REF_K)
  );
  const socBeta = chemProfile.soc_stress_coefficient_beta ?? 0.85;
  const socFactor = Math.exp(
    socBeta * (safeStorageSoc - SOC_REF)
  );
  const baselineAnnualLoss = chemProfile.calendar_baseline_annual_loss_pct ?? 1.4;
  const kCal =
    (baselineAnnualLoss / 100.0) *
    arrheniusFactor *
    socFactor;
  const calendarTimeExp = chemProfile.calendar_time_exponent_z ?? 0.5;
  const qLossCal =
    safeYears === 0
      ? 0
      : kCal * Math.pow(Math.max(0.1, safeYears), calendarTimeExp);

  // B. Cyclic Aging via Mechanical Strain & DCFC Factor
  const parsedEfficiency = typeof vehicleEfficiencyKmPerKwh === 'number'
    ? vehicleEfficiencyKmPerKwh
    : typeof vehicleEfficiencyKmPerKwh === 'string' && (vehicleEfficiencyKmPerKwh as string).trim() !== ''
    ? Number((vehicleEfficiencyKmPerKwh as string).trim())
    : NaN;
  const safeEfficiency =
    Number.isFinite(parsedEfficiency) && parsedEfficiency > 0
      ? parsedEfficiency
      : 5.2;
  const safeCapacity =
    Number.isFinite(packCapacityKwh) && packCapacityKwh > 0
      ? packCapacityKwh
      : (model?.battery_specs?.capacity_kwh ?? 77.4);

  const energyThroughputKwh = safeMileage / Math.max(1.0, safeEfficiency);
  const equivalentFullCycles = energyThroughputKwh / Math.max(10.0, safeCapacity);
  const safeCycles = Number.isFinite(equivalentFullCycles) ? Math.max(0, equivalentFullCycles) : 0;

  const dodExp = chemProfile.dod_exponent_u ?? 1.3;
  const fDod = Math.pow(0.85, dodExp);
  const dcfcMax = chemProfile.dcfc_acceleration_multiplier_max ?? 1.6;
  const fDcfc =
    1.0 + (dcfcMax - 1.0) * safeDcfcRatio;

  let fTempCyc = 1.0;
  if (safeTempC < 0) {
    const coldSensitivity = chemProfile.cold_charge_sensitivity_gamma ?? 0.45;
    const coldFraction = Math.min(1.0, Math.abs(safeTempC) / 15.0);
    fTempCyc = 1.0 + coldSensitivity * coldFraction;
  }

  const baseCycles = Math.max(100, chemProfile.cycle_life_to_80_soh ?? 1800);
  const cyclicExp = chemProfile.cyclic_exponent_w ?? 0.56;
  const qLossCyc =
    (0.2 / Math.pow(baseCycles, cyclicExp)) *
    fDod *
    fDcfc *
    fTempCyc *
    Math.pow(safeCycles, cyclicExp);

  // C. Sub-additive Coupling (p = 1.25)
  const P_COUPLING = 1.25;
  const safeQLossCal = Number.isFinite(qLossCal) ? Math.max(0, qLossCal) : 0;
  const safeQLossCyc = Number.isFinite(qLossCyc) ? Math.max(0, qLossCyc) : 0;
  const qLossTotal = Math.pow(
    Math.pow(safeQLossCal, P_COUPLING) + Math.pow(safeQLossCyc, P_COUPLING),
    1.0 / P_COUPLING
  );

  const finiteQLossTotal = Number.isFinite(qLossTotal) ? Math.max(0, qLossTotal) : 0;
  const rawSoh = (1.0 - finiteQLossTotal) * 100;
  const sohPct = clamp(Math.round(rawSoh * 10) / 10, 0.0, 100.0);

  // D. Grade Determination
  let grade: BatteryRiskGrade = 'GRADE_A';
  let gradeLabel = 'Grade A (최상급 / Pristine)';
  let badgeColor = 'emerald';
  let failureRiskPct = 0.3;
  let winterRangeRetentionPct = 76;
  let usedMarketValuationFactor = 1.0;
  let usedMarketValuationText = '감가 영향 없음 (신차급 / CPO 인증 프리미엄 대상)';
  let actionRecommendation =
    chemistryKey === 'LFP'
      ? '주 1회 100% 충전으로 BMS 셀 밸런싱을 유지하십시오.'
      : '일상 충전 제한을 80%로 설정하여 배터리 수명을 극대화하십시오.';

  if (sohPct < 70.0) {
    grade = 'CRITICAL';
    gradeLabel = 'Critical (수명 만료 / 교체 대상)';
    badgeColor = 'red';
    failureRiskPct = 42.0;
    winterRangeRetentionPct = 36;
    usedMarketValuationFactor = 0.3;
    usedMarketValuationText = '-60% ~ -80% 시세 폭락 (폐차/전손 기준 가치)';
    actionRecommendation =
      '배터리 교체 판정 대상입니다. 주행 중 갑작스러운 출력 차단 및 고속도로 주행 위험이 있습니다.';
  } else if (sohPct < 80.0) {
    grade = 'GRADE_C';
    gradeLabel = 'Grade C (경고 / 급속 열화 진입)';
    badgeColor = 'amber';
    failureRiskPct = 12.5;
    winterRangeRetentionPct = 48;
    usedMarketValuationFactor = 0.68;
    usedMarketValuationText = '-25% ~ -40% 심각한 감가 페널티 발생';
    actionRecommendation =
      '보증 만료(8년/16만km) 전 긴급 서비스센터 점검을 입고하여 보증 수리 가능 여부를 확인하십시오.';
  } else if (sohPct < 90.0) {
    grade = 'GRADE_B';
    gradeLabel = 'Grade B (양호 / 정상 마모)';
    badgeColor = 'blue';
    failureRiskPct = 2.1;
    winterRangeRetentionPct = 62;
    usedMarketValuationFactor = 0.92;
    usedMarketValuationText = '-5% ~ -12% 완만한 시세 조정';
    actionRecommendation =
      '100kW 이상 초급속 충전 빈도를 줄이고 한여름 고온 100% 완충 방치를 피하십시오.';
  }

  // E. Replacement Cost Tier Matching
  const replacementCosts =
    Array.isArray(customReplacementCosts) && customReplacementCosts.length > 0
      ? customReplacementCosts
      : DEFAULT_REPLACEMENT_TIERS;
  const fallbackTier = replacementCosts[0] || DEFAULT_REPLACEMENT_TIERS[0];

  let targetTier = replacementCosts[1] || fallbackTier;
  if (packCapacityKwh <= 65) {
    targetTier = replacementCosts[0] || fallbackTier;
  } else if (packCapacityKwh >= 89) {
    targetTier =
      replacementCosts[2] ||
      replacementCosts[replacementCosts.length - 1] ||
      fallbackTier;
  }

  const defaultCosts = DEFAULT_REPLACEMENT_TIERS[1].costs;
  const tierCosts = targetTier?.costs ?? defaultCosts;

  return {
    chemistry: chemistryKey,
    chemistryName: chemProfile.name,
    years: safeYears,
    totalKm: safeMileage,
    equivalentFullCycles: Math.round(safeCycles),
    calendarLossPct: Math.round(safeQLossCal * 1000) / 10,
    cyclicLossPct: Math.round(safeQLossCyc * 1000) / 10,
    totalLossPct: Math.round(finiteQLossTotal * 1000) / 10,
    sohPct,
    grade,
    gradeLabel,
    badgeColor,
    failureRiskPct,
    winterRangeRetentionPct,
    usedMarketValuationFactor,
    usedMarketValuationText,
    actionRecommendation,
    replacementCostEstimate: {
      tierId: targetTier?.tier_id ?? 'TIER_77KWH',
      segmentName: targetTier?.segment_name ?? '준중형/중형 (65~84kWh)',
      newPackKrw: tierCosts.new_pack_krw,
      remanPackKrw: tierCosts.reman_pack_krw,
      laborCoolantKrw: tierCosts.labor_coolant_krw,
      totalNewInstalledKrw: tierCosts.total_new_installed_krw,
      totalRemanInstalledKrw: tierCosts.total_reman_installed_krw,
      estimatedCostKrw: tierCosts.total_new_installed_krw,
    },
  };
}

/**
 * Calculates statutory EV subsidy clawback based on the 2-year mandatory operation period.
 * Strict implementation of Clean Air Conservation Act Enforcement Rule [Annex 21-2].
 */
export function calculateSubsidyClawback(
  heldMonths: number,
  localSubsidyKrw: number,
  transferType: TransferType,
  nationalSubsidyKrw: number = 0,
  customTiers?: ClawbackTier[]
): ClawbackResult {
  const parsedMonths = typeof heldMonths === 'number'
    ? heldMonths
    : typeof heldMonths === 'string' && (heldMonths as string).trim() !== ''
    ? Number((heldMonths as string).trim())
    : NaN;
  const normalizedMonths = Number.isFinite(parsedMonths)
    ? Math.max(0, parsedMonths)
    : heldMonths === Infinity || parsedMonths === Infinity
    ? 24
    : 0;
  const parsedLocal = typeof localSubsidyKrw === 'number'
    ? localSubsidyKrw
    : typeof localSubsidyKrw === 'string' && (localSubsidyKrw as string).trim() !== ''
    ? Number((localSubsidyKrw as string).trim())
    : NaN;
  const safeLocalSubsidy = Number.isFinite(parsedLocal) ? Math.max(0, Math.min(100_000_000, parsedLocal)) : 0;
  const parsedNational = typeof nationalSubsidyKrw === 'number'
    ? nationalSubsidyKrw
    : typeof nationalSubsidyKrw === 'string' && (nationalSubsidyKrw as string).trim() !== ''
    ? Number((nationalSubsidyKrw as string).trim())
    : NaN;
  const safeNationalSubsidy = Number.isFinite(parsedNational)
    ? Math.max(0, Math.min(100_000_000, parsedNational))
    : 0;

  const tiers = Array.isArray(customTiers) && customTiers.length > 0
    ? customTiers
    : DEFAULT_CLAWBACK_TIERS;

  const defaultTier: ClawbackTier = {
    min_months: 24,
    max_months_exclusive: null,
    clawback_rate: 0.0,
    label_ko: '24개월 이상 (의무종료 / 회수 없음)',
  };

  if (!tiers || tiers.length === 0) {
    const isExempt = normalizedMonths >= 24 || transferType === 'intra';
    const remainingMonths = Math.max(0, 24 - normalizedMonths);
    return {
      heldMonths: normalizedMonths,
      tierLabel: defaultTier.label_ko,
      statutoryClawbackRate: 0,
      effectiveClawbackRate: 0,
      localSubsidyReceivedKrw: safeLocalSubsidy,
      nationalSubsidyReceivedKrw: safeNationalSubsidy,
      localClawbackKrw: 0,
      nationalClawbackKrw: 0,
      totalClawbackKrw: 0,
      transferType,
      isExempt,
      remainingMonthsOfObligation: Math.round(remainingMonths * 10) / 10,
      explanation: '환수 요율 정보가 없습니다.',
    };
  }

  let matchedTier: ClawbackTier = tiers[tiers.length - 1]; // default >= 24m (0%)
  for (const t of tiers) {
    if (t.max_months_exclusive === null) {
      if (normalizedMonths >= t.min_months) {
        matchedTier = t;
        break;
      }
    } else {
      if (
        normalizedMonths >= t.min_months &&
        normalizedMonths < t.max_months_exclusive
      ) {
        matchedTier = t;
        break;
      }
    }
  }

  const statutoryRate = matchedTier.clawback_rate;
  let effectiveRate = 0;
  let localClawbackKrw = 0;
  let nationalClawbackKrw = 0;
  let isExempt = false;
  let explanation = '';

  if (normalizedMonths >= 24) {
    isExempt = true;
    explanation =
      '24개월(2년) 법정 의무운행기간이 경과하여 보조금 환수 의무가 완전히 소멸되었습니다.';
  } else if (transferType === 'intra') {
    isExempt = true;
    effectiveRate = 0;
    localClawbackKrw = 0;
    nationalClawbackKrw = 0;
    explanation =
      '동일 지자체 관내 이전: 매수인이 지자체장 승인을 거쳐 잔여 의무운행기간을 자동 승계하므로 환수액이 면제됩니다 (0원).';
  } else if (transferType === 'inter') {
    isExempt = statutoryRate === 0;
    effectiveRate = statutoryRate;
    localClawbackKrw = Math.round(safeLocalSubsidy * effectiveRate);
    nationalClawbackKrw = 0; // 국비는 국내 운행 유지 시 환수 면제
    explanation = `타 지자체 관외 이전: 매도인이 수령한 지자체 지방비 보조금(${Math.round(
      safeLocalSubsidy
    ).toLocaleString()}원)에 대해 사용기간별 회수요율(${(statutoryRate * 100).toFixed(
      0
    )}%)이 적용되어 ${localClawbackKrw.toLocaleString()}원이 환수 고지됩니다 (국비는 면제).`;
  } else if (transferType === 'export') {
    isExempt = false;
    effectiveRate = statutoryRate;
    localClawbackKrw = Math.round(safeLocalSubsidy * effectiveRate);
    nationalClawbackKrw = Math.round(safeNationalSubsidy * effectiveRate);
    explanation = `해외 수출 말소: 국내 대기질 개선 취지 상실로 국비와 지방비를 합산한 총 보조금에 회수요율(${(
      statutoryRate * 100
    ).toFixed(0)}%)이 전액 적용됩니다.`;
  }

  if (!explanation) {
    explanation = '알 수 없거나 미지정된 이전 유형입니다.';
  }

  const totalClawbackKrw = localClawbackKrw + nationalClawbackKrw;
  const remainingMonths = Math.max(0, 24 - normalizedMonths);

  return {
    heldMonths: normalizedMonths,
    tierLabel: matchedTier.label_ko,
    statutoryClawbackRate: statutoryRate,
    effectiveClawbackRate: effectiveRate,
    localSubsidyReceivedKrw: safeLocalSubsidy,
    nationalSubsidyReceivedKrw: safeNationalSubsidy,
    localClawbackKrw,
    nationalClawbackKrw,
    totalClawbackKrw,
    transferType,
    isExempt,
    remainingMonthsOfObligation: Math.round(remainingMonths * 10) / 10,
    explanation,
  };
}

/**
 * Calculates comparative running costs between an EV and an equivalent ICE vehicle.
 * Analyzes blended charging rates (slow vs fast), gasoline fuel economy, automobile tax, and auxiliary savings.
 */
export function calculateTcoComparison(
  annualKm: number,
  years: number,
  evEfficiencyKmPerKwh: number = 5.2,
  slowChargingRatio: number = 0.7,
  iceDisplacementCc: number = 1998,
  customParams?: TcoParameters
): TcoResult {
  const params = customParams || DEFAULT_TCO_PARAMETERS;
  const fuelTariffs = params?.fuel_tariffs ?? DEFAULT_TCO_PARAMETERS.fuel_tariffs;
  const efficiencyBaselines = params?.efficiency_baselines ?? DEFAULT_TCO_PARAMETERS.efficiency_baselines;
  const taxParameters = params?.tax_parameters ?? DEFAULT_TCO_PARAMETERS.tax_parameters;
  const auxiliaryBenefits = params?.auxiliary_benefits ?? DEFAULT_TCO_PARAMETERS.auxiliary_benefits;

  const parsedSlowRatio = typeof slowChargingRatio === 'number'
    ? slowChargingRatio
    : typeof slowChargingRatio === 'string' && (slowChargingRatio as string).trim() !== ''
    ? Number((slowChargingRatio as string).trim())
    : NaN;
  const safeSlowRatio = Number.isFinite(parsedSlowRatio)
    ? clamp(parsedSlowRatio, 0.0, 1.0)
    : 0.7;
  const fastChargingRatio = 1.0 - safeSlowRatio;

  // 1. Blended electricity rate
  const blendedTariff =
    safeSlowRatio * fuelTariffs.ev_slow_charging_krw_per_kwh +
    fastChargingRatio * fuelTariffs.ev_fast_charging_krw_per_kwh;

  const parsedEvEff = typeof evEfficiencyKmPerKwh === 'number'
    ? evEfficiencyKmPerKwh
    : typeof evEfficiencyKmPerKwh === 'string' && (evEfficiencyKmPerKwh as string).trim() !== ''
    ? Number((evEfficiencyKmPerKwh as string).trim())
    : NaN;
  const safeEvEff =
    Number.isFinite(parsedEvEff) && parsedEvEff > 0
      ? parsedEvEff
      : 5.2;
  const iceFuelEconomy = efficiencyBaselines.ice_gasoline_economy_km_per_liter;
  const safeIceEff =
    Number.isFinite(iceFuelEconomy) && iceFuelEconomy > 0 ? iceFuelEconomy : 12.0;

  const evCostPerKm = blendedTariff / Math.max(1.0, safeEvEff);
  const iceCostPerKm =
    fuelTariffs.ice_gasoline_krw_per_liter / Math.max(1.0, safeIceEff);

  // 2. Base ICE Tax Calculation Function
  const calculateIceAnnualTax = (yearIndex: number): number => {
    const parsedCc = typeof iceDisplacementCc === 'number'
      ? iceDisplacementCc
      : typeof iceDisplacementCc === 'string' && (iceDisplacementCc as string).trim() !== ''
      ? Number((iceDisplacementCc as string).trim())
      : NaN;
    const safeCc =
      Number.isFinite(parsedCc) && parsedCc > 0
        ? parsedCc
        : 1998;
    let ratePerCc = 200;
    if (safeCc <= 1000) {
      ratePerCc = 80;
    } else if (safeCc <= 1600) {
      ratePerCc = 140;
    }
    const educationMultiplier = taxParameters.education_tax_multiplier ?? 0.3;
    const baseNominalTax =
      safeCc * ratePerCc * (1 + educationMultiplier);

    let discount = 0.0;
    const startYear = taxParameters.ice_age_discount_start_year ?? 3;
    const ratePerYear = taxParameters.ice_age_discount_rate_per_year ?? 0.05;
    const maxDiscount = taxParameters.ice_age_discount_max ?? 0.5;
    if (yearIndex >= startYear) {
      discount = Math.min(
        maxDiscount,
        (yearIndex - (startYear - 1)) * ratePerYear
      );
    }
    return Math.round(baseNominalTax * (1 - discount));
  };

  const evAnnualTax = taxParameters.ev_annual_tax_krw ?? 130000;

  const yearlyBreakdown: TcoYearBreakdown[] = [];
  let cumulativeSavings = 0;
  let evTotalFuel = 0;
  let iceTotalFuel = 0;
  let evTotalTax = 0;
  let iceTotalTax = 0;
  let tollTotalSavings = 0;
  let parkingTotalSavings = 0;
  let maintenanceTotalSavings = 0;

  const parsedAnnualKm = typeof annualKm === 'number'
    ? annualKm
    : typeof annualKm === 'string' && (annualKm as string).trim() !== ''
    ? Number((annualKm as string).trim())
    : NaN;
  const safeAnnualKm = Number.isFinite(parsedAnnualKm) && parsedAnnualKm >= 0 ? Math.min(10_000_000, parsedAnnualKm) : 15000;
  const parsedYears = typeof years === 'number'
    ? years
    : typeof years === 'string' && (years as string).trim() !== ''
    ? Number((years as string).trim())
    : NaN;
  const rawYears = Math.min(30, Number.isFinite(parsedYears) && parsedYears > 0 ? parsedYears : 1);
  const safeYears = Math.max(1, Math.round(rawYears));
  const fullYears = Math.floor(rawYears);
  const fractionalRemainder = Math.round((rawYears - fullYears) * 10000) / 10000;
  const totalLoops = Math.max(1, fractionalRemainder > 0.0001 ? fullYears + 1 : fullYears);

  let runningKm = 0;
  for (let y = 1; y <= totalLoops; y++) {
    const fraction =
      y <= fullYears ? 1.0 : fractionalRemainder > 0 ? fractionalRemainder : 1.0;
    const currentKm = Math.round(safeAnnualKm * fraction);
    runningKm += currentKm;

    const evFuel = Math.round(currentKm * evCostPerKm);
    const iceFuel = Math.round(currentKm * iceCostPerKm);
    const evTax = Math.round(evAnnualTax * fraction);
    const iceTax = Math.round(calculateIceAnnualTax(y) * fraction);
    const toll = Math.round(auxiliaryBenefits.annual_toll_savings_krw * fraction);
    const parking = Math.round(
      auxiliaryBenefits.annual_parking_savings_krw * fraction
    );
    const maintenance = Math.round(
      auxiliaryBenefits.maintenance_annual_savings_krw * fraction
    );

    const annualSavings =
      iceFuel - evFuel + (iceTax - evTax) + toll + parking + maintenance;
    cumulativeSavings += annualSavings;

    evTotalFuel += evFuel;
    iceTotalFuel += iceFuel;
    evTotalTax += evTax;
    iceTotalTax += iceTax;
    tollTotalSavings += toll;
    parkingTotalSavings += parking;
    maintenanceTotalSavings += maintenance;

    yearlyBreakdown.push({
      year: y,
      cumulativeKm: runningKm,
      evElectricityCostKrw: evFuel,
      iceFuelCostKrw: iceFuel,
      evAutomobileTaxKrw: evTax,
      iceAutomobileTaxKrw: iceTax,
      tollSavingsKrw: toll,
      parkingSavingsKrw: parking,
      maintenanceSavingsKrw: maintenance,
      annualNetSavingsKrw: annualSavings,
      cumulativeNetSavingsKrw: cumulativeSavings,
    });
  }

  return {
    annualKm: safeAnnualKm,
    years: safeYears,
    totalKm: runningKm,
    evEfficiencyKmPerKwh: safeEvEff,
    iceFuelEconomyKmPerLiter: safeIceEff,
    blendedElectricityTariffKrwPerKwh: Math.round(blendedTariff * 100) / 100,
    gasolinePriceKrwPerLiter: fuelTariffs.ice_gasoline_krw_per_liter,
    evFuelCostPerKm: Math.round(evCostPerKm * 100) / 100,
    iceFuelCostPerKm: Math.round(iceCostPerKm * 100) / 100,
    evTotalFuelCostKrw: evTotalFuel,
    iceTotalFuelCostKrw: iceTotalFuel,
    fuelSavingsKrw: iceTotalFuel - evTotalFuel,
    evTotalTaxKrw: evTotalTax,
    iceTotalTaxKrw: iceTotalTax,
    taxSavingsKrw: iceTotalTax - evTotalTax,
    tollSavingsKrw: tollTotalSavings,
    parkingSavingsKrw: parkingTotalSavings,
    maintenanceSavingsKrw: maintenanceTotalSavings,
    totalAuxiliarySavingsKrw:
      tollTotalSavings + parkingTotalSavings + maintenanceTotalSavings,
    totalCumulativeSavingsKrw: cumulativeSavings,
    yearlyBreakdown,
  };
}
