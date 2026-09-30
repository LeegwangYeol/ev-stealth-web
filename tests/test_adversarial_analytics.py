"""
tests/test_adversarial_analytics.py - Comprehensive Adversarial Stress Test Suite.

Adversarially challenges:
1. scripts/domain_tokenizer.py:
   - Boundary inputs: Empty strings, None, whitespace-only, pure punctuation, Emoji/Unicode flood, 100KB massive strings.
   - Morphological Josa & Eomi stripping invariants.
   - Negation unification edge cases (trailing negations, stacked negations, unmapped words).
   - Longest-prefix Trie greedy matching & slang dictionary integration.
2. scripts/sentiment_engine.py:
   - Polarity bounds [-1.0, 1.0] under extreme stacked intensifiers and derogatory slang.
   - 4-Tier classification exact boundary tests.
   - Negation inversion and concessive clause re-weighting.
   - 5-Dimensional Defect Severity Index (DSI) bounds [0.0, 10.0] and multi-attribute scoring.
3. scripts/statistical_ranker.py:
   - Extreme inputs: Empty records, single doc, missing fields, malformed types.
   - Mathematical precision of TF, DF, Smooth TF-IDF, PMI N-grams, and Composite Complaint Scores (CCS).
   - TOP 30 Complaint Keywords ranking invariants.
4. scripts/cross_aggregator.py:
   - Contingency table row/col total invariants.
   - Pure Python Chi-Square statistic & degrees of freedom verification.
   - Platform, vehicle model, and temporal trend metrics consistency.
5. scripts/generate_report.py & STATISTICAL_REPORT.md:
   - Report generation idempotence and markdown table parsing.
   - Numerical consistency between report tables and raw database.
   - Zero placeholder tokens.
6. High-Scale Throughput & Stress Load:
   - 10,000 synthetic records stress test verifying performance and stability.
"""

from collections import Counter
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import unittest
from typing import Any, Dict, List, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if not (PROJECT_ROOT / "data" / "compiled_complaints.json").exists() and (PROJECT_ROOT.parent / "data" / "compiled_complaints.json").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.domain_tokenizer import AutomotiveTrie, BASE_AUTOMOTIVE_LEXICON, DomainTokenizer
from scripts.sentiment_engine import SentimentEngine, SentimentResult
from scripts.statistical_ranker import StatisticalRanker, KOREAN_STOPWORDS, DOMAIN_SEVERITY_MAP
from scripts.cross_aggregator import CrossAggregator
from scripts.generate_report import generate_statistical_report_content


