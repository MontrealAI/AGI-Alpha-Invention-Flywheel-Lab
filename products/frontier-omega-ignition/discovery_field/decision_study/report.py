"""Replay the registered four contexts and separately inspect answer-specific scientific reviews."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import evaluate as study


def evaluate_record(path, reviews):
    receipt = json.loads(path.read_text())
    arms_by_schema = {"ignition/scoped-included-observation/1": {"direct"},
                      "ignition/scoped-qwen-observation/1": {"direct", "prepared"}}
    if receipt.get("schema") not in arms_by_schema:
        raise ValueError("Unknown observation schema")
    routes = arms_by_schema[receipt["schema"]]
    if receipt["schema"] == "ignition/scoped-qwen-observation/1":
        pinned = {"missions.json", "sources.json", "evaluate.py", "observe.py"}
        if set(receipt["source_hashes"]) != pinned or any(
            study.sha((study.HERE / name).read_bytes()) != receipt["source_hashes"][name] for name in pinned
        ):
            raise ValueError("Recorded source differs from the measured runner or research inputs")
        for trial in receipt["cases"]:
            wire = trial["execution"]
            if wire.get("status") == "completed" and (
                    wire.get("reported_model") != receipt["model"]
                    or wire.get("response_sha256") != trial["answer_sha256"]):
                raise ValueError("Completed public model answer differs from its HARNESS receipt")
    replay = study.replay(path)
    if {(row["context"], row["route"]) for row in replay} != {
        (n, route) for n in range(1, 5) for route in routes
    }:
        raise ValueError("Missing or unexpected registered arm")
    out = []
    for trial, row in zip(receipt["cases"], replay, strict=True):
        verdict = row["verdict"]
        review = reviews.get(trial["answer_sha256"])
        result = {"context": trial["context"], "route": trial["route"],
                  "decision_label_correct": verdict["narrow_decision"],
                  "narrow_evidence_decision": verdict["evidence_decision_accepted"],
                  "scientific_review": review}
        result["reviewed_fact_and_proposed_test"] = (
            verdict["evidence_decision_accepted"] and verdict["design_fields_present"]
            and isinstance(review, dict) and review.get("claim_faithful") is True
            and review.get("proposed_test_usable") is True
        )
        out.append(result)
    return out


def report(directory):
    review = json.loads((directory / "scientific_review.json").read_text())
    arms = {}
    seen = set()
    for name in ("included", "qwen"):
        path = directory / (name + ".json")
        rec = json.loads(path.read_text())
        checks = evaluate_record(path, review["by_answer_sha256"])
        for trial in rec["cases"]:
            seen.add(trial["answer_sha256"])
        for route in sorted({row["route"] for row in checks}):
            selected = [row for row in checks if row["route"] == route]
            operating = [r["execution"] for r in rec["cases"] if "execution" in r and r["route"] == route]
            metered = len(operating) == len(selected) and all(
                isinstance(r.get("usage"), dict) and all(isinstance(r["usage"].get(k), int)
                for k in ("input_tokens", "output_tokens")) for r in operating)
            costs = None
            if metered:
                costs = {"calls": sum(r["application_model_calls"] for r in operating),
                         "input_tokens": sum(r["usage"]["input_tokens"] for r in operating),
                         "output_tokens": sum(r["usage"]["output_tokens"] for r in operating),
                         "request_wall_seconds": round(sum(r["wall_seconds"] for r in operating), 3),
                         "price": None}
            arms[name + "_" + route] = {"cases": selected, "metered_requests": costs,
                "decision_labels_correct": sum(row["decision_label_correct"] for row in selected),
                "narrow_accepted": sum(row["narrow_evidence_decision"] for row in selected),
                "reviewed_fact_and_proposed_test": sum(row["reviewed_fact_and_proposed_test"] for row in selected),
                "denominator": len(selected)}
    if seen != set(review["by_answer_sha256"]):
        raise ValueError("An answer is missing its recorded manual scientific review or an extra review is present")
    comparisons = [study.assess(n, study.conventional(n)) for n in range(1, 5)]
    arms["conventional_lookup"] = {"narrow_accepted": sum(c["evidence_decision_accepted"] for c in comparisons),
                                   "denominator": len(comparisons), "proposed_test_produced": False}
    return arms


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--directory", type=Path, default=study.HERE)
    opts = cli.parse_args()
    print(json.dumps(report(opts.directory), indent=2, ensure_ascii=False))
