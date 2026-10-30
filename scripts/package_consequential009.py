"""Create and verify a standalone source/evidence archive without Git history."""
import argparse, hashlib, io, json, re, subprocess, tarfile, zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = ['campaign/consequential-009', 'inventions/consequential009', 'research/consequential009',
            'verification/consequential009', 'evidence/consequential009', 'docs/consequential009']

def sha(raw): return hashlib.sha256(raw).hexdigest()
def safe(name):
    p = PurePosixPath(name)
    return bool(name) and bool(p.parts) and name == p.as_posix() and not p.is_absolute() and '..' not in p.parts and '\\' not in name

def pack(output, source_commit):
    freeze = json.loads((ROOT / 'campaign/consequential-009/SOURCE_FREEZE.json').read_text())
    files = set(freeze['files']) | {'AGENTS.md', 'CHARTER.md', 'FIRST_CAMPAIGN.md', 'THIRD_PARTY.md',
        'scripts/package_consequential009.py', 'scripts/build_consequential009_paper.py', 'REPRODUCING_CONSEQUENTIAL009.md'}
    files.update(str(p.relative_to(ROOT)) for p in (ROOT / 'tests').glob('test_consequential009*.py'))
    files.update(str(p.relative_to(ROOT)) for p in (ROOT / 'scripts').glob('build_consequential009_*.py'))
    for prefix in PREFIXES:
        for p in (ROOT / prefix).rglob('*'):
            if not p.is_file() or p.is_symlink(): continue
            name = str(p.relative_to(ROOT))
            if '__pycache__' in p.parts or p.suffix in {'.pyc', '.lock', '.aux', '.png'} or '.pending-' in p.name: continue
            if '/reference-r1/artifacts/raw/' in name: continue
            files.add(name)
    data = {name: (ROOT / name).read_bytes() for name in sorted(files)}
    if source_commit != 'WORKTREE':
        if not re.fullmatch('[0-9a-f]{40}', source_commit): raise ValueError('EXACT_COMMIT_OR_EXPLICIT_WORKTREE_REQUIRED')
        entries = subprocess.check_output(['git', '-C', str(ROOT), 'ls-tree', '-r', '-z', source_commit]).split(b'\0')
        public = {entry.split(b'\t', 1)[1].decode(): entry.split(b'\t', 1)[0].split()[2].decode() for entry in entries if entry}
        for name, raw in data.items():
            blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            if public.get(name) != blob: raise ValueError('CLAIMED_COMMIT_DOES_NOT_CONTAIN_EXACT_PACKAGED_BYTES ' + name)
    manifest = {'schema': 'agi-alpha/consequential009-download-manifest/v1',
        'source_commit': None if source_commit == 'WORKTREE' else source_commit,
        'source_identity_scope': 'UNPUBLISHED_WORKTREE; exact file hashes only' if source_commit == 'WORKTREE' else 'Every packaged source/evidence blob matched the exact claimed Git commit before packing.',
        'source_freeze_sha256': sha((ROOT / 'campaign/consequential-009/SOURCE_FREEZE.json').read_bytes()),
        'files': {name: {'sha256': sha(raw), 'bytes': len(raw)} for name, raw in data.items()},
        'original_reference_raw': 'Lossless verified reference-raw-r1.tar.gz plus per-original SHA256 manifest; restore separately. New replay generates new raw bytes independently.'}
    data['DOWNLOAD_MANIFEST.json'] = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in data.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 30, 0, 0, 0)); info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    return {'files': len(data), 'bytes': output.stat().st_size, 'sha256': sha(output.read_bytes()), 'source_commit': manifest['source_commit']}

def extract(archive_path, destination):
    destination = Path(destination)
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) > 5000 or len(names) != len(set(names)) or any(not safe(n) for n in names): raise ValueError('UNSAFE_ARCHIVE_NAMES')
        name_set = set(names)
        if any('/'.join(PurePosixPath(name).parts[:i]) in name_set for name in names for i in range(1, len(PurePosixPath(name).parts))): raise ValueError('ARCHIVE_FILE_PREFIX_CONFLICT')
        if sum(x.file_size for x in archive.infolist()) > 256 * 1024**2: raise ValueError('ARCHIVE_SIZE_CAP')
        if any((x.external_attr >> 16) & 0o170000 not in {0, 0o100000} for x in archive.infolist()): raise ValueError('NONREGULAR_ARCHIVE_MEMBER')
        manifest = json.loads(archive.read('DOWNLOAD_MANIFEST.json'))
        if set(names) != set(manifest['files']) | {'DOWNLOAD_MANIFEST.json'}: raise ValueError('ARCHIVE_MANIFEST_MEMBERSHIP')
        verified = {}
        for name in names:
            raw = archive.read(name)
            if name != 'DOWNLOAD_MANIFEST.json':
                expected = manifest['files'][name]
                if sha(raw) != expected['sha256'] or len(raw) != expected['bytes']: raise ValueError('ARCHIVE_BYTE_MISMATCH ' + name)
            verified[name] = raw
        destination.mkdir(parents=True, exist_ok=False)
        for name, raw in verified.items():
            path = destination / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    return {'files_verified': len(manifest['files']), 'source_commit': manifest['source_commit'], 'destination': str(destination)}

def restore_reference(root):
    root = Path(root).resolve(); record = json.loads((root / 'evidence/consequential009/reference-raw-r1-MANIFEST.json').read_text())
    raw = (root / record['archive']).read_bytes()
    if sha(raw) != record['archive_sha256'] or len(raw) != record['archive_bytes']: raise ValueError('RAW_ARCHIVE_IDENTITY')
    restored = 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:gz') as archive:
        members = archive.getmembers()
        if len(members) != len(record['files']) or {x.name for x in members} != set(record['files']): raise ValueError('RAW_ARCHIVE_MEMBERSHIP')
        for member in members:
            if not member.isfile() or not safe(member.name): raise ValueError('RAW_ARCHIVE_UNSAFE_MEMBER')
            expected = record['files'][member.name]
            if member.size != expected['bytes'] or member.size > 16 * 1024**2: raise ValueError('RAW_ARCHIVE_MEMBER_SIZE')
            value = archive.extractfile(member).read()
            if sha(value) != expected['sha256']: raise ValueError('RAW_ARCHIVE_MEMBER_IDENTITY')
            path = root / record['original_base'] / member.name; path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                if path.is_symlink() or sha(path.read_bytes()) != expected['sha256']: raise ValueError('RAW_RESTORE_CONFLICT')
            else: path.write_bytes(value)
            restored += 1
    return {'exact_original_files_verified_or_restored': restored, 'scope': 'Preserved first-run observation bytes, not a regenerated edition.'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('pack'); p.add_argument('--output', required=True); p.add_argument('--source-commit', required=True)
    p = sub.add_parser('extract'); p.add_argument('--archive', required=True); p.add_argument('--destination', required=True)
    p = sub.add_parser('restore-reference'); p.add_argument('--root', default=ROOT)
    args = parser.parse_args()
    result = pack(args.output, args.source_commit) if args.command == 'pack' else extract(args.archive, args.destination) if args.command == 'extract' else restore_reference(args.root)
    print(json.dumps(result, indent=2))