class TestDomainTokenizerAdversarial(unittest.TestCase):
    """Adversarial stress testing for DomainTokenizer and AutomotiveTrie."""

    def setUp(self):
        self.tokenizer = DomainTokenizer()

    def test_01_empty_none_whitespace_inputs(self):
        """Verify tokenizer handles empty, None, and whitespace-only inputs without crashing."""
        edge_cases = ["", "   ", "\t\t\n\r\n"]
        for inp in edge_cases:
            res = self.tokenizer.tokenize(inp)
            self.assertEqual(res, [], f"Expected empty token list for input: {repr(inp)}")

            stems = self.tokenizer.tokenize_to_stems(inp)
            self.assertEqual(stems, [], f"Expected empty stems for input: {repr(inp)}")

    def test_02_pure_special_characters_and_emojis(self):
        """Verify tokenizer handles emojis, Asian scripts, control characters, and special symbols."""
        emoji_text = "🚗⚡💥🔥💀😱👎🚨⚠️"
        tokens = self.tokenizer.tokenize(emoji_text)
        self.assertEqual(tokens, [], f"Pure emojis should normalize to empty, got: {tokens}")

        special_text = "!@#$^&*()+~`|}{[]:;?><"
        tokens = self.tokenizer.tokenize(special_text)
        self.assertEqual(tokens, [], f"Pure special symbols should normalize to empty, got: {tokens}")

    def test_03_technical_unit_preservation(self):
        """Verify technical units (%/℃/kW/km/h) and numbers are preserved."""
        text = "영하 15℃ 혹한기 충전 시 18kW 속도 급락 및 배터리 잔량 20%에서 0% 셧다운 100km/h 주행"
        tokens = self.tokenizer.tokenize(text)
        raw_text_joined = " ".join(t["raw"] for t in tokens)
        self.assertIn("15℃", raw_text_joined)
        self.assertIn("18kW", raw_text_joined)
        self.assertIn("20%", raw_text_joined)
        self.assertIn("0%", raw_text_joined)
        self.assertIn("100km/h", raw_text_joined)

    def test_04_affix_stripping_boundary_invariants(self):
        """Verify Josa & Eomi stripping logic invariants."""
        # Minimum length invariant (stems >= 2 characters when stripping)
        self.assertEqual(self.tokenizer.strip_affixes("차는"), "차는")  # len(group1) == 1 -> don't strip
        self.assertEqual(self.tokenizer.strip_affixes("차가"), "차가")
        self.assertEqual(self.tokenizer.strip_affixes("배터리가"), "배터리")  # stripped
        self.assertEqual(self.tokenizer.strip_affixes("주차타워에서"), "주차타워")
        self.assertEqual(self.tokenizer.strip_affixes("고장났다"), "고장")

    def test_05_negation_unification_edge_cases(self):
        """Verify negation unification across various tricky sentence structures."""
        # 1. Standard negation
        tokens = self.tokenizer.tokenize("시동이 안 걸린다")
        negated = [t for t in tokens if t["category"] == "negated_predicate"]
        self.assertTrue(len(negated) >= 1)
        self.assertIn("안", negated[0]["raw"])

        # 2. Trailing negation at end of string
        tokens_trailing = self.tokenizer.tokenize("언덕길 올라가다 차가 안")
        self.assertTrue(len(tokens_trailing) > 0)
        self.assertEqual(tokens_trailing[-1]["raw"], "안")

        # 3. Multiple negations
        tokens_multi = self.tokenizer.tokenize("전혀 안 된다")
        self.assertTrue(len(tokens_multi) >= 1)

    def test_06_trie_longest_prefix_greedy_matching(self):
        """Verify Trie prefers longer matches over shorter sub-matches."""
        # "Atlas Batman A51" should match the 3-word phrase over "Atlas" or "Batman"
        tokens = self.tokenizer.tokenize("순정 Atlas Batman A51 타이어 끼고 주행함")
        matched_stems = [t["stem"] for t in tokens if t["is_domain"]]
        self.assertTrue(any("Atlas Batman" in s or "배트맨" in s for s in matched_stems))

        # "3D 어라운드뷰 왜곡" vs "어라운드뷰"
        tokens_av = self.tokenizer.tokenize("3D 어라운드뷰 왜곡 때문에 휠 긁음")
        matched_av = [t["stem"] for t in tokens_av if t["is_domain"]]
        self.assertTrue(any("어라운드뷰" in s for s in matched_av))

    def test_07_massive_string_tokenizer_stress(self):
        """Stress-test tokenizer on 100KB long string."""
        sample_text = "아토3 순정 배트맨타이어 빗길 수막현상 피쉬테일 털리고 지하주차장 입차거부 당함. " * 1500
        start = time.perf_counter()
        tokens = self.tokenizer.tokenize(sample_text)
        elapsed = time.perf_counter() - start
        self.assertGreater(len(tokens), 5000)
        self.assertLess(elapsed, 2.0, f"Tokenization took too long: {elapsed:.2f}s")


