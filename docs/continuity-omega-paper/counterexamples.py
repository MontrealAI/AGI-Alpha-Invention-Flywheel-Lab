#!/usr/bin/env python3
"""Reproduce five bounded observations against the historical PR278 checker.

    python3 counterexamples.py --source278 /absolute/pinned/source278 \
        --output /tmp/continuity-counterexamples-NEW

Exit 0 means the expected weaknesses were reproduced, NOT that the checker
was qualified. The positive control, false Boolean-currency pass, malformed
input exception, stale inspection, and previously disclosed coherent-reseal
limit remain separate from the historical 29-test suite.

Both recorded Git blob identities and SHA-256 values are checked before any
prototype code executes. Only verified copies are used. Original source bytes
are preserved; all altered fixtures and logs go to a new output directory.
No PR279 implementation is integrated or qualified by this command.
"""
from __future__ import annotations

import argparse
import copy
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
import reproduce


ROOT = Path(__file__).resolve().parent
BASELINE = "a755d0375693465f8f31c0c919cc186eae74bbcc"
REPORTING_HEAD = "6cd7e1bb7197cabdf8f3d093eead662cde5351f4"
SUCCESS = "COUNTEREXAMPLES_REPRODUCED_NOT_CHECKER_QUALIFICATION"
EXPECTED = {
    "positive_control": {"verdict": "PASS_SYNTHETIC_ONLY", "orders": 2, "units": 1900},
    "boolean_currency": {
        "offer_json_type": "boolean", "constructor_rejected": True,
        "constructor_exception": "DrillRejected", "audit_verdict": "PASS_SYNTHETIC_ONLY",
        "audit_failure_count": 0, "cli_verify_exit": 0, "cli_verify_verdict": "PASS_SYNTHETIC_ONLY",
    },
    "malformed_top_level": {"input": "JSON null", "exception": "AttributeError", "structured_result_returned": False},
    "stale_inspection": {
        "changed_required_units": 1, "inspect_exit": 0,
        "inspect_returned_stored_passport": True, "inspect_has_fresh_audit": False,
        "inspect_technical_verdict": "READY_FOR_INDEPENDENT_SYNTHETIC_AUDIT",
        "fresh_verify_exit": 3, "fresh_verify_verdict": "FAIL",
        "fresh_verify_failures": ["PASSPORT_HANDOFF_BINDING", "REQUIRED_UNITS"],
        "stored_audit_verdict": "PASS_SYNTHETIC_ONLY",
    },
    "coherent_reseal": {
        "original_units": 1900, "rewritten_units": 2000,
        "event_digest_changed": True, "audit_verdict": "PASS_SYNTHETIC_ONLY",
        "interpretation": "Previously disclosed trust limitation; internal consistency does not bind an externally held original scenario.",
    },
}


def cli(source: Path, directory: Path, command: str) -> tuple[int, dict]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-m", "continuity_omega", command, "--in-dir", str(directory)],
        cwd=source, env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=30,
    )
    (directory / f"{command}.stdout.txt").write_text(result.stdout, encoding="utf-8")
    (directory / f"{command}.stderr.txt").write_text(result.stderr, encoding="utf-8")
    data = json.loads(result.stdout)
    reproduce.require(isinstance(data, dict), f"{command} did not return a JSON object")
    return result.returncode, data


def bundle(output: Path, name: str, case: object, handoff: dict, passport: dict, audit: dict | None = None) -> Path:
    directory = output / "cases" / name
    directory.mkdir(parents=True)
    for filename, value in (("INPUT.json", case), ("HANDOFF.json", handoff), ("PASSPORT.json", passport)):
        reproduce.write_json(directory / filename, value)
    if audit is not None:
        reproduce.write_json(directory / "AUDIT.json", audit)
    return directory


