#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reproduce real local single, actor/critic and parallel construction using llama.cpp."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.adapters import Runtime
from bridge.workflows import WorkflowService


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18766)
    parser.add_argument("--alias", default="local-workflow-model")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    binary, weights = args.server.resolve(), args.model.resolve()
    command = [str(binary), "-m", str(weights), "--host", "127.0.0.1", "--port", str(args.port), "-c", "8192", "-t", "2", "--n-gpu-layers", "0", "--no-webui", "--alias", args.alias,
               "--chat-template-kwargs", '{"enable_thinking":false}', "--reasoning-budget", "0"]
    log = (args.output / "server.log").open("wb")
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    record = {"schema": "alpha-genesis-live-local-workflow/v1", "protocol_revision": "explicit-json-mode-v2", "structured_output": "Explicitly configured JSON-object generation for builder and critic; independent semantic checks and original allocations unchanged. Historical unformatted failure preserved at evidence/hosted-local-3f4e1785d395.", "scope": "Actual local CPU inference against two frozen arithmetic cases. This establishes narrow construction behavior, not frontier reasoning or general invention superiority.",
              "model": {"configured_alias": args.alias, "weights_sha256": sha(weights), "server_sha256": sha(binary), "server_arguments": command[1:]},
              "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in [ROOT / "bridge/workflows.py", ROOT / "bridge/services.py", ROOT / "bridge/workflow_strategies.py", ROOT / "bridge/instruments.py", ROOT / "bridge/adapters.py", ROOT / "bridge/streaming.py", Path(__file__)]}, "runs": []}
    try:
        ready = False
        for _ in range(120):
            if process.poll() is not None:
                break
            try:
                with urlopen(f"http://127.0.0.1:{args.port}/health", timeout=1) as response:
                    ready = response.status == 200
                    if ready:
                        break
            except Exception:
                time.sleep(1)
        if not ready:
            raise RuntimeError("Explicitly selected local server did not become ready.")
        config = {"local_only": True, "timeout_seconds": 300, "providers": {"local": {"kind": "openai", "base_url": f"http://127.0.0.1:{args.port}/v1", "output_limit_field": "max_tokens", "models": {args.alias: {"input_per_million": 0, "output_per_million": 0, "max_output_tokens": 2048, "input_token_overhead": 4096, "json_mode": True}}}}}
        runtime = Runtime(config)
        service = WorkflowService(runtime, args.output / "workspace")
        for policy in ["single-model", "actor-critic", "parallel-exploration"]:
            roles = {"builder": {"provider": "local", "model": args.alias}}
            if policy == "actor-critic":
                roles["critic"] = {"provider": "local", "model": args.alias}
            spec = {"objective": "Construct calculator.json with declared input x and output result = x * 2. Return only the requested JSON action object. This is an arithmetic software qualification, not an empirical claim.", "context": "Use the construct_instrument tool. The operator prepared the expected outputs. No document is required.",
                    "roles": roles, "strategy": policy, "acceptance": [{"kind": "instrument", "artifact": "calculator.json", "input": {"x": 3}, "expected": {"result": 6}}, {"kind": "instrument", "artifact": "calculator.json", "input": {"x": 0}, "expected": {"result": 0}}],
                    "max_iterations": 3, "max_actions": 10, "max_output_tokens": 2048, "local_only": True}
            if policy == "parallel-exploration":
                spec.update(approaches=["Use direct multiplication of x by the literal 2.", "Use addition of x to itself; avoid multiplication."], max_iterations=2, max_actions=4)
            state = service.create(spec)
            started = time.monotonic()
            while state["status"] in {"ready", "running"}:
                state = service.step(state["id"])
                print(json.dumps({"policy": policy, "status": state["status"], "phase": state["phase"], "iteration": state["iteration"], "model_calls": state["model_calls"]}), flush=True)
            elapsed = time.monotonic() - started
            export = service.export(state["id"])
            (args.output / (policy + "-project.json")).write_text(json.dumps(export, ensure_ascii=False, indent=2) + "\n")
            entry = {"policy": policy, "status": state["status"], "wall_seconds": elapsed, "model_calls": state["model_calls"], "iterations": state["iteration"], "actions": state["actions"], "verification": state["verification"], "events": state["events"], "artifacts": state["artifacts"]}
            if state.get("branches"):
                entry.update(branches=state["branches"], selected_branch=state.get("selected_branch"), request_costs=state["request_costs"],
                             branch_evidence=[{"state": child["state"], "artifact_hashes": child["state"]["artifacts"], "export_sha256": child["sha256"]} for child in export["branch_exports"]])
            if state["status"] == "complete":
                external = args.output / (policy + "-export")
                external.mkdir()
                for name, content in export["files"].items():
                    (external / name).write_text(content)
                (external / "input.json").write_text('{"x":17}')
                run = subprocess.run([sys.executable, "RUN_INSTRUMENT.py", "calculator.json", "input.json"], cwd=external, capture_output=True, text=True)
                entry["external_execution"] = {"returncode": run.returncode, "result": json.loads(run.stdout) if run.returncode == 0 else None}
                entry["reuse"] = service.reuse(state["id"], {"x": 41})
                entry["strong_control"] = {"direct_arithmetic_result": 82, "accepted": entry["reuse"]["outputs"]["calculator.json"]["output"] == {"result": 82}, "advantage": "NOT_ESTABLISHED; direct arithmetic and equal-content ordinary reuse remain competent controls."}
            record["runs"].append(entry)
            record["source_unchanged"] = all(sha(ROOT / path) == expected for path, expected in record["source_sha256"].items())
            if not record["source_unchanged"]:
                raise RuntimeError("Source changed during live proof; preserve this attempt and rerun after freeze.")
            (args.output / "RESULT.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        service.close()
    except Exception as error:
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        (args.output / "RESULT.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
        raise
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()


if __name__ == "__main__":
    main()
