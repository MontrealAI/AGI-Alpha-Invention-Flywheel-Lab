"""Independent LP and full network-equation verification of DC box witnesses."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

from research.grid_uncertainty130 import _matrix, connected, validate


def independently_verify(model, candidate, tolerance=1e-5):
    validate(model)
    if not connected(model):
        raise AssertionError("DISCONNECTED_BASE")
    u = np.array(candidate["radii_non_slack_mw"], dtype=float)
    if u.shape != (len(model["buses"]) - 1,) or not np.isfinite(u).all() or np.any(u < 0):
        raise AssertionError("INVALID_BOX")
    p = np.asarray(model["p_mw"][1:], dtype=float)
    base = float(model["base_mva"])
    expected_outages = [None] + [b["id"] for b in model["branches"] if b["status"]]
    outputs = candidate["outcomes"]
    if len(outputs) != len(expected_outages) or [x["outage_id"] for x in outputs] != expected_outages:
        raise AssertionError("OUTAGE_SET_CHANGED")
    checks, islands, unsafe, unrated, worst_gap, worst_residual = 0, 0, 0, 0, 0.0, 0.0
    examples = []
    for obj in outputs:
        outage = next((i for i,b in enumerate(model["branches"]) if b["id"] == obj["outage_id"]), None)
        if obj["outage_id"] is not None and outage is None:
            raise AssertionError("UNKNOWN_OUTAGE")
        if not connected(model, outage):
            islands += 1
            if obj["status"] != "ISLANDING_UNKNOWN" or obj["rated"] or obj["unrated_ids"]:
                raise AssertionError("ISLANDING_MISLABEL")
            continue
        active, a, w, shift, B = _matrix(model, outage)
        rated = [b for _,b in active if b["rate_mw"] > 0]
        no_rating = [b["id"] for _,b in active if b["rate_mw"] == 0]
        if [x["branch_id"] for x in obj["rated"]] != [b["id"] for b in rated] or obj["unrated_ids"] != no_rating:
            raise AssertionError("BRANCH_SET_OR_RATING_CHANGED")
        n = len(p)
        eq = np.hstack([B, -np.eye(n) / base])
        rhs = p / base + a.T @ (w * shift)
        bound = [(None,None)] * n + [(-float(x),float(x)) for x in u]
        observed_overload = False
        for i, (row_index, branch) in enumerate(active):
            if branch["rate_mw"] <= 0:
                unrated += 1
                continue
            item = next(q for q in obj["rated"] if q["branch_id"] == branch["id"])
            extrema = []
            for direction in (-1.0, 1.0):
                objective = np.zeros(2*n, dtype=float)
                objective[:n] = -direction * base * w[i] * a[i]
                opt = linprog(objective, A_eq=eq, b_eq=rhs, bounds=bound,
                              method="highs")
                if not opt.success:
                    raise AssertionError("INDEPENDENT_LP_UNRESOLVED:" + opt.message)
                extrema.append(float(base * w[i] * (a[i] @ opt.x[:n] - shift[i])))
            expect = max(map(abs, extrema))
            reported = item["maximum_absolute_mw"]
            if not math.isfinite(reported):
                raise AssertionError("NONFINITE_CERTIFICATE")
            worst_gap = max(worst_gap, abs(reported - expect))
            if abs(reported-expect) > tolerance:
                raise AssertionError(f"LP_GAP_{branch['id']}:{reported}!= {expect}")
            delta = np.asarray(item["attaining_delta_non_slack_mw"], dtype=float)
            if delta.shape != (n,) or not np.isfinite(delta).all() or np.any(np.abs(delta) > u + 1e-10):
                raise AssertionError("WITNESS_OUTSIDE_BOX")
            theta = np.linalg.solve(B, (p + delta)/base + a.T @ (w*shift))
            residual = np.max(np.abs(B @ theta - (p+delta)/base - a.T @ (w*shift)))
            worst_residual = max(worst_residual, float(residual))
            if residual > 1e-8:
                raise AssertionError("KIRCHHOFF_RESIDUAL")
            attained = abs(base * w[i] * (a[i] @ theta - shift[i]))
            if abs(attained-reported) > tolerance:
                raise AssertionError("WITNESS_NOT_ATTAINING")
            observed_overload = observed_overload or (expect > float(branch["rate_mw"]) + 1e-6)
            if item["line_rating_mw"] != float(branch["rate_mw"]) or item["violates_rating"] != (expect > float(branch["rate_mw"]) + 1e-6):
                raise AssertionError("VIOLATION_MISLABEL")
            if len(examples) < 2 and item["violates_rating"]:
                examples.append({"outage_id":obj["outage_id"], "branch_id":branch["id"],
                                 "worst_mw":reported, "limit_mw":item["line_rating_mw"]})
            checks += 1
        expected_status = ("UNRATED_NO_COMPLETE_CERTIFICATE" if no_rating else
                           "MODEL_UNSAFE" if observed_overload else
                           "DC_BOX_N1_WITHIN_DECLARED_RATED_LIMITS")
        if obj["status"] != expected_status:
            raise AssertionError("FALSE_SAFETY_STATUS")
        if observed_overload:
            unsafe += 1
    if worst_gap > tolerance or worst_residual > 1e-8:
        raise AssertionError("VERIFICATION_ERROR")
    return {"lp_checked_rated_branch_outage_pairs": checks,
            "islanding_outages": islands, "outcomes_with_overload": unsafe,
            "unrated_line_instances": unrated, "maximum_lp_gap_mw":worst_gap,
            "maximum_equation_residual_per_unit":worst_residual,
            "sample_violations":examples}


def verify_file(candidate_path, output_path):
    from grid_screen import load_case
    root=Path(__file__).resolve().parents[1]
    raw=Path(candidate_path).read_bytes()
    # Canonical JSON not a signature; independently recompute against frozen case bytes.
    candidate=json.loads(raw)
    if candidate.get("schema")!="grid-uncertainty130/candidate/v1" or len(candidate.get("case_records", []))!=6:
        raise AssertionError("CANDIDATE_SCHEMA")
    details=[]
    expected_cases=("pglib_opf_case14_ieee.m", "pglib_opf_case30_ieee.m")
    for j,rec in enumerate(candidate["case_records"]):
        name=expected_cases[j//3]
        fraction=(0.0,0.02,0.1)[j%3]
        path=root/"research"/name
        if rec["case_name"]!=name or rec["authored_fraction"]!=fraction or rec["case_bytes_sha256"]!=hashlib.sha256(path.read_bytes()).hexdigest():
            raise AssertionError("FROZEN_CASE_CHANGED")
        model=load_case(path)
        reference_radii=[fraction*max(abs(p),1.0) for p in model["p_mw"][1:]]
        if not np.allclose(rec["radii_non_slack_mw"], reference_radii, rtol=0,atol=1e-12):
            raise AssertionError("FROZEN_BOX_CHANGED")
        data=independently_verify(model,rec)
        details.append({"case":name,"box_fraction":fraction,"source_bytes_sha256":rec["case_bytes_sha256"],**data})
    receipt={"schema":"grid-uncertainty130/independent-lp-receipt/v1",
             "accepted":True,"claim_tier":"CONDITIONAL_FIXED_DC_MODEL_ONLY_NO_GRID_OR_COMMERCE",
             "candidate_sha256":hashlib.sha256(raw).hexdigest(),"summary":details,
             "actual_buyer_acceptance":None,"actual_commerce_profit_usd":None,"trailing_365_profit_usd":None,
             "frontier_model_or_host_dollar_bill":None,"decision":"HOLD_NO_BID_NO_DEPLOY"}
    path=Path(output_path)
    if path.exists():
        raise FileExistsError("OUTPUT_MUST_BE_CREATE_ONLY")
    path.write_text(json.dumps(receipt,sort_keys=True,allow_nan=False,indent=2)+"\n")


def main():
    parser=argparse.ArgumentParser(description="Independent full-post-outage LP audit; no physical acceptance")
    parser.add_argument("--candidate",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    a=parser.parse_args()
    verify_file(a.candidate,a.output)


if __name__=="__main__":
    main()
