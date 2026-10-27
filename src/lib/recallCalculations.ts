/**
 * Pure calculation utilities, type definitions, and mathematical models for EV Recalls & Battery Safety.
 * Based on Ministry of Land, Infrastructure and Transport (국토교통부 MOLIT) & US NHTSA guidelines.
 *
 * This module has ZERO dependencies on heavy JSON data files, enabling client bundles
 * to remain lean without bundling redundant static data payloads.
 */

// ==========================================
// 1. DOMAIN ENUMS & INTERFACES
// ==========================================

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
  status: 'ACTIVE' | 'RESOLVED';
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
  note: string;
}

export interface RecallDatabaseMetadata {
  version: string;
  updated_at: string;
  total_campaigns: number;
  total_affected_vehicles_kdm: number;
  active_fire_campaigns: number;
  ota_remedy_rate_pct: number;
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
  batteryProfile?: BatterySafetyProfile;
  recalls: OfficialRecallCampaign[];
  activeCampaignsCount: number;
  hasFireRisk: boolean;
  hasPowerLoss: boolean;
  overallRiskGrade: 'CRITICAL' | 'WARNING' | 'SAFE';
  timestamp: string;
}

// ==========================================
// 2. CONSTANTS & FROZEN FALLBACKS (Zero-GC)
// ==========================================

export const DEFAULT_RECALL_METADATA: Readonly<RecallDatabaseMetadata> = Object.freeze({
  version: '1.0.0',
  updated_at: '2026-01-01T00:00:00.000Z',
  total_campaigns: 0,
  total_affected_vehicles_kdm: 0,
  active_fire_campaigns: 0,
  ota_remedy_rate_pct: 0,
});

export const EMPTY_RECALL_DATABASE: RecallDatabase = Object.freeze({
  metadata: DEFAULT_RECALL_METADATA,
  vin_prefixes: Object.freeze([]) as unknown as VinPrefixMapping[],
  battery_profiles: Object.freeze([]) as unknown as BatterySafetyProfile[],
  recalls: Object.freeze([]) as unknown as OfficialRecallCampaign[],
}) as unknown as RecallDatabase;

// Year code mapping according to ISO 3779 standard (Position 10)
export const VIN_YEAR_MAP: Readonly<Record<string, number>> = Object.freeze({
  G: 2016,
  H: 2017,
  J: 2018,
  K: 2019,
  L: 2020,
  M: 2021,
  N: 2022,
  P: 2023,
  R: 2024,
  S: 2025,
  T: 2026,
  V: 2027,
  W: 2028,
  X: 2029,
  Y: 2030,
});

// Known WMI prefixes fallback (Positions 1-3)
export const WMI_MAP: Readonly<Record<string, { brand: string; country: string }>> = Object.freeze({
  KM8: Object.freeze({ brand: '현대자동차', country: '대한민국' }),
  KMH: Object.freeze({ brand: '제네시스', country: '대한민국' }),
  KND: Object.freeze({ brand: '기아', country: '대한민국' }),
  '5YJ': Object.freeze({ brand: '테슬라', country: '미국 (캘리포니아 프리몬트)' }),
  '7SA': Object.freeze({ brand: '테슬라', country: '미국 (텍사스 오스틴)' }),
  LRW: Object.freeze({ brand: '테슬라', country: '중국 (상하이 기가팩토리)' }),
  W1K: Object.freeze({ brand: '메르세데스-벤츠', country: '독일' }),
  WDD: Object.freeze({ brand: '메르세데스-벤츠', country: '독일' }),
  WBA: Object.freeze({ brand: 'BMW', country: '독일' }),
  WBY: Object.freeze({ brand: 'BMW i', country: '독일' }),
  LGX: Object.freeze({ brand: 'BYD', country: '중국' }),
  '1G1': Object.freeze({ brand: '쉐보레', country: '미국' }),
  LPS: Object.freeze({ brand: '폴스타', country: '중국' }),
  WP0: Object.freeze({ brand: '포르쉐', country: '독일' }),
});

// ==========================================
// 3. PURE VIN VALIDATION & NORMALIZATION
// ==========================================

/**
 * Validates 17-character ISO 3779 VIN and provides clear diagnostic feedback.
 */
