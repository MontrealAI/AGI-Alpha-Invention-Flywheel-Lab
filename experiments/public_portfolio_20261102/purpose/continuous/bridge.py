from __future__ import annotations

from fractions import Fraction
from itertools import product
from pathlib import Path
from time import perf_counter, process_time
import argparse
import hashlib
import importlib.util
import json

import numpy as np
from scipy.integrate import solve_ivp
from scipy.io import loadmat


EXPECTED = {
    "Specifications.txt": "decb62879f7af779e44e3165d9c11425559be63e1c2265e12d26fdf498fa4f01",
    "dynamicsACC.m": "7addd66be8a8b9b730e30e4581cfa77abf7a8f38c35eb55fd706a9f159672fcc",
    "controller_5_20.mat": "730324c2fcc980f7123c186be458034520180a67e84cafe5973f8daf7cc42f3e"
}
INITIAL = [(90.0, 110.0), (32.0, 32.2), (0.0, 0.0), (10.0, 11.0), (30.0, 30.2), (0.0, 0.0)]


def load_network(benchmark_root):
    directory = Path(benchmark_root) / "benchmarks" / "ACC"
    actual = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in EXPECTED}
    if actual != EXPECTED:
        raise ValueError("pinned benchmark input mismatch")
    data = loadmat(directory / "controller_5_20.mat")
    weights = [np.asarray(w, dtype=np.float64) for w in data["W"].reshape(-1)]
    biases = [np.asarray(b, dtype=np.float64).reshape(-1) for b in data["b"].reshape(-1)]
    activations = [str(x).strip() for x in data["act_fcns"].reshape(-1)]
    if len(weights) != 6 or activations != ["relu"] * 5 + ["linear"]:
        raise ValueError("unqualified network architecture")
    if weights[0].shape != (20, 5) or weights[-1].shape != (1, 20):
        raise ValueError("unexpected network shape")
    return weights, biases, actual


def network_numpy(inputs, weights, biases):
    value = np.asarray(inputs, dtype=np.float64)
    for index, (weight, bias) in enumerate(zip(weights, biases)):
        value = weight @ value + bias
        if index < len(weights) - 1:
            value = np.maximum(value, 0.0)
    return float(value[0])


def network_scalar(inputs, weights, biases):
    value = list(map(float, inputs))
    for index, (weight, bias) in enumerate(zip(weights, biases)):
        value = [float(b) + sum(float(w) * x for w, x in zip(row, value)) for row, b in zip(weight, bias)]
        if index < len(weights) - 1:
            value = [max(0.0, x) for x in value]
    return value[0]


def controller_inputs(state):
    return [30.0, 1.4, state[4], state[0] - state[3], state[1] - state[4]]


def benchmark_rhs(time, state, command):
    x_lead, v_lead, a_lead, x_ego, v_ego, a_ego = state
    return np.array([v_lead, a_lead, -2.0 * a_lead - 4.0 - 0.0001 * v_lead ** 2, v_ego, a_ego, -2.0 * a_ego + 2.0 * command - 0.0001 * v_ego ** 2])


def conventional_rhs(time, state, command):
    rates = []
    for offset, control in ((0, -2.0), (3, command)):
        position, velocity, acceleration = state[offset:offset + 3]
        rates.extend((velocity, acceleration, 2.0 * (control - acceleration) - velocity * velocity / 10000.0))
    return np.array(rates)


def simulate(initial, weights, biases, *, method="DOP853", max_step=0.01, scalar=False, fallback=False):
    state = np.asarray(initial, dtype=float)
    times, states, commands = [0.0], [state.copy()], []
    implementation = network_scalar if scalar else network_numpy
    rhs = conventional_rhs if scalar else benchmark_rhs
    for sample in range(50):
        command = -2.0 if fallback else implementation(controller_inputs(state), weights, biases)
        commands.append(command)
        start, end = sample / 10.0, (sample + 1) / 10.0
        result = solve_ivp(rhs, (start, end), state, args=(command,), method=method, rtol=1e-10, atol=1e-12, max_step=max_step, t_eval=np.linspace(start, end, 21)[1:])
        if not result.success or not np.isfinite(result.y).all():
            raise ValueError("point integrator failed; not a safety pass")
        state = result.y[:, -1]
        times.extend(result.t.tolist())
        states.extend(result.y.T.tolist())
    trajectory = np.asarray(states)
    margin = trajectory[:, 0] - trajectory[:, 3] - 10.0 - 1.4 * trajectory[:, 4]
    return {"initial": list(map(float, initial)), "sampled_minimum_margin": float(margin.min()), "min_time": float(times[int(margin.argmin())]), "final_speed_ego": float(trajectory[-1, 4]), "final_state": state.tolist(), "command_range": [float(min(commands)), float(max(commands))], "sampled_margin_nonnegative": bool((margin >= 0.0).all()), "times": times, "states": trajectory.tolist()}


