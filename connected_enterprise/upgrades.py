"""Explicit, owner-authenticated local simulation source transitions.

Historical verifiers run in their pinned source directory. No account secret
is exported, and a transition never replaces the native monetary history.
"""
import copy
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import sys

from commercial.ledger import canonical, digest

from connected_enterprise.transition_evidence import ticket_body, active_directory, record_blobs

DOMAIN = b'native-source-transition\n'
_HISTORICAL_AUDITS = {}
MAX_TICKET_BYTES = 16_000_000


def preflight_ticket_size(output):
    """Reject an impossible v1 upgrade before changing its operator descriptor."""
    from .migration import _read
    output = Path(output).absolute()
    envelope = _read(output / 'account.sqlite.connected-journal.json')
    path = output / 'account.sqlite.adaptive-source-transitions.json'
    transitions = _read(path) if path.exists() else {}
    minimum_record = {'connected_journal': envelope['body']}
    if transitions:
        minimum_record['source_transitions'] = transitions
    lower_bound = len(canonical({'prior_record': minimum_record, 'prior_envelope': envelope}))
    if lower_bound > MAX_TICKET_BYTES:
        raise ValueError('SOURCE_UPGRADE_EXCEEDS_EXISTING_TICKET_BOUND')
    return lower_bound


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
    body = ticket_body(ticket)
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
    from commercial.ledger import load_jobs
    load_jobs(root, manifest)
    cache_key = digest({'ticket': ticket, 'manifest': manifest, 'root': str(root),
                        'verifier_files': body['verifier_files']})
    # Recheck all referenced objects even when a pinned verifier receipt is cached.
    record_blobs(body['prior_record'])
    if cache_key in _HISTORICAL_AUDITS:
        return copy.deepcopy(_HISTORICAL_AUDITS[cache_key])
    payload = {'record': body['prior_record'], 'manifest': manifest, 'root': str(root), 'evidence_root': active_directory()}
    code = ('import json,sys; from contextlib import ExitStack; from pathlib import Path; from connected_enterprise.finance import audit_journal; '
            'p=json.load(sys.stdin); stack=ExitStack(); '
            'scope=__import__("connected_enterprise.transition_evidence",fromlist=["evidence_directory"]).evidence_directory(p["evidence_root"]) if p["evidence_root"] and (Path(p["root"])/"connected_enterprise/transition_evidence.py").is_file() else ExitStack(); '
            'stack.enter_context(scope); r=audit_journal(p["record"],root=p["root"],manifest=p["manifest"]); '
            'assert r["accepted"]; print(json.dumps(r,sort_keys=True))')
    env = {**os.environ, 'PYTHONPATH': str(root), 'PYTHONDONTWRITEBYTECODE': '1'}
    done = subprocess.run([sys.executable, '-c', code], input=json.dumps(payload),
                          text=True, capture_output=True, cwd=root, env=env, timeout=60)
    if done.returncode:
        raise ValueError('PINNED_HISTORICAL_AUDIT_FAILED:' + done.stderr[-1200:])
    receipt = json.loads(done.stdout)
    if not receipt.get('accepted'):
        raise ValueError('PINNED_HISTORICAL_AUDIT_NOT_ACCEPTED')
    if source_inventory(root) != body['verifier_files']:
        raise ValueError('HISTORICAL_VERIFIER_CHANGED_DURING_AUDIT')
    load_jobs(root, manifest)
    if len(_HISTORICAL_AUDITS) >= 128:
        _HISTORICAL_AUDITS.pop(next(iter(_HISTORICAL_AUDITS)))
    _HISTORICAL_AUDITS[cache_key] = copy.deepcopy(receipt)
    return receipt