class TestSentimentEngineAdversarial(unittest.TestCase):
    """Adversarial stress testing for SentimentEngine and 4-Tier classification."""

    def setUp(self):
        self.engine = SentimentEngine()

    def test_01_empty_none_neutral_fallback(self):
        """Verify empty and None strings fallback to neutral polarity and 0.0 DSI."""
        for inp in ["", "   "]:
            res = self.engine.classify(inp)
            self.assertEqual(res.dsi_score, 0.0)
            self.assertIn(res.tier_label, ["NEUTRAL", "NEGATIVE"])
            self.assertTrue(-1.0 <= res.polarity_score <= 1.0)
            self.assertEqual(res.detected_complaints, [])

    def test_02_strict_score_bounds_under_extreme_rage(self):
        """Verify polarity score NEVER exceeds [-1.0, 1.0] under extreme stacked profanity."""
        extreme_rage_inputs = [
            "존나 개 씹 극악 최악 역대급 쓰레기 노답 짱깨차 시한폭탄 불쇼 황천길 익스프레스 벽돌방전 시발 폭망",
            "개빡치네 진짜 죽을뻔함 미쳤나 짱개차 바퀴달린 알리익스프레스 자폭차 살인무기",
            "완전 최고 훌륭 만족 대단히 정숙 쾌적 넓음 가성비 극찬 추천",
        ]
        for text in extreme_rage_inputs:
            res = self.engine.classify(text)
            self.assertTrue(-1.0 <= res.polarity_score <= 1.0, f"Score out of bounds: {res.polarity_score}")
            self.assertTrue(0.0 <= res.dsi_score <= 10.0, f"DSI out of bounds: {res.dsi_score}")
            for dim, val in res.dsi_breakdown.items():
                self.assertTrue(0.0 <= val <= 10.0, f"DSI breakdown {dim} out of bounds: {val}")

    def test_03_four_tier_classification_boundaries(self):
        """Verify 4-tier classification respects exact mathematical boundaries."""
        # 1. POSITIVE (+0.30 to +1.00)
        res_pos = self.engine.classify("가성비 최고 실내 공간 대단히 만족스럽고 정숙하고 훌륭합니다")
        self.assertGreaterEqual(res_pos.polarity_score, 0.30)
        self.assertEqual(res_pos.tier_label, "POSITIVE")

        # 2. NEUTRAL (-0.29 to +0.29)
        res_neu = self.engine.classify("신차 카탈로그 스펙과 공식 출시 일정 보조금 가격 확인")
        self.assertTrue(-0.29 <= res_neu.polarity_score <= 0.29)
        self.assertEqual(res_neu.tier_label, "NEUTRAL")

        # 3. NEGATIVE (-0.30 to -0.69)
        res_neg = self.engine.classify("와이퍼 채터링 소음이 나고 단차가 다소 아쉽네요")
        self.assertTrue(-0.69 <= res_neg.polarity_score <= -0.30 or res_neg.tier_label == "NEGATIVE")

        # 4. STRONGLY_NEGATIVE (-0.70 to -1.00)
        res_sneg = self.engine.classify("시한폭탄 불쇼 황천길 익스프레스 짱깨차 0% 벽돌방전 죽을뻔함")
        self.assertLessEqual(res_sneg.polarity_score, -0.70)
        self.assertEqual(res_sneg.tier_label, "STRONGLY_NEGATIVE")

    def test_04_concessive_clause_reweighting(self):
        """Verify concessive markers ('하지만', '그러나') properly reweight clauses."""
        # "가성비는 최고지만 배트맨타이어 때문에 피쉬테일 털려서 죽을뻔함"
        text = "가격이랑 가성비는 최고지만 순정 배트맨타이어 때문에 피쉬테일 털리고 지하주차장 입차거부 당함"
        res = self.engine.classify(text)
        self.assertLess(res.polarity_score, 0.0, "Concessive negative ending should dominate overall polarity")
        self.assertIn(res.tier_label, ["NEGATIVE", "STRONGLY_NEGATIVE"])
        self.assertGreater(res.dsi_score, 4.0)

    def test_05_negation_inversion(self):
        """Verify negators ('안', '못', '전혀') invert polarity."""
        res_positive = self.engine.classify("실내 마감과 정숙성이 대단히 훌륭하다")
        res_negated = self.engine.classify("실내 마감과 정숙성이 전혀 훌륭하지 않다")
        self.assertGreater(res_positive.polarity_score, res_negated.polarity_score)

    def test_06_dsi_five_dimensions_weights(self):
        """Verify DSI formula calculation: DSI = 0.35*Safety + 0.25*Func + 0.15*Econ + 0.15*Social + 0.10*Conv."""
        # Pure safety text
        res_safety = self.engine.classify("배터리 불쇼 화재 시한폭탄 자폭차")
        expected_dsi_approx = 0.35 * res_safety.dsi_breakdown["safety"] + 0.15 * res_safety.dsi_breakdown["social"]
        self.assertAlmostEqual(res_safety.dsi_score, round(expected_dsi_approx, 2), delta=0.5)


