/**
 * South Korea & Global EV Recall and Battery Safety Domain Types
 * Based on Ministry of Land, Infrastructure and Transport (국토교통부 MOLIT) & US NHTSA guidelines.
 */

export type RecallRiskLevel =
  | 'FIRE_HAZARD'
  | 'LOSS_OF_POWER'
  | 'BRAKE_STEERING'
  | 'SOFTWARE_REGULATION'
  | 'STRUCTURAL_DEFECT';

export type RemedyMethod =
  | 'HARDWARE_REPLACE'
  | 'SOFTWARE_UPDATE_SERVICE'
  | 'OTA_WIRELESS'
  | 'INSPECTION_ONLY';

export type FireIncidentStatus =
  | 'CRITICAL_MONITORING'
  | 'RECALLED_RESOLVED'
  | 'VERIFIED_SAFE';

export interface OfficialRecallCampaign {
  id: string;
  campaign_no: string;
  agency: 'MOLIT' | 'NHTSA' | string;
  agency_ko: string;
  brand: string;
  target_model: string;
  target_model_years: string;
  production_date_range: string;
  affected_kdm_units: number;
  defect_title: string;
  risk_level: RecallRiskLevel;
  risk_level_ko: string;
  defect_detail: string;
  remedy_type: RemedyMethod;
  remedy_type_ko: string;
  remedy_action: string;
  consumer_emergency_guide: string;
  service_center_contact: string;
  official_link: string;
  status: 'ACTIVE' | 'RESOLVED' | string;
}

export interface BatterySafetyProfile {
  model_id: string;
  brand: string;
  model_name: string;
  years: string;
  cell_supplier: string;
  cell_chemistry: string;
  fire_incident_status: FireIncidentStatus;
  fire_incident_status_ko: string;
  recommended_soc_limit: number;
  underground_parking_advisory: string;
  bms_safety_features: string;
}

export interface VinPrefixMapping {
  prefix: string;
  wmi: string;
  brand: string;
  model_name: string;
  country: string;
  sample_full_vin: string;
  sample_description: string;
  note?: string;
}

export interface RecallDatabaseMetadata {
  version: string;
  updated_at: string;
  last_updated?: string;
  total_campaigns: number;
  total_affected_vehicles_kdm: number;
  active_fire_campaigns: number;
  ota_remedy_rate_pct: number;
  data_sources?: string[];
}

export interface RecallDatabase {
  metadata: RecallDatabaseMetadata;
  vin_prefixes: VinPrefixMapping[];
  battery_profiles: BatterySafetyProfile[];
  recalls: OfficialRecallCampaign[];
}

export interface VinCheckResult {
  valid: boolean;
  query: string;
  mode: 'VIN' | 'MODEL';
  validationError?: string;
  decodedBrand?: string;
  decodedModel?: string;
  decodedYear?: number;
  decodedCountry?: string;
  decodedWmi?: string;
  batteryProfile?: BatterySafetyProfile;
  recalls: OfficialRecallCampaign[];
  activeCampaignsCount: number;
  hasFireRisk: boolean;
  hasPowerLoss: boolean;
  overallRiskGrade: 'CRITICAL' | 'WARNING' | 'SAFE';
  timestamp: string;
}

export interface RecallKPIs {
  totalCampaigns: number;
  activeCampaigns: number;
  totalAffectedVehiclesKdm: number;
  fireHazardCampaigns: number;
  lossOfPowerCampaigns: number;
  otaRemedyCampaigns: number;
  otaRemedyRatePct: number;
  criticalMonitoringBatteryCount: number;
  brandDistribution: Record<string, number>;
  riskLevelDistribution: Record<RecallRiskLevel, number>;
  remedyTypeDistribution: Record<RemedyMethod, number>;
  totalAffectedVehicles?: number;
  activeFireHazards?: number;
  otaRemedyRate?: number;
  fireRiskBrandCount?: number;
  totalBatteryProfiles?: number;
  resolvedCampaigns?: number;
  campaignResolutionRatePct?: number;
}

export interface ManufacturerRecallSummary {
  manufacturer: string;
  totalCampaigns: number;
  activeCampaigns: number;
  fireHazards: number;
  lossOfPower: number;
  affectedUnits: number;
  completionRatePct: number;
}

