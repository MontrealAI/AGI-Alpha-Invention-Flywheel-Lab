# SPDX-License-Identifier: Apache-2.0
"""Audit the separate included-Codex comparison using the registered references."""

from argparse import ArgumentParser
from hashlib import sha256
from pathlib import Path
import sys
from time import perf_counter

from run import canonical, contradiction, exact_row, missing_exact, numeric_correct, retained_reuse, save, verified_json


PROJECTION = ("id", "ambition", "semantics", "lang", "dataset", "schema", "facts", "metrics", "data")
PREDICTION_FIELDS = {"id", "decision", "queries", "result", "missing", "explanation"}


def grade_prediction(case, prediction, evidence, reuse, artifact, replay):
    if (set(prediction) != PREDICTION_FIELDS or prediction["decision"] not in {"ANSWER", "ABSTAIN"}
            or not isinstance(prediction["queries"], list) or len(prediction["queries"]) > 10
            or not all(isinstance(query, str) for query in prediction["queries"])
            or not isinstance(prediction["missing"], list) or not all(isinstance(x, str) for x in prediction["missing"])
            or not isinstance(prediction["result"], dict) or not isinstance(prediction["explanation"], str)):
        raise ValueError("The locked assisted prediction differs from the announced format.")
    primary = evidence["primary"]
    reference_missing = primary.get("decision") == "ABSTAIN"
    draft_error = contradiction(case, evidence, [prediction["explanation"]])
    verified_queries = []
    for sql in prediction["queries"]:
        try:
            packed = canonical(artifact(case["schema"], sql))
            executed = replay(packed, case["data"])
        except ValueError as error:
            verified_queries.append({"query": sql, "refused": str(error)})
            continue
        exact = not reference_missing and exact_row(executed["rows"], case["metrics"], primary)
        checked = {"query": sql, "artifact_sha256": sha256(packed).hexdigest(),
                   "input_sha256": executed["input_sha256"], "output_sha256": executed["output_sha256"],
                   "rows": executed["rows"], "primary_exact": exact}
        if exact:
            checked["held_reuse"] = retained_reuse(packed, case, evidence, reuse)
        verified_queries.append(checked)
    if reference_missing:
        correct = missing_exact(primary, prediction["missing"] + [prediction["explanation"]])
        false = prediction["decision"] == "ANSWER" or bool(prediction["result"]) or draft_error
        passed = prediction["decision"] == "ABSTAIN" and correct and not false
        measurements = {"precise_missing_cell": correct, "withheld_total": not false}
    else:
        correct = numeric_correct(prediction["result"], case, evidence)
        verified = any(query.get("primary_exact") for query in verified_queries)
        reusable = any(query.get("held_reuse", {}).get("matched") for query in verified_queries)
        false = prediction["decision"] == "ANSWER" and (not correct or not verified or draft_error)
        passed = prediction["decision"] == "ANSWER" and correct and reusable and not false
        measurements = {"reported_primary_exact": correct, "executed_primary_exact": verified,
                        "reusable_on_withheld": reusable}
    return {"case": case["id"], "verdict": "ACCEPT" if passed else "FAIL",
            "false_user_facing_acceptance": false, "verified_queries": verified_queries, **measurements}


def main():
    parser = ArgumentParser(description=__doc__)
    for field in ("repo", "registration", "sealed-cases", "public-cases", "reuse", "oracle", "authoring", "predictions", "output"):
        parser.add_argument("--" + field, required=True, type=Path)
    for field in ("registration-sha256", "authoring-sha256", "predictions-sha256"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    registered = verified_json(args.registration, args.registration_sha256)
    cases = verified_json(args.sealed_cases, registered["authorized_cases_sha256"])
    reuse = verified_json(args.reuse, registered["withheld_reuse_sha256"])
    gold = verified_json(args.oracle, registered["independent_oracle_sha256"])
    observed = verified_json(args.authoring, args.authoring_sha256)
    inputs = verified_json(args.public_cases, observed["cases_sha256"])
    predictions = verified_json(args.predictions, args.predictions_sha256)
    ids = [case["id"] for case in cases]
    if (inputs != [{key: case[key] for key in PROJECTION} for case in cases]
            or ids != registered["cohort"]["ordered_cases"] or [answer["id"] for answer in predictions] != ids
            or observed["predictions_sha256"] != args.predictions_sha256):
        raise ValueError("The assisted comparison differs from the locked inputs or denominator.")
    sys.path.insert(0, str(args.repo.resolve() / "products/alpha-genesis-harness"))
    from bridge.mission_tools import _artifact, _replay

    start = perf_counter()
    results = [grade_prediction(case, prediction, gold[case["id"]], reuse, _artifact, _replay)
               for case, prediction in zip(cases, predictions, strict=True)]
    result = {"schema": "frontier/outcome-driven-assisted-comparison-v1",
              "scope": "Post-registration included-Codex plus ordinary SQLite, same locked information and independent scoring. Different compute. Excluded from the registered materiality test.",
              "registration_sha256": args.registration_sha256, "cases_sha256": observed["cases_sha256"],
              "authoring_sha256": args.authoring_sha256, "predictions_sha256": args.predictions_sha256,
              "evaluated": len(results), "strict_acceptances": sum(x["verdict"] == "ACCEPT" for x in results),
              "false_acceptances": sum(x["false_user_facing_acceptance"] for x in results),
              "separate_evaluation_seconds": perf_counter() - start, "cases": results}
    save(args.output, result)
    print(f"Assisted accepted {result['strict_acceptances']}/{result['evaluated']}; false acceptances {result['false_acceptances']}.")


if __name__ == "__main__":
    main()
