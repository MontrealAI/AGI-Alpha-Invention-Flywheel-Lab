"""Pinned PR40 synthetic account crash-window witness; no original account/key access.

Run only with PYTHONPATH pointing at the detached owner source commit from PROTOCOL.
This probe deliberately lives outside tests/ so main's ordinary test discovery does
not confuse an unmerged owner implementation with current released production.
"""
import hashlib
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

OWNER_SHA = 'ced6c1cb004887dcdafaea59a2976020be649f8e'
PROTOCOL_SHA = 'a59518979ce5ac035b2b5e43f829d559fc9c7ba2'
EXPECTED_ID = 'operating-upgrade-1'
_receipts = []


class PostInvoiceBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.test_connected_operating_upgrade import OperatingUpgradeTests
        cls.owner_test = OperatingUpgradeTests
        cls.owner_test.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.owner_test.tearDownClass()
        if os.getenv('P0_CRASH116_RECEIPT'):
            path = Path(os.environ['P0_CRASH116_RECEIPT'])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({
                'schema': 'agi-alpha/post-invoice-crash116/v1',
                'source_sha': OWNER_SHA,
                'protocol_commit': PROTOCOL_SHA,
                'scope': 'disposable synthetic legacy accounts only, not original signer',
                'registered_case_count': 2,
                'passed_case_count': len(_receipts),
                'all_registered_cases_passed': len(_receipts) == 2,
                'qualified_cases': _receipts,
                'commerce': 'NONE',
                'native_original_account_migrated': False,
            }, sort_keys=True, indent=2) + '\n')

    def setUp(self):
        self.case = self.owner_test('test_nonempty_queue_transition_preserves_exact_identity_and_legacy_protection')
        self.case.setUp()

    def tearDown(self):
        self.case.tearDown()

    def exercise(self, *, retry_explicit):
        from connected_enterprise.finance import JournalAccount
        from commercial.ledger import digest
        started = time.perf_counter()
        c = self.case
        c.legacy()
        state = c.before['body']['state']
        self.assertTrue(state['queue'] or state['current'], 'the legacy operating state must be nonempty')
        self.assertTrue(state['orders'], 'the legacy account must contain an order')
        original_action_prefix = c.prior['ledger']['actions']
        initial_state = (c.world / 'STATE.json').read_bytes()
        old_key_inode = c.key.stat().st_ino
        invoice_id = 'source-upgrade-' + EXPECTED_ID
        invoice_amount = c.policy['upgrade_cost_microUSD']
        self.assertGreater(invoice_amount, 0, 'this test must reach a nonzero invoice')
        old_cost = JournalAccount.cost
        reached = []

        def crash_only_after_durable_cost(account, ident, amount, day):
            answer = old_cost(account, ident, amount, day)
            if ident == invoice_id:
                reached.append({'ident': ident, 'amount': amount, 'day': day})
                raise InterruptedError('INJECTED_POST_INVOICE_COMMIT_PRE_STATE_CRASH')
            return answer

        with patch.object(JournalAccount, 'cost', crash_only_after_durable_cost):
            with self.assertRaisesRegex(InterruptedError, 'INJECTED_POST_INVOICE_COMMIT_PRE_STATE_CRASH'):
                c.migrate()

        self.assertEqual(len(reached), 1, 'the exact intended crash boundary was never reached')
        self.assertEqual(reached[0]['amount'], invoice_amount)
        self.assertEqual((c.world / 'STATE.json').read_bytes(), initial_state,
                         'the original signed operating state must remain before the next checkpoint')
        self.assertEqual(c.key.stat().st_ino, old_key_inode)
        self.assertTrue((c.world / 'MIGRATION_INTENT.json').is_file())

        if retry_explicit:
            receipt = c.migrate()
            result = c.finish()
        else:
            result = c.finish()
            receipt = json.loads((c.world / 'MIGRATION_RECEIPT.json').read_text())

        actions = result['owned_account']['ledger']['actions']
        self.assertEqual(actions[:len(original_action_prefix)], original_action_prefix)
        transitions = [row for row in actions
                       if row['op'] == 'source_transition' and row['args']['id'] == EXPECTED_ID]
        invoices = [row for row in actions if row['op'] == 'cost'
                    and row['args']['id'] == invoice_id]
        self.assertEqual(len(transitions), 1, 'transition must occur exactly once')
        self.assertEqual(len(invoices), 1, 'durably committed invoice must not be charged a second time')
        self.assertEqual(invoices[0]['args']['amount'], invoice_amount)
        self.assertEqual(receipt['preserved_queue_sha256'], digest(state['queue']))
        self.assertEqual(receipt['preserved_order_provenance_sha256'], digest(state['orders']))
        self.assertEqual(c.key.stat().st_ino, old_key_inode)
        self.assertTrue(c.public_audit(result)['accepted'])
        self.assertEqual(receipt['monetary_summary_before'], receipt['monetary_summary_after'],
                         'the source transition itself must be cash/profit neutral')
        _receipts.append({
            'route': 'explicit_same_authorization_retry' if retry_explicit else 'canonical_engine_recovery',
            'crash_after_committed_invoice': True,
            'original_native_action_prefix_preserved': True,
            'original_signed_state_preserved_at_crash': True,
            'same_key_inode': True,
            'invoice_count': len(invoices),
            'invoice_amount_microUSD': invoice_amount,
            'source_transition_count': len(transitions),
            'queue_provenance_preserved': True,
            'public_audit_accepted': True,
            'cpu_or_billing': 'NOT_MEASURED',
            'wall_seconds': round(time.perf_counter() - started, 6),
        })

    def test_01_explicit_same_authority_retry(self):
        self.exercise(retry_explicit=True)

    def test_02_canonical_engine_recovers_without_manual_reupgrade(self):
        self.exercise(retry_explicit=False)


if __name__ == '__main__':
    unittest.main(verbosity=2)
