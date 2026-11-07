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
export const VIN_YEAR_MAP: Record<string, number> = {
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

// Canonical manufacturer mapping resolving synonyms, casing, and localized brand names
export const CANONICAL_MANUFACTURER_MAP: Record<string, string> = {
  hyundai: '현대자동차',
  '현대': '현대자동차',
  '현대차': '현대자동차',
  '현대자동차': '현대자동차',
  hmc: '현대자동차',

  kia: '기아',
  '기아': '기아',
  '기아자동차': '기아',

  genesis: '제네시스',
  '제네시스': '제네시스',

  tesla: '테슬라',
  '테슬라': '테슬라',

  mercedes: '메르세데스-벤츠',
  benz: '메르세데스-벤츠',
  'mercedes-benz': '메르세데스-벤츠',
  'mercedes benz': '메르세데스-벤츠',
  '메르세데스': '메르세데스-벤츠',
  '메르세데스-벤츠': '메르세데스-벤츠',
  '메르세데스벤츠': '메르세데스-벤츠',
  '벤츠': '메르세데스-벤츠',

  bmw: 'BMW',
  'bmw i': 'BMW',
  bmwi: 'BMW',

  byd: 'BYD',
  '비야디': 'BYD',

  chevrolet: '쉐보레',
  chevy: '쉐보레',
  gm: '쉐보레',
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
  'kg mobility': 'KG모빌리티',
  'kg모빌리티': 'KG모빌리티',
  ssangyong: 'KG모빌리티',
  '쌍용': 'KG모빌리티',
  '쌍용자동차': 'KG모빌리티',
};

/**
 * Normalizes manufacturer / brand string to canonical form, handling casing,
 * leading/trailing whitespace, punctuation, and English/Korean aliases.
 */
export function normalizeManufacturer(brand?: string | null): string {
  if (!brand || typeof brand !== 'string') return '';
  const cleaned = brand.trim();
  if (!cleaned) return '';

  const key = cleaned.toLowerCase().replace(/[\s\-_/()]+/g, '');
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
      ? (data.recalls as OfficialRecallCampaign[]).map((r) => ({
          ...r,
          official_link: sanitizeSafeUrl(r?.official_link),
        }))
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
    return d;
  }

  // 2. Try YYYYMMDD compact format
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
    return d;
  }

  // 3. Fallback to standard Date.parse
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

    // 3. End date of production_date_range (e.g. "2021.03.08 ~ 2024.03.04")
    if (typeof c.production_date_range === 'string') {
      const rangeParts = c.production_date_range.split('~');
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

  // Split disjoint segments separated by comma or semicolon
  const segments = targetModelYears.split(/[,;]/).map((s) => s.trim()).filter(Boolean);
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

    // 2. Open-ended future range: "2022 ~" or "2022 ~ 현재" or "2022년 이후"
    const openRangeMatch = segment.match(/(\d{4})\s*(?:~|-)\s*(?:현재|present|\+|$)/i);
    if (openRangeMatch) {
      hasValidSegment = true;
      const start = parseInt(openRangeMatch[1], 10);
      if (year >= start && year <= 2040) return true;
      continue;
    }

    // 3. Single year match: "2022"
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
  const sortedPrefixes = [...(db.vin_prefixes || [])].sort((a, b) => b.prefix.length - a.prefix.length);
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
    matchedBatteryProfile = (db.battery_profiles || []).find((bp) => {
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
    const decodedBrandLower = (decodedBrand || '').toLowerCase();
    const decodedCanonical = decodedBrand ? normalizeManufacturer(decodedBrand) : '';
    const campCanonical = campaign.brand ? normalizeManufacturer(campaign.brand) : '';
    const campBrandLower = (campaign.brand || '').toLowerCase();
    const campTargetLower = (campaign.target_model || '').toLowerCase();

    const brandMatches =
      Boolean(decodedBrand) &&
      (decodedCanonical === campCanonical ||
        campBrandLower === decodedBrandLower ||
        campBrandLower.includes(decodedBrandLower) ||
        decodedBrandLower.includes(campBrandLower) ||
        (campCanonical && campCanonical.toLowerCase().includes(decodedCanonical.toLowerCase())) ||
        (decodedCanonical && decodedCanonical.toLowerCase().includes(campCanonical.toLowerCase())) ||
        (decodedCanonical === '제네시스' && campCanonical === '현대자동차') ||
        (decodedBrand === '제네시스' && campaign.brand === '현대자동차') ||
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
    batteryProfile: matchedBatteryProfile,
    recalls: sortRecallsByDate(matchingRecalls, 'desc'),
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

    const brandMatches =
      campCanonical === canonicalBrand ||
      campBrandLower === brandLower ||
      campBrandLower.includes(brandLower) ||
      brandLower.includes(campBrandLower) ||
      (campCanonical && campCanonical.toLowerCase().includes(canonicalBrandLower)) ||
      (canonicalBrandLower && canonicalBrandLower.includes(campCanonical.toLowerCase())) ||
      (canonicalBrand === '제네시스' && campCanonical === '현대자동차') ||
      (cleanBrand === '제네시스' && campaign.brand === '현대자동차') ||
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
    decodedYear: year,
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
    activeCampaignsCount: matchingRecalls.filter((r) => r.status === 'ACTIVE').length,
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
      .filter((v) => isBrandMatch(v?.brand))
      .forEach((v) => {
        if (v?.model_name) models.add(v.model_name);
        else if (v?.model) models.add(v.model);
      });
  }

  // Include models explicitly tracked in recall campaigns for this brand
  (db.recalls || [])
    .filter((r) => isBrandMatch(r?.brand))
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
    if (campaign.status === 'ACTIVE') {
      group.activeCampaigns++;
    } else if (campaign.status === 'RESOLVED') {
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

    if (campaign.status === 'ACTIVE') activeCampaigns++;
    else if (campaign.status === 'RESOLVED') resolvedCampaigns++;

    if (Number.isFinite(campaign.affected_kdm_units) && campaign.affected_kdm_units > 0) {
      totalAffectedVehicles += campaign.affected_kdm_units;
    }
    if (campaign.risk_level === 'FIRE_HAZARD') {
      fireHazards++;
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
    activeFireHazards: fireHazards,
    otaRemedyRate: otaRemedyRatePct,
    fireRiskBrandCount: fireRiskBrands.size,
    totalBatteryProfiles: batteryProfiles.length,
  };
}

