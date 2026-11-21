"""Replay frozen scientific qualifications; this does not rerun AI construction.

The source manifest binds exact retained implementations, dependency bytes,
frozen scientific inputs and independent checker files. Every qualification
runs in a fresh scientific-Python process with one BLAS thread and a 10 GiB
address-space ceiling. This is not the Capability Forge seccomp sandbox.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent


def identity(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scientific_limit():
    memory = 10 * 1024 ** 3
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-arms", action="store_true",
                        help="Replay every frozen construction, including controls.")
    parser.add_argument("--output", type=Path,
                        default=Path(tempfile.mkdtemp(prefix="frontier-qec-replay-")))
    args = parser.parse_args()
    # Resolve relative paths in the caller's directory, before child cwd changes.
    args.output = args.output.expanduser().resolve()
    manifest_path = HERE / "SOURCE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    for name, expected in manifest["files"].items():
        path = HERE / name
        if identity(path) != expected:
            raise SystemExit("Source/input identity mismatch: " + name)
    args.output.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment.update(OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
                       MKL_NUM_THREADS="1", PYTHONHASHSEED="0")
    receipts = []
    arms = manifest["replays"]
    if not args.all_arms:
        arms = [arm for arm in arms if arm.get("default", False)]
    with tempfile.TemporaryDirectory(prefix="frontier-qec-bytecode-") as cache:
        environment["PYTHONPYCACHEPREFIX"] = cache
        for arm in arms:
            output = args.output / (arm["name"] + ".json")
            if output.exists():
                raise SystemExit("Choose a fresh output directory; receipt already exists: " + str(output))
            command = [sys.executable, str(HERE / arm["checker"]),
                       str(HERE / arm["candidate"]), "--output", str(output)]
            started = time.perf_counter()
            before = resource.getrusage(resource.RUSAGE_CHILDREN)
            process = subprocess.run(command, env=environment, cwd=HERE,
                                     text=True, capture_output=True,
                                     preexec_fn=scientific_limit)
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            elapsed = time.perf_counter() - started
            scientific = json.loads(output.read_text()) if output.exists() else {}
            matches = (
                process.returncode == 0
                and scientific.get("pass") == arm["expected_pass"]
                and scientific.get("passed_checks") == arm["expected_passed_checks"]
                and scientific.get("total_checks") == arm["expected_total_checks"]
            )
            row = {
                "name": arm["name"], "candidate_sha256": identity(HERE / arm["candidate"]),
                "returncode": process.returncode, "matched_recorded_verdict": matches,
                "scientific_pass": scientific.get("pass"),
                "passed_checks": scientific.get("passed_checks"),
                "total_checks": scientific.get("total_checks"),
                "wrapper_wall_seconds": elapsed,
                "child_cpu_seconds": (
                    after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime
                ),
                "scientific_wall_seconds": scientific.get("wall_seconds"),
                "scientific_cpu_seconds": scientific.get("cpu_seconds"),
                "peak_rss_kib": scientific.get("maximum_rss_kib"),
                "result_file": str(output),
                "stdout": process.stdout.strip(), "stderr": process.stderr.strip(),
            }
            receipts.append(row)
            print(json.dumps(row), flush=True)
    unchanged = all(identity(HERE / name) == expected
                    for name, expected in manifest["files"].items())
    summary = {
        "schema": "frontier.qec.replay.v1",
        "manifest_sha256": identity(manifest_path),
        "scope": "Scientific-source replay; not reconstruction latency, external certification, or economic proof.",
        "runtime": {
            "python": sys.version,
            "python_executable": sys.executable,
            "platform": platform.platform(),
            "numpy": importlib.metadata.version("numpy"),
            "scipy": importlib.metadata.version("scipy"),
            "linear_algebra_threads": 1,
            "third_party_binary_scope": "Versions recorded and pinned by requirements; external binaries and BLAS builds are not asserted byte-identical across hosts.",
        },
        "source_files_unchanged": unchanged,
        "all_recorded_verdicts_reproduced": unchanged and all(
            row["matched_recorded_verdict"] for row in receipts
        ),
        "arms": receipts,
    }
    (args.output / "SUMMARY.json").write_text(json.dumps(summary, indent=2) + "\n")
    if not summary["all_recorded_verdicts_reproduced"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
