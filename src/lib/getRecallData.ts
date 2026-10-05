import rawRecallData from '../data/ev_recall_database.json' with { type: 'json' };

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

// Year code mapping according to ISO 3779 standard (Position 10)
const VIN_YEAR_MAP: Record<string, number> = {
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
};

// Known WMI prefixes fallback (Positions 1-3)
const WMI_MAP: Record<string, { brand: string; country: string }> = {
  KM8: { brand: '현대자동차', country: '대한민국' },
  KMH: { brand: '제네시스', country: '대한민국' },
  KND: { brand: '기아', country: '대한민국' },
  '5YJ': { brand: '테슬라', country: '미국 (캘리포니아 프리몬트)' },
  '7SA': { brand: '테슬라', country: '미국 (텍사스 오스틴)' },
  LRW: { brand: '테슬라', country: '중국 (상하이 기가팩토리)' },
  W1K: { brand: '메르세데스-벤츠', country: '독일' },
  WDD: { brand: '메르세데스-벤츠', country: '독일' },
  WBA: { brand: 'BMW', country: '독일' },
  WBY: { brand: 'BMW i', country: '독일' },
  LGX: { brand: 'BYD', country: '중국' },
  '1G1': { brand: '쉐보레', country: '미국' },
  LPS: { brand: '폴스타', country: '중국' },
  WP0: { brand: '포르쉐', country: '독일' },
};

/**
 * Main safe loader for the EV Recall Database with defensive defaults.
 */
export function getRecallDatabase(): RecallDatabase {
  try {
    const data = rawRecallData as unknown as Partial<RecallDatabase>;
    const metadata: RecallDatabaseMetadata = {
      version: data.metadata?.version || '1.0.0',
      updated_at: data.metadata?.updated_at || new Date().toISOString(),
      total_campaigns: typeof data.metadata?.total_campaigns === 'number' ? data.metadata.total_campaigns : 0,
      total_affected_vehicles_kdm:
        typeof data.metadata?.total_affected_vehicles_kdm === 'number'
          ? data.metadata.total_affected_vehicles_kdm
          : 0,
      active_fire_campaigns:
        typeof data.metadata?.active_fire_campaigns === 'number'
          ? data.metadata.active_fire_campaigns
          : 0,
      ota_remedy_rate_pct:
        typeof data.metadata?.ota_remedy_rate_pct === 'number'
          ? data.metadata.ota_remedy_rate_pct
          : 0,
    };

    const vin_prefixes: VinPrefixMapping[] = Array.isArray(data.vin_prefixes)
      ? (data.vin_prefixes as VinPrefixMapping[])
      : [];

    const battery_profiles: BatterySafetyProfile[] = Array.isArray(data.battery_profiles)
      ? (data.battery_profiles as BatterySafetyProfile[])
      : [];

    const recalls: OfficialRecallCampaign[] = Array.isArray(data.recalls)
      ? (data.recalls as OfficialRecallCampaign[])
      : [];

    return {
      metadata,
      vin_prefixes,
      battery_profiles,
      recalls,
    };
  } catch (error) {
    console.error('Failed to load ev_recall_database.json, returning defensive fallback:', error);
    return {
      metadata: {
        version: '1.0.0',
        updated_at: new Date().toISOString(),
        total_campaigns: 0,
        total_affected_vehicles_kdm: 0,
        active_fire_campaigns: 0,
        ota_remedy_rate_pct: 0,
      },
      vin_prefixes: [],
      battery_profiles: [],
      recalls: [],
    };
  }
}

/**
 * Validates 17-character ISO 3779 VIN and provides clear diagnostic feedback.
 */
export function validateVinString(vin: string): { valid: boolean; normalized: string; error?: string } {
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

  const yearsMatch = targetModelYears.match(/(\d{4})/g);
  if (yearsMatch && yearsMatch.length >= 2) {
    const startYear = parseInt(yearsMatch[0], 10);
    const endYear = parseInt(yearsMatch[yearsMatch.length - 1], 10);
    return year >= startYear && year <= endYear;
  } else if (yearsMatch && yearsMatch.length === 1) {
    const targetYear = parseInt(yearsMatch[0], 10);
    return year === targetYear;
  }
  return true;
}

/**
 * Decodes 17-digit VIN and cross-references government recall campaigns and battery safety profiles.
 */
