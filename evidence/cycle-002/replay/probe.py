"""Bounded, fixed-code battery opportunity probe. No generated code or financial transaction."""
import argparse
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import resource
import time

EXPECTED = {'Kenya_cost.json': '432796b8595bbb2eb847dd586db931ed1b0ab04dbdd122714aecbc77064029d8', 'MINIGRID_INPUT.json': '3c57dd5235c21c559c98a56b7d963808c08abfe5dfe6e42148522fc92ca11291', 'battery_table3.json': '04dbce5a0ed66e222257421d4022c9f66afa4e6ac20a5801c3101bf25c7bf272', 'FULL_COST_COVERAGE.json': 'c2943d9ffc49c3734c4dd26eb9ea2f96d85b7a2afa0e9e31e2c3ca798dd3eb66'}


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate input key")
        result[key] = value
    return result


def read(source, name):
    path = source / name
    raw = path.read_bytes()
    if len(raw) > 1_000_000 or hashlib.sha256(raw).hexdigest() != EXPECTED[name]:
        raise ValueError("Source identity mismatch: " + name)
    return json.loads(raw, object_pairs_hook=no_duplicates,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError("Non-finite JSON")))


def number(value):
    result = D(str(value))
    if not result.is_finite():
        raise ValueError("Non-finite quantity")
    return result


def amount(value):
    return str(value.quantize(D("0.000000001")))


def schedule(period, horizon, include_terminal=False):
    if type(period) is not int or type(horizon) is not int or not 0 < period <= 100 or not 0 < horizon <= 100:
        raise ValueError("Bounded positive integer horizon and period required")
    return list(range(0, horizon + int(include_terminal), period))


def write(path, value):
    with path.open("x") as out:
        json.dump(value, out, indent=2, allow_nan=False)
        out.write("\n")


