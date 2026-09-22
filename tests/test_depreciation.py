"""
tests/test_depreciation.py - Comprehensive Unit & Behavioral Test Suite for EV Depreciation & TCO.

Scope & Behavioral Verification:
1. Data schema completeness:
   - 15 models across 8 major automotive brands.
   - Complete battery chemistry profiles (LFP, NCM_622, NCM_811, NCMA, NCA).
   - Battery replacement cost tiers (TIER_50KWH, TIER_77KWH, TIER_100KWH).
   - Adjustment factors, market context, and statutory sources.
2. Strict monotonic decrease of residual percentages over 1 to 5 years for all 15 models:
   - Residual % (MSRP basis) 100 > Year 1 > Year 2 > Year 3 > Year 4 > Year 5 > 0.
   - Residual % (Effective basis) strictly decreasing.
   - Depreciation % strictly increasing.
   - Resale average price strictly decreasing.
   - Defense tier ranking hierarchy (S, A, A-, B+, B, B-, C+, C, D).
3. Battery health degradation simulation boundary values:
   - Boundary totalKm = 0 km (pure calendar aging, 0 cyclic loss, SoH >= 98%).
   - Boundary totalKm = 500,000 km (severe cyclic fatigue, bounded in [0, 100]%, Grade C/Critical).
   - 0% DCFC vs 100% DCFC acceleration strain comparison.
   - Temperature extremes (-15°C cold charge penalty, +45°C Arrhenius acceleration).
   - Storage SoC kinetic sensitivity.
4. Statutory Korean 2-year subsidy clawback schedule:
   - All 8 statutory tiers ([0,3), [3,6), [6,9), [9,12), [12,15), [15,18), [18,21), [21,24)).
   - Intra-province transfer waiver (0 KRW clawback, 100% exemption).
   - Inter-province transfer (local subsidy clawed back according to rate; national subsidy exempt).
   - Export deregistration (both national and local subsidies clawed back).
   - 24-month statutory cliff (0% clawback rate, total exemption across all transfer types).
5. TCO economic calculations:
   - Slow charging (250 KRW/kWh) vs Fast charging (347.2 KRW/kWh) fuel tariffs.
   - ICE gasoline baseline (1,700 KRW/L, 12 km/L).
   - EV flat automobile tax (130,000 KRW = 100,000 KRW base + 30,000 KRW education tax).
   - ICE displacement tax tiers (80, 140, 200 KRW/cc) and age discount (up to 50%).
   - Auxiliary benefits (highway toll, public parking, maintenance = 600,000 KRW/year).
   - Cumulative net savings strict monotonic growth.
6. TypeScript Engine Parity (Oracle Cross-Validation):
   - Node-based evaluation of getDepreciationData.ts verifying exact parity with Python reference models.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from typing import Any, Dict, List, Optional, Tuple


def find_depreciation_data_file() -> Path:
    """Locate ev_depreciation_data.json robustly regardless of working directory."""
    current_file = Path(__file__).resolve()
    search_candidates = [
        current_file.parent.parent / "ev-stealth-web" / "src" / "data" / "ev_depreciation_data.json",
        current_file.parent.parent / "src" / "data" / "ev_depreciation_data.json",
        Path.cwd() / "ev-stealth-web" / "src" / "data" / "ev_depreciation_data.json",
        Path.cwd() / "src" / "data" / "ev_depreciation_data.json",
    ]
    for candidate in search_candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    raise FileNotFoundError(f"ev_depreciation_data.json not found in candidates: {search_candidates}")


def find_ts_library_file() -> Optional[Path]:
    """Locate getDepreciationData.ts if available."""
    current_file = Path(__file__).resolve()
    search_candidates = [
        current_file.parent.parent / "ev-stealth-web" / "src" / "lib" / "getDepreciationData.ts",
        current_file.parent.parent / "src" / "lib" / "getDepreciationData.ts",
        Path.cwd() / "ev-stealth-web" / "src" / "lib" / "getDepreciationData.ts",
        Path.cwd() / "src" / "lib" / "getDepreciationData.ts",
    ]
    for candidate in search_candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


DATA_FILE = find_depreciation_data_file()
with open(DATA_FILE, "r", encoding="utf-8") as f:
    RAW_DATABASE = json.load(f)


# ==============================================================================
# Python Reference Implementation (Mirroring getDepreciationData.ts)
# ==============================================================================

def clamp(val: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(val, max_val))


def normalize_chemistry(chem: str) -> str:
    upper = chem.upper()
    if "LFP" in upper:
        return "LFP"
    if "622" in upper:
        return "NCM_622"
    if "NCMA" in upper:
        return "NCMA"
    if "NCA" in upper:
        return "NCA"
    return "NCM_811"


def interpolate_baseline_residual(curve: Dict[str, Any], years: float, basis: str = "msrp") -> float:
    key = "residual_pct_effective" if basis == "effective" else "residual_pct_msrp"
    if years <= 0:
        return 100.0
    if years <= 1.0:
        y1 = curve["year_1"][key]
        return 100.0 - years * (100.0 - y1)
    if years <= 2.0:
        y1 = curve["year_1"][key]
        y2 = curve["year_2"][key]
        return y1 - (years - 1.0) * (y1 - y2)
    if years <= 3.0:
        y2 = curve["year_2"][key]
        y3 = curve["year_3"][key]
        return y2 - (years - 2.0) * (y2 - y3)
    if years <= 4.0:
        y3 = curve["year_3"][key]
        y4 = curve["year_4"][key]
        return y3 - (years - 3.0) * (y3 - y4)
    if years <= 5.0:
        y4 = curve["year_4"][key]
        y5 = curve["year_5"][key]
        return y4 - (years - 4.0) * (y4 - y5)

    y5 = curve["year_5"][key]
    excess = years - 5.0
    extrapolated = y5 * math.pow(0.92, excess)
    return max(10.0, extrapolated)


def calculate_depreciation(
    model_id: str,
    years: float,
    mileage_km: Optional[float] = None,
    winter_season: bool = False,
    price_basis: str = "msrp",
    custom_purchase_price_krw: Optional[int] = None,
) -> Dict[str, Any]:
    models = RAW_DATABASE["models"]
    model = next((m for m in models if m["id"].lower() == model_id.lower()), models[0])
    baseline_annual_km = RAW_DATABASE["metadata"]["baseline_annual_mileage_km"]
    if mileage_km is None:
        mileage_km = years * baseline_annual_km

    baseline_residual = interpolate_baseline_residual(model["depreciation_curve"], years, price_basis)

    # 1. Mileage Adjustment
    expected_km = years * baseline_annual_km
    delta_km = mileage_km - expected_km
    if delta_km > 0:
        mileage_adj = (delta_km / 10000.0) * RAW_DATABASE["adjustment_factors"]["mileage_sensitivity"]["penalty_per_10000km_excess"]
    else:
        bonus_rate = RAW_DATABASE["adjustment_factors"]["mileage_sensitivity"]["bonus_per_10000km_deficit"]
        mileage_adj = min(0.06, (abs(delta_km) / 10000.0) * bonus_rate)

    # 2. Warranty Cliff
    rem_years = model["warranty"]["years"] - years
    rem_km = model["warranty"]["km"] - mileage_km
    is_expired = rem_years <= 0 or rem_km <= 0
    is_approaching = (not is_expired) and (rem_years <= 2 or rem_km <= 25000)

    warranty_penalty = 0.0
    if is_expired:
        warranty_penalty = RAW_DATABASE["adjustment_factors"]["warranty_cliff"]["expired_warranty_penalty"]
    elif is_approaching:
        warranty_penalty = RAW_DATABASE["adjustment_factors"]["warranty_cliff"]["approaching_cliff_1_2_years_penalty"]

    # 3. Chemistry Aging
    chem_bonus = model["factor_weights"]["chemistry_aging"]
    if "LFP" in model["battery_specs"]["chemistry"] and years >= 3:
        chem_bonus += 0.01

    # 4. Winter Season
    winter_adj = 0.0
    if winter_season:
        if "LFP" in model["battery_specs"]["chemistry"]:
            winter_adj = -0.035
        else:
            winter_adj = -0.015

    # 5. Architecture & OTA
    arch_adj = model["factor_weights"]["architecture_800v"]
    ota_adj = model["factor_weights"]["ota_maturity"]

    total_adj_pct = (warranty_penalty + chem_bonus + arch_adj + ota_adj + mileage_adj + winter_adj) * 100.0
    adjusted_residual = clamp(round((baseline_residual + total_adj_pct) * 10.0) / 10.0, 5.0, 99.0)

    base_price = (
        custom_purchase_price_krw
        if custom_purchase_price_krw is not None
        else (model["net_purchase_price_krw"] if price_basis == "effective" else model["msrp_krw_baseline"])
    )

    residual_price = round((base_price * adjusted_residual) / 100.0)
    deprec_amount = base_price - residual_price

    return {
        "model_id": model["id"],
        "years": years,
        "mileage_km": mileage_km,
        "price_basis": price_basis,
        "base_purchase_price_krw": base_price,
        "baseline_residual_pct": round(baseline_residual * 10.0) / 10.0,
        "adjusted_residual_pct": adjusted_residual,
        "estimated_residual_price_krw": residual_price,
        "depreciation_amount_krw": deprec_amount,
        "defense_tier": model["resale_defense_tier"],
        "factor_adjustments": {
            "warranty_cliff_penalty": round(warranty_penalty * 1000.0) / 10.0,
            "battery_chemistry_bonus": round(chem_bonus * 1000.0) / 10.0,
            "architecture_adjustment": round(arch_adj * 1000.0) / 10.0,
            "ota_adjustment": round(ota_adj * 1000.0) / 10.0,
            "mileage_adjustment": round(mileage_adj * 1000.0) / 10.0,
            "winter_adjustment": round(winter_adj * 1000.0) / 10.0,
            "total_adjustment_pct": round(total_adj_pct * 10.0) / 10.0,
        },
        "warranty_status": {
            "is_approaching_cliff": is_approaching,
            "is_expired": is_expired,
            "remaining_years": max(0.0, round(rem_years * 10.0) / 10.0),
            "remaining_km": max(0.0, rem_km),
        },
    }


def simulate_battery_health(
    years: float,
    total_km: Optional[float] = None,
    annual_km: float = 15000.0,
    chemistry: str = "NCM_811",
    dcfc_ratio: float = 0.25,
    storage_soc: float = 0.50,
    ambient_temp_c: float = 25.0,
    pack_capacity_kwh: float = 77.4,
    vehicle_efficiency_km_per_kwh: float = 5.2,
) -> Dict[str, Any]:
    chem_key = normalize_chemistry(chemistry)
    chem = RAW_DATABASE["chemistries"].get(chem_key, RAW_DATABASE["chemistries"]["NCM_811"])
    total_km = total_km if total_km is not None else years * annual_km

    R_GAS = 8.314462
    T_REF_K = 298.15
    SOC_REF = 0.50
    temp_k = ambient_temp_c + 273.15

    # A. Calendar aging
    arrhenius = math.exp((-chem["calendar_arrhenius_ea_j_mol"] / R_GAS) * (1.0 / temp_k - 1.0 / T_REF_K))
    soc_factor = math.exp(chem["soc_stress_coefficient_beta"] * (storage_soc - SOC_REF))
    k_cal = (chem["calendar_baseline_annual_loss_pct"] / 100.0) * arrhenius * soc_factor
    q_loss_cal = k_cal * math.pow(max(0.1, years), chem["calendar_time_exponent_z"])

    # B. Cyclic aging
    energy_kwh = total_km / max(1.0, vehicle_efficiency_km_per_kwh)
    eq_cycles = energy_kwh / max(10.0, pack_capacity_kwh)

    f_dod = math.pow(0.85, chem["dod_exponent_u"])
    f_dcfc = 1.0 + (chem["dcfc_acceleration_multiplier_max"] - 1.0) * clamp(dcfc_ratio, 0.0, 1.0)

    f_temp_cyc = 1.0
    if ambient_temp_c < 0:
        cold_fraction = min(1.0, abs(ambient_temp_c) / 15.0)
        f_temp_cyc = 1.0 + chem["cold_charge_sensitivity_gamma"] * cold_fraction

    base_cycles = chem["cycle_life_to_80_soh"]
    q_loss_cyc = (
        (0.20 / math.pow(base_cycles, chem["cyclic_exponent_w"]))
        * f_dod
        * f_dcfc
        * f_temp_cyc
        * math.pow(eq_cycles, chem["cyclic_exponent_w"])
    )

    # C. Sub-additive coupling
    P_COUPLING = 1.25
    q_loss_total = math.pow(
        math.pow(q_loss_cal, P_COUPLING) + math.pow(q_loss_cyc, P_COUPLING),
        1.0 / P_COUPLING,
    )

    soh_pct = clamp(round((1.0 - q_loss_total) * 1000.0) / 10.0, 0.0, 100.0)

    # D. Grade
    if soh_pct < 70.0:
        grade = "CRITICAL"
        grade_label = "Critical (수명 만료 / 교체 대상)"
        badge_color = "red"
        failure_risk = 42.0
        winter_retention = 36
        valuation_factor = 0.30
    elif soh_pct < 80.0:
        grade = "GRADE_C"
        grade_label = "Grade C (경고 / 급속 열화 진입)"
        badge_color = "amber"
        failure_risk = 12.5
        winter_retention = 48
        valuation_factor = 0.68
    elif soh_pct < 90.0:
        grade = "GRADE_B"
        grade_label = "Grade B (양호 / 정상 마모)"
        badge_color = "blue"
        failure_risk = 2.1
        winter_retention = 62
        valuation_factor = 0.92
    else:
        grade = "GRADE_A"
        grade_label = "Grade A (최상급 / Pristine)"
        badge_color = "emerald"
        failure_risk = 0.3
        winter_retention = 76
        valuation_factor = 1.00

    # E. Replacement Cost Tier
    if pack_capacity_kwh <= 65.0:
        target_tier = RAW_DATABASE["battery_replacement_costs"][0]
    elif pack_capacity_kwh >= 89.0:
        target_tier = RAW_DATABASE["battery_replacement_costs"][2]
    else:
        target_tier = RAW_DATABASE["battery_replacement_costs"][1]

    return {
        "chemistry": chem_key,
        "years": years,
        "total_km": total_km,
        "equivalent_full_cycles": round(eq_cycles),
        "calendar_loss_pct": round(q_loss_cal * 1000.0) / 10.0,
        "cyclic_loss_pct": round(q_loss_cyc * 1000.0) / 10.0,
        "total_loss_pct": round(q_loss_total * 1000.0) / 10.0,
        "soh_pct": soh_pct,
        "grade": grade,
        "grade_label": grade_label,
        "badge_color": badge_color,
        "failure_risk_pct": failure_risk,
        "winter_range_retention_pct": winter_retention,
        "used_market_valuation_factor": valuation_factor,
        "replacement_cost_tier": target_tier["tier_id"],
        "replacement_new_pack_krw": target_tier["costs"]["new_pack_krw"],
        "replacement_total_new_installed_krw": target_tier["costs"]["total_new_installed_krw"],
    }


def calculate_subsidy_clawback(
    held_months: float,
    local_subsidy_krw: float,
    transfer_type: str,
    national_subsidy_krw: float = 0.0,
) -> Dict[str, Any]:
    norm_months = max(0.0, held_months)
    tiers = RAW_DATABASE["subsidy_clawback_schedule"]["tiers"]
    matched_tier = tiers[-1]  # default >= 24m
    for t in tiers:
        if t["max_months_exclusive"] is None:
            if norm_months >= t["min_months"]:
                matched_tier = t
                break
        else:
            if t["min_months"] <= norm_months < t["max_months_exclusive"]:
                matched_tier = t
                break

    statutory_rate = matched_tier["clawback_rate"]

    if norm_months >= 24.0:
        is_exempt = True
        effective_rate = 0.0
        local_clawback = 0
        national_clawback = 0
    elif transfer_type == "intra":
        is_exempt = True
        effective_rate = 0.0
        local_clawback = 0
        national_clawback = 0
    elif transfer_type == "inter":
        is_exempt = (statutory_rate == 0.0)
        effective_rate = statutory_rate
        local_clawback = round(local_subsidy_krw * effective_rate)
        national_clawback = 0
    elif transfer_type == "export":
        is_exempt = False
        effective_rate = statutory_rate
        local_clawback = round(local_subsidy_krw * effective_rate)
        national_clawback = round(national_subsidy_krw * effective_rate)
    else:
        raise ValueError(f"Unknown transfer_type: {transfer_type}")

    total_clawback = local_clawback + national_clawback
    remaining_months = max(0.0, 24.0 - norm_months)

    return {
        "held_months": norm_months,
        "tier_label": matched_tier["label_ko"],
        "statutory_clawback_rate": statutory_rate,
        "effective_clawback_rate": effective_rate,
        "local_subsidy_received_krw": local_subsidy_krw,
        "national_subsidy_received_krw": national_subsidy_krw,
        "local_clawback_krw": local_clawback,
        "national_clawback_krw": national_clawback,
        "total_clawback_krw": total_clawback,
        "transfer_type": transfer_type,
        "is_exempt": is_exempt,
        "remaining_months_of_obligation": round(remaining_months * 10.0) / 10.0,
    }


def calculate_tco_comparison(
    annual_km: float,
    years: int,
    ev_efficiency_km_per_kwh: float = 5.2,
    slow_charging_ratio: float = 0.70,
    ice_displacement_cc: int = 1998,
) -> Dict[str, Any]:
    params = RAW_DATABASE["tco_parameters"]
    clamped_slow = clamp(slow_charging_ratio, 0.0, 1.0)
    fast_ratio = 1.0 - clamped_slow

    blended_tariff = (
        clamped_slow * params["fuel_tariffs"]["ev_slow_charging_krw_per_kwh"]
        + fast_ratio * params["fuel_tariffs"]["ev_fast_charging_krw_per_kwh"]
    )
    ev_cost_per_km = blended_tariff / max(1.0, ev_efficiency_km_per_kwh)
    ice_economy = params["efficiency_baselines"]["ice_gasoline_economy_km_per_liter"]
    ice_cost_per_km = params["fuel_tariffs"]["ice_gasoline_krw_per_liter"] / max(1.0, ice_economy)

    def calculate_ice_annual_tax(year_idx: int) -> int:
        rate = 200
        if ice_displacement_cc <= 1000:
            rate = 80
        elif ice_displacement_cc <= 1600:
            rate = 140
        base_tax = ice_displacement_cc * rate * (1.0 + params["tax_parameters"]["education_tax_multiplier"])
        discount = 0.0
        if year_idx >= params["tax_parameters"]["ice_age_discount_start_year"]:
            discount = min(
                params["tax_parameters"]["ice_age_discount_max"],
                (year_idx - (params["tax_parameters"]["ice_age_discount_start_year"] - 1))
                * params["tax_parameters"]["ice_age_discount_rate_per_year"],
            )
        return round(base_tax * (1.0 - discount))

    ev_annual_tax = params["tax_parameters"]["ev_annual_tax_krw"]
    toll_annual = params["auxiliary_benefits"]["annual_toll_savings_krw"]
    parking_annual = params["auxiliary_benefits"]["annual_parking_savings_krw"]
    maint_annual = params["auxiliary_benefits"]["maintenance_annual_savings_krw"]

    yearly_breakdown = []
    cum_savings = 0
    ev_total_fuel = 0
    ice_total_fuel = 0
    ev_total_tax = 0
    ice_total_tax = 0

    for y in range(1, years + 1):
        ev_fuel = round(annual_km * ev_cost_per_km)
        ice_fuel = round(annual_km * ice_cost_per_km)
        ice_tax = calculate_ice_annual_tax(y)
        ann_savings = (ice_fuel - ev_fuel) + (ice_tax - ev_annual_tax) + toll_annual + parking_annual + maint_annual
        cum_savings += ann_savings

        ev_total_fuel += ev_fuel
        ice_total_fuel += ice_fuel
        ev_total_tax += ev_annual_tax
        ice_total_tax += ice_tax

        yearly_breakdown.append({
            "year": y,
            "cumulative_km": y * annual_km,
            "ev_electricity_cost_krw": ev_fuel,
            "ice_fuel_cost_krw": ice_fuel,
            "ev_automobile_tax_krw": ev_annual_tax,
            "ice_automobile_tax_krw": ice_tax,
            "toll_savings_krw": toll_annual,
            "parking_savings_krw": parking_annual,
            "maintenance_savings_krw": maint_annual,
            "annual_net_savings_krw": ann_savings,
            "cumulative_net_savings_krw": cum_savings,
        })

    return {
        "annual_km": annual_km,
        "years": years,
        "total_km": annual_km * years,
        "blended_electricity_tariff_krw_per_kwh": round(blended_tariff * 100.0) / 100.0,
        "ev_fuel_cost_per_km": round(ev_cost_per_km * 100.0) / 100.0,
        "ice_fuel_cost_per_km": round(ice_cost_per_km * 100.0) / 100.0,
        "ev_total_fuel_cost_krw": ev_total_fuel,
        "ice_total_fuel_cost_krw": ice_total_fuel,
        "fuel_savings_krw": ice_total_fuel - ev_total_fuel,
        "ev_total_tax_krw": ev_total_tax,
        "ice_total_tax_krw": ice_total_tax,
        "tax_savings_krw": ice_total_tax - ev_total_tax,
        "total_auxiliary_savings_krw": (toll_annual + parking_annual + maint_annual) * years,
        "total_cumulative_savings_krw": cum_savings,
        "yearly_breakdown": yearly_breakdown,
    }


# ==============================================================================
# Suite 1: Data Schema Completeness
# ==============================================================================

class TestDataSchemaCompleteness(unittest.TestCase):
    """Verifies complete schema structure across 15 models, 8 brands, chemistries, and tiers."""

    def test_01_metadata_structure_and_constants(self):
        meta = RAW_DATABASE.get("metadata", {})
        self.assertEqual(meta.get("version"), "1.0.0")
        self.assertEqual(meta.get("total_models"), 15)
        self.assertEqual(meta.get("brands_count"), 8)
        self.assertEqual(meta.get("currency"), "KRW")
        self.assertEqual(meta.get("baseline_annual_mileage_km"), 15000)
        self.assertGreaterEqual(len(meta.get("sources", [])), 5)
        self.assertTrue(any("Encar" in s for s in meta.get("sources", [])))
        self.assertTrue(any("K Car" in s for s in meta.get("sources", [])))
        self.assertTrue(any("MOLIT" in s or "국토교통부" in s for s in meta.get("sources", [])))

    def test_02_fifteen_models_across_eight_brands(self):
        models = RAW_DATABASE.get("models", [])
        self.assertEqual(len(models), 15, "Database must contain exactly 15 EV models")

        unique_brands = {m["brand_id"] for m in models}
        expected_brands = {"tesla", "hyundai", "kia", "genesis", "byd", "mercedes-benz", "bmw", "polestar"}
        self.assertEqual(unique_brands, expected_brands, f"Expected 8 specific brands, got: {unique_brands}")

        unique_ids = {m["id"] for m in models}
        self.assertEqual(len(unique_ids), 15, "Every model must possess a unique ID")

        # Specific representative models required by domain
        expected_models = [
            "model-3", "model-y", "ioniq5", "ioniq6", "ev6", "ev9",
            "gv60", "electrified-g80", "atto-3", "seal", "eqe", "eqs",
            "i4", "ix3", "polestar-2"
        ]
        for m_id in expected_models:
            self.assertIn(m_id, unique_ids, f"Model ID '{m_id}' must be present in database")

    def test_03_model_price_and_financial_fields(self):
        for model in RAW_DATABASE["models"]:
            msrp = model.get("msrp_krw_baseline")
            subsidy = model.get("avg_subsidy_krw")
            net_price = model.get("net_purchase_price_krw")

            self.assertIsInstance(msrp, int)
            self.assertGreater(msrp, 20_000_000, f"MSRP for {model['id']} must be > 20M KRW")
            self.assertIsInstance(subsidy, int)
            self.assertGreaterEqual(subsidy, 0)
            self.assertEqual(
                net_price,
                msrp - subsidy,
                f"Net purchase price must exactly equal MSRP - subsidy for {model['id']}",
            )

    def test_04_model_battery_specs_and_warranty_contracts(self):
        valid_architectures = {"400V", "800V", "550V/800V"}
        valid_chemistries = {"LFP", "NCM 811", "NCM 622", "NCMA", "NCA"}

        for model in RAW_DATABASE["models"]:
            b_spec = model.get("battery_specs", {})
            self.assertGreater(b_spec.get("capacity_kwh", 0), 30.0)
            self.assertIn(b_spec.get("voltage_architecture"), valid_architectures)
            self.assertTrue(
                any(c in b_spec.get("chemistry", "") for c in ["LFP", "NCM", "NCMA", "NCA"]),
                f"Invalid chemistry for {model['id']}: {b_spec.get('chemistry')}",
            )
            self.assertTrue(bool(b_spec.get("cell_supplier")))

            warranty = model.get("warranty", {})
            self.assertGreaterEqual(warranty.get("years", 0), 8)
            self.assertGreaterEqual(warranty.get("km", 0), 120_000)
            self.assertGreaterEqual(warranty.get("guarantee_retention_pct", 0), 65)

    def test_05_battery_chemistry_profiles_completeness(self):
        chem_dict = RAW_DATABASE.get("chemistries", {})
        expected_chem_keys = ["LFP", "NCM_622", "NCM_811", "NCMA", "NCA"]
        for key in expected_chem_keys:
            self.assertIn(key, chem_dict, f"Missing battery chemistry: {key}")
            profile = chem_dict[key]
            self.assertGreater(profile["nominal_cell_voltage_v"], 3.0)
            self.assertGreater(profile["voltage_cutoff_v"], 2.0)
            self.assertGreater(profile["energy_density_wh_kg"], 100)
            self.assertGreater(profile["cycle_life_to_80_soh"], 500)
            self.assertGreater(profile["calendar_arrhenius_ea_j_mol"], 20000.0)
            self.assertGreater(profile["soc_stress_coefficient_beta"], 0.0)
            self.assertGreater(profile["dcfc_acceleration_multiplier_max"], 1.0)
            self.assertGreaterEqual(profile["thermal_runaway_temp_c"], 200)

    def test_06_battery_replacement_cost_tiers_integrity(self):
        tiers = RAW_DATABASE.get("battery_replacement_costs", [])
        self.assertEqual(len(tiers), 3, "Must define 3 battery replacement capacity tiers")

        tier_ids = [t["tier_id"] for t in tiers]
        self.assertEqual(tier_ids, ["TIER_50KWH", "TIER_77KWH", "TIER_100KWH"])

        # Nominal capacities strictly increasing
        capacities = [t["pack_size_kwh_nominal"] for t in tiers]
        self.assertTrue(capacities[0] < capacities[1] < capacities[2])

        for tier in tiers:
            costs = tier["costs"]
            new_pack = costs["new_pack_krw"]
            labor = costs["labor_coolant_krw"]
            total_new = costs["total_new_installed_krw"]
            self.assertEqual(total_new, new_pack + labor, f"Tier {tier['tier_id']} total installed cost mismatch")
            if costs["reman_pack_krw"] is not None:
                self.assertEqual(costs["total_reman_installed_krw"], costs["reman_pack_krw"] + labor)
            self.assertGreater(costs["cost_per_kwh_usd"], 180)
            self.assertLess(costs["cost_per_kwh_usd"], 350)

    def test_07_market_context_and_adjustment_factors_schema(self):
        ctx = RAW_DATABASE.get("market_context", {})
        self.assertIn("cheongna_fire_impact_summary", ctx)
        self.assertIn("subsidy_clawback_rules", ctx)

        adj = RAW_DATABASE.get("adjustment_factors", {})
        self.assertIn("warranty_cliff", adj)
        self.assertIn("battery_chemistry", adj)
        self.assertIn("facelift_hardware", adj)
        self.assertIn("software_ota", adj)
        self.assertIn("mileage_sensitivity", adj)


# ==============================================================================
# Suite 2: Strict Monotonic Decrease of Residual Percentages
# ==============================================================================

class TestDepreciationCurveMonotonicity(unittest.TestCase):
    """Verifies strict monotonic decrease of residual percentages and prices over 1 to 5 years."""

    def test_01_strict_monotonic_residual_percentage_msrp_all_15_models(self):
        for model in RAW_DATABASE["models"]:
            curve = model["depreciation_curve"]
            y1 = curve["year_1"]["residual_pct_msrp"]
            y2 = curve["year_2"]["residual_pct_msrp"]
            y3 = curve["year_3"]["residual_pct_msrp"]
            y4 = curve["year_4"]["residual_pct_msrp"]
            y5 = curve["year_5"]["residual_pct_msrp"]

            self.assertGreater(100.0, y1, f"{model['id']}: Year 1 residual must be < 100%")
            self.assertGreater(y1, y2, f"{model['id']}: Year 1 ({y1}) must be > Year 2 ({y2})")
            self.assertGreater(y2, y3, f"{model['id']}: Year 2 ({y2}) must be > Year 3 ({y3})")
            self.assertGreater(y3, y4, f"{model['id']}: Year 3 ({y3}) must be > Year 4 ({y4})")
            self.assertGreater(y4, y5, f"{model['id']}: Year 4 ({y4}) must be > Year 5 ({y5})")
            self.assertGreater(y5, 0.0, f"{model['id']}: Year 5 residual must be > 0%")

    def test_02_strict_monotonic_residual_percentage_effective_all_15_models(self):
        for model in RAW_DATABASE["models"]:
            curve = model["depreciation_curve"]
            y1 = curve["year_1"]["residual_pct_effective"]
            y2 = curve["year_2"]["residual_pct_effective"]
            y3 = curve["year_3"]["residual_pct_effective"]
            y4 = curve["year_4"]["residual_pct_effective"]
            y5 = curve["year_5"]["residual_pct_effective"]

            self.assertGreater(100.0, y1, f"{model['id']}: Effective Year 1 must be < 100%")
            self.assertGreater(y1, y2, f"{model['id']}: Effective Y1 ({y1}) must be > Y2 ({y2})")
            self.assertGreater(y2, y3, f"{model['id']}: Effective Y2 ({y2}) must be > Y3 ({y3})")
            self.assertGreater(y3, y4, f"{model['id']}: Effective Y3 ({y3}) must be > Y4 ({y4})")
            self.assertGreater(y4, y5, f"{model['id']}: Effective Y4 ({y4}) must be > Y5 ({y5})")
            self.assertGreater(y5, 0.0, f"{model['id']}: Effective Year 5 must be > 0%")

    def test_03_strict_monotonic_depreciation_percentage_all_15_models(self):
        for model in RAW_DATABASE["models"]:
            curve = model["depreciation_curve"]
            d1 = curve["year_1"]["depreciation_pct_msrp"]
            d2 = curve["year_2"]["depreciation_pct_msrp"]
            d3 = curve["year_3"]["depreciation_pct_msrp"]
            d4 = curve["year_4"]["depreciation_pct_msrp"]
            d5 = curve["year_5"]["depreciation_pct_msrp"]

            self.assertLess(0.0, d1)
            self.assertLess(d1, d2)
            self.assertLess(d2, d3)
            self.assertLess(d3, d4)
            self.assertLess(d4, d5)
            self.assertLess(d5, 100.0)

            # Check complement identity: residual + depreciation == 100.0
            for yr_idx in [1, 2, 3, 4, 5]:
                pt = curve[f"year_{yr_idx}"]
                total = pt["residual_pct_msrp"] + pt["depreciation_pct_msrp"]
                self.assertAlmostEqual(total, 100.0, delta=0.1, msg=f"{model['id']} Year {yr_idx} sum != 100")

    def test_04_strict_monotonic_used_market_price_all_15_models(self):
        for model in RAW_DATABASE["models"]:
            msrp = model["msrp_krw_baseline"]
            curve = model["depreciation_curve"]
            p1 = curve["year_1"]["avg_used_price_krw"]
            p2 = curve["year_2"]["avg_used_price_krw"]
            p3 = curve["year_3"]["avg_used_price_krw"]
            p4 = curve["year_4"]["avg_used_price_krw"]
            p5 = curve["year_5"]["avg_used_price_krw"]

            self.assertGreater(msrp, p1, f"{model['id']}: MSRP must be > Year 1 price")
            self.assertGreater(p1, p2, f"{model['id']}: Year 1 price must be > Year 2 price")
            self.assertGreater(p2, p3, f"{model['id']}: Year 2 price must be > Year 3 price")
            self.assertGreater(p3, p4, f"{model['id']}: Year 3 price must be > Year 4 price")
            self.assertGreater(p4, p5, f"{model['id']}: Year 4 price must be > Year 5 price")
            self.assertGreater(p5, 0, f"{model['id']}: Year 5 price must be > 0")

            # Check exact price computation: round(msrp * residual / 100)
            for yr_idx in [1, 2, 3, 4, 5]:
                pt = curve[f"year_{yr_idx}"]
                expected_price = round((msrp * pt["residual_pct_msrp"]) / 100.0)
                self.assertEqual(
                    pt["avg_used_price_krw"],
                    expected_price,
                    f"{model['id']} Year {yr_idx} price does not match residual formula",
                )

    def test_05_annual_drop_pct_consistency(self):
        for model in RAW_DATABASE["models"]:
            curve = model["depreciation_curve"]
            prev_residual = 100.0
            for yr_idx in [1, 2, 3, 4, 5]:
                pt = curve[f"year_{yr_idx}"]
                computed_drop = round((prev_residual - pt["residual_pct_msrp"]) * 10.0) / 10.0
                self.assertAlmostEqual(
                    pt["annual_drop_pct"],
                    computed_drop,
                    delta=0.2,
                    msg=f"{model['id']} Year {yr_idx} annual drop discrepancy",
                )
                prev_residual = pt["residual_pct_msrp"]

    def test_06_defense_tier_ranking_hierarchy(self):
        tier_scores = {"S": 10, "A": 9, "A-": 8, "B+": 7, "B": 6, "B-": 5, "C+": 4, "C": 3, "D": 1}
        models_by_id = {m["id"]: m for m in RAW_DATABASE["models"]}

        # S-tier (Tesla Model 3 / Model Y) vs D-tier (Mercedes EQE / EQS)
        s_tier_model = models_by_id["model-3"]
        d_tier_model = models_by_id["eqe"]

        self.assertEqual(s_tier_model["resale_defense_tier"], "S")
        self.assertEqual(d_tier_model["resale_defense_tier"], "D")

        # Year 3 residual % comparison
        s_y3 = s_tier_model["depreciation_curve"]["year_3"]["residual_pct_msrp"]
        d_y3 = d_tier_model["depreciation_curve"]["year_3"]["residual_pct_msrp"]
        self.assertGreater(s_y3, d_y3 + 20.0, "S-tier model must beat D-tier model by over 20% residual points at Year 3")

    def test_07_continuous_interpolation_and_extrapolation_monotonicity(self):
        # Test arbitrary continuous points for all 15 models
        test_points = [0.0, 0.5, 1.0, 1.5, 2.0, 2.7, 3.0, 3.9, 4.0, 4.5, 5.0, 6.0, 7.5, 10.0]
        for model in RAW_DATABASE["models"]:
            curve = model["depreciation_curve"]
            residuals = [interpolate_baseline_residual(curve, t) for t in test_points]
            for i in range(len(residuals) - 1):
                self.assertGreater(
                    residuals[i],
                    residuals[i + 1],
                    f"{model['id']}: Interpolated residual at t={test_points[i]} ({residuals[i]}) must exceed t={test_points[i+1]} ({residuals[i+1]})",
                )


# ==============================================================================
# Suite 3: Battery Health Degradation Simulation Boundary Values
# ==============================================================================

class TestBatteryHealthSimulationBoundaries(unittest.TestCase):
    """Verifies electrochemical battery simulation boundary conditions (0 km, 500k km, 0% DCFC, 100% DCFC)."""

    def test_01_zero_mileage_boundary_pure_calendar_aging(self):
        # 0 km driven: cyclic loss must be exactly 0, equivalent full cycles = 0
        res = simulate_battery_health(years=1.0, total_km=0.0, chemistry="NCM_811")
        self.assertEqual(res["equivalent_full_cycles"], 0)
        self.assertEqual(res["cyclic_loss_pct"], 0.0)
        self.assertGreater(res["calendar_loss_pct"], 0.0)
        self.assertEqual(res["total_loss_pct"], res["calendar_loss_pct"])
        self.assertGreaterEqual(res["soh_pct"], 98.0)
        self.assertEqual(res["grade"], "GRADE_A")
        self.assertEqual(res["used_market_valuation_factor"], 1.0)

        # Micro-age (0.1 year, 0 km)
        res_micro = simulate_battery_health(years=0.1, total_km=0.0, chemistry="LFP")
        self.assertEqual(res_micro["cyclic_loss_pct"], 0.0)
        self.assertGreaterEqual(res_micro["soh_pct"], 99.0)

    def test_02_extreme_high_mileage_boundary_500k_km(self):
        # 500,000 km extreme distance driven over 10 years
        res_lfp = simulate_battery_health(years=10.0, total_km=500_000.0, chemistry="LFP", dcfc_ratio=0.50)
        res_ncm = simulate_battery_health(years=10.0, total_km=500_000.0, chemistry="NCM_811", dcfc_ratio=0.50)
        res_nca = simulate_battery_health(years=10.0, total_km=500_000.0, chemistry="NCA", dcfc_ratio=0.50)

        for res in [res_lfp, res_ncm, res_nca]:
            self.assertGreater(res["equivalent_full_cycles"], 1000)
            self.assertGreater(res["cyclic_loss_pct"], 8.0)
            self.assertGreater(res["total_loss_pct"], 12.0)

            # Numerical safety bounds
            self.assertGreaterEqual(res["soh_pct"], 0.0)
            self.assertLessEqual(res["soh_pct"], 100.0)
            self.assertFalse(math.isnan(res["soh_pct"]))
            self.assertFalse(math.isinf(res["soh_pct"]))

        # Ternary high-nickel chemistry (NCM 811 & NCA) severe cyclic fatigue
        self.assertGreater(res_ncm["cyclic_loss_pct"], 20.0)
        self.assertGreater(res_nca["cyclic_loss_pct"], 20.0)
        self.assertEqual(res_ncm["grade"], "GRADE_C")
        self.assertEqual(res_nca["grade"], "GRADE_C")
        self.assertGreater(res_ncm["failure_risk_pct"], 10.0)
        self.assertLess(res_ncm["used_market_valuation_factor"], 0.75)

        # LFP exceptional cycle life comparison: LFP cyclic loss < ternary cyclic loss
        self.assertLess(res_lfp["cyclic_loss_pct"], res_ncm["cyclic_loss_pct"])
        self.assertGreater(res_lfp["soh_pct"], res_ncm["soh_pct"])

    def test_03_zero_percent_vs_100_percent_dcfc_strain(self):
        # Hold all variables constant except DCFC ratio (0% vs 100%)
        slow_sim = simulate_battery_health(years=5.0, total_km=75_000.0, chemistry="NCM_811", dcfc_ratio=0.0)
        fast_sim = simulate_battery_health(years=5.0, total_km=75_000.0, chemistry="NCM_811", dcfc_ratio=1.0)

        # Calendar loss must be identical (calendar loss does not depend on charging speed)
        self.assertEqual(slow_sim["calendar_loss_pct"], fast_sim["calendar_loss_pct"])

        # Cyclic loss must be strictly greater under 100% fast charging
        self.assertGreater(
            fast_sim["cyclic_loss_pct"],
            slow_sim["cyclic_loss_pct"],
            "100% DCFC must produce strictly higher cyclic degradation than 0% DCFC",
        )

        # Total SoH must be lower under 100% DCFC
        self.assertLess(fast_sim["soh_pct"], slow_sim["soh_pct"])

        # Check acceleration factor ratio
        chem_profile = RAW_DATABASE["chemistries"]["NCM_811"]
        expected_multiplier = chem_profile["dcfc_acceleration_multiplier_max"]
        ratio = fast_sim["cyclic_loss_pct"] / max(0.01, slow_sim["cyclic_loss_pct"])
        self.assertAlmostEqual(ratio, expected_multiplier, delta=0.05)

    def test_04_dcfc_strain_monotonicity_across_charging_mix(self):
        dcfc_steps = [0.0, 0.25, 0.50, 0.75, 1.0]
        results = [
            simulate_battery_health(years=4.0, total_km=60_000.0, chemistry="NCMA", dcfc_ratio=r)
            for r in dcfc_steps
        ]
        for i in range(len(results) - 1):
            self.assertLessEqual(
                results[i]["cyclic_loss_pct"],
                results[i + 1]["cyclic_loss_pct"],
                f"Cyclic loss must increase monotonically with DCFC ratio",
            )
            self.assertGreaterEqual(
                results[i]["soh_pct"],
                results[i + 1]["soh_pct"],
                f"SoH must decrease monotonically with DCFC ratio",
            )

    def test_05_ambient_temperature_extremes_subzero_vs_scorching(self):
        # Cold temperature charging strain (-15°C vs 25°C)
        cold_res = simulate_battery_health(years=3.0, total_km=45_000.0, chemistry="LFP", ambient_temp_c=-15.0)
        room_res = simulate_battery_health(years=3.0, total_km=45_000.0, chemistry="LFP", ambient_temp_c=25.0)
        self.assertGreater(cold_res["cyclic_loss_pct"], room_res["cyclic_loss_pct"])

        # High temperature Arrhenius calendar degradation (+45°C vs 25°C)
        hot_res = simulate_battery_health(years=3.0, total_km=45_000.0, chemistry="NCM_811", ambient_temp_c=45.0)
        self.assertGreater(
            hot_res["calendar_loss_pct"],
            room_res["calendar_loss_pct"],
            "Scorching ambient temperature must accelerate Arrhenius calendar aging",
        )

    def test_06_storage_soc_stress_exponential_kinetics(self):
        soc_levels = [0.20, 0.50, 0.80, 1.00]
        results = [
            simulate_battery_health(years=3.0, total_km=30_000.0, chemistry="NCM_811", storage_soc=soc)
            for soc in soc_levels
        ]
        for i in range(len(results) - 1):
            self.assertLess(
                results[i]["calendar_loss_pct"],
                results[i + 1]["calendar_loss_pct"],
                "Calendar aging must increase monotonically with parking storage SoC",
            )

    def test_07_chemistry_resilience_comparison_lfp_vs_nca(self):
        # 1500 equivalent cycles comparison
        lfp_res = simulate_battery_health(years=5.0, total_km=150_000.0, chemistry="LFP", pack_capacity_kwh=60.0)
        nca_res = simulate_battery_health(years=5.0, total_km=150_000.0, chemistry="NCA", pack_capacity_kwh=60.0)

        # LFP cycle life (3000) >> NCA cycle life (1100)
        self.assertLess(
            lfp_res["cyclic_loss_pct"],
            nca_res["cyclic_loss_pct"],
            "LFP must exhibit substantially lower cyclic loss than NCA at high mileage",
        )

    def test_08_replacement_cost_tier_capacity_mapping(self):
        # Small pack (<= 65 kWh) -> TIER_50KWH
        res_small = simulate_battery_health(years=2.0, pack_capacity_kwh=58.0)
        self.assertEqual(res_small["replacement_cost_tier"], "TIER_50KWH")
        self.assertEqual(res_small["replacement_new_pack_krw"], 16_000_000)

        # Midsize pack (65-89 kWh) -> TIER_77KWH
        res_mid = simulate_battery_health(years=2.0, pack_capacity_kwh=77.4)
        self.assertEqual(res_mid["replacement_cost_tier"], "TIER_77KWH")
        self.assertEqual(res_mid["replacement_new_pack_krw"], 24_000_000)

        # Large pack (>= 89 kWh) -> TIER_100KWH
        res_large = simulate_battery_health(years=2.0, pack_capacity_kwh=99.8)
        self.assertEqual(res_large["replacement_cost_tier"], "TIER_100KWH")
        self.assertEqual(res_large["replacement_new_pack_krw"], 32_000_000)


# ==============================================================================
# Suite 4: Statutory Korean 2-Year Subsidy Clawback Schedule
# ==============================================================================

class TestSubsidyClawbackSchedule(unittest.TestCase):
    """Verifies statutory 2-year subsidy clawback schedule, tiers, waivers, and the 24-month cliff."""

    def test_01_all_eight_statutory_tiers_rates_validation(self):
        schedule = RAW_DATABASE.get("subsidy_clawback_schedule", {})
        self.assertEqual(schedule.get("mandatory_operation_months"), 24)
        self.assertTrue("대기환경보전법" in schedule.get("legal_basis", ""))

        tiers = schedule.get("tiers", [])
        self.assertGreaterEqual(len(tiers), 8)

        expected_rates = [
            (0, 3, 0.70),
            (3, 6, 0.65),
            (6, 9, 0.60),
            (9, 12, 0.55),
            (12, 15, 0.50),
            (15, 18, 0.40),
            (18, 21, 0.30),
            (21, 24, 0.20),
        ]
        for idx, (min_m, max_m, rate) in enumerate(expected_rates):
            t = tiers[idx]
            self.assertEqual(t["min_months"], min_m)
            self.assertEqual(t["max_months_exclusive"], max_m)
            self.assertEqual(t["clawback_rate"], rate)

        # Final cliff tier (>= 24 months)
        cliff_tier = tiers[-1]
        self.assertEqual(cliff_tier["min_months"], 24)
        self.assertIsNone(cliff_tier["max_months_exclusive"])
        self.assertEqual(cliff_tier["clawback_rate"], 0.00)

    def test_02_exact_tier_boundary_transitions(self):
        # Precise boundary checks for rate transitions
        boundaries = [
            (0.0, 0.70),
            (2.99, 0.70),
            (3.00, 0.65),
            (5.99, 0.65),
            (6.00, 0.60),
            (8.99, 0.60),
            (9.00, 0.55),
            (11.99, 0.55),
            (12.00, 0.50),
            (14.99, 0.50),
            (15.00, 0.40),
            (17.99, 0.40),
            (18.00, 0.30),
            (20.99, 0.30),
            (21.00, 0.20),
            (23.99, 0.20),
            (24.00, 0.00),
            (30.00, 0.00),
        ]
        for months, expected_rate in boundaries:
            res = calculate_subsidy_clawback(
                held_months=months,
                local_subsidy_krw=4_000_000,
                transfer_type="inter",
            )
            self.assertEqual(
                res["statutory_clawback_rate"],
                expected_rate,
                f"Failed rate at boundary month={months}: expected {expected_rate}, got {res['statutory_clawback_rate']}",
            )

    def test_03_intra_province_transfer_waiver_guarantee(self):
        # Within same municipality (관내 이전): 100% waiver across all holding periods (< 24m)
        test_months = [0.5, 3.0, 7.5, 11.0, 16.0, 22.0]
        for m in test_months:
            res = calculate_subsidy_clawback(
                held_months=m,
                local_subsidy_krw=5_000_000,
                national_subsidy_krw=3_000_000,
                transfer_type="intra",
            )
            self.assertTrue(res["is_exempt"])
            self.assertEqual(res["effective_clawback_rate"], 0.0)
            self.assertEqual(res["local_clawback_krw"], 0)
            self.assertEqual(res["national_clawback_krw"], 0)
            self.assertEqual(res["total_clawback_krw"], 0)
            self.assertGreater(res["remaining_months_of_obligation"], 0.0)

    def test_04_inter_province_transfer_local_subsidy_clawback_only(self):
        # Outside municipality (관외 이전): only local subsidy is clawed back; national subsidy is exempt
        local_sub = 4_000_000
        national_sub = 3_000_000

        # At 10 months: tier 9-12m (55%)
        res = calculate_subsidy_clawback(
            held_months=10.0,
            local_subsidy_krw=local_sub,
            national_subsidy_krw=national_sub,
            transfer_type="inter",
        )
        self.assertFalse(res["is_exempt"])
        self.assertEqual(res["statutory_clawback_rate"], 0.55)
        self.assertEqual(res["effective_clawback_rate"], 0.55)
        self.assertEqual(res["local_clawback_krw"], round(local_sub * 0.55))
        self.assertEqual(res["national_clawback_krw"], 0, "National subsidy must NOT be clawed back on inter-province sale")
        self.assertEqual(res["total_clawback_krw"], 2_200_000)
        self.assertEqual(res["remaining_months_of_obligation"], 14.0)

    def test_05_export_transfer_full_national_and_local_clawback(self):
        # Export deregistration (수출 말소): both national AND local subsidies are clawed back
        local_sub = 4_000_000
        national_sub = 3_000_000

        # At 10 months (55%)
        res = calculate_subsidy_clawback(
            held_months=10.0,
            local_subsidy_krw=local_sub,
            national_subsidy_krw=national_sub,
            transfer_type="export",
        )
        self.assertFalse(res["is_exempt"])
        self.assertEqual(res["statutory_clawback_rate"], 0.55)
        self.assertEqual(res["local_clawback_krw"], 2_200_000)
        self.assertEqual(res["national_clawback_krw"], 1_650_000)
        self.assertEqual(res["total_clawback_krw"], 3_850_000)

    def test_06_twenty_four_month_cliff_universal_exemption(self):
        # 24-month statutory cliff: at >= 24 months, clawback is 0 KRW even for export!
        for t_type in ["intra", "inter", "export"]:
            res_24 = calculate_subsidy_clawback(
                held_months=24.0,
                local_subsidy_krw=5_000_000,
                national_subsidy_krw=3_000_000,
                transfer_type=t_type,
            )
            self.assertTrue(res_24["is_exempt"])
            self.assertEqual(res_24["effective_clawback_rate"], 0.0)
            self.assertEqual(res_24["total_clawback_krw"], 0)
            self.assertEqual(res_24["remaining_months_of_obligation"], 0.0)

            res_36 = calculate_subsidy_clawback(
                held_months=36.0,
                local_subsidy_krw=5_000_000,
                national_subsidy_krw=3_000_000,
                transfer_type=t_type,
            )
            self.assertTrue(res_36["is_exempt"])
            self.assertEqual(res_36["total_clawback_krw"], 0)

    def test_07_subsidy_clawback_strictly_monotonic_over_time(self):
        # Clawback amount must strictly decrease or stay equal across months
        months_series = [1, 4, 7, 10, 13, 16, 19, 22, 24, 28]
        results = [
            calculate_subsidy_clawback(m, 5_000_000, "inter")["total_clawback_krw"]
            for m in months_series
        ]
        for i in range(len(results) - 1):
            self.assertGreaterEqual(
                results[i],
                results[i + 1],
                f"Clawback amount must decrease monotonically: {results[i]} < {results[i+1]}",
            )

    def test_08_remaining_months_of_obligation_calculation(self):
        res = calculate_subsidy_clawback(15.5, 1_000_000, "inter")
        self.assertEqual(res["remaining_months_of_obligation"], 8.5)

        res_over = calculate_subsidy_clawback(28.0, 1_000_000, "inter")
        self.assertEqual(res_over["remaining_months_of_obligation"], 0.0)


# ==============================================================================
# Suite 5: Total Cost of Ownership (TCO) Economic Calculations
# ==============================================================================

class TestTcoEconomicCalculations(unittest.TestCase):
    """Verifies TCO fuel tariffs, gasoline baseline, flat 130k KRW tax, and auxiliary benefits."""

    def test_01_fuel_tariffs_slow_vs_fast_charging(self):
        tariffs = RAW_DATABASE["tco_parameters"]["fuel_tariffs"]
        slow_tariff = tariffs["ev_slow_charging_krw_per_kwh"]
        fast_tariff = tariffs["ev_fast_charging_krw_per_kwh"]

        self.assertEqual(slow_tariff, 250.0)
        self.assertEqual(fast_tariff, 347.2)
        self.assertLess(slow_tariff, fast_tariff)

        # Compare 100% slow charging vs 100% fast charging
        tco_slow = calculate_tco_comparison(annual_km=15000, years=1, slow_charging_ratio=1.0)
        tco_fast = calculate_tco_comparison(annual_km=15000, years=1, slow_charging_ratio=0.0)

        self.assertEqual(tco_slow["blended_electricity_tariff_krw_per_kwh"], 250.0)
        self.assertEqual(tco_fast["blended_electricity_tariff_krw_per_kwh"], 347.2)

        self.assertLess(
            tco_slow["ev_total_fuel_cost_krw"],
            tco_fast["ev_total_fuel_cost_krw"],
            "100% slow charging must yield lower electricity expense than 100% fast charging",
        )

        expected_diff = round((347.2 - 250.0) / 5.2 * 15000)
        actual_diff = tco_fast["ev_total_fuel_cost_krw"] - tco_slow["ev_total_fuel_cost_krw"]
        self.assertAlmostEqual(actual_diff, expected_diff, delta=2)

    def test_02_ice_fuel_cost_baseline_comparison(self):
        # Gasoline 1,700 KRW/L at 12 km/L
        tco = calculate_tco_comparison(annual_km=15000, years=1, slow_charging_ratio=0.70)
        ice_annual_fuel = tco["ice_total_fuel_cost_krw"]
        expected_ice_fuel = round(15000 * (1700.0 / 12.0))  # 2,125,000 KRW
        self.assertEqual(ice_annual_fuel, expected_ice_fuel)

        # EV at blended rate (279.16 KRW/kWh) at 5.2 km/kWh
        ev_annual_fuel = tco["ev_total_fuel_cost_krw"]
        self.assertLess(ev_annual_fuel, 850_000)

        # EV must save more than 1,200,000 KRW/year on fuel alone
        self.assertGreater(tco["fuel_savings_krw"], 1_200_000)

    def test_03_ev_annual_automobile_tax_flat_130k_invariance(self):
        tax_params = RAW_DATABASE["tco_parameters"]["tax_parameters"]
        self.assertEqual(tax_params["ev_annual_tax_krw"], 130000)
        self.assertEqual(tax_params["ev_base_tax_krw"], 100000)
        self.assertEqual(tax_params["ev_education_tax_krw"], 30000)

        # Flat invariance across all 5 years
        tco = calculate_tco_comparison(annual_km=15000, years=5)
        for yr in tco["yearly_breakdown"]:
            self.assertEqual(yr["ev_automobile_tax_krw"], 130000, f"Year {yr['year']} EV tax must be 130,000 KRW")
        self.assertEqual(tco["ev_total_tax_krw"], 130000 * 5)

    def test_04_ice_automobile_tax_tiers_and_age_discount_amortization(self):
        # 1998cc Sonata benchmark: 200 KRW/cc * 1.30 = 519,480 KRW
        tco = calculate_tco_comparison(annual_km=15000, years=5, ice_displacement_cc=1998)
        breakdown = tco["yearly_breakdown"]

        # Year 1 & Year 2: no age discount
        self.assertEqual(breakdown[0]["ice_automobile_tax_krw"], 519480)
        self.assertEqual(breakdown[1]["ice_automobile_tax_krw"], 519480)

        # Year 3: 5% discount -> 519,480 * 0.95 = 493,506
        self.assertEqual(breakdown[2]["ice_automobile_tax_krw"], 493506)

        # Year 4: 10% discount -> 519,480 * 0.90 = 467,532
        self.assertEqual(breakdown[3]["ice_automobile_tax_krw"], 467532)

        # Year 5: 15% discount -> 519,480 * 0.85 = 441,558
        self.assertEqual(breakdown[4]["ice_automobile_tax_krw"], 441558)

        # 3-year cumulative tax savings
        tco_3yr = calculate_tco_comparison(annual_km=15000, years=3, ice_displacement_cc=1998)
        self.assertEqual(tco_3yr["ev_total_tax_krw"], 390000)
        self.assertEqual(tco_3yr["ice_total_tax_krw"], 519480 + 519480 + 493506)
        self.assertEqual(tco_3yr["tax_savings_krw"], 1142466)

    def test_05_annual_auxiliary_benefits_accumulation(self):
        aux = RAW_DATABASE["tco_parameters"]["auxiliary_benefits"]
        self.assertEqual(aux["annual_toll_savings_krw"], 250000)
        self.assertEqual(aux["annual_parking_savings_krw"], 150000)
        self.assertEqual(aux["maintenance_annual_savings_krw"], 200000)

        annual_aux = 250000 + 150000 + 200000  # 600,000 KRW
        tco = calculate_tco_comparison(annual_km=15000, years=4)
        self.assertEqual(tco["total_auxiliary_savings_krw"], annual_aux * 4)

    def test_06_cumulative_tco_net_savings_strict_monotonic_growth(self):
        tco = calculate_tco_comparison(annual_km=15000, years=5)
        savings = [yr["cumulative_net_savings_krw"] for yr in tco["yearly_breakdown"]]

        for i in range(len(savings) - 1):
            self.assertGreater(
                savings[i + 1],
                savings[i],
                f"Cumulative net savings must grow strictly year-over-year: {savings[i]} -> {savings[i+1]}",
            )
            # Each year should yield at least 2,000,000 KRW net economic advantage
            annual_net = tco["yearly_breakdown"][i + 1]["annual_net_savings_krw"]
            self.assertGreater(annual_net, 2_000_000)

    def test_07_tco_breakdown_numerical_parity(self):
        tco = calculate_tco_comparison(annual_km=20000, years=3)
        expected_cum = 0
        for yr in tco["yearly_breakdown"]:
            ann = (
                (yr["ice_fuel_cost_krw"] - yr["ev_electricity_cost_krw"])
                + (yr["ice_automobile_tax_krw"] - yr["ev_automobile_tax_krw"])
                + yr["toll_savings_krw"]
                + yr["parking_savings_krw"]
                + yr["maintenance_savings_krw"]
            )
            self.assertEqual(yr["annual_net_savings_krw"], ann)
            expected_cum += ann
            self.assertEqual(yr["cumulative_net_savings_krw"], expected_cum)
        self.assertEqual(tco["total_cumulative_savings_krw"], expected_cum)


# ==============================================================================
# Suite 6: TypeScript Engine Parity (Oracle Cross-Validation)
# ==============================================================================

class TestTypeScriptEngineParity(unittest.TestCase):
    """Executes Node against getDepreciationData.ts to ensure 100% parity with Python reference model."""

    node_available: bool = False
    ts_file: Optional[Path] = None

    @classmethod
    def setUpClass(cls):
        cls.ts_file = find_ts_library_file()
        if shutil.which("node") and cls.ts_file and cls.ts_file.exists():
            # Quick probe
            try:
                proc = subprocess.run(
                    ["node", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if proc.returncode == 0:
                    cls.node_available = True
            except Exception:
                cls.node_available = False

    def _run_node_expr(self, expr: str) -> Any:
        if not self.node_available or not self.ts_file:
            self.skipTest("Node.js runtime or getDepreciationData.ts not available for oracle execution")

        ts_path_str = str(self.ts_file)
        cmd = [
            "node",
            "--experimental-strip-types",
            "-e",
            f"""
            import * as engine from '{ts_path_str}';
            const result = ({expr});
            console.log(JSON.stringify(result));
            """,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if proc.returncode != 0:
            self.fail(f"Node execution failed with code {proc.returncode}:\n{proc.stderr}")

        # Parse JSON from stdout (skip warning lines if any)
        lines = [line.strip() for line in proc.stdout.splitlines() if line.strip().startswith("{") or line.strip().startswith("[")]
        if not lines:
            self.fail(f"No JSON output from Node:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        return json.loads(lines[-1])

    def test_01_oracle_models_count_and_ids(self):
        models = self._run_node_expr("engine.getAllModels()")
        self.assertEqual(len(models), 15)
        node_ids = [m["id"] for m in models]
        py_ids = [m["id"] for m in RAW_DATABASE["models"]]
        self.assertEqual(node_ids, py_ids)

    def test_02_oracle_battery_simulation_exact_match(self):
        # Compare Node output with Python output
        node_res = self._run_node_expr("engine.simulateBatteryHealth({ years: 3, totalKm: 45000, chemistry: 'NCM_811' })")
        py_res = simulate_battery_health(years=3.0, total_km=45000.0, chemistry="NCM_811")

        self.assertEqual(node_res["equivalentFullCycles"], py_res["equivalent_full_cycles"])
        self.assertEqual(node_res["calendarLossPct"], py_res["calendar_loss_pct"])
        self.assertEqual(node_res["cyclicLossPct"], py_res["cyclic_loss_pct"])
        self.assertEqual(node_res["totalLossPct"], py_res["total_loss_pct"])
        self.assertEqual(node_res["sohPct"], py_res["soh_pct"])
        self.assertEqual(node_res["grade"], py_res["grade"])

    def test_03_oracle_subsidy_clawback_matrix_match(self):
        scenarios = [
            (2, 4_000_000, "intra", 3_000_000),
            (10, 4_000_000, "inter", 3_000_000),
            (16, 4_000_000, "export", 3_000_000),
            (25, 4_000_000, "export", 3_000_000),
        ]
        for months, local_s, t_type, nat_s in scenarios:
            node_res = self._run_node_expr(
                f"engine.calculateSubsidyClawback({months}, {local_s}, '{t_type}', {nat_s})"
            )
            py_res = calculate_subsidy_clawback(months, local_s, t_type, nat_s)

            self.assertEqual(node_res["statutoryClawbackRate"], py_res["statutory_clawback_rate"])
            self.assertEqual(node_res["effectiveClawbackRate"], py_res["effective_clawback_rate"])
            self.assertEqual(node_res["localClawbackKrw"], py_res["local_clawback_krw"])
            self.assertEqual(node_res["nationalClawbackKrw"], py_res["national_clawback_krw"])
            self.assertEqual(node_res["totalClawbackKrw"], py_res["total_clawback_krw"])
            self.assertEqual(node_res["isExempt"], py_res["is_exempt"])

    def test_04_oracle_tco_calculation_exact_match(self):
        node_res = self._run_node_expr("engine.calculateTcoComparison(15000, 3)")
        py_res = calculate_tco_comparison(15000, 3)

        self.assertEqual(node_res["totalCumulativeSavingsKrw"], py_res["total_cumulative_savings_krw"])
        self.assertEqual(node_res["fuelSavingsKrw"], py_res["fuel_savings_krw"])
        self.assertEqual(node_res["taxSavingsKrw"], py_res["tax_savings_krw"])
        self.assertEqual(node_res["totalAuxiliarySavingsKrw"], py_res["total_auxiliary_savings_krw"])

        for i in range(3):
            node_yr = node_res["yearlyBreakdown"][i]
            py_yr = py_res["yearly_breakdown"][i]
            self.assertEqual(node_yr["evElectricityCostKrw"], py_yr["ev_electricity_cost_krw"])
            self.assertEqual(node_yr["iceFuelCostKrw"], py_yr["ice_fuel_cost_krw"])
            self.assertEqual(node_yr["annualNetSavingsKrw"], py_yr["annual_net_savings_krw"])
            self.assertEqual(node_yr["cumulativeNetSavingsKrw"], py_yr["cumulative_net_savings_krw"])

    def test_05_oracle_depreciation_calculation_match(self):
        node_res = self._run_node_expr("engine.calculateDepreciation({ modelId: 'model-3', years: 3 })")
        py_res = calculate_depreciation(model_id="model-3", years=3.0)

        self.assertEqual(node_res["baselineResidualPct"], py_res["baseline_residual_pct"])
        self.assertEqual(node_res["adjustedResidualPct"], py_res["adjusted_residual_pct"])
        self.assertEqual(node_res["estimatedResidualPriceKrw"], py_res["estimated_residual_price_krw"])
        self.assertEqual(node_res["depreciationAmountKrw"], py_res["depreciation_amount_krw"])


# ==============================================================================
# Suite 7: Adversarial Stress & Resiliency Edge Cases
# ==============================================================================

class TestAdversarialDepreciationStress(unittest.TestCase):
    """Verifies robustness under extreme numerical inputs and edge conditions."""

    def test_01_extreme_negative_and_out_of_range_inputs(self):
        # Negative held months in subsidy clawback should be clamped to 0
        claw_neg = calculate_subsidy_clawback(-5.0, 4_000_000, "inter")
        self.assertEqual(claw_neg["held_months"], 0.0)
        self.assertEqual(claw_neg["statutory_clawback_rate"], 0.70)

        # Huge subsidy holding period (1000 months)
        claw_huge = calculate_subsidy_clawback(1000.0, 4_000_000, "inter")
        self.assertTrue(claw_huge["is_exempt"])
        self.assertEqual(claw_huge["total_clawback_krw"], 0)

    def test_02_synthetic_100_year_extrapolation_asymptote(self):
        for model in RAW_DATABASE["models"]:
            curve = model["depreciation_curve"]
            res_100 = interpolate_baseline_residual(curve, 100.0)
            self.assertGreaterEqual(res_100, 10.0, "Extrapolated residual must respect 10% floor")
            self.assertLess(res_100, 11.0)

    def test_03_custom_purchase_price_overrides(self):
        custom_price = 100_000_000
        res = calculate_depreciation(model_id="ioniq5", years=2.0, custom_purchase_price_krw=custom_price)
        self.assertEqual(res["base_purchase_price_krw"], custom_price)
        expected_res_price = round(custom_price * (res["adjusted_residual_pct"] / 100.0))
        self.assertEqual(res["estimated_residual_price_krw"], expected_res_price)

    def test_04_zero_and_infinite_efficiency_resilience(self):
        # Efficiency 0 or negative must be clamped safely without DivisionByZero
        res_tco = calculate_tco_comparison(annual_km=15000, years=1, ev_efficiency_km_per_kwh=0.0)
        self.assertGreater(res_tco["ev_fuel_cost_per_km"], 0.0)
        self.assertFalse(math.isinf(res_tco["ev_fuel_cost_per_km"]))


if __name__ == "__main__":
    unittest.main()
