import type { Metadata } from 'next';
import Link from 'next/link';

export const dynamic = 'force-static';

export const metadata: Metadata = {
  title: '현대/기아 전기차 연식별 결함 및 구매 가이드 | Global EV Hub',
  description: '아이오닉5, EV6, EV9 등 현대/기아 전기차 연식별(2021~2026) ICCU 결함, 고질병 분석 및 피해야 할 연식 가이드',
};

export default function HyundaiKiaPage() {
  return (
    <div className="space-y-8 py-10 max-w-4xl mx-auto">
      <h1 className="text-4xl font-bold border-b pb-4">현대/기아 연식별 구매 가이드 (피해야 할 연식)</h1>
      
      <section className="space-y-4" aria-labelledby="heading-ioniq5">
        <h2 id="heading-ioniq5" className="text-3xl font-semibold text-gray-800">아이오닉 5 (Ioniq 5)</h2>
        
        <div className="bg-red-50 border-l-4 border-red-500 p-4" role="region" aria-label="아이오닉 5 구매 회피 연식 경고">
          <h3 className="text-xl font-bold text-red-700">🚫 2021~2022년식: AVOID (절대 피할 것)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>ICCU 결함:</strong> 800V ICCU 내부 퓨즈가 끊어지며 고속도로에서 갑자기 차가 서버림 (예상 수리비 525만 원 ~ 692만 원).</li>
            <li><strong>후방 와이퍼 부재:</strong> 비 오는 날 후방 시야가 완전히 가려져 심각한 안전 문제 발생.</li>
            <li><strong>조치:</strong> 이 연식은 감가가 심하더라도 피하는 것이 상책입니다.</li>
          </ul>
        </div>

        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4" role="region" aria-label="아이오닉 5 주의 연식 가이드">
          <h3 className="text-xl font-bold text-amber-900">⚠️ 2023~2024년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>배터리가 77.4kWh로 커지고 프리컨디셔닝이 추가되었으나, 여전히 ICCU 리콜(24V-868) 대상입니다.</li>
            <li><strong>조치:</strong> 딜러나 서비스센터에서 ICCU 리콜이 완료되었는지 반드시 확인 후 구매하세요.</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4" role="region" aria-label="아이오닉 5 안전 구매 가이드">
          <h3 className="text-xl font-bold text-green-900">✅ 2025년식 (Facelift): BUY SAFE (적극 추천)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>공장 출고 때부터 ICCU 하드웨어가 개선되었고, 84kWh로 배터리 용량 증가, 후방 와이퍼가 기본 장착되었습니다. 가장 추천하는 연식입니다.</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8" aria-labelledby="heading-ev6">
        <h2 id="heading-ev6" className="text-3xl font-semibold text-gray-800">기아 EV6</h2>
        
        <div className="bg-red-50 border-l-4 border-red-500 p-4" role="region" aria-label="기아 EV6 구매 회피 연식 경고">
          <h3 className="text-xl font-bold text-red-700">🚫 2022년식: AVOID (절대 피할 것)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>초기 결함:</strong> 충전구 잠금 핀이 고착되어 충전기가 안 빠지는 문제, 너무 단단한 서스펜션 세팅으로 인한 승차감 저하.</li>
          </ul>
        </div>

        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4" role="region" aria-label="기아 EV6 주의 연식 가이드">
          <h3 className="text-xl font-bold text-amber-900">⚠️ 2023~2024년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>후륜 구동축 톱니바퀴(스플라인) 파손 리콜(24V-057) 및 메리디안 오디오 앰프 고장(수리비 100만 원 이상) 위험이 있습니다.</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4" role="region" aria-label="EV6 안전 구매 가이드">
          <h3 className="text-xl font-bold text-green-900">✅ 2025년식 (Facelift): BUY SAFE (적극 추천)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>승차감이 크게 개선되었고 초기 기계적 결함이 대부분 잡혔습니다.</li>
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
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-blue-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <div className="flex items-center gap-2 text-blue-600 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📊</span>
              <span>현대·기아 결함 분석 (DSI)</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              아이오닉5 ICCU, EV6 구동축 등 연식별 결함 심각도 지수와 보증 외 예상 수리비 매트릭스를 확인합니다.
            </p>
            <span className="inline-flex items-center gap-1 text-xs text-blue-600 font-semibold mt-3 group-hover:underline">
              결함 통계 조회하기 &rarr;
            </span>
          </Link>

          <Link
            href="/recall-portal?brand=hyundai"
            prefetch={false}
            className="group block p-5 rounded-2xl border border-slate-200 bg-white hover:border-rose-400 hover:shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500"
          >
            <div className="flex items-center gap-2 text-rose-600 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">🚨</span>
              <span>현대·기아 공식 리콜 포털</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              차대번호(VIN) 17자리 또는 모델명으로 국토교통부 공식 리콜 조치 여부 및 탑재 배터리 제조사를 즉시 조회합니다.
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
            <div className="flex items-center gap-2 text-emerald-600 font-bold text-base mb-1">
              <span className="text-xl" aria-hidden="true">📉</span>
              <span>전기차 감가·배터리 수명 계산기</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              보조금 수령 후 5년간의 잔존가치, 배터리 잔존성능(SoH), 연차별 총소유비용(TCO)을 정밀 시뮬레이션합니다.
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
              <span>전국 지자체 실시간 보조금 소진율</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              환경부 및 17개 광역시도별 보조금 소진율, 마감 임박 경보, 5,500만 원 상한제 차등 지급액을 확인합니다.
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
