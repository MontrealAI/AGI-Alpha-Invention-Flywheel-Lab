#!/usr/bin/env python3
"""Assemble an owner review bundle from exact published HARNESS bytes and receipts.

This script makes no network requests and never accesses Squarespace or Library.
It neither rebuilds the customer ZIP nor upgrades a candidate's commercial status.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
from urllib.parse import urlsplit
import zipfile

REPOSITORY = 'https://github.com/MontrealAI/AGI-Alpha-Invention-Flywheel-Lab'
SOURCE_SCOPE = 'products/alpha-genesis-harness'
MAX_BYTES = 300_000_000
STATUSES = {'PASS', 'FAIL', 'BLOCKED', 'NOT TESTED'}
SHA = re.compile(r'[a-f0-9]{40}\Z')
DIGEST = re.compile(r'[a-f0-9]{64}\Z')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def parse_json(content):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON field: ' + key)
            result[key] = value
        return result
    return json.loads(content, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def read_json(path):
    return parse_json(Path(path).read_text(encoding='utf-8'))


def json_write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def safe_path(name):
    p = PurePosixPath(name)
    return bool(name and p.as_posix() == name and not p.is_absolute() and '\\' not in name
                and all(part not in {'', '.', '..'} and ':' not in part for part in p.parts))


def public_url(value):
    p = urlsplit(value)
    if p.scheme != 'https' or p.netloc != 'github.com' or p.username or p.password or p.query or p.fragment:
        raise ValueError('Use an HTTPS GitHub publication URL without credentials')
    if not value.startswith(REPOSITORY + '/'):
        raise ValueError('Publication URL must belong to the authorized repository')
    return value


def archive_snapshot(path, source, expected_hash):
    with Path(path).open('rb') as stream:
        raw = stream.read(MAX_BYTES)
        if len(raw) >= MAX_BYTES or stream.read(1):
            raise ValueError('Customer archive must remain under 300,000,000 bytes')
    actual = digest(raw)
    if expected_hash and actual != expected_hash:
        raise ValueError('Customer archive differs from the independently selected digest')
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        names = bundle.namelist()
        if not names or len(names) != len(set(names)) or any(not safe_path(n) for n in names):
            raise ValueError('Unsafe, empty or duplicate archive inventory')
        roots = {n.split('/', 1)[0] for n in names}
        if len(roots) != 1:
            raise ValueError('Customer archive must have one product directory')
        root = roots.pop()
        prefix = root + '/'
        if any(not n.startswith(prefix) for n in names):
            raise ValueError('Customer archive contains a non-product entry')
        if sum(i.file_size for i in bundle.infolist()) >= MAX_BYTES:
            raise ValueError('Expanded customer archive exceeds the safety envelope')
        for item in bundle.infolist():
            if item.file_size > 30_000_000 or ((item.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError('Oversized or linked customer archive entry')
        manifest = json.loads(bundle.read(prefix + 'RELEASE-MANIFEST.json'))
        if manifest.get('schema') != 'alpha-genesis-harness-release/v1':
            raise ValueError('Unsupported customer manifest schema')
        if manifest.get('source_revision') != source:
            raise ValueError('Customer manifest has a different source revision')
        if manifest.get('build_mode') != 'source-bound' or manifest.get('source_matches_commit') is not True:
            raise ValueError('Owner handoff requires an exact committed source-bound customer archive')
        if not SHA.fullmatch(str(manifest.get('source_product_tree', ''))):
            raise ValueError('Missing committed product tree identity')
        records = manifest.get('files')
        if not isinstance(records, list) or any(not isinstance(row, dict) for row in records):
            raise ValueError('Invalid customer manifest inventory')
        paths = [row.get('path') for row in records]
        if any(not isinstance(p, str) or not safe_path(p) for p in paths) or len(paths) != len(set(paths)):
            raise ValueError('Invalid or duplicate manifest path')
        if set(names) != {prefix + p for p in paths} | {prefix + 'RELEASE-MANIFEST.json'}:
            raise ValueError('Manifest and archive inventories differ')
        content = {}
        modes = {}
        for row in records:
            data = bundle.read(prefix + row['path'])
            if len(data) != row.get('bytes') or digest(data) != row.get('sha256'):
                raise ValueError('Customer file hash mismatch: ' + row['path'])
            content[row['path']] = data
            modes[row['path']] = (bundle.getinfo(prefix + row['path']).external_attr >> 16) & 0o777
        content['RELEASE-MANIFEST.json'] = bundle.read(prefix + 'RELEASE-MANIFEST.json')
        modes['RELEASE-MANIFEST.json'] = 0o644
    return raw, manifest, content, modes, actual


def model_evidence_snapshot(path, source, product_tree):
    """Verify a final public-evidence ZIP without extracting or upgrading its verdict.

    Returns the untouched ZIP, parsed manifest, all member bytes (including the
    manifest), and the ZIP SHA-256. Publication authenticity remains the caller's
    trusted download responsibility.
    """
    manifest_name = 'HOSTED-LOCAL-QUALIFICATION.json'
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{p}{i}' for p in ('COM', 'LPT') for i in range(1, 10)}

    def member_path(name):
        return (isinstance(name, str) and safe_path(name)
                and not any(ord(char) < 32 or char in '<>"|?*' for char in name)
                and all(part.rstrip(' .') == part and part.split('.')[0].upper() not in reserved
                        for part in PurePosixPath(name).parts))

    path = Path(path)
    if not member_path(path.name) or path.suffix.lower() != '.zip':
        raise ValueError('Model evidence must have a portable ZIP filename')
    with path.open('rb') as stream:
        raw = stream.read(MAX_BYTES)
        if len(raw) >= MAX_BYTES or stream.read(1):
            raise ValueError('Model evidence archive exceeds the safety envelope')
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        entries = bundle.infolist()
        names = [item.filename for item in entries]
        if (not names or len(names) > 10000 or len(names) != len(set(name.casefold() for name in names))
                or any(not member_path(name) for name in names)):
            raise ValueError('Unsafe, empty or duplicate model evidence inventory')
        if sum(item.file_size for item in entries) >= MAX_BYTES:
            raise ValueError('Expanded model evidence exceeds the safety envelope')
        for item in entries:
            kind = stat.S_IFMT(item.external_attr >> 16)
            if (item.is_dir() or item.external_attr & 0x10 or kind not in {0, stat.S_IFREG}
                    or item.orig_filename != item.filename or item.flag_bits & 1
                    or item.file_size > 30_000_000):
                raise ValueError('Model evidence members must be bounded regular files')
        if manifest_name not in names:
            raise ValueError('Model evidence is missing its root qualification manifest')
        manifest = parse_json(bundle.read(manifest_name))
        if (not isinstance(manifest, dict)
                or manifest.get('schema') != 'alpha-harness/hosted-local-qualification/v1'
                or manifest.get('status') not in {'PASS', 'FAIL'}):
            raise ValueError('Model evidence requires a final qualification manifest')
        if (manifest.get('source_revision') != source or manifest.get('source_product_tree') != product_tree
                or manifest.get('source_unchanged') is not True):
            raise ValueError('Model evidence must identify this unchanged source and product tree')
        records = manifest.get('published_sha256')
        if (not isinstance(records, dict) or manifest_name in records
                or any(not member_path(name) or not isinstance(value, str) or not DIGEST.fullmatch(value)
                       for name, value in records.items())):
            raise ValueError('Invalid model evidence hash inventory')
        if set(names) != set(records) | {manifest_name}:
            raise ValueError('Model evidence inventory differs from its published hashes')
        files = {manifest_name: bundle.read(manifest_name)}
        for name, expected in records.items():
            data = bundle.read(name)
            if digest(data) != expected:
                raise ValueError('Model evidence file hash mismatch: ' + name)
            files[name] = data
    return raw, manifest, files, digest(raw)


def operation_summary(path, source, archive_hash):
    receipt = read_json(path)
    if receipt.get('source_revision') != source or receipt.get('archive_sha256') != archive_hash:
        raise ValueError('Operation receipt must identify this source and this exact customer archive')
    if receipt.get('schema') != 'alpha-genesis-harness-downloaded-operation/v1':
        raise ValueError('Expected the published-archive operation receipt schema')
    parsed = operation_records(receipt.get('operations', []), Path(path).parent)
    passed = receipt.get('verdict') == 'PASSED IN SCOPE' and bool(parsed) and all(r['returncode'] == 0 for r in parsed)
    return receipt, {'status': 'PASS' if passed else 'FAIL', 'operations': parsed,
                     'dom_qualification': receipt.get('dom_qualification', 'NOT RECORDED'),
                     'scope': receipt.get('scope'), 'host': receipt.get('host')}


def operation_records(operations, log_folder, prefix=''):
    if not isinstance(operations, list):
        raise ValueError('Invalid operation list')
    parsed = []
    for index, row in enumerate(operations, 1):
        if not isinstance(row, dict):
            raise ValueError('Invalid operation receipt entry')
        if type(row.get('returncode')) is not int:
            raise ValueError('Operation returncode must be an integer, not a boolean or missing value')
        if (not isinstance(row.get('command'), list) or not row['command']
                or any(not isinstance(part, str) or not part for part in row['command'])):
            raise ValueError('Operation command must be a nonempty argument list')
        item = {'command': row.get('command'), 'returncode': row.get('returncode'), 'wall_seconds': row.get('wall_seconds')}
        output = ''
        for suffix in ('stdout', 'stderr'):
            log = Path(log_folder) / f'{prefix}operation-{index}.{suffix}.txt'
            if log.is_file() and not log.is_symlink() and log.stat().st_size < 5_000_000:
                output += log.read_text(errors='replace')
        python = re.findall(r'Ran (\d+) tests? in ', output)
        node = re.findall(r'(?:#|ℹ) tests (\d+)', output)
        skips = re.findall(r'OK \(skipped=(\d+)\)', output)
        if python:
            item['reported_python_tests'] = int(python[-1])
        if node:
            item['reported_node_tests'] = int(node[-1])
        if skips:
            item['reported_skips'] = int(skips[-1])
        parsed.append(item)
    return parsed


def matrix_read(content, override, source):
    if override:
        matrix = read_json(override)
        if matrix.get('source_revision') != source:
            raise ValueError('An external latest matrix must explicitly name the exact source revision')
        origin = 'Explicit source-bound owner-supplied latest matrix'
    else:
        if 'evidence/QUALIFICATION-MATRIX.json' not in content:
            raise ValueError('Customer archive has no qualification matrix')
        matrix = json.loads(content['evidence/QUALIFICATION-MATRIX.json'])
        if matrix.get('source_revision') not in {None, source}:
            raise ValueError('Packaged matrix identifies a different source')
        origin = 'Exact matrix embedded in the hash-verified customer archive; source identified by release manifest'
    rows = matrix.get('criteria')
    if not isinstance(rows, list) or any(not isinstance(r, dict) or r.get('status') not in STATUSES for r in rows):
        raise ValueError('Qualification matrix must use PASS / FAIL / BLOCKED / NOT TESTED')
    ids = [r.get('id') for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('Qualification matrix repeats a criterion')
    return matrix, origin


def copy_bytes(root, relative, data, mode=0o644):
    if not safe_path(relative):
        raise ValueError('Unsafe handoff path')
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    target.chmod(mode if mode in {0o644, 0o755} else 0o644)
    return relative


def escaped(value):
    return html.escape(str(value), quote=True)


def link(label, href):
    return '<a href="' + escaped(href) + '">' + escaped(label) + '</a>'


def assemble(args):
    if not SHA.fullmatch(args.source_sha):
        raise ValueError('Use the full 40-character final source commit')
    release_url = public_url(args.release_url)
    if not urlsplit(release_url).path.startswith(urlsplit(REPOSITORY).path + '/releases/tag/'):
        raise ValueError('Use the actual source-specific release-tag URL')
    if args.expected_sha256 and not DIGEST.fullmatch(args.expected_sha256):
        raise ValueError('Expected archive SHA-256 must be 64 lowercase hexadecimal characters')
    asset_dir = args.asset_dir.resolve(strict=True)
    if not asset_dir.is_dir():
        raise ValueError('Asset directory must exist')
    if args.customer_zip:
        archive = args.customer_zip.resolve(strict=True)
    else:
        matches = list(asset_dir.glob('ALPHA_GENESIS_HARNESS_*_source-bound_*.zip'))
        if len(matches) != 1:
            raise ValueError('Select exactly one downloaded customer ZIP with --customer-zip')
        archive = matches[0]
    selected_receipt = read_json(args.operation_receipt)
    expected_hash = args.expected_sha256 or selected_receipt.get('archive_sha256')
    if not isinstance(expected_hash, str) or not DIGEST.fullmatch(expected_hash):
        raise ValueError('A trustworthy external archive digest or source-bound operation receipt is required')
    raw, manifest, content, modes, archive_hash = archive_snapshot(archive, args.source_sha, expected_hash)
    operation, operation_view = operation_summary(args.operation_receipt, args.source_sha, archive_hash)
    matrix, matrix_origin = matrix_read(content, args.matrix, args.source_sha)
    version = str(manifest['version'])
    if not re.fullmatch(r'[0-9][A-Za-z0-9.-]{0,40}', version):
        raise ValueError('Unsafe version identifier')
    expected_release = REPOSITORY + f'/releases/tag/alpha-genesis-harness-v{version}-rc-{args.source_sha[:12]}'
    if release_url != expected_release:
        raise ValueError('Release tag must identify this candidate version and exact source prefix')
    model_evidence = None
    model_archive = getattr(args, 'model_evidence_archive', None)
    if model_archive is not None:
        model_archive = Path(model_archive).resolve(strict=True)
        model_evidence = model_evidence_snapshot(model_archive, args.source_sha, manifest['source_product_tree'])
    name = f'ALPHA_GENESIS_HARNESS_OWNER_HANDOFF_{version}_{args.source_sha[:12]}'
    output = args.output.resolve()
    folder = output / name
    if folder.exists() or (output / (name + '.zip')).exists():
        raise ValueError('Choose a new output directory; existing handoffs are not overwritten')
    folder.mkdir(parents=True)
    customer_zip_path = copy_bytes(folder, '01-CUSTOMER-DOWNLOAD/' + archive.name, raw)
    checksum_path = copy_bytes(folder, '01-CUSTOMER-DOWNLOAD/' + archive.name + '.sha256',
                              (archive_hash + '  ' + archive.name + '\n').encode())
    published_checksum = asset_dir / (archive.name + '.sha256')
    if published_checksum.is_file():
        text = published_checksum.read_text().strip()
        if not text.startswith(archive_hash + ' ') or archive.name not in text:
            raise ValueError('Downloaded checksum file does not match the selected customer archive')
        copy_bytes(folder, '05-VERIFICATION/PUBLISHED-CHECKSUM.txt', published_checksum.read_bytes())
    for rel, data in content.items():
        copy_bytes(folder, '02-EXPLORE-THE-EDITION/' + rel, data, modes[rel])
    docs = {'commercial/listing.md': '03-MANUAL-UPLOAD/BILINGUAL-PRODUCT-DESCRIPTIONS.md',
            'commercial/listing.json': '03-MANUAL-UPLOAD/LISTING-FIELD-MAP.json',
            'commercial/storefront-checklist.md': '03-MANUAL-UPLOAD/OWNER-MANUAL-UPLOAD-CHECKLIST.md',
            'docs/CHATGPT-COMMERCIAL-APPLICATION.md': '03-MANUAL-UPLOAD/CHATGPT-APPROVAL-MATERIALS.md'}
    for source, target in docs.items():
        if source in content:
            copy_bytes(folder, target, content[source])
    listing = content.get('commercial/listing.md', b'').decode('utf-8')
    if '## English' in listing and '## Français' in listing:
        en, fr = listing.split('## English', 1)[1].split('## Français', 1)
        copy_bytes(folder, '03-MANUAL-UPLOAD/PRODUCT-DESCRIPTION-EN.md', ('# English product copy\n' + en).encode())
        copy_bytes(folder, '03-MANUAL-UPLOAD/DESCRIPTION-PRODUIT-FR.md', ('# Description française\n' + fr).encode())
    copy_bytes(folder, '05-VERIFICATION/PUBLISHED-OPERATION.json', Path(args.operation_receipt).read_bytes())
    for index in range(1, len(operation_view['operations']) + 1):
        for suffix in ('stdout', 'stderr'):
            log = Path(args.operation_receipt).parent / f'operation-{index}.{suffix}.txt'
            if log.is_file() and not log.is_symlink() and log.stat().st_size < 5_000_000:
                copy_bytes(folder, '05-VERIFICATION/operation-logs/' + log.name, log.read_bytes())
    json_write(folder / '05-VERIFICATION/QUALIFICATION-MATRIX.json', matrix)
    json_write(folder / '05-VERIFICATION/OPERATION-SUMMARY.json', operation_view)
    operation_evidence = []
    for filename in ('WORKFLOW-DEMONSTRATION.json', 'STRATEGY-DEMONSTRATION.json',
                     'OMEGA-DEMONSTRATION.json', 'OMEGA-FRESH-SOURCE-FREEZE.json', 'OMEGA-FRESH-SUCCESSOR.json'):
        evidence_file = Path(args.operation_receipt).parent / filename
        if evidence_file.exists():
            if evidence_file.is_symlink() or not evidence_file.is_file() or evidence_file.stat().st_size > 30_000_000:
                raise ValueError('Unsafe published-operation evidence input')
            evidence_bytes = evidence_file.read_bytes()
            if not isinstance(parse_json(evidence_bytes), dict):
                raise ValueError('Published-operation evidence must contain a JSON record')
            evidence_path = copy_bytes(folder, '05-VERIFICATION/' + filename, evidence_bytes)
            operation_evidence.append({'path': evidence_path, 'sha256': digest(evidence_bytes)})
    model_evidence_view = None
    if model_evidence is not None:
        model_raw, model_manifest, model_files, model_hash = model_evidence
        model_zip_path = copy_bytes(folder, '05-VERIFICATION/' + model_archive.name, model_raw)
        model_manifest_path = copy_bytes(folder, '05-VERIFICATION/HOSTED-LOCAL-QUALIFICATION.json',
                                         model_files['HOSTED-LOCAL-QUALIFICATION.json'])
        model_evidence_view = {'archive': model_zip_path, 'archive_sha256': model_hash,
                               'archive_bytes': len(model_raw), 'manifest': model_manifest_path,
                               'recorded_status': model_manifest['status'],
                               'source_revision': model_manifest['source_revision'],
                               'source_product_tree': model_manifest['source_product_tree'],
                               'scope': 'Untouched downloaded model evidence; member hashes and source identities checked. Recorded outcomes are preserved, not promoted.'}
    screenshot_dirs = [asset_dir]
    if args.screenshots_dir:
        screenshot_dirs.insert(0, args.screenshots_dir.resolve(strict=True))
    screenshots = []
    screenshot_bindings = []
    browser_exports = []
    platforms = []
    browser = None
    for directory_index, directory in enumerate(screenshot_dirs, 1):
        candidate = None
        receipt = directory / 'BROWSER-VERIFICATION.json'
        if receipt.is_file() and not receipt.is_symlink():
            candidate = read_json(receipt)
            if candidate.get('source_revision') not in {None, args.source_sha}:
                raise ValueError('Screenshot receipt belongs to a different source revision')
            if browser is None or candidate.get('source_revision') == args.source_sha:
                browser = candidate
                copy_bytes(folder, '05-VERIFICATION/BROWSER-VERIFICATION.json', receipt.read_bytes())
            copy_bytes(folder, f'05-VERIFICATION/BROWSER-VERIFICATION-{directory_index}.json', receipt.read_bytes())
        platform_receipts = {}
        for platform_file in sorted(directory.glob('PLATFORM-*-VERIFICATION.json')):
            match = re.fullmatch(r'PLATFORM-([A-Za-z0-9_-]+)-VERIFICATION\.json', platform_file.name)
            if not match or platform_file.is_symlink():
                raise ValueError('Unsafe platform receipt input')
            platform_name = match.group(1)
            platform_record = read_json(platform_file)
            if (platform_record.get('source_revision') != args.source_sha
                    or platform_record.get('archive_sha256') != archive_hash):
                raise ValueError('Platform receipt must identify this source and exact customer archive')
            if platform_record.get('status') not in STATUSES:
                raise ValueError('Platform receipt has an unsupported status')
            platform_operations = operation_records(platform_record.get('operations', []), directory, platform_name + '-')
            if platform_record['status'] == 'PASS' and (not platform_operations or any(row['returncode'] != 0 for row in platform_operations)):
                raise ValueError('Platform PASS requires successful recorded operations')
            target = '05-VERIFICATION/' + platform_file.name
            if (folder / target).exists() and (folder / target).read_bytes() != platform_file.read_bytes():
                raise ValueError('Conflicting platform receipt filename')
            copy_bytes(folder, target, platform_file.read_bytes())
            platform_receipts[platform_name] = (platform_record, target)
            if not any(row['receipt'] == target for row in platforms):
                platforms.append({'platform': platform_name, 'status': platform_record['status'],
                                  'host': platform_record.get('host'), 'scope': platform_record.get('scope'),
                                  'operations': platform_operations, 'receipt': target})
            for index in range(1, len(platform_operations) + 1):
                for suffix in ('stdout', 'stderr'):
                    log = directory / f'{platform_name}-operation-{index}.{suffix}.txt'
                    if log.is_file() and not log.is_symlink() and log.stat().st_size < 5_000_000:
                        copy_bytes(folder, '05-VERIFICATION/operation-logs/' + log.name, log.read_bytes())
        for prefix, graphical in [('',candidate)] + [(name+'-',record) for name,(value,_target) in platform_receipts.items() for record in [value.get('browser_report')]]:
            if not graphical or not graphical.get('exports'):
                continue
            if graphical.get('source_revision') != args.source_sha or graphical.get('status') != 'PASS':
                raise ValueError('Browser exports require a successful matching-source receipt')
            for item in graphical['exports']:
                name = item.get('file')
                if not isinstance(name,str) or not safe_path(name) or '/' in name:
                    raise ValueError('Unsafe browser export filename')
                exported = directory/(prefix+name)
                if exported.is_symlink() or not exported.is_file() or not 0 < exported.stat().st_size <= 30_000_000:
                    raise ValueError('Missing or unsafe browser export file')
                data = exported.read_bytes()
                if type(item.get('bytes')) is not int or item['bytes'] != len(data) or digest(data) != item.get('sha256'):
                    raise ValueError('Browser export bytes differ from their receipt')
                target = '05-VERIFICATION/browser-exports/'+prefix+name
                if (folder/target).exists() and (folder/target).read_bytes() != data:
                    raise ValueError('Conflicting browser export filename')
                copy_bytes(folder,target,data)
                if not any(row['path']==target for row in browser_exports):
                    browser_exports.append({'path':target,'sha256':digest(data),'bytes':len(data)})
        for platform_name in platform_receipts:
            for suffix in ('stdout','stderr'):
                log = directory/f'{platform_name}-launcher.{suffix}.txt'
                if log.is_file() and not log.is_symlink() and log.stat().st_size < 5_000_000:
                    copy_bytes(folder,'05-VERIFICATION/operation-logs/'+log.name,log.read_bytes())
        candidates = sorted(set(directory.glob('HARNESS-*.png')) | set(directory.glob('*-HARNESS-*.png')))
        for image in candidates:
            if image.is_symlink() or image.stat().st_size > 20_000_000:
                raise ValueError('Unacceptable screenshot input')
            if not image.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Screenshot does not contain PNG bytes')
            target = '04-SCREENSHOTS/' + image.name
            image_receipt, image_receipt_path, receipt_image_name = candidate, (f'05-VERIFICATION/BROWSER-VERIFICATION-{directory_index}.json' if candidate else None), image.name
            platform_image = re.fullmatch(r'([A-Za-z0-9_-]+)-(HARNESS-.+\.png)', image.name)
            platform_pass = True
            if platform_image:
                platform_record, image_receipt_path = platform_receipts.get(platform_image.group(1), ({}, None))
                image_receipt = platform_record.get('browser_report')
                receipt_image_name = platform_image.group(2)
                platform_pass = platform_record.get('status') == 'PASS'
            binding = bool(platform_pass and image_receipt and image_receipt.get('source_revision') == args.source_sha
                           and image_receipt.get('status') == 'PASS'
                           and receipt_image_name in image_receipt.get('screenshots', []))
            screenshot_bindings.append({'path': target, 'source_receipt_associated': binding,
                                        'receipt': image_receipt_path})
            if target in screenshots:
                if (folder / target).read_bytes() != image.read_bytes():
                    raise ValueError('Conflicting screenshot filename')
                continue
            copy_bytes(folder, target, image.read_bytes())
            screenshots.append(target)
    screenshot_bound = bool(screenshots) and all(row['source_receipt_associated'] for row in screenshot_bindings)
    native_probe_receipts = []
    for directory in screenshot_dirs:
        probes = set(directory.glob('CODEX-HOST-VERIFICATION.json')) | set(directory.glob('*-CODEX-HOST-VERIFICATION.json'))
        for file in sorted(probes):
            if file.is_symlink() or not file.is_file() or file.stat().st_size >= 5_000_000:
                raise ValueError('Unsafe native Codex receipt input')
            if not re.fullmatch(r'(?:[A-Za-z0-9_-]+-)?CODEX-HOST-VERIFICATION\.json', file.name):
                raise ValueError('Unsafe native Codex receipt filename')
            probe = read_json(file)
            if not isinstance(probe, dict) or probe.get('status') not in STATUSES:
                raise ValueError('Invalid native Codex receipt')
            if (probe.get('source_revision') not in {None, args.source_sha}
                    or probe.get('archive_sha256') not in {None, archive_hash}):
                raise ValueError('Native Codex receipt belongs to another source or archive')
            target = '05-VERIFICATION/' + file.name
            if (folder / target).exists() and (folder / target).read_bytes() != file.read_bytes():
                raise ValueError('Conflicting native Codex receipt filename')
            copy_bytes(folder, target, file.read_bytes())
            if not any(row['receipt'] == target for row in native_probe_receipts):
                native_probe_receipts.append({'receipt': target, 'status': probe['status'],
                    'source_archive_bound': probe.get('source_revision') == args.source_sha
                        and probe.get('archive_sha256') == archive_hash})
            for suffix in ('stdout', 'stderr'):
                log = file.with_suffix('.' + suffix + '.txt')
                if log.is_file() and not log.is_symlink() and log.stat().st_size < 5_000_000:
                    log_target = '05-VERIFICATION/' + log.name
                    if (folder / log_target).exists() and (folder / log_target).read_bytes() != log.read_bytes():
                        raise ValueError('Conflicting native Codex diagnostic filename')
                    copy_bytes(folder, log_target, log.read_bytes())
    source_probe_receipts = []
    for name in ('FRONTIER-MONITOR-VERIFICATION.json','UPGRADE-FOUNDRY-HOST-VERIFICATION.json'):
        file = asset_dir/name
        if not file.exists():
            continue
        if file.is_symlink() or not file.is_file() or file.stat().st_size >= 5_000_000:
            raise ValueError('Unsafe extension probe receipt')
        record = read_json(file)
        if (record.get('source_revision') != args.source_sha or record.get('archive_sha256') != archive_hash
                or record.get('status') not in {'PASS','FAIL','BLOCKED'}):
            raise ValueError('Extension probe must identify this exact source and archive')
        target = copy_bytes(folder,'05-VERIFICATION/'+name,file.read_bytes())
        source_probe_receipts.append({'path':target,'status':record['status'],'sha256':digest(file.read_bytes())})
    rows = matrix['criteria']
    remaining = [r for r in rows if r['status'] != 'PASS']
    blocked = [r for r in rows if r['status'] == 'BLOCKED']
    counts = {s: sum(r['status'] == s for r in rows) for s in ['PASS', 'FAIL', 'BLOCKED', 'NOT TESTED']}
    items = [
        ('1', 'Customer application / Application client', '02-EXPLORE-THE-EDITION/app/index.html'),
        ('2', 'Source and build instructions / Source et compilation', '02-EXPLORE-THE-EDITION/docs/RELEASE.md'),
        ('3', 'Verified source installation package / Paquet source vérifié', customer_zip_path),
        ('4', 'START HERE / Démarrage', '02-EXPLORE-THE-EDITION/START-HERE.html'),
        ('5', 'English/French quick start / Démarrage bilingue', '02-EXPLORE-THE-EDITION/docs/QUICKSTART.md'),
        ('6', 'Frontier API connection guide / Connexion aux API', '02-EXPLORE-THE-EDITION/docs/PROVIDER-PROTOCOLS.md'),
        ('7', 'Local model guide / Modèles locaux', '02-EXPLORE-THE-EDITION/docs/MODEL-CONNECTIONS.md'),
        ('8', 'ChatGPT-plan guide / Forfait ChatGPT', '02-EXPLORE-THE-EDITION/docs/CHATGPT-PLAN.md'),
        ('9', 'Codex engineering guide / Ingénierie Codex', '02-EXPLORE-THE-EDITION/docs/CHATGPT-PLAN.md'),
        ('10', 'Advanced operator guide / Guide avancé', '02-EXPLORE-THE-EDITION/docs/OPERATOR.md'),
        ('11', 'GENESIS self-improvement example / Amélioration de GENESIS', '02-EXPLORE-THE-EDITION/docs/OMEGA-GENESIS-NEXT.md'),
        ('12', 'Additional examples / Exemples supplémentaires', '02-EXPLORE-THE-EDITION/examples/'),
        ('13', 'Scientific protocols and actual GENESIS evidence / Protocoles et preuves GENESIS', '05-VERIFICATION/OMEGA-DEMONSTRATION.json'),
        ('14', 'Actual screenshots and presentation assets / Captures et présentation', '04-SCREENSHOTS/'),
        ('15', 'Security, privacy and licences / Sécurité, confidentialité et licences', '02-EXPLORE-THE-EDITION/SECURITY.md'),
        ('16', 'Troubleshooting / Dépannage', '02-EXPLORE-THE-EDITION/docs/TROUBLESHOOTING.md'),
        ('17', 'Release notes and file manifest / Notes de version et manifeste', '02-EXPLORE-THE-EDITION/docs/RELEASE-NOTES.md'),
        ('18', 'SHA-256 checksums / Empreintes SHA-256', checksum_path),
        ('19', 'English/French commercial descriptions / Descriptions commerciales bilingues', '03-MANUAL-UPLOAD/BILINGUAL-PRODUCT-DESCRIPTIONS.md'),
        ('20', 'FAQ and purchase disclosures / FAQ et conditions d’achat', '02-EXPLORE-THE-EDITION/docs/FAQ.md'),
        ('21', 'Compatibility and platform scope / Compatibilité et plateformes', '02-EXPLORE-THE-EDITION/docs/INSTALLATION.md'),
        ('22', 'Final qualification matrix / Matrice de qualification finale', '05-VERIFICATION/QUALIFICATION-MATRIX.json'),
    ]
    required_paths = {
        '2': ['02-EXPLORE-THE-EDITION/scripts/package_release.py', '02-EXPLORE-THE-EDITION/README.md'],
        '3': ['02-EXPLORE-THE-EDITION/docs/INSTALLATION.md'],
        '6': ['02-EXPLORE-THE-EDITION/bridge/config.example.json'],
        '7': ['02-EXPLORE-THE-EDITION/bridge/config.local-only.example.json'],
        '8': ['03-MANUAL-UPLOAD/CHATGPT-APPROVAL-MATERIALS.md'],
        '10': ['02-EXPLORE-THE-EDITION/docs/FRONTIER-MONITOR.md'],
        '11': ['02-EXPLORE-THE-EDITION/bridge/genesis_next.py', '02-EXPLORE-THE-EDITION/scripts/qualify_genesis_successor.py',
               '02-EXPLORE-THE-EDITION/docs/UPGRADE-FOUNDRY.md','02-EXPLORE-THE-EDITION/bridge/upgrade_foundry.py'],
        '13': ['05-VERIFICATION/OMEGA-FRESH-SOURCE-FREEZE.json', '05-VERIFICATION/OMEGA-FRESH-SUCCESSOR.json',
               '02-EXPLORE-THE-EDITION/evidence/OMEGA-PROTOCOL.md', '02-EXPLORE-THE-EDITION/evidence/OMEGA-FRESH-SUCCESSOR-PROTOCOL.md'],
        '15': ['02-EXPLORE-THE-EDITION/docs/PRIVACY.md', '02-EXPLORE-THE-EDITION/LICENSE', '02-EXPLORE-THE-EDITION/THIRD-PARTY.json'],
        '17': ['02-EXPLORE-THE-EDITION/RELEASE-MANIFEST.json', '02-EXPLORE-THE-EDITION/VERSION.json'],
        '19': ['03-MANUAL-UPLOAD/PRODUCT-DESCRIPTION-EN.md', '03-MANUAL-UPLOAD/DESCRIPTION-PRODUIT-FR.md'],
        '20': ['02-EXPLORE-THE-EDITION/docs/EDITION.md'],
        '22': ['05-VERIFICATION/PUBLISHED-OPERATION.json'],
    }
    required_paths['13'].extend(row['path'] for row in browser_exports+source_probe_receipts)
    inventory = []
    for number, label, path in items:
        paths = [path] + required_paths.get(number, [])
        inventory.append({'id': number, 'deliverable': label, 'path': path, 'paths': paths,
                          'included': all((folder / entry).exists() for entry in paths)})
    identity = {'source_revision':args.source_sha, 'source_product_tree':manifest['source_product_tree'],
                'source_url':REPOSITORY + '/tree/' + args.source_sha + '/' + SOURCE_SCOPE,
                'release_url':release_url, 'archive_name':archive.name, 'archive_bytes':len(raw),
                'archive_sha256':archive_hash, 'version':version, 'release_status':manifest.get('release_status'),
                'package_status':'CANDIDATE_OWNER_HANDOFF', 'commercially_ready':False,
                'matrix_origin':matrix_origin, 'matrix_status_counts':counts,
                'published_archive_operation':operation_view, 'screenshots_source_bound':screenshot_bound,
                'screenshot_receipt_associations': screenshot_bindings,
                'platform_qualifications': platforms,
                'native_codex_probe_receipts': native_probe_receipts,
                'model_evidence_archive': model_evidence_view,
                'published_operation_evidence': operation_evidence,
                'browser_exports':browser_exports, 'source_probe_receipts':source_probe_receipts,
                'squarespace_activity':'NONE; explicitly reserved to Vincent',
                'required_deliverables':inventory, 'remaining_criteria':remaining,
                'scope':'The customer ZIP is copied byte-for-byte. The expanded copy is for owner inspection. This bundle does not certify live access or promote candidate/commercial status.'}
    identity['publication_provenance'] = 'Release URL and downloaded files are supplied by the operator after the trusted publication/download step. This offline assembler verifies their internal source/hash agreement; it does not independently authenticate GitHub or fetch the release.'
    if args.pull_request_url:
        identity['pull_request_url'] = public_url(args.pull_request_url)
    json_write(folder / 'OWNER-HANDOFF.json', identity)
    render_html(folder, identity, rows, items, screenshots, browser)
    lines = ['ALPHA GENESIS FLYWHEEL OMEGA HARNESS — OWNER HANDOFF', '',
             'Open 00-OWNER-START.html first. / Ouvrez d’abord 00-OWNER-START.html.', '',
             'This is an engineering release candidate, not a fully qualified commercial edition.',
             'Cette édition reste candidate; elle n’est pas une édition commerciale entièrement qualifiée.', '',
             'Only the exact customer ZIP inside 01-CUSTOMER-DOWNLOAD is the future storefront upload.',
             'Do not upload this owner bundle. Squarespace remains entirely under Vincent’s control.',
             'Seul le ZIP client du dossier 01 est destiné au chargement futur. Ne chargez pas ce dossier propriétaire.', '',
             'Customer archive: ' + archive.name, 'Bytes: ' + str(len(raw)), 'SHA-256: ' + archive_hash,
             'Source: ' + args.source_sha, 'Release: ' + release_url, '',
             'Review every BLOCKED, FAIL and NOT TESTED criterion before making commercial claims.']
    (folder / 'README-OWNER.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    file_records=[]
    for file in sorted(folder.rglob('*')):
        if file.is_file():
            file_records.append({'path':file.relative_to(folder).as_posix(),'bytes':file.stat().st_size,'sha256':digest(file.read_bytes())})
    json_write(folder / 'OWNER-FILE-MANIFEST.json', {'schema':'alpha-harness-owner-manifest/v1','source_revision':args.source_sha,'customer_archive_sha256':archive_hash,'files':file_records,'self_excluded':True})
    owner_zip=output/(name+'.zip')
    with zipfile.ZipFile(owner_zip,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as bundle:
        for file in sorted(folder.rglob('*')):
            if not file.is_file():
                continue
            info=zipfile.ZipInfo(name+'/'+file.relative_to(folder).as_posix(),date_time=(2026,1,1,0,0,0))
            info.create_system=3;info.external_attr=(0o100000|(file.stat().st_mode&0o777))<<16
            info.compress_type=zipfile.ZIP_DEFLATED
            bundle.writestr(info,file.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    result={'owner_directory':str(folder),'owner_zip':str(owner_zip),'owner_zip_bytes':owner_zip.stat().st_size,
            'owner_zip_sha256':digest(owner_zip.read_bytes()),'customer_archive_sha256':archive_hash,
            'customer_archive_bytes':len(raw),'source_revision':args.source_sha,
            'commercially_ready':False,'included_deliverable_types':sum(i['included'] for i in inventory),
            'expected_deliverable_types':len(items),'published_operation_status':operation_view['status']}
    owner_zip.with_suffix('.zip.sha256').write_text(result['owner_zip_sha256']+'  '+owner_zip.name+'\n')
    json_write(output/(name+'.receipt.json'),result)
    return result


def render_html(folder, identity, rows, items, screenshots, browser):
    esc=escaped
    badges=lambda status:'<span class="badge '+status.lower().replace(' ','-')+'">'+esc(status)+'</span>'
    remaining=[r for r in rows if r['status']!='PASS']
    source_link=link(identity['source_revision'][:12],identity['source_url'])
    release_link=link('Open the exact published release ↗',identity['release_url'])
    operation=identity['published_archive_operation']
    row_html=''.join('<tr><td>'+esc(r['id'])+'</td><td><strong>'+esc(r['requirement'])+'</strong><p>'+esc(r.get('actual_test_or_required_procedure',''))+'</p></td><td>'+badges(r['status'])+'</td><td>'+esc(r.get('remaining_dependency_or_scope',''))+'<div class="evidence">'+esc(r.get('evidence_location',''))+'</div></td></tr>' for r in rows)
    file_html=''.join('<tr><td>'+esc(row['id'])+'</td><td>'+link(row['deliverable'],row['path'])
                      + ''.join('<p>'+link(Path(path).name,path)+'</p>' for path in row['paths'][1:])
                      + '</td><td>'+('Included / Inclus' if row['included'] else '<strong class="missing">MISSING / ABSENT</strong>')+'</td></tr>'
                      for row in identity['required_deliverables'])
    ops=''.join('<li><code>'+esc(' '.join(map(str,r.get('command') or [])))+'</code><span class="opresult">Exit '+esc(r.get('returncode'))+'</span>'+(' · '+esc(r['reported_python_tests'])+' Python tests' if 'reported_python_tests' in r else '')+(' · '+esc(r['reported_node_tests'])+' Node tests' if 'reported_node_tests' in r else '')+(' · '+esc(r['reported_skips'])+' reported skip(s)' if 'reported_skips' in r else '')+'</li>' for r in operation['operations'])
    gaps=''.join('<li>'+badges(r['status'])+' <strong>'+esc(r['requirement'])+'</strong><p>'+esc(r.get('remaining_dependency_or_scope',''))+'</p></li>' for r in remaining)
    models=''.join('<tr><td>'+esc(r['requirement'])+'</td><td>'+badges(r['status'])+'</td><td>'+esc(r.get('remaining_dependency_or_scope',''))+'</td></tr>' for r in rows if str(r['id']).startswith('B'))
    platform_rows=''.join('<tr><td><strong>'+esc(row['platform'])+'</strong><p>'+esc(row.get('host',''))+'</p></td><td>'+badges(row['status'])+'</td><td>'+esc(row.get('scope',''))+'<p>'+link('Read this platform receipt',row['receipt'])+'</p>'+''.join('<p>'+esc(op['reported_node_tests'])+' Node tests executed on this platform</p>' for op in row['operations'] if 'reported_node_tests' in op)+'</td></tr>' for row in identity.get('platform_qualifications', []))
    if not platform_rows:
        platform_rows='<tr><td colspan="3">No source/hash-matched platform receipts supplied. / Aucun rapport de plateforme correspondant à cette source et à cette empreinte n’a été fourni.</td></tr>'
    gallery=''.join('<figure><a href="'+esc(path)+'"><img src="'+esc(path)+'" alt="'+esc(Path(path).stem.replace('-',' '))+'" loading="lazy"></a><figcaption>'+esc(Path(path).name)+'</figcaption></figure>' for path in screenshots)
    if not gallery:
        gallery='<p class="missing">No screenshots supplied. / Aucune capture fournie.</p>'
    screenshot_scope=('Each image is named by a matching-source graphical receipt.' if identity['screenshots_source_bound'] else 'Screenshot source association is not fully established; do not present the entire gallery as exact-source graphical qualification.')
    if browser:
        screenshot_scope+=' '+str(browser.get('scope',''))
    model_evidence = identity.get('model_evidence_archive')
    model_links = ''
    if model_evidence:
        model_links = ('<p>' + link('Download the unchanged model-evidence ZIP / Télécharger les preuves modèles', model_evidence['archive'])
                       + ' · ' + link('Read the model-evidence manifest', model_evidence['manifest'])
                       + '</p><p class="small">Recorded outcome: ' + esc(model_evidence['recorded_status'])
                       + '. Source and file hashes verified; this does not promote any qualification or commercial status.</p>')
    counts=''.join('<div><strong>'+str(identity['matrix_status_counts'][s])+'</strong><span>'+esc(s)+'</span></div>' for s in ['PASS','FAIL','BLOCKED','NOT TESTED'])
    document='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Owner handoff · ALPHA GENESIS HARNESS</title><style>
:root{--ink:#142338;--muted:#526276;--line:#d8e1ea;--paper:#f4f6f8;--gold:#d9bb72;--night:#0d1b2c;--green:#176b4b;--amber:#865b09;--red:#ae2431}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}header{background:linear-gradient(130deg,#0d1b2c,#233d53);color:#f7f3e9;padding:64px max(24px,calc((100vw - 1160px)/2)) 45px}.brand{font-size:12px;letter-spacing:.17em;color:#dfc88e;font-weight:750}h1{font-size:clamp(32px,4vw,54px);line-height:1.08;letter-spacing:-.035em;margin:18px 0}header p{color:#d6e0e8;max-width:820px}.kicker{display:inline-block;background:#493c20;border:1px solid #8e7843;border-radius:30px;padding:5px 13px;font-size:12px;margin-top:20px}.intro{font-size:20px}main{max-width:1208px;margin:auto;padding:32px 24px 60px}nav{display:flex;flex-wrap:wrap;gap:10px 25px;border-bottom:1px solid var(--line);padding-bottom:22px;margin-bottom:24px}a{color:#155b80;text-underline-offset:3px}a:focus-visible{outline:3px solid #bd8726;outline-offset:4px}header a{color:#f1dca8}h2{font-size:29px;line-height:1.2;letter-spacing:-.02em;margin:0 0 20px}h3{font-size:19px;margin:0 0 12px}section{margin:24px 0;padding:30px;background:white;border:1px solid var(--line);border-radius:16px;scroll-margin-top:20px}.leadbox{border-left:5px solid var(--gold);background:#fffdf7}.columns{display:grid;grid-template-columns:1fr 1fr;gap:26px}.button{display:inline-block;background:var(--gold);color:#172231;padding:12px 19px;border-radius:8px;text-decoration:none;font-weight:750;margin:6px 12px 6px 0}.secondary{background:#e8eef3}.muted,.evidence{color:var(--muted)}.small{font-size:13px}.evidence{font-size:12px;margin-top:10px;overflow-wrap:anywhere}.identity{display:grid;grid-template-columns:150px minmax(0,1fr);gap:8px 15px;margin:20px 0}.identity dt{font-weight:700}.identity dd{margin:0;overflow-wrap:anywhere}code{font:13px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;background:#eff3f7;padding:3px 6px;border-radius:4px;overflow-wrap:anywhere}.hash{display:block;padding:14px;background:#eff3f7;word-break:break-all}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:20px 0}.stats div{padding:16px;background:#f3f6f9;border-radius:10px}.stats strong{display:block;font-size:31px;line-height:1.2}.stats span{font-size:11px;letter-spacing:.08em;color:var(--muted)}.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px}th{text-align:left;font-size:11px;letter-spacing:.07em;text-transform:uppercase;color:var(--muted);background:#f0f4f7}th,td{padding:14px 12px;border-bottom:1px solid var(--line);vertical-align:top}td p{font-size:13px;color:var(--muted);margin:8px 0 0}.badge{display:inline-block;padding:3px 8px;border-radius:5px;white-space:nowrap;font-size:10px;font-weight:800;letter-spacing:.03em;background:#e6edf3;color:#3e5265}.pass{background:#e2f1e9;color:var(--green)}.fail{background:#fbe4e6;color:var(--red)}.blocked{background:#fff1d7;color:var(--amber)}.not-tested{background:#e9edf2;color:#526276}.missing{color:var(--red)}ul{padding-left:22px}.gaps li{margin:18px 0}.gaps p{margin:7px 0}.operation li{margin:12px 0;line-height:1.8}.opresult{margin-left:10px;font-size:12px;font-weight:750}.gallery{display:grid;grid-template-columns:1fr 1fr;gap:22px}figure{margin:0;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#f1f4f7}figure img{display:block;width:100%;height:auto}figcaption{padding:10px 14px;color:var(--muted);font-size:12px}.lang{font-size:11px;letter-spacing:.13em;font-weight:750;color:#7b6125;text-transform:uppercase}footer{font-size:12px;color:var(--muted);padding:0 10px}.stamp{padding:15px;background:#fff4df;border-radius:8px}details{border:1px solid var(--line);padding:16px;border-radius:10px;margin:16px 0}summary{font-weight:750;cursor:pointer}@media(max-width:720px){header{padding-top:36px}.columns,.gallery{grid-template-columns:1fr}section{padding:22px 18px}.stats{grid-template-columns:repeat(2,1fr)}.identity{grid-template-columns:1fr;gap:3px}.identity dd{margin-bottom:10px}.button{display:block;text-align:center}.intro{font-size:18px}}@media print{header{background:white;color:var(--ink);padding:20px}header p,header a{color:var(--ink)}main{padding:0}section{break-inside:avoid}nav{display:none}a{color:var(--ink)}.gallery{grid-template-columns:1fr 1fr}}
</style></head><body>'''
    document+='<header><div class="brand">ALPHA GENESIS FLYWHEEL Ω · HARNESS</div><div class="kicker">OWNER HANDOFF · REMISE AU PROPRIÉTAIRE</div><h1>The verified files.<br>The evidence. The next decision.</h1><p class="intro">An organized handoff for Vincent Boucher · MONTREAL.AI / QUEBEC.AI</p><p>Version '+esc(identity['version'])+' · Engineering release candidate. This handoff preserves the exact customer download and states the remaining qualification dependencies.</p><p lang="fr">Version candidate : les fichiers clients exacts, leurs preuves et les dépendances restantes sont réunis ici. Aucune activation commerciale n’est effectuée.</p></header>'
    document+='<main><nav aria-label="Handoff sections"><a href="#start">Start here</a><a href="#identity">Exact download</a><a href="#models">Model access</a><a href="#platforms">Platforms</a><a href="#files">22 deliverables</a><a href="#verification">Verification</a><a href="#screenshots">Screenshots</a><a href="#remaining">Remaining dependencies</a><a href="#upload">Manual upload</a></nav>'
    document+='<section id="start" class="leadbox"><div class="columns"><div><div class="lang">English</div><h2>Review the edition before upload.</h2><p><strong>This is a release candidate, not a declaration that the full commercial mandate is complete.</strong> The source-bound package and the published operation receipt are separate from live-provider access, commercial authorization and broader invention claims.</p>'+link('Open the customer START HERE →','02-EXPLORE-THE-EDITION/START-HERE.html').replace('<a ','<a class="button" ',1)+'<p class="small muted">The expanded copy is provided for inspection. The untouched ZIP in folder 01 is the only future storefront upload.</p></div><div lang="fr"><div class="lang">Français</div><h2>Examinez l’édition avant le chargement.</h2><p><strong>Cette version candidate ne constitue pas une déclaration de réalisation commerciale complète.</strong> Les tests du paquet restent distincts des accès réels, autorisations commerciales et preuves d’invention.</p><p>La copie décompressée sert à l’examen. Seul le ZIP client intact du dossier 01 est destiné au chargement futur. Squarespace demeure entièrement sous votre contrôle.</p></div></div></section>'
    document+='<section id="identity"><h2>Exact customer download / Téléchargement exact</h2><dl class="identity"><dt>Archive</dt><dd>'+link(identity['archive_name'],'01-CUSTOMER-DOWNLOAD/'+identity['archive_name'])+'</dd><dt>Size / Taille</dt><dd>'+format(identity['archive_bytes'],',')+' bytes · '+format(identity['archive_bytes']/1_000_000,'.3f')+' MB (decimal)</dd><dt>Source commit</dt><dd>'+source_link+'<br><code>'+esc(identity['source_revision'])+'</code></dd><dt>Publication</dt><dd>'+release_link+'</dd><dt>Price / Prix</dt><dd>CAD $299 · one-time / paiement unique · intended Official Edition</dd></dl><strong>SHA-256</strong><code class="hash">'+esc(identity['archive_sha256'])+'</code><p class="small muted">The archive is copied byte-for-byte from the supplied downloaded release assets and matched to the selected digest and operation receipt. No network request is made by this assembler.</p><p class="small muted">'+esc(identity.get('publication_provenance',''))+'</p></section>'
    document+='<section id="models"><h2>Model access / Accès aux modèles</h2><div class="table-wrap"><table><thead><tr><th>Requirement</th><th>Status</th><th>Actual scope and dependency</th></tr></thead><tbody>'+models+'</tbody></table></div><p class="small">Protocol fixtures are not live authentication. Local execution does not validate all servers or models. ChatGPT-plan allowance, API billing, Codex usage and local compute remain distinct.</p></section>'
    document+='<section id="platforms"><h2>Actual platform executions / Exécutions par système</h2><div class="table-wrap"><table><thead><tr><th>Host platform</th><th>Status</th><th>Recorded scope</th></tr></thead><tbody>'+platform_rows+'</tbody></table></div><p class="small">These receipts identify the same customer archive and source. Repeated JavaScript tests are per-platform executions; their counts are not added as unique tests. Read the explicit limits for authentication, security suites, native installers and desktop double-click.</p><p class="small" lang="fr">Les rapports identifient le même ZIP et la même source. Les répétitions de tests JavaScript sont indiquées par système, sans addition en tant que tests uniques. Les limites de chaque rapport restent applicables.</p></section>'
    document+='<section id="files"><h2>All 22 delivery categories / Les 22 catégories</h2><p>The exact source package supplies the application, documents, examples and source. The owner materials identify the upload and approval steps without performing them.</p><div class="table-wrap"><table><thead><tr><th>#</th><th>Open the deliverable</th><th>Inventory</th></tr></thead><tbody>'+file_html+'</tbody></table></div><p>'+link('Apache 2.0 licence','02-EXPLORE-THE-EDITION/LICENSE')+' · '+link('Security boundaries','02-EXPLORE-THE-EDITION/SECURITY.md')+' · '+link('Purchase scope','02-EXPLORE-THE-EDITION/docs/EDITION.md')+' · '+link('Commercial approval materials','03-MANUAL-UPLOAD/CHATGPT-APPROVAL-MATERIALS.md')+'</p></section>'
    document+='<section id="verification"><h2>Verification / Vérification</h2><p>Published-archive operation: '+badges(operation['status'])+'</p><p class="muted">'+esc(operation.get('scope',''))+'</p><p><strong>DOM/HTTP:</strong> '+esc(operation.get('dom_qualification',''))+'</p><details><summary>Executed commands and recorded counts</summary><ul class="operation">'+ops+'</ul></details><p class="small">Counts appear only when present in the actual operation logs. An absent count is not replaced with an earlier release’s total.</p><div class="stats">'+counts+'</div><p>'+esc(identity['matrix_origin'])+'. This matrix is preserved as supplied; operation evidence does not silently promote unrelated criteria.</p><div class="table-wrap"><table><thead><tr><th>ID</th><th>Requirement and test</th><th>Status</th><th>Scope, evidence and remaining dependency</th></tr></thead><tbody>'+row_html+'</tbody></table></div><p>'+link('Machine-readable matrix','05-VERIFICATION/QUALIFICATION-MATRIX.json')+' · '+link('Published operation receipt','05-VERIFICATION/PUBLISHED-OPERATION.json')+' · '+link('Complete handoff identity','OWNER-HANDOFF.json')+'</p></section>'
    document+='<section id="screenshots"><h2>Actual screenshots / Captures de l’application</h2><p class="muted">'+esc(screenshot_scope)+'</p><div class="gallery">'+gallery+'</div><p class="small">Images retain their original aspect ratios. A screenshot is a visual record, not proof of authenticated model access or full accessibility conformance.</p></section>'
    document+='<section id="remaining"><h2>Remaining dependencies / Dépendances restantes</h2><ul class="gaps">'+(gaps or '<li>No non-PASS matrix rows were supplied. Candidate status is still preserved; no new commercial authorization is inferred.</li>')+'</ul><p lang="fr">Chaque blocage et chaque essai non effectué reste explicite. Les réponses préparées ne prouvent pas une connexion réelle; une autorisation open source ne constitue pas une autorisation commerciale.</p></section>'
    document+='<section id="upload" class="leadbox"><h2>Your final manual action / Votre action finale</h2><p class="stamp"><strong>Do not upload this owner bundle.</strong> After the stated release blockers are resolved and you decide to activate the qualified edition, upload only <code>'+esc(identity['archive_name'])+'</code> from <strong>01-CUSTOMER-DOWNLOAD</strong>.</p><p>Use the English/French descriptions and actual screenshots. Confirm the intended CAD $299 one-time price, your merchant contact and applicable checkout disclosures. Keep the exact archive and checksum for your records. The supplied checklist is guidance for your own manual action.</p><p lang="fr"><strong>Ne chargez pas ce dossier propriétaire.</strong> Après résolution des blocages et votre décision d’activer l’édition qualifiée, chargez uniquement le ZIP client du dossier 01. Utilisez les descriptions bilingues, les captures réelles et vos conditions marchandes. Conservez l’archive et son empreinte.</p><p><strong>Squarespace activity performed by this handoff: none.</strong> No login, listing edit, upload, checkout action, purchase or publication.</p>'+link('Open the manual upload checklist →','03-MANUAL-UPLOAD/OWNER-MANUAL-UPLOAD-CHECKLIST.md').replace('<a ','<a class="button secondary" ',1)+'</section>'
    document+='<footer>© 2026 Vincent Boucher · MONTREAL.AI / QUEBEC.AI. No provider endorsement is implied. This owner bundle is an evidence-bound review package; customer licence terms remain in the exact edition.</footer></main></body></html>'
    document = document.replace('<section id="verification"><h2>Verification / Vérification</h2>',
                                '<section id="verification"><h2>Verification / Vérification</h2>' + model_links, 1)
    (folder/'00-OWNER-START.html').write_text(document,encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-sha',required=True)
    parser.add_argument('--release-url',required=True)
    parser.add_argument('--asset-dir',type=Path,required=True)
    parser.add_argument('--operation-receipt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--customer-zip',type=Path)
    parser.add_argument('--model-evidence-archive',type=Path,help='Untouched published public-model evidence ZIP with an exact source/tree-bound manifest')
    parser.add_argument('--expected-sha256')
    parser.add_argument('--matrix',type=Path,help='Optional latest matrix; must explicitly name --source-sha')
    parser.add_argument('--screenshots-dir',type=Path,help='Optional additional actual HARNESS PNGs and BROWSER-VERIFICATION.json')
    parser.add_argument('--pull-request-url')
    args=parser.parse_args()
    try:
        print(json.dumps(assemble(args),ensure_ascii=False,indent=2))
    except (ValueError,KeyError,TypeError,OSError,zipfile.BadZipFile,json.JSONDecodeError) as error:
        print(json.dumps({'status':'REFUSED','error':str(error)},ensure_ascii=False),file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
