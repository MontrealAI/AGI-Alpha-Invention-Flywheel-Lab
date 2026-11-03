"""A cache repair must never manufacture missing authority or accept another run."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from omega.primary_recovery import rebuild_checkpoint


class NarrowRecoveryTests(unittest.TestCase):
    def test_missing_account_is_not_created(self):
        with tempfile.TemporaryDirectory() as folder:
            missing = Path(folder)/'missing'
            with patch('omega.primary_recovery.subprocess.run') as worker:
                with self.assertRaisesRegex(ValueError,'EXISTING_REGULAR_RECOVERY_AUTHORITY'):
                    rebuild_checkpoint(missing)
                worker.assert_not_called()
            self.assertFalse(missing.exists())

    def test_another_registration_cannot_open_or_seed_an_account(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            registration = path/'registration.json'
            registration.write_text(json.dumps({'source_hashes':{},'selection':{'opening_microUSD':100_000_000_000}}))
            before = registration.read_bytes()
            with patch('omega.primary_recovery.subprocess.run') as worker:
                with self.assertRaisesRegex(ValueError,'ONLY_KNOWN_50B_FROZEN_REGISTRATION'):
                    rebuild_checkpoint(path)
                worker.assert_not_called()
            self.assertEqual(list(path.iterdir()),[registration])
            self.assertEqual(before,registration.read_bytes())


if __name__ == '__main__':
    unittest.main()
