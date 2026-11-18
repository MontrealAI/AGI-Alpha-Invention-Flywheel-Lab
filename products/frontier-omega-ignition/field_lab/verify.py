#!/usr/bin/env python3
"""Independent wire-to-SQL adjudication. No endpoint or inference needed for offline replay."""
from __future__ import annotations

import argparse
from decimal import Decimal
import hashlib
import http.client
import json
from pathlib import Path
import sqlite3

from protocol import decode, FIXTURE_TOKENIZER, HERE, NATIVE_TOKENIZER, read_workload, require, validate_authority


def digest(b):
    return hashlib.sha256(b).hexdigest()


def comparison_value(value):
    if type(value) is dict:
        return ("object", sorted((key,comparison_value(v)) for key,v in value.items()))
    if type(value) is list:
        return ("list", [comparison_value(v) for v in value])
    if type(value) in (int,float,Decimal):
        return ("number",Decimal(str(value)))
    return (type(value).__name__,value)


def canonical(data):
    def reject(pairs):
        obj = dict(pairs)
        if len(obj) != len(pairs):
            raise ValueError("ambiguous JSON")
        return obj

    def nonfinite(_):
        raise ValueError("non-finite JSON")

    parsed = json.loads(data,parse_int=Decimal,parse_float=Decimal,object_pairs_hook=reject,parse_constant=nonfinite)
    return comparison_value(parsed)

def parse_wire(call, alias):
    start, end = call["start_us"], call["end_us"]
    require(type(start) is int and type(end) is int and 0 <= start < end, "invalid attempt bounds")
    require(call["http"] is None or type(call["http"]) is int and 100 <= call["http"] <= 599,"invalid HTTP status")
    require(type(call["sse"]) is bool and call["error"] in {None,"client-or-stream-error","response-budget"},
            "unknown transport disposition")
    frames = call["events"]
    require(type(frames) is list, "missing wire frames")
    require(not frames or call["sse"] and call["http"] == 200, "frames on an unadmitted HTTP response")
    previous = start
    # Validate all observed clocks, even if an earlier frame has invalid scientific content.
    for f in frames:
        require(type(f) is list and len(f)==2 and type(f[0]) is int and previous <= f[0] <= end
                and type(f[1]) is str, "frame timestamp or data mismatch")
        previous = f[0]
    pieces = []
    first = None
    state = "stream"
    usage = None
    stream_id = None
    for when, wire in frames:
        try:
            if wire == "[DONE]":
                if state != "stopped":
                    state = "invalid"
                    break
                state = "done"
                continue
            obj = decode(wire)
            if obj.get("model") != alias or state == "done" or "error" in obj:
                state = "invalid"
                break
            if "id" in obj:
                if type(obj["id"]) is not str or stream_id is not None and obj["id"] != stream_id:
                    state = "invalid"
                    break
                stream_id = obj["id"]
            if obj.get("usage") is not None:
                if type(obj["usage"]) is not dict:
                    state = "invalid"
                    break
                usage = {k:n for k,n in obj["usage"].items() if k in {"prompt_tokens","completion_tokens"}
                         and type(n) is int and n >= 0}
            choices = obj["choices"]
            if choices == [] and state == "stopped" and usage is not None:
                continue
            if type(choices) is not list or len(choices)!=1 or state!="stream":
                state = "invalid"
                break
            ch, = choices
            if type(ch["index"]) is not int or ch["index"] or any(k in ch["delta"] for k in
                    ["tool_calls","refusal","function_call"]):
                state = "invalid"
                break
            part = ch["delta"].get("content")
            if part is not None and not isinstance(part, str):
                state = "invalid"
                break
            if part:
                pieces.append(part)
                if first is None:
                    first = when
            if ch.get("finish_reason") is not None:
                if ch["finish_reason"] != "stop":
                    state = "invalid"
                    break
                state = "stopped"
        except (TypeError, ValueError, KeyError, AttributeError, RecursionError):
            state = "invalid"
            break
    complete = bool(state=="done" and pieces and call["http"]==200 and call["sse"] and call["error"] is None)
    return "".join(pieces), first, complete, usage


