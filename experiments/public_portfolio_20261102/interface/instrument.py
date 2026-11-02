"""Research-only reference-normalized spectral transmission interface.

The model is monochromatic, two-material Beer-Lambert transmission. It is not a
physical instrument, photon-counting uncertainty model, or deployment approval.
"""
from __future__ import annotations

import numpy as np

ENERGIES_KEV = (50.0, 100.0, 150.0)
MATERIALS = ("aluminum", "copper")
MU_CM2_G = np.array([[0.3681, 2.613], [0.1704, 0.4584], [0.1378, 0.2217]])
COMPILER_VERSION = "spectral-reference-interface-v1"


def compile_interface(mu=MU_CM2_G):
    matrix = np.asarray(mu, dtype=float)
    if matrix.ndim != 2 or matrix.shape != (3, 2) or not np.isfinite(matrix).all():
        raise ValueError("finite three-energy/two-material matrix required")
    if np.linalg.matrix_rank(matrix) != 2:
        raise ValueError("unidentifiable material basis")
    decoder = np.linalg.pinv(matrix)
    return {"matrix": matrix.copy(), "decoder": decoder,
            "residual_map": np.eye(3) - matrix @ decoder,
            "version": COMPILER_VERSION}


FROZEN_INTERFACE = compile_interface()


def estimate(sample, reference, dark, relative_error_bound=0.0001, interface=None):
    """Infer areal density, conditional on calibrated common sample/reference gain.

The error bound concerns each dark-corrected sample/reference signal, not raw
counts. Users must independently justify dark-frame error within that envelope.
No data-only guard can detect all coherent departures from this contract.
"""
    data = [np.asarray(v, dtype=float) for v in (sample, reference, dark)]
    if not all(v.shape == data[0].shape for v in data) or data[0].ndim < 1 or data[0].shape[-1] != 3:
        raise ValueError("matching arrays ending in three energies required")
    if not all(np.isfinite(v).all() for v in data):
        raise ValueError("nonfinite observation")
    eps = float(relative_error_bound)
    if not np.isfinite(eps) or not 0 <= eps < 1:
        raise ValueError("relative_error_bound must be finite in [0,1)")
    asset = FROZEN_INTERFACE if interface is None else interface
    corrected_sample, corrected_reference = data[0] - data[2], data[1] - data[2]
    valid_signal = (corrected_sample > 0).all(axis=-1) & (corrected_reference > 0).all(axis=-1)
    a = (np.log(np.maximum(corrected_reference, np.finfo(float).tiny)) -
         np.log(np.maximum(corrected_sample, np.finfo(float).tiny)))
    mass = a @ asset["decoder"].T
    log_bound = np.log1p(eps) - np.log1p(-eps)
    mass_bound = np.abs(asset["decoder"]).sum(axis=1) * log_bound + 1e-11
    residual_bound = np.abs(asset["residual_map"]).sum(axis=1) * log_bound + 1e-11
    residual = a - mass @ asset["matrix"].T
    valid_model = (np.abs(residual) <= residual_bound).all(axis=-1)
    valid_mass = (mass >= -mass_bound).all(axis=-1)
    accepted = valid_signal & valid_model & valid_mass
    return {"accepted": accepted, "mass_areal_density_g_cm2": mass,
            "component_error_bound_g_cm2": mass_bound,
            "log_attenuation": a, "log_residual": residual,
            "log_residual_bound": residual_bound,
            "valid_signal": valid_signal, "valid_model": valid_model,
            "valid_nonnegative_material": valid_mass,
            "scope": "conditional monochromatic two-material common-gain model"}


def conventional(sample, reference, dark):
    """Independent standard flat-field/log/SVD material decomposition comparator."""
    s, r, d = (np.asarray(v, dtype=float) for v in (sample, reference, dark))
    if s.ndim < 1 or s.shape != r.shape or s.shape != d.shape or s.shape[-1] != 3:
        raise ValueError("incompatible observations")
    if not all(np.isfinite(v).all() for v in (s, r, d)) or (s <= d).any() or (r <= d).any():
        raise ValueError("invalid corrected observations")
    attenuation = np.log(r - d) - np.log(s - d)
    return np.linalg.lstsq(MU_CM2_G, attenuation.reshape(-1, 3).T, rcond=None)[0].T.reshape(s.shape[:-1] + (2,))


