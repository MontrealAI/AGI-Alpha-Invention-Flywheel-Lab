"""HARNESS132: one unittest identity cannot support two success verdicts.

Tests-only review stacked on PR330. The preregistered pre-fix source incorrectly
returns True for both duplicate negative cases; preserve the source history.
"""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import reconcile_release_evidence as reconcile


class DuplicateUnittestVerdictTests(unittest.TestCase):
    def test_g1_conflicting_skip_and_pass_same_identity_rejected(self):
        skipped = reconcile.G1_OUT_OF_SCOPE_SKIP
        identical_ok = skipped.split(" ... ", 1)[0] + " ... ok"
        other_ok = "test_other (test_bridge.OtherTests.test_other) ... ok"
        log = "\n".join((other_ok, skipped, identical_ok))
        self.assertFalse(reconcile.module_passed(log, "test_bridge", "G1"))

    def test_duplicate_ordinary_success_rejected_in_all_scopes(self):
        ok = "test_transport (test_bridge.TransportTests.test_transport) ... ok"
        self.assertFalse(reconcile.module_passed(ok + "\n" + ok, "test_bridge", "G1"))
        self.assertFalse(reconcile.module_passed(ok + "\n" + ok, "test_bridge"))

    def test_one_documented_skip_one_distinct_pass_remains_scoped(self):
        ok = "test_transport (test_bridge.TransportTests.test_transport) ... ok"
        log = ok + "\n" + reconcile.G1_OUT_OF_SCOPE_SKIP
        self.assertTrue(reconcile.module_passed(log, "test_bridge", "G1"))
        self.assertFalse(reconcile.module_passed(log, "test_bridge", "G4"))
        self.assertFalse(reconcile.module_passed(log, "test_bridge"))


if __name__ == "__main__":
    unittest.main()
