# SPDX-License-Identifier: Apache-2.0
"""Reviewer-owned tests for the frozen omega-evidence-reuse/1 protocol.

These are authored qualification cases, not blinded external benchmarks.
They use the original interpreter and independent expected answers. The
candidate never receives the test file as an editable construction target.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bridge.adapters import BridgeError
from bridge.genesis_next import EvidenceIndex, construct_candidate, load_candidate
from bridge.instruments import evaluate
from bridge.workflow_demo import FixtureRuntime


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def addition():
    return {
        "name": "Reviewer arithmetic fixture",
        "inputs": ["x", "offset"],
        "outputs": {"result": {"op": "add", "args": [{"field": "x"}, {"field": "offset"}]}},
        "conditions": "Explicit integer arithmetic only.",
        "limitations": "No empirical or commercial claims.",
    }


def case(x=23, offset=19, expected=42):
    return {"instrument": addition(), "input": {"x": x, "offset": offset}, "expected": {"result": expected}}


def verify(spec):
    actual = evaluate(spec["instrument"], spec["input"])["output"]
    return {"passed": actual == spec["expected"], "output": actual}


class EvidenceReuseIndependentTests(unittest.TestCase):
    def setUp(self):
        self.checker = sha("reviewer arithmetic evaluator version 1")
        self.deps = {"bridge/instruments.py": sha("original interpreter"), "source": sha("explicit integer arithmetic")}

    def index(self, **kwargs):
        return EvidenceIndex(self.checker, **kwargs)

    def check(self, index, spec=None, dependencies=None):
        spec = case() if spec is None else spec
        return index.check(spec, self.deps if dependencies is None else dependencies, lambda: verify(spec))

    def test_c01_exact_reuse_matches_original_evaluator(self):
        index = self.index()
        first = self.check(index)
        second = self.check(index)
        self.assertTrue(first["accepted"])
        self.assertFalse(first["reused"])
        self.assertTrue(second["accepted"])
        self.assertTrue(second["reused"])
        self.assertEqual(first["result"], second["result"])
        self.assertEqual(index.verification_calls, 1)

    def test_c02_same_name_different_instrument_is_not_reused(self):
        index = self.index()
        self.check(index)
        changed = case()
        changed["instrument"]["outputs"]["result"]["op"] = "mul"
        result = self.check(index, changed)
        self.assertFalse(result["reused"])
        self.assertFalse(result["accepted"])
        self.assertEqual(result["result"]["output"], {"result": 437})

    def test_c03_new_input_and_changed_acceptance_revalidate(self):
        index = self.index()
        self.check(index)
        valid = self.check(index, case(x=17, offset=29, expected=46))
        invalid = self.check(index, case(x=17, offset=29, expected=47))
        self.assertTrue(valid["accepted"])
        self.assertFalse(valid["reused"])
        self.assertFalse(invalid["accepted"])
        self.assertFalse(invalid["reused"])
        self.assertEqual(index.verification_calls, 3)

    def test_c04_checker_identity_separates_keys_and_requires_verification(self):
        original = self.index()
        self.check(original)
        revised = EvidenceIndex(sha("reviewer version 2"))
        self.assertNotEqual(original.key(case(), self.deps), revised.key(case(), self.deps))
        outcome = self.check(revised)
        self.assertFalse(outcome["reused"])
        self.assertEqual(revised.verification_calls, 1)

    def test_c05_changed_removed_added_dependency_cannot_hit_old_entry(self):
        for variant in ("changed", "removed", "added"):
            with self.subTest(variant=variant):
                index = self.index()
                self.check(index)
                dependencies = dict(self.deps)
                if variant == "changed":
                    dependencies["source"] = sha("different facts")
                elif variant == "removed":
                    del dependencies["source"]
                else:
                    dependencies["new-source"] = sha("new requirement")
                result = self.check(index, dependencies=dependencies)
                self.assertFalse(result["reused"])
                self.assertEqual(index.verification_calls, 2)

    def test_c06_targeted_invalidation_preserves_independent_entry(self):
        index = self.index()
        other = {"independent-source": sha("unrelated")}
        self.check(index)
        self.check(index, dependencies=other)
        index.invalidate(["source"])
        self.assertTrue(self.check(index, dependencies=other)["reused"])
        self.assertFalse(self.check(index)["reused"])
        self.assertEqual(index.verification_calls, 3)

    def test_c07_object_key_order_does_not_create_fake_difference(self):
        index = self.index()
        original = case()
        reordered = {key: original[key] for key in reversed(list(original))}
        reversed_deps = {key: self.deps[key] for key in reversed(list(self.deps))}
        first = self.check(index, original)
        second = self.check(index, reordered, reversed_deps)
        self.assertEqual(first["key"], second["key"])
        self.assertTrue(second["reused"])

    def test_c08_mutating_returned_value_cannot_poison_evidence(self):
        index = self.index()
        first = self.check(index)
        first["result"]["output"]["result"] = -999
        result = self.check(index)
        self.assertEqual(result["result"]["output"], {"result": 42})
        self.assertTrue(result["accepted"])

    def test_c08_mutating_verifier_owned_value_cannot_poison_evidence(self):
        index = self.index()
        original_result = verify(case())
        index.check(case(), self.deps, lambda: original_result)
        original_result["output"]["result"] = 0
        result = self.check(index)
        self.assertEqual(result["result"]["output"], {"result": 42})

    def test_c08_input_mutation_during_verification_cannot_bind_another_result(self):
        index = self.index()
        mutable = case()
        def changing_verifier():
            mutable["input"]["x"] = 24
            mutable["expected"]["result"] = 43
            return verify(mutable)
        try:
            index.check(mutable, self.deps, changing_verifier)
        except (BridgeError, ValueError):
            pass
        original = self.check(index)
        self.assertFalse(original["reused"])
        self.assertEqual(original["result"]["output"], {"result": 42})

    def test_c09_corrupted_archive_is_refused_or_revalidated(self):
        index = self.index()
        self.check(index)
        archive = index.export()
        corrupted = copy.deepcopy(archive)
        # An intact schema and entry list with a changed integrity receipt must
        # never become acceptance authority. No candidate internals are used.
        corrupted["sha256"] = "0" * 64
        restored = self.index()
        try:
            restored.import_archive(corrupted)
        except (BridgeError, ValueError, TypeError, KeyError):
            return
        result = self.check(restored)
        self.assertFalse(result["reused"])
        self.assertEqual(restored.verification_calls, 1)

    def test_c09_self_consistent_import_is_not_authenticated_authority(self):
        index = self.index()
        self.check(index)
        restored = self.index()
        restored.import_archive(index.export())
        result = self.check(restored)
        self.assertFalse(result["reused"])
        self.assertEqual(restored.verification_calls, 1)

    def test_c10_pre_cancel_does_not_retain_a_success(self):
        index = self.index()
        try:
            result = index.check(case(), self.deps, lambda: verify(case()), cancelled=True)
            self.assertFalse(result["accepted"])
        except (BridgeError, ValueError):
            pass
        self.assertFalse(self.check(index)["reused"])

    def test_c10_cancellation_during_verification_discards_late_result(self):
        index = self.index()
        cancelled = [False]
        def late_result():
            cancelled[0] = True
            return verify(case())
        try:
            result = index.check(case(), self.deps, late_result, cancelled=lambda: cancelled[0])
            self.assertFalse(result["accepted"])
        except (BridgeError, ValueError):
            pass
        self.assertFalse(self.check(index)["reused"])

    def test_c11_semantic_failure_never_becomes_accepted_evidence(self):
        index = self.index()
        invalid = case(expected=43)
        for _ in range(2):
            result = self.check(index, invalid)
            self.assertFalse(result["accepted"])
        valid = self.check(index)
        self.assertTrue(valid["accepted"])
        self.assertFalse(valid["reused"])

    def test_c12_nonfinite_and_malformed_inputs_are_rejected(self):
        index = self.index()
        for bad in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=str(bad)):
                invalid = case(x=bad)
                with self.assertRaises((BridgeError, ValueError, TypeError)):
                    index.key(invalid, self.deps)
        for deps in (None, [], {"source": "not-a-sha256"}):
            with self.subTest(deps=deps):
                with self.assertRaises((BridgeError, ValueError, TypeError)):
                    index.key(case(), deps)

    def test_c12_record_size_is_bounded(self):
        index = self.index()
        with self.assertRaises((BridgeError, ValueError, TypeError)):
            index.key({"oversized": "x" * (17 * 1024 * 1024)}, self.deps)

    def test_expiry_forces_revalidation_without_changing_answer(self):
        clock = [100.0]
        index = self.index(ttl_seconds=10, clock=lambda: clock[0])
        self.check(index)
        clock[0] = 111.0
        result = self.check(index)
        self.assertFalse(result["reused"])
        self.assertTrue(result["accepted"])
        self.assertEqual(index.verification_calls, 2)

    def test_c02_candidate_binds_artifact_type_as_well_as_bytes(self):
        # The original checker rejects source records presented as instruments.
        # Same content is not the same acceptance contract when metadata differs.
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            made = construct_candidate(root / "candidate")
            candidate_class = load_candidate(made["path"])
            service = candidate_class(FixtureRuntime([]), root / "runs", self.index(), self.deps)
            try:
                spec = {"objective": "Check artifact metadata without using any model",
                        "roles": {"builder": {"provider": "fixture", "model": "none"}},
                        "acceptance": [{"kind": "instrument", "artifact": "calculation.json",
                                        "input": {"x": 23, "offset": 19}, "expected": {"result": 42}}]}
                raw = json.dumps(addition())
                decisions = []
                for kind in ("instrument", "source"):
                    state = service._load(service.create(spec)["id"])
                    service._write(state, "calculation.json", raw, kind)
                    service._verify(state)
                    decisions.append(state["verification"]["passed"])
                self.assertEqual(decisions, [True, False])
            finally:
                service.close()

    def test_candidate_file_cannot_rewrite_evaluation_authority(self):
        with tempfile.TemporaryDirectory() as root:
            source = construct_candidate(Path(root) / "candidate")["path"]
            evaluator_before = hashlib.sha256((ROOT / "bridge/instruments.py").read_bytes()).hexdigest()
            self.assertEqual({p.name for p in source.parent.iterdir()}, {"candidate.py"})
            source.write_text(source.read_text() + "\nraise RuntimeError('candidate tried to expand authority')\n")
            with self.assertRaises(BridgeError):
                load_candidate(source)
            self.assertEqual(hashlib.sha256((ROOT / "bridge/instruments.py").read_bytes()).hexdigest(), evaluator_before)


if __name__ == "__main__":
    unittest.main()
