"""One explicit R2 case per invocation, with kernel-bounded worker admission.

The original financial worker is unchanged. No daemon, account reset, shorter
modeled horizon or automatic retry is implemented here.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

from connected_enterprise.finance import source_identity
from experiments.public_portfolio_20261102 import economics, qualification_run, service

AMENDMENT = economics.PREFIX + "EXECUTION_AMENDMENT_R2_002.json"
STAGE = "EXECUTION_STAGE_002.json"
STOP = "EXECUTION_FAILURE_STOP_002.json"


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source_hashes(root):
    return {name: _hash(root / name) for name in (
        economics.PREFIX + "dispatch_case.py", AMENDMENT,
        economics.PREFIX + "qualification_run.py")}


def _assert_native_source(root, products, amendment):
    manifest = service.prepare_manifest(root, products, "nonwriting-dispatch-source-check-002")
    identity = source_identity(root, manifest)
    if identity["sha256"] != amendment["unchanged_financial_source_sha256"]:
        raise ValueError("ORIGINAL_COMPLETE_NATIVE_SOURCE_REQUIRED_BEFORE_ADMISSION")
    return identity["sha256"]


def _assert_publication_sha(value):
    if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("EXACT_PUBLICATION_COMMIT_HEX_REQUIRED")


def _load(root, output):
    amendment = json.loads((root / AMENDMENT).read_text())
    original_amendment = json.loads((root / qualification_run.AMENDMENT).read_text())
    qualification_run._assert_math(root, original_amendment)
    protocol = json.loads((output / "public/protocol.json").read_text())
    if protocol != json.loads((root / economics.PROTOCOL).read_text()):
        raise ValueError("ORIGINAL_REGISTERED_PROTOCOL_REQUIRED")
    plans = qualification_run.planned_cases(protocol)
    if json.loads((output / "control/PLANNED_CASES.json").read_text()) != plans:
        raise ValueError("ORIGINAL_110_CASE_PLAN_REQUIRED")
    identity = json.loads((output / "public/RUN_IDENTITY.json").read_text())
    product_path = root / economics.PREFIX / "PRODUCTS.json"
    if _hash(product_path) != identity["products_file_sha256"]:
        raise ValueError("ORIGINAL_APPROVED_PRODUCTS_REQUIRED")
    products = json.loads(product_path.read_text())
    if isinstance(products, dict):
        products = products["products"]
    _assert_native_source(root, products, amendment)
    return amendment, original_amendment, protocol, plans, products


def register(root, output, publication_sha):
    root, output = Path(root).resolve(), Path(output).resolve()
    _assert_publication_sha(publication_sha)
    amendment, _, _, plans, _ = _load(root, output)
    complete, interrupted, unstarted, prefix = [], [], [], {}
    for plan in plans:
        case = plan["case_id"]
        reservation = output / "control/reservations" / (case + ".json")
        if not reservation.exists():
            if (output / "public" / case).exists() or (output / "private" / case).exists():
                raise ValueError("UNRESERVED_EXISTING_ACCOUNT_REFUSED")
            unstarted.append(case)
            continue
        row = json.loads(reservation.read_text())
        if row["status"] == "COMPLETE":
            complete.append(case)
        elif row["status"] in {"RUNNING", "RECOVERING_SAME_ACCOUNT"}:
            interrupted.append(case)
        else:
            raise ValueError("ACTUAL_FAILURE_IS_NOT_A_HOST_INTERRUPTION")
        prefix[case] = {p.name: _hash(p) for p in sorted((output / "public" / case).iterdir()) if p.is_file()}
    observed = {"completed": len(complete), "interrupted_case_ids": interrupted,
                "not_started": len(unstarted)}
    if observed != amendment["expected_registration_state"]:
        raise ValueError("PROSPECTIVE_EXECUTION002_STATE_REQUIRED")
    stage = {"schema": "public-portfolio/bounded-case-dispatch/v2", "publication_sha": publication_sha,
             "native_source_sha256": amendment["unchanged_financial_source_sha256"],
             "source_hashes": _source_hashes(root), "observed": observed,
             "complete_case_ids_read_only": complete, "public_prefix_hashes": prefix,
             "scope": "Original R2 continuation through explicit one-case calls; no financial-world change",
             "unknown_interrupted_process_resource_totals": None}
    economics._save(output / "public" / STAGE, stage)
    return stage


def _check_stage(root, output, publication_sha):
    stage = json.loads((output / "public" / STAGE).read_text())
    if stage["publication_sha"] != publication_sha or stage["source_hashes"] != _source_hashes(root):
        raise ValueError("EXACT_PROSPECTIVE_DISPATCH_SOURCE_REQUIRED")
    for case, files in stage["public_prefix_hashes"].items():
        for name, expected in files.items():
            if case not in stage["complete_case_ids_read_only"] and name != "manifest.json":
                continue
            path = output / "public" / case / name
            if path.is_symlink() or _hash(path) != expected:
                raise ValueError("ORIGINAL_COMPLETE_EVIDENCE_AND_MANIFESTS_READ_ONLY")
    return stage


@contextmanager
def _slot(output):
    streams = []
    acquired = None
    try:
        for index in range(4):
            stream = (output / "control" / ("financial-worker-slot-" + str(index) + ".lock")).open("a+b")
            streams.append(stream)
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = stream
                break
            except BlockingIOError:
                pass
        if acquired is None:
            raise BlockingIOError("FOUR_FINANCIAL_WORKER_SLOTS_ALREADY_OCCUPIED")
        yield
    finally:
        for stream in streams:
            stream.close()


def dispatch(root, output, case_id, publication_sha, *, resume_host_interruption=False):
    root, output = Path(root).resolve(), Path(output).resolve()
    _assert_publication_sha(publication_sha)
    _, original_amendment, protocol, plans, products = _load(root, output)
    stage = _check_stage(root, output, publication_sha)
    matches = [p for p in plans if p["case_id"] == case_id]
    if len(matches) != 1:
        raise ValueError("EXACT_REGISTERED_CASE_REQUIRED")
    plan = matches[0]
    if case_id in stage["complete_case_ids_read_only"]:
        raise ValueError("ORIGINAL_COMPLETE_CASE_IS_READ_ONLY")
    with _slot(output):
        # This short lock serializes admission only, never financial execution.
        with (output / "control/dispatch-admission-002.lock").open("a+b") as admission:
            fcntl.flock(admission.fileno(), fcntl.LOCK_EX)
            if (output / "public" / STOP).exists():
                raise ValueError("ACTUAL_FAILURE_STOPS_NEW_DISPATCH_NO_RETRY")
            reservation = output / "control/reservations" / (case_id + ".json")
            if resume_host_interruption:
                if not reservation.is_file():
                    raise ValueError("HOST_RECOVERY_REQUIRES_ORIGINAL_RESERVATION")
                row = json.loads(reservation.read_text())
                if row["status"] not in {"RUNNING", "RECOVERING_SAME_ACCOUNT"}:
                    raise ValueError("ONLY_INTERRUPTED_ORIGINAL_ACCOUNT_MAY_RESUME")
                if (output / "public" / case_id / "FAILURE.json").exists():
                    raise ValueError("ACTUAL_CASE_FAILURE_IS_NOT_RETRIED")
                # Fast recovery has its own separately published/tested source
                # registration. The fresh-case dispatcher cannot authorize it.
                from experiments.public_portfolio_20261102 import recovery_fast
                recovery_fast.assert_registered(root, output)
                mode = "SAME_ACCOUNT_HOST_INTERRUPTION_CONTINUATION"
            else:
                if reservation.exists() or (output / "public" / case_id).exists() or (output / "private" / case_id).exists():
                    raise ValueError("FRESH_CASE_MUST_NEVER_HAVE_STARTED")
                mode = "ORIGINAL_NEVER_STARTED_WORKER_ONCE"
            attempts = output / "control/dispatch002" / case_id
            attempts.mkdir(parents=True, exist_ok=True)
            number = len(list(attempts.glob("INTENT_*.json"))) + 1
            intent = {"schema": "public-portfolio/explicit-case-call/v2", "case_id": case_id,
                      "planned_index": plan["index"], "attempt": number, "mode": mode,
                      "publication_sha": publication_sha, "source_hashes": stage["source_hashes"],
                      "pid": os.getpid(), "no_reset_or_reseed": True}
            economics._save(attempts / ("INTENT_" + str(number).zfill(3) + ".json"), intent)
            if not resume_host_interruption:
                economics._save(reservation, {"schema": "public-portfolio/exclusive-r2-case-reservation/v1",
                                               "case_id": case_id, "planned_index": plan["index"],
                                               "status": "RESERVED", "no_prior_account_or_cash_imported": True})
        started = time.perf_counter()
        try:
            if resume_host_interruption:
                result = recovery_fast.recover_dispatch(root, output, products, protocol, plan, number)
            else:
                result = qualification_run._worker(str(root), str(output), products, protocol,
                                                   original_amendment, plan)
            if not result["ok"]:
                raise ValueError("ORIGINAL_WORKER_FAILED:" + result.get("error", ""))
            _check_stage(root, output, publication_sha)
            receipt = {"schema": "public-portfolio/explicit-case-call-receipt/v2", "status": "COMPLETE",
                       "intent": intent, "wall_seconds_this_call": time.perf_counter() - started,
                       "result_sha256": _hash(output / "public" / case_id / "RESULT.json"),
                       "unknown_prior_interrupted_resource_totals": None}
            economics._save(output / "public" / case_id / ("DISPATCH002_RECEIPT_" + str(number).zfill(3) + ".json"), receipt)
            return result
        except Exception as error:
            stop = {"schema": "public-portfolio/actual-failure-stop/v2", "case_id": case_id,
                    "attempt": number, "error_type": type(error).__name__, "error": str(error)[:2000],
                    "no_automatic_retry": True, "preserve_accounts_and_obligations": True}
            try:
                economics._save(output / "public" / STOP, stop)
            except FileExistsError:
                pass
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--output", required=True)
    parser.add_argument("--publication-sha", required=True)
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--case")
    parser.add_argument("--resume-host-interruption", action="store_true")
    args = parser.parse_args()
    if args.register:
        result = register(args.root, args.output, args.publication_sha)
        print(json.dumps({"status": "REGISTERED", "observed": result["observed"]}))
    else:
        if not args.case:
            parser.error("--case is required")
        result = dispatch(args.root, args.output, args.case, args.publication_sha,
                          resume_host_interruption=args.resume_host_interruption)
        print(json.dumps({"status": "COMPLETE", "case_id": result["case_id"]}))
