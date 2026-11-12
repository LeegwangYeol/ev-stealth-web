'use client';

import { useEffect, useRef, startTransition } from 'react';
import Link from 'next/link';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function HyundaiKiaGuideError({ error, reset }: ErrorProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    console.error('Unhandled Hyundai/Kia Guide route error:', error);
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
      aria-labelledby="hyundai-kia-error-heading"
      aria-describedby="hyundai-kia-error-description"
      className="min-h-[60vh] flex items-center justify-center px-4 py-12 outline-none focus:outline-none"
    >
      <div className="max-w-xl w-full bg-white border border-slate-200 rounded-3xl p-8 sm:p-10 shadow-xl text-center space-y-6">
        <div
          className="w-16 h-16 mx-auto rounded-2xl bg-blue-50 border border-blue-200 text-blue-600 flex items-center justify-center text-3xl shadow-inner"
          aria-hidden="true"
        >
          🚘
        </div>

        <div className="space-y-3">
          <h1
            id="hyundai-kia-error-heading"
            className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight"
          >
            현대/기아 구매 가이드를 불러올 수 없습니다
          </h1>
          <p
            id="hyundai-kia-error-description"
            className="text-sm sm:text-base text-slate-700 leading-relaxed max-w-md mx-auto"
          >
            현대·기아 전기차(ICCU, 배터리 등) 결함 분석 정보를 불러오는 중 오류가 발생했습니다.
            아래 &apos;다시 시도&apos; 버튼을 눌러 다시 로드해 주세요.
          </p>
          {error?.digest && (
            <p className="text-xs text-slate-700 font-mono pt-1">
              오류 참조 코드: <span className="bg-slate-100 text-slate-700 px-2 py-0.5 rounded border border-slate-200">{error.digest}</span>
            </p>
          )}
        </div>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
          <button
            type="button"
            onClick={handleRetry}
            aria-label="현대/기아 구매 가이드 다시 시도"
            className="w-full sm:w-auto min-h-[44px] inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold shadow-md transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
          >
            <span aria-hidden="true">🔄</span> 다시 시도
          </button>
          <Link
            href="/"
            prefetch={false}
            aria-label="메인 홈으로 이동"
            className="w-full sm:w-auto min-h-[44px] inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-800 font-medium border border-slate-200 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2"
          >
            <span aria-hidden="true">🏠</span> 홈으로 이동
          </Link>
        </div>

        <div className="pt-4 border-t border-slate-100 text-xs text-slate-700 flex flex-wrap justify-center gap-3">
          <Link
            href="/reliability-analytics"
            prefetch={false}
            className="hover:text-blue-700 transition inline-flex items-center gap-1 px-2 py-1 min-h-[44px] rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <span aria-hidden="true">📊</span> 결함 통계
          </Link>
          <Link
            href="/subsidy-tracker"
            prefetch={true}
            className="hover:text-amber-800 transition inline-flex items-center gap-1 px-2 py-1 min-h-[44px] rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
          >
            <span aria-hidden="true">⚡</span> 보조금 추적기
          </Link>
          <Link
            href="/recall-portal"
            prefetch={false}
            className="hover:text-rose-700 transition inline-flex items-center gap-1 px-2 py-1 min-h-[44px] rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500"
          >
            <span aria-hidden="true">🚨</span> 리콜 포털
          </Link>
        </div>
      </div>
    </div>
  );
}
