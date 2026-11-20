import rawDepreciationData from '../data/ev_depreciation_data.json' with { type: 'json' };
import type {
  BatteryChemistryType,
  ResaleDefenseTier,
  SoftwareOtaLevel,
  BatteryRiskGrade,
  TransferType,
  PriceBasis,
  DepreciationCurvePoint,
  DepreciationCurve,
  BatterySpecs,
  WarrantyInfo,
  FactorWeights,
  EvModelDepreciation,
  BatteryReplacementTierCosts,
  BatteryReplacementTier,
  BatteryChemistryProfile,
  WarrantyCliffAdjustment,
  BatteryChemistryAdjustment,
  FaceliftHardwareAdjustment,
  MileageSensitivityAdjustment,
  AdjustmentFactors,
  PartialAdjustmentFactors,
  ClawbackTier,
  SubsidyTransferRule,
  SubsidyClawbackSchedule,
  IceDisplacementTier,
  TcoFuelTariffs,
  TcoTaxParameters,
  TcoAuxiliaryBenefits,
  TcoEfficiencyBaselines,
  TcoParameters,
  PartialTcoParameters,
  DepreciationDatabase,
  DepreciationCalculationInput,
  FactorAdjustmentsBreakdown,
  WarrantyStatus,
  DepreciationCalculationResult,
  BatterySimulationInput,
  BatteryHealthResult,
  ClawbackResult,
  TcoYearBreakdown,
  TcoResult,
  CalculateDepreciationOptions,
} from '../types/depreciation.ts';

export type {
  BatteryChemistryType,
  ResaleDefenseTier,
  SoftwareOtaLevel,
  BatteryRiskGrade,
  TransferType,
  PriceBasis,
  DepreciationCurvePoint,
  DepreciationCurve,
  BatterySpecs,
  WarrantyInfo,
  FactorWeights,
  EvModelDepreciation,
  BatteryReplacementTierCosts,
  BatteryReplacementTier,
  BatteryChemistryProfile,
  WarrantyCliffAdjustment,
  BatteryChemistryAdjustment,
  FaceliftHardwareAdjustment,
  MileageSensitivityAdjustment,
  AdjustmentFactors,
  PartialAdjustmentFactors,
  ClawbackTier,
  SubsidyTransferRule,
  SubsidyClawbackSchedule,
  IceDisplacementTier,
  TcoFuelTariffs,
  TcoTaxParameters,
  TcoAuxiliaryBenefits,
  TcoEfficiencyBaselines,
  TcoParameters,
  PartialTcoParameters,
  DepreciationDatabase,
  DepreciationCalculationInput,
  FactorAdjustmentsBreakdown,
  WarrantyStatus,
  DepreciationCalculationResult,
  BatterySimulationInput,
  BatteryHealthResult,
  ClawbackResult,
  TcoYearBreakdown,
  TcoResult,
  CalculateDepreciationOptions,
};

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
      description: '배터리 보증 만료에 따른 감가율 페널티',
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
      max_mileage_discount_cap: -0.15,
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

function normalizeZero(val: number): number {
  return val === 0 ? 0 : val;
}

function roundTo(val: number, decimals: number = 0): number {
  if (!Number.isFinite(val)) return 0;
  const factor = decimals === 0 ? 1 : decimals === 1 ? 10 : decimals === 2 ? 100 : Math.pow(10, decimals);
  const scaled = val * factor;
  if (!Number.isFinite(scaled)) return normalizeZero(val);
  return normalizeZero(Math.round(scaled) / factor);
}

function isPlainRecord(val: unknown): val is Record<string, unknown> {
  return val !== null && typeof val === 'object' && !Array.isArray(val);
}

let cachedDatabase: DepreciationDatabase | null = null;

/**
 * Returns the complete EV depreciation database.
 */
export function getDepreciationDatabase(): DepreciationDatabase {
  if (cachedDatabase) return cachedDatabase;
  try {
    if (
      isPlainRecord(rawDepreciationData) &&
      Array.isArray(rawDepreciationData.models) &&
      rawDepreciationData.models.length > 0
    ) {
      const fb = DEFAULT_FALLBACK_DEPRECIATION_DATABASE;
      const hasAllSections =
        isPlainRecord(rawDepreciationData.metadata) &&
        isPlainRecord(rawDepreciationData.market_context) &&
        isPlainRecord(rawDepreciationData.adjustment_factors) &&
        isPlainRecord(rawDepreciationData.chemistries) &&
        Array.isArray(rawDepreciationData.battery_replacement_costs) &&
        rawDepreciationData.battery_replacement_costs.length > 0 &&
        isPlainRecord(rawDepreciationData.subsidy_clawback_schedule) &&
        Array.isArray(rawDepreciationData.subsidy_clawback_schedule.tiers) &&
        rawDepreciationData.subsidy_clawback_schedule.tiers.length > 0 &&
        isPlainRecord(rawDepreciationData.tco_parameters) &&
        isPlainRecord(rawDepreciationData.tco_parameters.fuel_tariffs) &&
        isPlainRecord(rawDepreciationData.tco_parameters.efficiency_baselines) &&
        isPlainRecord(rawDepreciationData.tco_parameters.tax_parameters) &&
        isPlainRecord(rawDepreciationData.tco_parameters.auxiliary_benefits);

      if (hasAllSections) {
        cachedDatabase = rawDepreciationData as unknown as DepreciationDatabase;
        return cachedDatabase;
      }

      const rawAdjFactors: Record<string, unknown> = isPlainRecord(rawDepreciationData.adjustment_factors)
        ? rawDepreciationData.adjustment_factors
        : {};
      const rawTco: Record<string, unknown> = isPlainRecord(rawDepreciationData.tco_parameters)
        ? rawDepreciationData.tco_parameters
        : {};
      const rawClawback: Record<string, unknown> = isPlainRecord(rawDepreciationData.subsidy_clawback_schedule)
        ? rawDepreciationData.subsidy_clawback_schedule
        : {};

      cachedDatabase = {
        metadata: isPlainRecord(rawDepreciationData.metadata)
          ? ({ ...fb.metadata, ...rawDepreciationData.metadata } as unknown as DepreciationDatabase['metadata'])
          : fb.metadata,
        market_context: isPlainRecord(rawDepreciationData.market_context)
          ? ({ ...fb.market_context, ...rawDepreciationData.market_context } as unknown as DepreciationDatabase['market_context'])
          : fb.market_context,
        adjustment_factors: {
          ...fb.adjustment_factors,
          ...(rawAdjFactors as Partial<AdjustmentFactors>),
          warranty_cliff: isPlainRecord(rawAdjFactors.warranty_cliff)
            ? ({ ...fb.adjustment_factors.warranty_cliff, ...rawAdjFactors.warranty_cliff } as WarrantyCliffAdjustment)
            : fb.adjustment_factors.warranty_cliff,
          battery_chemistry: isPlainRecord(rawAdjFactors.battery_chemistry)
            ? ({ ...fb.adjustment_factors.battery_chemistry, ...rawAdjFactors.battery_chemistry } as AdjustmentFactors['battery_chemistry'])
            : fb.adjustment_factors.battery_chemistry,
          mileage_sensitivity: isPlainRecord(rawAdjFactors.mileage_sensitivity)
            ? ({ ...fb.adjustment_factors.mileage_sensitivity, ...rawAdjFactors.mileage_sensitivity } as MileageSensitivityAdjustment)
            : fb.adjustment_factors.mileage_sensitivity,
        },
        chemistries: isPlainRecord(rawDepreciationData.chemistries)
          ? ({ ...fb.chemistries, ...rawDepreciationData.chemistries } as unknown as DepreciationDatabase['chemistries'])
          : fb.chemistries,
        battery_replacement_costs:
          Array.isArray(rawDepreciationData.battery_replacement_costs) &&
          rawDepreciationData.battery_replacement_costs.length > 0
            ? (rawDepreciationData.battery_replacement_costs as unknown as BatteryReplacementTier[])
            : fb.battery_replacement_costs,
        subsidy_clawback_schedule: {
          ...fb.subsidy_clawback_schedule,
          ...(rawClawback as Partial<SubsidyClawbackSchedule>),
          tiers:
            Array.isArray(rawClawback.tiers) && rawClawback.tiers.length > 0
              ? (rawClawback.tiers as unknown as ClawbackTier[])
              : fb.subsidy_clawback_schedule.tiers,
        },
        tco_parameters: {
          fuel_tariffs: isPlainRecord(rawTco.fuel_tariffs)
            ? ({ ...fb.tco_parameters.fuel_tariffs, ...rawTco.fuel_tariffs } as TcoFuelTariffs)
            : fb.tco_parameters.fuel_tariffs,
          efficiency_baselines: isPlainRecord(rawTco.efficiency_baselines)
            ? ({ ...fb.tco_parameters.efficiency_baselines, ...rawTco.efficiency_baselines } as TcoEfficiencyBaselines)
            : fb.tco_parameters.efficiency_baselines,
          tax_parameters: isPlainRecord(rawTco.tax_parameters)
            ? ({ ...fb.tco_parameters.tax_parameters, ...rawTco.tax_parameters } as TcoTaxParameters)
            : fb.tco_parameters.tax_parameters,
          auxiliary_benefits: isPlainRecord(rawTco.auxiliary_benefits)
            ? ({ ...fb.tco_parameters.auxiliary_benefits, ...rawTco.auxiliary_benefits } as TcoAuxiliaryBenefits)
            : fb.tco_parameters.auxiliary_benefits,
        },
        models: rawDepreciationData.models as unknown as EvModelDepreciation[],
      };
      return cachedDatabase;
    }
    cachedDatabase = DEFAULT_FALLBACK_DEPRECIATION_DATABASE;
    return cachedDatabase;
  } catch (err) {
    console.error('Failed to load depreciation database, using fallback:', err);
    cachedDatabase = DEFAULT_FALLBACK_DEPRECIATION_DATABASE;
    return cachedDatabase;
  }
}

