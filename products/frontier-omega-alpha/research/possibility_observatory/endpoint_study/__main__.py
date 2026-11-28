"""Replay the registered, offline agentic endpoint study."""

from argparse import ArgumentParser
from collections import Counter
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sys
from time import perf_counter_ns, process_time_ns

from . import decision, mlcommons, reference

HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "observations.json"
RECEIPT = HERE / "receipt.json"
AS_OF = "2026-11-23"
THRESHOLDS = ["40", "20", "60", "80"]


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def load_observations():
    with SNAPSHOT.open("rb") as file:
        raw = file.read(mlcommons.MAX_SNAPSHOT + 1)
    if len(raw) > mlcommons.MAX_SNAPSHOT:
        raise ValueError("Oversized normalized snapshot")
    return json.loads(raw)


def emit_observations(path, stream):
    evidence = mlcommons.normalize(path)
    rows = evidence.pop("rows")
    head = json.dumps(evidence, indent=2, ensure_ascii=True)
    stream.write(head[:-2] + ',\n  "rows": [\n')
    for index, row in enumerate(rows):
        if index:
            stream.write(",\n")
        stream.write("    " + json.dumps(row, separators=(",", ":"), ensure_ascii=True))
    stream.write("\n  ]\n}\n")


def run(evidence):
    if evidence["source_sha256"] != mlcommons.SOURCE_SHA256:
        raise ValueError("Unregistered evidence")
    rows = evidence["rows"]
    decision.validate(rows, mlcommons.MATCH, AS_OF, THRESHOLDS[0])
    thresholds = decision.breakpoints(rows, mlcommons.MATCH, AS_OF)
    deltas = {Decimal(text) for text in THRESHOLDS} | set(thresholds)

    # Also verify the open side of every measured breakpoint. The midpoint until
    # the next point has exactly the same admissible witnesses as that interval.
    boundaries = [Decimal(0), *thresholds, thresholds[-1] + Decimal(2)] if thresholds else []
    deltas.update((a + b) / 2 for a, b in zip(boundaries, boundaries[1:]))
    minimums = [format(value, "f") for value in sorted(deltas)]
    wall, cpu = perf_counter_ns(), process_time_ns()
    candidate = [decision.evaluate(rows, mlcommons.MATCH, AS_OF, value) for value in minimums]
    candidate_cost = {"wall_ns": perf_counter_ns() - wall, "cpu_ns": process_time_ns() - cpu}
    wall, cpu = perf_counter_ns(), process_time_ns()
    control = reference.evaluate_many(rows, mlcommons.MATCH, AS_OF, minimums)
    control_cost = {"wall_ns": perf_counter_ns() - wall, "cpu_ns": process_time_ns() - cpu}
    if candidate != control:
        i = next(index for index, (a, b) in enumerate(zip(candidate, control, strict=True)) if a != b)
        raise ValueError(f"Independent SQL disagrees at threshold {minimums[i]}")

    by_id = {row["id"]: row for row in rows}
    full = dict(zip(minimums, candidate, strict=True))
    def summarize(result):
        return {
            "dispositions": dict(sorted(Counter(result["dispositions"].values()).items())),
            "witnesses": [by_id[key] for key in result["winners"]],
        }
    capped = decision.evaluate(rows, mlcommons.MATCH, AS_OF, "40", "500")
    if capped != reference.evaluate_many(rows, mlcommons.MATCH, AS_OF, ["40"], "500")[0]:
        raise ValueError("Independent SQL disagrees on the exploratory first-token ceiling")
    receipt = {
        "schema": "frontier-omega-alpha/endpoint-witness-receipt-v1",
        "purpose": "Shortlist measured configurations for a future scoped replay",
        "production_authority": False,
        "as_of": AS_OF,
        "match": mlcommons.MATCH,
        "source_url": evidence["source"],
        "source_sha256": evidence["source_sha256"],
        "source_generated_at": evidence["generated_at"],
        "normalized_sha256": fingerprint(evidence),
        "rows": len(rows),
        "checks_reproduced_by_sql": len(minimums),
        "decisions_reproduced_by_sql": len(rows) * len(minimums),
        "witness_sets_sha256": fingerprint(full),
        "measured_breakpoints": [format(value, "f") for value in thresholds],
        "witness_curve": [[minimum, result["winners"]] for minimum, result in full.items()],
        "registered_cases": {minimum: summarize(full[minimum]) for minimum in THRESHOLDS},
        "exploratory_first_token_screen": {
            "p90_milliseconds_at_most": "500", "minimum_e2e_tokens_per_second": "40",
            "decisions_reproduced_by_sql": len(rows), **summarize(capped),
        },
        "economic_advantage_established": False,
    }
    return receipt, {"portable_selector": candidate_cost, "direct_sql": control_cost,
                     "scope": "Selector computation only on one warm process; not full workflow cost"}


def checked_receipt():
    receipt, _ = run(load_observations())
    if receipt != json.loads(RECEIPT.read_bytes()):
        raise ValueError("Endpoint study receipt differs from registered replay")
    return receipt


def main():
    parser = ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--normalize-pinned-source", type=Path)
    operation.add_argument("--check", action="store_true")
    parser.add_argument("--measure", action="store_true")
    args = parser.parse_args()
    if args.normalize_pinned_source:
        emit_observations(args.normalize_pinned_source, sys.stdout)
        return
    receipt, telemetry = run(load_observations())
    if args.check and receipt != json.loads(RECEIPT.read_bytes()):
        raise SystemExit("Endpoint study receipt does not reproduce")
    print(json.dumps(receipt, indent=2, ensure_ascii=True, sort_keys=True))
    if args.measure:
        print(json.dumps(telemetry, sort_keys=True), file=sys.stderr)


if __name__ == "__main__":
    main()
