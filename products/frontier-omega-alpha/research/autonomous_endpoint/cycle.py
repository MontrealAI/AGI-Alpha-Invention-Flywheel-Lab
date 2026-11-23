#!/usr/bin/env python3
"""Run, resume or verify the registered non-production Endpoint Field Lab cycle."""
from argparse import ArgumentParser
import base64
from contextlib import contextmanager
from copy import deepcopy
from datetime import date
import fcntl
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import platform
import secrets
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading

from common import (CONSTRUCTOR, HERE, LEGACY, REGISTRATION, ROOT, SANDBOX, atomic, checked,
                    clock, decode, encode, load_module, measure, read, require, sha)
from evaluation import DECIMAL, admitted, authenticated, capsule_groups, certify, choose_cases, compare, from_capsule, oracle

PUBLIC_RECEIPT = "receipt.json"
PROBES = ("read", "write", "network", "exec", "fork", "environment")


def checkpoint(path, content):
    if path.exists():
        require(read(path) == content, "CHECKPOINT_IDENTITY_CHANGED")
    else:
        atomic(path, content)


def identities(registration):
    sources = [REGISTRATION, SANDBOX, CONSTRUCTOR, LEGACY, HERE / "common.py",
               HERE / "evaluation.py", Path(__file__).resolve()]
    manifest = {str(path.relative_to(ROOT)): sha(path.read_bytes()) for path in sources}
    require(manifest[str(SANDBOX.relative_to(ROOT))] == registration["custody"]["sandbox_sha256"],
            "SANDBOX_IDENTITY_MISMATCH")
    return manifest


def acquire(state, registration, exercise):
    costs, attempts = {}, []
    source = ROOT / registration["source"]["path"]
    for attempt in range(2):
        injected = exercise and attempt == 0
        location = state / "absent-source" if injected else source
        with measure(costs, f"source_read_{attempt + 1}"):
            try:
                raw = location.read_bytes()
            except OSError as error:
                attempts.append({"state": "SOURCE_UNAVAILABLE", "bytes": 0, "errno": error.errno,
                                 "injected": injected})
                continue
            require(not injected, "MISSING_SOURCE_CONTROL_INVALID")
            attempts.append({"state": "SOURCE_ACQUIRED", "bytes": len(raw)})
            return raw, {"attempts": attempts, "costs": costs, "kind": "registered local copy"}
    atomic(state / "acquisition-failure.json", {"attempts": attempts, "costs": costs, "observed_at": clock()})
    raise ValueError("SOURCE_UNAVAILABLE_AFTER_RETRY")


def check_custody(sandbox, state, limits):
    marker = state / "evaluator-boundary-canary.json"
    if not marker.exists():
        atomic(marker, {"canary": secrets.token_hex(32)})
    before = sha(marker.read_bytes())
    checks = {}
    for kind in PROBES:
        receipt = sandbox._invoke({"probe": kind, "path": str(marker)}, limits)
        observed = receipt.get("worker", {}).get("result", {})
        passed = observed.get("empty" if kind == "environment" else "denied") is True
        checks[kind] = {"passed": receipt["state"] == "COMPLETE" and passed,
                        "errno": observed.get("errno"), "wall_seconds": receipt["wall_seconds"]}
    checks["evaluator_file_unchanged"] = {"passed": sha(marker.read_bytes()) == before}
    require(all(check["passed"] for check in checks.values()), "CONSTRUCTOR_BOUNDARY_FAILED")
    return checks


def run_confined(sandbox, name, payload, manifest, registration):
    receipt = sandbox.run(CONSTRUCTOR, name, payload, manifest[str(CONSTRUCTOR.relative_to(ROOT))],
                          registration["custody"]["limits"])
    require(receipt["state"] == "COMPLETE" and receipt.get("stderr_bytes") == 0, "CONFINED_WORKER_FAILED")
    worker = receipt["worker"]
    execution = {k: worker[k] for k in ("confinement", "worker_wall_seconds", "worker_cpu_seconds", "peak_rss_kib")}
    execution.update({key: receipt[key] for key in
                      ("interpreter_sha256", "input_sha256", "stdout_bytes", "wall_seconds")})
    return worker["result"], execution


