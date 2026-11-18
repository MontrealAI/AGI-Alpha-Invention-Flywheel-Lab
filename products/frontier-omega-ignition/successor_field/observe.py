"""Requalify all three successor routes in fresh processes, then check the registered recipient."""
import argparse
import collections
from datetime import datetime, timezone
import csv
import json
import platform
from pathlib import Path
import subprocess
import sys
import tempfile
import time
try:
    import resource
except ImportError:  # Python on Windows has no child resource clock.
    resource = None

from cohort import HERE, checked_facts, sha
from triage import desk


def child_cpu():
    if resource:
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        return usage.ru_utime + usage.ru_stime
    return None


def run(command):
    started, cpu = time.monotonic(), child_cpu()
    job = subprocess.run([sys.executable, *map(str, command)], capture_output=True, text=True)
    elapsed = time.monotonic() - started
    return {"exit": job.returncode, "wall_s": round(elapsed, 6),
            "child_cpu_s": round(child_cpu() - cpu, 6) if cpu is not None else None,
            **({"failure": job.stderr.splitlines()[-1:]} if job.returncode else {})}


def observe(output):
    output.mkdir(parents=True, exist_ok=False)
    routes = ["retained", "ordinary", "direct"]
    measurements = {r: [] for r in routes}
    expected_delivery = (HERE / "archive-queue.csv").read_bytes()
    failures = []
    observed_bytes = None
    with tempfile.TemporaryDirectory() as temp:
        for offset in range(len(routes)):
            for route in routes[offset:] + routes[:offset]:
                dest = Path(temp) / f"{offset}-{route}.csv"
                result = run([HERE / "triage.py", "--route", route, "--output", dest])
                if not result["exit"]:
                    data = dest.read_bytes()
                    observed_bytes = data
                    result["recipient_bytes"] = len(data)
                    result["matches_registered_bytes"] = data == expected_delivery
                    result["independent_audit"] = run([HERE / "audit.py", dest])
                measurements[route].append(result)
                if (result["exit"] or not result["matches_registered_bytes"] or
                        result["independent_audit"]["exit"]):
                    failures.append((offset, route))
    accepted = [r for r in routes if not any(name == r for _, name in failures)]
    raw_refusals = {}
    for name in ("forecast", "reference"):
        raw = desk().TableReader(1)
        try:
            raw.feed(checked_facts(name, "html"))
            raw.close()
        except ValueError as error:
            raw_refusals[name] = str(error)
    with (HERE / "archive-queue.csv").open(newline="", encoding="utf8") as fh:
        rows = list(csv.DictReader(fh))
    counts = collections.Counter(r["action"] for r in rows)
    sources = json.loads((HERE / "SOURCES.json").read_text())
    cost = {
        "full_download_bytes": sum(r["bytes"] for r in sources["sources"].values()),
        "sum_parallel_request_wall_seconds": round(sum(r["wall_seconds"] for r in sources["sources"].values()), 6),
        "distinct_projection_bytes": sum(r["bytes"] for r in sources["projections"].values()),
        "archive_queue_bytes": len(expected_delivery),
        "model_calls_in_three_production_routes": 0,
        "engineering_discovery_and_agent_usage_cost": None,
        "human_operating_labor_and_counterfactual": None,
        "deployment_maintenance_support_cost": None,
        "cash_price_or_payment": None,
        "historical_table_desk_qualification": {
            "nemotron_wall_s": 39.1139, "nemotron_cpu_s": 111.714,
            "tesseract_subprocess_wall_s": 1.016715,
            "original_tool_development_and_qualification_price": None,
            "source": "../table_desk/evidence/",
            "allocation": "Earlier programme observations; no claim every use incurs those costs again."
        }
    }
    files = [HERE / n for n in ("cohort.py", "triage.py", "audit.py", "prepare.py", "observe.py",
                                "REGISTRATION.md", "SOURCES.json")]
    files += [HERE.parent / "table_desk/table_desk.py"]
    record = {
        "experiment": "E — archival UT1 forecast-to-final triage", "tolerance_ms": "1.0",
        "recorded_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {"python": platform.python_version(), "machine": platform.machine(), "system": platform.system()},
        "summary": {"dates": len(rows), **{a: counts[a] for a in ("reprocess", "review", "retain", "defer")}},
        "accepted_routes": accepted, "independent_agreement": not failures,
        "queue_sha256": sha(expected_delivery), "reason_counts": dict(collections.Counter(r["reason"] for r in rows)),
        "initial_unadapted_table_reader": raw_refusals,
        "rotation": "Fresh processes in three cyclic orders. Producer includes in-process ASCII check and file delivery. External auditor timed separately.",
        "route_observations": measurements, "failures": failures, "known_costs_and_unknowns": cost,
        "outcome_scope": "Policy simulation over published observations at 00:00 UTC; no beneficiary archive changed.",
        "source_identities": {p.name: sha(p.read_bytes()) for p in files},
    }
    if not failures:
        (output / "archive-queue.csv").write_bytes(observed_bytes)
    (output / "OBSERVATION.json").write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"accepted_routes": accepted, "summary": record["summary"], "failures": failures}))
    return not failures


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True, help="A new output directory")
    sys.exit(0 if observe(ap.parse_args().output) else 1)