def authorize_upgrade(*, historical_root, target_root, manifest, path, opening,
                      working, contract, expected_state_digest, ident, day, operating=None,
                      transition_format="v1", evidence_root=None, prepared_ticket=None):
    """Invoke only after the owner has explicitly selected the target source."""
    from connected_enterprise.finance import source_identity
    historical_root, target_root = Path(historical_root).absolute(), Path(target_root).absolute()
    target = source_identity(target_root)
    if transition_format not in {'v1','v2-cas'}:raise ValueError('EXPLICIT_SUPPORTED_TRANSITION_FORMAT_REQUIRED')
    evidence_root = str(Path(evidence_root).absolute()) if evidence_root is not None else active_directory()
    if transition_format == 'v2-cas' and evidence_root is None:raise ValueError('EXPLICIT_TRANSITION_EVIDENCE_SCOPE_REQUIRED')
    if expected_state_digest is None and operating is None:
        raise ValueError('EXPLICIT_SOURCE_UPGRADE_CHECKPOINT_REQUIRED')
    files = source_inventory(historical_root)
    payload = {'root': str(historical_root), 'path': str(Path(path).absolute()),
               'manifest': manifest, 'opening': opening, 'working': working,
               'contract': contract, 'expected': expected_state_digest,
               'target': target, 'ident': ident, 'day': day, 'verifier_files': files,
               'operating': operating, 'transition_format': transition_format, 'evidence_root': evidence_root,
               'serializer': str(target_root/'connected_enterprise/transition_evidence.py'),
               'serializer_sha256': target['files']['connected_enterprise/transition_evidence.py'], 'prepared_ticket': prepared_ticket}

    code = '''import json,sys,hashlib,hmac
from pathlib import Path
from connected_enterprise.finance import JournalAccount
from commercial.ledger import canonical,digest
p=json.load(sys.stdin)
from contextlib import ExitStack
stack=ExitStack()
if p['evidence_root'] and (Path(p['root'])/'connected_enterprise/transition_evidence.py').is_file():
 from connected_enterprise.transition_evidence import evidence_directory
 stack.enter_context(evidence_directory(p['evidence_root']))
with JournalAccount(p['root'],p['manifest'],p['path'],opening=p['opening'],working=p['working'],contract=p['contract']) as a:
 a.audit(); r=a.export()
 if p['expected'] is not None and a.snapshot()['state_digest']!=p['expected']: raise ValueError('STALE_SOURCE_UPGRADE_CHECKPOINT')
 if p['operating'] is not None:
  from connected_enterprise.verify import check_source
  state=a.verify_checkpoint(p['operating']['prior_checkpoint'])
  if state['source']!=p['operating']['from_runtime']:raise ValueError('OPERATING_SOURCE_AUTHORITY_CHANGED')
  check_source(p['root'],state['source'])
  p['expected']=a.snapshot()['state_digest']
  p['day']=max(p['day'],max([e['day'] for e in r['ledger']['actions']],default=0))
 if p['day']<max([e['day'] for e in r['ledger']['actions']],default=0): raise ValueError('SOURCE_UPGRADE_CLOCK_ROLLBACK')
 old=json.loads(a.journal_path.read_text())
 counter=len(r.get('source_transitions',{}))+1
 if not 1<=counter<=4 or p['ident'] in r.get('source_transitions',{}):raise ValueError('SOURCE_UPGRADE_FORWARD_CHAIN_OR_IDENTITY_INVALID')
 seen={t['body']['from_source']['sha256'] for t in r.get('source_transitions',{}).values()}
 if p['target']==a.source or p['target']['sha256'] in seen:raise ValueError('SOURCE_TRANSITION_DOWNGRADE_OR_FORK')
 body={'schema':'agi-alpha/native-source-transition/v1','id':p['ident'],'account_path':p['path'],'from_source':a.source,'to_source':p['target'],'counter':counter,'expected_state_digest':p['expected'],'day':p['day'],'prior_record':r,'prior_envelope':old,'historical_root':p['root'],'verifier_files':p['verifier_files']}
 if p['operating'] is not None:body['operating']=p['operating']
 if p['transition_format']=='v2-cas':
  import importlib.util
  serializer=Path(p['serializer'])
  if serializer.is_symlink() or hashlib.sha256(serializer.read_bytes()).hexdigest()!=p['serializer_sha256']:raise ValueError('TARGET_TRANSITION_SERIALIZER_CHANGED')
  spec=importlib.util.spec_from_file_location('owner_selected_transition_serializer',serializer);codec=importlib.util.module_from_spec(spec);spec.loader.exec_module(codec)
  blobs={};body=codec.externalize(body,blobs)
  codec.persist_evidence(p['evidence_root'],blobs)
 ticket={'body':body,'signature':hmac.new(a._account._key,b'native-source-transition\\n'+canonical(body),hashlib.sha256).hexdigest()}
 if len(canonical(ticket))>16_000_000:raise ValueError('SOURCE_UPGRADE_EXCEEDS_EXISTING_TICKET_BOUND')
 if len(canonical({**r.get('source_transitions',{}),p['ident']:ticket}))+1>32_000_000:raise ValueError('BOUNDED_SOURCE_AUTHORIZATION_MAP_REQUIRED')
 # Conservative complete migration margin covers both pending/final receipts.
 if len(canonical(old))+len(canonical(ticket))+len(canonical(p['target']))+1_000_000>64_000_000:raise ValueError('BOUNDED_RESOURCE_JOURNAL_REQUIRED')
 if p['prepared_ticket'] is not None:
  if p['prepared_ticket']!=ticket:raise ValueError('PREPARED_SOURCE_AUTHORIZATION_CHANGED')
  ticket=p['prepared_ticket']
 print(json.dumps(ticket,sort_keys=True))
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
    body = ticket_body(ticket)
    return {'id': body['id'], 'from_source': body['from_source']['sha256'],
            'to_source': body['to_source']['sha256'], 'counter': body['counter'],
            'checkpoint_sha256': digest(body['prior_record'])}


def validate_ticket(ticket, *, key=None, root=None, path=None):
    fields = {'schema', 'id', 'account_path', 'from_source', 'to_source', 'counter',
              'expected_state_digest', 'day', 'prior_record', 'prior_envelope',
              'historical_root', 'verifier_files'}
    if not isinstance(ticket, dict) or set(ticket) != {'body', 'signature'}:
        raise ValueError('EXACT_SOURCE_TRANSITION_AUTHORIZATION_REQUIRED')
    body = ticket_body(ticket, key=key)
    if not isinstance(body, dict) or set(body) not in [fields, fields | {'operating'}] or body['schema'] != 'agi-alpha/native-source-transition/v1':
        raise ValueError('EXACT_SOURCE_TRANSITION_BODY_REQUIRED')
    if type(body['counter']) is not int or not 1 <= body['counter'] <= 4 or type(body['day']) is not int or body['day'] < 0:
        raise ValueError('SOURCE_TRANSITION_COUNTER_AND_CLOCK_REQUIRED')
    if len(canonical(ticket)) > MAX_TICKET_BYTES:
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
        expected = hmac.new(key, DOMAIN + canonical(ticket['body']), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, str(ticket['signature'])):
            raise ValueError('SOURCE_TRANSITION_SIGNATURE_MISMATCH')
    record = body['prior_record']
    if body['expected_state_digest'] != record['snapshot']['state_digest']:
        raise ValueError('SOURCE_TRANSITION_CHECKPOINT_CHANGED')
    if body['prior_envelope']['body'] != record['connected_journal']:
        raise ValueError('ORIGINAL_SIGNED_JOURNAL_NOT_PRESERVED')
    if 'operating' in body:
        from .migration import validate_operating_authority
        validate_operating_authority(ticket, key=key, root=root)
    return body


def recover_transition_evidence(historical_root, manifest, output, *, expected_checkpoint, ident):
    """Preserve interrupted objects under existing owner authority, never repair history."""
    from enterprise.runner import RunLock
    import re
    if not isinstance(ident,str) or re.fullmatch('[A-Za-z0-9_-]{1,80}',ident) is None:
        raise ValueError('SAFE_TRANSITION_RECOVERY_ID_REQUIRED')
    root=Path(historical_root).absolute();output=Path(output).absolute()
    serializer=Path(__file__).with_name('transition_evidence.py')
    payload={'root':str(root),'output':str(output),'manifest':manifest,'expected':expected_checkpoint,'id':ident,
             'serializer':str(serializer),'serializer_sha256':hashlib.sha256(serializer.read_bytes()).hexdigest()}
    code=r'''
