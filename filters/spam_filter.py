"""Spam, Noise & Exclusion Filter for Korean EV Community Scrapers.

Implements Stage 1 of the Defect NLP Pipeline:
- Journalistic News Detection (press releases, editorial reports, news agency wires)
- External news domain shares with minimal personal commentary
- Financial & stock market discussions (equities, earnings, crypto trading, speculation)
- Partisan political & ideological flame wars unrelated to vehicle defects
- Commercial advertisement, promotional broker ads, dealer solicitations, affiliate codes, scam promotions
- Prospective buyer advice-seeking inquiries vs. authentic defect reports
- Malicious bystander flame wars / trolling curses without technical defect basis
- Resilient input validation (None, non-string, null bytes, extreme length truncation)
- Defect & ownership context protection (preventing false positives on repair quotes, dealer complaints)

Authoritative specifications:
- /Users/a7890/src/my-e-car/.agents/orchestrator_daily_monitor/PROJECT.md § Interface Contracts
- /Users/a7890/src/my-e-car/.agents/spec_miner_nlp_workflow/specifications.md § 2.2
"""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from filters.slang_lexicon import (
    LAUGHING_MARKERS,
    NEWS_PATTERNS,
    OWNERSHIP_ANCHORS,
    STOCK_TERMS,
    find_matching_slang,
)

# ---------------------------------------------------------------------------
# Maximum input boundaries (DoS / ReDoS / memory leak defense)
# ---------------------------------------------------------------------------
MAX_TEXT_LENGTH: int = 50_000
MAX_URL_LENGTH: int = 2_048


def sanitize_input(val: Any, max_len: int = MAX_TEXT_LENGTH) -> str:
    """Safely coerces input to str, strips null bytes & control chars, and caps length.

    Prevents ReDoS, memory bloat, database insertion failure, and regex crash.
    """
    if val is None or val is False:
        return ""
    if isinstance(val, (bytes, bytearray)):
        try:
            val_str = val.decode("utf-8", errors="replace")
        except Exception:
            val_str = str(val)
    elif isinstance(val, str):
        val_str = val
    else:
        try:
            val_str = str(val)
        except Exception:
            return ""

    if "\x00" in val_str:
        val_str = val_str.replace("\x00", "")

    val_str = val_str.strip()
    if len(val_str) > max_len:
        val_str = val_str[:max_len]

    return val_str


# Pre-compiled regular expressions for Journalistic News matching
NEWS_REGEXES: List[re.Pattern[str]] = [
    re.compile(pat, re.IGNORECASE) for pat in NEWS_PATTERNS
]

# Pre-compiled journalistic wire agency and reporter markers (cached for high throughput)
JOURNALISTIC_WIRE_REGEXES: Tuple[re.Pattern[str], ...] = (
    re.compile(r"\[(?:속보|단독|기사)\]"),
    re.compile(r"기자\b"),
    re.compile(r"에 따르면"),
    re.compile(r"(?:밝혔다|전했다|보도했다|배포했다)\b"),
    re.compile(r"연합뉴스|뉴시스|뉴스1"),
)

# Pre-compiled inquiry patterns
INQUIRY_REGEXES: List[re.Pattern[str]] = [
    re.compile(r"(?:나요|가요)\s*[\?？]"),
    re.compile(r"(?:나요|가요)\s*$"),
]

# External news domains that indicate news shares
NEWS_DOMAINS: Tuple[str, ...] = (
    "news.naver.com",
    "v.daum.net",
    "autodaily.co.kr",
    "autoview.co.kr",
    "motorgraph.com",
    "yna.co.kr",
    "newsis.com",
    "news1.kr",
)

# Commercial spam / illegal advertisement keywords (retained and expanded for full backward compatibility)
COMMERCIAL_SPAM_KEYWORDS: Tuple[str, ...] = (
    "카톡 상담",
    "카톡 문의",
    "텔레그램",
    "선물옵션",
    "바카라",
    "출장안마",
    "카지노",
    "사설토토",
    "무직자 대출",
    "당일 대출",
    "텔레 문의",
    "라인 아이디",
    # Additional illicit / scam terms
    "홀덤",
    "파워볼",
    "안전놀이터",
    "꽁머니",
    "먹튀검증",
    "토토사이트",
    "슬롯머신",
    "소액결제 현금화",
    "정보이용료 현금화",
    "카드깡",
    "신용카드 현금화",
    "조건만남",
    "애인대행",
    "주식 리딩방",
    "코인 리딩방",
    "원금 보장",
    "수익률 100%",
    "리퍼럴 코드",
    "추천인 코드",
)

