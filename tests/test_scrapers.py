"""
Unit and Integration Tests for Scraper Infrastructure and Multi-Platform Extraction.
Covers:
- Common Utilities (SafeHttpClient, headers, delays, encodings, ComplaintRecord schema)
- Bobaedream Scraper (Multi-board list, search, post, comments, classification)
- DC Inside Scraper (Major/minor galleries, DOM list, post, AJAX comments, classification)
- Blind Scraper (Next.js SSR JSON extraction, verified company badges, classification)
- Cafe Forum Miner (Pomppu, Clien, Naver Cafe normalization)
- Compiled Database Integrity
"""

import json
import os
import sys
import unittest

# Ensure project root in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.exists(os.path.join(PROJECT_ROOT, "scrapers")):
    parent = os.path.dirname(PROJECT_ROOT)
    if os.path.exists(os.path.join(parent, "scrapers")):
        PROJECT_ROOT = parent

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scrapers.common_utils import (
    ComplaintRecord,
    SafeHttpClient,
    clean_html_text,
    encode_euc_kr_query,
    extract_slang_terms,
    get_random_headers,
    load_complaints_json,
    polite_delay,
    robust_decode,
    VALID_PLATFORMS,
    VALID_CATEGORIES,
    VALID_SEVERITIES,
)
from scrapers.bobaedream_scraper import BobaedreamScraper
from scrapers.dcinside_scraper import DCInsideScraper
from scrapers.blind_scraper import BlindScraper
from scrapers.cafe_forum_miner import CafeForumMiner
from scripts.validate_data import validate_database


class TestCommonUtils(unittest.TestCase):
    """Test safe HTTP client, headers, encoding helpers, and ComplaintRecord schema."""

    def test_user_agent_and_client_init(self):
        client = SafeHttpClient(min_delay=0.01, max_delay=0.02)
        ua = client.get_random_user_agent()
        self.assertTrue(len(ua) > 10)
        self.assertIn("Mozilla", ua)

    def test_random_headers(self):
        headers = get_random_headers(referer="https://example.com")
        self.assertIn("User-Agent", headers)
        self.assertIn("Accept-Language", headers)
        self.assertEqual(headers.get("Referer"), "https://example.com")

    def test_euc_kr_encoding(self):
        params = {"keyword": "아토3", "searchName": "커뮤니티"}
        encoded = encode_euc_kr_query(params)
        self.assertIsInstance(encoded, bytes)
        self.assertIn(b"keyword=", encoded)

    def test_robust_decode(self):
        sample_text = "비야디 전기차 결함"
        utf8_bytes = sample_text.encode("utf-8")
        euckr_bytes = sample_text.encode("euc-kr")

        self.assertEqual(robust_decode(utf8_bytes, "utf-8"), sample_text)
        self.assertEqual(robust_decode(euckr_bytes, "euc-kr"), sample_text)
        self.assertEqual(robust_decode(euckr_bytes), sample_text)

    def test_clean_html_text(self):
        raw = "<div><p>테스트 &amp; <b>내용</b></p><p>다음 줄</p><script>var a=1;</script></div>"
        cleaned = clean_html_text(raw)
        self.assertEqual(cleaned, "테스트 & 내용\n다음 줄")

    def test_complaint_record_validation_valid(self):
        rec = ComplaintRecord(
            id="TEST_001",
            platform="blind",
            board_name="블라인드 자동차",
            post_url="https://www.teamblind.com/kr/post/123",
            post_title="테스트 제목",
            target_vehicle="BYD Atto 3",
            category="parking",
            defect_topic="3D 어라운드뷰 왜곡 및 프레임 드랍으로 인한 휠/차체 긁힘",
            raw_quote="어라운드뷰 화면만 믿고 가다가 휠 긁어먹었네요.",
            slang_terms=["어안렌즈"],
            severity="functional_failure",
            platform_metadata={"author_type": "blind_verified_company", "author_badge": "현대자동차"}
        )
        is_valid, errors = rec.validate()
        self.assertTrue(is_valid, f"Validation errors: {errors}")
        self.assertEqual(len(errors), 0)

    def test_complaint_record_validation_invalid(self):
        bad_rec = ComplaintRecord(
            id="",
            platform="invalid_platform",
            board_name="",
            post_url="",
            post_title="",
            target_vehicle="",
            category="invalid_category",
            defect_topic="",
            raw_quote="sh",
            severity="bad_severity"
        )
        is_valid, errors = bad_rec.validate()
        self.assertFalse(is_valid)
        self.assertTrue(len(errors) >= 5)

    def test_slang_extraction(self):
        slang_dict = {
            "배트맨 타이어": {"meaning": "Atlas Batman A51"},
            "황천길": {"meaning": "Death"},
            "짱깨차": {"meaning": "Chinese car"}
        }
        text = "순정 배트맨 타이어 끼고 비 오는 날 달리면 황천길 갑니다. 짱깨차 수준."
        found = extract_slang_terms(text, slang_dict)
        self.assertEqual(found, ["배트맨 타이어", "짱깨차", "황천길"])


