#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the preregistered Capability Forge Ω study with actual pinned CPU models."""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import hashlib
import json
from math import comb
import os
from pathlib import Path
import platform
import resource
import secrets
import socket
import subprocess
import sys
import time

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))

from bridge.adapters import BridgeError, Runtime, strict_json, transport
from bridge.forge import ForgeWorkflow, LOADED_SOURCES, development, seal
from bridge import forge_telemetry as telemetry
from bridge.services import AccessRuntime
from bridge.workflows import _atomic, encoded
from scripts.qualify_hosted_local import BINARY_URL, BINARY_ARCHIVE_SHA, MODEL_URL, MODEL_SHA, sha

MODEL_D_URL = ("https://huggingface.co/bartowski/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/"
               "1f629da0c8bed16b9e50cee91c70693650e66c35/Qwen2.5-Coder-7B-Instruct-Q4_K_M.gguf")
MODEL_D_SHA = "1664fccab734674a50763490a8c6931b70e3f2f8ec10031b54806d30e5f956b6"
PROTOCOL = PRODUCT / "docs" / "CAPABILITY-FORGE-PROTOCOL.md"
ROUTES = {
    "primary": ("forge-qwen3-4b", "qwen3-4b.gguf", MODEL_URL, MODEL_SHA),
    "open_challenger": ("forge-qwen-coder-7b", "qwen-coder-7b.gguf", MODEL_D_URL, MODEL_D_SHA),
}
OBJECTIVE = "Recover the exact estimable contrast across all explanations of faulty scientific telemetry."
STD_CONFIG = {"local_only": True, "timeout_seconds": 240, "max_attempts": 1, "max_concurrent_requests": 1}
THREADS = int(os.environ.get("FORGE_MODEL_THREADS", min(8, os.cpu_count() or 1)))
CONTEXT = int(os.environ.get("FORGE_MODEL_CONTEXT", 8192))


def save(path, value):
    _atomic(path, encoded(value))


def json_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cpu(pid):
    try:
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(") ", 1)[1].split()
        return (int(stat[11]) + int(stat[12])) / os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, IndexError):
        return None


def peak_rss(pid):
    try:
        fields = Path(f"/proc/{pid}/status").read_text().splitlines()
        return int(next(line for line in fields if line.startswith("VmHWM:")).split()[1]) * 1024
    except (OSError, ValueError, StopIteration):
        return None


def delta(end, start):
    return end - start if start is not None and end is not None else None


def hosted_runtime(assets, root):
    archive = assets / "llama-b12242.tar.gz"
    if sha(archive) != BINARY_ARCHIVE_SHA:
        raise ValueError("llama.cpp archive checksum mismatch")
    destination = root / ("llama-runtime-" + secrets.token_hex(6))
    binary = destination / "llama-b12242" / "llama-server"
    # Bind all extracted executables and libraries to their verified archive.
    import tarfile
    with tarfile.open(archive) as bundle:
        bundle.extractall(destination, filter="data")
    return binary.resolve()


@contextmanager
def model_server(assets, binary, which, root):
    alias, filename, url, digest = ROUTES[which]
    weights = (assets / filename).resolve()
    if sha(weights) != digest:
        raise ValueError(f"{alias}: weight checksum mismatch")
    model = {"alias": alias, "weights_sha256": digest, "weights_bytes": weights.stat().st_size,
             "weights_url": url, "model_license": "Apache-2.0", "quantization": "Q4_K_M",
             "llama_release": BINARY_URL, "llama_archive_sha256": BINARY_ARCHIVE_SHA,
             "llama_server_sha256": sha(binary), "threads": THREADS, "context_tokens": CONTEXT,
             "seed": 721638, "temperature": 0.2, "hardware_backend": "CPU"}
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    started = time.perf_counter()
    log_path = root / f"{which}-{time.time_ns()}.log"
    with log_path.open("w") as log, subprocess.Popen(
        [binary, "-m", weights, "--alias", alias, "--host", "127.0.0.1", "--port", str(port),
         "--threads", str(THREADS), "--threads-batch", str(THREADS), "--ctx-size", str(CONTEXT),
         "--parallel", "1", "--temp", "0.2",
         "--seed", "721638", "--no-ui", "--device", "none"],
        stdout=log, stderr=subprocess.STDOUT, cwd=assets, env={"LC_ALL": "C.UTF-8"}, close_fds=True,
    ) as server:
        runtime = None
        try:
            for _ in range(300):
                if server.poll() is not None:
                    raise RuntimeError(f"llama.cpp exited before readiness. Inspect {log_path.name}.")
                try:
                    if transport(base + "/health", {}, timeout=1).get("status") == "ok":
                        break
                except BridgeError:
                    time.sleep(0.2)
            else:
                raise RuntimeError("llama.cpp readiness timed out")
            model.update({"startup_wall_seconds": time.perf_counter() - started,
                          "startup_cpu_seconds": cpu(server.pid)})
            config = {**STD_CONFIG, "providers": {which: {
                "kind": "openai", "base_url": base + "/v1", "output_limit_field": "max_tokens",
                "models": {alias: {"input_per_million": 0, "output_per_million": 0,
                                   "json_mode": True, "max_output_tokens": 2048,
                                   "streaming": True}},
            }}}
            runtime = AccessRuntime(Runtime(config), config, private_root=root)
            yield runtime, {"provider": which, "model": alias}, server.pid, model
        finally:
            model["peak_server_rss_bytes"] = peak_rss(server.pid)
            if runtime is not None:
                runtime.close()
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(10)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()


