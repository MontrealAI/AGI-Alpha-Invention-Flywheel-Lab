#!/usr/bin/env python3
"""PROOF Ω: finite-state proof-carrying executable policies, no model API needed."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
from engine import SpecificationError, explore
from audit import AuditError, audit, apply_verified

HERE = Path(__file__).resolve().parent


def load(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save(path, value):
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def cli():
    parser = argparse.ArgumentParser(description="Prove and enforce an exact finite-state policy")
    sub = parser.add_subparsers(dest="operation", required=True)
    prove = sub.add_parser("prove", help="Explore the full reachable policy state space")
    prove.add_argument("policy")
    prove.add_argument("--out", required=True)
    prove.add_argument("--max-states", type=int, default=100_000)
    check = sub.add_parser("audit", help="Independent certificate validation")
    check.add_argument("policy")
    check.add_argument("certificate")
    run = sub.add_parser("apply", help="Execute only a certified transition")
    run.add_argument("policy")
    run.add_argument("certificate")
    run.add_argument("action")
    run.add_argument("state", help="JSON object with all policy state variables")
    demo = sub.add_parser("demo", help="Demonstrate a passing and a failing financial policy")
    demo.add_argument("--out", default="/tmp/proof-omega-demo")
    args = parser.parse_args()
    try:
        if args.operation == "prove":
            result = explore(load(args.policy), max_states=args.max_states)
            save(args.out, result)
            print(json.dumps({"status": result["status"], "certificate": args.out,
                              "states": result.get("state_count"), "counterexample": result.get("counterexample")}, indent=2))
            return 0 if result["status"] == "PASS" else 2
        if args.operation == "audit":
            print(json.dumps(audit(load(args.policy), load(args.certificate)), indent=2))
            return 0
        if args.operation == "apply":
            current = json.loads(args.state)
            print(json.dumps(apply_verified(load(args.policy), load(args.certificate), current, args.action), sort_keys=True))
            return 0
        if args.operation == "demo":
            out = Path(args.out)
            out.mkdir(parents=True, exist_ok=True)
            good = load(HERE / "examples" / "escrow.json")
            bad = load(HERE / "examples" / "escrow_bug.json")
            positive = explore(good)
            negative = explore(bad)
            save(out / "PROOF.json", positive)
            save(out / "COUNTEREXAMPLE.json", negative)
            verified = audit(good, positive)
            if positive["status"] != "PASS" or negative["status"] != "FAIL":
                raise AuditError("demo evidence did not match expectations")
            print(json.dumps({"correct_policy": verified,
                              "buggy_policy": {"status": negative["status"], "witness": negative["counterexample"]},
                              "artifact_dir": str(out)}, indent=2))
            return 0
    except (ValueError, OSError, SpecificationError, AuditError, KeyError, TypeError) as err:
        print(json.dumps({"status": "HOLD", "error": str(err)}), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(cli())