import json,sys,hashlib,hmac,importlib.util
from pathlib import Path
from contextlib import ExitStack
from commercial.ledger import canonical,digest,strict_json
from commercial.persistence import atomic_bytes
from connected_enterprise.finance import JournalAccount
p=json.load(sys.stdin);out=Path(p['output']);state_raw=(out/'STATE.json').read_bytes();state=strict_json(state_raw)
if digest(state)!=p['expected']:raise ValueError('STALE_TRANSITION_RECOVERY_CHECKPOINT')
journal=strict_json((out/'account.sqlite.connected-journal.json').read_bytes())['body']
serializer=Path(p['serializer'])
if serializer.is_symlink() or hashlib.sha256(serializer.read_bytes()).hexdigest()!=p['serializer_sha256']:raise ValueError('RECOVERY_SERIALIZER_CHANGED')
spec=importlib.util.spec_from_file_location('owner_recovery_serializer',serializer);codec=importlib.util.module_from_spec(spec);spec.loader.exec_module(codec)
stack=ExitStack()
if (Path(p['root'])/'connected_enterprise/transition_evidence.py').is_file():
 from connected_enterprise.transition_evidence import evidence_directory
 stack.enter_context(evidence_directory(out/'TRANSITION_EVIDENCE'))
with JournalAccount(p['root'],p['manifest'],out/'account.sqlite',opening=journal['opening'],working=journal['working'],contract=journal['contract']) as a:
 a.audit();a.verify_checkpoint(state);before=a.export()
 rows=codec.recover_stages(out/'TRANSITION_EVIDENCE')
 body={'schema':'agi-alpha/transition-evidence-recovery/v1','id':p['id'],'source':a.source,
       'expected_checkpoint_sha256':p['expected'],'native_actions_sha256':before['ledger']['actions_sha256'],
       'objects':rows,'serializer_sha256':p['serializer_sha256'],
       'scope':'Preserved interrupted object bytes; no published content, account history, key or liability altered'}
 receipt={'body':body,'signature':hmac.new(a._account._key,b'connected-transition-evidence-recovery\n'+canonical(body),hashlib.sha256).hexdigest()}
 archive=out/'TRANSITION_RECOVERY';archive.mkdir(exist_ok=True)
 if archive.is_symlink():raise ValueError('RECOVERY_ARCHIVE_SYMLINK_REFUSED')
 path=archive/(p['id']+'.json');raw=canonical(receipt)+b'\n'
 if path.exists() and path.read_bytes()!=raw:raise ValueError('TRANSITION_RECOVERY_ID_REUSE_REFUSED')
 if not path.exists():atomic_bytes(path,raw)
 if (out/'STATE.json').read_bytes()!=state_raw or a.export()!=before:raise ValueError('TRANSITION_RECOVERY_CHANGED_HISTORY')
 print(json.dumps({'accepted':True,'receipt':receipt,'account_history_unchanged':True},sort_keys=True))
'''
    files=source_inventory(root)
    with RunLock(output):
        done=subprocess.run([sys.executable,'-c',code],input=json.dumps(payload),text=True,capture_output=True,
            cwd=root,env={**os.environ,'PYTHONPATH':str(root),'PYTHONDONTWRITEBYTECODE':'1'},timeout=120)
    if done.returncode:raise ValueError('OWNER_TRANSITION_RECOVERY_FAILED:'+done.stderr[-2000:])
    if source_inventory(root)!=files:raise ValueError('HISTORICAL_SOURCE_CHANGED_DURING_RECOVERY')
    return json.loads(done.stdout)
