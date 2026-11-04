"""Declared independent-Hertz contact model and integer construction.

Units: mm, N, MPa=N/mm^2. Calibration values are input assumptions, not
certified material properties. No account, device, network or model API access.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path

SCHEMA = 'genesis/surface-request/v1'


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()


def read(path):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError('duplicate JSON field: ' + key)
            result[key] = value
        return result
    raw = Path(path).read_bytes()
    if len(raw) > 1_000_000:
        raise ValueError('request exceeds declared 1 MB parser limit')
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def number(x, label, minimum=0, strict=False):
    if type(x) not in (int, float) or not math.isfinite(x) or (x <= minimum if strict else x < minimum):
        raise ValueError('invalid ' + label)
    return float(x)


def validate(s):
    if not isinstance(s, dict) or set(s) != {'schema', 'id', 'source', 'reference_height_mm',
        'height_menu_mm', 'maximum_contacts', 'pitch_mm', 'base_thickness_mm', 'families', 'states'}:
        raise ValueError('exact request fields required')
    if s['schema'] != SCHEMA or not isinstance(s['id'], str) or not 1 <= len(s['id']) <= 120:
        raise ValueError('request identity')
    if (not isinstance(s['source'], dict) or not isinstance(s['source'].get('url'),str)
            or not s['source']['url'].startswith('https://') or not isinstance(s['source'].get('scope'),str)
            or not s['source']['scope']):
        raise ValueError('explicit source and calibration scope required')
    reference = number(s['reference_height_mm'], 'reference height', strict=True)
    number(s['pitch_mm'], 'pitch', strict=True)
    number(s['base_thickness_mm'], 'base thickness', strict=True)
    if type(s['maximum_contacts']) is not int or not 1 <= s['maximum_contacts'] <= 256:
        raise ValueError('this adapter supports 1..256 sites; not an enterprise limit')
    heights = s['height_menu_mm']
    if not isinstance(heights, list) or not 1 <= len(heights) <= 64:
        raise ValueError('height menu')
    for h in heights:
        if number(h, 'height', strict=True) > reference:
            raise ValueError('height exceeds reference')
    if heights != sorted(set(heights)):
        raise ValueError('heights must be sorted and unique')
    families = s['families']
    if not isinstance(families, list) or not 1 <= len(families) <= 8:
        raise ValueError('family count')
    ids = []
    for f in families:
        if not isinstance(f, dict) or set(f) != {'id','radius_mm','modulus_MPa','static_MPa','dynamic_MPa',
                                               'static_range_MPa','dynamic_range_MPa'}:
            raise ValueError('exact family fields')
        if not isinstance(f['id'], str) or not f['id'] or len(f['id']) > 80:
            raise ValueError('family id')
        ids.append(f['id'])
        r = number(f['radius_mm'], 'radius', strict=True)
        number(f['modulus_MPa'], 'modulus', strict=True)
        if reference >= r or 2 * math.sqrt(2*r*reference - reference**2) >= s['pitch_mm']:
            raise ValueError('cap geometry overlaps or exceeds sphere')
        for key in ('static', 'dynamic'):
            nominal = number(f[key+'_MPa'], key, strict=True)
            limits = f[key+'_range_MPa']
            if not isinstance(limits, list) or len(limits) != 2:
                raise ValueError('explicit sensitivity interval')
            low, high = [number(v, 'sensitivity bound', strict=True) for v in limits]
            if not low <= nominal <= high:
                raise ValueError('nominal outside sensitivity interval')
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate family')
    states = s['states']
    if not isinstance(states, list) or not 1 <= len(states) <= 64:
        raise ValueError('state count')
    for state in states:
        if not isinstance(state, dict) or set(state) != {'indentation_mm','normal_N','static_N','dynamic_N','ratio'}:
            raise ValueError('exact state fields')
        d = number(state['indentation_mm'], 'indentation', strict=True)
        if d >= reference or d / min(f['radius_mm'] for f in families) > .25:
            raise ValueError('outside declared small-indentation geometry envelope')
        for key in ('normal_N','static_N','dynamic_N','ratio'):
            v = state[key]
            if not isinstance(v, list) or len(v) != 2:
                raise ValueError('closed target intervals required')
            lo, hi = [number(x, key) for x in v]
            if lo > hi or (key == 'dynamic_N' and lo <= 0):
                raise ValueError('invalid target interval / positive dynamic lower bound required')
    return s


def basis(s):
    """Columns are physical site types, not prespecified complete surfaces."""
    import numpy as np
    validate(s)
    choices = [(f['id'], h) for f in s['families'] for h in s['height_menu_mm']]
    lookup = {f['id']: f for f in s['families']}
    rows = []
    for state in s['states']:
        values = []
        for fid, h in choices:
            f = lookup[fid]
            depth = max(0., state['indentation_mm'] - (s['reference_height_mm']-h))
            area = math.pi*f['radius_mm']*depth
            normal = (4./3.)*f['modulus_MPa']*math.sqrt(f['radius_mm'])*depth**1.5
            values.append((normal, area*f['static_MPa'], area*f['dynamic_MPa']))
        rows.append(np.asarray(values, dtype=float).T)
    return choices, rows


def construct(s, family=None):
    """Ordinary mixed-integer optimization, not a claim of a new algorithm."""
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    choices, state_rows = basis(s)
    if family is not None and family not in {f['id'] for f in s['families']}:
        raise ValueError('unknown family restriction')
    matrix, lower, upper = [], [], []
    for state, row in zip(s['states'], state_rows):
        for key, coeff in zip(('normal_N','static_N','dynamic_N'), row):
            scale = max(1., state[key][1])
            matrix.append(coeff/scale)
            lower.append(state[key][0]/scale)
            upper.append(state[key][1]/scale)
        matrix.extend((row[1]-state['ratio'][0]*row[2], row[1]-state['ratio'][1]*row[2]))
        lower.extend((0., -np.inf)); upper.extend((np.inf, 0.))
    matrix.append(np.ones(len(choices))); lower.append(1); upper.append(s['maximum_contacts'])
    hi = [s['maximum_contacts'] if family is None or fid == family else 0 for fid, _ in choices]
    result = milp(np.ones(len(choices)), integrality=np.ones(len(choices)),
                  bounds=Bounds(np.zeros(len(choices)), hi),
                  constraints=LinearConstraint(np.asarray(matrix), lower, upper),
                  options={'mip_rel_gap': 0.})
    record = {'schema':'genesis/surface-design/v1', 'request_sha256':digest(s),
              'family_restriction':family, 'solver_status':int(result.status),
              'solver_message':str(result.message), 'contacts':[],
              'physical_qualification':False, 'commercial_qualification':False,
              'algorithm':'scipy.optimize.milp / HiGHS; all available families eligible'}
    if result.x is None:
        record['status'] = 'INFEASIBLE_IN_DECLARED_MODEL' if result.status == 2 else 'UNRESOLVED'
        return record
    rounded = np.rint(result.x)
    if np.max(np.abs(result.x-rounded)) > 1e-5:
        raise ValueError('nonintegral solver output')
    record['contacts'] = [{'family':fid, 'height_mm':h, 'count':int(n)}
        for (fid,h),n in zip(choices,rounded) if n > 0]
    record['status'] = 'CANDIDATE_REQUIRES_CHECK'
    record['solver_reports_optimal'] = result.status == 0
    record['optimality_scope'] = 'Numerical solver status in the declared integer grammar; not an independently proved global or physical optimum.'
    return record
