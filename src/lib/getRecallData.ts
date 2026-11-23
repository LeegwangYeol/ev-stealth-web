import rawRecallData from '../data/ev_recall_database.json' with { type: 'json' };
import { sanitizeSafeUrl } from './sanitizeUrl.ts';

import type {
  RecallRiskLevel,
  RemedyMethod,
  FireIncidentStatus,
  RecallAgency,
  RecallStatus,
  VinCheckMode,
  VinRiskGrade,
  OfficialRecallCampaign,
  BatterySafetyProfile,
  VinPrefixMapping,
  RecallDatabaseMetadata,
  RecallDatabase,
  VinCheckResult,
  RecallKPIs,
  ManufacturerRecallSummary,
} from '../types/recall.ts';

export type {
  RecallRiskLevel,
  RemedyMethod,
  FireIncidentStatus,
  RecallAgency,
  RecallStatus,
  VinCheckMode,
  VinRiskGrade,
  OfficialRecallCampaign,
  BatterySafetyProfile,
  VinPrefixMapping,
  RecallDatabaseMetadata,
  RecallDatabase,
  VinCheckResult,
  RecallKPIs,
  ManufacturerRecallSummary,
};

// Dangerous object property keys that could trigger prototype pollution or prototype lookup collisions
const DANGEROUS_PROTO_KEYS: ReadonlySet<string> = new Set([
  '__proto__',
  'constructor',
  'prototype',
  'tostring',
  'valueof',
  'hasownproperty',
  'isprototypeof',
  'propertyisenumerable',
  'tolocalestring',
  '__definegetter__',
  '__definesetter__',
  '__lookupgetter__',
  '__lookupsetter__',
]);

const ENGLISH_MONTH_MAP: Readonly<Record<string, number>> = Object.freeze({
  jan: 1,
  january: 1,
  feb: 2,
  february: 2,
  mar: 3,
  march: 3,
  apr: 4,
  april: 4,
  may: 5,
  jun: 6,
  june: 6,
  jul: 7,
  july: 7,
  aug: 8,
  august: 8,
  sep: 9,
  sept: 9,
  september: 9,
  oct: 10,
  october: 10,
  nov: 11,
  november: 11,
  dec: 12,
  december: 12,
});

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

// Year code mapping according to ISO 3779 standard (Position 10, 2010 - 2030)
export const VIN_YEAR_MAP: Readonly<Record<string, number>> = Object.freeze({
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
});

// Known WMI prefixes fallback (Positions 1-3)
export const WMI_MAP: Readonly<Record<string, { brand: string; country: string }>> = Object.freeze({
  KM8: Object.freeze({ brand: '현대자동차', country: '대한민국' }),
  KMH: Object.freeze({ brand: '제네시스', country: '대한민국' }),
  KMF: Object.freeze({ brand: '현대자동차', country: '대한민국 (상용/포터 EV)' }),
  KND: Object.freeze({ brand: '기아', country: '대한민국' }),
  KNA: Object.freeze({ brand: '기아', country: '대한민국' }),
  KNC: Object.freeze({ brand: '기아', country: '대한민국 (상용/봉고 EV)' }),
  KNM: Object.freeze({ brand: '르노코리아', country: '대한민국' }),
  KPT: Object.freeze({ brand: 'KG모빌리티', country: '대한민국' }),
  '5YJ': Object.freeze({ brand: '테슬라', country: '미국 (캘리포니아 프리몬트)' }),
  '7SA': Object.freeze({ brand: '테슬라', country: '미국 (텍사스 오스틴)' }),
  LRW: Object.freeze({ brand: '테슬라', country: '중국 (상하이 기가팩토리)' }),
  XP7: Object.freeze({ brand: '테슬라', country: '독일 (베를린 기가팩토리)' }),
  W1K: Object.freeze({ brand: '메르세데스-벤츠', country: '독일' }),
  WDD: Object.freeze({ brand: '메르세데스-벤츠', country: '독일' }),
  WDC: Object.freeze({ brand: '메르세데스-벤츠', country: '독일' }),
  '4JG': Object.freeze({ brand: '메르세데스-벤츠', country: '미국 (앨라배마 터스컬루사)' }),
  WBA: Object.freeze({ brand: 'BMW', country: '독일' }),
  WBY: Object.freeze({ brand: 'BMW i', country: '독일' }),
  WBX: Object.freeze({ brand: 'BMW', country: '독일' }),
  LGX: Object.freeze({ brand: 'BYD', country: '중국' }),
  '1G1': Object.freeze({ brand: '쉐보레', country: '미국' }),
  KL3: Object.freeze({ brand: '쉐보레', country: '대한민국 (한국지엠)' }),
  LPS: Object.freeze({ brand: '폴스타', country: '중국' }),
  WP0: Object.freeze({ brand: '포르쉐', country: '독일' }),
  WAU: Object.freeze({ brand: '아우디', country: '독일' }),
  WA1: Object.freeze({ brand: '아우디', country: '독일' }),
  WVW: Object.freeze({ brand: '폭스바겐', country: '독일' }),
  WVG: Object.freeze({ brand: '폭스바겐', country: '독일' }),
  YV1: Object.freeze({ brand: '볼보', country: '스웨덴' }),
  YV4: Object.freeze({ brand: '볼보', country: '스웨덴' }),
});

