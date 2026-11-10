"""Research-only Faraday conservation envelope; no physical, cost or profit qualification.

Source and frozen acceptance: campaign/blue-sky-120/PROTOCOL.md at
68270cc3c9e63a19993a0e1e9e1f5c5867e5a470.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

FARADAY_COULOMB_PER_MOL = Decimal("96485.33212")
OXYGEN_MOLAR_MASS_G = Decimal("31.998")
ELECTRONS_PER_MOL_O2 = Decimal(4)
SECONDS_PER_HOUR = Decimal(3600)
ONE_KILOGRAM_G = Decimal(1000)

REPORTED_G_H = Decimal("1.61")
REPORTED_ANODIC_EFFICIENCY = Decimal("0.8574")
REPORTED_OXYGEN_PURITY = Decimal("0.9166")
TARGET_G_H = Decimal("1000")
STUDIED_MIN_A_CM2 = Decimal("0.6")
STUDIED_MAX_A_CM2 = Decimal("1.0")
ILLUSTRATIVE_VOLTS = Decimal("3.0")
FREEZE = "68270cc3c9e63a19993a0e1e9e1f5c5867e5a470"

REFERENCES = [
    {"kind": "reported_laboratory_measurement", "published_online": "2026-11-03",
     "url": "https://jdse.bit.edu.cn/sktcxb/en/article/doi/10.3724/j.issn.2096-9287.2026.20250135"},
    {"kind": "strong_integrated_incumbent", "updated": "2026-07-17",
     "url": "https://techport.nasa.gov/projects/146991"},
    {"kind": "incumbent_mre_project", "updated": "2026-07-31",
     "url": "https://techport.nasa.gov/projects/116413"},
    {"kind": "incumbent_anode_alternative",
     "url": "https://ntrs.nasa.gov/citations/20250004626"},
]


def positive(value: Decimal | str | int, name: str) -> Decimal:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError) as e:
        raise ValueError(name + "_INVALID") from e
    if not d.is_finite() or d <= 0:
        raise ValueError(name + "_NOT_POSITIVE_FINITE")
    return d


def envelope(
    rate_g_h: Decimal | str | int,
    efficiency: Decimal | str | int,
    min_current_density_a_cm2: Decimal | str | int,
    max_current_density_a_cm2: Decimal | str | int,
    illustrative_voltage_v: Decimal | str | int,
) -> dict:
    rate = positive(rate_g_h, "rate")
    eta = positive(efficiency, "current_efficiency")
    if eta > 1:
        raise ValueError("current_efficiency_ABOVE_ONE")
    lo = positive(min_current_density_a_cm2, "min_density")
    hi = positive(max_current_density_a_cm2, "max_density")
    if lo > hi:
        raise ValueError("DENSITY_INTERVAL_REVERSED")
    voltage = positive(illustrative_voltage_v, "illustrative_voltage")
    with localcontext() as ctx:
        ctx.prec = 34
        current_a = rate / OXYGEN_MOLAR_MASS_G * ELECTRONS_PER_MOL_O2 * FARADAY_COULOMB_PER_MOL / SECONDS_PER_HOUR / eta
        min_area_m2 = (current_a / hi) / Decimal(10000)
        max_area_m2 = (current_a / lo) / Decimal(10000)
        electricity_kwh_per_kg = current_a * voltage / rate
    return {
        "rate_g_per_hour": str(rate),
        "assumed_anodic_efficiency_fraction": str(eta),
        "conditional_required_current_A": str(current_a),
        "conditional_area_m2_if_studied_current_densities_transfer": {
            "lower": str(min_area_m2),
            "upper": str(max_area_m2),
            "assumed_density_interval_A_per_cm2": [str(lo), str(hi)],
            "is_measurement_of_electrode_area": False,
        },
        "illustrative_electricity": {
            "voltage_V_unmeasured_scenario": str(voltage),
            "conditional_kWh_per_kg_at_same_efficiency_and_voltage": str(electricity_kwh_per_kg),
            "is_observed_process_energy_or_cost": False,
            "excludes": [
                "feed preparation", "heating and thermal management", "electrode replacement",
                "electrolyte management", "gas purification and capture",
                "power conversion", "duty cycle", "auxiliary losses",
            ],
        },
        "is_physical_throughput_demonstration": False,
    }


def record() -> dict:
    measured = envelope(REPORTED_G_H, REPORTED_ANODIC_EFFICIENCY,
                        STUDIED_MIN_A_CM2, STUDIED_MAX_A_CM2, ILLUSTRATIVE_VOLTS)
    scaled = envelope(TARGET_G_H, REPORTED_ANODIC_EFFICIENCY,
                      STUDIED_MIN_A_CM2, STUDIED_MAX_A_CM2, ILLUSTRATIVE_VOLTS)
    return {
        "schema": "agi-alpha/blue-sky120-faraday-envelope/v1",
        "frozen_protocol_commit": FREEZE,
        "historical_or_already_known_work_repeated_as_fresh": False,
        "sources": REFERENCES,
        "source_values_are_reported_not_independently_measured": True,
        "reported_oxygen_purity_fraction": str(REPORTED_OXYGEN_PURITY),
        "purity_acceptance_qualified": False,
        "report_rate": measured,
        "target_1kg_per_hour_condition": scaled,
        "proportional_current_factor_not_throughput_proof": str(TARGET_G_H / REPORTED_G_H),
        "alternatives": [
            {"id": "fe_ni_oxygen_only", "complete_cost_USD": None, "actual_buyer_acceptance": None},
            {"id": "integrated_blue_alchemist", "complete_cost_USD": None, "actual_buyer_acceptance": None},
            {"id": "earth_delivered_oxygen", "complete_cost_USD": None, "actual_buyer_acceptance": None},
            {"id": "no_build_no_purchase", "incremental_commitment_USD": "0",
             "buyer_acceptance_for_new_service": False},
        ],
        "measured_lunar_demand_units": None,
        "measured_equipment_lifetime_hours": None,
        "measured_bus_voltage_V": None,
        "collected_revenue_USD": "0",
        "qualified_native_profit_trailing_365_USD": None,
        "same_account_native_financing_executed": False,
        "technological_superiority_over_incumbent": None,
        "actual_commerce": False,
        "recursive_discovery_advantage": None,
        "decision": "HOLD_NO_BID_NO_DEPLOY",
        "first_unmet_gate": "measured complete system physical transfer, customer acceptance, complete cost and source-bound financing",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new JSON receipt path")
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Refusing to overwrite existing receipt")
    obj = record()
    protocol = Path(__file__).resolve().parents[1] / "campaign" / "blue-sky-120" / "PROTOCOL.md"
    if not protocol.is_file():
        raise FileNotFoundError("FROZEN_PROTOCOL_MISSING")
    obj["protocol_sha256"] = hashlib.sha256(protocol.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("HOLD_NO_BID_NO_DEPLOY receipt_sha256=" +
          hashlib.sha256(args.output.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
