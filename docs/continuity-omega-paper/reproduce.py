#!/usr/bin/env python3
"""Reproduce CONTINUITY OMEGA's pinned synthetic evidence with Python 3.10+.

Example (downloads only the public files listed in the evidence manifest):
    python3 reproduce.py --output /tmp/continuity-reproduction-NEW

Offline example (source directories are read, verified, and never modified):
    python3 reproduce.py --output /tmp/continuity-reproduction-NEW \
        --source277 /absolute/path/to/pr277 --source278 /absolute/path/to/pr278

Every executable source file must match BOTH its recorded Git blob identity
and SHA-256 before execution. Only verified files are copied into the new
output directory. All logs, source copies, and exercise artifacts stay there,
including failures. An existing output directory is never reused or removed.

These are authored software fixtures. No model API, live recovery, customer,
supplier, capacity reservation, financial account, or payment is involved.
The network mode retrieves public source files; the fixtures run offline.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request


MANIFEST = Path(__file__).resolve().parent / "evidence" / "REPRODUCTION.json"
RAW_BASE = "https://raw.githubusercontent.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab"
EXPECTED_TESTS = {"pr277": 9, "pr278": 29}
TEST_FILES = {
    "pr277": "test_connected_continuity_omega.py",
    "pr278": "test_continuity_omega.py",
}
CASES = (
    "nominal", "tampered_source", "overbooked", "correlated_outage",
    "unqualified", "late", "buyer_declines", "uneconomic",
    "unapproved_sharing", "no_order_source", "missing_from_restored",
    "extra_restored",
)
PASS_CASES = {"nominal", "missing_from_restored", "extra_restored"}
SCOPE = (
    "Pinned synthetic engineering reproduction only. Separate code paths under "
    "shared authorship; no measured LLM advantage, live cyber recovery, physical "
    "delivery, third-party certification, customer acceptance, or commerce."
)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8")


def identities(data: bytes) -> dict[str, str]:
    header = f"blob {len(data)}\0".encode("ascii")
    return {
        "git_blob": hashlib.sha1(header + data, usedforsecurity=False).hexdigest(),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def source_specs(manifest: dict) -> dict[str, dict]:
    """Reject incomplete or ambiguous source-to-hash mappings before executing."""
    require(manifest.get("schema") == "continuity-omega-paper/reproduction/v1",
            "Unsupported evidence manifest schema")
    result = {}
    for label, expected_count in EXPECTED_TESTS.items():
        tests = manifest["tests"][label]
        commit = tests["commit"]
        require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}", commit) is not None,
                f"Invalid pinned commit for {label}")
        require(type(tests["passed"]) is int and tests["passed"] == expected_count
                and tests["failed"] == 0, f"Unexpected declared test counts for {label}")
        hashes = manifest["source_sha256"][label]
        files = [dict(row) for row in manifest["source_files"] if row["commit"] == commit]
        paths = [row["path"] for row in files]
        require(files and len(paths) == len(set(paths)) and set(paths) == set(hashes),
                f"Missing, duplicate, or unmatched source identities for {label}")
        for row in files:
            path = PurePosixPath(row["path"])
            require(not path.is_absolute() and ".." not in path.parts
                    and str(path) == row["path"] and "\\" not in row["path"],
                    f"Unsafe source path: {row['path']}")
            require(re.fullmatch(r"[0-9a-f]{40}", row["git_blob"]) is not None,
                    f"Invalid Git blob identity: {row['path']}")
            row["sha256"] = hashes[row["path"]]
            require(re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is not None,
                    f"Invalid SHA-256 identity: {row['path']}")
        result[label] = {"commit": commit, "files": files}
    require(len({spec["commit"] for spec in result.values()}) == 2,
            "The two source revisions must remain distinct")
    require(len(manifest["source_files"]) == sum(len(s["files"]) for s in result.values()),
            "Source manifest contains an unassigned revision")
    return result


def materialize(label: str, spec: dict, local: Path | None, output: Path) -> tuple[Path, list[dict]]:
    destination = output / ("source" + label.removeprefix("pr"))
    destination.mkdir()
    records = []
    for row in spec["files"]:
        name = row["path"]
        if local is not None:
            original = local / name
            resolved = original.resolve(strict=True)
            require(resolved.is_relative_to(local), f"Source path escapes its snapshot: {name}")
            data = resolved.read_bytes()
            origin = str(original)
        else:
            origin = f"{RAW_BASE}/{spec['commit']}/{urllib.parse.quote(name, safe='/')}"
            request = urllib.request.Request(origin, headers={
                "User-Agent": "CONTINUITY-OMEGA-paper-reproduction/1.0",
                "Accept": "application/octet-stream",
            })
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read(4 * 1024 * 1024 + 1)
            require(len(data) <= 4 * 1024 * 1024, f"Unexpected source size: {name}")
        observed = identities(data)
        record = {"path": name, "origin": origin, **observed,
                  "verified": all(observed[key] == row[key] for key in observed)}
        if not record["verified"]:
            rejected = output / "rejected_sources" / label / (name + ".unverified")
            rejected.parent.mkdir(parents=True, exist_ok=True)
            rejected.write_bytes(data)
            record["unverified_bytes"] = str(rejected.relative_to(output))
        records.append(record)
        write_json(output / f"{label}_source_identity.json", records)
        require(record["verified"], f"Source identity mismatch for {label}/{name}: {observed}")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return destination, records


def check_source_bytes(directory: Path, spec: dict) -> bool:
    try:
        return all(identities((directory / row["path"]).read_bytes()) ==
                   {key: row[key] for key in ("git_blob", "sha256")}
                   for row in spec["files"])
    except OSError:
        return False


def run(command: list[str], cwd: Path, output: Path, name: str) -> tuple[dict, str]:
    """Keep complete logs even on a failed command or timeout."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    env.pop("PYTHONPATH", None)
    start = time.monotonic()
    entry = {"name": name, "command": command, "cwd": str(cwd), "passed": False}
    try:
        completed = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", timeout=60)
        stdout, stderr = completed.stdout, completed.stderr
        entry["returncode"] = completed.returncode
    except subprocess.TimeoutExpired as exc:
        def decoded(value: str | bytes | None) -> str:
            return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
        stdout, stderr = decoded(exc.stdout), decoded(exc.stderr)
        entry.update(returncode=None, timed_out=True)
    except OSError as exc:
        stdout, stderr = "", str(exc)
        entry.update(returncode=None, execution_error=str(exc))
    entry["elapsed_seconds"] = round(time.monotonic() - start, 4)
    for suffix, content in (("stdout", stdout), ("stderr", stderr)):
        path = output / "logs" / f"{name}.{suffix}.txt"
        path.write_text(content, encoding="utf-8")
        entry[suffix + "_log"] = str(path.relative_to(output))
    entry["_stderr"] = stderr
    return entry, stdout


