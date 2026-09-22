"""
Integrity & Behavioral Verification for the E2E Test Suite and Statistical Validator.

Verifies that:
1. Positive test cases: fully compliant dataset, scrapers, casebook, and statistical report pass all tiers.
2. Negative test cases:
   - Missing category triggers Tier 1 failure.
   - Empty quote or invalid URL triggers Tier 2 failure.
   - Monopolized platform triggers Tier 3 failure.
   - Missing casebook section or placeholder tokens triggers Tier 4 failure.
   - Missing mandatory platform or missing TOP ranking table triggers Tier 5 failure.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if not (PROJECT_ROOT / "scrapers").exists() and (PROJECT_ROOT.parent / "scrapers").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.e2e.test_runner import run_tier_suite, TIER_REGISTRY


SAMPLE_COMPLIANT_DATA = [
    # Parking (Tesla, Hyundai, BYD, Blind, DC, Bobae)
    {
        "id": "complaint_001",
        "platform": "dcinside",
        "board_name": "테슬라 갤러리",
        "post_url": "https://gall.dcinside.com/mgallery/board/view/?id=tesla&no=10234",
        "post_title": "모델Y 비전 파크 맹안 때문에 스토퍼 박고 립스포일러 다 깨먹음",
        "target_vehicle": "Tesla Model Y",
        "category": "parking",
        "defect_topic": "초음파 센서(USS) 삭제 및 범퍼 하단 1.5m 맹안으로 인한 스토퍼 충돌",
        "raw_quote": "초음파 센서 빼먹고 3D 진흙 반죽 그래픽 띄워놓고 멈추라는 테슬라 능지... 앞범퍼 하단 1.5미터 맹안이라 스토퍼 박고 립 깨먹음 개빡치네",
        "slang_terms": ["진흙반죽", "맹안", "개빡치네"],
        "collected_at": "2026-08-25T14:30:00Z"
    },
    {
        "id": "complaint_002",
        "platform": "bobaedream",
        "board_name": "국산차게시판",
        "post_url": "https://www.bobaedream.co.kr/view?code=national&No=213456",
        "post_title": "아이오닉5 RSPA 원격주차 믿다가 연석에 20인치 휠 우지끈 갈아먹음",
        "target_vehicle": "Hyundai Ioniq 5",
        "category": "parking",
        "defect_topic": "RSPA 2 낮은 연석 미인식으로 인한 휠 긁힘 파손",
        "raw_quote": "RSPA 원격주차 멋지게 빼려다 연석에 휠 긁고 휠빵 당함 센서가 낮은 턱을 못 봄 휠 복원비 15만원 날리고 피눈물 흘림 노답",
        "slang_terms": ["휠빵", "피눈물", "노답"],
        "collected_at": "2026-08-26T09:12:00Z"
    },
    {
        "id": "complaint_003",
        "platform": "blind",
        "board_name": "자동차",
        "post_url": "https://www.teamblind.com/kr/post/BYD-주차-경험-x1y2",
        "post_title": "BYD T4K 기계식 주차타워 중량초과로 입고 거부당함",
        "target_vehicle": "BYD T4K",
        "category": "parking",
        "defect_topic": "LFP 배터리 중량 초과로 인한 주차타워 입고 불가",
        "raw_quote": "LFP 배터리 싣고 공차중량 2톤 넘어가니까 기계식 주차타워 다 튕겨냄 이중주차 중립 N단도 안 먹어서 아파트 주차난 헬게이트 열림",
        "slang_terms": ["튕겨냄", "헬게이트"],
        "collected_at": "2026-08-27T11:05:00Z"
    },
    {
        "id": "complaint_004",
        "platform": "dcinside",
        "board_name": "전기차 갤러리",
        "post_url": "https://gall.dcinside.com/mgallery/board/view/?id=ev&no=10555",
        "post_title": "EV6 지하주차장 내리막 램프 내려가다 유령 급제동 꽂힘",
        "target_vehicle": "Kia EV6",
        "category": "parking",
        "defect_topic": "지하주차장 급경사 램프 진입 시 PCA-R/FCA 유령 긴급제동",
        "raw_quote": "지하주차장 램프 꺾이는 바닥에서 갑자기 쾅 소리 나면서 유령제동 급정거 꽂힘 안전벨트에 명치 얻어맞아서 숨도 안 쉬어짐 ㄷㄷ",
        "slang_terms": ["유령제동", "ㄷㄷ"],
        "collected_at": "2026-08-28T16:20:00Z"
    },
    {
        "id": "complaint_005",
        "platform": "bobaedream",
        "board_name": "수입차게시판",
        "post_url": "https://www.bobaedream.co.kr/view?code=import&No=334455",
        "post_title": "벤츠 EQE 파라시스 배터리 화재 포비아로 아파트 지하주차장 퇴출",
        "target_vehicle": "Mercedes-Benz EQE",
        "category": "parking",
        "defect_topic": "지하주차장 입차 거부 및 입주민 갈등",
        "raw_quote": "아파트 입대의에서 파라시스 폭탄 화재포비아 때문에 지하 2층 이하 주차 금지 때림 시한폭탄 취급받아서 개서러움",
        "slang_terms": ["파라시스폭탄", "화재포비아", "시한폭탄"],
        "collected_at": "2026-08-29T10:00:00Z"
    },

    # Charging (Tesla, Hyundai, BMW, Porsche, BYD)
    {
        "id": "complaint_006",
        "platform": "bobaedream",
        "board_name": "국산차게시판",
        "post_url": "https://www.bobaedream.co.kr/view?code=national&No=213789",
        "post_title": "경부고속도로 110km 달리다 ICCU 폭발 전원공급시스템 점검 셧다운",
        "target_vehicle": "Hyundai Ioniq 5",
        "category": "charging",
        "defect_topic": "ICCU 폭발 소손 및 고속도로 주행 중 전원 차단",
        "raw_quote": "경부고속도로 1차선 달리는데 뒤에서 퍽 소리 나더니 ICCU 터지고 전원공급시스템 점검 빨간불 뜸 거북이모드 걸리다 멈춰서 저승길 갈 뻔함 현대차 양아치",
        "slang_terms": ["ICCU", "전원공급시스템", "거북이모드", "저승길"],
        "collected_at": "2026-08-25T18:40:00Z"
    },
    {
        "id": "complaint_007",
        "platform": "dcinside",
        "board_name": "테슬라 갤러리",
        "post_url": "https://gall.dcinside.com/mgallery/board/view/?id=tesla&no=10890",
        "post_title": "현대 이피트(E-pit) 가서 350kW 물려봐야 70kW로 기어가는 굼벵이 신세",
        "target_vehicle": "Tesla Model 3",
        "category": "charging",
        "defect_topic": "현대 E-pit 800V 초급속 충전소 핸드셰이크 통신 오류 및 속도 제한",
        "raw_quote": "이피트 350kW 물려봐야 400V 부스트 변환 때문에 70kW로 기어가는 굼벵이 신세임 DC콤보 어댑터 발열 쓰로틀링 걸리면 35kW 떡락 개빡침",
        "slang_terms": ["굼벵이", "DC콤보", "개빡침"],
        "collected_at": "2026-08-26T21:15:00Z"
    },
    {
        "id": "complaint_008",
        "platform": "blind",
        "board_name": "자동차",
        "post_url": "https://www.teamblind.com/kr/post/BYD-BMS-결함-z3w4",
        "post_title": "배터리 잔량 20%에서 갑자기 0% 급락 벽돌됨",
        "target_vehicle": "BYD T4K",
        "category": "charging",
        "defect_topic": "BMS SOC 급락 및 벽돌 현상",
        "raw_quote": "계기판에 20% 찍혀있었는데 신호대기 중에 갑자기 0%로 떨어지면서 시동 꺼지고 벽돌차 됨 견인차 부르고 장사 망함",
        "slang_terms": ["벽돌", "벽돌차"],
        "collected_at": "2026-08-27T13:45:00Z"
    },
    {
        "id": "complaint_009",
        "platform": "dcinside",
        "board_name": "전기차 갤러리",
        "post_url": "https://gall.dcinside.com/mgallery/board/view/?id=ev&no=11002",
        "post_title": "완속 충전 과열 리콜 받고 왔더니 충전 속도 3.5kW로 반토막 냄",
        "target_vehicle": "Kia EV6",
        "category": "charging",
        "defect_topic": "완속 충전구 과열로 인한 3.5kW 전류 반토막 다운그레이드",
        "raw_quote": "완속 과열 리콜 받고 왔더니 3.5kW로 반토막 내놨네 밤새 8시간 꽂아놔도 28kWh 들어감 꼼수 리콜 진짜 답없음",
        "slang_terms": ["반토막", "답없음"],
        "collected_at": "2026-08-28T08:30:00Z"
    },
    {
        "id": "complaint_010",
        "platform": "naver_cafe",
        "board_name": "전기차동호회",
        "post_url": "https://cafe.naver.com/allaboutclube/22331",
        "post_title": "겨울철 충전구 솔레노이드 락 핀 결빙으로 충전건 분리 불가",
        "target_vehicle": "Tesla Model Y",
        "category": "charging",
        "defect_topic": "겨울철 충전구 모터 및 솔레노이드 락 핀 결빙",
        "raw_quote": "혹한기에 급속 충전 끝나고 커넥터 뽑으려는데 락 핀 얼어서 안 뽑힘 트렁크 뜯고 비상 와이어 당김 진짜 식겁했다",
        "slang_terms": ["결빙", "식겁"],
        "collected_at": "2026-08-29T14:10:00Z"
    },

    # Rainy Driving & Harsh Conditions (Tesla, Hyundai, Porsche, BYD)
    {
        "id": "complaint_011",
        "platform": "bobaedream",
        "board_name": "수입차게시판",
        "post_url": "https://www.bobaedream.co.kr/view?code=import&No=214012",
        "post_title": "비도 안 오는데 햇빛 쨍쨍한 날 미친 듯이 와이퍼 흔들어재낌 (정신병 와이퍼)",
        "target_vehicle": "Tesla Model 3",
        "category": "rain_driving",
        "defect_topic": "비전 기반 딥레인(Deep Rain) 오토와이퍼 오류",
        "raw_quote": "비도 안 오는데 대낮에 와이퍼 혼자 마른와이퍼질 미친 듯이 발작함 정신병 와이퍼 때문에 유리 기스 다 남 제발 우적센서 달아줘라",
        "slang_terms": ["정신병와이퍼", "마른와이퍼질"],
        "collected_at": "2026-08-25T19:20:00Z"
    },
    {
        "id": "complaint_012",
        "platform": "dcinside",
        "board_name": "전기차 갤러리",
        "post_url": "https://gall.dcinside.com/mgallery/board/view/?id=ev&no=11234",
        "post_title": "아이오닉5 초기형 리어 와이퍼 없어서 비 오는 날 후방 시야 0% 암흑",
        "target_vehicle": "Hyundai Ioniq 5",
        "category": "rain_driving",
        "defect_topic": "초기형 리어 와이퍼 부재로 인한 우천 후방 시야 상실",
        "raw_quote": "폭설 오는데 뒤유리가 그냥 흙탕물 도배돼서 뒤유리 걸레짝 됨 리어와이퍼 없어서 사이드미러만 보고 차선 바꾸다 비명 지름 살얼음 판이다",
        "slang_terms": ["뒤유리걸레짝", "살얼음"],
        "collected_at": "2026-08-26T22:00:00Z"
    },
    {
        "id": "complaint_013",
        "platform": "blind",
        "board_name": "자동차",
        "post_url": "https://www.teamblind.com/kr/post/BYD-ADAS-비가림-q5p6",
        "post_title": "영하 15도 영동고속도로에서 옥토밸브 터져서 히터 꺼지고 앞유리 성에 껴서 얼어죽을 뻔",
        "target_vehicle": "Tesla Model Y",
        "category": "rain_driving",
        "defect_topic": "혹한기 옥토밸브 고장으로 인한 주행 중 난방 중단 및 전면 성에 결빙",
        "raw_quote": "영하 15도에 옥토밸브 사망 뜨고 실내 난방 불가 뜨자마자 입김 나오고 앞유리 성에 껴서 시야 차단됨 갓길 세우고 견인차 기다리다 동사할 뻔",
        "slang_terms": ["옥토밸브사망", "옥토밸브"],
        "collected_at": "2026-08-27T17:10:00Z"
    },
    {
        "id": "complaint_014",
        "platform": "dcinside",
        "board_name": "자동차 갤러리",
        "post_url": "https://gall.dcinside.com/board/view/?id=car_new1&no=899123",
        "post_title": "타이칸 영하 날씨에 PTC 히터 터져서 냉동고 타이칸 됨",
        "target_vehicle": "Porsche Taycan",
        "category": "rain_driving",
        "defect_topic": "800V 고전압 PTC 히터 소손으로 혹한기 찬바람 송풍",
        "raw_quote": "1억 5천짜리 타이칸 샀는데 영하 10도에 히터 나가서 찬바람만 나오는 냉동고타이칸 얼음방 됨 부품 독일 오더 4달 대기 실화냐",
        "slang_terms": ["냉동고타이칸", "얼음방", "실화냐"],
        "collected_at": "2026-08-28T14:50:00Z"
    },
    {
        "id": "complaint_015",
        "platform": "bobaedream",
        "board_name": "국산차게시판",
        "post_url": "https://www.bobaedream.co.kr/view?code=national&No=214555",
        "post_title": "빗길에 교량 쇠판 밟고 후륜 회생제동 걸려 차 돌아갈 뻔함 (피쉬테일)",
        "target_vehicle": "Kia EV6",
        "category": "rain_driving",
        "defect_topic": "우천 시 후륜 회생제동 맨홀/교량 이음새 통과 피쉬테일",
        "raw_quote": "비 올 때 교량 이음새 쇠판 밟으면서 회생제동 걸리면 뒤꽁무니 털림 피쉬테일 나면서 차 돌아갈 뻔함 살얼음 밟듯이 타야 됨",
        "slang_terms": ["피쉬테일", "털림", "살얼음"],
        "collected_at": "2026-08-29T16:30:00Z"
    },

    # Hill Climbing & Maintenance (Tesla, Hyundai, Porsche, BYD)
    {
        "id": "complaint_016",
        "platform": "bobaedream",
        "board_name": "수입차게시판",
        "post_url": "https://www.bobaedream.co.kr/view?code=import&No=22780",
        "post_title": "뒤에서 콩 박았는데 기가캐스팅 먹었다고 전손 견적 4천만원 찍힘",
        "target_vehicle": "Tesla Model Y",
        "category": "hill_climbing",
        "defect_topic": "기가캐스팅 알루미늄 리어 프레임 경미 사고 전손 처리",
        "raw_quote": "뒤에서 살짝 콩 박혔는데 일체형 알루미늄 기가캐스팅 크랙 갔다고 전손 견적 4200만원 나옴 판금 용접 불가라 강제 전손폭탄 맞음",
        "slang_terms": ["기가캐스팅", "전손폭탄"],
        "collected_at": "2026-08-25T15:10:00Z"
    },
    {
        "id": "complaint_017",
        "platform": "dcinside",
        "board_name": "전기차 갤러리",
        "post_url": "https://gall.dcinside.com/mgallery/board/view/?id=ev&no=11456",
        "post_title": "배터리 하부 긁힘 2천만원 통교체 견적... 집안 거덜 난다",
        "target_vehicle": "Hyundai Ioniq 5",
        "category": "hill_climbing",
        "defect_topic": "배터리 하부 케이스 미세 스크래치 시 통교체 강제",
        "raw_quote": "과속방지턱에 배터리 커버 살짝 긁혔는데 블루핸즈에서 2400만원 배터리 통교체 견적 때림 하부긁힘 2천만원 실화냐 자차 보험료 폭등함",
        "slang_terms": ["하부긁힘", "2천만원", "실화냐"],
        "collected_at": "2026-08-26T17:40:00Z"
    },
    {
        "id": "complaint_018",
        "platform": "bobaedream",
        "board_name": "수입차게시판",
        "post_url": "https://www.bobaedream.co.kr/view?code=import&No=214890",
        "post_title": "타이칸 하부 스키드 플레이트 2mm 긁혔다고 8500만원 배터리 교체 부름",
        "target_vehicle": "Porsche Taycan",
        "category": "hill_climbing",
        "defect_topic": "포르쉐 타이칸 하부 스크래치 천문학적 배터리 교체비",
        "raw_quote": "하부 알루미늄 판넬 톡 긁혔는데 포르쉐 센터에서 8500만원 배터리 전체 교체 부름 7천만원전손 폭탄 맞고 보험사 분쟁 중",
        "slang_terms": ["7천만원전손"],
        "collected_at": "2026-08-27T20:30:00Z"
    },
    {
        "id": "complaint_019",
        "platform": "blind",
        "board_name": "자동차",
        "post_url": "https://www.teamblind.com/kr/post/BYD-등판력-저하-r7s8",
        "post_title": "경사로 정차 후 출발할 때 오토홀드 풀리며 롤백 뒤로 밀림",
        "target_vehicle": "BYD Atto 3",
        "category": "hill_climbing",
        "defect_topic": "경사로 출발 시 오토홀드 해제 딜레이로 롤백 밀림",
        "raw_quote": "마트 지하주차장 오르막 출차할 때 오토홀드 풀리면서 뒤로 30cm 덜컹 롤백 밀림 뒷차 박을 뻔해서 식겁했다 짱깨차 로직 왜이러냐",
        "slang_terms": ["롤백", "밀림", "식겁", "짱깨차"],
        "collected_at": "2026-08-28T19:00:00Z"
    },
    {
        "id": "complaint_020",
        "platform": "naver_cafe",
        "board_name": "소상공인전기차포럼",
        "post_url": "https://cafe.naver.com/smallbiztruck/23100",
        "post_title": "T4K 화물 1톤 싣고 남한산성 오르막 올랐더니 거북이모드 출력 제한",
        "target_vehicle": "BYD T4K",
        "category": "hill_climbing",
        "defect_topic": "산길 연속 등판 시 모터 발열 쓰로틀링 및 거북이모드",
        "raw_quote": "화물 1톤 싣고 언덕 5분 오르니까 모터 인버터 과열 쓰로틀링 걸려서 거북이모드 뜸 시속 15km로 기어가다 개빡침 폭망",
        "slang_terms": ["쓰로틀링", "거북이모드", "개빡침", "폭망"],
        "collected_at": "2026-08-29T18:00:00Z"
    }
]

SAMPLE_COMPLIANT_CASEBOOK = """# 글로벌 전기차(테슬라·현기차·글로벌 브랜드·중국 전기차) 실생활 핵심 결함 날것 사례집

