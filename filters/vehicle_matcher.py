"""Vehicle Brand and Model Extraction Engine.

Identifies vehicle manufacturer and specific EV models from Korean forum text.
Maps them to canonical brands:
- Hyundai (Ioniq 5/6/9, Genesis GV60/GV70/G80 EV, Kona EV, Casper Electric, Porter EV, ST1)
- Kia (EV3/EV6/EV9/EV2/EV4/EV5, Niro EV, Ray EV, Bongo EV, and '이븨/이브이' colloquialisms)
- Tesla (Model 3/Y/S/X/Cybertruck/Model 2, and '삼식이', '모델와이', '사트' colloquialisms)
- BYD (Atto 3, Seal, Dolphin, Sealion, Han, Tang, and '비야디/씰' colloquialisms)
- Other (Torres EVX, Mercedes EQE/EQS, BMW i4/iX3/iX, Polestar 2/4, Taycan, ID.4, Lyriq, etc.)

Features robust ambiguity resolution when multiple vehicle names or generic terms appear,
leveraging ownership anchor proximity, comparative roles, and structural positioning.

Authoritative reference:
/Users/a7890/src/my-e-car/.agents/orchestrator_daily_monitor/PROJECT.md § Interface Contracts
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Pattern, Tuple


# Canonical brand definitions
BRAND_HYUNDAI = "Hyundai"
BRAND_KIA = "Kia"
BRAND_TESLA = "Tesla"
BRAND_BYD = "BYD"
BRAND_OTHER = "Other"

VALID_BRANDS = [BRAND_HYUNDAI, BRAND_KIA, BRAND_TESLA, BRAND_BYD, BRAND_OTHER]

MAX_MATCHER_TITLE_LEN = 1_000
MAX_MATCHER_CONTENT_LEN = 30_000

# Comprehensive Hangul particle and ending lookahead
PARTICLE_LOOKAHEAD = (
    r"(?=[은는이가을를의에과와도만로랑처조마나한께보부까]|으로|보다|부터|까지|처럼|조차|마저|한테|"
    r"입|했|하|인|임|일|(?:\s|$)|[^a-zA-Z0-9가-힣]|$)"
)

# Proximity pattern for ownership, defect experience, or topic affirmation
OWNERSHIP_AFFINITY_PATTERN = re.compile(
    r"^(?:\s*(?:차주|오너|출고|인도|계약|구매|구입|기변|내\s*차|타는데|타고|타보니|타봤|몰고|탑승|주행기?|시승|결함|고장|화재|리콜|수리|센터|서비스|방전|먹통|단차|누수)"
    r"|[은는이가을를의에과와도만로랑처조마나한께보부까]|으로|보다|부터|까지|처럼|조차|마저|한테|입|했|하|인|임|일)",
    re.IGNORECASE,
)


# Model rule specification: (Regex pattern, Canonical Model Name, Canonical Brand)
MODEL_RULES: List[Tuple[Pattern[str], str, str]] = [
    # -----------------------------------------------------------------
    # Hyundai EV Models & Electrified Genesis
    # -----------------------------------------------------------------
    (re.compile(r"(아이오닉\s*5\s*N|ioniq\s*5\s*n)", re.IGNORECASE), "아이오닉5 N", BRAND_HYUNDAI),
    (re.compile(r"(아이오닉\s*5|ioniq\s*5)", re.IGNORECASE), "아이오닉5", BRAND_HYUNDAI),
    (re.compile(r"(아이오닉\s*6\s*N|ioniq\s*6\s*n)", re.IGNORECASE), "아이오닉6 N", BRAND_HYUNDAI),
    (re.compile(r"(아이오닉\s*6|ioniq\s*6)", re.IGNORECASE), "아이오닉6", BRAND_HYUNDAI),
    (re.compile(r"(아이오닉\s*메기|조선\s*메기)", re.IGNORECASE), "아이오닉6", BRAND_HYUNDAI),
    (re.compile(r"(아이오닉\s*9|ioniq\s*9)", re.IGNORECASE), "아이오닉9", BRAND_HYUNDAI),
    (re.compile(r"(아이오닉\s*7|ioniq\s*7)", re.IGNORECASE), "아이오닉7", BRAND_HYUNDAI),
    (re.compile(r"(아이오닉\s*(?:일렉트릭|ev|전기차)?|ioniq(?:\s*(?:ev|electric))?)" + PARTICLE_LOOKAHEAD, re.IGNORECASE), "아이오닉", BRAND_HYUNDAI),
    (re.compile(r"(코나\s*(?:일렉트릭|ev|전기차|electric)|kona\s*(?:ev|electric))", re.IGNORECASE), "코나 EV", BRAND_HYUNDAI),
    (re.compile(r"(캐스퍼\s*일렉트릭\s*크로스|casper\s*cross)", re.IGNORECASE), "캐스퍼 일렉트릭", BRAND_HYUNDAI),
    (re.compile(r"(캐스퍼\s*(?:일렉트릭|ev|전기차|electric)|casper\s*(?:electric|ev))", re.IGNORECASE), "캐스퍼 일렉트릭", BRAND_HYUNDAI),
    (re.compile(r"(포터\s*(?:일렉트릭|ev|전기차)|porter\s*ev)", re.IGNORECASE), "포터 EV", BRAND_HYUNDAI),
    (re.compile(r"(?<![a-zA-Z0-9])ST1(?![a-zA-Z0-9])", re.IGNORECASE), "ST1", BRAND_HYUNDAI),
    (re.compile(r"((?:제네시스\s*)?(?:(?:electrified|일렉트리파이드)\s*gv\s*60|gv\s*60))", re.IGNORECASE), "GV60", BRAND_HYUNDAI),
    (re.compile(r"((?:제네시스\s*)?(?:(?:electrified|일렉트리파이드)\s*gv\s*70|gv\s*70\s*(?:전동화|ev|일렉트릭|전기차))|(?<![a-zA-Z0-9])gv\s*70e(?![a-zA-Z0-9]))", re.IGNORECASE), "GV70 EV", BRAND_HYUNDAI),
    (re.compile(r"((?:제네시스\s*)?(?:(?:electrified|일렉트리파이드)\s*g\s*80|g\s*80\s*(?:전동화|ev|일렉트릭|전기차))|(?<![a-zA-Z0-9])g\s*80e(?![a-zA-Z0-9]))", re.IGNORECASE), "G80 EV", BRAND_HYUNDAI),
    (re.compile(r"(제네시스\s*(?:전기차|ev|일렉트릭|전동화)|(?:electrified|일렉트리파이드)\s*제네시스|genesis\s*(?:ev|electric))", re.IGNORECASE), "제네시스 EV", BRAND_HYUNDAI),
    (re.compile(r"(제네시스|genesis)", re.IGNORECASE), "제네시스", BRAND_HYUNDAI),

    # -----------------------------------------------------------------
    # Kia EV Models & Colloquialisms
    # -----------------------------------------------------------------
    (re.compile(r"(?<![a-zA-Z0-9])(ev\s*6\s*gt|이[븨브]이?\s*6\s*gt)(?![a-zA-Z0-9])", re.IGNORECASE), "EV6 GT", BRAND_KIA),
    (re.compile(r"(?<![a-zA-Z0-9])(ev\s*6|이[븨브]이?\s*6)(?![a-zA-Z0-9])", re.IGNORECASE), "EV6", BRAND_KIA),
    (re.compile(r"(?<![a-zA-Z0-9])(ev\s*9\s*gt|이[븨브]이?\s*9\s*gt)(?![a-zA-Z0-9])", re.IGNORECASE), "EV9 GT", BRAND_KIA),
    (re.compile(r"(?<![a-zA-Z0-9])(ev\s*9|이[븨브]이?\s*9)(?![a-zA-Z0-9])", re.IGNORECASE), "EV9", BRAND_KIA),
    (re.compile(r"(?<![a-zA-Z0-9])(ev\s*3|이[븨브]이?\s*3)(?![a-zA-Z0-9])", re.IGNORECASE), "EV3", BRAND_KIA),
    (re.compile(r"(?<![a-zA-Z0-9])(ev\s*2|이[븨브]이?\s*2)(?![a-zA-Z0-9])", re.IGNORECASE), "EV2", BRAND_KIA),
    (re.compile(r"(?<![a-zA-Z0-9])(ev\s*4|이[븨브]이?\s*4)(?![a-zA-Z0-9])", re.IGNORECASE), "EV4", BRAND_KIA),
    (re.compile(r"(?<![a-zA-Z0-9])(ev\s*5|이[븨브]이?\s*5)(?![a-zA-Z0-9])", re.IGNORECASE), "EV5", BRAND_KIA),
    (re.compile(r"(니로\s*(?:일렉트릭|ev|플러스|전기차)|niro\s*ev)", re.IGNORECASE), "니로 EV", BRAND_KIA),
    (re.compile(r"(레이\s*(?:ev|전기차)|ray\s*ev)", re.IGNORECASE), "레이 EV", BRAND_KIA),
    (re.compile(r"(봉고\s*(?:ev|전기차|일렉트릭)|bongo\s*ev)", re.IGNORECASE), "봉고 EV", BRAND_KIA),

    # -----------------------------------------------------------------
    # BMW M3 (Precedes Tesla Model 3 to prevent M3 Competition collision)
    # -----------------------------------------------------------------
    (re.compile(r"(bmw\s*m3|비엠\s*m3|\bm3\s*컴페티션|bmw의\s*m3|비엠더블유\s*m3)", re.IGNORECASE), "BMW M3", BRAND_OTHER),

    # -----------------------------------------------------------------
    # Tesla Models & Colloquialisms
    # -----------------------------------------------------------------
    (re.compile(r"(모델\s*(?:3|쓰리|스리)\s*하이랜드|model\s*3\s*highland|m3\s*(?:highland|하이랜드)|하이랜드|highland)", re.IGNORECASE), "Model 3 Highland", BRAND_TESLA),
    (re.compile(
        r"(모델\s*(?:3|쓰리|스리)|model\s*3|모삼"
        r"|(?:테슬라\s*)?삼식이"
        r"|(?:테슬라\s*)?메기\s*3"
        r"|(?:테슬라\s+)메기"
        r"|(?:테슬라\s*|tesla\s*)m3"
        r"|(?<!bmw\s)(?<!bmw)(?<!비엠\s)(?<!비엠)(?<!비엠더블유\s)(?<!비엠더블유)(?<!sm)(?<!애플\s)(?<!애플)(?<!맥\s)(?<!맥)(?<!mac\s)(?<!mac)"
        r"(?<![a-zA-Z0-9])m3(?=[은는이가을를의에과와도만로랑처조마나한께보부까]|으로|보다|부터|까지|처럼|조차|마저|한테|입|했|하|인|임|일)"
        r"|(?<!bmw\s)(?<!bmw)(?<!비엠\s)(?<!비엠)(?<!비엠더블유\s)(?<!비엠더블유)(?<!sm)(?<!애플\s)(?<!애플)(?<!맥\s)(?<!맥)(?<!mac\s)(?<!mac)"
        r"(?<![a-zA-Z0-9])m3\s*(?:rwd|awd|lwd|lr|p|롱레인지|롱레|스탠다드|스탠|퍼포먼스|퍼포|차주|오너|출고|인도|계약|단차|결함|승차감|전비|충전|배터리)"
        r"|(?<!bmw\s)(?<!bmw)(?<!비엠\s)(?<!비엠)(?<!비엠더블유\s)(?<!비엠더블유)(?<!sm)(?<!애플\s)(?<!애플)(?<!맥\s)(?<!맥)(?<!mac\s)(?<!mac)"
        r"(?<![a-zA-Z0-9])m3(?!\s*(?:맥북|macbook|칩|chip|프로|pro|max|맥스|울트라|ultra|컴페티션|competition))(?=\s|$|[^a-zA-Z0-9가-힣])"
        r")",
        re.IGNORECASE,
    ), "Model 3", BRAND_TESLA),
    (re.compile(r"(모델\s*(?:y|와이)\s*주니퍼|model\s*y\s*juniper|my\s*(?:주니퍼|juniper)|주니퍼|juniper)", re.IGNORECASE), "Model Y Juniper", BRAND_TESLA),
    (re.compile(
        r"(모델\s*(?:y|와이)|model\s*y|모와"
        r"|(?:테슬라\s*|tesla\s*)my"
        r"|\bmy(?=[은는이가을를의에과와도만로랑처조마나한께보부까]|으로|보다|부터|까지|처럼|조차|마저|한테|입|했|하|인|임|일)"
        r"|\bmy\s*(?:rwd|awd|lwd|lr|p|롱레인지|롱레|스탠다드|스탠|퍼포먼스|퍼포|차주|오너|출고|인도|계약|단차|결함|승차감)"
        r")" + PARTICLE_LOOKAHEAD,
        re.IGNORECASE,
    ), "Model Y", BRAND_TESLA),
    (re.compile(
        r"(모델\s*(?:s|에스)|model\s*s|모에스"
        r"|(?:테슬라\s*|tesla\s*)ms"
        r"|(?<!\d\s)(?<!\d)(?<![a-zA-Z0-9])ms(?=[은는이가을를의에과와도만로랑처조마나한께보부까]|으로|보다|부터|까지|처럼|조차|마저|한테|입|했|하|인|임|일)"
        r"|(?<!\d\s)(?<!\d)(?<![a-zA-Z0-9])ms\s*(?:플래드|plaid|롱레인지|롱레|퍼포먼스|차주|오너|출고|인도|계약|단차|결함|승차감)"
        r"|(?<!\d\s)(?<!\d)(?<![a-zA-Z0-9])ms(?!\s*(?:윈도우|windows|오피스|office|팀즈|teams|서피스|surface|소프트웨어|주가|주식|시총|초|sec))(?=\s|$|[^a-zA-Z0-9가-힣])"
        r")",
        re.IGNORECASE,
    ), "Model S", BRAND_TESLA),
    (re.compile(
        r"(모델\s*(?:x|엑스|익스)|model\s*x|모엑스"
        r"|(?:테슬라\s*|tesla\s*)mx"
        r"|(?<![a-zA-Z0-9])mx(?=[은는이가을를의에과와도만로랑처조마나한께보부까]|으로|보다|부터|까지|처럼|조차|마저|한테|입|했|하|인|임|일)"
        r"|(?<![a-zA-Z0-9])mx\s*(?:플래드|plaid|롱레인지|롱레|팔콘윙|falcon|차주|오너|출고|인도|계약|단차|결함|승차감)"
        r"|(?<![a-zA-Z0-9])mx(?!\s*(?:마스터|master|애니웨어|anywhere|버티컬|vertical|키즈|keys|-5|-30))(?=\s|$|[^a-zA-Z0-9가-힣])"
        r")",
        re.IGNORECASE,
    ), "Model X", BRAND_TESLA),
    (re.compile(
        r"(사이버트럭|cybertruck|(?:테슬라\s*)?[사싸]트(?=\s*(?:오너|차주|출고|인도|계약|단차|결함|전기차|주행|승차감|충전|배터리)|" + PARTICLE_LOOKAHEAD + r"))",
        re.IGNORECASE,
    ), "Cybertruck", BRAND_TESLA),
    (re.compile(r"(모델\s*(?:2|투)|model\s*2)" + PARTICLE_LOOKAHEAD, re.IGNORECASE), "Model 2", BRAND_TESLA),

    # -----------------------------------------------------------------
    # BYD Models & Colloquialisms
    # -----------------------------------------------------------------
    (re.compile(r"(아토\s*3|atto\s*3|atto3)", re.IGNORECASE), "Atto 3", BRAND_BYD),
    (re.compile(r"(돌핀|dolphin)", re.IGNORECASE), "돌핀", BRAND_BYD),
    (re.compile(
        r"((?:byd|비야디)\s*(?:의\s*)?(?:신차\s*|전기차\s*|세단\s*)?(?:씰|seal)"
        r"|(?<!도어\s)(?<!도어)(?<!오일\s)(?<!오일)(?<!고무\s)(?<!고무)(?<!웨더스트립\s)(?<!웨더스트립)(?<!유리\s)(?<!유리)(?<!윈도우\s)(?<!윈도우)(?<!트렁크\s)(?<!트렁크)(?<!방수\s)(?<!방수)(?<!엔진\s)(?<!엔진)(?<!모터\s)(?<!모터)(?<!문짝\s)(?<!문짝)(?<!실리콘\s)(?<!실리콘)"
        r"(?:byd\s*)?(?:씰|seal)\s*(?:ev|전기차|세단|오너|차주|출고|시승|인도|사전계약)"
        r")" + PARTICLE_LOOKAHEAD,
        re.IGNORECASE,
    ), "씰", BRAND_BYD),
    (re.compile(r"([시씨]라이언\s*0?7?|sealion\s*0?7?)", re.IGNORECASE), "시라이언", BRAND_BYD),
    (re.compile(r"((?:byd|비야디)\s*(?:한|han))" + PARTICLE_LOOKAHEAD, re.IGNORECASE), "한", BRAND_BYD),
    (re.compile(r"((?:byd|비야디)\s*(?:탕|tang))" + PARTICLE_LOOKAHEAD, re.IGNORECASE), "탕", BRAND_BYD),

    # -----------------------------------------------------------------
    # Other Domestic & Imported Models
    # -----------------------------------------------------------------
    (re.compile(r"(토레스\s*(?:evx|ev|전기차)|torres\s*(?:evx|ev))", re.IGNORECASE), "토레스 EVX", BRAND_OTHER),
    (re.compile(r"(타이칸|taycan)", re.IGNORECASE), "타이칸", BRAND_OTHER),
    (re.compile(r"(폴스타\s*2|polestar\s*2)", re.IGNORECASE), "폴스타 2", BRAND_OTHER),
    (re.compile(r"(폴스타\s*4|polestar\s*4)", re.IGNORECASE), "폴스타 4", BRAND_OTHER),
    (re.compile(r"(폴스타\s*3|polestar\s*3)", re.IGNORECASE), "폴스타 3", BRAND_OTHER),
    (re.compile(r"(폴스타\s*5|polestar\s*5)", re.IGNORECASE), "폴스타 5", BRAND_OTHER),
    (re.compile(r"(폴스타|polestar)" + PARTICLE_LOOKAHEAD, re.IGNORECASE), "폴스타", BRAND_OTHER),
    (re.compile(r"(?:벤츠\s*|mercedes(?:\s*-?\s*benz)?\s*)?(?<![a-zA-Z0-9])(eqe\s*(?:350\+?|53|suv)?)(?![a-zA-Z0-9])", re.IGNORECASE), "EQE", BRAND_OTHER),
    (re.compile(r"(?:벤츠\s*|mercedes(?:\s*-?\s*benz)?\s*)?(?<![a-zA-Z0-9])(eqs\s*(?:450\+?|580|suv)?)(?![a-zA-Z0-9])", re.IGNORECASE), "EQS", BRAND_OTHER),
    (re.compile(r"(?:벤츠\s*|mercedes(?:\s*-?\s*benz)?\s*)?(?<![a-zA-Z0-9])(eqa|eqb|eqc)(?![a-zA-Z0-9])", re.IGNORECASE), "EQ Series", BRAND_OTHER),
    (re.compile(r"(?:bmw\s*|비엠\s*)?(?<![a-zA-Z0-9])(i4\s*m50|i4)(?![a-zA-Z0-9])", re.IGNORECASE), "BMW i4", BRAND_OTHER),
    (re.compile(r"(?:bmw\s*|비엠\s*)?(?<![a-zA-Z0-9])(ix3)(?![a-zA-Z0-9])", re.IGNORECASE), "BMW iX3", BRAND_OTHER),
    (re.compile(
        r"(?:bmw\s*|비엠\s*)ix(?:\s*(?:40|50|m60|m))?(?![a-zA-Z0-9])"
        r"|(?<![a-zA-Z0-9])ix\s*(?:40|50|m60)(?![a-zA-Z0-9])"
        r"|(?<![a-zA-Z0-9])ix(?=[은는이가을를의에과와도만로랑처조마나한께보부까]|으로|보다|부터|까지|처럼|조차|마저|한테|입|했|하|인|임|일)"
        r"|(?<![a-zA-Z0-9])ix\s*(?:xdrive|오너|차주|출고|인도|시승|계약|단차|결함|전기차|배터리|승차감)",
        re.IGNORECASE,
    ), "BMW iX", BRAND_OTHER),
    (re.compile(r"(?:bmw\s*|비엠\s*)?(?<![a-zA-Z0-9])(i7|i5|ix1|ix2)(?![a-zA-Z0-9])|(?:bmw\s*|비엠\s*)i\s*시리즈", re.IGNORECASE), "BMW i Series", BRAND_OTHER),
    (re.compile(r"(e-tron|이 트론|이트론|q4\s*e-tron)", re.IGNORECASE), "Audi e-tron", BRAND_OTHER),
    (re.compile(r"(볼트\s*(?:ev|euv)|bolt\s*ev)", re.IGNORECASE), "볼트 EV", BRAND_OTHER),
    (re.compile(r"(ex\s*30|c40|xc40\s*recharge)", re.IGNORECASE), "Volvo EV", BRAND_OTHER),
    (re.compile(r"(리비안|rivian|r1t|r1s)", re.IGNORECASE), "Rivian", BRAND_OTHER),
    (re.compile(r"(루시드\s*에어|lucid\s*air|루시드)", re.IGNORECASE), "Lucid Air", BRAND_OTHER),
    (re.compile(r"(샤오미\s*su7|su7)", re.IGNORECASE), "샤오미 SU7", BRAND_OTHER),
    (re.compile(r"(폭스바겐\s*id\s*\.?\s*4|vw\s*id\s*\.?\s*4|(?<![a-zA-Z0-9])id\s*\.?\s*4(?![a-zA-Z0-9]))", re.IGNORECASE), "Volkswagen ID.4", BRAND_OTHER),
    (re.compile(r"(폭스바겐\s*id\s*\.?\s*버즈|vw\s*id\s*\.?\s*buzz|(?<![a-zA-Z0-9])id\s*\.?\s*(?:buzz|버즈)(?![a-zA-Z0-9]))", re.IGNORECASE), "Volkswagen ID.Buzz", BRAND_OTHER),
    (
        re.compile(
            r"(캐딜락\s*리릭|cadillac\s*lyriq|"
            r"(?<![a-zA-Z0-9가-힣])리릭" + PARTICLE_LOOKAHEAD + r"|"
            r"(?<![a-zA-Z0-9])lyriq" + PARTICLE_LOOKAHEAD + r")",
            re.IGNORECASE,
        ),
        "Cadillac Lyriq",
        BRAND_OTHER,
    ),
]


# Brand fallback keywords if model is not detected explicitly
BRAND_KEYWORDS: List[Tuple[Pattern[str], str]] = [
    (re.compile(r"(테슬라|tesla|테슬람|개슬라|개스라|기가상하이|테쪽이)", re.IGNORECASE), BRAND_TESLA),
    (re.compile(r"(현대자동차|현대차|현대\s*전기차|현기차|현기충|흉기차|흉기|블루핸즈|e-gmp|이피트|아이오닉|ioniq)", re.IGNORECASE), BRAND_HYUNDAI),
    (re.compile(r"(제네시스|genesis|(?:(?:electrified|일렉트리파이드)\s*)?(?:gv\s*60|gv\s*70|g\s*80))", re.IGNORECASE), BRAND_HYUNDAI),
    (re.compile(r"(기아차|기아\s*전기차|기아|오토큐|기아\s*(?:ev|이[븨브]이?))", re.IGNORECASE), BRAND_KIA),
    (re.compile(r"(byd|비야디|짱깨차|짱차|중국\s*전기차)", re.IGNORECASE), BRAND_BYD),
    (re.compile(r"(벤츠|mercedes|mercedes-benz|bmw|비엠더블유|비엠|아우디|audi|포르쉐|porsche|폴스타|polestar|볼보|volvo|쉐보레|chevrolet|chevy|캐딜락|cadillac|폭스바겐|volkswagen|vw|리비안|rivian|루시드|lucid|샤오미|xiaomi|쌍용|쌍용차|kgm|케이지엠|kg\s*모빌리티)", re.IGNORECASE), BRAND_OTHER),
]


class _MatchCandidate:
    __slots__ = ("start", "end", "model_name", "brand", "rule_idx", "score")

    def __init__(self, start: int, end: int, model_name: str, brand: str, rule_idx: int) -> None:
        self.start = start
        self.end = end
        self.model_name = model_name
        self.brand = brand
        self.rule_idx = rule_idx
        self.score = 0.0


def _find_and_resolve_candidates(text: str) -> Optional[Tuple[str, str]]:
    """Scan text against MODEL_RULES and resolve ambiguities using contextual affinity and position."""
    if not text:
        return None

    raw_candidates: List[_MatchCandidate] = []
    for idx, (pattern, model_name, brand) in enumerate(MODEL_RULES):
        for m in pattern.finditer(text):
            raw_candidates.append(_MatchCandidate(m.start(), m.end(), model_name, brand, idx))

    if not raw_candidates:
        return None

    # Filter out subsumed spans (e.g., '아이오닉5' strictly inside '아이오닉5 N')
    surviving: List[_MatchCandidate] = []
    for c in raw_candidates:
        is_subsumed = False
        for other in raw_candidates:
            if other is c:
                continue
            if other.start <= c.start and other.end >= c.end and (other.end - other.start) > (c.end - c.start):
                is_subsumed = True
                break
        if not is_subsumed:
            surviving.append(c)

    if not surviving:
        surviving = raw_candidates

    # If only one distinct model candidate, return immediately
    if len(surviving) == 1:
        return surviving[0].brand, surviving[0].model_name

    # Multiple candidates: score based on ownership affinity, defect affinity, and leftmost position
    for c in surviving:
        c.score = 100.0 - (c.start * 0.5)
        trailing = text[c.end:c.end + 25]
        if OWNERSHIP_AFFINITY_PATTERN.search(trailing):
            c.score += 80.0

        leading = text[max(0, c.start - 15):c.start]
        if any(anchor in leading for anchor in ("내 ", "내차", "우리 ", "타던 ", "보유")):
            c.score += 50.0

    # Highest score first, then earliest start position, then rule definition index
    surviving.sort(key=lambda x: (-x.score, x.start, x.rule_idx))
    winner = surviving[0]
    return winner.brand, winner.model_name


def extract_vehicle_info(title: str, content: str = "") -> Tuple[str, str]:
    """Extract vehicle brand and model from post title and content.

    Priority:
    1. Direct model regex match from title (highest confidence, with contextual disambiguation)
    2. Direct model regex match from content (with contextual disambiguation)
    3. Brand keyword match with default model
    4. Fallback to ("Other", "전기차")

    Returns:
        (vehicle_brand, vehicle_model)
    """
    title_str = str(title or "").strip()[:MAX_MATCHER_TITLE_LEN]
    content_str = str(content or "").strip()[:MAX_MATCHER_CONTENT_LEN]

    # 1. Search in title first for high-confidence model match
    if title_str:
        res = _find_and_resolve_candidates(title_str)
        if res:
            return res

    # 2. Search in content for model match
    if content_str:
        res = _find_and_resolve_candidates(content_str)
        if res:
            return res

    combined_text = f"{title_str} {content_str}".strip()

    # 3. Model not found, search for brand keywords
    for pattern, brand in BRAND_KEYWORDS:
        if pattern.search(title_str) or pattern.search(combined_text):
            default_model = {
                BRAND_HYUNDAI: "현대 전기차",
                BRAND_KIA: "기아 전기차",
                BRAND_TESLA: "테슬라",
                BRAND_BYD: "BYD 전기차",
                BRAND_OTHER: "기타 전기차",
            }.get(brand, "전기차")
            return brand, default_model

    # 4. Fallback
    return BRAND_OTHER, "전기차"


class VehicleMatcher:
    """Convenience class wrapper around extract_vehicle_info."""

    @staticmethod
    def match(title: str, content: str = "") -> Tuple[str, str]:
        return extract_vehicle_info(title, content)

    @staticmethod
    def extract_vehicle_info(title: str, content: str = "") -> Tuple[str, str]:
        return extract_vehicle_info(title, content)
