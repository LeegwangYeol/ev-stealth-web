/** @type {import('next').NextConfig} */
import withBundleAnalyzer from '@next/bundle-analyzer';

const isProd = process.env.NODE_ENV === 'production';

// Dynamic Content Security Policy supporting local development and hardened production
const cspDirectives = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isProd ? '' : " 'unsafe-eval'"}`,
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data: https://fonts.gstatic.com https://cdn.jsdelivr.net",
  `connect-src 'self'${isProd ? '' : ' ws: wss:'}`,
  "worker-src 'self' blob:",
  "child-src 'self' blob:",
  "frame-src 'none'",
  "manifest-src 'self'",
  "media-src 'self' blob: data:",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  ...(isProd ? ['upgrade-insecure-requests'] : []),
].join('; ');

const nextConfig = {
  distDir: process.env.NEXT_DIST_DIR || '.next',
  reactStrictMode: true,
  productionBrowserSourceMaps: false,
  poweredByHeader: false,
  compress: true,
  generateEtags: true,
  httpAgentOptions: {
    keepAlive: true,
  },
  images: {
    formats: ['image/avif', 'image/webp'],
    minimumCacheTTL: 86400,
  },
  compiler: {
    removeConsole: isProd
      ? {
          exclude: ['error', 'warn'],
        }
      : false,
  },
  typescript: {
    // Explicitly enforce full typechecking during production builds
    // Never allow type errors to silently deploy to production
    ignoreBuildErrors: false,
  },
  eslint: {
    // Explicitly enforce ESLint verification on all source files during builds
    ignoreDuringBuilds: false,
    dirs: ['src'],
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            value:
              'camera=(), microphone=(), geolocation=(), browsing-topics=(), interest-cohort=(), payment=(), usb=(), bluetooth=(), accelerometer=(), autoplay=(), encrypted-media=(), gyroscope=(), magnetometer=(), midi=(), screen-wake-lock=(), xr-spatial-tracking=(), display-capture=(), sync-xhr=(), clipboard-read=(), clipboard-write=(), web-share=(), serial=(), window-management=(), identity-credentials-get=(), otp-credentials=(), publickey-credentials-get=(), idle-detection=(), fullscreen=(self)',
          },
          {
            key: 'X-XSS-Protection',
            value: '1; mode=block',
          },
          {
            key: 'Strict-Transport-Security',
            value: 'max-age=63072000; includeSubDomains; preload',
          },
          {
            key: 'X-DNS-Prefetch-Control',
            value: 'on',
          },
          {
            key: 'Cross-Origin-Opener-Policy',
            value: 'same-origin',
          },
          {
            key: 'Cross-Origin-Resource-Policy',
            value: 'same-origin',
          },
          {
            key: 'X-Permitted-Cross-Domain-Policies',
            value: 'none',
          },
          {
            key: 'Content-Security-Policy',
            value: cspDirectives,
          },
        ],
      },
      {
        source: '/secret-admin-reports/:path*',
        headers: [
          {
            key: 'X-Robots-Tag',
            value: 'noindex, nofollow, noarchive, nosnippet, noimageindex',
          },
          {
            key: 'Cache-Control',
            value: 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0',
          },
          {
            key: 'Pragma',
            value: 'no-cache',
          },
          {
            key: 'Expires',
            value: '0',
          },
        ],
      },
      {
        source: '/data/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, s-maxage=3600, max-age=3600, stale-while-revalidate=86400',
          },
        ],
      },
      {
        source: '/:all*\\.(woff|woff2|ttf|otf)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
          {
            key: 'Cross-Origin-Resource-Policy',
            value: 'cross-origin',
          },
        ],
      },
      {
        source: '/:all*\\.(svg|ico|png|jpg|jpeg|webp|avif)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=86400, stale-while-revalidate=604800',
          },
          {
            key: 'Cross-Origin-Resource-Policy',
            value: 'cross-origin',
          },
        ],
      },
      {
        source: '/_next/static/:path*',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
          {
            key: 'Cross-Origin-Resource-Policy',
            value: 'cross-origin',
          },
        ],
      },
    ];
  },
};

const withBundleReport = withBundleAnalyzer({
  enabled: process.env.ANALYZE === 'true',
  openAnalyzer: process.env.OPEN_ANALYZER === 'true',
});

export default process.env.ANALYZE === 'true' ? withBundleReport(nextConfig) : nextConfig;
