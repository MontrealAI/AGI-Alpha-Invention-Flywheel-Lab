#!/usr/bin/env python3
"""Restore the registered CPU-only CellposeDINO runtime without image inference.

This additive installer does not modify registered source, protocols, or model
settings. All installed packages, downloads, and receipts live outside this
edition. It verifies the exact Python/package versions and upstream Python
source identities before declaring the environment ready. Public model weights
are downloaded from the frozen revision, never bundled into this repository.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
REGISTRATION = ROOT / "INCUMBENT_REGISTRATION-amendment-2.json"
PROTOCOL = ROOT / "INCUMBENT_PROTOCOL-amendment-2.json"
SOURCE_REVISION = "64d6d30da4a5da7c8905d9a106d9e2a996a29e4d"
EXPECTED_REGISTRATION = "a0ff81e25aa9782921a04f58b6062ec7be86a4538156ad6f3dee77945a17764f"
CELLPOSE_URL = "https://files.pythonhosted.org/packages/cc/20/d9d1fa1abffc8dab4381116ea0d91e8f8e4315acc038b76679608c097649/cellpose-4.2.1.1-py3-none-any.whl"
DINOV3_URL = "https://codeload.github.com/facebookresearch/dinov3/tar.gz/6876159a11b4df116f30f667f8c9888617df0751"
MODEL_URL = "https://huggingface.co/mouseland/cellpose-sam/resolve/7c61431b5fbb078f3296754bd15d9f51b320f837/cpdino-vitb"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def write_json(path, value):
    pending = path.with_name(path.name + ".pending")
    pending.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    pending.replace(path)


def source_boundary():
    """Protect the owning checkout, or just the extracted source edition.

    An extracted distribution can live inside an unrelated enclosing Git
    repository (for example a managed /workspace). Only the canonical repository
    layout identifies this edition's own checkout; an ambient .git marker does
    not make every sibling working directory part of the publication source.
    Git worktrees use a .git file and receive the same protection as clones.
    """
    relative = Path("docs/learning-to-build-v1.1.0/construction")
    for parent in ROOT.parents:
        if (parent / ".git").exists() and ROOT == parent / relative:
            return parent
    return ROOT.parent


def outside_edition(path):
    require(path.is_absolute(), "Paths must be absolute")
    path = path.resolve()
    require(not path.is_relative_to(source_boundary()),
            "Keep setup outside the repository/source edition")
    return path


def obtain(url, destination, expected_sha256, expected_bytes, record, output):
    started, cpu = time.perf_counter(), time.process_time()
    item = {"url": url, "file": destination.name, "expected_sha256": expected_sha256,
            "expected_bytes": expected_bytes, "status": "STARTED"}
    record["downloads"].append(item)
    write_json(output / "SETUP.json", record)
    try:
        require(not destination.is_symlink(), "Download cannot be a symlink")
        if destination.exists():
            item["reused"] = True
        else:
            pending = destination.with_name(destination.name + ".part")
            require(not pending.exists(), "A partial download exists; preserve/inspect it before a new attempt")
            item["reused"] = False
            request = urllib.request.Request(url, headers={"User-Agent": "Learning-to-Build-reproduction/1.1"})
            with urllib.request.urlopen(request, timeout=60) as source, pending.open("xb") as target:
                item["http_status"] = source.status
                while block := source.read(1024 * 1024):
                    target.write(block)
            item["bytes"], item["sha256"] = pending.stat().st_size, digest(pending)
            require(item["sha256"] == expected_sha256, "Downloaded SHA-256 differs: " + destination.name)
            require(expected_bytes is None or item["bytes"] == expected_bytes,
                    "Downloaded byte count differs: " + destination.name)
            pending.rename(destination)
        item["bytes"], item["sha256"] = destination.stat().st_size, digest(destination)
        require(item["sha256"] == expected_sha256, "Cached SHA-256 differs: " + destination.name)
        require(expected_bytes is None or item["bytes"] == expected_bytes, "Cached byte count differs")
        item["status"] = "VERIFIED"
        print(json.dumps({"download": destination.name, "status": item["status"], "reused": item["reused"]}), flush=True)
    except BaseException as error:
        item.update(status="FAILED", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        item.update(cpu_seconds=time.process_time() - cpu, wall_seconds=time.perf_counter() - started)
        write_json(output / "SETUP.json", record)


def command(argv, label, output, record, env):
    started = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    log = output / (label + ".log")
    item = {"command": [str(x) for x in argv], "log": log.name, "exit_code": None}
    record["commands"].append(item)
    write_json(output / "SETUP.json", record)
    print(json.dumps({"command": label, "status": "RUNNING"}), flush=True)
    try:
        with log.open("xb") as stream:
            result = subprocess.run([str(x) for x in argv], stdout=stream, stderr=subprocess.STDOUT, env=env)
        item["exit_code"] = result.returncode
    except BaseException as error:
        item.update(error_type=type(error).__name__, error=str(error))
        raise
    finally:
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        item.update(wall_seconds=time.perf_counter() - started,
                    cpu_seconds=(after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime),
                    log_sha256=digest(log) if log.exists() else None)
        write_json(output / "SETUP.json", record)
    print(json.dumps({"command": label, "exit_code": item["exit_code"]}), flush=True)
    require(item["exit_code"] == 0, "Setup command failed; inspect " + str(log))


def verify_requirements(text, registration, protocol):
    """Reject drift in the installation plan before installing any package."""
    expected = {name.lower().replace("_", "-"): version
                for name, version in registration["runtime_versions"]["packages"].items()}
    expected["cellpose"] = CELLPOSE_URL + "#sha256=" + protocol["upstream"]["cellpose_wheel_sha256"]
    expected["dinov3"] = DINOV3_URL + "#sha256=" + protocol["upstream"]["dinov3_archive_sha256"]
    actual = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith("--"):
            require(line in ("--index-url https://pypi.org/simple", "--extra-index-url https://download.pytorch.org/whl/cpu"), "Unexpected package index/options")
            continue
        name, version = line.split(" @ ", 1) if " @ " in line else line.split("==", 1)
        name = name.lower().replace("_", "-")
        require(name not in actual, "Duplicate package requirement")
        actual[name] = version
    require(actual == expected, "Requirements differ from the frozen runtime")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--venv", required=True, type=Path)
    parser.add_argument("--cache", required=True, type=Path, help="Package/model cache, separate from microscopy data")
    parser.add_argument("--output", required=True, type=Path, help="New immutable setup receipt directory")
    parser.add_argument("--data-cache", type=Path, help="Optional previously acquired public data; never downloaded here")
    parser.add_argument("--skip-install", action="store_true", help="Verify an existing environment without pip installation")
    args = parser.parse_args()
    args.venv, args.cache, args.output = map(outside_edition, (args.venv, args.cache, args.output))
    require(not args.output.exists(), "Setup receipt directory already exists; use a new output path")
    args.output.mkdir(parents=True)
    started, cpu = time.perf_counter(), time.process_time()
    record = {"schema": "learning-to-build/incumbent-setup/v1", "status": "STARTED",
              "started_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
              "registered_source_revision": SOURCE_REVISION, "setup_source_sha256": digest(Path(__file__)),
              "scope": "New reproduction setup of an exposed frozen comparison; no recovered original archive and no fresh holdout.",
              "public_image_pixels_decoded": 0, "predictions_performed": 0,
              "downloads": [], "commands": [], "financial_transactions_performed": 0}
    write_json(args.output / "SETUP.json", record)
    (args.output / "SETUP_SOURCE.py").write_bytes(Path(__file__).read_bytes())
    env = os.environ.copy()
    env.update({x: "1" for x in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS", "MAX_JOBS", "CMAKE_BUILD_PARALLEL_LEVEL")})
    env["CUDA_VISIBLE_DEVICES"] = ""
    try:
        require(digest(REGISTRATION) == EXPECTED_REGISTRATION, "Registration changed")
        registration = json.loads(REGISTRATION.read_text())
        protocol = json.loads(PROTOCOL.read_text())
        require(platform.python_version() == registration["runtime_versions"]["python"], "Use exactly the registered Python version")
        require(digest(PROTOCOL) == registration["protocol_sha256"], "Protocol changed")
        for name, expected in registration["implementation_files"].items():
            require(digest(ROOT / name) == expected, "Registered implementation changed: " + name)
        record["registration_sha256"] = digest(REGISTRATION)
        record["requirements_sha256"] = digest(ROOT / "requirements-incumbent.txt")
        record["runtime_requested"] = registration["runtime_versions"]
        requirements = (ROOT / "requirements-incumbent.txt").read_text()
        verify_requirements(requirements, registration, protocol)
        (args.output / "requirements-incumbent.txt").write_text(requirements)
        python = args.venv / "bin/python"
        record["existing_venv"] = args.venv.exists()
        if not args.venv.exists():
            require(not args.skip_install, "Existing environment required for --skip-install")
            command([sys.executable, "-m", "venv", args.venv], "create-venv", args.output, record, env)
        require((args.venv / "pyvenv.cfg").is_file() and python.is_file(), "Expected a Python virtual environment")
        record["venv_configuration"] = (args.venv / "pyvenv.cfg").read_text()
        args.cache.mkdir(parents=True, exist_ok=True)
        wheel = args.cache / "cellpose-4.2.1.1-py3-none-any.whl"
        archive = args.cache / "dinov3-6876159a11b4df116f30f667f8c9888617df0751.tar.gz"
        weights = args.cache / "cpdino-vitb"
        obtain(CELLPOSE_URL, wheel, protocol["upstream"]["cellpose_wheel_sha256"], None, record, args.output)
        obtain(DINOV3_URL, archive, protocol["upstream"]["dinov3_archive_sha256"], None, record, args.output)
        if not args.skip_install:
            requirements = requirements.replace(CELLPOSE_URL, wheel.as_uri()).replace(DINOV3_URL, archive.as_uri())
            effective = args.output / "requirements-local.txt"
            effective.write_text(requirements)
            command([python, "-m", "pip", "install", "--disable-pip-version-check", "--no-input", "--report", args.output / "pip-report.json", "-r", effective], "install-runtime", args.output, record, env)
        obtain(MODEL_URL, weights, protocol["model"]["sha256"], protocol["model"]["bytes"], record, args.output)
        command([python, ROOT / "incumbent.py", "preflight", "--weights", weights, "--output", args.output / "PREFLIGHT.json"], "preflight", args.output, record, env)
        contract_code = """import json, pathlib, sys
