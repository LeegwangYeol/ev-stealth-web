"use client";

import React, { useState, useEffect, useMemo, memo } from 'react';

export interface ClientTimestampProps {
  isoString?: string | null;
  timestamp?: string | null;
  format?: 'date' | 'time' | 'datetime' | string;
  className?: string;
  fallback?: string;
  locale?: string;
  options?: Intl.DateTimeFormatOptions;
}

/**
 * Idiomatic React 18 hydration-safe hook for mounted state.
 * Returns `false` on server and during initial hydration pass to match SSR markup,
 * then cleanly sets to `true` on client via useEffect without SSR/CSR hydration mismatches.
 */
export function useIsMounted(): boolean {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  return mounted;
}

function areTimestampPropsEqual(
  prevProps: ClientTimestampProps,
  nextProps: ClientTimestampProps
): boolean {
  if (
    prevProps.isoString !== nextProps.isoString ||
    prevProps.timestamp !== nextProps.timestamp ||
    prevProps.className !== nextProps.className ||
    prevProps.fallback !== nextProps.fallback ||
    prevProps.locale !== nextProps.locale ||
    prevProps.format !== nextProps.format
  ) {
    return false;
  }
  if (prevProps.options === nextProps.options) {
    return true;
  }
  if (
    !prevProps.options ||
    !nextProps.options ||
    typeof prevProps.options !== 'object' ||
    typeof nextProps.options !== 'object'
  ) {
    return prevProps.options === nextProps.options;
  }
  const prevKeys = Object.keys(prevProps.options) as (keyof Intl.DateTimeFormatOptions)[];
  const nextKeys = Object.keys(nextProps.options) as (keyof Intl.DateTimeFormatOptions)[];
  if (prevKeys.length !== nextKeys.length) {
    return false;
  }
  return prevKeys.every((key) => prevProps.options![key] === nextProps.options![key]);
}

/**
 * An isolated, memoized client component that formats an ISO timestamp string into `ko-KR` locale
 * safely after mounting via `useEffect`, returning an accessible `<time>` element with `dateTime`
 * attribute, `suppressHydrationWarning`, and fallback unformatted text before mounting.
 * This completely prevents server-client hydration mismatches and eliminates unmounted setState leaks.
 */
function ClientTimestampBase({
  isoString,
  timestamp,
  format,
  className,
  fallback = '방금 전',
  locale = 'ko-KR',
  options,
}: ClientTimestampProps) {
  const mounted = useIsMounted();

  const rawVal =
    typeof isoString === 'string' && isoString.trim().length > 0
      ? isoString
      : typeof timestamp === 'string'
      ? timestamp
      : '';
  const effectiveIso = rawVal.trim();
  const safeFallback = typeof fallback === 'string' ? fallback : '방금 전';
  const safeLocale = typeof locale === 'string' && locale.trim().length > 0 ? locale.trim() : 'ko-KR';

  const fallbackText = useMemo(() => {
    if (!effectiveIso) return safeFallback;
    return effectiveIso.includes('T')
      ? effectiveIso.replace('T', ' ').substring(0, 19) + (effectiveIso.endsWith('Z') ? ' (UTC)' : '')
      : effectiveIso;
  }, [effectiveIso, safeFallback]);

  const { formattedText, validIso } = useMemo(() => {
    if (!effectiveIso) {
      return { formattedText: safeFallback, validIso: undefined };
    }
    try {
      const date = new Date(effectiveIso);
      if (!isNaN(date.getTime())) {
        const iso = date.toISOString();
        if (!mounted) {
          return { formattedText: fallbackText, validIso: iso };
        }
        try {
          if (format === 'date') {
            return { formattedText: date.toLocaleDateString(safeLocale, options), validIso: iso };
          }
          if (format === 'time') {
            return { formattedText: date.toLocaleTimeString(safeLocale, options), validIso: iso };
          }
          return { formattedText: date.toLocaleString(safeLocale, options), validIso: iso };
        } catch {
          return { formattedText: fallbackText, validIso: iso };
        }
      }
    } catch {
      return { formattedText: fallbackText, validIso: undefined };
    }
    return { formattedText: fallbackText, validIso: undefined };
  }, [mounted, effectiveIso, safeLocale, options, format, safeFallback, fallbackText]);

  const displayText = mounted ? formattedText : fallbackText;

  return (
    <time
      dateTime={validIso || undefined}
      title={displayText}
      className={className}
      suppressHydrationWarning
    >
      {displayText}
    </time>
  );
}

export const ClientTimestamp = memo(ClientTimestampBase, areTimestampPropsEqual);

export default ClientTimestamp;