// Canonical manufacturer mapping resolving synonyms, casing, and localized brand names
export const CANONICAL_MANUFACTURER_MAP: Readonly<Record<string, string>> = Object.freeze({
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
});

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

  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
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

  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
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

  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
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
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return { valid: false, errors: ['Database root must be a non-null object'] };
  }

  const db = raw as Partial<RecallDatabase>;

  if (!db.metadata || typeof db.metadata !== 'object' || Array.isArray(db.metadata)) {
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
      version: typeof db.metadata?.version === 'string' && db.metadata.version.trim() ? db.metadata.version : '1.0.0',
      updated_at: typeof db.metadata?.updated_at === 'string' && db.metadata.updated_at.trim() ? db.metadata.updated_at : new Date().toISOString(),
      ...(typeof db.metadata?.last_updated === 'string' && db.metadata.last_updated.trim()
        ? { last_updated: db.metadata.last_updated }
        : {}),
      total_campaigns:
        typeof db.metadata?.total_campaigns === 'number' && Number.isFinite(db.metadata.total_campaigns) && db.metadata.total_campaigns >= 0
          ? db.metadata.total_campaigns + 0
          : validRecalls.length,
      total_affected_vehicles_kdm:
        typeof db.metadata?.total_affected_vehicles_kdm === 'number' && Number.isFinite(db.metadata.total_affected_vehicles_kdm) && db.metadata.total_affected_vehicles_kdm >= 0
          ? db.metadata.total_affected_vehicles_kdm + 0
          : validRecalls.reduce((sum, r) => {
              const units = Number.isFinite(r.affected_kdm_units) && r.affected_kdm_units > 0 ? r.affected_kdm_units : 0;
              const next = sum + units;
              return Number.isFinite(next) ? next : Number.MAX_VALUE;
            }, 0),
      active_fire_campaigns:
        typeof db.metadata?.active_fire_campaigns === 'number' && Number.isFinite(db.metadata.active_fire_campaigns) && db.metadata.active_fire_campaigns >= 0
          ? db.metadata.active_fire_campaigns + 0
          : validRecalls.filter((r) => r.risk_level === 'FIRE_HAZARD' && r.status === 'ACTIVE').length,
      ota_remedy_rate_pct:
        typeof db.metadata?.ota_remedy_rate_pct === 'number' &&
        Number.isFinite(db.metadata.ota_remedy_rate_pct) &&
        db.metadata.ota_remedy_rate_pct >= 0 &&
        db.metadata.ota_remedy_rate_pct <= 100
          ? db.metadata.ota_remedy_rate_pct + 0
          : (validRecalls.length > 0
              ? Math.round((validRecalls.filter((r) => r.remedy_type === 'OTA_WIRELESS').length / validRecalls.length) * 1000) / 10 + 0
              : 0),
      ...(Array.isArray(db.metadata?.data_sources)
        ? { data_sources: db.metadata.data_sources.filter((s): s is string => typeof s === 'string') }
        : {}),
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
  if (key && Object.prototype.hasOwnProperty.call(CANONICAL_MANUFACTURER_MAP, key)) {
    return CANONICAL_MANUFACTURER_MAP[key];
  }

  const keyWithSpaces = cleaned.toLowerCase().replace(/\s+/g, ' ');
  if (keyWithSpaces && Object.prototype.hasOwnProperty.call(CANONICAL_MANUFACTURER_MAP, keyWithSpaces)) {
    return CANONICAL_MANUFACTURER_MAP[keyWithSpaces];
  }

  return cleaned;
}

let cachedRecallDatabase: RecallDatabase | null = null;

function cloneRecallDatabase(db: RecallDatabase): RecallDatabase {
  return {
    metadata: {
      ...db.metadata,
      ...(Array.isArray(db.metadata.data_sources)
        ? { data_sources: [...db.metadata.data_sources] }
        : {}),
    },
    vin_prefixes: db.vin_prefixes.map((vp) => ({ ...vp })),
    battery_profiles: db.battery_profiles.map((bp) => ({ ...bp })),
    recalls: db.recalls.map((r) => ({ ...r })),
  };
}

/**
 * Main safe loader for the EV Recall Database with strict schema validation
 * and defensive defaults. Caches validated static JSON payload for high-throughput reuse.
 */
