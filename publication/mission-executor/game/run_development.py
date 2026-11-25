"""Execute reproducible development cases and resource-qualified comparators."""

import argparse
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import platform
from random import Random
from time import perf_counter, process_time

import numpy
import scipy

from compare_observation import action_counts, double_oracle, explicit, public_menu
from observation import allocation, parse_game, verify
from solve_observation import retained, solve


HERE = Path(__file__).resolve().parent
PLAN = allocation.read_json(HERE / "QUALIFICATION-PLAN.json")


def runs(game, order=0):
    tested = {}
    methods = (("sparse", solve), ("explicit", explicit), ("double_oracle", double_oracle))
    for name, method in methods[order:] + methods[:order]:
        _, result = method(game)
        tested[name] = result
    evidence = {}
    for name, output in tested.items():
        proof = output.get("verification")
        if proof and proof["verdict"] != "QUALIFIED":
            raise AssertionError(f"{name} returned a wide interval")
        evidence[name] = {
            "bounds": [proof["lower"], proof["upper"]] if proof else None,
            "seconds": output.get("whole_seconds"),
            "status": output.get("status", proof["verdict"] if proof else "UNKNOWN"),
            **{key: output[key] for key in ("nonzeros", "variables", "iterations") if key in output},
        }
    feasible = [tuple(map(Fraction, row["bounds"])) for row in evidence.values() if row["bounds"]]
    assert max(lo for lo, _ in feasible) <= min(hi for _, hi in feasible)
    row_count, column_count = action_counts(game)
    return {
        "model_sha256": game.digest(),
        "implicit_pairs": row_count * column_count,
        "row_policies": row_count,
        "opponent_actions": column_count,
        "arms": evidence,
    }


def instrument(name, cost, scenario_ids, distributions):
    return {
        "id": name,
        "cost": str(cost),
        "channel": {
            identity: {f"symbol-{k}": str(value) for k, value in enumerate(row)}
            for identity, row in zip(scenario_ids, distributions)
        },
    }


def development_games():
    rng = Random(PLAN["registered_development_seed"])
    for _ in range(PLAN["registered_development_games"]):
        lanes = rng.randint(1, 4)
        row_budget = rng.randint(0, 4)
        identities = [f"state-{i}" for i in range(rng.randint(1, 4))]
        scenarios = [
            {
                "id": identity, "column_budget": rng.randint(0, 4),
                "weights": [rng.randint(0, 14) for _ in range(lanes)],
            }
            for identity in identities
        ]
        options = [instrument("none", 0, identities, [(1,)] * len(identities))]
        for index in range(rng.randint(1, 3)):
            distributions = []
            for _ in identities:
                probability = Fraction(rng.randint(0, 13), 13)
                distributions.append((probability, 1 - probability))
            options.append(
                instrument(f"test-{index}", Fraction(rng.randint(0, 24), 7), identities, distributions)
            )
        yield parse_game({
            "schema": "frontier/costly-observation-game-v1", "row_budget": row_budget,
            "scenarios": scenarios, "instruments": options,
        })


def large_game():
    identities = ["north", "center", "south"]
    return parse_game({
        "schema": "frontier/costly-observation-game-v1",
        "row_budget": 7,
        "scenarios": [
            {"id": "north", "column_budget": 7, "weights": [10, 1, 6, 7, 2, 4]},
            {"id": "center", "column_budget": 8, "weights": [2, 3, 12, 7, 5, 8]},
            {"id": "south", "column_budget": 6, "weights": [1, 7, 1, 6, 9, 11]},
        ],
        "instruments": [
            instrument("none", 0, identities, [(1,)] * 3),
            instrument(
                "quick", Fraction(1, 5), identities,
                [(Fraction(4, 5), Fraction(1, 5)), (Fraction(1, 2), Fraction(1, 2)),
                 (Fraction(2, 5), Fraction(3, 5))],
            ),
            instrument(
                "detailed", Fraction(7, 10), identities,
                [(Fraction(7, 10), Fraction(2, 10), Fraction(1, 10)),
                 (Fraction(2, 10), Fraction(7, 10), Fraction(1, 10)),
                 (Fraction(2, 10), Fraction(2, 10), Fraction(6, 10))],
            ),
        ],
    })


