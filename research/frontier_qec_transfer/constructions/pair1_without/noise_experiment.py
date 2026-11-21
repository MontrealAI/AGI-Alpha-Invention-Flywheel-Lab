"""Nondestructive identification of mixtures of correctable local channels.

The code obeys the Knill--Laflamme conditions for the complete one-qubit
Pauli error span.  An orthonormal syndrome/logical factorization of that
span is constructed directly from those conditions.  A rank-one,
informationally complete syndrome POVM extracts all linearly available
noise information and discards only the syndrome.  Each registered
operator maps physical amplitudes to unnormalized logical amplitudes.

No logical state is supplied to, estimated by, or assumed by the design.
The implementation uses only NumPy, SciPy, and the standard library.
"""

import numpy as np
from scipy.optimize import linprog, minimize


_PAULIS = (
    np.array([[0, 1], [1, 0]], dtype=complex),
    np.array([[0, -1j], [1j, 0]], dtype=complex),
    np.array([[1, 0], [0, -1]], dtype=complex),
)


def _local_columns(columns, n, qubit, matrix):
    """Apply matrix[out_bit, in_bit], with physical qubit 0 the MSB."""
    mask = 1 << (n - qubit - 1)
    lower = np.arange(1 << n)
    lower = lower[(lower & mask) == 0]
    upper = lower | mask
    result = np.empty_like(columns, dtype=complex)
    result[lower] = matrix[0, 0] * columns[lower] + matrix[0, 1] * columns[upper]
    result[upper] = matrix[1, 0] * columns[lower] + matrix[1, 1] * columns[upper]
    return result


def _simplex_projection(values):
    """Euclidean projection onto nonnegative vectors of unit sum."""
    values = np.asarray(values, dtype=float)
    ordered = np.sort(values)[::-1]
    excess = np.cumsum(ordered) - 1.0
    positive = np.flatnonzero(ordered - excess / np.arange(1, len(values) + 1) > 0)
    index = int(positive[-1])
    return np.maximum(values - excess[index] / (index + 1), 0.0)