export function validateVinString(vin: string): { valid: boolean; normalized: string; error?: string } {
  if (!vin || typeof vin !== 'string') {
    return { valid: false, normalized: '', error: '차대번호(VIN) 17자리를 입력해 주십시오.' };
  }
  const normalized = vin.trim().toUpperCase().replace(/[\s-]/g, '');

  if (normalized.length === 0) {
    return { valid: false, normalized, error: '차대번호(VIN) 17자리를 입력해 주십시오.' };
  }

  if (/[IOQ]/i.test(normalized)) {
    return {
      valid: false,
      normalized,
      error: 'ISO 3779 규격상 숫자 1, 0과의 혼동을 방지하기 위해 영문자 I(아이), O(오), Q(큐)는 차대번호에 사용되지 않습니다.',
    };
  }

  if (normalized.length !== 17) {
    return {
      valid: false,
      normalized,
      error: `차대번호는 정확히 17자리여야 합니다. (현재 입력: ${normalized.length}자리)`,
    };
  }

  if (!/^[A-HJ-NPR-Z0-9]{17}$/.test(normalized)) {
    return {
      valid: false,
      normalized,
      error: '차대번호는 영문 대문자와 숫자(I, O, Q 제외)로만 구성되어야 합니다.',
    };
  }

  return { valid: true, normalized };
}

// ==========================================
// 4. CAMPAIGN MATCHING ALGORITHMS
// ==========================================

/**
 * Checks whether a vehicle model name matches any model in a campaign's comma-separated target_model string.
 * Prevents false-positive collisions across distinct models (e.g. "아이오닉 5" vs "아이오닉 EV", "모델 Y" vs "모델 3").
 */
export function isModelMatchForCampaign(queryModel: string, campaignTargetModel: string): boolean {
  if (!queryModel || !campaignTargetModel) return false;

  const normalize = (str: string) => str.toLowerCase().replace(/[\s\-_/()]+/g, '');
  const cleanBase = (name: string) => name.replace(/\s*\([^)]*\)/g, '').trim();

  const queryClean = cleanBase(queryModel).toLowerCase();
  const queryNorm = normalize(queryClean);

  const targets = campaignTargetModel.split(',').map((t) => cleanBase(t).toLowerCase());

  for (const target of targets) {
    const targetNorm = normalize(target);

    // Exact normalized match (e.g. "아이오닉5" === "아이오닉5", "ev6" === "ev6")
    if (queryNorm === targetNorm) return true;

    // Check containment while guarding against collisions
    if (targetNorm.includes(queryNorm) || queryNorm.includes(targetNorm)) {
      // 1. Number collision check: e.g. "아이오닉 5" vs "아이오닉 6", "EV6" vs "EV9"
      const queryNums = queryClean.match(/\d+/g) || [];
      const targetNums = target.match(/\d+/g) || [];
      if (queryNums.length > 0 && targetNums.length > 0) {
        if (queryNums.join('') !== targetNums.join('')) {
          continue;
        }
      }

      // 2. EV / Electric vs Numbered EV check (e.g. "아이오닉 EV" vs "아이오닉 5")
      const queryHasEv = /\bev\b|일렉트릭/i.test(queryClean);
      const targetHasEv = /\bev\b|일렉트릭/i.test(target);
      if (queryNums.length > 0 && !targetNums.length && targetHasEv) {
        continue;
      }
      if (targetNums.length > 0 && !queryNums.length && queryHasEv) {
        continue;
      }

      // 3. Model single-letter designation (e.g. "모델 Y" vs "모델 3/S/X")
      const queryLetter = queryClean.match(/(?:모델|model)\s*([a-z0-9])/i);
      const targetLetter = target.match(/(?:모델|model)\s*([a-z0-9])/i);
      if (queryLetter && targetLetter && queryLetter[1] !== targetLetter[1]) {
        continue;
      }

      return true;
    }

    // Sub-trims in query (e.g. "볼트 EV / EUV" matching "볼트 EV", "i4 eDrive40 / M50" matching "i4 eDrive40")
    const subTrims = queryModel.split(/[/,]/).map((s) => cleanBase(s).toLowerCase().trim());
    for (const sub of subTrims) {
      const subNorm = normalize(sub);
      if (subNorm === targetNorm || targetNorm.includes(subNorm) || subNorm.includes(targetNorm)) {
        const subNums = sub.match(/\d+/g) || [];
        const targetNums = target.match(/\d+/g) || [];
        if (subNums.length > 0 && targetNums.length > 0 && subNums.join('') !== targetNums.join('')) {
          continue;
        }
        return true;
      }
    }
  }

  return false;
}

/**
 * Checks whether a given model year falls within a campaign's target_model_years string.
 */
