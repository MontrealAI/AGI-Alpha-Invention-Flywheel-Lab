"""Exact economic semantics, synthesis, strategy and real native fault tests."""
import copy
from fractions import Fraction
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from contextlib import ExitStack, contextmanager
from mechanism_harness import market_cases as cases_module

from commercial.ledger import digest
from mechanism_harness import cart_program as v,cart_synthesis as s,cart_campaign as c,cart_native as n
from mechanism_harness.market_cases import market

PILOT=((1337,'substitute'),)
ORIGINAL_MARKET=cases_module.market

@contextmanager
def small_native_fixture():
    # Four-type engineering fixtures only; registered V4 confirmation is unchanged.
    def small(*args,**kwargs):
        kwargs['width']=2
        return ORIGINAL_MARKET(*args,**kwargs)
    with ExitStack() as stack:
        stack.enter_context(patch.object(c,'CASES',PILOT))
        stack.enter_context(patch.object(c,'market',side_effect=small))
        stack.enter_context(patch.object(cases_module,'market',side_effect=small))
        yield


class CartNativeExecution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='omega-v4-unit-');cls.path=Path(cls.tmp.name)/'central'
        cls.original=staticmethod(c.execute)
        with small_native_fixture(),patch.object(c,'execute',side_effect=lambda:cls.original(PILOT)):
            cls.result=n.run(cls.path)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_actual_acceptance_and_native_account(self):
        with small_native_fixture():self.assertTrue(n.audit(self.path)['accepted'])
        self.assertGreater(self.result['settled_buyers'],0)
        self.assertEqual(self.result['actual_revenue_usd'],0)
    def test_resume_never_reseeds(self):
        before=(self.path/'NATIVE_EXPORT.json').read_bytes()
        with small_native_fixture():again=n.run(self.path,resume=True)
        self.assertEqual(again,self.result);self.assertEqual(before,(self.path/'NATIVE_EXPORT.json').read_bytes())
    def test_revenue_or_profit_tamper_rejected(self):
        old=n.read(self.path/'REPORT.json');r=copy.deepcopy(old);r['native_summary']['profit']+=1
        n.save(self.path/'REPORT.json',r)
        try:
            with small_native_fixture(),self.assertRaisesRegex(ValueError,'SUMMARY'):n.audit(self.path)
        finally:n.save(self.path/'REPORT.json',old)
    def test_refusal_cannot_be_faked_by_cash_flag(self):
        file=self.path/'order-001.json';old=n.read(file);r=copy.deepcopy(old);r['affordable']=not r['affordable'];n.save(file,r)
        try:
            with small_native_fixture(),self.assertRaisesRegex(ValueError,'CASH'):n.audit(self.path)
        finally:n.save(file,old)
    def test_source_change_blocks_resume(self):
        with patch.object(n,'source_identity',return_value={'changed':'0'*64}),self.assertRaisesRegex(ValueError,'SOURCE'):n.run(self.path,resume=True)
    def test_failed_acceptance_refunds_without_income(self):
        out=Path(self.tmp.name)/'rejected'
        with small_native_fixture(),patch.object(c,'execute',side_effect=lambda:self.original(PILOT)):
            r=n.run(out,stress='failed_acceptance')
        self.assertGreater(r['refunded_buyers'],0);self.assertEqual(r['native_summary']['collections'],0)
        self.assertLess(r['native_summary']['profit'],0)
    def test_no_demand_spending_remains_visible(self):
        out=Path(self.tmp.name)/'no-demand'
        with small_native_fixture(),patch.object(c,'execute',side_effect=lambda:self.original(PILOT)):
            r=n.run(out,stress='no_demand')
        self.assertEqual(r['settled_buyers'],0);self.assertLess(r['native_summary']['profit'],0)
    def test_unavailable_payment_retains_acquisition_cost_without_sale(self):
        out=Path(self.tmp.name)/'payment-unavailable'
        with small_native_fixture(),patch.object(c,'execute',side_effect=lambda:self.original(PILOT)):
            r=n.run(out,stress='payment_failure')
        self.assertEqual(r['settled_buyers'],0)
        self.assertEqual(r['native_summary']['collections'],0)
        self.assertLess(r['native_summary']['profit'],0)
        exported=n.read(out/'NATIVE_EXPORT.json')
        self.assertFalse(any(a['op']=='offer' for a in exported['ledger']['actions']))

    def test_required_fee_omission_fails_independent_audit(self):
        original=n.JournalAccount.cost
        def missing(account,ident,amount,day):
            if ident.startswith('v4-fee-'):return None
            return original(account,ident,amount,day)
        out=Path(self.tmp.name)/'omit-fee'
        with small_native_fixture(),patch.object(c,'execute',side_effect=lambda:self.original(PILOT)),patch.object(n.JournalAccount,'cost',missing),self.assertRaisesRegex(ValueError,'MISSING_OR_EXTRA_REQUIRED_DEBIT'):
            n.run(out)

if __name__=='__main__':unittest.main()
