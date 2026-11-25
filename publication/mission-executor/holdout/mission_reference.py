"""Independently compute objective witnesses for pre-frozen legitimate missions."""

from __future__ import annotations

import itertools
import json
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from hashlib import sha256
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
REGISTRATION = "4417b33af28d8d0acfdd814714f8dd837d94fe6d2414c885c3ba2fbcd061d274"


def parse_utc(source: str):
    parsed = datetime.fromisoformat(source.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Explicit time basis required")
    return parsed.astimezone(timezone.utc)


def time_label(instant):
    return instant.isoformat().replace("+00:00", "Z")


def inverse_affine(data):
    command1, observed1 = map(Fraction, data["marks"][0])
    command2, observed2 = map(Fraction, data["marks"][1])
    if command2 == command1 or observed2 == observed1:
        return {"status":"non-invertible"}
    slope = (observed2-observed1)/(command2-command1)
    offset = observed1 - slope*command1
    commands = [(Fraction(target)-offset)/slope for target in data["targets"]]
    return {"slope":str(slope), "offset":str(offset), "commands":[str(command) for command in commands],
            "forward_replay":[str(command*slope+offset) for command in commands]}


def inventory_enumeration(data):
    best = None
    winners = []
    candidates = 0
    feasible = 0
    for size in range(min(data["max_items"], len(data["items"]))+1):
        for bundle in itertools.combinations(data["items"], size):
            candidates += 1
            names = {item[0] for item in bundle}
            weight = sum(item[1] for item in bundle)
            if (weight > data["max_kg"] or
                any(set(pair) <= names for pair in data["excludes"]) or
                any(trigger in names and needed not in names for trigger, needed in data["requires"])):
                continue
            feasible += 1
            points = sum(item[2] for item in bundle)
            if best is None or points > best:
                best = points
                winners = []
            if points == best:
                winners.append({"manifest":sorted(names),"kg":weight})
    return {"optimal_points":best,"optimal_feasible_manifests":winners,"candidate_count":candidates,
            "feasible_count":feasible}


def utc_interval_union(data):
    aligned = [(parse_utc(start),parse_utc(end)) for start,end in data["intervals"]]
    minute = timedelta(minutes=1)
    minutes = set()
    for start,end in aligned:
        if end < start or (end-start) % minute:
            raise ValueError("Expected increasing minute-aligned interval")
        minutes.update(start + index*minute for index in range((end-start)//minute))
    disjoint = []
    for tick in sorted(minutes):
        if disjoint and disjoint[-1][1] == tick:
            disjoint[-1][1] = tick + minute
        else:
            disjoint.append([tick,tick+minute])
    return {"aligned_intervals_utc":[[time_label(start),time_label(end)] for start,end in aligned],
            "disjoint_intervals_utc":[[time_label(start),time_label(end)] for start,end in disjoint],
            "total_minutes":len(minutes)}


def forecast_scope(data):
    hours = Fraction(int((parse_utc(data["valid_time"])-parse_utc(data["initialization"])).total_seconds()), 3600)
    expected = Fraction(data["installed_horizon_hours"])
    return {"derived_horizon_hours":str(hours),"installed_horizon_hours":str(expected),
            "compatible":hours==expected,"grid_aligned":all((Fraction(data[key])*4).denominator == 1
                                                            for key in ("latitude", "longitude")),
            "execution_allowed":False,"state":"INCOMPATIBLE" if hours != expected else "MISSING_AUTHORIZATION",
            "needed_equivalent_horizon_hours_tag":f"f{int(hours):03}"}


def missing_required_evidence(data):
    if data["authorized_logs"]:
        raise ValueError("This oracle is registered for missing input only")
    return {"disposition":"MISSING_INPUT","numerical_result":None,
            "required_inputs":["authorized paired volume and duration measurements"],
            "accessed_sources":[]}


def concentration_balance(data):
    contributions = []
    for volume,volume_unit,concentration,concentration_unit in data["batches"]:
        liters = Fraction(volume)*{"mL":Fraction(1,1000),"L":Fraction(1)}[volume_unit]
        mg_per_liter = Fraction(concentration)*{"mg/L":1,"g/L":1000}[concentration_unit]
        if liters < 0 or mg_per_liter < 0:
            raise ValueError("Nonnegative volumes and concentrations required")
        contributions.append((liters,liters*mg_per_liter))
    volume = sum(liters for liters,_ in contributions)
    mass = sum(mass for _,mass in contributions)
    concentration = mass/volume
    return {"final_volume_l":str(volume),"solute_mass_mg":str(mass),
            "final_concentration_mg_per_l":str(concentration),
            "mass_reconstructed_from_output_mg":str(concentration*volume),
            "mass_by_row_mg":[str(mass) for _,mass in contributions]}


def choose_source_revision(data):
    fixture_bytes = (HERE / data["fixture"]).read_bytes()
    revisions = json.loads(fixture_bytes)["revisions"]
    cutoff = parse_utc(data["cutoff"])
    control = []
    for revision in sorted(revisions, key=lambda row:(parse_utc(row["published"]),row["id"]),reverse=True):
        if parse_utc(revision["published"])>cutoff:
            status = "outside cutoff"
        elif revision["status"]!="observed":
            status = "unobserved"
        elif len(set(revision["fingerprints"])) != 2:
            status = "duplicate sources"
        else:
            return {"revision":revision["id"],"matched_fingerprints":revision["fingerprints"],
                    "higher_rank_exclusions":control,"input_sha256":sha256(fixture_bytes).hexdigest()}
        control.append({"revision":revision["id"],"reason":status})
    return {"disposition":"MISSING_INPUT","higher_rank_exclusions":control,
            "input_sha256":sha256(fixture_bytes).hexdigest()}


def two_lane_minimax(data):
    budget = data["row_budget"]
    if budget != 1:
        raise ValueError("This exact reference handles two pure allocator actions")
    options = ((1,0),(0,1))
    lines = {}
    for name, opponent_budget, weights in data["scenarios"]:
        for choice in range(opponent_budget+1):
            competitor = (choice,opponent_budget-choice)
            points = [sum(w*((x>y)-(x<y)) for x,y,w in zip(action,competitor,weights)) for action in options]
            lines[(name,competitor)] = (Fraction(points[1]),Fraction(points[0]-points[1]))
    candidates = {Fraction(0),Fraction(1)}
    for (b1,m1),(b2,m2) in itertools.combinations(lines.values(),2):
        if m1 != m2:
            cross = (b2-b1)/(m1-m2)
            if 0 <= cross <= 1:
                candidates.add(cross)
    worst = lambda p: min(base+slope*p for base,slope in lines.values())
    best = max(sorted(candidates),key=worst)
    v = worst(best)
    adversary_points = [(name,base,slope) for name,(base,slope) in lines.items() if base+slope*best==v]
    witness = []
    upper = None
    for (name1,b1,m1),(name2,b2,m2) in itertools.combinations(adversary_points,2):
        if m1 != m2 and m1*m2 <= 0:
            probability = -m2/(m1-m2)
            combined_slope = probability*m1+(1-probability)*m2
            combined_base = probability*b1+(1-probability)*b2
            upper = max(combined_base,combined_base+combined_slope)
            witness = [{"scenario":name[0],"allocation":name[1],"probability":str(mass)}
                       for name,mass in ((name1,probability),(name2,1-probability))]
            break
    if upper is None:
        name,base,slope = min(adversary_points,key=lambda item:max(item[1],item[1]+item[2]))
        upper = max(base,base+slope)
        witness = [{"scenario":name[0],"allocation":name[1],"probability":"1"}]
    return {"weight_on_first_lane":str(best),"weight_on_second_lane":str(1-best),"value":str(v),
            "exact_lower":str(v),"exact_upper":str(upper),"adversary_witness":witness,
            "matrix_columns":[{"scenario":name[0],"allocation":name[1],"payoffs":[str(base+slope),str(base)]}
                              for name,(base,slope) in lines.items()]}


ORACLES = {f.__name__: f for f in (
    inverse_affine,inventory_enumeration,utc_interval_union,forecast_scope,
    missing_required_evidence,concentration_balance,choose_source_revision,two_lane_minimax,
)}


def main():
    registration = (HERE/"REGISTRATION.json").read_bytes()
    assert sha256(registration).hexdigest() == REGISTRATION
    assets = json.loads(registration)["files"]
    for name in ("held_missions.json","revisions.json"):
        assert sha256((HERE/name).read_bytes()).hexdigest() == assets[name]
    cases = json.loads((HERE/"held_missions.json").read_bytes())
    results = {}
    for case in cases:
        oracle = ORACLES[case["oracle"]]
        results[case["id"]] = {
            "oracle":case["oracle"],
            "initial":oracle(case["input"]),
            "confirmation":[oracle(inputs) for inputs in case.get("confirmation",[])],
        }
    with (HERE/"MISSION-GROUND-TRUTH.json").open("x") as output:
        json.dump({"registration":REGISTRATION,"results":results},output,ensure_ascii=False,indent=2,sort_keys=True)
        output.write("\n")


if __name__ == "__main__":
    main()
