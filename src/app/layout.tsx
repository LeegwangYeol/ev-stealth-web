import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
  display: "swap",
  fallback: [
    "Pretendard",
    "-apple-system",
    "BlinkMacSystemFont",
    "system-ui",
    "Apple SD Gothic Neo",
    "Noto Sans KR",
    "Malgun Gothic",
    "Roboto",
    "sans-serif",
  ],
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
  display: "swap",
  preload: false,
  fallback: [
    "ui-monospace",
    "SFMono-Regular",
    "Menlo",
    "Monaco",
    "Consolas",
    "monospace",
  ],
});

import Link from "next/link";
import GlobalNavListener from "@/components/GlobalNavListener";
import SiteFooter from "@/components/layout/SiteFooter";
import JsonLd from "@/components/JsonLd";

const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "https://ev-stealth-web.vercel.app").replace(/\/+$/, "");

const globalJsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "@id": `${SITE_URL}/#website`,
      "url": SITE_URL,
      "name": "Global EV Hub",
      "alternateName": ["글로벌 EV 허브", "전기차 결함 및 리콜 정보 포털"],
      "description": "글로벌 전기차 결함, 리콜 정보, 실시간 보조금 소진율 및 감가방어율 종합 분석 포털",
      "inLanguage": "ko-KR",
    },
    {
      "@type": "Organization",
      "@id": `${SITE_URL}/#organization`,
      "name": "Global EV Hub",
      "url": SITE_URL,
      "logo": `${SITE_URL}/favicon.ico`,
    },
  ],
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Global EV Critical Issues Hub | Global EV Hub",
    template: "%s | Global EV Hub",
  },
  description: "글로벌 전기차 결함, 리콜 정보, 실시간 보조금 소진율 및 감가방어율 종합 분석 포털",
  keywords: [
    "전기차 결함",
    "전기차 리콜",
    "전기차 보조금 소진율",
    "전기차 감가율",
    "배터리 SOH",
    "전기차 중고차 가이드",
    "아이오닉5 ICCU",
    "테슬라 모델3 고질병",
    "Global EV Hub",
  ],
  authors: [{ name: "Global EV Hub Research Team", url: SITE_URL }],
  creator: "Global EV Hub",
  publisher: "Global EV Hub",
  alternates: {
    canonical: "/",
  },
  icons: {
    icon: "/favicon.ico",
    shortcut: "/favicon.ico",
    apple: "/favicon.ico",
  },
  openGraph: {
    title: "Global EV Critical Issues Hub | Global EV Hub",
    description: "글로벌 전기차 결함, 리콜 정보, 실시간 보조금 소진율 및 감가방어율 종합 분석 포털",
    url: "/",
    siteName: "Global EV Hub",
    locale: "ko_KR",
    type: "website",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Global EV Hub - 글로벌 전기차 결함 및 리콜 정보 포털",
        type: "image/png",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "Global EV Critical Issues Hub | Global EV Hub",
    description: "글로벌 전기차 결함, 리콜 정보, 실시간 보조금 소진율 및 감가방어율 종합 분석 포털",
    site: "@GlobalEVHub",
    creator: "@lolollol2379",
    images: ["/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};

export const viewport: Viewport = {
  themeColor: "#0f172a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-gray-50 text-gray-900`}
      >
        <JsonLd data={globalJsonLd} />
        {/* Global Skip Navigation Link */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-3 focus:left-3 focus:z-50 focus:px-4 focus:py-2 focus:bg-blue-600 focus:text-white focus:font-bold focus:rounded-lg focus:shadow-2xl focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          본문 바로가기
        </a>

        <header role="banner" className="bg-slate-900 text-white shadow-md sticky top-0 z-50 print:hidden">
          <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
            <Link
              href="/"
              prefetch={false}
              aria-label="Global EV Hub 홈으로 이동"
              className="text-xl font-bold tracking-tight hover:text-blue-300 transition shrink-0 flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900 rounded-lg"
            >
              <span aria-hidden="true">⚡</span> Global EV Hub
            </Link>

            {/* Desktop Navigation Bar */}
            <nav aria-label="데스크톱 내비게이션" data-testid="desktop-nav" className="hidden md:flex flex-wrap items-center justify-end gap-x-2 lg:gap-x-3 gap-y-1 text-xs lg:text-sm font-medium">
              <Link href="/subsidy-tracker" prefetch={true} className="text-amber-400 hover:text-white font-semibold transition flex items-center gap-1 px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900">
                <span aria-hidden="true">⚡</span> 보조금 실시간 소진율
              </Link>
              <Link href="/depreciation-calculator" prefetch={true} className="text-emerald-400 hover:text-white font-semibold transition flex items-center gap-1 px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900">
                <span aria-hidden="true">📉</span> 감가·배터리 계산기
              </Link>
              <Link href="/reliability-analytics" prefetch={false} className="text-blue-300 hover:text-white font-semibold transition flex items-center gap-1 px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900">
                <span aria-hidden="true">📊</span> 결함·신뢰성 통계
              </Link>
              <Link href="/recall-portal" prefetch={false} className="text-slate-200 hover:text-white font-medium transition flex items-center gap-1 px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900">
                <span aria-hidden="true">🚨</span> 공식 리콜 포털
              </Link>
              <Link href="/2026-latest" prefetch={false} className="text-slate-200 hover:text-white font-medium transition px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900">
                2026 최신 결함
              </Link>
              <Link href="/pdi-checklist" prefetch={false} aria-label="신차 출고 전 점검(PDI) 체크리스트" className="text-slate-200 hover:text-white font-medium transition px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900">
                PDI 체크리스트
              </Link>
              <Link href="/hyundai-kia" prefetch={false} className="text-slate-200 hover:text-white font-medium transition px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900">
                현대/기아
              </Link>
              <Link href="/tesla" prefetch={false} className="text-slate-200 hover:text-white font-medium transition px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900">
                테슬라
              </Link>
              <Link href="/byd" prefetch={false} className="text-slate-200 hover:text-white font-medium transition px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900">
                BYD
              </Link>
              <Link href="/global-brands" prefetch={false} className="text-slate-200 hover:text-white font-medium transition px-2 py-1 rounded hover:bg-slate-800 focus:outline-none focus:ring-2 focus-visible:ring-2 focus-visible:ring-blue-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900">
                기타 글로벌
              </Link>
            </nav>

            {/* Mobile Drawer Menu Toggle */}
            <details className="md:hidden relative group" id="mobile-nav-drawer" data-testid="mobile-drawer-toggle">
              <summary
                aria-label="모바일 내비게이션 메뉴 토글"
                className="list-none flex items-center gap-1.5 px-3 py-2 min-h-[44px] rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 hover:text-white text-sm font-medium cursor-pointer border border-slate-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 select-none"
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
                <div className="text-xs font-semibold text-slate-300 px-2 py-1 uppercase tracking-wider border-b border-slate-800 pb-2 flex items-center justify-between">
                  <span>모바일 메뉴</span>
                  <span className="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded border border-blue-500/30">Global EV</span>
                </div>
                <Link
                  href="/subsidy-tracker"
                  prefetch={true}
                  className="px-3 py-2 min-h-[44px] rounded-lg bg-amber-950/60 border border-amber-500/50 text-amber-300 hover:text-white font-semibold transition flex items-center justify-between focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  <span className="flex items-center gap-2">
                    <span aria-hidden="true">⚡</span> [실시간] 전국 보조금 소진율 추적기
                  </span>
                  <span className="text-[10px] bg-amber-400 text-slate-950 font-extrabold px-1.5 py-0.5 rounded">LIVE</span>
                </Link>
                <Link
                  href="/depreciation-calculator"
                  prefetch={true}
                  className="px-3 py-2 min-h-[44px] rounded-lg bg-emerald-950/60 border border-emerald-500/50 text-emerald-300 hover:text-white font-semibold transition flex items-center justify-between focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  <span className="flex items-center gap-2">
                    <span aria-hidden="true">📉</span> 감가·배터리 계산기
                  </span>
                  <span className="text-[10px] bg-emerald-400 text-slate-950 font-extrabold px-1.5 py-0.5 rounded">신규</span>
                </Link>
                <Link
                  href="/reliability-analytics"
                  prefetch={false}
                  className="px-3 py-2 min-h-[44px] rounded-lg hover:bg-slate-800 text-blue-300 hover:text-white font-semibold transition flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  <span aria-hidden="true">📊</span> 신뢰성 통계
                </Link>
                <Link
                  href="/recall-portal"
                  prefetch={false}
                  className="px-3 py-2 min-h-[44px] rounded-lg hover:bg-slate-800 text-slate-200 hover:text-white font-medium transition flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  <span aria-hidden="true">🚨</span> 리콜 포털
                </Link>
                <Link
                  href="/2026-latest"
                  prefetch={false}
                  className="px-3 py-2 min-h-[44px] rounded-lg hover:bg-slate-800 text-slate-200 hover:text-white font-medium transition flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  <span aria-hidden="true">🔥</span> 2026 최신 결함
                </Link>
                <Link
                  href="/pdi-checklist"
                  prefetch={false}
                  aria-label="신차 출고 전 점검(PDI) 체크리스트"
                  className="px-3 py-2 min-h-[44px] rounded-lg hover:bg-slate-800 text-slate-200 hover:text-white font-medium transition flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400"
                >
                  <span aria-hidden="true">✅</span> PDI 체크리스트
                </Link>
                <div className="h-px border-t border-slate-800 my-1" />
                <div className="text-[11px] font-semibold text-slate-300 px-2 py-0.5">제조사별 피하기 가이드</div>
                <div className="grid grid-cols-2 gap-1.5">
                  <Link href="/hyundai-kia" prefetch={false} className="px-2.5 py-2 min-h-[44px] flex items-center rounded hover:bg-slate-800 text-slate-300 hover:text-white text-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">
                    현대/기아
                  </Link>
                  <Link href="/tesla" prefetch={false} className="px-2.5 py-2 min-h-[44px] flex items-center rounded hover:bg-slate-800 text-slate-300 hover:text-white text-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">
                    테슬라
                  </Link>
                  <Link href="/byd" prefetch={false} className="px-2.5 py-2 min-h-[44px] flex items-center rounded hover:bg-slate-800 text-slate-300 hover:text-white text-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">
                    BYD
                  </Link>
                  <Link href="/global-brands" prefetch={false} className="px-2.5 py-2 min-h-[44px] flex items-center rounded hover:bg-slate-800 text-slate-300 hover:text-white text-xs transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-400">
                    기타 글로벌
                  </Link>
                </div>
              </nav>
            </details>
          </div>
        </header>
        <main id="main-content" tabIndex={-1} role="main" className="max-w-6xl mx-auto p-4 sm:p-6 min-h-screen outline-none focus:outline-none">
          {children}
        </main>
        <SiteFooter />

        {/* Mobile nav drawer auto-close on internal link click & Escape key listener with focus return */}
        <GlobalNavListener />
      </body>
    </html>
  );
}
