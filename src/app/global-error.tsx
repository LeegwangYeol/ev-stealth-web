'use client';

import { useEffect, useRef, startTransition } from 'react';

interface GlobalErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * Next.js Root Global Error Boundary (src/app/global-error.tsx)
 * Catches unhandled runtime exceptions within the root layout or provider hierarchy.
 * Replaces the entire root document, defining its own <html> and <body>.
 */
export default function GlobalError({ error, reset }: GlobalErrorProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Log exception for telemetry and diagnostic tracking
    console.error('Unhandled Root Layout Global Error:', error);
    // Move keyboard/screen reader focus to the alert container
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

  const handleReload = () => {
    if (typeof window !== 'undefined') {
      window.location.reload();
    }
  };

  const handleGoHome = () => {
    if (typeof window !== 'undefined') {
      window.location.href = '/';
    }
  };

  return (
    <html lang="ko">
      <body className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-4 antialiased font-sans">
        <main
          ref={containerRef}
          tabIndex={-1}
          role="alert"
          aria-live="assertive"
          aria-labelledby="global-error-heading"
          aria-describedby="global-error-description"
          className="max-w-lg w-full bg-slate-900 border border-slate-800 rounded-3xl p-8 sm:p-10 shadow-2xl text-center space-y-6 outline-none focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        >
          <div
            className="w-16 h-16 mx-auto rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-400 flex items-center justify-center text-3xl shadow-inner"
            aria-hidden="true"
          >
            ⚠️
          </div>

          <div className="space-y-3">
            <h1
              id="global-error-heading"
              className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight"
            >
              시스템 오류가 발생했습니다
            </h1>
            <p
              id="global-error-description"
              className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-md mx-auto"
            >
              애플리케이션 최상위 레이아웃을 렌더링하는 도중 예기치 못한 문제가 발생했습니다.
              아래 &apos;다시 시도&apos; 버튼 또는 &apos;새로고침&apos;을 눌러 복구해 주세요.
            </p>
            {error?.digest && (
              <p className="text-xs text-slate-400 font-mono pt-1">
                오류 참조 코드: <span className="bg-slate-800 text-slate-300 px-2 py-0.5 rounded border border-slate-700">{error.digest}</span>
              </p>
            )}
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
            <button
              type="button"
              onClick={handleRetry}
              aria-label="애플리케이션 다시 시도"
              className="w-full sm:w-auto min-h-[44px] inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-bold shadow-lg transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
            >
              <span aria-hidden="true">🔄</span> 다시 시도
            </button>
            <button
              type="button"
              onClick={handleReload}
              aria-label="페이지 새로고침"
              className="w-full sm:w-auto min-h-[44px] inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold border border-slate-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
            >
              <span aria-hidden="true">🔃</span> 새로고침
            </button>
            <button
              type="button"
              onClick={handleGoHome}
              aria-label="메인 홈으로 이동"
              className="w-full sm:w-auto min-h-[44px] inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold border border-slate-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
            >
              <span aria-hidden="true">🏠</span> 홈으로 이동
            </button>
          </div>
        </main>
      </body>
    </html>
  );
}
