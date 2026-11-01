import type { Metadata } from 'next';
import PdiChecklistClient from './PdiChecklistClient';
import JsonLd from '@/components/JsonLd';

export const dynamic = 'force-static';

const pdiJsonLd = {
  "@context": "https://schema.org",
  "@type": "HowTo",
  "name": "전기차 신차 인수(PDI) 체크리스트",
  "description": "전기차 신차 탁송 인수 전 필수 PDI 점검 항목 및 체크리스트. 인수증 서명 전 단차, 도장, 배터리팩 찍힘 등 확인.",
  "url": "https://ev-stealth-web.vercel.app/pdi-checklist",
  "step": [
    {
      "@type": "HowToStep",
      "name": "외관 및 도장·단차 검사",
      "text": "단차 및 도장 불량, 하부 배터리팩 찍힘을 확인합니다.",
    },
    {
      "@type": "HowToStep",
      "name": "실내 전장 및 소프트웨어 점검",
      "text": "공조기, 디스플레이 터치, 충전 포트 작동 여부를 확인합니다.",
    },
    {
      "@type": "HowToStep",
      "name": "지급품 및 서류 최종 확인",
      "text": "완속 충전 케이블, 이동식 충전기, V2L 젠더 등 기본 지급품을 점검합니다.",
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
  },
  twitter: {
    card: 'summary_large_image',
    title: '전기차 신차 인수(PDI) 체크리스트 | Global EV Hub',
    description: '전기차 신차 탁송 인수 전 필수 PDI 점검 항목 및 체크리스트. 인수증 서명 전 단차, 도장, 배터리팩 찍힘 등 확인.',
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
