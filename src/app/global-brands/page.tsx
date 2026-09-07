export default function GlobalEvPage() {
  return (
    <div className="space-y-8 py-10 max-w-4xl mx-auto">
      <h1 className="text-4xl font-bold border-b pb-4">유럽 및 북미 EV 연식별 가이드 (폭스바겐, 리비안, 폴스타 등)</h1>
      
      <section className="space-y-4">
        <h2 className="text-3xl font-semibold text-gray-800">쉐보레 볼트 EV / EUV</h2>
        <div className="bg-red-50 border-l-4 border-red-500 p-4">
          <h3 className="text-xl font-bold text-red-700">🚫 2017~2022년식: AVOID (절대 피할 것 - 배터리 화재)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>LG화학 파우치셀 화재 리콜:</strong> 분리막 접힘과 양극 탭 찢어짐이라는 2가지 희귀 제조 결함이 겹치면서 대형 배터리 화재 연쇄 발생.</li>
            <li><strong>조치:</strong> 중고차 구매 시 &apos;배터리 팩이 완전히 새것으로 교체된 차량&apos;이 아니면 절대 구매 금지. 배터리 자비 교체 비용은 약 2,200만 원.</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8">
        <h2 className="text-3xl font-semibold text-gray-800">폭스바겐 ID.4</h2>
        <div className="bg-red-50 border-l-4 border-red-500 p-4">
          <h3 className="text-xl font-bold text-red-700">🚫 2021~2024년식: AVOID (주행 중 문 열림 결함)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>주행 중 도어 열림 리콜:</strong> 플러시 도어 핸들 내부로 세차장 물이나 빗물이 스며들면 터치 센서가 이를 &apos;사람 손&apos;으로 인식해 주행 중인데도 차문이 열려버리는 치명적 결함 발생. 대규모 리콜 및 판매 중단 사태.</li>
            <li><strong>히트펌프 콤프레셔 박살:</strong> 겨울철 고압 R744(CO2) 히트펌프 배관 누수로 콤프레셔가 박살나며 쇳가루가 도는 현상 (수리비 550만 원).</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8">
        <h2 className="text-3xl font-semibold text-gray-800">볼보 EX30 / 폴스타 2</h2>
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4">
          <h3 className="text-xl font-bold text-yellow-700">⚠️ 2021~2024년식: CAUTION (소프트웨어 및 히터 결함)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>EX30 속도계 먹통:</strong> 모든 계기판을 중앙 12.3인치 스크린에 통합했으나 소프트웨어 에러로 주행 중 속도계 화면이 꺼지는 결함 리콜.</li>
            <li><strong>폴스타 2 세라믹 히터 파괴:</strong> 겨울철 고전압 냉각수 히터(HVCH) 내부 세라믹 부품이 쪼개지며 절연 파괴 에러로 히터 셧다운 (수리비 약 270만 원).</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8">
        <h2 className="text-3xl font-semibold text-gray-800">메르세데스-벤츠 EQE / EQS</h2>
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4">
          <h3 className="text-xl font-bold text-yellow-700">⚠️ 2022~2023년식: CAUTION (수리비 폭탄 주의)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>모터라이즈 도어핸들 박살:</strong> 겨울철 얼음이 얼었을 때 도어 핸들 모터가 억지로 튀어나오려다 내부 플라스틱 기어 이빨이 다 부서짐 (수리비 짝당 190만 원).</li>
            <li><strong>배터리 수리비 절망편:</strong> 118kWh EQS 배터리팩 무상보증 종료 후 교체 비용은 약 <strong>7,560만 원</strong>으로 중고차 가격 전체를 상회하는 끔찍한 리스크를 안고 있습니다.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}
