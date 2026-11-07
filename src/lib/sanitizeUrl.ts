/**
 * URL sanitization and security utility to prevent XSS (e.g. javascript:, data:, blob: URI execution),
 * protocol poisoning, encoded scheme evasion, malicious open redirects, and prototype pollution.
 *
 * Only allows strictly safe schemes: http, https, mailto, tel, or safe relative root/anchor paths.
 * If the URL is invalid or uses an insecure scheme, falls back to '#' safe anchor.
 */

/**
 * Strictly allowed URI schemes for the application.
 */
export const ALLOWED_SCHEMES = new Set([
  'http',
  'https',
  'mailto',
  'tel',
]);

/**
 * Forbidden URI pseudoprotocols and schemes that must NEVER be executed.
 */
export const FORBIDDEN_SCHEMES = new Set([
  'javascript',
  'data',
  'vbscript',
  'blob',
  'file',
  'about',
  'feed',
  'intent',
  'android-app',
  'ios-app',
  'ms-appx',
  'ws',
  'wss',
  'ftp',
  'ftps',
  'tftp',
  'gopher',
  'dict',
  'ldap',
  'ldaps',
  'ssh',
  'sftp',
  'telnet',
  'vnc',
  'rdp',
  'jar',
  'filesystem',
  'chrome',
  'chrome-extension',
  'moz-extension',
  'edge',
  'livescript',
  'mocha',
  'view-source',
  'content',
  'facetime',
  'skype',
  'sms',
]);

/**
 * Official South Korea Government and Public Authority Domains for EV Policy, Recalls, and Subsidies.
 */
export const GOVERNMENT_DOMAINS = Object.freeze([
  'ev.or.kr',
  'molit.go.kr',
  'car.go.kr',
  'kotsa.or.kr',
  'me.go.kr',
  'gov.kr',
  'data.go.kr',
  'law.go.kr',
  'motie.go.kr',
  'nhtsa.gov',
  'epa.gov',
]);

/**
 * Verified Electric Vehicle and Automotive Manufacturer Domains (Domestic & Global).
 */
export const MANUFACTURER_DOMAINS = Object.freeze([
  'hyundai.com',
  'hyundai.co.kr',
  'genesis.com',
  'kia.com',
  'kia.co.kr',
  'tesla.com',
  'teslamotors.com',
  'mercedes-benz.com',
  'mercedes-benz.co.kr',
  'bmw.com',
  'bmw.co.kr',
  'polestar.com',
  'porsche.com',
  'porsche.co.kr',
  'byd.com',
  'bydauto.com',
  'chevrolet.com',
  'chevrolet.co.kr',
  'audi.com',
  'audi.co.kr',
  'volkswagen.com',
  'volkswagen.co.kr',
  'volvocars.com',
  'rivian.com',
  'lucidmotors.com',
  'kg-mobility.com',
  'renaultkoream.com',
]);

/**
 * Verified Automotive and EV Community / Forum Domains Scraped or Referenced by EV Stealth.
 */
export const COMMUNITY_DOMAINS = Object.freeze([
  'bobaedream.co.kr',
  'clien.net',
  'ppomppu.co.kr',
  'dcinside.com',
  'naver.com',
  'daum.net',
  'teamblind.com',
  'reddit.com',
  'redd.it',
  'teslamotorsclub.com',
  'rivianforums.com',
  'lucidowners.com',
  'autohome.com.cn',
  'dongchedi.com',
  'weibo.com',
  'bilibili.com',
  'zhihu.com',
  'xiaohongshu.com',
]);

/**
 * Trusted First-Party and Local Development Domains.
 */
export const INTERNAL_DOMAINS = Object.freeze([
  'ev-stealth.kr',
  'ev-stealth.local',
  'localhost',
  '127.0.0.1',
]);

/**
 * Comprehensive Set of All Whitelisted Domains.
 */
export const ALL_WHITELISTED_DOMAINS = Object.freeze([
  ...GOVERNMENT_DOMAINS,
  ...MANUFACTURER_DOMAINS,
  ...COMMUNITY_DOMAINS,
  ...INTERNAL_DOMAINS,
]);

export type DomainCategory = 'government' | 'manufacturer' | 'community' | 'internal' | 'untrusted';

export interface SanitizeUrlOptions {
  /** If true, external URLs must match trusted domain categories */
  requireWhitelistedDomain?: boolean;
  /** Restrict whitelist check to specific domain categories */
  allowedCategories?: DomainCategory[];
}

/**
 * Dangerous parameter keys and expressions associated with Prototype Pollution attacks.
 */
