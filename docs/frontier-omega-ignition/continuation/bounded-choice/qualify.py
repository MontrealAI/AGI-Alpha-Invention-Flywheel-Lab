"""Run the prospectively registered, position-balanced chooser on two frozen public missions."""
import argparse
from copy import deepcopy
import json
import os
import re
from pathlib import Path
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/"products/frontier-omega-ignition/trials"))
import run
from ignition import development

IDS={"editorial":"17e1dcf5c5f062a89db070dda03e6df21c6965bf7dbb5b7dff06e62803cf057d",
     "parcel":"41e161e8df39e55f99618871541b7fbf48141a7311d55565980881e41fed97df"}
EVAL="50a13c7a52aca4ddaed813705f64bfe1f8767b520da5f75a3f8b32451fe78a41"
CELLS=(("editorial","ascending"),("parcel","descending"),("editorial","descending"),("parcel","ascending"))


def candidate_packet(menu):
    return [{"id":row["id"],"description":row["description"]} for row in menu["candidates"]]


def before():
    paths={"parcel":HERE/"parcel.json","editorial":run.PRODUCT/"examples/migration.json"}
    fixtures={k:json.loads(p.read_bytes()) for k,p in paths.items()}
    receipts={}
    menus={}
    if run.evaluation.evaluator_identity()["evaluation.py"]!=EVAL:
        raise ValueError("Independent evaluator changed")
    for name,x in fixtures.items():
        m=x["mission"]
        c=run.construction.freeze_contract(m["construction_spec"])
        if c["sha256"]!=IDS[name]:
            raise ValueError("Registered contract changed")
        d=c["spec"]["definition"]
        for direction in ("ascending","descending"):
            menu,error=development.menu(d,direction)
            if error or len(menu["candidates"])<2:
                raise ValueError("Purpose-sensitive alternatives unavailable")
            menus[name,direction]=menu
        asc=candidate_packet(menus[name,"ascending"])
        desc=candidate_packet(menus[name,"descending"])
        if asc!=list(reversed(desc)) or [x["id"] for x in asc]!=sorted({x["id"] for x in asc}):
            raise ValueError("Position control failed before inference")
        if name=="editorial":
            comparator=run.conventional_baseline(c)
        else:
            program={"columns":[{"target":"sorting_mark","source":"routing_note","type":"text","split":{"separator":" ","index":1}}],
                     "input_fields":["parcel_code","routing_note"],"extra_fields":"reject"}
            comp=run.construction.build(c,{"kind":"record_migration","program":program})
            comparator={"route":"Hand-authored bounded parcel mapping; recipient evaluator",
                        "evaluation":run.assessment(run.evaluation.evaluate(c,comp))}
        _,why=development.learn(d)
        receipts[name]={"fixture_sha256":run.sha(paths[name]),"contract_sha256":c["sha256"],"menus":{"ascending":asc,"descending":desc},
                        "complete_conventional":comparator,"public_only_learner":("ambiguous" if why else "unique")}
    return fixtures,menus,receipts


class Checked:
    def __init__(self,actual,mission,menu):
        self.actual,self.mission,self.menu=actual,mission,menu
        self.seen=False

    def identity(self):return self.actual.identity()

    @property
    def receipts(self):return self.actual.receipts

    def propose(self,stage,payload):
        fields={"instruction","purpose","requirements","fixed_operations","candidates","run_id","revision","mission_sha256"}
        # Construct the exact allowed body from operator-visible inputs. Hidden observations, test names,
        # per-case outcomes or a free-form selection instruction cannot enter through additional fields.
        instruction=("Choose the one mapping identified by the original objective. If the supplied intent does not distinguish "
                     "a complete mapping, answer abstain. Return only the registered choice identifier in the JSON choice field.")
        if (self.seen or stage!="choose_hypothesis" or set(payload)!=fields or payload["instruction"]!=instruction
                or not re.fullmatch(r"[0-9a-f]{32}",payload["run_id"]) or payload["revision"]!=1
                or not re.fullmatch(r"[0-9a-f]{64}",payload["mission_sha256"]) or
                payload["purpose"]!=self.mission["purpose"] or payload["requirements"]!=self.mission["requirements"]
                or payload["candidates"]!=candidate_packet(self.menu) or
                payload["fixed_operations"]!=[op["description"] for op in self.menu["fixed_operations"]]):
            raise ValueError("Chooser input boundary or presentation order changed")
        text=json.dumps(payload,ensure_ascii=False)
        for case in self.mission["construction_spec"]["cases"]:
            if case["name"] in text or run.digest(case["input"]) in text:
                raise ValueError("Private case identity in chooser request")
        self.seen=True
        return self.actual.propose(stage,payload)


