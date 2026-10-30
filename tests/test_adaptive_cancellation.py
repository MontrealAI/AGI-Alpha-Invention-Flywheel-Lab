import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from adaptive_enterprise.account import action_digest, audit_account
from tests import test_adaptive_account as fixture


class AdaptiveCancellationRetirementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.AdaptiveAccountTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        fixture.AdaptiveAccountTests.tearDownClass()

    def setUp(self):
        self.fixture = fixture.AdaptiveAccountTests()
        self.fixture.setUp()

    def tearDown(self):
        self.fixture.tearDown()

    def reserve_delivery(self, account, actions=()):
        self.fixture.earn(account)
        job = [j for j in self.fixture.manifest['jobs'] if j['service_id'] == 'reconciliation'][1]
        option = {'id': 'delivery', 'kind': 'delivery', 'upfront_cost': 10_000_000,
                  'later_liabilities': {'ordinary': 3_700_000},
                  'execution': {'kind': 'delivery', 'job_id': job['id'], 'customer_id': 'second-customer',
                                'payment_bps': 290, 'payment_fixed_microUSD': 300_000, 'onboarding_microUSD': 500_000}}
        plan = dict(fixture._plan(), selected_options=[option], upfront_cost=10_000_000,
                    worst_later_reserve=3_700_000, reserve_amount=13_700_000, expected_net=10_000_000)
        state = account.snapshot()['state_digest']
        account.reserve(plan, expected_state_digest=state,
                        authorized_digest=action_digest(plan, state, 13_700_000, 10_000_000),
                        amount=13_700_000, expected_net=10_000_000, day=1)
        if actions:
            account.execute('wallet', {'buyer': 'second-wallet', 'amount': 100_000_000}, 1)
            account.execute('offer', {'id': 'second-order', 'buyer': 'second-wallet', 'price': 100_000_000,
                                      'job_id': job['id'], 'deadline': 100}, 1)
            for action in actions:
                account.execute('event', {'id': 'second-order', 'event_id': 'second-' + action, 'action': action}, 1)
        return plan

    def assert_cancel_rejected(self, account, ident='next-delivery', day=1):
        before = account.export()
        with self.assertRaisesRegex(ValueError, 'CANCELLATION_RETIRED'):
            account.execute('cancel_investment', {'id': ident}, day)
        self.assertEqual(account.export(), before)

    def test_cancellation_before_work_is_retired_without_releasing_reserve(self):
        with self.fixture.open() as account:
            self.reserve_delivery(account)
            self.assert_cancel_rejected(account)
            self.assertEqual(account.snapshot()['summary']['reservedInvestment'], 13_700_000)
            self.assertTrue(account.audit()['accepted'])

    def test_partial_and_accepted_work_cannot_release_unreconciled_costs(self):
        with self.fixture.open() as account:
            self.reserve_delivery(account, ['consent', 'fund'])
            self.assert_cancel_rejected(account)
            account.execute('event', {'id': 'second-order', 'event_id': 'second-prepare', 'action': 'prepare'}, 1)
            self.assert_cancel_rejected(account)
            state = account.snapshot()['summary']
            self.assertEqual(state['reservedInvestment'], 13_700_000)
            self.assertEqual(state['custodyReserve'], 100_000_000)
            self.assertEqual(state['expenses'], 10_000_000)

    def test_duplicate_unknown_and_stale_cancellation_always_fail_closed(self):
        with self.fixture.open() as account:
            self.reserve_delivery(account, ['consent', 'fund', 'prepare'])
            for ident, day in [('next-delivery', 1), ('next-delivery', 1), ('missing-plan', 1), ('next-delivery', 0)]:
                with self.subTest(ident=ident, day=day):
                    self.assert_cancel_rejected(account, ident, day)

    def test_interrupted_prepared_work_reopens_with_obligations_intact(self):
        with self.fixture.open() as account:
            self.reserve_delivery(account, ['consent', 'fund', 'prepare'])
            expected = account.export()
        with self.fixture.open() as account:
            self.assertEqual(account.export(), expected)
            self.assert_cancel_rejected(account)
            self.assertTrue(account.audit()['accepted'])

    def test_finished_plan_cannot_be_cancelled_again(self):
        with self.fixture.open() as account:
            self.fixture.earn(account)
            self.fixture.reserve(account)
            account.finish('next-delivery', 30_000_000, 'b' * 64, 2)
            self.assert_cancel_rejected(account, day=2)
            self.assertEqual(account.snapshot()['summary']['expenses'], 40_000_000)

    def test_abrupt_exit_after_prepare_keeps_reserved_costs_on_recovery(self):
        with self.fixture.open() as account:
            self.reserve_delivery(account, ['consent', 'fund'])
        manifest_path = Path(self.fixture.tmp.name) / 'manifest.json'
        manifest_path.write_text(json.dumps(self.fixture.manifest))
        code = """import json,os,sys
from adaptive_enterprise.account import Account
root,path,manifest=sys.argv[1:]
account=Account(root,json.loads(open(manifest).read()),path,opening=1000000000,working=0,contract='adaptive-account-test')
account.execute('event',{'id':'second-order','event_id':'second-prepare','action':'prepare'},1)
os._exit(17)
"""
        done = subprocess.run([sys.executable, '-c', code, str(self.fixture.root), str(self.fixture.path), str(manifest_path)],
                              cwd=fixture.ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(done.returncode, 17, done.stderr)
        with self.fixture.open() as account:
            self.assert_cancel_rejected(account)
            state = account.snapshot()['summary']
            self.assertEqual(state['reservedInvestment'], 13_700_000)
            self.assertEqual(state['custodyReserve'], 100_000_000)
            self.assertTrue(account.audit()['accepted'])

    def legacy_cancel_record(self, account):
        self.reserve_delivery(account, ['consent', 'fund', 'prepare'])
        record = copy.deepcopy(account.export())
        account._owner.execute('cancel_investment', {'id': 'next-delivery'}, 1)
        record['ledger'] = account._owner.export()
        record['snapshot'] = account.snapshot()
        self.assertEqual(record['ledger']['summary']['reservedInvestment'], 0)
        self.assertEqual(record['ledger']['summary']['expenses'], 10_000_000)
        return record

    def test_valid_native_legacy_cancellation_history_cannot_pass_adaptive_auditor(self):
        with self.fixture.open() as account:
            record = self.legacy_cancel_record(account)
            with self.assertRaisesRegex(ValueError, 'CANCELLATION_RETIRED'):
                audit_account(record, root=self.fixture.root, manifest=self.fixture.manifest)
            with self.assertRaisesRegex(ValueError, 'CANCELLATION_RETIRED'):
                account.audit()

    def test_legacy_cancelled_account_cannot_be_exported_or_reopened(self):
        with self.fixture.open() as account:
            self.legacy_cancel_record(account)
            with self.assertRaisesRegex(ValueError, 'CANCELLATION_RETIRED'):
                account.export()
        with self.assertRaisesRegex(ValueError, 'CANCELLATION_RETIRED'):
            self.fixture.open()


if __name__ == '__main__':
    unittest.main()
