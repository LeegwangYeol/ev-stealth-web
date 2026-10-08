"""JSON Writer and Report Formatter for Daily EV Monitoring Pipeline.

Outputs structured JSON reports matching PROJECT.md § Interface Contracts to:
/Users/a7890/src/my-e-car/ev-stealth-web/src/data/daily_reports.json

Authoritative source:
- /Users/a7890/src/my-e-car/.agents/orchestrator_daily_monitor/PROJECT.md § Interface Contracts
- /Users/a7890/src/my-e-car/.agents/spec_miner_nlp_workflow/specifications.md § 3.3
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, Iterable, List, Optional, Union

from models.complaint import (
    ComplaintRecord,
    DailyReportPayload,
    DailyReportStatistics,
)


_CURRENT_DIR = Path(__file__).resolve().parent
_CANDIDATE_PATHS = [
    _CURRENT_DIR.parent / "ev-stealth-web" / "src" / "data" / "daily_reports.json",
    _CURRENT_DIR.parent / "src" / "data" / "daily_reports.json",
    _CURRENT_DIR.parent / "data" / "daily_reports.json",
]
DEFAULT_OUTPUT_PATH = str(
    next((p for p in _CANDIDATE_PATHS if p.parent.exists()), _CANDIDATE_PATHS[0])
)


def _safe_float(val: Any, default: float) -> float:
    """Safely convert value to float, returning default on None, ValueError, or TypeError."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _extract_record_date(record: Dict[str, Any]) -> str:
    """Extract normalized YYYY-MM-DD date string from a complaint record dict."""
    for field in ("date", "created_at", "timestamp"):
        val = record.get(field)
        if not val:
            continue
        val_str = str(val).strip()
        if len(val_str) >= 10 and val_str[4] in ("-", "/") and val_str[7] in ("-", "/"):
            return val_str[:10].replace("/", "-")
        try:
            dt = datetime.fromisoformat(val_str.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
    return ""


def format_daily_report_payload(
    complaints: Iterable[Union[ComplaintRecord, Dict[str, Any]]],
    total_scraped: Optional[int] = None,
    pipeline_version: str = "1.0.0",
    generated_at: Optional[str] = None,
) -> DailyReportPayload:
    """Transform complaint records into a validated DailyReportPayload object."""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat()

    report_dicts: List[Dict[str, Any]] = []
    negativity_scores: List[float] = []
    critical_count = 0
    category_counts: Counter[str] = Counter()

    for item in complaints:
        if isinstance(item, ComplaintRecord):
            # Only include authentic defects in daily reports
            if not item.is_authentic_defect:
                continue
            record_dict = item.to_admin_report_dict()
            neg_score = item.negativity_score
            is_critical = item.severity_tier == "CRITICAL"
            category = item.defect_category
        elif isinstance(item, dict):
            # Check is_authentic_defect if provided
            if not item.get("is_authentic_defect", True):
                continue
            record_dict = dict(item)
            # Ensure required aliases
            if "sentiment_score" not in record_dict and "negativity_score" in record_dict:
                record_dict["sentiment_score"] = record_dict["negativity_score"]
            if "slang_tags" not in record_dict and "slang_terms_detected" in record_dict:
                record_dict["slang_tags"] = record_dict["slang_terms_detected"]
            if "raw_quote" not in record_dict and "verbatim_quote" in record_dict:
                record_dict["raw_quote"] = record_dict["verbatim_quote"]

            neg_score = _safe_float(record_dict.get("negativity_score") or record_dict.get("sentiment_score"), 0.5)
            sev_idx = _safe_float(record_dict.get("severity_index"), 0.0)
            is_critical = record_dict.get("severity") == "CRITICAL" or sev_idx >= 8.0
            raw_cat = record_dict.get("defect_category")
            category = str(raw_cat) if raw_cat and str(raw_cat) != "None" else "BUILD_QUALITY"
        else:
            continue

        report_dicts.append(record_dict)
        negativity_scores.append(neg_score)
        if is_critical:
            critical_count += 1
        category_counts[category] += 1

    total_filtered = len(report_dicts)
    computed_total_scraped = total_scraped if total_scraped is not None else total_filtered
    avg_neg = (sum(negativity_scores) / total_filtered) if total_filtered > 0 else 0.0

    # Build category breakdown
    top_categories = []
    for cat, count in category_counts.most_common():
        ratio = round(count / total_filtered, 3) if total_filtered > 0 else 0.0
        top_categories.append({
            "category": cat,
            "count": count,
            "ratio": ratio,
        })

    statistics = DailyReportStatistics(
        total_scraped=computed_total_scraped,
        total_filtered_defects=total_filtered,
        avg_negativity_score=round(avg_neg, 2),
        critical_defect_count=critical_count,
    )

    # Accurately compute total_complaints_today based on generated_at date
    target_date_str = ""
    if generated_at:
        if len(generated_at) >= 10 and generated_at[4] in ("-", "/") and generated_at[7] in ("-", "/"):
            target_date_str = generated_at[:10].replace("/", "-")
        else:
            try:
                target_date_str = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).strftime("%Y-%m-%d")
            except Exception:
                pass
    if not target_date_str:
        target_date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    dated_records = 0
    today_matches = 0
    for r in report_dicts:
        r_date = _extract_record_date(r)
        if r_date:
            dated_records += 1
            if r_date == target_date_str:
                today_matches += 1

    if dated_records == 0 and total_filtered > 0:
        total_today = total_filtered
    else:
        undated_count = total_filtered - dated_records
        total_today = today_matches + undated_count

    return DailyReportPayload(
        generated_at=generated_at,
        pipeline_version=pipeline_version,
        statistics=statistics,
        reports=report_dicts,
        total_complaints_today=total_today,
        top_defect_categories=top_categories,
    )


