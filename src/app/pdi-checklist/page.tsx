import type { Metadata } from 'next';
import PdiChecklistClient from './PdiChecklistClient';

export const dynamic = 'force-static';

export const metadata: Metadata = {
  title: '전기차 신차 인수(PDI) 체크리스트 | Global EV Hub',
  description: '전기차 신차 탁송 인수 전 필수 PDI 점검 항목 및 체크리스트. 인수증 서명 전 단차, 도장, 배터리팩 찍힘 등 확인.',
};

export default function PdiChecklistPage() {
  return <PdiChecklistClient />;
}
