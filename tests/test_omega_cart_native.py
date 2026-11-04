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
    def test_existing_empty_output_is_not_fresh_authority(self):
        out=Path(self.tmp.name)/'preexisting-empty';out.mkdir()
        with self.assertRaisesRegex(FileExistsError,'NEW_ACCOUNT_REQUIRED'):
            n.run(out)
        self.assertEqual(list(out.iterdir()),[])

    def test_actual_acceptance_and_native_account(self):
        with small_native_fixture():self.assertTrue(n.audit(self.path)['accepted'])
        self.assertGreater(self.result['settled_buyers'],0)
        self.assertEqual(self.result['actual_revenue_usd'],0)
    def test_resume_never_reseeds(self):
        before=(self.path/'NATIVE_EXPORT.json').read_bytes()
        with small_native_fixture():again=n.run(self.path,resume=True)
        self.assertEqual(again,self.result);self.assertEqual(before,(self.path/'NATIVE_EXPORT.json').read_bytes())
    def test_completed_resume_rejects_new_authoritative_expense(self):
        out=Path(self.tmp.name)/'post-completion-expense'
        with small_native_fixture(),patch.object(c,'execute',side_effect=lambda:self.original(PILOT)):
            original=n.run(out,stress='no_demand')
        saved_report=(out/'REPORT.json').read_bytes();saved_export=(out/'NATIVE_EXPORT.json').read_bytes()
        def reopen():
            return n.JournalAccount(out/'runtime', n.read(out/'MANIFEST.json'), out/'account.sqlite',
                                    opening=n.OPENING, working=0, contract=n.CONTRACT)
        account=reopen()
        try:
            # The ordinary writer signs and persists the request before applying it.
            with (patch.object(account, '_attempt', side_effect=RuntimeError('durable intent')),
                  self.assertRaisesRegex(RuntimeError, 'durable intent')):
                account.cost('independent-post-completion-cost',10000,364)
            self.assertEqual(account.export()['connected_journal']['entries'][-1]['status'],'PENDING')
        finally:account.close()
        journal=out/'account.sqlite.connected-journal.json';tape_path=out/'account.sqlite.actions.jsonl'
        pending_journal=journal.read_bytes();before_tape=tape_path.read_bytes()
        with small_native_fixture(),self.assertRaisesRegex(ValueError,'COMPLETED_NATIVE_ACCOUNT_DIFFERS'):
            n.run(out,stress='no_demand',resume=True)
        self.assertTrue(tape_path.read_bytes() == before_tape, 'completed resume executed the signed intent')
        self.assertTrue(journal.read_bytes() == pending_journal, 'completed resume consumed the signed intent')
        self.assertEqual(saved_report,(out/'REPORT.json').read_bytes())
        self.assertEqual(saved_export,(out/'NATIVE_EXPORT.json').read_bytes())
        # Deliberately open the normal recovery writer on this separate fixture.
        account=reopen()
        try:
            self.assertEqual(account.export()['connected_journal']['entries'][-1]['status'],'COMPLETE')
            self.assertTrue(account.audit()['accepted'])
            self.assertEqual(account.snapshot()['summary']['profit'],original['native_summary']['profit']-10000)
        finally:account.close()
        tape=(out/'account.sqlite.actions.jsonl').read_bytes()
        with small_native_fixture(),self.assertRaisesRegex(ValueError,'COMPLETED_NATIVE_ACCOUNT_DIFFERS'):
            n.run(out,stress='no_demand',resume=True)
        self.assertEqual(saved_report,(out/'REPORT.json').read_bytes())
        self.assertEqual(saved_export,(out/'NATIVE_EXPORT.json').read_bytes())
        self.assertEqual(tape,(out/'account.sqlite.actions.jsonl').read_bytes())

    def test_public_audit_without_authority_cannot_resume_or_reseed(self):
        saved_export=(self.path/'NATIVE_EXPORT.json').read_bytes()
        with tempfile.TemporaryDirectory(prefix='omega-authority-held-') as held:
            files=list(self.path.glob('account.sqlite*'))
            for f in files:f.rename(Path(held)/f.name)
            try:
                with small_native_fixture():self.assertTrue(n.audit(self.path)['accepted'])
                with small_native_fixture(),self.assertRaisesRegex(ValueError,'EXISTING_NATIVE_AUTHORITY_REQUIRED'):
                    n.run(self.path,resume=True)
                self.assertEqual(list(self.path.glob('account.sqlite*')),[])
                self.assertEqual(saved_export,(self.path/'NATIVE_EXPORT.json').read_bytes())
            finally:
                for f in files:(Path(held)/f.name).rename(f)

    def test_completed_resume_reconstructs_only_missing_derived_database(self):
        old=self.path/'account.sqlite';held=self.path/'derived-cache-held'
        old.rename(held)
        try:
            with small_native_fixture():again=n.run(self.path,resume=True)
            self.assertEqual(again,self.result)
            self.assertTrue(old.is_file())
        finally:
            if old.exists():old.unlink()
            held.rename(old)

    def test_incomplete_resume_missing_authority_cannot_reseed(self):
        saved_export=(self.path/'NATIVE_EXPORT.json').read_bytes()
        with tempfile.TemporaryDirectory(prefix='omega-incomplete-authority-') as held:
            files=[*self.path.glob('account.sqlite*'),self.path/'REPORT.json']
            for f in files:f.rename(Path(held)/f.name)
            try:
                with small_native_fixture(),self.assertRaisesRegex(ValueError,'EXISTING_NATIVE_AUTHORITY_REQUIRED'):
                    n.run(self.path,resume=True)
                self.assertEqual(list(self.path.glob('account.sqlite*')),[])
                self.assertEqual(saved_export,(self.path/'NATIVE_EXPORT.json').read_bytes())
            finally:
                for f in files:(Path(held)/f.name).rename(f)

    def test_pre_account_bootstrap_interruption_can_continue(self):
        out=Path(self.tmp.name)/'bootstrap-interruption'
        with small_native_fixture(),patch.object(n,'JournalAccount',side_effect=RuntimeError('before native account')):
            with self.assertRaisesRegex(RuntimeError,'before native account'):n.run(out,stress='no_demand')
        self.assertFalse((out/'STUDY.json').exists())
        self.assertEqual(list(out.glob('account.sqlite*')),[])
        with small_native_fixture(),patch.object(c,'execute',side_effect=lambda:self.original(PILOT)):
            result=n.run(out,stress='no_demand',resume=True)
        self.assertEqual(result['native_summary']['collections'],0)

    def test_successor_construction_metadata_is_independently_replayed(self):
        out=Path(self.tmp.name)/'successor-metadata'
        with patch.object(c,'CASES',PILOT),patch.object(c,'execute',side_effect=lambda:self.original(PILOT)):
            result=n.run(out)
            self.assertIsNotNone(result['successor'])
            original_report=n.read(out/'REPORT.json');original_successor=n.read(out/'SUCCESSOR.json')
            changed=copy.deepcopy(original_successor)
            changed['construction']['total_rows_built']+=1
            altered=copy.deepcopy(original_report);altered['successor']=changed
            n.save(out/'REPORT.json',altered);n.save(out/'SUCCESSOR.json',changed)
            try:
                with self.assertRaisesRegex(ValueError,'SUCCESSOR_CONSTRUCTION_REPLAY_CHANGED'):n.audit(out)
            finally:
                n.save(out/'REPORT.json',original_report);n.save(out/'SUCCESSOR.json',original_successor)

    def test_unregistered_report_schema_arm_or_stress_cannot_be_renamed(self):
        original_report=n.read(self.path/'REPORT.json');original_contract=n.read(self.path/'CONTRACT.json')
        for field in ('schema','arm','stress'):
            with self.subTest(field=field):
                changed=copy.deepcopy(original_report);changed[field]='unsupported'
                contract=copy.deepcopy(original_contract)
                if field in contract:contract[field]='unsupported'
                n.save(self.path/'REPORT.json',changed);n.save(self.path/'CONTRACT.json',contract)
                try:
                    with small_native_fixture(),self.assertRaisesRegex(ValueError,'REGISTERED_REPORT_SCHEMA_AND_SCENARIO'):
                        n.audit(self.path)
                finally:
                    n.save(self.path/'REPORT.json',original_report);n.save(self.path/'CONTRACT.json',original_contract)

    def test_adaptive_decision_selects_verified_public_offer(self):
        out=Path(self.tmp.name)/'adaptive'
        with small_native_fixture(),patch.object(c,'execute',side_effect=lambda:self.original(PILOT)):
            result=n.run(out,arm='adaptive')
            self.assertTrue(n.audit(out)['accepted'])
        self.assertIsNotNone(result['decision'])
        self.assertGreater(result['settled_buyers'],0)

    def test_adaptive_nonentry_skips_private_observation_and_quotes(self):
        out=Path(self.tmp.name)/'adaptive-nonentry'
        def expensive(*args,**kwargs):
            kwargs['width']=2;m=ORIGINAL_MARKET(*args,**kwargs)
            for o in m['outcomes'][1:]:o['cost_cents']=1000000
            return m
        with patch.object(c,'CASES',PILOT),patch.object(c,'market',side_effect=expensive),patch.object(cases_module,'market',side_effect=expensive),patch.object(c,'execute',side_effect=lambda:self.original(PILOT)),patch.object(n,'private_type',side_effect=AssertionError('private observation after nonentry')):
            result=n.run(out,arm='adaptive')
            self.assertTrue(n.audit(out)['accepted'])
        self.assertEqual(result['nonentry_opportunities'],result['opportunities'])
        self.assertEqual(result['native_summary']['collections'],0)
        self.assertEqual(result['native_summary']['expenses'],(n.TARIFF['setup_cents']+n.TARIFF['discovery_per_market_cents']+n.TARIFF['maintenance_cents'])*n.CENT)
        exported=n.read(out/'NATIVE_EXPORT.json')
        self.assertFalse(any(a['op'] in ('wallet','offer') for a in exported['ledger']['actions']))
        self.assertFalse(any(e['request'].get('id','').startswith('v4-quote-') for e in exported['connected_journal']['entries']))

    def test_adaptive_nonentry_rejects_hidden_buyer_wallet(self):
        out=Path(self.tmp.name)/'adaptive-hidden-wallet'
        def expensive(*args,**kwargs):
            kwargs['width']=2;m=ORIGINAL_MARKET(*args,**kwargs)
            for o in m['outcomes'][1:]:o['cost_cents']=1000000
            return m
        original_cost=n.JournalAccount.cost
        def inject_wallet(account,ident,amount,day):
            if ident=='v4-maintenance':account.execute('wallet',{'buyer':'SIM-v4-buyer-1','amount':10000},day)
            return original_cost(account,ident,amount,day)
        with patch.object(c,'CASES',PILOT),patch.object(c,'market',side_effect=expensive),patch.object(cases_module,'market',side_effect=expensive),patch.object(c,'execute',side_effect=lambda:self.original(PILOT)),patch.object(n.JournalAccount,'cost',inject_wallet):
            with self.assertRaisesRegex(ValueError,'NONENTRY_MUST_PRECEDE_PRIVATE_OBSERVATION_AND_QUOTE'):
                n.run(out,arm='adaptive')

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


