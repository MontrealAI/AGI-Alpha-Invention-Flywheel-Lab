"""Offline qualification: reproducible search, withheld cases, adversarial refusal.

No real buyers, released protocols, revenue or general invention capability.
"""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import json
import tempfile
import unittest

from invent import (
    SCHEMA, Refused, aggregate, candidates, canonical, compare_successor,
    compile_plan, digest, run, strict_json, validate_brief, value,
)

HERE = Path(__file__).resolve().parent


def brief(name="brief-agent.json"):
    return strict_json((HERE / "examples" / name).read_text(encoding="utf-8"))


class MechanismFoundryTests(unittest.TestCase):
    def test_real_construction_search_across_modes(self):
        options = candidates()
        self.assertEqual(len(options), 25)
        self.assertEqual(len({(o["kind"], o["fee_bps"], o["expiry_days"])
                              for o in options}), len(options))
        self.assertEqual({o["kind"] for o in options},
                         {"direct", "buyer_escrow", "independent_escrow"})

    def test_two_frozen_distinct_briefs(self):
        a = run(brief())
        b = run(brief("brief-science.json"))
        self.assertNotEqual(a["input_sha256"], b["input_sha256"])
        for result in (a, b):
            self.assertEqual(result["decision"], "HOLD_NO_DEPLOY_NO_REVENUE")
            self.assertEqual(result["evidence"]["actual_buyer_demand"], "NOT_OBSERVED")
            self.assertEqual(result["evidence"]["real_collected_revenue"], "NOT_OBSERVED")
            self.assertEqual(result["evidence"]["new_mechanism_novelty"], "NOT_ESTABLISHED")
            self.assertEqual(result["development_selected"]["source"],
                             "AUTHORED_SYNTHETIC_MODEL")
            self.assertEqual(result["holdout_selected"]["source"],
                             "AUTHORED_SYNTHETIC_MODEL")

    def test_independent_holdout_not_used_to_choose(self):
        a = brief()
        first = run(a)["development_selected"]["candidate"]
        changed = deepcopy(a)
        changed["holdout"][0]["success_ppm"] = 0
        changed["holdout"][1]["success_ppm"] = 0
        self.assertEqual(first, run(changed)["development_selected"]["candidate"])

    def test_refuse_overlap_between_training_and_heldout(self):
        a = brief()
        a["holdout"][0]["id"] = a["development"][0]["id"]
        with self.assertRaisesRegex(Refused, "HOLDOUT_NOT_SEPARATE"):
            run(a)

    def test_required_controls_cannot_be_removed(self):
        a = brief()
        a["comparison_options"] = ["direct"]
        with self.assertRaisesRegex(Refused, "STRONG_COMPARISONS_REQUIRED"):
            run(a)

    def test_no_money_disguised_as_simulation(self):
        a = brief()
        a["currency"] = "USD"
        with self.assertRaisesRegex(Refused, "NO_REAL_MONEY_INPUT"):
            run(a)

    def test_strict_duplicate_json_and_nan(self):
        with self.assertRaises(Refused):
            strict_json('{"x":1,"x":2}')
        with self.assertRaises(Refused):
            strict_json('{"a":NaN}')

    def test_fraudulent_evidence_not_recognized(self):
        a = brief()
        a["enabler"]["verified"] = True
        a["rights_confirmed"] = True
        out = run(a)
        self.assertEqual(out["decision"], "HOLD_NO_DEPLOY_NO_REVENUE")
        self.assertEqual(out["evidence"]["independent_frontier_verification"],
                         "NOT_PERFORMED")

    def test_zero_chance_refuses_profitable_escrow(self):
        a = brief()
        for case in a["development"] + a["holdout"]:
            case["success_ppm"] = 0
            case["seller_outside"] = 1
        result = run(a)
        self.assertEqual(result["decision"], "HOLD_NO_DEPLOY_NO_REVENUE")
        self.assertTrue(all(c["candidate"]["fee_bps"] <= 200
                            for c in candidates()))

    def test_exact_balance_of_modeled_participant_utilities(self):
        case = brief()["development"][0]
        mechanism = {"kind": "independent_escrow", "fee_bps": 100,
                     "expiry_days": 3, "deployable": True, "verifier": "independent"}
        out = value(case, mechanism)
        self.assertTrue(out["accepted"])
        expected = (
            Fraction(case["success_ppm"], 1_000_000) *
            case["value_if_accepted"] - case["seller_cost"] -
            case["network_cost"] - case["independent_check_cost"] -
            case["operator_cost"]
        )
        self.assertEqual(out["buyer"] + out["seller"] + out["owner"], expected)

    def test_total_cost_includes_frozen_search_cost(self):
        a = brief()
        with_cost = run(a)
        a["fixed_construction_cost"] = 0
        no_cost = run(a)
        self.assertNotEqual(
            with_cost["holdout_selected"]["owner_profit_exact"],
            no_cost["holdout_selected"]["owner_profit_exact"],
        )

    def test_no_entry_baseline_is_defined_in_input(self):
        a = brief()
        self.assertIn("no_entry", a["comparison_options"])
        self.assertIn("free_existing_escrow", a["comparison_options"])

    def test_compiler_cannot_silently_deploy(self):
        for mechanism in candidates():
            built = compile_plan(mechanism)
            if mechanism["deployable"]:
                self.assertEqual(built["deployment_status"], "NOT_DEPLOYED")
                self.assertEqual(built["security_review"], "UNQUALIFIED")
                self.assertIn("TREASURY_REQUIRED", built["constructor"]["feeRecipient"])
                self.assertEqual(built["constructor"]["platformFeeBps"],
                                 mechanism["fee_bps"])
            else:
                self.assertEqual(built["status"], "NO_CONTRACT")

    def test_successor_is_not_called_causal_improvement(self):
        prior = run(brief())
        new = brief("brief-science.json")
        result = compare_successor(prior, new)
        self.assertEqual(result["claimed_causal_compounding"], "NOT_ESTABLISHED")
        self.assertEqual(result["actual_economic_value"], "NOT_OBSERVED")
        self.assertNotEqual(result["first_mission"], result["successor_mission"])

    def test_same_mission_cannot_be_fresh_successor(self):
        first = brief()
        with self.assertRaisesRegex(Refused, "SUCCESSOR_MUST_BE_DISTINCT"):
            compare_successor(run(first), first)

    def test_unknown_fields_refused(self):
        a = brief()
        a["new_money"] = "ONE_BILLION"
        with self.assertRaisesRegex(Refused, "EXACT_BRIEF_FIELDS"):
            run(a)

    def test_digest_is_deterministic(self):
        self.assertEqual(digest({"a": 1, "b": 2}), digest({"b": 2, "a": 1}))

    def test_synthetic_seller_refusal_not_counted_as_cash(self):
        case = brief("brief-science.json")["development"][0]
        m = {"kind": "independent_escrow", "fee_bps": 200,
             "expiry_days": 7, "deployable": True}
        out = value(case, m)
        self.assertFalse(out["accepted"])
        self.assertEqual(out["owner"], 0)

    def test_honest_adverse_model_still_returns_pack(self):
        bad = run(brief("brief-science.json"))
        self.assertEqual(bad["decision"], "HOLD_NO_DEPLOY_NO_REVENUE")
        self.assertEqual(bad["grammar"]["candidate_count"], 25)


if __name__ == "__main__":
    unittest.main()
