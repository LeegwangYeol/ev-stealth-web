import { Suspense } from 'react';
import type { Metadata } from 'next';
import { getRecallDatabase } from '@/lib/getRecallData';
import RecallPortalClient from './RecallPortalClient';
import JsonLd from '@/components/JsonLd';

export const dynamic = 'force-static';

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || 'https://ev-stealth-web.vercel.app').replace(/\/+$/, '');

const recallJsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'WebApplication',
      '@id': `${SITE_URL}/recall-portal#app`,
      name: '전기차 공식 리콜 & 배터리 제조사 화재 안전 포털',
      url: `${SITE_URL}/recall-portal`,
      applicationCategory: 'UtilitiesApplication',
      operatingSystem: 'All',
      description:
        '대한민국 국토교통부(MOLIT) 및 미국 NHTSA 공식 전기차 리콜 캠페인 실시간 조회. 17자리 차대번호(VIN) 및 차종별 배터리 셀 제조사, 화재 위험도 및 아파트 지하주차장 충전 안전 가이드 제공.',
      provider: {
        '@type': 'Organization',
        name: 'Global EV Hub',
        url: SITE_URL,
      },
    },
    {
      '@type': 'Dataset',
      '@id': `${SITE_URL}/recall-portal#dataset`,
      name: '국토교통부·NHTSA 공인 전기차 리콜 및 배터리 셀 제조사 데이터베이스',
      description:
        '국내외 전 차종 배터리 셀 제조사 실명, 국토교통부 자동차리콜센터 및 미국 NHTSA 공시 전기차 결함 시정조치 캠페인 전수 데이터베이스.',
      url: `${SITE_URL}/recall-portal`,
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
      temporalCoverage: '2018/2026',
    },
    {
      '@type': 'ItemList',
      '@id': `${SITE_URL}/recall-portal#itemlist`,
      name: '공식 전기차 리콜 및 배터리 화재 안전 핵심 서비스',
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: '국토교통부·NHTSA 공인 전기차 결함 시정조치 리콜 캠페인 실시간 조회',
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: '17자리 차대번호(VIN) 기반 배터리 셀 제조사(LG·SK·CATL·파라시스·삼성) 실명 확인',
        },
        {
          '@type': 'ListItem',
          position: 3,
          name: '아파트 지하주차장 충전율 90% 제한 및 전기차 화재 예방 안전 권고안',
        },
      ],
    },
    {
      '@type': 'FAQPage',
      '@id': `${SITE_URL}/recall-portal#faq`,
      mainEntity: [
        {
          '@type': 'Question',
          name: '내 전기차 배터리 제조사는 어디서 어떻게 확인할 수 있나요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '국토교통부 전기차 배터리 정보 공개 의무화 정책에 따라 자동차등록증 비고란 또는 본 포털의 17자리 차대번호(VIN) 조회를 통해 배터리 셀 제조사(LG에너지솔루션, SK온, CATL, 파라시스, 삼성SDI)를 즉시 확인할 수 있습니다.',
          },
        },
        {
          '@type': 'Question',
          name: '아파트 지하주차장 90% 충전 제한 권고안은 모든 전기차에 적용되나요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '서울시 및 주요 지자체 권고안으로 급속충전기 충전율 80% 제한, 완속충전 90% 이하 설정이 권장되고 있습니다. 차량 인포테인먼트 충전 목표치를 90%로 설정하면 화재 위험 완화 및 배터리 수명(SoH) 보존에 도움이 됩니다.',
          },
        },
        {
          '@type': 'Question',
          name: '공식 리콜 통지를 받았을 때 무상 수리 기한이 정해져 있나요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '자동차관리법에 따른 공식 안전 리콜은 기간 제한 없이 100% 제조사 전액 부담으로 무상 수리(SW 업데이트, 부품 교체)가 보장됩니다. 다만 안전 운행을 위해 공고 즉시 공식 서비스센터에 예약하여 조치를 받는 것이 권장됩니다.',
          },
        },
      ],
    },
    {
      '@type': 'BreadcrumbList',
      '@id': `${SITE_URL}/recall-portal#breadcrumb`,
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
          name: '공식 리콜 포털',
          item: `${SITE_URL}/recall-portal`,
        },
      ],
    },
  ],
};

export const metadata: Metadata = {
  title: '전기차 공식 리콜 & 배터리 제조사 화재 안전 포털',
  description:
    '대한민국 국토교통부(MOLIT) 및 미국 NHTSA 공식 전기차 리콜 캠페인 실시간 조회. 17자리 차대번호(VIN) 및 차종별 배터리 셀 제조사(파라시스, LG에너지솔루션, SK온, CATL, 삼성SDI 등), 화재 위험도 및 아파트 지하주차장 충전 안전 가이드 제공.',
  keywords: [
    '전기차 리콜 조회',
    '전기차 배터리 제조사',
    '전기차 차대번호 조회',
    'VIN 리콜 조회',
    '전기차 화재',
    '파라시스 배터리',
    '벤츠 EQE 화재',
    'ICCU 결함',
    '아이오닉5 리콜',
    'EV6 리콜',
    '테슬라 리콜',
    '아파트 지하주차장 전기차',
  ],
  alternates: {
    canonical: '/recall-portal',
  },
  openGraph: {
    title: '전기차 공식 리콜 & 배터리 제조사 화재 안전 포털 | Global EV Hub',
    description:
      '내 차 배터리 제조사와 공식 리콜을 1초 만에 확인하세요. 국토교통부 공시 데이터 및 지하주차장 안전 가이드 탑재.',
    url: '/recall-portal',
    type: 'website',
    locale: 'ko_KR',
    siteName: 'Global EV Hub',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: '전기차 공식 리콜 & 배터리 제조사 화재 안전 포털',
        type: 'image/png',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: '전기차 공식 리콜 & 배터리 제조사 화재 안전 포털 | Global EV Hub',
    description:
      '내 차 배터리 제조사와 공식 리콜을 1초 만에 확인하세요. 국토교통부 공시 데이터 및 지하주차장 안전 가이드 탑재.',
    site: '@GlobalEVHub',
    creator: '@lolollol2379',
    images: ['/og-image.png'],
  },
};

export default function RecallPortalPage() {
  const database = getRecallDatabase();
  return (
    <>
      <JsonLd data={recallJsonLd} />
      <Suspense
        fallback={
          <div role="status" aria-live="polite" className="min-h-screen bg-slate-900 text-slate-100 flex items-center justify-center p-8">
            <div className="text-center space-y-3">
              <div className="text-3xl animate-pulse motion-reduce:animate-none" aria-hidden="true">⚡</div>
              <div className="text-sm font-semibold text-slate-300">
                전기차 리콜 & 배터리 데이터베이스 로딩 중...
              </div>
            </div>
          </div>
        }
      >
        <RecallPortalClient initialDatabase={database} />
      </Suspense>
    </>
  );
}
