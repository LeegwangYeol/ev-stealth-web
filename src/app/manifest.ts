import type { MetadataRoute } from 'next';

/**
 * Web App Manifest generator for Next.js App Router.
 * Configures mobile PWA installation, home-screen badges, and search engine discoverability.
 */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: 'Global EV Hub - 글로벌 전기차 결함 및 리콜 정보 포털',
    short_name: 'Global EV Hub',
    description:
      '글로벌 전기차 결함, 리콜 정보, 실시간 보조금 소진율 및 감가방어율 종합 분석 포털',
    start_url: '/',
    display: 'standalone',
    background_color: '#0f172a',
    theme_color: '#0f172a',
    icons: [
      {
        src: '/favicon.ico',
        sizes: 'any',
        type: 'image/x-icon',
      },
    ],
  };
}