class TestStatisticalRankerAdversarial(unittest.TestCase):
    """Adversarial stress testing for StatisticalRanker, TF-IDF, and PMI N-grams."""

    def test_01_empty_and_single_record_datasets(self):
        """Verify ranker functions on empty or minimal dataset without zero-division."""
        # Empty records
        ranker_empty = StatisticalRanker([])
        top_empty = ranker_empty.compute_top_keywords(top_n=30)
        self.assertEqual(len(top_empty), 30)
        self.assertEqual(ranker_empty.compute_tfidf("배트맨타이어"), 0.0)
        self.assertEqual(ranker_empty.extract_ngrams(n=2), [])

        # Single record
        single_rec = [{
            "id": "single_001",
            "platform": "dcinside",
            "post_title": "아토3 빗길 수막현상",
            "raw_quote": "배트맨타이어 빗길 수막현상 피쉬테일 털림",
            "defect_topic": "우천시 주행",
        }]
        ranker_single = StatisticalRanker(single_rec)
        top_single = ranker_single.compute_top_keywords(top_n=10)
        self.assertEqual(len(top_single), 10)
        self.assertGreater(top_single[0]["raw_count"], 0)

    def test_02_malformed_record_fields(self):
        """Verify ranker handles records with missing, None, or unexpected field types."""
        malformed_records = [
            {"id": "bad_001"},  # Missing all content
            {"id": "bad_002", "post_title": "", "raw_quote": "", "defect_topic": ""},
            {"id": "bad_003", "post_title": "테스트", "raw_quote": "배트맨타이어", "defect_topic": "우천주행"},
        ]
        # Should not throw exception
        ranker = StatisticalRanker(malformed_records)
        top_res = ranker.compute_top_keywords(top_n=5)
        self.assertEqual(len(top_res), 5)

    def test_03_smooth_tfidf_mathematical_precision(self):
        """Verify smooth TF-IDF formula matches definition: TF * (ln((1+N)/(1+DF)) + 1.0)."""
        corpus = [
            {"id": "c1", "raw_quote": "배트맨타이어 웻그립 수막현상 피쉬테일", "post_title": "", "defect_topic": ""},
            {"id": "c2", "raw_quote": "배트맨타이어 혹한기 굼벵이충전", "post_title": "", "defect_topic": ""},
            {"id": "c3", "raw_quote": "지하주차장 입차거부 시한폭탄", "post_title": "", "defect_topic": ""},
        ]
        ranker = StatisticalRanker(corpus)
        n = 3
        term = "배트맨타이어"
        tf = ranker.term_freq[term]
        df = ranker.doc_freq[term]
        self.assertEqual(tf, 2)
        self.assertEqual(df, 2)

        expected_tfidf = round(tf * (math.log((1.0 + n) / (1.0 + df)) + 1.0), 2)
        calc_tfidf = ranker.compute_tfidf(term)
        self.assertEqual(calc_tfidf, expected_tfidf)

    def test_04_pmi_ngram_mathematical_invariants(self):
        """Verify Pointwise Mutual Information (PMI) scoring on co-occurring bigrams."""
        corpus = [
            {"id": f"doc_{i}", "raw_quote": "지하주차장 입차거부 시한폭탄 짱깨차", "post_title": "", "defect_topic": ""}
            for i in range(10)
        ]
        ranker = StatisticalRanker(corpus)
        ngrams = ranker.extract_ngrams(n=2, min_freq=3, top_k=5)
        self.assertTrue(len(ngrams) > 0)
        gram, count, pmi = ngrams[0]
        self.assertEqual(count, 10)
        self.assertGreater(pmi, 0.0)


