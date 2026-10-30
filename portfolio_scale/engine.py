"""Uncalibrated portfolio discovery, contingent strategic prices, and scale arithmetic.

No provider calls, customer contact, production, payment or actual commercial claim.
Only trusted, fixed model code is executed; input is bounded JSON data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

SOURCE = Path(__file__).with_name("universe.json")
MODEL = "conditional-portfolio-price-game/v1"
# These priors encode multiple possible future market configurations; not calibrated probabilities.
SCENARIOS = (
    {"id": "reference_competitive", "weight": .35, "rival_cost_ratio": 1.0,
     "us_risk": .035, "rival_risk": .065, "us_friction": .02, "rival_friction": .04,
     "self_cost": .40, "no_purchase_cost": 1.30, "human_multiplier": 1.12,
     "temperature": .095, "accept": .965, "collect": .97, "cost_multiplier": 1.0, "retention": .55},
    {"id": "equal_ai_price_war", "weight": .30, "rival_cost_ratio": .75,
     "us_risk": .055, "rival_risk": .055, "us_friction": .035, "rival_friction": .025,
     "self_cost": .22, "no_purchase_cost": 1.1, "human_multiplier": 1.08,
     "temperature": .085, "accept": .91, "collect": .94, "cost_multiplier": 1.35, "retention": .35},
    {"id": "verified_differentiation", "weight": .20, "rival_cost_ratio": 1.10,
     "us_risk": .012, "rival_risk": .20, "us_friction": .018, "rival_friction": .065,
     "self_cost": .65, "no_purchase_cost": 1.5, "human_multiplier": 1.30,
     "temperature": .09, "accept": .985, "collect": .985, "cost_multiplier": 1.0, "retention": .75},
    {"id": "trust_and_demand_shock", "weight": .15, "rival_cost_ratio": .8,
     "us_risk": .20, "rival_risk": .07, "us_friction": .095, "rival_friction": .025,
     "self_cost": .20, "no_purchase_cost": .75, "human_multiplier": 1.02,
     "temperature": .08, "accept": .75, "collect": .8, "cost_multiplier": 2.5, "retention": .15},
)
SEGMENTS = (
    {"id": "small_business", "workload_factor": .7, "service_factor": .9, "complexity": .9, "turnaround": 1.0},
    {"id": "growth_company", "workload_factor": 1.0, "service_factor": 1.0, "complexity": 1.0, "turnaround": 1.0},
    {"id": "enterprise", "workload_factor": 1.45, "service_factor": 1.15, "complexity": 1.3, "turnaround": 1.0},
    {"id": "agency", "workload_factor": 1.15, "service_factor": .95, "complexity": 1.15, "turnaround": 1.0},
)
TIERS = (
    {"id": "standard", "human_hours_multiplier": 1.0, "ai_cost_multiplier": 1.0},
    {"id": "expedited", "human_hours_multiplier": 1.4, "ai_cost_multiplier": 1.3},
)


def finite(value: Any, *, positive: bool = False) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or (positive and value <= 0):
        raise ValueError("Expected finite positive number" if positive else "Expected finite nonnegative number")
    return float(value)


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def validate(data: dict[str, Any]) -> None:
    if type(data) is not dict or data.get("schema") != "alpha-scale-opportunity-universe/v1":
        raise ValueError("Wrong opportunity universe schema")
    rows=data.get("jobs")
    if type(rows) is not list or not rows:
        raise ValueError("No jobs")
    if data.get("actual_jobs_performed") != 0 or data.get("commercial_flywheel") != "UNESTABLISHED":
        raise ValueError("Unverified commercial claim in source")
    if data.get("no_automatic_customer_permissions") is not True:
        raise ValueError("Authorization must not be assumed")
    wage=data["wage_role_rates_usd_hour"]
    if type(wage) is not dict or not wage:
        raise ValueError("Missing wage mapping")
    for v in wage.values(): finite(v, positive=True)
    finite(data["employer_compensation_factor"], positive=True)
    seen=set()
    for row in rows:
        if type(row) is not dict:
            raise ValueError("Malformed job")
        if type(row.get("id")) is not str or not row["id"] or row["id"] in seen:
            raise ValueError("Missing/duplicate job ID")
        seen.add(row["id"])
        if row.get("human_role") not in wage or row.get("quality_verified") is not False:
            raise ValueError("Unqualified role/quality field")
        if row.get("cost_evidence") != "UNMEASURED_AUTHOR_HYPOTHESIS" or row.get("demand_evidence") != "UNKNOWN":
            raise ValueError("Unsupported demand or cost claim")
        if row.get("risk") not in {"LOW_TO_MODERATE", "APPROVAL_REQUIRED"}:
            raise ValueError("Unsupported delivery authority")
        if type(row.get("first_wave_eligible")) is not bool or (row["risk"]=="APPROVAL_REQUIRED" and row["first_wave_eligible"]):
            raise ValueError("Risk/first-wave gate mismatch")
        for k in ("human_hours_hypothesis","autonomous_attempt_cost_hypothesis_usd",
                  "autonomous_qualification_cost_hypothesis_usd","autonomous_onboarding_cost_hypothesis_usd"):
            finite(row[k], positive=(k=="human_hours_hypothesis"))
        for k in ("name","category","unit","acceptance","authority"):
            if type(row.get(k)) is not str or not row[k].strip():
                raise ValueError("Missing service specification")


def soft_choice(our_price: float|None, rival_price:float|None, human:float, sc:dict) -> tuple[float,float]:
    # Every option is cost to obtain an equivalent stipulated outcome; assumptions are not observed.
    values={"human":human*sc["human_multiplier"],
            "self":human*sc["self_cost"],"no_purchase":human*sc["no_purchase_cost"]}
    if our_price is not None: values["us"]=our_price+human*(sc["us_risk"]+sc["us_friction"])
    if rival_price is not None: values["rival"]=rival_price+human*(sc["rival_risk"]+sc["rival_friction"])
    center=min(values.values())
    scale=human*sc["temperature"]
    w={k: math.exp(-(v-center)/scale) for k,v in values.items()}
    denom=sum(w.values())
    return w.get("us",0)/denom, w.get("rival",0)/denom


def linear_grid(low:float, high:float, steps:int) -> list[float]:
    if not 0<=low<=high or steps<2: raise ValueError("Bad price grid")
    return [low+(high-low)*i/(steps-1) for i in range(steps)]


def repeat_factor(sc:dict, price:float, human:float) -> float:
    # One initial delivery + up to two repeat cycles; explicitly assumed.
    r=max(0,min(.9,sc["retention"]*(1-.30*price/human)))
    return 1+.98*r+(.98*r)**2


def rival_response(price:float, human:float, ai_cost:float, sc:dict) -> dict:
    rcost=ai_cost*sc["rival_cost_ratio"]
    best={"price":None,"net":0.0,"win":0.0}
    for rp in linear_grid(max(.001,rcost*.95),max(rcost*.95,human*1.30),11):
        _,win=soft_choice(price,rp,human,sc)
        net=win*repeat_factor(sc,rp,human)*(sc["accept"]*sc["collect"]*rp-rcost)
        if net>best["net"]+1e-10: best={"price":rp,"net":net,"win":win}
    return best


def quote_evaluation(price:float, human:float, ai_cost:float, quote_cost:float,
                     onboarding_cost:float, sc:dict) -> dict:
    rival=rival_response(price,human,ai_cost,sc)
    pwin,_=soft_choice(price,rival["price"],human,sc)
    paid=sc["accept"]*sc["collect"]
    r=repeat_factor(sc,price,human)
    net=pwin*(r*(paid*price-ai_cost*sc["cost_multiplier"])-onboarding_cost)-quote_cost
    return {"win":pwin,"net":net,"rival":rival["price"],"expected_paid_revenue":pwin*r*paid*price}


def offer_pricing(row:dict, data:dict, segment:dict, tier:dict, scenarios=SCENARIOS) -> dict:
    if not scenarios or abs(sum(s["weight"] for s in scenarios)-1)>1e-8:
        raise ValueError("Scenario weights must sum to 1")
    for sc in scenarios:
        for name in ("accept","collect","retention","temperature","weight"):
            finite(sc[name],positive=(name=="temperature"))
        if sc["accept"]>1 or sc["collect"]>1 or sc["retention"]>1:
            raise ValueError("Probability invalid")
    h=finite(row["human_hours_hypothesis"],positive=True)*finite(data["wage_role_rates_usd_hour"][row["human_role"]],positive=True)*finite(data["employer_compensation_factor"],positive=True)*segment["workload_factor"]*tier["human_hours_multiplier"]
    c=row["autonomous_attempt_cost_hypothesis_usd"]*segment["complexity"]*tier["ai_cost_multiplier"]
    q=row["autonomous_qualification_cost_hypothesis_usd"]*segment["service_factor"]
    onboarding=row["autonomous_onboarding_cost_hypothesis_usd"]*segment["complexity"]
    best={"price":None,"objective":0.0,"expected_net":0.0,"pwin":0.0,"worst_net":0.0,"price_human_ratio":None}
    for p in linear_grid(.05*h,1.30*h,21):
        v=[quote_evaluation(p,h,c,q,onboarding,s) for s in scenarios]
        mean=sum(s["weight"]*o["net"] for s,o in zip(scenarios,v))
        worst=min(o["net"] for o in v)
        # Downside-penalized expected cash contribution, with no-bid outside option = 0.
        objective=mean-.3*max(0,-worst)
        if objective>best["objective"]+1e-10:
            best={"price":round(p,2),"objective":objective,"expected_net":mean,
                  "pwin":sum(s["weight"]*o["win"] for s,o in zip(scenarios,v)),
                  "worst_net":worst,"price_human_ratio":p/h}
    return {"job_id":row["id"],"family":row["family"],"segment":segment["id"],"tier":tier["id"],
            "risk":row["risk"],"launch_eligible":False, # unverified output, rights and demand
            "market_quote_authorized":False,"quality_verified":False,
            "decision":"ILLUSTRATIVE_PRICE_ONLY" if best["price"] is not None else "NO_BID_IN_SCENARIOS",
            "human_loaded_labor_scenario_usd":round(h,2),
            "ai_attempt_resource_scenario_usd":round(c,2),
            "ai_onboarding_resource_scenario_usd":round(onboarding,2),
            "quote_resource_scenario_usd":round(q,2),
            "price_usd":best["price"],"expected_value_per_qualified_lead_usd":round(best["expected_net"],2),
            "downside_adjusted_value_usd":round(best["objective"],2),
            "modeled_win_probability":round(best["pwin"],4),
            "worst_scenario_value_usd":round(best["worst_net"],2),
            "quote_ratio_to_human_labor_proxy":None if best["price"] is None else round(best["price_human_ratio"],3)}


def target_math(targets:list[float],annual_customer_revenue:list[float]) -> list[dict]:
    result=[]
    for target in targets:
        finite(target,positive=True)
        for acv in annual_customer_revenue:
            finite(acv,positive=True)
            result.append({"annual_revenue_target_usd":target,"annual_contract_value_scenario_usd":acv,
                           "fully_paid_active_customers_required":math.ceil(target/acv),
                           "time_to_target":"UNIDENTIFIABLE_WITHOUT_ACQUISITION_RETENTION_CAPACITY_AND_CAPITAL_DATA",
                           "scope":"ARITHMETIC_ONLY_NOT_A_FORECAST"})
    return result


def evaluate_portfolio(data:dict, *,segments=SEGMENTS,tiers=TIERS,scenarios=SCENARIOS) -> dict:
    validate(data)
    results=[offer_pricing(row,data,s,t,scenarios) for row in data["jobs"] for s in segments for t in tiers]
    ranked=sorted((x for x in results if x["decision"]!="NO_BID_IN_SCENARIOS" and x["risk"]=="LOW_TO_MODERATE"),
                  key=lambda x:x["downside_adjusted_value_usd"],reverse=True)
    return {"schema":"alpha-scale-portfolio-plan/v1","source_sha256":digest(data),
        "scenario_weights_unmeasured":True,"buyer_and_rival_parameters":"AUTHOR_PRIORS_NOT_MARKET_CALIBRATION",
        "service_types":len(data["jobs"]),"family_count":len(set(x["family"] for x in data["jobs"])),
        "scenario_offer_variants":len(results),"discovered_new_opportunities":0,
        "no_arbitrary_job_count_cap":True,"per_run_resource_limits_apply":True,"market_revenue_ceiling":None,
        "selected_experiment_only":ranked[:15],
        "all_offers":results,
        "targets":target_math([1e9,10e9,100e9],[25000,100000,500000,1000000]),
        "actual_accepted_jobs":0,"actual_collected_revenue":0,
        "conditional_simulated_flywheel":"NOT_EXECUTED_BY_THIS_PLANNING_MODEL",
        "observed_commercial_flywheel":"UNESTABLISHED",
        "inventive_capability_improvement":"UNMEASURED",
        "risk_boundary":"Sensitive domains require permission/authorization, data rights and independent accepted artifacts; this script does not execute work",
        "not_a_validated_market_portfolio":True}


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input",type=Path,default=SOURCE)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():parser.error("Output exists; preserve earlier evidence")
    if args.input.stat().st_size>2_000_000:parser.error("Input too large for scoped parser")
    data=json.loads(args.input.read_text(encoding="utf-8"))
    out=evaluate_portfolio(data)
    with args.output.open("x",encoding="utf-8") as f:
        json.dump(out,f,ensure_ascii=False,indent=2,allow_nan=False)
        f.write("\n")
    print(json.dumps({"service_types":out["service_types"],"variant_count":out["scenario_offer_variants"],
                      "best_exploratory_offers":out["selected_experiment_only"][:5],
                      "commercial_status":out["observed_commercial_flywheel"]},indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
