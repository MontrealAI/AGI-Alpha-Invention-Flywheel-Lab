# SPDX-License-Identifier: Apache-2.0
"""Integration and authority tests for the callable GENESIS NEXT workflow."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.adapters import BridgeError
from bridge.genesis_next import (CANDIDATE_SOURCE, EvidenceIndex, GenesisNextService, construct_candidate,
                                 demonstrate, load_candidate, select_experiments)
from bridge.workflow_demo import FixtureRuntime, instrument
from bridge.workflows import WorkflowService


class GenesisServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workflows = WorkflowService(FixtureRuntime([]), self.root / "workspace")
        self.service = GenesisNextService(self.workflows)

    def tearDown(self):
        self.workflows.close()
        self.temp.cleanup()

    def verification(self):
        return {"instrument": instrument(), "inputs": {"x": 2, "gain": 3, "offset": 4}, "expected": {"result": 10},
                "dependencies": {"local-facts": hashlib.sha256(b"affine fixture").hexdigest()}}

    def test_inventory_detects_shared_missing_capability_without_inventing_value(self):
        result = self.service.discover()
        first = result["candidates"][0]
        self.assertEqual(first["id"], "dependency-evidence-reuse")
        self.assertEqual(first["shared_opportunities"], 2)
        self.assertIsNone(first["score"])
        self.assertEqual(len(first["comparison_options"]), 5)

    def test_discovery_inspects_authenticated_workflow_trace(self):
        from bridge.workflow_demo import specification
        created = self.workflows.create(specification())
        state = self.workflows._load(created["id"])
        self.workflows._write(state, "affine.json", json.dumps(instrument()), "instrument")
        self.workflows._verify(state)
        self.workflows._verify(state)
        self.workflows._save(state)
        observed = self.service.status()["observations"]
        self.assertEqual(observed["verification_events"], 2)
        self.assertEqual(observed["repeated_verification_signatures"], 1)
        result = self.service.discover()
        candidate = next(c for c in result["candidates"] if c["id"] == "dependency-evidence-reuse")
        self.assertEqual(candidate["shared_opportunities"], 3)
        self.assertEqual(candidate["observed_evidence"][0]["count"], 1)
        self.assertEqual(candidate["observed_evidence"][0]["runs"][0]["run_id"], created["id"])
        self.assertIsNone(candidate["score"])

    def test_operator_unknown_probability_is_not_invented(self):
        record = self.service.add_opportunity({"title": "A new question", "required_capabilities": ["verification"],
            "verification_probability": None})["opportunity"]
        self.assertIsNone(record["verification_probability"])
        self.assertIsNone(record["prospective_value"])
        self.assertIsNone(record["estimated_cost"])

    def test_invalid_estimates_rejected(self):
        for bad in (-1, 2, True, float("nan")):
            with self.subTest(value=str(bad)), self.assertRaises((BridgeError, ValueError)):
                self.service.add_opportunity({"title": "bad", "verification_probability": bad})

    def test_replay_reactivates_but_does_not_unlock(self):
        replay = self.service.replay({"title": "New verifier observation", "url": "local:observed-checker",
            "observed_at": "2026-01-01T00:00:00Z", "content_sha256": "a" * 64, "capability_ids": ["dependency-evidence-reuse"], "evidence_status": "reported"})
        self.assertEqual(len(replay["reactivated"]), 2)
        self.assertTrue(all(x["unlocked"] is False for x in replay["reactivated"]))
        self.assertTrue(all(x["status"] == "reconsider" for x in replay["state"]["opportunities"]))
        self.assertEqual(replay["state"]["capabilities"][0]["status"], "implemented")

    def test_replay_requires_observed_content_and_timestamp(self):
        base = {"title": "Change", "url": "https://example.com/source", "observed_at": "2026-01-01T00:00:00Z", "content_sha256": "a" * 64}
        for changes in ({"url": "http://example.com"}, {"url": "https://secret@example.com"}, {"content_sha256": "label"},
                        {"observed_at": "2026-01-01T00:00:00"}, {"observed_at": "9999-01-01T00:00:00Z"}):
            with self.subTest(changes=changes), self.assertRaises(BridgeError):
                self.service.replay({**base, **changes})

    def test_callable_evidence_reuse_persists_across_service_restart(self):
        first = self.service.verify_instrument(self.verification())["verification"]
        self.assertTrue(first["accepted"])
        self.assertFalse(first["reused"])
        self.workflows.close()
        self.workflows = WorkflowService(FixtureRuntime([]), self.root / "workspace")
        self.service = GenesisNextService(self.workflows)
        second = self.service.verify_instrument(self.verification())["verification"]
        self.assertTrue(second["reused"])
        self.assertEqual(second["verification_calls"], 0)
        changed = self.verification()
        changed["expected"]["result"] = 11
        result = self.service.verify_instrument(changed)["verification"]
        self.assertFalse(result["accepted"])
        self.assertFalse(result["reused"])

    def test_source_drift_refuses_until_process_restart(self):
        self.service.verify_instrument(self.verification())
        from bridge.genesis_next import source_identity
        source = source_identity()
        source["instruments.py"] = "f" * 64
        with patch("bridge.genesis_next.source_identity", return_value=source), self.assertRaises(BridgeError) as context:
            self.service.verify_instrument(self.verification())
        self.assertEqual(context.exception.code, "GENESIS_SOURCE_DRIFT")
        # A restarted process pins the new loaded source and must invalidate
        # authenticated evidence that belongs to the previous checker identity.
        with patch("bridge.genesis_next.source_identity", return_value=source), patch("bridge.genesis_next._LOADED_SOURCE_IDENTITIES", source):
            result = self.service.verify_instrument(self.verification())["verification"]
        self.assertFalse(result["reused"])
        self.assertTrue(result["accepted"])

    def test_state_tampering_cannot_create_verified_capability(self):
        path = self.service.path
        value = json.loads(path.read_text())
        value["state"]["capabilities"][0]["status"] = "independently_verified"
        path.write_text(json.dumps(value))
        with self.assertRaises(BridgeError):
            self.service.status()

    def test_export_contains_no_private_integrity_key_or_reusable_authority(self):
        self.service.verify_instrument(self.verification())
        exported = self.service.export()
        self.assertNotIn("evidence_index", exported)
        self.assertNotIn("mac", exported)
        self.assertIn("Imports do not inherit authority", exported["export_notice"])
        json.dumps(exported, allow_nan=False)

    def test_demo_requires_explicit_bounded_authorization(self):
        for value in ({}, {"authorize": "yes"}, {"authorize": 1}):
            with self.assertRaises(BridgeError):
                self.service.run_demo(value)
        self.assertEqual(self.service.status()["experiments"], [])

    def test_complete_source_upgrade_and_successor_strong_control(self):
        result = self.service.run_demo({"authorize": True})
        experiment = result["experiment"]
        self.assertEqual(experiment["qualification"]["correctness"], "PASS")
        self.assertFalse(experiment["qualification"]["production_promotion"])
        self.assertEqual(experiment["arms"]["baseline"]["verification_calls"], 7)
        self.assertEqual(experiment["arms"]["candidate"]["verification_calls"], 5)
        self.assertEqual(experiment["arms"]["ordinary"]["verification_calls"], 5)
        self.assertEqual(experiment["successor"]["verdict"], "TIE_WITH_STRONG_ORDINARY_REUSE")
        self.assertFalse(experiment["costs"]["complete_cost_known"])
        self.assertEqual(len(result["state"]["lineage"]), 1)
        cap = next(c for c in result["state"]["capabilities"] if c["id"] == "dependency-evidence-reuse")
        self.assertEqual(cap["status"], "tested")
        self.assertIn("candidate.py", experiment["artifacts"])

    def test_constructor_refuses_modified_source_and_existing_directory(self):
        path = self.root / "candidate"
        made = construct_candidate(path)
        with self.assertRaises(BridgeError):
            construct_candidate(path)
        made["path"].write_text(CANDIDATE_SOURCE + "\nraise Exception('changed')")
        with self.assertRaises(BridgeError):
            load_candidate(made["path"])

    def test_distinct_experiment_selector_reuses_known_and_tests_unknown(self):
        index = EvidenceIndex("checker")
        deps = {"source": "a" * 64}
        known = {"expected": 1}
        index.check(known, deps, lambda: {"accepted": True})
        experiments = [{"id": "known", "priority": 100, "spec": known, "dependencies": deps},
                       {"id": "new", "priority": 10, "spec": {"expected": 2}, "dependencies": deps},
                       {"id": "lower", "priority": 1, "spec": {"expected": 3}, "dependencies": deps}]
        result = select_experiments(index, experiments, 1, lambda spec: {"accepted": True})
        self.assertEqual(result["verification_calls"], 1)
        self.assertEqual(result["unresolved"], ["lower"])
        self.assertTrue(result["outcomes"][0]["reused"])
        self.assertFalse(result["outcomes"][1]["reused"])

    def test_verifier_cannot_change_bound_specification(self):
        index = EvidenceIndex("checker")
        spec, deps = {"value": 1}, {"source": "a" * 64}
        def mutate():
            spec["value"] = 2
            return {"accepted": True}
        with self.assertRaises(BridgeError):
            index.check(spec, deps, mutate)
        self.assertFalse(index.entries)


if __name__ == "__main__":
    unittest.main()
