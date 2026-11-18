import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ignition import pursuit, selection
from ignition.controller import Controller
from ignition.store import PRODUCT, StateError, Store, canonical


class SelectionTest(unittest.TestCase):
    def setUp(self):
        self.path = PRODUCT / "examples/public-research-ranked.shortlist"
        self.plan = pursuit.read_shortlist(self.path)
        self.scroll, self.issue, self.quantum = self.plan["candidates"]

    def test_rank_and_screen_are_independent_of_input_order(self):
        order = selection.select(self.plan)
        self.assertEqual(order["ranked"], ["quantum", "scroll"])
        self.assertEqual(order["assessments"][-1]["candidate"], "expensify")
        self.assertTrue(all(row["estimated_net_usd_cents"] is None for row in order["assessments"]))
        self.plan["candidates"].reverse()
        self.assertEqual(selection.select(self.plan), order)

    def test_financial_bounds_can_change_rank_or_withhold(self):
        p = self.scroll["assessment"]
        # Arithmetic test using illustrative estimates. These are never loaded by the live portfolio.
        p.update(conditional_receipt_usd_cents=[1001, 1200], collection_probability_bps=[1000, 5000],
                 full_expected_cost_usd_cents=[10, 11])
        report = selection.select(self.plan)
        self.assertEqual(report["ranked"], ["scroll", "quantum"])
        self.assertEqual(report["assessments"][0]["estimated_net_usd_cents"], [89, 590])
        p["full_expected_cost_usd_cents"] = [601, 700]
        self.assertEqual(selection.select(self.plan)["ranked"], ["quantum"])

    def test_missing_or_expensive_grant_screens_before_construction(self):
        self.scroll["brief"]["mission"]["authority"]["public_sources"] = False
        self.quantum["assessment"]["requires_new_spending"] = True
        with tempfile.TemporaryDirectory() as folder:
            ctrl = Controller(Store(Path(folder) / "state"))
            with patch.object(pursuit, "read_shortlist", return_value=self.plan), patch.object(ctrl, "create") as build:
                receipt = pursuit.pursue(ctrl, self.path, "no-authority")
            build.assert_not_called()
            self.assertEqual(receipt["attempts"], [])
            self.assertEqual(receipt["selection"]["ranked"], [])
            self.assertIn("public-source grant", canonical(receipt["selection"]))

    def test_invalid_bounds_and_missing_brief_fail_before_registering(self):
        for profile in ({"collection_probability_bps": [0, 10001]}, {"full_expected_cost_usd_cents": [False, 12]},
                        {"days_to_collection": [3, 2]}, {"sources": []}):
            plan = copy.deepcopy(self.plan)
            plan["candidates"][0]["assessment"].update(profile)
            with self.assertRaises(StateError):
                selection.select(plan)
        del self.quantum["brief"]
        with self.assertRaisesRegex(StateError, "executable mission"):
            selection.select(self.plan)
