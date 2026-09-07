export default function BydPage() {
  return (
    <div className="space-y-8 py-10 max-w-4xl mx-auto">
      <h1 className="text-4xl font-bold border-b pb-4">BYD 연식별 구매 가이드 (피해야 할 연식)</h1>
      
      <section className="space-y-4">
        <h2 className="text-3xl font-semibold text-gray-800">돌핀 (Dolphin)</h2>
        
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4">
          <h3 className="text-xl font-bold text-yellow-700">⚠️ 2021~2023년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>에어컨 하얀 가루 (Al(OH)3):</strong> 에어컨 에바코어 코팅 불량으로 인해 호흡기에 치명적인 하얀 알루미늄 가루가 실내로 뿜어져 나오는 심각한 결함 발생.</li>
            <li><strong>조향장치 결함:</strong> 23년식에서 핸들 조향장치(CEPS) 컨트롤러 기판 마찰로 인한 파워스티어링 상실 위험 (대규모 리콜 진행됨).</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4">
          <h3 className="text-xl font-bold text-green-700">✅ 2024~2025년식: BUY SAFE (적극 추천)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>에바코어 코팅이 개선되었고 새로운 후륜 멀티링크 서스펜션이 적용되어 타이어 편마모와 승차감이 대폭 개선되었습니다. 배터리 교체 비용도 전 세계 최저 수준(약 900만 원 선)으로 유지비가 매우 저렴합니다.</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8">
        <h2 className="text-3xl font-semibold text-gray-800">시라이언 07 (Sealion 07)</h2>
        
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4">
          <h3 className="text-xl font-bold text-yellow-700">⚠️ 2024년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>12-in-1 모터 통짜 수리비 폭탄:</strong> 모터, 인버터, 충전기 등이 12-in-1으로 통합되어 있어 부품 하나만 고장 나도 전체 모듈을 통째로 교체해야 함 (보증 수리 외 비용 약 600만 원 발생).</li>
            <li><strong>CTB (Cell-to-Body) 배터리 파손 위험:</strong> 배터리 케이스가 차량 하부 바닥과 일체형이라서 주행 중 돌을 밟아 하부가 5mm만 찌그러져도 배터리 전체(약 1,400만 원)를 통교체해야 하는 치명적 수리 지옥 리스크.</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4">
          <h3 className="text-xl font-bold text-green-700">✅ 2025년식: BUY SAFE (추천)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>루프 라이다 세정 노즐 결함 개선 및 초기 하체 세팅이 수정되었습니다. 단, CTB 통짜 배터리의 구조적 한계(하부 긁힘 시 전손 위기)는 25년식도 동일하므로 반드시 하부 코팅이나 주의 운전이 필요합니다.</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8">
        <h2 className="text-3xl font-semibold text-gray-800">씰 (Seal)</h2>
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4">
          <h3 className="text-xl font-bold text-yellow-700">⚠️ 2022~2023년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>LFP 배터리 겨울철 셧다운(25%에서 갑자기 0%로 추락) 및 하체 나사 부식 발생.</li>
          </ul>
        </div>
        <div className="bg-green-50 border-l-4 border-green-500 p-4">
          <h3 className="text-xl font-bold text-green-700">✅ 2024년식: BUY SAFE (적극 추천)</h3>
        </div>
      </section>

      <section className="space-y-4 mt-8">
        <h2 className="text-3xl font-semibold text-gray-800">아토 3 (Atto 3)</h2>
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4">
          <h3 className="text-xl font-bold text-yellow-700">⚠️ 2022~2024년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>초기형 에어컨 곰팡이 냄새 고질병 및 앞바퀴 털림 증상. 24년식에 일부 개선되었으나 여전히 앞 서스펜션 세팅이 너무 무릅니다.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}
