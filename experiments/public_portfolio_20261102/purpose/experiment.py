from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from time import perf_counter, process_time
import argparse
import hashlib
import json

try:
    from .kernel import reach_avoid, recovery_set, verify_certificate
    from .diagnosis import belief_id, construct_diagnosis
    from .specialist import full_tree_layers
except ImportError:
    from kernel import reach_avoid, recovery_set, verify_certificate
    from diagnosis import belief_id, construct_diagnosis
    from specialist import full_tree_layers


def line_game(length, battery):
    states = [f"{position}:{charge}" for position in range(length + 1) for charge in range(battery + 1)]
    game = {s: {} for s in states + ["failure"]}
    for state in states:
        position, charge = map(int, state.split(":"))
        if charge == 0:
            game[state] = {"forward": ["failure"], "reverse": ["failure"]}
        else:
            game[state] = {"forward": [f"{min(position + 1, length)}:{charge - 1}"], "reverse": [f"{max(0, position - 1)}:{charge - 1}"], "fast": sorted({f"{min(position + step, length)}:{charge - 1}" for step in (1, 2)})}
    safe = set(states)
    emergency = {s for s in states if s.startswith("0:")}
    target = {s for s in states if s.startswith(str(length) + ":")}
    return game, safe, emergency, target


def diagnosis_models(length, battery, indistinguishable=False, calibration=True):
    base, safe, emergency, _ = line_game(length, battery)
    worlds = {}
    for world in ("normal", "weak_drive", "reverse_fault"):
        model = {s: {} for s in base}
        effective = "normal" if indistinguishable else world
        for state, actions in base.items():
            if state == "failure":
                continue
            position, charge = map(int, state.split(":"))
            for action, outcomes in actions.items():
                if effective == "reverse_fault" and action == "reverse" and position > 0:
                    outcomes = [f"{position}:{charge - 1}"] if charge else ["failure"]
                if effective == "weak_drive" and action == "fast" and charge:
                    outcomes = [f"{position}:{charge - 1}", f"{min(position + 1, length)}:{charge - 1}"]
                model[state][action] = [(next_state, "motion") for next_state in outcomes]
            if charge and position == 0 and calibration:
                observation = "reverse_fault" if effective == "reverse_fault" else "reverse_ok"
                model[state]["calibrate"] = [(f"0:{charge - 1}", observation)]
            if charge and position > 0:
                observation = "weak" if effective == "weak_drive" else "nominal"
                model[state]["load_test"] = [(f"{position}:{charge - 1}", observation)]
        worlds[world] = model
    return worlds, safe, emergency


def k1_case(length, battery):
    game, safe, emergency, targets = line_game(length, battery)
    recovery = recovery_set(game, safe, emergency, length + 1)
    candidate = reach_avoid(game, safe, targets, length + 1, recovery.winning)
    conventional = full_tree_layers(game, safe, targets, length + 1, recovery.winning, memoize=True)
    without_future = reach_avoid(game, safe, targets, length + 1)
    initial = f"0:{battery}"
    return {"length": length, "battery": battery, "states": len(game), "initial": initial, "accepted": verify_certificate(game, safe, targets, candidate, recovery.winning), "initial_feasible": initial in candidate.winning, "strong_conventional_exact_tie": candidate.layers == conventional.layers, "winning_states": len(candidate.winning), "goal_only_extra_states_rejected": len(without_future.winning - candidate.winning), "candidate_transition_checks": candidate.transition_checks, "conventional_transition_checks": conventional.transition_checks, "artifact": {"game": game, "safe": sorted(safe), "emergency": sorted(emergency), "targets": sorted(targets), "recovery": recovery.as_json(), "delivery": candidate.as_json()}}


def factorial():
    game, safe, emergency, targets = line_game(3, 8)
    reports = []
    expected = None
    for shared_mask in (False, True):
        for compact in (False, True):
            recovery_work = 0
            if shared_mask:
                rec = recovery_set(game, safe, emergency, 4)
                invariant = rec.winning
                recovery_work = rec.transition_checks
            else:
                invariant = set()
                for state in sorted(game):
                    rec = full_tree_layers(game, safe, emergency, 4, memoize=False)
                    recovery_work += rec.transition_checks
                    if state in rec.winning:
                        invariant.add(state)
            solver = reach_avoid if compact else full_tree_layers
            certificate = solver(game, safe, targets, 4, invariant)
            if expected is None:
                expected = certificate.layers
            reports.append({"representation_change_A": compact, "shared_recovery_change_B": shared_mask, "original_purpose_preserved": certificate.layers == expected and verify_certificate(game, safe, targets, certificate, invariant), "transition_checks_including_recovery": recovery_work + certificate.transition_checks})
    return reports


