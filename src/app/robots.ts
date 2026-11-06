import type { MetadataRoute } from 'next';

const BASE_URL = (process.env.NEXT_PUBLIC_SITE_URL || 'https://ev-stealth-web.vercel.app').replace(/\/+$/, '');

/**
 * Next.js App Router robots.txt generator.
 * Enforces search engine indexing permissions, blocking private admin routes and specifying the canonical sitemap.
 */
export default function robots(): MetadataRoute.Robots {
  let hostDomain = 'ev-stealth-web.vercel.app';
  try {
    hostDomain = new URL(BASE_URL).host;
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
    sitemap: `${BASE_URL}/sitemap.xml`,
    host: hostDomain,
  };
}
