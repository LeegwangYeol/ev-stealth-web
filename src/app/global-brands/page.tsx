import type { Metadata } from 'next';
import Link from 'next/link';
import JsonLd from '@/components/JsonLd';
import BrandComparisonNav, { OtherBrandsCrossNav } from '@/components/BrandComparisonNav';
import ModelSpecWarrantyCard from '@/components/ModelSpecWarrantyCard';

export const dynamic = 'force-static';
export const revalidate = false;

const rawSiteUrl =
  (process.env.NEXT_PUBLIC_SITE_URL || '').trim().replace(/\/+$/, '') ||
  'https://ev-stealth-web.vercel.app';
const normalizedSiteUrl =
  /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(rawSiteUrl) || rawSiteUrl.startsWith('//')
    ? rawSiteUrl
    : `https://${rawSiteUrl}`;

function resolveSiteUrl(url: string): string {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return parsed.origin;
    }
  } catch {
    // fallback below
  }
  return 'https://ev-stealth-web.vercel.app';
}

const SITE_URL = resolveSiteUrl(normalizedSiteUrl);

const globalBrandsJsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Article',
      '@id': `${SITE_URL}/global-brands#article`,
      headline: '글로벌 EV 브랜드 연식별 결함 및 구매 가이드',
      description: '폭스바겐 ID.4, 쉐보레 볼트 EV, 폴스타 2, 벤츠 EQE/EQS 등 유럽/북미 전기차 연식별 결함 및 중고차 구매 가이드',
      image: [`${SITE_URL}/og-image.png`],
      url: `${SITE_URL}/global-brands`,
      inLanguage: 'ko-KR',
      datePublished: '2026-01-01T00:00:00+09:00',
      dateModified: '2026-11-01T00:00:00+09:00',
      author: {
        '@type': 'Organization',
        name: 'Global EV Hub',
        url: SITE_URL,
      },
      publisher: {
        '@type': 'Organization',
        name: 'Global EV Hub',
        logo: {
          '@type': 'ImageObject',
          url: `${SITE_URL}/og-image.png`,
          width: 1200,
          height: 630,
        },
      },
      mainEntityOfPage: {
        '@type': 'WebPage',
        '@id': `${SITE_URL}/global-brands`,
      },
    },
    {
      '@type': 'Vehicle',
      '@id': `${SITE_URL}/global-brands#vehicle-bolt-ev`,
      name: '쉐보레 볼트 EV / EUV (Chevrolet Bolt EV / EUV)',
      image: `${SITE_URL}/og-image.png`,
      url: `${SITE_URL}/global-brands#heading-bolt-ev`,
      brand: {
        '@type': 'Brand',
        name: 'Chevrolet',
      },
      manufacturer: {
        '@type': 'Organization',
        name: 'General Motors',
      },
      model: 'Bolt EV',
      vehicleModelDate: '2017-2023',
      vehicleTransmission: '1단 감속기 (전기 모터)',
      fuelType: 'https://schema.org/Electric',
      description: '도심형 소형 CUV EV. LG 파우치형 삼원계 66kWh 배터리 탑재, 국토교통부 신품 교체 리콜 대상.',
      additionalProperty: [
        {
          '@type': 'PropertyValue',
          name: 'Battery Chemistry',
          value: 'LG에너지솔루션 NCM 66.0 kWh (리콜 신품 교체 기준)',
        },
        {
          '@type': 'PropertyValue',
          name: 'Powertrain Warranty',
          value: '배터리 리콜 교체 시점부터 8년 / 160,000 km 신규 보증 리셋',
        },
      ],
    },
    {
      '@type': 'Vehicle',
      '@id': `${SITE_URL}/global-brands#vehicle-id4`,
      name: '폭스바겐 ID.4 (Volkswagen ID.4)',
      image: `${SITE_URL}/og-image.png`,
      url: `${SITE_URL}/global-brands#heading-id4`,
      brand: {
        '@type': 'Brand',
        name: 'Volkswagen',
      },
      manufacturer: {
        '@type': 'Organization',
        name: 'Volkswagen AG',
      },
      model: 'ID.4',
      vehicleModelDate: '2021-2026',
      vehicleTransmission: '1단 감속기 (APP550 구동 모터)',
      fuelType: 'https://schema.org/Electric',
      description: 'MEB 전용 플랫폼 기반 준중형 SUV EV. 82.0kWh 삼원계 배터리 및 개선형 도어 래치 적용.',
      additionalProperty: [
        {
          '@type': 'PropertyValue',
          name: 'Battery Chemistry',
          value: 'LG에너지솔루션 / SK온 NCM 82.0 kWh (가용 77.0 kWh)',
        },
        {
          '@type': 'PropertyValue',
          name: 'Powertrain Warranty',
          value: '8년 / 160,000 km (보증 잔여용량 70%)',
        },
      ],
    },
    {
      '@type': 'Vehicle',
      '@id': `${SITE_URL}/global-brands#vehicle-benz-eqe`,
      name: '메르세데스-벤츠 EQE 350+ (Mercedes-Benz EQE 350+)',
      image: `${SITE_URL}/og-image.png`,
      url: `${SITE_URL}/global-brands#heading-benz-eqe`,
      brand: {
        '@type': 'Brand',
        name: 'Mercedes-Benz',
      },
      manufacturer: {
        '@type': 'Organization',
        name: 'Mercedes-Benz Group AG',
      },
      model: 'EQE 350+',
      vehicleModelDate: '2022-2026',
      vehicleTransmission: '1단 감속기 (전기 모터)',
      fuelType: 'https://schema.org/Electric',
      description: 'EVA2 전용 플랫폼 프리미엄 비즈니스 세단 EV. 90.6kWh 배터리(CATL / 파라시스) 탑재.',
      additionalProperty: [
        {
          '@type': 'PropertyValue',
          name: 'Battery Chemistry',
          value: 'NCM 삼원계 (CATL 또는 파라시스) 90.6 kWh',
        },
        {
          '@type': 'PropertyValue',
          name: 'Powertrain Warranty',
          value: '10년 / 250,000 km 배터리 보증서(배터리 인증서 발급)',
        },
      ],
    },
    {
      '@type': 'Vehicle',
      '@id': `${SITE_URL}/global-brands#vehicle-polestar2`,
      name: '폴스타 2 (Polestar 2)',
      image: `${SITE_URL}/og-image.png`,
      url: `${SITE_URL}/global-brands#heading-volvo-polestar`,
      brand: {
        '@type': 'Brand',
        name: 'Polestar',
      },
      manufacturer: {
        '@type': 'Organization',
        name: 'Polestar Performance AB',
      },
      model: 'Polestar 2',
      vehicleModelDate: '2021-2026',
      vehicleTransmission: '1단 감속기 (싱글/듀얼 모터)',
      fuelType: 'https://schema.org/Electric',
      description: 'CMA 플랫폼 기반 5도어 패스트백 크로스오버 EV. 78.0kWh 삼원계 배터리 및 안드로이드 오토모티브 OS 탑재.',
      additionalProperty: [
        {
          '@type': 'PropertyValue',
          name: 'Battery Chemistry',
          value: 'LG에너지솔루션 NCM 78.0 kWh',
        },
        {
          '@type': 'PropertyValue',
          name: 'Powertrain Warranty',
          value: '8년 / 160,000 km',
        },
      ],
    },
    {
      '@type': 'ItemList',
      '@id': `${SITE_URL}/global-brands#itemlist`,
      name: '글로벌 유럽·북미 전기차 모델별 결함 분석 리스트',
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: '쉐보레 볼트 EV / EUV (LG 파우치셀 화재 리콜 및 신품 교체 여부)',
          url: `${SITE_URL}/global-brands#heading-bolt-ev`,
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: '폭스바겐 ID.4 (주행 중 문 열림 터치센서 리콜 및 CO2 히트펌프)',
          url: `${SITE_URL}/global-brands#heading-id4`,
        },
        {
          '@type': 'ListItem',
          position: 3,
          name: '볼보 EX30 / 폴스타 2 (계기판 꺼짐 및 고전압 세라믹 히터)',
          url: `${SITE_URL}/global-brands#heading-volvo-polestar`,
        },
        {
          '@type': 'ListItem',
          position: 4,
          name: '메르세데스-벤츠 EQE / EQS (파라시스 배터리 화재 및 7,500만 원 교체비)',
          url: `${SITE_URL}/global-brands#heading-benz-eqe`,
        },
      ],
    },
    {
      '@type': 'FAQPage',
      '@id': `${SITE_URL}/global-brands#faq`,
      mainEntity: [
        {
          '@type': 'Question',
          name: '중고 쉐보레 볼트 EV를 구매할 때 배터리 리콜 교체 완료 여부는 어떻게 확인하나요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '국토교통부 자동차리콜센터(car.go.kr) 또는 쉐보레 공식 서비스센터 전산에서 66kWh 신품 배터리 팩 교체 완료 및 잔여 8년/16만km 배터리 보증이 리셋되었는지 확인해야 합니다. 배터리가 교체되지 않은 2017~2022년식 매물은 화재 위험으로 구매를 피해야 합니다.',
          },
        },
        {
          '@type': 'Question',
          name: '폭스바겐 ID.4의 주행 중 문 열림 결함은 어떻게 개선되었나요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '2021~2024년식 ID.4의 플러시 도어 핸들 침수 센서 오류로 인한 문 열림 리콜은 도어 핸들 방수 패킹 보강 및 제어 소프트웨어 업데이트로 조치되었습니다. 2025년식 이후는 개선형 도어 래치와 신형 APP550 구동 모터가 적용되었습니다.',
          },
        },
        {
          '@type': 'Question',
          name: '메르세데스-벤츠 EQE/EQS 중고차 구매 시 배터리 보증 만료 위험은 어느 정도인가요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '벤츠 EQS/EQE의 고전압 배터리 팩 교체 비용은 약 6,000만~7,560만 원에 달하므로, 파라시스 배터리 대신 CATL 배터리가 탑재되었는지 확인하고 공식 보증 연장 상품(워런티 플러스) 가입 차량을 선별해야 합니다.',
          },
        },
      ],
    },
    {
      '@type': 'BreadcrumbList',
      '@id': `${SITE_URL}/global-brands#breadcrumb`,
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
          name: '글로벌 브랜드 구매 가이드',
          item: `${SITE_URL}/global-brands`,
        },
      ],
    },
  ],
};

