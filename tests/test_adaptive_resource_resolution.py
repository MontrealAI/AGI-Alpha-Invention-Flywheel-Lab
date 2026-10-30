import copy
import json
import unittest
from unittest.mock import patch

from adaptive_enterprise.account import action_digest, audit_account
from commercial.ledger import digest
from tests import test_adaptive_account as fixture


class ExplicitResourceResolutionTests(unittest.TestCase):
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

    def plan(self):
        option = {'id': 'capacity-only', 'kind': 'capacity', 'upfront_cost': 40_000_000,
                  'later_liabilities': {'none': 0}, 'execution': {'kind': 'capacity', 'source_sha256': 'a' * 64}}
        return dict(fixture._plan('upfront-only'), upfront_cost=40_000_000,
                    worst_later_reserve=0, selected_options=[option])

    def reserve(self, account, plan, cap=50_000_000, day=1):
        state = account.snapshot()['state_digest']
        return account.reserve(plan, expected_state_digest=state,
                               authorized_digest=action_digest(plan, state, cap, 10_000_000),
                               amount=cap, expected_net=10_000_000, day=day)

    def receipt(self, account, plan, day=1, cap=50_000_000):
        option = plan['selected_options'][0]
        return {'schema': 'agi-alpha/adaptive012-obligation-resolution/v1', 'plan_id': plan['plan_id'],
                'resolved_at_day': day, 'native_actions_sha256': account.snapshot()['actions_sha256'],
                'work_artifact_sha256': 'b' * 64, 'upfront_incurred_microUSD': 40_000_000,
                'later_incurred_microUSD': 0, 'unused_reserve_microUSD': cap - 40_000_000,
                'deliveries': [], 'growth': [{'option_id': option['id'],
                    'execution_sha256': digest(option['execution']), 'prepaid_support_microUSD': 0}]}

    def test_upfront_only_finish_and_raw_execute_require_resolution(self):
        with self.fixture.open() as account:
            self.fixture.earn(account); plan = self.plan(); self.reserve(account, plan)
            before = account.export()
            with self.assertRaisesRegex(ValueError, 'RESOLUTION_REQUIRED'):
                account.finish(plan['plan_id'], 0, 'b' * 64, 1)
            with self.assertRaisesRegex(ValueError, 'OBLIGATION_AWARE'):
                account.execute('finish', {'id': plan['plan_id'], 'amount': 0, 'artifact_sha256': 'b' * 64}, 1)
            self.assertEqual(account.export(), before)

    def test_exact_upfront_invoice_and_unused_reserve_resume_idempotently(self):
        with self.fixture.open() as account:
            self.fixture.earn(account); plan = self.plan(); self.reserve(account, plan)
            receipt = self.receipt(account, plan)
            forged = copy.deepcopy(receipt); forged['upfront_incurred_microUSD'] = 0; forged['unused_reserve_microUSD'] = 50_000_000
            with self.assertRaisesRegex(ValueError, 'UPFRONT_RESOURCE_INVOICE'):
                account.finish(plan['plan_id'], 0, 'b' * 64, 1, obligation_receipt=forged)
            account.finish(plan['plan_id'], 40_000_000, 'b' * 64, 1, obligation_receipt=receipt)
            self.assertEqual(account.snapshot()['summary']['expenses'], 50_000_000)
            self.assertEqual(account.snapshot()['summary']['reservedInvestment'], 0)
            expected = account.export()
        with self.fixture.open() as account:
            account.finish(plan['plan_id'], 40_000_000, 'b' * 64, 1, obligation_receipt=receipt)
            self.assertEqual(account.export(), expected)
            self.assertTrue(account.audit()['accepted'])

    def test_top_level_upfront_must_equal_explicit_selected_contracts(self):
        with self.fixture.open() as account:
            self.fixture.earn(account); plan = self.plan()
            plan['selected_options'][0]['upfront_cost'] = 0
            with self.assertRaisesRegex(ValueError, 'UPFRONT_RESOURCE_CONTRACT_MISMATCH'):
                self.reserve(account, plan)
            self.assertEqual(account.snapshot()['summary']['reservedInvestment'], 0)

    def test_top_only_cost_or_later_contract_rejects_before_funds_or_proof(self):
        with self.fixture.open() as account:
            self.fixture.earn(account)
            before = account.export()
            for upfront, later in [(40_000_000, 0), (0, 20_000_000)]:
                plan = dict(fixture._plan('unsupported-top-only'), upfront_cost=upfront, worst_later_reserve=later)
                with self.subTest(upfront=upfront, later=later), self.assertRaisesRegex(ValueError, 'EXPLICIT_SELECTED_OBLIGATION_CONTRACTS'):
                    self.reserve(account, plan)
                self.assertEqual(account.export(), before)

    def test_unsafe_legacy_zero_finish_rejected_by_audit_export_and_reopen(self):
        with self.fixture.open() as account:
            self.fixture.earn(account); plan = self.plan(); self.reserve(account, plan)
            record = account.export()
            account._owner.execute('finish', {'id': plan['plan_id'], 'amount': 0, 'artifact_sha256': 'b' * 64}, 1)
            record['ledger'] = account._owner.export(); record['snapshot'] = account.snapshot()
            with self.assertRaisesRegex(ValueError, 'OBLIGATION_RECEIPT_MISSING'):
                audit_account(record, root=self.fixture.root, manifest=self.fixture.manifest)
            for operation in [account.audit, account.export]:
                with self.assertRaisesRegex(ValueError, 'OBLIGATION_RECEIPT_MISSING'):
                    operation()
        with self.assertRaisesRegex(ValueError, 'OBLIGATION_RECEIPT_MISSING'):
            self.fixture.open()

    def test_prepared_upfront_only_delivery_retains_cost_obligation_after_restart(self):
        with self.fixture.open() as account:
            self.fixture.earn(account); plan = self.plan(); option = plan['selected_options'][0]
            job = [j for j in self.fixture.manifest['jobs'] if j['service_id'] == 'reconciliation'][1]
            option['kind'] = 'delivery'; option['execution'] = {'kind': 'delivery', 'job_id': job['id'],
                'customer_id': 'second-customer', 'payment_bps': 0, 'payment_fixed_microUSD': 0, 'onboarding_microUSD': 0}
            self.reserve(account, plan)
            account.execute('wallet', {'buyer': 'second-wallet', 'amount': 100_000_000}, 1)
            account.execute('offer', {'id': 'second-order', 'buyer': 'second-wallet', 'price': 100_000_000,
                'job_id': job['id'], 'deadline': 100}, 1)
            for action in ['consent', 'fund', 'prepare']:
                account.execute('event', {'id': 'second-order', 'event_id': 'second-' + action, 'action': action}, 1)
        with self.fixture.open() as account:
            with self.assertRaisesRegex(ValueError, 'RESOLUTION_REQUIRED'):
                account.finish(plan['plan_id'], 0, 'b' * 64, 1)
            receipt = self.receipt(account, plan); receipt['growth'] = []
            receipt['deliveries'] = [{'option_id': option['id'], 'job_id': job['id'], 'order_id': 'second-order',
                'artifact_sha256': job['artifact_sha256'], 'customer_id': 'second-customer',
                'outcome': 'NATIVE_ACCEPTED', 'payment_fee_microUSD': 0, 'onboarding_microUSD': 0}]
            account.finish(plan['plan_id'], 40_000_000, 'b' * 64, 1, obligation_receipt=receipt)
            self.assertEqual(account.snapshot()['summary']['expenses'], 50_000_000)
            self.assertEqual(account.snapshot()['summary']['custodyReserve'], 100_000_000)
            self.assertTrue(account.audit()['accepted'])

    def test_definitive_unfunded_rejection_allows_same_plan_and_action_reauthorization(self):
        with self.fixture.open() as account:
            plan = fixture._plan('retry-after-reject')
            with self.assertRaisesRegex(ValueError, 'earned funds'):
                self.reserve(account, plan, day=0)
            self.assertNotIn(plan['plan_id'], account.export()['action_proofs'])
            self.assertEqual(account.snapshot()['sequence'], 0)
        with self.fixture.open() as account:
            self.fixture.earn(account); self.reserve(account, plan)
            self.assertEqual(account.snapshot()['summary']['reservedInvestment'], 50_000_000)
            self.assertTrue(account.audit()['accepted'])

    def test_native_commit_then_valueerror_retains_proof_and_exact_retry(self):
        with self.fixture.open() as account:
            self.fixture.earn(account); plan = fixture._plan('ack-loss'); execute = account._owner.execute
            def after_commit(*args, **kwargs):
                execute(*args, **kwargs)
                raise ValueError('ack lost after native commit')
            with patch.object(account._owner, 'execute', after_commit), self.assertRaisesRegex(ValueError, 'ack lost'):
                self.reserve(account, plan)
            self.assertIn(plan['plan_id'], account.export()['action_proofs'])
            expected = account.export(); body = expected['action_proofs'][plan['plan_id']]['body']
            account.reserve(plan, expected_state_digest=body['expected_state_digest'],
                            authorized_digest=body['authorized_digest'], amount=50_000_000,
                            expected_net=10_000_000, day=1)
            self.assertEqual(account.export(), expected)

    def test_interruption_before_native_commit_preserves_pending_proof(self):
        with self.fixture.open() as account:
            self.fixture.earn(account); plan = fixture._plan('precommit-interrupted')
            with patch.object(account._owner, 'execute', side_effect=InterruptedError('uncertain interruption')):
                with self.assertRaises(InterruptedError): self.reserve(account, plan)
            self.assertIn(plan['plan_id'], account.export()['action_proofs'])
            self.reserve(account, plan)
            self.assertEqual(account.snapshot()['summary']['reservedInvestment'], 50_000_000)

    def test_ambiguous_durable_tail_never_erases_authorization(self):
        with self.fixture.open() as account:
            self.fixture.earn(account); plan = fixture._plan('uncertain-tail'); persistence = account._owner._exchange.persistence
            def uncertain(*args, **kwargs):
                with persistence.tape.open('ab') as stream: stream.write(b'uncertain-tail\n')
                raise ValueError('uncertain durable append')
            with patch.object(account._owner, 'execute', uncertain), self.assertRaisesRegex(ValueError, 'uncertain'):
                self.reserve(account, plan)
            self.assertIn(plan['plan_id'], account.export()['action_proofs'])

    def test_failed_persistence_never_erases_authorization(self):
        with self.fixture.open() as account:
            self.fixture.earn(account); plan = fixture._plan('failed-storage'); persistence = account._owner._exchange.persistence
            def failed(*args, **kwargs):
                persistence.failed = True
                raise ValueError('DURABILITY_FAILURE_REQUIRES_RECOVERY')
            try:
                with patch.object(account._owner, 'execute', failed), self.assertRaisesRegex(ValueError, 'DURABILITY_FAILURE'):
                    self.reserve(account, plan)
                self.assertIn(plan['plan_id'], account.export()['action_proofs'])
            finally: persistence.failed = False

    def test_unrelated_native_advance_and_valueerror_preserve_proof(self):
        with self.fixture.open() as account:
            self.fixture.earn(account); plan = fixture._plan('unrelated-advance'); execute = account._owner.execute
            def advanced(*args, **kwargs):
                execute('cost', {'id': 'unrelated-native-resource', 'amount': 1}, 1)
                raise ValueError('unrelated native advancement')
            with patch.object(account._owner, 'execute', advanced), self.assertRaisesRegex(ValueError, 'advancement'):
                self.reserve(account, plan)
            self.assertIn(plan['plan_id'], account.export()['action_proofs'])
            self.assertEqual(account.snapshot()['summary']['expenses'], 10_000_001)

    def test_existing_interrupted_proof_survives_later_noncommitting_valueerror(self):
        with self.fixture.open() as account:
            self.fixture.earn(account); plan = fixture._plan('prior-pending')
            with patch.object(account._owner, 'execute', side_effect=InterruptedError('first interruption')):
                with self.assertRaises(InterruptedError): self.reserve(account, plan)
            proof = account.export()['action_proofs'][plan['plan_id']]
            with patch.object(account._owner, 'execute', side_effect=ValueError('later rejection')):
                with self.assertRaisesRegex(ValueError, 'later rejection'): self.reserve(account, plan)
            self.assertEqual(account.export()['action_proofs'][plan['plan_id']], proof)
            self.reserve(account, plan)
            self.assertEqual(account.snapshot()['summary']['reservedInvestment'], 50_000_000)


if __name__ == '__main__':
    unittest.main()
