"""Isolated, key-private v2 transport experiment; NOT a native Account upgrade."""
import hashlib
import hmac
import json
import os
from pathlib import Path

DOMAIN = b'agi-alpha/native-source-transition-capsule/v2\n'
SCHEMA = 'agi-alpha/source-transition-capsule/v2'
MAX_TICKET_BYTES = 16_000_000
MAX_ANCHOR_BYTES = 80_000_000


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _regular(path):
    path = Path(path).absolute()
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('REGULAR_NON_SYMLINK_ANCHOR_REQUIRED')
    if path.stat().st_size > MAX_ANCHOR_BYTES:
        raise ValueError('BOUNDED_ANCHOR_REQUIRED')
    return path


def _strict(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError('DUPLICATE_ANCHOR_FIELD')
        d[k] = v
    return d


def _anchor_path(storage, digest):
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('INVALID_ANCHOR_DIGEST')
    folder = Path(storage).absolute()
    if any(p.is_symlink() for p in (folder, *folder.parents)):
        raise ValueError('ANCHOR_DIRECTORY_SYMLINK_REFUSED')
    if not folder.is_dir():
        raise ValueError('PREEXISTING_ANCHOR_DIRECTORY_REQUIRED')
    return folder / (digest + '.json')


def _store_anchor(storage, raw):
    if len(raw) > MAX_ANCHOR_BYTES:
        raise ValueError('BOUNDED_ANCHOR_REQUIRED')
    digest = sha(raw)
    path = _anchor_path(storage, digest)
    if path.exists() or path.is_symlink():
        if _regular(path).read_bytes() != raw:
            raise ValueError('IMMUTABLE_ANCHOR_COLLISION')
        return digest
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        if _regular(path).read_bytes() != raw:
            raise ValueError('IMMUTABLE_ANCHOR_RACE')
        return digest
    try:
        with os.fdopen(fd, 'wb', closefd=True) as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        raise
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return digest



def _clock(checkpoint, prior_record, day):
    state = checkpoint['body'].get('state', {})
    last_time = state.get('last_time', 0)
    queue = state.get('queue', [])
    actions = prior_record.get('ledger', {}).get('actions', [])
    if type(last_time) is not int or not isinstance(queue, list) or not isinstance(actions, list):
        raise ValueError('PINNED_OPERATING_QUEUE_REQUIRED')
    if state.get('current') is not None or any(type(e.get('time')) is not int or not isinstance(e.get('id'), str) for e in queue):
        raise ValueError('RECOVER_INFLIGHT_OR_INVALID_QUEUE_BEFORE_TRANSITION')
    native_time = max((a.get('day', 0) for a in actions), default=0)
    if any(type(a.get('day', 0)) is not int for a in actions) or day < max(last_time, native_time):
        raise ValueError('SOURCE_TRANSITION_CLOCK_ROLLBACK')
    if queue and day > min(e['time'] for e in queue):
        raise ValueError('SOURCE_TRANSITION_OVERTAKES_PENDING_WORK')


def prepare(storage, *, key, account_path, transition_id, counter, day, from_source, to_source,
            checkpoint, prior_record, prior_envelope, verified_native_sequence, verified_native_digest):
    if not isinstance(key, bytes) or len(key) < 32:
        raise ValueError('EXISTING_ACCOUNT_HMAC_AUTHORITY_REQUIRED')
    if not isinstance(transition_id, str) or not transition_id or len(transition_id) > 80 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in transition_id):
        raise ValueError('SAFE_TRANSITION_ID_REQUIRED')
    if type(counter) is not int or not 1 <= counter <= 4 or type(day) is not int or day < 0:
        raise ValueError('FINITE_NATIVE_COUNTER_AND_CLOCK_REQUIRED')
    if not all(isinstance(x, str) and len(x) == 64 and all(c in '0123456789abcdef' for c in x) for x in (from_source, to_source, verified_native_digest)) or from_source == to_source:
        raise ValueError('PINNED_DISTINCT_SOURCE_REQUIRED')
    if type(verified_native_sequence) is not int or verified_native_sequence < 0:
        raise ValueError('NATIVE_PREFIX_REQUIRED')
    if not isinstance(checkpoint, dict) or not isinstance(prior_record, dict) or not isinstance(prior_envelope, dict):
        raise ValueError('EXACT_HISTORICAL_RECORDS_REQUIRED')
    if prior_envelope.get('body') != prior_record.get('connected_journal'):
        raise ValueError('ORIGINAL_SIGNED_JOURNAL_NOT_PRESERVED')
    body = checkpoint.get('body', {})
    if body.get('native_sequence') != verified_native_sequence or body.get('native_actions_sha256') != verified_native_digest or body.get('source_sha256') != from_source:
        raise ValueError('OPERATING_NATIVE_PREFIX_OR_SOURCE_CHANGED')
    if checkpoint.get('signature') is None or prior_envelope.get('signature') is None:
        raise ValueError('HISTORICAL_SIGNATURES_REQUIRED')
    _clock(checkpoint, prior_record, day)
    prior = {'schema': 'agi-alpha/source-transition-anchor/v2', 'prior_record': prior_record,
             'prior_envelope': prior_envelope, 'checkpoint': checkpoint}
    raw = canonical(prior)
    digest = _store_anchor(storage, raw)
    ticket_body = {'schema': SCHEMA, 'account_path': str(Path(account_path).absolute()), 'transition_id': transition_id,
                   'counter': counter, 'day': day, 'from_source_sha256': from_source,
                   'to_source_sha256': to_source, 'native_sequence': verified_native_sequence,
                   'native_actions_sha256': verified_native_digest, 'anchor_sha256': digest,
                   'anchor_bytes': len(raw), 'checkpoint_sha256': sha(canonical(checkpoint)),
                   'prior_record_sha256': sha(canonical(prior_record)),
                   'prior_journal_sha256': sha(canonical(prior_envelope))}
    ticket = {'body': ticket_body, 'signature': hmac.new(key, DOMAIN + canonical(ticket_body), hashlib.sha256).hexdigest()}
    if len(canonical(ticket)) > MAX_TICKET_BYTES:
        raise ValueError('EXISTING_TICKET_BOUND_EXCEEDED')
    return ticket