def sql_score(db, c, thresholds):
    n, attempts, good_transport, quality, failures, n_first, n_rate = db.execute(
        "SELECT count(*),sum(attempts),sum(full),sum(correct),sum(failed_first),count(first_us),count(rate_milli) FROM turns"
    ).fetchone()
    peak = db.execute("""WITH timeline(tick,delta) AS (SELECT opened,1 FROM intervals UNION ALL
                           SELECT closed,-1 FROM intervals), active AS (SELECT SUM(delta) OVER
                           (ORDER BY tick,delta ROWS UNBOUNDED PRECEDING) AS n FROM timeline)
                         SELECT MAX(n) FROM active""").fetchone()[0]
    require(peak <= c, "actual concurrency exceeded registered bound")
    def quantile(col, decile):
        return db.execute(f"""WITH ranked AS (SELECT {col} AS val, ROW_NUMBER() OVER (ORDER BY {col}) AS i,
                 COUNT(*) OVER () AS n FROM turns WHERE {col} IS NOT NULL)
                 SELECT val FROM ranked WHERE i=(?*n+9)/10""",(decile,)).fetchone()
    first, finish, rate = (quantile(k,q) for k,q in (("first_us",9),("turn_us",9),("rate_milli",1)))
    first, finish, rate = (r[0] if r is not None else None for r in (first,finish,rate))
    perf = (good_transport == n_first == n_rate == n and peak == c and
            first <= 1000*thresholds["p90_first_visible_ms"] and finish <= 1000*thresholds["p90_turn_ms"]
            and rate >= 1000*thresholds["p10_delivered_tokens_per_turn_second"])
    quality_met = quality >= thresholds["required_quality_fraction"]*n
    reliable = n - failures >= thresholds["required_first_attempt_completion_fraction"]*n
    return {"concurrency":c,"peak_in_flight":peak,"requests":n,"attempts":attempts,"transport_complete":good_transport,
            "quality_accepted":quality,"first_attempt_failures":failures,"visible_count":n_first,"rate_count":n_rate,
            "p90_first_visible_ms":first/1000 if first is not None else None,
            "p90_turn_ms":finish/1000 if finish is not None else None,
            "p10_delivered_tokens_per_turn_second":rate/1000 if rate is not None else None,
            "meets_task_quality":quality_met,"meets_first_attempt_reliability":reliable,
            "meets_interactive_performance":perf,
            "decision":"accept-registered-replay" if quality_met and reliable and perf else "withhold"}


