'use client';

import React, { useState, useEffect, useMemo } from 'react';

export type ChecklistItem = {
  id: string;
  category: string;
  task: string;
  warning?: string;
  checked: boolean;
};

export const INITIAL_PDI_ITEMS: ChecklistItem[] = [
  { id: '1', category: '외관 (도장 및 단차)', task: '앞/뒤 범퍼와 펜더 사이의 단차(벌어짐) 확인', warning: '테슬라와 초기형 현기차에서 빈번함', checked: false },
  { id: '2', category: '외관 (도장 및 단차)', task: '충전구 덮개가 꽉 닫히는지, 유격은 없는지 확인', checked: false },
  { id: '3', category: '외관 (도장 및 단차)', task: '하부 배터리팩 케이스 긁힘 및 찍힘 흔적 확인', warning: '인수 후 발견 시 차주 과실로 배터리 교환 불가(전손 위험)', checked: false },
  { id: '4', category: '실내 (시트 및 마감)', task: '시트 가죽 울음, 찢김, 박음질 불량 확인', checked: false },
  { id: '5', category: '실내 (시트 및 마감)', task: '전 좌석 안전벨트 체결 및 버튼 동작 정상 여부', checked: false },
  { id: '6', category: '시스템 (소프트웨어)', task: '메인 디스플레이 터치 먹통 및 재부팅 여부 확인', checked: false },
  { id: '7', category: '시스템 (소프트웨어)', task: '스마트폰 무선 충전 패드 작동 및 발열 체크', checked: false },
  { id: '8', category: '주행 및 하체', task: '핸들(스티어링 휠) 좌우 끝까지 돌릴 때 찌그덕/뚝 소음 확인', warning: '모델Y 컨트롤 암 부싱, 현기 전기차 등 고질병', checked: false },
  { id: '9', category: '주행 및 하체', task: '에어컨 및 히터 최대 가동 시 이음(백색가루/소음) 확인', warning: 'BYD 돌핀 백색가루, 테슬라 히트펌프 불량', checked: false },
];

const STORAGE_KEY = 'ev_pdi_checklist_state_v1';

