export default function HyundaiKiaPage() {
  return (
    <div className="space-y-8 py-10 max-w-4xl mx-auto">
      <h1 className="text-4xl font-bold border-b pb-4">현대/기아 연식별 구매 가이드 (피해야 할 연식)</h1>
      
      <section className="space-y-4">
        <h2 className="text-3xl font-semibold text-gray-800">아이오닉 5 (Ioniq 5)</h2>
        
        <div className="bg-red-50 border-l-4 border-red-500 p-4">
          <h3 className="text-xl font-bold text-red-700">🚫 2021~2022년식: AVOID (절대 피할 것)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>ICCU 결함:</strong> 800V ICCU 내부 퓨즈가 끊어지며 고속도로에서 갑자기 차가 서버림 (예상 수리비 525만 원 ~ 692만 원).</li>
            <li><strong>후방 와이퍼 부재:</strong> 비 오는 날 후방 시야가 완전히 가려져 심각한 안전 문제 발생.</li>
            <li><strong>조치:</strong> 이 연식은 감가가 심하더라도 피하는 것이 상책입니다.</li>
          </ul>
        </div>

        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4">
          <h3 className="text-xl font-bold text-yellow-700">⚠️ 2023~2024년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>배터리가 77.4kWh로 커지고 프리컨디셔닝이 추가되었으나, 여전히 ICCU 리콜(24V-868) 대상입니다.</li>
            <li><strong>조치:</strong> 딜러나 서비스센터에서 ICCU 리콜이 완료되었는지 반드시 확인 후 구매하세요.</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4">
          <h3 className="text-xl font-bold text-green-700">✅ 2025년식 (Facelift): BUY SAFE (적극 추천)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>공장 출고 때부터 ICCU 하드웨어가 개선되었고, 84kWh로 배터리 용량 증가, 후방 와이퍼가 기본 장착되었습니다. 가장 추천하는 연식입니다.</li>
          </ul>
        </div>
      </section>

      <section className="space-y-4 mt-8">
        <h2 className="text-3xl font-semibold text-gray-800">기아 EV6</h2>
        
        <div className="bg-red-50 border-l-4 border-red-500 p-4">
          <h3 className="text-xl font-bold text-red-700">🚫 2022년식: AVOID (절대 피할 것)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li><strong>초기 결함:</strong> 충전구 잠금 핀이 고착되어 충전기가 안 빠지는 문제, 너무 단단한 서스펜션 세팅으로 인한 승차감 저하.</li>
          </ul>
        </div>

        <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4">
          <h3 className="text-xl font-bold text-yellow-700">⚠️ 2023~2024년식: CAUTION (주의 요망)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>후륜 구동축 톱니바퀴(스플라인) 파손 리콜(24V-057) 및 메리디안 오디오 앰프 고장(수리비 100만 원 이상) 위험이 있습니다.</li>
          </ul>
        </div>

        <div className="bg-green-50 border-l-4 border-green-500 p-4">
          <h3 className="text-xl font-bold text-green-700">✅ 2025년식 (Facelift): BUY SAFE (적극 추천)</h3>
          <ul className="list-disc pl-6 mt-2 text-gray-700 space-y-1">
            <li>승차감이 크게 개선되었고 초기 기계적 결함이 대부분 잡혔습니다.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}
