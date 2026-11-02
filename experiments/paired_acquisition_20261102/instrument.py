from __future__ import annotations

import numpy as np

MU = np.array([[.3681, 2.613], [.1704, .4584], [.1378, .2217]])
MU.setflags(write=False)
ROUND_OFF = 1e-11


def compile_interface(mu=MU):
    matrix = np.array(mu, dtype=float, copy=True)
    if matrix.shape != (3, 2) or not np.isfinite(matrix).all() or np.linalg.matrix_rank(matrix) != 2:
        raise ValueError('finite identifiable three-channel/two-material basis required')
    decoder = np.linalg.pinv(matrix)
    residual = np.eye(3) - matrix @ decoder
    for array in (matrix, decoder, residual):
        array.setflags(write=False)
    return matrix, decoder, residual


RETAINED = compile_interface()


def _readings(a0, b0, a1, b1):
    arrays = tuple(np.asarray(x, dtype=float) for x in (a0, b0, a1, b1))
    shape = arrays[0].shape
    if not shape or shape[-1] != 3 or any(x.shape != shape for x in arrays):
        raise ValueError('four matching arrays ending in three energy channels required')
    if any(not np.isfinite(x).all() or (x <= 0).any() for x in arrays):
        raise ValueError('strictly positive finite corrected observations required')
    return arrays


def _envelope(eps, drift_bound):
    eps, drift_bound = float(eps), float(drift_bound)
    if not np.isfinite(eps) or not 0 <= eps < 1:
        raise ValueError('finite relative observation bound in [0,1) required')
    if not np.isfinite(drift_bound) or drift_bound < 0:
        raise ValueError('finite nonnegative log path-ratio change bound required')
    return drift_bound / 2 + np.log1p(eps) - np.log1p(-eps)


def decode_pair(a0, b0, a1, b1, *, eps=1e-4, drift_bound=2e-4, fresh=False):
    a0, b0, a1, b1 = _readings(a0, b0, a1, b1)
    beta = _envelope(eps, drift_bound)
    matrix, decoder, residual_map = compile_interface() if fresh else RETAINED
    attenuation = .5 * (np.log(b0) - np.log(a0) + np.log(a1) - np.log(b1))
    attenuation_bound = np.full_like(attenuation, beta)
    mass = attenuation @ decoder.T
    mass_bound = attenuation_bound @ np.abs(decoder).T
    residual = attenuation @ residual_map.T
    residual_bound = attenuation_bound @ np.abs(residual_map).T
    accepted = ((mass >= -mass_bound - ROUND_OFF).all(axis=-1)
                & (np.abs(residual) <= residual_bound + ROUND_OFF).all(axis=-1))
    return {'accepted': accepted, 'mass': mass, 'mass_bound': mass_bound,
            'attenuation': attenuation, 'attenuation_bound': attenuation_bound,
            'residual': residual, 'residual_bound': residual_bound}


def decode_spatial(a0, b0, a1, b1, *, geometry, threshold=.10, cell_area=.0625,
                   eps=1e-4, drift_bound=2e-4, fresh=False):
    geometry = np.asarray(geometry, dtype=float)
    if geometry.ndim != 2 or not np.isfinite(geometry).all() or (geometry < 0).any():
        raise ValueError('finite nonnegative path-length matrix required')
    if geometry.shape[1] == 0 or np.linalg.matrix_rank(geometry) != geometry.shape[1]:
        return {'accepted': False, 'reason': 'unidentifiable spatial geometry'}
    threshold, cell_area = float(threshold), float(cell_area)
    if not np.isfinite(threshold) or threshold <= 0 or not np.isfinite(cell_area) or cell_area <= 0:
        raise ValueError('positive finite threshold and cell area required')
    lines = decode_pair(a0, b0, a1, b1, eps=eps, drift_bound=drift_bound, fresh=fresh)
    if lines['mass'].shape != (geometry.shape[0], 2):
        raise ValueError('one spectral observation per ray required')
    if not bool(np.all(lines['accepted'])):
        return {'accepted': False, 'reason': 'spectral contract rejected'}
    decoder = np.linalg.pinv(geometry)
    density = decoder @ lines['mass']
    bound = np.abs(decoder) @ lines['mass_bound']
    residual = geometry @ density - lines['mass']
    residual_bound = np.abs(np.eye(len(geometry)) - geometry @ decoder) @ lines['mass_bound']
    accepted = bool((density >= -bound - ROUND_OFF).all()
                    and (np.abs(residual) <= residual_bound + ROUND_OFF).all())
    lower = np.maximum(0., density[:, 1] - bound[:, 1])
    upper = density[:, 1] + bound[:, 1]
    above, below = lower > threshold, upper <= threshold
    uncertain = ~(above | below)
    area = np.array([np.count_nonzero(above), np.count_nonzero(~below)]) * cell_area
    return {'accepted': accepted, 'density': density, 'density_bound': bound,
            'above': above, 'below': below, 'uncertain': uncertain, 'area_interval': area,
            'geometry_rank': int(np.linalg.matrix_rank(geometry)),
            'geometry_condition': float(np.linalg.cond(geometry))}


def fresh_pair(*args, **kwargs):
    return decode_pair(*args, fresh=True, **kwargs)


def fresh_spatial(*args, **kwargs):
    return decode_spatial(*args, fresh=True, **kwargs)
