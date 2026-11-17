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
        self.assertEqual(list((self.engine.root / "frontier-links").glob("*.json")).__len__(), 1)

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
            root = Path(self.root) if False else None
        external = ExternalStub()
        external.root = self.root / "external"
        with self.assertRaisesRegex(PermissionError, "SCENARIO_NOT_LIVE"):
            submit_qualified(external, self.reservoir, self.bundle,
                             buyer_keys={self.c["buyer"]: KEY}, now=self.now)

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
