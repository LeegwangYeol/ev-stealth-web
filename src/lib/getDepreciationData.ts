import rawDepreciationData from '../data/ev_depreciation_data.json' with { type: 'json' };

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

export interface TcoParameters {
  fuel_tariffs: {
    ev_slow_charging_krw_per_kwh: number;
    ev_fast_charging_krw_per_kwh: number;
    ice_gasoline_krw_per_liter: number;
    ice_diesel_krw_per_liter: number;
  };
  efficiency_baselines: {
    ev_efficiency_km_per_kwh: number;
    ice_gasoline_economy_km_per_liter: number;
    ice_diesel_economy_km_per_liter: number;
  };
  tax_parameters: {
    ev_annual_tax_krw: number;
    ev_base_tax_krw: number;
    ev_education_tax_krw: number;
    ice_displacement_tiers: IceDisplacementTier[];
    education_tax_multiplier: number;
    ice_age_discount_start_year: number;
    ice_age_discount_rate_per_year: number;
    ice_age_discount_max: number;
  };
  auxiliary_benefits: {
    expressway_toll_discount_rate: number;
    annual_toll_savings_krw: number;
    public_parking_discount_rate: number;
    annual_parking_savings_krw: number;
    maintenance_annual_savings_krw: number;
  };
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
    facelift_hardware: {
      platform_800V_premium: number;
      platform_400V_penalty: number;
      major_facelift_compute_shift_penalty: number;
      description: string;
    };
    software_ota: Record<SoftwareOtaLevel, number>;
    mileage_sensitivity: {
      base_km_per_year: number;
      penalty_per_10000km_excess: number;
      bonus_per_10000km_deficit: number;
    };
  };
  chemistries: Record<BatteryChemistryType, BatteryChemistryProfile>;
  battery_replacement_costs: BatteryReplacementTier[];
  subsidy_clawback_schedule: SubsidyClawbackSchedule;
  tco_parameters: TcoParameters;
  models: EvModelDepreciation[];
}

// ==========================================
// 3. CALCULATION INPUT & RESULT INTERFACES
// ==========================================

export interface DepreciationCalculationInput {
  modelId: string;
  years: number; // e.g. 1.0 to 5.0
  mileageKm?: number; // defaults to 15,000 * years
  winterSeason?: boolean; // apply seasonal low temp penalty
  priceBasis?: PriceBasis; // 'msrp' | 'effective' (default 'msrp')
  customPurchasePriceKrw?: number; // override base purchase price
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
  chemistry?: BatteryChemistryType | string;
  modelId?: string;
  years: number;
  totalKm?: number;
  annualKm?: number;
  dcfcRatio?: number; // 0.0 to 1.0 (fraction of DC fast charging)
  storageSoc?: number; // 0.0 to 1.0 (average state of charge during parking)
  ambientTempC?: number; // Celsius ambient temperature
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
  sohPct: number; // 0.0 to 100.0%
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
  };
}

