"""Run the two research capabilities on inspectable simulated examples.

This operator example is separate from the frozen construction experiment.
It performs classical computations; it does not operate quantum hardware.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "fixtures"))
from public_fixtures import (
    apply_local, archived_controlled_s_15, pollatsek_ruskai_7, shor_9,
)
from second_public_fixtures import pauli_hypotheses
from recovery import Recovery


def first_outcome():
    rows = []
    for factory in (pollatsek_ruskai_7, shor_9, archived_controlled_s_15):
        n, codewords = factory()
        recovery = Recovery(n, codewords)
        logical = np.arange(1, len(codewords) + 1, dtype=complex) + .4j
        logical /= np.linalg.norm(logical)
        state = recovery.encode(logical)
        gamma = .31
        channel = [np.diag([1, np.sqrt(1 - gamma)]),
                   np.array([[0, np.sqrt(gamma)], [0, 0]])]
        branches = [apply_local(state, n, n // 2, k) for k in channel]
        result = recovery.recover(branches)
        expected = np.outer(logical, logical.conj())
        residual = float(np.max(abs(result["logical_density"] - expected)))
        assert residual < 2e-8
        assert abs(result["input_probability"] - 1) < 2e-8
        assert abs(result["erasure_probability"]) < 2e-8
        rows.append({
            "code": factory.__name__, "physical_qubits": n,
            "logical_dimension": len(codewords),
            "recovery_operators": len(recovery.kraus()),
            "logical_density_max_error": residual,
            "input_probability": result["input_probability"],
            "correctable_probability": result["correctable_probability"],
            "erasure_probability": result["erasure_probability"],
        })
    return rows


def second_outcome():
    from noise_experiment import NoiseExperiment
    rows = []
    for factory in (pollatsek_ruskai_7, shor_9):
        n, codewords = factory()
        models = pauli_hypotheses(n)
        experiment = NoiseExperiment(n, codewords, models)
        instrument = experiment.measurement_operators()
        response = np.asarray(experiment.response_matrix(), float)
        info = experiment.identifiability()
        weights = np.arange(1, len(models) + 1, dtype=float)
        weights /= weights.sum()
        logical = np.array([np.sqrt(.37), 1j * np.sqrt(.63)])
        encoded = Recovery(n, codewords).encode(logical)
        observed = np.zeros(len(instrument))
        recovered = np.zeros((2, 2), complex)
        # Generate observations by executing the exported physical operators,
        # independently of the experiment's response-matrix prediction.
        for weight, model in zip(weights, models):
            for kraus in model["kraus"]:
                noisy = apply_local(encoded, n, model["qubit"], kraus)
                for index, operator in enumerate(instrument):
                    output = np.array([
                        sum(coefficient * noisy.get(word, 0j)
                            for word, coefficient in row.items())
                        for row in operator
                    ])
                    observed[index] += weight * float(np.vdot(output, output).real)
                    recovered += weight * np.outer(output, output.conj())
        estimate = experiment.estimate(observed)
        projector = np.asarray(info["identifiable_projector"], float)
        parameter_error = float(np.max(abs(
            np.asarray(estimate["identifiable_coordinates"]) - projector @ weights
        )))
        prediction_error = float(np.max(abs(response @ weights - observed)))
        preservation_error = float(np.max(abs(
            recovered - np.outer(logical, logical.conj())
        )))
        assert parameter_error < 2e-6
        assert prediction_error < 2e-8
        assert preservation_error < 2e-8
        rows.append({
            "code": factory.__name__, "hypotheses": len(models),
            "measurement_outcomes": len(instrument),
            "identifiable_rank": int(info["rank"]),
            "unique_mixture": bool(info["unique"]),
            "identifiable_coordinate_max_error": parameter_error,
            "response_prediction_max_error": prediction_error,
            "logical_preservation_max_error": preservation_error,
            "observation_model": "Exact probabilities from classical simulation; no laboratory data.",
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("first", "both"), default="both")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = {
        "scope": "Executable classical quantum-code research demonstration",
        "source_sha256": {
            "recovery.py": hashlib.sha256((HERE / "recovery.py").read_bytes()).hexdigest(),
            **({"noise_experiment.py": hashlib.sha256(
                (HERE / "noise_experiment.py").read_bytes()).hexdigest()}
               if args.stage == "both" else {}),
        },
        "recovery": first_outcome(),
    }
    if args.stage == "both":
        result["noise_experiment"] = second_outcome()
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
