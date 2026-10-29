"""Verify an actually downloaded release ZIP without checkout/history fallbacks."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import zipfile

FREEZE = '6606628dcd020dc735219186ba678ec0f4bb3d906ff689f5b896966406af4b40'
PREFIX = 'AGI_ALPHA_Mechanism_Completion/'
PHASE_MANIFEST_SHA256 = '28ef21aa066c78f77e856e57a65bf8803a629ec4c3124bf9986f5a07e0e8a1e7'
V2_FREEZE_SHA256 = '68b0ae0b82738315536edcf3dfde7276d6adb44e0ffa2a9a24ed18fedeb88306'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def execute(command, cwd, log, timeout=180):
    started = time.monotonic()
    with log.open('xb') as stream:
        result = subprocess.run(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout,
            env={'PATH': os.defpath, 'LANG': 'C.UTF-8', 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1', 'PYTHONNOUSERSITE': '1'})
    receipt = {'command': [str(x) for x in command], 'returncode': result.returncode, 'wall_seconds': time.monotonic()-started,
               'log': log.name, 'log_sha256': sha(log.read_bytes())}
    write(log.with_suffix('.json'), receipt)
    return receipt


def verify(archive, expected_sha, output, asset_metadata, phase_replay=False):
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    report = {'schema': 'agi-alpha-cycle005-published-download-verification/v1', 'status': 'STARTED',
              'asset_metadata': asset_metadata, 'archive_path': str(archive), 'python': sys.version, 'platform': platform.platform(),
              'expected_github_digest': 'sha256:' + expected_sha, 'source_freeze_sha256': FREEZE, 'checks': {}}
    write(output / 'STARTED.json', report)
    try:
        raw = archive.read_bytes()
        report['actual_archive_sha256'] = sha(raw)
        report['archive_bytes'] = len(raw)
        if report['actual_archive_sha256'] != expected_sha:
            raise ValueError('PUBLIC_ASSET_DIGEST_MISMATCH')
        with zipfile.ZipFile(archive) as bundle:
            entries = bundle.infolist()
            if len(entries) > 10001 or sum(item.file_size for item in entries) > 250*1024**2:
                raise ValueError('ARCHIVE_BOUND')
            names = [item.filename for item in entries]
            if len(names) != len(set(names)):
                raise ValueError('DUPLICATE_ARCHIVE_ENTRY')
            data = {}
            for item in entries:
                if not item.filename.startswith(PREFIX) or item.is_dir() or ((item.external_attr >> 16) & 0o170000) == 0o120000:
                    raise ValueError('ARCHIVE_ENTRY_SCOPE')
                name = item.filename[len(PREFIX):]
                relative = Path(name)
                if relative.is_absolute() or '..' in relative.parts or '.git' in relative.parts or not relative.parts or '\\' in name:
                    raise ValueError('ARCHIVE_PATH_SCOPE')
                data[name] = bundle.read(item)
        manifest = json.loads(data.pop('ARCHIVE_MANIFEST.json'))
        if manifest.get('schema') != 'lab/self-contained-source-archive/v2' or set(data) != set(manifest['files']) or any(sha(raw) != manifest['files'][name] for name, raw in data.items()):
            raise ValueError('INDEPENDENT_ARCHIVE_MANIFEST_MISMATCH')
        if sha(data['campaign/cycle-005/FREEZE.json']) != FREEZE:
            raise ValueError('TRUSTED_FREEZE_CHANGED')
        frozen = json.loads(data['campaign/cycle-005/FREEZE.json'])
        if len(frozen['sources']) != 50 or any(sha(data[name]) != expected for name, expected in frozen['sources'].items()):
            raise ValueError('TRUSTED_FIFTY_SOURCE_SET_CHANGED')
        report['checks']['independent_manifest'] = {'passed': True, 'files': len(data)}
        report['checks']['trusted_fifty_builder_sources'] = {'passed': True, 'files': 50}
        stage = Path(tempfile.mkdtemp(prefix='agi-alpha-public-download-005-'))
        source = stage / 'source'; source.mkdir()
        for name, raw in data.items():
            target = source / name; target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(raw)
        ancestors = [source, *source.parents]
        if any((path / '.git').exists() for path in ancestors):
            raise ValueError('GIT_HISTORY_PRESENT_IN_EXTRACTION_ANCESTRY')
        report['isolated_stage'] = str(stage)
        report['checks']['no_git_or_ancestor_history'] = {'passed': True, 'checked_ancestors': [str(x) for x in ancestors]}
        phase_root = source / 'inventions/phase_codes'
        if sha((phase_root / 'DISTRIBUTION_SHA256.json').read_bytes()) != PHASE_MANIFEST_SHA256:
            raise ValueError('OWNER_EXTERNAL_MANIFEST_PIN_CHANGED')
        if sha((phase_root / 'verification/runtime_v2/FREEZE.json').read_bytes()) != V2_FREEZE_SHA256:
            raise ValueError('OWNER_EXTERNAL_V2_FREEZE_PIN_CHANGED')
        phase_manifest = json.loads((phase_root / 'DISTRIBUTION_SHA256.json').read_text())
        bad_phase = [name for name, expected in phase_manifest.items() if sha((phase_root / name).read_bytes()) != expected]
        if len(phase_manifest) != 39 or bad_phase:
            raise ValueError('OWNER_PHASE_DISTRIBUTION_CHANGED ' + repr(bad_phase))
        v2 = json.loads((phase_root / 'verification/runtime_v2/FREEZE.json').read_text())
        v2_bad = [name for name, expected in v2['files'].items() if sha((phase_root / 'verification/runtime_v2' / name).read_bytes()) != expected]
        if len(v2['files']) != 2 or v2_bad:
            raise ValueError('OWNER_RUNTIME_V2_FREEZE_CHANGED')
        report['checks']['owner_39_phase_sources_and_v2_pins'] = {'passed': True, 'phase_files': 39, 'v2_files': 2,
            'runtime_v2_sha256': sha((phase_root / 'runtime_v2.py').read_bytes()), 'broad_certifier_sha256': sha((phase_root / 'verification/certify.py').read_bytes())}
        probe = 'import pathlib,flywheel,mechanisms;r=pathlib.Path.cwd().resolve();assert pathlib.Path(flywheel.__file__).resolve().is_relative_to(r);assert pathlib.Path(mechanisms.__file__).resolve().is_relative_to(r);print(flywheel.__file__);print(mechanisms.__file__)'
        steps = [
            ('extracted-module-origin', [sys.executable, '-c', probe], source),
            ('unit', [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'], source),
            ('verifier', [sys.executable, '-m', 'unittest', 'discover', '-s', 'verification', '-v'], source),
            ('documented-completion', [sys.executable, '-I', str(source / 'run_completion.py'), '--output', str(stage / 'documented-completion')], source),
            ('P1-original-and-repaired', [sys.executable, str(source / 'verification/cycle005_p1_regression.py'), '--root', str(source), '--output', str(stage / 'P1-regression')], source),
            ('original-edition-materialization', [sys.executable, '-I', str(source / 'flywheel/legacy.py'), '--root', str(source), '--output', str(stage / 'edition001')], source),
            ('original-edition-check', [sys.executable, '-I', str(stage / 'edition001/verification/check_edition.py')], stage / 'edition001'),
            ('original-edition-replay', [sys.executable, '-I', str(stage / 'edition001/reproduce.py'), '--output', str(stage / 'edition001-replay')], stage / 'edition001'),
            ('old22-materialization', [sys.executable, '-I', str(source / 'flywheel/archive_v2.py'), 'cycle004', str(source), str(stage / 'edition004')], source),
            ('old22-replay', [sys.executable, '-I', str(stage / 'edition004/run_cycle.py'), '--output', str(stage / 'edition004-replay')], stage / 'edition004')]
        for name, command, cwd in steps:
            receipt = execute(command, cwd, output / (name + '.log'))
            report['checks'][name] = dict(receipt, passed=receipt['returncode'] == 0)
            write(output / (name + '-receipt.json'), report['checks'][name])
            if receipt['returncode']:
                raise ValueError('DOWNLOADED_ARTIFACT_STEP_FAILED ' + name)
        completion = json.loads((stage / 'documented-completion/REPORT.json').read_text())
        marker = json.loads((stage / 'documented-completion/COMPLETE.json').read_text())
        if marker['report_sha256'] != sha((stage / 'documented-completion/REPORT.json').read_bytes()) or completion['freeze_sha256'] != FREEZE:
            raise ValueError('DOWNLOADED_COMPLETION_IDENTITY_MISMATCH')
        write(output / 'DOWNLOADED_COMPLETION_REPORT.json', completion)
        old_freeze = json.loads((stage / 'edition004/campaign/cycle-004/FREEZE.json').read_text())
        if len(old_freeze['sources']) != 22 or any(sha((stage / 'edition004' / name).read_bytes()) != expected for name, expected in old_freeze['sources'].items()):
            raise ValueError('OLD_TWENTYTWO_SOURCE_IDENTITIES_CHANGED')
        report['checks']['old_twentytwo_identity'] = {'passed': True, 'files': 22}
        if phase_replay:
            receipt = execute([sys.executable, str(phase_root / 'reproduce.py'), '--output', str(stage / 'phase-code-replay')], source, output / 'phase-owner-replay.log')
            report['checks']['phase_owner_replay'] = dict(receipt, passed=receipt['returncode'] == 0)
            if receipt['returncode']:
                raise ValueError('DOWNLOADED_OWNER_PHASE_REPLAY_FAILED')
        else:
            report['phase_replay_scope'] = 'Not repeated here; exact 39 owner files and v2 pins verified. Source-matched clean-release CI runs the full owner replay separately.'
        changed = [name for name, expected in manifest['files'].items() if sha((source / name).read_bytes()) != expected]
        if changed:
            raise ValueError('EXTRACTED_SOURCE_MUTATED ' + repr(changed))
        report['checks']['all_original_payloads_unchanged_after_execution'] = {'passed': True, 'files': len(data)}
        report['status'] = 'PASS_PUBLISHED_ASSET_IN_SCOPE'
        report['passed'] = True
    except BaseException as error:
        report['status'] = 'FAILED_OR_INTERRUPTED'
        report['passed'] = False
        report['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        report['wall_seconds'] = time.monotonic()-started
        report['verifier_source_sha256'] = sha(Path(__file__).read_bytes())
        report['limits'] = ['Exact downloaded asset, installed Python/dependencies and tested Linux host only.', 'No fresh scientific, economic or commercial claim; all source-case exposures preserved.']
        write(output / 'REPORT.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase-replay', action='store_true')
    args = parser.parse_args()
    result = verify(args.archive, args.sha256, args.output, json.loads(args.metadata.read_text()), args.phase_replay)
    print(json.dumps({'passed': result['passed'], 'status': result['status'], 'wall_seconds': result['wall_seconds']}))
