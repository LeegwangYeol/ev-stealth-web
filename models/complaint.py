"""Data models for raw scraped posts, classified complaints, and daily report JSON schemas.

Authoritative source:
- /Users/a7890/src/my-e-car/.agents/orchestrator_daily_monitor/PROJECT.md § Interface Contracts
- /Users/a7890/src/my-e-car/.agents/spec_miner_nlp_workflow/specifications.md
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import json
import math
import re
from typing import Any, Dict, List, Optional, Tuple, Union
import unicodedata


DEFECT_CATEGORY_KO_MAP: Dict[str, str] = {
    "BATTERY_CHARGING": "배터리/충전",
    "DRIVING_POWERTRAIN": "주행/모터/등판",
    "BUILD_QUALITY": "단차/누수/마감",
    "SOFTWARE_ELECTRONICS": "OTA/소프트웨어/먹통",
    "SERVICE_REPAIR_COST": "AS/수리비",
}

CANONICAL_CATEGORIES: List[str] = list(DEFECT_CATEGORY_KO_MAP.keys())

VALID_BRANDS: List[str] = ["Hyundai", "Kia", "Tesla", "BYD", "Other"]

VALID_SEVERITY_LEVELS: List[str] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

# Comprehensive category alias mapping for resilient normalization
CATEGORY_ALIASES: Dict[str, str] = {
    # BATTERY_CHARGING
    "BATTERY": "BATTERY_CHARGING",
    "CHARGING": "BATTERY_CHARGING",
    "BATTERY_CHARGING": "BATTERY_CHARGING",
    "배터리": "BATTERY_CHARGING",
    "충전": "BATTERY_CHARGING",
    "배터리/충전": "BATTERY_CHARGING",
    "배터리 충전": "BATTERY_CHARGING",
    "BMS": "BATTERY_CHARGING",
    "ICCU": "BATTERY_CHARGING",
    # DRIVING_POWERTRAIN
    "DRIVING": "DRIVING_POWERTRAIN",
    "POWERTRAIN": "DRIVING_POWERTRAIN",
    "DRIVING_POWERTRAIN": "DRIVING_POWERTRAIN",
    "주행": "DRIVING_POWERTRAIN",
    "모터": "DRIVING_POWERTRAIN",
    "등판": "DRIVING_POWERTRAIN",
    "주행/모터/등판": "DRIVING_POWERTRAIN",
    "주행 모터 등판": "DRIVING_POWERTRAIN",
    "제동": "DRIVING_POWERTRAIN",
    "조향": "DRIVING_POWERTRAIN",
    # BUILD_QUALITY
    "BUILD": "BUILD_QUALITY",
    "QUALITY": "BUILD_QUALITY",
    "BUILD_QUALITY": "BUILD_QUALITY",
    "단차": "BUILD_QUALITY",
    "누수": "BUILD_QUALITY",
    "마감": "BUILD_QUALITY",
    "단차/누수/마감": "BUILD_QUALITY",
    "단차 누수 마감": "BUILD_QUALITY",
    "조립": "BUILD_QUALITY",
    "외장": "BUILD_QUALITY",
    # SOFTWARE_ELECTRONICS
    "SOFTWARE": "SOFTWARE_ELECTRONICS",
    "ELECTRONICS": "SOFTWARE_ELECTRONICS",
    "SOFTWARE_ELECTRONICS": "SOFTWARE_ELECTRONICS",
    "OTA": "SOFTWARE_ELECTRONICS",
    "소프트웨어": "SOFTWARE_ELECTRONICS",
    "전장": "SOFTWARE_ELECTRONICS",
    "먹통": "SOFTWARE_ELECTRONICS",
    "OTA/소프트웨어/먹통": "SOFTWARE_ELECTRONICS",
    "인포테인먼트": "SOFTWARE_ELECTRONICS",
    # SERVICE_REPAIR_COST
    "SERVICE": "SERVICE_REPAIR_COST",
    "REPAIR": "SERVICE_REPAIR_COST",
    "COST": "SERVICE_REPAIR_COST",
    "SERVICE_REPAIR_COST": "SERVICE_REPAIR_COST",
    "AS": "SERVICE_REPAIR_COST",
    "A/S": "SERVICE_REPAIR_COST",
    "수리": "SERVICE_REPAIR_COST",
    "수리비": "SERVICE_REPAIR_COST",
    "서비스센터": "SERVICE_REPAIR_COST",
    "AS/수리비": "SERVICE_REPAIR_COST",
    "AS 수리비": "SERVICE_REPAIR_COST",
}


def validate_severity(sev: Any) -> bool:
    """Validate whether severity level is one of canonical levels CRITICAL, HIGH, MEDIUM, LOW."""
    if not isinstance(sev, str):
        return False
    return sev.strip().upper() in VALID_SEVERITY_LEVELS


def normalize_severity(severity: Any, severity_index: Any = None, default: str = "LOW") -> str:
    """Normalize severity level string or compute from DSI index."""
    if severity is not None and str(severity).strip():
        s = str(severity).strip().upper()
        if s in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            return s
        if s in ("WARNING", "MAJOR", "URGENT"):
            return "HIGH"
        if s in ("CAUTION", "MODERATE", "MINOR"):
            return "MEDIUM"
        if s in ("INFO", "INFORMATIONAL", "NEGLIGIBLE", "LOW"):
            return "LOW"
    try:
        val = float(severity_index)
        if not (math.isnan(val) or math.isinf(val)):
            if val >= 8.0:
                return "CRITICAL"
            if val >= 6.0:
                return "HIGH"
            if val >= 4.0:
                return "MEDIUM"
            return "LOW"
    except (ValueError, TypeError, OverflowError):
        pass
    return default


def validate_category(category: Any) -> bool:
    """Validate whether category is in CANONICAL_CATEGORIES or Korean mappings."""
    if not isinstance(category, str):
        return False
    s = category.strip()
    return (
        s.upper() in DEFECT_CATEGORY_KO_MAP
        or s in DEFECT_CATEGORY_KO_MAP.values()
    )


def normalize_category(category: Any, default: str = "BUILD_QUALITY") -> str:
    """Normalize category string (case-insensitive English, Korean, or aliases) to canonical uppercase English."""
    if not category:
        return default
    s = str(category).strip()
    s_upper = s.upper()
    if s_upper in DEFECT_CATEGORY_KO_MAP:
        return s_upper
    for k, v in DEFECT_CATEGORY_KO_MAP.items():
        if s == v or s_upper == v.upper():
            return k
    if s_upper in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[s_upper]
    if s in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[s]
    return default


def _safe_round(val: Any, decimals: int = 4, default: float = 0.0) -> float:
    """Safely round numeric value, catching None, NaN, Inf, and non-numeric inputs."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return round(f, decimals)
    except (ValueError, TypeError, OverflowError):
        return default


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely convert value to int, catching None, NaN, Inf, and non-numeric inputs."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return int(f)
    except (ValueError, TypeError, OverflowError):
        return default


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert value to float, catching None, NaN, Inf, and non-numeric inputs."""
    if val is None:
        return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return f
    except (ValueError, TypeError, OverflowError):
        return default


def _safe_clamp(val: Any, min_val: float = -1.0, max_val: float = 1.0, default: float = 0.0) -> float:
    """Safely convert numeric value and clamp to [min_val, max_val]."""
    f = _safe_float(val, default)
    if f < min_val:
        return min_val
    if f > max_val:
        return max_val
    return f


# Pre-compiled regex for stripping invalid characters: null bytes, non-printable control chars,
# Trojan Source / Unicode BiDi overrides, unpaired surrogates, BOM, and Unicode non-characters.
RE_INVALID_CHARS: re.Pattern[str] = re.compile(
    r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e\u2066-\u2069\ud800-\udfff\ufeff\ufffe\uffff]"
)


def sanitize_string(val: Any, max_len: int = 50_000) -> str:
    """Safely coerces input to str, strips null bytes, control chars, BiDi overrides & surrogates,
    normalizes NFC, and caps length.

    Immune to ReDoS, database insert crash, surrogate encoding error, and memory exhaustion.
    """
    if val is None or val is False:
        return ""
    if isinstance(val, (bytes, bytearray)):
        try:
            val_str = val.decode("utf-8", errors="replace")
        except Exception:
            val_str = str(val)
    elif isinstance(val, str):
        val_str = val
    else:
        try:
            val_str = str(val)
        except Exception:
            return ""

    if not val_str:
        return ""

    val_str = RE_INVALID_CHARS.sub("", val_str)
    val_str = val_str.strip()
    if len(val_str) > max_len:
        val_str = val_str[:max_len]
    return unicodedata.normalize("NFC", val_str)


# Pre-compiled date parsing regular expressions for high-throughput batch evaluation
_RE_DATE_KR_4: re.Pattern[str] = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일?")
_RE_DATE_KR_2: re.Pattern[str] = re.compile(r"(?:^|[^\d])(\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일?")
_RE_DATE_TS: re.Pattern[str] = re.compile(
    r"(\d{4})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{1,2})(?:[\sT]+\d{1,2}:\d{1,2}(?::\d{1,2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?(?:[^\d]|$)"
)
_RE_DATE_COMPACT_8: re.Pattern[str] = re.compile(
    r"(?:^|[^\d])((?:19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?:\d{4,6})?(?:$|[^\d])"
)
_RE_DATE_2: re.Pattern[str] = re.compile(r"(?:^|[^\d])(\d{2})\s*[./\-]\s*(\d{1,2})\s*[./\-]\s*(\d{1,2})")
_RE_DATE_COMPACT_6: re.Pattern[str] = re.compile(r"^(\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])$")
_RE_DATE_MD: re.Pattern[str] = re.compile(r"^(0[1-9]|1[0-2])[./\-](0[1-9]|[12]\d|3[01])$")


def parse_date_str(created_at: Any) -> str:
    """Extract YYYY-MM-DD from created_at or default safely to today (UTC).

    Guarantees calendar validity and never raises uncaught exceptions.
    Handles ISO 8601, Korean formats (4-digit and 2-digit years), dotted (with trailing dot),
    slashed, compacted (8-digit and 6-digit), relative Korean dates, and Unix epoch timestamps.
    """
    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if created_at is None:
        return today_iso

    def _validate_date(year: int, month: int, day: int) -> Optional[str]:
        try:
            if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                dt = datetime(year, month, day)
                return dt.strftime("%Y-%m-%d")
        except (ValueError, OverflowError):
            pass
        return None

    # Fast-path for date or datetime instances
    if isinstance(created_at, datetime):
        return _validate_date(created_at.year, created_at.month, created_at.day) or today_iso
    elif isinstance(created_at, date):
        return _validate_date(created_at.year, created_at.month, created_at.day) or today_iso
    elif hasattr(created_at, "year") and hasattr(created_at, "month") and hasattr(created_at, "day"):
        try:
            return _validate_date(int(created_at.year), int(created_at.month), int(created_at.day)) or today_iso
        except (ValueError, TypeError):
            pass

    # Numeric Unix timestamps (epoch seconds or milliseconds)
    if isinstance(created_at, (int, float)) and not isinstance(created_at, bool):
        try:
            ts = float(created_at)
            if 1_000_000_000 <= ts <= 2_500_000_000:
                dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                return dt.strftime("%Y-%m-%d")
            elif 1_000_000_000_000 <= ts <= 2_500_000_000_000:
                dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
                return dt.strftime("%Y-%m-%d")
        except (ValueError, OverflowError, OSError):
            pass

    s = sanitize_string(created_at, max_len=128)
    if not s:
        return today_iso

    # Relative Korean date keywords and time-only stamps
    if s in ("오늘", "방금") or re.match(r"^\d{1,2}:\d{2}(?::\d{2})?$", s):
        return today_iso
    if s == "어제":
        return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    if s in ("그제", "그저께"):
        return (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")

    current_year = datetime.now(timezone.utc).year

    # 1a. Handle 4-digit Korean explicit date format e.g. "2026년 10월 27일" or "2026년 9월 8일"
    match_kr = _RE_DATE_KR_4.search(s)
    if match_kr:
        v = _validate_date(int(match_kr.group(1)), int(match_kr.group(2)), int(match_kr.group(3)))
        if v:
            return v

    # 1b. Handle 2-digit Korean explicit date format e.g. "26년 10월 27일" or "26년 9월 8일"
    match_kr_2 = _RE_DATE_KR_2.search(s)
    if match_kr_2:
        yy = int(match_kr_2.group(1))
        y = 2000 + yy if yy < 70 else 1900 + yy
        v = _validate_date(y, int(match_kr_2.group(2)), int(match_kr_2.group(3)))
        if v:
            return v

    # 2. Handle timestamps with space, sub-second microseconds, or standard ISO formats
    match_ts = _RE_DATE_TS.search(s)
    if match_ts:
        v = _validate_date(int(match_ts.group(1)), int(match_ts.group(2)), int(match_ts.group(3)))
        if v:
            return v

    # 3. Handle 8-digit compact dates e.g. "20261028" or "20261028190123"
    match_compact = _RE_DATE_COMPACT_8.search(s)
    if match_compact:
        v = _validate_date(int(match_compact.group(1)), int(match_compact.group(2)), int(match_compact.group(3)))
        if v:
            return v

    # 4. Handle Korean 2-digit year patterns e.g. "26.10.25" or "26-10-25"
    match_2 = _RE_DATE_2.search(s)
    if match_2:
        yy = int(match_2.group(1))
        y = 2000 + yy if yy < 70 else 1900 + yy
        v = _validate_date(y, int(match_2.group(2)), int(match_2.group(3)))
        if v:
            return v

    # 5. Handle 6-digit compact dates e.g. "261028" (YYMMDD)
    match_compact_6 = _RE_DATE_COMPACT_6.search(s)
    if match_compact_6:
        yy = int(match_compact_6.group(1))
        y = 2000 + yy if yy < 70 else 1900 + yy
        v = _validate_date(y, int(match_compact_6.group(2)), int(match_compact_6.group(3)))
        if v:
            return v

    # 6. Handle month-day only format e.g. "10.28" or "10-28" (DCInside current-year posts)
    match_md = _RE_DATE_MD.search(s)
    if match_md:
        v = _validate_date(current_year, int(match_md.group(1)), int(match_md.group(2)))
        if v:
            return v

    # 7. Normalization fallback
    norm_date = s.replace("/", "-").replace(".", "-")
    if len(norm_date) >= 10 and norm_date[4] == "-" and norm_date[7] == "-":
        try:
            y_val, m_val, d_val = int(norm_date[:4]), int(norm_date[5:7]), int(norm_date[8:10])
            v = _validate_date(y_val, m_val, d_val)
            if v:
                return v
        except (ValueError, TypeError):
            pass
    try:
        dt = datetime.fromisoformat(norm_date.replace("Z", "+00:00"))
        v = _validate_date(dt.year, dt.month, dt.day)
        if v:
            return v
    except Exception:
        pass

    return today_iso


@dataclass(init=False)
class RawPost:
    """Raw post extracted by scraper modules."""
    platform: str
    post_id: str
    url: str
    title: str
    content: str
    comments: List[str] = field(default_factory=list)
    created_at: str = ""
    author: str = ""

    def __init__(
        self,
        platform: str = "",
        post_id: str = "",
        url: str = "",
        title: str = "",
        content: str = "",
        comments: Optional[Union[List[Any], Tuple[Any, ...], Set[Any], str]] = None,
        created_at: str = "",
        author: str = "",
        id: Optional[str] = None,
        source: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        self.platform = sanitize_string(str(source or platform or "unknown"), max_len=256)
        self.post_id = sanitize_string(str(id if id is not None else (post_id if post_id is not None else "")), max_len=256)
        self.url = sanitize_string(url, max_len=2048)
        self.title = sanitize_string(title, max_len=10_000)
        self.content = sanitize_string(content, max_len=100_000)

        if isinstance(comments, str):
            c_clean = sanitize_string(comments, max_len=10_000)
            self.comments = [c_clean] if c_clean else []
        elif isinstance(comments, (list, tuple, set)):
            safe_c: List[str] = []
            for c in comments:
                if c is not None:
                    c_clean = sanitize_string(c, max_len=10_000)
                    if c_clean:
                        safe_c.append(c_clean)
            self.comments = safe_c
        else:
            self.comments = []

        self.created_at = sanitize_string(created_at, max_len=128)
        self.author = sanitize_string(author, max_len=256)

    @property
    def id(self) -> str:
        return self.post_id

    @property
    def source(self) -> str:
        return self.platform

    def to_dict(self) -> Dict[str, Any]:
        return {
            "platform": self.platform,
            "post_id": self.post_id,
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "comments": list(self.comments),
            "created_at": self.created_at,
            "author": self.author,
        }

    def __getitem__(self, key: str) -> Any:
        if isinstance(key, str):
            if hasattr(self, key) and not key.startswith("_"):
                val = getattr(self, key)
                if not callable(val):
                    return val
            if key in ("platform", "post_id", "url", "title", "content", "comments", "created_at", "author", "id", "source"):
                return self.to_dict()[key]
        raise KeyError(key) from None

    def __contains__(self, key: Any) -> bool:
        if isinstance(key, str) and hasattr(self, key) and not key.startswith("_"):
            val = getattr(self, key)
            if not callable(val):
                return True
        return key in ("platform", "post_id", "url", "title", "content", "comments", "created_at", "author", "id", "source")

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    @classmethod
    def from_dict(cls, data: Any) -> RawPost:
        if isinstance(data, cls):
            return data
        if isinstance(data, (str, bytes, bytearray)):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    data = parsed
                else:
                    return cls()
            except Exception:
                return cls()
        if data is None or not isinstance(data, (dict, object)) or isinstance(data, (int, float, bool, list, tuple, set, str, bytes)):
            return cls()
        def _get(k: str, default: Any = "") -> Any:
            if isinstance(data, dict):
                return data.get(k, default)
            return getattr(data, k, default)
        raw_comments = _get("comments")
        comments = (
            [str(c) for c in raw_comments if c is not None]
            if isinstance(raw_comments, (list, tuple, set))
            else []
        )
        pid = _get("post_id", None)
        if pid is None or (isinstance(pid, str) and not pid.strip()):
            pid = _get("id", None)
        post_id = str(pid) if pid is not None else ""

        return cls(
            platform=str(_get("source") or _get("platform") or "unknown"),
            post_id=post_id,
            url=str(_get("url") or ""),
            title=str(_get("title") or ""),
            content=str(_get("content") or ""),
            comments=comments,
            created_at=str(_get("created_at") or _get("created_at=") or ""),
            author=str(_get("author") or ""),
        )


@dataclass
class DSIBreakdown:
    """5-dimensional breakdown of Defect Severity Index."""
    safety: float = 0.0
    functional: float = 0.0
    economic: float = 0.0
    social: float = 0.0
    convenience: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "safety": _safe_round(self.safety, 2),
            "functional": _safe_round(self.functional, 2),
            "economic": _safe_round(self.economic, 2),
            "social": _safe_round(self.social, 2),
            "convenience": _safe_round(self.convenience, 2),
        }

    def __getitem__(self, key: str) -> float:
        if key in ("safety", "functional", "economic", "social", "convenience"):
            return _safe_round(getattr(self, key, 0.0), 2)
        raise KeyError(key) from None

    def __contains__(self, key: Any) -> bool:
        return key in ("safety", "functional", "economic", "social", "convenience")

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    @classmethod
    def from_dict(cls, data: Any) -> Optional[DSIBreakdown]:
        """Convert dict or DSIBreakdown instance safely into a DSIBreakdown object."""
        if isinstance(data, cls):
            return data
        if hasattr(data, "get") and callable(data.get):
            return cls(
                safety=_safe_float(data.get("safety", 0.0)),
                functional=_safe_float(data.get("functional", 0.0)),
                economic=_safe_float(data.get("economic", 0.0)),
                social=_safe_float(data.get("social", 0.0)),
                convenience=_safe_float(data.get("convenience", 0.0)),
            )
        if isinstance(data, dict):
            return cls(
                safety=_safe_float(data.get("safety", 0.0)),
                functional=_safe_float(data.get("functional", 0.0)),
                economic=_safe_float(data.get("economic", 0.0)),
                social=_safe_float(data.get("social", 0.0)),
                convenience=_safe_float(data.get("convenience", 0.0)),
            )
        return None


def validate_report_entry(entry: Any, strict: bool = False) -> Tuple[bool, str]:
    """Strictly validates a defect report entry dictionary or record object against schema contracts.

    Returns:
        (is_valid: bool, reason: str)
    """
    if entry is None:
        return False, "Entry is None"
    if not isinstance(entry, (dict, object)) or isinstance(entry, (int, float, bool, list, tuple, set, str, bytes)):
        return False, f"Invalid entry type: {type(entry).__name__}, expected dict or mapping"

    def _get(k: str, default: Any = None) -> Any:
        if isinstance(entry, dict):
            return entry.get(k, default)
        return getattr(entry, k, default)

    # 1. Identifier validation (must have non-empty id or post_id)
    raw_id = _get("id")
    if raw_id is None or not str(raw_id).strip():
        raw_id = _get("post_id")
    if raw_id is None or not str(raw_id).strip():
        return False, "Missing or empty required field: 'id'"

    # 2. Content validation (must have title, summary, quote, or content)
    has_text = any(
        _get(k) is not None and str(_get(k)).strip() != ""
        for k in ("title", "post_title", "summary", "verbatim_quote", "raw_quote", "content")
    )
    if not has_text:
        return False, "Missing required content: title, summary, or quote cannot all be empty"

    # 3. Numeric bounds validation (no NaN or Inf allowed)
    for num_key, min_val, max_val in (
        ("sentiment_polarity", -1.0, 1.0),
        ("sentiment_score", 0.0, 1.0),
        ("negativity_score", 0.0, 1.0),
        ("severity_index", 0.0, 100.0),
        ("confidence_score", 0.0, 1.0),
    ):
        v = _get(num_key)
        if v is not None:
            try:
                fv = float(v)
                if math.isnan(fv) or math.isinf(fv):
                    if strict:
                        return False, f"Numeric field '{num_key}' cannot be NaN or Inf"
                elif strict and (fv < min_val or fv > max_val):
                    return False, f"Numeric field '{num_key}' value {fv} out of bounds [{min_val}, {max_val}]"
            except (ValueError, TypeError, OverflowError):
                if strict:
                    return False, f"Non-numeric value for numeric field '{num_key}'"

    # 4. Defect category check if strict=True
    if strict:
        cat = _get("defect_category") or _get("category")
        if cat is not None and str(cat).strip():
            s_cat = str(cat).strip().upper()
            if not validate_category(s_cat) and s_cat not in CATEGORY_ALIASES and str(cat).strip() not in CATEGORY_ALIASES:
                return False, f"Invalid defect_category: '{cat}'"

    return True, ""


def quarantine_entry(entry: Any, reason: str = "") -> Dict[str, Any]:
    """Wraps an invalid report entry into a quarantined record container."""
    now_iso = datetime.now(timezone.utc).isoformat()
    if isinstance(entry, dict):
        raw_data = dict(entry)
    elif hasattr(entry, "to_dict") and callable(entry.to_dict):
        raw_data = entry.to_dict()
    else:
        raw_data = {"raw_payload": str(entry)}

    res_reason = reason or "Failed schema validation"
    return {
        "quarantine_id": f"quarantine_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        "entry": raw_data,
        "reason": res_reason,
        "quarantine_reason": res_reason,
        "quarantined_at": now_iso,
        "is_quarantined": True,
    }


@dataclass
class ComplaintRecord:
    """Classified & filtered defect complaint record."""
    id: str
    source: str
    url: str
    title: str
    author: str
    created_at: str
    vehicle_brand: str
    vehicle_model: str
    defect_category: str
    summary: str
    verbatim_quote: str
    slang_terms_detected: List[str] = field(default_factory=list)
    sentiment_polarity: float = 0.0
    negativity_score: float = 0.0
    severity_index: float = 0.0
    is_authentic_defect: bool = True
    dsi_breakdown: Optional[DSIBreakdown] = None
    filter_reason: str = ""
    severity: Optional[str] = None
    confidence_score: float = 0.0

    def __post_init__(self) -> None:
        """Sanitize default factory values, ensure copy resilience, clean corrupted chars, and clamp sentiment bounds."""
        if self.slang_terms_detected is None:
            self.slang_terms_detected = []
        elif not isinstance(self.slang_terms_detected, list):
            self.slang_terms_detected = [sanitize_string(s, 256) for s in self.slang_terms_detected if s is not None]
        else:
            self.slang_terms_detected = [sanitize_string(s, 256) for s in self.slang_terms_detected if s is not None]

        # Sanitize text fields from null bytes, control chars, BiDi overrides, and surrogates
        self.id = sanitize_string(self.id, 256)
        self.source = sanitize_string(self.source, 256)
        self.url = sanitize_string(self.url, 2048)
        self.title = sanitize_string(self.title, 10_000)
        self.author = sanitize_string(self.author, 256)
        self.created_at = sanitize_string(self.created_at, 128)
        self.vehicle_brand = sanitize_string(self.vehicle_brand, 256)
        self.vehicle_model = sanitize_string(self.vehicle_model, 256)
        self.defect_category = sanitize_string(self.defect_category, 256)
        self.summary = sanitize_string(self.summary, 10_000)
        self.verbatim_quote = sanitize_string(self.verbatim_quote, 50_000)
        self.filter_reason = sanitize_string(self.filter_reason, 10_000)
        if self.severity is not None:
            self.severity = sanitize_string(self.severity, 64)

        # Clamp and sanitize numeric bounds
        self.sentiment_polarity = _safe_round(_safe_clamp(self.sentiment_polarity, -1.0, 1.0, 0.0), 4)
        self.negativity_score = _safe_round(_safe_clamp(self.negativity_score, 0.0, 1.0, 0.0), 4)
        self.severity_index = _safe_round(_safe_clamp(self.severity_index, 0.0, 100.0, 0.0), 2)
        self.confidence_score = _safe_round(_safe_clamp(self.confidence_score, 0.0, 1.0, 0.0), 4)

    @property
    def defect_category_ko(self) -> str:
        cat = self.defect_category
        if cat in DEFECT_CATEGORY_KO_MAP:
            return DEFECT_CATEGORY_KO_MAP[cat]
        if cat:
            cat_upper = cat.upper()
            if cat_upper in DEFECT_CATEGORY_KO_MAP:
                return DEFECT_CATEGORY_KO_MAP[cat_upper]
            for k, v in DEFECT_CATEGORY_KO_MAP.items():
                if cat == v or cat_upper == v.upper():
                    return v
            if cat_upper in CATEGORY_ALIASES:
                return DEFECT_CATEGORY_KO_MAP[CATEGORY_ALIASES[cat_upper]]
            if cat in CATEGORY_ALIASES:
                return DEFECT_CATEGORY_KO_MAP[CATEGORY_ALIASES[cat]]
        return "기타 결함"

    @property
    def severity_tier(self) -> str:
        """Map DSI score to 4 severity tiers or return explicit severity."""
        if self.severity and str(self.severity).strip():
            return str(self.severity).strip().upper()
        if self.severity_index is None:
            return "LOW"
        try:
            val = float(self.severity_index)
            if math.isnan(val) or math.isinf(val):
                return "LOW"
        except (ValueError, TypeError, OverflowError):
            return "LOW"

        if val >= 8.0:
            return "CRITICAL"
        if val >= 6.0:
            return "HIGH"
        if val >= 4.0:
            return "MEDIUM"
        return "LOW"

    @property
    def canonical_severity(self) -> str:
        """Return validated canonical severity level: CRITICAL, HIGH, MEDIUM, or LOW."""
        return normalize_severity(self.severity, self.severity_index, default="LOW")

    @property
    def sentiment_tier(self) -> str:
        """Map continuous polarity [-1.0, 1.0] to 4 tiers."""
        if self.sentiment_polarity is None:
            return "NEUTRAL"
        try:
            val = float(self.sentiment_polarity)
            if math.isnan(val) or math.isinf(val):
                return "NEUTRAL"
        except (ValueError, TypeError, OverflowError):
            return "NEUTRAL"

        if val >= 0.30:
            return "POSITIVE"
        if val >= -0.29:
            return "NEUTRAL"
        if val >= -0.69:
            return "NEGATIVE"
        return "STRONGLY_NEGATIVE"

    @property
    def date_str(self) -> str:
        """Extract YYYY-MM-DD from created_at or default to today."""
        return parse_date_str(self.created_at)

    def to_dict(self) -> Dict[str, Any]:
        """Format matching PROJECT.md § Interface Contract 1 (Scraper ↔ Filter)."""
        return {
            "id": self.id,
            "source": self.source,
            "url": self.url,
            "title": self.title,
            "author": self.author,
            "created_at": self.created_at,
            "vehicle_brand": self.vehicle_brand,
            "vehicle_model": self.vehicle_model,
            "defect_category": self.defect_category,
            "summary": self.summary,
            "verbatim_quote": self.verbatim_quote,
            "slang_terms_detected": list(self.slang_terms_detected or []),
            "sentiment_polarity": _safe_round(_safe_clamp(self.sentiment_polarity, -1.0, 1.0, 0.0), 4),
            "negativity_score": _safe_round(_safe_clamp(self.negativity_score, 0.0, 1.0, 0.0), 4),
            "severity_index": _safe_round(self.severity_index, 2),
            "is_authentic_defect": self.is_authentic_defect,
            "confidence_score": _safe_round(self.confidence_score, 4),
        }

    def to_admin_report_dict(self) -> Dict[str, Any]:
        """Format matching PROJECT.md § Interface Contract 2 (Admin Page & daily_reports.json)."""
        res = {
            "id": self.id,
            "source": self.source,
            "platform": self.source,
            "url": self.url,
            "post_url": self.url,
            "title": self.title,
            "post_title": self.title,
            "author": self.author,
            "date": self.date_str,
            "created_at": self.created_at,
            "vehicle_brand": self.vehicle_brand,
            "vehicle_model": self.vehicle_model,
            "target_vehicle": f"{self.vehicle_brand} {self.vehicle_model}".strip(),
            "defect_category": self.defect_category,
            "defect_category_ko": self.defect_category_ko,
            "summary": self.summary,
            "verbatim_quote": self.verbatim_quote,
            "raw_quote": self.verbatim_quote,
            "slang_tags": list(self.slang_terms_detected or []),
            "slang_terms_detected": list(self.slang_terms_detected or []),
            "sentiment_score": _safe_round(_safe_clamp(self.negativity_score, 0.0, 1.0, 0.0), 4),
            "sentiment_polarity": _safe_round(_safe_clamp(self.sentiment_polarity, -1.0, 1.0, 0.0), 4),
            "negativity_score": _safe_round(_safe_clamp(self.negativity_score, 0.0, 1.0, 0.0), 4),
            "sentiment_tier": self.sentiment_tier,
            "severity": self.severity_tier,
            "severity_index": _safe_round(self.severity_index, 2),
            "is_authentic_defect": self.is_authentic_defect,
            "confidence_score": _safe_round(self.confidence_score, 4),
        }
        if self.dsi_breakdown:
            res["dsi_breakdown"] = self.dsi_breakdown.to_dict()
        return res

    def validate(self, strict: bool = True) -> Tuple[bool, str]:
        """Validate this ComplaintRecord instance against schema contracts."""
        return validate_report_entry(self, strict=strict)

    @classmethod
    def from_dict(
        cls,
        data: Any,
        strict: bool = False,
        quarantine: bool = False,
    ) -> ComplaintRecord:
        """Construct ComplaintRecord from dict or ComplaintRecord instance with aliases and fallbacks."""
        if isinstance(data, cls):
            return data

        if isinstance(data, (str, bytes, bytearray)):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict):
                    data = parsed
            except Exception as e:
                if strict:
                    raise ValueError(f"Failed to parse JSON string: {e}") from e
                data = {}

        if not isinstance(data, (dict, object)) or data is None or isinstance(data, (int, float, bool, list, tuple, set, str, bytes)):
            data = {}

        if strict or quarantine:
            is_valid, reason = validate_report_entry(data, strict=True)
            if not is_valid:
                if strict:
                    raise ValueError(f"Strict validation failed: {reason}")
                rec = cls._from_dict_internal(data)
                rec.is_authentic_defect = False
                rec.filter_reason = f"QUARANTINED: {reason}"
                return rec

        return cls._from_dict_internal(data)

    @classmethod
    def from_json(cls, json_str: Union[str, bytes], **kwargs: Any) -> ComplaintRecord:
        """Parse raw JSON string safely into ComplaintRecord with strict or quarantine options."""
        return cls.from_dict(json_str, **kwargs)

    @classmethod
    def _from_dict_internal(cls, data: Any) -> ComplaintRecord:
        if not isinstance(data, (dict, object)) or data is None or isinstance(data, (int, float, bool, list, tuple, set, str, bytes)):
            data = {}

        def _get(key: str, default: Any = None) -> Any:
            if isinstance(data, dict):
                return data.get(key, default)
            return getattr(data, key, default)

        def _get_str(*keys: str, default: str = "") -> str:
            for k in keys:
                val = _get(k)
                if val is not None and str(val).strip() != "":
                    return str(val).strip()
            for k in keys:
                val = _get(k)
                if val is not None:
                    return str(val)
            return default

        # 1. post_id / id
        rec_id = _get_str("id", "post_id")

        # 2. source / platform
        source = _get_str("source", "platform", default="unknown")

        # 3. url / post_url
        url = _get_str("url", "post_url")

        # 4. title / post_title
        title = _get_str("title", "post_title")

        # 5. author
        author = _get_str("author")

        # 6. created_at (support date alias)
        created_at = _get_str("created_at", "date")

        # 7. vehicle_brand & vehicle_model with target_vehicle fallback
        brand = _get_str("vehicle_brand")
        model = _get_str("vehicle_model")
        target_veh = _get_str("target_vehicle")
        if (not brand or not model) and target_veh:
            brand_map = {
                "mercedes-benz": "Mercedes-Benz",
                "mercedes": "Mercedes-Benz",
                "benz": "Mercedes-Benz",
                "hyundai": "Hyundai",
                "현대": "Hyundai",
                "kia": "Kia",
                "기아": "Kia",
                "tesla": "Tesla",
                "테슬라": "Tesla",
                "byd": "BYD",
                "비야디": "BYD",
                "genesis": "Genesis",
                "제네시스": "Genesis",
                "porsche": "Porsche",
                "포르쉐": "Porsche",
                "bmw": "BMW",
                "audi": "Audi",
                "아우디": "Audi",
                "chevrolet": "Chevrolet",
                "쉐보레": "Chevrolet",
                "polestar": "Polestar",
                "폴스타": "Polestar",
                "volvo": "Volvo",
                "볼보": "Volvo",
                "volkswagen": "Volkswagen",
                "폭스바겐": "Volkswagen",
                "cadillac": "Cadillac",
                "캐딜락": "Cadillac",
                "rivian": "Rivian",
                "리비안": "Rivian",
                "lucid": "Lucid",
                "루시드": "Lucid",
                "other": "Other",
                "기타": "Other",
            }
            model_brand_map = {
                "ioniq": "Hyundai",
                "아이오닉": "Hyundai",
                "casper": "Hyundai",
                "캐스퍼": "Hyundai",
                "porter": "Hyundai",
                "포터": "Hyundai",
                "ev2": "Kia",
                "ev3": "Kia",
                "ev4": "Kia",
                "ev5": "Kia",
                "ev6": "Kia",
                "ev9": "Kia",
                "niro": "Kia",
                "니로": "Kia",
                "bongo": "Kia",
                "봉고": "Kia",
                "ray": "Kia",
                "레이": "Kia",
                "model 3": "Tesla",
                "model y": "Tesla",
                "model s": "Tesla",
                "model x": "Tesla",
                "cybertruck": "Tesla",
                "t4k": "BYD",
                "atto": "BYD",
                "seal": "BYD",
                "dolphin": "BYD",
                "sealion": "BYD",
                "시라이언": "BYD",
                "gv60": "Genesis",
                "gv70": "Genesis",
                "g80": "Genesis",
                "taycan": "Porsche",
                "타이칸": "Porsche",
                "id.4": "Volkswagen",
                "id4": "Volkswagen",
                "id.buzz": "Volkswagen",
                "id버즈": "Volkswagen",
                "lyriq": "Cadillac",
                "리릭": "Cadillac",
            }
            parsed_brand = ""
            parsed_model = ""
            tv_lower = target_veh.lower()
            for b_key, b_val in brand_map.items():
                if tv_lower == b_key:
                    parsed_brand = b_val
                    parsed_model = ""
                    break
                elif tv_lower.startswith(b_key + " "):
                    parsed_brand = b_val
                    parsed_model = target_veh[len(b_key):].strip()
                    break

            if not parsed_brand:
                for m_key, m_b in model_brand_map.items():
                    if tv_lower == m_key or tv_lower.startswith(m_key + " ") or tv_lower.startswith(m_key):
                        parsed_brand = m_b
                        parsed_model = target_veh
                        break

            if not parsed_brand:
                parts = target_veh.split(None, 1)
                if len(parts) == 2:
                    parsed_brand = parts[0]
                    parsed_model = parts[1]
                else:
                    parsed_brand = "Other"
                    parsed_model = parts[0]

            if not brand and parsed_brand:
                brand = parsed_brand
            if not model and parsed_model:
                model = parsed_model

        # 8. defect_category (support category or Korean category alias)
        defect_cat = _get_str("defect_category", "category")
        if defect_cat:
            defect_cat = normalize_category(defect_cat, default=defect_cat)
        else:
            cat_ko = _get_str("defect_category_ko")
            if cat_ko:
                defect_cat = normalize_category(cat_ko, default="BUILD_QUALITY")

        # 9. summary
        summary = _get_str("summary")

        # 10. verbatim_quote / raw_quote
        verbatim_quote = _get_str("verbatim_quote", "raw_quote")

        # 11. slang_terms_detected / slang_tags
        raw_slang = _get("slang_terms_detected")
        if raw_slang is None:
            raw_slang = _get("slang_tags")
        if raw_slang is None:
            raw_slang = _get("slang_terms")
        if isinstance(raw_slang, str):
            slang_terms: List[str] = [s.strip() for s in raw_slang.split(",") if s.strip()]
        elif isinstance(raw_slang, (list, tuple, set)):
            slang_terms = [str(s) for s in raw_slang if s is not None]
        else:
            slang_terms = []

        # 12. sentiment_polarity (clamped [-1.0, 1.0])
        polarity = _safe_round(_safe_clamp(_get("sentiment_polarity"), -1.0, 1.0, 0.0), 4)

        # 13. negativity_score / sentiment_score (clamped [0.0, 1.0])
        raw_neg = _get("negativity_score")
        if raw_neg is None:
            raw_neg = _get("sentiment_score")
        negativity = _safe_round(_safe_clamp(raw_neg, 0.0, 1.0, 0.0), 4)

        # 14. severity_index
        sev_idx = _safe_float(_get("severity_index"), 0.0)

        # 15. is_authentic_defect
        raw_auth = _get("is_authentic_defect")
        is_auth = bool(raw_auth) if raw_auth is not None else True

        # 16. dsi_breakdown: convert from dict or pass through DSIBreakdown instance
        raw_dsi = _get("dsi_breakdown")
        if isinstance(raw_dsi, DSIBreakdown):
            dsi = raw_dsi
        elif isinstance(raw_dsi, dict):
            dsi = DSIBreakdown.from_dict(raw_dsi)
        elif hasattr(raw_dsi, "get") and callable(raw_dsi.get):
            dsi = DSIBreakdown.from_dict(raw_dsi)
        else:
            dsi = None

        # 17. filter_reason
        filter_reason = _get_str("filter_reason")

        # 18. severity (support severity_tier alias)
        raw_sev = _get("severity")
        if raw_sev is None:
            raw_sev = _get("severity_tier")
        severity = str(raw_sev).strip() if raw_sev is not None else None

        # 19. confidence_score
        confidence_score = _safe_float(_get("confidence_score", 0.0), default=0.0)

        return cls(
            id=rec_id,
            source=source,
            url=url,
            title=title,
            author=author,
            created_at=created_at,
            vehicle_brand=brand,
            vehicle_model=model,
            defect_category=defect_cat,
            summary=summary,
            verbatim_quote=verbatim_quote,
            slang_terms_detected=slang_terms,
            sentiment_polarity=polarity,
            negativity_score=negativity,
            severity_index=sev_idx,
            is_authentic_defect=is_auth,
            dsi_breakdown=dsi,
            filter_reason=filter_reason,
            severity=severity,
            confidence_score=confidence_score,
        )

    def __getitem__(self, key: str) -> Any:
        if isinstance(key, str):
            if key == "platform":
                return self.source
            elif key == "post_url":
                return self.url
            elif key == "post_title":
                return self.title
            elif key == "date":
                return self.date_str
            elif key == "target_vehicle":
                return f"{self.vehicle_brand} {self.vehicle_model}".strip()
            elif key == "defect_category_ko":
                return self.defect_category_ko
            elif key in ("raw_quote", "verbatim_quote"):
                return self.verbatim_quote
            elif key in ("slang_tags", "slang_terms_detected"):
                return list(self.slang_terms_detected or [])
            elif key in ("sentiment_score", "negativity_score"):
                return _safe_round(_safe_clamp(self.negativity_score, 0.0, 1.0, 0.0), 4)
            elif key == "sentiment_polarity":
                return _safe_round(_safe_clamp(self.sentiment_polarity, -1.0, 1.0, 0.0), 4)
            elif key == "sentiment_tier":
                return self.sentiment_tier
            elif key in ("severity", "severity_tier"):
                return self.severity_tier
            elif key == "severity_index":
                return _safe_round(self.severity_index, 2)
            elif key == "confidence_score":
                return _safe_round(self.confidence_score, 4)
            elif key == "is_authentic_defect":
                return self.is_authentic_defect
            elif key == "dsi_breakdown":
                return self.dsi_breakdown.to_dict() if self.dsi_breakdown else None
            elif hasattr(self, key) and not key.startswith("_"):
                val = getattr(self, key)
                if not callable(val):
                    return val
        d = self.to_admin_report_dict()
        if key in d:
            return d[key]
        raise KeyError(key) from None

    def __contains__(self, key: Any) -> bool:
        if isinstance(key, str):
            if key in (
                "id", "source", "platform", "url", "post_url", "title", "post_title",
                "author", "date", "created_at", "vehicle_brand", "vehicle_model",
                "target_vehicle", "defect_category", "defect_category_ko", "summary",
                "verbatim_quote", "raw_quote", "slang_tags", "slang_terms_detected",
                "sentiment_score", "sentiment_polarity", "negativity_score",
                "sentiment_tier", "severity", "severity_tier", "severity_index",
                "is_authentic_defect", "confidence_score", "filter_reason"
            ):
                return True
            if key == "dsi_breakdown":
                return self.dsi_breakdown is not None
            if hasattr(self, key) and not key.startswith("_"):
                val = getattr(self, key)
                if not callable(val):
                    return True
        return key in self.to_admin_report_dict()

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self.to_admin_report_dict().keys()

    def values(self):
        return self.to_admin_report_dict().values()

    def items(self):
        return self.to_admin_report_dict().items()

    def __iter__(self):
        return iter(self.to_admin_report_dict())

    def __len__(self) -> int:
        return len(self.to_admin_report_dict())


@dataclass
class DailyReportStatistics:
    """Summary statistics for daily report payload."""
    total_scraped: int = 0
    total_filtered_defects: int = 0
    avg_negativity_score: float = 0.0
    critical_defect_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_scraped": self.total_scraped,
            "total_filtered_defects": self.total_filtered_defects,
            "avg_negativity_score": _safe_round(self.avg_negativity_score, 2),
            "critical_defect_count": self.critical_defect_count,
        }

    def __getitem__(self, key: str) -> Any:
        if isinstance(key, str):
            if key == "avg_negativity_score":
                return _safe_round(self.avg_negativity_score, 2)
            if key in ("total_scraped", "total_filtered_defects", "critical_defect_count"):
                return getattr(self, key)
            if hasattr(self, key) and not key.startswith("_"):
                val = getattr(self, key)
                if not callable(val):
                    return val
        raise KeyError(key) from None

    def __contains__(self, key: Any) -> bool:
        if isinstance(key, str) and hasattr(self, key) and not key.startswith("_"):
            val = getattr(self, key)
            if not callable(val):
                return True
        return key in ("total_scraped", "total_filtered_defects", "avg_negativity_score", "critical_defect_count")

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    @classmethod
    def from_dict(cls, data: Any) -> DailyReportStatistics:
        if isinstance(data, cls):
            return cls(
                total_scraped=data.total_scraped,
                total_filtered_defects=data.total_filtered_defects,
                avg_negativity_score=data.avg_negativity_score,
                critical_defect_count=data.critical_defect_count,
            )
        if not isinstance(data, dict):
            return cls()
        return cls(
            total_scraped=max(0, _safe_int(data.get("total_scraped", 0))),
            total_filtered_defects=max(0, _safe_int(data.get("total_filtered_defects", 0))),
            avg_negativity_score=_safe_float(data.get("avg_negativity_score", 0.0)),
            critical_defect_count=max(0, _safe_int(data.get("critical_defect_count", 0))),
        )


def _serialize_report_entry(r: Any) -> Dict[str, Any]:
    if hasattr(r, "to_admin_report_dict") and callable(r.to_admin_report_dict):
        return r.to_admin_report_dict()
    if hasattr(r, "to_dict") and callable(r.to_dict):
        return r.to_dict()
    if isinstance(r, dict):
        return {
            k: sanitize_string(v) if isinstance(v, str) else v
            for k, v in r.items()
        }
    return {}


@dataclass
class DailyReportPayload:
    """Complete container for outputting daily_reports.json."""
    generated_at: str
    pipeline_version: str = "1.0.0"
    statistics: DailyReportStatistics = field(default_factory=DailyReportStatistics)
    reports: List[Dict[str, Any]] = field(default_factory=list)
    total_complaints_today: int = 0
    top_defect_categories: List[Dict[str, Any]] = field(default_factory=list)
    quarantined_reports: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def quarantined_count(self) -> int:
        """Count of quarantined invalid entries."""
        return len(self.quarantined_reports)

    def quarantine_entry(self, entry: Any, reason: str = "Manual quarantine") -> None:
        """Gracefully isolate an invalid entry without raising exceptions."""
        self.quarantined_reports.append(quarantine_entry(entry, reason))

    def __getitem__(self, key: str) -> Any:
        if isinstance(key, str) and hasattr(self, key) and not key.startswith("_"):
            val = getattr(self, key)
            if not callable(val):
                return val
        raise KeyError(key)

    def __contains__(self, key: Any) -> bool:
        if isinstance(key, str) and hasattr(self, key) and not key.startswith("_"):
            val = getattr(self, key)
            if not callable(val):
                return True
        return key in (
            "generated_at", "pipeline_version", "statistics", "reports",
            "total_complaints_today", "top_defect_categories", "quarantined_reports"
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def items(self):
        return self.to_dict().items()

    def __iter__(self):
        return iter(self.to_dict())

    def __len__(self) -> int:
        return len(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        res = {
            "generated_at": self.generated_at,
            "pipeline_version": self.pipeline_version,
            "statistics": self.statistics.to_dict() if hasattr(self.statistics, "to_dict") else dict(self.statistics),
            "total_complaints_today": self.total_complaints_today,
            "top_defect_categories": [dict(c) for c in self.top_defect_categories if isinstance(c, dict)],
            "reports": [_serialize_report_entry(r) for r in self.reports],
        }
        if self.quarantined_reports:
            res["quarantined_reports"] = [dict(q) for q in self.quarantined_reports if isinstance(q, dict)]
        return res

    @classmethod
    def from_dict(cls, data: Any, quarantine_invalid: bool = True) -> DailyReportPayload:
        if isinstance(data, cls):
            return cls(
                generated_at=data.generated_at,
                pipeline_version=data.pipeline_version,
                statistics=DailyReportStatistics.from_dict(data.statistics),
                reports=[_serialize_report_entry(r) for r in data.reports],
                total_complaints_today=data.total_complaints_today,
                top_defect_categories=[dict(c) for c in data.top_defect_categories if isinstance(c, dict)],
                quarantined_reports=[dict(q) for q in data.quarantined_reports if isinstance(q, dict)],
            )

        # Handle raw JSON string or bytes input gracefully
        if isinstance(data, (str, bytes, bytearray)):
            try:
                parsed_data = json.loads(data)
                if isinstance(parsed_data, dict):
                    data = parsed_data
                else:
                    empty = cls(generated_at=datetime.now(timezone.utc).isoformat())
                    empty.quarantine_entry(data, f"JSON root must be an object, got {type(parsed_data).__name__}")
                    return empty
            except Exception as e:
                empty = cls(generated_at=datetime.now(timezone.utc).isoformat())
                empty.quarantine_entry(str(data)[:1000], f"Corrupt JSON payload: {e}")
                return empty

        if not isinstance(data, dict):
            empty = cls(generated_at=datetime.now(timezone.utc).isoformat())
            if data is not None:
                empty.quarantine_entry(data, f"Invalid payload type: {type(data).__name__}")
            return empty

        gen_at = str(data.get("generated_at") or datetime.now(timezone.utc).isoformat())
        pipe_ver = str(data.get("pipeline_version") or "1.0.0")

        raw_stats = data.get("statistics")
        if isinstance(raw_stats, DailyReportStatistics):
            stats = DailyReportStatistics.from_dict(raw_stats)
        elif isinstance(raw_stats, dict):
            stats = DailyReportStatistics.from_dict(raw_stats)
        else:
            stats = DailyReportStatistics()

        raw_reports = data.get("reports")
        valid_reports: List[Dict[str, Any]] = []
        quarantined: List[Dict[str, Any]] = []

        # Restore pre-existing quarantined reports if present
        raw_pre_quarantined = data.get("quarantined_reports")
        if isinstance(raw_pre_quarantined, (list, tuple)):
            for q in raw_pre_quarantined:
                if isinstance(q, dict):
                    quarantined.append(dict(q))

        if isinstance(raw_reports, (list, tuple)):
            for r in raw_reports:
                if quarantine_invalid:
                    is_valid, reason = validate_report_entry(r)
                    if is_valid:
                        valid_reports.append(_serialize_report_entry(r))
                    else:
                        quarantined.append(quarantine_entry(r, reason))
                else:
                    valid_reports.append(_serialize_report_entry(r))

        raw_cats = data.get("top_defect_categories")
        top_cats = [dict(c) for c in raw_cats if isinstance(c, dict)] if isinstance(raw_cats, (list, tuple)) else []

        tot_complaints = _safe_int(data.get("total_complaints_today", len(valid_reports)))

        return cls(
            generated_at=gen_at,
            pipeline_version=pipe_ver,
            statistics=stats,
            reports=valid_reports,
            total_complaints_today=tot_complaints,
            top_defect_categories=top_cats,
            quarantined_reports=quarantined,
        )

    @classmethod
    def from_json(cls, json_str: Union[str, bytes], quarantine_invalid: bool = True) -> DailyReportPayload:
        """Parse raw JSON string strictly and quarantine invalid entries without crashing."""
        return cls.from_dict(json_str, quarantine_invalid=quarantine_invalid)

    @classmethod
    def validate_payload(cls, data: Any) -> Tuple[bool, List[str]]:
        """Validate an entire daily report JSON payload against strict schema rules."""
        errors: List[str] = []
        if isinstance(data, (str, bytes, bytearray)):
            try:
                data = json.loads(data)
            except Exception as e:
                return False, [f"JSON decode failure: {e}"]
        if not isinstance(data, dict):
            return False, [f"Root payload must be an object, got {type(data).__name__}"]

        if "generated_at" not in data or not str(data["generated_at"]).strip():
            errors.append("Missing required field: 'generated_at'")
        if "reports" not in data or not isinstance(data["reports"], list):
            errors.append("Missing or non-list field: 'reports'")
        else:
            for idx, entry in enumerate(data["reports"]):
                is_valid, reason = validate_report_entry(entry, strict=True)
                if not is_valid:
                    errors.append(f"Report[{idx}] invalid: {reason}")

        return len(errors) == 0, errors


# Backward compatibility alias
DefectReport = ComplaintRecord

