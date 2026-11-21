"""Independent ideal-shot necessary AND sufficient bounds for the anchored physical receiver.

This is a bound for an i.i.d. mathematical outcome model, not quantum hardware
calibration, executable commercial operation, or an absolute shot cost forecast.
"""
from __future__ import annotations

import hashlib
import json
import math
from decimal import Decimal, ROUND_CEILING, localcontext
import resource
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OWNER = ROOT / "research" / "frontier_qec_transfer"
FRAME = ROOT / "research" / "frontier_framefix225"
sys.path.insert(0, str(OWNER))
sys.path.insert(0, str(OWNER / "fixtures"))
sys.path.insert(0, str(FRAME))

from framefix import build_canonical, pinned_blob_sha1
from noise_experiment import NoiseExperiment
from public_fixtures import pollatsek_ruskai_7, shor_9
from second_public_fixtures import pauli_hypotheses

PROTOCOL = HERE / "PROTOCOL.json"
PROTOCOL_COMMIT = "a5e4bcb055fd51fcb9fdee99f8b06948dbd84dfb"
TARGET = 0.05
NOISE_LEVELS = (0.0, 0.01, 0.05)
NUMERICAL_TV_FLOOR = 1e-9
NUMERICAL_BC_CEILING = 1e-12
MAX_RELIABLE_REPORTED_SHOTS = 10**12


def blob_hash(path: Path) -> str:
    return pinned_blob_sha1(path)


def verify_pins() -> dict:
    protocol = json.loads(PROTOCOL.read_text())
    if protocol["error_target"] != TARGET or tuple(protocol["scenario_noise_fractions"]) != NOISE_LEVELS:
        raise ValueError("registered protocol differs from executor")
    found = {}
    for filename, pinned in protocol["pinned_file_blob_sha1"].items():
        current = blob_hash(ROOT / filename)
        if current != pinned:
            raise ValueError(f"pinned owner source changed: {filename}")
        found[filename] = current
    return found


def validate_probabilities(p, q) -> tuple[np.ndarray, np.ndarray]:
    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    if p.ndim != 1 or p.shape != q.shape or not p.size:
        raise ValueError("invalid probability shape")
    if not np.all(np.isfinite(p)) or not np.all(np.isfinite(q)):
        raise ValueError("nonfinite probability")
    if min(float(p.min()), float(q.min())) < -1e-12:
        raise ValueError("negative probability")
    if max(abs(float(p.sum()) - 1), abs(float(q.sum()) - 1)) > 2e-8:
        raise ValueError("unnormalized distribution")
    # Avoid small floating-point sums > 1 before fidelity arithmetic.
    p = np.maximum(0.0, p)
    q = np.maximum(0.0, q)
    return p / p.sum(), q / q.sum()


def response_noise(p: np.ndarray, epsilon: float):
    if not (0 <= epsilon < 1):
        raise ValueError("invalid registered uniform-response noise")
    return (1-epsilon)*p + epsilon/len(p)


def bounded_n(bc: float, numerator: float, *, necessary: bool):
    """Directed high-precision ceil: never round a sufficient guarantee downward.

    The bound is conditional on the observed floating-point overlap and ideal
    i.i.d. model. One-ULP directed adjustments avoid falsely tight thresholds;
    they do not calibrate the real-world distribution or numerical shot costs.
    """
    if not (0 < bc < 1 and 0 < numerator < 1):
        raise ValueError("invalid distinguishable fidelity or bound")
    adjusted = math.nextafter(bc, 0.0 if necessary else 1.0)
    if not (0 < adjusted < 1):
        return {"count": None, "reason": "insufficient_numerical_precision"}
    with localcontext() as ctx:
        ctx.prec = 70
        threshold = Decimal(str(numerator)).ln() / (Decimal(2 if necessary else 1) * Decimal.from_float(adjusted).ln())
        if not threshold.is_finite() or threshold > MAX_RELIABLE_REPORTED_SHOTS:
            return {"count": None, "reason": "exceeds_reliable_reportable_1e12_shots"}
        value = int(threshold.to_integral_value(rounding=ROUND_CEILING))
    return {"count": max(1, value), "reason": None}


def pair_stats(p, q, helstrom_error: float, epsilon: float):
    p,q = validate_probabilities(p,q)
    p = response_noise(p, epsilon)
    q = response_noise(q, epsilon)
    p,q = validate_probabilities(p,q)
    bc = float(np.sqrt(p*q).sum())
    tv = float(np.abs(p-q).sum()/2)
    if bc > 1+2e-8 or bc < -2e-8:
        raise ValueError("invalid Bhattacharyya overlap")
    bc = min(1.0, max(0.0, bc))
    frame_error = (1-tv)/2
    if frame_error < helstrom_error - 2e-8:
        raise AssertionError("fixed receiver outperforms ideal quantum Helstrom")
    result = {
        "tv":tv,"bc":bc,
        "single_shot_error_fixed_receiver":frame_error,
        "ideal_known_pair_helstrom_error":helstrom_error,
        "necessary_shots":None, "sufficient_shots":None
    }
    if tv <= NUMERICAL_TV_FLOOR:
        result["status"] = "indistinguishable_within_registered_numerical_tolerance"
    elif 1-bc <= NUMERICAL_BC_CEILING:
        result["status"] = "numerically_unresolved_finite_shots"
    elif bc <= 0:
        result.update(status="finite", necessary_shots=1, sufficient_shots=1)
    else:
        necessary = bounded_n(bc, 4*TARGET*(1-TARGET), necessary=True)
        sufficient = bounded_n(bc, 2*TARGET, necessary=False)
        if necessary["count"] is not None and sufficient["count"] is not None:
            if not (1 <= necessary["count"] <= sufficient["count"]):
                raise AssertionError("invalid necessary/sufficient ordering")
            result.update(status="finite", necessary_shots=necessary["count"],
                          sufficient_shots=sufficient["count"])
        else:
            result["status"] = "exceeds_reliable_reportable_1e12_shots"
    return result


