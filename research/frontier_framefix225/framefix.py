"""Physical-gauge-invariant informationally complete noise receiver.

Research-only alternative to the frozen NoiseExperiment frame. This module
does NOT modify the QEC owner's Recovery, NoiseExperiment, or financial code.

The syndrome coordinates exported by an eigensolver have an arbitrary unitary
gauge inside degenerate Gram eigenspaces. A fixed IC readout tied to those
coordinates is therefore not a fixed physical instrument. We anchor a NEW
receiver to the ordered physical computational basis before choosing its POVM.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

import numpy as np

TOL = 2e-8


def pinned_blob_sha1(path: Path) -> str:
    """Git's exact blob identity, not a textual or filename-only pin."""
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def syndrome_anchor(recovery: np.ndarray, threshold: float = 1e-9) -> np.ndarray:
    """Gauge-equivariant deterministic syndrome coordinates (basis columns).

    First logical-output rows of the physical recovery map span the syndrome.
    Twice-reorthogonalized Gram-Schmidt consumes the corresponding physical
    computational basis columns in fixed ascending order. Under R->Q R,
    the anchor becomes U->Q U, so U^H R is gauge invariant.

    A near-dependent or ill-conditioned input refuses instead of choosing an
    unstable axis. This construction is NOT an optimizer for hardware cost.
    """
    recovery = np.asarray(recovery, dtype=np.complex128)
    if (recovery.ndim != 3 or recovery.shape[0] < 1 or
        recovery.shape[1] < 1 or recovery.shape[2] < recovery.shape[0] or
        not np.all(np.isfinite(recovery))):
        raise ValueError("invalid recovery tensor")
    if not (0 < threshold < 1e-4):
        raise ValueError("invalid fixed rank threshold")

    rank = recovery.shape[0]
    columns = recovery[:, 0, :]
    # Fail on a faulty input rather than accepting a different gauge model.
    if np.max(np.abs(columns @ columns.conj().T - np.eye(rank))) > TOL:
        raise ValueError("first logical recovery rows are not an isometry")

    axes = []
    for index in range(columns.shape[1]):
        v = columns[:, index].copy()
        for _ in range(2):
            for axis in axes:
                v -= axis * np.vdot(axis, v)
        norm = float(np.linalg.norm(v))
        if norm <= threshold:
            continue
        axes.append(v / norm)
        if len(axes) == rank:
            break
    if len(axes) != rank:
        raise ValueError("physical reference columns do not span syndrome")
    U = np.column_stack(axes)
    if np.max(np.abs(U.conj().T @ U - np.eye(rank))) > TOL:
        raise ValueError("canonical syndrome anchor failed orthogonality")
    return U


def fixed_ic_bras(rank: int) -> np.ndarray:
    """Deterministic r^2-outcome tight frame without eigenspace ambiguity."""
    if isinstance(rank, bool) or not isinstance(rank, (int, np.integer)) or not 1 <= rank <= 128:
        raise ValueError("invalid syndrome rank")
    raw = np.zeros((rank * rank, rank), dtype=np.complex128)
    raw[:rank] = np.eye(rank)
    cursor = rank
    for j in range(rank):
        for k in range(j + 1, rank):
            raw[cursor, j] = raw[cursor, k] = 1 / np.sqrt(2)
            cursor += 1
            raw[cursor, j] = 1 / np.sqrt(2)
            raw[cursor, k] = 1j / np.sqrt(2)
            cursor += 1
    assert cursor == rank * rank
    gram = raw.conj().T @ raw
    cholesky = np.linalg.cholesky(gram)
    # If gram=L L*, M=(L*)^-1, then M* gram M=I.
    inverse_right = np.linalg.solve(cholesky.conj().T, np.eye(rank))
    bras = raw @ inverse_right
    if np.max(np.abs(bras.conj().T @ bras - np.eye(rank))) > TOL:
        raise ValueError("informationally complete frame fails normalization")
    return bras