class RegisteredCartTimetable(unittest.TestCase):
    def test_positive_post_tax_cash_requires_actual_successor(self):
        original_execute, original_spend = c.execute, n.JournalAccount.spend
        observed = {}
        def omit_eligible(account, ident, *args, **kwargs):
            if ident == 'v4-successor':
                observed.update(account.snapshot()['summary'])
                return None
            return original_spend(account, ident, *args, **kwargs)
        with tempfile.TemporaryDirectory() as directory, patch.object(c, 'CASES', PILOT), patch.object(
                c, 'execute', side_effect=lambda: original_execute(PILOT)):
            out = Path(directory) / 'eligible'
            with patch.object(n.JournalAccount, 'spend', omit_eligible), self.assertRaisesRegex(
                    ValueError, 'POST_TAX_SUCCESSOR_DECISION_CHANGED'):
                n.run(out)
            self.assertGreaterEqual(min(observed['available'], observed['unrestrictedEarned']),
                                    n.TARIFF['successor_cents'] * n.CENT)
            self.assertIsNone(n.read(out/'REPORT.json')['successor'])
            with self.assertRaisesRegex(ValueError, 'POST_TAX_SUCCESSOR_DECISION_CHANGED'):
                n.audit(out)

    def test_additional_wallet_after_year_does_not_belong_to_closed_account(self):
        original = c.execute
        with tempfile.TemporaryDirectory() as directory, small_native_fixture(), patch.object(
                c, 'execute', side_effect=lambda: original(PILOT)):
            out = Path(directory) / 'unearned'
            report = n.run(out, stress='no_demand')
            self.assertIsNone(report['successor'])
            account = n.JournalAccount(out/'runtime', n.read(out/'MANIFEST.json'), out/'account.sqlite',
                                       opening=n.OPENING, working=0, contract=n.CONTRACT)
            try:
                account.execute('wallet', {'buyer': 'unexpected-buyer', 'amount': 75_000_000}, 365)
                export = account.export()
                report['native_summary'] = account.snapshot()['summary']
                report['native_audit'] = account.audit()
            finally:
                account.close()
            self.assertTrue(report['native_audit']['accepted'])
            n.save(out/'NATIVE_EXPORT.json', export)
            n.save(out/'REPORT.json', report)
            with self.assertRaisesRegex(ValueError, 'EXTRA_UNREGISTERED_NATIVE_ACTION'):
                n.audit(out)

    def test_available_cash_and_earned_cash_must_both_cover_successor(self):
        charge = n.TARIFF['successor_cents'] * n.CENT
        for available, earned, stopped, expected in (
                (charge - 1, 2 * charge, False, None), (2 * charge, charge - 1, False, None),
                (charge, charge, False, 'EARNED'), (2 * charge, 2 * charge, True, None)):
            with self.subTest(available=available, earned=earned, stopped=stopped):
                summary = dict(available=available, unrestrictedEarned=earned, investmentStopped=stopped)
                self.assertEqual(n._permitted_funding(summary, charge, 1, False, True), expected)

    def test_deferred_successor_and_report_bindings(self):
        original = c.execute
        with tempfile.TemporaryDirectory() as directory, small_native_fixture(), patch.object(
                c, 'execute', side_effect=lambda: original(PILOT)):
            out = Path(directory) / 'no-demand'
            good = n.run(out, stress='no_demand')
            self.assertTrue(n.audit(out)['accepted'])
            n.save(out/'SUCCESSOR.json', {'pretended': True})
            with self.assertRaisesRegex(ValueError, 'POST_TAX_SUCCESSOR_DECISION_CHANGED'):
                n.audit(out)
            (out/'SUCCESSOR.json').unlink()
            for changes, error in (({'native_audit': {'accepted': True}}, 'REPORTED_NATIVE_AUDIT_CHANGED'),
                                   ({'scope': 'real income'}, 'CLOSED_CART_REPORT_FIELDS_OR_SCOPE_CHANGED'),
                                   ({'additional_revenue_usd': 100}, 'CLOSED_CART_REPORT_FIELDS_OR_SCOPE_CHANGED')):
                with self.subTest(changes=changes):
                    n.save(out/'REPORT.json', {**good, **changes})
                    with self.assertRaisesRegex(ValueError, error):
                        n.audit(out)

    def test_same_day_tax_and_maintenance_cannot_be_interchanged(self):
        original, charge = c.execute, n.JournalAccount.cost
        delayed = {}
        def swap(account, ident, amount, day):
            if ident == 'v4-maintenance':
                delayed['maintenance'] = (ident, amount, day)
                return None
            result = charge(account, ident, amount, day)
            if ident == 'v4-modeled-tax':
                charge(account, *delayed['maintenance'])
            return result
        with tempfile.TemporaryDirectory() as directory, small_native_fixture(), patch.object(
                c, 'execute', side_effect=lambda: original(PILOT)), patch.object(n.JournalAccount, 'cost', swap):
            with self.assertRaisesRegex(ValueError, 'REGISTERED_NATIVE_TIMETABLE_CHANGED'):
                n.run(Path(directory)/'swapped', stress='no_demand')

    def test_wrong_economic_return_cannot_relabel_an_acquisition(self):
        original, spend = c.execute, n.JournalAccount.spend
        def overstate(account, ident, kind, amount, day, work, expected_net, **kwargs):
            if ident == 'v4-quote-1':
                expected_net += 1
            return spend(account, ident, kind, amount, day, work, expected_net, **kwargs)
        with tempfile.TemporaryDirectory() as directory, small_native_fixture(), patch.object(
                c, 'execute', side_effect=lambda: original(PILOT)), patch.object(n.JournalAccount, 'spend', overstate):
            with self.assertRaisesRegex(ValueError, 'REGISTERED_NATIVE_FUNDING_CHANGED'):
                n.run(Path(directory)/'relabelled', stress='no_demand')


if __name__=='__main__':unittest.main()