def verify(workfile, path, retokenize_authority=None):
    w, wsha = read_workload(workfile)
    receipt = decode(Path(path).read_bytes())
    require(receipt["schema"] == 1 and receipt["workload_sha256"] == wsha, "frozen workload mismatch")
    names = {"protocol.py","capture.py","field.py","fixture_server.py","REGISTRATION.md"}
    require(receipt["source"] == {n:digest((HERE/n).read_bytes()) for n in names}, "capture source mismatch")
    a = receipt["target"]
    require(receipt["route"] in {"field","conventional"}, "unknown replay client")
    require(a["scope"] in {"fixture","public-synthetic-pilot","authorized-workload-pilot"} and
            a["tokenizer"] == (FIXTURE_TOKENIZER if a["scope"]=="fixture" else NATIVE_TOKENIZER), "invalid scope")
    for k in ("hardware","configuration","target","model"):
        require(isinstance(a[k],str) and a[k].strip(), "incomplete field identity")
    for k in ("model_sha256","runtime_sha256"):
        require(isinstance(a[k],str) and len(a[k])==64 and all(c in "0123456789abcdef" for c in a[k]), "invalid identity")
    if a["scope"]=="fixture":
        require(a["model_sha256"] == a["runtime_sha256"] == receipt["source"]["fixture_server.py"], "fixture identity")
    local_port = None
    if retokenize_authority is not None:
        approval = decode(Path(retokenize_authority).read_bytes())
        local_port = validate_authority(approval,w,wsha)
        require(all(a[k] == approval[k] for k in a), "retokenizer authority does not match the recorded system")
    require([g["concurrency"] for g in receipt["loads"]] == w["concurrency"], "load denominator changed")
    answers = []
    tokens = receipt["tokenizations"]
    observed_texts = {}
    prompt = output = usage_count = 0
    previous_load_end = 0
    for group in receipt["loads"]:
        turns = group["turns"]
        require([t["id"] for t in turns] == [c["id"] for c in w["cases"]], "request denominator changed")
        db = sqlite3.connect(":memory:")
        try:
            db.execute("CREATE TABLE turns(attempts,full,correct,failed_first,first_us,turn_us,rate_milli)")
            db.execute("CREATE TABLE intervals(opened,closed)")
            for t, case in zip(turns,w["cases"],strict=True):
                calls = t["attempts"]
                require(isinstance(calls,list) and 1 <= len(calls) <= w["max_attempts_per_request"], "attempt count")
                prior = None
                for i, call in enumerate(calls):
                    if prior is not None:
                        require(prior["end_us"] <= call["start_us"] and prior["http"] in {429,503}
                                and not prior["events"] and prior["error"] is None, "unauthorized retry")
                    text, first, complete, usage = parse_wire(call,a["model"])
                    if i==0:
                        first_failed = not complete
                        require(call["start_us"] >= previous_load_end, "overlapping workload groups")
                    if text:
                        observed_texts[digest(text.encode())] = text
                    if usage and set(usage) == {"prompt_tokens", "completion_tokens"}:
                        usage_count += 1
                        prompt += usage["prompt_tokens"]
                        output += usage["completion_tokens"]
                    # Recover the exact transmitted body from the frozen task, excluding its answer key.
                    body = {"model":a["model"],"stream":True,"stream_options":{"include_usage":True},
                            "temperature":0,"max_tokens":w["max_output_tokens"],"messages":[
                            {"role":"system","content":w["instruction"]},{"role":"user","content":case["prompt"]}]}
                    encoded = json.dumps(body,ensure_ascii=False).encode()
                    require(call["request_bytes"]==len(encoded) and call["request_sha256"]==digest(encoded),
                            "transmitted request identity mismatch")
                    db.execute("INSERT INTO intervals VALUES(?,?)",(call["start_us"],call["end_us"]))
                    prior = call
                require(len(calls)==w["max_attempts_per_request"] or calls[-1]["http"] not in {429,503}
                        or calls[-1]["error"] is not None, "missing registered retry")
                quality = False
                if complete:
                    try:
                        quality = canonical(text)==comparison_value(case["expected"])
                    except (RecursionError, ValueError, TypeError):
                        pass
                elapsed = calls[-1]["end_us"]-calls[0]["start_us"]
                ids = tokens.get(digest(text.encode()))
                rate = len(ids)*1_000_000_000//elapsed if complete and ids is not None else None
                db.execute("INSERT INTO turns VALUES(?,?,?,?,?,?,?)",
                           (len(calls),int(complete),int(quality),int(first_failed),
                            None if first is None else first-calls[0]["start_us"],elapsed if complete else None,rate))
            answers.append(sql_score(db,group["concurrency"],w["thresholds"]))
            previous_load_end = db.execute("SELECT MAX(closed) FROM intervals").fetchone()[0]
        finally:
            db.close()
    require(tokens.keys() == observed_texts.keys(), "missing or unrelated tokenization")
    for key,text in observed_texts.items():
        ids = tokens[key]
        require(ids is None or type(ids) is list and all(type(i) is int and i>=0 for i in ids), "invalid token IDs")
        if a["scope"]=="fixture":
            require(ids == list(text.encode()), "fixture tokenizer disagrees")
        if local_port is not None:
            # Optional direct repeat against separately verified GGUF/runtime identities.
            conn = http.client.HTTPConnection("127.0.0.1",local_port,timeout=w["attempt_timeout_s"])
            try:
                conn.request("POST","/tokenize",json.dumps({"content":text,"add_special":False,"parse_special":False}),
                             {"Content-Type":"application/json"})
                res = conn.getresponse()
                result = res.read(w["max_response_bytes"]+1)
                require(res.status==200 and len(result)<=w["max_response_bytes"] and decode(result)["tokens"]==ids,
                        "native tokenizer did not reproduce IDs")
            finally:
                conn.close()
    require(canonical(json.dumps(receipt["metrics"])) == canonical(json.dumps(answers)),
            "producer decision or metrics disagree with wire/SQL replay")
    cost = receipt["cost"]
    for k in ("client_wall_us","client_process_cpu_us","post_replay_tokenizer_us"):
        require(type(cost[k]) is int and cost[k] >= 0, "invalid duration")
    require(cost["capture_process_includes_fixture_server_threads"] is (a["scope"] == "fixture")
            and cost["external_inference_server_cpu_us"] is None
            and (cost["child_cpu_us"] is None or type(cost["child_cpu_us"]) is int and cost["child_cpu_us"]>=0),
            "incorrect computational cost scope")
    require(cost["client_wall_us"] >= previous_load_end and cost["client_wall_us"] >= cost["post_replay_tokenizer_us"]
            and cost["tokenizer_http_queries"] == (0 if a["scope"]=="fixture" else len(tokens))
            and cost["usage_complete_attempts"] == usage_count
            and cost["reported_prompt_tokens_on_those_attempts"] == (prompt if usage_count else None)
            and cost["reported_completion_tokens_on_those_attempts"] == (output if usage_count else None)
            and cost["all_in_cost"] is None, "cost scope mismatch")
    require(receipt["operating_scope"] == {"registered_replay":"see each load", "availability":None,
            "operating_resource_fit":None, "economically_competitive":None, "production_access":None,
            "production_decision":"defer"}, "unsupported operating conclusion")
    return answers


