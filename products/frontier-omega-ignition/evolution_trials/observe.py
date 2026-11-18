"""Measure delivery from identical local inputs in fresh processes, with a separate recipient."""
import argparse
from collections import Counter
import hashlib
import json
import platform
from pathlib import Path
import resource
import statistics
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parent
PYTHON = [sys.executable, "-B"]
ARMS = {
    "retained": PRODUCT / "invention/evolution/alert.py",
    "direct_sql": HERE / "verify.py",
    "ordinary_reuse": HERE / "reuse.py",
}


def canonical(document):
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


def check_ordinary(observed, truth):
    accepted = 0
    if [c["id"] for c in observed["cohorts"]] != [c["id"] for c in truth["cohorts"]]:
        raise ValueError("An ordinary-reuse cohort differs")
    for partial, scope in zip(observed["cohorts"], truth["cohorts"]):
        if len(partial["decisions"]) != len(scope["coverage"]):
            raise ValueError("An ordinary-reuse cohort lost target/band dispositions")
        for row, actual in zip(partial["decisions"], scope["coverage"]):
            if (row["target_id"], row["band"]) != (actual["target_id"], actual["band"]):
                raise ValueError("An ordinary-reuse target or passband differs")
            if row["disposition"] == "no_trigger_proven":
                if actual["status"] != "no_trigger":
                    raise ValueError("Incorrect disposition from the reduced colour receipt")
                accepted += 1
            elif row["disposition"] != "insufficient_information":
                raise ValueError("Unknown ordinary-reuse claim")
    if observed["verified_issuance_dispositions"] != accepted:
        raise ValueError("Scope of partial result differs")


def cpu_used():
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime + usage.ru_stime + time.process_time()


def measure(function, *args):
    cpu, t0 = cpu_used(), time.perf_counter_ns()
    function(*args)
    return {"wall_ms": round((time.perf_counter_ns()-t0)/1_000_000, 3),
            "cpu_ms": round((cpu_used()-cpu)*1000, 3)}


def produce(arm, dest):
    subprocess.run([*PYTHON, ARMS[arm], "--out", dest], check=True, stdout=subprocess.DEVNULL)


def receive(arm, path, reproduction):
    # Symmetric full checks. Each complete arm receives exactly one normal run of the other plus identical comparison.
    other = "direct_sql" if arm == "retained" else "retained"
    produce(other, reproduction)
    observed, independent = (json.loads(p.read_bytes()) for p in (path, reproduction))
    if arm == "ordinary_reuse":
        check_ordinary(observed, independent)
    elif canonical(observed) != canonical(independent):
        raise ValueError("Complete delivered quantities disagree")


def rotation():
    rows = {name: [] for name in ARMS}
    fingerprints, sizes = {}, {}
    with tempfile.TemporaryDirectory() as tmp:
        orders = (tuple(ARMS), ("direct_sql", "ordinary_reuse", "retained"), ("ordinary_reuse", "retained", "direct_sql"))
        for order in orders:
            for arm in order:
                path = Path(tmp) / f"{arm}-{len(rows[arm])}.json"
                produced = measure(produce, arm, path)
                checked = measure(receive, arm, path, path.with_suffix(".recipient.json"))
                fp = canonical(json.loads(path.read_bytes()))
                if arm in fingerprints and fingerprints[arm] != fp:
                    raise ValueError(f"Result changed between rotations: {arm}")
                fingerprints[arm], sizes[arm] = fp, path.stat().st_size
                total = {k: round(produced[k] + checked[k], 3) for k in produced}
                rows[arm].append(dict(production=produced, recipient=checked, accepted_delivery=total))
    if fingerprints["retained"] != fingerprints["direct_sql"]:
        raise ValueError("Complete routes disagree")
    medians = {arm: {step: {measure: statistics.median(run[step][measure] for run in observations)
                            for measure in ("wall_ms", "cpu_ms")} for step in ("production", "recipient", "accepted_delivery")}
               for arm, observations in rows.items()}
    return {"clock": "perf_counter_ns and process_time plus child CPU; normal command startup included",
            "order": "three cyclic rotations; one fresh process per producer and per recipient; local filesystem cache shared",
            "python": platform.python_version(), "platform": platform.system() + " " + platform.machine(),
            "observations": rows, "median_ms": medians, "canonical_sha256": fingerprints, "delivered_bytes": sizes}


def observe():
    from reuse import inventory
    from verify import conventional
    full, reduced = conventional(), inventory()
    return {"scope": "two frozen SLSN-candidate research cohorts on recorded event time",
            "source_sha256": {c["id"]: c["source_sha256"] for c in full["cohorts"]},
            "decisions": sum(len(c["coverage"]) for c in full["cohorts"]),
            "scientific_summary": full["summary"],
            "scientific_comparisons": {c["id"]: sum(r["comparisons"] for r in c["coverage"]) for c in full["cohorts"]},
            "ordinary_reuse": {"resolved_issuance_dispositions": reduced["verified_issuance_dispositions"],
                               "status_counts": dict(Counter(r["disposition"] for c in reduced["cohorts"] for r in c["decisions"])),
                               "retained_distinct_detections": {c["id"]: c["retained_distinct_detections"] for c in reduced["cohorts"]}},
            "resource_observation": rotation()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path, help="record actual timings and dispositions in a fresh file")
    args = parser.parse_args()
    results = observe()
    with args.out.open("x", encoding="utf-8") as output:
        json.dump(results, output, indent=2, allow_nan=False)
        output.write("\n")
