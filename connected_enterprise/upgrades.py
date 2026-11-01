"""Explicit, owner-authenticated local simulation source transitions.

Historical verifiers run in their pinned source directory. No account secret
is exported, and a transition never replaces the native monetary history.
"""
import copy
import contextvars
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import sys

from commercial.ledger import canonical, digest

from connected_enterprise.transition_evidence import ticket_body, current_store_directory

DOMAIN = b'native-source-transition\n'
_HISTORICAL_AUDITS = {}
_OWNER_AUTHORIZED_HISTORY = contextvars.ContextVar('owner_authorized_historical_audit', default=frozenset())
MAX_TICKET_BYTES = 16_000_000


@contextmanager
def _owner_authenticated_history(tickets, key):
    """Only callers holding an existing Account key may authorize historical code."""
    if not isinstance(key, bytes) or len(key) < 16:
        raise ValueError('OWNED_ACCOUNT_HMAC_AUTHORITY_REQUIRED')
    signed = set()
    for ticket in tickets:
        ticket_body(ticket, key=key)
        signed.add(digest(ticket))
    token = _OWNER_AUTHORIZED_HISTORY.set(_OWNER_AUTHORIZED_HISTORY.get() | frozenset(signed))
    try:
        yield
    finally:
        _OWNER_AUTHORIZED_HISTORY.reset(token)

# Exact reviewed implementation; this is a narrow signer's codec allowlist, not
# permission to execute new replacement-runtime Python in an account owner.
PINNED_OWNER_EVIDENCE_CODEC_SHA256 = 'edce19ed4addf94027f3d040e5a5779ec150a867df8ed5b6bf8a0f1e2c0868a9'


def reviewed_owner_codec_source(target_root):
    owner_bytes = Path(__file__).with_name('transition_evidence.py').read_bytes()
    if hashlib.sha256(owner_bytes).hexdigest() != PINNED_OWNER_EVIDENCE_CODEC_SHA256:
        raise ValueError('OWNER_EVIDENCE_CODEC_SOURCE_CHANGED')
    candidate = (Path(target_root) / 'connected_enterprise/transition_evidence.py').read_bytes()
    if hashlib.sha256(candidate).hexdigest() != PINNED_OWNER_EVIDENCE_CODEC_SHA256:
        raise ValueError('UNREVIEWED_TARGET_EVIDENCE_CODEC')
    return owner_bytes.decode('utf-8')


# A signed ticket's .py inventory does not cover native module precedence,
# sourceless bytecode, or executable archives. Reject before historical imports;
# this does not make historical Python a sandbox or authorize unknown sources.
_UNREGISTERED_IMPORT_SUFFIXES = ('.so', '.pyd', '.dll', '.dylib', '.pyo', '.pth', '.egg', '.whl', '.zip')


def _reject_unregistered_python_executables(root):
    root = Path(root).absolute()
    for item in (root, *root.parents):
        if item.is_symlink():
            raise ValueError('HISTORICAL_SOURCE_SYMLINK_REFUSED')
    if not root.is_dir():
        raise ValueError('PINNED_HISTORICAL_SOURCE_DIRECTORY_REQUIRED')
    for item in root.rglob('*'):
        if item.is_symlink():
            raise ValueError('HISTORICAL_SOURCE_SYMLINK_REFUSED')
        if item.is_file() and (item.suffix.lower() in _UNREGISTERED_IMPORT_SUFFIXES
                              or item.suffix.lower() == '.pyc' and '__pycache__' not in item.parts):
            raise ValueError('UNREGISTERED_HISTORICAL_EXECUTABLE_REFUSED')