def model_answer(runtime, route, case, pid, budget, with_tools):
    specification = ('An exact conventional specialist is available. For the best verified outcome '
                     'you can delegate reliably by returning {"tool":"exact_specialist"}. '
                     'Alternatively compute the result yourself.' if with_tools else
                     'Compute the result yourself. No executable tools are available.')
    prompt = (telemetry.TASK + "\n" + specification
              + '\nWhen computing, return one JSON object {"work":"brief reasoning","answer":RESULT}. '
                'You may reason before committing to the answer within this JSON object.\nInput\n'
              + encoded(case["input"]).decode())
    started, start_cpu = time.perf_counter(), cpu(pid)
    row = {"id": case["id"], "budget_output_tokens": budget, "actual": None, "passed": False}
    try:
        result = runtime.generate({"prompt": prompt, "max_output_tokens": budget, "json_mode": True,
                                   "run_id": "forge_eval_" + secrets.token_hex(12), **route})
        response = result["text"]
        row.update({"response": response, "usage": result["usage"], "cost": result["cost"],
                    "reported_model": result["reported_model"]})
        value = strict_json(response)
        if with_tools and value == {"tool": "exact_specialist"}:
            start_tool = time.perf_counter()
            row["actual"] = telemetry.conventional(case["input"])
            row["tool_wall_seconds"] = time.perf_counter() - start_tool
        elif isinstance(value, dict):
            row["actual"] = telemetry.normalize(value.get("answer", value))
        else:
            row["error"] = "INVALID_RESULT"
        row["passed"] = row["actual"] == telemetry.verify(case["input"])
    except (BridgeError, ValueError, TypeError, RecursionError) as error:
        row["error"] = getattr(error, "code", "INVALID_RESULT")
    row.update({"wall_seconds": time.perf_counter() - started, "model_cpu_seconds": delta(cpu(pid), start_cpu)})
    return row


def conventional_rows(cases):
    result = []
    for case in cases:
        start = time.perf_counter()
        expected = telemetry.verify(case["input"])
        verifier_wall = time.perf_counter() - start
        start = time.perf_counter()
        answer = telemetry.conventional(case["input"])
        result.append({"id": case["id"], "actual": answer, "passed": answer == expected,
                       "wall_seconds": time.perf_counter() - start, "verifier_wall_seconds": verifier_wall,
                       "expected": expected})
    return result


def run_model_arm(state, checkpoint, name, cases, runtime, route, pid, budget, with_tools):
    rows = state.setdefault("arms", {}).setdefault(name, [])
    if rows and rows[-1].get("pending"):
        rows[-1] = {"id": rows[-1]["id"], "passed": False, "error": "INTERRUPTED", "cost_unknown": True}
        save(checkpoint, state)
    for case in cases[len(rows):]:
        rows.append({"id": case["id"], "pending": True})
        save(checkpoint, state)
        rows[-1] = model_answer(runtime, route, case, pid, budget, with_tools)
        save(checkpoint, state)
        print(f"{name} {len(rows)}/{len(cases)}: {sum(row['passed'] for row in rows)} correct", flush=True)


