"""Nondestructive identification of local channel mixtures on exact quantum codes.

The correctable span is factored as logical space tensor syndrome space by the
Knill--Laflamme Gram matrix.  A finite rank-one informationally complete POVM is
applied to the syndrome.  Its implementation also decodes the logical factor.
Only NumPy and SciPy are required; no execution-time data or network is used.
"""

import numpy as np
from scipy.optimize import linprog, minimize


_PAULIS = (
    np.eye(2, dtype=complex),
    np.array([[0, 1], [1, 0]], dtype=complex),
    np.array([[0, -1j], [1j, 0]], dtype=complex),
    np.diag([1, -1]).astype(complex),
)


def _local(matrix, code, n, qubit):
    """Apply a local operator to columns; physical qubit zero is the MSB."""
    words = np.arange(1 << n)
    mask = 1 << (n - 1 - qubit)
    result = np.zeros_like(code, dtype=complex)
    for old in range(2):
        source = words[((words & mask) != 0) == bool(old)]
        for new in range(2):
            target = (source & ~mask) | (new * mask)
            result[target] += matrix[new, old] * code[source]
    return result


class NoiseExperiment:
    """Construct a complete instrument and an identifiable classical model.

    Registered outcomes each have one Kraus map from the physical Hilbert space
    to the two-dimensional logical Hilbert space.  ``erasure_operators`` gives
    Kraus maps to a separate scalar erasure flag for the orthogonal complement.
    Returned sparse dictionaries contain direct coefficients, not ket entries.
    """

    def __init__(self, n, codewords, hypotheses):
        if not isinstance(n, (int, np.integer)) or not 1 <= n <= 9:
            raise ValueError("n must be an integer in the qualified range 1..9")
        if len(codewords) != 2:
            raise ValueError("exactly two ordered logical codewords are required")
        if not 1 <= len(hypotheses) <= 32:
            raise ValueError("between one and 32 hypotheses are required")
        self.n = int(n)
        self.dimension = 1 << self.n
        code = np.zeros((self.dimension, 2), dtype=complex)
        for a, word in enumerate(codewords):
            for coordinate, amplitude in word.items():
                if (not isinstance(coordinate, (int, np.integer)) or
                        not 0 <= coordinate < self.dimension):
                    raise ValueError("code coordinate out of range")
                code[int(coordinate), a] = complex(amplitude)
        if not np.all(np.isfinite(code)):
            raise ValueError("codewords must have finite coefficients")
        if np.max(np.abs(code.conj().T @ code - np.eye(2))) > 2e-8:
            raise ValueError("codewords must be orthonormal")

        errors = [code]
        for qubit in range(self.n):
            errors.extend(_local(p, code, self.n, qubit) for p in _PAULIS[1:])
        errors = np.asarray(errors)  # error, physical coordinate, logical index
        blocks = [errors[:, :, a].T for a in range(2)]
        gram = (blocks[0].conj().T @ blocks[0] +
                blocks[1].conj().T @ blocks[1]) / 2
        gram = (gram + gram.conj().T) / 2
        for a in range(2):
            for b in range(2):
                target = gram if a == b else np.zeros_like(gram)
                if np.max(np.abs(blocks[a].conj().T @ blocks[b] - target)) > 2e-8:
                    raise ValueError("code does not correct the full one-qubit error span")
        eigenvalues, eigenvectors = np.linalg.eigh(gram)
        threshold = 64 * len(gram) * np.finfo(float).eps * max(1., eigenvalues[-1])
        keep = eigenvalues > threshold
        if not np.any(keep) or np.min(eigenvalues) < -threshold:
            raise ValueError("invalid correctable-span Gram matrix")
        eigenvalues, eigenvectors = eigenvalues[keep], eigenvectors[:, keep]
        self.syndrome_dimension = len(eigenvalues)
        self._isometries = np.asarray([
            (block @ eigenvectors) / np.sqrt(eigenvalues)[None, :]
            for block in blocks
        ])  # logical, physical, syndrome
        syndrome_errors = np.sqrt(eigenvalues)[:, None] * eigenvectors.conj().T

        # These effects span every Hermitian syndrome operator.  Their sum is I:
        # four normalized pair vectors contribute 2(|i><i|+|j><j|).
        size = self.syndrome_dimension
        vectors = []
        scale = np.sqrt(2 * size - 1)
        for i in range(size):
            vector = np.zeros(size, dtype=complex)
            vector[i] = 1 / scale
            vectors.append(vector)
        for i in range(size):
            for j in range(i + 1, size):
                for phase in (1., -1., 1j, -1j):
                    vector = np.zeros(size, dtype=complex)
                    vector[i] = 1 / (np.sqrt(2) * scale)
                    vector[j] = phase / (np.sqrt(2) * scale)
                    vectors.append(vector)
        self._vectors = np.asarray(vectors)
        self._operators = np.einsum(
            "os,ads->oad", self._vectors.conj(), self._isometries.conj(),
            optimize=True,
        )

        names = []
        response = []
        for hypothesis in hypotheses:
            name, qubit = hypothesis["name"], hypothesis["qubit"]
            if not isinstance(name, str) or name in names:
                raise ValueError("hypothesis names must be unique strings")
            names.append(name)
            if (not isinstance(qubit, (int, np.integer)) or
                    not 0 <= qubit < self.n):
                raise ValueError("hypothesis qubit out of range")
            kraus = [np.asarray(k, dtype=complex) for k in hypothesis["kraus"]]
            if not kraus or any(k.shape != (2, 2) or not np.all(np.isfinite(k))
                                for k in kraus):
                raise ValueError("nonempty finite 2x2 Kraus matrices are required")
            trace_preservation = sum(k.conj().T @ k for k in kraus)
            if np.max(np.abs(trace_preservation - np.eye(2))) > 2e-8:
                raise ValueError("hypothesis is not trace preserving")
            probability = np.zeros(len(vectors))
            for operator in kraus:
                expansion = np.array([np.trace(p.conj().T @ operator) / 2
                                      for p in _PAULIS])
                coefficients = np.zeros(1 + 3 * self.n, dtype=complex)
                coefficients[0] = expansion[0]
                coefficients[1 + 3 * qubit:4 + 3 * qubit] = expansion[1:]
                syndrome = syndrome_errors @ coefficients
                probability += np.abs(self._vectors.conj() @ syndrome) ** 2
            response.append(probability)
        self.names = tuple(names)
        self._response = np.asarray(response).T
        u, singular_values, vh = np.linalg.svd(self._response, full_matrices=False)
        rank_tolerance = (64 * max(self._response.shape) * np.finfo(float).eps *
                          singular_values[0])
        self._rank = int(np.count_nonzero(singular_values > rank_tolerance))
        self._u = u[:, :self._rank]
        self._s = singular_values[:self._rank]
        self._v = vh[:self._rank, :]
        self._projector = self._v.T @ self._v
        self._projector = (self._projector + self._projector.T) / 2

    def measurement_operators(self):
        """Return registered Kraus operators as lists of two sparse direct rows."""
        return [[{int(i): complex(row[i]) for i in np.flatnonzero(row)}
                 for row in operator] for operator in self._operators]

    def response_matrix(self):
        """Return outcome probabilities with hypothesis order preserved."""
        return self._response.copy()

    def identifiability(self):
        """Euclidean identifiable quotient; the normalization direction is included."""
        return {"rank": self._rank, "unique": self._rank == len(self.names),
                "identifiable_projector": self._projector.copy()}

    def correctable_projector(self):
        """Projector onto all one-qubit Pauli images of the code."""
        return sum(u @ u.conj().T for u in self._isometries)

    def erasure_operators(self):
        """Kraus operators into a separate one-dimensional erasure output.

        There is one (possibly zero) row per physical coordinate.  All rows are
        grouped into the same classical erasure outcome.  Their adjoint products
        sum to I-P_S, so the registered outcomes plus this flag are CPTP.
        """
        complement = np.eye(self.dimension) - self.correctable_projector()
        return [[{int(i): complex(row[i]) for i in np.flatnonzero(row)}]
                for row in complement]

    def apply(self, state):
        """Execute the instrument on a sparse/dense ket or physical density.

        Unnormalized inputs retain their raw mass. ``logical_density`` is the
        unconditional registered output; it is not divided by success mass.
        ``outcome_logical_densities`` retain the individual measurement branches.
        """
        if isinstance(state, dict):
            vector = np.zeros(self.dimension, dtype=complex)
            for coordinate, amplitude in state.items():
                if not 0 <= coordinate < self.dimension:
                    raise ValueError("state coordinate out of range")
                vector[coordinate] = amplitude
            state = vector
        state = np.asarray(state, dtype=complex)
        if not np.all(np.isfinite(state)):
            raise ValueError("state must be finite")
        if state.shape == (self.dimension,):
            branches = self._operators @ state
            densities = branches[:, :, None] * branches[:, None, :].conj()
            input_probability = float(np.vdot(state, state).real)
            residual = state - sum(u @ (u.conj().T @ state)
                                   for u in self._isometries)
            erasure_probability = float(np.vdot(residual, residual).real)
        elif state.shape == (self.dimension, self.dimension):
            densities = np.einsum("oai,ij,obj->oab", self._operators, state,
                                  self._operators.conj(), optimize=True)
            input_probability = float(np.trace(state).real)
            complement = np.eye(self.dimension) - self.correctable_projector()
            erasure_probability = float(np.trace(complement @ state @ complement.conj().T).real)
        else:
            raise ValueError("state must be a physical ket or density matrix")
        return {"outcome_probabilities": np.trace(densities, axis1=1, axis2=2).real,
                "outcome_logical_densities": densities,
                "logical_density": densities.sum(axis=0),
                "erasure_probability": erasure_probability,
                "input_probability": input_probability}

    def estimate(self, observed):
        """Fit normalized classical observations over the probability simplex.

        Exact model probabilities use a pseudoinverse and, where necessary, a
        feasibility LP in independent identifiable coordinates. General counts
        use constrained least squares. Nonunique weights are representatives.
        """
        observed = np.asarray(observed, dtype=float)
        if (observed.shape != (self._response.shape[0],) or
                not np.all(np.isfinite(observed)) or np.any(observed < 0)):
            raise ValueError("observations must be a finite nonnegative outcome vector")
        total = float(observed.sum())
        if not np.isfinite(total) or total <= 0:
            raise ValueError("observations must have a finite positive total")
        y = observed / total
        coordinates = (self._u.T @ y) / self._s
        unconstrained = self._v.T @ coordinates
        weights = None
        is_model_vector = np.max(np.abs(self._response @ unconstrained - y)) <= 2e-11
        if is_model_vector and unconstrained.min() >= -2e-10:
            weights = np.maximum(unconstrained, 0)
        elif is_model_vector:
            feasible = linprog(
                np.zeros(len(self.names)),
                A_eq=np.vstack((self._v, np.ones((1, len(self.names))))),
                b_eq=np.r_[coordinates, 1.], bounds=(0., None), method="highs",
                options={"primal_feasibility_tolerance": 1e-9,
                         "dual_feasibility_tolerance": 1e-9},
            )
            if feasible.success:
                weights = np.maximum(feasible.x, 0)
        if weights is None:
            initial = np.maximum(unconstrained, 0)
            if initial.sum() <= 0:
                initial = np.ones(len(self.names))
            initial /= initial.sum()
            # Scaling keeps the probability least-squares Hessian near unit size.
            scale = self._s[0]
            matrix, target = self._response / scale, y / scale
            def objective(w):
                residual = matrix @ w - target
                return .5 * np.dot(residual, residual)
            def gradient(w):
                return matrix.T @ (matrix @ w - target)
            fit = minimize(
                objective, initial, jac=gradient, method="SLSQP",
                bounds=[(0., 1.)] * len(self.names),
                constraints={"type": "eq", "fun": lambda w: w.sum() - 1.,
                             "jac": lambda w: np.ones_like(w)},
                options={"ftol": 1e-14, "maxiter": 2000},
            )
            candidate = np.maximum(fit.x, 0)
            if np.all(np.isfinite(candidate)) and candidate.sum() > 0:
                candidate /= candidate.sum()
                weights = candidate if objective(candidate) <= objective(initial) else initial
            else:
                weights = initial
        weights /= weights.sum()
        return {"mixture_weights": weights,
                "identifiable_coordinates": self._projector @ weights,
                "predicted_frequencies": self._response @ weights,
                "unique": self._rank == len(self.names)}
