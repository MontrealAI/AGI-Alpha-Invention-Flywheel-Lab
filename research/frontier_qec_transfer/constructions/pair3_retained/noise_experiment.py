"""Nondestructive, informationally complete noise-mixture experiments.

The supplied Recovery capability separates a correctable physical state into
logical and syndrome factors.  A finite rank-one informationally complete POVM
on the syndrome factor then preserves the arbitrary logical state in every
outcome.  The POVM resolves the entire syndrome density, so its classical
response matrix has exactly the physically available linear rank.

Dependencies: NumPy, SciPy, and the unchanged sibling module recovery.py.
Physical qubit 0 is the most-significant bit.  Exported dictionaries contain
direct row coefficients (already conjugated where appropriate).
"""

from __future__ import annotations

from collections.abc import Mapping
import math
import operator

import numpy as np
from scipy.optimize import linprog, minimize

from recovery import Recovery


class NoiseExperiment:
    """Construct a complete finite measurement and a constrained estimator.

    ``measurement_operators`` lists the logical-output branches.  The remaining
    outcome is a classical erasure with effect ``erasure_effect()``.  ``measure``
    executes both parts, preserving the raw trace of subnormalized input.
    ``estimate`` uses Euclidean least-squares fitting on the probability simplex;
    it does not claim an optimal measurement design or finite-shot accuracy.
    """

    def __init__(self, n: int, codewords: list[dict[int, complex]],
                 hypotheses: list[dict]):
        if isinstance(n, (bool, np.bool_)):
            raise ValueError("n must be an integer between 1 and 9")
        try:
            self.n = operator.index(n)
        except TypeError as exc:
            raise ValueError("n must be an integer between 1 and 9") from exc
        if not 1 <= self.n <= 9 or len(codewords) != 2:
            raise ValueError("the contract requires n <= 9 and two codewords")
        self.K = 2
        self.dimension = 1 << self.n
        recovery = Recovery(self.n, codewords)
        base = recovery.kraus()
        self.syndrome_rank = len(base)
        r = self.syndrome_rank
        rows = np.zeros((r, self.K, self.dimension), dtype=complex)
        for s, branch in enumerate(base):
            for i, row in enumerate(branch):
                for word, value in row.items():
                    rows[s, i, word] = value
        self._recovery_rows = rows
        self._code = np.zeros((self.dimension, self.K), dtype=complex)
        for i, word in enumerate(codewords):
            for coordinate, value in word.items():
                self._code[int(coordinate), i] = value

        # r basis outcomes with weight 1/r; four pair outcomes per pair with
        # coefficients (e_j +/- e_k)/(2 sqrt(r)) and
        # (e_j +/- i e_k)/(2 sqrt(r)).  Each syndrome coordinate receives
        # total effect 1/r + (r-1)/r = 1.  Differences of pair outcomes span
        # both Hermitian off-diagonals; basis outcomes span the diagonals.
        L = r * (2 * r - 1)
        coefficients = np.zeros((L, r), dtype=complex)
        coefficients[:r, :] = np.eye(r) / math.sqrt(r)
        index = r
        scale = 1 / (2 * math.sqrt(r))
        for j in range(r):
            for k in range(j + 1, r):
                for phase in (1, -1, 1j, -1j):
                    coefficients[index, j] = scale
                    coefficients[index, k] = scale * phase
                    index += 1
        self._coefficients = coefficients
        self._operators = (coefficients @ rows.reshape(r, -1)).reshape(
            L, self.K, self.dimension)

        if not isinstance(hypotheses, (list, tuple)) or not 1 <= len(hypotheses) <= 32:
            raise ValueError("between 1 and 32 noise hypotheses are required")
        names = []
        densities = []
        scalar_residual = 0.0
        for hypothesis in hypotheses:
            if not isinstance(hypothesis, Mapping):
                raise ValueError("each hypothesis must be a mapping")
            name = hypothesis.get("name")
            if not isinstance(name, str) or name in names:
                raise ValueError("hypothesis names must be unique strings")
            names.append(name)
            q = hypothesis.get("qubit")
            if isinstance(q, (bool, np.bool_)):
                raise ValueError("hypothesis qubit must be an integer")
            try:
                q = operator.index(q)
            except TypeError as exc:
                raise ValueError("hypothesis qubit must be an integer") from exc
            if not 0 <= q < self.n:
                raise ValueError("hypothesis qubit is out of range")
            kraus = hypothesis.get("kraus")
            if not isinstance(kraus, (list, tuple)) or len(kraus) == 0:
                raise ValueError("each channel needs a nonempty Kraus list")
            matrices = []
            for matrix in kraus:
                matrix = np.asarray(matrix, dtype=complex)
                if matrix.shape != (2, 2) or not np.all(np.isfinite(matrix)):
                    raise ValueError("Kraus matrices must be finite complex 2x2 arrays")
                matrices.append(matrix)
            completeness = sum(matrix.conj().T @ matrix for matrix in matrices)
            if np.max(np.abs(completeness - np.eye(2))) > 5e-10:
                raise ValueError("hypothesis channel is not trace preserving")
            density = np.zeros((r, r), dtype=complex)
            for matrix in matrices:
                noisy_code = self._apply_local(self._code, q, matrix)
                block = (rows.reshape(r * self.K, self.dimension)
                         @ noisy_code).reshape(r, self.K, self.K)
                scalars = np.trace(block, axis1=1, axis2=2) / self.K
                residual = np.max(np.abs(
                    block - scalars[:, None, None] * np.eye(self.K)))
                scalar_residual = max(scalar_residual, float(residual))
                density += np.outer(scalars, scalars.conj())
            densities.append(density)
        if scalar_residual > 2e-9:
            raise ValueError("channel does not act trivially on the recovered logical factor")
        self.names = tuple(names)
        self._syndrome_densities = np.asarray(densities)
        response = np.column_stack([
            np.sum((coefficients @ density) * coefficients.conj(), axis=1).real
            for density in densities
        ])
        if np.min(response) < -2e-10:
            raise ValueError("numerically invalid outcome probability")
        response = np.maximum(response, 0.0)
        if np.max(np.abs(response.sum(axis=0) - 1)) > 2e-9:
            raise ValueError("measurement response does not conserve probability")
        self._response = response
        U, singular, Vh = np.linalg.svd(response, full_matrices=False)
        tolerance = 64 * np.finfo(float).eps * max(response.shape) * singular[0]
        keep = singular > tolerance
        self.rank = int(np.count_nonzero(keep))
        self.unique = self.rank == len(hypotheses)
        self._row_basis = Vh[keep, :]
        self._projector = self._row_basis.T @ self._row_basis
        self._singular_values = singular
        self.validation_residuals = dict(recovery.validation_residuals)
        self.validation_residuals.update({
            "logical_scalar": scalar_residual,
            "response_normalization": float(np.max(np.abs(response.sum(axis=0) - 1))),
            "measurement_tight_frame": float(np.max(np.abs(
                coefficients.conj().T @ coefficients - np.eye(r)))),
            "response_rank_tolerance": float(tolerance),
        })

        # Coordinates for the affine sum-one constraint.  All least-squares
        # fits, including finite-count fits, retain explicit normalization.
        H = len(hypotheses)
        self._uniform = np.ones(H) / H
        if H == 1:
            self._tangent = np.empty((1, 0))
            self._affine_pinv = np.empty((0, L))
        else:
            _, _, right = np.linalg.svd(np.ones((1, H)), full_matrices=True)
            self._tangent = right[1:, :].T
            B = response @ self._tangent
            Bu, Bs, Bv = np.linalg.svd(B, full_matrices=False)
            active = Bs > tolerance
            self._affine_pinv = ((Bv[active, :].T / Bs[active])
                                 @ Bu[:, active].T)

    def _apply_local(self, vectors, qubit, matrix):
        mask = 1 << (self.n - 1 - qubit)
        zero = np.flatnonzero((np.arange(self.dimension) & mask) == 0)
        one = zero | mask
        out = np.empty_like(vectors)
        out[zero] = matrix[0, 0] * vectors[zero] + matrix[0, 1] * vectors[one]
        out[one] = matrix[1, 0] * vectors[zero] + matrix[1, 1] * vectors[one]
        return out

    def measurement_operators(self):
        """Return fresh K-row sparse dictionaries with direct coefficients."""
        return [[{int(word): complex(row[word])
                  for word in np.flatnonzero(row)}
                 for row in branch] for branch in self._operators]

    def response_matrix(self):
        """Return an independent copy; columns retain the input hypothesis order."""
        return self._response.copy()

    def identifiability(self):
        """Certify the identifiable quotient, including mixture normalization."""
        return {"rank": self.rank, "unique": self.unique,
                "identifiable_projector": self._projector.copy()}

    def erasure_effect(self):
        """Return the physical effect for the additional classical erasure flag.

        Its probability on any density rho is Tr(erasure_effect() @ rho).
        This is a classical-output branch; it is excluded from response_matrix.
        """
        rows = self._recovery_rows.reshape(-1, self.dimension)
        return np.eye(self.dimension) - rows.conj().T @ rows

    def measure(self, branches):
        """Execute on independent sparse pure-state branches, preserving raw mass.

        Each input dictionary represents an unnormalized ket, and the input
        density is the sum of their outer products.  Outcome densities are
        unnormalized; no postselection or conditional normalization is used.
        """
        outcome_density = np.zeros((len(self._operators), self.K, self.K), complex)
        input_mass = []
        for branch in branches:
            if not isinstance(branch, Mapping):
                raise ValueError("each branch must be a sparse state mapping")
            ket = np.zeros(self.dimension, complex)
            for word, value in branch.items():
                if isinstance(word, (bool, np.bool_)):
                    raise ValueError("state coordinates must be integers")
                try:
                    word = operator.index(word)
                    value = complex(value)
                except (TypeError, ValueError, OverflowError) as exc:
                    raise ValueError("invalid sparse state") from exc
                if not 0 <= word < self.dimension or not np.isfinite(value):
                    raise ValueError("invalid sparse state")
                ket[word] = value
            input_mass.append(float(np.vdot(ket, ket).real))
            output = self._operators @ ket
            outcome_density += output[:, :, None] * output[:, None, :].conj()
        probabilities = np.trace(outcome_density, axis1=1, axis2=2).real
        logical_density = np.sum(outcome_density, axis=0)
        input_probability = math.fsum(input_mass)
        accepted = float(math.fsum(probabilities))
        return {"outcome_densities": outcome_density,
                "outcome_probabilities": probabilities,
                "logical_density": logical_density,
                "input_probability": input_probability,
                "correctable_probability": accepted,
                "erasure_probability": input_probability - accepted}

    @staticmethod
    def _simplex_projection(vector):
        ordered = np.sort(vector)[::-1]
        partial = np.cumsum(ordered) - 1
        support = np.flatnonzero(ordered > partial / np.arange(1, len(vector) + 1))
        rho = support[-1]
        return np.maximum(vector - partial[rho] / (rho + 1), 0)

    def estimate(self, observed):
        """Fit normalized classical observations to the probability simplex.

        In a deficient-rank model, mixture_weights is one feasible representative.
        Only identifiable_coordinates and predicted_frequencies describe the
        observable equivalence class.  Finite-count estimates remain descriptive.
        """
        raw = np.asarray(observed)
        if np.iscomplexobj(raw):
            raise ValueError("observations must be real")
        counts = np.asarray(raw, dtype=float)
        if (counts.shape != (self._response.shape[0],)
                or not np.all(np.isfinite(counts)) or np.any(counts < 0)):
            raise ValueError("observations must be a finite nonnegative length-L vector")
        maximum = float(np.max(counts))
        if maximum <= 0:
            raise ValueError("zero total observations")
        scaled = counts / maximum
        frequencies = scaled / math.fsum(scaled)
        target = frequencies - self._response @ self._uniform
        unconstrained = (self._uniform + self._tangent
                         @ (self._affine_pinv @ target))
        weights = None
        method = "affine_least_squares"
        if np.min(unconstrained) >= -2e-11:
            weights = np.maximum(unconstrained, 0)
        elif not self.unique:
            # Search the entire equivalent affine class before compromising the
            # fitted observation model.  This is essential for boundary mixtures
            # whose minimum-norm representative has a negative component.
            feasible = linprog(
                np.zeros(len(self.names)), A_eq=self._row_basis,
                b_eq=self._row_basis @ unconstrained, bounds=(0, None),
                method="highs", options={"primal_feasibility_tolerance": 1e-9,
                                         "dual_feasibility_tolerance": 1e-9})
            if feasible.success:
                candidate = np.maximum(feasible.x, 0)
                candidate /= candidate.sum()
                if np.max(np.abs(self._response @ (candidate - unconstrained))) < 1e-8:
                    weights = candidate
                    method = "equivalent_feasible_representative"
        if weights is None:
            # Convex least squares on the compact simplex.  Scaling by the
            # operator norm avoids a small objective solely due to many outcomes.
            scale = self._singular_values[0]
            matrix = self._response / scale
            data = frequencies / scale
            gram = matrix.T @ matrix
            linear = matrix.T @ data

            def objective(x):
                residual = matrix @ x - data
                return 0.5 * float(residual @ residual)

            result = minimize(
                objective, self._simplex_projection(unconstrained),
                jac=lambda x: gram @ x - linear, method="SLSQP",
                bounds=[(0.0, 1.0)] * len(self.names),
                constraints={"type": "eq", "fun": lambda x: x.sum() - 1,
                             "jac": lambda x: np.ones_like(x)},
                options={"ftol": 1e-14, "maxiter": 2000})
            if not result.success:
                raise RuntimeError("constrained frequency fit failed: " + result.message)
            weights = np.maximum(result.x, 0)
            method = "simplex_least_squares"
        weights = weights / math.fsum(weights)
        predicted = self._response @ weights
        return {"mixture_weights": weights,
                "identifiable_coordinates": self._projector @ weights,
                "predicted_frequencies": predicted,
                "unique": self.unique,
                "fit_method": method,
                "frequency_residual_l2": float(np.linalg.norm(predicted - frequencies))}
