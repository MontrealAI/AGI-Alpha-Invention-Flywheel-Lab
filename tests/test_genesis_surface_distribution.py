"""Distribution correctness, privacy allowlist and independent extraction tests."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

from research.genesis_surface.distribution import package, verify, source_files, ROOT


class DistributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name)/'dist'
        cls.receipt = package(cls.out)
        cls.stage = cls.out/'ALPHA_GENESIS_SURFACE'

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def copied(self, root):
        p=Path(root)/'package';shutil.copytree(self.stage,p);return p

    def test_clean_extraction_verified(self):
        self.assertTrue(self.receipt['clean_extracted_verification']['accepted'])
        self.assertFalse(self.receipt['actual_release_download'])
        self.assertTrue(verify(self.stage)['accepted'])

    def test_zip_integrity(self):
        with zipfile.ZipFile(self.out/'ALPHA_GENESIS_SURFACE.zip') as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(len(z.namelist()),len(set(z.namelist())))
            self.assertIn('ALPHA_GENESIS_SURFACE/START_HERE.html',z.namelist())
            self.assertTrue(all(n.startswith('ALPHA_GENESIS_SURFACE/') and '..' not in Path(n).parts for n in z.namelist()))

    def test_allowlist_contains_no_accounts(self):
        for name in source_files():
            self.assertTrue(name.startswith(('research/genesis_surface/','tests/test_genesis_surface','campaign/genesis-surface/')))
            self.assertFalse(name.endswith(('.sqlite','.key','.pem')))

    def test_changed_public_file_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=self.copied(t);(p/'README.md').write_text('changed')
            with self.assertRaises(ValueError):verify(p)

    def test_missing_file_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=self.copied(t);(p/'demo/design.json').unlink()
            with self.assertRaises(ValueError):verify(p)

    def test_extra_file_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=self.copied(t);(p/'extra.txt').write_text('not admitted')
            with self.assertRaises(ValueError):verify(p)

    def test_extra_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=self.copied(t);(p/'demo/PACKAGE.json').write_text('{}')
            with self.assertRaises(ValueError):verify(p)

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=self.copied(t);(p/'alias').symlink_to(p/'README.md')
            with self.assertRaises(ValueError):verify(p)

    def test_scope_promotion_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=self.copied(t);m=json.loads((p/'PACKAGE.json').read_text());m['scope']='PHYSICALLY_QUALIFIED'
            (p/'PACKAGE.json').write_text(json.dumps(m))
            with self.assertRaises(ValueError):verify(p)

    def test_no_overwrite(self):
        with self.assertRaises(FileExistsError):package(self.out)

    def test_decision_and_hypothesis_are_distinct(self):
        r=json.loads((self.stage/'CALIBRATION.json').read_text())
        self.assertFalse(r['robust_check']['accepted'])
        self.assertTrue(r['hypothetical_calibration_comparison']['check']['accepted'])
        self.assertEqual(r['actual_physical_measurements'],0)
        self.assertIn('not qualified',(self.stage/'START_HERE.html').read_text())


if __name__ == '__main__': unittest.main()
