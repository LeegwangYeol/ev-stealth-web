import { Suspense } from 'react';
import type { Metadata } from 'next';
import { getReliabilityTrendsData } from '@/lib/getReliabilityData';
import ReliabilityDashboardClient from './ReliabilityDashboardClient';
import JsonLd from '@/components/JsonLd';

export const dynamic = 'force-static';

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || 'https://ev-stealth-web.vercel.app').replace(/\/+$/, '');

const reliabilityJsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'WebApplication',
      '@id': `${SITE_URL}/reliability-analytics#app`,
      name: '전기차 모델·연식별 결함 통계 및 내구성 분석 (DSI)',
      url: `${SITE_URL}/reliability-analytics`,
      applicationCategory: 'AnalyticsApplication',
      operatingSystem: 'All',
      description:
        '현대, 기아, 테슬라, BYD, 벤츠, BMW 등 9대 브랜드 22개 차종 89개 연식별 결함 심각도 지수(DSI), 고질병 통계, 중고차 구매 시 절대 피해야 할 연식 가이드 및 보증 외 수리비 매트릭스를 제공합니다.',
      provider: {
        '@type': 'Organization',
        name: 'Global EV Hub',
        url: SITE_URL,
      },
    },
    {
      '@type': 'Dataset',
      '@id': `${SITE_URL}/reliability-analytics#dataset`,
      name: '글로벌 전기차 모델·연식별 결함 심각도 지수(DSI) 빅데이터',
      description:
        '9대 글로벌 완성차 제조사 22개 차종 89개 연식의 실제 차주 제보 1,280건 및 리콜 데이터 기반 결함 심각도 지수(DSI) 및 연식 리스크 매트릭스 데이터셋.',
      url: `${SITE_URL}/reliability-analytics`,
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
      '@id': `${SITE_URL}/reliability-analytics#itemlist`,
      name: '글로벌 전기차 주요 고질병 및 결함 심각도(DSI) 분석 리스트',
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: '현대/기아 E-GMP ICCU (통합충전제어장치) 파손 및 주행 중 전원 상실',
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: '테슬라 옥토밸브 히트펌프 냉각수 누수 및 컨트롤 암 부싱 파손',
        },
        {
          '@type': 'ListItem',
          position: 3,
          name: '메르세데스-벤츠 EQE/EQS 파라시스 배터리 화재 위험 및 7,500만 원 교체비',
        },
        {
          '@type': 'ListItem',
          position: 4,
          name: 'BYD 돌핀 에어컨 에바코어 수산화알루미늄 백색가루 분출 및 조향기판 결함',
        },
        {
          '@type': 'ListItem',
          position: 5,
          name: '폭스바겐 ID.4 터치센서 빗물 침수 주행 중 도어 열림 및 CO2 콤프레셔 파손',
        },
        {
          '@type': 'ListItem',
          position: 6,
          name: '볼보 EX30 통합 디스플레이 꺼짐 및 폴스타 2 고전압 세라믹 히터 파괴',
        },
      ],
    },
    {
      '@type': 'FAQPage',
      '@id': `${SITE_URL}/reliability-analytics#faq`,
      mainEntity: [
        {
          '@type': 'Question',
          name: '전기차 결함 심각도 지수(DSI, Defect Severity Index)란 무엇인가요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: 'DSI는 국토교통부·NHTSA 공식 리콜 이력, 1,280건의 실차주 제보, 주행 안전 위협도(화재, 주행 중 셧다운, 조향 상실), 보증 외 자비 수리비 부담액을 가중 평균하여 산출한 내구성 위험 지수입니다.',
          },
        },
        {
          '@type': 'Question',
          name: '보증 만료 후 고전압 배터리 교체비 매트릭스는 어떻게 산정되나요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '국내외 서비스센터 표준 공임 및 부품가(모비스, 테슬라, 벤츠 서비스코리아)를 기준으로 실비 반영되며, 최저 900만 원(BYD 블레이드)부터 최고 7,560만 원(벤츠 EQS 118kWh 팩)까지 차종별 편차를 비교합니다.',
          },
        },
        {
          '@type': 'Question',
          name: '중고 전기차 구매 시 연식별 리스크 히트맵을 어떻게 확인하나요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '차종 및 연식 선택 시 붉은색(구매 회피 - 치명 결함), 노란색(주의 요망 - 보증 확인 필수), 초록색(안심 추천 - 개선품 적용) 3단계 배지와 구체적인 고질병 원인 및 점검 가이드를 확인하실 수 있습니다.',
          },
        },
      ],
    },
    {
      '@type': 'BreadcrumbList',
      '@id': `${SITE_URL}/reliability-analytics#breadcrumb`,
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
          name: '결함·신뢰성 통계',
          item: `${SITE_URL}/reliability-analytics`,
        },
      ],
    },
  ],
};

