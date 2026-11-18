"""Run EP01 against the private candidate, full-source SQLite control and adverse controls."""
import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import importlib.util
import itertools
import json
from pathlib import Path
import platform
import resource
import sqlite3
import subprocess
import sys
import tempfile
import time

from reference import ELIGIBLE, MANIFEST, canonical, check_points, connect, number, selection, verify

HERE = Path(__file__).resolve().parent
PRODUCER = HERE.parent / "endpoint_lab/decide.py"
TABLES = HERE.parent / "endpoint_lab/reports.json"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def expect_rejection(operation):
    try:
        operation()
    except (ValueError, OSError):
        return True
    return False


def controls(contract, receipt):
    trial = {}
    mutations = {
        "edited_latency":lambda r: r["selected"][0].update(ttft_p90_ms="0.0001"),
        "swapped_witness":lambda r:r["selected"][0].update(run=r["selected"][0]["run"]+1),
        "missing_optimum":lambda r:r["selected"].clear(),
        "spurious_tie":lambda r:r["selected"].append(dict(r["selected"][0])),
        "wrong_contract_digest":lambda r:r.update(contract_sha256="0"*64),
        "stale_source":lambda r:r.update(reports_sha256="0"*64),
        "changed_authority":lambda r:r.update(deployment_authorized=True),
    }
    for name, change in mutations.items():
        copy = deepcopy(receipt)
        change(copy)
        trial[name] = expect_rejection(lambda: verify(contract,copy))
    return trial


def candidate_once(contract, folder):
    source = folder / "input.json"
    source.write_text(json.dumps(contract),encoding="utf-8")
    result = subprocess.run([sys.executable,"-B",str(PRODUCER),"--contract",str(source)],
                            capture_output=True, text=True)
    return result.returncode, json.loads(result.stdout) if result.returncode == 0 else {"error":result.stderr.strip()}


def max_system_choice(contract, db):
    # Only a diagnostic: this strategy does not perform the beneficiary's filters.
    rows = list(db.execute(ELIGIBLE, contract))
    if not rows:
        return None
    point = max(rows, key=lambda r:number(r["system_tps"]))
    return {k:point[k] for k in ("source","run","concurrency","system_tps","ttft_p90_ms","tps_per_user","tpot_p90_ms")}


def sweep(contract, db):
    # Import the candidate only as the treatment being measured; the complete
    # reference above is queried on exactly the same two contracts.
    spec = importlib.util.spec_from_file_location("endpoint_candidate", PRODUCER)
    treatment = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(treatment)
    alternatives = ("reported_tps_per_user", "inverse_p90_tpot")
    results, disagreements = [], []
    for rate in range(1,401):
        choices = []
        for metric in alternatives:
            test = {**contract,"min_tps_per_user":str(rate),"rate_metric":metric}
            reference = selection(test,db)
            output = treatment.decide(test)
            agrees = (reference["decision"] == output["decision"]
                      and canonical(reference["selected"]) == canonical(output["selected"]))
            if not agrees:
                disagreements.append({"rate":rate,"metric":metric})
            choices.append(tuple((p["source"],p["run"],p["concurrency"]) for p in reference["selected"]))
        results.append((rate,choices[0],choices[1]))
    intervals = []
    for pair, items in itertools.groupby(results,key=lambda row:(row[1],row[2])):
        group = list(items)
        if pair[0] != pair[1]:
            intervals.append({"start_tok_s":group[0][0],"end_tok_s":group[-1][0],
                              "reported_concurrency":[x[2] for x in pair[0]],
                              "inverse_p90_concurrency":[x[2] for x in pair[1]]})
    return {"rate_count":len(results),"thresholds_with_different_choice":sum(a!=b for _,a,b in results),
            "intervals":intervals,"candidate_sql_comparisons":2*len(results),"disagreements":disagreements}


