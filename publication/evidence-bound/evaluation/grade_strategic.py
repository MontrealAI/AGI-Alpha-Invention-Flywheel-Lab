# SPDX-License-Identifier: Apache-2.0
"""Grade the fixed predictive arms against an independently recomputed exact oracle."""

from argparse import ArgumentParser
from collections import Counter, defaultdict
from fractions import Fraction
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from statistics import mean
from time import perf_counter

from strategic_reference import exact


STRATA = ("asymmetric-two","asymmetric-extra-action","value-shift")
NO_TOOL = ("direct","method","retrieval")
REGISTRATION_SHA256 = "4df9caa128e65096a85f9faea372415fc56fae24550b792aba63ce1b7a27fdf7"
ADAPTER_SHA256 = "f278bd65102ef04e060ccade71fde2a92a7438064af3e95be53e7b744e6c64a3"
WEIGHTS_SHA256 = "5af571cbf074e6d21a03528d2330792e532ca608f24ac70a143f6b369968ab8c"
PREDICTOR_SHA256 = "bdde088ca5d9ba68f94a43f3382cf99b8d7ec6352d37ca81aea4d608e4c81f88"


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def input_sha(case):
    return sha256(json.dumps(case, sort_keys=True, separators=(",",":"), ensure_ascii=False).encode()).hexdigest()


def by_id(items):
    result = dict((row["id"],row) for row in items)
    if len(result) != len(items):
        raise ValueError("Duplicate evaluation case.")
    return result


def arm(cases, oracle, predictions):
    if set(predictions) != set(cases):
        raise ValueError("A qualified arm needs one outcome per registered case.")
    outcomes, groups, pairs = [], defaultdict(list), defaultdict(list)
    for ident, case in cases.items():
        prediction, actual = predictions[ident], oracle[ident]
        p = prediction["probability_buy"]
        decision = prediction["decision"]
        target = actual["choice"]
        advance = Fraction(actual["advantage_after_fee"])
        if prediction["input_sha256"] != input_sha(case) or decision not in {"BUY","SKIP"} or not isfinite(p) or not 0 <= p <= 1:
            raise ValueError(f"Arm prediction is not bound to its registered case {ident}.")
        result = {"id":ident, "family":actual["family"], "decision":decision,"expected":target,
                  "p_buy":p,"accepted":decision==target,"regret":str(Fraction(0) if decision==target else abs(advance)),
                  "brier":(p-int(target=="BUY"))**2,"prompt_tokens":prediction.get("tokens"),
                  "latency_share_seconds":prediction.get("batch_share_seconds")}
        outcomes.append(result)
        groups[actual["family"]].append(result)
        if actual["pair"] is not None:
            pairs[actual["pair"]].append(result)
    stratified = {key:{"accepted":sum(row["accepted"] for row in rows), "total":len(rows),
                        "brier":mean(row["brier"] for row in rows)}
                  for key,rows in sorted(groups.items())}
    return {"accepted":sum(row["accepted"] for row in outcomes),"total":len(outcomes),"brier":mean(row["brier"] for row in outcomes),
            "regret_total":str(sum(Fraction(row["regret"]) for row in outcomes)),
            "false_buys_on_exact_ties":sum(row["family"]=="boundary-tie" and row["decision"]=="BUY" for row in outcomes),
            "predicted_decisions":dict(Counter(row["decision"] for row in outcomes)),
            "strata":stratified,"value_shift_consistent_pairs":sum(
                key.startswith("shift-") and len({x["decision"] for x in rows})==1 for key,rows in pairs.items()),
            "boundary_adjacent_exact_pairs":sum(
                key.startswith("boundary-") and all(x["accepted"] for x in rows) for key,rows in pairs.items()),
            "observed_batch_wall_seconds":sum(x["latency_share_seconds"] or 0 for x in outcomes),
            "total_prompt_tokens":sum(x["prompt_tokens"] or 0 for x in outcomes),"outcomes":outcomes}