class TestBobaedreamScraper(unittest.TestCase):
    """Test Bobaedream scraper parsing and multi-board extraction logic."""

    def setUp(self):
        self.scraper = BobaedreamScraper(client=SafeHttpClient(min_delay=0.01, max_delay=0.02))

    def test_board_list_parsing(self):
        sample_html = """
        <table>
          <tr>
            <td>1</td>
            <td><a href="/view?code=national&No=2407234">BYD 아토3 충전 속도 질문</a></td>
            <td>작성자</td>
          </tr>
        </table>
        """
        items = self.scraper.parse_board_list(sample_html, "national")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["post_no"], "2407234")
        self.assertEqual(items[0]["board_code"], "national")
        self.assertIn("아토3 충전", items[0]["title"])

    def test_search_results_parsing(self):
        sample_html = """
        <dl>
          <dt><a href="/view?code=national&No=2407234" class="bsubject">BYD 아토3 충전 속도 질문</a></dt>
          <dd>작성자: 홍길동 | 날짜: 2026-01-15</dd>
        </dl>
        """
        items = self.scraper.parse_search_results(sample_html)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["post_no"], "2407234")
        self.assertEqual(items[0]["board_code"], "national")
        self.assertIn("아토3 충전", items[0]["title"])

    def test_post_detail_parsing(self):
        sample_html = """
        <html>
        <body>
          <strong class="title">아토3 어라운드뷰 왜곡 심각합니다</strong>
          <span class="author">보배차주</span>
          <div class="bodyCont">
            어라운드뷰 왜곡 때문에 휠 긁어먹었네요. 어안렌즈 굴절이 너무 심해요.
          </div>
          <!-- //bodyCont -->
          <div id="cmt_list">
            <dd id="cmt_1">저도 그거 보고 주차하다가 벽 박을 뻔했습니다.</dd>
          </div>
        </body>
        </html>
        """
        post = self.scraper.parse_post_detail(sample_html, "https://www.bobaedream.co.kr/view?code=import&No=714966")
        self.assertIn("어라운드뷰 왜곡", post["title"])
        self.assertIn("어안렌즈 굴절", post["body"])
        self.assertEqual(post["author"], "보배차주")
        self.assertEqual(len(post["comments"]), 1)

    def test_classification_and_record_extraction(self):
        post_data = {
            "url": "https://www.bobaedream.co.kr/view?code=electric&No=12345",
            "title": "BYD 씰 혹한기 급속 충전 굼벵이 충전 속도",
            "author": "전기차오너",
            "published_at": "2025-01-10",
            "view_count": 1500,
            "upvote_count": 30,
            "body": "영하 날씨에 LFP 배터리 100kW 환경부 급속 충전기에 꽂았는데 20kW로 기어가네요. 굼벵이 충전 때문에 얼어죽는 줄 알았습니다.",
            "comments": ["LFP 저온 충전 저하는 진짜 답이 없습니다."]
        }
        records = self.scraper.extract_complaint_records(post_data, board_name="보배드림 전기차게시판")
        self.assertGreaterEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec.platform, "bobaedream")
        self.assertEqual(rec.target_vehicle, "BYD Seal")
        self.assertEqual(rec.category, "charging")
        self.assertIn("굼벵이", rec.defect_topic)
        self.assertEqual(rec.platform_metadata.get("author_badge"), "전기차오너")


