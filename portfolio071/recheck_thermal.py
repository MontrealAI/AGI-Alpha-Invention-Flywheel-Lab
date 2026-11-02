"""Recheck disclosed original cases after correcting the registered tolerance.

This is an implementation correction after observing original confirmation
results. It is deliberately not reported as new blind confirmation.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

from portfolio071.verification import check_delivery, identity, receipt
from portfolio071.verify_thermal import run


def recheck(original, output):
    original, output = Path(original), Path(output)
    old = json.loads((original / "RESULTS.json").read_text())
    report = run(output)
    if len(old["fresh_cases"]) != len(report["fresh_cases"]):
        raise AssertionError("Original case family changed")
    changed = []
    for before, after in zip(old["fresh_cases"], report["fresh_cases"]):
        if before["case"] != after["case"] or before.get("request") != after.get("request"):
            raise AssertionError("Original request changed")
        for key in ("accepted", "expected_feasible", "returned_feasible", "independent_acceptance"):
            if before.get(key) != after.get(key):
                changed.append({"case": before["case"], "field": key,
                                "original": before.get(key), "corrected": after.get(key)})
    carried = []
    for name in ("k1", "k2"):
        value = json.loads((original / (name + ".json")).read_text())
        previous = value["independent_receipt"]
        corrected = receipt(value["request"], value["artifact"])
        if previous["request_sha256"] != corrected["request_sha256"] or previous["artifact_sha256"] != corrected["artifact_sha256"]:
            raise AssertionError("Original accepted artifact changed")
        if previous["accepted"] != corrected["accepted"]:
            changed.append({"case": name, "field": "accepted", "original": previous["accepted"], "corrected": corrected["accepted"]})
        value["independent_receipt"] = corrected
        value["evidence_stage"] = "Identical original artifact rechecked after tolerance implementation correction; not new blind confirmation."
        (output / (name + ".json")).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        carried.append({"case": name, "unchanged_request_sha256": corrected["request_sha256"],
                        "unchanged_artifact_sha256": corrected["artifact_sha256"],
                        "old_tolerance": previous["numeric_tolerance"], "corrected_tolerance": corrected["numeric_tolerance"],
                        "maximum_violation": corrected["max_violation"], "accepted": corrected["accepted"]})
        for row in report["fresh_cases"]:
            if row["case"] == name:
                row["artifact_hash"] = corrected["artifact_sha256"]
    # Post-disclosure regression guards demonstrate that the material tolerance
    # interval now rejects a residual the initial implementation admitted.
    ref = json.loads((original / "k2.json").read_text())
    corrected_tol = check_delivery(ref["request"], ref["artifact"])["numeric_tolerance"]
    old_tol = ref["independent_receipt"]["numeric_tolerance"]
    boundary = []
    for label, delta, expected in (("within_registered_tolerance", corrected_tol / 2, True),
                                   ("between_registered_and_initial_tolerances", (corrected_tol + old_tol) / 2, False)):
        artifact = copy.deepcopy(ref["artifact"])
        artifact["delivered_kw"][0] += delta
        result = check_delivery(ref["request"], artifact)
        if result["accepted"] is not expected:
            raise AssertionError("Tolerance regression guard failed")
        boundary.append({"case": label, "injected_residual": delta, "accepted": result["accepted"],
                         "original_tolerance_would_accept": result["max_violation"] <= old_tol})
    amendment = {"schema": "portfolio071/implementation-correction/v1",
                 "issue": "Root source audit found checker used 1e-7 times scale, while frozen preregistration requires absolute 1e-6 plus relative 1e-8 times scale.",
                 "original_results_sha256": hashlib.sha256((original / "RESULTS.json").read_bytes()).hexdigest(),
                 "original_verifier_sha256": ref["independent_receipt"]["verifier_sha256"],
                 "corrected_verifier_sha256": identity(),
                 "preregistration_changed": False, "constructor_changed": False,
                 "evaluation_stage": "Disclosed original case recheck following implementation correction; no new blind confirmation claim.",
                 "original_artifacts_rechecked": carried, "changed_decisions": changed,
                 "post_disclosure_regression_guards": boundary,
                 "remaining_scope": "Independent checks of an idealized engineering model, without physical qualification."}
    report["implementation_correction"] = amendment
    report["evidence_stage"] = amendment["evaluation_stage"]
    (output / "RESULTS.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    (output / "PROTOCOL_DEVIATION.json").write_text(json.dumps(amendment, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"changed_decisions": changed, "original_artifacts_rechecked": carried, "corrected_verifier_sha256": identity()}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    recheck(args.original, args.output)
