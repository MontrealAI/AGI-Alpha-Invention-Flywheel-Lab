"""Run the manifest-only package from a temporary relocated source tree."""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile
import time

BASE = Path('/workspace/scratch/e2ed86e4c5fa/frontier-first-proof/research/frontier_qec_transfer')
REVIEW = Path(__file__).resolve().parent


def identity(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def limit():
    resource.setrlimit(resource.RLIMIT_AS, (10 * 1024**3, 10 * 1024**3))


def main():
    start = time.perf_counter()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    manifest = json.loads((BASE/'SOURCE_MANIFEST.json').read_text())
    assert not manifest['provisional']
    original_manifest_hash = identity(BASE/'SOURCE_MANIFEST.json')
    retained = REVIEW/'relocated_replay'
    assert not retained.exists(), 'Preserve the previous replay receipt; use a new name.'
    environment = dict(os.environ)
    environment.pop('PYTHONPATH', None)
    environment.update(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1',
                       MKL_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
    with tempfile.TemporaryDirectory(prefix='independent-qec-relocated-') as temporary:
        outer = Path(temporary)
        package = outer/'source package'
        package.mkdir()
        for name, expected in manifest['files'].items():
            source = BASE/name
            assert identity(source) == expected, name
            destination = package/name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        shutil.copy2(BASE/'SOURCE_MANIFEST.json', package/'SOURCE_MANIFEST.json')
        replay = subprocess.run(
            [sys.executable, str(package/'reproduce.py'), '--all-arms',
             '--output', 'receipts'], cwd=outer, env=environment,
            text=True, capture_output=True, preexec_fn=limit)
        (REVIEW/'relocated_stdout.txt').write_text(replay.stdout)
        (REVIEW/'relocated_stderr.txt').write_text(replay.stderr)
        assert replay.returncode == 0, replay.stderr
        summary = json.loads((outer/'receipts/SUMMARY.json').read_text())
        assert summary['all_recorded_verdicts_reproduced']
        assert summary['source_files_unchanged']
        assert len(summary['arms']) == len(manifest['replays']) == 9
        assert not (package/'receipts').exists(), 'Relative output used the child source directory.'
        demo = subprocess.run(
            [sys.executable, str(package/'demo.py'), '--output',
             'receipts/operator_example.json'], cwd=outer, env=environment,
            text=True, capture_output=True, preexec_fn=limit)
        assert demo.returncode == 0, demo.stderr
        operator = json.loads((outer/'receipts/operator_example.json').read_text())
        assert operator['source_sha256']['noise_experiment.py'] == manifest['selected_successor_source_sha256']
        assert all(identity(package/name) == expected for name, expected in manifest['files'].items())
        shutil.copytree(outer/'receipts', retained)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    receipt = {
        'schema': 'frontier.qec.relocated_independent_review.v1',
        'pass': True,
        'scope': 'Linux manifest-only relocated scientific replay and selected demo; no hosted CI or reconstruction-latency claim.',
        'manifest_sha256': original_manifest_hash,
        'manifest_file_count': len(manifest['files']),
        'replay_count': len(summary['arms']),
        'copied_only_manifest_files_and_manifest': True,
        'source_path_contains_space': True,
        'cwd_outside_source_tree': True,
        'relative_output_in_callers_directory': True,
        'inherited_pythonpath_removed': True,
        'source_files_unchanged': True,
        'all_recorded_verdicts_reproduced': True,
        'selected_source_sha256': operator['source_sha256'],
        'replay_summary_sha256': identity(retained/'SUMMARY.json'),
        'operator_receipt_sha256': identity(retained/'operator_example.json'),
        'wall_seconds': time.perf_counter()-start,
        'child_cpu_seconds': after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
        'maximum_child_rss_kib': after.ru_maxrss,
        'runtime': summary['runtime'],
        'case_inputs_retained_in_review_output': False,
    }
    (REVIEW/'relocated_replay_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
