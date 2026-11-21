"""Run the frozen two-fixture, three-gauge physical measurement comparison."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import resource
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWNER = ROOT / "research" / "frontier_qec_transfer"
sys.path.insert(0, str(OWNER))
sys.path.insert(0, str(OWNER / "fixtures"))

from framefix import (
    pinned_blob_sha1, build_canonical, apply_syndrome_gauge, fixed_unitary)
from noise_experiment import NoiseExperiment
from public_fixtures import pollatsek_ruskai_7, shor_9
from second_public_fixtures import pauli_hypotheses

PINS = {
    "recovery.py": "6c8092bf132f9f218ca4c1b074a6c9b93d9b2b69",
    "noise_experiment.py": "434278fa64d4d7e90cb6a3117f5afdfe8e5bc40b",
    "fixtures/public_fixtures.py": "75be45ee4581eba1991ac4e8b2e5690084796f45",
    "fixtures/second_public_fixtures.py": "866b170844f751731d66cc4f76bbdb427f8d53cc",
}
SEEDS = (1, 7, 257)
LIMIT = 2e-8


def fixed_case(factory, expected_h, expected_rank):
    started = time.perf_counter()
    n, words = factory()
    exp = NoiseExperiment(n, words, pauli_hypotheses(n))
    if exp.H != expected_h or exp.rank != expected_rank:
        raise AssertionError("unexpected source hypothesis inventory")
    baseline = build_canonical(exp._recovery, exp._syndrome_states)
    old = exp.response_matrix()
    basepairs = baseline.pair_distances()
    if len(basepairs) != exp.H*(exp.H-1)//2:
        raise AssertionError("incomplete fixed pair inventory")
    variants = []
    for seed in SEEDS:
        Q = fixed_unitary(exp.syndrome_rank, seed)
        Rrot, Srot = apply_syndrome_gauge(
            exp._recovery, exp._syndrome_states, Q)
        frame = build_canonical(Rrot, Srot)
        response_delta = float(np.max(np.abs(frame.response-baseline.response)))
        physical_delta = float(np.max(np.abs(
            frame.physical_operators-baseline.physical_operators)))
        perturbed_old = np.einsum(
            "oi,hij,oj->oh", exp._bras, Srot, exp._bras.conj(),
            optimize=True).real
        old_difference = float(np.max(np.abs(old-perturbed_old)))
        pairs = frame.pair_distances()
        pair_drift = max(abs(a[1]-b[1]) for a,b in zip(basepairs,pairs))
        if max(response_delta, physical_delta, pair_drift) > LIMIT:
            raise AssertionError(
                f"physical gauge invariance FAILED in {factory.__name__} seed {seed}")
        variants.append({
            "seed": seed, "max_canonical_response_delta": response_delta,
            "max_canonical_physical_operator_delta": physical_delta,
            "max_pair_tv_delta": pair_drift,
            "old_coordinate_frame_response_delta": old_difference
        })
    if max(v["old_coordinate_frame_response_delta"] for v in variants) <= 1e-4:
        raise AssertionError("negative control did not expose a varying physical frame")
    return {
        "fixture": factory.__name__,
        "qubits": n,
        "hypotheses": exp.H,
        "registered_pairs": len(basepairs),
        "numerically_indistinguishable_pairs": sum(tv<=1e-9 for _,tv in basepairs),
        "owner_available_rank": exp.rank,
        "canonical_response_rank": int(np.linalg.matrix_rank(baseline.response)),
        "physical_measurement_outcomes": baseline.physical_operators.shape[0],
        "physical_completeness_residual": baseline.physical_completeness_residual,
        "frame_normalization_residual": baseline.frame_residual,
        "max_hypothesis_normalization_error": baseline.max_column_error,
        "physical_gauge_trials": variants,
        "pair_total_variation": [
            {"i": i, "j": j, "total_variation": tv}
            for (i,j), tv in basepairs
        ],
        "elapsed_wall_seconds_this_process": time.perf_counter()-started,
    }


def run():
    owner_hashes = {
        path: pinned_blob_sha1(OWNER / path) for path in PINS
    }
    if owner_hashes != PINS:
        raise ValueError("pinned scientific source identity changed")
    started = time.perf_counter()
    case1 = fixed_case(pollatsek_ruskai_7, 22, 22)
    case2 = fixed_case(shor_9, 28, 22)
    if sum(x["registered_pairs"] for x in (case1,case2)) != 609:
        raise AssertionError("missing registered pairs")
    cpu = resource.getrusage(resource.RUSAGE_SELF)
    return {
        "schema": "frontier/framefix225/gauge-qualification/v1",
        "frozen_preimplementation_protocol_commit":
            "9f2eb4d722d250cfe5211c7de6ac3e50bfdf6a10",
        "owner_source": "7501e83ea37b0d933e2318be2099b37308de0574",
        "parent_pr525_source": "e18e40c3952a74228e7b6071d35d2c668c9e2041",
        "exact_owner_source_git_blob_sha1": owner_hashes,
        "fixed_gauge_seeds": list(SEEDS),
        "fixed_pairs": 609,
        "cases": [case1,case2],
        "process_resource_telemetry": {
            "wall_seconds": time.perf_counter()-started,
            "self_user_cpu_seconds": cpu.ru_utime,
            "self_system_cpu_seconds": cpu.ru_stime,
        },
        "physical_hardware_shots": 0,
        "real_buyers": 0,
        "real_cash_collected_USD": 0,
        "host_and_model_bill_USD": None,
        "decision": "RESEARCH_ONLY_NO_DEPLOY",
        "scope": "Physically anchored mathematical gauge-invariance and all-pair inventory; NOT hardware calibration, realized economic value or native financial authority"
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("refuse to overwrite evidence")
    result = run()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    for case in result["cases"]:
        print(case["fixture"],case["registered_pairs"],"pairs",
              case["numerically_indistinguishable_pairs"],"indistinguishable",
              "max gauge response delta",
              max(x["max_canonical_response_delta"]
                  for x in case["physical_gauge_trials"]))
    print("Research-only gauge-invariant design; no physical or economic claim.")


if __name__ == "__main__":
    main()
