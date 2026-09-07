import Link from 'next/link';

export default function Latest2026Page() {
  return (
    <div className="space-y-10">
      <header className="border-b pb-6">
        <h1 className="text-4xl font-extrabold text-slate-900 mb-4">2026년식 KDM(국내 내수용) EV 초기 품질 리포트</h1>
        <p className="text-lg text-gray-600">
          올해 막 출고된 2026년식 최신 전기차(아이오닉 5 페이스리프트, EV3, 아이오닉 9, 테슬라 모델Y, BYD 시라이언 7)의 한국 차주 실제 평가와 초기 결함을 100% 원문 출처(보배드림, 레딧 등)와 함께 분석했습니다.
        </p>
      </header>

      <section>
        <h2 className="text-3xl font-bold text-slate-800 mb-6 border-l-4 border-red-500 pl-4">1. 기아 EV3 (2026)</h2>
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-200">
          <ul className="list-disc list-inside space-y-3 text-gray-700">
            <li>
              <strong>초기 결함:</strong> 주행 중 계기판에 &quot;전기차 시스템을 점검하십시오&quot; 문구가 뜨며 시동이 꺼지고 동력이 차단되는 결함(MCU 통신 오류). 한국교통안전공단 무상수리 및 리콜 실시.
            </li>
            <li>
              <strong>차주 리얼 후기:</strong> &quot;도심 주행 중 갑작스러운 동력 상실로 뒤차와 추돌할 뻔해 생명의 위협을 느꼈다.&quot;
            </li>
            <li>
              <strong>출처:</strong> <Link href="https://m.bobaedream.co.kr/board/bbs_view/national/2328953/2/1" target="_blank" className="text-blue-600 hover:underline">보배드림 커뮤니티 원문</Link> | <Link href="https://www.autodaily.co.kr/news/articleView.html?idxno=535684" target="_blank" className="text-blue-600 hover:underline">오토데일리 기사</Link>
            </li>
          </ul>
        </div>
      </section>

      <section>
        <h2 className="text-3xl font-bold text-slate-800 mb-6 border-l-4 border-blue-500 pl-4">2. 더 뉴 아이오닉 5 페이스리프트 (2026)</h2>
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-200">
          <ul className="list-disc list-inside space-y-3 text-gray-700">
            <li>
              <strong>초기 결함:</strong> 이전 연식의 고질병인 ICCU(통합충전제어장치) 고장으로 주행 중 거북이 모드(출력 제한) 발생 및 완속/급속 충전 불능 상태 돌입. 신규 ccNC 인포테인먼트 무선 카플레이 멈춤 버그.
            </li>
            <li>
              <strong>차주 리얼 후기:</strong> &quot;페이스리프트 신차임에도 이전 모델의 ICCU 문제가 터졌다. 고속 주행 중 출력 저하로 불안감이 큼.&quot;
            </li>
            <li>
              <strong>출처:</strong> <Link href="https://www.reddit.com/r/Ioniq5/comments/1ibf63c/800_miles_in_my_2025_ioniq_5_officially_has_a/" target="_blank" className="text-blue-600 hover:underline">레딧 차주 인증</Link> | <Link href="https://m.bobaedream.co.kr/board/bbs_view/national/2317279" target="_blank" className="text-blue-600 hover:underline">보배드림 출력저하 후기</Link>
            </li>
          </ul>
        </div>
      </section>

      <section>
        <h2 className="text-3xl font-bold text-slate-800 mb-6 border-l-4 border-indigo-500 pl-4">3. 테슬라 모델 Y (2026 주니퍼 리프레시 / 테슬라 코리아)</h2>
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-200">
          <ul className="list-disc list-inside space-y-3 text-gray-700">
            <li>
              <strong>초기 결함:</strong> 동절기 12V 저전압 배터리 전력 부족 시 플러시 도어 핸들이 얼거나 래치가 열리지 않아 탑승 불가. 컨트롤 암 부싱 조기 마모로 방지턱 통과 시 덜컹거림 찌걱 소음 발생.
            </li>
            <li>
              <strong>차주 리얼 후기:</strong> &quot;기가 상하이 생산이라 단차는 나아졌지만, 혹한기 아침에 문이 안 열려서 출근에 큰 차질을 빚었다.&quot;
            </li>
            <li>
              <strong>출처:</strong> <Link href="https://www.bobaedream.co.kr/view?code=cnews&No=872" target="_blank" className="text-blue-600 hover:underline">보배드림 문 열림 결함 보도</Link> | <Link href="https://m.bobaedream.co.kr/board/bbs_view/best/927611/2/2?cmt=1" target="_blank" className="text-blue-600 hover:underline">하부 소음 후기</Link>
            </li>
          </ul>
        </div>
      </section>

      <section>
        <h2 className="text-3xl font-bold text-slate-800 mb-6 border-l-4 border-green-500 pl-4">4. BYD 시라이언 7 (2026 BYD 코리아)</h2>
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-200">
          <ul className="list-disc list-inside space-y-3 text-gray-700">
            <li>
              <strong>초기 결함:</strong> 섀시 하부 서브프레임 접합부 및 휠 하우스 안쪽 용접 부위 조기 부식(녹) 현상 발견. DiLink 인포테인먼트의 어색한 한글 번역 및 공공 급속 충전기(E-pit 등) 충전 타임아웃 오류.
            </li>
            <li>
              <strong>차주 리얼 후기:</strong> &quot;가격은 매력적이나 하체 방청 수준이 엉망이라 겨울 염화칼슘 도로를 타면 금방 썩을 것 같다. 내비 번역체도 거슬린다.&quot;
            </li>
            <li>
              <strong>출처:</strong> <Link href="https://www.bobaedream.co.kr/view?code=best&No=888548" target="_blank" className="text-blue-600 hover:underline">보배드림 조기 녹(부식) 현상</Link> | <Link href="https://m.bobaedream.co.kr/board/bbs_view/cnews/595" target="_blank" className="text-blue-600 hover:underline">충전기 호환성 문제</Link>
            </li>
          </ul>
        </div>
      </section>
      
      <section>
        <h2 className="text-3xl font-bold text-slate-800 mb-6 border-l-4 border-yellow-500 pl-4">5. 현대 아이오닉 9 (2026 플래그십)</h2>
        <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-200">
          <ul className="list-disc list-inside space-y-3 text-gray-700">
            <li>
              <strong>초기 결함:</strong> 주행거리 389km 만에 배터리 제어 시스템 경고등 점등 및 고전압 배터리팩 내부 PCB 기판 소손 판정으로 배터리 분해 수리. 2열 도어와 쿼터 글라스 몰딩 간격 유격 불량.
            </li>
            <li>
              <strong>차주 리얼 후기:</strong> &quot;8천만 원짜리 차를 뽑자마자 고전압 배터리를 통째로 뜯어내야 한다고 해서 환불을 요구 중이다.&quot;
            </li>
            <li>
              <strong>출처:</strong> <Link href="https://m.bobaedream.co.kr/board/bbs_view/best/1008916/2/8?cmt=1" target="_blank" className="text-blue-600 hover:underline">보배드림 아이오닉9 배터리 결함</Link>
            </li>
          </ul>
        </div>
      </section>

    </div>
  );
}
