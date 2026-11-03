"""Frozen adversarial scenarios: conditional payoffs, not real contracts."""
import copy
import tempfile
import unittest
from pathlib import Path

from enterprise078.transactional_admission.choice import quote, subset_key
from enterprise078.transactional_admission.offer import COSTS
from .guard import pin_source, review


def offer(ident="a", buyer="buyer", partner="supplier"):
    return {"id": ident, "buyer": buyer, "price": 200,
            "terms_id": "complete-service-v1", "partner": partner}


def case(rows, bundles, cost=120):
    buyers, partners, full = {}, {}, {}
    for ids in bundles:
        selected = [row for row in rows if row["id"] in ids]
        bg, pg = {}, {}
        for row in selected:
            bg.setdefault(row["buyer"], []).append(row)
            if row["partner"] is not None:
                pg.setdefault(row["partner"], []).append(row)
        for name, group in bg.items():
            buyers.setdefault(name, {})[subset_key(r["id"] for r in group)] = {
                "joint_value": 600 if len(group) > 1 else 500,
                "consent": True, "quote": quote(group),
                "outside": {"human": 100, "competitor_ai": 70,
                            "self_service": 50, "no_purchase": 0},
            }
        for name, group in pg.items():
            partners.setdefault(name, {})[subset_key(r["id"] for r in group)] = {
                "consent": True, "quote": quote(group),
            }
        full[subset_key(ids)] = {k: cost if k == "production" else 0 for k in COSTS}
    return {"buyers": buyers, "collection_lower_bounds": {r["id"]: 200 for r in rows},
            "costs": full, "partners": partners, "assumptions_known_at": 5}


def economics(rows, bundles, compensation=80, own_cost=50, outside=10):
    result = {}
    for ids in bundles:
        groups = {}
        for row in rows:
            if row["id"] in ids and row["partner"] is not None:
                groups.setdefault(row["partner"], []).append(row)
        for name, group in groups.items():
            result.setdefault(name, {})[subset_key(r["id"] for r in group)] = {
                "quote": quote(group), "compensation": compensation,
                "own_cost": own_cost, "outside_surplus": outside,
                "seller_cost_category": "production",
            }
    return result


