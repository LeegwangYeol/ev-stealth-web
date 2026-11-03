import React, { memo, useMemo } from 'react';
import { serializeJsonLd } from '@/lib/sanitizeUrl';

export interface JsonLdProps {
  data: Record<string, unknown> | Array<Record<string, unknown>>;
  id?: string;
}

/**
 * Reusable JSON-LD Structured Data Component.
 * Injects Schema.org structured data safely for search engine crawlers and rich snippets.
 */
export const JsonLd = memo(function JsonLd({ data, id }: JsonLdProps) {
  // Sanitize JSON-LD to prevent script breakout XSS (e.g. </script> injection), unicode escaping, and prototype pollution
  const safeJsonString = useMemo(() => serializeJsonLd(data), [data]);

  return (
    <script
      id={id}
      type="application/ld+json"
      dangerouslySetInnerHTML={{
        __html: safeJsonString,
      }}
    />
  );
});

export { serializeJsonLd };
export default JsonLd;
