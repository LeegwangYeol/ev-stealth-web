import type { Metadata } from 'next';
import { getDailyReports } from '@/lib/getDailyReports';
import AdminDashboardClient from './AdminDashboardClient';

export const metadata: Metadata = {
  title: 'Daily EV Defect Monitoring - Admin Reports',
  description: '내부 모니터링 전용 비공개 데일리 EV 결함 관리자 리포트',
  robots: {
    index: false,
    follow: false,
    nocache: true,
    googleBot: {
      index: false,
      follow: false,
    },
  },
};

export default function SecretAdminReportsPage() {
  const data = getDailyReports();

  return (
    <div className="py-2">
      <AdminDashboardClient initialData={data} />
    </div>
  );
}
