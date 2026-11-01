export default function SubsidyTrackerLoading() {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="전국 보조금 소진율 데이터 로딩 중"
      className="space-y-8 py-6 animate-pulse motion-reduce:animate-none"
    >
      <span className="sr-only">전국 보조금 소진율 데이터를 불러오는 중입니다...</span>

      {/* Header Skeleton */}
      <div className="space-y-3">
        <div className="h-8 sm:h-10 bg-slate-800 rounded-2xl w-3/4 max-w-xl" />
        <div className="h-4 sm:h-5 bg-slate-800/60 rounded-xl w-5/6 max-w-2xl" />
      </div>

      {/* Category Tabs Skeleton */}
      <div className="flex gap-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-10 w-32 bg-slate-800 rounded-xl" />
        ))}
      </div>

      {/* Nationwide Summary Card Skeleton */}
      <div className="p-6 rounded-3xl bg-slate-900 border border-slate-800 space-y-6">
        <div className="flex justify-between items-center">
          <div className="h-6 bg-slate-800 rounded w-48" />
          <div className="h-6 bg-slate-800 rounded w-24" />
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800 space-y-2">
              <div className="h-3 bg-slate-800 rounded w-1/2" />
              <div className="h-7 bg-slate-700 rounded w-3/4" />
              <div className="h-2 bg-slate-800 rounded w-full" />
            </div>
          ))}
        </div>
      </div>

      {/* Search & Filter Controls Skeleton */}
      <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 flex flex-col sm:flex-row gap-3">
        <div className="h-10 bg-slate-950 rounded-xl flex-1 border border-slate-800" />
        <div className="h-10 w-36 bg-slate-950 rounded-xl border border-slate-800" />
      </div>

      {/* Regional Grid Skeleton */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div
            key={i}
            className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4"
          >
            <div className="flex justify-between items-center">
              <div className="h-5 bg-slate-800 rounded w-28" />
              <div className="h-6 w-16 bg-slate-800 rounded-full" />
            </div>
            <div className="space-y-2">
              <div className="h-3 bg-slate-800 rounded w-full" />
              <div className="h-3 bg-slate-800/60 rounded w-4/5" />
            </div>
            <div className="h-2 bg-slate-800 rounded-full w-full" />
          </div>
        ))}
      </div>
    </div>
  );
}
