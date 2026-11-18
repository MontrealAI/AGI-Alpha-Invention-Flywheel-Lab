"""Operate the registered CPU pilot on a fresh, locally owned llama.cpp process."""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import resource
import socket
import subprocess
import sys
import tarfile
import time

PRODUCT = Path(__file__).resolve().parents[1]
REPO = PRODUCT.parents[1]
sys.path.insert(0, str(PRODUCT))
import qualify_live as local

FIELD = PRODUCT / "field_lab"
WORKLOAD = FIELD / "workload.json"
PINS = local.pinned


def now():
    return datetime.now(timezone.utc).isoformat()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def checked_asset(path, url, digest, size):
    if path.exists():
        if path.stat().st_size != size or PINS.sha(path) != digest:
            raise ValueError(f"Cached {path.name} differs from pinned identity")
    else:
        PINS.download(url, path, digest, size)
    return path


def prepare(assets, work, record):
    assets.mkdir(exist_ok=True, parents=True)
    start = time.monotonic()
    archive = checked_asset(assets / "llama.tar.gz", PINS.BINARY_URL,
                            PINS.BINARY_ARCHIVE_SHA, PINS.BINARY_ARCHIVE_BYTES)
    weights = checked_asset(assets / "model.gguf", PINS.MODEL_URL, PINS.MODEL_SHA, PINS.MODEL_BYTES)
    runtime = work / "runtime"
    runtime.mkdir()
    with tarfile.open(archive) as package:
        package.extractall(runtime, filter="data")
    binary, = [item for item in runtime.rglob("llama-server") if item.is_file()]
    record["assets"] = {
        "weights_sha256": PINS.MODEL_SHA, "weights_bytes": PINS.MODEL_BYTES,
        "model_repository": PINS.MODEL_REPO, "model_revision": PINS.MODEL_REVISION,
        "runtime_archive_sha256": PINS.BINARY_ARCHIVE_SHA,
        "runtime_archive_bytes": PINS.BINARY_ARCHIVE_BYTES, "server_sha256": PINS.sha(binary),
        "weights_preparation_wall_seconds": round(time.monotonic() - start, 4),
    }
    return binary, weights


def hardware():
    cpu = next((line.partition(":")[2].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
                if line.startswith("model name")), platform.machine())
    return {"processor": cpu, "architecture": platform.machine(), "platform": platform.system(),
            "threads": local.available_threads(), "gpu_layers": 0}


def child_cpu():
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime


