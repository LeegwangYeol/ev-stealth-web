"""
domain_tokenizer.py - Pure Python 3.14 Korean Automotive Domain Tokenizer & Morphological Stripper.

Implements:
1. AutomotiveTrie: Prefix-tree data structure with greedy longest-prefix matching for 150+ EV domain terms.
2. Korean Morphological Josa & Eomi Stripping Engine: Rule-based deterministic affix stemmer.
3. Negation Unification: Compound token bonding (e.g. '안_된다', '못_올라감', '입차불가').
4. Text Normalization: Cleans noise, control characters, while preserving technical units (%/℃/kW/km/h).

Zero external runtime dependencies. Standard library only.
"""

from dataclasses import dataclass, field
import json
import os
import re
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class TrieNode:
    """Trie node for Automotive terminology prefix tree."""
    children: Dict[str, 'TrieNode'] = field(default_factory=dict)
    is_end: bool = False
    domain_category: Optional[str] = None
    severity_weight: float = 1.0
    canonical_name: Optional[str] = None


class AutomotiveTrie:
    """
    Prefix-Tree (Trie) implementing greedy longest-prefix matching for Korean automotive
    domain slang, model names, subsystems, and failure symptoms.
    """

    def __init__(self):
        self.root = TrieNode()
        self.term_count = 0

    def insert(
        self,
        word: str,
        domain_category: str = "general",
        severity_weight: float = 1.0,
        canonical_name: Optional[str] = None
    ) -> None:
        """Insert a word or phrase into the Trie."""
        if not word or not isinstance(word, str):
            return
        cleaned = word.strip()
        if not cleaned:
            return

        curr = self.root
        for char in cleaned:
            if char not in curr.children:
                curr.children[char] = TrieNode()
            curr = curr.children[char]

        if not curr.is_end:
            self.term_count += 1
        curr.is_end = True
        curr.domain_category = domain_category
        curr.severity_weight = severity_weight
        curr.canonical_name = canonical_name or cleaned

    def search_longest_prefix(
        self,
        text: str,
        start_idx: int
    ) -> Optional[Tuple[str, str, float, Optional[str], int]]:
        """
        Greedy longest-prefix match from start_idx in text.
        Returns: (matched_surface, domain_category, severity_weight, canonical_name, next_idx) or None.
        """
        curr = self.root
        longest_match = None

        for i in range(start_idx, len(text)):
            char = text[i]
            if char not in curr.children:
                break
            curr = curr.children[char]
            if curr.is_end:
                longest_match = (
                    text[start_idx:i + 1],
                    curr.domain_category,
                    curr.severity_weight,
                    curr.canonical_name,
                    i + 1
                )
        return longest_match


