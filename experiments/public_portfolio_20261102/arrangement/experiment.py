from copy import deepcopy
from pathlib import Path
import argparse
import hashlib
import json
import math
import time
import numpy as np
from scipy.stats import ncx2
from .orbital import (cw_transition, generator, reconstruct_transition, collision_bound,
                      disk_probability, physical_options, select_contract, servicing_transfer,
                      numerical_replay, participant_response)


def base_request():
    return {"mean_m": [20., 10.], "cov_m2": [[400., 50.], [50., 100.]],
            "radius_m": 5., "execution_bound_m": 2., "n_rad_s": 0.001078,
            "lead_s": 3600., "actions_mps": [[-.02, -.01, 0., .01, .02], [-.02, -.01, 0., .01, .02]],
            "fuel_cost_usd_per_mps": [600000., 12000.], "fixed_burn_usd": [1200., 50.],
            "asset_loss_usd": [5e7, 1000.], "cash_usd": [100000., 10000.],
            "platform_fee_usd": 100., "transfer_grid_usd": [-1000., -500., 0., 100., 250., 500., 1000., 2500., 5000.],
            "max_overlap_bound": 1e-4, "consent": [True, True], "units": "SI_USD",
            "linearization_scale_m": 500., "execution_default": False}


def digest_sources():
    root = Path(__file__).parent
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob("*.py"))}