def decoded_result(entry: dict, stdout: str) -> dict:
    try:
        value = json.loads(stdout)
        require(isinstance(value, dict), "Command did not produce a JSON object")
        return value
    except (ValueError, TypeError) as exc:
        entry.setdefault("failures", []).append("Invalid JSON result: " + str(exc))
        return {}


def suite(label: str, source: Path, output: Path) -> dict:
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests",
               "-p", TEST_FILES[label], "-v"]
    entry, stdout = run(command, source, output, label + "_tests")
    text = stdout + entry.pop("_stderr")
    counts = re.findall(r"(?m)^Ran (\d+) tests? in [^\n]+$", text)
    entry["test_count"] = int(counts[0]) if len(counts) == 1 else None
    entry["expected_test_count"] = EXPECTED_TESTS[label]
    entry["passed"] = (entry["returncode"] == 0
                       and entry["test_count"] == EXPECTED_TESTS[label]
                       and re.search(r"(?m)^OK\s*$", text) is not None)
    if not entry["passed"]:
        entry["failures"] = ["Expected exact test count and an unqualified successful unittest result"]
    return entry


def benchmark(source: Path, output: Path) -> dict:
    command = [sys.executable, "campaign/continuity_omega_20261106/continuity_proof.py"]
    entry, stdout = run(command, source, output, "pr277_benchmark")
    entry.pop("_stderr")
    result = decoded_result(entry, stdout)
    write_json(output / "pr277_benchmark.json", result)
    rows = result.get("cases", [])
    expected = [True, False, False, False]
    vectors = {key: [row.get(key) for row in rows] for key in (
        "registered_expected", "proof_accepted", "conventional_accepted",
        "health_only_accepted", "independent_verification")}
    checks = [
        entry["returncode"] == 0,
        result.get("case_count") == 4,
        [row.get("case") for row in rows] == ["healthy", "lost_pending_liability", "stale_recovery", "tampered_tape"],
        all(vectors[key] == expected for key in ("registered_expected", "proof_accepted", "conventional_accepted")),
        vectors["health_only_accepted"] == [True] * 4,
        vectors["independent_verification"] == [True] * 4,
        result.get("all_registered_verdicts_match") is True,
        result.get("competent_conventional_tie") is True,
        result.get("portable_proof_advantage_over_strong_control_established") is False,
        result.get("customer_acceptance_or_actual_commerce") is False,
        result.get("commercial_status") == "HOLD_NO_OBSERVED_WILLINGNESS_TO_PAY_OR_COMPLETE_COSTS",
        str(result.get("recommended_action", "")).startswith("NO_DEPLOY;"),
    ]
    entry.update(passed=all(checks) and not entry.get("failures"), case_count=len(rows),
                 candidate_verdicts=vectors["proof_accepted"],
                 competent_comparator_verdicts=vectors["conventional_accepted"])
    if not entry["passed"]:
        entry.setdefault("failures", []).append("Benchmark differs from the recorded four-case tie and scope")
    return entry


