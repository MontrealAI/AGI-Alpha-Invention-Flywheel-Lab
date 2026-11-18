"""Source-label acquisition closes an ambiguous migration through the ordinary controller."""
from copy import deepcopy
import tempfile
import unittest

from ignition.construction import fingerprint
from ignition.controller import Controller
from ignition.development import projection_scope, resolve_projections
from ignition.store import Store

from action_study.construction.mission import mission as clock_mission


class SourceProjection(unittest.TestCase):
    def setUp(self):
        self.mission, _ = clock_mission()
        self.spec = self.mission["construction_spec"]
        self.pool = self.mission["resources"]["mapping_evidence"]

    def pinned(self):
        self.pool["sha256"] = fingerprint({k: self.pool[k] for k in ("source", "records", "decision_sha256")})

    def run_controller(self):
        work = tempfile.TemporaryDirectory()
        self.addCleanup(work.cleanup)
        ctrl = Controller(Store(work.name))
        rid, rev = ctrl.create({"request_id": "projection-regression", "mission": self.mission})
        return ctrl, rid, rev, ctrl.advance(rid, rev)

    def test_normal_path_delivers_and_remains_within_four_observations(self):
        ctrl, rid, rev, state = self.run_controller()
        self.assertEqual(state["status"], "verified", state.get("error"))
        self.assertEqual(state["routing"]["method"], "evidence_projection")
        self.assertEqual(state["mapping_resolution"]["initial_choices"], {target["name"]: 2 for target in self.spec["definition"]["targets"]})
        self.assertGreater(len(state["mapping_resolution"]["labels_examined"]), 0)
        self.assertLessEqual(len(state["mapping_resolution"]["labels_examined"]), 4)
        self.assertTrue(ctrl.deliver(rid, rev).startswith(b"PK"))

    def test_malformed_confirmation_envelope_is_checked_only_by_evaluator(self):
        self.spec["cases"].append({"name": "unknown rows", "input": {"rows": None}, "error": "invalid_input"})
        _, _, _, state = self.run_controller()
        self.assertEqual(state["status"], "verified", state.get("error"))
        rejection, = [c for c in state["evaluation"]["cases"] if c["name"] == "unknown rows"]
        self.assertTrue(rejection["candidate_pass"])

    def test_altered_bytes_at_pinned_identity_defer(self):
        self.pool["records"][0]["expected"]["landed_hour"] = 882
        _, _, _, state = self.run_controller()
        self.assertEqual(state["status"], "deferred")
        self.assertIn("changed", state["error"])

    def test_no_discriminating_inputs_and_zero_budget_defer(self):
        sample = self.spec["definition"]["demonstrations"][0]
        self.pool["records"] = [{"id": "same-clock", "input": sample["input"]["rows"][0], "expected": sample["expected"]["rows"][0]}]
        self.pool["max_labels"] = 1
        self.pinned()
        _, rec = resolve_projections(self.spec["definition"], self.pool, projection_scope(self.mission))
        self.assertIn("No approved input", rec["obstruction"])
        self.pool["max_labels"] = 0
        _, rec = resolve_projections(self.spec["definition"], self.pool, projection_scope(self.mission))
        self.assertIn("budget", rec["obstruction"])

    def test_disagreeing_observations_for_one_acquired_input_defer(self):
        _, rec = resolve_projections(self.spec["definition"], self.pool, projection_scope(self.mission))
        first, = [r for r in self.pool["records"] if r["id"] == rec["labels_examined"][0]]
        other = deepcopy(first)
        other["id"] = "second-publisher-record"
        other["expected"]["written_date"] = "contradictory"
        self.pool["records"] = [first, other]
        self.pool["max_labels"] = 2
        self.pinned()
        _, rec = resolve_projections(self.spec["definition"], self.pool, projection_scope(self.mission))
        self.assertIn("contradicts", rec["obstruction"])
        self.assertEqual(len(rec["labels_examined"]), 2)

    def test_genuine_source_fields_do_not_attest_a_different_purpose(self):
        self.mission["purpose"] = self.spec["purpose"] = "Certify contributors' working hours from the two Git clocks."
        _, _, _, state = self.run_controller()
        self.assertEqual(state["status"], "deferred")
        self.assertIn("different beneficiary purpose", state["error"])
        self.assertEqual(state["mapping_resolution"]["labels_examined"], [])

    def test_overlapping_confirmation_cannot_enter_source_pool(self):
        case = self.spec["cases"][0]
        self.pool["records"][0]["input"] = case["input"]["rows"][0]
        self.pinned()
        _, _, _, state = self.run_controller()
        self.assertEqual(state["status"], "deferred")
        self.assertIn("overlaps", state["error"])

    def test_wider_transform_still_has_access_to_open_direct_route(self):
        del self.mission["resources"]["mapping_evidence"]
        self.mission["resources"].update(execution_strategy="direct", direct_method="model")
        _, _, _, state = self.run_controller()
        self.assertEqual(state["routing"]["method"], "model")
        self.assertEqual(state["status"], "blocked")