class TestDCInsideScraper(unittest.TestCase):
    """Test DC Inside scraper parsing and gallery extraction logic."""

    def setUp(self):
        self.scraper = DCInsideScraper(client=SafeHttpClient(min_delay=0.01, max_delay=0.02))

    def test_gallery_list_parsing(self):
        sample_html = """
        <table>
          <tr data-no="154210" class="ub-content us-post">
            <td class="gall_tit ub-word">
              <a href="/board/view/?id=electriccar&no=154210">아토3 초음파 센서 허공에 대고 삐삐거림</a>
            </td>
          </tr>
        </table>
        """
        items = self.scraper.parse_gallery_list(sample_html, "electriccar")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["post_id"], "154210")
        self.assertIn("초음파 센서", items[0]["title"])

    def test_post_detail_parsing(self):
        sample_html = """
        <html>
        <body>
          <span class="title_subject">빗길 회생제동 시 피쉬테일 털림</span>
          <td class="gall_writer"><span class="nickname">차갤러</span><span class="ip">(118.235)</span></td>
          <span class="gall_date" title="2025-07-20 14:00:00">2025.07.20</span>
          <input type="hidden" id="e_s_n_o" name="e_s_n_o" value="test_token_12345" />
          <div class="writing_view_box">
            비 오는 날 맨홀 통과할 때 차체 털림 발생해서 식겁했음. 순정 배트맨 타이어 극악 웻그립.
          </div>
          <!-- //writing_view_box -->
          <p class="usertxt">순정 배트맨 타이어가 문제임.</p>
        </body>
        </html>
        """
        post = self.scraper.parse_post_detail(sample_html, "https://gall.dcinside.com/mgallery/board/view/?id=electriccar&no=100", "electriccar", "100")
        self.assertIn("피쉬테일", post["title"])
        self.assertIn("차체 털림", post["body"])
        self.assertEqual(post["author_badge"], "차갤러 (118.235)")
        self.assertEqual(post["e_s_n_o"], "test_token_12345")
        self.assertEqual(len(post["comments"]), 1)

    def test_record_extraction(self):
        post_data = {
            "url": "https://gall.dcinside.com/mgallery/board/view/?id=commercialvehicle&no=555",
            "gallery_id": "commercialvehicle",
            "post_id": "555",
            "title": "T4K 1톤 화물 싣고 오르막 등판 롤백 식은땀",
            "author_badge": "용달맨 (223.38)",
            "author_type": "dc_masked_ip",
            "published_at": "2025-04-12",
            "view_count": 890,
            "upvote_count": 15,
            "body": "T4K 화물 적재하고 지하주차장 오르막 램프 올라가다가 오토홀드 풀리면서 뒤로 30cm 밀림 롤백 겪었습니다. 사고 날 뻔.",
            "comments": ["오토홀드 해제 딜레이 진짜 심함."]
        }
        records = self.scraper.extract_complaint_records(post_data)
        self.assertGreaterEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec.platform, "dcinside")
        self.assertEqual(rec.target_vehicle, "BYD T4K 1-Ton Truck")
        self.assertEqual(rec.category, "hill_climbing")
        self.assertIn("롤백", rec.defect_topic)
        self.assertEqual(rec.severity, "critical_safety")


