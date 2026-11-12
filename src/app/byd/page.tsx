import type { Metadata } from 'next';
import Link from 'next/link';
import JsonLd from '@/components/JsonLd';
import BrandComparisonNav, { OtherBrandsCrossNav } from '@/components/BrandComparisonNav';

export const dynamic = 'force-static';
export const revalidate = false;

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || 'https://ev-stealth-web.vercel.app').replace(/\/+$/, '');

const bydJsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Article',
      '@id': `${SITE_URL}/byd#article`,
      headline: 'BYD 전기차 연식별 결함 및 구매 가이드',
      description: 'BYD 돌핀, 시라이언 7, 씰, 아토 3 연식별(2021~2026) 에어컨 백색가루, 하체 부식, 조향장치 결함 및 구매 가이드',
      image: [`${SITE_URL}/og-image.png`],
      url: `${SITE_URL}/byd`,
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
        '@id': `${SITE_URL}/byd`,
      },
    },
    {
      '@type': 'ItemList',
      '@id': `${SITE_URL}/byd#itemlist`,
      name: 'BYD 전기차 주요 모델별 연식 결함 가이드 리스트',
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: 'BYD 돌핀 (2021~2023 에어컨 백색가루 및 조향기판 결함 회피, 2024~2025 안심 추천)',
          url: `${SITE_URL}/byd#heading-byd-dolphin`,
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: 'BYD 시라이언 07 (2024년식 12-in-1 모터 통짜 수리비 및 CTB 하부 찍힘 전손 위험)',
          url: `${SITE_URL}/byd#heading-byd-sealion`,
        },
        {
          '@type': 'ListItem',
          position: 3,
          name: 'BYD 씰 (블레이드 LFP 배터리 특성 및 체결 볼트 방청 개선)',
          url: `${SITE_URL}/byd#heading-byd-seal`,
        },
        {
          '@type': 'ListItem',
          position: 4,
          name: 'BYD 아토 3 (에어컨 에바포레이터 악취 및 앞 서스펜션 세팅)',
          url: `${SITE_URL}/byd#heading-byd-atto3`,
        },
      ],
    },
    {
      '@type': 'FAQPage',
      '@id': `${SITE_URL}/byd#faq`,
      mainEntity: [
        {
          '@type': 'Question',
          name: 'BYD 돌핀의 에어컨 백색 가루 결함의 정체와 해결 연식은?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '에어컨 에바포레이터 코팅 불량으로 인체 호흡기에 유해한 수산화알루미늄(Al(OH)3) 분진이 분출된 현상으로, 2024년식 이후 생산분부터 개선된 표면 처리 코팅이 적용되어 해결되었습니다.',
          },
        },
        {
          '@type': 'Question',
          name: 'BYD 시라이언 07의 CTB(Cell-to-Body) 배터리 구조상 주의할 점은?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '배터리 팩이 차체 바닥 구조물과 완전 일체화되어 있어 과속방지턱이나 비포장도로에서 하부 긁힘·찌그러짐 발생 시 부분 수리가 불가하며 배터리 팩 전체(약 1,400만 원) 교체 판정이 나올 수 있습니다.',
          },
        },
        {
          '@type': 'Question',
          name: 'BYD 블레이드 LFP 배터리의 장점과 겨울철 단점은?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '관통 테스트에서도 발화하지 않는 뛰어난 열적 안정성과 약 900만 원대의 저렴한 교체비가 장점이나, 영하 5도 이하 혹한기에서는 화학적 특성상 급속 충전 속도가 크게 저하될 수 있습니다.',
          },
        },
      ],
    },
    {
      '@type': 'BreadcrumbList',
      '@id': `${SITE_URL}/byd#breadcrumb`,
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
          name: 'BYD 구매 가이드',
          item: `${SITE_URL}/byd`,
        },
      ],
    },
  ],
};

