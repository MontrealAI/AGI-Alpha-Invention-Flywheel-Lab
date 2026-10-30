import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

from experiments.resource006_v3 import run

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def sources(expected):
    path = ROOT/'campaign/cycle-007/REPRODUCTION_FREEZE.json'
    if sha(path) != expected:
        raise ValueError('EXTERNAL_FREEZE_IDENTITY_MISMATCH')
    freeze = json.loads(path.read_text())
    for name, digest in freeze['files'].items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('SOURCE_PATH_SCOPE')
        current = ROOT
        for part in relative.parts:
            current = current/part
            if current.is_symlink():
                raise ValueError('SOURCE_SYMLINK')
        if not current.is_file() or sha(current) != digest:
            raise ValueError('FROZEN_SOURCE_MISMATCH:'+name)
    return freeze


def main(output, expected_freeze_sha256, with_compatibility, chemistry_tools_dir=None, download_tools=False):
    freeze = sources(expected_freeze_sha256)
    output = output.absolute()
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise FileExistsError(output)
    output.mkdir(parents=True)
    wall, cpu = time.monotonic(), time.process_time()
    write(output/'STARTED.json', {'schema': 'agi-alpha/reproduction007/v1', 'source_freeze_sha256': expected_freeze_sha256,
                                 'claim_mode': 'Exposed engineering reproduction. No protected confirmation, new scientific result or error-budget reset.',
                                 'source_file_count': len(freeze['files'])})
    receipts = []
    python = str(Path(sys.executable).absolute())

    def phase(name, arguments, cpu_cap=60, wall_cap=90):
        envelope = run([python, *arguments], output/name, output/'RESOURCE_LEDGER.json', name,
                      {'wall_seconds': wall_cap, 'cpu_seconds': cpu_cap, 'memory_bytes': 2*1024**3,
                       'output_bytes': 8*1024**2, 'storage_bytes': 128*1024**2}, cwd=ROOT)
        receipt = envelope['receipt']
        receipts.append({'phase': name, 'receipt': receipt})
        write(output/(name+'-binding.json'), {'receipt_sha256': sha(output/name/'RECEIPT.json')})
        if receipt['state'] != 'complete':
            raise RuntimeError('INCOMPLETE_PHASE:'+name)

    phase('unit-tests', ['-m', 'unittest', 'tests.test_lifetime007', 'tests.test_commerce007', 'verification.test_denovo007_protocol_preflight', '-v'])
    phase('actual-retention-transfer', ['-m', 'experiments.lifetime007', '--output', str(output/'actual-retention-transfer/artifacts')])
    phase('exposed-temporal-verifier', ['verification/cycle007_temporal.py', '--root', str(ROOT),
        '--worker', str(ROOT/'evidence/cycle-007/temporal-verification/EXPOSED_PROTECTED_CASES.py'),
        '--protocol', str(ROOT/'verification/cycle007_temporal_protocol.json'), '--output', str(output/'exposed-temporal-verifier/artifacts')])
    phase('actual-asgi-baseline', ['-m', 'experiments.temporal_probe007', '--output', str(output/'actual-asgi-baseline/artifacts')])
    phase('constructed-asgi', ['-m', 'experiments.temporal_construct007', '--output', str(output/'constructed-asgi/artifacts')])
    data = ROOT/'evidence/cycle-007/massbank-probe/development-dataset'
    phase('actual-spectra-baseline', ['-m', 'experiments.massbank_entropy007', '--data', str(data), '--output', str(output/'actual-spectra-baseline/artifacts.json')])
    phase('independent-spectra-replay', ['verification/cycle007_massbank_baseline.py', '--data', str(data),
        '--baseline', str(output/'actual-spectra-baseline/artifacts.json'), '--output', str(output/'independent-spectra-replay/artifacts.json')])
    contract = ROOT/'campaign/cycle-007/ECONOMICS_CONTRACT.json'
    acceptance = ROOT/'evidence/cycle-007/verification/REPORT.json'
    phase('conditional-exchange', ['-m', 'experiments.commerce007', '--artifact', str(ROOT/'evidence/cycle-007/verification/ACCEPTED_DELIVERY.json'),
        '--acceptance', str(acceptance), '--contract', str(contract), '--output', str(output/'conditional-exchange/artifacts'),
        '--expected-contract-sha256', sha(contract), '--expected-acceptance-sha256', sha(acceptance)])
    setup_receipt = None
    if with_compatibility:
        setup_command = [python, 'verification/cycle007_setup_compatibility.py', '--directory', str(output/'compatibility-envs'), '--output', str(output/'compatibility-setup')]
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.monotonic()
        with (output/'compatibility-setup.log').open('xb') as stream:
            completed = subprocess.run(setup_command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=500, env=dict(os.environ))
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        setup_receipt = {'command': setup_command, 'returncode': completed.returncode, 'wall_seconds': time.monotonic()-start,
                         'waited_child_cpu_seconds': after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                         'scope': 'Free dependency installation with inherited approved network/proxy environment; separately timed trusted setup, not an effect sandbox.'}
        write(output/'compatibility-setup-receipt.json', setup_receipt)
        if completed.returncode:
            raise RuntimeError('FRESH_ENVIRONMENT_SETUP_FAILED')
        phase('exposed-compatibility-verifier', ['verification/cycle007_compatibility.py',
            '--source', str(ROOT/'evidence/cycle-007/dependency-probe/source'),
            '--manifest', str(ROOT/'evidence/cycle-007/dependency-probe/source_manifest.json'),
            '--candidate', str(ROOT/'campaign/cycle-007/COMPATIBILITY_TARGET.json'),
            '--baseline-python', str(output/'compatibility-envs/baseline/bin/python'),
            '--target-python', str(output/'compatibility-envs/target/bin/python'),
            '--worker', str(ROOT/'evidence/cycle-007/verification/EXPOSED_PROTECTED_CASES.py'),
            '--protocol', str(ROOT/'verification/cycle007_compatibility_protocol_v3.json'), '--output', str(output/'exposed-compatibility-verifier/artifacts')], cpu_cap=120, wall_cap=150)
    chemical_receipt = None
    if chemistry_tools_dir is not None:
        command = [python, 'experiments/denovo007.py', '--tools-dir', str(chemistry_tools_dir.absolute()), '--output', str(output/'chemical-baseline')]
        if download_tools:
            command.append('--download-tools')
        start = time.monotonic()
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        with (output/'chemical-baseline.log').open('xb') as stream:
            completed = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=650, env=dict(os.environ))
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        chemical_receipt = {'command': command, 'returncode': completed.returncode, 'wall_seconds': time.monotonic()-start,
                            'waited_child_cpu_seconds': after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                            'scope': 'Pinned free baseline tools; helper enforces offline Java process limits and aggregate CPU allowance. Reproduction of exposed chemistry inputs, not new confirmation.'}
        write(output/'chemical-baseline-receipt.json', chemical_receipt)
        if completed.returncode:
            raise RuntimeError('CHEMICAL_BASELINE_INCOMPLETE')
    sources(expected_freeze_sha256)
    report = {'schema': 'agi-alpha/reproduction-report007/v1', 'completed_phases': receipts, 'compatibility_setup': setup_receipt,
              'fresh_compatibility_replayed': with_compatibility, 'chemical_java_baseline_replayed': chemical_receipt is not None,
              'chemical_baseline_receipt': chemical_receipt,
              'chemical_java_baseline_continuation': 'Use the separately source-bound de-novo baseline command and pinned free tools; this driver never silently counts an unrun phase.',
              'wall_seconds': time.monotonic()-wall, 'self_cpu_seconds': time.process_time()-cpu,
              'reproduction_complete_in_stated_scope': True, 'enabling_invention_demonstrated': False,
              'commercially_qualified_earned_funds': 0, 'full_campaign_complete': False,
              'limitations': ['Every previously protected case is now exposed.', 'Core and chemistry baselines are supporting evidence; no flagship is admitted by this replay.',
                              'Agent inference and complete lifecycle monetary costs remain unknown.', 'Original commerce qualifies canonical JSON content; the original raw-byte claim remains false.']}
    write(output/'REPORT.json', report)
    write(output/'COMPLETE.json', {'report_sha256': sha(output/'REPORT.json'), 'source_freeze_sha256': expected_freeze_sha256})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--expected-freeze-sha256', required=True)
    parser.add_argument('--with-compatibility', action='store_true')
    parser.add_argument('--chemistry-tools-dir', type=Path)
    parser.add_argument('--download-tools', action='store_true')
    args = parser.parse_args()
    main(args.output, args.expected_freeze_sha256, args.with_compatibility, args.chemistry_tools_dir, args.download_tools)
