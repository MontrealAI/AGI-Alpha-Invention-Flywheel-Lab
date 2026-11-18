"""Construct fresh research operations, then independently replay the delivered ZIPs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from time import perf_counter
from zipfile import ZipFile


PRODUCT = Path(__file__).resolve().parents[2]
SOURCES = PRODUCT / "action_study/qualification_choice/sources"
RESERVED = {
    "astropy__astropy": "20cb08123f7cd8328241da94b102c4d2315ccdcb",
    "matplotlib__matplotlib": "0f83580005eb0b07c5b4a55a5836ed66bccf37c4",
    "pallets__flask": "685752bf65361740e3bc71d71caf74401ac0e969",
    "sphinx-doc__sphinx": "243279c01e731ae7b4befb6622748c33a7adee61",
}
JQ = '{task:.id,trace_bytes:(.B_content_range|split("/")|last|tonumber),observed:.B_retrieved_utc}'


def check(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode()


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(args, *, cwd=PRODUCT, data=None, codes=(0,)):
    result = subprocess.run(args, cwd=cwd, input=data, capture_output=True,
                            env={**os.environ, "IGNITION_MODEL_PROVIDER": "unavailable",
                                 "PYTHONDONTWRITEBYTECODE": "1"})
    check(result.returncode in codes, f"{Path(args[0]).name} returned {result.returncode}: "
          + result.stderr.decode(errors="replace")[-1200:])
    return result.stdout


def load_rows(name):
    raw = (SOURCES / (name + ".json")).read_bytes()
    if name in RESERVED:
        blob = b"blob " + str(len(raw)).encode() + b"\0" + raw
        check(hashlib.sha1(blob).hexdigest() == RESERVED[name], "Reserved source changed: " + name)
    study = json.loads(raw)
    return [dict(zip(study["row_fields"], values, strict=True)) for values in study["rows"]]


def expected_row(row):
    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", row["B_content_range"])
    check(match is not None, "Source receipt has no completed byte range")
    first, last, length = map(int, match.groups())
    check(first <= last < length, "Source byte range is inconsistent")
    return {"task": row["id"], "observed": row["B_retrieved_utc"], "trace_bytes": length}


def make_mission(kind, purpose, definition, cases):
    return {"mission": {"purpose": purpose, "beneficiary": "MONTREAL.AI research operations",
                        "requirements": ["Check all registered cases and deliver an offline executable."],
                        "authority": {}, "resources": {"max_model_calls": 0},
                        "construction_spec": {"purpose": purpose, "kind": kind,
                                              "definition": definition, "cases": cases}}}


def build_cli(work, output, label, mission):
    brief = work / (label + ".json")
    brief.write_bytes(encoded(mission))
    cli = [sys.executable, "-B", "-m", "ignition", "--state", str(work / "state")]
    start = [*cli, "start", str(brief), "--request-id", "release-transfer-" + label]
    before = perf_counter()
    result = json.loads(run(start))
    replay = json.loads(run(start))
    archive = output / (label + ".zip")
    run([*cli, "export", result["id"], str(archive), "--version", str(result["version"])])
    return accepted(result, replay, archive, before, "private_cli")


def accepted(result, replay, archive, before, transport):
    check(result["status"] == "verified", "Mission failed: " + str(result.get("error")))
    check(result["routing"]["method"] == "specialist", "This comparison requires the existing exact compiler")
    check((result["id"], result["artifact"]) == (replay["id"], replay["artifact"]), "Changed on reopening")
    return {"id": result["id"], "runtime": result["runtime"], "package_sha256": sha(archive),
            "artifact_sha256": result["artifact"]["sha256"], "contract_sha256": result["contract_sha256"],
            "comparison": result["evaluation"]["comparison"]["outcome"], "verified": True,
            "reopened_without_duplicate": True, "transport": transport, "model_calls": 0,
            "start_restart_export_seconds": round(perf_counter() - before, 6)}


def unpack(archive, folder, expected_sha):
    check(sha(archive) == expected_sha, "Transfer package digest mismatch")
    with ZipFile(archive) as package:
        for item in package.infolist():
            path = Path(item.filename)
            check(not path.is_absolute() and ".." not in path.parts, "Invalid member name")
        package.extractall(folder)
    run([sys.executable, "-IB", "run.py", "verify"], cwd=folder)
    return [sys.executable, "-IB", str(folder / "run.py")]


def produce(out, builder=build_cli):
    out.mkdir(mode=0o700)
    queue = out / "queue"
    queue.mkdir(mode=0o700)
    source = run(["git", "rev-parse", "HEAD"]).decode().strip()
    dirty = run(["git", "status", "--short", "--", "ignition", "qa/transfer",
                 "../alpha-genesis-harness/bridge"]).decode().splitlines()
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        seed = load_rows("django__django")[:2]
        definition = {"columns": [{"source": "id", "target": "task", "type": "text"},
                                  {"source": "B_content_range", "target": "trace_bytes", "type": "integer",
                                   "split": {"separator": "/", "index": -1}},
                                  {"source": "B_retrieved_utc", "target": "observed", "type": "text"}],
                      "extra_fields": "drop"}
        migration = make_mission("record_migration", "Prepare a research queue of trace identities, "
                                 "archive byte counts and observation timestamps.", definition, [
                                     {"name": "Two Django result headers", "input": {"rows": seed},
                                      "expected": {"rows": [expected_row(row) for row in seed]}}])
        first = builder(work, out, "migration", migration)
        app = unpack(out / "migration.zip", work / "first", first["package_sha256"])
        for name in RESERVED:
            rows = load_rows(name)
            (queue / (name + ".jsonl")).write_bytes(
                run([*app, "migrate-jsonl"], data=b"".join(encoded(row) for row in rows)))
        inventory = {file.name: sha(file) for file in sorted(queue.iterdir())}
        empty = {"ok": False, "matched": [], "changed": [], "missing": sorted(inventory), "unexpected": []}
        audit = make_mission("manifest_audit", "Verify that the transferred trace-budget queue is complete "
                             "and unchanged before researchers schedule the full downloads.",
                             {"manifest": inventory}, [{"name": "Missing research batch",
                                                        "input": {"files": {}}, "expected": empty}])
        second = builder(work, out, "integrity", audit)
    manifest = out / "producer.json"
    manifest.write_bytes(encoded({"source": source, "changed_source_paths": dirty, "migration": first,
                                 "integrity": second, "output_sha256": inventory, "heldout_git_blobs": RESERVED}))
    print(json.dumps({"source": source, "manifest_sha256": sha(manifest), "mission_ids": [first["id"], second["id"]]}))


def timed(call):
    start = perf_counter()
    result = call()
    return result, round((perf_counter() - start) * 1000, 4)


def inventory_cli(root):
    names = sorted(f.name for f in root.iterdir())
    output = run(["sha256sum", "--", *names], cwd=root).decode().splitlines()
    return {name: line.split()[0] for name, line in zip(names, output, strict=True)}


def classify(expected, actual):
    shared = expected.keys() & actual.keys()
    good = sorted(name for name in shared if expected[name] == actual[name])
    return {"ok": expected == actual, "matched": good, "changed": sorted(shared - set(good)),
            "missing": sorted(expected.keys() - actual.keys()), "unexpected": sorted(actual.keys() - expected.keys())}


def receive(out, trusted):
    check(sha(out / "producer.json") == trusted, "Producer manifest digest mismatch")
    producer = json.loads((out / "producer.json").read_bytes())
    route_times = []
    audit_times = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        migrate = unpack(out / "migration.zip", work / "migrate", producer["migration"]["package_sha256"])
        audit = unpack(out / "integrity.zip", work / "audit", producer["integrity"]["package_sha256"])
        queue = out / "queue"
        for index, name in enumerate(RESERVED):
            rows = load_rows(name)
            inputs = b"".join(encoded(row) for row in rows)
            expected = [expected_row(row) for row in rows]
            calls = {"candidate": lambda: run([*migrate, "migrate-jsonl"], data=inputs),
                     "jq": lambda: run(["jq", "-c", JQ], data=inputs)}
            times = {}
            for arm in (list(calls) if index % 2 == 0 else reversed(calls)):
                raw, times[arm] = timed(calls[arm])
                check([json.loads(line) for line in raw.splitlines()] == expected, f"{name}: {arm} differs")
            received = (queue / (name + ".jsonl")).read_bytes().splitlines()
            check([json.loads(line) for line in received] == expected, f"{name}: transferred queue differs")
            route_times.append({"source": name, "rows": len(rows),
                                "planned_trace_bytes": sum(row["trace_bytes"] for row in expected),
                                "elapsed_ms": times})
        expected = producer["output_sha256"]
        names = sorted(expected)
        for index, condition in enumerate(("intact", "truncated", "replaced", "recovered")):
            sample = work / condition
            shutil.copytree(queue, sample)
            if condition == "truncated":
                item = sample / names[0]
                item.write_bytes(item.read_bytes()[:-1])
            if condition == "replaced":
                (sample / names[1]).rename(sample / "substituted.jsonl")
            codes = (1,) if condition in ("truncated", "replaced") else (0,)
            calls = {"candidate": lambda: json.loads(run([*audit, "audit-directory", str(sample)], codes=codes)),
                     "coreutils": lambda: classify(expected, inventory_cli(sample))}
            observations = {}
            times = {}
            for arm in (list(calls) if index % 2 == 0 else reversed(calls)):
                observations[arm], times[arm] = timed(calls[arm])
            check(observations["candidate"] == observations["coreutils"], condition + ": verdicts differ")
            audit_times.append({"condition": condition, "verdict": observations["candidate"], "elapsed_ms": times})
    report = {"source": producer["source"], "producer_sha256": trusted, "migration": route_times,
              "directory_acceptance": audit_times, "correctness_vs_conventional": "tie",
              "authorized_new_spend_usd": 0, "observed_model_calls": 0, "production_qualified": False,
              "full_economic_cost_usd": None, "accepted_by_beneficiary": None, "payment_received": None,
              "timing_scope": "Warm local host; one CLI process per arm per condition, including startup. "
                              "Input extraction and operator labor excluded. No latency advantage inferred."}
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["produce", "receive"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--manifest-sha256")
    args = parser.parse_args()
    if args.action == "produce":
        produce(args.directory.resolve())
    elif args.manifest_sha256:
        receive(args.directory.resolve(), args.manifest_sha256)
    else:
        parser.error("receive requires the producer's manifest SHA-256")
