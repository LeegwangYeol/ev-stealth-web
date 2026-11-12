import type { Metadata } from 'next';
import Link from 'next/link';
import JsonLd from '@/components/JsonLd';
import BrandComparisonNav, { OtherBrandsCrossNav } from '@/components/BrandComparisonNav';

export const dynamic = 'force-static';
export const revalidate = false;

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || 'https://ev-stealth-web.vercel.app').replace(/\/+$/, '');

const hyundaiKiaJsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Article',
      '@id': `${SITE_URL}/hyundai-kia#article`,
      headline: '현대/기아 전기차 연식별 결함 및 구매 가이드',
      description: '아이오닉5, EV6, EV9 등 현대/기아 전기차 연식별(2021~2026) ICCU 결함, 고질병 분석 및 피해야 할 연식 가이드',
      image: [`${SITE_URL}/og-image.png`],
      url: `${SITE_URL}/hyundai-kia`,
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
        '@id': `${SITE_URL}/hyundai-kia`,
      },
    },
    {
      '@type': 'ItemList',
      '@id': `${SITE_URL}/hyundai-kia#itemlist`,
      name: '현대/기아 전기차 주요 차종별 연식 결함 가이드',
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: '현대 아이오닉 5 (2021~2022 초기형 ICCU 결함 회피 및 2025 페이스리프트 추천)',
          url: `${SITE_URL}/hyundai-kia#heading-ioniq5`,
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: '기아 EV6 (2021~2023 12V 방전 및 통합충전모듈 리콜)',
          url: `${SITE_URL}/hyundai-kia#heading-ev6`,
        },
        {
          '@type': 'ListItem',
          position: 3,
          name: '기아 EV9 (초기 시동 꺼짐 소프트웨어 리콜 및 고용량 배터리팩 안전성)',
          url: `${SITE_URL}/hyundai-kia#heading-ev9`,
        },
      ],
    },
    {
      '@type': 'FAQPage',
      '@id': `${SITE_URL}/hyundai-kia#faq`,
      mainEntity: [
        {
          '@type': 'Question',
          name: '아이오닉 5 및 EV6의 ICCU(통합충전제어장치) 결함 증상은 무엇인가요?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '완속 충전 직후 또는 고속 주행 중 차량 뒤편에서 펑 소리와 함께 전원공급장치 점검 경고등이 점등되며 수 분 내 차량 속도가 제한되고 시동이 꺼지는 현상입니다. 내부 파워소자 과전류 파손이 원인입니다.',
          },
        },
        {
          '@type': 'Question',
          name: '중고 아이오닉5/EV6 구매 시 ICCU 개선품 장착 여부를 확인하는 방법은?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '블루핸즈나 오토큐 또는 자동차리콜센터(car.go.kr)에서 차대번호(VIN)로 국토교통부 리콜 및 무상수리 이력(개선형 ICCU 부품 교체 여부)을 반드시 확인한 후 구매해야 합니다.',
          },
        },
        {
          '@type': 'Question',
          name: '현대/기아 전기차 중 가장 안전하게 추천할 수 있는 연식은?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '2024년식 하반기 이후 페이스리프트 모델(더 뉴 아이오닉5, 더 뉴 EV6) 및 2025~2026년식은 2세대 개선형 ICCU와 84kWh 대용량 배터리가 장착되어 내구성과 고질병 위험이 획기적으로 개선되었습니다.',
          },
        },
      ],
    },
    {
      '@type': 'BreadcrumbList',
      '@id': `${SITE_URL}/hyundai-kia#breadcrumb`,
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
          name: '현대/기아 구매 가이드',
          item: `${SITE_URL}/hyundai-kia`,
        },
      ],
    },
  ],
};

export const metadata: Metadata = {
  title: '현대/기아 전기차 연식별 결함 및 구매 가이드',
  description: '아이오닉5, EV6, EV9 등 현대/기아 전기차 연식별(2021~2026) ICCU 결함, 고질병 분석 및 피해야 할 연식 가이드',
  keywords: [
    '현대기아 전기차 결함',
    '아이오닉5 ICCU',
    '기아 EV6 결함',
    'EV9 시동꺼짐',
    '아이오닉5 고질병',
    'EV6 리콜',
    'E-GMP 결함',
    '전기차 피해야할 연식',
    '현대기아 전기차 중고',
  ],
  alternates: {
    canonical: '/hyundai-kia',
    languages: {
      'ko-KR': '/hyundai-kia',
      'x-default': '/hyundai-kia',
    },
  },
  openGraph: {
    title: '현대/기아 전기차 연식별 결함 및 구매 가이드 | Global EV Hub',
    description: '아이오닉5, EV6, EV9 등 현대/기아 전기차 연식별(2021~2026) ICCU 결함, 고질병 분석 및 피해야 할 연식 가이드',
    url: '/hyundai-kia',
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
        alt: '현대/기아 전기차 연식별 결함 및 구매 가이드',
        type: 'image/png',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: '현대/기아 전기차 연식별 결함 및 구매 가이드 | Global EV Hub',
    description: '아이오닉5, EV6, EV9 등 현대/기아 전기차 연식별(2021~2026) ICCU 결함, 고질병 분석 및 피해야 할 연식 가이드',
    site: '@GlobalEVHub',
    creator: '@lolollol2379',
    images: ['/og-image.png'],
  },
};

