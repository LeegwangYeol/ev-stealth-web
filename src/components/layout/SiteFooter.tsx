import React from 'react';

export default function SiteFooter() {
  return (
    <footer
      role="contentinfo"
      aria-label="법적 고지 및 데이터 출처"
      className="bg-slate-900 border-t border-slate-800 text-center py-8 px-4 text-xs text-slate-400 space-y-3"
    >
      <div className="flex flex-wrap justify-center items-center gap-x-3 gap-y-1">
        <span className="font-semibold text-slate-300">공식 데이터 출처:</span>
        <a
          href="https://www.ev.or.kr"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-white underline underline-offset-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded px-1"
          aria-label="환경부 및 한국환경공단(KECO) 무공해차 통합누리집 (새 창에서 열림)"
        >
          환경부 무공해차 통합누리집 (KECO)
          <span className="sr-only"> (새 창에서 열림)</span>
        </a>
        <span aria-hidden="true" className="text-slate-600">·</span>
        <a
          href="https://www.car.go.kr"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-white underline underline-offset-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded px-1"
          aria-label="국토교통부(MOLIT) 자동차리콜센터 (새 창에서 열림)"
        >
          국토교통부 자동차리콜센터 (MOLIT)
          <span className="sr-only"> (새 창에서 열림)</span>
        </a>
        <span aria-hidden="true" className="text-slate-600">·</span>
        <a
          href="https://www.nhtsa.gov"
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-white underline underline-offset-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded px-1"
          aria-label="미국 도로교통안전국(NHTSA) 공식 리콜 및 안전 데이터 (새 창에서 열림)"
        >
          미국 도로교통안전국 (NHTSA)
          <span className="sr-only"> (새 창에서 열림)</span>
        </a>
      </div>
      <p className="text-[11px] text-slate-400 max-w-xl mx-auto leading-relaxed">
        본 서비스의 보조금 및 결함 정보는 공공 데이터와 실차주 제보를 기반으로 분석된 참고용 정보이며, 실제 지급 여부는 관할 지자체 공고에 따릅니다.
      </p>
      <div className="pt-1 text-slate-400 text-[11px]">
        © 2026 EV Critical Issues &amp; Safety Intelligence Hub. All rights reserved.
      </div>
    </footer>
  );
}

export { SiteFooter };
