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

EXPIRY_EXPERIMENT = 'lean-4.36-enrollment-expiry-decoder-equivalence'
EXPIRY_PRELUDE = '''def octets (x : BitVec 32) :=
  (((x >>> 24) &&& 255) <<< 24) ||| (((x >>> 16) &&& 255) <<< 16) |||
  (((x >>> 8) &&& 255) <<< 8) ||| (x &&& 255)
def halves (x : BitVec 32) := ((x >>> 16) <<< 16) ||| (x &&& 65535)
'''
EXPIRY_ONE = '''(policy : BitVec 32 → Bool) (x : BitVec 32) :
    policy (octets x) = policy (halves x)'''
EXPIRY_TWO = '''(policy : BitVec 32 → BitVec 8 → Bool) (x : BitVec 32) (kind : BitVec 8) :
    policy (octets x) (kind ^^^ 0) = policy (halves x) (kind &&& 255)'''
EXPIRY_CASES = (
    ('opaque_policy', EXPIRY_ONE, 'exact congrArg policy (by bv_decide)'),
    ('opaque_policy_with_kind', EXPIRY_TWO, '''have expiry : octets x = halves x := by bv_decide
  have code : kind ^^^ 0 = kind &&& 255 := by bv_decide
  rw [expiry, code]'''),
)
EXPIRY_WRONG = EXPIRY_TWO.replace('(halves x)', '(halves x ^^^ 1)')


def expiry_reference():
    """Cross-check independent byte and halfword decoders with boundary and seeded words."""
    from random import Random

    rng = Random(4360)
    words = list(range(65536)) + [0, 1, 255, 256, 65535, 65536, 2**31, 2**32 - 1]
    words.extend(rng.getrandbits(32) for _ in range(4096))
    for word in words:
        encoded = word.to_bytes(4, 'big')
        by_byte = sum(byte * 256**(3 - index) for index, byte in enumerate(encoded))
        by_half = int.from_bytes(encoded[:2], 'big') * 65536 + int.from_bytes(encoded[2:], 'big')
        if by_byte != word or by_half != word:
            raise ValueError('Big-endian decoding cross-check failed')
    return {'checked_words': len(words), 'seed': 4360,
            'invalid_case_witness': {'word': 0, 'kind': 0, 'left_result': False, 'right_result': True},
            'witness_oracle': 'Return whether the expiry word has its least significant bit set.'}


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


def check(binary, folder, case, statement, tactic, method, prelude=''):
    payload = (f'import Std.Tactic.BVDecide\nset_option maxHeartbeats 200000\nset_option warningAsError true\n'
               f'{prelude}theorem frontier_check {statement} := by\n  {tactic}\n#print axioms frontier_check\n')
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


def compare(before, after, expiry_word=False):
    cases = EXPIRY_CASES if expiry_word else CASES
    wrong = EXPIRY_WRONG if expiry_word else WRONG
    prelude = EXPIRY_PRELUDE if expiry_word else ''
    reference = expiry_reference() if expiry_word else independent_reference()
    outcomes = []
    with TemporaryDirectory(prefix='frontier-lean-delta-') as working:
        folder = Path(working)
        for version, binary in zip(VERSIONS, (before, after), strict=True):
            binary = binary.resolve(strict=True)
            reported = subprocess_result(binary, '--version')
            if reported.returncode or not re.search(r'\bversion ' + re.escape(version) + ',', reported.stdout):
                raise ValueError('Use the registered Lean release ' + version)
            proofs = []
            for name, statement, manual in cases:
                for method, tactic in [('explicit_congruence', manual), ('grind', 'grind'),
                                       ('default_bv', 'bv_decide'), ('uf_bv', 'bv_decide +uf')]:
                    if expiry_word:
                        tactic = 'unfold octets halves\n  ' + tactic
                        if method == 'explicit_congruence' and name == 'opaque_policy_with_kind':
                            tactic = manual.replace('by bv_decide\n', 'by unfold octets halves; bv_decide\n', 1)
                    proofs.append(check(binary, folder, name, statement, tactic, method, prelude))
            if version == VERSIONS[-1]:
                tactic = 'unfold octets halves\n  bv_decide +uf' if expiry_word else 'bv_decide +uf'
                proofs.append(check(binary, folder, 'invalid_two_arguments', wrong, tactic, 'uf_bv', prelude))
            outcomes.append({'version': reported.stdout.strip(), 'proofs': proofs})
    before_proofs, after_proofs = [row['proofs'] for row in outcomes]
    accepted = (all(row['accepted'] for row in before_proofs + after_proofs if row['method'] == 'explicit_congruence')
                and all(not row['accepted'] and 'Invalid configuration option `uf`' in (row['diagnostic'] or '')
                        for row in before_proofs if row['method'] == 'uf_bv')
                and all(row['accepted'] for row in after_proofs[:-1] if row['method'] == 'uf_bv')
                and not after_proofs[-1]['accepted'] and after_proofs[-1]['reports_counterexample'])
    return {'experiment': EXPIRY_EXPERIMENT if expiry_word else EXPERIMENT, 'source': FEATURE,
            'registered_outcome': 'matched' if accepted else 'not-matched', 'independent_reference': reference,
            'runtimes': outcomes, 'retained_asset': 'Reusable +uf proof pattern on both arities' if accepted else None,
            'causal_invention_improvement': 'unproven', 'economic_effect': 'unproven'}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--before', required=True, type=Path)
    parser.add_argument('--after', required=True, type=Path)
    parser.add_argument('--expiry-word', action='store_true', help='Compare decoders for the 32-bit enrollment expiry word')
    args = parser.parse_args()
    report = compare(args.before, args.after, args.expiry_word)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report['registered_outcome'] == 'matched' else 1


if __name__ == '__main__':
    raise SystemExit(main())
