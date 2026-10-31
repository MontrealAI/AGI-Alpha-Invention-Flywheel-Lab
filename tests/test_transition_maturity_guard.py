"""Real native maturity execution with synthetic snapshot fault injection.

No native balance corruption is claimed; injected views never mutate the ledger.
"""
import copy
import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from commercial.terms import prospective_terms
from enterprise.services import SOURCE_PATHS as SERVICES, prepare_services
from experiments.commerce006 import PINS
ROOT=Path(__file__).resolve().parents[1]
PATCHED=ROOT/'connected_enterprise/finance.py'
spec=importlib.util.spec_from_file_location('connected_enterprise.maturity_guard_review',PATCHED)
finance=importlib.util.module_from_spec(spec);spec.loader.exec_module(finance)

class NativeMaturityGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='maturity-guard-source-');cls.root=Path(cls.tmp.name)
        for name in set(finance.SOURCE_PATHS)|set(SERVICES)|set(PINS):
            p=cls.root/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(PATCHED if name=='connected_enterprise/finance.py' else ROOT/name,p)
        cls.manifest=prepare_services(cls.root,'services');cls.job=next(j for j in cls.manifest['jobs'] if j['service_id']=='reconciliation')
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='maturity-guard-account-');self.account=finance.JournalAccount(self.root,self.manifest,Path(self.tmp.name)/'account.sqlite',opening=20_000_000,working=0,contract='maturity-guard-synthetic')
    def tearDown(self):self.account.close();self.tmp.cleanup()
    def settle(self,ident='o',at=0):
        a=self.account;terms=prospective_terms(ident,2_000_000,20,at+2,residual=100_000)
        a.execute('register_terms',{'id':'t-'+ident,'terms':terms},at);a.execute('wallet',{'buyer':'b-'+ident,'amount':2_000_000},at)
        a.execute('offer',{'id':ident,'buyer':'b-'+ident,'price':2_000_000,'job_id':self.job['id'],'deadline':10,'terms_id':'t-'+ident},at)
        for action,t in [('consent',at),('fund',at),('prepare',at+1),('release',at+2)]:a.execute('event',{'id':ident,'event_id':ident+'-'+action,'action':action},t)
    def test_real_maturity_releases_reserve_without_cash_or_profit(self):
        self.settle();before=self.account.snapshot()['summary'];after=self.account.advance_financial(21)['summary']
        self.assertEqual((before['cash'],before['profit']),(after['cash'],after['profit']));self.assertLess(after['tailReserve'],before['tailReserve']);self.assertTrue(self.account.audit()['accepted'])
        self.assertEqual(self.account.advance_financial(21)['summary'],after)
    def test_cash_and_profit_fault_views_detected_after_actual_native_execution(self):
        self.settle();a=self.account;execute=a.execute;snapshot=a._account.snapshot
        for field in ['cash','profit']:
            # Each iteration uses a fresh separately settled account; no reseeding of a business.
            if field=='profit':
                a.close();self.tmp.cleanup();self.setUp();self.settle();a=self.account;execute=a.execute;snapshot=a._account.snapshot
            matured=[False]
            def run(op,args,day):
                result=execute(op,args,day)
                if op=='mature':matured[0]=True
                return result
            def view():
                result=snapshot()
                if matured[0]:result=copy.deepcopy(result);result['summary'][field]+=1
                return result
            with self.subTest(field=field),patch.object(a,'execute',side_effect=run),patch.object(a._account,'snapshot',side_effect=view):
                with self.assertRaisesRegex(ValueError,'MATURITY_CANNOT_CREATE_CASH_OR_PROFIT'):a.advance_financial(21)
            self.assertTrue(matured[0]);self.assertTrue(a.audit()['accepted'])
    def test_independent_native_replay_rejects_forged_maturity_balance(self):
        from commercial.ledger import audit, digest
        self.settle();self.account.advance_financial(21)
        tape=self.account.export()['ledger']
        for field in ['cash','profit']:
            forged=copy.deepcopy(tape);event=next(e for e in forged['actions'] if e['op']=='mature');event['after'][field]+=1
            forged['actions_sha256']=digest(forged['actions'])
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'EVENT_DERIVED_BALANCE_MISMATCH'):
                audit(forged,root=self.root,manifest=self.manifest)

    def test_legitimate_same_clock_claim_payment_and_later_claim_are_not_forbidden(self):
        self.settle();a=self.account
        a.execute('claim',{'id':'o','claim_id':'c','amount':50_000,'kind':'ordinary'},20)
        a.execute('resolve_claim',{'id':'o','claim_id':'c','settlement_id':'s','resolution':'pay'},21)
        before=a.snapshot()['summary'];after=a.advance_financial(21)['summary'];self.assertEqual((before['cash'],before['profit']),(after['cash'],after['profit']))
        a.execute('claim',{'id':'o','claim_id':'late','amount':5_000,'kind':'ordinary'},21)
        a.execute('resolve_claim',{'id':'o','claim_id':'late','settlement_id':'s2','resolution':'pay'},21)
        self.assertTrue(a.audit()['accepted'])

if __name__=='__main__':unittest.main()
