"""Historical child failures must not transmit arbitrary private diagnostics."""
import hashlib
import hmac
import os
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from commercial.ledger import canonical
from connected_enterprise import upgrades


class HistoricalChildDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-history-diagnostics-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'historical'
        (self.root / 'connected_enterprise').mkdir(parents=True)
        (self.root / 'connected_enterprise/finance.py').write_text('SYNTHETIC = True\n')
        self.marker = 'SYNTHETIC_PRIVATE_DIAGNOSTIC_DO_NOT_COPY'

    def failure(self, code='PRIOR_AUTHORITY_CHANGED'):
        return SimpleNamespace(returncode=23, stdout='', stderr=(
            'historical module diagnostic: ' + self.marker + '\n'
            'ValueError: ' + code + ': ' + self.marker + '\n'))

    def test_whitelisted_category_survives_without_child_text(self):
        message = upgrades._safe_historical_child_failure(self.failure())
        self.assertIn('child_exit=23', message)
        self.assertIn('child_reported_code=PRIOR_AUTHORITY_CHANGED', message)
        self.assertNotIn(self.marker, message)
        self.assertNotIn('historical module diagnostic', message)

    def test_arbitrary_uppercase_child_exception_not_echoed(self):
        message = upgrades._safe_historical_child_failure(self.failure(self.marker))
        self.assertNotIn(self.marker, message)
        self.assertNotIn('child_reported_code=', message)

    def test_owner_signing_failure_does_not_echo_subprocess_output(self):
        with patch('connected_enterprise.finance.source_identity', return_value={'sha256':'0'*64,'files':{}}):
            with patch.object(upgrades, '_run_pinned_historical_python', return_value=self.failure()):
                with self.assertRaisesRegex(ValueError, 'SOURCE_UPGRADE_AUTHORIZATION_FAILED') as raised:
                    upgrades.authorize_upgrade(
                        historical_root=self.root, target_root=self.root, manifest={},
                        path=self.root/'synthetic-account.sqlite', opening=100, working=40,
                        contract='synthetic', expected_state_digest='1'*64,
                        ident='synthetic', day=0)
        self.assertIn('child_reported_code=PRIOR_AUTHORITY_CHANGED', str(raised.exception))
        self.assertNotIn(self.marker, str(raised.exception))

    def test_historical_audit_failure_does_not_echo_subprocess_output(self):
        inventory = upgrades.source_inventory(self.root)
        body = {'schema':'agi-alpha/native-source-transition/v1',
                'historical_root':str(self.root), 'verifier_files':inventory,
                'from_source':{'sha256':'2'*64}, 'prior_record':{'synthetic':True}}
        key = os.urandom(32)
        ticket = {'body':body,'signature':hmac.new(key,upgrades.DOMAIN+canonical(body),hashlib.sha256).hexdigest()}
        with patch('commercial.ledger.load_jobs'):
            with patch.object(upgrades, '_run_pinned_historical_python', return_value=self.failure()):
                with upgrades._owner_authenticated_history([ticket], key):
                    with self.assertRaisesRegex(ValueError, 'PINNED_HISTORICAL_AUDIT_FAILED') as raised:
                        upgrades.verify_historical(ticket, {}, root=self.root)
        self.assertIn('child_exit=23', str(raised.exception))
        self.assertNotIn(self.marker, str(raised.exception))


if __name__ == '__main__':
    unittest.main()
