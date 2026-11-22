"""All quote controls are artificial fixtures; hosted job additionally reads exact public evidence."""
from fractions import Fraction
import hashlib
import json
import unittest

from research import prequote094 as m


def fixture():
    def account(revenue):
        expense = 100000000
        f = {
            "recognized_revenue": revenue, "recovery_income": 0,
            "incurred_expenses_including_tax": expense,
            "profit_after_modeled_tax": revenue - expense,
            "collections": revenue, "cash_expenses_paid": expense,
            "cash": m.OPENING + revenue - expense, "tail_reserve": 0,
            "working_capital": 0, "custody_reserve": 0,
            "custody_restricted": 0, "reserved_investment": 0,
            "available_cash": m.OPENING + revenue - expense,
        }
        return {
            "native_audit_accepted": True,
            "audit_receipt_sha256": "TEST_ONLY_NOT_A_NATIVE_AUDIT",
            "artifact_file_sha256": {"fixture": "TEST_ONLY"},
            "incurred_expense_breakdown_microUSD": {"production_contract": expense},
            "financial_microUSD": f,
        }
    data = {
        "schema": "omega/earned-paid-reach-paired-evidence/v1", "window_days": [0,365],
        "end_day_exclusive": True, "opening_microUSD_each": m.OPENING,
        "actual_revenue_usd": 0, "actual_complete_lifecycle_cost_usd": None,
        "pairs": {},
    }
    fields = ("profit_after_modeled_tax","cash","available_cash","collections",
              "recognized_revenue","incurred_expenses_including_tax","tail_reserve")
    for name, delta in zip(m.CASES, m.EXPECTED_DELTAS):
        old, new = account(400000000), account(400000000 + delta)
        a, b = old["financial_microUSD"], new["financial_microUSD"]
        data["pairs"][name] = {
            "organic": old, "pilot": new,
            "comparison": {"pilot_minus_organic_financial_microUSD": {
                k: b[k] - a[k] for k in fields
            }},
        }
    return data


def raw(data):
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def cert(data):
    payload = raw(data)
    return m.certify(payload, hashlib.sha256(payload).hexdigest())


class FrozenEvidenceTests(unittest.TestCase):
    def test_real_public_case_sha_when_source_present(self):
        if not m.SOURCE.is_file():
            self.skipTest("original repository evidence not mounted in local-only test")
        result = m.certify(m.SOURCE.read_bytes())
        self.assertEqual(result["source_sha256"], m.SOURCE_SHA256)
        self.assertEqual(result["registered_grid_size"], 108)
        self.assertEqual(result["decision"], "NO_NEW_CHANNEL_COMMITMENT")

    def test_five_case_and_exact_108_cell_grid(self):
        result = cert(fixture())
        self.assertEqual(result["registered_grid_size"], 108)
        self.assertEqual(sum(result["illustrative_winner_counts_not_evidence_of_demand"].values()),108)
        self.assertEqual(result["strongest_no_information_robust_policy"], "NO_NEW_CHANNEL")
        self.assertEqual(result["maximin_unscreened_incremental_microUSD"], -7160000)
        self.assertFalse(result["target_3b_achieved"])
        self.assertEqual(result["new_native_account_count"],0)
        self.assertIsNone(result["signal_quality_measurements"])

    def test_exact_source_sha_rejects_fixtures_by_default(self):
        with self.assertRaisesRegex(ValueError, "SOURCE_SHA256_MISMATCH"):
            m.certify(raw(fixture()))

    def test_duplicate_keys_rejected(self):
        text = raw(fixture()).decode().replace('"actual_revenue_usd":0',
                      '"actual_revenue_usd":0,"actual_revenue_usd":0',1).encode()
        with self.assertRaisesRegex(ValueError,"DUPLICATE_JSON_KEY"):
            m.certify(text,hashlib.sha256(text).hexdigest())

    def test_tampered_cash_and_audit_rejected(self):
        d=fixture()
        d["pairs"]["central"]["pilot"]["financial_microUSD"]["cash"]+=1
        with self.assertRaisesRegex(ValueError,"INCORRECT_CASH"):
            cert(d)
        d=fixture()
        d["pairs"]["central"]["pilot"]["native_audit_accepted"]=False
        with self.assertRaisesRegex(ValueError,"UNVERIFIED_NATIVE_EXPORT"):
            cert(d)

    def test_unknown_true_costs_cannot_be_silently_zeroed(self):
        d=fixture();d["actual_complete_lifecycle_cost_usd"]=0
        with self.assertRaisesRegex(ValueError,"FROZEN_SCOPE_CHANGED"):cert(d)
        d=fixture();d["actual_revenue_usd"]=False
        with self.assertRaisesRegex(ValueError,"FROZEN_SCOPE_CHANGED"):cert(d)

    def test_comparison_and_profit_reconcile(self):
        d=fixture()
        d["pairs"]["weak"]["comparison"]["pilot_minus_organic_financial_microUSD"]["profit_after_modeled_tax"]+=1
        with self.assertRaisesRegex(ValueError,"COMPARISON_MISMATCH"):cert(d)
        d=fixture()
        d["pairs"]["weak"]["pilot"]["financial_microUSD"]["recognized_revenue"]+=1
        with self.assertRaisesRegex(ValueError,"INCORRECT_PROFIT"):cert(d)

    def test_integer_and_nonfinite_costs_rejected(self):
        d=fixture();d["opening_microUSD_each"]=True
        with self.assertRaisesRegex(ValueError,"INTEGER_REQUIRED"):cert(d)
        d=fixture()
        d["pairs"]["weak"]["pilot"]["incurred_expense_breakdown_microUSD"]["production_contract"]=-100
        with self.assertRaisesRegex(ValueError,"INCORRECT_COSTS"):cert(d)
        text=raw(fixture()).replace(b'"actual_revenue_usd":0',b'"actual_revenue_usd":NaN')
        with self.assertRaisesRegex(ValueError,"NONFINITE_JSON"):
            m.certify(text,hashlib.sha256(text).hexdigest())


