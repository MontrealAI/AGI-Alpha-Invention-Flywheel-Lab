from __future__ import annotations

import argparse
import concurrent.futures
import copy
import hashlib
import json
import multiprocessing
import os
import resource
import subprocess
import time
from pathlib import Path

from commercial.ledger import canonical
from experiments.public_portfolio_20261102 import economics


AMENDMENT = economics.PREFIX+"QUALIFICATION_AMENDMENT_R2.json"


def _save(path, value):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical(value)+b"\n")


def _replace(path,value):
    path=Path(path)
    temporary=path.with_name(path.name+".next")
    with temporary.open("xb") as stream:
        stream.write(canonical(value)+b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary,path)


def resource_allocation():
    logical=os.cpu_count() or 1
    affinity=len(os.sched_getaffinity(0)) if hasattr(os,"sched_getaffinity") else logical
    quota_count=None
    quota_text=None
    quota=Path("/sys/fs/cgroup/cpu.max")
    if quota.is_file():
        quota_text=quota.read_text().strip()
        parts=quota_text.split()
        if len(parts)==2 and parts[0]!="max":
            quota_count=max(1,int(parts[0])//int(parts[1]))
    limits=[4,logical,affinity]
    if quota_count is not None:
        limits.append(quota_count)
    memory=Path("/sys/fs/cgroup/memory.max")
    return {"logical_cpus":logical,"affinity_cpus":affinity,"cgroup_cpu_max":quota_text,"quota_whole_cpus":quota_count,"cgroup_memory_max_bytes":memory.read_text().strip() if memory.is_file() else None,"workers":max(1,min(limits)),"scope":"Observed local allocation for this finite execution; no resource entitlement beyond actual host limits"}


def planned_cases(protocol):
    plans=[]
    for route in economics.ROUTES:
        for scenario in protocol["registered_scenarios"]:
            plans.append({"index":len(plans),"route":route,"scenario":copy.deepcopy(scenario),"case_id":route+"-"+scenario["id"]})
    if len({row["case_id"] for row in plans})!=len(plans):
        raise ValueError("UNIQUE_REGISTERED_CASE_IDENTITIES_REQUIRED")
    return plans


def _assert_math(root,amendment):
    for name,expected in amendment["required_unchanged_economic_source"].items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:
            raise ValueError("R2_UNCHANGED_ECONOMIC_MODEL_REQUIRED:"+name)


def _worker(root_string,output_string,products,protocol,amendment,plan):
    root,output=Path(root_string),Path(output_string)
    reservation=output/"control"/"reservations"/(plan["case_id"]+".json")
    registered=json.loads(reservation.read_text())
    if registered.get("status")!="RESERVED" or registered.get("case_id")!=plan["case_id"] or registered.get("planned_index")!=plan["index"]:
        raise ValueError("EXCLUSIVE_ORIGINAL_CASE_RESERVATION_REQUIRED")
    before=resource.getrusage(resource.RUSAGE_SELF)
    started=time.perf_counter()
    _replace(reservation,{**registered,"status":"RUNNING","worker_pid":os.getpid()})
    try:
        _assert_math(root,amendment)
        state=economics._run_case(root,output,products,protocol,plan["route"],plan["scenario"])
        result={"ok":True,"planned_index":plan["index"],"case_id":plan["case_id"],"result":economics._compact(state)}
        status="COMPLETE"
    except Exception as error:
        result={"ok":False,"planned_index":plan["index"],"case_id":plan["case_id"],"error_type":type(error).__name__,"error":str(error)[:2000],"no_automatic_retry":True,"partial_account_recovery_preserved":True}
        _save(output/"public"/plan["case_id"]/"FAILURE.json",result)
        status="FAILED"
    after=resource.getrusage(resource.RUSAGE_SELF)
    resources={"case_id":plan["case_id"],"planned_index":plan["index"],"wall_seconds":time.perf_counter()-started,"user_cpu_seconds":after.ru_utime-before.ru_utime,"system_cpu_seconds":after.ru_stime-before.ru_stime,"worker_process_peak_rss_kib":after.ru_maxrss,"peak_rss_scope":"Worker high-water process memory, not a per-case allocation delta","actual_model_tokens":None,"actual_host_model_billing":None}
    result["resources"]=resources
    _save(output/"public"/plan["case_id"]/"RESOURCES.json",resources)
    _replace(reservation,{**registered,"status":status,"worker_pid":os.getpid(),"resources":resources})
    return result


def _r1_reference(path):
    if path is None:
        return {"observed":False,"scope":"No R1 account or cash imported"}
    public=Path(path).resolve()/"public"
    result={"observed":True,"scope":"Read-only public completion/checkpoint reference; no account, wallet, key or capital imported","completed_case_ids":sorted(p.parent.name for p in public.glob("*/RESULT.json"))}
    for name in ("INTENTIONAL_BOUNDARY.json","CHECKPOINT.json"):
        file=public/name
        if file.is_file():
            result[name]={"sha256":hashlib.sha256(file.read_bytes()).hexdigest(),"record":json.loads(file.read_text())}
    return result


def run(root,output,products_path=None,r1_output=None):
    root,output=Path(root).resolve(),Path(output).resolve()
    if root!=Path(__file__).resolve().parents[2]:
        raise ValueError("CONTROLLER_AND_NATIVE_SOURCE_ROOT_MUST_MATCH")
    amendment=json.loads((root/AMENDMENT).read_text())
    _assert_math(root,amendment)
    protocol=json.loads((root/economics.PROTOCOL).read_text())
    plans=planned_cases(protocol)
    if len(plans)!=amendment["plan"]["registered_cases"]:
        raise ValueError("R2_REGISTERED_COMPARISON_DENOMINATOR_CHANGED")
    product_file=Path(products_path) if products_path else root/economics.PREFIX/"PRODUCTS.json"
    if not product_file.is_absolute():
        product_file=root/product_file
    products=json.loads(product_file.read_text())
    if isinstance(products,dict):
        products=products["products"]
    if not isinstance(products,list) or len({p["id"] for p in products})!=len(products):
        raise ValueError("UNIQUE_APPROVED_PRODUCT_METADATA_REQUIRED")
    output.mkdir(parents=True,exist_ok=False)
    allocation=resource_allocation()
    _save(output/"public"/"protocol.json",protocol)
    _save(output/"public"/"QUALIFICATION_AMENDMENT_R2.json",amendment)
    try:
        commit=subprocess.run(["git","rev-parse","HEAD"],cwd=root,check=True,capture_output=True,text=True).stdout.strip()
    except (OSError,subprocess.CalledProcessError):
        commit=None
    summary={"schema":"public-portfolio-native-economics-results/v1","qualification_stage":"R2_INDEPENDENT_SOURCE_QUALIFICATION_REPRODUCTION","protocol_sha256":hashlib.sha256((root/economics.PROTOCOL).read_bytes()).hexdigest(),"source_sha256":hashlib.sha256((root/economics.PREFIX/"economics.py").read_bytes()).hexdigest(),"controller_sha256":hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),"amendment_sha256":hashlib.sha256((root/AMENDMENT).read_bytes()).hexdigest(),"products_file_sha256":hashlib.sha256(product_file.read_bytes()).hexdigest(),"code_commit":commit,"r1_reference":_r1_reference(r1_output),"scope":"SEPARATE_CONDITIONAL_COMPUTATIONAL_BUSINESSES_NOT_ACTUAL_COMMERCE","registered_businesses":len(plans),"cases":[],"actual_revenue_usd":0,"calibrated_demand":False,"actual_host_model_billing":None,"capital_secured":False,"resource_allocation":allocation}
    _save(output/"control"/"PLANNED_CASES.json",plans)
    _save(output/"public"/"RUN_IDENTITY.json",{k:v for k,v in summary.items() if k!="cases"})
    start=time.perf_counter()
    parent_before=resource.getrusage(resource.RUSAGE_SELF)
    children_before=resource.getrusage(resource.RUSAGE_CHILDREN)
    completed,failed,resources=[],[],[]
    next_index=0
    stop_scheduling=False
    context=multiprocessing.get_context("spawn")
    with concurrent.futures.ProcessPoolExecutor(max_workers=allocation["workers"],mp_context=context) as pool:
        running={}
        while running or (next_index<len(plans) and not stop_scheduling):
            while len(running)<allocation["workers"] and next_index<len(plans) and not stop_scheduling:
                plan=plans[next_index]
                reservation=output/"control"/"reservations"/(plan["case_id"]+".json")
                _save(reservation,{"schema":"public-portfolio/exclusive-r2-case-reservation/v1","case_id":plan["case_id"],"planned_index":plan["index"],"status":"RESERVED","no_prior_account_or_cash_imported":True})
                future=pool.submit(_worker,str(root),str(output),products,protocol,amendment,plan)
                running[future]=plan
                print("START "+plan["case_id"],flush=True)
                next_index+=1
            if not running:
                break
            done,_=concurrent.futures.wait(running,return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                plan=running.pop(future)
                try:
                    result=future.result()
                except Exception as error:
                    result={"ok":False,"planned_index":plan["index"],"case_id":plan["case_id"],"error_type":type(error).__name__,"error":str(error)[:2000],"worker_process_failure":True,"no_automatic_retry":True,"partial_account_recovery_preserved":True}
                if result["ok"]:
                    completed.append((result["planned_index"],result["result"]))
                    print("DONE "+result["case_id"]+" collected="+str(result["result"]["accepted_and_collected_orders"]),flush=True)
                else:
                    failed.append(result)
                    stop_scheduling=True
                    print("FAILED "+result["case_id"]+" "+result["error_type"],flush=True)
                if "resources" in result:
                    resources.append(result["resources"])
    summary["cases"]=[row for _,row in sorted(completed,key=lambda x:x[0])]
    summary["completed_businesses"]=len(completed)
    summary["failed_businesses"]=len(failed)
    summary["target_1b_count"]=sum(row["target_1b"] for row in summary["cases"])
    summary["target_3b_count"]=sum(row["target_3b"] for row in summary["cases"])
    parent_after=resource.getrusage(resource.RUSAGE_SELF)
    children_after=resource.getrusage(resource.RUSAGE_CHILDREN)
    telemetry={"schema":"public-portfolio/actual-r2-execution-resources/v1","wall_seconds":time.perf_counter()-start,"controller_user_cpu_seconds":parent_after.ru_utime-parent_before.ru_utime,"controller_system_cpu_seconds":parent_after.ru_stime-parent_before.ru_stime,"children_user_cpu_seconds":children_after.ru_utime-children_before.ru_utime,"children_system_cpu_seconds":children_after.ru_stime-children_before.ru_stime,"controller_peak_rss_kib":parent_after.ru_maxrss,"largest_worker_peak_rss_kib":children_after.ru_maxrss,"resource_allocation":allocation,"case_resources":sorted(resources,key=lambda x:x["planned_index"]),"actual_model_tokens":None,"actual_host_model_billing":None}
    _save(output/"public"/"TELEMETRY.json",telemetry)
    if failed or len(completed)!=len(plans):
        checkpoint={"schema":"public-portfolio/r2-source-qualification-checkpoint/v1","registered_cases":len(plans),"completed_case_ids":[row["case_id"] for row in summary["cases"]],"failed":failed,"not_started_case_ids":[plan["case_id"] for plan in plans[next_index:]],"running_accounts_allowed_to_finish":True,"no_retry_no_reset_no_pooled_cash":True}
        _save(output/"public"/"CHECKPOINT.json",checkpoint)
        _save(output/"public"/"PARTIAL_RESULTS.json",summary)
        return {**summary,"status":"CHECKPOINT"}
    summary["working_capital_pairs"]=[]
    for route in economics.ROUTES:
        pair={row["scenario"]:row for row in summary["cases"] if row["route"]==route and row["scenario"].startswith("working-capital-")}
        aware,greedy=pair["working-capital-aware"],pair["working-capital-greedy"]
        if aware["matched_world_sha256"]!=greedy["matched_world_sha256"]:
            raise ValueError("R2_MATCHED_WORKING_CAPITAL_WORLD_CHANGED")
        summary["working_capital_pairs"].append({"route":route,"matched_world_sha256":aware["matched_world_sha256"],"aware_minus_greedy_profit_microUSD":aware["profit_microUSD"]-greedy["profit_microUSD"],"aware_minus_greedy_collected_orders":aware["accepted_and_collected_orders"]-greedy["accepted_and_collected_orders"]})
    summary["status"]="COMPLETE"
    _save(output/"public"/"RESULTS.json",summary)
    economics._write_report(output,protocol,summary)
    return summary


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--root",default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--output",required=True)
    parser.add_argument("--products")
    parser.add_argument("--r1-output")
    args=parser.parse_args()
    result=run(args.root,args.output,args.products,args.r1_output)
    print(json.dumps({"status":result["status"],"completed":result["completed_businesses"],"failed":result["failed_businesses"],"target_3b_count":result["target_3b_count"]}))
    raise SystemExit(0 if result["status"]=="COMPLETE" else 2)
