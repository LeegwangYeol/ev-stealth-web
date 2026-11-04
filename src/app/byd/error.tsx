'use client';

import { useEffect } from 'react';
import Link from 'next/link';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function BydGuideError({ error, reset }: ErrorProps) {
  useEffect(() => {
    console.error('Unhandled BYD Guide route error:', error);
  }, [error]);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="min-h-[60vh] flex items-center justify-center px-4 py-12"
    >
      <div className="max-w-xl w-full bg-white border border-slate-200 rounded-3xl p-8 sm:p-10 shadow-xl text-center space-y-6">
        <div
          className="w-16 h-16 mx-auto rounded-2xl bg-amber-50 border border-amber-200 text-amber-600 flex items-center justify-center text-3xl shadow-inner"
          aria-hidden="true"
        >
          ⚡
        </div>

        <div className="space-y-3">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            BYD 구매 가이드를 불러올 수 없습니다
          </h1>
          <p className="text-sm sm:text-base text-slate-600 leading-relaxed max-w-md mx-auto">
            BYD 모델별 결함 분석 정보를 불러오는 중 오류가 발생했습니다.
            아래 &apos;다시 시도&apos; 버튼을 눌러 다시 로드해 주세요.
          </p>
          {error?.digest && (
            <p className="text-xs text-slate-600 font-mono pt-1">
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
            aria-label="BYD 구매 가이드 다시 시도"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold shadow-md transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2"
          >
            <span aria-hidden="true">🔄</span> 다시 시도
          </button>
          <Link
            href="/"
            prefetch={false}
            aria-label="메인 홈으로 이동"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium border border-slate-200 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2"
          >
            <span aria-hidden="true">🏠</span> 홈으로 이동
          </Link>
        </div>
      </div>
    </div>
  );
}
