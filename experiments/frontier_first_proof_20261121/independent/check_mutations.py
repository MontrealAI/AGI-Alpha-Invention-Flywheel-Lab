#!/usr/bin/env python3
"""Concrete semantic and proof counterexamples for the independent verifier."""
import argparse
import copy
import hashlib
import json
import time
from pathlib import Path

from verify_certificate import (Rejected, canonical_hash, source_bound_first_record,
                                source_bound_successor_record, verify)


def run(source_root, evidence_root):
    first = json.loads((evidence_root / "first_portfolio.json").read_text())
    successor = json.loads((evidence_root / "successor.json").read_text())
    cases = []
    start = time.perf_counter()

    def mutation(label, original, mutate, check):
        candidate = copy.deepcopy(original)
        mutate(candidate)
        try:
            check(candidate)
        except Rejected as error:
            cases.append({"mutation": label, "rejected": True, "reason": str(error)})
        else:
            raise AssertionError(f"MUTATION_WRONGLY_ACCEPTED:{label}")

    first_check = lambda r: source_bound_first_record(r, source_root / "amidation.csv")
    successor_check = lambda r: source_bound_successor_record(r, source_root)
    first_check(first)
    successor_check(successor)
    mutation("displayed_recipe_wrong_base", first, lambda r: r["cases"][3]["recipes"][0].update(base_name="WRONG"), first_check)
    mutation("assignment_wrong_yield", first, lambda r: r["cases"][3]["assignments"][0].update(recorded_yield_percent="99.99"), first_check)
    mutation("assignment_wrong_maximum", first, lambda r: r["cases"][3]["assignments"][0].update(recorded_maximum_percent="99.99"), first_check)
    mutation("assignment_wrong_threshold", first, lambda r: r["cases"][3]["assignments"][0].update(required_yield_percent="0"), first_check)
    mutation("assignment_wrong_source_line", first, lambda r: r["cases"][3]["assignments"][0].update(csv_line=999), first_check)
    mutation("assignment_wrong_substrate_name", first, lambda r: r["cases"][3]["assignments"][0].update(substrate_name="WRONG"), first_check)
    mutation("assignment_missing_substrate", first, lambda r: r["cases"][3]["assignments"].pop(), first_check)
    mutation("assignment_unselected_condition", first, lambda r: r["cases"][3]["assignments"][0].update(
        condition_index=next(j for j in range(96) if j not in r["cases"][3]["result"]["selected"])), first_check)
    mutation("covered_substrates_false", first, lambda r: r["cases"][3].update(covered_substrates=9), first_check)
    mutation("best_single_coverage_false", first, lambda r: r["cases"][3].update(best_single_condition_coverage=10), first_check)
    mutation("source_url_wrong", first, lambda r: r.update(source_url="https://example.invalid/data.csv"), first_check)
    mutation("source_negative_yield_clipped", first, lambda r: r.update(recorded_yield_range_percent=["0", "98.71"]), first_check)
    mutation("first_case_omission", first, lambda r: r["cases"].pop(), first_check)
    mutation("successor_displayed_selection_wrong", successor, lambda r: r["results"][2]["selected_substrates"].__setitem__(0, "s999"), successor_check)
    mutation("successor_witness_substrate_unselected", successor, lambda r: r["results"][2]["source_linked_pair_witnesses"][0].update(substrate="s999"), successor_check)
    mutation("successor_witness_gap_wrong", successor, lambda r: r["results"][2]["source_linked_pair_witnesses"][0].update(absolute_gap_percentage_points="100"), successor_check)
    mutation("successor_witness_source_line_wrong", successor, lambda r: r["results"][2]["source_linked_pair_witnesses"][0]["source_rows"][0].update(csv_line=999), successor_check)
    mutation("successor_witness_source_yield_wrong", successor, lambda r: r["results"][2]["source_linked_pair_witnesses"][0]["source_rows"][0].update({"yield": "100"}), successor_check)
    mutation("successor_witness_pair_missing", successor, lambda r: r["results"][2]["source_linked_pair_witnesses"].pop(), successor_check)
    mutation("successor_omitted_pair_missing", successor, lambda r: r["results"][4]["indistinguishable_pairs"].pop(), successor_check)
    mutation("successor_omitted_maximum_wrong", successor, lambda r: r["results"][4]["indistinguishable_pairs"][0].update(maximum_recorded_gap="0"), successor_check)
    mutation("successor_omitted_source_wrong", successor, lambda r: r["results"][4]["indistinguishable_pairs"][0]["source_rows_at_maximum"][0].update(csv_line=999), successor_check)
    mutation("successor_pair_denominator_wrong", successor, lambda r: r["results"][2].update(full_pair_denominator=252), successor_check)
    mutation("successor_cohort_mislabeled", successor, lambda r: r["results"][2]["source"].update(solvent="methanol"), successor_check)
    mutation("successor_case_omission", successor, lambda r: r["results"].pop(), successor_check)

    problem = {"schema": "frontier-cover-instance/v1", "option_ids": ["a", "b", "c", "d"],
               "requirements": [[0, 1], [0, 2], [1, 3]]}
    certificate = {"schema": "frontier-min-cover-proof/v1", "problem_sha256": canonical_hash(problem),
                   "optimum": 2, "selected": [0, 1], "root": 1,
                   "nodes": [{"type": "capacity"}, {"type": "branch", "row": 0,
                   "children": [[0, 0], [1, 0]], "dominated": []}]}
    verify(problem, certificate)
    check_proof = lambda c: verify(problem, c)
    mutation("proof_wrong_problem_hash", certificate, lambda c: c.update(problem_sha256="0" * 64), check_proof)
    mutation("proof_duplicate_selection", certificate, lambda c: c.update(selected=[0, 0]), check_proof)
    mutation("proof_boolean_index", certificate, lambda c: c.update(selected=[False, 1]), check_proof)
    mutation("proof_missing_branch", certificate, lambda c: c["nodes"][1]["children"].pop(), check_proof)
    mutation("proof_duplicate_branch", certificate, lambda c: c["nodes"][1]["children"].append([0, 0]), check_proof)
    mutation("proof_forward_cycle", certificate, lambda c: c["nodes"][1]["children"].__setitem__(0, [0, 1]), check_proof)

    def false_dominance(c):
        c["nodes"][1]["children"] = [[0, 0]]
        c["nodes"][1]["dominated"] = [[1, 0]]
    mutation("proof_false_dominance", certificate, false_dominance, check_proof)
    mutation("proof_context_invalid_shared_leaf", certificate,
             lambda c: c["nodes"].__setitem__(0, {"type": "packing", "rows": [2]}), check_proof)
    mutation("proof_false_empty_requirement", certificate,
             lambda c: c["nodes"].__setitem__(0, {"type": "empty", "row": 2}), check_proof)
    forged_problem = {"schema": "frontier-cover-instance/v1", "option_ids": ["a", "b", "c", "d"],
                      "requirements": [[0, 1], [0, 2], [0, 3]]}
    forged = {"schema": "frontier-min-cover-proof/v1", "problem_sha256": canonical_hash(forged_problem),
              "optimum": 2, "selected": [0, 1], "root": 0, "nodes": [{"type": "capacity"}]}
    try:
        verify(forged_problem, forged)
    except Rejected as error:
        cases.append({"mutation": "proof_false_capacity_lower_bound", "rejected": True, "reason": str(error)})
    else:
        raise AssertionError("FALSE_CAPACITY_ACCEPTED")
    forged["nodes"] = [{"type": "packing", "rows": [0, 1]}]
    try:
        verify(forged_problem, forged)
    except Rejected as error:
        cases.append({"mutation": "proof_overlapping_packing", "rejected": True, "reason": str(error)})
    else:
        raise AssertionError("OVERLAPPING_PACKING_ACCEPTED")
    return {"schema": "frontier-independent-verifier-mutations/v1", "valid_first_cases": 5,
            "valid_successor_cases": 10, "valid_shared_dag_example": 1, "mutants_tested": len(cases),
            "mutants_rejected": sum(x["rejected"] for x in cases), "cases": cases,
            "wall_seconds": time.perf_counter() - start,
            "test_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "verifier_sha256": hashlib.sha256(Path(__file__).with_name("verify_certificate.py").read_bytes()).hexdigest(),
            "scope": "Concrete source-output and proof integrity regressions; no claim of exhaustive adversarial security."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    results = run(args.source_root, args.evidence_root)
    args.output.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({k: v for k, v in results.items() if k != "cases"}, indent=2))
