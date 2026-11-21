"""Nondestructive identification of mixtures of correctable local channels.

The supplied Recovery supplies orthogonal syndrome decoders R_a, with
R_a E V = c_a(E) I on the complete single-qubit error space.  An explicit
rank-one informationally complete POVM measures only this syndrome.  Its
outcomes decode to the same, unknown logical state.  No logical probe is
selected, and no outcome is postselected.

The only nonstandard dependency is the supplied, frozen recovery.py.
All calculations are local CPU calculations using NumPy and SciPy.
"""

from __future__ import annotations

import math
from numbers import Integral

import numpy as np
from scipy.optimize import minimize, nnls

from recovery import Recovery


class NoiseExperiment:
    """Construct a complete noise-identification instrument for a K=2 code.

    ``measurement_operators`` exports direct coefficients, not ket vectors.
    Registered outcomes have one Kraus operator each.  An extra classical
    erasure outcome, excluded from ``response_matrix``, is implemented by
    ``measure`` and also exposed through ``erasure_effect`` and
    ``erasure_operators``.  These methods preserve subnormalized raw mass.

    Numerical ranks are intended for the separated singular spectra of the
    public contract.  Statistical estimates are constrained least-squares
    estimates; no finite-shot precision or experiment-design optimality is
    asserted.
    """

    def __init__(self, n: int, codewords: list[dict[int, complex]],
                 hypotheses: list[dict]):
        if isinstance(n, bool) or not isinstance(n, Integral) or not 1 <= n <= 9:
            raise ValueError("n must be an integer in 1..9")
        if (not isinstance(codewords, (list, tuple)) or len(codewords) != 2
                or not all(isinstance(c, dict) for c in codewords)):
            raise ValueError("Supply two sparse logical codewords")
        if sum(map(len, codewords)) > 2048:
            raise ValueError("At most 2048 code amplitudes are supported")
        if not isinstance(hypotheses, (list, tuple)) or not 1 <= len(hypotheses) <= 32:
            raise ValueError("Supply between one and 32 channel hypotheses")
        self.n, self.dimension, self.k = int(n), 1 << int(n), 2
        self.hypothesis_count = len(hypotheses)
        self._recovery = Recovery(self.n, codewords)
        self._code = np.zeros((self.dimension, self.k), dtype=complex)
        for j, state in enumerate(codewords):
            for word, amplitude in state.items():
                self._code[int(word), j] = complex(amplitude)

        sparse_decoders = self._recovery.kraus()
        self.syndrome_rank = len(sparse_decoders)
        self._decoders = np.zeros((self.syndrome_rank, self.k, self.dimension),
                                  dtype=complex)
        for a, rows in enumerate(sparse_decoders):
            for j, row in enumerate(rows):
                for word, coefficient in row.items():
                    self._decoders[a, j, word] = coefficient

        self._hypotheses = self._validate_hypotheses(hypotheses)
        self.names = tuple(h["name"] for h in self._hypotheses)
        self._syndrome_states = np.zeros(
            (self.hypothesis_count, self.syndrome_rank, self.syndrome_rank),
            dtype=complex)
        scalar_error = 0.0
        for h, hypothesis in enumerate(self._hypotheses):
            for operator in hypothesis["kraus"]:
                images = self._apply_local(self._code, hypothesis["qubit"], operator)
                decoded = np.einsum("akd,dj->akj", self._decoders, images,
                                    optimize=True)
                amplitudes = np.trace(decoded, axis1=1, axis2=2) / self.k
                scalar_error = max(scalar_error, float(np.max(np.abs(
                    decoded - amplitudes[:, None, None] * np.eye(self.k)))))
                self._syndrome_states[h] += np.outer(amplitudes, amplitudes.conj())
        if scalar_error > 1e-8:
            raise ValueError("Noise does not act as a logical-independent syndrome")
        self.scalar_nondisturbance_residual = scalar_error

        # Row vectors w_o give POVM effects w_o^* w_o.  Basis vectors and
        # both real/imaginary pair superpositions sum to (2r-1) I before
        # scaling.  Their probabilities determine every Hermitian entry.
        self._frame = self._informationally_complete_frame(self.syndrome_rank)
        self._operators = np.einsum("oa,ajd->ojd", self._frame, self._decoders,
                                    optimize=True)
        response = np.einsum("oa,hab,ob->oh", self._frame,
                             self._syndrome_states, self._frame.conj(),
                             optimize=True)
        if np.max(np.abs(response.imag)) > 1e-9 or np.min(response.real) < -1e-9:
            raise ValueError("Invalid syndrome measurement probabilities")
        self._response = np.maximum(response.real, 0.0)
        if np.max(np.abs(self._response.sum(axis=0) - 1)) > 1e-8:
            raise ValueError("Supported noise probabilities do not sum to one")
        self.outcome_count = self._response.shape[0]

        _, singular, right = np.linalg.svd(self._response, full_matrices=False)
        self._rank = self._numerical_rank(singular, self._response.shape)
        self._projector = right[:self._rank].T @ right[:self._rank]
        self._projector = (self._projector + self._projector.T) / 2
        self._unique = self._rank == self.hypothesis_count
        # This is an independent representation of the full physical model
        # up to an isometry, so the IC response must have this same rank.
        physical_model = np.concatenate(
            (self._syndrome_states.real.reshape(self.hypothesis_count, -1),
             self._syndrome_states.imag.reshape(self.hypothesis_count, -1)),
            axis=1).T
        physical_singular = np.linalg.svd(physical_model, compute_uv=False)
        self.available_rank = self._numerical_rank(physical_singular,
                                                   physical_model.shape)
        if self.available_rank != self._rank:
            raise ValueError("Numerical rank is not separated sufficiently for certification")
        self._gram = self._response.T @ self._response
        self._objective_scale = float(singular[0] ** 2)

    @staticmethod
    def _numerical_rank(singular, shape):
        if not len(singular) or singular[0] == 0:
            return 0
        cutoff = 32 * np.finfo(float).eps * max(shape) * singular[0]
        return int(np.count_nonzero(singular > cutoff))

    def _validate_hypotheses(self, hypotheses):
        validated, names = [], set()
        for hypothesis in hypotheses:
            if not isinstance(hypothesis, dict):
                raise ValueError("Each hypothesis must be a dictionary")
            name = hypothesis.get("name")
            if not isinstance(name, str) or name in names:
                raise ValueError("Hypothesis names must be unique strings")
            names.add(name)
            qubit = hypothesis.get("qubit")
            if (isinstance(qubit, bool) or not isinstance(qubit, Integral)
                    or not 0 <= qubit < self.n):
                raise ValueError("Hypothesis qubit is outside the code")
            supplied = hypothesis.get("kraus")
            if not isinstance(supplied, (list, tuple)) or not supplied:
                raise ValueError("Each channel needs a nonempty list of Kraus matrices")
            kraus = []
            for operator in supplied:
                matrix = np.asarray(operator, dtype=complex)
                if matrix.shape != (2, 2) or not np.isfinite(matrix).all():
                    raise ValueError("Local Kraus matrices must be finite 2x2 matrices")
                kraus.append(matrix.copy())
            completeness = sum((k.conj().T @ k for k in kraus),
                               np.zeros((2, 2), dtype=complex))
            if np.max(np.abs(completeness - np.eye(2))) > 1e-9:
                raise ValueError("Hypothesis is not a trace-preserving quantum channel")
            validated.append({"name": name, "qubit": int(qubit), "kraus": kraus})
        return validated

    def _apply_local(self, state_columns, qubit, matrix):
        words = np.arange(self.dimension)
        mask = 1 << (self.n - 1 - qubit)
        bits = ((words & mask) != 0).astype(int)
        low = words & ~mask
        high = low | mask
        return (matrix[bits, 0, None] * state_columns[low]
                + matrix[bits, 1, None] * state_columns[high])

    @staticmethod
    def _informationally_complete_frame(rank):
        frame = np.zeros((2 * rank * rank - rank, rank), dtype=complex)
        normalizer = math.sqrt(2 * rank - 1)
        frame[:rank] = np.eye(rank) / normalizer
        row = rank
        for a in range(rank):
            for b in range(a + 1, rank):
                for phase in (1, -1, 1j, -1j):
                    frame[row, a] = 1 / (math.sqrt(2) * normalizer)
                    frame[row, b] = phase / (math.sqrt(2) * normalizer)
                    row += 1
        return frame

    def measurement_operators(self):
        """Return K-row sparse direct coefficients, in response-row order."""
        return [[{int(word): complex(row[word]) for word in np.flatnonzero(row)}
                 for row in operator] for operator in self._operators]

    def response_matrix(self):
        """Return registered outcome probabilities, with hypotheses in input order."""
        return self._response.copy()

    def identifiability(self):
        """Certify the full identifiable quotient, including normalization."""
        return {"rank": self._rank, "unique": bool(self._unique),
                "identifiable_projector": self._projector.copy()}

    def estimate(self, observed):
        """Fit nonnegative mixture weights after explicitly normalizing counts.

        Ideal model probabilities use an exact feasible nonnegative solution
        whenever found.  Other observations are fitted over the probability
        simplex.  For deficient rank, the weights are only a representative;
        the identifiable coordinates and fitted probabilities are invariant
        across observationally equivalent representatives.
        """
        raw = np.asarray(observed)
        if np.iscomplexobj(raw):
            raise ValueError("Observations must be real counts or probabilities")
        counts = np.asarray(raw, dtype=float)
        if (counts.shape != (self.outcome_count,) or not np.isfinite(counts).all()
                or np.min(counts) < 0):
            raise ValueError("Observations must be a finite nonnegative outcome vector")
        largest = float(np.max(counts))
        if largest <= 0:
            raise ValueError("Zero total observations cannot be estimated")
        # Scaling first also normalizes valid counts whose raw sum overflows.
        frequencies = counts / largest
        frequencies /= math.fsum(map(float, frequencies))

        status = "exact_model"
        try:
            weights, _ = nnls(self._response, frequencies,
                              maxiter=100 * self.hypothesis_count)
        except RuntimeError:
            weights = np.ones(self.hypothesis_count)
        total = float(weights.sum())
        weights = (weights / total if total > 0
                   else np.full(self.hypothesis_count, 1 / self.hypothesis_count))
        if np.max(np.abs(self._response @ weights - frequencies)) > 1e-11:
            linear = self._response.T @ frequencies
            scale = self._objective_scale

            def objective(x):
                return float((0.5 * x @ self._gram @ x - linear @ x) / scale)

            def gradient(x):
                return (self._gram @ x - linear) / scale

            fitted = minimize(
                objective, weights, jac=gradient, method="SLSQP",
                bounds=[(0.0, 1.0)] * self.hypothesis_count,
                constraints={"type": "eq", "fun": lambda x: float(x.sum() - 1),
                             "jac": lambda x: np.ones(self.hypothesis_count)},
                options={"ftol": 1e-14, "maxiter": 1000})
            candidate = np.maximum(np.asarray(fitted.x, dtype=float), 0)
            if np.isfinite(candidate).all() and candidate.sum() > 0:
                candidate /= candidate.sum()
                if objective(candidate) <= objective(weights) + 1e-15:
                    weights = candidate
            status = ("constrained_least_squares" if fitted.success
                      else "feasible_nonnegative_fit")
        prediction = self._response @ weights
        return {"mixture_weights": weights.copy(),
                "identifiable_coordinates": self._projector @ weights,
                "predicted_frequencies": prediction,
                "unique": bool(self._unique), "fit_status": status,
                "residual_norm": float(np.linalg.norm(prediction - frequencies))}

    def erasure_effect(self):
        """Return I-P_S, the effect for the single classical erasure outcome."""
        decoder = self._decoders.reshape(-1, self.dimension)
        complement = np.eye(self.dimension) - decoder.conj().T @ decoder
        return (complement + complement.conj().T) / 2

    def erasure_operators(self):
        """Return row Kraus operators for the one-dimensional erasure flag.

        Rows of I-P_S are a (possibly redundant) Kraus representation since
        this matrix is a projector.  All these Kraus branches share one
        classical erasure label; they are excluded from registered outcomes.
        """
        return [{int(word): complex(row[word]) for word in np.flatnonzero(row)}
                for row in self.erasure_effect()]

    def _dense_state(self, state):
        if not isinstance(state, dict):
            raise ValueError("A pure branch must be a sparse dictionary")
        vector = np.zeros(self.dimension, dtype=complex)
        for word, amplitude in state.items():
            if (isinstance(word, bool) or not isinstance(word, Integral)
                    or not 0 <= word < self.dimension):
                raise ValueError("A physical coordinate is outside the code space")
            value = complex(amplitude)
            if not math.isfinite(value.real) or not math.isfinite(value.imag):
                raise ValueError("Branch amplitudes must be finite")
            vector[int(word)] = value
        return vector

    def measure(self, branches):
        """Execute the entire instrument on incoherent, unnormalized pure branches.

        Return every registered logical density and probability, their sum,
        and the raw erasure/input mass.  Tiny signed erasure residuals due to
        floating-point roundoff are retained rather than hidden by rescaling.
        """
        if not isinstance(branches, (list, tuple)):
            raise ValueError("Supply a list of sparse unnormalized pure branches")
        densities = np.zeros((self.outcome_count, self.k, self.k), dtype=complex)
        masses = []
        for supplied in branches:
            state = self._dense_state(supplied)
            masses.append(float(np.vdot(state, state).real))
            decoded = np.einsum("ojd,d->oj", self._operators, state, optimize=True)
            densities += np.einsum("oi,oj->oij", decoded, decoded.conj())
        input_mass = math.fsum(masses)
        if not math.isfinite(input_mass):
            raise ValueError("Input probability exceeds finite floating-point range")
        probabilities = np.trace(densities, axis1=1, axis2=2).real
        logical_density = densities.sum(axis=0)
        correctable = float(probabilities.sum())
        return {"outcome_logical_densities": densities,
                "outcome_probabilities": probabilities,
                "logical_density": logical_density,
                "input_probability": input_mass,
                "correctable_probability": correctable,
                "erasure_probability": input_mass - correctable}