def write_daily_reports(
    complaints: Iterable[Union[ComplaintRecord, Dict[str, Any]]],
    output_path: str = DEFAULT_OUTPUT_PATH,
    total_scraped: Optional[int] = None,
    pipeline_version: str = "1.0.0",
    generated_at: Optional[str] = None,
    merge_existing: bool = True,
) -> str:
    """Format and atomically write daily reports JSON to the destination path.

    Deduplicates by ID/URL and merges newly discovered defects with existing
    historical reports when merge_existing is True and output_path exists.
    Returns the absolute path written.
    """
    items_to_write: List[Union[ComplaintRecord, Dict[str, Any]]] = list(complaints)

    existing_reports: List[Dict[str, Any]] = []
    existing_total_scraped = 0
    if merge_existing and os.path.exists(output_path):
        try:
            existing_data = read_daily_reports(output_path)
            existing_reports = existing_data.get("reports", [])
            existing_total_scraped = existing_data.get("statistics", {}).get("total_scraped", 0)
        except Exception:
            existing_reports = []
            existing_total_scraped = 0

    # Extract new complaint dicts to index by id and url
    new_payload = format_daily_report_payload(
        complaints=items_to_write,
        total_scraped=total_scraped,
        pipeline_version=pipeline_version,
        generated_at=generated_at,
    )
    new_reports = new_payload.reports

    seen_ids = set()
    seen_urls = set()
    merged_reports: List[Dict[str, Any]] = []

    for nr in new_reports:
        nid = nr.get("id")
        nurl = nr.get("url")
        if (nid and nid in seen_ids) or (nurl and nurl in seen_urls):
            continue
        if nid:
            seen_ids.add(nid)
        if nurl:
            seen_urls.add(nurl)
        merged_reports.append(nr)

    for er in existing_reports:
        eid = er.get("id")
        eurl = er.get("url")
        if (eid and eid in seen_ids) or (eurl and eurl in seen_urls):
            continue
        if eid:
            seen_ids.add(eid)
        if eurl:
            seen_urls.add(eurl)
        merged_reports.append(er)

    combined_total_scraped = (
        (existing_total_scraped + total_scraped)
        if total_scraped is not None
        else max(existing_total_scraped, len(merged_reports))
    )
    items_to_write = merged_reports
    total_scraped = combined_total_scraped

    payload = format_daily_report_payload(
        complaints=items_to_write,
        total_scraped=total_scraped,
        pipeline_version=pipeline_version,
        generated_at=generated_at,
    )

    data = payload.to_dict()

    # Ensure parent directory exists
    dir_path = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(dir_path, exist_ok=True)

    # Perform atomic write via temporary file with crash durability (flush + fsync)
    temp_dir = dir_path
    temp_name: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
            temp_name = tf.name
            json.dump(data, tf, ensure_ascii=False, indent=2)
            tf.flush()
            os.fsync(tf.fileno())

        try:
            os.chmod(temp_name, 0o644)
        except OSError:
            pass
        os.replace(temp_name, output_path)
        temp_name = None
    finally:
        if temp_name and os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass

    return output_path


def read_daily_reports(path: str = DEFAULT_OUTPUT_PATH) -> Dict[str, Any]:
    """Read and parse daily reports JSON from file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
