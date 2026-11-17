"""Fail-closed, no-network regression tests for FRONTIER Ω ignition."""
import copy
import unittest

from frontier_omega.__main__ import COST_CATEGORIES, InventoryError, validate
from frontier_omega.ignition import ignition, portfolio_decisions


class IgnitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        opportunities, _ = validate()
        cls.opportunities = opportunities
        cls.o = next(o for o in opportunities if o["id"] == "O002")

    def fixture(self, old_accepted=12, synthetic=False):
        costs = {k: 0 for k in COST_CATEGORIES}
        costs.update({"model_compute": 250, "human_work": 250,
                      "independent_verification": 150,
                      "acquisition": 80, "residual_obligations": 100})
        return {
            "synthetic": synthetic, "source_access_confirmed": True,
            "test_authorized": True, "external_receipt_audit": True,
            "strongest_complete_alternative_tested": True,
            "buyer_contact_authorized": True,
            "matched_test": {
                "task_suite_sha256": "a" * 64,
                "same_frozen_suite": True,
                "review": {"independent_verifier": True,
                           "report_url": "https://example.invalid/unverified-assertion"},
                "baseline": {"date": "2026-10-11", "cases": 20,
                             "accepted": old_accepted, "p95_turnaround_hours": 40,
                             "costs_usd": costs},
                "current": {"date": "2026-11-16", "cases": 20,
                            "accepted": 20, "p95_turnaround_hours": 20,
                            "costs_usd": costs},
            },
            "pilot": {
                "signed_order": True, "contract_price_usd": 5000,
                "liquid_unrestricted_cash_usd": 2200,
                "remaining_obligations_reserved_usd": 100,
                "customer_rights_confirmed": True,
                "outside_option_beaten": True,
                "upper_complete_costs_usd": {
                    **{k: 0 for k in COST_CATEGORIES},
                    "model_compute": 400, "human_work": 300,
                    "independent_verification": 300,
                    "acquisition": 250, "residual_obligations": 200,
                },
            },
        }

    def test_uncertain_seed_only_proposes_a_probe(self):
        row = ignition(self.o)
        self.assertEqual(row["decision"], "PROBE_CANDIDATE")
        self.assertEqual(row["reported_metrics"], {})

    def test_synthetic_fixture_cannot_ignite(self):
        self.assertEqual(ignition(self.o, self.fixture(synthetic=True))["decision"],
                         "SYNTHETIC_REHEARSAL")

    def test_missing_source_access_blocks_testing(self):
        e = self.fixture()
        e["source_access_confirmed"] = False
        self.assertEqual(ignition(self.o, e)["decision"], "VERIFY_SOURCE_ACCESS")

    def test_permission_blocks_testing(self):
        e = self.fixture()
        e["test_authorized"] = False
        self.assertEqual(ignition(self.o, e)["decision"], "AWAIT_TEST_AUTHORIZATION")

    def test_missing_old_new_matched_test_demands_measurement(self):
        e = self.fixture()
        del e["matched_test"]
        self.assertEqual(ignition(self.o, e)["decision"], "RUN_MATCHED_CROSSING_TEST")

    def test_reported_threshold_requires_audit(self):
        e = self.fixture()
        e["external_receipt_audit"] = False
        self.assertEqual(ignition(self.o, e)["decision"], "INDEPENDENT_AUDIT_REQUIRED")

    def test_known_incumbent_alternative_is_mandatory(self):
        e = self.fixture()
        e["strongest_complete_alternative_tested"] = False
        self.assertEqual(ignition(self.o, e)["decision"], "COMPARE_STRONG_ALTERNATIVE")

    def test_no_authorized_outreach(self):
        e = self.fixture()
        e["buyer_contact_authorized"] = False
        self.assertEqual(ignition(self.o, e)["decision"], "AWAIT_MARKET_AUTHORIZATION")

    def test_price_hypothesis_is_not_signed_customer_order(self):
        e = self.fixture()
        e["pilot"]["signed_order"] = False
        self.assertEqual(ignition(self.o, e)["decision"], "VERIFY_PAID_DEMAND")

    def test_rights_precede_pilot(self):
        e = self.fixture()
        e["pilot"]["customer_rights_confirmed"] = False
        self.assertEqual(ignition(self.o, e)["decision"], "AWAIT_CUSTOMER_DATA_RIGHTS")

    def test_underwater_pilot_waits_for_cost_or_price(self):
        e = self.fixture()
        e["pilot"]["contract_price_usd"] = 1000
        self.assertEqual(ignition(self.o, e)["decision"], "WAIT_FOR_COST_OR_PRICE_CROSSING")

    def test_cash_cannot_be_replaced_by_future_contract_income(self):
        e = self.fixture()
        e["pilot"]["liquid_unrestricted_cash_usd"] = 300
        self.assertEqual(ignition(self.o, e)["decision"], "AWAIT_FUNDED_EXECUTION")

    def test_real_buyer_outside_option_required(self):
        e = self.fixture()
        e["pilot"]["outside_option_beaten"] = False
        self.assertEqual(ignition(self.o, e)["decision"], "COMPARE_BUYER_OUTSIDE_OPTION")

    def test_provisional_ignition_does_not_act_or_claim_profit(self):
        row = ignition(self.o, self.fixture())
        self.assertEqual(row["decision"], "IGNITE_PILOT_REVIEW_REQUIRED")
        self.assertIn("READ_ONLY", row["status"])
        self.assertEqual(row["reported_metrics"]["contracted_surplus_floor_usd_not_profit"], 3550.0)
        self.assertEqual(row["reported_metrics"]["tail_cash_reserved_within_complete_cost_usd"], 100.0)

    def test_past_already_qualified_is_not_new_five_week_crossing(self):
        row = ignition(self.o, self.fixture(old_accepted=20))
        self.assertFalse(row["reported_metrics"]["new_five_week_crossing_reported"])

    def test_repeat_sales_report_is_not_certified_cash(self):
        e = self.fixture()
        e["sales"] = {"accepted_and_collected_count": 2, "native_account_audited": True,
                      "repeat_customer_documented": True}
        row = ignition(self.o, e)
        self.assertEqual(row["decision"], "SCALE_CANDIDATE_AUDIT_REQUIRED")
        self.assertEqual(row["reported_metrics"]["claimed_accepted_and_collected_count"], 2)

    def test_zero_and_negative_amount_are_rejected(self):
        e = self.fixture()
        e["pilot"]["upper_complete_costs_usd"]["financing"] = -10
        with self.assertRaises(InventoryError):
            ignition(self.o, e)

    def test_nonfinite_amount_rejected(self):
        e = self.fixture()
        e["pilot"]["contract_price_usd"] = float("nan")
        with self.assertRaises(InventoryError):
            ignition(self.o, e)

    def test_liability_reserve_cannot_exceed_declared_tail(self):
        e = self.fixture()
        e["pilot"]["remaining_obligations_reserved_usd"] = 300
        with self.assertRaises(InventoryError):
            ignition(self.o, e)

    def test_missing_cost_category_rejected(self):
        e = self.fixture()
        del e["pilot"]["upper_complete_costs_usd"]["financing"]
        with self.assertRaises(InventoryError):
            ignition(self.o, e)

    def test_failed_current_benchmark_blocks_pilot(self):
        e = self.fixture()
        e["matched_test"]["current"]["accepted"] = 14
        self.assertEqual(ignition(self.o, e)["decision"], "RETEST_OR_REDESIGN")

    def test_nested_synthetic_benchmark_never_becomes_pilot(self):
        # A real-looking outer record must not erase the inner rehearsal label.
        e = self.fixture()
        e["matched_test"]["synthetic"] = True
        self.assertEqual(ignition(self.o, e)["decision"], "SYNTHETIC_REHEARSAL")

    def test_nested_benchmark_opportunity_identity_is_preserved(self):
        e = self.fixture()
        e["matched_test"]["opportunity_id"] = "O050"
        with self.assertRaises(InventoryError):
            ignition(self.o, e)

    def test_nonboolean_nested_synthetic_flag_rejected(self):
        e = self.fixture()
        e["matched_test"]["synthetic"] = "false"
        with self.assertRaises(InventoryError):
            ignition(self.o, e)

    def test_nonfinite_benchmark_p95_cannot_create_crossing(self):
        from frontier_omega.__main__ import assess_one
        for field in ("baseline", "current"):
            for nonfinite in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(field=field, nonfinite=str(nonfinite)):
                    e = self.fixture(old_accepted=20)["matched_test"]
                    e["opportunity_id"] = self.o["id"]
                    e["synthetic"] = False
                    e[field]["p95_turnaround_hours"] = nonfinite
                    with self.assertRaises(InventoryError):
                        assess_one(self.o, e)

    def test_all_57_are_candidates_and_none_are_live_sales(self):
        rows = portfolio_decisions(self.opportunities, {}, limit=48)
        self.assertEqual(rows["count"], 57)
        self.assertEqual(rows["actual_ignitions_executed"], 0)
        self.assertEqual(rows["actual_revenue_certified"], 0)
        self.assertTrue(all(r["decision"] == "PROBE_CANDIDATE" for r in rows["candidates"]))

    def test_unknown_evidence_id_fails_closed(self):
        with self.assertRaises(InventoryError):
            portfolio_decisions(self.opportunities, {"O999": {}})


if __name__ == "__main__":
    unittest.main()
