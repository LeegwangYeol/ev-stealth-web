'use client';

import React, { useState, memo, useCallback } from 'react';

interface FaqItem {
  id: string;
  question: string;
  answer: React.ReactNode;
}

const FAQ_ITEMS: FaqItem[] = [
  {
    id: 'price-cap',
    question: '2026년 전기차 보조금 5,500만 / 8,500만 원 슬라이딩 가격 상한제 기준은 어떻게 적용되나요?',
    answer: (
      <div className="space-y-2 text-slate-300 leading-relaxed text-xs sm:text-sm">
        <p>
          환경부 무공해차 보조금 업무처리지침에 따라 전기승용차의 기본 출고가(MSRP, 트림별 기본 가격 기준, 옵션 제외)에 따라 3단계 차등 지원율이 적용됩니다:
        </p>
        <ul className="list-disc pl-5 space-y-1 text-slate-300">
          <li><strong className="text-emerald-400">5,500만 원 미만:</strong> 국비 및 지방비 보조금 <strong>100% 전액 지원</strong></li>
          <li><strong className="text-amber-400">5,500만 원 이상 ~ 8,500만 원 미만:</strong> 산출 보조금의 <strong>50% 감액 지원</strong></li>
          <li><strong className="text-rose-400">8,500만 원 이상:</strong> 고가 프리미엄 차량으로 분류되어 보조금 <strong>지급 대상에서 전액 제외 (0원)</strong></li>
        </ul>
      </div>
    ),
  },
  {
    id: 'local-subsidy-matching',
    question: '지자체별 지방비 보조금은 어떻게 산출되며 왜 지역마다 차이가 나나요?',
    answer: (
      <div className="space-y-2 text-slate-300 leading-relaxed text-xs sm:text-sm">
        <p>
          지자체 보조금은 <strong>국비 보조금 비율(해당 모델 국비 지원액 / 국비 최대 지원 상한액 650만 원)</strong>에 비례하여 각 지자체의 공고 조례 지원액이 매칭됩니다.
        </p>
        <p className="text-slate-300">
          서울(150만 원), 대구(250만 원), 제주(400만 원) 등 지자체 재정 자립도 및 보급 목표 대수에 따라 지방비 책정 금액이 상이하며, 특히 경북 울릉군의 경우 도서 지역 특수 지원으로 최대 1,100만 원까지 지원되어 서울 대비 최대 950만 원의 실구매가 격차가 발생할 수 있습니다.
        </p>
      </div>
    ),
  },
  {
    id: 'mandatory-operation',
    question: '보조금을 받은 전기차를 2년 이내에 매각하거나 타 시·도로 이전하면 어떻게 되나요?',
    answer: (
      <div className="space-y-2 text-slate-300 leading-relaxed text-xs sm:text-sm">
        <p>
          대기환경보전법 제58조 및 동법 시행규칙에 따라 보조금을 지급받은 전기차 구매자는 최초 등록일로부터 <strong>2년간 의무 운행 기간</strong>을 준수해야 합니다:
        </p>
        <ul className="list-disc pl-5 space-y-1 text-slate-300">
          <li><strong>관내(동일 시·도 내) 매매:</strong> 구매자에게 의무 운행 잔여 기간이 자동 승계되어 보조금 환수가 발생하지 않습니다.</li>
          <li><strong className="text-rose-400">관외(타 시·도) 매매 또는 수출·폐차:</strong> 운행 기간별 환수율 기준(3개월 미만 70%, 6개월 미만 60%, 12개월 미만 50%, 18개월 미만 30%, 24개월 미만 20%)에 따라 관할 지자체가 지방비를 강제 환수합니다.</li>
        </ul>
      </div>
    ),
  },
  {
    id: 'supplementary-budget',
    question: '원하는 지자체의 보조금이 마감(소진율 100%)된 경우 어떻게 대처해야 하나요?',
    answer: (
      <div className="space-y-2 text-slate-300 leading-relaxed text-xs sm:text-sm">
        <p>
          공고 물량이 전액 소진되었더라도 다음 3가지 경로를 통해 보조금을 확보할 수 있습니다:
        </p>
        <ol className="list-decimal pl-5 space-y-1 text-slate-300">
          <li><strong>취소분 대기 접수:</strong> 출고 지연 또는 단순 변심으로 신청 취소분이 발생하면 선착순 접수 순서대로 순차 배정됩니다.</li>
          <li><strong>지자체 추가경정예산(추경):</strong> 6~8월 상반기 결산 후 각 지자체 의회에서 전기차 보급 활성화를 위한 추경 편성이 진행됩니다. (본 시스템에서 추경 편성 여부 실시간 표시)</li>
          <li><strong>법인/리스 명의 활용:</strong> 타 지역 지사를 보유한 법인이나 렌터카/리스사의 경우 잔여 쿼터가 있는 지자체로 분산 등록이 가능할 수 있습니다.</li>
        </ol>
      </div>
    ),
  },
  {
    id: 'additional-grants',
    question: '청년, 소상공인, 다자녀 가구 및 노후 경유차 특별 가산금 조건은 무엇인가요?',
    answer: (
      <div className="space-y-2 text-slate-300 leading-relaxed text-xs sm:text-sm">
        <p>
          2026년 환경부 정책에 따라 취약 계층 및 친환경 전환 촉진을 위한 중복 지원 혜택이 강화되었습니다:
        </p>
        <ul className="list-disc pl-5 space-y-1 text-slate-300">
          <li><strong>청년 생애 최초 구매자 (만 19~34세):</strong> 국비 보조금의 <strong>+20% 추가 지원</strong></li>
          <li><strong>소상공인 및 개인택시 운송사업자:</strong> 국비 보조금의 <strong>+30% 추가 지원</strong></li>
          <li><strong>다자녀 가구 (18세 미만 자녀 2인 이상):</strong> 국비 보조금의 <strong>+10% 추가 지원</strong></li>
          <li><strong>노후 경유차 (4·5등급) 조기폐차 후 구매:</strong> 기본 조기폐차 지원금 외 <strong>정액 100만 원 추가 지원</strong></li>
        </ul>
      </div>
    ),
  },
];

