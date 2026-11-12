#!/usr/bin/env python3
"""
scripts/sync_defect_reports.py - Defect Reports Synchronization and Deduplication Engine.

Provides transactional, crash-durable, bidirectional synchronization of community
defect reports (daily_reports.json) across:
- ev-stealth-web/src/data/daily_reports.json
- ev-stealth-web/data/daily_reports.json
- data/daily_reports.json
- public/data/daily_reports.json (and web mirror)

Key Capabilities:
1. Reliable Deduplication:
   - Primary matching by report ID.
   - Secondary matching by canonical URL / post_url.
   - Fallback matching by composite key: (source, vehicle_model, date, normalized_title).
   - Rich record merging: unions slang tags, merges DSI breakdown scores, retains latest metadata.
2. Robust Advisory Locking:
   - Advisory file lock on .sync_defect_reports.lock with configurable acquisition timeout.
   - Automatic stale lock detection, dead-PID validation, and unheld lock cleanup.
3. TypeScript Strict Type Parity:
   - Conforms strictly to DailyReportData and DefectReportItem interfaces in src/types/reports.ts.
   - Automatic recalculation of statistics (total_filtered_defects, avg_negativity_score,
     critical_defect_count, top_model, top_platform) and top_defect_categories.
4. POSIX Atomic File Replacement:
   - Writes via NamedTemporaryFile, fsync, atomic rename (os.replace), and parent directory fsync.
   - Bitwise SHA-256 and mtime parity preservation across all mirrored datasets.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# Base logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] [sync_defect_reports] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sync_defect_reports")

# Adaptive repository root resolution
def find_repo_root() -> Path:
    """Resolve the root directory containing data/ and ev-stealth-web/."""
    candidates = [
        Path(__file__).resolve().parent.parent.parent,
        Path(__file__).resolve().parent.parent,
        Path.cwd(),
        Path.cwd().parent,
    ]
    for cand in candidates:
        if (cand / "ev-stealth-web").is_dir() and (cand / "data").is_dir():
            return cand
    for cand in candidates:
        if (cand / "src" / "data").is_dir():
            return cand.parent if cand.name == "ev-stealth-web" else cand
    return Path(__file__).resolve().parent.parent.parent

REPO_ROOT = find_repo_root()
WEB_ROOT = REPO_ROOT / "ev-stealth-web" if (REPO_ROOT / "ev-stealth-web").is_dir() else REPO_ROOT

# Ensure tracker modules can be imported
for sys_dir in (str(REPO_ROOT), str(WEB_ROOT)):
    if sys_dir not in sys.path:
        sys.path.insert(0, sys_dir)

try:
    from tracker.atomic_writer import (
        FileLock,
        cleanup_stale_lock_files,
        is_corrupted_or_quarantined_filename,
        quarantine_corrupted_file,
    )
except ImportError:
    # Standalone fallback if tracker is not in python path
    FileLock = None  # type: ignore
    cleanup_stale_lock_files = None  # type: ignore
    is_corrupted_or_quarantined_filename = lambda p: False  # type: ignore
    quarantine_corrupted_file = lambda p: p  # type: ignore

DEFAULT_LOCK_TIMEOUT = 15.0
DEFAULT_STALE_TIMEOUT = 60.0
LOCK_FILE_NAME = ".sync_defect_reports.lock"

# Standard defect categories recognized in src/types/reports.ts
VALID_DEFECT_CATEGORIES = {
    "BATTERY_CHARGING",
    "DRIVING_POWERTRAIN",
    "BUILD_QUALITY",
    "SOFTWARE_ELECTRONICS",
    "SERVICE_REPAIR_COST",
    "COLD_WEATHER",
}

VALID_SEVERITIES = {
    "CRITICAL",
    "HIGH",
    "WARNING",
    "MEDIUM",
    "CAUTION",
    "LOW",
    "INFO",
}


# =============================================================================
# DEDUPLICATION & COMPOSITE KEY GENERATION
# =============================================================================

def normalize_text_for_key(text: Optional[str]) -> str:
    """Normalize text string by trimming, lowercasing, and collapsing whitespace."""
    if not text:
        return ""
    # Collapse multiple whitespaces and remove non-alphanumeric punctuation for stable matching
    s = str(text).strip().lower()
    return re.sub(r"\s+", " ", s)


def normalize_url_for_key(url: Optional[str]) -> str:
    """Normalize URL by stripping protocol prefix, hash anchors, and trailing slashes."""
    if not url:
        return ""
    u = str(url).strip()
    u = u.split("#")[0]
    u = re.sub(r"^https?://(www\.)?", "", u)
    return u.rstrip("/")


def build_composite_key(report: Dict[str, Any]) -> str:
    """Construct a deterministic composite key for a defect report item.
    
    Uses platform/source, vehicle model, normalized date, and cleaned title.
    """
    source = normalize_text_for_key(report.get("source") or report.get("platform") or "unknown")
    model = normalize_text_for_key(report.get("vehicle_model") or report.get("target_vehicle") or "general")
    date_val = str(report.get("date") or report.get("created_at") or "")[:10]
    title = normalize_text_for_key(report.get("title") or report.get("post_title") or "")
    if len(title) > 64:
        title = title[:64]
    return f"comp::{source}::{model}::{date_val}::{title}"


def get_report_primary_id(report: Dict[str, Any]) -> Optional[str]:
    """Extract report ID if valid and non-trivial."""
    rep_id = str(report.get("id") or "").strip()
    if rep_id and rep_id.lower() not in ("none", "null", "undefined", "0", ""):
        return rep_id
    return None


def get_report_url_key(report: Dict[str, Any]) -> Optional[str]:
    """Extract normalized URL key if present."""
    url = report.get("url") or report.get("post_url")
    norm_url = normalize_url_for_key(url)
    return f"url::{norm_url}" if norm_url else None


def merge_report_records(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    """Merge an incoming duplicate report record into existing record.
    
    Preserves existing non-empty values, incorporates newer metadata,
    unions slang tags, and merges DSI breakdowns.
    """
    merged = dict(existing)

    # 1. Scalar string values: prefer non-empty and longer content
    for text_key in (
        "summary",
        "verbatim_quote",
        "raw_quote",
        "defect_category_ko",
        "category",
        "vehicle_brand",
        "target_vehicle",
        "author",
        "post_title",
        "url",
        "post_url",
        "platform",
    ):
        inc_val = incoming.get(text_key)
        ex_val = merged.get(text_key)
        if (not ex_val or str(ex_val).strip() == "") and inc_val:
            merged[text_key] = inc_val
        elif inc_val and ex_val and len(str(inc_val).strip()) > len(str(ex_val).strip()):
            merged[text_key] = inc_val

    # 2. Date / Created_at: take the most detailed timestamp
    ex_created = str(merged.get("created_at") or "")
    inc_created = str(incoming.get("created_at") or "")
    if inc_created and (not ex_created or inc_created > ex_created):
        merged["created_at"] = inc_created
        if incoming.get("date"):
            merged["date"] = str(incoming["date"])[:10]

    # 3. Slang tags: set union preserving deterministic order
    ex_tags = list(merged.get("slang_tags") or [])
    inc_tags = list(incoming.get("slang_tags") or [])
    seen_tags = set(ex_tags)
    for tag in inc_tags:
        if tag and tag not in seen_tags:
            ex_tags.append(tag)
            seen_tags.add(tag)
    merged["slang_tags"] = ex_tags

    # Slang terms detected
    ex_terms = list(merged.get("slang_terms_detected") or [])
    inc_terms = list(incoming.get("slang_terms_detected") or [])
    seen_terms = set(ex_terms)
    for term in inc_terms:
        if term and term not in seen_terms:
            ex_terms.append(term)
            seen_terms.add(term)
    if ex_terms:
        merged["slang_terms_detected"] = ex_terms

    # 4. Sentiment and Severity: retain maximum severity and highest negativity
    try:
        ex_neg = float(merged.get("negativity_score", merged.get("sentiment_score", 0.0)))
        inc_neg = float(incoming.get("negativity_score", incoming.get("sentiment_score", 0.0)))
        if inc_neg > ex_neg:
            merged["negativity_score"] = round(inc_neg, 4)
            merged["sentiment_score"] = round(inc_neg, 4)
    except (ValueError, TypeError):
        pass

    severity_order = {"INFO": 0, "LOW": 1, "CAUTION": 2, "MEDIUM": 3, "WARNING": 4, "HIGH": 5, "CRITICAL": 6}
    ex_sev_rank = severity_order.get(str(merged.get("severity", "")).upper(), 2)
    inc_sev_rank = severity_order.get(str(incoming.get("severity", "")).upper(), 2)
    if inc_sev_rank > ex_sev_rank:
        merged["severity"] = incoming.get("severity")

    # 5. DSI breakdown: combine metrics
    ex_dsi = merged.get("dsi_breakdown")
    inc_dsi = incoming.get("dsi_breakdown")
    if isinstance(inc_dsi, dict):
        if not isinstance(ex_dsi, dict):
            merged["dsi_breakdown"] = dict(inc_dsi)
        else:
            merged_dsi = dict(ex_dsi)
            for dim, val in inc_dsi.items():
                if val is not None:
                    try:
                        f_val = float(val)
                        if dim not in merged_dsi or float(merged_dsi[dim]) < f_val:
                            merged_dsi[dim] = f_val
                    except (ValueError, TypeError):
                        pass
            merged["dsi_breakdown"] = merged_dsi

    # 6. Authenticity flag
    if "is_authentic_defect" in incoming:
        merged["is_authentic_defect"] = bool(incoming["is_authentic_defect"])

    return merged


def deduplicate_reports(reports: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Deduplicate reports list reliably by ID, URL, or composite key.
    
    Returns:
        (deduplicated_reports_list, count_of_duplicates_removed)
    """
    if not reports:
        return [], 0

    id_index: Dict[str, int] = {}
    url_index: Dict[str, int] = {}
    comp_index: Dict[str, int] = {}

    deduped: List[Dict[str, Any]] = []
    duplicates_count = 0

    for rep in reports:
        if not isinstance(rep, dict):
            continue

        rep_id = get_report_primary_id(rep)
        url_key = get_report_url_key(rep)
        comp_key = build_composite_key(rep)

        target_idx: Optional[int] = None

        # Check existing indices in priority order: ID -> URL -> Composite Key
        if rep_id and rep_id in id_index:
            target_idx = id_index[rep_id]
        elif url_key and url_key in url_index:
            target_idx = url_index[url_key]
        elif comp_key and comp_key in comp_index:
            target_idx = comp_index[comp_key]

        if target_idx is not None:
            # Duplicate found: merge incoming into target
            deduped[target_idx] = merge_report_records(deduped[target_idx], rep)
            duplicates_count += 1
            # Ensure new keys are mapped to this target
            if rep_id:
                id_index[rep_id] = target_idx
            if url_key:
                url_index[url_key] = target_idx
            comp_index[comp_key] = target_idx
        else:
            # New unique item
            new_idx = len(deduped)
            deduped.append(dict(rep))
            if rep_id:
                id_index[rep_id] = new_idx
            if url_key:
                url_index[url_key] = new_idx
            comp_index[comp_key] = new_idx

    return deduped, duplicates_count


