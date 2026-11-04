'use client';

import { useEffect } from 'react';
import Link from 'next/link';

interface SubsidyErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * Next.js Segment Error Boundary: Subsidy Tracker (/subsidy-tracker)
 * Catches unhandled exceptions during subsidy quota and region calculations.
 */
export default function SubsidyTrackerError({ error, reset }: SubsidyErrorProps) {
  useEffect(() => {
    console.error('Unhandled Subsidy Tracker route error:', error);
  }, [error]);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="min-h-[60vh] flex items-center justify-center px-4 py-12"
    >
      <div className="max-w-xl w-full bg-slate-900 border border-amber-500/30 rounded-3xl p-8 sm:p-10 shadow-2xl text-center space-y-6">
        <div
          className="w-16 h-16 mx-auto rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-400 flex items-center justify-center text-3xl shadow-inner"
          aria-hidden="true"
        >
          ⚡
        </div>

        <div className="space-y-3">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            보조금 소진율 데이터를 불러올 수 없습니다
          </h1>
          <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-md mx-auto">
            17개 광역시도 지자체 보조금 접수 데이터 동기화 과정에서 일시적인 지연이나 오류가 발생했습니다.
            저장된 기준 데이터로 안전하게 다시 로드할 수 있습니다.
          </p>
          {error?.digest && (
            <p className="text-xs text-slate-300 font-mono pt-1">
              오류 참조 코드: <span className="bg-slate-800 text-slate-300 px-2 py-0.5 rounded border border-slate-700">{error.digest}</span>
            </p>
          )}
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <button
            type="button"
            onClick={() => {
              try {
                reset();
              } catch {
                if (typeof window !== 'undefined') {
                  window.location.reload();
                }
              }
            }}
            aria-label="보조금 추적기 다시 시도"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
          >
            <span aria-hidden="true">🔄</span> 다시 시도
          </button>
          <Link
            href="/"
            prefetch={false}
            aria-label="메인 홈으로 이동"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium border border-slate-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
          >
            <span aria-hidden="true">🏠</span> 홈으로 이동
          </Link>
        </div>

        <div className="pt-4 border-t border-slate-800/80 text-xs text-slate-300 flex flex-wrap justify-center gap-4">
          <Link
            href="/depreciation-calculator"
            prefetch={true}
            className="hover:text-amber-300 transition inline-flex items-center gap-1 px-1.5 py-0.5 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
          >
            <span aria-hidden="true">📉</span> 감가 계산기
          </Link>
          <Link
            href="/reliability-analytics"
            prefetch={false}
            className="hover:text-blue-300 transition inline-flex items-center gap-1 px-1.5 py-0.5 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
          >
            <span aria-hidden="true">📊</span> 결함 분석 포털
          </Link>
          <Link
            href="/recall-portal"
            prefetch={false}
            className="hover:text-rose-300 transition inline-flex items-center gap-1 px-1.5 py-0.5 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-400"
          >
            <span aria-hidden="true">🚨</span> 리콜 포털
          </Link>
        </div>
      </div>
    </div>
  );
}
