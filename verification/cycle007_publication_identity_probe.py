import argparse
import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from flywheel.archive_v2 import PREFIX, build, extract


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def probe(runner, checker, output):
    runner, checker, output = [Path(p).resolve() for p in (runner, checker, output)]
    output.mkdir(parents=True, exist_ok=False)
    copied = output/'pre-import-root'
    (copied/'experiments').mkdir(parents=True)
    (copied/'campaign/cycle-007').mkdir(parents=True)
    (copied/'run_cycle007.py').write_bytes(runner.read_bytes())
    (copied/'experiments/__init__.py').write_text('')
    (copied/'experiments/resource006_v3.py').write_text("from pathlib import Path\nPath(__file__).with_name('IMPORT_MARKER.txt').write_text('harmless verifier marker\\n')\ndef run(*a,**k):raise AssertionError('Unexpected worker execution')\n")
    (copied/'campaign/cycle-007/REPRODUCTION_FREEZE.json').write_text('{"files": {}}\n')
    command = [sys.executable, str(copied/'run_cycle007.py'), '--output', str(copied/'replay'), '--expected-freeze-sha256', '0'*64]
    result = subprocess.run(command, cwd=copied, capture_output=True, text=True, timeout=10)
    (output/'pre-import.stdout').write_text(result.stdout)
    (output/'pre-import.stderr').write_text(result.stderr)
    marker = copied/'experiments/IMPORT_MARKER.txt'
    pre_import = {'returncode': result.returncode, 'identity_refused': 'EXTERNAL_FREEZE_IDENTITY_MISMATCH' in result.stderr,
                  'repository_import_executed_before_refusal': marker.exists()}
    pre_import['passed'] = result.returncode != 0 and pre_import['identity_refused'] and not marker.exists()
    source = output/'archive-source'
    (source/'campaign/cycle-007').mkdir(parents=True)
    (source/'campaign/cycle-007/REPRODUCTION_FREEZE.json').write_text('{"files": {}}\n')
    (source/'run_cycle007.py').write_text('pass\n')
    (source/'README.txt').write_text('Original bound payload\n')
    original = output/'original.zip'
    built = build(source, original)
    alternative = output/'replacement.zip'
    with zipfile.ZipFile(original) as first, zipfile.ZipFile(alternative, 'x') as second:
        for item in first.infolist():
            second.writestr(item, first.read(item))
        second.writestr(PREFIX+'UNBOUND_MARKER.txt', 'Harmless extra absent from the original manifest\n')
    mutable = output/'mutable-input.zip'
    shutil.copyfile(original, mutable)
    loader = importlib.machinery.SourceFileLoader('cycle007_archive_layer_probe', str(checker))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    def swap_after_validation(archive, destination):
        manifest = extract(archive, destination)
        shutil.copyfile(alternative, mutable)
        return manifest
    def replay_stub(command, **kwargs):
        destination = Path(command[command.index('--output')+1])
        destination.mkdir(parents=True, exist_ok=False)
        report = destination/'REPORT.json'
        report.write_text('{"runtime_replay_stubbed_for_identity_layer_probe": true}\n')
        (destination/'COMPLETE.json').write_text(json.dumps({'report_sha256': sha(report)})+'\n')
        return SimpleNamespace(returncode=0)
    module.extract = swap_after_validation
    oldrun = module.subprocess.run
    module.subprocess.run = replay_stub
    error = None
    try:
        module.main(mutable, built['archive_sha256'], output/'archive-check', output/'tools-unused', False)
    except Exception as exc:
        error = type(exc).__name__+':'+str(exc)
    finally:
        module.subprocess.run = oldrun
    ordinary_marker = output/'archive-check/ordinary-extraction'/PREFIX.rstrip('/')/'UNBOUND_MARKER.txt'
    archive_report = output/'archive-check/REPORT.json'
    archive_layer = {'expected_archive_sha256': built['archive_sha256'], 'replacement_archive_sha256': sha(alternative),
                     'input_archive_replaced_after_validated_extraction': sha(mutable) == sha(alternative),
                     'unbound_extra_present_in_ordinary_extraction': ordinary_marker.exists(), 'checker_completed': archive_report.exists(),
                     'error': error, 'runtime_replay_stubbed': True,
                     'scope': 'Real archive hashing, validation and extraction; only expensive runtime replay is stubbed to isolate archive identity. No claim that the stub qualifies software or a real published archive.'}
    archive_layer['passed'] = not ordinary_marker.exists() and (archive_report.exists() or (error is not None and 'IDENTITY' in error))
    report = {'schema': 'agi-alpha/publication-identity-probe007/v1', 'runner_sha256': sha(runner), 'checker_sha256': sha(checker),
              'verifier_sha256': sha(__file__), 'pre_import': pre_import, 'archive_snapshot': archive_layer,
              'passed': pre_import['passed'] and archive_layer['passed'],
              'scope': 'Harmless verifier-owned copied source and generated ZIP fixtures only. Candidate source, original evidence and actual releases are not modified.'}
    with (output/'REPORT.json').open('x') as stream:
        json.dump(report, stream, sort_keys=True, indent=2);stream.write('\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('runner', 'checker', 'output'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    result = probe(args.runner, args.checker, args.output)
    print(json.dumps({'passed': result['passed'], 'pre_import': result['pre_import'], 'archive_snapshot': result['archive_snapshot']}))
    sys.exit(0 if result['passed'] else 1)
