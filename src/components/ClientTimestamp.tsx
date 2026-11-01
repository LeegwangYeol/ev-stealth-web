"use client";

import React, { useState, useEffect, useMemo, memo } from 'react';

export interface ClientTimestampProps {
  isoString?: string | null;
  timestamp?: string | null;
  format?: string;
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
 * This eliminates the need for parent components to hold a root `mounted` state.
 */
function ClientTimestampBase({
  isoString,
  timestamp,
  className,
  fallback = '방금 전',
  locale = 'ko-KR',
  options,
}: ClientTimestampProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const effectiveIso = isoString || timestamp;
  const fallbackText = useMemo(() => {
    if (!effectiveIso) return fallback;
    return effectiveIso.includes('T')
      ? effectiveIso.replace('T', ' ').substring(0, 19) + ' (UTC)'
      : effectiveIso;
  }, [effectiveIso, fallback]);

  const formattedText = useMemo(() => {
    if (!mounted || !effectiveIso) {
      return fallbackText;
    }
    try {
      const date = new Date(effectiveIso);
      if (!isNaN(date.getTime())) {
        return date.toLocaleString(locale, options);
      }
    } catch {
      return fallbackText;
    }
    return fallbackText;
  }, [mounted, effectiveIso, locale, options, fallbackText]);

  return (
    <time
      dateTime={effectiveIso || undefined}
      className={className}
      suppressHydrationWarning
    >
      {mounted ? formattedText : fallbackText}
    </time>
  );
}

export const ClientTimestamp = memo(ClientTimestampBase, areTimestampPropsEqual);

export default ClientTimestamp;
