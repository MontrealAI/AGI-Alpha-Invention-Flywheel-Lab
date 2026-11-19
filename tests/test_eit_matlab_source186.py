"""EIT186 offline adversarial integrity and claim-scope tests."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research.eit_physical_control183.control import Refusal
from research.eit_matlab_source186.review import (
    SAMPLE_BASENAME, SAMPLE_SHA, SAMPLE_BYTES, source_line_index, main,
)

def parse(raw):
    return source_line_index(raw, hashlib.sha256(raw).hexdigest(), len(raw))

class OriginalMatlabSourceTests(unittest.TestCase):
    def test_index_complete_and_lexical_only(self):
        raw = b"% comment\nV = voltages_matrix(:);\nJ = load('J.mat');\nalpha = 0.01;\n"
        actual = parse(raw)
        self.assertEqual(actual["physical_line_count"], 4)
        self.assertEqual(actual["code_bearing_line_count"], 3)
        self.assertEqual([r["line"] for r in actual["source_line_index"]], [2, 3, 4])
        self.assertFalse(actual["semantic_measurement_row_mapping_authenticated"])
        self.assertFalse(actual["property_reconstruction_performed"])
        self.assertEqual(actual["decision"], "HOLD_NO_DEPLOY_NO_BID")
        self.assertEqual(actual["source_line_index"][0]["line_sha256"],
                         hashlib.sha256(b"V = voltages_matrix(:);").hexdigest())
        self.assertIn("voltage", actual["source_line_index"][0]["lexical_indicators_only"])
        self.assertIn("jacobian", actual["source_line_index"][1]["lexical_indicators_only"])
        self.assertNotIn("V = voltages_matrix(:)", str(actual))

    def test_wrong_hash_refuses(self):
        with self.assertRaisesRegex(Refusal, "SAMPLE_SHA256_CHANGED"):
            source_line_index(b"x=1", "0"*64, 3)

    def test_changed_or_oversized_size_refuses(self):
        with self.assertRaisesRegex(Refusal, "SAMPLE_SIZE_CHANGED_OR_OVER_LIMIT"):
            source_line_index(b"x=1", hashlib.sha256(b"x=1").hexdigest(), 4)
        with self.assertRaisesRegex(Refusal, "SAMPLE_SIZE_CHANGED_OR_OVER_LIMIT"):
            parse(b"x"*4097)

    def test_invalid_ascii_empty_and_overlong_script_refuse(self):
        for raw in [b"\xff\n", b"% comment only\n", b"\n", b"x\n"*201]:
            with self.subTest(raw=raw[:8]), self.assertRaises(Refusal):
                parse(raw)

    def test_identifier_index_bounded(self):
        raw = b" ".join(("abc%d" % n).encode() for n in range(30))
        result = parse(raw)["source_line_index"][0]
        self.assertEqual(result["identifier_count"], 30)
        self.assertEqual(len(result["first_identifiers"]), 12)
        self.assertTrue(result["identifiers_truncated"])

    def test_original_ids_remain_pinned(self):
        self.assertEqual(SAMPLE_BASENAME, "Example_CylinderPhantom_LinearDifferenceImaging.m")
        self.assertEqual(SAMPLE_BYTES, 1910)
        self.assertEqual(SAMPLE_SHA, "48cac4535c4239b538a98b23e3088bc2bf3e4200291fb2946bf0156cb99209f9")

    def test_existing_receipt_refuses_before_download(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)/"receipt.json"
            target.write_text("unchanged")
            with patch("research.eit_matlab_source186.review.download_exact",
                       side_effect=AssertionError("no network allowed")):
                with self.assertRaisesRegex(Refusal, "OUTPUT_MUST_BE_CREATE_ONLY"):
                    main(["--out", str(target)])
            self.assertEqual(target.read_text(), "unchanged")

    def test_offline_test_cannot_download_source(self):
        with tempfile.TemporaryDirectory() as d:
            with patch("research.eit_matlab_source186.review.download_exact",
                       side_effect=RuntimeError("no network")):
                with self.assertRaisesRegex(RuntimeError, "no network"):
                    main(["--out", str(Path(d)/"new.json")])

if __name__ == "__main__":
    unittest.main()
