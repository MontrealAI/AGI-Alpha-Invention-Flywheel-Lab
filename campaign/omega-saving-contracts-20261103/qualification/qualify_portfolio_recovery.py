"""Source-isolated portfolio recovery qualification; no business account recovery.

Run unchanged historical tests on their immutable original source. Optionally run
current fresh-fixture tests with the explicit test-only source expectation and
an original-pin refusal regression. No production source pin is modified.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
HISTORICAL = "38846ad9b72ef04c10b2b97b3dbff52d1efc3790"
EXPECTED_SOURCE = "bb74d40f7a84ca155189f908c091db32b27093e203e0d63696f327a9a2492901"
PREFIX = "experiments/public_portfolio_20261102/"
FREEZE = PREFIX + "EVALUATION_SOURCE_FREEZE_R2.json"
TEST = PREFIX + "verification/test_recovery.py"
MODULES = (
    "experiments.public_portfolio_20261102.verification.test_recovery",
    "experiments.public_portfolio_20261102.verification.test_recovery_fast",
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT,
                                   env={**os.environ, "GIT_NO_REPLACE_OBJECTS": "1"})


def materialize(ref, target):
    if not re.fullmatch(r"[0-9a-f]{40}", ref) or git("rev-parse", ref + "^{commit}").decode().strip() != ref:
        raise ValueError("EXACT_COMMIT_REQUIRED")
    freeze = json.loads(git("show", ref + ":" + FREEZE))
    paths = set(freeze["source_files_except_this_receipt"]) | {FREEZE}
    # Include separately bound execution/test adapters. Never include campaign
    # private accounts, retained public ledgers or any working-tree credentials.
    tree = git("ls-tree", "-r", "--name-only", ref, PREFIX).decode().splitlines()
    for path in tree:
        relative = path[len(PREFIX):]
        if "/" not in relative and path.endswith((".py", ".json", "AGENTS.md")):
            paths.add(path)
        if relative.startswith("verification/") and path.endswith(".py"):
            paths.add(path)
        if relative.startswith("verification/") and any(
                tag in Path(path).name for tag in ("RECOVERY", "recovery")) and path.endswith(".json"):
            paths.add(path)
    expected = set(paths)
    extracted = {}
    process = subprocess.Popen(["git", "archive", ref, "--", *sorted(paths)],
        cwd=ROOT, env={**os.environ, "GIT_NO_REPLACE_OBJECTS": "1"}, stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
            for member in archive:
                if member.isdir():
                    continue
                if not member.isfile() or member.name not in expected:
                    raise ValueError("ONLY_DECLARED_REGULAR_PUBLIC_SOURCE_FILES")
                path = Path(member.name)
                if path.is_absolute() or ".." in path.parts:
                    raise ValueError("RELATIVE_SOURCE_REQUIRED")
                raw = archive.extractfile(member).read()
                dest = target / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(raw)
                extracted[member.name] = sha(raw)
        if process.wait() != 0 or set(extracted) != expected:
            raise ValueError("COMPLETE_IMMUTABLE_SOURCE_MATERIALIZATION_REQUIRED")
    except BaseException:
        process.terminate()
        process.wait()
        raise
    finally:
        process.stdout.close()
    return {"commit": ref, "materialized_file_count": len(extracted),
            "materialized_files_sha256": sha(canonical(extracted)),
            "unchanged_recovery_test_sha256": extracted[TEST]}


CHILD = r"""
import hashlib, io, json, sys, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from connected_enterprise.finance import source_identity
from experiments.public_portfolio_20261102 import recovery_run
schema = {'schema': 'public-portfolio-20261102/native-services/v2'}
before = source_identity(Path.cwd(), schema)
production_pin = recovery_run.EXPECTED_NATIVE_SOURCE
assert production_pin == 'bb74d40f7a84ca155189f908c091db32b27093e203e0d63696f327a9a2492901'
historical = sys.argv[1] == 'historical'
if historical:
    assert before['sha256'] == production_pin
