import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

import Link from "next/link";
import Script from "next/script";

export const metadata: Metadata = {
  title: "Global EV Critical Issues Hub",
  description: "글로벌 전기차 결함 및 수리비 폭탄 리포트",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-gray-50 text-gray-900`}
      >
        {/* Global Skip Navigation Link */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50 focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white focus:font-bold focus:rounded-lg focus:shadow-2xl focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          본문 바로가기
        </a>

        <header className="bg-slate-900 text-white shadow-md sticky top-0 z-50">
          <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
            <Link href="/" className="text-xl font-bold tracking-tight hover:text-blue-300 transition shrink-0 flex items-center gap-2">
              <span>⚡</span> Global EV Hub
            </Link>

            {/* Desktop Navigation Bar */}
            <nav aria-label="데스크톱 내비게이션" data-testid="desktop-nav" className="hidden md:flex flex-wrap items-center justify-end gap-x-2 lg:gap-x-3 gap-y-1 text-xs lg:text-sm font-medium">
              <Link href="/subsidy-tracker" className="text-amber-400 hover:text-white font-semibold transition flex items-center gap-1 px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 focus:ring-offset-slate-900">
                <span>⚡</span> 보조금 실시간 소진율
              </Link>
              <Link href="/depreciation-calculator" className="text-emerald-400 hover:text-white font-semibold transition flex items-center gap-1 px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 focus:ring-offset-slate-900">
                <span>📉</span> 감가·배터리 계산기
              </Link>
              <Link href="/reliability-analytics" className="text-blue-300 hover:text-white font-semibold transition flex items-center gap-1 px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 focus:ring-offset-slate-900">
                <span>📊</span> 결함·신뢰성 통계
              </Link>
              <Link href="/recall-portal" className="text-slate-200 hover:text-white font-medium transition flex items-center gap-1 px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 focus:ring-offset-slate-900">
                <span>🚨</span> 공식 리콜 포털
              </Link>
              <Link href="/2026-latest" className="text-slate-200 hover:text-white font-medium transition px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 focus:ring-offset-slate-900">
                2026 최신 결함
              </Link>
              <Link href="/pdi-checklist" className="text-slate-200 hover:text-white font-medium transition px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 focus:ring-offset-slate-900">
                PDI 체크리스트
              </Link>
              <Link href="/hyundai-kia" className="text-slate-200 hover:text-white font-medium transition px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 focus:ring-offset-slate-900">
                현대/기아
              </Link>
              <Link href="/tesla" className="text-slate-200 hover:text-white font-medium transition px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 focus:ring-offset-slate-900">
                테슬라
              </Link>
              <Link href="/byd" className="text-slate-200 hover:text-white font-medium transition px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 focus:ring-offset-slate-900">
                BYD
              </Link>
              <Link href="/global-brands" className="text-slate-200 hover:text-white font-medium transition px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:ring-offset-2 focus:ring-offset-slate-900">
                기타 글로벌
              </Link>
            </nav>

            {/* Mobile Drawer Menu Toggle */}
            <details className="md:hidden relative group" id="mobile-nav-drawer" data-testid="mobile-drawer-toggle">
              <summary
                className="list-none flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white text-sm font-medium cursor-pointer border border-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-400 select-none"
              >
                <svg className="w-5 h-5 block group-open:hidden" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
                <svg className="w-5 h-5 hidden group-open:block" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
                <span className="group-open:hidden">메뉴 열기</span>
                <span className="hidden group-open:inline">메뉴 닫기</span>
              </summary>

              {/* Mobile Drawer Content */}
              <nav
                aria-label="모바일 서랍 메뉴"
                data-testid="mobile-drawer"
                className="absolute right-0 mt-2 w-72 max-w-[calc(100vw-2rem)] bg-slate-900 border border-slate-700 rounded-xl shadow-2xl p-4 flex flex-col gap-1.5 z-50 animate-in fade-in slide-in-from-top-2 duration-200 text-sm"
              >
                <div className="text-xs font-semibold text-slate-400 px-2 py-1 uppercase tracking-wider border-b border-slate-800 pb-2 flex items-center justify-between">
                  <span>모바일 메뉴</span>
                  <span className="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded border border-blue-500/30">Global EV</span>
                </div>
                <Link
                  href="/subsidy-tracker"
                  className="px-3 py-2 rounded-lg bg-amber-950/60 border border-amber-500/50 text-amber-300 hover:text-white font-semibold transition flex items-center justify-between focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  <span className="flex items-center gap-2">
                    <span>⚡</span> [실시간] 전국 보조금 소진율 추적기
                  </span>
                  <span className="text-[10px] bg-amber-400 text-slate-950 font-extrabold px-1.5 py-0.5 rounded">LIVE</span>
                </Link>
                <Link
                  href="/depreciation-calculator"
                  className="px-3 py-2 rounded-lg bg-emerald-950/60 border border-emerald-500/50 text-emerald-300 hover:text-white font-semibold transition flex items-center justify-between focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  <span className="flex items-center gap-2">
                    <span>📉</span> 감가·배터리 계산기
                  </span>
                  <span className="text-[10px] bg-emerald-400 text-slate-950 font-extrabold px-1.5 py-0.5 rounded">신규</span>
                </Link>
                <Link
                  href="/reliability-analytics"
                  className="px-3 py-2 rounded-lg hover:bg-slate-800 text-blue-300 hover:text-white font-semibold transition flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  <span>📊</span> 신뢰성 통계
                </Link>
                <Link
                  href="/recall-portal"
                  className="px-3 py-2 rounded-lg hover:bg-slate-800 text-slate-200 hover:text-white font-medium transition flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  <span>🚨</span> 리콜 포털
                </Link>
                <Link
                  href="/2026-latest"
                  className="px-3 py-2 rounded-lg hover:bg-slate-800 text-slate-200 hover:text-white font-medium transition flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  <span>🔥</span> 2026 최신 결함
                </Link>
                <Link
                  href="/pdi-checklist"
                  className="px-3 py-2 rounded-lg hover:bg-slate-800 text-slate-200 hover:text-white font-medium transition flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  <span>✅</span> PDI 체크리스트
                </Link>
                <div className="h-px border-t border-slate-800 my-1" />
                <div className="text-[11px] font-semibold text-slate-400 px-2 py-0.5">제조사별 피하기 가이드</div>
                <div className="grid grid-cols-2 gap-1">
                  <Link href="/hyundai-kia" className="px-2.5 py-1.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white text-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">
                    현대/기아
                  </Link>
                  <Link href="/tesla" className="px-2.5 py-1.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white text-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">
                    테슬라
                  </Link>
                  <Link href="/byd" className="px-2.5 py-1.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white text-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">
                    BYD
                  </Link>
                  <Link href="/global-brands" className="px-2.5 py-1.5 rounded hover:bg-slate-800 text-slate-300 hover:text-white text-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">
                    기타 글로벌
                  </Link>
                </div>
              </nav>
            </details>
          </div>
        </header>
        <main id="main-content" className="max-w-6xl mx-auto p-6 min-h-screen">
          {children}
        </main>
        <footer className="bg-gray-200 text-center p-6 text-sm text-gray-600">
          © 2026 EV Critical Issues & Safety Intelligence Hub
        </footer>

        {/* Mobile nav drawer auto-close on internal link click & Escape key listener with focus return */}
        <Script
          id="mobile-nav-script"
          strategy="afterInteractive"
          dangerouslySetInnerHTML={{
            __html: `
              document.addEventListener('click', function(e) {
                var drawer = document.getElementById('mobile-nav-drawer');
                if (drawer && drawer.hasAttribute('open')) {
                  var target = e.target;
                  if (target && target.closest && target.closest('#mobile-nav-drawer a')) {
                    drawer.removeAttribute('open');
                  }
                }
              });
              document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape' || e.key === 'Esc') {
                  var drawer = document.getElementById('mobile-nav-drawer');
                  if (drawer && drawer.hasAttribute('open')) {
                    drawer.removeAttribute('open');
                    var summary = drawer.querySelector('summary');
                    if (summary) {
                      summary.focus();
                    }
                  }
                }
              });
            `,
          }}
        />
      </body>
    </html>
  );
}
