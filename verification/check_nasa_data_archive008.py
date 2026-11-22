"""Check the downloaded data-only Git tree and restore exact evidence bytes.

This is byte preservation, not qualification of a new scientific instrument.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile


def check(archive, commit, expected_tree, output):
    archive, output = Path(archive), Path(output).absolute()
    if output.exists() or any(p.is_symlink() for p in (output, *output.parents)):
        raise ValueError('FRESH_OUTPUT_REQUIRED')
    if archive.is_symlink() or archive.stat().st_size > 128 * 1024**2:
        raise ValueError('ARCHIVE_INPUT_BOUND')
    if len(commit) != 40 or any(x not in '0123456789abcdef' for x in commit):
        raise ValueError('FULL_COMMIT_REQUIRED')
    expected = json.loads(Path(expected_tree).read_text())
    output.mkdir(parents=True, exist_ok=False)
    root = output / 'downloaded-source'
    root.mkdir()
    prefix = 'AGI-Alpha-Invention-Flywheel-Lab-' + commit
    found = {}
    expanded = 0
    with tarfile.open(archive, 'r:gz') as package:
        for item in package:
            path = PurePosixPath(item.name)
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != prefix or '\\' in item.name:
                raise ValueError('ARCHIVE_PATH_SCOPE')
            if item.isdir():
                continue
            name = PurePosixPath(*path.parts[1:]).as_posix()
            if not item.isfile() or name not in expected or name in found:
                raise ValueError('ARCHIVE_SET_OR_TYPE')
            expanded += item.size
            if expanded > 96 * 1024**2 or len(found) >= 32:
                raise ValueError('ARCHIVE_RESOURCE_BOUND')
            raw = package.extractfile(item).read()
            actual = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            if actual != expected[name]:
                raise ValueError('GIT_BLOB_IDENTITY')
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            found[name] = hashlib.sha256(raw).hexdigest()
    if set(found) != set(expected):
        raise ValueError('INCOMPLETE_GIT_TREE')
    destination = output / 'restored-fields'
    subprocess.run([sys.executable, str(root / 'assemble_nasa_fields008.py'), '--root', str(root), '--output', str(destination)], check=True, timeout=60)
    report = {'schema': 'agi-alpha/downloaded-nasa-data-integrity008/v1', 'source_commit': commit,
              'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'source_files': found,
              'complete_git_blob_set_verified_before_execution': True,
              'source_bytes_unchanged': all(hashlib.sha256((root / n).read_bytes()).hexdigest() == h for n, h in found.items()),
              'restored': json.loads((destination / 'REPORT.json').read_text()),
              'checker_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': 'Exact downloaded frozen data bytes and lossless assembly only. No new runtime, physical, superiority, commercial or mission qualification.'}
    report['data_integrity_verified'] = report['source_bytes_unchanged'] and report['restored']['state'] == 'complete'
    (output / 'REPORT.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', required=True)
    p.add_argument('--commit', required=True)
    p.add_argument('--expected-tree', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    r = check(a.archive, a.commit, a.expected_tree, a.output)
    print(json.dumps({'data_integrity_verified': r['data_integrity_verified'], 'restored_files': len(r['restored']['files'])}))