export const PROTOTYPE_POLLUTION_REGEX = /^(?:__proto__|constructor|prototype)(?:[.[\]\s]|$)/i;

/**
 * Decodes HTML entities (numeric decimal/hex and named entities) to uncover obfuscated URI schemes.
 * Handles decimal (&#58;), hex (&#x3a;), optional trailing semicolons, and common named entities (&colon;).
 */
export function decodeHtmlEntities(str: string): string {
  return str
    .replace(/&#x([0-9a-fA-F]+);?/gi, (_, hex) => {
      try {
        const code = parseInt(hex, 16);
        return code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : '';
      } catch {
        return '';
      }
    })
    .replace(/&#([0-9]+);?/g, (_, dec) => {
      try {
        const code = parseInt(dec, 10);
        return code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : '';
      } catch {
        return '';
      }
    })
    .replace(/&colon;?/gi, ':')
    .replace(/&tab;?/gi, '\t')
    .replace(/&newline;?/gi, '\n')
    .replace(/&sol;?/gi, '/')
    .replace(/&bsol;?/gi, '\\')
    .replace(/&quot;?/gi, '"')
    .replace(/&apos;?/gi, "'")
    .replace(/&lt;?/gi, '<')
    .replace(/&gt;?/gi, '>')
    .replace(/&amp;?/gi, '&');
}

/**
 * Iteratively decodes percent-encoded sequences up to 5 passes to uncover multi-layer encoding bypasses.
 * Fallback decodes individual ASCII %XX sequences if a malformed byte throws URIError.
 * Also neutralizes Microsoft %uXXXX unicode bypass patterns.
 */
export function safeDecodePercent(str: string): string {
  let prev = str;
  // Decode legacy %uXXXX encoding if present
  if (/%u[0-9a-fA-F]{4}/i.test(prev)) {
    prev = prev.replace(/%u([0-9a-fA-F]{4})/gi, (_, hex) => {
      try {
        return String.fromCharCode(parseInt(hex, 16));
      } catch {
        return '';
      }
    });
  }

  for (let i = 0; i < 5; i++) {
    try {
      const decoded = decodeURIComponent(prev);
      if (decoded === prev) break;
      prev = decoded;
    } catch {
      // Decode individual %XX tokens if full decodeURIComponent threw (e.g. malformed trailing byte)
      try {
        const partialDecoded = prev.replace(/%([0-9a-fA-F]{2})/g, (match, hex) => {
          const byte = parseInt(hex, 16);
          return byte < 128 ? String.fromCharCode(byte) : match;
        });
        if (partialDecoded === prev) break;
        prev = partialDecoded;
      } catch {
        break;
      }
    }
  }
  return prev;
}

/**
 * Normalizes and extracts the URI scheme if one is present, uncovering obfuscated or encoded schemes.
 * Uses a two-pass decode in case percent decoding reveals newly formed HTML entities.
 */
export function extractAndNormalizeScheme(raw: string): string {
  let decoded = safeDecodePercent(decodeHtmlEntities(raw));
  // Second pass: uncover nested entity sequences like %26colon; or %26%23x3a%3b
  decoded = safeDecodePercent(decodeHtmlEntities(decoded));

  const stripped = decoded
    .replace(/\\0|\\x00|\\u0000|\\u\{0+\}/gi, '')
    .replace(/[\s\x00-\x1f\x7f-\x9f\u00ad\u200b-\u200f\ufeff\u200e\u200f\u2028-\u202f\u2060-\u206f]/gi, '')
    .toLowerCase();

  const colonIndex = stripped.indexOf(':');
  if (colonIndex === -1) return '';

  const slashIndex = stripped.indexOf('/');
  const qmarkIndex = stripped.indexOf('?');
  const hashIndex = stripped.indexOf('#');

  // If a slash, question mark, or hash occurs before the colon, the colon is part of the path/query/hash, not a scheme
  if (
    (slashIndex !== -1 && slashIndex < colonIndex) ||
    (qmarkIndex !== -1 && qmarkIndex < colonIndex) ||
    (hashIndex !== -1 && hashIndex < colonIndex)
  ) {
    return '';
  }

  const scheme = stripped.slice(0, colonIndex);
  // Scheme must be a valid RFC 3986 identifier starting with a letter
  if (!/^[a-z][a-z0-9+.-]*$/.test(scheme)) {
    return '';
  }
  return scheme;
}

/**
 * Checks if a candidate URL is a malicious open redirect vector (protocol-relative, backslash, or encoded slashes).
 */