export interface ClawbackResult {
  heldMonths: number;
  tierLabel: string;
  statutoryClawbackRate: number; // e.g. 0.70 down to 0.00
  effectiveClawbackRate: number;
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
// 4. CORE DATA ACCESS FUNCTIONS
// ==========================================

export const DEFAULT_FALLBACK_DEPRECIATION_DATABASE: DepreciationDatabase = {
  metadata: {
    version: '1.0.0-fallback',
    generated_at: new Date().toISOString(),
    total_models: 0,
    brands_count: 0,
    currency: 'KRW',
    baseline_annual_mileage_km: 15000,
    sources: ['Fallback Default'],
  },
  market_context: {
    korean_market_status: '폴백 기본 데이터베이스',
    cheongna_fire_impact_summary: '',
    subsidy_clawback_rules: '',
  },
  adjustment_factors: {
    warranty_cliff: {
      safe_period_multiplier: 1.0,
      approaching_cliff_1_2_years_penalty: -0.06,
      expired_warranty_penalty: -0.14,
      description: '배터리 보증 만료에 따른 감가율 패널티',
    },
    battery_chemistry: {
      LFP: {
        cycle_life_bonus_yr3_5: 0.025,
        winter_seasonal_discount: -0.035,
        fire_safety_reputation_bonus: 0.03,
        description: 'LFP 배터리',
      },
      NCM_622: {
        cycle_life_bonus_yr3_5: 0.0,
        winter_seasonal_discount: -0.015,
        fire_safety_reputation_bonus: 0.01,
        description: 'NCM 622 배터리',
      },
      NCM_811: {
        cycle_life_bonus_yr3_5: -0.01,
        winter_seasonal_discount: -0.01,
        fire_safety_reputation_bonus: 0.0,
        description: 'NCM 811 배터리',
      },
      NCMA: {
        cycle_life_bonus_yr3_5: 0.015,
        winter_seasonal_discount: -0.01,
        fire_safety_reputation_bonus: 0.015,
        description: 'NCMA 배터리',
      },
      NCA: {
        cycle_life_bonus_yr3_5: -0.015,
        winter_seasonal_discount: -0.01,
        fire_safety_reputation_bonus: -0.005,
        description: 'NCA 배터리',
      },
    },
    facelift_hardware: {
      platform_800V_premium: 0.02,
      platform_400V_penalty: -0.02,
      major_facelift_compute_shift_penalty: -0.03,
      description: '하드웨어 아키텍처 및 페이스리프트 영향',
    },
    software_ota: {
      FULL_STACK: 0.03,
      ADVANCED_CCB: 0.015,
      INFOTAINMENT_ONLY: 0.0,
      BASIC: -0.02,
    },
    mileage_sensitivity: {
      base_km_per_year: 15000,
      penalty_per_10000km_excess: -0.018,
      bonus_per_10000km_deficit: 0.012,
    },
  },
  chemistries: {
    LFP: {
      id: 'LFP',
      name: 'LFP (리튬인산철 / Lithium Iron Phosphate)',
      cathode_structure: 'Olivine LiFePO4',
      nominal_cell_voltage_v: 3.2,
      voltage_cutoff_v: 2.5,
      energy_density_wh_kg: 160,
      cycle_life_to_80_soh: 3000,
      calendar_baseline_annual_loss_pct: 0.8,
      calendar_arrhenius_ea_j_mol: 52000,
      soc_stress_coefficient_beta: 0.4,
      calendar_time_exponent_z: 0.5,
      cyclic_exponent_w: 0.55,
      dod_exponent_u: 1.1,
      dcfc_acceleration_multiplier_max: 1.3,
      cold_charge_sensitivity_gamma: 0.7,
      thermal_runaway_temp_c: 270,
      ocv_profile_type: 'FLAT_PLATEAU',
      cell_balancing_requirement: 'WEEKLY_100PCT_CHARGE',
    },
    NCM_622: {
      id: 'NCM_622',
      name: 'NCM 622 (중밀도 삼원계)',
      cathode_structure: 'Layered LiNi0.6Co0.2Mn0.2O2',
      nominal_cell_voltage_v: 3.65,
      voltage_cutoff_v: 2.8,
      energy_density_wh_kg: 220,
      cycle_life_to_80_soh: 1800,
      calendar_baseline_annual_loss_pct: 1.2,
      calendar_arrhenius_ea_j_mol: 60000,
      soc_stress_coefficient_beta: 0.7,
      calendar_time_exponent_z: 0.5,
      cyclic_exponent_w: 0.58,
      dod_exponent_u: 1.3,
      dcfc_acceleration_multiplier_max: 1.6,
      cold_charge_sensitivity_gamma: 0.45,
      thermal_runaway_temp_c: 210,
      ocv_profile_type: 'SLOPING',
      cell_balancing_requirement: 'NORMAL_BMS_ROUTINE',
    },
    NCM_811: {
      id: 'NCM_811',
      name: 'NCM 811 (고에너지밀도 하이니켈)',
      cathode_structure: 'Layered LiNi0.8Co0.1Mn0.1O2',
      nominal_cell_voltage_v: 3.7,
      voltage_cutoff_v: 2.8,
      energy_density_wh_kg: 275,
      cycle_life_to_80_soh: 1400,
      calendar_baseline_annual_loss_pct: 1.5,
      calendar_arrhenius_ea_j_mol: 65000,
      soc_stress_coefficient_beta: 0.9,
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
  },
  battery_replacement_costs: [
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
  ],
  subsidy_clawback_schedule: {
    mandatory_operation_months: 24,
    legal_basis: '대기환경보전법 시행규칙 [별표 21의2]',
    tiers: [
      { min_months: 0, max_months_exclusive: 3, clawback_rate: 0.7, label_ko: '3개월 미만 (70% 회수)' },
      { min_months: 3, max_months_exclusive: 6, clawback_rate: 0.6, label_ko: '3개월 이상 6개월 미만 (60% 회수)' },
      { min_months: 6, max_months_exclusive: 12, clawback_rate: 0.5, label_ko: '6개월 이상 12개월 미만 (50% 회수)' },
      { min_months: 12, max_months_exclusive: 18, clawback_rate: 0.35, label_ko: '12개월 이상 18개월 미만 (35% 회수)' },
      { min_months: 18, max_months_exclusive: 24, clawback_rate: 0.2, label_ko: '18개월 이상 24개월 미만 (20% 회수)' },
      { min_months: 24, max_months_exclusive: null, clawback_rate: 0.0, label_ko: '24개월 이상 (의무종료 / 회수 없음)' },
    ],
    transfer_rules: {
      intra: { scenario: '관내 이전', clawback_local: false, clawback_national: false, description: '의무 승계로 환수 없음' },
      inter: { scenario: '관외 이전', clawback_local: true, clawback_national: false, description: '지방비만 잔여기간 비율 회수' },
      export: { scenario: '수출 말소', clawback_local: true, clawback_national: true, description: '국비/지방비 전액 회수율 적용' },
    },
  },
  tco_parameters: {
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
  },
  models: [
    {
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
    },
  ],
};

/**
 * Returns the complete EV depreciation database.
 */
export function getDepreciationDatabase(): DepreciationDatabase {
  try {
    if (
      rawDepreciationData &&
      typeof rawDepreciationData === 'object' &&
      Array.isArray((rawDepreciationData as Record<string, unknown>).models)
    ) {
      return rawDepreciationData as unknown as DepreciationDatabase;
    }
    return DEFAULT_FALLBACK_DEPRECIATION_DATABASE;
  } catch (err) {
    console.error('Failed to load depreciation database, using fallback:', err);
    return DEFAULT_FALLBACK_DEPRECIATION_DATABASE;
  }
}

const DATABASE: DepreciationDatabase = getDepreciationDatabase();

/**
 * Returns all 15 EV depreciation models.
 */
export function getAllModels(): EvModelDepreciation[] {
  return DATABASE.models;
}

/**
 * Finds a specific model by its unique ID.
 */
export function getModelById(id: string): EvModelDepreciation | undefined {
  if (!id || typeof id !== 'string') return undefined;
  return DATABASE.models.find(
    (m) => m.id.toLowerCase() === id.toLowerCase() || m.id === id
  );
}

/**
 * Returns unique brands with model counts.
 */
export function getAllBrands(): { id: string; name_ko: string; name_en: string; count: number }[] {
  const brandMap = new Map<string, { id: string; name_ko: string; name_en: string; count: number }>();
  for (const model of DATABASE.models) {
    const existing = brandMap.get(model.brand_id);
    if (existing) {
      existing.count += 1;
    } else {
      brandMap.set(model.brand_id, {
        id: model.brand_id,
        name_ko: model.brand_name_ko,
        name_en: model.brand_name_en,
        count: 1,
      });
    }
  }
  return Array.from(brandMap.values());
}

/**
 * Returns the battery replacement costs across capacity tiers.
 */
export function getBatteryReplacementCosts(): BatteryReplacementTier[] {
  return DATABASE.battery_replacement_costs;
}

/**
 * Returns the statutory subsidy clawback schedule tiers.
 */
export function getClawbackSchedule(): ClawbackTier[] {
  return DATABASE.subsidy_clawback_schedule.tiers;
}

/**
 * Returns TCO fuel tariffs, tax rates, and auxiliary savings parameters.
 */
export function getTcoParameters(): TcoParameters {
  return DATABASE.tco_parameters;
}

// ==========================================
// 5. HELPER MATH UTILITIES
// ==========================================

function clamp(val: number, min: number, max: number): number {
  if (!Number.isFinite(val)) return min;
  return Math.min(Math.max(val, min), max);
}

function normalizeChemistry(chem: string): BatteryChemistryType {
  const upper = chem.toUpperCase();
  if (upper.includes('LFP')) return 'LFP';
  if (upper.includes('622')) return 'NCM_622';
  if (upper.includes('NCMA')) return 'NCMA';
  if (upper.includes('NCA')) return 'NCA';
  return 'NCM_811';
}

function interpolateBaselineResidual(curve: DepreciationCurve, years: number, basis: PriceBasis): number {
  const key = basis === 'effective' ? 'residual_pct_effective' : 'residual_pct_msrp';

  if (!Number.isFinite(years) || years <= 0) return 100.0;
  if (years <= 1.0) {
    const y1 = curve?.year_1?.[key] ?? 100.0;
    return 100.0 - years * (100.0 - y1);
  }
  if (years <= 2.0) {
    const y1 = curve?.year_1?.[key] ?? 100.0;
    const y2 = curve?.year_2?.[key] ?? y1;
    return y1 - (years - 1.0) * (y1 - y2);
  }
  if (years <= 3.0) {
    const y2 = curve?.year_2?.[key] ?? 100.0;
    const y3 = curve?.year_3?.[key] ?? y2;
    return y2 - (years - 2.0) * (y2 - y3);
  }
  if (years <= 4.0) {
    const y3 = curve?.year_3?.[key] ?? 100.0;
    const y4 = curve?.year_4?.[key] ?? y3;
    return y3 - (years - 3.0) * (y3 - y4);
  }
  if (years <= 5.0) {
    const y4 = curve?.year_4?.[key] ?? 100.0;
    const y5 = curve?.year_5?.[key] ?? y4;
    return y4 - (years - 4.0) * (y4 - y5);
  }

  // Beyond 5 years: extrapolate with compounding 8% drop per additional year
  const y5 = curve?.year_5?.[key] ?? 50.0;
  const excessYears = years - 5.0;
  const extrapolated = y5 * Math.pow(0.92, excessYears);
  return Math.max(10.0, extrapolated);
}

// ==========================================
// 6. DEPRECIATION CALCULATOR
// ==========================================

/**
 * Calculates empirical depreciation and adjusted residual value for an EV.
 * Accounts for vehicle age, mileage, warranty cliff, chemistry, 800V architecture, and OTA status.
 */
export function calculateDepreciation(input: DepreciationCalculationInput): DepreciationCalculationResult {
  const rawYears = input.years;
  const years = Number.isFinite(rawYears) ? Math.max(0, rawYears) : 0;

  const rawMileage = input.mileageKm;
  const defaultMileage = years * DATABASE.metadata.baseline_annual_mileage_km;
  const mileageKm = Number.isFinite(rawMileage) ? Math.max(0, rawMileage!) : defaultMileage;

  const {
    modelId,
    winterSeason = false,
    priceBasis = 'msrp',
    customPurchasePriceKrw,
  } = input;

  const model = getModelById(modelId) || DATABASE.models[0];
  const baselineResidualPct = interpolateBaselineResidual(model.depreciation_curve, years, priceBasis);

  // 1. Mileage Adjustment
  const expectedMileage = years * DATABASE.metadata.baseline_annual_mileage_km;
  const deltaMileage = mileageKm - expectedMileage;
  let mileageAdjustment = 0;
  if (deltaMileage > 0) {
    mileageAdjustment = (deltaMileage / 10000) * DATABASE.adjustment_factors.mileage_sensitivity.penalty_per_10000km_excess;
  } else {
    const bonusRate = DATABASE.adjustment_factors.mileage_sensitivity.bonus_per_10000km_deficit;
    mileageAdjustment = Math.min(0.06, (Math.abs(deltaMileage) / 10000) * bonusRate);
  }

  // 2. Warranty Cliff
  const remainingWarrantyYears = model.warranty.years - years;
  const remainingWarrantyKm = model.warranty.km - mileageKm;
  const isExpired = remainingWarrantyYears <= 0 || remainingWarrantyKm <= 0;
  const isApproachingCliff = !isExpired && (remainingWarrantyYears <= 2 || remainingWarrantyKm <= 25000);

  let warrantyCliffPenalty = 0;
  if (isExpired) {
    warrantyCliffPenalty = DATABASE.adjustment_factors.warranty_cliff.expired_warranty_penalty;
  } else if (isApproachingCliff) {
    warrantyCliffPenalty = DATABASE.adjustment_factors.warranty_cliff.approaching_cliff_1_2_years_penalty;
  }

  // 3. Chemistry Aging Adjustment
  let batteryChemistryBonus = model.factor_weights.chemistry_aging;
  if (model.battery_specs.chemistry.includes('LFP')) {
    // Smooth monotonic ramp from year 2.0 to 3.0 to ensure discrete chemistry bonuses never invert the depreciation curve
    const lfpBonusRamp = clamp(years - 2.0, 0.0, 1.0);
    batteryChemistryBonus += 0.01 * lfpBonusRamp;
  }

  // 4. Winter Season Adjustment
  let winterAdjustment = 0;
  if (winterSeason) {
    if (model.battery_specs.chemistry.includes('LFP')) {
      winterAdjustment = -0.035;
    } else {
      winterAdjustment = -0.015;
    }
  }

  // 5. Hardware Architecture & OTA
  const architectureAdjustment = model.factor_weights.architecture_800v;
  const otaAdjustment = model.factor_weights.ota_maturity;

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

  const basePurchasePriceKrw =
    Number.isFinite(customPurchasePriceKrw) && (customPurchasePriceKrw as number) >= 0
      ? (customPurchasePriceKrw as number)
      : (priceBasis === 'effective' ? model.net_purchase_price_krw : model.msrp_krw_baseline);

  const estimatedResidualPriceKrw = Math.round((basePurchasePriceKrw * adjustedResidualPct) / 100);
  const depreciationAmountKrw = basePurchasePriceKrw - estimatedResidualPriceKrw;

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
    defenseTier: model.resale_defense_tier,
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
      remainingYears: Math.max(0, Math.round(remainingWarrantyYears * 10) / 10),
      remainingKm: Math.max(0, remainingWarrantyKm),
    },
    keyPros: model.key_pros_resale,
    keyCons: model.key_cons_resale,
  };
}

