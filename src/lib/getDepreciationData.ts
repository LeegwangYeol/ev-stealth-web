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

const DATABASE: DepreciationDatabase = rawDepreciationData as unknown as DepreciationDatabase;

/**
 * Returns the complete EV depreciation database.
 */
export function getDepreciationDatabase(): DepreciationDatabase {
  return DATABASE;
}

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

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
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

  if (years <= 0) return 100.0;
  if (years <= 1.0) {
    const y1 = curve.year_1[key];
    return 100.0 - years * (100.0 - y1);
  }
  if (years <= 2.0) {
    const y1 = curve.year_1[key];
    const y2 = curve.year_2[key];
    return y1 - (years - 1.0) * (y1 - y2);
  }
  if (years <= 3.0) {
    const y2 = curve.year_2[key];
    const y3 = curve.year_3[key];
    return y2 - (years - 2.0) * (y2 - y3);
  }
  if (years <= 4.0) {
    const y3 = curve.year_3[key];
    const y4 = curve.year_4[key];
    return y3 - (years - 3.0) * (y3 - y4);
  }
  if (years <= 5.0) {
    const y4 = curve.year_4[key];
    const y5 = curve.year_5[key];
    return y4 - (years - 4.0) * (y4 - y5);
  }

  // Beyond 5 years: extrapolate with compounding 8% drop per additional year
  const y5 = curve.year_5[key];
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
  const {
    modelId,
    years,
    mileageKm = years * DATABASE.metadata.baseline_annual_mileage_km,
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
    customPurchasePriceKrw ??
    (priceBasis === 'effective' ? model.net_purchase_price_krw : model.msrp_krw_baseline);

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
    years,
    totalKm: inputTotalKm,
    annualKm = 15000,
    dcfcRatio = 0.25,
    storageSoc = 0.50,
    ambientTempC = 25.0,
    vehicleEfficiencyKmPerKwh = 5.2,
  } = params;

  let model: EvModelDepreciation | undefined;
  if (modelId) {
    model = getModelById(modelId);
  }

  const chemistryKey: BatteryChemistryType = normalizeChemistry(
    chemInput || model?.battery_specs.chemistry || 'NCM_811'
  );

  const chemProfile = DATABASE.chemistries[chemistryKey] || DATABASE.chemistries.NCM_811;
  const packCapacityKwh = params.packCapacityKwh ?? model?.battery_specs.capacity_kwh ?? 77.4;
  const mileage = inputTotalKm ?? years * annualKm;
  const safeMileage = Math.max(0, mileage);

  // A. Calendar Aging via Arrhenius & SoC Kinetics
  const R_GAS = 8.314462;
  const T_REF_K = 298.15;
  const SOC_REF = 0.50;
  const tempK = ambientTempC + 273.15;

  const arrheniusFactor = Math.exp(
    (-chemProfile.calendar_arrhenius_ea_j_mol / R_GAS) * (1.0 / tempK - 1.0 / T_REF_K)
  );
  const socFactor = Math.exp(chemProfile.soc_stress_coefficient_beta * (storageSoc - SOC_REF));
  const kCal = (chemProfile.calendar_baseline_annual_loss_pct / 100.0) * arrheniusFactor * socFactor;
  const qLossCal = kCal * Math.pow(Math.max(0.1, years), chemProfile.calendar_time_exponent_z);

  // B. Cyclic Aging via Mechanical Strain & DCFC Factor
  const energyThroughputKwh = safeMileage / Math.max(1.0, vehicleEfficiencyKmPerKwh);
  const equivalentFullCycles = energyThroughputKwh / Math.max(10.0, packCapacityKwh);

  const fDod = Math.pow(0.85, chemProfile.dod_exponent_u);
  const fDcfc = 1.0 + (chemProfile.dcfc_acceleration_multiplier_max - 1.0) * clamp(dcfcRatio, 0.0, 1.0);

  let fTempCyc = 1.0;
  if (ambientTempC < 0) {
    const coldFraction = Math.min(1.0, Math.abs(ambientTempC) / 15.0);
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
    years,
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
  const normalizedMonths = Math.max(0, heldMonths);
  const tiers = DATABASE.subsidy_clawback_schedule.tiers;

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
    localClawbackKrw = Math.round(localSubsidyKrw * effectiveRate);
    nationalClawbackKrw = 0; // 국비는 국내 운행 유지 시 환수 면제
    explanation = `타 지자체 관외 이전: 매도인이 수령한 지자체 지방비 보조금(${Math.round(localSubsidyKrw).toLocaleString()}원)에 대해 사용기간별 회수요율(${(statutoryRate * 100).toFixed(0)}%)이 적용되어 ${localClawbackKrw.toLocaleString()}원이 환수 고지됩니다 (국비는 면제).`;
  } else if (transferType === 'export') {
    isExempt = false;
    effectiveRate = statutoryRate;
    localClawbackKrw = Math.round(localSubsidyKrw * effectiveRate);
    nationalClawbackKrw = Math.round(nationalSubsidyKrw * effectiveRate);
    explanation = `해외 수출 말소: 국내 대기질 개선 취지 상실로 국비와 지방비를 합산한 총 보조금에 회수요율(${(statutoryRate * 100).toFixed(0)}%)이 전액 적용됩니다.`;
  }

  const totalClawbackKrw = localClawbackKrw + nationalClawbackKrw;
  const remainingMonths = Math.max(0, 24 - normalizedMonths);

  return {
    heldMonths: normalizedMonths,
    tierLabel: matchedTier.label_ko,
    statutoryClawbackRate: statutoryRate,
    effectiveClawbackRate: effectiveRate,
    localSubsidyReceivedKrw: localSubsidyKrw,
    nationalSubsidyReceivedKrw: nationalSubsidyKrw,
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
  const clampedSlowRatio = clamp(slowChargingRatio, 0.0, 1.0);
  const fastChargingRatio = 1.0 - clampedSlowRatio;

  // 1. Blended electricity rate
  const blendedTariff =
    clampedSlowRatio * params.fuel_tariffs.ev_slow_charging_krw_per_kwh +
    fastChargingRatio * params.fuel_tariffs.ev_fast_charging_krw_per_kwh;

  const evCostPerKm = blendedTariff / Math.max(1.0, evEfficiencyKmPerKwh);
  const iceFuelEconomy = params.efficiency_baselines.ice_gasoline_economy_km_per_liter;
  const iceCostPerKm = params.fuel_tariffs.ice_gasoline_krw_per_liter / Math.max(1.0, iceFuelEconomy);

  // 2. Base ICE Tax Calculation Function
  const calculateIceAnnualTax = (yearIndex: number): number => {
    let ratePerCc = 200;
    if (iceDisplacementCc <= 1000) {
      ratePerCc = 80;
    } else if (iceDisplacementCc <= 1600) {
      ratePerCc = 140;
    }
    const baseNominalTax = iceDisplacementCc * ratePerCc * (1 + params.tax_parameters.education_tax_multiplier);

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

  const safeYears = Math.max(1, Math.round(years));

  for (let y = 1; y <= safeYears; y++) {
    const evFuel = Math.round(annualKm * evCostPerKm);
    const iceFuel = Math.round(annualKm * iceCostPerKm);
    const iceTax = calculateIceAnnualTax(y);
    const toll = params.auxiliary_benefits.annual_toll_savings_krw;
    const parking = params.auxiliary_benefits.annual_parking_savings_krw;
    const maintenance = params.auxiliary_benefits.maintenance_annual_savings_krw;

    const annualSavings = (iceFuel - evFuel) + (iceTax - evAnnualTax) + toll + parking + maintenance;
    cumulativeSavings += annualSavings;

    evTotalFuel += evFuel;
    iceTotalFuel += iceFuel;
    evTotalTax += evAnnualTax;
    iceTotalTax += iceTax;
    tollTotalSavings += toll;
    parkingTotalSavings += parking;
    maintenanceTotalSavings += maintenance;

    yearlyBreakdown.push({
      year: y,
      cumulativeKm: y * annualKm,
      evElectricityCostKrw: evFuel,
      iceFuelCostKrw: iceFuel,
      evAutomobileTaxKrw: evAnnualTax,
      iceAutomobileTaxKrw: iceTax,
      tollSavingsKrw: toll,
      parkingSavingsKrw: parking,
      maintenanceSavingsKrw: maintenance,
      annualNetSavingsKrw: annualSavings,
      cumulativeNetSavingsKrw: cumulativeSavings,
    });
  }

  return {
    annualKm,
    years: safeYears,
    totalKm: annualKm * safeYears,
    evEfficiencyKmPerKwh,
    iceFuelEconomyKmPerLiter: iceFuelEconomy,
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
