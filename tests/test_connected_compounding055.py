import copy
import tempfile
import unittest
from pathlib import Path
from adaptive_enterprise.instruments import prepare_services
from connected_enterprise.compounding055 import configuration,COHORT
from connected_enterprise.engine import run_world
from connected_enterprise.verify import audit
ROOT=Path(__file__).resolve().parents[1]

class RecurringNative055(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='recurring055-',dir=ROOT)
        cls.folder=Path(cls.temp.name)
        cls.manifest=prepare_services(ROOT,str(cls.folder.relative_to(ROOT)/'jobs'),cohort_seed=COHORT)
        cls.manifest['native_engine']='exact-permanent-v2'
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def run_case(self,name,config,**kwargs):
        return run_world(ROOT,self.manifest,config,2611010550,'channel',self.folder/name,**kwargs)
    def test_resume_new_work_retains_onboarding_and_full_costs(self):
        cfg=configuration('friction',35);cfg.pop('startup_acquisition_policy')
        paused=self.run_case('repeat',cfg,stop_after_events=4)
        prefix=copy.deepcopy(paused['owned_account']['ledger']['actions'])
        result=self.run_case('repeat',cfg)
        self.assertTrue(result['complete']);self.assertTrue(audit(ROOT,self.manifest,result)['accepted'])
        self.assertEqual(result['owned_account']['ledger']['actions'][:len(prefix)],prefix)
        self.assertEqual(result['summary']['expenses'],sum(c['amount'] for c in result['costs']))
        self.assertEqual(len({o['job_id'] for o in result['orders']}),len(result['orders']))
        for order in result['orders']:
            matching=[row for row in cfg['recurring_request_policy']['requests'][order['customer_id']] if row['job_id']==order['job_id']]
            self.assertEqual(len(matching),1)
            self.assertLessEqual(matching[0]['release_hour'],order['qualified_time'])
            self.assertLess(order['qualified_time'],matching[0]['expiry_hour'])
        candidates=[o for o in result['orders'] if o['outcome']=='SETTLED']
        self.assertTrue(candidates)
        for customer in {o['customer_id'] for o in candidates}:
            sequence=[o for o in candidates if o['customer_id']==customer]
            self.assertEqual(sequence[0]['onboarding'],cfg['onboarding_cost'])
            for order in sequence[1:]:self.assertEqual(order['onboarding'],0)
        again=self.run_case('repeat',cfg)
        self.assertEqual(result['owned_account'],again['owned_account'])
        bad=copy.deepcopy(result)
        d=next(d for d in bad['decisions'] if d.get('kind')=='offer')
        d['request_job_id']='unregistered-work'
        with self.assertRaises(ValueError):audit(ROOT,self.manifest,bad)
    def test_competent_substitute_causes_hold_and_no_quote_fees(self):
        cfg=configuration('commodity',14)
        result=self.run_case('hold',cfg)
        self.assertTrue(audit(ROOT,self.manifest,result)['accepted'])
        self.assertEqual(result['orders'],[]);self.assertEqual(result['investments'],[])
        self.assertFalse(any(c['category'].startswith(('outreach','qualification')) for c in result['costs']))
        self.assertEqual(result['summary']['profit'],-cfg['setup_cost']-14*cfg['maintenance_daily'])
    def test_unregistered_work_fails_before_account_creation(self):
        cfg=configuration('friction',14)
        cfg['recurring_request_policy']['requests']['SIM-customer-000'][0]['job_id']='not-admitted'
        cfg['complete_offer_policy']['requested_jobs']['SIM-customer-000']=['not-admitted']
        with self.assertRaisesRegex(ValueError,'PREDECLARED_ADMITTED_CUSTOMER_REQUESTS_REQUIRED'):
            self.run_case('invalid',cfg)
        self.assertFalse((self.folder/'invalid/account.sqlite').exists())
    def test_packet_addition_cannot_change_registered_primitive_workload(self):
        from adaptive_enterprise.instruments import prepare_complete_offer_services
        from connected_enterprise.runner import _service_manifest
        cfg=configuration('friction',14);cfg['recurring_request_policy']['chunk_size']=64
        packets=prepare_complete_offer_services(ROOT,str(self.folder.relative_to(ROOT)/'extra-packet'),cohort_seed=COHORT,packet_jobs=1,packet_rows=4)
        with self.assertRaisesRegex(ValueError,'FROZEN_WORKLOAD_ADMISSION_CHANGED'):
            _service_manifest(packets,{'central':cfg})

class DecisionSourceBinding055(unittest.TestCase):
    def test_mutated_imported_acquisition_code_refuses_financial_write(self):
        from tests.test_connected_chunked_admission048 import copy_sources
        from connected_enterprise.finance import JournalAccount
        with tempfile.TemporaryDirectory(prefix='recurring-source055-') as folder:
            root=Path(folder);copy_sources(root)
            manifest=prepare_services(root,'jobs',cohort_seed=COHORT)
            path=root/'connected_enterprise/recurring_acquisition055.py';original=path.read_bytes()
            with JournalAccount(root,manifest,root/'account.sqlite',opening=100_000_000_000,working=0,contract='recurring-source055') as account:
                try:
                    path.write_bytes(original+b'\n')
                    with self.assertRaisesRegex(ValueError,'SOURCE'):
                        account.cost('blocked',100_000,0)
                finally:path.write_bytes(original)

if __name__=='__main__':unittest.main()
