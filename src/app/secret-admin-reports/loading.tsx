export default function SecretAdminReportsLoading() {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="관리자 데일리 결함 모니터링 리포트 로딩 중"
      className="space-y-8 py-6 animate-pulse motion-reduce:animate-none"
    >
      <span className="sr-only">관리자 결함 모니터링 리포트를 불러오는 중입니다...</span>

      {/* Header Skeleton */}
      <div className="space-y-3">
        <div className="h-8 sm:h-10 bg-slate-800 rounded-2xl w-3/4 max-w-xl" />
        <div className="h-4 sm:h-5 bg-slate-800/60 rounded-xl w-5/6 max-w-2xl" />
      </div>

      {/* KPI Stats Bar Skeleton */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-2">
            <div className="h-3 bg-slate-800 rounded w-1/2" />
            <div className="h-7 bg-slate-700 rounded w-3/4" />
          </div>
        ))}
      </div>

      {/* Filter Tabs Skeleton */}
      <div className="flex gap-2 overflow-x-auto pb-1">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="h-9 w-24 bg-slate-800 rounded-xl shrink-0" />
        ))}
      </div>

      {/* Report Cards Skeletons */}
      <div className="space-y-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-3"
          >
            <div className="flex justify-between items-center">
              <div className="h-5 bg-slate-800 rounded w-1/3" />
              <div className="h-6 w-16 bg-slate-800 rounded-full" />
            </div>
            <div className="space-y-2">
              <div className="h-4 bg-slate-800/80 rounded w-full" />
              <div className="h-4 bg-slate-800/50 rounded w-4/5" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
