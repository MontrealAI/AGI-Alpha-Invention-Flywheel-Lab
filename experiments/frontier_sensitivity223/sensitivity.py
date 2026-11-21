#!/usr/bin/env python3
"""Independent, hypothetical measurement-error sensitivity for frozen chemistry decisions.

All numeric uncertainty radii are *assumed*, not observed or calibrated.
This module never changes the original decision tools, sources or evidence.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, localcontext
import hashlib
import itertools
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
OWNER = HERE.parent / "frontier_first_proof_20261121"
PROTOCOL = HERE / "PROTOCOL.json"
SOURCE_HASHES = {
    "amidation.csv": "e77f6a498387888eec63423265d6feb9d8b1ff9299b8afbc3bcc1218a7e5857a",
    "nib-etoh.csv": "d5216a673eefbaacc4ae961f4ff6acb73dbc1c83e37d0548fa7eaf84bbe5607c",
}
COVER_SHA256 = "786867bdffc2502ecd816b043b4a974f86faf7dba8a3a3bdcd7de89a965c95d7"
RADII = ("0", "0.25", "0.5", "1", "2", "5")
FRACTION = Decimal("0.90")
GAP = Decimal("20")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pinned_bytes(path: Path, expected_sha256: str) -> bytes:
    raw = path.read_bytes()
    if digest(raw) != expected_sha256:
        raise ValueError("PINNED_INPUT_CHANGED: " + path.name)
    return raw


def validated_parent():
    pinned_bytes(OWNER / "cover.py", COVER_SHA256)
    p = json.loads(PROTOCOL.read_text(encoding="utf8"))
    if tuple(p["cases"]["error_radii_percentage_points"]) != RADII:
        raise ValueError("PROTOCOL_CHANGED")
    if p["pin"]["owner_head"] != "b211c461874051f29827345fc96f82d0d196fc12":
        raise ValueError("OWNER_PIN_CHANGED")
    if p["cases"]["amidation_relative_fraction_percent"] != 90 or p["cases"]["ethanol_ligand_gap_percentage_points"] != 20:
        raise ValueError("CONTRACT_CHANGED")
    return p


def load_amidation(source: Path):
    raw = pinned_bytes(source, SOURCE_HASHES["amidation.csv"])
    rows = list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    required = {"base_name", "solvent_name", "activator_name", "nucleophile_id", "yield"}
    if not rows or not required <= set(rows[0]):
        raise ValueError("AMIDATION_COLUMNS")
    recipes = sorted({(r["base_name"], r["solvent_name"], r["activator_name"]) for r in rows})
    subs = sorted({r["nucleophile_id"] for r in rows})
    cells = {}
    for r in rows:
        key = (r["nucleophile_id"], (r["base_name"], r["solvent_name"], r["activator_name"]))
        if not all(key[1]) or not key[0] or key in cells:
            raise ValueError("AMIDATION_DUPLICATE_OR_EMPTY")
        value = Decimal(r["yield"])
        if not value.is_finite():
            raise ValueError("NONFINITE")
        cells[key] = value
    if (len(recipes), len(subs), len(cells)) != (96, 10, 960):
        raise ValueError("AMIDATION_SHAPE")
    matrix = [[cells[(s,c)] for c in recipes] for s in subs]
    if any(max(row) <= 0 for row in matrix):
        raise ValueError("NONPOSITIVE_BEST")
    return subs, recipes, matrix


def load_ethanol(source: Path):
    raw = pinned_bytes(source, SOURCE_HASHES["nib-etoh.csv"])
    reader = csv.DictReader(raw.decode("utf-8").splitlines())
    if reader.fieldnames != ["", "electrophile_id", "ligand_name", "yield"]:
        raise ValueError("ETHANOL_COLUMNS")
    cells = {}
    indices = set()
    for row in reader:
        key = (row["electrophile_id"], row["ligand_name"])
        if not all(key) or key in cells or row[""] in indices:
            raise ValueError("ETHANOL_DUPLICATE_OR_EMPTY")
        indices.add(row[""])
        y = Decimal(row["yield"])
        if not y.is_finite():
            raise ValueError("NONFINITE")
        cells[key] = y
    subs = sorted({s for s, _ in cells})
    ligands = sorted({l for _,l in cells})
    if (len(subs), len(ligands), len(cells)) != (33, 23, 759):
        raise ValueError("ETHANOL_SHAPE")
    return subs, ligands, cells


def fixed_assignment_guaranteed(row: list[Decimal], c: int, epsilon: Decimal, fraction: Decimal = FRACTION) -> bool:
    """Exact guarantee for a *fixed assignment* under independent cell errors.

    If c is lowered to y_c-e, that same cell cannot simultaneously be raised
    to y_c+e when forming the true row maximum. Other cells may be raised.
    """
    if not row or len(row) < 2 or not 0 <= c < len(row) or epsilon < 0 or not 0 < fraction <= 1:
        raise ValueError("INVALID_AMIDATION_ASSUMPTIONS")
    if not all(y.is_finite() for y in row):
        raise ValueError("NONFINITE")
    low = row[c] - epsilon
    worst_max = max(low, max(v + epsilon for j, v in enumerate(row) if j != c))
    if worst_max <= 0:
        return False  # relative yield undefined if the resulting maximum is nonpositive
    return low >= fraction * worst_max


def robust_amidation_incidence(matrix, epsilon):
    if epsilon < 0:
        raise ValueError("NEGATIVE_EPSILON")
    return [[j for j in range(len(matrix[i])) if fixed_assignment_guaranteed(matrix[i], j, epsilon)]
            for i in range(len(matrix))]


def robust_ethanol_incidence(subs, ligands, cells, epsilon):
    """Preserve the *full* 253-pair denominator; no silent eligible-subset reduction."""
    if epsilon < 0:
        raise ValueError("NEGATIVE_EPSILON")
    pairs = list(itertools.combinations(ligands, 2))
    requirements = []
    for a, b in pairs:
        row = [i for i, s in enumerate(subs)
               if abs(cells[(s,a)] - cells[(s,b)]) >= GAP + 2 * epsilon]
        requirements.append(row)
    return pairs, requirements


def qualified_min_cover(options, requirements):
    """Original exact solver with separately authored checker, or full-universe refusal."""
    if not requirements or any(not row for row in requirements):
        return {"status": "INFEASIBLE_FULL_UNIVERSE", "empty_rows": [i for i, r in enumerate(requirements) if not r]}
    if str(OWNER) not in sys.path:
        sys.path.insert(0, str(OWNER))
    from cover import solve_cover, canonical_problem
    result = solve_cover(list(options), requirements, node_limit=1000000)
    if result.get("status") != "OPTIMAL":
        raise RuntimeError("SOLVER_NOT_OPTIMAL")
    checker_dir = str(OWNER / "independent")
    if checker_dir not in sys.path:
        sys.path.insert(0, checker_dir)
    from verify_certificate import verify
    problem = canonical_problem(list(options), requirements)
    checked = verify(problem, result["certificate"])
    if not checked.get("accepted") or checked.get("optimum") != result["cardinality"]:
        raise ValueError("INDEPENDENT_PROOF_REJECTED")
    return {"status": "OPTIMAL", "minimum_options": result["cardinality"],
            "selected_option_ids": [options[j] for j in result["selected"]],
            "proof_sha256": digest(json.dumps(result["certificate"], sort_keys=True, separators=(",", ":")).encode()),
            "independent_checker": {"accepted": True, "optimum": checked["optimum"],
                                    "checked_states": checked["checked_states"]},
            "proof_nodes": result["stats"]["proof_nodes"]}


def original_first_selection():
    data = json.loads((OWNER / "evidence" / "first_portfolio.json").read_text(encoding="utf8"))
    primary = [c for c in data["cases"] if c["fraction_percent"] == 90]
    if len(primary) != 1 or primary[0]["result"]["cardinality"] != 5:
        raise ValueError("FROZEN_FIRST_SELECTION_CHANGED")
    return primary[0]["result"]["selected"]


def original_ethanol_selection():
    data = json.loads((OWNER / "evidence" / "successor.json").read_text(encoding="utf8"))
    cases = [r for r in data["results"] if r["case_id"] == "nib-etoh.csv:20"]
    if len(cases) != 1 or cases[0]["answer"]["cardinality"] != 6:
        raise ValueError("FROZEN_ETHANOL_SELECTION_CHANGED")
    return cases[0]["selected_substrates"]


def evaluate(data_dir: Path):
    start = time.perf_counter()
    protocol = validated_parent()
    subs, recipes, matrix = load_amidation(data_dir / "amidation.csv")
    ethanol_subs, ligands, cells = load_ethanol(data_dir / "nib-etoh.csv")
    first_indices = original_first_selection()
    ethanol_original = original_ethanol_selection()
    if len(set(first_indices)) != 5 or any(type(j) is not int or not 0 <= j < len(recipes) for j in first_indices):
        raise ValueError("FIRST_SELECTION_INVALID")
    if len(set(ethanol_original)) != 6 or any(s not in ethanol_subs for s in ethanol_original):
        raise ValueError("ETHANOL_SELECTION_INVALID")
    results=[]
    for label in RADII:
        e=Decimal(label)
        first_reqs=robust_amidation_incidence(matrix,e)
        first_fixed=[subs[i] for i,r in enumerate(first_reqs) if not any(j in r for j in first_indices)]
        first_opt=qualified_min_cover([str(i) for i in range(len(recipes))],first_reqs)
        pairs,second_reqs=robust_ethanol_incidence(ethanol_subs,ligands,cells,e)
        ethanol_index={s:i for i,s in enumerate(ethanol_subs)}
        second_fixed=[list(pairs[i]) for i,r in enumerate(second_reqs)
                      if not any(ethanol_index[s] in r for s in ethanol_original)]
        second_opt=qualified_min_cover(ethanol_subs,second_reqs)
        if len(pairs)!=253 or len(subs)!=10 or len(ethanol_subs)!=33:
            raise ValueError("DENOMINATOR_CHANGED")
        results.append({"epsilon_percentage_points":label,"amidation":{
            "full_denominator":10,"original_five_fail_count":len(first_fixed),
            "original_five_failing_substrates":first_fixed,
            "robust_infeasible_substrates":[subs[i] for i in first_opt.get("empty_rows",[])],
            "reoptimized":first_opt},
            "ethanol":{"full_denominator":253,"original_six_fail_count":len(second_fixed),
            "original_six_failing_pairs":second_fixed,
            "robust_infeasible_pairs":[list(pairs[i]) for i in second_opt.get("empty_rows",[])],
            "reoptimized":second_opt}})
    return {"schema":"frontier-sensitivity223-results/v1",
            "protocol_sha256":digest(PROTOCOL.read_bytes()),
            "original_owner_head":protocol["pin"]["owner_head"],
            "original_asset_sha256":COVER_SHA256,
            "source_sha256":SOURCE_HASHES,
            "assumed_uncertainty_not_empirical":True,
            "comparison_scope":"Fixed assignments vs robust optimal finite set cover under hypothetical independent symmetric per-cell errors.",
            "results":results,
            "wall_seconds":time.perf_counter()-start,
            "claims":{"prospective_lab_reliability":"NOT_ESTABLISHED",
                      "experimental_uncertainty_bound":"UNKNOWN",
                      "economic_value":"NOT_ESTABLISHED",
                      "causal_invention_advantage":"NOT_ESTABLISHED",
                      "first_and_second_tools":"EXISTING_RESEARCH_ASSETS_UNCHANGED"}}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--data-dir",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    if a.output.exists():
        raise SystemExit("OUTPUT_EXISTS: preserve prior receipts")
    result=evaluate(a.data_dir)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open("x",encoding="utf8") as f:
        json.dump(result,f,indent=2,ensure_ascii=False)
        f.write("\n")
    for case in result["results"]:
        print(json.dumps({"epsilon":case["epsilon_percentage_points"],
            "first_original_failed":case["amidation"]["original_five_fail_count"],
            "first_opt":case["amidation"]["reoptimized"]["status"],
            "first_min":case["amidation"]["reoptimized"].get("minimum_options"),
            "second_original_failed":case["ethanol"]["original_six_fail_count"],
            "second_opt":case["ethanol"]["reoptimized"]["status"],
            "second_min":case["ethanol"]["reoptimized"].get("minimum_options")}),flush=True)


if __name__=="__main__":
    main()
