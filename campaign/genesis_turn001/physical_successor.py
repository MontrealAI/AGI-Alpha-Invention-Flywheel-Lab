"""Real measured-laboratory successor for GENESIS 001: no invented EV pack physics.

The original March 2026 controlled-cell physical measurements (independent of
our fictional native buyer) enable *research inventory* planning. A commercial
market, vehicle/field storage qualification, transfer advantage and extra R&D
cost remain UNESTABLISHED. This supplementary study does not change the
historical native account or double-charge its $18 modeled R&D envelope.
"""
from __future__ import annotations
import argparse, csv, hashlib, io, itertools, json, pathlib, time, zipfile

SOURCE_SHA={
    "evaluation.json":"d03ba18f5c24777a1c7a3171af71402833fa3ad05cc53ddbfb79f10077c28386",
    "cycle_capacities.csv":"8847a7b3b31044911b623cc670e87c57c02a1400af980c3195a1595c8e85a78b",
    "sealed_predictions.json":"63911780ab68ceaf88e8f29923944aabb40c5be1c2e8fb48abaaf20a0a271f7c",
}
RUN_ID=41931850452
LOT_NEEDS={"RESEARCH-A":85000,"RESEARCH-B":72000}
# units: 1 deci-mAh = 0.0001 Ah. These are NOT Wh, pack
# deliverability, safety-certified cells, or real customer contracts.

def require(test,why):
    if not test:raise ValueError(why)

