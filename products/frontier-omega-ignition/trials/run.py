#!/usr/bin/env python3
"""Collect one prospectively registered public observation on a clean Git checkout."""
from __future__ import annotations

import argparse
from contextlib import contextmanager, nullcontext
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
REVIEW = HERE.parents[2]
PRODUCT_REPO = Path(os.environ.get("IGNITION_TRIAL_PRODUCT", REVIEW)).resolve()
PRODUCT = PRODUCT_REPO / "products/frontier-omega-ignition"
sys.path.insert(0, str(PRODUCT))
import qualify_live as hosted
from examples import compare_conventional as ordinary
from ignition import construction, delivery, evaluation
from ignition.controller import Controller
from ignition.provider import LocalProvider, ModelProvider
from ignition.store import Store, digest, runtime_source

FROZEN = "89f2196d552810bc56696a7f380ae66c55f8763a"
RECORDED_RESPONSE = "9bef7cd8787ba4397137da29dce7e4b450f70c31eb26dacfa8910a6c38bf42b3"
MODES = ("direct", "research", "adaptive")
CELLS = {f"{fixture}-{mode}": (fixture,mode,False) for fixture in ("integrity","migration") for mode in MODES}
CELLS.update({f"repair-{mode}": ("integrity",mode,True) for mode in ("adaptive","direct")})
CELLS["integrity-default"] = ("integrity","default",False)
CELLS.update({f"frozen-{fixture}": (fixture,"frozen",False) for fixture in ("integrity","migration")})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(root, *args):
    return subprocess.run(["git","-C",str(root),*args],check=True,stdout=subprocess.PIPE,
                          text=True,stderr=subprocess.DEVNULL).stdout.strip()


def sources(mode):
    code = hosted.checked_source()
    review = git(REVIEW,"rev-parse","HEAD")
    if (review != os.environ.get("EXPECTED_SOURCE",review)
            or git(REVIEW,"status","--porcelain","--untracked-files=all","--",str(HERE.relative_to(REVIEW)))
            or code != (FROZEN if mode == "frozen" else review)):
        raise ValueError("Exact-source study checkout mismatch")
    return {"product_revision":code, "experiment_revision":review, "python":sys.version.split()[0],
            "runtime_sha256":runtime_source(), "registration_sha256":sha(HERE/"REGISTRATION.md"),
            "driver_sha256":sha(Path(__file__)), "evaluator":evaluation.evaluator_identity()}


def assessment(result):
    if result is None:
        return None
    return {"status":result["status"], "case_count":len(result["cases"]),
            "candidate_cases_passed":sum(c["candidate_pass"] for c in result["cases"]),
            "reference_cases_passed":sum(c["reference_pass"] is True for c in result["cases"]),
            "failed_case_names":[c["name"] for c in result["cases"] if not c["candidate_pass"]],
            "contract_conforms":result.get("declared_program_conforms"),
            "comparison":result["comparison"], "telemetry_ns":result["telemetry_ns"],
            "receipt_sha256":result["receipt_sha256"]}


def planted(contract):
    program = copy.deepcopy(construction.build_view(contract)["definition"])
    program["manifest"][min(program["manifest"])] = "0"*64
    return {"kind":"manifest_audit", "program":program}


def conventional(contract):
    program = construction.build_view(contract)["definition"]
    return {"kind":"manifest_audit", "program":program}


def conventional_baseline(contract):
    spec = contract["spec"]
    name = "jq" if spec["kind"] == "record_migration" else "sha256sum"
    executable = shutil.which(name)
    if not executable:
        raise ValueError("Registered conventional executable absent")
    start = time.monotonic()
    cases = []
    for case in spec["cases"]:
        observed = (ordinary.conventional_migrate(case["input"],executable) if name=="jq" else
                    ordinary.conventional_audit(case["input"],spec["definition"]["manifest"],executable))
        expected = case["expected"] if "expected" in case else {"error":case["error"]}
        cases.append({"name":case["name"],"passed":observed==expected})
    return {"tool":name,"version":subprocess.check_output([executable,"--version"],text=True).splitlines()[0],
            "original_declared_cases":cases, "accepted_on_declared_cases":all(c["passed"] for c in cases),
            "wall_seconds":round(time.monotonic()-start,6),
            "scope":"Existing hand-authored conventional route and original declared cases; model-evaluator controls are reported separately."}


