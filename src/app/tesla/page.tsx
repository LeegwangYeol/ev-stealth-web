import type { Metadata } from 'next';
import Link from 'next/link';
import JsonLd from '@/components/JsonLd';
import BrandComparisonNav, { OtherBrandsCrossNav } from '@/components/BrandComparisonNav';

export const dynamic = 'force-static';
export const revalidate = false;

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || 'https://ev-stealth-web.vercel.app').replace(/\/+$/, '');

const teslaJsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Article',
      '@id': `${SITE_URL}/tesla#article`,
      headline: '테슬라 연식별 결함 및 구매 가이드',
      description: '테슬라 모델 3, 모델 Y 연식별(2017~2026) 히터 파괴, 컨트롤 암, 옥토밸브 히트펌프 결함 분석 및 중고차 구매 가이드',
      url: `${SITE_URL}/tesla`,
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
          url: `${SITE_URL}/favicon.ico`,
        },
      },
      mainEntityOfPage: `${SITE_URL}/tesla`,
    },
    {
      '@type': 'Vehicle',
      '@id': `${SITE_URL}/tesla#vehicle-model3`,
      name: '테슬라 모델 3 하이랜드 (Tesla Model 3 Highland)',
      brand: {
        '@type': 'Brand',
        name: 'Tesla',
      },
      manufacturer: {
        '@type': 'Organization',
        name: 'Tesla, Inc.',
      },
      model: 'Model 3 Highland',
      vehicleModelDate: '2024-2026',
      vehicleTransmission: '1단 고정 기어 (전기 모터)',
      fuelType: 'https://schema.org/Electric',
      description: '테슬라 모델 3 하이랜드 페이스리프트. FSD 댐퍼 및 전좌석 이중접합 유리 적용, LFP(스탠다드) 및 삼원계 NCMA(롱레인지) 배터리 탑재.',
      additionalProperty: [
        {
          '@type': 'PropertyValue',
          name: 'Battery Chemistry (RWD)',
          value: 'CATL LFP (리튬인산철) 60 kWh',
        },
        {
          '@type': 'PropertyValue',
          name: 'Battery Chemistry (Long Range)',
          value: 'LG에너지솔루션 NCM/NCMA (삼원계) 81.6 kWh',
        },
        {
          '@type': 'PropertyValue',
          name: 'Safety Rating',
          value: 'Euro NCAP 5-Star / NHTSA 5-Star',
        },
        {
          '@type': 'PropertyValue',
          name: 'Thermal Runaway Threshold',
          value: 'LFP > 270°C, NCM ~210°C',
        },
      ],
    },
    {
      '@type': 'Vehicle',
      '@id': `${SITE_URL}/tesla#vehicle-modely`,
      name: '테슬라 모델 Y 주니퍼 / 컴포트 (Tesla Model Y Juniper)',
      brand: {
        '@type': 'Brand',
        name: 'Tesla',
      },
      manufacturer: {
        '@type': 'Organization',
        name: 'Tesla, Inc.',
      },
      model: 'Model Y',
      vehicleModelDate: '2024-2026',
      vehicleTransmission: '1단 고정 기어 (전기 모터)',
      fuelType: 'https://schema.org/Electric',
      description: '테슬라 모델 Y 중형 크로스오버 EV. HW4.0 차세대 오토파일럿 컴퓨터 및 컴포트 서스펜션 기본 적용, RWD LFP 및 롱레인지 AWD NCMA 배터리 탑재.',
      additionalProperty: [
        {
          '@type': 'PropertyValue',
          name: 'Battery Chemistry (RWD)',
          value: 'CATL LFP (리튬인산철) 60 kWh',
        },
        {
          '@type': 'PropertyValue',
          name: 'Battery Chemistry (Long Range AWD)',
          value: 'LG에너지솔루션/파나소닉 NCMA/NCA 81.6 kWh',
        },
        {
          '@type': 'PropertyValue',
          name: 'Safety Rating',
          value: 'Euro NCAP 5-Star (성인 탑승자 97%) / IIHS TSP+',
        },
      ],
    },
    {
      '@type': 'ItemList',
      '@id': `${SITE_URL}/tesla#itemlist`,
      name: '테슬라 모델별 연식 고질병 및 구매 가이드 리스트',
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: '테슬라 모델 3 (2017~2020 초기형 PTC 히터 파괴 회피 및 2024 하이랜드 추천)',
          url: `${SITE_URL}/tesla#heading-model3`,
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: '테슬라 모델 Y (2020~2022 초기형 옥토밸브 히트펌프 결함 및 2025 주니퍼 페이스리프트)',
          url: `${SITE_URL}/tesla#heading-modely`,
        },
      ],
    },
    {
      '@type': 'FAQPage',
      '@id': `${SITE_URL}/tesla#faq`,
      mainEntity: [
        {
          '@type': 'Question',
          name: '테슬라 모델 3 2017~2020년식 초기형을 피해야 하는 이유는?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '히트펌프가 없는 구형 저항식 PTC 히터로 인해 겨울철 전비가 40% 이상 급락하며, 프론트 상단 컨트롤 암 부싱 고무 찢어짐으로 인한 하체 삐걱거림 및 조향 유격 고질병이 빈번합니다.',
          },
        },
        {
          '@type': 'Question',
          name: '테슬라 옥토밸브 히트펌프 결함 증상과 조치 여부는?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '2021~2022년식 초기 히트펌프 모델에서 극저온 주행 시 3웨이/8웨이 냉각수 제어 밸브 고착으로 실내 난방이 먹통되는 리콜이 발생했습니다. 개선된 밸브 부품과 최신 펌웨어(OTA) 적용 여부를 확인해야 합니다.',
          },
        },
        {
          '@type': 'Question',
          name: '테슬라 모델 3 하이랜드(Highland)의 핵심 변경점은?',
          acceptedAnswer: {
            '@type': 'Answer',
            text: '2024년식 하이랜드는 전 좌석 360도 이중접합 차음 유리, 주파수 감응형 쇼크업소버 탑재로 승차감과 풍절음이 획기적으로 개선되었으며 통풍 시트와 후석 8인치 디스플레이가 적용되었습니다.',
          },
        },
      ],
    },
    {
      '@type': 'BreadcrumbList',
      '@id': `${SITE_URL}/tesla#breadcrumb`,
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
          name: '테슬라 구매 가이드',
          item: `${SITE_URL}/tesla`,
        },
      ],
    },
  ],
};