def main():
    parser = ArgumentParser(description=__doc__)
    for name in ("registration","cases","oracle","predictions","output"):
        parser.add_argument("--"+name,type=Path,required=True)
    args = parser.parse_args()
    if sha(args.registration) != REGISTRATION_SHA256:
        raise ValueError("Exactly the preregistered evaluation must be used.")
    registration = json.loads(args.registration.read_bytes())
    if sha(args.cases) != registration["input_sha256"] or sha(args.oracle) != registration["oracle_sha256"]:
        raise ValueError("Held input or oracle bytes differ.")
    if sha(Path(__file__).with_name("strategic_reference.py")) != registration["exact_reference_sha256"]:
        raise ValueError("Independent exact reference differs.")
    cases = by_id([json.loads(line) for line in args.cases.read_bytes().splitlines()])
    oracle = by_id(json.loads(args.oracle.read_bytes()))
    if set(oracle)!=set(cases) or len(cases)!=registration["planned_cases"]:
        raise ValueError("The fixed denominator changed.")
    started = perf_counter()
    for ident, case in cases.items():
        checked = exact(case)
        if any(oracle[ident][key]!=value for key,value in checked.items()):
            raise ValueError(f"Independent primal/dual replay disagrees with the frozen target {ident}.")
    exact_solver_seconds = perf_counter()-started
    predictions = json.loads(args.predictions.read_bytes())
    if (predictions["weights_sha256"]!=WEIGHTS_SHA256 or predictions["adapter_sha256"]!=ADAPTER_SHA256
            or predictions["prediction_source_sha256"]!=PREDICTOR_SHA256
            or predictions["case_bytes_sha256"]!=registration["input_sha256"]):
        raise ValueError("Model, checkpoint or case identity differs.")
    required = {prefix+"_"+style for prefix in ("base","adapted") for style in (*NO_TOOL,"verified-tool")}
    if set(predictions["arms"])!=required:
        raise ValueError("The registered comparison arms are incomplete.")
    results = {key:arm(cases,oracle,by_id(rows)) for key,rows in predictions["arms"].items()}
    best_base = max(("base_"+style for style in NO_TOOL),key=lambda name:results[name]["accepted"])
    label_counts = Counter(row["choice"] for row in oracle.values())
    changed = {}
    for style in (*NO_TOOL,"verified-tool"):
        same_cases = zip(results["base_"+style]["outcomes"],results["adapted_"+style]["outcomes"],strict=True)
        changed[style] = sum(base["decision"] != adapted["decision"] for base,adapted in same_cases)
    gate_checks = {}
    for style in NO_TOOL:
        key = "adapted_"+style
        current = results[key]
        gate_checks[key] = {"minimum_36_of_48":current["accepted"] >= 36,
                            "at_least_8_more_than_strongest_no_tool_base":current["accepted"]>=results[best_base]["accepted"]+8,
                            "each_12_case_stratum_at_least_60_percent":all(
                                current["strata"][family]["accepted"]*5 >= current["strata"][family]["total"]*3
                                for family in STRATA),
                            "at_most_2_false_purchases_on_exact_ties":current["false_buys_on_exact_ties"]<=2}
    report = {
        "schema":"frontier/independent-strategic-llm-result-v1","registration_sha256":REGISTRATION_SHA256,
        "prediction_bytes_sha256":sha(args.predictions),"exact_reference_source_sha256":registration["exact_reference_sha256"],
        "base_sha256":WEIGHTS_SHA256,"adapter_sha256":ADAPTER_SHA256,"predictor_sha256":PREDICTOR_SHA256,"cases":len(cases),
        "strata":dict(Counter(row["family"] for row in oracle.values())),
        "label_counts":dict(label_counts),"constant_skip_control":{"accepted":label_counts["SKIP"]},
        "matched_decisions_changed_by_adaptation":changed,
        "oracle_admissibility":"Exact rational primal and dual witnesses agreed on all cases.",
        "strongest_matched_no_tool_base_arm":best_base,"preregistered_gates":gate_checks,
        "admission":"GO in tested scientific scope" if all(gate_checks["adapted_direct"].values()) else "NO-GO for specialist admission",
        "exact_solver":{"accepted":len(cases),"wall_seconds":exact_solver_seconds,
                        "baseline_uses_explicit_payoff_and_signal_structure":True},
        "predictive_scoring_wall_seconds":predictions["wall_seconds"],
        "peak_predictor_process_memory_bytes":predictions["peak_process_memory_bytes"],
        "matched_arms":results,
        "limits":"Synthetic one-observation decisions. Paired cases share structure. Scores are probabilities conditional on the two forced response tokens. Distinct evaluator context on one administrative setup. No full-cost or frontier superiority claim.",
    }
    with args.output.open("x",encoding="utf-8") as stream:
        json.dump(report,stream,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)
        stream.write("\n")
    print(json.dumps({"denominator":len(cases),"qualified":report["admission"],
        "correct":{key:value["accepted"] for key,value in results.items()},"gate_checks":gate_checks}))


if __name__ == "__main__":
    main()
