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
          <div className="max-w-6xl mx-auto flex justify-between items-center">
            <Link href="/" className="text-xl font-bold tracking-tight hover:text-blue-300 transition">
              Global EV Hub
            </Link>
            <div className="flex gap-4">
              <Link href="/2026-latest" className="text-slate-600 hover:text-slate-900 font-medium">
                2026 최신 결함
              </Link>
              <Link href="/pdi-checklist" className="text-slate-600 hover:text-slate-900 font-medium">
                PDI 체크리스트
              </Link>
              <Link href="/hyundai-kia" className="text-slate-600 hover:text-slate-900 font-medium">
                현대/기아
              </Link>
              <Link href="/tesla" className="text-slate-600 hover:text-slate-900 font-medium">
                테슬라
              </Link>
              <Link href="/byd" className="text-slate-600 hover:text-slate-900 font-medium">
                BYD
              </Link>
              <Link href="/global-brands" className="text-slate-600 hover:text-slate-900 font-medium">
                기타 글로벌
              </Link>
            </div>
          </div>
        </nav>
        <main className="max-w-6xl mx-auto p-6 min-h-screen">
          {children}
        </main>
        <footer className="bg-gray-200 text-center p-6 text-sm text-gray-600">
          © 2026 Max - EV & Minivelo Customization Assistant
        </footer>
      </body>
    </html>
  );
}