export function isYearMatchForCampaign(year?: number, targetModelYears?: string): boolean {
  if (!year || !targetModelYears) return true;

  // Split disjoint segments separated by comma or semicolon
  const segments = targetModelYears.split(/[,;]/).map((s) => s.trim());
  let hasValidSegment = false;

  for (const segment of segments) {
    const match = segment.match(/(\d{4})\s*(?:~|-)\s*(\d{4})/);
    if (match) {
      hasValidSegment = true;
      const start = parseInt(match[1], 10);
      const end = parseInt(match[2], 10);
      if (year >= Math.min(start, end) && year <= Math.max(start, end)) return true;
    } else {
      const singleYearMatch = segment.match(/(\d{4})/);
      if (singleYearMatch) {
        hasValidSegment = true;
        if (parseInt(singleYearMatch[1], 10) === year) {
          return true;
        }
      }
    }
  }
  return !hasValidSegment;
}

// ==========================================
// 5. VIN DECODER & CROSS-REFERENCE ENGINE
// ==========================================

/**
 * Pure decoder: Decodes 17-digit VIN and cross-references government recall campaigns and battery safety profiles.
 * Requires `db` parameter to eliminate static JSON bundling from client components.
 */
export function decodeVinAndCheckRecalls(rawVin: string, db?: RecallDatabase): VinCheckResult {
  const activeDb = db || EMPTY_RECALL_DATABASE;
  const validation = validateVinString(rawVin);

  if (!validation.valid) {
    return {
      valid: false,
      query: rawVin,
      mode: 'VIN',
      validationError: validation.error,
      recalls: [],
      activeCampaignsCount: 0,
      hasFireRisk: false,
      hasPowerLoss: false,
      overallRiskGrade: 'SAFE',
      timestamp: new Date().toISOString(),
    };
  }

  const vin = validation.normalized;

  // 1. Decode Year from 10th character (index 9)
  const yearChar = vin.charAt(9);
  const decodedYear = VIN_YEAR_MAP[yearChar];

  // 2. Decode Prefix (WMI + VDS)
  const sortedPrefixes = [...(activeDb.vin_prefixes || [])].sort((a, b) => b.prefix.length - a.prefix.length);
  const matchedPrefix = sortedPrefixes.find((p) => vin.startsWith(p.prefix));

  let decodedBrand = matchedPrefix?.brand;
  const decodedModel = matchedPrefix?.model_name;
  let decodedCountry = matchedPrefix?.country;

  // Fallback to WMI (first 3 chars)
  if (!decodedBrand) {
    const wmi = vin.substring(0, 3);
    const wmiMatch = WMI_MAP[wmi];
    if (wmiMatch) {
      decodedBrand = wmiMatch.brand;
      decodedCountry = wmiMatch.country;
    } else {
      decodedBrand = '기타/미확인 브랜드';
      decodedCountry = '미확인 국가';
    }
  }

  // 3. Match Battery Profile
  let matchedBatteryProfile: BatterySafetyProfile | undefined;
  if (decodedModel) {
    matchedBatteryProfile = (activeDb.battery_profiles || []).find((bp) => {
      const pModel = bp.model_name.toLowerCase();
      const dModel = (decodedModel || '').toLowerCase();
      return pModel.includes(dModel) || dModel.includes(pModel);
    });
  }

  // 4. Match Recall Campaigns
  const matchingRecalls = (activeDb.recalls || []).filter((campaign) => {
    const brandMatches =
      decodedBrand &&
      (campaign.brand.toLowerCase().includes(decodedBrand.toLowerCase()) ||
        decodedBrand.toLowerCase().includes(campaign.brand.toLowerCase()) ||
        (decodedBrand === '제네시스' && campaign.brand === '현대자동차') ||
        campaign.target_model.toLowerCase().includes(decodedBrand.toLowerCase()));

    if (!brandMatches) return false;

    if (decodedModel && !isModelMatchForCampaign(decodedModel, campaign.target_model)) {
      return false;
    }

    if (decodedYear && !isYearMatchForCampaign(decodedYear, campaign.target_model_years)) {
      return false;
    }

    return true;
  });

  const hasFireRisk =
    matchingRecalls.some((r) => r.risk_level === 'FIRE_HAZARD') ||
    matchedBatteryProfile?.fire_incident_status === 'CRITICAL_MONITORING';

  const hasPowerLoss = matchingRecalls.some((r) => r.risk_level === 'LOSS_OF_POWER');

  let overallRiskGrade: 'CRITICAL' | 'WARNING' | 'SAFE' = 'SAFE';
  if (hasFireRisk) {
    overallRiskGrade = 'CRITICAL';
  } else if (hasPowerLoss || matchingRecalls.length > 0) {
    overallRiskGrade = 'WARNING';
  }

  return {
    valid: true,
    query: vin,
    mode: 'VIN',
    decodedBrand,
    decodedModel,
    decodedYear,
    decodedCountry,
    batteryProfile: matchedBatteryProfile,
    recalls: matchingRecalls,
    activeCampaignsCount: matchingRecalls.filter((r) => r.status === 'ACTIVE').length,
    hasFireRisk,
    hasPowerLoss,
    overallRiskGrade,
    timestamp: new Date().toISOString(),
  };
}

