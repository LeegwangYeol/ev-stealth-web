'use client';

import { useEffect, useRef, startTransition } from 'react';
import Link from 'next/link';

interface AdminErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * Next.js Segment Error Boundary: Secret Admin Reports (/secret-admin-reports)
 * Catches unhandled exceptions during daily monitoring reports parse and KPI calculations.
 */
export default function SecretAdminReportsError({ error, reset }: AdminErrorProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    console.error('Unhandled Admin Reports route error:', error);
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
      aria-atomic="true"
      aria-labelledby="admin-error-heading"
      aria-describedby="admin-error-description"
      className="min-h-[60vh] flex items-center justify-center px-4 py-12 outline-none focus:outline-none"
    >
      <div className="max-w-xl w-full bg-slate-900 border border-slate-800 rounded-3xl p-8 sm:p-10 shadow-2xl text-center space-y-6">
        <div
          className="w-16 h-16 mx-auto rounded-2xl bg-slate-800 border border-slate-700 text-amber-400 flex items-center justify-center text-3xl shadow-inner"
          aria-hidden="true"
        >
          🔒
        </div>

        <div className="space-y-3">
          <h1
            id="admin-error-heading"
            className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight"
          >
            관리자 리포트를 불러올 수 없습니다
          </h1>
          <p
            id="admin-error-description"
            className="text-sm sm:text-base text-slate-200 leading-relaxed max-w-md mx-auto"
          >
            데일리 결함 모니터링 원시 데이터 파싱 또는 통계 집계 중 오류가 발생했습니다.
            아래 &apos;다시 시도&apos; 버튼을 눌러 다시 로드해 주세요.
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
            onClick={handleRetry}
            aria-label="관리자 리포트 다시 시도"
            className="w-full sm:w-auto min-h-[44px] inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
          >
            <span aria-hidden="true">🔄</span> 다시 시도
          </button>
          <Link
            href="/"
            prefetch={false}
            aria-label="메인 홈으로 이동"
            className="w-full sm:w-auto min-h-[44px] inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium border border-slate-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
          >
            <span aria-hidden="true">🏠</span> 홈으로 이동
          </Link>
        </div>

        <div className="pt-4 border-t border-slate-800/80 text-xs text-slate-300 flex flex-wrap justify-center gap-3">
          <Link
            href="/reliability-analytics"
            prefetch={false}
            className="hover:text-blue-300 transition inline-flex items-center gap-1 px-2 py-1 min-h-[44px] rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
          >
            <span aria-hidden="true">📊</span> 결함 통계
          </Link>
          <Link
            href="/recall-portal"
            prefetch={false}
            className="hover:text-rose-300 transition inline-flex items-center gap-1 px-2 py-1 min-h-[44px] rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-400"
          >
            <span aria-hidden="true">🚨</span> 리콜 포털
          </Link>
          <Link
            href="/subsidy-tracker"
            prefetch={true}
            className="hover:text-amber-300 transition inline-flex items-center gap-1 px-2 py-1 min-h-[44px] rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400"
          >
            <span aria-hidden="true">⚡</span> 보조금 추적
          </Link>
        </div>
      </div>
    </div>
  );
}
