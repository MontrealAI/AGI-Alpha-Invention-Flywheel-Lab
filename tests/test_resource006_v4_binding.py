"""Keep the repaired reproduction distinct from immutable historical inputs."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import run_cycle007_repaired as driver

ROOT = Path(__file__).resolve().parents[1]

class ResourceRepairBindingTests(unittest.TestCase):
    def test_original_wrapper_and_freeze_preserved(self):
        historical = ROOT / 'campaign/cycle-007/REPRODUCTION_FREEZE.json'
        successor = json.loads((historical.with_name('REPAIRED_REPRODUCTION_FREEZE.json')).read_text())
        original = json.loads(historical.read_text())
        self.assertEqual(driver.sha(historical), successor['historical_freeze_sha256'])
        for name, expected in original['files'].items():
            self.assertEqual(successor['files'][name], expected)
        self.assertEqual(driver.sha(ROOT / 'experiments/resource006_v3.py'), '8a10193e2cc29ca277560c7b2153d616e8cb46e64fbc7f54c102518dc2b71cbd')
        self.assertEqual(driver.sha(ROOT / 'experiments/resource006_v4.py'), successor['files']['experiments/resource006_v4.py'])
        self.assertEqual(driver.sha(ROOT / 'run_cycle007_repaired.py'), successor['files']['run_cycle007_repaired.py'])

    def test_repaired_driver_rejects_changed_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source.py'; source.write_text('original')
            freeze = root / 'campaign/cycle-007/REPAIRED_REPRODUCTION_FREEZE.json'
            freeze.parent.mkdir(parents=True)
            freeze.write_text(json.dumps({'files': {'source.py': driver.sha(source)}}))
            expected = driver.sha(freeze)
            with patch.object(driver, 'ROOT', root):
                driver.sources(expected)
                source.write_text('changed')
                with self.assertRaisesRegex(ValueError, 'FROZEN_SOURCE_MISMATCH'):
                    driver.sources(expected)
                with self.assertRaisesRegex(ValueError, 'EXTERNAL_FREEZE_IDENTITY_MISMATCH'):
                    driver.sources('0' * 64)