def invalid_checks(raw, rows, capsule, registration, state):
    checks = {}

    def rejects(name, operation, victim):
        try:
            operation()
        except (OSError, ValueError) as error:
            witness = str(error) if isinstance(error, ValueError) else type(error).__name__
            checks[name] = {"passed": witness == victim, "observed": witness}
        else:
            checks[name] = {"passed": False, "observed": "UNEXPECTED_ACCEPTANCE"}

    rejects("missing-source", lambda: (state / "absent-source").read_bytes(), "FileNotFoundError")
    rejects("digest-mismatch", lambda: authenticated(raw + b"\n", registration), "SOURCE_DIGEST_MISMATCH")
    stale = decode(raw)
    stale["generated_at"] = "2026-11-01T00:00:00.000Z"
    rejects("stale-source", lambda: admitted(stale, registration), "STALE_OR_UNREGISTERED_SOURCE")
    malformed = decode(raw)
    valid = next(record for record in malformed["rows"] if record["id"] == rows[0]["id"])
    valid["load"] = "invalid"
    rejects("malformed-source", lambda: admitted(malformed, registration), "MALFORMED_MEASUREMENT")
    valid["load"] = None
    rejects("incomplete-measurement", lambda: admitted(malformed, registration), "INCOMPLETE_MEASUREMENT")
    conflict = decode(raw)
    changed = dict(conflict["rows"][0])
    changed["load"] = 314159
    conflict["rows"].append(changed)
    rejects("contradictory-source", lambda: admitted(conflict, registration), "CONTRADICTORY_SOURCE_IDENTITY")
    forged = deepcopy(capsule)
    forged["groups"][0]["points"][0][4] += 1
    rejects("invalid-certificate", lambda: certify(rows, forged), "CERTIFICATE_CHANGED_WITNESS")
    return checks


def pilot_source(state, registration):
    spec = registration["endpoint_pilot"]
    checkout = state / "pilot-source"
    checkout.mkdir(mode=0o700, exist_ok=True)
    for name, expected in spec["sha256"].items():
        path = checkout / name
        if not path.exists():
            source = checked(["git", "-C", str(ROOT), "show", f"{spec['ref']}:{spec['path']}/{name}"])
            require(sha(source) == expected, "FA01_SOURCE_IDENTITY_MISMATCH")
            path.write_bytes(source)
        require(sha(path.read_bytes()) == expected, "FA01_SOURCE_IDENTITY_MISMATCH")
    return checkout


def overload_replay():
    """Real loopback transport against an occupied synthetic admission slot."""
    slot = threading.BoundedSemaphore(1)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            admitted = slot.acquire(blocking=False)
            body = b"ok" if admitted else b""
            try:
                self.send_response(200 if admitted else 503)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            finally:
                if admitted:
                    slot.release()

    def native(port):
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            connection.request("GET", "/")
            response = connection.getresponse()
            return [response.status, len(response.read())]
        finally:
            connection.close()

    def curl(port):
        output = checked(["curl", "-q", "--noproxy", "*", "--silent", "--max-time", "3",
                          "--write-out", "\n%{http_code}", f"http://127.0.0.1:{port}/"])
        body, status = output.rsplit(b"\n", 1)
        return [int(status), len(body)]

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        worker.start()
        results = {}
        try:
            for name, client in (("field-http", native), ("conventional-curl", curl)):
                with slot:
                    refused = client(server.server_port)
                results[name] = [refused, client(server.server_port)]
        finally:
            server.shutdown()
            worker.join()
    return {"passed": all(value == [[503, 0], [200, 2]] for value in results.values()),
            "status_and_body_bytes": results}