def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def sha(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()

def ah_to_deci_mah(v):
    from decimal import Decimal,ROUND_HALF_UP
    return int((Decimal(str(v))*Decimal("10000")).to_integral_value(rounding=ROUND_HALF_UP))

def evidence_from_zip(path):
    with zipfile.ZipFile(path) as z:
        require(set(SOURCE_SHA).issubset(z.namelist()),"MISSING_PUBLISHED_LAB_FILES")
        blobs={k:z.read(k) for k in SOURCE_SHA}
    for k,expected in SOURCE_SHA.items():
        require(hashlib.sha256(blobs[k]).hexdigest()==expected,"PUBLISHED_SOURCE_HASH_CHANGED:"+k)
    evaluation=json.loads(blobs["evaluation.json"])
    sealed=json.loads(blobs["sealed_predictions.json"])
    require(evaluation["kind"]=="actual_measured_lab_retrospective_prognosis", "NOT_LAB_SOURCE")
    require(evaluation["accepted"] is False and evaluation["registered_test_cells"]==9
            and evaluation["registered_endpoints"]==18,"ORIGINAL_FAILED_PILOT_CHANGED")
    require(sealed["prediction_sha256"]==evaluation["prediction_seal"],"PREDICTION_SEAL_CHANGED")
    test={r["cell"]:r for r in evaluation["test_records"]}
    forecasts={r["cell"]:r for r in evaluation["results"] if r["method"]=="adjusted_peer"}
    require(len(test)==len(forecasts)==9,"NINE_UNIQUE_SOURCE_CELLS_REQUIRED")
    measured={}
    for r in csv.DictReader(io.StringIO(blobs["cycle_capacities.csv"].decode("utf-8"))):
        if r["role"]=="test" and r["cycle"]=="1000":
            k=r["cell"]
            require(k not in measured,"DUPLICATE_MEASURED_CELL")
            measured[k]={"group":r["group"],"capacity_deci_mAh":ah_to_deci_mah(r["accepted_capacity_ah"])}
    require(set(test)==set(measured),"UNACCOUNTED_MEASURED_CELL")
    missed=[]
    for cell in sorted(test):
        p=test[cell];f=forecasts[cell]
        require(measured[cell]["group"]==p["group"]==f["group"],"MODEL_CELL_GROUP_CHANGED")
        require(measured[cell]["capacity_deci_mAh"]==ah_to_deci_mah(p["cycle_capacities_ah"]["1000"]),"CAPACITY_RECONSTRUCTION_MISMATCH")
        for k in ("500","1000"):
            e=f["endpoints"][k];target=f["targets"][k]
            if not e["lower"]<=target<=e["upper"]:
                missed.append({"cell":cell,"endpoint":int(k)})
    require(len(missed)==2,"ORIGINAL_TWO_UNCOVERED_INTERVALS_CHANGED")
    return {"source_run":RUN_ID,"source_sha256":SOURCE_SHA,
            "cell_counts":len(test),"intervals_covered":18-len(missed),
            "intervals_total":18,"missed_intervals":missed,
            "forecast_qualification":"FAIL_16_OF_18",
            "physical_operating_scope":"measured 1C/35C cycling in laboratory, not EV pack, safety approval or actual household electricity",
            "cards":[{"id":c,"group":measured[c]["group"],"capacity_deci_mAh":measured[c]["capacity_deci_mAh"],
                      "source_cycle":1000,"data_class":"MEASURED_LAB"} for c in sorted(measured)]}

def construct_lots(first):
    require(first["forecast_qualification"]=="FAIL_16_OF_18", "FORECASTS_MUST_NOT_BE_PROMOTED")
    cards=first["cards"]
    require(len(cards)==9 and all(x["data_class"]=="MEASURED_LAB" and x["source_cycle"]==1000 for x in cards),
            "MEASURED_CARDS_REQUIRED")
    best=None
    for options in itertools.product((None,*LOT_NEEDS),repeat=len(cards)):
        totals={k:0 for k in LOT_NEEDS}
        used=[]
        for c,lot in zip(cards,options):
            if lot is not None:
                totals[lot]+=c["capacity_deci_mAh"];used.append((c["id"],lot))
        if any(totals[k]<LOT_NEEDS[k] for k in LOT_NEEDS):continue
        rank=(len(used),sum(totals.values())-sum(LOT_NEEDS.values()),tuple(sorted(used)))
        if best is None or rank<best[0]:best=rank,used,totals
    if best is None:
        return {"status":"NO_CAPACITY_IN_THIS_LAB_SAMPLE","assignments":[],"totals_deci_mAh":{},
                "source_digest":sha(first),"field_qualified":False}
    _,used,totals=best
    return {"status":"LAB_INVENTORY_FEASIBLE","assignments":[{"cell":c,"lot":l} for c,l in sorted(used)],
            "totals_deci_mAh":totals,"source_digest":sha(first),"field_qualified":False}

def independent_oracle(first,claim):
    """Separately enumerates all assignments; no call to construct_lots."""
    require(claim["source_digest"]==sha(first) and claim["field_qualified"] is False,"SOURCE_OR_SAFETY_CLAIM_CHANGED")
    cards={x["id"]:x for x in first["cards"]}
    require(len(cards)==9,"CARD_DENOMINATOR_CHANGED")
    eligible=sorted(cards)
    valid=[]
    for choices in itertools.product((None,*sorted(LOT_NEEDS)),repeat=len(eligible)):
        sums={k:0 for k in LOT_NEEDS};assigned=[]
        for cell,lot in zip(eligible,choices):
            if lot is not None:
                sums[lot]+=cards[cell]["capacity_deci_mAh"];assigned.append((cell,lot))
        if all(sums[k]>=LOT_NEEDS[k] for k in LOT_NEEDS):
            valid.append((len(assigned),sum(sums.values())-sum(LOT_NEEDS.values()),tuple(assigned)))
    if not valid:
        require(claim["status"]=="NO_CAPACITY_IN_THIS_LAB_SAMPLE" and claim["assignments"]==[], "FICTITIOUS_FEASIBILITY")
        return True
    used=[(x["cell"],x["lot"]) for x in claim["assignments"]]
    require(len(used)==len(set(x[0] for x in used)),"DOUBLE_USED_CELL")
    require(all(c in cards and l in LOT_NEEDS and cards[c]["data_class"]=="MEASURED_LAB" for c,l in used), "UNVERIFIED_OR_FICTITIOUS_CELL")
    sums={k:0 for k in LOT_NEEDS}
    for c,l in used:sums[l]+=cards[c]["capacity_deci_mAh"]
    require(sums==claim["totals_deci_mAh"] and all(sums[k]>=LOT_NEEDS[k] for k in sums),"INCORRECT_CAPACITY_TOTAL")
    key=(len(used),sum(sums.values())-sum(LOT_NEEDS.values()),tuple(sorted(used)))
    require(claim["status"]=="LAB_INVENTORY_FEASIBLE" and key==min(valid),"NOT_OPTIMAL_FOR_REGISTERED_LAB_TASK")
    return True

def ensure_native(native_dir):
    """Read-only replay of the already registered synthetic financial experiment."""
    from . import native_turn
    require(native_turn.audit(native_dir),"NATIVE_ACCOUNT_OR_FIRST_ACCEPTANCE_REJECTED")
    r=json.loads((pathlib.Path(native_dir)/"REPORT.json").read_text())
    require(r["scenario"]=="central" and r["first_accepted"] is True
           and r["successor_funded_from"]=="EARNED"
           and r["simulated_profit_after_r_and_d_cents"]==840
           and r["actual_customer_receipts_cents"]==0,"FALSE_FIRST_CYCLE_OR_REVENUE")
    return {"native_report_sha256":sha(r),"first_accepted":True,
            "simulated_earned_research_funding_cents":1800,
            "actual_customer_receipts_cents":0,
            "scope":"Existing synthetic R&D envelope, NOT a newly received sale or measured physical research cost"}

def produce(upstream,output,native_dir=None):
    path=pathlib.Path(output)
    require(not path.exists(),"FRESH_OUTPUT_REQUIRED")
    start=time.process_time_ns();first=evidence_from_zip(upstream);read_cpu=time.process_time_ns()-start
    start=time.process_time_ns();second=construct_lots(first);solve_cpu=time.process_time_ns()-start
    require(independent_oracle(first,second),"SUCCESSOR_REJECTED")
    # A capable conventional comparator has exactly the same public measurements
    # and ordinary exhaustive search. Reconstruct the source without inheriting
    # the certificate. This may tie; it is NOT artificially denied access.
    direct=evidence_from_zip(upstream)
    control=construct_lots(direct)
    require(control==second,"CONVENTIONAL_COMPARATOR_MISMATCH")
    native=ensure_native(native_dir) if native_dir else None
    result={"schema":"genesis/real-data-successor/v1",
            "first":first,"second":second,
            "native":native,
            "independent_acceptance":True,
            "qualified_forecast":False,
            "physically_qualified_second_life_batteries":False,
            "buyer_accepted_successor":False,
            "real_new_market":False,
            "actual_revenue_usd":0,
            "measured_research_cost_usd":None,
            "model_earnings_are_not_cash":True,
            "strong_conventional_alternative_ties":control==second,
            "reading_cpu_ns":read_cpu,"solution_cpu_ns":solve_cpu,
            "meaning":"A published *physical laboratory* capacity dataset enables a different checked research inventory allocation. Existing direct methods match. This does not certify field storage, show real buyer demand or make a causal inventor-superiority claim."}
    path.mkdir(parents=True)
    (path/"PUBLIC_REPORT.json").write_bytes(canonical(result)+b"\n")
    return result

def audit(upstream,output,native_dir=None):
    r=json.loads((pathlib.Path(output)/"PUBLIC_REPORT.json").read_text())
    require(r["schema"]=="genesis/real-data-successor/v1","REPORT_CHANGED")
    first=evidence_from_zip(upstream)
    require(first==r["first"],"PUBLISHED_SOURCE_OR_FIRST_OUTPUT_CHANGED")
    require(r["second"]==construct_lots(first),"PUBLISHED_SECOND_OUTPUT_CHANGED")
    independent_oracle(first,r["second"])
    require(r["strong_conventional_alternative_ties"] is True
            and r["qualified_forecast"] is False
            and r["physically_qualified_second_life_batteries"] is False
            and r["buyer_accepted_successor"] is False
            and r["real_new_market"] is False
            and r["actual_revenue_usd"]==0
            and r["measured_research_cost_usd"] is None
            and r["model_earnings_are_not_cash"] is True,"UNSUPPORTED_CLAIM")
    if native_dir:require(r["native"]==ensure_native(native_dir),"NATIVE_PARENT_CHANGED")
    else:require(r["native"] is None,"UNVERIFIED_FUNDING_CLAIM")
    return True

def self_test(upstream):
    first=evidence_from_zip(upstream)
    result=construct_lots(first)
    independent_oracle(first,result)
    import copy
    tests=0
    for mutation in ("duplicate","missing","fake","capacity","field","source"):
        changed=copy.deepcopy(result)
        if mutation=="duplicate":changed["assignments"].append(dict(changed["assignments"][0]))
        if mutation=="missing":changed["assignments"].pop()
        if mutation=="fake":changed["assignments"][0]["cell"]="INVENTED"
        if mutation=="capacity":changed["totals_deci_mAh"]["RESEARCH-A"]+=1
        if mutation=="field":changed["field_qualified"]=True
        if mutation=="source":changed["source_digest"]="0"*64
        try:independent_oracle(first,changed)
        except ValueError:tests+=1
        else:raise ValueError("AUDITOR_FALSE_ACCEPT:"+mutation)
    require(tests==6 and first["intervals_covered"]==16 and len(first["missed_intervals"])==2, "NEGATIVE_CONTROLS_FAILED")
    return tests

def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=("run","audit","test"))
    p.add_argument("--upstream-zip",required=True)
    p.add_argument("--output")
    p.add_argument("--native-dir")
    args=p.parse_args()
    if args.action=="test":print(json.dumps({"negative_controls_rejected":self_test(args.upstream_zip)}));return
    if not args.output:raise SystemExit("--output required")
    out=produce(args.upstream_zip,args.output,args.native_dir) if args.action=="run" else {"audit_passed":audit(args.upstream_zip,args.output,args.native_dir)}
    print(json.dumps({k:out.get(k) for k in ("independent_acceptance","qualified_forecast","actual_revenue_usd","strong_conventional_alternative_ties","audit_passed") if k in out},sort_keys=True))
if __name__=="__main__":main()
