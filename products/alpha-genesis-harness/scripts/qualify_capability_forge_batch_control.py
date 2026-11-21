#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the whole-cohort, tool-equipped open controls with pinned local models."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import secrets
import time

from qualify_capability_forge import (
    ROUTES, cpu, delta, hosted_runtime, model_server, save, strict_json, telemetry,
)


def run(assets, binary, root, which, cases):
    outcome = {"model": None, "cases": [], "planned": len(cases)}
    with model_server(assets, binary, which, root) as (runtime, route, pid, manifest):
        outcome["model"] = manifest
        prompt = (
            f"{telemetry.TASK}\nThere are {len(cases)} independent inputs of this exact type, all authorized "
            "for local processing. An available conventional specialist solves this exact contract using "
            "rational arithmetic and returns one result per case. Select the most reliable existing tool "
            'plan for the whole batch. Reply with one JSON object {"tool":"exact_specialist"} to delegate.'
        )
        started, cpu_before = time.perf_counter(), cpu(pid)
        response = runtime.generate({**route, "run_id": "forge_batch_" + secrets.token_hex(12),
                                     "prompt": prompt, "max_output_tokens": 512, "json_mode": True})
        outcome.update({"response": response["text"], "usage": response["usage"], "cost": response["cost"],
                        "model_wall_seconds": time.perf_counter() - started,
                        "model_cpu_seconds": delta(cpu(pid), cpu_before),
                        "reported_model": response["reported_model"]})
        if strict_json(response["text"]) != {"tool": "exact_specialist"}:
            outcome["status"] = "UNUSABLE_TOOL_SELECTION"
            return outcome
        for case in cases:
            start = time.perf_counter()
            result = telemetry.conventional(case["input"])
            elapsed = time.perf_counter() - start
            start = time.perf_counter()
            expected = telemetry.verify(case["input"])
            outcome["cases"].append({"id": case["id"], "answer": result, "passed": result == expected,
                                     "application_wall_seconds": elapsed,
                                     "verification_wall_seconds": time.perf_counter() - start})
        outcome["status"] = "OBSERVED"
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--models", nargs="+", choices=ROUTES, default=list(ROUTES))
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(mode=0o700)
    frozen = strict_json(args.checkpoint.read_bytes())
    cases = frozen["cohorts"]["qualification"]
    commitment = telemetry.fingerprint(cases)
    if commitment != frozen["commitments"]["qualification"]:
        raise ValueError("Cohort source does not match the commitment.")
    binary = hosted_runtime(args.assets.resolve(), root)
    receipt = {"cohort_sha256": commitment, "scope": "Whole-cohort existing-tool control", "outcomes": {}}
    for which in args.models:
        try:
            receipt["outcomes"][which] = run(args.assets.resolve(), binary, root, which, cases)
        except (ValueError, RuntimeError, OSError, TimeoutError) as error:
            receipt["outcomes"][which] = {"status": "FAILED", "error": getattr(error, "code", type(error).__name__)}
        save(root / "batch-control.json", receipt)
        arm = receipt["outcomes"][which]
        print(which, arm["status"], sum(row["passed"] for row in arm.get("cases", [])), "/", len(cases), flush=True)


if __name__ == "__main__":
    main()
