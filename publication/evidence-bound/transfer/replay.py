#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay a matched release-cache decision on two frozen HARNESS revisions."""

import argparse
from datetime import UTC, datetime, timedelta
from hashlib import file_digest, sha256
import hmac
import io
import json
from pathlib import Path
import resource
import sqlite3
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns, process_time_ns
from zipfile import ZipFile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
HARNESS = Path("products/alpha-genesis-harness")
FILES = [str(HARNESS / "bridge"), "products/frontier-member-tools/inventor/relational.py"]
REGISTRATION_PIN = "0fed2762ba73c22f4f45d889f7f044ccbb82d23621a24c9626b010aac5c48474"
TABLE_SCHEMA = {"assets": {"archive": "TEXT", "expected_hash": "TEXT", "observed_hash": "TEXT"}}
APPROVED = "release-cache"
CAP = ["construct_table", "run_table"]
OMITTED_ARCHIVE = "endpoint-evidence-screen-1.0.0.zip"
LOCAL_CANDIDATE = "aa42b078e10a745f22f0ce2dba8fceaca8caabba"
REVIEW_HEAD = "43d6192655d922d886bceb0b4e61be8bcfaa766e"
CANDIDATE_TREE = "dab63b5461958e328b11782ca3a11a2a8a9cd5bd"


