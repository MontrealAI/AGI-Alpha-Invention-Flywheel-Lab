"""Engineering exits for owner-held CAS authorization and operating continuation."""
import copy,hashlib,json,os,subprocess,sys,unittest
from pathlib import Path
from unittest.mock import patch
import tests.test_transition_cas_candidate as fixture
from connected_enterprise import operations
from connected_enterprise.transition_evidence import evidence_directory,ticket_body,persist_evidence
from connected_enterprise.upgrades import authorize_upgrade
from connected_enterprise.migration import default_policy
from commercial.ledger import digest

class OwnerSigningTests(unittest.TestCase):
 setUpClass=classmethod(fixture.CASMigrationTests.setUpClass.__func__)
 tearDownClass=classmethod(fixture.CASMigrationTests.tearDownClass.__func__)
 setUp=fixture.CASMigrationTests.setUp
 tearDown=fixture.CASMigrationTests.tearDown
 def test_owner_signs_without_parent_reading_key_and_rejects_changed_preparation(self):
  store=Path(self.case.name)/'objects';store.mkdir();original=Path.read_bytes
  def guarded(path):
   if path==self.keypath:raise AssertionError('parent attempted to read owner key')
   return original(path)
  kwargs=dict(historical_root=self.old,target_root=self.new,manifest=self.manifest,path=self.path,
              opening=500000000,working=100000000,contract='connected014-ordinary-legacy-owned',
              expected_state_digest=self.prior['snapshot']['state_digest'],ident='owner-cas',day=1,
              transition_format='v2-cas',evidence_root=store)
  with patch.object(Path,'read_bytes',guarded):ticket=authorize_upgrade(**kwargs)
  self.assertEqual(ticket['body']['schema'],'agi-alpha/native-source-transition/v2-cas')
  with evidence_directory(store):self.assertEqual(ticket_body(ticket)['prior_record'],self.prior)
  self.assertEqual(authorize_upgrade(**kwargs,prepared_ticket=ticket),ticket)
  admission=Path(self.case.name)/'TRANSITION_PREFLIGHT'/(digest(ticket)+'.json')
  value=json.loads(admission.read_text());self.assertEqual(value['body']['ticket_sha256'],digest(ticket))
  import hmac
  from commercial.ledger import canonical
  expected=hmac.new(self.key,b'native-publication-preflight\n'+canonical(value['body']),hashlib.sha256).hexdigest()
  self.assertEqual(value['signature'],expected)
  self.assertLessEqual(value['body']['preflight']['planned_public_files'],10000)
  self.assertLessEqual(value['body']['preflight']['planned_public_bytes'],512*1024*1024)
  changed=copy.deepcopy(ticket);changed['signature']='0'*64
  with self.assertRaisesRegex(ValueError,'PREPARED_SOURCE_AUTHORIZATION_CHANGED'):
   authorize_upgrade(**kwargs,prepared_ticket=changed)

