#!/usr/bin/env python3
"""Verify an externally identified HARNESS archive and operate its extracted bytes.

SPDX-License-Identifier: Apache-2.0
Copyright 2026 Vincent Boucher
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile
import time
import zipfile

from package_release import MAX_ARCHIVE, verify_snapshot

try:
    import resource
except ImportError:  # Windows has no Unix getrusage; never invent a CPU reading.
    resource = None


def qualify(archive: Path, expected_sha256: str, expected_revision: str, output: Path, dom_modules: Path | None = None) -> dict:
    if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256):
        raise ValueError("An externally supplied SHA-256 is required")
    if not re.fullmatch(r"[a-f0-9]{40}", expected_revision):
        raise ValueError("An exact externally supplied source revision is required")
    with archive.open('rb') as stream:
        data = stream.read(MAX_ARCHIVE)
        if len(data) >= MAX_ARCHIVE or stream.read(1):
            raise ValueError('Archive exceeds the processing envelope')
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("Archive differs from the externally supplied SHA-256")
    integrity = verify_snapshot(data, expected_sha256=expected_sha256, expected_source_revision=expected_revision)
    if integrity["source_revision"] != expected_revision or not integrity.get("source_claim_matches_commit") or integrity.get("build_mode") != "source-bound":
        raise ValueError("Archive is not bound to the requested committed source")
    output.mkdir(parents=True, exist_ok=False)
    receipt = {"schema": "alpha-genesis-harness-downloaded-operation/v1", "verdict": "INVALID",
               "archive_sha256": expected_sha256, "source_revision": expected_revision,
               "operations": [], "scope": "Extracted-byte automated operation on this host; not cross-platform, authenticated-provider or commercial qualification.",
               "actual_inference_cost": "No provider requests", "actual_host_cost": "Unknown",
               "host": {"platform": platform.platform(), "python": platform.python_version()},
               "dom_qualification": "REQUESTED" if dom_modules else "NOT TESTED: no explicit DOM dependency directory supplied"}
    start = time.monotonic()
    initial_usage = resource.getrusage(resource.RUSAGE_CHILDREN) if resource else None
    try:
        with tempfile.TemporaryDirectory(prefix="harness-clean-") as folder:
            # verify() rejects traversal, aliases, symlinks, oversize and unlisted members.
            with zipfile.ZipFile(io.BytesIO(data)) as bundle:
                bundle.extractall(folder)
            roots = list(Path(folder).iterdir())
            if len(roots) != 1 or not roots[0].is_dir():
                raise ValueError("Expected one extracted product directory")
            product = roots[0]
            tests = sorted(str(p.relative_to(product)) for p in (product / "tests").glob("*.test.cjs"))
            if not tests:
                raise ValueError("Archive contains no executable engine acceptance suite")
            commands = [["node", "--test", *tests],
                        [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"]]
            if not (product / "tests/test_bridge.py").is_file():
                raise ValueError("Archive contains no provider fixture regression suite")
            if (product / "launch.py").is_file():
                commands.append([sys.executable, "-B", "launch.py", "--help"])
            if platform.system() == "Linux" and (product / "Launch-HARNESS.sh").is_file():
                commands.append(["sh", "Launch-HARNESS.sh", "--help"])
            if (product / "bridge/workflows.py").is_file():
                commands.append([sys.executable, "-B", "-m", "bridge.workflows", "demo",
                                 "--workspace", str(Path(folder) / "private-demo"),
                                 "--output", str(output.resolve() / "WORKFLOW-DEMONSTRATION.json")])
            if (product / "bridge/genesis_next.py").is_file():
                for required in ("docs/OMEGA-GENESIS-NEXT.md", "evidence/OMEGA-PROTOCOL.md",
                                 "tests/test_genesis_next.py", "tests/test_genesis_next_independent.py",
                                 "evidence/OMEGA-FRESH-SUCCESSOR-PROTOCOL.md", "scripts/qualify_genesis_successor.py"):
                    if not (product / required).is_file():
                        raise ValueError("Archive lacks an Ω qualification dependency: " + required)
                commands.append([sys.executable, "-B", "-m", "bridge.genesis_next", "demo",
                                 "--workspace", str(Path(folder) / "private-omega-demo"), "--authorize",
                                 "--output", str(output.resolve() / "OMEGA-DEMONSTRATION.json")])
                frozen = str(output.resolve() / "OMEGA-FRESH-SOURCE-FREEZE.json")
                commands.append([sys.executable, "-B", "scripts/qualify_genesis_successor.py", "freeze", "--output", frozen])
                commands.append([sys.executable, "-B", "scripts/qualify_genesis_successor.py", "run", "--freeze", frozen,
                                 "--output", str(output.resolve() / "OMEGA-FRESH-SUCCESSOR.json")])
            if (product / "bridge/strategy_demo.py").is_file():
                commands.append([sys.executable, "-B", "-m", "bridge.strategy_demo",
                                 "--workspace", str(Path(folder) / "private-strategy-demo"),
                                 "--output", str(output.resolve() / "STRATEGY-DEMONSTRATION.json")])
            if dom_modules is not None:
                dom_modules = dom_modules.resolve(strict=True)
                expected = json.loads((product / "tests/dom/package.json").read_text())["dependencies"]["jsdom"]
                actual = json.loads((dom_modules / "jsdom/package.json").read_text())["version"]
                if actual != expected:
                    raise ValueError("DOM dependency version differs from the packaged exact requirement")
                replays = ["UI_REPLAY.cjs", "UI_PARALLEL_REPLAY.cjs", "UI_CONNECTED_ACCEPTANCE.cjs",
                           "UI_AGENTIC_REPLAY.cjs", "UI_HTTP_WORKFLOW_REPLAY.cjs"]
                if (product / "bridge/genesis_next.py").is_file():
                    replays.append("UI_GENESIS_NEXT_REPLAY.cjs")
                for replay in replays:
                    path = product / "evidence" / replay
                    if not path.is_file() or path.is_symlink():
                        raise ValueError("Archive lacks a requested DOM acceptance replay: " + replay)
                    commands.append(["node", "evidence/" + replay])
                receipt["dom_dependency"] = {"name": "jsdom", "version": actual, "bundled": False,
                                              "scope": "Explicit development dependency; extracted application and replay bytes"}
            for index, command in enumerate(commands, 1):
                phase = time.monotonic()
                # Extracted tests never inherit GitHub tokens or caller credentials.
                environment = {"PATH": os.environ.get("PATH", os.defpath), "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
                # These are OS/runtime paths, not arbitrary inherited credentials.
                for name in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):
                    if name in os.environ:
                        environment[name] = os.environ[name]
                if dom_modules is not None:
                    environment["NODE_PATH"] = str(dom_modules)
                    environment["PYTHON"] = sys.executable
                process = subprocess.run(command, cwd=product, env=environment, capture_output=True, text=True)
                (output / f"operation-{index}.stdout.txt").write_text(process.stdout, encoding="utf-8")
                (output / f"operation-{index}.stderr.txt").write_text(process.stderr, encoding="utf-8")
                receipt["operations"].append({"command": command, "returncode": process.returncode,
                                              "wall_seconds": round(time.monotonic()-phase, 6)})
                if process.returncode:
                    raise ValueError(f"Extracted operation {index} failed; preserved logs identify the failure")
            if (product / "bridge/genesis_next.py").is_file():
                omega = json.loads((output / "OMEGA-DEMONSTRATION.json").read_text())["experiment"]
                fresh = json.loads((output / "OMEGA-FRESH-SUCCESSOR.json").read_text())
                if omega["qualification"]["correctness"] != "PASS" or fresh["status"] != "PASS":
                    raise ValueError("Extracted Ω qualification did not pass its fixed correctness requirements")
                receipt["omega_qualification"] = {
                    "correctness": omega["qualification"]["correctness"],
                    "scientific_verdict": omega["qualification"]["scientific_verdict"],
                    "fresh_successor_status": fresh["status"],
                    "strong_control_advantage": fresh["strong_control_advantage"],
                    "complete_costs_known": fresh["complete_costs_known"],
                    "source_sha256": fresh["source_sha256"],
                    "evidence_files": ["OMEGA-DEMONSTRATION.json", "OMEGA-FRESH-SOURCE-FREEZE.json", "OMEGA-FRESH-SUCCESSOR.json"],
                }
            receipt["verdict"] = "PASSED IN SCOPE"
            if dom_modules is not None:
                receipt["dom_qualification"] = "PASS: extracted-byte DOM and actual loopback HTTP replays; authored model fixtures, not graphical or live-provider qualification"
    except BaseException as exc:
        receipt["error"] = str(exc)
        raise
    finally:
        receipt["wall_seconds"] = round(time.monotonic()-start, 6)
        usage = resource.getrusage(resource.RUSAGE_CHILDREN) if resource else None
        receipt["child_cpu_seconds"] = round(usage.ru_utime + usage.ru_stime - initial_usage.ru_utime - initial_usage.ru_stime, 6) if usage else None
        (output / "QUALIFICATION.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--expected-source-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dom-modules", type=Path, help="Explicit pinned development node_modules directory; runs all packaged DOM/HTTP replays without inheriting other environment variables")
    args = parser.parse_args()
    print(json.dumps(qualify(args.archive, args.expected_sha256, args.expected_source_revision, args.output, args.dom_modules), indent=2))


if __name__ == "__main__":
    main()
