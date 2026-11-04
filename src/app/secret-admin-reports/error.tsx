'use client';

import { useEffect } from 'react';
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
  useEffect(() => {
    console.error('Unhandled Admin Reports route error:', error);
  }, [error]);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="min-h-[60vh] flex items-center justify-center px-4 py-12"
    >
      <div className="max-w-xl w-full bg-slate-900 border border-slate-800 rounded-3xl p-8 sm:p-10 shadow-2xl text-center space-y-6">
        <div
          className="w-16 h-16 mx-auto rounded-2xl bg-slate-800 border border-slate-700 text-amber-400 flex items-center justify-center text-3xl shadow-inner"
          aria-hidden="true"
        >
          🔒
        </div>

        <div className="space-y-3">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            관리자 리포트를 불러올 수 없습니다
          </h1>
          <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-md mx-auto">
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
            onClick={() => {
              try {
                reset();
              } catch {
                if (typeof window !== 'undefined') {
                  window.location.reload();
                }
              }
            }}
            aria-label="관리자 리포트 다시 시도"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
          >
            <span aria-hidden="true">🔄</span> 다시 시도
          </button>
          <Link
            href="/"
            prefetch={false}
            aria-label="메인 홈으로 이동"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium border border-slate-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
          >
            <span aria-hidden="true">🏠</span> 홈으로 이동
          </Link>
        </div>
      </div>
    </div>
  );
}
