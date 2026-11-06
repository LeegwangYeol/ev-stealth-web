import { Suspense } from 'react';
import type { Metadata } from 'next';
import { getSubsidyDatabase } from '@/lib/getSubsidyData';
import SubsidyTrackerClient from './SubsidyTrackerClient';
import JsonLd from '@/components/JsonLd';

export const dynamic = 'force-static';

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || 'https://ev-stealth-web.vercel.app').replace(/\/+$/, '');

const subsidyJsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'WebApplication',
      '@id': `${SITE_URL}/subsidy-tracker#app`,
      name: '전국 지자체별 전기차 실시간 보조금 소진율 추적기',
      url: `${SITE_URL}/subsidy-tracker`,
      applicationCategory: 'UtilitiesApplication',
      operatingSystem: 'All',
      description:
        '2026년 환경부 무공해차 통합누리집(ev.or.kr) 및 17개 광역시도 지자체별 전기차 실시간 보조금 소진율, 접수·출고 대수, 잔여 쿼터 긴급 소진 경보 및 실구매 체감가 시뮬레이션 계산기.',
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
      '@id': `${SITE_URL}/subsidy-tracker#dataset`,
      name: '2026 대한민국 전국 지자체별 전기차 보조금 및 실시간 소진율 데이터셋',
      description:
        '환경부 무공해차 통합누리집 연계 전국 17개 광역시도 73개 지자체의 전기승용 및 전기화물 보조금 공고대수, 접수대수, 출고대수, 실시간 소진율 및 차종별 매칭 보조금 데이터셋.',
      url: `${SITE_URL}/subsidy-tracker`,
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
      temporalCoverage: '2026',
      spatialCoverage: {
        '@type': 'Place',
        name: '대한민국 (South Korea)',
      },
    },
    {
      '@type': 'FAQPage',
      '@id': `${SITE_URL}/subsidy-tracker#faq`,
      mainEntity: [
        {
          '@type': 'Question',
          name: '2026년 전기차 보조금 5,500만 / 8,500만 원 슬라이딩 가격 상한제 기준은 어떻게 적용되나요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '환경부 무공해차 보조금 업무처리지침에 따라 전기승용차의 기본 출고가(MSRP, 옵션 제외) 기준 5,500만 원 미만은 국비 및 지방비 100% 전액 지원, 5,500만 원 이상 ~ 8,500만 원 미만은 50% 감액 지원, 8,500만 원 이상은 고가 프리미엄 차량으로 분류되어 전액 제외(0원)됩니다.',
          },
        },
        {
          '@type': 'Question',
          name: '지자체별 지방비 보조금은 어떻게 산출되며 왜 지역마다 차이가 나나요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '지자체 보조금은 국비 보조금 비율(해당 모델 국비 지원액 / 국비 최대 지원 상한액 650만 원)에 비례하여 각 지자체의 공고 조례 지원액이 매칭됩니다. 서울(150만 원), 대구(250만 원), 제주(400만 원), 울릉군(최대 1,100만 원) 등 지자체 재정 자립도 및 보급 목표 대수에 따라 지방비 책정 금액이 상이합니다.',
          },
        },
        {
          '@type': 'Question',
          name: '보조금을 받은 전기차를 2년 이내에 매각하거나 타 시·도로 이전하면 어떻게 되나요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '대기환경보전법 제58조에 따라 최초 등록일로부터 2년간 의무 운행 기간이 적용됩니다. 동일 시·도 내 매매는 잔여 기간이 자동 승계되어 환수가 발생하지 않으나, 타 시·도 매매 또는 수출·폐차 시 운행 기간별 환수율(3개월 미만 70% ~ 24개월 미만 20%)에 따라 지방비가 강제 환수됩니다.',
          },
        },
        {
          '@type': 'Question',
          name: '원하는 지자체의 보조금이 마감(소진율 100%)된 경우 어떻게 대처해야 하나요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '공고 물량이 전액 소진되었더라도 취소분 대기 접수(출고 지연/변심 취소분 선착순 배정), 지자체 추가경정예산(추경, 6~8월 상반기 결산 후 편성), 또는 법인/리스 명의를 통한 타 지자체 분산 등록의 방법이 있습니다.',
          },
        },
        {
          '@type': 'Question',
          name: '청년, 소상공인, 다자녀 가구 및 노후 경유차 특별 가산금 조건은 무엇인가요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '2026년 환경부 정책에 따라 청년 생애 최초 구매자(만 19~34세)는 국비의 +20%, 소상공인 및 개인택시는 +30%, 다자녀 가구(자녀 2인 이상)는 +10% 추가 지원되며, 노후 경유차(4·5등급) 조기폐차 후 구매 시 정액 100만 원이 추가 지원됩니다.',
          },
        },
      ],
    },
    {
      '@type': 'BreadcrumbList',
      '@id': `${SITE_URL}/subsidy-tracker#breadcrumb`,
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
          name: '실시간 보조금 소진율',
          item: `${SITE_URL}/subsidy-tracker`,
        },
      ],
    },
  ],
};

