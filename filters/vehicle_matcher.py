"""Vehicle Brand and Model Extraction Engine.

Identifies vehicle manufacturer and specific EV models from Korean forum text.
Maps them to canonical brands:
- Hyundai
- Kia
- Tesla
- BYD
- Other

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


# Model rule specification: (Regex pattern, Canonical Model Name, Canonical Brand)
MODEL_RULES: List[Tuple[Pattern[str], str, str]] = [
    # -----------------------------------------------------------------
    # Hyundai EV Models
    # -----------------------------------------------------------------
    (re.compile(r"(아이오닉\s*5\s*N|ioniq\s*5\s*n)", re.IGNORECASE), "아이오닉5 N", BRAND_HYUNDAI),
    (re.compile(r"(아이오닉\s*5|ioniq\s*5)", re.IGNORECASE), "아이오닉5", BRAND_HYUNDAI),
    (re.compile(r"(아이오닉\s*6|ioniq\s*6)", re.IGNORECASE), "아이오닉6", BRAND_HYUNDAI),
    (re.compile(r"(아이오닉\s*9|ioniq\s*9)", re.IGNORECASE), "아이오닉9", BRAND_HYUNDAI),
    (re.compile(r"(코나\s*(일렉트릭|ev|전기차)|kona\s*ev)", re.IGNORECASE), "코나 EV", BRAND_HYUNDAI),
    (re.compile(r"(캐스퍼\s*(일렉트릭|ev|전기차)|casper\s*electric)", re.IGNORECASE), "캐스퍼 일렉트릭", BRAND_HYUNDAI),
    (re.compile(r"(포터\s*(일렉트릭|ev|전기차)|porter\s*ev)", re.IGNORECASE), "포터 EV", BRAND_HYUNDAI),
    (re.compile(r"(?<![a-zA-Z0-9])ST1(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "ST1", BRAND_HYUNDAI),
    (re.compile(r"(gv\s*60|제네시스\s*gv\s*60)", re.IGNORECASE), "GV60", BRAND_HYUNDAI),
    (re.compile(r"(gv\s*70\s*(전동화|ev)|electrified\s*gv\s*70)", re.IGNORECASE), "GV70 EV", BRAND_HYUNDAI),
    (re.compile(r"(g\s*80\s*(전동화|ev)|electrified\s*g\s*80)", re.IGNORECASE), "G80 EV", BRAND_HYUNDAI),

    # -----------------------------------------------------------------
    # Kia EV Models
    # -----------------------------------------------------------------
    (re.compile(r"(?<![a-zA-Z0-9])(ev\s*6\s*gt)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "EV6 GT", BRAND_KIA),
    (re.compile(r"(?<![a-zA-Z0-9])(ev\s*6)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "EV6", BRAND_KIA),
    (re.compile(r"(?<![a-zA-Z0-9])(ev\s*9)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "EV9", BRAND_KIA),
    (re.compile(r"(?<![a-zA-Z0-9])(ev\s*3)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "EV3", BRAND_KIA),
    (re.compile(r"(?<![a-zA-Z0-9])(ev\s*4)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "EV4", BRAND_KIA),
    (re.compile(r"(?<![a-zA-Z0-9])(ev\s*5)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "EV5", BRAND_KIA),
    (re.compile(r"(니로\s*(일렉트릭|ev|플러스|전기차)|niro\s*ev)", re.IGNORECASE), "니로 EV", BRAND_KIA),
    (re.compile(r"(레이\s*(ev|전기차)|ray\s*ev)", re.IGNORECASE), "레이 EV", BRAND_KIA),
    (re.compile(r"(봉고\s*(ev|전기차|일렉트릭)|bongo\s*ev)", re.IGNORECASE), "봉고 EV", BRAND_KIA),

    # -----------------------------------------------------------------
    # Tesla Models
    # -----------------------------------------------------------------
    (re.compile(r"(모델\s*3\s*하이랜드|model\s*3\s*highland|하이랜드|highland)", re.IGNORECASE), "Model 3 Highland", BRAND_TESLA),
    (re.compile(r"(모델\s*3|model\s*3|\bm3\b)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "Model 3", BRAND_TESLA),
    (re.compile(r"(모델\s*y\s*주니퍼|model\s*y\s*juniper|주니퍼|juniper)", re.IGNORECASE), "Model Y Juniper", BRAND_TESLA),
    (re.compile(r"(모델\s*y|model\s*y|\bmy\b)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "Model Y", BRAND_TESLA),
    (re.compile(r"(모델\s*s|model\s*s|\bms\b)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "Model S", BRAND_TESLA),
    (re.compile(r"(모델\s*x|model\s*x|\bmx\b)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "Model X", BRAND_TESLA),
    (re.compile(r"(사이버트럭|cybertruck)", re.IGNORECASE), "Cybertruck", BRAND_TESLA),

    # -----------------------------------------------------------------
    # BYD Models
    # -----------------------------------------------------------------
    (re.compile(r"(아토\s*3|atto\s*3|atto3)", re.IGNORECASE), "Atto 3", BRAND_BYD),
    (re.compile(r"(돌핀|dolphin)", re.IGNORECASE), "돌핀", BRAND_BYD),
    (re.compile(r"(?<![a-zA-Z0-9가-힣])(씰|seal)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "씰", BRAND_BYD),
    (re.compile(r"(시라이언\s*7?|sealion\s*7?)", re.IGNORECASE), "시라이언", BRAND_BYD),
    (re.compile(r"\b(byd\s*한|byd\s*han)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "한", BRAND_BYD),
    (re.compile(r"\b(byd\s*탕|byd\s*tang)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "탕", BRAND_BYD),

    # -----------------------------------------------------------------
    # Other Brands & Models
    # -----------------------------------------------------------------
    (re.compile(r"(타이칸|taycan)", re.IGNORECASE), "타이칸", BRAND_OTHER),
    (re.compile(r"(폴스타\s*2|polestar\s*2)", re.IGNORECASE), "폴스타 2", BRAND_OTHER),
    (re.compile(r"(폴스타\s*4|polestar\s*4)", re.IGNORECASE), "폴스타 4", BRAND_OTHER),
    (re.compile(r"(?<![a-zA-Z0-9])(eqe\s*350\+?|eqe\s*53|eqe)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "EQE", BRAND_OTHER),
    (re.compile(r"(?<![a-zA-Z0-9])(eqs\s*450\+?|eqs\s*580|eqs)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "EQS", BRAND_OTHER),
    (re.compile(r"(?<![a-zA-Z0-9])(eqa|eqb|eqc)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "EQ Series", BRAND_OTHER),
    (re.compile(r"(?<![a-zA-Z0-9])(bmw\s*i4|i4\s*m50|i4)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "BMW i4", BRAND_OTHER),
    (re.compile(r"(?<![a-zA-Z0-9])(bmw\s*ix3|ix3)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "BMW iX3", BRAND_OTHER),
    (re.compile(r"(?<![a-zA-Z0-9])(bmw\s*ix|bmw\s*i7|bmw\s*i5)(?=[은는이가을를의에과와도만로]|으로|[^a-zA-Z0-9가-힣]|$)", re.IGNORECASE), "BMW i Series", BRAND_OTHER),
    (re.compile(r"(e-tron|이 트론|이트론|q4\s*e-tron)", re.IGNORECASE), "Audi e-tron", BRAND_OTHER),
    (re.compile(r"(볼트\s*ev|볼트\s*euv|bolt\s*ev)", re.IGNORECASE), "볼트 EV", BRAND_OTHER),
    (re.compile(r"(ex\s*30|c40|xc40\s*recharge)", re.IGNORECASE), "Volvo EV", BRAND_OTHER),
    (re.compile(r"(리비안|rivian|r1t|r1s)", re.IGNORECASE), "Rivian", BRAND_OTHER),
    (re.compile(r"(루시드\s*에어|lucid\s*air|루시드)", re.IGNORECASE), "Lucid Air", BRAND_OTHER),
    (re.compile(r"(샤오미\s*su7|su7)", re.IGNORECASE), "샤오미 SU7", BRAND_OTHER),
]


# Brand fallback keywords if model is not detected explicitly
BRAND_KEYWORDS: List[Tuple[Pattern[str], str]] = [
    (re.compile(r"(테슬라|tesla|테슬람|개슬라|개스라|기가상하이)", re.IGNORECASE), BRAND_TESLA),
    (re.compile(r"(현대차|현대\s*전기차|현기차|현기충|흉기차|흉기|블루핸즈|e-gmp|이피트)", re.IGNORECASE), BRAND_HYUNDAI),
    (re.compile(r"(기아차|기아\s*전기차|기아|오토큐)", re.IGNORECASE), BRAND_KIA),
    (re.compile(r"(byd|비야디|짱깨차|짱차|중국\s*전기차)", re.IGNORECASE), BRAND_BYD),
    (re.compile(r"(벤츠|bmw|아우디|포르쉐|폴스타|볼보|쉐보레|폭스바겐|리비안|루시드|샤오미)", re.IGNORECASE), BRAND_OTHER),
]


def extract_vehicle_info(title: str, content: str = "") -> Tuple[str, str]:
    """Extract vehicle brand and model from post title and content.

    Priority:
    1. Direct model regex match from title (highest confidence)
    2. Direct model regex match from content
    3. Brand keyword match with default model
    4. Fallback to ("Other", "전기차")

    Returns:
        (vehicle_brand, vehicle_model)
    """
    combined_text = f"{title} {content}"

    # 1. Search in title first for high-confidence model match
    for pattern, model_name, brand in MODEL_RULES:
        if pattern.search(title):
            return brand, model_name

    # 2. Search in content for model match
    for pattern, model_name, brand in MODEL_RULES:
        if pattern.search(combined_text):
            return brand, model_name

    # 3. Model not found, search for brand keywords
    for pattern, brand in BRAND_KEYWORDS:
        if pattern.search(title) or pattern.search(combined_text):
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
