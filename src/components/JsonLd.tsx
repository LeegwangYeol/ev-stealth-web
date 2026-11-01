import React, { memo, useMemo } from 'react';

export interface JsonLdProps {
  data: Record<string, unknown> | Array<Record<string, unknown>>;
}

/**
 * Reusable JSON-LD Structured Data Component.
 * Injects Schema.org structured data safely for search engine crawlers and rich snippets.
 */
export const JsonLd = memo(function JsonLd({ data }: JsonLdProps) {
  // Sanitize JSON-LD to prevent script breakout XSS (e.g. </script> injection)
  const safeJsonString = useMemo(() => {
    return JSON.stringify(data)
      .replace(/</g, '\\u003c')
      .replace(/>/g, '\\u003e');
  }, [data]);

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: safeJsonString,
      }}
    />
  );
});

export default JsonLd;
