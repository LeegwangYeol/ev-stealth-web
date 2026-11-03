"""
sentiment_engine.py - Pure Python 3.14 4-Tier Sentiment Polarity & Defect Severity Index (DSI) Scorer.

Implements:
1. 4-Tier Sentiment Polarity Classifier:
   - POSITIVE: +0.30 ~ +1.00
   - NEUTRAL: -0.29 ~ +0.29
   - NEGATIVE: -0.30 ~ -0.69
   - STRONGLY_NEGATIVE / DEROGATORY: -0.70 ~ -1.00
2. Context Window Modifiers:
   - Intensifiers (Super: x1.8, Standard: x1.4, Diminishers: x0.6)
   - Negators (안, 못, 전혀, 결코 -> inverts sign x -0.85)
   - Concessives (하지만, 그러나 -> previous x0.5, next x1.5)
3. 5-Dimensional Defect Severity Index (DSI: 0.0 - 10.0):
   DSI = 0.35 * S_safety + 0.25 * S_functional + 0.15 * S_economic + 0.15 * S_social + 0.10 * S_convenience

Zero external runtime dependencies. Standard library only.
"""

from dataclasses import dataclass, field
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Ensure project root in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from scripts.domain_tokenizer import DomainTokenizer
except ImportError:
    from domain_tokenizer import DomainTokenizer


@dataclass
class SentimentResult:
    """Structured result from sentiment and DSI analysis."""
    polarity_score: float
    tier_label: str
    dsi_score: float
    dsi_breakdown: Dict[str, float]
    detected_complaints: List[str]
    intensity_multiplier: float
    negation_flag: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "polarity_score": self.polarity_score,
            "tier_label": self.tier_label,
            "dsi_score": self.dsi_score,
            "dsi_breakdown": self.dsi_breakdown,
            "detected_complaints": self.detected_complaints,
            "intensity_multiplier": self.intensity_multiplier,
            "negation_flag": self.negation_flag,
        }


