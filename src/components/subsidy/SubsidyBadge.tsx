'use client';

import React from 'react';
import { AlertSeverity } from '@/types/subsidy';

export interface SubsidyBadgeProps {
  status?: AlertSeverity | string | null;
  showIcon?: boolean;
  className?: string;
}

/**
 * Pure Helper: Badge styling with opaque solid backgrounds for compliant WCAG AA contrast (> 7:1)
 */
export const getBadgeStyle = (status?: AlertSeverity | string | null): string => {
  const normalized = (status || '').toUpperCase();
  switch (normalized) {
    case 'HEALTHY':
    case 'AVAILABLE':
      return 'bg-emerald-950 text-emerald-300 border-emerald-500/50';
    case 'CAUTION':
      return 'bg-amber-950 text-amber-300 border-amber-500/50';
    case 'WARNING':
      return 'bg-orange-950 text-orange-300 border-orange-500/50';
    case 'CRITICAL':
      return 'bg-rose-950 text-rose-300 border-rose-500/50 animate-pulse motion-reduce:animate-none';
    case 'DEPLETED':
      return 'bg-slate-900 text-slate-200 border-slate-500';
    default:
      return 'bg-emerald-950 text-emerald-300 border-emerald-500/50';
  }
};

/**
 * Pure Helper: Status badge labels with accessible visual indicator
 */
export const getStatusLabel = (status?: AlertSeverity | string | null): string => {
  const normalized = (status || '').toUpperCase();
  switch (normalized) {
    case 'HEALTHY':
    case 'AVAILABLE':
      return '🟢 안정';
    case 'CAUTION':
      return '🟡 주의';
    case 'WARNING':
      return '🟠 경고';
    case 'CRITICAL':
      return '🔴 마감임박';
    case 'DEPLETED':
      return '🔒 소진';
    default:
      return '🟢 안정';
  }
};

export const SubsidyBadge = React.memo(function SubsidyBadge({
  status,
  showIcon = true,
  className = '',
}: SubsidyBadgeProps) {
  const label = getStatusLabel(status);
  const style = getBadgeStyle(status);
  const cleanLabel = label.replace(/^[^a-zA-Z0-9가-힣]+\s*/, '');

  return (
    <span
      role="status"
      aria-label={`보조금 상태: ${cleanLabel}`}
      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg text-xs font-bold border whitespace-nowrap shrink-0 ${style} ${className}`}
    >
      {showIcon ? label : cleanLabel}
    </span>
  );
});

export default SubsidyBadge;
