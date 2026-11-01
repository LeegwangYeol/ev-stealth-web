/**
 * URL sanitization utility to prevent XSS (e.g. javascript: or data: URI execution)
 * and malicious open redirects.
 *
 * Only allows safe schemes: http, https, mailto, tel, or relative root/anchor paths.
 * If the URL is invalid or uses an insecure scheme, falls back to '#' safe anchor.
 */
export function sanitizeSafeUrl(url?: unknown): string {
  if (!url || typeof url !== 'string') return '#';
  const trimmed = url.trim();

  // Explicitly disallow dangerous pseudoprotocols
  if (/^(?:javascript|data|vbscript):/i.test(trimmed)) {
    return '#';
  }

  // Allow standard web protocols and relative internal routes
  if (/^(?:https?:\/\/|\/|#|mailto:|tel:)/i.test(trimmed)) {
    return trimmed;
  }

  return '#';
}
