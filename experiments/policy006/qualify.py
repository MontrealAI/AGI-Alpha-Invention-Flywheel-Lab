import argparse
import hashlib
import json
from pathlib import Path
import resource
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from flywheel import sandbox
from mechanisms import policy006 as policy


def run(source, output):
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    path = ROOT / 'mechanisms/policy006.py'
    source_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    proposals = policy.generate(20261029, 24, omega_source_path=source)
    native = sys.modules['_agi_alpha_omega006_pinned']
    features = dict(zip(policy.FEATURES, (.37, .2, .6, .4, .1, .8)))
    action = {'id': 'known-readonly-action', 'kind': 'measure', 'features': features,
              'feature_provenance': {name: 'observed' for name in policy.FEATURES},
              'source_identities': ['c' * 64], 'cost_units': 1}
    observation = {'actions': [action], 'evidence_sha256': 'd' * 64}
    budget = {'steps': 1, 'cost_units': 1, 'kinds': {kind: 1 for kind in policy.KINDS}}
    spent = {'steps': 0, 'cost_units': 0, 'kinds': {kind: 0 for kind in policy.KINDS}}
    checks = []
    for program in proposals['programs']:
        receipt = sandbox.run(path, 'interpret', {'policy': program, 'observation': observation,
                              'budget': budget, 'spent': spent}, source_sha)
        expected = native.evaluate_expr(program['priority'], features)
        if receipt['state'] != 'COMPLETE' or receipt['worker']['result']['ranked'][0]['score'] != expected:
            raise ValueError('NATIVE_CONFINED_PARITY_FAILURE')
        checks.append({'policy': program, 'expected_omega_score': expected, 'confined_receipt': receipt})
    unit = subprocess.run([sys.executable, '-m', 'unittest', 'tests.test_policy006', '-v'], cwd=ROOT,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30)
    (output / 'UNIT.txt').write_text(unit.stdout)
    if unit.returncode:
        raise ValueError('UNIT_FAILURE')
    after = resource.getrusage(resource.RUSAGE_SELF)
    child_after = resource.getrusage(resource.RUSAGE_CHILDREN)
    report = {'schema': 'agi-alpha-cycle006-policy-qualification/v1',
              'policy_source_sha256': source_sha, 'omega_programs_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'omega_archive_sha256': 'c0df2ac39ddcb32de672db93d05df77b8d8f683966cb92469ab00bf2060284a1',
              'native_adapter': 'Original Program.create/mutate and evaluate_expr execute after exact source identity check. Native domain engine.search is not run for this different task.',
              'public_distribution': 'Original programs.py is locally recovered, not copied into this public package. Optional source-pinned adapter refuses a missing/changed original; independent deterministic generation remains available.',
              'generated': proposals, 'parity_checks': checks, 'unit_returncode': unit.returncode,
              'resources': {'wall_seconds': time.monotonic() - started,
                            'process_cpu_seconds': after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                            'child_cpu_seconds': child_after.ru_utime + child_after.ru_stime - children.ru_utime - children.ru_stime,
                            'external_model_calls': 0, 'complete_monetary_cost': None},
              'claims': {'engineering': 'Six tests and24 native-generated priority compositions execute as JSON in seccomp and agree with original Omega expression evaluation.',
                         'scientific_advantage': 'UNRUN', 'discovery_learning_advantage': 'UNRUN', 'complete_cost_advantage': 'UNKNOWN'},
              'limits': ['Features/primitives, broker and mutation/adaptor are developer-authored; compositions generated at runtime.',
                         'Feature provenance declarations are not authenticated semantic truth; the external experiment must bind them to real observations/development models.',
                         'These engineering tests are not the consequential task or protected scientific confirmation.']}
    with (output / 'QUALIFICATION.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--omega-source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.omega_source, args.output)['resources']))
