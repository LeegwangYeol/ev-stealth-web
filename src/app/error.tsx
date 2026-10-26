'use client';

import { useEffect } from 'react';
import Link from 'next/link';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * Next.js App Router Root Error Boundary
 * Catches unhandled runtime exceptions within the route tree and provides recovery controls.
 */
export default function ErrorBoundary({ error, reset }: ErrorProps) {
  useEffect(() => {
    // Log exception for telemetry and diagnostic tracking
    console.error('Unhandled App Router client error:', error);
  }, [error]);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="min-h-[70vh] flex items-center justify-center px-4 py-16"
    >
      <div className="max-w-lg w-full bg-white rounded-3xl p-8 sm:p-10 shadow-xl border border-slate-200 text-center space-y-6">
        <div
          className="w-16 h-16 mx-auto rounded-2xl bg-rose-50 border border-rose-200 text-rose-600 flex items-center justify-center text-3xl shadow-inner"
          aria-hidden="true"
        >
          ⚠️
        </div>

        <div className="space-y-2">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            일시적인 오류가 발생했습니다
          </h1>
          <p className="text-sm sm:text-base text-slate-600 leading-relaxed">
            데이터를 불러오거나 처리하는 과정에서 예기치 않은 오류가 발생했습니다. 일시적인 현상일 수 있으니 아래 &apos;다시 시도&apos; 버튼을 눌러주시거나 메인 페이지로 이동해 주세요.
          </p>
          {error?.digest && (
            <p className="text-xs text-slate-400 font-mono pt-1">
              오류 참조 코드: <span className="bg-slate-100 px-1.5 py-0.5 rounded">{error.digest}</span>
            </p>
          )}
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <button
            type="button"
            onClick={() => reset()}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow-md transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
          >
            <span>🔄</span> 다시 시도 (Reset)
          </button>
          <Link
            href="/"
            prefetch={false}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold border border-slate-200 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2"
          >
            <span>🏠</span> 홈으로 이동
          </Link>
        </div>
      </div>
    </div>
  );
}