export function isOpenRedirect(raw: string): boolean {
  let decoded = safeDecodePercent(decodeHtmlEntities(raw));
  decoded = safeDecodePercent(decodeHtmlEntities(decoded));
  const trimmedDecoded = decoded.trim();
  const trimmedRaw = raw.trim();

  // Protocol relative or multiple leading slashes/backslashes (e.g. //evil.com, \\\evil.com)
  if (/^[/\\]{2,}/.test(trimmedDecoded) || /^[/\\]{2,}/.test(trimmedRaw)) {
    return true;
  }
  // Mixed slash/backslash leading (e.g. /\evil.com, \/evil.com)
  if (/^[/\\][\\]/.test(trimmedDecoded) || /^[/\\][\\]/.test(trimmedRaw)) {
    return true;
  }
  // Single backslash leading (e.g. \evil.com)
  if (/^\\/.test(trimmedDecoded) || /^\\/.test(trimmedRaw)) {
    return true;
  }
  // Encoded slash/backslash following a single slash (e.g. /%5cevil.com, /%2fevil.com)
  if (
    /^\/(?:%2f|%5c)/i.test(trimmedRaw) ||
    /^\/(?:%2f|%5c)/i.test(trimmedDecoded)
  ) {
    return true;
  }
  return false;
}

/**
 * Checks whether a parameter key (or its percent-decoded representation) matches a prototype pollution pattern.
 */
export function isPrototypePollutionKey(key: string): boolean {
  if (!key) return false;
  // Raw check
  if (PROTOTYPE_POLLUTION_REGEX.test(key)) return true;
  // Decoded check to uncover percent-encoded keys (%5f%5fproto%5f%5f, %63onstructor, etc.)
  try {
    const decoded = safeDecodePercent(key);
    if (PROTOTYPE_POLLUTION_REGEX.test(decoded)) return true;
  } catch {
    // Malformed encoding in key
  }
  return false;
}

/**
 * Strips dangerous prototype pollution query parameters from an absolute URL or relative path.
 * Retains all legitimate query parameters, paths, and anchors.
 */
export function stripPrototypePollutionQueryParams(url: string): string {
  if (!url || !url.includes('?')) return url;

  // Case 1: Absolute URL
  if (/^https?:\/\//i.test(url)) {
    try {
      const parsed = new URL(url);
      if (!parsed.search) return url;
      const params = new URLSearchParams(parsed.search);
      let mutated = false;
      const keysToRemove: string[] = [];

      for (const key of params.keys()) {
        if (isPrototypePollutionKey(key)) {
          keysToRemove.push(key);
          mutated = true;
        }
      }

      if (!mutated) return url;

      for (const key of keysToRemove) {
        params.delete(key);
      }

      parsed.search = params.toString();
      return parsed.toString();
    } catch {
      return url;
    }
  }

  // Case 2: Relative route with query string (e.g. /recall-portal?model=ioniq&__proto__[admin]=true)
  try {
    const dummyBase = 'http://safe-internal.local';
    const parsed = new URL(url, dummyBase);
    if (!parsed.search) return url;
    const params = new URLSearchParams(parsed.search);
    let mutated = false;
    const keysToRemove: string[] = [];

    for (const key of params.keys()) {
      if (isPrototypePollutionKey(key)) {
        keysToRemove.push(key);
        mutated = true;
      }
    }

    if (!mutated) return url;

    for (const key of keysToRemove) {
      params.delete(key);
    }

    const searchStr = params.toString() ? '?' + params.toString() : '';
    const hashStr = parsed.hash || '';
    return parsed.pathname + searchStr + hashStr;
  } catch {
    return url;
  }
}

/**
 * Safely parses a query string or URL into a clean Object with null prototype,
 * completely immune to prototype pollution (__proto__, constructor, prototype).
 */
export function parseSafeQueryParams(input?: unknown): Record<string, string> {
  const result: Record<string, string> = Object.create(null);
  if (!input || typeof input !== 'string') return result;

  let searchStr = input.trim();
  const qmarkIndex = searchStr.indexOf('?');
  if (qmarkIndex !== -1) {
    searchStr = searchStr.slice(qmarkIndex + 1);
  }
  const hashIndex = searchStr.indexOf('#');
  if (hashIndex !== -1) {
    searchStr = searchStr.slice(0, hashIndex);
  }
  if (!searchStr) return result;

  try {
    const searchParams = new URLSearchParams(searchStr);
    for (const [key, value] of searchParams.entries()) {
      if (!isPrototypePollutionKey(key)) {
        result[key] = value;
      }
    }
  } catch {
    // Return safe object on parsing failure
  }

  return result;
}

/**
 * Safely extracts the normalized hostname from a URL string or hostname input.
 * Returns empty string if parsing fails or input is invalid.
 */
