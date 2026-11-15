import type { MetadataRoute } from 'next';

export const dynamic = 'force-dynamic';
export const revalidate = 86400;

function getBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_SITE_URL) {
    const raw = process.env.NEXT_PUBLIC_SITE_URL.trim().replace(/\/+$/, '');
    return raw.startsWith('http') ? raw : `https://${raw}`;
  }
  if (process.env.VERCEL_URL) {
    const raw = process.env.VERCEL_URL.trim().replace(/\/+$/, '');
    return raw.startsWith('http') ? raw : `https://${raw}`;
  }
  return 'https://ev-stealth-web.vercel.app';
}

/**
 * Next.js App Router robots.txt generator.
 * Enforces search engine indexing permissions, blocking private admin routes and specifying the canonical sitemap.
 */
export default function robots(): MetadataRoute.Robots {
  const baseUrl = getBaseUrl();
  let hostDomain = 'ev-stealth-web.vercel.app';
  try {
    hostDomain = new URL(baseUrl).host;
  } catch {
    // fallback
  }

  return {
    rules: [
      {
        userAgent: '*',
        allow: '/',
        disallow: [
          '/secret-admin-reports',
          '/secret-admin-reports/',
          '/api/',
        ],
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
    host: hostDomain,
  };
}
