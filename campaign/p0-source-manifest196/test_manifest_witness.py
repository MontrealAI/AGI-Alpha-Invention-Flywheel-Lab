import ast
import unittest
from unittest.mock import patch

import manifest_witness as w


class SourceManifest196Tests(unittest.TestCase):
    def test_pinned_source_and_frozen_synthetic_result(self):
        receipt = w.report()
        self.assertTrue(receipt["all_frozen_negative_checks_met"])
        self.assertEqual(receipt["owner_call_witness"]["historical_target_no_manifest_calls"], 2)
        self.assertFalse(receipt["native_account_opened"])
        self.assertFalse(receipt["observed_commerce"])
        self.assertIsNone(receipt["actual_profit_usd"])

    def test_simulated_unselected_file_cannot_change_binding(self):
        choices = ("src/core.py", "src/selected.py")
        base = w.fingerprint(choices)
        self.assertNotEqual(w.fingerprint(choices, "src/selected.py"), base)
        with self.assertRaisesRegex(ValueError, "SYNTHETIC_CHANGE_PATH_NOT_SELECTED"):
            w.fingerprint(choices, "src/not-selected.py")

    def test_source_selector_rejects_missing_manifest_parameter(self):
        source = b"""
SOURCE_PATHS = ("common.py",)
PRODUCTION_SOURCE_PATHS = ("production.py",)
INVENTORY_SOURCE_PATHS = ("inventory.py",)
def source_paths_for_manifest(manifest=None): return SOURCE_PATHS
def source_identity(root):
    for name in source_paths_for_manifest(): pass
"""
        with self.assertRaisesRegex(ValueError, "TARGET_SOURCE_IDENTITY_SELECTOR_CHANGED"):
            w.names_from_target(source)

    def test_changed_blob_cannot_be_interpreted_as_original(self):
        original = w.PINNED
        akey = (w.TARGET, "connected_enterprise/finance.py")
        modified = dict(original)
        modified[akey] = "0" * 40
        with patch.object(w, "PINNED", modified):
            with self.assertRaisesRegex(ValueError, "PINNED_BLOB_CHANGED"):
                w.git_bytes(*akey)

    def test_owner_upgrade_manifest_argument_is_not_silently_accepted(self):
        good = b"""
def source_identity(root): return {}
"""
        with_manifest = b"""
def authorize_upgrade():
    target = source_identity(target_root, manifest)
"""
        receipt = w.owner_target_call(with_manifest, good)
        self.assertEqual(receipt["historical_target_no_manifest_calls"], 0)


if __name__ == "__main__":
    unittest.main()
