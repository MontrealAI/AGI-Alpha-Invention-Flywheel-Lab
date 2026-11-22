"""Run the registered Lean 4.36 bit-vector experiment with two approved local releases."""

from argparse import ArgumentParser
from hashlib import sha256
from itertools import product
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
from time import perf_counter

VERSIONS = ('4.35.0', '4.36.0')
FEATURE = 'https://lean-lang.org/doc/reference/latest/releases/v4.36.0/'
EXPERIMENT = 'lean-4.36-black-box-bit-vector-congruence'
ONE_ARGUMENT = '''(oracle : BitVec 4 → BitVec 4) (x mask : BitVec 4) (fixed : x &&& mask = x) :
    oracle (x ^^^ 0) = oracle (x &&& mask)'''
TWO_ARGUMENTS = '''(oracle : BitVec 4 → BitVec 4 → BitVec 4) (x mask value : BitVec 4) (fixed : x ||| mask = x) :
    oracle (x ^^^ 0) ((value ^^^ mask) ^^^ mask) = oracle (x ||| mask) (value &&& 15)'''
MANUAL_TWO = '''have left : x ^^^ 0 = x ||| mask := by bv_decide
  have right : (value ^^^ mask) ^^^ mask = value &&& 15 := by bv_decide
  exact (congrArg (fun z => oracle z ((value ^^^ mask) ^^^ mask)) left).trans (congrArg (oracle (x ||| mask)) right)'''
CASES = (
    ('one_argument', ONE_ARGUMENT, 'exact congrArg oracle (by bv_decide)'),
    ('two_arguments', TWO_ARGUMENTS, MANUAL_TWO),
)
WRONG = TWO_ARGUMENTS.replace('(value &&& 15)', '((value &&& 15) ||| 1)')


def independent_reference():
    """Compare argument tuples and use the second projection to witness the false case."""
    pairs = [(x, mask) for x, mask in product(range(16), repeat=2) if x & mask == x]
    triples = [(x, mask, value) for x, mask, value in product(range(16), repeat=3) if x | mask == x]
    if not all((x ^ 0) == (x & mask) for x, mask in pairs):
        raise ValueError('One-argument reference failed')
    if not all((x ^ 0, (value ^ mask) ^ mask) == (x | mask, value & 15) for x, mask, value in triples):
        raise ValueError('Two-argument reference failed')
    witness = next((x, mask, value) for x, mask, value in triples if (value ^ mask) ^ mask != ((value & 15) | 1))
    return {'one_argument_inputs': len(pairs), 'two_argument_inputs': len(triples),
            'invalid_case_witness': dict(zip(('x', 'mask', 'value'), witness, strict=True)),
            'witness_oracle': 'second argument'}


def subprocess_result(binary, *args, cwd=None):
    return subprocess.run([binary, *args], cwd=cwd, capture_output=True, text=True, timeout=30,
                          env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}, check=False)


def check(binary, folder, case, statement, tactic, method):
    payload = (f'import Std.Tactic.BVDecide\nset_option maxHeartbeats 200000\nset_option warningAsError true\n'
               f'theorem frontier_check {statement} := by\n  {tactic}\n#print axioms frontier_check\n')
    (folder / 'Proof.lean').write_text(payload, encoding='utf-8')
    started = perf_counter()
    result = subprocess_result(binary, 'Proof.lean', cwd=folder)
    elapsed = perf_counter() - started
    output = result.stdout + result.stderr
    audit = re.search(r"(?m)^'frontier_check' (?:depends on axioms: \[[^\]]+\]|does not depend on any axioms)", output)
    axioms = ' '.join(audit.group().split()) if audit else None
    counterexample = re.search(r'(?m)(?:^|error: )The prover found a (?:potentially spurious )?counterexample[,:]', output)
    return {'case': case, 'method': method, 'accepted': result.returncode == 0 and axioms is not None and 'sorryAx' not in axioms,
            'source_sha256': sha256(payload.encode()).hexdigest(), 'axioms': axioms,
            'diagnostic': next((line[:220] for line in output.splitlines() if 'error:' in line), None),
            'reports_counterexample': bool(counterexample),
            'wall_seconds': round(elapsed, 6)}


def compare(before, after):
    reference = independent_reference()
    outcomes = []
    with TemporaryDirectory(prefix='frontier-lean-delta-') as working:
        folder = Path(working)
        for version, binary in zip(VERSIONS, (before, after), strict=True):
            binary = binary.resolve(strict=True)
            reported = subprocess_result(binary, '--version')
            if reported.returncode or not re.search(r'\bversion ' + re.escape(version) + ',', reported.stdout):
                raise ValueError('Use the registered Lean release ' + version)
            proofs = []
            for name, statement, manual in CASES:
                for method, tactic in [('explicit_congruence', manual), ('grind', 'grind'),
                                       ('default_bv', 'bv_decide'), ('uf_bv', 'bv_decide +uf')]:
                    proofs.append(check(binary, folder, name, statement, tactic, method))
            if version == VERSIONS[-1]:
                proofs.append(check(binary, folder, 'invalid_two_arguments', WRONG, 'bv_decide +uf', 'uf_bv'))
            outcomes.append({'version': reported.stdout.strip(), 'proofs': proofs})
    before_proofs, after_proofs = [row['proofs'] for row in outcomes]
    accepted = (all(row['accepted'] for row in before_proofs + after_proofs if row['method'] == 'explicit_congruence')
                and all(not row['accepted'] and 'Invalid configuration option `uf`' in (row['diagnostic'] or '')
                        for row in before_proofs if row['method'] == 'uf_bv')
                and all(row['accepted'] for row in after_proofs[:-1] if row['method'] == 'uf_bv')
                and not after_proofs[-1]['accepted'] and after_proofs[-1]['reports_counterexample'])
    return {'experiment': EXPERIMENT, 'source': FEATURE,
            'registered_outcome': 'matched' if accepted else 'not-matched', 'independent_reference': reference,
            'runtimes': outcomes, 'retained_asset': 'Reusable +uf proof pattern on both arities' if accepted else None,
            'causal_invention_improvement': 'unproven', 'economic_effect': 'unproven'}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True, type=Path)
    parser.add_argument('--after', required=True, type=Path)
    args = parser.parse_args()
    report = compare(args.before, args.after)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['registered_outcome'] == 'matched' else 1


if __name__ == '__main__':
    raise SystemExit(main())
