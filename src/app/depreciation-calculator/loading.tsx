export default function DepreciationCalculatorLoading() {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="감가 및 배터리 수명 계산기 로딩 중"
      className="space-y-8 py-6 animate-pulse motion-reduce:animate-none"
    >
      <span className="sr-only">감가율 및 배터리 수명 계산기를 불러오는 중입니다...</span>

      {/* Header Skeleton */}
      <div className="space-y-3">
        <div className="h-8 sm:h-10 bg-slate-200 rounded-2xl w-3/4 max-w-xl" />
        <div className="h-4 sm:h-5 bg-slate-100 rounded-xl w-5/6 max-w-2xl" />
      </div>

      {/* Vehicle Selection Bar Skeleton */}
      <div className="p-6 rounded-3xl bg-white border border-slate-200/80 shadow-sm space-y-4">
        <div className="h-6 bg-slate-200 rounded w-44" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-12 bg-slate-100 rounded-xl" />
          ))}
        </div>
      </div>

      {/* Simulation Controls & Preview Skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1 p-6 rounded-3xl bg-white border border-slate-200/80 shadow-sm space-y-5">
          <div className="h-5 bg-slate-200 rounded w-36" />
          <div className="space-y-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="space-y-2">
                <div className="h-4 bg-slate-100 rounded w-1/2" />
                <div className="h-3 bg-slate-200 rounded-full w-full" />
              </div>
            ))}
          </div>
        </div>

        <div className="lg:col-span-2 p-6 rounded-3xl bg-white border border-slate-200/80 shadow-sm space-y-5">
          <div className="h-5 bg-slate-200 rounded w-48" />
          <div className="h-64 bg-slate-100 rounded-2xl flex items-center justify-center">
            <div className="w-12 h-12 rounded-full border-4 border-slate-200 border-t-emerald-500 animate-spin" />
          </div>
        </div>
      </div>
    </div>
  );
}
