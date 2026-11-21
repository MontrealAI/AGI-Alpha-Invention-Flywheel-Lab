"""Independent finite-shot feasibility gate for the existing nondestructive noise tool.

Frozen protocol: PROTOCOL.json at Git commit 52d85e0730c94901bae913dc76ebb237eb917273.
No changes to underlying recovery, noise instrument, native financial accounts or outcomes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "research" / "frontier_qec_transfer"
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(SOURCE / "fixtures"))

from noise_experiment import NoiseExperiment
from second_public_fixtures import pauli_hypotheses
from public_fixtures import pollatsek_ruskai_7, shor_9

ALPHA = 0.05
BUDGETS = (100, 1000, 10000, 1000000)
TV_RESOLUTION = 1e-9
SOURCE_FILES = ("recovery.py", "noise_experiment.py",
                "fixtures/public_fixtures.py", "fixtures/second_public_fixtures.py")


def checked_distribution(p):
    """Reject invalid probabilities; clip only floating point negative noise."""
    p = np.asarray(p, dtype=float)
    if p.ndim != 1 or not len(p) or not np.all(np.isfinite(p)):
        raise ValueError("invalid probability vector")
    if p.min() < -2e-8 or abs(float(p.sum()) - 1) > 2e-8:
        raise ValueError("unphysical response column")
    p = np.maximum(p, 0.0)
    return p / math.fsum(float(v) for v in p)


def hellinger_squared(p, q):
    """1-Bhattacharyya coefficient via a stable sum of squares."""
    p, q = checked_distribution(p), checked_distribution(q)
    return min(1.0, max(0.0, 0.5 * math.fsum(
        float(v) for v in (np.sqrt(p) - np.sqrt(q)) ** 2)))


def required_shots_necessary(h2, alpha=ALPHA):
    """Necessary, not sufficient, N for equal-prior Bayes risk <= alpha."""
    if not (0 < alpha < 0.5) or not (0 <= h2 <= 1):
        raise ValueError("invalid bound parameters")
    if h2 == 0:
        return None  # indistinguishable at any sample count
    if h2 == 1:
        return 1
    return max(1, math.ceil(math.log(4 * alpha * (1 - alpha)) /
                            (2 * math.log1p(-h2))))


def risk_lower_bound(h2, n):
    """Optimal equal-prior error >= (1-sqrt(1-BC**(2*n)))/2."""
    if n < 1 or not (0 <= h2 <= 1):
        raise ValueError("invalid shot count or squared Hellinger distance")
    if h2 == 0:
        return 0.5
    if h2 == 1:
        return 0.0
    one_minus_power = -math.expm1(2 * n * math.log1p(-h2))
    return 0.5 * (1 - math.sqrt(min(1.0, max(0.0, one_minus_power))))


def frame_one_shot_error(p, q):
    return 0.5 * (1 - .5 * float(np.abs(p - q).sum()))


def helstrom_one_shot_error(rho, sigma):
    """Best pair-specific syndrome measurement; not a deployed receiver."""
    rho, sigma = np.asarray(rho, complex), np.asarray(sigma, complex)
    for state in (rho, sigma):
        if (state.shape != rho.shape or
            np.max(abs(state - state.conj().T)) > 2e-8 or
            abs(np.trace(state) - 1) > 2e-8):
            raise ValueError("invalid syndrome density matrix")
    eigenvalues = np.linalg.eigvalsh((rho - sigma + (rho - sigma).conj().T)/2)
    return 0.5 * (1 - .5 * float(np.abs(eigenvalues).sum()))


def fixture_report(factory):
    n, words = factory()
    experiment = NoiseExperiment(n, words, pauli_hypotheses(n))
    a = np.asarray(experiment.response_matrix(), float)
    named = experiment.hypothesis_names
    states = np.asarray(experiment._syndrome_states, complex)
    columns = [checked_distribution(a[:,i]) for i in range(len(named))]
    pairs = []
    for i in range(len(named)):
        for j in range(i + 1, len(named)):
            p, q = columns[i], columns[j]
            tv = 0.5 * float(np.abs(p - q).sum())
            h2 = hellinger_squared(p, q)
            frame_error = frame_one_shot_error(p, q)
            optimum = helstrom_one_shot_error(states[i], states[j])
            if optimum > frame_error + 2e-8:
                raise AssertionError("pair-specific Helstrom optimum worse than frame")
            pairs.append({
                "i": i, "j": j, "names": [named[i], named[j]],
                "total_variation": tv,
                "hellinger_squared": h2,
                "frame_error_one_shot": frame_error,
                "helstrom_error_one_shot": optimum,
                "numerically_distinguishable": tv > TV_RESOLUTION,
                "necessary_shots_for_5pct_risk": (
                    required_shots_necessary(h2) if tv > TV_RESOLUTION else None),
            })
    eligible = [p for p in pairs if p["numerically_distinguishable"]]
    if not eligible:
        raise AssertionError("zero distinguishable pairs in fixed fixture")
    hardest = min(eligible, key=lambda p: (p["hellinger_squared"],p["i"],p["j"]))
    result = {
        "code": factory.__name__,
        "hypotheses": len(named),
        "measurement_outcomes": len(experiment.measurement_operators()),
        "rank": experiment.identifiability()["rank"],
        "realized_povm_shape": list(experiment._operators.shape),
        "realized_povm_sha256": hashlib.sha256(
            np.ascontiguousarray(experiment._operators, dtype=np.complex128).tobytes()
        ).hexdigest(),
        "realized_response_sha256": hashlib.sha256(
            np.ascontiguousarray(a, dtype=np.float64).tobytes()
        ).hexdigest(),
        "realization_warning": ("A source hash does not freeze a degenerate syndrome "
                                "eigenbasis or the physical POVM constructed from it; "
                                "shot estimates apply only to this realized POVM."),
        "unique_mixture": experiment.identifiability()["unique"],
        "pair_count": len(pairs),
        "numerically_indistinguishable_pairs": len(pairs)-len(eligible),
        "hardest_distinguishable_pair": hardest,
        "necessary_risk_lower_bounds_by_shots": {
            str(nshots): risk_lower_bound(hardest["hellinger_squared"], nshots)
            for nshots in BUDGETS
        },
        "pairs": pairs,
    }
    return result


def run():
    return {
        "schema": "frontier/shotgate224/measured-mathematical-bounds/v1",
        "frozen_protocol_commit": "52d85e0730c94901bae913dc76ebb237eb917273",
        "qualified_owner_source_commit": "7501e83ea37b0d933e2318be2099b37308de0574",
        "source_sha256": {
            f: hashlib.sha256((SOURCE / f).read_bytes()).hexdigest() for f in SOURCE_FILES
        },
        "target_equal_prior_average_error": ALPHA,
        "shot_budgets": list(BUDGETS),
        "cases": [fixture_report(f) for f in (pollatsek_ruskai_7, shor_9)],
        "scope": ("Exact-probability mathematical necessary-shot lower bounds for "
                  "the evidenced POVM byte identity, NOT source-invariant shot claims, "
                  "sufficient sample sizes, physical receivers or economic findings."),
        "decision": "RESEARCH_ONLY_NO_DEPLOY",
        "actual_hardware_shots": 0,
        "real_customers": 0,
        "new_revenue": 0,
        "actual_host_model_bill_USD": None
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError("refuse to overwrite existing evidence")
    result = run()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    for case in result["cases"]:
        top = case["hardest_distinguishable_pair"]
        print(f'{case["code"]}: {case["pair_count"]} pairs; '
              f'{case["numerically_indistinguishable_pairs"]} numerically indistinguishable; '
              f'hardest {top["names"]}, necessary N>={top["necessary_shots_for_5pct_risk"]}')
    print("Mathematical necessary condition only; no physical/economic qualification.")


if __name__ == "__main__":
    main()
