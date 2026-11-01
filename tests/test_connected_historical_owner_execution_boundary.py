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
        self.inventory = {'connected_enterprise/finance.py': 'a' * 64}
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
        with patch.object(upgrades, 'source_inventory', return_value=self.inventory), \
             patch('commercial.ledger.load_jobs'), \
             patch.object(upgrades.subprocess, 'run', return_value=receipt) as execute, \
             patch.dict(os.environ, {'HISTORICAL_TEST_PRIVATE_MARKER': 'must-not-inherit'}):
            with upgrades._owner_authenticated_history([self.ticket], self.key):
                assert upgrades.verify_historical(self.ticket, {}, root=self.root)['accepted']
            env = execute.call_args.kwargs['env']
            self.assertNotIn('HISTORICAL_TEST_PRIVATE_MARKER', env)
            self.assertEqual(env['PYTHONPATH'], str(self.root))
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


if __name__ == '__main__':
    unittest.main()
