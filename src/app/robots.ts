import type { MetadataRoute } from 'next';

export const dynamic = 'force-dynamic';
export const revalidate = 86400;

function getBaseUrl(): string {
  const candidates = [process.env.NEXT_PUBLIC_SITE_URL, process.env.VERCEL_URL];
  for (const candidate of candidates) {
    const raw = (candidate || '').trim().replace(/\/+$/, '');
    if (raw) {
      return raw.startsWith('http://') || raw.startsWith('https://') ? raw : `https://${raw}`;
    }
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
