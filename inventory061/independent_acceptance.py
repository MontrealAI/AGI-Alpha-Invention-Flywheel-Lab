"""Independent acceptance for the original public OR-License13 inventory request.

No producer, expert answer, hidden verifier, or supplied accounting program is
imported. Formula semantics come only from the original client brief and the two
client-provided input/program files. Circular demand windows are recomputed by
direct summation; holding inventory uses exact rational arithmetic.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import time

SOURCE_COMMIT = "2bda4b8d6ddd4bd1cb62b89acee0c7c2f1914d47"
SOURCE_SHA256 = {
    "brief.md": "294948637c42a5e0f6c87b1125a14ef4b88a5179fceb0d71b45b36c4ef53c0e8",
    "problem_description.md": "d05da00a1ced1f6c6ddfc63fe87a72aa0338cccd91bafeb6ec44ecf3a10a5c26",
    "params.yaml": "add849298baea9e6d8fe5d9cf0441acf248548ff76a25cf562c6351f0c22bee8",
    "01.json": "c949fac0c2fe39c8ada57d028152072b4aa722a415343c2b16ad454f4afab649",
    "program/_inventory_engine.py": "2567686d09d69df44fe95f2945e2fe2af66786006b87d58100a0e15a09e80ca2",
    "program/_inventory_objective.py": "00fb6c9d7b3b2d567bb2f84344dd72b767c2898400fe14a3acd2c2bf16be58f4",
}
DATA_CANONICAL_SHA256 = "128ce3632a2af201a38996f0e6e5a3fb5da6bcef523e3f27dc4ac212a7e3bd0b"
PARAMETERS = {
    "reorder_point_fixed_quantity": {"reorder_point", "order_quantity"},
    "reorder_point_order_up_to": {"reorder_point", "order_up_to_level"},
    "base_stock": {"base_stock_level"},
    "periodic_review_order_up_to": {"order_up_to_level"},
}


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def _safe_hash(value):
    try:
        return canonical_hash(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _unique_object(pairs):
    value = {}
    for key, entry in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON field: {key}")
        value[key] = entry
    return value


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON value: " + value)))


def _integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _rational(value):
    return Fraction(str(value))


def _windows(daily, days):
    # Independent from the supplied program's incremental circular recurrence.
    return [sum(daily[(anchor + offset) % 365] for offset in range(days))
            for anchor in range(365)]


def _account(instance, policies, commitments):
    products = {row["product"]: row for row in instance["products"]}
    centrals = {row["node"]: row for row in instance["central_warehouses"]}
    regionals = {row["node"]: row for row in instance["regional_centers"]}
    daily = {(node, product): list(instance["demand"][node][product])
             for node in regionals for product in products}
    for product, terms in products.items():
        central = terms["source_central_warehouse"]
        daily[central, product] = [sum(daily[node, product][day] for node in regionals)
                                   for day in range(365)]
    audits = {}
    costs = {key: Fraction(0) for key in ("CDC_safety", "RDC_safety", "CDC_cycle", "RDC_cycle")}
    inventories = {key: Fraction(0) for key in costs}
    for pair in sorted(policies):
        node, product = pair
        entry = policies[pair]
        params, family = entry["parameters"], entry["policy_type"]
        if node in centrals:
            kind, terms = "CDC", centrals[node]
            days = terms["lead_time_days"] - commitments[pair]
        else:
            kind, terms = "RDC", regionals[node]["replenishment"][products[product]["category"]]
            days = commitments[terms["source"], product] + terms["lead_time_days"]
        if family == "periodic_review_order_up_to":
            days += terms["review_interval_days"]
        if family in {"reorder_point_fixed_quantity", "reorder_point_order_up_to"}:
            threshold = params["reorder_point"]
        elif family == "base_stock":
            threshold = params["base_stock_level"]
        else:
            threshold = params["order_up_to_level"]
        windows = _windows(daily[pair], days)
        mean_protection = Fraction(sum(windows), 365)
        safety = max(Fraction(0), threshold - mean_protection)
        fixed_cycle = Fraction(sum(daily[pair]) * terms["review_interval_days"], 730)
        batch_cycle = Fraction(0)
        if family == "reorder_point_fixed_quantity":
            batch_cycle = Fraction(params["order_quantity"], 2)
        elif family == "reorder_point_order_up_to":
            batch_cycle = Fraction(params["order_up_to_level"] - params["reorder_point"], 2)
        elif family == "periodic_review_order_up_to":
            batch_cycle = fixed_cycle
        cycle = max(fixed_cycle, batch_cycle)
        unit_holding = _rational(products[product]["unit_value"]) * _rational(products[product]["holding_cost_rate"])
        costs[kind + "_safety"] += safety * unit_holding
        costs[kind + "_cycle"] += cycle * unit_holding
        inventories[kind + "_safety"] += safety
        inventories[kind + "_cycle"] += cycle
        audits[pair] = {"windows": windows, "threshold": threshold,
                        "kind": kind, "protection_days": days,
                        "mean_protection_demand": float(mean_protection),
                        "safety_stock_pieces": float(safety), "cycle_stock_pieces": float(cycle),
                        "safety_holding_cost_yuan": float(safety * unit_holding),
                        "cycle_holding_cost_yuan": float(cycle * unit_holding)}
    service = {}
    successes = {}
    for node in sorted(regionals):
        for product in sorted(products):
            source = regionals[node]["replenishment"][products[product]["category"]]["source"]
            upstream, local = audits[source, product], audits[node, product]
            count = sum(upstream["windows"][day] <= upstream["threshold"] and
                        local["windows"][day] <= local["threshold"] for day in range(365))
            successes[node + "/" + product] = count
            service[node + "/" + product] = count / 365
    total_cost = sum(costs.values(), Fraction(0))
    safety_cost, cycle_cost = costs["CDC_safety"] + costs["RDC_safety"], costs["CDC_cycle"] + costs["RDC_cycle"]
    mean_service_exact = Fraction(sum(successes.values()), 365 * 48)
    service_loss = max(Fraction(0), _rational(instance["ideal_service_level"]) - mean_service_exact)
    cost_loss = total_cost / (total_cost + _rational(instance["inventory_cost_normalization_yuan"]))
    weight_sum = _rational(instance["service_distance_weight"]) + _rational(instance["cost_distance_weight"])
    service_weight = _rational(instance["service_distance_weight"]) / weight_sum
    cost_weight = _rational(instance["cost_distance_weight"]) / weight_sum
    distance = math.sqrt(float(service_weight * service_loss**2 + cost_weight * cost_loss**2))
    level = math.floor((distance + 1e-12) / instance["ideal_distance_level_width"])
    below = sum(count * 100 < 95 * 365 for count in successes.values())
    return {
        "average_cycle_service": float(mean_service_exact), "minimum_cycle_service": min(service.values()),
        "cycle_service_by_pair": service, "successful_anchor_counts_by_pair": successes,
        "historical_anchors_per_pair": 365, "RDC_product_pairs_below_95_percent": below,
        "all_RDC_product_pairs_meet_95_percent": below == 0, "95_percent_is_hard_constraint": False,
        "holding_cost_yuan_per_2023_year": float(total_cost),
        "safety_stock_holding_cost": float(safety_cost), "cycle_stock_holding_cost": float(cycle_cost),
        "cost_components_yuan": {key: float(value) for key, value in costs.items()},
        "inventory_components_pieces": {key: float(value) for key, value in inventories.items()},
        "normalized_service_loss": float(service_loss), "normalized_inventory_cost_loss": float(cost_loss),
        "ideal_point_distance": distance, "ideal_distance_level": level,
        "ranking_key": [level, -float(mean_service_exact), float(total_cost)],
        "encoded_client_program_objective": level * 1_000_000_000.0 + float(1 - mean_service_exact) * 1_000_000.0 + float(cost_loss),
        "point_accounting": {node + "/" + product: {key: value for key, value in audit.items() if key != "windows"}
                             for (node, product), audit in audits.items()},
    }


def verify(instance, solution):
    """Check original hard rules and recompute client-provided accounting.

    Historical service below95% is disclosed and scored; it is never converted
    into an invented rejection threshold. No self-reported cost/service fields
    are accepted in the required delivery JSON.
    """
    errors = []
    metrics = None
    started, cpu = time.monotonic(), time.process_time()

    def require(condition, message):
        if not condition:
            errors.append(message)

    try:
        require(canonical_hash(instance) == DATA_CANONICAL_SHA256, "original client input hash mismatch")
        require(instance.get("contract_version") == "inventory-harbor-7", "wrong original contract version")
        require(instance.get("planning_year") == 2023 and instance.get("horizon_days") == 365, "wrong original planning horizon")
        products = {row["product"]: row for row in instance["products"]}
        centrals = {row["node"]: row for row in instance["central_warehouses"]}
        regionals = {row["node"]: row for row in instance["regional_centers"]}
        expected_cdc = {(terms["source_central_warehouse"], product) for product, terms in products.items()}
        expected_rdc = {(node, product) for node in regionals for product in products}
        expected_points = expected_cdc | expected_rdc
        require(len(expected_cdc) == 6 and len(expected_points) == 54, "original point coverage changed")
        for node in regionals:
            for product in products:
                values = instance["demand"][node][product]
                require(len(values) == 365 and all(_integer(v) and v >= 0 for v in values), "invalid original demand history")
                source = regionals[node]["replenishment"][products[product]["category"]]["source"]
                require(source == products[product]["source_central_warehouse"], "original supply relationship inconsistent")
        require(isinstance(solution, dict), "H0: solution must be an object")
        if not isinstance(solution, dict):
            raise ValueError("cannot parse nonobject solution")
        require(set(solution) == {"inventory_policy", "cdc_service_time"}, "H0: root fields must be exactly inventory_policy and cdc_service_time")
        policies, commitments = {}, {}
        require(isinstance(solution.get("inventory_policy"), list), "H0: inventory_policy must be an array")
        for index, entry in enumerate(solution.get("inventory_policy", [])):
            label = f"inventory_policy[{index}]"
            if not isinstance(entry, dict):
                errors.append(f"H0: {label} must be an object")
                continue
            require(set(entry) == {"node", "product", "policy_type", "parameters"}, f"H0: {label} has incorrect fields")
            node, product, family, parameters = (entry.get(key) for key in ("node", "product", "policy_type", "parameters"))
            if not all(isinstance(v, str) for v in (node, product, family)):
                errors.append(f"H0: {label} identifiers must be strings")
                continue
            pair = node, product
            require(pair in expected_points, f"H1: unknown or altered inventory point {node}/{product}")
            require(pair not in policies, f"H1: duplicate inventory point {node}/{product}")
            if family not in PARAMETERS or not isinstance(parameters, dict):
                errors.append(f"H0: {label} unsupported family or parameters")
                continue
            require(set(parameters) == PARAMETERS[family], f"H0: {label} wrong policy parameter fields")
            integer_values = all(_integer(v) for v in parameters.values())
            require(integer_values, f"H0: {label} parameters must be integers, excluding booleans")
            if not integer_values:
                continue
            require(all(value >= 0 for value in parameters.values()), f"H2: {label} negative parameter")
            if family == "reorder_point_fixed_quantity":
                require(parameters.get("order_quantity", 0) > 0, f"H2: {label} order quantity must be positive")
            elif family == "reorder_point_order_up_to":
                require(parameters.get("order_up_to_level", -1) >= parameters.get("reorder_point", 0), f"H2: {label} order-up-to below reorder point")
            policies[pair] = entry
        require(set(policies) == expected_points and len(solution.get("inventory_policy", [])) == 54, "H1: exact54 inventory points not covered")
        require(isinstance(solution.get("cdc_service_time"), list), "H0: cdc_service_time must be an array")
        for index, entry in enumerate(solution.get("cdc_service_time", [])):
            if not isinstance(entry, dict):
                errors.append(f"H0: cdc_service_time[{index}] must be an object")
                continue
            require(set(entry) == {"node", "product", "days"}, f"H0: cdc_service_time[{index}] incorrect fields")
            node, product, days = (entry.get(key) for key in ("node", "product", "days"))
            if not isinstance(node, str) or not isinstance(product, str):
                errors.append(f"H0: cdc_service_time[{index}] identifiers must be strings")
                continue
            pair = node, product
            require(pair in expected_cdc, f"H1: unknown CDC-product point {node}/{product}")
            require(pair not in commitments, f"H1: duplicate CDC-product commitment {node}/{product}")
            require(_integer(days), f"H0: {node}/{product} service days must be an integer, excluding booleans")
            if _integer(days) and pair in expected_cdc:
                require(0 <= days <= centrals[node]["lead_time_days"], f"H3: {node}/{product} commitment outside inbound lead")
            commitments[pair] = days
        require(set(commitments) == expected_cdc and len(solution.get("cdc_service_time", [])) == 6, "H1: exact6 CDC commitments not covered")
        if not errors:
            metrics = _account(instance, policies, commitments)
    except (KeyError, ValueError, TypeError, AttributeError, IndexError, OverflowError) as exc:
        errors.append(f"malformed or unsupported input/delivery: {type(exc).__name__}: {exc}")
    return {
        "schema": "orlicense061-independent-acceptance/v1", "accepted": not errors,
        "errors": errors, "metrics": metrics, "source_commit": SOURCE_COMMIT,
        "input_canonical_sha256": _safe_hash(instance),
        "delivery_sha256": _safe_hash(solution),
        "scope": "original public client hard rules and retrospective2023 accounting; no expert comparison, live industrial acceptance or realized savings claim",
        "telemetry": {"wall_time_s": time.monotonic()-started, "process_cpu_s": time.process_time()-cpu,
                      "external_model_billing": None},
    }


def check_additional_quality95(receipt):
    """Separate buyer-requested offer condition; original hard rules stay intact."""
    counts = (receipt.get("metrics") or {}).get("successful_anchor_counts_by_pair", {})
    minimum = (95 * 365 + 99) // 100
    failures = [{"point": point, "successful_anchors": count, "total_anchors": 365}
                for point, count in sorted(counts.items()) if count < minimum]
    return {"condition": "each48 joint CDC/RDC empirical cycle service at least95percent",
            "requested_service_floor": 0.95, "minimum_successful_anchors_per365": minimum,
            "original_contract_accepted": receipt.get("accepted") is True,
            "accepted": receipt.get("accepted") is True and len(counts) == 48 and not failures,
            "failed_pairs": failures,
            "scope": "additional explicit quality offer; original ranking and hard acceptance unchanged"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=Path(__file__).with_name("inputs"))
    parser.add_argument("--solution", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-service95", action="store_true",
                        help="also check separately requested95percent service for every pair")
    args = parser.parse_args(argv)
    source_errors, hashes = [], {}
    for name, expected in SOURCE_SHA256.items():
        path = args.inputs / name
        if not path.is_file():
            source_errors.append("original source file missing: " + name)
            continue
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        if hashes[name] != expected:
            source_errors.append("original source file hash mismatch: " + name)
    try:
        receipt = verify(read_json(args.inputs / "01.json"), read_json(args.solution))
    except (OSError, ValueError) as exc:
        receipt = {"schema": "orlicense061-independent-acceptance/v1", "accepted": False,
                   "errors": [str(exc)], "metrics": None}
    receipt["errors"] = source_errors + receipt["errors"]
    receipt["accepted"] = not receipt["errors"]
    receipt["original_source_sha256"] = hashes
    receipt["checker_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    if args.require_service95:
        receipt["additional_quality95"] = check_additional_quality95(receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"output": str(args.output), "accepted": receipt["accepted"], "errors": receipt["errors"]}))
    passed = receipt["accepted"] and (not args.require_service95 or receipt["additional_quality95"]["accepted"])
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