def stable(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def fingerprint(value):
    return sha256(stable(value)).hexdigest()


def setup():
    registration = (HERE / "REGISTRATION.json").read_bytes()
    sources = (HERE / "SOURCES.json").read_bytes()
    assert sha256(registration).hexdigest() == REGISTRATION_PIN
    registration = json.loads(registration)
    assert sha256(sources).hexdigest() == registration["freeze"]["source_sha256"]
    return registration, json.loads(sources)


def panel(sources, ident):
    published = sources["production"]
    manifest = sources["staging"] if ident == "staging" else published
    rows = {"assets": [{"archive": name, "expected_hash": expected,
                        "observed_hash": sources["observed"][name]["sha256"]}
                       for name, expected in manifest["assets"].items()]}
    if ident == "missing":
        del rows["assets"][0]["observed_hash"]
    query = "SELECT COUNT(*) FROM assets WHERE expected_hash = observed_hash"
    if ident == "incorrect-tool":
        query += f" AND archive <> '{OMITTED_ARCHIVE}'"
    assertion = "4" if ident in {"false-prose", "incorrect-tool"} else "5"
    argument = {"fixtures": rows} if ident == "fixture" else {"dataset": APPROVED}
    actions = [{"tool": "construct_table", "name": "release-cache.json", "schema": TABLE_SCHEMA, "sql": query},
               {"tool": "run_table", "name": "release-cache.json", "input": argument}]
    observed = {name: data for name, data in sources["observed"].items() if ident != "missing" or name != rows["assets"][0]["archive"]}
    return {"manifest": manifest, "rows": rows, "actions": actions, "assertion": assertion,
            "published": published, "source_url": sources["production_receipt_url"], "observed": observed}


def baseline(disposition, reason=None, value=None):
    return {key: item for key, item in {"status": disposition, "reason": reason, "value": value}.items() if item is not None}


def reference_count(sources):
    return sum(hmac.compare_digest(requirement, sources["observed"][name]["sha256"])
               for name, requirement in sources["production"]["assets"].items())


def ordinary(case, expected):
    manifest, published = case["manifest"], case["published"]
    action = case["actions"][1]
    rows = case["rows"]["assets"]
    if "fixtures" in action["input"]:
        disposition = baseline("REJECTED", "INPUT_ORIGIN_INELIGIBLE")
    elif manifest["source_commit"] != published["source_commit"]:
        disposition = baseline("REJECTED", "INPUT_VERSION_MISMATCH")
    elif not all(row.get("observed_hash") for row in rows):
        disposition = baseline("ABSTAIN", "REQUIRED_FIELD_MISSING")
    else:
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE assets (archive TEXT PRIMARY KEY, expected_hash TEXT, observed_hash TEXT)")
            db.executemany("INSERT INTO assets VALUES (:archive, :expected_hash, :observed_hash)", rows)
            [(value,)] = db.execute(case["actions"][0]["sql"]).fetchall()
        if str(value) != case["assertion"]:
            disposition = baseline("REJECTED", "CLAIM_CONTRADICTS_EXECUTED_RESULT")
        elif value != expected or {row["archive"] for row in rows} != set(published["assets"]):
            disposition = baseline("REJECTED", "REFERENCE_DISAGREES")
        else:
            disposition = baseline("VERIFIED", value=str(value))
    report = {"algorithm": "Independent Python and in-memory SQLite release witness", "decision": disposition,
              "receipt_sha256": manifest["receipt_sha256"], "input_sha256": fingerprint(case["rows"]),
              "action_sha256": fingerprint(case["actions"]), "reference_count": expected}
    return disposition, {"portable_bytes": len(stable(report)), "portable_summary_sha256": fingerprint(report)}


def bind(case, expected, digest):
    manifest, published = case["manifest"], case["published"]
    parent = {"kind": "values", "origin": "VERIFIED_EXTERNAL_SOURCE" if manifest == published else "OPERATOR_SUPPLIED_OBSERVATION",
              "version": manifest["source_commit"], "facts": {"receipt": manifest["receipt_sha256"]},
              "sha256": digest(manifest), "values": manifest}
    if manifest == published:
        parent["source"] = case["source_url"]
    observed = {"kind": "values", "origin": "OPERATOR_SUPPLIED_OBSERVATION", "version": published["source_commit"],
                "facts": {"capture_workflow_run": published["workflow_run"]}, "sha256": digest(case["observed"]),
                "values": case["observed"]}
    bounds = {"workflow_run": published["workflow_run"], "required_archive_count": len(published["assets"])}
    derived = {"kind": "table", "origin": "DERIVED_DATA", "version": manifest["source_commit"],
               "facts": bounds | {"workflow_run": manifest["workflow_run"]},
               "sha256": digest(case["rows"]), "parents": {"release-receipt": parent["sha256"],
                                                      "cached-archive-observations": observed["sha256"]}}
    claim = {"id": "verified-cached-archives", "dataset": APPROVED, "tool": "run_table", "version": published["source_commit"],
             "locator": ["rows", 0, 0], "unit": "archive", "dimension": "count", "requires": bounds,
             "required_fields": [["assets", key] for key in TABLE_SCHEMA["assets"]],
             "reference": {"value": str(expected), "source": "Independent comparison of the frozen official receipt and SHA-256 of the captured archive bytes"}}
    return {"inputs": {"release-receipt": parent, "cached-archive-observations": observed, APPROVED: derived}, "claims": [claim]}


def controller(case, expected, retained, objective, witness=None):
    from bridge.universal_missions import UniversalMissionService
    from bridge.workflow_demo import FixtureRuntime
    from bridge.workflows import digest

    requirements = {"approved_tables": {APPROVED: case["rows"]}}
    construct, run = case["actions"]
    if retained:
        requirements["evidence"] = bind(case, expected, digest)
        claim = requirements["evidence"]["claims"][0]
        run = {**run, "claim": {key: claim[key] for key in ("id", "unit", "dimension")} | {"value": case["assertion"]}}
    proposal = {"summary": f"The available release cache has exactly {case['assertion']} qualifying files.",
                "actions": [construct, run], "done": True}
    with TemporaryDirectory() as workspace:
        service = UniversalMissionService(FixtureRuntime([proposal]), workspace)
        try:
            created = service.submit({"ambition": objective, "context": "Exact public release evidence and approved cached file digests.",
                                      "language": "en", "provider": "fixture", "model": "authored-release-verification",
                                      "expires_at": (datetime.now(UTC) + timedelta(minutes=3)).isoformat(),
                                      "max_turns": 1, "max_actions": 2, "max_output_tokens": 1024,
                                      "tools": CAP, "requirements": requirements})
            result = service.step(created["id"])
            archive = service.export(created["id"])
        finally:
            service.close()
    claim = (result.get("evidence", {}).get("claims") or [{}])[0]
    if claim.get("status") == "VERIFIED":
        disposition = baseline("VERIFIED", value=claim["value"])
    else:
        disposition = baseline(claim.get("status", "UNRESOLVED"), claim.get("reason"))
    execution = next((event["detail"]["outcome"] for event in result["events"]
                      if event["kind"] == "tool_completed" and event["detail"]["tool"] == "run_table"), {})
    detail = {"portable_bytes": len(stable(archive)), "portable_summary_sha256": archive["sha256"],
              "native_status": result["status"], "native_qualification": result["qualification"],
              "raw_rows": execution.get("rows"), "input_origin": execution.get("input_origin"),
              "source_binding_present": bool(claim.get("execution_receipt"))}
    if witness is not None:
        witness.append(archive)
    return disposition, detail


def cpu_seconds():
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return process_time_ns() / 1_000_000_000 + children.ru_utime + children.ru_stime


def worker(arm, witness_path=None):
    if arm != "ordinary":
        # Import before timing so shared interpreter/import setup cannot dominate a panel.
        from bridge import universal_missions, workflow_demo, workflows  # noqa: F401
    registration, sources = setup()
    expected = reference_count(sources)
    reports = {}
    for repeated in range(3):
        for row in registration["panels"]:
            ident = row["id"]
            case = panel(sources, ident)
            witness = [] if witness_path and not repeated and ident == "exact" else None
            begin, cpu = perf_counter_ns(), cpu_seconds()
            decision, detail = ordinary(case, expected) if arm == "ordinary" else controller(
                case, expected, arm == "retained", registration["objective"], witness)
            duration = (perf_counter_ns() - begin) / 1_000_000_000
            measured = {"wall_seconds": duration, "cpu_seconds": cpu_seconds() - cpu}
            if not repeated:
                reports[ident] = {"decision": decision, "exact": decision == row["expected"], "detail": detail, "runs": []}
            assert reports[ident]["decision"] == decision
            reports[ident]["runs"].append(measured)
            if witness:
                witness_path.write_bytes(stable(witness[0]) + b"\n")
    return reports


def frozen(revision, temp):
    if revision == LOCAL_CANDIDATE:
        for revision in (LOCAL_CANDIDATE, REVIEW_HEAD):
            probe = subprocess.run(["git", "rev-parse", "--verify", f"{revision}^{{tree}}"], cwd=ROOT,
                                   capture_output=True, text=True, check=False)
            if probe.returncode == 0 and probe.stdout.strip() == CANDIDATE_TREE:
                break
        else:
            raise ValueError(f"Fetch PR #594 commit {REVIEW_HEAD} to restore the frozen candidate tree.")
    target = temp / revision
    content = subprocess.check_output(["git", "archive", "--format=zip", revision, *FILES], cwd=ROOT)
    with ZipFile(io.BytesIO(content)) as archive:
        archive.extractall(target)
    return target / HARNESS


def main(witness_path=None):
    registration, sources = setup()
    revisions = registration["freeze"]
    with TemporaryDirectory() as folder:
        temp = Path(folder)
        older, newer = (frozen(revisions[key], temp) for key in ("original", "candidate"))
        report = {"schema": "frontier/controlled-release-evidence-replay/v1", "registration_sha256": REGISTRATION_PIN,
                  "frozen": {**revisions, "candidate_tree": CANDIDATE_TREE, "tree_equivalent_public_head": REVIEW_HEAD},
                  "source_receipt": sources["production_actions_url"],
                  "python": sys.version.split()[0], "sqlite": sqlite3.sqlite_version,
                  "scope": "Local authored replays with actual shipped bytes captured previously and exact negative controls. Zero inference calls.",
                  "results": {}}
        for arm, bridge in (("original", older), ("ordinary", None), ("retained", newer), ("withdrawal", newer)):
            cmd = [sys.executable, "-B", str(Path(__file__).resolve()), "--worker", arm]
            if bridge is not None:
                cmd.extend(["--bridge", str(bridge)])
            if arm == "retained" and witness_path is not None:
                cmd.extend(["--witness", str(witness_path)])
            rows = json.loads(subprocess.check_output(cmd))
            timings = [run for row in rows.values() for run in row["runs"]]
            report["results"][arm] = {"exact_dispositions": sum(row["exact"] for row in rows.values()),
                                       "false_accepted": sum(row["decision"]["status"] == "VERIFIED" and not row["exact"] for row in rows.values()),
                                       "median_panel_wall_seconds": statistics.median(row["wall_seconds"] for row in timings),
                                       "median_panel_cpu_seconds": statistics.median(row["cpu_seconds"] for row in timings),
                                       "panels": rows}
    return report


def verify_captures(directory):
    _, sources = setup()
    checked = {"atlas-release.json": sources["production"]["receipt_sha256"]}
    for name, asset in sources["observed"].items():
        path = directory / name
        assert path.stat().st_size == asset["bytes"], name
        checked[name] = asset["sha256"]
    for name, expected in checked.items():
        with (directory / name).open("rb") as captured:
            assert hmac.compare_digest(file_digest(captured, "sha256").hexdigest(), expected), name
    return {"exact_capture_files": len(checked), "source_commit": sources["production"]["source_commit"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=("original", "retained", "ordinary", "withdrawal"))
    parser.add_argument("--bridge", type=Path)
    parser.add_argument("--verify-captures", type=Path, help="Check an existing directory of exact #593 Pages captures")
    parser.add_argument("--witness", type=Path, help="Save the native portable archive of the authentic panel")
    args = parser.parse_args()
    if args.bridge:
        sys.path.insert(0, str(args.bridge))
    if args.verify_captures:
        result = verify_captures(args.verify_captures)
    else:
        result = worker(args.worker, args.witness) if args.worker else main(args.witness)
    print(json.dumps(result, indent=2, sort_keys=True))
