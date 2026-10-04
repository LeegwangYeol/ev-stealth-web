import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center space-y-12 py-20">
      <div className="text-center space-y-4">
        <h1 className="text-5xl font-extrabold tracking-tight text-slate-900">
          글로벌 EV 중고차 연식별 피하기 가이드
        </h1>
        <p className="text-xl text-gray-600 max-w-2xl mx-auto">
          &quot;테슬라 사지 마라&quot;가 아니라 <strong>&quot;테슬라 모델3 2017~2020년식은 피해라&quot;</strong>가 맞습니다. 특정 모델과 연식별(Model Year) 고질병을 정확하게 파헤칩니다.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 w-full max-w-6xl">
        <Link href="/subsidy-tracker"
          className="group block p-6 bg-gradient-to-br from-amber-950 via-slate-900 to-yellow-950 text-white border border-amber-700/50 rounded-2xl shadow-lg hover:shadow-2xl hover:border-amber-400 transition-all duration-300 md:col-span-2 lg:col-span-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
            <div className="flex items-center gap-2">
              <span className="px-3 py-1 bg-amber-500/30 text-amber-300 border border-amber-400/40 rounded-full text-xs font-bold uppercase tracking-wider flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping motion-reduce:animate-none inline-block" aria-hidden="true" />
                스케줄러 실시간 연동
              </span>
              <span className="text-xs text-amber-200 font-medium">전국 17개 광역시도 · 73개 지자체 보조금 실시간 소진율</span>
            </div>
            <span className="text-xs text-amber-300 font-semibold">5,500만/8,500만 원 상한제 실구매가 자동 계산</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold mb-2 text-white group-hover:text-amber-300 transition">
            ⚡ 전국 지자체별 전기차 실시간 보조금 소진율 추적기 &rarr;
          </h2>
          <p className="text-slate-300 leading-relaxed text-sm sm:text-base">
            환경부 무공해차 통합누리집(ev.or.kr) 실시간 공고 쿼터와 연동하여, 내 거주지의 <strong>전기승용·화물 보조금 잔여량과 5단계 소진 경보</strong>(원활·주의·경고·위험·마감)를 실시간 추적합니다. 선택한 차종의 <strong>국비+지방비 매칭 지원금과 최종 실구매 체감가</strong>를 원클릭으로 계산하세요.
          </p>
          <div className="mt-4 pt-3 border-t border-amber-900/60 flex flex-wrap gap-2 text-xs text-amber-200/90">
            <span className="px-2.5 py-1 rounded-md bg-amber-900/40 border border-amber-700/30">✓ 17개 시도 실시간 쿼터 소진율</span>
            <span className="px-2.5 py-1 rounded-md bg-amber-900/40 border border-amber-700/30">✓ 5단계 긴급 소진 경보 배지</span>
            <span className="px-2.5 py-1 rounded-md bg-amber-900/40 border border-amber-700/30">✓ 55M/85M 슬라이딩 실구매가 계산</span>
            <span className="px-2.5 py-1 rounded-md bg-amber-900/40 border border-amber-700/30">✓ 지자체별 거주 요건 알림</span>
          </div>
        </Link>

        <Link href="/depreciation-calculator"
          prefetch={false}
          className="group block p-6 bg-gradient-to-br from-emerald-950 via-slate-900 to-teal-950 text-white border border-emerald-700/50 rounded-2xl shadow-lg hover:shadow-2xl hover:border-emerald-400 transition-all duration-300 md:col-span-2 lg:col-span-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
            <div className="flex items-center gap-2">
              <span className="px-3 py-1 bg-emerald-500/30 text-emerald-300 border border-emerald-400/40 rounded-full text-xs font-bold uppercase tracking-wider">
                신규 확장
              </span>
              <span className="text-xs text-emerald-200 font-medium">15개 주요 모델 잔존가치 빅데이터 · 배터리 수명 시뮬레이션</span>
            </div>
            <span className="text-xs text-emerald-300 font-semibold">대기환경보전법 제58조 보조금 환수율 완벽 반영</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold mb-2 text-white group-hover:text-emerald-300 transition">
            📉 전기차 감가방어율 &amp; 배터리 수명 계산기 &rarr;
          </h2>
          <p className="text-slate-300 leading-relaxed text-sm sm:text-base">
            내 차의 1~5년 차 잔존가치와 <strong>감가 방어율 비교</strong>, 주행거리·급속충전 비율에 따른 <strong>배터리 열화 시뮬레이션</strong>(SoH 잔여수명 및 배터리 교체비용), 2년 의무운행 기간 내 매도 시 <strong>보조금 환수액 계산</strong>, 5년 유지비 총소유비용(<strong>TCO 절감 분석</strong>)까지 원클릭으로 정밀 시뮬레이션하세요.
          </p>
          <div className="mt-4 pt-3 border-t border-emerald-900/60 flex flex-wrap gap-2 text-xs text-emerald-200/90">
            <span className="px-2.5 py-1 rounded-md bg-emerald-900/40 border border-emerald-700/30">✓ 감가 방어율 비교</span>
            <span className="px-2.5 py-1 rounded-md bg-emerald-900/40 border border-emerald-700/30">✓ 배터리 열화 시뮬레이션</span>
            <span className="px-2.5 py-1 rounded-md bg-emerald-900/40 border border-emerald-700/30">✓ 보조금 환수액 계산</span>
            <span className="px-2.5 py-1 rounded-md bg-emerald-900/40 border border-emerald-700/30">✓ TCO 절감 분석</span>
          </div>
        </Link>

        <Link href="/reliability-analytics"
          prefetch={false}
          className="group block p-6 bg-gradient-to-br from-indigo-900 via-slate-900 to-blue-950 text-white border border-indigo-700/50 rounded-2xl shadow-lg hover:shadow-2xl hover:border-indigo-400 transition-all duration-300 md:col-span-2 lg:col-span-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
            <div className="flex items-center gap-2">
              <span className="px-3 py-1 bg-indigo-500/30 text-indigo-300 border border-indigo-400/40 rounded-full text-xs font-bold uppercase tracking-wider">
                핵심 신규 포털
              </span>
              <span className="text-xs text-indigo-200 font-medium">9개 브랜드 · 22개 모델 · 89개 연식 전수 평가</span>
            </div>
            <span className="text-xs text-indigo-300 font-semibold">1,280건 커뮤니티 빅데이터 기반</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold mb-2 text-white group-hover:text-blue-300 transition">
            📊 전기차 결함 통계 &amp; 내구성(DSI) 분석 대시보드 &rarr;
          </h2>
          <p className="text-slate-300 leading-relaxed text-sm sm:text-base">
            아이오닉, EV6, 모델3/Y, BYD, 벤츠 EQE 등 89개 연식별 결함 심각도 지수(DSI), 고질병 랭킹, 연식 리스크 히트맵 및 보증 만료 후 폭탄 수리비 매트릭스를 인터랙티브 차트로 확인하세요.
          </p>
        </Link>

        <Link href="/recall-portal"
          prefetch={false}
          className="group block p-6 bg-gradient-to-br from-rose-950 via-slate-900 to-amber-950 text-white border border-rose-700/50 rounded-2xl shadow-lg hover:shadow-2xl hover:border-rose-400 transition-all duration-300 md:col-span-2 lg:col-span-3 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
            <div className="flex items-center gap-2">
              <span className="px-3 py-1 bg-rose-500/30 text-rose-300 border border-rose-400/40 rounded-full text-xs font-bold uppercase tracking-wider">
                국토부·NHTSA 공인 연동
              </span>
              <span className="text-xs text-rose-200 font-medium">배터리 제조사 전면 공개 · 17자리 VIN 1초 조회</span>
            </div>
            <span className="text-xs text-rose-300 font-semibold">지하주차장 화재 권고안 &amp; 원클릭 예시</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold mb-2 text-white group-hover:text-rose-300 transition">
            🚨 공식 전기차 리콜 &amp; 배터리 화재 안전 포털 &rarr;
          </h2>
          <p className="text-slate-300 leading-relaxed text-sm sm:text-base">
            내 차의 배터리 제조사(LG에너지솔루션·SK온·삼성SDI·CATL·파라시스) 실명 공개, 국토교통부·NHTSA 공식 리콜 이력 및 지하주차장 화재 안전 권고안을 17자리 차대번호(VIN) 조회 또는 원클릭 예시로 즉시 확인하세요.
          </p>
        </Link>

        <Link href="/2026-latest"
          prefetch={false}
          className="group block p-6 bg-blue-50 border border-blue-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
          <h2 className="text-2xl font-bold mb-3 text-blue-700 group-hover:text-blue-800">🔥 2026년식 KDM 최신 리뷰 &rarr;</h2>
          <p className="text-gray-700 leading-relaxed">
            방금 출고된 EV3, 26년식 모델Y, 아이오닉9, BYD 시라이언7의 한국 차주 리얼 후기와 초기 결함 총정리! (출처 포함)
          </p>
        </Link>

        <Link href="/pdi-checklist"
          prefetch={false}
          className="group block p-6 bg-green-50 border border-green-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
          <h2 className="text-2xl font-bold mb-3 text-green-700 group-hover:text-green-800">✅ 신차 인수(PDI) 체크리스트 &rarr;</h2>
          <p className="text-gray-700 leading-relaxed">
            호갱 방지! 탁송된 전기차 서명 전 스마트폰으로 열어보고 하나씩 체크하세요. 하부 배터리팩 찍힘 등 필수 확인 항목.
          </p>
        </Link>

        <Link href="/hyundai-kia"
          prefetch={false}
          className="group block p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
          <h2 className="text-2xl font-bold mb-3 group-hover:text-blue-600">현대/기아 연식별 &rarr;</h2>
          <p className="text-gray-600 leading-relaxed">
            아이오닉5, EV6, GV60의 초기형(21~22년식) ICCU 결함 피하는 법 및 구매 추천 연식.
          </p>
        </Link>

        <Link href="/tesla"
          prefetch={false}
          className="group block p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
          <h2 className="text-2xl font-bold mb-3 group-hover:text-blue-600">테슬라 연식별 &rarr;</h2>
          <p className="text-gray-600 leading-relaxed">
            모델3/모델Y 히트펌프 사망 결함, 컨트롤 암 파손을 피하기 위한 연식 선택 가이드.
          </p>
        </Link>

        <Link href="/byd"
          prefetch={false}
          className="group block p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
          <h2 className="text-2xl font-bold mb-3 group-hover:text-blue-600">BYD 연식별 &rarr;</h2>
          <p className="text-gray-600 leading-relaxed">
            돌핀 에어컨 백색 가루 결함, 시라이언 07 CTB 파손 위험 등 주력 모델 피하기 매트릭스.
          </p>
        </Link>

        <Link href="/global-brands"
          prefetch={false}
          className="group block p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2">
          <h2 className="text-2xl font-bold mb-3 group-hover:text-blue-600">폭스바겐/벤츠/폴스타 &rarr;</h2>
          <p className="text-gray-600 leading-relaxed">
            볼트EV 화재 리콜, 폭스바겐 ID.4 주행 중 문열림, 벤츠 7,500만 원 배터리 교체비 리포트.
          </p>
        </Link>
      </div>
    </div>
  );
}
