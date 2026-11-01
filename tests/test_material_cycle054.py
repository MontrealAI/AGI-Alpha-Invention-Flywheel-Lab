import copy
import json
from pathlib import Path
import tempfile
import unittest
from connected_enterprise.material054 import solve,ordinary_milp,textbook_order,successor_order
from connected_enterprise.material_cycle054 import economics,USD
from connected_enterprise.material_verify054 import audit_plan
from connected_enterprise.material_service054 import freeze_jobs,load_jobs
from connected_enterprise.finance import JournalAccount
from commercial.terms_exact_v2 import prospective_terms

ROOT=Path(__file__).resolve().parents[1]

class MaterialCycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=textbook_order();cls.art,_=solve(cls.raw)
        cls.second=successor_order(cls.art);cls.b,_=solve(cls.second)
    def test_exact_ordinary_and_equal_content(self):
        for raw,a in [(self.raw,self.art),(self.second,self.b)]:
            ordinary=ordinary_milp(raw)
            self.assertTrue(audit_plan(raw,ordinary)['accepted'])
            self.assertEqual(a['material_cost_microUSD'],ordinary['material_cost_microUSD'])
            self.assertEqual(a,solve(copy.deepcopy(raw))[0])
    def test_voluntary_choice_and_adverse_controls(self):
        self.assertEqual(economics(self.second,self.b,budget=100*USD,value=130*USD)['buyer_choice'],'BUY')
        for kwargs in [{'rival':30*USD},{'value':25*USD},{'transport':100*USD}]:
            args={'budget':100*USD,'value':130*USD};args.update(kwargs)
            self.assertEqual(economics(self.second,self.b,**args)['buyer_choice'],'NO_PURCHASE_FROM_US')
        cold=copy.deepcopy(self.second);cold['stocks']=cold['stocks'][-1:]
        b,_=solve(cold)
        self.assertEqual(economics(cold,b,budget=100*USD,value=130*USD)['buyer_choice'],'NO_PURCHASE_FROM_US')
    def test_positive_kerf_and_resource_limit(self):
        raw=copy.deepcopy(self.second);raw['kerf_mm']=3
        b,_=solve(raw);self.assertTrue(audit_plan(raw,b)['accepted'])
        with self.assertRaisesRegex(RuntimeError,'STATE_WINDOW'):solve(raw,max_states=1)
    def test_native_admission_parent_dependency_and_single_use(self):
        # Engineering fixture account, never an economic campaign result.
        with tempfile.TemporaryDirectory(prefix='material054-unit-',dir=ROOT) as tmp:
            target=Path(tmp);relative=str((target/'evidence').relative_to(ROOT))
            m=freeze_jobs(ROOT,relative,[(self.raw,self.art,None),(self.second,self.b,self.raw['order_id'])])
            a=JournalAccount(ROOT,m,target/'account.sqlite',opening=100000*USD,working=0,contract='material054-test-only')
            try:
                # Commit first job exactly once; native audit must replay this rule.
                for i,raw in enumerate([self.raw,self.second]):
                    ident='test'+str(i);price=100*USD
                    a.execute('wallet',{'buyer':ident,'amount':1000*USD},0)
                    a.execute('register_terms',{'id':ident+'terms','terms':prospective_terms(ident,price,24,1)},0)
                    if i==0:
                        a.execute('offer',{'id':ident,'buyer':ident,'price':price,'job_id':raw['order_id'],'deadline':10,'terms_id':ident+'terms'},0)
                        for action in ['consent','fund','prepare','release']:
                            a.execute('event',{'id':ident,'action':action,'event_id':ident+action},0)
                    else:
                        a.execute('offer',{'id':ident,'buyer':ident,'price':price,'job_id':raw['order_id'],'deadline':10,'terms_id':ident+'terms'},0)
                before=a.snapshot()['summary']
                with self.assertRaisesRegex(ValueError,'ALREADY_COMMITTED'):
                    a.execute('offer',{'id':'duplicate','buyer':'test0','price':100*USD,'job_id':self.raw['order_id'],'deadline':10,'terms_id':'test0terms'},0)
                self.assertEqual(before,a.snapshot()['summary'])
                self.assertTrue(a.audit()['accepted'])
            finally:a.close()
    def test_cross_job_stock_reuse_rejected(self):
        raw=copy.deepcopy(self.raw);raw['order_id']='duplicate-material'
        b,_=solve(raw)
        with tempfile.TemporaryDirectory(prefix='material054-unit-',dir=ROOT) as tmp:
            with self.assertRaisesRegex(ValueError,'DOUBLE_CONSUMPTION'):
                freeze_jobs(ROOT,str((Path(tmp)/'evidence').relative_to(ROOT)),[(self.raw,self.art,None),(raw,b,None)])

if __name__=='__main__':unittest.main()