def verify(storage, ticket, *, key, account_path, expected_source, expected_counter, expected_sequence,
           expected_native_digest, expected_checkpoint_sha256, historical_audit):
    if not isinstance(ticket, dict) or set(ticket) != {'body', 'signature'} or len(canonical(ticket)) > MAX_TICKET_BYTES:
        raise ValueError('EXACT_BOUNDED_CAPSULE_REQUIRED')
    b = ticket['body']
    keys = {'schema', 'account_path', 'transition_id', 'counter', 'day', 'from_source_sha256',
            'to_source_sha256', 'native_sequence', 'native_actions_sha256', 'anchor_sha256',
            'anchor_bytes', 'checkpoint_sha256', 'prior_record_sha256', 'prior_journal_sha256'}
    if not isinstance(b, dict) or set(b) != keys or b['schema'] != SCHEMA:
        raise ValueError('EXACT_CAPSULE_BODY_REQUIRED')
    if not isinstance(key, bytes) or len(key) < 32 or not hmac.compare_digest(str(ticket['signature']), hmac.new(key, DOMAIN + canonical(b), hashlib.sha256).hexdigest()):
        raise ValueError('ACCOUNT_CAPSULE_HMAC_REJECTED')
    if (b['account_path'] != str(Path(account_path).absolute()) or b['from_source_sha256'] != expected_source
            or type(b['counter']) is not int or type(b['native_sequence']) is not int
            or b['counter'] != expected_counter + 1 or b['native_sequence'] != expected_sequence
            or b['native_actions_sha256'] != expected_native_digest
            or b['checkpoint_sha256'] != expected_checkpoint_sha256
            or type(b['day']) is not int or b['day'] < 0 or b['to_source_sha256'] == b['from_source_sha256']):
        raise ValueError('STALE_FORK_OR_CROSS_ACCOUNT_CAPSULE_REJECTED')
    if type(b['anchor_bytes']) is not int or not 0 < b['anchor_bytes'] <= MAX_ANCHOR_BYTES:
        raise ValueError('BOUNDED_ANCHOR_REQUIRED')
    path = _regular(_anchor_path(storage, b['anchor_sha256']))
    if path.stat().st_size != b['anchor_bytes']:
        raise ValueError('ANCHOR_SIZE_CHANGED')
    raw = path.read_bytes()
    if sha(raw) != b['anchor_sha256']:
        raise ValueError('ANCHOR_HASH_CHANGED')
    record = json.loads(raw, object_pairs_hook=_strict)
    if not isinstance(record, dict) or set(record) != {'schema', 'prior_record', 'prior_envelope', 'checkpoint'} or record['schema'] != 'agi-alpha/source-transition-anchor/v2':
        raise ValueError('HISTORICAL_RECORD_SHAPE_CHANGED')
    old, envelope, checkpoint = record['prior_record'], record['prior_envelope'], record['checkpoint']
    if (sha(canonical(old)) != b['prior_record_sha256'] or sha(canonical(envelope)) != b['prior_journal_sha256']
            or sha(canonical(checkpoint)) != b['checkpoint_sha256'] or envelope.get('body') != old.get('connected_journal')
            or checkpoint.get('body', {}).get('native_sequence') != b['native_sequence']
            or checkpoint.get('body', {}).get('native_actions_sha256') != b['native_actions_sha256']
            or checkpoint.get('body', {}).get('source_sha256') != b['from_source_sha256']):
        raise ValueError('HISTORICAL_RECORD_OR_OPERATING_PREFIX_CHANGED')
    _clock(checkpoint, old, b['day'])
    result = historical_audit(old, envelope, checkpoint)
    if not isinstance(result, dict) or result.get('accepted') is not True or result.get('native_sequence') != b['native_sequence'] or result.get('native_actions_sha256') != b['native_actions_sha256']:
        raise ValueError('MANDATORY_PINNED_HISTORICAL_AUDIT_REJECTED')
    return {'structurally_verified': True, 'anchor_sha256': b['anchor_sha256'],
            'native_sequence': b['native_sequence'], 'counter': b['counter'],
            'historical_audit_receipt_sha256': sha(canonical(result))}