class SentimentEngine:
    """
    Automotive Domain Sentiment & Defect Severity Evaluation Engine.
    Combines rule-based contextual polarity propagation with multi-attribute DSI scoring.
    """

    # Intensifier Lexicon with context multiplier weights
    INTENSIFIERS: Dict[str, float] = {
        # Super intensifiers (Extreme community emotion & rage)
        "존나": 1.9, "개": 1.8, "씹": 1.9, "극악": 2.0, "역대급": 1.8, "핵": 1.8,
        "개빡": 1.9, "노답": 1.8, "미쳤": 1.8, "시발": 1.9, "개판": 1.8, "폭망": 1.8,
        "쓰레기": 1.9, "황천길": 2.0, "최악": 1.9, "절대": 1.6, "완전": 1.5,
        # Standard intensifiers
        "진짜": 1.4, "너무": 1.4, "매우": 1.4, "엄청": 1.4, "상당히": 1.3,
        "대단히": 1.3, "심각": 1.5, "극심": 1.6, "제대로": 1.3, "오지게": 1.5,
        # Diminishers
        "약간": 0.6, "조금": 0.6, "살짝": 0.7, "다소": 0.7, "그나마": 0.6, "그럭저럭": 0.6,
    }

    # Negation Operators
    NEGATORS: Set[str] = {
        "안", "못", "없", "아니", "결코", "전혀", "1도", "하나도", "아님", "없음", "불가", "금지", "제외"
    }

    # Concessive Transition Markers
    CONCESSIVES: Set[str] = {
        "하지만", "그러나", "그렇지만", "반면에", "다만", "그럼에도", "근데", "하지만서도"
    }

    # Domain Polarity Lexicon (-1.0 to +1.0)
    POLARITY_LEXICON: Dict[str, float] = {
        # Strongly Negative / Derogatory (-0.75 ~ -1.0)
        "시한폭탄": -1.0, "움직이는 시한폭탄": -1.0, "화재 테러범": -1.0, "화재테러": -1.0,
        "불쇼": -1.0, "자폭차": -1.0, "황천길": -1.0, "황천길 익스프레스": -1.0,
        "벽돌": -0.95, "벽돌차": -0.95, "벽돌방전": -0.95, "급발진": -1.0,
        "피쉬테일": -0.90, "차체 털림": -0.85, "팬텀 브레이킹": -0.90, "유령 급제동": -0.90,
        "롤백": -0.85, "롤백 덜컹": -0.85, "등판불능": -0.90, "등판불가": -0.90,
        "짱깨차": -0.90, "짱차": -0.85, "짱개차": -0.90, "바퀴달린 알리익스프레스": -0.85,
        "바퀴달린 알리": -0.85, "알리트럭": -0.80, "짱트럭": -0.80, "보조금 털이범": -0.80,
        "지하주차장 입차거부": -0.90, "입차거부": -0.90, "입차금지": -0.90, "중량초과": -0.80,
        "감가폭탄": -0.85, "감가상각 지옥": -0.85, "뻥배터리": -0.90,
        # Multi-Brand Critical Additions
        "ICCU 폭탄": -1.0, "ICCU폭탄": -1.0, "ICCU 터짐": -1.0, "ICCU터짐": -1.0,
        "폭탄 돌리기": -0.90, "파라시스 폭탄": -1.0, "파라시스폭탄": -1.0, "파라시스": -0.75,
        "옥토밸브 사망": -1.0, "옥토밸브사망": -1.0, "얼음방 에디션": -0.95, "얼음방에디션": -0.95,
        "냉동고 타이칸": -0.95, "냉동고타이칸": -0.95, "전손 폭탄": -1.0, "전손폭탄": -1.0,
        "7천만원 전손": -1.0, "7천만원전손": -1.0, "하부 긁힘 2천만 원": -0.95, "배터리 전손": -0.95,
        "스펀지 브레이크": -0.90, "스펀지브레이크": -0.90, "허당 브레이크": -0.90, "허당브레이크": -0.90,
        "벽돌 페달": -0.95, "벽돌페달": -0.95, "볼트 화재": -1.0, "볼트화재": -1.0,
        "정신병 와이퍼": -0.90, "정신병와이퍼": -0.90, "자석 핸들": -0.85, "자석핸들": -0.85,
        "램프 꽂힘": -0.90, "램프꽂힘": -0.90, "티캠 먹통": -0.85, "티캠먹통": -0.85,
        "할증 폭탄": -0.90, "할증폭탄": -0.90,

        # Negative (-0.35 ~ -0.70)
        "굼벵이 충전": -0.70, "반토막 충전": -0.65, "통신 튕김": -0.70, "환경부 튕김": -0.70,
        "세션 튕김": -0.70, "통신 에러": -0.65, "통신 락": -0.65, "충전건 고착": -0.70,
        "물림 현상": -0.65, "12V 저전압 방전": -0.75, "12V방전": -0.75, "단차 누수": -0.70,
        "단차": -0.55, "누수": -0.70, "웨더스트립": -0.55, "워터파크": -0.70,
        "배트맨 타이어": -0.80, "빙판 썰매": -0.75, "스케이트 타이어": -0.75,
        "수막현상": -0.75, "휠스핀": -0.70, "슬립": -0.65, "거북이 모드": -0.75,
        "거북이등": -0.75, "열 쓰로틀링": -0.75, "쓰로틀링": -0.70, "출력 저하": -0.70,
        "3D 어라운드뷰 왜곡": -0.65, "어라운드뷰 왜곡": -0.65, "어안렌즈 굴절": -0.65,
        "프레임 드랍": -0.60, "어지럼증 뷰": -0.60, "고스트 비핑": -0.55,
        "와이퍼 채터링": -0.50, "채터링 소음": -0.50, "디프로스트": -0.60,
        "하부 부식": -0.65, "서브프레임 부식": -0.65, "부품 수급 3개월": -0.75,
        "부품 수급": -0.70, "이중주차 불가": -0.65, "N단 중립주차 불가": -0.65,
        "연석 충돌": -0.75, "갈지자 자율주행": -0.70, "뻥스펙": -0.65,
        "불안": -0.60, "공포": -0.80, "답답": -0.55, "짜증": -0.60, "위험": -0.80,
        "후회": -0.70, "비추": -0.75, "사지마": -0.85, "결함": -0.65, "고장": -0.65,
        # Multi-Brand Negative Additions
        "마른 와이퍼질": -0.70, "마른와이퍼질": -0.70, "휠빵": -0.65, "진흙 반죽": -0.65,
        "진흙반죽": -0.65, "뱀파이어 드레인": -0.70, "뱀파이어드레인": -0.70, "눈꽃 마크": -0.70,
        "눈꽃마크": -0.70, "귀신 소리": -0.65, "귀신소리": -0.65, "슈차 지옥": -0.65,
        "슈차지옥": -0.65, "DC콤보 벽돌": -0.60, "테슬람": -0.70, "뒤유리 걸레짝": -0.75,
        "뒤유리걸레짝": -0.75, "블라인드 에디션": -0.75, "블라인드에디션": -0.75,
        "완속 반토막 패치": -0.75, "완속반토막": -0.70, "꼼수 리콜": -0.75, "블핸 퇴짜": -0.70,
        "블핸퇴짜": -0.70, "하이테크 유배": -0.75, "하이테크유배": -0.75, "원격주차 휠스킨": -0.70,
        "원격주차휠스킨": -0.70, "연석 그라인더": -0.70, "히터 찬바람": -0.75, "히터찬바람": -0.75,
        "전원공급시스템": -0.75, "하이퍼스크린 블랙아웃": -0.80, "CCU 사망": -0.80, "CCU사망": -0.80,
        "골병 승차감": -0.65, "골병승차감": -0.65, "80프로 락": -0.70, "80프로락": -0.70,
        "얼티엄 벽돌": -0.80, "얼티엄벽돌": -0.80, "MCU 블랙아웃": -0.80, "단차 감성": -0.60,

        # Neutral (-0.20 ~ +0.20)
        "스펙": 0.0, "카탈로그": 0.0, "출시": 0.05, "보조금": 0.0, "가격": 0.0,
        "LFP": -0.05, "삼원계": 0.05, "주행거리": 0.0, "공차중량": -0.05, "전폭": -0.05,
        "충전소": 0.0, "고속도로": 0.0, "지하주차장": -0.10, "테스트": 0.0,
        "E-GMP": 0.0, "V2L": 0.10, "800V": 0.10, "오토파일럿": 0.0,

        # Positive (+0.35 ~ +0.90)
        "가성비": 0.60, "만족": 0.75, "우수": 0.75, "최고": 0.85, "훌륭": 0.80,
        "편리": 0.65, "쾌적": 0.70, "넉넉": 0.55, "조용": 0.60, "정숙": 0.65,
        "저렴": 0.50, "추천": 0.70, "합리적": 0.60, "넓음": 0.55, "도움": 0.50
    }

    def __init__(self, tokenizer: Optional[DomainTokenizer] = None):
        self.tokenizer = tokenizer or DomainTokenizer()

    def classify(
        self,
        raw_text: str,
        tokens: Optional[List[Dict[str, Any]]] = None
    ) -> SentimentResult:
        """
        Evaluate 4-tier sentiment polarity and 5-dimension DSI score for given text.
        """
        if tokens is None:
            tokens = self.tokenizer.tokenize(raw_text)

        total_score = 0.0
        score_count = 0
        current_multiplier = 1.0
        negate_flag = False
        concessive_multiplier = 1.0

        detected_complaints: List[str] = []

        # DSI Dimension Max Accumulators (0.0 to 10.0)
        s_safety = 0.0
        s_functional = 0.0
        s_economic = 0.0
        s_social = 0.0
        s_convenience = 0.0

        for i, tok in enumerate(tokens):
            raw = tok["raw"]
            stem = tok["stem"]
            cat = tok.get("category", "")

            # 1. Concessive Transition Check
            if raw in self.CONCESSIVES or stem in self.CONCESSIVES:
                # Downweight preceding clauses, boost subsequent clauses
                total_score *= 0.5
                concessive_multiplier = 1.5
                continue

            # 2. Intensifier Check
            if raw in self.INTENSIFIERS or stem in self.INTENSIFIERS:
                factor = self.INTENSIFIERS.get(raw, self.INTENSIFIERS.get(stem, 1.0))
                current_multiplier = max(current_multiplier, factor)
                continue

            # 3. Negator Check
            if raw in self.NEGATORS or stem in self.NEGATORS:
                negate_flag = True
                continue

            # 4. Sentiment Polarity Lookup
            base_pol = self.POLARITY_LEXICON.get(stem, self.POLARITY_LEXICON.get(raw, None))
            if base_pol is not None:
                effective_score = base_pol * current_multiplier * concessive_multiplier
                if negate_flag:
                    effective_score *= -0.85
                    negate_flag = False

                # Clamp score
                effective_score = max(-1.0, min(1.0, effective_score))
                total_score += effective_score
                score_count += 1
                current_multiplier = 1.0

            # 5. DSI Multi-Dimensional Attribute Scoring
            # Safety Hazard Dimension (35%)
            if (
                any(kw in stem or kw in raw for kw in ["화재", "불쇼", "시한폭탄", "자폭차", "황천길", "급발진", "파라시스폭탄", "볼트화재"])
            ):
                s_safety = max(s_safety, 9.8)
                detected_complaints.append("화재 포비아 및 열폭주 안전 불신")
            elif any(kw in stem or kw in raw for kw in ["옥토밸브", "얼음방", "냉동고타이칸", "히터찬바람"]):
                s_safety = max(s_safety, 9.6)
                detected_complaints.append("혹한기 열관리/히터 고장 및 앞유리 성에 시야 상실")
            elif any(kw in stem or kw in raw for kw in ["ICCU", "전원공급시스템", "통합충전제어장치"]):
                s_safety = max(s_safety, 9.6)
                detected_complaints.append("ICCU 파워모듈 소손 및 고속 주행 셧다운")
            elif any(kw in stem or kw in raw for kw in ["벽돌페달", "스펀지브레이크", "허당브레이크", "브레이크"]):
                s_safety = max(s_safety, 9.4)
                detected_complaints.append("전자식 통합 브레이크 부스트 상실 및 제동 밀림")
            elif any(kw in stem or kw in raw for kw in ["피쉬테일", "수막현상", "배트맨타이어", "스케이트", "빙판"]):
                s_safety = max(s_safety, 9.2)
                detected_complaints.append("빗길 타이어 수막현상 및 회생제동 피쉬테일")
            elif any(kw in stem or kw in raw for kw in ["정신병와이퍼", "마른와이퍼질", "블라인드에디션", "뒤유리걸레짝"]):
                s_safety = max(s_safety, 9.0)
                detected_complaints.append("우천 시 시야 차단 (오토와이퍼 오류 / 리어와이퍼 부재)")
            elif any(kw in stem or kw in raw for kw in ["팬텀", "유령", "고스트브레이킹", "램프꽂힘", "갈지자"]):
                s_safety = max(s_safety, 8.8)
                detected_complaints.append("ADAS / 주차 램프 센서 오인식 유령 급제동")
            elif any(kw in stem or kw in raw for kw in ["롤백", "뒤로밀림", "밀림", "오토홀드"]):
                s_safety = max(s_safety, 8.5)
                detected_complaints.append("경사로 정차 후 출발 시 롤백 덜컹")
            elif any(kw in stem or kw in raw for kw in ["벽돌", "방전", "0%"]):
                s_safety = max(s_safety, 8.5)
                detected_complaints.append("주행 중 BMS SOC 급락 및 벽돌 셧다운")

            # Functional Breakdown Dimension (25%)
            if any(kw in stem or kw in raw for kw in ["완속반토막", "3.5kW", "꼼수리콜"]):
                s_functional = max(s_functional, 8.8)
                detected_complaints.append("완속 충전 과열 3.5kW 강제 다운그레이드 패치")
            elif any(kw in stem or kw in raw for kw in ["튕김", "PLC", "통신에러", "통신락", "환경부", "세션", "CCU"]):
                s_functional = max(s_functional, 8.5)
                detected_complaints.append("공용 급속 충전기 PLC 통신 오류 및 세션 튕김")
            elif any(kw in stem or kw in raw for kw in ["TCAM", "티캠", "페이스커넥트"]):
                s_functional = max(s_functional, 8.5)
                detected_complaints.append("통신 모듈 먹통 및 스마트키 / 키리스 엔트리 불가")
            elif any(kw in stem or kw in raw for kw in ["12V", "보조배터리", "방전", "먹통", "MCU블랙아웃", "하이퍼스크린"]):
                s_functional = max(s_functional, 8.4)
                detected_complaints.append("12V 저전압 배터리 방전 / 디스플레이 블랙아웃")
            elif any(kw in stem or kw in raw for kw in ["거북이", "쓰로틀링", "과열", "출력제한", "등판불능", "프리컨"]):
                s_functional = max(s_functional, 8.0)
                detected_complaints.append("산길 등판 모터 발열 쓰로틀링 (거북이모드)")
            elif any(kw in stem or kw in raw for kw in ["고착", "물림", "안빠짐", "락결빙", "충전구결빙"]):
                s_functional = max(s_functional, 7.8)
                detected_complaints.append("충전 커넥터 락 고착 및 충전구 결빙 분리 불가")

            # Economic Loss & AS Dimension (15%)
            if any(kw in stem or kw in raw for kw in ["기가캐스팅", "전손", "7천만원", "2천만원", "배터리교체", "하부긁힘"]):
                s_economic = max(s_economic, 9.8)
                detected_complaints.append("경미한 하부 충돌/단차에도 수천만원 배터리·차체 통교체 전손")
            elif any(kw in stem or kw in raw for kw in ["할증", "보험료", "자차거부"]):
                s_economic = max(s_economic, 9.2)
                detected_complaints.append("높은 손해율로 인한 자차 보험료 폭등 및 인수 거절")
            elif any(kw in stem or kw in raw for kw in ["감가폭탄", "감가상각", "중고차", "반값", "똥값"]):
                s_economic = max(s_economic, 9.0)
                detected_complaints.append("중고차 시장 기피 및 극심한 감가폭탄")
            elif any(kw in stem or kw in raw for kw in ["부품수급", "3개월", "블루핸즈거부", "블핸퇴짜", "하이테크유배", "서비스센터"]):
                s_economic = max(s_economic, 8.5)
                detected_complaints.append("직영 AS 정비 인력 부족 및 수개월 수리 대기 유배")

            # Social Conflict Dimension (15%)
            if any(kw in stem or kw in raw for kw in ["입차거부", "입차금지", "지하주차장", "입대의", "주민", "포스트잇"]):
                s_social = max(s_social, 9.5)
                detected_complaints.append("아파트 지하주차장 입차 거부 및 주민 갈등")
            elif any(kw in stem or kw in raw for kw in ["이중주차", "N단", "중립"]):
                s_social = max(s_social, 8.8)
                detected_complaints.append("N단 중립 이중주차 불가로 인한 주차장 멱살잡이")
            elif any(kw in stem or kw in raw for kw in ["짱깨차", "짱차", "테슬람", "알리익스프레스", "조롱", "왕따"]):
                s_social = max(s_social, 8.5)
                detected_complaints.append("특정 전기차 브랜드를 향한 사회적 비하 및 멸칭")

            # Convenience Discomfort Dimension (10%)
            if any(kw in stem or kw in raw for kw in ["뱀파이어드레인", "센트리", "감시모드"]):
                s_convenience = max(s_convenience, 8.8)
                detected_complaints.append("센트리 모드 배터리 상시 방전 (뱀파이어 드레인)")
            elif any(kw in stem or kw in raw for kw in ["휠빵", "위버터빈", "원격주차", "RSPA", "연석"]):
                s_convenience = max(s_convenience, 8.5)
                detected_complaints.append("돌출 림 및 주차 센서 오판으로 인한 휠 연석 긁힘")
            elif any(kw in stem or kw in raw for kw in ["귀신소리", "어퍼암", "자석핸들", "골병승차감"]):
                s_convenience = max(s_convenience, 8.5)
                detected_complaints.append("하체 삐걱 소음 / 스티어링 걸림 / 딱딱한 승차감")
            elif any(kw in stem or kw in raw for kw in ["어라운드뷰", "왜곡", "진흙반죽", "어안", "프레임드랍"]):
                s_convenience = max(s_convenience, 8.0)
                detected_complaints.append("3D 어라운드뷰 왜곡 및 비전 주차 거리 오차")
            elif any(kw in stem or kw in raw for kw in ["굼벵이", "저온충전", "슈차지옥"]):
                s_convenience = max(s_convenience, 8.0)
                detected_complaints.append("충전소 대기 체증 및 저온 충전 속도 저하")
            elif any(kw in stem or kw in raw for kw in ["단차", "누수", "웨더스트립", "워터파크"]):
                s_convenience = max(s_convenience, 7.8)
                detected_complaints.append("차체 단차로 인한 풍절음 및 빗물 누수")

        # Compute Final Polarity
        if score_count > 0:
            final_polarity = total_score / score_count
        else:
            # Fallback based on DSI presence or default complaint tendency
            has_severe = (s_safety > 0 or s_functional > 0 or s_social > 0)
            final_polarity = -0.55 if has_severe else -0.15

        final_polarity = max(-1.0, min(1.0, round(final_polarity, 3)))

        # Assign 4-Tier Label
        if final_polarity >= 0.30:
            tier_label = "POSITIVE"
        elif final_polarity >= -0.29:
            tier_label = "NEUTRAL"
        elif final_polarity >= -0.69:
            tier_label = "NEGATIVE"
        else:
            tier_label = "STRONGLY_NEGATIVE"

        # Compute Defect Severity Index (0.0 to 10.0)
        dsi_score = (
            0.35 * s_safety +
            0.25 * s_functional +
            0.15 * s_economic +
            0.15 * s_social +
            0.10 * s_convenience
        )
        dsi_score = round(max(0.0, min(10.0, dsi_score)), 2)

        breakdown = {
            "safety": round(s_safety, 2),
            "functional": round(s_functional, 2),
            "economic": round(s_economic, 2),
            "social": round(s_social, 2),
            "convenience": round(s_convenience, 2)
        }

        # Deduplicate detected complaints
        unique_complaints = sorted(list(set(detected_complaints)))

        return SentimentResult(
            polarity_score=final_polarity,
            tier_label=tier_label,
            dsi_score=dsi_score,
            dsi_breakdown=breakdown,
            detected_complaints=unique_complaints,
            intensity_multiplier=current_multiplier,
            negation_flag=negate_flag
        )


