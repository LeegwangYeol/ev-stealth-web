"""Contextual Defect Classification Engine for Korean EV Community Data.

Implements the multi-stage filter and scoring pipelines:
- Stage 1: Noise & Exclusion Filter (Journalistic, Stock spam, Pure flame wars via SpamFilter)
- Stage 2: Ownership Anchor & Operational Symptom Verification
- Stage 3: Negation, Concessive Scoping, and Sarcasm Resolution
- Stage 4: Defect Actionability Gate & 5-Pillar Taxonomy Classification

Scoring engines:
- Sentiment Polarity P in [-1.0, 1.0]
- Normalized Defect Negativity N_score in [0.0, 1.0]
- 5-Dimensional Defect Severity Index (DSI) in [0.0, 10.0]

Authoritative reference:
- /Users/a7890/src/my-e-car/.agents/spec_miner_nlp_workflow/specifications.md § 2.2 - § 2.4
- /Users/a7890/src/my-e-car/.agents/orchestrator_daily_monitor/PROJECT.md § Interface Contracts
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import unicodedata

from filters.slang_lexicon import (
    CONCESSIVES,
    DIMINISHERS,
    LAUGHING_MARKERS,
    NEGATORS,
    OWNERSHIP_ANCHORS,
    RAW_SLANG_ENTRIES,
    SARCASM_PRAISE_WORDS,
    SLANG_CATALOG,
    STANDARD_INTENSIFIERS,
    SUPER_INTENSIFIERS,
    SYMPTOM_PREDICATES,
    SlangEntry,
    _RE_BOUNDED_ICCU,
    _RE_BOUNDED_V2L,
    _RE_BYD_SEAL,
    _RE_JEONSON,
    _RE_MEGI,
    _RE_RICE_COOKER_APP,
    _RE_TCAM_KO,
    _decode_bytes_safely,
    find_matching_slang,
)
from filters.spam_filter import (
    CATEGORY_KEYWORD_MAP,
    SpamFilter,
    _RE_DEFECT_HAJA,
    evaluate_stage1_noise,
    matches_category_keyword,
)
from filters.vehicle_matcher import extract_vehicle_info
from models.complaint import (
    CANONICAL_CATEGORIES,
    DEFECT_CATEGORY_KO_MAP,
    ComplaintRecord,
    DSIBreakdown,
    RawPost,
    parse_date_str,
)

# High-precision compound defect phrases mapping to canonical taxonomy
COMPOUND_DEFECT_RULES: Dict[str, List[str]] = {
    "BATTERY_CHARGING": [
        "iccu 폭탄", "iccu 터짐", "iccu 고장", "iccu 리콜", "iccu 교체", "iccu 경고등", "iccu",
        "통합충전제어장치", "통합 충전 제어 장치", "통합충전제어기", "통합 충전 제어기",
        "배터리 화재", "배터리 열폭주", "열폭주", "배터리 폭발", "배터리 발화", "배터리 불",
        "배터리 연기", "화재 발생", "불쇼",
        "bms 오작동", "bms 오류", "bms 에러", "bms 경고등", "bms 벽돌", "bms 업데이트",
        "배터리 관리 시스템", "배터리관리시스템", "bms",
        "12v 방전", "12v 배터리 방전", "완속 충전 불량", "급속 충전 중단", "완속 충전 불가",
        "급속 충전 불가", "충전구 안 열림", "v2l 오류", "전원공급장치 점검", "전원공급장치",
        "충전 튕김", "충전 끊김", "절연 저항", "절연 파괴", "냉각수 누수"
    ],
    "DRIVING_POWERTRAIN": [
        # Brake / Deceleration failures (Must override generic '먹통' from software!)
        "브레이크 먹통", "제동 불능", "제동 불가", "스펀지 브레이크", "벽돌 페달",
        "브레이크 밀림", "브레이크 꺼짐", "브레이크 작동안함", "브레이크 안 밟힘", "브레이크 고장",
        "페달 먹통", "회생제동 먹통", "회생제동 불능", "회생제동 풀림", "회생제동 털림",
        "오토홀드 먹통", "오토홀드 오류", "오토홀드 고장", "오토홀드 풀림", "오토홀드 미작동",
        "가속 페달 먹통", "가속 페달 이상", "가속 먹통",
        # Motor / Reducer noise & vibration (Must override generic '소음'/'잡소리' from build quality!)
        "모터 감속기 소음", "감속기 소음", "모터 소음", "감속기 잡소리", "감속기 이음",
        "감속기 쇠소리", "감속기 갈리는", "모터 고주파", "인버터 고주파", "모터 잡소리",
        "모터 진동", "감속기 진동", "모터 감속기", "고래소리", "귀신소리", "구동 모터",
        "감속기 오일", "인버터 소음",
        # Steering & Fishtailing
        "피시테일", "피시테일링", "피쉬테일", "피쉬테일링", "fishtail", "fishtailing",
        "조향 장치 이상", "조향 불능", "조향 먹통", "조향 이상", "조향각",
        "핸들 잠김", "핸들 쏠림", "핸들 털림", "핸들 조향", "mdps 결함", "mdps 이상", "오토스티어 풀림",
        # Powertrain sudden failures
        "동력 상실", "동력상실", "구동력 상실", "급발진", "롤백", "출력 저하",
        "원페달 먹통", "아이페달 풀림", "원페달 풀림"
    ],
    "BUILD_QUALITY": [
        # Electronic door catch failures (Must override generic '먹통' from software!)
        "전자식 도어캐치", "도어캐치", "도어 캐치", "도어캐치 먹통", "도어캐치 실종",
        "외캐치", "오토플러시", "플러시 핸들", "플러시 도어", "팝업 도어", "팝업 핸들",
        "도어 손잡이", "손잡이 먹통", "도어 손잡이 안 나옴", "도어 핸들", "동결 고착",
        # Body / Cabin defects
        "단차", "누수", "워터파크", "풍절음", "웨더스트립", "도장 불량", "유리 단차",
        "트렁크 단차", "도어 단차", "찌걱찌걱", "시트 삐걱"
    ],
    "SOFTWARE_ELECTRONICS": [
        # Infotainment & OTA Blackouts
        "인포테인먼트", "ota 블랙아웃", "계기판 블랙아웃", "화면 블랙아웃", "클러스터 블랙아웃",
        "화면 꺼짐", "디스플레이 먹통", "내비 먹통", "네비 먹통", "클러스터 먹통",
        "ota 벽돌", "업데이트 벽돌", "티캠 먹통", "tcam 먹통", "티캠", "tcam",
        "ccnc", "ccic", "avnt", "헤드업 디스플레이 먹통", "hud 먹통", "어라운드뷰 왜곡",
        "블랙아웃", "dsm 블랙아웃", "dsm 먹통", "dsm", "디지털 사이드미러 먹통", "디지털 사이드미러", "디지털 사이드 미러"
    ],
    "SERVICE_REPAIR_COST": [
        "수리비 폭탄", "전손 처리", "전손", "통교체", "감가상각", "보험료 할증",
        "서비스센터 입고 지연", "부품 수급 지연", "대차 거부", "대차 불가", "하이테크 입고"
    ]
}

# General positive sentiment tokens for praise detection
POSITIVE_LEXICON: Dict[str, float] = {
    "양품": 0.85,
    "만족": 0.80,
    "대만족": 0.95,
    "최고": 0.90,
    "좋다": 0.70,
    "좋네": 0.70,
    "좋음": 0.75,
    "좋습니다": 0.75,
    "좋네요": 0.70,
    "좋아요": 0.70,
    "좋은": 0.65,
    "신세계": 0.90,
    "조용": 0.60,
    "조용하고": 0.60,
    "부드럽": 0.65,
    "편하": 0.65,
    "편리": 0.75,
    "쾌적": 0.80,
    "꿀기능": 0.80,
    "개꿀": 0.80,
    "추천": 0.75,
    "강추": 0.90,
    "극찬": 0.90,
    "훌륭": 0.85,
    "완벽": 0.90,
    "이쁘": 0.60,
    "예쁘": 0.60,
    "이쁨": 0.60,
}

# General negative sentiment tokens beyond slang
NEGATIVE_LEXICON: Dict[str, float] = {
    "고장": -0.80,
    "결함": -0.85,
    "불량": -0.80,
    "위험": -0.85,
    "사고": -0.90,
    "불안": -0.75,
    "짜증": -0.70,
    "열받": -0.80,
    "빡침": -0.85,
    "답답": -0.65,
    "스트레스": -0.75,
    "후회": -0.80,
    "실망": -0.75,
    "최악": -0.95,
    "문제": -0.60,
    "하자": -0.75,
    "식겁": -0.85,
    "죽는 줄": -0.95,
    "죽을 뻔": -0.98,
    "심함": -0.75,
    "심각": -0.85,
    "개판": -0.85,
    "개뿔": -0.70,
}

# Pre-compiled regular expressions for tokenization, boundary matching and ReDoS avoidance
RE_CLAUSE_SPLIT: re.Pattern[str] = re.compile(r"[,;.\n]+")
RE_TOKENS: re.Pattern[str] = re.compile(r"[\w가-힣]+")
RE_HANGUL: re.Pattern[str] = re.compile(r"[가-힣]")
RE_AS_KEYWORD: re.Pattern[str] = re.compile(r"(?<![a-zA-Z0-9])(?:as|a/s)(?![a-zA-Z0-9])", re.IGNORECASE)
_RE_ATTACHED_EOPDA: re.Pattern[str] = re.compile(
    r"없(?:습니다|네요|어요|었음|었어|었던|었습|더라|는지|는데|지만|군요|이|는|다|고|음|네|어|죠|지)"
)
_RE_GAE_INTENSIFIER: re.Pattern[str] = re.compile(
    r"(?<![가-힣0-9a-zA-Z])개(?!(?:선|인|발|정|시|업|통|최|편|방|념|요|괄|혁|수|월|별|체|입|관|막|장|축|량|조|척|학|화|회|국|근|녕|로|에서|부터|까지|랑|와|과|의|에|도|는|은|를|이|가|\s*$))"
    r"|(?<![가-힣0-9a-zA-Z])개(?=\s|$)"
)
_BOUNDED_COMPOUND_REGEXES: Dict[str, re.Pattern[str]] = {
    "iccu": _RE_BOUNDED_ICCU,
    "bms": re.compile(r"(?<![a-zA-Z0-9])bms(?![a-zA-Z])", re.IGNORECASE),
    "tcam": re.compile(r"(?<![a-zA-Z0-9])tcam(?![a-zA-Z])", re.IGNORECASE),
    "ccnc": re.compile(r"(?<![a-zA-Z0-9])ccnc(?![a-zA-Z0-9])", re.IGNORECASE),
    "ccic": re.compile(r"(?<![a-zA-Z0-9])ccic(?![a-zA-Z0-9])", re.IGNORECASE),
    "avnt": re.compile(r"(?<![a-zA-Z0-9])avnt(?![a-zA-Z0-9])", re.IGNORECASE),
    "dsm": re.compile(r"(?<![a-zA-Z0-9])dsm(?![a-zA-Z0-9])", re.IGNORECASE),
}


def _matches_compound_phrase(phrase: str, text_lower: str) -> bool:
    """Match a compound defect phrase against lowercased text with boundary safety."""
    if phrase == "티캠":
        return _RE_TCAM_KO.search(text_lower) is not None
    if phrase == "전손":
        return _RE_JEONSON.search(text_lower) is not None
    bounded = _BOUNDED_COMPOUND_REGEXES.get(phrase)
    if bounded is not None:
        return bounded.search(text_lower) is not None
    return phrase in text_lower

# Malfunction cues that disambiguate neutral EV features from actual defect complaints
MALFUNCTION_CUES: Tuple[str, ...] = (
    "오류", "차단", "과열", "먹통", "방전", "고장", "안 됨", "안됨", "에러",
    "경고등", "중단", "안 켜", "미작동", "소리 안", "소리도 안", "소리안", "버튼식",
    "불량", "버그", "안 나", "꺼지", "꺼짐", "꺼졌"
)

# Pre-sorted immutable collections for zero-overhead inner loop evaluation
_SORTED_COMPOUND_RULES: Dict[str, Tuple[str, ...]] = {
    cat: tuple(sorted(phrases, key=len, reverse=True))
    for cat, phrases in COMPOUND_DEFECT_RULES.items()
}
_SORTED_NEGATIVE_WORDS: Tuple[str, ...] = tuple(sorted(NEGATIVE_LEXICON.keys(), key=len, reverse=True))
_SORTED_POSITIVE_WORDS: Tuple[str, ...] = tuple(sorted(POSITIVE_LEXICON.keys(), key=len, reverse=True))

_BASE_DEFECT_WORDS: Tuple[str, ...] = (
    "단차", "잡소리", "소음", "누수", "고장", "결함", "불량", "하자", "이음",
    "찌걱찌걱", "흔들림", "떨림", "문제", "이상", "에러"
)
_ALL_DEFECT_TERMS_LIST: List[str] = list(_BASE_DEFECT_WORDS)
for _entry in RAW_SLANG_ENTRIES:
    if _entry.defect_category is not None and _entry.term not in _ALL_DEFECT_TERMS_LIST:
        _ALL_DEFECT_TERMS_LIST.append(_entry.term)

_SINGLE_PART_DEFECT_TERMS: Tuple[str, ...] = tuple(t for t in _ALL_DEFECT_TERMS_LIST if " " not in t)
_MULTI_PART_DEFECT_TERMS: Tuple[Tuple[Tuple[str, ...], str], ...] = tuple(
    (tuple(t.split()), t) for t in _ALL_DEFECT_TERMS_LIST if " " in t
)

MAX_TEXT_LENGTH: int = 50_000

_SARCASM_DEFECT_WORDS: Tuple[str, ...] = (
    "단차", "누수", "워터파크", "불쇼", "화재", "먹통", "벽돌", "고장", "짱개차", "짱깨차"
)
_EXCLUDED_NEGATOR_PATTERNS: Tuple[str, ...] = (
    "안전", "불안", "어처구니없", "어이없", "말도 안", "말도안",
    "납득이 안", "납득안", "안정", "안심", "안내", "안락",
    "대책 없", "대책없", "답이 없", "답없",
    "형편없", "쓸데없", "터무니없", "어림없", "정신없", "부질없", "보잘것없",
    "끊임없", "쉴새없", "수없", "끝없", "한없", "어김없", "가차없",
    "이유없", "원인없", "전조없", "예고없",
)
_SPACED_EOPDA_SUBJECTS: Tuple[str, ...] = (
    "대책", "대책이", "대책도",
    "답", "답이", "답도",
    "어이", "어이가",
    "어처구니", "어처구니가",
    "양심", "양심이",
    "개념", "개념이",
    "상식", "상식이",
    "이유", "이유가", "이유도",
    "원인", "원인이", "원인도",
    "전조", "전조가", "전조도",
    "예고", "예고가", "예고도",
    "경고", "경고가", "경고도",
    "새",
)
_MALFUNCTION_VERBS: Tuple[str, ...] = (
    "되고", "된다", "돼서", "됨", "돼", "되", "됐",
    "열리고", "열려", "열림", "열린다", "열리", "열렸",
    "켜지고", "켜져", "켜짐", "켜진다", "켜지", "켜졌",
    "꺼지고", "꺼져", "꺼짐", "꺼진다", "꺼지", "꺼졌",
    "걸리고", "걸려", "걸림", "걸린다",
    "빠지고", "빠져", "빠짐", "빠진다",
    "먹히고", "먹혀", "먹힘", "먹힌다",
    "나오고", "나와", "나옴", "나온다", "나오", "나왔",
    "돌아가고", "돌아가", "돌아감", "돌아간다",
    "작동하고", "작동해", "작동함", "작동된다", "작동",
    "잡히고", "잡혀", "잡힘", "잡힌다", "잡히",
    "고쳐지고", "고쳐져", "고쳐짐", "고쳐진다", "고쳐",
    "해결되고", "해결돼", "해결됨", "해결된다", "해결",
    "사라지고", "사라져", "사라짐", "사라진다",
    "없어지고", "없어져", "없어짐", "없어진다",
    "풀리고", "풀려", "풀림", "풀린다", "풀리",
    "줄어들고", "줄어들어", "줄어듦", "줄어든다", "줄어",
    "멈추고", "멈춰", "멈춤", "멈춘다",
    "밟히", "밟혀", "밟힘", "밟힌", "밟혔",
    "뽑히", "뽑혀", "뽑힘", "뽑힌",
    "닦이", "닦여", "닦임", "닦인",
    "들어오", "들어와", "들어옴", "들어온", "들어왔",
    "움직이", "움직여", "움직임", "움직인", "움직였",
)
_MULTI_CHAR_NEGATORS: Tuple[str, ...] = tuple(
    neg for neg in NEGATORS if neg not in ("안", "못", "없")
)
_SLANG_TERM_LOWER_PAIRS: Tuple[Tuple[SlangEntry, str, str], ...] = tuple(
    (entry, unicodedata.normalize("NFC", entry.term), unicodedata.normalize("NFC", entry.term).lower())
    for entry in RAW_SLANG_ENTRIES
)


# Pre-compiled regex for stripping invalid characters: null bytes, non-printable control chars,
# zero-width spaces, Trojan Source / Unicode BiDi overrides, unpaired surrogates, BOM, and Unicode non-characters.
RE_INVALID_CHARS: re.Pattern[str] = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200d\u202a-\u202e\u2060\u2066-\u2069\ud800-\udfff\ufeff\ufffe\uffff]"
)
RE_UNICODE_SPACES: re.Pattern[str] = re.compile(r"[\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]")
FULLWIDTH_TRANS: Dict[int, int] = {i: i - 0xFEE0 for i in range(0xFF01, 0xFF5F)}


def sanitize_text(val: Any, max_len: int = MAX_TEXT_LENGTH) -> str:
    """Safely coerces input to str, strips null bytes, control chars, BiDi overrides & surrogates,
    normalizes NFC, and caps length."""
    if val is None or val is False:
        return ""
    if isinstance(val, (bytes, bytearray)):
        val_str = _decode_bytes_safely(val)
    elif isinstance(val, str):
        val_str = val
    else:
        try:
            val_str = str(val)
        except Exception:
            return ""

    if not val_str:
        return ""

    if len(val_str) > max_len:
        val_str = val_str[:max_len]

    val_str = RE_INVALID_CHARS.sub("", val_str)
    val_str = RE_UNICODE_SPACES.sub(" ", val_str)
    val_str = val_str.translate(FULLWIDTH_TRANS)
    val_str = val_str.strip()

    return unicodedata.normalize("NFC", val_str)


def normalize_date(date_val: Any, default: Optional[str] = None) -> str:
    """Safely normalizes any date representation (ISO 8601, Korean format, timestamps) to YYYY-MM-DD."""
    res = parse_date_str(date_val)
    return res if res else (default or "")


class DefectClassifier:
    """4-Stage Contextual Filtering and Defect Classification Engine."""

    def __init__(self, spam_filter: Optional[SpamFilter] = None) -> None:
        self.spam_filter = spam_filter or SpamFilter()
        self.negator_tokens = set(NEGATORS)
        self.super_intensifiers = SUPER_INTENSIFIERS
        self.standard_intensifiers = STANDARD_INTENSIFIERS
        self.diminishers = DIMINISHERS
        self.concessives = set(CONCESSIVES)

    def normalize_date(self, date_val: Any, default: Optional[str] = None) -> str:
        """Instance method to normalize dates."""
        return normalize_date(date_val, default=default)

    # -----------------------------------------------------------------
    # STAGE 1: Noise & Exclusion Filter
    # -----------------------------------------------------------------
    def evaluate_stage1_noise(self, text: Any, url: Any = "") -> Tuple[bool, str]:
        """Delegate Stage 1 noise filtering to SpamFilter with bulletproof null-checks."""
        return self.spam_filter.evaluate_stage1_noise(text, url)

    # -----------------------------------------------------------------
    # STAGE 2: Ownership Anchor & Operational Symptom Verification
    # -----------------------------------------------------------------
    def evaluate_stage2_ownership(self, text: Any) -> Tuple[bool, str]:
        """Verify real ownership anchor and operational symptom predicates.

        Returns:
            (is_authentic_owner, reason)
        """
        text_str = sanitize_text(text)
        if not text_str or len(text_str) <= 1:
            return False, "Missing first-person ownership anchor: empty or single-character text"

        # Foreign language post without Korean text
        if not RE_HANGUL.search(text_str):
            return False, "Missing first-person ownership anchor: foreign language post without verified ownership experience"

        operational_anchors = [
            "시동", "시동 걸", "시동 켰", "시동 켜", "주행 중", "주행하", "주행했",
            "운전 중", "운전하", "운전했", "차를 몰", "몰았", "충전기 꽂", "충전 중", "충전하",
            "회전교차로", "교차로", "갓길", "골목길", "유턴"
        ]
        has_anchor = any(anchor in text_str for anchor in OWNERSHIP_ANCHORS) or any(op in text_str for op in operational_anchors)
        
        text_lower = text_str.lower()
        if "깜빡이" in text_str and not any(mc in text_lower for mc in MALFUNCTION_CUES):
            has_symptom = any(symptom in text_str for symptom in SYMPTOM_PREDICATES if symptom != "깜빡이")
        else:
            has_symptom = any(symptom in text_str for symptom in SYMPTOM_PREDICATES)

        # If text explicitly mentions defect slang or defect nouns, treat symptom as verified
        matched_slang = find_matching_slang(text_str)
        feature_terms = {"v2l", "깜빡이", "웨더스트립"}
        for e in matched_slang:
            if e.defect_category is not None:
                if e.term.lower() in feature_terms:
                    if any(mc in text_lower for mc in MALFUNCTION_CUES):
                        has_symptom = True
                        break
                else:
                    has_symptom = True
                    break

        defect_keywords = [
            "고장", "결함", "오작동", "버그", "불량", "하자", "긁", "안 닦",
            "튕김", "에러", "불통", "누수", "화재", "멈춤", "물이 흥건", "물 고이",
            "물 차", "물 새", "워터파크", "동력 상실", "경고등",
            "소음", "잡소리", "이음", "떨림", "흔들림", "진동", "단차",
            "iccu", "bms", "피시테일", "피쉬테일", "fishtail", "도어캐치", "스펀지 브레이크", "열폭주",
            "꺼지", "꺼짐", "소리도 안"
        ]
        if any(
            (_RE_DEFECT_HAJA.search(text_lower) is not None)
            if dk == "하자"
            else (_matches_compound_phrase(dk, text_lower) if dk in ("iccu", "bms") else (dk in text_lower))
            for dk in defect_keywords
        ):
            has_symptom = True

        # Check for bystander / third-person trolling without genuine owner experience
        bystander_targets = ["흉기충들", "개슬람들", "테슬람들", "짱깨들", "호구들", "흉기충", "개슬람", "테슬람", "짱깨", "호구"]
        bystander_wishes = ["봐야 정신", "정신차리", "멸망", "꼴좋다", "꼴 좋다", "못한 놈", "꼬라지", "멈춰봐야", "터져봐야", "불타봐야", "당해봐야"]
        if any(bt in text_str for bt in bystander_targets) and any(bw in text_str for bw in bystander_wishes):
            return False, "Missing ownership anchor: bystander flame war / trolling without owner experience"

        if not has_anchor:
            return False, "Missing first-person ownership anchor"
        if not has_symptom:
            return False, "Missing operational malfunction symptom"

        return True, "Verified authentic owner experience"

    # -----------------------------------------------------------------
    # STAGE 3: Negation, Concessive Scoping, & Sarcasm Resolution
    # -----------------------------------------------------------------
    def evaluate_stage3_scoping(self, text: Any) -> Dict[str, Any]:
        """Perform token-level negation, concessive clause reweighting, and sarcasm inversion.

        Returns analysis dict with polarity, negation status, sarcasm status.
        """
        text_str = sanitize_text(text)
        if not text_str:
            return {
                "polarity": 0.0,
                "is_sarcastic": False,
                "negated_defects": [],
                "matched_terms": [],
            }

        # Split into sentences or clauses using pre-compiled regex
        clauses = RE_CLAUSE_SPLIT.split(text_str)
        if len(clauses) > 100:
            clauses = clauses[:100]

        is_sarcastic = self._detect_sarcasm(text_str)

        tokens = RE_TOKENS.findall(text_str)
        if len(tokens) > 500:
            tokens = tokens[:500]

        # Check for global praise / negated defects (e.g. "단차 전혀 없고 잡소리도 1도 안 납니다")
        negated_defects = self._detect_negated_defects(tokens, text_str=text_str)

        # If every sarcasm-triggering defect noun in the text was explicitly negated,
        # treat it as genuine owner praise rather than sarcastic inversion.
        if is_sarcastic and negated_defects:
            negated_set = set(negated_defects)
            present_defect_words = [w for w in _SARCASM_DEFECT_WORDS if w in text_str]
            if present_defect_words and all(
                any(w in neg or neg in w for neg in negated_set)
                for w in present_defect_words
            ):
                is_sarcastic = False

        # Polarity calculation with concessive handling
        polarity, matches = self._calculate_polarity(clauses, is_sarcastic, negated_defects)

        return {
            "polarity": polarity,
            "is_sarcastic": is_sarcastic,
            "negated_defects": negated_defects,
            "matched_terms": matches,
        }

    def _detect_sarcasm(self, text: Any) -> bool:
        """Detect sarcastic praise: defect noun + superlative praise + laughing markers."""
        text_str = sanitize_text(text)
        if not text_str:
            return False
        has_defect_word = any(w in text_str for w in _SARCASM_DEFECT_WORDS)
        has_praise_word = any(pw in text_str for pw in SARCASM_PRAISE_WORDS)
        has_laughing = any(lm in text_str for lm in LAUGHING_MARKERS)

        return has_defect_word and has_praise_word and has_laughing

    def _is_negator_in_window(self, window: List[str]) -> bool:
        """Check if any token in the window is a genuine negator, respecting token boundaries and exclusions."""
        for j, w in enumerate(window):
            w_strip = str(w or "").strip()
            if not w_strip:
                continue

            # Explicitly exclude positive/distress words containing negator characters
            if any(p in w_strip for p in _EXCLUDED_NEGATOR_PATTERNS):
                continue

            # Idiom check: '말도 안 됨' / '납득이 안 됨' where '안' follows '말도', '납득이', etc.
            if w_strip == "안":
                if j > 0 and window[j - 1] in ("말도", "말이", "납득이", "납득", "이해가", "이해"):
                    continue
                # Hearsay contrastive: '안 난다더니', '안 들린다더니', '안 보인다더니'
                if j + 1 < len(window) and any(
                    window[j + 1].startswith(p) for p in ("난다더니", "들린다더니", "보인다더니")
                ):
                    continue
                if j + 1 < len(window):
                    if any(window[j + 1].startswith(mv) for mv in _MALFUNCTION_VERBS):
                        continue
                    return True
                continue

            # Rhetorical and hearsay contrastive exclusions: '없기는 개뿔', '없기는커녕', '없다더니', '없다는데'
            if w_strip.startswith(("없기는", "없다더니", "없다는데", "없다지만", "없긴")):
                continue
            if w_strip.startswith("없") and j > 0 and window[j - 1] in _SPACED_EOPDA_SUBJECTS:
                continue
            if w_strip.startswith("없") and j + 1 < len(window) and window[j + 1] in (
                "개뿔", "커녕", "무슨", "개뿔이", "들었는데", "하더니", "해서", "했으나", "봤는데"
            ):
                continue

            # Double-negation / persistent defect: '안 없어지고', '안 없어져요', '없어지지 않고'
            if w_strip.startswith(("없어지", "없어져", "없어졌", "없어진")) or "없어지" in w_strip or "없어졌" in w_strip:
                if j > 0 and window[j - 1] == "안":
                    continue
                if j + 1 < len(window) and any(
                    window[j + 1].startswith(p) for p in ("않", "못", "안")
                ):
                    continue

            # 1. Any inflection of '없다' (standalone or attached, e.g. 없다, 단차없습니다, 결함없는)
            if w_strip.startswith("없") or _RE_ATTACHED_EOPDA.search(w_strip):
                return True

            # Perception verb negation (e.g. 안들림, 안들려, 안들립니다, 안보임, 안보여, 안보입니다, 안느껴짐, 안느껴져, 안남, 안나요, 안납니다)
            if w_strip.startswith("안") and any(w_strip.startswith(p) for p in ("안들", "안보", "안느껴", "안남", "안나")):
                return True

            # 2. Exact match for single-character negator '못'
            if w_strip == "못":
                return True

            # 3. Multi-character negators from NEGATORS
            for neg in _MULTI_CHAR_NEGATORS:
                if neg in w_strip:
                    return True

        return False

    def _detect_negated_defects(self, tokens: List[str], text_str: Optional[str] = None) -> List[str]:
        """Check if defect terms are negated by following negators."""
        if not tokens:
            return []

        if len(tokens) > 500:
            tokens = tokens[:500]

        if text_str is None:
            text_str = " ".join(tokens)
        text_lower = text_str.lower()
        tokens_lower = [t.lower() for t in tokens]

        negated: List[str] = []
        non_negatable_terms = {"깜빡이", "v2l", "dsm", "mcu", "tcam", "hud", "아이오닉", "이븨", "이브이", "모델와이"}
        affirmative_occurrences = (
            "돼서", "됐다", "됨", "터져서", "터짐", "났음", "났다", "생겨서", "생김", "생겼", "심해서", "심함", "터져", "터졌",
            "발생", "발생해", "발생함", "발생했다", "나타나", "나타남", "나타났다", "시작", "시작됨",
            "심하", "심해요", "심한", "개심함", "개판", "난리", "오지", "폭발"
        )

        for dw in _SINGLE_PART_DEFECT_TERMS:
            dw_lower = dw.lower()
            if dw_lower in non_negatable_terms or dw_lower not in text_lower:
                continue
            for i, tok_lower in enumerate(tokens_lower):
                if dw_lower == "하자":
                    if not tok_lower.startswith("하자") or tok_lower.startswith(("하자마자", "하자고", "하자면")):
                        continue
                elif dw_lower == "전손":
                    if _RE_JEONSON.search(tok_lower) is None:
                        continue
                elif dw_lower == "티캠":
                    if _RE_TCAM_KO.search(tok_lower) is None:
                        continue
                elif dw_lower == "이상":
                    if not (dw_lower in tok_lower or tok_lower.startswith(dw_lower)):
                        continue
                    if any(ch.isdigit() for ch in tok_lower) or tok_lower.startswith(("더이상", "그이상", "이이상")):
                        continue
                    if i > 0 and (
                        tokens_lower[i - 1] in ("더", "그", "이")
                        or any(ch.isdigit() for ch in tokens_lower[i - 1])
                    ):
                        continue
                elif not (dw_lower in tok_lower or tok_lower.startswith(dw_lower)):
                    continue

                after_slice = tokens[i + 1:min(len(tokens), i + 4)]
                if any(any(t.startswith(aff) for aff in affirmative_occurrences) for t in after_slice):
                    continue
                window_end = min(len(tokens), i + 5)
                window = tokens[i:window_end]
                if self._is_negator_in_window(window):
                    negated.append(dw)
                    break

        for parts, dw in _MULTI_PART_DEFECT_TERMS:
            dw_lower = dw.lower()
            parts_lower = tuple(p.lower() for p in parts)
            if dw_lower in non_negatable_terms or parts_lower[0] not in text_lower:
                continue
            m = len(parts_lower)
            for i in range(len(tokens_lower) - m + 1):
                if (tokens_lower[i] == parts_lower[0] or parts_lower[0] in tokens_lower[i]) and all(
                    tokens_lower[i + k].startswith(parts_lower[k]) or parts_lower[k] in tokens_lower[i + k]
                    for k in range(1, m)
                ):
                    after_slice = tokens[i + m:min(len(tokens), i + m + 4)]
                    if any(any(t.startswith(aff) for aff in affirmative_occurrences) for t in after_slice):
                        continue
                    window_end = min(len(tokens), i + m + 5)
                    window = tokens[i:window_end]
                    if self._is_negator_in_window(window):
                        negated.append(dw)
                        break

        return list(set(negated))

    @staticmethod
    def _is_positive_negated_in_clause(pos_word: str, clause_tokens: List[str]) -> bool:
        """Return True if a positive lexicon term is locally negated (e.g. '훌륭하지 않다', '안 좋다')."""
        if not clause_tokens:
            return False
        for idx, tok in enumerate(clause_tokens):
            if pos_word not in tok:
                continue
            if idx > 0 and clause_tokens[idx - 1] in ("안", "못"):
                return True
            if tok.endswith(("안함", "못함", "안됨", "아님")):
                return True
            for nxt in clause_tokens[idx + 1:idx + 3]:
                if nxt in ("안", "못", "아님") or nxt.startswith(("않", "못", "아니")):
                    return True
        return False

    def _calculate_polarity(
        self,
        clauses: List[str],
        is_sarcastic: bool,
        negated_defects: List[str],
    ) -> Tuple[float, List[str]]:
        """Calculate weighted polarity across clauses."""
        if is_sarcastic:
            return -0.95, ["sarcasm_inversion"]

        total_score = 0.0
        total_weight = 0.0
        matched_terms: List[str] = []

        # Split clauses at mid-clause concessive connectives when trailing text exists
        expanded_clauses: List[str] = []
        sorted_concs = sorted(self.concessives, key=len, reverse=True)
        for raw_c in clauses:
            c = str(raw_c or "").strip()
            if not c:
                continue
            while c:
                if len(expanded_clauses) >= 200:
                    break
                split_done = False
                for conc in sorted_concs:
                    idx = c.find(conc)
                    if idx > 0:
                        end_idx = idx + len(conc)
                        tail = c[end_idx:].strip()
                        if tail:
                            expanded_clauses.append(c[:end_idx].strip())
                            c = tail
                            split_done = True
                            break
                if not split_done:
                    expanded_clauses.append(c)
                    break
            if len(expanded_clauses) >= 200:
                break

        is_post_concessive = False

        for clause in expanded_clauses:
            clause = clause.strip()
            if not clause:
                continue

            starts_with_conc = any(clause.startswith(conc) for conc in self.concessives)
            has_conc = starts_with_conc or any(conc in clause for conc in self.concessives)
            if starts_with_conc:
                is_post_concessive = True

            clause_multiplier = 1.5 if is_post_concessive else 0.5
            clause_lower = clause.lower()
            clause_tokens: Optional[List[str]] = None
            clause_intensifier: Optional[float] = None

            for slang_entry, slang_nfc, slang_lower in _SLANG_TERM_LOWER_PAIRS:
                term = slang_entry.term
                if term == "씰":
                    if "씰링" in clause or not _RE_BYD_SEAL.search(clause):
                        continue
                elif term == "밥솥":
                    if _RE_RICE_COOKER_APP.search(clause) and not any(
                        w in clause for w in ("소리", "취사소리", "이음", "고주파", "모터", "인버터", "잡소리")
                    ):
                        continue
                    if slang_lower not in clause_lower:
                        continue
                elif term == "전손":
                    if not _RE_JEONSON.search(clause):
                        continue
                elif term == "티캠":
                    if not _RE_TCAM_KO.search(clause):
                        continue
                elif term == "ICCU":
                    if not _RE_BOUNDED_ICCU.search(clause):
                        continue
                elif term == "V2L":
                    if not any(mc in clause_lower for mc in MALFUNCTION_CUES):
                        continue
                    if not _RE_BOUNDED_V2L.search(clause):
                        continue
                elif term == "메기":
                    if not _RE_MEGI.search(clause):
                        continue
                else:
                    if term.lower() in ("깜빡이", "웨더스트립"):
                        if not any(mc in clause_lower for mc in MALFUNCTION_CUES):
                            continue
                    if slang_lower not in clause_lower:
                        continue

                is_term_negated = any(dw in term or term in dw for dw in negated_defects)
                if is_term_negated:
                    term_polarity = -slang_entry.default_polarity * 0.85
                else:
                    term_polarity = slang_entry.default_polarity

                if clause_intensifier is None:
                    clause_intensifier = self._get_intensifier_multiplier(clause)
                weight = slang_entry.severity_weight * clause_multiplier * clause_intensifier
                total_score += term_polarity * weight
                total_weight += weight
                matched_terms.append(term)

            matched_clause_negs: List[str] = []
            for neg_word in _SORTED_NEGATIVE_WORDS:
                if neg_word in clause and not any(neg_word in already for already in matched_clause_negs):
                    matched_clause_negs.append(neg_word)
                    base_val = NEGATIVE_LEXICON[neg_word]
                    if any(dw in neg_word or neg_word in dw for dw in negated_defects):
                        term_polarity = 0.70
                    else:
                        term_polarity = base_val
                    if clause_intensifier is None:
                        clause_intensifier = self._get_intensifier_multiplier(clause)
                    weight = 2.5 * clause_multiplier * clause_intensifier
                    total_score += term_polarity * weight
                    total_weight += weight
                    matched_terms.append(neg_word)

            matched_clause_pos: List[str] = []
            for pos_word in _SORTED_POSITIVE_WORDS:
                if pos_word in clause and not any(pos_word in already for already in matched_clause_pos):
                    matched_clause_pos.append(pos_word)
                    base_val = POSITIVE_LEXICON[pos_word]
                    if clause_tokens is None:
                        clause_tokens = RE_TOKENS.findall(clause)
                    if self._is_positive_negated_in_clause(pos_word, clause_tokens):
                        term_polarity = -base_val * 0.85
                    else:
                        term_polarity = base_val
                    weight = 1.5 * clause_multiplier
                    total_score += term_polarity * weight
                    total_weight += weight
                    matched_terms.append(pos_word)

            if has_conc and not is_post_concessive:
                is_post_concessive = True

        if total_weight == 0.0:
            if negated_defects:
                return 0.70, [f"negated_{d}" for d in negated_defects]
            return -0.55, matched_terms

        final_polarity = total_score / total_weight
        clamped_polarity = max(-1.0, min(1.0, final_polarity))
        return clamped_polarity, matched_terms

    def _get_intensifier_multiplier(self, clause: str) -> float:
        """Find the strongest intensifier or diminisher in the clause."""
        best_super = 0.0
        for term, mult in self.super_intensifiers.items():
            if not term:
                continue
            if term == "개":
                if _RE_GAE_INTENSIFIER.search(clause):
                    best_super = max(best_super, mult)
            elif term in clause:
                best_super = max(best_super, mult)
        if best_super > 0.0:
            return best_super

        best_std = 0.0
        for term, mult in self.standard_intensifiers.items():
            if term and term in clause:
                best_std = max(best_std, mult)
        if best_std > 0.0:
            return best_std

        for term, mult in self.diminishers.items():
            if term and term in clause:
                return mult
        return 1.0

    def _filter_actionable_slang(
        self,
        slang_matches: List[SlangEntry],
        text_lower: str,
    ) -> List[SlangEntry]:
        """Exclude neutral feature terms unless accompanied by a malfunction cue."""
        has_malfunction_cue: Optional[bool] = None
        filtered: List[SlangEntry] = []
        for entry in slang_matches:
            if entry.term.lower() in ("v2l", "깜빡이", "웨더스트립"):
                if has_malfunction_cue is None:
                    has_malfunction_cue = any(mc in text_lower for mc in MALFUNCTION_CUES)
                if not has_malfunction_cue:
                    continue
            filtered.append(entry)
        return filtered

    # -----------------------------------------------------------------
    # STAGE 4: Defect Actionability Gate & 5-Pillar Classification
    # -----------------------------------------------------------------
    def classify_defect_category(self, text: Any, slang_matches: Optional[List[SlangEntry]] = None) -> str:
        """Assign one of the 5 canonical categories with high-precision compound rules and priority resolution."""
        text_str = sanitize_text(text)
        if not text_str:
            return "BUILD_QUALITY"

        slang_matches = slang_matches if slang_matches is not None else find_matching_slang(text_str)
        category_scores: Dict[str, float] = {cat: 0.0 for cat in CANONICAL_CATEGORIES}

        text_lower = text_str.lower()
        actionable_slang = self._filter_actionable_slang(slang_matches, text_lower)
        suppress_software_meoktong = False
        suppress_build_noise = False

        # 1. High-precision compound defect rules using pre-sorted phrases
        for cat, phrases in _SORTED_COMPOUND_RULES.items():
            for phrase in phrases:
                if _matches_compound_phrase(phrase, text_lower):
                    category_scores[cat] += 12.0
                    if cat == "DRIVING_POWERTRAIN":
                        if any(term in phrase for term in ("브레이크", "페달", "제동", "조향", "오토홀드", "가속", "동력", "구동")):
                            suppress_software_meoktong = True
                        if any(term in phrase for term in ("감속기", "모터", "인버터")):
                            suppress_build_noise = True
                    elif cat == "BUILD_QUALITY":
                        if any(term in phrase for term in ("도어", "캐치", "손잡이", "외캐치", "플러시")):
                            suppress_software_meoktong = True

        # 2. Slang matches with suppression awareness
        for entry in actionable_slang:
            if not entry.defect_category or entry.defect_category not in category_scores:
                continue
            if entry.term == "먹통" and suppress_software_meoktong:
                continue
            if entry.term in ("잡소리", "소음", "찌걱") and suppress_build_noise:
                continue
            category_scores[entry.defect_category] += entry.severity_weight * 2.5

        # 3. Category keyword map with word boundary and suppression awareness
        for cat, kw_list in CATEGORY_KEYWORD_MAP.items():
            for kw in kw_list:
                if kw == "먹통" and suppress_software_meoktong:
                    continue
                if kw in ("소음", "잡소리") and suppress_build_noise:
                    continue
                if matches_category_keyword(cat, kw, text_lower):
                    category_scores[cat] += 1.0

        # 4. Root Cause Priority Resolution:
        # In EV defect posts, owners frequently describe the secondary repair / dealership experience
        # (e.g. 'ICCU 터져서 사업소 입고하고 수리비 견적 나옴'). When a primary physical failure (score >= 12.0)
        # occurred, the root cause physical defect takes precedence over secondary service complaints.
        # However, if SERVICE_REPAIR_COST has a stronger or compound match while the physical category
        # only has a generic noun mention (e.g. '배터리 팩 하부 긁힘 견적 2500만원 통교체 전손'),
        # SERVICE_REPAIR_COST is legitimately preserved.
        physical_cats = ["BATTERY_CHARGING", "DRIVING_POWERTRAIN", "BUILD_QUALITY", "SOFTWARE_ELECTRONICS"]
        max_physical_score = max(category_scores[c] for c in physical_cats)
        service_score = category_scores["SERVICE_REPAIR_COST"]

        if max_physical_score >= 12.0 and service_score > 0.0:
            category_scores["SERVICE_REPAIR_COST"] = min(service_score, max_physical_score - 1.0)

        # Priority weighting hierarchy in case of close ties:
        # BATTERY_CHARGING / DRIVING_POWERTRAIN (Safety Critical) > SOFTWARE_ELECTRONICS > BUILD_QUALITY > SERVICE_REPAIR_COST
        priority_order = ["BATTERY_CHARGING", "DRIVING_POWERTRAIN", "SOFTWARE_ELECTRONICS", "BUILD_QUALITY", "SERVICE_REPAIR_COST"]
        best_category = max(priority_order, key=lambda c: category_scores[c])
        if category_scores[best_category] > 0.0:
            return best_category

        return "BUILD_QUALITY"

    def calculate_confidence(
        self,
        text: Any,
        category: str,
        slang_matches: Optional[List[SlangEntry]] = None,
        polarity: float = 0.0,
        negated_defects: Optional[List[str]] = None,
    ) -> float:
        """Calculate statistical confidence score [0.0, 1.0] for defect classification and false-positive suppression."""
        text_str = sanitize_text(text)
        if not text_str or len(text_str) <= 1:
            return 0.0

        slang_matches = slang_matches if slang_matches is not None else find_matching_slang(text_str)
        negated_defects = negated_defects or []
        text_lower = text_str.lower()
        actionable_slang = self._filter_actionable_slang(slang_matches, text_lower)

        confidence = 0.0

        # 1. Technical component keyword from category map
        has_comp_kw = any(
            matches_category_keyword(category, kw, text_lower)
            for kw in CATEGORY_KEYWORD_MAP.get(category, [])
        )
        if has_comp_kw:
            confidence += 0.20

        # 2. Defect slang entry for this category
        cat_slang = [e for e in actionable_slang if e.defect_category == category]
        if cat_slang:
            max_sev = max(e.severity_weight for e in cat_slang)
            confidence += 0.25 * (max_sev / 5.0)

        # 3. Operational symptom predicate
        has_symptom = any(sym in text_str for sym in SYMPTOM_PREDICATES)
        if has_symptom:
            confidence += 0.20

        # 4. Ownership anchor
        has_owner = any(anchor in text_str for anchor in OWNERSHIP_ANCHORS) or any(
            op in text_str for op in ("시동", "주행 중", "운전 중", "충전 중", "회전교차로", "교차로", "갓길")
        )
        if has_owner:
            confidence += 0.15

        # 5. High-precision compound defect match
        category_compounds = COMPOUND_DEFECT_RULES.get(category, [])
        if any(_matches_compound_phrase(cp, text_lower) for cp in category_compounds):
            confidence += 0.20

        # False-positive suppression penalties
        if negated_defects:
            confidence -= 0.40
        if polarity > 0.0:
            confidence -= 0.30 * polarity
        if len(text_str) < 25:
            confidence -= 0.15

        return round(max(0.0, min(1.0, confidence)), 4)

    def compute_dsi(
        self,
        text: Any,
        category: str,
        slang_matches: Optional[List[SlangEntry]] = None,
    ) -> Tuple[float, DSIBreakdown]:
        """Calculate 5-Dimensional Defect Severity Index (DSI 0.0 ~ 10.0)."""
        text_str = sanitize_text(text)
        slang_matches = slang_matches if slang_matches is not None else find_matching_slang(text_str)
        actionable_slang = self._filter_actionable_slang(slang_matches, text_str.lower())

        s_safety = max([e.safety_impact for e in actionable_slang] + [0.0])
        s_functional = max([e.functional_impact for e in actionable_slang] + [0.0])
        s_economic = max([e.economic_impact for e in actionable_slang] + [0.0])
        s_social = max([e.social_impact for e in actionable_slang] + [0.0])
        s_convenience = max([e.convenience_impact for e in actionable_slang] + [0.0])

        if category == "BATTERY_CHARGING":
            s_safety = max(s_safety, 7.5)
            s_functional = max(s_functional, 8.0)
            s_convenience = max(s_convenience, 6.0)
        elif category == "DRIVING_POWERTRAIN":
            s_safety = max(s_safety, 8.5)
            s_functional = max(s_functional, 7.5)
            s_convenience = max(s_convenience, 6.0)
        elif category == "BUILD_QUALITY":
            s_convenience = max(s_convenience, 7.5)
            s_functional = max(s_functional, 4.0)
        elif category == "SOFTWARE_ELECTRONICS":
            s_functional = max(s_functional, 7.0)
            s_convenience = max(s_convenience, 6.5)
        elif category == "SERVICE_REPAIR_COST":
            s_economic = max(s_economic, 8.5)
            s_social = max(s_social, 7.0)
            s_convenience = max(s_convenience, 6.5)

        if any(w in text_str for w in ["황천길", "죽을 뻔", "죽는 줄", "식겁", "급발진", "화재", "스펀지 브레이크"]):
            s_safety = max(s_safety, 9.8)
            s_functional = max(s_functional, 9.2)

        if s_safety >= 9.0 or s_functional >= 9.0:
            s_functional = max(s_functional, 9.0)
            s_economic = max(s_economic, 8.5)
            s_social = max(s_social, 8.0)
            s_convenience = max(s_convenience, 8.0)
        elif s_economic >= 8.5:
            s_functional = max(s_functional, 7.5)
            s_social = max(s_social, 8.0)
            s_convenience = max(s_convenience, 7.5)

        s_safety = max(0.0, min(10.0, s_safety))
        s_functional = max(0.0, min(10.0, s_functional))
        s_economic = max(0.0, min(10.0, s_economic))
        s_social = max(0.0, min(10.0, s_social))
        s_convenience = max(0.0, min(10.0, s_convenience))

        dsi_score = (
            0.35 * s_safety
            + 0.25 * s_functional
            + 0.15 * s_economic
            + 0.15 * s_social
            + 0.10 * s_convenience
        )

        clamped_dsi = round(max(0.0, min(10.0, dsi_score)), 2)
        breakdown = DSIBreakdown(
            safety=round(s_safety, 2),
            functional=round(s_functional, 2),
            economic=round(s_economic, 2),
            social=round(s_social, 2),
            convenience=round(s_convenience, 2),
        )
        return clamped_dsi, breakdown

    # -----------------------------------------------------------------
    # Primary Pipeline Entrypoint
    # -----------------------------------------------------------------
    def process_post(self, post: Union[RawPost, Dict[str, Any], None]) -> ComplaintRecord:
        """Execute full 4-stage filter and return ComplaintRecord."""
        if post is None:
            post = RawPost()
        elif isinstance(post, dict):
            post = RawPost.from_dict(post)
        elif not isinstance(post, RawPost):
            # Arbitrary non-string object (e.g. int, float, list)
            post = RawPost(title="", content=str(post or ""))

        title_str = sanitize_text(post.title, max_len=10_000)
        content_str = sanitize_text(post.content, max_len=50_000)
        combined_text = f"{title_str}\n{content_str}".strip()

        # Handle comments: protect against string splitting into individual characters
        raw_comments = post.comments
        if isinstance(raw_comments, str):
            c_clean = sanitize_text(raw_comments, max_len=10_000)
            safe_comments = [c_clean] if c_clean else []
        elif isinstance(raw_comments, (list, tuple, set)):
            safe_comments = []
            acc_len = len(combined_text)
            for c in raw_comments:
                cleaned = sanitize_text(c, max_len=10_000)
                if cleaned:
                    safe_comments.append(cleaned)
                    acc_len += len(cleaned) + 1
                    if acc_len >= MAX_TEXT_LENGTH:
                        break
        else:
            safe_comments = []

        comments_text = " ".join(safe_comments)
        full_text = f"{combined_text} {comments_text}".strip()
        if len(full_text) > MAX_TEXT_LENGTH:
            full_text = full_text[:MAX_TEXT_LENGTH]

        # Extract vehicle brand and model (bounded input for ReDoS / latency defense)
        vm_content = content_str[:10_000] if len(content_str) > 10_000 else content_str
        brand, model = extract_vehicle_info(title_str, vm_content)

        # Matched slang entries
        slang_matches = find_matching_slang(full_text)
        slang_terms = [e.term for e in slang_matches]

        # STAGE 1: Noise & Exclusion Filter
        is_discarded, s1_reason = self.evaluate_stage1_noise(full_text, post.url)
        if is_discarded:
            return ComplaintRecord(
                id=post.post_id,
                source=post.platform,
                url=post.url,
                title=post.title,
                author=post.author,
                created_at=post.created_at,
                vehicle_brand=brand,
                vehicle_model=model,
                defect_category="BUILD_QUALITY",
                summary="Filtered by Stage 1 Noise & Exclusion",
                verbatim_quote=self._extract_verbatim_quote(post),
                slang_terms_detected=slang_terms,
                sentiment_polarity=0.0,
                negativity_score=0.5,
                severity_index=0.0,
                is_authentic_defect=False,
                filter_reason=s1_reason,
                confidence_score=0.0,
            )

        # STAGE 2: Ownership Anchor Validation
        is_owner, s2_reason = self.evaluate_stage2_ownership(full_text)
        if not is_owner:
            return ComplaintRecord(
                id=post.post_id,
                source=post.platform,
                url=post.url,
                title=post.title,
                author=post.author,
                created_at=post.created_at,
                vehicle_brand=brand,
                vehicle_model=model,
                defect_category="BUILD_QUALITY",
                summary="Filtered by Stage 2 Ownership Verification",
                verbatim_quote=self._extract_verbatim_quote(post),
                slang_terms_detected=slang_terms,
                sentiment_polarity=0.0,
                negativity_score=0.5,
                severity_index=0.0,
                is_authentic_defect=False,
                filter_reason=s2_reason,
                confidence_score=0.0,
            )

        # STAGE 3: Negation, Concessive Scoping, & Sarcasm Resolution
        stage3_res = self.evaluate_stage3_scoping(full_text)
        polarity = stage3_res["polarity"]
        negativity_score = max(0.0, min(1.0, (1.0 - polarity) / 2.0))

        # STAGE 4: Defect Actionability Gate & 5-Pillar Classification
        category = self.classify_defect_category(full_text, slang_matches)
        dsi_score, dsi_breakdown = self.compute_dsi(full_text, category, slang_matches)
        confidence_score = self.calculate_confidence(
            full_text, category, slang_matches, polarity, stage3_res.get("negated_defects", [])
        )

        verbatim_quote = self._extract_verbatim_quote(post)
        qualifies = (polarity <= -0.30 or dsi_score >= 3.5) and len(verbatim_quote) >= 15 and confidence_score >= 0.35

        if polarity >= 0.30:
            qualifies = False
            filter_reason = "Praise or negated defects; positive polarity"
        elif confidence_score < 0.35:
            qualifies = False
            filter_reason = f"Low confidence defect signal: confidence={confidence_score:.2f} (< 0.35)"
        elif not qualifies:
            filter_reason = f"Fails gate: polarity={polarity:.2f}, dsi={dsi_score:.2f}, quote_len={len(verbatim_quote)}"
        else:
            filter_reason = "PASSED: Authentic EV defect complaint"

        summary = self._generate_summary(title_str, brand, model, category, slang_terms)

        return ComplaintRecord(
            id=post.post_id,
            source=post.platform,
            url=post.url,
            title=post.title,
            author=post.author,
            created_at=post.created_at,
            vehicle_brand=brand,
            vehicle_model=model,
            defect_category=category,
            summary=summary,
            verbatim_quote=verbatim_quote,
            slang_terms_detected=slang_terms,
            sentiment_polarity=polarity,
            negativity_score=negativity_score,
            severity_index=dsi_score,
            is_authentic_defect=qualifies,
            dsi_breakdown=dsi_breakdown,
            filter_reason=filter_reason,
            confidence_score=confidence_score,
        )

    def classify(self, post_or_text: Any) -> ComplaintRecord:
        """Alias for process_post allowing direct text, dict, or RawPost with bulletproof type safety."""
        if post_or_text is None:
            return self.process_post(RawPost())
        if isinstance(post_or_text, str):
            raw = RawPost(title="", content=post_or_text)
            return self.process_post(raw)
        if isinstance(post_or_text, RawPost):
            return self.process_post(post_or_text)
        if isinstance(post_or_text, dict):
            return self.process_post(RawPost.from_dict(post_or_text))
        # Non-string scalar, list, or arbitrary object
        return self.process_post(RawPost(title="", content=str(post_or_text or "")))

    def _extract_verbatim_quote(self, post: RawPost) -> str:
        """Extract the most emotional and colloquial verbatim quote from the post."""
        content = sanitize_text(post.content)
        if len(content) >= 15:
            return content
        title = sanitize_text(post.title)
        combined = f"{title} {content}".strip()
        return combined

    def _generate_summary(
        self,
        title: str,
        brand: str,
        model: str,
        category: str,
        slang_terms: List[str],
    ) -> str:
        """Produce an informative technical summary of the complaint."""
        cat_desc = {
            "BATTERY_CHARGING": "배터리 충전 및 전원 시스템 결함",
            "DRIVING_POWERTRAIN": "주행 동력계 및 제동/조향 안전 결함",
            "BUILD_QUALITY": "외장 조립 단차, 누수 및 실내 마감 불량",
            "SOFTWARE_ELECTRONICS": "인포테인먼트/OTA 소프트웨어 및 전장 먹통",
            "SERVICE_REPAIR_COST": "AS 서비스센터 입고 지연 및 과다 수리비/감가",
        }.get(category, "차량 결함")

        slang_str = f" ({', '.join(slang_terms[:3])})" if slang_terms else ""
        return f"[{brand} {model}] {cat_desc}: {title}{slang_str}"


# Backward compatibility alias
ContextualDefectFilter = DefectClassifier

__all__ = [
    "DefectClassifier",
    "ContextualDefectFilter",
    "COMPOUND_DEFECT_RULES",
    "NEGATIVE_LEXICON",
    "POSITIVE_LEXICON",
    "normalize_date",
    "sanitize_text",
    "RE_INVALID_CHARS",
    "RE_CLAUSE_SPLIT",
    "RE_TOKENS",
    "RE_HANGUL",
    "RE_AS_KEYWORD",
]
