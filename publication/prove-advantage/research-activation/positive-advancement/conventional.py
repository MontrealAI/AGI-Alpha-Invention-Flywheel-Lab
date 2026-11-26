"""Read-only conventional download and exact range controls for two FRONTIER releases."""

from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from struct import unpack_from
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, process_time
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import ZIP_STORED, ZipFile


SITE = 'https://montrealai.github.io/AGI-Alpha-Invention-Flywheel-Lab/frontier-omega-alpha/'
CURRENT = 'f0c8db6c7a1110dc614ab8a02c7a0bd5f79260de'
FACTORY = '436bb1b142a0da1f2c272f77821b75c3efdd73fe'
FACTORY_ARCHIVE = '5a29bc8d215895216201b85dcf6f5af6709d0ecea857792cf24b3cc4d20ec791'
CASES = {
    'ACT15': {
        'filename': 'frontier-activation-1.5.0.zip',
        'pin': FACTORY,
        'members': {
            'evidence_control.py': 'products/frontier-member-tools/activation/evidence_control.py',
            'study/factory/EVIDENCE.json': 'publication/factory/EVIDENCE.json',
        },
    },
    'INV10': {
        'filename': 'frontier-inventor-1.0.0.zip',
        'pin': CURRENT,
        'members': {
            'relational.py': 'products/frontier-member-tools/inventor/relational.py',
            'study/reproduction.json': 'publication/inventor/reproduction.json',
            'study/evidence.json': 'publication/inventor/evidence.json',
        },
    },
}

INVENTOR_CHECK = '''
from hashlib import sha256
import json
from pathlib import Path
from relational import check

reproduction = json.loads(Path('study/reproduction.json').read_bytes())
evidence = json.loads(Path('study/evidence.json').read_bytes())
registration = reproduction['registration']
def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()
if digest(registration) != evidence['registration_sha256']:
    raise ValueError('Registration hash differs')
records = {}
for label, record in evidence['assessments'].items():
    assessment = record['assessment']
    if assessment['arm'] != 'conventional':
        continue
    name = assessment['mission']
    sample = reproduction['missions'][name]
    commitments = registration['commitments'][name]
    if (digest(sample['mission']) != commitments['mission'] or
            digest(sample['confirmation']) != commitments['confirmation'] or
            digest(sample['incumbent']) != commitments['incumbent'] or digest(assessment) != record['sha256']):
        raise ValueError('Case, tool or assessment hash differs')
    observed = check(sample['mission'], sample['confirmation'], sample['incumbent']['sql'])
    if len(observed) != 9 or observed != assessment['checks'] or not all(row['pass'] for row in observed):
        raise ValueError('Conventional scope did not reproduce')
    if assessment['matched'] != assessment['total'] or assessment['total'] != 9 or assessment['verdict'] != 'MATCHED':
        raise ValueError('Conventional qualification differs')
    records[label] = dict(matched=9, total=9, verdict='MATCHED')
if set(records) != {'editions-conventional', 'endpoint-conventional', 'impact-conventional'}:
    raise ValueError('Conventional scope is incomplete')
print(json.dumps(records, sort_keys=True))
'''


class NoRedirect(HTTPRedirectHandler):
    """Limit acquisition to a known approved release URL."""

    def redirect_request(self, *args, **kwargs):
        return None


HTTP = build_opener(NoRedirect())


def digest(raw):
    return sha256(raw).hexdigest()


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def fetch(name, *, limit, metrics, interval=None):
    headers = {'User-Agent': 'FRONTIER-public-release-independent-control',
               'Accept-Encoding': 'identity'}
    if interval is not None:
        first, last = interval
        headers['Range'] = f'bytes={first}-{last}'
    start = monotonic()
    entry = {'file': name, 'range': interval}
    metrics.append(entry)
    try:
        with HTTP.open(Request(SITE + name, headers=headers), timeout=20) as r:
            entry.update(status=r.status, content_range=r.headers.get('Content-Range'),
                         content_length=r.headers.get('Content-Length'), etag=r.headers.get('ETag'))
            raw = r.read(limit + 1)
            entry['body_bytes_read'] = len(raw)
            require(len(raw) <= limit, 'Response exceeds read envelope')
            require(r.headers.get('Content-Encoding') in {None, 'identity'}, 'Unexpected transfer encoding')
            return raw
    finally:
        entry['wall_seconds'] = monotonic() - start


def get_layout(raw, files):
    with ZipFile(BytesIO(raw)) as archive:
        require(len(archive.namelist()) == len(set(archive.namelist())), 'Nonunique archive member')
        payload = {}
        spans = {}
        for name in files:
            info = archive.getinfo(name)
            require(info.compress_type == ZIP_STORED, 'Expected stored ZIP member')
            offset = info.header_offset
            magic, = unpack_from('<I', raw, offset)
            name_len, extra_len = unpack_from('<HH', raw, offset + 26)
            require(magic == 0x04034b50 and raw[offset + 30:offset + 30 + name_len] == name.encode(),
                    'Invalid ZIP member header')
            first = offset + 30 + name_len + extra_len
            spans[name] = (first, first + info.compress_size - 1)
            payload[name] = archive.read(info)
    return payload, spans


def optimum(spans):
    ordered = sorted(spans.values())
    plans = [[(ordered[0][0], ordered[-1][1])]]
    for index in range(len(ordered) - 1):
        plans.append([(ordered[0][0], ordered[index][1]), (ordered[index+1][0], ordered[-1][1])])
    return min(plans, key=lambda routes: (sum(b-a+1 for a,b in routes), len(routes), routes))