@contextlib.contextmanager
def server(binary, weights, work, record, arm):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    threads = str(record["hardware"]["threads"])
    slots = "3" if arm in {"field", "conventional"} else "1"
    config = ["--ctx-size", "6144", "--parallel", slots, "--threads", threads, "--threads-batch",
              threads, "--n-gpu-layers", "0", "--seed", "6144", "--temp", "0",
              "--no-repack", "--batch-size", "128", "--ubatch-size", "64", "--no-webui"]
    record["serving_configuration"] = config
    args = [str(binary), "-m", str(weights), "--host", "127.0.0.1", "--port", str(port),
            "--alias", local.MODEL_ALIAS, *config]
    env = {"PATH": os.defpath, "LD_LIBRARY_PATH": str(binary.parent), "HOME": str(work),
           "LANG": "C.UTF-8", "NO_PROXY": "127.0.0.1"}
    with (work / "server.log").open("wb") as log:
        proc = subprocess.Popen(args, cwd=work, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        try:
            local.wait_ready(proc, port)
            yield port
        finally:
            record["server_exit_before_shutdown"] = proc.poll()
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


def run_child(args, log):
    with log.open("wb") as file:
        return subprocess.run([sys.executable, "-B", *map(str, args)], cwd=PRODUCT,
                              stdin=subprocess.DEVNULL, stdout=file, stderr=subprocess.STDOUT).returncode


def run_arm(arm, port, record, work, output):
    if arm in {"field", "conventional"}:
        authority = {
            "schema": 1, "scope": "public-synthetic-pilot", "target": "qwen-cpu",
            "base_url": f"http://127.0.0.1:{port}", "model": local.MODEL_ALIAS,
            "model_sha256": PINS.MODEL_SHA, "runtime_sha256": record["assets"]["server_sha256"],
            "hardware": f'{record["hardware"]["processor"]}, {record["hardware"]["threads"]} threads',
            "configuration": " ".join(record["serving_configuration"]),
            "workload_sha256": record["source_files"]["field_lab/workload.json"],
            "max_concurrency": 3, "max_attempts": 24,
            "tokenizer": "llama.cpp-/tokenize-add_special=false-parse_special=false",
            "locally_owned_no_forwarding": True,
        }
        permit = work / "local-authority.json"
        write(permit, authority)
        trace = output / (arm + ".json")
        code = run_child([FIELD / "field.py", "run", "--route", arm, "--workload", WORKLOAD,
                          "--authority", permit, "--output", trace], work / "client.log")
        if code:
            return {"client_exit": code}
        command = [FIELD / "verify.py", "--workload", WORKLOAD, "--receipt", trace]
        verify = run_child(command, work / "verify.log")
        retokenize = run_child([*command, "--retokenize-authority", permit], work / "tokenizer.log")
        return {"client_exit": code, "independent_replay_exit": verify, "live_tokenizer_exit": retokenize,
                "independently_checked_loads": json.loads(trace.read_bytes())["metrics"] if verify == 0 else None,
                "receipt_sha256": PINS.sha(trace)}
    dest = output / (arm + ".json")
    code = run_child(["-m", "discovery_field.study", "live", "--port", port, "--model",
                      local.MODEL_ALIAS, "--weights-sha256", PINS.MODEL_SHA, "--mode", arm,
                      "--out", dest], work / "client.log")
    cases = json.loads(dest.read_bytes())["cases"] if dest.is_file() else []
    return {"client_exit": code, "receipt_sha256": PINS.sha(dest) if dest.is_file() else None,
            "observations": [{"task": row["task"], "transport": row["receipt"].get("status"),
                              "usage": row["receipt"].get("usage"), "assessment": row["assessment"]}
                             for row in cases]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", required=True, type=Path, help="New scratch directory for the model and private logs")
    parser.add_argument("--assets", required=True, type=Path, help="Local pinned download cache")
    parser.add_argument("--output", required=True, type=Path, help="New directory for public synthetic receipts")
    parser.add_argument("--study", choices=["both", "field", "discovery", "open"], default="both")
    options = parser.parse_args()
    work, output = options.work.resolve(), options.output.resolve()
    work.mkdir(mode=0o700, parents=True)
    output.mkdir(parents=True)
    source = [Path(__file__).resolve(), PRODUCT / "qualify_live.py"]
    if options.study in ("both", "field"):
        source += [FIELD / name for name in ("field.py", "capture.py", "protocol.py", "verify.py", "workload.json")]
    if options.study in ("both", "discovery", "open"):
        source += [path for path in (PRODUCT / "discovery_field").glob("*") if path.is_file() and
                   ((path.suffix == ".py" and not path.name.startswith("test_")) or
                    path.name in {"missions.json", "open_mission.json", "catalog.json"})]
    record = {
        "schema": "ignition.cpu-pilot.v1", "started_at": now(), "model": local.MODEL_ALIAS,
        "revision_at_launch": local.git("rev-parse", "HEAD"), "hardware": hardware(),
        "source_files": {p.relative_to(PRODUCT).as_posix(): PINS.sha(p) for p in sorted(set(source))},
        "hosting": "standard public GitHub CPU" if os.environ.get("GITHUB_ACTIONS") == "true" else "shared engineering CPU",
        "billing": None, "production_traffic": False, "scope": "public authored pilot only", "arms": {},
    }
    start, cpu = time.monotonic(), child_cpu() + time.process_time()
    arms = {"both": ["field", "conventional", "direct", "targeted", "open"], "open": ["open"],
            "field": ["field", "conventional"], "discovery": ["direct", "targeted"]}[options.study]
    try:
        binary, weights = prepare(options.assets.resolve(), work, record)
        for arm in arms:
            phase, before = time.monotonic(), child_cpu()
            folder = work / arm
            folder.mkdir(mode=0o700)
            try:
                with server(binary, weights, folder, record, arm) as port:
                    result = run_arm(arm, port, record, folder, output)
            except (OSError, ValueError, local.Blocked) as exc:
                result = {"execution_obstruction": str(exc)[:250]}
            result.update(serving_configuration=record.get("serving_configuration"),
                          server_exit_before_shutdown=record.pop("server_exit_before_shutdown", None),
                          wall_seconds_with_startup=round(time.monotonic() - phase, 4),
                          child_cpu_seconds_including_server=round(child_cpu() - before, 4))
            record["arms"][arm] = result
            write(output / "operation.json", record)
    except (OSError, ValueError, local.Blocked, tarfile.TarError) as exc:
        record["execution_obstruction"] = str(exc)[:250]
    record.update(finished_at=now(), wall_seconds=round(time.monotonic() - start, 4),
                  cpu_seconds_including_children=round(child_cpu() + time.process_time() - cpu, 4))
    record["executed"] = len(record["arms"]) == len(arms) and all(
        a.get("client_exit") == 0 and a.get("independent_replay_exit", 0) == 0 and
        a.get("live_tokenizer_exit", 0) == 0 and a.get("server_exit_before_shutdown") is None
        for a in record["arms"].values())
    write(output / "operation.json", record)
    print(json.dumps({"executed": record["executed"], "arms": record["arms"],
                      "obstruction": record.get("execution_obstruction")}))
    return 0 if record["executed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
