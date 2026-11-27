import rawReportData from '../data/daily_reports.json' with { type: 'json' };
import { sanitizeSafeUrl, sanitizeText, stripHtmlTags, sanitizeHtml, safeJsonParse, isPrototypePollutionKey } from './sanitizeUrl.ts';

export { stripHtmlTags, sanitizeHtml };

import type {
  DefectCategoryCode,
  SeverityLevel,
  DefectReportSource,
  DsiBreakdown,
  DefectReportItem,
  DailyReportStatistics,
  ReportStatistics,
  DailyReportData,
  AdminDefectReportItem,
  AdminDailyReportData,
} from '../types/reports.ts';

export type {
  DefectCategoryCode,
  SeverityLevel,
  DefectReportSource,
  DsiBreakdown,
  DefectReportItem,
  DailyReportStatistics,
  ReportStatistics,
  DailyReportData,
  AdminDefectReportItem,
  AdminDailyReportData,
};

export const CATEGORY_MAP: Record<string, { code: DefectCategoryCode; ko: string }> = {
  // Canonical 5-Pillar Taxonomy
  BATTERY_CHARGING: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  DRIVING_POWERTRAIN: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  BUILD_QUALITY: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  SOFTWARE_ELECTRONICS: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  SERVICE_REPAIR_COST: { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },

  // Lowercase Canonical Variants
  battery_charging: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  driving_powertrain: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  build_quality: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  software_electronics: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  service_repair_cost: { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },

  // Korean Category Labels & Synonyms
  '배터리/충전': { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  '배터리': { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  '충전': { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  '화재': { code: 'BATTERY_CHARGING', ko: '배터리/충전' },

  '주행/모터/등판': { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  '주행': { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  '모터': { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  '등판': { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  '제동': { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  '조향': { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  '브레이크': { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },

  '단차/누수/마감': { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  '단차': { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  '누수': { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  '마감': { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  '풍절음': { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  '잡소리': { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },

  'OTA/소프트웨어': { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  'OTA/소프트웨어/먹통': { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  '소프트웨어': { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  '전장': { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  '전자장비': { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  '먹통': { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  '블랙아웃': { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },

  'AS/수리비': { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  '수리비': { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  'AS': { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  'as': { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  '정비': { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  '서비스': { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  '감가': { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },

  // Crawler Keywords & Aliases
  parking: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  charging: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  battery: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  iccu: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  bms: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  fire: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },
  safety: { code: 'BATTERY_CHARGING', ko: '배터리/충전' },

  driving: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  powertrain: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  motor: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  brake: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  steering: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  fishtail: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  rain_driving: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },
  hill_climbing: { code: 'DRIVING_POWERTRAIN', ko: '주행/모터/등판' },

  build: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  quality: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  assembly: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  leak: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  water_leak: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  noise: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },
  gap: { code: 'BUILD_QUALITY', ko: '단차/누수/마감' },

  software: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  electronics: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  ota: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  infotainment: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  blackout: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },
  display: { code: 'SOFTWARE_ELECTRONICS', ko: 'OTA/소프트웨어' },

  maintenance: { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  service: { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  repair: { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  cost: { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
  depreciation: { code: 'SERVICE_REPAIR_COST', ko: 'AS/수리비' },
};

function firstSafeString(...candidates: unknown[]): string {
  for (const candidate of candidates) {
    if (typeof candidate === 'string') {
      const cleaned = sanitizeText(candidate);
      if (cleaned) return cleaned;
    }
  }
  return '';
}

function firstSafeId(...candidates: unknown[]): string {
  for (const candidate of candidates) {
    if (typeof candidate === 'string') {
      const cleaned = sanitizeText(candidate);
      if (cleaned) return cleaned;
    } else if (typeof candidate === 'number' && Number.isFinite(candidate)) {
      return String(candidate);
    }
  }
  return '';
}

const FORBIDDEN_PROTOTYPE_KEYS = new Set([
  '__proto__',
  'constructor',
  'prototype',
  'tostring',
  'valueof',
  'hasownproperty',
  'isprototypeof',
  'propertyisenumerable',
  'tolocalestring',
]);

function isForbiddenPrototypeKey(key: string): boolean {
  return (
    FORBIDDEN_PROTOTYPE_KEYS.has(key.toLowerCase()) ||
    key in Object.prototype ||
    isPrototypePollutionKey(key)
  );
}

/**
 * Resolves defect category safely from category code, alias, or Korean label.
 */
export function resolveCategory(
  rawCategory?: unknown,
  rawCategoryKo?: unknown
): { code: DefectCategoryCode; ko: string } {
  const rawCat = typeof rawCategory === 'string' ? sanitizeText(rawCategory).trim() : '';
  const rawCatKo = typeof rawCategoryKo === 'string' ? sanitizeText(rawCategoryKo).trim() : '';
  const cat = rawCat && !isForbiddenPrototypeKey(rawCat) ? rawCat : '';
  const catKo = rawCatKo && !isForbiddenPrototypeKey(rawCatKo) ? rawCatKo : '';

  // 1. Direct match in CATEGORY_MAP
  if (cat && Object.prototype.hasOwnProperty.call(CATEGORY_MAP, cat)) {
    return CATEGORY_MAP[cat];
  }

  // 2. Case-insensitive lookup (uppercase then lowercase)
  const upper = cat.toUpperCase();
  if (upper && Object.prototype.hasOwnProperty.call(CATEGORY_MAP, upper)) {
    return CATEGORY_MAP[upper];
  }
  const lower = cat.toLowerCase();
  if (lower && Object.prototype.hasOwnProperty.call(CATEGORY_MAP, lower)) {
    return CATEGORY_MAP[lower];
  }

  // 3. Korean label lookup
  if (catKo && Object.prototype.hasOwnProperty.call(CATEGORY_MAP, catKo)) {
    return CATEGORY_MAP[catKo];
  }
  const koUpper = catKo.toUpperCase();
  if (koUpper && Object.prototype.hasOwnProperty.call(CATEGORY_MAP, koUpper)) {
    return CATEGORY_MAP[koUpper];
  }

  // 4. Default fallback when both empty (preserves default BATTERY_CHARGING / 배터리/충전 contract)
  if (!cat && !catKo) {
    return CATEGORY_MAP['BATTERY_CHARGING'];
  }

  // 5. Unrecognized custom category: preserve sanitized code, fallback label
  return {
    code: cat || 'BUILD_QUALITY',
    ko: catKo || '기타 결함',
  };
}

/**
 * Masks internal filesystem paths (e.g. /Users/..., /home/..., /var/..., C:\Users\...)
 * to prevent sensitive directory structure and username leakage.
 */
export function maskInternalPaths(text?: unknown): string {
  if (!text || typeof text !== 'string') return '';
  return text
    // Absolute Unix/Mac paths starting with common internal dirs
    .replace(/(?:\/(?:Users|home|root|var|etc|opt|tmp|private|srv|usr|app|src)\/[a-zA-Z0-9_\-./]+)/g, '[내부경로_마스킹]')
    // Windows paths: C:\Users\... or D:\app\...
    .replace(/(?:[a-zA-Z]:\\(?:Users|Windows|Program Files|inetpub|app|temp)\\[a-zA-Z0-9_\-\\.]+)/gi, '[내부경로_마스킹]');
}

/**
 * Masks sensitive tokens, API keys, credentials, and secrets (JWTs, Bearer tokens, GitHub, OpenAI, AWS keys).
 */
export function maskSensitiveTokens(text?: unknown): string {
  if (!text || typeof text !== 'string') return '';
  return text
    // JWT tokens (eyJ...)
    .replace(/eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}/g, '[REDACTED_JWT]')
    // Bearer authorization tokens
    .replace(/Bearer\s+[a-zA-Z0-9_\-.~+/]+=*/gi, 'Bearer [REDACTED_TOKEN]')
    // GitHub personal access tokens
    .replace(/gh[pousr]_[A-Za-z0-9]{20,}/g, '[REDACTED_TOKEN]')
    // AWS access keys
    .replace(/\b(?:AKIA|ASIA)[0-9A-Z]{16}\b/g, '[REDACTED_AWS_KEY]')
    // OpenAI / AI secret keys (including project-scoped sk-proj-... keys)
    .replace(/\bsk-(?:proj-)?[a-zA-Z0-9_-]{20,}\b/g, '[REDACTED_KEY]')
    // Key-value credential pairs (api_key=..., secret=..., password=...) - linear capture avoids lookbehind ReDoS
    .replace(/((?:api[_-]?key|secret|password|passwd|auth[_-]?token|access[_-]?token)\s*[:=]\s*["']?)[a-zA-Z0-9_\-.~+/]{8,}/gi, '$1[REDACTED_SECRET]');
}

/**
 * Masks sensitive personally identifiable information (PII) from author names,
 * such as full IPv4 addresses, emails, and phone numbers.
 */
export function maskAuthor(author?: unknown): string {
  if (!author || typeof author !== 'string') return '익명 제보자';
  const trimmed = sanitizeText(author).trim();
  if (!trimmed) return '익명 제보자';

  // 1. Mask unmasked full IPv4 addresses (e.g. "123.45.67.89" -> "123.45.*.*")
  let masked = trimmed.replace(/\b(\d{1,3}\.\d{1,3})\.\d{1,3}\.\d{1,3}\b/g, '$1.*.*');

  // 2. Mask email addresses (e.g. "john.doe@example.com" -> "j***@example.com") in O(N) time
  if (masked.includes('@')) {
    masked = masked.replace(
      /(^|[^a-zA-Z0-9._%+-])([a-zA-Z0-9._%+-])[a-zA-Z0-9._%+-]*@((?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})\b/g,
      '$1$2***@$3'
    );
  }

  // 3. Mask phone numbers (e.g. "010-1234-5678" -> "010-****-5678")
  masked = masked.replace(/\b(01[016789])-?\d{3,4}-?(\d{4})\b/g, '$1-****-$2');

  // 4. Mask internal paths and tokens if present in author
  masked = maskSensitiveTokens(maskInternalPaths(masked));

  return masked;
}

/**
 * Composite sensitive data sanitizer that masks internal paths and credentials.
 */
export function maskSensitiveData(text?: unknown): string {
  if (!text || typeof text !== 'string') return '';
  return maskSensitiveTokens(maskInternalPaths(text));
}

const REPORT_SENSITIVE_QUERY_KEYS = new Set([
  'token',
  'access_token',
  'access-token',
  'refresh_token',
  'id_token',
  'auth',
  'auth_token',
  'authorization',
  'api_key',
  'api-key',
  'apikey',
  'x-api-key',
  'key',
  'secret',
  'client_secret',
  'client-secret',
  'password',
  'passwd',
  'pwd',
  'session',
  'session_id',
  'sessionid',
  'jwt',
]);

function isPrivateOrInternalHost(rawHost: string): boolean {
  const host = rawHost.toLowerCase().replace(/\.+$/, '');
  if (!host) return true;
  if (host.includes('%')) return true;

  const bareHost = host.startsWith('[') && host.endsWith(']') ? host.slice(1, -1) : host;
  if (
    bareHost === 'localhost' ||
    bareHost.endsWith('.localhost') ||
    bareHost === '0.0.0.0' ||
    bareHost === '::1' ||
    bareHost === '::' ||
    bareHost.endsWith('.local') ||
    bareHost.endsWith('.localdomain') ||
    bareHost.endsWith('.internal') ||
    bareHost.endsWith('.intranet') ||
    bareHost.endsWith('.corp') ||
    bareHost.endsWith('.arpa') ||
    bareHost.endsWith('.lan') ||
    bareHost.endsWith('.home') ||
    bareHost.endsWith('.private')
  ) {
    return true;
  }

  // IPv6 reserved, loopback, unspecified, IPv4-mapped/compatible (::/96), NAT64, Teredo, benchmarking, ORCHID, 6to4, 6bone, discard, ULA, link/site-local, multicast.
  // Only Global Unicast (2000::/3) outside special-use tunneling/documentation/benchmarking ranges is public.
  if (host.startsWith('[') || bareHost.includes(':')) {
    if (bareHost.startsWith(':')) {
      return true;
    }
    const parts = bareHost.split(':');
    if (!/^[0-9a-f]{1,4}$/.test(parts[0])) {
      return true;
    }
    const h0 = parseInt(parts[0], 16);
    if (!Number.isFinite(h0) || Number.isNaN(h0) || h0 < 0x2000 || h0 > 0x3fff) {
      return true;
    }
    if (h0 === 0x2002 || h0 === 0x3ffe) {
      return true;
    }
    if (h0 === 0x3fff) {
      const seg1 = parts[1] ?? '';
      if (seg1 !== '' && !/^[0-9a-f]{1,4}$/.test(seg1)) {
        return true;
      }
      const h1 = seg1 === '' ? 0 : parseInt(seg1, 16);
      if (!Number.isFinite(h1) || Number.isNaN(h1) || h1 <= 0x0fff) {
        return true;
      }
    }
    if (h0 === 0x2001) {
      const seg1 = parts[1] ?? '';
      if (seg1 !== '' && !/^[0-9a-f]{1,4}$/.test(seg1)) {
        return true;
      }
      const h1 = seg1 === '' ? 0 : parseInt(seg1, 16);
      if (
        !Number.isFinite(h1) ||
        Number.isNaN(h1) ||
        h1 === 0 ||
        h1 === 2 ||
        h1 === 0x0db8 ||
        (h1 >= 0x0010 && h1 <= 0x002f)
      ) {
        return true;
      }
    }
    return false;
  }

  // Require at least one dot for non-IPv6 hostnames to block single-label internal services (e.g. http://redis:6379)
  if (!bareHost.includes('.')) {
    return true;
  }

  // IPv4 private, loopback, link-local, CGNAT, benchmark, 6to4-relay, TEST-NET, and multicast/reserved ranges
  return (
    /^0\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(bareHost) ||
    /^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(bareHost) ||
    /^169\.254\.\d{1,3}\.\d{1,3}$/.test(bareHost) ||
    /^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(bareHost) ||
    /^172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}$/.test(bareHost) ||
    /^192\.168\.\d{1,3}\.\d{1,3}$/.test(bareHost) ||
    /^192\.0\.[02]\.\d{1,3}$/.test(bareHost) ||
    /^192\.88\.99\.\d{1,3}$/.test(bareHost) ||
    /^198\.1[89]\.\d{1,3}\.\d{1,3}$/.test(bareHost) ||
    /^198\.51\.100\.\d{1,3}$/.test(bareHost) ||
    /^203\.0\.113\.\d{1,3}$/.test(bareHost) ||
    /^100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}$/.test(bareHost) ||
    /^(?:22[4-9]|23\d|24\d|25[0-5])\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(bareHost)
  );
}

function stripSensitiveParamsFromUrlObj(urlObj: URL): boolean {
  let modified = false;
  for (const paramKey of Array.from(urlObj.searchParams.keys())) {
    if (REPORT_SENSITIVE_QUERY_KEYS.has(paramKey.toLowerCase())) {
      urlObj.searchParams.delete(paramKey);
      modified = true;
    }
  }
  // Strip sensitive OAuth/token parameters if leaked in hash fragments (e.g. #access_token=... or #/callback?access_token=...)
  if (urlObj.hash && urlObj.hash.includes('=')) {
    const rawFragment = urlObj.hash.slice(1);
    const qIdx = rawFragment.indexOf('?');
    const hashPrefix = qIdx !== -1 ? rawFragment.slice(0, qIdx) : '';
    const hashQuery = qIdx !== -1 ? rawFragment.slice(qIdx + 1) : rawFragment;
    const hashParams = new URLSearchParams(hashQuery);
    let hashModified = false;
    for (const hashKey of Array.from(hashParams.keys())) {
      if (REPORT_SENSITIVE_QUERY_KEYS.has(hashKey.toLowerCase())) {
        hashParams.delete(hashKey);
        hashModified = true;
      }
    }
    if (hashModified) {
      const nextQuery = hashParams.toString();
      if (hashPrefix) {
        urlObj.hash = nextQuery ? `#${hashPrefix}?${nextQuery}` : `#${hashPrefix}`;
      } else {
        urlObj.hash = nextQuery ? `#${nextQuery}` : '';
      }
      modified = true;
    }
  }
  return modified;
}

/**
 * Safely sanitizes external URLs to prevent javascript:, data:, vbscript: or other XSS injections,
 * blocks internal/private network addresses (SSRF protection), and strips sensitive query parameters.
 */
export function sanitizeReportUrl(rawUrl?: unknown): string {
  if (!rawUrl || typeof rawUrl !== 'string') return '#';
  const trimmed = rawUrl.trim();
  if (!trimmed) return '#';
  if (/^(?:javascript|data|vbscript):/i.test(trimmed)) {
    return '#';
  }
  // Reject XSS/attribute breakout characters before URL parsing/re-serialization
  const safeBase = sanitizeSafeUrl(trimmed);
  if (safeBase === '#') {
    return '#';
  }

  // Block internal hostnames, loopbacks, userinfo credentials, and private/reserved IPv4 & IPv6 ranges
  try {
    if (/^https?:\/\//i.test(safeBase)) {
      const urlObj = new URL(safeBase);
      if (urlObj.username || urlObj.password) {
        return '#';
      }
      if (isPrivateOrInternalHost(urlObj.hostname)) {
        return '#';
      }

      if (stripSensitiveParamsFromUrlObj(urlObj)) {
        return sanitizeSafeUrl(urlObj.toString());
      }
    } else if (safeBase.startsWith('/')) {
      const urlObj = new URL(safeBase, 'http://safe-internal.local');
      if (stripSensitiveParamsFromUrlObj(urlObj)) {
        const safePath = urlObj.pathname.replace(/^\/{2,}/, '/');
        const searchStr = urlObj.searchParams.toString() ? `?${urlObj.searchParams.toString()}` : '';
        return sanitizeSafeUrl(safePath + searchStr + (urlObj.hash || ''));
      }
    }
  } catch {
    return '#';
  }

  return safeBase;
}

/**
 * Normalizes and bounds sentiment/negativity scores safely between 0.00 and 1.00.
 */
export function getSafeSentimentScore(rawScore?: unknown, fallback = 0.85): number {
  const safeFallback =
    typeof fallback === 'number' && Number.isFinite(fallback)
      ? Number(Math.min(1.0, Math.max(0.0, fallback)).toFixed(2))
      : 0.85;
  if (typeof rawScore !== 'number' || !Number.isFinite(rawScore)) {
    return safeFallback;
  }
  let val = Math.abs(rawScore);
  // If score was provided on a 0-100 scale (e.g. 85), scale down to 0-1
  if (val > 1.0 && val <= 100.0) {
    val = val / 100.0;
  }
  const clamped = Math.min(1.0, Math.max(0.0, val));
  return Number(clamped.toFixed(2));
}

export interface DeduplicationSummary {
  totalBefore: number;
  totalAfter: number;
  duplicatesRemoved: number;
  isDeduplicated: boolean;
}

const DEDUP_NOISE_PARAMS = new Set([
  'utm_source',
  'utm_medium',
  'utm_campaign',
  'utm_term',
  'utm_content',
  'fbclid',
  'gclid',
  'yclid',
  'mc_cid',
  'mc_eid',
  'ref',
  'referer',
  'referrer',
  'source',
  'query',
  'page',
  'rtn',
  '_',
]);

function canonicalizeReportUrlForDedup(rawUrl: string): string {
  try {
    const isRelative = rawUrl.startsWith('/');
    const parsed = isRelative ? new URL(rawUrl, 'http://safe-internal.local') : new URL(rawUrl);
    const host = isRelative ? '' : parsed.hostname.toLowerCase().replace(/\.+$/, '');
    const pathname = isRelative
      ? (parsed.pathname.replace(/\/+$/, '') || '/')
      : parsed.pathname.replace(/\/+$/, '');
    const keptParams: Array<[string, string]> = [];
    for (const [rawKey, rawVal] of parsed.searchParams.entries()) {
      const key = rawKey.toLowerCase();
      if (DEDUP_NOISE_PARAMS.has(key) || key.startsWith('utm_')) continue;
      // Strip malformed appended query string suffix (e.g. "999?query=1" -> "999")
      const cleanVal = rawVal.replace(/\?[a-zA-Z0-9_]+=.*$/, '');
      keptParams.push([key, cleanVal]);
    }
    keptParams.sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0));
    const queryStr = keptParams.length > 0
      ? '?' + keptParams.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&')
      : '';
    return `${host}${pathname}${queryStr}`;
  } catch {
    return rawUrl.replace(/^https?:\/\//i, '').replace(/#.*$/, '').replace(/\/+$/, '');
  }
}

/**
 * Deduplicates reports list using deterministic ID, canonical URL, and semantic composite keys.
 */
export function deduplicateReports(
  rawReports: Array<Record<string, unknown> | DefectReportItem>
): {
  reports: DefectReportItem[];
  summary: DeduplicationSummary;
} {
  const safeList = Array.isArray(rawReports) ? rawReports : [];
  const seenKeys = new Set<string>();
  const deduped: DefectReportItem[] = [];
  let duplicatesRemoved = 0;

  safeList.forEach((item, idx) => {
    if (!item || typeof item !== 'object' || Array.isArray(item)) return;

    // Always normalize to guarantee URL sanitization, PII masking, and field invariants
    const normalized = normalizeReport(item as Record<string, unknown>, idx);

    // Deterministic deduplication keys (source-scoped ID + canonical URL, or semantic fingerprint fallback):
    const id = String(normalized.id || '').trim();
    const idKey = id && !id.startsWith('report_') ? `id:${normalized.source}:${id}` : '';
    const urlKey = normalized.url && normalized.url !== '#'
      ? `url:${canonicalizeReportUrlForDedup(normalized.url)}`
      : '';
    let fpKey = '';
    if (!idKey && !urlKey) {
      const model = (normalized.vehicle_model || '').trim().toLowerCase();
      const cat = (normalized.defect_category || '').trim().toUpperCase();
      const titleClean = (normalized.title || '')
        .trim()
        .toLowerCase()
        .replace(/[^\w\s가-힣ㄱ-ㅎㅏ-ㅣ]/g, '')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 40);
      fpKey = `fp:${model}:${cat}:${titleClean}`;
    }

    if (
      (idKey && seenKeys.has(idKey)) ||
      (urlKey && seenKeys.has(urlKey)) ||
      (fpKey && seenKeys.has(fpKey))
    ) {
      duplicatesRemoved++;
      return;
    }

    if (idKey) seenKeys.add(idKey);
    if (urlKey) seenKeys.add(urlKey);
    if (fpKey) seenKeys.add(fpKey);
    deduped.push(normalized);
  });

  return {
    reports: deduped,
    summary: {
      totalBefore: safeList.length,
      totalAfter: deduped.length,
      duplicatesRemoved,
      isDeduplicated: true,
    },
  };
}

function toFiniteOrUndefined(value: unknown): number | undefined {
  if (typeof value !== 'number' || !Number.isFinite(value)) return undefined;
  return Object.is(value, -0) ? 0 : value;
}

function toFiniteOrZero(value: unknown): number {
  return toFiniteOrUndefined(value) ?? 0;
}

function firstRawUrlCandidate(...candidates: unknown[]): string {
  for (const candidate of candidates) {
    if (typeof candidate === 'string' && candidate.trim().length > 0) {
      return candidate;
    }
  }
  return '#';
}

/**
 * Normalizes any raw item from external JSON to DefectReportItem with safe defaults.
 */
export function normalizeReport(raw: Record<string, unknown>, index: number): DefectReportItem {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) raw = {};
  const safeIndex = typeof index === 'number' && Number.isFinite(index) && index >= 0 ? Math.floor(index) : 0;

  const catInfo = resolveCategory(
    firstSafeString(raw.defect_category, raw.category, raw.defect_category_key),
    firstSafeString(raw.defect_category_ko, raw.category_ko)
  );

  const rawSeverity = firstSafeString(raw.severity, raw.severity_tier).toUpperCase();
  let severity: SeverityLevel = 'WARNING';
  if (rawSeverity === 'CRITICAL' || rawSeverity.includes('CRITICAL')) {
    severity = 'CRITICAL';
  } else if (rawSeverity === 'HIGH') {
    severity = 'HIGH';
  } else if (rawSeverity === 'MEDIUM') {
    severity = 'MEDIUM';
  } else if (rawSeverity === 'LOW') {
    severity = 'LOW';
  } else if (rawSeverity === 'CAUTION' || rawSeverity.includes('CAUTION') || rawSeverity.includes('CONVENIENCE')) {
    severity = 'CAUTION';
  } else if (rawSeverity === 'WARNING' || rawSeverity.includes('WARN') || rawSeverity.includes('FUNCTIONAL')) {
    severity = 'WARNING';
  } else if (rawSeverity === 'INFO' || rawSeverity.includes('INFO')) {
    severity = 'INFO';
  } else if (typeof raw.severity_index === 'number' && Number.isFinite(raw.severity_index)) {
    const idx = raw.severity_index;
    if (idx >= 8.0) severity = 'CRITICAL';
    else if (idx >= 6.0) severity = 'HIGH';
    else if (idx >= 4.0) severity = 'MEDIUM';
    else severity = 'LOW';
  }

  const rawScore = toFiniteOrUndefined(raw.sentiment_score) ?? toFiniteOrUndefined(raw.negativity_score) ?? 0.85;
  const score = getSafeSentimentScore(rawScore, 0.85);

  let rawSlang = raw.slang_tags || raw.slang_terms || raw.slang_terms_detected;
  if (typeof rawSlang === 'string') {
    const trimmedSlang = rawSlang.trim();
    if (trimmedSlang.startsWith('[') && trimmedSlang.endsWith(']')) {
      rawSlang = safeJsonParse<unknown[]>(trimmedSlang, []);
    } else if (trimmedSlang.length > 0) {
      rawSlang = trimmedSlang.split(',').map((s) => s.trim()).filter(Boolean);
    } else {
      rawSlang = [];
    }
  }
  const slangList = Array.isArray(rawSlang) ? rawSlang : [];
  const slangTags = slangList
    .filter((s): s is string => typeof s === 'string')
    .map((s) => maskSensitiveData(sanitizeText(s)))
    .filter((s): s is string => Boolean(s && s.length > 0));

  let rawDsiCandidate = raw.dsi_breakdown;
  if (typeof rawDsiCandidate === 'string') {
    const trimmedDsi = rawDsiCandidate.trim();
    if (trimmedDsi.startsWith('{') && trimmedDsi.endsWith('}')) {
      rawDsiCandidate = safeJsonParse<Record<string, unknown> | null>(trimmedDsi, null);
    }
  }
  const rawDsi = rawDsiCandidate && typeof rawDsiCandidate === 'object' && !Array.isArray(rawDsiCandidate)
    ? (rawDsiCandidate as Record<string, unknown>)
    : null;
  const dsiBreakdown: DefectReportItem['dsi_breakdown'] = rawDsi
    ? {
        safety: toFiniteOrZero(rawDsi.safety),
        functional: toFiniteOrZero(rawDsi.functional),
        economic: toFiniteOrZero(rawDsi.economic),
        social: toFiniteOrZero(rawDsi.social),
        convenience: toFiniteOrZero(rawDsi.convenience),
      }
    : undefined;

  let safeDate = firstSafeString(raw.date, raw.post_date);
  if (!safeDate && typeof raw.created_at === 'string') {
    const split = raw.created_at.trim().split(/[T\s]/)[0];
    if (split && split.length >= 8) {
      safeDate = sanitizeText(split);
    }
  }
  if (!safeDate) {
    safeDate = new Date().toISOString().split('T')[0];
  }

  const rawCatKo = firstSafeString(raw.defect_category_ko);
  const safeCatKo = rawCatKo && !isForbiddenPrototypeKey(rawCatKo) ? maskSensitiveData(rawCatKo) : '';

  return {
    id: firstSafeId(raw.id, raw.post_id) || `report_${safeIndex + 1}`,
    source: firstSafeString(raw.source, raw.platform).toLowerCase() || 'bobaedream',
    url: sanitizeReportUrl(firstRawUrlCandidate(raw.url, raw.post_url)),
    title: maskSensitiveData(firstSafeString(raw.title, raw.post_title)) || '전기차 결함 제보',
    date: safeDate,
    created_at: firstSafeString(raw.created_at) || undefined,
    vehicle_model: firstSafeString(raw.vehicle_model, raw.target_vehicle) || '미상 모델',
    vehicle_brand: firstSafeString(raw.vehicle_brand) || undefined,
    target_vehicle: firstSafeString(raw.target_vehicle) || undefined,
    defect_category: catInfo.code,
    defect_category_ko: safeCatKo || catInfo.ko,
    summary: maskSensitiveData(firstSafeString(raw.summary, raw.defect_summary, raw.defect_topic)) || '결함 상세 내용 요약',
    verbatim_quote: maskSensitiveData(firstSafeString(raw.verbatim_quote, raw.raw_quote, raw.content)) || '원문 없음',
    slang_tags: slangTags,
    sentiment_score: score,
    sentiment_polarity: toFiniteOrUndefined(raw.sentiment_polarity),
    severity,
    severity_index: toFiniteOrUndefined(raw.severity_index),
    author: typeof raw.author === 'string' ? maskAuthor(raw.author) : undefined,
    is_authentic_defect: typeof raw.is_authentic_defect === 'boolean' ? raw.is_authentic_defect : true,
    dsi_breakdown: dsiBreakdown,
  };
}

/**
 * Calculates summary KPIs dynamically from reports list.
 */
export function calculateKPIs(
  reports: DefectReportItem[],
  existingStats?: Partial<ReportStatistics>
): ReportStatistics {
  const safeReports = Array.isArray(reports)
    ? reports.filter((r): r is DefectReportItem => Boolean(r && typeof r === 'object' && !Array.isArray(r)))
    : [];
  const totalFiltered = safeReports.length;
  const criticalCount = safeReports.filter(
    (r) => typeof r.severity === 'string' && r.severity.trim().toUpperCase() === 'CRITICAL'
  ).length;

  const totalScore = safeReports.reduce((acc, r) => {
    const val = typeof r.sentiment_score === 'number' && Number.isFinite(r.sentiment_score)
      ? getSafeSentimentScore(r.sentiment_score, 0)
      : 0;
    return acc + val;
  }, 0);
  const avgScore = totalFiltered > 0 ? Number((totalScore / totalFiltered).toFixed(2)) : 0.0;

  // Calculate top vehicle model with prototype-safe Map
  const modelCounts = new Map<string, number>();
  for (const r of safeReports) {
    const model = typeof r.vehicle_model === 'string' ? sanitizeText(r.vehicle_model) : '';
    if (model) {
      modelCounts.set(model, (modelCounts.get(model) || 0) + 1);
    }
  }
  let topModelName = '아이오닉5';
  let maxModelCount = 0;
  modelCounts.forEach((count, model) => {
    if (count > maxModelCount) {
      maxModelCount = count;
      topModelName = model;
    }
  });
  const topModelDisplay = totalFiltered > 0 && maxModelCount > 0
    ? `${topModelName} (${maxModelCount}건)`
    : '해당 없음 (0건)';

  // Calculate top community platform with prototype-safe Map
  const platformCounts = new Map<string, number>();
  for (const r of safeReports) {
    const rawSrc = typeof r.source === 'string' ? sanitizeText(r.source) : '';
    const src = (rawSrc || 'bobaedream').toLowerCase();
    platformCounts.set(src, (platformCounts.get(src) || 0) + 1);
  }
  let topPlatformKey = 'bobaedream';
  let maxPlatformCount = 0;
  platformCounts.forEach((count, platform) => {
    if (count > maxPlatformCount) {
      maxPlatformCount = count;
      topPlatformKey = platform;
    }
  });
  const platformRatio = totalFiltered > 0 ? Math.round((maxPlatformCount / totalFiltered) * 100) : 0;
  const platformNameKo = topPlatformKey.includes('bobae')
    ? '보배드림'
    : topPlatformKey.includes('dc')
      ? '디시인사이드'
      : topPlatformKey.includes('clien')
        ? '클리앙'
        : topPlatformKey.includes('ppomppu')
          ? '뽐뿌'
          : topPlatformKey.includes('naver')
            ? '네이버 카페'
            : topPlatformKey.includes('blind')
              ? '블라인드'
              : topPlatformKey.includes('reddit')
                ? '레딧'
                : topPlatformKey;
  const topPlatformDisplay = totalFiltered > 0
    ? `${platformNameKo} (${platformRatio}%)`
    : '해당 없음 (0%)';

  const totalScraped = existingStats?.total_scraped ?? (totalFiltered * 7);
  const existingTopModel = typeof existingStats?.top_model === 'string'
    ? maskSensitiveData(sanitizeText(existingStats.top_model))
    : '';
  const existingTopPlatform = typeof existingStats?.top_platform === 'string'
    ? maskSensitiveData(sanitizeText(existingStats.top_platform))
    : '';

  return {
    total_scraped: typeof totalScraped === 'number' && Number.isFinite(totalScraped)
      ? Math.floor(Math.max(0, totalScraped)) || 0
      : (totalFiltered * 7),
    total_filtered_defects: totalFiltered,
    avg_negativity_score: typeof existingStats?.avg_negativity_score === 'number' && Number.isFinite(existingStats.avg_negativity_score)
      ? getSafeSentimentScore(existingStats.avg_negativity_score, avgScore)
      : avgScore,
    critical_defect_count: typeof existingStats?.critical_defect_count === 'number' && Number.isFinite(existingStats.critical_defect_count)
      ? Math.floor(Math.min(totalFiltered, Math.max(0, existingStats.critical_defect_count))) || 0
      : criticalCount,
    top_model: existingTopModel || topModelDisplay,
    top_platform: existingTopPlatform || topPlatformDisplay,
    duplicates_removed: typeof existingStats?.duplicates_removed === 'number' && Number.isFinite(existingStats.duplicates_removed)
      ? Math.floor(Math.max(0, existingStats.duplicates_removed)) || 0
      : 0,
    is_deduplicated: typeof existingStats?.is_deduplicated === 'boolean' ? existingStats.is_deduplicated : true,
  };
}

export const calculateReportStatistics = calculateKPIs;

/**
 * Returns safe fallback Daily EV Defect Reports data when loading fails or data is empty.
 */
export function getFallbackReportData(): DailyReportData {
  return {
    generated_at: new Date().toISOString(),
    pipeline_version: '1.0.0',
    statistics: {
      total_scraped: 0,
      total_filtered_defects: 0,
      avg_negativity_score: 0.0,
      critical_defect_count: 0,
      top_model: '해당 없음 (0건)',
      top_platform: '해당 없음 (0%)',
    },
    total_complaints_today: 0,
    top_defect_categories: [],
    reports: [],
  };
}

/**
 * High-fidelity canonical mock reports covering all 5 taxonomy pillars.
 * Used for offline test suites, visual previews, or when data files are completely missing.
 */
export const FALLBACK_MOCK_REPORTS: DefectReportItem[] = [
  {
    id: 'mock_bat_001',
    source: 'dcinside',
    url: 'https://gall.dcinside.com/mgallery/board/view/?id=car_new1&no=1284920',
    title: '전기차 ICCU 터져서 고속도로에서 멈춤',
    date: '2026-09-08',
    vehicle_model: '아이오닉5',
    vehicle_brand: '현대',
    defect_category: 'BATTERY_CHARGING',
    defect_category_ko: '배터리/충전',
    summary: '주행 중 갑작스러운 경고등 점등과 함께 ICCU 고장으로 차량 동력 상실 및 갓길 긴급 견인',
    verbatim_quote: '고속도로에서 100km로 달리는데 갑자기 퍽 소리 나더니 배터리 경고등 뜨고 악셀 먹통됨',
    slang_tags: ['ICCU폭탄', '벽돌차', '황천길'],
    sentiment_score: 0.96,
    severity: 'CRITICAL',
    is_authentic_defect: true,
  },
  {
    id: 'mock_drv_002',
    source: 'bobaedream',
    url: 'https://www.bobaedream.co.kr/view?code=national&No=2291045',
    title: '기아 EV3 빗길 주행하다가 뒤 털려서 가드레일 박을 뻔했습니다',
    date: '2026-09-08',
    vehicle_model: 'EV3',
    vehicle_brand: '기아',
    defect_category: 'DRIVING_POWERTRAIN',
    defect_category_ko: '주행/모터/등판',
    summary: '우천 고속 주행 시 리어 토션빔 접지력 상실 및 회생제동 개입으로 인한 피쉬테일 현상 발생',
    verbatim_quote: '비 오는 날 고속도로 이음새 밟고 회생제동 살짝 걸리는 순간 뒤쪽이 좌우로 사정없이 털리면서 피쉬테일 옴',
    slang_tags: ['피쉬테일', '토션빔털림', '회생제동슬립'],
    sentiment_score: 0.94,
    severity: 'CRITICAL',
    is_authentic_defect: true,
  },
  {
    id: 'mock_bld_003',
    source: 'bobaedream',
    url: 'https://www.bobaedream.co.kr/view?code=national&No=2290881',
    title: '출고 3일된 EV6 트렁크 누수로 스페어 공간 한강 됐습니다',
    date: '2026-09-08',
    vehicle_model: 'EV6',
    vehicle_brand: '기아',
    defect_category: 'BUILD_QUALITY',
    defect_category_ko: '단차/누수/마감',
    summary: '트렁크 테일게이트 웨더스트립 조립 불량으로 인한 우천 시 트렁크 하부 침수',
    verbatim_quote: '차 받은 지 3일 만에 폭우 내렸는데 오늘 트렁크 바닥 열어보니까 물이 찰랑찰랑 한강이네요',
    slang_tags: ['누수차', '수족관에디션', '단차지옥'],
    sentiment_score: 0.91,
    severity: 'WARNING',
    is_authentic_defect: true,
  },
  {
    id: 'mock_sft_004',
    source: 'dcinside',
    url: 'https://gall.dcinside.com/mgallery/board/view/?id=car_new1&no=1284550',
    title: '테슬라 모델Y OTA 최신 업데이트 받고 계기판 블랙아웃 벽돌됨',
    date: '2026-09-08',
    vehicle_model: '모델 Y',
    vehicle_brand: '테슬라',
    defect_category: 'SOFTWARE_ELECTRONICS',
    defect_category_ko: 'OTA/소프트웨어',
    summary: '차량 펌웨어 OTA 배포 설치 중 MCU 통신 오류로 인한 센터 디스플레이 완전 암전 및 운행 불가',
    verbatim_quote: '새벽에 와이파이 잡고 업데이트 눌렀는데 아침에 출근하려고 차 타니까 중앙 스크린 꺼져있고 리셋 눌러도 깜깜무소식',
    slang_tags: ['OTA벽돌', '블랙아웃', '어부바행'],
    sentiment_score: 0.95,
    severity: 'CRITICAL',
    is_authentic_defect: true,
  },
  {
    id: 'mock_svc_005',
    source: 'bobaedream',
    url: 'https://www.bobaedream.co.kr/view?code=national&No=2290412',
    title: '방지턱 하부 스쳤는데 배터리팩 긁혔다고 전손 3800만원 요구합니다',
    date: '2026-09-07',
    vehicle_model: '아이오닉6',
    vehicle_brand: '현대',
    defect_category: 'SERVICE_REPAIR_COST',
    defect_category_ko: 'AS/수리비',
    summary: '배터리 하부 케이스 미세 스크래치로 인한 서비스센터의 안전 규정상 배터리 전량 교체 및 3800만원 청구',
    verbatim_quote: '지하주차장 방지턱 살짝 긁혀서 소리 났길래 점검받으러 갔더니 하부 배터리 케이스 스크래치 났다고 배터리 통교체 3800만원 부름',
    slang_tags: ['수리비폭탄', '전손각', '통교체갑질'],
    sentiment_score: 0.98,
    severity: 'CRITICAL',
    is_authentic_defect: true,
  },
];

/**
 * Returns consistent, populated fallback mock Daily EV Defect Reports data when files are missing
 * and realistic mock data is explicitly required.
 */
export function getFallbackMockReportData(): DailyReportData {
  const reports = FALLBACK_MOCK_REPORTS.map((r, idx) => normalizeReport(r as unknown as Record<string, unknown>, idx));
  const statistics = calculateKPIs(reports);
  const catCountMap = new Map<string, number>();
  for (const r of reports) {
    const cat = r.defect_category || 'BUILD_QUALITY';
    catCountMap.set(cat, (catCountMap.get(cat) || 0) + 1);
  }
  const topDefectCategories = Array.from(catCountMap.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([category, count]) => ({
      category,
      count,
      ratio: reports.length > 0 ? Number((count / reports.length).toFixed(3)) : 0,
    }));

  return {
    generated_at: new Date().toISOString(),
    pipeline_version: '1.0.0-mock',
    statistics,
    total_complaints_today: reports.length,
    top_defect_categories: topDefectCategories,
    reports,
  };
}

/**
 * Main type-safe loader for Daily EV Defect Reports.
 * Provides safe fallback in case the data is empty or corrupted.
 */
export function getDailyReports(options?: { useMockOnEmpty?: boolean }): DailyReportData {
  try {
    let parsedInput: unknown = rawReportData;
    if (typeof parsedInput === 'string') {
      parsedInput = safeJsonParse(parsedInput, null);
    }

    const rawData = parsedInput as unknown as {
      generated_at?: string;
      pipeline_version?: string;
      statistics?: Partial<ReportStatistics>;
      total_complaints_today?: number;
      top_defect_categories?: Array<{
        category: string;
        count: number;
        ratio?: number;
        percentage?: number;
      }>;
      reports?: Record<string, unknown>[];
    } | null | undefined;

    if (!rawData || typeof rawData !== 'object' || (Array.isArray(rawData) && rawData.length === 0)) {
      return options?.useMockOnEmpty ? getFallbackMockReportData() : getFallbackReportData();
    }

    if (!Array.isArray(rawData) && Object.keys(rawData).length === 0) {
      return options?.useMockOnEmpty ? getFallbackMockReportData() : getFallbackReportData();
    }

    const rawReports = Array.isArray(rawData)
      ? (rawData as Record<string, unknown>[])
      : (Array.isArray(rawData?.reports) ? rawData.reports : []);

    const validRawReports = rawReports.filter(
      (item): item is Record<string, unknown> => Boolean(item && typeof item === 'object' && !Array.isArray(item))
    );
    const droppedCorruptCount = rawReports.length - validRawReports.length;

    const { reports, summary: dedupSummary } = deduplicateReports(validRawReports);

    if (reports.length === 0 && options?.useMockOnEmpty) {
      return getFallbackMockReportData();
    }

    const canTrustUpstreamAggregates =
      dedupSummary.duplicatesRemoved === 0 && droppedCorruptCount === 0 && reports.length > 0;

    const rawStats = rawData?.statistics && typeof rawData.statistics === 'object' && !Array.isArray(rawData.statistics)
      ? rawData.statistics
      : undefined;
    const upstreamDuplicatesRemoved =
      typeof rawStats?.duplicates_removed === 'number' && Number.isFinite(rawStats.duplicates_removed)
        ? Math.floor(Math.max(0, rawStats.duplicates_removed))
        : 0;
    const statsInput: Partial<ReportStatistics> = canTrustUpstreamAggregates
      ? {
          ...rawStats,
          duplicates_removed: upstreamDuplicatesRemoved,
          is_deduplicated: true,
        }
      : {
          total_scraped: rawStats?.total_scraped,
          duplicates_removed: upstreamDuplicatesRemoved + dedupSummary.duplicatesRemoved,
          is_deduplicated: true,
        };
    const statistics = calculateKPIs(reports, statsInput);

    const mergedTopCategories = new Map<string, { category: string; count: number; ratio: number; percentage?: number }>();
    if (canTrustUpstreamAggregates && Array.isArray(rawData?.top_defect_categories)) {
      for (const cat of rawData.top_defect_categories) {
        if (!cat || typeof cat !== 'object' || Array.isArray(cat)) continue;
        if (typeof cat.category !== 'string') continue;
        const cleanedCategory = sanitizeText(cat.category);
        if (!cleanedCategory || isForbiddenPrototypeKey(cleanedCategory)) continue;
        const resolved = resolveCategory(cleanedCategory);
        const safeCount = typeof cat.count === 'number' && Number.isFinite(cat.count) ? Math.floor(Math.max(0, cat.count)) : 0;
        const rawRatio = cat.ratio;
        const rawPct = cat.percentage;
        const hasFiniteRatio = typeof rawRatio === 'number' && Number.isFinite(rawRatio);
        const hasFinitePct = typeof rawPct === 'number' && Number.isFinite(rawPct);
        const safePct = hasFinitePct ? Math.min(100, Math.max(0, rawPct)) : 0;
        const derivedRatio = hasFiniteRatio
          ? Math.min(1, Math.max(0, rawRatio))
          : hasFinitePct
            ? Math.min(1, Math.max(0, Number((safePct / 100).toFixed(3))))
            : 0;
        const existing = mergedTopCategories.get(resolved.code);
        if (existing) {
          existing.count += safeCount;
          existing.ratio = Math.min(1, Number((existing.ratio + derivedRatio).toFixed(3)));
          if (hasFinitePct) {
            existing.percentage = Math.min(100, Number(((existing.percentage ?? 0) + safePct).toFixed(1)));
          }
        } else {
          mergedTopCategories.set(resolved.code, {
            category: resolved.code,
            count: safeCount,
            ratio: derivedRatio,
            ...(hasFinitePct ? { percentage: safePct } : {}),
          });
        }
      }
    }
    let safeTopCategories = Array.from(mergedTopCategories.values()).sort((a, b) => b.count - a.count);

    if (safeTopCategories.length === 0 && reports.length > 0) {
      const catCountMap = new Map<string, number>();
      for (const r of reports) {
        const cat = r.defect_category || 'BUILD_QUALITY';
        catCountMap.set(cat, (catCountMap.get(cat) || 0) + 1);
      }
      safeTopCategories = Array.from(catCountMap.entries())
        .sort((a, b) => b[1] - a[1])
        .map(([category, count]) => ({
          category,
          count,
          ratio: reports.length > 0 ? Number((count / reports.length).toFixed(3)) : 0,
        }));
    }

    return {
      generated_at: typeof rawData?.generated_at === 'string' && rawData.generated_at.trim()
        ? sanitizeText(rawData.generated_at)
        : new Date().toISOString(),
      pipeline_version: typeof rawData?.pipeline_version === 'string' && rawData.pipeline_version.trim()
        ? sanitizeText(rawData.pipeline_version)
        : '1.0.0',
      statistics,
      total_complaints_today:
        canTrustUpstreamAggregates &&
        typeof rawData?.total_complaints_today === 'number' &&
        Number.isFinite(rawData.total_complaints_today)
          ? Math.floor(Math.max(0, rawData.total_complaints_today))
          : reports.length,
      top_defect_categories: safeTopCategories,
      reports,
    };
  } catch (error) {
    console.error('Failed to load daily reports, using safe fallback:', error);
    return options?.useMockOnEmpty ? getFallbackMockReportData() : getFallbackReportData();
  }
}
