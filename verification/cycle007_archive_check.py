import argparse
import hashlib
import io
import json
from pathlib import Path
import resource
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flywheel.archive_v2 import MANIFEST, PREFIX, extract


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(archive, expected_sha256, output, tools_dir, download_tools):
    archive, output = archive.absolute(), output.absolute()
    if archive.is_symlink() or not archive.is_file():
        raise ValueError('REGULAR_ARCHIVE_REQUIRED')
    with archive.open('rb') as source:
        raw = source.read(256*1024**2+1)
    if len(raw) > 256*1024**2:
        raise ValueError('SOURCE_ARCHIVE_BYTE_ALLOWANCE')
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError('PUBLISHED_ARCHIVE_IDENTITY_MISMATCH')
    if output.exists() or output.is_symlink() or any(p.is_symlink() for p in output.parents):
        raise FileExistsError(output)
    output.mkdir(parents=True)
    started = time.monotonic()
    validated = output/'validated-source'
    manifest = extract(io.BytesIO(raw), validated)
    ordinary_base = output/'ordinary-extraction'
    with zipfile.ZipFile(io.BytesIO(raw)) as stream:
        stream.extractall(ordinary_base)
    ordinary = ordinary_base/PREFIX.rstrip('/')
    roots = [('validated', validated), ('ordinary', ordinary)]
    results = []
    for name, root in roots:
        actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
        expected = set(manifest['files']) | ({MANIFEST} if name == 'ordinary' else set())
        if actual != expected:
            raise ValueError('EXTRACTED_SOURCE_SET_MISMATCH:'+name)
        for relative, digest in manifest['files'].items():
            path = root/relative
            if path.is_symlink() or sha(path) != digest:
                raise ValueError('EXTRACTED_SOURCE_IDENTITY:'+name+':'+relative)
        freeze = root/'campaign/cycle-007/REPRODUCTION_FREEZE.json'
        command = [str(Path(sys.executable).absolute()), str(root/'run_cycle007.py'), '--expected-freeze-sha256', sha(freeze),
                   '--output', str(output/(name+'-replay')), '--with-compatibility', '--chemistry-tools-dir', str(tools_dir.absolute())]
        if download_tools:
            command.append('--download-tools')
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        start = time.monotonic()
        with (output/(name+'.log')).open('xb') as log:
            completed = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT, timeout=850)
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        replay = output/(name+'-replay')
        complete = replay/'COMPLETE.json'
        accepted = completed.returncode == 0 and complete.is_file() and json.loads(complete.read_text())['report_sha256'] == sha(replay/'REPORT.json')
        result = {'extraction': name, 'files_verified': len(manifest['files']), 'command': command, 'returncode': completed.returncode,
                  'accepted_reproduction': accepted, 'wall_seconds': time.monotonic()-start,
                  'waited_child_cpu_seconds': after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime,
                  'complete_sha256': sha(complete) if complete.exists() else None, 'log_sha256': sha(output/(name+'.log'))}
        results.append(result)
        if not accepted:
            (output/'INCOMPLETE.json').write_text(json.dumps(results, indent=2)+'\n')
            raise RuntimeError('CLEAN_EXTRACTION_REPRODUCTION_FAILED:'+name)
    report = {'schema': 'agi-alpha/archive-qualification007/v1', 'archive_sha256': expected_sha256,
              'archive_bytes': len(raw), 'payload_files': len(manifest['files']), 'results': results,
              'ordinary_and_validated_extractions_reproduced': True, 'wall_seconds': time.monotonic()-started,
              'scope': 'Actual exact archive extraction and exposed source-bound engineering/chemical baseline replay; no new protected confirmation, invention success, commercial success or retroactive qualification of historical failed receipts.'}
    (output/'REPORT.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    (output/'COMPLETE.json').write_text(json.dumps({'report_sha256': sha(output/'REPORT.json')})+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--chemistry-tools-dir', type=Path, required=True)
    parser.add_argument('--download-tools', action='store_true')
    args = parser.parse_args()
    main(args.archive, args.expected_sha256, args.output, args.chemistry_tools_dir, args.download_tools)