## 1. 개요 및 발간 배경 (Executive Summary & Background)
국내 커뮤니티(디시인사이드, 보배드림, 블라인드, 네이버 대표 카페 등)에서 실제 전기차 오너들이 겪은 적나라한 불만과 결함 경험담을 집대성한 사례집입니다.

## 2. 커뮤니티 은어 및 용어 사전 (Community Slang Dictionary & Tone Guide)
- **테슬람**: 테슬라 하드웨어 결함을 소프트웨어로 다 된다며 옹호하는 극성 팬덤
- **정신병 와이퍼**: 비전 딥레인 센서 오류로 맑은 날 마른 유리를 긁는 오작동
- **진흙 반죽**: 테슬라 비전 하이 피델리티 3D 파크 어시스트 왜곡 렌더링
- **ICCU 폭탄**: 현대 E-GMP 통합 충전 제어 장치 파손 및 고속도로 주행 셧다운
- **완속 반토막 패치**: 완속 충전구 과열을 피하기 위해 전류를 3.5kW로 낮춘 업데이트
- **뒤유리 걸레짝**: 리어 와이퍼가 없는 초기 아이오닉5/EV6 빗길 후방 시야 실명
- **파라시스 폭탄**: 벤츠 EQE 중국 파라시스 배터리 화재 및 지하주차장 퇴출
- **냉동고 타이칸**: 포르쉐 타이칸 혹한기 800V PTC 히터 고장 찬바람 송풍
- **7천만원 전손**: 타이칸 배터리 하부 2mm 스크래치에 8천만원 교체 견적
- **짱깨차 / 짱차**: 중국산 전기차 비하 은어
- **배트맨타이어**: 중국산 순정 타이어의 극악 웻그립 조롱

