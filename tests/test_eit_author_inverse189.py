"""Offline EIT189 source gate controls. Never access network in tests."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.eit_physical_control183.control import Refusal
from research.eit_author_inverse189.inspect import (
    source_expression_witness, write_fresh, main, MAX_SCRIPT_LINES,
)


class OriginalAuthors189SourceTests(unittest.TestCase):
    def test_wrong_matlab_bytes_rejected_before_parsing_or_exec(self):
        with self.assertRaisesRegex(Refusal, "SAMPLE_SIZE_CHANGED_OR_OVER_LIMIT"):
            source_expression_witness(b"exec('not allowed')")

    def test_correct_size_but_wrong_sha_is_rejected(self):
        with self.assertRaisesRegex(Refusal, "SAMPLE_SHA256_CHANGED"):
            source_expression_witness(b"x" * 1910)

    def test_source_size_is_frozen_and_bounded(self):
        self.assertLess(MAX_SCRIPT_LINES, 1000)

    def test_create_only_reproducible_json_keeps_old_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "evidence.json"
            source = {"schema": "test", "decision": "HOLD_NO_DEPLOY_NO_BID"}
            write_fresh(p, source)
            frozen = p.read_bytes()
            with self.assertRaisesRegex(Refusal, "EIT189_OUTPUT_MUST_BE_FRESH"):
                write_fresh(p, {"schema": "changed"})
            self.assertEqual(p.read_bytes(), frozen)

    def test_symlink_output_is_rejected_and_target_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "safe.json"
            p.write_bytes(b"persistent untouched")
            link = Path(d) / "forbidden.json"
            link.symlink_to(p)
            with self.assertRaisesRegex(Refusal, "EIT189_OUTPUT_MUST_BE_FRESH"):
                write_fresh(link, {"schema": "test"})
            self.assertEqual(p.read_bytes(), b"persistent untouched")

    def test_existing_output_never_downloads_original_source(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "existing.json"
            p.write_text("previous receipt", encoding="utf-8")
            with patch("research.eit_author_inverse189.inspect.download_exact",
                       side_effect=AssertionError("must not download")):
                with self.assertRaisesRegex(Refusal, "EIT189_OUTPUT_MUST_BE_FRESH"):
                    main(["--out", str(p)])
            self.assertEqual(p.read_text(), "previous receipt")

    def test_missing_source_fails_without_creating_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "fresh.json"
            with patch("research.eit_author_inverse189.inspect.download_exact",
                       side_effect=Refusal("EIT189_EXPECTED_SOURCE_FAILURE")):
                with self.assertRaisesRegex(Refusal, "EIT189_EXPECTED_SOURCE_FAILURE"):
                    main(["--out", str(p)])
            self.assertFalse(p.exists())


if __name__ == "__main__":
    unittest.main()
