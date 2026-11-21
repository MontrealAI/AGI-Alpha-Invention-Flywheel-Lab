# SPDX-License-Identifier: Apache-2.0
"""LINKAGE218: fixed adversarial cases for evidence-first economic discovery.

All evidence and beneficiaries here are synthetic; never convert this fixture to
real buyer demand, genuine source provenance or a successful economic invention.
Owner economic_mission.py is imported unchanged.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from bridge.economic_mission import (
    citation_prompt, collect_next, confirm_citations, decide,
    discovery_prompt, discovery_schema, register,
)

OWNER_HEAD = "109bdcb4ec3d2309f23ba2c9ab3c96df530aada1"
OWNER_BLOB = "b9f1e647d8d3c4bf898888c0cd3b2a6ef9dee861"
# The semantic mismatch is intentionally manifest: an arithmetic sum does not
# test or create a clinic inventory service.
CALCULATION_GOAL = "Return the integer sum of input fields first and second."
PROPOSED_OUTCOME = "Create a verified clinic inventory replenishment service."
SOURCE_TEXT = {
    "one": (
        "Synthetic source one: weather stations record precipitation in millimeters. "
        "These figures alone provide no evidence of customers or clinic services."
    ),
    "two": (
        "Synthetic source two: astronomy telescopes record observations of distant stars. "
        "There is no vendor purchase commitment, contract or customer revenue."
    ),
}


class CaptureOnly:
    def __init__(self):
        self.runtime = SimpleNamespace(status=lambda: {"local_only": True})
        self.events = []

    def _event(self, state, name, receipt):
        self.events.append((name, receipt))

    def _save(self, state):
        pass


def source_input(name, text):
    return {
        "url": "https://synthetic.example.invalid/" + name,
        "label": "SYNTHETIC-NOT-PRIMARY-SOURCE " + name,
        "snapshot": {"body": text, "sha256": hashlib.sha256(text.encode()).hexdigest()},
    }


def make_state():
    cases = [
        {"input": {"first": 1, "second": 2}, "expected": {"sum": 3}},
        {"input": {"first": 2, "second": 3}, "expected": {"sum": 5}},
        {"input": {"first": 5, "second": 8}, "expected": {"sum": 13}},
    ]
    spec = {
        "objective": "Investigate a new useful enterprise activity, not an assigned calculator.",
        "context": "Consider any evidence-backed productive opportunities. No solution supplied.",
        "roles": {"researcher": {"provider": "local", "model": "fixture"}},
        "strategy": "single-model",
        "acceptance": {},
        "tool_permissions": ["construct_instrument"],
        "local_only": True,
        "economic_mission": {
            "beneficiary": "SYNTHETIC BUSINESS (no genuine customer)",
            "language": "en",
            "blind_discovery": True,
            "confirm_citations": True,
            "sources": {k: source_input(k, v) for k, v in SOURCE_TEXT.items()},
            "contracts": {
                "arithmetic": {
                    "goal": CALCULATION_GOAL, "source": "one",
                    "development": [cases[0]],
                    "qualification": cases[1:],
                }
            },
        },
    }
    state = {"spec": spec, "economic_mission": register(spec)}
    service = CaptureOnly()
    assert collect_next(service, state)
    assert collect_next(service, state)
    assert not collect_next(service, state)
    assert len(service.events) == 2
    return state


def first_proposals():
    fields = {
        "title": "A genuinely different service",
        "outcome": PROPOSED_OUTCOME,
        "constraint": "Lack inventory and buyer participation information",
        "alternative": "Existing enterprise software and capable human analyst",
        "experiment": "Independent clinic trial with accepted deliveries",
        "capture": "Unknown until voluntary purchasers pay",
        "source": "one",
        "quote": "Synthetic source one: weather stations record precipitation",
        "contract": None,
    }
    return {
        "opportunities": [
            fields,
            {**fields, "title": "Another unrelated productive idea",
             "outcome": "Improve a telescope calibration workflow",
             "source": "two",
             "quote": "Synthetic source two: astronomy telescopes record observations"},
            {**fields, "title": "A third unrelated productive idea",
             "outcome": "Investigate upstream quality of weather sensors",
             "quote": "Synthetic source one: weather stations record precipitation"},
        ],
        "selection": 0,
        "rationale": "SYNTHETIC illustration only, not a commercial recommendation.",
    }


def initial_state():
    state = make_state()
    early = decide(state, first_proposals())
    state["economic_mission"]["decision"] = early
    return state, early


def citations(*, primary_source="one", selected=0):
    return {
        "citations": [
            {"source": primary_source, "excerpt_index": 0, "contract": "arithmetic"},
            {"source": "two", "excerpt_index": 0, "contract": None},
            {"source": "one", "excerpt_index": 0, "contract": None},
        ],
        "selection": selected,
        "rationale": "Synthetic citation mapping deliberately not semantic.",
    }


class Linkage218(unittest.TestCase):
    counterexample_admitted = None
    def test_01_blind_no_contract_leak(self):
        state = make_state()
        prompt = discovery_prompt(state)
        schema = discovery_schema(state=state)
        self.assertNotIn(CALCULATION_GOAL, prompt)
        self.assertNotIn("[arithmetic]", prompt)
        self.assertNotIn("arithmetic", prompt)
        self.assertEqual(schema["properties"]["opportunities"]["items"]["properties"]["contract"],
                         {"type": "null"})
        initial = decide(state, first_proposals())
        self.assertIsNone(initial["selected"])

    def test_02_same_source_wrong_outcome_is_admitted(self):
        state, first = initial_state()
        self.assertIsNone(first["selected"])
        self.assertEqual(first["proposed_selection"], 0)
        self.assertIn(CALCULATION_GOAL, citation_prompt(state))
        decided = confirm_citations(state, citations())
        # This is a recorded COUNTEREXAMPLE to semantic match, NOT a passing
        # qualification of the economic outcome.
        self.assertEqual(decided["selected"], 0)
        type(self).counterexample_admitted = decided["selected"] == 0
        self.assertEqual(decided["disposition"], "admitted_to_test")
        self.assertTrue(decided["opportunities"][0]["registered_test"])
        self.assertTrue(decided["opportunities"][0]["quote_verified"])
        self.assertEqual(decided["opportunities"][0]["outcome"], PROPOSED_OUTCOME)

    def test_03_wrong_source_refusal(self):
        state, _ = initial_state()
        decided = confirm_citations(state, citations(primary_source="two"))
        self.assertIsNone(decided["selected"])
        self.assertEqual(decided["disposition"],
                         "selected_opportunity_lacks_source_or_registered_test")

    def test_04_explicit_abstention_remains_no_selection(self):
        state, _ = initial_state()
        decided = confirm_citations(state, citations(selected=None))
        self.assertIsNone(decided["selected"])
        self.assertEqual(decided["disposition"], "model_abstained")


def witness():
    import subprocess
    root = Path(__file__).resolve().parents[1]
    source = root / "bridge" / "economic_mission.py"
    blob = subprocess.check_output(
        ["git", "hash-object", str(source)], cwd=root, text=True).strip()
    if blob != OWNER_BLOB:
        raise ValueError("OWNER_SOURCE_IDENTITY_MISMATCH: review a new immutable version")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Linkage218)
    result = unittest.TestResult()
    suite.run(result)
    if not result.wasSuccessful() or result.testsRun != 4:
        raise AssertionError(f"Registered case failure: {result.errors!r}, {result.failures!r}")
    same_source_admitted = Linkage218.counterexample_admitted
    if type(same_source_admitted) is not bool:
        raise AssertionError("Missing result for preregistered semantic mismatch")
    return {
        "schema": "agi-alpha/omega-linkage218/v1",
        "owner_head": OWNER_HEAD,
        "owner_source_blob": blob,
        "preregistration": "research/omega-linkage218/PREREGISTRATION.md",
        "synthetic_only": True,
        "registered_cases_run": result.testsRun,
        "technical_source_id_refusal": "ACHIEVED",
        "blind_initial_contract_non_disclosure": "ACHIEVED",
        "semantic_outcome_to_test_linkage": "FAILED" if same_source_admitted else "NOT_FALSIFIED_ON_THIS_FIXTURE",
        "counterexample_admitted": same_source_admitted,
        "counterexample_selected_contract": "arithmetic" if same_source_admitted else None,
        "counterexample_proposed_outcome": PROPOSED_OUTCOME,
        "counterexample_tested_goal": CALCULATION_GOAL,
        "actual_beneficiary_value": None,
        "actual_customer_payment": None,
        "complete_cost_profit": None,
        "recursive_inventor_advantage": None,
        "usd3b_trailing365_profit_achieved": False,
        "decision": "HOLD / NO COMMERCIAL CLAIM / NO DEPLOY",
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == "--witness":
        result = witness()
        Path(sys.argv[2]).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
        print(json.dumps(result, sort_keys=True))
    else:
        unittest.main()