// ==========================================
// 6. MODEL-BASED CHECK (Mode B)
// ==========================================

/**
 * Checks recalls and battery profile directly by Brand, Model, and optional Year (Mode B).
 */
export function checkRecallsByModel(
  brand: string,
  modelName: string,
  year?: number,
  db?: RecallDatabase
): VinCheckResult {
  if (
    !brand ||
    typeof brand !== 'string' ||
    !brand.trim() ||
    !modelName ||
    typeof modelName !== 'string' ||
    !modelName.trim()
  ) {
    return {
      valid: false,
      query: `${typeof brand === 'string' ? brand : ''} ${typeof modelName === 'string' ? modelName : ''} ${year || ''}`.trim(),
      mode: 'MODEL',
      decodedBrand: typeof brand === 'string' ? brand.trim() || undefined : undefined,
      decodedModel: typeof modelName === 'string' ? modelName.trim() || undefined : undefined,
      decodedYear: typeof year === 'number' && Number.isFinite(year) ? year : undefined,
      recalls: [],
      activeCampaignsCount: 0,
      hasFireRisk: false,
      hasPowerLoss: false,
      overallRiskGrade: 'SAFE',
      timestamp: new Date().toISOString(),
    };
  }

  const cleanBrand = brand.trim();
  const cleanModel = modelName.trim();
  const brandLower = cleanBrand.toLowerCase();
  const modelLower = cleanModel.toLowerCase();

  const activeDb = db || EMPTY_RECALL_DATABASE;

  const matchedBatteryProfile = (activeDb.battery_profiles || []).find((bp) => {
    if (!bp?.brand || !bp?.model_name) return false;
    const bpBrandLower = bp.brand.toLowerCase();
    const bpModelLower = bp.model_name.toLowerCase();
    const brandMatch = bpBrandLower.includes(brandLower) || brandLower.includes(bpBrandLower);
    const modelMatch = bpModelLower.includes(modelLower) || modelLower.includes(bpModelLower);
    return brandMatch && modelMatch;
  });

  const matchingRecalls = (activeDb.recalls || []).filter((campaign) => {
    if (!campaign?.brand || !campaign?.target_model) return false;
    const campBrandLower = campaign.brand.toLowerCase();
    const campTargetLower = campaign.target_model.toLowerCase();

    const brandMatches =
      campBrandLower.includes(brandLower) ||
      brandLower.includes(campBrandLower) ||
      (cleanBrand === '제네시스' && campaign.brand === '현대자동차') ||
      campTargetLower.includes(brandLower);

    if (!brandMatches) return false;

    if (!isModelMatchForCampaign(cleanModel, campaign.target_model)) {
      return false;
    }

    if (year && !isYearMatchForCampaign(year, campaign.target_model_years)) {
      return false;
    }

    return true;
  });

  const hasFireRisk =
    matchingRecalls.some((r) => r.risk_level === 'FIRE_HAZARD') ||
    matchedBatteryProfile?.fire_incident_status === 'CRITICAL_MONITORING';

  const hasPowerLoss = matchingRecalls.some((r) => r.risk_level === 'LOSS_OF_POWER');

  let overallRiskGrade: 'CRITICAL' | 'WARNING' | 'SAFE' = 'SAFE';
  if (hasFireRisk) {
    overallRiskGrade = 'CRITICAL';
  } else if (hasPowerLoss || matchingRecalls.length > 0) {
    overallRiskGrade = 'WARNING';
  }

  return {
    valid: true,
    query: `${cleanBrand} ${cleanModel} ${year || ''}`.trim(),
    mode: 'MODEL',
    decodedBrand: cleanBrand,
    decodedModel: cleanModel,
    decodedYear: year,
    decodedCountry:
      matchedBatteryProfile?.brand === '현대자동차' ||
      matchedBatteryProfile?.brand === '기아' ||
      matchedBatteryProfile?.brand === '제네시스'
        ? '대한민국'
        : undefined,
    batteryProfile: matchedBatteryProfile,
    recalls: matchingRecalls,
    activeCampaignsCount: matchingRecalls.filter((r) => r.status === 'ACTIVE').length,
    hasFireRisk,
    hasPowerLoss,
    overallRiskGrade,
    timestamp: new Date().toISOString(),
  };
}

