import type { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: '페이지를 찾을 수 없습니다 (404) | Global EV Hub',
  description: '요청하신 페이지가 존재하지 않거나 주소가 변경되었습니다.',
  openGraph: {
    title: '페이지를 찾을 수 없습니다 (404) | Global EV Hub',
    description: '요청하신 페이지가 존재하지 않거나 주소가 변경되었습니다.',
    siteName: 'Global EV Hub',
    locale: 'ko_KR',
    type: 'website',
  },
};

/**
 * Next.js App Router Branded 404 Not Found Page
 * Provides graceful navigation back to high-intent core utilities.
 */
export default function NotFound() {
  return (
    <div
      role="region"
      aria-label="404 페이지 찾을 수 없음 안내"
      className="min-h-[70vh] flex items-center justify-center px-4 py-16"
    >
      <div className="max-w-2xl w-full bg-white rounded-3xl p-8 sm:p-12 shadow-xl border border-slate-200 text-center space-y-8">
        <div className="space-y-3">
          <div
            className="inline-flex items-center justify-center w-20 h-20 rounded-2xl bg-amber-50 border border-amber-200 text-amber-600 text-4xl mx-auto shadow-inner"
            aria-hidden="true"
          >
            ⚡
          </div>
          <div className="text-6xl sm:text-7xl font-black text-slate-900 tracking-tight font-mono">
            404
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900">
            요청하신 페이지를 찾을 수 없습니다
          </h1>
          <p className="text-slate-600 text-sm sm:text-base max-w-md mx-auto leading-relaxed">
            방문하시려는 페이지의 주소가 잘못되었거나 삭제되어 표시할 수 없습니다. 아래 바로가기 메뉴를 통해 핵심 전기차 분석 도구를 이용해 보세요.
          </p>
        </div>

        {/* Quick Navigation Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-left">
          <Link
            href="/subsidy-tracker"
            prefetch={true}
            className="group p-5 rounded-2xl border border-slate-200 bg-slate-50 hover:bg-amber-50/60 hover:border-amber-300 transition shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
          >
            <div className="flex items-center gap-2 font-bold text-slate-900 group-hover:text-amber-800 text-base">
              <span className="text-xl">⚡</span>
              <span>보조금 소진율 추적기</span>
            </div>
            <p className="text-xs text-slate-600 mt-1 leading-relaxed">
              전국 17개 지자체 실시간 쿼터 및 소진 마감 긴급 경보
            </p>
          </Link>

          <Link
            href="/reliability-analytics"
            prefetch={false}
            className="group p-5 rounded-2xl border border-slate-200 bg-slate-50 hover:bg-blue-50/60 hover:border-blue-300 transition shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <div className="flex items-center gap-2 font-bold text-slate-900 group-hover:text-blue-800 text-base">
              <span className="text-xl">📊</span>
              <span>결함 분석 포털 (DSI)</span>
            </div>
            <p className="text-xs text-slate-600 mt-1 leading-relaxed">
              9대 제조사 22개 차종 연식별 결함 심각도 및 피해야 할 연식
            </p>
          </Link>

          <Link
            href="/depreciation-calculator"
            prefetch={true}
            className="group p-5 rounded-2xl border border-slate-200 bg-slate-50 hover:bg-emerald-50/60 hover:border-emerald-300 transition shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          >
            <div className="flex items-center gap-2 font-bold text-slate-900 group-hover:text-emerald-800 text-base">
              <span className="text-xl">📉</span>
              <span>감가 계산기</span>
            </div>
            <p className="text-xs text-slate-600 mt-1 leading-relaxed">
              실구매가·배터리 건강도(SoH) 기반 5년 TCO 및 잔존가치 시뮬레이션
            </p>
          </Link>

          <Link
            href="/"
            prefetch={false}
            className="group p-5 rounded-2xl border border-slate-200 bg-slate-50 hover:bg-indigo-50/60 hover:border-indigo-300 transition shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
          >
            <div className="flex items-center gap-2 font-bold text-slate-900 group-hover:text-indigo-800 text-base">
              <span className="text-xl">🏠</span>
              <span>홈으로 이동</span>
            </div>
            <p className="text-xs text-slate-600 mt-1 leading-relaxed">
              Global EV Hub 메인 대시보드 및 실시간 커뮤니티 결함 리포트
            </p>
          </Link>
        </div>
      </div>
    </div>
  );
}
