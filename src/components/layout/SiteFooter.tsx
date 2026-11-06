import React, { memo } from 'react';

const SiteFooter = memo(function SiteFooter() {
  return (
    <footer
      role="contentinfo"
      aria-label="법적 고지 및 데이터 출처"
      className="bg-slate-900 border-t border-slate-700 text-center py-8 px-4 text-xs text-slate-300 space-y-3 print:hidden"
    >
      <div className="flex flex-wrap justify-center items-center gap-x-3 gap-y-1">
        <span className="font-semibold text-slate-200">공식 데이터 출처:</span>
        <a
          href="https://www.ev.or.kr"
          target="_blank"
          rel="noopener noreferrer"
          className="text-slate-200 hover:text-white underline underline-offset-2 inline-flex items-center gap-1 min-h-[32px] px-1.5 py-1 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 transition-colors"
          aria-label="환경부 및 한국환경공단(KECO) 무공해차 통합누리집 (새 창에서 열림)"
        >
          <span>환경부 무공해차 통합누리집 (KECO)</span>
          <svg
            className="w-3.5 h-3.5 text-slate-300 shrink-0"
            width="14"
            height="14"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
            focusable="false"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
            />
          </svg>
          <span className="sr-only"> (새 창에서 열림)</span>
        </a>
        <span aria-hidden="true" className="text-slate-300">·</span>
        <a
          href="https://www.car.go.kr"
          target="_blank"
          rel="noopener noreferrer"
          className="text-slate-200 hover:text-white underline underline-offset-2 inline-flex items-center gap-1 min-h-[32px] px-1.5 py-1 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 transition-colors"
          aria-label="국토교통부(MOLIT) 자동차리콜센터 (새 창에서 열림)"
        >
          <span>국토교통부 자동차리콜센터 (MOLIT)</span>
          <svg
            className="w-3.5 h-3.5 text-slate-300 shrink-0"
            width="14"
            height="14"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
            focusable="false"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
            />
          </svg>
          <span className="sr-only"> (새 창에서 열림)</span>
        </a>
        <span aria-hidden="true" className="text-slate-300">·</span>
        <a
          href="https://www.nhtsa.gov"
          target="_blank"
          rel="noopener noreferrer"
          className="text-slate-200 hover:text-white underline underline-offset-2 inline-flex items-center gap-1 min-h-[32px] px-1.5 py-1 rounded focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 transition-colors"
          aria-label="미국 도로교통안전국(NHTSA) 공식 리콜 및 안전 데이터 (새 창에서 열림)"
        >
          <span>미국 도로교통안전국 (NHTSA)</span>
          <svg
            className="w-3.5 h-3.5 text-slate-300 shrink-0"
            width="14"
            height="14"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
            focusable="false"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
            />
          </svg>
          <span className="sr-only"> (새 창에서 열림)</span>
        </a>
      </div>
      <p className="text-[11px] text-slate-300 max-w-xl mx-auto leading-relaxed">
        본 서비스의 보조금 및 결함 정보는 공공 데이터와 실차주 제보를 기반으로 분석된 참고용 정보이며, 실제 지급 여부는 관할 지자체 공고에 따릅니다.
      </p>
      <div className="pt-1 flex flex-wrap justify-center items-center gap-2 text-slate-300 text-[11px]">
        <span>© 2026 EV Critical Issues &amp; Safety Intelligence Hub. All rights reserved.</span>
        <span aria-hidden="true">·</span>
        <a
          href="#main-content"
          className="text-slate-300 hover:text-white underline underline-offset-2 rounded px-1.5 py-0.5 min-h-[24px] inline-flex items-center gap-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 transition-colors"
          aria-label="본문 맨 위로 바로가기"
        >
          <span aria-hidden="true">↑</span>
          <span>본문 맨 위로</span>
        </a>
      </div>
    </footer>
  );
});

export default SiteFooter;
export { SiteFooter };