# Affiliate / referral codes and links
AFFILIATE_REGEXES: List[re.Pattern[str]] = [
    re.compile(r"(?:리퍼럴|레퍼럴|추천인|초대)\s*(?:코드|링크|아이디|프로모션|주소|입력|혜택)\b", re.IGNORECASE),
    re.compile(r"(?:할인|프로모션|쿠폰)\s*(?:코드|번호)\s*[:：]?\s*[A-Za-z0-9_\-]{4,}", re.IGNORECASE),
    re.compile(r"\b(?:ts\.la|coupa\.ng)/[a-zA-Z0-9_\-]+", re.IGNORECASE),
    re.compile(r"\blink\.coupang\.com\b", re.IGNORECASE),
    re.compile(r"\b(?:referral|affiliate)\s*(?:code|link|id)\b", re.IGNORECASE),
]

# Dealer promotional broker ads / commercial solicitation
DEALER_PROMO_REGEXES: List[re.Pattern[str]] = [
    re.compile(r"(?:신차\s*)?(?:장기\s*렌트|오토\s*리스|리스\s*승계)\s*(?:특가|최저가|즉시출고|프로모션|견적비교|상담문의|비교상담|최저가비교)", re.IGNORECASE),
    re.compile(r"(?:장기\s*렌트|오토\s*리스|리스|렌트)\s*(?:견적|비교|상담|신청|문의)", re.IGNORECASE),
    re.compile(r"(?:최저가|한정특가|초특가)\s*(?:견적|출고|비교|리스|렌트)\s*(?:문의|상담|신청)", re.IGNORECASE),
    re.compile(r"(?:즉시출고|선착순|초특가|한정특가)\s*(?:할인|이벤트|특가|프로모션)", re.IGNORECASE),
    re.compile(r"(?:신차패키지|썬팅|틴팅|블랙박스)\s*(?:특가|최저가|공동구매|공구|시공\s*이벤트|시공\s*문의)", re.IGNORECASE),
    re.compile(r"(?:딜러|영업사원)\s*(?:특별\s*지원|현금\s*지원|페이백|서비스\s*지원|사은품\s*증정)", re.IGNORECASE),
    re.compile(r"(?:무료\s*시승|견적\s*상담)\s*(?:신청|예약)\s*[:：]?\s*(?:https?://|open\.kakao|bit\.ly)", re.IGNORECASE),
]

# Contact solicitation & direct messaging channels
CONTACT_SPAM_REGEXES: List[re.Pattern[str]] = [
    re.compile(r"(?:https?://)?open\.kakao\.com/[a-zA-Z0-9_\-\./]+", re.IGNORECASE),
    re.compile(r"(?:https?://)?pf\.kakao\.com/[a-zA-Z0-9_\-\./]+", re.IGNORECASE),
    re.compile(r"(?:https?://)?t\.me/[a-zA-Z0-9_\-\./]+", re.IGNORECASE),
    re.compile(r"(?:https?://)?(?:bit\.ly|tinyurl\.com|me2\.do)/[a-zA-Z0-9_\-\./]+", re.IGNORECASE),
    re.compile(r"(?:카톡|텔레|라인|톡)\s*(?:아이디|ID|문의|상담|연락|주세요)\s*[:：]?\s*@?[a-zA-Z0-9_]{3,}", re.IGNORECASE),
    re.compile(r"010[-.\s]?\d{4}[-.\s]?\d{4}\s*(?:로\s*)?(?:문의|상담|연락|문자)", re.IGNORECASE),
]