export function decodeVinAndCheckRecalls(rawVin: string, customDb?: RecallDatabase): VinCheckResult {
  const db = customDb || getRecallDatabase();
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
  // Match against known prefixes, prioritizing the longest match
  const sortedPrefixes = [...db.vin_prefixes].sort((a, b) => b.prefix.length - a.prefix.length);
  const matchedPrefix = sortedPrefixes.find((p) => vin.startsWith(p.prefix));

  let decodedBrand = matchedPrefix?.brand;
  const decodedModel = matchedPrefix?.model_name;
  let decodedCountry = matchedPrefix?.country;

  // If no exact prefix match, fallback to WMI (first 3 chars)
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
    matchedBatteryProfile = db.battery_profiles.find((bp) => {
      const pModel = bp.model_name.toLowerCase();
      const dModel = (decodedModel || '').toLowerCase();
      return pModel.includes(dModel) || dModel.includes(pModel);
    });
  }

  // 4. Match Recall Campaigns
  const matchingRecalls = db.recalls.filter((campaign) => {
    // Brand match check
    const brandMatches =
      decodedBrand &&
      (campaign.brand.toLowerCase().includes(decodedBrand.toLowerCase()) ||
        decodedBrand.toLowerCase().includes(campaign.brand.toLowerCase()) ||
        (decodedBrand === '제네시스' && campaign.brand === '현대자동차') ||
        campaign.target_model.toLowerCase().includes(decodedBrand.toLowerCase()));

    if (!brandMatches) return false;

    // If model is known, check if model name matches target_model with collision protection
    if (decodedModel && !isModelMatchForCampaign(decodedModel, campaign.target_model)) {
      return false;
    }

    // Year match check against target_model_years
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

/**
 * Checks recalls and battery profile directly by Brand, Model, and optional Year (Mode B).
 */
export function checkRecallsByModel(
  brand: string,
  modelName: string,
  year?: number,
  customDb?: RecallDatabase
): VinCheckResult {
  const db = customDb || getRecallDatabase();

  const matchedBatteryProfile = db.battery_profiles.find((bp) => {
    const brandMatch = bp.brand.toLowerCase().includes(brand.toLowerCase());
    const modelMatch =
      bp.model_name.toLowerCase().includes(modelName.toLowerCase()) ||
      modelName.toLowerCase().includes(bp.model_name.toLowerCase());
    return brandMatch && modelMatch;
  });

  const matchingRecalls = db.recalls.filter((campaign) => {
    const brandMatches =
      campaign.brand.toLowerCase().includes(brand.toLowerCase()) ||
      brand.toLowerCase().includes(campaign.brand.toLowerCase()) ||
      (brand === '제네시스' && campaign.brand === '현대자동차') ||
      campaign.target_model.toLowerCase().includes(brand.toLowerCase());

    if (!brandMatches) return false;

    // Model match check with collision protection
    if (modelName && !isModelMatchForCampaign(modelName, campaign.target_model)) {
      return false;
    }

    // If year is specified, check if it falls within the campaign's target_model_years
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
    query: `${brand} ${modelName} ${year || ''}`.trim(),
    mode: 'MODEL',
    decodedBrand: brand,
    decodedModel: modelName,
    decodedYear: year,
    decodedCountry: matchedBatteryProfile?.brand === '현대자동차' || matchedBatteryProfile?.brand === '기아' || matchedBatteryProfile?.brand === '제네시스' ? '대한민국' : undefined,
    batteryProfile: matchedBatteryProfile,
    recalls: matchingRecalls,
    activeCampaignsCount: matchingRecalls.filter((r) => r.status === 'ACTIVE').length,
    hasFireRisk,
    hasPowerLoss,
    overallRiskGrade,
    timestamp: new Date().toISOString(),
  };
}

/**
 * Returns distinct list of brands available in recall campaigns and battery profiles.
 */
export function getDistinctBrands(customDb?: RecallDatabase): string[] {
  const db = customDb || getRecallDatabase();
  const brands = new Set<string>();
  db.battery_profiles.forEach((p) => brands.add(p.brand));
  db.recalls.forEach((r) => brands.add(r.brand));
  return Array.from(brands);
}

/**
 * Returns list of vehicle models for a selected brand.
 */
export function getModelsForBrand(brand: string, customDb?: RecallDatabase): string[] {
  const db = customDb || getRecallDatabase();
  const models = new Set<string>();

  db.battery_profiles
    .filter((bp) => bp.brand.toLowerCase() === brand.toLowerCase())
    .forEach((bp) => models.add(bp.model_name));

  db.vin_prefixes
    .filter((vp) => vp.brand.toLowerCase() === brand.toLowerCase())
    .forEach((vp) => models.add(vp.model_name));

  return Array.from(models);
}