def run_experiment(output_dir):
    started, cpu = time.perf_counter(), time.process_time()
    protocol = json.loads(Path(__file__).with_name("PREREGISTRATION.json").read_text())
    rng = np.random.default_rng(protocol["confirmation_seed"])
    dynamics = []
    risk = []
    for index in range(24):
        n, t = rng.uniform(.0008, .0014), rng.uniform(0, 14400)
        f = cw_transition(n, t)
        reference = reconstruct_transition(n, t)
        dynamics.append({"case": index, "n": n, "t": t,
                         "matrix_max_error": float(np.max(np.abs(f-reference))),
                         "semigroup_max_error": float(np.max(np.abs(f-cw_transition(n, t/2)@cw_transition(n, t/2))))})
        theta = rng.uniform(-math.pi, math.pi)
        rotation = np.array([[math.cos(theta), -math.sin(theta)], [math.sin(theta), math.cos(theta)]])
        covariance = rotation@np.diag(rng.uniform(25., 2500., 2))@rotation.T
        mean = rng.uniform(-120., 120., 2)
        radius = rng.uniform(1., 10.)
        exact = disk_probability(mean, covariance, radius)
        bound = collision_bound(mean, covariance, radius)
        risk.append({"case": index, "integrated_probability": exact, "upper_bound": bound,
                     "bound_valid": bool(exact <= bound+1e-10)})
    limiting = []
    for sigma, radius in [(10., 5.), (20., 2.), (50., 10.)]:
        exact = disk_probability([0., 0.], np.eye(2)*sigma*sigma, radius)
        analytic = float(ncx2.cdf(radius*radius/(sigma*sigma), 2, 0))
        limiting.append({"isotropic_integral": exact, "analytic": analytic,
                         "error": abs(exact-analytic)})
    req = base_request()
    factorial = {name: select_contract(req, tech, arrange) for name, tech, arrange in [
        ("original", False, False), ("technical_only", True, False),
        ("arrangement_only", False, True), ("joint", True, True)]}
    ordinary = select_contract(req, True, True)
    private_types = []
    for actual_rate in [12000., 300000., 1000000.]:
        private = deepcopy(req)
        private["fuel_cost_usd_per_mps"][1] = actual_rate
        private_types.append({"B_actual_fuel_rate_usd_per_mps": actual_rate,
                              "response": participant_response(factorial["joint"], private)})
    fee_frontier = []
    for fee in [0., 100., 500., 1000., 2500., 5000., 10000.]:
        case = deepcopy(req)
        case["platform_fee_usd"] = fee
        outcome = select_contract(case)
        fee_frontier.append({"fee_usd": fee, "accepted": outcome["accepted"],
                             "selected": outcome.get("selected")})
    negatives = {}
    for name, updates in {
        "no_demand": {"asset_loss_usd": [0., 0.]},
        "financing_refusal": {"cash_usd": [0., 0.]},
        "failed_execution_qualification": {"execution_default": True},
        "rival_free_same_capability": {"platform_fee_usd": 0.},
        "large_covariance": {"cov_m2": [[1e6, 0.], [0., 1e6]]},
    }.items():
        case = deepcopy(req)
        case.update(updates)
        negatives[name] = select_contract(case)
    rejected = {}
    for name, updates in {
        "non_spd": {"cov_m2": [[1., 2.], [2., 1.]]},
        "nonfinite": {"mean_m": [float("nan"), 0.]},
        "permission_withdrawal": {"consent": [True, False]},
        "wrong_units": {"units": "km"},
        "model_envelope": {"linearization_scale_m": 2000.},
    }.items():
        case = deepcopy(req)
        case.update(updates)
        try:
            select_contract(case)
            rejected[name] = False
        except ValueError:
            rejected[name] = True
    k1_manifest = {"retained": ["cw_transition", "collision_bound", "scoped_request_validation"],
                   "source_hashes": digest_sources(), "task": "two-party epoch separation and voluntary cost-sharing",
                   "limit": "not integrated encounter risk or flight clearance"}
    successors = []
    for case in range(12):
        n, duration = rng.uniform(.0008, .0014), rng.uniform(6000., 10000.)
        initial = rng.uniform(-250., 250., 6)
        initial[3:] = 0.
        target = np.array([500.+20*case, 30., 10., 0., 0., 0.])
        inherited = servicing_transfer(n, duration, initial, target)
        ordinary_reuse = servicing_transfer(n, duration, initial, target, cw_transition)
        fresh = servicing_transfer(n, duration, initial, target, reconstruct_transition)
        if inherited.get("burns_mps"):
            replay = numerical_replay(n, duration, initial, np.asarray(inherited["burns_mps"]))
            independent_error = float(np.linalg.norm(replay-target))
        else:
            independent_error = None
        f = cw_transition(n, duration)
        direct_one_burn = np.linalg.lstsq(f[:, 3:], target-f@initial, rcond=None)[0]
        no_new_construction_residual = float(np.linalg.norm(f@initial+f[:, 3:]@direct_one_burn-target))
        successors.append({"case": case, "inherited": inherited, "ordinary_reuse": ordinary_reuse,
                           "no_inheritance_direct_specialist": fresh,
                           "ordinary_reuse_tie": bool(inherited == ordinary_reuse),
                           "specialist_fuel_difference": abs(inherited.get("fuel_mps", 0)-fresh.get("fuel_mps", 0)),
                           "independent_ode_endpoint_error": independent_error,
                           "no_new_two_burn_construction_residual": no_new_construction_residual})
    checks = {
        "cw_matches_exponential": max(x["matrix_max_error"] for x in dynamics) < 1e-7,
        "cw_semigroup": max(x["semigroup_max_error"] for x in dynamics) < 1e-7,
        "all_probability_bounds": all(x["bound_valid"] for x in risk),
        "isotropic_limit": max(x["error"] for x in limiting) < 1e-10,
        "invalid_inputs_refused": all(rejected.values()),
        "no_demand_refused": not negatives["no_demand"]["accepted"],
        "no_cash_refused": not negatives["financing_refusal"]["accepted"],
        "default_refused": not negatives["failed_execution_qualification"]["accepted"],
        "conventional_k1_tie": ordinary == factorial["joint"],
        "ordinary_k2_tie": all(x["ordinary_reuse_tie"] for x in successors),
        "independent_k2_replay": all(x["independent_ode_endpoint_error"] is not None and x["independent_ode_endpoint_error"] < 1e-5 for x in successors),
    }
    result = {"schema": "public-portfolio-arrangement-result/v1", "scope": "synthetic linear-orbit mathematics and authored finite private-type economic cases only",
              "protocol_sha256": hashlib.sha256(Path(__file__).with_name("PREREGISTRATION.json").read_bytes()).hexdigest(),
              "source_sha256": digest_sources(), "dynamics": dynamics, "risk": risk, "limiting_cases": limiting,
              "factorial": factorial, "ordinary_unrestricted": ordinary, "private_type_response": private_types,
              "fee_frontier": fee_frontier,
              "negative_cases": negatives, "invalid_inputs": rejected, "k1_manifest": k1_manifest,
              "k2": successors, "checks": checks, "engineering_checks_pass": all(checks.values()),
              "verdicts": {"computational_artifact": "constructed_pending_independent_verifier",
                           "physical_validation": "unresolved_not_run", "retained_content": "ordinary_reuse_tie",
                           "better_discovery": "not_demonstrated", "blue_sky_residual": "unresolved_existing_CREAM_complete_alternative",
                           "market_validation": "unresolved_no_real_consent_or_revenue",
                           "native_profit": "delegated_to_canonical_portfolio_account_no_local_ledger"},
              "measured_resources": {"cpu_seconds": time.process_time()-cpu, "wall_seconds": time.perf_counter()-started,
                                     "actual_incremental_spending_usd": 0, "model_tokens": None,
                                     "actual_model_or_host_bill": "unknown", "human_intervention_since_assignment_minutes": 0}}
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=False)
    (out/"RESULTS.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    (out/"K1_MANIFEST.json").write_text(json.dumps(k1_manifest, indent=2)+"\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    args = p.parse_args()
    result = run_experiment(args.output)
    print(json.dumps({"checks": result["checks"], "verdicts": result["verdicts"]}, indent=2))
