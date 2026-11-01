/**
 * EV Depreciation, Battery Degradation (Arrhenius Kinetics), Subsidy Clawback, and TCO Domain Types
 * Based on South Korea Ministry of Environment subsidy clawback guidelines and battery electrochemical models.
 */

export type BatteryChemistryType = 'LFP' | 'NCM_622' | 'NCM_811' | 'NCMA' | 'NCA';
export type ResaleDefenseTier = 'S' | 'A' | 'A-' | 'B+' | 'B' | 'B-' | 'C+' | 'C' | 'D';
export type SoftwareOtaLevel = 'FULL_STACK' | 'ADVANCED_CCB' | 'INFOTAINMENT_ONLY' | 'BASIC';
export type BatteryRiskGrade = 'GRADE_A' | 'GRADE_B' | 'GRADE_C' | 'CRITICAL';
export type TransferType = 'intra' | 'inter' | 'export';
export type PriceBasis = 'msrp' | 'effective';

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
  release_year: number;
  segment: string;
  msrp_base_krw: number;
  effective_purchase_price_krw: number;
  subsidy_national_krw: number;
  subsidy_local_avg_krw: number;
  total_subsidy_krw: number;
  resale_defense_tier: ResaleDefenseTier;
  depreciation_curve: DepreciationCurve;
  battery_specs: BatterySpecs;
  warranty: WarrantyInfo;
  factor_weights: FactorWeights;
  notable_depreciation_risk: string;
}

export interface BatteryReplacementTierCosts {
  module_repair_krw?: number;
  full_pack_oem_krw?: number;
  remanufactured_pack_krw?: number;
  labor_inspection_krw?: number;
}

export interface BatteryReplacementTier {
  model_id?: string;
  tier_id?: string;
  brand?: string;
  model_name?: string;
  segment_name?: string;
  pack_capacity_kwh?: number;
  cell_supplier?: string;
  replacement_cost_krw?: number;
  costs?: BatteryReplacementTierCosts;
  cost_to_residual_ratio_5yr?: number;
  risk_level?: string;
  out_of_warranty_risk_desc?: string;
  new_pack_krw?: number;
  remanufactured_pack_krw?: number | null;
  labor_coolant_krw?: number;
  estimated_cost_krw?: number;
}

export interface BatteryChemistryProfile {
  chemistry: BatteryChemistryType;
  full_name: string;
  calendar_aging_factor: number;
  cycle_aging_factor: number;
  fast_charging_penalty_factor: number;
  temperature_sensitivity: string;
  expected_soh_5yr_at_100k_km: number;
  advantages: string;
  vulnerabilities: string;
}

export interface AdjustmentFactors {
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
}

export interface ClawbackTier {
  min_months: number;
  max_months_exclusive: number | null;
  max_months?: number | null;
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
  max_cc?: number | null;
  rate_per_cc_krw?: number;
  name?: string;
  annual_tax_krw?: number;
  description?: string;
}

export interface TcoFuelTariffs {
  slow_charging_krw_per_kwh?: number;
  fast_charging_krw_per_kwh?: number;
  gasoline_krw_per_liter?: number;
  diesel_krw_per_liter?: number;
  ev_slow_charging_krw_per_kwh?: number;
  ev_fast_charging_krw_per_kwh?: number;
  ice_gasoline_krw_per_liter?: number;
  ice_diesel_krw_per_liter?: number;
}

export interface TcoTaxParameters {
  ev_annual_automobile_tax_krw?: number;
  ev_annual_auto_tax_krw?: number;
  ice_gasoline_annual_tax_krw?: number;
  ice_diesel_annual_tax_krw?: number;
  ice_annual_tax_by_engine_cc?: Record<string, IceDisplacementTier>;
}

export interface TcoAuxiliaryBenefits {
  highway_toll_discount_rate?: number;
  public_parking_discount_rate?: number;
  annual_parking_savings_krw?: number;
  maintenance_annual_savings_krw?: number;
  highway_toll_discount_pct_ev?: number;
  congestion_toll_discount_pct_ev?: number;
  public_parking_discount_pct_ev?: number;
}

