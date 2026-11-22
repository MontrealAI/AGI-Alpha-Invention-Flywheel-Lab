"""Compile known linear/reciprocal boundary physics into an acquisition plan.

The voltage parser follows KTC2023's published injection-major ordering. All
selection uses geometry only. Fresh specimen voltages are never compiler inputs.
"""
from dataclasses import dataclass
import hashlib
import numpy as np
from scipy import linalg


def geometry(currents, measurements):
    I, M = (np.asarray(x, dtype=np.float64) for x in (currents, measurements))
    if I.ndim != 2 or M.ndim != 2 or I.shape[0] != M.shape[0]:
        raise ValueError('Electrode geometry mismatch')
    if not np.isfinite(I).all() or not np.isfinite(M).all():
        raise ValueError('Nonfinite geometry')
    if I.shape[0] < 3 or not np.allclose(I.sum(axis=0), 0, atol=1e-12):
        raise ValueError('Currents must conserve charge')
    if not np.allclose(M.sum(axis=0), 0, atol=1e-12):
        raise ValueError('Require voltage differences')
    Q = linalg.helmert(I.shape[0], full=False).T
    C, D = Q.T @ I, M.T @ Q
    if np.linalg.matrix_rank(C) == 0:
        raise ValueError('Current patterns contain no excitation')
    if np.linalg.matrix_rank(D) != I.shape[0]-1:
        raise ValueError('Voltage differences do not span electrode potentials')
    return I, M, C, D


def signature(I, M):
    h = hashlib.sha256()
    for x in [I, M]:
        a = np.asarray(x, dtype='<f8', order='C')
        h.update(str(a.shape).encode())
        h.update(a.tobytes())
    return h.hexdigest()


def acquisition_order(C):
    """QR basis followed by greedy D-optimal extension; not global optimization."""
    _, singular, right = linalg.svd(C, full_matrices=False)
    dim, patterns = np.linalg.matrix_rank(C), C.shape[1]
    normalized = singular[:dim,None] * right[:dim] / singular[0]
    _, _, pivots = linalg.qr(normalized, mode='economic', pivoting=True)
    chosen = list(map(int, pivots[:dim]))
    while len(chosen) < patterns:
        remain = [j for j in range(patterns) if j not in chosen]
        gram = normalized[:, chosen] @ normalized[:, chosen].T
        influence = np.sum(normalized[:, remain] * linalg.solve(
            gram, normalized[:, remain], assume_a='pos'), axis=0)
        chosen.append(remain[int(np.argmax(influence))])
    return chosen


def reciprocal_design(C, D):
    """Each column is an independent symmetric transfer-matrix coefficient."""
    columns = []
    for a in range(C.shape[0]):
        for b in range(a, C.shape[0]):
            voltage = D[:, a, None] * C[b, None, :]
            if a != b:
                voltage = voltage + D[:, b, None] * C[a, None, :]
            columns.append(voltage.T.ravel())
    return np.stack(columns, axis=1)


@dataclass
class Plan:
    selected: tuple
    mode: str
    geometry_sha256: str
    n_measurements: int
    n_patterns: int
    operator: np.ndarray
    coefficient_rank: int

    def predict(self, currents, measurements, acquired):
        I, M, _, _ = geometry(currents, measurements)
        if signature(I, M) != self.geometry_sha256:
            raise ValueError('Changed geometry requires a new plan')
        observed = np.asarray(acquired, dtype=np.float64)
        if observed.shape != (self.n_measurements, len(self.selected)):
            raise ValueError('Supply only the declared acquired pattern columns')
        if not np.isfinite(observed).all():
            raise ValueError('Nonfinite measurement')
        if self.mode == 'linear':
            result = observed @ self.operator
        else:
            result = (self.operator @ observed.T.ravel()).reshape(
                self.n_patterns, self.n_measurements).T
        # Recovery synthesizes only missing observations. Never replace actual
        # acquired values by a model projection (especially at full acquisition).
        result[:,self.selected] = observed
        return result


def compile_plan(currents, measurements, count, mode='reciprocal', order=None):
    I, M, C, D = geometry(currents, measurements)
    input_rank = np.linalg.matrix_rank(C)
    if type(count) is not int or not input_rank <= count <= C.shape[1]:
        raise ValueError('Count must cover a full current basis')
    if mode not in ['linear', 'reciprocal']:
        raise ValueError('Unknown model')
    selected = tuple((acquisition_order(C) if order is None else order)[:count])
    if len(selected) != count or len(set(selected)) != count:
        raise ValueError('Missing or duplicate acquisition indices')
    if any(type(j) is not int or not 0 <= j < C.shape[1] for j in selected):
        raise ValueError('Invalid acquisition index')
    if np.linalg.matrix_rank(C[:, selected]) != input_rank:
        raise ValueError('Selected patterns do not span current space')
    if mode == 'linear':
        operator = linalg.pinv(C[:, selected], rtol=1e-11) @ C
        rank = input_rank
    else:
        A = reciprocal_design(C, D)
        rows = np.concatenate([np.arange(j*M.shape[1], (j+1)*M.shape[1])
                               for j in selected])
        inverse, rank = linalg.pinv(A[rows], rtol=1e-11, return_rank=True)
        if rank != np.linalg.matrix_rank(A):
            raise ValueError('Requested responses are not identifiable from this subset')
        operator = A @ inverse
    return Plan(selected, mode, signature(I,M), M.shape[1], I.shape[1],
                operator, int(rank))


def decode(vector, measurements, patterns):
    v = np.asarray(vector, dtype=np.float64)
    if v.size != measurements*patterns or not np.isfinite(v).all():
        raise ValueError('Invalid voltage vector')
    return v.reshape(patterns, measurements).T


def relative_error(predicted, reference):
    denominator = np.linalg.norm(reference)
    if denominator == 0:
        return 0.0 if np.linalg.norm(predicted) == 0 else None
    return float(np.linalg.norm(predicted-reference)/denominator)
