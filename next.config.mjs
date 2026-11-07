/** @type {import('next').NextConfig} */
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
  "manifest-src 'self'",
  "media-src 'self' blob: data:",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  ...(isProd ? ['upgrade-insecure-requests'] : []),
].join('; ');

const nextConfig = {
  reactStrictMode: true,
  productionBrowserSourceMaps: false,
  poweredByHeader: false,
  compress: true,
  swcMinify: true,
  generateEtags: true,
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
              'camera=(), microphone=(), geolocation=(), browsing-topics=(), interest-cohort=(), payment=(), usb=(), bluetooth=(), accelerometer=(), autoplay=(), encrypted-media=(), gyroscope=(), magnetometer=(), midi=(), screen-wake-lock=(), xr-spatial-tracking=(), display-capture=(), sync-xhr=()',
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
            value: 'noindex, nofollow, noarchive',
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
        source: '/:all*\\.(svg|ico|png|jpg|jpeg|webp|avif|woff|woff2|ttf|otf)',
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

export default nextConfig;
