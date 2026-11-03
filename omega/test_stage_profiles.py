import copy
from pathlib import Path
import tempfile
import unittest

from omega.native_lifecycle.stage import BASE_PINS, NATIVE_BASE_PROFILES, native_basis, stage


class NativeConstructionProfileTests(unittest.TestCase):
    def test_original_and_current_complete_profiles_are_distinct(self):
        original = '38846ad9b72ef04c10b2b97b3dbff52d1efc3790'
        current = '92f4351c99e6d86bf699117d1d9cd8f1ffcb5fbb'
        self.assertEqual(BASE_PINS, NATIVE_BASE_PROFILES[original])
        for commit, hashes in NATIVE_BASE_PROFILES.items():
            self.assertEqual(native_basis(copy.deepcopy(hashes)), commit)
        self.assertNotEqual(NATIVE_BASE_PROFILES[original], NATIVE_BASE_PROFILES[current])

    def test_mixed_unknown_missing_and_extra_native_identities_reject(self):
        original, current = [copy.deepcopy(p) for p in NATIVE_BASE_PROFILES.values()]
        mixed = dict(original, **{'commercial/ledger.py': current['commercial/ledger.py']})
        altered = dict(current, **{'commercial/ledger.py': '0' * 64})
        missing = {'commercial/ledger.py': current['commercial/ledger.py']}
        extra = dict(current, **{'unregistered.py': '0' * 64})
        for hashes in (mixed, altered, missing, extra):
            with self.subTest(hashes=hashes), self.assertRaisesRegex(ValueError, 'EXACT_PR191_NATIVE_SOURCE_REQUIRED'):
                native_basis(hashes)

    def test_unknown_native_bytes_reject_before_creating_staging_target(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)/'base'
            target = Path(temporary)/'staged'
            for name in BASE_PINS:
                path = base/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((root/name).read_bytes())
            ledger = base/'commercial/ledger.py'
            ledger.write_bytes(ledger.read_bytes()+b'\n# unregistered construction source\n')
            with self.assertRaisesRegex(ValueError, 'EXACT_PR191_NATIVE_SOURCE_REQUIRED'):
                stage(base,target)
            self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
