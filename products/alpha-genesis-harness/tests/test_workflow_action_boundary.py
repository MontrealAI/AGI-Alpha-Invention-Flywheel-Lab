# SPDX-License-Identifier: Apache-2.0
"""Durable artifacts still receive acceptance checks at the action boundary."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bridge.workflow_demo import FixtureRuntime, proposal, specification
from bridge.workflows import WorkflowService


class ActionBoundaryTests(unittest.TestCase):
    def test_budget_truncation_keeps_verification_and_critic(self):
        spec = specification()
        spec["max_actions"] = 1
        build = proposal(True)
        build["actions"] = build["actions"][:1] + [{"tool": "read_artifact", "name": "affine.json"}]
        runtime = FixtureRuntime([build, {"verdict": "accept", "feedback": "Frozen checks passed."}])
        with tempfile.TemporaryDirectory() as directory:
            service = WorkflowService(runtime, directory)
            try:
                first = service.step(service.create(spec)["id"])
                self.assertEqual(first["actions"], 1)
                self.assertTrue(first["verification"]["passed"])
                self.assertEqual(first["phase"], "critic")
                self.assertIn("actions_truncated", [event["kind"] for event in first["events"]])
                final = service.step(first["id"])
                self.assertEqual(final["status"], "complete")
                self.assertEqual(final["model_calls"], 2)
            finally:
                service.close()

    def test_last_action_rechecks_changed_artifact_instead_of_retaining_old_pass(self):
        spec = specification()
        spec["max_actions"] = 2
        first = proposal(True)
        first["actions"] = first["actions"][:1]
        repair = proposal(False)
        repair["actions"] = repair["actions"][:1] + [{"tool": "read_artifact", "name": "affine.json"}]
        runtime = FixtureRuntime([first, {"verdict": "revise", "feedback": "Exercise repair path."},
                                  repair, {"verdict": "accept", "feedback": "Model claim alone cannot pass."}])
        with tempfile.TemporaryDirectory() as directory:
            service = WorkflowService(runtime, directory)
            try:
                state = service.step(service.create(spec)["id"])
                self.assertTrue(state["verification"]["passed"])
                service.step(state["id"])
                changed = service.step(state["id"])
                self.assertFalse(changed["verification"]["passed"])
                self.assertEqual(changed["phase"], "critic")
                reviewed = service.step(state["id"])
                self.assertNotEqual(reviewed["status"], "complete")
                final = service.step(state["id"])
                self.assertEqual(final["status"], "exhausted")
                self.assertFalse(final["verification"]["passed"])
            finally:
                service.close()


if __name__ == "__main__":
    unittest.main()