# Scam promotions, illegal gambling & predatory financial services
SCAM_PROMO_REGEXES: List[re.Pattern[str]] = [
    re.compile(r"(?:주식|코인|가상화폐|해외선물|선물거래|재테크)\s*(?:리딩방|무료체험|추천주|단톡방|픽방|VIP방)", re.IGNORECASE),
    re.compile(r"(?:수익률|원금)\s*(?:보장|100%|극대화|폭등|확정|지급)", re.IGNORECASE),
    re.compile(r"(?:무료|VIP)\s*(?:체험|리딩|추천)\s*(?:신청|입장|링크)", re.IGNORECASE),
    re.compile(r"(?:바카라|카지노|슬롯머신|사설토토|토토사이트|홀덤|파워볼|안전놀이터|메이저놀이터|꽁머니|첫충|매충|먹튀검증)", re.IGNORECASE),
    re.compile(r"(?:출장안마|출장마사지|조건만남|애인대행)", re.IGNORECASE),
    re.compile(r"(?:소액결제|정보이용료|카드깡|신용카드|비상금)\s*현금화", re.IGNORECASE),
    re.compile(r"(?:당일|무직자|신불자|저신용자|급전|일수|월변)\s*(?:대출|대납|승인|당일지급)", re.IGNORECASE),
]

# Hard illicit spam patterns (never tolerated, even if technical defect words are present)
HARD_ILLICIT_REGEXES: List[re.Pattern[str]] = (
    AFFILIATE_REGEXES + CONTACT_SPAM_REGEXES + SCAM_PROMO_REGEXES
)
HARD_ILLICIT_REGEX_SET: Set[re.Pattern[str]] = set(HARD_ILLICIT_REGEXES)

# Combined commercial spam regexes
COMMERCIAL_SPAM_REGEXES: List[re.Pattern[str]] = (
    HARD_ILLICIT_REGEXES + DEALER_PROMO_REGEXES
)

# Extended speculative financial terms (equities, crypto, derivative speculation)
FINANCIAL_SPECULATION_TERMS: Tuple[str, ...] = (
    # Equities & Stock Trading
    "주가",
    "나스닥",
    "코스피",
    "코스닥",
    "실적",
    "매수",
    "매도",
    "평단",
    "평단가",
    "테슬라 주식",
    "어닝",
    "어닝쇼크",
    "어닝서프라이즈",
    "실적발표",
    "목표주가",
    "호재",
    "악재",
    "주총",
    "주주",
    "상장",
    "시총",
    "시가총액",
    "공매도",
    "숏스퀴즈",
    "풋옵션",
    "콜옵션",
    "선물거래",
    "선물옵션",
    "유상증자",
    "전환사채",
    "주가전망",
    "주식투자",
    "풀매수",
    "손절매",
    # Crypto & Virtual Assets
    "비트코인",
    "이더리움",
    "가상화폐",
    "알트코인",
    "업비트",
    "바이낸스",
    "빗썸",
    "코인 투자",
    "차트분석",
    "골든크로스",
    "데드크로스",
    "김치프리미엄",
)

# Partisan politics and ideological conflict terms
POLITICAL_TERMS: Tuple[str, ...] = (
    # Politicians
    "윤석열",
    "이재명",
    "한동훈",
    "문재인",
    "조국",
    "김건희",
    # Parties & factions
    "민주당",
    "국민의힘",
    "더불어민주당",
    "개혁신당",
    "여당",
    "야당",
    "진보당",
    "정의당",
    # Ideological & polarizing labels / insults
    "좌파",
    "우파",
    "좌빨",
    "수박",
    "개딸",
    "태극기부대",
    "토착왜구",
    "정치병",
    "친북",
    "종북",
    "친중파",
    "친일파",
    # Elections & political mobilization
    "정권교체",
    "정권심판",
    "정권퇴진",
    "탄핵",
    "총선",
    "대선",
    "국회의원",
)

