import React, { memo, useMemo } from 'react';

export interface JsonLdProps {
  data: Record<string, unknown> | Array<Record<string, unknown>>;
}

/**
 * Reusable JSON-LD Structured Data Component.
 * Injects Schema.org structured data safely for search engine crawlers and rich snippets.
 */
export const JsonLd = memo(function JsonLd({ data }: JsonLdProps) {
  // Sanitize JSON-LD to prevent script breakout XSS (e.g. </script> injection), unicode escaping, and prototype pollution
  const safeJsonString = useMemo(() => {
    try {
      return JSON.stringify(data, (key, value) => {
        if (key === '__proto__' || key === 'constructor' || key === 'prototype') {
          return undefined;
        }
        return value;
      })
        .replace(/</g, '\\u003c')
        .replace(/>/g, '\\u003e')
        .replace(/&/g, '\\u0026')
        .replace(/\u2028/g, '\\u2028')
        .replace(/\u2029/g, '\\u2029');
    } catch {
      return '{}';
    }
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
