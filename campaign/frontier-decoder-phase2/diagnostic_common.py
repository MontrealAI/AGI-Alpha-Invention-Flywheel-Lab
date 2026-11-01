"""Original syndrome-only fallback shared by worker and timeout scorer."""
import math
from functools import reduce
from operator import xor

def mask(indices):
    return reduce(xor, (1 << int(i) for i in indices), 0)

def bits(m):
    while m:
        b = m & -m
        yield b.bit_length() - 1
        m ^= b

class Fallback:
    """Cost-ordered GF(2) witness, not an accuracy-competitive decoder.

    Independently merge identical full (detector, logical) symptoms by exact XOR
    probability. This representation is independent of Tesseract public ID maps.
    """
    def __init__(self, dem):
        parity = {}
        for inst in dem.flattened():
            if inst.type != 'error':
                continue
            h = logical = 0
            for t in inst.targets_copy():
                if t.is_relative_detector_id(): h ^= 1 << t.val
                elif t.is_logical_observable_id(): logical ^= 1 << t.val
            key = (h, logical)
            parity[key] = parity.get(key, 1.0) * (1 - 2 * inst.args_copy()[0])
        self.columns = []
        for (h, logical), q in sorted(parity.items()):
            p = (1 - q) / 2
            if p == 0: continue
            if not 0 < p < 1:
                raise ValueError('Fallback requires non-deterministic positive DEM probabilities')
            self.columns.append((h, logical, math.log((1-p)/p)))
        self.basis = {}
        for i in sorted(range(len(self.columns)), key=lambda i: (self.columns[i][2], i)):
            h = self.columns[i][0]; witness = 1 << i
            while h:
                pivot = h.bit_length() - 1
                if pivot not in self.basis:
                    self.basis[pivot] = h, witness
                    break
                a, b = self.basis[pivot]
                h ^= a; witness ^= b
    def solve(self, syndrome):
        residual = syndrome; witness = 0
        while residual:
            pivot = residual.bit_length() - 1
            if pivot not in self.basis:
                raise ValueError('Sampled syndrome outside DEM column span')
            h, v = self.basis[pivot]; residual ^= h; witness ^= v
        h = logical = 0; cost = 0.0
        for i in bits(witness):
            d, l, w = self.columns[i]; h ^= d; logical ^= l; cost += w
        if h != syndrome: raise AssertionError('Fallback syndrome check failed')
        return {'logical': logical, 'cost': cost,
                'errors': list(bits(witness)), 'error_namespace': 'canonical_symptom_columns'}

def select(candidates):
    """Exact finite-pool sum of relative weights, not full coset probability."""
    scored = sorted(candidates, key=lambda x: (x['cost'], x['errors']))
    best = scored[0]['logical']; offset = scored[0]['cost']; mass = {}
    for c in scored:
        mass[c['logical']] = mass.get(c['logical'], 0.0) + math.exp(offset-c['cost'])
    summed = max(mass, key=lambda l: (mass[l], l == best, -l))
    return best, summed, mass