export interface TcoEfficiencyBaselines {
  ev_efficiency_km_per_kwh?: number;
  ice_gasoline_economy_km_per_liter?: number;
  ice_diesel_economy_km_per_liter?: number;
  ev_standard_km_per_kwh?: number;
  ice_gasoline_standard_km_per_liter?: number;
  ice_diesel_standard_km_per_liter?: number;
}

export interface TcoParameters {
  fuel_tariffs: TcoFuelTariffs;
  efficiency_baselines?: TcoEfficiencyBaselines;
  tax_parameters?: TcoTaxParameters;
  auxiliary_benefits?: TcoAuxiliaryBenefits;
  tax?: TcoTaxParameters;
}

export interface DepreciationDatabase {
  metadata: {
    version: string;
    generated_at?: string;
    total_models?: number;
    brands_count?: number;
    currency: string;
    baseline_annual_mileage_km?: number;
    sources?: string[];
    analysis_base_year?: number;
    data_sources?: string[];
    models_evaluated?: number;
  };
  market_context?: {
    korean_market_status: string;
    cheongna_fire_impact_summary: string;
    subsidy_clawback_rules: string;
  };
  adjustment_factors: AdjustmentFactors;
  chemistries?: Record<BatteryChemistryType, BatteryChemistryProfile>;
  battery_chemistry_profiles?: Record<BatteryChemistryType, BatteryChemistryProfile>;
  battery_replacement_costs?: BatteryReplacementTier[];
  battery_replacement_matrix?: BatteryReplacementTier[];
  subsidy_clawback_schedule: SubsidyClawbackSchedule;
  tco_parameters: TcoParameters;
  models: EvModelDepreciation[];
}

export interface DepreciationCalculationInput {
  modelId: string;
  years: number; // 0 to 10
  mileageKm?: number; // total odometer km
  winterSeason?: boolean;
  priceBasis?: PriceBasis;
  customPurchasePriceKrw?: number;
  regionId?: string;
  heldYears?: number;
  totalKm?: number;
  fastChargingRatioPct?: number;
  model?: EvModelDepreciation;
}

export interface FactorAdjustmentsBreakdown {
  warrantyCliffPenalty?: number;
  batteryChemistryBonus?: number;
  architectureAdjustment?: number;
  otaAdjustment?: number;
  mileageAdjustment?: number;
  winterAdjustment?: number;
  totalAdjustmentPct?: number;
  warrantyAdjustmentPct?: number;
  mileageAdjustmentPct?: number;
  fastChargingAdjustmentPct?: number;
  chemistryAdjustmentPct?: number;
  architecture800vBonusPct?: number;
  otaBonusPct?: number;
  netAdjustmentPct?: number;
}

export interface WarrantyStatus {
  isApproachingCliff?: boolean;
  isExpired?: boolean;
  remainingYears: number;
  remainingKm: number;
  isUnderWarranty?: boolean;
  remainingWarrantyYears?: number;
  remainingWarrantyKm?: number;
  isMileageExceeded?: boolean;
  isTimeExceeded?: boolean;
}

export interface DepreciationCalculationResult {
  model: EvModelDepreciation;
  years: number;
  mileageKm: number;
  priceBasis: PriceBasis;
  basePurchasePriceKrw?: number;
  initialPriceKrw?: number;
  baselineResidualPct?: number;
  baseResidualPct?: number;
  adjustedResidualPct: number;
  estimatedResidualPriceKrw?: number;
  estimatedResalePriceKrw?: number;
  depreciationAmountKrw: number;
  depreciationPct?: number;
  defenseTier?: ResaleDefenseTier;
  resaleDefenseTier?: ResaleDefenseTier;
  factorAdjustments?: FactorAdjustmentsBreakdown;
  factorBreakdown?: FactorAdjustmentsBreakdown;
  warrantyStatus: WarrantyStatus;
  keyPros?: string;
  keyCons?: string;
}

export interface BatterySimulationInput {
  modelId?: string;
  chemistry?: string | BatteryChemistryType;
  years?: number;
  heldYears?: number;
  totalKm?: number;
  annualKm?: number;
  dcfcRatio?: number; // 0.0 (100% slow) to 1.0 (100% DC fast)
  fastChargingRatioPct?: number;
  storageSoc?: number; // 0.2 to 1.0
  ambientTempC?: number; // Celsius (-20 to 45)
  seasonalColdWinterExposurePct?: number;
  packCapacityKwh?: number;
  vehicleEfficiencyKmPerKwh?: number;
}