def main():
    """CLI test harness for sentiment engine."""
    engine = SentimentEngine()
    test_cases = [
        "가성비 하나는 진짜 최고고 실내 공간도 완전 만족스럽네요 추천합니다",
        "단순히 출시 일정과 보조금 규격을 확인하고 있습니다",
        "조립 단차가 약간 아쉽고 와이퍼 소음이 살짝 신경 쓰이네요",
        "배트맨타이어 빗길 수막현상으로 피쉬테일 털리고 지하주차장 입차거부까지 당함 짱깨차 존나 노답이다",
        "고속도로 달리다가 BMS 20%에서 0%로 급락하며 차 셧다운되고 벽돌됨 진짜 죽을뻔함"
    ]

    print("=" * 70)
    print("4-TIER SENTIMENT & DSI SCORING TEST RUN")
    print("=" * 70)
    for text in test_cases:
        res = engine.classify(text)
        print(f"Text: {text}")
        print(f"  -> Polarity: {res.polarity_score:+.3f} | Tier: {res.tier_label:<18} | DSI: {res.dsi_score:.2f} / 10.0")
        print(f"  -> Breakdown: Safety={res.dsi_breakdown['safety']}, Func={res.dsi_breakdown['functional']}, Social={res.dsi_breakdown['social']}")
        print(f"  -> Complaints: {res.detected_complaints}")
        print("-" * 70)


if __name__ == "__main__":
    main()