modules = (
    'experiments.public_portfolio_20261102.verification.test_recovery',
    'experiments.public_portfolio_20261102.verification.test_recovery_fast',
)
rows = []
for module in modules:
    suite = unittest.TestLoader().loadTestsFromName(module)
    declared = suite.countTestCases()
    start = time.perf_counter()
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=0, buffer=True).run(suite)
    rows.append({'module': module, 'declared': declared, 'executed': result.testsRun,
        'wall_seconds': time.perf_counter() - start, 'passed': result.wasSuccessful(),
        'errors': [{'test': t.id(), 'traceback_tail': detail[-5000:]} for t, detail in result.errors],
        'failures': [{'test': t.id(), 'traceback_tail': detail[-5000:]} for t, detail in result.failures],
        'skipped': [{'test': t.id(), 'reason': reason} for t, reason in result.skipped]})
    assert recovery_run.EXPECTED_NATIVE_SOURCE == production_pin
after = source_identity(Path.cwd(), schema)
output = {'scope': ('UNCHANGED_HISTORICAL_NONBUSINESS_RECOVERY_TESTS' if historical else
                   'FRESH_CURRENT_SOURCE_FIXTURE_ALGORITHMS_AND_ORIGINAL_PIN_REFUSAL'),
    'source_before_sha256': before['sha256'], 'source_after_sha256': after['sha256'],
    'source_unchanged': before == after, 'production_pin': production_pin,
    'production_pin_restored_after_tests': recovery_run.EXPECTED_NATIVE_SOURCE == production_pin,
    'module_results': rows, 'passed': before == after and all(r['passed'] for r in rows)}
print(json.dumps(output, sort_keys=True))
sys.exit(0 if output['passed'] else 1)
"""


def run_case(ref, historical):
    with tempfile.TemporaryDirectory(prefix="portfolio-immutable-source-") as temporary:
        target = Path(temporary)
        started = time.perf_counter()
        materialization = materialize(ref, target)
        materialization["wall_seconds"] = time.perf_counter() - started
        overlay = None
        if not historical:
            raw = (ROOT / TEST).read_bytes()
            (target / TEST).write_bytes(raw)
            overlay = {"path": TEST, "sha256": sha(raw),
                "scope": "Only the fresh-fixture test module; production files remain exactly the named commit."}
        result = subprocess.run([sys.executable, "-I", "-c", CHILD,
            "historical" if historical else "current"], cwd=target,
            capture_output=True, text=True)
        try:
            outcome = json.loads(result.stdout)
        except json.JSONDecodeError:
            outcome = {"passed": False, "setup_error": True,
                "stderr_tail": result.stderr[-6000:], "stdout_tail": result.stdout[-2000:]}
        return {"materialization": materialization, "test_overlay": overlay,
                "process_returncode": result.returncode, **outcome}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--current-ref", help="Exact current commit to test with the explicitly patched fresh-fixture module.")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    if output.exists():
        raise FileExistsError("PRESERVE_PREVIOUS_QUALIFICATION_RECEIPT")
    record = {"schema": "omega-savings/source-isolated-portfolio-qualification/v1",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "runner_sha256": sha(Path(__file__).read_bytes()), "historical_commit": HISTORICAL,
        "production_expected_native_source": EXPECTED_SOURCE,
        "registered_test_modules": list(MODULES), "complete": False, "cases": []}
    def save():
        output.parent.mkdir(parents=True, exist_ok=True)
        pending = output.with_suffix(output.suffix + ".pending")
        pending.write_bytes(canonical(record) + b"\n")
        os.replace(pending, output)
    save()
    for ref, historical in ([(HISTORICAL, True)] +
                            ([(args.current_ref, False)] if args.current_ref else [])):
        record["current_case"] = {"ref": ref, "historical": historical}
        save()
        try:
            result = run_case(ref, historical)
        except BaseException as exc:
            record["setup_failure"] = {"type": type(exc).__name__, "message": str(exc)}
            save()
            raise
        record["cases"].append(result)
        save()
        print(json.dumps({"commit": ref, "historical": historical,
            "passed": result["passed"], "process_returncode": result["process_returncode"],
            "tests": sum(r["executed"] for r in result.get("module_results", []))}), flush=True)
    record["current_case"] = None
    record["complete"] = True
    record["passed"] = all(row["passed"] for row in record["cases"])
    record["finished_utc"] = datetime.now(timezone.utc).isoformat()
    record["interpretation"] = ("Engineering recovery tests on new nonbusiness fixtures. "
        "No original private authority acquired, copied, restored, or exercised. "
        "No historical source pins, accounts or economic results changed.")
    save()
    raise SystemExit(0 if record["passed"] else 1)


if __name__ == "__main__":
    main()