def cell(name,order,fixture,menu,actual,work,out):
    start=time.monotonic()
    workspace=work/(name+"-"+order);workspace.mkdir()
    m=deepcopy(fixture["mission"])
    m["resources"].update(execution_strategy="direct",direct_method="model_choice",choice_order=order,max_model_calls=1,max_repairs=0)
    provider=Checked(actual,m,menu)
    store=run.Store(workspace/"missions")
    controller=run.Controller(store,provider_factory=lambda:provider)
    pos=len(actual.receipts)
    mid,version=controller.create({"mission":m,"sources":fixture["sources"],"request_id":"bounded-"+name+"-"+order})
    controller.advance(mid,version)
    state=store.get(mid)
    calls=[{k:r[k] for k in run.hosted.PUBLIC_ROUTES if k in r} for r in actual.receipts[pos:]]
    result={"fixture":name,"order":order,"observation":"INCOMPLETE","mission_verdict":"UNAVAILABLE","mission_status":state["status"],
            "ordered_ids":[r["id"] for r in menu["candidates"]],"calls":calls,"elapsed_seconds":round(time.monotonic()-start,6),
            "evaluator":run.assessment(state.get("evaluation")),"portable":None}
    selected=(state.get("mapping_resolution") or {}).get("choice")
    result["choice"]=selected if selected in result["ordered_ids"]+["abstain"] else None
    result["choice_position"]=result["ordered_ids"].index(selected)+1 if selected in result["ordered_ids"] else None
    if not provider.seen or len(calls)!=1:
        return result
    r=calls[0]
    if (r.get("stage")!="choose_hypothesis" or r.get("application_model_calls")!=1 or r.get("mode")!="local"
            or r.get("reported_model")!=run.hosted.MODEL_ALIAS or r.get("status")!="completed" or not r.get("response_sha256")
            or not r.get("response_schema_sha256") or not state.get("contract") or state["contract"]["sha256"]!=IDS[name]):
        return result
    if result["choice"] is None:
        return result
    result["mission_verdict"]="NOT_ACCEPTED"
    if state["status"]=="verified":
        if result["evaluator"]["status"]!="pass" or result["evaluator"]["candidate_cases_passed"]!=result["evaluator"]["case_count"]:
            return result
        bundle=controller.deliver(mid,version)
        checks=run.hosted.check_portable(bundle,workspace)
        if checks["verified_exit"] or checks["example_exit"]:
            return result
        pkg=run.delivery.export_bundle(state["contract"],state["artifact"],state["evaluation"],
                                       {"source":run.hosted.checked_source(),"public_cell":name+"-"+order,
                                        "registered_choice":selected,"model":run.hosted.MODEL_ALIAS,"calls":calls})
        recheck=workspace/"public-copy";recheck.mkdir()
        delivered=run.hosted.check_portable(pkg,recheck)
        if delivered!=checks:
            return result
        dest=out/(name+"-"+order+".zip");dest.write_bytes(pkg)
        result.update(mission_verdict="ACCEPTED",portable=checks,artifact_sha256=state["artifact"]["sha256"],public_zip_sha256=run.sha(dest))
    elif state["status"] not in ("deferred","failed"):
        return result
    result.update(observation="COMPLETE",elapsed_seconds=round(time.monotonic()-start,6))
    return result


