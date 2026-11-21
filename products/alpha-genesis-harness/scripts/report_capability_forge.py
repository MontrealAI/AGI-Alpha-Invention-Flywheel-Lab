#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Summarize every observed study arm and rescore explicit string-encoded answers."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import statistics
import sys

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from bridge import forge_telemetry as telemetry
from bridge.adapters import BridgeError, strict_json
from scripts.qualify_capability_forge import comparison


def explicit_answer(response):
    """Read the final answer field with up to one extra string-escaping layer."""
    value = strict_json(response)
    if not isinstance(value, dict):
        raise ValueError("Expected a complete response object.")
    value = value.get("answer", value)
    if isinstance(value, str):
        try:
            value = strict_json(value)
        except BridgeError:
            if "\x5c\x22" not in value:
                raise
            value = strict_json(strict_json('"' + value + '"'))
    return telemetry.normalize(value)


def rescore(rows, reference):
    expected = {row["id"]: row["expected"] for row in reference}
    results = []
    for row in rows:
        answer = row.get("actual")
        if answer is None and row.get("response"):
            try:
                answer = explicit_answer(row["response"])
            except (BridgeError, ValueError, TypeError, RecursionError):
                pass
        results.append({"id": row["id"], "actual": answer, "passed": answer == expected[row["id"]],
                        "strict_passed": row.get("passed") is True, "observed_error": row.get("error")})
    return results


def measured(rows, key):
    values = [row.get(key) for row in rows if row.get(key) is not None]
    return {"seconds": sum(values) if values else None, "median": statistics.median(values) if values else None,
            "count": len(values)}


def summarize(state):
    results = {}
    for name, registered in state["arms"].items():
        rows = [row for row in registered if not row.get("pending")]
        usage = [row["usage"] for row in rows if row.get("usage") and row["usage"].get("output_tokens") is not None]
        results[name] = {
            "passed": sum(row.get("passed") is True for row in rows), "observed": len(rows),
            "errors": sorted(row["error"] for row in rows if row.get("error")),
            "wall": measured(rows, "wall_seconds"), "application_wall": measured(rows, "application_wall_seconds"),
            "verification_wall": measured(rows, "verifier_wall_seconds"), "model_cpu": measured(rows, "model_cpu_seconds"),
            "model_output_tokens": sum(item["output_tokens"] for item in usage) if usage else None,
            "reported_token_records": len(usage),
        }
    adjusted = {}
    for name in ("A_development", "A_qualification", "A_qualification_512",
                 "B_qualification", "B_qualification_512", "D_qualification", "D_qualification_512"):
        if name in state["arms"]:
            scope = "development" if name.endswith("_development") else "qualification"
            held = [row for row in state["arms"][name] if not row.get("pending")]
            adjusted[name] = rescore(held, state["arms"]["F_" + scope])
    comparisons = {}
    for arm in ("A", "B", "D", "F"):
        name = arm + "_qualification"
        candidate = state["arms"].get("C_qualification", [])
        other = state["arms"].get(name, [])
        if any(row.get("pending") for row in other):
            other = []
        comparisons[arm] = {"strict": comparison(candidate, other),
                            "exact_answer": comparison(candidate, adjusted.get(name, other))}
    return {"sources": state["sources"], "commitments": state["commitments"],
            "models": state["models"], "status": state.get("forge_status"),
            "candidate": state.get("candidate"), "forge_cost": state.get("forge_segments", []),
            "forge_requests": state.get("forge_requests", state.get("provenance", {}).get("model_requests", [])),
            "program_search_wall_seconds": state.get("repair_wall_seconds"), "accuracy_and_usage": results,
            "explicit_answer_rescore": adjusted, "comparisons": comparisons,
            "retained_successor": state.get("retained_successor"), "restricted_E": state["restricted_E"],
            "cost_scope": state["cost_scope"], "hardware": state.get("hardware"), "specialist": state.get("specialist")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    args = parser.parse_args()
    raw = args.checkpoint.read_bytes()
    report = summarize(strict_json(raw))
    report["study_checkpoint_sha256"] = sha256(raw).hexdigest()
    print(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
