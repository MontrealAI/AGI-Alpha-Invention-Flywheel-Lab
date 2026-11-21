"""Conventional sparse Knill--Laflamme recovery with explicit erasure.

This implements the standard construction: diagonalize the error-overlap
matrix, orthogonalize the corresponding error images, and decode each
orthogonal syndrome.  It introduces no new recovery theorem.  Physical state
coordinates are compressed before sparse linear algebra; an ambient physical
density matrix or projector is never materialized.

Mathematical reference: E. Knill and R. Laflamme, Phys. Rev. A 55, 900 (1997),
https://doi.org/10.1103/PhysRevA.55.900 (arXiv:quant-ph/9604034).
"""

from __future__ import annotations

import math
from numbers import Integral

import numpy as np
from scipy import sparse


class Recovery:
    """Recover a supplied orthonormal code from arbitrary single-qubit errors.

    The constructor validates the complete one-qubit Knill--Laflamme matrix,
    including all logical off-diagonal entries.  Numerical rank decisions are
    double-precision decisions on the well-conditioned domain in the contract.
    """

    _KL_TOLERANCE = 1e-9

    def __init__(self, n: int, codewords: list[dict[int, complex]]):
        if isinstance(n, bool) or not isinstance(n, Integral) or not 1 <= n <= 20:
            raise ValueError("n must be an integer in the qualified range 1..20")
        if not isinstance(codewords, (list, tuple)) or len(codewords) not in (2, 4):
            raise ValueError("Supply two or four ordered logical codewords")
        self.n, self.dimension, self.k = int(n), 1 << int(n), len(codewords)
        self._codewords = [self._state(state) for state in codewords]
        if sum(len(state) for state in self._codewords) > 4096:
            raise ValueError("The registered domain has at most 4096 code amplitudes")

        # Identity, then X/Y/Z on each physical qubit.  Qubit zero is MSB.
        errors = [(0, "I")]
        errors.extend((1 << (self.n - 1 - q), axis)
                      for q in range(self.n) for axis in ("X", "Y", "Z"))
        self.error_count = len(errors)
        active = set().union(*(state.keys() for state in self._codewords))
        original = tuple(active)
        for q in range(self.n):
            mask = 1 << (self.n - 1 - q)
            active.update(word ^ mask for word in original)
        self._words = np.array(sorted(active), dtype=np.int64)
        self._index = {int(word): row for row, word in enumerate(self._words)}

        row_indices, column_indices, amplitudes = [], [], []
        for error_index, (mask, axis) in enumerate(errors):
            for logical_index, state in enumerate(self._codewords):
                column = error_index * self.k + logical_index
                for word, amplitude in state.items():
                    bit = bool(word & mask)
                    if axis == "X":
                        target, coefficient = word ^ mask, 1
                    elif axis == "Y":
                        target, coefficient = word ^ mask, -1j if bit else 1j
                    elif axis == "Z":
                        target, coefficient = word, -1 if bit else 1
                    else:
                        target, coefficient = word, 1
                    row_indices.append(self._index[target])
                    column_indices.append(column)
                    amplitudes.append(coefficient * amplitude)

        images = sparse.csc_matrix(
            (np.asarray(amplitudes, dtype=complex), (row_indices, column_indices)),
            shape=(len(self._words), self.error_count * self.k),
        )
        gram = (images.conjugate().T @ images).toarray()
        if np.max(np.abs(gram[:self.k, :self.k] - np.eye(self.k))) > self._KL_TOLERANCE:
            raise ValueError("Codewords are not orthonormal; normalization is not implicit")

        overlap = sum(gram[k::self.k, k::self.k] for k in range(self.k)) / self.k
        residual = gram - np.kron(overlap, np.eye(self.k))
        self.kl_residual = float(np.max(np.abs(residual)))
        if self.kl_residual > self._KL_TOLERANCE:
            raise ValueError("Code fails the complete single-qubit Knill--Laflamme conditions")

        overlap = (overlap + overlap.conjugate().T) / 2
        values, vectors = np.linalg.eigh(overlap)
        if float(values[0]) < -self._KL_TOLERANCE:
            raise ValueError("Error-overlap matrix is not positive semidefinite")
        cutoff = max(1e-12, 128 * np.finfo(float).eps * self.error_count
                     * max(1.0, float(values[-1])))
        positive = values > cutoff
        self.syndrome_rank = int(np.count_nonzero(positive))
        if not self.syndrome_rank:
            raise ValueError("The code has no nonzero correctable error image")

        # If C = U diag(lambda) U*, W_a = sum_i U_ia E_i V/sqrt(lambda_a).
        # KL implies W_a* W_b = delta_ab I.  R_a = W_a* then supplies a
        # complete logical recovery on the correctable subspace.
        change = vectors[:, positive] / np.sqrt(values[positive])[None, :]
        transform = sparse.csc_matrix(np.kron(change, np.eye(self.k)))
        orthogonal_images = (images @ transform).tocsc()
        orthogonal_images.eliminate_zeros()
        orthogonality = (orthogonal_images.conjugate().T @ orthogonal_images).toarray()
        self.orthogonality_residual = float(np.max(np.abs(
            orthogonality - np.eye(self.syndrome_rank * self.k))))
        if self.orthogonality_residual > 1e-8:
            raise ValueError("Numerical recovery basis is not sufficiently well conditioned")
        self._decoder = orthogonal_images.conjugate().T.tocsr()

    def _state(self, state):
        if not isinstance(state, dict):
            raise TypeError("Sparse states are dictionaries of physical words and amplitudes")
        result = {}
        for word, value in state.items():
            if (isinstance(word, bool) or not isinstance(word, Integral)
                    or not 0 <= int(word) < self.dimension):
                raise ValueError("Physical word is outside the n-qubit computational basis")
            try:
                amplitude = complex(value)
            except (TypeError, ValueError, OverflowError) as error:
                raise ValueError("A state amplitude is not a finite complex number") from error
            if not math.isfinite(amplitude.real) or not math.isfinite(amplitude.imag):
                raise ValueError("A state amplitude is not finite")
            if amplitude:
                result[int(word)] = amplitude
        return result

    def encode(self, logical):
        vector = np.asarray(logical, dtype=complex)
        if vector.shape != (self.k,) or not np.isfinite(vector).all():
            raise ValueError("Logical state must have K finite complex components")
        encoded = {}
        for coefficient, state in zip(vector, self._codewords):
            for word, amplitude in state.items():
                encoded[word] = encoded.get(word, 0j) + coefficient * amplitude
        return {word: complex(amplitude) for word, amplitude in encoded.items() if amplitude}

    def recover(self, branches):
        if not isinstance(branches, (list, tuple)):
            raise TypeError("Supply a list of unnormalized pure-state Kraus branches")
        density = np.zeros((self.k, self.k), dtype=complex)
        branch_masses = []
        for supplied in branches:
            state = self._state(supplied)
            mass = math.fsum(abs(amplitude) ** 2 for amplitude in state.values())
            if not math.isfinite(mass):
                raise ValueError("Branch probability exceeds finite floating-point range")
            branch_masses.append(mass)
            active = np.zeros(len(self._words), dtype=complex)
            for word, amplitude in state.items():
                row = self._index.get(word)
                if row is not None:
                    active[row] = amplitude
            decoded = np.asarray(self._decoder @ active).reshape(self.syndrome_rank, self.k)
            # Distinct Kraus branches are summed incoherently.  This ordering
            # yields y_i conjugate(y_j), including genuinely complex states.
            density += decoded.T @ decoded.conjugate()
        input_probability = math.fsum(branch_masses)
        correctable_probability = float(np.trace(density).real)
        return {
            "logical_density": density,
            "input_probability": input_probability,
            "correctable_probability": correctable_probability,
            # Keep the actual residual, including harmless roundoff.  Never
            # normalize, postselect, or hide complement probability.
            "erasure_probability": input_probability - correctable_probability,
        }

    def kraus(self):
        operators = []
        for syndrome in range(self.syndrome_rank):
            rows = []
            for logical in range(self.k):
                row = self._decoder.getrow(syndrome * self.k + logical)
                rows.append({int(self._words[index]): complex(amplitude)
                             for index, amplitude in zip(row.indices, row.data)
                             if amplitude})
            operators.append(rows)
        return operators
