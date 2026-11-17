"""Test-first commercial handoff. Synthetic counterparties are NOT real buyers/payments."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import tempfile
import time
import unittest

from frontier_omega.core import Reservoir, SHA
from connected_enterprise.alpha_economic.core import digest, identifier, sign
from connected_enterprise.alpha_economic.demo import example, instrument, ordinary
from connected_enterprise.alpha_economic.agents import AuthoredFixtureAgent
from connected_enterprise.alpha_economic.commerce import SimulatedBuyer
from connected_enterprise.alpha_economic.runtime import Engine, default_policy
from connected_enterprise.alpha_economic.frontier_bridge import (
    admission_preflight, submit_qualified, make_trial, bundle_shape
)

KEY = b"actual-buyer-key-must-be-external-and-confidential-fixture"
PROBLEM = "bounded-capacity-fulfillment"
BEFORE = "historical-pinned-agent-20261012"
AFTER = "claude-fable-52-20261109"
SEED = Path(__file__).resolve().parents[1] / "examples/frontier-omega/public-opportunities-20261116.json"


def old_instrument(c):
    return {"inputs": c["inputs"], "outputs": {"served": -1, "unserved": -1, "delivered_value": -1}}


def numeric(cost):
    return {
        "acquisition": 200_000, "research": 200_000, "construction": cost,
        "verification": 200_000, "delivery": 200_000, "support": 200_000,
        "maintenance": 200_000, "payment_fees": 200_000,
        "tax_provision": 200_000, "failure_recovery": 200_000
    }


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.reservoir = Reservoir(self.root / "reservoir")
        self.reservoir.seed(json.loads(SEED.read_text()))
        self.c = example(1)
        self.now = int(time.time())
        self.c["expires_at"] = self.now + 86400
        self.c["nonce"] = "actual-buyer-fixture-1"
        self.c["ordinary"] = ordinary()
        self.c["scope_key"] = PROBLEM
        self.c["purpose"] = "Construct a bounded digital capacity-fulfillment instrument with independently checked arithmetic."
        self.reservoir.add({
            "schema": "frontier-omega/problem/v1",
            "id": PROBLEM,
            "title": "Authored fixture for bounded capacity fulfillment",
            "beneficiary": "An explicitly synthetic buyer in a bounded test",
            "outcome": self.c["purpose"],
            "acceptance": "Frozen capacity-arithmetic test cases with a separate evaluator",
            "blocker": "An authored historical instrument fails the exact acceptance cases.",
            "tags": ["long-horizon-agents"],
            "demand": {"status": "HYPOTHESIS",
                       "basis": "Authored fixture with no customer consent or external demand.",
                       "ceiling_microUSD": None, "deadline": None,
                       "terms_sha256": None, "consent_verification": "NOT_VERIFIED"},
            "alternatives": [
                {"name": "Competent specialist", "route": "Known arithmetic algorithm",
                 "unknowns": "External labor and integration quotes not measured."},
                {"name": "Human-plus-AI", "route": "Expert using a conventional interpreter",
                 "unknowns": "No actual customer comparative costs measured."},
                {"name": "No purchase", "route": "Buyer declines the example",
                 "unknowns": "No external buyer exists in this test."}
            ],
            "source_urls": ["https://example.org/fixture"],
            "next_test": "Measure one finite host-replayed instrument before any commercial claim."
        })
        self.old = old_instrument(self.c)
        self.current = instrument()
        baseline = {
            "schema": "frontier-omega/capability/v1",
            "id": BEFORE, "title": "Pinned historical comparator fixture",
            "observed_on": "2026-10-12",
            "description": "Authored old method with a deliberate error, not a historical model capability.",
            "tags": ["long-horizon-agents"], "source_urls": ["https://example.org/fixture"],
            "availability": "REPORTED"
        }
        self.reservoir.add(baseline)
        self.envelope = sign({
            "kind": "request", "buyer": self.c["buyer"],
            "expires_at": self.c["expires_at"], "contract": self.c
        }, KEY)
        self.bundle = bundle_shape(PROBLEM, BEFORE, AFTER, self.envelope, self.old, self.current)
        self.engine = Engine(self.root / "engine", default_policy(),
                             AuthoredFixtureAgent({"capacity-fulfillment-v1": self.current}),
                             SimulatedBuyer({self.c["buyer"]: KEY}), {self.c["buyer"]: KEY})
        self.addCleanup(self.engine.close)

    def register(self):
        self.reservoir.add(make_trial(
            self.c, PROBLEM, BEFORE, "frozen-old", self.old,
            run_on="2026-11-16", costs_microUSD=numeric(13_000_000),
            acceptance_probability_bps=9500, scope="AUTHORED_SCENARIO"))
        self.reservoir.add(make_trial(
            self.c, PROBLEM, AFTER, "frozen-new", self.current,
            run_on="2026-11-16", costs_microUSD=numeric(2_000_000),
            acceptance_probability_bps=9500, scope="AUTHORED_SCENARIO"))

    def preflight(self):
        return admission_preflight(self.reservoir, self.bundle,
                                   {self.c["buyer"]: KEY}, now=self.now)

    def test_real_host_checker_replay_and_complete_simulated_successor_path(self):
        self.register()
        report = self.preflight()
        self.assertEqual(report["technical_scope"], "HOST_REPLAYED_FINITE_CASES")
        self.assertEqual(report["conversion_status"], "AUTHENTICATED_READY_FOR_ENGINE_INTAKE")
        self.assertFalse(report["actual_customer_established"])
        self.assertFalse(report["earned_revenue_established"])
        result = submit_qualified(self.engine, self.reservoir, self.bundle, now=self.now)
        self.assertEqual(result["job"], identifier(self.c))
        self.assertTrue(result["frontier_link_receipt"].is_file())
        self.assertEqual(self.engine.run(max_ticks=95)["actual_collections"], 0)
        self.assertEqual(self.engine.state.get(result["job"])["state"], "COMPLETE")
        self.assertTrue((self.engine.root / "outbox" / result["job"] / "solution.zip").is_file())
        self.assertTrue(self.engine.state.get(result["job"])["data"]["reinvestment"]["funding"] == "EARNED")
        self.assertEqual(self.engine.state.get(result["job"])["data"]["real_commerce"], False)

    def test_idempotent_replay_submits_one_work_order_and_one_link(self):
        self.register()
        first = submit_qualified(self.engine, self.reservoir, self.bundle, now=self.now)
        second = submit_qualified(self.engine, self.reservoir, self.bundle, now=self.now)
        self.assertEqual(first["job"], second["job"])
        self.assertEqual(len(self.engine.state.summary()["jobs"]), 1)
        self.assertEqual(len(list((self.engine.root / "frontier-links").glob("*.json"))), 1)

    def test_public_source_signal_without_trails_never_creates_paid_order(self):
        with self.assertRaisesRegex(ValueError, "MATCHED_REPORTED_CROSSING_REQUIRED"):
            submit_qualified(self.engine, self.reservoir, self.bundle, now=self.now)
        self.assertEqual(self.engine.state.summary()["jobs"], [])

    def test_signed_request_binding_rejects_forged_or_changed_buyer_terms(self):
        self.register()
        altered = copy.deepcopy(self.bundle)
        altered["buyer_envelope"]["body"]["contract"]["price_microUSD"] += 10000
        with self.assertRaisesRegex(ValueError, "AUTHENTICATION_FAILED"):
            admission_preflight(self.reservoir, altered, {self.c["buyer"]: KEY}, now=self.now)
        self.assertEqual(self.engine.state.summary()["jobs"], [])

    def test_old_and_new_evidence_hashes_are_reexecuted_not_accepted_on_faith(self):
        self.register()
        altered = copy.deepcopy(self.bundle)
        altered["current_instrument"]["outputs"]["served"] = 999
        with self.assertRaisesRegex(ValueError, "EVIDENCE_HASH_OR_CHECKER_MISMATCH"):
            admission_preflight(self.reservoir, altered, {self.c["buyer"]: KEY}, now=self.now)

    def test_failing_current_checker_is_refused_even_when_price_is_positive(self):
        self.register()
        altered = copy.deepcopy(self.bundle)
        altered["current_instrument"] = old_instrument(self.c)
        with self.assertRaises(ValueError):
            admission_preflight(self.reservoir, altered, {self.c["buyer"]: KEY}, now=self.now)

    def test_cost_only_crossing_is_distinguished_from_new_technical_capability(self):
        self.reservoir.add(make_trial(
            self.c, PROBLEM, BEFORE, "frozen-old", self.current,
            run_on="2026-11-16", costs_microUSD=numeric(13_000_000),
            acceptance_probability_bps=9500, scope="AUTHORED_SCENARIO"))
        self.reservoir.add(make_trial(
            self.c, PROBLEM, AFTER, "frozen-new", self.current,
            run_on="2026-11-16", costs_microUSD=numeric(2_000_000),
            acceptance_probability_bps=9500, scope="AUTHORED_SCENARIO"))
        altered = copy.deepcopy(self.bundle)
        altered["historical_instrument"] = self.current
        report = admission_preflight(self.reservoir, altered, {self.c["buyer"]: KEY}, now=self.now)
        self.assertEqual(report["crossing_mechanism"], "ECONOMIC_UNBLOCKING_REPORTED_COSTS")
        self.assertFalse(report["economic_crossing_established"])

    def test_changed_acceptance_cases_requires_frozen_registered_trial(self):
        self.register()
        altered = copy.deepcopy(self.bundle)
        c = altered["buyer_envelope"]["body"]["contract"]
        c["confirmation"][0]["expected"]["served"] = 9999
        altered["buyer_envelope"] = sign(altered["buyer_envelope"]["body"], KEY)
        with self.assertRaisesRegex(ValueError, "MATCHED_REPORTED_CROSSING_REQUIRED"):
            admission_preflight(self.reservoir, altered, {self.c["buyer"]: KEY}, now=self.now)

    def test_strong_current_alternative_must_pass_host_checker(self):
        altered = copy.deepcopy(self.bundle)
        c = altered["buyer_envelope"]["body"]["contract"]
        c["ordinary"] = self.old
        altered["buyer_envelope"] = sign(altered["buyer_envelope"]["body"], KEY)
        self.reservoir.add(make_trial(
            c, PROBLEM, BEFORE, "frozen-old", self.old,
            run_on="2026-11-16", costs_microUSD=numeric(13_000_000),
            acceptance_probability_bps=9500, scope="AUTHORED_SCENARIO"))
        self.reservoir.add(make_trial(
            c, PROBLEM, AFTER, "frozen-new", self.current,
            run_on="2026-11-16", costs_microUSD=numeric(2_000_000),
            acceptance_probability_bps=9500, scope="AUTHORED_SCENARIO"))
        with self.assertRaisesRegex(ValueError, "COMPETENT_ORDINARY_CONTROL_MUST_PASS"):
            admission_preflight(self.reservoir, altered, {self.c["buyer"]: KEY}, now=self.now)

    def test_exact_full_cost_envelope_required(self):
        self.register()
        data = self.reservoir.rows("trials")
        self.assertEqual(len(data), 2)
        # A newly registered trial using the same frozen protocol cannot be
        # silently substituted with lower costs or an optimistic price.
        with self.reservoir.tx() as db:
            db.execute("UPDATE trials SET body='{}' WHERE id='frozen-new'")
        with self.assertRaisesRegex(ValueError, "INTEGRITY"):
            admission_preflight(self.reservoir, self.bundle, {self.c["buyer"]: KEY}, now=self.now)

    def test_scenario_can_never_be_passed_as_a_real_financial_qualification(self):
        self.register()
        class ExternalStub:
            policy = {"scope": "EXTERNAL_LIVE"}
        external = ExternalStub()
        external.root = self.root / "external"
        with self.assertRaisesRegex(PermissionError, "SCENARIO_NOT_LIVE"):
            submit_qualified(external, self.reservoir, self.bundle,
                             buyer_keys={self.c["buyer"]: KEY}, now=self.now)

    def test_qualified_inbox_defers_until_frozen_replay_then_admits(self):
        from connected_enterprise.alpha_economic.frontier_intake import QualifiedInbox
        inbox = QualifiedInbox(self.engine, self.reservoir)
        request = inbox.inbox / "buyer-request.json"
        request.write_text(json.dumps(self.bundle))
        request.chmod(0o600)
        first = inbox.watch(interval=.05, cycles=1)
        self.assertEqual(first["receipts"][0]["status"], "DEFERRED_NOT_YET_QUALIFIED")
        self.assertTrue(request.exists())
        self.assertEqual(self.engine.state.summary()["jobs"], [])
        self.register()
        second = inbox.watch(interval=.05, cycles=1)
        self.assertEqual(second["receipts"][0]["status"], "ORDER_ADMITTED_NOT_PAID")
        self.assertFalse(request.exists())
        self.assertEqual(len(list(inbox.processed.iterdir())), 1)
        self.assertEqual(len(self.engine.state.summary()["jobs"]), 1)

    def test_qualified_inbox_rejects_forged_customer_signature(self):
        from connected_enterprise.alpha_economic.frontier_intake import QualifiedInbox
        self.register()
        inbox = QualifiedInbox(self.engine, self.reservoir)
        request = inbox.inbox / "forged.json"
        altered = copy.deepcopy(self.bundle)
        altered["buyer_envelope"]["signature"] = "f" * 64
        request.write_text(json.dumps(altered))
        request.chmod(0o600)
        receipts = inbox.watch(interval=.05, cycles=1)["receipts"]
        self.assertEqual(receipts[0]["status"], "REJECTED")
        self.assertEqual(self.engine.state.summary()["jobs"], [])
        self.assertEqual(len(list(inbox.rejected.iterdir())), 1)

    def test_qualified_inbox_refuses_world_readable_buyer_material(self):
        from connected_enterprise.alpha_economic.frontier_intake import QualifiedInbox
        self.register()
        inbox = QualifiedInbox(self.engine, self.reservoir)
        request = inbox.inbox / "not-private.json"
        request.write_text(json.dumps(self.bundle))
        request.chmod(0o644)
        status = inbox.scan()[0]["status"]
        self.assertEqual(status, "REFUSED_UNSAFE_FILE")
        self.assertEqual(self.engine.state.summary()["jobs"], [])

    def test_one_command_ignition_runs_sensor_intake_and_simulated_engine(self):
        from connected_enterprise.alpha_economic.frontier_intake import QualifiedInbox
        from connected_enterprise.alpha_economic.frontier_conversion_cli import ignite
        self.register()
        inbox = QualifiedInbox(self.engine, self.reservoir)
        request = inbox.inbox / "authorized.json"
        request.write_text(json.dumps(self.bundle))
        request.chmod(0o600)
        output = ignite(self.engine, self.reservoir, .05, cycles=120)
        self.assertEqual(output["financial_scope"], "SIMULATED")
        self.assertFalse(output["real_payment_established_by_ignition"])
        self.assertEqual(self.engine.state.get(identifier(self.c))["state"], "COMPLETE")
        self.assertEqual(output["engine"]["actual_collections"], 0)
        self.assertTrue((self.engine.root / "outbox" / identifier(self.c) / "solution.zip").exists())

    def test_reported_costs_below_engine_worst_case_are_refused(self):
        self.reservoir.add(make_trial(
            self.c, PROBLEM, BEFORE, "frozen-old", self.old,
            run_on="2026-11-16", costs_microUSD=numeric(13_000_000),
            acceptance_probability_bps=9500, scope="AUTHORED_SCENARIO"))
        self.reservoir.add(make_trial(
            self.c, PROBLEM, AFTER, "frozen-new", self.current,
            run_on="2026-11-16", costs_microUSD=numeric(500_000),
            acceptance_probability_bps=9500, scope="AUTHORED_SCENARIO"))
        with self.assertRaisesRegex(ValueError, "FULL_COST_UNDERSTATES"):
            self.preflight()

    def test_signed_purchase_with_unacceptable_outside_option_refused(self):
        self.register()
        altered = copy.deepcopy(self.bundle)
        c = altered["buyer_envelope"]["body"]["contract"]
        c["outside_option_microUSD"] = c["price_microUSD"] - 1
        altered["buyer_envelope"] = sign(altered["buyer_envelope"]["body"], KEY)
        with self.assertRaisesRegex(ValueError, "OUTSIDE_OPTION_LOSES"):
            admission_preflight(self.reservoir, altered, {self.c["buyer"]: KEY}, now=self.now)

    def test_customer_signs_request_then_independently_checks_delivered_bytes(self):
        from connected_enterprise.alpha_economic.frontier_buyer import (
            sign_request, sign_verified_delivery, verify_archive)
        from connected_enterprise.alpha_economic.delivery import package
        from connected_enterprise.alpha_economic.commerce import acceptance
        from connected_enterprise.alpha_economic.core import authenticate
        envelope = sign_request(self.c, KEY, now=self.now)
        self.assertEqual(
            authenticate(envelope, KEY, kind="request", now=self.now)["buyer"],
            self.c["buyer"])
        artifact = {
            "schema": "alpha-economic/artifact/v1",
            "contract_sha256": digest(self.c),
            "instrument": self.current,
            "provenance": {"kind": "AUTHORED_BUYER_FIXTURE_NOT_INDEPENDENT_CUSTOMER"}
        }
        receipt = package(self.c, artifact, self.root / "buyer-delivery")
        archive = (self.root / "buyer-delivery" / "solution.zip").read_bytes()
        result = verify_archive(archive, receipt, artifact, self.c)
        self.assertTrue(result["verified"])
        signed = sign_verified_delivery(
            self.c, artifact, receipt, archive, KEY, now=self.now)
        self.assertTrue(
            acceptance(signed, self.c, artifact, receipt, KEY, self.now)["accepted"])

    def test_buyer_fails_closed_on_modified_package_and_claimed_acceptance(self):
        from connected_enterprise.alpha_economic.frontier_buyer import (
            sign_verified_delivery)
        from connected_enterprise.alpha_economic.delivery import package
        artifact = {
            "schema": "alpha-economic/artifact/v1",
            "contract_sha256": digest(self.c),
            "instrument": self.current,
            "provenance": {"kind": "AUTHORED_FIXTURE"}
        }
        receipt = package(self.c, artifact, self.root / "buyer-delivery")
        archive = (self.root / "buyer-delivery" / "solution.zip").read_bytes()
        with self.assertRaisesRegex(ValueError, "PACKAGE_DIGEST_CHANGED"):
            sign_verified_delivery(
                self.c, artifact, receipt, archive[:-1] + b"x", KEY, now=self.now)
        changed_receipt = copy.deepcopy(receipt)
        changed_receipt["files"]["instrument.json"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "MANIFEST_CHANGED"):
            sign_verified_delivery(
                self.c, artifact, changed_receipt, archive, KEY, now=self.now)
        changed_artifact = copy.deepcopy(artifact)
        changed_artifact["instrument"]["outputs"]["served"] = 999
        with self.assertRaises(ValueError):
            sign_verified_delivery(
                self.c, changed_artifact, receipt, archive, KEY, now=self.now)
        with self.assertRaisesRegex(ValueError, "DEADLINE_EXPIRED"):
            sign_verified_delivery(
                self.c, artifact, receipt, archive, KEY,
                now=self.c["expires_at"])

    def test_buyer_refuses_checker_rejected_delivery_even_with_valid_archive(self):
        from unittest.mock import patch
        from connected_enterprise.alpha_economic.frontier_buyer import sign_verified_delivery
        from connected_enterprise.alpha_economic.delivery import package
        artifact = {
            "schema": "alpha-economic/artifact/v1",
            "contract_sha256": digest(self.c),
            "instrument": self.current,
            "provenance": {"kind": "AUTHORED_FIXTURE"}
        }
        receipt = package(self.c, artifact, self.root / "buyer-decision")
        archive = (self.root / "buyer-decision" / "solution.zip").read_bytes()
        with patch("connected_enterprise.alpha_economic.frontier_buyer.checker.verify",
                   return_value={"accepted": False}):
            with self.assertRaisesRegex(ValueError, "BUYER_CHECKER_REJECTED_DELIVERY"):
                sign_verified_delivery(
                    self.c, artifact, receipt, archive, KEY, now=self.now)

    def test_customer_owned_cli_generates_request_and_verified_acceptance(self):
        import os
        import subprocess
        import sys
        from connected_enterprise.alpha_economic.delivery import package
        from connected_enterprise.alpha_economic.commerce import acceptance
        folder = self.root / "buyer"
        folder.mkdir(mode=0o700)
        contract_path = folder / "contract.json"
        contract_path.write_text(json.dumps(self.c))
        archive_folder = folder / "delivery"
        artifact = {
            "schema": "alpha-economic/artifact/v1",
            "contract_sha256": digest(self.c),
            "instrument": self.current,
            "provenance": {"kind": "AUTHORED_FIXTURE"}
        }
        receipt = package(self.c, artifact, archive_folder)
        artifact_path = folder / "artifact.json"
        artifact_path.write_text(json.dumps(artifact))
        receipt_path = folder / "receipt.json"
        receipt_path.write_text(json.dumps(receipt))
        archive_path = archive_folder / "solution.zip"
        keyvar = "ALPHA_CUSTOMER_TEST_KEY"
        environment = dict(os.environ, **{keyvar: KEY.decode()})
        common = [
            sys.executable, "-m",
            "connected_enterprise.alpha_economic.frontier_buyer_cli",
            "--contract", str(contract_path), "--buyer-key-env", keyvar
        ]
        signed_request = folder / "buyer-request.json"
        proc = subprocess.run(common + ["request", "--output", str(signed_request)],
                              cwd=Path(__file__).resolve().parents[1], env=environment,
                              text=True, capture_output=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(signed_request.exists())
        self.assertEqual(signed_request.stat().st_mode & 0o077, 0)
        self.assertNotIn(KEY.decode(), proc.stdout)
        signed_delivery = folder / "buyer-acceptance.json"
        proc = subprocess.run(common + [
            "accept", "--artifact", str(artifact_path),
            "--receipt", str(receipt_path), "--archive", str(archive_path),
            "--output", str(signed_delivery)
        ], cwd=Path(__file__).resolve().parents[1], env=environment,
           text=True, capture_output=True, timeout=30)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        envelope = json.loads(signed_delivery.read_text())
        self.assertTrue(
            acceptance(envelope, self.c, artifact, receipt, KEY, self.now)["accepted"])

    def test_external_test_payment_protocol_is_wired_after_qualified_intake(self):
        """End to end through EXTERNAL_TEST, with authored fake provider receipts.

        Neither a real Stripe call nor an independent buyer or a live treasury
        is exercised. This checks gate sequencing, not actual money.
        """
        from unittest.mock import patch
        from test_alpha_economic_external_loop import ProtocolTreasury, ProtocolPayments
        from connected_enterprise.alpha_economic.agents import HarnessAgent
        from connected_enterprise.alpha_economic.commerce import HTTPBuyer
        from connected_enterprise.alpha_economic.live import LiveEngine
        self.reservoir.add(make_trial(
            self.c, PROBLEM, BEFORE, "frozen-old", self.old,
            run_on="2026-11-16", costs_microUSD=numeric(13_000_000),
            acceptance_probability_bps=9500, scope="OPERATOR_REPORTED_UNVERIFIED"))
        self.reservoir.add(make_trial(
            self.c, PROBLEM, AFTER, "frozen-new", self.current,
            run_on="2026-11-16", costs_microUSD=numeric(2_000_000),
            acceptance_probability_bps=9500, scope="OPERATOR_REPORTED_UNVERIFIED"))
        now = [self.now]
        policy = default_policy()
        policy.update(scope="EXTERNAL_TEST", opening_microUSD=0, startup_microUSD=0)
        agent = HarnessAgent({"kind": "harness", "runtime": {}, "routes": {}})
        buyer = HTTPBuyer(
            {self.c["buyer"]: "https://example.org"}, {self.c["buyer"]: KEY},
            enabled=True)
        simulated_counterparty = SimulatedBuyer({self.c["buyer"]: KEY})
        treasury, stripe = ProtocolTreasury(), ProtocolPayments()
        with patch.object(agent, "construct", return_value=(
                 self.current, {"scope": "AUTHORED_PROTOCOL_FIXTURE_NO_MODEL_INFERENCE"})), \
             patch.object(buyer, "quote", side_effect=simulated_counterparty.quote), \
             patch.object(buyer, "deliver", side_effect=simulated_counterparty.deliver), \
             patch.object(buyer, "payment", return_value={"received": True}):
            external = LiveEngine(
                self.root / "external-test", policy, agent, buyer,
                {self.c["buyer"]: KEY}, treasury, stripe,
                success_url="https://example.org/yes",
                cancel_url="https://example.org/no",
                authorized=True, clock=lambda: now[0])
            try:
                result = submit_qualified(
                    external, self.reservoir, self.bundle, now=self.now)
                with external.state.lock():
                    for _ in range(60):
                        stage = external.state.get(result["job"])["state"]
                        if stage == "SETTLED":
                            now[0] += 26 * 3600
                        if stage == "COMPLETE":
                            break
                        external.step()
                self.assertEqual(
                    external.state.get(result["job"])["state"], "COMPLETE")
                self.assertEqual(
                    [x[0] for x in treasury.operations
                     if x[0] in ("begin", "prepare", "release", "reinvest")],
                    ["begin", "prepare", "release", "reinvest"])
                self.assertFalse((external.root / "account").exists())
                report = external.report()
                self.assertEqual(report["scope"], "EXTERNAL_TEST")
                self.assertFalse(report["native_simulation_used"])
                self.assertEqual(result["actual_paid_customer_established"], False)
            finally:
                external.close()

    def test_buyer_decline_is_not_fake_revenue(self):
        self.register()
        self.engine.buyer.decline = True
        result = submit_qualified(self.engine, self.reservoir, self.bundle, now=self.now)
        output = self.engine.run(max_ticks=95)
        self.assertEqual(self.engine.state.get(result["job"])["state"], "DECLINED")
        self.assertEqual(output["native_summary"]["collections"], 0)
        self.assertEqual(output["actual_collections"], 0)


if __name__ == "__main__":
    unittest.main()