export const metadata: Metadata = {
  title: 'BYD 전기차 연식별 결함 및 구매 가이드',
  description: 'BYD 돌핀, 시라이언 7, 씰, 아토 3 연식별(2021~2026) 에어컨 백색가루, 하체 부식, 조향장치 결함 및 구매 가이드',
  keywords: [
    'BYD 연식별 결함',
    'BYD 돌핀 고질병',
    '시라이언 07 수리비',
    'BYD 씰 결함',
    '아토3 결함',
    'BYD 에어컨 백색가루',
    '블레이드 배터리 안전성',
    'CTB 배터리 교체비용',
    'BYD 중고차 가이드',
  ],
  alternates: {
    canonical: '/byd',
    languages: {
      'ko-KR': '/byd',
      'x-default': '/byd',
    },
  },
  openGraph: {
    title: 'BYD 전기차 연식별 결함 및 구매 가이드 | Global EV Hub',
    description: 'BYD 돌핀, 시라이언 7, 씰, 아토 3 연식별(2021~2026) 에어컨 백색가루, 하체 부식, 조향장치 결함 및 구매 가이드',
    url: '/byd',
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
        alt: 'BYD 전기차 연식별 결함 및 구매 가이드',
        type: 'image/png',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'BYD 전기차 연식별 결함 및 구매 가이드 | Global EV Hub',
    description: 'BYD 돌핀, 시라이언 7, 씰, 아토 3 연식별(2021~2026) 에어컨 백색가루, 하체 부식, 조향장치 결함 및 구매 가이드',
    site: '@GlobalEVHub',
    creator: '@lolollol2379',
    images: ['/og-image.png'],
  },
};

