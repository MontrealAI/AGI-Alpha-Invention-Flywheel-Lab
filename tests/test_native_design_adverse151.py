"""Source-bound finite preflight; never starts a native business during unittest."""
import copy
import tempfile
import unittest
from pathlib import Path

from commercial.ledger import digest
from scripts.run_native_design_adverse151 import (
    ARMS, CAPITALS, REGIMES, interpret, main, robust_verdict, specifications,
)


class NativeAdverse151Tests(unittest.TestCase):
    def test_six_fixed_case_registry_and_no_seventh_selected_arm(self):
        rows = specifications()
        self.assertEqual(len(rows), 6)
        expected = [regime + "-" + tier for regime, *_ in REGIMES for tier, _ in CAPITALS]
        self.assertEqual([name for name, _ in rows], expected)
        self.assertEqual({tuple((d["id"], d["arm"]) for d in spec["designs"])
                          for _, spec in rows}, {ARMS})
        self.assertEqual({spec["incumbent"] for _, spec in rows}, {"incumbent"})
        self.assertTrue(all(spec["evidence_role"] == "finite_authored_comparison"
                            and spec["config"]["horizon_days"] == 21
                            and spec["config"]["customer_pool"] == 10 for _, spec in rows))
        self.assertTrue(all(spec["development_seed"] != spec["confirmation_seed"]
                            for _, spec in rows))

    def test_identical_common_random_seeds_across_two_capital_sensitivities(self):
        pairs = specifications()
        for low, high in zip(pairs[::2], pairs[1::2]):
            a, b = low[1], high[1]
            for field in ("development_seed", "confirmation_seed", "service_cohort_seed"):
                self.assertEqual(a[field], b[field])
            self.assertEqual(a["config"]["opening"], 2500 * 1_000_000)
            self.assertEqual(b["config"]["opening"], 25000 * 1_000_000)
            low_cfg = copy.deepcopy(a["config"])
            high_cfg = copy.deepcopy(b["config"])
            del low_cfg["opening"]
            del high_cfg["opening"]
            self.assertEqual(low_cfg, high_cfg)

    def test_no_outside_funding_or_contract_tail_maturity_change(self):
        for _, spec in specifications():
            cfg = spec["config"]
            self.assertNotIn("prospective_policy", cfg)
            self.assertNotIn("cash_diagnostic_available", cfg)
            self.assertNotIn("startup_acquisition_policy", cfg)
            self.assertEqual(set(d["arm"] for d in spec["designs"]),
                             {"baseline", "growth", "competitive_growth"})

    def test_all_six_same_challenger_support_and_any_one_veto(self):
        keys = [name for name, _ in specifications()]
        favorable = {name: {"native_challenger": "competitive_distribution"}
                     for name in keys}
        yes = robust_verdict(favorable)
        self.assertEqual(yes["support"], "ROBUST_SIMULATED_CHALLENGER_SUPPORTED")
        self.assertEqual(yes["common_challenger"], "competitive_distribution")
        for change in (None, "earned_distribution"):
            altered = copy.deepcopy(favorable)
            altered[keys[-1]]["native_challenger"] = change
            no = robust_verdict(altered)
            self.assertEqual(no["support"], "REJECT_ROBUST_SIMULATED_CHALLENGER")
            self.assertIsNone(no["common_challenger"])

    def test_missing_or_extra_case_rejected(self):
        cases = {name: {"native_challenger": None} for name, _ in specifications()}
        cases.pop(next(iter(cases)))
        with self.assertRaisesRegex(ValueError, "REGISTERED_SIX_CASE"):
            robust_verdict(cases)
        cases["spurious"] = {"native_challenger": "earned_distribution"}
        with self.assertRaisesRegex(ValueError, "REGISTERED_SIX_CASE"):
            robust_verdict(cases)

    def _native(self, spec, selected="earned_distribution", accepted=True):
        receipt = {
            "profit_microUSD": 21_000_000,
            "obligations_covered": True,
            "unrestricted_earned_microUSD": 9_000_000,
        }
        return {
            "schema": "agi-alpha/native-design-search041/v1",
            "status": "CONDITIONAL_SIMULATED_EXECUTION",
            "source_sha256": "0" * 64, "spec_sha256": digest(spec),
            "confirmation": {"incumbent": {**receipt, "profit_microUSD": 10_000_000},
                             "earned_distribution": receipt},
            "heldout_recommendation": {
                "recommended_policy": selected, "challenger_accepted": accepted,
                "native_financial_action_authority": []},
            "matched_confirmation_profit_delta_microUSD": 11_000_000,
            "connected_earned_successor_witness": None,
        }

    def test_fresh_narrow_native_winner_is_not_real_commerce(self):
        spec = specifications()[0][1]
        row = interpret(spec, self._native(spec))
        self.assertTrue(row["robust_challenger_support_in_this_case"])
        self.assertEqual(row["actual_external_collections_microUSD"], 0)
        self.assertEqual(row["real_buyer_count"], 0)
        self.assertEqual(row["native_financial_action_authority"], [])

    def test_incumbent_hold_or_no_deploy(self):
        spec = specifications()[0][1]
        r = self._native(spec, selected="incumbent", accepted=False)
        row = interpret(spec, r)
        self.assertEqual(row["native_recommendation"], "incumbent")
        self.assertFalse(row["robust_challenger_support_in_this_case"])
        r = self._native(spec, selected=None, accepted=False)
        self.assertEqual(interpret(spec, r)["native_recommendation"], "NO_DEPLOY")

    def test_reject_report_forgery_and_undeclared_financial_authority(self):
        spec = specifications()[0][1]
        for mutate, expected in (
            (lambda r: r.update(spec_sha256="1" * 64), "REGISTERED_CASE_SOURCE_CHANGED"),
            (lambda r: r["heldout_recommendation"].update(
                native_financial_action_authority=["purchase"]), "NO_EXTERNAL_ACTION_AUTHORITY_ALLOWED"),
            (lambda r: r["heldout_recommendation"].update(
                recommended_policy="made_up"), "UNSUPPORTED_NATIVE_POLICY_RECOMMENDATION"),
            (lambda r: r["heldout_recommendation"].update(
                challenger_accepted=False), "CHALLENGER_RECOMMENDATION_CONFLICT"),
        ):
            r = self._native(spec)
            mutate(r)
            with self.assertRaisesRegex(ValueError, expected):
                interpret(spec, r)

    def test_existing_root_refused_without_operating_any_account(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "FRESH_ABSOLUTE_NON_SYMLINK"):
                main(["--output", temp])
            self.assertEqual(list(Path(temp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
