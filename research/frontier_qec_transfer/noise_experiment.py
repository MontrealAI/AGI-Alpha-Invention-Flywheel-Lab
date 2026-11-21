"""Nondestructive identification of mixtures of correctable local channels.

This module uses the public Recovery API from the supplied recovery.py.
The syndrome frame is informationally complete: start with bras e_j,
(e_j+e_k)/sqrt(2), and (e_j+i e_k)/sqrt(2), then right-whiten their
frame operator.  These r**2 rank-one effects sum to the syndrome identity
and span every Hermitian syndrome operator.  Combining each frame bra
with the recovery Kraus operators yields one physical-to-logical Kraus
operator per outcome.  The code's logical state is unchanged in every
supported branch; all available channel-mixture information is retained.

An additional erasure outcome has effect I - projector(correctable span).
It is exposed by erasure_effect() and executed by execute().  Counts are
normalized explicitly.  Estimation fits the identifiable coordinates on
the probability simplex; it makes no optimal-shot or uncertainty claim.
"""
from __future__ import annotations

from collections.abc import Mapping
import math
import operator

import numpy as np
from scipy.optimize import linprog, minimize

from recovery import Recovery


class NoiseExperiment:
    """Construct an executable instrument for a valid two-dimensional code."""

    def __init__(self, n: int, codewords: list[dict[int, complex]],
                 hypotheses: list[dict]):
        if isinstance(n, (bool, np.bool_)):
            raise ValueError("n must be an integer between 1 and 9")
        try:
            self.n = operator.index(n)
        except TypeError as exc:
            raise ValueError("n must be an integer between 1 and 9") from exc
        if not 1 <= self.n <= 9:
            raise ValueError("n must be an integer between 1 and 9")
        if len(codewords) != 2:
            raise ValueError("exactly two ordered orthonormal codewords are required")
        self.K = 2
        self.dimension = 1 << self.n
        recovery = Recovery(self.n, codewords)
        self.syndrome_rank = recovery.syndrome_rank
        recovery_operators = recovery.kraus()
        self._recovery = np.zeros(
            (self.syndrome_rank, self.K, self.dimension), complex)
        for s, rows in enumerate(recovery_operators):
            for i, row in enumerate(rows):
                for word, coefficient in row.items():
                    self._recovery[s, i, word] = coefficient
        self._code = np.zeros((self.dimension, self.K), complex)
        for i, word in enumerate(codewords):
            for coordinate, coefficient in word.items():
                self._code[coordinate, i] = coefficient
        self.hypotheses = self._validate_hypotheses(hypotheses)
        self.hypothesis_names = tuple(h["name"] for h in self.hypotheses)
        self.H = len(self.hypotheses)

        r = self.syndrome_rank
        raw = np.zeros((r * r, r), complex)
        raw[:r] = np.eye(r)
        cursor = r
        for j in range(r):
            for k in range(j + 1, r):
                raw[cursor, j] = raw[cursor, k] = 1 / np.sqrt(2)
                cursor += 1
                raw[cursor, j] = 1 / np.sqrt(2)
                raw[cursor, k] = 1j / np.sqrt(2)
                cursor += 1
        frame = raw.conjugate().T @ raw
        values, vectors = np.linalg.eigh(frame)
        inverse_sqrt = (vectors / np.sqrt(values)[None, :]) @ vectors.conjugate().T
        self._bras = raw @ inverse_sqrt
        self.L = len(self._bras)
        self._operators = np.einsum(
            "os,sid->oid", self._bras, self._recovery, optimize=True)

        self._response = np.empty((self.L, self.H), float)
        self._syndrome_states = np.empty((self.H, r, r), complex)
        for h, hypothesis in enumerate(self.hypotheses):
            sigma = np.zeros((r, r), complex)
            probability = np.zeros(self.L, float)
            for kraus in hypothesis["kraus"]:
                physical = self._apply_local(
                    self._code[:, 0], hypothesis["qubit"], kraus)
                syndrome = self._recovery[:, 0, :] @ physical
                sigma += np.outer(syndrome, syndrome.conjugate())
                probability += np.abs(self._bras @ syndrome) ** 2
            self._syndrome_states[h] = sigma
            self._response[:, h] = probability
        u, singular, vh = np.linalg.svd(self._response, full_matrices=False)
        tolerance = (32 * np.finfo(float).eps
                     * max(self._response.shape) * singular[0])
        self.rank = int(np.count_nonzero(singular > tolerance))
        self.unique = self.rank == self.H
        self._coordinate_rows = vh[:self.rank].copy()
        self._inverse = ((vh[:self.rank].T / singular[:self.rank])
                         @ u[:, :self.rank].T)
        self._projector = self._coordinate_rows.T @ self._coordinate_rows
        self._projector = (self._projector + self._projector.T) * 0.5
        # Independent representation within this constructor certifies that
        # the informationally complete frame retained the available rank.
        physical_columns = np.concatenate((
            self._syndrome_states.real.reshape(self.H, -1),
            self._syndrome_states.imag.reshape(self.H, -1)), axis=1).T
        physical_singular = np.linalg.svd(physical_columns, compute_uv=False)
        physical_tolerance = (32 * np.finfo(float).eps
                              * max(physical_columns.shape) * physical_singular[0])
        available_rank = int(np.count_nonzero(physical_singular > physical_tolerance))
        if available_rank != self.rank:
            raise ValueError("noise-model rank is numerically unresolved")
        self.validation_residuals = {
            **recovery.validation_residuals,
            "frame_completeness": float(np.max(np.abs(
                self._bras.conjugate().T @ self._bras - np.eye(r)))),
            "response_normalization": float(np.max(np.abs(
                self._response.sum(axis=0) - 1))),
            "available_rank": available_rank,
            "response_rank_tolerance": float(tolerance),
            "physical_rank_tolerance": float(physical_tolerance),
        }

    def _validate_hypotheses(self, hypotheses):
        if not 1 <= len(hypotheses) <= 32:
            raise ValueError("between 1 and 32 channel hypotheses are required")
        result, names = [], set()
        for hypothesis in hypotheses:
            if not isinstance(hypothesis, Mapping):
                raise ValueError("each hypothesis must be a mapping")
            name = hypothesis.get("name")
            if not isinstance(name, str) or name in names:
                raise ValueError("hypothesis names must be unique strings")
            names.add(name)
            q = hypothesis.get("qubit")
            if isinstance(q, (bool, np.bool_)):
                raise ValueError("hypothesis qubit must be an integer")
            try:
                q = operator.index(q)
            except TypeError as exc:
                raise ValueError("hypothesis qubit must be an integer") from exc
            if not 0 <= q < self.n:
                raise ValueError("hypothesis qubit is out of range")
            operators = hypothesis.get("kraus")
            if operators is None or len(operators) == 0:
                raise ValueError("each hypothesis needs nonempty Kraus operators")
            kraus = []
            gram = np.zeros((2, 2), complex)
            for matrix in operators:
                matrix = np.asarray(matrix, dtype=complex)
                if matrix.shape != (2, 2) or not np.all(np.isfinite(matrix)):
                    raise ValueError("Kraus operators must be finite 2 by 2 matrices")
                matrix = matrix.copy()
                gram += matrix.conjugate().T @ matrix
                matrix.setflags(write=False)
                kraus.append(matrix)
            if np.max(np.abs(gram - np.eye(2))) > 5e-10:
                raise ValueError("hypothesis is not trace-preserving")
            result.append({"name": name, "qubit": q, "kraus": tuple(kraus)})
        return tuple(result)

    def _apply_local(self, state, qubit, matrix):
        mask = 1 << (self.n - 1 - qubit)
        words = np.arange(self.dimension)
        zero = words[(words & mask) == 0]
        one = zero | mask
        output = np.empty_like(state, dtype=complex)
        output[zero] = matrix[0, 0] * state[zero] + matrix[0, 1] * state[one]
        output[one] = matrix[1, 0] * state[zero] + matrix[1, 1] * state[one]
        return output

    def measurement_operators(self):
        """Fresh direct-coefficient sparse operators in response-row order."""
        return [[{int(word): complex(row[word]) for word in np.flatnonzero(row)}
                 for row in outcome] for outcome in self._operators]

    def response_matrix(self):
        """Outcome probabilities, excluding the unsupported-space erasure flag."""
        return self._response.copy()

    def identifiability(self):
        """The Euclidean row-space certificate includes weight normalization."""
        return {"rank": self.rank, "unique": self.unique,
                "identifiable_projector": self._projector.copy()}

    @staticmethod
    def _simplex_projection(vector):
        ordered = np.sort(vector)[::-1]
        shifted = np.cumsum(ordered) - 1
        indices = np.arange(1, len(vector) + 1)
        active = ordered - shifted / indices > 0
        last = np.flatnonzero(active)[-1]
        threshold = shifted[last] / (last + 1)
        weights = np.maximum(vector - threshold, 0)
        return weights / weights.sum()

    def estimate(self, observed):
        """Fit counts/probabilities and return a feasible mixture representative.

        The fit is Euclidean in identifiable parameter coordinates, after
        imposing normalization.  For exact model data it recovers every
        identifiable coordinate.  Finite-sample estimates can be biased
        at the boundary; these outputs are not confidence intervals.
        """
        raw = np.asarray(observed)
        if np.iscomplexobj(raw):
            raise ValueError("observations must be real")
        observed = np.asarray(raw, dtype=float)
        if observed.shape != (self.L,) or not np.all(np.isfinite(observed)):
            raise ValueError("observations must be a finite length-L vector")
        if np.any(observed < 0) or not np.any(observed > 0):
            raise ValueError("observations must be nonnegative with positive total")
        # Scaling first also avoids overflow for valid large finite counts.
        frequencies = observed / observed.max()
        frequencies = frequencies / math.fsum(float(x) for x in frequencies)
        linear = self._inverse @ frequencies
        linear += (1 - float(linear.sum())) / self.H
        rows = self._coordinate_rows
        target = rows @ linear
        if np.min(linear) >= -2e-12:
            weights = np.maximum(linear, 0)
            weights /= weights.sum()
        elif self.unique:
            weights = self._simplex_projection(linear)
        else:
            # This detects exact feasible quotient coordinates, including
            # nonunique mixtures whose minimum-norm representative is negative.
            feasible = linprog(
                np.zeros(self.H), A_eq=rows, b_eq=target,
                bounds=(0, None), method="highs",
                options={"primal_feasibility_tolerance": 1e-10,
                         "dual_feasibility_tolerance": 1e-10})
            if feasible.success:
                weights = np.maximum(feasible.x, 0)
                weights /= weights.sum()
            else:
                def objective(w):
                    residual = rows @ w - target
                    return 0.5 * float(residual @ residual)

                def gradient(w):
                    return rows.T @ (rows @ w - target)

                fitted = minimize(
                    objective, self._simplex_projection(linear), jac=gradient,
                    method="SLSQP", bounds=[(0, 1)] * self.H,
                    constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1,
                                  "jac": lambda w: np.ones(self.H)}],
                    options={"ftol": 1e-14, "maxiter": 2000})
                if not fitted.success:
                    raise RuntimeError("constrained mixture fit failed: " + fitted.message)
                weights = np.maximum(fitted.x, 0)
                weights /= weights.sum()
        return {"mixture_weights": weights,
                "identifiable_coordinates": self._projector @ weights,
                "predicted_frequencies": self._response @ weights,
                "unique": self.unique}

    def erasure_effect(self):
        """Return the physical-space effect of the one classical erasure flag.

        Its CP branch maps rho to trace(effect @ rho) times the erasure
        flag state.  It has no logical output and is excluded from A.
        """
        rows = self._recovery.reshape(-1, self.dimension)
        effect = np.eye(self.dimension) - rows.conjugate().T @ rows
        return (effect + effect.conjugate().T) * 0.5

    def execute(self, branches):
        """Execute on independent sparse pure-state branches, with raw mass.

        This accepts subnormalized states and mixed states represented as
        sums of branch outer products.  Outcome logical densities are
        unnormalized.  Erasure is the raw input mass minus recovered mass;
        a roundoff-sized negative residual is retained transparently.
        """
        densities = np.zeros((self.L, self.K, self.K), complex)
        input_masses = []
        for branch in branches:
            if not isinstance(branch, Mapping):
                raise ValueError("each input branch must be a sparse mapping")
            state = np.zeros(self.dimension, complex)
            for word, coefficient in branch.items():
                if isinstance(word, (bool, np.bool_)):
                    raise ValueError("physical indices must be integers")
                try:
                    word = operator.index(word)
                except TypeError as exc:
                    raise ValueError("physical indices must be integers") from exc
                coefficient = complex(coefficient)
                if not 0 <= word < self.dimension or not np.isfinite(coefficient):
                    raise ValueError("invalid physical coordinate or amplitude")
                state[word] = coefficient
            input_masses.append(float(np.vdot(state, state).real))
            output = self._operators @ state
            densities += output[:, :, None] * output[:, None, :].conjugate()
        probabilities = np.trace(densities, axis1=1, axis2=2).real
        logical_density = densities.sum(axis=0)
        raw_mass = math.fsum(input_masses)
        recovered_mass = float(probabilities.sum())
        return {"outcome_logical_densities": densities,
                "outcome_probabilities": probabilities,
                "logical_density": logical_density,
                "input_probability": raw_mass,
                "correctable_probability": recovered_mass,
                "erasure_probability": raw_mass - recovered_mass}
