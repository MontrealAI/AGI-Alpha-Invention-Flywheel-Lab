"""Restore a small, source-bound evidence packet from an indexed public ZIP."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
from time import monotonic, process_time
from urllib.request import Request, build_opener
from zipfile import ZIP_STORED, ZipFile


from frontier_public_watch import NoRedirect, SITE, fetch, unique_object


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / 'publication/prove-advantage/research-activation/positive-advancement/PACKETS.json'
ARCHIVE_PINS = {
    'ACT15': ('frontier-activation-1.5.0.zip', '5a29bc8d215895216201b85dcf6f5af6709d0ecea857792cf24b3cc4d20ec791'),
    'INV10': ('frontier-inventor-1.0.0.zip', '7eb4759ffb168b6cc46504c92aa3dcc7c4d40914cb122d6b3ba36327aa90534d'),
}
SOURCE_HASHES = {
    'ACT15': {
        'evidence_control.py': 'dc0392e6ff2423c120873630347b33d0bf184b3bd7435dc6f8af2651ab3313e5',
        'study/factory/EVIDENCE.json': '62bdbfd8998a4b099534db8423ffd9b7aaf22ef4a08de35702d0aa378207f033',
    },
    'INV10': {
        'relational.py': '48d0ab154a4fd5d09f8edc7b65dbcb916c7967d68c78901bdeb3c949a534084d',
        'study/reproduction.json': '37cae3850b058f44917503a6ab63b8832e6e123ca6ef627e70db5be0a06fa88b',
        'study/evidence.json': 'fdac418e43ee6495c4f230564bbd547eba762c22d61556254a1158ba3c48fb1b',
    },
}
ARCHIVE = re.compile(r'frontier-(?:activation|inventor)-[0-9]+\.[0-9]+\.[0-9]+\.zip\Z')
MEMBER = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,179}\Z', re.ASCII)
SHA256 = re.compile(r'[0-9a-f]{64}\Z')
ETAG = re.compile(r'"[!#-~]{1,160}"\Z', re.ASCII)
MAX_ARCHIVE_BYTES = 3_000_000
LOCAL_HEADER = struct.Struct('<4s5H3I2H')


def fingerprint(data):
    return sha256(data).hexdigest()


def check_member_name(name):
    if (not isinstance(name, str) or not MEMBER.fullmatch(name)
            or str(PurePosixPath(name)) != name or any(x in {'.', '..'} for x in name.split('/'))):
        raise ValueError('Invalid evidence member path.')


def index_archive(raw, archive, expected_sha256, selected):
    """Bind selected plain member extents to an independently identified archive and sources."""
    if (not isinstance(archive, str) or not ARCHIVE.fullmatch(archive)
            or not 0 < len(raw) <= MAX_ARCHIVE_BYTES or fingerprint(raw) != expected_sha256):
        raise ValueError('Unexpected public archive bytes or identity.')
    with ZipFile(BytesIO(raw)) as opened:
        members = opened.namelist()
        if len(members) != len(set(members)):
            raise ValueError('Duplicate ZIP member name.')
        entries = {}
        for name, digest in selected.items():
            check_member_name(name)
            location = opened.getinfo(name)
            if (location.is_dir() or location.compress_type != ZIP_STORED
                    or not 0 < location.file_size == location.compress_size <= MAX_ARCHIVE_BYTES):
                raise ValueError('Evidence members must be nonempty stored ZIP entries.')
            data = opened.read(location)
            if fingerprint(data) != digest:
                raise ValueError('Evidence member differs from its independently pinned source.')
            header = LOCAL_HEADER.unpack_from(raw, location.header_offset)
            if header[0] != b'PK\x03\x04':
                raise ValueError('Invalid ZIP record.')
            start = location.header_offset + LOCAL_HEADER.size + sum(header[-2:])
            end = start + len(data)
            if raw[start:end] != data:
                raise ValueError('The indexed extent differs from the ZIP member.')
            entries[name] = {'start': start, 'end': end, 'sha256': digest}
    packet = {'archive': archive, 'archive_sha256': expected_sha256, 'archive_bytes': len(raw), 'members': entries}
    validate(packet)
    return packet


def validate(packet):
    if (not ARCHIVE.fullmatch(packet['archive']) or not SHA256.fullmatch(packet['archive_sha256'])
            or type(packet['archive_bytes']) is not int or not 0 < packet['archive_bytes'] <= MAX_ARCHIVE_BYTES
            or not isinstance(packet['members'], dict) or not packet['members']):
        raise ValueError('Unrecognized source-bound evidence contract.')
    for name, row in packet['members'].items():
        check_member_name(name)
        start, end = row['start'], row['end']
        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= packet['archive_bytes']
                or not SHA256.fullmatch(row['sha256'])):
            raise ValueError('Evidence extent lies outside its archive or lacks a source digest.')


def verify_contract(case, packet):
    validate(packet)
    identity = packet['archive'], packet['archive_sha256']
    members = {name: row['sha256'] for name, row in packet['members'].items()}
    if identity != ARCHIVE_PINS[case] or members != SOURCE_HASHES[case]:
        raise ValueError('The index differs from the exact reviewed packet contract.')


def plan(extents, limit):
    if type(limit) is not int or limit not in range(1, 9):
        raise ValueError('Choose between one and eight range reads.')
    components = []
    for start, end in sorted(extents):
        if not 0 <= start < end:
            raise ValueError('An evidence extent must be nonempty.')
        if components and start <= components[-1][1]:
            left, right = components[-1]
            components[-1] = left, max(right, end)
        else:
            components.append((start, end))
    if not components:
        return []
    gaps = [(right[0] - left[1], i) for i, (left, right) in enumerate(zip(components, components[1:]))]
    cuts = {i for _, i in sorted(gaps, reverse=True)[:limit - 1]}
    start = components[0][0]
    result = []
    for i, (_, end) in enumerate(components):
        if i in cuts:
            result.append((start, end))
            start = components[i + 1][0]
    result.append((start, components[-1][1]))
    return result


def download_range(packet, start, end):
    url = SITE + packet['archive']
    headers = {'Range': f'bytes={start}-{end - 1}', 'Accept-Encoding': 'identity',
               'Cache-Control': 'no-cache', 'User-Agent': 'Frontier-Verified-Evidence/1.0'}
    with build_opener(NoRedirect()).open(Request(url, headers=headers), timeout=18) as response:
        expected = f'bytes {start}-{end - 1}/{packet["archive_bytes"]}'
        etag = response.headers.get('ETag', '')
        fields = ('ETag', 'Content-Range', 'Content-Encoding', 'Content-Length')
        if (response.status != 206 or response.url != url or response.headers.get('Content-Range') != expected
                or response.headers.get('Content-Encoding', 'identity') != 'identity' or not ETAG.fullmatch(etag)
                or response.headers.get('Content-Length', str(end - start)) != str(end - start)
                or any(len(response.headers.get_all(field, [])) > 1 for field in fields)):
            raise ValueError('The range reply does not bind the unchanged public archive representation.')
        body = response.read(end - start + 1)
    if len(body) != end - start:
        raise ValueError('Incomplete archive range.')
    return body, etag


def restore(packet, limit, request=download_range):
    validate(packet)
    tick = monotonic()
    cpu = process_time()
    extents = [(row['start'], row['end']) for row in packet['members'].values()]
    intervals = plan(extents, limit)
    with ThreadPoolExecutor(max_workers=min(4, len(intervals))) as readers:
        replies = list(readers.map(lambda extent: request(packet, *extent), intervals))
    tags = {etag for _, etag in replies}
    if len(tags) != 1 or not ETAG.fullmatch(next(iter(tags))):
        raise ValueError('The archive representation changed between range responses.')
    etag, = tags
    bodies = {extent: body for extent, (body, _) in zip(intervals, replies, strict=True)}
    if any(len(body) != end - start for (start, end), body in bodies.items()):
        raise ValueError('Incomplete archive range.')
    output = {}
    for name, row in packet['members'].items():
        start, end = row['start'], row['end']
        left, right = next(i for i in intervals if i[0] <= start < end <= i[1])
        raw = bodies[left, right][start - left:end - left]
        if len(raw) != end - start or fingerprint(raw) != row['sha256']:
            raise ValueError('Recovered evidence does not match the independently pinned member.')
        output[name] = raw
    receipt = {'archive': packet['archive'], 'indexed_archive_sha256': packet['archive_sha256'],
               'source': SITE + packet['archive'], 'archive_bytes': packet['archive_bytes'],
               'range_requests': len(intervals), 'response_body_bytes': sum(map(len, bodies.values())),
               'verified_files': {name: fingerprint(data) for name, data in output.items()},
               'ranges': intervals, 'etag': etag,
               'wall_seconds': round(monotonic() - tick, 6), 'cpu_seconds': round(process_time() - cpu, 6)}
    return output, receipt


def full_archive(packet):
    validate(packet)
    started, cpu = monotonic(), process_time()
    raw = fetch(SITE + packet['archive'], packet['archive_bytes'])
    check = index_archive(raw, packet['archive'], packet['archive_sha256'],
                          {name: entry['sha256'] for name, entry in packet['members'].items()})
    if check != packet:
        raise ValueError('The live archive differs from the retained research index.')
    with ZipFile(BytesIO(raw)) as opened:
        output = {name: opened.read(name) for name in packet['members']}
    return output, {'archive': packet['archive'], 'requests': 1, 'response_body_bytes': len(raw),
                    'wall_seconds': round(monotonic() - started, 6), 'cpu_seconds': round(process_time() - cpu, 6),
                    'verified_files': {name: fingerprint(data) for name, data in output.items()}}


def restore_into(case, directory, read_limit=2):
    index = json.loads(INDEX.read_bytes(), object_pairs_hook=unique_object)
    if index['schema'] != 'frontier/verified-evidence-packets-v1' or set(index['packets']) != set(SOURCE_HASHES):
        raise ValueError('Unexpected evidence index schema.')
    packet = index['packets'][case]
    verify_contract(case, packet)
    parent = directory.parent.resolve(strict=True)
    if os.name == 'posix':
        for ancestor in (parent, *parent.parents):
            info = ancestor.stat()
            if (info.st_uid not in {0, os.getuid()}
                    or info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX):
                raise ValueError('Choose a new destination under trusted, protected parent directories.')
    directory = parent / directory.name
    if os.path.lexists(directory):
        raise FileExistsError('Choose an unused evidence destination.')
    files, receipt = restore(packet, read_limit)
    directory.mkdir(mode=0o700)
    for name, body in files.items():
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(body)
    pending = directory / 'receipt.json.pending'
    with pending.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, indent=2)
        stream.write('\n')
    pending.replace(directory / 'receipt.json')
    return receipt