def known_historic_defect(contract):
    proposal = json.loads((HERE/"historical-integrity-proposal.json").read_bytes())
    if digest(proposal) != RECORDED_RESPONSE:
        raise ValueError("Recovered proposal does not match the original record")
    product = construction.build(contract,proposal)
    result = evaluation.evaluate(contract,product)
    measured = assessment(result)
    if (measured["status"] != "fail" or measured["candidate_cases_passed"] != 8
            or measured["reference_cases_passed"] != 9):
        raise ValueError("The recovered earlier failure did not reproduce")
    return {"recorded_model_response_sha256":RECORDED_RESPONSE,"recovered_proposal":proposal,
            "artifact_sha256":product["sha256"],"evaluation":measured}


class ObservedProvider:
    """The sole synthetic response is a labelled, intentionally rejected E intervention."""

    def __init__(self, actual, plant):
        self.actual, self.plant = actual, plant
        self.interventions = []

    def identity(self):
        return self.actual.identity()

    @property
    def receipts(self):
        return self.actual.receipts

    def propose(self, stage, payload):
        if self.plant is not None and stage == "construct" and not self.interventions:
            self.interventions.append({"stage":stage, "type":"preregistered synthetic defect",
                                       "proposal_sha256":digest(self.plant)})
            return self.plant
        return self.actual.propose(stage,payload)


