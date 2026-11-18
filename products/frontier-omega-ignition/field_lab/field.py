#!/usr/bin/env python3
"""Capture bounded service replays and decide the registered operating scope."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import http.client
import json
from pathlib import Path
import platform
import subprocess
import time

from capture import attempt, micros, native_tokens, read_events
from protocol import accepted, decode, FIXTURE_TOKENIZER, HERE, read_workload, require, sha, validate_authority


def percentile(values, tenths):
    return sorted(values)[(tenths * len(values) + 9) // 10 - 1] if values else None


def summary(w, authority, load, turns, tokenizations):
    firsts, finishes, rates = [], [], []
    events = []
    n_ok = n_quality = failed_firsts = attempts = 0
    for turn, case in zip(turns, w["cases"], strict=True):
        calls = turn["attempts"]
        attempts += len(calls)
        failed_firsts += not read_events(calls[0], authority["model"])[2]
        for call in calls:
            events.extend([(call["start_us"], 1), (call["end_us"], -1)])
        text, first, complete, _ = read_events(calls[-1], authority["model"])
        origin = calls[0]["start_us"]
        if first is not None:
            firsts.append(first - origin)
        if not complete:
            continue
        n_ok += 1
        n_quality += accepted(text, case["expected"])
        turn_us = calls[-1]["end_us"] - origin
        finishes.append(turn_us)
        key = sha(text.encode())
        ids = tokenizations.get(key)
        if ids is not None and turn_us > 0:
            rates.append(len(ids) * 1_000_000_000 // turn_us)
    active = peak = 0
    for _, change in sorted(events):
        active += change
        peak = max(peak, active)
    count = len(turns)
    p90_first = percentile(firsts, 9)
    p90_turn = percentile(finishes, 9)
    p10_rate = percentile(rates, 1)
    limits = w["thresholds"]
    quality = n_quality >= limits["required_quality_fraction"] * count
    reliability = (count - failed_firsts) >= limits["required_first_attempt_completion_fraction"] * count
    performance = (len(firsts) == len(finishes) == len(rates) == count and peak == load
                   and p90_first <= limits["p90_first_visible_ms"] * 1000
                   and p90_turn <= limits["p90_turn_ms"] * 1000
                   and p10_rate >= limits["p10_delivered_tokens_per_turn_second"] * 1000)
    return {"concurrency":load, "peak_in_flight":peak, "requests":count, "attempts":attempts,
            "transport_complete":n_ok, "quality_accepted":n_quality, "first_attempt_failures":failed_firsts,
            "visible_count":len(firsts), "rate_count":len(rates),
            "p90_first_visible_ms":None if p90_first is None else p90_first / 1000,
            "p90_turn_ms":None if p90_turn is None else p90_turn / 1000,
            "p10_delivered_tokens_per_turn_second":None if p10_rate is None else p10_rate / 1000,
            "meets_task_quality":quality, "meets_first_attempt_reliability":reliability,
            "meets_interactive_performance":performance,
            "decision":"accept-registered-replay" if quality and reliability and performance else "withhold"}


def child_cpu_us():
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        return round((usage.ru_utime + usage.ru_stime) * 1_000_000)
    except ImportError:
        return None


def run(w, digest, a, route, fixture_reset=None):
    fixture = fixture_reset is not None
    port = validate_authority(a, w, digest, fixture)
    start = micros()
    cpu_start = time.process_time_ns()
    child_start = child_cpu_us()
    raw = {"schema":1, "started_utc":datetime.now(timezone.utc).isoformat(), "workload_sha256":digest,
           "source":{name:sha((HERE / name).read_bytes()) for name in
                     ("protocol.py","capture.py","field.py","fixture_server.py","REGISTRATION.md")},
           "target":{k:a[k] for k in ("scope","target","model","model_sha256","runtime_sha256","hardware",
                                      "configuration","tokenizer")},
           "authority_sha256":sha(json.dumps(a, sort_keys=True,separators=(",",":")).encode()),
           "route":route, "loads":[], "tokenizations":{},
           "client_environment":{"python":platform.python_version(), "system":platform.system(),
                                 "architecture":platform.machine()}}
    if route == "conventional":
        raw["client_environment"]["curl"] = subprocess.check_output(["curl","-q","--version"],text=True).splitlines()[0]
    for load in w["concurrency"]:
        if fixture:
            fixture_reset()
        def replay(case):
            calls = []
            for _ in range(w["max_attempts_per_request"]):
                call = attempt(port, a, w, case, route, start)
                calls.append(call)
                if call["http"] not in {429,503} or call["events"] or call["error"]:
                    break
            return {"id":case["id"], "attempts":calls}
        with ThreadPoolExecutor(max_workers=load) as pool:
            turns = list(pool.map(replay, w["cases"]))
        raw["loads"].append({"concurrency":load, "turns":turns})

    # Retokenization is outside timed service turns so a benchmarking aid cannot saturate the model.
    tok_start = micros()
    lookup = raw["tokenizations"]
    token_queries = 0
    reported_prompt = reported_output = usage_pairs = 0
    for group in raw["loads"]:
        for turn in group["turns"]:
            for call in turn["attempts"]:
                text, _, _, usage = read_events(call, a["model"])
                if usage and "prompt_tokens" in usage and "completion_tokens" in usage:
                    usage_pairs += 1
                    reported_prompt += usage["prompt_tokens"]
                    reported_output += usage["completion_tokens"]
                if not text or sha(text.encode()) in lookup:
                    continue
                key = sha(text.encode())
                if fixture:
                    lookup[key] = list(text.encode())
                else:
                    token_queries += 1
                    try:
                        lookup[key] = native_tokens(port, text, w["attempt_timeout_s"], w["max_response_bytes"])
                    except (OSError, ValueError, TypeError, KeyError, http.client.HTTPException):
                        lookup[key] = None
    tokenization_us = micros() - tok_start
    raw["metrics"] = [summary(w, a, g["concurrency"], g["turns"], lookup) for g in raw["loads"]]
    child_end = child_cpu_us()
    raw["cost"] = {"client_wall_us":micros()-start, "client_process_cpu_us":(time.process_time_ns()-cpu_start)//1000,
                   "post_replay_tokenizer_us":tokenization_us, "tokenizer_http_queries":token_queries,
                   "usage_complete_attempts":usage_pairs, "reported_prompt_tokens_on_those_attempts":reported_prompt if usage_pairs else None,
                   "reported_completion_tokens_on_those_attempts":reported_output if usage_pairs else None,
                   "capture_process_includes_fixture_server_threads":fixture,
                   "child_cpu_us":None if child_end is None else child_end - child_start,
                   "external_inference_server_cpu_us":None,
                   "all_in_cost":None}
    raw["operating_scope"] = {"registered_replay":"see each load", "availability":None,
                              "operating_resource_fit":None, "economically_competitive":None,
                              "production_access":None,"production_decision":"defer"}
    return raw


def save(path, obj, *, compact=False):
    # A new file only. Local captures can contain complete private responses.
    import os
    with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w", encoding="utf-8") as out:
        json.dump(obj, out, ensure_ascii=False, allow_nan=False, indent=None if compact else 2,
                  separators=(",",":") if compact else None)
        out.write("\n")


def fixtures(workfile, outdir):
    from fixture_server import serve
    from verify import verify
    w, digest = read_workload(workfile)
    outdir.mkdir(exist_ok=False, parents=True, mode=0o700)
    rows, receipts = [], []
    (outdir / "evidence").mkdir(mode=0o700)
    for target in ("nominal", "adverse"):
        for route in ("field", "conventional"):
            with serve(target) as (port, seen):
                code_sha = sha((HERE / "fixture_server.py").read_bytes())
                a = {"schema":1, "scope":"fixture", "target":target, "base_url":f"http://127.0.0.1:{port}",
                     "model":"scripted-service-v1", "model_sha256":code_sha, "runtime_sha256":code_sha,
                     "hardware":f"loopback CPU {platform.machine()}", "configuration":"ThreadingHTTPServer; deterministic public grammar and fault schedule",
                     "workload_sha256":digest, "max_concurrency":max(w["concurrency"]),
                     "max_attempts":len(w["cases"])*len(w["concurrency"])*w["max_attempts_per_request"],
                     "tokenizer":FIXTURE_TOKENIZER,"locally_owned_no_forwarding":True}
                receipt = run(w, digest, a, route, seen.clear)
            relative = f"evidence/{target}-{route}.json"
            path = outdir / relative
            save(path, receipt, compact=True)
            verify_start = micros()
            verify_cpu = time.process_time_ns()
            certified = verify(workfile, path)
            receipts.append({"path":relative, "sha256":sha(path.read_bytes()),
                             "verification_wall_us":micros()-verify_start,
                             "verification_process_cpu_us":(time.process_time_ns()-verify_cpu)//1000})
            rows.extend({"target":target,"route":route, **row} for row in certified)
    public = {"schema":1,"mission":w["mission"],"scope":"actual HTTP loopback measurements on scripted public fixtures",
              "field_decision":"defer","workload_sha256":digest,"tokenizer":FIXTURE_TOKENIZER,
              "operating_obstacles":["representative field traffic","matching model/runtime and hardware access",
                                     "long-run availability","complete operating cost"],
              "verifier_sha256":sha((HERE / "verify.py").read_bytes()), "receipts":receipts,"arms":rows}
    save(outdir / "PUBLIC.json", public)
    return public


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("run", "fixture"):
        cmd = sub.add_parser(action)
        cmd.add_argument("--workload",type=Path,default=HERE / "workload.json")
        cmd.add_argument("--output",type=Path,required=True)
        if action == "run":
            cmd.add_argument("--authority",type=Path,required=True)
            cmd.add_argument("--route",choices=("field","conventional"),default="field")
    args = parser.parse_args()
    if args.action == "fixture":
        result = fixtures(args.workload, args.output)
        print(f"{len(result['arms'])} independently replayed fixture/load/client observations")
    else:
        w, digest = read_workload(args.workload)
        a = decode(args.authority.read_bytes())
        validate_authority(a,w,digest)
        # Reserve the destination before any real inference access. A failed write or
        # pre-existing path must not spend another run while discarding its receipt.
        require(not args.output.exists() and args.output.parent.is_dir(), "choose a fresh file in an existing directory")
        import os
        with os.fdopen(os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as out:
            result = run(w, digest, a, args.route)
            json.dump(result,out,ensure_ascii=False,allow_nan=False,separators=(",",":"))
            out.write("\n")
        print(json.dumps(result["metrics"], ensure_ascii=False))


if __name__ == "__main__":
    main()
