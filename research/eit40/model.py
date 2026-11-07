"""EIT40: source-bound 40-pattern residual-response calibration prototype.

Standalone additive research. Public KTC physical measurements; no new sensing.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import numpy as np
from scipy import linalg

from research.measurement_compiler.core import acquisition_order, geometry, signature

EXTRAS = 4
COUNT = 40


def matrix_hash(*matrices):
    h = sha256()
    for x in matrices:
        a = np.asarray(x, dtype="<f8", order="C")
        if a.ndim != 2 or not np.isfinite(a).all():
            raise ValueError("NONFINITE_OR_NONMATRIX_SOURCE")
        h.update(str(a.shape).encode("ascii"))
        h.update(a.tobytes())
    return h.hexdigest()


def _validate(I, M, reference, calibrations, count):
    I, M, C, _ = geometry(I, M)
    if type(count) is not int or not EXTRAS + np.linalg.matrix_rank(C) <= count <= I.shape[1]:
        raise ValueError("INVALID_ACQUISITION_COUNT")
    if type(calibrations) not in (tuple, list) or not 3 <= len(calibrations) <= 4:
        raise ValueError("THREE_OR_FOUR_CALIBRATION_SPECIMENS_REQUIRED")
    mats = [np.asarray(a, dtype=np.float64) for a in (reference, *calibrations)]
    expected = (M.shape[1], I.shape[1])
    if any(a.shape != expected or not np.isfinite(a).all() for a in mats):
        raise ValueError("INVALID_CALIBRATION_DIMENSIONS")
    return I, M, C, mats


def augmented_basis(I, M, reference, calibrations, mode="physical_residual", count=COUNT):
    I, M, C, mats = _validate(I, M, reference, calibrations, count)
    _, _, right = linalg.svd(C, full_matrices=False)
    rank = int(np.linalg.matrix_rank(C))
    known = right[:rank]
    if mode == "physical_residual":
        residuals = []
        for V in mats:
            residual = V - (V @ known.T) @ known
            magnitude = np.linalg.norm(residual)
            if not np.isfinite(magnitude) or magnitude <= 1e-12 * max(np.linalg.norm(V), 1.0):
                raise ValueError("UNIDENTIFIABLE_REFERENCE_RESIDUAL")
            residuals.append(residual / magnitude)
        X = np.concatenate(residuals, axis=0)
        _, singular, right_residual = linalg.svd(X, full_matrices=False)
        if singular[EXTRAS - 1] <= singular[0] * 1e-10:
            raise ValueError("INSUFFICIENT_RESIDUAL_MODES")
        extras = right_residual[:EXTRAS] - (right_residual[:EXTRAS] @ known.T) @ known
        q, _ = linalg.qr(extras.T, mode="economic")
        basis = np.vstack((known, q.T))
    elif mode == "conventional_pca":
        # A competent ordinary specialist receives the same reference and
        # physical calibration specimens; no inferior observation budget.
        X = np.concatenate([V / max(np.linalg.norm(V), 1e-300) for V in mats], axis=0)
        _, singular, right_all = linalg.svd(X, full_matrices=False)
        if singular[rank + EXTRAS - 1] <= singular[0] * 1e-10:
            raise ValueError("INSUFFICIENT_CONVENTIONAL_MODES")
        basis = right_all[: rank + EXTRAS]
    else:
        raise ValueError("UNREGISTERED_MODEL")
    if basis.shape != (rank + EXTRAS, I.shape[1]):
        raise ValueError("BASIS_SHAPE_CHANGED")
    return np.asarray(basis, dtype=np.float64)


@dataclass(frozen=True)
class Plan:
    selected: tuple[int, ...]
    geometry_sha256: str
    calibration_sha256: str
    basis_sha256: str
    basis: np.ndarray
    operator: np.ndarray
    mode: str
    patterns: int
    measurements: int
    calibration_specimens: int

    def predict(self, currents, measurements, reference, calibrations, acquired):
        I, M, _, _ = geometry(currents, measurements)
        if signature(I, M) != self.geometry_sha256:
            raise ValueError("GEOMETRY_CHANGED")
        if matrix_hash(reference, *calibrations) != self.calibration_sha256:
            raise ValueError("CALIBRATION_SOURCE_CHANGED")
        if matrix_hash(self.basis) != self.basis_sha256:
            raise ValueError("BASIS_CHANGED")
        V = np.asarray(acquired, dtype=np.float64)
        if V.shape != (self.measurements, len(self.selected)) or not np.isfinite(V).all():
            raise ValueError("INVALID_ACQUIRED_OBSERVATIONS")
        out = V @ self.operator
        out[:, self.selected] = V
        return out


def compile_plan(currents, measurements, reference, calibrations, mode="physical_residual", count=COUNT):
    I, M, _, _ = geometry(currents, measurements)
    B = augmented_basis(I, M, reference, calibrations, mode=mode, count=count)
    selected = tuple(int(j) for j in acquisition_order(B)[:count])
    if len(set(selected)) != count or any(j < 0 or j >= B.shape[1] for j in selected):
        raise ValueError("INVALID_SELECTED_COLUMNS")
    if np.linalg.matrix_rank(B[:, selected]) != B.shape[0]:
        raise ValueError("UNIDENTIFIABLE_ACQUISITION")
    operator = linalg.pinv(B[:, selected], rtol=1e-11) @ B
    return Plan(
        selected, signature(I, M), matrix_hash(reference, *calibrations),
        matrix_hash(B), B, operator, mode, I.shape[1], M.shape[1],
        len(calibrations),
    )


def error(predicted, truth):
    a, b = np.asarray(predicted), np.asarray(truth)
    if a.shape != b.shape or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("NONFINITE_OR_MISMATCHED_EVALUATION")
    norm = np.linalg.norm(b)
    if norm <= 0:
        raise ValueError("ZERO_CONTRAST_REFERENCE")
    return float(np.linalg.norm(a - b) / norm)


def development_gate(errors):
    if len(errors) != 4 or any(type(x) not in (float, int) or not np.isfinite(x) or x < 0 for x in errors):
        raise ValueError("INVALID_FOLD_DENOMINATOR")
    return all(x <= 0.05 for x in errors)
