#!/usr/bin/env python3
"""Read-only, source-locked direct manifest delivery for a fixed public mission.

This is a conventional, no-model fallback. It does not issue a customer contract,
replace the authenticated native account, or change the original frozen study.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

REPO = Path(__file__).resolve().parents[2]
PRODUCT = REPO / "products/frontier-omega-ignition"
FIXTURE = PRODUCT / "examples/integrity.json"
FIXTURE_SHA256 = "f3c5981afbc3e61f57cbd7331bc6f1a4398c6b076aa794fc6bbda8e3c0f44425"
SOURCE_BLOBS = {
    "ignition/construction.py": "d8ce91c0800cf444a61dc37f546eb84fcd2ca13b",
    "ignition/evaluation.py": "d9e241fddbd8be485ad708a49023809191658a4d",
    "ignition/delivery.py": "9634bb17dffa6f9771178165249656fd0be52a9c",
    "ignition/portable.py": "1b9fb991a784af343c5dab643dd929444d77647a",
    "examples/integrity.json": "90b778d84e7b586d6a0e59465c7e4459f892f6c0",
}
sys.path.insert(0, str(PRODUCT))
from ignition.construction import build, freeze_contract  # noqa: E402
from ignition.delivery import export_bundle  # noqa: E402
from ignition.evaluation import evaluate  # noqa: E402


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_lock() -> dict[str, str]:
    checked = {}
    for path, expected in SOURCE_BLOBS.items():
        data = (PRODUCT / path).read_bytes()
        actual = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if actual != expected:
            raise ValueError("SOURCE_LOCK_MISMATCH: " + path)
        checked[path] = actual
    if sha256(FIXTURE.read_bytes()) != FIXTURE_SHA256:
        raise ValueError("FIXTURE_CONTENT_MISMATCH")
    return checked


def check_command(command: list[str], cwd: Path, expected_exit: int,
                  *, stdin: bytes | None = None) -> dict:
    p = subprocess.run(command, cwd=cwd, input=stdin, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=40, check=False)
    if p.returncode != expected_exit:
        raise ValueError("PORTABLE_EXIT_MISMATCH")
    try:
        value = json.loads(p.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("PORTABLE_INVALID_JSON") from exc
    return value


def verify_receiver(bundle: bytes, specification: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="ignition-direct-receiver-") as work:
        root = Path(work)
        unpack = root / "receiver"
        unpack.mkdir()
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            if archive.testzip() is not None:
                raise ValueError("CORRUPT_PORTABLE_ARCHIVE")
            if any(n.startswith("/") or ".." in Path(n).parts for n in archive.namelist()):
                raise ValueError("UNSAFE_PORTABLE_MEMBER")
            archive.extractall(unpack)
        executable = [sys.executable, "-I", "run.py"]
        verified = check_command(executable + ["verify"], unpack, 0)
        if verified.get("status") != "pass":
            raise ValueError("PORTABLE_VERIFICATION_FAILED")
        observed = []
        for index, case in enumerate(specification["cases"]):
            if "expected" not in case:
                continue
            envelope = json.dumps(case["input"], separators=(",", ":")).encode()
            output = check_command(executable + ["run"], unpack, 0, stdin=envelope)
            if output != case["expected"]:
                raise ValueError("PORTABLE_CASE_DIFFERENCE")
            folder = root / f"observed-{index}"
            folder.mkdir()
            for relative, encoded in case["input"]["files"].items():
                if relative.startswith("/") or ".." in Path(relative).parts:
                    raise ValueError("UNSAFE_FIXTURE_PATH")
                target = folder / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(base64.b64decode(encoded, validate=True))
            actual = check_command(executable + ["audit-directory", str(folder)], unpack,
                                   0 if case["expected"]["ok"] else 1)
            if actual != case["expected"]:
                raise ValueError("OBSERVED_DIRECTORY_DIFFERENCE")
            observed.append({"case": case["name"], "expected_ok": case["expected"]["ok"],
                             "portable_run": "PASS", "observed_directory": "PASS"})
        for case in specification["cases"]:
            if "error" not in case:
                continue
            p = subprocess.run(executable + ["run"], cwd=unpack,
                               input=json.dumps(case["input"]).encode(), stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=40, check=False)
            if p.returncode == 0 or case["error"].encode() not in p.stderr:
                raise ValueError("PORTABLE_NEGATIVE_WAS_ACCEPTED")
        if len(observed) < 2:
            raise ValueError("INSUFFICIENT_INDEPENDENT_OBSERVATIONS")
        return {"verify": "PASS", "cases": observed,
                "negative_cases": sum("error" in c for c in specification["cases"])}


def compare_conventional(specification: dict) -> dict:
    if not shutil.which("sha256sum") or not shutil.which("jq"):
        raise ValueError("COMPETENT_CONVENTIONAL_TOOLS_MISSING")
    p = subprocess.run([sys.executable, "-B", "compare_conventional.py"],
                       cwd=PRODUCT / "examples", stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=60, check=False)
    if p.returncode:
        raise ValueError("CONVENTIONAL_COMPARATOR_FAILED")
    results = json.loads(p.stdout)
    arm = next((a for a in results["arms"] if a["id"] == "integrity"), None)
    if not results["all_matched"] or arm is None or len(arm["cases"]) != len(specification["cases"]):
        raise ValueError("CONVENTIONAL_CASES_INCOMPLETE")
    if not all(c["matched_frozen_expectation"] for c in arm["cases"]):
        raise ValueError("CONVENTIONAL_ACCEPTANCE_FAILED")
    return {"outcome": "tie_on_frozen_cases", "tool": arm["tool"],
            "passed_cases": len(arm["cases"]), "complete_cost_known": False}


def qualify(destination: Path, *, strong_conventional: bool) -> dict:
    start_wall = time.monotonic()
    start_cpu = time.process_time()
    if destination.exists() or destination.is_symlink():
        raise ValueError("FRESH_OUTPUT_DIRECTORY_REQUIRED")
    source = source_lock()
    fixture = json.loads(FIXTURE.read_bytes())
    if fixture.get("id") != "integrity":
        raise ValueError("WRONG_PUBLIC_MISSION")
    spec = fixture["mission"]["construction_spec"]
    if spec.get("kind") != "manifest_audit" or not spec["definition"].get("manifest"):
        raise ValueError("DIRECT_MANIFEST_ONLY")
    contract = freeze_contract(spec)
    artifact = build(contract, {"kind": "manifest_audit", "program": spec["definition"]})
    evaluation = evaluate(contract, artifact)
    if evaluation["status"] != "pass" or evaluation["comparison"]["outcome"] != "tie":
        raise ValueError("FROZEN_INDEPENDENT_ACCEPTANCE_FAILED")
    context = {"protocol": "ignition/direct-manifest-public/1",
               "fixture_sha256": FIXTURE_SHA256, "source_blobs": source,
               "method": "operator-pinned digest manifest; no inference, no financial authority",
               "model_calls": 0, "buyer_and_complete_cost_evidence": "unmeasured"}
    bundle = export_bundle(contract, artifact, evaluation, context)
    recipient = verify_receiver(bundle, spec)
    conventional = compare_conventional(spec) if strong_conventional else {
        "outcome": "not_executed", "complete_cost_known": False}
    if source_lock() != source:
        raise ValueError("SOURCE_CHANGED_DURING_QUALIFICATION")
    record = {"schema": "ignition/direct-manifest-qualification/v1",
              "status": "ENGINEERING_ACCEPTED", "source_product_revision":
              "89f2196d552810bc56696a7f380ae66c55f8763a",
              "source_blobs": source, "fixture_sha256": FIXTURE_SHA256,
              "contract_sha256": contract["sha256"], "artifact_sha256": artifact["sha256"],
              "package_sha256": sha256(bundle), "case_count": len(spec["cases"]),
              "evaluator_status": evaluation["status"], "evaluator_control_outcome":
              evaluation["comparison"]["outcome"], "receiver": recipient,
              "competent_conventional": conventional,
              "model_calls": 0, "actual_paying_customers": 0,
              "complete_commercial_cost": None, "trailing_365_profit": None,
              "frontier_breakthrough": "NOT_ESTABLISHED",
              "wall_seconds": round(time.monotonic() - start_wall, 6),
              "process_cpu_seconds": round(time.process_time() - start_cpu, 6)}
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "receiver.zip").write_bytes(bundle)
    (destination / "RESULT.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--strong-conventional", action="store_true")
    args = parser.parse_args()
    try:
        result = qualify(args.output.resolve(), strong_conventional=args.strong_conventional)
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        print("DIRECT_MANIFEST_QUALIFICATION_FAILED: " + str(error), file=sys.stderr)
        return 1
    print(json.dumps({"status": result["status"], "cases": result["case_count"],
                      "model_calls": result["model_calls"],
                      "conventional": result["competent_conventional"]["outcome"],
                      "package_sha256": result["package_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
