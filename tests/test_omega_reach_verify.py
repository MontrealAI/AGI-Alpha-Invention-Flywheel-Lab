"""Adversarial checks of audience attribution and complete native obligations."""
from __future__ import annotations

import copy
import unittest

from connected_enterprise.channels import ChannelBook, default_contracts
from mechanism_harness import reach_policy
from mechanism_harness.reach_verify import (
    JournalCursor, _attribution, _audit_decision, _daily_routes, _private_profile, verify_channel,
)


class ReachVerifierTests(unittest.TestCase):
    def setUp(self):
        self.buyers = [{'id': f'dev-{i:03d}'} for i in range(8)]
        self.contracts = {'pilot': {**default_contracts()['pilot'], 'lead_days': 1,
                                    'activation_reliability_bps': 10000,
                                    'realization_bps': 10000, 'owned_audience_count': 2}}
        self.days = range(4)
        book = ChannelBook(17, self.contracts)
        book.purchase('pilot', 0, 'development-tranche')
        for day in self.days:
            book.expose(day, self.buyers)
        self.book = book.export()

    def check(self, book, plans=('development-tranche',)):
        return verify_channel(book, self.contracts, 17, self.buyers, self.days, plans)

    def test_missing_day_and_phantom_credit_rejected(self):
        self.assertEqual(self.check(self.book)['exposure_days_checked'], 4)
        damaged = copy.deepcopy(self.book)
        del damaged['exposures_by_day']['0']
        with self.assertRaisesRegex(ValueError, 'INCOMPLETE_CHANNEL_DAYS'):
            self.check(damaged)
        damaged = copy.deepcopy(self.book)
        damaged['instances']['development-tranche']['failure_credit_due_microUSD'] = 1
        with self.assertRaisesRegex(ValueError, 'SEEDED_CHANNEL_HISTORY_MISMATCH'):
            self.check(damaged)

    def test_unpaid_access_and_hidden_recipient_rejected(self):
        with self.assertRaisesRegex(ValueError, 'UNDECLARED_CHANNEL_RIGHT'):
            self.check(self.book, plans=())
        damaged = copy.deepcopy(self.book)
        damaged['exposures_by_day']['1']['exposures'][0]['customer_id'] = 'unreached'
        with self.assertRaisesRegex(ValueError, 'SEEDED_CHANNEL_HISTORY_MISMATCH'):
            self.check(damaged)

    def test_attribution_excludes_organic_buyers_and_counts_all_paid_losses(self):
        def row(buyer, source, plan, status, collected, production, fee):
            return {'buyer': buyer, 'source': source, 'source_plan_id': plan, 'status': status,
                    'collections_microUSD': collected, 'production_microUSD': production,
                    'fee_microUSD': fee, 'quote_microUSD': 10}
        rows = [
            row('warm-001', 'warm', None, 'SETTLED', 100, 20, 2),
            row('warm-002', 'warm', None, 'REFUNDED', 0, 13, 0),
            row('reach-005', 'paid', 'dev', 'SETTLED', 90, 19, 1),
            row('reach-012', 'paid', 'dev', 'SETTLED', 100, 19, 1),
            row('reach-016', 'paid', 'dev', 'UNQUALIFIED', 0, 0, 0),
            row('reach-023', 'paid', 'dev', 'REFUNDED', 0, 2, 0),
            row('reach-003', 'organic', None, 'SETTLED', 77, 12, 1),
        ]
        observed = _attribution(rows, {'plan_id': 'dev', 'amount': 625})
        self.assertEqual(observed, {
            'warm_settled': 1, 'warm_contribution_microUSD': 65,
            'first_invoice_microUSD': 625, 'first_exclusive_settled': 1,
            'first_exclusive_collections_microUSD': 100, 'first_paid_variable_costs_microUSD': 82,
        })

    def test_overlapping_contact_preserves_paid_only_exposure_without_double_quote(self):
        paid = [{'customer_id': b, 'source_plan_id': 'dev', 'exposure_id': f'dev-{b}'}
                for b in ('reach-000', 'reach-006', 'reach-013')]
        book = {'exposures_by_day': {'92': {'exposures': paid}}}
        rows = list(_daily_routes(92, book))
        self.assertEqual([(r['buyer'], r['source'], r['paid_exclusive']) for r in rows],
                         [('reach-000', 'organic', False), ('reach-006', 'paid', False),
                          ('reach-013', 'paid', True)])
        self.assertEqual(len(paid), 3)

    def test_seed_cash_cannot_fund_profitable_projection_or_fake_native_grant(self):
        journal = JournalCursor({'connected_journal': {'entries': []},
                                 'ledger': {'actions': [], 'summary': {
                                     'available': 100_000_000_000, 'unrestrictedEarned': 0}}})
        terms = {'arm': 'pilot', 'supplier_contracts': {'pilot': default_contracts()['pilot']}}
        row = {'source': 'warm', 'day': 5, 'status': 'SETTLED', 'collections_microUSD': 30_000_000,
               'production_microUSD': 200_000, 'fee_microUSD': 10_000, 'quote_microUSD': 100_000}
        receipt = reach_policy.decide('pilot', 90, 100_000_000_000, 0, **_attribution([row], None))
        record = {'prefix': journal.prefix(), 'policy': receipt, 'day': 90, 'funding': None, 'purchase': None}
        self.assertEqual(receipt['reason'], 'INSUFFICIENT_UNRESTRICTED_EARNINGS')
        self.assertIsNone(_audit_decision(record, 90, terms, [row], None, journal, {}, set()))
        with self.assertRaisesRegex(ValueError, 'REACH_DECISION_OR_GRANT_CHANGED'):
            _audit_decision({**record, 'funding': {'funding': 'SEED'}}, 90, terms, [row], None, journal, {}, set())
        with self.assertRaisesRegex(ValueError, 'FUTURE_REACH_OBSERVATION'):
            _audit_decision(record, 90, terms, [{**row, 'day': 90}], None, journal, {}, set())

    def test_lifetime_balance_and_per_cart_cap_are_distinct(self):
        buyer = 'dev-005'
        market = {'types': [{'weight': 1, 'values': [0, 32], 'budget_cents': 20, 'outside_utility': 1}]}
        args = (712, buyer, 8, market, {}, 'central')
        self.assertEqual(_private_profile(*args, None, False),
                         (40, True, {'values': [0, 32], 'budget_cents': 20, 'outside_utility': 1}))
        self.assertEqual(_private_profile(*args, 12, False)[2]['budget_cents'], 12)

    def test_valid_native_but_unreported_expense_rejected(self):
        # The canonical engine can legitimately debit an arbitrary business cost.
        # Completing the registered business requires an exact economic purpose.
        action={'before':{'available':100},'after':{'available':99}}
        expense={'operation':'execute','op':'cost','args':{'id':'undeclared','amount':1},'day':1}
        exported={'connected_journal':{'entries':[{'status':'COMPLETE','request':expense,'receipt':{'sequence':1}}]},
                  'ledger':{'actions':[action]}}
        journal=JournalCursor(exported)
        with self.assertRaisesRegex(ValueError,'HIDDEN_EXTRA_REACH_TRANSACTION'):
            journal.finish()
        with self.assertRaisesRegex(ValueError,'UNEXPECTED_REACH_TRANSACTION'):
            journal.cost('registered',1,1)

    def test_replacing_earned_financing_with_seed_debit_is_rejected(self):
        request = {'operation': 'spend', 'id': 'dev', 'kind': 'acquisition', 'amount': 5,
                   'day': 1, 'work': {}, 'expected_net': 1, 'allow_seed': True}
        receipt = {'native_event_sequence': 0, 'funding': 'SEED', 'plan_id': None}
        entry = {'status': 'COMPLETE', 'request': request, 'receipt': receipt}
        action = {'before': {'available': 100, 'unrestrictedEarned': 6}, 'after': {}}
        cursor = JournalCursor({'connected_journal': {'entries': [entry]}, 'ledger': {'actions': [action]}})
        with self.assertRaisesRegex(ValueError, 'REACH_FUNDING_SOURCE_OR_PLAN_CHANGED'):
            cursor.spend('dev', 'acquisition', 5, 1, {}, 1, True)

    def test_journal_rejects_bool_as_money(self):
        request = {'operation':'execute','op':'cost','args':{'id':'quote','amount':True},'day':1}
        exported={'connected_journal':{'entries':[{'status':'COMPLETE','request':request,'receipt':{'sequence':1}}]},
                  'ledger':{'actions':[{'before':{},'after':{}}]}}
        with self.assertRaisesRegex(ValueError,'UNEXPECTED_REACH_TRANSACTION'):
            JournalCursor(exported).cost('quote',1,1)

if __name__ == '__main__':
    unittest.main()