# Category keywords to protect posts mentioning technical components from false-positive discarding
CATEGORY_KEYWORD_MAP: Dict[str, List[str]] = {
    "BATTERY_CHARGING": [
        "배터리", "충전", "급속", "완속", "bms", "iccu", "12v", "방전", "열폭주",
        "화재", "충전기", "이피트", "슈퍼차저", "soc", "인렛", "주행거리", "전원공급장치", "v2l"
    ],
    "DRIVING_POWERTRAIN": [
        "모터", "감속기", "인버터", "브레이크", "가속", "급발진", "제동", "회생제동",
        "핸들", "조향", "피쉬테일", "팬텀", "유령", "오토홀드", "롤백", "밀림", "등판",
        "거북이", "출력", "동력", "악셀", "페달", "수막", "회생제동 멀미", "고래소리"
    ],
    "BUILD_QUALITY": [
        "단차", "누수", "잡소리", "찌걱", "풍절음", "도장", "조립", "마감", "웨더스트립",
        "도어", "트렁크", "보닛", "유리", "와이퍼", "루프", "시트", "소음"
    ],
    "SOFTWARE_ELECTRONICS": [
        "소프트웨어", "mcu", "내비", "ota", "화면", "디스플레이", "계기판", "블랙아웃",
        "먹통", "tcam", "티캠", "통신", "스마트키", "업데이트", "재부팅", "어라운드뷰", "구독"
    ],
    "SERVICE_REPAIR_COST": [
        "수리비", "견적", "전손", "통교체", "as", "서비스센터", "블루핸즈", "오토큐",
        "하이테크", "감가", "감가상각", "손해", "보험", "보험료", "공동인수", "사업소", "입고", "대차", "부품"
    ],
}

# Defect question keywords that protect authentic defect posts ending with question marks
DEFECT_QUESTION_KEYWORDS: Tuple[str, ...] = (
    "iccu", "퍽", "멈춤", "누수", "화재", "고장", "결함",
    "오작동", "버그", "불량", "하자", "방전", "단차", "잡소리",
    "급발진", "먹통", "블랙아웃", "물 새", "물이 흥건", "물 고이",
    "물 차", "경고등", "시동", "꺼짐", "수리비", "전손", "에러",
    "불통", "워터파크", "피쉬테일", "덜컹", "찌걱", "동력 상실",
    "소음", "이음", "떨림", "진동", "통교체", "이상음", "고주파",
    "이명", "출력 저하", "제동 불량", "페달 먹통"
)

# Brand pejoratives used in flame wars
BRAND_PEJORATIVES: Tuple[str, ...] = (
    "테슬람", "현기충", "흉기차", "흉기", "짱깨차", "짱차", "개슬라", "개스라"
)

# Malicious curses without owner experience
FLAME_CURSES: Tuple[str, ...] = (
    "타죽어", "불타죽", "망해라", "개돼지"
)


