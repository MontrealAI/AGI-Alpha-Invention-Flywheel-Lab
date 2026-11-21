"""Nondestructive tomography of correctable local-channel mixtures.

The construction factors the complete one-qubit error span into a syndrome
space and the original logical space using the Knill--Laflamme Gram matrix.
A rank-one informationally complete POVM on the syndrome exports executable
recovery/measurement branches.  No particular error syndrome or hypothesis is
assumed orthogonal or distinguishable.  NumPy and SciPy are the only runtime
dependencies; no supplied recovery asset is required.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import linprog, minimize


class NoiseExperiment:
    """Construct a complete noise experiment for a correctable two-state code.

    Physical qubit zero is the most-significant coordinate bit.  Returned
    sparse operators contain direct row coefficients, not conjugated kets.
    The registered branches cover the full Pauli-correctable subspace; the
    complementary erasure effect and an executable full instrument are also
    provided by ``erasure_effect`` and ``apply``.
    """

    def __init__(self, n: int, codewords: list[dict[int, complex]],
                 hypotheses: list[dict]):
        if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or not 1 <= n <= 9:
            raise ValueError("n must be an integer in the qualified interval 1..9")
        self.n, self.dimension = int(n), 1 << int(n)
        if len(codewords) != 2:
            raise ValueError("exactly two orthonormal logical basis codewords are required")
        self.logical_dimension = 2
        self._code = np.zeros((self.dimension, 2), dtype=complex)
        for k, word in enumerate(codewords):
            for coordinate, amplitude in word.items():
                if (isinstance(coordinate, bool) or
                    not isinstance(coordinate, (int, np.integer)) or
                    not 0 <= coordinate < self.dimension):
                    raise ValueError("codeword coordinate outside the physical space")
                if not np.isfinite(amplitude):
                    raise ValueError("codeword amplitudes must be finite")
                self._code[int(coordinate), k] = complex(amplitude)
        if np.max(np.abs(self._code.conj().T @ self._code - np.eye(2))) > 2e-8:
            raise ValueError("codewords must be orthonormal")
        if not 1 <= len(hypotheses) <= 32:
            raise ValueError("between one and 32 channel hypotheses are required")
        paulis = np.array([np.eye(2), [[0, 1], [1, 0]],
                           [[0, -1j], [1j, 0]], [[1, 0], [0, -1]]], complex)
        self._hypotheses = []
        names = set()
        for hypothesis in hypotheses:
            name, qubit = hypothesis['name'], hypothesis['qubit']
            if not isinstance(name, str) or name in names:
                raise ValueError("hypothesis names must be unique strings")
            if (isinstance(qubit, bool) or not isinstance(qubit, (int, np.integer))
                    or not 0 <= qubit < self.n):
                raise ValueError("hypothesis qubit outside the physical space")
            kraus = [np.asarray(a, complex).copy() for a in hypothesis['kraus']]
            if not kraus or any(a.shape != (2, 2) or not np.isfinite(a).all()
                                for a in kraus):
                raise ValueError("each channel needs finite 2 by 2 Kraus matrices")
            tp = sum((a.conj().T @ a for a in kraus), np.zeros((2, 2), complex))
            if np.max(np.abs(tp - np.eye(2))) > 2e-8:
                raise ValueError("the supplied local channel is not trace preserving")
            names.add(name)
            self._hypotheses.append((name, int(qubit), kraus))
        self.hypothesis_names = tuple(h[0] for h in self._hypotheses)

        # E[a, d, k] = (physical Pauli a applied to logical basis k)[d].
        errors = [self._code]
        for qubit in range(self.n):
            errors.extend(self._local(self._code, qubit, p) for p in paulis[1:])
        errors = np.asarray(errors)
        m = len(errors)
        error_matrix = errors.transpose(1, 0, 2).reshape(self.dimension, 2*m)
        full_gram = (error_matrix.conj().T @ error_matrix).reshape(m, 2, m, 2)
        gram = (full_gram[:, 0, :, 0] + full_gram[:, 1, :, 1]) / 2
        gram = (gram + gram.conj().T) / 2
        target_gram = np.einsum('ab,ij->aibj', gram, np.eye(2))
        if np.max(np.abs(full_gram - target_gram)) > 2e-8:
            raise ValueError("the code does not correct arbitrary one-qubit errors")
        eigenvalues, eigenvectors = np.linalg.eigh(gram)
        cutoff = max(self.dimension, m) * np.finfo(float).eps * 64 * max(1., eigenvalues[-1])
        keep = eigenvalues > cutoff
        if not np.any(keep):
            raise ValueError("the correctable error span is empty")
        lam, u = eigenvalues[keep], eigenvectors[:, keep]
        r = len(lam)
        self.syndrome_dimension = r
        f = np.einsum('adk,aj->jdk', errors, u) / np.sqrt(lam)[:, None, None]
        # Isometry W : syndrome tensor logical -> physical correctable span.
        self._isometry = f.transpose(1, 0, 2).reshape(self.dimension, 2*r)
        if np.max(np.abs(self._isometry.conj().T @ self._isometry - np.eye(2*r))) > 2e-8:
            raise ValueError("the correctable-space factorization is numerically unstable")

        # r^2 linearly independent rank-one Hermitian effects, made complete
        # by an invertible positive congruence. Their span remains Herm(r).
        raw = np.zeros((r*r, r), complex)
        raw[:r] = np.eye(r)
        row = r
        for i in range(r):
            for j in range(i+1, r):
                raw[row, i] = raw[row, j] = 1/np.sqrt(2)
                raw[row+1, i], raw[row+1, j] = 1/np.sqrt(2), 1j/np.sqrt(2)
                row += 2
        frame_gram = raw.conj().T @ raw
        values, vectors = np.linalg.eigh(frame_gram)
        inverse_root = (vectors * (1/np.sqrt(values))) @ vectors.conj().T
        self._frame = raw @ inverse_root
        self.outcome_count = r*r
        self._dense_operators = np.einsum('oj,jdk->okd', self._frame, f.conj())
        self._sparse_operators = None

        # A coherent local Kraus matrix has syndrome coordinates sqrt(lam) U* c.
        # Keeping its complex Pauli coefficients is essential for general CPTP
        # channels; treating Pauli components as a classical mixture would fail.
        response = np.empty((r*r, len(self._hypotheses)), float)
        syndrome_densities = []
        for h, (_, qubit, kraus) in enumerate(self._hypotheses):
            density = np.zeros((r, r), complex)
            probabilities = np.zeros(r*r, float)
            for operator in kraus:
                local_coefficients = np.einsum('pij,ji->p', paulis, operator) / 2
                coefficients = np.zeros(m, complex)
                coefficients[0] = local_coefficients[0]
                coefficients[1+3*qubit:4+3*qubit] = local_coefficients[1:]
                syndrome = np.sqrt(lam) * (u.conj().T @ coefficients)
                amplitudes = self._frame @ syndrome
                probabilities += np.abs(amplitudes)**2
                density += np.outer(syndrome, syndrome.conj())
            response[:, h] = probabilities
            syndrome_densities.append(density)
        self._response = response
        self._syndrome_densities = np.asarray(syndrome_densities)
        left, singular, right = np.linalg.svd(response, full_matrices=False)
        tolerance = max(response.shape) * np.finfo(float).eps * 32 * singular[0]
        self._rank = int(np.sum(singular > tolerance))
        self._left = left[:, :self._rank]
        self._singular = singular[:self._rank]
        self._right = right[:self._rank]
        self._projector = self._right.T @ self._right
        self._unique = self._rank == len(self._hypotheses)

    def _local(self, vectors, qubit, operator):
        """Apply a 2 by 2 matrix without a full physical Kronecker matrix."""
        mask = 1 << (self.n - 1 - qubit)
        zero = np.arange(self.dimension)[(np.arange(self.dimension) & mask) == 0]
        one = zero | mask
        result = np.empty_like(vectors, dtype=complex)
        result[zero] = operator[0, 0]*vectors[zero] + operator[0, 1]*vectors[one]
        result[one] = operator[1, 0]*vectors[zero] + operator[1, 1]*vectors[one]
        return result

    def measurement_operators(self):
        """Return one two-row sparse recovery Kraus operator per observation."""
        if self._sparse_operators is None:
            self._sparse_operators = [
                [{int(d): complex(c) for d, c in enumerate(row) if c != 0}
                 for row in operator] for operator in self._dense_operators]
        # The dictionaries are deliberately copied so edits by a caller cannot
        # silently change the instrument on subsequent calls.
        return [[row.copy() for row in operator] for operator in self._sparse_operators]

    def response_matrix(self):
        """Observation probabilities; columns follow the supplied hypothesis order."""
        return self._response.copy()

    def identifiability(self):
        """Euclidean row-space projector, including the normalization direction."""
        return {'rank': self._rank, 'unique': self._unique,
                'identifiable_projector': self._projector.copy()}

    def estimate(self, observed):
        """Fit normalized frequencies with an explicitly feasible mixture.

        Exact model observations first use a linear inverse and, if necessary,
        a feasibility linear program. Other observations use constrained least
        squares on the probability simplex. With a rank-deficient response,
        weights are one representative; only their row-space projection is
        identifiable. Finite-sample fits carry no universal accuracy claim.
        """
        data = np.asarray(observed, float)
        if data.shape != (self.outcome_count,) or not np.isfinite(data).all():
            raise ValueError("observations must be a finite vector with one value per outcome")
        if np.any(data < 0) or data.sum() <= 0 or not np.isfinite(data.sum()):
            raise ValueError("observations must be nonnegative with positive finite total")
        frequencies = data / data.sum()
        coordinates = (self._left.T @ frequencies) / self._singular
        least_norm = self._right.T @ coordinates
        weights = None
        exact_model = np.max(np.abs(self._response @ least_norm - frequencies)) <= 2e-11
        if exact_model:
            if np.min(least_norm) >= -2e-10 and abs(least_norm.sum()-1) <= 2e-9:
                weights = np.maximum(least_norm, 0)
            else:
                equalities = np.vstack((self._right, np.ones(len(least_norm))))
                targets = np.r_[coordinates, 1.]
                feasible = linprog(np.zeros(len(least_norm)), A_eq=equalities,
                                   b_eq=targets, bounds=(0, None), method='highs',
                                   options={'primal_feasibility_tolerance': 1e-9,
                                            'dual_feasibility_tolerance': 1e-9})
                if feasible.success:
                    weights = np.maximum(feasible.x, 0)
        method = 'exact feasible inverse'
        if weights is None:
            start = np.maximum(least_norm, 0)
            start = start / start.sum() if start.sum() else np.full(len(start), 1/len(start))
            scale = self._singular[0]**2
            response = self._response
            def objective(w):
                residual = response @ w - frequencies
                return .5*float(residual @ residual)/scale
            def gradient(w):
                return response.T @ (response @ w - frequencies)/scale
            fit = minimize(objective, start, jac=gradient, method='SLSQP',
                           bounds=[(0., 1.)]*len(start),
                           constraints={'type': 'eq', 'fun': lambda w: w.sum()-1.,
                                        'jac': lambda w: np.ones(len(w))},
                           options={'ftol': 1e-14, 'maxiter': 2000})
            if not fit.success:
                raise RuntimeError("simplex least-squares fit failed: " + fit.message)
            weights = np.maximum(fit.x, 0)
            method = 'simplex constrained least squares'
        weights /= weights.sum()
        predicted = self._response @ weights
        return {'mixture_weights': weights,
                'identifiable_coordinates': self._projector @ weights,
                'predicted_frequencies': predicted,
                'unique': self._unique,
                'estimator': method,
                'frequency_residual_l2': float(np.linalg.norm(predicted-frequencies))}

    def erasure_effect(self):
        """Effect of the classical erasure outcome on the entire physical space.

        The erasure instrument is rho -> Tr(effect @ rho)|erasure><erasure|.
        Together with the exported branches, this is a CPTP instrument.
        """
        effect = np.eye(self.dimension) - self._isometry @ self._isometry.conj().T
        return (effect + effect.conj().T) / 2

    def apply(self, state):
        """Execute every branch plus erasure, preserving subnormalized raw mass.

        Accepts a sparse pure vector, a dense pure vector, or a physical density
        matrix. Density matrices are expected to be positive semidefinite;
        neither input vectors nor density matrices are implicitly normalized.
        """
        if isinstance(state, dict):
            vector = np.zeros(self.dimension, complex)
            for word, value in state.items():
                if not isinstance(word, (int, np.integer)) or not 0 <= word < self.dimension:
                    raise ValueError("physical coordinate out of range")
                vector[word] = value
            state = vector
        state = np.asarray(state, complex)
        if not np.isfinite(state).all():
            raise ValueError("state must be finite")
        if state.shape == (self.dimension,):
            raw_mass = float(np.vdot(state, state).real)
            syndrome_logical = (self._isometry.conj().T @ state).reshape(-1, 2)
            outputs = self._frame @ syndrome_logical
            densities = outputs[:, :, None] * outputs[:, None, :].conj()
        elif state.shape == (self.dimension, self.dimension):
            if np.max(np.abs(state-state.conj().T)) > 2e-8:
                raise ValueError("density input must be Hermitian")
            raw_mass = float(np.trace(state).real)
            reduced = self._isometry.conj().T @ state @ self._isometry
            reduced = reduced.reshape(self.syndrome_dimension, 2, self.syndrome_dimension, 2)
            densities = np.einsum('oj,jklm,ol->okm', self._frame, reduced, self._frame.conj())
        else:
            raise ValueError("state must be a physical vector or density matrix")
        probabilities = np.trace(densities, axis1=1, axis2=2).real
        erasure = raw_mass - float(probabilities.sum())
        if raw_mass < -2e-8 or np.min(probabilities) < -2e-8 or erasure < -2e-8:
            raise ValueError("input is not a positive state or numerical mass is inconsistent")
        erasure = max(0., erasure)
        return {'outcome_logical_densities': densities,
                'outcome_probabilities': probabilities,
                'logical_density': densities.sum(axis=0),
                'erasure_probability': erasure,
                'input_probability': raw_mass,
                'total_probability': float(probabilities.sum())+erasure}
