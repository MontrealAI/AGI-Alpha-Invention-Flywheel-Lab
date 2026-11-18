#!/usr/bin/env python3
"""Run a single source-bound qualification with open weights on an ordinary Linux CPU."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
import zipfile

PRODUCT = Path(__file__).resolve().parent
REPO = PRODUCT.parents[1]
HARNESS = PRODUCT.parent / "alpha-genesis-harness"
sys.path.insert(0, str(HARNESS))
from scripts import qualify_hosted_local as pinned

from ignition import construction, delivery, evaluation
from ignition.controller import CONSTRUCT_INSTRUCTION, Controller
from ignition.provider import LocalProvider
from ignition.store import Store, digest, runtime_source

MODEL_ALIAS = "Qwen3-4B-Instruct-2507-Q4_K_M"
EXAMPLE = PRODUCT / "examples" / "migration.json"
STAGES = {"discover", "challenge", "construct"}
LIVE_STREAM_ARM = "live-sources-streaming-sse-v1"
PUBLIC_ROUTES = {key for key in (
    "stage", "status", "provider", "model", "reported_model", "mode", "run_id", "request_sha256",
    "response_schema_sha256", "raw_response_sha256", "response_sha256", "error_code", "usage", "application_model_calls",
    "complete_cost_known", "wall_seconds", "recorded_at", "transport_mode", "harness_streaming_sha256",
    "stream_output_bytes", "stream_fragments")}
CHECKOUT_PATHS = [PRODUCT.relative_to(REPO).as_posix(), "products/alpha-genesis-harness/bridge",
                  "products/alpha-genesis-harness/scripts/package_release.py",
                  "products/alpha-genesis-harness/scripts/qualify_hosted_local.py"]


class Blocked(Exception):
    pass


def stamp():
    return datetime.now(timezone.utc).isoformat()


def available_threads():
    count = len(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else (os.cpu_count() or 1)
    cpu_limit = Path("/sys/fs/cgroup/cpu.max")
    if cpu_limit.is_file():
        quota, period = cpu_limit.read_text().strip().split()
        if quota.isdigit() and period.isdigit() and int(period) > 0:
            count = min(count, (int(quota) + int(period) - 1) // int(period))
    return max(1, count)


def runner_window():
    if "AGI_JOB_START_EPOCH" in os.environ:
        # Reserve the same final five minutes as the repository resource policy.
        remaining = int(os.environ["AGI_JOB_START_EPOCH"]) + 360 * 60 - 300 - time.time()
        if remaining < 1:
            raise Blocked("Actual hosted runner window exhausted.")
        return remaining
    return None


def git(*args):
    completed = subprocess.run(["git", *args], cwd=REPO, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True)
    if completed.returncode:
        raise Blocked("A checked-out Git revision is required.")
    return completed.stdout.strip()


def checked_source():
    if git("status", "--porcelain", "--untracked-files=all", "--", *CHECKOUT_PATHS):
        raise Blocked("The product or its HARNESS dependencies differ from the checked-out revision.")
    return git("rev-parse", "HEAD")


def setup_model(work, record):
    archive = work / "llama.tar.gz"
    weights = work / "model.gguf"
    runtime = work / "llama"
    try:
        runner_window()
        pinned.download(pinned.BINARY_URL, archive, pinned.BINARY_ARCHIVE_SHA, pinned.BINARY_ARCHIVE_BYTES)
        record["verified_runtime_archive_sha256"] = pinned.BINARY_ARCHIVE_SHA
        runner_window()
        pinned.download(pinned.MODEL_URL, weights, pinned.MODEL_SHA, pinned.MODEL_BYTES)
        record["verified_model_file_sha256"] = pinned.MODEL_SHA
        runtime.mkdir()
        with tarfile.open(archive) as package:
            package.extractall(runtime, filter="data")
        binaries = [p for p in runtime.rglob("llama-server") if p.is_file()]
        if len(binaries) != 1:
            raise Blocked("The verified archive did not contain one llama-server.")
        binary, = binaries
        record["verified_runtime_binary_sha256"] = pinned.sha(binary)
        return binary, weights
    except (urllib.error.URLError, OSError, ValueError, tarfile.TarError) as error:
        raise Blocked(f"Pinned open model or runtime unavailable ({type(error).__name__}).") from None


def wait_ready(server, port):
    reader = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while server.poll() is None:
        runner_window()
        try:
            with reader.open(f"http://127.0.0.1:{port}/health", timeout=5) as res:
                if json.loads(res.read(4096)).get("status") == "ok":
                    return
        except (OSError, ValueError):
            time.sleep(1)
    raise Blocked("Verified llama-server exited before it became ready.")


def compact_calls(state):
    calls = []
    for attempt in list(state["calls"].values()) + list(state.get("unsuccessful_calls", [])):
        for receipt in attempt.get("receipt") or attempt.get("receipts") or []:
            calls.append({k: receipt[k] for k in PUBLIC_ROUTES if k in receipt})
    return calls


def diagnostic(state, calls):
    """Return only product-owned categories, even if the model itself supplied a stop reason."""
    status, stage = state["status"], state["stage"]
    research = state.get("research") or {}
    decision = research.get("decision")
    if decision not in {"build", "incumbent", "defer", "stop"}:
        decision = None
    if status == "verified":
        reason = "accepted"
    elif status == "deferred":
        reason = "selection declined construction"
    elif status == "failed":
        reason = "frozen acceptance failed"
    elif calls and calls[-1].get("status") == "failed":
        reason = "local provider rejected or failed the call"
    elif stage in {"discover", "challenge", "construct"}:
        reason = {"discover": "discovery response failed the candidate contract",
                  "challenge": "challenge response failed the adjudication contract",
                  "construct": "construction response failed the artifact grammar"}[stage]
    else:
        reason = "mission prerequisite unavailable"
    return {"category": reason, "decision": decision,
            "candidate_count": len(research.get("candidates", [])),
            "executable_contract_frozen": bool(state.get("contract")),
            "artifact_built": bool(state.get("artifact"))}


def result_status(state, calls, portable):
    if state["status"] != "verified":
        return "FAIL"
    if any(call.get("status") != "completed" or call.get("mode") != "local"
           or call.get("reported_model") != MODEL_ALIAS or not call.get("response_sha256")
           or call.get("application_model_calls") != 1 for call in calls):
        return "FAIL"
    if not STAGES.issubset({call.get("stage") for call in calls}) or not portable:
        return "FAIL"
    return "PASS" if state.get("evaluation", {}).get("status") == "pass" else "FAIL"


def check_portable(archive, work):
    """Execute only checkout-matched Python shipped in the CI-produced bundle."""
    folder = work / "delivery"
    folder.mkdir()
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        members = zf.namelist()
        if len(set(members)) != len(members):
            raise ValueError("Repeated export member.")
        from ignition.portable import MEMBERS
        if set(members) != set(MEMBERS) | {"SHA256SUMS.json"}:
            raise ValueError("Unexpected export member list.")
        trusted = {"ignition/construction.py": (PRODUCT / "ignition/construction.py").read_bytes(),
                   "ignition/evaluation.py": (PRODUCT / "ignition/evaluation.py").read_bytes(),
                   "run.py": (PRODUCT / "ignition/portable.py").read_bytes(),
                   "ignition/__init__.py": b'"""Portable FRONTIER OMEGA execution and evaluation."""\n'}
        for name in members:
            dest = (folder / name).resolve()
            raw = zf.read(name)
            if name in trusted and raw != trusted[name]:
                raise ValueError("Exported implementation differs from qualified source.")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
    env = {"LANG": "C.UTF-8", "PATH": os.defpath}
    check = subprocess.run([sys.executable, "-IB", str(folder/"run.py"), "verify"],
                           cwd=folder, env=env, stdin=subprocess.DEVNULL, capture_output=True)
    result = subprocess.run([sys.executable, "-IB", str(folder/"run.py"), "run"],
                            cwd=folder, env=env, input=(folder/"example-input.json").read_bytes(),
                            capture_output=True)
    return {"verified_exit": check.returncode, "example_exit": result.returncode,
            "example_output_sha256": hashlib.sha256(result.stdout).hexdigest()}


def run_mission(work, model, record, *, live_sources=False):
    # This public mission and its tests were recorded before this worker's model run.
    example = json.loads(EXAMPLE.read_bytes())
    # This historical comparator specifically exercises research-led discovery.
    example["mission"]["resources"]["execution_strategy"] = "research"
    if live_sources:
        # A separate prospective run grants only the repository's allowlisted public retrieval.
        example["mission"]["authority"].update(public_sources=True, assisted_model=False)
    state_store = Store(work/"missions")
    controller = Controller(state_store, provider_factory=lambda: model)
    run_id, version = controller.create({"mission": example["mission"], "sources": example["sources"],
                                         "request_id": "hosted-local-migration"})
    controller.advance(run_id, version)
    state = state_store.get(run_id)
    calls = compact_calls(state)
    record.update(contract_sha256=state["contract"]["sha256"] if state.get("contract") else None,
                  mission_status=state["status"], last_stage=state["stage"], calls=calls,
                  diagnostic=diagnostic(state, calls),
                  call_count=state.get("attempts", 0), spec_sha256=state["input_sha256"],
                  evidence_inputs=("Supplied excerpts plus live allowlisted source retrieval" if live_sources
                                   else "Frozen public source excerpts supplied with the mission"),
                  failure_message_sha256=digest(state["error"]) if state.get("error") else None)
    portable = False
    if state["status"] == "verified":
        bundle = controller.deliver(run_id, version)
        record["bundle_sha256"] = hashlib.sha256(bundle).hexdigest()
        record["portable"] = check_portable(bundle, work)
        portable = record["portable"]["verified_exit"] == record["portable"]["example_exit"] == 0
        evaluation = state["evaluation"]
        record["evaluation"] = {"status": evaluation["status"], "case_count": len(evaluation["cases"]),
                                "sha256": digest(evaluation)}
    record["status"] = result_status(state, calls, portable)
    if live_sources:
        record["construction_status"] = record["status"]
        record["acquisition_and_investigation"] = acquired_investigation(state, calls)
        record["status"] = record["acquisition_and_investigation"]["status"]
        if record["status"] == "PASS" and not all(c.get("transport_mode") == "streaming-sse/1" for c in calls):
            record["status"] = "FAIL"


def acquired_investigation(state, calls):
    sources = state.get("source_result") or {}
    research = state.get("research") or {}
    acquired = sources.get("sources", [])
    sources_by_id = {row["id"]: row for row in research.get("signals", [])}
    retrieved = {row["source_response_sha256"] for row in acquired}
    covered = {key for key, row in sources_by_id.items() if row.get("source_response_sha256") in retrieved}
    attributed = [c["id"] for c in research.get("candidates", []) if set(c.get("usable_sources", [])) & covered]
    stages = {c.get("stage") for c in calls if c.get("mode") == "local" and c.get("status") == "completed"
              and c.get("reported_model") == MODEL_ALIAS}
    required_roles = {"Published release", "Earlier snapshot; capability at this revision requires testing"}
    matched_feeds = [feed for feed in sources.get("feeds", []) if required_roles <=
                     {row["role"] for row in acquired if row["feed"] == feed}]
    matched = bool(matched_feeds)
    status = "BLOCKED" if not acquired else ("PASS" if matched and attributed and {"discover", "challenge"} <= stages else "FAIL")
    return {"status": status, "feeds": sources.get("feeds", []),
            "observations": [{k:row[k] for k in ("feed", "url", "role", "version", "retrieved_at",
                                                  "event_at", "source_response_sha256") if k in row} for row in acquired],
            "source_failures": [{k:row.get(k) for k in ("feed","role")} for row in sources.get("failures", [])],
            "matched_temporal_sources": matched, "feeds_with_both_dates": matched_feeds, "candidates_citing_live_sources": attributed,
            "selected_cites_live_source": bool(set((research.get("selected") or {}).get("usable_sources", [])) & covered),
            "model_stages": sorted(stages), "frontier_crossing": "unproven"}


def run_direct(work, model, record):
    # Same visible mission, evidence, capability, test contract and interpreter. One direct model invocation.
    example = json.loads(EXAMPLE.read_bytes())
    mission = example["mission"]
    contract = construction.freeze_contract(mission["construction_spec"])
    visible = construction.build_view(contract)
    record.update(contract_sha256=contract["sha256"], status="FAIL")
    pos = len(model.receipts)
    try:
        proposal = model.propose("direct_construct", {"instruction": CONSTRUCT_INSTRUCTION,
            "purpose": mission["purpose"], "requirements": mission["requirements"], "beneficiary": mission["beneficiary"],
            "resources": mission["resources"], "time": mission["time"], "sources": example["sources"],
            "kind":visible["kind"], "definition":visible["definition"]})
        artifact = construction.build(contract, proposal)
        result = evaluation.evaluate(contract, artifact)
        record.update(case_count=len(result["cases"]), artifact_sha256=artifact["sha256"],
                      accepted=result["status"] == "pass", evaluation_sha256=digest(result))
        if record["accepted"]:
            bundle = delivery.export_bundle(contract, artifact, result, {"comparison":"direct same-model arm"})
            record["portable"] = check_portable(bundle, work)
            if record["portable"]["verified_exit"] == record["portable"]["example_exit"] == 0:
                record["status"] = "PASS"
    finally:
        record["calls"] = [{k:r[k] for k in PUBLIC_ROUTES if k in r} for r in model.receipts[pos:]]
        if (len(record["calls"]) != 1 or record["calls"][0].get("reported_model") != MODEL_ALIAS or
                record["calls"][0].get("status") != "completed"):
            record["status"] = "FAIL"


def timed_arm(root, name, function, model):
    path = root / name
    path.mkdir(mode=0o700)
    record = {"status":"FAIL", "calls":[]}
    start = time.monotonic()
    try:
        runner_window()
        function(path, model, record)
    except Blocked as error:
        record.update(status="BLOCKED", obstruction=str(error))
    except Exception as error:
        record.update(status="FAIL", error_category=type(error).__name__)
    record["arm_wall_seconds"] = round(time.monotonic()-start, 6)
    usage = [r.get("usage") or {} for r in record["calls"]]
    record["tokens"] = {key:sum(x[key] for x in usage) if usage and all(type(x.get(key)) is int for x in usage)
                         else None for key in ("input_tokens", "output_tokens")}
    return record


def campaign(work, model, record, *, live_model):
    primary = timed_arm(work, "primary", run_mission, model)
    # Keep the original primary result, even when the direct arm succeeds.
    record.update(primary)
    record["registered_primary"] = primary
    direct = timed_arm(work, "direct", run_direct, model)
    record["direct_comparator"] = direct
    proven = primary["status"] == "PASS", direct["status"] == "PASS"
    outcome = {(True, True):"both accepted", (False, False):"neither accepted",
               (True, False):"only primary accepted", (False, True):"only direct accepted"}[proven]
    record["direct_comparison"] = {"outcome":outcome, "order":["primary","direct",LIVE_STREAM_ARM],
        "timing_scope":"Arm wall includes preparation, inference, checks and portable use. Download and startup are shared. A warm server can favor later arms.",
        "economic_advantage":"unmeasured", "human_comparison":"unmeasured"}
    def live(path, selected, receipt):
        return run_mission(path, selected, receipt, live_sources=True)
    record["live_source_trial"] = timed_arm(work, LIVE_STREAM_ARM, live, live_model)
    record["live_source_trial"]["arm_id"] = LIVE_STREAM_ARM
    live_status = record["live_source_trial"]["status"]
    # The direct arm can legitimately win or lose. The new integration gate requires actual acquisition AND use.
    if primary["status"] != "PASS":
        record["status"] = primary["status"]
    elif live_status != "PASS":
        record["status"] = live_status
    elif direct.get("error_category") and not direct.get("calls"):
        record["status"] = "FAIL"
    elif not direct.get("contract_sha256") or direct["contract_sha256"] != primary.get("contract_sha256"):
        record["status"] = "FAIL"
    elif record["live_source_trial"].get("mission_status") in {"blocked", "failed"}:
        record["status"] = "FAIL"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True, help="Fresh private directory outside the checkout")
    parser.add_argument("--output", type=Path, required=True, help="New file for a compact public receipt")
    args = parser.parse_args()
    work, output = args.work.resolve(), args.output.resolve()
    if (work.is_relative_to(REPO) or output.is_relative_to(REPO) or output.is_relative_to(work)
            or work.exists() or output.exists()):
        parser.error("Supply fresh, separate output and work locations outside the checkout.")
    work.mkdir(parents=True, mode=0o700)
    output.parent.mkdir(parents=True, exist_ok=True)
    record = dict(protocol="ignition/hosted-local/2", status="BLOCKED", started_at=stamp(),
                  live_source_arm=LIVE_STREAM_ARM,
                  model=MODEL_ALIAS, model_revision=pinned.MODEL_REVISION, runtime_url=pinned.BINARY_URL,
                  model_url=pinned.MODEL_URL, complete_cost_known=False, new_paid_services=0,
                  fixture_model_responses=0, calls=[], commercial_result="unmeasured",
                  frontier_crossing="unproven", human_baseline="unmeasured",
                  comparison_scope="Executable frozen acceptance and conventional comparator",
                  mission_fixture_sha256=hashlib.sha256(EXAMPLE.read_bytes()).hexdigest(),
                  actions_run=os.environ.get("GITHUB_RUN_ID"))
    start = time.monotonic()
    try:
        record["source_revision"] = checked_source()
        record["runtime_source_sha256"] = runtime_source()
        binary, weights = setup_model(work, record)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        with (work/"model.log").open("wb") as log:
            # No inherited credentials, CLI homes, proxies or code evaluation tools.
            env = {"PATH": os.defpath, "LD_LIBRARY_PATH": str(binary.parent), "HOME": str(work),
                   "LANG": "C.UTF-8", "NO_PROXY": "127.0.0.1"}
            threads = available_threads()
            record["inference_threads"] = threads
            args = [str(binary), "-m", str(weights), "--alias", MODEL_ALIAS, "--host", "127.0.0.1",
                    "--port", str(port), "--ctx-size", "32768", "--threads", str(threads), "--threads-batch", str(threads), "--parallel", "1",
                    "--n-gpu-layers", "0", "--seed", "6144", "--temp", "0"]
            server = subprocess.Popen(args, cwd=work, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
            try:
                wait_ready(server, port)
                model = LocalProvider("llama-cpp", MODEL_ALIAS, port, pinned.MODEL_SHA,
                                      output_tokens=8192, timeout=600, schema_output=True)
                live_model = LocalProvider("llama-cpp", MODEL_ALIAS, port, pinned.MODEL_SHA,
                                           output_tokens=8192, timeout=600, schema_output=True, streaming=True)
                campaign(work, model, record, live_model=live_model)
            finally:
                server.terminate()
                try:
                    server.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
        if checked_source() != record["source_revision"] or runtime_source() != record["runtime_source_sha256"]:
            raise ValueError("Source changed during the registered execution.")
    except Blocked as exc:
        record.update(status="BLOCKED", obstruction=str(exc))
    except Exception as exc:
        # Only bounded category metadata leaves the private workspace. Rich diagnostics stay local.
        record.update(status="FAIL", error_category=type(exc).__name__)
        if os.environ.get("GITHUB_ACTIONS") != "true":
            print(f"Private diagnostic: {type(exc).__name__}: {exc}", file=sys.stderr)
    record.update(finished_at=stamp(), wall_seconds=round(time.monotonic()-start, 3))
    output.write_text(json.dumps(record, indent=2, ensure_ascii=False, allow_nan=False)+"\n")
    summary = {k:record[k] for k in ("status", "model", "wall_seconds")}
    for key in ("source_revision", "last_stage", "diagnostic", "obstruction", "error_category"):
        if key in record:
            summary[key] = record[key]
    for key in ("registered_primary", "direct_comparator", "live_source_trial"):
        if key in record:
            item = record[key]
            summary[key] = {k:item[k] for k in ("status", "arm_wall_seconds", "last_stage", "tokens", "diagnostic",
                                               "construction_status", "error_category") if k in item}
    print(json.dumps(summary))
    return {"PASS":0,"BLOCKED":2,"FAIL":1}[record["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
