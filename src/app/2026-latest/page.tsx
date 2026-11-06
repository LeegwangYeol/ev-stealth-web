import type { Metadata } from 'next';
import Link from 'next/link';
import JsonLd from '@/components/JsonLd';
import BrandComparisonNav, { OtherBrandsCrossNav } from '@/components/BrandComparisonNav';

export const dynamic = 'force-static';
export const revalidate = false;

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || 'https://ev-stealth-web.vercel.app').replace(/\/+$/, '');

const latest2026JsonLd = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Article',
      '@id': `${SITE_URL}/2026-latest#article`,
      headline: '2026년식 KDM(국내 내수용) EV 초기 품질 리포트',
      description: '올해 출고된 2026년식 최신 전기차(아이오닉5, EV3, 아이오닉9, 모델Y, 시라이언7)의 한국 차주 실제 평가와 초기 결함 분석',
      url: `${SITE_URL}/2026-latest`,
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
      mainEntityOfPage: `${SITE_URL}/2026-latest`,
    },
    {
      '@type': 'BreadcrumbList',
      '@id': `${SITE_URL}/2026-latest#breadcrumb`,
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
          name: '2026 최신 결함',
          item: `${SITE_URL}/2026-latest`,
        },
      ],
    },
  ],
};

export const metadata: Metadata = {
  title: '2026년식 KDM EV 초기 품질 리포트',
  description: '올해 출고된 2026년식 최신 전기차(아이오닉5, EV3, 아이오닉9, 모델Y, 시라이언7)의 한국 차주 실제 평가와 초기 결함을 100% 원문 출처와 함께 분석했습니다.',
  keywords: [
    '2026 전기차 결함',
    'EV3 초기결함',
    '2026 아이오닉5',
    '2026 모델Y 주니퍼',
    '시라이언7 부식',
    '아이오닉9 결함',
    'KDM 전기차 품질',
    '2026 전기차 리포트',
  ],
  alternates: {
    canonical: '/2026-latest',
  },
  openGraph: {
    title: '2026년식 KDM EV 초기 품질 리포트 | Global EV Hub',
    description: '올해 출고된 2026년식 최신 전기차(아이오닉5, EV3, 아이오닉9, 모델Y, 시라이언7)의 한국 차주 실제 평가와 초기 결함을 100% 원문 출처와 함께 분석했습니다.',
    url: '/2026-latest',
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
        alt: '2026년식 KDM EV 초기 품질 리포트',
        type: 'image/png',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: '2026년식 KDM EV 초기 품질 리포트 | Global EV Hub',
    description: '올해 출고된 2026년식 최신 전기차(아이오닉5, EV3, 아이오닉9, 모델Y, 시라이언7)의 한국 차주 실제 평가와 초기 결함을 100% 원문 출처와 함께 분석했습니다.',
    site: '@GlobalEVHub',
    creator: '@lolollol2379',
    images: ['/og-image.png'],
  },
};

