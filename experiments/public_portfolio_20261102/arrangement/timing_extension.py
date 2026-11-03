from pathlib import Path
import argparse
import hashlib
import json
import time
import numpy as np
from scipy.integrate import solve_ivp
from .orbital import cw_transition, generator, reconstruct_transition


def solve_timed_transfer(n, duration_s, initial, target, fractions, transition=cw_transition):
    initial, target = np.asarray(initial, float), np.asarray(target, float)
    if initial.shape != (6,) or target.shape != (6,) or not np.isfinite(initial).all() or not np.isfinite(target).all():
        raise ValueError("finite 6D SI endpoint states required")
    if max(np.linalg.norm(initial[:3]), np.linalg.norm(target[:3])) > 1500:
        raise ValueError("outside close-proximity state envelope")
    if not fractions or any(not np.isfinite(x) or not 0 < x <= 1 for x in fractions):
        raise ValueError("second impulse must occur within the mission")
    f = transition(n, duration_s)
    candidates = []
    for fraction in fractions:
        h = transition(n, duration_s*(1-fraction))
        a = np.column_stack([f[:, 3:], h[:, 3:]])
        condition = float(np.linalg.cond(a))
        if condition > 1e10:
            continue
        burns = np.linalg.solve(a, target-f@initial).reshape(2, 3)
        residual = float(np.linalg.norm(f@initial+a@burns.ravel()-target))
        fuel = float(sum(np.linalg.norm(b) for b in burns))
        candidates.append({"second_fraction": fraction, "burns_mps": burns.tolist(),
                           "fuel_mps": fuel, "endpoint_residual": residual,
                           "accepted": bool(fuel <= 5.0 and residual <= 1e-7), "condition": condition})
    if not candidates:
        return {"accepted": False, "reason": "all_finite_timing_systems_ill_conditioned", "systems_solved": 0}
    candidates.sort(key=lambda x: (x["fuel_mps"], x["second_fraction"]))
    return {**candidates[0], "systems_solved": len(candidates),
            "finite_timing_optimality_gap_mps": 0., "scope": "finite-grid minimum-delta-v linear endpoint design only"}


def replay_timed(n, duration, initial, result):
    state = np.asarray(initial, float).copy()
    fraction = result["second_fraction"]
    for burn, interval in zip(result["burns_mps"], [duration*fraction, duration*(1-fraction)]):
        state[3:] += burn
        if interval:
            state = solve_ivp(lambda t, y: generator(n)@y, (0, interval), state,
                              rtol=1e-11, atol=1e-11).y[:, -1]
    return state


def run_experiment(output_dir):
    started, cpu = time.perf_counter(), time.process_time()
    path = Path(__file__).parent
    protocol = json.loads((path/"TIMING_PREREGISTRATION.json").read_text())
    rng = np.random.default_rng(protocol["fresh_confirmation_seed"])
    records = []
    for case in range(12):
        n, duration = rng.uniform(.0008, .0014), rng.uniform(6000., 10000.)
        initial = rng.uniform(-250., 250., 6)
        initial[3:] = 0.
        target = np.array([500.+20*case, 30., 10., 0., 0., 0.])
        inherited = solve_timed_transfer(n, duration, initial, target, protocol["second_burn_fractions"])
        fixed = solve_timed_transfer(n, duration, initial, target, [.5])
        ordinary = solve_timed_transfer(n, duration, initial, target, protocol["second_burn_fractions"])
        fresh = solve_timed_transfer(n, duration, initial, target, protocol["second_burn_fractions"], reconstruct_transition)
        replay = replay_timed(n, duration, initial, inherited)
        records.append({"case": case, "n_rad_s": n, "duration_s": duration, "initial_state": initial.tolist(),
                        "target_state": target.tolist(), "timing_construction": inherited,
                        "inherited_fixed_half_time": fixed, "equal_content_ordinary_timing": ordinary,
                        "fresh_direct_specialist": fresh,
                        "numerical_replay_endpoint_error": float(np.linalg.norm(replay-target)),
                        "ordinary_tie": inherited == ordinary,
                        "direct_specialist_fuel_difference": abs(inherited["fuel_mps"]-fresh["fuel_mps"])})
    invalid = {}
    for key, fractions in [("after_mission", [1.1]), ("zero_or_before", [0.]), ("nonfinite", [float("nan")])]:
        try:
            solve_timed_transfer(.001, 7200., np.zeros(6), np.array([500., 0., 0., 0., 0., 0.]), fractions)
            invalid[key] = False
        except ValueError:
            invalid[key] = True
    checks = {"all_replay_endpoint_tolerance": max(r["numerical_replay_endpoint_error"] for r in records) < 1e-5,
              "ordinary_equal_content_tie": all(r["ordinary_tie"] for r in records),
              "direct_specialist_tie_tolerance": max(r["direct_specialist_fuel_difference"] for r in records) < 1e-7,
              "no_threshold_relaxation": all(r["timing_construction"]["accepted"] == (r["timing_construction"]["fuel_mps"] <= 5. and r["timing_construction"]["endpoint_residual"] <= 1e-7) for r in records),
              "invalid_timing_refused": all(invalid.values())}
    result = {"schema": "arrangement-timing-extension-result/v1", "earlier_attempt": "evidence-confirmation-01/RESULTS.json",
              "earlier_negative": "0/12 fixed-half-time endpoints satisfied total delta-v <=5m/s; 0/4 contracts accepted",
              "protocol_sha256": hashlib.sha256((path/"TIMING_PREREGISTRATION.json").read_bytes()).hexdigest(),
              "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [path/"orbital.py", path/"timing_extension.py"]},
              "records": records, "checks": checks,
              "counts": {"fresh_cases": len(records), "timing_accepted": sum(r["timing_construction"]["accepted"] for r in records),
                         "fixed_half_time_accepted": sum(r["inherited_fixed_half_time"]["accepted"] for r in records)},
              "limits": ["no continuous corridor clearance", "no physical orbit validation", "classical unrestricted timing specialist tie",
                         "no new commercial acceptance", "original failed accounts/attempts not reset"],
              "resources": {"cpu_seconds": time.process_time()-cpu, "wall_seconds": time.perf_counter()-started,
                            "incremental_spending_usd": 0, "human_intervention_minutes_after_assignment": 0,
                            "actual_model_host_billing": "unknown"}}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=False)
    (out/"RESULTS.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    args = p.parse_args()
    result = run_experiment(args.output)
    print(json.dumps({"counts": result["counts"], "checks": result["checks"]}, indent=2))