// ==========================================
// 7. BRAND & MODEL CATALOG UTILITIES
// ==========================================

/**
 * Returns distinct list of brands available in recall campaigns and battery profiles.
 */
export function getDistinctBrands(db?: RecallDatabase): string[] {
  const activeDb = db || EMPTY_RECALL_DATABASE;
  const brands = new Set<string>();
  (activeDb.battery_profiles || []).forEach((p) => {
    if (p?.brand) brands.add(p.brand);
  });
  (activeDb.recalls || []).forEach((r) => {
    if (r?.brand) brands.add(r.brand);
  });
  return Array.from(brands);
}

/**
 * Returns list of vehicle models for a selected brand.
 */
export function getModelsForBrand(brand: string, db?: RecallDatabase): string[] {
  if (!brand || typeof brand !== 'string' || !brand.trim()) {
    return [];
  }
  const cleanBrand = brand.trim().toLowerCase();
  const activeDb = db || EMPTY_RECALL_DATABASE;
  const models = new Set<string>();

  (activeDb.battery_profiles || [])
    .filter((bp) => bp?.brand && typeof bp.brand === 'string' && bp.brand.toLowerCase() === cleanBrand)
    .forEach((bp) => {
      if (bp?.model_name) models.add(bp.model_name);
    });

  (activeDb.vin_prefixes || [])
    .filter((vp) => vp?.brand && typeof vp.brand === 'string' && vp.brand.toLowerCase() === cleanBrand)
    .forEach((vp) => {
      if (vp?.model_name) models.add(vp.model_name);
    });

  // Support custom db.vehicles if present in customDb or mock
  const customVehicles = (activeDb as unknown as Record<string, unknown>)?.vehicles;
  if (Array.isArray(customVehicles)) {
    (customVehicles as Array<{ brand?: string; model_name?: string; model?: string }>)
      .filter((v) => v?.brand && typeof v.brand === 'string' && v.brand.toLowerCase() === cleanBrand)
      .forEach((v) => {
        if (v?.model_name) models.add(v.model_name);
        else if (v?.model) models.add(v.model);
      });
  }

  // Include models explicitly tracked in recall campaigns for this brand
  (activeDb.recalls || [])
    .filter((r) => r?.brand && typeof r.brand === 'string' && r.brand.toLowerCase() === cleanBrand)
    .forEach((r) => {
      if (r?.target_model) {
        r.target_model.split(',').forEach((tm) => {
          const cleanModel = tm.replace(/\s*\([^)]*\)/g, '').trim();
          if (cleanModel) models.add(cleanModel);
        });
      }
    });

  return Array.from(models);
}

// ==========================================
// 8. STATISTICAL KPIS ENGINE
// ==========================================

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
}

/**
 * Pure calculation of key recall and battery safety metrics from a RecallDatabase.
 */