export function extractHostname(urlOrHost?: unknown): string {
  if (!urlOrHost || typeof urlOrHost !== 'string') return '';
  const trimmed = urlOrHost.trim();
  if (!trimmed) return '';

  // Bare hostname without protocol or slashes
  if (!trimmed.includes('/') && !trimmed.includes(':') && /^[a-zA-Z0-9.\-]+$/.test(trimmed)) {
    return trimmed.toLowerCase().replace(/\.$/, '');
  }

  try {
    if (/^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(trimmed)) {
      const parsed = new URL(trimmed);
      return (parsed.hostname || '').toLowerCase().replace(/\.$/, '');
    }
    const parsed = new URL('http://' + trimmed);
    return (parsed.hostname || '').toLowerCase().replace(/\.$/, '');
  } catch {
    return '';
  }
}

/**
 * Checks whether a candidate hostname safely matches a target trusted domain.
 * Strictly prevents prefix/suffix spoofing (e.g. fake-ev.or.kr, ev.or.kr.evil.com).
 */
export function matchDomain(candidateHost: string, trustedDomain: string): boolean {
  if (!candidateHost || !trustedDomain) return false;
  const normHost = candidateHost.toLowerCase().replace(/\.$/, '');
  const normTarget = trustedDomain.toLowerCase().replace(/\.$/, '');
  return normHost === normTarget || normHost.endsWith('.' + normTarget);
}

/**
 * Checks whether a candidate URL or hostname matches any domain in a given domain whitelist.
 */
export function matchesAnyDomain(urlOrHost: unknown, domainList: readonly string[]): boolean {
  const host = extractHostname(urlOrHost);
  if (!host) return false;
  return domainList.some((trusted) => matchDomain(host, trusted));
}

/**
 * Checks if a domain is an official Korean or international EV government regulatory portal.
 */
export function isGovernmentDomain(urlOrHost?: unknown): boolean {
  return matchesAnyDomain(urlOrHost, GOVERNMENT_DOMAINS);
}

/**
 * Checks if a domain is a verified EV or automotive manufacturer.
 */
export function isManufacturerDomain(urlOrHost?: unknown): boolean {
  return matchesAnyDomain(urlOrHost, MANUFACTURER_DOMAINS);
}

/**
 * Checks if a domain is a verified community forum or consumer defect disclosure board.
 */
export function isCommunityDomain(urlOrHost?: unknown): boolean {
  return matchesAnyDomain(urlOrHost, COMMUNITY_DOMAINS);
}

/**
 * Checks if a domain is an internal or local development host.
 */
export function isInternalDomain(urlOrHost?: unknown): boolean {
  return matchesAnyDomain(urlOrHost, INTERNAL_DOMAINS);
}

/**
 * Checks if a domain is present in any trusted whitelist category.
 */
export function isWhitelistedDomain(urlOrHost?: unknown): boolean {
  return matchesAnyDomain(urlOrHost, ALL_WHITELISTED_DOMAINS);
}

/**
 * Classifies a URL or hostname into its corresponding domain security category.
 */
export function classifyDomain(urlOrHost?: unknown): DomainCategory {
  if (isGovernmentDomain(urlOrHost)) return 'government';
  if (isManufacturerDomain(urlOrHost)) return 'manufacturer';
  if (isCommunityDomain(urlOrHost)) return 'community';
  if (isInternalDomain(urlOrHost)) return 'internal';
  return 'untrusted';
}

/**
 * Sanitizes an untrusted URL input to prevent XSS, scheme injection, open redirects,
 * and prototype pollution in query parameters.
 *
 * Supports optional domain whitelisting enforcement via options.requireWhitelistedDomain.
 * Returns '#' if the URL is unsafe, empty, invalid, or untrusted.
 */
