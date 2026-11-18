"""Run a fresh local observer with the two frozen public GitHub response arrays."""
import argparse
import hashlib
import json
import os
import resource
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from field_trials import observe
from ignition import scout
from ignition.controller import Controller
from ignition.provider import LocalProvider
from ignition.store import Store

ROOT_URL = "https://api.github.com/repos/ggml-org/llama.cpp"
URLS = {ROOT_URL + "/releases?per_page=3": "latest-releases.json",
        ROOT_URL + "/commits?per_page=1&until=2026-10-14T23:59:59Z": "latest-baseline.json"}


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + "\n")


def stamp():
    return datetime.now(timezone.utc).isoformat()


def cpu():
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return time.process_time() + children.ru_utime + children.ru_stime


def run(args):
    work = args.work.resolve()
    work.mkdir(mode=0o700)
    clock = lambda: datetime.now(timezone.utc)
    if args.replay_at:
        historical = datetime.fromisoformat(args.replay_at)
        if historical.tzinfo is None or historical.date().isoformat() != "2026-11-18":
            raise ValueError("Use the attributed observation day and an explicit UTC offset.")
        clock = lambda: historical
    brief = json.loads(Path("examples/scout.json").read_text())
    record = {"started_at": stamp(), "source_time_mode": "historical replay" if args.replay_at else "current",
              "max_output_tokens_per_call": args.output_tokens,
              "hardware": observe.hardware(), "inputs": [], "brief_sha256": observe.PINS.sha(Path("examples/scout.json"))}
    record["hardware"]["threads"] = min(4, record["hardware"]["threads"])
    first_wall, first_cpu = time.monotonic(), cpu()

    def public_snapshot(url):
        data = (args.observations / URLS[url]).read_text().rstrip("\n")
        digest = hashlib.sha256(data.encode()).hexdigest()
        record["inputs"].append({"url": url, "imported_representation_sha256": digest})
        return {"text": data, "sha256": digest, "retrieved_at": clock().isoformat()}

    binary, weights = observe.prepare(args.assets, work, record)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    threads = str(record["hardware"]["threads"])
    configuration = ["--ctx-size", "12288", "--parallel", "1", "--threads", threads, "--threads-batch", threads,
                     "--n-gpu-layers", "0", "--seed", "6144", "--temp", "0", "--no-repack", "--batch-size",
                     "128", "--ubatch-size", "64", "--no-webui"]
    record["serving_configuration"] = configuration
    env = {"PATH": os.defpath, "LD_LIBRARY_PATH": str(binary.parent), "HOME": str(work), "LANG": "C.UTF-8",
           "NO_PROXY": "127.0.0.1"}
    args_list = [str(binary), "-m", str(weights), "--host", "127.0.0.1", "--port", str(port),
                 "--alias", observe.local.MODEL_ALIAS, *configuration]
    write(work / "recovery.json", record)
    with (work / "server.log").open("wb") as log:
        proc = subprocess.Popen(args_list, cwd=work, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        try:
            observe.local.wait_ready(proc, port)
            provider = LocalProvider("llama-cpp", observe.local.MODEL_ALIAS, port, observe.PINS.MODEL_SHA,
                                     output_tokens=args.output_tokens, timeout=240, schema_output=True, streaming=True)
            controller = Controller(Store(work / "state"), provider_factory=lambda: provider)
            # On a later day an explicitly labelled historical replay may fix the source evaluation clock.
            from contextlib import nullcontext
            anchor = patch("ignition.controller.timestamp", lambda: clock().isoformat()) if args.replay_at else nullcontext()
            with anchor:
                result = scout.poll(controller, brief, "public-recovery", investigate_initial=True,
                                    fetch=public_snapshot, clock=clock)
                write(work / "observation.json", result)
                state = controller.store.get(result["missions"][0]["mission_id"])
                write(work / "mission.json", state)
                count = len(provider.receipts)
                restart = scout.poll(Controller(Store(work / "state"), provider_factory=lambda: provider), brief,
                                     "public-recovery", investigate_initial=True, fetch=public_snapshot, clock=clock)
            write(work / "restart.json", restart)
            write(work / "receipts.json", provider.receipts)
            research = state.get("research") or {}
            record.update(status=state["status"], error=state.get("error"), attempts=state.get("attempts", 0),
                          research_decision=research.get("decision"), reason=research.get("decision_reason"),
                          candidates=[r["title"] for r in research.get("candidates", [])],
                          repeat_status=restart["status"], repeat_children=len(restart["missions"]),
                          repeat_model_calls=len(provider.receipts)-count,
                          verified=(state["status"]=="verified" and (state.get("evaluation") or {}).get("status")=="pass"))
        finally:
            proc.terminate()
            try:
                proc.wait(15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            record.update(finished_at=stamp(), wall_seconds=time.monotonic()-first_wall, cpu_seconds=cpu()-first_cpu)
            write(work / "recovery.json", record)
    print(json.dumps({k:record[k] for k in ("status","attempts","research_decision","repeat_children","repeat_model_calls","wall_seconds")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True, type=Path, help="new private output directory")
    parser.add_argument("--assets", required=True, type=Path, help="cache for the two verified public model/runtime assets")
    parser.add_argument("--observations", required=True, type=Path, help="directory containing the two publisher JSON arrays")
    parser.add_argument("--replay-at", help="explicit source timestamp for historical replay after the release window")
    parser.add_argument("--output-tokens", type=int, choices=(2048,4096), default=2048,
                        help="registered per-call output allowance")
    run(parser.parse_args())
