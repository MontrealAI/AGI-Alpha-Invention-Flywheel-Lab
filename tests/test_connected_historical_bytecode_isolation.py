"""Key-free regression: recorded Python hashes do not cover executable .pyc caches."""
import hashlib
import json
import os
from pathlib import Path
import py_compile
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from connected_enterprise import upgrades


class HistoricalPythonCacheIsolationTests(unittest.TestCase):
    def test_unhashed_timestamp_cache_cannot_override_pinned_source(self):
        with tempfile.TemporaryDirectory(prefix='native-history-shadow-') as folder:
            root = Path(folder)
            path = root / 'historical_verifier.py'
            path.write_text("RESULT='EVIL'\n")
            py_compile.compile(str(path), doraise=True)
            previous = path.stat()
            path.write_text("RESULT='GOOD'\n")
            os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
            vetted = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertTrue(list(root.rglob('*.pyc')))
            code = 'import historical_verifier; print(historical_verifier.RESULT)'
            old = subprocess.run([sys.executable, '-c', code], cwd=root, capture_output=True,
                                 text=True, env={'PYTHONPATH': str(root),
                                                 'PYTHONDONTWRITEBYTECODE': '1'})
            self.assertEqual(old.returncode, 0, old.stderr)
            self.assertEqual(old.stdout.strip(), 'EVIL')
            checked = upgrades._run_pinned_historical_python(root, code, {})
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(checked.stdout.strip(), 'GOOD')
            self.assertEqual(vetted, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_private_parent_environment_is_not_inherited(self):
        with tempfile.TemporaryDirectory(prefix='native-history-environment-') as folder:
            program = ('import json,os,sys;print(json.dumps({'
                       '"marker":os.getenv("AGI_ALPHA_SYNTHETIC_SECRET"),'
                       '"cache":sys.pycache_prefix,'
                       '"no_write":sys.dont_write_bytecode}))')
            with patch.dict(os.environ, {'AGI_ALPHA_SYNTHETIC_SECRET': 'not-for-child'}):
                completed = upgrades._run_pinned_historical_python(Path(folder), program, {})
            self.assertEqual(completed.returncode, 0, completed.stderr)
            outcome = json.loads(completed.stdout)
            self.assertIsNone(outcome['marker'])
            self.assertTrue(outcome['no_write'])
            self.assertTrue(outcome['cache'])
            self.assertFalse(Path(outcome['cache']).exists())

    def test_owner_authorization_uses_same_isolated_interpreter(self):
        with tempfile.TemporaryDirectory(prefix='native-history-owner-') as folder:
            root = Path(folder)
            fake_ticket = {'body': {'synthetic_only': True}, 'signature': 'not-a-key'}
            source = {'files': {'x.py': 'a' * 64}, 'sha256': 'b' * 64}
            result = SimpleNamespace(returncode=0, stdout=json.dumps(fake_ticket), stderr='')
            with patch.object(upgrades, 'source_inventory', return_value={'x.py': 'a' * 64}), \
                 patch('connected_enterprise.finance.source_identity', return_value=source), \
                 patch.object(upgrades, '_run_pinned_historical_python', return_value=result) as run:
                got = upgrades.authorize_upgrade(
                    historical_root=root, target_root=root, manifest={},
                    path=root / 'account.sqlite', opening=100, working=0,
                    contract='adaptive', expected_state_digest='synthetic',
                    ident='synthetic-upgrade', day=0)
            self.assertEqual(got, fake_ticket)
            run.assert_called_once()
            self.assertEqual(run.call_args.args[0], root)


if __name__ == '__main__':
    unittest.main()
