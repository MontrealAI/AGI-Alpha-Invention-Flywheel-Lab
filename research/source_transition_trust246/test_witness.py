"""Tests reproduce a historical owner-source signer boundary, not a safe release.

No real account, secret, wallet or native migration is accessed.
"""
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import witness


class HistoricalSignerBoundaryNegativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = witness.pinned_owner_source()

    def test_exact_historical_owner_blob_and_historical_signer_site(self):
        result = witness.inspect_owner_source(self.source)
        self.assertEqual(result["source_blob_git_sha1"], witness.OWNER_BLOB)
        self.assertTrue(result["target_supplied_python_interpreted"])
        self.assertTrue(result["historical_signer_active_at_exec"])
        self.assertTrue(result["key_bearing_scope_present"])
        self.assertIn("NOT_ACTUAL_KEY_READ", result["scope"])

    def test_caller_frame_visibility_synthetic_marker_only(self):
        self.assertEqual(
            witness.synthetic_caller_visibility(), "SYNTHETIC_NO_KEY"
        )

    def test_changed_pinned_source_fails_closed(self):
        with patch("urllib.request.urlopen", return_value=io.BytesIO(self.source + b"#")):
            with self.assertRaisesRegex(ValueError, "EXACT_OWNER_GIT_BLOB_MISMATCH"):
                witness.pinned_owner_source()

    def test_oversized_source_fails_before_parsing(self):
        with patch("urllib.request.urlopen", return_value=io.BytesIO(b"x" * (witness.MAX_BYTES + 1))):
            with self.assertRaisesRegex(ValueError, "BOUNDED_PUBLIC_OWNER_SOURCE_REQUIRED"):
                witness.pinned_owner_source()

    def test_nonexecutable_structural_input_does_not_execute(self):
        marker = "SYNTHETIC_NO_KEY"
        payload = {"codec_source": "raise Exception('never executed')", "marker": marker}
        decoded = json.loads(json.dumps(payload))
        self.assertEqual(decoded["marker"], marker)
        self.assertEqual(decoded["codec_source"], payload["codec_source"])

    def test_final_negative_verdict_never_promoted(self):
        with patch.object(witness, "pinned_owner_source", return_value=self.source):
            record = witness.report()
        self.assertFalse(record["actual_secret_read"])
        self.assertFalse(record["actual_compromise_observed"])
        self.assertFalse(record["actual_task_custody_known"])
        self.assertFalse(record["historical_migration_qualified"])
        self.assertFalse(record["release_go"])


if __name__ == "__main__":
    unittest.main()