export const metadata: Metadata = {
  title: '테슬라 연식별 결함 및 구매 가이드',
  description: '테슬라 모델 3, 모델 Y 연식별(2017~2026) 히터 파괴, 컨트롤 암, 옥토밸브 히트펌프 결함 분석 및 중고차 구매 가이드',
  keywords: [
    '테슬라 연식별 결함',
    '테슬라 모델3 고질병',
    '테슬라 모델Y 결함',
    '테슬라 히트펌프 결함',
    '옥토밸브 파손',
    '테슬라 컨트롤암',
    '모델3 하이랜드',
    '모델Y 주니퍼',
    '테슬라 중고차 가이드',
  ],
  alternates: {
    canonical: '/tesla',
  },
  openGraph: {
    title: '테슬라 연식별 결함 및 구매 가이드 | Global EV Hub',
    description: '테슬라 모델 3, 모델 Y 연식별(2017~2026) 히터 파괴, 컨트롤 암, 옥토밸브 히트펌프 결함 분석 및 중고차 구매 가이드',
    url: '/tesla',
    siteName: 'Global EV Hub',
    locale: 'ko_KR',
    type: 'article',
    publishedTime: '2026-01-01T00:00:00+09:00',
    modifiedTime: '2026-11-01T00:00:00+09:00',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: '테슬라 연식별 결함 및 구매 가이드',
        type: 'image/png',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: '테슬라 연식별 결함 및 구매 가이드 | Global EV Hub',
    description: '테슬라 모델 3, 모델 Y 연식별(2017~2026) 히터 파괴, 컨트롤 암, 옥토밸브 히트펌프 결함 분석 및 중고차 구매 가이드',
    site: '@GlobalEVHub',
    creator: '@lolollol2379',
    images: ['/og-image.png'],
  },
};