class OwnerOperatingTests(unittest.TestCase):
 setUpClass=classmethod(fixture.CASOperatingTests.setUpClass.__func__)
 tearDownClass=classmethod(fixture.CASOperatingTests.tearDownClass.__func__)
 setUp=fixture.CASOperatingTests.setUp
 tearDown=fixture.CASOperatingTests.tearDown
 legacy=fixture.CASOperatingTests.legacy
 def command(self,root,*args):
  done=subprocess.run([sys.executable,'-m','connected_enterprise',*map(str,args)],cwd=root,
      env={**os.environ,'PYTHONPATH':str(root),'PYTHONDONTWRITEBYTECODE':'1'},text=True,capture_output=True,timeout=150)
  self.assertEqual(done.returncode,0,done.stderr[-5000:]);return done
 def test_forward_upgrade_uses_registered_historical_selector_and_rejects_changed_resource(self):
  self.legacy();key_inode=self.key.stat().st_ino
  previous=self.case/'previous-selector';operations._copy_source(self.new,previous)
  operations._copy_inputs(self.old,previous,self.manifest)
  resource=previous/'historical-selector-resource.json';resource.write_text('{"historical":"bound"}\n')
  runner=previous/'connected_enterprise/runner.py'
  runner.write_text(runner.read_text().replace('    names=set(inherited_paths(root))',
     "    names=set(inherited_paths(root)); names.add('historical-selector-resource.json')"))
  manifest=self.case/'SERVICES.json';manifest.write_text(json.dumps(self.manifest))
  policy=self.case/'policy.json';policy.write_text(json.dumps(self.policy))
  def upgrade(root,old,ident):
   checkpoint=json.loads((self.world/'STATE.json').read_text())
   self.command(root,'upgrade','--output',self.world,'--historical-source',old,'--manifest',manifest,
       '--policy',policy,'--expected-checkpoint',digest(checkpoint),'--id',ident,'--transition-format','v2-cas')
  # Only the old CLI computes and signs the historical runtime map.
  upgrade(previous,self.old,'historical-selector-first')
  descriptor=operations.read_operator(self.world)[0];registered=self.world/descriptor['source_dir']
  self.assertIn(resource.name,descriptor['source']['files'])
  from connected_enterprise.runner import identity
  self.assertNotEqual(identity(registered),descriptor['source'])
  bound=registered/resource.name;raw=bound.read_bytes();bound.write_bytes(raw+b' ')
  with self.assertRaisesRegex(ValueError,'CONNECTED_EXECUTING_SOURCE_CHANGED'):
   operations.read_operator(self.world)
  bound.write_bytes(raw)
  prior=json.loads((self.world/'RESULT.json').read_text())['owned_account']['ledger']['actions']
  upgrade(fixture.ROOT,registered,'historical-selector-second')
  self.command(fixture.ROOT,'operate','--output',self.world)
  result=json.loads((self.world/'RESULT.json').read_text())
  self.assertTrue(result['complete']);self.assertEqual(result['owned_account']['ledger']['actions'][:len(prior)],prior)
  self.assertEqual(self.key.stat().st_ino,key_inode)
  self.command(fixture.ROOT,'audit','--output',self.world)
 def test_public_cli_two_successive_owner_transitions_and_unchanged_resume(self):
  self.legacy();before=self.before['body']['state'];self.assertTrue(before['queue'])
  manifest=self.case/'SERVICES.json';manifest.write_text(json.dumps(self.manifest))
  policy=self.case/'policy.json';policy.write_text(json.dumps(self.policy))
  keyhash=hashlib.sha256(self.key.read_bytes()).hexdigest()
  def upgrade(root,old,ident):
   checkpoint=json.loads((self.world/'STATE.json').read_text())
   self.command(root,'upgrade','--output',self.world,'--historical-source',old,'--manifest',manifest,
      '--policy',policy,'--expected-checkpoint',digest(checkpoint),'--id',ident,'--transition-format','v2-cas')
  # Legitimate interruption leaves only a private stage, never a partial canonical object.
  store=self.world/'TRANSITION_EVIDENCE';store.mkdir()
  raw=b'{"synthetic":"interrupted"}';name=hashlib.sha256(raw).hexdigest()
  def crash(where,stage):
   if where=='stage_created':raise InterruptedError('owned stage interruption')
  with self.assertRaises(InterruptedError):persist_evidence(store,{name:raw},failpoint=crash)
  native_before=(self.world/'account.sqlite.actions.jsonl').read_bytes()
  recovery=self.command(self.new,'recover-transition-evidence','--output',self.world,'--historical-source',self.old,
        '--manifest',manifest,'--expected-checkpoint',digest(self.before),'--id','stage-recovery')
  self.assertTrue(json.loads(recovery.stdout)['accepted'])
  self.assertEqual((self.world/'account.sqlite.actions.jsonl').read_bytes(),native_before)
  self.assertEqual(len(list(store.glob('.orphan-*'))),1)
  self.assertFalse((store/name).exists())
  # Retrying publication creates a complete, independently hashed object.
  persist_evidence(store,{name:raw})
  upgrade(self.new,self.old,'first-owner-cas')
  first=operations.read_operator(self.world)[0];old=self.world/first['source_dir']
  state=json.loads((self.world/'STATE.json').read_text())['body']['state']
  for name in ['queue','current','orders','buyers','events','investments','used_jobs','processed_events','last_time']:
   self.assertEqual(before[name],state[name],name)
  self.command(self.new,'operate','--output',self.world,'--max-events','1')
  nextroot=self.case/'next-source';operations._copy_source(self.new,nextroot);operations._copy_inputs(self.old,nextroot,self.manifest)
  with (nextroot/'connected_enterprise/pricing.py').open('a') as stream:stream.write('\n# Distinct experimental forward source version.\n')
  upgrade(nextroot,old,'second-owner-cas')
  self.command(nextroot,'operate','--output',self.world)
  result=json.loads((self.world/'RESULT.json').read_text());self.assertTrue(result['complete'])
  transitions=[e for e in result['owned_account']['ledger']['actions'] if e['op']=='source_transition']
  self.assertEqual([e['args']['counter'] for e in transitions],[1,2])
  self.assertEqual(result['owned_account']['ledger']['actions'][:len(self.prior['ledger']['actions'])],self.prior['ledger']['actions'])
  self.command(nextroot,'resume','--output',self.world)
  self.assertEqual(json.loads((self.world/'RESULT.json').read_text())['summary'],result['summary'])
  self.command(nextroot,'audit','--output',self.world)
  self.assertEqual(self.key.stat().st_ino,self.key_inode)
  self.assertEqual(hashlib.sha256(self.key.read_bytes()).hexdigest(),keyhash)
  public=self.case/'public-portable'
  done=subprocess.run([sys.executable,str(nextroot/'scripts/export_recovered023.py'),'--business',str(self.world),
                       '--output',str(public),'--offline-historical-sources'],cwd=nextroot,
        env={**os.environ,'PYTHONPATH':str(nextroot),'PYTHONDONTWRITEBYTECODE':'1'},text=True,capture_output=True,timeout=180)
  self.assertEqual(done.returncode,0,done.stderr[-5000:]);self.assertTrue(json.loads(done.stdout)['accepted'])
  self.assertTrue((public/'TRANSITION_EVIDENCE_INDEX.json').is_file())
  self.assertFalse(any('.sqlite' in str(p.relative_to(public)) or p.name.endswith('.adaptive-simulation-key') for p in public.rglob('*')))
  self.assertEqual(self.key.stat().st_ino,self.key_inode)