export function sanitizeSafeUrl(url?: unknown, options?: SanitizeUrlOptions): string {
  if (!url || typeof url !== 'string') return '#';
  const trimmed = url.trim();
  if (!trimmed) return '#';

  // Explicitly disallow raw control characters or null bytes
  if (/[\x00-\x1f\x7f]/.test(trimmed)) {
    return '#';
  }

  // Reject literal null byte escape sequences in string (\0, \x00, \u0000, \u{0})
  if (/\\0|\\x00|\\u0000|\\u\{0+\}/i.test(trimmed)) {
    return '#';
  }

  // Reject percent-encoded null bytes (%00) and CRLF injection (%0d, %0a)
  if (/(?:%00|%0d|%0a)/i.test(trimmed)) {
    return '#';
  }

  // Extract scheme and check against allowed and forbidden schemes
  const normalizedScheme = extractAndNormalizeScheme(trimmed);
  if (normalizedScheme) {
    if (FORBIDDEN_SCHEMES.has(normalizedScheme) || !ALLOWED_SCHEMES.has(normalizedScheme)) {
      return '#';
    }
  }

  // Block protocol-relative URLs and backslash redirects
  if (isOpenRedirect(trimmed)) {
    return '#';
  }

  // Anchor links (#...)
  if (/^#[a-zA-Z0-9_\-.:]*$/.test(trimmed)) {
    return trimmed;
  }

  // Safe internal relative routes (must start with / and not followed by / or \ or encoded slashes, no backslashes anywhere in path)
  if (/^\/(?![/\\])/.test(trimmed) && !/[\s<>"'\\]/.test(trimmed) && !/^\/(?:%2f|%5c)/i.test(trimmed)) {
    // Strip any prototype pollution from internal relative query params
    return stripPrototypePollutionQueryParams(trimmed);
  }

  // mailto:
  if (/^mailto:[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/i.test(trimmed)) {
    return trimmed;
  }

  // tel:
  if (/^tel:[+0-9\-#*().]+$/i.test(trimmed)) {
    return trimmed;
  }

  // Absolute web URLs: must be http or https with valid hostname
  if (/^https?:\/\//i.test(trimmed) && !/[\s<>"'\\]/.test(trimmed)) {
    try {
      const parsed = new URL(trimmed);
      if (
        (parsed.protocol === 'http:' || parsed.protocol === 'https:') &&
        parsed.hostname &&
        parsed.hostname.length > 0
      ) {
        // Enforce safe domain whitelisting if requested
        if (options?.requireWhitelistedDomain) {
          const category = classifyDomain(parsed.hostname);
          if (options.allowedCategories && options.allowedCategories.length > 0) {
            if (!options.allowedCategories.includes(category)) {
              return '#';
            }
          } else if (!isWhitelistedDomain(parsed.hostname)) {
            return '#';
          }
        }

        // Clean query parameters of any prototype pollution keys
        return stripPrototypePollutionQueryParams(trimmed);
      }
    } catch {
      return '#';
    }
  }

  return '#';
}

/**
 * Sanitizes a URL and strictly enforces that external destinations belong to the verified EV domain whitelist.
 */
export function sanitizeWhitelistedUrl(
  url?: unknown,
  allowedCategories?: DomainCategory[]
): string {
  return sanitizeSafeUrl(url, {
    requireWhitelistedDomain: true,
    allowedCategories,
  });
}

/**
 * Checks if a URL is strictly safe.
 */
export function isSafeUrl(url?: unknown): boolean {
  return sanitizeSafeUrl(url) !== '#';
}

/**
 * Checks if a sanitized URL is an external link (http:// or https://).
 */
export function isExternalUrl(url?: unknown): boolean {
  const safe = sanitizeSafeUrl(url);
  return safe.startsWith('http://') || safe.startsWith('https://');
}

/**
 * Sanitizes raw text from untrusted sources (e.g. community quotes, scraped defect reports)
 * to prevent control character injection, Unicode bidirectional override spoofing, and null bytes.
 */
export function sanitizeText(text?: unknown): string {
  if (text === null || text === undefined) return '';
  return String(text)
    .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, '')
    .replace(/[\u202A-\u202E\u2066-\u2069]/g, '')
    .trim();
}

/**
 * Safely parses JSON strings while stripping dangerous prototype pollution keys
 * (__proto__, constructor, prototype).
 */
export function safeJsonParse<T = unknown>(jsonString?: unknown, fallback: T = {} as T): T {
  if (!jsonString || typeof jsonString !== 'string') return fallback;
  try {
    return JSON.parse(jsonString, (key, value) => {
      if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
        return undefined;
      }
      return value;
    }) as T;
  } catch {
    return fallback;
  }
}

/**
 * Safely serializes data into a sanitized JSON string suitable for inclusion in
 * <script type="application/ld+json">.
 * Neutralizes script tag breakout attacks (</script>, <!--), escapes &, and strips prototype pollution.
 */
export function serializeJsonLd(data: unknown): string {
  if (data === null || data === undefined) return '{}';
  try {
    const json = JSON.stringify(data, (key, value) => {
      if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
        return undefined;
      }
      return value;
    });
    if (!json) return '{}';
    return json
      .replace(/</g, '\\u003c')
      .replace(/>/g, '\\u003e')
      .replace(/&/g, '\\u0026')
      .replace(/\u2028/g, '\\u2028')
      .replace(/\u2029/g, '\\u2029');
  } catch {
    return '{}';
  }
}
