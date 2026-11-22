"""Exact finite-domain conformance of an executable to an independently audited policy.

This is a *bounded, deterministic JSONL contract check*, NOT a proof over all machine
inputs, all memory states, concurrency, or compiler semantics. Default isolated Docker.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from audit import audit
from engine import canonical


class ContractError(Exception):
    pass


def binary_conformance(model, cert, executable, *, unsafe_local=False, max_cases=25000):
    """Compare an actual executable on EVERY reachable state × action combination."""
    audit(model, cert)
    actions = sorted(a["name"] for a in model["actions"])
    states = cert["states"]
    if len(states) * len(actions) > max_cases:
        raise ContractError("finite executable test budget exceeded: HOLD, not PASS")
    executable = Path(executable).resolve()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise ContractError("executable missing or not runnable")
    varnames = cert["variables"]
    graph = {(tuple(edge["from"]), edge["action"]): edge["to"] for edge in cert["edges"]}
    requests, wants = [], []
    for state in states:
        for action in actions:
            requests.append({"state": dict(zip(varnames, state)), "action": action})
            key = (tuple(state), action)
            wants.append({"state": dict(zip(varnames, graph[key]))} if key in graph else {"rejected": True})
    payload = "\n".join(canonical(req) for req in requests) + "\n"
    if len(payload.encode()) > 8_000_000:
        raise ContractError("input too large")
    if unsafe_local:
        command = [str(executable)]
        mode = "UNSAFE_LOCAL_TRUSTED_FIXTURE_ONLY"
    else:
        if not shutil.which("docker"):
            raise ContractError("Docker missing: fail closed; do not execute untrusted binary on host")
        command = ["docker", "run", "--rm", "-i", "--network=none", "--read-only",
                   "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=65534:65534",
                   "--pids-limit=32", "--memory=256m", "--cpus=1",
                   "--tmpfs=/tmp:rw,noexec,nosuid,size=16m",
                   "--mount", f"type=bind,src={executable},dst=/job/oracle,readonly",
                   "python:3.12-slim", "/job/oracle"]
        mode = "DOCKER_NO_NETWORK_RESTRICTED"
    try:
        proc = subprocess.run(command, input=payload, text=True, capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ContractError(f"execution failed safely: {exc}") from exc
    if proc.returncode != 0 or proc.stderr.strip() or len(proc.stdout.encode()) > 8_000_000:
        raise ContractError(f"binary errored, produced stderr or exceeded cap: rc={proc.returncode}")
    lines = proc.stdout.splitlines()
    if len(lines) != len(wants):
        raise ContractError(f"binary response count mismatch: {len(lines)} versus {len(wants)}")
    mismatches = []
    for idx, (line, want) in enumerate(zip(lines, wants)):
        try:
            observed = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ContractError("non-JSON executable output") from exc
        if canonical(observed) != canonical(want):
            mismatches.append({"request": requests[idx], "expected": want, "observed": observed})
            if len(mismatches) == 3:
                break
    return {"schema": "proof-omega.binary-conformance.v1",
            "status": "PASS_BOUNDED_EXECUTABLE_CONFORMANCE" if not mismatches else "FAIL_MISMATCH",
            "model_sha256": cert["model_sha256"],
            "binary_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
            "cases": len(requests), "mode": mode, "mismatches": mismatches,
            "scope": "all reachable certified states x declared actions; deterministic JSONL adapter only"}
