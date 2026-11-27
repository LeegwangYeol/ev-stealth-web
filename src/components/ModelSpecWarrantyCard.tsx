import React, { memo } from 'react';

export interface ModelSpecWarrantyProps {
  modelName: string;
  badge?: string;
  msrpRange: string;
  effectivePriceRange: string;
  usedPriceRange?: string;
  batterySpecs: {
    capacity: string;
    chemistry: string;
    voltage: string;
    range: string;
  };
  warranty: {
    batteryYearsKm: string;
    batteryGuaranteeSoh?: string;
    generalYearsKm: string;
    outOfWarrantyRisk?: string;
  };
}

const safeTrim = (value: unknown, fallback = ''): string => {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  return trimmed || fallback;
};

export const ModelSpecWarrantyCard = memo(function ModelSpecWarrantyCard({
  modelName,
  badge,
  msrpRange,
  effectivePriceRange,
  usedPriceRange,
  batterySpecs,
  warranty,
}: ModelSpecWarrantyProps) {
  const safeModelName = safeTrim(modelName, '전기차 모델');
  const safeBadge = safeTrim(badge);
  const safeMsrpRange = safeTrim(msrpRange, '-');
  const safeEffectivePriceRange = safeTrim(effectivePriceRange, '-');
  const safeUsedPriceRange = safeTrim(usedPriceRange);
  const safeCapacity = safeTrim(batterySpecs?.capacity, '-');
  const safeChemistry = safeTrim(batterySpecs?.chemistry, '-');
  const safeVoltage = safeTrim(batterySpecs?.voltage, '-');
  const safeRange = safeTrim(batterySpecs?.range, '-');
  const safeBatteryYearsKm = safeTrim(warranty?.batteryYearsKm, '-');
  const safeBatteryGuaranteeSoh = safeTrim(warranty?.batteryGuaranteeSoh);
  const safeGeneralYearsKm = safeTrim(warranty?.generalYearsKm, '-');
  const safeOutOfWarrantyRisk = safeTrim(warranty?.outOfWarrantyRisk);

  const renderSpecValue = (val: string) =>
    val === '-' ? (
      <>
        <span className="sr-only">정보 없음</span>
        <span aria-hidden="true">-</span>
      </>
    ) : (
      val
    );

  return (
    <div
      role="region"
      aria-label={`${safeModelName} 핵심 제원 및 공식 보증 가이드`}
      className="rounded-2xl border border-slate-200/90 bg-white p-4 sm:p-5 shadow-sm space-y-3.5 transition-colors hover:border-slate-300"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2.5">
        <h3 className="text-base sm:text-lg font-bold text-slate-900 flex items-center gap-2 min-w-0">
          <span className="text-blue-600 text-lg sm:text-xl shrink-0" aria-hidden="true">
            📋
          </span>
          <span className="min-w-0 break-words">{safeModelName} 제원 · 공식 보증 · 실구매가</span>
        </h3>
        {safeBadge && (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold bg-blue-50 text-blue-800 border border-blue-200/60">
            <span className="sr-only">모델 특징: </span>
            {safeBadge}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* Pricing Guide Card */}
        <div className="rounded-xl border border-blue-100 bg-blue-50/40 p-3 sm:p-3.5 space-y-1.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold text-blue-900 flex items-center gap-1">
              <span aria-hidden="true">🏷️</span> 가격 가이드 (신차/중고)
            </h4>
          </div>
          <dl className="text-xs space-y-1 text-slate-700">
            <div className="flex justify-between items-baseline gap-2">
              <dt className="text-slate-600 font-medium shrink-0">신차 출고가:</dt>
              <dd className="font-semibold text-slate-900 text-right break-words min-w-0">{renderSpecValue(safeMsrpRange)}</dd>
            </div>
            <div className="flex justify-between items-baseline gap-2">
              <dt className="text-slate-600 font-medium shrink-0">보조금 실구매:</dt>
              <dd className="font-bold text-blue-700 text-right break-words min-w-0">{renderSpecValue(safeEffectivePriceRange)}</dd>
            </div>
            {safeUsedPriceRange && (
              <div className="flex justify-between items-baseline gap-2 pt-1 border-t border-blue-200/50">
                <dt className="text-slate-600 font-medium shrink-0">중고차 시세:</dt>
                <dd className="font-semibold text-emerald-800 text-right break-words min-w-0">
                  {renderSpecValue(safeUsedPriceRange)}
                </dd>
              </div>
            )}
          </dl>
        </div>

        {/* Battery & Powertrain Specs Card */}
        <div className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-3 sm:p-3.5 space-y-1.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold text-emerald-900 flex items-center gap-1">
              <span aria-hidden="true">🔋</span> 배터리 &amp; 주행 스펙
            </h4>
          </div>
          <dl className="text-xs space-y-1 text-slate-700">
            <div className="flex justify-between items-baseline gap-2">
              <dt className="text-slate-600 font-medium shrink-0">배터리 용량:</dt>
              <dd className="font-semibold text-slate-900 text-right break-words min-w-0">{renderSpecValue(safeCapacity)}</dd>
            </div>
            <div className="flex justify-between items-baseline gap-2">
              <dt className="text-slate-600 font-medium shrink-0">양극재 / 셀:</dt>
              <dd className="font-semibold text-slate-900 text-right break-keep break-words leading-tight min-w-0">
                {renderSpecValue(safeChemistry)}
              </dd>
            </div>
            <div className="flex justify-between items-baseline gap-2">
              <dt className="text-slate-600 font-medium shrink-0">충전 시스템:</dt>
              <dd className="font-semibold text-slate-900 text-right break-keep break-words leading-tight min-w-0">
                {renderSpecValue(safeVoltage)}
              </dd>
            </div>
            <div className="flex justify-between items-baseline gap-2 pt-1 border-t border-emerald-200/50">
              <dt className="text-slate-600 font-medium shrink-0">복합 주행거리:</dt>
              <dd className="font-bold text-emerald-800 text-right break-words min-w-0">{renderSpecValue(safeRange)}</dd>
            </div>
          </dl>
        </div>

        {/* Official Factory Warranty Card */}
        <div className="rounded-xl border border-indigo-100 bg-indigo-50/40 p-3 sm:p-3.5 space-y-1.5 flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-bold text-indigo-900 flex items-center gap-1">
              <span aria-hidden="true">🛡️</span> 제조사 공식 보증 (워런티)
            </h4>
          </div>
          <dl className="text-xs space-y-1 text-slate-700">
            <div className="flex justify-between items-baseline gap-2">
              <dt className="text-slate-600 font-medium shrink-0">배터리/구동계:</dt>
              <dd className="font-bold text-indigo-800 text-right break-words min-w-0">{renderSpecValue(safeBatteryYearsKm)}</dd>
            </div>
            {safeBatteryGuaranteeSoh && (
              <div className="flex justify-between items-baseline gap-2">
                <dt className="text-slate-600 font-medium shrink-0">성능 보증:</dt>
                <dd className="font-medium text-slate-700 text-right break-words min-w-0">
                  {renderSpecValue(safeBatteryGuaranteeSoh)}
                </dd>
              </div>
            )}
            <div className="flex justify-between items-baseline gap-2">
              <dt className="text-slate-600 font-medium shrink-0">차체 / 일반:</dt>
              <dd className="font-semibold text-slate-900 text-right break-words min-w-0">{renderSpecValue(safeGeneralYearsKm)}</dd>
            </div>
          </dl>
          {safeOutOfWarrantyRisk && (
            <div className="pt-1 border-t border-indigo-200/50">
              <p className="text-[11px] text-rose-800 leading-tight">
                <span className="font-bold">
                  <span aria-hidden="true">⚠️ </span>보증 만료 위험:
                </span>{' '}
                {safeOutOfWarrantyRisk}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

export default ModelSpecWarrantyCard;
