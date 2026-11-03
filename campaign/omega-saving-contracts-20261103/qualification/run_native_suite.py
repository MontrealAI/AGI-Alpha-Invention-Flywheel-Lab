"""Compact, resumable qualification of existing native-account test modules.

Run once against an identified source closure. This runner changes no finance,
test expectation, or account. Each module completes before its receipt is saved.
An interruption preserves completed modules; resume requires identical source.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import unittest


ROOT = Path(__file__).resolve().parents[3]
PREFIXES = ("test_connected", "test_commercial", "test_adaptive")
EXTRA_MODULES = ("tests.test_omega_savings_native",)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".pending")
    with temporary.open("wb") as stream:
        stream.write(canonical(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def sources():
    result = subprocess.run(["rg", "--files", "-g", "*.py", "-g", "*.c",
                             "-g", "requirements*.txt"], cwd=ROOT,
                            capture_output=True, text=True, check=True)
    files = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
             for name in sorted(result.stdout.splitlines())}
    return {"files": files, "sha256": digest(files)}


class CompactResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subprocess_errors = []

    def addError(self, test, err):
        super().addError(test, err)
        value = getattr(err[1], "stderr", None)
        if value:
            if isinstance(value, bytes):
                value = value.decode(errors="replace")
            self.subprocess_errors.append({"test": test.id(), "stderr_tail": str(value)[-4000:]})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    modules = sorted({"tests." + path.stem for path in (ROOT / "tests").glob("test_*.py")
                      if path.name.startswith(PREFIXES)} | set(EXTRA_MODULES))
    source = sources()
    if args.resume:
        record = json.loads(output.read_text())
        if record["source_before"] != source or record["registered_modules"] != modules:
            raise ValueError("QUALIFICATION_RESUME_REQUIRES_IDENTICAL_SOURCE_AND_MODULES")
    else:
        if output.exists():
            raise FileExistsError("PRESERVE_EARLIER_QUALIFICATION_RECEIPT")
        record = {"schema": "omega-savings/composed-native-qualification/v1",
            "scope": "LOCAL_EXISTING_NATIVE_ADAPTIVE_CONNECTED_REGRESSIONS",
            "started_utc": now(), "source_before": source,
            "registered_modules": modules,
            "static_test_definitions": sum(len(re.findall(r"^    def test_", (ROOT / "tests" / (name.split(".")[-1] + ".py")).read_text(), re.M)) for name in modules),
            "module_results": [], "complete": False, "current_module": None}
        save(output, record)
    completed = {row["module"] for row in record["module_results"]}
    for module in modules:
        if module in completed:
            continue
        record["current_module"] = module
        save(output, record)
        started = time.perf_counter()
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(module)
        declared = suite.countTestCases()
        stream = io.StringIO()
        result = unittest.TextTestRunner(stream=stream, verbosity=0,
            resultclass=CompactResult, buffer=True).run(suite)
        row = {"module": module, "declared_tests": declared, "executed_tests": result.testsRun,
            "passed": result.wasSuccessful(), "wall_seconds": time.perf_counter() - started,
            "failures": [{"test": t.id(), "traceback_tail": detail[-6000:]} for t, detail in result.failures],
            "errors": [{"test": t.id(), "traceback_tail": detail[-6000:]} for t, detail in result.errors],
            "skipped": [{"test": t.id(), "reason": reason} for t, reason in result.skipped],
            "expected_failures": [t.id() for t, _ in result.expectedFailures],
            "unexpected_successes": [t.id() for t in result.unexpectedSuccesses],
            "subprocess_errors": result.subprocess_errors}
        record["module_results"].append(row)
        record["current_module"] = None
        save(output, record)
        print(json.dumps({k: row[k] for k in ("module", "executed_tests", "passed", "wall_seconds")}), flush=True)
    record["source_after"] = sources()
    record["source_unchanged"] = record["source_after"] == record["source_before"]
    record["complete"] = True
    record["finished_utc"] = now()
    record["passed"] = record["source_unchanged"] and all(row["passed"] for row in record["module_results"])
    record["executed_tests"] = sum(row["executed_tests"] for row in record["module_results"])
    record["error_count"] = sum(len(row["errors"]) for row in record["module_results"])
    record["failure_count"] = sum(len(row["failures"]) for row in record["module_results"])
    save(output, record)
    print(json.dumps({k: record[k] for k in ("complete", "passed", "executed_tests", "error_count", "failure_count", "source_unchanged")}), flush=True)
    raise SystemExit(0 if record["passed"] else 1)


if __name__ == "__main__":
    main()