# 250+ Exhaustive Multi-Brand Global EV Domain Lexicon (Term, Category, Severity Weight, Canonical Name)
BASE_AUTOMOTIVE_LEXICON: List[Tuple[str, str, float, str]] = [
    # 1. Vehicle Models & Brands (차종 및 브랜드)
    # --- Tesla ---
    ("테슬라", "vehicle_brand", 1.0, "Tesla"),
    ("Tesla", "vehicle_brand", 1.0, "Tesla"),
    ("모델3", "vehicle_model", 1.0, "Tesla Model 3"),
    ("모델 3", "vehicle_model", 1.0, "Tesla Model 3"),
    ("Model 3", "vehicle_model", 1.0, "Tesla Model 3"),
    ("하이랜드", "vehicle_model", 1.0, "Tesla Model 3 Highland"),
    ("모델Y", "vehicle_model", 1.0, "Tesla Model Y"),
    ("모델 Y", "vehicle_model", 1.0, "Tesla Model Y"),
    ("Model Y", "vehicle_model", 1.0, "Tesla Model Y"),
    ("주니퍼", "vehicle_model", 1.0, "Tesla Model Y Juniper"),
    ("모델S", "vehicle_model", 1.0, "Tesla Model S"),
    ("모델 S", "vehicle_model", 1.0, "Tesla Model S"),
    ("플래드", "vehicle_model", 1.0, "Tesla Plaid"),
    ("Plaid", "vehicle_model", 1.0, "Tesla Plaid"),
    ("모델X", "vehicle_model", 1.0, "Tesla Model X"),
    ("모델 X", "vehicle_model", 1.0, "Tesla Model X"),
    ("사이버트럭", "vehicle_model", 1.0, "Tesla Cybertruck"),
    ("Cybertruck", "vehicle_model", 1.0, "Tesla Cybertruck"),

    # --- Hyundai / Kia / Genesis ---
    ("현대차", "vehicle_brand", 1.0, "Hyundai"),
    ("기아", "vehicle_brand", 1.0, "Kia"),
    ("제네시스", "vehicle_brand", 1.0, "Genesis"),
    ("현기차", "vehicle_brand", 1.0, "Hyundai/Kia"),
    ("아이오닉5", "vehicle_model", 1.0, "Hyundai Ioniq 5"),
    ("아이오닉 5", "vehicle_model", 1.0, "Hyundai Ioniq 5"),
    ("Ioniq 5", "vehicle_model", 1.0, "Hyundai Ioniq 5"),
    ("아이오닉6", "vehicle_model", 1.0, "Hyundai Ioniq 6"),
    ("아이오닉 6", "vehicle_model", 1.0, "Hyundai Ioniq 6"),
    ("Ioniq 6", "vehicle_model", 1.0, "Hyundai Ioniq 6"),
    ("EV6", "vehicle_model", 1.0, "Kia EV6"),
    ("EV9", "vehicle_model", 1.0, "Kia EV9"),
    ("GV60", "vehicle_model", 1.0, "Genesis GV60"),
    ("eG80", "vehicle_model", 1.0, "Genesis Electrified G80"),
    ("eGV70", "vehicle_model", 1.0, "Genesis Electrified GV70"),
    ("코나EV", "vehicle_model", 1.0, "Hyundai Kona EV"),
    ("니로EV", "vehicle_model", 1.0, "Kia Niro EV"),
    ("포터EV", "vehicle_model", 1.0, "Hyundai Porter EV"),
    ("봉고EV", "vehicle_model", 1.0, "Kia Bongo EV"),

    # --- Global Imports (Mercedes, BMW, Porsche, Polestar, GM) ---
    ("메르세데스", "vehicle_brand", 1.0, "Mercedes-Benz"),
    ("벤츠", "vehicle_brand", 1.0, "Mercedes-Benz"),
    ("EQE", "vehicle_model", 1.0, "Mercedes-Benz EQE"),
    ("EQS", "vehicle_model", 1.0, "Mercedes-Benz EQS"),
    ("EQA", "vehicle_model", 1.0, "Mercedes-Benz EQA"),
    ("EQB", "vehicle_model", 1.0, "Mercedes-Benz EQB"),
    ("BMW", "vehicle_brand", 1.0, "BMW"),
    ("i4", "vehicle_model", 1.0, "BMW i4"),
    ("iX3", "vehicle_model", 1.0, "BMW iX3"),
    ("i7", "vehicle_model", 1.0, "BMW i7"),
    ("iX", "vehicle_model", 1.0, "BMW iX"),
    ("포르쉐", "vehicle_brand", 1.0, "Porsche"),
    ("타이칸", "vehicle_model", 1.0, "Porsche Taycan"),
    ("폴스타", "vehicle_brand", 1.0, "Polestar"),
    ("폴스타2", "vehicle_model", 1.0, "Polestar 2"),
    ("폴스타4", "vehicle_model", 1.0, "Polestar 4"),
    ("볼트EV", "vehicle_model", 1.0, "Chevrolet Bolt EV"),
    ("볼트EUV", "vehicle_model", 1.0, "Chevrolet Bolt EUV"),
    ("이쿼녹스EV", "vehicle_model", 1.0, "Chevrolet Equinox EV"),
    ("토레스EVX", "vehicle_model", 1.0, "Torres EVX"),

    # --- BYD & Chinese Passenger & Commercial ---
    ("BYD", "vehicle_brand", 1.0, "BYD"),
    ("비와이디", "vehicle_brand", 1.0, "BYD"),
    ("비야디", "vehicle_brand", 1.0, "BYD"),
    ("바이드", "vehicle_brand", 1.0, "BYD"),
    ("아토3", "vehicle_model", 1.0, "BYD Atto 3"),
    ("아토 3", "vehicle_model", 1.0, "BYD Atto 3"),
    ("아토쓰리", "vehicle_model", 1.0, "BYD Atto 3"),
    ("앗삼", "vehicle_model", 1.0, "BYD Atto 3"),
    ("ATTO3", "vehicle_model", 1.0, "BYD Atto 3"),
    ("Atto 3", "vehicle_model", 1.0, "BYD Atto 3"),
    ("씰", "vehicle_model", 1.0, "BYD Seal"),
    ("SEAL", "vehicle_model", 1.0, "BYD Seal"),
    ("돌핀", "vehicle_model", 1.0, "BYD Dolphin"),
    ("DOLPHIN", "vehicle_model", 1.0, "BYD Dolphin"),
    ("씰리온7", "vehicle_model", 1.0, "BYD Sealion 7"),
    ("씰리온 7", "vehicle_model", 1.0, "BYD Sealion 7"),
    ("씨라이언7", "vehicle_model", 1.0, "BYD Sealion 7"),
    ("씨라이언 7", "vehicle_model", 1.0, "BYD Sealion 7"),
    ("SEALION7", "vehicle_model", 1.0, "BYD Sealion 7"),
    ("Sealion 7", "vehicle_model", 1.0, "BYD Sealion 7"),
    ("T4K", "vehicle_model", 1.0, "BYD T4K"),
    ("티포케이", "vehicle_model", 1.0, "BYD T4K"),
    ("티포-케이", "vehicle_model", 1.0, "BYD T4K"),
    ("GS글로벌T4K", "vehicle_model", 1.0, "BYD T4K"),
    ("동풍소콘", "vehicle_brand", 1.0, "DFSK"),
    ("DFSK", "vehicle_brand", 1.0, "DFSK"),
    ("마사다", "vehicle_model", 1.0, "DFSK Masada"),
    ("마사다밴", "vehicle_model", 1.0, "DFSK Masada"),
    ("마사다 2밴", "vehicle_model", 1.0, "DFSK Masada 2-Van"),
    ("이티밴", "vehicle_model", 1.0, "ET-VAN"),
    ("ETVAN", "vehicle_model", 1.0, "ET-VAN"),
    ("ET-VAN", "vehicle_model", 1.0, "ET-VAN"),
    ("지리", "vehicle_brand", 1.0, "Geely"),
    ("지커", "vehicle_brand", 1.0, "Zeekr"),
    ("샤오미", "vehicle_brand", 1.0, "Xiaomi"),
    ("SU7", "vehicle_model", 1.0, "Xiaomi SU7"),

    # 2. Battery, Thermal & Power Electronics Subsystems (배터리 및 전장)
    ("E-GMP", "tech_platform", 1.5, "E-GMP 플랫폼"),
    ("ICCU", "tech_electrical", 2.5, "통합충전제어장치 (ICCU)"),
    ("통합충전제어장치", "tech_electrical", 2.5, "통합충전제어장치 (ICCU)"),
    ("ICCU 폭탄", "hyundai_charging", 2.5, "ICCU 폭탄"),
    ("ICCU폭탄", "hyundai_charging", 2.5, "ICCU 폭탄"),
    ("ICCU 터짐", "hyundai_charging", 2.5, "ICCU 터짐"),
    ("ICCU터짐", "hyundai_charging", 2.5, "ICCU 터짐"),
    ("전원공급시스템", "hyundai_charging", 2.2, "전원공급시스템 점검 경고"),
    ("전원공급시스템 점검", "hyundai_charging", 2.5, "전원공급시스템 점검 경고"),
    ("LDC", "tech_electrical", 2.0, "저전압 직류변환장치 (LDC)"),
    ("OBC", "tech_electrical", 1.8, "온보드 차저 (OBC)"),
    ("V2L", "tech_electrical", 1.2, "V2L (양방향 전력공급)"),
    ("옥토밸브", "tesla_thermal", 2.5, "옥토밸브 (Octovalve)"),
    ("Octovalve", "tesla_thermal", 2.5, "옥토밸브 (Octovalve)"),
    ("옥토밸브 사망", "tesla_thermal", 2.5, "옥토밸브 사망"),
    ("옥토밸브사망", "tesla_thermal", 2.5, "옥토밸브 사망"),
    ("히트펌프", "tech_thermal", 1.5, "히트펌프"),
    ("PTC히터", "tech_thermal", 1.8, "PTC 히터"),
    ("PTC 히터", "tech_thermal", 1.8, "PTC 히터"),
    ("히터 찬바람", "hyundai_driving", 2.2, "혹한기 히터 찬바람 결함"),
    ("히터찬바람", "hyundai_driving", 2.2, "혹한기 히터 찬바람 결함"),
    ("얼음방 에디션", "porsche_climate", 2.5, "타이칸 얼음방 에디션"),
    ("얼음방에디션", "porsche_climate", 2.5, "타이칸 얼음방 에디션"),
    ("냉동고 타이칸", "porsche_climate", 2.5, "냉동고 타이칸"),
    ("냉동고타이칸", "porsche_climate", 2.5, "냉동고 타이칸"),
    ("파라시스", "mercedes_battery", 2.5, "Farasis 파라시스 배터리"),
    ("Farasis", "mercedes_battery", 2.5, "Farasis 파라시스 배터리"),
    ("파라시스 폭탄", "mercedes_battery", 2.5, "파라시스 폭탄"),
    ("파라시스폭탄", "mercedes_battery", 2.5, "파라시스 폭탄"),
    ("LFP", "tech_battery", 1.5, "LFP 배터리"),
    ("리튬인산철", "tech_battery", 1.5, "LFP 배터리"),
    ("인산철", "tech_battery", 1.5, "LFP 배터리"),
    ("블레이드배터리", "tech_battery", 1.8, "블레이드 배터리"),
    ("블레이드 배터리", "tech_battery", 1.8, "블레이드 배터리"),
    ("NCM", "tech_battery", 1.2, "NCM 삼원계"),
    ("삼원계", "tech_battery", 1.2, "NCM 삼원계"),
    ("BMS", "tech_bms", 1.8, "BMS (배터리관리시스템)"),
    ("SOC", "tech_bms", 1.5, "SOC (배터리잔량)"),
    ("12V배터리", "tech_electrical", 1.8, "12V 저전압 배터리"),
    ("12V 보조배터리", "tech_electrical", 1.8, "12V 저전압 배터리"),
    ("12V방전", "charging_12v", 2.0, "12V 저전압 배터리 방전"),
    ("12V 방전", "charging_12v", 2.0, "12V 저전압 배터리 방전"),
    ("뱀파이어 드레인", "tesla_charging", 2.0, "뱀파이어 드레인 (Sentry 모드 방전)"),
    ("뱀파이어드레인", "tesla_charging", 2.0, "뱀파이어 드레인 (Sentry 모드 방전)"),
    ("센트리 모드", "tesla_charging", 1.8, "센트리 모드"),
    ("센트리모드", "tesla_charging", 1.8, "센트리 모드"),
    ("전압강하", "tech_bms", 2.0, "전압 강하 (Voltage Sag)"),
    ("Voltage Sag", "tech_bms", 2.0, "전압 강하 (Voltage Sag)"),

    # 3. Charging Protocol & Hardware (충전 프로토콜 및 인터페이스)
    ("슈퍼차저", "tesla_charging", 1.5, "슈퍼차저 (Supercharger)"),
    ("슈차", "tesla_charging", 1.5, "슈퍼차저 (Supercharger)"),
    ("슈차 지옥", "tesla_charging", 1.8, "슈퍼차저 대기열 지옥"),
    ("슈차지옥", "tesla_charging", 1.8, "슈퍼차저 대기열 지옥"),
    ("NACS", "charging_protocol", 1.5, "테슬라 NACS 충전 포트"),
    ("CCS1", "charging_protocol", 1.2, "DC 콤보 CCS1"),
    ("DC콤보", "charging_protocol", 1.2, "DC 콤보 CCS1"),
    ("DC콤보 벽돌", "tesla_charging", 1.8, "무거운 CCS1 어댑터 벽돌"),
    ("이핏", "charging_cpo", 1.2, "현대 이핏 (E-pit)"),
    ("E-pit", "charging_cpo", 1.2, "현대 이핏 (E-pit)"),
    ("PLC통신", "charging_protocol", 2.0, "PLC 통신"),
    ("ISO15118", "charging_protocol", 1.8, "KS R ISO 15118 프로토콜"),
    ("DIN70121", "charging_protocol", 1.8, "DIN 70121 프로토콜"),
    ("환경부충전기", "charging_cpo", 1.8, "환경부 공공 급속 충전기"),
    ("채비", "charging_cpo", 1.5, "채비(CHAEVI) 충전기"),
    ("커넥터락", "charging_lock", 1.8, "충전 커넥터 솔레노이드 락"),
    ("충전건고착", "charging_lock", 2.0, "충전건 물림 고착"),
    ("충전건 고착", "charging_lock", 2.0, "충전건 물림 고착"),
    ("충전구결빙", "charging_lock", 1.8, "혹한기 충전구 결빙"),
    ("충전구 결빙", "charging_lock", 1.8, "혹한기 충전구 결빙"),
    ("통신튕김", "charging_protocol", 2.0, "충전 PLC 통신 튕김"),
    ("환경부튕김", "charging_protocol", 2.0, "환경부 급속 충전기 PLC 튕김"),
    ("환경부 튕김", "charging_protocol", 2.0, "환경부 급속 충전기 PLC 튕김"),
    ("세션튕김", "charging_protocol", 2.0, "충전 세션 튕김"),
    ("세션 튕김", "charging_protocol", 2.0, "충전 세션 튕김"),
    ("굼벵이충전", "charging_lfp", 2.0, "혹한기 LFP 굼벵이 충전"),
    ("굼벵이 충전", "charging_lfp", 2.0, "혹한기 LFP 굼벵이 충전"),
    ("반토막충전", "charging_lfp", 1.8, "저온 급속 반토막 충전"),
    ("반토막 충전", "charging_lfp", 1.8, "저온 급속 반토막 충전"),
    ("완속반토막", "hyundai_charging", 2.0, "완속 3.5kW 강제 반토막"),
    ("완속 반토막 패치", "hyundai_charging", 2.0, "완속 3.5kW 강제 반토막"),
    ("CCU 사망", "bmw_charging", 2.2, "BMW CCU 소손 사망"),
    ("CCU사망", "bmw_charging", 2.2, "BMW CCU 소손 사망"),

    # 4. ADAS, Vision, Parking & Chassis (주행보조, 비전, 주차, 섀시)
    ("테슬라비전", "tesla_vision", 2.0, "테슬라 비전 (Tesla Vision)"),
    ("테슬라 비전", "tesla_vision", 2.0, "테슬라 비전 (Tesla Vision)"),
    ("초음파센서", "parking_sensors", 1.5, "초음파 주차 센서 (USS)"),
    ("USS", "parking_sensors", 1.5, "초음파 주차 센서 (USS)"),
    ("하이피델리티", "tesla_vision", 1.8, "하이 피델리티 파크 어시스트"),
    ("진흙 반죽", "tesla_parking", 2.0, "3D 진흙 반죽 그래픽"),
    ("진흙반죽", "tesla_parking", 2.0, "3D 진흙 반죽 그래픽"),
    ("위버터빈", "tesla_parking", 2.0, "위버터빈 대구경 휠"),
    ("휠빵", "tesla_parking", 2.0, "휠빵 (연석 긁힘)"),
    ("스마트서먼", "tesla_vision", 2.0, "스마트 서먼 (Smart Summon)"),
    ("스마트 서먼", "tesla_vision", 2.0, "스마트 서먼 (Smart Summon)"),
    ("ASS", "tesla_vision", 2.0, "Actually Smart Summon (ASS)"),
    ("RSPA", "hyundai_parking", 1.8, "원격 스마트 주차 보조 (RSPA)"),
    ("RSPA2", "hyundai_parking", 1.8, "원격 스마트 주차 보조 2 (RSPA 2)"),
    ("원격주차 휠스킨", "hyundai_parking", 2.0, "RSPA 원격 주차 휠 긁힘"),
    ("램프 꽂힘", "hyundai_parking", 2.2, "지하주차장 램프 유령 급제동"),
    ("램프꽂힘", "hyundai_parking", 2.2, "지하주차장 램프 유령 급제동"),
    ("어라운드뷰", "parking_camera", 1.5, "3D 어라운드뷰"),
    ("어라운드 뷰", "parking_camera", 1.5, "3D 어라운드뷰"),
    ("3D어라운드뷰", "parking_camera", 1.8, "3D 어라운드뷰 왜곡"),
    ("서라운드뷰", "parking_camera", 1.5, "360도 서라운드뷰"),
    ("어안렌즈", "parking_camera", 1.5, "어안렌즈 광각 왜곡"),
    ("어안왜곡", "parking_camera", 1.8, "어안렌즈 왜곡"),
    ("프레임드랍", "parking_camera", 1.8, "카메라 15fps 프레임 드랍"),
    ("스펀지 브레이크", "mercedes_braking", 2.2, "벤츠 EQ 스펀지 브레이크"),
    ("스펀지브레이크", "mercedes_braking", 2.2, "벤츠 EQ 스펀지 브레이크"),
    ("허당 브레이크", "mercedes_braking", 2.2, "허당 브레이크 답력 상실"),
    ("벽돌 페달", "bmw_braking", 2.5, "BMW Continental MK C2 벽돌 페달"),
    ("벽돌페달", "bmw_braking", 2.5, "BMW Continental MK C2 벽돌 페달"),
    ("TCAM", "polestar_connectivity", 2.2, "폴스타 TCAM 통신 모듈"),
    ("티캠", "polestar_connectivity", 2.2, "폴스타 TCAM 통신 모듈"),
    ("티캠 먹통", "polestar_connectivity", 2.2, "티캠 통신 두절 및 키리스 먹통"),
    ("티캠먹통", "polestar_connectivity", 2.2, "티캠 통신 두절 및 키리스 먹통"),
    ("자석 핸들", "tesla_steering", 2.2, "스티어링 랙 노치 (자석 핸들)"),
    ("자석핸들", "tesla_steering", 2.2, "스티어링 랙 노치 (자석 핸들)"),
    ("어퍼암", "tesla_suspension", 2.0, "어퍼 컨트롤 암 (Upper Control Arm)"),
    ("귀신 소리", "tesla_suspension", 2.0, "어퍼암 볼조인트 귀신 소리"),
    ("귀신소리", "tesla_suspension", 2.0, "어퍼암 볼조인트 귀신 소리"),
    ("기가캐스팅", "tesla_body", 2.5, "기가캐스팅 알루미늄 차체"),
    ("Gigacasting", "tesla_body", 2.5, "기가캐스팅 알루미늄 차체"),
    ("골병 승차감", "polestar_comfort", 2.0, "폴스타 골병 승차감"),
    ("골병승차감", "polestar_comfort", 2.0, "폴스타 골병 승차감"),
    ("토션빔", "chassis_suspension", 1.5, "후륜 토션빔 서스펜션"),
    ("오토홀드", "hill_climbing", 2.0, "전자식 오토홀드"),
    ("EPB", "chassis_brake", 1.5, "EPB 전자식 파킹 브레이크"),
    ("TCS", "chassis_control", 1.8, "TCS (트랙션컨트롤)"),
    ("ESC", "chassis_control", 1.8, "ESC (차체자세제어)"),
    ("회생제동", "chassis_brake", 1.8, "회생제동 토크 개입"),
    ("눈꽃 마크", "tesla_driving", 2.2, "냉간 회생제동 차단 (눈꽃 마크)"),
    ("눈꽃마크", "tesla_driving", 2.2, "냉간 회생제동 차단 (눈꽃 마크)"),
    ("배트맨타이어", "rain_driving_tires", 2.5, "순정 Atlas Batman OE 타이어"),
    ("배트맨 타이어", "rain_driving_tires", 2.5, "순정 Atlas Batman OE 타이어"),
    ("Atlas Batman", "rain_driving_tires", 2.5, "Atlas Batman A51 타이어"),
    ("웻그립", "rain_driving_tires", 2.5, "빗길 웻그립 (젖은노면 접지력)"),
    ("수막현상", "rain_driving_tires", 2.5, "빗길 고속 수막현상"),
    ("휠스핀", "rain_driving_tires", 2.2, "젖은 노면/오르막 휠스핀"),
    ("피쉬테일", "rain_driving_handling", 2.5, "빗길 맨홀/철판 피쉬테일"),
    ("차체털림", "rain_driving_handling", 2.2, "빗길 차체 털림"),
    ("차체 털림", "rain_driving_handling", 2.2, "빗길 차체 털림"),
    ("팬텀브레이킹", "rain_driving_adas", 2.5, "폭우 시 ADAS 팬텀 브레이킹"),
    ("팬텀 브레이킹", "rain_driving_adas", 2.5, "폭우 시 ADAS 팬텀 브레이킹"),
    ("고스트브레이킹", "rain_driving_adas", 2.5, "유령 급제동 (고스트 브레이킹)"),
    ("유령급제동", "rain_driving_adas", 2.5, "우천 시 유령 급제동"),
    ("정신병 와이퍼", "tesla_wiper", 2.5, "정신병 와이퍼 (Deep Rain 오류)"),
    ("정신병와이퍼", "tesla_wiper", 2.5, "정신병 와이퍼 (Deep Rain 오류)"),
    ("마른 와이퍼질", "tesla_wiper", 2.2, "마른 와이퍼질"),
    ("마른와이퍼질", "tesla_wiper", 2.2, "마른 와이퍼질"),
    ("오토와이퍼", "rain_driving_body", 1.5, "오토 와이퍼 로직"),
    ("와이퍼채터링", "rain_driving_body", 1.5, "와이퍼 암 채터링 소음"),
    ("채터링", "rain_driving_body", 1.5, "와이퍼 채터링 소음"),
    ("뒤유리 걸레짝", "hyundai_driving", 2.0, "리어 와이퍼 부재 후방 시야 상실"),
    ("뒤유리걸레짝", "hyundai_driving", 2.0, "리어 와이퍼 부재 후방 시야 상실"),
    ("블라인드 에디션", "hyundai_driving", 2.0, "리어 와이퍼 부재 블라인드 에디션"),
    ("블라인드에디션", "hyundai_driving", 2.0, "리어 와이퍼 부재 블라인드 에디션"),
    ("디프로스트", "rain_driving_body", 1.8, "공조기 디프로스트 성에/습기 제거"),
    ("단차누수", "rain_driving_body", 2.0, "조립 단차 웨더스트립 빗물 누수"),
    ("단차 누수", "rain_driving_body", 2.0, "조립 단차 웨더스트립 빗물 누수"),
    ("단차", "rain_driving_body", 1.5, "조립 단차"),
    ("웨더스트립", "rain_driving_body", 1.8, "도어 고무 웨더스트립 조립 불량"),
    ("실내누수", "rain_driving_body", 2.0, "실내 빗물 누수"),
    ("하부부식", "rain_driving_body", 1.8, "하부 섀시 볼트 붉은 녹 부식"),

    # 5. Hill Climbing, Maintenance, AS & Social Stigma (등판, 정비, 사회적 갈등)
    ("롤백", "hill_climbing", 2.2, "경사로 정차 후 출발 시 롤백 (뒤로 밀림)"),
    ("롤백덜컹", "hill_climbing", 2.2, "경사로 오토홀드 롤백 덜컹"),
    ("롤백 덜컹", "hill_climbing", 2.2, "경사로 오토홀드 롤백 덜컹"),
    ("거북이모드", "hill_climbing_power", 2.2, "모터 과열 거북이모드 출력 제한"),
    ("거북이 모드", "hill_climbing_power", 2.2, "모터 과열 거북이모드 출력 제한"),
    ("거북이등", "hill_climbing_power", 2.2, "계기판 거북이 경고등 점등"),
    ("열쓰로틀링", "hill_climbing_power", 2.2, "모터/인버터 발열 쓰로틀링"),
    ("열 쓰로틀링", "hill_climbing_power", 2.2, "모터/인버터 발열 쓰로틀링"),
    ("출력제한", "hill_climbing_power", 2.0, "모터 출력 제한"),
    ("등판불능", "hill_climbing_power", 2.5, "급경사 등판 불능"),
    ("블루핸즈", "hyundai_as", 1.2, "현대 블루핸즈"),
    ("오토큐", "hyundai_as", 1.2, "기아 오토큐"),
    ("블핸 퇴짜", "hyundai_as", 2.0, "블루핸즈 전기차 입고 거부"),
    ("블핸퇴짜", "hyundai_as", 2.0, "블루핸즈 전기차 입고 거부"),
    ("하이테크센터", "hyundai_as", 1.5, "직영 하이테크센터"),
    ("하이테크 유배", "hyundai_as", 2.0, "하이테크센터 3개월 대기 유배"),
    ("서비스센터 예약", "economics_as", 2.0, "서비스센터 2달 예약 대기"),
    ("전손 폭탄", "economics_as", 2.5, "기가캐스팅/배터리 전손 폭탄"),
    ("전손폭탄", "economics_as", 2.5, "기가캐스팅/배터리 전손 폭탄"),
    ("묻지마 전손", "economics_as", 2.5, "하부 긁힘 묻지마 전손"),
    ("묻지마전손", "economics_as", 2.5, "하부 긁힘 묻지마 전손"),
    ("하부 긁힘 2천만 원", "economics_as", 2.5, "배터리 하부 긁힘 2천만원 통교체"),
    ("7천만원 전손", "economics_as", 2.5, "타이칸 배터리 7천만원 전손"),
    ("7천만원전손", "economics_as", 2.5, "타이칸 배터리 7천만원 전손"),
    ("할증 폭탄", "economics_as", 2.2, "자차 보험료 할증 폭탄"),
    ("할증폭탄", "economics_as", 2.2, "자차 보험료 할증 폭탄"),
    ("감가폭탄", "economics_as", 2.0, "중고차 잔존가치 감가폭탄"),
    ("감가 폭탄", "economics_as", 2.0, "중고차 잔존가치 감가폭탄"),
    ("감가상각", "economics_as", 1.8, "중고차 감가상각"),
    ("부품수급 3개월", "economics_as", 2.0, "AS 부품 수급 3개월 지연"),
    ("부품수급", "economics_as", 1.8, "AS 부품 수급 부족"),
    ("부품 수급", "economics_as", 1.8, "AS 부품 수급 부족"),
    ("선전직구부품", "economics_as", 1.8, "선전 직구 자가수리 부품"),
    ("어부바", "economics_as", 1.8, "어부바 렉카 견인"),
    ("어부바견인", "economics_as", 1.8, "어부바 렉카 견인"),
    ("벽돌차", "charging_12v", 2.5, "12V 방전 벽돌차"),
    ("벽돌", "charging_12v", 2.5, "차량 시스템 벽돌"),
    ("벽돌방전", "charging_12v", 2.5, "벽돌 방전"),
    ("벽돌 현상", "charging_12v", 2.5, "시스템 벽돌 현상"),
    ("OTA 벽돌", "charging_12v", 2.5, "OTA 펌웨어 에러 벽돌"),
    ("OTA벽돌", "charging_12v", 2.5, "OTA 펌웨어 에러 벽돌"),
    ("MCU 블랙아웃", "tesla_infotainment", 2.5, "MCU 화면 블랙아웃"),
    ("하이퍼스크린 블랙아웃", "mercedes_infotainment", 2.5, "하이퍼스크린 블랙아웃"),
    ("짱깨차", "general_derogatory", 2.2, "중국산 자동차 비하 멸칭"),
    ("짱차", "general_derogatory", 2.2, "중국산 차량 축약 멸칭"),
    ("테슬람", "general_derogatory", 1.8, "테슬라 극성 팬덤 비하어"),
    ("바퀴달린 알리익스프레스", "general_derogatory", 2.2, "바퀴달린 알리익스프레스"),
    ("알리트럭", "commercial_vehicles", 2.2, "중국산 1톤 전기 화물차 멸칭"),
    ("짱트럭", "commercial_vehicles", 2.2, "중국산 1톤 전기 화물차 멸칭"),
    ("움직이는 시한폭탄", "parking_social", 2.5, "움직이는 시한폭탄 (화재 포비아)"),
    ("시한폭탄", "parking_social", 2.5, "움직이는 시한폭탄"),
    ("화재 테러범", "parking_social", 2.5, "화재 테러범 취급"),
    ("화재포비아", "parking_social", 2.2, "아파트 지하주차장 화재 포비아"),
    ("불쇼", "parking_social", 2.5, "배터리 열폭주 화재 불쇼"),
    ("자폭차", "parking_social", 2.2, "자폭차"),
    ("황천길 익스프레스", "safety_general", 2.5, "황천길 익스프레스"),
    ("황천길", "safety_general", 2.5, "황천길"),
    ("지하주차장 입차거부", "parking_social", 2.5, "지하주차장 입차 거부"),
    ("지하주차장입차거부", "parking_social", 2.5, "지하주차장 입차 거부"),
    ("지하주차장거부", "parking_social", 2.5, "지하주차장 진입 거부"),
    ("입차거부", "parking_social", 2.5, "지하주차장 입차 거부"),
    ("입차금지", "parking_social", 2.5, "지하주차장 입차 금지"),
    ("기계식주차불가", "parking", 2.0, "기계식 주차타워 입고 불가"),
    ("중량초과", "parking", 2.0, "공차중량 2톤 초과"),
    ("N단중립주차불가", "parking", 1.8, "N단 중립 이중주차 불가"),
    ("이중주차불가", "parking", 1.8, "아파트 이중주차 불가"),
    ("이중주차", "parking", 1.5, "이중주차"),
    ("연석충돌", "parking", 2.0, "자동주차 연석 충돌"),
]


