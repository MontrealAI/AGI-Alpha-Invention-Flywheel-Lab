"""P0-248: pure historical-owner v2-CAS wire-shape compatibility reference.

Research only. This module neither reads target-source code nor signs, mutates,
opens, or authenticates an account. Existing owner HMAC/locking/recovery must
validate and commit any real transition separately.
"""
import hashlib
import json
import math
import re

V1 = 'agi-alpha/native-source-transition/v1'
V2 = 'agi-alpha/native-source-transition/v2-cas'
BASE_FIELDS = frozenset(('schema', 'id', 'account_path', 'from_source',
                         'to_source', 'counter', 'expected_state_digest',
                         'day', 'historical_root', 'verifier_files'))
REQUIRED_EVIDENCE = frozenset(('prior_record', 'prior_envelope'))
MAX_TICKET_BYTES = 16_000_000
MAX_BLOB_BYTES = 64_000_000
MAX_BUNDLE_BYTES = 512 * 1024 * 1024
MAX_BUNDLE_FILES = 10_000
SHA = re.compile(r'[0-9a-f]{64}\Z')


def _plain(x, depth=0):
    if depth > 128:
        raise ValueError('JSON_DEPTH_BOUND')
    if x is None or type(x) in (str, bool, int):
        return
    if type(x) is float and math.isfinite(x):
        return
    if type(x) is list:
        for v in x:
            _plain(v, depth + 1)
        return
    if type(x) is dict:
        for k, v in x.items():
            if type(k) is not str:
                raise ValueError('STRING_KEYS_REQUIRED')
            _plain(v, depth + 1)
        return
    raise ValueError('PLAIN_FINITE_JSON_REQUIRED')


