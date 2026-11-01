'use client';

import { useEffect } from 'react';
import Link from 'next/link';

interface RecallErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * Next.js Segment Error Boundary: Recall Portal (/recall-portal)
 * Catches unhandled exceptions during VIN decoding and recall database searches.
 */
export default function RecallPortalError({ error, reset }: RecallErrorProps) {
  useEffect(() => {
    console.error('Unhandled Recall Portal route error:', error);
  }, [error]);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="min-h-[60vh] flex items-center justify-center px-4 py-12"
    >
      <div className="max-w-xl w-full bg-white border border-rose-200 rounded-3xl p-8 sm:p-10 shadow-xl text-center space-y-6">
        <div
          className="w-16 h-16 mx-auto rounded-2xl bg-rose-50 border border-rose-200 text-rose-600 flex items-center justify-center text-3xl shadow-inner"
          aria-hidden="true"
        >
          🚨
        </div>

        <div className="space-y-3">
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            공식 리콜 정보를 불러올 수 없습니다
          </h1>
          <p className="text-sm sm:text-base text-slate-600 leading-relaxed max-w-md mx-auto">
            국토교통부 자동차리콜센터 연동 및 배터리 제조사 안전 데이터베이스 검색 중 오류가 발생했습니다.
            아래 &apos;다시 시도&apos; 버튼을 눌러 안전하게 재조회해 주세요.
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
            aria-label="리콜 포털 다시 시도"
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-rose-600 hover:bg-rose-700 text-white font-bold shadow-md transition focus:outline-none focus-visible:ring-2 focus-visible:ring-rose-500 focus-visible:ring-offset-2"
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
          <Link href="/reliability-analytics" prefetch={false} className="hover:text-blue-600 transition">
            📊 결함 분석 포털
          </Link>
          <Link href="/subsidy-tracker" prefetch={true} className="hover:text-amber-600 transition">
            ⚡ 보조금 추적기
          </Link>
          <Link href="/pdi-checklist" prefetch={false} className="hover:text-cyan-600 transition">
            ✅ PDI 체크리스트
          </Link>
        </div>
      </div>
    </div>
  );
}
