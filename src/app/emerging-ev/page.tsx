export default function EmergingEvPage() {
  return (
    <div className="space-y-8 py-10">
      <h1 className="text-4xl font-bold border-b pb-4">신흥 스타트업 EV 장기 소유 트랩 분석</h1>
      
      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-red-600">🚨 리비안 (Rivian): 통짜 프레임 수리 지옥</h2>
        <ul className="list-disc pl-6 space-y-2 text-gray-700">
          <li><strong>결함 내용:</strong> 차체 뒤쪽이 하나로 이어져 있는 통짜 구조라, 후방에 시속 4km로 가볍게 부딪혀서 찌그러져도 차체 뼈대를 잘라내고 수리해야 함.</li>
          <li><strong>예상 수리비:</strong> 가벼운 찌그러짐 수리에 <strong>3,750만 원 ~ 6,000만 원</strong> (신차 가격의 거의 절반).</li>
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-red-600">🚨 샤오미 (Xiaomi SU7): 브레이크 파열 및 수리비 폭탄</h2>
        <ul className="list-disc pl-6 space-y-2 text-gray-700">
          <li><strong>결함 내용:</strong> 트랙 주행 시 브레이크 패드가 갈려나가며 고속 충돌 사고 발생. 배터리가 차체에 결합된 CTB(Cell to Body) 구조라 하부 충격 시 수리가 불가함.</li>
          <li><strong>예상 수리비:</strong> 하부 충격 및 파손 수리 시 <strong>2,800만 원 ~ 3,200만 원</strong> (신차 가격이 4천만 원대인데 수리비가 3천만 원).</li>
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-red-600">🚨 루시드 (Lucid Air): 인버터 결함 및 수리비 거품</h2>
        <ul className="list-disc pl-6 space-y-2 text-gray-700">
          <li><strong>결함 내용:</strong> 인버터 커넥터 마모로 인해 고속도로 주행 중 동력이 끊어지는 현상. 또한 전면 유리 파손 시 독자적인 ADAS 보정 때문에 수리비가 기하급수적으로 증가함.</li>
          <li><strong>예상 수리비:</strong> 수리 시 <strong>430만 원 ~ 3,750만 원</strong> (독점적 서비스 센터 수리비).</li>
        </ul>
      </section>
    </div>
  );
}
