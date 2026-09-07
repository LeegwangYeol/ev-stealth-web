export default function GlobalEvPage() {
  return (
    <div className="space-y-8 py-10">
      <h1 className="text-4xl font-bold border-b pb-4">글로벌 EV 치명적 결함 분석</h1>
      
      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-red-600">🚨 테슬라 (Tesla) 핵심 불만 TOP 3</h2>
        <ul className="list-disc pl-6 space-y-2 text-gray-700">
          <li><strong>기가캐스팅 전손대란 (689회):</strong> 차체 뒷부분 일체형 설계로 가벼운 후방 추돌에도 부품 교체 불가, 4,000만 원짜리 전손 처리 및 보험료 폭등.</li>
          <li><strong>초음파 센서 삭제 (425회):</strong> 원가 절감을 위해 비전(카메라)에만 의존, 앞범퍼 1.5m 맹안(사각지대) 발생으로 사고 빈발.</li>
          <li><strong>혹한기 옥토밸브 파손 (612회):</strong> 영하 15도에서 열관리 시스템 파손으로 히터 정지 및 LFP 배터리 주행거리 45% 급감.</li>
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-red-600">🚨 국내 전기차 (현대/기아) 핵심 결함 및 예상 수리비</h2>
        <ul className="list-disc pl-6 space-y-2 text-gray-700">
          <li><strong>ICCU 주행 중 셧다운:</strong> 고속도로 주행 중 전력 반도체 열 스트레스로 12V 배터리 충전이 멈추고 셧다운되는 치명적 결함. 무상수리 기간(10년/16만km) 경과 시 수리비 <strong>346만 원 ~ 478만 원</strong>.</li>
          <li><strong>배터리 팩 하부 2~3mm 긁힘 통교체:</strong> 과속방지턱에 배터리 커버가 2mm만 긁혀도 무조건 전체 교체 판정. 수리비 <strong>2,050만 원 ~ 3,700만 원</strong> (특약 없을 시 감가상각비 400~800만 원 별도 청구).</li>
          <li><strong>구동 모터 및 감속기 갈림 (&apos;우주선 소리&apos;):</strong> 모터의 강력한 토크를 감속기가 버티지 못해 쇳가루 발생 및 베어링 손상. 모터+감속기 통교체 시 <strong>510만 원 ~ 650만 원</strong>.</li>
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-red-600">🚨 해외/수입 전기차 (테슬라, 벤츠, 포르쉐) 수리비 폭탄</h2>
        <ul className="list-disc pl-6 space-y-2 text-gray-700">
          <li><strong>메르세데스-벤츠 EQ 2mm 긁힘 룰:</strong> 중국산 파라시스 배터리 화재 논란. 하부 2mm 긁힘 시 배터리 팩 전체 교환 비용 <strong>7,000만 원 ~ 1억 원</strong> (중고차 가격 초과).</li>
          <li><strong>포르쉐 타이칸 800V 배터리 셀 사망:</strong> 보증 종료 후 분리막 결함으로 쇼트 발생 시 배터리 교체 비용 <strong>6,700만 원 ~ 1억 1,700만 원</strong>.</li>
          <li><strong>테슬라 보증 종료 후 배터리 사망 쇼크:</strong> 5~8년 주행 후 BMS_a066 에러 발생 시 리퍼 배터리 교체 비용 <strong>1,600만 원 ~ 3,100만 원</strong>.</li>
        </ul>
      </section>
    </div>
  );
}
