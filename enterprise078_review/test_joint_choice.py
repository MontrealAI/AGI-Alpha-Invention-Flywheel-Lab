import shutil
import tempfile
import unittest
from pathlib import Path

from enterprise078.transactional_admission.offer import COSTS
from enterprise078_review.joint_choice import INCUMBENT, pinned_source, review, subset_key


def offer(name, buyer="buyer", partner=None):
    return {"id": name, "buyer": buyer, "price": 200, "collected": 200,
            "value": 500, "outside": 100, "response": "consented",
            "accepted": True, "partner": partner,
            "costs": {k: (50 if k == "production" else 0) for k in COSTS}}


def utility(value, *, human=100, ai=70, self_service=50, none=0):
    return {"joint_value": value,
            "outside": {"human": human, "competitor_ai": ai,
                        "self_service": self_service, "no_purchase": none}}


def case_for(rows, *, double_value=500, double_human=300,
             single_ai=70, paid=True, partner_status="accepted"):
    by_buyer = {}
    for row in rows:
        by_buyer.setdefault(row["buyer"], {})[subset_key([row["id"]])] = utility(
            500, ai=single_ai)
    if len(rows) == 2 and rows[0]["buyer"] == rows[1]["buyer"]:
        by_buyer[rows[0]["buyer"]][subset_key([r["id"] for r in rows])] = utility(
            double_value, human=double_human)
    return {"buyers": by_buyer,
            "collections": {r["id"]: (r["price"] if paid else 0) for r in rows},
            "consents": {r["id"]: True for r in rows},
            "acceptances": {r["id"]: True for r in rows},
            "partners": {r["partner"]: partner_status for r in rows if r.get("partner")}}


class RegisteredJointChoiceTests(unittest.TestCase):
    def evaluate(self, rows, bundles, scenarios, wallets=None):
        if wallets is None:
            wallets = {r["buyer"]: 500 for r in rows}
        return review(rows, bundles, wallets=wallets, available=1000,
                      earned=1000, sunk_acquisition=30, scenarios=scenarios)

    def test_substitute_outputs_incumbent_false_joint_win(self):
        rows = [offer("a"), offer("b")]
        result = self.evaluate(rows, [["a"], ["a", "b"]], {"normal": case_for(rows)})
        self.assertEqual(result["incumbent_selected_bundle"], ["a", "b"])
        self.assertEqual(result["robust_selected_bundle"], ["a"])
        self.assertEqual(result["robust_net_microUSD"], 120)
        self.assertIn("BUYER_PREFERS_OUTSIDE_OR_TIES:normal:buyer",
                      result["outcomes"][2]["reasons"])
        self.assertFalse(result["native_catalog_admitted"])
        self.assertFalse(result["paid_commerce"])

    def test_rival_price_response_reverses_singleton(self):
        rows = [offer("a"), offer("b")]
        result = self.evaluate(rows, [["a"], ["a", "b"]],
                               {"ordinary": case_for(rows),
                                "rival_price_war": case_for(rows, single_ai=310)})
        self.assertEqual(result["robust_selected_bundle"], [])
        self.assertIn("BUYER_PREFERS_OUTSIDE_OR_TIES:rival_price_war:buyer",
                      result["outcomes"][1]["reasons"])

    def test_distinct_buyers_can_keep_complete_offer(self):
        rows = [offer("a", "buyer_a"), offer("b", "buyer_b")]
        result = self.evaluate(rows, [["a"], ["b"], ["a", "b"]],
                               {"ordinary": case_for(rows)},
                               wallets={"buyer_a": 300, "buyer_b": 300})
        self.assertEqual(result["robust_selected_bundle"], ["a", "b"])
        self.assertEqual(result["robust_net_microUSD"], 270)
        self.assertFalse(result["native_catalog_admitted"])

    def test_unknown_joint_valuation_refuses_without_substitute_zero(self):
        rows = [offer("a"), offer("b")]
        state = case_for(rows)
        del state["buyers"]["buyer"][subset_key(["a", "b"])]
        result = self.evaluate(rows, [["a"], ["a", "b"]], {"no_joint_proof": state})
        self.assertEqual(result["robust_selected_bundle"], ["a"])
        self.assertIn("JOINT_VALUE_OR_OUTSIDE_UNESTABLISHED:no_joint_proof:buyer",
                      result["outcomes"][2]["reasons"])

    def test_unknown_competent_ai_outside_refuses(self):
        rows = [offer("a")]
        state = case_for(rows)
        del state["buyers"]["buyer"][subset_key(["a"])]["outside"]["competitor_ai"]
        result = self.evaluate(rows, [["a"]], {"no_ai_comparison": state})
        self.assertEqual(result["robust_selected_bundle"], [])
        self.assertIn("COMPLETE_OUTSIDE_OPTIONS_UNESTABLISHED:no_ai_comparison:buyer",
                      result["outcomes"][1]["reasons"])

    def test_nonpayment_downside_keeps_no_deploy(self):
        rows = [offer("a")]
        result = self.evaluate(rows, [["a"]], {"paid": case_for(rows),
                                                "nonpayment": case_for(rows, paid=False)})
        self.assertEqual(result["robust_selected_bundle"], [])
        self.assertEqual(result["outcomes"][1]["robust_net_microUSD"], -80)

    def test_partner_refusal_not_assumed_away(self):
        rows = [offer("a", partner="channel_partner")]
        result = self.evaluate(rows, [["a"]], {"no_contract": case_for(rows, partner_status="refused")})
        self.assertEqual(result["robust_selected_bundle"], [])
        self.assertIn("PARTNER_PARTICIPATION_UNESTABLISHED:no_contract",
                      result["outcomes"][1]["reasons"])

    def test_source_drift_refuses_without_editing_owner_source(self):
        original = Path(__file__).resolve().parents[1]
        self.assertEqual(pinned_source(), INCUMBENT)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in INCUMBENT:
                dst = root / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original / name, dst)
            self.assertEqual(pinned_source(root), INCUMBENT)
            p = root / "enterprise078/transactional_admission/intent.py"
            p.write_bytes(p.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "INCUMBENT_SOURCE_CHANGED_REQUALIFY"):
                pinned_source(root)

    def test_no_fabricated_worlds(self):
        with self.assertRaisesRegex(ValueError, "REGISTERED_SCENARIOS_REQUIRED"):
            self.evaluate([offer("a")], [["a"]], {})


if __name__ == "__main__":
    unittest.main()
