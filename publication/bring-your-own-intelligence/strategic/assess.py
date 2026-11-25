# SPDX-License-Identifier: Apache-2.0
"""Score frozen proposals of strategic protocols against separately reviewed facts."""

import argparse
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path
import sys

from protocols import FAMILIES, FIELDS, PUBLICATION, ProtocolEnvironment, compatibility, fingerprint, single_case, validate

sys.path.insert(0, str(PUBLICATION / "evidence-bound" / "evaluation"))
from strategic_reference import exact


NUMERIC_INPUTS = {
    "private_signaling": {"id": "scoped-noisy-signal-test", "payoffs": [[3, -1], [-2, 4], [0, 0]],
                          "accuracy": [80, 70], "fee": 0},
    "public_offer": {"price": "19/7", "value": "2.8"},
}


def approved_output(family, result):
    if result["status"] != "certified":
        return False
    inputs = NUMERIC_INPUTS[family]
    if family == "private_signaling":
        return result["value"] == exact(inputs)["purchase_before_fee"]
    price, value = map(Fraction, (inputs["price"], inputs["value"]))
    delta = value.numerator * price.denominator - price.numerator * value.denominator
    denominator = price.denominator * value.denominator
    return (result["response"] == ("accept" if delta >= 0 else "reject")
            and Fraction(result["surplus"]) * denominator == max(0, delta))


def json_file(path):
    return json.loads(Path(path).read_bytes())


def by_id(rows):
    indexed = {row["id"]: row for row in rows}
    if len(indexed) != len(rows) or not indexed:
        raise ValueError("Expected distinct case IDs")
    return indexed


def grade(cases, reference, rows):
    compatible_count = records = invalid = false_admissions = 0
    field_matches = Counter()
    language_matches = Counter()
    certified_counts = Counter()
    evidence = []
    predictions = by_id(rows)
    if cases.keys() != predictions.keys():
        raise ValueError("Each arm requires all held cases")
    for ident, case in cases.items():
        expected = validate(reference[ident]["record"])
        prediction = predictions[ident]["record"]
        if prediction is not None:
            validate(prediction)
        scope = compatibility(case["family"], expected)
        environments = ProtocolEnvironment(case, expected, NUMERIC_INPUTS[case["family"]])
        assert environments.reset() == case
        _, reward, finished, result = environments.step(prediction)
        assert finished
        proposal_compatible = prediction is not None and compatibility(case["family"], prediction)["status"] == "compatible"
        if proposal_compatible and scope["status"] != "compatible":
            false_admissions += 1
            assert reward == -2 and result["status"] != "certified"
        if prediction == expected:
            records += 1
            language_matches[case["lang"]] += 1
        if prediction is None:
            invalid += 1
        else:
            for field in FIELDS:
                field_matches[field] += prediction[field] == expected[field]
        if scope["status"] == "compatible":
            compatible_count += 1
        if result["status"] == "certified":
            if not approved_output(case["family"], result):
                raise AssertionError("Policy certificate disagrees with the conventional reference")
            certified_counts[case["family"]] += 1
        evidence.append({"id": ident, "language": case["lang"], "family": case["family"],
                         "reference_disposition": scope["status"], "full_record_match": prediction == expected,
                         "reward": reward, "proposal_compatible": proposal_compatible, "reviewed_policy": result})
    return {
        "record_matches": records, "held_cases": len(cases), "invalid_completions": invalid,
        "field_exact_matches": {field: field_matches[field] for field in FIELDS},
        "language_exact_matches": {lang: language_matches[lang] for lang in ("en", "fr")},
        "compatible_reference_cases": compatible_count, "certified_family_counts": {
            family: certified_counts[family] for family in FAMILIES},
        "false_solver_proposals": false_admissions, "false_admissions": 0,
        "cases": evidence,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("cases", "reference", "registration", "predictions", "training", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--assisted", type=Path)
    args = parser.parse_args()
    registration, raw, training = (json_file(path) for path in (args.registration, args.predictions, args.training))
    if (registration["held_input_sha256"] != fingerprint(args.cases)
            or registration["held_reference_sha256"] != fingerprint(args.reference)
            or training["registration_sha256"] != fingerprint(args.registration)
            or raw["training_sha256"] != registration["data_sha256"]["train"]
            or raw["fit_source_sha256"] != registration["source_sha256"]["fit.py"]
            or raw["cases_sha256"] != registration["held_input_sha256"]
            or raw["adapter_sha256"] != training["checkpoint"]["sha256"]
            or raw["base_weights_sha256"] != training["base_files_sha256"]["model.safetensors"]
            or set(raw["arms"]) != set(registration["model_arms"])):
        raise ValueError("Assessment inputs do not match the frozen comparison and fitted checkpoint")
    cases = by_id([single_case(case) for case in json_file(args.cases)])
    reference = by_id(json_file(args.reference))
    if len(cases) != registration["held_cases"] or reference.keys() != cases.keys():
        raise ValueError("Held references must cover the complete registered panel")
    scores = {arm: grade(cases, reference, rows) for arm, rows in raw["arms"].items()}
    adapted = scores["adapted_direct"]
    advance = (adapted["record_matches"] >= 6
               and adapted["record_matches"] > max(scores[name]["record_matches"] for name in ("base_direct", "base_retrieval"))
               and all(adapted["certified_family_counts"].values()) and not adapted["false_solver_proposals"])
    if args.assisted:
        assisted = json_file(args.assisted)
        if assisted["cases_sha256"] != fingerprint(args.cases):
            raise ValueError("Assisted comparator used different briefs")
        scores["included_assisted"] = grade(cases, reference, assisted["records"])
    report = {"schema": "frontier/strategic-protocol-assessment/v1",
              "registration_sha256": fingerprint(args.registration), "inputs_sha256": fingerprint(args.cases),
              "reference_sha256": fingerprint(args.reference), "predictions_sha256": fingerprint(args.predictions),
              "training_result_sha256": fingerprint(args.training), "assessor_source_sha256": fingerprint(__file__),
              "checkpoint_sha256": raw["adapter_sha256"], "solver_scope": NUMERIC_INPUTS,
              "grade": scores, "prediction_wall_seconds": raw["wall_seconds"],
              "assisted_predictions_sha256": fingerprint(args.assisted) if args.assisted else None,
              "advance_to_larger_confirmation": bool(advance), "deployment": "NO_GO"}
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
