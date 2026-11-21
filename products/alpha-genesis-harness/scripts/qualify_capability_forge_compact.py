#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the compact model-alone control without giving it tools or sealed answers."""
from __future__ import annotations

import argparse
from pathlib import Path
import secrets
import time

from qualify_capability_forge import cpu, delta, hosted_runtime, model_server, save, strict_json, telemetry
from bridge.adapters import BridgeError
from bridge.workflows import encoded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(mode=0o700)
    frozen = strict_json(args.checkpoint.read_bytes())
    cases = frozen["cohorts"]["qualification"]
    commitment = telemetry.fingerprint(cases)
    if commitment != frozen["commitments"]["qualification"]:
        raise ValueError("Qualification inputs do not match the prospective commitment.")
    binary = hosted_runtime(args.assets.resolve(), root)
    receipt = {"commitment": commitment, "budget_output_tokens": 512, "planned": len(cases),
               "model": None, "rows": []}
    checkpoint = root / "compact-control.json"
    with model_server(args.assets.resolve(), binary, "primary", root) as (runtime, route, pid, manifest):
        receipt["model"] = manifest
        for case in cases:
            row = {"id": case["id"], "pending": True, "passed": False}
            receipt["rows"].append(row)
            save(checkpoint, receipt)
            prompt = (
                "Solve the following exact numerical problem without executable tools.\n" + telemetry.TASK +
                '\nReturn a single JSON object with "status" and, only for "determined", "value". '
                'You may include "work" with up to 40 words of concise reasoning. '
                'Keep status and value at the top level as fields.\nInput\n' + encoded(case["input"]).decode()
            )
            start, start_cpu = time.perf_counter(), cpu(pid)
            try:
                response = runtime.generate({**route, "run_id": "forge_compact_" + secrets.token_hex(12),
                                             "prompt": prompt, "max_output_tokens": 512, "json_mode": True, "stream": True})
                row.update({"response": response["text"], "usage": response["usage"], "cost": response["cost"],
                            "reported_model": response["reported_model"]})
                value = strict_json(response["text"])
                if not isinstance(value, dict):
                    raise ValueError("Result is not an object")
                value.pop("work", None)
                row["actual"] = telemetry.normalize(value)
                row["passed"] = row["actual"] == telemetry.verify(case["input"])
            except (BridgeError, ValueError, TypeError, RecursionError) as error:
                row["error"] = getattr(error, "code", "INVALID_RESULT")
            row.update({"wall_seconds": time.perf_counter() - start, "model_cpu_seconds": delta(cpu(pid), start_cpu)})
            row.pop("pending")
            save(checkpoint, receipt)
            print(len(receipt["rows"]), "/", len(cases), "correct:",
                  sum(r["passed"] for r in receipt["rows"]), flush=True)
    save(checkpoint, receipt)


if __name__ == "__main__":
    main()
