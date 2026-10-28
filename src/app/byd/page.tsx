import type { Metadata } from 'next';
import Link from 'next/link';

export const dynamic = 'force-static';

export const metadata: Metadata = {
  title: 'BYD 전기차 연식별 결함 및 구매 가이드 | Global EV Hub',
  description: 'BYD 돌핀, 시라이언 7, 씰, 아토 3 연식별(2021~2026) 에어컨 백색가루, 하체 부식, 조향장치 결함 및 구매 가이드',
  openGraph: {
    title: 'BYD 전기차 연식별 결함 및 구매 가이드 | Global EV Hub',
    description: 'BYD 돌핀, 시라이언 7, 씰, 아토 3 연식별(2021~2026) 에어컨 백색가루, 하체 부식, 조향장치 결함 및 구매 가이드',
    siteName: 'Global EV Hub',
    locale: 'ko_KR',
    type: 'website',
  },
};

export default function BydPage() {
  return (
    <div className="space-y-8 py-10 max-w-4xl mx-auto">
      <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold border-b pb-4">BYD 연식별 구매 가이드 (피해야 할 연식)</h1>
      
      <section className="space-y-4" aria-labelledby="heading-byd-dolphin">
        <h2 id="heading-byd-dolphin" className="text-3xl font-semibold text-gray-800">돌핀 (Dolphin)</h2>
        
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4" role="region" aria-label="돌핀 주의 연식 가이드">
          <h3 className="text-xl font-bold text-amber-900">⚠️ 2021~2023년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>에어컨 하얀 가루 (Al(OH)3):</strong> 에어컨 에바코어 코팅 불량으로 인해 호흡기에 치명적인 하얀 알루미늄 가루가 실내로 뿜어져 나오는 심각한 결함 발생.</li>
            <li><strong>조향장치 결함:</strong> 23년식에서 핸들 조향장치(CEPS) 컨트롤러 기판 마찰로 인한 파워스티어링 상실 위험 (대규모 리콜 진행됨).</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4" role="region" aria-label="돌핀 안전 구매 가이드">
          <h3 className="text-xl font-bold text-green-900">✅ 2024~2025년식: BUY SAFE (적극 추천)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>에바코어 코팅이 개선되었고 새로운 후륜 멀티링크 서스펜션이 적용되어 타이어 편마모와 승차감이 대폭 개선되었습니다. 배터리 교체 비용도 전 세계 최저 수준(약 900만 원 선)으로 유지비가 매우 저렴합니다.</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8" aria-labelledby="heading-byd-sealion">
        <h2 id="heading-byd-sealion" className="text-3xl font-semibold text-gray-800">시라이언 07 (Sealion 07)</h2>
        
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4" role="region" aria-label="시라이언 07 주의 연식 가이드">
          <h3 className="text-xl font-bold text-amber-900">⚠️ 2024년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>12-in-1 모터 통짜 수리비 폭탄:</strong> 모터, 인버터, 충전기 등이 12-in-1으로 통합되어 있어 부품 하나만 고장 나도 전체 모듈을 통째로 교체해야 함 (보증 수리 외 비용 약 600만 원 발생).</li>
            <li><strong>CTB (Cell-to-Body) 배터리 파손 위험:</strong> 배터리 케이스가 차량 하부 바닥과 일체형이라서 주행 중 돌을 밟아 하부가 5mm만 찌그러져도 배터리 전체(약 1,400만 원)를 통교체해야 하는 치명적 수리 지옥 리스크.</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4" role="region" aria-label="시라이언 07 안전 구매 가이드">
          <h3 className="text-xl font-bold text-green-900">✅ 2025년식: BUY SAFE (추천)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>루프 라이다 세정 노즐 결함 개선 및 초기 하체 세팅이 수정되었습니다. 단, CTB 통짜 배터리의 구조적 한계(하부 긁힘 시 전손 위기)는 25년식도 동일하므로 반드시 하부 코팅이나 주의 운전이 필요합니다.</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8" aria-labelledby="heading-byd-seal">
        <h2 id="heading-byd-seal" className="text-3xl font-semibold text-gray-800">씰 (Seal)</h2>
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4" role="region" aria-label="씰 주의 연식 가이드">
          <h3 className="text-xl font-bold text-amber-900">⚠️ 2022~2023년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>LFP 배터리 겨울철 셧다운(25%에서 갑자기 0%로 추락) 및 하체 나사 부식 발생.</li>
          </ul>
        </div>
        <div className="bg-green-50 border-l-4 border-green-500 p-4" role="region" aria-label="씰 안전 구매 가이드">
          <h3 className="text-xl font-bold text-green-900">✅ 2024년식: BUY SAFE (적극 추천)</h3>
        </div>
      </section>

      <section className="space-y-4 mt-8" aria-labelledby="heading-byd-atto3">
        <h2 id="heading-byd-atto3" className="text-3xl font-semibold text-gray-800">아토 3 (Atto 3)</h2>
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4" role="region" aria-label="아토 3 주의 연식 가이드">
          <h3 className="text-xl font-bold text-amber-900">⚠️ 2022~2024년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>초기형 에어컨 곰팡이 냄새 고질병 및 앞바퀴 털림 증상. 24년식에 일부 개선되었으나 여전히 앞 서스펜션 세팅이 너무 무릅니다.</li>
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
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-blue-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <div className="flex items-center gap-2 text-blue-600 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📊</span>
              <span>BYD DSI 결함 통계 및 수리비</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              12-in-1 모터 통교체 수리비 및 CTB 하부 찍힘 위험 등 BYD 실차주 고질병 데이터를 분석합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-blue-600 font-semibold mt-3 group-hover:underline">
              BYD 결함 통계 보기 &rarr;
            </span>
          </Link>

          <Link
            href="/recall-portal?brand=byd"
            prefetch={false}
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-rose-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500"
          >
            <div className="flex items-center gap-2 text-rose-600 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">🚨</span>
              <span>BYD 공식 리콜 & 배터리 정보</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              돌핀 스티어링 리콜 내역, 블레이드 LFP 셀 제조사(FinDreams) 및 VIN 차대번호 조회를 제공합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-rose-600 font-semibold mt-3 group-hover:underline">
              리콜 및 배터리 확인하기 &rarr;
            </span>
          </Link>

          <Link
            href="/depreciation-calculator"
            prefetch={true}
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-emerald-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          >
            <div className="flex items-center gap-2 text-emerald-700 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📉</span>
              <span>LFP 배터리 감가 & 잔존가치 계산기</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              중국산 LFP 배터리의 국내 중고차 시장 감가방어율과 5년 보유 TCO 시뮬레이션을 계산합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-emerald-700 font-semibold mt-3 group-hover:underline">
              감가율 계산하기 &rarr;
            </span>
          </Link>

          <Link
            href="/subsidy-tracker"
            prefetch={true}
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-amber-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
          >
            <div className="flex items-center gap-2 text-amber-800 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">⚡</span>
              <span>BYD 모델별 지자체 보조금 현황</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              배터리 에너지 밀도 및 재활용 계수에 따른 환경부 보조금 차등 지급액과 잔여 쿼터를 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-amber-800 font-semibold mt-3 group-hover:underline">
              보조금 소진율 확인하기 &rarr;
            </span>
          </Link>
        </div>
      </section>
    </div>
  );
}
