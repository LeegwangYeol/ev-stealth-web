import type { Metadata } from 'next';
import Link from 'next/link';
import JsonLd from '@/components/JsonLd';

export const dynamic = 'force-static';
export const revalidate = false;

const teslaJsonLd = {
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "테슬라 연식별 결함 및 구매 가이드",
  "description": "테슬라 모델 3, 모델 Y 연식별(2017~2026) 히터 파괴, 컨트롤 암, 옥토밸브 히트펌프 결함 분석 및 중고차 구매 가이드",
  "url": "https://ev-stealth-web.vercel.app/tesla",
  "inLanguage": "ko-KR",
  "datePublished": "2026-01-01T00:00:00+09:00",
  "dateModified": "2026-11-01T00:00:00+09:00",
  "author": {
    "@type": "Organization",
    "name": "Global EV Hub",
    "url": "https://ev-stealth-web.vercel.app",
  },
  "publisher": {
    "@type": "Organization",
    "name": "Global EV Hub",
    "logo": {
      "@type": "ImageObject",
      "url": "https://ev-stealth-web.vercel.app/favicon.ico",
    },
  },
  "mainEntityOfPage": "https://ev-stealth-web.vercel.app/tesla",
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
  },
  twitter: {
    card: 'summary_large_image',
    title: '테슬라 연식별 결함 및 구매 가이드 | Global EV Hub',
    description: '테슬라 모델 3, 모델 Y 연식별(2017~2026) 히터 파괴, 컨트롤 암, 옥토밸브 히트펌프 결함 분석 및 중고차 구매 가이드',
  },
};

export default function TeslaPage() {
  return (
    <article className="space-y-8 py-6 sm:py-10 max-w-4xl mx-auto">
      <JsonLd data={teslaJsonLd} />
      <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold border-b pb-4 text-slate-900">
        테슬라 연식별 구매 가이드 (피해야 할 연식)
      </h1>
      
      {/* Model 3 Guide */}
      <section className="space-y-4" aria-labelledby="heading-tesla-model3">
        <h2 id="heading-tesla-model3" className="text-3xl font-semibold text-gray-800">
          모델 3 (Model 3)
        </h2>
        
        <div className="bg-red-50 border-l-4 border-red-500 p-4" role="region" aria-label="테슬라 모델 3 구매 회피 연식 경고">
          <h3 className="text-xl font-bold text-red-700">
            <span aria-hidden="true">🚫 </span>2017~2020년식: 구매 회피 (AVOID - 절대 피할 것)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>히터 파괴:</strong> PTC 고전압 히터가 타버려서 겨울에 얼어 죽을 수 있음 (수리비 168만 원 ~ 567만 원).</li>
            <li><strong>컨트롤 암 찌그덕:</strong> 앞바퀴 서스펜션 볼조인트에 물이 들어가 부서지면서 침대 스프링 소리가 남.</li>
            <li><strong>범퍼 물고임:</strong> 비 오는 날 뒷범퍼 아래에 물이 고여 범퍼가 통째로 뜯겨나가는 결함. 히트펌프도 없어서 겨울철 주행거리 반토막.</li>
          </ul>
        </div>

        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4" role="region" aria-label="테슬라 모델 3 주의 연식 가이드">
          <h3 className="text-xl font-bold text-amber-900">
            <span aria-hidden="true">⚠️ </span>2021~2023년식: 주의 요망 (CAUTION)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>히트펌프 사망:</strong> 옥토밸브(히트펌프) 결함으로 한파에 에어컨/히터가 모두 죽는 결함 발생 (수리비 87만 원 ~ 661만 원).</li>
            <li>LFP 배터리 탑재 모델(RWD)은 겨울철 100% 완충을 자주 안 해주면 배터리 계산 오류로 차가 멈출 수 있습니다.</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4" role="region" aria-label="테슬라 모델 3 안전 구매 가이드">
          <h3 className="text-xl font-bold text-green-900">
            <span aria-hidden="true">✅ </span>2024년식 (하이랜드): 안심 추천 (BUY SAFE)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>승차감이 극적으로 개선(FSD 댐퍼)되었고, 방음이 엄청나게 좋아졌습니다. 깜빡이 레버가 없어진 것만 적응하면 최고의 선택입니다.</li>
          </ul>
        </div>
      </section>

      {/* Model Y Guide */}
      <section className="space-y-4 pt-6 border-t border-slate-200" aria-labelledby="heading-tesla-modely">
        <h2 id="heading-tesla-modely" className="text-3xl font-semibold text-gray-800">
          모델 Y (Model Y)
        </h2>

        <div className="bg-red-50 border-l-4 border-red-500 p-4" role="region" aria-label="테슬라 모델 Y 구매 회피 연식 경고">
          <h3 className="text-xl font-bold text-red-700">
            <span aria-hidden="true">🚫 </span>2020~2021년식: 구매 회피 (AVOID - 초기형 결함 및 승차감 불량)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>초기형 옥토밸브 동파 파손:</strong> 1세대 히트펌프 밸브 고착으로 혹한기 난방 셧다운 및 컴프레셔 파손 리콜 발생.</li>
            <li><strong>극악의 승차감:</strong> 초기 세팅 서스펜션이 지나치게 단단하여 방지턱 및 노면 요철 통과 시 2열 동승자 멀미 및 차체 잔진동 유발.</li>
            <li><strong>도장 및 단차 누수:</strong> 테일램프 습기 유입 및 트렁크 웨더스트립 조립 불량으로 인한 트렁크 누수 다발.</li>
          </ul>
        </div>

        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4" role="region" aria-label="테슬라 모델 Y 주의 연식 가이드">
          <h3 className="text-xl font-bold text-amber-900">
            <span aria-hidden="true">⚠️ </span>2022~2023년식: 주의 요망 (CAUTION - 후륜 LFP 배터리 및 부싱 주의)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>RWD LFP 배터리 저온 관리:</strong> 중국 기가 상하이산 CATL LFP 셀 탑재 차량은 겨울철 주기적 100% 완충 미진행 시 BMS 셀 편차 오차로 인한 주행 중 멈춤 주의 필요.</li>
            <li><strong>컨트롤 암 부싱 이음:</strong> 서스펜션 어퍼암 볼조인트 방수 패킹 경화로 침대 스프링 삐걱거림 소음 발생 (보증 기간 내 교체 필수).</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4" role="region" aria-label="테슬라 모델 Y 안전 구매 가이드">
          <h3 className="text-xl font-bold text-green-900">
            <span aria-hidden="true">✅ </span>2024~2025년식: 안심 추천 (BUY SAFE - 컴포트 서스펜션 및 HW4.0 탑재)
          </h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
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
            <div className="flex items-center gap-2 text-blue-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📊</span>
              <span>테슬라 결함 심층 분석 (DSI)</span>
            </div>
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
            <div className="flex items-center gap-2 text-rose-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">🚨</span>
              <span>테슬라 VIN 차대번호 및 리콜 조회</span>
            </div>
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
            <div className="flex items-center gap-2 text-emerald-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📉</span>
              <span>테슬라 감가방어율 및 배터리 수명(SoH) 계산기</span>
            </div>
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
            <div className="flex items-center gap-2 text-amber-800 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">⚡</span>
              <span>모델Y RWD 실시간 보조금 소진율</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              지자체별 승용 전기차 쿼터 마감 현황과 가격 상한제 기준 테슬라 실구매 체감가를 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-amber-800 font-semibold mt-3 group-hover:underline">
              보조금 소진율 확인하기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>
        </div>
      </section>
    </article>
  );
}