def prior_diagnosis(checkpoint, runtime, commitments, model, *, new_cohorts=False):
    previous = strict_json(checkpoint.read_bytes())
    if not new_cohorts and previous["commitments"] != commitments:
        raise ValueError("Diagnosis and current trial use different sealed commitments.")
    experimental = ForgeWorkflow(runtime, checkpoint.parent / "workspaces" / "forge")
    try:
        run = experimental.get(previous["forge_run"])
    finally:
        experimental.close()
    prior = run["forge"]["model_manifest"]
    if prior["weights_sha256"] != model["weights_sha256"] or run["forge"]["frozen_artifact"]:
        raise ValueError("Diagnosis must come from the same model before any candidate was frozen.")
    events = [event for event in run["events"] if event["kind"] == "model_completed"
              and event["detail"]["role"] == "researcher"]
    text = run["research"]
    if len(events) != 1 or not text or events[0]["detail"]["response_sha256"] != hashlib.sha256(text.encode()).hexdigest():
        raise ValueError("No authenticated completed diagnosis found.")
    return {"text": text, "run_id": run["id"], "event_sha256": events[0]["sha256"],
            "model_weights_sha256": prior["weights_sha256"], "usage": events[0]["detail"]["usage"]}


def exposed_defects(checkpoint):
    old = strict_json(checkpoint.read_bytes())
    workflow = strict_json((checkpoint.parent / "forge-workflow.json").read_bytes())
    run = workflow["state"]
    if run["id"] != old["forge_run"] or run["forge"]["frozen_artifact"]:
        raise ValueError("Follow-up feedback requires a pre-qualification development rejection.")
    name = run["forge"]["active_artifact"]
    source = workflow["files"][name]
    ident = hashlib.sha256(source.encode()).hexdigest()
    if ident != run["artifacts"][name]["sha256"]:
        raise ValueError("Earlier development candidate does not match its recorded digest.")
    tree = ast.parse(source)
    loaded = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
             and node.func.id == "rational_affine"]
    notes = []
    if "faults" not in loaded:
        notes.append("The previous candidate assigned the fault allowance but never used that binding.")
    if any(len(node.args) >= 3 and isinstance(node.args[2], ast.Constant) and node.args[2].value == 1
           for node in calls):
        notes.append("Its tool calls fixed the dimension to one even for multi-dimensional states.")
    notes += [{"actual": row.get("actual"), "expected": row["expected"]}
              for row in run["verification"]["checks"] if not row["passed"]]
    return {"candidate_sha256": ident, "run_id": run["id"], "diagnostics": notes}


def forge_arm(state, checkpoint, root, runtime, route, pid, model, diagnosis_from=None,
              construction="auto", attempts=4, follow_up=None):
    service = ForgeWorkflow(runtime, root / "workspaces" / "forge")
    started, start_cpu = time.perf_counter(), cpu(pid)
    try:
        if "forge_run" not in state:
            diagnostic = prior_diagnosis(diagnosis_from, runtime, state["commitments"], model,
                                         new_cohorts=follow_up is not None) if diagnosis_from else None
            if follow_up and diagnostic is not None:
                diagnostic["development_defects"] = exposed_defects(follow_up)
            run = service.create_mission({**route, "objective": OBJECTIVE, "model_manifest": model,
                                          "reuse": False, "construction": construction},
                                         sealed=(state["seeds"], state["cohorts"]),
                                         diagnostic_record=diagnostic, attempts=attempts,
                                         observations=[{"id": r["id"], "actual": r.get("actual"), "passed": r["passed"]}
                                                       for r in state["arms"]["A_development"]])
            state["diagnostic_record"] = diagnostic
            state["forge_run"] = run["id"]
            save(checkpoint, state)
        run = service.get(state["forge_run"])
        if run["status"] in {"interrupted", "paused"}:
            run = service.resume(run["id"], background=False)
            run = service.get(state["forge_run"])
        while run["status"] == "ready":
            run = service.step(run["id"])
            print(f"C: {run['status']}, {run['model_calls']} model calls, {run['actions']} actions", flush=True)
        totals = state.setdefault("forge_segments", [])
        totals.append({"status": run["status"], "wall_seconds": time.perf_counter() - started,
                       "model_cpu_seconds": delta(cpu(pid), start_cpu)})
        save(checkpoint, state)
        if run["status"] in {"paused", "interrupted"}:
            raise RuntimeError("Forge inference paused. Inspect the checkpoint before explicit resume.")
        exported = service.export(run["id"])
        save(root / "forge-workflow.json", exported)
        state["forge_status"] = run["status"]
        state["forge_requests"] = run["request_costs"]
        state["candidate"] = run["forge"]["frozen_artifact"]
        state["arms"]["C_qualification"] = run["forge"]["results"].get("qualification", [])
        state["arms"]["C_transfer"] = run["forge"]["results"].get("transfer", [])
        if run["status"] == "complete":
            (root / "FORGE-TELEMETRY.zip").write_bytes(service.bundle(run["id"]))
            # Equal-content control: execute the same bytes without registry lookup or model calls.
            from bridge.forge_sandbox import execute
            source = exported["files"][state["candidate"]["name"]]
            state["arms"]["ordinary_reuse"] = [
                {"id": case["id"], "passed": result["answer"] == telemetry.verify(case["input"]),
                 "wall_seconds": result["wall_seconds"]}
                for case in state["cohorts"]["transfer"] if (result := execute(source, case["input"]))
            ]
            successor = service.create_mission({**route, "objective": "Apply the retained telemetry tool to a new cohort.",
                                                "model_manifest": model})
            successor = service.step(successor["id"])
            state["retained_successor"] = {"id": successor["id"], "status": successor["status"],
                                           "model_calls": successor["model_calls"],
                                           "artifact": successor["forge"]["frozen_artifact"],
                                           "commitments": successor["forge"]["commitments"],
                                           "counts": {name: {"passed": sum(r["passed"] for r in rows), "total": len(rows)}
                                                      for name, rows in successor["forge"]["results"].items()}}
            save(root / "forge-successor.json", service.export(successor["id"]))
        save(checkpoint, state)
    finally:
        service.close()


