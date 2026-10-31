import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from adaptive_enterprise.instruments import prepare_services
from connected_enterprise.operations import _copy_source, _copy_inputs
from connected_enterprise.upgrades import authorize_upgrade

ROOT=Path(__file__).resolve().parents[1]


class PendingClaimSourceUpgradeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture=tempfile.TemporaryDirectory(prefix='claim-upgrade-sources-');cls.base=Path(cls.fixture.name)
        cls.old=cls.base/'prior-version';cls.new=cls.base/'forward-version';_copy_source(ROOT,cls.old)
        cls.manifest=prepare_services(cls.old,'services',cohort_seed=2610312203)
        _copy_source(ROOT,cls.new);_copy_inputs(cls.old,cls.new,cls.manifest)
        p=cls.new/'connected_enterprise/finance.py';p.write_bytes(p.read_bytes()+b'\n# Authorized no-op source-version fixture for claim continuity.\n')

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def run_case(self,kind):
        with tempfile.TemporaryDirectory(prefix='pending-claim-upgrade-') as directory:
            path=Path(directory)/'account.sqlite';contract='pending-claim-authenticated-continuation'
            payload={'root':str(self.old),'path':str(path),'manifest':self.manifest,'contract':contract,'kind':kind}
            before_code='''import json,sys
from connected_enterprise.finance import JournalAccount
from commercial.terms import prospective_terms
p=json.load(sys.stdin)
with JournalAccount(p['root'],p['manifest'],p['path'],opening=500000000,working=100000000,contract=p['contract']) as a:
 job=next(j for j in p['manifest']['jobs'] if j['service_id']=='reconciliation' and j['accepted'])
 terms=prospective_terms('owned-claim-order',100000000,20,2,residual=5000000,premium=1000000,coverage_limit=50000000,deductible=10000000,payout_delay_hours=2)
 a.execute('register_terms',{'id':'owned-v1','terms':terms},0)
 a.execute('wallet',{'buyer':'buyer','amount':100000000},0)
 a.execute('offer',{'id':'owned-claim-order','buyer':'buyer','price':100000000,'job_id':job['id'],'deadline':10,'terms_id':'owned-v1'},0)
 for action in ['consent','fund','prepare','release']:a.execute('event',{'id':'owned-claim-order','action':action,'event_id':'owned-'+action},2)
 a.cost('complete-original-service',10000000,2)
 a.execute('claim',{'id':'owned-claim-order','claim_id':'pending-claim','amount':20000000,'kind':p['kind']},20)
 print(json.dumps(a.export()))
'''
            env={**os.environ,'PYTHONPATH':str(self.old),'PYTHONDONTWRITEBYTECODE':'1'}
            done=subprocess.run([sys.executable,'-c',before_code],input=json.dumps(payload),cwd=self.old,env=env,text=True,capture_output=True,timeout=60)
            self.assertEqual(done.returncode,0,done.stderr);before=json.loads(done.stdout)
            key=path.with_name(path.name+'.adaptive-simulation-key');inode=key.stat().st_ino
            ticket=authorize_upgrade(historical_root=self.old,target_root=self.new,manifest=self.manifest,path=path,
                                     opening=500000000,working=100000000,contract=contract,
                                     expected_state_digest=before['snapshot']['state_digest'],ident='claim-source-forward',day=20)
            payload.update(root=str(self.new),ticket=ticket,before=before)
            after_code='''import json,sys
from connected_enterprise.finance import JournalAccount
p=json.load(sys.stdin)
with JournalAccount.upgrade_source(p['root'],p['manifest'],p['path'],opening=500000000,working=100000000,contract=p['contract'],authorization=p['ticket']) as a:
 assert a.snapshot()['summary']==p['before']['ledger']['summary']
 assert a.export()['ledger']['prospective_claims']==p['before']['ledger']['prospective_claims']
 after=a.advance_financial(21)['summary'];assert after['payables']==20000000 and after['tailReserve']==5000000
 assert after['cash']==p['before']['ledger']['summary']['cash']
 if p['kind']=='covered':
  a.execute('resolve_claim',{'id':'owned-claim-order','claim_id':'pending-claim','settlement_id':'pay','resolution':'pay'},22)
  prior=a.snapshot()['summary']
  a.execute('recover_claim',{'id':'owned-claim-order','claim_id':'pending-claim','settlement_id':'collect','amount':10000000,'source_tx':'synthetic-collected-recovery'},24)
  recovered=a.snapshot()['summary'];assert recovered['cash']-prior['cash']==10000000 and recovered['recoveryIncome']==10000000
 else:
  assert after['payables']==20000000
  if p['kind']=='provider_default':assert after['investmentStopped']
 assert a.audit()['accepted']
 print(json.dumps({'accepted':True,'summary':a.snapshot()['summary']}))
'''
            done=subprocess.run([sys.executable,'-c',after_code],input=json.dumps(payload),cwd=self.new,
                                env={**env,'PYTHONPATH':str(self.new)},text=True,capture_output=True,timeout=60)
            self.assertEqual(done.returncode,0,done.stderr);self.assertTrue(json.loads(done.stdout)['accepted'])
            self.assertEqual(key.stat().st_ino,inode)

    def test_pending_disputed_claim_survives_authenticated_source_upgrade_and_maturity(self):
        self.run_case('disputed')

    def test_covered_claim_recovery_is_collected_only_after_preserved_upgrade_and_payment(self):
        self.run_case('covered')

    def test_provider_default_and_unpaid_liability_are_not_erased_by_upgrade(self):
        self.run_case('provider_default')


if __name__=='__main__':unittest.main()
