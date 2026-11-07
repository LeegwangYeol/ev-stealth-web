'use client';

import { useEffect, useRef, startTransition } from 'react';
import Link from 'next/link';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * Next.js App Router Root Error Boundary
 * Catches unhandled runtime exceptions within the route tree and provides accessible recovery controls.
 */
export default function ErrorBoundary({ error, reset }: ErrorProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Log exception for telemetry and diagnostic tracking
    console.error('Unhandled App Router client error:', error);
    // Focus the alert container for screen reader and keyboard accessibility
    containerRef.current?.focus();
  }, [error]);

  const handleRetry = () => {
    try {
      startTransition(() => {
        reset();
      });
    } catch {
      if (typeof window !== 'undefined') {
        window.location.reload();
      }
    }
  };

  return (
    <div
      ref={containerRef}
      tabIndex={-1}
      role="alert"
      aria-live="assertive"
      aria-labelledby="root-error-heading"
      aria-describedby="root-error-description"
      className="min-h-[70vh] flex items-center justify-center px-4 py-16 outline-none focus:outline-none"
    >
      <div className="max-w-lg w-full bg-white rounded-3xl p-8 sm:p-10 shadow-xl border border-slate-200 text-center space-y-6">
        <div
          className="w-16 h-16 mx-auto rounded-2xl bg-rose-50 border border-rose-200 text-rose-600 flex items-center justify-center text-3xl shadow-inner"
          aria-hidden="true"
        >
          ⚠️
        </div>

        <div className="space-y-2">
          <h1
            id="root-error-heading"
            className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight"
          >
            일시적인 오류가 발생했습니다
          </h1>
          <p
            id="root-error-description"
            className="text-sm sm:text-base text-slate-700 leading-relaxed"
          >
            데이터를 불러오거나 처리하는 과정에서 예기치 않은 오류가 발생했습니다. 일시적인 현상일 수 있으니 아래 &apos;다시 시도&apos; 버튼을 눌러주시거나 메인 페이지로 이동해 주세요.
          </p>
          {error?.digest && (
            <p className="text-xs text-slate-700 font-mono pt-1">
              오류 참조 코드: <span className="bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">{error.digest}</span>
            </p>
          )}
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <button
            type="button"
            onClick={handleRetry}
            aria-label="다시 시도"
            className="w-full sm:w-auto min-h-[44px] inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow-md transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
          >
            <span aria-hidden="true">🔄</span> 다시 시도
          </button>
          <Link
            href="/"
            prefetch={false}
            aria-label="홈으로 이동"
            className="w-full sm:w-auto min-h-[44px] inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 font-semibold border border-slate-200 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2"
          >
            <span aria-hidden="true">🏠</span> 홈으로 이동
          </Link>
        </div>

        {/* Quick core navigation fallbacks */}
        <div className="pt-4 border-t border-slate-100 text-xs text-slate-700 flex flex-wrap justify-center gap-3">
          <Link
            href="/subsidy-tracker"
            prefetch={true}
            className="hover:text-amber-700 transition inline-flex items-center gap-1 px-2 py-1 min-h-[44px] rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
          >
            <span aria-hidden="true">⚡</span> 보조금 추적기
          </Link>
          <Link
            href="/reliability-analytics"
            prefetch={false}
            className="hover:text-blue-700 transition inline-flex items-center gap-1 px-2 py-1 min-h-[44px] rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <span aria-hidden="true">📊</span> 결함 분석 포털
          </Link>
          <Link
            href="/depreciation-calculator"
            prefetch={true}
            className="hover:text-emerald-700 transition inline-flex items-center gap-1 px-2 py-1 min-h-[44px] rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500"
          >
            <span aria-hidden="true">📉</span> 감가 계산기
          </Link>
          <Link
            href="/recall-portal"
            prefetch={false}
            className="hover:text-rose-700 transition inline-flex items-center gap-1 px-2 py-1 min-h-[44px] rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500"
          >
            <span aria-hidden="true">🚨</span> 공식 리콜
          </Link>
        </div>
      </div>
    </div>
  );
}
