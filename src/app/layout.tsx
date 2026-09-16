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
        <nav className="bg-slate-900 text-white p-4 shadow-md">
          <div className="max-w-6xl mx-auto flex flex-col sm:flex-row justify-between items-center gap-3 sm:gap-4">
            <Link href="/" className="text-xl font-bold tracking-tight hover:text-blue-300 transition shrink-0">
              Global EV Hub
            </Link>
            <div className="flex flex-wrap items-center justify-center sm:justify-end gap-x-3 sm:gap-x-4 gap-y-2 text-sm sm:text-base">
              <Link href="/2026-latest" className="text-slate-200 hover:text-white font-medium transition">
                2026 최신 결함
              </Link>
              <Link href="/pdi-checklist" className="text-slate-200 hover:text-white font-medium transition">
                PDI 체크리스트
              </Link>
              <Link href="/hyundai-kia" className="text-slate-200 hover:text-white font-medium transition">
                현대/기아
              </Link>
              <Link href="/tesla" className="text-slate-200 hover:text-white font-medium transition">
                테슬라
              </Link>
              <Link href="/byd" className="text-slate-200 hover:text-white font-medium transition">
                BYD
              </Link>
              <Link href="/global-brands" className="text-slate-200 hover:text-white font-medium transition">
                기타 글로벌
              </Link>
            </div>
          </div>
        </nav>
        <main className="max-w-6xl mx-auto p-6 min-h-screen">
          {children}
        </main>
        <footer className="bg-gray-200 text-center p-6 text-sm text-gray-600">
          © 2026 EV Critical Issues & Safety Intelligence Hub
        </footer>
      </body>
    </html>
  );
}