// ==========================================
// 7. ELECTROCHEMICAL BATTERY HEALTH SIMULATOR
// ==========================================

/**
 * Simulates electrochemical State of Health (SoH) and degradation kinetics.
 * Combines Arrhenius calendar aging and cyclic fatigue with DC fast charging strain.
 */
export function simulateBatteryHealth(params: BatterySimulationInput): BatteryHealthResult {
  const {
    chemistry: chemInput,
    modelId,
    years: rawYears,
    totalKm: inputTotalKm,
    annualKm = 15000,
    dcfcRatio = 0.25,
    storageSoc = 0.50,
    ambientTempC = 25.0,
    vehicleEfficiencyKmPerKwh = 5.2,
  } = params;

  const years = Math.max(0, Number.isFinite(rawYears) ? rawYears : 0);

  let model: EvModelDepreciation | undefined;
  if (modelId) {
    model = getModelById(modelId);
  }

  const chemistryKey: BatteryChemistryType = normalizeChemistry(
    chemInput || model?.battery_specs.chemistry || 'NCM_811'
  );

  const chemProfile = DATABASE.chemistries[chemistryKey] || DATABASE.chemistries.NCM_811;
  const packCapacityKwh = params.packCapacityKwh ?? model?.battery_specs.capacity_kwh ?? 77.4;
  const safeYears = Number.isFinite(years) && years > 0 ? years : 3;
  const safeAnnualKm = Number.isFinite(annualKm) && annualKm >= 0 ? annualKm : 15000;
  const rawMileage = Number.isFinite(inputTotalKm)
    ? (inputTotalKm as number)
    : safeYears * safeAnnualKm;
  const safeMileage = Math.max(0, rawMileage);

  // A. Calendar Aging via Arrhenius & SoC Kinetics
  const R_GAS = 8.314462;
  const T_REF_K = 298.15;
  const SOC_REF = 0.50;
  const safeTempC = Number.isFinite(ambientTempC) ? ambientTempC : 25.0;
  const safeStorageSoc = Number.isFinite(storageSoc) ? clamp(storageSoc, 0.0, 1.0) : 0.50;
  const safeDcfcRatio = Number.isFinite(dcfcRatio) ? clamp(dcfcRatio, 0.0, 1.0) : 0.25;
  const tempK = safeTempC + 273.15;

  const arrheniusFactor = Math.exp(
    (-chemProfile.calendar_arrhenius_ea_j_mol / R_GAS) * (1.0 / tempK - 1.0 / T_REF_K)
  );
  const socFactor = Math.exp(chemProfile.soc_stress_coefficient_beta * (safeStorageSoc - SOC_REF));
  const kCal = (chemProfile.calendar_baseline_annual_loss_pct / 100.0) * arrheniusFactor * socFactor;
  const qLossCal = kCal * Math.pow(Math.max(0.1, safeYears), chemProfile.calendar_time_exponent_z);

  // B. Cyclic Aging via Mechanical Strain & DCFC Factor
  const safeEfficiency =
    Number.isFinite(vehicleEfficiencyKmPerKwh) && (vehicleEfficiencyKmPerKwh as number) > 0
      ? (vehicleEfficiencyKmPerKwh as number)
      : 5.2;
  const safeCapacity =
    Number.isFinite(packCapacityKwh) && (packCapacityKwh as number) > 0
      ? (packCapacityKwh as number)
      : (model?.battery_specs.capacity_kwh ?? 77.4);

  const energyThroughputKwh = safeMileage / Math.max(1.0, safeEfficiency);
  const equivalentFullCycles = energyThroughputKwh / Math.max(10.0, safeCapacity);

  const fDod = Math.pow(0.85, chemProfile.dod_exponent_u);
  const fDcfc = 1.0 + (chemProfile.dcfc_acceleration_multiplier_max - 1.0) * safeDcfcRatio;

  let fTempCyc = 1.0;
  if (safeTempC < 0) {
    const coldFraction = Math.min(1.0, Math.abs(safeTempC) / 15.0);
    fTempCyc = 1.0 + chemProfile.cold_charge_sensitivity_gamma * coldFraction;
  }

  const baseCycles = chemProfile.cycle_life_to_80_soh;
  const qLossCyc =
    (0.20 / Math.pow(baseCycles, chemProfile.cyclic_exponent_w)) *
    fDod *
    fDcfc *
    fTempCyc *
    Math.pow(equivalentFullCycles, chemProfile.cyclic_exponent_w);

  // C. Sub-additive Coupling (p = 1.25)
  const P_COUPLING = 1.25;
  const qLossTotal = Math.pow(
    Math.pow(qLossCal, P_COUPLING) + Math.pow(qLossCyc, P_COUPLING),
    1.0 / P_COUPLING
  );

  const sohPct = clamp(Math.round((1.0 - qLossTotal) * 1000) / 10, 0.0, 100.0);

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
    usedMarketValuationFactor = 0.30;
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
  let targetTier = DATABASE.battery_replacement_costs[1]; // default midsize 77kWh
  if (packCapacityKwh <= 65) {
    targetTier = DATABASE.battery_replacement_costs[0]; // 50kWh
  } else if (packCapacityKwh >= 89) {
    targetTier = DATABASE.battery_replacement_costs[2]; // 100kWh
  }

  return {
    chemistry: chemistryKey,
    chemistryName: chemProfile.name,
    years: safeYears,
    totalKm: safeMileage,
    equivalentFullCycles: Math.round(equivalentFullCycles),
    calendarLossPct: Math.round(qLossCal * 1000) / 10,
    cyclicLossPct: Math.round(qLossCyc * 1000) / 10,
    totalLossPct: Math.round(qLossTotal * 1000) / 10,
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
      tierId: targetTier.tier_id,
      segmentName: targetTier.segment_name,
      newPackKrw: targetTier.costs.new_pack_krw,
      remanPackKrw: targetTier.costs.reman_pack_krw,
      laborCoolantKrw: targetTier.costs.labor_coolant_krw,
      totalNewInstalledKrw: targetTier.costs.total_new_installed_krw,
      totalRemanInstalledKrw: targetTier.costs.total_reman_installed_krw,
    },
  };
}

