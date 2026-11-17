#!/usr/bin/env python3
"""Run or recheck a registered public assisted exercise; never send a model API call."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import tempfile

import run

IDENTITY = ("OpenAI Codex in ChatGPT Work", "GPT-6 family; precise backend revision unreported")


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+"\n")


def setup(exercise,workspace):
    fixture_path = run.PRODUCT/"examples"/(exercise+".json")
    source = json.loads(fixture_path.read_bytes())
    source["mission"]["resources"].update(execution_strategy="direct",direct_method="model",max_model_calls=4,max_repairs=1)
    store = run.Store(workspace/"assisted-mission")
    ctrl = run.Controller(store,assisted=IDENTITY)
    return fixture_path,source,store,ctrl


def start(exercise,workspace):
    workspace.mkdir(parents=True,exist_ok=False)
    fixture,example,store,controller = setup(exercise,workspace)
    mid,version = controller.create({"mission":example["mission"],"sources":example["sources"],"request_id":"assisted-trial-"+exercise})
    controller.advance(mid,version)
    state = store.get(mid)
    if state["status"] != "awaiting_model" or state["handoff"]["stage"]!="construct":
        raise ValueError("Expected a real pending direct construction request")
    write(workspace/"session.json",{"exercise":exercise,"mission_id":mid,"revision":version,
                                  "fixture_sha256":run.sha(fixture),"started_at":run.hosted.stamp()})
    return state["handoff"]


def submit(workspace,request_sha,answer,output, *, replay=False):
    if output.exists():
        raise ValueError("Use a new receipt path")
    session = json.loads((workspace/"session.json").read_bytes())
    fixture,example,store,controller = setup(session["exercise"],workspace)
    mid,revision = session["mission_id"],session["revision"]
    before = store.get(mid)
    pending = before.get("handoff") or {}
    if pending.get("stage") != "construct" or pending.get("sha256") != request_sha:
        raise ValueError("Response is not bound to this pending exchange")
    if run.sha(fixture) != session["fixture_sha256"]:
        raise ValueError("Public fixture changed")
    controller.intervene(mid,revision,"respond",{"sha256":request_sha,"response":answer})
    controller.advance(mid,revision)
    state = store.get(mid)
    calls = run.hosted.compact_calls(state)
    contract = run.construction.freeze_contract(example["mission"]["construction_spec"])
    if state.get("contract") != contract:
        raise ValueError("Frozen contract identity mismatch")
    package = None
    if state["status"] == "verified":
        bundle = controller.deliver(mid,revision)
        package = run.hosted.check_portable(bundle,workspace)
        if package["verified_exit"] or package["example_exit"]:
            raise ValueError("Recipient check failed")
    has_exchange = any(c.get("mode")=="manual" and c.get("request_sha256")==request_sha
                       and c.get("response_sha256")==run.digest(answer) and c.get("application_model_calls")==0
                       for c in calls)
    if not has_exchange:
        raise ValueError("Reviewed-exchange evidence missing")
    ended = run.hosted.stamp()
    # Content identities are separate from the local runtime identity (which also binds the Python patch release).
    code = run.PRODUCT/"ignition"
    binding = {p.name:run.sha(p) for p in sorted(code.glob("*.py"))}
    receipt = {"protocol":"ignition/included-assisted/1","mode":"REPRODUCED" if replay else "LIVE_ASSISTED",
               "exercise":session["exercise"],"mission_verdict":"ACCEPTED" if package else "NOT_ACCEPTED",
               "provider":state["provider"],"exact_backend_independently_attested":False,
               "fixture_sha256":session["fixture_sha256"],"application_sources_sha256":run.digest(binding),
               "application_source_files":binding,"runtime_sha256":state["runtime"],
               "contract_sha256":contract["sha256"],"request_sha256":request_sha,
               "answer_sha256":run.digest(answer),"answer":answer,"calls":calls,
               "started_at":session["started_at"],"finished_at":ended,
               "exchange_wall_seconds":(datetime.fromisoformat(ended)-datetime.fromisoformat(session["started_at"])).total_seconds(),
               "model_only_latency_seconds":None,"model_token_usage":None,"complete_cost_known":False,
               "operator_assisted":True,"prior_public_fixtures_known":True,"accepted_recipient":package,
               "independent_evaluation":run.assessment(state.get("evaluation")),
               "artifact_sha256":(state.get("artifact") or {}).get("sha256")}
    write(output,receipt)
    print(json.dumps({k:receipt[k] for k in ("mode","exercise","mission_verdict","answer_sha256","artifact_sha256")}))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    s=p.add_subparsers(dest="action",required=True)
    op=s.add_parser("open"); op.add_argument("exercise",choices=("integrity","migration")); op.add_argument("workspace",type=Path)
    op=s.add_parser("submit"); op.add_argument("workspace",type=Path); op.add_argument("request_sha256"); op.add_argument("answer",type=Path); op.add_argument("output",type=Path)
    op=s.add_parser("reproduce"); op.add_argument("record",type=Path); op.add_argument("output",type=Path)
    args=p.parse_args()
    if args.action=="open":
        print(json.dumps(start(args.exercise,args.workspace),ensure_ascii=False))
    elif args.action=="submit":
        submit(args.workspace,args.request_sha256,json.loads(args.answer.read_bytes()),args.output)
    else:
        original=json.loads(args.record.read_bytes())
        if original.get("protocol")!="ignition/included-assisted/1" or original.get("mode")!="LIVE_ASSISTED" or original["exercise"] not in ("integrity","migration"):
            raise ValueError("Expected a registered public assisted source receipt")
        with tempfile.TemporaryDirectory() as root:
            session=Path(root)/"session"
            req=start(original["exercise"],session)
            submit(session,req["sha256"],original["answer"],args.output,replay=True)
        reproduced=json.loads(args.output.read_bytes())
        for field in ("fixture_sha256","contract_sha256","answer_sha256","artifact_sha256","mission_verdict"):
            if reproduced[field]!=original[field]:
                raise ValueError("Reproduced outcome differs: "+field)


if __name__=="__main__":
    main()