def observe(cell, work, public, actual, record):
    fixture, mode, inject = CELLS[cell]
    fixture_path = PRODUCT/"examples"/(fixture+".json")
    example = json.loads(fixture_path.read_bytes())
    mission = example["mission"]
    contract = construction.freeze_contract(mission["construction_spec"])
    record.update(fixture=fixture, fixture_sha256=sha(fixture_path), strategy_intervention=mode,
                  contract_sha256=contract["sha256"], planted_defect=inject)
    record["conventional_baseline"] = conventional_baseline(contract)
    if mode != "frozen":
        mission["resources"].update(max_model_calls=4, max_repairs=1)
        if mode != "default":
            mission["resources"]["direct_method"] = "model"
        if mode not in {"adaptive","default"}:
            mission["resources"]["execution_strategy"] = mode
    if mode == "frozen" and fixture == "integrity":
        record["historical_exact_proposal_reproduction"] = known_historic_defect(contract)
    plant = planted(contract) if inject else None
    if inject:
        t0 = time.monotonic()
        bad = evaluation.evaluate(contract,construction.build(contract,plant))
        competent = evaluation.evaluate(contract,construction.build(contract,conventional(contract)))
        if bad["status"] != "fail" or not bad["comparison"]["reference_pass"] or competent["status"] != "pass":
            raise ValueError("Planted intervention was not independently confirmed")
        record.update(planted_assessment=assessment(bad),conventional_repair=assessment(competent),
                      interventional_check_seconds=round(time.monotonic()-t0,6))
    provider = ObservedProvider(actual,plant)
    store = Store(work/"missions")
    controller = Controller(store,provider_factory=lambda:provider)
    start = time.monotonic()
    run_id, revision = controller.create({"mission":mission,"sources":example["sources"],"request_id":"registered-"+cell})
    controller.advance(run_id,revision)
    state = store.get(run_id)
    calls = [{k:r[k] for k in hosted.PUBLIC_ROUTES if k in r} for r in actual.receipts]
    record.update(calls=calls, actual_local_model_calls=sum(c.get("application_model_calls",0) for c in calls),
                  synthetic_interventions=provider.interventions, mission_status=state["status"], stage=state["stage"],
                  tokens={k:sum(r["usage"][k] for r in calls) if calls and all(type((r.get("usage") or {}).get(k)) is int for r in calls) else None
                          for k in ("input_tokens","output_tokens")},
                  repair_calls=sum(c.get("stage")=="repair" for c in calls),
                  purpose_sha256=digest(mission["purpose"]),input_sha256=state["input_sha256"],
                  route=(state.get("routing") or {}).get("route"), method=(state.get("routing") or {}).get("method"), diagnostic=hosted.diagnostic(state,calls),
                  independent_evaluation=assessment(state.get("evaluation")), portable=None)
    research = state.get("research") or {}
    record["selection"] = {k:research.get(k) for k in ("decision","kind")}
    record["selection"]["candidate_count"] = len(research.get("candidates",[]))
    challenge = next((c["response"] for c in state["calls"].values() if c.get("stage")=="challenge"),{})
    decision = challenge.get("decision")
    if decision in ("build","defer","stop","incumbent"):
        record["selection"]["model_recommendation"] = decision
    record["attempts"] = [{k:a[k] for k in ("attempt","contract_sha256","proposal_sha256","artifact_sha256","receipt_sha256",
                                             "status","checks","passed_checks","repairable","comparison","elapsed_seconds")
                            if k in a} for a in state.get("construction_attempts",[])]
    # Untrusted prose stays in the private worker. A bounded known explanation may leave as a category.
    message = research.get("decision_reason")
    record["selection"]["reason_sha256"] = digest(message) if isinstance(message,str) else None
    rules = ("The selected route lacks usable attributable support or repeats another route.",
             "The incumbent decision did not select an existing solution.")
    if message in rules:
        record["selection"]["known_controller_gate"] = message
    if state.get("artifact") is not None:
        record["artifact_sha256"] = state["artifact"]["sha256"]
    if state.get("contract") is not None and state["contract"] != contract:
        raise ValueError("Frozen contract differs from original")
    if any(c.get("mode") != "local" or c.get("reported_model") != hosted.MODEL_ALIAS
           or c.get("application_model_calls") != 1 or c.get("status") != "completed"
           or not c.get("response_sha256") for c in calls) or (not calls and mode != "default"):
        raise ValueError("Model call provenance incomplete")
    if mode == "default" and (calls or record["method"] != "specialist"):
        raise ValueError("Default exact manifest used inference instead of the registered specialist")
    if inject and (len(provider.interventions) != 1 or record["repair_calls"] != 1):
        raise ValueError("Required independently confirmed repair intervention missing")
    if mode != "frozen" and record["route"] != ("research" if mode=="research" else "direct"):
        raise ValueError("Observed route differs from registered fixture")
    if state["status"] == "verified":
        if state.get("contract") != contract or record["independent_evaluation"]["status"] != "pass":
            raise ValueError("Verified status without frozen acceptance")
        # Exercise the full normal delivery guard, then publish a minimal public-fixture context.
        original = controller.deliver(run_id,revision)
        checked = hosted.check_portable(original,work)
        if checked["verified_exit"] or checked["example_exit"]:
            raise ValueError("Normal delivery failed recipient execution")
        bundle = delivery.export_bundle(contract,state["artifact"],state["evaluation"],
                   {"public_registered_cell":cell,"source":record["sources"],"model":record.get("model"),"calls":calls})
        folder = work/"public-recipient-check"
        folder.mkdir()
        checked = hosted.check_portable(bundle,folder)
        if checked["verified_exit"] or checked["example_exit"]:
            raise ValueError("Public recipient execution failed")
        (public/"recipient.zip").write_bytes(bundle)
        record.update(portable=checked,delivery_sha256=hashlib.sha256(bundle).hexdigest(),mission_verdict="ACCEPTED")
    elif state["status"] in {"deferred","failed","blocked","awaiting_contract"}:
        record["mission_verdict"] = "NOT_ACCEPTED"
    else:
        raise ValueError("Unexpected terminal state")
    record["mission_wall_seconds"] = round(time.monotonic()-start,6)


@contextmanager
def local_model(work,record):
    binary,weights = hosted.setup_model(work,record)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        port = sock.getsockname()[1]
    threads = hosted.available_threads()
    record.update(threads=threads,model=hosted.MODEL_ALIAS,model_revision=hosted.pinned.MODEL_REVISION)
    command = [str(binary),"-m",str(weights),"--alias",hosted.MODEL_ALIAS,"--host","127.0.0.1",
               "--port",str(port),"--ctx-size","32768","--threads",str(threads),"--threads-batch",str(threads),
               "--parallel","1","--n-gpu-layers","0","--seed","6144","--temp","0"]
    env = {"PATH":os.defpath,"LD_LIBRARY_PATH":str(binary.parent),"HOME":str(work),"LANG":"C.UTF-8","NO_PROXY":"127.0.0.1"}
    with (work/"private-server.log").open("wb") as log:
        server = subprocess.Popen(command,cwd=work,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log)
        try:
            hosted.wait_ready(server,port)
            yield LocalProvider("llama-cpp",hosted.MODEL_ALIAS,port,hosted.pinned.MODEL_SHA,
                                output_tokens=8192,timeout=600,schema_output=True)
        finally:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()


