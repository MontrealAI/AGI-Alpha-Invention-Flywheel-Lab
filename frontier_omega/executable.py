"""Independent bounded JSON-task execution for historical/current frontier comparisons.

Executes supplied declarative instruments and a competent conventional alternative.
A passing finite test does NOT authenticate model authorship, vintage, demand or profit.
"""
from __future__ import annotations
import argparse
from datetime import date
import hashlib
import importlib.util
import json
from pathlib import Path
import re

SCHEMA="frontier-omega/executable-comparison/v1"
SUITE="frontier-omega/heldout-suite/v1"
METHOD="frontier-omega/declarative-method/v1"
HEX=re.compile(r"[0-9a-f]{64}\Z")
ID=re.compile(r"[a-z][a-z0-9-]{2,95}\Z")


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":"),allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def strict_json(raw):
    def pairs(rows):
        result={}
        for k,v in rows:
            if k in result: raise ValueError("DUPLICATE_JSON_FIELD")
            result[k]=v
        return result
    return json.loads(raw,object_pairs_hook=pairs,
       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))


def day(s):
    if type(s) is not str or len(s)!=10 or date.fromisoformat(s).isoformat()!=s:
        raise ValueError("ISO_DAY_REQUIRED")
    return date.fromisoformat(s)


def evaluator():
    source=Path(__file__).resolve().parents[1]/"products"/"alpha-genesis-harness"/"bridge"/"instruments.py"
    if not source.is_file() or source.is_symlink():
        raise ValueError("PINNED_BOUNDED_EVALUATOR_SOURCE_REQUIRED")
    spec=importlib.util.spec_from_file_location("_frontier_bounded_evaluator",source)
    if spec is None or spec.loader is None: raise ValueError("EVALUATOR_UNAVAILABLE")
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj,hashlib.sha256(source.read_bytes()).hexdigest()


