"""Comprehensive test suite for EV Subsidy Models and Report Generator Audit.

Covers:
1. RegionSubsidy, VehicleSubsidy, SubsidySnapshot models and methods.
2. Dict-like bracket access obj['key'] and .get(key) support alongside attribute access.
3. Report generator markdown templates: formatting of percentage numbers, currency representation (만 원 / 억 원).
4. Edge cases when dataset has empty regions, missing vehicle entries, or malformed values.
"""

from __future__ import annotations

import unittest
from tracker import (
    CategoryMetrics,
    MunicipalityMetrics,
    NationwideSummary,
    PopularModelEntry,
    RegionRecord,
    RegionSubsidy,
    ReportGenerator,
    SubsidyMetadata,
    SubsidyPayload,
    SubsidySnapshot,
    VehicleSubsidy,
    format_currency_krw,
    format_percentage,
)


class TestSubsidyModelsAndReportGeneratorAudit(unittest.TestCase):
    """Deep verification of models, dict-like access, formatters, and report edge cases."""

    def setUp(self) -> None:
        self.report_gen = ReportGenerator()

    # -------------------------------------------------------------------------
    # 1. RegionSubsidy, VehicleSubsidy, SubsidySnapshot Models and Methods
    # -------------------------------------------------------------------------
    def test_01_model_aliases_identity_and_instantiation(self) -> None:
        """Verify RegionSubsidy, VehicleSubsidy, SubsidySnapshot aliases and type safety."""
        self.assertIs(RegionSubsidy, RegionRecord)
        self.assertIs(VehicleSubsidy, PopularModelEntry)
        self.assertIs(SubsidySnapshot, SubsidyPayload)

        # RegionSubsidy instantiation and methods
        p_cat = CategoryMetrics(
            announced_units=1000,
            applied_units=850,
            delivered_units=800,
            remaining_units=150,
            depletion_rate=85.0,
            delivery_rate=80.0,
            status="WARNING",
            max_local_subsidy_krw=4000000,
            max_total_subsidy_krw=10500000,
            total_budget_krw=10500000000,
            remaining_budget_krw=1575000000,
        )
        muni = MunicipalityMetrics(
            name_ko="수원시",
            announced_units=500,
            applied_units=400,
            remaining_units=100,
            depletion_rate=80.0,
            status="WARNING",
            local_subsidy_krw=3500000,
            muni_id="KR-41-111",
            name_en="Suwon-si",
            total_subsidy_krw=10000000,
        )
        region = RegionSubsidy(
            region_id="KR-41",
            iso_code="KR-41",
            name_ko="경기도",
            name_en="Gyeonggi-do",
            tier="province",
            overall_depletion_rate=85.0,
            overall_status="WARNING",
            residency_requirement_days=30,
            categories={"passenger": p_cat},
            municipalities=[muni],
        )

        self.assertIsInstance(region, RegionRecord)
        self.assertIsInstance(region, RegionSubsidy)
        self.assertEqual(region.code, "KR-41")  # Auto-synced in __post_init__
        self.assertEqual(region.get_category("passenger"), p_cat)
        self.assertIsNone(region.get_category("commercial"))
        self.assertEqual(region.get_remaining_units("passenger"), 150)
        self.assertEqual(region.get_remaining_units("commercial"), 0)
        self.assertEqual(region.get_depletion_rate("passenger"), 85.0)
        self.assertEqual(region.get_local_subsidy("passenger"), 4000000)
        self.assertEqual(region.get_total_subsidy("passenger"), 10500000)
        self.assertIsNotNone(region.get_municipality("KR-41-111"))
        self.assertIsNotNone(region.get_municipality("수원시"))
        self.assertIsNotNone(region.get_municipality("suwon-si"))
        self.assertIsNone(region.get_municipality("안양시"))
        self.assertTrue(region.is_warning())
        self.assertFalse(region.is_critical())
        self.assertFalse(region.is_depleted())

        # Critical / Depleted edge cases
        crit_region = RegionSubsidy(
            region_id="KR-49",
            name_ko="제주특별자치도",
            overall_depletion_rate=99.0,
            overall_status="CRITICAL",
        )
        self.assertTrue(crit_region.is_critical())
        self.assertFalse(crit_region.is_warning())

        dep_region = RegionSubsidy(
            region_id="KR-27",
            name_ko="대구광역시",
            overall_depletion_rate=100.0,
            overall_status="DEPLETED",
        )
        self.assertTrue(dep_region.is_depleted())
        self.assertTrue(dep_region.is_critical())

    def test_02_vehicle_subsidy_methods_and_pricing(self) -> None:
        """Verify VehicleSubsidy methods: regional lookup, total subsidy, and net pricing."""
        vehicle = VehicleSubsidy(
            model_id="ioniq6_long_range",
            name_ko="아이오닉 6 롱레인지",
            manufacturer="현대",
            battery_type="NCM",
            battery_capacity_kwh=77.4,
            rated_range_km=524,
            base_price_krw=54000000,
            price_subsidy_ratio=1.0,
            national_subsidy_krw=6900000,
            regional_subsidy_samples={
                "KR-11": {"local_subsidy_krw": 1500000},
                "KR-49": {"local_subsidy_krw": 4000000},
                "KR-46": 11500000,  # Plain integer local subsidy sample
            },
        )

        self.assertIsInstance(vehicle, PopularModelEntry)
        self.assertIsInstance(vehicle, VehicleSubsidy)

        # Regional subsidy lookup
        self.assertEqual(vehicle.get_regional_subsidy("KR-11"), 1500000)
        self.assertEqual(vehicle.get_regional_subsidy("kr-11"), 1500000)  # Case-insensitive
        self.assertEqual(vehicle.get_regional_subsidy("KR-49"), 4000000)
        self.assertEqual(vehicle.get_regional_subsidy("KR-46"), 11500000)
        self.assertEqual(vehicle.get_regional_subsidy("KR-99"), 0)  # Unknown region

        # Total subsidy & Final purchase price
        self.assertEqual(vehicle.calculate_total_subsidy("KR-11"), 6900000 + 1500000)  # 8,400,000
        self.assertEqual(vehicle.calculate_final_price("KR-11"), 54000000 - 8400000)   # 45,600,000
        self.assertEqual(vehicle.get_subsidy("KR-11"), 8400000)

        # Clamped final price if subsidy exceeds base price
        cheap_car = VehicleSubsidy(
            model_id="cheap_ev",
            name_ko="초소형 전기차",
            manufacturer="중소기업",
            battery_type="LFP",
            battery_capacity_kwh=15.0,
            rated_range_km=100,
            base_price_krw=10000000,
            price_subsidy_ratio=1.0,
            national_subsidy_krw=6000000,
            regional_subsidy_samples={"KR-46": {"local_subsidy_krw": 6000000}},
        )
        self.assertEqual(cheap_car.calculate_final_price("KR-46"), 0)  # Max(0, 10M - 12M)

    def test_03_subsidy_snapshot_methods_and_filtering(self) -> None:
        """Verify SubsidySnapshot helper methods for regions, vehicles, and status querying."""
        meta = SubsidyMetadata(
            version="1.0.0",
            generated_at="2026-11-04T00:00:00Z",
            policy_year=2026,
            data_sources=["ev.or.kr"],
            total_regions_tracked=3,
            total_municipalities_tracked=5,
        )
        summary = NationwideSummary(
            total_announced_units=3000,
            total_applied_units=2700,
            total_delivered_units=2500,
            total_remaining_units=300,
            nationwide_depletion_rate=90.0,
            total_budget_billion_krw=35.0,
            disbursed_budget_billion_krw=31.5,
            category_totals={},
            alert_region_counts={"CRITICAL": 1, "WARNING": 1, "HEALTHY": 1},
        )
        r_seoul = RegionSubsidy(region_id="KR-11", name_ko="서울특별시", overall_depletion_rate=75.0, overall_status="HEALTHY")
        r_daegu = RegionSubsidy(region_id="KR-27", name_ko="대구광역시", overall_depletion_rate=96.0, overall_status="CRITICAL")
        r_gyeonggi = RegionSubsidy(region_id="KR-41", name_ko="경기도", overall_depletion_rate=88.0, overall_status="WARNING")

        m_ioniq5 = VehicleSubsidy(
            model_id="ioniq5_std",
            name_ko="아이오닉 5",
            manufacturer="현대",
            battery_type="NCM",
            battery_capacity_kwh=58.2,
            rated_range_km=370,
            base_price_krw=50000000,
            price_subsidy_ratio=1.0,
            national_subsidy_krw=6500000,
            regional_subsidy_samples={},
        )

        snapshot = SubsidySnapshot(
            metadata=meta,
            alert_thresholds={},
            nationwide_summary=summary,
            regions=[r_seoul, r_daegu, r_gyeonggi],
            popular_models_matrix=[m_ioniq5],
            historical_depletion_trajectory=[],
        )

        self.assertIsInstance(snapshot, SubsidyPayload)
        self.assertIsInstance(snapshot, SubsidySnapshot)
        self.assertEqual(snapshot.total_regions(), 3)
        self.assertEqual(snapshot.total_models(), 1)

        # Region lookups
        self.assertEqual(snapshot.get_region("KR-11"), r_seoul)
        self.assertEqual(snapshot.get_region("서울특별시"), r_seoul)
        self.assertEqual(snapshot.get_region("seoul"), None)
        self.assertEqual(snapshot.get_region("KR-27"), r_daegu)
        self.assertIsNone(snapshot.get_region("KR-99"))

        # Model lookups
        self.assertEqual(snapshot.get_model("ioniq5_std"), m_ioniq5)
        self.assertEqual(snapshot.get_model("아이오닉 5"), m_ioniq5)
        self.assertEqual(snapshot.get_vehicle("ioniq5_std"), m_ioniq5)
        self.assertIsNone(snapshot.get_model("ev6"))

        # Category filter methods
        crit = snapshot.get_critical_regions()
        self.assertEqual(len(crit), 1)
        self.assertEqual(crit[0].name_ko, "대구광역시")

        warn = snapshot.get_warning_regions()
        self.assertEqual(len(warn), 1)
        self.assertEqual(warn[0].name_ko, "경기도")

        healthy = snapshot.get_healthy_regions()
        self.assertEqual(len(healthy), 1)
        self.assertEqual(healthy[0].name_ko, "서울특별시")

        # from_json parsing
        json_blob = '{"metadata": {"version": "2.0.0", "policy_year": 2026}, "regions": [{"region_id": "KR-11", "name_ko": "서울"}]}'
        parsed = SubsidySnapshot.from_json(json_blob)
        self.assertEqual(parsed.metadata.version, "2.0.0")
        self.assertEqual(len(parsed.regions), 1)
        self.assertEqual(parsed.regions[0].region_id, "KR-11")

    # -------------------------------------------------------------------------
    # 2. Dict-like Bracket Access obj['key'] and .get(key) Support
    # -------------------------------------------------------------------------
    def test_04_dict_like_access_on_all_models_and_aliases(self) -> None:
        """Verify obj['key'], obj.get(key), and 'in' containment for standard keys and aliases."""
        # 1. RegionRecord / RegionSubsidy
        region = RegionSubsidy(
            region_id="KR-11",
            iso_code="KR-11",
            name_ko="서울특별시",
            overall_depletion_rate=78.5,
            overall_status="CAUTION",
            residency_requirement_days=30,
        )
        self.assertEqual(region["region_id"], "KR-11")
        self.assertEqual(region["code"], "KR-11")
        self.assertEqual(region["id"], "KR-11")           # Alias
        self.assertEqual(region["name"], "서울특별시")    # Alias
        self.assertEqual(region["depletion_rate"], 78.5) # Alias
        self.assertEqual(region["status"], "CAUTION")     # Alias
        self.assertEqual(region["residency_days"], 30)    # Alias
        self.assertEqual(region.get("id"), "KR-11")
        self.assertEqual(region.get("non_existent", "def"), "def")
        self.assertIn("id", region)
        self.assertIn("depletion_rate", region)
        self.assertNotIn("unknown_field", region)
        with self.assertRaises(KeyError):
            _ = region["unknown_field"]

        # 2. PopularModelEntry / VehicleSubsidy
        model = VehicleSubsidy(
            model_id="ev6_gt",
            name_ko="EV6 GT",
            manufacturer="기아",
            battery_type="NCM",
            battery_capacity_kwh=77.4,
            rated_range_km=342,
            base_price_krw=72000000,
            price_subsidy_ratio=0.5,
            national_subsidy_krw=3100000,
            regional_subsidy_samples={},
        )
        self.assertEqual(model["id"], "ev6_gt")              # Alias
        self.assertEqual(model["name"], "EV6 GT")            # Alias
        self.assertEqual(model["model_name"], "EV6 GT")      # Alias
        self.assertEqual(model["brand"], "기아")              # Alias
        self.assertEqual(model["maker"], "기아")              # Alias
        self.assertEqual(model["price"], 72000000)           # Alias
        self.assertEqual(model["national_subsidy"], 3100000) # Alias
        self.assertEqual(model["capacity"], 77.4)            # Alias
        self.assertEqual(model["range"], 342)                # Alias
        self.assertIn("brand", model)
        self.assertIn("price", model)
        self.assertNotIn("not_real", model)
        self.assertEqual(model.get("not_real", 99), 99)

        # 3. NationwideSummary
        summary = NationwideSummary(
            total_announced_units=100000,
            total_applied_units=85000,
            total_delivered_units=80000,
            total_remaining_units=15000,
            nationwide_depletion_rate=85.0,
            total_budget_billion_krw=1500.0,
            disbursed_budget_billion_krw=1275.0,
            category_totals={},
            alert_region_counts={},
        )
        self.assertEqual(summary["announced"], 100000)         # Alias
        self.assertEqual(summary["applied"], 85000)            # Alias
        self.assertEqual(summary["delivered"], 80000)          # Alias
        self.assertEqual(summary["remaining"], 15000)          # Alias
        self.assertEqual(summary["rate"], 85.0)                # Alias
        self.assertEqual(summary["total_budget"], 1500.0)      # Alias
        self.assertEqual(summary["disbursed_budget"], 1275.0)  # Alias
        self.assertEqual(summary["disbursed_budget_krw"], 1275000000000)
        self.assertIn("rate", summary)
        self.assertIn("disbursed_budget_krw", summary)

        # 4. SubsidyPayload / SubsidySnapshot
        snapshot = SubsidySnapshot(
            metadata=SubsidyMetadata(
                version="1.0.0",
                generated_at="2026-11-04T00:00:00Z",
                policy_year=2026,
                data_sources=["ev.or.kr"],
                total_regions_tracked=1,
                total_municipalities_tracked=0,
            ),
            alert_thresholds={},
            nationwide_summary=summary,
            regions=[region],
            popular_models_matrix=[model],
            historical_depletion_trajectory=[],
        )
        self.assertEqual(snapshot["summary"], summary)                    # Alias
        self.assertEqual(snapshot["models"], [model])                     # Alias
        self.assertEqual(snapshot["vehicles"], [model])                   # Alias
        self.assertEqual(snapshot["generated_at"], "2026-11-04T00:00:00Z") # Delegated to metadata
        self.assertEqual(snapshot["version"], "1.0.0")                    # Delegated to metadata
        self.assertIn("vehicles", snapshot)
        self.assertIn("generated_at", snapshot)
        self.assertNotIn("ghost_key", snapshot)

    # -------------------------------------------------------------------------
    # 3. Report Generator Markdown Templates & Currency Representation
    # -------------------------------------------------------------------------
    def test_05_format_currency_krw_and_format_percentage(self) -> None:
        """Verify format_currency_krw and format_percentage representations."""
        # 만 원 units
        self.assertEqual(format_currency_krw(11500000), "1,150만 원")
        self.assertEqual(format_currency_krw(9000000), "900만 원")
        self.assertEqual(format_currency_krw(1500000), "150만 원")
        self.assertEqual(format_currency_krw(6500000), "650만 원")
        self.assertEqual(format_currency_krw(50000000), "5,000만 원")
        self.assertEqual(format_currency_krw(50000000, unit="만 원"), "5,000만 원")

        # 억 원 units
        self.assertEqual(format_currency_krw(1893.4, unit="billion"), "1,893.4억 원")
        self.assertEqual(format_currency_krw(2105.0, unit="billion"), "2,105억 원")
        self.assertEqual(format_currency_krw(100000000), "1억 원")
        self.assertEqual(format_currency_krw(1275000000000), "12,750억 원")

        # Zero and fallback handling
        self.assertEqual(format_currency_krw(0), "0원")
        self.assertEqual(format_currency_krw(None), "0원")
        self.assertEqual(format_currency_krw(float("nan")), "0원")

        # Percentage formatting
        self.assertEqual(format_percentage(89.4), "89.4%")
        self.assertEqual(format_percentage(99.0), "99.0%")
        self.assertEqual(format_percentage(100.0, decimals=0), "100%")
        self.assertEqual(format_percentage(float("nan")), "0.0%")
        self.assertEqual(format_percentage(None), "0.0%")

    def test_06_vehicle_subsidy_briefing_table(self) -> None:
        """Verify generate_vehicle_subsidy_briefing generates valid markdown tables in 만 원."""
        model1 = VehicleSubsidy(
            model_id="ioniq5_std",
            name_ko="아이오닉 5",
            manufacturer="현대",
            battery_type="NCM",
            battery_capacity_kwh=58.2,
            rated_range_km=370,
            base_price_krw=50000000,
            price_subsidy_ratio=1.0,
            national_subsidy_krw=6500000,
            regional_subsidy_samples={"KR-11": {"local_subsidy_krw": 1500000}},
        )
        model2 = VehicleSubsidy(
            model_id="ev3_std",
            name_ko="EV3 스탠다드",
            manufacturer="기아",
            battery_type="NCM",
            battery_capacity_kwh=58.3,
            rated_range_km=350,
            base_price_krw=39950000,
            price_subsidy_ratio=1.0,
            national_subsidy_krw=5400000,
            regional_subsidy_samples={"KR-11": {"local_subsidy_krw": 1500000}},
        )

        table_md = self.report_gen.generate_vehicle_subsidy_briefing([model1, model2], target_region="KR-11")
        self.assertIn("## 🚗 주요 인기 전기차 국비·지방비 보조금 및 실구매가 매트릭스 (기준: 서울특별시)", table_md)
        self.assertIn("| 제조사 | 모델명 | 기본가격 | 국비 보조금 | 지방비 보조금 | 총 보조금 | 실구매가 (체감가) |", table_md)
        self.assertIn("현대 | 아이오닉 5 | 5,000만 원 | 650만 원 | 150만 원 | 800만 원 | **4,200만 원**", table_md)
        self.assertIn("기아 | EV3 스탠다드", table_md)

    # -------------------------------------------------------------------------
    # 4. Edge Cases: Empty Regions, Missing Vehicles, Malformed Values
    # -------------------------------------------------------------------------
    def test_07_empty_and_none_dataset_resilience(self) -> None:
        """Briefing generator must handle None, empty dicts, empty regions, and missing vehicles gracefully."""
        # 1. Completely None payload
        briefing_none = self.report_gen.generate_subsidy_briefing(None)
        self.assertIn("# [대한민국 2026 전국 지자체 전기차 보조금 실시간 소진율 모니터링]", briefing_none)
        self.assertIn("현재 접수 마감된 긴급 지자체 없음.", briefing_none)
        self.assertIn("경고 지역 없음.", briefing_none)

        # 2. Empty dict payload
        briefing_empty = self.report_gen.generate_subsidy_briefing({})
        self.assertIn("# [대한민국 2026 전국 지자체 전기차 보조금 실시간 소진율 모니터링]", briefing_empty)

        # 3. Payload with empty regions and include_models=True
        empty_payload = SubsidySnapshot(
            metadata=SubsidyMetadata("1.0", "2026-11-04T00:00:00Z", 2026, [], 0, 0),
            alert_thresholds={},
            nationwide_summary=NationwideSummary(0, 0, 0, 0, 0.0, 0.0, 0.0, {}, {}),
            regions=[],
            popular_models_matrix=[],
            historical_depletion_trajectory=[],
        )
        briefing_full = self.report_gen.generate_subsidy_briefing(empty_payload, include_models=True)
        self.assertIn("현재 접수 마감된 긴급 지자체 없음.", briefing_full)
        self.assertIn("등록된 주요 인기 차종 정보가 없습니다.", briefing_full)

        # 4. Statistical report with None and empty list
        stat_none = self.report_gen.generate_statistical_report(None)
        self.assertIn("분석 표본수**: 총 0건", stat_none)

        # 5. Defect briefing with None
        defect_none = self.report_gen.generate_defect_briefing(None)
        self.assertIn("총 수집/분류 결함 건수**: 0건", defect_none)
        self.assertIn("수집된 결함 내역이 없습니다.", defect_none)

    def test_08_malformed_nested_values_handling(self) -> None:
        """Verify resilience when region categories are lists instead of dicts or contain None values."""
        malformed_region = {
            "name_ko": "울릉군",
            "overall_status": "critical",
            "overall_depletion_rate": float("nan"),
            "categories": [
                {"category": "passenger", "remaining_units": None},
                {"category": "commercial", "remaining_units": 15},
            ],
        }
        malformed_summary = {
            "disbursed_budget_billion_krw": None,
            "disbursed_budget_krw": 1893400000000,  # Fallback to KRW
            "total_budget_billion_krw": float("inf"),
            "category_totals": None,  # Not a dict!
        }
        payload = {
            "metadata": {"generated_at": None},
            "nationwide_summary": malformed_summary,
            "regions": [malformed_region],
        }

        briefing = self.report_gen.generate_subsidy_briefing(payload)
        self.assertIn("울릉군", briefing)
        self.assertIn("1,893.4억 원", briefing)  # Successfully computed from disbursed_budget_krw


if __name__ == "__main__":
    unittest.main()
