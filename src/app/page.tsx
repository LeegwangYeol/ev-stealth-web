import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center space-y-12 py-20">
      <div className="text-center space-y-4">
        <h1 className="text-5xl font-extrabold tracking-tight text-slate-900">
          대규모 에이전트 리포트 허브
        </h1>
        <p className="text-xl text-gray-600 max-w-2xl mx-auto">
          전기차의 숨겨진 치명적 결함부터 출퇴근족을 위한 스텔스 미니벨로 개조 가이드까지, 전 세계 5천 건 이상의 커뮤니티 데이터 분석 결과를 확인하세요.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 w-full max-w-5xl">
        <Link href="/global-ev"
          className="group block p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300">
          <h2 className="text-2xl font-bold mb-3 group-hover:text-blue-600">글로벌 EV 치명적 결함 &rarr;</h2>
          <p className="text-gray-600 leading-relaxed">
            테슬라, 현기차, 수입 프리미엄 브랜드들의 충격적인 실소유주 결함과 수리비 폭탄 리포트.
          </p>
        </Link>

        <Link href="/emerging-ev"
          className="group block p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300">
          <h2 className="text-2xl font-bold mb-3 group-hover:text-blue-600">신흥 EV 트랩 분석 &rarr;</h2>
          <p className="text-gray-600 leading-relaxed">
            샤오미, 리비안, 루시드의 하드웨어 결함 및 OTA 구독형 소프트웨어 갑질 사태 요약.
          </p>
        </Link>

        <Link href="/stealth-minivelo"
          className="group block p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300">
          <h2 className="text-2xl font-bold mb-3 group-hover:text-blue-600">스텔스 미니벨로 마스터 가이드 &rarr;</h2>
          <p className="text-gray-600 leading-relaxed">
            전철 단속을 피하기 위한 완벽한 초소형 모터/배터리 세팅 및 개조 실패 포렌식 분석.
          </p>
        </Link>
      </div>
    </div>
  );
}
