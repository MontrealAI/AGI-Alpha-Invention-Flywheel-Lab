"""Independent conventional Kelvin/current-reversal interval comparator.

Assumes passive R,C >= 0, stable per-channel offsets within each session,
independent bounded voltage errors, bounded current error per observation,
and constant positive gain and sense fraction per session. No truth labels read.
All bounds use rational arithmetic; only JSON output is outward-rounded.

Conventional foundations: Keysight, How to Measure Resistance Using Four-Wire
Measurement; Keithley Low Level Measurements Handbook, 7th edition, current
reversal for thermoelectric EMFs. These sources establish the measurement
methods, not the synthetic error budgets or this software's correctness.
https://www.keysight.com/us/en/use-cases/measure-resistance-using-four-wire-measurement.html
https://www.tek.com/en/documents/product-article/keithley-low-level-measurements-handbook---7th-edition

A nominal-current feasibility witness is deliberately required. Valid data
requiring nonzero current corrections may therefore be conservatively rejected.
"""
from fractions import Fraction as F
from itertools import combinations
import math


def number(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError('Expected finite number')
    if not math.isfinite(x):
        raise ValueError('Expected finite number')
    return F(str(x))


def bounds(x):
    if not isinstance(x, (list, tuple)) or len(x) != 2:
        raise ValueError('Expected interval')
    lo, hi = map(number, x)
    if not 0 < lo <= hi:
        raise ValueError('Nonpositive or reversed range')
    return lo, hi


def slopes(rows, channel, ev, ei):
    # For every pair, dy = slope*dx + (e_j-e_i). Stable offset cancels.
    lo, hi = F(0), None
    for a, b in combinations(rows, 2):
        dx, dy = b[0]-a[0], b[channel]-a[channel]
        if dx < 0:
            dx, dy = -dx, -dy
        dl, dh = dx-2*ei, dx+2*ei
        vl, vh = dy-2*ev, dy+2*ev
        if dh == 0:
            if not vl <= 0 <= vh:
                raise ValueError('Inconsistent duplicate current')
            continue
        if dl <= 0:
            # Such pairs add no safe constraint here; reversal pairs do.
            continue
        lo = max(lo, vl/dh)
        upper = vh/dl
        hi = upper if hi is None else min(hi, upper)
    if hi is None or hi < lo:
        raise ValueError('Inconsistent or unidentifiable slope')
    return lo, hi


def session(s):
    ev, ei = number(s['voltage_error']), number(s['current_error'])
    if ev < 0 or ei < 0:
        raise ValueError('Negative error bound')
    gl, gh = bounds(s['gain_range'])
    fl, fh = bounds(s['sense_fraction_range'])
    if fh > 1:
        raise ValueError('Sense fraction extends outside the rod')
    records = s['records']
    if not isinstance(records, list) or not records or len(records) % 2:
        raise ValueError('Missing complete reversal pairs')
    rows = [(number(r['current']), number(r['v2']), number(r['v4'])) for r in records]
    for a,b in zip(rows[::2], rows[1::2]):
        if not ((a[0] > ei and b[0] < -ei) or (b[0] > ei and a[0] < -ei)):
            raise ValueError('Unsafe current reversal')
    # Nominal currents are allowed realizations. Pairwise offset intervals
    # intersect iff all pair inequalities hold, so each slope range is exact
    # for that witness. Choose A=max and B=min; B <= f_max*A proves C>=0.
    na, nb = slopes(rows, 1, ev, F(0)), slopes(rows, 2, ev, F(0))
    if nb[0] > fh*na[1]:
        raise ValueError('No passive nominal-current witness')
    al, ah = slopes(rows, 1, ev, ei)
    bl, bh = slopes(rows, 2, ev, ei)
    if bl > fh*ah:
        raise ValueError('Inconsistent channel slopes')
    # A=g(R+C), B=g*f*R. Shared g retained where easy; other dependence
    # discarded only outward, producing conservative projections.
    bulk = (bl/fh/gh, min(bh/fl, ah)/gl)
    contact = (max(F(0), al-bh/fl)/gh, (ah-bl/fh)/gl)
    if bulk[0] > bulk[1] or contact[0] > contact[1]:
        raise ValueError('Empty projection')
    return {'bulk':bulk, 'contact':contact}


def outward(q, up):
    v = float(q)
    if not math.isfinite(v):
        raise ValueError('Unrepresentable output')
    if (up and F(v) < q) or (not up and F(v) > q):
        v = math.nextafter(v, math.inf if up else -math.inf)
    if not math.isfinite(v):
        raise ValueError('Unrepresentable output')
    return v


def encode(s):
    return {k:None if v is None else [outward(v[0],False),outward(v[1],True)] for k,v in s.items()}


def analyze(observation):
    empty = {'bulk':None, 'contact':None}
    sessions = {}
    for name in ('baseline','after'):
        try:
            sessions[name] = session(observation[name])
            encode(sessions[name])
        except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError):
            sessions[name] = empty.copy()
    diff, classes = empty.copy(), {'sample':'ambiguous','contact':'ambiguous'}
    for key, label, tolerance in [('bulk','sample',F(1,2)),('contact','contact',F(1,4))]:
        a, b = sessions['baseline'][key], sessions['after'][key]
        if a is None or b is None:
            continue
        d = (b[0]-a[1],b[1]-a[0])
        try:
            delivered = encode({key:d})[key]
        except (ValueError, OverflowError):
            continue
        diff[key] = d
        # Labels are certified by the serialized outward-rounded interval.
        if delivered[0] > tolerance or delivered[1] < -tolerance:
            classes[label] = 'changed'
        elif delivered[0] >= -tolerance and delivered[1] <= tolerance:
            classes[label] = 'unchanged'
    return {'baseline':encode(sessions['baseline']), 'after':encode(sessions['after']),
            'difference':encode(diff), 'classifications':classes}
