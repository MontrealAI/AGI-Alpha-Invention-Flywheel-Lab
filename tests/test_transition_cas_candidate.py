"""Isolated synthetic protocol tests, not original-account qualification."""
import copy,hashlib,hmac,json,os,shutil,stat,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
from commercial.ledger import canonical
from connected_enterprise.transition_evidence import externalize,evidence_scope,ticket_body,DOMAIN
from connected_enterprise.upgrades import authorize_upgrade,validate_ticket,transition_args
from connected_enterprise.finance import JournalAccount
from adaptive_enterprise.instruments import prepare_services
ROOT=Path(__file__).resolve().parents[1]

class CASMigrationTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(prefix='synthetic-cas-');cls.directory=Path(cls.tmp.name)
  cls.old=cls.directory/'old';cls.old.mkdir()
  pinned=json.loads((ROOT/'historical/cas-parent7d/MANIFEST.json').read_text());archive=ROOT/'historical/cas-parent7d/source.zip'
  assert pinned['commit']=='7d75766401adede49afd2427be82eb0302934b80'
  assert hashlib.sha256(archive.read_bytes()).hexdigest()==pinned['archive_sha256']
  with zipfile.ZipFile(archive) as z:
   assert len(z.namelist())==len(set(z.namelist())) and set(z.namelist())|set(pinned['shared_files'])==set(pinned['source']['files'])
   assert len(z.namelist())<=10000 and sum(i.file_size for i in z.infolist())<=16_000_000
   for item in z.infolist():
    name=Path(item.filename);raw=z.read(item)
    assert not name.is_absolute() and '..' not in name.parts and not stat.S_ISLNK(item.external_attr>>16)
    assert hashlib.sha256(raw).hexdigest()==pinned['source']['files'][item.filename]
    p=cls.old/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
  for value in pinned['shared_files']:
   name=Path(value);p=ROOT/name;raw=p.read_bytes()
   assert not name.is_absolute() and '..' not in name.parts and not p.is_symlink()
   assert hashlib.sha256(raw).hexdigest()==pinned['source']['files'][value]
   target=cls.old/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
  from connected_enterprise.runner import identity
  assert identity(cls.old)['sha256']=='1a28649f02eee54e2ba6c78a57aff99f4544e0dd4d09d67cf52ef226267d9fba'
  cls.manifest=prepare_services(cls.old,'services')
  from connected_enterprise.operations import _copy_source,_copy_inputs
  cls.new=cls.directory/'new';_copy_source(ROOT,cls.new);_copy_inputs(cls.old,cls.new,cls.manifest)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def setUp(self):
  self.case=tempfile.TemporaryDirectory(prefix='synthetic-cas-account-');self.path=Path(self.case.name)/'a.sqlite'
  payload={'root':str(self.old),'path':str(self.path),'manifest':self.manifest}
  code="""import json,sys
from connected_enterprise.finance import JournalAccount
p=json.load(sys.stdin)
with JournalAccount(p['root'],p['manifest'],p['path'],opening=500000000,working=100000000,contract='connected014-ordinary-legacy-owned') as a:
 a.cost('prior-expense',7,0)
 print(json.dumps(a.export()))
"""
  result=subprocess.run([sys.executable,'-c',code],input=json.dumps(payload),text=True,capture_output=True,cwd=self.old,env={**os.environ,'PYTHONPATH':str(self.old)},timeout=60)
  self.assertEqual(result.returncode,0,result.stderr);self.prior=json.loads(result.stdout)
  self.keypath=self.path.with_name(self.path.name+'.adaptive-simulation-key');self.key=self.keypath.read_bytes();self.inode=self.keypath.stat().st_ino
  self.legacy=authorize_upgrade(historical_root=self.old,target_root=self.new,manifest=self.manifest,path=self.path,opening=500000000,working=100000000,contract='connected014-ordinary-legacy-owned',expected_state_digest=self.prior['snapshot']['state_digest'],ident='cas-transition',day=1)
  self.blobs={};body=externalize(self.legacy['body'],self.blobs)
  # Ephemeral fixture key only. Production signing belongs in owner subprocess.
  self.ticket={'body':body,'signature':hmac.new(self.key,DOMAIN+canonical(body),hashlib.sha256).hexdigest()}
 def tearDown(self):self.case.cleanup()
 def open(self,ticket):
  return JournalAccount.upgrade_source(self.new,self.manifest,self.path,opening=500000000,working=100000000,contract='connected014-ordinary-legacy-owned',authorization=ticket)
 def test_same_account_native_transition_audit_and_reopen(self):
  with evidence_scope(self.blobs):
   self.assertEqual(validate_ticket(self.ticket,key=self.key,path=self.path),self.legacy['body'])
   self.assertEqual(transition_args(self.ticket),transition_args(self.legacy))
   with self.open(self.ticket) as account:
    record=account.export();self.assertEqual(record['ledger']['actions'][:-1],self.prior['ledger']['actions'])
    self.assertEqual(record['ledger']['summary'],self.prior['ledger']['summary'])
    self.assertEqual(record['source_transitions']['cas-transition'],self.ticket)
    self.assertTrue(account.audit()['accepted'])
   with JournalAccount(self.new,self.manifest,self.path,opening=500000000,working=100000000,contract='connected014-ordinary-legacy-owned') as account:
    self.assertEqual(account.export(),record)
   self.assertEqual(hashlib.sha256(self.keypath.read_bytes()).hexdigest(),hashlib.sha256(self.key).hexdigest());self.assertEqual(self.keypath.stat().st_ino,self.inode)
 def test_explicit_directory_cross_process_public_audit(self):
  from connected_enterprise.transition_evidence import persist_evidence
  store=Path(self.case.name)/'public-blobs';store.mkdir();persist_evidence(store,self.blobs)
  with evidence_scope(self.blobs):
   with self.open(self.ticket) as account:record=account.export()
  payload={'root':str(self.new),'manifest':self.manifest,'record':record,'store':str(store)}
  code="import json,sys;from connected_enterprise.transition_evidence import evidence_directory;from connected_enterprise.finance import audit_journal;p=json.load(sys.stdin)\nwith evidence_directory(p['store']):r=audit_journal(p['record'],root=p['root'],manifest=p['manifest']);assert r['accepted'];print('accepted')"
  done=subprocess.run([sys.executable,'-c',code],input=json.dumps(payload),text=True,capture_output=True,cwd=self.new,env={**os.environ,'PYTHONPATH':str(self.new)},timeout=60)
  self.assertEqual(done.returncode,0,done.stderr);self.assertEqual(done.stdout.strip(),'accepted')
  self.assertEqual(set(p.name for p in store.iterdir()),set(self.blobs))
 def test_missing_scope_rejects_before_journal_mutation(self):
  journal=self.path.with_name(self.path.name+'.connected-journal.json');before=journal.read_bytes()
  with self.assertRaisesRegex(ValueError,'EXPLICIT_TRANSITION_EVIDENCE_SCOPE'):self.open(self.ticket)
  self.assertEqual(journal.read_bytes(),before)
 def test_wrong_signature_precedes_external_resolution(self):
  ticket=copy.deepcopy(self.ticket);ticket['signature']='0'*64
  with self.assertRaisesRegex(ValueError,'SIGNATURE_MISMATCH'):validate_ticket(ticket,key=self.key)
 def test_tampered_blob_and_missing_blob_reject(self):
  corrupt=dict(self.blobs);key=next(iter(corrupt));corrupt[key]+=b' '
  with self.assertRaisesRegex(ValueError,'HASH_CHANGED'):
   with evidence_scope(corrupt):pass
  with evidence_scope({}),self.assertRaisesRegex(ValueError,'MISSING_OR_CHANGED'):validate_ticket(self.ticket,key=self.key)
 def test_duplicate_storage_is_deduplicated_and_history_is_opaque(self):
  first=dict(self.blobs);externalize(self.legacy['body'],self.blobs);self.assertEqual(first,self.blobs)
  body=copy.deepcopy(self.legacy['body']);body['prior_record']['source_transitions']={'old':self.ticket}
  body['counter']=2;second=externalize(body,self.blobs)
  ticket={'body':second,'signature':hmac.new(self.key,DOMAIN+canonical(second),hashlib.sha256).hexdigest()}
  with evidence_scope(self.blobs):
   resolved=ticket_body(ticket,key=self.key)
   self.assertEqual(resolved['prior_record']['source_transitions']['old'],self.ticket)
 def test_resolved_mutation_cannot_change_subsequent_authenticated_view(self):
  with evidence_scope(self.blobs):
   first=ticket_body(self.ticket,key=self.key);first['prior_record']['snapshot']['state_digest']='f'*64
   second=ticket_body(self.ticket,key=self.key)
   self.assertEqual(second,self.legacy['body'])
 def test_stale_signed_state_and_double_apply(self):
  bad=copy.deepcopy(self.ticket);bad['body']['expected_state_digest']='f'*64
  bad['signature']=hmac.new(self.key,DOMAIN+canonical(bad['body']),hashlib.sha256).hexdigest()
  journal=self.path.with_name(self.path.name+'.connected-journal.json');before=journal.read_bytes()
  with evidence_scope(self.blobs):
   with self.assertRaisesRegex(ValueError,'CHECKPOINT_CHANGED'):self.open(bad)
   self.assertEqual(journal.read_bytes(),before)
   with self.open(self.ticket) as account:first=account.export()
   with self.open(self.ticket) as account:
    self.assertEqual(account.export(),first)
    self.assertEqual(sum(a['op']=='source_transition' for a in first['ledger']['actions']),1)
 def test_cross_process_reopen_with_explicit_store(self):
  from connected_enterprise.transition_evidence import persist_evidence
  store=Path(self.case.name)/'reopen-blobs';store.mkdir();persist_evidence(store,self.blobs)
  with evidence_scope(self.blobs):
   with self.open(self.ticket) as account:record=account.export()
  payload={'root':str(self.new),'manifest':self.manifest,'path':str(self.path),'store':str(store),'record':record}
  code="import json,sys;from connected_enterprise.transition_evidence import evidence_directory;from connected_enterprise.finance import JournalAccount;p=json.load(sys.stdin)\nwith evidence_directory(p['store']):\n with JournalAccount(p['root'],p['manifest'],p['path'],opening=500000000,working=100000000,contract='connected014-ordinary-legacy-owned') as a:assert a.export()==p['record'];assert a.audit()['accepted'];print('accepted')"
  done=subprocess.run([sys.executable,'-c',code],input=json.dumps(payload),text=True,capture_output=True,cwd=self.new,env={**os.environ,'PYTHONPATH':str(self.new)},timeout=60)
  self.assertEqual(done.returncode,0,done.stderr)
 def test_reference_path_and_counter_five_reject(self):
  for mutation in ['path','counter']:
   ticket=copy.deepcopy(self.ticket)
   if mutation=='path':ticket['body']['evidence']['prior_record']['sha256']='../../etc/passwd'
   else:ticket['body']['counter']=5
   ticket['signature']=hmac.new(self.key,DOMAIN+canonical(ticket['body']),hashlib.sha256).hexdigest()
   with evidence_scope(self.blobs),self.assertRaises(ValueError):validate_ticket(ticket,key=self.key)