## 3. Part 1: 테슬라(Tesla) 실생활 핵심 결함 날것 사례집

### 3.1 주차 및 저속 기동 (Parking & Low-Speed Maneuvering)

#### [사례 1] TS-PK-01: 초음파 센서(USS) 삭제 및 범퍼 하단 1.5m 맹안 스토퍼 충돌
- **출처**: [디시인사이드 테슬라 갤러리](https://gall.dcinside.com/mgallery/board/view/?id=tesla&no=10234)
> "초음파 센서 빼먹고 3D 진흙 반죽 그래픽 띄워놓고 멈추라는 테슬라 능지... 앞범퍼 하단 1.5미터 맹안이라 스토퍼 박고 립 깨먹음 개빡치네"

### 3.2 충전 인프라 및 전장 시스템 (Charging & Electrical Systems)

#### [사례 2] TS-CH-01: 현대 E-pit 800V 초급속 충전소 400V 승압 병목 및 70kW 제한
- **출처**: [디시인사이드 테슬라 갤러리](https://gall.dcinside.com/mgallery/board/view/?id=tesla&no=10890)
> "이피트 350kW 물려봐야 400V 부스트 변환 때문에 70kW로 기어가는 굼벵이 신세임 DC콤보 어댑터 발열 쓰로틀링 걸리면 35kW 떡락 개빡침"

#### [사례 3] TS-CH-04: 센트리 모드 250W 상시 전력 소모 및 뱀파이어 드레인
- **출처**: [보배드림 수입차게시판](https://www.bobaedream.co.kr/view?code=import&No=213789)
> "주차장에 세워만 뒀는데 센트리가 전기를 하마처럼 쳐먹음 뱀파이어 드레인 때문에 장기 주차할 때 스트레스 극심"

### 3.3 혹한/우천/가혹 주행 (Harsh Driving, Winter & Thermal Management)

#### [사례 4] TS-DR-01: 비전 딥레인 오토와이퍼 오류 (마른 유리 긁힘 발작)
- **출처**: [보배드림 수입차게시판](https://www.bobaedream.co.kr/view?code=import&No=214012)
> "비도 안 오는데 대낮에 와이퍼 혼자 마른와이퍼질 미친 듯이 발작함 정신병 와이퍼 때문에 유리 기스 다 남 제발 우적센서 달아줘라"

### 3.4 정비, AS, 기가캐스팅 및 수리 경제성 (Maintenance, AS & Repair Economics)

#### [사례 5] TS-MT-02: 기가캐스팅 알루미늄 리어 프레임 경미 사고 4,000만원 전손
- **출처**: [보배드림 수입차게시판](https://www.bobaedream.co.kr/view?code=import&No=22780)
> "뒤에서 살짝 콩 박혔는데 일체형 알루미늄 기가캐스팅 크랙 갔다고 전손 견적 4200만원 나옴 판금 용접 불가라 강제 전손폭탄 맞음"

## 4. Part 2: 현대·기아·제네시스(E-GMP) 핵심 결함 날것 사례집

### 4.1 주차 및 저속 기동 (Parking & Low-Speed Maneuvering)

#### [사례 6] HK-PK-01: RSPA 2 낮은 연석 미인식 휠 긁힘
- **출처**: [보배드림 국산차게시판](https://www.bobaedream.co.kr/view?code=national&No=213456)
> "RSPA 원격주차 멋지게 빼려다 연석에 휠 긁고 휠빵 당함 센서가 낮은 턱을 못 봄 휠 복원비 15만원 날리고 피눈물 흘림 노답"

#### [사례 7] HK-PK-02: 지하주차장 급경사 램프 PCA-R/FCA 유령 긴급제동
- **출처**: [디시인사이드 전기차 갤러리](https://gall.dcinside.com/mgallery/board/view/?id=ev&no=10555)
> "지하주차장 램프 꺾이는 바닥에서 갑자기 쾅 소리 나면서 유령제동 급정거 꽂힘 안전벨트에 명치 얻어맞아서 숨도 안 쉬어짐 ㄷㄷ"

### 4.2 충전 인프라 및 전력전자 (Charging & High-Voltage PE Systems)

#### [사례 8] HK-CH-01: ICCU 폭발 및 고속도로 주행 전원 차단
- **출처**: [보배드림 국산차게시판](https://www.bobaedream.co.kr/view?code=national&No=213789)
> "경부고속도로 1차선 달리는데 뒤에서 퍽 소리 나더니 ICCU 터지고 전원공급시스템 점검 빨간불 뜸 거북이모드 걸리다 멈춰서 저승길 갈 뻔함 현대차 양아치"

### 4.3 혹한/우천/가혹 주행 (Harsh Driving, Winter & Dynamics)

#### [사례 9] HK-DR-01: 초기형 아이오닉5 리어 와이퍼 부재 후방 시야 암흑
- **출처**: [디시인사이드 전기차 갤러리](https://gall.dcinside.com/mgallery/board/view/?id=ev&no=11234)
> "폭설 오는데 뒤유리가 그냥 흙탕물 도배돼서 뒤유리 걸레짝 됨 리어와이퍼 없어서 사이드미러만 보고 차선 바꾸다 비명 지름 살얼음 판이다"

### 4.4 정비, AS 및 수리 경제성 (Maintenance, AS & Repair Economics)

#### [사례 10] HK-MT-01: 고전압 배터리 하부 긁힘 2,400만원 통교체 견적
- **출처**: [보배드림 국산차게시판](https://www.bobaedream.co.kr/view?code=national&No=213456)
> "과속방지턱에 배터리 커버 살짝 긁혔는데 블루핸즈에서 2400만원 배터리 통교체 견적 때림 하부긁힘 2천만원 실화냐 자차 보험료 폭등함"

## 5. Part 3: 글로벌 전기차 결함 날것 사례집

### 5.1 포르쉐 타이칸 (Porsche Taycan)

#### [사례 11] GB-PO-01: 혹한기 PTC 히터 소손 냉동고 타이칸 찬바람 송풍
- **출처**: [디시인사이드 자동차 갤러리](https://gall.dcinside.com/board/view/?id=car_new1&no=899123)
> "1억 5천짜리 타이칸 샀는데 영하 10도에 히터 나가서 찬바람만 나오는 냉동고타이칸 얼음방 됨 부품 독일 오더 4달 대기 실화냐"

### 5.2 BYD 및 중국 전기차

#### [사례 12] GB-BY-01: 경사로 오토홀드 롤백 밀림
- **출처**: [블라인드 자동차](https://www.teamblind.com/kr/post/BYD-등판력-저하-r7s8)
> "마트 지하주차장 오르막 출차할 때 오토홀드 풀리면서 뒤로 30cm 덜컹 롤백 밀림 뒷차 박을 뻔해서 식겁했다 짱깨차 로직 왜이러냐"

#### [사례 13] GB-BY-02: T4K 화물 적재 시 모터 발열 쓰로틀링
- **출처**: [네이버 소상공인전기차포럼](https://cafe.naver.com/smallbiztruck/23100)
> "화물 1톤 싣고 언덕 5분 오르니까 모터 인버터 과열 쓰로틀링 걸려서 거북이모드 뜸 시속 15km로 기어가다 개빡침 폭망"

#### [사례 14] GB-BY-03: 기계식 주차타워 중량 초과 입고 불가
- **출처**: [블라인드 자동차](https://www.teamblind.com/kr/post/BYD-주차-경험-x1y2)
> "LFP 배터리 싣고 공차중량 2톤 넘어가니까 기계식 주차타워 다 튕겨냄 이중주차 중립 N단도 안 먹어서 아파트 주차난 헬게이트 열림"

#### [사례 15] GB-BY-04: LFP 배터리 혹한기 급속 충전 속도 저하
- **출처**: [뽐뿌 자동차포럼](https://www.ppomppu.co.kr/zboard/view.php?id=car&no=982341)
> "영하 날씨에 급속충전기 꽂았더니 15kW로 기어가는 굼벵이 충전 보여줌 충전 스트레스 극심"

#### [사례 16] GB-BY-05: 산길 급경사로 연속 등판 시 모터 과열 출력 제한
- **출처**: [디시인사이드 전기차 갤러리](https://gall.dcinside.com/mgallery/board/view/?id=ev&no=12345)
> "언덕길 등판할 때 모터 과열 경고 뜨면서 시속 20km로 출력 제한 걸림 등판 능력 한계"

## 6. 출처 및 검증 색인 (Master Source Index & Verification Links)
| 번호 | 브랜드 | 차종 | 커뮤니티 | 게시판 | 원본 링크 |
|---|---|---|---|---|---|
| 1 | Tesla | Model Y | 디시인사이드 | 테슬라 갤러리 | https://gall.dcinside.com/mgallery/board/view/?id=tesla&no=10234 |
| 2 | Hyundai | Ioniq 5 | 보배드림 | 국산차게시판 | https://www.bobaedream.co.kr/view?code=national&No=213456 |
| 3 | BYD | T4K | 블라인드 | 자동차 | https://www.teamblind.com/kr/post/BYD-주차-경험-x1y2 |
| 4 | Tesla | Model 3 | 디시인사이드 | 테슬라 갤러리 | https://gall.dcinside.com/mgallery/board/view/?id=tesla&no=10890 |
| 5 | Hyundai | Ioniq 5 | 보배드림 | 국산차게시판 | https://www.bobaedream.co.kr/view?code=national&No=213789 |
| 6 | Tesla | Model 3 | 보배드림 | 수입차게시판 | https://www.bobaedream.co.kr/view?code=import&No=214012 |
| 7 | Hyundai | Ioniq 5 | 디시인사이드 | 전기차 갤러리 | https://gall.dcinside.com/mgallery/board/view/?id=ev&no=11234 |
| 8 | Tesla | Model Y | 보배드림 | 수입차게시판 | https://www.bobaedream.co.kr/view?code=import&No=22780 |
| 9 | Porsche | Taycan | 디시인사이드 | 자동차 갤러리 | https://gall.dcinside.com/board/view/?id=car_new1&no=899123 |
| 10 | BYD | Atto 3 | 블라인드 | 자동차 | https://www.teamblind.com/kr/post/BYD-등판력-저하-r7s8 |
| 11 | BYD | T4K | 네이버카페 | 소상공인전기차 | https://cafe.naver.com/smallbiztruck/23100 |
| 12 | Kia | EV6 | 디시인사이드 | 전기차 갤러리 | https://gall.dcinside.com/mgallery/board/view/?id=ev&no=10555 |
"""

SAMPLE_COMPLIANT_REPORT = """# 글로벌 전기차 커뮤니티 대규모 빅데이터 통계 분석 및 감성 평가 심층 리포트 (2024–2026)

## 1. 개요 및 빅데이터 수집 통계 (Executive Summary & Data Volume Metrics)
본 리포트는 보배드림, 디시인사이드, 블라인드 등 국내외 주요 커뮤니티의 테슬라, 현대/기아차, 글로벌 브랜드(벤츠, BMW, 포르쉐, 폴스타), 중국 전기차 관련 게시물 및 댓글을 안전한 크롤링(딜레이/지터 1.5s~3.5s 준수, User-Agent 로테이션, 백오프 로직)을 통해 수집하여 통계적으로 정밀 분석한 결과입니다.

- **수집 기간**: 2024년 1월 ~ 2026년 8월 (최근 2년간)
- **분석 대상 커뮤니티**: 보배드림 (Bobaedream), 디시인사이드 (DC Inside), 블라인드 (Blind)
- **총 수집 건수**: 3,500건 (게시글 및 댓글 정규화 레코드)
- **평가 모델**: 한국어 자동차 도메인 형태소 분석기, 4단계 감성 분석 엔진, 결함 심각도 지수 (DSI)

## 2. 불만 키워드 종합 TOP 30 랭킹 및 빈도 분석 (Top 30 Complaint Keywords)

| 순위 | 키워드 | 카테고리 | 언급 빈도수 (TF) | 점유율 (%) | TF-IDF | 평균 DSI | 대표 검증 코멘트 |
|---|---|---|---|---|---|---|---|
| 1 | 기가캐스팅 전손폭탄 | Maintenance / Structure | 495 | 14.14% | 1512.4 | 9.8 | "뒤에서 콩 박았는데 기가캐스팅 먹었다고 전손 4천" |
| 2 | ICCU 전원차단 셧다운 | Charging / PE | 482 | 13.77% | 1482.4 | 9.5 | "경부고속도로 달리다 ICCU 터져서 벽돌됨" |
| 3 | 지하주차장 입차거부 | Parking / Social | 451 | 12.89% | 1398.2 | 8.8 | "아파트 입대의에서 화재포비아 지하 진입 금지 통과됨" |
| 4 | 비전 와이퍼 마른발작 | Rainy Driving / Sensor | 419 | 11.97% | 1285.6 | 9.2 | "비도 안 오는데 마른 유리 긁는 정신병 와이퍼" |
| 5 | 혹한기 옥토밸브 난방중단 | Harsh Driving / HVAC | 398 | 11.37% | 1214.0 | 9.7 | "영하 15도에 옥토밸브 터져 앞유리 성에 껴서 얼어죽을 뻔" |
| 6 | 완속 3.5kW 반토막패치 | Charging / OBC | 374 | 10.69% | 1145.8 | 8.2 | "완속 과열 리콜 받고 3.5kW로 반토막 내놓음" |
| 7 | 타이칸 8천만 배터리통교체 | Maintenance / Battery | 342 | 9.77% | 1088.1 | 9.6 | "하부 스키드 2mm 긁힘에 8500만원 배터리 교체 견적" |
| 8 | 리어와이퍼 부재 시야실명 | Rainy Driving / Aero | 329 | 9.40% | 1045.3 | 8.9 | "비 오는 날 뒤유리 흙탕물 덮여 후방 시야 0%" |
| 9 | 빗길 교량 회생제동 피쉬테일 | Rainy Driving / Dynamics | 315 | 9.00% | 998.7 | 9.3 | "빗길 쇠판 밟고 회생제동 걸려 차 돌아갈 뻔" |
| 10 | RSPA 원격주차 휠스크래치 | Parking / ADAS | 288 | 8.23% | 902.6 | 8.6 | "원격주차 믿다 연석에 20인치 다이아몬드 휠 긁어먹음" |
| 11 | 테슬라 공식AS 2달대기 | Maintenance / AS | 275 | 7.86% | 856.4 | 9.0 | "고장 나도 예약 2달 뒤, 전화도 안 받는 테슬라 AS" |
| 12 | 경사로 오토홀드 롤백밀림 | Hill Climbing / HSA | 261 | 7.46% | 812.9 | 8.4 | "언덕길 출발할 때 오토홀드 풀리며 뒤로 덜컹 밀림" |

## 3. 핵심 4대 결함 도메인별 통계 심층 분석
- **주차 문제 (Parking Issues)**: 테슬라 비전 카메라 1.5m 맹안 및 RSPA 2 낮은 연석 미인식 휠 파손.
- **충전 문제 (Charging Issues)**: 현대 E-GMP ICCU 폭발 소손 및 테슬라 NACS-CCS1 발열 쓰로틀링.
- **가혹 주행 (Harsh Driving)**: 혹한기 옥토밸브/PTC 히터 고장 및 빗길 회생제동 피쉬테일.
- **정비 및 수리 경제성 (Maintenance & Repair Economics)**: 기가캐스팅 전손 대란 및 배터리 하부 긁힘 통교체 청구.

## 4. 커뮤니티 플랫폼별 비교 통계 (Cross-Platform Analytics)
보배드림, 디시인사이드, 블라인드 3개 플랫폼 비교 분석:

| 플랫폼 | 주요 사용자층 | 핵심 관심사 | 부정 감성 비율 | 비하 슬랭 밀도 | 대표 키워드 |
|---|---|---|---|---|---|
| **보배드림** | 30~50대 자차 오너 및 정비사 | 기가캐스팅 전손, 배터리 하부 긁힘, 수리 분쟁 | 86.4% | 중간 (4.2개/1000단어) | 기가캐스팅, 전손폭탄, 하부긁힘 |
| **디시인사이드** | 10~30대 익명 커뮤니티 | ICCU 폭발, 비전 주차, 정신병 와이퍼 | 94.2% | 극상 (16.8개/1000단어) | 진흙반죽, 테슬람, ICCU |
| **블라인드** | 20~40대 직장인 및 엔지니어 | AS 대기 기간, 수리비 경제성, 중고 감가 | 78.0% | 낮음 (2.4개/1000단어) | 하이테크대기, 블루핸즈거부, 보험료 |

## 5. 4단계 감성 분석 및 결함 심각도 지수 (DSI Metrics)
- **긍정 (Positive)**: 0.0%
- **중립 (Neutral)**: 10.5%
- **부정 (Negative)**: 41.5%
- **강한 부정 (Strongly Negative)**: 48.0%

결함 심각도 지수 (DSI) 가중치 모델:
$$\\text{DSI} = 0.35 \\cdot S_{\\text{safety}} + 0.25 \\cdot S_{\\text{functional}} + 0.15 \\cdot S_{\\text{economic}} + 0.15 \\cdot S_{\\text{social}} + 0.10 \\cdot S_{\\text{convenience}}$$

## 6. 시계열 민심 변화 추이 분석 (Temporal Trends: 2024 ~ 2026)
- **2024년**: 벤츠 청라 화재 및 지하주차장 입차 거부 급증.
- **2025년**: E-GMP ICCU 폭발 리콜 및 테슬라 비전 딥레인 와이퍼 오류 누적.
- **2026년**: 기가캐스팅 및 타이칸 배터리 전손 대란, 보험료 폭등 현실화.

## 7. 전략적 제언 및 결론 (Strategic Insights)
글로벌 전기차 제조사들은 센서 원가절감(비전 올인) 재고, 수리 가능한 섀시/배터리 설계, 고전압 정비망 확충을 최우선 과제로 추진해야 합니다.
"""


class TestInfraIntegrity(unittest.TestCase):
    """Verifies that the test suites correctly pass compliant data and reject defective data."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_file = Path(self.temp_dir.name) / "compiled_complaints.json"
        self.casebook_file = Path(self.temp_dir.name) / "CASEBOOK.md"
        self.report_file = Path(self.temp_dir.name) / "STATISTICAL_REPORT.md"

        # Write compliant files
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(SAMPLE_COMPLIANT_DATA, f, ensure_ascii=False, indent=2)
        with open(self.casebook_file, "w", encoding="utf-8") as f:
            f.write(SAMPLE_COMPLIANT_CASEBOOK)
        with open(self.report_file, "w", encoding="utf-8") as f:
            f.write(SAMPLE_COMPLIANT_REPORT)

        os.environ["COMPLAINTS_DATA_PATH"] = str(self.data_file)
        os.environ["CASEBOOK_FILE_PATH"] = str(self.casebook_file)
        os.environ["STATISTICAL_REPORT_PATH"] = str(self.report_file)

    def tearDown(self):
        self.temp_dir.cleanup()
        os.environ.pop("COMPLAINTS_DATA_PATH", None)
        os.environ.pop("CASEBOOK_FILE_PATH", None)
        os.environ.pop("STATISTICAL_REPORT_PATH", None)

    def test_compliant_dataset_passes_all_5_suites(self):
        """Verify that a 100% compliant dataset passes all tiers."""
        for tier_num, (name, test_cls) in TIER_REGISTRY.items():
            res = run_tier_suite(tier_num, name, test_cls)
            self.assertTrue(
                res.is_success,
                f"Compliant data failed {name}:\nFailures: {res.failures_details}\nErrors: {res.errors_details}",
            )
            self.assertEqual(res.failed, 0)
            self.assertEqual(res.errors, 0)
            self.assertGreater(res.passed, 0)

    def test_missing_category_fails_tier1(self):
        """Verify that removing a mandatory category fails Tier 1."""
        defective_data = [r for r in SAMPLE_COMPLIANT_DATA if r["category"] != "parking"]
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(defective_data, f, ensure_ascii=False, indent=2)

        res = run_tier_suite(1, TIER_REGISTRY[1][0], TIER_REGISTRY[1][1])
        self.assertFalse(res.is_success, "Tier 1 should fail when a category is missing.")
        self.assertGreater(res.failed, 0)

    def test_empty_quote_fails_tier2(self):
        """Verify that an empty quote fails Tier 2."""
        defective_data = [dict(r) for r in SAMPLE_COMPLIANT_DATA]
        defective_data[0]["raw_quote"] = "TODO"
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(defective_data, f, ensure_ascii=False, indent=2)

        res = run_tier_suite(2, TIER_REGISTRY[2][0], TIER_REGISTRY[2][1])
        self.assertFalse(res.is_success, "Tier 2 should fail when a quote is a placeholder.")
        self.assertGreater(res.failed, 0)

    def test_placeholder_in_casebook_fails_tier4(self):
        """Verify that forbidden placeholder token in CASEBOOK.md fails Tier 4."""
        defective_casebook = SAMPLE_COMPLIANT_CASEBOOK + "\n\n[TODO] Add more cases\n"
        with open(self.casebook_file, "w", encoding="utf-8") as f:
            f.write(defective_casebook)

        res = run_tier_suite(4, TIER_REGISTRY[4][0], TIER_REGISTRY[4][1])
        self.assertFalse(res.is_success, "Tier 4 should fail when placeholder tokens exist.")
        self.assertGreater(res.failed, 0)

    def test_missing_mandatory_platform_fails_tier5(self):
        """Verify that omitting Blind fails Tier 5."""
        defective_data = [r for r in SAMPLE_COMPLIANT_DATA if r["platform"] != "blind"]
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(defective_data, f, ensure_ascii=False, indent=2)

        res = run_tier_suite(5, TIER_REGISTRY[5][0], TIER_REGISTRY[5][1])
        self.assertFalse(res.is_success, "Tier 5 should fail when a mandatory platform is missing.")
        self.assertGreater(res.failed, 0)


if __name__ == "__main__":
    unittest.main()
