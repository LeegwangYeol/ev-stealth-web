export default function TeslaLoading() {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="테슬라 연식별 구매 가이드 로딩 중"
      className="space-y-8 py-6 max-w-4xl mx-auto animate-pulse motion-reduce:animate-none"
    >
      <span className="sr-only">테슬라 연식별 구매 가이드를 불러오는 중입니다...</span>

      {/* Header Skeleton */}
      <div className="space-y-3">
        <div className="h-8 sm:h-10 bg-slate-200 rounded-2xl w-3/4 max-w-xl" />
        <div className="h-4 sm:h-5 bg-slate-100 rounded-xl w-5/6" />
      </div>

      {/* Content Section Skeletons */}
      <div className="space-y-6">
        {[1, 2, 3].map((i) => (
          <div key={i} className="p-6 rounded-3xl bg-white border border-slate-200/80 shadow-sm space-y-4">
            <div className="h-6 bg-slate-200 rounded-xl w-56" />
            <div className="space-y-2">
              <div className="h-4 bg-slate-100 rounded w-full" />
              <div className="h-4 bg-slate-100 rounded w-4/5" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
