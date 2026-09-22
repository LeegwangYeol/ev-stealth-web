import type { Metadata } from 'next';
import { getReliabilityTrendsData } from '@/lib/getReliabilityData';
import ReliabilityDashboardClient from './ReliabilityDashboardClient';

export const dynamic = 'force-static';

export const metadata: Metadata = {
  title: '전기차 모델·연식별 결함 통계 및 내구성 분석 (DSI) | Global EV Hub',
  description:
    '현대, 기아, 테슬라, BYD, 벤츠, BMW 등 9대 브랜드 22개 차종 89개 연식별 결함 심각도 지수(DSI), 고질병 통계, 중고차 구매 시 절대 피해야 할 연식 가이드 및 보증 외 수리비 매트릭스를 제공합니다.',
  keywords: [
    '전기차 결함 통계',
    '전기차 내구성 DSI',
    '아이오닉5 ICCU 결함',
    'EV6 결함 연식',
    '테슬라 모델3 히트펌프 옥토밸브',
    '벤츠 EQE 파라시스 배터리 화재',
    'BYD 백색가루 결함',
    '전기차 배터리 교체비용',
    '중고 전기차 피해야할 연식',
  ],
  openGraph: {
    title: '전기차 모델·연식별 결함 통계 및 내구성 분석 (DSI) | Global EV Hub',
    description:
      '9대 제조사 22개 모델 89개 연식의 실제 차주 제보 1,280건 심층 분석. 결함 심각도 지수(DSI), 연식별 위험 히트맵, 보증 외 수리비 매트릭스.',
    type: 'website',
  },
};

export default function ReliabilityAnalyticsPage() {
  const data = getReliabilityTrendsData();

  return (
    <div className="py-6 sm:py-8 space-y-6">
      <ReliabilityDashboardClient initialData={data} />
    </div>
  );
}