class TestBlindScraper(unittest.TestCase):
    """Test Blind scraper Next.js SSR JSON parsing and verified badge extraction."""

    def setUp(self):
        self.scraper = BlindScraper(client=SafeHttpClient(min_delay=0.01, max_delay=0.02))

    def test_google_dork_query_builder(self):
        query = self.scraper.build_google_dork_query("BYD", category="parking")
        self.assertIn("site:teamblind.com/kr/post", query)
        self.assertIn('"BYD"', query)
        self.assertIn("주차", query)

    def test_next_data_ssr_parsing(self):
        ssr_json = {
            "props": {
                "pageProps": {
                    "article": {
                        "id": "8912401",
                        "title": "BYD 씰 시승해보고 경악한 점 (현직 완성차 엔지니어 후기)",
                        "body": "어제 지인이 뽑은 씰 시승해봤는데 빗길에서 회생제동 걸릴 때 뒷바퀴 접지력 순간적으로 날아가면서 차체 털림 발생함. 순정 타이어 웻그립 심각.",
                        "created_at": "2025-04-18T14:22:00+09:00",
                        "view_count": 8420,
                        "like_count": 142,
                        "user": {
                            "companyName": "현대자동차",
                            "job": "R&D"
                        },
                        "comments": [
                            {
                                "body": "LFP 블레이드 배터리 겨울철 저온 굼벵이 충전이랑 급속 충전 통신 튕김 심각함.",
                                "user": {
                                    "companyName": "LG에너지솔루션"
                                }
                            }
                        ]
                    }
                }
            }
        }
        sample_html = f"""
        <html>
        <head>
          <script id="__NEXT_DATA__" type="application/json">{json.dumps(ssr_json)}</script>
        </head>
        <body></body>
        </html>
        """
        post = self.scraper.parse_post_detail(sample_html, "https://www.teamblind.com/kr/post/test-post-8912401")
        self.assertEqual(post["title"], "BYD 씰 시승해보고 경악한 점 (현직 완성차 엔지니어 후기)")
        self.assertEqual(post["company"], "현대자동차")
        self.assertEqual(post["author_badge"], "현대자동차")
        self.assertEqual(post["view_count"], 8420)
        self.assertEqual(len(post["comments"]), 1)
        self.assertIn("[LG에너지솔루션]", post["comments"][0])

    def test_blind_record_extraction(self):
        post_data = {
            "url": "https://www.teamblind.com/kr/post/byd-atto3-parking-12345",
            "title": "BYD 아토3 어라운드뷰 왜곡 및 주차센서 고스트 비핑",
            "company": "현대모비스",
            "published_at": "2025-08-10",
            "view_count": 5200,
            "upvote_count": 95,
            "body": "아토3 3D 어라운드뷰 왜곡 심각해서 주차하다가 휠 긁어먹기 딱 좋음. 초음파 센서도 비만 오면 고스트 비핑 울림.",
            "comments": ["[기아] 저희 팀에서도 분석해봤는데 카메라 왜곡 보정 알고리즘 미흡입니다."]
        }
        records = self.scraper.extract_complaint_records(post_data)
        self.assertGreaterEqual(len(records), 1)
        rec = records[0]
        self.assertEqual(rec.platform, "blind")
        self.assertEqual(rec.board_name, "블라인드 자동차")
        self.assertEqual(rec.category, "parking")
        self.assertEqual(rec.platform_metadata.get("author_type"), "blind_verified_company")
        self.assertEqual(rec.platform_metadata.get("author_badge"), "현대모비스")


class TestCafeForumMiner(unittest.TestCase):
    """Test Cafe and forum normalizer logic."""

    def setUp(self):
        self.miner = CafeForumMiner(client=SafeHttpClient(min_delay=0.01, max_delay=0.02))

    def test_normalization_and_validation(self):
        raw = {
            "platform": "naver_cafe",
            "board_name": "전기차 동호회",
            "post_url": "https://cafe.naver.com/allaboutclube/123",
            "post_title": "BYD 언덕 롤백 문제",
            "target_vehicle": "BYD Atto 3",
            "category": "hill_climbing",
            "defect_topic": "경사로 정차 후 재출발 시 오토홀드 해제 딜레이로 뒤로 밀림(롤백)",
            "raw_quote": "경사로에서 브레이크 떼는 순간 뒤로 덜컹 밀려서 식은땀 줄줄 흘렸습니다.",
            "severity": "critical_safety"
        }
        rec = self.miner.normalize_record(raw)
        self.assertIsNotNone(rec)
        self.assertEqual(rec.category, "hill_climbing")
        self.assertEqual(rec.severity, "critical_safety")


class TestCompiledDatabase(unittest.TestCase):
    """Verify integrity and requirement compliance of compiled database."""

    def test_database_validation(self):
        complaints_file = os.path.join(PROJECT_ROOT, "data", "compiled_complaints.json")
        slang_file = os.path.join(PROJECT_ROOT, "data", "slang_dict.json")

        is_valid, errors, stats = validate_database(complaints_file, slang_file, min_per_category=5, min_total=30)
        self.assertTrue(is_valid, f"Validation errors: {errors}")
        self.assertGreaterEqual(stats["total_cases"], 30)
        for cat in ["parking", "charging", "rain_driving", "hill_climbing"]:
            self.assertGreaterEqual(stats["category_counts"].get(cat, 0), 5)


if __name__ == "__main__":
    unittest.main()
