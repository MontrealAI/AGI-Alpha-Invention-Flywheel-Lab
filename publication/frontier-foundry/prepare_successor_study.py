"""Prepare the registered archive-resume case sheet outside the constructor."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import random
import re
import secrets
import subprocess
from time import perf_counter_ns

URL = 'https://noaa-gfs-bdp-pds.s3.amazonaws.com/gfs.20240124/00/atmos/gfs.t00z.pgrb2.0p25.f024'
FOLLOW_UP_URL = URL.replace('20240124', '20240125')
MODEL = 'qwen3-4b-instruct-2507-q4_k_m'
NUM = {'min':0, 'max':2_000_000_000}
TASK = {
    'schema':'frontier/foundry-mission-v1', 'language':'en',
    'objective':'Decide whether a fresh partial weather-data response can extend the last verified prefix.',
    'rule':('All inputs except same_version are nonnegative integers. previous_end is the last saved byte. '
            'start and end are inclusive offsets in the new response, object_bytes is the total object length, '
            'and body_bytes is the integer count of bytes actually transferred. same_version means the same '
            'strong version validator. Output appendable is true exactly when same_version is true, start is '
            'one after previous_end, start is at or before end, end is within the object, and the inclusive '
            'count of the new interval equals body_bytes.'),
    'inputs':{**{key:NUM for key in ('previous_end','start','end','object_bytes','body_bytes')}, 'same_version':'boolean'},
    'outputs':{'appendable':'boolean'},
    'alternative':'Direct Python range membership/cardinality with source checks for strong ETag and byte counts.',
    'acceptance':'Every held case must agree with the independent decision. No network or file effects from the evaluator.',
}


def stable(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def digest(raw):
    return sha256(raw).hexdigest()


def save(path, value):
    with path.open('xb') as file:
        file.write(stable(value) + b'\n')


def acquire(directory, left, right, url):
    data, headers = directory / f'{left}-{right}.bytes', directory / f'{left}-{right}.headers'
    start = perf_counter_ns()
    status = subprocess.run(['curl', '-fsS', '--max-time', '30', '--max-filesize', str(right-left+1),
                             '--range', f'{left}-{right}', '--dump-header', str(headers),
                             '--output', str(data), url], capture_output=True)
    elapsed = perf_counter_ns() - start
    lines = headers.read_text(errors='replace').splitlines() if headers.exists() else []
    fields = {}
    http = None
    for line in lines:
        if line.startswith('HTTP/'):
            http = line.split()[1]
            fields = {}
        elif ':' in line:
            key, value = line.split(':', 1)
            fields[key.lower()] = value.strip()
    body = data.read_bytes() if data.exists() else b''
    content_range = fields.get('content-range', '')
    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', content_range)
    etag = fields.get('etag', '')
    ok = (status.returncode == 0 and http == '206' and match is not None and
          tuple(map(int, match.groups()[:2])) == (left,right) and int(match[3]) > right and
          len(body) == right-left+1 and re.fullmatch(r'"[^"\x00-\x20\x7f]+"', etag) is not None)
    receipt = {'requested_range':f'{left}-{right}', 'content_range':content_range, 'http':http,
               'curl_exit':status.returncode, 'etag':etag, 'bytes':len(body), 'sha256':digest(body),
               'elapsed_ns':elapsed, 'observed':ok, 'object_bytes':int(match[3]) if match else None}
    return body, receipt


def oracle(item):
    interval = range(item['start'], item['end'] + 1)
    return (item['same_version'] and item['previous_end'] + 1 == interval.start and
            0 < len(interval) == item['body_bytes'] and interval[-1] in range(item['object_bytes']))


def row(item):
    return {'input':item, 'expected':{'appendable':oracle(item)}}


def controlled_cases(seed):
    rng = random.Random(seed)
    rows = []
    for _ in range(6):
        previous = rng.randrange(10_000, 10_000_000)
        size = rng.randrange(3, 512)
        good = {'previous_end':previous, 'start':previous+1, 'end':previous+size,
                'object_bytes':previous+size+rng.randrange(2, 1_000), 'body_bytes':size, 'same_version':True}
        rows.extend(row(test) for test in (good,
                    {**good, 'start':previous+2, 'body_bytes':size-1},
                    {**good, 'start':previous, 'body_bytes':size+1},
                    {**good, 'end':previous, 'body_bytes':0},
                    {**good, 'object_bytes':good['end']},
                    {**good, 'body_bytes':size-1},
                    {**good, 'same_version':False},
                    {**good, 'end':previous+1, 'object_bytes':previous+2, 'body_bytes':1}))
    rng.shuffle(rows)
    return rows


def incumbent():
    def field(name):
        return {'field':name}

    def op(name, *args):
        return {'op':name, 'args':list(args)}

    start, end = field('start'), field('end')
    return {'name':'Conventional direct integer baseline', 'inputs':list(TASK['inputs']),
            'outputs':{'appendable':op('and', field('same_version'),
                                       op('eq', start, op('add', field('previous_end'), 1)),
                                       op('lte', start, end), op('lt', end, field('object_bytes')),
                                       op('eq', op('add', op('sub', end, start), 1), field('body_bytes')))}}


def main(directory, seed, clarify):
    directory.mkdir(mode=0o700)
    url = FOLLOW_UP_URL if clarify else URL
    task = {**TASK}
    if clarify:
        task['rule'] += (' Offsets start at zero. The last legal offset is object_bytes minus one. An end '
                         'offset equal to object_bytes must be rejected, even if the lengths agree.')
    raw = [acquire(directory, left, right, url) for left,right in ((0,15),(16,31),(0,31))]
    a, b, joined = [body for body, _ in raw]
    parts = [receipt for _, receipt in raw]
    same_version = len({p['etag'] for p in parts}) == 1
    accepted = (all(p['observed'] for p in parts) and same_version and a+b == joined and
                len({p['object_bytes'] for p in parts}) == 1 and parts[0]['object_bytes'] <= NUM['max'])
    rows = controlled_cases(seed)
    if accepted:
        rows.append(row({'previous_end':15,'start':16,'end':31,'object_bytes':parts[0]['object_bytes'],
                         'body_bytes':len(b), 'same_version':same_version}))
    cases = {'schema':'frontier/foundry-cases-v1', 'mission_sha256':digest(stable(task)),
             'reference':'Python range oracle, RFC 9110 sections 14 and 15.3.7.3, and verified NOAA ranges when available.',
             'cases':rows}
    spec = {'task':task,'model':MODEL,'output_tokens':256,
            'hypothesis':'Named reuse increases accepted construction for a continuation decision compared with equal-content ordinary reuse.'}
    save(directory / 'spec.json', spec)
    save(directory / 'cases.json', cases)
    save(directory / 'incumbent.json', incumbent())
    save(directory / 'source.json', {'url':url,'parts':parts,'status':'OBSERVED' if accepted else 'ABSTAIN',
                                     'real_cases':int(accepted),'generated_cases':48,'seed':str(seed),
                                     'case_sha256':digest(stable(cases))})
    print(digest(stable(cases)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--seed', type=int)
    parser.add_argument('--clarify', action='store_true')
    args = parser.parse_args()
    main(args.directory, secrets.randbits(63) if args.seed is None else args.seed, args.clarify)
