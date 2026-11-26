"""Run the registered dispatch comparison and return a reproducible JSON receipt."""

from argparse import ArgumentParser
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import resource
import subprocess
from time import perf_counter_ns, process_time_ns
from unittest.mock import patch
from urllib.error import URLError

import numpy as np
import scipy

from dispatch_inputs import DEV_CASE, EVALUATION_CASES, EVIDENCE_REVISION, PINS, acquire, normalized
from dispatch_recovery import analyze, reconcile, source_matrices
from verify_dispatch_recovery import check_result, conventional

REGISTRATION = "933219e2b791132dae69e840f834b82566416f0c"


def clock(fn, *args):
    wall, cpu = perf_counter_ns(), process_time_ns()
    result = fn(*args)
    return result, {"wall_ms": (perf_counter_ns() - wall) / 1e6,
                    "cpu_ms": (process_time_ns() - cpu) / 1e6}


def rejects(fn, *args):
    try:
        fn(*args)
    except ValueError as error:
        return str(error)
    raise AssertionError("negative control was accepted")


def controls(directory, clean_case, raw, data, output, baseline, truck):
    checks = {
        "wrong_source_digest": rejects(analyze, clean_case, raw[:-1] + bytes([raw[-1] ^ 1]), data),
        "truncated_source": rejects(analyze, clean_case, raw[:-1], data),
        "truncated_numeric_payload": rejects(source_matrices, raw[:-1]),
    }
    network_dir = directory / "control_unavailable"
    with patch("dispatch_inputs.urlopen", side_effect=URLError("registered acquisition control")):
        try:
            acquire(clean_case, network_dir)
        except URLError as error:
            checks["unavailable_acquisition"] = str(error.reason)
        else:
            raise AssertionError("unavailable acquisition was accepted")
    if list(network_dir.iterdir()):
        raise AssertionError("failed acquisition created a ready input")
    checks["unavailable_acquisition_no_commit"] = True

    travel, dist = source_matrices(raw)
    dist[0][8] += 0.5
    decision = reconcile(clean_case, (travel, dist), data)
    if decision["reason"] != "contradictory_representation":
        raise AssertionError("conflicting representation was accepted")
    checks["contradictory_distance"] = decision["reason"]

    travel, dist = source_matrices(raw)
    travel[0][0] = dist[0][8] = dist[8][0] = float("nan")
    decision = reconcile(clean_case, (travel, dist), data)
    if decision["reason"] != "source_value_not_identified":
        raise AssertionError("missing travel was silently filled")
    checks["unbacked_missing_cell"] = decision["reason"]

    travel, dist = source_matrices(raw)
    travel.pop(0)
    dist.pop(8)
    for row in dist:
        row.pop(8)
    decision = reconcile(clean_case, (travel, dist), data)
    if decision["reason"] != "row_identity_not_established":
        raise AssertionError("unkeyed row was silently assigned")
    checks["unkeyed_missing_row"] = decision["reason"]

    tampered = deepcopy(output)
    tampered["truck_travel_minutes"][0][0] += 1.0
    if check_result(clean_case, raw, data, tampered, baseline, truck):
        raise AssertionError("modified receipt was accepted")
    checks["modified_numeric_receipt"] = "rejected"
    return checks


def run(repo, directory, development=False):
    started = datetime.now(timezone.utc).isoformat()
    full_wall, full_cpu = perf_counter_ns(), process_time_ns()
    cases = (DEV_CASE,) if development else EVALUATION_CASES
    results, controls_passed, failures = [], {}, []
    for case in cases:
        try:
            (raw, acquisition), acquisition_cost = clock(acquire, case, directory)
            data, pinned_metadata = clock(normalized, case, repo)
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            failures.append({"case": case, "stage": "acquire", "error": str(error)})
            continue
        (baseline, truck), baseline_cost = clock(conventional, case, raw, data)
        output, candidate_cost = clock(analyze, case, raw, data)
        valid, verification_cost = clock(check_result, case, raw, data, output, baseline, truck)
        if not valid:
            failures.append({"case": case, "stage": "independent_technical_check",
                             "error": "candidate disagrees with source or conventional reconciliation"})
        results.append({"acquisition": acquisition, "baseline": baseline, "challenger": output,
                        "independent_technical_check": valid,
                        "costs": {"acquisition": acquisition_cost, "pinned_metadata": pinned_metadata,
                                  "conventional": baseline_cost, "challenger": candidate_cost,
                                  "independent_check": verification_cost}})
        if case in (DEV_CASE, EVALUATION_CASES[-1]) and baseline["verdict"] == "SOURCE_READY" and valid:
            controls_passed.update(controls(directory, case, raw, data, output, baseline, truck))
        if output.get("counterexamples") and valid:
            tampered = deepcopy(output)
            tampered["counterexamples"][1] = tampered["counterexamples"][0]
            if check_result(case, raw, data, tampered, baseline, truck):
                raise AssertionError("duplicated witness was accepted")
            controls_passed[f"{case}_modified_counterexample"] = "rejected"
    recovered = [entry["challenger"]["case"] for entry in results
                 if entry["challenger"]["verdict"] == "RECOVERED_INPUT"]
    if not controls_passed:
        failures.append({"stage": "negative_controls", "error": "clean control unavailable"})
    return {"schema": "frontier/distribution-source-recovery/v1",
            "phase": "development" if development else "registered_public_evaluation",
            "registration": REGISTRATION, "evidence_revision": EVIDENCE_REVISION,
            "executable_revision": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
            "started_at_utc": started, "cases": results, "failures": failures,
            "recovered_case_ids": recovered, "negative_controls": controls_passed,
            "verdict": "ABSTAIN" if failures or not recovered else "INSUFFICIENT EVIDENCE",
            "limits": ["Source recovery only", "Public findings and case IDs",
                       "No independently administered confirmation or beneficiary approval",
                       "Imports, installation, downstream dispatch, people, and maintenance unmeasured"],
            "resources": {"platform": platform.platform(), "python": platform.python_version(),
                          "numpy": np.__version__, "scipy": scipy.__version__,
                          "elapsed_ms_after_import": (perf_counter_ns() - full_wall) / 1e6,
                          "cpu_ms_after_import": (process_time_ns() - full_cpu) / 1e6,
                          "peak_process_rss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                          "peak_rss_unit": "byte" if platform.system() == "Darwin" else "KiB"}}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--source-cache", required=True, type=Path)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--development", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.repo, args.source_cache, args.development), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
