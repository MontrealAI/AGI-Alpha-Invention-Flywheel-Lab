"""Check frozen strategic predictions, whole outcomes and exact certificates."""

import argparse
from collections import Counter
from fractions import Fraction
import json
from pathlib import Path
import sys
from time import perf_counter

from formalize import COMPATIBLE, FIELDS, compile_reviewed, fingerprint, read_jsonl, review_case

EVALUATION = Path(__file__).resolve().parents[2] / "evidence-bound" / "evaluation"
sys.path.insert(0, str(EVALUATION))
from strategic_reference import exact

REQUIRED_ARMS = {"ordinary_rules_and_numeric_tool"} | {
    f"{prefix}_{style}" for prefix in ("base", "adapted")
    for style in ("direct", "method", "retrieval", "method_with_numeric_tool", "retrieval_with_numeric_tool")
}


def check_certificate(result, truth, case):
    if result["disposition"] != "certified_scoped":
        raise ValueError("A bound check needs a certified scoped game")
    if result["solver_input"] != {key: case[key] for key in ("id", "payoffs", "accuracy", "fee")}:
        raise ValueError("Solver input changed the authorized facts")
    values = result["exact_bounds"]
    independent_buy = Fraction(truth["purchase_before_fee"]) - case["fee"]
    if (Fraction(values["BUY"]) != independent_buy or values["SKIP"] != truth["skip"]
            or result["decision"] != truth["choice"]):
        raise ArithmeticError("Independent exact value and compiler disagree")