def read_object(path: Path) -> dict:
    result = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(result, dict), f"Expected JSON object: {path.name}")
    return result


def handoff_case(case: str, source: Path, output: Path) -> tuple[dict, Path]:
    destination = output / "cases" / case
    command = [sys.executable, "-m", "continuity_omega", "demo", "--case", case,
               "--out", str(destination)]
    entry, stdout = run(command, source, output, "pr278_" + case)
    entry.pop("_stderr")
    result = decoded_result(entry, stdout)
    entry.update(case=case, observed_verdict=result.get("verdict"))
    expected_pass = case in PASS_CASES
    entry["expected_returncode"] = 0 if expected_pass else 2
    expected_verdict = "PASS_SYNTHETIC_ONLY" if expected_pass else "REJECTED_BEFORE_HANDOFF"
    valid = entry["returncode"] == entry["expected_returncode"] and result.get("verdict") == expected_verdict
    try:
        if expected_pass:
            handoff = read_object(destination / "HANDOFF.json")
            passport = read_object(destination / "PASSPORT.json")
            audit = read_object(destination / "AUDIT.json")
            economics = passport.get("economics", {})
            boundaries = passport.get("evidence_boundary", {})
            valid = valid and all((
                result.get("orders") == 2, result.get("units") == 1900,
                result.get("restore_findings") == (4 if case == "extra_restored" else 3),
                audit.get("verdict") == "PASS_SYNTHETIC_ONLY",
                audit.get("failure_count") == 0, audit.get("failures") == [],
                audit.get("replayed_orders") == 2, audit.get("replayed_units") == 1900,
                handoff.get("required_units") == 1900, handoff.get("supplier_id") == "PRINTER-P",
                handoff.get("supplier_available_units_in_window") == 2100,
                handoff.get("rehearsed_completion_hours") == 22,
                handoff.get("latest_required_hours") == 48,
                economics.get("modeled_cost") == 5050, economics.get("offer") == 5700,
                economics.get("modeled_contribution") == 650,
                economics.get("currency") == "ILLUSTRATIVE_USD",
                len(boundaries) == 6 and all(value is False for value in boundaries.values()),
                passport.get("comparison", {}).get("incremental_advantage") == "NOT_ESTABLISHED",
                (destination / "PASSPORT.md").is_file(),
                not (destination / "REJECTION.json").exists(),
            ))
            entry.update(orders=audit.get("replayed_orders"), units=audit.get("replayed_units"),
                         modeled_contribution_usd=economics.get("modeled_contribution"))
        else:
            rejection = read_object(destination / "REJECTION.json")
            valid = valid and rejection == result and bool(rejection.get("reason"))
            valid = valid and not any((destination / name).exists() for name in (
                "HANDOFF.json", "PASSPORT.json", "PASSPORT.md", "AUDIT.json"))
    except (OSError, ValueError, TypeError) as exc:
        valid = False
        entry.setdefault("failures", []).append(str(exc))
    entry["passed"] = valid and not entry.get("failures")
    if not entry["passed"]:
        entry.setdefault("failures", []).append("Case differs from its declared synthetic result")
    return entry, destination


