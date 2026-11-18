"""Frozen offline controls for nucleuswatch 1.2.0 native adapter, no HTTP."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MODULE = (HERE / "products/frontier-omega-ignition/evolution_trials"
          / "incumbent_stock_probe.py")
spec = importlib.util.spec_from_file_location("ignition_incumbent_stock_probe", MODULE)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class IncumbentInterfaceControls(unittest.TestCase):
    def test_reference_perturbation_is_lost_without_alert_provenance(self):
        original = probe.stock_view(probe.synthetic_raw_detection())
        altered = probe.stock_view(probe.synthetic_raw_detection(rfid=9999))
        # This is a counterexample to stock-output sufficiency, NOT evidence
        # that the altered reference was in the real October source.
        self.assertTrue(original.equals(altered))
        self.assertNotIn("rfid", original.columns)
        self.assertEqual(original.iloc[0]["band"], "g")

    def test_field_and_readout_perturbations_are_also_lost(self):
        original = probe.stock_view(probe.synthetic_raw_detection())
        altered = probe.stock_view(probe.synthetic_raw_detection(field=506, rcid=59))
        self.assertTrue(original.equals(altered))
        self.assertNotIn("field", original.columns)
        self.assertNotIn("rcid", original.columns)

    def test_stock_exposes_its_genuine_missing_alert_coverage_strength(self):
        value = probe.cross_broker_coverage_positive_control()
        self.assertTrue(value["alerce_present"])
        self.assertFalse(value["fink_present"])

    def test_finite_predeclared_verdict_and_limits(self):
        result = probe.probe()
        self.assertEqual(result["stock_only"]["verdict"],
                         "INSUFFICIENT_SOURCE_FIELDS_FOR_SPECIFIC_REFERENCE_STREAM")
        self.assertEqual(result["competent_augmented_route"],
                         "NOT_EXECUTED_OR_DISQUALIFIED")
        self.assertEqual(result["commerce_verdict"], "UNQUALIFIED_NO_DEPLOY")
        self.assertIsNone(result["source"]["verified_pypi_wheel_sha256"])
        self.assertEqual(json.loads(json.dumps(result))["new_collected_revenue_usd"], 0)

    def test_wrong_upstream_version_is_a_hard_failure(self):
        old = probe.nucleuswatch.__version__
        try:
            probe.nucleuswatch.__version__ = "0.0.0"
            with self.assertRaisesRegex(ValueError, "UPSTREAM_VERSION_NOT_PINNED"):
                probe.probe()
        finally:
            probe.nucleuswatch.__version__ = old

    def test_unverified_or_tampered_wheel_cannot_be_claimed(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "nucleuswatch-1.2.0-py3-none-any.whl"
            path.write_bytes(b"not the verified published wheel")
            with self.assertRaisesRegex(ValueError, "PINNED_WHEEL_DIGEST_MISMATCH"):
                probe.probe(wheel_path=path)


if __name__ == "__main__":
    unittest.main()
