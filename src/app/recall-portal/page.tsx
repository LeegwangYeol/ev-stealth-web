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
      name: '전기차 공식 리콜 & 배터리 제조사 화재 안전 포털 (통합 리콜 현황)',
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
      license: 'https://creativecommons.org/licenses/by/4.0/',
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
      spatialCoverage: {
        '@type': 'Place',
        name: '대한민국 및 북미 (South Korea & North America)',
      },
      distribution: [
        {
          '@type': 'DataDownload',
          encodingFormat: 'application/json',
          contentUrl: `${SITE_URL}/data/ev_recall_database.json`,
        },
      ],
      variableMeasured: [
        '전기차 결함 시정조치(리콜) 캠페인',
        '배터리 셀 제조사(LG·SK·CATL·파라시스·삼성)',
        '화재 및 동력상실 위험도',
        '17자리 차대번호(VIN) 프리픽스 매칭',
        'OTA 무상 수리 이행률',
      ],
      keywords: [
        '전기차 리콜',
        '국토교통부 리콜',
        'NHTSA 리콜',
        '배터리 제조사',
        'ICCU 결함',
        '파라시스 화재',
        '차대번호 조회',
      ],
    },
    {
      '@type': 'ItemList',
      '@id': `${SITE_URL}/recall-portal#itemlist`,
      name: '대한민국 국토교통부·미국 NHTSA 공인 주요 전기차 리콜 캠페인',
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: '현대 아이오닉 5/6 ICCU 소프트웨어 오류 및 동력 상실 리콜 (MOLIT-2024-0318 / NHTSA-24V-868)',
          url: `${SITE_URL}/recall-portal#RC-2024-HYUNDAI-ICCU`,
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: '기아 EV6/EV9 ICCU 내부 전력소자 파손 및 주행 중 멈춤 리콜 (MOLIT-2024-0319 / NHTSA-24V-869)',
          url: `${SITE_URL}/recall-portal#RC-2024-KIA-ICCU`,
        },
        {
          '@type': 'ListItem',
          position: 3,
          name: '메르세데스-벤츠 EQE/EQS 파라시스(Farasis) 배터리 셀 열폭주 화재 리콜 (MOLIT-2024-0814)',
          url: `${SITE_URL}/recall-portal#RC-2024-BENZ-EQE-FARASIS`,
        },
        {
          '@type': 'ListItem',
          position: 4,
          name: '현대 코나 일렉트릭 LG 배터리 음극 탭 접힘 단락 화재 전량 교체 리콜 (MOLIT-2021-0224)',
          url: `${SITE_URL}/recall-portal#RC-2021-HYUNDAI-KONA-FIRE`,
        },
        {
          '@type': 'ListItem',
          position: 5,
          name: 'GM 쉐보레 볼트 EV/EUV LG 파우치셀 화재 신품 배터리 교체 리콜 (NHTSA-21V-560 / MOLIT-2021-0820)',
          url: `${SITE_URL}/recall-portal#RC-2021-GM-BOLT-FIRE`,
        },
        {
          '@type': 'ListItem',
          position: 6,
          name: '테슬라 모델 Y/3/S/X 오토스티어 운전자 주의 모니터링 경고 개선 OTA 리콜 (NHTSA-23V-838 / MOLIT-2024-0105)',
          url: `${SITE_URL}/recall-portal#RC-2024-TESLA-AUTOPILOT`,
        },
        {
          '@type': 'ListItem',
          position: 7,
          name: 'BMW i4/iX 보쉬 통합제동시스템(IBPS) 제동 보조 배력 상실 리콜 (MOLIT-2024-0220 / NHTSA-24V-104)',
          url: `${SITE_URL}/recall-portal#RC-2024-BMW-I4-BRAKE`,
        },
        {
          '@type': 'ListItem',
          position: 8,
          name: 'BYD 아토 3/돌핀 조향 칼럼 배선 하네스 마찰 EPS 조향 보조 리콜 (APAC-2024-BYD03 / NHTSA-24V-BYD01)',
          url: `${SITE_URL}/recall-portal#RC-2024-BYD-ATTO3-STEERING`,
        },
        {
          '@type': 'ListItem',
          position: 9,
          name: '폴스타 2 고전압 인버터 및 BMS 통신 오류 동력 차단 리콜 (MOLIT-2022-1105)',
          url: `${SITE_URL}/recall-portal#RC-2022-POLESTAR2-INVERTER`,
        },
        {
          '@type': 'ListItem',
          position: 10,
          name: '기아 EV9 가상 엔진 사운드(VESS) 소프트웨어 설정 오류 리콜 (MOLIT-2023-0914)',
          url: `${SITE_URL}/recall-portal#RC-2023-KIA-EV9-VESS`,
        },
        {
          '@type': 'ListItem',
          position: 11,
          name: '테슬라 모델 3/Y 후방 카메라 미표시 및 도어 래치 잠금 규정 리콜 (MOLIT-2024-0422 / NHTSA-24V-035)',
          url: `${SITE_URL}/recall-portal#RC-2024-TESLA-CAM-LOCK`,
        },
        {
          '@type': 'ListItem',
          position: 12,
          name: '포르쉐 타이칸 LG 고전압 배터리 팩 실런트 침수 셀 단락 화재 리콜 (MOLIT-2024-0518 / NHTSA-24V-391)',
          url: `${SITE_URL}/recall-portal#RC-2024-PORSCHE-TAYCAN-SEAL`,
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
  title: '전기차 공식 리콜 & 통합 리콜 현황 (배터리 화재 안전 포털)',
  description:
    '대한민국 국토교통부(MOLIT) 및 미국 NHTSA 공식 전기차 리콜 캠페인 실시간 조회. 17자리 차대번호(VIN) 및 차종별 배터리 셀 제조사(파라시스, LG에너지솔루션, SK온, CATL, 삼성SDI 등), 화재 위험도 및 아파트 지하주차장 충전 안전 가이드 제공.',
  keywords: [
    '통합 리콜 현황',
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
    languages: {
      'ko-KR': '/recall-portal',
      'x-default': '/recall-portal',
    },
  },
  openGraph: {
    title: '전기차 공식 리콜 & 통합 리콜 현황 (배터리 화재 안전 포털) | Global EV Hub',
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
        alt: '전기차 공식 리콜 & 통합 리콜 현황 (배터리 화재 안전 포털)',
        type: 'image/png',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: '전기차 공식 리콜 & 통합 리콜 현황 (배터리 화재 안전 포털) | Global EV Hub',
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
