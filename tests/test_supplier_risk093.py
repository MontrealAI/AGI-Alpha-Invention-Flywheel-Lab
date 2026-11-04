"""Frozen supplier-risk093 receipts; never creates/resumes an account."""
import copy
import hashlib
import json
import unittest

from research.supplier_risk093 import SOURCE, certify

CASES=("central","weak","copycat","no_demand","failed_activation")


def altered_doc():
    return json.loads(SOURCE.read_text(encoding="utf-8"))


def check_altered(data):
    raw=json.dumps(data,sort_keys=True,separators=(",",":")).encode()
    return certify(raw, expected_digest=hashlib.sha256(raw).hexdigest())


class SupplierRisk093Tests(unittest.TestCase):
    def test_a_registered_all_cases_fixed_result(self):
        receipt=certify(SOURCE.read_bytes())
        self.assertEqual(set(receipt["cases"]),set(CASES))
        self.assertEqual(receipt["existing_audited_accounts"],10)
        self.assertEqual(receipt["new_native_accounts"],0)
        self.assertEqual(receipt["min_prepaid_aftertax_delta_microUSD"],-7_160_000)
        self.assertEqual(receipt["adverse_fee_free_negative_cases"],["weak","copycat","no_demand"])
        self.assertEqual(receipt["cases"]["central"]["fee_removed_unchanged_actions_pretax_bound_microUSD"],268_890_000)
        self.assertEqual(receipt["cases"]["weak"]["fee_removed_unchanged_actions_pretax_bound_microUSD"],-2_700_000)
        self.assertEqual(receipt["cases"]["failed_activation"]["fee_removed_unchanged_actions_pretax_bound_microUSD"],0)
        self.assertFalse(receipt["seller_supplier_robust_pareto_via_fee_only"])
        self.assertFalse(receipt["target_3b_reached"])

    def test_b_tampered_source_sha_fails_before_account_review(self):
        with self.assertRaisesRegex(ValueError,"SOURCE_SHA256_MISMATCH"):
            certify(SOURCE.read_bytes()+b" ")

    def test_c_missing_canonical_audit_fails(self):
        d=altered_doc()
        d["pairs"]["central"]["pilot"]["native_audit_accepted"]=False
        with self.assertRaisesRegex(ValueError,"UNAUDITED_ACCOUNT"):
            check_altered(d)

    def test_d_hidden_changed_liability_fails(self):
        d=altered_doc()
        d["pairs"]["central"]["pilot"]["financial_microUSD"]["tail_reserve"]+=1
        with self.assertRaisesRegex(ValueError,"LIQUIDITY_MISMATCH"):
            check_altered(d)

    def test_e_inconsistent_native_profit_fails(self):
        d=altered_doc()
        d["pairs"]["central"]["pilot"]["financial_microUSD"]["profit_after_modeled_tax"]+=1
        with self.assertRaisesRegex(ValueError,"PROFIT_MISMATCH"):
            check_altered(d)

    def test_f_false_comparison_fails(self):
        d=altered_doc()
        d["pairs"]["central"]["comparison"]["pilot_minus_organic_financial_microUSD"]["profit_after_modeled_tax"]+=1
        with self.assertRaisesRegex(ValueError,"PAIRED_DELTA_MISMATCH"):
            check_altered(d)

    def test_g_change_registered_cases_and_opening_fails(self):
        d=altered_doc()
        d["pairs"]["convenient_win"]=copy.deepcopy(d["pairs"]["central"])
        with self.assertRaisesRegex(ValueError,"REGISTERED_CASES_CHANGED"):
            check_altered(d)
        d=altered_doc()
        d["opening_microUSD_each"]*=2
        with self.assertRaisesRegex(ValueError,"CAPITAL_OR_REAL_SCOPE_CHANGED"):
            check_altered(d)

    def test_h_supplier_invoice_consistency_fails(self):
        d=altered_doc()
        d["pairs"]["central"]["pilot"]["tranches"][0]["invoice_microUSD"]+=1
        with self.assertRaisesRegex(ValueError,"PAID_INVOICE_MISMATCH"):
            check_altered(d)

    def test_i_no_real_commerce_or_partner_consent_inferred(self):
        d=certify(SOURCE.read_bytes())
        self.assertEqual(d["actual_revenue_usd"],0)
        self.assertIsNone(d["actual_full_cost_usd"])
        self.assertIsNone(d["real_trailing_365_profit_usd"])
        self.assertEqual(d["partner_cost_and_outside_option"],"UNKNOWN")
        self.assertEqual(d["current_decision"],"KEEP_ORGANIC_NO_NEW_PARTNER_CONTRACT")


if __name__ == "__main__":
    unittest.main()
