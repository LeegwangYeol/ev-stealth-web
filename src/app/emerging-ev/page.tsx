export default function EmergingEvPage() {
  return (
    <div className="space-y-8 py-10">
      <h1 className="text-4xl font-bold border-b pb-4">신흥 스타트업 EV 장기 소유 트랩 분석</h1>
      
      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-red-600">🚨 샤오미 (SU7) 설계 결함</h2>
        <ul className="list-disc pl-6 space-y-2 text-gray-700">
          <li><strong>전동 트렁크 단두대 결함:</strong> 마지막 2cm를 당겨주는 소프트 클로징 모터에 끼임 방지 기능이 없어 아이 손가락이 다치는 사고 다수. 제조사는 &apos;업계 관례&apos;라며 대응 거부.</li>
          <li><strong>노출된 에어서스펜션 탱크:</strong> 트렁크 넓이를 위해 하단 후방 범퍼빔 아래에 보호판 없이 고압 탱크를 매달아, 경미한 후방 추돌에도 에어서스 전체가 전손 처리됨.</li>
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-red-600">🚨 리비안 & 루시드의 스타트업 한계</h2>
        <ul className="list-disc pl-6 space-y-2 text-gray-700">
          <li><strong>리비안 12V 셧다운:</strong> 12V 배터리가 방전되면 주행 중에도 차량 전체가 셧다운되며 비상등조차 켜지지 않는 아찔한 상황 발생.</li>
          <li><strong>루시드 수리 지옥:</strong> 경미한 하네스 교체 사고에도 부품 재고가 없어 11주 이상 방치. 찌그덕 소리와 조립 불량으로 &apos;죽음의 천 번 찌르기&apos; 원성.</li>
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-red-600">🚨 장기 소유 소프트웨어/OTA 트랩</h2>
        <ul className="list-disc pl-6 space-y-2 text-gray-700">
          <li><strong>테슬라 레이더 강제 비활성화:</strong> 차량 구매 시 포함되었던 물리 레이더를 OTA 업데이트로 강제 삭제 후 비전(카메라) 전용으로 전환. 이후 그림자를 장애물로 오인하는 &apos;유령 제동(Phantom Braking)&apos; 급증.</li>
          <li><strong>리비안 OTA 벽돌화:</strong> 직원의 실수로 잘못된 인증서가 배포되는 바람에 9천만 원짜리 트럭의 화면과 공조기가 밤사이 먹통(벽돌화)이 된 사태.</li>
        </ul>
      </section>
    </div>
  );
}
