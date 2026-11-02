"""One source-bound offline industrial construction; never opens or mutates a native account."""
import argparse
import hashlib
import json
import resource
import sys
import time
from pathlib import Path

from commercial.ledger import canonical
from industrial064.acceptance import verify
from industrial064.construct import ProducerFailure, construct
from industrial064.service import source_paths

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "campaign/industrial-funded-064/OFFLINE_SPARSE_PROBE.json"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    return digest(Path(path).read_bytes())


def run(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    protocol = json.loads(PROTOCOL.read_text())
    registration = json.loads((ROOT / "industrial064/registration.json").read_text())
    req = registration["requests"][0]
    if req["id"] != "baseline" or req["input_sha256"] != protocol["public_input"]["sha256"]:
        raise ValueError("PRECOMMITTED_REQUEST_CHANGED")
    if req["cost_ceiling_yuan"] != protocol["acceptance"]["maximum_client_operating_cost_yuan"]:
        raise ValueError("PRECOMMITTED_CLIENT_BUDGET_CHANGED")
    if req["distance_margin"] != protocol["acceptance"]["extra_distance_margin"]:
        raise ValueError("PRECOMMITTED_DISTANCE_MARGIN_CHANGED")
    if protocol["producer_solver_seconds"] != 120 or protocol["outer_worker_timeout_seconds"] != 155:
        raise ValueError("PRECOMMITTED_SOLVER_LIMIT_CHANGED")
    paths = source_paths(ROOT)
    source = {name: file_digest(ROOT / name) for name in paths}
    raw = (ROOT / req["input_path"]).read_bytes()
    if digest(raw) != req["input_sha256"]:
        raise ValueError("PUBLIC_INPUT_IDENTITY_CHANGED")
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    receipt = {
        "schema": "agi-alpha/industrial064-no-account-prototype-result/v1",
        "protocol_sha256": file_digest(PROTOCOL),
        "source_file_sha256": source,
        "source_bound_input_sha256": req["input_sha256"],
        "source_head": "GitHub Actions checks out its exact PR head, not an inferred main",
        "attempts": 1,
        "model_initial_capital": None,
        "native_account_created": False,
        "native_business_expenses": None,
        "actual_buyer_collections": 0,
        "producer": None,
        "independent_acceptance": None,
        "failure": None,
        "accepted": False,
        "claim": "OFFLINE_CONSTRUCTOR_ENGINEERING_ONLY"
    }
    try:
        plan, production = construct(ROOT, req, out / "produced")
        receipt["producer"] = production
        raw_plan = canonical(plan)
        receipt["plan_sha256"] = digest(raw_plan)
        receipt["plan_bytes"] = len(raw_plan)
        receipt["production_receipt_sha256"] = file_digest(out / "produced/production.json")
        if len(raw_plan) > protocol["acceptance"]["require_native_service_max_artifact_bytes"]:
            raise ValueError("NATIVE_SERVICE_DELIVERY_RESOURCE_BOUND")
        outcome = verify(ROOT, req, plan)
        receipt["independent_acceptance"] = outcome
        receipt["accepted"] = outcome["accepted"] is True
        if not receipt["accepted"]:
            receipt["failure"] = {"kind": "INDEPENDENT_CLIENT_REJECTION"}
    except Exception as exc:
        receipt["failure"] = {"kind": type(exc).__name__, "opaque_message_sha256": digest(str(exc).encode())}
        if isinstance(exc, ProducerFailure):
            receipt["failure"]["producer_diagnostics"] = exc.diagnostics
    finally:
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        receipt["resource"] = {
            "wall_seconds": time.monotonic() - started,
            "child_cpu_seconds": (after.ru_utime + after.ru_stime) - (before.ru_utime + before.ru_stime),
            "child_maxrss_kib_linux": after.ru_maxrss
        }
        (out / "RESULT.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
        print(json.dumps({
            "accepted": receipt["accepted"], "failure": receipt["failure"],
            "protocol_sha256": receipt["protocol_sha256"],
            "source_file_count": len(source),
            "wall_seconds": receipt["resource"]["wall_seconds"],
            "native_account_created": False
        }, sort_keys=True), flush=True)
    return receipt["accepted"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    sys.exit(0 if run(args.output) else 1)