class PartnerPayoffTests(unittest.TestCase):
    def check(self, rows=None, bundles=None, scenarios=None, econ=None, **overrides):
        rows = [offer()] if rows is None else rows
        bundles = [["a"]] if bundles is None else bundles
        scenarios = {"base": case(rows, bundles)} if scenarios is None else scenarios
        econ = {name: economics(rows, bundles) for name in scenarios} if econ is None else econ
        kw = {"wallets": {r["buyer"]: 1000 for r in rows}, "available": 1000,
              "earned": 1000, "sunk_acquisition": 30, "decision_time": 5,
              "scenarios": scenarios, "partner_economics": econ}
        kw.update(overrides)
        return review(rows, bundles, **kw)

    def test_consented_but_negative_supplier_payoff_refuses(self):
        rows, bundles = [offer()], [["a"]]
        econ = {"base": economics(rows, bundles, compensation=40, own_cost=60, outside=0)}
        result = self.check(rows, bundles, econ=econ)
        self.assertEqual(result["incumbent_predecision_selected_bundle"], ["a"])
        self.assertEqual(result["review_selected_bundle"], [])
        self.assertIn("PARTNER_OUTSIDE_OPTION_WINS_OR_TIES:base:supplier",
                      result["outcomes"][1]["reasons"])

    def test_positive_supplier_with_booked_transfer_passes_conditionally(self):
        result = self.check()
        self.assertEqual(result["review_selected_bundle"], ["a"])
        self.assertEqual(result["review_worst_case_net_microUSD"], 50)
        self.assertFalse(result["native_catalog_admitted"])
        self.assertFalse(result["partner_contracts_executed"])
        self.assertFalse(result["observed_buyers"])
        self.assertIsNone(result["forecast_expected_net"])

    def test_unbooked_partner_transfer_refused_despite_positive_payoff(self):
        rows, bundles = [offer()], [["a"]]
        econ = {"base": economics(rows, bundles, compensation=150)}
        result = self.check(rows, bundles, econ=econ)
        self.assertEqual(result["review_selected_bundle"], [])
        self.assertIn("PARTNER_PAYMENT_NOT_IN_SELLER_COSTS:base:production",
                      result["outcomes"][1]["reasons"])

    def test_unknown_malformed_or_changed_receipt_fails_closed(self):
        rows, bundles = [offer()], [["a"]]
        variants = ("missing", "null", "boolean", "terms_changed", "package_changed")
        for variant in variants:
            with self.subTest(variant=variant):
                e = economics(rows, bundles)
                key = subset_key(["a"])
                if variant == "missing":
                    e = {}
                elif variant == "null":
                    e["supplier"][key]["own_cost"] = None
                elif variant == "boolean":
                    e["supplier"][key]["compensation"] = True
                elif variant == "terms_changed":
                    e["supplier"][key]["quote"]["a"]["terms_id"] = "unaccepted"
                else:
                    e["supplier"][subset_key(["b"])] = e["supplier"].pop(key)
                result = self.check(rows, bundles, econ={"base": e})
                self.assertEqual(result["review_selected_bundle"], [])
                self.assertTrue(result["outcomes"][1]["reasons"])

    def test_all_scenarios_including_adverse_partner_are_binding(self):
        rows, bundles = [offer()], [["a"]]
        scenarios = {"good": case(rows, bundles), "adverse": case(rows, bundles)}
        econ = {"good": economics(rows, bundles),
                "adverse": economics(rows, bundles, compensation=40, own_cost=60, outside=0)}
        result = self.check(rows, bundles, scenarios=scenarios, econ=econ)
        self.assertEqual(result["incumbent_predecision_selected_bundle"], ["a"])
        self.assertEqual(result["review_selected_bundle"], [])
        self.assertIn("PARTNER_OUTSIDE_OPTION_WINS_OR_TIES:adverse:supplier",
                      result["outcomes"][1]["reasons"])

    def test_multiple_partners_consume_shared_seller_cost_budget(self):
        rows = [offer("a", "buyer", "supplier1"), offer("b", "buyer", "supplier2")]
        bundles = [["a", "b"]]
        result = self.check(rows, bundles)
        self.assertEqual(result["incumbent_predecision_selected_bundle"], ["a", "b"])
        self.assertEqual(result["review_selected_bundle"], [])
        self.assertIn("PARTNER_PAYMENT_NOT_IN_SELLER_COSTS:base:production",
                      result["outcomes"][1]["reasons"])

    def test_no_partner_does_not_invent_supplier_obligation(self):
        rows = [offer(partner=None)]
        result = self.check(rows)
        self.assertEqual(result["review_selected_bundle"], ["a"])
        self.assertEqual(result["outcomes"][1]["partner_payoffs"]["base"], {})

    def test_no_entry_wins_tie_and_missing_scenario_is_error(self):
        rows, bundles = [offer()], [["a"]]
        scenarios = {"base": case(rows, bundles)}
        scenarios["base"]["collection_lower_bounds"]["a"] = 120
        result = self.check(rows, bundles, scenarios=scenarios)
        self.assertEqual(result["review_selected_bundle"], [])
        with self.assertRaisesRegex(ValueError, "ALL_REGISTERED_PARTNER_SCENARIOS_REQUIRED"):
            self.check(rows, bundles, scenarios=scenarios, econ={})

    def test_source_pin_fails_on_candidate_drift(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(len(pin_source()), 2)
        with tempfile.TemporaryDirectory() as temporary:
            tmp = Path(temporary)
            for relative in ("enterprise078/transactional_admission/choice.py",
                             "enterprise078/transactional_admission/planning.py"):
                target = tmp / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((root / relative).read_bytes())
            self.assertEqual(len(pin_source(tmp)), 2)
            (tmp / "enterprise078/transactional_admission/planning.py").write_bytes(
                (tmp / "enterprise078/transactional_admission/planning.py").read_bytes() + b"\\n#changed\\n"
            )
            with self.assertRaisesRegex(ValueError, "PARTNER_REVIEW_INCUMBENT_SOURCE_CHANGED"):
                pin_source(tmp)

    def test_no_input_mutation_and_no_native_ledger(self):
        rows, bundles = [offer()], [["a"]]
        scenarios = {"base": case(rows, bundles)}
        econ = {"base": economics(rows, bundles)}
        prior = copy.deepcopy((rows, bundles, scenarios, econ))
        result = self.check(rows, bundles, scenarios=scenarios, econ=econ)
        self.assertEqual((rows, bundles, scenarios, econ), prior)
        self.assertEqual(result["native_mutations"], 0)
        self.assertFalse(result["observed_partner_evidence"])


if __name__ == "__main__":
    unittest.main()
