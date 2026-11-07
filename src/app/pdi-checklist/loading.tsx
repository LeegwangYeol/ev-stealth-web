export default function PdiChecklistLoading() {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="PDI 신차 출고 전 체크리스트 로딩 중"
      className="space-y-8 py-6 max-w-4xl mx-auto animate-pulse motion-reduce:animate-none"
    >
      <span className="sr-only">신차 출고 전 체크리스트를 불러오는 중입니다...</span>

      {/* Visual Placeholder Skeletons */}
      <div aria-hidden="true" className="space-y-8">
        {/* Header Skeleton */}
        <div className="space-y-3">
          <div className="h-8 sm:h-10 bg-slate-200 rounded-2xl w-3/4 max-w-lg" />
          <div className="h-4 sm:h-5 bg-slate-100 rounded-xl w-5/6" />
        </div>

        {/* Progress Bar Skeleton */}
        <div className="p-6 rounded-3xl bg-white border border-slate-200/80 shadow-sm space-y-3">
          <div className="flex justify-between items-center">
            <div className="h-4 bg-slate-200 rounded w-28" />
            <div className="h-4 bg-slate-200 rounded w-16" />
          </div>
          <div className="h-3 bg-slate-100 rounded-full w-full" />
        </div>

        {/* Checklist Items Skeletons */}
        <div className="space-y-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-sm flex items-start gap-4"
            >
              <div className="h-6 w-6 rounded-lg bg-slate-200 shrink-0 mt-0.5" />
              <div className="space-y-2 flex-1">
                <div className="h-4 bg-slate-200 rounded w-2/3" />
                <div className="h-3 bg-slate-100 rounded w-1/3" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