const DATABASE: DepreciationDatabase = getDepreciationDatabase();

interface ModelIndex {
  exact: Map<string, EvModelDepreciation>;
  normalized: Map<string, EvModelDepreciation>;
  length: number;
}

const modelIndexCache = new WeakMap<readonly EvModelDepreciation[], ModelIndex>();

function getModelIndex(models: readonly EvModelDepreciation[]): ModelIndex {
  const cached = modelIndexCache.get(models);
  if (cached && cached.length === models.length) return cached;

  const exact = new Map<string, EvModelDepreciation>();
  const normalized = new Map<string, EvModelDepreciation>();
  for (const m of models) {
    if (!isPlainRecord(m) || typeof m.id !== 'string') continue;
    const lower = m.id.toLowerCase().trim();
    if (!lower) continue;
    if (!exact.has(lower)) exact.set(lower, m as unknown as EvModelDepreciation);
    const norm = lower.replace(/[-_\s]/g, '');
    if (norm && !normalized.has(norm)) normalized.set(norm, m as unknown as EvModelDepreciation);
  }
  const index: ModelIndex = { exact, normalized, length: models.length };
  modelIndexCache.set(models, index);
  return index;
}

/**
 * Returns all EV depreciation models.
 */
export function getAllModels(): EvModelDepreciation[] {
  return Array.isArray(DATABASE?.models) && DATABASE.models.length > 0
    ? DATABASE.models
    : DEFAULT_FALLBACK_DEPRECIATION_DATABASE.models;
}

/**
 * Finds a specific model by its unique ID.
 */
export function getModelById(id: string): EvModelDepreciation | undefined {
  if (!id || typeof id !== 'string') return undefined;
  const models = getAllModels();
  return (
    findModelById(models, id) ||
    findModelById(DEFAULT_FALLBACK_DEPRECIATION_DATABASE.models, id)
  );
}

/**
 * Returns unique brands with model counts.
 */