def public_summary(record):
    keys = ("cell","observation","mission_verdict","actions_run","actions_attempt","mission_status","stage",
            "fixture_sha256","contract_sha256","artifact_sha256","delivery_sha256","route","method",
            "actual_local_model_calls","repair_calls","synthetic_interventions","setup_wall_seconds",
            "mission_wall_seconds","study_wall_seconds","tokens","portable","diagnostic","selection",
            "error_class","obstruction_category","complete_cost_known","sources","attempts")
    summary = {key:record[key] for key in keys if key in record}
    for label in ("independent_evaluation","planted_assessment","conventional_repair"):
        result = record.get(label)
        if result:
            summary[label] = {k:result[k] for k in ("status","case_count","candidate_cases_passed",
                                                     "reference_cases_passed","contract_conforms","failed_case_names")}
            summary[label]["comparison"] = result["comparison"]["outcome"]
    if "historical_exact_proposal_reproduction" in record:
        summary["historical_match"] = record["historical_exact_proposal_reproduction"]["recorded_model_response_sha256"]
    baseline = record.get("conventional_baseline") or {}
    if baseline:
        summary["ordinary"] = {"version":baseline["version"],"passed":baseline["accepted_on_declared_cases"],
                               "case_count":len(baseline["original_declared_cases"]),"seconds":baseline["wall_seconds"]}
    summary["model_calls"] = [{k:r.get(k) for k in ("stage","status","wall_seconds","usage","response_sha256")}
                              for r in record.get("calls",[])]
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cell",choices=sorted(CELLS),required=True)
    parser.add_argument("--work",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    work,public = args.work.resolve(),args.output.resolve()
    if (any(p.exists() or p.is_relative_to(REVIEW) or p.is_relative_to(PRODUCT_REPO) for p in (work,public))
            or work.is_relative_to(public) or public.is_relative_to(work)):
        parser.error("Use separate fresh paths outside the checkouts")
    work.mkdir(mode=0o700,parents=True)
    public.mkdir(mode=0o700,parents=True)
    start = time.monotonic()
    record = {"protocol":"ignition/adaptive-trial/1", "cell":args.cell,"observation":"INCOMPLETE","mission_verdict":"UNAVAILABLE",
              "started_at":hosted.stamp(),"complete_cost_known":False,"unattended_human_interventions":0,
              "authorized_compute":"standard public-repository CPU","new_paid_services":0,
              "actions_run":os.environ.get("GITHUB_RUN_ID"),"actions_attempt":os.environ.get("GITHUB_RUN_ATTEMPT")}
    try:
        mode = CELLS[args.cell][1]
        record["sources"] = sources(mode)
        if mode == "default":
            record.update(model=None, model_revision=None, model_setup="No model process for native-specialist control")
        context = nullcontext(ModelProvider()) if mode=="default" else local_model(work,record)
        with context as model:
            record["setup_wall_seconds"] = round(time.monotonic()-start,6)
            observe(args.cell,work,public,model,record)
        if sources(mode) != record["sources"]:
            raise ValueError("Source changed during experiment")
        record["observation"] = "COMPLETE"
    except Exception as exc:
        record.update(observation="INCOMPLETE",mission_verdict="UNAVAILABLE",error_class=type(exc).__name__)
        approved = {"Exact-source study checkout mismatch","Recovered proposal does not match the original record",
                    "The recovered earlier failure did not reproduce","Registered conventional executable absent",
                    "Planted intervention was not independently confirmed","Frozen contract differs from original",
                    "Model call provenance incomplete","Default exact manifest used inference instead of the registered specialist",
                    "Required independently confirmed repair intervention missing","Observed route differs from registered fixture",
                    "Verified status without frozen acceptance","Normal delivery failed recipient execution",
                    "Public recipient execution failed","Unexpected terminal state","Source changed during experiment"}
        if type(exc) is ValueError and str(exc) in approved:
            record["obstruction_category"] = str(exc)
        (public/"recipient.zip").unlink(missing_ok=True)
        if not os.environ.get("GITHUB_ACTIONS"):
            raise
    finally:
        record.update(finished_at=hosted.stamp(),study_wall_seconds=round(time.monotonic()-start,6))
        (public/"receipt.json").write_text(json.dumps(record,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
    print("IGNITION_OBSERVATION "+json.dumps(public_summary(record),separators=(",",":"),ensure_ascii=True))
    return 0 if record["observation"]=="COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
