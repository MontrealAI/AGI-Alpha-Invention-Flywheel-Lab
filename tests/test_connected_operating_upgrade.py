import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import threading
import unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

from adaptive_enterprise.instruments import prepare_services
from commercial.ledger import digest
from connected_enterprise.engine import default_config, run_world
from connected_enterprise.finance import JournalAccount, audit_journal
from connected_enterprise.migration import default_policy, upgrade_world
from connected_enterprise.operations import _copy_source, _copy_inputs
from connected_enterprise.runner import identity
from connected_enterprise.verify import audit

ROOT = Path(__file__).resolve().parents[1]


class OperatingUpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = tempfile.TemporaryDirectory(prefix='operating-upgrade-source-')
        cls.base = Path(cls.fixture.name); cls.old = cls.base / 'released'; cls.old.mkdir()
        from tests.connected_legacy_fixture import materialize
        materialize(ROOT,'9facd934d9ae763691e8a51052a67793cac5b48e',cls.old)
        cls.manifest = prepare_services(cls.old,'service-inputs',cohort_seed=2610312202)
        cls.new = cls.base / 'candidate'; _copy_source(ROOT,cls.new); _copy_inputs(cls.old,cls.new,cls.manifest)
        cls.source = identity(cls.new); cls.old_source = identity(cls.old)
        cls.cfg = default_config(); cls.cfg.update(horizon_days=8,customer_pool=8,opening=500_000_000,
            setup_cost=5_000_000,clearing_hours=1,payment_deadline_hours=12,
            arrival_bps=10000,retention_bps=10000,nonpayment_bps=0,price_pressure_bps=10000)

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='operating-upgrade-case-')
        self.case = Path(self.tmp.name); self.world = self.case / 'business'
        self.policy = default_policy(); self.policy['protection_hours'] = 2

    def tearDown(self):
        self.tmp.cleanup()

    def legacy(self, prepared=False):
        payload = {'root':str(self.old),'manifest':self.manifest,'config':self.cfg,'seed':2610312202,
                   'arm':'growth','output':str(self.world),'source':self.old_source,'stop_after_events':2}
        code = '''import json,sys
from pathlib import Path
from connected_enterprise.engine import run_world
p=json.load(sys.stdin);prepared=PREPARED
def stop(where,state,account):
 if prepared and state['current']['event']['kind']=='plan':
  (Path(p['output']).parent/'PRIOR.json').write_text(json.dumps(account.export()))
  raise InterruptedError('prepared legacy checkpoint')
try:
 r=run_world(**p,failpoint=stop)
 (Path(p['output']).parent/'PRIOR.json').write_text(json.dumps(r['owned_account']))
except InterruptedError:
 if not prepared:raise
'''.replace('PREPARED',repr(prepared))
        done = subprocess.run([sys.executable,'-c',code],input=json.dumps(payload),cwd=self.old,
                              env={**os.environ,'PYTHONPATH':str(self.old)},text=True,capture_output=True,timeout=60)
        self.assertEqual(done.returncode,0,done.stderr)
        self.before = json.loads((self.world/'STATE.json').read_text())
        self.prior = json.loads((self.world.parent/'PRIOR.json').read_text())
        self.key = self.world/'account.sqlite.adaptive-simulation-key'; self.key_inode = self.key.stat().st_ino
        return self.before

    def migrate(self, **kwargs):
        return upgrade_world(self.new,self.old,self.manifest,self.world,policy=self.policy,
                             expected_checkpoint_sha256=digest(self.before),ident='operating-upgrade-1',**kwargs)

    def finish(self):
        result = run_world(self.new,self.manifest,self.cfg,2610312202,'growth',self.world,source=self.source)
        self.assertTrue(result['complete']); self.assertTrue(audit(self.new,self.manifest,result)['accepted'])
        return result

    def test_nonempty_queue_transition_preserves_exact_identity_and_legacy_protection(self):
        self.legacy(); receipt=self.migrate()
        state=json.loads((self.world/'STATE.json').read_text())['body']['state']
        for name in ['queue','current','orders','buyers','events','investments','used_jobs','processed_events','last_time']:
            self.assertEqual(state[name],self.before['body']['state'][name],name)
        self.assertEqual(state['costs'][:len(self.before['body']['state']['costs'])],self.before['body']['state']['costs'])
        self.assertEqual(state['costs'][-1]['amount'],self.policy['upgrade_cost_microUSD'])
        self.assertEqual(receipt['monetary_summary_before'],receipt['monetary_summary_after'])
        self.assertEqual(self.key.stat().st_ino,self.key_inode)
        result=self.finish(); actions=result['owned_account']['ledger']['actions']
        self.assertEqual(actions[:len(self.prior['ledger']['actions'])],self.prior['ledger']['actions'])
        legacy={o['id'] for o in self.before['body']['state']['orders']}
        permanent=sum(o['price']+200_000 for o in result['orders'] if o['id'] in legacy and o['outcome']=='SETTLED')
        self.assertGreaterEqual(result['summary']['tailReserve'],permanent)

    def test_prepared_legacy_plan_recovers_without_repricing_or_retroactive_terms(self):
        self.legacy(prepared=True); self.assertIsNotNone(self.before['body']['state']['current'])
        proposed=copy.deepcopy(self.before['body']['state']['current']['orders']); self.migrate(); result=self.finish()
        for old in proposed:
            order=next(o for o in result['orders'] if o['id']==old['id'])
            self.assertEqual(order['price'],old['price']); self.assertNotIn('terms',order)
            self.assertEqual(sum(e['op']=='offer' and e['args']['id']==old['id'] for e in result['owned_account']['ledger']['actions']),1)

    def test_crash_at_each_transition_boundary_resumes_once(self):
        for stage in ['after_upgrade_intent','after_financial_transition','after_operating_checkpoint']:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory(prefix='migration-crash-') as directory:
                self.world=Path(directory)/'business'; self.legacy()
                def crash(where,account):
                    if where==stage:raise InterruptedError(stage)
                with self.assertRaises(InterruptedError):self.migrate(failpoint=crash)
                result=self.finish()
                self.assertEqual(sum(e['op']=='source_transition' for e in result['owned_account']['ledger']['actions']),1)
                self.assertEqual(self.key.stat().st_ino,self.key_inode)

    def test_stale_checkpoint_and_forged_operating_state_do_not_commit(self):
        self.legacy(); journal=self.world/'account.sqlite.connected-journal.json'; original=journal.read_bytes()
        with self.assertRaisesRegex(ValueError,'STALE_OPERATING_UPGRADE'):
            upgrade_world(self.new,self.old,self.manifest,self.world,policy=self.policy,expected_checkpoint_sha256='0'*64,ident='bad')
        forged=copy.deepcopy(self.before); forged['body']['state']['queue'].clear()
        (self.world/'STATE.json').write_text(json.dumps(forged))
        with self.assertRaisesRegex(ValueError,'SIGNATURE_MISMATCH'):
            upgrade_world(self.new,self.old,self.manifest,self.world,policy=self.policy,expected_checkpoint_sha256=digest(forged),ident='forged')
        self.assertEqual(journal.read_bytes(),original)
        self.assertFalse((self.world/'MIGRATION_INTENT.json').exists())

    def test_signed_intent_tamper_and_fork_cannot_rewrite_history(self):
        self.legacy()
        def crash(where,account):
            if where=='after_upgrade_intent':raise InterruptedError(where)
        with self.assertRaises(InterruptedError):self.migrate(failpoint=crash)
        path=self.world/'MIGRATION_INTENT.json'; original=path.read_bytes(); intent=json.loads(original)
        intent['ticket']['body']['operating']['policy']['premium_microUSD']=1
        path.write_text(json.dumps(intent))
        with self.assertRaises(ValueError):self.finish()
        path.write_bytes(original); self.migrate(); result=self.finish(); count=len(result['owned_account']['ledger']['actions'])
        with self.assertRaisesRegex(ValueError,'RETRY_AUTHORITY_CHANGED'):
            upgrade_world(self.new,self.old,self.manifest,self.world,policy=self.policy,expected_checkpoint_sha256=digest(self.before),ident='fork')
        self.assertEqual(len(json.loads((self.world/'RESULT.json').read_text())['owned_account']['ledger']['actions']),count)

    def test_two_operating_writers_racing_upgrade_commit_once(self):
        self.legacy(); entered=threading.Event(); release=threading.Event()
        def hold(where,account):
            if where=='after_upgrade_intent':entered.set(); release.wait(timeout=20)
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(self.migrate,failpoint=hold)
            try:
                self.assertTrue(entered.wait(timeout=20))
                second=pool.submit(self.migrate)
                with self.assertRaisesRegex(ValueError,'ANOTHER_CURRENT_RUN_OWNS_OUTPUT'):second.result(timeout=10)
            finally:release.set()
            self.assertTrue(first.result(timeout=20)['accepted'])
        result=self.finish()
        self.assertEqual(sum(e['op']=='source_transition' for e in result['owned_account']['ledger']['actions']),1)

    def test_cached_historical_audit_rechecks_source_and_artifact_bytes(self):
        self.legacy(); self.migrate(); result=self.finish()
        self.assertTrue(audit_journal(result['owned_account'],root=self.new,manifest=self.manifest)['accepted'])
        paths=[self.old/'connected_enterprise/finance.py',self.old/self.manifest['jobs'][0]['artifact']]
        for path in paths:
            original=path.read_bytes()
            try:
                path.write_bytes(original+b'\n')
                with self.assertRaises(ValueError):audit_journal(result['owned_account'],root=self.new,manifest=self.manifest)
            finally:path.write_bytes(original)
        self.assertTrue(audit_journal(result['owned_account'],root=self.new,manifest=self.manifest)['accepted'])

    def test_public_audit_rejects_retroactive_terms_and_lineage_omission(self):
        self.legacy(); self.migrate(); result=self.finish()
        forged=copy.deepcopy(result); forged['operating_upgrades']=[]
        with self.assertRaises(ValueError):audit(self.new,self.manifest,forged)
        forged=copy.deepcopy(result); forged['orders'][0]['terms']={}
        with self.assertRaises(ValueError):audit(self.new,self.manifest,forged)

    def test_old_signed_checkpoint_cannot_rewind_new_version_financial_history(self):
        self.legacy(); self.migrate(); migrated=(self.world/'STATE.json').read_bytes()
        result=self.finish(); final=(self.world/'STATE.json').read_bytes()
        native=copy.deepcopy(result['owned_account']['ledger']['actions'])
        for checkpoint in [json.dumps(self.before).encode(),migrated]:
            try:
                (self.world/'STATE.json').write_bytes(checkpoint)
                with self.assertRaisesRegex(ValueError,'REWIND|STALE_SIGNED_OPERATING'):
                    self.finish()
            finally:(self.world/'STATE.json').write_bytes(final)
        self.assertEqual(self.finish()['owned_account']['ledger']['actions'],native)

    def test_public_cli_upgrade_operation_resume_audit_and_scoreboard(self):
        self.legacy(); manifest=self.case/'SERVICES.json'; manifest.write_text(json.dumps(self.manifest))
        policy=self.case/'POLICY.json'; policy.write_text(json.dumps(self.policy))
        command=[sys.executable,'-m','connected_enterprise']
        steps=[['upgrade','--output',str(self.world),'--historical-source',str(self.old),'--manifest',str(manifest),
                '--policy',str(policy),'--expected-checkpoint',digest(self.before),'--id','cli-upgrade'],
               ['operate','--output',str(self.world),'--max-events','2'],['resume','--output',str(self.world)],
               ['audit','--output',str(self.world)],['scoreboard','--output',str(self.world)]]
        for step in steps:
            done=subprocess.run(command+step,cwd=ROOT,text=True,capture_output=True,timeout=120)
            self.assertEqual(done.returncode,0,(step,done.stdout,done.stderr))
        score=json.loads((self.world/'SCOREBOARD.json').read_text())
        self.assertTrue(score['accepted_audit']);self.assertTrue(score['complete'])
        self.assertEqual(self.key.stat().st_ino,self.key_inode)

    def test_forward_engine_only_upgrade_preserves_prior_transition_and_same_business(self):
        from connected_enterprise.operations import prepare_upgrade,upgrade,operate
        self.legacy();manifest=self.case/'SERVICES.json';manifest.write_text(json.dumps(self.manifest))
        prepare_upgrade(self.new,self.old,manifest,self.world,policy=self.policy,
                        expected_checkpoint_sha256=digest(self.before),ident='operating-upgrade-1')
        upgrade(self.world);operate(self.world,max_events=2)
        first=json.loads((self.world/'RESULT.json').read_text())
        first_receipt=(self.world/'MIGRATION_RECEIPT.json').read_bytes()
        checkpoint=json.loads((self.world/'STATE.json').read_text())
        future=self.case/'forward-source';shutil.copytree(self.world/'source-022',future)
        engine=future/'connected_enterprise/engine.py';engine.write_bytes(engine.read_bytes()+b'\n# Authorized forward engine-only source fixture.\n')
        prepare_upgrade(future,self.world/'source-022',manifest,self.world,policy=self.policy,
                        expected_checkpoint_sha256=digest(checkpoint),ident='operating-upgrade-2')
        # A replayed, authenticated intent from the previous source must be
        # retained as rejected evidence rather than replace the new checkpoint.
        import hashlib,hmac
        from commercial.ledger import canonical
        intent_body={'schema':'agi-alpha/connected-operating-checkpoint-intent/v1',
            'path':str(self.world/'STATE.json'),'source_sha256':checkpoint['body']['source_sha256'],
            'manifest_sha256':digest(self.manifest),'prior_sequence':checkpoint['body']['native_sequence']-1,
            'prior_actions_sha256':digest(first['owned_account']['ledger']['actions'][:checkpoint['body']['native_sequence']-1]),'state':checkpoint['body']['state']}
        intent={'body':intent_body,'signature':hmac.new(self.key.read_bytes(),
            b'connected-operating-checkpoint-intent\n'+canonical(intent_body),hashlib.sha256).hexdigest()}
        raw=canonical(intent)+b'\n';intent_path=self.world/'account.sqlite.operating-checkpoint-intent.json'
        intent_path.write_bytes(raw)
        descriptor_before=(self.world/'OPERATOR.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'RETRY_TARGET_CHANGED'):
            prepare_upgrade(self.new,self.world/'source-022',manifest,self.world,policy=self.policy,
                expected_checkpoint_sha256=digest(checkpoint),ident='operating-upgrade-2')
        self.assertEqual((self.world/'OPERATOR.json').read_bytes(),descriptor_before)
        upgrade(self.world)
        intent_path.write_bytes(raw)
        for command in ['resume','audit']:
            done=subprocess.run([sys.executable,'-m','connected_enterprise',command,'--output',str(self.world)],
                                cwd=ROOT,text=True,capture_output=True,timeout=160)
            self.assertEqual(done.returncode,0,done.stderr)
        result=json.loads((self.world/'RESULT.json').read_text())
        self.assertEqual(len(result['operating_upgrades']),2)
        self.assertEqual(result['owned_account']['ledger']['actions'][:len(first['owned_account']['ledger']['actions'])],first['owned_account']['ledger']['actions'])
        archived=list((self.world/'MIGRATION_HISTORY').glob('*.receipt.json'))
        self.assertEqual(len(archived),1);self.assertEqual(archived[0].read_bytes(),first_receipt)
        rejected=self.world/'account.sqlite.rejected-operating-intents'/ (hashlib.sha256(raw).hexdigest()+'.json')
        self.assertEqual(rejected.read_bytes(),raw);self.assertFalse(intent_path.exists())
        self.assertEqual(self.key.stat().st_ino,self.key_inode)

    def test_second_transition_native_commit_crash_recovers_without_downgrade(self):
        from connected_enterprise.operations import prepare_upgrade,upgrade,operate
        from adaptive_enterprise.account import Account
        self.legacy();manifest=self.case/'SERVICES.json';manifest.write_text(json.dumps(self.manifest))
        prepare_upgrade(self.new,self.old,manifest,self.world,policy=self.policy,
                        expected_checkpoint_sha256=digest(self.before),ident='operating-upgrade-1')
        upgrade(self.world);operate(self.world,max_events=2)
        checkpoint=json.loads((self.world/'STATE.json').read_text());future=self.case/'forward-crash-source'
        shutil.copytree(self.world/'source-022',future);engine=future/'connected_enterprise/engine.py'
        engine.write_bytes(engine.read_bytes()+b'\n# Authorized forward crash-recovery fixture.\n')
        descriptor=prepare_upgrade(future,self.world/'source-022',manifest,self.world,policy=self.policy,
                        expected_checkpoint_sha256=digest(checkpoint),ident='operating-upgrade-2')
        original=Account.source_transition
        def crash(account,ticket):
            result=original(account,ticket)
            if ticket['body']['counter']==2:raise InterruptedError('second native transition committed')
            return result
        with patch.object(Account,'source_transition',crash),self.assertRaises(InterruptedError):upgrade(self.world)
        done=subprocess.run([sys.executable,'-m','connected_enterprise','resume','--output',str(self.world)],
                            cwd=ROOT,text=True,capture_output=True,timeout=180)
        self.assertEqual(done.returncode,0,done.stderr)
        result=json.loads((self.world/'RESULT.json').read_text());actions=result['owned_account']['ledger']['actions']
        self.assertEqual(sum(e['op']=='source_transition' and e['args']['counter']==2 for e in actions),1)
        self.assertEqual(sum(e['op']=='cost' and e['args']['id']=='source-upgrade-operating-upgrade-2' for e in actions),1)
        self.assertEqual(self.key.stat().st_ino,self.key_inode)


if __name__=='__main__':unittest.main()
