import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from commercial.ledger import digest
from connected_enterprise.finance import audit_journal
from tests import test_connected_finance as fixture


class ConnectedRejectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.ConnectedFinanceTests.setUpClass()

    @classmethod
    def tearDownClass(cls):
        fixture.ConnectedFinanceTests.tearDownClass()

    def setUp(self):
        self.t = fixture.ConnectedFinanceTests()
        self.t.setUp()

    def tearDown(self):
        self.t.tearDown()

    def unknown(self):
        return self.t.account.execute('event', {'id': 'unknown', 'action': 'consent', 'event_id': 'consent'}, 0)

    def record(self):
        return self.t.account.export()

    def status(self):
        return self.record()['connected_journal']['entries'][-1]['status']

    def test_unknown_trade_rejection_allows_cost_audit_reopen_and_stable_duplicate(self):
        before = self.t.account._account.export()
        with self.assertRaisesRegex(ValueError, 'unknown trade'):
            self.unknown()
        self.assertEqual(self.status(), 'REJECTED')
        self.assertEqual(self.t.account._account.export(), before)
        self.assertEqual(self.t.account.audit()['connected_rejected_entries'], 1)
        self.t.account.cost('legitimate', 7, 1)
        self.t.reopen()
        unchanged = self.record()
        with self.assertRaisesRegex(ValueError, 'unknown trade'):
            self.unknown()
        with self.assertRaisesRegex(ValueError, 'PAYLOAD_CHANGED'):
            self.t.account.execute('event', {'id': 'unknown', 'action': 'fund', 'event_id': 'consent'}, 0)
        self.assertEqual(self.record(), unchanged)
        self.assertEqual(self.t.account.snapshot()['summary']['expenses'], 7)
        self.assertTrue(self.t.account.audit()['accepted'])

    def test_stale_native_cost_is_terminal_without_charging(self):
        self.t.account.cost('first', 7, 2)
        with self.assertRaisesRegex(ValueError, 'EVENT_TIME_REGRESSION'):
            self.t.account.cost('stale', 11, 1)
        self.assertEqual(self.status(), 'REJECTED')
        self.t.account.cost('fresh', 13, 2)
        self.t.reopen()
        self.assertEqual(self.t.account.snapshot()['summary']['expenses'], 20)
        self.assertTrue(self.t.account.audit()['accepted'])

    def test_rejected_seed_spend_has_zero_financial_coverage(self):
        self.t.account.cost('first', 7, 2)
        with self.assertRaisesRegex(ValueError, 'EVENT_TIME_REGRESSION'):
            self.t.spend(allow_seed=True, day=1)
        self.assertEqual(self.status(), 'REJECTED')
        self.t.reopen()
        self.assertEqual(self.t.account.audit()['source_bound_resource_spend_microUSD'], 0)
        self.assertEqual(self.t.account.snapshot()['summary']['expenses'], 7)

    def test_rejected_earned_reservation_leaves_no_proof_or_native_commit(self):
        self.t.earn(); self.t.account.cost('later', 7, 2)
        before = self.t.account._account.export()
        with self.assertRaisesRegex(ValueError, 'EVENT_TIME_REGRESSION'):
            self.t.spend(day=1)
        self.assertEqual(self.status(), 'REJECTED')
        self.assertEqual(self.t.account._account.export(), before)
        self.t.reopen()
        self.assertTrue(self.t.account.audit()['accepted'])

    def test_preexisting_ambiguous_pending_is_not_retired(self):
        with patch.object(self.t.account._account, 'execute', side_effect=InterruptedError('unknown outcome')):
            with self.assertRaises(InterruptedError):
                self.unknown()
        before = self.record()
        with self.assertRaisesRegex(ValueError, 'unknown trade'):
            self.unknown()
        self.assertEqual(self.record(), before)
        self.assertEqual(self.status(), 'PENDING')
        with self.assertRaisesRegex(ValueError, 'PENDING_CONNECTED_ACTION'):
            self.t.account.cost('blocked', 7, 0)

    def test_certified_interruption_before_native_rejection_recovers_terminally(self):
        with patch.object(self.t.account._account, 'execute', side_effect=InterruptedError('before native')):
            with self.assertRaises(InterruptedError):
                self.unknown()
        self.assertEqual(self.status(), 'PENDING')
        self.t.reopen()
        self.assertEqual(self.status(), 'REJECTED')
        self.t.account.cost('after-safe-recovery', 7, 0)
        self.assertTrue(self.t.account.audit()['accepted'])

    def test_uncertified_legacy_pending_rejection_remains_fail_closed(self):
        with patch.object(self.t.account._account, 'execute', side_effect=InterruptedError('before native')):
            with self.assertRaises(InterruptedError):
                self.unknown()
        del self.t.account._journal['entries'][-1]['attempt']
        self.t.account._save()
        before = self.t.account.journal_path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'unknown trade'):
            self.t.reopen()
        self.assertEqual(self.t.account.journal_path.read_bytes(), before)

    def test_value_error_after_native_commit_stays_pending_and_recovers_once(self):
        execute = self.t.account._account.execute
        def lost_ack(*args, **kwargs):
            execute(*args, **kwargs)
            raise ValueError('commit acknowledgment lost')
        with patch.object(self.t.account._account, 'execute', lost_ack):
            with self.assertRaisesRegex(ValueError, 'acknowledgment lost'):
                self.t.account.cost('committed', 7, 0)
        self.assertEqual(self.status(), 'PENDING')
        self.t.reopen()
        self.assertEqual(self.t.account.cost('committed', 7, 0)['summary']['expenses'], 7)
        self.assertEqual(len(self.record()['ledger']['actions']), 1)
        self.assertTrue(self.t.account.audit()['accepted'])

    def test_partial_earned_spend_never_retires_committed_reservation(self):
        self.t.earn()
        with patch.object(self.t.account._account, 'finish', side_effect=ValueError('finish rejected')):
            with self.assertRaisesRegex(ValueError, 'finish rejected'):
                self.t.spend()
        self.assertEqual(self.status(), 'PENDING')
        self.assertEqual(self.t.account.snapshot()['summary']['reservedInvestment'], 60_000_000)
        self.t.reopen()
        self.assertEqual(self.t.spend()['funding'], 'EARNED')
        self.assertEqual(self.t.account.snapshot()['summary']['expenses'], 70_000_000)
        self.assertTrue(self.t.account.audit()['accepted'])

    def test_nonreproducible_error_preserves_pending(self):
        with patch.object(self.t.account._account, 'execute', side_effect=ValueError('unproven rejection')):
            with self.assertRaisesRegex(ValueError, 'unproven rejection'):
                self.t.account.cost('possible', 7, 0)
        self.assertEqual(self.status(), 'PENDING')
        self.t.reopen()
        self.assertEqual(self.t.account.snapshot()['summary']['expenses'], 7)

    def test_failed_rejection_save_requires_reopen_and_preserves_durable_result(self):
        save = self.t.account._save
        calls = []
        def lose_ack(*args, **kwargs):
            save(*args, **kwargs); calls.append(None)
            if len(calls) == 2:
                raise OSError('rejection save acknowledgment lost')
        with patch.object(self.t.account, '_save', lose_ack):
            with self.assertRaises(OSError):
                self.unknown()
        self.assertEqual(self.t.account._journal['entries'][-1]['status'], 'PENDING')
        with self.assertRaisesRegex(ValueError, 'DURABILITY_REQUIRES_REOPEN'):
            self.t.account.cost('blocked', 7, 0)
        self.t.reopen()
        self.assertEqual(self.status(), 'REJECTED')
        self.t.account.cost('allowed', 7, 0)
        self.assertTrue(self.t.account.audit()['accepted'])

    def test_marker_save_rejected_before_write_recovers_from_certificate(self):
        save = self.t.account._save
        calls = []
        def fail_before_save(*args, **kwargs):
            calls.append(None)
            if len(calls) == 2:
                raise OSError('before rejection save')
            return save(*args, **kwargs)
        with patch.object(self.t.account, '_save', fail_before_save):
            with self.assertRaises(OSError):
                self.unknown()
        self.assertEqual(json.loads(self.t.account.journal_path.read_text())['body']['entries'][-1]['status'], 'PENDING')
        self.t.reopen()
        self.assertEqual(self.status(), 'REJECTED')
        self.t.account.cost('after-before-save-recovery', 7, 0)
        self.assertTrue(self.t.account.audit()['accepted'])

    def test_rejected_marker_cannot_hide_uncovered_native_cost(self):
        with self.assertRaisesRegex(ValueError, 'unknown trade'):
            self.unknown()
        self.t.account._account.cost('unlogged', 7, 0)
        with self.assertRaisesRegex(ValueError, 'NATIVE_ACTION_COVERAGE'):
            self.t.account.audit()

    def test_forged_rejection_cannot_hide_committed_action_or_invent_failure(self):
        with self.assertRaisesRegex(ValueError, 'unknown trade'):
            self.unknown()
        forged = copy.deepcopy(self.record())
        entry = forged['connected_journal']['entries'][0]
        entry['request'] = {'operation': 'execute', 'op': 'cost', 'args': {'id': 'valid', 'amount': 7}, 'day': 0}
        entry['key'] = 'native:cost:valid'
        entry['receipt']['request_sha256'] = digest(entry['request'])
        entry['attempt']['request_sha256'] = digest(entry['request'])
        forged['connected_journal_sha256'] = digest(forged['connected_journal'])
        with self.assertRaisesRegex(ValueError, 'REJECTION_NOT_REPRODUCIBLE'):
            audit_journal(forged, root=self.t.root, manifest=self.t.manifest)
        forged = copy.deepcopy(self.record())
        forged['connected_journal']['entries'][0]['receipt']['native_sequence'] = 1
        forged['connected_journal_sha256'] = digest(forged['connected_journal'])
        with self.assertRaisesRegex(ValueError, 'SOURCE_BOUND_CONNECTED_REJECTION'):
            audit_journal(forged, root=self.t.root, manifest=self.t.manifest)


if __name__ == '__main__':
    unittest.main()