export default function HyundaiKiaPage() {
  return (
    <article className="space-y-8 py-6 sm:py-10 max-w-4xl mx-auto">
      <JsonLd data={hyundaiKiaJsonLd} />
      <BrandComparisonNav currentBrand="hyundai-kia" pageTitle="현대/기아 구매 가이드" />

      <header className="border-b pb-4 space-y-2">
        <h1 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-slate-900 tracking-tight">
          현대/기아 연식별 구매 가이드 (피해야 할 연식)
        </h1>
        <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
          현대 아이오닉 5, 기아 EV6, EV9의 E-GMP 800V ICCU(통합충전제어장치) 파손, 후륜 구동축 스플라인 파손 및 12V 방전 고질병을 분석하고 연식별 안전 구매 기준을 제시합니다.
        </p>
      </header>

      {/* 현대/기아 연식별 판정 요약 표 (WCAG AA Compliance: table headers, caption, overflow container) */}
      <section aria-labelledby="heading-hyundai-kia-summary" className="space-y-3">
        <h2 id="heading-hyundai-kia-summary" className="text-xl sm:text-2xl font-bold text-slate-900">
          현대·기아 주요 차종 연식별 판정 요약 표
        </h2>
        <div className="overflow-x-auto table-scroll-container rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="sm:hidden flex items-center justify-between px-3 py-1.5 text-[11px] font-medium text-slate-500 bg-slate-50 border-b border-slate-200 select-none" aria-hidden="true">
            <span>← 좌우로 밀어서 전체 모델 비교</span>
            <span className="text-[10px] text-blue-700 font-semibold">가로 스크롤 ↔</span>
          </div>
          <table className="w-full min-w-[640px] text-left border-collapse text-xs sm:text-sm" aria-label="현대 기아 주요 모델별 주의 및 추천 연식 요약 표">
            <caption className="sr-only">현대 아이오닉 5, 기아 EV6, EV9 연식별 회피 연식, 주의 연식, 추천 연식, 주요 고질병 및 리콜 출처 요약 표</caption>
            <thead className="bg-slate-900 text-slate-100 uppercase text-[11px] sm:text-xs tracking-wider">
              <tr>
                <th scope="col" className="py-3 px-4 font-semibold text-slate-100">차종/모델</th>
                <th scope="col" className="py-3 px-4 font-semibold text-slate-100">회피 연식 (AVOID)</th>
                <th scope="col" className="py-3 px-4 font-semibold text-slate-100">주의 연식 (CAUTION)</th>
                <th scope="col" className="py-3 px-4 font-semibold text-slate-100">추천 연식 (BUY SAFE)</th>
                <th scope="col" className="py-3 px-4 font-semibold text-slate-100">핵심 결함 및 리스크</th>
                <th scope="col" className="py-3 px-4 font-semibold text-slate-100 text-center">공식 리콜</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              <tr className="hover:bg-slate-50/80 transition-colors">
                <th scope="row" className="py-3 px-4 font-bold text-slate-900 whitespace-nowrap">
                  아이오닉 5 (Ioniq 5)
                </th>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-900">
                    2021~2022년식
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-900">
                    2023~2024년식
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-900">
                    2025년식 (PE)
                  </span>
                </td>
                <td className="py-3 px-4 text-slate-700">
                  800V ICCU 내부 퓨즈 단선(고속도로 동력 상실), 후방 와이퍼 미적용
                </td>
                <td className="py-3 px-4 text-center whitespace-nowrap">
                  <a
                    href="https://www.car.go.kr"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="국토교통부 자동차리콜센터 아이오닉 5 ICCU 리콜 공지 (새 창에서 열림)"
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
                  기아 EV6 (Kia EV6)
                </th>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-900">
                    2022년식
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-900">
                    2023~2024년식
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-900">
                    2025년식 (PE)
                  </span>
                </td>
                <td className="py-3 px-4 text-slate-700">
                  충전구 핀 고착, 후륜 구동축 스플라인 파손(24V-057), 오디오 앰프 고장
                </td>
                <td className="py-3 px-4 text-center whitespace-nowrap">
                  <a
                    href="https://www.nhtsa.gov/recalls?nhtsaId=24V057000"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="미국 NHTSA 기아 EV6 구동축 파손 리콜(24V-057) 정보 (새 창에서 열림)"
                    className="text-blue-700 hover:text-blue-800 hover:underline font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 rounded-lg inline-flex items-center justify-center gap-1 px-3 py-2 min-h-[44px] bg-blue-50/60 hover:bg-blue-100/70 border border-blue-200/60 transition"
                  >
                    <span>NHTSA</span>
                    <svg className="w-3.5 h-3.5 shrink-0" width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                    <span className="sr-only"> (새 창에서 열림)</span>
                  </a>
                </td>
              </tr>
              <tr className="hover:bg-slate-50/80 transition-colors">
                <th scope="row" className="py-3 px-4 font-bold text-slate-900 whitespace-nowrap">
                  기아 EV9 (Kia EV9)
                </th>
                <td className="py-3 px-4 text-slate-400">
                  -
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-900">
                    2023~2024년식
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-900">
                    2025~2026년식
                  </span>
                </td>
                <td className="py-3 px-4 text-slate-700">
                  지문인식/무선충전 암전류 12V 방전 및 대용량 ICCU 완속 충전 오류
                </td>
                <td className="py-3 px-4 text-center whitespace-nowrap">
                  <a
                    href="https://www.car.go.kr"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="국토교통부 자동차리콜센터 기아 EV9 리콜 및 무상수리 정보 (새 창에서 열림)"
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
      
      {/* Ioniq 5 Guide */}
      <section className="space-y-4" aria-labelledby="heading-ioniq5">
        <h2 id="heading-ioniq5" className="text-2xl sm:text-3xl font-bold text-slate-800">
          아이오닉 5 (Ioniq 5)
        </h2>
        
        <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-xl" role="region" aria-label="현대 아이오닉 5 구매 회피 연식 경고">
          <h3 className="text-lg sm:text-xl font-bold text-red-900">
            <span aria-hidden="true">🚫 </span>2021~2022년식: 구매 회피 (AVOID - 절대 피할 것)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li><strong>ICCU 결함:</strong> 800V ICCU 내부 퓨즈가 끊어지며 고속도로에서 갑자기 차가 서버림 (예상 수리비 525만 원 ~ 692만 원).</li>
            <li><strong>후방 와이퍼 부재:</strong> 비 오는 날 후방 시야가 완전히 가려져 심각한 안전 문제 발생.</li>
            <li><strong>조치:</strong> 이 연식은 감가가 심하더라도 피하는 것이 상책입니다.</li>
          </ul>
        </div>

        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-r-xl" role="region" aria-label="현대 아이오닉 5 주의 연식 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-amber-900">
            <span aria-hidden="true">⚠️ </span>2023~2024년식: 주의 요망 (CAUTION)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>배터리가 77.4kWh로 커지고 프리컨디셔닝이 추가되었으나, 여전히 ICCU 리콜(24V-868) 대상입니다.</li>
            <li><strong>조치:</strong> 딜러나 서비스센터에서 ICCU 리콜이 완료되었는지 반드시 확인 후 구매하세요.</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-r-xl" role="region" aria-label="현대 아이오닉 5 안전 구매 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-green-900">
            <span aria-hidden="true">✅ </span>2025년식 (페이스리프트): 안심 추천 (BUY SAFE)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>공장 출고 때부터 ICCU 하드웨어가 개선되었고, 84kWh로 배터리 용량 증가, 후방 와이퍼가 기본 장착되었습니다. 가장 추천하는 연식입니다.</li>
          </ul>
        </div>
      </section>

      {/* Kia EV6 Guide */}
      <section className="space-y-4 mt-8" aria-labelledby="heading-ev6">
        <h2 id="heading-ev6" className="text-2xl sm:text-3xl font-bold text-slate-800">
          기아 EV6 (Kia EV6)
        </h2>
        
        <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-xl" role="region" aria-label="기아 EV6 구매 회피 연식 경고">
          <h3 className="text-lg sm:text-xl font-bold text-red-900">
            <span aria-hidden="true">🚫 </span>2022년식: 구매 회피 (AVOID - 절대 피할 것)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li><strong>초기 결함:</strong> 충전구 잠금 핀이 고착되어 충전기가 안 빠지는 문제, 너무 단단한 서스펜션 세팅으로 인한 승차감 저하.</li>
          </ul>
        </div>

        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-r-xl" role="region" aria-label="기아 EV6 주의 연식 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-amber-900">
            <span aria-hidden="true">⚠️ </span>2023~2024년식: 주의 요망 (CAUTION)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>후륜 구동축 톱니바퀴(스플라인) 파손 리콜(24V-057) 및 메리디안 오디오 앰프 고장(수리비 100만 원 이상) 위험이 있습니다.</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-r-xl" role="region" aria-label="기아 EV6 안전 구매 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-green-900">
            <span aria-hidden="true">✅ </span>2025년식 (페이스리프트): 안심 추천 (BUY SAFE)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>승차감이 크게 개선되었고 초기 기계적 결함이 대부분 잡혔습니다.</li>
          </ul>
        </div>
      </section>

      {/* Kia EV9 Guide */}
      <section className="space-y-4 mt-8" aria-labelledby="heading-ev9">
        <h2 id="heading-ev9" className="text-2xl sm:text-3xl font-bold text-slate-800">
          기아 EV9 (Kia EV9)
        </h2>
        
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-r-xl" role="region" aria-label="기아 EV9 주의 연식 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-amber-900">
            <span aria-hidden="true">⚠️ </span>2023~2024년식: 주의 요망 (CAUTION - 초기 12V 방전 및 소프트웨어 주의)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li><strong>12V 저전압 배터리 방전:</strong> 지문 인증 시스템 및 스마트폰 무선 충전 패드 암전류로 인한 12V 방전 및 시동 불가 문제 발생 (무상수리 조치 대상).</li>
            <li><strong>ICCU 충전 소프트웨어 리콜:</strong> 99.8kWh 대용량 배터리팩 충전 제어기(ICCU) 소프트웨어 결함으로 완속 충전 오류 발생 (공식 리콜 조치 필수 확인).</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-r-xl" role="region" aria-label="기아 EV9 안전 구매 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-green-900">
            <span aria-hidden="true">✅ </span>2025~2026년식: 안심 추천 (BUY SAFE - 전장 시스템 안정화)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>BMS 슬립 제어 로직이 개선되어 암전류 방전 문제가 해결되었으며, 전장 시스템 안정화와 2열 멀티 컨투어 시트 소음 방지 부품이 기본 적용되었습니다.</li>
          </ul>
        </div>
      </section>

      {/* Contextual CTA Cross-Links to Interactive Intelligence Tools */}
      <section aria-labelledby="heading-hyundai-kia-tools" className="pt-8 border-t border-slate-200 space-y-6">
        <div className="space-y-1">
          <h2 id="heading-hyundai-kia-tools" className="text-2xl font-bold text-slate-900">
            현대·기아 전기차 심층 분석 및 실시간 조회 도구
          </h2>
          <p className="text-sm text-slate-600">
            결함 빅데이터, 국토교통부 공식 리콜, 중고차 감가율 및 2026년 지자체 보조금 잔여량을 실시간으로 확인하세요.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            href="/reliability-analytics?brand=hyundai"
            prefetch={false}
            aria-label="현대·기아 결함 분석 (DSI) 통계 바로가기"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-blue-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
          >
            <h3 className="flex items-center gap-2 text-blue-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📊</span>
              <span>현대·기아 결함 분석 (DSI)</span>
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              아이오닉5 ICCU, EV6 구동축 등 연식별 결함 심각도 지수와 보증 외 예상 수리비 매트릭스를 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-blue-700 font-semibold mt-3 group-hover:underline">
              결함 통계 조회하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>

          <Link
            href="/recall-portal?brand=hyundai"
            prefetch={false}
            aria-label="현대·기아 공식 리콜 포털 바로가기"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-rose-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-600"
          >
            <h3 className="flex items-center gap-2 text-rose-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">🚨</span>
              <span>현대·기아 공식 리콜 포털</span>
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              차대번호(VIN) 17자리 또는 모델명으로 국토교통부 공식 리콜 조치 여부 및 탑재 배터리 제조사를 즉시 조회합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-rose-700 font-semibold mt-3 group-hover:underline">
              리콜 및 배터리 확인하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>

          <Link
            href="/depreciation-calculator"
            prefetch={true}
            aria-label="전기차 감가 및 배터리 수명 계산기 바로가기"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-emerald-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
          >
            <h3 className="flex items-center gap-2 text-emerald-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📉</span>
              <span>전기차 감가·배터리 수명 계산기</span>
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              보조금 수령 후 5년간의 잔존가치, 배터리 잔존성능(SoH), 연차별 총소유비용(TCO)을 정밀 시뮬레이션합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-semibold mt-3 group-hover:underline">
              감가율 계산하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>

          <Link
            href="/subsidy-tracker"
            prefetch={true}
            aria-label="전국 지자체 실시간 보조금 소진율 조회 바로가기"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-amber-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-600"
          >
            <h3 className="flex items-center gap-2 text-amber-800 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">⚡</span>
              <span>전국 지자체 실시간 보조금 소진율</span>
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              환경부 및 17개 광역시도별 보조금 소진율, 마감 임박 경보, 5,500만 원 상한제 차등 지급액을 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-amber-800 font-semibold mt-3 group-hover:underline">
              보조금 소진율 확인하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>
        </div>
      </section>

      {/* Brand Comparison Cross Navigation */}
      <OtherBrandsCrossNav currentBrand="hyundai-kia" />
    </article>
  );
}