def ray_matrix(size=4, cell_side_cm=0.25, angles=None, offsets=None):
    """Exact straight-ray/cell segment lengths for an ideal parallel-beam grid."""
    if not isinstance(size, int) or size < 1 or cell_side_cm <= 0:
        raise ValueError("positive geometry required")
    angles = np.linspace(0, np.pi, 9, endpoint=False) if angles is None else np.asarray(angles, dtype=float)
    extent = size * cell_side_cm / 2
    offsets = np.linspace(-extent * 1.3, extent * 1.3, 11) if offsets is None else np.asarray(offsets, dtype=float)
    rows = []
    for angle in angles:
        normal = np.array([np.cos(angle), np.sin(angle)])
        direction = np.array([-np.sin(angle), np.cos(angle)])
        for offset in offsets:
            origin = normal * offset
            lengths = []
            for iy in range(size):
                for ix in range(size):
                    lower = np.array([ix, iy]) * cell_side_cm - extent
                    upper = lower + cell_side_cm
                    t_low, t_high = -np.inf, np.inf
                    for axis in (0, 1):
                        if abs(direction[axis]) < 1e-12:
                            if not lower[axis] <= origin[axis] < upper[axis]:
                                t_low, t_high = 1, 0
                        else:
                            first, last = sorted(((lower[axis] - origin[axis]) / direction[axis],
                                                  (upper[axis] - origin[axis]) / direction[axis]))
                            t_low, t_high = max(t_low, first), min(t_high, last)
                    lengths.append(max(0.0, t_high - t_low))
            rows.append(lengths)
    return np.asarray(rows)


def reconstruct(sample, reference, dark, projection_matrix, image_shape=(4, 4),
                relative_error_bound=0.0001, inherit=True):
    """Construct a new spatial density function from a retained spectral interface."""
    geometry = np.asarray(projection_matrix, dtype=float)
    pixels = int(np.prod(image_shape))
    if geometry.ndim != 2 or geometry.shape[1] != pixels or not np.isfinite(geometry).all() or (geometry < 0).any():
        raise ValueError("invalid nonnegative geometry")
    if np.linalg.matrix_rank(geometry) != pixels:
        return {"accepted": False, "reason": "unidentifiable spatial geometry"}
    asset = FROZEN_INTERFACE if inherit else compile_interface()
    lines = estimate(sample, reference, dark, relative_error_bound, interface=asset)
    if lines["accepted"].shape != (geometry.shape[0],):
        raise ValueError("one spectral observation per ray required")
    if not lines["accepted"].all():
        return {"accepted": False, "reason": "spectral contract rejected"}
    spatial_decoder = np.linalg.pinv(geometry)
    density = spatial_decoder @ lines["mass_areal_density_g_cm2"]
    density_bounds = np.abs(spatial_decoder).sum(axis=1)[:, None] * lines["component_error_bound_g_cm2"][None, :] + 1e-10
    residual = geometry @ density - lines["mass_areal_density_g_cm2"]
    propagated = (np.abs(np.eye(len(geometry)) - geometry @ spatial_decoder).sum(axis=1)[:, None] *
                  lines["component_error_bound_g_cm2"][None, :] + 1e-10)
    accepted = bool((density >= -density_bounds).all() and (np.abs(residual) <= propagated).all())
    return {"accepted": accepted, "density_g_cm3": density.reshape(tuple(image_shape) + (2,)),
            "component_error_bound_g_cm3": density_bounds.reshape(tuple(image_shape) + (2,)),
            "geometry_rank": pixels, "geometry_condition_number": float(np.linalg.cond(geometry)),
            "inherited": inherit}
