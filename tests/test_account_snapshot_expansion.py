"""Snapshot optimization must equal the existing full-export observation.

Only the newly registered expansion schema selects this path. These tests use
real native transactions and separately reconstruct the historical snapshot.
"""
import copy
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from adaptive_enterprise.account import Account
from commercial.ledger import digest
from omega.expansion_native import NativeBridge
from omega.test_expansion_native import order


def full_export_snapshot(account):
    tape = account._owner.export()
    return {'summary': copy.deepcopy(tape['summary']),
            'state_digest': digest({'config': tape['config'], 'actions_sha256': tape['actions_sha256'],
                                    'summary': tape['summary']}),
            'actions_sha256': tape['actions_sha256'], 'sequence': len(tape['actions']),
            'scope': 'SIMULATED', 'ownership': 'MANDATORY_SINGLE_LOCAL_POSIX_WRITER',
            'filesystem': account.filesystem}


class ExpansionSnapshotTests(unittest.TestCase):
    def test_historical_readonly_wrapper_without_manifest_retains_export_path(self):
        # FastPrefixRelay deliberately exposes only the old snapshot protocol;
        # it is not an Account instance and has no manifest attribute.
        tape = {'summary': {'cash': 123}, 'config': {'contract': 'historical'},
                'actions': [], 'actions_sha256': digest([])}
        calls = []
        wrapper = SimpleNamespace(
            _assert_owner=lambda: calls.append('guard'),
            _owner=SimpleNamespace(export=lambda: calls.append('export') or tape),
            filesystem='LOCAL_POSIX')
        self.assertEqual(Account.snapshot(wrapper), full_export_snapshot(wrapper))
        self.assertEqual(calls, ['guard', 'export', 'export'])
        self.assertFalse(hasattr(wrapper, 'manifest'))

    def assertEquivalent(self, bridge):
        account = bridge.account._account
        self.assertEqual(account.snapshot(), full_export_snapshot(account))

    def test_empty_accepted_uncollected_release_refund_claim_and_maturity_equivalence(self):
        with tempfile.TemporaryDirectory() as directory:
            with NativeBridge(Path(directory) / 'account') as bridge:
                self.assertEquivalent(bridge)
                bridge.deliver(order('delayed', hour=1, collection_delay_hours=5))
                self.assertEquivalent(bridge)
                self.assertGreater(bridge.account.snapshot()['summary']['custodyReserve'], 0)
                bridge.advance(6)
                self.assertEquivalent(bridge)
                bridge.deliver(order('refunded', hour=7, accept=False))
                self.assertEquivalent(bridge)
                bridge.account.execute('claim', {'id': 'delayed', 'claim_id': 'dispute',
                                                 'amount': 1000000, 'kind': 'disputed'}, 8)
                self.assertEquivalent(bridge)
                bridge.account.execute('resolve_claim', {'id': 'delayed', 'claim_id': 'dispute',
                    'settlement_id': 'deny-dispute', 'resolution': 'deny'}, 9)
                self.assertEquivalent(bridge)
                bridge.advance(800)
                self.assertEquivalent(bridge)
                self.assertTrue(bridge.account.audit()['accepted'])

    def test_fresh_history_and_configuration_identity_no_cached_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            with NativeBridge(Path(directory) / 'account') as bridge:
                bridge.account.cost('actual-cost', 1000000, 1)
                account = bridge.account._account
                before = account.snapshot()
                exchange = account._owner._exchange
                original = exchange.actions[-1]['day']
                try:
                    exchange.actions[-1]['day'] = original + 1
                    changed = account.snapshot()
                    self.assertNotEqual(changed['actions_sha256'], before['actions_sha256'])
                    self.assertNotEqual(changed['state_digest'], before['state_digest'])
                    self.assertEquivalent(bridge)
                finally:
                    exchange.actions[-1]['day'] = original
                original_contract = exchange.config['contract']
                try:
                    exchange.config['contract'] = original_contract + ':changed'
                    self.assertNotEqual(account.snapshot()['state_digest'], before['state_digest'])
                    self.assertEquivalent(bridge)
                finally:
                    exchange.config['contract'] = original_contract
                self.assertEqual(account.snapshot(), before)
                changed = account.snapshot()
                changed['summary']['cash'] = -1
                self.assertEqual(account.snapshot(), before)

    def test_snapshot_avoids_full_export_without_skipping_live_owner_check(self):
        with tempfile.TemporaryDirectory() as directory:
            with NativeBridge(Path(directory) / 'account') as bridge:
                account = bridge.account._account
                expected = full_export_snapshot(account)
                with patch.object(account._owner, 'export', side_effect=AssertionError('full export performed')):
                    self.assertEqual(account.snapshot(), expected)
                with patch.object(account._owner.lease, 'assert_owner', side_effect=ValueError('LEASE_LOST')):
                    with self.assertRaisesRegex(ValueError, 'LEASE_LOST'):
                        account.snapshot()
                with patch('connected_enterprise.finance.source_identity', return_value={'changed': True}):
                    with self.assertRaisesRegex(ValueError, 'CONNECTED_FINANCE_SOURCE_CHANGED'):
                        bridge.account.snapshot()
            with self.assertRaisesRegex(ValueError, 'ADAPTIVE_ACCOUNT_CLOSED'):
                account.snapshot()


if __name__ == '__main__':
    unittest.main()
