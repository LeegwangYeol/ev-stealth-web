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
export const PROTOTYPE_POLLUTION_REGEX = /(?:^|[.[\]\s'"])(?:__proto__|constructor|prototype|Object\.prototype|__defineGetter__|__defineSetter__|__lookupGetter__|__lookupSetter__)(?:[.[\]\s'"]|$)/i;

/**
 * Decodes HTML entities (numeric decimal/hex and named entities) to uncover obfuscated URI schemes.
 * Handles decimal (&#58;), hex (&#x3a;), optional trailing semicolons on numeric/legacy entities, and named entities (&colon;).
 */
export function decodeHtmlEntities(str: string): string {
  if (!str || typeof str !== 'string') return '';
  if (!str.includes('&')) return str;
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
    .replace(/&colon;/gi, ':')
    .replace(/&tab;/gi, '\t')
    .replace(/&newline;/gi, '\n')
    .replace(/&nbsp;?/gi, ' ')
    .replace(/&sol;/gi, '/')
    .replace(/&bsol;/gi, '\\')
    .replace(/&quot;?/gi, '"')
    .replace(/&apos;/gi, "'")
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
  if (!str || typeof str !== 'string') return '';
  if (!str.includes('%')) return str;
  let prev = str;

  for (let i = 0; i < 5; i++) {
    let working = prev;
    // Decode legacy %uXXXX encoding on each pass to catch multi-layer encodings (e.g. %25u0073)
    if (/%u[0-9a-fA-F]{4}/i.test(working)) {
      working = working.replace(/%u([0-9a-fA-F]{4})/gi, (_, hex) => {
        try {
          return String.fromCharCode(parseInt(hex, 16));
        } catch {
          return '';
        }
      });
    }
    try {
      const decoded = decodeURIComponent(working);
      if (decoded === prev) break;
      prev = decoded;
    } catch {
      // Decode individual %XX tokens if full decodeURIComponent threw (e.g. malformed trailing byte)
      try {
        const partialDecoded = working.replace(/%([0-9a-fA-F]{2})/g, (match, hex) => {
          const byte = parseInt(hex, 16);
          return byte < 128 ? String.fromCharCode(byte) : match;
        });
        if (partialDecoded === prev) break;
        prev = partialDecoded;
      } catch {
        prev = working;
        break;
      }
    }
  }
  return prev;
}

function extractSchemeFromDecoded(decoded: string): string {
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
 * Normalizes and extracts the URI scheme if one is present, uncovering obfuscated or encoded schemes.
 * Uses a two-pass decode in case percent decoding reveals newly formed HTML entities.
 */
export function extractAndNormalizeScheme(raw: string): string {
  if (!raw || typeof raw !== 'string') return '';
  let decoded = safeDecodePercent(decodeHtmlEntities(raw));
  // Second pass: uncover nested entity sequences like %26colon; or %26%23x3a%3b
  decoded = safeDecodePercent(decodeHtmlEntities(decoded));
  return extractSchemeFromDecoded(decoded);
}

function isOpenRedirectWithDecoded(trimmedRaw: string, decoded: string): boolean {
  const trimmedDecoded = decoded.trim();

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
 * Checks if a candidate URL is a malicious open redirect vector (protocol-relative, backslash, or encoded slashes).
 */
export function isOpenRedirect(raw: string): boolean {
  if (!raw || typeof raw !== 'string') return false;
  let decoded = safeDecodePercent(decodeHtmlEntities(raw));
  decoded = safeDecodePercent(decodeHtmlEntities(decoded));
  return isOpenRedirectWithDecoded(raw.trim(), decoded);
}

/**
 * Checks whether a parameter key (or its percent-decoded representation) matches a prototype pollution pattern.
 */
export function isPrototypePollutionKey(key: string): boolean {
  if (!key || typeof key !== 'string') return false;
  const stripControl = /[\x00-\x1f\x7f-\x9f\u00ad\u200b-\u200f\ufeff\u2028-\u202f\u2060-\u206f]/g;
  const cleanRaw = key.replace(stripControl, '');
  // Raw check
  if (PROTOTYPE_POLLUTION_REGEX.test(cleanRaw)) return true;
  // Decoded check to uncover percent-encoded keys (%5f%5fproto%5f%5f, %63onstructor, __proto__%00, etc.)
  try {
    const decoded = safeDecodePercent(key).replace(stripControl, '');
    if (PROTOTYPE_POLLUTION_REGEX.test(decoded)) return true;
  } catch {
    // Malformed encoding in key
  }
  return false;
}

function removePrototypePollutionParams(params: URLSearchParams): boolean {
  const keysToRemove = new Set<string>();
  for (const key of params.keys()) {
    if (isPrototypePollutionKey(key)) {
      keysToRemove.add(key);
    }
  }
  if (keysToRemove.size === 0) return false;
  for (const key of keysToRemove) {
    params.delete(key);
  }
  return true;
}

function stripPrototypePollutionFromParsedUrl(parsed: URL, originalUrl: string): string {
  if (!parsed.search) return originalUrl;
  const params = new URLSearchParams(parsed.search);
  if (!removePrototypePollutionParams(params)) return originalUrl;

  parsed.search = params.toString();
  return parsed.toString();
}

/**
 * Strips dangerous prototype pollution query parameters from an absolute URL or relative path.
 * Retains all legitimate query parameters, paths, and anchors.
 */
export function stripPrototypePollutionQueryParams(url: string): string {
  if (!url || typeof url !== 'string' || !url.includes('?')) return typeof url === 'string' ? url : '';

  // Case 1: Absolute URL
  if (/^https?:\/\//i.test(url)) {
    try {
      return stripPrototypePollutionFromParsedUrl(new URL(url), url);
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
    if (!removePrototypePollutionParams(params)) return url;

    // Collapse multiple leading slashes after dot-segment resolution so relative paths never become protocol-relative //host
    const safePath = parsed.pathname.replace(/^\/{2,}/, '/');
    const searchStr = params.toString() ? '?' + params.toString() : '';
    const hashStr = parsed.hash || '';
    return safePath + searchStr + hashStr;
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
  if (!searchStr) return result;

  // If hash comes before question mark (e.g. /path#section?query=1), the query belongs to the hash fragment, not searchParams
  const hashIndex = searchStr.indexOf('#');
  const qmarkIndex = searchStr.indexOf('?');
  if (hashIndex !== -1 && (qmarkIndex === -1 || hashIndex < qmarkIndex)) {
    return result;
  }

  if (qmarkIndex !== -1) {
    searchStr = searchStr.slice(qmarkIndex + 1);
  }
  const trailingHashIndex = searchStr.indexOf('#');
  if (trailingHashIndex !== -1) {
    searchStr = searchStr.slice(0, trailingHashIndex);
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
  if (/[\x00-\x1f\x7f-\x9f\u00ad\u200b-\u200f\u2028-\u202f\u2060-\u206f\ufeff]/u.test(urlOrHost)) {
    return '';
  }
  const trimmed = urlOrHost.trim();
  if (!trimmed || trimmed.includes('\\') || trimmed.startsWith('/')) return '';

  // Bare hostname without protocol or slashes
  if (!trimmed.includes('/') && !trimmed.includes(':') && !trimmed.includes('@') && /^[a-zA-Z0-9.\-]+$/.test(trimmed)) {
    return trimmed.toLowerCase().replace(/\.+$/, '');
  }

  try {
    const parsed = /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(trimmed)
      ? new URL(trimmed)
      : new URL('http://' + trimmed);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return '';
    if (parsed.username || parsed.password) return '';
    return (parsed.hostname || '').toLowerCase().replace(/\.+$/, '');
  } catch {
    return '';
  }
}

/**
 * Checks whether a candidate hostname safely matches a target trusted domain.
 * Strictly prevents prefix/suffix spoofing (e.g. fake-ev.or.kr, ev.or.kr.evil.com).
 */
export function matchDomain(candidateHost: string, trustedDomain: string): boolean {
  if (!candidateHost || !trustedDomain || typeof candidateHost !== 'string' || typeof trustedDomain !== 'string') return false;
  const normHost = candidateHost.toLowerCase().replace(/\.+$/, '');
  const normTarget = trustedDomain.toLowerCase().replace(/\.+$/, '');
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

  // 1. Check for raw control characters or null bytes in untrimmed input (rejecting embedded nulls, C0/C1, separators)
  // Allows standard leading/trailing whitespace (\t, \r, \n, space) to be trimmed cleanly, but blocks all other raw controls
  if (/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u00ad\u200b-\u200f\u2028-\u202f\u2060-\u206f\ufeff]/u.test(url)) {
    return '#';
  }

  const trimmed = url.trim();
  if (!trimmed) return '#';

  // 2. Reject if any control characters remain after trim (e.g. tabs or newlines within the URL body)
  if (/[\x00-\x1f\x7f-\x9f\u00ad\u200b-\u200f\u2028-\u202f\u2060-\u206f\ufeff]/u.test(trimmed)) {
    return '#';
  }

  // 3. Reject literal escape sequences in string for null or control characters (\0, \x00-\x1f, \u0000-\u001f, etc.)
  if (/\\(?:0|x0[0-9a-fA-F]|x1[0-9a-fA-F]|x7[fF]|x[89][0-9a-fA-F]|u00[0-1][0-9a-fA-F]|u007[fF]|u00[89][0-9a-fA-F]|u\{0+\})/i.test(trimmed)) {
    return '#';
  }

  // 4. Reject percent-encoded C0 controls (%00-%1F) and DEL (%7F)
  if (/%(?:0[0-9a-fA-F]|1[0-9a-fA-F]|7[fF])/i.test(trimmed)) {
    return '#';
  }

  // 5. Reject Microsoft unicode percent-encoding for control characters (%u0000-%u001F, %u007F-%u009F, %u2028-%u2029)
  if (/%u(?:00[0-1][0-9a-fA-F]|007[fF]|00[89][0-9a-fA-F]|202[89]|200[b-fB-F]|feff|FEFF)/i.test(trimmed)) {
    return '#';
  }

  // 6. Multi-pass decode entities and percent-encodings to detect nested/obfuscated control characters & HTML null entities
  if (/&#(?:0+|x0+)(?:;|[^0-9a-fA-F]|$)/i.test(trimmed)) {
    return '#';
  }
  const decodedPass1 = safeDecodePercent(decodeHtmlEntities(trimmed));
  if (/&#(?:0+|x0+)(?:;|[^0-9a-fA-F]|$)/i.test(decodedPass1)) {
    return '#';
  }
  const decodedCheck = safeDecodePercent(decodeHtmlEntities(decodedPass1));
  if (/[\x00-\x1f\x7f-\x9f\u00ad\u200b-\u200f\u2028-\u202f\u2060-\u206f\ufeff]/u.test(decodedCheck)) {
    return '#';
  }

  // 7. Extract scheme once from decodedCheck and verify against forbidden/allowed schemes
  const normalizedScheme = extractSchemeFromDecoded(decodedCheck);
  if (
    /(?:javascript|data|vbscript)\s*:/i.test(trimmed) ||
    /(?:javascript|data|vbscript)\s*:/i.test(decodedCheck)
  ) {
    if (!normalizedScheme || normalizedScheme === 'javascript' || normalizedScheme === 'data' || normalizedScheme === 'vbscript' || FORBIDDEN_SCHEMES.has(normalizedScheme)) {
      return '#';
    }
  }

  if (normalizedScheme) {
    if (FORBIDDEN_SCHEMES.has(normalizedScheme) || !ALLOWED_SCHEMES.has(normalizedScheme)) {
      return '#';
    }
  }

  // 8. Block protocol-relative URLs and backslash redirects
  if (isOpenRedirectWithDecoded(trimmed, decodedCheck)) {
    return '#';
  }

  // 9. Anchor links (#...)
  if (/^#[a-zA-Z0-9_\-.:]*$/.test(trimmed)) {
    return trimmed;
  }

  // 10. Safe internal relative routes (must start with / and not followed by / or \ or encoded slashes, no backslashes anywhere in path)
  if (/^\/(?![/\\])/.test(trimmed) && !/[\s<>"'\\]/.test(trimmed) && !/^\/(?:%2f|%5c)/i.test(trimmed)) {
    // Reject dot-segment paths (e.g. /..//evil.com, /..%2f/evil.com) that normalize to a protocol-relative //host path
    try {
      const resolvedPath = new URL(trimmed, 'http://safe-internal.local').pathname;
      if (resolvedPath.startsWith('//')) {
        return '#';
      }
      const decodedTrimmed = decodedCheck.trim();
      if (decodedTrimmed.startsWith('/')) {
        const resolvedDecodedPath = new URL(decodedTrimmed, 'http://safe-internal.local').pathname;
        if (resolvedDecodedPath.startsWith('//')) {
          return '#';
        }
      }
    } catch {
      return '#';
    }
    // Strip any prototype pollution from internal relative query params
    const cleaned = stripPrototypePollutionQueryParams(trimmed);
    return isOpenRedirectWithDecoded(cleaned, cleaned) ? '#' : cleaned;
  }

  // 11. mailto: (disjoint label/dot regex prevents ReDoS backtracking)
  if (/^mailto:[a-zA-Z0-9._%+-]+@(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$/i.test(trimmed)) {
    return trimmed;
  }

  // 12. tel:
  if (/^tel:[+0-9\-#*().]+$/i.test(trimmed)) {
    return trimmed;
  }

  // 13. Absolute web URLs: must be http or https with valid hostname and no authority userinfo
  if (/^https?:\/\//i.test(trimmed) && !/[\s<>"'\\]/.test(trimmed) && !/^https?:\/\/[^/?#]*@/i.test(trimmed)) {
    try {
      const parsed = new URL(trimmed);
      if (parsed.username || parsed.password) {
        return '#';
      }
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
        return parsed.search ? stripPrototypePollutionFromParsedUrl(parsed, trimmed) : trimmed;
      }
    } catch {
      return '#';
    }
  }

  return '#';
}

/**
 * Standard alias for sanitizeSafeUrl.
 */
export const sanitizeUrl = sanitizeSafeUrl;
export default sanitizeSafeUrl;

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
  return /^https?:\/\//i.test(safe);
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

const EXECUTABLE_BLOCK_TAGS = ['script', 'style', 'iframe', 'object', 'embed', 'svg', 'template'] as const;

/**
 * Strips `<tag ...>...</tag>` blocks in strictly O(N) time without catastrophic regex backtracking.
 */
function stripTagBlock(str: string, tagName: string): string {
  const openRe = new RegExp(`<${tagName}\\b`, 'gi');
  const closeRe = new RegExp(`</${tagName}\\s*>`, 'gi');
  let result = '';
  let cursor = 0;

  while (true) {
    openRe.lastIndex = cursor;
    const openMatch = openRe.exec(str);
    if (!openMatch) break;

    closeRe.lastIndex = openMatch.index + openMatch[0].length;
    const closeMatch = closeRe.exec(str);
    if (!closeMatch) break;

    result += str.slice(cursor, openMatch.index);
    cursor = closeMatch.index + closeMatch[0].length;
  }

  if (cursor === 0) return str;
  return result + str.slice(cursor);
}

function stripExecutableBlocks(str: string): string {
  if (!str.includes('</')) return str;
  let current = str;
  for (const tag of EXECUTABLE_BLOCK_TAGS) {
    current = stripTagBlock(current, tag);
    if (!current.includes('</')) break;
  }
  return current;
}

/**
 * Strips `<...>` tag pairs (matching `/<[^>]+>/g`) in strictly O(N) time,
 * avoiding polynomial backtracking on inputs with many unclosed `<` characters.
 */
function stripAngleTagPairs(str: string): string {
  if (!str.includes('<') || !str.includes('>')) return str;
  let result = '';
  let cursor = 0;

  while (cursor < str.length) {
    const openIdx = str.indexOf('<', cursor);
    if (openIdx === -1) break;

    const closeIdx = str.indexOf('>', openIdx + 1);
    if (closeIdx === -1) break;

    if (closeIdx === openIdx + 1) {
      result += str.slice(cursor, openIdx + 1);
      cursor = openIdx + 1;
    } else {
      result += str.slice(cursor, openIdx);
      cursor = closeIdx + 1;
    }
  }

  if (cursor === 0) return str;
  return result + str.slice(cursor);
}

/**
 * Strips trailing unclosed `<tag...` after the last `>` in strictly O(N) time.
 */
function stripTrailingUnclosedTag(str: string): string {
  const lastGt = str.lastIndexOf('>');
  const searchFrom = lastGt === -1 ? 0 : lastGt + 1;
  const tail = str.slice(searchFrom);
  if (!tail.includes('<')) return str;
  const match = /<[a-zA-Z\/!?][^>]*$/.exec(tail);
  if (!match) return str;
  return str.slice(0, searchFrom + match.index);
}

/**
 * Sanitizes and strips HTML tags from untrusted text (verbatim quotes, forum posts, defect titles, and summaries),
 * eliminating XSS injection vectors, neutralizing executable script/style/iframe blocks, decoding HTML entities,
 * and converting paragraph and break tags into clean, human-readable line breaks.
 */
export function stripHtmlTags(input?: unknown): string {
  if (input === null || input === undefined) return '';
  let str = String(input);
  if (!str) return '';

  // 1. Remove dangerous control characters and unicode bidi overrides
  str = sanitizeText(str);

  // 2. Strip executable and container elements including their inner content
  str = stripExecutableBlocks(str);

  // 3. Convert breaks and block-closing tags to clean newlines
  str = str.replace(/<br\s*\/?>/gi, '\n');
  str = str.replace(/<\/(?:p|div|tr|li|h[1-6]|blockquote)>/gi, '\n');

  // 4. Strip all remaining HTML tags
  str = stripAngleTagPairs(str);

  // 5. Decode common HTML entities (&quot;, &apos;, &amp;, &lt;, &gt;, &nbsp;, decimal, and hex entities)
  str = decodeHtmlEntities(str);

  // 6. Multi-pass tag removal in case decoding entities or nested structures revealed new tags (e.g. &lt;script&gt;)
  let prevPass = '';
  while (str.includes('<') && str !== prevPass) {
    prevPass = str;
    str = stripExecutableBlocks(str);
    str = stripAngleTagPairs(str);
    str = stripTrailingUnclosedTag(str);
  }

  // 7. Neutralize any stray event handler attributes (e.g., onmouseover=, onerror=, onload=) or javascript: schemes
  str = str.replace(/\b(?:on\w+)\s*=\s*(?:'[^']*'|"[^"]*"|[^\s>]+)/gi, '');
  str = str.replace(/\bjavascript:\s*/gi, '');

  // 8. Normalize whitespace while preserving linebreaks (max 2 consecutive newlines)
  str = str
    .replace(/[ \t\f\v]+/g, ' ')
    .replace(/\r\n|\r/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  return str;
}

/**
 * Standard alias for stripHtmlTags.
 */
export const sanitizeHtml = stripHtmlTags;

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
