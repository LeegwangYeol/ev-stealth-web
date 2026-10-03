import { Suspense } from 'react';
import type { Metadata } from 'next';
import { getRecallDatabase } from '@/lib/getRecallData';
import RecallPortalClient from './RecallPortalClient';

export const metadata: Metadata = {
  title: '전기차 공식 리콜 & 배터리 제조사 화재 안전 포털 | Global EV Hub',
  description:
    '대한민국 국토교통부(MOLIT) 및 미국 NHTSA 공식 전기차 리콜 캠페인 실시간 조회. 17자리 차대번호(VIN) 및 차종별 배터리 셀 제조사(파라시스, LG에너지솔루션, SK온, CATL, 삼성SDI 등), 화재 위험도 및 아파트 지하주차장 충전 안전 가이드 제공.',
  keywords: [
    '전기차 리콜 조회',
    '전기차 배터리 제조사',
    '전기차 차대번호 조회',
    'VIN 리콜 조회',
    '전기차 화재',
    '파라시스 배터리',
    '벤츠 EQE 화재',
    'ICCU 결함',
    '아이오닉5 리콜',
    'EV6 리콜',
    '테슬라 리콜',
    '아파트 지하주차장 전기차',
  ],
  openGraph: {
    title: '전기차 공식 리콜 & 배터리 제조사 화재 안전 포털',
    description:
      '내 차 배터리 제조사와 공식 리콜을 1초 만에 확인하세요. 국토교통부 공시 데이터 및 지하주차장 안전 가이드 탑재.',
    type: 'website',
    locale: 'ko_KR',
  },
};

export default function RecallPortalPage() {
  const database = getRecallDatabase();
  return (
    <Suspense
      fallback={
        <div role="status" aria-live="polite" className="min-h-screen bg-slate-900 text-slate-100 flex items-center justify-center p-8">
          <div className="text-center space-y-3">
            <div className="text-3xl animate-pulse motion-reduce:animate-none" aria-hidden="true">⚡</div>
            <div className="text-sm font-semibold text-slate-400">
              전기차 리콜 & 배터리 데이터베이스 로딩 중...
            </div>
          </div>
        </div>
      }
    >
      <RecallPortalClient initialDatabase={database} />
    </Suspense>
  );
}
