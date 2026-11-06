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
 */
export function safeDecodePercent(str: string): string {
  let prev = str;
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
    .replace(/\\0|\\x00|\\u0000/gi, '')
    .replace(/[\s\x00-\x1f\x7f\u00ad\u200b-\u200d\ufeff\u200e\u200f\u202a-\u202e\u2060\u2066-\u2069]/gi, '')
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
 * Sanitizes an untrusted URL input to prevent XSS, scheme injection, and open redirects.
 * Returns '#' if the URL is unsafe, empty, or invalid.
 */
export function sanitizeSafeUrl(url?: unknown): string {
  if (!url || typeof url !== 'string') return '#';
  const trimmed = url.trim();
  if (!trimmed) return '#';

  // Explicitly disallow raw control characters or null bytes
  if (/[\x00-\x1f\x7f]/.test(trimmed)) {
    return '#';
  }

  // Reject literal null byte escape sequences in string (\0, \x00, \u0000)
  if (/\\0|\\x00|\\u0000/i.test(trimmed)) {
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
    return trimmed;
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
        return trimmed;
      }
    } catch {
      return '#';
    }
  }

  return '#';
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
