from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EDITION = Path('docs/transformational063')
CAMPAIGN = Path('campaign/transformational-063')
SPEC = importlib.util.spec_from_file_location('historical_publication063', ROOT / EDITION / 'verify_publication.py')
PUBLICATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PUBLICATION)


class HistoricalPublication063Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='historical-publication063-')
        self.root = Path(self.temporary.name)
        self.metadata = json.loads((ROOT / EDITION / 'publication.json').read_text())
        for name in set(self.metadata['sha256']) | {str(EDITION / 'publication.json')}:
            self.copy(ROOT / name, self.root / name)

    def tearDown(self):
        self.temporary.cleanup()

    @staticmethod
    def copy(source, target):
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    def install_matching_current_source(self):
        native = self.root / CAMPAIGN / 'native'
        source = json.loads((native / 'SOURCE.json').read_text())
        for name in source['files']:
            self.copy(native / 'source' / name, self.root / name)
        provenance = json.loads((self.root / CAMPAIGN / 'regression-source' / 'PROVENANCE.json').read_text())
        for name, record in provenance['files'].items():
            self.copy(self.root / record['snapshot_path'], self.root / name)

    def test_retained_edition_verifies_without_git_or_current_runtime(self):
        self.assertFalse((self.root / '.git').exists())
        self.assertFalse((self.root / 'connected_enterprise/finance.py').exists())
        self.assertTrue(PUBLICATION.verify(self.root)['accepted'])

    def test_explicit_current_source_guard_accepts_exact_old_source(self):
        self.install_matching_current_source()
        self.assertTrue(PUBLICATION.verify(self.root, require_current_source=True)['accepted'])

    def test_later_runtime_changes_do_not_rewrite_history_but_fail_strict_mode(self):
        self.install_matching_current_source()
        path = self.root / 'connected_enterprise/finance.py'
        path.write_bytes(path.read_bytes() + b'\n')
        self.assertTrue(PUBLICATION.verify(self.root)['accepted'])
        with self.assertRaisesRegex(ValueError, 'CURRENT_NATIVE_SOURCE_CHANGED:connected_enterprise/finance.py'):
            PUBLICATION.verify(self.root, require_current_source=True)

    def test_changed_retained_native_source_is_rejected(self):
        path = self.root / CAMPAIGN / 'native/source/connected_enterprise/finance.py'
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'PUBLICATION_BYTES_CHANGED'):
            PUBLICATION.verify(self.root)

    def test_rehashed_changed_regression_snapshot_still_fails_original_receipt(self):
        name = str(CAMPAIGN / 'regression-source/tests/test_connected_transformational063.py')
        path = self.root / name
        path.write_bytes(path.read_bytes() + b'\n')
        self.metadata['sha256'][name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.root / EDITION / 'publication.json').write_text(json.dumps(self.metadata))
        with self.assertRaisesRegex(ValueError, 'HISTORICAL_REGRESSION_SOURCE_CHANGED'):
            PUBLICATION.verify(self.root)


if __name__ == '__main__':
    unittest.main()
