"""One-command bounded development replay. Fixed trusted code only; no generated programs."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
CANDIDATE_SHA = "72d14ed2fe728b669e8a77834f88f7b3c6c7521537c30b616286719933874f01"
CLOSURE_SHA = "a06a4f7630184b54205173e1f271e6af7ae5396687fd64deb575ae4de13b3252"
DATA_SHA = {"pglib_opf_case14_ieee.m": "bd5c568621de65e4b0922317010868bc7fa94173807faa10ea8fdbbe77c28106",
            "pglib_opf_case30_ieee.m": "cae3290639d989731d32428aacf30c0b918bc91db73bc54791f3aa62d3f76c70"}


def write(path, data):
    with path.open("x") as stream:
        json.dump(data, stream, indent=2, allow_nan=False)
        stream.write("\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def worker(output):
    start, cpu = time.monotonic(), time.process_time()
    manifest = ROOT / "campaign/cycle-001/CLOSURE.json"
    if digest(manifest) != CLOSURE_SHA:
        raise ValueError("SOURCE_CLOSURE_MANIFEST_MISMATCH")
    closure = json.loads(manifest.read_text())
    expected_python = {p for p in closure if p.endswith(".py")} | {"reproduce.py"}
    actual_python = {str(p.relative_to(ROOT)) for p in ROOT.rglob("*.py")
                     if not set(p.relative_to(ROOT).parts) & {"evidence", ".venv", ".git", "__pycache__"}}
    if actual_python != expected_python:
        raise ValueError("SOURCE_SET_MISMATCH")
    for path, sha in closure.items():
        if (ROOT / path).is_symlink() or digest(ROOT / path) != sha:
            raise ValueError("SOURCE_IDENTITY_MISMATCH " + path)
    expected = {ROOT / "grid_screen/__init__.py": CANDIDATE_SHA,
                **{ROOT / "research" / p: h for p, h in DATA_SHA.items()}}
    for path, sha in expected.items():
        if digest(path) != sha:
            raise ValueError("SOURCE_IDENTITY_MISMATCH " + path.name)
    from grid_screen import screen, exact_screen, legacy_screen, load_case
    from campaign.successor import construct
    from verification.verify import evaluate, compare
    from verification.check_inputs import check_inputs
    check_inputs(ROOT / "research", ROOT / "verification/data_manifest.json")
    verified = evaluate(ROOT / "grid_screen/__init__.py", CANDIDATE_SHA,
                        [ROOT / "research" / p for p in DATA_SHA], output / "independent", ROOT / "verification/spec.json")
    if not verified["all_passed"]:
        raise ValueError("Independent DC verification failed")
    predecessor = load_case(ROOT / "research/pglib_opf_case14_ieee.m")
    legacy, repaired = legacy_screen(predecessor), screen(predecessor)
    criticism = {"origin": "developer deliberately seeded legacy singular-denominator suppression, not recovered autonomous failure",
                 "legacy_errors": compare(predecessor, legacy), "repair_errors": compare(predecessor, repaired),
                 "constraint": "Disconnected outage cannot be labeled CONNECTED or count as accepted service",
                 "repair": "Explicit graph-connectivity guard, otherwise full DC LODF; unchanged independent flow specification"}
    write(output / "CRITICISM_REPAIR.json", criticism)
    write(output / "PREDECESSOR.json", repaired)
    successor = load_case(ROOT / "research/pglib_opf_case30_ieee.m")
    arms = {}
    for name, method in [("inheritance", screen), ("no_inheritance_direct_solve", exact_screen),
                         ("ordinary_reuse_equivalent_content", screen), ("unguarded_ablation", legacy_screen)]:
        arms[name] = construct(successor, method)
    def semantic(arm):
        return {k: v for k, v in arm.items() if k != "construction_wall_seconds"}
    inherited, ordinary, direct = (arms[k] for k in ("inheritance", "ordinary_reuse_equivalent_content", "no_inheritance_direct_solve"))
    endpoints = [inherited["interval_mw"], direct["interval_mw"]]
    if (endpoints[0] is None) != (endpoints[1] is None):
        raise ValueError("Successor envelope differs from direct control")
    if endpoints[0] is not None and any(abs(a-b)>1e-5 for a,b in zip(*endpoints)):
        raise ValueError("Successor envelope endpoint mismatch")
    write(output / "SUCCESSOR.json", {"arms": arms, "ordinary_reuse_equal": semantic(inherited) == semantic(ordinary),
          "endpoint_matches_direct": True, "causal_experience_advantage": "NOT_ESTABLISHED",
          "construction_scope": "Fresh conditional transfer-envelope artifact on preselected IEEE30; not completed utility delivery",
          "lifecycle_costs": "inference, discovery, extraction, adaptation, integration and verification prices UNKNOWN; no after-cost advantage claimed",
          "freshness": "Public second benchmark chosen before candidate outcomes; not protected statistical confirmation"})
    from exchange_boundary import run as exchange_run
    exchange = exchange_run(output / "SUCCESSOR.json", output / "exchange")
    report = {"schema": "agi-alpha-first-campaign-development/v1", "candidate_sha256": CANDIDATE_SHA,
              "independent_checks": len(verified["checks"]), "independent_checks_passed": verified["all_passed"],
              "criticism_repaired": bool(criticism["legacy_errors"]) and not criticism["repair_errors"],
              "data_sha256": DATA_SHA, "successor_ordinary_reuse_equal": semantic(inherited) == semantic(ordinary),
              "exchange_mechanism_checks": len(exchange["mechanismChecks"]),
              "simulated_revenue": exchange["snapshot"]["revenue"],
              "unrestricted_earned": exchange["snapshot"]["unrestrictedEarned"],
              "decision": "RETAIN_INCUMBENT_FOR_KNOWN_DC_MECHANISM; PIVOT_OPPORTUNITY_BEFORE_COMMERCIAL_ADMISSION",
              "verdicts": {"engineering_execution": "DEMONSTRATED_IN_REDUCED_DC_SCOPE",
                  "consequential_enabling_change": "NOT_DEMONSTRATED", "commercial_viability": "UNKNOWN",
                  "investment_attractiveness": "UNKNOWN", "alpha_value_capture": "UNKNOWN",
                  "unrestricted_earned_funding": "NOT_DEMONSTRATED", "causal_successor_benefit": "NOT_ESTABLISHED",
                  "progressive_experience_advantage": "NOT_TESTED", "complete_connected_flywheel": "NOT_DEMONSTRATED"},
              "resources": {"worker_wall_seconds": time.monotonic()-start, "worker_cpu_seconds": time.process_time()-cpu,
                  "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  "price_rates": None, "complete_monetary_cost": None,
                  "other_costs_unknown": ["root and subagent inference", "research", "failed attempts", "verification and integration labor",
                                          "storage and maintenance", "buyer acquisition and support", "risk and terminal obligations"]},
              "no_statistical_confirmation": True, "alpha_spent": 0,
              "limits": ["No AC/voltage/dynamic/real dispatch qualification", "No buyer specification, demand evidence or receipts",
                         "Same host/model procedural verification only; verifier source exposure recorded",
                         "Known ordinary method; no autonomous structural discovery or unrestricted strategy invention",
                         "Resource-limited trusted worker is not a qualified arbitrary generated-code sandbox"]}
    write(output / "REPORT.json", report)
    return report


def limits():
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (10*1024**2, 10*1024**2))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args()
    output = args.output.resolve()
    if args.worker:
        worker(output)
        return 0
    output.mkdir(parents=True, exist_ok=False)
    write(output / "STARTED.json", {"state": "STARTED", "prior_evidence_overwrite": False,
          "limits": {"wall_seconds": 150, "cpu_seconds": 120, "address_space_bytes": 1024**3, "file_bytes": 10*1024**2},
          "scope": "Fixed trusted code; no untrusted shell, generated code, provider calls or network operations"})
    env = {"PATH": os.defpath, "LANG": "C.UTF-8", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "PYTHONHASHSEED": "0"}
    try:
        with (output / "WORKER.log").open("xb") as log:
            result = subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "--worker", "--output", str(output)],
                                    cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=150, preexec_fn=limits)
        if result.returncode:
            raise RuntimeError("Worker failed; preserve WORKER.log and partial evidence")
        write(output / "COMPLETE.json", {"state": "COMPLETE", "report_sha256": digest(output / "REPORT.json")})
        print(json.dumps({"output": str(output), "report_sha256": digest(output / "REPORT.json")}))
    except (Exception, KeyboardInterrupt) as exc:
        write(output / "INTERRUPTED.json", {"state": "INCOMPLETE", "reason": type(exc).__name__ + ": " + str(exc),
              "recovery": "Preserve directory; rerun to a new exclusive output. No financial settlement occurred."})
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
