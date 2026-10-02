"""Core EV Subsidy Depletion Tracker Engine.

Orchestrates data harvesting, metric recalculations, 5-tier alert classifications,
nationwide aggregations, fallback resilience, and atomic persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import urllib.error
import urllib.request

from tracker.atomic_writer import atomic_write_json, atomic_write_json_multiple
from tracker.subsidy_baseline import (
    COMMERCIAL_NATIONAL_CAP_KRW,
    DEFAULT_ALERT_THRESHOLDS,
    PASSENGER_NATIONAL_CAP_KRW,
    build_baseline_regions,
    build_initial_baseline,
    build_popular_models,
)
from tracker.subsidy_models import (
    AlertSeverity,
    CategoryMetrics,
    MunicipalityMetrics,
    NationwideSummary,
    PopularModelEntry,
    RegionRecord,
    SubsidyMetadata,
    SubsidyPayload,
)

logger = logging.getLogger("subsidy_tracker")

# Exported baseline aliases and getters matching interface specifications
get_baseline_regions = build_baseline_regions
get_baseline_models = build_popular_models
get_baseline_dataset = build_initial_baseline


def get_baseline_thresholds() -> Dict[str, Any]:
    """Return default 5-tier alert threshold configuration dictionary."""
    return DEFAULT_ALERT_THRESHOLDS


def calculate_depletion_rate(applied: int, announced: int) -> float:
    """Calculate EV subsidy depletion rate as percentage with zero-division guard."""
    if announced <= 0:
        return 0.0
    return round((applied / announced) * 100.0, 1)


def calculate_remaining_units(applied: int, announced: int) -> int:
    """Calculate remaining quota units clamped at zero for over-subscription."""
    return max(0, announced - applied)


def classify_alert_tier(depletion_rate: float) -> str:
    """Classify depletion rate into standard 5-tier alert severity level."""
    return AlertSeverity.from_rate(depletion_rate).value


def calculate_price_cap_ratio(msrp: int) -> float:
    """Statutory 2026 Korean EV subsidy ratio tiers: 1.0 (<=55M), 0.5 (55M-85M), 0.0 (>85M)."""
    if msrp <= 55_000_000:
        return 1.0
    elif msrp <= 85_000_000:
        return 0.5
    return 0.0


def calculate_net_subsidy(
    model_national: int,
    max_national: int,
    max_local: int,
    msrp: int,
) -> Dict[str, int]:
    """Calculate national subsidy, local subsidy, total subsidy, and net consumer purchase price."""
    ratio = calculate_price_cap_ratio(msrp)
    effective_national = int(round(model_national * ratio))
    if max_national > 0:
        local_ratio = model_national / max_national
    else:
        local_ratio = 0.0
    effective_local = int(round(max_local * local_ratio * ratio))
    total_subsidy = effective_national + effective_local
    net_price = max(0, msrp - total_subsidy)
    return {
        "national_subsidy_krw": effective_national,
        "local_subsidy_krw": effective_local,
        "total_subsidy_krw": total_subsidy,
        "net_price_krw": net_price,
    }


class SubsidyTracker:
    """Automated tracker for nationwide South Korea EV subsidy allocations and depletion."""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        timeout_seconds: float = 5.0,
        cache_fallback_path: Optional[Union[str, Path]] = None,
        validate_cache: bool = False,
        quarantine_corrupted: bool = False,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.timeout_seconds = timeout_seconds
        self.cache_fallback_path = Path(cache_fallback_path) if cache_fallback_path else None
        self.validate_cache = validate_cache
        self.quarantine_corrupted = quarantine_corrupted

    def evaluate_status(self, depletion_rate: float) -> AlertSeverity:
        """Evaluate 5-tier alert severity from depletion percentage."""
        return AlertSeverity.from_rate(depletion_rate)

    def calculate_category_metrics(
        self,
        announced: int,
        applied: int,
        delivered: int,
        max_local_subsidy: int,
        national_cap: int = PASSENGER_NATIONAL_CAP_KRW,
        avg_per_unit_budget: int = 10_000_000,
    ) -> CategoryMetrics:
        """Safely compute metrics for a single category with boundary clamping."""
        depletion_rate = (
            round((applied / announced * 100.0), 1) if announced > 0 else 0.0
        )
        delivery_rate = (
            round((delivered / announced * 100.0), 1) if announced > 0 else 0.0
        )
        remaining_units = max(0, announced - applied)
        status = self.evaluate_status(depletion_rate).value

        total_budget = announced * avg_per_unit_budget
        disbursed_budget = applied * avg_per_unit_budget
        remaining_budget = max(0, total_budget - disbursed_budget)

        return CategoryMetrics(
            announced_units=announced,
            applied_units=applied,
            delivered_units=delivered,
            remaining_units=remaining_units,
            depletion_rate=depletion_rate,
            delivery_rate=delivery_rate,
            status=status,
            max_local_subsidy_krw=max_local_subsidy,
            max_total_subsidy_krw=max_local_subsidy + national_cap,
            total_budget_krw=total_budget,
            remaining_budget_krw=remaining_budget,
        )

    def update_region_metrics(self, region: RegionRecord) -> RegionRecord:
        """Recalculate overall status and depletion rates for a region."""
        total_announced = 0
        total_applied = 0

        for cat_name, cat in region.categories.items():
            total_announced += cat.announced_units
            total_applied += cat.applied_units
            cat.remaining_units = max(0, cat.announced_units - cat.applied_units)
            cat.depletion_rate = (
                round((cat.applied_units / cat.announced_units * 100.0), 1)
                if cat.announced_units > 0
                else 0.0
            )
            cat.delivery_rate = (
                round((cat.delivered_units / cat.announced_units * 100.0), 1)
                if cat.announced_units > 0
                else 0.0
            )
            cat.status = self.evaluate_status(cat.depletion_rate).value
            if cat.total_budget_krw > 0 and cat.announced_units > 0:
                unit_budget = cat.total_budget_krw / cat.announced_units
                cat.remaining_budget_krw = int(max(0, cat.total_budget_krw - (cat.applied_units * unit_budget)))

        # Recalculate municipalities if present
        if region.municipalities:
            for muni in region.municipalities:
                muni.remaining_units = max(0, muni.announced_units - muni.applied_units)
                muni.depletion_rate = (
                    round((muni.applied_units / muni.announced_units * 100.0), 1)
                    if muni.announced_units > 0
                    else 0.0
                )
                muni.status = self.evaluate_status(muni.depletion_rate).value

        # Overall depletion rate is weighted by volume across all categories
        overall_rate = (
            round((total_applied / total_announced * 100.0), 1)
            if total_announced > 0
            else 0.0
        )
        region.overall_depletion_rate = overall_rate
        region.overall_status = self.evaluate_status(overall_rate).value
        return region

    def compute_nationwide_summary(self, regions: List[RegionRecord]) -> NationwideSummary:
        """Aggregate totals across all tracked regions."""
        total_announced = 0
        total_applied = 0
        total_delivered = 0
        total_budget_krw = 0
        disbursed_budget_krw = 0

        cat_counts: Dict[str, Dict[str, int]] = {
            "passenger": {"announced": 0, "applied": 0, "delivered": 0},
            "commercial": {"announced": 0, "applied": 0, "delivered": 0},
            "bus": {"announced": 0, "applied": 0, "delivered": 0},
        }

        alert_counts: Dict[str, int] = {
            "healthy": 0,
            "caution": 0,
            "warning": 0,
            "critical": 0,
            "depleted": 0,
        }

        for r in regions:
            # Region overall status
            st_key = r.overall_status.lower()
            if st_key in alert_counts:
                alert_counts[st_key] += 1

            for c_name, c_data in r.categories.items():
                if c_name not in cat_counts:
                    cat_counts[c_name] = {"announced": 0, "applied": 0, "delivered": 0}

                cat_counts[c_name]["announced"] += c_data.announced_units
                cat_counts[c_name]["applied"] += c_data.applied_units
                cat_counts[c_name]["delivered"] += c_data.delivered_units

                total_announced += c_data.announced_units
                total_applied += c_data.applied_units
                total_delivered += c_data.delivered_units
                total_budget_krw += c_data.total_budget_krw
                disbursed_budget_krw += (c_data.total_budget_krw - c_data.remaining_budget_krw)

        total_remaining = max(0, total_announced - total_applied)
        nationwide_rate = (
            round((total_applied / total_announced * 100.0), 1)
            if total_announced > 0
            else 0.0
        )

        cat_totals = {}
        for c_name, counts in cat_counts.items():
            c_ann = counts["announced"]
            c_app = counts["applied"]
            c_del = counts["delivered"]
            c_rate = round((c_app / c_ann * 100.0), 1) if c_ann > 0 else 0.0
            c_del_rate = round((c_del / c_ann * 100.0), 1) if c_ann > 0 else 0.0
            cat_totals[c_name] = {
                "announced_units": c_ann,
                "applied_units": c_app,
                "delivered_units": c_del,
                "remaining_units": max(0, c_ann - c_app),
                "depletion_rate": c_rate,
                "delivery_rate": c_del_rate,
                "status": self.evaluate_status(c_rate).value,
            }

        return NationwideSummary(
            total_announced_units=total_announced,
            total_applied_units=total_applied,
            total_delivered_units=total_delivered,
            total_remaining_units=total_remaining,
            nationwide_depletion_rate=nationwide_rate,
            total_budget_billion_krw=round(total_budget_krw / 1_000_000_000, 1),
            disbursed_budget_billion_krw=round(disbursed_budget_krw / 1_000_000_000, 1),
            category_totals=cat_totals,
            alert_region_counts=alert_counts,
        )

    def fetch_live_updates(self) -> Optional[Dict[str, Any]]:
        """Attempt to fetch live data from remote endpoint with graceful fallback."""
        if not self.endpoint_url:
            logger.debug("No endpoint URL configured. Using validated baseline engine.")
            return None

        logger.info("Attempting live poll from %s (timeout=%.1fs)...", self.endpoint_url, self.timeout_seconds)
        try:
            req = urllib.request.Request(
                self.endpoint_url,
                headers={"User-Agent": "MyECar-SubsidyTracker/1.0 (Automated Scheduled Task)"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                if resp.status == 200:
                    raw_data = resp.read().decode("utf-8")
                    return json.loads(raw_data)
                logger.warning("Remote server returned non-200 status: %d", resp.status)
                return None
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            logger.warning("Live fetch failed: %s. Initiating graceful fallback.", exc)
            return None

    def quarantine_corrupted_cache(self, cache_path: Union[str, Path]) -> Optional[Path]:
        """Quarantine a corrupted cache file by renaming it with a timestamp suffix."""
        p = Path(cache_path)
        if not p.exists():
            return None
        try:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            quarantine_path = p.with_name(f"{p.stem}.corrupt_{ts}{p.suffix}")
            p.rename(quarantine_path)
            logger.warning("Quarantined corrupted cache file: %s -> %s", p, quarantine_path)
            return quarantine_path
        except OSError as exc:
            logger.warning("Failed to quarantine corrupted cache file %s: %s", p, exc)
            return None

    def discard_corrupted_cache(self, cache_path: Union[str, Path]) -> bool:
        """Discard a corrupted cache file by removing it from disk."""
        p = Path(cache_path)
        if not p.exists():
            return False
        try:
            p.unlink()
            logger.warning("Discarded corrupted cache file: %s", p)
            return True
        except OSError as exc:
            logger.warning("Failed to discard corrupted cache file %s: %s", p, exc)
            return False

    def load_cached_payload(
        self,
        cache_path: Optional[Union[str, Path]] = None,
        validate: bool = False,
        quarantine: Optional[bool] = None,
    ) -> Optional[SubsidyPayload]:
        """Load and validate cached SubsidyPayload snapshot with corrupted file resilience.

        Hardened against:
        - Malformed/truncated JSON or invalid UTF-8 bytes.
        - Non-dictionary or missing root keys.
        - Invalid schema structures (non-list regions, missing categories).
        - Degenerate cache states.

        If corruption is detected:
        - Logs warning.
        - Quarantines or discards corrupted cache gracefully if quarantine is requested.
        - Gracefully discards invalid payload in memory and returns None (triggering fresh baseline computation).
        """
        target_path = Path(cache_path) if cache_path else self.cache_fallback_path
        if not target_path or not target_path.exists():
            return None

        should_quarantine = self.quarantine_corrupted if quarantine is None else quarantine

        try:
            logger.info("Loading cached snapshot from %s", target_path)
            with open(target_path, "r", encoding="utf-8") as f:
                cached_dict = json.load(f)

            if not isinstance(cached_dict, dict):
                raise ValueError(
                    f"Cache content must be a JSON object (dict), got {type(cached_dict).__name__}"
                )

            payload = SubsidyPayload.from_dict(cached_dict)

            if validate:
                if not payload.regions or len(payload.regions) < 17:
                    raise ValueError(
                        f"Invalid cache schema: expected >= 17 regions, found {len(payload.regions) if payload.regions else 0}"
                    )
                for idx, r in enumerate(payload.regions):
                    if not hasattr(r, "categories") or not isinstance(r.categories, dict):
                        raise ValueError(
                            f"Corrupted region record at index {idx}: missing categories dictionary"
                        )

            return payload
        except Exception as e:
            logger.warning(
                "Failed to load cache %s: %s. Gracefully discarding corrupted cache snapshot.",
                target_path,
                e,
            )
            if should_quarantine:
                self.quarantine_corrupted_cache(target_path)
            return None

    def execute_tracking_cycle(
        self,
        mock_network_failure: bool = False,
        validate_cache: Optional[bool] = None,
        quarantine_corrupted: Optional[bool] = None,
    ) -> Tuple[SubsidyPayload, bool]:
        """Run complete tracking cycle. Returns (payload, is_fallback_used)."""
        logger.info("Starting EV Subsidy tracking cycle...")

        should_validate = self.validate_cache if validate_cache is None else validate_cache
        should_quarantine = self.quarantine_corrupted if quarantine_corrupted is None else quarantine_corrupted

        live_data = None
        if not mock_network_failure and self.endpoint_url:
            live_data = self.fetch_live_updates()

        # If live_data exists and contains valid payload, use it
        if live_data and "regions" in live_data:
            try:
                payload = SubsidyPayload.from_dict(live_data)
                # Recalculate metrics to guarantee invariants
                for idx, r in enumerate(payload.regions):
                    payload.regions[idx] = self.update_region_metrics(r)
                payload.nationwide_summary = self.compute_nationwide_summary(payload.regions)
                payload.metadata.generated_at = datetime.now(timezone.utc).isoformat()
                logger.info("Successfully refreshed tracking data from live endpoint.")
                return payload, False
            except Exception as e:
                logger.warning("Error parsing live data: %s. Falling back to baseline.", e)

        # Fallback to local cached file if available, otherwise built-in baseline
        payload = None
        if self.cache_fallback_path and self.cache_fallback_path.exists():
            payload = self.load_cached_payload(
                cache_path=self.cache_fallback_path,
                validate=should_validate,
                quarantine=should_quarantine,
            )

        if payload is None:
            logger.info("Generating authoritative 2026 baseline dataset.")
            payload = build_initial_baseline()

        # Update timestamp and verify metrics
        try:
            for idx, r in enumerate(payload.regions):
                payload.regions[idx] = self.update_region_metrics(r)
            payload.nationwide_summary = self.compute_nationwide_summary(payload.regions)
            payload.metadata.generated_at = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            if should_validate:
                logger.warning("Structural anomaly updating region metrics: %s. Falling back to baseline.", e)
                if should_quarantine and self.cache_fallback_path:
                    self.quarantine_corrupted_cache(self.cache_fallback_path)
                payload = build_initial_baseline()
                for idx, r in enumerate(payload.regions):
                    payload.regions[idx] = self.update_region_metrics(r)
                payload.nationwide_summary = self.compute_nationwide_summary(payload.regions)
                payload.metadata.generated_at = datetime.now(timezone.utc).isoformat()
            else:
                raise

        return payload, True

    def collect_and_save(
        self,
        sync_web: bool = False,
        output_path: Optional[Union[str, Path]] = None,
        dry_run: bool = False,
        quarantine_corrupted: bool = False,
    ) -> SubsidyPayload:
        """Execute complete subsidy collection cycle and atomically save to disk.

        Conforms to PROJECT.md interface contract:
        SubsidyTracker.collect_and_save(sync_web: bool, output_path: Optional[str], dry_run: bool) -> SubsidyPayload
        """
        payload, fallback_used = self.execute_tracking_cycle(
            validate_cache=True,
            quarantine_corrupted=quarantine_corrupted,
        )

        if not dry_run:
            cwd = Path.cwd()
            destinations: List[Path] = []

            if output_path:
                primary = Path(output_path)
            elif self.cache_fallback_path:
                primary = Path(self.cache_fallback_path)
            elif (cwd / "src" / "data").exists():
                primary = cwd / "src" / "data" / "ev_subsidy_data.json"
            else:
                primary = cwd / "data" / "ev_subsidy_data.json"

            destinations.append(primary)

            # Ensure subsidy_depletion_data.json mirror parity
            if primary.name == "ev_subsidy_data.json":
                destinations.append(primary.parent / "subsidy_depletion_data.json")
            elif primary.name == "subsidy_depletion_data.json":
                destinations.append(primary.parent / "ev_subsidy_data.json")

            if sync_web:
                web_dir_env = os.getenv("EV_TRACKER_WEB_DIR")
                if web_dir_env:
                    web_dir = Path(web_dir_env)
                    destinations.append(web_dir / "ev_subsidy_data.json")
                    destinations.append(web_dir / "subsidy_depletion_data.json")
                elif (cwd / "src" / "data").exists():
                    destinations.append(cwd / "src" / "data" / "ev_subsidy_data.json")
                    destinations.append(cwd / "src" / "data" / "subsidy_depletion_data.json")
                    if (cwd.parent / "data").exists():
                        destinations.append(cwd.parent / "data" / "ev_subsidy_data.json")
                        destinations.append(cwd.parent / "data" / "subsidy_depletion_data.json")
                else:
                    destinations.append(cwd / "ev-stealth-web" / "src" / "data" / "ev_subsidy_data.json")
                    destinations.append(cwd / "ev-stealth-web" / "src" / "data" / "subsidy_depletion_data.json")

            # Deduplicate destinations preserving order
            unique_destinations: List[Path] = []
            seen_paths = set()
            for dst in destinations:
                resolved_key = str(dst.resolve()) if dst.exists() else str(dst.absolute())
                if resolved_key not in seen_paths:
                    seen_paths.add(resolved_key)
                    unique_destinations.append(dst)

            self.save_payload(payload, unique_destinations)

        return payload

    def save_payload(
        self,
        payload: SubsidyPayload,
        destination_paths: List[Union[str, Path]],
    ) -> List[Path]:
        """Atomically persist payload to all destination paths."""
        written = atomic_write_json_multiple(payload, destination_paths)
        for w in written:
            logger.info("Saved subsidy dataset: %s", w)
        return written

    def generate_briefing(self, payload: SubsidyPayload, fallback_used: bool = False) -> str:
        """Generate formatted executive markdown summary briefing."""
        summary = payload.nationwide_summary
        gen_time = payload.metadata.generated_at

        critical_regions = [
            f"{r.name_ko} ({r.overall_depletion_rate}%, 잔여: {r.categories['passenger'].remaining_units:,}대)"
            for r in payload.regions
            if r.overall_status in ("CRITICAL", "DEPLETED")
        ]
        warning_regions = [
            f"{r.name_ko} ({r.overall_depletion_rate}%, 잔여: {r.categories['passenger'].remaining_units:,}대)"
            for r in payload.regions
            if r.overall_status == "WARNING"
        ]

        p_info = summary.category_totals.get("passenger", {})
        c_info = summary.category_totals.get("commercial", {})
        b_info = summary.category_totals.get("bus", {})

        status_text = "FALLBACK_BASELINE (Resilient)" if fallback_used else "SUCCESS (Live Sync)"

        lines = [
            "# [대한민국 2026 전국 지자체 전기차 보조금 실시간 소진율 모니터링]",
            f"- **기록 시각(UTC)**: {gen_time}",
            f"- **파이프라인 상태**: {status_text}",
            f"- **전국 평균 소진율**: {summary.nationwide_depletion_rate}% (총 공고: {summary.total_announced_units:,}대 / 접수: {summary.total_applied_units:,}대)",
            f"- **집행 예산**: {summary.disbursed_budget_billion_krw:,}억 원 / 총 예산 {summary.total_budget_billion_krw:,}억 원",
            "",
            "## 🚨 긴급 마감 임박 지자체 (CRITICAL / DEPLETED >= 95%)",
            (
                "\n".join([f"  - 🔴 {cr}" for cr in critical_regions])
                if critical_regions
                else "  - 현재 접수 마감된 긴급 지자체 없음."
            ),
            "",
            "## ⚠️ 주의·경고 지자체 (WARNING 80% ~ 94.9%)",
            (
                "\n".join([f"  - 🟠 {wr}" for wr in warning_regions])
                if warning_regions
                else "  - 경고 지역 없음."
            ),
            "",
            "## 📊 차종별 소진 현황",
            f"- **승용**: 공고 {p_info.get('announced_units', 0):,}대 | 접수 {p_info.get('applied_units', 0):,}대 ({p_info.get('depletion_rate', 0)}%) | 잔여 {p_info.get('remaining_units', 0):,}대 [{p_info.get('status', 'N/A')}]",
            f"- **화물**: 공고 {c_info.get('announced_units', 0):,}대 | 접수 {c_info.get('applied_units', 0):,}대 ({c_info.get('depletion_rate', 0)}%) | 잔여 {c_info.get('remaining_units', 0):,}대 [{c_info.get('status', 'N/A')}]",
            f"- **승합(버스)**: 공고 {b_info.get('announced_units', 0):,}대 | 접수 {b_info.get('applied_units', 0):,}대 ({b_info.get('depletion_rate', 0)}%) | 잔여 {b_info.get('remaining_units', 0):,}대 [{b_info.get('status', 'N/A')}]",
            "",
            "## 💡 예비 차주 권고 사항",
            "- 대구, 울산, 경북, 제주는 보조금 마감 직전(소진율 96%~99%)입니다. 실계약자는 대기 순번 및 제조사 즉시 출고 재고를 확인하십시오.",
            "- 전남(신안 1,150만 원), 경북(울릉 1,100만 원), 충남(태안 900만 원) 등 군 단위 지역은 고액 보조금이 지급되나 거주기간 요건(30~90일)을 확인해야 합니다.",
        ]
        return "\n".join(lines)


__all__ = [
    "SubsidyTracker",
    "get_baseline_regions",
    "get_baseline_models",
    "get_baseline_thresholds",
    "get_baseline_dataset",
    "calculate_depletion_rate",
    "calculate_remaining_units",
    "classify_alert_tier",
    "calculate_price_cap_ratio",
    "calculate_net_subsidy",
]