export default function Latest2026Page() {
  return (
    <article className="space-y-8 py-6 sm:py-10 max-w-4xl mx-auto">
      <JsonLd data={latest2026JsonLd} />
      <BrandComparisonNav currentBrand="2026-latest" pageTitle="2026 최신 결함 리포트" />
      
      <header className="border-b pb-6">
        <h1 className="text-2xl sm:text-3xl md:text-4xl font-extrabold text-slate-900 mb-3 tracking-tight">
          2026년식 KDM(국내 내수용) EV 초기 품질 리포트
        </h1>
        <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
          올해 막 출고된 2026년식 최신 전기차(아이오닉 5 페이스리프트, EV3, 아이오닉 9, 테슬라 모델Y, BYD 시라이언 7)의 한국 차주 실제 평가와 초기 결함을 100% 원문 출처(보배드림, 레딧 등)와 함께 분석했습니다.
        </p>
      </header>

      {/* 2026 최신 결함 긴급 주의보 콜아웃 (WCAG AAA > 8.5:1 대비: text-amber-900 & text-slate-700 on bg-yellow-50) */}
      <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 rounded-r-xl" role="region" aria-labelledby="heading-alert-2026">
        <h2 id="heading-alert-2026" className="text-lg sm:text-xl font-bold text-amber-900 flex items-center gap-2">
          <span aria-hidden="true">⚠️</span> 2026년식 신차 초기 결함 긴급 주의보 (CAUTION)
        </h2>
        <p className="text-sm font-medium text-slate-700 mt-2 leading-relaxed">
          올해 출시된 주요 국내 출시(KDM) 전기차에서 전자제어(MCU/ICCU) 통신 장애 및 조기 부식, 동력 상실 사례가 보고되고 있습니다. 이상 경고등 점등 시 즉시 안전지대로 대피하고 제조사 무상수리 및 리콜 조치를 받으시기 바랍니다.
        </p>
      </div>

      {/* 1. Kia EV3 */}
      <section aria-labelledby="heading-ev3-2026" className="space-y-4">
        <h2 id="heading-ev3-2026" className="text-2xl sm:text-3xl font-bold text-slate-800">
          1. 기아 EV3 (Kia EV3 2026)
        </h2>
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-4">
          <div className="bg-red-50 border-l-4 border-red-500 p-3.5 rounded-r-xl" role="region" aria-label="기아 EV3 초기 결함 경고">
            <h3 className="text-base sm:text-lg font-bold text-red-900">
              <span aria-hidden="true">🚫 </span>신차 초기 결함: 주행 중 동력 상실 및 시동 꺼짐 리콜 (AVOID)
            </h3>
          </div>
          <ul className="list-disc pl-6 space-y-2 text-slate-700 text-sm sm:text-base leading-relaxed">
            <li>
              <strong>초기 결함:</strong> 주행 중 계기판에 &quot;전기차 시스템을 점검하십시오&quot; 문구가 뜨며 시동이 꺼지고 동력이 차단되는 결함(MCU 통신 오류). 한국교통안전공단 무상수리 및 리콜 실시.
            </li>
            <li>
              <strong>차주 리얼 후기:</strong> &quot;도심 주행 중 갑작스러운 동력 상실로 뒤차와 추돌할 뻔해 생명의 위협을 느꼈다.&quot;
            </li>
            <li>
              <strong>출처:</strong> <a href="https://m.bobaedream.co.kr/board/bbs_view/national/2328953/2/1" target="_blank" rel="noopener noreferrer" aria-label="기아 EV3 보배드림 커뮤니티 결함 원문 (새 창에서 열림)" className="text-blue-700 hover:text-blue-800 hover:underline focus-visible:ring-2 focus-visible:ring-blue-600 rounded outline-none inline-block py-0.5">보배드림 커뮤니티 원문<span className="sr-only"> (새 창에서 열림)</span></a> | <a href="https://www.autodaily.co.kr/news/articleView.html?idxno=535684" target="_blank" rel="noopener noreferrer" aria-label="기아 EV3 오토데일리 리콜 보도 기사 (새 창에서 열림)" className="text-blue-700 hover:text-blue-800 hover:underline focus-visible:ring-2 focus-visible:ring-blue-600 rounded outline-none inline-block py-0.5">오토데일리 기사<span className="sr-only"> (새 창에서 열림)</span></a>
            </li>
          </ul>
        </div>
      </section>

      {/* 2. Ioniq 5 PE */}
      <section aria-labelledby="heading-ioniq5-2026" className="space-y-4">
        <h2 id="heading-ioniq5-2026" className="text-2xl sm:text-3xl font-bold text-slate-800">
          2. 더 뉴 아이오닉 5 페이스리프트 (Ioniq 5 PE 2026)
        </h2>
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-4">
          <div className="bg-yellow-50 border-l-4 border-yellow-500 p-3.5 rounded-r-xl" role="region" aria-label="아이오닉 5 페이스리프트 주의 요망">
            <h3 className="text-base sm:text-lg font-bold text-amber-900">
              <span aria-hidden="true">⚠️ </span>초기 결함 주의: 페이스리프트 후에도 여전한 ICCU 고장 및 출력 제한 (CAUTION)
            </h3>
          </div>
          <ul className="list-disc pl-6 space-y-2 text-slate-700 text-sm sm:text-base leading-relaxed">
            <li>
              <strong>초기 결함:</strong> 이전 연식의 고질병인 ICCU(통합충전제어장치) 고장으로 주행 중 거북이 모드(출력 제한) 발생 및 완속/급속 충전 불능 상태 돌입. 신규 ccNC 인포테인먼트 무선 카플레이 멈춤 버그.
            </li>
            <li>
              <strong>차주 리얼 후기:</strong> &quot;페이스리프트 신차임에도 이전 모델의 ICCU 문제가 터졌다. 고속 주행 중 출력 저하로 불안감이 큼.&quot;
            </li>
            <li>
              <strong>출처:</strong> <a href="https://www.reddit.com/r/Ioniq5/comments/1ibf63c/800_miles_in_my_2025_ioniq_5_officially_has_a/" target="_blank" rel="noopener noreferrer" aria-label="더 뉴 아이오닉 5 페이스리프트 레딧 차주 ICCU 고장 인증글 (새 창에서 열림)" className="text-blue-700 hover:text-blue-800 hover:underline focus-visible:ring-2 focus-visible:ring-blue-600 rounded outline-none inline-block py-0.5">레딧 차주 인증<span className="sr-only"> (새 창에서 열림)</span></a> | <a href="https://m.bobaedream.co.kr/board/bbs_view/national/2317279" target="_blank" rel="noopener noreferrer" aria-label="더 뉴 아이오닉 5 보배드림 출력저하 후기 (새 창에서 열림)" className="text-blue-700 hover:text-blue-800 hover:underline focus-visible:ring-2 focus-visible:ring-blue-600 rounded outline-none inline-block py-0.5">보배드림 출력저하 후기<span className="sr-only"> (새 창에서 열림)</span></a>
            </li>
          </ul>
        </div>
      </section>

      {/* 3. Tesla Model Y Juniper */}
      <section aria-labelledby="heading-modely-2026" className="space-y-4">
        <h2 id="heading-modely-2026" className="text-2xl sm:text-3xl font-bold text-slate-800">
          3. 테슬라 모델 Y (Tesla Model Y 2026 주니퍼)
        </h2>
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-4">
          <div className="bg-yellow-50 border-l-4 border-yellow-500 p-3.5 rounded-r-xl" role="region" aria-label="테슬라 모델 Y 주니퍼 주의 요망">
            <h3 className="text-base sm:text-lg font-bold text-amber-900">
              <span aria-hidden="true">⚠️ </span>초기 결함 주의: 동절기 플러시 도어 동결 및 컨트롤 암 소음 (CAUTION)
            </h3>
          </div>
          <ul className="list-disc pl-6 space-y-2 text-slate-700 text-sm sm:text-base leading-relaxed">
            <li>
              <strong>초기 결함:</strong> 동절기 12V 저전압 배터리 전력 부족 시 플러시 도어 핸들이 얼거나 래치가 열리지 않아 탑승 불가. 컨트롤 암 부싱 조기 마모로 방지턱 통과 시 덜컹거림 찌걱 소음 발생.
            </li>
            <li>
              <strong>차주 리얼 후기:</strong> &quot;기가 상하이 생산이라 단차는 나아졌지만, 혹한기 아침에 문이 안 열려서 출근에 큰 차질을 빚었다.&quot;
            </li>
            <li>
              <strong>출처:</strong> <a href="https://www.bobaedream.co.kr/view?code=cnews&No=872" target="_blank" rel="noopener noreferrer" aria-label="테슬라 모델 Y 주니퍼 보배드림 문 열림 결함 보도 (새 창에서 열림)" className="text-blue-700 hover:text-blue-800 hover:underline focus-visible:ring-2 focus-visible:ring-blue-600 rounded outline-none inline-block py-0.5">보배드림 문 열림 결함 보도<span className="sr-only"> (새 창에서 열림)</span></a> | <a href="https://m.bobaedream.co.kr/board/bbs_view/best/927611/2/2?cmt=1" target="_blank" rel="noopener noreferrer" aria-label="테슬라 모델 Y 주니퍼 보배드림 하부 소음 후기 (새 창에서 열림)" className="text-blue-700 hover:text-blue-800 hover:underline focus-visible:ring-2 focus-visible:ring-blue-600 rounded outline-none inline-block py-0.5">하부 소음 후기<span className="sr-only"> (새 창에서 열림)</span></a>
            </li>
          </ul>
        </div>
      </section>

      {/* 4. BYD Sealion 7 */}
      <section aria-labelledby="heading-sealion7-2026" className="space-y-4">
        <h2 id="heading-sealion7-2026" className="text-2xl sm:text-3xl font-bold text-slate-800">
          4. BYD 시라이언 7 (BYD Sealion 7 2026)
        </h2>
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-4">
          <div className="bg-yellow-50 border-l-4 border-yellow-500 p-3.5 rounded-r-xl" role="region" aria-label="BYD 시라이언 7 주의 요망">
            <h3 className="text-base sm:text-lg font-bold text-amber-900">
              <span aria-hidden="true">⚠️ </span>초기 결함 주의: 하체 서브프레임 조기 부식 및 충전기 통신 에러 (CAUTION)
            </h3>
          </div>
          <ul className="list-disc pl-6 space-y-2 text-slate-700 text-sm sm:text-base leading-relaxed">
            <li>
              <strong>초기 결함:</strong> 섀시 하부 서브프레임 접합부 및 휠 하우스 안쪽 용접 부위 조기 부식(녹) 현상 발견. DiLink 인포테인먼트의 어색한 한글 번역 및 공공 급속 충전기(E-pit 등) 충전 타임아웃 오류.
            </li>
            <li>
              <strong>차주 리얼 후기:</strong> &quot;가격은 매력적이나 하체 방청 수준이 엉망이라 겨울 염화칼슘 도로를 타면 금방 썩을 것 같다. 내비 번역체도 거슬린다.&quot;
            </li>
            <li>
              <strong>출처:</strong> <a href="https://www.bobaedream.co.kr/view?code=best&No=888548" target="_blank" rel="noopener noreferrer" aria-label="BYD 시라이언 7 보배드림 조기 녹 부식 현상 제보 (새 창에서 열림)" className="text-blue-700 hover:text-blue-800 hover:underline focus-visible:ring-2 focus-visible:ring-blue-600 rounded outline-none inline-block py-0.5">보배드림 조기 녹(부식) 현상<span className="sr-only"> (새 창에서 열림)</span></a> | <a href="https://m.bobaedream.co.kr/board/bbs_view/cnews/595" target="_blank" rel="noopener noreferrer" aria-label="BYD 시라이언 7 보배드림 충전기 호환성 문제 제보 (새 창에서 열림)" className="text-blue-700 hover:text-blue-800 hover:underline focus-visible:ring-2 focus-visible:ring-blue-600 rounded outline-none inline-block py-0.5">충전기 호환성 문제<span className="sr-only"> (새 창에서 열림)</span></a>
            </li>
          </ul>
        </div>
      </section>
      
      {/* 5. Hyundai Ioniq 9 */}
      <section aria-labelledby="heading-ioniq9-2026" className="space-y-4">
        <h2 id="heading-ioniq9-2026" className="text-2xl sm:text-3xl font-bold text-slate-800">
          5. 현대 아이오닉 9 (Hyundai Ioniq 9 2026)
        </h2>
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-slate-200 space-y-4">
          <div className="bg-red-50 border-l-4 border-red-500 p-3.5 rounded-r-xl" role="region" aria-label="아이오닉 9 신차 치명적 결함 경고">
            <h3 className="text-base sm:text-lg font-bold text-red-900">
              <span aria-hidden="true">🚫 </span>신차 치명적 결함: 출고 즉시 고전압 배터리팩 소손 판정 (AVOID)
            </h3>
          </div>
          <ul className="list-disc pl-6 space-y-2 text-slate-700 text-sm sm:text-base leading-relaxed">
            <li>
              <strong>초기 결함:</strong> 주행거리 389km 만에 배터리 제어 시스템 경고등 점등 및 고전압 배터리팩 내부 PCB 기판 소손 판정으로 배터리 분해 수리. 2열 도어와 쿼터 글라스 몰딩 간격 유격 불량.
            </li>
            <li>
              <strong>차주 리얼 후기:</strong> &quot;8,000만 원짜리 차를 뽑자마자 고전압 배터리를 통째로 뜯어내야 한다고 해서 환불을 요구 중이다.&quot;
            </li>
            <li>
              <strong>출처:</strong> <a href="https://m.bobaedream.co.kr/board/bbs_view/best/1008916/2/8?cmt=1" target="_blank" rel="noopener noreferrer" aria-label="현대 아이오닉 9 보배드림 배터리 결함 제보 (새 창에서 열림)" className="text-blue-700 hover:text-blue-800 hover:underline focus-visible:ring-2 focus-visible:ring-blue-600 rounded outline-none inline-block py-0.5">보배드림 아이오닉9 배터리 결함<span className="sr-only"> (새 창에서 열림)</span></a>
            </li>
          </ul>
        </div>
      </section>

      {/* 연계 서비스 바로가기 (Cross-Tool CTAs) */}
      <section aria-labelledby="heading-cross-tools" className="pt-8 border-t border-slate-200 space-y-6">
        <div className="space-y-1">
          <h2 id="heading-cross-tools" className="text-2xl font-bold text-slate-900">
            2026 최신 전기차 데이터 인텔리전스 및 진단 도구
          </h2>
          <p className="text-sm text-slate-600">
            신차 출고 전 결함 심층 분석, 국토교통부 공식 리콜, 5년 감가 시뮬레이션 및 실시간 지자체 보조금을 비교하세요.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Link
            href="/reliability-analytics"
            prefetch={false}
            aria-label="실차주 결함 통계 및 고질병 랭킹 바로가기"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-blue-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
          >
            <h3 className="flex items-center gap-2 text-blue-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📊</span>
              <span>실차주 결함 통계 및 고질병 랭킹 (DSI)</span>
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              현대·기아·테슬라 등 브랜드별 결함 심각도 지수(DSI), 다발 결함 부품 랭킹 및 예상 수리비를 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-blue-700 font-semibold mt-3 group-hover:underline">
              결함 통계 조회하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>

          <Link
            href="/recall-portal"
            prefetch={false}
            aria-label="공식 리콜 및 배터리 제조사 조회 바로가기"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-rose-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-600"
          >
            <h3 className="flex items-center gap-2 text-rose-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">🚨</span>
              <span>공식 리콜 및 배터리 제조사 조회</span>
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
            aria-label="전기차 감가율 및 배터리 수명 시뮬레이터 바로가기"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-emerald-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
          >
            <h3 className="flex items-center gap-2 text-emerald-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📉</span>
              <span>전기차 감가율 및 배터리 수명 시뮬레이터</span>
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
            aria-label="지자체 보조금 실시간 소진율 추적기 바로가기"
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-amber-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-600"
          >
            <h3 className="flex items-center gap-2 text-amber-800 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">⚡</span>
              <span>지자체 보조금 실시간 소진율 추적기</span>
            </h3>
            <p className="text-xs text-slate-600 leading-relaxed">
              환경부 및 17개 광역시도별 보조금 소진율, 마감 임박 경보, 5,500만 원 상한제 차등 지급액을 실시간 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-amber-800 font-semibold mt-3 group-hover:underline">
              보조금 소진율 확인하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>
        </div>
      </section>

      {/* Brand Comparison Cross Navigation */}
      <OtherBrandsCrossNav currentBrand="2026-latest" />
    </article>
  );
}
