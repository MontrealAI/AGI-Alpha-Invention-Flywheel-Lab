"""Download an exact GitHub source package, bind every byte to its Git tree, execute 008.

Trusted reviewed commands only; resource006 is not arbitrary-code isolation. Sandbox
qualification precedes interpreted synthesis. No scientific confirmation is implied.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.resource006 import run

REPO = 'MontrealAI/AGI-Alpha-Invention-Flywheel-Lab'
MAX_DOWNLOAD = 128 * 1024**2
MAX_EXPANDED = 512 * 1024**2


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def qualify(source_ref, output, downloaded_archive=None):
    if len(source_ref) != 40 or any(c not in '0123456789abcdef' for c in source_ref):
        raise ValueError('FULL_COMMIT_REQUIRED')
    output = Path(output).absolute()
    if output.exists() or any(x.is_symlink() for x in (output, *output.parents)):
        raise ValueError('FRESH_OUTPUT_REQUIRED')
    # Trusted local object database supplies the complete expected tree, before download.
    tree = subprocess.check_output(['git', 'ls-tree', '-rz', source_ref], cwd=ROOT)
    expected = {}
    for row in tree.split(b'\0'):
        if not row:
            continue
        metadata, name = row.split(b'\t', 1)
        mode, kind, digest = metadata.decode().split()
        if mode not in ('100644', '100755') or kind != 'blob':
            raise ValueError('REGULAR_SOURCE_FILES_ONLY')
        expected[name.decode()] = digest
    output.mkdir(parents=True)
    url = 'https://codeload.github.com/' + REPO + '/tar.gz/' + source_ref
    archive = output / 'downloaded.tar.gz'
    received = 0
    if downloaded_archive is not None:
        src = Path(downloaded_archive).absolute()
        if src.is_symlink() or not src.is_file() or src.stat().st_size > MAX_DOWNLOAD:
            raise ValueError('DOWNLOADED_ARCHIVE_SCOPE')
        raw_archive = src.read_bytes()
        archive.write_bytes(raw_archive)
        received = len(raw_archive)
    else:
        with urllib.request.urlopen(url, timeout=60) as response, archive.open('xb') as stream:
            while True:
                block = response.read(1024**2)
                if not block:
                    break
                received += len(block)
                if received > MAX_DOWNLOAD:
                    raise ValueError('DOWNLOAD_LIMIT')
                stream.write(block)
    root = output / 'source'
    root.mkdir()
    actual = {}
    prefix = 'AGI-Alpha-Invention-Flywheel-Lab-' + source_ref
    expanded = 0
    with tarfile.open(archive, 'r:gz') as package:
        for member in package:
            path = PurePosixPath(member.name)
            if not path.parts or path.parts[0] != prefix or path.is_absolute() or '..' in path.parts or '\\' in member.name:
                raise ValueError('PACKAGE_PATH_SCOPE')
            if member.isdir():
                continue
            name = PurePosixPath(*path.parts[1:]).as_posix()
            if not member.isfile() or name not in expected or name in actual:
                raise ValueError('PACKAGE_TREE_SET_OR_TYPE')
            expanded += member.size
            if expanded > MAX_EXPANDED or len(actual) >= 20000:
                raise ValueError('PACKAGE_RESOURCE_LIMIT')
            raw = package.extractfile(member).read()
            git_blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            if git_blob != expected[name]:
                raise ValueError('SOURCE_BLOB_MISMATCH ' + name)
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            actual[name] = sha(raw)
    if set(actual) != set(expected):
        raise ValueError('SOURCE_TREE_INCOMPLETE')
    manifest = {'source_ref': source_ref, 'url': url, 'archive_sha256': sha(archive.read_bytes()),
                'download_bytes': received, 'expanded_bytes': expanded, 'files': actual}
    (output / 'SOURCE_MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n')
    commands = [
        ('sandbox', ['python3', '-m', 'unittest', 'tests.test_sandbox', '-v'], 60),
        ('authority', ['python3', '-m', 'unittest', 'verification.test_observability008', '-v'], 30),
        ('construct', ['python3', '-m', 'experiments.observability008', 'construct', '--output', str(output / 'construction')], 30),
        ('accept', ['python3', 'verification/accept_linear_plan008.py', '--root', '.', '--task', 'research/observability008/elowitz/model_constraints.json', '--delivery', str(output / 'construction/DELIVERY.json'), '--output', str(output / 'review')], 30),
        ('retain', ['python3', '-m', 'experiments.observability008', 'retain-use', '--previous', str(output / 'construction'), '--acceptance', 'evidence/overnight-008/observability-accepted-r2/ACCEPTANCE.json', '--fresh', 'research/observability008/crauste/model_constraints.json', '--output', str(output / 'retained')], 30),
        ('forced-model', ['python3', 'research/observability008/compile_petab_forcing.py', '--source', 'research/observability008/boehm/source', '--output', str(output / 'boehm')], 60),
        ('literals', ['python3', 'scripts/replay_literal_check008.py', '--output', str(output / 'literal')], 20),
    ]
    checks = {}
    for name, command, cpu in commands:
        receipt = run(command, output / (name + '-bounded'), output / 'RESOURCE_LEDGER.json', name,
                      {'wall_seconds': cpu * 2, 'cpu_seconds': cpu, 'memory_bytes': 2 * 1024**3,
                       'output_bytes': 32 * 1024**2, 'storage_bytes': 64 * 1024**2}, cwd=root)
        checks[name] = receipt
        if receipt['receipt']['state'] != 'complete':
            break
        if name == 'accept' and json.loads((output / 'review/ACCEPTANCE.json').read_text()).get('accepted') is not True:
            raise ValueError('SCOPED_ACCEPTANCE_FAILED')
    unchanged = all(sha((root / name).read_bytes()) == digest for name, digest in actual.items())
    report = {'schema': 'agi-alpha/downloaded-package008/v1', 'source_ref': source_ref,
              'archive_sha256': manifest['archive_sha256'], 'all_git_blobs_verified_before_execution': True,
              'source_files': len(actual), 'commands': checks, 'source_bytes_unchanged': unchanged,
              'runtime_qualified': len(checks) == len(commands) and all(x['receipt']['state'] == 'complete' for x in checks.values()) and unchanged,
              'scope': 'Downloaded exact GitHub contents, executed scoped 008 scientific construction/verification/real memory path. No XCT, paper, physical, superiority or commercial qualification is implied.'}
    (output / 'REPORT.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-ref', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--archive', help='Previously downloaded exact codeload package; still checks every Git blob before execution.')
    a = p.parse_args()
    result = qualify(a.source_ref, a.output, a.archive)
    print(json.dumps({'runtime_qualified': result['runtime_qualified'], 'source_ref': result['source_ref'], 'output': a.output}))
    raise SystemExit(0 if result['runtime_qualified'] else 1)
