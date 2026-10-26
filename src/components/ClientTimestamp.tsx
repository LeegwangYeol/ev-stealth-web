"use client";

import React, { useState, useEffect, memo } from 'react';

export interface ClientTimestampProps {
  isoString?: string | null;
  timestamp?: string | null;
  format?: string;
  className?: string;
  fallback?: string;
  locale?: string;
  options?: Intl.DateTimeFormatOptions;
}

/**
 * An isolated, memoized client component that formats an ISO timestamp string into `ko-KR` locale
 * safely after mounting (`useEffect`), returning an accessible `<time>` element with `dateTime`
 * attribute and fallback unformatted text before mounting.
 * This eliminates the need for parent components to hold a root `mounted` state.
 */
export const ClientTimestamp = memo(function ClientTimestamp({
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
  const fallbackText = effectiveIso
    ? effectiveIso.includes('T')
      ? effectiveIso.replace('T', ' ').substring(0, 19) + ' (UTC)'
      : effectiveIso
    : fallback;

  let formattedText = fallbackText;
  if (mounted && effectiveIso) {
    try {
      const date = new Date(effectiveIso);
      if (!isNaN(date.getTime())) {
        formattedText = date.toLocaleString(locale, options);
      }
    } catch {
      formattedText = fallbackText;
    }
  }

  return (
    <time
      dateTime={effectiveIso || undefined}
      className={className}
      suppressHydrationWarning
    >
      {mounted ? formattedText : fallbackText}
    </time>
  );
});

export default ClientTimestamp;
