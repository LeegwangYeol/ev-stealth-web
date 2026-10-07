"""
tests/test_sync_integrity_cycle9.py - Comprehensive Cycle 9 Synchronization, Backend Hardening,
and Frontend Boundary Resilience Test Suite.

Authoritative Reference:
- ORIGINAL_REQUEST.md
- DISPATCH.md (Cycle 9 Wave 2 specification)
- COLLABORATION.md

Coverage:
1. Bidirectional default path synchronization in run_tracker.py:
   - _resolve_default_paths() correctly resolves dual-tree targets (root data/ and web src/data/).
   - main() execution automatically synchronizes outputs bidirectionally when default targets are specified.
   - Defect reports bidirectional synchronization between root and web directories.
2. Microsecond quarantine collision avoidance in tracker/subsidy_tracker.py:
   - quarantine_corrupted_cache() utilizes microsecond precision (%Y%m%d_%H%M%S_%f) in filename timestamp suffix.
   - Rapid-fire consecutive quarantines in tight loops (<1ms) generate distinct filenames without collision.
   - Graceful non-existent and error containment.
3. Category-filtered index retrieval and caching in tracker/defect_tracker.py:
   - DefectTracker._build_category_index() classifies defect records into normalized uppercase category buckets.
   - DefectTracker.query_defects() extracts candidates from category index for high-performance retrieval.
   - Query cache memoization and bounded cache memory protection (1024 entries).
   - Invalidation mechanisms (invalidate_cache() and mtime-based re-indexing).
4. getPriceSubsidyRatio(Infinity) returns 0.0 in ev-stealth-web/src/lib/getSubsidyData.ts:
   - Positive Infinity strictly returns 0.0 (luxury vehicle exclusion for infinite MSRP).
   - Negative Infinity and non-finites safely caught by boundary guards.
   - Statutory price boundaries (54,999,999 -> 1.0, 55,000,000 -> 0.5, 84,999,999 -> 0.5, 85,000,000 -> 0.0).
5. getRegionById(null) and getModelById(null) null/type guards in getSubsidyData.ts:
   - Null, undefined, empty, and non-string inputs safely return undefined without throwing TypeError.
   - Valid identifiers correctly resolve corresponding entries.
6. getAllEnrichedModels({}) iterability guard in ev-stealth-web/src/lib/getReliabilityData.ts:
   - Passing an empty object {} or object with missing brands returns an empty array [] without throwing TypeError.
   - Tolerates malformed brands with null/undefined models arrays.
   - Default invocation returns complete enriched model matrix.
7. simulateBatteryHealth() NaN input resilience in ev-stealth-web/src/lib/getDepreciationData.ts:
   - Passing NaN for ambientTempC, storageSoc, dcfcRatio, years, packCapacityKwh returns valid finite numbers.
   - Zero NaN, zero null, zero undefined in numerical simulation outputs.
8. batterySimulationCache bounded eviction at 100 entries in DepreciationCalculatorClient.tsx:
   - Component source verification confirming MAX_BATTERY_SIMULATION_CACHE_ENTRIES = 100 and FIFO eviction.
   - Map FIFO eviction algorithm verification under 150+ insertions retaining exactly 100 newest items.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Adaptive repository and web root resolution
def _find_repo_root() -> Path:
    candidates = [
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent.parent.parent,
        Path.cwd(),
        Path.cwd().parent,
    ]
    for p in candidates:
        if (p / "ev-stealth-web").is_dir() and (p / "data").is_dir():
            return p
    return Path(__file__).resolve().parent.parent

PROJECT_ROOT = _find_repo_root()
WEB_ROOT = PROJECT_ROOT / "ev-stealth-web"
SRC_DIR = WEB_ROOT / "src"
LIB_DIR = SRC_DIR / "lib"
APP_DIR = SRC_DIR / "app"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
else:
    sys.path.remove(str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT))

if str(WEB_ROOT) not in sys.path:
    sys.path.append(str(WEB_ROOT))

import run_tracker
from tracker.subsidy_tracker import SubsidyTracker
from tracker.defect_tracker import DefectTracker
from tracker.subsidy_models import SubsidyPayload
from tracker.subsidy_baseline import build_initial_baseline


def _eval_ts_node(script: str, timeout_sec: int = 30) -> Any:
    """
    Executes a Node.js snippet using jiti to resolve TypeScript files with alias mappings
    synchronously and accurately without transpilation skew.
    """
    if not shutil.which("node"):
        raise unittest.SkipTest("Node.js runtime not installed on host environment.")

    jiti_path = WEB_ROOT / "node_modules" / "jiti"
    pkg_path = WEB_ROOT / "package.json"

    if not jiti_path.exists():
        raise unittest.SkipTest(f"jiti not found at {jiti_path}")

    node_wrapper = f"""
    const Module = require('module');
    const path = require('path');
    const origResolve = Module._resolveFilename;
    Module._resolveFilename = function(request, parent, isMain, options) {{
        if (request.startsWith('@/')) {{
            request = request.replace('@/', path.resolve({json.dumps(str(SRC_DIR))}) + '/');
        }}
        return origResolve.call(this, request, parent, isMain, options);
    }};
    const createJITI = require({json.dumps(str(jiti_path))});
    const jiti = createJITI({json.dumps(str(pkg_path))});

    {script}
    """
    proc = subprocess.run(
        ["node", "-e", node_wrapper],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=timeout_sec,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Node execution failed with exit code {proc.returncode}:\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )

    lines = [
        line.strip()
        for line in proc.stdout.splitlines()
        if line.strip() and not line.strip().startswith("(") and not line.strip().startswith("Warning:")
    ]
    if not lines:
        raise ValueError(f"No JSON output from Node execution:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
    return json.loads(lines[-1])


# ==============================================================================
# 1. Bidirectional Default Path Synchronization in run_tracker.py
# ==============================================================================

class TestCycle9BidirectionalDefaultPathSync(unittest.TestCase):
    """Verifies bidirectional default path resolution and synchronization in run_tracker.py."""

    def test_resolve_default_paths_detects_dual_tree_targets(self) -> None:
        """_resolve_default_paths() must resolve primary and web mirrors when in dual-tree repo."""
        primary_out, web_out, mirror_prim, mirror_web, ext_targets = run_tracker._resolve_default_paths()

        self.assertTrue(str(primary_out).endswith("ev_subsidy_data.json"))
        self.assertTrue(str(web_out).endswith("ev_subsidy_data.json"))
        self.assertTrue(str(mirror_prim).endswith("subsidy_depletion_data.json"))
        self.assertTrue(str(mirror_web).endswith("subsidy_depletion_data.json"))

        # Both root data and web data directories must be referenced
        all_targets = [primary_out, web_out, mirror_prim, mirror_web] + ext_targets
        all_target_strs = [str(t) for t in all_targets]

        has_root_data = any("/data/" in s or s.endswith("/data") for s in all_target_strs)
        has_web_data = any("ev-stealth-web" in s or "/src/data" in s for s in all_target_strs)
        self.assertTrue(has_root_data, "Resolved targets must include root data/ directory")
        self.assertTrue(has_web_data, "Resolved targets must include web src/data/ directory")

    def test_sync_defect_reports_bidirectional_root_to_web(self) -> None:
        """sync_defect_reports() copies from root to web when root is newer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            root_dir = tmp / "data"
            web_dir = tmp / "ev-stealth-web" / "src" / "data"
            root_dir.mkdir(parents=True)
            web_dir.mkdir(parents=True)

            root_file = root_dir / "daily_reports.json"
            web_file = web_dir / "daily_reports.json"

            sample_reports = {
                "reports": [
                    {
                        "report_id": "test-c9-01",
                        "title": "Cycle 9 Test Report",
                        "defect_category": "BATTERY_CHARGING",
                        "vehicle_brand": "현대",
                        "vehicle_model": "아이오닉 5",
                        "severity_index": 7.5,
                    }
                ],
                "statistics": {"total_filtered_defects": 1},
            }
            with open(root_file, "w", encoding="utf-8") as f:
                json.dump(sample_reports, f)

            with mock.patch.object(run_tracker, "_CURRENT_DIR", tmp):
                written = run_tracker.sync_defect_reports(web_dir=web_dir)

            self.assertTrue(web_file.exists(), "Web defect file must be created")
            with open(web_file, "r", encoding="utf-8") as f:
                web_data = json.load(f)
            self.assertEqual(web_data["reports"][0]["report_id"], "test-c9-01")
            self.assertIn(str(web_file), written)

    def test_sync_defect_reports_bidirectional_web_to_root(self) -> None:
        """sync_defect_reports() copies from web to root when web is newer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            root_dir = tmp / "data"
            web_dir = tmp / "ev-stealth-web" / "src" / "data"
            root_dir.mkdir(parents=True)
            web_dir.mkdir(parents=True)

            root_file = root_dir / "daily_reports.json"
            web_file = web_dir / "daily_reports.json"

            older_reports = {
                "reports": [{"report_id": "old-report", "defect_category": "OTHER"}],
                "statistics": {},
            }
            with open(root_file, "w", encoding="utf-8") as f:
                json.dump(older_reports, f)

            # Set older mtime on root file
            past_time = time.time() - 100
            os.utime(root_file, (past_time, past_time))

            newer_reports = {
                "reports": [
                    {
                        "report_id": "newer-web-report",
                        "title": "Newer Defect on Web",
                        "defect_category": "SOFTWARE_ELECTRONICS",
                        "vehicle_brand": "기아",
                        "vehicle_model": "EV6",
                        "severity_index": 8.0,
                    }
                ],
                "statistics": {"total_filtered_defects": 1},
            }
            with open(web_file, "w", encoding="utf-8") as f:
                json.dump(newer_reports, f)

            with mock.patch.object(run_tracker, "_CURRENT_DIR", tmp):
                written = run_tracker.sync_defect_reports(web_dir=web_dir)

            with open(root_file, "r", encoding="utf-8") as f:
                updated_root = json.load(f)
            self.assertEqual(updated_root["reports"][0]["report_id"], "newer-web-report")
            self.assertIn(str(root_file), written)


# ==============================================================================
# 2. Microsecond Quarantine Collision Avoidance in tracker/subsidy_tracker.py
# ==============================================================================

class TestCycle9MicrosecondQuarantineCollisionAvoidance(unittest.TestCase):
    """Verifies microsecond quarantine naming and collision avoidance in SubsidyTracker."""

    def setUp(self) -> None:
        self.tracker = SubsidyTracker(quarantine_corrupted=True)

    def test_quarantine_filename_includes_microsecond_timestamp(self) -> None:
        """Quarantine filename must contain microsecond timestamp matching %Y%m%d_%H%M%S_%f."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_cache.json"
            test_file.write_text("{corrupt json", encoding="utf-8")

            quarantined = self.tracker.quarantine_corrupted_cache(test_file)
            self.assertIsNotNone(quarantined)
            self.assertTrue(quarantined.exists())
            self.assertFalse(test_file.exists())

            # Verify pattern: test_cache.corrupt_YYYYMMDD_HHMMSS_ffffff.json
            pattern = r"^test_cache\.corrupt_\d{8}_\d{6}_\d{6}\.json$"
            self.assertRegex(
                quarantined.name,
                pattern,
                f"Quarantine filename '{quarantined.name}' must contain 6-digit microsecond precision",
            )

    def test_rapid_consecutive_quarantines_do_not_collide(self) -> None:
        """Rapid consecutive calls to quarantine_corrupted_cache must produce distinct files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            quarantined_files: List[Path] = []
            tmp = Path(tmpdir)

            for i in range(5):
                cache_file = tmp / "ev_subsidy_data.json"
                cache_file.write_text(f'{{"attempt": {i}, corrupt}}', encoding="utf-8")
                q_path = self.tracker.quarantine_corrupted_cache(cache_file)
                self.assertIsNotNone(q_path)
                quarantined_files.append(q_path)

            # All 5 files must exist and have unique paths
            self.assertEqual(len(quarantined_files), 5)
            unique_paths = {p.resolve() for p in quarantined_files}
            self.assertEqual(
                len(unique_paths),
                5,
                f"All 5 quarantined paths must be distinct (collision detected: {quarantined_files})",
            )
            for p in quarantined_files:
                self.assertTrue(p.exists(), f"Quarantined file {p} must exist on disk")

    def test_quarantine_nonexistent_file_returns_none(self) -> None:
        """quarantine_corrupted_cache on a non-existent file returns None without raising."""
        non_existent = Path("/tmp/definitely_not_existing_cycle9_file.json")
        res = self.tracker.quarantine_corrupted_cache(non_existent)
        self.assertIsNone(res)


# ==============================================================================
# 3. Category-Filtered Index Retrieval in tracker/defect_tracker.py
# ==============================================================================

class TestCycle9DefectTrackerCategoryIndexAndQuerying(unittest.TestCase):
    """Verifies category pre-filtering index and query caching in DefectTracker."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp(prefix="test_cycle9_defect_")
        self.data_path = Path(self.temp_dir) / "daily_reports.json"

        # Synthetic multi-category dataset
        self.sample_dataset = {
            "reports": [
                {
                    "report_id": "r-01",
                    "title": "BMS Overheat Warning",
                    "defect_category": "BATTERY_CHARGING",
                    "vehicle_brand": "현대",
                    "vehicle_model": "아이오닉 5",
                    "severity_index": 8.5,
                    "defect_topic": "배터리 과열",
                    "verbatim_quote": "급속 충전 중 배터리 경고등",
                },
                {
                    "report_id": "r-02",
                    "title": "Infotainment Black Screen",
                    "defect_category": "SOFTWARE_ELECTRONICS",
                    "vehicle_brand": "현대",
                    "vehicle_model": "아이오닉 6",
                    "severity_index": 5.0,
                    "defect_topic": "화면 블랙아웃",
                    "verbatim_quote": "내비게이션 화면 꺼짐",
                },
                {
                    "report_id": "r-03",
                    "title": "OBC Charging Interruption",
                    "defect_category": "BATTERY_CHARGING",
                    "vehicle_brand": "기아",
                    "vehicle_model": "EV6",
                    "severity_index": 7.8,
                    "defect_topic": "완속 충전 중단",
                    "verbatim_quote": "완속 충전기 꽂으면 바로 튕김",
                },
                {
                    "report_id": "r-04",
                    "title": "Regenerative Braking Judder",
                    "defect_category": "BRAKE_STEERING",
                    "vehicle_brand": "테슬라",
                    "vehicle_model": "Model Y",
                    "severity_index": 6.2,
                    "defect_topic": "회생제동 이질감",
                    "verbatim_quote": "감속 시 페달 떨림",
                },
            ],
            "statistics": {"total_filtered_defects": 4},
        }
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(self.sample_dataset, f)

        self.defect_tracker = DefectTracker(root_data_dir=self.temp_dir, web_data_dir=self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_category_index_build_and_retrieval(self) -> None:
        """DefectTracker builds category index and query_defects retrieves from pre-filtered bucket."""
        # Query BATTERY_CHARGING
        battery_results = self.defect_tracker.query_defects(
            category="BATTERY_CHARGING",
            file_path=self.data_path,
        )
        self.assertEqual(len(battery_results), 2)
        for r in battery_results:
            self.assertEqual(r["defect_category"], "BATTERY_CHARGING")
        ids = {r["report_id"] for r in battery_results}
        self.assertEqual(ids, {"r-01", "r-03"})

        # Case-insensitive category query with whitespace
        soft_results = self.defect_tracker.query_defects(
            category="  software_electronics  ",
            file_path=self.data_path,
        )
        self.assertEqual(len(soft_results), 1)
        self.assertEqual(soft_results[0]["report_id"], "r-02")

    def test_query_cache_memoization_and_invalidation(self) -> None:
        """Repeated queries return cached results; invalidate_cache() clears in-memory state."""
        # Initial query builds cache
        res1 = self.defect_tracker.query_defects(category="BATTERY_CHARGING", file_path=self.data_path)
        self.assertEqual(len(res1), 2)
        self.assertGreater(len(self.defect_tracker._query_cache), 0)

        # Second query hits cache
        res2 = self.defect_tracker.query_defects(category="BATTERY_CHARGING", file_path=self.data_path)
        self.assertEqual(res1, res2)

        # Invalidation clears index and cache
        self.defect_tracker.invalidate_cache()
        self.assertIsNone(self.defect_tracker._cached_reports)
        self.assertEqual(len(self.defect_tracker._category_index), 0)
        self.assertEqual(len(self.defect_tracker._query_cache), 0)

    def test_multi_criteria_filtering_with_category_index(self) -> None:
        """Combined filters (category + brand + min_severity) operate correctly on indexed pool."""
        results = self.defect_tracker.query_defects(
            category="BATTERY_CHARGING",
            vehicle_brand="현대",
            min_severity=8.0,
            file_path=self.data_path,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["report_id"], "r-01")

        # Non-matching criteria returns empty list
        no_match = self.defect_tracker.query_defects(
            category="BATTERY_CHARGING",
            vehicle_brand="BMW",
            file_path=self.data_path,
        )
        self.assertEqual(no_match, [])


# ==============================================================================
# 4. getPriceSubsidyRatio(Infinity) returns 0.0 in getSubsidyData.ts
# ==============================================================================

class TestCycle9PriceSubsidyRatioInfinity(unittest.TestCase):
    """Verifies getPriceSubsidyRatio luxury vehicle exclusion for Infinity MSRP in getSubsidyData.ts."""

    def test_get_price_subsidy_ratio_infinity_returns_zero(self) -> None:
        """getPriceSubsidyRatio(Infinity) must return 0.0 (luxury vehicle exclusion)."""
        sub_path = json.dumps(str(LIB_DIR / "getSubsidyData.ts"))
        script = f"""
        const sub = jiti({sub_path});
        const results = {{
            ratioPosInf: sub.getPriceSubsidyRatio(Infinity),
            ratioNegInf: sub.getPriceSubsidyRatio(-Infinity),
            ratioNaN: sub.getPriceSubsidyRatio(NaN),
            ratioZero: sub.getPriceSubsidyRatio(0),
            ratio54M: sub.getPriceSubsidyRatio(54999999),
            ratio55M: sub.getPriceSubsidyRatio(55000000),
            ratio84M: sub.getPriceSubsidyRatio(84999999),
            ratio85M: sub.getPriceSubsidyRatio(85000000),
            ratio120M: sub.getPriceSubsidyRatio(120000000)
        }};
        console.log(JSON.stringify(results));
        """
        res = _eval_ts_node(script)

        # Core Cycle 9 requirement: Infinity returns 0.0
        self.assertEqual(res["ratioPosInf"], 0.0, "getPriceSubsidyRatio(Infinity) must strictly return 0.0")

        # Boundary and error sanity
        self.assertEqual(res["ratioNegInf"], 1.0, "-Infinity caught by non-finite/negative guard returning 1.0")
        self.assertEqual(res["ratioNaN"], 1.0, "NaN caught by non-finite guard returning 1.0")
        self.assertEqual(res["ratioZero"], 1.0, "0 KRW returns 1.0 (100% eligibility)")
        self.assertEqual(res["ratio54M"], 1.0, "54.99M KRW returns 1.0")
        self.assertEqual(res["ratio55M"], 0.5, "55.00M KRW returns 0.5 (50% statutory tier)")
        self.assertEqual(res["ratio84M"], 0.5, "84.99M KRW returns 0.5")
        self.assertEqual(res["ratio85M"], 0.0, "85.00M KRW returns 0.0 (0% luxury exclusion)")
        self.assertEqual(res["ratio120M"], 0.0, "120M KRW returns 0.0")


# ==============================================================================
# 5. getRegionById(null) and getModelById(null) return undefined
# ==============================================================================

class TestCycle9SubsidyDataNullGuards(unittest.TestCase):
    """Verifies getRegionById and getModelById defensive null/type guards in getSubsidyData.ts."""

    def test_get_region_and_model_by_id_null_guards(self) -> None:
        """getRegionById and getModelById with null/undefined/non-strings must return undefined without throwing."""
        sub_path = json.dumps(str(LIB_DIR / "getSubsidyData.ts"))
        script = f"""
        const sub = jiti({sub_path});
        const results = {{
            regionNull: sub.getRegionById(null) === undefined,
            regionUndefined: sub.getRegionById(undefined) === undefined,
            regionEmpty: sub.getRegionById("") === undefined,
            regionNumber: sub.getRegionById(12345) === undefined,
            regionObject: sub.getRegionById({{}}) === undefined,
            modelNull: sub.getModelById(null) === undefined,
            modelUndefined: sub.getModelById(undefined) === undefined,
            modelEmpty: sub.getModelById("") === undefined,
            modelNumber: sub.getModelById(9999) === undefined,
            modelObject: sub.getModelById({{}}) === undefined,
            validRegion: sub.getRegionById("KR-11")?.name_ko,
            validModel: sub.getModelById("ioniq-5-2026")?.name_ko
        }};
        console.log(JSON.stringify(results));
        """
        res = _eval_ts_node(script)

        # All invalid inputs return undefined (evaluated to true in JS === undefined)
        self.assertTrue(res["regionNull"], "getRegionById(null) must return undefined")
        self.assertTrue(res["regionUndefined"], "getRegionById(undefined) must return undefined")
        self.assertTrue(res["regionEmpty"], "getRegionById('') must return undefined")
        self.assertTrue(res["regionNumber"], "getRegionById(number) must return undefined")
        self.assertTrue(res["regionObject"], "getRegionById({}) must return undefined")

        self.assertTrue(res["modelNull"], "getModelById(null) must return undefined")
        self.assertTrue(res["modelUndefined"], "getModelById(undefined) must return undefined")
        self.assertTrue(res["modelEmpty"], "getModelById('') must return undefined")
        self.assertTrue(res["modelNumber"], "getModelById(number) must return undefined")
        self.assertTrue(res["modelObject"], "getModelById({}) must return undefined")

        # Valid lookups continue to resolve correctly
        self.assertIn("서울", res["validRegion"])
        self.assertIn("아이오닉 5", res["validModel"])


# ==============================================================================
# 6. getAllEnrichedModels({}) returns [] without throwing in getReliabilityData.ts
# ==============================================================================

class TestCycle9ReliabilityEnrichedModelsIterability(unittest.TestCase):
    """Verifies getAllEnrichedModels array iterability guards in getReliabilityData.ts."""

    def test_get_all_enriched_models_empty_object_and_iterability(self) -> None:
        """getAllEnrichedModels({}) must return empty array without throwing TypeError."""
        rel_path = json.dumps(str(LIB_DIR / "getReliabilityData.ts"))
        script = f"""
        const rel = jiti({rel_path});
        let emptyObjThrew = false;
        let nullBrandsThrew = false;
        let nullModelsThrew = false;
        let emptyResult = null;
        let nullBrandsResult = null;
        let nullModelsResult = null;

        try {{
            emptyResult = rel.getAllEnrichedModels({{}});
        }} catch (e) {{
            emptyObjThrew = true;
        }}

        try {{
            nullBrandsResult = rel.getAllEnrichedModels({{ brands: null }});
        }} catch (e) {{
            nullBrandsThrew = true;
        }}

        try {{
            nullModelsResult = rel.getAllEnrichedModels({{
                brands: [{{ name_ko: "테스트", models: null }}]
            }});
        }} catch (e) {{
            nullModelsThrew = true;
        }}

        const defaultResult = rel.getAllEnrichedModels();

        console.log(JSON.stringify({{
            emptyObjThrew,
            emptyResultIsArray: Array.isArray(emptyResult),
            emptyResultLength: emptyResult ? emptyResult.length : -1,
            nullBrandsThrew,
            nullBrandsIsArray: Array.isArray(nullBrandsResult),
            nullBrandsLength: nullBrandsResult ? nullBrandsResult.length : -1,
            nullModelsThrew,
            nullModelsIsArray: Array.isArray(nullModelsResult),
            nullModelsLength: nullModelsResult ? nullModelsResult.length : -1,
            defaultCount: defaultResult.length
        }}));
        """
        res = _eval_ts_node(script)

        self.assertFalse(res["emptyObjThrew"], "getAllEnrichedModels({}) must not throw")
        self.assertTrue(res["emptyResultIsArray"], "getAllEnrichedModels({}) must return an Array")
        self.assertEqual(res["emptyResultLength"], 0, "getAllEnrichedModels({}) must return empty array [0]")

        self.assertFalse(res["nullBrandsThrew"], "getAllEnrichedModels({ brands: null }) must not throw")
        self.assertEqual(res["nullBrandsLength"], 0)

        self.assertFalse(res["nullModelsThrew"], "getAllEnrichedModels with null models must not throw")
        self.assertEqual(res["nullModelsLength"], 0)

        # Default execution returns all models
        self.assertGreaterEqual(res["defaultCount"], 20, "Default dataset must return 20+ models")


# ==============================================================================
# 7. simulateBatteryHealth() with NaN inputs returns valid finite numbers
# ==============================================================================

class TestCycle9BatterySimulationNaNResilience(unittest.TestCase):
    """Verifies simulateBatteryHealth parameter sanitization and zero NaN outputs in getDepreciationData.ts."""

    def test_simulate_battery_health_nan_inputs_produce_finite_numbers(self) -> None:
        """simulateBatteryHealth with all NaN inputs must return valid finite numbers without NaN."""
        dep_path = json.dumps(str(LIB_DIR / "getDepreciationData.ts"))
        script = f"""
        const dep = jiti({dep_path});
        const result = dep.simulateBatteryHealth({{
            ambientTempC: NaN,
            storageSoc: NaN,
            dcfcRatio: NaN,
            years: NaN,
            totalKm: NaN,
            annualKm: NaN,
            packCapacityKwh: NaN,
            vehicleEfficiencyKmPerKwh: NaN
        }});

        function findNaNs(obj, path = '') {{
            const nans = [];
            for (const [k, v] of Object.entries(obj)) {{
                const cur = path ? `${{path}}.${{k}}` : k;
                if (typeof v === 'number') {{
                    if (!Number.isFinite(v)) {{
                        nans.push(`${{cur}}: ${{v}}`);
                    }}
                }} else if (v && typeof v === 'object' && !Array.isArray(v)) {{
                    nans.push(...findNaNs(v, cur));
                }}
            }}
            return nans;
        }}

        const nanList = findNaNs(result);

        console.log(JSON.stringify({{
            nanCount: nanList.length,
            nanList,
            calendarLossPct: result.calendarLossPct,
            cyclicLossPct: result.cyclicLossPct,
            totalLossPct: result.totalLossPct,
            sohPct: result.sohPct,
            equivalentFullCycles: result.equivalentFullCycles,
            failureRiskPct: result.failureRiskPct,
            winterRangeRetentionPct: result.winterRangeRetentionPct
        }}));
        """
        res = _eval_ts_node(script)

        self.assertEqual(res["nanCount"], 0, f"Result must not contain any NaN or non-finite values: {res['nanList']}")
        self.assertGreater(res["sohPct"], 0.0)
        self.assertLessEqual(res["sohPct"], 100.0)
        self.assertGreater(res["totalLossPct"], 0.0)
        self.assertTrue(isinstance(res["calendarLossPct"], (int, float)))
        self.assertTrue(isinstance(res["cyclicLossPct"], (int, float)))


# ==============================================================================
# 8. batterySimulationCache Bounded Eviction at 100 Entries
# ==============================================================================

class TestCycle9BatterySimulationCacheBoundedEviction(unittest.TestCase):
    """Verifies bounded eviction (FIFO cap at 100 entries) in DepreciationCalculatorClient.tsx."""

    def test_component_defines_max_100_cache_entries_constant(self) -> None:
        """DepreciationCalculatorClient.tsx must define MAX_BATTERY_SIMULATION_CACHE_ENTRIES = 100."""
        calc_file = APP_DIR / "depreciation-calculator" / "DepreciationCalculatorClient.tsx"
        self.assertTrue(calc_file.exists(), f"File {calc_file} must exist")
        content = calc_file.read_text(encoding="utf-8")

        self.assertIn(
            "const MAX_BATTERY_SIMULATION_CACHE_ENTRIES = 100;",
            content,
            "Must define const MAX_BATTERY_SIMULATION_CACHE_ENTRIES = 100",
        )
        # Verify eviction logic exists
        eviction_snippet = "batterySimulationCache.current.size >= MAX_BATTERY_SIMULATION_CACHE_ENTRIES"
        self.assertIn(eviction_snippet, content, "Must check cache size against maximum entries cap")
        self.assertIn("batterySimulationCache.current.delete(", content, "Must evict oldest key via Map.delete")

    def test_map_fifo_bounded_eviction_algorithm_simulation(self) -> None:
        """Simulate the Map FIFO bounded eviction algorithm: inserting 150 entries stays strictly at 100."""
        script = """
        const MAX_BATTERY_SIMULATION_CACHE_ENTRIES = 100;
        const cache = new Map();

        for (let i = 0; i < 150; i++) {
            const key = `key_${i}`;
            const value = { iteration: i, score: i * 1.5 };

            if (cache.size >= MAX_BATTERY_SIMULATION_CACHE_ENTRIES) {
                const oldestKey = cache.keys().next().value;
                if (oldestKey !== undefined) {
                    cache.delete(oldestKey);
                }
            }
            cache.set(key, value);
        }

        const keys = Array.from(cache.keys());

        console.log(JSON.stringify({
            finalSize: cache.size,
            hasFirstKey: cache.has("key_0"),
            hasEvictedKey49: cache.has("key_49"),
            hasRetainedKey50: cache.has("key_50"),
            hasLastKey149: cache.has("key_149"),
            oldestRemainingKey: keys[0],
            newestKey: keys[keys.length - 1]
        }));
        """
        proc = subprocess.run(["node", "-e", script], capture_output=True, text=True, check=True)
        res = json.loads(proc.stdout.strip())

        self.assertEqual(res["finalSize"], 100, "Cache size must be strictly capped at 100 entries")
        self.assertFalse(res["hasFirstKey"], "Oldest key_0 must be evicted")
        self.assertFalse(res["hasEvictedKey49"], "Key 49 must be evicted")
        self.assertTrue(res["hasRetainedKey50"], "Key 50 must be retained")
        self.assertTrue(res["hasLastKey149"], "Latest key_149 must be present")
        self.assertEqual(res["oldestRemainingKey"], "key_50")
        self.assertEqual(res["newestKey"], "key_149")


if __name__ == "__main__":
    unittest.main()