def run(source, output):
    start, cpu = time.monotonic(), time.process_time()
    kenya = read(source, "Kenya_cost.json")
    mini = read(source, "MINIGRID_INPUT.json")
    measured = read(source, "battery_table3.json")
    coverage = read(source, "FULL_COST_COVERAGE.json")
    output.mkdir(parents=True, exist_ok=False)
    write(output / "STARTED.json", {"mode": "DEVELOPMENT_SOURCE_BOUND_PROBE", "input_sha256": EXPECTED})

    total = sum(number(v) for v in kenya["rows"].values())
    if total != number(kenya["reported_total"]):
        raise ValueError("BOM does not reconcile")
    testing = number(kenya["rows"]["cell_and_battery_testing"])
    floor = total - testing
    life = kenya["lifetime_scenario"]
    new_unit = number(life["new_table10_price_KES"]) / number(life["new_table10_kWh"])
    new_lifetime_unit = new_unit / number(life["new_cycles_report_range"][0])
    branches = []
    nominal = number(life["other_source_nominal_voltage_V"]) * number(life["other_source_nominal_Ah"]) / 1000
    for label, energy in [("priced_table_2_4kWh", number(life["priced_used_kWh"])), ("nominal_V_times_Ah_NOT_usable", nominal)]:
        cost = floor / (energy * number(life["used_cycles_report_range"][1]))
        branches.append({"interpretation": label, "kWh": str(energy),
                         "KES_per_nominal_lifetime_kWh": amount(cost),
                         "used_to_new_ratio": amount(cost / new_lifetime_unit),
                         "admissible_matched_comparison": False})
    write(output / "COST_CEILING.json", {
        "BOM_KES": str(total), "testing_KES": str(testing),
        "maximum_BOM_saving_percent": amount(100 * testing / total), "free_testing_BOM_floor_KES": str(floor),
        "meaning": "Algebraic ceiling, not a safe method or candidate effect. Missing costs are not zero.",
        "branches": branches, "new_reference_KES_per_nominal_lifetime_kWh": amount(new_lifetime_unit),
        "capacity_identity_can_reverse_partial_ranking": (number(branches[0]["used_to_new_ratio"]) > 1) != (number(branches[1]["used_to_new_ratio"]) > 1),
        "complete_service_profit": None, "source_conflicts": kenya["source_conflicts"],
        "selection_yield": None, "reason": "Selected 14 modules are not all accepted modules; unreported outcomes cannot be assumed rejects or successes"})

    used_mean = sum(number(s["used_USD_per_kWh"]) for s in mini["sites"]) / len(mini["sites"])
    new_mean = sum(number(s["new_USD_per_kWh"]) for s in mini["sites"]) / len(mini["sites"])
    horizon, capacity = mini["comparison_service_years"], number(mini["illustrative_pack_kWh"])
    rows = []
    for pricing, used_price in [("source_rounded_mean", number(mini["source_rounded_mean_used_USD_per_kWh"])), ("mean_of_site_chart", used_mean)]:
        for period in mini["used_replacement_years"]:
            for inclusive in [False, True]:
                ut, nt = schedule(period, horizon, inclusive), schedule(mini["ordinary_new_replacement_years"], horizon, inclusive)
                uc, nc = used_price * len(ut), new_mean * len(nt)
                rows.append({"pricing": pricing, "used_period_years": period, "include_terminal_purchase": inclusive,
                    "used_purchase_years": ut, "new_purchase_years": nt,
                    "used_capex_USD_per_kWh": amount(uc), "new_capex_USD_per_kWh": amount(nc),
                    "used_pack_capex_USD": amount(uc * capacity), "new_pack_capex_USD": amount(nc * capacity),
                    "used_percent_above_new": amount(100 * (uc / nc - 1)),
                    "terminal_asset_value_USD": None,
                    "qualified_service_cost_USD": None})
    write(output / "REPLACEMENT_LEDGER.json", {"service_interval": "[0,20) years",
        "price_basis": "Published source-reported invoice aggregates, historical; no current quote assumed",
        "zero_discount_constant_price_diagnostic_only": True,
        "site_mean_used_USD_per_kWh": amount(used_mean), "site_mean_new_USD_per_kWh": amount(new_mean),
        "ratio_of_means_upfront_discount_percent": amount(100 * (1 - used_mean / new_mean)),
        "rows": rows,
        "interpretation": "Boundary convention changes the result; no reconstruction or error finding against unreleased source workbook. Inclusive end purchases require service beyond horizon or independently priced ending assets. Neither cost sign is profit.",
        "excluded_source_costs": mini["invoice_limitations"]})

    pairs, index = [], {(r["asset"], r["current_A"], r["date"]): r for r in measured["rows"]}
    for asset in ["BESS1", "BESS2"]:
        for current in [30, 60]:
            a, b = index[(asset, current, "2020-06-17")], index[(asset, current, "2020-11-17")]
            inconsistent = []
            for r in [a, b]:
                for field in ["temperature_C", "initial_cell_voltage_V", "end_discharge_cell_voltage_V", "equivalent_capacity_Ah"]:
                    stats = r[field]
                    if not stats["min"] <= stats["avg"] <= stats["max"]:
                        inconsistent.append({"record": r["id"], "field": field})
            pairs.append({"asset": asset, "current_A": current,
                "apparent_min_equivalent_capacity_change_percent": amount(100 * (1 - number(b["equivalent_capacity_Ah"]["min"]) / number(a["equivalent_capacity_Ah"]["min"]))),
                "raw_Ah_change_percent": amount(100 * (1 - number(b["measured_capacity_Ah"]) / number(a["measured_capacity_Ah"]))),
                "initial_avg_voltage_delta_V": amount(number(b["initial_cell_voltage_V"]["avg"]) - number(a["initial_cell_voltage_V"]["avg"])),
                "end_avg_voltage_delta_V": amount(number(b["end_discharge_cell_voltage_V"]["avg"]) - number(a["end_discharge_cell_voltage_V"]["avg"])),
                "source_summary_inconsistencies": inconsistent,
                "causal_degradation": "UNKNOWN", "qualified_true_SOH": None,
                "reason": "Endpoint/temperature differences, summary inconsistencies and unavailable calibration/raw traces; not proof of degradation or safety"})
    write(output / "MEASUREMENT_BOUNDARY.json", {"actual_assets": 2, "rows_are_not_independent_replications": True,
                                               "comparisons": pairs, "qualification": "UNKNOWN"})
    missing = [v["category"] for v in coverage["cost_items"] if v["complete_matched_amount"] is None]
    report = {"decision": "PURSUE_LIFETIME_QUALIFICATION_MEASUREMENT; DO_NOT_ADMIT_COMMERCIAL_OFFERING",
        "different_bottleneck": "Warranty-backed usable lifetime and full replacement obligations of retired battery storage",
        "demand": "Source-reported actual mini-grid purchases and external battery-grading participation; no buyer acceptance of Alpha",
        "full_service_profit": None, "full_service_comparison": "UNKNOWN", "unknown_complete_cost_categories": missing,
        "candidate_technical_gain": "NOT_ESTABLISHED", "ordinary_qualified_methods_retained": True,
        "unrestricted_earned_funds": 0, "exchange": "NOT_RUN_NO_QUALIFIED_DELIVERY_OR_BUYER_CONTRACT",
        "next_decisive_measurement": "Rights-cleared paired per-site capacity/calibration, load/temperature and failure records with all purchase, logistics, warranty, replacement and terminal cash flows; prefreeze service/acceptance before testing a lifetime instrument",
        "public_data_gaps": ["private underlying invoices and service terms", "longitudinal true usable-capacity calibration", "rejected/all-input histories and costs", "independent offer price or customer acceptance"],
        "resource_meter": {"wall_seconds": time.monotonic()-start, "CPU_seconds": time.process_time()-cpu,
                           "max_process_RSS_KiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                           "rate_and_complete_inference_cost": None},
        "scope": "Development arithmetic and admission probe; not a new diagnostic, commercial delivery, certification, or statistical confirmation",
        "statistical_alpha_spent": 0}
    write(output / "DECISION.json", report)
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
    write(output / "COMPLETE.json", {"state": "COMPLETE", "outputs_sha256": files,
                                   "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
    return report


if __name__ == "__main__":
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    resource.setrlimit(resource.RLIMIT_AS, (256*1024**2, 256*1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (2*1024**2, 2*1024**2))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    outcome = run(args.input, args.output)
    print(json.dumps({"decision": outcome["decision"], "output": str(args.output)}))