def probe(source: Path, output: Path) -> dict:
    reproduce.require(not any(name == "continuity_omega" or name.startswith("continuity_omega.")
                              for name in sys.modules), "Prototype modules were already imported before source verification")
    sys.path.insert(0, str(source))
    try:
        demo = importlib.import_module("continuity_omega.demo")
        engine = importlib.import_module("continuity_omega.engine")
        checker = importlib.import_module("continuity_omega.checker")
        case = demo.case_for()
        handoff, passport = engine.construct(case)
        positive = checker.audit(case, handoff, passport)
        bundle(output, "positive_control", case, handoff, passport, positive)
        observations = {"positive_control": {
            "verdict": positive["verdict"], "orders": positive["replayed_orders"],
            "units": positive["replayed_units"],
        }}

        # Construct a valid zero-cost, one-unit-price package, then replace the
        # offer with JSON true in both case and passport. The constructor's
        # exact-integer rule rejects this, but the historical checker accepts it.
        boolean = copy.deepcopy(case)
        boolean["economics"]["costs"] = {key: 0 for key in boolean["economics"]["costs"]}
        boolean["suppliers"][0]["quoted_cost"] = 0
        boolean["economics"]["offer"] = 1
        bh, bp = engine.construct(boolean)
        boolean["economics"]["offer"] = True
        bp["economics"]["offer"] = True
        rejected, exception = False, None
        try:
            engine.construct(boolean)
        except ValueError as error:
            rejected, exception = True, type(error).__name__
        ba = checker.audit(boolean, bh, bp)
        directory = bundle(output, "boolean_currency", boolean, bh, bp, ba)
        code, verified = cli(source, directory, "verify")
        observations["boolean_currency"] = {
            "offer_json_type": "boolean" if type(boolean["economics"]["offer"]) is bool else "other",
            "constructor_rejected": rejected, "constructor_exception": exception,
            "audit_verdict": ba["verdict"], "audit_failure_count": ba["failure_count"],
            "cli_verify_exit": code, "cli_verify_verdict": verified.get("verdict"),
        }

        directory = bundle(output, "malformed_top_level", None, handoff, passport)
        malformed = {"input": "JSON null", "exception": None, "structured_result_returned": False}
        try:
            value = checker.audit(None, handoff, passport)
            malformed["structured_result_returned"] = isinstance(value, dict)
            reproduce.write_json(directory / "RETURNED.json", value)
        except Exception as error:
            malformed["exception"] = type(error).__name__
            reproduce.write_json(directory / "EXCEPTION.json", {"type": type(error).__name__, "message": str(error)})
        observations["malformed_top_level"] = malformed

        # Preserve the original handoff and stored audit; mutate only this new
        # fixture's handoff. Inspect and verify then observe the same files.
        directory = bundle(output, "stale_inspection", case, handoff, passport, positive)
        reproduce.write_json(directory / "HANDOFF.before.json", handoff)
        changed = copy.deepcopy(handoff)
        changed["required_units"] = 1
        reproduce.write_json(directory / "HANDOFF.json", changed)
        inspect_code, inspected = cli(source, directory, "inspect")
        verify_code, verified = cli(source, directory, "verify")
        observations["stale_inspection"] = {
            "changed_required_units": changed["required_units"], "inspect_exit": inspect_code,
            "inspect_returned_stored_passport": inspected == passport,
            "inspect_has_fresh_audit": "fresh_audit" in inspected,
            "inspect_technical_verdict": inspected.get("technical_verdict"),
            "fresh_verify_exit": verify_code, "fresh_verify_verdict": verified.get("verdict"),
            "fresh_verify_failures": verified.get("failures"),
            "stored_audit_verdict": json.loads((directory / "AUDIT.json").read_text())["verdict"],
        }

        replacement = copy.deepcopy(case)
        replacement["source_events"][3]["quantity"] = 1200
        replacement["source_seal"] = engine.digest(replacement["source_events"])
        rh, rp = engine.construct(replacement)
        ra = checker.audit(replacement, rh, rp)
        bundle(output, "coherent_reseal", replacement, rh, rp, ra)
        observations["coherent_reseal"] = {
            "original_units": handoff["required_units"], "rewritten_units": rh["required_units"],
            "event_digest_changed": replacement["source_seal"] != case["source_seal"],
            "audit_verdict": ra["verdict"],
            "interpretation": EXPECTED["coherent_reseal"]["interpretation"],
        }
        return observations
    finally:
        sys.path.remove(str(source))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source278", type=Path, required=True, help="Local historical PR278 snapshot; both source hashes must match")
    parser.add_argument("--output", type=Path, required=True, help="New absolute output directory; never overwrite prior evidence")
    args = parser.parse_args()
    if not args.output.is_absolute():
        parser.error("--output must be an absolute path")
    if args.output.exists() or args.output.is_symlink():
        parser.error("--output exists; choose a new directory")
    source = args.source278.resolve()
    output = args.output.resolve()
    if not source.is_dir():
        parser.error("--source278 must be an existing directory")
    if output == source or output.is_relative_to(source):
        parser.error("--output must not modify the supplied source directory")
    output.mkdir(parents=True)
    record = {
        "schema": "continuity-omega-paper/counterexamples/v1", "source_commit": BASELINE,
        "reporting_pr": 279, "reporting_head_observed": REPORTING_HEAD,
        "reporting_source": "https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab/blob/" + REPORTING_HEAD + "/docs/continuity-omega/HARDENING.md",
        "scope": "Five authored observations against the historical checker, including one positive control. Counterexample reproduction is NOT checker qualification; no live operations, payments, or PR279 repair qualification.",
        "historical_suite": {"recorded_test_passes": 29, "rerun_by_this_command": False},
        "observations": {}, "source_identity_verified": False,
        "source_bytes_unchanged": False, "expected_observations_matched": False,
    }
    try:
        manifest = json.loads((ROOT / "evidence" / "REPRODUCTION.json").read_text(encoding="utf-8"))
        spec = reproduce.source_specs(manifest)["pr278"]
        reproduce.require(spec["commit"] == BASELINE, "This probe set is fixed to the historical a755d037 revision")
        copied, identities = reproduce.materialize("pr278", spec, source, output)
        record["source_identity_verified"] = all(row["verified"] for row in identities)
        record["observations"] = probe(copied, output)
        record["source_bytes_unchanged"] = (reproduce.check_source_bytes(source, spec)
                                               and reproduce.check_source_bytes(copied, spec))
        # JSON comparison distinguishes Boolean true from integer 1.
        canonical = lambda value: json.dumps(value, sort_keys=True, allow_nan=False)
        record["expected_observations_matched"] = canonical(record["observations"]) == canonical(EXPECTED)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        record["error"] = str(error)
    passed = (record["source_identity_verified"] and record["source_bytes_unchanged"]
              and record["expected_observations_matched"] and "error" not in record)
    record["status"] = SUCCESS if passed else "COUNTEREXAMPLE_REPRODUCTION_DID_NOT_MATCH"
    record["probe_count"] = len(record["observations"])
    path = output / "RESULT.json"
    reproduce.write_json(path, record)
    print(json.dumps({"status": record["status"], "report": str(path),
                      "probe_count": record["probe_count"], "source_bytes_unchanged": record["source_bytes_unchanged"]}, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