def bind(files, expected):
    require(set(files) == set(expected), 'Required packet incomplete')
    received = {name: digest(raw) for name, raw in files.items()}
    require(received == expected, 'Release member does not match independently pinned Git bytes')
    return received


def check(case, files):
    with TemporaryDirectory(prefix=case + '-', dir=OUT) as root:
        root = Path(root)
        for name, raw in files.items():
            artifact = root / name
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(raw)
        args = [sys.executable, '-I', '-B']
        if case == 'ACT15':
            args.extend(['evidence_control.py', 'study/factory/EVIDENCE.json', '--metrics'])
        else:
            code = "import sys;sys.path.insert(0, '.');" + INVENTOR_CHECK
            args.extend(['-c', code])
        result = subprocess.run(args, capture_output=True, cwd=root, check=True)
    payload = json.loads(result.stdout)
    if case == 'ACT15':
        accepted = {row['id'] for row in payload if row['verdict'] == 'DOCUMENTED_BY_CUTOFF'}
        withheld = {row['id'] for row in payload if row['verdict'] == 'ABSTAIN_UNESTABLISHED'}
        require(len(payload) == 9 and len(withheld) == 7 and accepted == {'prusa_offer', 'bambu_software'}
                and all(not payload_row['onset_established'] and not payload_row['continuity_established']
                        for payload_row in payload), 'Unexpected industrial review disposition')
        return dict(outcome='MATCHED', accepted=sorted(accepted), withheld=sorted(withheld),
                    stdout_sha256=digest(result.stdout), exact_decisions=9, runner_metrics=json.loads(result.stderr))
    return dict(outcome='MATCHED', comparisons=payload, stdout_sha256=digest(result.stdout),
                exact_decisions=27)


def operation(label, use, expected, release):
    filename = use['filename']
    complete = dict(operations=[])
    started, cpu = monotonic(), process_time()
    full = fetch(filename, limit=3_000_000, metrics=complete['operations'])
    full_sha = release['foundry_sha256'][filename]
    if label == 'ACT15':
        require(full_sha == FACTORY_ARCHIVE, 'Factory release does not match source-fixed exact ZIP')
    require(complete['operations'][0]['status'] == 200 and digest(full) == full_sha, 'Whole archive hash differs')
    members, spans = get_layout(full, expected)
    member_hashes = bind(members, expected)
    complete['verification'] = check(label, members)
    complete.update(wall_seconds=monotonic()-started, parent_cpu_seconds=process_time()-cpu,
                    sha256=full_sha, body_bytes=len(full), required_member_sha256=member_hashes)
    plan_started = monotonic()
    ranges = optimum(spans)
    lower = sum(b-a+1 for a,b in ranges)
    minimum_payload = sum(b-a+1 for a,b in spans.values())
    range_receipt = {'operations': [], 'planned_intervals': ranges, 'known_index': True,
                     'index_elapsed_seconds': monotonic() - plan_started,
                     'two_single_range_exact_optimum_bytes': lower, 'member_payload_lower_bound_bytes': minimum_payload}
    started, cpu = monotonic(), process_time()
    restored = {}
    try:
        for first, last in ranges:
            body = fetch(filename, interval=(first,last), limit=last-first+1, metrics=range_receipt['operations'])
            response = range_receipt['operations'][-1]
            require(response['status'] == 206 and len(body) == last-first+1,
                    'Range response is incomplete or not partial')
            require(response['content_range'] == f'bytes {first}-{last}/{len(full)}',
                    'Range does not refer to the pinned envelope')
            for name, (low, high) in spans.items():
                if first <= low and high <= last:
                    restored[name] = body[low-first:high-first+1]
        bind(restored, expected)
        range_receipt['verification'] = check(label, restored)
        require(range_receipt['verification']['stdout_sha256'] == complete['verification']['stdout_sha256'],
                'Result from ranged members differs')
        range_receipt['outcome'] = 'MATCHED'
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        range_receipt.update(outcome='FAILED', reason=str(error))
    range_receipt.update(wall_seconds=monotonic()-started, parent_cpu_seconds=process_time()-cpu,
                         body_bytes=sum(row.get('body_bytes_read',0) for row in range_receipt['operations']))
    return {'whole_archive': complete, 'ordinary_optimal_two_ranges': range_receipt, 'member_spans': spans}


def main(repo):
    started, cpu = monotonic(), process_time()
    expected = {name: {member: digest(subprocess.check_output(['git','show',f"{case['pin']}:{source}"], cwd=repo))
                       for member, source in case['members'].items()} for name, case in CASES.items()}
    metas = []
    release_raw = fetch('atlas-release.json',limit=16_000,metrics=metas)
    release = json.loads(release_raw)
    require(release['source_commit'] == CURRENT, 'Observed Pages source differs from registered release')
    prep = dict(wall_seconds=monotonic()-started, parent_cpu_seconds=process_time()-cpu, operations=metas)
    result = dict(source_revision=CURRENT, atlas_workflow_run=release['workflow_run'],
                  atlas_manifest_sha256=digest(release_raw), common_provenance_prep=prep,
                  author_or_reviewer_time='unmeasured', construction='single operator command for both arms', cases={})
    for name, case in CASES.items():
        try:
            result['cases'][name] = operation(name, case, expected[name], release)
        except (ValueError,OSError,subprocess.SubprocessError) as error:
            result['cases'][name] = {'outcome':'FAILED','reason':str(error)}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main(Path(sys.argv[1]).resolve())
