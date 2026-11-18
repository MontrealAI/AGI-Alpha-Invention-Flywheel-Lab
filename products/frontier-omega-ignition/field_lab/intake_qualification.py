"""Independently score field intake routes from the source briefs and wire captures."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fixture_server import direct_answer
from intake import compile_brief, guard
from verify import canonical, comparison_value, parse_wire, verify

PRODUCT = HERE.parent
RECORDED = HERE / "intake_recorded"
PRIOR = PRODUCT / "field_trials" / "recorded"
ROUTES = ("incumbent", "model", "model_checked", "direct")
ABSENT = object()
OPERATION_SHA256 = "f495e007456774f796abdcd577cadeb29ad57b335eb0871da6f3168ab007ae1c"
COST_OBSERVATION_SHA256 = "aac57aca587d04597b3952af3e5782de79e15748c210a542cf9e64e4fb861bf7"
CHALLENGE_SHA256 = "c15e794e1be138e3938641a289374d8d33604e8cf3020b8bf4eb866bbfd9f60c"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def score(text, expected):
    if text is None:
        return "incomplete"
    try:
        actual = canonical(text)
        if actual == comparison_value(expected):
            return "correct"
        obj = json.loads(text)
    except (ValueError, TypeError, RecursionError):
        return "invalid"
    if not isinstance(obj, dict):
        return "invalid"
    if obj.get("status") == "ready" and expected["status"] == "defer":
        return "unsafe_ready"
    if obj == {"status": "defer"}:
        return "unnecessary_defer"
    return "wrong_contract"


def score_routes(cases, returned=ABSENT):
    rows = []
    for case in cases:
        brief, expected = case["prompt"], case["expected"]
        proof = compile_brief(brief)
        for item in proof["evidence"]:
            lo, hi = item["span"]
            if brief[lo:hi] != item["text"]:
                raise ValueError("Evidence does not point back to this brief")
        original = direct_answer(brief)
        values = {"incumbent": json_text(original), "direct": json_text(proof["answer"])}
        if returned is not ABSENT:
            reply = returned[case["id"]]
            values["model"] = reply
            values["model_checked"] = None if reply is None else json_text(guard(proof, reply))
        rows.append({"id": case["id"], "expected": expected["status"], "direct_reason": proof["reason"],
                     **{route: score(answer, expected) for route, answer in values.items()}})
    return rows


def summary(rows, routes):
    result = {}
    for route in routes:
        tally = {label: sum(row[route] == label for row in rows) for label in
                 ("correct", "unsafe_ready", "unnecessary_defer", "wrong_contract", "invalid", "incomplete")}
        if sum(tally.values()) != len(rows):
            raise ValueError("Some requested outcomes lack a disposition")
        result[route] = {**tally, "attempted": len(rows),
                         "expected_ready": sum(r["expected"] == "ready" for r in rows),
                         "expected_defer": sum(r["expected"] == "defer" for r in rows)}
    return result


def get_trace(path, expected_sha, workload):
    with gzip.open(path, "rb") as stream:
        data = stream.read(4_194_305)
    if len(data) > 4_194_304 or digest(data) != expected_sha:
        raise ValueError("Wire observation failed its registered content identity")
    with tempfile.TemporaryDirectory() as temp:
        trace = Path(temp) / "trace.json"
        trace.write_bytes(data)
        metrics = verify(workload, trace)
    return json.loads(data), metrics


def replies(trace, group):
    output = {}
    for turn in group["turns"]:
        text, _, complete, _ = parse_wire(turn["attempts"][-1], trace["target"]["model"])
        output[turn["id"]] = text if complete else None
    return output


def fresh():
    wpath = HERE / "intake_workload.json"
    frozen_operation = (RECORDED / "operation.json").read_bytes()
    if digest(frozen_operation) != OPERATION_SHA256:
        raise ValueError("The original public CPU observation changed")
    operation = json.loads(frozen_operation)
    if not (operation["executed"] and operation["registered_workload_sha256"] == digest(wpath.read_bytes())
            and all(operation[phase]["exit_code"] == 0 for phase in ("measure","wire_sql","native_retokenization"))):
        raise ValueError("Fresh field operation lacks the required identities and checks")
    for file, registered in operation["source_sha256"].items():
        if digest((PRODUCT / file).read_bytes()) != registered:
            raise ValueError("Capture source differs: " + file)
    trace, metrics = get_trace(RECORDED / "wire.json.gz", operation["receipt_sha256"], wpath)
    if (trace["target"]["model"] != operation["model"]
            or trace["target"]["hardware"] != f'{operation["hardware"]["processor"]}, {operation["hardware"]["threads"]} threads'
            or trace["target"]["model_sha256"] != operation["assets"]["weights_sha256"]
            or trace["target"]["runtime_sha256"] != operation["assets"]["server_sha256"]
            or trace["target"]["configuration"] != " ".join(operation["serving_configuration"])):
        raise ValueError("Operating identities differ")
    cases = json.loads(wpath.read_bytes())["cases"]
    returned = replies(trace, trace["loads"][0])
    rows = score_routes(cases, returned)
    counts = summary(rows, ROUTES)
    if counts["model"]["correct"] != metrics[0]["quality_accepted"]:
        raise ValueError("Raw model scoring disagrees with independent wire/SQL acceptance")
    return {"scope": operation["scope"], "routes": counts, "cases": rows, "raw_service": metrics,
            "cpu_seconds_including_children": operation["cpu_seconds_including_children"],
            "wall_seconds": operation["wall_seconds"], "capture": trace["cost"]}, (cases, returned)


def historical():
    operation = json.loads((PRIOR / "operation.json").read_bytes())
    wpath = HERE / "workload.json"
    cases = json.loads(wpath.read_bytes())["cases"]
    groups = []
    for client in ("field", "conventional"):
        trace, metrics = get_trace(PRIOR / (client + ".json.gz"), operation["arms"][client]["receipt_sha256"], wpath)
        for group, metric in zip(trace["loads"], metrics, strict=True):
            rows = score_routes(cases, replies(trace, group))
            counts = summary(rows, ROUTES)
            if counts["model"]["correct"] != metric["quality_accepted"]:
                raise ValueError("Historical raw model score differs")
            groups.append({"client": client, "concurrency": group["concurrency"], "rows": rows, "routes": counts})
    all_rows = [r for group in groups for r in group["rows"]]
    return {"routes": summary(all_rows, ROUTES),
            "groups": [{"client": g["client"], "concurrency":g["concurrency"],
                        "correct":{r:g["routes"][r]["correct"] for r in ROUTES},
                        "changed_by_check":[r["id"] for r in g["rows"] if r["model"] != r["model_checked"]]}
                       for g in groups]}


def measured_costs(cases, returned):
    # One warmup. Rotate the order in each measurement round to reduce first-route bias.
    # Measure complete local batch construction and serialization, not online TTFT.
    routes = ["incumbent", "model_checked", "direct"]
    samples = {r: [] for r in routes}
    for i in range(31):
        for name in routes[i % 3:] + routes[:i % 3]:
            start = time.perf_counter_ns()
            for case in cases:
                brief = case["prompt"]
                if name == "incumbent":
                    result = direct_answer(brief)
                elif name == "direct":
                    result = compile_brief(brief)
                else:
                    proof = compile_brief(brief)
                    reply = returned[case["id"]]
                    result = None if reply is None else guard(proof, reply)
                json_text(result)
            elapsed = time.perf_counter_ns() - start
            if i:
                samples[name].append(elapsed)
    # A real recipient also pays for Python startup, input/output and re-opening.
    # This supplemental clock is a local CLI invocation, separate from service SLA.
    cold_us = []
    cold_correct = 0
    for case in cases:
        start = time.perf_counter_ns()
        child = subprocess.run([sys.executable, "-B", str(HERE / "intake.py")], input=case["prompt"],
                               encoding="utf-8", check=True, capture_output=True)
        receipt = json.loads(child.stdout)
        cold_correct += score(json_text(receipt["answer"]), case["expected"]) == "correct"
        cold_us.append((time.perf_counter_ns() - start) // 1000)
    return {"scope": "30 measured passes over all 12 briefs after one warmup; local process elapsed ns per batch including JSON serialization. Direct serializes its evidence too. Checked model operates on completed, already captured outputs.",
            "supplemental_cold_cli": {"scope": "12 new Python processes reading the brief on stdin through parent re-opening and scoring of stdout. No HTTP or model call.",
                                      "correct": cold_correct, "attempted": len(cases), "wall_us": cold_us,
                                      "p90_complete_us": sorted(cold_us)[(9*len(cold_us)+9)//10-1]},
            "workload_sha256": digest((HERE / "intake_workload.json").read_bytes()),
            "grammar_sha256": digest((HERE / "intake.py").read_bytes()),
            "median_batch_ns": {k: statistics.median(v) for k, v in samples.items()},
            "complete_operating_cost": None}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    options = ap.add_mutually_exclusive_group()
    options.add_argument("--check", action="store_true", help="Compare with the published outcome")
    options.add_argument("--timings", action="store_true", help="Observe new direct/guard clock readings")
    options.add_argument("--challenge", type=Path, help="Score additional independent briefs without inference")
    args = ap.parse_args()
    if args.challenge:
        data = json.loads(args.challenge.read_bytes())
        cases = data["cases"] if isinstance(data, dict) else data
        rows = score_routes(cases)
        result = {"routes": summary(rows, ("incumbent", "direct")), "cases": rows}
    else:
        result, (cases, returned) = fresh()
        if args.timings:
            result = measured_costs(cases, returned)
        else:
            result = {"grammar_sha256": digest((HERE / "intake.py").read_bytes()),
                      "fresh": result, "historical": historical()}
            challenge = (RECORDED / "independent_challenge.json").read_bytes()
            if digest(challenge) != CHALLENGE_SHA256:
                raise ValueError("The independently committed challenge changed")
            rows = score_routes(json.loads(challenge))
            result["independent_challenge"] = {"source_sha256": digest(challenge), "cases": rows,
                                               "routes": summary(rows, ("incumbent", "direct"))}
            if args.check:
                if result != json.loads((RECORDED / "result.json").read_bytes()):
                    raise SystemExit("Intake outcome differs from re-executed qualification")
                cost = (RECORDED / "route_costs.json").read_bytes()
                if digest(cost) != COST_OBSERVATION_SHA256:
                    raise SystemExit("Supplemental local clock observation changed")
                cold = json.loads(cost)["supplemental_cold_cli"]
                rank = (9 * len(cases) + 9) // 10
                if (len(cold["wall_us"]) != len(cases) or sorted(cold["wall_us"])[rank-1] != cold["p90_complete_us"]
                        or cold["correct"] != result["fresh"]["routes"]["direct"]["correct"]):
                    raise SystemExit("Cold CLI delivery observation disagrees")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
