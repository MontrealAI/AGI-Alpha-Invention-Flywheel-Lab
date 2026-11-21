"""Nondestructive, informationally complete local-noise experiments.

Recovery identifies the correctable physical space with syndrome x logical.
A fixed rank-one informationally complete POVM measures only syndrome. Its
one-Kraus branches return the logical state unchanged. The additional erasure
map is rho -> Tr((I-P_S) rho) |erasure><erasure|; it is not included among
response-matrix rows. No normalization of quantum input mass is performed.

The retained recovery.py is the sole nonstandard dependency. All numerical
work is local, CPU-only, and uses NumPy/SciPy. This construction promises
maximal linear identifiability, not optimal finite-shot efficiency.
"""
from __future__ import annotations

from collections.abc import Mapping
import operator

import numpy as np
from scipy.optimize import linprog, minimize

from recovery import Recovery


class NoiseExperiment:
    """Construct an experiment for a two-dimensional one-error-correcting code.

    Physical qubit zero is the most-significant bit. Exported dictionaries
    contain direct row coefficients, so no additional conjugation is needed.
    The public contract permits n <= 9 and up to 32 named local CPTP channels.
    """

    _VALIDATION_ATOL = 5e-10

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
            raise ValueError("exactly two ordered logical codewords are required")
        if not 1 <= len(hypotheses) <= 32:
            raise ValueError("between one and 32 hypotheses are required")
        self.K = 2
        self.dimension = 1 << self.n
        self._recovery = Recovery(self.n, codewords)
        self.syndrome_rank = self._recovery.syndrome_rank
        r = self.syndrome_rank

        recovery_rows = np.zeros((r, 2, self.dimension), dtype=complex)
        for s, rows in enumerate(self._recovery.kraus()):
            for i, row in enumerate(rows):
                for word, value in row.items():
                    recovery_rows[s, i, word] = value
        self._recovery_rows = recovery_rows
        code = np.zeros((self.dimension, 2), dtype=complex)
        for i, word in enumerate(codewords):
            for basis, amplitude in word.items():
                code[basis, i] = amplitude

        # The frame consists of e_i and all (e_i +/- e_j)/sqrt(2),
        # (e_i +/- i e_j)/sqrt(2). Its projector sum is (2r-1) I.
        # Coefficients below are bras, already including that normalization.
        frame = []
        labels = []
        denominator = 2*r - 1
        for i in range(r):
            row = np.zeros(r, dtype=complex)
            row[i] = 1/np.sqrt(denominator)
            frame.append(row)
            labels.append(("basis", i))
        for i in range(r):
            for j in range(i+1, r):
                for kind, phase in (("real", 1.0), ("imaginary", -1j)):
                    for sign in (1, -1):
                        row = np.zeros(r, dtype=complex)
                        row[i] = 1/np.sqrt(2*denominator)
                        row[j] = sign*phase/np.sqrt(2*denominator)
                        frame.append(row)
                        labels.append((kind, i, j, sign))
        self._frame = np.asarray(frame)
        self._labels = tuple(labels)
        self._operators = np.einsum(
            "os,skd->okd", self._frame, recovery_rows, optimize=True)

        names = []
        syndrome_densities = []
        max_channel_residual = 0.0
        max_branch_residual = 0.0
        for hypothesis in hypotheses:
            if not isinstance(hypothesis, Mapping):
                raise ValueError("each hypothesis must be a dictionary")
            name = hypothesis.get("name")
            if not isinstance(name, str) or name in names:
                raise ValueError("hypothesis names must be unique strings")
            names.append(name)
            qubit = hypothesis.get("qubit")
            if isinstance(qubit, (bool, np.bool_)):
                raise ValueError("hypothesis qubit must be an integer position")
            try:
                qubit = operator.index(qubit)
            except TypeError as exc:
                raise ValueError("hypothesis qubit must be an integer position") from exc
            if not 0 <= qubit < self.n:
                raise ValueError("hypothesis qubit is out of range")
            try:
                kraus = list(hypothesis["kraus"])
            except (KeyError, TypeError) as exc:
                raise ValueError("hypothesis requires a nonempty Kraus list") from exc
            if not kraus:
                raise ValueError("hypothesis requires a nonempty Kraus list")
            completeness = np.zeros((2, 2), dtype=complex)
            sigma = np.zeros((r, r), dtype=complex)
            for raw_matrix in kraus:
                try:
                    matrix = np.asarray(raw_matrix, dtype=complex)
                except (TypeError, ValueError, OverflowError) as exc:
                    raise ValueError("Kraus matrices must be finite complex 2x2 arrays") from exc
                if matrix.shape != (2, 2) or not np.all(np.isfinite(matrix)):
                    raise ValueError("Kraus matrices must be finite complex 2x2 arrays")
                completeness += matrix.conj().T @ matrix
                errored_code = self._apply_local(code, qubit, matrix)
                blocks = np.einsum("skd,di->ski", recovery_rows,
                                   errored_code, optimize=True)
                coefficients = np.trace(blocks, axis1=1, axis2=2)/2
                residual = np.max(np.abs(
                    blocks-coefficients[:, None, None]*np.eye(2)[None, :, :]))
                max_branch_residual = max(max_branch_residual, float(residual))
                sigma += np.outer(coefficients, coefficients.conj())
            channel_residual = float(np.max(np.abs(completeness-np.eye(2))))
            max_channel_residual = max(max_channel_residual, channel_residual)
            if channel_residual > self._VALIDATION_ATOL:
                raise ValueError("hypothesis Kraus matrices do not define a CPTP channel")
            syndrome_densities.append((sigma+sigma.conj().T)/2)
        if max_branch_residual > 2e-9:
            raise ValueError("noise fails the verified syndrome/logical factorization")
        self.hypothesis_names = tuple(names)
        self._syndrome_densities = np.asarray(syndrome_densities)
        response = np.column_stack([
            np.sum((self._frame @ sigma)*self._frame.conj(), axis=1).real
            for sigma in self._syndrome_densities
        ])
        probability_residual = float(np.max(np.abs(response.sum(axis=0)-1)))
        if np.min(response) < -2e-10 or probability_residual > 2e-9:
            raise ValueError("syndrome response is not a normalized probability model")
        # Only remove negative floating-point roundoff. Do not renormalize
        # response columns: they are the actual exported branch probabilities.
        self._response = np.maximum(response, 0.0)
        u, singular_values, vt = np.linalg.svd(self._response, full_matrices=False)
        rank_tolerance = (64*np.finfo(float).eps*max(self._response.shape)
                          *singular_values[0])
        rank = int(np.count_nonzero(singular_values > rank_tolerance))
        self._rank = rank
        self._unique = rank == len(hypotheses)
        self._u = u[:, :rank]
        self._singular_values = singular_values[:rank]
        self._vt = vt[:rank, :]
        self._projector = self._vt.T @ self._vt
        self._projector = (self._projector+self._projector.T)/2
        self.validation_residuals = {
            **self._recovery.validation_residuals,
            "channel_trace_preservation": max_channel_residual,
            "logical_branch_factorization": max_branch_residual,
            "response_column_normalization": probability_residual,
            "syndrome_frame_completeness": float(np.max(np.abs(
                self._frame.conj().T @ self._frame-np.eye(r)))),
            "identifiability_rank_tolerance": float(rank_tolerance),
        }
        for array in (self._recovery_rows, self._frame, self._operators,
                      self._syndrome_densities, self._response, self._u,
                      self._singular_values, self._vt, self._projector):
            array.setflags(write=False)

    def _apply_local(self, vectors, qubit, matrix):
        mask = 1 << (self.n-1-qubit)
        zero = np.arange(self.dimension)
        zero = zero[(zero & mask) == 0]
        one = zero | mask
        output = np.empty_like(vectors)
        output[zero] = matrix[0, 0]*vectors[zero]+matrix[0, 1]*vectors[one]
        output[one] = matrix[1, 0]*vectors[zero]+matrix[1, 1]*vectors[one]
        return output

    def measurement_operators(self):
        """Return all one-Kraus logical branches as fresh direct-row mappings.

        The complement is a classical erasure outcome, excluded from these
        rows and from response_matrix(). See erasure_effect() and measure().
        """
        return [[{int(word): complex(row[word])
                  for word in np.flatnonzero(row)}
                 for row in outcome] for outcome in self._operators]

    def outcome_labels(self):
        """Return immutable labels in the same order as the exported rows."""
        return self._labels

    def response_matrix(self):
        """Return A[o,h], independent of the unknown logical density."""
        return self._response.copy()

    def identifiability(self):
        """Certify the identifiable Euclidean quotient of mixture weights."""
        return {"rank": self._rank, "unique": self._unique,
                "identifiable_projector": self._projector.copy()}

    @staticmethod
    def _probability_vector(values):
        values = np.maximum(np.asarray(values, dtype=float), 0.0)
        total = values.sum()
        if not np.isfinite(total) or total <= 0:
            return np.full(len(values), 1/len(values))
        return values/total

    def estimate(self, observed):
        """Normalize classical observations and fit a simplex-constrained model.

        Exactly consistent observations are inverted on the identifiable
        quotient; linear programming finds a feasible representative if the
        minimum-norm inverse is not nonnegative. Otherwise constrained least
        squares fits the frequencies. In deficient models no representative
        is asserted to equal the unknown true mixture.
        """
        raw = np.asarray(observed)
        if np.iscomplexobj(raw):
            raise ValueError("observations must be real nonnegative counts or probabilities")
        try:
            values = np.asarray(observed, dtype=float)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("observations must be finite nonnegative numbers") from exc
        if (values.shape != (len(self._response),)
                or not np.all(np.isfinite(values)) or np.any(values < 0)):
            raise ValueError("observations must be a finite nonnegative length-L vector")
        largest = float(np.max(values))
        if largest <= 0:
            raise ValueError("observations must have positive total mass")
        # Scaling first prevents overflow when finite count values are large.
        frequencies = values/largest
        frequencies /= frequencies.sum()
        target = (self._u.T @ frequencies)/self._singular_values
        inverse = self._vt.T @ target
        projection_residual = float(np.linalg.norm(
            self._response @ inverse-frequencies))
        weights = None
        method = "constrained_least_squares"
        if projection_residual <= 1e-10:
            if np.min(inverse) >= -2e-11:
                candidate = self._probability_vector(inverse)
                if np.max(np.abs(self._vt @ candidate-target)) <= 2e-9:
                    weights = candidate
                    method = "identifiable_inverse"
            if weights is None:
                feasible = linprog(
                    np.zeros(len(inverse)), A_eq=self._vt, b_eq=target,
                    bounds=(0.0, 1.0), method="highs",
                    options={"primal_feasibility_tolerance": 1e-9,
                             "dual_feasibility_tolerance": 1e-9})
                if feasible.success:
                    candidate = self._probability_vector(feasible.x)
                    if np.max(np.abs(self._vt @ candidate-target)) <= 2e-8:
                        weights = candidate
                        method = "feasible_identifiable_inverse"
        if weights is None:
            initial = self._probability_vector(inverse)
            relative_singular = self._singular_values/self._singular_values[0]
            reduced = relative_singular[:, None]*self._vt
            reduced_target = relative_singular*target

            def objective(w):
                residual = reduced @ w-reduced_target
                return float(0.5*(residual @ residual)), reduced.T @ residual

            fit = minimize(
                objective, initial, jac=True, method="SLSQP",
                bounds=[(0.0, 1.0)]*len(inverse),
                constraints={"type": "eq", "fun": lambda w: np.sum(w)-1,
                             "jac": lambda w: np.ones(len(w))},
                options={"ftol": 1e-13, "maxiter": 2000, "disp": False})
            candidate = self._probability_vector(fit.x)
            # Preserve a valid feasible answer even on a solver stopping issue;
            # explicitly expose solver status instead of claiming convergence.
            if objective(candidate)[0] > objective(initial)[0]:
                candidate = initial
            weights = candidate
            status = str(fit.message)
            converged = bool(fit.success)
        else:
            status = "consistent observation model solved on its identifiable quotient"
            converged = True
        prediction = self._response @ weights
        return {"mixture_weights": weights,
                "identifiable_coordinates": self._projector @ weights,
                "predicted_frequencies": prediction,
                "unique": self._unique,
                "fit_method": method,
                "fit_converged": converged,
                "fit_status": status,
                "fit_residual_norm": float(np.linalg.norm(prediction-frequencies))}

    def erasure_effect(self):
        """Return I-P_S for the additional classical erasure outcome.

        Its output map is Tr((I-P_S) rho) times the erasure flag. This outcome
        may have multiple Kraus operators; every registered logical outcome
        returned by measurement_operators() has exactly one.
        """
        rows = self._recovery_rows.reshape(-1, self.dimension)
        effect = np.eye(self.dimension)-rows.conj().T @ rows
        return (effect+effect.conj().T)/2

    def measure(self, branches):
        """Execute the full instrument on independent sparse pure-state branches.

        A density can be supplied as any sum of outer products of these
        branches, including subnormalized inputs. Outcomes and erasure carry
        raw mass. The logical density is the unconditional sum over all
        registered logical outcomes. A zero input yields zero throughout.
        """
        density = np.zeros((2, 2), dtype=complex)
        probabilities = np.zeros(len(self._frame), dtype=float)
        input_mass = 0.0
        erasure_mass = 0.0
        for branch in branches:
            if not isinstance(branch, Mapping):
                raise ValueError("physical branches must be sparse mappings")
            vector = np.zeros(self.dimension, dtype=complex)
            for word, amplitude in branch.items():
                if isinstance(word, (bool, np.bool_)):
                    raise ValueError("physical words must be integer indices")
                try:
                    word = operator.index(word)
                    amplitude = complex(amplitude)
                except (TypeError, ValueError, OverflowError) as exc:
                    raise ValueError("invalid physical branch entry") from exc
                if not 0 <= word < self.dimension or not np.isfinite(amplitude):
                    raise ValueError("invalid physical branch entry")
                vector[word] = amplitude
            recovered = np.einsum("skd,d->sk", self._recovery_rows, vector)
            output = self._frame @ recovered
            density += output.T @ output.conj()
            probabilities += np.sum(np.abs(output)**2, axis=1)
            projected = np.einsum("skd,sk->d", self._recovery_rows.conj(), recovered)
            input_mass += float(np.vdot(vector, vector).real)
            complement = vector-projected
            erasure_mass += float(np.vdot(complement, complement).real)
        density = (density+density.conj().T)/2
        correctable_mass = float(np.sum(probabilities))
        return {"logical_density": density,
                "outcome_probabilities": probabilities,
                "input_probability": input_mass,
                "correctable_probability": correctable_mass,
                "erasure_probability": erasure_mass,
                "mass_balance_residual": correctable_mass+erasure_mass-input_mass}
