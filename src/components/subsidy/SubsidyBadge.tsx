'use client';

import React from 'react';
import { AlertSeverity } from '@/types/subsidy';
import { getBadgeStyle, getStatusLabel } from '@/lib/subsidyCalculations';

export { getBadgeStyle, getStatusLabel };

export interface SubsidyBadgeProps {
  status?: AlertSeverity | string | null;
  showIcon?: boolean;
  className?: string;
}

export const SubsidyBadge = React.memo(function SubsidyBadge({
  status,
  showIcon = true,
  className = '',
}: SubsidyBadgeProps) {
  const label = getStatusLabel(status);
  const style = getBadgeStyle(status);
  const cleanLabel = label.replace(/^[^a-zA-Z0-9가-힣]+\s*/, '');
  const emoji = label.match(/^[^a-zA-Z0-9가-힣]+/)?.[0]?.trim() || '';

  return (
    <span
      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg text-xs font-bold border whitespace-nowrap shrink-0 ${style} ${className}`}
    >
      <span className="sr-only">보조금 상태: </span>
      {showIcon && emoji && <span aria-hidden="true">{emoji} </span>}
      <span>{cleanLabel}</span>
    </span>
  );
});

export default SubsidyBadge;
