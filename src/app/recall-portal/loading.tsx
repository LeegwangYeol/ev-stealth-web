export default function RecallPortalLoading() {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="공식 리콜 및 배터리 안전 포털 로딩 중"
      className="space-y-8 py-6 animate-pulse motion-reduce:animate-none"
    >
      <span className="sr-only">공식 리콜 및 배터리 안전 포털 데이터를 불러오는 중입니다...</span>

      {/* Visual Placeholder Skeletons */}
      <div aria-hidden="true" className="space-y-8">
        {/* Header Skeleton */}
        <div className="space-y-3">
          <div className="h-8 sm:h-10 bg-slate-200 rounded-2xl w-3/4 max-w-xl" />
          <div className="h-4 sm:h-5 bg-slate-100 rounded-xl w-5/6 max-w-2xl" />
        </div>

        {/* Search & Mode Switcher Skeleton */}
        <div className="p-6 rounded-3xl bg-white border border-slate-200/80 shadow-sm space-y-5">
          <div className="flex gap-3">
            <div className="h-10 w-40 bg-slate-200 rounded-xl" />
            <div className="h-10 w-40 bg-slate-100 rounded-xl" />
          </div>
          <div className="h-12 bg-slate-100 rounded-2xl w-full" />
        </div>

        {/* Campaign Cards Skeleton */}
        <div className="space-y-4">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="p-6 rounded-2xl bg-white border border-slate-200/80 shadow-sm space-y-3"
            >
              <div className="flex justify-between items-center">
                <div className="h-5 bg-slate-200 rounded w-48" />
                <div className="h-6 w-20 bg-rose-100 rounded-full" />
              </div>
              <div className="space-y-2">
                <div className="h-4 bg-slate-100 rounded w-full" />
                <div className="h-4 bg-slate-100/70 rounded w-3/4" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