def verify_public(workfile, public_path):
    projection = decode(Path(public_path).read_bytes())
    w, worksha = read_workload(workfile)
    require(projection["schema"] == 1 and projection["workload_sha256"] == worksha
            and projection["mission"] == w["mission"] and projection["field_decision"] == "defer"
            and projection["scope"] == "actual HTTP loopback measurements on scripted public fixtures"
            and projection["tokenizer"] == FIXTURE_TOKENIZER
            and projection["verifier_sha256"] == digest(Path(__file__).read_bytes()), "public identity mismatch")
    require(projection["operating_obstacles"] == ["representative field traffic","matching model/runtime and hardware access",
            "long-run availability","complete operating cost"], "operating evidence mismatch")
    arms = []
    files = projection["receipts"]
    expected = [(t,r) for t in ("nominal","adverse") for r in ("field","conventional")]
    require(len(files)==len(expected), "public capture denominator")
    for spec,(target,route) in zip(files,expected,strict=True):
        rel = "evidence/" + target + "-" + route + ".json"
        require(spec["path"] == rel, "unexpected public receipt path")
        path = Path(public_path).parent / rel
        data = path.read_bytes()
        obj = decode(data)
        require(spec["sha256"] == digest(data) and obj["route"] == route and obj["target"]["target"] == target,
                "public capture identity mismatch")
        arms.extend({"target":target,"route":route,**row} for row in verify(workfile,path))
    require(canonical(json.dumps(arms)) == canonical(json.dumps(projection["arms"])),
            "public results disagree with independent reference")
    return arms


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workload",type=Path,default=HERE/"workload.json")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--receipt",type=Path)
    source.add_argument("--public",type=Path)
    parser.add_argument("--retokenize-authority",type=Path)
    args = parser.parse_args()
    if args.public:
        if args.retokenize_authority:
            parser.error("--retokenize-authority requires --receipt")
        rows = verify_public(args.workload,args.public)
    else:
        rows = verify(args.workload,args.receipt,args.retokenize_authority)
    print(json.dumps(rows,indent=2))