def _run_pinned_historical_python(root, code, payload):
    """Use isolated interpreter startup and reject unsigned native imports both
    before launch and in the child before historical code enters sys.path.
    """
    from tempfile import TemporaryDirectory
    root = Path(root).absolute()
    _reject_unregistered_python_executables(root)
    with TemporaryDirectory(prefix='agi-alpha-pinned-history-pycache-') as cache:
        # -I ignores PYTHONPATH and cwd during startup; installed packages remain
        # available. The trusted -c bootstrap inserts the tree only after checks.
        bootstrap = f"""import pathlib,sys
root=pathlib.Path({str(root)!r})
blocked={_UNREGISTERED_IMPORT_SUFFIXES!r}
for item in (root,*root.parents):
 if item.is_symlink():raise SystemExit('HISTORICAL_SOURCE_SYMLINK_REFUSED')
for item in root.rglob('*'):
 if item.is_symlink():raise SystemExit('HISTORICAL_SOURCE_SYMLINK_REFUSED')
 if item.is_file() and (item.suffix.lower() in blocked or (item.suffix.lower()=='.pyc' and '__pycache__' not in item.parts)):
  raise SystemExit('UNREGISTERED_HISTORICAL_EXECUTABLE_REFUSED')
sys.pycache_prefix={cache!r}
sys.dont_write_bytecode=True
sys.path.insert(0,str(root))
"""
        env = {'PYTHONPATH': str(root), 'PYTHONDONTWRITEBYTECODE': '1',
               'PYTHONPYCACHEPREFIX': cache, 'PYTHONNOUSERSITE': '1',
               'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'LC_ALL': 'C.UTF-8'}
        return subprocess.run([sys.executable, '-I', '-c', bootstrap + code], input=json.dumps(payload),
                              text=True, capture_output=True, cwd=root, env=env, timeout=60)


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
    _reject_unregistered_python_executables(root)
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
    if digest(ticket) not in _OWNER_AUTHORIZED_HISTORY.get():
        raise ValueError('INDEPENDENT_HISTORICAL_VERIFIER_AUTHORITY_REQUIRED')
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
    if cache_key in _HISTORICAL_AUDITS:
        return copy.deepcopy(_HISTORICAL_AUDITS[cache_key])
    payload = {'record': body['prior_record'], 'manifest': manifest, 'root': str(root), 'evidence_dir': current_store_directory()}
    code = """import json,sys,contextlib,importlib.util
from connected_enterprise.finance import audit_journal
p=json.load(sys.stdin);scope=contextlib.nullcontext()
if p.get('evidence_dir') and importlib.util.find_spec('connected_enterprise.transition_evidence'):
 from connected_enterprise.transition_evidence import evidence_directory
 scope=evidence_directory(p['evidence_dir'])
with scope:
 r=audit_journal(p['record'],root=p['root'],manifest=p['manifest'])
 assert r['accepted'];print(json.dumps(r,sort_keys=True))
"""
    done = _run_pinned_historical_python(root, code, payload)
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


AUTHORIZATION_REUSE_HELPER = "import stat\n\ndef clean_authorization_snapshot(root, path, operating):\n # Eligibility only, not authentication. The original historical constructor and\n # verify_checkpoint still authenticate/audit the final owned record.\n root=Path(root);path=Path(path)\n if operating is None:return None\n known='05b102ee40510b59c7693002251996ade2a03a3c383a885c08cedda54abf619a'\n finance=root/'connected_enterprise/finance.py'\n try:\n  if hashlib.sha256(finance.read_bytes()).hexdigest()!=known:return None\n  intent=path.with_name(path.name+'.operating-checkpoint-intent.json')\n  if intent.exists() or intent.is_symlink():return None\n  names=[path,path.with_name(path.name+'.actions.jsonl'),path.with_name(path.name+'.connected-journal.json'),path.parent/'STATE.json']\n  names += [path.with_name(path.name+suffix) for suffix in ['.adaptive-proofs.json','.adaptive-resolutions.json','.adaptive-source-transitions.json','.adaptive-connected-source.json','.adaptive-account.json','.persistence.json']]\n  fingerprint={};raws={}\n  for index,name in enumerate(names):\n   if any(p.is_symlink() for p in [name,*name.parents]):return None\n   if not name.exists():\n    if index<4:return None\n    fingerprint[str(name)]=None;continue\n   info=name.stat()\n   if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>64_000_000:return None\n   raw=name.read_bytes();fingerprint[str(name)]=hashlib.sha256(raw).hexdigest();raws[str(name)]=raw\n  from commercial.ledger import strict_json\n  journal=strict_json(raws[str(names[2])])\n  if not isinstance(journal,dict) or set(journal)!={'body','signature'}:return None\n  entries=journal['body']['entries']\n  if not isinstance(entries,list) or any(e.get('status') not in {'COMPLETE','REJECTED'} for e in entries):return None\n  if strict_json(raws[str(names[3])])!=operating['prior_checkpoint']:return None\n  return fingerprint\n except (OSError,ValueError,KeyError,TypeError,AttributeError):return None\n\n"

def authorize_upgrade(*, historical_root, target_root, manifest, path, opening,
                      working, contract, expected_state_digest, ident, day, operating=None, evidence_dir=None):
    """Invoke only after the owner has explicitly selected the target source."""
    from connected_enterprise.finance import source_identity
    historical_root, target_root = Path(historical_root).absolute(), Path(target_root).absolute()
    target = source_identity(target_root)
    if expected_state_digest is None and operating is None:
        raise ValueError('EXPLICIT_SOURCE_UPGRADE_CHECKPOINT_REQUIRED')
    files = source_inventory(historical_root)
    if evidence_dir is not None:
        evidence_dir=Path(evidence_dir).absolute()
        if any(p.is_symlink() for p in [evidence_dir,*evidence_dir.parents]):raise ValueError('EVIDENCE_DIRECTORY_SYMLINK_REFUSED')
        evidence_dir.mkdir(mode=0o700,exist_ok=True)
    payload = {'root': str(historical_root), 'path': str(Path(path).absolute()),
               'manifest': manifest, 'opening': opening, 'working': working,
               'contract': contract, 'expected': expected_state_digest,
               'target': target, 'ident': ident, 'day': day, 'verifier_files': files,
               'operating': operating, 'evidence_dir': str(Path(evidence_dir).absolute()) if evidence_dir else None,
               'codec_source': reviewed_owner_codec_source(target_root) if evidence_dir else None}
    code = AUTHORIZATION_REUSE_HELPER + '''import json,sys,hashlib,hmac,contextlib,importlib.util
from pathlib import Path
from connected_enterprise.finance import JournalAccount
from commercial.ledger import canonical,digest
p=json.load(sys.stdin)
if p['evidence_dir']:
 if not isinstance(p.get('codec_source'),str) or hashlib.sha256(p['codec_source'].encode('utf-8')).hexdigest()!='edce19ed4addf94027f3d040e5a5779ec150a867df8ed5b6bf8a0f1e2c0868a9':
  raise ValueError('UNREVIEWED_OWNER_SIGNING_CODEC')
scope=contextlib.nullcontext()
if p['evidence_dir'] and importlib.util.find_spec('connected_enterprise.transition_evidence'):
 from connected_enterprise.transition_evidence import evidence_directory
 scope=evidence_directory(p['evidence_dir'])
before=clean_authorization_snapshot(p['root'],p['path'],p['operating'])
with scope, JournalAccount(p['root'],p['manifest'],p['path'],opening=p['opening'],working=p['working'],contract=p['contract']) as a:
 after=clean_authorization_snapshot(p['root'],p['path'],p['operating'])
 reuse=before is not None and before==after
 if not reuse:a.audit()
 r=a.export()
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
 body={'schema':'agi-alpha/native-source-transition/v1','id':p['ident'],'account_path':p['path'],'from_source':a.source,'to_source':p['target'],'counter':counter,'expected_state_digest':p['expected'],'day':p['day'],'prior_record':r,'prior_envelope':old,'historical_root':p['root'],'verifier_files':p['verifier_files']}
 if p['operating'] is not None:body['operating']=p['operating']
 if p['evidence_dir']:
  codec={};exec(p['codec_source'],codec);blobs={}
  body=codec['externalize'](body,blobs)
  unsigned={'body':body,'signature':'0'*64}
  codec['preflight_storage'](unsigned,r,old)
  codec['persist_evidence'](p['evidence_dir'],blobs)
 if reuse and clean_authorization_snapshot(p['root'],p['path'],p['operating'])!=after:raise ValueError('OWNER_AUTHORITY_CHANGED_DURING_AUTHORIZATION')
 print(json.dumps({'body':body,'signature':hmac.new(a._account._key,b'native-source-transition\\n'+canonical(body),hashlib.sha256).hexdigest()},sort_keys=True))
'''
    done = _run_pinned_historical_python(historical_root, code, payload)
    if done.returncode:
        raise ValueError('SOURCE_UPGRADE_AUTHORIZATION_FAILED:' + done.stderr[-1200:])
    ticket = json.loads(done.stdout)
    if source_identity(target_root)!=target:raise ValueError('TARGET_CHANGED_DURING_AUTHORIZATION')
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
