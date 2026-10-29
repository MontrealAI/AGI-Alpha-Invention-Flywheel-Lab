import hashlib
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from flywheel import foundation


class FoundationBoundary(unittest.TestCase):
    def test_actual_upstream_acceptance_binds_exact_output(self):
        artifact = {"result": "3/2"}
        identity = foundation.digest(artifact)
        self.assertEqual(identity, hashlib.sha256(foundation.canonical(artifact)).hexdigest())
        verdict = {"accepted": True, "task_id": "target", "artifact_hash": identity}
        self.assertEqual(foundation.strict_acceptance(verdict, "target", identity), verdict)
        for changed in ({**verdict, "accepted": 1}, {**verdict, "artifact_hash": "0" * 64}, {**verdict, "task_id": "other"}):
            with self.assertRaises(ValueError):
                foundation.strict_acceptance(changed, "target", identity)

    def test_collision_and_non_inert_output_are_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "evidence.json"
            foundation.write_new(path, {"quantity": "3/2"})
            original = path.read_bytes()
            with self.assertRaises(FileExistsError):
                foundation.write_new(path, {"quantity": "7"})
            self.assertEqual(path.read_bytes(), original)
            with self.assertRaises(ValueError):
                foundation.write_new(Path(folder) / "float.json", {"quantity": 1.5})

    def test_source_corruption_is_refused_before_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for relative in foundation.PINS:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(foundation.ROOT / relative, target)
            marker = root / "must-not-exist"
            source = root / "vendor/alpha_structure/contracts.py"
            source.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").touch()\n")
            with patch.object(foundation, "ROOT", root), self.assertRaises(ValueError):
                foundation.qualify()
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