export default function TeslaPage() {
  return (
    <article className="space-y-8 py-6 sm:py-10 max-w-4xl mx-auto">
      <JsonLd data={teslaJsonLd} />
      <BrandComparisonNav currentBrand="tesla" pageTitle="테슬라 구매 가이드" />

      <header className="border-b pb-4 space-y-2">
        <h1 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-slate-900 tracking-tight">
          테슬라 연식별 구매 가이드 (피해야 할 연식)
        </h1>
        <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
          테슬라 모델 3 및 모델 Y의 초기형 PTC 히터 파손, 히트펌프(옥토밸브) 셧다운, 서스펜션 컨트롤 암 삐걱거림 결함 분석 및 중고차 구매 연식 가이드를 제공합니다.
        </p>
      </header>

      {/* 테슬라 연식별 판정 요약 표 (WCAG AA Compliance: table headers, caption, overflow container) */}
      <section aria-labelledby="heading-tesla-summary" className="space-y-3">
        <h2 id="heading-tesla-summary" className="text-xl sm:text-2xl font-bold text-slate-900">
          테슬라 주요 차종 연식별 판정 요약 표
        </h2>
        <div
          tabIndex={0}
          role="region"
          aria-label="가로 스크롤 가능한 테슬라 주요 차종 연식별 판정 요약 표"
          className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
        >
          <table className="w-full min-w-[640px] text-left border-collapse text-xs sm:text-sm" aria-label="테슬라 주요 모델별 주의 및 추천 연식 요약 표">
            <caption className="sr-only">테슬라 모델 3 및 모델 Y 연식별 회피 연식, 주의 연식, 추천 연식, 주요 고질병 및 리콜 출처 요약 표</caption>
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
                  모델 3 (Model 3)
                </th>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-900">
                    2017~2020년식
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-900">
                    2021~2023년식
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-900">
                    2024년식 (하이랜드)
                  </span>
                </td>
                <td className="py-3 px-4 text-slate-700">
                  PTC 히터 단선, 서스펜션 컨트롤 암 침대 소음, 옥토밸브 동파
                </td>
                <td className="py-3 px-4 text-center whitespace-nowrap">
                  <a
                    href="https://www.nhtsa.gov/recalls?vin=5YJ3"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="미국 NHTSA 테슬라 모델 3 공식 리콜 내역 (새 창에서 열림)"
                    className="text-blue-700 hover:text-blue-800 hover:underline font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 rounded inline-flex items-center gap-1 py-0.5"
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
                  모델 Y (Model Y)
                </th>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-red-100 text-red-900">
                    2020~2021년식
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-900">
                    2022~2023년식
                  </span>
                </td>
                <td className="py-3 px-4">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-green-100 text-green-900">
                    2024~2025년식
                  </span>
                </td>
                <td className="py-3 px-4 text-slate-700">
                  1세대 옥토밸브 난방 셧다운, 초기형 하체 극악 승차감, RWD LFP 잔량 오차
                </td>
                <td className="py-3 px-4 text-center whitespace-nowrap">
                  <a
                    href="https://www.car.go.kr"
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="국토교통부 자동차리콜센터 테슬라 모델 Y 리콜 정보 (새 창에서 열림)"
                    className="text-blue-700 hover:text-blue-800 hover:underline font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 rounded inline-flex items-center gap-1 py-0.5"
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
      
      {/* Model 3 Guide */}
      <section className="space-y-4" aria-labelledby="heading-tesla-model3">
        <h2 id="heading-tesla-model3" className="text-2xl sm:text-3xl font-bold text-slate-800">
          모델 3 (Model 3)
        </h2>
        
        <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-xl" role="region" aria-label="테슬라 모델 3 구매 회피 연식 경고">
          <h3 className="text-lg sm:text-xl font-bold text-red-900">
            <span aria-hidden="true">🚫 </span>2017~2020년식: 구매 회피 (AVOID - 절대 피할 것)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li><strong>히터 파괴:</strong> PTC 고전압 히터가 타버려서 겨울에 얼어 죽을 수 있음 (수리비 168만 원 ~ 567만 원).</li>
            <li><strong>컨트롤 암 찌그덕:</strong> 앞바퀴 서스펜션 볼조인트에 물이 들어가 부서지면서 침대 스프링 소리가 남.</li>
            <li><strong>범퍼 물고임:</strong> 비 오는 날 뒷범퍼 아래에 물이 고여 범퍼가 통째로 뜯겨나가는 결함. 히트펌프도 없어서 겨울철 주행거리 반토막.</li>
          </ul>
        </div>

        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-r-xl" role="region" aria-label="테슬라 모델 3 주의 연식 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-amber-900">
            <span aria-hidden="true">⚠️ </span>2021~2023년식: 주의 요망 (CAUTION)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li><strong>히트펌프 사망:</strong> 옥토밸브(히트펌프) 결함으로 한파에 에어컨/히터가 모두 죽는 결함 발생 (수리비 87만 원 ~ 661만 원).</li>
            <li>LFP 배터리 탑재 모델(RWD)은 겨울철 100% 완충을 자주 안 해주면 배터리 계산 오류로 차가 멈출 수 있습니다.</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-r-xl" role="region" aria-label="테슬라 모델 3 안전 구매 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-green-900">
            <span aria-hidden="true">✅ </span>2024년식 (하이랜드): 안심 추천 (BUY SAFE)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>승차감이 극적으로 개선(FSD 댐퍼)되었고, 방음이 엄청나게 좋아졌습니다. 깜빡이 레버가 없어진 것만 적응하면 최고의 선택입니다.</li>
          </ul>
        </div>
      </section>

      {/* Model Y Guide */}
      <section className="space-y-4 pt-6 border-t border-slate-200" aria-labelledby="heading-tesla-modely">
        <h2 id="heading-tesla-modely" className="text-2xl sm:text-3xl font-bold text-slate-800">
          모델 Y (Model Y)
        </h2>

        <div className="bg-red-50 border-l-4 border-red-500 p-4 rounded-r-xl" role="region" aria-label="테슬라 모델 Y 구매 회피 연식 경고">
          <h3 className="text-lg sm:text-xl font-bold text-red-900">
            <span aria-hidden="true">🚫 </span>2020~2021년식: 구매 회피 (AVOID - 초기형 결함 및 승차감 불량)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li><strong>초기형 옥토밸브 동파 파손:</strong> 1세대 히트펌프 밸브 고착으로 혹한기 난방 셧다운 및 컴프레셔 파손 리콜 발생.</li>
            <li><strong>극악의 승차감:</strong> 초기 세팅 서스펜션이 지나치게 단단하여 방지턱 및 노면 요철 통과 시 2열 동승자 멀미 및 차체 잔진동 유발.</li>
            <li><strong>도장 및 단차 누수:</strong> 테일램프 습기 유입 및 트렁크 웨더스트립 조립 불량으로 인한 트렁크 누수 다발.</li>
          </ul>
        </div>

        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-r-xl" role="region" aria-label="테슬라 모델 Y 주의 연식 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-amber-900">
            <span aria-hidden="true">⚠️ </span>2022~2023년식: 주의 요망 (CAUTION - 후륜 LFP 배터리 및 부싱 주의)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li><strong>RWD LFP 배터리 저온 관리:</strong> 중국 기가 상하이산 CATL LFP 셀 탑재 차량은 겨울철 주기적 100% 완충 미진행 시 BMS 셀 편차 오차로 인한 주행 중 멈춤 주의 필요.</li>
            <li><strong>컨트롤 암 부싱 이음:</strong> 서스펜션 어퍼암 볼조인트 방수 패킹 경화로 침대 스프링 삐걱거림 소음 발생 (보증 기간 내 교체 필수).</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4 rounded-r-xl" role="region" aria-label="테슬라 모델 Y 안전 구매 가이드">
          <h3 className="text-lg sm:text-xl font-bold text-green-900">
            <span aria-hidden="true">✅ </span>2024~2025년식: 안심 추천 (BUY SAFE - 컴포트 서스펜션 및 HW4.0 탑재)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-slate-700 space-y-1.5 text-sm sm:text-base leading-relaxed">
            <li>기본 컴포트 서스펜션이 장착되어 승차감이 눈에 띄게 개선되었으며, 차세대 오토파일럿 컴퓨터(HW4.0) 적용으로 카메라 해상도 및 연산 안정성이 강화되었습니다.</li>
          </ul>
        </div>
      </section>

      {/* Contextual CTA Cross-Links to Interactive Intelligence Tools */}
      <section aria-labelledby="heading-tesla-tools" className="pt-8 border-t border-slate-200 space-y-6">
        <div className="space-y-1">
          <h2 id="heading-tesla-tools" className="text-2xl font-bold text-slate-900">
            테슬라 전기차 데이터 인텔리전스 및 진단 도구
          </h2>
          <p className="text-sm text-slate-600">
            모델3·모델Y 결함 심각도, 국토교통부·NHTSA 리콜, 배터리 잔존가치 및 실시간 지자체 보조금을 비교하세요.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            href="/reliability-analytics?brand=tesla"
            prefetch={false}
            aria-label="테슬라 결함 심층 분석 (DSI) 통계 바로가기"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-blue-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
          >
            <h3 className="flex items-center gap-2 text-blue-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📊</span>
              <span>테슬라 결함 심층 분석 (DSI)</span>
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              히트펌프 옥토밸브 파손, 서스펜션 컨트롤 암 찌그덕 등 연식별 DSI 점수와 수리비 통계를 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-blue-700 font-semibold mt-3 group-hover:underline">
              테슬라 결함 통계 보기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>

          <Link
            href="/recall-portal?brand=tesla"
            prefetch={false}
            aria-label="테슬라 VIN 차대번호 및 리콜 조회 바로가기"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-rose-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-600"
          >
            <h3 className="flex items-center gap-2 text-rose-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">🚨</span>
              <span>테슬라 VIN 차대번호 및 리콜 조회</span>
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              차대번호 17자리 프리픽스(5YJ3, LRW 등)로 오토파일럿 ECU, 도어 래치 및 배터리 공급사를 즉시 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-rose-700 font-semibold mt-3 group-hover:underline">
              리콜 및 VIN 조회하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>

          <Link
            href="/depreciation-calculator"
            prefetch={true}
            aria-label="테슬라 감가방어율 및 배터리 수명 계산기 바로가기"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-emerald-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
          >
            <h3 className="flex items-center gap-2 text-emerald-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📉</span>
              <span>테슬라 감가방어율 및 배터리 수명(SoH) 계산기</span>
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              LFP 및 삼원계(NCM) 배터리 열화율 곡선과 5년 보유 기간 총 유지비(TCO)를 정밀 시뮬레이션합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-semibold mt-3 group-hover:underline">
              감가율 계산하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>

          <Link
            href="/subsidy-tracker"
            prefetch={true}
            aria-label="모델Y RWD 실시간 보조금 소진율 조회 바로가기"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-amber-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-600"
          >
            <h3 className="flex items-center gap-2 text-amber-800 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">⚡</span>
              <span>모델Y RWD 실시간 보조금 소진율</span>
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              지자체별 승용 전기차 쿼터 마감 현황과 가격 상한제 기준 테슬라 실구매 체감가를 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-amber-800 font-semibold mt-3 group-hover:underline">
              보조금 소진율 확인하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>
        </div>
      </section>

      {/* Brand Comparison Cross Navigation */}
      <OtherBrandsCrossNav currentBrand="tesla" />
    </article>
  );
}
