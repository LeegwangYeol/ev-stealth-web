import type { Metadata } from 'next';
import { getDepreciationDatabase } from '@/lib/getDepreciationData';
import DepreciationCalculatorClient from './DepreciationCalculatorClient';

export const dynamic = 'force-static';

export const metadata: Metadata = {
  title: '전기차 감가방어율 & 배터리 수명 계산기 | Global EV Hub',
  description:
    '2026년 국내 실거래(엔카·케이카·국토교통부) 기반 전기차 잔존가치, 배터리 잔여수명(SoH), 2년 의무운행 보조금 환수액(대기환경보전법 제58조), 5개년 총소유비용(TCO) 실시간 정밀 시뮬레이터.',
  keywords: [
    '전기차 감가율 계산기',
    '전기차 잔존가치 계산기',
    '배터리 수명 계산기',
    '전기차 배터리 SoH',
    '전기차 보조금 환수 계산기',
    '대기환경보전법 제58조',
    '2년 의무운행기간',
    '전기차 TCO 계산기',
    '테슬라 감가율',
    '아이오닉5 감가율',
    'EV6 잔존가치',
    'BYD 잔존가치',
    '전기차 배터리 교체비용',
    '전기차 유지비 비교',
  ],
  openGraph: {
    title: '전기차 감가방어율 & 배터리 수명 계산기 (2026 국내 실거래 기반)',
    description:
      '내 차 5년 뒤 중고 시세와 배터리 수명(SoH)은? 법정 보조금 환수액 및 내연기관 대비 5개년 유지비 절감액을 1초 만에 시뮬레이션하세요.',
    type: 'website',
    locale: 'ko_KR',
    siteName: 'Global EV Hub',
  },
  twitter: {
    card: 'summary_large_image',
    title: '전기차 감가방어율 & 배터리 수명 계산기 (2026)',
    description:
      '2026년 국내 실거래 기반 잔존가치, 배터리 잔여수명(SoH), 2년 의무운행 보조금 환수율, 5개년 TCO 정밀 계산기.',
  },
};

export default function DepreciationCalculatorPage() {
  const database = getDepreciationDatabase();

  return (
    <div className="py-4 sm:py-6 space-y-6">
      <DepreciationCalculatorClient initialDatabase={database} />
    </div>
  );
}