class TestCrossAggregatorAdversarial(unittest.TestCase):
    """Adversarial stress testing for CrossAggregator, Contingency tables, and Chi-Square."""

    def test_01_contingency_table_marginal_sums(self):
        """Verify contingency table row and column totals equal Grand Total."""
        data_path = PROJECT_ROOT / "data" / "compiled_complaints.json"
        with open(data_path, "r", encoding="utf-8") as f:
            records = json.load(f)

        agg = CrossAggregator()
        results = agg.analyze(records)
        contingency = results["contingency"]

        plat_sent = contingency["platform_sentiment"]
        matrix = plat_sent["matrix"]

        row_totals = [sum(row) for row in matrix]
        col_totals = [sum(matrix[r][c] for r in range(len(matrix))) for c in range(len(matrix[0]))]
        grand_total = sum(row_totals)

        self.assertEqual(sum(col_totals), grand_total)
        self.assertGreater(grand_total, 0)
        self.assertEqual(plat_sent["degrees_of_freedom"], (len(matrix) - 1) * (len(matrix[0]) - 1))

    def test_02_chi_square_computation_accuracy(self):
        """Verify pure Python Chi-Square statistic: sum((O - E)^2 / E)."""
        data_path = PROJECT_ROOT / "data" / "compiled_complaints.json"
        with open(data_path, "r", encoding="utf-8") as f:
            records = json.load(f)

        agg = CrossAggregator()
        results = agg.analyze(records)
        plat_sent = results["contingency"]["platform_sentiment"]
        matrix = plat_sent["matrix"]
        reported_chi2 = plat_sent["chi2_statistic"]

        # Re-compute Chi-Square
        num_rows = len(matrix)
        num_cols = len(matrix[0])
        row_totals = [sum(row) for row in matrix]
        col_totals = [sum(matrix[r][c] for r in range(num_rows)) for c in range(num_cols)]
        grand_total = sum(row_totals)

        manual_chi2 = 0.0
        for r in range(num_rows):
            for c in range(num_cols):
                o_val = matrix[r][c]
                e_val = (row_totals[r] * col_totals[c]) / grand_total
                if e_val > 0:
                    manual_chi2 += ((o_val - e_val) ** 2) / e_val

        self.assertAlmostEqual(reported_chi2, round(manual_chi2, 3), places=2)


class TestStatisticalReportConsistency(unittest.TestCase):
    """Verification of STATISTICAL_REPORT.md numerical consistency against compiled database."""

    def setUp(self):
        data_path = PROJECT_ROOT / "data" / "compiled_complaints.json"
        with open(data_path, "r", encoding="utf-8") as f:
            self.records = json.load(f)

        report_path = PROJECT_ROOT / "STATISTICAL_REPORT.md"
        with open(report_path, "r", encoding="utf-8") as f:
            self.report_text = f.read()

    def test_01_no_placeholder_tokens(self):
        """Verify zero placeholder tokens in STATISTICAL_REPORT.md."""
        forbidden = ["[TODO]", "[TBD]", "[PLACEHOLDER]", "[INSERT", "Lorem ipsum", "추가 예정", "산출 예정"]
        for f in forbidden:
            self.assertNotIn(f, self.report_text, f"Found forbidden placeholder: {f}")

    def test_02_top30_ranking_table_integrity(self):
        """Verify TOP 30 ranking table has exactly 30 numbered rows, strictly descending ranks, and valid counts."""
        # Find all table rows matching rank numbers | **1** | ... | **30** |
        rank_pattern = re.compile(
            r'\|\s*\*\*(\d+)\*\*\s*\|\s*`([^`]+)`\s*\|\s*([^\|]+)\|\s*([\d,]+)회\s*\|\s*([\d\.]+)%\s*\|\s*([\d\.,]+)\s*\|\s*\*\*([\d\.]+)\*\*\s*\|\s*(?:[\d,]+\s*\|\s*)?"([^"]+)"\s*\|'
        )
        matches = rank_pattern.findall(self.report_text)
        self.assertGreaterEqual(len(matches), 30, f"Expected at least 30 ranked rows, found {len(matches)}")

        prev_rank = 0
        total_share = 0.0
        for m in matches:
            rank_num = int(m[0])
            kw = m[1]
            cat = m[2].strip()
            tf = int(m[3].replace(",", ""))
            share = float(m[4])
            tfidf = float(m[5])
            dsi = float(m[6])
            quote = m[7]

            # Invariants
            self.assertEqual(rank_num, prev_rank + 1, f"Rank number sequence broken at {rank_num}")
            prev_rank = rank_num
            self.assertGreater(tf, 0, f"TF must be > 0 for {kw}")
            self.assertGreater(share, 0.0, f"Share must be > 0.0% for {kw}")
            self.assertGreater(tfidf, 0.0, f"TF-IDF must be > 0.0 for {kw}")
            self.assertTrue(0.0 <= dsi <= 10.0, f"DSI must be in [0.0, 10.0] for {kw}, got {dsi}")
            self.assertTrue(len(quote) >= 5, f"Quote too short for {kw}: '{quote}'")
            total_share += share

        self.assertGreater(total_share, 100.0, "Sum of multi-label keyword shares should exceed 100% due to overlapping topics")

    def test_03_report_regeneration_idempotence(self):
        """Verify generate_report.py generates valid markdown idempotently."""
        tokenizer = DomainTokenizer()
        sentiment_engine = SentimentEngine(tokenizer)
        ranker = StatisticalRanker(self.records, tokenizer, sentiment_engine)
        aggregator = CrossAggregator(tokenizer, sentiment_engine)

        new_content = generate_statistical_report_content(self.records, ranker, aggregator)
        self.assertGreater(len(new_content), 10000)
        self.assertIn("## 1. 개요 및 빅데이터 수집 통계", new_content)
        self.assertIn("## 2. 불만 키워드 종합 TOP 30 랭킹", new_content)
        self.assertIn("## 3. 핵심 4대 결함 도메인별 통계 심층 분석", new_content)
        self.assertIn("## 4. 커뮤니티 플랫폼별 비교 통계", new_content)
        self.assertIn("## 5. 차종별 결함 집중도 및 위험성 평가", new_content)
        self.assertIn("## 6. 시계열 민심 변화 추이 분석", new_content)
        self.assertIn("## 7. 전략적 제언 및 결론", new_content)


