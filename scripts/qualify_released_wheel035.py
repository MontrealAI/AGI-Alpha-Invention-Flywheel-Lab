"""Read-only smoke of the wheel shipped in the actual canonical source inventory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from connected_enterprise.runner import identity


def qualify(output, expected_source):
    output = Path(output)
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise ValueError('FRESH_RECEIPT_REQUIRED')
    start = time.monotonic()
    before = os.times()
    receipt = {'schema': 'agi-alpha/released-wheel035/v1', 'accepted': False,
               'scope': 'EXTRACTED_SOURCE_READ_ONLY_UTILITY_SMOKE_NOT_COMMERCE',
               'funding_authority': False, 'expected_source_sha256': expected_source,
               'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        receipt['source_sha256'] = identity(ROOT)['sha256']
        if receipt['source_sha256'] != expected_source:
            raise ValueError('RELEASED_WHEEL_SOURCE_CHANGED')
        with tempfile.TemporaryDirectory(prefix='wheel-utility-') as temp:
            target = Path(temp) / 'precision'
            # -I prevents ambient PYTHONPATH/user-site dependencies; cwd is exact extracted source.
            result = subprocess.run([sys.executable, '-I', '-c',
                "import sys;sys.path.insert(0,'.');from flywheel_wheel.__main__ import main;raise SystemExit(main(sys.argv[1:]))",
                'precision', '--output', str(target)], cwd=ROOT, capture_output=True, timeout=60)
            if result.returncode:
                raise ValueError('RELEASED_WHEEL_EXECUTION_FAILED')
            import xml.etree.ElementTree as ET
            tree = ET.parse(target / 'wheel.svg')
            if len(tree.findall('.//{http://www.w3.org/2000/svg}textPath')) != 48:
                raise ValueError('RELEASED_WHEEL_STAGE_COUNT_CHANGED')
            snapshot = json.loads((target / 'snapshot.json').read_text())
            if snapshot.get('funding_authority') is not False:
                raise ValueError('RELEASED_WHEEL_AUTHORITY_CHANGED')
            receipt['stage_count'] = 48
            receipt['output_sha256'] = {name: hashlib.sha256((target / name).read_bytes()).hexdigest()
                                       for name in ('wheel.svg', 'snapshot.json', 'index.html')}
        if identity(ROOT)['sha256'] != expected_source:
            raise ValueError('RELEASED_WHEEL_SOURCE_CHANGED')
        receipt['accepted'] = True
    except Exception as exc:
        # Compact category only: no account paths, subprocess logs or private outputs.
        receipt['failure_type'] = type(exc).__name__
        receipt['lesson'] = 'Utility or source qualification failed; do not claim released wheel usability.'
    finally:
        after = os.times()
        receipt['resources'] = {'wall_seconds': time.monotonic() - start,
            'process_cpu_seconds': after.user + after.system - before.user - before.system,
            'waited_child_cpu_seconds': after.children_user + after.children_system - before.children_user - before.children_system,
            'scope': 'Utility smoke only; separate from native six-command operation. Host/model billing unavailable.'}
        with output.open('x') as stream:
            json.dump(receipt, stream, sort_keys=True, indent=2)
            stream.write('\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--expected-source', required=True)
    args = parser.parse_args()
    raise SystemExit(0 if qualify(args.output, args.expected_source)['accepted'] else 1)
