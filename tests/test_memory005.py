import copy
import json
from pathlib import Path
import tempfile
import unittest

from mechanisms.memory import acquire, digest, failed_transfer, generate, generate_bundle, ordinary_bundle, ordinary_generate, retain


ROOT = Path(__file__).resolve().parents[1]


class MemoryAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.memory = Path(self.temporary.name) / "retained"
        self.task = {"id": "investigation-A", "phases": [
            {"id": "reserve_A", "kind": "reserve", "unit": "event", "deps": []},
            {"id": "init_A", "kind": "initialization", "unit": "event", "deps": ["reserve_A"]},
            {"id": "work_A", "kind": "measurement", "unit": "event", "deps": ["init_A"]},
            {"id": "publish_A", "kind": "commit", "unit": "event", "deps": ["work_A"]}], "conditions": {"recoverable": True}}
        self.graph = {"id": "donor-transaction", "nodes": [
            {"id": "r", "kind": "reserve", "unit": "event"}, {"id": "i", "kind": "initialization", "unit": "event"}, {"id": "w", "kind": "measurement", "unit": "event"}, {"id": "p", "kind": "commit", "unit": "event"}],
            "relations": [["r", "precedes", "i"], ["i", "precedes", "w"], ["w", "precedes", "p"]], "conditions": {"recoverable": True}}
        self.mapping = {"source_graph": self.graph, "target_events": {"r": "reserve_A", "i": "init_A", "w": "work_A", "p": "publish_A"}}
        self.before = {"language": "event-plan/v1", "order": ["reserve_A", "init_A", "work_A", "publish_A"], "protected": ["work_A"], "atomic": [], "compensations": {}}
        self.after = {**self.before, "protected": ["init_A", "work_A"]}
        self.obligations = [{"kind": "protect", "phase_ids": ["init_A"], "status": "established"}]
        self.receipt = {"before_sha256": digest(self.before), "after_sha256": digest(self.after), "before_passed": False, "after_passed": True, "costs": {"verification_cpu_seconds": 0.1}}
        self.target = {"id": "successor-B", "phases": [
            {"id": "allocate_B", "kind": "reserve", "unit": "event", "deps": []},
            {"id": "load_B", "kind": "initialization", "unit": "event", "deps": ["allocate_B"]},
            {"id": "infer_B", "kind": "measurement", "unit": "event", "deps": ["load_B"]},
            {"id": "release_B", "kind": "commit", "unit": "event", "deps": ["infer_B"]}], "conditions": {"recoverable": True}}

    def acquire(self):
        return acquire(self.task, self.mapping, self.before, self.after, self.obligations, self.receipt, ROOT)

    def test_actual_delta_becomes_role_recipe_without_target_literal(self):
        record = self.acquire()
        operator = record["generative_operator"]["program"]
        self.assertEqual(operator["role_deltas"], [{"kind": "protect", "role_ids": ["i"]}])
        self.assertEqual(operator["base_role_obligations"], [{"kind": "protect", "role_ids": ["w"]}])
        self.assertNotIn("init_A", json.dumps(operator))
        self.assertEqual(record["provenance"]["before_sha256"], digest(self.before))
        self.assertIsNone(record["costs"]["complete_cost_usd"])

    def test_adjudication_identity_and_real_transition_required(self):
        self.receipt["after_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "VERIFICATION_IDENTITY_MISMATCH"):
            self.acquire()
        self.receipt["after_sha256"] = digest(self.after)
        self.obligations[0]["status"] = "hypothesis"
        with self.assertRaisesRegex(ValueError, "UNADJUDICATED_REPAIR_DELTA"):
            self.acquire()
        self.obligations[0]["status"] = "established"
        self.receipt["before_passed"] = True
        with self.assertRaisesRegex(ValueError, "VERIFIED_REPAIR_TRANSITION_REQUIRED"):
            self.acquire()

    def test_store_retrieve_remap_and_competitive_equivalent_content(self):
        retained = retain(self.memory, self.task, self.mapping, self.before, self.after, self.obligations, self.receipt, ROOT)
        learned = generate(self.memory, self.target, [], ROOT, 64)
        ordinary = ordinary_generate(retained["record"], self.target, [], ROOT, 64)
        self.assertEqual(learned["status"], "constructed")
        self.assertEqual(learned["program"], ordinary["program"])
        self.assertIn("load_B", learned["program"]["protected"])
        self.assertIn("infer_B", learned["program"]["protected"])
        self.assertNotIn("init_A", json.dumps(learned["program"]))
        self.assertTrue(learned["memory_instantiation"]["fresh_target"])
        self.assertEqual(learned["memory"]["id"], retained["id"])

    def test_removed_operator_preserves_base_and_incompatible_scope_refuses(self):
        record = self.acquire()
        record["generative_operator"]["program"]["role_deltas"] = []
        from flywheel.retention import store
        store(self.memory, record)
        result = generate(self.memory, self.target, [], ROOT, 64)
        self.assertEqual(result["status"], "constructed")
        self.assertEqual(result["program"]["protected"], ["infer_B"])
        self.assertEqual(result["memory_instantiation"]["learned_role_delta_count"], 0)
        self.target["conditions"]["recoverable"] = False
        result = generate(self.memory, self.target, [], ROOT, 64)
        self.assertEqual(result["memory"]["retrieval"]["refused"][0]["reason"], "INAPPLICABLE_TYPED_CONDITIONS")

    def test_full_repaired_procedure_reconstructs_on_fresh_ids(self):
        self.before["protected"] = ["init_A"]
        self.after = {**self.before, "protected": ["init_A", "work_A", "publish_A"], "atomic": ["publish_A"]}
        self.obligations = [{"kind": "protect", "phase_ids": ["work_A", "publish_A"], "status": "established"}, {"kind": "atomic_publish", "phase_ids": ["publish_A"], "status": "established"}]
        self.receipt.update({"before_sha256": digest(self.before), "after_sha256": digest(self.after)})
        retained = retain(self.memory, self.task, self.mapping, self.before, self.after, self.obligations, self.receipt, ROOT)
        result = generate(self.memory, self.target, [], ROOT, 64)
        self.assertEqual(result["status"], "constructed")
        self.assertEqual(set(result["program"]["protected"]), {"load_B", "infer_B", "release_B"})
        self.assertEqual(result["program"]["atomic"], ["release_B"])
        self.assertNotIn("publish_A", json.dumps(retained["record"]["generative_operator"]))
        ablated = copy.deepcopy(retained["record"])
        ablated["generative_operator"]["program"]["role_deltas"] = []
        base = ordinary_generate(ablated, self.target, [], ROOT, 64)
        self.assertEqual(base["program"]["protected"], ["load_B"])
        self.assertEqual(base["program"]["atomic"], [])

    def test_failed_mapping_keeps_scoped_costs_and_no_generator(self):
        retained = failed_transfer(self.memory, self.task, self.mapping, "causal mismatch", ROOT, {"cpu_seconds": 0.5})
        self.assertEqual(retained["record"]["verification"]["status"], "failed")
        self.assertEqual(retained["record"]["costs"]["cpu_seconds"], 0.5)
        result = generate(self.memory, self.target, [], ROOT, 64)
        self.assertEqual(result["status"], "refused")
        self.assertEqual(len(result["memory"]["retrieval"]["failures"]), 1)

    def test_separately_verified_instruments_combine_under_external_objective(self):
        from mechanisms.construct import interpret
        empty = {**self.before, "protected": [], "atomic": []}
        instruments = []
        for kind, field, event, scope in (("protect", "protected", "init_A", "initialization-interruption-marker"), ("atomic_publish", "atomic", "publish_A", "atomic-publication")):
            task = copy.deepcopy(self.task)
            task["id"] = "acquisition-" + scope
            after = {**empty, field: [event]}
            def outcome(program):
                result = interpret({"task": task, "program": program, "interrupt_at": event, "interrupt_stage": "during"})
                return result["interrupted_marker"] if field == "protected" else not result["partial_publication"]
            receipt = {"before_sha256": digest(empty), "after_sha256": digest(after), "before_passed": outcome(empty), "after_passed": outcome(after), "objective_scope": {"id": scope, "full_combined_objective_verified": False}}
            instruments.append(retain(self.memory, task, self.mapping, empty, after, [{"kind": kind, "phase_ids": [event], "status": "established"}], receipt, ROOT))
        limits = {"max_candidates": 64, "max_combinations": 4, "max_bundle_size": 2}
        inherited = generate_bundle(self.memory, self.target, [], ROOT, limits)
        ordinary = ordinary_bundle(instruments, self.target, [], ROOT, limits)
        def accepted(program):
            marker = interpret({"task": self.target, "program": program, "interrupt_at": "load_B"})["interrupted_marker"]
            atomic = not interpret({"task": self.target, "program": program, "interrupt_at": "release_B", "interrupt_stage": "during"})["partial_publication"]
            return marker and atomic
        outcomes = [(item["memory_bundle"]["record_count"], accepted(item["program"])) for item in inherited["candidates"]]
        self.assertEqual(outcomes, [(0, False), (1, False), (1, False), (2, True)])
        self.assertEqual([item["program"] for item in inherited["candidates"]], [item["program"] for item in ordinary["candidates"]])
        self.assertEqual(inherited["memory"]["evaluated_candidates"], sum(len(item["attempts"]) for item in inherited["candidates"]))
        self.assertEqual(inherited["memory"]["combinations_considered"], 4)
        self.assertIsNone(inherited["program"])
        self.assertEqual(inherited["candidates"][-1]["memory_bundle"]["verification_scopes"][0]["full_combined_objective_verified"], False)
        deduplicated = ordinary_bundle(instruments + [instruments[0]], self.target, [], ROOT, limits)
        self.assertEqual(deduplicated["memory"]["duplicate_records_ignored"], 1)
        self.assertEqual(len(deduplicated["candidates"]), 4)
        bounded = generate_bundle(self.memory, self.target, [], ROOT, {**limits, "max_candidates": 1})
        self.assertEqual(bounded["status"], "exhausted")
        self.assertEqual(bounded["memory"]["evaluated_candidates"], 1)

    def test_bundle_missing_inapplicable_or_corrupted_sources_cannot_supply_operator(self):
        record = self.acquire()
        missing = generate_bundle(self.memory, self.target, [], ROOT, 64)
        self.assertEqual([item["memory_bundle"]["record_count"] for item in missing["candidates"]], [0])
        bad = copy.deepcopy(record)
        bad["applicability"]["conditions"]["recoverable"] = False
        corrupt = copy.deepcopy(record)
        corrupt["instrument"]["sha256"] = "0" * 64
        result = ordinary_bundle([bad, corrupt], self.target, [], ROOT, 64)
        self.assertEqual([item["memory_bundle"]["record_count"] for item in result["candidates"]], [0])
        self.assertEqual(len(result["memory"]["refused"]), 2)


if __name__ == "__main__":
    unittest.main()