sys.path.insert(0, sys.argv[1])
import incumbent
registration = incumbent.read_json(incumbent.ROOT / 'INCUMBENT_REGISTRATION-amendment-2.json')
incumbent.require(incumbent.canonical(incumbent.runtime_versions()) == incumbent.canonical(registration['runtime_versions']), 'Exact registered runtime differs')
cache = pathlib.Path(sys.argv[3]) if sys.argv[3] else None
_, _, identity = incumbent.contract(incumbent.ROOT / 'INCUMBENT_PROTOCOL-amendment-2.json', incumbent.ROOT / 'INCUMBENT_REGISTRATION-amendment-2.json', cache)
if cache is not None:
    import data
    primary = incumbent.read_json(incumbent.ROOT / incumbent.PRIMARY_PROTOCOL)
    incumbent.require(incumbent.canonical(data.archive_manifest(cache)) == incumbent.canonical(primary['data']['archives']), 'Data archives differ')
incumbent.write_json(pathlib.Path(sys.argv[2]), {'status': 'PASS', 'identity': identity, 'pixels_decoded': 0, 'predictions_performed': 0})
print('Exact frozen contract verified; no public image pixels decoded or predictions performed')
"""
        if args.data_cache:
            args.data_cache = outside_edition(args.data_cache)
            require((args.data_cache / "FETCH.json").is_file(), "Data acquisition receipt missing")
        command([python, "-c", contract_code, ROOT, args.output / "CONTRACT.json", str(args.data_cache) if args.data_cache else ""], "verify-contract", args.output, record, env)
        record.update(status="READY_FOR_REPRODUCTION", weights=str(weights), python=str(python),
                      runtime_verified=json.loads((args.output / "PREFLIGHT.json").read_text())["runtime_versions"])
    except BaseException as error:
        record.update(status="FAILED", error_type=type(error).__name__, error=str(error))
        raise
    finally:
        record.update(finished_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                      setup_process_cpu_seconds=time.process_time() - cpu,
                      wall_seconds=time.perf_counter() - started,
                      cost_scope="Measured setup process/child CPU and wall time; upstream training, authoring and host billing are unknown, not zero.")
        write_json(args.output / "SETUP.json", record)
        print(json.dumps({"status": record["status"], "receipt": str(args.output / "SETUP.json")}), flush=True)


if __name__ == "__main__":
    main()
