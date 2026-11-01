export default function RootLoading() {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="페이지 로딩 중"
      className="w-full max-w-6xl mx-auto py-12 px-4 space-y-8 animate-pulse motion-reduce:animate-none"
    >
      <span className="sr-only">페이지 내용을 불러오는 중입니다...</span>

      {/* Header Skeleton */}
      <div className="space-y-4 text-center max-w-2xl mx-auto">
        <div className="h-10 bg-slate-200 rounded-2xl w-3/4 mx-auto" />
        <div className="h-5 bg-slate-100 rounded-xl w-5/6 mx-auto" />
        <div className="h-4 bg-slate-100 rounded-lg w-2/3 mx-auto" />
      </div>

      {/* KPI Stats Bar Skeleton */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="p-5 rounded-2xl bg-white border border-slate-200/80 shadow-sm space-y-3"
          >
            <div className="h-4 bg-slate-200 rounded w-1/2" />
            <div className="h-7 bg-slate-300 rounded-lg w-3/4" />
            <div className="h-3 bg-slate-100 rounded w-2/3" />
          </div>
        ))}
      </div>

      {/* Main Content Skeleton Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {[1, 2, 3, 4, 5, 6].map((i) => (
          <div
            key={i}
            className="p-6 rounded-3xl bg-white border border-slate-200/80 shadow-sm space-y-4"
          >
            <div className="flex items-center justify-between">
              <div className="h-6 bg-slate-200 rounded-xl w-2/5" />
              <div className="h-6 w-16 bg-slate-100 rounded-full" />
            </div>
            <div className="space-y-2">
              <div className="h-4 bg-slate-100 rounded w-full" />
              <div className="h-4 bg-slate-100 rounded w-4/5" />
            </div>
            <div className="pt-2 border-t border-slate-100 flex justify-between items-center">
              <div className="h-4 bg-slate-200 rounded w-1/3" />
              <div className="h-4 bg-slate-200 rounded w-1/4" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