export const metadata: Metadata = {
  title: '전기차 모델·연식별 결함 통계 및 내구성 분석 (DSI)',
  description:
    '현대, 기아, 테슬라, BYD, 벤츠, BMW 등 9대 브랜드 22개 차종 89개 연식별 결함 심각도 지수(DSI), 고질병 통계, 중고차 구매 시 절대 피해야 할 연식 가이드 및 보증 외 수리비 매트릭스를 제공합니다.',
  keywords: [
    '전기차 결함 통계',
    '전기차 내구성 DSI',
    '아이오닉5 ICCU 결함',
    'EV6 결함 연식',
    '테슬라 모델3 히트펌프 옥토밸브',
    '벤츠 EQE 파라시스 배터리 화재',
    'BYD 백색가루 결함',
    '전기차 배터리 교체비용',
    '중고 전기차 피해야할 연식',
  ],
  alternates: {
    canonical: '/reliability-analytics',
  },
  openGraph: {
    title: '전기차 모델·연식별 결함 통계 및 내구성 분석 (DSI) | Global EV Hub',
    description:
      '9대 제조사 22개 모델 89개 연식의 실제 차주 제보 1,280건 심층 분석. 결함 심각도 지수(DSI), 연식별 위험 히트맵, 보증 외 수리비 매트릭스.',
    url: '/reliability-analytics',
    type: 'website',
    locale: 'ko_KR',
    siteName: 'Global EV Hub',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: '전기차 모델·연식별 결함 통계 및 내구성 분석 (DSI)',
        type: 'image/png',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: '전기차 모델·연식별 결함 통계 및 내구성 분석 (DSI) | Global EV Hub',
    description:
      '9대 제조사 22개 모델 89개 연식의 실제 차주 제보 1,280건 심층 분석. 결함 심각도 지수(DSI), 연식별 위험 히트맵, 보증 외 수리비 매트릭스.',
    site: '@GlobalEVHub',
    creator: '@lolollol2379',
    images: ['/og-image.png'],
  },
};

export default function ReliabilityAnalyticsPage() {
  const data = getReliabilityTrendsData();

  return (
    <div
      id="reliability-analytics-page"
      role="region"
      aria-label="전기차 모델·연식별 결함 통계 및 내구성 분석 대시보드"
      className="py-6 sm:py-8 space-y-6"
    >
      <JsonLd data={reliabilityJsonLd} />
      <Suspense
        fallback={
          <div
            role="status"
            aria-live="polite"
            className="flex min-h-[400px] items-center justify-center rounded-3xl border border-slate-700 bg-slate-900/60 p-12 text-center"
          >
            <div className="space-y-4">
              <div
                className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent motion-reduce:animate-none"
                aria-hidden="true"
              />
              <p className="text-sm font-medium text-slate-300">
                전기차 결함 통계 및 DSI 내구성 데이터를 불러오는 중...
              </p>
            </div>
          </div>
        }
      >
        <ReliabilityDashboardClient initialData={data} />
      </Suspense>
    </div>
  );
}

