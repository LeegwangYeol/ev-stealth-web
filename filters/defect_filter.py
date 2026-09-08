"""4-Stage Contextual EV Defect & Korean Slang Classification Engine.

Implements the multi-stage filter and scoring pipelines:
- Stage 1: Noise & Exclusion Filter (Journalistic, Stock spam, Pure flame wars)
- Stage 2: Ownership Anchor & Operational Symptom Verification
- Stage 3: Negation, Concessive Scoping, and Sarcasm Resolution
- Stage 4: Defect Actionability Gate & 5-Pillar Taxonomy Classification

Scoring engines:
- Sentiment Polarity P in [-1.0, 1.0]
- Normalized Defect Negativity N_score in [0.0, 1.0]
- 5-Dimensional Defect Severity Index (DSI) in [0.0, 10.0]

Authoritative reference:
/Users/a7890/src/my-e-car/.agents/spec_miner_nlp_workflow/specifications.md § 2.2 - § 2.4
/Users/a7890/src/my-e-car/.agents/orchestrator_daily_monitor/PROJECT.md § Interface Contracts
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

from filters.slang_lexicon import (
    CONCESSIVES,
    DIMINISHERS,
    LAUGHING_MARKERS,
    NEGATORS,
    NEWS_PATTERNS,
    OWNERSHIP_ANCHORS,
    RAW_SLANG_ENTRIES,
    SARCASM_PRAISE_WORDS,
    SLANG_CATALOG,
    STANDARD_INTENSIFIERS,
    STOCK_TERMS,
    SUPER_INTENSIFIERS,
    SYMPTOM_PREDICATES,
    SlangEntry,
    find_matching_slang,
)
from filters.vehicle_matcher import extract_vehicle_info
from models.complaint import (
    CANONICAL_CATEGORIES,
    ComplaintRecord,
    DSIBreakdown,
    RawPost,
)


# Compile regular expressions for Stage 1 news matching
NEWS_REGEXES: List[re.Pattern[str]] = [re.compile(pat, re.IGNORECASE) for pat in NEWS_PATTERNS]

# General positive sentiment tokens for praise detection
POSITIVE_LEXICON: Dict[str, float] = {
    "양품": 0.85,
    "만족": 0.80,
    "대만족": 0.95,
    "최고": 0.90,
    "좋다": 0.70,
    "좋네": 0.70,
    "좋음": 0.75,
    "조용": 0.60,
    "조용하고": 0.60,
    "부드럽": 0.65,
    "편하": 0.65,
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
}

# Category keyword fallback triggers
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


class ContextualDefectFilter:
    """4-Stage Contextual Filtering and Defect Classification Engine."""

    def __init__(self) -> None:
        self.negator_tokens = set(NEGATORS)
        self.super_intensifiers = SUPER_INTENSIFIERS
        self.standard_intensifiers = STANDARD_INTENSIFIERS
        self.diminishers = DIMINISHERS
        self.concessives = set(CONCESSIVES)

    # -----------------------------------------------------------------
    # STAGE 1: Noise & Exclusion Filter
    # -----------------------------------------------------------------
    def evaluate_stage1_noise(self, text: str, url: str = "") -> Tuple[bool, str]:
        """Check if post is journalistic news, stock trading, or baseless flaming.

        Returns:
            (is_discarded, reason)
        """
        # 1. Journalistic News Detection
        for pattern in NEWS_REGEXES:
            if pattern.search(text):
                return True, f"Journalistic pattern matched: {pattern.pattern}"

        # External news domains with short commentary
        news_domains = ["news.naver.com", "v.daum.net", "autodaily.co.kr", "autoview.co.kr"]
        if any(d in url for d in news_domains) and len(text.strip()) < 50:
            return True, "External news link share with minimal personal text"

        # 2. Financial / Stock Market Discussions
        matched_stock_terms = [term for term in STOCK_TERMS if term in text]
        if len(matched_stock_terms) >= 2:
            return True, f"Financial / stock discussion: {matched_stock_terms}"

        # 3. Prospective Buyer Queries / General Inquiries Filter (~나요?, ~가요?, 살까요, 궁금)
        inquiry_terms = ["살까요", "궁금"]
        inquiry_patterns = [
            r"(?:나요|가요)\s*[\?？]",
            r"(?:나요|가요)\s*$",
        ]
        if any(term in text for term in inquiry_terms) or any(re.search(pat, text) for pat in inquiry_patterns):
            return True, "Prospective buyer inquiry or advice-seeking question rather than defect complaint"

        # 4. Pure Brand Flaming / Tribalism without technical basis
        brand_pejoratives = ["테슬람", "현기충", "흉기차", "흉기", "짱깨차", "짱차", "개슬라", "개스라"]
        has_pejorative = any(p in text for p in brand_pejoratives)
        has_laughter = any(lm in text for lm in LAUGHING_MARKERS)

        # Malicious non-owner flame curses (e.g. 타죽어라, 불타죽어라)
        flame_curses = ["타죽어", "불타죽", "망해라", "개돼지"]
        if has_pejorative and any(fc in text for fc in flame_curses):
            return True, "Malicious non-owner flame curse without authentic defect experience"

        # Check if text mentions ANY technical component or symptom (case-insensitive)
        text_lower = text.lower()
        has_component = False
        for cats in CATEGORY_KEYWORD_MAP.values():
            if any(k.lower() in text_lower for k in cats):
                has_component = True
                break

        if has_pejorative and has_laughter and not has_component:
            return True, "Baseless brand flaming without technical defect basis"

        return False, ""

    # -----------------------------------------------------------------
    # STAGE 2: Ownership Anchor & Operational Symptom Verification
    # -----------------------------------------------------------------
    def evaluate_stage2_ownership(self, text: str) -> Tuple[bool, str]:
        """Verify real ownership anchor and operational symptom predicates.

        Returns:
            (is_authentic_owner, reason)
        """
        has_anchor = any(anchor in text for anchor in OWNERSHIP_ANCHORS)
        has_symptom = any(symptom in text for symptom in SYMPTOM_PREDICATES)

        # If text explicitly mentions defect slang or defect nouns, treat symptom as verified
        matched_slang = find_matching_slang(text)
        if any(e.defect_category is not None for e in matched_slang):
            has_symptom = True

        defect_keywords = ["고장", "결함", "오작동", "버그", "불량", "하자", "긁", "안 닦", "튕김", "에러", "불통"]
        if any(dk in text for dk in defect_keywords):
            has_symptom = True

        # Check for bystander / third-person trolling without genuine owner experience
        bystander_targets = ["흉기충들", "개슬람들", "테슬람들", "짱깨들", "호구들"]
        bystander_wishes = ["봐야 정신", "정신차리", "멸망", "꼴좋다", "꼴 좋다", "못한 놈", "꼬라지", "멈춰봐야", "터져봐야", "불타봐야", "당해봐야"]
        if any(bt in text for bt in bystander_targets) and any(bw in text for bw in bystander_wishes):
            return False, "Missing ownership anchor: bystander flame war / trolling without owner experience"

        if not has_anchor:
            return False, "Missing first-person ownership anchor"
        if not has_symptom:
            return False, "Missing operational malfunction symptom"

        return True, "Verified authentic owner experience"

    # -----------------------------------------------------------------
    # STAGE 3: Negation, Concessive Scoping, & Sarcasm Resolution
    # -----------------------------------------------------------------
    def evaluate_stage3_scoping(self, text: str) -> Dict[str, Any]:
        """Perform token-level negation, concessive clause reweighting, and sarcasm inversion.

        Returns analysis dict with polarity, negation status, sarcasm status.
        """
        # Split into sentences or clauses
        clauses = re.split(r"[,;.\n]+", text)
        is_sarcastic = self._detect_sarcasm(text)

        tokens = re.findall(r"[\w가-힣]+", text)

        # Check for global praise / negated defects (e.g. "단차 전혀 없고 잡소리도 1도 안 납니다")
        negated_defects = self._detect_negated_defects(tokens)

        # Polarity calculation with concessive handling
        polarity, matches = self._calculate_polarity(clauses, is_sarcastic, negated_defects)

        return {
            "polarity": polarity,
            "is_sarcastic": is_sarcastic,
            "negated_defects": negated_defects,
            "matched_terms": matches,
        }

    def _detect_sarcasm(self, text: str) -> bool:
        """Detect sarcastic praise: defect noun + superlative praise + laughing markers."""
        has_defect_word = any(
            w in text for w in ["단차", "누수", "워터파크", "불쇼", "화재", "먹통", "벽돌", "고장", "짱개차", "짱깨차"]
        )
        has_praise_word = any(pw in text for pw in SARCASM_PRAISE_WORDS)
        has_laughing = any(lm in text for lm in LAUGHING_MARKERS)

        return has_defect_word and has_praise_word and has_laughing

    def _is_negator_in_window(self, window: List[str]) -> bool:
        """Check if any token in the window is a genuine negator, respecting token boundaries and exclusions."""
        excluded_patterns = [
            "안전", "불안", "어처구니없", "어이없", "말도 안", "말도안",
            "납득이 안", "납득안", "안정", "안심", "안내", "안락",
            "대책 없", "대책없", "답이 없", "답없"
        ]
        for j, w in enumerate(window):
            w_strip = w.strip()
            if not w_strip:
                continue

            # Explicitly exclude positive/distress words containing negator characters
            if any(p in w_strip for p in excluded_patterns):
                continue

            # Idiom check: '말도 안 됨' / '납득이 안 됨' where '안' follows '말도', '납득이', etc.
            if w_strip == "안":
                if j > 0 and window[j - 1] in ("말도", "납득이", "이해가"):
                    continue
                # Verbs following '안' that describe malfunction symptoms rather than defect negation (e.g. 인식도 안 되고, 시동도 안 걸리고)
                malfunction_verbs = ("되고", "된다", "돼서", "열리고", "열려", "켜지고", "켜져", "걸리고", "걸려", "빠지고", "먹히고")
                if j + 1 < len(window) and any(window[j + 1].startswith(mv) for mv in malfunction_verbs):
                    continue
                return True

            # 1. Single-character negators (못, 없) must require exact token match (token boundary/whitespace)
            if w_strip in ("못", "없"):
                return True

            # 2. Multi-character negators from NEGATORS
            for neg in NEGATORS:
                if neg in ("안", "못", "없"):
                    continue
                if neg in w_strip:
                    return True

        return False

    def _detect_negated_defects(self, tokens: List[str]) -> List[str]:
        """Check if defect terms (base words + all slang entries) are negated by following negators."""
        negated: List[str] = []
        base_defect_words = [
            "단차", "잡소리", "소음", "누수", "고장", "결함", "불량", "하자", "이음",
            "찌걱찌걱", "흔들림", "떨림", "문제", "이상", "에러"
        ]
        # Collect candidate defect terms: base defect words + all RAW_SLANG_ENTRIES terms
        all_defect_terms: List[str] = list(base_defect_words)
        for entry in RAW_SLANG_ENTRIES:
            if entry.term not in all_defect_terms:
                all_defect_terms.append(entry.term)

        affirmative_occurrences = (
            "돼서", "됐다", "됨", "터져서", "터짐", "났음", "났다", "생겨서", "생김", "심해서", "심함", "터져", "터졌"
        )

        for dw in all_defect_terms:
            parts = dw.split()
            if len(parts) == 1:
                # Single-token defect word
                for i, tok in enumerate(tokens):
                    if dw in tok or tok.startswith(dw):
                        # If immediately followed by an affirmative predicate, the defect affirmatively occurred
                        if i + 1 < len(tokens) and any(tokens[i + 1].startswith(aff) for aff in affirmative_occurrences):
                            continue
                        window_end = min(len(tokens), i + 5)
                        window = tokens[i:window_end]
                        if self._is_negator_in_window(window):
                            negated.append(dw)
                            break
            else:
                # Multi-token defect term (e.g. '배터리 광탈', 'ICCU 폭탄')
                m = len(parts)
                for i in range(len(tokens) - m + 1):
                    if (tokens[i] == parts[0] or parts[0] in tokens[i]) and all(
                        tokens[i + k].startswith(parts[k]) or parts[k] in tokens[i + k]
                        for k in range(1, m)
                    ):
                        if i + m < len(tokens) and any(tokens[i + m].startswith(aff) for aff in affirmative_occurrences):
                            continue
                        window_end = min(len(tokens), i + m + 4)
                        window = tokens[i:window_end]
                        if self._is_negator_in_window(window):
                            negated.append(dw)
                            break

        return list(set(negated))

    def _calculate_polarity(
        self,
        clauses: List[str],
        is_sarcastic: bool,
        negated_defects: List[str],
    ) -> Tuple[float, List[str]]:
        """Calculate weighted polarity across clauses."""
        if is_sarcastic:
            # Sarcasm resolution: invert to strongly negative
            return -0.95, ["sarcasm_inversion"]

        total_score = 0.0
        total_weight = 0.0
        matched_terms: List[str] = []

        is_post_concessive = False

        for clause in clauses:
            clause = clause.strip()
            if not clause:
                continue

            # Check for concessive connective (하지만, 그러나, etc.)
            for conc in self.concessives:
                if conc in clause:
                    is_post_concessive = True
                    break

            clause_multiplier = 1.5 if is_post_concessive else 0.5

            tokens = re.findall(r"[\w가-힣]+", clause)

            # Check slang terms
            for slang_entry in RAW_SLANG_ENTRIES:
                if slang_entry.term in clause:
                    # Check if this term was negated in this clause
                    is_term_negated = any(dw in slang_entry.term or slang_entry.term in dw for dw in negated_defects)
                    if is_term_negated:
                        # Invert defect polarity from negative to positive
                        term_polarity = -slang_entry.default_polarity * 0.85
                    else:
                        term_polarity = slang_entry.default_polarity

                    intensifier_mult = self._get_intensifier_multiplier(clause)
                    weight = slang_entry.severity_weight * clause_multiplier * intensifier_mult
                    total_score += term_polarity * weight
                    total_weight += weight
                    matched_terms.append(slang_entry.term)

            # Check negative lexicon (sorted by length descending to prevent sub-matches)
            matched_clause_negs: List[str] = []
            for neg_word in sorted(NEGATIVE_LEXICON.keys(), key=len, reverse=True):
                if neg_word in clause and not any(neg_word in already for already in matched_clause_negs):
                    matched_clause_negs.append(neg_word)
                    base_val = NEGATIVE_LEXICON[neg_word]
                    if any(dw in neg_word or neg_word in dw for dw in negated_defects):
                        term_polarity = 0.70
                    else:
                        term_polarity = base_val
                    intensifier_mult = self._get_intensifier_multiplier(clause)
                    weight = 2.5 * clause_multiplier * intensifier_mult
                    total_score += term_polarity * weight
                    total_weight += weight
                    matched_terms.append(neg_word)

            # Check positive lexicon (sorted by length descending to prevent sub-matches)
            matched_clause_pos: List[str] = []
            for pos_word in sorted(POSITIVE_LEXICON.keys(), key=len, reverse=True):
                if pos_word in clause and not any(pos_word in already for already in matched_clause_pos):
                    matched_clause_pos.append(pos_word)
                    base_val = POSITIVE_LEXICON[pos_word]
                    # Pre-concessive praise gets weakened by clause_multiplier (0.5)
                    weight = 1.5 * clause_multiplier
                    total_score += base_val * weight
                    total_weight += weight
                    matched_terms.append(pos_word)

        if total_weight == 0.0:
            # Fallback if severe technical words were detected
            return -0.55, matched_terms

        final_polarity = total_score / total_weight
        clamped_polarity = max(-1.0, min(1.0, final_polarity))
        return clamped_polarity, matched_terms

    def _get_intensifier_multiplier(self, clause: str) -> float:
        """Find the strongest intensifier or diminisher in the clause."""
        for term, mult in self.super_intensifiers.items():
            if term in clause:
                return mult
        for term, mult in self.standard_intensifiers.items():
            if term in clause:
                return mult
        for term, mult in self.diminishers.items():
            if term in clause:
                return mult
        return 1.0

    # -----------------------------------------------------------------
    # STAGE 4: Defect Actionability Gate & 5-Pillar Classification
    # -----------------------------------------------------------------
    def classify_defect_category(self, text: str, slang_matches: List[SlangEntry]) -> str:
        """Assign one of the 5 canonical categories based on matched terms and keywords."""
        category_scores: Dict[str, float] = {cat: 0.0 for cat in CANONICAL_CATEGORIES}

        # 1. Score from matched slang entries
        for entry in slang_matches:
            if entry.defect_category and entry.defect_category in category_scores:
                category_scores[entry.defect_category] += entry.severity_weight * 2.5

        # 2. Score from domain keywords
        text_lower = text.lower()
        for cat, kw_list in CATEGORY_KEYWORD_MAP.items():
            for kw in kw_list:
                if kw in text_lower:
                    category_scores[cat] += 1.0

        best_category = max(category_scores.items(), key=lambda x: x[1])
        if best_category[1] > 0.0:
            return best_category[0]

        # Default fallback
        return "BUILD_QUALITY"

    def compute_dsi(
        self,
        text: str,
        category: str,
        slang_matches: List[SlangEntry],
    ) -> Tuple[float, DSIBreakdown]:
        """Calculate 5-Dimensional Defect Severity Index (DSI 0.0 ~ 10.0).

        Formula:
        DSI = 0.35 * S_safety + 0.25 * S_functional + 0.15 * S_economic + 0.15 * S_social + 0.10 * S_convenience
        """
        # Collect highest impact values across matched slang entries
        s_safety = max([e.safety_impact for e in slang_matches] + [0.0])
        s_functional = max([e.functional_impact for e in slang_matches] + [0.0])
        s_economic = max([e.economic_impact for e in slang_matches] + [0.0])
        s_social = max([e.social_impact for e in slang_matches] + [0.0])
        s_convenience = max([e.convenience_impact for e in slang_matches] + [0.0])

        # Domain category baseline boosts
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

        # Danger & profanity intensifier adjustments
        if any(w in text for w in ["황천길", "죽을 뻔", "죽는 줄", "식겁", "급발진", "화재", "스펀지 브레이크"]):
            s_safety = max(s_safety, 9.8)
            s_functional = max(s_functional, 9.2)

        # Systemic cascading impacts when failure is critical
        if s_safety >= 9.0 or s_functional >= 9.0:
            s_functional = max(s_functional, 9.0)
            s_economic = max(s_economic, 8.5)
            s_social = max(s_social, 8.0)
            s_convenience = max(s_convenience, 8.0)
        elif s_economic >= 8.5:
            s_functional = max(s_functional, 7.5)
            s_social = max(s_social, 8.0)
            s_convenience = max(s_convenience, 7.5)

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
    def process_post(self, post: RawPost) -> ComplaintRecord:
        """Execute full 4-stage filter and return ComplaintRecord."""
        combined_text = f"{post.title}\n{post.content}".strip()
        comments_text = " ".join(post.comments)
        full_text = f"{combined_text} {comments_text}".strip()

        # Extract vehicle brand and model
        brand, model = extract_vehicle_info(post.title, post.content)

        # Matched slang entries
        slang_matches = find_matching_slang(full_text)
        slang_terms = [e.term for e in slang_matches]

        # -------------------------------------------------------------
        # STAGE 1: Noise & Exclusion Filter
        # -------------------------------------------------------------
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
            )

        # -------------------------------------------------------------
        # STAGE 2: Ownership Anchor Validation
        # -------------------------------------------------------------
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
            )

        # -------------------------------------------------------------
        # STAGE 3: Negation, Concessive Scoping, & Sarcasm Resolution
        # -------------------------------------------------------------
        stage3_res = self.evaluate_stage3_scoping(full_text)
        polarity = stage3_res["polarity"]
        negativity_score = max(0.0, min(1.0, (1.0 - polarity) / 2.0))

        # -------------------------------------------------------------
        # STAGE 4: Defect Actionability Gate & 5-Pillar Classification
        # -------------------------------------------------------------
        category = self.classify_defect_category(full_text, slang_matches)
        dsi_score, dsi_breakdown = self.compute_dsi(full_text, category, slang_matches)

        # Gate Check:
        # 1. Defect Category in 5 canonical taxonomy codes (guaranteed)
        # 2. Polarity P <= -0.30 OR DSI >= 3.5
        # 3. Verbatim quote length >= 15 chars
        verbatim_quote = self._extract_verbatim_quote(post)
        qualifies = (polarity <= -0.30 or dsi_score >= 3.5) and len(verbatim_quote) >= 15

        # Check if the whole defect was negated (e.g. "완전 양품", "단차 전혀 없음")
        if polarity >= 0.30:
            qualifies = False
            filter_reason = "Praise or negated defects; positive polarity"
        elif not qualifies:
            filter_reason = f"Fails gate: polarity={polarity:.2f}, dsi={dsi_score:.2f}, quote_len={len(verbatim_quote)}"
        else:
            filter_reason = "PASSED: Authentic EV defect complaint"

        summary = self._generate_summary(post.title, brand, model, category, slang_terms)

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
        )

    def _extract_verbatim_quote(self, post: RawPost) -> str:
        """Extract the most emotional and colloquial verbatim quote from the post."""
        content = post.content.strip()
        if len(content) >= 15:
            # Prefer content if detailed
            return content
        combined = f"{post.title} {content}".strip()
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
