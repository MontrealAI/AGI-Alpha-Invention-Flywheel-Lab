"""Frozen adversarial UTF-8 JSON ingress tests for FRONTIER Ω.

These tests do not attest a buyer, benchmark, or signing authority.
They reject ambiguity before any read-only ignition/economic classification.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from frontier_omega.__main__ import InventoryError, read_json


class FrontierOmegaJSONEvidenceIntegrityTests(unittest.TestCase):
    def parse(self, raw):
        with TemporaryDirectory() as temp:
            source = Path(temp) / "reported-evidence.json"
            source.write_text(raw, encoding="utf-8")
            return read_json(source)

    def test_duplicate_outer_synthetic_cannot_erase_rehearsal(self):
        with self.assertRaises(InventoryError):
            self.parse('{"synthetic": true, "synthetic": false}')

    def test_duplicate_nested_synthetic_cannot_erase_rehearsal(self):
        with self.assertRaises(InventoryError):
            self.parse('{"matched_test":{"synthetic":true,"synthetic":false}}')

    def test_nonstandard_nan_rejected_before_classification(self):
        with self.assertRaises(InventoryError):
            self.parse('{"p95_turnaround_hours":NaN}')

    def test_nonstandard_infinity_rejected_before_classification(self):
        for marker in ("Infinity", "-Infinity"):
            with self.subTest(marker=marker), self.assertRaises(InventoryError):
                self.parse('{"costs_usd":{"model_compute":' + marker + '}}')

    def test_valid_unambiguous_json_unaffected(self):
        self.assertEqual(
            self.parse('{"synthetic":true,"matched_test":{"synthetic":true}}'),
            {"synthetic": True, "matched_test": {"synthetic": True}},
        )


if __name__ == "__main__":
    unittest.main()
