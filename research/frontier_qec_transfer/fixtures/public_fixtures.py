"""Public development codes and physical conventions; no recovery implementation."""
from fractions import Fraction
from itertools import product
from math import comb, sqrt
from pathlib import Path
import json


def pollatsek_ruskai_7():
    """Du et al., Characterizing Quantum Codes..., Eq. 23 (Dicke basis)."""
    coefficients = {0: sqrt(15)/8, 2: -sqrt(7)/8,
                    4: sqrt(21)/8, 6: sqrt(21)/8}
    zero = {x: complex(coefficients[x.bit_count()]/sqrt(comb(7,x.bit_count())))
            for x in range(128) if x.bit_count() in coefficients}
    one = {127 ^ x: a for x,a in zero.items()}
    return 7, [zero, one]


def shor_9():
    """Nine-qubit Shor code: products of three |000> +/- |111> blocks."""
    zero, one = {}, {}
    for bits in product((0,1), repeat=3):
        word = int(''.join('111' if b else '000' for b in bits), 2)
        zero[word] = complex(1/sqrt(8))
        one[word] = complex((-1)**sum(bits)/sqrt(8))
    return 9, [zero, one]


def archived_controlled_s_15():
    data = json.loads(Path(__file__).with_name('controlled_s15.json').read_text())
    return data['n'], [
        {int(word,2): complex(sqrt(float(Fraction(prob))))
         for word,prob in cw['probabilities'].items()}
        for cw in data['codewords']
    ]


def apply_local(state, n, qubit, matrix):
    """Physical qubit 0 is the most-significant bit; matrix[out_bit,in_bit]."""
    mask = 1 << (n-1-qubit)
    out = {}
    for word,amp in state.items():
        old = int(bool(word & mask))
        for new in (0,1):
            coefficient = matrix[new][old]
            if coefficient:
                target = (word & ~mask) | (mask if new else 0)
                out[target] = out.get(target,0j) + coefficient*amp
    return {word:amp for word,amp in out.items() if amp != 0}


def development_example(recovery_class):
    """A few visible checks. Withheld qualification covers more than these."""
    import numpy as np
    for factory in (pollatsek_ruskai_7, shor_9, archived_controlled_s_15):
        n, words = factory()
        recovery = recovery_class(n,words)
        logical = np.arange(1,len(words)+1,dtype=complex) + 0.3j
        logical /= np.linalg.norm(logical)
        state = recovery.encode(logical)
        gamma = 0.23
        k0 = np.array([[1,0],[0,sqrt(1-gamma)]],complex)
        k1 = np.array([[0,sqrt(gamma)],[0,0]],complex)
        branches = [apply_local(state,n,n//2,k) for k in (k0,k1)]
        result = recovery.recover(branches)
        assert np.max(np.abs(np.asarray(result['logical_density']) -
                             np.outer(logical,logical.conj()))) < 2e-8
        assert abs(result['erasure_probability']) < 2e-8
        assert abs(result['input_probability']-1) < 2e-8
    return True