def pilot_replay(state, registration):
    costs = {}
    with measure(costs, "pinned_pilot_source_acquisition"):
        checkout = pilot_source(state, registration)
    # A fresh capture directory after interruption preserves partial prior runs.
    output = Path(tempfile.mkdtemp(prefix="fa01-", dir=state)) / "capture"
    with measure(costs, "matched_live_loopback_replay"):
        checked([sys.executable, "-B", str(checkout / "field.py"), "fixture", "--output", str(output)])
    with measure(costs, "separate_sqlite_wire_replay"):
        verified = checked([sys.executable, "-B", str(checkout / "verify.py"), "--public", str(output / "PUBLIC.json")])
    projection = read(output / "PUBLIC.json")
    arms = projection["arms"]
    require(len(arms) == 8, "PILOT_DENOMINATOR_CHANGED")
    results = {}
    for target in ("nominal", "adverse"):
        results[target] = {}
        for method in ("field", "conventional"):
            qualifying = [a["concurrency"] for a in arms if a["target"] == target and a["route"] == method
                          and a["decision"] == "accept-registered-replay"]
            tested = sorted(a["concurrency"] for a in arms if a["target"] == target and a["route"] == method)
            require(tested == registration["endpoint_pilot"]["workers"], "PILOT_LOAD_DENOMINATOR_CHANGED")
            results[target][method] = max(qualifying, default="ABSTAIN")
    execution = []
    for capture in projection["receipts"]:
        path = output / capture["path"]
        execution.append({"path": capture["path"], "bytes": path.stat().st_size,
                          "sha256": capture["sha256"], "costs": read(path)["cost"],
                          "verification_wall_us": capture["verification_wall_us"],
                          "verification_process_cpu_us": capture["verification_process_cpu_us"]})
    return {"source_ref": registration["endpoint_pilot"]["ref"], "arms": arms,
            "highest_observed_qualifying_load": results, "public_projection_sha256": sha((output / "PUBLIC.json").read_bytes()),
            "independent_verifier_output_sha256": sha(verified), "capture_costs": execution,
            "raw_capture_bytes": sum(capture["bytes"] for capture in execution), "costs": costs}


def signature(state, receipt):
    key, data = state / "evaluator.key", state / "signature-input.json"
    if not key.exists():
        private_key = checked(["openssl", "genpkey", "-algorithm", "ED25519"])
        with tempfile.NamedTemporaryFile(dir=state, prefix=".new-key-") as out:
            out.write(private_key)
            out.flush()
            os.fsync(out.fileno())
            os.link(out.name, key)
    public = checked(["openssl", "pkey", "-in", str(key), "-pubout"])
    atomic(data, receipt)
    signed = checked(["openssl", "pkeyutl", "-sign", "-rawin", "-inkey", str(key), "-in", str(data)])
    return {"receipt": receipt, "evaluator_public_key": public.decode(),
            "evaluator_public_key_sha256": sha(public), "signature_ed25519": base64.b64encode(signed).decode()}


def verify(path, trusted_key_sha256=None):
    envelope = read(path)
    key = envelope["evaluator_public_key"].encode()
    actual_key = sha(key)
    require(actual_key == envelope["evaluator_public_key_sha256"], "KEY_IDENTITY_MISMATCH")
    if trusted_key_sha256 is not None:
        require(actual_key == trusted_key_sha256, "UNTRUSTED_EVALUATOR_KEY")
    with tempfile.TemporaryDirectory(prefix="omega-receipt-") as temporary:
        scratch = Path(temporary)
        (scratch / "key.pem").write_bytes(key)
        (scratch / "receipt.json").write_bytes(encode(envelope["receipt"]))
        (scratch / "receipt.sig").write_bytes(base64.b64decode(envelope["signature_ed25519"], validate=True))
        checked(["openssl", "pkeyutl", "-verify", "-rawin", "-pubin", "-inkey", str(scratch / "key.pem"),
                 "-in", str(scratch / "receipt.json"), "-sigfile", str(scratch / "receipt.sig")])
    return envelope


def verified_decision(capsule_path, receipt_path, query_path, trusted_key_sha256):
    receipt = verify(receipt_path, trusted_key_sha256)["receipt"]
    require(receipt["research_verdict"] == "AGREED_WITH_EXACT_ORACLE", "CAPSULE_RECEIPT_HAS_NO_ACCEPTANCE")
    raw = capsule_path.read_bytes()
    require(sha(raw) == receipt["capsule_sha256"], "CAPSULE_IDENTITY_MISMATCH")
    query = read(query_path)
    require(isinstance(query, dict) and set(query) == {"scope", "as_of", "floor", "ceiling"} and
            isinstance(query["scope"], list) and all(isinstance(key, str) for key in query["scope"]) and
            all(isinstance(query[key], str) and DECIMAL.fullmatch(query[key]) for key in ("floor", "ceiling")) and
            isinstance(query["as_of"], str) and date.fromisoformat(query["as_of"]).isoformat() == query["as_of"],
            "INVALID_SCREENING_QUERY")
    groups = capsule_groups(decode(raw))
    if tuple(query["scope"]) not in groups or query["as_of"] > receipt["source"]["cutoff"]:
        return {"decision": "ABSTAIN", "reason": "OUTSIDE_CERTIFIED_SCOPE_OR_CUTOFF"}
    return from_capsule(groups, query)