if __name__=='__main__':unittest.main()

from contextlib import ExitStack
from unittest.mock import patch
import tests.test_connected_operating_upgrade as operating_fixture
from connected_enterprise.engine import default_config
from connected_enterprise.runner import identity
from connected_enterprise.migration import default_policy

class CASOperatingTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  CASMigrationTests.setUpClass.__func__(cls)
  cls.old_source=identity(cls.old);cls.source=identity(cls.new)
  cls.cfg=default_config();cls.cfg.update(horizon_days=2,customer_pool=8,opening=500_000_000,
    setup_cost=5_000_000,clearing_hours=1,payment_deadline_hours=12,
    arrival_bps=10000,retention_bps=10000,nonpayment_bps=0,price_pressure_bps=10000)
 @classmethod
 def tearDownClass(cls):CASMigrationTests.tearDownClass.__func__(cls)
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='cas-operating-');self.case=Path(self.tmp.name);self.world=self.case/'business'
  self.policy=default_policy();self.policy['protection_hours']=2
  self.scopes=ExitStack();self.blobs={}
 def tearDown(self):self.scopes.close();self.tmp.cleanup()
 legacy=operating_fixture.OperatingUpgradeTests.legacy
 migrate=operating_fixture.OperatingUpgradeTests.migrate
 finish=operating_fixture.OperatingUpgradeTests.finish
 def authorize_cas(self,**kwargs):
  ticket=authorize_upgrade(**kwargs);body=externalize(ticket['body'],self.blobs)
  key=self.key.read_bytes() # Newly created synthetic account only.
  ticket={'body':body,'signature':hmac.new(key,DOMAIN+canonical(body),hashlib.sha256).hexdigest()}
  self.scopes.enter_context(evidence_scope(self.blobs))
  return ticket
 def test_nonempty_operating_queue_and_complete_horizon(self):
  self.legacy();self.assertTrue(self.before['body']['state']['queue'])
  with patch('connected_enterprise.upgrades.authorize_upgrade',side_effect=self.authorize_cas):
   receipt=self.migrate()
  state=json.loads((self.world/'STATE.json').read_text())['body']['state']
  for name in ['queue','current','orders','buyers','events','investments','used_jobs','processed_events','last_time']:
   self.assertEqual(state[name],self.before['body']['state'][name],name)
  result=self.finish();self.assertTrue(result['complete'])
  self.assertEqual(self.key.stat().st_ino,self.key_inode)
  self.assertEqual(result['owned_account']['ledger']['actions'][:len(self.prior['ledger']['actions'])],self.prior['ledger']['actions'])
  self.assertEqual(sum(a['op']=='source_transition' for a in result['owned_account']['ledger']['actions']),1)
  self.assertEqual(self.finish()['summary'],result['summary'])
 def test_native_commit_interruption_recovers_once(self):
  from adaptive_enterprise.account import Account
  self.legacy();original=Account.source_transition
  def crash(account,ticket):
   original(account,ticket);raise InterruptedError('synthetic after native commit')
  with patch('connected_enterprise.upgrades.authorize_upgrade',side_effect=self.authorize_cas),patch.object(Account,'source_transition',crash),self.assertRaises(InterruptedError):
   self.migrate()
  result=self.finish()
  self.assertEqual(sum(a['op']=='source_transition' for a in result['owned_account']['ledger']['actions']),1)
  self.assertEqual(self.key.stat().st_ino,self.key_inode)
