"""EIT191 bounded adverse controls: no invented eligibility, sale, or cash."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import hashlib
import json
import tempfile
import unittest

from research.eit_commercial191.gate import (
    AS_OF, POLAND, SPAIN, GateError, deadline_gate, evaluate, main,
    validate_notices, write_create_only,
)


class Eit191Tests(unittest.TestCase):
    def test_official_close_and_unknown_not_falsely_open(self):
        self.assertEqual(deadline_gate(SPAIN, AS_OF),
                         "CLOSED_BY_DECLARED_OFFICIAL_DEADLINE")
        self.assertEqual(deadline_gate(POLAND, AS_OF),
                         "UNKNOWN_NOT_PROVEN_OPEN")
        self.assertEqual(deadline_gate(SPAIN, date(2026, 9, 20)),
                         "DATE_NOT_ELAPSED_ELIGIBILITY_UNVERIFIED")

    def test_all_three_materially_different_paid_routes_refuse(self):
        result = evaluate()
        paid = [c for c in result["comparisons"] if c["route"] != "no_deploy_no_bid"]
        self.assertEqual(len(paid), 3)
        self.assertTrue(all(not c["qualified"] for c in paid))
        self.assertTrue(all(c["missing_independently_authenticated"] for c in paid))
        self.assertEqual(result["selected"], "no_deploy_no_bid")

    def test_never_convert_tender_to_collected_contract_or_profit(self):
        result = evaluate()
        self.assertEqual(result["observed_paid_contracts_from_this_work"], 0)
        self.assertEqual(result["new_earned_cash_from_this_work_usd"], 0)
        self.assertIsNone(result["actual_native_trailing_365_profit_usd"])
        self.assertFalse(result["three_billion_target_achieved"])
        self.assertFalse(result["release_or_deploy"])

    def test_bundle_is_not_eit_only_price_or_contract(self):
        result = evaluate()
        spain = next(x for x in result["notices"] if x["notice"] == SPAIN["notice"])
        self.assertEqual(spain["full_bundle_estimate_eur"], 228000)
        self.assertIsNone(spain["eit_only_estimate_eur"])
        self.assertFalse(spain["is_award"])

    def test_secondary_deadline_is_not_admitted_as_official(self):
        forged = deepcopy(POLAND)
        forged["official_deadline"] = forged["secondary_deadline_unverified"]
        with self.assertRaisesRegex(GateError, "REGISTERED_NOTICE_FACTS_CHANGED"):
            evaluate(notices=(forged, SPAIN))

    def test_claimed_rights_or_funds_cannot_self_approve(self):
        for claim in ("medical_device_authorization", "written_oem_partner_consent",
                      "authoritative_native_funding", "verified_industrial_buyer_demand"):
            with self.subTest(claim=claim), self.assertRaisesRegex(
                    GateError, "NO_PROOF_AUTHENTICATOR"):
                evaluate(claimed_proofs={claim: True})

    def test_false_or_unknown_claim_is_not_pass(self):
        result = evaluate(claimed_proofs={"medical_device_authorization": None,
                                         "verified_industrial_buyer_demand": False})
        self.assertEqual(result["selected"], "no_deploy_no_bid")
        with self.assertRaisesRegex(GateError, "UNSUPPORTED_PROOF_CLAIM"):
            evaluate(claimed_proofs={"collected_revenue": "3000000000"})

    def test_duplicate_or_changed_primary_record_fails(self):
        with self.assertRaisesRegex(GateError, "NOTICE_SET_MISMATCH"):
            validate_notices((POLAND, POLAND))
        forged = deepcopy(SPAIN)
        forged["full_bundle_estimate_eur"] = 10_000_000
        with self.assertRaises(GateError):
            validate_notices((POLAND, forged))
        forged2 = deepcopy(POLAND)
        forged2["published"] = "2025-01-01"
        with self.assertRaisesRegex(GateError, "REGISTERED_NOTICE_FACTS_CHANGED"):
            validate_notices((forged2, SPAIN))

    def test_create_only_cannot_clobber_liabilities_or_old_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "receipt.json"
            write_create_only(p, evaluate())
            original = p.read_bytes()
            with self.assertRaisesRegex(GateError, "ALREADY_EXISTS"):
                write_create_only(p, {"selected": "fake"})
            self.assertEqual(p.read_bytes(), original)
            other = Path(d) / "symlink.json"
            other.symlink_to(p)
            with self.assertRaisesRegex(GateError, "ALREADY_EXISTS"):
                write_create_only(other, evaluate())

    def test_actual_command_receipt_has_source_and_protocol_digest(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "one-and-only.json"
            main(["--out", str(p)])
            receipt = json.loads(p.read_text())
            self.assertEqual(receipt["selected"], "no_deploy_no_bid")
            self.assertEqual(len(receipt["protocol_sha256"]), 64)
            self.assertEqual(len(receipt["executing_source_sha256"]), 64)
            self.assertIsNone(receipt["actual_native_trailing_365_profit_usd"])
            with self.assertRaisesRegex(GateError, "ALREADY_EXISTS"):
                main(["--out", str(p)])


if __name__ == "__main__":
    unittest.main()
