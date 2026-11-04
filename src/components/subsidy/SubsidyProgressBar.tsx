'use client';

import React, { memo } from 'react';
import { getStatusLabel } from './SubsidyBadge';

export interface SubsidyProgressBarProps {
  depletionRate: number;
  deliveredUnits: number;
  appliedUnits: number;
  remainingUnits: number;
  announcedUnits: number;
  regionName: string;
  categoryLabel: string;
  status?: string;
  showDetails?: boolean;
}

export const SubsidyProgressBar = memo(function SubsidyProgressBar({
  depletionRate,
  deliveredUnits,
  appliedUnits,
  remainingUnits,
  announcedUnits,
  regionName,
  categoryLabel,
  status = 'available',
  showDetails = true,
}: SubsidyProgressBarProps) {
  const safeRegionName = (regionName || '해당 지역').trim();
  const safeCategoryLabel = (categoryLabel || '전기차').trim();
  const displayAnnounced = Number.isFinite(announcedUnits) && announcedUnits > 0 ? announcedUnits : 0;
  const safeAnnounced = displayAnnounced > 0 ? displayAnnounced : 1;
  const safeDelivered = Number.isFinite(deliveredUnits) ? Math.max(0, deliveredUnits) : 0;
  const safeApplied = Number.isFinite(appliedUnits) ? Math.max(0, appliedUnits) : 0;
  const safeDepletion = Number.isFinite(depletionRate)
    ? Math.max(0, depletionRate)
    : displayAnnounced > 0
    ? (safeApplied / safeAnnounced) * 100
    : 0;
  const safeRemaining = Number.isFinite(remainingUnits)
    ? Math.max(0, remainingUnits)
    : Math.max(0, displayAnnounced - safeApplied);

  const rawDeliveredPct = displayAnnounced > 0 ? Math.round((safeDelivered / safeAnnounced) * 100) : 0;
  const deliveredPct = Number.isFinite(rawDeliveredPct) ? Math.min(100, Math.max(0, rawDeliveredPct)) : 0;
  const rawPendingPct = safeDepletion - deliveredPct;
  const pendingPct = Number.isFinite(rawPendingPct) ? Math.max(0, Math.min(100 - deliveredPct, rawPendingPct)) : 0;
  const remainingPct = Math.max(0, 100 - (deliveredPct + pendingPct));
  const pendingCount = Math.max(0, safeApplied - safeDelivered);

  return (
    <div className="space-y-1.5 pt-1">
      {showDetails && (
        <div className="flex justify-between items-center text-xs">
          <span className="font-semibold text-slate-300">
            소진율 <strong className="text-amber-400 text-sm">{safeDepletion.toFixed(1)}%</strong>
          </span>
          <span className="text-slate-300 text-[11px] font-medium">
            잔여 <strong className="text-emerald-400 font-bold">{safeRemaining.toLocaleString()}</strong> / {displayAnnounced.toLocaleString()}대
          </span>
        </div>
      )}

      {/* WCAG AA Multi-Layer Progress Bar with Non-Text Contrast >= 3:1 */}
      <div
        role="progressbar"
        aria-valuenow={Math.min(100, Math.max(0, Math.round(safeDepletion)))}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${safeRegionName} ${safeCategoryLabel} 보조금 소진율`}
        aria-valuetext={`소진율 ${safeDepletion.toFixed(1)}% (${getStatusLabel(status)}), 잔여 ${safeRemaining.toLocaleString()}대`}
        className="w-full bg-slate-950 rounded-full h-3.5 overflow-hidden flex relative border border-slate-600"
      >
        {/* Layer 1: Confirmed Delivered */}
        {deliveredPct > 0 && (
          <div
            style={{ width: `${deliveredPct}%` }}
            className="bg-blue-500 h-full border-r border-slate-950 transition-all duration-500"
            title={`출고 완료: ${safeDelivered.toLocaleString()}대 (${deliveredPct}%)`}
          />
        )}
        {/* Layer 2: Pending Applications */}
        {pendingPct > 0 && (
          <div
            style={{ width: `${pendingPct}%` }}
            className="bg-amber-400 h-full border-r border-slate-950 transition-all duration-500"
            title={`접수 대기: ${pendingCount.toLocaleString()}대 (${pendingPct.toFixed(1)}%)`}
          />
        )}
        {/* Layer 3: Remaining (slate track with >= 3:1 contrast against bg-slate-950) */}
        {remainingPct > 0 && (
          <div
            style={{ width: `${remainingPct}%` }}
            className="bg-slate-700 h-full"
            title={`잔여: ${safeRemaining.toLocaleString()}대 (${remainingPct.toFixed(1)}%)`}
          />
        )}
      </div>

      {showDetails && (
        <div className="flex flex-wrap gap-x-2 gap-y-0.5 justify-between text-[10px] sm:text-[11px] text-slate-300 font-medium pt-0.5">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-blue-500 inline-block" aria-hidden="true" />
            출고 {safeDelivered.toLocaleString()}대
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" aria-hidden="true" />
            심사중 {pendingCount.toLocaleString()}대
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-slate-300 inline-block border border-slate-500" aria-hidden="true" />
            잔여 {safeRemaining.toLocaleString()}대
          </span>
        </div>
      )}
    </div>
  );
});

export default SubsidyProgressBar;
