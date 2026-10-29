"""Necessary applicability checks for the inherited zero-moment scaffold.

This is an executable retention of a model-derived criticism, not an autonomous
discovery of the mathematical representation or a sufficient existence test.
"""
from __future__ import annotations
import argparse, json, pathlib

def analyze(n):
    if type(n) is not int or not 8 <= n <= 20:
        raise ValueError('RESOURCE_BOUND')
    rows = [sum(((j+1) >> i & 1) << j for j in range(n)) for i in range(n.bit_length())]
    dual = []
    for selector in range(1, 1 << len(rows)):
        mask = 0
        for i, row in enumerate(rows):
            if selector >> i & 1: mask ^= row
        if mask: dual.append(mask)
    witnesses = sorted({mask for mask in dual if mask.bit_count() <= 2})
    return {'n': n, 'parity_columns': list(range(1, n+1)),
            'minimum_nonzero_dual_weight': min(x.bit_count() for x in dual),
            'zero_moment_contradiction': bool(witnesses),
            'contradiction_masks': [format(m, f'0{n}b') for m in witnesses],
            'proof': 'Every scaffold word obeys dual parity=0. Its corresponding Z product has expectation+1 for every normalized distribution. A weight1/2 such product contradicts the required zero moment.',
            'decision': 'REJECT_PROVED_INCOMPATIBLE' if witnesses else 'UNKNOWN_REQUIRES_CONSTRUCTION',
            'scope': 'Necessary applicability check only. No existence, novelty, demand or sufficient code certificate.'}

if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('--n', type=int, nargs='+', required=True); p.add_argument('--output',required=True); a=p.parse_args()
    out=pathlib.Path(a.output)
    with out.open('x') as h: json.dump([analyze(n) for n in a.n],h,indent=2); h.write('\n')