export const metadata: Metadata = {
  title: '글로벌 EV 브랜드 연식별 결함 및 구매 가이드',
  description: '폭스바겐 ID.4, 쉐보레 볼트 EV, 폴스타 2, 벤츠 EQE/EQS 등 유럽/북미 전기차 연식별 결함 및 중고차 구매 가이드',
  keywords: [
    '글로벌 전기차 결함',
    '볼트EV 배터리 화재',
    '폭스바겐 ID4 문열림',
    '폴스타2 히터 결함',
    '볼보 EX30 속도계',
    '벤츠 EQE 화재',
    '벤츠 EQS 배터리 교체비',
    '수입 전기차 연식 가이드',
  ],
  alternates: {
    canonical: '/global-brands',
    languages: {
      'ko-KR': '/global-brands',
      'x-default': '/global-brands',
    },
  },
  openGraph: {
    title: '글로벌 EV 브랜드 연식별 결함 및 구매 가이드 | Global EV Hub',
    description: '폭스바겐 ID.4, 쉐보레 볼트 EV, 폴스타 2, 벤츠 EQE/EQS 등 유럽/북미 전기차 연식별 결함 및 중고차 구매 가이드',
    url: '/global-brands',
    siteName: 'Global EV Hub',
    locale: 'ko_KR',
    type: 'article',
    authors: ['Global EV Hub'],
    section: '전기차 결함 및 구매 가이드',
    publishedTime: '2026-01-01T00:00:00+09:00',
    modifiedTime: '2026-11-01T00:00:00+09:00',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: '글로벌 EV 브랜드 연식별 결함 및 구매 가이드',
        type: 'image/png',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: '글로벌 EV 브랜드 연식별 결함 및 구매 가이드 | Global EV Hub',
    description: '폭스바겐 ID.4, 쉐보레 볼트 EV, 폴스타 2, 벤츠 EQE/EQS 등 유럽/북미 전기차 연식별 결함 및 중고차 구매 가이드',
    site: '@GlobalEVHub',
    creator: '@lolollol2379',
    images: ['/og-image.png'],
  },
};

