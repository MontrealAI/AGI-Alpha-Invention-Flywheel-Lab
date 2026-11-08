"""Prospective nonfinancial closure checks, not a repeat of modeled business evidence."""
from pathlib import Path
from copy import deepcopy
from scripts.qualify_omega_release import reach_source, TRIAL_NATIVE_SOURCE_PATHS
from tests.test_connected_reach_release import PaidReachRelease
import tempfile
import unittest
from unittest.mock import patch

from connected_enterprise import runner
from mechanism_harness import reach_native


EXPECTED_NEW = {
    "campaign/omega-trial-once-20261107/PROTOCOL.md",
    "campaign/omega-trial-once-20261107/RELEASE_CLOSURE_PROTOCOL.md",
    "campaign/omega-trial-once-20261107/RELEASE_CLOSURE_AMENDMENT_A.md",
    "campaign/omega-trial-once-20261107/RELEASE_CLOSURE_AMENDMENT_B.md",
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

    def test_independent_sealed_manifest_strict_two_source_trial_variant(self):
        historical = PaidReachRelease()
        historical.setUp()  # existing synthetic historical native/release fixture
        old = deepcopy(historical.manifest)
        self.assertIsNotNone(reach_source(old))
        self.assertFalse(TRIAL_NATIVE_SOURCE_PATHS.intersection(old["omega_reach_native_source"]))
        trial = deepcopy(old)
        new_hashes = {}
        for i, name in enumerate(sorted(runner.TRIAL_REACH_RELEASE_PATHS)):
            new_hashes[name] = format(i + 1, "064x")
        trial["files"].update(new_hashes)
        for name in TRIAL_NATIVE_SOURCE_PATHS:
            trial["omega_reach_native_source"][name] = trial["files"][name]
        self.assertEqual(set(reach_source(trial)), set(old["omega_reach_native_source"]) | TRIAL_NATIVE_SOURCE_PATHS)
        # Publisher must not omit even a non-native member of its true closure.
        for path in sorted(runner.TRIAL_REACH_RELEASE_PATHS):
            changed = deepcopy(trial)
            del changed["files"][path]
            with self.subTest(missing=path), self.assertRaisesRegex(ValueError, "PAID_REACH_EXACT_NATIVE_SOURCE_CLOSURE_REQUIRED"):
                reach_source(changed)
        # A native identifier cannot silently drop a trial source or falsify its hash.
        for name in sorted(TRIAL_NATIVE_SOURCE_PATHS):
            omitted = deepcopy(trial)
            del omitted["omega_reach_native_source"][name]
            with self.subTest(native_missing=name), self.assertRaises(ValueError):
                reach_source(omitted)
            tampered = deepcopy(trial)
            tampered["omega_reach_native_source"][name] = "f" * 64
            with self.subTest(native_wrong_hash=name), self.assertRaises(ValueError):
                reach_source(tampered)
        invented = deepcopy(trial)
        invented["omega_reach_native_source"]["unregistered.py"] = "e" * 64
        with self.assertRaises(ValueError):
            reach_source(invented)
        downgrade = deepcopy(trial)
        for name in runner.TRIAL_REACH_RELEASE_PATHS:
            del downgrade["files"][name]
        with self.assertRaises(ValueError):
            reach_source(downgrade)

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
            # A newer native source cannot lie about being an older complete
            # distribution simply by omitting every trial-only file.
            native = root / "mechanism_harness/reach_native.py"
            native.write_bytes(b"source_identity advertises campaign/omega-trial-once-20261107/PROTOCOL.md\\n")
            with self.assertRaisesRegex(ValueError, "TRIAL_REACH_SOURCE_DEPENDENCY_MISSING"):
                runner.source_paths(root)
            native.write_bytes(b"synthetic historical native without trial\\n")
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