def canonical(x):
    _plain(x)
    # Match the historical owner's ASCII-escaped canonical wire representation.
    return json.dumps(x, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf-8')


def _unique(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError('DUPLICATE_KEY')
        d[k] = v
    return d


def _bad_constant(_):
    raise ValueError('NONFINITE_JSON')


def _budget(raw):
    depth = 0
    nodes = 0
    quoted = escaped = primitive = False
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
            continue
        if byte == 34:
            quoted = True
            nodes += 1
            primitive = False
        elif byte in (91, 123):
            depth += 1
            nodes += 1
            primitive = False
        elif byte in (93, 125):
            depth -= 1
            primitive = False
            if depth < 0:
                raise ValueError('JSON_DEPTH_BOUND')
        elif byte in (9, 10, 13, 32, 44, 58):
            primitive = False
        elif not primitive:
            nodes += 1
            primitive = True
        if depth > 128 or nodes > 2_000_000:
            raise ValueError('JSON_DEPTH_OR_NODE_BOUND')
    if quoted or depth:
        raise ValueError('INVALID_JSON_STRUCTURE')


def strict_blob(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BLOB_BYTES:
        raise ValueError('BOUNDED_BLOB_REQUIRED')
    _budget(raw)
    try:
        parsed = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique,
                            parse_constant=_bad_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError('STRICT_JSON_REQUIRED') from exc
    if type(parsed) is not dict or canonical(parsed) != raw:
        raise ValueError('CANONICAL_DICT_BLOB_REQUIRED')
    return parsed


def _validate_v1(original):
    if type(original) is not dict or original.get('schema') != V1:
        raise ValueError('EXACT_V1_BODY_REQUIRED')
    names = set(original)
    if names not in (BASE_FIELDS | REQUIRED_EVIDENCE,
                     BASE_FIELDS | REQUIRED_EVIDENCE | {'operating'}):
        raise ValueError('EXACT_V1_FIELDS_REQUIRED')
    for name in REQUIRED_EVIDENCE | ({'operating'} if 'operating' in original else set()):
        if type(original[name]) is not dict:
            raise ValueError('OWNER_EVIDENCE_DICT_REQUIRED')
    canonical(original)


def externalize_owner_v2(original):
    """Construct three-field-compatible owner v2 shape; no signer or file I/O."""
    _validate_v1(original)
    fields = sorted(REQUIRED_EVIDENCE | ({'operating'} if 'operating' in original else set()))
    blobs = {}
    refs = {}
    for field in fields:
        raw = canonical(original[field])
        if not 0 < len(raw) <= MAX_BLOB_BYTES:
            raise ValueError('EXISTING_BLOB_BOUND')
        sha = hashlib.sha256(raw).hexdigest()  # historical owner wire convention
        blobs[sha] = raw
        refs[field] = {'sha256': sha, 'bytes': len(raw)}
    if len(blobs) > MAX_BUNDLE_FILES or sum(map(len, blobs.values())) > MAX_BUNDLE_BYTES:
        raise ValueError('EXISTING_BUNDLE_BOUND')
    result = {k: json.loads(canonical(original[k])) for k in BASE_FIELDS}
    result['schema'] = V2
    result['evidence'] = refs
    if len(canonical({'body': result, 'signature': '0' * 64})) > MAX_TICKET_BYTES:
        raise ValueError('EXISTING_SIGNED_TICKET_BOUND')
    return result, blobs


def owner_pre_sign_compare(trusted_original, proposed, blobs):
    """Fail-closed exact comparison to a signer-owned freshly authenticated body.

    This cannot authorize HMAC, decide account authority, or repair operating
    queues by itself. The actual owner process must enforce those separately.
    """
    _validate_v1(trusted_original)
    if type(proposed) is not dict or set(proposed) != BASE_FIELDS | {'evidence'}:
        raise ValueError('EXACT_OWNER_V2_BODY_REQUIRED')
    if proposed['schema'] != V2 or type(proposed['evidence']) is not dict:
        raise ValueError('OWNER_V2_SCHEMA_REQUIRED')
    expected_fields = REQUIRED_EVIDENCE | ({'operating'} if 'operating' in trusted_original else set())
    if set(proposed['evidence']) != expected_fields:
        raise ValueError('EXACT_OWNER_V2_REFERENCES_REQUIRED')
    if type(blobs) is not dict or len(blobs) > MAX_BUNDLE_FILES:
        raise ValueError('BOUNDED_BUNDLE_REQUIRED')
    if any(type(k) is not str or type(v) is not bytes for k, v in blobs.items()):
        raise ValueError('PLAIN_BLOB_MAP_REQUIRED')
    if sum(map(len, blobs.values())) > MAX_BUNDLE_BYTES:
        raise ValueError('BOUNDED_BUNDLE_REQUIRED')
    if len(canonical({'body': proposed, 'signature': '0' * 64})) > MAX_TICKET_BYTES:
        raise ValueError('EXISTING_SIGNED_TICKET_BOUND')
    resolved = {k: proposed[k] for k in BASE_FIELDS}
    resolved['schema'] = V1
    used = set()
    for field in sorted(expected_fields):
        ref = proposed['evidence'][field]
        if type(ref) is not dict or set(ref) != {'sha256', 'bytes'}:
            raise ValueError('EXACT_OWNER_BLOB_REF_REQUIRED')
        sha, n = ref['sha256'], ref['bytes']
        if type(sha) is not str or not SHA.fullmatch(sha) or type(n) is not int or not 0 < n <= MAX_BLOB_BYTES:
            raise ValueError('BOUNDED_OWNER_BLOB_REF_REQUIRED')
        raw = blobs.get(sha)
        if raw is None or len(raw) != n or hashlib.sha256(raw).hexdigest() != sha:
            raise ValueError('OWNER_BLOB_CONTENT_OR_SIZE_CHANGED')
        resolved[field] = strict_blob(raw)
        used.add(sha)
    if set(blobs) != used:
        raise ValueError('EXTRANEOUS_BLOB_REFUSED')
    if canonical(resolved) != canonical(trusted_original):
        raise ValueError('HISTORICAL_OWNER_HISTORY_OR_QUEUE_CHANGED')
    return canonical(proposed)
