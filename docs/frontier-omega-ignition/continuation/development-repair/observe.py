"""One new conditional model repair, one independent conventional control; public fixtures only."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0,str(ROOT/"products/frontier-omega-ignition/trials"))
import run

ORIGINAL = "4719005c957e53716ccd3f328688d8a9c40ee4cc"
PROPOSAL = "9353460cae209c5ee2e7aa43d9b45bcc93fa77136c8743391cb9ffa106e3ed2e"
CONTRACT = "17e1dcf5c5f062a89db070dda03e6df21c6965bf7dbb5b7dff06e62803cf057d"
EVALUATOR = "50a13c7a52aca4ddaed813705f64bfe1f8767b520da5f75a3f8b32451fe78a41"


def leaves(item):
    if isinstance(item,dict):
        return set().union(*(leaves(v) for v in item.values())) if item else set()
    if isinstance(item,list):
        return set().union(*(leaves(v) for v in item)) if item else set()
    return {item} if isinstance(item,str) else set()


class Seeded(run.ObservedProvider):
    def __init__(self,actual,seed,spec):
        super().__init__(actual,seed)
        disclosed = leaves(spec["definition"])
        self.private = leaves(spec["cases"]) - disclosed
        self.private.update(run.digest(c["input"]) for c in spec["cases"])
        self.feedback_digest = None

    def propose(self,stage,payload):
        if stage=="repair":
            if self.feedback_digest is not None:
                raise ValueError("Duplicate repair call")
            feedback=payload.get("verified_failure") or {}
            if (len(self.interventions)!=1 or not feedback or self.private.intersection(leaves(feedback))):
                raise ValueError("Visible feedback boundary failed")
            if not any("development" in k and k!="failed_check_counts" for k in feedback):
                raise ValueError("No separate public development diagnostics")
            self.feedback_digest=run.digest(feedback)
        elif stage!="construct" or self.interventions:
            raise ValueError("Unexpected model stage")
        return super().propose(stage,payload)


def check_recipient(controller,mid,revision,work,output):
    data = controller.deliver(mid,revision)
    receipt = run.hosted.check_portable(data,work)
    if receipt["verified_exit"] or receipt["example_exit"]:
        raise ValueError("Recipient rejected")
    # Publish a bounded context separately from the complete source-matched private delivery.
    state = controller.store.get(mid)
    safe = run.delivery.export_bundle(state["contract"],state["artifact"],state["evaluation"],
                                     {"study":"conditional-development-repair","source":run.hosted.checked_source(),
                                      "cell":work.name,"contract_sha256":CONTRACT})
    folder=work/"public-copy";folder.mkdir()
    checked=run.hosted.check_portable(safe,folder)
    if checked!=receipt:
        raise ValueError("Public recipient differs")
    path=output/(work.name+".zip")
    path.write_bytes(safe)
    return {**checked,"public_zip_sha256":run.sha(path)}


def mission(example,method,model,work,output):
    import copy
    start=time.monotonic()
    accepted=copy.deepcopy(example["mission"])
    accepted["resources"].update(execution_strategy="direct",direct_method=method,max_model_calls=2,max_repairs=1)
    if method=="specialist":
        accepted["authority"].update(local_model=False,assisted_model=False)
    store=run.Store(work/"missions")
    ctrl=run.Controller(store,provider_factory=lambda:model)
    mid,v=ctrl.create({"mission":accepted,"sources":example["sources"],"request_id":"new-conditional-"+method})
    ctrl.advance(mid,v)
    state=store.get(mid)
    receipt={"mission_status":state["status"],"route":state.get("routing"),"portable":None,
             "attempts":[{k:a[k] for k in ("attempt","proposal_sha256","status","checks","passed_checks","receipt_sha256") if k in a}
                         for a in state.get("construction_attempts",[])],
             "evaluation":run.assessment(state.get("evaluation"))}
    receipt["route"]={k:(receipt["route"] or {}).get(k) for k in ("route","method")}
    if state.get("contract") and state["contract"]["sha256"]!=CONTRACT:
        raise ValueError("Contract identity changed")
    if state["status"]=="verified":
        receipt["portable"]=check_recipient(ctrl,mid,v,work,output)
    receipt["accepted"]=bool(receipt["portable"])
    receipt["elapsed_seconds"]=round(time.monotonic()-start,6)
    return receipt


def execute(work,output,record):
    expected=os.environ.get("EXPECTED_SOURCE")
    source=run.hosted.checked_source()
    if ((expected and source!=expected) or run.git(ROOT,"status","--porcelain","--",str(HERE.relative_to(ROOT)),
            ".github/workflows/frontier-ignition-development-feedback.yml")):
        raise ValueError("Unbound source")
    fixture=run.PRODUCT/"examples/migration.json"
    example=json.loads(fixture.read_bytes())
    contract=run.construction.freeze_contract(example["mission"]["construction_spec"])
    seed=json.loads((HERE/"rejected-proposal.json").read_bytes())
    if run.digest(seed)!=PROPOSAL or contract["sha256"]!=CONTRACT or run.evaluation.evaluator_identity()["evaluation.py"]!=EVALUATOR:
        raise ValueError("Registered identities differ")
    old=run.assessment(run.evaluation.evaluate(contract,run.construction.build(contract,seed)))
    if old["status"]!="fail" or old["candidate_cases_passed"]!=5 or old["case_count"]!=9:
        raise ValueError("Prior failure did not reproduce")
    record.update(source=source,fixture_sha256=run.sha(fixture),original_product=ORIGINAL,seed_response_sha256=PROPOSAL,
                  contract_sha256=CONTRACT,independent_evaluator_sha256=EVALUATOR,old_evaluation=old,
                  runtime_sha256=run.runtime_source(),driver_sha256=run.sha(Path(__file__)),
                  registration_sha256=run.sha(HERE/"REGISTRATION.md"),
                  conventional=run.conventional_baseline(contract))
    spec=example["mission"]["construction_spec"]
    folder=work/"specialist";folder.mkdir()
    record["specialist"]=mission(example,"specialist",run.ModelProvider(),folder,output)
    record["specialist"]["actual_model_calls"]=0
    t0=time.monotonic()
    with run.local_model(work,record) as actual:
        record["setup_seconds"]=round(time.monotonic()-t0,6)
        folder=work/"model";folder.mkdir()
        provider=Seeded(actual,seed,spec)
        record["model_result"]=mission(example,"model",provider,folder,output)
        calls=[{k:r[k] for k in run.hosted.PUBLIC_ROUTES if k in r} for r in actual.receipts]
        record.update(calls=calls,feedback_sha256=provider.feedback_digest)
        if len(provider.interventions)!=1 or not provider.feedback_digest or len(calls)!=1:
            raise ValueError("Registered intervention incomplete")
        c=calls[0]
        if (c.get("mode")!="local" or c.get("reported_model")!=run.hosted.MODEL_ALIAS or c.get("stage")!="repair"
                or c.get("application_model_calls")!=1 or c.get("status")!="completed" or not c.get("response_sha256")):
            raise ValueError("Model execution unverified")
        outcomes=record["model_result"]["attempts"]
        if not outcomes or outcomes[0].get("proposal_sha256")!=PROPOSAL or outcomes[0].get("passed_checks")!=5:
            raise ValueError("Runtime did not adjudicate the registered starting program")
    if run.hosted.checked_source()!=source:
        raise ValueError("Product changed")
    if not record["conventional"]["accepted_on_declared_cases"]:
        raise ValueError("Registered conventional check failed")
    record.update(observation="COMPLETE",mission_verdict="ACCEPTED" if record["model_result"]["accepted"] else "NOT_ACCEPTED")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work",required=True,type=Path);p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    work,out=a.work.resolve(),a.output.resolve()
    if (any(x.exists() or x.is_relative_to(ROOT) for x in (work,out)) or work.is_relative_to(out) or out.is_relative_to(work)):
        p.error("Fresh separate paths outside checkout required")
    work.mkdir(parents=True,mode=0o700);out.mkdir(parents=True,mode=0o700)
    r={"protocol":"ignition/conditional-development-repair/1","observation":"INCOMPLETE","mission_verdict":"UNAVAILABLE",
       "started_at":run.hosted.stamp(),"actions_run":os.environ.get("GITHUB_RUN_ID"),
       "actions_attempt":os.environ.get("GITHUB_RUN_ATTEMPT"),"complete_cost_known":False}
    t0=time.monotonic()
    try:
        execute(work,out,r)
    except Exception as err:
        r["error_type"]=type(err).__name__
        safe={"Registered identities differ","Prior failure did not reproduce","Visible feedback boundary failed",
              "No separate public development diagnostics","Registered intervention incomplete","Model execution unverified",
              "Runtime did not adjudicate the registered starting program","Registered conventional check failed"}
        if str(err) in safe:r["failure_category"]=str(err)
        if not os.environ.get("GITHUB_ACTIONS"):
            raise
    finally:
        if r["observation"]!="COMPLETE":
            for name in ("model.zip","specialist.zip"):
                (out/name).unlink(missing_ok=True)
        r.update(elapsed_seconds=round(time.monotonic()-t0,6),finished_at=run.hosted.stamp())
        (out/"receipt.json").write_text(json.dumps(r,indent=2,allow_nan=False)+"\n")
        print("IGNITION_DEVELOPMENT_RESULT "+json.dumps(r,separators=(",",":"),ensure_ascii=True))
    return 0 if r["observation"]=="COMPLETE" else 1


if __name__=="__main__":
    raise SystemExit(main())