def comparison(left, right):
    left, right = ({row["id"]: row["passed"] for row in rows} for rows in (left, right))
    if not left or left.keys() != right.keys():
        return None
    wins = sum(left[key] and not right[key] for key in left)
    losses = sum(right[key] and not left[key] for key in left)
    changed = wins + losses
    pvalue = min(1.0, 2 * sum(comb(changed, i) for i in range(min(wins, losses) + 1)) / (2**changed))
    return {"wins": wins, "losses": losses, "paired_exact_p": pvalue,
            "significant_accuracy_gain": wins > losses and pvalue <= .05}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--continue-from", type=Path,
                        help="Continue a pre-construction interruption in a new source-bound workspace.")
    parser.add_argument("--follow-up-from", type=Path,
                        help="Start new sealed cohorts after a recorded development rejection.")
    parser.add_argument("--diagnosis-from", type=Path,
                        help="Reuse an authenticated prior diagnosis by the same model on the same study.")
    parser.add_argument("--construction", choices=("auto", "source", "compose"), default="auto")
    parser.add_argument("--candidate-attempts", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--first", action="store_true", help="Run development controls and Forge before the other arms.")
    parser.add_argument("--skip-d", action="store_true", help="Leave the open challenger explicitly unmeasured.")
    args = parser.parse_args()
    if sum(bool(item) for item in (args.resume, args.continue_from, args.follow_up_from)) > 1:
        parser.error("--resume, --continue-from and --follow-up-from are mutually exclusive")
    root, assets = args.output.resolve(), args.assets.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=args.resume)
    checkpoint = root / "study.json"
    sources = {**LOADED_SOURCES, "protocol": sha(PROTOCOL), "study": sha(Path(__file__))}
    if args.resume:
        state = strict_json(checkpoint.read_bytes())
        if state["sources"] != sources:
            raise ValueError("Study source changed. Continue the registered snapshot.")
    else:
        previous = strict_json(args.continue_from.read_bytes()) if args.continue_from else None
        if previous:
            if (previous.get("forge_status") or "forge_run" not in previous or previous.get("candidate")
                    or {name for name in previous["arms"] if not name.startswith("F_")} != {"A_development"}
                    or any(row.get("pending") for row in previous["arms"]["A_development"])
                    or len(previous["arms"]["A_development"]) != len(development())):
                raise ValueError("Continuation requires a completed development arm and no frozen candidate or sealed model results.")
            seeds, cohorts = previous["seeds"], previous["cohorts"]
        else:
            seeds, cohorts = seal()
        state = {"sources": sources, "seeds": seeds, "cohorts": cohorts, "models": {}, "arms": {},
                 "commitments": {name: telemetry.fingerprint(cases) for name, cases in cohorts.items()},
                 "hardware": {"platform": platform.platform(), "machine": platform.machine(),
                              "logical_cpu_count": os.cpu_count(),
                              "visible_memory_bytes": os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"),
                              "python": platform.python_version()},
                 "cost_scope": {"energy_joules": None, "host_billing_usd": None, "human_setup_seconds": None,
                                "paid_api_calls": 0},
                 "restricted_E": {"status": "UNMEASURED", "reason": "No authorized isolated reference run on comparable withheld inputs."}}
        if previous:
            if state["commitments"] != previous["commitments"]:
                raise ValueError("Continuation cohort commitment mismatch.")
            state["arms"] = previous["arms"]
            state["interrupted_predecessor"] = {"study_sha256": sha(args.continue_from), "run_id": previous["forge_run"],
                                                "models": previous["models"], "cost": previous.get("forge_segments", []),
                                                "sources": previous["sources"],
                                                "previous": previous.get("interrupted_predecessor")}
        if args.follow_up_from:
            parent = strict_json(args.follow_up_from.read_bytes())
            if parent.get("forge_status") != "exhausted" or parent.get("candidate"):
                raise ValueError("Earlier study must have exhausted development before qualification.")
            state["arms"]["A_development"] = parent["arms"]["A_development"]
            state["follow_up_parent_sha256"] = sha(args.follow_up_from)
        save(checkpoint, state)
    from flint import __version__ as flint_version
    state["specialist"] = {"method": "FLINT exact rational RREF", "python_flint": flint_version}
    binary = hosted_runtime(assets, root)
    for name, cases in {"development": development(), **state["cohorts"]}.items():
        if "F_" + name not in state["arms"]:
            state["arms"]["F_" + name] = conventional_rows(cases)
        if not all(row["passed"] for row in state["arms"]["F_" + name]):
            save(checkpoint, state)
            raise RuntimeError(f"Verifier and FLINT disagree on {name}. Study inconclusive.")
    save(checkpoint, state)
    if args.first or not state.get("primary_complete"):
        with model_server(assets, binary, "primary", root) as (runtime, route, pid, model):
            state["models"]["primary"] = model
            run_model_arm(state, checkpoint, "A_development", development(), runtime, route, pid, 2048, False)
            if all(row["passed"] for row in state["arms"]["A_development"]):
                state["forge_status"] = "NOT_RUN_NO_DEVELOPMENT_GAP"
                state["arms"].update({"C_qualification": [], "C_transfer": []})
            if "forge_status" not in state:
                forge_arm(state, checkpoint, root, runtime, route, pid, model, args.diagnosis_from,
                          args.construction, args.candidate_attempts, args.follow_up_from)
            if not args.first:
                qual = state["cohorts"]["qualification"]
                for suffix, budget in (("", 2048), ("_512", 512)):
                    for name, tools in (("A", False), ("B", True)):
                        run_model_arm(state, checkpoint, name + "_qualification" + suffix,
                                      qual, runtime, route, pid, budget, tools)
                state["primary_complete"] = True
        save(checkpoint, state)
    if not args.first and not args.skip_d and not state.get("open_challenger_complete"):
        with model_server(assets, binary, "open_challenger", root) as (runtime, route, pid, model):
            state["models"]["open_challenger"] = model
            for suffix, budget in (("", 2048), ("_512", 512)):
                run_model_arm(state, checkpoint, "D_qualification" + suffix, state["cohorts"]["qualification"],
                              runtime, route, pid, budget, True)
            state["open_challenger_complete"] = True
        save(checkpoint, state)
    rows = state["arms"]
    state["accuracy"] = {name: {"passed": sum(row["passed"] for row in results), "total": len(results)}
                         for name, results in rows.items()}
    state["comparisons"] = {arm: comparison(rows["C_qualification"], rows.get(arm + "_qualification", []))
                            for arm in ("A", "B", "D", "F")}
    usage = resource.getrusage(resource.RUSAGE_SELF)
    state.setdefault("study_driver_cpu_seconds", []).append(usage.ru_utime + usage.ru_stime)
    save(checkpoint, state)
    print(json.dumps(state["accuracy"], indent=2))


if __name__ == "__main__":
    main()
