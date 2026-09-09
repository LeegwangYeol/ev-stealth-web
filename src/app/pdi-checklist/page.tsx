'use client';

import { useState } from 'react';

type ChecklistItem = {
  id: string;
  category: string;
  task: string;
  warning?: string;
  checked: boolean;
};

const initialItems: ChecklistItem[] = [
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

export default function PdiChecklistPage() {
  const [items, setItems] = useState<ChecklistItem[]>(initialItems);

  const toggleCheck = (id: string) => {
    setItems((prev) =>
      prev.map((item) =>
        item.id === id ? { ...item, checked: !item.checked } : item
      )
    );
  };

  const progress = Math.round((items.filter((i) => i.checked).length / items.length) * 100);

  return (
    <div className="max-w-4xl mx-auto py-10 space-y-8">
      <header className="border-b pb-6">
        <h1 className="text-4xl font-extrabold text-slate-900 mb-4">전기차 신차 인수(PDI) 체크리스트 ✅</h1>
        <p className="text-lg text-gray-600">
          호갱 당하지 않는 방법! 탁송 차량을 인수증에 서명하기 전에 반드시 아래 결함 항목들을 체크하세요. 한번 서명하면 치명적 결함도 차주 과실로 떠넘겨질 수 있습니다.
        </p>
      </header>

      <div className="sticky top-0 bg-white/90 backdrop-blur-md p-4 rounded-xl border border-gray-200 shadow-sm z-10">
        <div className="flex justify-between items-center mb-2">
          <span className="font-semibold text-gray-700">검수 진행률</span>
          <span className="font-bold text-blue-600">{progress}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-3">
          <div
            className="bg-blue-600 h-3 rounded-full transition-all duration-500 ease-out"
            style={{ width: `${progress}%` }}
          ></div>
        </div>
      </div>

      <div className="space-y-6">
        {Array.from(new Set(items.map((i) => i.category))).map((category) => (
          <div key={category} className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">
            <h2 className="bg-slate-50 border-b border-gray-200 p-4 text-xl font-bold text-slate-800">
              {category}
            </h2>
            <div className="divide-y divide-gray-100">
              {items
                .filter((item) => item.category === category)
                .map((item) => (
                  <label
                    key={item.id}
                    className="flex items-start p-4 hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={item.checked}
                      onChange={() => toggleCheck(item.id)}
                      className="mt-1 w-6 h-6 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500"
                    />
                    <div className="ml-4 flex-1">
                      <p className={`text-lg ${item.checked ? 'text-gray-400 line-through' : 'text-gray-800'}`}>
                        {item.task}
                      </p>
                      {item.warning && (
                        <p className={`mt-1 text-sm font-medium ${item.checked ? 'text-gray-300' : 'text-red-500'}`}>
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
        <div className="bg-green-50 border border-green-200 text-green-800 p-6 rounded-2xl text-center shadow-sm animate-pulse">
          <h3 className="text-2xl font-bold mb-2">🎉 검수 완료!</h3>
          <p>모든 항목을 확인하셨습니다. 이상이 없다면 안심하고 인수증에 서명하세요.</p>
        </div>
      )}
    </div>
  );
}
