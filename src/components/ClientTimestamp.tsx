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
  if (!prevProps.options || !nextProps.options) {
    return false;
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
 * safely after mounting (`useEffect`), returning an accessible `<time>` element with `dateTime`
 * attribute and fallback unformatted text before mounting.
 * This eliminates the need for parent components to hold a root `mounted` state and completely
 * prevents server-client hydration mismatches.
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
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    let isCurrent = true;
    if (isCurrent) {
      setMounted(true);
    }
    return () => {
      isCurrent = false;
    };
  }, []);

  const effectiveIso = (isoString || timestamp || '').trim();

  const fallbackText = useMemo(() => {
    if (!effectiveIso) return fallback;
    return effectiveIso.includes('T')
      ? effectiveIso.replace('T', ' ').substring(0, 19) + ' (UTC)'
      : effectiveIso;
  }, [effectiveIso, fallback]);

  const { formattedText, validIso } = useMemo(() => {
    if (!effectiveIso) {
      return { formattedText: fallback, validIso: undefined };
    }
    try {
      const date = new Date(effectiveIso);
      if (!isNaN(date.getTime())) {
        const iso = date.toISOString();
        if (!mounted) {
          return { formattedText: fallbackText, validIso: iso };
        }
        if (format === 'date') {
          return { formattedText: date.toLocaleDateString(locale, options), validIso: iso };
        }
        if (format === 'time') {
          return { formattedText: date.toLocaleTimeString(locale, options), validIso: iso };
        }
        return { formattedText: date.toLocaleString(locale, options), validIso: iso };
      }
    } catch {
      return { formattedText: fallbackText, validIso: undefined };
    }
    return { formattedText: fallbackText, validIso: undefined };
  }, [mounted, effectiveIso, locale, options, format, fallback, fallbackText]);

  const displayText = mounted ? formattedText : fallbackText;

  return (
    <time
      dateTime={validIso || (effectiveIso || undefined)}
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

