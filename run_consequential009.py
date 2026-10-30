"""Replay the actual finite circuit construction, checking, retrieval and conditional exchange."""
import signal

def _stop(signum, frame): raise KeyboardInterrupt('CONSEQUENTIAL009_SIGNAL_' + str(signum))
signal.signal(signal.SIGTERM, _stop)

import argparse, hashlib, json, sys, time
from pathlib import Path
from experiments.resource006_v3 import run as bounded_run

ROOT = Path(__file__).resolve().parent

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text())
def write(path, value):
    with path.open('x') as stream: json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False); stream.write('\n')

def run(output):
    started = time.monotonic()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    freeze_path = ROOT / 'campaign/consequential-009/SOURCE_FREEZE.json'
    freeze = read(freeze_path)
    for name, expected in freeze['files'].items():
        if sha(ROOT / name) != expected: raise ValueError('FROZEN_SOURCE_MISMATCH ' + name)
    write(output / 'SOURCE_FREEZE.json', freeze)
    write(output / 'STARTED.json', {'scope': 'Exposed finite ideal-circuit model replay; no new scientific or market samples',
        'source_freeze_sha256': sha(freeze_path), 'inference_calls': 0, 'complete_cost': None})
    ledger = output / 'resource-ledger.json'
    receipts = []
    def execute(name, command):
        result = bounded_run([sys.executable, *map(str, command)], output / name, ledger, name,
            {'wall_seconds': 120, 'cpu_seconds': 60, 'memory_bytes': 1073741824,
             'output_bytes': 16777216, 'storage_bytes': 67108864}, ROOT)
        receipts.append({'name': name, 'receipt_sha256': result['receipt_sha256'], 'receipt': result['receipt']})
        if result['receipt']['state'] != 'complete': raise RuntimeError('STEP_FAILED ' + name)
    try:
        protocol = ROOT / 'research/consequential009/analog/PROTOCOL.json'
        execute('producer', ['-m', 'inventions.consequential009.experiment', '--protocol', protocol,
                              '--output', output / 'producer/artifacts'])
        directory = output / 'producer/artifacts'
        artifact, receipt = directory / 'REPORT.json', output / 'verifier/ACCEPTANCE.json'
        verifier = ROOT / 'verification/consequential009/cohort_check.py'
        execute('verifier', [verifier, '--root', ROOT, '--directory', directory,
                            '--expected-protocol', sha(protocol), '--expected-artifact', sha(artifact), '--output', receipt])
        execute('retention', ['-m', 'experiments.consequential009_retention', '--primary-directory', directory,
            '--receipt', receipt, '--expected-receipt-sha256', sha(receipt), '--output', output / 'retention/artifacts'])
        policy = ROOT / 'campaign/consequential-009/COMMERCIAL_POLICY.json'
        paths = {'artifact': artifact, 'receipt': receipt, 'protocol': protocol,
                 'candidate': ROOT / 'inventions/consequential009/circuit.py', 'verifier': verifier}
        command = ['-m', 'experiments.consequential009_commerce']
        for name, path in paths.items(): command += ['--' + name, path, '--expected-' + name + '-sha256', sha(path)]
        execute('commerce', [*command, '--policy', policy, '--expected-policy-sha256', sha(policy),
                            '--output', output / 'commerce/artifacts'])
        inherited = read(output / 'retention/artifacts/RESULT.json')
        ref_protocol = ROOT / 'research/consequential009/analog/REFERENCE_PROTOCOL.json'
        execute('reference', ['-m', 'experiments.consequential009_reference_retained',
            '--memory', output / 'retention/artifacts/memory', '--expected-record-sha256', inherited['record_sha256'],
            '--protocol', ref_protocol, '--output', output / 'reference/work'])
        ref_directory = output / 'reference/work/artifacts'
        execute('reference-verifier', [ROOT / 'verification/consequential009/reference_check.py',
            '--root', ROOT, '--directory', ref_directory, '--expected-protocol', sha(ref_protocol),
            '--expected-artifact', sha(ref_directory / 'REPORT.json'),
            '--output', output / 'reference-verifier/ACCEPTANCE.json'])
        for name, expected in freeze['files'].items():
            if sha(ROOT / name) != expected: raise ValueError('SOURCE_CHANGED_DURING_REPLAY ' + name)
        produced, inherited, commercial = read(artifact), read(output / 'retention/artifacts/RESULT.json'), read(output / 'commerce/artifacts/RESULT.json')
        result = {'schema': 'agi-alpha/consequential009-complete-replay/v1', 'completed': True,
            'source_freeze_sha256': sha(freeze_path), 'primary': produced['primary'], 'successor': produced['fresh_successor'],
            'independent_acceptance': read(receipt)['accepted'], 'retention': inherited['decision'],
            'reference': read(ref_directory / 'REPORT.json'),
            'reference_independent_acceptance': read(output / 'reference-verifier/ACCEPTANCE.json')['accepted'],
            'commerce': commercial['evidence_grounded_decision'], 'resources': receipts,
            'wall_seconds': time.monotonic() - started,
            'scope': 'Downloaded-source reproducibility of finite engineering and conditional financial execution. Same cases, not new confirmation, observed orders or physical validation.',
            'mission_success': False,
            'missing': ['Scientific/technical advantage over competent full-VI methods', 'Measured physical calibration and real service utility',
                'Exact executed frontier model/token cost receipt', 'Matched competent-human task time and complete service costs',
                'Independent AGI ALPHA participation/price/volume evidence', 'Qualified unrestricted earned funding and funded successor advantage']}
        write(output / 'RESULT.json', result)
        return result
    except BaseException as error:
        write(output / 'INCOMPLETE.json', {'error_type': type(error).__name__, 'error': str(error),
            'receipts': receipts, 'wall_seconds': time.monotonic() - started, 'costs_preserved': True})
        raise

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({'completed': result['completed'], 'independent_acceptance': result['independent_acceptance'],
                      'mission_success': result['mission_success'], 'wall_seconds': result['wall_seconds']}))