@dataclass(frozen=True)
class CanonicalMeasurement:
    bras: np.ndarray
    physical_operators: np.ndarray
    response: np.ndarray
    syndrome_states: np.ndarray
    anchor: np.ndarray
    frame_residual: float
    physical_completeness_residual: float
    max_column_error: float

    def pair_distances(self):
        """All unordered pure-model total variations, including zero-distance."""
        m = self.response.shape[1]
        return [((i, j), float(0.5 * np.abs(
            self.response[:, i] - self.response[:, j]).sum()))
                for i in range(m) for j in range(i + 1, m)]


def build_canonical(recovery, syndrome_states) -> CanonicalMeasurement:
    """Build the physically anchored alternative measurement and audit it."""
    R = np.asarray(recovery, dtype=np.complex128)
    S = np.asarray(syndrome_states, dtype=np.complex128)
    if R.ndim != 3 or S.ndim != 3 or S.shape[1:] != (R.shape[0], R.shape[0]):
        raise ValueError("incompatible recovery and syndrome states")
    if not len(S) or not np.all(np.isfinite(R)) or not np.all(np.isfinite(S)):
        raise ValueError("nonfinite or empty physical source")
    if np.max(np.abs(S - S.conj().transpose(0, 2, 1))) > TOL:
        raise ValueError("non-Hermitian noise syndrome state")
    if np.max(np.abs(np.trace(S, axis1=1, axis2=2) - 1)) > TOL:
        raise ValueError("unnormalized noise syndrome state")

    U = syndrome_anchor(R)
    Rfixed = np.einsum("as,sid->aid", U.conj().T, R, optimize=True)
    Sfixed = U.conj().T @ S @ U
    bras = fixed_ic_bras(R.shape[0])
    physical = np.einsum("oa,aid->oid", bras, Rfixed, optimize=True)
    complex_probs = np.einsum(
        "oi,hij,oj->oh", bras, Sfixed, bras.conj(), optimize=True)
    if np.max(np.abs(complex_probs.imag)) > TOL:
        raise ValueError("complex measurement probabilities")
    response = complex_probs.real
    if np.min(response) < -TOL:
        raise ValueError("negative measurement probability")
    normalization = float(np.max(np.abs(response.sum(axis=0) - 1)))
    if normalization > TOL:
        raise ValueError("incomplete measurement probabilities")
    if np.min(response) < 0:
        response = np.maximum(response, 0.0)  # only <TOL numerical noise
    frame_residual = float(np.max(np.abs(bras.conj().T @ bras - np.eye(R.shape[0]))))
    # Full physical effect equality, not just reduced syndrome normalization.
    x = physical.reshape(-1, R.shape[2])
    y = R.reshape(-1, R.shape[2])
    completeness = float(np.max(np.abs(x.conj().T @ x - y.conj().T @ y)))
    if completeness > TOL:
        raise ValueError("physical Kraus completeness changed")
    return CanonicalMeasurement(
        bras, physical, response, Sfixed, U, frame_residual,
        completeness, normalization)


def apply_syndrome_gauge(recovery, states, Q):
    """Metamorphic gauge input: same physical effects in arbitrary coordinates."""
    R = np.asarray(recovery, complex)
    S = np.asarray(states, complex)
    Q = np.asarray(Q, complex)
    rank = R.shape[0]
    if Q.shape != (rank, rank) or np.max(
        np.abs(Q.conj().T @ Q - np.eye(rank))) > TOL:
        raise ValueError("nonunitary proposed syndrome gauge")
    return np.einsum("as,sid->aid", Q, R, optimize=True), Q @ S @ Q.conj().T


def fixed_unitary(rank: int, seed: int) -> np.ndarray:
    """Preregistered deterministic complex gauge, never chosen by outcome."""
    rng = np.random.default_rng(seed)
    z = rng.standard_normal((rank, rank)) + 1j * rng.standard_normal((rank, rank))
    q, r = np.linalg.qr(z)
    diag = np.diag(r)
    return q @ np.diag(np.conj(diag) / np.abs(diag))
