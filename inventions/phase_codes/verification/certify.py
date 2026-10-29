"""Exact independent certificate for the declared sparse probability construction class.

This is a sufficient-class arithmetic proof, not a general QECC classifier or a Lean proof.
No search, optimizer, model, or builder implementation is imported.
"""
import argparse
from fractions import Fraction
import hashlib
import itertools
import json
from pathlib import Path
import re
import sys
import time

LABELS = ['00', '01', '10', '11']
TARGET = [0, 0, 0, 1]
FIELDS = {'n','physical_weights','global_phase_exponent','logical_order','codewords'}


def unique_object(pairs):
    out = {}
    for key,value in pairs:
        if key in out:
            raise ValueError(f'duplicate JSON key: {key}')
        out[key] = value
    return out


def strict_int(x, low, high):
    return type(x) is int and low <= x <= high


def load_candidate(raw):
    obj = json.loads(raw, object_pairs_hook=unique_object,
                     parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f'nonfinite constant {x}')))
    if type(obj) is not dict or set(obj) != FIELDS:
        raise ValueError('input must have exactly the declared fields')
    n = obj['n']
    if not strict_int(n, 2, 128):
        raise ValueError('n must be an integer between2 and128')
    w = obj['physical_weights']
    if type(w) is not list or len(w) != n or not all(strict_int(v,0,3) for v in w):
        raise ValueError('physical_weights must have n integer residues in0..3')
    if not strict_int(obj['global_phase_exponent'],0,3) or obj['logical_order'] != LABELS:
        raise ValueError('global phase or logical order does not follow fixed contract')
    words = obj['codewords']
    if type(words) is not list or len(words) != 4:
        raise ValueError('exactly four codewords required')
    states = []
    for index,row in enumerate(words):
        if type(row) is not dict or set(row) != {'logical','probabilities'} or row['logical'] != LABELS[index]:
            raise ValueError('codeword object or label does not follow contract')
        probs = row['probabilities']
        if type(probs) is not dict or not probs:
            raise ValueError('each logical support must be a nonempty object')
        state = {}
        for bits,ps in probs.items():
            if type(bits) is not str or len(bits) != n or set(bits)-{'0','1'}:
                raise ValueError(f'invalid basis bitstring in logical{LABELS[index]}')
            if type(ps) is not str or re.fullmatch(r'[1-9][0-9]*(/[1-9][0-9]*)?',ps) is None:
                raise ValueError('probabilities must be exact positive rational strings; zeros omitted')
            p = Fraction(ps)
            if p > 1:
                raise ValueError('individual probability exceeds1')
            state[int(bits,2)] = p
        states.append(state)
    return obj,states


def certify(raw):
    obj,states = load_candidate(raw)
    n = obj['n']; w = obj['physical_weights']; g = obj['global_phase_exponent']
    checks = {}; failures = []
    norms = [sum(s.values(),Fraction(0)) for s in states]
    checks['unit_normalization'] = all(v == 1 for v in norms)
    if not checks['unit_normalization']:
        failures.append({'check':'unit_normalization','norms':list(map(str,norms))})
    owner = {}; overlaps = []
    for i,s in enumerate(states):
        for x in s:
            if x in owner:
                overlaps.append({'bits':format(x,f'0{n}b'),'logical_pair':[LABELS[owner[x]],LABELS[i]]})
            else:
                owner[x] = i
    checks['disjoint_supports'] = not overlaps
    if overlaps:failures.append({'check':'disjoint_supports','witness':overlaps[0]})
    positions = [1 << (n-1-j) for j in range(n)]
    flip_masks = positions + [a|b for a,b in itertools.combinations(positions,2)]
    near = None
    for x in owner:
        for mask in flip_masks:
            y = x ^ mask
            if y in owner:
                near = {'x':format(x,f'0{n}b'),'y':format(y,f'0{n}b'),'distance':mask.bit_count()}
                break
        if near:break
    checks['union_support_distance_at_least3'] = near is None
    if near:failures.append({'check':'union_support_distance_at_least3','witness':near,'scope':'sufficient class rejected; general KL not decided'})
    moments = []; mismatches = []
    for mask in flip_masks:
        values = [sum(((-p if (x&mask).bit_count()%2 else p) for x,p in s.items()),Fraction(0)) for s in states]
        moments.append({'z_mask':format(mask,f'0{n}b'),'values':list(map(str,values))})
        if any(v != values[0] for v in values[1:]):
            mismatches.append(moments[-1])
    checks['common_exact_Z_and_ZZ_moments'] = not mismatches
    if mismatches:failures.append({'check':'common_exact_Z_and_ZZ_moments','witness':mismatches[0]})
    phases = []; bad_phase = []
    for i,s in enumerate(states):
        expected = (g+TARGET[i])%4
        found = set()
        for x in s:
            charge = sum(v for bit,v in zip(format(x,f'0{n}b'),w) if bit == '1')%4
            found.add(charge)
            if charge != expected and not bad_phase:
                bad_phase.append({'logical':LABELS[i],'bits':format(x,f'0{n}b'),'actual_exponent':charge,'required_exponent':expected})
        phases.append({'logical':LABELS[i],'required_exponent':expected,'actual_exponents':sorted(found)})
    checks['physical_phase_is_fixed_logical_controlled_S'] = not bad_phase
    if bad_phase:failures.append({'check':'physical_phase_is_fixed_logical_controlled_S','witness':bad_phase[0]})
    ok = all(checks.values())
    return dict(status='CERTIFIED_EXACT_ALGEBRA_ONLY' if ok else 'NOT_CERTIFIED',
        n=n,K=4,logical_order=LABELS,checks=checks,failures=failures,
        support_sizes=[len(s) for s in states],union_support_size=len(owner),norms=list(map(str,norms)),
        exact_diagonal_moments=moments,phase_action=phases,
        detectable_Pauli_weight_bound=2 if ok else None,
        detectable_Pauli_operator_count_including_identity=1+3*n+9*n*(n-1)//2 if ok else None,
        arbitrary_single_qubit_errors_correctable_by_KL=ok,
        quantum_distance_lower_bound=3 if ok else None,
        non_Pauli_stabilizer_certified=ok,
        nonadditivity_reason='physical S powers are Clifford; logical trace modulus squared10 is neither0 nor a power of2' if ok else None,
        LU_inequivalence_to_stabilizer_not_proved=True,
        operational_limits=['ideal algebra only','encoder and recovery not constructed','device and noise not tested','novelty and demand not certified'])


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('candidate',type=Path);ap.add_argument('--expected-sha256',required=True)
    ap.add_argument('--output',required=True,type=Path)
    a=ap.parse_args()
    if a.output.exists():raise SystemExit('Output already exists; refusing overwrite')
    raw=a.candidate.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if digest != a.expected_sha256:raise SystemExit('Candidate SHA256 does not match frozen input')
    try:
        result=certify(raw);code=0 if result['status']=='CERTIFIED_EXACT_ALGEBRA_ONLY' else 1
    except (ValueError,TypeError,KeyError,OverflowError) as e:
        result={'status':'INPUT_REJECTED','reason':str(e)};code=2
    result.update(candidate_sha256=digest,verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        spec_sha256=hashlib.sha256((Path(__file__).parent/'SPEC.json').read_bytes()).hexdigest(),
        completed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ['status','candidate_sha256','verifier_sha256']}))
    raise SystemExit(code)


if __name__=='__main__':main()
