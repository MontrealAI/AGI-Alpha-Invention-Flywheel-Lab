"""Construct explicit logical-preserving pair-specific syndrome Helstrom receivers.

Independent addition to SHOTGATE224; original recovered-code and noise tools unchanged.
This solves a binary KNOWN-HYPOTHESIS decision, not the owner's general mixture task.
"""
from __future__ import annotations
import numpy as np
from noise_experiment import NoiseExperiment


class BinaryHelstrom:
    def __init__(self, experiment: NoiseExperiment, first: int, second: int):
        if not 0 <= first < experiment.H or not 0 <= second < experiment.H or first == second:
            raise ValueError("two different hypothesis indices required")
        self.experiment = experiment
        self.first, self.second = first, second
        rho = experiment._syndrome_states[first]
        sigma = experiment._syndrome_states[second]
        delta = (rho - sigma + (rho - sigma).conj().T) / 2
        eigenvalues, eigenvectors = np.linalg.eigh(delta)
        self.labels = tuple("first" if value > 0 else "second" for value in eigenvalues)
        # Row-coefficients = spectral syndrome bra * previous recovery Kraus rows.
        # The physical branch acts linearly on amplitudes, without a second conjugation.
        self._operators = np.einsum(
            "bs,sid->bid", eigenvectors.conj().T, experiment._recovery,
            optimize=True
        )
        self.syndrome_dimension = experiment.syndrome_rank
        self._eigenvectors = eigenvectors.copy()

    def certificate(self):
        """Complete physical fine-Kraus certificate and predicted two-label errors."""
        exp = self.experiment
        original = exp._recovery.reshape(-1, exp.dimension)
        transformed = self._operators.reshape(-1, exp.dimension)
        completeness = float(np.max(np.abs(
            transformed.conj().T @ transformed - original.conj().T @ original
        )))
        def distribution(h):
            sigma = exp._syndrome_states[h]
            probabilities = []
            for lab in ("first", "second"):
                probabilities.append(float(sum(
                    np.vdot(self._eigenrow(j),sigma @ self._eigenrow(j)).real
                    for j, label in enumerate(self.labels) if label == lab
                )))
            return probabilities

        p = distribution(self.first)
        q = distribution(self.second)
        error = 0.5 * (p[1] + q[0])
        return {
            "source_pair": [exp.hypothesis_names[self.first],
                            exp.hypothesis_names[self.second]],
            "fine_kraus_operators": len(self.labels),
            "coarse_labels": ["first", "second"],
            "physical_completeness_residual": completeness,
            "probabilities_first_hypothesis": p,
            "probabilities_second_hypothesis": q,
            "equal_prior_one_shot_error": error,
        }

    def _eigenrow(self, index):
        # Eigenvector in original syndrome coordinates for direct prediction.
        return self._eigenvectors[:, index]

    def operators(self):
        """Each fine-grained physical-to-logical Kraus operator and binary label."""
        return [(label, matrix.copy()) for label, matrix in
                zip(self.labels, self._operators)]

    def execute(self, branches):
        """Preserve mass and return unnormalized logical density per binary label."""
        exp = self.experiment
        output = {key: np.zeros((exp.K, exp.K),complex)
                  for key in ("first","second")}
        input_mass = 0.0
        for branch in branches:
            physical = np.zeros(exp.dimension,complex)
            for coordinate, amplitude in branch.items():
                if isinstance(coordinate,bool) or not isinstance(coordinate,int) or not 0 <= coordinate < exp.dimension:
                    raise ValueError("invalid physical coordinate")
                c = complex(amplitude)
                if not np.isfinite(c):
                    raise ValueError("nonfinite branch amplitude")
                physical[coordinate] = c
            input_mass += float(np.vdot(physical,physical).real)
            for label, operator in self.operators():
                v = operator @ physical
                output[label] += np.outer(v,v.conj())
        probabilities = {key: float(np.trace(d).real) for key,d in output.items()}
        erasure = input_mass - sum(probabilities.values())
        return {
            "logical_density_by_label": output,
            "probabilities": probabilities,
            "input_mass": input_mass,
            "erasure": erasure
        }