export function calculateRecallKPIs(db?: RecallDatabase): RecallKPIs {
  const activeDb = db || EMPTY_RECALL_DATABASE;
  const recalls = activeDb.recalls || [];
  const batteryProfiles = activeDb.battery_profiles || [];

  const totalCampaigns = recalls.length;
  let activeCampaigns = 0;
  let totalAffectedVehicles = 0;
  let fireHazards = 0;
  let lossOfPower = 0;
  let otaRemedies = 0;

  const brandDistribution: Record<string, number> = {};
  const riskLevelDistribution: Record<RecallRiskLevel, number> = {
    FIRE_HAZARD: 0,
    LOSS_OF_POWER: 0,
    BRAKE_STEERING: 0,
    SOFTWARE_REGULATION: 0,
    STRUCTURAL_DEFECT: 0,
  };
  const remedyTypeDistribution: Record<RemedyMethod, number> = {
    HARDWARE_REPLACE: 0,
    SOFTWARE_UPDATE_SERVICE: 0,
    OTA_WIRELESS: 0,
    INSPECTION_ONLY: 0,
  };

  for (const campaign of recalls) {
    if (campaign.status === 'ACTIVE') activeCampaigns++;
    if (Number.isFinite(campaign.affected_kdm_units) && campaign.affected_kdm_units > 0) {
      totalAffectedVehicles += campaign.affected_kdm_units;
    }
    if (campaign.risk_level === 'FIRE_HAZARD') fireHazards++;
    if (campaign.risk_level === 'LOSS_OF_POWER') lossOfPower++;
    if (campaign.remedy_type === 'OTA_WIRELESS') otaRemedies++;

    if (campaign.brand) {
      brandDistribution[campaign.brand] = (brandDistribution[campaign.brand] || 0) + 1;
    }

    if (campaign.risk_level && campaign.risk_level in riskLevelDistribution) {
      riskLevelDistribution[campaign.risk_level]++;
    }

    if (campaign.remedy_type && campaign.remedy_type in remedyTypeDistribution) {
      remedyTypeDistribution[campaign.remedy_type]++;
    }
  }

  const otaRemedyRatePct = totalCampaigns > 0
    ? Math.round((otaRemedies / totalCampaigns) * 1000) / 10
    : 0;

  const criticalMonitoringBatteryCount = batteryProfiles.filter(
    (bp) => bp.fire_incident_status === 'CRITICAL_MONITORING'
  ).length;

  return {
    totalCampaigns,
    activeCampaigns,
    totalAffectedVehiclesKdm: totalAffectedVehicles,
    fireHazardCampaigns: fireHazards,
    lossOfPowerCampaigns: lossOfPower,
    otaRemedyCampaigns: otaRemedies,
    otaRemedyRatePct,
    criticalMonitoringBatteryCount,
    brandDistribution,
    riskLevelDistribution,
    remedyTypeDistribution,
  };
}

// ==========================================
// 9. BADGE & STYLING HELPERS
// ==========================================

export function getRiskLevelBadgeStyle(riskLevel: RecallRiskLevel): {
  badgeClass: string;
  icon: string;
  labelKo: string;
} {
  switch (riskLevel) {
    case 'FIRE_HAZARD':
      return {
        badgeClass: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
        icon: '🔥',
        labelKo: '화재 위험',
      };
    case 'LOSS_OF_POWER':
      return {
        badgeClass: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
        icon: '⚡',
        labelKo: '동력 상실/ICCU',
      };
    case 'BRAKE_STEERING':
      return {
        badgeClass: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
        icon: '🛑',
        labelKo: '조향/제동',
      };
    case 'SOFTWARE_REGULATION':
      return {
        badgeClass: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
        icon: '💻',
        labelKo: '소프트웨어/규정',
      };
    case 'STRUCTURAL_DEFECT':
      return {
        badgeClass: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
        icon: '🔩',
        labelKo: '차체/구조 결함',
      };
    default:
      return {
        badgeClass: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
        icon: 'ℹ️',
        labelKo: '일반 리콜',
      };
  }
}

export function getFireStatusBadgeStyle(status: FireIncidentStatus): {
  badgeClass: string;
  icon: string;
  labelKo: string;
} {
  switch (status) {
    case 'CRITICAL_MONITORING':
      return {
        badgeClass: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
        icon: '🚨',
        labelKo: '집중 모니터링',
      };
    case 'RECALLED_RESOLVED':
      return {
        badgeClass: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
        icon: '🔄',
        labelKo: '리콜 조치 완료',
      };
    case 'VERIFIED_SAFE':
      return {
        badgeClass: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
        icon: '✅',
        labelKo: '안전성 검증',
      };
    default:
      return {
        badgeClass: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
        icon: 'ℹ️',
        labelKo: '상태 정보 없음',
      };
  }
}

export function getRemedyTypeBadgeStyle(remedyType: RemedyMethod): {
  badgeClass: string;
  icon: string;
  labelKo: string;
} {
  switch (remedyType) {
    case 'HARDWARE_REPLACE':
      return {
        badgeClass: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
        icon: '🔧',
        labelKo: '부품 교체',
      };
    case 'SOFTWARE_UPDATE_SERVICE':
      return {
        badgeClass: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
        icon: '🛠️',
        labelKo: '센터 방문 SW',
      };
    case 'OTA_WIRELESS':
      return {
        badgeClass: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
        icon: '📡',
        labelKo: '무선(OTA) 업데이트',
      };
    case 'INSPECTION_ONLY':
      return {
        badgeClass: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
        icon: '🔍',
        labelKo: '점검 후 조치',
      };
    default:
      return {
        badgeClass: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
        icon: 'ℹ️',
        labelKo: '조치 방법 미정',
      };
  }
}