def evaluate(state, exercise, simulate_interrupt):
    registration = read(REGISTRATION)
    manifest = identities(registration)
    locked = state / "preconstruction.json"
    if not locked.exists():
        atomic(locked, {"identities": manifest, "registered_source": registration["source"]["normalized_sha256"],
                        "cycle_policy": {"exercise_recovery": exercise}, "frozen_at": clock()})
    freeze = read(locked)
    require(freeze["identities"] == manifest and freeze["cycle_policy"] == {"exercise_recovery": exercise},
            "PRECONSTRUCTION_CONTRACT_CHANGED")
    sandbox = load_module("pinned_endpoint_sandbox", SANDBOX)
    costs = {}
    with measure(costs, "acquisition_and_admission"):
        raw, acquisition = acquire(state, registration, exercise)
        rows = authenticated(raw, registration)
        cut = registration["comparison"]["scope_keys"].index("model")
        development = [r for r in rows if r["scope"][cut] in registration["comparison"]["development_models"]]
        confirmation = [r for r in rows if r["scope"][cut] in registration["comparison"]["confirmation_models"]]
        require(development and confirmation, "MISSING_DEVELOPMENT_OR_CONFIRMATION_POPULATION")
    with measure(costs, "constructor_boundary_checks"):
        boundary = check_custody(sandbox, state, registration["custody"]["limits"])
    artifact = state / "frozen-construction.json"
    if not artifact.exists():
        with measure(costs, "construction"):
            plan, constructor = run_confined(sandbox, "construct", development, manifest, registration)
            require(set(plan) == {"method", "development_rows", "development_kept"} and
                    plan["method"] in {"dominance", "projection"} and
                    plan["development_rows"] == len(development) and
                    1 <= plan["development_kept"] <= len(development), "INVALID_CONSTRUCTION_PLAN")
        atomic(artifact, {"plan": plan, "constructor": constructor, "preconstruction_sha256": sha(locked.read_bytes()),
                          "frozen_at": clock(), "costs": costs, "first_acquisition": acquisition})
    frozen = read(artifact)
    require(frozen["preconstruction_sha256"] == sha(locked.read_bytes()) and identities(registration) == manifest,
            "CONSTRUCTION_OR_EVALUATOR_CHANGED")
    frozen_sha = sha(artifact.read_bytes())
    secret = state / "confirmation-private.json"
    if not secret.exists():
        seed = secrets.token_bytes(32)
        cases = choose_cases(confirmation, registration, seed)
        atomic(secret, {"nonce": seed.hex(), "frozen_construction_sha256": frozen_sha,
                        "selected_at": clock(), "cases": cases})
    held = read(secret)
    require(frozen_sha == held["frozen_construction_sha256"], "CONFIRMATION_BOUND_TO_DIFFERENT_ARTIFACT")
    selected = held["cases"]
    commitment = sha(bytes.fromhex(held["nonce"]) + encode(selected))
    if simulate_interrupt:
        atomic(state / "interruption.json", {"phase": "after-confirmation-freeze", "case_commitment": commitment,
                                             "artifact_sha256": frozen_sha, "stopped_at": clock(), "signal": "SIGKILL",
                                             "attempt_costs": costs, "acquisition": acquisition})
        os.kill(os.getpid(), signal.SIGKILL)
    interruption = state / "interruption.json"
    interrupted = read(interruption) if interruption.exists() else None
    if interrupted:
        require(interrupted["case_commitment"] == commitment and interrupted["artifact_sha256"] == frozen_sha,
                "RESUME_CHANGED_HELD_CASES_OR_CONSTRUCTION")
    with measure(costs, "candidate_materialization"):
        capsule, materialization = run_confined(sandbox, "materialize", {"method": frozen["plan"]["method"],
                                                  "rows": confirmation}, manifest, registration)
        checkpoint(state / "capsule.json", capsule)
    with measure(costs, "independent_coverage_verification"):
        coverage = certify(confirmation, capsule)
    with measure(costs, "controls"):
        controls = invalid_checks(raw, confirmation, capsule, registration, state)
        first = confirmation[0]
        paired = [first, dict(first, id="synthetic-equal-load-control")]
        tie_query = {"scope": first["scope"], "as_of": first["day"], "floor": first["rate"], "ceiling": first["first"]}
        tie, _ = run_confined(sandbox, "materialize", {"method": frozen["plan"]["method"],
                                 "rows": paired}, manifest, registration)
        certify(paired, tie)
        empty_authored = {"tie": tie_query, "expected": oracle(paired, tie_query)}
        checkpoint(state / "tie-control.json", empty_authored)
        tie_metrics, tie_records = compare(paired, [tie_query], tie, state, registration)
        controls["equal-load-witnesses"] = {"passed": len(empty_authored["expected"]["witnesses"]) == 2 and
                                             tie_metrics["failure_count"] == 0}
        checkpoint(state / "tie-control-scoring.json", tie_records)
    # Reload only the portable evidence for the candidate. Incumbents receive the same source rights.
    with measure(costs, "candidate_detached_read"):
        detached = read(state / "capsule.json")
        require(sha(encode(detached)) == sha(encode(capsule)), "CAPSULE_REOPEN_CHANGED")
    with measure(costs, "matched_comparison"):
        comparisons, private = compare(confirmation, selected, detached, state, registration)
        checkpoint(state / "confirmation-scoring-private.json", private)
    if exercise:
        controls["retryable-source-loss"] = {"passed": len(acquisition["attempts"]) == 2 and
                                              acquisition["attempts"][0]["state"] == "SOURCE_UNAVAILABLE" and
                                              acquisition["attempts"][1]["state"] == "SOURCE_ACQUIRED"}
        controls["interrupted-evaluation"] = {"passed": interrupted is not None}
    with measure(costs, "fa01_end_to_end"):
        pilot = pilot_replay(state, registration)
    with measure(costs, "bounded_overload_recovery"):
        controls["bounded-overload-recovery"] = overload_replay()
    pilot_control = pilot["highest_observed_qualifying_load"]["adverse"]
    controls["fault_injected_loopback"] = {"passed": all(value == "ABSTAIN" for value in pilot_control.values())}
    controls["pilot_transport_recovery"] = {"passed": all(a["attempts"] == 7 and a["quality_accepted"] == 2
                                                          for a in pilot["arms"] if a["target"] == "adverse")}
    require(identities(registration) == manifest and sha(artifact.read_bytes()) == frozen_sha and
            sha((state / "capsule.json").read_bytes()) == sha(encode(capsule)), "FROZEN_INPUT_CHANGED")
    accepted = comparisons["failure_count"] == 0 and all(check["passed"] for check in controls.values())
    receipt = {"schema": "frontier-omega-alpha/autonomous-endpoint-receipt-v1", "completed_at": clock(),
               "operational_adoption": "ABSTAIN", "production_status": registration["operational"]["production_status"],
               "missing_operational_evidence": registration["operational"]["missing"],
               "research_verdict": "AGREED_WITH_EXACT_ORACLE" if accepted else "REJECTED_BY_EVALUATOR",
               "source": registration["source"], "implementation_sha256": manifest,
               "preconstruction_frozen_at": freeze["frozen_at"], "artifact_frozen_at": frozen["frozen_at"],
               "confirmation_selected_at": held["selected_at"], "confirmation_commitment_sha256": commitment,
               "frozen_artifact_sha256": frozen_sha, "plan": frozen["plan"],
               "capsule_sha256": sha(encode(capsule)), "coverage": coverage,
               "confinement": {"effects": boundary, "constructor": frozen["constructor"], "materialization": materialization,
                               "role": "confined constructor and separate trusted evaluator; local runner administrator trusted"},
               "acquisition": acquisition, "first_acquisition": frozen["first_acquisition"], "controls": controls,
               "recovery": interrupted, "comparison": comparisons, "pilot": pilot, "phase_costs": costs,
               "construction_attempt_costs": frozen["costs"],
               "environment": {"system": platform.system(), "kernel": platform.release(), "architecture": platform.machine(),
                               "python": platform.python_version(), "sqlite": sqlite3.sqlite_version,
                               "available_logical_cpus": len(os.sched_getaffinity(0))},
               "unmeasured_costs": {key: None for key in ("upstream_fees", "loaded_human_review", "energy", "engineering_total",
                                                           "long_term_maintenance", "service_fees", "support")},
               "routine_human_interventions_during_cycle": 0,
               "operating_choice": "Existing indexed SQL remains the incumbent; complete economic advantage unproven",
               "s1_admission": "NOT_ESTABLISHED", "s2_transfer": "UNPROVEN", "better_constructor": "UNPROVEN",
               "better_learning_update": "UNPROVEN"}
    public = signature(state, receipt)
    atomic(state / PUBLIC_RECEIPT, public)


