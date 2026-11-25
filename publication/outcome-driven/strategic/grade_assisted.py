"""Grade a separately frozen direct assisted interpretation of the held briefs."""

import argparse
import json
from pathlib import Path

from formalize import FIELDS, fingerprint, read_jsonl
from grade import grade


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("cases", "oracle", "linkage", "observed", "predictions", "output"):
        parser.add_argument("--" + field, type=Path, required=True)
    args = parser.parse_args()
    cases = read_jsonl(args.cases)
    expected = read_jsonl(args.oracle)
    guesses = read_jsonl(args.predictions)
    linkage = json.loads(args.linkage.read_bytes())
    observed = json.loads(args.observed.read_bytes())
    if linkage["cases_sha256"] != fingerprint(args.cases) or linkage["oracle_sha256"] != fingerprint(args.oracle):
        raise ValueError("The held identities changed")
    if observed["input_sha256"] != fingerprint(args.cases) or observed["predictions_sha256"] != fingerprint(args.predictions):
        raise ValueError("The observed direct input or output changed")
    case_ids = [case["id"] for case in cases]
    reference = {row["id"]: {field: row[field] for field in FIELDS} for row in expected}
    if set(reference) != set(case_ids) or len(cases) != len(expected) or len(cases) != linkage["count"]:
        raise ValueError("The held roster changed")
    if [row["id"] for row in guesses] != case_ids or any(set(row) != ({"id"} | set(FIELDS)) for row in guesses):
        raise ValueError("The direct prediction roster changed")
    predictions = {
        "arms": {"included_assisted": [{field: row[field] for field in FIELDS} for row in guesses]},
        "elapsed_seconds": {},
    }
    score, exact, _ = grade(cases, reference, predictions)
    report = {
        "schema": "frontier/strategic-formalizer-assisted-assay-v1",
        "comparison_scope": "Exploratory included-Codex assistance on the same locked input-only panel after registration. Different compute. Outside the preregistered admission gate.",
        "frozen_linkage_sha256": fingerprint(args.linkage),
        "observed_sha256": fingerprint(args.observed),
        "predictions_sha256": fingerprint(args.predictions),
        "cases": len(cases), "compatible_cases": len(exact),
        "score": score["included_assisted"],
    }
    with args.output.open("x", encoding="utf-8") as sink:
        json.dump(report, sink, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        sink.write("\n")
    print(json.dumps({k: report["score"][k] for k in ("cases", "full_outcome", "false_solver_proposals",
                                                      "certified_supported", "timing", "units", "missing")}))


if __name__ == "__main__":
    main()
