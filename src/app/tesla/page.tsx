export default function TeslaPage() {
  return (
    <div className="space-y-8 py-10 max-w-4xl mx-auto">
      <h1 className="text-4xl font-bold border-b pb-4">테슬라 연식별 구매 가이드 (피해야 할 연식)</h1>
      
      <section className="space-y-4">
        <h2 className="text-3xl font-semibold text-gray-800">모델 3 (Model 3)</h2>
        
        <div className="bg-red-50 border-l-4 border-red-500 p-4">
          <h3 className="text-xl font-bold text-red-700">🚫 2017~2020년식: AVOID (절대 피할 것)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>히터 파괴:</strong> PTC 고전압 히터가 타버려서 겨울에 얼어 죽을 수 있음 (수리비 168만 원 ~ 567만 원).</li>
            <li><strong>컨트롤 암 찌그덕:</strong> 앞바퀴 서스펜션 볼조인트에 물이 들어가 부서지면서 침대 스프링 소리가 남.</li>
            <li><strong>범퍼 물고임:</strong> 비 오는 날 뒷범퍼 아래에 물이 고여 범퍼가 통째로 뜯겨나가는 결함. 히트펌프도 없어서 겨울철 주행거리 반토막.</li>
          </ul>
        </div>

        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4">
          <h3 className="text-xl font-bold text-yellow-700">⚠️ 2021~2023년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>히트펌프 사망:</strong> 옥토밸브(히트펌프) 결함으로 한파에 에어컨/히터가 모두 죽는 결함 발생 (수리비 87만 원 ~ 661만 원).</li>
            <li>LFP 배터리 탑재 모델(RWD)은 겨울철 100% 완충을 자주 안 해주면 배터리 계산 오류로 차가 멈출 수 있습니다.</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4">
          <h3 className="text-xl font-bold text-green-700">✅ 2024년식 (Highland): BUY SAFE (적극 추천)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>승차감이 극적으로 개선(FSD 댐퍼)되었고, 방음이 엄청나게 좋아졌습니다. 깜빡이 레버가 없어진 것만 적응하면 최고의 선택입니다.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}
