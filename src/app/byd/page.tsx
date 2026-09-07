export default function BydPage() {
  return (
    <div className="space-y-8 py-10 max-w-4xl mx-auto">
      <h1 className="text-4xl font-bold border-b pb-4">BYD 연식별 구매 가이드 (피해야 할 연식)</h1>
      
      <section className="space-y-4">
        <h2 className="text-3xl font-semibold text-gray-800">씰 (Seal)</h2>
        
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4">
          <h3 className="text-xl font-bold text-yellow-700">⚠️ 2022~2023년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>LFP 배터리 셧다운:</strong> 영하의 날씨에서 배터리가 25% 남았는데 순식간에 0%로 곤두박질치며 차가 서버리는 현상.</li>
            <li><strong>하부 부식:</strong> 하체 나사들에 저렴한 아연 도금이 쓰여서, 겨울철 염화칼슘을 만나면 뻘겋게 녹이 슬어버립니다 (부식 수리비 121만 원 ~ 297만 원).</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4">
          <h3 className="text-xl font-bold text-green-700">✅ 2024년식: BUY SAFE (적극 추천)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>BMS(배터리 관리 시스템) 소프트웨어가 개선되어 겨울철 셧다운이 해결되었고, 하체 부품에 부식 방지 코팅(Dacromet)이 적용되었습니다. 승차감도 대폭 개선되었습니다.</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8">
        <h2 className="text-3xl font-semibold text-gray-800">아토 3 (Atto 3)</h2>
        
        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4">
          <h3 className="text-xl font-bold text-yellow-700">⚠️ 2022~2023년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>에어컨 쉰내:</strong> 에어컨 안에 물이 고이면서 심한 곰팡이 냄새가 지속적으로 발생.</li>
            <li><strong>앞바퀴 털림:</strong> 급가속 시 앞바퀴가 덜덜 떨리며 그립을 잃어버리는 현상 발생 (엔진 마운트가 너무 무름).</li>
          </ul>
        </div>

        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4">
          <h3 className="text-xl font-bold text-yellow-700">⚠️ 2024년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>타이어가 고급(콘티넨탈)으로 바뀌고 에어컨 냄새 등은 잡혔으나, 방지턱을 넘을 때 앞 서스펜션이 여전히 너무 물렁거린다는 단점이 있습니다. 가성비 출퇴근용으로만 적합합니다.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}
