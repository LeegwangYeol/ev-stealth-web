"""Spam, Noise & Exclusion Filter for Korean EV Community Scrapers.

Implements Stage 1 of the Defect NLP Pipeline:
- Journalistic News Detection (press releases, editorial reports, news agency wires)
- External news domain shares with minimal personal commentary
- Financial & stock market discussions (equities, earnings, trading)
- Commercial advertisement & promotional spam (gambling, loans, unauthorized solicitations)
- Prospective buyer advice-seeking inquiries vs. authentic defect reports
- Malicious bystander flame wars / trolling curses without technical defect basis

Authoritative specifications:
- /Users/a7890/src/my-e-car/.agents/orchestrator_daily_monitor/PROJECT.md § Interface Contracts
- /Users/a7890/src/my-e-car/.agents/spec_miner_nlp_workflow/specifications.md § 2.2
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple, Union

from filters.slang_lexicon import (
    LAUGHING_MARKERS,
    NEWS_PATTERNS,
    STOCK_TERMS,
    find_matching_slang,
)

# Pre-compiled regular expressions for Journalistic News matching
NEWS_REGEXES: List[re.Pattern[str]] = [
    re.compile(pat, re.IGNORECASE) for pat in NEWS_PATTERNS
]

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

# Commercial spam / illegal advertisement keywords
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
    "소음", "이음", "떨림", "진동"
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
    ) -> None:
        self.news_regexes = list(news_regexes or NEWS_REGEXES)
        self.stock_terms = list(stock_terms or STOCK_TERMS)
        self.commercial_spam_terms = list(commercial_spam_terms or COMMERCIAL_SPAM_KEYWORDS)

    def evaluate_stage1_noise(self, text: Any, url: Any = "") -> Tuple[bool, str]:
        """Check if post is journalistic news, stock trading, commercial spam, or baseless flaming.

        Args:
            text: Text content of the post (title + body + comments). Safely coerced to str.
            url: Post URL or shared link. Safely coerced to str.

        Returns:
            (is_discarded, reason): True if discarded, with descriptive reason string.
        """
        text_str = str(text or "").strip()
        url_str = str(url or "").strip()

        if not text_str:
            return True, "Empty or whitespace-only content"

        # 1. Commercial / Illegal solicitation spam
        for spam_term in self.commercial_spam_terms:
            if spam_term in text_str:
                return True, f"Commercial advertisement spam detected: {spam_term}"

        # 2. Journalistic News Detection
        for pattern in self.news_regexes:
            if pattern.search(text_str):
                return True, f"Journalistic pattern matched: {pattern.pattern}"

        # External news domains with short commentary
        if any(d in url_str for d in NEWS_DOMAINS) and len(text_str) < 50:
            return True, "External news link share with minimal personal text"

        # 3. Financial / Stock Market Discussions
        matched_stock_terms = [term for term in self.stock_terms if term in text_str]
        if len(matched_stock_terms) >= 2:
            return True, f"Financial / stock discussion: {matched_stock_terms}"

        # Check if text mentions ANY technical component or symptom (case-insensitive)
        text_lower = text_str.lower()
        has_component = False
        for cats in CATEGORY_KEYWORD_MAP.values():
            if any(k.lower() in text_lower for k in cats):
                has_component = True
                break

        has_defect_keyword = any(dk in text_lower for dk in DEFECT_QUESTION_KEYWORDS)
        has_defect_slang = any(e.defect_category is not None for e in find_matching_slang(text_str))

        # 4. Prospective Buyer Queries / General Inquiries Filter (~나요?, ~가요?, 살까요, 궁금)
        inquiry_terms = ["살까요", "궁금"]
        if any(term in text_str for term in inquiry_terms):
            if not (has_defect_keyword or has_defect_slang):
                return True, "Prospective buyer inquiry or advice-seeking question rather than defect complaint"

        if any(pat.search(text_str) for pat in INQUIRY_REGEXES):
            # Retain authentic owner defect complaints ending with question markers
            if not (has_defect_keyword or has_defect_slang or has_component):
                return True, "Prospective buyer inquiry or advice-seeking question rather than defect complaint"

        # 5. Pure Brand Flaming / Tribalism without technical basis
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

    def filter_posts(self, posts: Iterable[Any]) -> List[Any]:
        """Filter an iterable of post dicts or objects, retaining only non-spam items."""
        retained: List[Any] = []
        for p in (posts or []):
            if p is None:
                continue
            if isinstance(p, dict):
                title = p.get("title", "")
                content = p.get("content", "")
                url = p.get("url", "")
            else:
                title = getattr(p, "title", "")
                content = getattr(p, "content", "")
                url = getattr(p, "url", "")
            combined = f"{title} {content}".strip()
            if not self.is_spam(combined, url):
                retained.append(p)
        return retained


# Module-level default singleton instance
_default_spam_filter = SpamFilter()


def evaluate_stage1_noise(text: Any, url: Any = "") -> Tuple[bool, str]:
    """Module-level function to evaluate Stage 1 noise."""
    return _default_spam_filter.evaluate_stage1_noise(text, url)


def is_spam(text: Any, url: Any = "") -> bool:
    """Module-level function returning True if post is spam."""
    return _default_spam_filter.is_spam(text, url)
