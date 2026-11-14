import type { Metadata } from 'next';
import { getDailyReports, getFallbackReportData } from '@/lib/getDailyReports';
import AdminDashboardClient from './AdminDashboardClient';

export const dynamic = 'force-static';

export const metadata: Metadata = {
  title: '데일리 EV 결함 관리자 리포트',
  description: '내부 모니터링 전용 비공개 데일리 EV 결함 관리자 리포트',
  keywords: [
    'EV 결함 리포트',
    '전기차 일일 모니터링',
    '관리자 대시보드',
    '결함 데이터 분석',
    'Global EV Hub',
  ],
  alternates: {
    canonical: '/secret-admin-reports',
    languages: {
      'ko-KR': '/secret-admin-reports',
      'x-default': '/secret-admin-reports',
    },
  },
  openGraph: {
    title: '데일리 EV 결함 관리자 리포트 | Global EV Hub',
    description: '내부 모니터링 전용 비공개 데일리 EV 결함 관리자 리포트',
    url: '/secret-admin-reports',
    siteName: 'Global EV Hub',
    locale: 'ko_KR',
    type: 'website',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: '데일리 EV 결함 관리자 리포트',
        type: 'image/png',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: '데일리 EV 결함 관리자 리포트 | Global EV Hub',
    description: '내부 모니터링 전용 비공개 데일리 EV 결함 관리자 리포트',
    site: '@GlobalEVHub',
    creator: '@lolollol2379',
    images: ['/og-image.png'],
  },
  robots: {
    index: false,
    follow: false,
    nocache: true,
    googleBot: {
      index: false,
      follow: false,
    },
  },
};

export default function SecretAdminReportsPage() {
  let data;
  try {
    data = getDailyReports();
  } catch {
    data = getFallbackReportData();
  }
  const safeData = data || getFallbackReportData();

  return (
    <div className="py-2">
      <AdminDashboardClient initialData={safeData} />
    </div>
  );
}
