"""Prospective nonfinancial closure checks, not a repeat of modeled business evidence."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from connected_enterprise import runner
from mechanism_harness import reach_native


EXPECTED_NEW = {
    "campaign/omega-trial-once-20261107/PROTOCOL.md",
    "campaign/omega-trial-once-20261107/RELEASE_CLOSURE_PROTOCOL.md",
    "tests/test_omega_trial_once_20261107.py",
    "tests/test_omega_reach_release_closure_20261108.py",
    "scripts/omega_trial_once_matrix.py",
    ".github/workflows/omega-trial-once-20261107.yml",
    ".github/workflows/omega-reach-closure-20261108.yml",
}


class ProspectiveReachReleaseClosure(unittest.TestCase):
    def test_real_current_source_map_is_contained_with_research_components(self):
        self.assertTrue(EXPECTED_NEW <= set(runner.TRIAL_REACH_RELEASE_PATHS))
        included = set(runner.source_paths(runner.ROOT))
        self.assertTrue(EXPECTED_NEW <= included)
        self.assertTrue(set(reach_native.source_identity()) <= included)

    def test_missing_or_linked_member_fails_before_a_public_archive(self):
        source = set(runner.OMEGA_V4_RELEASE_PATHS) | set(runner.REACH_RELEASE_PATHS) | set(runner.TRIAL_REACH_RELEASE_PATHS) | set(runner.LEGACY_RELEASE_PATHS)
        with tempfile.TemporaryDirectory() as tmp, patch.object(runner, "inherited_paths", return_value=[]):
            root = Path(tmp)
            for name in source:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"synthetic research source fixture\n")
            self.assertTrue(source <= set(runner.source_paths(root)))
            # A complete pre-existing paid-reach distribution still works when
            # the opt-in trial is absent; no retroactive source requirement.
            for name in runner.TRIAL_REACH_RELEASE_PATHS:
                (root / name).unlink()
            self.assertTrue(set(runner.REACH_RELEASE_PATHS) <= set(runner.source_paths(root)))
            for name in runner.TRIAL_REACH_RELEASE_PATHS:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"synthetic research source fixture\\n")
            target = root / "campaign/omega-trial-once-20261107/PROTOCOL.md"
            content = target.read_bytes()
            target.unlink()
            with self.assertRaisesRegex(ValueError, "TRIAL_REACH_SOURCE_DEPENDENCY_MISSING"):
                runner.source_paths(root)
            target.write_bytes(content)
            outside = root / "separate-fixture.txt"
            outside.write_bytes(content)
            target.unlink()
            target.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "TRIAL_REACH_SOURCE_DEPENDENCY_MISSING"):
                runner.identity(root)


if __name__ == "__main__":
    unittest.main()