export interface BatteryHealthResult {
  chemistry: BatteryChemistryType;
  chemistryName?: string;
  chemistryFullName?: string;
  years: number;
  heldYears?: number;
  totalKm: number;
  equivalentFullCycles?: number;
  calendarLossPct: number;
  cyclicLossPct?: number;
  cycleLossPct?: number;
  fastChargeLossPct?: number;
  totalLossPct?: number;
  sohPct?: number; // State of Health (100% to 0%)
  sohPercentage?: number;
  grade?: BatteryRiskGrade;
  replacementRiskGrade?: BatteryRiskGrade;
  gradeLabel?: string;
  badgeColor?: string;
  failureRiskPct?: number;
  winterRangeRetentionPct?: number;
  usedMarketValuationFactor?: number;
  usedMarketValuationText?: string;
  capacityRetentionKwh?: number;
  originalCapacityKwh?: number;
  replacementCostKrw?: number;
  replacementCostRatioToResidual?: number;
  warrantyRetentionThresholdPct?: number;
  isWarrantyClaimEligible?: boolean;
  advisoryMessage?: string;
  actionRecommendation?: string;
  replacementCostEstimate?: {
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
  tierLabel?: string;
  statutoryClawbackRate?: number;
  effectiveClawbackRate?: number;
  localSubsidyReceivedKrw?: number;
  nationalSubsidyReceivedKrw?: number;
  localClawbackKrw?: number;
  nationalClawbackKrw?: number;
  totalClawbackKrw?: number;
  transferType: TransferType;
  isExempt?: boolean;
  isClawbackExempt?: boolean;
  remainingMonthsOfObligation?: number;
  explanation?: string;
  initialLocalSubsidyKrw?: number;
  initialNationalSubsidyKrw?: number;
  totalInitialSubsidyKrw?: number;
  clawbackRate?: number;
  clawbackAmountKrw?: number;
  retainedSubsidyKrw?: number;
  legalBasis?: string;
  scenarioDescription?: string;
}

export interface TcoYearBreakdown {
  year: number;
  cumulativeKm?: number;
  evElectricityCostKrw?: number;
  evFuelCostKrw?: number;
  iceFuelCostKrw?: number;
  iceGasolineFuelCostKrw?: number;
  iceDieselFuelCostKrw?: number;
  evAutomobileTaxKrw?: number;
  evAnnualTaxKrw?: number;
  iceAutomobileTaxKrw?: number;
  iceAnnualTaxKrw?: number;
  tollSavingsKrw?: number;
  parkingSavingsKrw?: number;
  evTollParkingDiscountKrw?: number;
  maintenanceSavingsKrw?: number;
  annualNetSavingsKrw?: number;
  cumulativeNetSavingsKrw?: number;
  cumulativeEvNetSavingsVsGasolineKrw?: number;
}

export interface TcoResult {
  annualKm: number;
  years?: number;
  evaluatedYears?: number;
  totalKm: number;
  evEfficiencyKmPerKwh?: number;
  iceFuelEconomyKmPerLiter?: number;
  blendedElectricityTariffKrwPerKwh?: number;
  gasolinePriceKrwPerLiter?: number;
  evFuelCostPerKm?: number;
  iceFuelCostPerKm?: number;
  evTotalFuelCostKrw: number;
  iceTotalFuelCostKrw?: number;
  iceGasolineTotalFuelCostKrw?: number;
  iceDieselTotalFuelCostKrw?: number;
  fuelSavingsKrw?: number;
  fuelSavingsVsGasolineKrw?: number;
  evTotalTaxKrw?: number;
  iceTotalTaxKrw?: number;
  taxSavingsKrw?: number;
  taxSavingsVsGasolineKrw?: number;
  tollSavingsKrw?: number;
  parkingSavingsKrw?: number;
  tollParkingSavingsKrw?: number;
  maintenanceSavingsKrw?: number;
  totalOperatingSavingsVsGasolineKrw?: number;
  netFiveYearSavingsKrw?: number;
  breakEvenKm?: number;
  yearBreakdowns: TcoYearBreakdown[];
}

export interface CalculateDepreciationOptions {
  customPurchasePriceKrw?: number;
  annualAverageKm?: number;
}
