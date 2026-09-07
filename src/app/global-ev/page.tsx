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
        <h2 className="text-2xl font-semibold text-red-600">🚨 현대/기아 (HMG) 핵심 불만 TOP 3</h2>
        <ul className="list-disc pl-6 space-y-2 text-gray-700">
          <li><strong>ICCU 주행 중 셧다운 (782회):</strong> 고속도로 주행 중 동력이 끊어지며 거북이 모드로 멈춰버리는 치명적 결함.</li>
          <li><strong>배터리 하부 긁힘 통교체 (654회):</strong> 과속방지턱에 하부가 1~2mm만 긁혀도 배터리 팩 전체 교체(2,400만 원) 판정.</li>
          <li><strong>완속 충전 3.5kW 꼼수 (472회):</strong> 화재 예방을 핑계로 완속 충전 속도를 강제로 반토막 내버리는 소프트웨어 업데이트.</li>
        </ul>
      </section>

      <section className="space-y-4">
        <h2 className="text-2xl font-semibold text-red-600">🚨 수입 프리미엄 브랜드 핵심 불만</h2>
        <ul className="list-disc pl-6 space-y-2 text-gray-700">
          <li><strong>메르세데스 EQ (745회):</strong> 중국산 파라시스 배터리 논란 및 브레이크 스펀지 현상.</li>
          <li><strong>BMW i 시리즈 (542회):</strong> 콘티넨탈사 통합 브레이크 모듈 결함으로 브레이크가 돌덩이처럼 굳어버리는 현상.</li>
          <li><strong>포르쉐 타이칸 (498회):</strong> 겨울철 PTC 히터 사망 및 하부 스토퍼 긁힘에 8,500만 원 수리비 청구.</li>
        </ul>
      </section>
    </div>
  );
}
