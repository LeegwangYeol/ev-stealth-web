import Link from 'next/link';

export type BrandPageKey = 'hyundai-kia' | 'tesla' | 'byd' | 'global-brands' | '2026-latest';

interface BrandItem {
  key: BrandPageKey;
  label: string;
  shortLabel: string;
  href: string;
  icon: string;
  badge?: string;
}

export const BRAND_PAGES: BrandItem[] = [
  { key: 'hyundai-kia', label: '현대/기아', shortLabel: '현대·기아', href: '/hyundai-kia', icon: '🚘' },
  { key: 'tesla', label: '테슬라', shortLabel: '테슬라', href: '/tesla', icon: '🚗' },
  { key: 'byd', label: 'BYD', shortLabel: 'BYD', href: '/byd', icon: '⚡' },
  { key: 'global-brands', label: '기타 글로벌', shortLabel: '글로벌', href: '/global-brands', icon: '🌍' },
  { key: '2026-latest', label: '2026 최신 결함', shortLabel: '2026 최신', href: '/2026-latest', icon: '🔥', badge: '신차' },
];

interface BrandComparisonNavProps {
  currentBrand: BrandPageKey;
  pageTitle: string;
}

export default function BrandComparisonNav({ currentBrand, pageTitle }: BrandComparisonNavProps) {
  return (
    <div className="space-y-4 mb-6">
      {/* Top Breadcrumb & Back Nav */}
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs sm:text-sm">
        <nav aria-label="브레드크럼 위치 경로" className="flex items-center gap-1.5 text-slate-600">
          <Link
            href="/"
            prefetch={false}
            className="hover:text-blue-600 transition flex items-center gap-1 font-medium text-slate-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded py-1 px-1.5 min-h-[36px]"
          >
            <span aria-hidden="true">🏠</span> 홈
          </Link>
          <span aria-hidden="true" className="text-slate-600">/</span>
          <span className="text-slate-600 hidden sm:inline">브랜드별 가이드</span>
          <span aria-hidden="true" className="text-slate-300 hidden sm:inline">/</span>
          <span className="text-slate-900 font-semibold truncate max-w-[200px] sm:max-w-none" aria-current="page">
            {pageTitle}
          </span>
        </nav>

        <Link
          href="/"
          prefetch={false}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 hover:text-slate-900 text-xs font-semibold transition border border-slate-200/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 min-h-[36px]"
          aria-label="메인 홈 전체 서비스 목록으로 돌아가기"
        >
          <span aria-hidden="true">&larr;</span> 전체 가이드 홈
        </Link>
      </div>

      {/* Brand Switcher Nav Tabs */}
      <nav
        aria-label="제조사별 결함 가이드 빠른 전환 탭"
        className="p-1.5 bg-slate-100/90 rounded-2xl border border-slate-200 shadow-inner flex overflow-x-auto gap-1.5 scrollbar-thin"
      >
        {BRAND_PAGES.map((brand) => {
          const isActive = brand.key === currentBrand;
          return (
            <Link
              key={brand.key}
              href={brand.href}
              prefetch={false}
              aria-current={isActive ? 'page' : undefined}
              className={`flex-1 min-w-[96px] sm:min-w-0 min-h-[44px] px-3 py-2 rounded-xl text-xs sm:text-sm font-semibold transition flex items-center justify-center gap-1.5 text-center focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 ${
                isActive
                  ? 'bg-blue-600 text-white shadow-sm ring-1 ring-blue-700/20'
                  : 'bg-white text-slate-700 hover:bg-slate-50 hover:text-blue-700 border border-slate-200/80'
              }`}
            >
              <span aria-hidden="true" className="text-base">{brand.icon}</span>
              <span className="whitespace-nowrap">{brand.shortLabel}</span>
              {brand.badge && (
                <span
                  className={`text-[10px] font-extrabold px-1.5 py-0.2 rounded-full ${
                    isActive ? 'bg-white/20 text-white' : 'bg-rose-100 text-rose-700'
                  }`}
                >
                  {brand.badge}
                </span>
              )}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

export function OtherBrandsCrossNav({ currentBrand }: { currentBrand: BrandPageKey }) {
  const otherBrands = BRAND_PAGES.filter((b) => b.key !== currentBrand);

  return (
    <div className="pt-8 border-t border-slate-200 space-y-4">
      <div className="space-y-1">
        <h3 className="text-xl font-bold text-slate-900">
          다른 제조사 연식별 가이드 비교하기
        </h3>
        <p className="text-xs sm:text-sm text-slate-600">
          관심 있는 다른 제조사의 연식별 고질병과 감가·리콜 정보를 즉시 비교하세요.
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {otherBrands.map((brand) => (
          <Link
            key={brand.key}
            href={brand.href}
            prefetch={false}
            className="group p-4 rounded-xl border border-slate-200 bg-white hover:border-blue-400 hover:shadow-md transition flex flex-col justify-between gap-2 min-h-[72px] focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
          >
            <div className="flex items-center gap-2">
              <span className="text-2xl" aria-hidden="true">{brand.icon}</span>
              <span className="font-bold text-sm text-slate-900 group-hover:text-blue-600 transition">
                {brand.label}
              </span>
            </div>
            <span className="text-xs text-blue-600 font-semibold group-hover:underline inline-flex items-center gap-1">
              가이드 보기 <span aria-hidden="true">&rarr;</span>
            </span>
          </Link>
        ))}
      </div>
    </div>
  );
}
