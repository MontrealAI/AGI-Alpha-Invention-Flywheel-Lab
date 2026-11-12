#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Qualify the exact workshop source through its private HTTP connector and portable replay."""
from __future__ import annotations

import argparse
from functools import partial
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
from uuid import uuid4
import zipfile

PRODUCT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PRODUCT))
from bridge import workshop
from scripts.qualify_hosted_local import MODEL_SHA, WORKSHOP_MODEL_ALIAS, WORKSHOP_MODEL_SHA, sha, write

PINNED_MODELS = {MODEL_SHA: "Qwen3-4B-Instruct-2507-Q4_K_M", WORKSHOP_MODEL_SHA: WORKSHOP_MODEL_ALIAS}
TERMINAL = {"complete", "cancelled", "failed", "exhausted", "needs_review", "paused", "interrupted"}


def port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def request(url, payload=None, headers=None):
    data = None if payload is None else json.dumps(payload, allow_nan=False).encode()
    request_headers = dict(headers or {})
    if data is not None:
        request_headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=request_headers)
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=15) as response:
        raw = response.read()
        return raw if response.headers.get_content_type() == "application/zip" else json.loads(raw)


def wait_ready(url, process, headers=None):
    for _ in range(200):
        try:
            return request(url, headers=headers)
        except OSError:
            if process.poll() is not None:
                raise
            time.sleep(.2)
    raise RuntimeError("The loopback process did not become ready.")