# =============================================================================
# TYPESCRIPT SCHEMA PARITY & NORMALIZATION (src/types/reports.ts)
# =============================================================================

def normalize_report_item(item: Dict[str, Any], default_idx: int = 1) -> Dict[str, Any]:
    """Normalize a defect report item to strictly adhere to DefectReportItem TypeScript interface."""
    normalized: Dict[str, Any] = {}

    # Required: id (string)
    raw_id = item.get("id")
    if raw_id is not None and str(raw_id).strip() not in ("", "none", "null", "undefined"):
        normalized["id"] = str(raw_id).strip()
    else:
        # Generate deterministic stable ID from composite key
        comp = build_composite_key(item)
        short_hash = hashlib.sha256(comp.encode("utf-8")).hexdigest()[:10]
        normalized["id"] = f"defect_{short_hash}"

    # Required: source (string)
    normalized["source"] = str(item.get("source") or item.get("platform") or "community").strip()

    # Optional: platform
    if item.get("platform"):
        normalized["platform"] = str(item["platform"]).strip()
    else:
        normalized["platform"] = normalized["source"]

    # Optional: url & post_url
    url_val = item.get("url") or item.get("post_url")
    if url_val:
        normalized["url"] = str(url_val).strip()
        normalized["post_url"] = str(url_val).strip()

    # Required: title (string)
    title = str(item.get("title") or item.get("post_title") or "Untitled Defect Report").strip()
    normalized["title"] = title
    normalized["post_title"] = str(item.get("post_title") or title).strip()

    # Optional: author
    if "author" in item and item["author"] is not None:
        normalized["author"] = str(item["author"]).strip()

    # Required: date (string, YYYY-MM-DD)
    date_val = str(item.get("date") or item.get("created_at") or "")[:10]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date_val):
        date_val = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    normalized["date"] = date_val

    # Optional: created_at (string, ISO-8601)
    if item.get("created_at"):
        normalized["created_at"] = str(item["created_at"]).strip()
    else:
        normalized["created_at"] = f"{date_val}T00:00:00+00:00"

    # Optional: vehicle_brand
    if item.get("vehicle_brand"):
        normalized["vehicle_brand"] = str(item["vehicle_brand"]).strip()

    # Required: vehicle_model (string)
    model = str(item.get("vehicle_model") or item.get("target_vehicle") or "전기차").strip()
    normalized["vehicle_model"] = model
    if item.get("target_vehicle"):
        normalized["target_vehicle"] = str(item["target_vehicle"]).strip()
    elif normalized.get("vehicle_brand"):
        normalized["target_vehicle"] = f"{normalized['vehicle_brand']} {model}".strip()

    # Required: defect_category (DefectCategoryCode)
    cat = str(item.get("defect_category") or item.get("category") or "BUILD_QUALITY").strip().upper()
    if cat not in VALID_DEFECT_CATEGORIES:
        cat = "BUILD_QUALITY"
    normalized["defect_category"] = cat
    normalized["category"] = cat

    # Optional: defect_category_ko
    category_ko_map = {
        "BATTERY_CHARGING": "배터리/충전",
        "DRIVING_POWERTRAIN": "동력계통/주행",
        "BUILD_QUALITY": "외장/마감/조립",
        "SOFTWARE_ELECTRONICS": "소프트웨어/전장",
        "SERVICE_REPAIR_COST": "AS/수리비",
        "COLD_WEATHER": "저온/동절기",
    }
    normalized["defect_category_ko"] = str(
        item.get("defect_category_ko") or category_ko_map.get(cat, "기타 결함")
    )

    # Required: summary (string)
    summary = str(item.get("summary") or "").strip()
    if not summary:
        summary = f"[{model}] {normalized['defect_category_ko']}: {title}"
    normalized["summary"] = summary

    # Optional: verbatim_quote & raw_quote
    quote = str(item.get("verbatim_quote") or item.get("raw_quote") or "").strip()
    if quote:
        normalized["verbatim_quote"] = quote
        normalized["raw_quote"] = quote

    # Required: slang_tags (string[])
    tags = item.get("slang_tags")
    if isinstance(tags, list):
        normalized["slang_tags"] = [str(t).strip() for t in tags if str(t).strip()]
    else:
        normalized["slang_tags"] = []

    # Optional: slang_terms_detected (string[])
    terms = item.get("slang_terms_detected")
    if isinstance(terms, list):
        normalized["slang_terms_detected"] = [str(t).strip() for t in terms if str(t).strip()]

    # Required: sentiment_score (number, float)
    try:
        score = float(item.get("sentiment_score", item.get("negativity_score", 0.5)))
        normalized["sentiment_score"] = round(max(0.0, min(1.0, score)), 4)
    except (ValueError, TypeError):
        normalized["sentiment_score"] = 0.5

    # Optional: sentiment_polarity (number)
    if "sentiment_polarity" in item and item["sentiment_polarity"] is not None:
        try:
            normalized["sentiment_polarity"] = round(float(item["sentiment_polarity"]), 4)
        except (ValueError, TypeError):
            pass

    # Optional: negativity_score (number)
    try:
        neg = float(item.get("negativity_score", normalized["sentiment_score"]))
        normalized["negativity_score"] = round(max(0.0, min(1.0, neg)), 4)
    except (ValueError, TypeError):
        normalized["negativity_score"] = normalized["sentiment_score"]

    # Optional: sentiment_tier (string)
    if item.get("sentiment_tier"):
        normalized["sentiment_tier"] = str(item["sentiment_tier"]).strip()
    else:
        ns = normalized["negativity_score"]
        if ns >= 0.85:
            normalized["sentiment_tier"] = "STRONGLY_NEGATIVE"
        elif ns >= 0.65:
            normalized["sentiment_tier"] = "NEGATIVE"
        elif ns >= 0.40:
            normalized["sentiment_tier"] = "NEUTRAL"
        else:
            normalized["sentiment_tier"] = "POSITIVE"

    # Required: severity (SeverityLevel)
    sev = str(item.get("severity") or "MEDIUM").strip().upper()
    if sev not in VALID_SEVERITIES:
        sev = "MEDIUM"
    normalized["severity"] = sev

    # Optional: severity_index (number)
    if "severity_index" in item and item["severity_index"] is not None:
        try:
            normalized["severity_index"] = round(float(item["severity_index"]), 2)
        except (ValueError, TypeError):
            pass

    # Optional: is_authentic_defect (boolean)
    if "is_authentic_defect" in item and item["is_authentic_defect"] is not None:
        normalized["is_authentic_defect"] = bool(item["is_authentic_defect"])
    else:
        normalized["is_authentic_defect"] = True

    # Optional: dsi_breakdown (DsiBreakdown)
    raw_dsi = item.get("dsi_breakdown")
    if isinstance(raw_dsi, dict):
        clean_dsi: Dict[str, float] = {}
        for dim in ("safety", "functional", "economic", "social", "convenience"):
            if dim in raw_dsi and raw_dsi[dim] is not None:
                try:
                    clean_dsi[dim] = round(float(raw_dsi[dim]), 2)
                except (ValueError, TypeError):
                    pass
        if clean_dsi:
            normalized["dsi_breakdown"] = clean_dsi

    return normalized