// ==========================================
// 8. STATUTORY SUBSIDY CLAWBACK CALCULATOR
// ==========================================

/**
 * Calculates statutory EV subsidy clawback based on the 2-year mandatory operation period.
 * Strict implementation of Clean Air Conservation Act Enforcement Rule [Annex 21-2].
 */
export function calculateSubsidyClawback(
  heldMonths: number,
  localSubsidyKrw: number,
  transferType: TransferType,
  nationalSubsidyKrw: number = 0
): ClawbackResult {
  const normalizedMonths = Number.isFinite(heldMonths) ? Math.max(0, heldMonths) : 0;
  const safeLocalSubsidy = Number.isFinite(localSubsidyKrw) ? Math.max(0, localSubsidyKrw) : 0;
  const safeNationalSubsidy = Number.isFinite(nationalSubsidyKrw) ? Math.max(0, nationalSubsidyKrw) : 0;
  const tiers = getDepreciationDatabase().subsidy_clawback_schedule?.tiers;

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
      if (normalizedMonths >= t.min_months && normalizedMonths < t.max_months_exclusive) {
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
    explanation = '24개월(2년) 법정 의무운행기간이 경과하여 보조금 환수 의무가 완전히 소멸되었습니다.';
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
    explanation = `타 지자체 관외 이전: 매도인이 수령한 지자체 지방비 보조금(${Math.round(safeLocalSubsidy).toLocaleString()}원)에 대해 사용기간별 회수요율(${(statutoryRate * 100).toFixed(0)}%)이 적용되어 ${localClawbackKrw.toLocaleString()}원이 환수 고지됩니다 (국비는 면제).`;
  } else if (transferType === 'export') {
    isExempt = false;
    effectiveRate = statutoryRate;
    localClawbackKrw = Math.round(safeLocalSubsidy * effectiveRate);
    nationalClawbackKrw = Math.round(safeNationalSubsidy * effectiveRate);
    explanation = `해외 수출 말소: 국내 대기질 개선 취지 상실로 국비와 지방비를 합산한 총 보조금에 회수요율(${(statutoryRate * 100).toFixed(0)}%)이 전액 적용됩니다.`;
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

// ==========================================
// 9. TOTAL COST OF OWNERSHIP (TCO) CALCULATOR
// ==========================================

/**
 * Calculates comparative running costs between an EV and an equivalent ICE vehicle.
 * Analyzes blended charging rates (slow vs fast), gasoline fuel economy, automobile tax, and auxiliary savings.
 */
export function calculateTcoComparison(
  annualKm: number,
  years: number,
  evEfficiencyKmPerKwh: number = 5.2,
  slowChargingRatio: number = 0.70,
  iceDisplacementCc: number = 1998
): TcoResult {
  const params = DATABASE.tco_parameters;
  const safeSlowRatio = Number.isFinite(slowChargingRatio) ? clamp(slowChargingRatio, 0.0, 1.0) : 0.70;
  const fastChargingRatio = 1.0 - safeSlowRatio;

  // 1. Blended electricity rate
  const blendedTariff =
    safeSlowRatio * params.fuel_tariffs.ev_slow_charging_krw_per_kwh +
    fastChargingRatio * params.fuel_tariffs.ev_fast_charging_krw_per_kwh;

  const safeEvEff =
    Number.isFinite(evEfficiencyKmPerKwh) && evEfficiencyKmPerKwh > 0
      ? evEfficiencyKmPerKwh
      : 5.2;
  const iceFuelEconomy = params.efficiency_baselines.ice_gasoline_economy_km_per_liter;
  const safeIceEff =
    Number.isFinite(iceFuelEconomy) && iceFuelEconomy > 0
      ? iceFuelEconomy
      : 12.0;

  const evCostPerKm = blendedTariff / Math.max(1.0, safeEvEff);
  const iceCostPerKm = params.fuel_tariffs.ice_gasoline_krw_per_liter / Math.max(1.0, safeIceEff);

  // 2. Base ICE Tax Calculation Function
  const calculateIceAnnualTax = (yearIndex: number): number => {
    const safeCc = Number.isFinite(iceDisplacementCc) && iceDisplacementCc > 0 ? iceDisplacementCc : 1998;
    let ratePerCc = 200;
    if (safeCc <= 1000) {
      ratePerCc = 80;
    } else if (safeCc <= 1600) {
      ratePerCc = 140;
    }
    const baseNominalTax = safeCc * ratePerCc * (1 + params.tax_parameters.education_tax_multiplier);

    let discount = 0.0;
    if (yearIndex >= params.tax_parameters.ice_age_discount_start_year) {
      discount = Math.min(
        params.tax_parameters.ice_age_discount_max,
        (yearIndex - (params.tax_parameters.ice_age_discount_start_year - 1)) *
          params.tax_parameters.ice_age_discount_rate_per_year
      );
    }
    return Math.round(baseNominalTax * (1 - discount));
  };

  const evAnnualTax = params.tax_parameters.ev_annual_tax_krw;

  const yearlyBreakdown: TcoYearBreakdown[] = [];
  let cumulativeSavings = 0;
  let evTotalFuel = 0;
  let iceTotalFuel = 0;
  let evTotalTax = 0;
  let iceTotalTax = 0;
  let tollTotalSavings = 0;
  let parkingTotalSavings = 0;
  let maintenanceTotalSavings = 0;

  const safeAnnualKm = Number.isFinite(annualKm) && annualKm >= 0 ? annualKm : 15000;
  const rawYears = Number.isFinite(years) && years > 0 ? years : 1;
  const safeYears = Math.max(1, Math.round(rawYears));
  const fullYears = Math.floor(rawYears);
  const fractionalRemainder = Math.round((rawYears - fullYears) * 10000) / 10000;
  const totalLoops = Math.max(1, fractionalRemainder > 0.0001 ? fullYears + 1 : fullYears);

  let runningKm = 0;
  for (let y = 1; y <= totalLoops; y++) {
    const fraction = y <= fullYears ? 1.0 : (fractionalRemainder > 0 ? fractionalRemainder : 1.0);
    const currentKm = Math.round(safeAnnualKm * fraction);
    runningKm += currentKm;

    const evFuel = Math.round(currentKm * evCostPerKm);
    const iceFuel = Math.round(currentKm * iceCostPerKm);
    const evTax = Math.round(evAnnualTax * fraction);
    const iceTax = Math.round(calculateIceAnnualTax(y) * fraction);
    const toll = Math.round(params.auxiliary_benefits.annual_toll_savings_krw * fraction);
    const parking = Math.round(params.auxiliary_benefits.annual_parking_savings_krw * fraction);
    const maintenance = Math.round(params.auxiliary_benefits.maintenance_annual_savings_krw * fraction);

    const annualSavings = (iceFuel - evFuel) + (iceTax - evTax) + toll + parking + maintenance;
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
    gasolinePriceKrwPerLiter: params.fuel_tariffs.ice_gasoline_krw_per_liter,
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
    totalAuxiliarySavingsKrw: tollTotalSavings + parkingTotalSavings + maintenanceTotalSavings,
    totalCumulativeSavingsKrw: cumulativeSavings,
    yearlyBreakdown,
  };
}
