"use client";

import React, { useState, useEffect, memo } from 'react';

export interface ClientTimestampProps {
  isoString?: string | null;
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
  className,
  fallback = '방금 전',
  locale = 'ko-KR',
  options,
}: ClientTimestampProps) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const fallbackText = isoString
    ? isoString.includes('T')
      ? isoString.replace('T', ' ').substring(0, 19) + ' (UTC)'
      : isoString
    : fallback;

  let formattedText = fallbackText;
  if (mounted && isoString) {
    try {
      const date = new Date(isoString);
      if (!isNaN(date.getTime())) {
        formattedText = date.toLocaleString(locale, options);
      }
    } catch {
      formattedText = fallbackText;
    }
  }

  return (
    <time
      dateTime={isoString || undefined}
      className={className}
      suppressHydrationWarning
    >
      {mounted ? formattedText : fallbackText}
    </time>
  );
});

export default ClientTimestamp;