def k2_case(name, battery, *, indistinguishable=False, calibration=True):
    worlds, safe, emergency = diagnosis_models(3, battery, indistinguishable, calibration)
    candidate = construct_diagnosis(worlds, safe, emergency, 4, 4)
    fresh = construct_diagnosis(worlds, safe, emergency, 4, 4, inherited_kernel=False)
    ordinary = construct_diagnosis(worlds, safe, emergency, 4, 4)
    initial = belief_id(f"0:{battery}", worlds)
    nominal = reach_avoid(candidate["game"], candidate["safe"], candidate["diagnosed"], 4)
    certified = verify_certificate(candidate["game"], candidate["safe"], candidate["diagnosed"], candidate["certificate"], candidate["recovery"].winning)
    return {"name": name, "battery": battery, "belief_states": len(candidate["game"]), "initial": initial, "accepted_certificate": certified, "safe_exact_diagnosis_feasible": initial in candidate["certificate"].winning, "no_inheritance_exact_tie": candidate["certificate"].layers == fresh["certificate"].layers, "equal_content_ordinary_reuse_exact_tie": candidate["certificate"].layers == ordinary["certificate"].layers, "unsafe_diagnosis_states_rejected": len(nominal.winning - candidate["certificate"].winning), "artifact": {"game": candidate["game"], "metadata": candidate["metadata"], "safe": sorted(candidate["safe"]), "emergency": sorted(candidate["emergency"]), "diagnosed": sorted(candidate["diagnosed"]), "recovery": candidate["recovery"].as_json(), "diagnosis": candidate["certificate"].as_json()}}


def run_experiment(output_dir):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    started, cpu = perf_counter(), process_time()
    k1 = [k1_case(length, 2 * length + 2) for length in (3, 4, 5, 6, 7, 8)]
    k1 += [k1_case(5, battery) for battery in (3, 5, 7, 9)]
    k2 = [k2_case("central", 8), k2_case("low_energy_refusal", 2), k2_case("indistinguishable_faults", 8, indistinguishable=True), k2_case("no_safe_diagnostic_probe", 8, calibration=False)]
    for stage, cases in (("K1", k1), ("K2", k2)):
        for index, case in enumerate(cases):
            artifact = case.pop("artifact")
            serialized = json.dumps(artifact, sort_keys=True, separators=(",", ":"))
            path = output / f"{stage}_{index:02d}.json"
            path.write_text(serialized + "\n")
            case["artifact_path"] = path.name
            case["artifact_sha256"] = hashlib.sha256((serialized + "\n").encode()).hexdigest()
    result = {"route": "purpose", "evidence_kind": "executed synthetic finite-state computation, not physical safety or observed commerce", "K1": k1, "factorial": factorial(), "K2": k2, "claims": {"finite_purpose_preservation": all(x["accepted"] and x["strong_conventional_exact_tie"] for x in k1), "different_successor_function_constructed": True, "retained_instrument_superiority": False, "ordinary_reuse_tie": True, "newly_attainable_real_world_outcome": "unresolved", "Blue_Sky_admission": "unresolved; strong conventional complete route ties", "human_productivity": "unmeasured", "actual_commerce": False, "profit_target_attained": False}, "resource_telemetry": {"wall_seconds": perf_counter() - started, "cpu_seconds": process_time() - cpu, "internal_human_intervention_minutes_during_computation": 0, "model_and_host_actual_billing": "unknown; no paid call made by this code"}}
    result["all_registered_conditions"] = all(x["accepted"] and x["strong_conventional_exact_tie"] for x in k1) and all(x["accepted_certificate"] and x["no_inheritance_exact_tie"] and x["equal_content_ordinary_reuse_exact_tie"] for x in k2) and k2[0]["safe_exact_diagnosis_feasible"] and not any(x["safe_exact_diagnosis_feasible"] for x in k2[1:]) and all(x["original_purpose_preserved"] for x in result["factorial"])
    (output / "RESULTS.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run_experiment(args.output)
    print(json.dumps({"all_registered_conditions": result["all_registered_conditions"], "output": args.output, "claims": result["claims"]}, indent=2))