class NoiseExperiment:
    """Construct a complete nondestructive experiment for local noise.

    Required methods are measurement_operators, response_matrix,
    identifiability, and estimate.  erasure_effect, erasure_operators, and
    apply_instrument expose the complementary classical erasure outcome.
    apply_instrument preserves raw mass, including subnormalized inputs.
    """

    def __init__(self, n, codewords, hypotheses):
        if isinstance(n, (bool, np.bool_)) or not isinstance(n, (int, np.integer)):
            raise ValueError("n must be an integer")
        if not 1 <= n <= 9:
            raise ValueError("the supported finite domain is 1 <= n <= 9")
        self.n = int(n)
        self.dimension = 1 << self.n
        if len(codewords) != 2:
            raise ValueError("exactly two ordered logical basis states are required")
        self.logical_dimension = 2
        if sum(len(word) for word in codewords) > 2048:
            raise ValueError("the code exceeds the supported amplitude count")
        code = np.zeros((self.dimension, 2), dtype=complex)
        for logical, word in enumerate(codewords):
            if not isinstance(word, dict):
                raise ValueError("each codeword must be an integer-coordinate dictionary")
            for coordinate, amplitude in word.items():
                if (isinstance(coordinate, (bool, np.bool_)) or
                        not isinstance(coordinate, (int, np.integer)) or
                        not 0 <= coordinate < self.dimension):
                    raise ValueError("invalid physical basis coordinate")
                code[int(coordinate), logical] = complex(amplitude)
        if not np.all(np.isfinite(code)):
            raise ValueError("code amplitudes must be finite")
        if np.max(np.abs(code.conj().T @ code - np.eye(2))) > 2e-8:
            raise ValueError("codewords must be orthonormal")
        self._code = code

        if not 1 <= len(hypotheses) <= 32:
            raise ValueError("between one and 32 channel hypotheses are required")
        names = set()
        channels = []
        for hypothesis in hypotheses:
            name = hypothesis.get("name")
            qubit = hypothesis.get("qubit")
            if not isinstance(name, str) or name in names:
                raise ValueError("hypothesis names must be unique strings")
            names.add(name)
            if (isinstance(qubit, (bool, np.bool_)) or
                    not isinstance(qubit, (int, np.integer)) or
                    not 0 <= qubit < self.n):
                raise ValueError("invalid channel qubit")
            operators = [np.array(k, dtype=complex, copy=True)
                         for k in hypothesis.get("kraus", [])]
            if not operators or any(k.shape != (2, 2) or not np.all(np.isfinite(k))
                                    for k in operators):
                raise ValueError("each channel needs finite 2 by 2 Kraus matrices")
            trace_effect = sum((k.conj().T @ k for k in operators),
                               np.zeros((2, 2), dtype=complex))
            if np.max(np.abs(trace_effect - np.eye(2))) > 2e-8:
                raise ValueError("channel Kraus operators must be trace preserving")
            channels.append((name, int(qubit), tuple(operators)))
        self.hypothesis_names = tuple(channel[0] for channel in channels)
        self._channels = tuple(channels)

        # F[:, logical, error] contains the complete one-qubit error frame.
        images = [code]
        for qubit in range(self.n):
            images.extend(_local_columns(code, self.n, qubit, pauli)
                          for pauli in _PAULIS)
        frame = np.stack(images, axis=2)
        gram = sum(frame[:, logical, :].conj().T @ frame[:, logical, :]
                   for logical in range(2)) / 2.0
        gram = (gram + gram.conj().T) / 2.0
        kl_error = 0.0
        for left in range(2):
            for right in range(2):
                block = frame[:, left, :].conj().T @ frame[:, right, :]
                expected = gram if left == right else 0.0
                kl_error = max(kl_error, float(np.max(np.abs(block - expected))))
        if kl_error > 2e-8:
            raise ValueError("the code does not correct the full one-qubit error span")
        eigenvalues, eigenvectors = np.linalg.eigh(gram)
        eigen_tolerance = (64 * np.finfo(float).eps * gram.shape[0] *
                           max(1.0, float(eigenvalues[-1])))
        if eigenvalues[0] < -2e-8:
            raise ValueError("invalid error Gram matrix")
        keep = eigenvalues > eigen_tolerance
        if not np.any(keep):
            raise ValueError("empty correctable span")
        transform = eigenvectors[:, keep] / np.sqrt(eigenvalues[keep])[None, :]
        basis = np.einsum("dka,as->dks", frame, transform, optimize=True)
        self.syndrome_dimension = int(np.count_nonzero(keep))
        self._basis = basis
        self._span_basis = basis.transpose(0, 2, 1).reshape(self.dimension, -1)
        orthogonality_error = np.max(np.abs(
            self._span_basis.conj().T @ self._span_basis -
            np.eye(self._span_basis.shape[1])))
        if orthogonality_error > 2e-8:
            raise ValueError("the correctable span is numerically ill conditioned")

        # The union of a coordinate basis and both signs of every real and
        # imaginary pair is a tight rank-one informationally complete frame.
        # Sum_o |v_o><v_o| = I: the unscaled sum is (2*r - 1)*I.
        rank = self.syndrome_dimension
        scale = 1.0 / np.sqrt(2 * rank - 1)
        vectors = [scale * np.eye(rank, dtype=complex)[j] for j in range(rank)]
        for j in range(rank):
            for k in range(j + 1, rank):
                for phase in (1.0, -1.0, 1j, -1j):
                    vector = np.zeros(rank, dtype=complex)
                    vector[j] = scale / np.sqrt(2.0)
                    vector[k] = phase * scale / np.sqrt(2.0)
                    vectors.append(vector)
        self._povm_vectors = np.asarray(vectors)
        self._operators = np.einsum("os,dks->okd", self._povm_vectors.conj(),
                                    basis.conj(), optimize=True)

        syndrome_densities = []
        for _, qubit, kraus in channels:
            density = np.zeros((rank, rank), dtype=complex)
            for operator in kraus:
                physical = _local_columns(code, self.n, qubit, operator)
                amplitudes = sum(basis[:, logical, :].conj().T @ physical[:, logical]
                                 for logical in range(2)) / 2.0
                density += np.outer(amplitudes, amplitudes.conj())
            syndrome_densities.append(density)
        probabilities = np.einsum("os,hst,ot->oh", self._povm_vectors.conj(),
                                  np.asarray(syndrome_densities), self._povm_vectors,
                                  optimize=True)
        if np.max(np.abs(probabilities.imag)) > 2e-8:
            raise ArithmeticError("nonreal channel response")
        self._response = np.maximum(probabilities.real, 0.0)
        if np.max(np.abs(self._response.sum(axis=0) - 1.0)) > 2e-8:
            raise ArithmeticError("the supported channels do not have unit total response")
        u, singular_values, vt = np.linalg.svd(self._response, full_matrices=False)
        rank_tolerance = (32 * np.finfo(float).eps * max(self._response.shape) *
                          singular_values[0])
        self._rank = int(np.count_nonzero(singular_values > rank_tolerance))
        self._u = u[:, :self._rank]
        self._singular_values = singular_values[:self._rank]
        self._v = vt[:self._rank]
        self._projector = self._v.T @ self._v
        self._projector = (self._projector + self._projector.T) / 2.0
        self._unique = self._rank == len(channels)

    def measurement_operators(self):
        """Return direct row coefficients, with no implicit conjugation.

        Result[outcome][logical_row][physical_word] is the coefficient in
        output[logical_row] = sum(coefficient * input[physical_word]).
        All returned containers are independent of the internal design.
        """
        return [[{int(i): complex(row[i]) for i in np.flatnonzero(row)}
                 for row in operator] for operator in self._operators]

    def response_matrix(self):
        """Outcome probabilities, excluding the supported-model zero erasure."""
        return self._response.copy()

    def identifiability(self):
        """Euclidean row-space certificate, including mixture normalization."""
        return {"rank": self._rank, "unique": self._unique,
                "identifiable_projector": self._projector.copy()}

    def estimate(self, observed):
        """Fit normalized frequencies on the probability simplex.

        Exact model frequencies are inverted in the identifiable quotient.
        A feasible representative is found by linear programming if the
        minimum-norm inverse has negative components.  Other observations
        receive a constrained ordinary least-squares probability fit.
        No uniqueness of deficient-rank mixtures is asserted.
        """
        observations = np.asarray(observed, dtype=float)
        if observations.shape != (len(self._response),):
            raise ValueError("observed must have one entry for each registered outcome")
        if not np.all(np.isfinite(observations)) or np.any(observations < 0):
            raise ValueError("observations must be finite and nonnegative")
        largest = float(np.max(observations))
        if largest <= 0:
            raise ValueError("observations must have positive total mass")
        # Scaling before summation avoids overflow for very large count units.
        frequencies = observations / largest
        frequencies = frequencies / frequencies.sum()
        coordinates = (self._u.T @ frequencies) / self._singular_values
        inverse = self._v.T @ coordinates
        span_residual = frequencies - self._u @ (self._u.T @ frequencies)
        exact_span = np.max(np.abs(span_residual)) <= 5e-11
        weights = None
        if (exact_span and np.min(inverse) >= -5e-11 and
                abs(inverse.sum() - 1.0) <= 5e-10):
            weights = np.maximum(inverse, 0.0)
            weights /= weights.sum()
        elif exact_span:
            equalities = np.vstack((self._v, np.ones((1, len(inverse)))))
            target = np.r_[coordinates, 1.0]
            feasibility = linprog(np.zeros(len(inverse)), A_eq=equalities,
                                  b_eq=target, bounds=(0.0, None), method="highs",
                                  options={"primal_feasibility_tolerance": 1e-9,
                                           "dual_feasibility_tolerance": 1e-9})
            if feasibility.success:
                candidate = np.maximum(feasibility.x, 0.0)
                candidate /= candidate.sum()
                if np.max(np.abs(self._v @ candidate - coordinates)) <= 2e-8:
                    weights = candidate

        if weights is None:
            if exact_span:
                # Whiten only the exact inverse problem: its identifiable
                # curvature is one even when physical responses are small.
                design, target = self._v, coordinates
            else:
                design = self._response / self._singular_values[0]
                target = frequencies / self._singular_values[0]
            hessian = design.T @ design
            linear = design.T @ target

            def objective(w):
                residual = design @ w - target
                return 0.5 * float(residual @ residual)

            def gradient(w):
                return hessian @ w - linear

            fit = minimize(objective, _simplex_projection(inverse), jac=gradient,
                           bounds=[(0.0, 1.0)] * len(inverse),
                           constraints={"type": "eq",
                                        "fun": lambda w: float(w.sum() - 1.0),
                                        "jac": lambda w: np.ones_like(w)},
                           method="SLSQP", options={"ftol": 1e-14, "maxiter": 5000})
            if not np.all(np.isfinite(fit.x)):
                raise ArithmeticError("classical mixture fitting produced nonfinite weights")
            weights = np.maximum(fit.x, 0.0)
            if weights.sum() <= 0:
                raise ArithmeticError("classical mixture fitting lost normalization")
            weights /= weights.sum()
            if not fit.success:
                grad = gradient(weights)
                active = weights > 1e-8
                level = float(np.mean(grad[active]))
                violation = float(np.max(np.abs(grad[active] - level)))
                if np.any(~active):
                    violation = max(violation, float(np.max(np.maximum(level - grad[~active], 0))))
                if violation > 2e-7:
                    raise ArithmeticError("classical simplex fit failed: " + fit.message)

        return {"mixture_weights": weights,
                "identifiable_coordinates": self._projector @ weights,
                "predicted_frequencies": self._response @ weights,
                "unique": self._unique}

    def erasure_effect(self):
        """Return I - projector(S), the effect of the classical erasure flag."""
        effect = np.eye(self.dimension, dtype=complex) - self._span_basis @ self._span_basis.conj().T
        return (effect + effect.conj().T) / 2.0

    def erasure_operators(self):
        """Scalar-output Kraus rows sharing one classical erasure flag.

        Rows of the complementary projector give a redundant Kraus
        representation of rho -> trace((I-projector(S))*rho).
        These rows are intentionally excluded from response_matrix().
        """
        return [{int(i): complex(row[i]) for i in np.flatnonzero(row)}
                for row in self.erasure_effect()]

    def apply_instrument(self, physical):
        """Apply the complete instrument without normalizing its input.

        physical may be a sparse state dictionary, a dense state vector,
        a physical density matrix, or a list of sparse unnormalized pure
        branches representing a mixed state.  The returned logical density
        and individual outcome densities retain their raw probabilities.
        """
        def vector_from_sparse(state):
            vector = np.zeros(self.dimension, dtype=complex)
            for word, amplitude in state.items():
                if not isinstance(word, (int, np.integer)) or not 0 <= word < self.dimension:
                    raise ValueError("invalid physical state coordinate")
                vector[int(word)] = complex(amplitude)
            return vector

        if isinstance(physical, dict):
            vector = vector_from_sparse(physical)
            density = np.outer(vector, vector.conj())
        elif isinstance(physical, (list, tuple)) and all(isinstance(s, dict) for s in physical):
            density = np.zeros((self.dimension, self.dimension), dtype=complex)
            for state in physical:
                vector = vector_from_sparse(state)
                density += np.outer(vector, vector.conj())
        else:
            values = np.asarray(physical, dtype=complex)
            if values.shape == (self.dimension,):
                density = np.outer(values, values.conj())
            elif values.shape == (self.dimension, self.dimension):
                density = values.copy()
            else:
                raise ValueError("physical input has incompatible dimensions")
        if not np.all(np.isfinite(density)):
            raise ValueError("physical input must be finite")
        if np.max(np.abs(density - density.conj().T)) > 2e-8:
            raise ValueError("a density input must be Hermitian")
        if np.linalg.eigvalsh(density)[0] < -2e-8:
            raise ValueError("a density input must be positive semidefinite")
        outcomes = np.einsum("okd,de,ole->okl", self._operators, density,
                             self._operators.conj(), optimize=True)
        probabilities = np.trace(outcomes, axis1=1, axis2=2).real
        input_probability = float(np.trace(density).real)
        erasure = float(np.trace(self.erasure_effect() @ density).real)
        if erasure < 0 and erasure >= -2e-8 * max(1.0, abs(input_probability)):
            erasure = 0.0
        return {"outcome_densities": outcomes,
                "outcome_probabilities": probabilities,
                "logical_density": outcomes.sum(axis=0),
                "erasure_probability": erasure,
                "input_probability": input_probability}