def validate(suite,methods):
    fields={"schema","problem_id","historical_cutoff","as_of","cases","inputs",
            "min_pass_bps","max_operations","acceptance_text_sha256"}
    if type(suite) is not dict or set(suite)!=fields or suite["schema"]!=SUITE:
        raise ValueError("EXACT_HELDOUT_SUITE_REQUIRED")
    cutoff,now=day(suite["historical_cutoff"]),day(suite["as_of"])
    if cutoff>=now or (now-cutoff).days>366: raise ValueError("BOUNDED_HISTORICAL_WINDOW_REQUIRED")
    if type(suite["problem_id"]) is not str or not ID.fullmatch(suite["problem_id"]):
        raise ValueError("PROBLEM_ID_REQUIRED")
    if type(suite["acceptance_text_sha256"]) is not str or not HEX.fullmatch(suite["acceptance_text_sha256"]):
        raise ValueError("ACCEPTANCE_SOURCE_SHA256_REQUIRED")
    ins=suite["inputs"]
    if type(ins) is not list or not 1<=len(ins)<=32 or len(ins)!=len(set(ins)) or any(
            type(k) is not str or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}",k) is None for k in ins):
        raise ValueError("FINITE_INPUT_NAMES_REQUIRED")
    cases=suite["cases"]
    if type(cases) is not list or not 1<=len(cases)<=128:
        raise ValueError("FINITE_HELDOUT_CASES_REQUIRED")
    for case in cases:
        if type(case) is not dict or set(case)!={"input","expected"} or type(case["input"]) is not dict or type(case["expected"]) is not dict or not set(ins)<=set(case["input"]) or len(canonical(case))>50000:
            raise ValueError("EXACT_BOUNDED_HELDOUT_CASE_REQUIRED")
    if type(suite["min_pass_bps"]) is not int or not 1<=suite["min_pass_bps"]<=10000 or type(suite["max_operations"]) is not int or not 1<=suite["max_operations"]<=100000:
        raise ValueError("EXACT_ACCEPTANCE_AND_OPERATION_BOUNDS_REQUIRED")
    if type(methods) is not list or len(methods)!=3:
        raise ValueError("OLD_NEW_AND_STRONG_ALTERNATIVE_REQUIRED")
    roles=set()
    for method in methods:
        required={"schema","role","id","available_at","source_sha256","instrument","complete_unit_cost_microUSD","cost_basis"}
        if type(method) is not dict or set(method)!=required or method["schema"]!=METHOD:
            raise ValueError("EXACT_BOUNDED_METHOD_REQUIRED")
        role=method["role"]
        if role not in {"HISTORICAL_FRONTIER","CURRENT_FRONTIER","STRONG_ALTERNATIVE"} or role in roles:
            raise ValueError("UNIQUE_FRONTIER_COMPARATOR_ROLE_REQUIRED")
        roles.add(role)
        if type(method["id"]) is not str or not ID.fullmatch(method["id"]) or type(method["source_sha256"]) is not str or not HEX.fullmatch(method["source_sha256"]):
            raise ValueError("METHOD_SOURCE_IDENTITIES_REQUIRED")
        inst=method["instrument"]
        if type(inst) is not dict or inst.get("inputs")!=ins or len(canonical(inst))>100000:
            raise ValueError("COMMON_INSTRUMENT_INPUT_CONTRACT_REQUIRED")
        cost=method["complete_unit_cost_microUSD"]
        if cost is not None and (type(cost) is not int or not 0<=cost<=10**15):
            raise ValueError("NONNEGATIVE_DECLARED_COST_REQUIRED")
        if method["cost_basis"] not in ("DECLARED_SCENARIO","UNKNOWN") or (cost is None)!=(method["cost_basis"]=="UNKNOWN"):
            raise ValueError("COST_SCENARIO_OR_UNKNOWN_REQUIRED")
        vintage=day(method["available_at"])
        if role=="HISTORICAL_FRONTIER" and vintage>cutoff:
            raise ValueError("HISTORICAL_METHOD_AFTER_CUTOFF")
        if role=="CURRENT_FRONTIER" and not cutoff<vintage<=now:
            raise ValueError("CURRENT_METHOD_OUTSIDE_WINDOW")
        if role=="STRONG_ALTERNATIVE" and vintage>now:
            raise ValueError("FUTURE_CONTROL_FORBIDDEN")
    if roles!={"HISTORICAL_FRONTIER","CURRENT_FRONTIER","STRONG_ALTERNATIVE"}:
        raise ValueError("THREE_REQUIRED_COMPARATORS_MISSING")


def compare(suite,methods,*,problem=None):
    validate(suite,methods)
    if problem is not None and (type(problem) is not dict or problem.get("id")!=suite["problem_id"] or digest(problem.get("acceptance"))!=suite["acceptance_text_sha256"]):
        raise ValueError("SUITE_NOT_BOUND_TO_FROZEN_PROBLEM_ACCEPTANCE")
    engine,evaluator_hash=evaluator()
    arms=[]
    for method in methods:
        checks=[]
        for case in suite["cases"]:
            try:
                actual=engine.evaluate(method["instrument"],case["input"],max_operations=suite["max_operations"])
                passed=engine._json_equal(actual["output"],case["expected"])
                operations=actual["operations"]
            except (ValueError,TypeError,OverflowError,KeyError,RecursionError):
                passed=False;operations=None
            checks.append({"case_sha256":digest(case),"passed":passed,"operations":operations})
        rate=10000*sum(int(x["passed"]) for x in checks)//len(checks)
        arms.append({"role":method["role"],"method_id":method["id"],
           "method_sha256":digest(method),"instrument_sha256":digest(method["instrument"]),
           "declared_source_sha256":method["source_sha256"],
           "available_at_claimed":method["available_at"],"reproduced_pass_bps":rate,
           "accepted_on_finite_cases":rate>=suite["min_pass_bps"],
           "reported_complete_unit_cost_microUSD":method["complete_unit_cost_microUSD"],
           "cost_basis":method["cost_basis"],"cases":checks})
    by={r["role"]:r for r in arms}
    old,new,incumbent=(by[k] for k in ("HISTORICAL_FRONTIER","CURRENT_FRONTIER","STRONG_ALTERNATIVE"))
    crossing=not old["accepted_on_finite_cases"] and new["accepted_on_finite_cases"]
    historical_incumbent=(incumbent["available_at_claimed"]<=suite["historical_cutoff"])
    if historical_incumbent and incumbent["accepted_on_finite_cases"]:
        verdict="HISTORICALLY_FEASIBLE_VIA_STRONG_ALTERNATIVE"
    elif not crossing:
        verdict="NO_REPRODUCED_TECHNICAL_CROSSING"
    elif incumbent["accepted_on_finite_cases"] and (
          incumbent["reported_complete_unit_cost_microUSD"] is not None
          and new["reported_complete_unit_cost_microUSD"] is not None
          and incumbent["reported_complete_unit_cost_microUSD"]<=new["reported_complete_unit_cost_microUSD"]):
        verdict="CURRENT_CONTROL_MATCHES_OR_BEATS_ON_DECLARED_COST"
    else:
        verdict="REPRODUCED_FINITE_TEST_CROSSING_HISTORICAL_PROVENANCE_UNVERIFIED"
    result={"schema":SCHEMA,"suite_sha256":digest(suite),"evaluator_source_sha256":evaluator_hash,
       "compared_problem_id":suite["problem_id"],"accepted_on_registered_cases":crossing,
       "historical_alternative_available":historical_incumbent,"verdict":verdict,
       "methods":arms,"asserted_historical_availability_independently_verified":False,
       "model_authorship_independently_verified":False,
       "economic_feasibility_established":False,"customer_demand_verified":False,
       "permission_to_spend":False,"financial_operations":0,
       "scope":"EXECUTED_BOUNDED_INSTRUMENTS_LOCAL_FINITE_HOLDOUT_ONLY"}
    result["receipt_sha256"]=digest(result)
    return result


