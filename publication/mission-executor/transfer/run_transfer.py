"""Compare exact break-even recommendations across retained and ordinary methods."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from fractions import Fraction
from hashlib import sha256
from itertools import product
import json
from math import lcm
from pathlib import Path
import platform
from statistics import median
import sys
from time import perf_counter, process_time

import numpy as np
import scipy
from scipy.optimize import linprog


HERE = Path(__file__).resolve().parent
GAME = HERE.parent / "game"
sys.path[:0] = [str(GAME), str(GAME / "evaluator")]

from observation import parse_game, verify
from solve_observation import solve
from strategic_reference import independent_certificate, model_space, utility


DENOMINATOR = 1_000_000_000
ENTRY_LIMIT = 250_000


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def distribute(values):
    """Round a solver distribution while conserving exactly one unit of probability."""
    weights = np.maximum(values, 0)
    if not np.all(np.isfinite(weights)) or weights.sum() <= 0:
        raise ValueError("The optimizer did not return a finite probability distribution")
    units = weights / weights.sum() * DENOMINATOR
    integer = np.floor(units).astype(np.int64)
    missing = int(DENOMINATOR - integer.sum())
    if not 0 <= missing <= len(integer):
        raise ArithmeticError("Invalid residual probability mass")
    order = np.argsort(-(units - integer), kind="stable")
    integer[order[:missing]] += 1
    return [int(x) for x in integer]


def reference_model(game):
    """Construct the ordinary full normal form with exact rational payoff entries."""
    scenarios, row, column, signals, probabilities, costs = model_space(game)
    instrument, names = next(iter(signals.items()))
    count = len(row) ** len(names)
    if count * len(column) > ENTRY_LIMIT:
        raise ValueError("Case exceeds registered normal-form entry budget")
    denominator = lcm(costs[instrument].denominator, *(
        value.denominator for vector in probabilities[instrument].values() for value in vector.values()
    ))
    scale = max(1, *(sum(item["weights"]) for item in scenarios.values()))
    if (scale + costs[instrument]) * denominator >= 2 ** 52:
        raise OverflowError("Payoff lattice exceeds exact integer conversion")
    board = np.asarray([[utility(r, c, scenarios[s]["weights"]) for s, c in column] for r in row],
                       dtype=np.int64)
    policy_coordinates = list(product(range(len(row)), repeat=len(names)))
    where = np.asarray(policy_coordinates, dtype=np.intp)
    payoffs = np.full((count, len(column)), -int(costs[instrument] * denominator), dtype=np.int64)
    for index, signal in enumerate(names):
        weights = np.asarray([int(probabilities[instrument][s][signal] * denominator) for s, _ in column],
                             dtype=np.int64)
        payoffs += board[where[:, index], :] * weights
    return instrument, names, row, column, policy_coordinates, payoffs / denominator


def original_solve(document, game):
    instrument, names, row, column, actions, matrix = reference_model(document)
    rows, cols = matrix.shape
    reward = np.r_[np.zeros(rows), -1.]
    constraints = np.column_stack((-matrix.T, np.ones(cols)))
    normalization = np.r_[np.ones(rows), 0.][None, :]
    forward = linprog(reward, A_ub=constraints, b_ub=np.zeros(cols),
                      A_eq=normalization, b_eq=[1.], bounds=[(0, None)] * rows + [(None, None)],
                      method="highs")
    if not forward.success:
        raise RuntimeError(forward.message)
    # Obtain column strategy from the primal dual multipliers. Running a second LP
    # is unnecessary because the exact strategy certificate checks both bounds.
    row_mass = distribute(forward.x[:-1])
    col_mass = distribute(-forward.ineqlin.marginals)
    tables = {name: {} for name in names}
    for action, mass in zip(actions, row_mass):
        if mass:
            for name, index in zip(names, action):
                move = row[index]
                tables[name][move] = tables[name].get(move, 0) + mass
    certificate = {
        "schema": "frontier/costly-observation-certificate-v1",
        "game_sha256": game.digest(),
        "denominator": DENOMINATOR,
        "row": [{
            "instrument": instrument,
            "mass": DENOMINATOR,
            "signals": {name: [{"allocation": list(move), "mass": mass} for move, mass in sorted(table.items())]
                        for name, table in tables.items()},
        }],
        "column": [{"scenario": scenario, "allocation": list(move), "mass": mass}
                   for (scenario, move), mass in zip(column, col_mass) if mass],
    }
    return certificate, rows * cols


def alternative(document, option):
    restricted = deepcopy(document)
    restricted["instruments"] = [item for item in restricted["instruments"] if item["id"] == option]
    return restricted, parse_game(restricted)


def interval(proof):
    return tuple(Fraction(proof[name]) for name in ("lower", "upper"))


def decisions(quotes, fee):
    lower, upper = fee
    return {quote: "BUY" if Fraction(quote) < lower
            else "SKIP" if Fraction(quote) > upper
            else "UNRESOLVED_OR_TIE" for quote in quotes}


def arm(case, method):
    started = perf_counter()
    cpu = process_time()
    results = {}
    certificates = {}
    for option in ("none", "probe"):
        model, game = alternative(case["game"], option)
        if method == "retained":
            certificate, receipt = solve(game)
            work = {"sparse_nonzeros": receipt["nonzeros"], "sparse_variables": receipt["variables"]}
        else:
            certificate, count = original_solve(model, game)
            work = {"explicit_payoff_entries": count}
        checked = verify(game, certificate)
        if checked["verdict"] != "QUALIFIED":
            raise ArithmeticError(f"{option} optimizer returned an uncertified interval")
        certificates[option] = certificate
        results[option] = {"interval": [checked["lower"], checked["upper"]], **work}
    blind_lo, blind_hi = map(Fraction, results["none"]["interval"])
    noisy_lo, noisy_hi = map(Fraction, results["probe"]["interval"])
    fee = max(Fraction(0), noisy_lo - blind_hi), max(Fraction(0), noisy_hi - blind_lo)
    return {
        "wall_s": perf_counter() - started,
        "cpu_s": process_time() - cpu,
        "forced": results,
        "fee_interval": list(map(str, fee)),
        "quoted_decisions": decisions(case["quotes"], fee),
        "certificates": certificates,
    }


def run_case(case, index, repetitions):
    runs = {"retained": [], "ordinary": []}
    first_evidence = {}
    for repetition in range(repetitions):
        names = ("retained", "ordinary") if (index + repetition) % 2 == 0 else ("ordinary", "retained")
        comparison = {}
        for name in names:
            result = arm(case, name)
            certificates = result.pop("certificates")
            runs[name].append(result)
            comparison[name] = result
            if repetition == 0:
                # Apply the held evaluator's methodically separate all-action checker
                # outside both timing arms, to the exact same acceptance contract.
                first_evidence[name] = {}
                for option, certificate in certificates.items():
                    model, _ = alternative(case["game"], option)
                    independent = independent_certificate(model, certificate)
                    if [independent["lower"], independent["upper"]] != result["forced"][option]["interval"]:
                        raise ArithmeticError("Independent exact bounds disagree")
                    first_evidence[name][option] = {"certificate": certificate, "independent": independent}
        bounds = [tuple(map(Fraction, result["fee_interval"])) for result in comparison.values()]
        scale = max(1, *(sum(option["weights"]) for option in case["game"]["scenarios"]))
        if max(pair[0] for pair in bounds) > min(pair[1] for pair in bounds):
            raise ArithmeticError("Correctly bounded fee intervals do not overlap")
        if any((hi - lo) * 1_000_000 > scale for lo, hi in bounds):
            raise ArithmeticError("Break-even bounds are wider than the registration")
        if comparison["retained"]["quoted_decisions"] != comparison["ordinary"]["quoted_decisions"]:
            raise ArithmeticError("Quoted price recommendations disagree")
    medians = {
        arm_name: {field: median(sample[field] for sample in samples) for field in ("wall_s", "cpu_s")}
        for arm_name, samples in runs.items()
    }
    return {
        "id": case["id"],
        "repetitions": runs,
        "median": medians,
        "wall_retained_to_ordinary_ratio": medians["retained"]["wall_s"] / medians["ordinary"]["wall_s"],
        "first_certificates_independently_recomputed": first_evidence,
        "without_observation": {
            "fee_interval": ["0", "0"],
            "quoted_decisions": decisions(case["quotes"], (Fraction(0), Fraction(0))),
            "proof": "Giving two copies of the same optimized no-signal contract yields identical certified minimax payoff for both. The difference is exactly zero. The blind baseline is solved in both arms."
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    flags = parser.parse_args()
    registration = load(HERE / "REGISTRATION.json")
    for name, expected in registration["sha256"].items():
        if digest(HERE / name) != expected:
            raise ValueError(f"Frozen transfer file changed: {name}")
    plan, inputs = load(HERE / "PLAN.json"), load(HERE / "INPUTS.json")
    denominator = plan["denominator"]
    if len(inputs["cases"]) != denominator["cases"]:
        raise ValueError("Case denominator changed")
    results = [run_case(case, index, denominator["paired_repetitions"]) for index, case in enumerate(inputs["cases"])]
    faster = sum(item["wall_retained_to_ordinary_ratio"] <= .8 for item in results)
    outcome = {
        "schema": "frontier/observation-cost-transfer-receipt-v1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "registration_sha256": digest(HERE / "REGISTRATION.json"),
        "runtime": {"python": platform.python_version(), "scipy": scipy.__version__, "numpy": np.__version__},
        "outcomes": results,
        "accepted_cases": len(results),
        "accepted_quote_comparisons": len(results) * denominator["quotes_per_case"],
        "materially_faster_cases": faster,
        "declared_speed_gate": "PASS" if faster >= 2 else "FAIL",
        "operating_scope": "Matched process-local computation and exact outcome checks. Includes optimizer initialization in the first sample and records method-order effects. Complete construction, integration, maintenance and financial costs remain unobserved.",
    }
    with flags.output.open("x", encoding="utf-8") as stream:
        json.dump(outcome, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
