import type { Metadata } from 'next';
import Link from 'next/link';

export const dynamic = 'force-static';

export const metadata: Metadata = {
  title: '테슬라 연식별 결함 및 구매 가이드 | Global EV Hub',
  description: '테슬라 모델 3, 모델 Y 연식별(2017~2026) 히터 파괴, 컨트롤 암, 옥토밸브 히트펌프 결함 분석 및 중고차 구매 가이드',
};

export default function TeslaPage() {
  return (
    <div className="space-y-8 py-10 max-w-4xl mx-auto">
      <h1 className="text-4xl font-bold border-b pb-4">테슬라 연식별 구매 가이드 (피해야 할 연식)</h1>
      
      <section className="space-y-4" aria-labelledby="heading-tesla-model3">
        <h2 id="heading-tesla-model3" className="text-3xl font-semibold text-gray-800">모델 3 (Model 3)</h2>
        
        <div className="bg-red-50 border-l-4 border-red-500 p-4" role="region" aria-label="테슬라 모델 3 구매 회피 연식 경고">
          <h3 className="text-xl font-bold text-red-700">🚫 2017~2020년식: AVOID (절대 피할 것)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>히터 파괴:</strong> PTC 고전압 히터가 타버려서 겨울에 얼어 죽을 수 있음 (수리비 168만 원 ~ 567만 원).</li>
            <li><strong>컨트롤 암 찌그덕:</strong> 앞바퀴 서스펜션 볼조인트에 물이 들어가 부서지면서 침대 스프링 소리가 남.</li>
            <li><strong>범퍼 물고임:</strong> 비 오는 날 뒷범퍼 아래에 물이 고여 범퍼가 통째로 뜯겨나가는 결함. 히트펌프도 없어서 겨울철 주행거리 반토막.</li>
          </ul>
        </div>

        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4" role="region" aria-label="테슬라 모델 3 주의 연식 가이드">
          <h3 className="text-xl font-bold text-amber-900">⚠️ 2021~2023년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>히트펌프 사망:</strong> 옥토밸브(히트펌프) 결함으로 한파에 에어컨/히터가 모두 죽는 결함 발생 (수리비 87만 원 ~ 661만 원).</li>
            <li>LFP 배터리 탑재 모델(RWD)은 겨울철 100% 완충을 자주 안 해주면 배터리 계산 오류로 차가 멈출 수 있습니다.</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4" role="region" aria-label="테슬라 모델 3 안전 구매 가이드">
          <h3 className="text-xl font-bold text-green-900">✅ 2024년식 (Highland): BUY SAFE (적극 추천)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>승차감이 극적으로 개선(FSD 댐퍼)되었고, 방음이 엄청나게 좋아졌습니다. 깜빡이 레버가 없어진 것만 적응하면 최고의 선택입니다.</li>
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
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-blue-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <div className="flex items-center gap-2 text-blue-600 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📊</span>
              <span>테슬라 결함 심층 분석 (DSI)</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              히트펌프 옥토밸브 파손, 서스펜션 컨트롤 암 찌그덕 등 연식별 DSI 점수와 수리비 통계를 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-blue-600 font-semibold mt-3 group-hover:underline">
              테슬라 결함 통계 보기 &rarr;
            </span>
          </Link>

          <Link
            href="/recall-portal?brand=tesla"
            prefetch={false}
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-rose-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500"
          >
            <div className="flex items-center gap-2 text-rose-600 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">🚨</span>
              <span>테슬라 VIN 차대번호 및 리콜 조회</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              차대번호 17자리 프리픽스(5YJ3, LRW 등)로 오토파일럿 ECU, 도어 래치 및 배터리 공급사를 즉시 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-rose-600 font-semibold mt-3 group-hover:underline">
              리콜 및 VIN 조회하기 &rarr;
            </span>
          </Link>

          <Link
            href="/depreciation-calculator"
            prefetch={true}
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-emerald-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          >
            <div className="flex items-center gap-2 text-emerald-600 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📉</span>
              <span>테슬라 감가방어율 & SoH 계산기</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              LFP 및 삼원계(NCM) 배터리 열화율 곡선과 5년 보유 기간 총 유지비(TCO)를 정밀 시뮬레이션합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-emerald-600 font-semibold mt-3 group-hover:underline">
              감가율 계산하기 &rarr;
            </span>
          </Link>

          <Link
            href="/subsidy-tracker"
            prefetch={true}
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-amber-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
          >
            <div className="flex items-center gap-2 text-amber-600 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">⚡</span>
              <span>모델Y RWD 실시간 보조금 소진율</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              지자체별 승용 전기차 쿼터 마감 현황과 가격 상한제 기준 테슬라 실구매 체감가를 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-amber-600 font-semibold mt-3 group-hover:underline">
              보조금 소진율 확인하기 &rarr;
            </span>
          </Link>
        </div>
      </section>
    </div>
  );
}
