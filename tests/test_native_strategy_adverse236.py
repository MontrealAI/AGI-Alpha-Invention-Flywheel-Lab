"""No favorable-seed selection and no unsupported commercial claim for adverse236."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.native_strategy_adverse236 import (
    CASES, PROTOCOL_SCHEMA, load_protocol, public_case, registered_spec,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "campaign/native-strategy-adverse236/PROTOCOL.json"


class Adverse236Tests(unittest.TestCase):
    def setUp(self):
        self.original = json.loads(REGISTRY.read_text())

    def write(self, value):
        f = tempfile.TemporaryDirectory()
        self.addCleanup(f.cleanup)
        path = Path(f.name) / "protocol.json"
        path.write_text(json.dumps(value))
        return path

    def test_exact_preregistered_all_cohorts_one_stopping_rule(self):
        contract = load_protocol(REGISTRY)
        self.assertEqual(contract["schema"], PROTOCOL_SCHEMA)
        self.assertEqual(len(contract["cohorts"]), 5)
        self.assertEqual(tuple(c["id"] for c in contract["cohorts"]), CASES)
        self.assertEqual(len({
            seed for c in contract["cohorts"]
            for seed in (c["development_seed"], c["confirmation_seed"])
        }), 10)
        self.assertTrue(contract["no_deploy_option"])
        self.assertIn("do not retune inputs", contract["stopper"])
        self.assertIn("actual", contract["outcomes_and_costs"])

    def test_each_native_spec_keeps_same_market_across_design_arms(self):
        c = load_protocol(REGISTRY)
        for case in c["cohorts"]:
            with self.subTest(case=case["id"]):
                spec = registered_spec(c, case)
                self.assertEqual(spec["evidence_role"], "finite_authored_comparison")
                self.assertEqual(spec["incumbent"], "incumbent")
                self.assertEqual(spec["development_seed"], case["development_seed"])
                self.assertEqual(spec["confirmation_seed"], case["confirmation_seed"])
                self.assertEqual({x["arm"] for x in spec["designs"]},
                                 {"baseline", "growth", "competitive_growth"})
                for name, value in case["config_overrides"].items():
                    self.assertEqual(spec["config"][name], value)
                self.assertEqual(spec["config"]["scope"], "SIMULATED")
                self.assertEqual(spec["config"]["customer_pool"], 8)

    def test_rejects_retrospective_missing_or_extra_cohort(self):
        for mutation in ("missing", "extra", "reorder"):
            c = copy.deepcopy(self.original)
            if mutation == "missing":
                c["cohorts"].pop()
            if mutation == "extra":
                c["cohorts"].append(copy.deepcopy(c["cohorts"][-1]))
            if mutation == "reorder":
                c["cohorts"].reverse()
            with self.subTest(mutation=mutation), self.assertRaisesRegex(
                    ValueError, "EXACT_REGISTERED_SCENARIO"):
                load_protocol(self.write(c))

    def test_rejects_seed_reuse_and_buyer_value_manipulation(self):
        c = copy.deepcopy(self.original)
        c["cohorts"][1]["confirmation_seed"] = c["cohorts"][0]["confirmation_seed"]
        with self.assertRaisesRegex(ValueError, "SEEDS_REQUIRED"):
            load_protocol(self.write(c))
        c = copy.deepcopy(self.original)
        c["cohorts"][1]["config_overrides"]["buyer_budget_multiplier_bps"] = 20000
        with self.assertRaisesRegex(ValueError, "UNREGISTERED_MARKET"):
            load_protocol(self.write(c))
        c = copy.deepcopy(self.original)
        c["exact_registered_designs"][1]["arm"] = "baseline"
        with self.assertRaisesRegex(ValueError, "EXACT_INCUMBENT"):
            load_protocol(self.write(c))

    def test_rejects_relaxed_no_deploy_and_source_fork(self):
        c = copy.deepcopy(self.original)
        c["decision_rule"]["no_deploy"] = "deploy"
        with self.assertRaisesRegex(ValueError, "COMMERCIAL_BOUNDARY"):
            load_protocol(self.write(c))
        c = copy.deepcopy(self.original)
        c["frozen_underlying_source"] = "x" * 40
        with self.assertRaisesRegex(ValueError, "SOURCE_PARENT"):
            load_protocol(self.write(c))

    def test_native_challenger_must_win_and_protect_every_condition(self):
        case = self.original["cohorts"][0]
        proof = {
            "heldout_recommendation": {
                "recommended_policy": "earned_distribution",
                "challenger_accepted": True,
            },
            "matched_confirmation_profit_delta_microUSD": 55,
            "confirmed_positive_funded_successor_opportunity": True,
            "comparative_advantage_on_one_fresh_seed": True,
            "confirmation": {
                "incumbent": {"profit_microUSD": 10, "obligations_covered": True,
                              "settled_orders": 1},
                "earned_distribution": {"profit_microUSD": 65, "obligations_covered": True,
                                        "settled_orders": 2},
            },
            "selection": {"selected": "earned_distribution"},
            "source_sha256": "source",
            "spec_sha256": "spec",
        }
        self.assertTrue(public_case(case, proof, 1.2, .2)["strict_adverse_challenger_gate"])
        self.assertEqual(public_case(case, proof, 1.2, .2)["external_policy_adoption"], "NO_DEPLOY")
        for field, bad in (
            ("matched_confirmation_profit_delta_microUSD", 0),
            ("matched_confirmation_profit_delta_microUSD", -1),
            ("matched_confirmation_profit_delta_microUSD", None),
            ("confirmed_positive_funded_successor_opportunity", False),
            ("comparative_advantage_on_one_fresh_seed", False),
        ):
            p = copy.deepcopy(proof)
            p[field] = bad
            with self.subTest(field=field, bad=bad):
                self.assertFalse(public_case(case, p, 1.2, .2)[
                    "strict_adverse_challenger_gate"])
        p = copy.deepcopy(proof)
        p["heldout_recommendation"]["challenger_accepted"] = False
        self.assertFalse(public_case(case, p, 1.2, .2)["strict_adverse_challenger_gate"])

    def test_no_legal_or_cash_claim_from_potential_simulation(self):
        case = self.original["cohorts"][0]
        proof = {
            "heldout_recommendation": {"recommended_policy": None,
                                        "challenger_accepted": False},
            "matched_confirmation_profit_delta_microUSD": None,
            "confirmed_positive_funded_successor_opportunity": False,
            "comparative_advantage_on_one_fresh_seed": False,
            "confirmation": {}, "selection": {"selected": None},
            "source_sha256": "source", "spec_sha256": "spec",
        }
        result = public_case(case, proof, 0.1, 0.1)
        self.assertEqual(result["actual_external_collections_usd"], 0)
        self.assertIsNone(result["unmeasured_host_or_model_dollars"])
        self.assertFalse(result["strict_adverse_challenger_gate"])


if __name__ == "__main__":
    unittest.main()