export default function BydPage() {
  return (
    <article className="space-y-8 py-6 sm:py-10 max-w-4xl mx-auto">
      <JsonLd data={bydJsonLd} />
      <BrandComparisonNav currentBrand="byd" pageTitle="BYD 구매 가이드" />

      <header className="border-b pb-4 space-y-2">
        <h1 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-slate-900 tracking-tight">
          BYD 연식별 구매 가이드 (피해야 할 연식)
        </h1>
        <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
          중국 1위 전기차 제조사 BYD의 돌핀, 시라이언 07, 씰, 아토 3 모델별 고질병(에어컨 백색가루, CTB 일체형 배터리 파손 수리비, 하체 부식 등)과 추천 연식을 완벽 분석했습니다.
        </p>
      </header>

      {/* BYD 연식별 판정 요약 표 (WCAG AA Compliance: table headers, caption, overflow container) */}
      <section aria-labelledby="heading-byd-summary" className="space-y-3">
        <h2 id="heading-byd-summary" className="text-xl sm:text-2xl font-bold text-slate-900">
          BYD 주요 차종 연식별 판정 요약 표
        </h2>
        <div className="overflow-x-auto table-scroll-container rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="sm:hidden flex items-center justify-between px-3 py-1.5 text-[11px] font-medium text-slate-500 bg-slate-50 border-b border-slate-200 select-none" aria-hidden="true">
            <span>← 좌우로 밀어서 전체 모델 비교</span>
            <span className="text-[10px] text-blue-700 font-semibold">가로 스크롤 ↔</span>
          </div>
          <table className="w-full min-w-[640px] text-left border-collapse text-xs sm:text-sm" aria-label="BYD 주요 모델별 주의 및 추천 연식 요약 표">
            <caption className="sr-only">BYD 전기차 모델별 주의 연식, 추천 연식, 주요 결함 및 공식 리콜 출처 비교 요약 표</caption>
            <thead className="bg-slate-900 text-slate-100 uppercase text-[11px] sm:text-xs tracking-wider">
              <tr>
                <th scope="col" className="py-3 px-4 font-semibold text-slate-100">차종/모델</th>
                <th scope="col" className="py-3 px-4 font-semibold text-slate-100">주의 연식 (CAUTION)</th>
                <th scope="col" className="py-3 px-4 font-semibold text-slate-100">추천 연식 (BUY SAFE)</th>
                <th scope="col" className="py-3 px-4 font-semibold text-slate-100">핵심 결함 및 리스크</th>
                <th scope="col" className="py-3 px-4 font-semibold text-slate-100 text-center">공식 출처</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              <tr className="hover:bg-slate-50/80 transition-colors">
                <th scope="row" className="py-3 px-4 font-bold text-slate-900 whitespace-nowrap">
                  돌핀 (Dolphin)
                </th>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-900">
                    2021~2023년식
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-900">
                    2024~2025년식
                  </span>
                </td>
                <td className="py-3 px-4 text-slate-700">
                  에어컨 백색가루(Al(OH)3) 실내 분출 및 조향장치(CEPS) 리콜
                </td>
                <td className="py-3 px-4 text-center whitespace-nowrap">
                  <a
                    href="https://www.car.go.kr"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="돌핀 국토교통부 자동차리콜센터 공식 정보 (새 창에서 열림)"
                    className="text-blue-700 hover:text-blue-800 hover:underline font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 rounded-lg inline-flex items-center justify-center gap-1 px-3 py-2 min-h-[44px] bg-blue-50/60 hover:bg-blue-100/70 border border-blue-200/60 transition"
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
                  시라이언 07 (Sealion 07)
                </th>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-900">
                    2024년식
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-900">
                    2025년식
                  </span>
                </td>
                <td className="py-3 px-4 text-slate-700">
                  12-in-1 모터 통교체 수리비 및 CTB 하부 긁힘 배터리 파손 리스크
                </td>
                <td className="py-3 px-4 text-center whitespace-nowrap">
                  <a
                    href="https://www.car.go.kr"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="시라이언 07 국토교통부 자동차리콜센터 공식 정보 (새 창에서 열림)"
                    className="text-blue-700 hover:text-blue-800 hover:underline font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 rounded-lg inline-flex items-center justify-center gap-1 px-3 py-2 min-h-[44px] bg-blue-50/60 hover:bg-blue-100/70 border border-blue-200/60 transition"
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
                  씰 (Seal)
                </th>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-900">
                    2022~2023년식
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-900">
                    2024년식
                  </span>
                </td>
                <td className="py-3 px-4 text-slate-700">
                  겨울철 LFP 배터리 셧다운(SoC 급락) 및 하체 볼트 조기 녹 발생
                </td>
                <td className="py-3 px-4 text-center whitespace-nowrap">
                  <a
                    href="https://www.car.go.kr"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="씰 국토교통부 자동차리콜센터 공식 정보 (새 창에서 열림)"
                    className="text-blue-700 hover:text-blue-800 hover:underline font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 rounded-lg inline-flex items-center justify-center gap-1 px-3 py-2 min-h-[44px] bg-blue-50/60 hover:bg-blue-100/70 border border-blue-200/60 transition"
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
                  아토 3 (Atto 3)
                </th>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-900">
                    2022~2024년식
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-900">
                    2025년식
                  </span>
                </td>
                <td className="py-3 px-4 text-slate-700">
                  에어컨 에바포레이터 곰팡이 악취 및 지나치게 무른 앞 댐퍼 세팅
                </td>
                <td className="py-3 px-4 text-center whitespace-nowrap">
                  <a
                    href="https://www.car.go.kr"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="아토 3 국토교통부 자동차리콜센터 공식 정보 (새 창에서 열림)"
                    className="text-blue-700 hover:text-blue-800 hover:underline font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 rounded-lg inline-flex items-center justify-center gap-1 px-3 py-2 min-h-[44px] bg-blue-50/60 hover:bg-blue-100/70 border border-blue-200/60 transition"
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
      
      <section className="space-y-4" aria-labelledby="heading-byd-dolphin">
        <h2 id="heading-byd-dolphin" className="text-2xl sm:text-3xl font-bold text-slate-800">
          돌핀 (Dolphin)
        </h2>
        
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-r-xl" role="region" aria-label="BYD 돌핀 주의 연식 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-amber-900">
            <span aria-hidden="true">⚠️ </span>2021~2023년식: 주의 요망 (CAUTION)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li><strong>에어컨 하얀 가루 (Al(OH)3):</strong> 에어컨 에바코어 코팅 불량으로 인해 호흡기에 치명적인 하얀 알루미늄 가루가 실내로 뿜어져 나오는 심각한 결함 발생.</li>
            <li><strong>조향장치 결함:</strong> 23년식에서 핸들 조향장치(CEPS) 컨트롤러 기판 마찰로 인한 파워스티어링 상실 위험 (대규모 리콜 진행됨).</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-r-xl" role="region" aria-label="BYD 돌핀 안전 구매 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-green-900">
            <span aria-hidden="true">✅ </span>2024~2025년식: 안심 추천 (BUY SAFE)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>에바코어 코팅이 개선되었고 새로운 후륜 멀티링크 서스펜션이 적용되어 타이어 편마모와 승차감이 대폭 개선되었습니다. 배터리 교체 비용도 전 세계 최저 수준(약 900만 원 선)으로 유지비가 매우 저렴합니다.</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8" aria-labelledby="heading-byd-sealion">
        <h2 id="heading-byd-sealion" className="text-2xl sm:text-3xl font-bold text-slate-800">
          시라이언 07 (Sealion 07)
        </h2>
        
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-r-xl" role="region" aria-label="BYD 시라이언 07 주의 연식 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-amber-900">
            <span aria-hidden="true">⚠️ </span>2024년식: 주의 요망 (CAUTION)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li><strong>12-in-1 모터 통짜 수리비 폭탄:</strong> 모터, 인버터, 충전기 등이 12-in-1으로 통합되어 있어 부품 하나만 고장 나도 전체 모듈을 통째로 교체해야 함 (보증 수리 외 비용 약 600만 원 발생).</li>
            <li><strong>CTB (Cell-to-Body) 배터리 파손 위험:</strong> 배터리 케이스가 차량 하부 바닥과 일체형이라서 주행 중 돌을 밟아 하부가 5mm만 찌그러져도 배터리 전체(약 1,400만 원)를 통교체해야 하는 치명적 수리 지옥 리스크.</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-r-xl" role="region" aria-label="BYD 시라이언 07 안전 구매 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-green-900">
            <span aria-hidden="true">✅ </span>2025년식: 안심 추천 (BUY SAFE)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>루프 라이다 세정 노즐 결함 개선 및 초기 하체 세팅이 수정되었습니다. 단, CTB 통짜 배터리의 구조적 한계(하부 긁힘 시 전손 위기)는 25년식도 동일하므로 반드시 하부 코팅이나 주의 운전이 필요합니다.</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8" aria-labelledby="heading-byd-seal">
        <h2 id="heading-byd-seal" className="text-2xl sm:text-3xl font-bold text-slate-800">
          씰 (Seal)
        </h2>
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-r-xl" role="region" aria-label="BYD 씰 주의 연식 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-amber-900">
            <span aria-hidden="true">⚠️ </span>2022~2023년식: 주의 요망 (CAUTION)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>LFP 배터리 겨울철 셧다운(25%에서 갑자기 0%로 추락) 및 하체 나사 부식 발생.</li>
          </ul>
        </div>
        <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-r-xl" role="region" aria-label="BYD 씰 안전 구매 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-green-900">
            <span aria-hidden="true">✅ </span>2024년식: 안심 추천 (BUY SAFE)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>하체 체결 볼트 방청 도금이 아연-니켈 도금으로 개선되어 조기 녹 발생 문제를 해결하였습니다.</li>
            <li>겨울철 LFP 배터리 잔여량 급락 방지를 위한 BMS 셀 전압 편차 캘리브레이션 펌웨어가 적용되어 주행 안정성이 크게 향상되었습니다.</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8" aria-labelledby="heading-byd-atto3">
        <h2 id="heading-byd-atto3" className="text-2xl sm:text-3xl font-bold text-slate-800">
          아토 3 (Atto 3)
        </h2>
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-r-xl" role="region" aria-label="BYD 아토 3 주의 연식 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-amber-900">
            <span aria-hidden="true">⚠️ </span>2022~2024년식: 주의 요망 (CAUTION)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>초기형 에어컨 곰팡이 냄새 고질병 및 앞바퀴 털림 증상. 24년식에 일부 개선되었으나 여전히 앞 서스펜션 세팅이 너무 무릅니다.</li>
          </ul>
        </div>
        <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-r-xl" role="region" aria-label="BYD 아토 3 안전 구매 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-green-900">
            <span aria-hidden="true">✅ </span>2025년식: 안심 추천 (BUY SAFE - 개선형)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>공조기 에바포레이터 친수성 코팅 공정이 전면 변경되어 냄새 리스크가 차단되었으며, 앞 댐퍼 감쇠력 튜닝으로 고속 주행 시 앞바퀴 흔들림이 개선되었습니다.</li>
          </ul>
        </div>
      </section>

      {/* Contextual CTA Cross-Links to Interactive Intelligence Tools */}
      <section aria-labelledby="heading-byd-tools" className="pt-8 border-t border-slate-200 space-y-6">
        <div className="space-y-1">
          <h2 id="heading-byd-tools" className="text-2xl font-bold text-slate-900">
            BYD 전기차 내구성 및 실시간 분석 도구
          </h2>
          <p className="text-sm text-slate-600">
            블레이드 배터리 안전성, CTB 구조적 수리비 리스크, 감가율 및 국내 진출 모델 보조금 현황을 확인하세요.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            href="/reliability-analytics?brand=byd"
            prefetch={false}
            aria-label="BYD 결함 통계 및 수리비 조회 바로가기"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-blue-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
          >
            <h3 className="flex items-center gap-2 text-blue-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📊</span>
              <span>BYD DSI 결함 통계 및 수리비</span>
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              12-in-1 모터 통교체 수리비 및 CTB 하부 찍힘 위험 등 BYD 실차주 고질병 데이터를 분석합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-blue-700 font-semibold mt-3 group-hover:underline">
              BYD 결함 통계 보기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>

          <Link
            href="/recall-portal?brand=byd"
            prefetch={false}
            aria-label="BYD 공식 리콜 및 배터리 정보 조회 바로가기"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-rose-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-600"
          >
            <h3 className="flex items-center gap-2 text-rose-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">🚨</span>
              <span>BYD 공식 리콜 및 배터리 정보</span>
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              돌핀 스티어링 리콜 내역, 블레이드 LFP 셀 제조사(FinDreams) 및 VIN 차대번호 조회를 제공합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-rose-700 font-semibold mt-3 group-hover:underline">
              리콜 및 배터리 확인하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>

          <Link
            href="/depreciation-calculator"
            prefetch={true}
            aria-label="BYD LFP 배터리 감가 및 잔존가치 계산기 바로가기"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-emerald-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
          >
            <h3 className="flex items-center gap-2 text-emerald-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📉</span>
              <span>LFP 배터리 감가 및 잔존가치 계산기</span>
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              중국산 LFP 배터리의 국내 중고차 시장 감가방어율과 5년 보유 TCO 시뮬레이션을 계산합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-semibold mt-3 group-hover:underline">
              감가율 계산하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>

          <Link
            href="/subsidy-tracker"
            prefetch={true}
            aria-label="BYD 모델별 지자체 보조금 현황 조회 바로가기"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-amber-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-600"
          >
            <h3 className="flex items-center gap-2 text-amber-800 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">⚡</span>
              <span>BYD 모델별 지자체 보조금 현황</span>
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              배터리 에너지 밀도 및 재활용 계수에 따른 환경부 보조금 차등 지급액과 잔여 쿼터를 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-amber-800 font-semibold mt-3 group-hover:underline">
              보조금 소진율 확인하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>
        </div>
      </section>

      {/* Brand Comparison Cross Navigation */}
      <OtherBrandsCrossNav currentBrand="byd" />
    </article>
  );
}