export const metadata: Metadata = {
  title: '전국 지자체별 전기차 실시간 보조금 소진율 추적기',
  description:
    '2026년 환경부 무공해차 통합누리집(ev.or.kr) 및 17개 광역시도 지자체별 전기차 실시간 보조금 소진율, 접수·출고 대수, 잔여 쿼터 긴급 소진 경보 및 실구매 체감가 시뮬레이션 계산기.',
  keywords: [
    '전기차 보조금 소진율',
    '전국 지자체 보조금',
    '2026 전기차 보조금',
    '전기차 실구매가 계산기',
    '환경부 보조금',
    '무공해차 통합누리집',
    '서울시 전기차 보조금',
    '경기도 전기차 보조금',
    '보조금 잔여대수',
    '보조금 마감 임박',
    '아이오닉5 보조금',
    'EV3 보조금',
    '모델Y 보조금',
  ],
  alternates: {
    canonical: '/subsidy-tracker',
  },
  openGraph: {
    title: '전국 지자체별 전기차 실시간 보조금 소진율 추적기 | Global EV Hub',
    description:
      '내 거주 지자체의 전기차 보조금 잔여량과 5단계 소진 경보, 차종별 5,500만/8,500만 원 상한제 실구매가를 실시간으로 계산하세요.',
    url: '/subsidy-tracker',
    type: 'website',
    locale: 'ko_KR',
    siteName: 'Global EV Hub',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: '전국 지자체별 전기차 실시간 보조금 소진율 추적기',
        type: 'image/png',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: '전국 지자체별 전기차 실시간 보조금 소진율 추적기 | Global EV Hub',
    description:
      '내 거주 지자체의 전기차 보조금 잔여량과 5단계 소진 경보, 차종별 5,500만/8,500만 원 상한제 실구매가를 실시간으로 계산하세요.',
    site: '@GlobalEVHub',
    creator: '@lolollol2379',
    images: ['/og-image.png'],
  },
};

export default function SubsidyTrackerPage() {
  const database = getSubsidyDatabase();

  return (
    <>
      <JsonLd data={subsidyJsonLd} />
      <Suspense
        fallback={
          <div role="status" aria-live="polite" className="min-h-screen bg-slate-900 text-slate-100 flex items-center justify-center p-8">
            <div className="text-center space-y-3">
              <div className="text-4xl animate-bounce motion-reduce:animate-none" aria-hidden="true">⚡</div>
              <div className="text-base font-bold text-amber-400">
                전국 지자체별 보조금 소진율 데이터 로딩 중...
              </div>
              <p className="text-xs text-slate-300">
                환경부 및 17개 시도 실시간 쿼터 집계 분석 중입니다.
              </p>
            </div>
          </div>
        }
      >
        <SubsidyTrackerClient initialData={database} />
      </Suspense>
    </>
  );
}