interface FaqItemRowProps {
  item: FaqItem;
  idx: number;
  isOpen: boolean;
  onToggle: (id: string) => void;
  onKeyDown: (e: React.KeyboardEvent, index: number) => void;
}

const FaqItemRow = memo(function FaqItemRow({
  item,
  idx,
  isOpen,
  onToggle,
  onKeyDown,
}: FaqItemRowProps) {
  return (
    <div className="rounded-2xl border border-slate-800/80 bg-slate-900/60 overflow-hidden transition">
      <h3>
        <button
          id={`faq-btn-${item.id}`}
          type="button"
          aria-expanded={isOpen}
          aria-controls={`faq-panel-${item.id}`}
          onClick={() => onToggle(item.id)}
          onKeyDown={(e) => onKeyDown(e, idx)}
          className="w-full py-3.5 px-4 sm:px-5 min-h-[44px] text-left text-xs sm:text-sm font-semibold text-slate-200 hover:text-white flex items-center justify-between gap-3 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-900"
        >
          <span className="flex items-center gap-2">
            <span className="text-amber-400 font-bold" aria-hidden="true">Q.</span>
            <span>{item.question}</span>
          </span>
          <span
            aria-hidden="true"
            className={`text-slate-300 text-xs shrink-0 transition-transform duration-200 ${isOpen ? 'rotate-180 text-amber-400' : ''}`}
          >
            ▼
          </span>
        </button>
      </h3>

      <div
        id={`faq-panel-${item.id}`}
        role="region"
        aria-labelledby={`faq-btn-${item.id}`}
        hidden={!isOpen}
        className={`${!isOpen ? 'hidden' : ''} px-4 sm:px-5 pb-4 pt-1 border-t border-slate-800/60 bg-slate-950/40`}
      >
        {item.answer}
      </div>
    </div>
  );
});

export const SubsidyFaqAccordion = memo(function SubsidyFaqAccordion() {
  const [openIds, setOpenIds] = useState<Record<string, boolean>>({ 'price-cap': true });

  const toggleItem = useCallback((id: string) => {
    setOpenIds((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent, index: number) => {
    const total = FAQ_ITEMS.length;
    let nextIndex = -1;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      nextIndex = (index + 1) % total;
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      nextIndex = (index - 1 + total) % total;
    } else if (e.key === 'Home') {
      e.preventDefault();
      nextIndex = 0;
    } else if (e.key === 'End') {
      e.preventDefault();
      nextIndex = total - 1;
    }

    if (nextIndex >= 0) {
      const targetBtn = document.getElementById(`faq-btn-${FAQ_ITEMS[nextIndex].id}`);
      if (targetBtn) {
        targetBtn.focus();
      }
    }
  }, []);

  return (
    <section
      aria-labelledby="subsidy-guidelines-heading"
      className="bg-slate-950 p-6 sm:p-7 rounded-3xl border border-slate-900 space-y-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-900 pb-3">
        <h2 id="subsidy-guidelines-heading" className="text-base sm:text-lg font-bold text-white flex items-center gap-2">
          <span>📌</span> 2026년 환경부 및 지자체 전기차 보조금 제도 가이드 &amp; 자주 묻는 질문
        </h2>
        <span className="text-xs text-slate-300">클릭하여 세부 기준 확인</span>
      </div>

      <div className="space-y-2">
        {FAQ_ITEMS.map((item, idx) => (
          <FaqItemRow
            key={item.id}
            item={item}
            idx={idx}
            isOpen={!!openIds[item.id]}
            onToggle={toggleItem}
            onKeyDown={handleKeyDown}
          />
        ))}
      </div>
    </section>
  );
});

export default SubsidyFaqAccordion;
