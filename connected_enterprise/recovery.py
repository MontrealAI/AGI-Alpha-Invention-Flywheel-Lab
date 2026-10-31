"""Compatible metadata recovery using the unchanged account's pinned verifier."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from commercial.ledger import digest, strict_json
from enterprise.runner import RunLock

VERIFY = r'''
import hashlib,hmac,json,sys,os
from pathlib import Path
from adaptive_enterprise.account import Account,audit_account
from commercial.ledger import canonical,digest,strict_json,operating_state_digest
from commercial.persistence import atomic_bytes
from connected_enterprise.finance import audit_journal,source_identity
from connected_enterprise.verify import check_source
from connected_enterprise.upgrades import validate_ticket
p=json.load(sys.stdin);out=Path(p['output']);account_path=out/'account.sqlite'
from contextlib import ExitStack
stack=ExitStack()
if (out/'TRANSITION_EVIDENCE').exists():
 from connected_enterprise.transition_evidence import evidence_directory
 stack.enter_context(evidence_directory(out/'TRANSITION_EVIDENCE'))
required=[account_path,out/'STATE.json',out/'account.sqlite.actions.jsonl',out/'account.sqlite.adaptive-simulation-key',out/'account.sqlite.connected-journal.json']
if any(not f.is_file() or f.is_symlink() for f in required):raise ValueError('EXISTING_OWNED_RECOVERY_FILES_REQUIRED')
journal_path=out/'account.sqlite.connected-journal.json';journal_raw=journal_path.read_bytes();journal=strict_json(journal_raw);header=journal['body']
state_raw=(out/'STATE.json').read_bytes();state=strict_json(state_raw)
if digest(state)!=p['expected']:raise ValueError('STALE_COMPATIBLE_RECOVERY_CHECKPOINT')
intent_path=out/'account.sqlite.operating-checkpoint-intent.json'
if not intent_path.is_file() or intent_path.is_symlink():raise ValueError('EXISTING_OPERATING_INTENT_REQUIRED')
intent_raw=intent_path.read_bytes();intent=strict_json(intent_raw)
before_tape=(out/'account.sqlite.actions.jsonl').read_bytes();before_key_inode=required[3].stat().st_ino
with Account(p['root'],p['manifest'],account_path,opening=header['opening'],working=header['working'],contract=header['contract']) as owner:
 def signed(envelope,domain):
  return hmac.compare_digest(str(envelope.get('signature')),hmac.new(owner._key,domain+canonical(envelope['body']),hashlib.sha256).hexdigest())
 if not signed(journal,b'connected014-journal\n') or not signed(state,b'connected014-operating-state\n') or not signed(intent,b'connected-operating-checkpoint-intent\n'):raise ValueError('COMPATIBLE_RECOVERY_SIGNATURE_MISMATCH')
 record=owner.export();record['connected_journal']=header;record['connected_journal_sha256']=digest(header)
 if not audit_account(record,root=p['root'],manifest=p['manifest'])['accepted'] or not audit_journal(record,root=p['root'],manifest=p['manifest'])['accepted']:raise ValueError('PINNED_CANONICAL_FINANCIAL_AUDIT_REQUIRED')
 if any(e['status']=='PENDING' for e in header['entries']):raise ValueError('UNRESOLVED_FINANCIAL_WAL_CANNOT_BE_METADATA_RECOVERED')
 if header['source']!=source_identity(p['root']) or header['manifest_sha256']!=digest(p['manifest']):raise ValueError('PINNED_RECOVERY_SOURCE_CHANGED')
 sb=state['body'];ib=intent['body'];tape=record['ledger'];actions=tape['actions'];markers=[e for e in actions if e['op']=='operating_checkpoint']
 fields={'schema','scope','contract','source_sha256','manifest_sha256','native_sequence','native_actions_sha256','state'}
 if set(sb)!=fields or sb['schema']!='agi-alpha/connected014-operating-checkpoint/v1' or sb['scope']!='SIMULATED_LOCAL_POSIX':raise ValueError('EXACT_RECOVERY_OPERATING_CHECKPOINT_REQUIRED')
 if sb['contract']!=header['contract'] or sb['manifest_sha256']!=digest(p['manifest']):raise ValueError('RECOVERY_STATE_AUTHORITY_CHANGED')
 n=sb['native_sequence'];old=ib['prior_sequence']
 if type(n)is not int or type(old)is not int or not 0<=old<n<=len(actions) or digest(actions[:n])!=sb['native_actions_sha256'] or digest(actions[:old])!=ib['prior_actions_sha256']:raise ValueError('RECOVERY_NATIVE_PREFIX_MISMATCH')
 if not markers or operating_state_digest(sb['state'])!=markers[-1]['args']['state_sha256'] or n<=markers[-1]['seq']:raise ValueError('LATEST_NATIVE_OPERATING_CHECKPOINT_REQUIRED')
 checkpoint_source=header['source'];state_root=p['root'];pending=None
 if sb['source_sha256']!=header['source']['sha256']:
  history=header.get('source_history',[])
  if not history:raise ValueError('AUTHENTICATED_PENDING_TRANSITION_REQUIRED')
  ticket=validate_ticket(history[-1],key=owner._key,root=p['root'],path=account_path)
  if state!=ticket.get('operating',{}).get('prior_checkpoint'):raise ValueError('EXACT_PENDING_TRANSITION_PREDECESSOR_REQUIRED')
  tail=actions[n:]
  if len(tail) not in {1,2} or tail[0]['op']!='source_transition' or tail[0]['args']['id']!=ticket['id'] or len(tail)==2 and (tail[1]['op']!='cost' or tail[1]['args']!={'id':'source-upgrade-'+ticket['id'],'amount':ticket['operating']['policy']['upgrade_cost_microUSD']}):raise ValueError('PENDING_TRANSITION_NATIVE_TAIL_CHANGED')
  checkpoint_source=ticket['from_source'];state_root=ticket['historical_root'];pending=ticket['id']
  if sb['source_sha256']!=checkpoint_source['sha256']:raise ValueError('PENDING_CHECKPOINT_SOURCE_CHANGED')
 check_source(state_root,sb['state']['source'])
 if ib['schema']!='agi-alpha/connected-operating-checkpoint-intent/v1' or ib['path']!=str(out/'STATE.json') or ib['manifest_sha256']!=header['manifest_sha256'] or ib['source_sha256']!=checkpoint_source['sha256']:raise ValueError('OBSOLETE_INTENT_AUTHORITY_CHANGED')
 archive=out/'CHECKPOINT_RECOVERY';archive.mkdir(exist_ok=True)
 if archive.is_symlink():raise ValueError('RECOVERY_ARCHIVE_SYMLINK_REFUSED')
 archived=archive/(p['id']+'.obsolete-intent.json')
 if archived.exists() and archived.read_bytes()!=intent_raw:raise ValueError('RECOVERY_ID_REUSE_REFUSED')
 if not archived.exists():atomic_bytes(archived,intent_raw)
 body={'schema':'agi-alpha/compatible-operating-intent-recovery/v1','id':p['id'],'account_path':str(account_path),'source':header['source'],
       'expected_checkpoint_sha256':p['expected'],'native_actions_sha256':tape['actions_sha256'],'native_action_count':len(actions),
       'obsolete_intent_sha256':hashlib.sha256(intent_raw).hexdigest(),'latest_operating_counter':markers[-1]['args']['counter'],
       'recovery_module_sha256':p['module_sha256'],'recovery_verifier_sha256':p['verifier_sha256'],
       'checkpoint_source_sha256':checkpoint_source['sha256'],'pending_authenticated_transition':pending,
       'scope':'Verified compatible metadata recovery; financial ledger, signed STATE, journal, account and key remain unchanged'}
 receipt={'body':body,'signature':hmac.new(owner._key,b'connected-compatible-intent-recovery\n'+canonical(body),hashlib.sha256).hexdigest()}
 receipt_path=archive/(p['id']+'.receipt.json');receipt_raw=canonical(receipt)+b'\n'
 if receipt_path.exists() and receipt_path.read_bytes()!=receipt_raw:raise ValueError('RECOVERY_RECEIPT_REWRITE_REFUSED')
 if not receipt_path.exists():atomic_bytes(receipt_path,receipt_raw)
 os.replace(intent_path,archived)
 for directory in [archive,out]:
  fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY)
  try:os.fsync(fd)
  finally:os.close(fd)
 if (out/'STATE.json').read_bytes()!=state_raw or journal_path.read_bytes()!=journal_raw or (out/'account.sqlite.actions.jsonl').read_bytes()!=before_tape or required[3].stat().st_ino!=before_key_inode:raise ValueError('RECOVERY_CHANGED_PROTECTED_HISTORY')
 print(json.dumps({'accepted':True,'receipt':receipt,'account_history_unchanged':True},sort_keys=True))
'''


def recover_checkpoint(historical_root, manifest_path, output, *, expected_checkpoint, ident):
    output=Path(output).absolute();historical_root=Path(historical_root).absolute()
    if not isinstance(ident,str) or not ident or len(ident)>80 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in ident):
        raise ValueError('SAFE_COMPATIBLE_RECOVERY_ID_REQUIRED')
    manifest=strict_json(Path(manifest_path).read_bytes())
    payload={'root':str(historical_root),'manifest':manifest,'output':str(output),'expected':expected_checkpoint,'id':ident,
             'module_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'verifier_sha256':hashlib.sha256(VERIFY.encode()).hexdigest()}
    with RunLock(output):
        done=subprocess.run([sys.executable,'-c',VERIFY],input=json.dumps(payload),cwd=historical_root,
                            env={**os.environ,'PYTHONPATH':str(historical_root),'PYTHONDONTWRITEBYTECODE':'1'},
                            text=True,capture_output=True,timeout=120)
    if done.returncode:raise ValueError('PINNED_COMPATIBLE_RECOVERY_FAILED:'+done.stderr[-3000:])
    return json.loads(done.stdout)