class GameAndAuthorizationTests(unittest.TestCase):
    def test_hypothetical_policy_never_authorizes_purchase(self):
        result=cert(fixture())
        self.assertEqual(result["decision"],"NO_NEW_CHANNEL_COMMITMENT")
        for row in result["registered_grid"]:
            self.assertFalse(row["authorize_purchase"])
            self.assertFalse(row["known_signal_calibration"])

    def test_costless_perfect_signal_is_not_prospective(self):
        s=m.choose_policy(Fraction(1,2),Fraction(1),Fraction(0),0)
        self.assertEqual(s["finite_game_optimal_policy_HYPOTHETICAL"],"SCREEN_BUY_POSITIVE")
        self.assertEqual(s["best_payoff_microUSD_exact"]["numerator"],102556000)
        self.assertFalse(s["authorize_purchase"])

    def test_strong_competitor_may_invert_bad_signal(self):
        s=m.choose_policy(Fraction(1,2),Fraction(0),Fraction(1),0)
        self.assertEqual(s["finite_game_optimal_policy_HYPOTHETICAL"],"SCREEN_BUY_NEGATIVE")

    def test_adverse_only_buy_with_signal_cost_loses(self):
        s=m.choose_policy(Fraction(0),Fraction(1),Fraction(0),1000000)
        self.assertEqual(s["finite_game_optimal_policy_HYPOTHETICAL"],"NO_NEW_CHANNEL")
        self.assertLess(s["policy_payoffs_microUSD_exact"]["SCREEN_BUY_POSITIVE"]["numerator"],0)

    def test_unconditional_incumbent_retained_and_oracle_bound(self):
        for p in m.GRIDS["central_prior"]:
            for tpr in m.GRIDS["sensitivity"]:
                for fpr in m.GRIDS["false_positive_rate"]:
                    for c in m.GRIDS["screen_cost_usd"]:
                        r=m.choose_policy(p,tpr,fpr,c*m.USD)
                        vals=r["policy_payoffs_microUSD_exact"]
                        self.assertIn("UNSCREENED_PILOT",vals)
                        self.assertIn("NO_NEW_CHANNEL",vals)
                        v=lambda x:Fraction(x["numerator"],x["denominator"])
                        self.assertGreaterEqual(v(r["best_payoff_microUSD_exact"]),0)
                        self.assertLessEqual(v(r["best_payoff_microUSD_exact"]),
                                             v(r["unattainable_perfect_oracle_upper_microUSD_exact"]))

    def test_bad_probability_and_negative_screen_price(self):
        for p,tpr,fpr,c in ((Fraction(11,10),Fraction(1),Fraction(0),0),
                            (Fraction(1),Fraction(-1),Fraction(0),0),
                            (Fraction(1),Fraction(1),Fraction(0),-1)):
            with self.assertRaises(ValueError):m.choose_policy(p,tpr,fpr,c)


if __name__=="__main__":
    unittest.main()