def grade(cases, oracle, predictions):
    started = perf_counter()
    references = {}
    for case in cases:
        truth = review_case(case, oracle[case["id"]])
        if truth == COMPATIBLE:
            game = {key: case[key] for key in ("payoffs", "accuracy", "fee")}
            exact_reference = exact(game)
            check_certificate(compile_reviewed(case, truth, truth), exact_reference, case)
            references[case["id"]] = exact_reference
    independent_solver_seconds = perf_counter() - started
    results = {}
    for name, guesses in predictions["arms"].items():
        metrics = Counter(all_fields=0, certified_supported=0, full_outcome=0, false_solver_proposals=0,
                          true_withheld=0, timing=0, units=0, missing=0)
        outcomes = []
        for case, prediction in zip(cases, guesses, strict=True):
            ident = case["id"]
            truth = oracle[ident]
            result = compile_reviewed(case, prediction, truth)
            metrics.update({field: prediction[field] == truth[field] for field in FIELDS})
            metrics.update(all_fields=prediction == truth,
                           false_solver_proposals=prediction == COMPATIBLE and truth != COMPATIBLE)
            accepted = result["disposition"] in ("certified_scoped", "withhold")
            metrics.update(full_outcome=accepted, true_withheld=result["disposition"] == "withhold")
            if result["disposition"] == "certified_scoped":
                check_certificate(result, references[ident], case)
                metrics.update(certified_supported=1)
            outcomes.append({"id": ident, "prediction": prediction, "disposition": result["disposition"],
                             "accepted": accepted})
        results[name] = {**metrics, "cases": len(cases), "outcomes": outcomes,
                         "measured_model_inference_seconds": predictions["elapsed_seconds"].get(name)}
    return results, references, independent_solver_seconds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("train-registration", "training-result", "cases", "oracle", "predictions", "output"):
        parser.add_argument("--" + field, type=Path, required=True)
    parser.add_argument("--confirmation-registration", type=Path)
    args = parser.parse_args()
    cases = read_jsonl(args.cases)
    expected = read_jsonl(args.oracle)
    oracle = {row["id"]: {key: row[key] for key in FIELDS} for row in expected}
    if len(oracle) != len(expected) or set(oracle) != {case["id"] for case in cases}:
        raise ValueError("Reference roster differs from the input roster")
    predictions = json.loads(args.predictions.read_bytes())
    registration = json.loads(args.train_registration.read_bytes())
    training = json.loads(args.training_result.read_bytes())
    if (predictions["case_sha256"] != fingerprint(args.cases)
            or predictions["case_ids"] != [case["id"] for case in cases]
            or predictions["training_sha256"] != registration["data_sha256"]["train"]
            or set(predictions["arms"]) != REQUIRED_ARMS):
        raise ValueError("The frozen prediction inputs or denominator differ")
    if (training["registration_sha256"] != fingerprint(args.train_registration)
            or training["checkpoint"]["sha256"] != predictions["adapter_sha256"]
            or training["base_files_sha256"]["model.safetensors"] != predictions["base_weights_sha256"]
            or training["source_sha256"]["fit.py"] != predictions["run_source_sha256"]):
        raise ValueError("The fitted checkpoint, inference code or registration differ")
    conf_sha = None
    if args.confirmation_registration:
        conf_sha = fingerprint(args.confirmation_registration)
        conf = json.loads(args.confirmation_registration.read_bytes())
        if (conf["cases_sha256"] != fingerprint(args.cases) or conf["oracle_sha256"] != fingerprint(args.oracle)
                or conf["count"] != len(cases) or conf["training_registration_sha256"] != fingerprint(args.train_registration)):
            raise ValueError("Independent confirmation identities differ")
    results, references, reference_seconds = grade(cases, oracle, predictions)
    strongest = max((key for key in results if not key.startswith("adapted")),
                    key=lambda key: results[key]["full_outcome"])
    primary = registration["admission"]["primary"]
    candidate, baseline = results[primary], results[strongest]
    denominator = len(cases)
    gate = registration["admission"]
    checks = {
        "independently_authored_confirmation": conf_sha is not None,
        "minimum_full_outcome_rate": candidate["full_outcome"] >= gate["minimum_full_outcome_rate"] * denominator,
        "minimum_material_gain": 100 * (candidate["full_outcome"] - baseline["full_outcome"]) >=
        gate["minimum_material_gain_over_strongest_baseline_percentage_points"] * denominator,
        "maximum_false_solver_proposals": candidate["false_solver_proposals"] <= gate["maximum_false_solver_proposals"],
        "minimum_certified_supported_cases": candidate["certified_supported"] >= gate["minimum_certified_supported_cases"],
    }
    report = {
        "schema": "frontier/strategic-formalizer-evaluation-v1",
        "admission": "GO in tested scope" if all(checks.values()) else "NO-GO for deployment",
        "evaluation_scope": "Separately authored confirmation" if conf_sha else "Known-development diagnostic",
        "cases": len(cases), "compatible_cases": len(references), "language_counts": predictions["lang_counts"],
        "strongest_base_or_rules_arm": strongest, "primary_adapted_arm": primary, "preregistered_gate": checks,
        "predictions_sha256": fingerprint(args.predictions), "cases_sha256": fingerprint(args.cases),
        "oracle_sha256": fingerprint(args.oracle), "adapter_sha256": predictions["adapter_sha256"],
        "training_result_sha256": fingerprint(args.training_result), "grader_sha256": fingerprint(Path(__file__)),
        "registration_sha256": fingerprint(args.train_registration), "confirmation_registration_sha256": conf_sha,
        "standalone_independent_reference_sha256": fingerprint(EVALUATION / "strategic_reference.py"),
        "exact_certificate_crosscheck_seconds": reference_seconds, "exact_references": references,
        "arms": results, "peak_process_memory_bytes": predictions["max_process_memory_bytes"],
        "notes": "Compatible terms and a correctly completed exact calculation are both required. Execution uses the independent semantic contract. Withheld summaries require all requested issue fields to be correct. Model times omit authoring, separate review and full economic cost.",
    }
    with args.output.open("x", encoding="utf-8") as sink:
        json.dump(report, sink, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        sink.write("\n")
    print(json.dumps({"admission": report["admission"], "cases": len(cases), "compatible": len(references),
                      "full_outcomes": {arm: row["full_outcome"] for arm, row in results.items()},
                      "gate": checks}, ensure_ascii=False))


if __name__ == "__main__":
    main()
