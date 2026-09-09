import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center space-y-12 py-20">
      <div className="text-center space-y-4">
        <h1 className="text-5xl font-extrabold tracking-tight text-slate-900">
          글로벌 EV 중고차 연식별 피하기 가이드
        </h1>
        <p className="text-xl text-gray-600 max-w-2xl mx-auto">
          &quot;테슬라 사지 마라&quot;가 아니라 <strong>&quot;테슬라 모델3 2017~2020년식은 피해라&quot;</strong>가 맞습니다. 특정 모델과 연식별(Model Year) 고질병을 정확하게 파헤칩니다.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8 w-full max-w-6xl">
        <Link href="/2026-latest"
          className="group block p-6 bg-blue-50 border border-blue-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300">
          <h2 className="text-2xl font-bold mb-3 text-blue-700 group-hover:text-blue-800">🔥 2026년식 KDM 최신 리뷰 &rarr;</h2>
          <p className="text-gray-700 leading-relaxed">
            방금 출고된 EV3, 26년식 모델Y, 아이오닉9, BYD 시라이언7의 한국 차주 리얼 후기와 초기 결함 총정리! (출처 포함)
          </p>
        </Link>

        <Link href="/pdi-checklist"
          className="group block p-6 bg-green-50 border border-green-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300">
          <h2 className="text-2xl font-bold mb-3 text-green-700 group-hover:text-green-800">✅ 신차 인수(PDI) 체크리스트 &rarr;</h2>
          <p className="text-gray-700 leading-relaxed">
            호갱 방지! 탁송된 전기차 서명 전 스마트폰으로 열어보고 하나씩 체크하세요. 하부 배터리팩 찍힘 등 필수 확인 항목.
          </p>
        </Link>

        <Link href="/hyundai-kia"
          className="group block p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300">
          <h2 className="text-2xl font-bold mb-3 group-hover:text-blue-600">현대/기아 연식별 &rarr;</h2>
          <p className="text-gray-600 leading-relaxed">
            아이오닉5, EV6, GV60의 초기형(21~22년식) ICCU 결함 피하는 법 및 구매 추천 연식.
          </p>
        </Link>

        <Link href="/tesla"
          className="group block p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300">
          <h2 className="text-2xl font-bold mb-3 group-hover:text-blue-600">테슬라 연식별 &rarr;</h2>
          <p className="text-gray-600 leading-relaxed">
            모델3/모델Y 히트펌프 사망 결함, 컨트롤 암 파손을 피하기 위한 연식 선택 가이드.
          </p>
        </Link>

        <Link href="/byd"
          className="group block p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300">
          <h2 className="text-2xl font-bold mb-3 group-hover:text-blue-600">BYD 연식별 &rarr;</h2>
          <p className="text-gray-600 leading-relaxed">
            돌핀 에어컨 백색 가루 결함, 시라이언 07 CTB 파손 위험 등 주력 모델 피하기 매트릭스.
          </p>
        </Link>

        <Link href="/global-brands"
          className="group block p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300">
          <h2 className="text-2xl font-bold mb-3 group-hover:text-blue-600">폭스바겐/벤츠/폴스타 &rarr;</h2>
          <p className="text-gray-600 leading-relaxed">
            볼트EV 화재 리콜, 폭스바겐 ID.4 주행 중 문열림, 벤츠 7,500만 원 배터리 교체비 리포트.
          </p>
        </Link>
      </div>
    </div>
  );
}
