#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""One real official-source observation; no model, login, retry or background job.

Exit 0: bounded retrieval and reported-evidence replay passed.
Exit 2: the existing source-transport boundary blocked the observation.
Exit 1: an implementation, identity or lifecycle invariant failed.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bridge.adapters import BridgeError, Runtime
from bridge.frontier_monitor import FrontierMonitorService
from bridge.genesis_next import GenesisNextService
from bridge.workflows import WorkflowService

SOURCE_URL = "https://developers.openai.com/siwc/token-sharing-open-source"
SOURCE_HOST = "developers.openai.com"
CAPABILITY_ID = "chatgpt-plan-access"
TRANSPORT_BLOCKERS = {"SOURCE_URL", "SOURCE_CONNECTION", "SOURCE_HTTP", "SOURCE_TYPE", "SOURCE_SIZE"}
SOURCE_FILES = ("bridge/adapters.py", "bridge/workflows.py", "bridge/instruments.py", "bridge/genesis_next.py",
                "bridge/frontier_monitor.py", "scripts/probe_frontier_monitor.py")


def source_identities():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def probe():
    """Exercise the actual service with one exact source and a fresh private root."""
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    sources = source_identities()
    receipt = {"schema": "alpha-genesis-live-frontier-observation/v1", "status": "FAIL",
               "attempted_at": datetime.now(timezone.utc).isoformat(), "source_url": SOURCE_URL,
               "allowed_hosts": [SOURCE_HOST], "source_sha256": sources,
               "scope": "One official HTTPS retrieval and reported-evidence replay. Not semantic source validation, model entitlement, continuous broad awareness, a reproduced capability, or commercial approval.",
               "publication_time": None, "publication_age_verified": False, "byte_change_observed": None,
               "inference_calls": 0, "real_credentials_used": False, "paid_requests_enabled": False,
               "source_observation_attempts": 0, "http_dispatch_verified": False, "background_monitoring_started": False,
               "environment": {"system": platform.system(), "machine": platform.machine(), "python": platform.python_version()},
               "complete_economic_cost_known": False}
    monitor = workflows = None
    try:
        with ExitStack() as stack:
            temporary = stack.enter_context(tempfile.TemporaryDirectory(prefix="harness-frontier-observation-"))
            # Resolve the temporary parent (notably /var on macOS) before the
            # existing private-workspace symlink boundary validates it.
            workspace = Path(temporary).resolve() / "workspace"
            runtime = Runtime({"providers": {}, "source_hosts": [SOURCE_HOST], "local_only": False,
                               "allow_paid_requests": False, "session_budget_usd": 0})
            workflows = WorkflowService(runtime, workspace)
            stack.callback(workflows.close)
            genesis = GenesisNextService(workflows)
            opportunity = genesis.add_opportunity({"title": "Review current ChatGPT-plan integration documentation",
                "description": "Observed official bytes can reopen a documentation review. This probe does not establish eligibility, consent, entitlement or commercial authorization.",
                "required_capabilities": [CAPABILITY_ID], "blocking_conditions": ["Current official conditions need an independently checked interpretation."],
                "verification_probability": None})["opportunity"]
            monitor = FrontierMonitorService(workflows, genesis)
            stack.callback(monitor.close)
            job = monitor.add({"url": SOURCE_URL, "title": "Official Sign in with ChatGPT open-source documentation",
                               "capability_ids": [CAPABILITY_ID], "interval_seconds": 3600,
                               "authorize": True, "resume_after_restart": False})["job"]
            require(not job["enabled"] and not monitor.status()["worker_running"], "Adding the source unexpectedly started background work.")
            receipt["source_observation_attempts"] = 1
            outcome = monitor.poll({"job_id": job["id"]})
            observation = outcome["observation"]
            receipt["observation"] = observation
            receipt["job"] = outcome["state"]["jobs"][0]
            if observation.get("status") == "FAILED":
                code = observation.get("error_code", "UNKNOWN_SOURCE_FAILURE")
                receipt.update(status="BLOCKED" if code in TRANSPORT_BLOCKERS else "FAIL", error_code=code)
            else:
                require(observation.get("status") == "INITIAL_OBSERVATION", "Fresh source did not produce an initial observation.")
                require(observation.get("previous_sha256") is None, "Fresh source asserted an unobserved previous identity.")
                require(observation.get("replayed") is True, "Fetched source was not committed as reported GENESIS evidence.")
                events = genesis.status()["frontier_events"]
                require(len(events) == 1 and events[0]["url"] == SOURCE_URL and events[0]["content_sha256"] == observation["sha256"],
                        "GENESIS evidence identity differs from the observed official source.")
                require(events[0]["evidence_status"] == "reported", "Source observation was improperly promoted to reproduced evidence.")
                reconsidered = next(o for o in genesis.status()["opportunities"] if o["id"] == opportunity["id"])
                require(reconsidered["status"] == "reconsider", "Source association did not reopen its registered question.")
                history = receipt["job"]["history"]
                require(len(history) == 1 and history[0]["status"] == "INITIAL_OBSERVATION"
                        and history[0]["sha256"] == observation["sha256"], "Monitor history does not bind the fetched observation.")
                receipt.update(status="PASS", evidence_event=events[0], opportunity_status=reconsidered["status"],
                               actual_source_sha256=observation["sha256"], retrieved_at=observation["retrieved_at"], http_dispatch_verified=True)
            stopped = monitor.stop({"job_id": job["id"]})
            require(stopped["job"]["enabled"] is False, "Probe did not stop its source job.")
            require(not stopped["state"]["worker_running"], "Unexpected background worker remained active.")
            receipt["stopped"] = True
            monitor.close(); workflows.close()
            monitor = workflows = None
        receipt["temporary_workspace_removed"] = not workspace.exists()
        require(receipt["temporary_workspace_removed"], "Temporary private observation workspace was not removed.")
        require(source_identities() == sources, "Source files changed during the observation probe.")
    except BridgeError as error:
        receipt.update(status="BLOCKED" if error.code in TRANSPORT_BLOCKERS else "FAIL", error_code=error.code)
    except Exception as error:
        # Error type and fixed local invariant messages only; no remote body,
        # exception URL, environment value or private directory is copied.
        receipt.update(status="FAIL", error_type=type(error).__name__)
        if isinstance(error, ValueError):
            receipt["invariant_failure"] = str(error)[:300]
    finally:
        if monitor is not None:
            monitor.close()
        if workflows is not None:
            workflows.close()
        receipt["wall_seconds"] = time.perf_counter() - started_wall
        receipt["cpu_seconds"] = time.process_time() - started_cpu
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New JSON receipt; existing files are never overwritten.")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error("Output already exists; preserve the prior observation and choose a new receipt path.")
    result = probe()
    raw = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            output.write(raw)
    print(raw, end="")
    return {"PASS": 0, "BLOCKED": 2, "FAIL": 1}[result["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
