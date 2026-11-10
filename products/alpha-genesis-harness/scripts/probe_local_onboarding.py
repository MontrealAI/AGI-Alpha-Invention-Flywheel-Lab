#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Operate real local inference through the customer HTTP onboarding workflow.

Requires caller-supplied llama.cpp and GGUF bytes. No download, cloud inference,
credential, or paid resource is requested. Results include failures unchanged.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
from pathlib import Path
import platform
import resource
import subprocess
import sys
import threading
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.adapters import Runtime
from bridge.server import HarnessServer


def sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", type=int, default=18767)
    parser.add_argument("--alias", default="Qwen3-1.7B-Q4_K_M")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    paths = [ROOT / "bridge" / name for name in ("adapters.py", "services.py", "server.py", "onboarding.py", "workflows.py", "instruments.py", "streaming.py")]
    paths.append(Path(__file__))
    identities = lambda: {str(p.relative_to(ROOT)): sha(p) for p in paths}
    record = {"schema": "alpha-genesis-live-local-onboarding/v1", "created_at": datetime.now(timezone.utc).isoformat(),
              "platform": platform.platform(), "source_sha256": identities(), "status": "NOT_TESTED", "runs": [],
              "scope": "Current source-byte local onboarding, construction, export and bounded reuse regression. Fixed arithmetic cases are public regression cases, not fresh research confirmation or a general invention advantage.",
              "model": {"configured_alias": args.alias, "weights_sha256": sha(args.model), "weights_bytes": args.model.stat().st_size,
                        "server_sha256": sha(args.server)},
              "protocol": {"policies": ["single-model", "actor-critic"], "construction_cases": [{"x": 3, "expected": 6}, {"x": 0, "expected": 0}],
                           "export_case": {"x": 17, "expected": 34}, "reuse_case": {"x": 41, "expected": 82},
                           "max_iterations": 3, "max_actions": 10, "max_output_tokens": 2048, "context_window": 16384,
                           "strong_control": "Direct multiplication and ordinary equal-content reuse; both calculate 82. No advantage presumed."}}
    command = [str(args.server.resolve()), "-m", str(args.model.resolve()), "--host", "127.0.0.1", "--port", str(args.port),
               "-c", "16384", "-t", "2", "--n-gpu-layers", "0", "--no-webui", "--alias", args.alias,
               "--chat-template-kwargs", '{"enable_thinking":false}', "--reasoning-budget", "0"]
    record["model"]["server_arguments"] = ["-m", "PINNED_MODEL.gguf", *command[3:]]
    started = time.monotonic()
    cpu_before = resource.getrusage(resource.RUSAGE_CHILDREN)
    process, harness, thread = None, None, None
    log = (args.output / "server.log").open("wb")
    try:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        for _ in range(120):
            if process.poll() is not None:
                raise RuntimeError("Local model server exited before readiness.")
            try:
                with urlopen(f"http://127.0.0.1:{args.port}/health", timeout=1) as response:
                    if response.status == 200:
                        break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError("Local server did not become ready within the readiness probe.")
        config = {"local_only": True, "timeout_seconds": 300, "allow_paid_requests": False, "session_budget_usd": 0}
        harness = HarnessServer(("127.0.0.1", 0), Runtime(config), config=config, workspace=args.output / "workspace")
        thread = threading.Thread(target=harness.serve_forever, daemon=True)
        thread.start()
        token = None
        def request(path, data=None):
            connection = http.client.HTTPConnection("127.0.0.1", harness.server_port, timeout=600)
            headers = {"X-Harness-Client": "browser"}
            if token:
                headers["X-Harness-Token"] = token
            if data is not None:
                headers["Content-Type"] = "application/json"
            try:
                connection.request("GET" if data is None else "POST", path, body=None if data is None else json.dumps(data), headers=headers)
                response = connection.getresponse()
                value = json.loads(response.read())
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}: {value.get('error', {}).get('code', 'UNKNOWN')}")
                return value
            finally:
                connection.close()
        token = request("/api/session")["token"]
        record["discovery"] = request("/api/local-models/discover", {"engine": "llama-cpp", "port": args.port})
        if args.alias not in [item["id"] for item in record["discovery"]["models"]]:
            raise RuntimeError("Expected installed model was absent from the catalog.")
        connection = request("/api/local-models/connect", {"engine": "llama-cpp", "port": args.port, "model": args.alias,
                              "consent": True, "save": True, "json_mode": False, "streaming": False, "tool_calling": False,
                              "max_output_tokens": 2048, "context_window": 16384})
        record["onboarding"] = {key: connection[key] for key in ("connected", "saved", "inference_verified", "provider")}
        provider_id = connection["provider"]["id"]
        for policy in record["protocol"]["policies"]:
            roles = {"builder": {"provider": provider_id, "model": args.alias}}
            if policy == "actor-critic":
                roles["critic"] = dict(roles["builder"])
            spec = {"objective": "Construct calculator.json with declared input x and output result = x * 2. Return only the requested JSON action object. This is an arithmetic software qualification, not an empirical claim.",
                    "context": "Use the construct_instrument tool. The operator prepared the expected outputs. No document is required.",
                    "roles": roles, "strategy": policy, "acceptance": [{"kind": "instrument", "artifact": "calculator.json", "input": {"x": 3}, "expected": {"result": 6}},
                    {"kind": "instrument", "artifact": "calculator.json", "input": {"x": 0}, "expected": {"result": 0}}],
                    "max_iterations": 3, "max_actions": 10, "max_output_tokens": 2048, "local_only": True}
            state = request("/api/workflows/create", {"spec": spec})
            arm_started = time.monotonic()
            while state["status"] in {"ready", "running"}:
                state = request("/api/workflows/step", {"run_id": state["id"]})
                print(json.dumps({"policy": policy, "status": state["status"], "model_calls": state["model_calls"]}), flush=True)
            exported = request("/api/workflows/export", {"run_id": state["id"]})
            (args.output / (policy + "-project.json")).write_text(json.dumps(exported, indent=2) + "\n")
            entry = {"policy": policy, "status": state["status"], "wall_seconds": time.monotonic() - arm_started,
                     "model_calls": state["model_calls"], "iterations": state["iteration"], "actions": state["actions"],
                     "verification": state["verification"], "artifacts": state["artifacts"],
                     "events": [{"kind": row["kind"], "detail": row["detail"]} for row in state["events"] if row["kind"] in {"model_completed", "model_failed", "model_error", "critique", "tool_refused"}]}
            if state["status"] == "complete":
                external = args.output / (policy + "-export")
                external.mkdir()
                for name, content in exported["files"].items():
                    if Path(name).name != name:
                        raise RuntimeError("Unexpected exported path.")
                    (external / name).write_text(content)
                (external / "input.json").write_text('{"x":17}')
                execution = subprocess.run([sys.executable, "RUN_INSTRUMENT.py", "calculator.json", "input.json"], cwd=external, capture_output=True, text=True)
                output = json.loads(execution.stdout) if execution.returncode == 0 else None
                entry["external_execution"] = {"returncode": execution.returncode, "result": output,
                                               "accepted": execution.returncode == 0 and output.get("output") == {"result": 34}}
                entry["reuse"] = request("/api/workflows/reuse", {"capability_id": state["id"], "input": {"x": 41}})
                entry["reuse_accepted_on_frozen_case"] = entry["reuse"]["outputs"]["calculator.json"]["output"] == {"result": 82}
                entry["strong_control"] = {"output": {"result": 41 * 2}, "accepted": True, "advantage": "NOT_ESTABLISHED; direct arithmetic and ordinary reuse tie."}
                entry["constructed_instrument"] = json.loads(exported["files"]["calculator.json"])
            record["runs"].append(entry)
            (args.output / "RESULT.json").write_text(json.dumps(record, indent=2) + "\n")
        record["status"] = "PASS" if all(row["status"] == "complete" and row.get("external_execution", {}).get("accepted") and row.get("reuse_accepted_on_frozen_case") for row in record["runs"]) else "FAIL"
    except Exception as error:
        record.update(status="FAIL", error={"type": type(error).__name__, "message": str(error)})
    finally:
        if harness:
            harness.shutdown(); harness.server_close()
        if thread:
            thread.join()
        if process:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
        log.close()
        after = identities()
        record["source_unchanged_during_execution"] = record["source_sha256"] == after
        if not record["source_unchanged_during_execution"]:
            record["source_after_sha256"] = after
            record["status"] = "FAIL_SOURCE_CHANGED"
        cpu_after = resource.getrusage(resource.RUSAGE_CHILDREN)
        record["resources"] = {"wall_seconds": time.monotonic() - started,
                               "child_cpu_seconds": cpu_after.ru_utime + cpu_after.ru_stime - cpu_before.ru_utime - cpu_before.ru_stime,
                               "separately_billed_model_requests": 0, "complete_cost_known": False,
                               "unknown_costs": ["hardware", "electricity", "engineering", "maintenance", "opportunity cost"]}
        (args.output / "RESULT.json").write_text(json.dumps(record, indent=2) + "\n")
        print(json.dumps({"status": record["status"], "runs": len(record["runs"]), "output": str(args.output / "RESULT.json")}))
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
