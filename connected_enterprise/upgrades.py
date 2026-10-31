"""Explicit, owner-authenticated local simulation source transitions.

Historical verifiers run in their pinned source directory. No account secret
is exported, and a transition never replaces the native monetary history.
"""
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import sys

from commercial.ledger import canonical, digest

DOMAIN = b'native-source-transition\n'


def source_inventory(root):
    root = Path(root).absolute()
    files = {}
    for path in sorted(root.rglob('*.py')):
        relative = path.relative_to(root)
        if any(part in {'__pycache__', '.git', '.venv', 'historical-source-versions'} for part in relative.parts):
            continue
        if any(p.is_symlink() for p in [path, *path.parents]):
            raise ValueError('HISTORICAL_SOURCE_SYMLINK_REFUSED')
        files[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not files or len(files) > 4000:
        raise ValueError('BOUNDED_PINNED_HISTORICAL_SOURCE_REQUIRED')
    return files


def verify_historical(ticket, manifest, *, root=None):
    body = ticket['body']
    candidates = [Path(body['historical_root']).absolute()]
    if root is not None:
        candidates.append(Path(root).absolute() / 'historical-source-versions' / body['from_source']['sha256'])
    selected = None
    for candidate in candidates:
        try:
            if candidate.is_dir() and source_inventory(candidate) == body['verifier_files']:
                selected = candidate
                break
        except (ValueError, OSError):
            continue
    if selected is None:
        raise ValueError('PINNED_HISTORICAL_VERIFIER_CHANGED')
    root = selected
    payload = {'record': body['prior_record'], 'manifest': manifest, 'root': str(root)}
    code = ('import json,sys; from connected_enterprise.finance import audit_journal; '
            'p=json.load(sys.stdin); r=audit_journal(p["record"],root=p["root"],manifest=p["manifest"]); '
            'assert r["accepted"]; print(json.dumps(r,sort_keys=True))')
    env = {**os.environ, 'PYTHONPATH': str(root), 'PYTHONDONTWRITEBYTECODE': '1'}
    done = subprocess.run([sys.executable, '-c', code], input=json.dumps(payload),
                          text=True, capture_output=True, cwd=root, env=env, timeout=60)
    if done.returncode:
        raise ValueError('PINNED_HISTORICAL_AUDIT_FAILED:' + done.stderr[-1200:])
    receipt = json.loads(done.stdout)
    if not receipt.get('accepted'):
        raise ValueError('PINNED_HISTORICAL_AUDIT_NOT_ACCEPTED')
    return receipt


def authorize_upgrade(*, historical_root, target_root, manifest, path, opening,
                      working, contract, expected_state_digest, ident, day):
    """Invoke only after the owner has explicitly selected the target source."""
    from connected_enterprise.finance import source_identity
    historical_root, target_root = Path(historical_root).absolute(), Path(target_root).absolute()
    target = source_identity(target_root)
    files = source_inventory(historical_root)
    payload = {'root': str(historical_root), 'path': str(Path(path).absolute()),
               'manifest': manifest, 'opening': opening, 'working': working,
               'contract': contract, 'expected': expected_state_digest,
               'target': target, 'ident': ident, 'day': day, 'verifier_files': files}
    code = '''import json,sys,hashlib,hmac
from pathlib import Path
from connected_enterprise.finance import JournalAccount
from commercial.ledger import canonical,digest
p=json.load(sys.stdin)
with JournalAccount(p['root'],p['manifest'],p['path'],opening=p['opening'],working=p['working'],contract=p['contract']) as a:
 a.audit(); r=a.export()
 if a.snapshot()['state_digest']!=p['expected']: raise ValueError('STALE_SOURCE_UPGRADE_CHECKPOINT')
 if p['day']<max([e['day'] for e in r['ledger']['actions']],default=0): raise ValueError('SOURCE_UPGRADE_CLOCK_ROLLBACK')
 old=json.loads(a.journal_path.read_text())
 counter=len(r.get('source_transitions',{}))+1
 body={'schema':'agi-alpha/native-source-transition/v1','id':p['ident'],'account_path':p['path'],'from_source':a.source,'to_source':p['target'],'counter':counter,'expected_state_digest':p['expected'],'day':p['day'],'prior_record':r,'prior_envelope':old,'historical_root':p['root'],'verifier_files':p['verifier_files']}
 print(json.dumps({'body':body,'signature':hmac.new(a._account._key,b'native-source-transition\\n'+canonical(body),hashlib.sha256).hexdigest()},sort_keys=True))
'''
    env = {**os.environ, 'PYTHONPATH': str(historical_root), 'PYTHONDONTWRITEBYTECODE': '1'}
    done = subprocess.run([sys.executable, '-c', code], input=json.dumps(payload),
                          text=True, capture_output=True, cwd=historical_root, env=env, timeout=60)
    if done.returncode:
        raise ValueError('SOURCE_UPGRADE_AUTHORIZATION_FAILED:' + done.stderr[-1200:])
    ticket = json.loads(done.stdout)
    if source_inventory(historical_root) != files:
        raise ValueError('HISTORICAL_SOURCE_CHANGED_DURING_AUTHORIZATION')
    return ticket


def transition_args(ticket):
    body = ticket['body']
    return {'id': body['id'], 'from_source': body['from_source']['sha256'],
            'to_source': body['to_source']['sha256'], 'counter': body['counter'],
            'checkpoint_sha256': digest(body['prior_record'])}


def validate_ticket(ticket, *, key=None, root=None, path=None):
    fields = {'schema', 'id', 'account_path', 'from_source', 'to_source', 'counter',
              'expected_state_digest', 'day', 'prior_record', 'prior_envelope',
              'historical_root', 'verifier_files'}
    if not isinstance(ticket, dict) or set(ticket) != {'body', 'signature'}:
        raise ValueError('EXACT_SOURCE_TRANSITION_AUTHORIZATION_REQUIRED')
    body = ticket['body']
    if not isinstance(body, dict) or set(body) != fields or body['schema'] != 'agi-alpha/native-source-transition/v1':
        raise ValueError('EXACT_SOURCE_TRANSITION_BODY_REQUIRED')
    if type(body['counter']) is not int or not 1 <= body['counter'] <= 4 or type(body['day']) is not int or body['day'] < 0:
        raise ValueError('SOURCE_TRANSITION_COUNTER_AND_CLOCK_REQUIRED')
    if len(canonical(ticket)) > 16_000_000:
        raise ValueError('BOUNDED_SOURCE_TRANSITION_REQUIRED')
    for source in [body['from_source'], body['to_source']]:
        if set(source) != {'files', 'sha256'} or digest(source['files']) != source['sha256']:
            raise ValueError('SOURCE_TRANSITION_IDENTITY_MISMATCH')
    if body['from_source'] == body['to_source']:
        raise ValueError('DISTINCT_FORWARD_SOURCE_TRANSITION_REQUIRED')
    if path is not None and body['account_path'] != str(Path(path).absolute()):
        raise ValueError('SOURCE_TRANSITION_ACCOUNT_IDENTITY_CHANGED')
    if root is not None:
        from connected_enterprise.finance import source_identity
        if body['to_source'] != source_identity(root):
            raise ValueError('SOURCE_TRANSITION_TARGET_CHANGED')
    if key is not None:
        expected = hmac.new(key, DOMAIN + canonical(body), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, str(ticket['signature'])):
            raise ValueError('SOURCE_TRANSITION_SIGNATURE_MISMATCH')
    record = body['prior_record']
    if body['expected_state_digest'] != record['snapshot']['state_digest']:
        raise ValueError('SOURCE_TRANSITION_CHECKPOINT_CHANGED')
    if body['prior_envelope']['body'] != record['connected_journal']:
        raise ValueError('ORIGINAL_SIGNED_JOURNAL_NOT_PRESERVED')
    return body
