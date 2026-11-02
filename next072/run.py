"""Finite execution entry point; source download requires a public freeze receipt."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import resource
import sys
import time
import urllib.request

import numpy as np

from .data import InputFailure, canonical_json_hash, prepare_records, source_identity, workbook_records
from .evaluate import run
from .freeze import validate_freeze
from .protocol import EXPERIMENT_ID, PRIMARY_POLICY, SOURCE_BLOB, SOURCE_COMMIT, SOURCE_PATH, SOURCE_URL


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def runtime_limits():
    out = {}
    for key, path in (("memory_max_bytes", "/sys/fs/cgroup/memory.max"), ("cpu_quota_period", "/sys/fs/cgroup/cpu.max")):
        try:
            out[key] = Path(path).read_text().strip()
        except OSError:
            out[key] = "UNKNOWN"
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New attempt-specific output directory")
    parser.add_argument("--freeze", required=True, help="Published preregistration/constructor commit SHA")
    parser.add_argument("--execution-kind", choices=("registered_confirmation", "engineering_reproduction"), default="registered_confirmation")
    parser.add_argument("--workbook", type=Path)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--compact", type=Path, help="Replay a previously prepared, hashed compact dataset")
    args = parser.parse_args(argv)
    if len(args.freeze) != 40 or any(c not in "0123456789abcdef" for c in args.freeze):
        parser.error("A full published 40-character freeze commit is required")
    if args.compact and (args.download or args.workbook):
        parser.error("Choose compact replay or source workbook preparation")
    if not args.compact and args.workbook is None:
        parser.error("A workbook path is required for source preparation")
    if args.output.exists():
        parser.error("Attempt output already exists; preserve it and choose a new path")
    args.output.mkdir(parents=True)
    started_wall, started_cpu = time.perf_counter(), time.process_time()
    receipt = {
        "experiment_id": EXPERIMENT_ID, "started_utc": utc_now(),
        "public_freeze_commit": args.freeze, "argv": sys.argv,
        "execution_kind": args.execution_kind,
        "python": sys.version, "numpy": np.__version__, "platform": platform.platform(),
        "observed_runtime_limits": runtime_limits(),
        "actual_inference_cost_usd": "UNKNOWN", "actual_host_cost_usd": "UNKNOWN",
        "extra_purchased_resources": False, "outside_human_or_laboratory_actions": 0,
        "input_source_commit": SOURCE_COMMIT, "input_source_path": SOURCE_PATH,
        "input_git_blob": SOURCE_BLOB, "input_source_url": SOURCE_URL,
    }
    exit_code = 0
    try:
        # Verify source and contract identity before retrieving/reading outcomes.
        receipt.update(validate_freeze(Path(__file__).resolve().parents[1]))
        if args.compact:
            prepared = json.loads(args.compact.read_text())
            receipt["mode"] = "compact_policy_replay_not_raw_measurement_validation"
            receipt["compact_input_sha256"] = hashlib.sha256(args.compact.read_bytes()).hexdigest()
        else:
            receipt["mode"] = "author_condition_mean_source_replay"
            if args.download:
                if args.workbook.exists():
                    raise InputFailure("Download destination already exists; do not replace pinned input")
                args.workbook.parent.mkdir(parents=True, exist_ok=True)
                temporary = args.workbook.with_suffix(args.workbook.suffix + ".part")
                download_start = time.perf_counter()
                with urllib.request.urlopen(SOURCE_URL, timeout=45) as response, temporary.open("wb") as target:
                    receipt["retrieval_http_status"] = response.status
                    receipt["retrieval_final_url"] = response.url
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        target.write(chunk)
                receipt["retrieval_wall_seconds"] = time.perf_counter() - download_start
                receipt["input_identity"] = source_identity(temporary)
                temporary.replace(args.workbook)
            else:
                receipt["input_identity"] = source_identity(args.workbook)
                receipt["retrieval_in_this_attempt"] = False
            prepared = prepare_records(workbook_records(args.workbook))
        receipt["prepared_evidence_sha256"] = canonical_json_hash(prepared)
        # Do not print labels during construction. Store compact evidence only
        # as an evaluator-owned reference; policies receive PublicContext alone.
        result = run(prepared)
        result["input_evidence_sha256"] = receipt["prepared_evidence_sha256"]
        result["public_freeze_commit"] = args.freeze
        result["execution_kind"] = args.execution_kind
        write_json(args.output / "compact_evidence.json", prepared)
        write_json(args.output / "results.json", result)
        receipt["result_sha256"] = hashlib.sha256((args.output / "results.json").read_bytes()).hexdigest()
        receipt["status"] = "COMPLETED"
        print(json.dumps({
            "status": receipt["status"], "output": str(args.output),
            "denominator": result["input_denominator"],
            "primary": result["policy_results"][PRIMARY_POLICY],
            "ordinary_reuse_exact_tie": result["equal_content_ordinary_reuse_exact_tie"],
            "independent_acceptance": result["independent_acceptance"],
        }, indent=2))
    except Exception as exc:
        exit_code = 1
        receipt["status"] = "FAILED"
        receipt["failure_type"] = type(exc).__name__
        receipt["failure_message"] = str(exc)
        write_json(args.output / "failure.json", {"status": "FAILED", "type": type(exc).__name__, "message": str(exc)})
        print(json.dumps({"status": "FAILED", "type": type(exc).__name__, "message": str(exc)}, indent=2))
    finally:
        receipt["finished_utc"] = utc_now()
        receipt["wall_seconds"] = time.perf_counter() - started_wall
        receipt["cpu_seconds"] = time.process_time() - started_cpu
        receipt["peak_rss_kib_linux"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        write_json(args.output / "resource_receipt.json", receipt)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
