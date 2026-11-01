'use client';

import { useEffect } from 'react';
import Link from 'next/link';

interface DepreciationErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * Next.js Segment Error Boundary: Depreciation Calculator (/depreciation-calculator)
 * Catches unhandled runtime calculations during battery degradation or depreciation simulation.
 */
export default function DepreciationCalculatorError({ error, reset }: DepreciationErrorProps) {
  useEffect(() => {
    console.error('Unhandled Depreciation Calculator route error:', error);
  }, [error]);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="min-h-[60vh] flex items-center justify-center px-4 py-12"
    >
      <div className="max-w-xl w-full bg-white border border-emerald-200 rounded-3xl p-8 sm:p-10 shadow-xl text-center space-y-6">
        <div
          className="w-16 h-16 mx-auto rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-600 flex items-center justify-center text-3xl shadow-inner"
          aria-hidden="true"
        >
          📉
        </div>

        <div className="space-y-3">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            감가율 시뮬레이션 계산 중 오류가 발생했습니다
          </h1>
          <p className="text-sm sm:text-base text-slate-600 leading-relaxed max-w-md mx-auto">
            배터리 노화(Arrhenius Kinetics) 및 5개년 잔존가치 연산 중 일시적인 계산 오류가 발생했습니다.
            기본 안전 프리셋으로 복구하려면 아래 &apos;다시 시도&apos; 버튼을 눌러주세요.
          </p>
          {error?.digest && (
            <p className="text-xs text-slate-500 font-mono pt-1">
              오류 참조 코드: <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200">{error.digest}</span>
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
            aria-label="감가 계산기 다시 시도"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold shadow-md transition focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
          >
            <span>🔄</span> 다시 시도
          </button>
          <Link
            href="/"
            prefetch={false}
            aria-label="메인 홈으로 이동"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium border border-slate-200 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2"
          >
            <span>🏠</span> 홈으로 이동
          </Link>
        </div>

        <div className="pt-4 border-t border-slate-100 text-xs text-slate-500 flex flex-wrap justify-center gap-4">
          <Link href="/subsidy-tracker" prefetch={true} className="hover:text-emerald-700 transition">
            ⚡ 보조금 추적기
          </Link>
          <Link href="/reliability-analytics" prefetch={false} className="hover:text-blue-700 transition">
            📊 결함 분석 포털
          </Link>
          <Link href="/recall-portal" prefetch={false} className="hover:text-rose-700 transition">
            🚨 리콜 포털
          </Link>
        </div>
      </div>
    </div>
  );
}
