"""Read a one-file submission through trusted GitHub REST metadata."""

from base64 import b64decode
from hashlib import sha1, sha256
import re
import subprocess

from .intake import CAPSULE, GITHUB_SHA, INBOX, LOGIN, capsule, digest, event_id, exported_capsule, load_json

REPO = 'MontrealAI/AGI-Alpha-Invention-Flywheel-Lab'
BRANCH = re.compile(r'bridge-intake/([0-9a-f]{64})\Z')
LEGACY_PR = 546
LEGACY_HEAD = '49510b45f85b0eafc5bdaa6440fa1bec603a92ca'
LEGACY_CAPSULE_DIGEST = 'be47efe8e929d66d5e82a79bb3c19f9d858ca812058d14b2d2335ebf12fd1fe1'


def github(path):
    response = subprocess.run(['gh', 'api', '-H', 'Accept: application/vnd.github+json', path],
                              capture_output=True, timeout=25, check=False)
    if response.returncode:
        raise ValueError('GitHub read or approval unavailable')
    return load_json(response.stdout, 2 * 1024 * 1024)


def normalize_pr_capsule(number, head, raw):
    if number == LEGACY_PR and head == LEGACY_HEAD and sha256(raw).hexdigest() == LEGACY_CAPSULE_DIGEST:
        old = load_json(raw)
        legacy_id = digest({key: old[key] for key in ('source_task_id', 'source', 'version')})
        del old['source_task_id']
        old['schema'] = CAPSULE
        projected = exported_capsule(old)
        capsule(projected)
        return projected, legacy_id
    value = capsule(raw)
    if value is None or raw != exported_capsule(value):
        raise ValueError('Use the exact normalized capsule produced by preflight')
    return raw, event_id(value)


def intake_pr(number, owners, expected_head, request=github):
    if type(number) is not int or not 1 <= number <= 100_000_000 or not owners or len(owners) > 32 or not all(LOGIN.fullmatch(x) for x in owners):
        raise ValueError('Invalid PR number or configured submitter list')
    if not isinstance(expected_head, str) or not GITHUB_SHA.fullmatch(expected_head):
        raise ValueError('Supply the full reviewed GitHub head')
    endpoints = 'repos/' + REPO
    pull = endpoints + '/pulls/' + str(number)
    meta = request(pull)
    actor = meta['user']['login']
    head = meta['head']['sha']
    branch = BRANCH.fullmatch(meta['head']['ref'])
    if (meta['number'] != number or meta['state'] != 'open' or actor not in owners or head != expected_head or not branch
            or meta['base']['ref'] != 'main' or meta['base']['repo']['full_name'] != REPO
            or meta['head']['repo']['full_name'] != REPO or meta['changed_files'] != 1):
        raise ValueError('Only reviewed single-file submissions to the authorized repository can enter')
    files = request(pull + '/files?per_page=2')
    if not isinstance(files, list) or len(files) != 1 or files[0]['status'] != 'added':
        raise ValueError('Only one added public capsule is permitted')
    file = files[0]
    path = INBOX + branch.group(1) + '.json'
    if file['filename'] != path or not GITHUB_SHA.fullmatch(file['sha']):
        raise ValueError('Unexpected inbox path or Git object')
    blob = request(endpoints + '/contents/' + path + '?ref=' + expected_head)
    if (blob['path'] != path or blob['type'] != 'file' or blob['sha'] != file['sha']
            or blob['encoding'] != 'base64' or type(blob['size']) is not int
            or not 0 < blob['size'] <= 4096 or len(blob['content']) > 6000):
        raise ValueError('Unexpected capsule blob')
    raw = b64decode(''.join(blob['content'].split()), validate=True)
    git_hash = sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if len(raw) != blob['size'] or git_hash != blob['sha']:
        raise ValueError('Capsule bytes do not match the Git object')
    projected, identity = normalize_pr_capsule(number, head, raw)
    if branch.group(1) != identity:
        raise ValueError('The authoring branch and input path must bind the validated identity')
    check = request(pull)
    changed_refs = any(check[side]['ref'] != meta[side]['ref'] or check[side].get('sha') != meta[side].get('sha')
                       or check[side]['repo']['full_name'] != REPO for side in ('head', 'base'))
    if changed_refs or check['user']['login'] != actor or check['state'] != 'open' or check['changed_files'] != 1:
        raise ValueError('Submission changed during validation')
    return projected, {'submitted_at': meta['created_at'], 'submitter': actor, 'github_pr': number,
                 'commit_sha': head, 'authenticated_by': 'github-rest'}
