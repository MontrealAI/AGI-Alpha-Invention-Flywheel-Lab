import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flywheel.legacy import materialize, PINS

ROOT = Path(__file__).resolve().parents[1]


class LegacyTests(unittest.TestCase):
    def test_exact_frozen_source_set_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "snapshot"
            receipt = materialize(ROOT, output)
            actual = {str(path.relative_to(output)) for path in output.rglob("*.py")}
            self.assertEqual(actual, set(receipt["python_source_set"]))
            self.assertNotIn("flywheel/commercial.py", actual)
            self.assertEqual(hashlib.sha256((output / "reproduce.py").read_bytes()).hexdigest(), PINS["reproduce.py"])
            with self.assertRaises(FileExistsError):
                materialize(ROOT, output)

    def test_manifest_corruption_refused_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "snapshot"
            with patch("flywheel.legacy.PINS", {**PINS, "campaign/cycle-001/CLOSURE.json": "0" * 64}):
                with self.assertRaisesRegex(ValueError, "LEGACY_IDENTITY_MISMATCH"):
                    materialize(ROOT, output)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
