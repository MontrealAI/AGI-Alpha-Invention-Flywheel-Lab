"""Sparse logical recovery for arbitrary single-qubit-correcting codes.

The physical error basis is I followed by X_q, Y_q, Z_q, with qubit 0
the most-significant bit.  If V_i has columns E_a|i_L>, the
Knill--Laflamme condition is V_i^* V_j = delta_ij G.  Diagonalizing
the common positive matrix G gives orthonormal vectors

    |s, i> = V_i u_s / sqrt(lambda_s).

The returned recovery operator R_s has rows <s, i|.  Thus its rows
contain already-conjugated coefficients: multiplying a row by a
physical state uses no further conjugation.  Zero eigenvalues are
discarded, which is essential for degenerate codes.  The sum R_s^*R_s
is the projector onto the correctable subspace.  All remaining trace
goes to one classical erasure flag.

Only sparse error columns, small Gram matrices, and dense arrays on
active coordinates are constructed; there are no dense full-physical-
space square operators.  NumPy and SciPy are the only dependencies.
"""

from __future__ import annotations

from collections.abc import Mapping
import math
import operator

import numpy as np
from scipy import sparse


class Recovery:
    """Construct a recovery channel for an ordered orthonormal code basis.

    The specified domain is n <= 20 and K in {2, 4}.  Other positive K
    values are accepted when they satisfy the same mathematical tests.
    Numerical validation is deliberately strict; inputs are never
    normalized or silently projected onto a valid-code manifold.
    """

    _VALIDATION_ATOL = 5.0e-10

    def __init__(self, n: int, codewords: list[dict[int, complex]]):
        if isinstance(n, (bool, np.bool_)):
            raise ValueError("n must be an integer between 1 and 20")
        try:
            self.n = operator.index(n)
        except TypeError as exc:
            raise ValueError("n must be an integer between 1 and 20") from exc
        if not 1 <= self.n <= 20:
            raise ValueError("n must be an integer between 1 and 20")
        self._dimension = 1 << self.n
        try:
            self.K = len(codewords)
        except TypeError as exc:
            raise ValueError("codewords must be an ordered nonempty sequence") from exc
        if self.K < 1:
            raise ValueError("codewords must be an ordered nonempty sequence")
        self._codewords = tuple(self._validated_state(cw) for cw in codewords)

        # Validate the supplied ordered basis without altering it.
        code_gram = np.empty((self.K, self.K), dtype=np.complex128)
        for i, left in enumerate(self._codewords):
            for j, right in enumerate(self._codewords):
                products = [a.conjugate() * right.get(word, 0j)
                            for word, a in left.items()]
                code_gram[i, j] = complex(
                    math.fsum(z.real for z in products),
                    math.fsum(z.imag for z in products),
                )
        basis_error = float(np.max(np.abs(code_gram - np.eye(self.K))))
        if not math.isfinite(basis_error) or basis_error > self._VALIDATION_ATOL:
            raise ValueError(
                "codewords are not orthonormal "
                f"(maximum Gram residual {basis_error:.6g})"
            )

        m = 1 + 3 * self.n
        self._error_count = m
        column_rows = []
        column_data = []
        pointers = [0]

        def add_column(indices, amplitudes):
            column_rows.append(indices)
            column_data.append(amplitudes)
            pointers.append(pointers[-1] + len(indices))

        for cw in self._codewords:
            words = np.fromiter(cw.keys(), dtype=np.int64, count=len(cw))
            amplitudes = np.fromiter(cw.values(), dtype=np.complex128,
                                     count=len(cw))
            add_column(words, amplitudes)
            for q in range(self.n):
                mask = 1 << (self.n - 1 - q)
                sign = 1 - 2 * ((words & mask) != 0).astype(np.int8)
                flipped = words ^ mask
                add_column(flipped, amplitudes)              # X
                add_column(flipped, 1j * sign * amplitudes)  # Y
                add_column(words, sign * amplitudes)        # Z

        errors = sparse.csc_matrix(
            (np.concatenate(column_data), np.concatenate(column_rows),
             np.asarray(pointers, dtype=np.int64)),
            shape=(self._dimension, self.K * m),
            dtype=np.complex128,
        )
        errors.sort_indices()
        full_gram = (errors.conjugate().transpose() @ errors).toarray()
        common_gram = sum(
            full_gram[i*m:(i+1)*m, i*m:(i+1)*m]
            for i in range(self.K)
        ) / self.K
        common_gram = (common_gram + common_gram.conjugate().T) * 0.5

        expected = np.kron(np.eye(self.K), common_gram)
        kl_error = float(np.max(np.abs(full_gram - expected)))
        if not math.isfinite(kl_error) or kl_error > self._VALIDATION_ATOL:
            raise ValueError(
                "code fails the single-qubit Knill--Laflamme conditions "
                f"(maximum residual {kl_error:.6g})"
            )

        eigenvalues, eigenvectors = np.linalg.eigh(common_gram)
        # The cutoff removes floating-point zero modes, rather than assuming
        # that every Pauli error defines a distinct orthogonal sector.
        rank_tolerance = (64 * np.finfo(np.float64).eps * m
                          * max(1.0, float(eigenvalues[-1])))
        if eigenvalues[0] < -rank_tolerance:
            raise ValueError("error Gram matrix is not positive semidefinite")
        keep = eigenvalues > rank_tolerance
        self.syndrome_rank = int(np.count_nonzero(keep))
        if self.syndrome_rank == 0:
            raise ValueError("code has no numerically resolvable error subspace")
        transform = eigenvectors[:, keep] / np.sqrt(eigenvalues[keep])[None, :]

        # Check the complete logical/syndrome isometry before constructing
        # the sparse exported certificate.  This also guards against input
        # whose small residual is amplified by excessive ill-conditioning.
        global_transform = np.kron(np.eye(self.K), transform)
        orthogonal_gram = (global_transform.conjugate().T
                           @ full_gram @ global_transform)
        orthogonality_error = float(np.max(np.abs(
            orthogonal_gram - np.eye(self.K * self.syndrome_rank)
        )))
        if not math.isfinite(orthogonality_error) or orthogonality_error > 2.0e-9:
            raise ValueError(
                "error subspace is numerically ill-conditioned or fails "
                f"correctability (isometry residual {orthogonality_error:.6g})"
            )

        supports = []
        rows = []
        for i in range(self.K):
            columns = errors[:, i*m:(i+1)*m]
            support = np.unique(columns.indices)
            # Each logical word keeps its own active support, avoiding a
            # dense array across the union of all logical-word supports.
            vectors = columns[support, :] @ transform
            row_matrix = np.ascontiguousarray(vectors.conjugate().T)
            support.setflags(write=False)
            row_matrix.setflags(write=False)
            supports.append(support)
            rows.append(row_matrix)
        self._supports = tuple(supports)
        self._rows = tuple(rows)
        self.validation_residuals = {
            "code_orthonormality": basis_error,
            "knill_laflamme": kl_error,
            "syndrome_isometry": orthogonality_error,
            "rank_tolerance": rank_tolerance,
        }

    def _validated_state(self, state):
        if not isinstance(state, Mapping):
            raise ValueError("each physical state must be a sparse mapping")
        clean = {}
        for word, amplitude in state.items():
            if isinstance(word, (bool, np.bool_)):
                raise ValueError("physical words must be integer basis indices")
            try:
                index = operator.index(word)
            except TypeError as exc:
                raise ValueError("physical words must be integer basis indices") from exc
            if not 0 <= index < self._dimension:
                raise ValueError("physical basis index is out of range")
            try:
                value = complex(amplitude)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("physical amplitudes must be finite complex numbers") from exc
            if not (math.isfinite(value.real) and math.isfinite(value.imag)):
                raise ValueError("physical amplitudes must be finite complex numbers")
            if value != 0:
                clean[index] = value
        return clean

    def encode(self, logical):
        """Return the supplied ordered codeword combination, without normalization."""
        try:
            logical = np.asarray(logical, dtype=np.complex128)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("logical must be a finite K-component vector") from exc
        if logical.shape != (self.K,) or not np.all(np.isfinite(logical)):
            raise ValueError("logical must be a finite K-component vector")
        state = {}
        for coefficient, cw in zip(logical, self._codewords):
            if coefficient != 0:
                coefficient = complex(coefficient)
                for word, amplitude in cw.items():
                    state[word] = state.get(word, 0j) + coefficient * amplitude
        return {word: amplitude for word, amplitude in state.items()
                if amplitude != 0}

    def recover(self, branches: list[dict[int, complex]]):
        """Sum independent Kraus-branch densities and report all raw trace.

        The returned density is unnormalized.  A zero input returns a zero
        density and zero probabilities.  The erasure value is the raw mass
        difference; a roundoff-sized negative value is not renormalized.
        """
        density = np.zeros((self.K, self.K), dtype=np.complex128)
        probabilities = []
        for branch in branches:
            state = self._validated_state(branch)
            probabilities.append(math.fsum(
                value.real * value.real + value.imag * value.imag
                for value in state.values()
            ))
            if not state:
                continue
            outputs = np.empty((self.K, self.syndrome_rank),
                               dtype=np.complex128)
            for i, (support, row_matrix) in enumerate(zip(self._supports, self._rows)):
                amplitudes = np.fromiter(
                    (state.get(int(word), 0j) for word in support),
                    dtype=np.complex128, count=len(support),
                )
                outputs[i, :] = row_matrix @ amplitudes
            density += outputs @ outputs.conjugate().T
        density = (density + density.conjugate().T) * 0.5
        input_probability = math.fsum(probabilities)
        correctable_probability = float(np.trace(density).real)
        return {
            "logical_density": density,
            "input_probability": float(input_probability),
            "correctable_probability": correctable_probability,
            "erasure_probability": float(input_probability - correctable_probability),
        }

    def kraus(self):
        """Export fresh sparse row dictionaries for all logical recovery operators."""
        return [
            [
                {int(word): complex(coefficient)
                 for word, coefficient in zip(support, row_matrix[syndrome, :])
                 if coefficient != 0}
                for support, row_matrix in zip(self._supports, self._rows)
            ]
            for syndrome in range(self.syndrome_rank)
        ]