def helstrom_one_shot(rho, sigma):
    delta = rho - sigma
    if np.max(np.abs(delta-delta.conj().T)) > 2e-8:
        raise ValueError("nonhermitian density contrast")
    eig = np.linalg.eigvalsh((delta+delta.conj().T)/2)
    tv_quantum = float(np.abs(eig).sum()/2)
    if tv_quantum > 1+2e-8:
        raise ValueError("invalid quantum trace distance")
    return max(0.0, (1-min(1.0,tv_quantum))/2)


def evaluate_fixture(factory, expected_h, expected_pairs):
    start = time.perf_counter()
    qubits, code = factory()
    exp = NoiseExperiment(qubits, code, pauli_hypotheses(qubits))
    if exp.H != expected_h:
        raise AssertionError("changed hypothesis inventory")
    fixed = build_canonical(exp._recovery, exp._syndrome_states)
    response = np.asarray(fixed.response, dtype=float)
    if response.shape != (exp.syndrome_rank**2,expected_h):
        raise AssertionError("changed physical receiver inventory")
    states = fixed.syndrome_states
    pairs=[]
    for i in range(expected_h):
        for j in range(i+1,expected_h):
            ideal_error=helstrom_one_shot(states[i],states[j])
            observations=[pair_stats(response[:,i],response[:,j],ideal_error,e)
                          for e in NOISE_LEVELS]
            if any(observations[k+1]["tv"] > observations[k]["tv"]+2e-8
                   or observations[k+1]["bc"] < observations[k]["bc"]-2e-8
                   for k in range(len(observations)-1)):
                raise AssertionError("data-processing monotonicity failed")
            # Do not change identity or denominator when an error bound is unqualified.
            pairs.append({"i":i,"j":j,"noise_cases":observations})
    if len(pairs)!=expected_pairs:
        raise AssertionError("registered pair denominator changed")
    scenarios=[]
    for k,level in enumerate(NOISE_LEVELS):
        records=[p["noise_cases"][k] for p in pairs]
        finite=[r for r in records if r["status"]=="finite"]
        over=[r for r in records if r["status"]=="exceeds_reliable_reportable_1e12_shots"]
        scenarios.append({
            "uniform_response_noise_fraction":level,
            "pair_count":len(records),
            "finite_pairs":len(finite),
            "indistinguishable_pairs":sum(r["status"].startswith("indistinguishable") for r in records),
            "numerically_unresolved_pairs":sum(r["status"].startswith("numerically_unresolved") for r in records),
            "unreportably_large_pairs":len(over),
            "max_finite_necessary_shots":max((r["necessary_shots"] for r in finite),default=None),
            "max_finite_sufficient_shots":max((r["sufficient_shots"] for r in finite),default=None),
            "max_ideal_fixed_receiver_single_shot_error":max(r["single_shot_error_fixed_receiver"] for r in records),
            "max_ideal_known_pair_helstrom_error":max(r["ideal_known_pair_helstrom_error"] for r in records),
        })
    return {
        "fixture":factory.__name__, "qubits":qubits,
        "hypotheses":expected_h,"pairs":len(pairs),
        "physical_outcomes":response.shape[0], "scenarios":scenarios,
        "all_pair_scenarios":pairs,
        "elapsed_wall_seconds":time.perf_counter()-start
    }


def evaluate():
    pins = verify_pins()
    start = time.perf_counter()
    cases=[evaluate_fixture(pollatsek_ruskai_7,22,231),
           evaluate_fixture(shor_9,28,378)]
    if sum(c["pairs"] for c in cases)!=609 or sum(c["pairs"]*3 for c in cases)!=1827:
        raise AssertionError("registered denominator changed")
    usage=resource.getrusage(resource.RUSAGE_SELF)
    return {
        "schema":"frontier/framecost226/ideal-iid-shot-bounds/v1",
        "protocol_frozen_commit":PROTOCOL_COMMIT,
        "protocol_sha256":hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
        "pinned_source_git_blob_sha1":pins,
        "upstream_physical_receiver_head":"04767e2b7628e9e4b470c910fd7a3c3c03202135",
        "target_average_binary_error":TARGET,
        "fixed_uniform_noise_fractions":list(NOISE_LEVELS),
        "registered_pairs":609,"registered_pair_scenarios":1827,
        "cases":cases,
        "math_boundary":"Necessary and sufficient bounds for ideal i.i.d. syndrome POVM outcomes on known equally likely binary hypotheses, NOT a sufficient guarantee for an unknown mixture.",
        "strong_comparator":"Pair-specific Helstrom is ideal mathematical single-copy optimum for a known binary task, NOT a complete rival enterprise or a physically demonstrated receiver.",
        "hypothetical_noise_not_measured":True,
        "actual_physical_shots":0,"buyer_acceptances":0,
        "real_collected_revenue_USD":0,"real_complete_cost_profit_USD":None,
        "actual_host_and_model_billing_USD":None,
        "resource_telemetry":{"wall_seconds":time.perf_counter()-start,"self_user_cpu_seconds":usage.ru_utime,"self_system_cpu_seconds":usage.ru_stime},
        "decision":"HOLD_NO_DEPLOY"
    }


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        raise ValueError("will not overwrite evidence")
    result=evaluate()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n")
    for case in result["cases"]:
        print(case["fixture"],case["pairs"],"pairs",case["scenarios"])
    print("COMPLETE 1827 ideal-shot pair scenarios; NO DEPLOY, no economic inference")
