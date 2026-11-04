"""Real canonical-account integration, no financial mocks. Synthetic commerce only."""
import copy,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from genesis002 import engine
from genesis002.audit import audit
from genesis002.backend import Backend
from genesis002.common import read,write,digest
from genesis002.report import render
ROOT=Path(__file__).resolve().parents[1]
REPO=Path(os.environ.get('GENESIS_NATIVE_REPO',ROOT)).resolve()
BASE=read(ROOT/'campaign/genesis-enterprise-002/INPUT.json')
@unittest.skipUnless((REPO/'connected_enterprise/finance.py').exists(),'canonical native checkout required; not a financial mock')
class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='genesis002-tests-');cls.base=Path(cls.tmp.name);cls.central=cls.base/'central'
        cls.result=engine.run(REPO,cls.central,copy.deepcopy(BASE))
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def fresh(self,name,stress='central',cycles=3,**overrides):
        c=copy.deepcopy(BASE);c['cycles']=cycles;c.update(overrides);out=self.base/name
        return out,engine.run(REPO,out,c,stress=stress)
    def test_complete_artifact_native_path(self):
        a=audit(REPO,self.central);self.assertTrue(a['accepted']);self.assertEqual(a['settled_deliveries'],6)
        self.assertEqual(a['earned_funded_repeat_deliveries'],5);self.assertTrue(a['research_paid_from_earnings'])
    def test_money_matches_native(self):
        r=self.result;self.assertEqual(r['modeled_profit_cents'],14320)
        self.assertEqual(r['modeled_profit_cents']*10000,r['native_summary']['profit'])
        self.assertEqual(r['modeled_revenue_cents']*10000,r['native_summary']['collections'])
        self.assertEqual(r['actual_revenue_usd'],0);self.assertEqual(r['external_model_calls'],0)
    def test_simpler_existing_tool_retained(self):
        for p in (self.central/'intents').glob('*.json'):self.assertEqual(read(p)['decision']['selected']['method_id'],'direct-standard')
        self.assertEqual(self.result['research']['decision'],'RETAIN_DIRECT_CONVENTIONAL_TIE')
    def test_research_partition(self):
        s=read(self.central/'ROUTING_STUDY.json');self.assertEqual(s['frozen_policy_sha256'],digest(s['policy']))
        self.assertEqual(s['summary']['learned_router'],s['summary']['direct_conventional'])
        self.assertEqual(s['summary']['learned_router']['accepted'],24);self.assertEqual(s['meta_discovery_superiority'],'NOT_ESTABLISHED')
    def test_completed_resume_unchanged(self):
        before=(self.central/'NATIVE_EXPORT.json').read_bytes();r=engine.run(REPO,self.central,resume=True)
        self.assertEqual(r,self.result);self.assertEqual(before,(self.central/'NATIVE_EXPORT.json').read_bytes())
    def test_cannot_overwrite_existing(self):
        with self.assertRaises(FileExistsError):engine.run(REPO,self.central,copy.deepcopy(BASE))
    def test_no_demand_sunk_costs_remain(self):
        out,r=self.fresh('no-demand',stress='no_demand');self.assertEqual(r['settled'],0);self.assertEqual(r['nonentry'],3)
        self.assertEqual(r['modeled_profit_cents'],-700);self.assertIsNone(r['research']);self.assertTrue(audit(REPO,out)['accepted'])
    def test_refunds_no_seed_recycling(self):
        out,r=self.fresh('rejected',stress='failed_acceptance');self.assertEqual(r['refunded'],1);self.assertEqual(r['nonentry'],2)
        self.assertEqual(r['modeled_revenue_cents'],0);self.assertEqual(r['modeled_profit_cents'],-1350)
        self.assertIsNone(r['research']);self.assertTrue(audit(REPO,out)['accepted'])
    def test_no_payment_no_production(self):
        out,r=self.fresh('no-payment',stress='payment_failure');self.assertEqual(r['no_payment'],1);self.assertEqual(r['nonentry'],2)
        self.assertEqual(r['modeled_profit_cents'],-750);self.assertFalse((out/'deliveries').exists());self.assertTrue(audit(REPO,out)['accepted'])
    def test_research_declines_uneconomic(self):
        out,r=self.fresh('low-research-value',cycles=2,successor_expected_benefit_cents=499)
        self.assertGreater(r['modeled_profit_cents'],0);self.assertIsNone(r['research']);self.assertFalse(read(out/'RESEARCH_DECISION.json')['conduct'])
    def test_pause_resume_same_authority(self):
        c=copy.deepcopy(BASE);c['cycles']=3;out=self.base/'paused';r=engine.run(REPO,out,c,max_cycles=1)
        self.assertFalse(r['complete']);self.assertFalse((out/'REPORT.json').exists());key=(out/'account.sqlite.adaptive-simulation-key').read_bytes()
        r=engine.run(REPO,out,resume=True);self.assertEqual(r['settled'],3)
        self.assertEqual(key,(out/'account.sqlite.adaptive-simulation-key').read_bytes());self.assertTrue(audit(REPO,out)['accepted'])
    def test_crash_after_native_commit(self):
        c=copy.deepcopy(BASE);c['cycles']=2;out=self.base/'interrupted';original=engine._spend
        def fail_after(*args,**kwargs):
            result=original(*args,**kwargs)
            if args[1]=='g2-produce-0':raise RuntimeError('controlled interruption after native commit')
            return result
        with patch.object(engine,'_spend',side_effect=fail_after):
            with self.assertRaises(RuntimeError):engine.run(REPO,out,c)
        key=(out/'account.sqlite.adaptive-simulation-key').read_bytes();r=engine.run(REPO,out,resume=True)
        self.assertEqual(r['settled'],2);self.assertEqual(key,(out/'account.sqlite.adaptive-simulation-key').read_bytes())
        self.assertEqual(sum(x['key']=='spend:g2-produce-0' for x in read(out/'NATIVE_EXPORT.json')['connected_journal']['entries']),1)
    def test_missing_authority_no_reseed(self):
        p=self.central/'account.sqlite.adaptive-simulation-key';data=p.read_bytes();p.unlink()
        try:
            with self.assertRaisesRegex(ValueError,'NO_RESEED'):engine.run(REPO,self.central,resume=True)
        finally:p.write_bytes(data)
    def test_source_change_rejected(self):
        p=self.central/'CONTRACT.json';old=p.read_bytes();x=read(p);x['source']['genesis']['engine.py']='0'*64;write(p,x)
        try:
            with self.assertRaisesRegex(ValueError,'SOURCE_CHANGED'):engine.run(REPO,self.central,resume=True)
        finally:p.write_bytes(old)
    def test_config_change_rejected(self):
        c=copy.deepcopy(BASE);c['opening_cents']+=1000
        with self.assertRaisesRegex(ValueError,'CONFIGURATION_CHANGED'):engine.run(REPO,self.central,c,resume=True)
    def test_stress_change_rejected(self):
        with self.assertRaisesRegex(ValueError,'STRESS_CHANGED'):engine.run(REPO,self.central,resume=True,stress='no_demand')
    def test_tampered_artifact(self):
        p=self.central/'deliveries/000000.json';old=p.read_bytes();x=read(p);x['artifact']['outcome_scope']='intake_readiness';write(p,x)
        try:
            with self.assertRaises(ValueError):audit(REPO,self.central)
        finally:p.write_bytes(old)
    def test_forged_profit(self):
        p=self.central/'REPORT.json';old=p.read_bytes();x=read(p);x['modeled_profit_cents']+=1;write(p,x)
        try:
            with self.assertRaisesRegex(ValueError,'REPORTED_RESULT'):audit(REPO,self.central)
        finally:p.write_bytes(old)
    def test_extra_episode(self):
        p=self.central/'episodes/999999.json';write(p,{'profit':'fake'})
        try:
            with self.assertRaisesRegex(ValueError,'UNREGISTERED_EPISODE'):audit(REPO,self.central)
        finally:p.unlink()
    def test_html_escapes(self):
        p=self.central/'intents/000000.json';old=p.read_bytes();x=read(p);x['decision']['selected']['offer_id']='<script>alert(1)</script>';write(p,x)
        try:
            page=render(self.central);self.assertNotIn('<script>alert(1)',page);self.assertIn('&lt;script&gt;',page)
        finally:p.write_bytes(old)
    def test_completed_account_later_expense(self):
        out,r=self.fresh('stale',cycles=1);b=Backend(REPO);m=read(out/'MANIFEST.json');c=read(out/'CONTRACT.json')['configuration']
        account=b.account(out/'runtime',m,out,c)
        try:account.cost('controlled-later-expense',10000,20)
        finally:account.close()
        with self.assertRaisesRegex(ValueError,'COMPLETED_ACCOUNT_CHANGED'):engine.run(REPO,out,resume=True)
    def test_unattractive_program_creates_no_account(self):
        c=copy.deepcopy(BASE);c['setup_cents']=30000;out=self.base/'declined-startup'
        with self.assertRaisesRegex(ValueError,'NO_JUSTIFIED_STARTUP'):engine.run(REPO,out,c)
        self.assertFalse(out.exists())
    def test_seed_policy_can_be_declared_without_reseeding(self):
        out,r=self.fresh('seed-permitted',stress='payment_failure',cycles=2,continuation_funding_policy='AVAILABLE_NATIVE_CASH')
        self.assertEqual(r['no_payment'],2);self.assertEqual(r['modeled_profit_cents'],-800)
        self.assertTrue(audit(REPO,out)['accepted'])
    def test_seed_protection_disclosed(self):
        self.assertGreater(self.result['native_summary']['equityProtectionBacking'],0);self.assertGreater(self.result['native_summary']['tailReserve'],0)
if __name__=='__main__':unittest.main()
