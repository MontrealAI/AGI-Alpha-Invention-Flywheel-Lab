"""Key-free source-authenticity checks at the historical signing boundary."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from connected_enterprise import finance, upgrades


class OwnerCodecSigningBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='owner-codec-security-')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.historical = root / 'historical'
        self.target = root / 'candidate'
        self.historical.mkdir()
        (self.target / 'connected_enterprise').mkdir(parents=True)
        self.reviewed = Path(upgrades.__file__).with_name('transition_evidence.py').read_bytes()
        self.codec = self.target / 'connected_enterprise/transition_evidence.py'
        self.codec.write_bytes(self.reviewed)
        self.args = dict(historical_root=self.historical, target_root=self.target,
                         manifest={'fixture': True}, path=root / 'unused-account.sqlite',
                         opening=100, working=10, contract='synthetic-only',
                         expected_state_digest='fixture-digest', ident='fixture-transition',
                         day=0, evidence_dir=root / 'evidence')

    def owner_call(self, **overrides):
        options = {**self.args, **overrides}
        with patch.object(finance, 'source_identity', return_value={'sha256': 'fixture-source'}), \
             patch.object(upgrades, 'source_inventory', return_value=[]), \
             patch.object(upgrades.subprocess, 'run') as worker:
            worker.return_value = SimpleNamespace(returncode=0, stderr='',
                                                  stdout=json.dumps({'body': {}, 'signature': 'fixture'}))
            try:
                outcome = upgrades.authorize_upgrade(**options)
                return outcome, worker
            except BaseException:
                self.worker_called_on_error = worker.called
                raise

    def test_reviewed_source_is_cryptographically_pinned(self):
        self.assertEqual(hashlib.sha256(self.reviewed).hexdigest(),
                         upgrades.PINNED_OWNER_EVIDENCE_CODEC_SHA256)
        self.assertEqual(upgrades.reviewed_owner_codec_source(self.target),
                         self.reviewed.decode('utf-8'))

    def test_unreviewed_target_rejected_before_owner_subprocess(self):
        self.codec.write_text("raise RuntimeError('untrusted candidate code')\n")
        with self.assertRaisesRegex(ValueError, 'UNREVIEWED_TARGET_EVIDENCE_CODEC'):
            self.owner_call()
        self.assertFalse(self.worker_called_on_error)

    def test_mutated_target_single_byte_rejected_before_owner_subprocess(self):
        self.codec.write_bytes(self.reviewed + b'\n')
        with self.assertRaisesRegex(ValueError, 'UNREVIEWED_TARGET_EVIDENCE_CODEC'):
            self.owner_call()
        self.assertFalse(self.worker_called_on_error)

    def test_changed_local_codec_rejected_before_owner_subprocess(self):
        fake = self.target / 'trusted/upgrades.py'
        fake.parent.mkdir()
        fake.write_text('synthetic-module')
        fake.with_name('transition_evidence.py').write_text('unreviewed implementation')
        with patch.object(upgrades, '__file__', str(fake)):
            with self.assertRaisesRegex(ValueError, 'OWNER_EVIDENCE_CODEC_SOURCE_CHANGED'):
                self.owner_call()
        self.assertFalse(self.worker_called_on_error)

    def test_selected_reviewed_code_rechecked_before_account_open(self):
        _, worker = self.owner_call()
        self.assertEqual(worker.call_count, 1)
        payload = json.loads(worker.call_args.kwargs['input'])
        self.assertEqual(payload['codec_source'], self.reviewed.decode('utf-8'))
        script = worker.call_args.args[0][2]
        compile(script, 'synthetic-owner-subprocess', 'exec')
        self.assertLess(script.index("UNREVIEWED_OWNER_SIGNING_CODEC"),
                        script.index("with scope, JournalAccount"))
        self.assertIn("if not reuse:a.audit()", script)
        self.assertIn("state=a.verify_checkpoint(p['operating']['prior_checkpoint'])", script)

    def test_legacy_no_evidence_scope_retains_original_owner_path(self):
        _, worker = self.owner_call(evidence_dir=None)
        payload = json.loads(worker.call_args.kwargs['input'])
        self.assertIsNone(payload['codec_source'])
        self.assertIsNone(payload['evidence_dir'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