class SpamFilter:
    """Robust 1st-stage noise & spam filter engine."""

    def __init__(
        self,
        news_regexes: Optional[Sequence[re.Pattern[str]]] = None,
        stock_terms: Optional[Sequence[str]] = None,
        commercial_spam_terms: Optional[Sequence[str]] = None,
        commercial_spam_regexes: Optional[Sequence[re.Pattern[str]]] = None,
        political_terms: Optional[Sequence[str]] = None,
        ownership_anchors: Optional[Sequence[str]] = None,
    ) -> None:
        self.news_regexes = list(news_regexes or NEWS_REGEXES)
        self.stock_terms = list(stock_terms or STOCK_TERMS)
        self.financial_terms = list(stock_terms or FINANCIAL_SPECULATION_TERMS)
        self.commercial_spam_terms = list(commercial_spam_terms or COMMERCIAL_SPAM_KEYWORDS)
        self.commercial_spam_regexes = list(commercial_spam_regexes or COMMERCIAL_SPAM_REGEXES)
        self.hard_illicit_regex_set = set(HARD_ILLICIT_REGEXES)
        self.political_terms = list(political_terms or POLITICAL_TERMS)
        self.ownership_anchors = list(ownership_anchors or OWNERSHIP_ANCHORS)

    def evaluate_stage1_noise(self, text: Any, url: Any = "") -> Tuple[bool, str]:
        """Check if post is journalistic news, stock trading, commercial spam, politics, or baseless flaming.

        Args:
            text: Text content of the post (title + body + comments). Safely coerced and sanitized.
            url: Post URL or shared link. Safely coerced and sanitized.

        Returns:
            (is_discarded, reason): True if discarded, with descriptive reason string.
        """
        text_str = sanitize_input(text, MAX_TEXT_LENGTH)
        url_str = sanitize_input(url, MAX_URL_LENGTH)

        # 0. Basic Noise, Length, and Emoji/Symbol Checks
        if not text_str:
            return True, "Empty or whitespace-only content"

        if len(text_str) <= 1:
            return True, "Discarded: single-character or insufficient content"

        if not any(c.isalnum() for c in text_str):
            return True, "Discarded: pure emojis or symbols without text"

        # -----------------------------------------------------------------
        # Context extraction: Technical components, defect keywords & slang
        # -----------------------------------------------------------------
        text_lower = text_str.lower()

        has_component = False
        for cats in CATEGORY_KEYWORD_MAP.values():
            if any(k.lower() in text_lower for k in cats):
                has_component = True
                break

        has_defect_keyword = any(dk in text_lower for dk in DEFECT_QUESTION_KEYWORDS)

        try:
            slang_matches = find_matching_slang(text_str)
            has_defect_slang = any(e.defect_category is not None for e in slang_matches)
        except Exception:
            has_defect_slang = False

        has_ownership_anchor = any(anchor in text_str for anchor in self.ownership_anchors)

        has_defect_symptom = has_defect_keyword or has_defect_slang or any(
            w in text_lower for w in (
                "고장", "결함", "누수", "소음", "파손",
                "경고등", "먹통", "단차", "터짐", "멈춤",
                "방전", "화재", "전손", "통교체"
            )
        )

        has_defect_context = has_component or has_defect_symptom
        is_owner_complaint = has_defect_symptom and (
            has_ownership_anchor
            or any(w in text_str for w in ("내 차", "내차", "우리차", "우리 차", "차주", "오너", "인수거부", "서비스센터", "블루핸즈", "오토큐", "하이테크", "사업소", "정비소", "신고", "접수", "민원"))
        )

        # -----------------------------------------------------------------
        # 1. Commercial / Promotional Spam, Solicitations & Affiliate Codes
        # -----------------------------------------------------------------
        for spam_term in self.commercial_spam_terms:
            if spam_term in text_str:
                return True, f"Commercial advertisement spam detected: {spam_term}"

        for pattern in self.commercial_spam_regexes:
            m = pattern.search(text_str) or (pattern.search(url_str) if url_str else None)
            if m:
                matched_expr = m.group(0)
                is_hard_illicit = (pattern in self.hard_illicit_regex_set) or any(
                    regex.search(text_str) or (regex.search(url_str) if url_str else None)
                    for regex in HARD_ILLICIT_REGEXES
                )
                if not is_hard_illicit and is_owner_complaint:
                    # Protect genuine owner complaint from promotional broker regex false positive
                    continue

                return True, f"Commercial advertisement spam detected: {matched_expr}"

        # -----------------------------------------------------------------
        # 2. Foreign Language (Posts lacking Korean Hangul characters)
        # -----------------------------------------------------------------
        if not re.search(r"[\uac00-\ud7a3]", text_str):
            return True, "Foreign language without Korean context"

        # -----------------------------------------------------------------
        # 3. Journalistic News Detection
        # -----------------------------------------------------------------
        if any(d in url_str for d in NEWS_DOMAINS) and len(text_str) < 50:
            return True, "External news link share with minimal personal text"

        for pattern in self.news_regexes:
            if pattern.search(text_str):
                # Protect owner reports that mention reporting/filing to government agencies
                # unless strong journalistic wire markers appear
                if pattern.pattern in (r"국토부", r"국토교통부", r"산업부"):
                    has_journalistic_wire = any(p.search(text_str) for p in JOURNALISTIC_WIRE_REGEXES)
                    if not has_journalistic_wire and (has_ownership_anchor or "신고" in text_str or "접수" in text_str or "민원" in text_str):
                        continue

                return True, f"Journalistic pattern matched: {pattern.pattern}"

        # -----------------------------------------------------------------
        # 4. Financial / Stock Market & Crypto Speculation
        # -----------------------------------------------------------------
        matched_stock_terms = [term for term in self.financial_terms if term in text_str]
        if len(matched_stock_terms) >= 2:
            if is_owner_complaint:
                pure_trading_terms = [
                    t for t in matched_stock_terms
                    if t in ("나스닥", "코스피", "코스닥", "목표주가", "공매도", "숏스퀴즈", "풋옵션", "콜옵션", "선물거래", "비트코인", "이더리움", "업비트", "바이낸스")
                ]
                if len(pure_trading_terms) >= 3:
                    return True, f"Financial / stock discussion: {matched_stock_terms}"
            else:
                return True, f"Financial / stock discussion: {matched_stock_terms}"

        # -----------------------------------------------------------------
        # 5. Unrelated Political Discussions
        # -----------------------------------------------------------------
        matched_political = [term for term in self.political_terms if term in text_str]
        if len(matched_political) >= 2:
            if is_owner_complaint:
                partisan_insults = [
                    t for t in matched_political
                    if t in ("좌빨", "개딸", "토착왜구", "수박", "태극기부대", "정치병", "종북")
                ]
                if len(partisan_insults) >= 2 or len(matched_political) >= 4:
                    return True, f"Unrelated political discussion: {matched_political}"
            else:
                return True, f"Unrelated political discussion: {matched_political}"

        # -----------------------------------------------------------------
        # 6. Prospective Buyer Queries / General Inquiries (~나요?, ~가요?, 살까요, 궁금)
        # -----------------------------------------------------------------
        inquiry_terms = ["살까요", "궁금"]
        if any(term in text_str for term in inquiry_terms):
            if not (has_defect_keyword or has_defect_slang):
                return True, "Prospective buyer inquiry or advice-seeking question rather than defect complaint"

        if any(pat.search(text_str) for pat in INQUIRY_REGEXES):
            # Retain authentic owner defect complaints ending with question markers
            if not (has_defect_keyword or has_defect_slang or has_component):
                return True, "Prospective buyer inquiry or advice-seeking question rather than defect complaint"

        # -----------------------------------------------------------------
        # 7. Pure Brand Flaming / Tribalism without technical defect basis
        # -----------------------------------------------------------------
        has_pejorative = any(p in text_str for p in BRAND_PEJORATIVES)
        has_laughter = any(lm in text_str for lm in LAUGHING_MARKERS)

        if has_pejorative and any(fc in text_str for fc in FLAME_CURSES):
            return True, "Malicious non-owner flame curse without authentic defect experience"

        if has_pejorative and has_laughter and not has_component:
            return True, "Baseless brand flaming without technical defect basis"

        return False, ""

    def is_spam(self, text: Any, url: Any = "") -> bool:
        """Convenience method returning boolean True if text/url is spam or noise."""
        discarded, _ = self.evaluate_stage1_noise(text, url)
        return discarded

    def evaluate(self, text: Any, url: Any = "") -> Tuple[bool, str]:
        """Alias for evaluate_stage1_noise."""
        return self.evaluate_stage1_noise(text, url)

    def filter_posts(self, posts: Any) -> List[Any]:
        """Filter an iterable of post dicts or objects, retaining only non-spam items.

        Handles None, non-iterables, malformed items, and attribute/key access errors safely.
        """
        if posts is None or not isinstance(posts, Iterable) or isinstance(posts, (str, bytes, bytearray)):
            return []

        retained: List[Any] = []
        for p in posts:
            if p is None:
                continue
            try:
                if isinstance(p, dict):
                    title = p.get("title", "")
                    content = p.get("content", "")
                    url = p.get("url", "")
                else:
                    title = getattr(p, "title", "")
                    content = getattr(p, "content", "")
                    url = getattr(p, "url", "")

                combined = f"{title or ''} {content or ''}".strip()
                if not self.is_spam(combined, str(url or "")):
                    retained.append(p)
            except Exception:
                continue
        return retained


# Module-level default singleton instance
_default_spam_filter = SpamFilter()


def evaluate_stage1_noise(text: Any, url: Any = "") -> Tuple[bool, str]:
    """Module-level function to evaluate Stage 1 noise."""
    return _default_spam_filter.evaluate_stage1_noise(text, url)


def is_spam(text: Any, url: Any = "") -> bool:
    """Module-level function returning True if post is spam."""
    return _default_spam_filter.is_spam(text, url)
