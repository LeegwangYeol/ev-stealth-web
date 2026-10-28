import type { Metadata } from 'next';
import Link from 'next/link';

export const dynamic = 'force-static';

export const metadata: Metadata = {
  title: '글로벌 EV 브랜드 연식별 결함 및 구매 가이드 | Global EV Hub',
  description: '폭스바겐 ID.4, 쉐보레 볼트 EV, 폴스타 2, 벤츠 EQE/EQS 등 유럽/북미 전기차 연식별 결함 및 중고차 구매 가이드',
  openGraph: {
    title: '글로벌 EV 브랜드 연식별 결함 및 구매 가이드 | Global EV Hub',
    description: '폭스바겐 ID.4, 쉐보레 볼트 EV, 폴스타 2, 벤츠 EQE/EQS 등 유럽/북미 전기차 연식별 결함 및 중고차 구매 가이드',
    siteName: 'Global EV Hub',
    locale: 'ko_KR',
    type: 'website',
  },
};

export default function GlobalEvPage() {
  return (
    <div className="space-y-8 py-10 max-w-4xl mx-auto">
      <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold border-b pb-4">유럽 및 북미 EV 연식별 가이드 (폭스바겐, 리비안, 폴스타 등)</h1>
      
      <section className="space-y-4" aria-labelledby="heading-bolt-ev">
        <h2 id="heading-bolt-ev" className="text-3xl font-semibold text-gray-800">쉐보레 볼트 EV / EUV</h2>
        <div className="bg-red-50 border-l-4 border-red-500 p-4" role="region" aria-label="쉐보레 볼트 EV 구매 회피 연식 경고">
          <h3 className="text-xl font-bold text-red-700">🚫 2017~2022년식: AVOID (절대 피할 것 - 배터리 화재)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>LG화학 파우치셀 화재 리콜:</strong> 분리막 접힘과 양극 탭 찢어짐이라는 2가지 희귀 제조 결함이 겹치면서 대형 배터리 화재 연쇄 발생.</li>
            <li><strong>조치:</strong> 중고차 구매 시 &apos;배터리 팩이 완전히 새것으로 교체된 차량&apos;이 아니면 절대 구매 금지. 배터리 자비 교체 비용은 약 2,200만 원.</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8" aria-labelledby="heading-id4">
        <h2 id="heading-id4" className="text-3xl font-semibold text-gray-800">폭스바겐 ID.4</h2>
        <div className="bg-red-50 border-l-4 border-red-500 p-4" role="region" aria-label="폭스바겐 ID.4 구매 회피 연식 경고">
          <h3 className="text-xl font-bold text-red-700">🚫 2021~2024년식: AVOID (주행 중 문 열림 결함)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>주행 중 도어 열림 리콜:</strong> 플러시 도어 핸들 내부로 세차장 물이나 빗물이 스며들면 터치 센서가 이를 &apos;사람 손&apos;으로 인식해 주행 중인데도 차문이 열려버리는 치명적 결함 발생. 대규모 리콜 및 판매 중단 사태.</li>
            <li><strong>히트펌프 콤프레셔 박살:</strong> 겨울철 고압 R744(CO2) 히트펌프 배관 누수로 콤프레셔가 박살나며 쇳가루가 도는 현상 (수리비 550만 원).</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8" aria-labelledby="heading-volvo-polestar">
        <h2 id="heading-volvo-polestar" className="text-3xl font-semibold text-gray-800">볼보 EX30 / 폴스타 2</h2>
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4" role="region" aria-label="볼보 EX30 및 폴스타 2 주의 연식 가이드">
          <h3 className="text-xl font-bold text-amber-900">⚠️ 2021~2024년식: CAUTION (소프트웨어 및 히터 결함)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>EX30 속도계 먹통:</strong> 모든 계기판을 중앙 12.3인치 스크린에 통합했으나 소프트웨어 에러로 주행 중 속도계 화면이 꺼지는 결함 리콜.</li>
            <li><strong>폴스타 2 세라믹 히터 파괴:</strong> 겨울철 고전압 냉각수 히터(HVCH) 내부 세라믹 부품이 쪼개지며 절연 파괴 에러로 히터 셧다운 (수리비 약 270만 원).</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8" aria-labelledby="heading-benz-eqe">
        <h2 id="heading-benz-eqe" className="text-3xl font-semibold text-gray-800">메르세데스-벤츠 EQE / EQS</h2>
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4" role="region" aria-label="메르세데스-벤츠 EQE 및 EQS 주의 연식 가이드">
          <h3 className="text-xl font-bold text-amber-900">⚠️ 2022~2023년식: CAUTION (수리비 폭탄 주의)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>모터라이즈 도어핸들 박살:</strong> 겨울철 얼음이 얼었을 때 도어 핸들 모터가 억지로 튀어나오려다 내부 플라스틱 기어 이빨이 다 부서짐 (수리비 짝당 190만 원).</li>
            <li><strong>배터리 수리비 절망편:</strong> 118kWh EQS 배터리팩 무상보증 종료 후 교체 비용은 약 <strong>7,560만 원</strong>으로 중고차 가격 전체를 상회하는 끔찍한 리스크를 안고 있습니다.</li>
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
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-blue-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <div className="flex items-center gap-2 text-blue-600 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📊</span>
              <span>글로벌 9대 브랜드 DSI 비교 랭킹</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              벤츠, BMW, 폭스바겐, 볼보, 폴스타의 결함 심각도 지수와 보증 외 고전압 배터리 교체비 매트릭스를 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-blue-600 font-semibold mt-3 group-hover:underline">
              내구성 랭킹 조회하기 &rarr;
            </span>
          </Link>

          <Link
            href="/recall-portal"
            prefetch={false}
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-rose-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500"
          >
            <div className="flex items-center gap-2 text-rose-600 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">🚨</span>
              <span>수입차 VIN 및 배터리 공급사 조회</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              17자리 차대번호로 파라시스, CATL, LG에너지솔루션 등 실제 탑재 배터리 제조사와 국토부 공식 리콜을 조회합니다.
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
              <span>수입 EV 감가율 & 배터리 잔존가치</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              독일 프리미엄 브랜드의 급격한 중고차 감가 곡선과 보증 만료 후 5년 TCO 유지비를 정밀 산출합니다.
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
              <span>수입 전기차 보조금 상한제 시뮬레이터</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              출고가 5,500만 원(100%), 8,500만 원(50%), 8,500만 원 초과(0%) 기준 실질 지자체 보조금을 비교합니다.
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
