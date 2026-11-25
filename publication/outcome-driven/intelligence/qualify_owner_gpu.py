# SPDX-License-Identifier: Apache-2.0
"""Replay registered public missions on an owner-approved Ubuntu GPU host."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
from urllib.request import ProxyHandler, build_opener


REPO = Path(__file__).resolve().parents[3]
EVALUATION = REPO / "publication/evidence-bound/evaluation"
FRESH = EVALUATION / "fresh"
MODEL_REGISTRATION = EVALUATION.parent / "productive/REGISTRATION.json"
REGISTRATION_SHA256 = "591e595b8b32bee948a2cfed14d189cc7719641b5dabf5a181af7f1ac1cf88dd"
MODELS = {"gpt-oss-20b-mxfp4": "repeat", "qwen3-30b-a3b-q4_k_m": "first"}
PORT = 38461
CONTEXT_TOKENS = 16384
STARTUP_SECONDS = 180
TOTAL_SECONDS = 1800


class Blocked(Exception):
    """A controlled interruption with a display-safe reason."""


def load(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def gpu_inventory(smi, env):
    fields = "index,uuid,name,driver_version,memory.total,memory.used,memory.free,power.draw"
    result = subprocess.check_output([smi, "--query-gpu=" + fields, "--format=csv,noheader,nounits"],
                                     env=env, stdin=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True, timeout=8)
    inventory = {}
    for row in csv.reader(result.splitlines(), skipinitialspace=True):
        index, uuid, name, driver, total, used, free, power = (item.strip() for item in row)
        if not re.fullmatch(r"GPU-[0-9a-fA-F-]+", uuid):
            raise ValueError("Unexpected NVIDIA device identity.")
        watts = float(power) if re.fullmatch(r"\d+(?:\.\d+)?", power) else None
        inventory[index] = {"uuid": uuid, "name": name, "driver": driver, "total_mib": int(total),
                            "used_mib": int(used), "free_mib": int(free), "power_w": watts}
    return inventory


def telemetry(smi, env, devices, metrics, previous):
    try:
        inventory = gpu_inventory(smi, env)
    except (OSError, ValueError, subprocess.SubprocessError):
        return {}
    timestamp = time.monotonic()
    current = {}
    for index in devices:
        if index not in inventory:
            continue
        board = inventory[index]
        counts = metrics[index]
        counts["samples"] += 1
        counts["sampled_peak_board_used_mib"] = max(counts["sampled_peak_board_used_mib"], board["used_mib"])
        counts["sampled_min_board_free_mib"] = min(counts["sampled_min_board_free_mib"], board["free_mib"])
        if board["power_w"] is not None:
            current[index] = (timestamp, board["power_w"])
            if index in previous:
                last_time, last_watts = previous[index]
                interval = timestamp - last_time
                counts["power_covered_seconds"] += interval
                counts["sampled_board_energy_joules"] += interval * (last_watts + board["power_w"]) / 2
    return current


def startup_evidence(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    layers = re.search(r"offloaded (\d+)/(\d+) layers to GPU", text)
    context = re.search(r"\bn_ctx(?:_slot)?\s*=\s*(\d+)", text)
    buffers = re.findall(r"\bCUDA(\d+)\s+model buffer size\s*=\s*(\d+(?:\.\d+)?)\s+MiB", text)
    timing = re.findall(r"(prompt eval|\beval) time\s*=.*?([\d.]+) tokens per second", text)
    return {
        "gpu_layers": {"offloaded": int(layers[1]), "total": int(layers[2])} if layers else None,
        "observed_context_tokens": int(context[1]) if context else None,
        "cuda_model_buffer_mib_by_visible_index": {device: float(size) for device, size in buffers},
        "prefill_tokens_per_second": [float(rate) for kind, rate in timing if kind == "prompt eval"],
        "generation_tokens_per_second": [float(rate) for kind, rate in timing if kind == "eval"],
    }


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def run(args, output, receipt):
    if platform.system() != "Linux":
        raise Blocked("Run the launcher on the approved Ubuntu GPU workstation.")
    receipt["physical_memory_bytes"] = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    smi = shutil.which("nvidia-smi")
    if smi is None:
        raise Blocked("nvidia-smi is unavailable on this host.")
    binary = shutil.which(args.llama_server)
    if binary is None:
        raise Blocked("Supply the approved CUDA-enabled llama-server executable.")
    env = {key: os.environ[key] for key in ("PATH", "LD_LIBRARY_PATH", "TMPDIR") if key in os.environ}
    env.update({"LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"})
    devices = args.devices.split(",")
    inventory = gpu_inventory(smi, env)
    if not set(devices) <= set(inventory):
        raise Blocked("One or more selected NVIDIA devices are unavailable.")
    metrics = {index: {key: inventory[index][key] for key in ("name", "driver", "total_mib")} for index in devices}
    for index, row in metrics.items():
        row.update({"initial_free_mib": inventory[index]["free_mib"], "samples": 0,
                    "sampled_peak_board_used_mib": inventory[index]["used_mib"],
                    "sampled_min_board_free_mib": inventory[index]["free_mib"],
                    "power_covered_seconds": 0.0, "sampled_board_energy_joules": 0.0})
    receipt["gpus_by_nvidia_smi_index"] = metrics
    receipt["two_titan_rtx_selected"] = len(devices) == 2 and all("TITAN RTX" in row["name"] for row in metrics.values())
    env["CUDA_VISIBLE_DEVICES"] = ",".join(inventory[index]["uuid"] for index in devices)

    checkpoint = load(MODEL_REGISTRATION)["sources"][MODELS[args.checkpoint]]
    if not args.weights.is_file() or args.weights.stat().st_size != checkpoint["size_bytes"]:
        raise Blocked("The selected weight file is missing or its byte length differs from the published checkpoint.")
    weight_stat = args.weights.stat()
    weight_sha = sha256(args.weights)
    receipt["model"] = {"alias": args.checkpoint, "publisher": checkpoint["repository"],
                        "publisher_revision": checkpoint["revision"], "bytes": checkpoint["size_bytes"],
                        "sha256": weight_sha, "publisher_sha256_matches": weight_sha == checkpoint["registry_linked_sha256"]}
    if not receipt["model"]["publisher_sha256_matches"]:
        raise Blocked("The weight digest differs from the published checkpoint.")
    version = subprocess.check_output([binary, "--version"], env=env, stdin=subprocess.DEVNULL,
                                      stderr=subprocess.STDOUT, text=True, timeout=15)
    match = re.search(r"(?mi)^version:\s*([0-9A-Za-z .(),_+-]+)$", version)
    receipt["llama_cpp"] = {"version": match[1] if match else None, "binary_sha256": sha256(Path(binary))}

    registration = load(FRESH / "REGISTRATION.json")
    if sha256(FRESH / "REGISTRATION.json") != REGISTRATION_SHA256:
        raise Blocked("The independent evaluation registration differs from the expected bytes.")
    if sha256(FRESH / "CASES.json") != registration["case_sha256"]:
        raise Blocked("The independent evaluation cases differ from the expected bytes.")
    cases = load(FRESH / "CASES.json")
    core = registration["core"]
    if any("sources" in case for case in cases if case["id"] in core):
        raise Blocked("The selected qualification includes a source acquisition case.")
    config = load(FRESH / "RUNTIME-CONFIG.json")
    provider = config["providers"]["llama-cpp"]
    options = provider["models"]["qwen3-8b-q4_k_m"]
    options["context_window"] = CONTEXT_TOKENS
    provider.update({"label": "Owner-authorized local CUDA llama.cpp", "models": {args.checkpoint: options},
                     "base_url": f"http://127.0.0.1:{PORT}/v1"})
    save(output / "runtime-config.json", config)
    receipt["registered_cases"] = core
    receipt["configured_context_tokens"] = CONTEXT_TOKENS
    receipt["registered_output_tokens_per_turn"] = registration["budget"]["max_tokens_per_turn"]

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as port_check:
        try:
            port_check.bind(("127.0.0.1", PORT))
        except OSError as error:
            raise Blocked(f"Loopback port {PORT} is unavailable. Stop its listener before retrying.") from error
    url = f"http://127.0.0.1:{PORT}/health"
    opener = build_opener(ProxyHandler({}))
    server_log = output / "llama-server.log"
    command = [binary, "--offline", "--host", "127.0.0.1", "--port", str(PORT), "--model", str(args.weights.resolve()),
               "--alias", args.checkpoint, "--ctx-size", str(CONTEXT_TOKENS), "--parallel", "1", "--threads", "6",
               "--n-gpu-layers", "99", "--split-mode", "layer", "--tensor-split", ",".join("1" for _ in devices),
               "--no-ui", "--reasoning", "off", "--jinja", "--log-verbosity", "4"]
    print("Starting the local GPU runtime.", flush=True)
    deadline = time.monotonic() + TOTAL_SECONDS
    previous = {}
    with server_log.open("wb") as log:
        server = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        try:
            startup_deadline = time.monotonic() + STARTUP_SECONDS
            while time.monotonic() < startup_deadline and server.poll() is None:
                previous = telemetry(smi, env, devices, metrics, previous)
                try:
                    with opener.open(url, timeout=2) as response:
                        health = json.loads(response.read(256))
                        if isinstance(health, dict) and health.get("status") == "ok":
                            break
                except (OSError, ValueError):
                    pass
                time.sleep(1)
            else:
                raise Blocked("The selected runtime did not load the checkpoint on loopback. Inspect the private server log.")

            placement = startup_evidence(server_log)
            if (not placement["gpu_layers"] or not placement["gpu_layers"]["offloaded"]
                    or not placement["cuda_model_buffer_mib_by_visible_index"]):
                raise Blocked("The local runtime did not report CUDA model placement. Inspect the private server log.")
            receipt["gpu_placement_on_all_selected_devices"] = (
                set(placement["cuda_model_buffer_mib_by_visible_index"]) == {str(index) for index in range(len(devices))}
            )

            for arm in ("evidence", "direct"):
                print(f"Running the registered {arm} missions.", flush=True)
                result = output / arm
                evaluator = [sys.executable, "-B", str(EVALUATION / "run_missions.py"), "--repo", str(REPO),
                             "--cases", str(FRESH / "CASES.json"), "--oracle", str(FRESH / "ORACLE.json"),
                             "--registration", str(FRESH / "REGISTRATION.json"), "--registration-sha256", REGISTRATION_SHA256,
                             "--config", str(output / "runtime-config.json"), "--result", str(result),
                             "--arm", arm, "--model", args.checkpoint, "--only", *core]
                with (output / (arm + ".log")).open("wb") as arm_log:
                    worker = subprocess.Popen(evaluator, env=env, stdin=subprocess.DEVNULL,
                                              stdout=arm_log, stderr=subprocess.STDOUT)
                    try:
                        while worker.poll() is None and time.monotonic() < deadline and server.poll() is None:
                            previous = telemetry(smi, env, devices, metrics, previous)
                            time.sleep(1)
                    finally:
                        stop(worker)
                if worker.returncode != 0:
                    raise Blocked(f"The {arm} evaluation was interrupted. Inspect the private evaluation log.")
                keys = ("verdict", "actual_provider_dispatches", "token_usage", "task_elapsed_seconds", "provider_seconds")
                receipt["arms"][arm] = {ident: {key: row[key] for key in keys}
                                        for ident, row in load(result / "report.json")["cases"].items()}
        finally:
            stop(server)
    receipt["observed_runtime"] = startup_evidence(server_log)
    current_stat = args.weights.stat()
    if (current_stat.st_ino, current_stat.st_size, current_stat.st_mtime_ns) != (weight_stat.st_ino, weight_stat.st_size, weight_stat.st_mtime_ns):
        raise Blocked("The selected weight file changed during the qualification.")
    receipt["status"] = "OBSERVED"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weights", required=True, type=Path, help="Existing owner-approved publisher GGUF")
    parser.add_argument("--output", required=True, type=Path, help="A new local directory for the results")
    parser.add_argument("--llama-server", default="llama-server", help="Existing approved CUDA-enabled executable")
    parser.add_argument("--checkpoint", choices=tuple(MODELS), default="gpt-oss-20b-mxfp4")
    parser.add_argument("--devices", default="0,1", help="One or two existing NVIDIA device indices")
    args = parser.parse_args()
    if not re.fullmatch(r"\d+(?:,\d+)?", args.devices) or len(set(args.devices.split(","))) != len(args.devices.split(",")):
        parser.error("Supply distinct comma-separated NVIDIA device indices.")
    output = args.output.resolve()
    try:
        output.mkdir(mode=0o700)
    except OSError:
        parser.error("Supply a new output directory under an existing writable parent.")
    began = time.monotonic()
    receipt = {"schema": "frontier/owner-gpu-mission-qualification/v1", "started_at_utc": datetime.now(timezone.utc).isoformat(),
               "system": platform.system(), "kernel": platform.release(), "architecture": platform.machine(),
               "execution": "Registered public engineering replay with matching local model arms",
               "registration_sha256": REGISTRATION_SHA256, "paid_provider_requests": 0,
               "training_or_adaptation_tested": False, "status": "BLOCKED", "arms": {}}
    try:
        run(args, output, receipt)
    except Blocked as error:
        receipt["diagnostic"] = str(error)
    except KeyboardInterrupt:
        receipt.update({"status": "INTERRUPTED", "diagnostic": "Operator interrupted the run."})
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        receipt["diagnostic"] = "The local preflight failed with " + type(error).__name__ + "."
    finally:
        if (output / "llama-server.log").is_file() and "observed_runtime" not in receipt:
            receipt["observed_runtime"] = startup_evidence(output / "llama-server.log")
        for board in receipt.get("gpus_by_nvidia_smi_index", {}).values():
            if board["power_covered_seconds"] == 0:
                board["sampled_board_energy_joules"] = None
        receipt["wall_seconds_including_setup"] = time.monotonic() - began
        save(output / "RECEIPT.json", receipt)
    print(f"{receipt['status']} · {output / 'RECEIPT.json'}", flush=True)
    if "diagnostic" in receipt:
        print(receipt["diagnostic"], flush=True)
    return 0 if receipt["status"] == "OBSERVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