class OwnerCrashTests(unittest.TestCase):
 setUpClass=classmethod(fixture.CASOperatingTests.setUpClass.__func__)
 tearDownClass=classmethod(fixture.CASOperatingTests.tearDownClass.__func__)
 setUp=fixture.CASOperatingTests.setUp
 tearDown=fixture.CASOperatingTests.tearDown
 legacy=fixture.CASOperatingTests.legacy
 def prepare(self):
  manifest=self.case/'manifest.json';manifest.write_text(json.dumps(self.manifest))
  return operations.prepare_upgrade(self.new,self.old,manifest,self.world,policy=self.policy,
     expected_checkpoint_sha256=digest(self.before),ident='owner-crash',transition_format='v2-cas')
 def finish(self):
  result=operations.operate(self.world)
  self.assertTrue(result['complete']);self.assertTrue(operations.audit(self.world)['accepted'])
  actions=result['owned_account']['ledger']['actions']
  self.assertEqual(sum(e['op']=='source_transition' for e in actions),1)
  self.assertEqual(sum(e['op']=='cost' and e['args']['id']=='source-upgrade-owner-crash' for e in actions),1)
  self.assertEqual(actions[:len(self.prior['ledger']['actions'])],self.prior['ledger']['actions'])
  self.assertEqual(self.key.stat().st_ino,self.key_inode)
  return result
 def test_preparation_survives_descriptor_interruption_and_reuses_exact_signed_wire(self):
  self.legacy();native=(self.world/'account.sqlite.actions.jsonl').read_bytes();original=operations._write
  def crash(path,value):
   if Path(path).name=='OPERATOR.json':raise InterruptedError('before descriptor publication')
   return original(path,value)
  with patch.object(operations,'_write',crash),self.assertRaises(InterruptedError):self.prepare()
  self.assertFalse((self.world/'OPERATOR.json').exists());self.assertEqual((self.world/'account.sqlite.actions.jsonl').read_bytes(),native)
  preparations=list((self.world/'TRANSITION_PREPARATIONS').glob('*.json'));self.assertEqual(len(preparations),1)
  original=preparations[0].read_bytes();self.prepare();self.assertEqual(preparations[0].read_bytes(),original)
  operations.upgrade(self.world);self.finish()
 def test_migration_intent_boundary(self):self.boundary('after_upgrade_intent')
 def test_financial_commit_boundary(self):self.boundary('after_financial_transition')
 def test_checkpoint_publication_boundary(self):self.boundary('after_operating_checkpoint')
 def boundary(self,where):
  self.legacy();self.prepare()
  def crash(observed,account):
   if observed==where:raise InterruptedError(where)
  with self.assertRaises(InterruptedError):operations.upgrade(self.world,failpoint=crash)
  operations.upgrade(self.world);self.finish()
 def test_checkpoint_intent_and_financial_anchor_interruptions(self):
  from connected_enterprise import finance
  for after in [False,True]:
   with self.subTest(after_checkpoint=after):
    if after:
     self.tearDown();self.setUp()
    self.legacy();self.prepare();original=finance.atomic_bytes
    def crash(path,raw):
     if Path(path).name=='STATE.json':
      if after:original(path,raw)
      raise InterruptedError('state publication')
     return original(path,raw)
    with patch.object(finance,'atomic_bytes',crash),self.assertRaises(InterruptedError):operations.upgrade(self.world)
    operations.upgrade(self.world);self.finish()
 def test_missing_or_changed_preparation_cannot_create_new_authority(self):
  self.legacy();self.prepare();path=next((self.world/'TRANSITION_PREPARATIONS').glob('*.json'));raw=path.read_bytes()
  ticket=json.loads(raw);ticket['signature']='0'*64;path.write_text(json.dumps(ticket))
  native=(self.world/'account.sqlite.actions.jsonl').read_bytes()
  with self.assertRaisesRegex(ValueError,'PREPARED_SOURCE_AUTHORIZATION_CHANGED'):operations.upgrade(self.world)
  self.assertEqual((self.world/'account.sqlite.actions.jsonl').read_bytes(),native)
  self.assertFalse((self.world/'MIGRATION_INTENT.json').exists())
  path.write_bytes(raw);operations.upgrade(self.world);result=self.finish()
  with evidence_directory(self.world/'TRANSITION_EVIDENCE'):
   from connected_enterprise.finance import audit_journal
   descriptor=operations.read_operator(self.world)[0];root=self.world/descriptor['source_dir']
   self.assertTrue(audit_journal(result['owned_account'],root=root,manifest=self.manifest)['accepted'])
   ref=ticket['body']['evidence']['prior_record'];obj=self.world/'TRANSITION_EVIDENCE'/ref['sha256'];saved=obj.read_bytes()
   try:
    obj.write_bytes(saved+b' ')
    with self.assertRaises(ValueError):audit_journal(result['owned_account'],root=root,manifest=self.manifest)
   finally:obj.write_bytes(saved)


class OwnerFourTransitionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  fixture.CASOperatingTests.setUpClass.__func__(cls)
  # A large, disclosed synthetic verifier inventory makes recursive copying
  # exceed the unchanged archive file guard. These are not research evidence.
  notes=cls.old/'synthetic-verifier-inventory';notes.mkdir()
  for number in range(3000):(notes/(str(number)+'.py')).write_bytes(b'')
 tearDownClass=classmethod(fixture.CASOperatingTests.tearDownClass.__func__)
 setUp=fixture.CASOperatingTests.setUp
 tearDown=fixture.CASOperatingTests.tearDown
 legacy=fixture.CASOperatingTests.legacy
 command=OwnerOperatingTests.command
 def test_four_owner_transitions_flat_portable_history_and_fifth_rejection(self):
  self.legacy();manifest=self.case/'manifest.json';manifest.write_text(json.dumps(self.manifest))
  policy=self.case/'policy.json';policy.write_text(json.dumps(self.policy))
  old=self.old;target=self.new
  for counter in range(1,5):
   checkpoint=json.loads((self.world/'STATE.json').read_text())
   self.command(target,'upgrade','--output',self.world,'--historical-source',old,'--manifest',manifest,
       '--policy',policy,'--expected-checkpoint',digest(checkpoint),'--id','four-owner-'+str(counter),'--transition-format','v2-cas')
   descriptor=operations.read_operator(self.world)[0];old=self.world/descriptor['source_dir']
   self.command(target,'operate','--output',self.world,'--max-events','1')
   target=self.case/('source-'+str(counter+1));operations._copy_source(old,target);operations._copy_inputs(self.old,target,self.manifest)
   with (target/'connected_enterprise/pricing.py').open('a') as stream:stream.write('\n# Finite synthetic forward source '+str(counter+1)+'.\n')
  checkpoint=json.loads((self.world/'STATE.json').read_text());operator=(self.world/'OPERATOR.json').read_bytes();native=(self.world/'account.sqlite.actions.jsonl').read_bytes()
  with self.assertRaisesRegex(ValueError,'FORWARD_CHAIN_OR_IDENTITY_INVALID'):
   operations.prepare_upgrade(target,old,manifest,self.world,policy=self.policy,expected_checkpoint_sha256=digest(checkpoint),ident='fifth-forbidden',transition_format='v2-cas')
  self.assertEqual((self.world/'OPERATOR.json').read_bytes(),operator);self.assertEqual((self.world/'account.sqlite.actions.jsonl').read_bytes(),native)
  self.command(old,'resume','--output',self.world);self.command(old,'audit','--output',self.world)
  result=json.loads((self.world/'RESULT.json').read_text());self.assertTrue(result['complete'])
  self.assertEqual([e['args']['counter'] for e in result['owned_account']['ledger']['actions'] if e['op']=='source_transition'],[1,2,3,4])
  public=self.case/'public-four'
  done=subprocess.run([sys.executable,str(old/'scripts/export_recovered023.py'),'--business',str(self.world),'--output',str(public),'--offline-historical-sources'],cwd=old,
      env={**os.environ,'PYTHONPATH':str(old),'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=300)
  self.assertEqual(done.returncode,0,done.stderr[-6000:]);self.assertTrue(json.loads(done.stdout)['accepted'])
  versions=public/'source/historical-source-versions'
  self.assertEqual(len(list(versions.iterdir())),4)
  self.assertFalse(any(p.name=='historical-source-versions' for p in versions.rglob('*')))
  self.assertEqual(len(list(versions.rglob('synthetic-verifier-inventory/*.py'))),3000)
  self.assertEqual(self.key.stat().st_ino,self.key_inode)

class OwnerPublicationBudgetTests(unittest.TestCase):
 setUpClass=classmethod(fixture.CASOperatingTests.setUpClass.__func__)
 tearDownClass=classmethod(fixture.CASOperatingTests.tearDownClass.__func__)
 setUp=fixture.CASOperatingTests.setUp
 tearDown=fixture.CASOperatingTests.tearDown
 legacy=fixture.CASOperatingTests.legacy
 def test_combined_source_and_objects_reject_before_descriptor_or_financial_change(self):
  self.legacy();target=self.case/'bounded-target';operations._copy_source(self.new,target);operations._copy_inputs(self.old,target,self.manifest)
  module=target/'connected_enterprise/transition_evidence.py';text=module.read_text();self.assertIn('MAX_BUNDLE_FILES = 10_000',text)
  module.write_text(text.replace('MAX_BUNDLE_FILES = 10_000','MAX_BUNDLE_FILES = 300'))
  manifest=self.case/'manifest.json';manifest.write_text(json.dumps(self.manifest))
  journal=(self.world/'account.sqlite.connected-journal.json').read_bytes();native=(self.world/'account.sqlite.actions.jsonl').read_bytes()
  with self.assertRaisesRegex(ValueError,'SHARED_PUBLICATION_BUDGET_EXCEEDED'):
   operations.prepare_upgrade(target,self.old,manifest,self.world,policy=self.policy,expected_checkpoint_sha256=digest(self.before),ident='unpublishable',transition_format='v2-cas')
  self.assertFalse((self.world/'OPERATOR.json').exists());self.assertFalse((self.world/'MIGRATION_INTENT.json').exists())
  self.assertEqual((self.world/'account.sqlite.connected-journal.json').read_bytes(),journal)
  self.assertEqual((self.world/'account.sqlite.actions.jsonl').read_bytes(),native)
  self.assertEqual(list((self.world/'TRANSITION_EVIDENCE').iterdir()),[])
  self.assertEqual(self.key.stat().st_ino,self.key_inode)

 def test_bare_target_preflights_bound_inputs_before_the_normal_copy(self):
  self.legacy();target=self.case/'bare-target'
  operations._copy_source(fixture.ROOT,target)
  # The source-only installation intentionally lacks generated cohort inputs.
  self.assertFalse((target/self.manifest['jobs'][0]['input']).exists())
  manifest=self.case/'manifest.json';manifest.write_text(json.dumps(self.manifest))
  descriptor=operations.prepare_upgrade(target,self.old,manifest,self.world,policy=self.policy,
      expected_checkpoint_sha256=digest(self.before),ident='bare-installed-target',transition_format='v2-cas')
  self.assertTrue((self.world/descriptor['source_dir']/self.manifest['jobs'][0]['input']).is_file())
  self.assertTrue(operations.upgrade(self.world)['accepted'])
  self.assertTrue(operations.operate(self.world)['complete']);self.assertTrue(operations.audit(self.world)['accepted'])
  self.assertEqual(self.key.stat().st_ino,self.key_inode)
