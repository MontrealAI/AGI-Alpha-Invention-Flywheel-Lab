import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from flywheel.commercial import run


class CommercialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.artifact = self.root / "artifact.json"
        self.artifact.write_text(json.dumps({"technical_outcome": "scoped-pass"}))

    def test_technical_pass_cannot_create_commerce(self):
        acceptance = {"accepted": True, "artifact_sha256": hashlib.sha256(self.artifact.read_bytes()).hexdigest()}
        result = run(self.artifact, self.root / "out", technical_acceptance=acceptance)
        self.assertTrue(result["technicalEvidenceBound"])
        self.assertEqual(result["snapshot"]["unrestrictedEarned"], 0)
        self.assertEqual(result["economics"]["actual_receipts"], 0)
        self.assertIsNone(result["economics"]["complete_cost"])
        self.assertIsNone(result["economics"]["complete_profit"])
        names = {item["name"] for item in result["mechanismChecks"]}
        self.assertTrue({"nonpayment", "acceptance-dispute-disputed-delivery", "duplicate-refund-idempotent",
                         "durable-interruption-recovery", "correlated-failures-refunded",
                         "opening-capital-cannot-fund-successor"} <= names)
        self.assertTrue(all(item["passed"] for item in result["mechanismChecks"]))

    def test_untrusted_evidence_and_forged_acceptance_do_not_qualify(self):
        evidence = {key: {"claimed": True} for key in ("buyer_specification", "participation_evidence", "price_evidence",
                                                      "complete_cost", "independent_service_acceptance")}
        result = run(self.artifact, self.root / "out", commercial_evidence=evidence,
                     technical_acceptance={"accepted": True, "artifact_sha256": "0" * 64})
        self.assertFalse(result["technicalEvidenceBound"])
        self.assertTrue(all(item["reason"] == "BUYER_ACCEPTANCE_AUTHORITY_NOT_QUALIFIED" for item in result["semanticChecks"]))
        self.assertEqual(result["snapshot"]["revenue"], 0)

    def test_exclusive_output_preserves_evidence(self):
        run(self.artifact, self.root / "out")
        with self.assertRaises(FileExistsError):
            run(self.artifact, self.root / "out")

    def test_source_mismatch_refused_before_import(self):
        with patch("flywheel.commercial.PINS", {"vendor/alpha_claim/contracts.py": "0" * 64}):
            with self.assertRaisesRegex(ValueError, "PINNED_EXCHANGE_SOURCE_MISMATCH"):
                run(self.artifact, self.root / "out")
        self.assertFalse((self.root / "out").exists())


if __name__ == "__main__":
    unittest.main()