def source_identity():
    manifest = PRODUCT / "RELEASE-MANIFEST.json"
    if manifest.is_file():
        return json.loads(manifest.read_text(encoding="utf-8"))["source_revision"], None
    root = PRODUCT.parents[1]
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    tree = subprocess.check_output(["git", "rev-parse", "HEAD:products/alpha-genesis-harness"], cwd=root, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain", "--", "products/alpha-genesis-harness"], cwd=root):
        raise ValueError("Qualify a clean committed checkout or verified extracted package.")
    return revision, tree


def trial(api, output, family, ambition, *, model, prior=None, trial_name=None, **details):
    start = time.monotonic()
    name = trial_name or family + ("-fresh" if details.get("fresh") else "")
    payload = {"request_id": uuid4().hex, "family": family, "objective": ambition,
               "provider": "local", "model": model, "consent": "local", **details}
    if prior:
        payload.update(inherit=prior, loop="successor")
    state = api("register", payload)
    identity = {"run_id": state["id"], "revision": state["revision"]}
    api("start", identity)
    deadline = start + 960  # Three model attempts, each with a 300-second transport bound.
    while True:
        state = api("get", {"run_id": identity["run_id"]})
        if state["status"] in TERMINAL and not state["worker_active"]:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError("The bounded local trial did not settle.")
        time.sleep(.5)
    raw = api("bundle", dict(identity, revision=state["revision"]))
    archive = output / (name + ".zip")
    archive.write_bytes(raw)
    root = output / name
    root.mkdir()
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        bundle.extractall(root)  # This ZIP is the just-generated response from the private connector.
    replay = None
    if (root / "RUN_WORKSHOP.py").is_file():
        process = subprocess.run([sys.executable, "-B", "RUN_WORKSHOP.py", "check"], cwd=root, capture_output=True, text=True)
        write(root / "REPLAY.json", {"exit_code": process.returncode, "stdout": process.stdout, "stderr": process.stderr})
        replay = process.returncode
    receipt = {"name": name, "id": state["id"], "status": state["status"], "docket": state["docket"],
               "requests": state["requests"], "events": state["events"], "replay_exit": replay,
               "bundle_sha256": hashlib.sha256(raw).hexdigest(), "wall_seconds": time.monotonic() - start}
    print(json.dumps({key: receipt[key] for key in ("name", "status", "docket", "replay_exit")}), flush=True)
    return receipt


def run(args):
    source, tree = source_identity()
    model_sha = sha(args.model)
    model = PINNED_MODELS.get(model_sha)
    if model is None:
        raise ValueError("Pinned Qwen model checksum failed.")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    model_port, connector_port = port(), port()
    while connector_port == model_port:
        connector_port = port()
    settings = {"local_only": True, "allow_paid_requests": False, "timeout_seconds": 300, "max_attempts": 1,
                "providers": {"local": {"kind": "openai", "base_url": f"http://127.0.0.1:{model_port}/v1",
                                        "output_limit_field": "max_tokens", "models": {model: {
                                            "input_per_million": 0, "output_per_million": 0,
                                            "max_output_tokens": 3072, "input_token_overhead": 2048,
                                            "json_mode": True, "json_schema": True}}}}}
    config = output / "loopback-config.json"
    write(config, settings)
    runtime_url, app_url = f"http://127.0.0.1:{model_port}", f"http://127.0.0.1:{connector_port}"
    environment = {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "TMPDIR") if key in os.environ}
    runtime_env = dict(environment, LD_LIBRARY_PATH=str(args.runtime.parent), NO_PROXY="127.0.0.1")
    log = output / "llama.log"
    receipt = {"schema": "alpha-genesis/workshop-local-qualification/v1", "source_revision": source,
               "source_product_tree": tree, "sources_sha256": workshop.LOADED_SOURCES,
               "runtime_sha256": sha(args.runtime), "model_sha256": model_sha,
               "route": "Loopback llama.cpp CPU", "platform": sys.platform, "expected_model": model,
               "complete_economic_cost": None, "cases": [], "status": "RUNNING"}
    write(output / "RESULT.json", receipt)
    processes = []
    try:
        with log.open("wb") as stream:
            runtime = subprocess.Popen([str(args.runtime), "--model", str(args.model), "--alias", model,
                "--host", "127.0.0.1", "--port", str(model_port), "--ctx-size", "16384", "--threads", str(args.threads),
                "--parallel", "1", "--no-webui", "--temp", "0", "--seed", "315"],
                env=runtime_env, stdout=stream, stderr=subprocess.STDOUT)
        processes.append(runtime)
        wait_ready(runtime_url + "/health", runtime)
        receipt["reported_model"] = request(runtime_url + "/v1/models")["data"][0]["id"]
        with (output / "connector.log").open("wb") as stream:
            connector = subprocess.Popen([sys.executable, "launch.py", "--no-browser", "--config", str(config),
                "--port", str(connector_port), "--workspace", str(output / "private-workspace")],
                cwd=PRODUCT, env=environment, stdout=stream, stderr=subprocess.STDOUT)
        processes.append(connector)
        headers = {"X-Harness-Token": wait_ready(app_url + "/api/session", connector, {"X-Harness-Client": "browser"})["token"]}
        def api(action, body):
            return request(app_url + "/api/workshop/" + action, body, headers)
        def record(family, ambition, **kwargs):
            result = trial(api, output, family, ambition, model=model, **kwargs)
            receipt["cases"].append(result)
            write(output / "RESULT.json", receipt)
            return result
        foundry = record("foundry", "Distinguish sensor drift from defects for three independent inspection users.")
        if foundry["docket"]["status"] == "admitted":
            record("foundry", "Requalify the cold-chain logger at field-handoff conditions.", prior=foundry["id"], fresh=True)
        record("contrast", "Check scoped accessibility evidence and exceptions without rounding.")
        record("arrangement", "Decide whether a shared inspection core can be offered voluntarily within current cash.")
        record("custom", "Give a repair cooperative a reusable way to triage its next parts delivery.",
               context='Inputs arrived and reserved are nonnegative counts. Output exactly {"ready":boolean,"remaining":number}. '
                       'ready means arrived is at least reserved. remaining is max(0, arrived minus reserved).',
               cases=[{"input": {"arrived": a, "reserved": b},
                       "expected": {"ready": a >= b, "remaining": max(0, a - b)}} for a, b in [(3, 4), (17, 4), (2, 2), (0, 0)]])
        first_hash = foundry["docket"]["artifact_hashes"].get("instrument.json")
        successor = next((row for row in receipt["cases"] if row["name"] == "foundry-fresh"), {})
        receipt["unchanged_artifact_reuse"] = bool(first_hash and first_hash == successor.get("docket", {}).get("artifact_hashes", {}).get("instrument.json"))
        receipt["status"] = "PASS" if (len(receipt["cases"]) == 5 and receipt["unchanged_artifact_reuse"] and
            all(row["status"] == "complete" and row["replay_exit"] == 0 and
                any(event["kind"] == "model_completed" and event["detail"]["reported_model"] == model
                    for event in row["events"]) for row in receipt["cases"])) else "FAIL"
        if args.browser:
            browser_env = dict(environment, **{key: os.environ[key] for key in ("NODE_PATH", "WORKSHOP_CHROMIUM") if key in os.environ})
            browser = subprocess.run(["node", str(PRODUCT / "evidence" / "UI_WORKSHOP_BROWSER.cjs"),
                                      app_url + "/", "construct", str(output / "browser")], env=browser_env)
            receipt["browser_exit"] = browser.returncode
            if browser.returncode != 0:
                receipt["status"] = "FAIL"
        if args.study:
            from scripts.workshop_builder_study import run as study
            def generate(prompt):
                return request(app_url + "/api/generate", {
                    "provider": "local", "model": model, "prompt": prompt,
                    "max_output_tokens": 512, "json_mode": True, "run_id": "study_" + uuid4().hex,
                }, headers)
            try:
                comparison = study(api, generate, partial(trial, model=model), output)
            except (ValueError, OSError, RuntimeError) as error:
                comparison = {"status": "FAILED", "error": {"type": type(error).__name__, "message": str(error)}}
            write(output / "BUILDER-STUDY.json", comparison)
            receipt["builder_study_status"] = comparison["status"]
    except Exception as error:
        receipt["status"], receipt["error"] = "FAIL", {"type": type(error).__name__, "message": str(error)}
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        if workshop.source_hashes() != receipt["sources_sha256"]:
            receipt["status"], receipt["source_changed"] = "FAIL", True
        write(output / "RESULT.json", receipt)
    return 0 if receipt["status"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=lambda value: Path(value).resolve(), required=True)
    parser.add_argument("--model", type=lambda value: Path(value).resolve(), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threads", type=int, choices=range(1, 33), default=4)
    parser.add_argument("--browser", action="store_true", help="Also operate a rendered Chromium client against the real connector.")
    parser.add_argument("--study", action="store_true", help="Run the separate matched study of reusable builder guidance.")
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
