export default function ReliabilityAnalyticsLoading() {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="전기차 결함 통계 및 DSI 내구성 데이터 로딩 중"
      className="space-y-8 py-6 animate-pulse motion-reduce:animate-none"
    >
      <span className="sr-only">전기차 결함 통계 및 DSI 내구성 데이터를 불러오는 중입니다...</span>

      {/* Header Skeleton */}
      <div className="space-y-3">
        <div className="h-8 sm:h-10 bg-slate-200 rounded-2xl w-3/4 max-w-xl" />
        <div className="h-4 sm:h-5 bg-slate-100 rounded-xl w-5/6 max-w-2xl" />
      </div>

      {/* Overview Stat Badges */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="p-4 rounded-2xl bg-white border border-slate-200/80 shadow-sm space-y-2">
            <div className="h-3 bg-slate-200 rounded w-1/2" />
            <div className="h-7 bg-slate-300 rounded w-3/4" />
          </div>
        ))}
      </div>

      {/* Heatmap & Chart Container Skeleton */}
      <div className="p-6 rounded-3xl bg-white border border-slate-200/80 shadow-sm space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="h-6 bg-slate-200 rounded w-56" />
          <div className="flex gap-2">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-8 w-24 bg-slate-100 rounded-lg" />
            ))}
          </div>
        </div>

        {/* Heatmap Grid Rows Skeleton */}
        <div className="space-y-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-12 bg-slate-100 rounded-xl flex items-center px-4 justify-between">
              <div className="h-4 bg-slate-200 rounded w-32" />
              <div className="flex gap-2">
                {[1, 2, 3, 4, 5].map((j) => (
                  <div key={j} className="h-7 w-7 bg-slate-200 rounded-lg" />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
