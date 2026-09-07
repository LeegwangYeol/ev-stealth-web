import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-col items-center justify-center space-y-12 py-20">
      <div className="text-center space-y-4">
        <h1 className="text-5xl font-extrabold tracking-tight text-slate-900">
          글로벌 EV 치명적 결함 허브
        </h1>
        <p className="text-xl text-gray-600 max-w-2xl mx-auto">
          BYD, 현기차, 테슬라 등 전 세계 전기차의 숨겨진 하드웨어 결함과 경악스러운 배터리 교체 수리비 폭탄 리포트.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 w-full max-w-5xl">
        <Link href="/byd-ev"
          className="group block p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300">
          <h2 className="text-2xl font-bold mb-3 group-hover:text-blue-600">BYD 결함 및 수리비 &rarr;</h2>
          <p className="text-gray-600 leading-relaxed">
            블레이드 배터리 CTP 구조적 한계와 공임비 거품으로 인한 전손 트랩 및 빗물 누수 셧다운 분석.
          </p>
        </Link>

        <Link href="/global-ev"
          className="group block p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300">
          <h2 className="text-2xl font-bold mb-3 group-hover:text-blue-600">국내/수입 EV 결함 &rarr;</h2>
          <p className="text-gray-600 leading-relaxed">
            현대/기아차 ICCU 셧다운, 하부 2mm 긁힘 배터리 통교체, 테슬라 및 벤츠의 치명적 설계 결함 정리.
          </p>
        </Link>

        <Link href="/emerging-ev"
          className="group block p-6 bg-white border border-gray-200 rounded-2xl shadow-sm hover:shadow-xl transition-all duration-300">
          <h2 className="text-2xl font-bold mb-3 group-hover:text-blue-600">신흥 스타트업 EV 트랩 &rarr;</h2>
          <p className="text-gray-600 leading-relaxed">
            리비안의 통짜 프레임 수리 지옥, 샤오미 브레이크 파열, 그리고 루시드 OTA 벽돌화 사태 요약.
          </p>
        </Link>
      </div>
    </div>
  );
}