def negative_controls(model, certificate):
    incorrect_channel = deepcopy(model)
    incorrect_channel["instruments"][0]["channel"]["north"]["silent"] = "1/2"
    missing_signal = deepcopy(model)
    del missing_signal["instruments"][1]["channel"]["south"]["quiet"]
    phantom_probability = deepcopy(model)
    phantom_probability["instruments"][1]["channel"]["south"]["trigger"] = 0.5
    incorrect_mass = deepcopy(certificate)
    incorrect_mass["row"][0]["signals"]["trigger"][0]["mass"] += 1
    stale_objective = deepcopy(model)
    stale_objective["instruments"][1]["cost"] = "3"
    unqualified = deepcopy(certificate)
    unqualified["row"] = [{
        "instrument": "none", "mass": certificate["denominator"],
        "signals": {"silent": [{"allocation": [1, 0], "mass": certificate["denominator"]}]},
    }]
    controls = {
        "non_normalized_channel": lambda: parse_game(incorrect_channel),
        "inconsistent_signal_alphabet": lambda: parse_game(missing_signal),
        "binary_float_probability": lambda: parse_game(phantom_probability),
        "unconserved_integer_mass": lambda: verify(parse_game(model), incorrect_mass),
        "edited_game_digest": lambda: verify(parse_game(stale_objective), certificate),
    }
    outcomes = {}
    for name, check in controls.items():
        try:
            check()
        except ValueError as error:
            outcomes[name] = {"status": "REJECTED", "reason": str(error)}
        else:
            raise AssertionError(f"{name} incorrectly passed")
    proof = verify(parse_game(model), unqualified)
    assert proof["verdict"] == "BOUND_ONLY"
    outcomes["feasible_suboptimal_policy"] = proof
    return outcomes


def measure():
    wall_started, cpu_started = perf_counter(), process_time()
    example = allocation.read_json(HERE / "EXAMPLE.json")
    problem = parse_game(example)
    certificate, proof = solve(problem)
    assert (proof["verification"]["lower"], proof["verification"]["upper"]) == ("7", "7")
    announcement = public_menu(problem)
    assert Fraction(announcement["lower"]) <= 6 <= Fraction(announcement["upper"])
    _, no_observation = retained.solve(problem.allocation)
    best_case_upper = []
    for scenario in problem.allocation.scenarios:
        specific = allocation.Game(problem.allocation.budget, (scenario,))
        _, known = retained.solve(specific)
        proof_given_state = known["verification"]
        best_case_upper.append(Fraction(proof_given_state["upper_numerator"], proof_given_state["denominator"]))
    assert min(best_case_upper) == 12
    curve = []
    for cost, expected in enumerate((9, 8, 7, 6, 6)):
        model = deepcopy(example)
        for item in model["instruments"][1:]:
            item["cost"] = str(cost)
        _, experiment = solve(parse_game(model))
        result = experiment["verification"]
        assert Fraction(result["lower"]) <= expected <= Fraction(result["upper"])
        curve.append({"cost": cost, "lower": result["lower"], "upper": result["upper"]})
    controls = negative_controls(example, certificate)
    held_development = [runs(game, index % 3) for index, game in enumerate(development_games())]
    large = large_game()
    large_profile = runs(large)
    return {
        "schema": "frontier/costly-observation-development-v1",
        "environment": {
            "python": platform.python_version(), "numpy": numpy.__version__,
            "scipy": scipy.__version__,
        },
        "example": runs(problem),
        "public_vs_private": {
            "private_interval": ["7", "7"],
            "public_interval": [announcement["lower"], announcement["upper"]],
            "private_improvement_interval": [
                str(7 - Fraction(announcement["upper"])), str(7 - Fraction(announcement["lower"])),
            ],
            "single_option_intervals": {
                name: [item["verification"]["lower"], item["verification"]["upper"]]
                for name, item in announcement["instruments"].items()
            },
            "retained_no_info_certificate": no_observation["verification"],
            "clairvoyant_free_scenario_upper": str(min(best_case_upper)),
            "cost_sensitivity": curve,
        },
        "negative_controls": controls,
        "generated": held_development,
        "large_model": large.document(),
        "large_profile": large_profile,
        "total_seconds": perf_counter() - wall_started,
        "total_cpu_seconds": process_time() - cpu_started,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    allocation.write_json(args.output, measure())


if __name__ == "__main__":
    main()
