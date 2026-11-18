"""Replay a capacity decision against measured public MLPerf Endpoints report cells."""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPORTS_SHA256 = "ba572c5d5abf65aaf95406c66689d5b786a4bc4371d507ae2254e72c7763ac90"
REQUIRED = {"model", "dataset", "min_concurrency", "max_ttft_p90_ms", "min_tps_per_user",
            "load_mode", "rate_metric", "require_point_accuracy", "require_price", "require_access"}
NUMERICAL = {"below_minimum_load", "first_token_too_slow", "token_rate_too_low"}


def distinct(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"Duplicate JSON key: {key}")
        obj[key] = value
    return obj


def strict_json(text):
    def reject(s):
        raise ValueError(f"Non-finite number: {s}")
    return json.loads(text, object_pairs_hook=distinct, parse_constant=reject)


def canonical_hash(obj):
    encoded = json.dumps(obj, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode()
    return sha256(encoded).hexdigest()


def positive(value, field):
    if type(value) not in (str, int):
        raise ValueError(f"{field} needs a positive decimal string or integer.")
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", str(value)):
        raise ValueError(f"{field} needs a plain unsigned decimal, without an exponent.")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal for {field}.") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError(f"{field} must be positive and finite.")
    return number


def validate(contract):
    if not isinstance(contract, dict) or set(contract) != REQUIRED:
        raise ValueError("Provide precisely the registered capacity contract fields.")
    for field in ("model", "dataset"):
        if not isinstance(contract[field], str) or not contract[field].strip():
            raise ValueError(f"{field} must name a workload.")
    if contract["load_mode"] not in ("online", "reported"):
        raise ValueError("Use online or reported load mode.")
    if contract["rate_metric"] not in ("reported_tps_per_user", "inverse_p90_tpot", "agentic_e2e"):
        raise ValueError("Unsupported rate definition.")
    if type(contract["min_concurrency"]) is not int or contract["min_concurrency"] < 1:
        raise ValueError("Minimum concurrency must be a positive integer.")
    for field in ("require_point_accuracy", "require_price", "require_access"):
        if type(contract[field]) is not bool:
            raise ValueError(f"{field} must be a boolean.")
    return (positive(contract["max_ttft_p90_ms"], "max_ttft_p90_ms"),
            positive(contract["min_tps_per_user"], "min_tps_per_user"))


def frozen_sources(path):
    data = path.read_bytes()
    if sha256(data).hexdigest() != REPORTS_SHA256:
        raise ValueError("Public report cells differ from the reviewed evidence pack.")
    return strict_json(data)["sources"]


def source_checks(source, contract):
    checks = {
        "unverified_report": source["status"] != "PUBLISHED",
        "outside_standardized_scope": source["version"] != "v1.0" or source["division"] != "Standardized",
        "outside_reported_deployment": source["deployment"] != "Client on Premises",
        "unavailable_system_category": source["availability"] != "Available",
        "different_model": source["model"] != contract["model"],
        "different_dataset": source["dataset"] != contract["dataset"],
        "price_evidence_unavailable": contract["require_price"],
        "lab_access_unproven": contract["require_access"],
        "turn_end_to_end_unmeasured": contract["rate_metric"] == "agentic_e2e",
    }
    return [code for code, failed in checks.items() if failed]


def point_checks(point, contract, latency_limit, rate_floor):
    checks = {
        "incomplete_run": point["state"] != "complete",
        "failed_or_unreported_queries": point["failed"] != 0 or not point["issued"],
        "offline_or_unknown_load": point["config_type"] not in {"online", "submission"}
                                   or (point["config_region"] or "").lower() == "offline",
        "online_label_unavailable": contract["load_mode"] == "online" and point["config_type"] != "online",
        "point_accuracy_unreported": contract["require_point_accuracy"] and point["point_accuracy"] is None,
        "below_minimum_load": point["concurrency"] < contract["min_concurrency"],
    }
    latency = point["ttft_p90_ms"]
    checks["missing_first_token"] = latency is None
    checks["first_token_too_slow"] = latency is not None and Decimal(latency) > latency_limit
    mode = contract["rate_metric"]
    if mode != "agentic_e2e":
        val = point["tps_per_user"] if mode == "reported_tps_per_user" else point["tpot_p90_ms"]
        checks["missing_token_rate"] = val is None or Decimal(val) <= 0
        if not checks["missing_token_rate"]:
            # Cross-multiply as exact rationals; Decimal division rounds near boundaries.
            if mode == "reported_tps_per_user":
                checks["token_rate_too_low"] = Decimal(val) < rate_floor
            else:
                a, b = Decimal(val).as_integer_ratio()
                c, d = rate_floor.as_integer_ratio()
                checks["token_rate_too_low"] = a * c > 1000 * b * d
    return [code for code, failed in checks.items() if failed]


def next_observation(selected, rows):
    max_load = selected[0]["concurrency"] if selected else 0
    if selected:
        # A same-system next point is a real configuration that can be remeasured.
        # Report all tied directions; never transfer a capacity claim between systems.
        sources = {p["source"] for p in selected}
        higher = [p for p in rows if p["source"] in sources and p["concurrency"] > max_load
                  and set(p["reasons"]) <= NUMERICAL]
        if higher:
            load = min(p["concurrency"] for p in higher)
            targets = [p for p in higher if p["concurrency"] == load]
            return {"action": "measure_next_recorded_load_on_intended_traffic", "targets": targets}
        return {"action": "verify_selected_point_on_intended_traffic", "targets": selected}
    relevant = [p for p in rows if "different_model" not in p["reasons"]
                and "different_dataset" not in p["reasons"] and "unverified_report" not in p["reasons"]]
    obstacles = Counter(reason for p in relevant for reason in p["reasons"])
    return {"action": "collect_missing_evidence" if relevant else "measure_matching_workload",
            "obstacles": dict(sorted(obstacles.items()))}


def decide(contract, reports_path=None):
    """Return an evidence receipt. Only the shipped public projection is trusted."""
    latency, rate = validate(contract)
    sources = frozen_sources(Path(reports_path) if reports_path else HERE / "reports.json")
    eligible, excluded = [], []
    for source in sources:
        scope = source_checks(source, contract)
        for p in source["points"]:
            reasons = scope + point_checks(p, contract, latency, rate)
            row = {"source": source["id"], "run": p["run"], "concurrency": p["concurrency"],
                   "ttft_p90_ms": p["ttft_p90_ms"], "tps_per_user": p["tps_per_user"],
                   "tpot_p90_ms": p["tpot_p90_ms"], "system_tps": p["system_tps"],
                   "config_type": p["config_type"], "failed": p["failed"]}
            if reasons:
                excluded.append({**row, "reasons": reasons})
            else:
                eligible.append(row)
    highest = max((p["concurrency"] for p in eligible), default=None)
    selected = [p for p in eligible if p["concurrency"] == highest]
    return {"schema": "frontier-endpoints/decision/v1", "contract": dict(contract),
            "contract_sha256": canonical_hash(contract), "reports_sha256": REPORTS_SHA256,
            "instrument_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
            "decision": "supported" if selected else "withheld", "selected": selected,
            "eligible": eligible, "excluded": excluded, "next_test": next_observation(selected, excluded),
            "deployment_authorized": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--contract", required=True, type=Path)
    p.add_argument("--case", help="key in a named contract collection")
    p.add_argument("--reports", type=Path, help="alternative path to the same locked report bytes")
    p.add_argument("--output", type=Path, help="new receipt file; default stdout")
    args = p.parse_args()
    try:
        obj = strict_json(args.contract.read_bytes())
        result = decide(obj[args.case] if args.case else obj, args.reports)
        data = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as f:
                f.write(data)
        else:
            print(data, end="")
    except (ValueError, OSError, KeyError, TypeError) as error:
        p.exit(2, f"Endpoint Lab: {error}\n")


if __name__ == "__main__":
    main()
