"""Key-free, source-specific regression for the historical Python verifier gate."""
import hashlib
import hmac
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from commercial.ledger import canonical
from connected_enterprise import upgrades


class HistoricalVerifierAuthorityBoundaryTests(unittest.TestCase):
    def setUp(self):
        upgrades._HISTORICAL_AUDITS.clear()
        self.tmp = tempfile.TemporaryDirectory(prefix='historical-verifier-boundary-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'connected_enterprise').mkdir()
        (self.root / 'connected_enterprise/finance.py').write_text('SYNTHETIC_ONLY=True\n')
        self.inventory = upgrades.source_inventory(self.root)
        self.key = b'unit-test-only-key-material-32byte'
        body = {'schema': 'agi-alpha/native-source-transition/v1',
                'historical_root': str(self.root), 'verifier_files': self.inventory,
                'from_source': {'sha256': 'b' * 64},
                'prior_record': {'schema': 'synthetic-only'}}
        self.ticket = {'body': body,
                       'signature': hmac.new(self.key, upgrades.DOMAIN + canonical(body), hashlib.sha256).hexdigest()}

    def test_keyfree_ticket_cannot_select_executable_code(self):
        with patch.object(upgrades, 'source_inventory') as inventory, patch.object(upgrades.subprocess, 'run') as execute:
            with self.assertRaisesRegex(ValueError, 'INDEPENDENT_HISTORICAL_VERIFIER_AUTHORITY_REQUIRED'):
                upgrades.verify_historical(self.ticket, {}, root=self.root)
            inventory.assert_not_called()
            execute.assert_not_called()

    def test_self_consistent_forged_ticket_does_not_acquire_owner_authority(self):
        forged = {'body': self.ticket['body'], 'signature': '0' * 64}
        with self.assertRaisesRegex(ValueError, 'SOURCE_TRANSITION_SIGNATURE_MISMATCH'):
            with upgrades._owner_authenticated_history([forged], self.key):
                pass
        with patch.object(upgrades.subprocess, 'run') as execute:
            with self.assertRaisesRegex(ValueError, 'INDEPENDENT_HISTORICAL_VERIFIER_AUTHORITY_REQUIRED'):
                upgrades.verify_historical(forged, {}, root=self.root)
            execute.assert_not_called()

    def test_authenticated_owner_scope_allows_exact_ticket_only(self):
        receipt = SimpleNamespace(returncode=0, stdout=json.dumps({'accepted': True}), stderr='')
        with patch('commercial.ledger.load_jobs'), \
             patch.object(upgrades.subprocess, 'run', return_value=receipt) as execute, \
             patch.dict(os.environ, {'HISTORICAL_TEST_PRIVATE_MARKER': 'must-not-inherit'}):
            with upgrades._owner_authenticated_history([self.ticket], self.key):
                assert upgrades.verify_historical(self.ticket, {}, root=self.root)['accepted']
            env = execute.call_args.kwargs['env']
            self.assertNotIn('HISTORICAL_TEST_PRIVATE_MARKER', env)
            self.assertNotIn('PYTHONPATH', env)
            self.assertEqual(env['PYTHONNOUSERSITE'], '1')
            self.assertEqual(execute.call_count, 1)
        with self.assertRaisesRegex(ValueError, 'INDEPENDENT_HISTORICAL_VERIFIER_AUTHORITY_REQUIRED'):
            upgrades.verify_historical(self.ticket, {}, root=self.root)

    def test_authorized_ticket_cannot_be_swapped_in_scope(self):
        changed = json.loads(json.dumps(self.ticket))
        changed['body']['historical_root'] = str(self.root / 'changed')
        with upgrades._owner_authenticated_history([self.ticket], self.key):
            with patch.object(upgrades.subprocess, 'run') as execute:
                with self.assertRaisesRegex(ValueError, 'INDEPENDENT_HISTORICAL_VERIFIER_AUTHORITY_REQUIRED'):
                    upgrades.verify_historical(changed, {}, root=self.root)
                execute.assert_not_called()

    def test_owner_authority_cannot_use_short_key(self):
        with self.assertRaisesRegex(ValueError, 'OWNED_ACCOUNT_HMAC_AUTHORITY_REQUIRED'):
            with upgrades._owner_authenticated_history([self.ticket], b'one-byte'):
                pass

    def test_owner_scope_does_not_leave_trust_after_exception(self):
        with self.assertRaisesRegex(RuntimeError, 'intentional'):
            with upgrades._owner_authenticated_history([self.ticket], self.key):
                raise RuntimeError('intentional')
        with patch.object(upgrades.subprocess, 'run') as execute:
            with self.assertRaisesRegex(ValueError, 'INDEPENDENT_HISTORICAL_VERIFIER_AUTHORITY_REQUIRED'):
                upgrades.verify_historical(self.ticket, {}, root=self.root)
            execute.assert_not_called()



class PublishedHistoricalVerifierSelectionTests(unittest.TestCase):
    """Public selection trusts only byte-identical archived code distributions."""
    @classmethod
    def setUpClass(cls):
        from tests.connected_legacy_fixture import materialize
        cls.temp = tempfile.TemporaryDirectory(prefix='pinned-public-verifier-')
        cls.roots = {}
        base = Path(cls.temp.name)
        repo = Path(__file__).resolve().parents[1]
        for commit in (
            '9facd934d9ae763691e8a51052a67793cac5b48e',
            '10bdb2c5787f95158642b068756ba30b58140562',
            '9c74bc5a8de61167a9c157c9cd2532c4a9b7577d',
        ):
            root = base / commit
            materialize(repo, commit, root)
            cls.roots[commit] = root

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def _ticket(self, root, history=None):
        body = {
            'schema': 'agi-alpha/native-source-transition/v1',
            'historical_root': str(root),
            'from_source': {'sha256': 'a' * 64},
            'verifier_files': upgrades.source_inventory(root),
            'prior_record': {'connected_journal': {'source_history': history or []}},
        }
        return {'body': body, 'signature': '0' * 64}

    def test_pinned_manifest_fingerprints_match_every_archived_python_byte(self):
        from commercial.ledger import digest
        expected = {
            '9facd934d9ae763691e8a51052a67793cac5b48e':
                '166f7bd870713590b31bfe76cf0dbb0184f63684005cd0e98bcea297dae5ed8b',
            '10bdb2c5787f95158642b068756ba30b58140562':
                '7b04fd501ec510dfff0ae71a3dcbeae4b62151945eb102d9aca637ec9008c50e',
            '9c74bc5a8de61167a9c157c9cd2532c4a9b7577d':
                '60c3bad4de77f0e8dd113a2fe9fdb7fb212186ded1324099f6808196bc6cc2a8',
        }
        for commit, root in self.roots.items():
            with self.subTest(commit=commit):
                self.assertEqual(digest(upgrades.source_inventory(root)), expected[commit])
                self.assertIn(expected[commit], upgrades.PINNED_PUBLIC_HISTORICAL_INVENTORIES)

    def test_known_exact_source_may_reach_public_verifier_without_owner_key(self):
        root = self.roots['9facd934d9ae763691e8a51052a67793cac5b48e']
        ticket = self._ticket(root)
        receipt = SimpleNamespace(returncode=0, stdout=json.dumps({'accepted': True}), stderr='')
        with patch('commercial.ledger.load_jobs'), patch.object(
            upgrades, '_run_pinned_historical_python', return_value=receipt
        ) as execute:
            self.assertTrue(upgrades.verify_historical(ticket, {}, root=root)['accepted'])
            self.assertEqual(execute.call_count, 1)

    def test_extra_unsigned_python_is_refused_before_historical_execution(self):
        root = self.roots['10bdb2c5787f95158642b068756ba30b58140562']
        ticket = self._ticket(root)
        extra = root / 'untrusted_extra.py'
        try:
            extra.write_text('SYNTHETIC_UNREVIEWED = True\n')
            with patch('commercial.ledger.load_jobs') as jobs, patch.object(
                upgrades, '_run_pinned_historical_python'
            ) as execute:
                with self.assertRaisesRegex(ValueError, 'PINNED_HISTORICAL_VERIFIER_CHANGED'):
                    upgrades.verify_historical(ticket, {}, root=root)
                jobs.assert_not_called()
                execute.assert_not_called()
        finally:
            extra.unlink(missing_ok=True)

    def test_whitelisted_outer_source_cannot_hide_untrusted_nested_verifier(self):
        root = self.roots['9facd934d9ae763691e8a51052a67793cac5b48e']
        inner = {'body': {'schema': 'agi-alpha/native-source-transition/v1',
                          'verifier_files': {'foreign.py': '0' * 64},
                          'prior_record': {'connected_journal': {'source_history': []}}},
                 'signature': '0' * 64}
        ticket = self._ticket(root, history=[inner])
        with patch('commercial.ledger.load_jobs') as jobs, patch.object(
            upgrades, '_run_pinned_historical_python'
        ) as execute:
            with self.assertRaisesRegex(ValueError, 'INDEPENDENT_HISTORICAL_VERIFIER_AUTHORITY_REQUIRED'):
                upgrades.verify_historical(ticket, {}, root=root)
            jobs.assert_not_called()
            execute.assert_not_called()

    def test_unreviewed_ticket_closure_cannot_self_attest_as_trusted(self):
        root = self.roots['9facd934d9ae763691e8a51052a67793cac5b48e']
        ticket = self._ticket(root)
        ticket['body']['verifier_files']['invented.py'] = '0' * 64
        with patch('commercial.ledger.load_jobs') as jobs, patch.object(
            upgrades, '_run_pinned_historical_python'
        ) as execute:
            with self.assertRaisesRegex(ValueError, 'INDEPENDENT_HISTORICAL_VERIFIER_AUTHORITY_REQUIRED'):
                upgrades.verify_historical(ticket, {}, root=root)
            jobs.assert_not_called()
            execute.assert_not_called()



if __name__ == '__main__':
    unittest.main()
