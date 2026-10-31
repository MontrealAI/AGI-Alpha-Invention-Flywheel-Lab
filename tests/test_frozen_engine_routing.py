import builtins
import hashlib
from pathlib import Path
import tempfile
import shutil
import unittest
from unittest.mock import patch

from commercial.native_engine import engine, PROSPECTIVE_PINS
from experiments.commerce006 import engine as frozen_engine, PINS
from adaptive_enterprise.account import audit_account

ROOT = Path(__file__).resolve().parents[1]


class FrozenEngineRoutingTests(unittest.TestCase):
    def test_historical_paths_are_original_bytes(self):
        expected = {
            'experiments/commerce006.py': '2fc529131885c75752dab8dbd77d85b5a36d4c0b43cb5e7e53286c997cc0a52f',
            'vendor/alpha_claim/protected_exchange.py': '7b72c911d99a9aa12dc1f412d3b66f69ba58f3d4f2f50291310a7fd849df5272',
        }
        for name, digest in expected.items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(), digest)

    def test_default_is_frozen_and_prospective_is_explicit(self):
        self.assertIs(engine(), frozen_engine())
        self.assertIs(engine(version='legacy-permanent-v1'), frozen_engine())
        prospective = engine(version='prospective-v1')
        self.assertNotEqual(prospective.__module__, frozen_engine().__module__)
        self.assertTrue(hasattr(prospective, 'register_terms'))
        self.assertFalse(hasattr(frozen_engine(), 'register_terms'))
        with self.assertRaisesRegex(ValueError, 'SUPPORTED_EXPLICIT'):
            engine(version='future-unregistered')

    def test_prospective_tampering_fails_without_rebinding_historical_pins(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in {*PINS, *PROSPECTIVE_PINS}:
                path=root/name; path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/name,path)
            path=root/'vendor/alpha_claim/protected_exchange_prospective_v1.py'
            path.write_bytes(path.read_bytes()+b'\n# tamper\n')
            self.assertIs(engine(root), frozen_engine())
            with self.assertRaisesRegex(ValueError, 'PINNED_EXCHANGE_SOURCE_MISMATCH'):
                engine(root, version='prospective-v1')

    def test_current_ledger_explicit_prospective_call_uses_versioned_engine(self):
        from commercial.ledger import TapeExchange
        with tempfile.TemporaryDirectory() as temporary, patch('commercial.ledger.load_jobs',return_value={}), patch('commercial.ledger.engine',wraps=engine) as selected:
            tape=TapeExchange(Path(temporary)/'test.json',root=ROOT,
                              manifest={'native_engine':'prospective-v1'},opening=100,working=0,
                              contract='isolated-routing-test',durable=False)
            try:
                selected.assert_called_once_with(version='prospective-v1')
                self.assertTrue(isinstance(tape.ex,engine(version='prospective-v1')))
            finally:
                tape.close()

    def test_adaptive_only_audit_does_not_import_connected(self):
        self._audit_without_connected([])

    def test_transition_audit_requires_connected_verifier(self):
        with self.assertRaisesRegex(ModuleNotFoundError, 'connected verifier unavailable'):
            self._audit_without_connected([{'op':'source_transition'}])

    def test_pending_transition_requires_connected_verifier(self):
        with self.assertRaisesRegex(ModuleNotFoundError, 'connected verifier unavailable'):
            self._audit_without_connected([], pending_source_transition={})

    def _audit_without_connected(self, actions, **kwargs):
        original = builtins.__import__
        def guarded(name, *args, **kw):
            if name.startswith('connected_enterprise'):
                raise ModuleNotFoundError('connected verifier unavailable')
            return original(name, *args, **kw)
        record={'schema':'agi-alpha/adaptive012-owned-account/v1', 'scope':'SIMULATED',
                'ledger':{'actions':actions}, 'action_proofs':{}}
        with patch('adaptive_enterprise.account._audit_native_and_jobs',return_value=({},{})), patch('builtins.__import__',side_effect=guarded):
            return audit_account(record,root=ROOT,manifest={'schema':'agi-alpha/adaptive012-services/v1'},**kwargs)


if __name__ == '__main__': unittest.main()
