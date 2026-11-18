"""Frozen augmented competent conventional route: exposed original packets only."""
from __future__ import annotations

import gzip
import importlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent.parent
SOURCE = HERE / "products/frontier-omega-ignition/evolution_trials"
sys.path.insert(0, str(SOURCE))
augmented = importlib.import_module("incumbent_augmented_probe")


class AugmentedIncumbentControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = augmented.compare()

    def test_real_original_october_answers_recovered_by_ordinary_augmented_route(self):
        record = self.result
        self.assertEqual(record["candidate_count"], 6)
        self.assertEqual(record["original_packet_count"], 6)
        self.assertGreater(record["original_packet_bytes_uncompressed"], 0)
        self.assertTrue(record["matched_original_report"])
        self.assertEqual(record["witness_ids"], {
            "g": "3587249065815015015",
            "r": "3587389715815015003",
        })
        self.assertEqual(record["scientific_output_verdict"],
                         "EXPOSED_CASE_FUNCTIONAL_TIE_NO_INCREMENTAL_ADVANTAGE_ESTABLISHED")
        self.assertEqual(record["economic_verdict"], "NO_DEPLOY")

    def test_original_source_digest_pins_are_exactly_the_original_packet_manifest(self):
        pinned = json.loads(augmented.REFERENCE_PATH.read_bytes())["source_sha256"]["packets"]
        self.assertEqual(self.result["original_packet_sha256"], pinned)
        self.assertEqual(len(pinned), 6)
        self.assertTrue(self.result["original_byte_tamper_rejected"])

    def test_synthetic_reference_counterexample_distinguishes_stock_from_augmented(self):
        self.assertTrue(self.result["synthetic_off_reference_undetectable_stock_only"])
        self.assertTrue(self.result["synthetic_off_reference_rejected_augmented"])
        self.assertEqual(self.result["new_accepted_sky_observations"], 0)

    def test_source_packet_byte_change_refused_before_decoding(self):
        body = gzip.decompress(augmented._source_paths()[0].read_bytes())
        cid = str(augmented.conventional.packet_candidate(body, augmented.stock.TARGET)["candid"])
        expected = json.loads(augmented.REFERENCE_PATH.read_bytes())["source_sha256"]["packets"][cid]
        bad = bytearray(body)
        bad[-1] ^= 1
        with self.assertRaisesRegex(ValueError, "PINNED_ORIGINAL_PACKET_DIGEST_MISMATCH"):
            augmented.checked_packet(bytes(bad), cid, expected)

    def test_missing_packet_refuses_instead_of_sampling_fewer(self):
        with patch.object(augmented, "_source_paths",
                          return_value=augmented._source_paths()[:-1]):
            with self.assertRaisesRegex(ValueError, "INCOMPLETE_OR_CHANGED_PINNED_COHORT"):
                augmented.compare()

    def test_changed_installed_version_refuses_before_scientific_claim(self):
        with patch.object(augmented.stock.nucleuswatch, "__version__", "1.0.0"):
            with self.assertRaisesRegex(ValueError, "UPSTREAM_VERSION_NOT_PINNED"):
                augmented.compare()

    def test_no_payments_or_labor_or_demand_are_invented(self):
        self.assertEqual(self.result["new_collected_revenue_usd"], 0)
        self.assertEqual(self.result["new_paying_customers"], 0)
        self.assertIsNone(self.result["operator_hours"])
        self.assertIsNone(self.result["human_comparator_complete_cost_usd"])
        self.assertIsNone(self.result["model_and_host_billing_usd"])
        self.assertEqual(self.result["business_demand"], "UNMEASURED")

    def test_create_only_receipt_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "receipt.json"
            body = json.dumps(self.result, sort_keys=True, indent=2)
            with path.open("x") as out:
                out.write(body)
            with self.assertRaises(FileExistsError):
                with path.open("x") as out:
                    out.write(body)


if __name__ == "__main__":
    unittest.main()
