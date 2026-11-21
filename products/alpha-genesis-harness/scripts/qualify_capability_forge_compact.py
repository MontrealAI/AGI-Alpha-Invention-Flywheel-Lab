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
    parser.add_argument("--resume", action="store_true", help="Continue the same cohort without retrying sent items.")
    args = parser.parse_args()
    root = args.output.resolve()
    root.mkdir(mode=0o700, exist_ok=args.resume)
    frozen = strict_json(args.checkpoint.read_bytes())
    cases = frozen["cohorts"]["qualification"]
    commitment = telemetry.fingerprint(cases)
    if commitment != frozen["commitments"]["qualification"]:
        raise ValueError("Qualification inputs do not match the prospective commitment.")
    checkpoint = root / "compact-control.json"
    if args.resume:
        receipt = strict_json(checkpoint.read_bytes())
        if receipt["commitment"] != commitment or receipt["budget_output_tokens"] != 512:
            raise ValueError("Cannot resume a changed comparison.")
        if receipt["rows"] and receipt["rows"][-1].get("pending"):
            row = receipt["rows"][-1]
            row.pop("pending")
            row.update({"error": "INTERRUPTED", "cost_unknown": True})
            save(checkpoint, receipt)
    else:
        receipt = {"commitment": commitment, "budget_output_tokens": 512, "planned": len(cases),
                   "model": None, "rows": []}
    binary = hosted_runtime(args.assets.resolve(), root)
    with model_server(args.assets.resolve(), binary, "primary", root) as (runtime, route, pid, manifest):
        if receipt["model"]:
            for key in ("weights_sha256", "threads", "context_tokens", "llama_server_sha256"):
                if receipt["model"][key] != manifest[key]:
                    raise ValueError("Cannot resume with a different model or inference configuration.")
            receipt.setdefault("earlier_server_sessions", []).append(receipt["model"])
        receipt["model"] = manifest
        for case in cases[len(receipt["rows"]):]:
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