@contextmanager
def exclusive_state(state):
    require(not state.is_symlink(), "STATE_SYMLINK_FORBIDDEN")
    state.mkdir(mode=0o700, exist_ok=True)
    require(state.stat().st_mode & 0o077 == 0, "EVALUATOR_STATE_MUST_BE_PRIVATE")
    fd = os.open(state / "run.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield


def run(state, output, exercise):
    with exclusive_state(state):
        target = state / PUBLIC_RECEIPT
        attempts, costs = [], {}
        if not target.exists():
            command = [sys.executable, "-B", str(Path(__file__).resolve()), "_evaluator", str(state)]
            with measure(costs, "supervised_evaluation"):
                for attempt in range(2):
                    arguments = command + (["--exercise-recovery"] if exercise else [])
                    if exercise and attempt == 0 and not (state / "interruption.json").exists():
                        arguments += ["--interrupt"]
                    evaluated = subprocess.run(arguments, check=False)
                    attempts.append(evaluated.returncode)
                    if evaluated.returncode == 0:
                        break
                    if evaluated.returncode not in {-signal.SIGKILL, -signal.SIGTERM}:
                        break
            atomic(state / "supervisor-private.json", {"evaluator_exit_codes": attempts, "costs": costs})
            require(target.exists() and attempts[-1] == 0, "EVALUATION_INCOMPLETE_CHECKPOINT_RETAINED")
        with measure(costs, "signature_verification_and_export"):
            public = verify(target)
            output.mkdir(mode=0o700, parents=True, exist_ok=True)
            atomic(output / PUBLIC_RECEIPT, public)
            if public["receipt"]["research_verdict"] == "AGREED_WITH_EXACT_ORACLE":
                capsule = state / "capsule.json"
                require(sha(capsule.read_bytes()) == public["receipt"]["capsule_sha256"], "CAPSULE_IDENTITY_MISMATCH")
                atomic(output / "capsule.json", read(capsule))
        receipt = public["receipt"]
    return {"operational_adoption": receipt["operational_adoption"], "research_verdict": receipt["research_verdict"],
            "receipt": str(output / PUBLIC_RECEIPT), "evaluator_exit_codes": attempts, "supervisor_costs": costs}


def main():
    parser = ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    launch = commands.add_parser("run")
    launch.add_argument("--state", type=Path, required=True)
    launch.add_argument("--output", type=Path, required=True)
    launch.add_argument("--exercise-recovery", action="store_true")
    check = commands.add_parser("verify")
    check.add_argument("receipt", type=Path)
    check.add_argument("--key-sha256")
    decide = commands.add_parser("decide")
    decide.add_argument("--capsule", type=Path, required=True)
    decide.add_argument("--receipt", type=Path, required=True)
    decide.add_argument("--query", type=Path, required=True)
    decide.add_argument("--key-sha256", required=True)
    worker = commands.add_parser("_evaluator")
    worker.add_argument("state", type=Path)
    worker.add_argument("--exercise-recovery", action="store_true")
    worker.add_argument("--interrupt", action="store_true")
    args = parser.parse_args()
    if args.command == "_evaluator":
        evaluate(args.state, args.exercise_recovery, args.interrupt)
        return
    if args.command == "verify":
        result = verify(args.receipt, args.key_sha256)
        print(encode({"signature_valid": True, "evaluator_key_pinned_by_caller": args.key_sha256 is not None,
                      "operational_adoption": result["receipt"]["operational_adoption"]}).decode(), end="")
        return
    if args.command == "decide":
        print(encode(verified_decision(args.capsule, args.receipt, args.query, args.key_sha256)).decode(), end="")
        return
    print(encode(run(args.state.absolute(), args.output.absolute(), args.exercise_recovery)).decode(), end="")


if __name__ == "__main__":
    main()
