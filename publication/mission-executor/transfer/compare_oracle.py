"""Compare retained sparse execution with its strongest available implicit alternative."""

from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from statistics import median
from time import perf_counter, process_time
import argparse
import json

from run_transfer import HERE, alternative, arm, decisions, digest, load, verify
from compare_observation import double_oracle


def oracle_arm(case):
    wall, cpu = perf_counter(), process_time()
    observed = {}
    for option in ("none", "probe"):
        _, game = alternative(case["game"], option)
        certificate, result = double_oracle(game)
        proof = verify(game, certificate)
        if proof["verdict"] != "QUALIFIED":
            raise ArithmeticError("Restricted oracle failed the exact outcome contract")
        observed[option] = {
            "bounds": [proof["lower"], proof["upper"]],
            "iterations": result["iterations"],
            "active_row_policies": result["active_row_policies"],
            "active_opponent_actions": result["active_opponent_actions"],
        }
    blind_low, blind_high = map(Fraction, observed["none"]["bounds"])
    noisy_low, noisy_high = map(Fraction, observed["probe"]["bounds"])
    bounds = max(Fraction(0), noisy_low - blind_high), max(Fraction(0), noisy_high - blind_low)
    return {
        "wall_s": perf_counter() - wall,
        "cpu_s": process_time() - cpu,
        "fee_interval": list(map(str, bounds)),
        "quoted_decisions": decisions(case["quotes"], bounds),
        "subgames": observed,
    }


def run(case, offset, repeats):
    pairings = {"retained": [], "double_oracle": []}
    for attempt in range(repeats):
        order = ("retained", "double_oracle") if (attempt + offset) % 2 == 0 else ("double_oracle", "retained")
        for method in order:
            if method == "retained":
                outcome = arm(case, method)
                del outcome["certificates"]
            else:
                outcome = oracle_arm(case)
            pairings[method].append(outcome)
        a, b = (pairings[method][-1] for method in ("retained", "double_oracle"))
        if a["quoted_decisions"] != b["quoted_decisions"]:
            raise ArithmeticError("Exact recommendations disagree")
        intervals = [tuple(map(Fraction, obj["fee_interval"])) for obj in (a, b)]
        if max(x[0] for x in intervals) > min(x[1] for x in intervals):
            raise ArithmeticError("Exact fee intervals disagree")
    medians = {method: {clock: median(x[clock] for x in runs) for clock in ("wall_s", "cpu_s")}
               for method, runs in pairings.items()}
    return {"id": case["id"], "samples": pairings, "median": medians,
            "retained_wall_ratio": medians["retained"]["wall_s"] / medians["double_oracle"]["wall_s"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    registration = HERE / "ORACLE-REGISTRATION.json"
    plan = load(registration)
    for name, expected in plan["sha256"].items():
        if digest(HERE / name) != expected:
            raise ValueError(f"Frozen comparator source changed: {name}")
    cases = load(HERE / "INPUTS.json")["cases"]
    rows = [run(case, i, plan["repetitions"]) for i, case in enumerate(cases)]
    threshold = sum(result["retained_wall_ratio"] <= 0.8 for result in rows)
    receipt = {
        "schema": "frontier/observation-cost-implicit-control-result-v1",
        "registered_sha256": digest(registration),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Post-primary same-cases sensitivity control, independently benchmarked strategy algorithm sharing the qualification verifier.",
        "cases": rows,
        "material_retained_speed_denominator": f"{threshold}/{len(rows)}",
    }
    with args.output.open("x",encoding="utf-8") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