export default function GlobalEvPage() {
  return (
    <article className="space-y-8 py-6 sm:py-10 max-w-4xl mx-auto">
      <JsonLd data={globalBrandsJsonLd} />
      <BrandComparisonNav currentBrand="global-brands" pageTitle="글로벌 브랜드 구매 가이드" />

      <header className="border-b border-slate-200 pb-4 space-y-2">
        <h1 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-slate-900 tracking-tight">
          유럽 및 북미 EV 연식별 가이드 (폭스바겐, 쉐보레, 볼보/폴스타, 벤츠 등)
        </h1>
        <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
          폭스바겐 ID.4, 쉐보레 볼트 EV, 볼보 EX30/폴스타 2, 메르세데스-벤츠 EQE/EQS 등 유럽·북미 주요 전기차 모델의 고질병(배터리 화재, 주행 중 문 열림, 히터 파손, 배터리 교체비 폭탄)과 연식별 안전 구매 기준을 완벽 분석했습니다.
        </p>
      </header>

      {/* 글로벌 브랜드 연식별 판정 요약 표 (WCAG AA Compliance: table headers, caption, overflow container) */}
      <section aria-labelledby="heading-global-summary" className="space-y-3">
        <h2 id="heading-global-summary" className="text-xl sm:text-2xl font-bold text-slate-900">
          글로벌 주요 차종 연식별 판정 요약 표
        </h2>
        <div
          tabIndex={0}
          role="region"
          aria-label="가로 스크롤 가능한 글로벌 주요 차종 연식별 판정 요약 표"
          className="overflow-x-auto table-scroll-container rounded-2xl border border-slate-200 bg-white shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
        >
          <div className="sm:hidden flex items-center justify-between px-3 py-1.5 text-[11px] font-medium text-slate-600 bg-slate-50 border-b border-slate-200 select-none" aria-hidden="true">
            <span>← 좌우로 밀어서 전체 모델 비교</span>
            <span className="text-[10px] text-blue-700 font-semibold">가로 스크롤 ↔</span>
          </div>
          <table className="w-full min-w-[640px] text-left border-collapse text-xs sm:text-sm" aria-label="글로벌 주요 모델별 주의 및 추천 연식 요약 표">
            <caption className="sr-only">유럽·북미 전기차 모델별 주의 연식, 추천 연식, 주요 결함 및 공식 리콜 출처 비교 요약 표</caption>
            <thead className="bg-slate-900 text-slate-100 uppercase text-[11px] sm:text-xs tracking-wider">
              <tr>
                <th scope="col" className="py-3 px-4 font-semibold text-slate-100">차종/모델</th>
                <th scope="col" className="py-3 px-4 font-semibold text-slate-100">회피/주의 연식</th>
                <th scope="col" className="py-3 px-4 font-semibold text-slate-100">추천 연식 (BUY SAFE)</th>
                <th scope="col" className="py-3 px-4 font-semibold text-slate-100">핵심 결함 및 리스크</th>
                <th scope="col" className="py-3 px-4 font-semibold text-slate-100 text-center">공식 리콜</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              <tr className="hover:bg-slate-50/80 transition-colors">
                <th scope="row" className="py-3 px-4 font-bold text-slate-900 whitespace-nowrap">
                  쉐보레 볼트 EV / EUV
                </th>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-900">
                    2017~2022년식 (미교체)
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-900">
                    리콜 배터리 교체 매물
                  </span>
                </td>
                <td className="py-3 px-4 text-slate-700">
                  LG 파우치셀 분리막 접힘 및 양극 탭 파손 화재 리콜 (신품 배터리 팩 확인 필수)
                </td>
                <td className="py-3 px-4 text-center whitespace-nowrap">
                  <a
                    href="https://www.car.go.kr"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="볼트 EV 국토교통부 자동차리콜센터 리콜 조회 (새 창에서 열림)"
                    className="text-blue-700 hover:text-blue-800 hover:underline font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 rounded-lg inline-flex items-center justify-center gap-1 px-3 py-2 min-h-[44px] min-w-[44px] bg-blue-50/60 hover:bg-blue-100/70 border border-blue-200/60 transition"
                  >
                    <span>리콜 조회</span>
                    <svg className="w-3.5 h-3.5 shrink-0" width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                    <span className="sr-only"> (새 창에서 열림)</span>
                  </a>
                </td>
              </tr>
              <tr className="hover:bg-slate-50/80 transition-colors">
                <th scope="row" className="py-3 px-4 font-bold text-slate-900 whitespace-nowrap">
                  폭스바겐 ID.4
                </th>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-900">
                    2021~2024년식
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-900">
                    2025년식 이후
                  </span>
                </td>
                <td className="py-3 px-4 text-slate-700">
                  주행 중 플러시 도어 핸들 침수 터치 오류로 문 열림 리콜 및 CO2 콤프레셔 파손
                </td>
                <td className="py-3 px-4 text-center whitespace-nowrap">
                  <a
                    href="https://www.car.go.kr"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="ID.4 국토교통부 자동차리콜센터 리콜 조회 (새 창에서 열림)"
                    className="text-blue-700 hover:text-blue-800 hover:underline font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 rounded-lg inline-flex items-center justify-center gap-1 px-3 py-2 min-h-[44px] min-w-[44px] bg-blue-50/60 hover:bg-blue-100/70 border border-blue-200/60 transition"
                  >
                    <span>리콜 조회</span>
                    <svg className="w-3.5 h-3.5 shrink-0" width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                    <span className="sr-only"> (새 창에서 열림)</span>
                  </a>
                </td>
              </tr>
              <tr className="hover:bg-slate-50/80 transition-colors">
                <th scope="row" className="py-3 px-4 font-bold text-slate-900 whitespace-nowrap">
                  볼보 EX30 / 폴스타 2
                </th>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-900">
                    2021~2024년식
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-900">
                    2024년식 이후
                  </span>
                </td>
                <td className="py-3 px-4 text-slate-700">
                  EX30 중앙 속도계 화면 꺼짐 리콜 및 폴스타2 고전압 세라믹 히터(HVCH) 파괴
                </td>
                <td className="py-3 px-4 text-center whitespace-nowrap">
                  <a
                    href="https://www.car.go.kr"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="볼보/폴스타 국토교통부 자동차리콜센터 리콜 조회 (새 창에서 열림)"
                    className="text-blue-700 hover:text-blue-800 hover:underline font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 rounded-lg inline-flex items-center justify-center gap-1 px-3 py-2 min-h-[44px] min-w-[44px] bg-blue-50/60 hover:bg-blue-100/70 border border-blue-200/60 transition"
                  >
                    <span>리콜 조회</span>
                    <svg className="w-3.5 h-3.5 shrink-0" width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                    <span className="sr-only"> (새 창에서 열림)</span>
                  </a>
                </td>
              </tr>
              <tr className="hover:bg-slate-50/80 transition-colors">
                <th scope="row" className="py-3 px-4 font-bold text-slate-900 whitespace-nowrap">
                  메르세데스-벤츠 EQE / EQS
                </th>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-900">
                    2022~2023년식
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-900">
                    2024년식 이후 (CATL 탑재)
                  </span>
                </td>
                <td className="py-3 px-4 text-slate-700">
                  파라시스 배터리 화재 리스크, 플러시 도어 모터 파손 및 7,560만 원 배터리 교체비
                </td>
                <td className="py-3 px-4 text-center whitespace-nowrap">
                  <a
                    href="https://www.car.go.kr"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="벤츠 EQE 국토교통부 자동차리콜센터 리콜 조회 (새 창에서 열림)"
                    className="text-blue-700 hover:text-blue-800 hover:underline font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 rounded-lg inline-flex items-center justify-center gap-1 px-3 py-2 min-h-[44px] min-w-[44px] bg-blue-50/60 hover:bg-blue-100/70 border border-blue-200/60 transition"
                  >
                    <span>리콜 조회</span>
                    <svg className="w-3.5 h-3.5 shrink-0" width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                    <span className="sr-only"> (새 창에서 열림)</span>
                  </a>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      
      <section className="space-y-4" aria-labelledby="heading-bolt-ev">
        <h2 id="heading-bolt-ev" className="text-2xl sm:text-3xl font-bold text-slate-800">
          쉐보레 볼트 EV / EUV
        </h2>

        <ModelSpecWarrantyCard
          modelName="쉐보레 볼트 EV / EUV"
          badge="배터리 리콜 완료 추천"
          msrpRange="신차 단종 / 4,130만 ~ 4,490만 원"
          effectivePriceRange="약 3,300만 원 (출고 당시)"
          usedPriceRange="1,700만 ~ 2,350만 원"
          batterySpecs={{
            capacity: "66.0 kWh (신품 개선 배터리)",
            chemistry: "LG에너지솔루션 NCM622 파우치",
            voltage: "400V 고전압 시스템",
            range: "403km ~ 414km (복합)",
          }}
          warranty={{
            batteryYearsKm: "신품 교체 후 8년 / 160,000 km (리셋)",
            batteryGuaranteeSoh: "신품 팩 교체 시 보증 기간 신규 적용",
            generalYearsKm: "일반 부품 만료 (중고차 기준)",
            outOfWarrantyRisk: "리콜 미교체 차량 구매 절대 금지, 배터리 자비 교체 2,200만 원",
          }}
        />
        <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-xl" role="region" aria-label="쉐보레 볼트 EV 구매 회피 연식 경고">
          <h3 className="text-lg sm:text-xl font-bold text-red-900">
            <span aria-hidden="true">🚫 </span>2017~2022년식: 구매 회피 (AVOID - 배터리 화재 위험)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li><strong>LG화학 파우치셀 화재 리콜:</strong> 분리막 접힘과 양극 탭 찢어짐이라는 2가지 희귀 제조 결함이 겹치면서 대형 배터리 화재 연쇄 발생.</li>
            <li><strong>조치:</strong> 중고차 구매 시 &apos;배터리 팩이 완전히 새것으로 교체된 차량&apos;이 아니면 절대 구매 금지. 배터리 자비 교체 비용은 약 2,200만 원.</li>
          </ul>
        </div>
        <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-r-xl" role="region" aria-label="쉐보레 볼트 EV 안전 구매 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-green-900">
            <span aria-hidden="true">✅ </span>리콜 배터리 교체 완료 매물: 안심 추천 (BUY SAFE - 배터리 보증 연장 확인)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>공식 서비스센터에서 신품 개선 배터리 팩(66kWh)으로 리콜 교체 완료된 이력이 국토부 전산에서 확인되고, 잔여 배터리 보증(8년/16만km 리셋)이 살아있는 매물은 가격 대비 뛰어난 실주행 효율을 제공합니다.</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8" aria-labelledby="heading-id4">
        <h2 id="heading-id4" className="text-2xl sm:text-3xl font-bold text-slate-800">
          폭스바겐 ID.4
        </h2>

        <ModelSpecWarrantyCard
          modelName="폭스바겐 ID.4 (Volkswagen ID.4)"
          badge="MEB 플랫폼 준중형 SUV"
          msrpRange="5,490만 ~ 5,990만 원"
          effectivePriceRange="약 4,800만 ~ 5,300만 원 (보조금 100%)"
          usedPriceRange="3,100만 ~ 4,100만 원"
          batterySpecs={{
            capacity: "82.0 kWh (가용 77.0 kWh)",
            chemistry: "LG엔솔 / SK온 NCM712 삼원계",
            voltage: "400V (최대 135kW 급속)",
            range: "421km ~ 440km (복합)",
          }}
          warranty={{
            batteryYearsKm: "8년 / 160,000 km",
            batteryGuaranteeSoh: "잔존용량(SoH) 70% 보증",
            generalYearsKm: "3년 / 100,000 km",
            outOfWarrantyRisk: "CO2 히트펌프 콤프레셔 파손 550만 원, 도어 핸들 센서 침수 주의",
          }}
        />
        <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-xl" role="region" aria-label="폭스바겐 ID.4 구매 회피 연식 경고">
          <h3 className="text-lg sm:text-xl font-bold text-red-900">
            <span aria-hidden="true">🚫 </span>2021~2024년식: 구매 회피 (AVOID - 주행 중 문 열림 결함)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li><strong>주행 중 도어 열림 리콜:</strong> 플러시 도어 핸들 내부로 세차장 물이나 빗물이 스며들면 터치 센서가 이를 &apos;사람 손&apos;으로 인식해 주행 중인데도 차문이 열려버리는 치명적 결함 발생. 대규모 리콜 및 판매 중단 사태.</li>
            <li><strong>히트펌프 콤프레셔 박살:</strong> 겨울철 고압 R744(CO2) 히트펌프 배관 누수로 콤프레셔가 박살나며 쇳가루가 도는 현상 (수리비 550만 원).</li>
          </ul>
        </div>
        <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-r-xl" role="region" aria-label="폭스바겐 ID.4 안전 구매 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-green-900">
            <span aria-hidden="true">✅ </span>2025년식 이후: 안심 추천 (BUY SAFE - 도어 래치 개선 및 신형 구동계)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>도어 핸들 방수 패킹 보강 및 센서 알고리즘 개선으로 문 열림 리콜이 종결되었으며, 차세대 APP550 고효율 모터 탑재와 인포테인먼트 4.0 적용으로 동력 성능과 조작 편의성이 대폭 향상되었습니다.</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8" aria-labelledby="heading-volvo-polestar">
        <h2 id="heading-volvo-polestar" className="text-2xl sm:text-3xl font-bold text-slate-800">
          볼보 EX30 / 폴스타 2
        </h2>

        <ModelSpecWarrantyCard
          modelName="볼보 EX30 & 폴스타 2"
          badge="스웨디시 프리미엄 EV"
          msrpRange="4,945만 ~ 6,090만 원"
          effectivePriceRange="약 4,400만 ~ 5,400만 원"
          usedPriceRange="3,000만 ~ 4,200만 원"
          batterySpecs={{
            capacity: "69.0 kWh (EX30) / 82.0 kWh (폴스타2)",
            chemistry: "CATL / LG 삼원계 NMC",
            voltage: "400V (최대 153~205kW 급속)",
            range: "404km (EX30) / 449km (폴스타2)",
          }}
          warranty={{
            batteryYearsKm: "8년 / 160,000 km",
            batteryGuaranteeSoh: "잔존용량(SoH) 70% 보증",
            generalYearsKm: "5년 / 100,000 km (수입차 최장급)",
            outOfWarrantyRisk: "폴스타2 고전압 히터(HVCH) 270만 원, EX30 중앙 속도계 OTA 필수",
          }}
        />
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-r-xl" role="region" aria-label="볼보 EX30 및 폴스타 2 주의 연식 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-amber-900">
            <span aria-hidden="true">⚠️ </span>2021~2024년식: 주의 요망 (CAUTION - 소프트웨어 및 히터 결함)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li><strong>EX30 속도계 먹통:</strong> 모든 계기판을 중앙 12.3인치 스크린에 통합했으나 소프트웨어 에러로 주행 중 속도계 화면이 꺼지는 결함 리콜.</li>
            <li><strong>폴스타 2 세라믹 히터 파괴:</strong> 겨울철 고전압 냉각수 히터(HVCH) 내부 세라믹 부품이 쪼개지며 절연 파괴 에러로 히터 셧다운 (수리비 약 270만 원).</li>
          </ul>
        </div>
        <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-r-xl" role="region" aria-label="볼보 EX30 및 폴스타 2 안전 구매 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-green-900">
            <span aria-hidden="true">✅ </span>2024년식 이후: 안심 추천 (BUY SAFE - 폴스타2 페이스리프트 및 EX30 OTA 개선형)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>폴스타 2 싱글모터는 후륜구동(RWD) 플랫폼 전환 및 개선형 세라믹 히터가 탑재되어 전비와 겨울철 내구성이 대폭 강화되었습니다. EX30은 화면 꺼짐 패치 소프트웨어(OTA 1.4 이상) 적용 확인 후 구매를 권장합니다.</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8" aria-labelledby="heading-benz-eqe">
        <h2 id="heading-benz-eqe" className="text-2xl sm:text-3xl font-bold text-slate-800">
          메르세데스-벤츠 EQE / EQS
        </h2>

        <ModelSpecWarrantyCard
          modelName="메르세데스-벤츠 EQE / EQS"
          badge="럭셔리 대형 전기 세단"
          msrpRange="1억 300만 ~ 2억 1,000만 원"
          effectivePriceRange="보조금 0% (8,500만 원 초과)"
          usedPriceRange="5,100만 ~ 1억 1,000만 원 (감가율 극대)"
          batterySpecs={{
            capacity: "88.8~90.6 kWh (EQE) / 118.0 kWh (EQS)",
            chemistry: "파라시스(초기) / CATL(개선형)",
            voltage: "400V EVA2 플랫폼",
            range: "471km (EQE) / 478km (EQS)",
          }}
          warranty={{
            batteryYearsKm: "10년 / 250,000 km (EQS), 10년 / 16만km (EQE)",
            batteryGuaranteeSoh: "잔존용량(SoH) 70% 보증",
            generalYearsKm: "2년 / 무제한 (워런티 플러스 권장)",
            outOfWarrantyRisk: "EQS 배터리팩 교체비 약 7,560만 원 (전손 리스크), 파라시스 셀 기피",
          }}
        />
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-r-xl" role="region" aria-label="메르세데스-벤츠 EQE 및 EQS 주의 연식 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-amber-900">
            <span aria-hidden="true">⚠️ </span>2022~2023년식: 주의 요망 (CAUTION - 수리비 주의)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li><strong>모터라이즈 도어핸들 박살:</strong> 겨울철 얼음이 얼었을 때 도어 핸들 모터가 억지로 튀어나오려다 내부 플라스틱 기어 이빨이 다 부서짐 (수리비 짝당 190만 원).</li>
            <li><strong>배터리 수리비 절망편:</strong> 118kWh EQS 배터리팩 무상보증 종료 후 교체 비용은 약 <strong>7,560만 원</strong>으로 중고차 가격 전체를 상회하는 끔찍한 리스크를 안고 있습니다.</li>
          </ul>
        </div>
        <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-r-xl" role="region" aria-label="메르세데스-벤츠 EQE 및 EQS 안전 구매 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-green-900">
            <span aria-hidden="true">✅ </span>2024년식 이후: 조건부 추천 (BUY CAUTIOUSLY - CATL 배터리 탑재 및 보증 연장 매물)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>파라시스 배터리 대신 CATL 배터리가 탑재된 개체(차대번호 VIN 및 국토교통부 배터리 제조사 조회 필수)를 선택하고, 공식 보증 연장 상품(워런티 플러스) 가입 차량을 엄선하여 구매해야 합니다.</li>
          </ul>
        </div>
      </section>

      {/* Contextual CTA Cross-Links to Interactive Intelligence Tools */}
      <section aria-labelledby="heading-global-tools" className="pt-8 border-t border-slate-200 space-y-6">
        <div className="space-y-1">
          <h2 id="heading-global-tools" className="text-2xl font-bold text-slate-900">
            글로벌 수입 EV 데이터 인텔리전스 및 진단 도구
          </h2>
          <p className="text-sm text-slate-600">
            유럽·북미 9대 브랜드 DSI 결함 순위, 파라시스·CATL 배터리 조회, 수리비 폭탄 방어 및 국고 보조금을 확인하세요.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            href="/reliability-analytics"
            prefetch={false}
            aria-labelledby="cta-global-reliability-title"
            aria-describedby="cta-global-reliability-desc"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-blue-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
          >
            <h3 id="cta-global-reliability-title" className="flex items-center gap-2 text-blue-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📊</span>
              <span>글로벌 9대 브랜드 스텔스 품질 점수(DSI) 비교</span>
            </h3>
            <p id="cta-global-reliability-desc" className="text-xs text-slate-600 leading-relaxed">
              벤츠, BMW, 폭스바겐, 볼보, 폴스타의 결함 심각도 지수와 보증 외 고전압 배터리 교체비 매트릭스를 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-blue-700 font-semibold mt-3 group-hover:underline">
              내구성 랭킹 조회하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>

          <Link
            href="/recall-portal"
            prefetch={false}
            aria-labelledby="cta-global-recall-title"
            aria-describedby="cta-global-recall-desc"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-rose-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-600 focus-visible:ring-offset-2"
          >
            <h3 id="cta-global-recall-title" className="flex items-center gap-2 text-rose-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">🚨</span>
              <span>수입차 VIN 및 통합 리콜 현황 조회</span>
            </h3>
            <p id="cta-global-recall-desc" className="text-xs text-slate-600 leading-relaxed">
              17자리 차대번호로 파라시스, CATL, LG에너지솔루션 등 실제 탑재 배터리 제조사와 국토부 공식 리콜을 조회합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-rose-700 font-semibold mt-3 group-hover:underline">
              리콜 및 배터리 확인하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>

          <Link
            href="/depreciation-calculator"
            prefetch={true}
            aria-labelledby="cta-global-depreciation-title"
            aria-describedby="cta-global-depreciation-desc"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-emerald-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2"
          >
            <h3 id="cta-global-depreciation-title" className="flex items-center gap-2 text-emerald-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📉</span>
              <span>수입 EV 감가상각 시뮬레이터 &amp; 배터리 잔존가치</span>
            </h3>
            <p id="cta-global-depreciation-desc" className="text-xs text-slate-600 leading-relaxed">
              독일 프리미엄 브랜드의 급격한 중고차 감가 곡선과 보증 만료 후 5년 TCO 유지비를 정밀 산출합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-semibold mt-3 group-hover:underline">
              감가율 계산하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>

          <Link
            href="/subsidy-tracker"
            prefetch={true}
            aria-labelledby="cta-global-subsidy-title"
            aria-describedby="cta-global-subsidy-desc"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-amber-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-700 focus-visible:ring-offset-2"
          >
            <h3 id="cta-global-subsidy-title" className="flex items-center gap-2 text-amber-800 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">⚡</span>
              <span>수입 전기차 보조금 실시간 소진율</span>
            </h3>
            <p id="cta-global-subsidy-desc" className="text-xs text-slate-600 leading-relaxed">
              출고가 5,500만 원(100%), 8,500만 원(50%), 8,500만 원 초과(0%) 기준 실질 지자체 보조금을 비교합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-amber-800 font-semibold mt-3 group-hover:underline">
              보조금 소진율 확인하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>
        </div>
      </section>

      {/* Brand Comparison Cross Navigation */}
      <OtherBrandsCrossNav currentBrand="global-brands" />
    </article>
  );
}
