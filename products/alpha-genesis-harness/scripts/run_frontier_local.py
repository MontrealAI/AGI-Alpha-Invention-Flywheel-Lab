#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run one FRONTIER stage against a hash-pinned local CPU model.

The launcher owns the model process and client in the same environment. It does
not download models, request credentials, call paid APIs or infer economic value.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import socket
import subprocess
import sys
import time
from urllib.request import build_opener, ProxyHandler

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from bridge.adapters import Runtime, strict_json
from bridge.frontier_mission import FrontierMissionService
from bridge.services import AccessRuntime
from bridge.workflows import WorkflowService, _atomic, digest, encoded, now, require


def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def server_cpu(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
        return (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, IndexError):
        return None


def server_rss(pid):
    try:
        lines = Path(f"/proc/{pid}/status").read_text().splitlines()
        return int(next(line for line in lines if line.startswith("VmHWM:")).split()[1]) * 1024
    except (OSError, ValueError, StopIteration):
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("discover", "build"))
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--server", required=True, type=Path)
    parser.add_argument("--model", required=True, type=Path)
    parser.add_argument("--model-sha256", required=True)
    parser.add_argument("--server-sha256", required=True)
    parser.add_argument("--mission", type=Path, help="Register this mission before its first discovery")
    parser.add_argument("--id", help="Continue an existing frozen mission")
    parser.add_argument("--stage", choices=("first", "second"), default="first")
    parser.add_argument("--arm", choices=("first", "with_asset", "without_asset"), default="first")
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--context", type=int, default=16384)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    require(bool(args.mission) != bool(args.id), "Supply a new mission or an existing ID.", "FRONTIER_RUN")
    require(args.action == "discover" or args.id, "Construction requires a frozen existing mission.", "FRONTIER_RUN")
    require(args.threads > 0 and args.context > 0, "Use positive actual CPU/context allocations.", "FRONTIER_RUN")
    require(not args.output.exists(), "Choose a new output file; earlier trial evidence must not be overwritten.", "FRONTIER_RUN")
    require(sha(args.model) == args.model_sha256 and sha(args.server) == args.server_sha256,
            "Pinned model or server bytes differ; no inference was launched.", "FRONTIER_RUN_SOURCE")
    args.workspace.mkdir(parents=True, exist_ok=True, mode=0o700)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    alias = "frontier-qwen-coder-7b"  # Public example route; actual bytes are independently pinned.
    identity = {"origin": "live_local_model", "model_weights_sha256": args.model_sha256,
        "server_sha256": args.server_sha256, "model_alias": alias, "context_tokens": args.context,
        "seed": 721638, "threads": args.threads, "temperature": 0.2, "hardware_backend": "CPU",
        "launcher_sha256": sha(Path(__file__).resolve()),
        "python": platform.python_version(), "system": platform.system(), "machine": platform.machine()}
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    log_path = args.workspace / ("model-" + secrets.token_hex(6) + ".log")
    record = {"schema": "frontier-local-execution/v1", "started_at": now(), "action": args.action,
        "stage": args.stage, "arm": args.arm, "runtime_identity": identity, "status": "starting",
        "startup_wall_seconds": None, "model_cpu_seconds": None, "model_peak_rss_bytes": None,
        "actual_complete_cost": None,
        "model_resource_scope": "Observed process CPU and peak RSS before shutdown; shutdown CPU is not measured.",
        "cost_scope": "Measured execution resources only; acquisition, human work, energy and host billing unknown."}
    started = time.perf_counter()
    runtime = workflows = None
    process = None
    try:
        with log_path.open("w") as log:
            process = subprocess.Popen([str(args.server.resolve()), "-m", str(args.model.resolve()),
                "--alias", alias, "--host", "127.0.0.1", "--port", str(port),
                "--threads", str(args.threads), "--threads-batch", str(args.threads),
                "--ctx-size", str(args.context), "--parallel", "1", "--temp", "0.2", "--seed", "721638",
                "--no-ui", "--device", "none"], stdout=log, stderr=subprocess.STDOUT,
                env={"LC_ALL": "C.UTF-8"}, close_fds=True)
            # Readiness is a process-health check, not a mission-wide deadline.
            while True:
                require(process.poll() is None, "Local model exited before readiness; inspect its retained log.", "FRONTIER_MODEL_START")
                try:
                    with build_opener(ProxyHandler({})).open(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                        if strict_json(response.read()).get("status") == "ok":
                            break
                except OSError:
                    pass
                time.sleep(0.2)
            record["startup_wall_seconds"] = time.perf_counter() - started
            config = {"local_only": True, "allow_paid_requests": False, "session_budget_usd": 0,
                "timeout_seconds": 600, "max_attempts": 1, "max_concurrent_requests": 1,
                "providers": {"local": {"kind": "openai", "base_url": f"http://127.0.0.1:{port}/v1",
                    "output_limit_field": "max_tokens", "models": {alias: {"input_per_million": 0,
                        "output_per_million": 0, "context_window": args.context, "max_output_tokens": min(args.context, 32768),
                        "json_mode": True, "json_schema": True, "streaming": True}}}}}
            runtime = AccessRuntime(Runtime(config), config, private_root=args.workspace)
            workflows = WorkflowService(runtime, args.workspace)
            service = FrontierMissionService(workflows)
            if args.mission:
                initial = service.register(strict_json(args.mission.read_bytes()))
                ident = initial["id"]
                state = service._load(ident)
                state["runtime_identity"] = identity
                service._save(state)
            else:
                ident = args.id
                state = service._load(ident)
                require(state["runtime_identity"] == identity, "Runtime identity changed between comparison stages.", "FRONTIER_RUNTIME_DRIFT")
            record["mission_id"] = ident
            print(json.dumps({"mission_id": ident, "stage": args.stage, "arm": args.arm, "status": "running"}), flush=True)
            result = getattr(service, args.action)({"id": ident, "stage": args.stage, "arm": args.arm})
            state = service._load(ident)
            if args.action == "build":
                state["builds"][args.arm]["execution_provenance"] = "live_local_model"
                state["builds"][args.arm]["runtime_identity_sha256"] = digest(identity)
            record.update(status="completed", mission_status=result["status"], model_cpu_seconds=server_cpu(process.pid),
                          model_peak_rss_bytes=server_rss(process.pid), wall_seconds=time.perf_counter() - started)
            state["events"].append({"kind": "local_execution", "at": now(), "record": copy_record(record)})
            service._save(state)
            record["export"] = service.export({"id": ident})
    except BaseException as error:
        record.update(status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
                      error_code=getattr(error, "code", type(error).__name__), wall_seconds=time.perf_counter() - started)
        raise
    finally:
        if process is not None:
            record["model_cpu_seconds"] = server_cpu(process.pid)
            record["model_peak_rss_bytes"] = server_rss(process.pid)
        cleanup_errors = []
        for owned in (workflows, runtime):
            if owned is not None:
                try:
                    owned.close()
                except Exception as error:
                    cleanup_errors.append(type(error).__name__)
        try:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        except Exception as error:
            cleanup_errors.append(type(error).__name__)
        if cleanup_errors:
            record["cleanup_errors"] = cleanup_errors
            if record["status"] == "completed":
                record["status"] = "completed_with_cleanup_errors"
        record["finished_at"] = now()
        record["wall_seconds"] = time.perf_counter() - started
        _atomic(args.output, encoded(record) + b"\n")
    print(json.dumps({"mission_id": record.get("mission_id"), "status": record["status"],
                      "mission_status": record.get("mission_status"), "output": str(args.output)}))


def copy_record(value):
    return strict_json(encoded(value))


if __name__ == "__main__":
    main()
