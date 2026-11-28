"""Execute the registered source qualification instrument and learning comparisons."""

from argparse import ArgumentParser
from hashlib import sha256
import json
from pathlib import Path
import sys
from time import perf_counter_ns, process_time_ns

from . import oracle, plans, records

RECEIPT = records.HERE / "receipt.json"


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def simplify(groups):
    return [case for group in groups for case in group]


def evaluate(cases, order, reference=None):
    statuses = {}
    work = 0
    for case in cases:
        status, cost, _ = plans.evaluate(case, order)
        statuses[case["id"]] = status
        work += cost
    if reference is not None and statuses != reference:
        raise ValueError("Evidence decision differs from the independent relational oracle")
    return statuses, work


def observation(cases, expected, order):
    _, steps = evaluate(cases, order, expected)
    return {"order": [plans.CHECKS[index] for index in order], "predicate_checks": steps}


def milestone_witness(intent, cases, order):
    viable = [c for c in cases if c["id"].startswith(intent)]
    if not viable:
        raise ValueError("Unregistered archive query")
    checks, _ = evaluate(viable, order, oracle.outcomes(viable))
    return [{"id": c["id"], "source": c["source"], "documented": c["observed"]["chronology"]}
            for c in viable if checks[c["id"]] == "supported"]


def run():
    telemetry = {}
    def timed(name, fn, *args):
        wall, cpu = perf_counter_ns(), process_time_ns()
        value = fn(*args)
        telemetry[name] = {"wall_ns": perf_counter_ns() - wall, "cpu_ns": process_time_ns() - cpu}
        return value

    source_bytes = records.CAPTURE.read_bytes()
    capture = json.loads(source_bytes)
    hardware = timed("adapt_hardware", records.hardware_groups)
    pages = timed("adapt_pages", records.pages_groups, capture["pages"])
    construction = simplify(hardware)
    pre_archive = [c for c in construction if "/prusa-archived-us-offer/" not in c["id"]]
    prior = milestone_witness("orderable/2026-10-20/", pre_archive, plans.FIXED)
    orderable = milestone_witness("orderable/2026-10-20/", construction, plans.FIXED)
    physical = milestone_witness("independent-application/2026-10-21/", construction, plans.FIXED)
    if len(orderable) != 1 or orderable[0]["documented"] != "2026-09-29" or physical:
        raise ValueError("The constructed proof must match the independently verified ALPHA-1 record")
    results = []
    for name, development, confirmation in (
        ("hardware-to-endpoints", hardware, records.endpoint_groups),
        ("pages-to-lean", pages, lambda: records.lean_groups(capture["lean"])),
    ):
        training = simplify(development)
        fitted = timed(f"{name}/adapt_development", plans.pooled_masks, development)
        greedy = timed(f"{name}/conventional_constructor", plans.greedy, *fitted)
        inherited = timed(f"{name}/exact_constructor", plans.optimal, *fitted)
        verification = timed(f"{name}/exhaustive_constructor_verification", plans.exhaustive, *fitted)
        if inherited != verification:
            raise ValueError("Exact subset choice disagrees with exhaustive enumeration")
        learned, rule, development_scores = timed(f"{name}/learn_rule", plans.choose_update, development)
        frozen = {"development_sha256": fingerprint(development), "inherited": inherited,
                  "learned": learned, "update": rule}
        confirmation = timed(f"{name}/adapt_confirmation", confirmation)
        cases = simplify(confirmation)
        if {case["source"] for case in training} & {case["source"] for case in cases}:
            raise ValueError("Development and confirmation must use different sources")
        expected = timed(f"{name}/independent_confirmation", oracle.outcomes, cases)
        oracle_check = timed(f"{name}/independent_development", oracle.outcomes, training)
        orders = {"fixed_no_history": plans.FIXED, "ordinary_reuse": tuple(inherited),
                  "equal_content_conventional": greedy, "pooled_constructor": inherited,
                  "learned_update": learned}
        arms = {key: timed(f"{name}/execute/{key}", observation, cases, expected, plan)
                for key, plan in orders.items()}
        require = timed(f"{name}/development_replay", observation, training, oracle_check, inherited)
        results.append({
            "campaign": name, "development_cases": len(training), "confirmation_cases": len(cases),
            "development_sha256": fingerprint(development), "confirmation_sha256": fingerprint(confirmation),
            "frozen_program_sha256": fingerprint(frozen), "development_checks": require["predicate_checks"],
            "confirmation_verdicts_sha256": fingerprint(expected),
            "confirmation_verdicts": {status: list(expected.values()).count(status)
                                      for status in ("supported", "inapplicable", "insufficient")},
            "learning_rule": rule, "development_omission_costs": development_scores, "arms": arms,
        })
    return {"schema": "frontier-omega-alpha/evidence-constructor-study-v1",
            "capture_sha256": sha256(source_bytes).hexdigest(), "orderable_before_october_21": orderable,
            "without_archived_offer": prior,
            "independent_production_evidence": physical, "campaigns": results,
            "operating_order": [plans.CHECKS[index] for index in plans.FIXED],
            "complete_productive_cost_established": False,
            "general_inventor_or_learning_advantage_established": False,
            "production_authority": False}, telemetry


def main():
    parser = ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--capture", type=Path)
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--measure", action="store_true")
    args = parser.parse_args()
    if args.capture:
        result = records.capture(args.capture)
    else:
        result, telemetry = run()
        if args.check and result != json.loads(RECEIPT.read_bytes()):
            raise SystemExit("The registered constructor comparison does not reproduce")
        if args.measure:
            print(json.dumps(telemetry, sort_keys=True), file=sys.stderr)
    print(json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