export default function PdiChecklistClient() {
  const [items, setItems] = useState<ChecklistItem[]>(INITIAL_PDI_ITEMS);
  const [mounted, setMounted] = useState(false);

  // Safe client mounting check: hydrate from localStorage after mount
  useEffect(() => {
    setMounted(true);
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed)) {
            setItems((current) =>
              current.map((item) => {
                const match = parsed.find((p: ChecklistItem) => p.id === item.id);
                return match ? { ...item, checked: Boolean(match.checked) } : item;
              })
            );
          }
        }
      }
    } catch (e) {
      console.warn('Failed to load PDI checklist from localStorage:', e);
    }
  }, []);

  // Save changes to localStorage after mounted
  useEffect(() => {
    if (!mounted) return;
    try {
      if (typeof window !== 'undefined' && window.localStorage) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
      }
    } catch (e) {
      console.warn('Failed to save PDI checklist to localStorage:', e);
    }
  }, [items, mounted]);

  const toggleCheck = (id: string) => {
    setItems((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, checked: !item.checked } : item
      )
    );
  };

  const resetChecklist = () => {
    if (typeof window !== 'undefined' && window.confirm('체크리스트 상태를 초기화하시겠습니까?')) {
      setItems(INITIAL_PDI_ITEMS);
      try {
        if (window.localStorage) {
          localStorage.removeItem(STORAGE_KEY);
        }
      } catch (e) {
        console.warn('Failed to clear PDI checklist localStorage:', e);
      }
    }
  };

  const [selectedCategory, setSelectedCategory] = useState<string>('ALL');

  // Memoized category sets and filtered count calculations
  const categories = useMemo(() => Array.from(new Set(items.map((i) => i.category))), [items]);
  const checkedCount = useMemo(() => items.filter((i) => i.checked).length, [items]);
  const totalItems = items.length;
  // Guard against division by zero (items.length === 0 ? 0 : Math.round((checkedCount / items.length) * 100))
  const progress = useMemo(() => {
    return totalItems > 0 ? Math.round((checkedCount / totalItems) * 100) : 0;
  }, [checkedCount, totalItems]);
  const progressPercentage = progress;

  const allCategories = useMemo(() => ['ALL', ...categories], [categories]);

  const handleTabKeyDown = (e: React.KeyboardEvent, currentIndex: number) => {
    const count = allCategories.length;
    let nextIndex = -1;
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      nextIndex = (currentIndex + 1) % count;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      nextIndex = (currentIndex - 1 + count) % count;
    } else if (e.key === 'Home') {
      e.preventDefault();
      nextIndex = 0;
    } else if (e.key === 'End') {
      e.preventDefault();
      nextIndex = count - 1;
    }
    if (nextIndex !== -1) {
      const nextCat = allCategories[nextIndex];
      setSelectedCategory(nextCat);
      document.getElementById(`pdi-tab-${nextIndex}`)?.focus();
    }
  };

  // Memoized category statistics
  const categoryStats = useMemo(() => {
    const stats: Record<string, { total: number; checked: number }> = {};
    for (const cat of categories) {
      stats[cat] = { total: 0, checked: 0 };
    }
    for (const item of items) {
      if (stats[item.category]) {
        stats[item.category].total += 1;
        if (item.checked) stats[item.category].checked += 1;
      }
    }
    return stats;
  }, [items, categories]);

  // Memoized items grouped by category to eliminate redundant array filters during rendering
  const itemsByCategory = useMemo(() => {
    const map = new Map<string, ChecklistItem[]>();
    for (const cat of categories) {
      map.set(cat, []);
    }
    for (const item of items) {
      const list = map.get(item.category);
      if (list) list.push(item);
    }
    return map;
  }, [items, categories]);

  // Displayed categories based on selected category filter
  const displayedCategories = useMemo(() => {
    return selectedCategory === 'ALL'
      ? categories
      : categories.filter((c) => c === selectedCategory);
  }, [categories, selectedCategory]);

  return (
    <div className="max-w-4xl mx-auto py-10 space-y-8">
      <header className="border-b pb-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 mb-2">
              전기차 신차 인수(PDI) 체크리스트 ✅
            </h1>
            <p className="text-base sm:text-lg text-gray-600">
              호갱 당하지 않는 방법! 탁송 차량을 인수증에 서명하기 전에 반드시 아래 결함 항목들을 체크하세요.
            </p>
          </div>
          {mounted && (
            <button
              onClick={resetChecklist}
              type="button"
              className="self-start sm:self-auto px-3.5 py-2 text-xs font-semibold text-slate-600 hover:text-red-700 bg-white hover:bg-red-50 border border-slate-300 rounded-lg shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
            >
              체크리스트 초기화
            </button>
          )}
        </div>
        <div className="mt-3 flex items-center gap-2 text-xs text-slate-600">
          <span aria-hidden="true" className={`w-2 h-2 rounded-full ${mounted ? 'bg-emerald-500' : 'bg-slate-300'}`} />
          <span>{mounted ? '로컬 저장소 동기화 활성화됨 (새로고침 시 체크 상태 유지)' : '초기화 중...'}</span>
        </div>
      </header>

      <div className="sticky top-0 bg-white/90 backdrop-blur-md p-4 rounded-xl border border-gray-200 shadow-sm z-10 space-y-3">
        <div className="flex justify-between items-center">
          <span className="font-semibold text-gray-700">검수 진행률 ({checkedCount}/{items.length})</span>
          <span className="font-bold text-blue-600">{progress}%</span>
        </div>
        <div
          role="progressbar"
          aria-valuenow={progressPercentage}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="PDI 점검 진행률"
          aria-valuetext={`${progressPercentage}% 검수 완료`}
          className="w-full bg-gray-200 rounded-full h-3"
        >
          <div
            className="bg-blue-600 h-3 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${progressPercentage}%` }}
          />
        </div>

        {/* Category Filter Chips with visible focus rings */}
        <div
          role="tablist"
          aria-label="체크리스트 카테고리 필터"
          className="flex flex-wrap items-center gap-2 pt-2 border-t border-gray-100"
        >
          {(() => {
            const isSelected = selectedCategory === 'ALL';
            return (
              <button
                id="pdi-tab-0"
                type="button"
                role="tab"
                aria-selected={isSelected}
                aria-controls="pdi-checklist-tabpanel"
                tabIndex={isSelected ? 0 : -1}
                onKeyDown={(e) => handleTabKeyDown(e, 0)}
                onClick={() => setSelectedCategory('ALL')}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  isSelected
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                }`}
              >
                전체 ({items.length})
              </button>
            );
          })()}
          {categories.map((cat, idx) => {
            const count = categoryStats[cat]?.total || 0;
            const checked = categoryStats[cat]?.checked || 0;
            const isSelected = selectedCategory === cat;
            const tabIndex = idx + 1;
            return (
              <button
                key={cat}
                id={`pdi-tab-${tabIndex}`}
                type="button"
                role="tab"
                aria-selected={isSelected}
                aria-controls="pdi-checklist-tabpanel"
                tabIndex={isSelected ? 0 : -1}
                onKeyDown={(e) => handleTabKeyDown(e, tabIndex)}
                onClick={() => setSelectedCategory(cat)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 ${
                  isSelected
                    ? 'bg-blue-600 text-white border-blue-600'
                    : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'
                }`}
              >
                {cat} ({checked}/{count})
              </button>
            );
          })}
        </div>
      </div>

      <div
        id="pdi-checklist-tabpanel"
        role="tabpanel"
        aria-labelledby={`pdi-tab-${Math.max(0, allCategories.indexOf(selectedCategory))}`}
        tabIndex={0}
        className="space-y-6 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-2xl"
      >
        {displayedCategories.map((category) => (
          <div key={category} className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
            <h2 className="bg-slate-50 border-b border-gray-200 p-4 text-xl font-bold text-slate-800">
              {category}
            </h2>
            <div className="divide-y divide-gray-100">
              {(itemsByCategory.get(category) || []).map((item) => (
                <label
                  key={item.id}
                  className="flex items-start p-4 hover:bg-slate-50 cursor-pointer transition-colors rounded-xl focus-within:ring-2 focus-within:ring-blue-500"
                >
                  <input
                    type="checkbox"
                    checked={item.checked}
                    onChange={() => toggleCheck(item.id)}
                    className="mt-1 w-6 h-6 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 focus-visible:ring-2 focus-visible:ring-blue-500"
                  />
                  <div className="ml-4 flex-1">
                    <p className={`text-lg ${item.checked ? 'text-slate-600 line-through' : 'text-gray-800'}`}>
                      {item.task}
                    </p>
                    {item.warning && (
                      <p className={`mt-1 text-sm font-medium ${item.checked ? 'text-slate-600 line-through' : 'text-red-700'}`}>
                        ⚠️ 주의: {item.warning}
                      </p>
                    )}
                  </div>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>

      {progress === 100 && (
        <div
          role="status"
          aria-live="polite"
          className="bg-green-50 border border-green-200 text-green-800 p-6 rounded-2xl text-center shadow-sm animate-pulse motion-reduce:animate-none"
        >
          <h3 className="text-2xl font-bold mb-2">🎉 검수 완료!</h3>
          <p>모든 항목을 확인하셨습니다. 이상이 없다면 안심하고 인수증에 서명하세요.</p>
        </div>
      )}
    </div>
  );
}
