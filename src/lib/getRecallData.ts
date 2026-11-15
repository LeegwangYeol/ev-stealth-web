import rawRecallData from '../data/ev_recall_database.json' with { type: 'json' };
import { sanitizeSafeUrl } from './sanitizeUrl.ts';

import type {
  RecallRiskLevel,
  RemedyMethod,
  FireIncidentStatus,
  OfficialRecallCampaign,
  BatterySafetyProfile,
  VinPrefixMapping,
  RecallDatabaseMetadata,
  RecallDatabase,
  VinCheckResult,
} from '../types/recall.ts';

export type {
  RecallRiskLevel,
  RemedyMethod,
  FireIncidentStatus,
  OfficialRecallCampaign,
  BatterySafetyProfile,
  VinPrefixMapping,
  RecallDatabaseMetadata,
  RecallDatabase,
  VinCheckResult,
};

// Year code mapping according to ISO 3779 standard (Position 10)
// Supports full 30-year automotive cycle (2010 - 2039)
export const VIN_YEAR_MAP: Record<string, number> = {
  A: 2010,
  B: 2011,
  C: 2012,
  D: 2013,
  E: 2014,
  F: 2015,
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
export const WMI_MAP: Record<string, { brand: string; country: string }> = {
  KM8: { brand: '현대자동차', country: '대한민국' },
  KMH: { brand: '제네시스', country: '대한민국' },
  KMF: { brand: '현대자동차', country: '대한민국 (상용/포터 EV)' },
  KND: { brand: '기아', country: '대한민국' },
  KNA: { brand: '기아', country: '대한민국' },
  KNC: { brand: '기아', country: '대한민국 (상용/봉고 EV)' },
  KNM: { brand: '르노코리아', country: '대한민국' },
  KPT: { brand: 'KG모빌리티', country: '대한민국' },
  '5YJ': { brand: '테슬라', country: '미국 (캘리포니아 프리몬트)' },
  '7SA': { brand: '테슬라', country: '미국 (텍사스 오스틴)' },
  LRW: { brand: '테슬라', country: '중국 (상하이 기가팩토리)' },
  XP7: { brand: '테슬라', country: '독일 (베를린 기가팩토리)' },
  W1K: { brand: '메르세데스-벤츠', country: '독일' },
  WDD: { brand: '메르세데스-벤츠', country: '독일' },
  WDC: { brand: '메르세데스-벤츠', country: '독일' },
  '4JG': { brand: '메르세데스-벤츠', country: '미국 (앨라배마 터스컬루사)' },
  WBA: { brand: 'BMW', country: '독일' },
  WBY: { brand: 'BMW i', country: '독일' },
  WBX: { brand: 'BMW', country: '독일' },
  LGX: { brand: 'BYD', country: '중국' },
  '1G1': { brand: '쉐보레', country: '미국' },
  KL3: { brand: '쉐보레', country: '대한민국 (한국지엠)' },
  LPS: { brand: '폴스타', country: '중국' },
  WP0: { brand: '포르쉐', country: '독일' },
  WAU: { brand: '아우디', country: '독일' },
  WA1: { brand: '아우디', country: '독일' },
  WVW: { brand: '폭스바겐', country: '독일' },
  WVG: { brand: '폭스바겐', country: '독일' },
  YV1: { brand: '볼보', country: '스웨덴' },
  YV4: { brand: '볼보', country: '스웨덴' },
};

// Canonical manufacturer mapping resolving synonyms, casing, and localized brand names
export const CANONICAL_MANUFACTURER_MAP: Record<string, string> = {
  hyundai: '현대자동차',
  '현대': '현대자동차',
  '현대차': '현대자동차',
  '현대자동차': '현대자동차',
  hyundaimotor: '현대자동차',
  hyundaimotors: '현대자동차',
  'hyundai motor': '현대자동차',
  hmc: '현대자동차',

  kia: '기아',
  '기아': '기아',
  '기아자동차': '기아',
  kiamotors: '기아',
  'kia motors': '기아',

  genesis: '제네시스',
  '제네시스': '제네시스',

  tesla: '테슬라',
  '테슬라': '테슬라',
  teslamotors: '테슬라',
  'tesla motors': '테슬라',

  mercedes: '메르세데스-벤츠',
  benz: '메르세데스-벤츠',
  mercedesbenz: '메르세데스-벤츠',
  'mercedes-benz': '메르세데스-벤츠',
  'mercedes benz': '메르세데스-벤츠',
  '메르세데스': '메르세데스-벤츠',
  '메르세데스-벤츠': '메르세데스-벤츠',
  '메르세데스벤츠': '메르세데스-벤츠',
  '벤츠': '메르세데스-벤츠',

  bmw: 'BMW',
  'bmw i': 'BMW',
  bmwi: 'BMW',
  bmwkorea: 'BMW',
  'bmw korea': 'BMW',

  byd: 'BYD',
  '비야디': 'BYD',

  chevrolet: '쉐보레',
  chevy: '쉐보레',
  gm: '쉐보레',
  generalmotors: '쉐보레',
  'general motors': '쉐보레',
  '쉐보레': '쉐보레',
  '한국지엠': '쉐보레',

  polestar: '폴스타',
  '폴스타': '폴스타',

  porsche: '포르쉐',
  '포르쉐': '포르쉐',

  audi: '아우디',
  '아우디': '아우디',

  volkswagen: '폭스바겐',
  vw: '폭스바겐',
  '폭스바겐': '폭스바겐',

  volvo: '볼보',
  '볼보': '볼보',

  kgm: 'KG모빌리티',
  kgmobility: 'KG모빌리티',
  'kg mobility': 'KG모빌리티',
  'kg모빌리티': 'KG모빌리티',
  ssangyong: 'KG모빌리티',
  '쌍용': 'KG모빌리티',
  '쌍용자동차': 'KG모빌리티',

  renault: '르노코리아',
  renaultkorea: '르노코리아',
  'renault korea': '르노코리아',
  '르노': '르노코리아',
  '르노코리아': '르노코리아',
  '르노삼성': '르노코리아',
};

// Valid enum sets for strict schema validation
export const VALID_RECALL_RISK_LEVELS: ReadonlySet<RecallRiskLevel> = new Set<RecallRiskLevel>([
  'FIRE_HAZARD',
  'LOSS_OF_POWER',
  'BRAKE_STEERING',
  'SOFTWARE_REGULATION',
  'STRUCTURAL_DEFECT',
]);

export const VALID_REMEDY_METHODS: ReadonlySet<RemedyMethod> = new Set<RemedyMethod>([
  'HARDWARE_REPLACE',
  'SOFTWARE_UPDATE_SERVICE',
  'OTA_WIRELESS',
  'INSPECTION_ONLY',
]);

export const VALID_FIRE_INCIDENT_STATUSES: ReadonlySet<FireIncidentStatus> = new Set<FireIncidentStatus>([
  'CRITICAL_MONITORING',
  'RECALLED_RESOLVED',
  'VERIFIED_SAFE',
]);

export interface SchemaValidationResult<T> {
  valid: boolean;
  errors: string[];
  data?: T;
}

/**
 * Validates a single OfficialRecallCampaign record against strict domain schema constraints.
 */
export function validateOfficialRecallCampaign(
  raw: unknown,
  index?: number
): SchemaValidationResult<OfficialRecallCampaign> {
  const prefix = index !== undefined ? `Recall[${index}]` : 'Recall';
  const errors: string[] = [];

  if (!raw || typeof raw !== 'object') {
    return { valid: false, errors: [`${prefix}: Record must be a non-null object`] };
  }

  const r = raw as Record<string, unknown>;

  if (typeof r.id !== 'string' || !r.id.trim()) {
    errors.push(`${prefix}: Missing or empty id`);
  }
  if (typeof r.campaign_no !== 'string' || !r.campaign_no.trim()) {
    errors.push(`${prefix}: Missing or empty campaign_no`);
  }
  if (typeof r.brand !== 'string' || !r.brand.trim()) {
    errors.push(`${prefix}: Missing or empty brand`);
  }
  if (typeof r.target_model !== 'string' || !r.target_model.trim()) {
    errors.push(`${prefix}: Missing or empty target_model`);
  }
  if (typeof r.risk_level !== 'string' || !VALID_RECALL_RISK_LEVELS.has(r.risk_level as RecallRiskLevel)) {
    errors.push(`${prefix}: Invalid risk_level '${r.risk_level}'`);
  }
  if (typeof r.remedy_type !== 'string' || !VALID_REMEDY_METHODS.has(r.remedy_type as RemedyMethod)) {
    errors.push(`${prefix}: Invalid remedy_type '${r.remedy_type}'`);
  }
  if (typeof r.status !== 'string' || (r.status !== 'ACTIVE' && r.status !== 'RESOLVED')) {
    errors.push(`${prefix}: Invalid status '${r.status}' (must be 'ACTIVE' or 'RESOLVED')`);
  }
  if (
    typeof r.affected_kdm_units !== 'number' ||
    !Number.isFinite(r.affected_kdm_units) ||
    r.affected_kdm_units < 0
  ) {
    errors.push(`${prefix}: Invalid affected_kdm_units '${r.affected_kdm_units}' (must be non-negative finite number)`);
  }

  const valid = errors.length === 0;
  return {
    valid,
    errors,
    data: valid ? (r as unknown as OfficialRecallCampaign) : undefined,
  };
}

/**
 * Validates a single BatterySafetyProfile record against strict domain schema constraints.
 */
export function validateBatterySafetyProfile(
  raw: unknown,
  index?: number
): SchemaValidationResult<BatterySafetyProfile> {
  const prefix = index !== undefined ? `BatteryProfile[${index}]` : 'BatteryProfile';
  const errors: string[] = [];

  if (!raw || typeof raw !== 'object') {
    return { valid: false, errors: [`${prefix}: Record must be a non-null object`] };
  }

  const bp = raw as Record<string, unknown>;

  if (typeof bp.model_id !== 'string' || !bp.model_id.trim()) {
    errors.push(`${prefix}: Missing or empty model_id`);
  }
  if (typeof bp.brand !== 'string' || !bp.brand.trim()) {
    errors.push(`${prefix}: Missing or empty brand`);
  }
  if (typeof bp.model_name !== 'string' || !bp.model_name.trim()) {
    errors.push(`${prefix}: Missing or empty model_name`);
  }
  if (typeof bp.cell_supplier !== 'string' || !bp.cell_supplier.trim()) {
    errors.push(`${prefix}: Missing or empty cell_supplier`);
  }
  if (
    typeof bp.fire_incident_status !== 'string' ||
    !VALID_FIRE_INCIDENT_STATUSES.has(bp.fire_incident_status as FireIncidentStatus)
  ) {
    errors.push(`${prefix}: Invalid fire_incident_status '${bp.fire_incident_status}'`);
  }
  if (
    typeof bp.recommended_soc_limit !== 'number' ||
    !Number.isFinite(bp.recommended_soc_limit) ||
    bp.recommended_soc_limit < 50 ||
    bp.recommended_soc_limit > 100
  ) {
    errors.push(`${prefix}: Invalid recommended_soc_limit '${bp.recommended_soc_limit}' (must be 50-100)`);
  }

  const valid = errors.length === 0;
  return {
    valid,
    errors,
    data: valid ? (bp as unknown as BatterySafetyProfile) : undefined,
  };
}

/**
 * Validates a single VinPrefixMapping record against strict domain schema constraints.
 */
export function validateVinPrefixMapping(
  raw: unknown,
  index?: number
): SchemaValidationResult<VinPrefixMapping> {
  const prefix = index !== undefined ? `VinPrefix[${index}]` : 'VinPrefix';
  const errors: string[] = [];

  if (!raw || typeof raw !== 'object') {
    return { valid: false, errors: [`${prefix}: Record must be a non-null object`] };
  }

  const vp = raw as Record<string, unknown>;

  if (typeof vp.prefix !== 'string' || !vp.prefix.trim()) {
    errors.push(`${prefix}: Missing or empty prefix`);
  }
  if (typeof vp.brand !== 'string' || !vp.brand.trim()) {
    errors.push(`${prefix}: Missing or empty brand`);
  }
  if (typeof vp.model_name !== 'string' || !vp.model_name.trim()) {
    errors.push(`${prefix}: Missing or empty model_name`);
  }

  const valid = errors.length === 0;
  return {
    valid,
    errors,
    data: valid ? (vp as unknown as VinPrefixMapping) : undefined,
  };
}

/**
 * Validates entire RecallDatabase payload and calculates verified metadata totals.
 */
export function validateRecallDatabaseSchema(raw: unknown): {
  valid: boolean;
  errors: string[];
  database?: RecallDatabase;
} {
  const errors: string[] = [];
  if (!raw || typeof raw !== 'object') {
    return { valid: false, errors: ['Database root must be a non-null object'] };
  }

  const db = raw as Partial<RecallDatabase>;

  if (!db.metadata || typeof db.metadata !== 'object') {
    errors.push('Database: Missing metadata object');
  }

  const validRecalls: OfficialRecallCampaign[] = [];
  if (!Array.isArray(db.recalls)) {
    errors.push('Database: Missing recalls array');
  } else {
    db.recalls.forEach((r, idx) => {
      const res = validateOfficialRecallCampaign(r, idx);
      if (!res.valid) {
        errors.push(...res.errors);
      } else if (res.data) {
        validRecalls.push(res.data);
      }
    });
  }

  const validBatteryProfiles: BatterySafetyProfile[] = [];
  if (!Array.isArray(db.battery_profiles)) {
    errors.push('Database: Missing battery_profiles array');
  } else {
    db.battery_profiles.forEach((bp, idx) => {
      const res = validateBatterySafetyProfile(bp, idx);
      if (!res.valid) {
        errors.push(...res.errors);
      } else if (res.data) {
        validBatteryProfiles.push(res.data);
      }
    });
  }

  const validPrefixes: VinPrefixMapping[] = [];
  if (!Array.isArray(db.vin_prefixes)) {
    errors.push('Database: Missing vin_prefixes array');
  } else {
    db.vin_prefixes.forEach((vp, idx) => {
      const res = validateVinPrefixMapping(vp, idx);
      if (!res.valid) {
        errors.push(...res.errors);
      } else if (res.data) {
        validPrefixes.push(res.data);
      }
    });
  }

  const valid = errors.length === 0;
  const database: RecallDatabase = {
    metadata: {
      version: typeof db.metadata?.version === 'string' ? db.metadata.version : '1.0.0',
      updated_at: typeof db.metadata?.updated_at === 'string' ? db.metadata.updated_at : new Date().toISOString(),
      total_campaigns:
        typeof db.metadata?.total_campaigns === 'number' && Number.isFinite(db.metadata.total_campaigns)
          ? db.metadata.total_campaigns
          : validRecalls.length,
      total_affected_vehicles_kdm:
        typeof db.metadata?.total_affected_vehicles_kdm === 'number' && Number.isFinite(db.metadata.total_affected_vehicles_kdm)
          ? db.metadata.total_affected_vehicles_kdm
          : validRecalls.reduce((sum, r) => sum + (r.affected_kdm_units || 0), 0),
      active_fire_campaigns:
        typeof db.metadata?.active_fire_campaigns === 'number' && Number.isFinite(db.metadata.active_fire_campaigns)
          ? db.metadata.active_fire_campaigns
          : validRecalls.filter((r) => r.risk_level === 'FIRE_HAZARD' && r.status === 'ACTIVE').length,
      ota_remedy_rate_pct:
        typeof db.metadata?.ota_remedy_rate_pct === 'number' && Number.isFinite(db.metadata.ota_remedy_rate_pct)
          ? db.metadata.ota_remedy_rate_pct
          : (validRecalls.length > 0
              ? Math.round((validRecalls.filter((r) => r.remedy_type === 'OTA_WIRELESS').length / validRecalls.length) * 1000) / 10
              : 0),
    },
    vin_prefixes: validPrefixes,
    battery_profiles: validBatteryProfiles,
    recalls: validRecalls,
  };

  return { valid, errors, database };
}

/**
 * Normalizes manufacturer / brand string to canonical form, handling casing,
 * leading/trailing whitespace, punctuation, and English/Korean aliases.
 */
export function normalizeManufacturer(brand?: string | null): string {
  if (!brand || typeof brand !== 'string') return '';
  const cleaned = brand.trim();
  if (!cleaned) return '';

  const key = cleaned.toLowerCase().replace(/[\s\-_/()[\]+.,&]+/g, '');
  if (CANONICAL_MANUFACTURER_MAP[key]) {
    return CANONICAL_MANUFACTURER_MAP[key];
  }

  const keyWithSpaces = cleaned.toLowerCase().replace(/\s+/g, ' ');
  if (CANONICAL_MANUFACTURER_MAP[keyWithSpaces]) {
    return CANONICAL_MANUFACTURER_MAP[keyWithSpaces];
  }

  return cleaned;
}

/**
 * Main safe loader for the EV Recall Database with strict schema validation
 * and defensive defaults.
 */
export function getRecallDatabase(): RecallDatabase {
  try {
    const validated = validateRecallDatabaseSchema(rawRecallData);
    if (validated.database) {
      // Ensure official URLs are safely sanitized
      const sanitizedRecalls = validated.database.recalls.map((r) => ({
        ...r,
        official_link: sanitizeSafeUrl(r.official_link),
      }));
      return {
        ...validated.database,
        recalls: sanitizedRecalls,
      };
    }
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

/**
 * Calculates the standard ISO 3779 / US 49 CFR Part 565 9th check digit for a 17-character VIN.
 * Returns null if VIN is invalid, contains illegal characters (I, O, Q), or is not 17 chars.
 */
export function calculateVinCheckDigit(vin: string): string | null {
  if (!vin || typeof vin !== 'string') return null;
  const clean = vin.trim().toUpperCase().replace(/[\s-]/g, '');
  if (clean.length !== 17 || /[IOQ]/i.test(clean)) return null;

  const weights = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2];
  const transliteration: Record<string, number> = {
    A: 1, B: 2, C: 3, D: 4, E: 5, F: 6, G: 7, H: 8,
    J: 1, K: 2, L: 3, M: 4, N: 5, P: 7, R: 9,
    S: 2, T: 3, U: 4, V: 5, W: 6, X: 7, Y: 8, Z: 9,
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9,
  };

  let sum = 0;
  for (let i = 0; i < 17; i++) {
    const ch = clean[i];
    const val = transliteration[ch];
    if (val === undefined) return null;
    sum += val * weights[i];
  }
  const rem = sum % 11;
  return rem === 10 ? 'X' : String(rem);
}

/**
 * Checks whether the 9th character matches the calculated check digit per ISO 3779 / NHTSA algorithm.
 * Note: Check digit verification is strictly enforced in North America; in European/Asian domestic markets,
 * the 9th character can be a vehicle descriptor code (VDS).
 */
export function verifyVinChecksum(vin: string): {
  isValidCheckDigit: boolean;
  expectedCheckDigit: string | null;
  actualCheckDigit: string | null;
} {
  const expected = calculateVinCheckDigit(vin);
  if (!expected || typeof vin !== 'string') {
    return { isValidCheckDigit: false, expectedCheckDigit: null, actualCheckDigit: null };
  }
  const clean = vin.trim().toUpperCase().replace(/[\s-]/g, '');
  const actual = clean.length === 17 ? clean[8] : null;
  return {
    isValidCheckDigit: expected === actual,
    expectedCheckDigit: expected,
    actualCheckDigit: actual,
  };
}

/**
 * Checks whether a vehicle model name matches any model in a campaign's comma-separated target_model string.
 * Prevents false-positive collisions across distinct models (e.g. "아이오닉 5" vs "아이오닉 EV", "모델 Y" vs "모델 3").
 */
export function isModelMatchForCampaign(queryModel: string, campaignTargetModel: string): boolean {
  if (
    !queryModel ||
    !campaignTargetModel ||
    typeof queryModel !== 'string' ||
    typeof campaignTargetModel !== 'string'
  ) {
    return false;
  }

  const normalize = (str: string) => str.toLowerCase().replace(/[\s\-_/()[\]+.,&]+/g, '');
  const cleanBase = (name: string) => name.replace(/\s*\([^)]*\)/g, '').trim();

  const queryClean = cleanBase(queryModel).toLowerCase();
  const queryNorm = normalize(queryClean);

  // Require query to contain at least one alphanumeric or Korean character
  if (!queryNorm || !/[a-zA-Z0-9가-힣]/.test(queryNorm)) {
    return false;
  }

  // Safely extracts model designation digits while ignoring drivetrains (2WD/4WD),
  // generation counters (1세대, 2세대), 4-digit years (2020-2030), and battery capacities (77.4kWh)
  const extractModelDigits = (str: string): string[] => {
    const stripped = str
      .replace(/\b(?:19|20)\d{2}\b/g, '')
      .replace(/\b[24]wd\b/gi, '')
      .replace(/\b\d+세대\b/g, '')
      .replace(/\b\d+(?:\.\d+)?\s*kwh\b/gi, '');
    return stripped.match(/\d+/g) || [];
  };

  const queryNums = extractModelDigits(queryClean);
  const targets = campaignTargetModel.split(',').map((t) => cleanBase(t).toLowerCase());

  for (const target of targets) {
    const targetNorm = normalize(target);
    if (!targetNorm || !/[a-zA-Z0-9가-힣]/.test(targetNorm)) {
      continue;
    }

    // Exact normalized match (e.g. "아이오닉5" === "아이오닉5", "ev6" === "ev6")
    if (queryNorm === targetNorm) return true;

    // Check containment while guarding against collisions
    if (targetNorm.includes(queryNorm) || queryNorm.includes(targetNorm)) {
      // 1. Number collision check: e.g. "아이오닉 5" vs "아이오닉 6", "EV6" vs "EV9"
      const targetNums = extractModelDigits(target);
      if (queryNums.length > 0 && targetNums.length > 0) {
        if (queryNums.join('') !== targetNums.join('')) {
          continue;
        }
      }

      // 2. EV / Electric vs Numbered EV check (e.g. "아이오닉 EV" vs "아이오닉 5")
      const queryHasEv = /\bev\b|일렉트릭/i.test(queryClean);
      const targetHasEv = /\bev\b|일렉트릭/i.test(target);
      if (!queryHasEv && queryNums.length > 0 && !targetNums.length && targetHasEv) {
        continue;
      }
      if (!targetHasEv && targetNums.length > 0 && !queryNums.length && queryHasEv) {
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
      if (!subNorm || !/[a-zA-Z0-9가-힣]/.test(subNorm)) {
        continue;
      }
      if (subNorm === targetNorm || targetNorm.includes(subNorm) || subNorm.includes(targetNorm)) {
        const subNums = extractModelDigits(sub);
        const targetNums = extractModelDigits(target);
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
 * Safely parses recall date strings across multiple government format conventions:
 * - "YYYY.MM.DD" (MOLIT format)
 * - "YYYY-MM-DD" (ISO / NHTSA format)
 * - "YYYY/MM/DD"
 * - "YYYYMMDD"
 * - ISO date strings e.g. "2024-03-18T00:00:00Z"
 *
 * Enforces strict date validation and safeguards against invalid strings (NaN)
 * and future dates beyond permissible vehicle timeline bounds (1990 - 2040).
 */
export function parseRecallDate(dateStr?: string | null): Date | null {
  if (!dateStr || typeof dateStr !== 'string') return null;
  const clean = dateStr.trim();
  if (!clean || clean.toLowerCase() === 'null' || clean.toLowerCase() === 'undefined') return null;

  // 1. Try standard regex pattern for YYYY.MM.DD, YYYY-MM-DD, YYYY/MM/DD
  const delimiterMatch = clean.match(/^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})/);
  if (delimiterMatch) {
    const year = parseInt(delimiterMatch[1], 10);
    const month = parseInt(delimiterMatch[2], 10);
    const day = parseInt(delimiterMatch[3], 10);

    if (year < 1990 || year > 2040 || month < 1 || month > 12 || day < 1 || day > 31) {
      return null;
    }

    const d = new Date(Date.UTC(year, month - 1, day));
    if (isNaN(d.getTime())) return null;
    // Strict calendar rollover guard (e.g. 2024-02-31 rolling over to March)
    if (d.getUTCFullYear() !== year || d.getUTCMonth() !== month - 1 || d.getUTCDate() !== day) {
      return null;
    }
    return d;
  }

  // 2. Try Korean date notation: YYYY년 MM월 DD일
  const koreanDateMatch = clean.match(/^(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일/);
  if (koreanDateMatch) {
    const year = parseInt(koreanDateMatch[1], 10);
    const month = parseInt(koreanDateMatch[2], 10);
    const day = parseInt(koreanDateMatch[3], 10);

    if (year < 1990 || year > 2040 || month < 1 || month > 12 || day < 1 || day > 31) {
      return null;
    }

    const d = new Date(Date.UTC(year, month - 1, day));
    if (isNaN(d.getTime())) return null;
    if (d.getUTCFullYear() !== year || d.getUTCMonth() !== month - 1 || d.getUTCDate() !== day) {
      return null;
    }
    return d;
  }

  // 3. Try YYYYMMDD compact format
  const compactMatch = clean.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (compactMatch) {
    const year = parseInt(compactMatch[1], 10);
    const month = parseInt(compactMatch[2], 10);
    const day = parseInt(compactMatch[3], 10);

    if (year < 1990 || year > 2040 || month < 1 || month > 12 || day < 1 || day > 31) {
      return null;
    }

    const d = new Date(Date.UTC(year, month - 1, day));
    if (isNaN(d.getTime())) return null;
    if (d.getUTCFullYear() !== year || d.getUTCMonth() !== month - 1 || d.getUTCDate() !== day) {
      return null;
    }
    return d;
  }

  // 4. Fallback to standard Date.parse
  const timestamp = Date.parse(clean);
  if (isNaN(timestamp)) return null;

  const parsed = new Date(timestamp);
  const fullYear = parsed.getUTCFullYear();
  if (fullYear < 1990 || fullYear > 2040) return null;

  return parsed;
}

/**
 * Extracts a verified 4-digit recall or model year from a variety of inputs:
 * number, date string, range string, or campaign object.
 * Returns undefined for invalid strings, NaN, Infinity, negative values, or future dates (> 2040).
 */
export function extractRecallYear(
  input?: string | number | OfficialRecallCampaign | Record<string, unknown> | null
): number | undefined {
  if (input === undefined || input === null) return undefined;

  // Case A: number input
  if (typeof input === 'number') {
    if (!Number.isFinite(input) || input < 1990 || input > 2040) {
      return undefined;
    }
    return Math.floor(input);
  }

  // Case B: string input
  if (typeof input === 'string') {
    const clean = input.trim();
    if (!clean) return undefined;

    // Check parsed date first
    const parsedDate = parseRecallDate(clean);
    if (parsedDate) {
      return parsedDate.getUTCFullYear();
    }

    // Check for 4-digit year matches (take the most recent valid year if a range)
    const matches = Array.from(clean.matchAll(/\b(19\d\d|20\d\d)\b/g));
    if (matches.length > 0) {
      const validYears = matches
        .map((m) => parseInt(m[1], 10))
        .filter((y) => y >= 1990 && y <= 2040);
      if (validYears.length > 0) {
        return Math.max(...validYears);
      }
    }
    return undefined;
  }

  // Case C: OfficialRecallCampaign or record object
  if (typeof input === 'object') {
    const obj = input as Record<string, unknown>;

    // 1. Try explicit date fields if present
    if (typeof obj.recall_date === 'string') {
      const yr = extractRecallYear(obj.recall_date);
      if (yr) return yr;
    }
    if (typeof obj.date === 'string') {
      const yr = extractRecallYear(obj.date);
      if (yr) return yr;
    }

    // 2. Try campaign_no (e.g. "MOLIT-2024-0318")
    if (typeof obj.campaign_no === 'string') {
      const yr = extractRecallYear(obj.campaign_no);
      if (yr) return yr;
    }

    // 3. Try production_date_range (e.g. "2021.03.08 ~ 2024.03.04")
    if (typeof obj.production_date_range === 'string') {
      const yr = extractRecallYear(obj.production_date_range);
      if (yr) return yr;
    }

    // 4. Try target_model_years (e.g. "2021 ~ 2024")
    if (typeof obj.target_model_years === 'string') {
      const yr = extractRecallYear(obj.target_model_years);
      if (yr) return yr;
    }

    // 5. Try id (e.g. "RC-2024-HYUNDAI-ICCU")
    if (typeof obj.id === 'string') {
      const yr = extractRecallYear(obj.id);
      if (yr) return yr;
    }
  }

  return undefined;
}

/**
 * Sorts an array of recall campaigns by date (descending newest first by default).
 * Deterministically handles invalid date strings, future dates, and unparseable records
 * without mutating the source array and without producing NaN sort instabilities.
 */
export function sortRecallsByDate(
  recalls: OfficialRecallCampaign[],
  order: 'desc' | 'asc' = 'desc'
): OfficialRecallCampaign[] {
  if (!Array.isArray(recalls) || recalls.length === 0) {
    return [];
  }

  const getSortTimestamp = (c: OfficialRecallCampaign): number => {
    if (!c || typeof c !== 'object') return -1;

    // 1. Explicit date / recall_date
    const rawDate = (c as unknown as Record<string, unknown>).recall_date || (c as unknown as Record<string, unknown>).date;
    if (typeof rawDate === 'string') {
      const parsed = parseRecallDate(rawDate);
      if (parsed) return parsed.getTime();
    }

    // 2. MOLIT-YYYY-MMDD in campaign_no
    if (typeof c.campaign_no === 'string') {
      const molitMatch = c.campaign_no.match(/MOLIT-(\d{4})-(\d{2})(\d{2})/i);
      if (molitMatch) {
        const d = parseRecallDate(`${molitMatch[1]}-${molitMatch[2]}-${molitMatch[3]}`);
        if (d) return d.getTime();
      }
      const genericDateMatch = c.campaign_no.match(/(\d{4})[.\-](\d{2})[.\-](\d{2})/);
      if (genericDateMatch) {
        const d = parseRecallDate(`${genericDateMatch[1]}-${genericDateMatch[2]}-${genericDateMatch[3]}`);
        if (d) return d.getTime();
      }
    }

    // 3. End date of production_date_range (e.g. "2021.03.08 ~ 2024.03.04" or "2021-03-08 - 2024-03-04")
    if (typeof c.production_date_range === 'string') {
      const rangeParts = c.production_date_range.split(/[~–—]|\s+-\s+/);
      const endDateStr = (rangeParts[1] || rangeParts[0]).trim();
      const parsed = parseRecallDate(endDateStr);
      if (parsed) return parsed.getTime();
    }

    // 4. Target model year or ID year
    const yr = extractRecallYear(c);
    if (yr) {
      return new Date(Date.UTC(yr, 0, 1)).getTime();
    }

    return -1;
  };

  return [...recalls].sort((a, b) => {
    const timeA = getSortTimestamp(a);
    const timeB = getSortTimestamp(b);

    if (timeA === timeB) return 0;

    // Items with invalid/missing date sort to the bottom
    if (timeA === -1) return 1;
    if (timeB === -1) return -1;

    return order === 'asc' ? timeA - timeB : timeB - timeA;
  });
}

/**
 * Checks whether a given model year falls within a campaign's target_model_years string.
 * Safely guards against NaN, non-finite values, negative numbers, and future date anomalies.
 */
export function isYearMatchForCampaign(year?: number, targetModelYears?: string): boolean {
  if (year === undefined || year === null) return true;
  if (typeof year !== 'number' || !Number.isFinite(year) || year <= 0) return false;
  if (!targetModelYears || typeof targetModelYears !== 'string' || !targetModelYears.trim()) return true;

  // Clean target string: remove Korean particle "년"
  const cleanTarget = targetModelYears.replace(/년/g, '').trim();

  // Split disjoint segments separated by comma or semicolon
  const segments = cleanTarget.split(/[,;]/).map((s) => s.trim()).filter(Boolean);
  if (segments.length === 0) return true;

  let hasValidSegment = false;

  for (const segment of segments) {
    // 1. Closed range: "2021 ~ 2024" or "2021-2024"
    const rangeMatch = segment.match(/(\d{4})\s*(?:~|-)\s*(\d{4})/);
    if (rangeMatch) {
      hasValidSegment = true;
      const start = parseInt(rangeMatch[1], 10);
      const end = parseInt(rangeMatch[2], 10);
      const minYear = Math.min(start, end);
      const maxYear = Math.max(start, end);
      if (year >= minYear && year <= maxYear) return true;
      continue;
    }

    // 2. Open-ended future range: "2022 ~", "2022~", "2022 ~ 현재", "2022 이후", "2022+"
    // Structured without adjacent unbounded quantifiers to prevent catastrophic backtracking (ReDoS)
    const openRangeMatch = segment.match(/(\d{4})(?:\s*[~-])?\s*(?:현재|present|이후|\+)|(\d{4})\s*[~-]\s*$/i);
    if (openRangeMatch) {
      hasValidSegment = true;
      const start = parseInt(openRangeMatch[1] || openRangeMatch[2], 10);
      if (year >= start && year <= 2040) return true;
      continue;
    }

    // 3. Before range: "2022 이전", "~ 2022", "~2022"
    const beforeRangeMatch = segment.match(/(?:^\s*[~-]\s*(\d{4}))|(?:(\d{4})\s*(?:이전|까지|before))/i);
    if (beforeRangeMatch) {
      hasValidSegment = true;
      const end = parseInt(beforeRangeMatch[1] || beforeRangeMatch[2], 10);
      if (year >= 1990 && year <= end) return true;
      continue;
    }

    // 4. Single year match: "2022"
    const singleYearMatch = segment.match(/(\d{4})/);
    if (singleYearMatch) {
      hasValidSegment = true;
      if (parseInt(singleYearMatch[1], 10) === year) {
        return true;
      }
    }
  }

  return !hasValidSegment;
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
      query: typeof rawVin === 'string' ? rawVin : '',
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
  const wmi = vin.substring(0, 3);

  // 1. Decode Year from 10th character (index 9)
  const yearChar = vin.charAt(9);
  const decodedYear = VIN_YEAR_MAP[yearChar] || VIN_YEAR_MAP[yearChar.toUpperCase()];

  // 2. Decode Prefix (WMI + VDS)
  const sortedPrefixes = [...(db.vin_prefixes || [])]
    .filter((p) => p && typeof p.prefix === 'string')
    .sort((a, b) => b.prefix.length - a.prefix.length);
  const matchedPrefix = sortedPrefixes.find((p) => vin.startsWith(p.prefix.trim().toUpperCase()));

  let decodedBrand = matchedPrefix?.brand;
  const decodedModel = matchedPrefix?.model_name;
  let decodedCountry = matchedPrefix?.country;

  // If no exact prefix match, fallback to WMI (first 3 chars)
  if (!decodedBrand) {
    const wmiMatch = WMI_MAP[wmi];
    if (wmiMatch) {
      decodedBrand = wmiMatch.brand;
      decodedCountry = decodedCountry || wmiMatch.country;
    } else {
      decodedBrand = '기타/미확인 브랜드';
    }
  }

  // Fallback to 1st character of VIN for country if still unknown
  if (!decodedCountry || decodedCountry === '미확인 국가') {
    const firstChar = vin.charAt(0);
    if (firstChar === 'K') decodedCountry = '대한민국';
    else if (firstChar === 'W') decodedCountry = '독일';
    else if (firstChar === 'L') decodedCountry = '중국';
    else if (firstChar === '1' || firstChar === '4' || firstChar === '5') decodedCountry = '미국';
    else if (firstChar === 'J') decodedCountry = '일본';
    else if (firstChar === '2') decodedCountry = '캐나다';
    else if (firstChar === '3') decodedCountry = '멕시코';
    else if (firstChar === 'S') decodedCountry = '영국';
    else decodedCountry = '미확인 국가';
  }

  // 3. Match Battery Profile
  let matchedBatteryProfile: BatterySafetyProfile | undefined;
  if (decodedModel) {
    matchedBatteryProfile = (db.battery_profiles || []).find((bp) => {
      if (!bp || typeof bp.model_name !== 'string') return false;
      const pModel = bp.model_name.toLowerCase();
      const dModel = (decodedModel || '').toLowerCase();
      return (
        pModel.includes(dModel) ||
        dModel.includes(pModel) ||
        isModelMatchForCampaign(decodedModel || '', bp.model_name)
      );
    });
  }

  // 4. Match Recall Campaigns
  const matchingRecalls = (db.recalls || []).filter((campaign) => {
    if (!campaign || typeof campaign !== 'object') return false;
    const decodedBrandLower = (decodedBrand || '').toLowerCase();
    const decodedCanonical = decodedBrand ? normalizeManufacturer(decodedBrand) : '';
    const campCanonical = campaign.brand ? normalizeManufacturer(campaign.brand) : '';
    const campBrandLower = (campaign.brand || '').toLowerCase();
    const campTargetLower = (campaign.target_model || '').toLowerCase();

    // Genesis guard: only match Hyundai recalls if campaign mentions Genesis or matches model
    const isGenesisOnHyundai =
      (decodedCanonical === '제네시스' || decodedBrandLower === '제네시스') &&
      campCanonical === '현대자동차';

    const genesisMatches =
      isGenesisOnHyundai &&
      (campTargetLower.includes('제네시스') ||
        campTargetLower.includes('genesis') ||
        Boolean(decodedModel && isModelMatchForCampaign(decodedModel, campaign.target_model)));

    const brandMatches =
      Boolean(decodedBrand) &&
      (genesisMatches ||
        decodedCanonical === campCanonical ||
        campBrandLower === decodedBrandLower ||
        campBrandLower.includes(decodedBrandLower) ||
        decodedBrandLower.includes(campBrandLower) ||
        (campCanonical && campCanonical.toLowerCase().includes(decodedCanonical.toLowerCase())) ||
        (decodedCanonical && decodedCanonical.toLowerCase().includes(campCanonical.toLowerCase())) ||
        campTargetLower.includes(decodedBrandLower) ||
        (decodedCanonical && campTargetLower.includes(decodedCanonical.toLowerCase())));

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
    decodedWmi: wmi,
    batteryProfile: matchedBatteryProfile,
    recalls: sortRecallsByDate(matchingRecalls, 'desc'),
    activeCampaignsCount: matchingRecalls.filter((r) => typeof r.status === 'string' && r.status.trim().toUpperCase() === 'ACTIVE').length,
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
  const cleanBrand = typeof brand === 'string' ? brand.trim() : '';
  const cleanModel = typeof modelName === 'string' ? modelName.trim() : '';

  if (
    !cleanBrand ||
    !cleanModel ||
    !/[a-zA-Z0-9가-힣]/.test(cleanModel)
  ) {
    return {
      valid: false,
      query: `${cleanBrand} ${cleanModel} ${year || ''}`.trim(),
      mode: 'MODEL',
      validationError: '제조사와 유효한 차종명을 모두 입력해 주십시오.',
      decodedBrand: cleanBrand || undefined,
      decodedModel: cleanModel || undefined,
      decodedYear: typeof year === 'number' && Number.isFinite(year) ? year : undefined,
      recalls: [],
      activeCampaignsCount: 0,
      hasFireRisk: false,
      hasPowerLoss: false,
      overallRiskGrade: 'SAFE',
      timestamp: new Date().toISOString(),
    };
  }

  const canonicalBrand = normalizeManufacturer(cleanBrand);
  const brandLower = cleanBrand.toLowerCase();
  const canonicalBrandLower = canonicalBrand.toLowerCase();
  const modelLower = cleanModel.toLowerCase();

  const db = customDb || getRecallDatabase();

  const matchedBatteryProfile = (db.battery_profiles || []).find((bp) => {
    if (!bp?.brand || !bp?.model_name) return false;
    const bpCanonical = normalizeManufacturer(bp.brand);
    const bpBrandLower = bp.brand.toLowerCase();
    const bpModelLower = bp.model_name.toLowerCase();
    const brandMatch =
      bpCanonical === canonicalBrand ||
      bpBrandLower === brandLower ||
      bpBrandLower.includes(brandLower) ||
      brandLower.includes(bpBrandLower) ||
      (bpCanonical && bpCanonical.toLowerCase().includes(canonicalBrandLower)) ||
      (canonicalBrandLower && canonicalBrandLower.includes(bpCanonical.toLowerCase()));
    const modelMatch =
      bpModelLower.includes(modelLower) ||
      modelLower.includes(bpModelLower) ||
      isModelMatchForCampaign(cleanModel, bp.model_name);
    return brandMatch && modelMatch;
  });

  const matchingRecalls = (db.recalls || []).filter((campaign) => {
    if (!campaign?.brand || !campaign?.target_model) return false;
    const campCanonical = normalizeManufacturer(campaign.brand);
    const campBrandLower = campaign.brand.toLowerCase();
    const campTargetLower = campaign.target_model.toLowerCase();

    // Genesis guard: only match Hyundai recalls if campaign mentions Genesis or matches model
    const isGenesisOnHyundai =
      (canonicalBrand === '제네시스' || cleanBrand === '제네시스') &&
      campCanonical === '현대자동차';

    const genesisMatches =
      isGenesisOnHyundai &&
      (campTargetLower.includes('제네시스') ||
        campTargetLower.includes('genesis') ||
        isModelMatchForCampaign(cleanModel, campaign.target_model));

    const brandMatches =
      genesisMatches ||
      campCanonical === canonicalBrand ||
      campBrandLower === brandLower ||
      campBrandLower.includes(brandLower) ||
      brandLower.includes(campBrandLower) ||
      (campCanonical && campCanonical.toLowerCase().includes(canonicalBrandLower)) ||
      (canonicalBrandLower && canonicalBrandLower.includes(campCanonical.toLowerCase())) ||
      campTargetLower.includes(brandLower) ||
      (canonicalBrandLower && campTargetLower.includes(canonicalBrandLower));

    if (!brandMatches) return false;

    if (!isModelMatchForCampaign(cleanModel, campaign.target_model)) {
      return false;
    }

    if (year !== undefined && !isYearMatchForCampaign(year, campaign.target_model_years)) {
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
    decodedYear: typeof year === 'number' && Number.isFinite(year) ? year : undefined,
    decodedCountry:
      canonicalBrand === '현대자동차' ||
      canonicalBrand === '기아' ||
      canonicalBrand === '제네시스' ||
      matchedBatteryProfile?.brand === '현대자동차' ||
      matchedBatteryProfile?.brand === '기아' ||
      matchedBatteryProfile?.brand === '제네시스'
        ? '대한민국'
        : undefined,
    batteryProfile: matchedBatteryProfile,
    recalls: sortRecallsByDate(matchingRecalls, 'desc'),
    activeCampaignsCount: matchingRecalls.filter((r) => typeof r.status === 'string' && r.status.trim().toUpperCase() === 'ACTIVE').length,
    hasFireRisk,
    hasPowerLoss,
    overallRiskGrade,
    timestamp: new Date().toISOString(),
  };
}

/**
 * Returns distinct list of brands available in recall campaigns and battery profiles,
 * deduplicated via canonical manufacturer normalization.
 */
export function getDistinctBrands(customDb?: RecallDatabase): string[] {
  const db = customDb || getRecallDatabase();
  const brands = new Set<string>();
  (db.battery_profiles || []).forEach((p) => {
    if (p?.brand) brands.add(normalizeManufacturer(p.brand));
  });
  (db.recalls || []).forEach((r) => {
    if (r?.brand) brands.add(normalizeManufacturer(r.brand));
  });
  return Array.from(brands);
}

/**
 * Returns list of vehicle models for a selected brand.
 * Supports manufacturer aliases, casing discrepancies, and localized names.
 */
export function getModelsForBrand(brand: string, customDb?: RecallDatabase): string[] {
  if (!brand || typeof brand !== 'string' || !brand.trim()) {
    return [];
  }
  const cleanBrand = brand.trim().toLowerCase();
  const canonicalBrand = normalizeManufacturer(brand);
  const db = customDb || getRecallDatabase();
  const models = new Set<string>();

  const isBrandMatch = (itemBrand?: string) => {
    if (!itemBrand || typeof itemBrand !== 'string') return false;
    const itemClean = itemBrand.trim().toLowerCase();
    if (itemClean === cleanBrand) return true;
    const itemCanonical = normalizeManufacturer(itemBrand);
    return (
      itemCanonical === canonicalBrand ||
      itemCanonical.toLowerCase() === cleanBrand ||
      itemClean.includes(cleanBrand) ||
      cleanBrand.includes(itemClean)
    );
  };

  (db.battery_profiles || [])
    .filter((bp) => isBrandMatch(bp?.brand))
    .forEach((bp) => {
      if (bp?.model_name) models.add(bp.model_name);
    });

  (db.vin_prefixes || [])
    .filter((vp) => isBrandMatch(vp?.brand))
    .forEach((vp) => {
      if (vp?.model_name) models.add(vp.model_name);
    });

  // Support custom db.vehicles if present in customDb or mock
  const customVehicles = (db as unknown as Record<string, unknown>)?.vehicles;
  if (Array.isArray(customVehicles)) {
    (customVehicles as Array<{ brand?: string; model_name?: string; model?: string }>)
      .filter((v) => v && isBrandMatch(v?.brand))
      .forEach((v) => {
        if (v?.model_name) models.add(v.model_name);
        else if (v?.model) models.add(v.model);
      });
  }

  // Include models explicitly tracked in recall campaigns for this brand
  (db.recalls || [])
    .filter((r) => r && (isBrandMatch(r?.brand) || (canonicalBrand === '제네시스' && r?.brand && normalizeManufacturer(r.brand) === '현대자동차')))
    .forEach((r) => {
      if (r?.target_model) {
        r.target_model.split(',').forEach((tm) => {
          const cleanModel = tm.replace(/\s*\([^)]*\)/g, '').trim();
          if (cleanModel) {
            if (canonicalBrand === '제네시스') {
              if (cleanModel.includes('제네시스') || cleanModel.startsWith('GV') || cleanModel.startsWith('G80') || cleanModel.startsWith('G90')) {
                models.add(cleanModel.replace(/^제네시스\s*/, ''));
                models.add(cleanModel);
              }
            } else {
              models.add(cleanModel);
            }
          }
        });
      }
    });

  return Array.from(models);
}

/**
 * Computes recall completion rate (percentage 0.0% - 100.0%) with strict safeguards
 * against division by zero, NaN, Infinity, negative values, and over-100% overflow.
 */
export function calculateRecallCompletionRate(
  completedUnits: number,
  totalUnits: number
): number {
  if (
    typeof completedUnits !== 'number' ||
    typeof totalUnits !== 'number' ||
    !Number.isFinite(completedUnits) ||
    !Number.isFinite(totalUnits) ||
    totalUnits <= 0 ||
    completedUnits <= 0
  ) {
    return 0;
  }

  const rawRate = (completedUnits / totalUnits) * 100;
  if (!Number.isFinite(rawRate) || rawRate <= 0) return 0;
  if (rawRate >= 100) return 100;

  return Math.round(rawRate * 10) / 10;
}

/**
 * Computes recall campaign resolution rate (percentage of campaigns marked RESOLVED)
 * with division by zero safeguards.
 */
export function calculateCampaignResolutionRate(
  resolvedCampaigns: number,
  totalCampaigns: number
): number {
  if (
    typeof resolvedCampaigns !== 'number' ||
    typeof totalCampaigns !== 'number' ||
    !Number.isFinite(resolvedCampaigns) ||
    !Number.isFinite(totalCampaigns) ||
    totalCampaigns <= 0 ||
    resolvedCampaigns <= 0
  ) {
    return 0;
  }

  const rawRate = (resolvedCampaigns / totalCampaigns) * 100;
  if (!Number.isFinite(rawRate) || rawRate <= 0) return 0;
  if (rawRate >= 100) return 100;

  return Math.round(rawRate * 10) / 10;
}

export interface ManufacturerRecallSummary {
  manufacturer: string;
  totalCampaigns: number;
  activeCampaigns: number;
  resolvedCampaigns: number;
  fireHazards: number;
  lossOfPower: number;
  affectedUnits: number;
  completionRatePct: number;
}

/**
 * Aggregates recall campaigns by canonical manufacturer, resolving casing and naming discrepancies.
 * Pure aggregation function with zero dependencies.
 */
export function aggregateRecallsByManufacturer(
  recalls?: OfficialRecallCampaign[]
): Record<string, ManufacturerRecallSummary> {
  const safeRecalls = Array.isArray(recalls) ? recalls : [];
  const result: Record<string, ManufacturerRecallSummary> = {};

  for (const campaign of safeRecalls) {
    if (!campaign || typeof campaign !== 'object') continue;
    const manufacturer = normalizeManufacturer(campaign.brand || '기타/미확인 브랜드');

    if (!result[manufacturer]) {
      result[manufacturer] = {
        manufacturer,
        totalCampaigns: 0,
        activeCampaigns: 0,
        resolvedCampaigns: 0,
        fireHazards: 0,
        lossOfPower: 0,
        affectedUnits: 0,
        completionRatePct: 0,
      };
    }

    const group = result[manufacturer];
    group.totalCampaigns++;
    const statusUpper = typeof campaign.status === 'string' ? campaign.status.trim().toUpperCase() : '';
    if (statusUpper === 'ACTIVE') {
      group.activeCampaigns++;
    } else if (statusUpper === 'RESOLVED') {
      group.resolvedCampaigns++;
    }

    if (campaign.risk_level === 'FIRE_HAZARD') group.fireHazards++;
    if (campaign.risk_level === 'LOSS_OF_POWER') group.lossOfPower++;

    if (Number.isFinite(campaign.affected_kdm_units) && campaign.affected_kdm_units > 0) {
      group.affectedUnits += campaign.affected_kdm_units;
    }
  }

  // Calculate resolution/completion rates with division-by-zero safeguard
  for (const key of Object.keys(result)) {
    const summary = result[key];
    summary.completionRatePct = calculateCampaignResolutionRate(
      summary.resolvedCampaigns,
      summary.totalCampaigns
    );
  }

  return result;
}

/**
 * Pure calculation of key recall and battery safety metrics from a RecallDatabase.
 * Employs strict division-by-zero guards and canonical manufacturer normalization.
 */
export function calculateRecallKPIs(customDb?: RecallDatabase): {
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
  resolvedCampaigns?: number;
  campaignResolutionRatePct?: number;
  totalAffectedVehicles?: number;
  activeFireHazards?: number;
  otaRemedyRate?: number;
  fireRiskBrandCount?: number;
  totalBatteryProfiles?: number;
} {
  const db = customDb || getRecallDatabase();
  const recalls = Array.isArray(db.recalls) ? db.recalls : [];
  const batteryProfiles = Array.isArray(db.battery_profiles) ? db.battery_profiles : [];

  const totalCampaigns = recalls.length;
  let activeCampaigns = 0;
  let resolvedCampaigns = 0;
  let totalAffectedVehicles = 0;
  let fireHazards = 0;
  let activeFireHazards = 0;
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

  const fireRiskBrands = new Set<string>();

  for (const campaign of recalls) {
    if (!campaign || typeof campaign !== 'object') continue;

    const statusUpper = typeof campaign.status === 'string' ? campaign.status.trim().toUpperCase() : '';
    if (statusUpper === 'ACTIVE') activeCampaigns++;
    else if (statusUpper === 'RESOLVED') resolvedCampaigns++;

    if (Number.isFinite(campaign.affected_kdm_units) && campaign.affected_kdm_units > 0) {
      totalAffectedVehicles += campaign.affected_kdm_units;
    }
    if (campaign.risk_level === 'FIRE_HAZARD') {
      fireHazards++;
      if (statusUpper === 'ACTIVE') activeFireHazards++;
      if (campaign.brand) fireRiskBrands.add(normalizeManufacturer(campaign.brand));
    }
    if (campaign.risk_level === 'LOSS_OF_POWER') lossOfPower++;
    if (campaign.remedy_type === 'OTA_WIRELESS') otaRemedies++;

    if (campaign.brand) {
      const canonical = normalizeManufacturer(campaign.brand);
      brandDistribution[canonical] = (brandDistribution[canonical] || 0) + 1;
    }

    if (campaign.risk_level && campaign.risk_level in riskLevelDistribution) {
      riskLevelDistribution[campaign.risk_level]++;
    }

    if (campaign.remedy_type && campaign.remedy_type in remedyTypeDistribution) {
      remedyTypeDistribution[campaign.remedy_type]++;
    }
  }

  const otaRemedyRatePct =
    totalCampaigns > 0 && Number.isFinite(totalCampaigns)
      ? Math.min(100, Math.max(0, Math.round((otaRemedies / totalCampaigns) * 1000) / 10))
      : 0;

  const campaignResolutionRatePct = calculateCampaignResolutionRate(
    resolvedCampaigns,
    totalCampaigns
  );

  const criticalMonitoringBatteryCount = batteryProfiles.filter(
    (bp) => bp && bp.fire_incident_status === 'CRITICAL_MONITORING'
  ).length;

  return {
    totalCampaigns,
    activeCampaigns,
    resolvedCampaigns,
    totalAffectedVehiclesKdm: totalAffectedVehicles,
    fireHazardCampaigns: fireHazards,
    lossOfPowerCampaigns: lossOfPower,
    otaRemedyCampaigns: otaRemedies,
    otaRemedyRatePct,
    campaignResolutionRatePct,
    criticalMonitoringBatteryCount,
    brandDistribution,
    riskLevelDistribution,
    remedyTypeDistribution,
    totalAffectedVehicles,
    activeFireHazards,
    otaRemedyRate: otaRemedyRatePct,
    fireRiskBrandCount: fireRiskBrands.size,
    totalBatteryProfiles: batteryProfiles.length,
  };
}

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
        badgeClass: 'bg-slate-800 text-slate-200 border-slate-600',
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
        badgeClass: 'bg-slate-800 text-slate-200 border-slate-600',
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
        badgeClass: 'bg-slate-800 text-slate-200 border-slate-600',
        icon: '🔍',
        labelKo: '점검 후 조치',
      };
    default:
      return {
        badgeClass: 'bg-slate-800 text-slate-200 border-slate-600',
        icon: 'ℹ️',
        labelKo: '조치 방법 미정',
      };
  }
}

