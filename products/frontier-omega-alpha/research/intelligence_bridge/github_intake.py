"""Read a one-file submission through trusted GitHub REST metadata."""

from base64 import b64decode
from hashlib import sha1
import subprocess

from .intake import GITHUB_SHA, INBOX, LOGIN, capsule, event_id, exported_capsule, load_json

REPO = 'MontrealAI/AGI-Alpha-Invention-Flywheel-Lab'


def github(path):
    response = subprocess.run(['gh', 'api', '-H', 'Accept: application/vnd.github+json', path],
                              capture_output=True, timeout=25, check=False)
    if response.returncode:
        raise ValueError('GitHub read or approval unavailable')
    return load_json(response.stdout, 2 * 1024 * 1024)


def intake_pr(number, owners, request=github):
    if type(number) is not int or not 1 <= number <= 100_000_000 or not owners or len(owners) > 32 or not all(LOGIN.fullmatch(x) for x in owners):
        raise ValueError('Invalid PR number or configured submitter list')
    endpoints = 'repos/' + REPO
    pull = endpoints + '/pulls/' + str(number)
    meta = request(pull)
    actor = meta['user']['login']
    head = meta['head']['sha']
    if (meta['number'] != number or meta['state'] != 'open' or actor not in owners or not GITHUB_SHA.fullmatch(head)
            or meta['base']['ref'] != 'main' or meta['base']['repo']['full_name'] != REPO
            or meta['head']['repo']['full_name'] != REPO or meta['changed_files'] != 1):
        raise ValueError('Only reviewed single-file submissions to the authorized repository can enter')
    files = request(pull + '/files?per_page=2')
    if not isinstance(files, list) or len(files) != 1 or files[0]['status'] != 'added':
        raise ValueError('Only one added public capsule is permitted')
    file = files[0]
    if not file['filename'].startswith(INBOX) or not GITHUB_SHA.fullmatch(file['sha']):
        raise ValueError('Unexpected inbox path or Git object')
    blob = request(endpoints + '/git/blobs/' + file['sha'])
    if (blob['sha'] != file['sha'] or blob['encoding'] != 'base64' or type(blob['size']) is not int
            or not 0 < blob['size'] <= 4096 or len(blob['content']) > 6000):
        raise ValueError('Unexpected capsule blob')
    raw = b64decode(''.join(blob['content'].split()), validate=True)
    git_hash = sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
    if len(raw) != blob['size'] or git_hash != blob['sha']:
        raise ValueError('Capsule bytes do not match the Git object')
    value = capsule(raw)
    if value is None or raw != exported_capsule(value):
        raise ValueError('Use the exact normalized capsule produced by preflight')
    identity = event_id(value)
    if file['filename'] != INBOX + identity + '.json' or meta['head']['ref'] != 'bridge-intake/' + identity:
        raise ValueError('The authoring branch and input path must bind the validated identity')
    check = request(pull)
    if check['head']['sha'] != head or check['user']['login'] != actor or check['state'] != 'open':
        raise ValueError('Submission changed during validation')
    return raw, {'submitted_at': meta['created_at'], 'submitter': actor, 'github_pr': number,
                 'commit_sha': head, 'authenticated_by': 'github-rest'}
