import type { Metadata } from 'next';
import { getDepreciationDatabase } from '@/lib/getDepreciationData';
import DepreciationCalculatorClient from './DepreciationCalculatorClient';
import JsonLd from '@/components/JsonLd';

export const dynamic = 'force-static';

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || 'https://ev-stealth-web.vercel.app').replace(/\/+$/, '');

const depreciationJsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'WebApplication',
      '@id': `${SITE_URL}/depreciation-calculator#app`,
      name: '전기차 감가방어율 & 배터리 수명 계산기',
      url: `${SITE_URL}/depreciation-calculator`,
      applicationCategory: 'FinanceApplication',
      operatingSystem: 'All',
      description:
        '2026년 국내 실거래(엔카·케이카·국토교통부) 기반 전기차 잔존가치, 배터리 잔여수명(SoH), 2년 의무운행 보조금 환수액(대기환경보전법 제58조), 5개년 총소유비용(TCO) 실시간 정밀 시뮬레이터.',
      offers: {
        '@type': 'Offer',
        price: '0',
        priceCurrency: 'KRW',
      },
      provider: {
        '@type': 'Organization',
        name: 'Global EV Hub',
        url: SITE_URL,
      },
    },
    {
      '@type': 'Dataset',
      '@id': `${SITE_URL}/depreciation-calculator#dataset`,
      name: '2026 대한민국 전기차 모델별 잔존가치 및 감가율 빅데이터',
      description:
        '국내 주요 15개 전기차 모델의 1~5년 차 잔존가치, 연간 감가율, 배터리 충·방전 사이클별 SoH 열화도 및 TCO 비교 분석 데이터셋.',
      url: `${SITE_URL}/depreciation-calculator`,
      isAccessibleForFree: true,
      creator: {
        '@type': 'Organization',
        name: 'Global EV Hub Research Team',
        url: SITE_URL,
      },
      publisher: {
        '@type': 'Organization',
        name: 'Global EV Hub',
        url: SITE_URL,
      },
      temporalCoverage: '2021/2026',
    },
    {
      '@type': 'ItemList',
      '@id': `${SITE_URL}/depreciation-calculator#itemlist`,
      name: '전기차 감가율 및 배터리 잔존가치 시뮬레이션 주요 차종',
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: '현대 아이오닉 5 (E-GMP 800V 초급속 충전 및 5개년 감가방어율)',
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: '기아 EV6 (고성능 전기 크로스오버 및 배터리 잔여수명 SoH)',
        },
        {
          '@type': 'ListItem',
          position: 3,
          name: '테슬라 모델 3 / 모델 Y (글로벌 베스트셀러 감가 방어율 및 LFP 열화도)',
        },
        {
          '@type': 'ListItem',
          position: 4,
          name: '기아 EV9 (대형 3열 패밀리 전기 SUV 감가 및 TCO 총소유비용)',
        },
        {
          '@type': 'ListItem',
          position: 5,
          name: '현대 포터2 EV / 기아 봉고3 EV (영업용 화물 충방전 사이클 수명)',
        },
      ],
    },
    {
      '@type': 'FAQPage',
      '@id': `${SITE_URL}/depreciation-calculator#faq`,
      mainEntity: [
        {
          '@type': 'Question',
          name: '전기차 감가율은 내연기관차와 비교했을 때 왜 초기 3년에 더 큰가요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '전기차는 신차 구매 시 정부·지자체 보조금(600만~1,800만 원)이 차감되어 실제 구매 체감가가 낮아지며, 중고차 시장에서는 신차가격이 아닌 실구매가 기준으로 감가가 시작되고 배터리 기술 발전 속도 및 보증 만료 우려가 반영되기 때문입니다.',
          },
        },
        {
          '@type': 'Question',
          name: '배터리 건강상태(SoH)는 중고 전기차 가격 및 잔존가치에 어떤 영향을 주나요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '배터리 팩 교체비용이 1,500만~7,500만 원에 달하므로 SoH 85% 이상 유지 차량은 감가 방어율이 매우 우수하나, SoH 70% 이하 또는 보증 기준(10년/16만km 70%) 미달 우려 차량은 급격한 감가가 발생합니다.',
          },
        },
        {
          '@type': 'Question',
          name: '전기차 2년 의무운행 기간 내에 차량을 판매하면 보조금을 얼마나 반환해야 하나요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '대기환경보전법 제58조에 따라 타 시·도로 이전하거나 폐차/수출 시 3개월 미만 70%, 6개월 미만 60%, 12개월 미만 50%, 18개월 미만 30%, 24개월 미만 20%의 지원금을 관할 지자체에 반환해야 합니다. 단, 관내 동일 시·도 매매는 승계 처리됩니다.',
          },
        },
      ],
    },
    {
      '@type': 'BreadcrumbList',
      '@id': `${SITE_URL}/depreciation-calculator#breadcrumb`,
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: '홈',
          item: SITE_URL,
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: '감가·배터리 계산기',
          item: `${SITE_URL}/depreciation-calculator`,
        },
      ],
    },
  ],
};

export const metadata: Metadata = {
  title: '전기차 감가방어율 & 배터리 수명 계산기',
  description:
    '2026년 국내 실거래(엔카·케이카·국토교통부) 기반 전기차 잔존가치, 배터리 잔여수명(SoH), 2년 의무운행 보조금 환수액(대기환경보전법 제58조), 5개년 총소유비용(TCO) 실시간 정밀 시뮬레이터.',
  keywords: [
    '전기차 감가율 계산기',
    '전기차 잔존가치 계산기',
    '배터리 수명 계산기',
    '전기차 배터리 SoH',
    '전기차 보조금 환수 계산기',
    '대기환경보전법 제58조',
    '2년 의무운행기간',
    '전기차 TCO 계산기',
    '테슬라 감가율',
    '아이오닉5 감가율',
    'EV6 잔존가치',
    'BYD 잔존가치',
    '전기차 배터리 교체비용',
    '전기차 유지비 비교',
  ],
  alternates: {
    canonical: '/depreciation-calculator',
  },
  openGraph: {
    title: '전기차 감가방어율 & 배터리 수명 계산기 (2026 국내 실거래 기반) | Global EV Hub',
    description:
      '내 차 5년 뒤 중고 시세와 배터리 수명(SoH)은? 법정 보조금 환수액 및 내연기관 대비 5개년 유지비 절감액을 1초 만에 시뮬레이션하세요.',
    url: '/depreciation-calculator',
    type: 'website',
    locale: 'ko_KR',
    siteName: 'Global EV Hub',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: '전기차 감가방어율 & 배터리 수명 계산기',
        type: 'image/png',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: '전기차 감가방어율 & 배터리 수명 계산기 (2026) | Global EV Hub',
    description:
      '2026년 국내 실거래 기반 잔존가치, 배터리 잔여수명(SoH), 2년 의무운행 보조금 환수율, 5개년 TCO 정밀 계산기.',
    site: '@GlobalEVHub',
    creator: '@lolollol2379',
    images: ['/og-image.png'],
  },
};

export default function DepreciationCalculatorPage() {
  const database = getDepreciationDatabase();

  return (
    <div className="py-4 sm:py-6 space-y-6">
      <JsonLd data={depreciationJsonLd} />
      <DepreciationCalculatorClient initialDatabase={database} />
    </div>
  );
}
