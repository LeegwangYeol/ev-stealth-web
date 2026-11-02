/**
 * URL sanitization and security utility to prevent XSS (e.g. javascript:, data:, blob: URI execution),
 * protocol poisoning, malicious open redirects, and prototype pollution.
 *
 * Only allows safe schemes: http, https, mailto, tel, or safe relative root/anchor paths.
 * If the URL is invalid or uses an insecure scheme, falls back to '#' safe anchor.
 */
export function sanitizeSafeUrl(url?: unknown): string {
  if (!url || typeof url !== 'string') return '#';
  const trimmed = url.trim();

  // Explicitly disallow dangerous pseudoprotocols
  if (/^(?:javascript|data|vbscript):/i.test(trimmed)) {
    return '#';
  }

  // Reject URLs containing raw control characters or null bytes
  if (/[\x00-\x1f\x7f]/.test(trimmed)) {
    return '#';
  }

  const sanitized = trimmed;

  // Deep pseudoprotocol check (strips internal spaces/tabs to prevent obfuscation bypasses)
  const normalizedProtocol = sanitized.replace(/\s+/g, '').toLowerCase();
  if (/^(?:javascript|data|vbscript|blob|file|about):/.test(normalizedProtocol)) {
    return '#';
  }

  // Block protocol-relative URLs (//evil.com) and backslash redirects (/\\evil.com, \\\\evil.com)
  if (/^[/\\]{2,}/.test(sanitized) || /^[/\\][\\]/.test(sanitized)) {
    return '#';
  }

  // Anchor links
  if (/^#[a-zA-Z0-9_\-.:]*$/.test(sanitized)) {
    return sanitized;
  }

  // Safe internal relative routes (must start with / and not followed by / or \)
  if (/^\/(?![/\\])/.test(sanitized) && !/[\s<>"']/.test(sanitized)) {
    return sanitized;
  }

  // mailto:
  if (/^mailto:[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/i.test(sanitized)) {
    return sanitized;
  }

  // tel:
  if (/^tel:[+0-9\-#*().]+$/i.test(sanitized)) {
    return sanitized;
  }

  // Absolute web URLs: must be http or https with valid hostname
  if (/^https?:\/\//i.test(sanitized) && !/[\s<>"']/.test(sanitized)) {
    try {
      const parsed = new URL(sanitized);
      if (
        (parsed.protocol === 'http:' || parsed.protocol === 'https:') &&
        parsed.hostname &&
        parsed.hostname.length > 0
      ) {
        return sanitized;
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
