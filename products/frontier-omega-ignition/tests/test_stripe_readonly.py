"""Provider I/O is mocked. Every journal is a disposable synthetic workspace."""
import copy
from datetime import datetime
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ignition import commercial_handoff as journal
from ignition import stripe_readonly as stripe
from ignition.controller import Controller
from ignition.pursuit import _run_key, pursue
from ignition.store import Conflict, StateError, Store


class ReadOnlyStripe(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.ctrl = Controller(Store(root / "synthetic-only"))
        src = Path(__file__).resolve().parents[1] / "examples/evidence_action.json"
        self.pursuit_id = "synthetic-stripe-test"
        brief = src.read_bytes()
        self.rid, self.version = self.ctrl.create({"request_id": _run_key(self.pursuit_id, "fixture"),
                                                  "mission": json.loads(brief)["mission"]})
        (root / "mission.json").write_bytes(brief)
        candidate = {"id":"fixture", "mission_file":"mission.json", "counterparty":"Synthetic counterparty",
                     "problem":"Fixture problem", "current_alternative":"Fixture alternative", "contact_route":"Fixture",
                     "source":"https://example.invalid/fixture", "observed_on":"2026-11-18", "rights":"Self-authored fixture",
                     "value_and_uncertainty":"Unknown outside this test", "proof_order":1}
        self.plan = root / "test.shortlist"
        self.plan.write_text(json.dumps({"purpose":"Synthetic pursuit", "selection_basis":"Fixture order",
                                         "candidates":[candidate, dict(candidate, id="unreached", proof_order=2)]}))
        self.ctrl.advance(self.rid, self.version)
        self.parties = {"merchant": "acct_FixtureMerchant", "customer": "cus_FixtureBuyer",
                        "payment_intent": "pi_FixtureIntent"}
        self.request = dict(self.parties, charge="ch_FixtureCharge")
        for stage in ("identified", "validated", "offered", "accepted", "delivered"):
            event = journal.template(self.ctrl.store, self.rid, self.version, stage)
            event.update(counterparty="Synthetic counterparty", reviewer="Fixture")
            for key, value in event["details"].items():
                if not value:
                    event["details"][key] = "Fixture " + key
            if stage == "offered":
                event["details"].update(amount="12.40", currency="CAD", stripe_parties_sha256=stripe.parties(self.parties),
                                        artifact_sha256=hashlib.sha256(self.ctrl.deliver(self.rid, self.version)).hexdigest())
            files = {}
            for kind in event["evidence"]:
                source = root / kind
                source.write_text("TEST FIXTURE " + kind)
                event["evidence"][kind].update(source="Synthetic " + kind, sha256=hashlib.sha256(source.read_bytes()).hexdigest())
                files[kind] = source
            record = journal.record(self.ctrl, self.rid, self.version, event, files)
            if stage == "offered":
                self.offer = record["history"][-1]
        after = math.ceil(datetime.fromisoformat(self.offer["recorded_at"]).timestamp()) + 1
        clock = patch.object(stripe.time, "time", return_value=after + 86400)
        clock.start()
        self.addCleanup(clock.stop)
        self.charge = dict(id=self.request["charge"], object="charge", customer=self.request["customer"],
                           payment_intent=self.request["payment_intent"], created=after, status="succeeded",
                           currency="cad", livemode=True, captured=True, paid=True, disputed=False, refunded=False,
                           amount=1240, amount_captured=1240, amount_refunded=0, transfer_data=None,
                           on_behalf_of=None, source_transfer=None, application_fee=None, application_fee_amount=None,
                           metadata={stripe.BINDING_KEY: self.offer["sha256"]},
                           billing_details={"email":"sensitive-fixture@example.invalid"},
                           balance_transaction=dict(object="balance_transaction", id="txn_Fixture", status="available",
                                                    created=after, available_on=after+86400, type="charge",
                                                    balance_type="payments", source=self.request["charge"],
                                                    currency="cad", amount=1240, exchange_rate=None, fee=66, net=1174))

    def invoke(self, request=None, sequence=0):
        return journal.reconcile_stripe(self.ctrl, self.rid, self.version, self.request if request is None else request,
                                        999, sequence)

    def test_fixture_transition_is_private_and_idempotent(self):
        with patch.object(stripe, "observe", return_value=(self.charge, ["f" * 64, "e" * 64])) as provider:
            state = self.invoke()
            self.assertEqual(state["commercial_state"], "paid")
            receipt = state["collected_revenue"]
            self.assertEqual([receipt[k] for k in ("currency","gross_minor","provider_fee_minor","available_net_minor")],
                             ["CAD", 1240, 66, 1174])
            self.assertFalse(receipt["bank_payout_verified"])
            self.assertEqual(state, self.invoke())
            provider.assert_called_once()
            with self.assertRaises(Conflict):
                self.invoke(dict(self.request, charge="ch_Other"))
        contents = self.ctrl.store.db.read_bytes()
        for secret in (*self.request.values(), "txn_Fixture", "sensitive-fixture@example.invalid"):
            self.assertNotIn(secret.encode(), contents)

    def test_all_unverified_conditions_fail_without_recording_paid(self):
        defects = {"livemode":False, "captured":False, "refunded":True, "disputed":True, "status":"failed",
                   "amount_captured":1, "amount_refunded":1, "customer":"cus_Other", "currency":"usd", "paid":1,
                   "metadata":{}, "id":"ch_Other", "amount":10, "transfer_data":{"destination":"acct_Other"},
                   "on_behalf_of":"acct_Other", "application_fee":"fee_Fixture", "payment_intent":"pi_NotEnrolled",
                   "created":math.floor(datetime.fromisoformat(self.offer["recorded_at"]).timestamp()) - 1}
        for key, value in defects.items():
            changed = dict(self.charge, **{key:value})
            with self.subTest(key=key), patch.object(stripe, "observe", return_value=(changed, [])), self.assertRaises(StateError):
                self.invoke()
        for key, value in {"status":"pending", "source":"ch_Other", "fee":-1, "net":1240, "exchange_rate":1,
                           "amount":10, "available_on":self.charge["created"] + 86401,
                           "created":self.charge["created"] - 1, "balance_type":"issuing", "currency":"usd",
                           "type":"transfer"}.items():
            changed = copy.deepcopy(self.charge)
            changed["balance_transaction"][key] = value
            with self.subTest(key=key), patch.object(stripe, "observe", return_value=(changed, [])), self.assertRaises(StateError):
                self.invoke()
        self.assertIsNone(journal.status(self.ctrl.store, self.rid, self.version)["collected_revenue"])
        with patch.object(stripe, "observe", side_effect=AssertionError("attempted unauthorized read")):
            with self.assertRaises(Conflict):
                self.invoke(dict(self.request, merchant="acct_Other"))
            self.ctrl.store.set_operation(self.rid, self.version, "pause")
            with self.assertRaises(Conflict):
                self.invoke()
            self.ctrl.store.set_operation(self.rid, self.version, "resume")
            with self.assertRaises(Conflict):
                self.invoke()

    def test_pause_during_read_and_duplicate_transaction_roll_back(self):
        def interrupt(*_):
            self.ctrl.store.set_operation(self.rid, self.version, "pause")
            self.ctrl.store.set_operation(self.rid, self.version, "resume")
            return self.charge, []
        with patch.object(stripe, "observe", side_effect=interrupt), self.assertRaises(Conflict):
            self.invoke()
        with self.ctrl.store.connection() as db:
            db.execute("CREATE TABLE ignition_stripe_claims(charge_sha256 TEXT PRIMARY KEY, transaction_sha256 TEXT UNIQUE)")
            tx = stripe.reconcile_charge(self.charge, self.request, self.offer)["balance_transaction_fingerprint"]
            db.execute("INSERT INTO ignition_stripe_claims VALUES(?,?)", ("another charge fingerprint", tx))
        with patch.object(stripe, "observe", return_value=(self.charge, [])), self.assertRaises(Conflict):
            self.invoke(sequence=2)
        self.assertIsNone(journal.status(self.ctrl.store, self.rid, self.version)["collected_revenue"])

    def test_transport_only_reads_current_merchant_and_one_charge(self):
        class Response(io.BytesIO):
            status = 200
            def getheader(self, _):
                return "req_Fixture"
        account = {"id":self.request["merchant"], "object":"account"}
        with tempfile.TemporaryFile() as fd, patch.object(stripe.http.client, "HTTPSConnection") as connection:
            fd.write(b"rk_" + b"live_SyntheticOnlyFixture\n")
            fd.seek(0)
            conn = connection.return_value
            conn.getresponse.side_effect = [Response(json.dumps(v).encode()) for v in (account, self.charge)]
            observed, trace = stripe.observe(self.request, fd.fileno(), lambda: None)
            self.assertEqual(observed, self.charge)
            self.assertEqual(len(trace), 2)
            self.assertEqual([c.args[:2] for c in conn.request.call_args_list],
                             [("GET","/v1/account"), ("GET","/v1/charges/ch_FixtureCharge?expand%5B%5D=balance_transaction")])
            self.assertEqual(connection.call_args.args[0], "api.stripe.com")
            fd.seek(0)
            conn.getresponse.side_effect = [Response(b'{"object":"account","id":"acct_Other"}')]
            with self.assertRaises(StateError):
                stripe.observe(self.request, fd.fileno(), lambda: None)
            fd.seek(0)
            fd.truncate()
            fd.write(b"rk_" + b"test_SyntheticOnlyFixture\n")
            fd.seek(0)
            with self.assertRaises(StateError):
                stripe.observe(self.request, fd.fileno(), lambda: None)
            self.assertEqual(conn.request.call_count, 3)

    def test_pursuit_projects_only_the_existing_missions_observation(self):
        def run():
            return pursue(self.ctrl, self.plan, self.pursuit_id)
        before = run()
        self.assertEqual(before["result"], "existing_commercial_engagement")
        self.assertIsNone(before["collected_revenue"])
        with patch.object(stripe, "observe", return_value=(self.charge, ["f"*64, "e"*64])) as provider:
            paid = self.invoke()
            after = run()
            self.assertEqual(after["result"], "existing_commercial_engagement")
            self.assertEqual(len(after["attempts"]), 1)
            self.assertEqual(after["attempts"][0]["commercial_state"], "paid")
            self.assertEqual(after["attempts"][0]["next_action"], paid["next_action"])
            self.assertEqual(after["collected_revenue"], {**paid["collected_revenue"],
                             "candidate":"fixture", "mission_id":self.rid, "version":self.version})
            self.assertEqual(after, run())
            self.assertEqual(len(journal.status(self.ctrl.store, self.rid, self.version)["history"]), 6)
            provider.assert_called_once()

    def test_currency_precision(self):
        self.assertEqual(stripe.minor_amount("12.4", "CAD"), 1240)
        self.assertEqual(stripe.minor_amount("123.00", "JPY"), 123)
        for value, currency in (("0.111","USD"), ("0.1","JPY"), ("1.00","XYZ")):
            with self.assertRaises(StateError):
                stripe.minor_amount(value, currency)


if __name__ == "__main__":
    unittest.main()