def study(work,out,record):
    sha=run.hosted.checked_source()
    if sha!=os.environ.get("EXPECTED_SOURCE",sha) or run.git(ROOT,"status","--porcelain","--",str(HERE.relative_to(ROOT)),
                                                              ".github/workflows/frontier-ignition-bounded-choice.yml"):
        raise ValueError("Source binding failed")
    fixtures,menus,baselines=before()
    record.update(source=sha,registration_sha256=run.sha(HERE/"REGISTRATION.md"),driver_sha256=run.sha(Path(__file__)),
                  runtime_sha256=run.runtime_source(),evaluator=run.evaluation.evaluator_identity(),preflight=baselines,cells=[])
    start=time.monotonic()
    with run.local_model(work,record) as model:
        record["setup_seconds"]=round(time.monotonic()-start,6)
        for name,direction in CELLS:
            try:
                outcome=cell(name,direction,fixtures[name],menus[name,direction],model,work,out)
            except Exception as err:
                outcome={"fixture":name,"order":direction,"observation":"INCOMPLETE","mission_verdict":"UNAVAILABLE","error_type":type(err).__name__}
            record["cells"].append(outcome)
            print("IGNITION_CHOICE_CELL "+json.dumps(outcome,separators=(",",":"),ensure_ascii=True),flush=True)
    if run.hosted.checked_source()!=sha:
        raise ValueError("Source changed during observation")
    record["observation"]="COMPLETE" if all(r["observation"]=="COMPLETE" for r in record["cells"]) else "INCOMPLETE"
    consistent=all(len({r.get("artifact_sha256") for r in record["cells"] if r["fixture"]==name})==1 for name in IDS)
    record["four_verified_order_invariant_recipients"]=consistent and all(r["mission_verdict"]=="ACCEPTED" for r in record["cells"])
    record["mission_verdict"]=("UNAVAILABLE" if record["observation"]!="COMPLETE" else
                               "ACCEPTED" if record["four_verified_order_invariant_recipients"] else "NOT_ACCEPTED")


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--work",required=True,type=Path);p.add_argument("--output",required=True,type=Path)
    a=p.parse_args();w,o=a.work.resolve(),a.output.resolve()
    if (any(x.exists() or x.is_relative_to(ROOT) for x in (w,o)) or w.is_relative_to(o) or o.is_relative_to(w)):
        p.error("Use fresh separate paths outside the checkout")
    w.mkdir(mode=0o700,parents=True);o.mkdir(mode=0o700,parents=True)
    stamp=time.monotonic()
    r={"protocol":"ignition/bounded-choice/1","started_at":run.hosted.stamp(),"observation":"INCOMPLETE",
       "mission_verdict":"UNAVAILABLE","complete_cost_known":False,"actions_run":os.environ.get("GITHUB_RUN_ID"),
       "actions_attempt":os.environ.get("GITHUB_RUN_ATTEMPT"),"human_interventions_in_unattended_cells":0}
    try:
        study(w,o,r)
    except Exception as err:
        r["error_type"]=type(err).__name__
        if not os.environ.get("GITHUB_ACTIONS"):raise
    finally:
        r.update(finished_at=run.hosted.stamp(),total_seconds=round(time.monotonic()-stamp,6))
        (o/"receipt.json").write_text(json.dumps(r,indent=2,ensure_ascii=False,allow_nan=False)+"\n")
        print("IGNITION_CHOICE_SUMMARY "+json.dumps({k:r.get(k) for k in ("source","observation","mission_verdict","four_verified_order_invariant_recipients","total_seconds","error_type")}))
    return 0 if r["observation"]=="COMPLETE" else 1


if __name__=="__main__":
    raise SystemExit(main())