class DomainTokenizer:
    """
    Korean Automotive NLP Tokenizer combining Trie prefix matching,
    morphological postposition (Josa) & verb/adjective ending (Eomi) stripping,
    and negation unification.
    """

    # Korean Postpositions (Josa) Regex Pattern
    JOSA_REGEX = re.compile(
        r'^(.*?)(은|는|이|가|을|를|에|에서|로|으로|과|와|도|만|부터|까지|한테|에게|보다|의|랑|이랑|이라서|이어서|이며|이고|이나|이라도|이든|마저|조차|처럼|같이|마다|땜에|때메|에게서|한테서)$'
    )

    # Korean Verb / Adjective Endings (Eomi) Regex Pattern
    EOMI_REGEX = re.compile(
        r'^(.*?)(하다|되다|나다|먹다|터지다|나오다|당하다|됐다|났다|터졌다|밀렸다|끊겼다|망했다|빠졌다|탔다|걸렸다|꽂혔다|깎였다|털렸다|긁혔다|죽었다|박았다|멈췄다|가다|갔다|오다|왔다|치다|쳤다|보이다|들다|하는데|되는데|나는데|터지는데|밀리는데|끊기는데|당하는데|습니다|ㅂ니다|세요|어요|아요|더군요|네요|거든|잖아|구요|는데|으니|니까|려고|면서|더라|았다|었다|였다|으면|려면)$'
    )

    # Text Normalization Cleaner: preserves Korean, alphanumeric, whitespace, key units
    CLEAN_REGEX = re.compile(r'[^가-힣A-Za-z0-9\s%℃kWkm/h\-\.\,\_\/]')

    def __init__(self, slang_dict_path: Optional[str] = None):
        self.trie = AutomotiveTrie()
        self._build_lexicon(slang_dict_path)

    def _build_lexicon(self, slang_dict_path: Optional[str]):
        """Populate Trie with base automotive lexicon and optional external slang dict."""
        for term, cat, weight, canon in BASE_AUTOMOTIVE_LEXICON:
            self.trie.insert(term, domain_category=cat, severity_weight=weight, canonical_name=canon)
            # Insert spaceless version if phrase contains whitespace
            if " " in term:
                self.trie.insert(
                    term.replace(" ", ""),
                    domain_category=cat,
                    severity_weight=weight,
                    canonical_name=canon
                )

        # Ingest external slang dictionary if available
        dict_candidates = [
            slang_dict_path,
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "slang_dict.json"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "slang_dict.json"),
            os.path.join(os.getcwd(), "data", "slang_dict.json"),
            os.path.join(os.getcwd(), "..", "data", "slang_dict.json"),
        ]
        dict_path = next((p for p in dict_candidates if p and os.path.exists(p)), None)
        if dict_path:
            try:
                with open(dict_path, "r", encoding="utf-8") as f:
                    slang_data = json.load(f)
                for term, info in slang_data.items():
                    cat = info.get("category", "slang")
                    self.trie.insert(term, domain_category=cat, severity_weight=2.0, canonical_name=term)
                    if " " in term:
                        self.trie.insert(term.replace(" ", ""), domain_category=cat, severity_weight=2.0, canonical_name=term)
            except Exception:
                pass

    def strip_affixes(self, token_str: str) -> str:
        """Strip Josa and Eomi from token string."""
        stem = token_str
        # Strip Josa first
        josa_m = self.JOSA_REGEX.match(stem)
        if josa_m and len(josa_m.group(1)) >= 2:
            stem = josa_m.group(1)

        # Strip Eomi second
        eomi_m = self.EOMI_REGEX.match(stem)
        if eomi_m and len(eomi_m.group(1)) >= 2:
            stem = eomi_m.group(1)

        return stem

    def normalize_text(self, text: str) -> str:
        """Clean noise characters and unify whitespace."""
        if not text:
            return ""
        cleaned = self.CLEAN_REGEX.sub(" ", text)
        return re.sub(r'\s+', ' ', cleaned).strip()

    def tokenize(self, text: str) -> List[Dict[str, Any]]:
        """
        Tokenize raw Korean automotive text into rich token objects.
        Implements Trie longest match, affix stripping, and negation unification.
        """
        normalized = self.normalize_text(text)
        tokens: List[Dict[str, Any]] = []
        i = 0
        n = len(normalized)

        while i < n:
            if normalized[i].isspace():
                i += 1
                continue

            # 1. Check Trie for Longest Domain Prefix Match
            trie_match = self.trie.search_longest_prefix(normalized, i)
            if trie_match:
                matched_surface, cat, weight, canon, next_idx = trie_match
                tokens.append({
                    "raw": matched_surface,
                    "stem": canon or matched_surface,
                    "category": cat,
                    "weight": weight,
                    "is_domain": True
                })
                i = next_idx
                continue

            # 2. Extract standard whitespace-delimited word
            match = re.match(r'\S+', normalized[i:])
            if match:
                raw_word = match.group(0)
                i += len(raw_word)

                # Strip affixes (Josa / Eomi)
                stem = self.strip_affixes(raw_word)

                # Re-check stripped stem in Trie
                stem_trie_match = self.trie.search_longest_prefix(stem, 0)
                if stem_trie_match and stem_trie_match[4] == len(stem):
                    _, cat, weight, canon, _ = stem_trie_match
                    tokens.append({
                        "raw": raw_word,
                        "stem": canon or stem,
                        "category": cat,
                        "weight": weight,
                        "is_domain": True
                    })
                else:
                    tokens.append({
                        "raw": raw_word,
                        "stem": stem,
                        "category": "general_token",
                        "weight": 1.0,
                        "is_domain": False
                    })
            else:
                i += 1

        # 3. Negation & Compound Unification Pass
        unified_tokens = self._unify_negations(tokens)
        return unified_tokens

    def _unify_negations(self, tokens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Unify adjacent negation particles with predicates:
        e.g. ['안', '된다'] -> '안_된다', ['못', '올라감'] -> '못_올라감'
        """
        unified = []
        skip_next = False
        neg_particles = {"안", "못", "전혀", "결코", "절대"}

        for idx, tok in enumerate(tokens):
            if skip_next:
                skip_next = False
                continue

            stem = tok["stem"]
            raw = tok["raw"]

            if idx + 1 < len(tokens) and (raw in neg_particles or stem in neg_particles):
                next_tok = tokens[idx + 1]
                combined_stem = f"{stem}_{next_tok['stem']}"
                combined_raw = f"{raw} {next_tok['raw']}"
                unified.append({
                    "raw": combined_raw,
                    "stem": combined_stem,
                    "category": "negated_predicate",
                    "weight": max(tok.get("weight", 1.0), next_tok.get("weight", 1.0)) * 1.3,
                    "is_domain": True
                })
                skip_next = True
            else:
                unified.append(tok)

        return unified

    def tokenize_to_stems(self, text: str) -> List[str]:
        """Convenience method returning list of clean token stems."""
        tokens = self.tokenize(text)
        return [t["stem"] for t in tokens if len(t["stem"]) > 1]


def main():
    """Quick CLI verification for domain_tokenizer."""
    tokenizer = DomainTokenizer()
    sample = "아토3 순정 배트맨타이어 끼고 비오는 날 올림픽대로에서 수막현상 터지며 피쉬테일 털리고 지하주차장 입차거부까지 당함 짱차 진짜 노답이다"
    tokens = tokenizer.tokenize(sample)
    print("=" * 60)
    print("DOMAIN TOKENIZER TEST RUN")
    print("=" * 60)
    print(f"Input: {sample}")
    print(f"Total Trie Terms: {tokenizer.trie.term_count}")
    print(f"Tokens ({len(tokens)}):")
    for t in tokens:
        print(f"  - raw: {t['raw']:<16} | stem: {t['stem']:<20} | cat: {t['category']:<18} | domain: {t['is_domain']} | w: {t['weight']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
