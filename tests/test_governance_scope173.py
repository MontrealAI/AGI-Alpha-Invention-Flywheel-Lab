"""T173 frozen successor-inventory authority negative case; synthetic-only."""
from __future__ import annotations

import copy
import unittest

from products.governance_impact140 import engine as native
from research import governance_scope172 as scope
from tests.test_governance_scope172 import sample


class SuccessorInventoryAnchor173(unittest.TestCase):
    def test_t173_changed_successor_inventory_cannot_be_replaced_by_stale_prior_list(self):
        observed = sample()
        observed["after_systems"][0]["tags"] = ["new-target-tag"]
        target_digest = native.sha256(observed["after_systems"])

        # Demonstrate the precise old missing-anchor exposure, while allowing
        # the corrected contract to refuse a missing fifth source anchor.
        legacy = copy.deepcopy(observed)
        legacy["after_systems"] = copy.deepcopy(legacy["before_systems"])
        self.assertNotEqual(native.sha256(legacy["after_systems"]), target_digest)
        try:
            old_result = scope.propose(legacy)
        except ValueError as exc:
            self.assertIn("FIVE_EXTERNAL_SOURCE_ANCHORS_REQUIRED", str(exc))
        else:
            self.assertEqual(old_result["summary"]["provisional_count"], 2,
                             "ORIGINAL_MISSING_TARGET_ANCHOR_EXPOSURE_NOT_REPRODUCED")

        # This independent, externally declared target digest must bind the
        # successor inventory for a later proposal. It is NOT a signature.
        observed["anchors"]["systems_after_sha256"] = target_digest
        actual = scope.propose(observed)
        self.assertEqual(actual["summary"]["provisional_count"], 0)
        self.assertEqual(actual["summary"]["review_required_count"], 2)
        self.assertFalse(actual["same_registered_system_inventory"])

        attacker = copy.deepcopy(observed)
        attacker["after_systems"] = copy.deepcopy(attacker["before_systems"])
        with self.assertRaisesRegex(ValueError,
                                    "EXTERNAL_SOURCE_ANCHOR_MISMATCH_systems_after_sha256"):
            scope.propose(attacker)


if __name__ == "__main__":
    unittest.main()