def main():
    arg = argparse.ArgumentParser(description=__doc__)
    arg.add_argument("--output",required=True,type=Path, help="new JSON file")
    args = arg.parse_args()
    wall, cpu = time.perf_counter(),time.process_time()
    initial = resource.getrusage(resource.RUSAGE_CHILDREN)
    contracts = json.loads((HERE / "contracts.json").read_bytes())
    evidence = {"study":"EP01","registered_source":"989afc887039fa4ecfaec1a3137312f3517f078c",
                "sensitivity_registration":"12e2d651d68884fd611275ff882379aba7947682",
                "python":platform.python_version(), "sqlite":sqlite3.sqlite_version,
                "hashes":{p.name:digest(p) for p in (PRODUCER,TABLES,HERE/"contracts.json",HERE/"reference.py",Path(__file__),HERE/"REGISTRATION.md",HERE/"SENSITIVITY.md")},
                "source_manifest_sha256":MANIFEST,"cases":{}}
    with connect() as db, tempfile.TemporaryDirectory() as tmp:
        evidence["population"] = [dict(row) for row in db.execute(
            "SELECT source,model,dataset,verified,COUNT(*) AS runs FROM evidence GROUP BY source ORDER BY source")]
        for name, spec in contracts.items():
            start = time.perf_counter()
            code, treatment = candidate_once(spec, Path(tmp))
            cand_wall = time.perf_counter()-start
            start = time.perf_counter()
            reference = selection(spec,db)
            sql_wall = time.perf_counter()-start
            try:
                verify(spec,treatment)
                accepted, error = code == 0, None
            except (KeyError,ValueError) as exc:
                accepted, error = False,str(exc)
            row = {"producer_exit":code,"candidate_decision":treatment.get("decision"),"reference":reference,
                   "agrees":accepted,"failure":error,"candidate_process_wall_s":round(cand_wall,6),
                   "sql_query_wall_s_excluding_load":round(sql_wall,6)}
            if name in ("interactive_gpt","interactive_deepseek","tail_rate_deepseek"):
                row["highest_system_tps_diagnostic"] = max_system_choice(spec,db)
                row["candidate_next_test"] = {k:v for k,v in treatment.get("next_test",{}).items() if k=="action"}
            if name == "interactive_gpt" and treatment.get("selected"):
                evidence["corrupted_receipts_rejected"] = controls(spec,treatment)
            evidence["cases"][name] = row
        start=time.perf_counter()
        evidence["rate_sensitivity"] = sweep(contracts["interactive_deepseek"],db)
        evidence["sensitivity_wall_seconds"] = round(time.perf_counter()-start,6)
    current = resource.getrusage(resource.RUSAGE_CHILDREN)
    evidence["execution"] = {"wall_seconds":round(time.perf_counter()-wall,6),
        "process_and_child_cpu_seconds":round(time.process_time()-cpu+current.ru_utime-initial.ru_utime+current.ru_stime-initial.ru_stime,6),
        "primary_candidate_processes":len(contracts),"incremental_paid_services":0,"complete_monetary_cost":"unmeasured"}
    evidence["pass"] = (all(x["agrees"] for x in evidence["cases"].values())
        and all(evidence["corrupted_receipts_rejected"].values()) and not evidence["rate_sensitivity"]["disagreements"]
        and all(evidence["cases"][k]["candidate_decision"]=="supported" for k in ("interactive_gpt","interactive_deepseek","tail_rate_deepseek"))
        and all(evidence["cases"][k]["candidate_decision"]=="withheld" for k in list(contracts)[3:]))
    with args.output.open("x", encoding="utf-8") as fp:
        json.dump(evidence,fp,indent=2,ensure_ascii=False);fp.write("\n")
    print(json.dumps({"pass":evidence["pass"],"cases":len(contracts),"seconds":evidence["execution"]["wall_seconds"],
                      "different_choices":evidence["rate_sensitivity"]["thresholds_with_different_choice"]}))
    if not evidence["pass"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