def verify_nominal(source: Path, directory: Path, output: Path) -> dict:
    command = [sys.executable, "-m", "continuity_omega", "verify", "--in-dir", str(directory)]
    entry, stdout = run(command, source, output, "pr278_nominal_verify")
    entry.pop("_stderr")
    result = decoded_result(entry, stdout)
    try:
        recorded = read_object(directory / "AUDIT.json")
        entry["passed"] = (entry["returncode"] == 0 and result == recorded
                           and result.get("verdict") == "PASS_SYNTHETIC_ONLY"
                           and result.get("failure_count") == 0
                           and result.get("replayed_orders") == 2
                           and result.get("replayed_units") == 1900)
    except (OSError, ValueError) as exc:
        entry.setdefault("failures", []).append(str(exc))
    if not entry["passed"]:
        entry.setdefault("failures", []).append("Nominal verification did not reproduce its audit")
    entry["observed_verdict"] = result.get("verdict")
    return entry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, required=True, help="New absolute directory; never overwrite prior evidence")
    parser.add_argument("--source277", type=Path, help="Optional local PR277 snapshot instead of downloading its files")
    parser.add_argument("--source278", type=Path, help="Optional local PR278 snapshot instead of downloading its files")
    args = parser.parse_args()
    if not args.output.is_absolute():
        parser.error("--output must be an absolute path")
    if args.output.exists() or args.output.is_symlink():
        parser.error("--output already exists; choose a new directory to preserve prior evidence")
    output = args.output.resolve()
    local = {"pr277": args.source277, "pr278": args.source278}
    for label, directory in local.items():
        if directory is not None:
            directory = directory.resolve()
            if not directory.is_dir():
                parser.error(f"{label} source is not a directory: {directory}")
            if output == directory or output.is_relative_to(directory):
                parser.error("--output must not modify a supplied source directory")
            local[label] = directory
    output.mkdir(parents=True)
    (output / "logs").mkdir()
    (output / "cases").mkdir()
    report = {"schema": "continuity-omega-paper/reproduction-run/v1", "started_utc": now(),
              "scope": SCOPE, "python": sys.version, "sources": {}, "runs": [], "errors": []}
    try:
        manifest_bytes = MANIFEST.read_bytes()
        report["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
        specs = source_specs(json.loads(manifest_bytes))
        for label, spec in specs.items():
            report["sources"][label] = {"commit": spec["commit"], "files": len(spec["files"]),
                                        "origin": str(local[label]) if local[label] else "public GitHub raw files",
                                        "identity_verified": False}
            try:
                source, _ = materialize(label, spec, local[label], output)
                report["sources"][label]["identity_verified"] = True
                report["runs"].append(suite(label, source, output))
                if label == "pr277":
                    report["runs"].append(benchmark(source, output))
                else:
                    for case in CASES:
                        entry, directory = handoff_case(case, source, output)
                        report["runs"].append(entry)
                        if case == "nominal":
                            report["runs"].append(verify_nominal(source, directory, output))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                report["errors"].append({"source": label, "error": str(exc)})
            finally:
                copied = output / ("source" + label.removeprefix("pr"))
                report["sources"][label]["copied_source_bytes_unchanged"] = check_source_bytes(copied, spec)
                if local[label] is not None:
                    report["sources"][label]["original_source_bytes_unchanged"] = check_source_bytes(local[label], spec)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report["errors"].append({"stage": "manifest", "error": str(exc)})
    finally:
        report["finished_utc"] = now()
        source_ok = len(report["sources"]) == 2 and all(
            value.get("identity_verified") and value.get("copied_source_bytes_unchanged")
            and value.get("original_source_bytes_unchanged", True)
            for value in report["sources"].values())
        # Two suites + PR277 benchmark + twelve PR278 cases + nominal verification.
        report["passed"] = (not report["errors"] and source_ok and len(report["runs"]) == 16
                            and all(entry["passed"] for entry in report["runs"]))
        report["status"] = "REPRODUCED_SYNTHETIC_ONLY" if report["passed"] else "REPRODUCTION_FAILED"
        write_json(output / "RESULT.json", report)
        print(json.dumps({"status": report["status"], "result": str(output / "RESULT.json"),
                          "runs": len(report["runs"]), "errors": report["errors"],
                          "scope": SCOPE}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
