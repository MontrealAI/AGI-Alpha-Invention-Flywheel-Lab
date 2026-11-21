#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Qualify a bounded program search from an authentic rejected local-model source."""
from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import time

from qualify_capability_forge import (
    AccessRuntime, ForgeWorkflow, LOADED_SOURCES, OBJECTIVE, Runtime, conventional_rows,
    save, seal, strict_json, telemetry,
)
from bridge.forge import development


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    previous = strict_json(args.previous.read_bytes())
    if previous.get("forge_status") != "exhausted" or previous.get("candidate"):
        raise ValueError("The prior model run must have exhausted exposed development.")
    root = args.output.resolve()
    root.mkdir(mode=0o700)
    model = previous["models"]["primary"]
    route = {"provider": "primary", "model": model["alias"]}
    # The route is registered for identity only. This trial never calls it.
    config = {"local_only": True, "providers": {"primary": {
        "kind": "openai", "base_url": "http://127.0.0.1:9/v1",
        "models": {model["alias"]: {"input_per_million": 0, "output_per_million": 0}},
    }}}
    runtime = AccessRuntime(Runtime(config), config, root)
    old = ForgeWorkflow(runtime, args.previous.resolve().parent / "workspaces" / "forge")
    try:
        exported = old.export(previous["forge_run"])
    finally:
        old.close()
    source_run = exported["state"]
    tested = [event for event in source_run["events"] if event["kind"] == "verification"
              and event["detail"].get("artifact")]
    source_check = max(tested, key=lambda event: sum(row["passed"] for row in event["detail"]["checks"]))
    filename = source_check["detail"]["artifact"]
    source = exported["files"][filename]
    provenance = {"run_id": source_run["id"], "candidate_sha256": source_run["artifacts"][filename]["sha256"],
                  "development_event_sha256": source_check["sha256"],
                  "model_requests": previous["forge_requests"],
                  "source_sha256": source_run["forge"]["sources"]}
    seeds, cohorts = seal()
    state = {"sources": {**LOADED_SOURCES, "study": sha256(Path(__file__).read_bytes()).hexdigest()},
             "models": {"primary": model}, "seeds": seeds, "cohorts": cohorts,
             "commitments": {name: telemetry.fingerprint(cases) for name, cases in cohorts.items()},
             "provenance": provenance, "prior_study_sha256": sha256(args.previous.read_bytes()).hexdigest(),
             "arms": {"A_development": previous["arms"]["A_development"]},
             "cost_scope": {"matched_wall_timing": False, "host_billing_usd": None, "energy_joules": None,
                            "new_model_requests_in_repair": 0},
             "restricted_E": {"status": "UNMEASURED"}}
    for name, cases in {"development": development(), **cohorts}.items():
        state["arms"]["F_" + name] = conventional_rows(cases)
        if not all(row["passed"] for row in state["arms"]["F_" + name]):
            raise ValueError("Independent verifier and conventional arm disagree.")
    save(root / "study.json", state)
    service = ForgeWorkflow(runtime, root / "workspaces" / "forge")
    try:
        mission = {**route, "objective": OBJECTIVE, "model_manifest": model}
        run = service.create_mission({**mission, "reuse": False}, sealed=(seeds, cohorts))
        started = time.perf_counter()
        run = service.repair_development(run["id"], source, provenance)
        state["repair_wall_seconds"] = time.perf_counter() - started
        state["forge_run"] = run["id"]
        state["forge_status"] = run["status"]
        state["candidate"] = run["forge"]["frozen_artifact"]
        state["arms"]["C_qualification"] = run["forge"]["results"].get("qualification", [])
        state["arms"]["C_transfer"] = run["forge"]["results"].get("transfer", [])
        save(root / "forge-workflow.json", service.export(run["id"]))
        if run["status"] == "complete":
            (root / "FORGE-TELEMETRY.zip").write_bytes(service.bundle(run["id"]))
            successor = service.create_mission({**mission, "objective": "Requalify the retained artifact on another cohort."})
            successor = service.step(successor["id"])
            state["retained_successor"] = {
                "id": successor["id"], "status": successor["status"], "calls": successor["model_calls"],
                "artifact": successor["forge"]["frozen_artifact"], "commitments": successor["forge"]["commitments"],
                "checks": {name: {"passed": sum(row["passed"] for row in cases), "total": len(cases)}
                           for name, cases in successor["forge"]["results"].items()},
            }
            save(root / "forge-successor.json", service.export(successor["id"]))
        save(root / "study.json", state)
        print(run["status"], state["candidate"], state.get("retained_successor"), flush=True)
        if run["status"] != "complete":
            raise SystemExit(1)
    finally:
        service.close()
        runtime.close()


if __name__ == "__main__":
    main()
