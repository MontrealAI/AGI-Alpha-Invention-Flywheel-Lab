"""Lossless publication packaging for completed commercial010 evidence.

This is a publication tool outside the frozen commercial candidate. Archives
preserve all original/interrupted and resumed file bytes, including SQLite,
logs and receipts. ZIP timestamps are normalized; no evidence is regenerated.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

PART_LIMIT = 600000
MAX_BYTES = 6 * 1024**3
MAX_INDEX = 16 * 1024**2
CHUNK = 1024 * 1024
STAMP = (1980, 1, 1, 0, 0, 0)
EPOCH = 315532800
SCHEMA = 'agi-alpha/commercial010-lossless-archive/v1'


def digest_file(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b''):
            value.update(chunk)
    return value.hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def read_json(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_INDEX:
        raise ValueError('BOUNDED_REGULAR_JSON_REQUIRED')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('DUPLICATE_JSON_FIELD')
            result[key] = value
        return result
    return json.loads(path.read_bytes(), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def safe_path(path, *, new=False):
    path = Path(path).absolute()
    if '..' in path.parts or path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise ValueError('SYMLINK_OR_PARENT_PATH_REFUSED')
    if new and path.exists():
        raise FileExistsError(path)
    return path


def zip_path(name):
    if not isinstance(name, str) or not name or '\\' in name or '\x00' in name or ':' in name:
        raise ValueError('UNSAFE_ARCHIVE_ENTRY_PATH')
    text = name[:-1] if name.endswith('/') else name
    path = PurePosixPath(text)
    if path.is_absolute() or '..' in path.parts or '.' in path.parts or not path.parts or str(path) != text:
        raise ValueError('UNSAFE_ARCHIVE_ENTRY_PATH')
    if path.parts[0] not in {'original', 'resumed', 'interrupted_recovery'}:
        raise ValueError('UNKNOWN_ARCHIVE_SOURCE_PREFIX')
    return path


def complete_run(resumed, expected_freeze=None):
    resumed = safe_path(resumed)
    receipt = read_json(resumed / 'RECEIPT.json')
    recovery = read_json(resumed / 'RECOVERY.json')
    if receipt.get('state') != 'complete' or receipt.get('descendant_survivors') is not False:
        raise ValueError('COMPLETE_CLEAN_SUPERVISOR_RECEIPT_REQUIRED')
    if recovery.get('schema') != 'agi-alpha/commercial010-recovery/v1' or recovery.get('scope') != 'SIMULATED_ENGINEERING_RECOVERY':
        raise ValueError('COMPLETED_RECOVERY_PROOF_REQUIRED')
    if recovery.get('candidate_changes') is not False or recovery.get('seed_substitutions') is not False or recovery.get('parameter_adaptations') is not False:
        raise ValueError('UNCHANGED_FROZEN_RECOVERY_REQUIRED')
    if expected_freeze is not None and recovery.get('source_freeze_sha256') != expected_freeze:
        raise ValueError('EXTERNAL_SOURCE_FREEZE_MISMATCH')
    progress = resumed / 'RECOVERY_PROGRESS.jsonl'
    if not recovery.get('progress_sha256') or digest_file(progress) != recovery['progress_sha256']:
        raise ValueError('DURABLE_RECOVERY_PROGRESS_CHANGED')
    result = resumed / 'artifacts/RESULT.json'
    if digest_file(result) != recovery['result_sha256']:
        raise ValueError('RECOVERED_RESULT_CHANGED')
    return receipt, recovery


def fingerprint(path):
    s = Path(path).lstat()
    return (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns)


def snapshot(root, prefix):
    root = safe_path(root)
    if not root.is_dir():
        raise ValueError('SOURCE_DIRECTORY_REQUIRED')
    paths = [root, *sorted(root.rglob('*'), key=lambda p: p.relative_to(root).as_posix())]
    result = []
    for path in paths:
        s = path.lstat()
        if stat.S_ISLNK(s.st_mode) or not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):
            raise ValueError('ONLY_REGULAR_EVIDENCE_FILES_AND_DIRECTORIES')
        if stat.S_IMODE(s.st_mode) > 0o777:
            raise ValueError('PRIVILEGED_SOURCE_PERMISSION_REFUSED')
        relative = path.relative_to(root).as_posix()
        name = prefix + ('/' + relative if relative != '.' else '')
        directory = stat.S_ISDIR(s.st_mode)
        if directory:
            name += '/'
        zip_path(name)
        result.append({'path': path, 'name': name, 'kind': 'directory' if directory else 'file',
                       'mode': stat.S_IMODE(s.st_mode), 'fingerprint': fingerprint(path),
                       'source': prefix, 'relative_path': relative})
    return result


def new_file_from(source, destination):
    destination = safe_path(destination, new=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    safe_path(destination.parent)
    with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.publication-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            with Path(source).open('rb') as original:
                shutil.copyfileobj(original, stream, CHUNK)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink()
            raise
    try:
        os.link(temporary, destination)
        shutil.copystat(source, destination, follow_symlinks=False)
    finally:
        temporary.unlink()
    return destination


def archive(original, resumed, output, expected_freeze=None, failed_recovery=None):
    original, resumed, output = safe_path(original), safe_path(resumed), safe_path(output, new=True)
    receipt, recovery = complete_run(resumed, expected_freeze)
    if not (original / 'PENDING.json').is_file():
        raise ValueError('PRESERVED_INTERRUPTED_RUN_REQUIRED')
    failed_recovery = safe_path(failed_recovery) if failed_recovery is not None else None
    sources = [original, resumed] + ([failed_recovery] if failed_recovery else [])
    for source in sources:
        if output == source or source in output.parents:
            raise ValueError('ARCHIVE_OUTPUT_MUST_BE_OUTSIDE_INPUT_ROOTS')
    entries = snapshot(original, 'original') + snapshot(resumed, 'resumed')
    if failed_recovery:
        entries += snapshot(failed_recovery, 'interrupted_recovery')
    entries.sort(key=lambda item: item['name'])
    if sum(e['fingerprint'][3] for e in entries if e['kind'] == 'file') > MAX_BYTES:
        raise ValueError('SOURCE_BYTE_CAP')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.commercial010-package-', dir=output.parent) as work:
        temporary = Path(work)
        packed = temporary / 'commercial010-evidence.zip'
        indexed = []
        with zipfile.ZipFile(packed, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
            for entry in entries:
                path = entry['path']
                if fingerprint(path) != entry['fingerprint']:
                    raise ValueError('SOURCE_CHANGED_DURING_PACKAGING')
                info = zipfile.ZipInfo(entry['name'], date_time=STAMP)
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                info._compresslevel = 6
                kind_mode = stat.S_IFDIR if entry['kind'] == 'directory' else stat.S_IFREG
                info.external_attr = ((kind_mode | entry['mode']) << 16) | (0x10 if entry['kind'] == 'directory' else 0)
                value, size = hashlib.sha256(), 0
                if entry['kind'] == 'directory':
                    z.writestr(info, b'')
                else:
                    with path.open('rb') as source, z.open(info, 'w', force_zip64=True) as destination:
                        for chunk in iter(lambda: source.read(CHUNK), b''):
                            size += len(chunk)
                            value.update(chunk)
                            destination.write(chunk)
                    if size != entry['fingerprint'][3]:
                        raise ValueError('SOURCE_READ_SIZE_CHANGED')
                if fingerprint(path) != entry['fingerprint']:
                    raise ValueError('SOURCE_CHANGED_DURING_PACKAGING')
                indexed.append({'path': entry['name'], 'kind': entry['kind'], 'bytes': size,
                                'sha256': value.hexdigest(), 'mode': entry['mode'],
                                'source': entry['source'], 'relative_path': entry['relative_path']})
        # Detect added/removed paths or modified bytes/metadata during packaging.
        again = snapshot(original, 'original') + snapshot(resumed, 'resumed')
        if failed_recovery:
            again += snapshot(failed_recovery, 'interrupted_recovery')
        if {e['name']: e['fingerprint'] for e in entries} != {e['name']: e['fingerprint'] for e in again}:
            raise ValueError('SOURCE_TREE_CHANGED_DURING_PACKAGING')
        staged = temporary / 'parts'
        staged.mkdir()
        parts = []
        with packed.open('rb') as source:
            number = 0
            while True:
                raw = source.read(PART_LIMIT)
                if not raw:
                    break
                filename = 'part-%05d.bin' % number
                (staged / filename).write_bytes(raw)
                parts.append({'order': number, 'filename': filename, 'bytes': len(raw),
                              'sha256': hashlib.sha256(raw).hexdigest()})
                number += 1
        index = {'schema': SCHEMA, 'scope': 'LOSSLESS_PUBLICATION_OF_SIMULATED_ENGINEERING_EVIDENCE',
                 'format': 'ZIP_DEFLATED', 'compression_level': 6, 'normalized_timestamp': list(STAMP),
                 'part_max_bytes': PART_LIMIT, 'archive_filename': packed.name,
                 'archive_bytes': packed.stat().st_size, 'archive_sha256': digest_file(packed),
                 'parts': parts, 'entries': indexed,
                 'source_freeze_sha256': recovery['source_freeze_sha256'],
                 'interruption_inventory_sha256': recovery['interruption_inventory_sha256'],
                 'original_pending_sha256': digest_file(original / 'PENDING.json'),
                 'resumed_receipt_sha256': digest_file(resumed / 'RECEIPT.json'),
                 'recovery_sha256': digest_file(resumed / 'RECOVERY.json'),
                 'recovery_progress_sha256': recovery['progress_sha256'],
                 'failed_recovery_receipt_sha256': digest_file(failed_recovery / 'RECEIPT.json') if failed_recovery and (failed_recovery / 'RECEIPT.json').is_file() else None,
                 'semantics': 'Original interrupted outputs and completed resumed outputs are retained separately. No source bytes, verdicts, prices, seeds or financial evidence are regenerated. Timestamp normalization changes ZIP metadata only.'}
        (staged / 'INDEX.json').write_bytes(canonical(index))
        verify_zip(packed, index)
        # Output was checked absent; mkdir is exclusive and copies use exclusive
        # destination links so publication cannot overwrite an existing artifact.
        output.mkdir()
        for child in sorted(staged.iterdir()):
            new_file_from(child, output / child.name)
    return {'index': str(output / 'INDEX.json'), 'index_sha256': digest_file(output / 'INDEX.json'),
            'parts': len(parts), 'archive_bytes': index['archive_bytes'], 'entries': len(indexed)}


def validate_index(path, expected=None):
    path = safe_path(path)
    if expected is not None and digest_file(path) != expected:
        raise ValueError('EXTERNAL_ARCHIVE_INDEX_MISMATCH')
    index = read_json(path)
    if index.get('schema') != SCHEMA or index.get('format') != 'ZIP_DEFLATED' or index.get('part_max_bytes') != PART_LIMIT:
        raise ValueError('ARCHIVE_INDEX_SCHEMA')
    if type(index.get('archive_bytes')) is not int or not 0 < index['archive_bytes'] <= MAX_BYTES:
        raise ValueError('ARCHIVE_BYTE_CAP')
    parts, entries = index.get('parts'), index.get('entries')
    if not isinstance(parts, list) or not parts or not isinstance(entries, list) or not entries:
        raise ValueError('COMPLETE_PART_AND_ENTRY_INVENTORY_REQUIRED')
    names = set()
    for number, part in enumerate(parts):
        if not isinstance(part, dict):
            raise ValueError('PART_OBJECT_REQUIRED')
        expected_name = 'part-%05d.bin' % number
        if part.get('order') != number or part.get('filename') != expected_name or type(part.get('bytes')) is not int or not 0 < part['bytes'] <= PART_LIMIT:
            raise ValueError('ORDERED_BOUNDED_PARTS_REQUIRED')
    if sum(p['bytes'] for p in parts) != index['archive_bytes']:
        raise ValueError('PART_BYTE_CONSERVATION_FAILURE')
    total = 0
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('ENTRY_OBJECT_REQUIRED')
        name = entry.get('path')
        zip_path(name)
        if name in names or entry.get('kind') not in {'file', 'directory'} or type(entry.get('bytes')) is not int or entry['bytes'] < 0:
            raise ValueError('UNIQUE_VALID_ENTRY_INVENTORY_REQUIRED')
        if name.endswith('/') != (entry['kind'] == 'directory') or entry['kind'] == 'directory' and entry['bytes'] != 0:
            raise ValueError('ENTRY_KIND_OR_SIZE_MISMATCH')
        if type(entry.get('mode')) is not int or not 0 <= entry['mode'] <= 0o777:
            raise ValueError('SAFE_ARCHIVE_PERMISSION_REQUIRED')
        total += entry['bytes']
        names.add(name)
    if total > MAX_BYTES:
        raise ValueError('EXTRACTED_BYTE_CAP')
    return index


def verify_zip(path, index):
    if Path(path).stat().st_size != index['archive_bytes'] or digest_file(path) != index['archive_sha256']:
        raise ValueError('REASSEMBLED_ARCHIVE_IDENTITY_MISMATCH')
    expected = {e['path']: e for e in index['entries']}
    with zipfile.ZipFile(path, 'r') as z:
        infos = z.infolist()
        if len(infos) != len(expected) or {i.filename for i in infos} != set(expected):
            raise ValueError('ZIP_ENTRY_INVENTORY_MISMATCH')
        for info in infos:
            zip_path(info.filename)
            entry = expected[info.filename]
            mode = info.external_attr >> 16
            desired_kind = stat.S_IFDIR if entry['kind'] == 'directory' else stat.S_IFREG
            if stat.S_IFMT(mode) != desired_kind or stat.S_IMODE(mode) != entry['mode'] or info.date_time != STAMP or info.compress_type != zipfile.ZIP_DEFLATED or info.file_size != entry['bytes']:
                raise ValueError('ZIP_ENTRY_METADATA_MISMATCH')
            value, count = hashlib.sha256(), 0
            with z.open(info) as stream:
                for raw in iter(lambda: stream.read(CHUNK), b''):
                    count += len(raw)
                    if count > entry['bytes']:
                        raise ValueError('ZIP_ENTRY_EXCEEDS_DECLARED_SIZE')
                    value.update(raw)
            if count != entry['bytes'] or value.hexdigest() != entry['sha256']:
                raise ValueError('ZIP_ENTRY_BYTE_IDENTITY_MISMATCH')
    return True


def reassemble(index_path, output, expected=None):
    index_path, output = safe_path(index_path), safe_path(output, new=True)
    index = validate_index(index_path, expected)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix='.reassemble-', delete=False) as joined:
        temporary = Path(joined.name)
        try:
            for part in index['parts']:
                source = safe_path(index_path.parent / part['filename'])
                if not source.is_file() or source.stat().st_size != part['bytes'] or digest_file(source) != part['sha256']:
                    raise ValueError('ARCHIVE_PART_IDENTITY_MISMATCH ' + part['filename'])
                with source.open('rb') as stream:
                    shutil.copyfileobj(stream, joined, CHUNK)
            joined.flush()
            os.fsync(joined.fileno())
        except BaseException:
            temporary.unlink()
            raise
    try:
        verify_zip(temporary, index)
        os.link(temporary, output)
    finally:
        temporary.unlink()
    return {'archive': str(output), 'archive_sha256': index['archive_sha256'], 'verified_entries': len(index['entries'])}


def extract(index_path, output, expected=None):
    index_path, output = safe_path(index_path), safe_path(output, new=True)
    index = validate_index(index_path, expected)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.evidence-extract-', dir=output.parent) as tmp:
        packed = Path(tmp) / 'verified.zip'
        reassemble(index_path, packed, expected)
        staged = Path(tmp) / 'tree'
        staged.mkdir()
        with zipfile.ZipFile(packed) as z:
            for entry in index['entries']:
                relative = zip_path(entry['path'])
                destination = staged.joinpath(*relative.parts)
                if entry['kind'] == 'directory':
                    destination.mkdir(parents=True, exist_ok=True)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with destination.open('xb') as stream, z.open(entry['path']) as source:
                        shutil.copyfileobj(source, stream, CHUNK)
                    if digest_file(destination) != entry['sha256']:
                        raise ValueError('EXTRACTED_BYTE_IDENTITY_MISMATCH')
            for entry in sorted(index['entries'], key=lambda e: len(PurePosixPath(e['path']).parts), reverse=True):
                destination = staged.joinpath(*zip_path(entry['path']).parts)
                os.chmod(destination, entry['mode'])
                os.utime(destination, (EPOCH, EPOCH))
        output.mkdir()
        for child in sorted(staged.iterdir()):
            shutil.copytree(child, output / child.name, symlinks=False, copy_function=lambda a, b: new_file_from(a, b))
    return {'output': str(output), 'verified_entries': len(index['entries']), 'archive_sha256': index['archive_sha256']}


def publish(resumed, destination, expected_freeze=None):
    resumed, destination = safe_path(resumed), safe_path(destination)
    _, recovery = complete_run(resumed, expected_freeze)
    source = resumed / 'artifacts'
    result = read_json(source / 'RESULT.json')
    prices = read_json(source / 'PRICE_FREEZE.json')
    if result.get('scope') != 'SIMULATED' or prices.get('scope') != 'SIMULATED':
        raise ValueError('SIMULATED_PUBLICATION_SCOPE_REQUIRED')
    if result['policy_file_sha256'] != prices['policy_sha256'] or result['cohort_file_sha256'] != prices['cohort_sha256']:
        raise ValueError('AGGREGATE_PRICE_FREEZE_IDENTITY_MISMATCH')
    targets = [destination / 'RESULT.json', destination / 'PRICE_FREEZE.json', destination / 'representatives']
    for path in targets:
        safe_path(path, new=True)
    selection = {'schema': 'agi-alpha/commercial010-representative-selection/v1', 'scope': 'SIMULATED',
                 'rule': 'For each arm, use only declared qualification worlds. Sort individual results by complete profit, world ID, seed; select upper median at index n//2. No favorable reselection.',
                 'aggregate_sha256': digest_file(source / 'RESULT.json'), 'price_freeze_sha256': digest_file(source / 'PRICE_FREEZE.json'),
                 'recovery_sha256': digest_file(resumed / 'RECOVERY.json'),
                 'recovery_progress_sha256': recovery['progress_sha256'],
                 'failed_recovery_receipt_sha256': digest_file(failed_recovery / 'RECEIPT.json') if failed_recovery and (failed_recovery / 'RECEIPT.json').is_file() else None,
                 'source_freeze_sha256': recovery['source_freeze_sha256'], 'arms': {}}
    progress = {}
    for line in (resumed / 'RECOVERY_PROGRESS.jsonl').read_text().splitlines():
        record = json.loads(line)
        relative = record['relative_directory']
        if relative in progress:
            raise ValueError('DUPLICATE_RECOVERY_WORLD_PROGRESS')
        progress[relative] = record['result_sha256']
    chosen = {}
    for arm, summary in sorted(result['arms'].items()):
        if not isinstance(arm, str) or not arm or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789_' for c in arm):
            raise ValueError('SAFE_ARM_IDENTIFIER_REQUIRED')
        # The aggregate qualification summary pins the number and distribution;
        # frozen calibration worlds are read from the same campaign policy.
        root = Path(__file__).resolve().parents[1]
        policy = read_json(root / 'campaign/commercial-010/POLICY.json')
        if digest_file(root / 'campaign/commercial-010/POLICY.json') != result['policy_file_sha256']:
            raise ValueError('FROZEN_POLICY_CHANGED')
        qualified = {w['id'] for w in policy['worlds'] if w['qualification_region']}
        candidates = []
        for path in sorted((source / 'confirmation' / arm).glob('*/*/RESULT.json')):
            world = read_json(path)
            if world['arm']['id'] != arm or world['scope'] != 'SIMULATED':
                raise ValueError('REPRESENTATIVE_ARM_OR_SCOPE_MISMATCH')
            if world['world'] in qualified:
                candidates.append((world['ledger']['summary']['profit'], world['world'], world['seed'], path, world))
        if len(candidates) != summary['qualification_region']['runs']:
            raise ValueError('REPRESENTATIVE_COHORT_COUNT_MISMATCH')
        candidates.sort(key=lambda x: x[:3])
        profit, world_id, seed, path, world = candidates[len(candidates) // 2]
        if profit != summary['qualification_region']['profit_median']:
            raise ValueError('AGGREGATE_MEDIAN_MISMATCH')
        directory = path.parent.relative_to(source).as_posix()
        if progress.get(directory) != digest_file(path):
            raise ValueError('REPRESENTATIVE_NOT_BOUND_TO_DURABLE_RECOVERY_PROGRESS')
        relative = path.relative_to(resumed).as_posix()
        selection['arms'][arm] = {'source_path': 'resumed/' + relative, 'source_sha256': digest_file(path),
                                  'qualification_runs': len(candidates), 'selected_rank_zero_based': len(candidates) // 2,
                                  'world': world_id, 'seed': seed, 'complete_profit': profit,
                                  'financial_summary': world['ledger']['summary'],
                                  'paid_jobs': world['paid_jobs'], 'earned_funded_cycles': world['earned_funded_cycles'],
                                  'reinvested_earned': world['reinvested_earned']}
        chosen[arm] = path
    destination.mkdir(parents=True, exist_ok=True)
    new_file_from(source / 'RESULT.json', destination / 'RESULT.json')
    new_file_from(source / 'PRICE_FREEZE.json', destination / 'PRICE_FREEZE.json')
    representatives = destination / 'representatives'
    representatives.mkdir()
    for arm, path in chosen.items():
        new_file_from(path, representatives / arm / 'RESULT.json')
    with (representatives / 'SELECTION.json').open('xb') as stream:
        stream.write(canonical(selection))
    return {'aggregate': str(destination / 'RESULT.json'), 'price_freeze': str(destination / 'PRICE_FREEZE.json'),
            'selection': str(representatives / 'SELECTION.json'), 'selection_sha256': digest_file(representatives / 'SELECTION.json')}


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    pack = commands.add_parser('archive')
    pack.add_argument('--original', type=Path, required=True)
    pack.add_argument('--resumed', type=Path, required=True)
    pack.add_argument('--failed-recovery', type=Path)
    pack.add_argument('--output-dir', type=Path, required=True)
    pack.add_argument('--freeze-sha256')
    for command in ['reassemble', 'extract']:
        sub = commands.add_parser(command)
        sub.add_argument('--index', type=Path, required=True)
        sub.add_argument('--output', type=Path, required=True)
        sub.add_argument('--index-sha256')
    sub = commands.add_parser('publish')
    sub.add_argument('--resumed', type=Path, required=True)
    sub.add_argument('--destination', type=Path, required=True)
    sub.add_argument('--freeze-sha256')
    args = parser.parse_args()
    if args.command == 'archive':
        result = archive(args.original, args.resumed, args.output_dir, args.freeze_sha256, args.failed_recovery)
    elif args.command == 'reassemble':
        result = reassemble(args.index, args.output, args.index_sha256)
    elif args.command == 'extract':
        result = extract(args.index, args.output, args.index_sha256)
    else:
        result = publish(args.resumed, args.destination, args.freeze_sha256)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
