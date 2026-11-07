import type { Metadata } from 'next';
import PdiChecklistClient from './PdiChecklistClient';
import JsonLd from '@/components/JsonLd';

export const dynamic = 'force-static';

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || 'https://ev-stealth-web.vercel.app').replace(/\/+$/, '');

const pdiJsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'HowTo',
      '@id': `${SITE_URL}/pdi-checklist#howto`,
      name: '전기차 신차 인수(PDI) 체크리스트',
      description: '전기차 신차 탁송 인수 전 필수 PDI 점검 항목 및 체크리스트. 인수증 서명 전 단차, 도장, 배터리팩 찍힘 등 확인.',
      url: `${SITE_URL}/pdi-checklist`,
      step: [
        {
          '@type': 'HowToStep',
          position: 1,
          name: '외관 및 도장·단차 검사',
          text: '단차 및 도장 불량, 하부 배터리팩 찍힘을 확인합니다.',
          url: `${SITE_URL}/pdi-checklist#step-1`,
        },
        {
          '@type': 'HowToStep',
          position: 2,
          name: '실내 전장 및 소프트웨어 점검',
          text: '공조기, 디스플레이 터치, 충전 포트 작동 여부를 확인합니다.',
          url: `${SITE_URL}/pdi-checklist#step-2`,
        },
        {
          '@type': 'HowToStep',
          position: 3,
          name: '지급품 및 서류 최종 확인',
          text: '완속 충전 케이블, 이동식 충전기, V2L 젠더 등 기본 지급품을 점검합니다.',
          url: `${SITE_URL}/pdi-checklist#step-3`,
        },
      ],
    },
    {
      '@type': 'ItemList',
      '@id': `${SITE_URL}/pdi-checklist#itemlist`,
      name: '전기차 신차 인수(PDI) 핵심 점검 단계',
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: '하부 고전압 배터리팩 찍힘 및 언더커버 손상 육안 검사',
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: '외관 도장 불량(티끌, 도장 뭉침) 및 보닛·도어·트렁크 단차(3mm 이내) 측정',
        },
        {
          '@type': 'ListItem',
          position: 3,
          name: '실내 듀얼 디스플레이 터치, 클러스터 먹통, HUD 및 공조 시스템 전장 점검',
        },
        {
          '@type': 'ListItem',
          position: 4,
          name: '충전 도어 전동 개폐, 완속/급속 체결 및 비상 수동 해제 레버 확인',
        },
        {
          '@type': 'ListItem',
          position: 5,
          name: 'V2L 커넥터, 이동식 충전기 케이블 및 기본 지급품 패키지 수량 검수',
        },
      ],
    },
    {
      '@type': 'FAQPage',
      '@id': `${SITE_URL}/pdi-checklist#faq`,
      mainEntity: [
        {
          '@type': 'Question',
          name: '탁송 현장에서 결함 발견 시 인수증 서명은 어떻게 해야 하나요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '결함 부위를 다양한 각도에서 근접 촬영한 뒤 탁송 기사 입회하에 인수증 비고란에 결함 내용을 구체적으로 기재하고 사진을 남겨야 합니다. 하부 배터리 찍힘이나 도장 파손 등 중대 하자는 인수 서명을 거부하고 회차 요청이 가능합니다.',
          },
        },
        {
          '@type': 'Question',
          name: '신차 출고 시 임시 번호판 상태를 유지하는 것이 권장되는 이유는?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '정식 번호판 등록이 완료되면 소유권이 완전히 이전되어 차량 교환이나 환불(레몬법 적용)이 극도로 어려워집니다. 10일간의 임시 운행 기간 동안 충전 및 주행 테스트를 거친 후 등록하는 것이 안전합니다.',
          },
        },
        {
          '@type': 'Question',
          name: '하부 배터리팩 찍힘 검사가 전기차에서 가장 중요한 이유는 무엇인가요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '탁송 인수 이후 발견된 하부 찍힘은 차주 과실(도로 노면 충격)로 처리되어 제조사 무상보증이 거부될 위험이 높으며, 케이스 변형 시 배터리 팩 전체 교체(1,500만~7,500만 원) 판정이 날 수 있기 때문입니다.',
          },
        },
      ],
    },
    {
      '@type': 'BreadcrumbList',
      '@id': `${SITE_URL}/pdi-checklist#breadcrumb`,
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
          name: 'PDI 체크리스트',
          item: `${SITE_URL}/pdi-checklist`,
        },
      ],
    },
  ],
};

export const metadata: Metadata = {
  title: '전기차 신차 인수(PDI) 체크리스트',
  description: '전기차 신차 탁송 인수 전 필수 PDI 점검 항목 및 체크리스트. 인수증 서명 전 단차, 도장, 배터리팩 찍힘 등 확인.',
  keywords: [
    '전기차 PDI',
    '신차 검수 체크리스트',
    '전기차 단차',
    '배터리팩 찍힘',
    '전기차 인수 점검',
    '아이오닉5 검수',
    '테슬라 인수 체크리스트',
  ],
  alternates: {
    canonical: '/pdi-checklist',
  },
  openGraph: {
    title: '전기차 신차 인수(PDI) 체크리스트 | Global EV Hub',
    description: '전기차 신차 탁송 인수 전 필수 PDI 점검 항목 및 체크리스트. 인수증 서명 전 단차, 도장, 배터리팩 찍힘 등 확인.',
    url: '/pdi-checklist',
    siteName: 'Global EV Hub',
    locale: 'ko_KR',
    type: 'website',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: '전기차 신차 인수(PDI) 체크리스트',
        type: 'image/png',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: '전기차 신차 인수(PDI) 체크리스트 | Global EV Hub',
    description: '전기차 신차 탁송 인수 전 필수 PDI 점검 항목 및 체크리스트. 인수증 서명 전 단차, 도장, 배터리팩 찍힘 등 확인.',
    site: '@GlobalEVHub',
    creator: '@lolollol2379',
    images: ['/og-image.png'],
  },
};

export default function PdiChecklistPage() {
  return (
    <>
      <JsonLd data={pdiJsonLd} />
      <PdiChecklistClient />
    </>
  );
}