export function getAllBrands(): { id: string; name_ko: string; name_en: string; count: number }[] {
  const brandMap = new Map<string, { id: string; name_ko: string; name_en: string; count: number }>();
  const models = getAllModels();
  for (const model of models) {
    if (!isPlainRecord(model) || typeof model.brand_id !== 'string' || !model.brand_id.trim()) continue;
    const existing = brandMap.get(model.brand_id);
    if (existing) {
      existing.count += 1;
    } else {
      brandMap.set(model.brand_id, {
        id: model.brand_id,
        name_ko: typeof model.brand_name_ko === 'string' && model.brand_name_ko ? model.brand_name_ko : model.brand_id,
        name_en: typeof model.brand_name_en === 'string' && model.brand_name_en ? model.brand_name_en : model.brand_id,
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
  return Array.isArray(DATABASE?.battery_replacement_costs) && DATABASE.battery_replacement_costs.length > 0
    ? DATABASE.battery_replacement_costs
    : DEFAULT_FALLBACK_DEPRECIATION_DATABASE.battery_replacement_costs;
}

/**
 * Returns the statutory subsidy clawback schedule tiers.
 */
export function getClawbackSchedule(): ClawbackTier[] {
  return Array.isArray(DATABASE?.subsidy_clawback_schedule?.tiers) && DATABASE.subsidy_clawback_schedule.tiers.length > 0
    ? DATABASE.subsidy_clawback_schedule.tiers
    : DEFAULT_FALLBACK_DEPRECIATION_DATABASE.subsidy_clawback_schedule.tiers;
}

/**
 * Returns TCO fuel tariffs, tax rates, and auxiliary savings parameters.
 */
export function getTcoParameters(): TcoParameters {
  return isPlainRecord(DATABASE?.tco_parameters)
    ? DATABASE.tco_parameters
    : DEFAULT_FALLBACK_DEPRECIATION_DATABASE.tco_parameters;
}

// ==========================================
// 5. HELPER MATH UTILITIES
// ==========================================

export function clamp(val: number, min: number, max: number): number {
  const safeMin = Number.isFinite(min) ? normalizeZero(min) : 0;
  const safeMax = Number.isFinite(max) ? normalizeZero(max) : safeMin;
  const trueMin = normalizeZero(Math.min(safeMin, safeMax));
  const trueMax = normalizeZero(Math.max(safeMin, safeMax));
  if (val === Infinity) return trueMax;
  if (!Number.isFinite(val)) return trueMin;
  return normalizeZero(Math.min(Math.max(val, trueMin), trueMax));
}

function finiteOr(val: unknown, fallback: number): number {
  return typeof val === 'number' && Number.isFinite(val) ? normalizeZero(val) : normalizeZero(fallback);
}

function finiteNonNegOr(val: unknown, fallback: number): number {
  return typeof val === 'number' && Number.isFinite(val) && val >= 0
    ? normalizeZero(val)
    : normalizeZero(fallback);
}

function finitePosOr(val: unknown, fallback: number): number {
  return typeof val === 'number' && Number.isFinite(val) && val > 0 ? val : normalizeZero(fallback);
}

function parseNumericInput(val: unknown): number {
  if (typeof val === 'number') return normalizeZero(val);
  if (typeof val === 'string') {
    const trimmed = val.trim();
    if (trimmed !== '') return normalizeZero(Number(trimmed));
  }
  return NaN;
}

const VALID_DEFENSE_TIERS: ReadonlySet<string> = new Set([
  'S', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'D',
]);

function sanitizeDefenseTier(tier: unknown): ResaleDefenseTier {
  return typeof tier === 'string' && VALID_DEFENSE_TIERS.has(tier)
    ? (tier as ResaleDefenseTier)
    : 'B';
}

function findModelById(models: readonly EvModelDepreciation[] | undefined, modelId: unknown): EvModelDepreciation | undefined {
  if (!Array.isArray(models) || models.length === 0 || typeof modelId !== 'string') return undefined;
  const searchId = modelId.toLowerCase().trim();
  if (!searchId) return undefined;
  const { exact, normalized } = getModelIndex(models);
  const direct = exact.get(searchId);
  if (direct) return direct;
  const searchNorm = searchId.replace(/[-_\s]/g, '');
  return searchNorm ? normalized.get(searchNorm) : undefined;
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

export function interpolateBaselineResidual(curve: DepreciationCurve, years: number, basis: PriceBasis): number {
  const key = basis === 'effective' ? 'residual_pct_effective' : 'residual_pct_msrp';

  const numYears = parseNumericInput(years);
  if (numYears !== Infinity && (!Number.isFinite(numYears) || numYears <= 0)) return 100.0;

  const getPoint = (val: unknown, fallback: number): number =>
    typeof val === 'number' && Number.isFinite(val) ? clamp(val, 0.0, 100.0) : fallback;

  const y1 = getPoint(curve?.year_1?.[key], 100.0);
  const y2 = getPoint(curve?.year_2?.[key], y1);
  const y3 = getPoint(curve?.year_3?.[key], y2);
  const y4 = getPoint(curve?.year_4?.[key], y3);
  const y5 = getPoint(curve?.year_5?.[key], y4 !== 100.0 ? y4 : 50.0);

  if (numYears === Infinity) {
    return clamp(Math.min(10.0, y5), 0.0, 100.0);
  }

  if (numYears <= 1.0) {
    return clamp(100.0 - numYears * (100.0 - y1), 0.0, 100.0);
  }
  if (numYears <= 2.0) {
    return clamp(y1 - (numYears - 1.0) * (y1 - y2), 0.0, 100.0);
  }
  if (numYears <= 3.0) {
    return clamp(y2 - (numYears - 2.0) * (y2 - y3), 0.0, 100.0);
  }
  if (numYears <= 4.0) {
    return clamp(y3 - (numYears - 3.0) * (y3 - y4), 0.0, 100.0);
  }
  if (numYears <= 5.0) {
    return clamp(y4 - (numYears - 4.0) * (y4 - y5), 0.0, 100.0);
  }

  // Beyond 5 years: extrapolate with compounding 8% drop per additional year
  const excessYears = numYears - 5.0;
  const floor = Math.min(10.0, y5);
  const extrapolated = y5 * Math.pow(0.92, excessYears);
  const safeExtrapolated = Number.isFinite(extrapolated) ? Math.max(floor, extrapolated) : floor;
  return clamp(safeExtrapolated, 0.0, 100.0);
}

// ==========================================
// 6. DEPRECIATION CALCULATOR
// ==========================================

/**
 * Calculates empirical depreciation and adjusted residual value for an EV.
 * Accounts for vehicle age, mileage, warranty cliff, chemistry, 800V architecture, and OTA status.
 */
export function calculateDepreciation(
  input: DepreciationCalculationInput,
  options?: CalculateDepreciationOptions
): DepreciationCalculationResult {
  const safeInput = isPlainRecord(input) ? (input as unknown as DepreciationCalculationInput) : ({} as DepreciationCalculationInput);
  const safeOptions = isPlainRecord(options) ? (options as unknown as CalculateDepreciationOptions) : undefined;

  const rawYearsInput =
    safeInput.years !== undefined && safeInput.years !== null ? safeInput.years : safeInput.heldYears;
  const parsedYears = parseNumericInput(rawYearsInput);
  const years = Number.isFinite(parsedYears) ? clamp(parsedYears, 0, 100) : 0;

  const rawFactors = isPlainRecord(safeOptions?.adjustmentFactors)
    ? safeOptions.adjustmentFactors
    : undefined;
  const rawMileageSens = isPlainRecord(rawFactors?.mileage_sensitivity)
    ? rawFactors.mileage_sensitivity
    : undefined;
  const rawWarrantyCliff = isPlainRecord(rawFactors?.warranty_cliff)
    ? rawFactors.warranty_cliff
    : undefined;

  const defaultBaselineAnnualMileage = finitePosOr(
    DATABASE?.metadata?.baseline_annual_mileage_km,
    15000
  );
  const baselineAnnualMileage = finitePosOr(
    safeOptions?.baselineAnnualMileageKm ?? safeOptions?.annualAverageKm,
    finitePosOr(
      rawMileageSens?.baseline_annual_km,
      finitePosOr(
        rawMileageSens?.base_km_per_year,
        defaultBaselineAnnualMileage
      )
    )
  );
  const rawMileageInput =
    safeInput.mileageKm !== undefined && safeInput.mileageKm !== null ? safeInput.mileageKm : safeInput.totalKm;
  const parsedMileage = parseNumericInput(rawMileageInput);
  const defaultMileage = normalizeZero(years * baselineAnnualMileage);
  const mileageKm = Number.isFinite(parsedMileage)
    ? clamp(parsedMileage, 0, 10_000_000)
    : defaultMileage;

  const {
    modelId,
    winterSeason = false,
  } = safeInput;
  const priceBasis: PriceBasis = safeInput.priceBasis === 'effective' ? 'effective' : 'msrp';

  const explicitModel = isPlainRecord(safeInput.model)
    ? (safeInput.model as EvModelDepreciation)
    : isPlainRecord(safeOptions?.model)
    ? (safeOptions.model as EvModelDepreciation)
    : undefined;
  const model =
    explicitModel ||
    (safeOptions?.models && modelId ? findModelById(safeOptions.models, modelId) : undefined) ||
    (modelId ? getModelById(modelId) : undefined) ||
    DATABASE?.models?.[0] ||
    DEFAULT_FALLBACK_DEPRECIATION_DATABASE.models[0];
  const rawBaselineResidualPct = interpolateBaselineResidual(model.depreciation_curve, years, priceBasis);
  const baselineResidualPct = Number.isFinite(rawBaselineResidualPct)
    ? clamp(rawBaselineResidualPct, 0.0, 100.0)
    : 100.0;

  // 1. Mileage Adjustment
  const defaultAdjFactors = DEFAULT_FALLBACK_DEPRECIATION_DATABASE.adjustment_factors;
  const adjFactors = isPlainRecord(DATABASE?.adjustment_factors)
    ? DATABASE.adjustment_factors
    : defaultAdjFactors;
  const mileageSens = isPlainRecord(adjFactors?.mileage_sensitivity)
    ? adjFactors.mileage_sensitivity
    : defaultAdjFactors.mileage_sensitivity;
  const warrantyCliff = isPlainRecord(adjFactors?.warranty_cliff)
    ? adjFactors.warranty_cliff
    : defaultAdjFactors.warranty_cliff;

  const excessPenaltyRate = clamp(
    finiteOr(
      rawMileageSens?.penalty_per_10000km_excess,
      finiteOr(mileageSens?.penalty_per_10000km_excess, -0.018)
    ),
    -1.0,
    0.0
  );
  const deficitBonusRate = clamp(
    finiteOr(
      rawMileageSens?.bonus_per_10000km_deficit,
      finiteOr(mileageSens?.bonus_per_10000km_deficit, 0.012)
    ),
    0.0,
    1.0
  );
  const maxDiscountCap = clamp(
    finiteOr(
      rawMileageSens?.max_mileage_discount_cap,
      finiteOr(mileageSens?.max_mileage_discount_cap, -0.15)
    ),
    -1.0,
    0.0
  );
  const approachingCliffPenalty = clamp(
    finiteOr(
      rawWarrantyCliff?.approaching_cliff_1_2_years_penalty,
      finiteOr(warrantyCliff?.approaching_cliff_1_2_years_penalty, -0.06)
    ),
    -1.0,
    0.0
  );
  const expiredWarrantyPenalty = clamp(
    finiteOr(
      rawWarrantyCliff?.expired_warranty_penalty,
      finiteOr(warrantyCliff?.expired_warranty_penalty, -0.14)
    ),
    -1.0,
    0.0
  );

  const expectedMileage = years * baselineAnnualMileage;
  const deltaMileage = mileageKm - expectedMileage;
  let mileageAdjustment = 0;
  if (deltaMileage > 0) {
    const rawPenalty = (deltaMileage / 10000) * excessPenaltyRate;
    const cappedPenalty = Math.max(maxDiscountCap, rawPenalty);
    if (mileageKm >= 500000) {
      mileageAdjustment = rawPenalty;
    } else if (mileageKm > 300000) {
      const progress = (mileageKm - 300000) / 200000;
      mileageAdjustment = cappedPenalty * (1 - progress) + rawPenalty * progress;
    } else {
      mileageAdjustment = cappedPenalty;
    }
  } else {
    mileageAdjustment = Math.min(0.06, (Math.abs(deltaMileage) / 10000) * deficitBonusRate);
  }

  // 2. Warranty Cliff
  const warrantyYears = finiteNonNegOr(model?.warranty?.years, 8);
  const warrantyKm = finiteNonNegOr(model?.warranty?.km, 160000);
  const remainingWarrantyYears = warrantyYears - years;
  const remainingWarrantyKm = warrantyKm - mileageKm;
  const isExpired = remainingWarrantyYears <= 0 || remainingWarrantyKm <= 0;
  const isApproachingCliff = !isExpired && (remainingWarrantyYears <= 2 || remainingWarrantyKm <= 25000);

  let warrantyCliffPenalty = 0;
  if (isExpired) {
    warrantyCliffPenalty = expiredWarrantyPenalty;
  } else if (isApproachingCliff) {
    warrantyCliffPenalty = approachingCliffPenalty;
  }

  // 3. Chemistry Aging Adjustment
  const modelChemistry = model?.battery_specs?.chemistry ?? 'NCM_811';
  const isLfp = normalizeChemistry(modelChemistry) === 'LFP';
  const rawChemBonus = model?.factor_weights?.chemistry_aging;
  let batteryChemistryBonus =
    typeof rawChemBonus === 'number' && Number.isFinite(rawChemBonus)
      ? clamp(rawChemBonus, -1.0, 1.0)
      : 0;
  if (isLfp) {
    // Smooth monotonic ramp from year 2.0 to 3.0 to ensure discrete chemistry bonuses never invert the depreciation curve
    const lfpBonusRamp = clamp(years - 2.0, 0.0, 1.0);
    batteryChemistryBonus += 0.01 * lfpBonusRamp;
  }

  // 4. Winter Season Adjustment
  let winterAdjustment = 0;
  if (winterSeason) {
    winterAdjustment = isLfp ? -0.035 : -0.015;
  }

  // 5. Hardware Architecture & OTA
  const rawArchAdj = model?.factor_weights?.architecture_800v;
  const architectureAdjustment =
    typeof rawArchAdj === 'number' && Number.isFinite(rawArchAdj)
      ? clamp(rawArchAdj, -1.0, 1.0)
      : 0;
  const rawOtaAdj = model?.factor_weights?.ota_maturity;
  const otaAdjustment =
    typeof rawOtaAdj === 'number' && Number.isFinite(rawOtaAdj)
      ? clamp(rawOtaAdj, -1.0, 1.0)
      : 0;

  mileageAdjustment = Number.isFinite(mileageAdjustment) ? clamp(mileageAdjustment, -1e6, 1e6) : 0;

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
    roundTo(baselineResidualPct + totalAdjustmentPct, 1),
    5.0,
    99.0
  );

  const rawCustomPriceInput =
    safeInput.customPurchasePriceKrw !== undefined && safeInput.customPurchasePriceKrw !== null
      ? safeInput.customPurchasePriceKrw
      : safeOptions?.customPurchasePriceKrw;
  const parsedCustomPrice = parseNumericInput(rawCustomPriceInput);

  const rawBasePurchasePrice =
    Number.isFinite(parsedCustomPrice) && parsedCustomPrice >= 0
      ? parsedCustomPrice
      : (priceBasis === 'effective'
          ? finiteNonNegOr(model?.net_purchase_price_krw, 48_000_000)
          : finiteNonNegOr(model?.msrp_krw_baseline, 55_000_000));

  const basePurchasePriceKrw = normalizeZero(Math.min(10_000_000_000, Math.max(0, rawBasePurchasePrice)));

  const rawEstimatedResidual = Math.round((basePurchasePriceKrw * adjustedResidualPct) / 100);
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
    baselineResidualPct: roundTo(baselineResidualPct, 1),
    adjustedResidualPct,
    estimatedResidualPriceKrw,
    depreciationAmountKrw,
    defenseTier: sanitizeDefenseTier(model?.resale_defense_tier),
    factorAdjustments: {
      warrantyCliffPenalty: roundTo(warrantyCliffPenalty * 100, 1),
      batteryChemistryBonus: roundTo(batteryChemistryBonus * 100, 1),
      architectureAdjustment: roundTo(architectureAdjustment * 100, 1),
      otaAdjustment: roundTo(otaAdjustment * 100, 1),
      mileageAdjustment: roundTo(mileageAdjustment * 100, 1),
      winterAdjustment: roundTo(winterAdjustment * 100, 1),
      totalAdjustmentPct: roundTo(totalAdjustmentPct, 1),
    },
    warrantyStatus: {
      isApproachingCliff,
      isExpired,
      remainingYears: Number.isFinite(remainingWarrantyYears)
        ? Math.max(0, roundTo(remainingWarrantyYears, 1))
        : 0,
      remainingKm: Number.isFinite(remainingWarrantyKm)
        ? Math.max(0, roundTo(remainingWarrantyKm, 0))
        : 0,
    },
    keyPros: typeof model?.key_pros_resale === 'string' ? model.key_pros_resale : '데이터 동기화 완료',
    keyCons: typeof model?.key_cons_resale === 'string' ? model.key_cons_resale : '정기 점검 필요',
  };
}

// ==========================================
// 7. ELECTROCHEMICAL BATTERY HEALTH SIMULATOR
// ==========================================

/**
 * Simulates electrochemical State of Health (SoH) and degradation kinetics.
 * Combines Arrhenius calendar aging and cyclic fatigue with DC fast charging strain.
 */
export function simulateBatteryHealth(
  params: BatterySimulationInput,
  customChemistries?: Record<string, Partial<BatteryChemistryProfile>>,
  customReplacementCosts?: readonly BatteryReplacementTier[],
  options?: { models?: readonly EvModelDepreciation[]; model?: EvModelDepreciation }
): BatteryHealthResult {
  const safeParams = isPlainRecord(params) ? (params as unknown as BatterySimulationInput) : ({} as BatterySimulationInput);
  const safeOptions = isPlainRecord(options) ? options : undefined;
  const {
    chemistry: chemInput,
    modelId,
    totalKm: inputTotalKm,
    annualKm = 15000,
    storageSoc = 0.50,
    ambientTempC = 25.0,
    vehicleEfficiencyKmPerKwh = 5.2,
  } = safeParams;
  const rawDcfcRatio =
    safeParams.dcfcRatio !== undefined && safeParams.dcfcRatio !== null
      ? safeParams.dcfcRatio
      : safeParams.fastChargingRatioPct !== undefined && safeParams.fastChargingRatioPct !== null
      ? parseNumericInput(safeParams.fastChargingRatioPct) / 100
      : 0.25;

  const rawYears = (
    safeParams.years !== undefined && safeParams.years !== null ? safeParams.years : safeParams.heldYears
  ) as unknown;
  const parsedYears = parseNumericInput(rawYears);
  const isInvalidYears =
    rawYears === undefined ||
    rawYears === null ||
    !Number.isFinite(parsedYears) ||
    parsedYears < 0;
  const safeYears = isInvalidYears ? 3 : clamp(parsedYears, 0, 100);

  let model: EvModelDepreciation | undefined = isPlainRecord(safeParams.model)
    ? (safeParams.model as EvModelDepreciation)
    : isPlainRecord(safeOptions?.model)
    ? (safeOptions.model as EvModelDepreciation)
    : undefined;
  if (!model && Array.isArray(safeOptions?.models) && modelId) {
    model = findModelById(safeOptions.models as EvModelDepreciation[], modelId);
  }
  if (!model && typeof modelId === 'string' && modelId.trim() !== '') {
    model = getModelById(modelId);
  }

  const chemistryKey: BatteryChemistryType = normalizeChemistry(
    chemInput || model?.battery_specs?.chemistry || 'NCM_811'
  );

  const hardFallbackChem =
    DEFAULT_FALLBACK_DEPRECIATION_DATABASE.chemistries[chemistryKey] ||
    DEFAULT_FALLBACK_DEPRECIATION_DATABASE.chemistries.NCM_811;
  const dbChems = isPlainRecord(DATABASE?.chemistries) ? DATABASE.chemistries : undefined;
  const dbChem =
    dbChems && Object.prototype.hasOwnProperty.call(dbChems, chemistryKey)
      ? dbChems[chemistryKey]
      : dbChems && Object.prototype.hasOwnProperty.call(dbChems, 'NCM_811')
      ? dbChems.NCM_811
      : undefined;
  const defaultChem: BatteryChemistryProfile = isPlainRecord(dbChem)
    ? {
        ...hardFallbackChem,
        ...dbChem,
        name: typeof dbChem.name === 'string' && dbChem.name.trim() ? dbChem.name : hardFallbackChem.name,
        calendar_arrhenius_ea_j_mol: finiteNonNegOr(dbChem.calendar_arrhenius_ea_j_mol, hardFallbackChem.calendar_arrhenius_ea_j_mol),
        soc_stress_coefficient_beta: finiteOr(dbChem.soc_stress_coefficient_beta, hardFallbackChem.soc_stress_coefficient_beta),
        calendar_baseline_annual_loss_pct: finiteNonNegOr(dbChem.calendar_baseline_annual_loss_pct, hardFallbackChem.calendar_baseline_annual_loss_pct),
        calendar_time_exponent_z: finiteNonNegOr(dbChem.calendar_time_exponent_z, hardFallbackChem.calendar_time_exponent_z),
        dod_exponent_u: finiteNonNegOr(dbChem.dod_exponent_u, hardFallbackChem.dod_exponent_u),
        dcfc_acceleration_multiplier_max: finiteOr(dbChem.dcfc_acceleration_multiplier_max, hardFallbackChem.dcfc_acceleration_multiplier_max),
        cold_charge_sensitivity_gamma: finiteNonNegOr(dbChem.cold_charge_sensitivity_gamma, hardFallbackChem.cold_charge_sensitivity_gamma),
        cycle_life_to_80_soh: finitePosOr(dbChem.cycle_life_to_80_soh, hardFallbackChem.cycle_life_to_80_soh),
        cyclic_exponent_w: finiteNonNegOr(dbChem.cyclic_exponent_w, hardFallbackChem.cyclic_exponent_w),
      }
    : hardFallbackChem;
  const rawCustomChem =
    isPlainRecord(customChemistries) &&
    Object.prototype.hasOwnProperty.call(customChemistries, chemistryKey)
      ? customChemistries[chemistryKey]
      : undefined;
  const chemProfile = isPlainRecord(rawCustomChem)
    ? (rawCustomChem as Partial<BatteryChemistryProfile>)
    : defaultChem;

  const modelCapacityFallback = finitePosOr(model?.battery_specs?.capacity_kwh, 77.4);
  const parsedPackCapacity =
    safeParams.packCapacityKwh !== undefined && safeParams.packCapacityKwh !== null
      ? parseNumericInput(safeParams.packCapacityKwh)
      : modelCapacityFallback;
  const packCapacityKwh =
    Number.isFinite(parsedPackCapacity) && parsedPackCapacity > 0
      ? clamp(parsedPackCapacity, 10.0, 500.0)
      : clamp(modelCapacityFallback, 10.0, 500.0);

  const parsedAnnualKm = parseNumericInput(annualKm);
  const safeAnnualKm =
    Number.isFinite(parsedAnnualKm) && parsedAnnualKm >= 0
      ? normalizeZero(Math.min(10_000_000, parsedAnnualKm))
      : 15000;

  const parsedInputTotalKm = parseNumericInput(inputTotalKm);
  const rawMileage = Number.isFinite(parsedInputTotalKm)
    ? parsedInputTotalKm
    : safeYears * safeAnnualKm;
  const safeMileage = clamp(rawMileage, 0, 10_000_000);

  // A. Calendar Aging via Arrhenius & SoC Kinetics
  const R_GAS = 8.314462;
  const T_REF_K = 298.15;
  const SOC_REF = 0.50;

  const parsedAmbientTemp = parseNumericInput(ambientTempC);
  const safeTempC = Number.isFinite(parsedAmbientTemp) ? clamp(parsedAmbientTemp, -60.0, 85.0) : 25.0;

  const parsedStorageSoc = parseNumericInput(storageSoc);
  const safeStorageSoc = Number.isFinite(parsedStorageSoc) ? clamp(parsedStorageSoc, 0.0, 1.0) : 0.50;

  const parsedDcfcRatio = parseNumericInput(rawDcfcRatio);
  const safeDcfcRatio = Number.isFinite(parsedDcfcRatio) ? clamp(parsedDcfcRatio, 0.0, 1.0) : 0.25;
  const tempK = Math.max(1.0, safeTempC + 273.15);

  const arrheniusEa = clamp(
    finiteNonNegOr(
      chemProfile?.calendar_arrhenius_ea_j_mol,
      defaultChem.calendar_arrhenius_ea_j_mol
    ),
    0,
    500_000
  );
  const arrheniusExponent = clamp((-arrheniusEa / R_GAS) * (1.0 / tempK - 1.0 / T_REF_K), -500, 500);
  const arrheniusFactor = Math.exp(arrheniusExponent);
  const socBeta = clamp(
    finiteNonNegOr(
      chemProfile?.soc_stress_coefficient_beta,
      defaultChem.soc_stress_coefficient_beta
    ),
    0,
    20
  );
  const socExponent = clamp(socBeta * (safeStorageSoc - SOC_REF), -500, 500);
  const socFactor = Math.exp(socExponent);
  const baselineAnnualLoss = clamp(
    finiteNonNegOr(
      chemProfile?.calendar_baseline_annual_loss_pct,
      defaultChem.calendar_baseline_annual_loss_pct
    ),
    0,
    100
  );
  const calendarTimeExp = clamp(
    finiteNonNegOr(chemProfile?.calendar_time_exponent_z, defaultChem.calendar_time_exponent_z),
    0,
    20
  );
  const qLossCal =
    safeYears > 0 && baselineAnnualLoss > 0
      ? (baselineAnnualLoss / 100.0) * arrheniusFactor * socFactor * Math.pow(safeYears, calendarTimeExp)
      : 0;

  // B. Cyclic Aging via Mechanical Strain & DCFC Factor
  const parsedEfficiency = parseNumericInput(vehicleEfficiencyKmPerKwh);
  const safeEfficiency =
    Number.isFinite(parsedEfficiency) && parsedEfficiency > 0
      ? clamp(parsedEfficiency, 0.5, 30.0)
      : 5.2;
  const safeCapacity = packCapacityKwh;

  const energyThroughputKwh = safeMileage / Math.max(1.0, safeEfficiency);
  const equivalentFullCycles = energyThroughputKwh / Math.max(10.0, safeCapacity);
  const safeCycles = Number.isFinite(equivalentFullCycles) ? normalizeZero(Math.max(0, equivalentFullCycles)) : 0;

  const dodExp = clamp(
    finiteNonNegOr(chemProfile?.dod_exponent_u, defaultChem.dod_exponent_u),
    0,
    20
  );
  const fDod = Math.pow(0.85, dodExp);
  const dcfcMax = clamp(
    finiteOr(chemProfile?.dcfc_acceleration_multiplier_max, defaultChem.dcfc_acceleration_multiplier_max),
    1.0,
    1000.0
  );
  const fDcfc = 1.0 + (dcfcMax - 1.0) * safeDcfcRatio;

  let fTempCyc = 1.0;
  if (safeTempC < 0) {
    const coldSensitivity = clamp(
      finiteNonNegOr(chemProfile?.cold_charge_sensitivity_gamma, defaultChem.cold_charge_sensitivity_gamma),
      0,
      1000
    );
    const coldFraction = Math.min(1.0, Math.abs(safeTempC) / 15.0);
    fTempCyc = 1.0 + coldSensitivity * coldFraction;
  }

  const baseCycles = clamp(
    finitePosOr(chemProfile?.cycle_life_to_80_soh, defaultChem.cycle_life_to_80_soh),
    100,
    1_000_000
  );
  const cyclicExp = clamp(
    finiteNonNegOr(chemProfile?.cyclic_exponent_w, defaultChem.cyclic_exponent_w),
    0,
    20
  );
  const qLossCyc =
    safeCycles > 0
      ? 0.20 * fDod * fDcfc * fTempCyc * Math.pow(safeCycles / baseCycles, cyclicExp)
      : 0;

  // C. Sub-additive Coupling (p = 1.25)
  const P_COUPLING = 1.25;
  const safeQLossCal = Number.isFinite(qLossCal) ? clamp(qLossCal, 0, 100) : qLossCal === Infinity ? 100 : 0;
  const safeQLossCyc = Number.isFinite(qLossCyc) ? clamp(qLossCyc, 0, 100) : qLossCyc === Infinity ? 100 : 0;
  const qLossTotal = Math.pow(
    Math.pow(safeQLossCal, P_COUPLING) + Math.pow(safeQLossCyc, P_COUPLING),
    1.0 / P_COUPLING
  );

  const finiteQLossTotal = Number.isFinite(qLossTotal) ? clamp(qLossTotal, 0, 100) : 0;
  const rawSoh = (1.0 - finiteQLossTotal) * 100;
  const sohPct = clamp(roundTo(rawSoh, 1), 0.0, 100.0);

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
    failureRiskPct = Math.min(99.9, roundTo(42.0 + (70.0 - sohPct) * 0.8, 1));
    winterRangeRetentionPct = Math.max(0, Math.round(36 * (sohPct / 70.0)));
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
  const candidateCosts = Array.isArray(customReplacementCosts) && customReplacementCosts.length > 0
    ? customReplacementCosts
    : DATABASE.battery_replacement_costs;
  const replacementCosts = Array.isArray(candidateCosts) && candidateCosts.length > 0
    ? candidateCosts
    : DEFAULT_FALLBACK_DEPRECIATION_DATABASE.battery_replacement_costs;
  const fallbackTier = isPlainRecord(replacementCosts[0])
    ? (replacementCosts[0] as unknown as BatteryReplacementTier)
    : DEFAULT_FALLBACK_DEPRECIATION_DATABASE.battery_replacement_costs[0];

  const pickTier = (idx: number): BatteryReplacementTier => {
    const candidate = replacementCosts[idx];
    return isPlainRecord(candidate) ? (candidate as unknown as BatteryReplacementTier) : fallbackTier;
  };

  let targetTier = pickTier(1);
  if (packCapacityKwh <= 65) {
    targetTier = pickTier(0);
  } else if (packCapacityKwh >= 89) {
    targetTier = isPlainRecord(replacementCosts[2])
      ? (replacementCosts[2] as unknown as BatteryReplacementTier)
      : pickTier(replacementCosts.length - 1);
  }

  const defaultCosts = DEFAULT_FALLBACK_DEPRECIATION_DATABASE.battery_replacement_costs[1].costs;
  const tierCosts = isPlainRecord(targetTier?.costs) ? targetTier.costs : defaultCosts;
  const newPackKrw = Math.min(1e12, finiteNonNegOr(tierCosts?.new_pack_krw, defaultCosts.new_pack_krw));
  const laborCoolantKrw = Math.min(1e12, finiteNonNegOr(tierCosts?.labor_coolant_krw, defaultCosts.labor_coolant_krw));
  const fallbackTotalNew =
    typeof tierCosts?.new_pack_krw === 'number' && Number.isFinite(tierCosts.new_pack_krw) && tierCosts.new_pack_krw >= 0
      ? Math.min(1e12, newPackKrw + laborCoolantKrw)
      : defaultCosts.total_new_installed_krw;
  const totalNewInstalledKrw = Math.min(
    1e12,
    finiteNonNegOr(tierCosts?.total_new_installed_krw, fallbackTotalNew)
  );
  const remanPackKrw =
    tierCosts?.reman_pack_krw === null
      ? null
      : typeof tierCosts?.reman_pack_krw === 'number' &&
        Number.isFinite(tierCosts.reman_pack_krw) &&
        tierCosts.reman_pack_krw >= 0
      ? normalizeZero(Math.min(1e12, tierCosts.reman_pack_krw))
      : null;
  const totalRemanInstalledKrw =
    tierCosts?.total_reman_installed_krw === null
      ? null
      : typeof tierCosts?.total_reman_installed_krw === 'number' &&
        Number.isFinite(tierCosts.total_reman_installed_krw) &&
        tierCosts.total_reman_installed_krw >= 0
      ? normalizeZero(Math.min(1e12, tierCosts.total_reman_installed_krw))
      : null;

  return {
    chemistry: chemistryKey,
    chemistryName:
      (typeof chemProfile?.name === 'string' && chemProfile.name.trim()) ||
      defaultChem.name ||
      chemistryKey ||
      '전기차 배터리',
    years: safeYears,
    totalKm: safeMileage,
    equivalentFullCycles: normalizeZero(Math.round(safeCycles)),
    calendarLossPct: clamp(roundTo(safeQLossCal * 100, 1), 0.0, 100.0),
    cyclicLossPct: clamp(roundTo(safeQLossCyc * 100, 1), 0.0, 100.0),
    totalLossPct: clamp(roundTo(finiteQLossTotal * 100, 1), 0.0, 100.0),
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
      tierId:
        typeof targetTier?.tier_id === 'string' && targetTier.tier_id
          ? targetTier.tier_id
          : 'TIER_77KWH',
      segmentName:
        typeof targetTier?.segment_name === 'string' && targetTier.segment_name
          ? targetTier.segment_name
          : '준중형/중형 (65~84kWh)',
      newPackKrw,
      remanPackKrw,
      laborCoolantKrw,
      totalNewInstalledKrw,
      totalRemanInstalledKrw,
      estimatedCostKrw: totalNewInstalledKrw,
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
  nationalSubsidyKrw: number = 0,
  customTiers?: readonly ClawbackTier[]
): ClawbackResult {
  const parsedMonths = parseNumericInput(heldMonths);
  const normalizedMonths = Number.isFinite(parsedMonths)
    ? Math.max(0, parsedMonths)
    : heldMonths === Infinity || parsedMonths === Infinity
    ? 24
    : 0;
  const parsedLocal = parseNumericInput(localSubsidyKrw);
  const safeLocalSubsidy = Number.isFinite(parsedLocal) ? Math.max(0, Math.min(100_000_000, parsedLocal)) : 0;
  const parsedNational = parseNumericInput(nationalSubsidyKrw);
  const safeNationalSubsidy = Number.isFinite(parsedNational) ? Math.max(0, Math.min(100_000_000, parsedNational)) : 0;
  const tiers = Array.isArray(customTiers) && customTiers.length > 0
    ? customTiers
    : getClawbackSchedule();

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
      remainingMonthsOfObligation: roundTo(remainingMonths, 1),
      explanation: '환수 요율 정보가 없습니다.',
    };
  }

  let matchedTier: ClawbackTier | undefined;
  for (const t of tiers) {
    if (!isPlainRecord(t)) continue;
    const minM = finiteNonNegOr(t.min_months, 0);
    if (
      t.max_months_exclusive === null ||
      t.max_months_exclusive === undefined ||
      t.max_months_exclusive === Infinity
    ) {
      if (normalizedMonths >= minM) {
        matchedTier = t as unknown as ClawbackTier;
        break;
      }
    } else if (
      typeof t.max_months_exclusive === 'number' &&
      Number.isFinite(t.max_months_exclusive)
    ) {
      if (normalizedMonths >= minM && normalizedMonths < t.max_months_exclusive) {
        matchedTier = t as unknown as ClawbackTier;
        break;
      }
    }
  }
  if (!matchedTier) {
    const lastTier = tiers[tiers.length - 1];
    matchedTier =
      normalizedMonths >= 24
        ? defaultTier
        : isPlainRecord(lastTier)
        ? (lastTier as unknown as ClawbackTier)
        : defaultTier;
  }

  const rawStatutoryRate = matchedTier?.clawback_rate;
  const statutoryRate = typeof rawStatutoryRate === 'number' && Number.isFinite(rawStatutoryRate)
    ? clamp(rawStatutoryRate, 0.0, 1.0)
    : 0.0;
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
    localClawbackKrw = normalizeZero(Math.round(safeLocalSubsidy * effectiveRate));
    nationalClawbackKrw = 0; // 국비는 국내 운행 유지 시 환수 면제
    explanation = `타 지자체 관외 이전: 매도인이 수령한 지자체 지방비 보조금(${Math.round(safeLocalSubsidy).toLocaleString()}원)에 대해 사용기간별 회수요율(${(statutoryRate * 100).toFixed(0)}%)이 적용되어 ${localClawbackKrw.toLocaleString()}원이 환수 고지됩니다 (국비는 면제).`;
  } else if (transferType === 'export') {
    isExempt = false;
    effectiveRate = statutoryRate;
    localClawbackKrw = normalizeZero(Math.round(safeLocalSubsidy * effectiveRate));
    nationalClawbackKrw = normalizeZero(Math.round(safeNationalSubsidy * effectiveRate));
    explanation = `해외 수출 말소: 국내 대기질 개선 취지 상실로 국비와 지방비를 합산한 총 보조금에 회수요율(${(statutoryRate * 100).toFixed(0)}%)이 전액 적용됩니다.`;
  }

  if (!explanation) {
    explanation = '알 수 없거나 미지정된 이전 유형입니다.';
  }

  const totalClawbackKrw = normalizeZero(localClawbackKrw + nationalClawbackKrw);
  const remainingMonths = Math.max(0, 24 - normalizedMonths);

  return {
    heldMonths: normalizeZero(normalizedMonths),
    tierLabel:
      typeof matchedTier?.label_ko === 'string' && matchedTier.label_ko
        ? matchedTier.label_ko
        : defaultTier.label_ko,
    statutoryClawbackRate: statutoryRate,
    effectiveClawbackRate: effectiveRate,
    localSubsidyReceivedKrw: normalizeZero(safeLocalSubsidy),
    nationalSubsidyReceivedKrw: normalizeZero(safeNationalSubsidy),
    localClawbackKrw,
    nationalClawbackKrw,
    totalClawbackKrw,
    transferType,
    isExempt,
    remainingMonthsOfObligation: roundTo(remainingMonths, 1),
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
  iceDisplacementCc: number = 1998,
  customParams?: PartialTcoParameters
): TcoResult {
  const hardFallbackTco = DEFAULT_FALLBACK_DEPRECIATION_DATABASE.tco_parameters;
  const fallbackTco = isPlainRecord(DATABASE?.tco_parameters)
    ? DATABASE.tco_parameters
    : hardFallbackTco;
  const params: PartialTcoParameters = isPlainRecord(customParams)
    ? (customParams as PartialTcoParameters)
    : fallbackTco;
  const rawFuelTariffs = isPlainRecord(params.fuel_tariffs) ? params.fuel_tariffs : undefined;
  const rawEfficiencyBaselines = isPlainRecord(params.efficiency_baselines)
    ? params.efficiency_baselines
    : undefined;
  const rawAuxBenefits = isPlainRecord(params.auxiliary_benefits)
    ? params.auxiliary_benefits
    : undefined;
  const fuelTariffs = {
    ev_slow_charging_krw_per_kwh: Math.min(
      1e12,
      finiteNonNegOr(
        rawFuelTariffs?.ev_slow_charging_krw_per_kwh,
        finiteNonNegOr(
          fallbackTco?.fuel_tariffs?.ev_slow_charging_krw_per_kwh,
          hardFallbackTco.fuel_tariffs.ev_slow_charging_krw_per_kwh
        )
      )
    ),
    ev_fast_charging_krw_per_kwh: Math.min(
      1e12,
      finiteNonNegOr(
        rawFuelTariffs?.ev_fast_charging_krw_per_kwh,
        finiteNonNegOr(
          fallbackTco?.fuel_tariffs?.ev_fast_charging_krw_per_kwh,
          hardFallbackTco.fuel_tariffs.ev_fast_charging_krw_per_kwh
        )
      )
    ),
    ice_gasoline_krw_per_liter: Math.min(
      1e12,
      finiteNonNegOr(
        rawFuelTariffs?.ice_gasoline_krw_per_liter,
        finiteNonNegOr(
          fallbackTco?.fuel_tariffs?.ice_gasoline_krw_per_liter,
          hardFallbackTco.fuel_tariffs.ice_gasoline_krw_per_liter
        )
      )
    ),
    ice_diesel_krw_per_liter: Math.min(
      1e12,
      finiteNonNegOr(
        rawFuelTariffs?.ice_diesel_krw_per_liter,
        finiteNonNegOr(
          fallbackTco?.fuel_tariffs?.ice_diesel_krw_per_liter,
          hardFallbackTco.fuel_tariffs.ice_diesel_krw_per_liter
        )
      )
    ),
  };
  const iceFuelEconomy = finitePosOr(
    rawEfficiencyBaselines?.ice_gasoline_economy_km_per_liter,
    finitePosOr(
      fallbackTco?.efficiency_baselines?.ice_gasoline_economy_km_per_liter,
      hardFallbackTco.efficiency_baselines.ice_gasoline_economy_km_per_liter
    )
  );
  const rawTaxParams = isPlainRecord(params.tax_parameters) ? params.tax_parameters : undefined;
  const fallbackTaxParams = fallbackTco?.tax_parameters ?? hardFallbackTco.tax_parameters;
  const taxParameters = {
    ev_annual_tax_krw: Math.min(
      1e12,
      finiteNonNegOr(
        rawTaxParams?.ev_annual_tax_krw,
        finiteNonNegOr(fallbackTaxParams?.ev_annual_tax_krw, hardFallbackTco.tax_parameters.ev_annual_tax_krw)
      )
    ),
    education_tax_multiplier: Math.min(
      1e6,
      finiteNonNegOr(
        rawTaxParams?.education_tax_multiplier,
        finiteNonNegOr(fallbackTaxParams?.education_tax_multiplier, hardFallbackTco.tax_parameters.education_tax_multiplier)
      )
    ),
    ice_age_discount_start_year: Math.max(
      1,
      finitePosOr(
        rawTaxParams?.ice_age_discount_start_year,
        finitePosOr(fallbackTaxParams?.ice_age_discount_start_year, hardFallbackTco.tax_parameters.ice_age_discount_start_year)
      )
    ),
    ice_age_discount_rate_per_year: clamp(
      finiteNonNegOr(
        rawTaxParams?.ice_age_discount_rate_per_year,
        finiteNonNegOr(fallbackTaxParams?.ice_age_discount_rate_per_year, hardFallbackTco.tax_parameters.ice_age_discount_rate_per_year)
      ),
      0,
      1
    ),
    ice_age_discount_max: clamp(
      finiteNonNegOr(
        rawTaxParams?.ice_age_discount_max,
        finiteNonNegOr(fallbackTaxParams?.ice_age_discount_max, hardFallbackTco.tax_parameters.ice_age_discount_max)
      ),
      0,
      1
    ),
    ice_displacement_tiers:
      Array.isArray(rawTaxParams?.ice_displacement_tiers) &&
      rawTaxParams.ice_displacement_tiers.length > 0
        ? rawTaxParams.ice_displacement_tiers
        : Array.isArray(fallbackTaxParams?.ice_displacement_tiers) &&
          fallbackTaxParams.ice_displacement_tiers.length > 0
        ? fallbackTaxParams.ice_displacement_tiers
        : hardFallbackTco.tax_parameters.ice_displacement_tiers,
  };
  const auxiliaryBenefits = {
    expressway_toll_discount_rate: clamp(
      finiteNonNegOr(
        rawAuxBenefits?.expressway_toll_discount_rate,
        finiteNonNegOr(
          fallbackTco?.auxiliary_benefits?.expressway_toll_discount_rate,
          hardFallbackTco.auxiliary_benefits.expressway_toll_discount_rate
        )
      ),
      0,
      1
    ),
    annual_toll_savings_krw: Math.min(
      1e12,
      finiteNonNegOr(
        rawAuxBenefits?.annual_toll_savings_krw,
        finiteNonNegOr(
          fallbackTco?.auxiliary_benefits?.annual_toll_savings_krw,
          hardFallbackTco.auxiliary_benefits.annual_toll_savings_krw
        )
      )
    ),
    public_parking_discount_rate: clamp(
      finiteNonNegOr(
        rawAuxBenefits?.public_parking_discount_rate,
        finiteNonNegOr(
          fallbackTco?.auxiliary_benefits?.public_parking_discount_rate,
          hardFallbackTco.auxiliary_benefits.public_parking_discount_rate
        )
      ),
      0,
      1
    ),
    annual_parking_savings_krw: Math.min(
      1e12,
      finiteNonNegOr(
        rawAuxBenefits?.annual_parking_savings_krw,
        finiteNonNegOr(
          fallbackTco?.auxiliary_benefits?.annual_parking_savings_krw,
          hardFallbackTco.auxiliary_benefits.annual_parking_savings_krw
        )
      )
    ),
    maintenance_annual_savings_krw: Math.min(
      1e12,
      finiteNonNegOr(
        rawAuxBenefits?.maintenance_annual_savings_krw,
        finiteNonNegOr(
          fallbackTco?.auxiliary_benefits?.maintenance_annual_savings_krw,
          hardFallbackTco.auxiliary_benefits.maintenance_annual_savings_krw
        )
      )
    ),
  };

  const parsedSlowRatio = parseNumericInput(slowChargingRatio);
  const safeSlowRatio = Number.isFinite(parsedSlowRatio) ? clamp(parsedSlowRatio, 0.0, 1.0) : 0.70;
  const fastChargingRatio = 1.0 - safeSlowRatio;

  // 1. Blended electricity rate
  const blendedTariff = normalizeZero(
    safeSlowRatio * fuelTariffs.ev_slow_charging_krw_per_kwh +
      fastChargingRatio * fuelTariffs.ev_fast_charging_krw_per_kwh
  );

  const parsedEvEff = parseNumericInput(evEfficiencyKmPerKwh);
  const safeEvEff = clamp(
    Number.isFinite(parsedEvEff) && parsedEvEff > 0
      ? parsedEvEff
      : finitePosOr(
          rawEfficiencyBaselines?.ev_efficiency_km_per_kwh,
          finitePosOr(
            fallbackTco?.efficiency_baselines?.ev_efficiency_km_per_kwh,
            hardFallbackTco.efficiency_baselines.ev_efficiency_km_per_kwh
          )
        ),
    0.5,
    1000
  );
  const safeIceEff = clamp(finitePosOr(iceFuelEconomy, 12.0), 0.5, 1000);

  const evCostPerKm = normalizeZero(blendedTariff / Math.max(1.0, safeEvEff));
  const iceCostPerKm = normalizeZero(
    fuelTariffs.ice_gasoline_krw_per_liter / Math.max(1.0, safeIceEff)
  );

  // 2. Base ICE Tax Calculation (hoisted outside yearly loop)
  const parsedCc = parseNumericInput(iceDisplacementCc);
  const safeCc = Number.isFinite(parsedCc) && parsedCc > 0 ? Math.min(100_000, parsedCc) : 1998;
  let ratePerCc = safeCc <= 1000 ? 80 : safeCc <= 1600 ? 140 : 200;
  for (const tier of taxParameters.ice_displacement_tiers) {
    if (!isPlainRecord(tier)) continue;
    if (tier.max_cc === null || tier.max_cc === undefined || tier.max_cc === Infinity) {
      ratePerCc = Math.min(1e9, finiteNonNegOr(tier.rate_per_cc_krw, ratePerCc));
      break;
    }
    if (typeof tier.max_cc === 'number' && Number.isFinite(tier.max_cc) && safeCc <= tier.max_cc) {
      ratePerCc = Math.min(1e9, finiteNonNegOr(tier.rate_per_cc_krw, ratePerCc));
      break;
    }
  }
  const baseNominalIceTax = safeCc * ratePerCc * (1 + taxParameters.education_tax_multiplier);

  const calculateIceAnnualTax = (yearIndex: number): number => {
    let discount = 0.0;
    if (yearIndex >= taxParameters.ice_age_discount_start_year) {
      const rawDiscount =
        (yearIndex - (taxParameters.ice_age_discount_start_year - 1)) *
        taxParameters.ice_age_discount_rate_per_year;
      discount = clamp(rawDiscount, 0, taxParameters.ice_age_discount_max);
    }
    return normalizeZero(Math.round(baseNominalIceTax * (1 - discount)));
  };

  const evAnnualTax = taxParameters.ev_annual_tax_krw;

  const yearlyBreakdown: TcoYearBreakdown[] = [];
  let cumulativeSavings = 0;
  let evTotalFuel = 0;
  let iceTotalFuel = 0;
  let evTotalTax = 0;
  let iceTotalTax = 0;
  let tollTotalSavings = 0;
  let parkingTotalSavings = 0;
  let maintenanceTotalSavings = 0;

  const parsedAnnualKm = parseNumericInput(annualKm);
  const safeAnnualKm =
    Number.isFinite(parsedAnnualKm) && parsedAnnualKm >= 0
      ? normalizeZero(Math.min(10_000_000, parsedAnnualKm))
      : 15000;
  const parsedYears = parseNumericInput(years);

  const rawYears = Math.min(30, Number.isFinite(parsedYears) && parsedYears > 0 ? parsedYears : 1);
  const safeYears = Math.max(1, Math.round(rawYears));
  const fullYears = Math.floor(rawYears);
  const fractionalRemainder = roundTo(rawYears - fullYears, 4);
  const totalLoops =
    fullYears === 0
      ? 1
      : fractionalRemainder > 0.0001
      ? fullYears + 1
      : fullYears;

  let runningKm = 0;
  for (let y = 1; y <= totalLoops; y++) {
    const fraction =
      y <= fullYears
        ? 1.0
        : fractionalRemainder > 0
        ? fractionalRemainder
        : fullYears === 0
        ? rawYears
        : 1.0;
    const currentKm = normalizeZero(Math.round(safeAnnualKm * fraction));
    runningKm = normalizeZero(runningKm + currentKm);

    const evFuel = normalizeZero(Math.round(currentKm * evCostPerKm));
    const iceFuel = normalizeZero(Math.round(currentKm * iceCostPerKm));
    const evTax = normalizeZero(Math.round(evAnnualTax * fraction));
    const iceTax = normalizeZero(Math.round(calculateIceAnnualTax(y) * fraction));
    const toll = normalizeZero(Math.round(auxiliaryBenefits.annual_toll_savings_krw * fraction));
    const parking = normalizeZero(Math.round(auxiliaryBenefits.annual_parking_savings_krw * fraction));
    const maintenance = normalizeZero(Math.round(auxiliaryBenefits.maintenance_annual_savings_krw * fraction));

    const annualSavings = normalizeZero((iceFuel - evFuel) + (iceTax - evTax) + toll + parking + maintenance);
    cumulativeSavings = normalizeZero(cumulativeSavings + annualSavings);

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
    blendedElectricityTariffKrwPerKwh: roundTo(blendedTariff, 2),
    gasolinePriceKrwPerLiter: fuelTariffs.ice_gasoline_krw_per_liter,
    evFuelCostPerKm: roundTo(evCostPerKm, 2),
    iceFuelCostPerKm: roundTo(iceCostPerKm, 2),
    evTotalFuelCostKrw: normalizeZero(evTotalFuel),
    iceTotalFuelCostKrw: normalizeZero(iceTotalFuel),
    fuelSavingsKrw: normalizeZero(iceTotalFuel - evTotalFuel),
    evTotalTaxKrw: normalizeZero(evTotalTax),
    iceTotalTaxKrw: normalizeZero(iceTotalTax),
    taxSavingsKrw: normalizeZero(iceTotalTax - evTotalTax),
    tollSavingsKrw: normalizeZero(tollTotalSavings),
    parkingSavingsKrw: normalizeZero(parkingTotalSavings),
    maintenanceSavingsKrw: normalizeZero(maintenanceTotalSavings),
    totalAuxiliarySavingsKrw: normalizeZero(tollTotalSavings + parkingTotalSavings + maintenanceTotalSavings),
    totalCumulativeSavingsKrw: cumulativeSavings,
    yearlyBreakdown,
  };
}
