import { Suspense } from 'react';
import type { Metadata } from 'next';
import { getSubsidyDatabase } from '@/lib/getSubsidyData';
import SubsidyTrackerClient from './SubsidyTrackerClient';

export const dynamic = 'force-static';

export const metadata: Metadata = {
  title: '전국 지자체별 전기차 실시간 보조금 소진율 추적기 | EV Stealth Web',
  description:
    '2026년 환경부 무공해차 통합누리집(ev.or.kr) 및 17개 광역시도 지자체별 전기차 실시간 보조금 소진율, 접수·출고 대수, 잔여 쿼터 긴급 소진 경보 및 실구매 체감가 시뮬레이션 계산기.',
  keywords: [
    '전기차 보조금 소진율',
    '전국 지자체 보조금',
    '2026 전기차 보조금',
    '전기차 실구매가 계산기',
    '환경부 보조금',
    '무공해차 통합누리집',
    '서울시 전기차 보조금',
    '경기도 전기차 보조금',
    '보조금 잔여대수',
    '보조금 마감 임박',
    '아이오닉5 보조금',
    'EV3 보조금',
    '모델Y 보조금',
  ],
  openGraph: {
    title: '전국 지자체별 전기차 실시간 보조금 소진율 추적기 | EV Stealth Web',
    description:
      '내 거주 지자체의 전기차 보조금 잔여량과 5단계 소진 경보, 차종별 5,500만/8,500만 원 상한제 실구매가를 실시간으로 계산하세요.',
    type: 'website',
    locale: 'ko_KR',
  },
};

export default function SubsidyTrackerPage() {
  const database = getSubsidyDatabase();

  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-slate-900 text-slate-100 flex items-center justify-center p-8">
          <div className="text-center space-y-3">
            <div className="text-4xl animate-bounce">⚡</div>
            <div className="text-base font-bold text-amber-400">
              전국 지자체별 보조금 소진율 데이터 로딩 중...
            </div>
            <p className="text-xs text-slate-400">
              환경부 및 17개 시도 실시간 쿼터 집계 분석 중입니다.
            </p>
          </div>
        </div>
      }
    >
      <SubsidyTrackerClient initialData={database} />
    </Suspense>
  );
}