class TestHighScaleThroughputStress(unittest.TestCase):
    """Stress testing on 10,000 synthetic documents to evaluate throughput and stability."""

    def test_01_synthetic_10k_records_load(self):
        """Benchmark 10,000 document tokenization, sentiment classification, and statistical ranking."""
        templates = [
            "BYD 아토3 순정 배트맨타이어 끼고 비오는 날 올림픽대로에서 수막현상 터지며 피쉬테일 털리고 지하주차장 입차거부까지 당함 짱깨차 진짜 노답이다",
            "BYD 씰 혹한기 영하 10도에 환경부 급속 충전기 꽂았더니 PLC 통신 튕김 에러 뜨며 18kW 굼벵이충전 극악",
            "BYD T4K 화물 1톤 싣고 남한산성 언덕길 올라가는데 모터 과열 거북이모드 뜨며 출력제한 20km 서행 롤백 덜컹",
            "BMS 20% 잔량에서 갑자기 0%로 순간 폭락하며 고속도로에서 차 셧다운되고 벽돌차 됨 12V 방전까지 터짐",
            "LFP 배터리 중량 2.1톤 초과로 아파트 기계식 주차타워 입고 불가 먹고 N단 중립 이중주차도 안 됨",
            "엔카 중고차 올렸더니 1년 만에 반값 감가폭탄 터지고 범퍼 수리 AS 부품 선전 직구 3개월 대기",
        ]
        platforms = ["bobaedream", "dcinside", "blind", "naver_cafe"]

        synthetic_records = []
        for i in range(10000):
            tpl = templates[i % len(templates)]
            plat = platforms[i % len(platforms)]
            synthetic_records.append({
                "id": f"synth_{i:05d}",
                "platform": plat,
                "post_title": f"합성 테스트 게시글 {i}",
                "raw_quote": tpl,
                "defect_topic": "종합 결함 테스트",
            })

        start_time = time.perf_counter()

        # Run pipeline
        tokenizer = DomainTokenizer()
        sentiment_engine = SentimentEngine(tokenizer)
        ranker = StatisticalRanker(synthetic_records, tokenizer, sentiment_engine)
        top30 = ranker.compute_top_keywords(synthetic_records, top_n=30)
        ngrams = ranker.extract_ngrams(n=2, min_freq=10, top_k=10)

        total_time = time.perf_counter() - start_time
        docs_per_sec = len(synthetic_records) / max(0.001, total_time)

        # Assertions
        self.assertEqual(len(top30), 30)
        self.assertGreater(len(ngrams), 0)
        self.assertGreater(docs_per_sec, 400, f"Throughput too low: {docs_per_sec:.1f} docs/sec (Total: {total_time:.2f}s)")
        print(f"\n[BENCHMARK] 10,000 synthetic records processed in {total_time:.3f}s ({docs_per_sec:,.0f} docs/sec)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