def compute_report_statistics(
    reports: List[Dict[str, Any]],
    raw_scraped_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Compute DailyReportStatistics adhering to TypeScript definition."""
    total_defects = len(reports)
    total_scraped = max(raw_scraped_count or total_defects, total_defects)

    if reports:
        neg_scores = [float(r.get("negativity_score", r.get("sentiment_score", 0.0))) for r in reports]
        avg_negativity = round(sum(neg_scores) / len(neg_scores), 3)
    else:
        avg_negativity = 0.0

    critical_count = sum(1 for r in reports if str(r.get("severity", "")).upper() == "CRITICAL")

    # Find top model and platform
    model_counter = Counter(r.get("vehicle_model") for r in reports if r.get("vehicle_model"))
    platform_counter = Counter(r.get("platform") or r.get("source") for r in reports if r.get("platform") or r.get("source"))

    stats: Dict[str, Any] = {
        "total_scraped": total_scraped,
        "total_filtered_defects": total_defects,
        "avg_negativity_score": avg_negativity,
        "critical_defect_count": critical_count,
    }
    if model_counter:
        stats["top_model"] = model_counter.most_common(1)[0][0]
    if platform_counter:
        stats["top_platform"] = platform_counter.most_common(1)[0][0]

    return stats


def compute_top_categories(reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compute sorted top defect categories with frequency counts and ratios."""
    if not reports:
        return []
    total = len(reports)
    cat_counts = Counter(r.get("defect_category") or r.get("category") or "BUILD_QUALITY" for r in reports)
    categories_list = []
    for cat, count in cat_counts.most_common():
        categories_list.append({
            "category": cat,
            "count": count,
            "ratio": round(count / total, 3),
            "percentage": round((count / total) * 100, 1),
        })
    return categories_list


def build_canonical_payload(
    reports: List[Dict[str, Any]],
    existing_meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build fully conforming DailyReportData payload."""
    deduped_reports, _ = deduplicate_reports(reports)
    normalized_reports = [normalize_report_item(r, idx + 1) for idx, r in enumerate(deduped_reports)]

    existing = existing_meta or {}
    scraped_count = None
    if isinstance(existing.get("statistics"), dict):
        scraped_count = existing["statistics"].get("total_scraped")

    stats = compute_report_statistics(normalized_reports, raw_scraped_count=scraped_count)
    top_categories = compute_top_categories(normalized_reports)

    generated_at = existing.get("generated_at")
    if not generated_at or not isinstance(generated_at, str):
        generated_at = datetime.now(timezone.utc).isoformat()

    payload: Dict[str, Any] = {
        "generated_at": generated_at,
        "pipeline_version": existing.get("pipeline_version", "1.0.0"),
        "statistics": stats,
        "total_complaints_today": len(normalized_reports),
        "top_defect_categories": top_categories,
        "reports": normalized_reports,
    }
    return payload


# =============================================================================
# SYNCHRONIZATION & FILE LOCKING ENGINE
# =============================================================================

def validate_reports_file(path: Union[str, Path]) -> bool:
    """Validate that path exists and parses to valid JSON with a 'reports' key or list."""
    p = Path(path)
    if is_corrupted_or_quarantined_filename(p):
        return False
    if not p.is_file() or p.stat().st_size == 0:
        return False
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, dict):
            if "reports" in data and isinstance(data["reports"], list):
                return True
        elif isinstance(data, list):
            return all(isinstance(item, dict) for item in data)
        return False
    except Exception as exc:
        logger.debug("Validation failed for %s: %s", p, exc)
        return False


def load_reports_from_file(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Load defect reports and top-level metadata from file."""
    with open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if isinstance(data, dict):
        reports = data.get("reports", [])
        meta = {k: v for k, v in data.items() if k != "reports"}
        return (reports if isinstance(reports, list) else []), meta
    elif isinstance(data, list):
        return [r for r in data if isinstance(r, dict)], {}
    return [], {}


def get_default_known_paths(
    root_dir: Optional[Union[str, Path]] = None,
    web_dir: Optional[Union[str, Path]] = None,
) -> Tuple[Path, Path, List[Path]]:
    """Determine root_reports_path, web_reports_path, and public mirrors."""
    repo_root = REPO_ROOT

    # 1. Root reports path
    if root_dir:
        root_path = Path(root_dir) / "daily_reports.json" if Path(root_dir).is_dir() else Path(root_dir)
    elif (repo_root / "data").is_dir():
        root_path = repo_root / "data" / "daily_reports.json"
    else:
        root_path = Path.cwd() / "data" / "daily_reports.json"

    # 2. Web reports path (src/data/)
    if web_dir:
        w = Path(web_dir)
        if (w / "src" / "data").is_dir():
            web_path = w / "src" / "data" / "daily_reports.json"
        elif w.name == "data" and w.parent.name == "src":
            web_path = w / "daily_reports.json"
        elif (w / "daily_reports.json").is_file():
            web_path = w / "daily_reports.json"
        else:
            web_path = w / "daily_reports.json"
    elif (repo_root / "ev-stealth-web" / "src" / "data").is_dir():
        web_path = repo_root / "ev-stealth-web" / "src" / "data" / "daily_reports.json"
    elif (repo_root / "src" / "data").is_dir():
        web_path = repo_root / "src" / "data" / "daily_reports.json"
    else:
        web_path = Path.cwd() / "src" / "data" / "daily_reports.json"

    # 3. Additional targets
    is_custom_run = (root_dir is not None) or (web_dir is not None)
    if is_custom_run:
        additional: List[Path] = []
        if web_dir:
            w_parent = Path(web_dir).parent
            if (w_parent / "public" / "data").is_dir():
                additional.append(w_parent / "public" / "data" / "daily_reports.json")
            if (w_parent / "data").is_dir():
                additional.append(w_parent / "data" / "daily_reports.json")
        if root_dir:
            r_parent = Path(root_dir).parent
            if (r_parent / "public" / "data").is_dir():
                additional.append(r_parent / "public" / "data" / "daily_reports.json")
    else:
        additional = [
            repo_root / "ev-stealth-web" / "data" / "daily_reports.json",
            repo_root / "public" / "data" / "daily_reports.json",
            repo_root / "ev-stealth-web" / "public" / "data" / "daily_reports.json",
        ]

    # Deduplicate paths preserving order
    seen: Set[str] = set()
    deduped_additional: List[Path] = []
    for p in additional:
        try:
            res_str = str(p.resolve())
        except (OSError, RuntimeError):
            res_str = str(p.absolute())
        if res_str not in seen and res_str != str(root_path.resolve() if root_path.exists() else root_path):
            seen.add(res_str)
            deduped_additional.append(p)

    return root_path, web_path, deduped_additional


def sync_defect_reports(
    root_dir: Optional[Union[str, Path]] = None,
    web_dir: Optional[Union[str, Path]] = None,
    dry_run: bool = False,
    lock_timeout: float = DEFAULT_LOCK_TIMEOUT,
    stale_timeout: float = DEFAULT_STALE_TIMEOUT,
    quarantine_corrupted: bool = True,
    dedup_only: bool = False,
) -> List[str]:
    """Execute reliable, deduplicated defect report synchronization across all mirrors.
    
    Returns list of paths successfully synchronized.
    """
    root_reports_path, web_reports_path, additional_paths = get_default_known_paths(root_dir, web_dir)
    all_target_paths = [root_reports_path, web_reports_path] + additional_paths

    logger.info("Initiating defect reports synchronization...")
    logger.debug("Primary root: %s", root_reports_path)
    logger.debug("Primary web:  %s", web_reports_path)

    if dry_run:
        logger.info("[DRY-RUN] Defect reports synchronization completed with 0 writes.")
        return []

    # Prepare lock directory
    lock_dir = root_reports_path.parent
    lock_dir.mkdir(parents=True, exist_ok=True)
    sync_lock_path = lock_dir / LOCK_FILE_NAME

    # Clean up stale locks automatically
    if cleanup_stale_lock_files is not None:
        cleanup_stale_lock_files(lock_dir, prefix=(".sync_",), max_age_seconds=stale_timeout)
        if web_reports_path.parent != lock_dir and web_reports_path.parent.is_dir():
            cleanup_stale_lock_files(web_reports_path.parent, prefix=(".sync_",), max_age_seconds=stale_timeout)

    written_paths: List[str] = []

    # Acquire advisory file lock
    lock_ctx = FileLock(sync_lock_path, timeout=lock_timeout, stale_timeout=stale_timeout) if FileLock else None

    with lock_ctx if lock_ctx else open("/dev/null"):
        # Discover and sort candidate source files
        existing_candidates = [p for p in all_target_paths if p.is_file()]

        valid_sources: List[Path] = []
        for cand in existing_candidates:
            if is_corrupted_or_quarantined_filename(cand):
                continue
            if validate_reports_file(cand):
                valid_sources.append(cand)
            elif quarantine_corrupted:
                logger.warning("Quarantining invalid/corrupted defect report file: %s", cand)
                quarantine_corrupted_file(cand)

        if not valid_sources:
            logger.error("No valid candidate defect report files found among %s. Aborting sync.", existing_candidates)
            return []

        # Sort candidate sources by report count (descending) and mtime (descending)
        def _source_weight(path: Path) -> Tuple[int, float]:
            try:
                reports, _ = load_reports_from_file(path)
                return (len(reports), path.stat().st_mtime)
            except Exception:
                return (0, 0.0)

        valid_sources.sort(key=_source_weight, reverse=True)
        primary_source = valid_sources[0]
        logger.info("Selected primary defect report source: %s", primary_source)

        # Collect reports from primary source and any auxiliary sources for union deduplication
        all_reports: List[Dict[str, Any]] = []
        combined_meta: Dict[str, Any] = {}

        primary_reports, primary_meta = load_reports_from_file(primary_source)
        all_reports.extend(primary_reports)
        combined_meta.update(primary_meta)

        # Merge secondary valid sources if they contain unique reports
        for sec_source in valid_sources[1:]:
            try:
                sec_reports, _ = load_reports_from_file(sec_source)
                all_reports.extend(sec_reports)
            except Exception as e:
                logger.warning("Could not read secondary source %s: %s", sec_source, e)

        # Perform comprehensive deduplication
        deduped_reports, removed_dupes = deduplicate_reports(all_reports)
        if removed_dupes > 0:
            logger.info("Deduplicated %d redundant defect reports (retained %d unique).", removed_dupes, len(deduped_reports))
        else:
            logger.info("All %d defect reports are verified unique (0 duplicates).", len(deduped_reports))

        # Build canonical payload conforming to TypeScript types
        canonical_payload = build_canonical_payload(deduped_reports, existing_meta=combined_meta)
        canonical_json_bytes = json.dumps(canonical_payload, indent=2, ensure_ascii=False).encode("utf-8")
        canonical_hash = hashlib.sha256(canonical_json_bytes).hexdigest()

        # Target destinations to update
        destinations_to_write: List[Path] = []
        for target in all_target_paths:
            # Check if target already has identical SHA-256
            if target.is_file():
                try:
                    with open(target, "rb") as tf:
                        existing_hash = hashlib.sha256(tf.read()).hexdigest()
                    if existing_hash == canonical_hash:
                        logger.debug("Skipping redundant write for %s (SHA-256 match).", target)
                        continue
                except OSError:
                    pass
            destinations_to_write.append(target)

        # Atomically write canonical payload to all destinations
        source_mtime = primary_source.stat().st_mtime if primary_source.exists() else time.time()
        for dst in destinations_to_write:
            temp_name = None
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile("wb", dir=str(dst.parent), delete=False, prefix=".tmp_sync_") as tf:
                    temp_name = tf.name
                    tf.write(canonical_json_bytes)
                    tf.flush()
                    os.fsync(tf.fileno())

                try:
                    os.chmod(temp_name, 0o644)
                except OSError:
                    pass

                os.replace(temp_name, dst)
                temp_name = None

                # Maintain uniform timestamp across mirrors
                try:
                    os.utime(dst, (source_mtime, source_mtime))
                except OSError:
                    pass

                # Fsync parent directory to persist directory entry
                try:
                    dir_fd = os.open(str(dst.parent), os.O_RDONLY)
                    os.fsync(dir_fd)
                    os.close(dir_fd)
                except OSError:
                    pass

                written_paths.append(str(dst))
                logger.info("  ✓ Successfully synchronized and deduplicated: %s", dst)
            except Exception as exc:
                logger.error("Failed to atomically write defect report to %s: %s", dst, exc)
            finally:
                if temp_name and os.path.exists(temp_name):
                    try:
                        os.unlink(temp_name)
                    except OSError:
                        pass

    # Verify bitwise parity across existing main targets
    verified_mirrors = [p for p in [root_reports_path, web_reports_path] if p.is_file()]
    if len(verified_mirrors) == 2:
        with open(verified_mirrors[0], "rb") as f1, open(verified_mirrors[1], "rb") as f2:
            h1 = hashlib.sha256(f1.read()).hexdigest()
            h2 = hashlib.sha256(f2.read()).hexdigest()
        if h1 == h2:
            logger.info("Cryptographic parity verified: root <-> web SHA-256 match (%s).", h1[:12])
        else:
            logger.warning("Cryptographic parity mismatch: %s != %s", h1[:12], h2[:12])

    return written_paths


# =============================================================================
# CLI ENTRYPOINT
# =============================================================================

def parse_cli_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Autonomous Defect Reports Synchronization and Deduplication Tool"
    )
    parser.add_argument(
        "--root-dir",
        type=str,
        default=None,
        help="Root data directory containing daily_reports.json (default: repo root data/)",
    )
    parser.add_argument(
        "--web-dir",
        type=str,
        default=None,
        help="Web frontend directory containing src/data/ (default: ev-stealth-web/src/data/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate synchronization without modifying any files on disk",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_LOCK_TIMEOUT,
        help="Lock acquisition timeout in seconds (default: 15.0)",
    )
    parser.add_argument(
        "--stale-timeout",
        type=float,
        default=DEFAULT_STALE_TIMEOUT,
        help="Stale lock cleanup age threshold in seconds (default: 60.0)",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate schema and deduplication status without writing changes",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose debug logging",
    )
    return parser.parse_args()


def main() -> int:
    """CLI execution entrypoint."""
    args = parse_cli_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    try:
        if args.check_only:
            root_p, web_p, _ = get_default_known_paths(args.root_dir, args.web_dir)
            logger.info("Checking schema and integrity of %s and %s...", root_p, web_p)
            for p in (root_p, web_p):
                if not p.is_file():
                    logger.error("File does not exist: %s", p)
                    return 1
                valid = validate_reports_file(p)
                if not valid:
                    logger.error("Schema validation failed: %s", p)
                    return 1
                reports, _ = load_reports_from_file(p)
                deduped, count = deduplicate_reports(reports)
                logger.info("File %s: %d total reports, %d duplicates detected.", p, len(reports), count)
            logger.info("Check completed successfully. Files are healthy.")
            return 0

        written = sync_defect_reports(
            root_dir=args.root_dir,
            web_dir=args.web_dir,
            dry_run=args.dry_run,
            lock_timeout=args.timeout,
            stale_timeout=args.stale_timeout,
        )
        logger.info("Synchronization completed. Updated files: %d", len(written))
        return 0
    except Exception as exc:
        logger.exception("Synchronization aborted due to unhandled error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
