"""Independently audit complete source-bound outputs, without an optimizer.

The delegated reviewer wrote independent/verify_certificate.py and its source
parser without importing the producer's solver or domain adapters. This wrapper
binds the frozen asset and reports their verdicts together. Standard library only.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "independent"))
from verify_certificate import source_bound_first, source_bound_successor


def check_provenance(successor):
    freeze = json.loads((HERE / "evidence/FIRST_ASSET_FREEZE.json").read_text())
    expected_files = {"cover.py", "portfolio.py", "PROTOCOL.json", "evidence/first_portfolio.json"}
    if freeze.get("schema") != "frontier-first-asset-freeze/v1" or set(freeze.get("files", {})) != expected_files:
        raise ValueError("FIRST_FREEZE_SCHEMA_MISMATCH")
    for name, metadata in freeze["files"].items():
        source = (HERE / name).read_bytes()
        if len(source) != metadata["bytes"] or hashlib.sha256(source).hexdigest() != metadata["sha256"]:
            raise ValueError(f"FROZEN_FIRST_SOURCE_CHANGED:{name}")
    actual = freeze["files"]["cover.py"]["sha256"]
    adapter_source = (HERE / "successor.py").read_bytes()
    adapter_hash = hashlib.sha256(adapter_source).hexdigest()
    protocol_hash = hashlib.sha256((HERE / "independent/PROTOCOL.json").read_bytes()).hexdigest()
    successor_freeze = json.loads((HERE / "evidence/successor_source_freeze.json").read_text())
    if (successor_freeze.get("schema") != "frontier-successor-source-freeze/v1" or
            successor_freeze.get("source_sha256") != adapter_hash or
            successor_freeze.get("source_bytes") != len(adapter_source) or
            successor_freeze.get("first_asset_sha256") != actual or successor_freeze.get("preexecution") is not True):
        raise ValueError("FROZEN_SUCCESSOR_ADAPTER_CHANGED")
    protocol_freeze = json.loads((HERE / "independent/PROTOCOL_FREEZE.json").read_text())
    if protocol_freeze.get("protocol_sha256") != protocol_hash:
        raise ValueError("FROZEN_INDEPENDENT_PROTOCOL_CHANGED")
    if successor.get("retained_cover_sha256") != actual:
        raise ValueError("SUCCESSOR_RETAINED_SOURCE_MISMATCH")
    if successor.get("adapter_sha256") != adapter_hash:
        raise ValueError("SUCCESSOR_ADAPTER_SOURCE_MISMATCH")
    if successor.get("protocol_sha256") != protocol_hash:
        raise ValueError("SUCCESSOR_PROTOCOL_MISMATCH")
    for case in successor.get("results", []):
        if case.get("retained_asset_sha256") != actual:
            raise ValueError("SUCCESSOR_CASE_RETAINED_SOURCE_MISMATCH")
        if case.get("adapter_sha256") != adapter_hash:
            raise ValueError("SUCCESSOR_CASE_ADAPTER_SOURCE_MISMATCH")
    return actual


def run(data_dir, first_path, successor_path):
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    actual = check_provenance(json.loads(Path(successor_path).read_text()))
    first = source_bound_first(first_path, Path(data_dir) / "amidation.csv")
    second = source_bound_successor(successor_path, Path(data_dir))
    if not first["accepted"] or not second["accepted"]:
        raise ValueError("INDEPENDENT_ACCEPTANCE_FAILED")
    return {"schema": "frontier-complete-source-audit/v1", "accepted": True,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(), "retained_asset_sha256": actual,
        "first": first, "successor": second,
        "resources": {"wall_seconds": time.perf_counter() - start_wall,
                      "cpu_seconds": time.process_time() - start_cpu},
        "accepted_case_count": len(first["cases"]) + len(second["cases"]),
        "meaning": "All stated finite-data recommendations and their exact minimality certificates accepted. This is not prospective physical or commercial acceptance.",
        "scope": "Source bytes, finite problem semantics, displayed assignments/witnesses and independently checked cardinality; no production solver import."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--successor", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Use a new audit output path")
    result = run(args.data_dir, args.first, args.successor)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"accepted": result["accepted"], "accepted_case_count": result["accepted_case_count"],
                      "output": str(args.output), "resources": result["resources"]}, indent=2))

