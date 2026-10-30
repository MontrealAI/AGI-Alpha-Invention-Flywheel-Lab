import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from flywheel.legacy import materialize, _read

ROOT = Path(__file__).resolve().parents[1]


class CurrentPolicyBoundaryTests(unittest.TestCase):
    def test_current_policy_and_historical_input_are_distinct(self):
        edition = json.loads((ROOT/'campaign/cycle-001/EDITION_SHA256.json').read_text())
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'legacy'
            receipt = materialize(ROOT, target)
            for name in ('AGENTS.md','CAMPAIGN.md','CHARTER.md','FIRST_CAMPAIGN.md','README.md'):
                with self.subTest(name=name):
                    original = (ROOT/'historical/cycle-001'/f'{name}.txt').read_bytes()
                    self.assertEqual(hashlib.sha256(original).hexdigest(), edition[name])
                    self.assertEqual((target/name).read_bytes(), original)
                    if (ROOT/name).read_bytes() != original:
                        self.assertIn('bundled-historical-snapshot', receipt['files'][name]['origin'])

    def test_corrupt_missing_or_symlink_historical_policy_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'root'
            root.mkdir()
            shutil.copy2(ROOT/'AGENTS.md', root/'AGENTS.md')
            expected = json.loads((ROOT/'campaign/cycle-001/EDITION_SHA256.json').read_text())['AGENTS.md']
            historical = root/'historical/cycle-001/AGENTS.md.txt'
            historical.parent.mkdir(parents=True)
            for mode in ('missing', 'corrupt', 'symlink'):
                if historical.exists() or historical.is_symlink(): historical.unlink()
                if mode == 'corrupt': historical.write_text('altered historical policy')
                if mode == 'symlink': historical.symlink_to(ROOT/'historical/cycle-001/AGENTS.md.txt')
                with self.subTest(mode=mode), self.assertRaises(ValueError):
                    _read(root, 'AGENTS.md', expected)
                self.assertFalse((Path(folder)/mode).exists())