export function getRecallDatabase(): RecallDatabase {
  if (cachedRecallDatabase) {
    return cloneRecallDatabase(cachedRecallDatabase);
  }
  try {
    const validated = validateRecallDatabaseSchema(rawRecallData);
    if (validated.database) {
      // Ensure official URLs are safely sanitized
      const sanitizedRecalls = validated.database.recalls.map((r) => ({
        ...r,
        official_link: sanitizeSafeUrl(r.official_link),
      }));
      cachedRecallDatabase = {
        ...validated.database,
        recalls: sanitizedRecalls,
      };
      return cloneRecallDatabase(cachedRecallDatabase);
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
    if (!Object.prototype.hasOwnProperty.call(transliteration, ch)) return null;
    const val = transliteration[ch];
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

function normalizeModelStr(str: string): string {
  return str.toLowerCase().replace(/[\s\-_/()[\]+.,&]+/g, '');
}

function cleanModelBase(name: string): string {
  return name.replace(/\s*\([^)]*\)/g, '').trim();
}

function stripNonModelNumericTokens(str: string): string {
  return str
    .replace(/\b(?:19|20)\d{2}(?:my)?\b/gi, '')
    .replace(/\b[24]wd\b/gi, '')
    .replace(/(?<![0-9])\d+\s*세대(?![0-9])/g, '')
    .replace(/\b\d+(?:\.\d+)?\s*kwh\b/gi, '');
}

// Safely extracts model designation digits while ignoring drivetrains (2WD/4WD),
// generation counters (1세대, 2세대), 4-digit years (2020-2030, 2024MY), and battery capacities (77.4kWh)
function extractModelDigits(str: string): string[] {
  return stripNonModelNumericTokens(str).match(/\d+/g) || [];
}

// Expands slash-separated trims while preserving base model prefix (e.g. "i4 eDrive40 / M50" -> ["i4 edrive40 / m50", "i4 edrive40", "i4 m50"])
function expandSlashVariants(raw: string): string[] {
  const parts = raw.split('/').map((s) => s.trim()).filter(Boolean);
  if (parts.length <= 1) return [raw];
  const variants: string[] = [raw, parts[0]];
  const firstWords = parts[0].split(/\s+/);
  const basePrefix = firstWords.length > 1 ? firstWords[0] : '';
  for (let i = 1; i < parts.length; i++) {
    const part = parts[i];
    if (basePrefix && !part.startsWith(basePrefix)) {
      variants.push(`${basePrefix} ${part}`);
    } else {
      variants.push(part);
    }
  }
  return variants;
}

function hasAttachedDigitTokenCollision(a: string, b: string): boolean {
  const tokensA = stripNonModelNumericTokens(a).toLowerCase().split(/[^a-z0-9가-힣]+/).filter(Boolean);
  const tokensB = stripNonModelNumericTokens(b).toLowerCase().split(/[^a-z0-9가-힣]+/).filter(Boolean);

  const checkPair = (bareList: string[], suffixedList: string[]): boolean => {
    for (const bare of bareList) {
      if (!/^[a-z가-힣]+$/.test(bare)) continue;
      for (const tok of suffixedList) {
        const m = tok.match(/^([a-z가-힣]+)\d+$/);
        if (m && m[1] === bare) {
          return true;
        }
      }
    }
    return false;
  };

  return checkPair(tokensA, tokensB) || checkPair(tokensB, tokensA);
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

  const queryClean = cleanModelBase(queryModel).toLowerCase();
  const queryNorm = normalizeModelStr(queryClean);

  // Require query to contain at least one alphanumeric or Korean character
  if (!queryNorm || !/[a-zA-Z0-9가-힣]/.test(queryNorm)) {
    return false;
  }

  const queryNums = extractModelDigits(queryClean);
  const queryLetter = queryClean.match(/(?:모델|model)\s*([a-z0-9])/i);

  const passesCollisionGuards = (
    candidate: string,
    candidateNums: string[],
    target: string,
    targetNums: string[]
  ): boolean => {
    // 1. Number collision check: e.g. "아이오닉 5" vs "아이오닉 6", "EV6" vs "EV9"
    if (candidateNums.length > 0 && targetNums.length > 0 && candidateNums.join(',') !== targetNums.join(',')) {
      return false;
    }

    // 1b. Attached-digit model code check: e.g. "iX" vs "iX3", "GV" vs "GV60"
    if (hasAttachedDigitTokenCollision(candidate, target)) {
      return false;
    }

    // 2. EV / Electric vs Numbered EV check (e.g. "아이오닉 EV" vs "아이오닉 5")
    const candidateHasEv = /\bev(?:\b|(?=\d+\s*세대))|일렉트릭/i.test(candidate);
    const targetHasEv = /\bev(?:\b|(?=\d+\s*세대))|일렉트릭/i.test(target);
    if (!candidateHasEv && candidateNums.length > 0 && !targetNums.length && targetHasEv) {
      return false;
    }
    if (!targetHasEv && targetNums.length > 0 && !candidateNums.length && candidateHasEv) {
      return false;
    }

    // 3. Model single-letter designation (e.g. "모델 Y" vs "모델 3/S/X")
    const candidateLetter = candidate.match(/(?:모델|model)\s*([a-z0-9])/i) || queryLetter;
    const targetLetter = target.match(/(?:모델|model)\s*([a-z0-9])/i);
    if (candidateLetter && targetLetter && candidateLetter[1] !== targetLetter[1]) {
      return false;
    }

    return true;
  };

  const rawTargets = campaignTargetModel.split(',').map((t) => cleanModelBase(t).toLowerCase()).filter(Boolean);
  const targets = rawTargets.flatMap((t) => expandSlashVariants(t));
  const subTrims = cleanModelBase(queryModel)
    .split(',')
    .map((s) => s.toLowerCase().trim())
    .filter(Boolean)
    .flatMap((s) => expandSlashVariants(s));

  const preparedSubTrims =
    subTrims.length > 1
      ? subTrims
          .map((sub) => {
            const subNorm = normalizeModelStr(sub);
            return { sub, subNorm, subNums: extractModelDigits(sub) };
          })
          .filter((entry) => entry.subNorm && /[a-zA-Z0-9가-힣]/.test(entry.subNorm))
      : [];

  for (const target of targets) {
    const targetNorm = normalizeModelStr(target);
    if (!targetNorm || !/[a-zA-Z0-9가-힣]/.test(targetNorm)) {
      continue;
    }

    // Exact normalized match (e.g. "아이오닉5" === "아이오닉5", "ev6" === "ev6")
    if (queryNorm === targetNorm) return true;

    const targetNums = extractModelDigits(target);

    // Check containment while guarding against collisions
    if (
      (targetNorm.includes(queryNorm) || queryNorm.includes(targetNorm)) &&
      passesCollisionGuards(queryClean, queryNums, target, targetNums)
    ) {
      return true;
    }

    // Sub-trims in query (e.g. "볼트 EV / EUV" matching "볼트 EV", "i4 eDrive40 / M50" matching "i4 M50")
    for (const { sub, subNorm, subNums } of preparedSubTrims) {
      if (
        (subNorm === targetNorm || targetNorm.includes(subNorm) || subNorm.includes(targetNorm)) &&
        passesCollisionGuards(sub, subNums, target, targetNums)
      ) {
        return true;
      }
    }
  }

  return false;
}

/**
 * Validates and constructs a UTC Date without calendar rollover (1990-2040).
 */
function buildValidatedUtcDate(year: number, month: number, day: number): Date | null {
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

  // 1. Try standard regex pattern for YYYY.MM.DD, YYYY-MM-DD, YYYY/MM/DD (with optional validated time suffix)
  const delimiterMatch = clean.match(
    /^(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})(?:$|(?:T|\s+)(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(?:Z|([+-])(\d{2}):?(\d{2}))?$)/i
  );
  if (delimiterMatch) {
    const year = parseInt(delimiterMatch[1], 10);
    const month = parseInt(delimiterMatch[2], 10);
    const day = parseInt(delimiterMatch[3], 10);
    const baseDate = buildValidatedUtcDate(year, month, day);
    if (!baseDate) {
      return null;
    }
    if (delimiterMatch[4] !== undefined) {
      const hour = parseInt(delimiterMatch[4], 10);
      const minute = parseInt(delimiterMatch[5], 10);
      const second = delimiterMatch[6] !== undefined ? parseInt(delimiterMatch[6], 10) : 0;
      if (hour > 23 || minute > 59 || second > 59) {
        return null;
      }
      let offsetMinutes = 0;
      if (delimiterMatch[8] !== undefined) {
        const tzHour = parseInt(delimiterMatch[8], 10);
        const tzMin = parseInt(delimiterMatch[9], 10);
        if (tzHour > 23 || tzMin > 59) {
          return null;
        }
        const sign = delimiterMatch[7] === '-' ? -1 : 1;
        offsetMinutes = sign * (tzHour * 60 + tzMin);
      }
      const utcMs = Date.UTC(year, month - 1, day, hour, minute, second) - offsetMinutes * 60_000;
      const d = new Date(utcMs);
      const utcYear = d.getUTCFullYear();
      if (isNaN(d.getTime()) || utcYear < 1990 || utcYear > 2040) {
        return null;
      }
      return d;
    }
    return baseDate;
  }

  // 1b. Korean dot notation with optional spaces & trailing dot: "2024. 3. 18." or "2024. 03. 18"
  const spacedDotMatch = clean.match(/^(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.?$/);
  if (spacedDotMatch) {
    return buildValidatedUtcDate(
      parseInt(spacedDotMatch[1], 10),
      parseInt(spacedDotMatch[2], 10),
      parseInt(spacedDotMatch[3], 10)
    );
  }

  // 2. Try Korean date notation: YYYY년 MM월 DD일
  const koreanDateMatch = clean.match(/^(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일$/);
  if (koreanDateMatch) {
    return buildValidatedUtcDate(
      parseInt(koreanDateMatch[1], 10),
      parseInt(koreanDateMatch[2], 10),
      parseInt(koreanDateMatch[3], 10)
    );
  }

  // 3. Try YYYYMMDD compact format
  const compactMatch = clean.match(/^(\d{4})(\d{2})(\d{2})$/);
  if (compactMatch) {
    return buildValidatedUtcDate(
      parseInt(compactMatch[1], 10),
      parseInt(compactMatch[2], 10),
      parseInt(compactMatch[3], 10)
    );
  }

  // 4. Explicit UTC parsing for English month-name dates (avoids local-timezone shift and V8 calendar rollover)
  const monthFirstMatch = clean.match(
    /^([a-z]{3,9})\.?[\s\-/]+(\d{1,2})(?:st|nd|rd|th)?(?:,)?[\s\-/]+(\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?$/i
  );
  if (monthFirstMatch) {
    if (monthFirstMatch[4] !== undefined) {
      const hour = parseInt(monthFirstMatch[4], 10);
      const minute = parseInt(monthFirstMatch[5], 10);
      const second = monthFirstMatch[6] !== undefined ? parseInt(monthFirstMatch[6], 10) : 0;
      if (hour > 23 || minute > 59 || second > 59) return null;
    }
    const mKey = monthFirstMatch[1].toLowerCase();
    const month = Object.prototype.hasOwnProperty.call(ENGLISH_MONTH_MAP, mKey) ? ENGLISH_MONTH_MAP[mKey] : undefined;
    if (!month) return null;
    return buildValidatedUtcDate(parseInt(monthFirstMatch[3], 10), month, parseInt(monthFirstMatch[2], 10));
  }

  const dayFirstMatch = clean.match(
    /^(\d{1,2})(?:st|nd|rd|th)?[\s\-/]+([a-z]{3,9})\.?(?:,)?[\s\-/]+(\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?$/i
  );
  if (dayFirstMatch) {
    if (dayFirstMatch[4] !== undefined) {
      const hour = parseInt(dayFirstMatch[4], 10);
      const minute = parseInt(dayFirstMatch[5], 10);
      const second = dayFirstMatch[6] !== undefined ? parseInt(dayFirstMatch[6], 10) : 0;
      if (hour > 23 || minute > 59 || second > 59) return null;
    }
    const mKey = dayFirstMatch[2].toLowerCase();
    const month = Object.prototype.hasOwnProperty.call(ENGLISH_MONTH_MAP, mKey) ? ENGLISH_MONTH_MAP[mKey] : undefined;
    if (!month) return null;
    return buildValidatedUtcDate(parseInt(dayFirstMatch[3], 10), month, parseInt(dayFirstMatch[1], 10));
  }

  const yearFirstMonthNameMatch = clean.match(
    /^(\d{4})[\s\-/]+([a-z]{3,9})\.?[\s\-/]+(\d{1,2})(?:st|nd|rd|th)?(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?$/i
  );
  if (yearFirstMonthNameMatch) {
    if (yearFirstMonthNameMatch[4] !== undefined) {
      const hour = parseInt(yearFirstMonthNameMatch[4], 10);
      const minute = parseInt(yearFirstMonthNameMatch[5], 10);
      const second = yearFirstMonthNameMatch[6] !== undefined ? parseInt(yearFirstMonthNameMatch[6], 10) : 0;
      if (hour > 23 || minute > 59 || second > 59) return null;
    }
    const mKey = yearFirstMonthNameMatch[2].toLowerCase();
    const month = Object.prototype.hasOwnProperty.call(ENGLISH_MONTH_MAP, mKey) ? ENGLISH_MONTH_MAP[mKey] : undefined;
    if (!month) return null;
    return buildValidatedUtcDate(parseInt(yearFirstMonthNameMatch[1], 10), month, parseInt(yearFirstMonthNameMatch[3], 10));
  }

  // 5. Fallback to standard Date.parse only for explicit RFC/ISO timestamps with a 4-digit year
  // Guards against V8 Date.parse quirks where "아이오닉 5" or "12" parse as year 2001,
  // and rejects V8 calendar rollover (e.g. "Feb 31, 2024 GMT", "2024-02-31 12:00:00 GMT", "2024-Feb-31").
  const hasFourDigitYear = /(?:19|20)\d{2}/.test(clean);
  const looksLikeIsoOrEnglishDate =
    /^\d{4}-\d{2}-\d{2}[T ]/.test(clean) ||
    /\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b/i.test(clean);
  if (!hasFourDigitYear || !looksLikeIsoOrEnglishDate) {
    return null;
  }

  const leadingNumericDate = clean.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?![0-9])/);
  if (leadingNumericDate) {
    if (
      !buildValidatedUtcDate(
        parseInt(leadingNumericDate[1], 10),
        parseInt(leadingNumericDate[2], 10),
        parseInt(leadingNumericDate[3], 10)
      )
    ) {
      return null;
    }
  }

  const rfcMonthDay =
    clean.match(/\b([a-z]{3,9})[\s\-/.,]+(\d{1,2})(?:st|nd|rd|th)?[\s\-/.,]+(\d{4})\b/i) ||
    clean.match(/\b(\d{1,2})(?:st|nd|rd|th)?[\s\-/.,]+([a-z]{3,9})[\s\-/.,]+(\d{4})\b/i) ||
    clean.match(/\b(\d{4})[\s\-/.,]+([a-z]{3,9})[\s\-/.,]+(\d{1,2})(?:st|nd|rd|th)?\b/i);
  if (rfcMonthDay) {
    let mKey: string;
    let dayNum: number;
    let yearNum: number;
    if (/^\d{4}$/.test(rfcMonthDay[1])) {
      yearNum = parseInt(rfcMonthDay[1], 10);
      mKey = rfcMonthDay[2].toLowerCase();
      dayNum = parseInt(rfcMonthDay[3], 10);
    } else if (/^[a-z]/i.test(rfcMonthDay[1])) {
      mKey = rfcMonthDay[1].toLowerCase();
      dayNum = parseInt(rfcMonthDay[2], 10);
      yearNum = parseInt(rfcMonthDay[3], 10);
    } else {
      dayNum = parseInt(rfcMonthDay[1], 10);
      mKey = rfcMonthDay[2].toLowerCase();
      yearNum = parseInt(rfcMonthDay[3], 10);
    }
    const monthNum = Object.prototype.hasOwnProperty.call(ENGLISH_MONTH_MAP, mKey)
      ? ENGLISH_MONTH_MAP[mKey]
      : undefined;
    if (monthNum && !buildValidatedUtcDate(yearNum, monthNum, dayNum)) {
      return null;
    }
  }

  // Enforce UTC when no explicit timezone suffix is present so Date.parse never shifts dates via local TZ
  const hasExplicitTz = /(?:Z|GMT|UTC|UT|[ECMP][SD]T|[+-]\d{2}:?\d{2})(?:\s*\([^)]+\))?\s*$/i.test(clean);
  const timestamp = Date.parse(hasExplicitTz ? clean : `${clean} UTC`);
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
    const matches = Array.from(clean.matchAll(/(?<![0-9])(19\d\d|20\d\d)(?![0-9])/g));
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
  if (typeof input === 'object' && !Array.isArray(input)) {
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

    // 1. Explicit recall_date / date
    if (typeof c.recall_date === 'string') {
      const parsed = parseRecallDate(c.recall_date);
      if (parsed) return parsed.getTime();
    }
    if (typeof c.date === 'string') {
      const parsed = parseRecallDate(c.date);
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

    // 3. End date (or start date if open-ended) of production_date_range
    if (typeof c.production_date_range === 'string') {
      const rangeParts = c.production_date_range.split(/[~–—]|\s+-\s+/);
      const endDateStr = (rangeParts[1] || rangeParts[0] || '').trim();
      const parsedEnd = parseRecallDate(endDateStr);
      if (parsedEnd) return parsedEnd.getTime();
      if (rangeParts[1] && rangeParts[0]) {
        const parsedStart = parseRecallDate(rangeParts[0].trim());
        if (parsedStart) return parsedStart.getTime();
      }
    }

    // 4. Target model year or ID year
    const yr = extractRecallYear(c);
    if (yr) {
      return new Date(Date.UTC(yr, 0, 1)).getTime();
    }

    return -1;
  };

  // Schwartzian transform: compute sort timestamps once per item (O(N)) rather than per comparison
  const decorated = recalls.map((item) => ({
    item,
    time: getSortTimestamp(item),
  }));

  decorated.sort((a, b) => {
    if (a.time === b.time) return 0;

    // Items with invalid/missing date sort to the bottom
    if (a.time === -1) return 1;
    if (b.time === -1) return -1;

    return order === 'asc' ? a.time - b.time : b.time - a.time;
  });

  return decorated.map((d) => d.item);
}

/**
 * Checks whether a given model year falls within a campaign's target_model_years string.
 * Safely guards against NaN, non-finite values, negative numbers, and future date anomalies.
 */
export function isYearMatchForCampaign(year?: number, targetModelYears?: string): boolean {
  if (year === undefined || year === null) return true;
  if (
    typeof year !== 'number' ||
    !Number.isFinite(year) ||
    !Number.isInteger(year) ||
    year < 1990 ||
    year > 2040
  ) {
    return false;
  }
  if (!targetModelYears || typeof targetModelYears !== 'string' || !targetModelYears.trim()) return true;

  // Clean target string: remove Korean year particle "년", "년식", "년형" and month/day sub-tokens
  const cleanTarget = targetModelYears
    .replace(/년(?:식|형)?/g, '')
    .replace(/(?<![0-9])\d{1,2}\s*월(?:\s*\d{1,2}\s*일)?/g, '')
    .trim();

  // Split disjoint segments separated by comma or semicolon
  const segments = cleanTarget.split(/[,;]/).map((s) => s.trim()).filter(Boolean);
  if (segments.length === 0) return true;

  let hasValidSegment = false;

  for (const segment of segments) {
    // 1. Closed range: "2021 ~ 2024", "2021-2024", "2021.03 ~ 2024.05", or "2021-03-01 ~ 2024-05-01"
    const rangeMatch = segment.match(
      /(?<![0-9])((?:19|20)\d{2})(?:[.\-/]\d{1,2}(?![0-9])(?:[.\-/]\d{1,2}(?![0-9]))?)?\s*[~–—-]\s*((?:19|20)\d{2})(?:[.\-/]\d{1,2}(?![0-9])(?:[.\-/]\d{1,2}(?![0-9]))?)?(?![0-9])/
    );
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
    const openRangeMatch = segment.match(
      /(?<![0-9])((?:19|20)\d{2})(?:[.\-/]\d{1,2}(?![0-9])(?:[.\-/]\d{1,2}(?![0-9]))?)?\s*(?:[~–—-]\s*)?(?:현재|present|이후|\+)|(?<![0-9])((?:19|20)\d{2})(?:[.\-/]\d{1,2}(?![0-9])(?:[.\-/]\d{1,2}(?![0-9]))?)?\s*[~–—-]\s*$/i
    );
    if (openRangeMatch) {
      hasValidSegment = true;
      const start = parseInt(openRangeMatch[1] || openRangeMatch[2], 10);
      if (year >= start && year <= 2040) return true;
      continue;
    }

    // 3. Before range: "2022 이전", "~ 2022", "~2022"
    const beforeRangeMatch = segment.match(
      /(?:^\s*[~–—-]\s*((?:19|20)\d{2})(?:[.\-/]\d{1,2}(?![0-9])(?:[.\-/]\d{1,2}(?![0-9]))?)?(?![0-9]))|(?:(?<![0-9])((?:19|20)\d{2})(?:[.\-/]\d{1,2}(?![0-9])(?:[.\-/]\d{1,2}(?![0-9]))?)?\s*(?:이전|까지|before))/i
    );
    if (beforeRangeMatch) {
      hasValidSegment = true;
      const end = parseInt(beforeRangeMatch[1] || beforeRangeMatch[2], 10);
      if (year >= 1990 && year <= end) return true;
      continue;
    }

    // 4. Single year match: "2022"
    const singleYearMatch = segment.match(/(?<![0-9])((?:19|20)\d{2})(?![0-9])/);
    if (singleYearMatch) {
      hasValidSegment = true;
      if (parseInt(singleYearMatch[1], 10) === year) {
        return true;
      }
    }
  }

  return !hasValidSegment;
}

const SORTED_VIN_PREFIX_CACHE = new WeakMap<
  VinPrefixMapping[],
  {
    snapshot: Array<{ ref: VinPrefixMapping; prefix: unknown }>;
    sorted: Array<{ entry: VinPrefixMapping; prefixUpper: string }>;
  }
>();

function getSortedVinPrefixes(
  vinPrefixes: VinPrefixMapping[]
): Array<{ entry: VinPrefixMapping; prefixUpper: string }> {
  const cached = SORTED_VIN_PREFIX_CACHE.get(vinPrefixes);
  if (
    cached &&
    cached.snapshot.length === vinPrefixes.length &&
    cached.snapshot.every((s, idx) => s.ref === vinPrefixes[idx] && s.prefix === vinPrefixes[idx]?.prefix)
  ) {
    return cached.sorted;
  }

  const snapshot = vinPrefixes.map((entry) => ({ ref: entry, prefix: entry?.prefix }));
  const sorted = vinPrefixes
    .filter((p) => p && typeof p.prefix === 'string' && p.prefix.trim().length > 0)
    .map((entry) => ({ entry, prefixUpper: entry.prefix.trim().toUpperCase() }))
    .sort((a, b) => b.prefixUpper.length - a.prefixUpper.length);

  SORTED_VIN_PREFIX_CACHE.set(vinPrefixes, { snapshot, sorted });
  return sorted;
}

function isBrandCompatibleForLookup(
  queryBrandLower: string,
  queryCanonical: string,
  targetBrand?: string
): boolean {
  if (!targetBrand || typeof targetBrand !== 'string') return false;
  const targetClean = targetBrand.trim().toLowerCase();
  if (!targetClean) return false;
  const targetCanonical = normalizeManufacturer(targetBrand);
  const allowSubstring = queryBrandLower.length >= 2 && targetClean.length >= 2;
  return (
    (Boolean(queryCanonical) && targetCanonical === queryCanonical) ||
    targetClean === queryBrandLower ||
    (allowSubstring && (targetClean.includes(queryBrandLower) || queryBrandLower.includes(targetClean))) ||
    (Boolean(targetCanonical) &&
      Boolean(queryCanonical) &&
      targetCanonical.length >= 2 &&
      queryCanonical.length >= 2 &&
      (targetCanonical.toLowerCase().includes(queryCanonical.toLowerCase()) ||
        queryCanonical.toLowerCase().includes(targetCanonical.toLowerCase())))
  );
}

const BRAND_WORD_BOUNDARY_REGEX_CACHE = new Map<string, RegExp>();

function matchesTargetBrandMention(campTargetLower: string, brandTermLower: string): boolean {
  if (!brandTermLower || brandTermLower.length < 2) return false;
  if (/^[a-z0-9]+$/i.test(brandTermLower) && brandTermLower.length < 3) {
    let re = BRAND_WORD_BOUNDARY_REGEX_CACHE.get(brandTermLower);
    if (!re) {
      const escaped = brandTermLower.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      re = new RegExp(`\\b${escaped}\\b`, 'i');
      if (BRAND_WORD_BOUNDARY_REGEX_CACHE.size < 256) {
        BRAND_WORD_BOUNDARY_REGEX_CACHE.set(brandTermLower, re);
      }
    }
    return re.test(campTargetLower);
  }
  return campTargetLower.includes(brandTermLower);
}

function deduplicateRecallsById(recalls: OfficialRecallCampaign[]): OfficialRecallCampaign[] {
  if (recalls.length <= 1) return recalls;
  const seenKeys = new Set<string>();
  const deduped: OfficialRecallCampaign[] = [];
  for (const r of recalls) {
    const idKey = typeof r.id === 'string' ? r.id.trim().toLowerCase() : '';
    if (idKey) {
      const key = `id:${idKey}`;
      if (seenKeys.has(key)) continue;
      seenKeys.add(key);
    } else {
      const campNo = typeof r.campaign_no === 'string' ? r.campaign_no.trim().toLowerCase() : '';
      if (campNo) {
        const brandKey = typeof r.brand === 'string' ? normalizeManufacturer(r.brand).toLowerCase() : '';
        const modelKey = typeof r.target_model === 'string' ? r.target_model.trim().toLowerCase() : '';
        const key = `camp:${campNo}::${brandKey}::${modelKey}`;
        if (seenKeys.has(key)) continue;
        seenKeys.add(key);
      }
    }
    deduped.push(r);
  }
  return deduped;
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
  const yearChar = vin.charAt(9).toUpperCase();
  const decodedYear = Object.prototype.hasOwnProperty.call(VIN_YEAR_MAP, yearChar)
    ? VIN_YEAR_MAP[yearChar]
    : undefined;

  // 2. Decode Prefix (WMI + VDS)
  const vinPrefixes = Array.isArray(db.vin_prefixes) ? db.vin_prefixes : [];
  const sortedPrefixes = getSortedVinPrefixes(vinPrefixes);
  const matchedPrefix = sortedPrefixes.find((p) => vin.startsWith(p.prefixUpper))?.entry;

  let decodedBrand = typeof matchedPrefix?.brand === 'string' ? matchedPrefix.brand.trim() || undefined : undefined;
  const decodedModel = typeof matchedPrefix?.model_name === 'string' ? matchedPrefix.model_name.trim() || undefined : undefined;
  let decodedCountry = typeof matchedPrefix?.country === 'string' ? matchedPrefix.country.trim() || undefined : undefined;

  // If no exact prefix match, fallback to WMI (first 3 chars)
  if (!decodedBrand) {
    const wmiMatch = Object.prototype.hasOwnProperty.call(WMI_MAP, wmi) ? WMI_MAP[wmi] : undefined;
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

  const batteryProfiles = Array.isArray(db.battery_profiles) ? db.battery_profiles : [];
  const recalls = Array.isArray(db.recalls) ? db.recalls : [];

  const decodedBrandLower = decodedBrand.toLowerCase();
  const decodedCanonical = normalizeManufacturer(decodedBrand);
  const decodedCanonicalLower = decodedCanonical.toLowerCase();

  // 3. Match Battery Profile (prefer brand-compatible & year-matching profile when multiple trims exist)
  let matchedBatteryProfile: BatterySafetyProfile | undefined;
  if (decodedModel) {
    const modelMatches = batteryProfiles.filter((bp) => {
      if (!bp || typeof bp !== 'object' || typeof bp.model_name !== 'string') return false;
      if (
        decodedBrand !== '기타/미확인 브랜드' &&
        typeof bp.brand === 'string' &&
        bp.brand.trim() &&
        !isBrandCompatibleForLookup(decodedBrandLower, decodedCanonical, bp.brand)
      ) {
        return false;
      }
      return isModelMatchForCampaign(decodedModel, bp.model_name);
    });
    if (modelMatches.length > 0) {
      matchedBatteryProfile =
        (decodedYear !== undefined
          ? modelMatches.find((bp) => typeof bp.years === 'string' && bp.years.trim() && isYearMatchForCampaign(decodedYear, bp.years))
          : undefined) || modelMatches[0];
    }
  }

  // 4. Match Recall Campaigns
  const matchingRecalls = deduplicateRecallsById(recalls.filter((campaign) => {
    if (
      !campaign ||
      typeof campaign !== 'object' ||
      typeof campaign.brand !== 'string' ||
      !campaign.brand.trim() ||
      typeof campaign.target_model !== 'string' ||
      !campaign.target_model.trim()
    ) {
      return false;
    }
    if (!decodedBrand || decodedBrand === '기타/미확인 브랜드') return false;

    const campCanonical = normalizeManufacturer(campaign.brand);
    const campTargetLower = campaign.target_model.trim().toLowerCase();

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
      genesisMatches ||
      isBrandCompatibleForLookup(decodedBrandLower, decodedCanonical, campaign.brand) ||
      matchesTargetBrandMention(campTargetLower, decodedBrandLower) ||
      matchesTargetBrandMention(campTargetLower, decodedCanonicalLower);

    if (!brandMatches) return false;

    if (decodedModel && !isModelMatchForCampaign(decodedModel, campaign.target_model)) {
      return false;
    }

    if (decodedYear !== undefined && !isYearMatchForCampaign(decodedYear, campaign.target_model_years)) {
      return false;
    }

    return true;
  }));

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
  const validYear =
    typeof year === 'number' && Number.isFinite(year) && Number.isInteger(year) && year >= 1990 && year <= 2040
      ? year
      : undefined;
  const queryYearSuffix = validYear !== undefined ? ` ${validYear}` : '';

  if (
    !cleanBrand ||
    !cleanModel ||
    !/[a-zA-Z0-9가-힣]/.test(cleanBrand) ||
    !/[a-zA-Z0-9가-힣]/.test(cleanModel)
  ) {
    return {
      valid: false,
      query: `${cleanBrand} ${cleanModel}${queryYearSuffix}`.trim(),
      mode: 'MODEL',
      validationError: '제조사와 유효한 차종명을 모두 입력해 주십시오.',
      decodedBrand: cleanBrand || undefined,
      decodedModel: cleanModel || undefined,
      decodedYear: validYear,
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

  const db = customDb || getRecallDatabase();
  const batteryProfiles = Array.isArray(db.battery_profiles) ? db.battery_profiles : [];
  const recalls = Array.isArray(db.recalls) ? db.recalls : [];

  const batteryProfileMatches = batteryProfiles.filter((bp) => {
    if (!bp || typeof bp.brand !== 'string' || typeof bp.model_name !== 'string') return false;
    if (!bp.brand.trim() || !bp.model_name.trim()) return false;
    return (
      isBrandCompatibleForLookup(brandLower, canonicalBrand, bp.brand) &&
      isModelMatchForCampaign(cleanModel, bp.model_name)
    );
  });
  const matchedBatteryProfile =
    (validYear !== undefined
      ? batteryProfileMatches.find((bp) => typeof bp.years === 'string' && bp.years.trim() && isYearMatchForCampaign(validYear, bp.years))
      : undefined) || batteryProfileMatches[0];

  const matchingRecalls = deduplicateRecallsById(recalls.filter((campaign) => {
    if (!campaign || typeof campaign.brand !== 'string' || typeof campaign.target_model !== 'string') return false;
    const campBrandLower = campaign.brand.trim().toLowerCase();
    const campTargetLower = campaign.target_model.trim().toLowerCase();
    if (!campBrandLower || !campTargetLower) return false;
    const campCanonical = normalizeManufacturer(campaign.brand);

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
      isBrandCompatibleForLookup(brandLower, canonicalBrand, campaign.brand) ||
      matchesTargetBrandMention(campTargetLower, brandLower) ||
      matchesTargetBrandMention(campTargetLower, canonicalBrandLower);

    if (!brandMatches) return false;

    if (!isModelMatchForCampaign(cleanModel, campaign.target_model)) {
      return false;
    }

    if (validYear !== undefined && !isYearMatchForCampaign(validYear, campaign.target_model_years)) {
      return false;
    }

    return true;
  }));

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
    query: `${cleanBrand} ${cleanModel}${queryYearSuffix}`.trim(),
    mode: 'MODEL',
    decodedBrand: cleanBrand,
    decodedModel: cleanModel,
    decodedYear: validYear,
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
  const batteryProfiles = Array.isArray(db.battery_profiles) ? db.battery_profiles : [];
  const recalls = Array.isArray(db.recalls) ? db.recalls : [];

  batteryProfiles.forEach((p) => {
    if (!p || typeof p !== 'object') return;
    const normalized = normalizeManufacturer(p.brand);
    if (normalized && !DANGEROUS_PROTO_KEYS.has(normalized.toLowerCase())) {
      brands.add(normalized);
    }
  });
  recalls.forEach((r) => {
    if (!r || typeof r !== 'object') return;
    const normalized = normalizeManufacturer(r.brand);
    if (normalized && !DANGEROUS_PROTO_KEYS.has(normalized.toLowerCase())) {
      brands.add(normalized);
    }
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
  if (!/[a-zA-Z0-9가-힣]/.test(cleanBrand)) {
    return [];
  }
  const canonicalBrand = normalizeManufacturer(brand);
  const db = customDb || getRecallDatabase();
  const models = new Set<string>();

  const isBrandMatch = (itemBrand?: string) => {
    if (!itemBrand || typeof itemBrand !== 'string') return false;
    const itemClean = itemBrand.trim().toLowerCase();
    if (!itemClean) return false;
    if (itemClean === cleanBrand) return true;
    const itemCanonical = normalizeManufacturer(itemBrand);
    const allowSubstring = cleanBrand.length >= 2 && itemClean.length >= 2;
    return (
      (Boolean(canonicalBrand) && itemCanonical === canonicalBrand) ||
      itemCanonical.toLowerCase() === cleanBrand ||
      (allowSubstring && (itemClean.includes(cleanBrand) || cleanBrand.includes(itemClean)))
    );
  };

  const batteryProfiles = Array.isArray(db.battery_profiles) ? db.battery_profiles : [];
  const vinPrefixes = Array.isArray(db.vin_prefixes) ? db.vin_prefixes : [];
  const recalls = Array.isArray(db.recalls) ? db.recalls : [];

  batteryProfiles
    .filter((bp) => bp && isBrandMatch(bp?.brand))
    .forEach((bp) => {
      const m = typeof bp?.model_name === 'string' ? bp.model_name.trim() : '';
      if (m) models.add(m);
    });

  vinPrefixes
    .filter((vp) => vp && isBrandMatch(vp?.brand))
    .forEach((vp) => {
      const m = typeof vp?.model_name === 'string' ? vp.model_name.trim() : '';
      if (m) models.add(m);
    });

  // Support custom db.vehicles if present in customDb or mock
  const customVehicles = (db as unknown as Record<string, unknown>)?.vehicles;
  if (Array.isArray(customVehicles)) {
    (customVehicles as Array<{ brand?: string; model_name?: string; model?: string }>)
      .filter((v) => v && isBrandMatch(v?.brand))
      .forEach((v) => {
        const mn = typeof v?.model_name === 'string' ? v.model_name.trim() : '';
        const md = typeof v?.model === 'string' ? v.model.trim() : '';
        if (mn) models.add(mn);
        else if (md) models.add(md);
      });
  }

  // Include models explicitly tracked in recall campaigns for this brand
  recalls
    .filter((r) => r && (isBrandMatch(r?.brand) || (canonicalBrand === '제네시스' && r?.brand && normalizeManufacturer(r.brand) === '현대자동차')))
    .forEach((r) => {
      const directBrandMatch = isBrandMatch(r?.brand);
      if (typeof r?.target_model === 'string' && r.target_model) {
        r.target_model.split(',').forEach((tm) => {
          const cleanModel = tm.replace(/\s*\([^)]*\)/g, '').trim();
          if (cleanModel) {
            if (canonicalBrand === '제네시스') {
              if (directBrandMatch || cleanModel.includes('제네시스') || /^g(?:v|70|80|90)/i.test(cleanModel)) {
                const stripped = cleanModel.replace(/^제네시스\s*/, '').trim();
                if (stripped) models.add(stripped);
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

  if (completedUnits >= totalUnits) return 100;

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

  if (resolvedCampaigns >= totalCampaigns) return 100;

  const rawRate = (resolvedCampaigns / totalCampaigns) * 100;
  if (!Number.isFinite(rawRate) || rawRate <= 0) return 0;
  if (rawRate >= 100) return 100;

  return Math.round(rawRate * 10) / 10;
}

/**
 * Aggregates recall campaigns by canonical manufacturer, resolving casing and naming discrepancies.
 * Pure aggregation function with zero dependencies and strict prototype-key safety.
 */
export function aggregateRecallsByManufacturer(
  recalls?: OfficialRecallCampaign[]
): Record<string, ManufacturerRecallSummary> {
  const safeRecalls = Array.isArray(recalls) ? recalls : [];
  const result: Record<string, ManufacturerRecallSummary> = {};

  for (const campaign of safeRecalls) {
    if (!campaign || typeof campaign !== 'object' || Array.isArray(campaign)) continue;
    const rawBrand = typeof campaign.brand === 'string' && campaign.brand.trim() ? campaign.brand : '기타/미확인 브랜드';
    const normalizedBrand = normalizeManufacturer(rawBrand) || '기타/미확인 브랜드';
    const manufacturer = DANGEROUS_PROTO_KEYS.has(normalizedBrand.toLowerCase()) ? '기타/미확인 브랜드' : normalizedBrand;

    if (!Object.prototype.hasOwnProperty.call(result, manufacturer)) {
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

    if (typeof campaign.affected_kdm_units === 'number' && Number.isFinite(campaign.affected_kdm_units) && campaign.affected_kdm_units > 0) {
      const nextUnits = group.affectedUnits + campaign.affected_kdm_units;
      if (Number.isFinite(nextUnits)) {
        group.affectedUnits = nextUnits;
      }
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
 * Employs strict division-by-zero guards, prototype-key safety, and canonical manufacturer normalization.
 */
export function calculateRecallKPIs(customDb?: RecallDatabase): RecallKPIs {
  const db = customDb || getRecallDatabase();
  const rawRecalls = Array.isArray(db.recalls) ? db.recalls : [];
  const rawBatteryProfiles = Array.isArray(db.battery_profiles) ? db.battery_profiles : [];

  const recalls = rawRecalls.filter((c) => c && typeof c === 'object' && !Array.isArray(c));
  const batteryProfiles = rawBatteryProfiles.filter((bp) => bp && typeof bp === 'object' && !Array.isArray(bp));

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
    const statusUpper = typeof campaign.status === 'string' ? campaign.status.trim().toUpperCase() : '';
    if (statusUpper === 'ACTIVE') activeCampaigns++;
    else if (statusUpper === 'RESOLVED') resolvedCampaigns++;

    if (typeof campaign.affected_kdm_units === 'number' && Number.isFinite(campaign.affected_kdm_units) && campaign.affected_kdm_units > 0) {
      const nextTotal = totalAffectedVehicles + campaign.affected_kdm_units;
      if (Number.isFinite(nextTotal)) {
        totalAffectedVehicles = nextTotal;
      }
    }
    const canonicalBrand = normalizeManufacturer(campaign.brand);
    const safeCanonicalBrand =
      canonicalBrand && !DANGEROUS_PROTO_KEYS.has(canonicalBrand.toLowerCase())
        ? canonicalBrand
        : '';
    if (campaign.risk_level === 'FIRE_HAZARD') {
      fireHazards++;
      if (statusUpper === 'ACTIVE') activeFireHazards++;
      if (safeCanonicalBrand) fireRiskBrands.add(safeCanonicalBrand);
    }
    if (campaign.risk_level === 'LOSS_OF_POWER') lossOfPower++;
    if (campaign.remedy_type === 'OTA_WIRELESS') otaRemedies++;

    if (safeCanonicalBrand) {
      const prevCount = Object.prototype.hasOwnProperty.call(brandDistribution, safeCanonicalBrand)
        ? brandDistribution[safeCanonicalBrand]
        : 0;
      brandDistribution[safeCanonicalBrand] = prevCount + 1;
    }

    if (campaign.risk_level && Object.prototype.hasOwnProperty.call(riskLevelDistribution, campaign.risk_level)) {
      riskLevelDistribution[campaign.risk_level]++;
    }

    if (campaign.remedy_type && Object.prototype.hasOwnProperty.call(remedyTypeDistribution, campaign.remedy_type)) {
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
    (bp) => bp.fire_incident_status === 'CRITICAL_MONITORING'
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

