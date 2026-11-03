"""Adversarial operating audit tests, separate from commercial confirmation.

The native fixture deliberately uses a losing development world and a small
registered acquisition policy. Its purpose is audit coverage, not demand or
annual-profit evidence. No external API, payment or account is used.
"""
import copy
from pathlib import Path
import shutil
import tempfile
import unittest

from commercial.ledger import digest
from connected_enterprise.finance import JournalAccount, audit_journal, source_paths_for_manifest
from experiments.commerce006 import PINS
from omega_savings import runner, service
from omega_savings.audit import _NativeEvidence, _OperatingReplay, operating_audit
from omega_savings.world import USD, make_rule


ROOT = Path(__file__).resolve().parents[1]


class SavingsOperatingAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="omega-audit-development-fixture-")
        cls.root = Path(cls.directory.name)
        for name in sorted(set(source_paths_for_manifest({"schema": service.SCHEMA})) | set(PINS)):
            target = cls.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        cls.registration = runner.registration(role="development", seeds=(12,), worlds=("adverse",),
            policies=("fixed_split",), fixed_fraction=0, cadence_days=30)
        case = cls.registration["cases"][0]
        cls.rule = make_rule(case["seed"], case["world"], technical=cls.registration["technical"])
        cls.manifest = service.prepare_manifest(cls.root, "omega_savings/deliveries/" + case["id"], rule=cls.rule)
        cls.state = runner._initial(case, cls.registration)
        with JournalAccount(cls.root, cls.manifest, cls.root / "private/account.sqlite",
                opening=100_000 * USD, working=0, contract="omega-saving-contracts-665b:" + case["id"]) as account:
            while cls.state["queue"]:
                event = cls.state["queue"].pop(0)
                intent = runner._prepare_intent(account, cls.state, event, cls.rule, cls.registration)
                runner._apply_intent(account, cls.state, intent, cls.root, cls.manifest, cls.rule, cls.registration)
                cls.state["processed"] += 1
            cls.public = account.export()
        # The operating check supplements this real independent native replay.
        if not audit_journal(cls.public, root=cls.root, manifest=cls.manifest)["accepted"]:
            raise AssertionError("native fixture failed")

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def audit(self, state=None, public=None, rule=None, registration=None):
        return operating_audit(self.state if state is None else state,
            self.public if public is None else public, self.rule if rule is None else rule,
            self.registration if registration is None else registration,
            root=self.root, manifest=self.manifest)

    def test_full_year_native_fixture_replays_independently(self):
        checked = self.audit()
        self.assertTrue(checked["accepted"])
        self.assertEqual(checked["native_actions_covered"], len(self.public["ledger"]["actions"]))
        self.assertEqual(checked["actual_artifacts_rechecked"], len(self.state["orders"]))
        self.assertEqual(checked["operating_hours"], [0, 8760])
        self.assertEqual(self.state["campaign_count"], 1)
        self.assertLess(self.state["year_summary"]["profit"], 0)
        self.assertGreater(len(self.state["corrections"]), 0)

    def test_self_consistent_inflated_selling_count_is_rejected(self):
        forged = copy.deepcopy(self.state)
        forged["stats"]["community"]["settled_units"] += 10000
        for decision in forged["decisions"]:
            if decision["observation"]["channel_stats"]["community"]["campaigns"]:
                decision["observation"]["channel_stats"]["community"]["settled_units"] += 10000
        with self.assertRaisesRegex(ValueError, "HISTORICAL_INFORMATION_CHANGED"):
            self.audit(state=forged)

    def test_rehashed_per_buyer_budget_forgery_is_rejected(self):
        state, public = copy.deepcopy(self.state), copy.deepcopy(self.public)
        order = state["orders"][0]
        order["budget"] += order["units"] * USD
        wallet = next(a for a in public["ledger"]["actions"] if a["op"] == "wallet")
        wallet["args"]["amount"] = order["budget"]
        # A hash attests bytes, not authority: this recomputation must not help.
        public["ledger"]["actions_sha256"] = digest(public["ledger"]["actions"])
        with self.assertRaisesRegex(ValueError, "NATIVE_EFFECT_OR_ORDER_CHANGED:wallet"):
            self.audit(state=state, public=public)

    def test_policy_action_cannot_be_replaced_after_observing_results(self):
        forged = copy.deepcopy(self.state)
        action = next(d["action"] for d in forged["decisions"] if d["action"]["action"] == "campaign")
        action["price_index"] = 2
        with self.assertRaisesRegex(ValueError, "DECISION_OR_HISTORICAL_INFORMATION_CHANGED"):
            self.audit(state=forged)

    def test_future_cash_cannot_enter_a_prior_policy_observation(self):
        forged = copy.deepcopy(self.state)
        forged["decisions"][0]["observation"]["available"] = self.public["ledger"]["summary"]["available"]
        self.assertNotEqual(forged["decisions"][0], self.state["decisions"][0])
        with self.assertRaisesRegex(ValueError, "HISTORICAL_INFORMATION_CHANGED"):
            self.audit(state=forged)

    def test_hidden_world_information_is_not_a_permitted_policy_input(self):
        forged = copy.deepcopy(self.state)
        forged["decisions"][0]["observation"]["seed"] = self.rule["seed"]
        with self.assertRaisesRegex(ValueError, "HISTORICAL_INFORMATION_CHANGED"):
            self.audit(state=forged)

    def test_contact_rights_or_exposures_cannot_be_invented_or_sold_twice(self):
        forged = copy.deepcopy(self.state)
        campaign = next(iter(forged["campaigns"].values()))
        campaign["units"] *= 2
        campaign["exposure"]["fresh"] *= 2
        with self.assertRaisesRegex(ValueError, "OPERATING_FIELD_CHANGED:campaigns"):
            self.audit(state=forged)

    def test_first_n_selection_and_hidden_partition_are_bound(self):
        forged = copy.deepcopy(self.state)
        lot = next(l for l in forged["lots"] if l["selected_units"])
        lot["selected_units"] += 1
        lot["members_sha256"] = digest(["fictional-extra-buyer"])
        with self.assertRaisesRegex(ValueError, "OPERATING_FIELD_CHANGED:lots"):
            self.audit(state=forged)

    def test_complete_cost_categories_cannot_be_reallocated_or_omitted(self):
        forged = copy.deepcopy(self.state)
        costs = forged["orders"][0]["cost_categories"]
        costs["production"] += costs.pop("verification")
        with self.assertRaisesRegex(ValueError, "OPERATING_FIELD_CHANGED:orders"):
            self.audit(state=forged)

    def test_unpaid_acquisition_cannot_support_contact_rights(self):
        public = copy.deepcopy(self.public)
        entry = next(e for e in public["connected_journal"]["entries"]
            if e["request"].get("kind") == "paid_contact_rights")
        entry["request"]["amount"] = 0
        public["connected_journal_sha256"] = digest(public["connected_journal"])
        with self.assertRaisesRegex(ValueError, "RESOURCE_REQUEST_CHANGED"):
            self.audit(public=public)

    def test_seed_funding_cannot_be_relabelled_as_earnings(self):
        forged = copy.deepcopy(self.state)
        forged["funded"][0]["funding"] = "EARNED"
        with self.assertRaisesRegex(ValueError, "OPERATING_FIELD_CHANGED:funded"):
            self.audit(state=forged)

    def test_phantom_orders_costs_and_tax_are_rejected(self):
        for field in ("orders", "costs", "taxes"):
            forged = copy.deepcopy(self.state)
            forged[field].append({"id": "phantom", "amount": 0})
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "OPERATING_FIELD_CHANGED:" + field):
                self.audit(state=forged)

    def test_exact_capital_and_trailing_year_are_required(self):
        for key, value in (("opening_microUSD", 1_000_000 * USD),
                           ("operating_hours", [0, 17520]),
                           ("settlement_end_hour", 17520)):
            registration = copy.deepcopy(self.registration)
            registration[key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                self.audit(registration=registration)

    def test_incomplete_history_cannot_be_reported_as_qualified_year(self):
        forged = copy.deepcopy(self.state)
        forged["pending"] = {"event": {"kind": "settle", "hour": 10}}
        with self.assertRaisesRegex(ValueError, "COMPLETE_SETTLED_OPERATING_RUN_REQUIRED"):
            self.audit(state=forged)

    def test_actual_native_postcollection_claim_defers_and_retries_same_hour(self):
        """A targeted native transaction, not an additional commercial world."""
        job_id = self.state["orders"][0]["job"]
        _, contract = service.contract_for(self.root, self.manifest, job_id)
        totals = service.totals(contract)
        order_id = "targeted-claim-order"
        state = runner._initial(self.registration["cases"][0], self.registration)
        state.update(built=True, capability=1, queue=[], next_serial=0)
        state["campaigns"]["targeted-campaign"] = {"channel": "community", "price_index": 1}
        state["stats"]["community"]["by_price"]["1"] = {"net": 0, "contacts": 20}
        state["orders"] = [{"order": order_id, "units": totals["units"],
            "price": totals["price_microUSD"], "campaign": "targeted-campaign"}]
        due = contract["collection_delay_hours"]
        # This ordinary scheduled decision has priority over the same-hour
        # later-created resolution event, reproducing the identified defect.
        runner._schedule(state, {"kind": "decision", "hour": due + 216, "cycle": (due + 216) // 720})
        runner._schedule(state, {"kind": "claim", "hour": due + 168, "order": order_id})
        initial = copy.deepcopy(state)
        with JournalAccount(self.root, self.manifest, self.root / "targeted-claim-private/account.sqlite",
                opening=100_000 * USD, working=0, contract="targeted-claim-native-unit-test") as account:
            outcome = service.fulfill(account, self.root, self.manifest, job_id,
                order_id=order_id, buyer="targeted-claim-buyer", hour=0)
            self.assertEqual(outcome["status"], "released")
            prefix = len(account.export()["ledger"]["actions"])
            for kind in ("claim", "decision", "resolve_claim"):
                event = state["queue"].pop(0)
                self.assertEqual(event["kind"], kind)
                intent = runner._prepare_intent(account, state, event, self.rule, self.registration)
                runner._apply_intent(account, state, intent, self.root, self.manifest, self.rule, self.registration)
                if kind == "decision":
                    self.assertEqual(intent["action"], {"action": "wait", "reason": "unresolved_native_payables"})
                    self.assertTrue(state["deferred_for_obligations"])
                    self.assertGreater(account.snapshot()["summary"]["payables"], 0)
            record = account.export()
        self.assertTrue(audit_journal(record, root=self.root, manifest=self.manifest)["accepted"])
        self.assertFalse(state["deferred_for_obligations"])
        self.assertEqual(record["ledger"]["summary"]["payables"], 0)
        self.assertEqual(len(state["queue"]), 1)
        self.assertEqual(state["queue"][0]["kind"], "decision")
        self.assertEqual(state["queue"][0]["hour"], due + 216)
        self.assertEqual(state["claims"][0]["paid"], totals["price_microUSD"] // totals["units"] // 10 * totals["units"])
        # Independently consume the exact claim/decision/payment prefix using
        # only the native before/after evidence and the preexisting state.
        replay = _OperatingReplay(state, record, self.rule, self.registration, self.root, self.manifest)
        replay.s, replay.native.cursor = copy.deepcopy(initial), prefix
        for kind in ("claim", "decision", "resolve_claim"):
            event = replay.s["queue"].pop(0)
            self.assertEqual(event["kind"], kind)
            getattr(replay, kind)(event)
        self.assertEqual(replay.s, state)
        self.assertEqual(replay.native.cursor, len(record["ledger"]["actions"]))
        self.assertEqual(len([a for a in record["ledger"]["actions"][prefix:] if a["op"] == "resolve_claim"]), 1)
        # Changing the disputed amount and recomputing the tape digest cannot
        # turn another claim into the predeclared per-buyer tenth-price claim.
        forged = copy.deepcopy(record)
        forged["ledger"]["actions"][prefix]["args"]["amount"] += 1
        forged["ledger"]["actions_sha256"] = digest(forged["ledger"]["actions"])
        replay = _OperatingReplay(state, forged, self.rule, self.registration, self.root, self.manifest)
        replay.s, replay.native.cursor = copy.deepcopy(initial), prefix
        with self.assertRaisesRegex(ValueError, "NATIVE_EFFECT_OR_ORDER_CHANGED:claim"):
            replay.claim(replay.s["queue"].pop(0))


class TaxPrefixUnitCases(unittest.TestCase):
    """Small authored prefixes test tax logic, not financial qualification."""
    def fixture(self, paid=100 * USD):
        before = {"profit": 400 * USD, "expenses": 0, "expensePaid": 0,
                  "available": 1000 * USD, "cash": 1000 * USD}
        after = {"profit": 300 * USD, "expenses": 100 * USD,
                 "expensePaid": paid, "available": 1000 * USD - paid,
                 "cash": 1000 * USD - paid}
        action = {"seq": 0, "day": 5, "op": "cost",
                  "args": {"id": "tax:first", "amount": 100 * USD},
                  "before": before, "after": after}
        replay = object.__new__(_OperatingReplay)
        replay.native = _NativeEvidence({"ledger": {"actions": [action], "summary": after},
                                          "connected_journal": {"entries": []}})
        replay.s, replay.tax_assessed = {"costs": [], "taxes": []}, 0
        return replay

    def test_tax_assessment_payment_reserve_and_highwater_are_separate(self):
        replay = self.fixture()
        replay.tax("first", 5)
        self.assertEqual(replay.s["taxes"], [{"id": "tax:first", "hour": 5,
            "expense": 100 * USD, "cash_payment": 100 * USD, "reserve_unpaid": 0}])
        # Adding paid tax back recovers the original high water, not new profit.
        replay.tax("second", 5)
        self.assertEqual(len(replay.s["taxes"]), 1)

    def test_unpaid_tax_is_not_permitted_by_immediate_payment_schedule(self):
        replay = self.fixture(paid=0)
        with self.assertRaisesRegex(ValueError, "EXPENSE_NOT_FULLY_PAID"):
            replay.tax("first", 5)

    def test_twelve_simultaneous_maturities_follow_native_lexical_export_order(self):
        # order-10 precedes order-2 in the native export. A fixture of only two
        # orders would fail to expose an insertion-order operating replayer.
        replay = object.__new__(_OperatingReplay)
        replay.s = {"orders": [{"order": "order-" + str(i), "native_outcome": "release"}
                               for i in range(12)]}
        replay.order_terms = {o["order"]: {"maturity_day": 10} for o in replay.s["orders"]}
        replay.matured = set()
        summary = {"cash": 1000, "revenue": 100, "profit": 50, "expenses": 50}
        actions = [{"seq": i, "day": 11, "op": "mature",
                    "args": {"id": ident, "event_id": "maturity:" + ident + ":" + digest(replay.order_terms[ident])[:20]},
                    "before": copy.deepcopy(summary), "after": copy.deepcopy(summary)}
                   for i, ident in enumerate(sorted(replay.order_terms))]
        replay.native = _NativeEvidence({"ledger": {"actions": actions, "summary": summary},
                                          "connected_journal": {"entries": []}})
        replay.advance(10)  # Claim boundary is inclusive.
        self.assertEqual(replay.native.cursor, 0)
        replay.advance(11)
        self.assertEqual(replay.native.cursor, 12)
        self.assertEqual(replay.matured, set(replay.order_terms))


if __name__ == "__main__":
    unittest.main()