def analytic_fallback_certificate():
    q = Fraction
    horizon, mu, vmax = q(5), q(1, 10000), q(161, 5)
    acceleration_bound = q(2) + mu * vmax * vmax / 2
    minimum_speed = q(30) - acceleration_bound * horizon
    relative_velocity_fraction = 1 - mu * (2 * vmax) * horizon / 2
    minimum_margin = q(90) - q(11) - q(10) - q(7, 5) * q(151, 5)
    validity = minimum_speed > 0 and relative_velocity_fraction > 0 and minimum_margin >= 0
    return {"controller": "conventional fixed command ego=-2, equal to lead command", "whole_initial_box_covered": validity, "exact_lower_margin": str(minimum_margin), "exact_acceleration_absolute_bound": str(acceleration_bound), "exact_positive_speed_lower_bound": str(minimum_speed), "exact_relative_velocity_fraction_lower_bound": str(relative_velocity_fraction), "derivation": "With v in [0,V], a remains in [-(2+mu*V^2/2),0], preserving positive nonincreasing v over 5s. Before any hypothetical first zero of w=vL-vE, z=w' obeys z'=-2z-mu*(vL+vE)*w, z(0)=0; hence w(t)>=w(0)*(1-mu*2V*t/2)>0. Thus distance is nondecreasing and ego speed nonincreasing, so margin never falls below its initial minimum.", "scope": "An analytic safety witness for supplied ODE under fixed braking. It is neither original neural-controller verification nor full ACC tracking/comfort/actuator/road safety certification.", "full_ACC_purpose_bridge": "REJECTED: proof certifies only the external formal safe-distance property; tracking and comfort were not preserved or qualified"}


def run(benchmark_root, output_dir):
    from interval_check import check_original_network
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    started, cpu = perf_counter(), process_time()
    weights, biases, identity = load_network(benchmark_root)
    variable_indices = (0, 1, 3, 4)
    corners = []
    for bits in product((0, 1), repeat=4):
        initial = [bounds[0] for bounds in INITIAL]
        for index, bit in zip(variable_indices, bits):
            initial[index] = INITIAL[index][bit]
        corners.append(initial)
    rng = np.random.default_rng(2026110201)
    initials = corners + [[float(rng.uniform(lo, hi)) if lo < hi else lo for lo, hi in INITIAL] for _ in range(16)]
    original, comparisons, fallback = [], [], []
    for index, initial in enumerate(initials):
        main = simulate(initial, weights, biases)
        alternative = simulate(initial, weights, biases, method="RK45", max_step=0.005, scalar=True)
        conventional = simulate(initial, weights, biases, fallback=True)
        difference = float(np.max(np.abs(np.asarray(main["states"]) - np.asarray(alternative["states"]))))
        comparisons.append({"case": index, "maximum_state_absolute_difference": difference, "same_sampled_safety_verdict": main["sampled_margin_nonnegative"] == alternative["sampled_margin_nonnegative"], "within_registered_1e_6_check": difference <= 1e-6})
        for result in (main, conventional):
            result.pop("states")
            result.pop("times")
        original.append(main)
        fallback.append(conventional)
    interval = check_original_network(weights, biases, INITIAL)
    dependency_names = ["qpsolvers", "commonroad", "commonroad_dc"]
    safeacc = {"source_commit":"dbba852cde06435b3c870bb660ccb135ca6d21ed","status":"BLOCKED_NOT_EXECUTED","missing_dependencies":[name for name in dependency_names if importlib.util.find_spec(name) is None],"other_boundaries":"CommonRoad scenario/dynamics and required full-tool setup are not the ARCH ODE; no substitute result is labeled SafeACC execution"}
    result = {"route":"purpose-continuous-bridge", "input_identity":identity, "original_NN_point_trajectories":original, "independent_point_comparison":comparisons, "conventional_braking_point_trajectories":fallback, "conventional_analytic_certificate":analytic_fallback_certificate(), "original_NN_interval_attempt":interval, "strong_existing_SafeACC":safeacc, "claims":{"external_continuous_model_used":True,"physical_validation":False,"original_neural_controller_whole_initial_set_safe":interval["verdict"],"finite_K1_to_physical_robot_bridge":"UNRESOLVED: no sound abstraction of these dynamics into the earlier finite line game was produced","different_meaningful_next_decision":"Do not sell finite certificates as physical safety; full controller and abstraction qualification remain necessary","superiority":"NOT_ESTABLISHED; conventional analytic safe-distance witness is independently available","actual_commerce":False,"full_ACC_purpose_preservation":"REJECTED_FOR_FALLBACK: speed/comfort requirements cannot be dropped"}, "resource_telemetry":{"wall_seconds":perf_counter()-started,"cpu_seconds":process_time()-cpu,"actual_model_and_host_billing":"unknown; no model API invoked by this code"}}
    result["registered_checks_completed"] = len(original)==32 and all(x["within_registered_1e_6_check"] and x["same_sampled_safety_verdict"] for x in comparisons) and result["conventional_analytic_certificate"]["whole_initial_box_covered"]
    (out / "RESULTS.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(args.benchmark,args.output)
    print(json.dumps({"registered_checks_completed":result["registered_checks_completed"],"claims":result["claims"]},indent=2))
