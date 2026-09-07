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
  title: "EV & Stealth Minivelo Hub",
  description: "글로벌 전기차 결함 및 미니벨로 스텔스 개조 가이드",
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
              EV & Stealth Hub
            </Link>
            <div className="flex gap-6 text-sm font-medium">
              <Link href="/global-ev" className="hover:text-blue-400 transition">글로벌 EV 결함</Link>
              <Link href="/emerging-ev" className="hover:text-blue-400 transition">신흥 EV 트랩</Link>
              <Link href="/stealth-minivelo" className="hover:text-blue-400 transition">스텔스 미니벨로 개조</Link>
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
