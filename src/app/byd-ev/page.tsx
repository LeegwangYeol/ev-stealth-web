export default function BydEvPage() {
  return (
    <div className="space-y-8 py-10">
      <h1 className="text-4xl font-bold border-b pb-4">BYD (비야디) 핵심 결함 및 예상 수리비</h1>
      
      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-red-600">🚨 블레이드 배터리 팩(CTP) 하부 긁힘 전손 트랩</h2>
        <ul className="list-disc pl-6 space-y-2 text-gray-700">
          <li><strong>결함 내용:</strong> 배터리 셀을 팩에 접착제로 아예 발라버린 &apos;셀투팩(CTP)&apos; 구조 탓에, 하부에 살짝만 긁혀도 부분 수리가 아예 불가능하고 무조건 배터리 전체를 갈아야 함.</li>
          <li><strong>예상 수리비:</strong> <strong>1,450만 원 ~ 3,400만 원</strong> (경미한 긁힘에도 차량 가액의 70~90% 수리비 폭탄으로 전손 처리 속출).</li>
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-red-600">🚨 배터리 팩 빗물 누수 및 고전압 차단</h2>
        <ul className="list-disc pl-6 space-y-2 text-gray-700">
          <li><strong>결함 내용:</strong> 팩 마감 가스켓 불량 및 압력 밸브 변형으로 빗물이 스며들어 고전압 절연 파괴 및 주행 중 셧다운 발생 (중국에서만 11만 대 리콜).</li>
          <li><strong>예상 수리비:</strong> <strong>1,200만 원 ~ 2,200만 원</strong>.</li>
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-red-600">🚨 가벼운 접촉 사고 수리비 폭탄 (공임비 거품)</h2>
        <ul className="list-disc pl-6 space-y-2 text-gray-700">
          <li><strong>결함 내용:</strong> 저속으로 주차장 범퍼 접촉 사고만 나도 센서 뭉치가 박살남. 특히 수입차 공임(시간당 11만 5천 원)이 적용되어 수리비가 비정상적으로 부풀려짐.</li>
          <li><strong>예상 수리비:</strong> 단순 범퍼/센서 파손 시 <strong>650만 원 ~ 1,150만 원</strong>.</li>
        </ul>
      </section>
    </div>
  );
}
