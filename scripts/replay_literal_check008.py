"""Replay the unchanged literal witness in a fresh source-matched layout."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    'compile_petab_forcing.py': 'd012c3ba045b4abb061f1c313e1a02139c4f47f6272e3bc0fc077b6fcc9a5cf5',
    'gauge_probe.py': 'baf786e8a784b62072372c5aafd439d1b004ce9e5a2cd3cf98860adad1612c81',
    'check_literals.py': '92ae97359df9b019b427d775143049e8f408677e4f4d55c3033c36420f66db57',
}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    source = ROOT / 'research/observability008'
    for name, expected in PINS.items():
        if hashlib.sha256((source / name).read_bytes()).hexdigest() != expected:
            raise ValueError('FROZEN_LITERAL_SOURCE_CHANGED ' + name)
    a.output.mkdir(parents=True, exist_ok=False)
    for name in PINS:
        shutil.copyfile(source / name, a.output / name)
    shutil.copytree(source / 'boehm/source', a.output / 'boehm_source')
    result = subprocess.run([sys.executable, str((a.output / 'check_literals.py').resolve())],
                            capture_output=True, text=True, timeout=30,
                            env={'PATH': os.defpath, 'LANG': 'C.UTF-8', 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1'})
    (a.output / 'stdout.log').write_text(result.stdout)
    (a.output / 'stderr.log').write_text(result.stderr)
    if result.returncode:
        raise RuntimeError('LITERAL_REGRESSION_FAILED ' + result.stderr[-1000:])
    report = json.loads(result.stdout)
    if report.get('passed') is not True:
        raise ValueError('LITERAL_WITNESS_NOT_QUALIFIED')
    (a.output / 'RESULT.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
