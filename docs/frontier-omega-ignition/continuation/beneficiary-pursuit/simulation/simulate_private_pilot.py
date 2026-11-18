"""Offline commercial simulation against an exact checkout. Output contains no provider identifiers."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from unittest.mock import patch
from zipfile import ZipFile

REVISION = "a44aa8535e7899aa197d6e17f567e86547792536"
NAME = "Fictional Aster Imaging Lab (invented for simulation)"
START = datetime(2026, 11, 18, 15, 0, tzinfo=timezone.utc)
PRICE, FEE = 25000, 800
SCOPE = "One offline compatibility check on an authorized unsigned-byte input against both pinned conventional operators."
CRITERIA = "The transferred recipient must verify byte-identical output on the specified single-channel fixture."


def when(day):
    return START + timedelta(days=day)


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def stage_evidence(stage, event, files, temp, day):
    for kind in event["evidence"]:
        doc = {"simulation": True, "counterparty": NAME, "stage": stage, "evidence_role": kind,
               "modeled_day": day, "assumed_or_observed_terms": event["details"]}
        path = temp / f"synthetic-{stage}-{kind}.json"
        path.write_text(json.dumps(doc, sort_keys=True))
        files[kind] = path
        event["evidence"][kind] = {"source": "Invented exercise evidence: " + kind,
                                   "sha256": checksum(path.read_bytes())}


def simulate(source, output):
    real_sha = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if real_sha != REVISION:
        raise ValueError("An exact a44aa853 checkout is required.")
    product = source / "products/frontier-omega-ignition"
    subprocess.run(["git", "-C", str(source), "diff", "--quiet", REVISION, "--",
                    "products/frontier-omega-ignition", "products/alpha-genesis-harness/bridge"], check=True)
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(product))
    from ignition import commercial_handoff as journal
    from ignition import stripe_readonly as stripe
    from ignition.controller import Controller
    from ignition.store import Store

    with tempfile.TemporaryDirectory(prefix="explicit-fictional-pilot-") as private:
        temp = Path(private)
        opened = set()
        attempted_network = []
        def audit(event, args):
            if event == "sqlite3.connect":
                path = Path(args[0]).resolve()
                if not path.is_relative_to(temp):
                    raise RuntimeError("A simulation attempted to open a non-disposable journal.")
                opened.add(path)
            elif event in {"socket.connect", "socket.getaddrinfo"}:
                attempted_network.append(event)
                raise RuntimeError("External communication is forbidden in this simulation.")
        sys.addaudithook(audit)
        ctrl = Controller(Store(temp / "disposable-journal"))
        envelope = json.loads((product / "examples/scroll.json").read_bytes())
        mission = dict(envelope["mission"], beneficiary=NAME)
        rid, version = ctrl.create({"request_id": "synthetic-pilot-service", "mission": mission})
        state = ctrl.advance(rid, version)
        if state["status"] != "verified":
            raise RuntimeError(state.get("error"))
        data = ctrl.deliver(rid, version)
        with ZipFile(io.BytesIO(data)) as z:
            portable = temp / "recipient"
            z.extractall(portable)
        sample = temp / "self-authored.u8"
        sample.write_bytes(bytes([10] * 90 + [14] * 10))
        command = [sys.executable, "-IB", str(portable / "scroll_tool.py"), "verify", "--input", str(sample)]
        observed = json.loads(subprocess.check_output(command, cwd=portable))
        if not observed["passed"] or len(set(observed["sha256"].values())) != 1:
            raise RuntimeError("Actual recipient comparisons disagreed.")
        artifact_sha = checksum(data)
        ask = {"merchant": "acct_SyntheticMerchant", "customer": "cus_SyntheticBuyer",
               "payment_intent": "pi_SyntheticIntent", "charge": "ch_SyntheticCharge"}
        rows = [
            ("identified", 0, {"problem": "Fictional lab needs same-byte CPU compatibility on an owned test patch.",
                               "current_alternative": "Run the two pinned upstream implementations directly at no license fee.",
                               "contact_route": "Invented internal exercise; no recipient was contacted."}),
            ("validated", 1, {"acceptance_criteria": CRITERIA, "willingness_basis": "Assumed willingness for one paid pilot.",
                              "funding_basis": "Assumed fictional budget of USD 250.",
                              "rights": "Invented lab supplies its own input; the exercise uses only self-authored bytes."}),
            ("offered", 2, {"offer_id": "FICTIONAL-PILOT", "recipient": NAME, "amount": "250.00", "currency": "USD",
                            "terms": SCOPE, "acceptance_criteria": CRITERIA, "artifact_sha256": artifact_sha,
                            "stripe_parties_sha256": stripe.parties(ask)}),
            ("accepted", 4, {"decision_reference": "Simulated sign-off by fictional lab."}),
            ("delivered", 8, {"accepted_outcome": "Assumed lab acknowledgment; the comparison itself ran offline."})]
        for stage, day, details in rows:
            event = journal.template(ctrl.store, rid, version, stage)
            event.update(counterparty=NAME, reviewer="Simulation harness; no human representative.")
            event["details"].update(details)
            files = {}
            stage_evidence(stage, event, files, temp, day)
            with patch.object(journal, "timestamp", return_value=when(day).isoformat()):
                history = journal.record(ctrl, rid, version, event, files)
            if stage == "offered":
                offer_sha = history["history"][-1]["sha256"]
        assert history["collected_revenue"] is None
        charge_time = int(when(9).timestamp())
        available = int(when(12).timestamp())
        txn = dict(object="balance_transaction", id="txn_SyntheticCash", status="available", type="charge", balance_type="payments",
                   source=ask["charge"], currency="usd", amount=PRICE, exchange_rate=None, fee=FEE,
                   net=PRICE-FEE, created=charge_time, available_on=available)
        charge = dict(id=ask["charge"], object="charge", customer=ask["customer"], payment_intent=ask["payment_intent"],
                      status="succeeded", currency="usd", livemode=True, captured=True, paid=True, disputed=False, refunded=False,
                      amount=PRICE, amount_captured=PRICE, amount_refunded=0, transfer_data=None, on_behalf_of=None,
                      source_transfer=None, application_fee=None, application_fee_amount=None,
                      metadata={stripe.BINDING_KEY:offer_sha}, created=charge_time, balance_transaction=txn)
        class Response(io.BytesIO):
            status = 200
            def getheader(self, key):
                return "req_SyntheticResponse"
        with tempfile.TemporaryFile() as fake_key, patch.object(stripe.http.client, "HTTPSConnection") as transport, \
                patch.object(stripe.time, "time", return_value=available + 60), \
                patch.object(journal, "timestamp", return_value=(when(12)+timedelta(minutes=1)).isoformat()):
            fake_key.write(b"rk_" + b"live_SyntheticOnlyFixture\n")
            fake_key.seek(0)
            transport.return_value.getresponse.side_effect = [Response(json.dumps(obj).encode()) for obj in
                        ({"object":"account", "id":ask["merchant"]}, charge)]
            result = journal.reconcile_stripe(ctrl,rid,version,ask,fake_key.fileno(),0)
            retry = journal.reconcile_stripe(ctrl,rid,version,ask,fake_key.fileno(),0)
            assert len(transport.return_value.request.call_args_list) == 2 and retry == result
            assert all(x.args[0] == "GET" for x in transport.return_value.request.call_args_list)
        events = [item["event"]["stage"] for item in result["history"]]
        assert events == ["identified","validated","offered","accepted","delivered","paid"]
        paid = result["collected_revenue"]
        assert (paid["gross_minor"],paid["provider_fee_minor"],paid["available_net_minor"]) == (25000,800,24200)
        assert opened and not attempted_network
        public = {
            "schema":"frontier-ignition-commercial-simulation/1",
            "classification":"SIMULATED ONLY. No real demand, acceptance, payment, contract or prize decision.",
            "source_revision":REVISION,
            "private_pilot":{
                "counterparty":NAME, "scope":SCOPE, "incumbent":"Self-service using the freely available upstream operators.",
                "offer_assumption_usd":250, "fee_assumption_usd":8, "fee_provenance":"Illustrative assumption, not a Stripe quote.",
                "events":[{"stage":s,"day_after_start":d,"commercial_evidence":"fictional"} for s,d in zip(events,[0,1,2,4,8,12])],
                "working_artifact":{"type":"Offline scroll normalizer", "sha256":artifact_sha,
                   "measured_input":"100 self-authored bytes", "source_input_sha256":checksum(sample.read_bytes()),
                   "observed_output_sha256":observed["sha256"]["candidate"], "compared_arms": sorted(observed["sha256"]),
                   "outcome":"Three operator outputs matched byte for byte on the synthetic input."},
                "simulated_funds":{"currency":paid["currency"],"gross_minor":paid["gross_minor"],
                                   "assumed_fee_minor":paid["provider_fee_minor"],"net_before_fulfillment_costs_minor":paid["available_net_minor"],
                                   "bank_payout_verified":False,"real_cash_collected_minor":0,"net_profit":"unmeasured"},
                "limits":"The price, demand, buyer decisions, settlement and elapsed commercial days are assumptions. This run measures only software behavior.",
                "replay":"Second reconciliation returned the same receipt and journal length without another provider request."
            },
            "prize_no_award_case":{"mechanism":"Discretionary scientific competition, evaluated separately from any service sale.",
                "hypothesis":"Even after a hypothetical eligible submission, the sponsor selects another contribution.",
                "conditional_prize_usd":0, "real_submission":False, "real_adjudication_observed":False,
                "service_sale":False,"prize_probability":"unestimated", "real_cash_collected_usd":0},
            "isolation":{"sqlite_open_guard":"All SQLite connection paths were under one newly created temporary directory.",
                 "guarded_unique_local_sqlite_paths":len(opened), "production_journals_opened_by_simulator":0,
                 "simulated_transport_requests":2,"provider_requests_sent":0,"real_credentials_used":False,
                 "parent_process_socket_or_dns_attempts":len(attempted_network),"disposable_journal_removed_on_exit":True},
        }
    assert not temp.exists()
    output.write_text(json.dumps(public, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path)
    parser.add_argument("output", type=Path)
    args=parser.parse_args()
    simulate(args.checkout.resolve(), args.output.resolve())
