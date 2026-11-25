"""Finite prospective public observation of a staged FreeCAD binary release."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from time import monotonic, perf_counter_ns, sleep
from urllib.request import HTTPRedirectHandler, Request, build_opener

from evidence_truth import evaluate


TARGET = 'weekly-2026.11.25'
URL = f'https://api.github.com/repos/FreeCAD/FreeCAD/releases/tags/{TARGET}'
ASSET = f'FreeCAD_{TARGET}-Linux-aarch64.AppImage'
ROOT = Path(__file__).resolve().parent / 'prospective'
CAPTURE_INTERVAL = 95
CAPTURE_COUNT = 37
ANSWER = 'freecad-weekly-arm-artifact'
HEX = re.compile(r'sha256:[a-f0-9]{64}\Z')
SCOPE = {'product': 'FreeCAD', 'version': TARGET, 'feature': 'AppImage', 'platform': 'Linux-aarch64'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def clock():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *arguments, **options):
        return None


def request_snapshot():
    request = Request(URL, headers={'User-Agent': 'Frontier-Atlas-Prospective-Research/1.0',
                                    'Accept': 'application/vnd.github+json', 'Cache-Control': 'no-cache'})
    with build_opener(NoRedirect()).open(request, timeout=12) as response:
        if response.status != 200 or response.url != URL:
            raise ValueError('unexpected official response')
        body = response.read(200_001)
        if not 0 < len(body) <= 200_000:
            raise ValueError('unbounded official response')
        metadata = {field.lower(): response.headers.get(field)
                    for field in ('Date', 'Age', 'ETag', 'X-RateLimit-Remaining')}
    return body, metadata


def ordinary(release):
    if release.get('tag_name') != TARGET or release.get('draft') is not False or release.get('prerelease') is not True:
        raise ValueError('incorrect official release identity')
    hits = [a for a in release['assets'] if a['name'] == ASSET and a['state'] == 'uploaded'
            and type(a['size']) is int and a['size'] > 0 and HEX.fullmatch(a.get('digest') or '')]
    if len(hits) > 1:
        raise ValueError('ambiguous asset identity')
    return hits[0] if hits else None


def retained(release, body_digest, observed_utc):
    if release.get('tag_name') != TARGET or release.get('draft') is not False or release.get('prerelease') is not True:
        raise ValueError('incorrect official release identity')
    as_of = observed_utc.split('.')[0] + 'Z'
    rows = [{'id': 'tag-only', 'source': 'release', 'role': 'documentation',
             'verified_by': release['published_at'], 'scope': SCOPE}]
    assets = {a['id']: a for a in release['assets']}
    if len(assets) != len(release['assets']):
        raise ValueError('ambiguous asset identity')
    for identity, asset in assets.items():
        if asset['name'] != ASSET or asset['state'] != 'uploaded' or type(asset['size']) is not int or asset['size'] <= 0:
            continue
        if HEX.fullmatch(asset.get('digest') or ''):
            rows.append({'id': f'asset-{identity}', 'source': 'release', 'role': 'first_party_release',
                         'verified_by': as_of, 'scope': SCOPE})
    study = {'schema': 'frontier/evidence-truth-v1',
             'sources': [{'id': 'release', 'url': URL, 'binding': 'source_bytes',
                          'sha256': body_digest, 'published_at': release['published_at']}],
             'cases': [{'id': ANSWER, 'kind': 'product_stage', 'stage': 'software_support',
                        'as_of': as_of, 'scope': SCOPE, 'records': rows}]}
    return evaluate(study)[ANSWER]


def append(row):
    with (ROOT / 'observations.jsonl').open('ab') as stream:
        stream.write(canonical(row) + b'\n')
    print(canonical(row).decode(), flush=True)


def observe(number):
    row = {'sequence': number, 'requested_at_utc': clock()}
    started = perf_counter_ns()
    try:
        body, headers = request_snapshot()
        row.update({'acquired_at_utc': clock(), 'fetch_ns': perf_counter_ns() - started,
                    'bytes': len(body), 'sha256': sha256(body).hexdigest(), 'headers': headers})
        raw = ROOT / f"{row['sha256']}.json"
        if not raw.exists():
            raw.write_bytes(body)
        release = json.loads(body)
        row['tag_published_at_utc'] = release['published_at']
        row['total_assets'] = len(release['assets'])
        tick = perf_counter_ns()
        baseline = ordinary(release)
        row['competent_baseline_ns'] = perf_counter_ns() - tick
        tick = perf_counter_ns()
        truth = retained(release, row['sha256'], row['acquired_at_utc'])
        row['retained_stage_ns'] = perf_counter_ns() - tick
        row['retained_result'] = truth['verdict']
        row['tag_only_as_artifact'] = truth['excluded'].get('tag-only')
        row['competent_baseline_witnessed'] = baseline is not None
        if baseline:
            row['witness'] = {k: baseline[k] for k in ('id', 'name', 'state', 'size', 'digest', 'created_at', 'updated_at')}
        if (baseline is not None) != (truth['verdict'] == 'DOCUMENTED_BY_CUTOFF'):
            row['disagreement'] = True
    except (OSError, ValueError, KeyError) as error:
        row['error'] = str(error)
    append(row)
    return row


def main():
    ROOT.mkdir(exist_ok=False)
    registration = {'frozen_at_utc': clock(), 'source': URL, 'tag': TARGET, 'asset': ASSET,
                    'sampling_interval_s': CAPTURE_INTERVAL, 'maximum_samples': CAPTURE_COUNT,
                    'acceptance': 'Exact public non-draft prerelease; exact Linux aarch64 AppImage asset; uploaded state; positive size; SHA-256 digest.',
                    'publication_clock': 'Asset created_at and updated_at are registry metadata. Measure actionability from first observed qualifying payload.',
                    'comparison': 'Strong exact-source ordinary validator and retained stage adjudicator receive the identical recorded source byte stream. Null acquisition lead by design; this is a matched attestation and verification trial.',
                    'stop': 'Stop after first qualifying jointly witnessed asset, fixed sample count, or a local STOP file. Report absent events and failures.',
                    'source_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
                    'retained_sha256': sha256(Path(sys.modules['evidence_truth'].__file__).read_bytes()).hexdigest()}
    (ROOT / 'registration.json').write_bytes(canonical(registration) + b'\n')
    print(canonical(registration).decode(), flush=True)
    origin = monotonic()
    for number in range(CAPTURE_COUNT):
        if (ROOT / 'STOP').exists():
            break
        row = observe(number)
        if row.get('witness'):
            break
        due = origin + (number + 1) * CAPTURE_INTERVAL
        while monotonic() < due and not (ROOT / 'STOP').exists():
            sleep(min(5, max(0, due - monotonic())))


if __name__ == '__main__':
    main()