def demo():
    suite={"schema":SUITE,"problem_id":"synthetic-capacity-demand",
      "historical_cutoff":"2026-10-12","as_of":"2026-11-16",
      "inputs":["demand","capacity"],"min_pass_bps":10000,"max_operations":250,
      "acceptance_text_sha256":digest("Synthetic capacity clipping with finite acceptance"),
      "cases":[{"input":{"demand":12,"capacity":8},"expected":{"served":8}},
               {"input":{"demand":3,"capacity":10},"expected":{"served":3}},
               {"input":{"demand":0,"capacity":3},"expected":{"served":0}}]}
    arms=[]
    for role,ident,available,formula,cost in (
        ("HISTORICAL_FRONTIER","historical-hypothesis","2026-10-01","demand",90),
        ("CURRENT_FRONTIER","current-hypothesis","2026-11-01","min(demand,capacity)",65),
        ("STRONG_ALTERNATIVE","conventional-min","2026-10-01","min(demand,capacity)",60)):
        arms.append({"schema":METHOD,"role":role,"id":ident,"available_at":available,
          "source_sha256":"0"*64,
          "instrument":{"name":ident,"inputs":["demand","capacity"],
              "outputs":{"served":{"formula":formula}}},
          "complete_unit_cost_microUSD":cost,"cost_basis":"DECLARED_SCENARIO"})
    return compare(suite,arms)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--demo",action="store_true")
    for name in ("suite","historical","current","alternative","problem","out"):
        p.add_argument("--"+name,type=Path)
    args=p.parse_args(argv)
    if args.demo:
        if any(getattr(args,x) for x in ("suite","historical","current","alternative","problem")):
            p.error("--demo cannot use trial file inputs")
        result=demo()
    else:
        if any(getattr(args,x) is None for x in ("suite","historical","current","alternative")):
            p.error("--suite, --historical, --current, --alternative required")
        suite=strict_json(args.suite.read_bytes())
        methods=[strict_json(getattr(args,n).read_bytes()) for n in ("historical","current","alternative")]
        problem=strict_json(args.problem.read_bytes()) if args.problem else None
        result=compare(suite,methods,problem=problem)
    output=json.dumps(result,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+"\n"
    if args.out:
        if args.out.exists():raise ValueError("EXISTING_RECEIPT_NOT_OVERWRITTEN")
        args.out.write_text(output)
    print(output)


if __name__=="__main__": main()
